"""Effect results driven by die rolls."""

import random

from ..common import new_id


class DiceEffectsMixin:
    def _rules_result_destroy_target_tokens_for_controller(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "card"
        ), None)
        item = self.find_battlefield_item((target or {}).get("itemId"))
        if item is None:
            return {"kind": result.get("kind"), "status": "target_missing"}
        controller_id = self.rules_item_controller_id(item)
        base = self.rules_manifestation_base_power(item)
        movement = self._rules_remove_field_item_by_effect(
            item, item.get("ownerId"), "graveyard", "top", reason="destroy"
        )
        self.prune_rules_ongoing_effects()
        if movement.get("status") not in {"moved", "removed_copy"}:
            return {"kind": result.get("kind"), "status": movement.get("status")}
        created = [
            self.create_rules_token_copy(
                (action.get("source") or {}).get("cardId"), controller_id,
                source_item_id=(action.get("source") or {}).get("itemId"),
                hollow=True, effects_disabled=True, generic_power=1,
            )
            for _index in range(max(0, base))
        ]
        created = [item for item in created if item is not None]
        return {
            "kind": result.get("kind"), "status": "destroyed",
            "controllerId": controller_id, "tokens": len(created),
        }

    def _rules_result_roll_d6_gain_half_essence(self, action, result, player_id, player):
        roll = random.randint(1, 6)
        amount = (roll + 1) // 2
        owner_id = action.get("controllerId") or player_id
        self.add_rules_excess_essence(
            owner_id, [{"temperament": "transcendent", "amount": amount, "retained": True}]
        )
        return {
            "kind": result.get("kind"), "status": "rolled",
            "roll": roll, "essences": amount, "playerId": owner_id,
        }

    def _rules_result_roll_discard_deck_gain_power(self, action, result, player_id, player):
        source_item = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
        if result.get("kind") == "roll_discard_deck_gain_power":
            roll = random.randint(1, 6)
            discarded = 0
            deck = self.players[player_id]["zones"]["deck"]
            for _index in range(min(roll, len(deck))):
                error, _owner, replacement = self.move_zone_card_by_effect(
                    player_id, "deck", player_id, "graveyard", deck[0], "top"
                )
                if error:
                    break
                if not replacement:
                    discarded += 1
            if source_item is not None:
                source_item["rollDiscarded"] = discarded
            if discarded and source_item is not None:
                self.adjust_rules_power_counter(source_item, discarded)
            return {
                "kind": result.get("kind"), "status": "resolved",
                "roll": roll, "discarded": discarded,
            }
        trigger = (action.get("ability") or {}).get("trigger") or {}
        amount = int(trigger.get("sourceRollDiscarded", (source_item or {}).get("rollDiscarded")) or 0)
        discarded = {}
        for pid in self.players:
            if pid == player_id:
                continue
            deck = self.players[pid]["zones"]["deck"]
            for _index in range(min(amount, len(deck))):
                error, _owner, replacement = self.move_zone_card_by_effect(
                    pid, "deck", pid, "graveyard", deck[0], "top"
                )
                if error:
                    break
                discarded[pid] = discarded.get(pid, 0) + (0 if replacement else 1)
        return {
            "kind": result.get("kind"),
            "status": "discarded" if discarded else "nothing", "discarded": discarded,
        }

    def _rules_result_roll_d6_move_source_to_stalemate_on_odd(self, action, result, player_id, player):
        source_item = self.find_battlefield_item(
            (action.get("source") or {}).get("itemId")
        )
        roll = random.randint(1, 6)
        if source_item is None:
            return {
                "kind": result.get("kind"),
                "status": "source_missing", "roll": roll,
            }
        source_item.setdefault("counters", {})["Roll"] = roll
        moved = roll % 2 == 1
        if moved:
            source_item["fieldZone"] = "stalemate"
            source_item.pop("isSupport", None)
            source_item.pop("supportUntilTurn", None)
        return {
            "kind": result.get("kind"),
            "status": "moved" if moved else "unchanged",
            "roll": roll, "itemId": source_item.get("id"),
            "fieldZone": self.rules_field_zone(source_item),
        }

    def _rules_result_score_controller_then_destroy_source(self, action, result, player_id, player):
        source_item = self.find_battlefield_item(
            (action.get("source") or {}).get("itemId")
        )
        controller_id = action.get("controllerId") or player_id
        delta = self.adjust_rules_score(
            controller_id, int(result.get("value") or 0)
        )
        movement = self._rules_remove_field_item_by_effect(
            source_item, source_item.get("ownerId"), "graveyard", "top",
            reason="destroy",
        ) if source_item is not None else {"status": "source_missing"}
        return {
            "kind": result.get("kind"),
            "status": "resolved",
            "playerId": controller_id,
            "delta": delta,
            "score": self.players[controller_id]["score"],
            "movement": movement,
        }

    def _rules_result_roll_d6_power_by_parity(self, action, result, player_id, player):
        roll = random.randint(1, 6)
        value = (
            int(result.get("even") or 0)
            if roll % 2 == 0 else int(result.get("odd") or 0)
        )
        source_item = self.find_battlefield_item(
            (action.get("source") or {}).get("itemId")
        )
        if source_item is None:
            return {
                "kind": result.get("kind"),
                "status": "source_missing",
                "roll": roll,
            }
        effect = {
            "id": new_id(), "actionId": action.get("id"),
            "abilityId": (action.get("ability") or {}).get("id"),
            "controllerId": player_id,
            "source": dict(action.get("source") or {}),
            "target": {
                "kind": "card", "itemId": source_item["id"],
                "cardId": source_item.get("cardId"),
                "ownerId": source_item.get("ownerId"),
            },
            "kind": "power_modifier",
            "duration": "while_target_on_field",  # Plinius keeps its roll
            "startedTurn": self.phase_tracker["turn"],
            "value": value,
        }
        self.append_rules_ongoing_effect(effect)
        return {
            "kind": result.get("kind"),
            "status": "resolved",
            "roll": roll, "value": value,
            "effectId": effect["id"],
        }

    def _rules_result_roll_d6_target_table(self, action, result, player_id, player):
        roll = random.randint(1, 6)
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "card"
        ), None)
        item = self.find_battlefield_item(
            target.get("itemId") if target else None
        )
        if item is None:
            return {
                "kind": result.get("kind"),
                "status": "target_missing", "roll": roll,
            }
        table = result.get("table")
        if table == "greed":
            value = 0 if roll <= 2 else -1 if roll <= 4 else -2
            if value:
                effect = {
                    "id": new_id(), "actionId": action.get("id"),
                    "abilityId": (action.get("ability") or {}).get("id"),
                    "controllerId": player_id,
                    "source": dict(action.get("source") or {}),
                    "target": dict(target),
                    "kind": "power_modifier",
                    "duration": "while_target_on_field",  # no printed duration: a permanent modifier
                    "startedTurn": self.phase_tracker["turn"],
                    "value": value,
                }
                self.append_rules_ongoing_effect(effect)
            return {
                "kind": result.get("kind"),
                "status": "resolved", "table": table,
                "roll": roll, "value": value,
            }
        if roll <= 2:
            nested = {
                **action,
                "ability": {
                    **(action.get("ability") or {}),
                    "result": {
                        "kind": "move_target",
                        "zone": "graveyard",
                        "position": "top",
                        "reason": "destroy",
                    },
                },
            }
            effect_result = self.apply_rules_action_result(nested)
        elif roll == 3:
            self.set_rules_item_temperament(item, "hollow", action)
            effect_result = {"status": "temperament", "temperament": "hollow"}
        else:
            value = 2 if roll <= 5 else 3
            effect = {
                "id": new_id(), "actionId": action.get("id"),
                "abilityId": (action.get("ability") or {}).get("id"),
                "controllerId": player_id,
                "source": dict(action.get("source") or {}),
                "target": dict(target),
                "kind": "power_modifier",
                "duration": "while_target_on_field",  # no printed duration: a permanent modifier
                "startedTurn": self.phase_tracker["turn"],
                "value": value,
            }
            self.append_rules_ongoing_effect(effect)
            effect_result = {"status": "power", "value": value}
        return {
            "kind": result.get("kind"),
            "status": "resolved", "table": table,
            "roll": roll, "outcome": effect_result,
        }

    def _rules_result_roll_d6_each_target(self, action, result, player_id, player):
        rolls = []
        hits = []
        for target in action.get("targets") or []:
            if target.get("kind") != "card":
                continue
            roll = random.randint(1, 6)
            hit = roll in {1, 6}
            entry = {"cardId": target.get("cardId"), "itemId": target.get("itemId"), "roll": roll, "hit": hit}
            rolls.append(roll)
            if hit and result.get("onHit") == "destroy":
                if self.find_battlefield_item(target.get("itemId")) is None:
                    entry["status"] = "target_missing"
                else:
                    entry["movement"] = self.apply_rules_action_result({
                        **action,
                        "targets": [dict(target)],
                        "ability": {
                            **(action.get("ability") or {}),
                            "result": {"kind": "move_target", "zone": "graveyard", "position": "top", "reason": "destroy"},
                        },
                    })
            hits.append(entry)
        payload = {
            "kind": "roll_d6_each_target", "status": "resolved", "onHit": result.get("onHit"),
            "rolls": rolls, "results": hits, "hitCount": sum(entry["hit"] for entry in hits),
        }
        if result.get("onHit") == "points":
            payload["playerId"] = player_id
            payload["delta"] = self.adjust_rules_score(player_id, int(result.get("points") or 0) * payload["hitCount"])
            payload["score"] = self.players.get(player_id, {}).get("score")
        return payload

    def _rules_result_roll_d6_conditional_source(self, action, result, player_id, player):
        roll = random.randint(1, 6)
        source_item = self.find_battlefield_item(
            (action.get("source") or {}).get("itemId")
        )
        if source_item is None:
            return {
                "kind": result.get("kind"),
                "status": "source_missing", "roll": roll,
            }
        source_item.setdefault("counters", {})["Roll"] = roll
        if roll % 2 == 0:
            draw = self.request_rules_draw(player_id, 1, player_id)
            return {
                "kind": result.get("kind"),
                "status": "draw", "roll": roll,
                "draw": draw,
            }
        candidates = [
            item["id"] for item in self.battlefield
            if item is not source_item
            and item.get("faceUp")
            and self.rules_item_controller_id(item) == player_id
        ]
        if not candidates:
            return {
                "kind": result.get("kind"),
                "status": "no_target", "roll": roll,
            }
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id,
            "kind": "random_target_effect",
            "playerId": player_id,
            "sourceCardId": source_item.get("cardId"),
            "sourceItemId": source_item.get("id"),
            "candidateItemIds": candidates,
            "roll": roll,
            "effectKind": "lose_effects",
        }
        return {
            "kind": "choice_required",
            "choiceId": choice_id,
            "choiceKind": "random_target_effect",
            "playerId": player_id,
            "roll": roll,
        }

    def _rules_result_roll_multiple_even_power_odd_discard(self, action, result, player_id, player):
        rolls = [
            random.randint(1, 6)
            for _index in range(int(result.get("rolls") or 0))
        ]
        even_count = sum(roll % 2 == 0 for roll in rolls)
        odd_count = len(rolls) - even_count
        source_item = self.find_battlefield_item(
            (action.get("source") or {}).get("itemId")
        )
        if source_item is not None and even_count:
            self.adjust_rules_power_counter(source_item, even_count)
        discard_count = min(
            odd_count, len(self.players[player_id]["zones"]["hand"])
        )
        choice_id = None
        if discard_count:
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id,
                "kind": "discard_from_hand",
                "playerId": player_id,
                "count": discard_count,
                "sourceCardId": (action.get("source") or {}).get("cardId"),
            }
        return {
            "kind": result.get("kind"),
            "status": "resolved",
            "rolls": rolls,
            "evenCount": even_count,
            "oddCount": odd_count,
            "discardChoiceId": choice_id,
        }

    def _rules_result_score_controller_by_source_roll_then_exile(self, action, result, player_id, player):
        source_item = self.find_battlefield_item(
            (action.get("source") or {}).get("itemId")
        )
        if source_item is None:
            return {
                "kind": result.get("kind"),
                "status": "source_missing",
            }
        roll = int((source_item.get("counters") or {}).get("Roll") or 0)
        loss = 5 if roll <= 2 else 10 if roll <= 4 else 15
        controller_id = self.rules_item_controller_id(source_item)
        delta = self.adjust_rules_score(controller_id, -loss)
        movement = self._rules_remove_field_item_by_effect(
            source_item, source_item.get("ownerId"), "exile", "top"
        )
        return {
            "kind": result.get("kind"),
            "status": "resolved", "roll": roll,
            "playerId": controller_id, "delta": delta,
            "score": self.players[controller_id]["score"],
            "movement": movement,
        }
