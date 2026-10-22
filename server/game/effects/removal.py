"""Effect results that destroy, exile, sacrifice or send cards to the Stalemate Zone."""

import random

from ..common import RULES_WILL_TYPES, new_id


class RemovalEffectsMixin:
    def _rules_result_dissolve_vessel_targets(self, action, result, player_id, player):
        moved, gained = [], 0
        for target in action.get("targets") or []:
            if target.get("kind") != "zone_card" or target.get("zone") != "receptacle":
                continue
            container_id = target.get("containerId")
            card_id = target.get("cardId")
            owner_id = self.card_owner_in_zone(container_id, "receptacle", card_id)
            if owner_id is None or container_id != player_id:
                continue
            error, _owner, replacement = self.move_zone_card_by_effect(
                container_id, "receptacle", owner_id, "deck", card_id, "top"
            )
            if error:
                continue
            random.shuffle(self.players[owner_id]["zones"]["deck"])
            moved.append(card_id)
            if not replacement:
                gained += int(result.get("value") or 0)
        if gained:
            self.adjust_rules_score(player_id, gained)
        return {
            "kind": result.get("kind"),
            "status": "moved" if moved else "nothing",
            "cardIds": moved, "points": gained,
        }

    def _rules_result_destroy_all_tokens(self, action, result, player_id, player):
        removed = []
        for item in list(self.battlefield):
            if item.get("isTokenCard"):
                movement = self._rules_remove_field_item(
                    item, item.get("ownerId"), "graveyard", "top"
                )
                if movement.get("status") in {"moved", "removed_copy"}:
                    removed.append(item["id"])
        self.prune_rules_ongoing_effects()
        return {
            "kind": result.get("kind"),
            "status": "destroyed" if removed else "nothing",
            "itemIds": removed,
        }

    def _rules_result_exile_all_wills_and_interzones(self, action, result, player_id, player):
        removed = []
        for item in list(self.battlefield):
            card_type = self.rules_item_card_rules(item).get("type")
            in_interzone = (
                card_type == "manifestation"
                and self.rules_field_zone(item) == "interzone"
            )
            if card_type not in RULES_WILL_TYPES and not in_interzone:
                continue
            movement = self._rules_remove_field_item(
                item, item.get("ownerId"), "exile", "top"
            )
            if movement.get("status") in {"moved", "removed_copy"}:
                removed.append(item["id"])
        self.prune_rules_ongoing_effects()
        return {
            "kind": result.get("kind"),
            "status": "exiled" if removed else "nothing",
            "itemIds": removed,
        }

    def _rules_result_sacrifice_other_confrontation_for_essence(self, action, result, player_id, player):
        source_id = (action.get("source") or {}).get("itemId")
        sacrificed, limbo = [], 0
        for item in list(self.rules_confrontation_items(player_id, ("confrontation",))):
            if item.get("id") == source_id:
                continue
            movement = self._rules_remove_field_item(
                item, item.get("ownerId"), "graveyard", "top"
            )
            if movement.get("status") == "moved":
                limbo += 1
            if movement.get("status") in {"moved", "removed_copy"}:
                sacrificed.append(item["id"])
        self.prune_rules_ongoing_effects()
        if limbo:
            self.add_rules_excess_essence(
                player_id, [{"temperament": "transcendent", "amount": limbo}]
            )
        return {
            "kind": result.get("kind"),
            "status": "sacrificed" if sacrificed else "nothing",
            "itemIds": sacrificed, "essences": limbo,
        }

    def _rules_result_stalemate_to_support_disabled(self, action, result, player_id, player):
        moved = []
        for item in list(self.rules_confrontation_items(player_id, ("stalemate",))):
            item["stackedOn"] = None
            self.mark_rules_support_entry(item)
            moved.append(item["id"])
        effects = []
        for item_id in moved:
            item = self.find_battlefield_item(item_id)
            effects.extend(self.create_rules_ongoing_effects({
                **action,
                "targets": [{
                    "kind": "card", "itemId": item_id,
                    "cardId": item.get("cardId"), "ownerId": item.get("ownerId"),
                }],
                "ability": {
                    "id": f'{(action.get("ability") or {}).get("id")}:disabled',
                    "ongoingEffect": {
                        "kind": "lose_effects", "duration": "until_end_of_turn",
                    },
                },
            }))
        return {
            "kind": result.get("kind"),
            "status": "supported" if moved else "nothing",
            "itemIds": moved, "effects": len(effects),
        }

    def _rules_result_destroy_persistent_will_refund_essence(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "card"
        ), None)
        item = self.find_battlefield_item((target or {}).get("itemId"))
        metadata = self.card_rules.get((item or {}).get("cardId"), {})
        if item is None or metadata.get("type") != "persistent_will":
            return {"kind": result.get("kind"), "status": "target_missing"}
        controller_id = self.rules_item_controller_id(item)
        essences = self.rules_printed_tribute_essence(item.get("cardId"))
        cost = sum(entry["amount"] for entry in essences)
        movement = self._rules_remove_field_item_by_effect(
            item, item.get("ownerId"), "graveyard", "top", reason="destroy"
        )
        self.prune_rules_ongoing_effects()
        if movement.get("status") not in {"moved", "removed_copy"}:
            return {"kind": result.get("kind"), "status": movement.get("status")}
        refunded = self.add_rules_excess_essence(controller_id, essences)
        return {
            "kind": result.get("kind"), "status": "destroyed",
            "controllerId": controller_id, "essences": cost,
            "temperament": essences[0]["temperament"] if len(essences) == 1 else None,
            "refundedEssence": refunded,
        }

    def _rules_result_karmapult_sacrifice(self, action, result, player_id, player):
        host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
        target = next((e for e in action.get("targets") or [] if e.get("kind") == "card"), None)
        target_item = self.find_battlefield_item((target or {}).get("itemId"))
        if host is None or target_item is None:
            return {"kind": result.get("kind"), "status": "target_missing"}
        sacrificed = [dict(entry) for entry in host.get("attachedCards") or []]
        host["attachedCards"] = []
        self.rules_sync_attached_counter(host)
        for entry in sacrificed:
            self.put_zone_card(entry["ownerId"], "graveyard", entry["cardId"], entry["ownerId"], "top")
        if sacrificed:
            self.rules_engine["ongoingEffects"].append({
                "id": new_id(), "actionId": action.get("id"),
                "abilityId": "karmapult-power-loss",
                "controllerId": action.get("controllerId") or player_id,
                "source": {"cardId": host.get("cardId"), "itemId": host["id"], "zone": "battlefield"},
                "target": {
                    "kind": "card", "itemId": target_item["id"],
                    "cardId": target_item.get("cardId"), "ownerId": target_item.get("ownerId"),
                },
                "kind": "power_modifier", "value": -len(sacrificed),
                "duration": "until_end_of_turn",
                "startedTurn": self.phase_tracker["turn"],
            })
        return {
            "kind": result.get("kind"), "status": "sacrificed" if sacrificed else "nothing_placed",
            "count": len(sacrificed), "cardIds": [e["cardId"] for e in sacrificed],
            "itemId": target_item["id"], "value": -len(sacrificed),
        }

    def _rules_result_destroy_random_vessel_manifestations(self, action, result, player_id, player):
        source = action.get("source") or {}
        container_id = source.get("containerId")
        if container_id not in self.players:
            return {"kind": result.get("kind"), "status": "source_missing"}
        pool = list(self.players[container_id]["zones"].get("receptacle", []))
        if source.get("cardId") in pool:
            pool.remove(source.get("cardId"))
        if (
            container_id != action.get("controllerId")
            and self.rules_vessel_locked(container_id)
        ):
            pool = []
        pool = [
            cid for cid in pool
            if self.card_rules.get(cid, {}).get("type") == "manifestation"
        ]
        random.shuffle(pool)
        destroyed = []
        for card_id in pool[:int(result.get("count") or 1)]:
            owner_id = self.card_owner_in_zone(container_id, "receptacle", card_id)
            if owner_id is None:
                continue
            error, _owner, replacement = self.move_zone_card_by_effect(
                container_id, "receptacle", owner_id, "graveyard", card_id, "top"
            )
            if not error and not replacement:
                destroyed.append(card_id)
        return {
            "kind": result.get("kind"),
            "status": "destroyed" if destroyed else "nothing", "cardIds": destroyed,
        }

    def _rules_result_exile_confrontation_stalemate_and_source(self, action, result, player_id, player):
        removed = []
        source_id = (action.get("source") or {}).get("itemId")
        for item in list(self.rules_confrontation_items(None, ("confrontation", "stalemate"))):
            movement = self._rules_remove_field_item(item, item.get("ownerId"), "exile", "top")
            if movement.get("status") in {"moved", "removed_copy"}:
                removed.append(item["id"])
        source_item = self.find_battlefield_item(source_id)
        if source_item is not None:
            self._rules_remove_field_item(source_item, source_item.get("ownerId"), "exile", "top")
        self.prune_rules_ongoing_effects()
        return {
            "kind": result.get("kind"),
            "status": "exiled" if removed else "nothing", "itemIds": removed,
        }

    def _rules_result_destroy_next_opponent_confrontation_entry(self, action, result, player_id, player):
        for pid in self.players:
            if pid != player_id:
                self.rules_engine.setdefault("destroyNextEntries", []).append({
                    "controllerId": pid, "turn": self.phase_tracker["turn"],
                })
        return {"kind": result.get("kind"), "status": "armed"}

    def _rules_result_stalemate_targets(self, action, result, player_id, player):
        source = action.get("source") or {}
        item_ids = [
            entry.get("itemId") for entry in action.get("targets") or []
            if entry.get("kind") == "card"
        ]
        if result.get("kind") == "stalemate_target_grant_source_support":
            item_ids = [item_id for item_id in item_ids if item_id != source.get("itemId")]
            if not item_ids:
                return {"kind": result.get("kind"), "status": "target_missing"}
        if result.get("includeSource") and source.get("itemId"):
            item_ids.append(source.get("itemId"))
        moved = []
        for item_id in item_ids:
            item = self.find_battlefield_item(item_id)
            if item is None or self.rules_item_zone_locked(item):
                continue
            item["stackedOn"] = None
            self.rules_stalemate_item(item_id)
            if result.get("lockZone"):
                item["zoneLockTurn"] = self.phase_tracker["turn"]
            moved.append(item_id)
        self.prune_rules_ongoing_effects()
        payload = {
            "kind": result.get("kind"),
            "status": "stalemated" if moved else "nothing", "itemIds": moved,
        }
        if result.get("kind") == "stalemate_target_grant_source_support" and moved:
            payload["support"] = self.apply_rules_action_result({
                **action,
                "ability": {**(action.get("ability") or {}), "result": {"kind": "grant_source_support_until_end_turn"}},
            })
        return payload

    def _rules_result_each_player_stalemate_own_confrontation(self, action, result, player_id, player):
        moved, queue = [], []
        for pid in self.players:
            candidates = [
                item["id"] for item in self.rules_confrontation_items(pid)
                if not self.rules_item_zone_locked(item)
            ]
            if len(candidates) == 1:
                moved.append(self.rules_stalemate_item(candidates[0]))
            elif candidates:
                queue.append({"playerId": pid, "candidateItemIds": candidates})
        payload = {"kind": result.get("kind"), "status": "stalemated", "itemIds": moved}
        if queue:
            choice = self.rules_next_pick_own_item_choice(
                queue, action.get("id"),
                (action.get("source") or {}).get("cardId"), moved,
            )
            payload.update({
                "kind": "choice_required", "choiceId": choice["id"],
                "choiceKind": "pick_own_item", "playerId": choice["playerId"],
            })
        return payload

    def _rules_result_stalemate_confrontation(self, action, result, player_id, player):
        if result.get("scope") == "winner":
            winner_id = (self.rules_engine.get("confrontationResult") or {}).get("winnerId")
            items = (
                self.rules_confrontation_items(winner_id)
                if winner_id in self.players else []
            )
        else:
            items = self.rules_confrontation_items()
        moved = []
        for item in items:
            item["fieldZone"] = "stalemate"
            item.pop("isSupport", None)
            item.pop("supportUntilTurn", None)
            if result.get("lockZone"):
                item["zoneLockTurn"] = self.phase_tracker["turn"]
            moved.append(item["id"])
        if result.get("lockSupportEntries"):
            self.rules_engine.setdefault("supportLocks", []).append({
                "turn": self.phase_tracker["turn"], "playerId": None,
            })
        self.prune_rules_ongoing_effects()
        return {
            "kind": result.get("kind"), "status": "stalemated" if moved else "nothing",
            "itemIds": moved, "locked": bool(result.get("lockZone")),
        }

    def _rules_result_destroy_random_interzone_target_player(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "player"
        ), None)
        target_id = (target or {}).get("playerId")
        candidates = [
            item for item in self.rules_confrontation_items(target_id, ("interzone",))
        ] if target_id in self.players else []
        if not candidates:
            return {"kind": result.get("kind"), "status": "nothing_to_destroy"}
        item = random.choice(candidates)
        movement = self._rules_remove_field_item_by_effect(
            item, item.get("ownerId"), "graveyard", "top", reason="destroy"
        )
        self.prune_rules_ongoing_effects()
        return {
            "kind": result.get("kind"), "status": movement.get("status"),
            "targetPlayerId": target_id, "cardId": item.get("cardId"),
            "itemId": item.get("id"),
        }

    def _rules_result_exile_target_on_win(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "card"
        ), None)
        item = self.find_battlefield_item((target or {}).get("itemId"))
        if item is None:
            return {"kind": result.get("kind"), "status": "target_missing"}
        self.create_rules_effect_memory(
            item["ownerId"], item["cardId"], "win_destination_exile",
            controller_id=player_id, source_action_id=action.get("id"),
            data={"itemId": item["id"]},
        )
        return {"kind": result.get("kind"), "status": "marked", "itemId": item["id"]}

    def _rules_result_destroy_source(self, action, result, player_id, player):
        source_item = self.find_battlefield_item(
            (action.get("source") or {}).get("itemId")
        )
        if source_item is None:
            return {
                "kind": "destroy_source",
                "status": "source_missing",
            }
        movement = self._rules_remove_field_item_by_effect(
            source_item, source_item.get("ownerId"), "graveyard", "top",
            reason="destroy",
        )
        self.prune_rules_ongoing_effects()
        return {
            "kind": "destroy_source",
            "status": movement.get("status"),
            "itemId": source_item.get("id"),
            "cardId": source_item.get("cardId"),
            "ownerId": source_item.get("ownerId"),
            "destination": "graveyard",
            **({
                "replacement": movement,
            } if movement.get("status") == "suspended" else {}),
        }

    def _rules_result_capture_stalemate_and_copy(self, action, result, player_id, player):
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
                "status": "target_missing",
            }
        card_id = item.get("cardId")
        movement = self._rules_remove_field_item_by_effect(
            item, player_id, "receptacle", "top"
        )
        copy = self.create_rules_token_copy(
            card_id, player_id,
            source_item_id=(action.get("source") or {}).get("itemId"),
        )
        triggered_actions = self.queue_rules_token_copy_entry_triggers(copy)
        return {
            "kind": result.get("kind"),
            "status": "resolved",
            "movement": movement,
            "copyItemId": copy["id"],
            "triggeredActions": triggered_actions,
        }

    def _rules_result_stalemate_unless_opponent_pays(self, action, result, player_id, player):
        controller_id = action.get("controllerId")
        opponent_id = self.other_rules_player_id(controller_id)
        first_ids = self.rules_engine.get("firstManifestationItemIds", {})
        powers = {}
        for pid in (controller_id, opponent_id):
            first = self.find_battlefield_item(first_ids.get(pid))
            if first is not None:
                powers[pid] = int(self.card_rules.get(first.get("cardId"), {}).get("power") or 0)
        if (
            controller_id not in powers or opponent_id not in powers
            or powers[controller_id] >= powers[opponent_id]
        ):
            return {"kind": result.get("kind"), "status": "condition_failed", "powers": powers}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "immediate_effect_payment", "playerId": opponent_id,
            "payment": result.get("payment"),
            "requirements": self.rules_requirements_from_symbols(result.get("payment")),
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "actionId": action.get("id"),
            "controllerId": controller_id,
            "stalemateOnDecline": True,
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "immediate_effect_payment", "playerId": opponent_id,
            "payment": result.get("payment"),
        }

    def _rules_result_destroy_matching_on_field(self, action, result, player_id, player):
        turn = self.phase_tracker["turn"]
        if result.get("match") == "entered_support_this_turn":
            matched_ids = {
                entry.get("itemId")
                for entry in self.rules_engine.get("supportEntries") or []
                if int(entry.get("turn") or 0) == turn
            }
        else:
            outcome = self.rules_engine.get("confrontationResult") or {}
            winner_id = (
                outcome.get("winnerId")
                if outcome.get("turn") == turn else None
            )
            matched_ids = {
                item_id for item_id in outcome.get("participantItemIds") or []
                if winner_id is not None
                and self.rules_item_controller_id(
                    self.find_battlefield_item(item_id)
                ) == winner_id
            }
        destroyed = []
        for item in list(self.battlefield):
            if item.get("id") not in matched_ids or not item.get("faceUp"):
                continue
            if (
                self.rules_item_card_rules(item).get("type")
                != "manifestation"
                and not item.get("isTokenCard")
            ):
                continue
            movement = self._rules_remove_field_item_by_effect(
                item, item.get("ownerId"), "graveyard", "top",
                reason="destroy",
            )
            if movement.get("status") in {"moved", "removed_copy", "suspended"}:
                destroyed.append(movement)
        return {
            "kind": "destroy_matching_on_field",
            "match": result.get("match"),
            "destroyed": destroyed,
        }

    def _rules_result_exile_source_take_control_to_interzone(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") in {"card", "zone_card"}
        ), None)
        source_item = self.find_battlefield_item(
            (action.get("source") or {}).get("itemId")
        )
        if target is None or source_item is None:
            return {"kind": result.get("kind"), "status": "target_missing"}
        if target.get("kind") == "zone_card" and (
            self.rules_interzone_slot_count(player_id)
            >= self.rules_interzone_capacity(player_id)
            and not self.rules_interzone_share_anchor(player_id, {
                "id": "incoming", "cardId": target.get("cardId"),
                "ownerId": target.get("ownerId"),
            })
        ):
            return {"kind": result.get("kind"), "status": "interzone_full"}
        if target.get("kind") == "card":
            taken = self.find_battlefield_item(target.get("itemId"))
            if (
                taken is None
                or self.rules_field_zone(taken) != "interzone"
                or self.rules_item_controller_id(taken) == player_id
                or self.rules_item_zone_locked(taken)
                or self.card_rules.get(taken.get("cardId"), {}).get("type") != "manifestation"
            ):
                return {"kind": result.get("kind"), "status": "target_missing"}
            if (
                self.rules_interzone_slot_count(player_id)
                >= self.rules_interzone_capacity(player_id)
                and not self.rules_interzone_share_anchor(player_id, taken)
            ):
                return {"kind": result.get("kind"), "status": "interzone_full"}
        exiled = self._rules_remove_field_item_by_effect(
            source_item, source_item.get("ownerId"), "exile", "top",
            reason="exile",
        )
        payload = {
            "kind": result.get("kind"), "status": "taken", "exiled": exiled,
            "cardId": target.get("cardId"),
        }
        if target.get("kind") == "zone_card":
            payload["movement"] = self.apply_rules_action_result({
                **action,
                "ability": {**(action.get("ability") or {}), "result": {
                    "kind": "move_zone_target_to_field_zone",
                    "fieldZone": "interzone",
                }},
            })
            return payload
        if self.rules_interzone_slot_count(player_id) >= self.rules_interzone_capacity(player_id):
            anchor = self.rules_interzone_share_anchor(player_id, taken)
            taken.update({
                "stackedOn": anchor, "stackOffsetX": 18.0, "stackOffsetY": 18.0,
            })
        else:
            taken["stackedOn"] = None
        taken["controllerId"] = player_id
        taken["fieldZone"] = "interzone"
        taken["isSupport"] = False
        self.mark_rules_interzone_entry(taken)
        self.prune_rules_ongoing_effects()
        payload["itemId"] = taken["id"]
        return payload

    def _rules_result_destroy_vessel_target_owner_sacrifices(self, action, result, player_id, player):
        destroyed = self.apply_rules_action_result({
            **action,
            "ability": {**(action.get("ability") or {}), "result": {
                "kind": "move_target", "zone": "graveyard",
                "position": "top", "reason": "destroy",
            }},
        })
        if not destroyed or destroyed.get("status") not in {"moved", "suspended"}:
            return {"kind": result.get("kind"), "status": "target_missing",
                    "destroyed": destroyed}
        sacrificer_id = destroyed.get("ownerId")
        candidates = [
            item["id"] for item in self.battlefield
            if self.rules_item_controller_id(item) == sacrificer_id
            and self.rules_item_card_rules(item).get("type") == "manifestation"
            and not self.rules_item_zone_locked(item)
        ]
        payload = {
            "kind": result.get("kind"), "status": "destroyed",
            "destroyed": destroyed, "sacrificerId": sacrificer_id,
        }
        if len(candidates) == 1:
            picked = self.find_battlefield_item(candidates[0])
            payload["sacrificed"] = self._rules_remove_field_item_by_effect(
                picked, picked.get("ownerId"), "graveyard", "top",
                reason="sacrifice",
            )
            self.prune_rules_ongoing_effects()
        elif candidates:
            choice = self.rules_next_pick_own_item_choice(
                [{"playerId": sacrificer_id, "candidateItemIds": candidates}],
                action.get("id"), (action.get("source") or {}).get("cardId"),
                [], purpose="sacrifice",
            )
            payload.update({
                "kind": "choice_required", "choiceId": choice["id"],
                "choiceKind": "pick_own_item", "playerId": sacrificer_id,
                "purpose": "sacrifice",
            })
        return payload
