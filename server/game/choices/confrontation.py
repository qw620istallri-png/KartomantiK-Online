"""Pending choices made during the Confrontation and Recovery phases."""

from ..common import ADVANCED_PHASES, new_id


class ConfrontationChoicesMixin:
    def _rules_choice_persist_first_manifestation(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if item_id not in choice.get("candidateItemIds", []):
            return "Choose a valid Persist Manifestation.", None
        candidates = [
            self.find_battlefield_item(candidate_id)
            for candidate_id in choice.get("candidateItemIds") or []
        ]
        if any(candidate is None for candidate in candidates):
            return "A Persist Manifestation is no longer available.", None
        result = self.rules_engine.get("confrontationResult") or {}
        persisted = self.find_battlefield_item(item_id)
        persisted_result = self._mark_rules_persisted_first(
            persisted, player_id
        )
        result.setdefault("persisted", []).append(persisted_result)
        returned = []
        for candidate in candidates:
            if candidate.get("id") == item_id:
                continue
            returned.append(self._rules_remove_field_item(
                candidate, candidate.get("ownerId"), "deck", "bottom"
            ))
        result.setdefault("returned", []).extend(returned)
        self.rules_engine["pendingChoice"] = None
        self._queue_next_rules_confrontation_destination()
        return None, {
            "kind": "persist_first_manifestation",
            "playerId": player_id,
            "itemId": item_id,
            "cardId": persisted.get("cardId"),
            "returnedItemIds": [
                movement.get("itemId") for movement in returned
            ],
        }

    def _rules_choice_confrontation_relocation(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        groups = choice.get("_groups") or []
        supplied = (
            option.get("groups")
            if isinstance(option, dict) else None
        )
        if not isinstance(supplied, list) or len(supplied) != len(groups):
            return "Choose a destination for every Confrontation Manifestation.", None
        validated_groups = []
        supplied_players = [entry.get("playerId") if isinstance(entry, dict) else None for entry in supplied]
        if (
            not all(isinstance(pid, str) for pid in supplied_players)
            or len(set(supplied_players)) != len(supplied_players)
            or set(supplied_players) != {group.get("playerId") for group in groups}
        ):
            return "Choose every player's Confrontation destinations.", None
        for group in groups:
            submitted = next((
                entry for entry in supplied
                if isinstance(entry, dict)
                and entry.get("playerId") == group.get("playerId")
            ), None)
            if submitted is None:
                return "Choose every player's Confrontation destinations.", None
            interzone_ids = submitted.get("interzone")
            deck_ids = submitted.get("deckBottom")
            expected = list(group.get("itemIds") or [])
            if (
                not isinstance(interzone_ids, list)
                or not isinstance(deck_ids, list)
                or not all(isinstance(current_id, str) for current_id in interzone_ids + deck_ids)
                or len(interzone_ids) > int(group.get("interzoneSlots") or 0)
                or len(set(interzone_ids + deck_ids)) != len(expected)
                or set(interzone_ids + deck_ids) != set(expected)
            ):
                return "Use every Confrontation Manifestation exactly once within the Interzone limit.", None
            for current_id in interzone_ids + deck_ids:
                item = self.find_battlefield_item(current_id)
                if (
                    item is None or self.rules_field_zone(item) != "confrontation"
                    or item.get("ownerId") != group.get("playerId")
                ):
                    return "A Confrontation Manifestation is no longer available.", None
            validated_groups.append((interzone_ids, deck_ids))

        movements = []
        for interzone_ids, deck_ids in validated_groups:
            for current_id in interzone_ids:
                item = self.find_battlefield_item(current_id)
                if item is None:
                    continue
                item["fieldZone"] = "interzone"
                self.mark_rules_interzone_entry(item)
                item["isSupport"] = False
                item["stackedOn"] = None
                movements.append({
                    "itemId": current_id, "cardId": item.get("cardId"),
                    "destination": "interzone",
                })
            for current_id in deck_ids:
                item = self.find_battlefield_item(current_id)
                if item is None:
                    continue
                movements.append(self._rules_remove_field_item_by_effect(
                    item, item.get("ownerId"), "deck", "bottom"
                ))
        opponent_id = self.other_rules_player_id(player_id)
        if opponent_id:
            self.adjust_rules_score(opponent_id, 50)
        self.phase_tracker["index"] = ADVANCED_PHASES.index("end_actions")
        self.rules_engine["priorityPasses"] = []
        self.rules_engine["confrontationResult"] = None
        self.rules_engine["pendingChoice"] = None
        return None, {
            "kind": "confrontation_relocation",
            "status": "ended",
            "playerId": player_id,
            "movements": movements,
            "opponentId": opponent_id,
            "opponentScore": (
                self.players[opponent_id]["score"] if opponent_id else None
            ),
            "phaseId": self.current_phase_id(),
            "sourceMovement": choice.get("_sourceMovement"),
            "sourceCardId": choice.get("sourceCardId"),
        }

    def _rules_choice_recovery_shared_choice(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if option not in choice.get("options", []):
            return "Choose a valid Recovery effect.", None
        discarded = []
        score_delta = 0
        if option == "discard_deck_bottom_3":
            if len(self.players[player_id]["zones"]["deck"]) < 3:
                return "Your Deck no longer has three cards to discard.", None
            for _index in range(3):
                card_id = self.players[player_id]["zones"]["deck"][-1]
                error, _owner_id = self.move_zone_card(
                    player_id, "deck", player_id, "graveyard", card_id, "top"
                )
                if error:
                    return error, None
                discarded.append(card_id)
        else:
            score_delta = self.adjust_rules_score(player_id, -10)
        remaining = list(choice.get("remainingPlayerIds") or [])
        source_action = {
            "id": choice.get("actionId"),
            "controllerId": choice.get("controllerId"),
            "source": {"cardId": choice.get("sourceCardId")},
        }
        self.rules_engine["pendingChoice"] = None
        next_choice = self._set_next_rules_recovery_choice(remaining, source_action)
        return None, {
            "kind": "recovery_shared_choice",
            "playerId": player_id,
            "option": option,
            "cardIds": discarded,
            "count": len(discarded),
            "scoreDelta": score_delta,
            "score": self.players[player_id]["score"],
            "choiceId": choice_id,
            "actionId": choice.get("actionId"),
            "controllerId": choice.get("controllerId"),
            "sourceCardId": choice.get("sourceCardId"),
            "nextPlayerId": next_choice.get("playerId") if next_choice else None,
        }

    def _rules_choice_confrontation_destination(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if option not in choice.get("options", []):
            return "Choose a valid confrontation destination.", None
        item = self.find_battlefield_item(choice.get("itemId"))
        if item is None or item.get("ownerId") != player_id:
            return "This confrontation card is no longer available.", None
        result = self.rules_engine.get("confrontationResult") or {}
        if option == "deck_bottom":
            movement = self._rules_remove_field_item(item, item["ownerId"], "deck", "bottom")
            result.setdefault("returned", []).append(movement)
            pending = result.get("pendingOwnItemIds") or []
            if pending and pending[0] == item["id"]:
                pending.pop(0)
            self.rules_engine["pendingChoice"] = None
            self._queue_next_rules_confrontation_destination()
            return None, {
                "kind": "confrontation_destination", "playerId": player_id,
                "cardId": item.get("cardId"), "itemId": item.get("id"),
                "destination": "deck_bottom",
            }

        if option == "karmapult":
            holder = self.rules_karmapult_holder(player_id, item)
            if holder is None:
                return "You have no Karmapult to place it on.", None
            self.battlefield.remove(item)
            for other in self.battlefield:
                if other.get("stackedOn") == item.get("id"):
                    other["stackedOn"] = None
            holder.setdefault("attachedCards", []).append({
                "cardId": item["cardId"], "ownerId": item["ownerId"],
            })
            self.rules_sync_attached_counter(holder)
            result.setdefault("returned", []).append({
                "status": "karmapult", "itemId": item["id"], "cardId": item.get("cardId"),
            })
            pending = result.get("pendingOwnItemIds") or []
            if pending and pending[0] == item["id"]:
                pending.pop(0)
            self.rules_engine["pendingChoice"] = None
            self._queue_next_rules_confrontation_destination()
            return None, {
                "kind": "confrontation_destination", "playerId": player_id,
                "cardId": item.get("cardId"), "itemId": item.get("id"),
                "destination": "karmapult", "holderItemId": holder["id"],
            }

        # a Support (World Spore...) leaves the card it was under: it takes its own Interzone slot
        if item.get("isSupport") or item.get("stackedOn"):
            item["stackedOn"] = None
            item["isSupport"] = False
        interzone_items = self.rules_confrontation_items(player_id, ("interzone",))
        if self.rules_interzone_slot_count(player_id) >= self.rules_interzone_capacity(player_id):
            share_anchor = self.rules_interzone_share_anchor(player_id, item)
            if share_anchor:
                item["fieldZone"] = "interzone"
                item["controllerId"] = player_id
                self.mark_rules_interzone_entry(item)
                item["stackedOn"] = share_anchor
                result.setdefault("returned", []).append({
                    "status": "interzone", "itemId": item["id"],
                    "cardId": item.get("cardId"), "stackedOn": share_anchor,
                })
                pending = result.get("pendingOwnItemIds") or []
                if pending and pending[0] == item["id"]:
                    pending.pop(0)
                self.rules_engine["pendingChoice"] = None
                triggered_actions = self.queue_rules_field_zone_entry_triggers(
                    item, "interzone",
                    resume_confrontation_cleanup=True,
                )
                if not self.rules_engine.get("pendingChoice"):
                    self._queue_next_rules_confrontation_destination()
                return None, {
                    "kind": "confrontation_destination", "playerId": player_id,
                    "cardId": item.get("cardId"), "itemId": item.get("id"),
                    "destination": "interzone", "stackedOn": share_anchor,
                    "triggeredActions": triggered_actions,
                }
            replacement_candidates = [
                entry["id"] for entry in interzone_items
                if self.rules_interzone_item_replaceable(entry)
            ]
            if not replacement_candidates:
                return "No Manifestation in your Interzone can currently be replaced.", None
            replacement = {
                "id": new_id(), "kind": "confrontation_replace_interzone",
                "playerId": player_id, "itemId": item["id"], "cardId": item.get("cardId"),
                "candidateItemIds": replacement_candidates,
            }
            self.rules_engine["pendingChoice"] = replacement
            return None, {
                "kind": "confrontation_replacement_required", "playerId": player_id,
                "cardId": item.get("cardId"), "itemId": item.get("id"),
            }
        item["fieldZone"] = "interzone"
        item["controllerId"] = player_id
        self.mark_rules_interzone_entry(item)
        result.setdefault("returned", []).append({
            "status": "interzone", "itemId": item["id"], "cardId": item.get("cardId"),
        })
        pending = result.get("pendingOwnItemIds") or []
        if pending and pending[0] == item["id"]:
            pending.pop(0)
        self.rules_engine["pendingChoice"] = None
        triggered_actions = self.queue_rules_field_zone_entry_triggers(
            item, "interzone",
            resume_confrontation_cleanup=True,
        )
        if not self.rules_engine.get("pendingChoice"):
            self._queue_next_rules_confrontation_destination()
        return None, {
            "kind": "confrontation_destination", "playerId": player_id,
            "cardId": item.get("cardId"), "itemId": item.get("id"),
            "destination": "interzone",
            "triggeredActions": triggered_actions,
        }

    def _rules_choice_confrontation_replace_interzone(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if item_id not in choice.get("candidateItemIds", []):
            return "Choose a valid Interzone card to replace.", None
        entering = self.find_battlefield_item(choice.get("itemId"))
        replaced = self.find_battlefield_item(item_id)
        if (
            entering is None
            or replaced is None
            or self.rules_item_controller_id(replaced) != player_id
            or not self.rules_interzone_item_replaceable(replaced)
        ):
            return "This Interzone choice is no longer available.", None
        movement = self._rules_remove_field_item(replaced, replaced["ownerId"], "deck", "bottom")
        entering["fieldZone"] = "interzone"
        entering["controllerId"] = player_id
        self.mark_rules_interzone_entry(entering)
        result = self.rules_engine.get("confrontationResult") or {}
        result.setdefault("returned", []).extend([
            movement,
            {"status": "interzone", "itemId": entering["id"], "cardId": entering.get("cardId")},
        ])
        pending = result.get("pendingOwnItemIds") or []
        if pending and pending[0] == entering["id"]:
            pending.pop(0)
        self.rules_engine["pendingChoice"] = None
        triggered_actions = self.queue_rules_field_zone_entry_triggers(
            entering, "interzone",
            resume_confrontation_cleanup=True,
        )
        if not self.rules_engine.get("pendingChoice"):
            self._queue_next_rules_confrontation_destination()
        return None, {
            "kind": "confrontation_replace_interzone", "playerId": player_id,
            "cardId": entering.get("cardId"), "itemId": entering.get("id"),
            "replacedCardId": replaced.get("cardId"), "replacedItemId": replaced.get("id"),
            "triggeredActions": triggered_actions,
        }
