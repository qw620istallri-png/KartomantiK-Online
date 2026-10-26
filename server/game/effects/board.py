"""Effect results that move cards between field zones, create tokens or change control."""

import random

from ..common import (
    RULES_SCORE_COUNTS, ADVANCED_PHASES, RULES_WILL_TYPES, RULES_TEMPERAMENTS, new_id
)


class BoardEffectsMixin:
    def _rules_result_create_essence(self, action, result, player_id, player):
        amount = int(result.get("value") or 0)
        if result.get("perCount") in RULES_SCORE_COUNTS:
            amount *= self.rules_score_count(
                result["perCount"], player_id, action
            )
        if amount <= 0:
            return {"kind": result.get("kind"), "status": "nothing", "amount": 0}
        temperament = result.get("temperament")
        source_item = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
        if temperament == "source_chosen":
            temperament = (source_item or {}).get("chosenTemperament")
            if temperament not in RULES_TEMPERAMENTS:
                return {"kind": result.get("kind"), "status": "no_temperament", "amount": 0}
        created = self.add_rules_excess_essence(player_id, [{
            "temperament": temperament,
            "amount": amount,
            "retained": bool(result.get("retained")),
        }])
        exiled = False
        counter_name = result.get("exileSourceIfNoCounter")
        if counter_name and source_item is not None:
            held = sum(
                int(v or 0) for k, v in (source_item.get("counters") or {}).items()
                if str(k).casefold() == str(counter_name).casefold()
            )
            if held <= 0:
                self._rules_remove_field_item_by_effect(
                    source_item, source_item.get("ownerId"), "exile", "top", reason="exile",
                )
                exiled = True
        return {
            "kind": result.get("kind"),
            "status": "created",
            "playerId": player_id,
            "temperament": temperament,
            "amount": amount,
            "tokens": created,
            **({"sourceExiled": True} if exiled else {}),
        }

    def _rules_result_move_zone_target_to_field_zone(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "zone_card"
        ), None)
        if target is None:
            return {
                "kind": result.get("kind"),
                "status": "target_missing",
            }
        container_id = target.get("containerId")
        zone = target.get("zone")
        card_id = target.get("cardId")
        owner_id = self.card_owner_in_zone(
            container_id, zone, card_id
        )
        if owner_id is None:
            return {
                "kind": result.get("kind"),
                "status": "target_missing",
            }
        seat = self.players[player_id].get("seat")
        item = {
            "id": new_id(), "ownerId": owner_id,
            "controllerId": player_id, "cardId": card_id,
            "x": 740.0, "y": 800.0 if seat != 1 else 525.0,
            "faceUp": True, "rotation": 0.0, "counters": {},
            "stackedOn": None,
        }
        field_zone = result.get("fieldZone")
        if field_zone == "interzone":
            if self.rules_interzone_slot_count(player_id) >= self.rules_interzone_capacity(player_id):
                anchor = self.rules_interzone_share_anchor(
                    player_id, item
                )
                if not anchor:
                    return {
                        "kind": result.get("kind"),
                        "status": "interzone_full",
                    }
                item.update({
                    "stackedOn": anchor,
                    "stackOffsetX": 18.0,
                    "stackOffsetY": 18.0,
                })
            item["fieldZone"] = "interzone"
            self.mark_rules_interzone_entry(item)
        elif result.get("asSupport"):
            self.mark_rules_support_entry(item)
        elif field_zone == "confrontation":
            self.mark_rules_confrontation_entry(item)
        else:
            item["fieldZone"] = field_zone
        self.take_zone_card(container_id, zone, card_id)
        self.battlefield.append(item)
        triggered = self.queue_rules_battlefield_entry_triggers(
            card_id, owner_id, item["id"], True, defer=True,
        )
        triggered.extend(self.queue_rules_manifestation_entry_watchers(
            item, defer=True, played=False,
        ))
        triggered.extend(self.queue_rules_persistent_will_entry_watchers(
            item, defer=True,
        ))
        triggered.extend(self.queue_rules_field_zone_entry_triggers(
            item, self.rules_field_zone(item), defer=True,
        ))
        if item.get("isSupport"):
            triggered.extend(self.queue_rules_support_entry_triggers(
                item, played=False, from_zone=zone, defer=True,
            ))
        self.queue_or_defer_rules_simultaneous_actions(triggered)
        return {
            "kind": result.get("kind"),
            "status": "moved",
            "itemId": item["id"],
            "cardId": card_id,
            "ownerId": owner_id,
            "controllerId": player_id,
            "fieldZone": item.get("fieldZone"),
        }

    def _rules_result_move_target_to_own_vessel(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "card"
        ), None)
        item = self.find_battlefield_item((target or {}).get("itemId"))
        if item is None or item.get("ownerId") == player_id:
            return {"kind": result.get("kind"), "status": "target_missing"}
        if (
            self.rules_item_card_rules(item).get("adamant")
            and self.rules_item_effects_active(item)
            and self.rules_item_controller_id(item) != player_id
        ):
            return {"kind": result.get("kind"), "status": "prevented_adamant",
                    "cardId": item.get("cardId"), "itemId": item.get("id")}
        movement = self._rules_remove_field_item(item, player_id, "receptacle")
        self.prune_rules_ongoing_effects()
        return {"kind": result.get("kind"), "status": movement.get("status"),
                "cardId": item.get("cardId"), "itemId": item.get("id"),
                "containerId": player_id, "zone": "receptacle"}

    def _rules_result_consult_support(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "player"
        ), None)
        target_id = (target or {}).get("playerId")
        if target_id not in self.players:
            return {"kind": result.get("kind"), "status": "target_missing"}
        deck = self.players[target_id]["zones"]["deck"]
        discarded, found = [], None
        while deck:
            top_card = deck[0]
            if self.card_rules.get(top_card, {}).get("type") == "manifestation":
                found = top_card
                break
            error, _owner, replacement = self.move_zone_card_by_effect(
                target_id, "deck", target_id, "graveyard", top_card, "top"
            )
            if error:
                break
            if not replacement:
                discarded.append(top_card)
        if found is None:
            return {
                "kind": result.get("kind"), "status": "no_manifestation",
                "discarded": discarded,
            }
        if self.rules_support_entry_locked(target_id, put=True):
            return {"kind": result.get("kind"), "status": "prevented", "discarded": discarded}
        owner_id = self.take_zone_card(target_id, "deck", found)
        seat = self.players[target_id].get("seat")
        item = {
            "id": new_id(), "ownerId": owner_id, "controllerId": target_id,
            "cardId": found, "x": 740.0, "y": 800.0 if seat != 1 else 525.0,
            "faceUp": True, "rotation": 0.0, "counters": {}, "stackedOn": None,
        }
        self.mark_rules_support_entry(item)
        self.battlefield.append(item)
        self.queue_rules_effect_support_entry(item, "deck")
        return {
            "kind": result.get("kind"), "status": "support",
            "cardId": found, "itemId": item["id"],
            "controllerId": target_id, "discarded": discarded,
        }

    def _rules_result_first_manifestations_to_interzone_tokens(self, action, result, player_id, player):
        counts = {}
        for pid in self.players:
            first = self.find_battlefield_item(
                self.rules_engine.get("firstManifestationItemIds", {}).get(pid)
            )
            if (
                first is None
                or self.rules_item_controller_id(first) != pid
                or self.rules_field_zone(first) != "confrontation"
            ):
                continue
            base = self.rules_manifestation_base_power(first)
            if self.rules_interzone_slot_count(pid) >= self.rules_interzone_capacity(pid):
                anchor = self.rules_interzone_share_anchor(pid, first)
                if anchor:
                    first.update({
                        "stackedOn": anchor, "stackOffsetX": 18.0,
                        "stackOffsetY": 18.0,
                    })
                else:
                    first["stackedOn"] = None
            else:
                first["stackedOn"] = None
            first["fieldZone"] = "interzone"
            first["isSupport"] = False
            self.mark_rules_interzone_entry(first)
            counts[pid] = max(0, base)
        source = action.get("source") or {}
        created = {}
        for pid, count in counts.items():
            copies = [
                self.create_rules_token_copy(
                    source.get("cardId"), pid,
                    source_item_id=source.get("itemId"),
                    hollow=True, effects_disabled=True, generic_power=1,
                )
                for _index in range(count)
            ]
            created[pid] = [copy["id"] for copy in copies if copy is not None]
        return {
            "kind": result.get("kind"),
            "status": "resolved" if counts else "nothing",
            "tokens": {pid: len(ids) for pid, ids in created.items()},
        }

    def _rules_result_interzone_target_to_support(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "card"
        ), None)
        item = self.find_battlefield_item((target or {}).get("itemId"))
        if item is None or self.rules_field_zone(item) != "interzone":
            return {"kind": result.get("kind"), "status": "target_missing"}
        if self.rules_support_entry_locked(self.rules_item_controller_id(item), put=True):
            return {"kind": result.get("kind"), "status": "prevented"}
        item["stackedOn"] = None
        self.mark_rules_support_entry(item)
        self.queue_rules_effect_support_entry(item, "interzone", enters_field=False)
        return {
            "kind": result.get("kind"), "status": "support",
            "itemId": item["id"], "cardId": item.get("cardId"),
        }

    def _rules_result_gummo_copy_vessel(self, action, result, player_id, player):
        host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
        vessel = [
            c for c in player["zones"]["receptacle"]
            if self.card_rules.get(c, {}).get("type") == "manifestation"
        ]
        if host is None or not vessel:
            return {"kind": result.get("kind"), "status": "no_vessel_card"}
        if not action.get("optionalAccepted"):
            return {"kind": result.get("kind"), "status": "declined"}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "reveal_hand_discard", "purpose": "gummo",
            "playerId": player_id, "targetPlayerId": player_id,
            "cardIds": list(dict.fromkeys(vessel)), "sourceItemId": host["id"],
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "actionId": action.get("id"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "reveal_hand_discard", "playerId": player_id,
        }

    def _rules_result_interzone_becomes_first_manifestation(self, action, result, player_id, player):
        host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
        if host is None or self.rules_field_zone(host) != "interzone":
            return {"kind": result.get("kind"), "status": "target_missing"}
        if not self.rules_item_becomes_first_manifestation(host, player_id):
            return {"kind": result.get("kind"), "status": "target_missing"}
        return {
            "kind": result.get("kind"), "status": "first_manifestation",
            "itemId": host["id"], "cardId": host.get("cardId"),
        }

    def _rules_result_field_becomes_first_manifestation(self, action, result, player_id, player):
        # Juggernut: the Will on the field enters the Confrontation Zone as First Manifestation.
        host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
        if host is None or self.rules_field_zone(host) != "field":
            return {"kind": result.get("kind"), "status": "target_missing"}
        if not self.rules_item_becomes_first_manifestation(host, player_id):
            return {"kind": result.get("kind"), "status": "no_first_slot"}
        return {
            "kind": result.get("kind"), "status": "first_manifestation",
            "itemId": host["id"], "cardId": host.get("cardId"),
        }

    def _rules_result_source_to_winner_vessel(self, action, result, player_id, player):
        host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
        winner_id = (self.rules_engine.get("confrontationResult") or {}).get("winnerId")
        if host is None or winner_id not in self.players:
            return {"kind": result.get("kind"), "status": "target_missing"}
        movement = self._rules_remove_field_item_by_effect(
            host, winner_id, "receptacle", "top", reason="vessel",
        )
        return {"kind": result.get("kind"), "status": "taken", "movement": movement,
                "winnerId": winner_id}

    def _rules_result_wish_exchange(self, action, result, player_id, player):
        target = next((e for e in action.get("targets") or [] if e.get("kind") == "zone_card"), None)
        mine_id = (target or {}).get("cardId")
        vessel = player["zones"]["receptacle"]
        if mine_id not in vessel:
            return {"kind": result.get("kind"), "status": "target_missing"}
        points_of = lambda card: int((self.card_points or {}).get(card, 0) or 0)
        owner_id = self.card_owner_in_zone(player_id, "receptacle", mine_id)
        if owner_id not in self.players:
            return {"kind": result.get("kind"), "status": "target_missing"}
        candidates = [
            card_id for card_id in self.players[owner_id]["zones"]["receptacle"]
            if self.card_owner_in_zone(owner_id, "receptacle", card_id) == player_id
            and self.card_rules.get(card_id, {}).get("type") == "manifestation"
            and points_of(card_id) >= points_of(mine_id)
            and not (owner_id == player_id and card_id == mine_id)
        ]
        if not candidates:
            return {"kind": result.get("kind"), "status": "owner_cannot"}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "reveal_hand_discard", "purpose": "wish",
            "playerId": owner_id, "targetPlayerId": owner_id, "cardIds": candidates,
            "casterId": player_id, "chosenCardId": mine_id,
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "actionId": action.get("id"), "controllerId": action.get("controllerId"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "reveal_hand_discard", "playerId": owner_id,
        }

    def _rules_result_chabak_support(self, action, result, player_id, player):
        source = action.get("source") or {}
        hand = player["zones"]["hand"]
        others = list(hand)
        if source.get("cardId") in others:
            others.remove(source["cardId"])
        if (
            source.get("cardId") not in hand
            or sum(1 for c in others if self.card_rules.get(c, {}).get("type") == "manifestation") < 2
        ):
            return {"kind": result.get("kind"), "status": "source_missing"}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "discard_from_hand",
            "playerId": player_id, "count": 2, "requireManifestation": True,
            "destination": "stalemate_for_support",
            "sourceCardId": source.get("cardId"),
            "actionId": action.get("id"),
            "controllerId": action.get("controllerId"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "discard_from_hand", "playerId": player_id, "count": 2,
        }

    def _rules_result_ycar_exchange(self, action, result, player_id, player):
        opponents = [pid for pid in self.players if pid != player_id]
        target = next((
            entry for entry in action.get("targets") or [] if entry.get("kind") == "card"
        ), None)
        item = self.find_battlefield_item((target or {}).get("itemId"))
        if (
            not opponents or item is None or self.rules_field_zone(item) != "interzone"
            or item.get("ownerId") in opponents
        ):
            return {"kind": result.get("kind"), "status": "target_missing"}
        opponent_id = opponents[0]
        movement = self._rules_remove_field_item_by_effect(
            item, opponent_id, "receptacle", "top", reason="vessel",
        )
        if movement.get("status") != "moved":
            return {"kind": result.get("kind"), "status": movement.get("status")}
        candidates = sorted(
            card_id for card_id in player["zones"]["deck"]
            if self.card_rules.get(card_id, {}).get("type") == "manifestation"
        )
        if not candidates:
            random.shuffle(player["zones"]["deck"])
            return {"kind": result.get("kind"), "status": "no_cards", "movement": movement}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "discard_from_hand",
            "playerId": player_id, "count": 1, "upTo": False,
            "candidateCardIds": candidates, "destination": "interzone_from_search",
            "actionId": action.get("id"),
            "controllerId": action.get("controllerId"),
            "sourceCardId": (action.get("source") or {}).get("cardId"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "discard_from_hand", "playerId": player_id,
            "count": 1, "search": True,
        }

    def _rules_result_grant_support_entry_bonus(self, action, result, player_id, player):
        turn = self.phase_tracker["turn"]
        if result.get("requireLostPrevious") and (
            (self.rules_engine.get("confrontationLosses") or {}).get(str(turn - 1)) != player_id
        ):
            return {"kind": result.get("kind"), "status": "condition_failed"}
        self.rules_engine.setdefault("supportEntryBonuses", []).append({
            "turn": turn, "playerId": player_id, "value": int(result.get("value") or 1),
            "sourceCardId": (action.get("source") or {}).get("cardId"),
        })
        return {"kind": result.get("kind"), "status": "armed", "value": int(result.get("value") or 1)}

    def _rules_result_lock_support_entries(self, action, result, player_id, player):
        self.rules_engine.setdefault("supportLocks", []).append({
            "turn": self.phase_tracker["turn"],
            "playerId": player_id if result.get("scope") == "controller" else None,
            "playOnly": bool(result.get("playOnly")),
        })
        return {"kind": result.get("kind"), "status": "locked", "scope": result.get("scope")}

    def _rules_result_move_zone_target_to_own_vessel(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "zone_card"
        ), None)
        container_id = (target or {}).get("containerId")
        zone = (target or {}).get("zone")
        card_id = (target or {}).get("cardId")
        owner_id = self.card_owner_in_zone(container_id, zone, card_id)
        if owner_id is None or owner_id == player_id:
            return {"kind": result.get("kind"), "status": "target_missing"}
        self.take_zone_card(container_id, zone, card_id)
        self.put_zone_card(player_id, "receptacle", card_id, owner_id)
        self.record_rules_observed_event(
            "manifestation_enters_opponent_vessel", owner_id
        )
        return {
            "kind": result.get("kind"), "status": "moved",
            "cardId": card_id, "ownerId": owner_id,
            "containerId": player_id, "zone": "receptacle",
        }

    def _rules_result_return_target_player_support(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "player"
        ), None)
        target_id = (target or {}).get("playerId")
        if target_id not in self.players:
            return {"kind": result.get("kind"), "status": "target_missing"}
        support_mode = result.get("kind") == "return_target_player_support"
        moved, prevented = [], []
        returned_by_owner = {}
        for item in list(self.battlefield):
            if (
                self.rules_item_controller_id(item) != target_id
                or self.rules_item_card_rules(item).get("type") != "manifestation"
            ):
                continue
            if support_mode:
                if not item.get("isSupport") or self.rules_field_zone(item) != "confrontation":
                    continue
            elif self.rules_field_zone(item) != "interzone":
                continue
            if (
                self.rules_item_card_rules(item).get("adamant")
                and self.rules_item_effects_active(item)
                and target_id != player_id
            ):
                prevented.append(item["id"])
                continue
            movement = self._rules_remove_field_item_by_effect(
                item, item.get("ownerId"),
                "hand" if support_mode else "deck", "top", reason="return",
            )
            if movement.get("status") != "moved":
                continue
            moved.append(item["id"])
            if not support_mode:
                returned_by_owner.setdefault(item["ownerId"], []).append(item["cardId"])
            if support_mode:
                self.rules_engine["playRestrictions"].append({
                    "id": new_id(), "playerId": item["ownerId"],
                    "cardId": item["cardId"], "turn": self.phase_tracker["turn"],
                    "sourceActionId": action.get("id"),
                })
        self.prune_rules_ongoing_effects()
        payload = {
            "kind": result.get("kind"), "status": "moved",
            "targetPlayerId": target_id, "itemIds": moved,
            "preventedItemIds": prevented,
        }
        order_queue = [
            {"playerId": owner_id, "cardIds": list(reversed(card_ids))}
            for owner_id, card_ids in returned_by_owner.items()
            if len(card_ids) > 1
        ]
        if order_queue:
            choice = self.rules_next_deck_order_choice(
                order_queue, (action.get("source") or {}).get("cardId")
            )
            payload.update({
                "kind": "choice_required", "choiceId": choice["id"],
                "choiceKind": "deck_reorder", "playerId": choice["playerId"],
                "returned": moved,
            })
        return payload

    def _rules_result_create_target_token_copy_in_support(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "card"
        ), None)
        item = self.find_battlefield_item(
            (target or {}).get("itemId")
        )
        if item is None:
            return {
                "kind": result.get("kind"),
                "status": "target_missing",
            }
        copy = self.create_rules_token_copy(
            item.get("cardId"), player_id,
            source_item_id=(action.get("source") or {}).get("itemId"),
        )
        if copy is None:
            return {"kind": result.get("kind"), "status": "entry_blocked"}
        triggered_actions = self.queue_rules_token_copy_entry_triggers(copy)
        return {
            "kind": result.get("kind"),
            "status": "created",
            "targetItemId": item.get("id"),
            "createdItemId": copy["id"],
            "triggeredActions": triggered_actions,
        }

    def _rules_result_grant_friendly_interzone_support_until_end_turn(self, action, result, player_id, player):
        item_ids = []
        for item in self.rules_confrontation_items(
            player_id, ("interzone",)
        ):
            item["supportUntilTurn"] = self.phase_tracker["turn"]
            item_ids.append(item["id"])
        return {
            "kind": result.get("kind"),
            "status": "granted",
            "itemIds": item_ids,
        }

    def _rules_result_create_support_tokens_from_optional_extra_essence(self, action, result, player_id, player):
        count = max(
            0, int(
                (action.get("cost") or {}).get(
                    "optionalExtraEssenceSpent"
                ) or 0
            )
        )
        tokens = [
            self.create_rules_token_copy(
                None, player_id,
                source_item_id=(
                    action.get("sourceResolution") or {}
                ).get("itemId"),
                hollow=True,
                effects_disabled=True,
                generic_power=1,
            )
            for _index in range(count)
        ]
        tokens = [token for token in tokens if token is not None]
        return {
            "kind": result.get("kind"),
            "status": "created",
            "count": len(tokens),
            "itemIds": [item["id"] for item in tokens],
        }

    def _rules_result_create_support_token(self, action, result, player_id, player):
        token = self.create_rules_token_copy(
            None, player_id,
            source_item_id=(action.get("source") or {}).get("itemId"),
            generic_power=result.get("power"),
            generic_temperament=result.get("temperament"),
        )
        if token is None:
            return {"kind": result.get("kind"), "status": "entry_blocked"}
        return {
            "kind": result.get("kind"),
            "status": "created",
            "createdItemId": token["id"],
            "power": token["power"],
            "temperament": token["temperament"],
        }

    def _rules_result_protect_related_will(self, action, result, player_id, player):
        trigger = (action.get("ability") or {}).get("trigger") or {}
        related = next((
            entry for entry in self.rules_engine.get("actionStack") or []
            if entry.get("id") == trigger.get("relatedActionId")
            and entry.get("kind") == "play_card"
            and (entry.get("source") or {}).get("zone") == "hand"
            and self.card_rules.get(
                (entry.get("source") or {}).get("cardId"), {}
            ).get("type") in RULES_WILL_TYPES
        ), None)
        if related is None:
            return {"kind": result.get("kind"), "status": "related_action_not_hand_will"}
        related["cannotBeNeutralized"] = True
        related_source = related.get("source") or {}
        if self.card_rules.get(related_source.get("cardId"), {}).get("type") == "persistent_will":
            self.append_rules_ongoing_effect({
                "id": new_id(), "actionId": action.get("id"),
                "abilityId": (action.get("ability") or {}).get("id"),
                "controllerId": related.get("controllerId"),
                "source": {"cardId": (action.get("source") or {}).get("cardId")},
                "target": {
                    "kind": "stack_action", "actionId": related.get("id"),
                    "cardId": related_source.get("cardId"),
                    "ownerId": related_source.get("ownerId"),
                },
                "kind": "protection", "fromOpponents": True,
                "duration": "until_end_of_turn",
                "startedTurn": self.phase_tracker["turn"],
            })
        return {
            "kind": result.get("kind"), "status": "protected",
            "actionId": related.get("id"),
            "cardId": related_source.get("cardId"),
        }

    def _rules_result_grant_source_support_until_end_turn(self, action, result, player_id, player):
        source = action.get("source") or {}
        source_item = self.find_battlefield_item(source.get("itemId"))
        if source_item is not None:
            source_item["supportUntilTurn"] = self.phase_tracker["turn"]
            return {
                "kind": result.get("kind"),
                "status": "granted",
                "itemId": source_item.get("id"),
                "cardId": source_item.get("cardId"),
                "zone": self.rules_field_zone(source_item),
            }
        if (
            source.get("zone") == "hand"
            and source.get("cardId")
            in self.players[player_id]["zones"]["hand"]
        ):
            permission = {
                "id": new_id(),
                "abilityId": (action.get("ability") or {}).get("id"),
                "playerId": player_id,
                "cardId": source.get("cardId"),
                "fromZone": "hand",
                "phaseIds": ["confrontation_reaction"],
                "asSupport": True,
                "turn": self.phase_tracker["turn"],
            }
            self.rules_engine["playPermissions"].append(permission)
            if (action.get("ability") or {}).get("id") == "timid-brain-discard-will-for-support":
                # Timid Brain says "Play", not "gains Support". The temporary
                # permission is used only by this normal, responseable card play.
                previous_priority = self.rules_engine.get("priorityPlayerId")
                self.rules_engine["priorityPlayerId"] = player_id
                played = None
                try:
                    error, played = self.declare_rules_action(
                        player_id, self.card_labels.get(source["cardId"], source["cardId"]),
                        kind="play_card", source={"cardId": source["cardId"], "zone": "hand"},
                        as_support=True, placement=action.get("placement"), internal=True,
                    )
                finally:
                    self.rules_engine["playPermissions"] = [
                        entry for entry in self.rules_engine["playPermissions"]
                        if entry.get("id") != permission["id"]
                    ]
                    if played is None:
                        self.rules_engine["priorityPlayerId"] = previous_priority
                if error:
                    return {"kind": result.get("kind"), "status": "prevented", "error": error}
                return {
                    "kind": result.get("kind"), "status": "played",
                    "cardId": source["cardId"], "actionId": played["id"],
                }
            return {
                "kind": result.get("kind"),
                "status": "granted",
                "permissionId": permission["id"],
                "cardId": source.get("cardId"),
                "zone": "hand",
            }
        return {
            "kind": result.get("kind"),
            "status": "source_missing",
        }

    def _rules_result_grant_source_support_if_base_higher_than_own_first(self, action, result, player_id, player):
        source_item = self.find_battlefield_item(
            (action.get("source") or {}).get("itemId")
        )
        if source_item is None:
            return {
                "kind": result.get("kind"),
                "status": "source_missing",
            }
        controller_id = self.rules_item_controller_id(source_item)
        first_item = self.find_battlefield_item(
            (self.rules_engine.get("firstManifestationItemIds") or {}).get(
                controller_id
            )
        )
        source_base = self.rules_manifestation_base_power(source_item)
        first_base = self.rules_manifestation_base_power(first_item)
        granted = first_item is not None and source_base > first_base
        if granted:
            source_item["supportUntilTurn"] = self.phase_tracker["turn"]
        return {
            "kind": result.get("kind"),
            "status": "granted" if granted else "condition_failed",
            "itemId": source_item.get("id"),
            "sourceBasePower": source_base,
            "firstBasePower": first_base if first_item is not None else None,
        }

    def _rules_result_play_vessel_target_as_support(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "zone_card"
        ), None)
        container_id = (target or {}).get("containerId")
        card_id = (target or {}).get("cardId")
        owner_id = (
            self.card_owner_in_zone(container_id, "receptacle", card_id)
            if container_id in self.players else None
        )
        if owner_id is None:
            return {"kind": result.get("kind"), "status": "target_missing"}
        if self.rules_support_entry_locked(player_id, put=True):
            return {"kind": result.get("kind"), "status": "prevented"}
        self.take_zone_card(container_id, "receptacle", card_id)
        seat = self.players[player_id].get("seat")
        item = {
            "id": new_id(), "ownerId": owner_id,
            "controllerId": player_id, "cardId": card_id,
            "x": 740.0, "y": 800.0 if seat != 1 else 525.0,
            "faceUp": True, "rotation": 0.0, "counters": {},
            "stackedOn": None,
            "supportReturn": {"controllerId": player_id},
        }
        self.mark_rules_support_entry(item)
        self.battlefield.append(item)
        self.queue_rules_effect_support_entry(item, "receptacle")
        return {
            "kind": result.get("kind"), "status": "moved",
            "itemId": item["id"], "cardId": card_id,
            "ownerId": owner_id, "controllerId": player_id,
        }

    def _rules_result_change_source_control(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "player"
        ), None)
        controller_id = target.get("playerId") if target else None
        source_item_id = (
            (action.get("sourceResolution") or {}).get("itemId")
            or (action.get("source") or {}).get("itemId")
        )
        source_item = self.find_battlefield_item(source_item_id)
        if source_item is None:
            return {
                "kind": "change_source_control",
                "status": "source_missing",
            }
        if controller_id not in self.players:
            controller_id = self.rules_item_controller_id(source_item)
        previous_controller_id = self.rules_item_controller_id(source_item)
        source_item["controllerId"] = controller_id
        if result.get("counter"):
            counters = source_item.setdefault("counters", {})
            current = int(counters.get(result["counter"]) or 0)
            counters[result["counter"]] = (
                current + int(result.get("counterValue") or 0)
                if result.get("incrementCounter")
                else int(result.get("counterValue") or 0)
            )
        return {
            "kind": "change_source_control",
            "status": "changed",
            "itemId": source_item["id"],
            "cardId": source_item.get("cardId"),
            "ownerId": source_item.get("ownerId"),
            "previousControllerId": previous_controller_id,
            "controllerId": controller_id,
            "counter": result.get("counter"),
            "counterValue": result.get("counterValue"),
        }

    def _rules_result_create_tokens_for_target_interzone_count(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "player"
        ), None)
        target_id = target.get("playerId") if target else None
        if target_id not in self.players:
            return {
                "kind": result.get("kind"),
                "status": "target_missing",
            }
        count = len(self.rules_confrontation_items(
            target_id, ("interzone",)
        ))
        source_item_id = (action.get("source") or {}).get("itemId")
        created = [
            self.create_rules_token_copy(
                (action.get("source") or {}).get("cardId"),
                player_id,
                source_item_id=source_item_id,
                hollow=True,
                effects_disabled=True,
                generic_power=1,
            )
            for _index in range(count)
        ]
        created = [item for item in created if item is not None]
        return {
            "kind": result.get("kind"),
            "status": "created",
            "count": len(created),
            "itemIds": [item["id"] for item in created],
            "targetPlayerId": target_id,
        }

    def _rules_result_copy_related_tribute_if_exhaust(self, action, result, player_id, player):
        source_item = self.find_battlefield_item(
            (action.get("source") or {}).get("itemId")
        )
        related_card_id = (
            (action.get("ability") or {}).get("trigger") or {}
        ).get("relatedCardId")
        if (
            source_item is None
            or int(round(float(source_item.get("rotation") or 0))) % 180
            or self.card_rules.get(related_card_id, {}).get("type")
            != "manifestation"
        ):
            return {
                "kind": result.get("kind"),
                "status": "unavailable",
            }
        if action.get("optionalAccepted"):
            source_item["rotation"] = 90.0
            copy = self.create_rules_token_copy(
                related_card_id, player_id,
                source_item_id=source_item.get("id"),
            )
            if copy is None:
                return {"kind": result.get("kind"), "status": "entry_blocked"}
            triggered_actions = self.queue_rules_token_copy_entry_triggers(copy)
            return {
                "kind": result.get("kind"),
                "status": "accepted",
                "playerId": player_id,
                "relatedCardId": related_card_id,
                "createdItemId": copy["id"],
                "triggeredActions": triggered_actions,
            }
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id,
            "kind": "optional_trigger",
            "playerId": player_id,
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "options": ["accept", "decline"],
            "_effect": "copy_related_tribute_if_exhaust",
            "_sourceItemId": source_item["id"],
            "_relatedCardId": related_card_id,
        }
        return {
            "kind": "choice_required",
            "choiceId": choice_id,
            "choiceKind": "optional_trigger",
            "playerId": player_id,
        }

    def _rules_result_copy_entering_persistent_will_for_others(self, action, result, player_id, player):
        trigger = (action.get("ability") or {}).get("trigger") or {}
        card_id = trigger.get("relatedCardId")
        event_controller_id = trigger.get("eventControllerId")
        if (
            self.card_rules.get(card_id, {}).get("type") != "persistent_will"
            or event_controller_id not in self.players
        ):
            return {
                "kind": result.get("kind"),
                "status": "event_missing",
            }
        created = [
            self.create_rules_token_copy(
                card_id, current_id,
                source_item_id=(action.get("source") or {}).get("itemId"),
            )
            for current_id in self.players
            if current_id != event_controller_id
        ]
        created = [item for item in created if item is not None]
        triggered_actions = []
        for created_item in created:
            triggered_actions.extend(
                self.queue_rules_token_copy_entry_triggers(created_item)
            )
        return {
            "kind": result.get("kind"),
            "status": "created",
            "createdItemIds": [item["id"] for item in created],
            "triggeredActions": triggered_actions,
        }

    def _rules_result_take_last_opponent_support_to_vessel(self, action, result, player_id, player):
        item = self.rules_last_opponent_support(player_id, 2)
        if item is None:
            return {"kind": result.get("kind"), "status": "target_missing"}
        if item.get("ownerId") == player_id:
            return {"kind": result.get("kind"), "status": "own_card"}
        movement = self._rules_remove_field_item_by_effect(item, player_id, "receptacle", "top", reason="vessel")
        return {"kind": result.get("kind"), "status": "taken", "movement": movement}

    def _rules_result_grant_free_will_play(self, action, result, player_id, player):
        owner_id = (action.get("source") or {}).get("ownerId") or player_id
        if owner_id not in self.players:
            return {"kind": result.get("kind"), "status": "target_missing"}
        self.rules_engine["playPermissions"].append({
            "id": new_id(), "abilityId": (action.get("ability") or {}).get("id"),
            "playerId": owner_id, "anyWill": True, "fromZone": "hand",
            "phaseIds": list(ADVANCED_PHASES), "asSupport": False,
            "noTribute": True, "turn": self.phase_tracker["turn"],
            "sourceCardId": (action.get("source") or {}).get("cardId"),
        })
        return {"kind": result.get("kind"), "status": "granted", "playerId": owner_id}

    def _rules_result_will_becomes_support_manifestation(self, action, result, player_id, player):
        from_hand = result.get("kind") == "put_hand_will_as_support_manifestation"
        if self.rules_support_entry_locked(player_id, put=True):
            return {"kind": result.get("kind"), "status": "prevented"}
        if from_hand:
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "zone_card"
            ), None)
            card_id = (target or {}).get("cardId")
            owner_id = self.card_owner_in_zone(player_id, "hand", card_id) if card_id else None
            if (
                owner_id is None
                or self.card_rules.get(card_id, {}).get("type") not in RULES_WILL_TYPES
                or not self.take_zone_card(player_id, "hand", card_id)
            ):
                return {"kind": result.get("kind"), "status": "target_missing"}
            seat = self.players[player_id].get("seat")
            item = {
                "id": new_id(), "ownerId": owner_id,
                "controllerId": player_id, "cardId": card_id,
                "x": 740.0, "y": 800.0 if seat != 1 else 525.0,
                "faceUp": True, "rotation": 0.0, "counters": {},
                "stackedOn": None,
                # Put onto the field, not played: its own effects stay off.
                "effectsDisabled": True,
            }
            self.battlefield.append(item)
            outcomes = {"onWin": "free_play", "onLoss": "exile", "onStalemate": "exile"}
        else:
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "card"
            ), None)
            item = self.find_battlefield_item((target or {}).get("itemId"))
            if (
                item is None
                or self.rules_item_card_rules(item).get("type") != "persistent_will"
                or self.rules_item_controller_id(item) != player_id
                or self.rules_field_zone(item) != "field"
                or item.get("willManifestation")
            ):
                return {"kind": result.get("kind"), "status": "target_missing"}
            outcomes = {"onWin": "revert", "onLoss": "destroy", "onStalemate": "revert"}
        will_cost = self.rules_will_tribute_cost(item.get("cardId"))
        item["willManifestation"] = {
            "power": will_cost, "turn": self.phase_tracker["turn"], **outcomes,
        }
        item["controllerId"] = player_id
        item["stackedOn"] = None
        self.mark_rules_support_entry(item)
        triggered = self.queue_rules_support_entry_triggers(
            item, played=False, from_zone="hand" if from_hand else "field", defer=True,
        )
        triggered.extend(self.queue_rules_field_zone_entry_triggers(
            item, "confrontation", defer=True,
        ))
        if triggered:
            self.queue_rules_simultaneous_actions(triggered)
        return {
            "kind": result.get("kind"), "status": "moved",
            "itemId": item["id"], "cardId": item.get("cardId"), "power": will_cost,
        }

    def _rules_result_free_concealed_wills(self, action, result, player_id, player):
        source_id = (action.get("source") or {}).get("itemId")
        freed = []
        for item in self.battlefield:
            if item.get("concealedWill") and item.get("jigonItemId") == source_id:
                item["concealedFree"] = True
                freed.append(item["id"])
        return {"kind": result.get("kind"), "status": "freed", "itemIds": freed}

    def _rules_result_move_targets(self, action, result, player_id, player):
        movements = []
        for target in action.get("targets") or []:
            nested = {
                **action,
                "targets": [target],
                "ability": {
                    **(action.get("ability") or {}),
                    "result": {
                        "kind": "move_target",
                        "zone": result.get("zone"),
                        "position": result.get("position"),
                        "reason": result.get("reason"),
                    },
                },
            }
            movement = self.apply_rules_action_result(nested)
            if movement:
                movements.append(movement)
        return {
            "kind": "move_targets",
            "status": "resolved",
            "movements": movements,
        }

    def _rules_result_end_confrontation_relocate_all(self, action, result, player_id, player):
        source_item = self.find_battlefield_item(
            (action.get("source") or {}).get("itemId")
        )
        if source_item is None:
            return {
                "kind": result.get("kind"),
                "status": "source_missing",
            }
        source_movement = self._rules_remove_field_item_by_effect(
            source_item, source_item.get("ownerId"), "exile", "top"
        )
        groups = []
        for owner_id in self.players:
            item_ids = [
                item["id"] for item in self.rules_confrontation_items()
                if item.get("ownerId") == owner_id
            ]
            if not item_ids:
                continue
            groups.append({
                "playerId": owner_id,
                "itemIds": item_ids,
                "interzoneSlots": max(
                    0, 3 - self.rules_interzone_slot_count(owner_id)
                ),
            })
        if not groups:
            self.phase_tracker["index"] = ADVANCED_PHASES.index(
                "end_actions"
            )
            opponent_id = self.other_rules_player_id(player_id)
            if opponent_id:
                self.adjust_rules_score(opponent_id, 50)
            return {
                "kind": result.get("kind"),
                "status": "ended",
                "sourceMovement": source_movement,
            }
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id,
            "kind": "confrontation_relocation",
            "playerId": player_id,
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "groups": groups,
            "_groups": groups,
            "_sourceMovement": source_movement,
        }
        return {
            "kind": "choice_required",
            "choiceId": choice_id,
            "choiceKind": "confrontation_relocation",
            "playerId": player_id,
        }

    def _rules_result_end_confrontation_unless_payment(self, action, result, player_id, player):
        opponent_id = self.other_rules_player_id(player_id)
        choice_id = new_id()
        controller_base_power = sum(
            self.rules_manifestation_base_power(item)
            for item in self.rules_confrontation_items(player_id)
        )
        self.rules_engine["pendingChoice"] = {
            "id": choice_id,
            "kind": "immediate_effect_payment",
            "playerId": opponent_id,
            "payment": result.get("payment"),
            "requirements": self.rules_requirements_from_symbols(
                result.get("payment")
            ),
            "actionId": action.get("id"),
            "controllerId": player_id,
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "exileOnDecline": bool(result.get("exileOnDecline")),
            "reduceWinnerManifestationOnControllerDefeat": bool(
                result.get(
                    "reduceWinnerManifestationOnControllerDefeat"
                )
            ),
            "controllerBasePower": controller_base_power,
        }
        return {
            "kind": "choice_required",
            "choiceId": choice_id,
            "choiceKind": "immediate_effect_payment",
            "playerId": opponent_id,
            "payment": result.get("payment"),
        }

    def _rules_result_exchange_control_targets(self, action, result, player_id, player):
        card_targets = [
            target for target in action.get("targets") or []
            if target.get("kind") == "card"
        ]
        if len(card_targets) != 2:
            return {
                "kind": "exchange_control_targets",
                "status": "target_missing",
            }
        first = self.find_battlefield_item(card_targets[0].get("itemId"))
        second = self.find_battlefield_item(card_targets[1].get("itemId"))
        if first is None or second is None:
            return {
                "kind": "exchange_control_targets",
                "status": "target_missing",
            }
        first_controller = self.rules_item_controller_id(first)
        second_controller = self.rules_item_controller_id(second)
        first["controllerId"] = second_controller
        second["controllerId"] = first_controller
        memory_ids = []
        if result.get("rememberAtResolution"):
            for item in (first, second):
                memory = self.create_rules_effect_memory(
                    item.get("ownerId"), item.get("cardId"),
                    "move_to_deck_at_resolution",
                    controller_id=player_id,
                    source_action_id=action.get("id"),
                    data={
                        "itemId": item.get("id"),
                        "sourceCardId": (action.get("source") or {}).get("cardId"),
                        "sourceOwnerId": (
                            (action.get("source") or {}).get("ownerId")
                            or player_id
                        ),
                    },
                )
                if memory:
                    memory_ids.append(memory["id"])
        # played during the Resolution (Dominate the Aspects in the
        # Effects step): the "at the Resolution" return was already
        # collected for this turn, so it fires right away, before the
        # cards are moved by the outcome of the Confrontation.
        resolution_triggers = (
            self.queue_rules_resolution_memory_triggers(defer=True)
            if memory_ids and self.current_phase_id() == "resolution_effects"
            else []
        )
        return {
            "kind": "exchange_control_targets",
            "status": "exchanged",
            **({"resolutionTriggers": resolution_triggers} if resolution_triggers else {}),
            "itemIds": [first["id"], second["id"]],
            "controllerIds": [
                self.rules_item_controller_id(first),
                self.rules_item_controller_id(second),
            ],
            "memoryIds": memory_ids,
        }

    def _rules_result_create_support_tokens(self, action, result, player_id, player):
        source_item = self.find_battlefield_item(
            (action.get("source") or {}).get("itemId")
        )
        count = int(result.get("count") or 1)
        if result.get("fieldZone") == "interzone":
            # Stampeding Brood: never past the Interzone spaces
            count = max(0, min(count, self.rules_interzone_capacity(player_id)
                               - self.rules_interzone_slot_count(player_id)))
        if result.get("upTo") and count > 0 and action.get("_tokenCount") is None:
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "token_count", "playerId": player_id,
                "max": count, "options": [str(value) for value in range(count + 1)],
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "_action": action,
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "token_count", "playerId": player_id,
            }
        if action.get("_tokenCount") is not None:
            count = max(0, min(count, int(action["_tokenCount"])))
        created = [
            self.create_rules_token_copy(
                None, player_id,
                source_item_id=(source_item or {}).get("id"),
                generic_power=result.get("power"),
                generic_temperament=result.get("temperament"),
                field_zone=result.get("fieldZone"),
            )
            for _index in range(count)
        ]
        created = [item for item in created if item is not None]
        if result.get("permanent"):
            # "not lost at the Resolution": these tokens stay and can only go to the Interzone
            for token in created:
                token["permanent"] = True
        return {
            "kind": "create_support_tokens",
            "status": "created",
            "count": len(created),
            "itemIds": [item["id"] for item in created],
        }

    def _rules_result_move_random_zone_card(self, action, result, player_id, player):
        if result.get("eachPlayer"):
            moves = [
                self._move_random_zone_card(container_id, result)
                for container_id in list(self.players)
            ]
            return {"kind": "move_card", "status": "moved", "random": True, "each": moves}
        target = next(
            (entry for entry in action.get("targets") or [] if entry.get("kind") == "player"),
            None,
        )
        return self._move_random_zone_card(target.get("playerId") if target else None, result)

    def _rules_result_move_target(self, action, result, player_id, player):
        target = next(
            (entry for entry in action.get("targets") or [] if entry.get("kind") in {"card", "zone_card"}),
            None,
        )
        destination = result.get("zone")
        position = result.get("position")
        reason = result.get("reason")
        # Deviate (errata): "Lose 5 points." is part of the resolved effect
        score_paid = (
            -self.adjust_rules_score(player_id, -int(result["scoreCost"]))
            if result.get("scoreCost") and target else 0
        )
        def movement(payload):
            if reason:
                payload["reason"] = reason
            if score_paid:
                payload["scoreLost"] = score_paid
            return payload
        if target and target.get("kind") == "zone_card":
            container_id = target.get("containerId")
            from_zone = target.get("zone")
            card_id = target.get("cardId")
            owner_id = self.card_owner_in_zone(container_id, from_zone, card_id)
            if (
                owner_id is None
                or card_id not in self.players.get(container_id, {}).get("zones", {}).get(from_zone, [])
            ):
                return movement({
                    "kind": "move_card", "status": "target_missing",
                    "cardId": card_id, "fromZone": from_zone,
                    "fromContainerId": container_id, "toZone": destination,
                    "position": position,
                })
            error, _owner_id, replacement = self.move_zone_card_by_effect(
                container_id, from_zone, owner_id, destination, card_id, position,
            )
            if error:
                return movement({
                    "kind": "move_card", "status": "target_missing",
                    "cardId": card_id, "fromZone": from_zone,
                    "fromContainerId": container_id, "toZone": destination,
                    "position": position,
                })
            payload = {
                "kind": "move_card",
                "status": replacement["status"] if replacement else "moved",
                "cardId": card_id,
                "ownerId": owner_id, "fromZone": from_zone,
                "fromContainerId": container_id, "toZone": destination,
                "position": position,
            }
            if replacement:
                payload["replacement"] = replacement
            return movement(payload)
        item = self.find_battlefield_item(target.get("itemId")) if target else None
        if item is None:
            return movement({
                "kind": "move_card", "status": "target_missing",
                "cardId": target.get("cardId") if target else None,
                "itemId": target.get("itemId") if target else None,
                "toZone": result.get("zone"), "position": result.get("position"),
            })
        item_controller = item.get("controllerId") or item.get("ownerId")
        if self.rules_item_zone_locked(item):
            return movement({
                "kind": "move_card", "status": "prevented_zone_lock",
                "cardId": item.get("cardId"), "itemId": item.get("id"),
                "ownerId": item.get("ownerId"), "fromZone": "battlefield",
                "toZone": destination, "position": position,
            })
        if (
            self.rules_item_card_rules(item).get("adamant")
            and self.rules_item_effects_active(item)
            and item_controller != player_id
            and reason != "destroy"
        ):
            return movement({
                "kind": "move_card", "status": "prevented_adamant",
                "cardId": item.get("cardId"), "itemId": item.get("id"),
                "ownerId": item.get("ownerId"), "fromZone": "battlefield",
                "toZone": destination, "position": position,
            })
        movement_result = self._rules_remove_field_item_by_effect(
            item, item.get("ownerId"), destination, position,
            reason=result.get("reason"),
        )
        status = movement_result.get("status")
        if status == "moved":
            if destination == "hand" and result.get("restrictPlayUntilEndOfTurn"):
                self.rules_engine["playRestrictions"].append({
                    "id": new_id(), "playerId": item["ownerId"],
                    "cardId": item["cardId"], "turn": self.phase_tracker["turn"],
                    "sourceActionId": action.get("id"),
                })
        self.prune_rules_ongoing_effects()
        payload = {
            "kind": "move_card", "status": status,
            "cardId": item.get("cardId"), "itemId": item.get("id"),
            "ownerId": item.get("ownerId"), "fromZone": "battlefield",
            "toZone": destination, "position": position,
        }
        if status == "suspended":
            payload["replacement"] = movement_result
        if status == "moved" and destination == "hand" and result.get("restrictPlayUntilEndOfTurn"):
            payload["playRestrictedUntilTurnEnd"] = True
        return movement(payload)

    def _rules_result_chain_from_zone(self, action, result, player_id, player):
        if int(result.get("scoreCost") or 0) < 0:
            self.adjust_rules_score(player_id, int(result["scoreCost"]))
        if result.get("players") == "each_opponent":
            chain_players = [pid for pid in self.players if pid != player_id]
        elif result.get("players") == "all":
            chain_players = [player_id] + [
                pid for pid in self.players if pid != player_id
            ]
        else:
            chain_players = [player_id]
        return self.begin_rules_chain_sequence(
            player_id, chain_players, result, action
        )

    def _rules_result_create_event_token_copy_in_support(self, action, result, player_id, player):
        trigger = (action.get("ability") or {}).get("trigger") or {}
        event_item = self.find_battlefield_item(trigger.get("eventItemId"))
        if (
            event_item is None
            or event_item.get("isTokenCard") or event_item.get("isCopy")
            or event_item.get("isTokenCopy")
            or self.card_rules.get(event_item.get("cardId"), {}).get("type")
            != "manifestation"
        ):
            return {"kind": result.get("kind"), "status": "not_applicable"}
        copy = self.create_rules_token_copy(
            event_item["cardId"], action.get("controllerId") or player_id,
            source_item_id=(action.get("source") or {}).get("itemId"),
        )
        if copy is None:
            return {"kind": result.get("kind"), "status": "entry_blocked"}
        triggered_actions = self.queue_rules_token_copy_entry_triggers(copy)
        return {
            "kind": result.get("kind"), "status": "created",
            "cardId": copy.get("cardId"), "itemId": copy["id"],
            "triggeredActions": triggered_actions,
        }

    def _rules_result_offer_support_else_chain(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "card"
        ), None)
        item = self.find_battlefield_item((target or {}).get("itemId"))
        if item is None or self.rules_field_zone(item) != "interzone":
            return {"kind": result.get("kind"), "status": "target_missing"}
        chooser_id = self.rules_item_controller_id(item)
        if chooser_id not in self.players:
            return {"kind": result.get("kind"), "status": "target_missing"}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "binary_choice", "purpose": "support_else_chain",
            "playerId": chooser_id, "options": ["yes", "no"],
            "headingKey": "rulesSupportElseChainHeading",
            "textKey": "rulesSupportElseChainText",
            "yesKey": "rulesSupportElseChainYes", "noKey": "rulesSupportElseChainNo",
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "relatedCardId": item.get("cardId"),
            "targetItemId": item.get("id"),
            "controllerId": action.get("controllerId"),
            "_action": {
                "id": action.get("id"), "controllerId": action.get("controllerId"),
                "source": dict(action.get("source") or {}),
            },
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "binary_choice", "playerId": chooser_id,
        }

    def _rules_result_return_first_then_chain(self, action, result, player_id, player):
        first = self.find_battlefield_item(
            (self.rules_engine.get("firstManifestationItemIds") or {}).get(player_id)
        )
        if first is None or self.rules_item_zone_locked(first):
            return {"kind": result.get("kind"), "status": "no_first_manifestation"}
        owner_id = first.get("ownerId")
        card_id = first.get("cardId")
        movement = self._rules_remove_field_item_by_effect(
            first, owner_id, "hand", "top"
        )
        if movement.get("status") == "moved":
            self.rules_engine["playRestrictions"].append({
                "id": new_id(), "playerId": owner_id, "cardId": card_id,
                "turn": self.phase_tracker["turn"],
                "sourceActionId": action.get("id"),
            })
        self.prune_rules_ongoing_effects()
        chain = self.begin_rules_chain_sequence(
            player_id, [player_id],
            {"kind": "chain_from_zone", "zone": "hand", "optional": False},
            action,
        )
        return {**chain, "returned": {
            "status": movement.get("status"), "cardId": card_id,
            "ownerId": owner_id, "playRestrictedUntilTurnEnd": True,
        }}
