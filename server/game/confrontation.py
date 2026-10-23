"""State actions, Confrontation results and end-of-Confrontation cleanup."""

import random

from .common import NUM_SEATS, TEMPERAMENT_DOMINANCE, new_id


class ConfrontationMixin:
    def resolve_rules_state_actions(self, previous_powers=None):
        """Destroy face-up Manifestations whose current Power is zero or less."""
        previous_powers = dict(previous_powers or {})
        destroyed = []
        replacements = []
        triggered_actions = []
        threshold_exiled = []
        for item in list(self.battlefield):
            if (
                not item.get("faceUp")
                or self.rules_item_card_rules(item).get("type") != "manifestation"
                or not self.rules_item_effects_active(item)
                or self.rules_field_zone(item) == "stalemate"
            ):
                continue
            passive = next((
                entry for entry in self.rules_item_card_rules(item).get("passiveEffects") or []
                if entry.get("kind") == "sacrifice_at_power"
            ), None)
            if (
                passive is None
                or self.rules_manifestation_characteristics(item)["power"]
                < int(passive.get("threshold") or 0)
            ):
                continue
            controller_id = self.rules_item_controller_id(item)
            movement = self._rules_remove_field_item_by_effect(
                item, item.get("ownerId"), "graveyard", "top", reason="sacrifice",
            )
            movement["replacement"] = "sacrifice_at_power"
            replacements.append(movement)
            if movement.get("status") == "moved":
                triggered_actions.extend(self.queue_rules_zone_entry_triggers(
                    item.get("cardId"), item.get("ownerId"),
                    item.get("ownerId"), "graveyard", defer=True,
                ))
            for other in self.rules_confrontation_items(controller_id):
                self.append_rules_ongoing_effect({
                    "id": new_id(), "actionId": None,
                    "abilityId": "sacrifice-at-power-bonus",
                    "controllerId": controller_id,
                    "source": {"cardId": item.get("cardId")},
                    "target": {
                        "kind": "card", "itemId": other["id"],
                        "cardId": other.get("cardId"), "ownerId": other.get("ownerId"),
                    },
                    "kind": "power_modifier", "value": int(passive.get("bonus") or 0),
                    "duration": "until_end_of_turn",
                    "startedTurn": self.phase_tracker["turn"],
                })
        for item in list(self.rules_confrontation_items()):
            if not self.rules_item_effects_active(item):
                continue
            threshold = self.rules_item_card_rules(item).get(
                "suspensionThresholds", {}
            ).get("exile")
            if (
                isinstance(threshold, (int, float))
                and self.rules_manifestation_characteristics(item)["power"] >= threshold
            ):
                suspended = self.release_rules_suspended_by(
                    item.get("id"), exile=True
                )
                movement = self._rules_remove_field_item(
                    item, item.get("ownerId"), "exile", "top",
                    release_suspended=False,
                )
                movement["exiledSuspended"] = suspended
                threshold_exiled.append(movement)
        while True:
            candidates = [
                item for item in list(self.battlefield)
                if item.get("faceUp")
                and (
                    self.rules_item_card_rules(item).get("type") == "manifestation"
                    or item.get("isTokenCard")
                )
                and (
                    item.get("id") not in previous_powers
                    or previous_powers[item.get("id")] > 0
                    or item.get("zeroPowerSustained")
                )
                and self.rules_manifestation_characteristics(item)["power"] <= 0
            ]
            if not candidates:
                break
            removed_items = []
            sustained_any = False
            life_sources = self.rules_active_passive_sources(
                "sustain_exact_zero"
            )
            greed_sources = self.rules_active_passive_sources(
                "capture_opponent_exact_zero"
            )
            for item in candidates:
                power = self.rules_manifestation_characteristics(item)["power"]
                item_controller = item.get("controllerId") or item.get("ownerId")
                greed_source = next((
                    source for source in greed_sources
                    if (source.get("controllerId") or source.get("ownerId"))
                    != item_controller
                ), None)
                if power == 0 and greed_source:
                    destination_player_id = (
                        greed_source.get("controllerId")
                        or greed_source.get("ownerId")
                    )
                    movement = self._rules_remove_field_item(
                        item, destination_player_id, "receptacle", "top"
                    )
                    movement["replacement"] = "capture_opponent_exact_zero"
                    replacements.append(movement)
                    removed_items.append(item)
                    continue
                if power == 0 and life_sources:
                    if not item.get("effectsDisabled"):
                        item["effectsDisabled"] = True
                        item["zeroPowerSustained"] = True
                        replacements.append({
                            "status": "sustained",
                            "replacement": "sustain_exact_zero",
                            "itemId": item.get("id"),
                            "cardId": item.get("cardId"),
                        })
                        self.prune_rules_ongoing_effects()
                    sustained_any = True
                    continue
                movement = self._rules_remove_field_item_by_effect(
                    item, item.get("ownerId"), "graveyard", "top",
                    reason="destroy",
                )
                destroyed.append(movement)
                removed_items.append(item)
                if movement.get("status") == "moved":
                    triggered_actions.extend(self.queue_rules_zone_entry_triggers(
                        item.get("cardId"), item.get("ownerId"),
                        item.get("ownerId"), "graveyard", defer=True,
                    ))
            if not removed_items:
                if sustained_any:
                    break
                break
            powers_before_removal = {
                item.get("id"): self.rules_manifestation_characteristics(item)["power"]
                for item in self.battlefield
            }
            self.prune_rules_ongoing_effects()
            previous_powers = powers_before_removal
        return {
            "destroyed": destroyed,
            "replacements": replacements,
            "triggeredActions": triggered_actions,
            "thresholdExiled": threshold_exiled,
        }

    @staticmethod
    def rules_temperament_winner(first, second):
        if first == second or not first or not second:
            return None
        if first == "transcendent" or second == "hollow":
            return 0
        if second == "transcendent" or first == "hollow":
            return 1
        if second in TEMPERAMENT_DOMINANCE.get(first, set()):
            return 0
        if first in TEMPERAMENT_DOMINANCE.get(second, set()):
            return 1
        return None

    @staticmethod
    def rules_priority_roll(player_ids):
        while True:
            rolls = {player_id: random.randint(1, 6) for player_id in player_ids}
            high = max(rolls.values())
            winners = [player_id for player_id, value in rolls.items() if value == high]
            if len(winners) == 1:
                return winners[0], rolls

    def _rules_remove_field_item(self, item, container_id, zone, position="top",
                                 release_suspended=True, reason=None):
        if item not in self.battlefield:
            return {"status": "missing", "itemId": item.get("id")}
        rolls_for_vessel = bool(
            zone == "receptacle"
            and self.rules_item_card_rules(item).get("vesselEntryRoll")
            and self.rules_item_effects_active(item)
        )
        if (
            item.get("exileIfLeaves")
            and zone in {"graveyard", "hand", "deck"}
            and not item.get("isCopy") and not item.get("isTokenCard")
        ):
            container_id, zone, position = item.get("ownerId"), "exile", "top"
        if not item.get("isCopy") and not item.get("isTokenCard"):
            container_id, zone, position = self.rules_zone_move_destination(
                container_id, zone, item.get("cardId"), item.get("ownerId"),
                position, from_field=True,
            )
        self.battlefield.remove(item)
        for entry in item.pop("attachedCards", None) or []:
            self.put_zone_card(entry["ownerId"], "exile", entry["cardId"], entry["ownerId"], "top")
        for other in self.battlefield:
            if other.get("stackedOn") == item.get("id"):
                other["stackedOn"] = None
        if item.get("isCopy") or item.get("isTokenCard"):
            self.rules_engine["effectMemories"] = [memory
                for memory in self.rules_engine.get("effectMemories") or []
                if (memory.get("data") or {}).get("itemId") != item.get("id")]
            released = self.release_rules_suspended_by(item.get("id")) if release_suspended else []
            return {
                "status": "removed_copy", "itemId": item.get("id"),
                "cardId": item.get("cardId"), "ownerId": item.get("ownerId"),
                "releasedSuspended": released,
            }
        vessel_roll = None
        if rolls_for_vessel:
            vessel_roll = random.randint(1, 6)
            self.rules_engine["lastVesselRoll"] = {
                "cardId": item.get("cardId"), "roll": vessel_roll,
                "turn": self.phase_tracker["turn"],
            }
            if vessel_roll % 2 == 1:
                container_id, zone, position = item["ownerId"], "hand", "top"
        self.put_zone_card(container_id, zone, item["cardId"], item["ownerId"], position,
                           limbo_reason=reason or "move", from_zone="battlefield")
        if (zone == "receptacle" and container_id != item.get("ownerId")
                and self.rules_item_card_rules(item).get("type") == "manifestation"):
            self.record_rules_observed_event(
                "manifestation_enters_opponent_vessel", item.get("ownerId")
            )
        if zone in {"deck", "exile"}:
            self.clear_rules_effect_memories(item["ownerId"], item["cardId"])
        released = (
            self.release_rules_suspended_by(item.get("id"))
            if release_suspended
            and any(
                entry.get("sourceEffectId") == item.get("id")
                for entry in self.rules_engine.get("suspendedCards") or []
            )
            else []
        )
        return {
            "status": "moved", "itemId": item.get("id"), "cardId": item.get("cardId"),
            "ownerId": item.get("ownerId"), "containerId": container_id,
            "zone": zone, "position": position, "releasedSuspended": released,
            **({"vesselRoll": vessel_roll} if vessel_roll is not None else {}),
        }

    def _rules_remove_field_item_by_effect(self, item, container_id, zone,
                                           position="top", reason=None):
        if item not in self.battlefield:
            return {"status": "missing", "itemId": item.get("id")}
        if item.get("isCopy") or item.get("isTokenCard"):
            controller_before = self.rules_item_controller_id(item)
            is_manifestation = self.rules_item_card_rules(item).get("type") == "manifestation" or item.get("isTokenCard")
            movement = self._rules_remove_field_item(item, container_id, zone, position)
            if is_manifestation:
                self.record_rules_observed_event("manifestation_left_by_effect", controller_before, cardId=item.get("cardId"))
            return movement
        replacement = self.rules_effect_move_replacement(
            item.get("ownerId"), "battlefield", container_id, zone, item.get("cardId"), item,
        )
        field_penalty = 0
        suspension_source = None
        if replacement:
            if replacement['replacementKind'] == 'suspend':
                suspension_source = replacement['_sourceItem']
            else:
                container_id, zone = replacement['_destination']
                position = 'top'
                if replacement['actionId'].startswith('exile-cz:'):
                    field_penalty = int(self.rules_item_card_rules(item).get('exiledByEffectFieldPenalty') or 0)
        controller_before = self.rules_item_controller_id(item)
        if suspension_source:
            self.battlefield.remove(item)
            for attached in item.pop("attachedCards", None) or []:
                self.put_zone_card(attached['ownerId'], 'exile', attached['cardId'], attached['ownerId'])
            for other in self.battlefield:
                if other.get("stackedOn") == item.get("id"):
                    other["stackedOn"] = None
            suspended = {
                "id": new_id(),
                "cardId": item.get("cardId"),
                "ownerId": item.get("ownerId"),
                "fromContainerId": item.get("ownerId"),
                "fromZone": "battlefield",
                "sourceEffectId": suspension_source.get("id"),
            }
            self.rules_engine["suspendedCards"].append(suspended)
            if self.rules_item_card_rules(item).get("type") == "manifestation":
                self.record_rules_observed_event(
                    "manifestation_left_by_effect", controller_before, cardId=item.get("cardId"),
                )
            self.prune_rules_ongoing_effects()
            released = (
                self.release_rules_suspended_by(suspension_source.get("id"))
                if item.get("id") == suspension_source.get("id") else []
            )
            return {
                "status": "suspended",
                "itemId": item.get("id"),
                "cardId": item.get("cardId"),
                "ownerId": item.get("ownerId"),
                "suspensionId": suspended["id"],
                "sourceItemId": suspension_source.get("id"),
                "releasedSuspended": released,
            }
        movement = self._rules_remove_field_item(
            item, container_id, zone, position, reason=reason
        )
        if field_penalty and movement.get("status") == "moved":
            for other in self.battlefield:
                if self.card_rules.get(other.get("cardId"), {}).get("type") == "manifestation":
                    self.adjust_rules_power_counter(other, -field_penalty)
        if (
            movement.get("status") == "moved"
            and self.rules_item_card_rules(item).get("type") == "manifestation"
        ):
            self.record_rules_observed_event(
                "manifestation_left_by_effect", controller_before,
                cardId=item.get("cardId"),
            )
        if (
            movement.get("status") == "moved"
            and movement.get("zone") == "graveyard"
            and reason in {"destroy", "discard"}
        ):
            if reason == "destroy":
                if self.rules_item_card_rules(item).get("type") == "manifestation":
                    self.record_rules_observed_event("manifestation_destroyed", controller_before)
            else:
                self.record_rules_observed_event(
                    "cards_discarded", item.get("ownerId")
                )
        return movement

    def prepare_rules_confrontation_result(self):
        if not self.rules_engine["enabled"] or self.current_phase_id() != "resolution_compare":
            return None
        existing = self.rules_engine.get("confrontationResult")
        if existing and existing.get("turn") == self.phase_tracker["turn"]:
            return existing

        state_actions = self.resolve_rules_state_actions()
        destroyed = state_actions["destroyed"]
        if state_actions["triggeredActions"]:
            self.queue_rules_simultaneous_actions(
                state_actions["triggeredActions"]
            )
        self.prune_rules_ongoing_effects()

        player_ids = list(self.players)
        totals = {}
        last_temperaments = {}
        participant_ids = []
        for player_id in player_ids:
            items = self.rules_confrontation_items(player_id)
            participant_ids.extend(item["id"] for item in items)
            totals[player_id] = sum(self.rules_confrontation_power(item) for item in items)
            last_item = max(
                items,
                key=lambda item: (
                    int(item.get("confrontationOrder") or 0),
                    self.battlefield.index(item),
                ),
                default=None,
            )
            last_temperaments[player_id] = (
                self.rules_manifestation_characteristics(last_item)["temperament"]
                if last_item else None
            )

        winner_id = None
        loser_id = None
        reason = "stalemate"
        priority_rolls = None
        forced_winner_id = self.rules_engine.get(
            "forcedConfrontationWinnerId"
        )
        loudmouth_forces_stalemate = any(
            passive.get("kind") == "stalemate_if_last_confrontation_entry"
            and int(source.get("confrontationOrder") or 0)
            == max((
                int(item.get("confrontationOrder") or 0)
                for item in self.rules_confrontation_items()
            ), default=0)
            for source in self.rules_active_passive_sources(
                "stalemate_if_last_confrontation_entry"
            )
            for passive in self.card_rules.get(
                source.get("cardId"), {}
            ).get("passiveEffects") or []
        )
        loudmouth_forces_stalemate = (
            loudmouth_forces_stalemate
            or bool(self.rules_engine.get("forcedConfrontationStalemate"))
        )
        if forced_winner_id in self.players and not loudmouth_forces_stalemate:
            winner_id = forced_winner_id
            loser_id = self.other_rules_player_id(winner_id)
            reason = "forced"
        elif len(player_ids) == 2 and not loudmouth_forces_stalemate:
            first_id, second_id = player_ids
            if totals[first_id] != totals[second_id]:
                winner_id = first_id if totals[first_id] > totals[second_id] else second_id
                reason = "power"
            elif totals[first_id] <= 0:
                # 0 against 0: nobody wins, Temperaments do not decide it
                pass
            else:
                temperament_winner = self.rules_temperament_winner(
                    last_temperaments[first_id], last_temperaments[second_id]
                )
                if temperament_winner is not None:
                    winner_id = player_ids[temperament_winner]
                    reason = "temperament"
            if winner_id:
                loser_id = second_id if winner_id == first_id else first_id

        if winner_id:
            priority_id = winner_id
            self.rules_engine["lastConfrontationWinnerId"] = winner_id
        elif player_ids:
            priority_id, priority_rolls = self.rules_priority_roll(player_ids)
        else:
            priority_id = None
        self.rules_engine["priorityPlayerId"] = priority_id
        result = {
            "turn": self.phase_tracker["turn"], "status": "effects",
            "winnerId": winner_id, "loserId": loser_id,
            "stalemate": winner_id is None, "reason": reason,
            "totals": totals, "lastTemperaments": last_temperaments,
            "participantItemIds": participant_ids, "destroyed": destroyed,
            "winnerItemIds": [item["id"] for item in self.rules_confrontation_items(winner_id)] if winner_id else [],
            "loserItemIds": [item["id"] for item in self.rules_confrontation_items(loser_id)] if loser_id else [],
            "stateReplacements": state_actions["replacements"],
            "priorityPlayerId": priority_id, "priorityRolls": priority_rolls,
            "captured": [], "returned": [],
        }
        self.rules_engine["confrontationResult"] = result
        if loser_id:
            self.rules_engine.setdefault("confrontationLosses", {})[
                str(self.phase_tracker["turn"])
            ] = loser_id
        elif winner_id is None:
            self.rules_engine.setdefault("confrontationStalemates", {})[
                str(self.phase_tracker["turn"])
            ] = True
        if winner_id and len(self.rules_confrontation_items(winner_id)) == 1:
            for source in self.rules_active_passive_sources("solo_confrontation_win_points"):
                if self.rules_item_controller_id(source) != winner_id:
                    continue
                value = sum(
                    int(passive.get("value") or 0)
                    for passive in self.rules_item_card_rules(source).get("passiveEffects") or []
                    if passive.get("kind") == "solo_confrontation_win_points"
                )
                effect_source = {"cardId": source.get("cardId"), "itemId": source.get("id"), "zone": "battlefield"}
                effect_result = self.apply_rules_action_result({
                    "controllerId": winner_id, "source": effect_source,
                    "ability": {"result": {"kind": "score_owner", "value": value}},
                })
                result.setdefault("automaticEffects", []).append({"source": effect_source, "effectResult": effect_result})
                self.add_log(winner_id, "rules_action_resolved", {
                    "controllerId": winner_id, "automatic": True,
                    "label": self.card_labels.get(source.get("cardId"), source.get("cardId")),
                    "source": effect_source, "effectResult": effect_result,
                    "stackDepth": len(self.rules_engine["actionStack"]),
                })
        return result

    def rules_revelation_order(self):
        """Return First Manifestations in the official simultaneous-trigger order."""
        player_ids = list(self.players)
        if len(player_ids) != 2:
            return list(self.rules_engine["firstManifestationItemIds"].values()), None, None
        items_by_player = {
            player_id: self.find_battlefield_item(
                self.rules_engine["firstManifestationItemIds"].get(player_id)
            )
            for player_id in player_ids
        }
        totals = {
            player_id: sum(self.rules_confrontation_power(item) for item in self.rules_confrontation_items(player_id))
            for player_id in player_ids
        }
        first_id, second_id = player_ids
        advantaged_id = None
        if totals[first_id] != totals[second_id]:
            advantaged_id = first_id if totals[first_id] > totals[second_id] else second_id
        else:
            first_temperament = self.rules_manifestation_characteristics(items_by_player[first_id])["temperament"]
            second_temperament = self.rules_manifestation_characteristics(items_by_player[second_id])["temperament"]
            temperament_winner = self.rules_temperament_winner(first_temperament, second_temperament)
            if temperament_winner is not None:
                advantaged_id = player_ids[temperament_winner]
        if advantaged_id:
            priority_id = second_id if advantaged_id == first_id else first_id
            order = [priority_id, advantaged_id]
            rolls = None
        else:
            priority_id, rolls = self.rules_priority_roll(player_ids)
            order = [priority_id, self.other_rules_player_id(priority_id)]
        return [
            items_by_player[player_id]["id"]
            for player_id in order if items_by_player.get(player_id)
        ], priority_id, rolls

    def rules_lowest_confrontation_power_player(self):
        """Return the player who would lose if the confrontation resolved now."""
        player_ids = list(self.players)
        if len(player_ids) != NUM_SEATS:
            return None
        items_by_player = {
            player_id: self.rules_confrontation_items(player_id)
            for player_id in player_ids
        }
        totals = {
            player_id: sum(self.rules_confrontation_power(item) for item in items)
            for player_id, items in items_by_player.items()
        }
        first_id, second_id = player_ids
        if totals[first_id] != totals[second_id]:
            return first_id if totals[first_id] < totals[second_id] else second_id
        last_items = {
            player_id: max(
                items,
                key=lambda item: (
                    int(item.get("confrontationOrder") or 0),
                    self.battlefield.index(item),
                ),
                default=None,
            )
            for player_id, items in items_by_player.items()
        }
        first_temperament = self.rules_manifestation_characteristics(
            last_items[first_id]
        )["temperament"]
        second_temperament = self.rules_manifestation_characteristics(
            last_items[second_id]
        )["temperament"]
        temperament_winner = self.rules_temperament_winner(
            first_temperament, second_temperament
        )
        if temperament_winner is None:
            return None
        return second_id if temperament_winner == 0 else first_id

    def _queue_next_rules_confrontation_destination(self):
        result = self.rules_engine.get("confrontationResult") or {}
        pending = result.get("pendingOwnItemIds") or []
        while pending:
            candidate = self.find_battlefield_item(pending[0])
            if candidate is None:
                pending.pop(0)
            elif (
                (candidate.get("isCopy") or candidate.get("isTokenCard"))
                and not candidate.get("permanent")
            ):
                # temporary Copies and Tokens end with the turn: no deck, no Interzone
                result.setdefault("returned", []).append(
                    self._rules_remove_field_item(
                        candidate, candidate.get("ownerId"), "exile", "top"
                    )
                )
                pending.pop(0)
            else:
                break
        if not pending:
            result["status"] = "complete"
            result.pop("pendingOwnItemIds", None)
            self.rules_engine["pendingChoice"] = None
            self.prune_rules_ongoing_effects()
            return None
        item = self.find_battlefield_item(pending[0])
        choice = {
            "id": new_id(), "kind": "confrontation_destination",
            "playerId": result.get("winnerId"), "itemId": item["id"],
            "cardId": item.get("cardId"), "options": ["interzone", "deck_bottom"],
        }
        if item.get("isCopy") or item.get("isTokenCard"):
            # a permanent Copy or Token can only stay in the Interzone
            choice["options"] = ["interzone"]
        elif self.rules_karmapult_holder(result.get("winnerId"), item):
            choice["options"].append("karmapult")
        self.rules_engine["pendingChoice"] = choice
        result["status"] = "cleanup_choice"
        return choice

    def _mark_rules_persisted_first(self, item, player_id):
        for other in self.battlefield:
            if (other.get("controllerId") or other.get("ownerId")) == player_id:
                other.pop("persistedFirst", None)
        item["fieldZone"] = "confrontation"
        item["isSupport"] = False
        item["persistedFirst"] = True
        item["stackedOn"] = None
        self.rules_engine["firstManifestationItemIds"][player_id] = item["id"]
        return {
            "status": "persisted",
            "itemId": item["id"],
            "cardId": item.get("cardId"),
            "playerId": player_id,
        }

    def rules_item_confrontation_outcome(self, item, result, *, won):
        side = "winner" if won else "loser"
        participants = result.get(f"{side}ItemIds")
        if participants is not None:
            return item.get("id") in participants
        return self.rules_item_controller_id(item) == result.get(f"{side}Id")

    def begin_rules_confrontation_cleanup(self):
        result = self.rules_engine.get("confrontationResult")
        if not result or result.get("turn") != self.phase_tracker["turn"]:
            result = self.prepare_rules_confrontation_result()
        if not result or result.get("status") not in {"effects", "cleanup"}:
            return result
        participant_ids = set(result.get("participantItemIds") or [])
        self.settle_rules_will_manifestations(result, participant_ids)
        support_returned = []
        for item in list(self.battlefield):
            support_return = item.get("supportReturn")
            if not support_return or item.get("id") not in participant_ids:
                continue
            if self.rules_item_zone_locked(item):
                continue
            controller_id = support_return.get("controllerId")
            if (
                not result.get("stalemate")
                and result.get("winnerId") == controller_id
                and controller_id in self.players
            ):
                support_returned.append(self._rules_remove_field_item(
                    item, controller_id, "receptacle", "top"
                ))
            else:
                support_returned.append(self._rules_remove_field_item(
                    item, item.get("ownerId"), "hand", "top"
                ))
        if support_returned:
            result["supportReturned"] = support_returned
        if result.get("stalemate"):
            moved = []
            for item in list(self.battlefield):
                if item.get("id") not in participant_ids:
                    continue
                if item.get("isCopy") or item.get("isTokenCard"):
                    moved.append(self._rules_remove_field_item(item, item.get("ownerId"), "exile", "top"))
                else:
                    item["fieldZone"] = "stalemate"
                    # Stalemate's explicit rule preserves controller and modifiers.
                    moved.append({"status": "stalemate", "itemId": item["id"], "cardId": item.get("cardId")})
            result["returned"] = moved
            result["status"] = "complete"
            self.prune_rules_ongoing_effects()
            return result

        winner_id = result.get("winnerId")
        loser_id = result.get("loserId")
        rematch = self.rules_engine.get("rematchPending") or {}
        rematch_item_ids = set(
            rematch.get("protectedItemIds") or []
            if int(rematch.get("turn") or 0) == self.phase_tracker["turn"]
            else []
        )
        captured = []
        support_exiled = []
        support_resolved = []
        # Card-specific victory destinations precede ordinary owner-based capture.
        # Use the comparison snapshot: later control changes cannot change who won.
        for item in list(self.rules_confrontation_items()):
            if (
                not self.rules_item_confrontation_outcome(item, result, won=True)
                or item.get("id") in rematch_item_ids
                or self.rules_item_zone_locked(item)
                or int(item.get("holdUntilResolution") or 0) > self.phase_tracker["turn"]
                or self.rules_stalemate_win_blocked(item)
            ):
                continue
            win_exile_memory = next((
                memory for memory in self.rules_effect_memories_for(
                    item.get("ownerId"), item.get("cardId"),
                    "win_destination_exile",
                )
                if (memory.get("data") or {}).get("itemId") == item.get("id")
            ), None)
            if win_exile_memory:
                support_exiled.append(self._rules_remove_field_item(
                    item, item.get("ownerId"), "exile", "top"
                ))
                continue
            if (
                loser_id in self.players
                and self.rules_item_effects_active(item)
                and not item.get("isCopy") and not item.get("isTokenCard")
                and any(
                    passive.get("kind") == "win_to_opponent_interzone"
                    for passive in self.rules_item_card_rules(item).get(
                        "passiveEffects"
                    ) or []
                )
            ):
                if self.rules_interzone_slot_count(loser_id) >= self.rules_interzone_capacity(loser_id):
                    anchor = self.rules_interzone_share_anchor(loser_id, item)
                    item.update({
                        "stackedOn": anchor, "stackOffsetX": 18.0, "stackOffsetY": 18.0,
                    } if anchor else {"stackedOn": None})
                else:
                    item["stackedOn"] = None
                item["controllerId"] = loser_id
                item["fieldZone"] = "interzone"
                item["isSupport"] = False
                self.mark_rules_interzone_entry(item)
                support_resolved.append({
                    "kind": "win_to_opponent_interzone", "cardId": item.get("cardId"),
                    "itemId": item.get("id"), "playerId": loser_id,
                })
                continue
            if not item.get("isSupport"):
                continue
            support_effect = item.get("supportWinEffect") or {}
            if support_effect.get("kind") == "opponent_vessel_score" and loser_id in self.players:
                movement = self._rules_remove_field_item(item, loser_id, "receptacle", "top")
                delta = max(0, min(int(support_effect.get("value") or 0), 999))
                delta = self.adjust_rules_score(loser_id, delta)
                support_resolved.append({
                    "kind": "opponent_vessel_score", "cardId": item.get("cardId"),
                    "itemId": item.get("id"), "playerId": loser_id,
                    "delta": delta, "score": self.players[loser_id]["score"],
                    "movement": movement,
                })
            elif item.get("supportWinDestination") == "exile":
                support_exiled.append(self._rules_remove_field_item(
                    item, item.get("ownerId"), "exile", "top"
                ))
            elif item.get("supportWinDestination") == "opponent_receptacle" and loser_id in self.players:
                movement = self._rules_remove_field_item(item, loser_id, "receptacle", "top")
                support_resolved.append({
                    "kind": "opponent_vessel", "cardId": item.get("cardId"),
                    "itemId": item.get("id"), "playerId": loser_id,
                    "movement": movement,
                })
        # Loss destinations are also card effects and follow the actual outcome.
        for item in list(self.rules_confrontation_items()):
            if item.get("id") in rematch_item_ids or self.rules_item_zone_locked(item):
                continue
            if (
                self.rules_item_card_rules(item).get("lossDestination") == "winner_interzone"
                and self.rules_item_confrontation_outcome(item, result, won=False)
                and self.rules_item_effects_active(item)
                and winner_id in self.players
                and not item.get("isCopy") and not item.get("isTokenCard")
            ):
                if self.rules_interzone_slot_count(winner_id) >= self.rules_interzone_capacity(winner_id):
                    anchor = self.rules_interzone_share_anchor(winner_id, item)
                    item.update({
                        "stackedOn": anchor, "stackOffsetX": 18.0, "stackOffsetY": 18.0,
                    } if anchor else {"stackedOn": None})
                else:
                    item["stackedOn"] = None
                item["controllerId"] = winner_id
                item["fieldZone"] = "interzone"
                item["isSupport"] = False
                self.mark_rules_interzone_entry(item)
                captured.append({
                    "status": "moved_to_winner_interzone", "itemId": item.get("id"),
                    "cardId": item.get("cardId"), "ownerId": item.get("ownerId"),
                    "containerId": winner_id, "zone": "interzone",
                })
                continue
            if (
                self.rules_item_card_rules(item).get("lossDestination") == "own_interzone"
                and self.rules_item_confrontation_outcome(item, result, won=False)
                and self.rules_item_effects_active(item)
                and not item.get("isCopy") and not item.get("isTokenCard")
            ):
                owner_id = loser_id
                if self.rules_interzone_slot_count(owner_id) >= self.rules_interzone_capacity(owner_id):
                    anchor = self.rules_interzone_share_anchor(owner_id, item)
                    item.update({
                        "stackedOn": anchor, "stackOffsetX": 18.0, "stackOffsetY": 18.0,
                    } if anchor else {"stackedOn": None})
                else:
                    item["stackedOn"] = None
                item["fieldZone"] = "interzone"
                item["controllerId"] = owner_id
                item["isSupport"] = False
                self.mark_rules_interzone_entry(item)
                captured.append({
                    "status": "moved_to_own_interzone", "itemId": item.get("id"),
                    "cardId": item.get("cardId"), "ownerId": item.get("ownerId"),
                    "containerId": owner_id, "zone": "interzone",
                })
                continue
        # cards in Stalemate never take part in the resolution
        for item in list(self.rules_confrontation_items_owned_by(
            loser_id, ("confrontation",)
        )):
            if item.get("id") in rematch_item_ids or self.rules_item_zone_locked(item):
                continue
            captured.append(self._rules_remove_field_item(item, winner_id, "receptacle", "top"))
        # The Stalemate Zone is settled by the first confrontation with a winner
        # (FAQ "How is a Stalemate resolved?"): the winner takes the opponent's
        # waiting Manifestations into their Vessel and places their own like
        # winning cards. They are neither winners nor losers, so no win or loss
        # effect triggers. Cards an effect locked there this turn stay.
        stalemate_own = []
        if winner_id in self.players:
            for item in list(self.battlefield):
                if self.rules_field_zone(item) != "stalemate" or self.rules_item_zone_locked(item):
                    continue
                if item.get("ownerId") == winner_id:
                    if not self.rules_stalemate_win_blocked(item):
                        stalemate_own.append(item)
                    continue
                movement = self._rules_remove_field_item(
                    item, winner_id,
                    "exile" if item.get("isCopy") or item.get("isTokenCard") else "receptacle",
                    "top",
                )
                movement["fromStalemate"] = True
                captured.append(movement)
        own_items = [
            item for item in self.rules_confrontation_items_owned_by(
                winner_id, ("confrontation",)
            )
            if item.get("id") not in rematch_item_ids
            and not self.rules_item_zone_locked(item)
            and int(item.get("holdUntilResolution") or 0) <= self.phase_tracker["turn"]
            and not self.rules_stalemate_win_blocked(item)
        ]
        for held_item in self.battlefield:
            if int(held_item.get("holdUntilResolution") or 0) == self.phase_tracker["turn"]:
                held_item.pop("holdUntilResolution", None)
        result["captured"] = captured
        result["supportExiled"] = support_exiled
        result["supportResolved"] = support_resolved
        # Inspired Nimbus & co.: cards captured into a Vessel trigger their own
        # "enters an Empathic Vessel" abilities, and Vessel watchers react now.
        vessel_triggers = []
        for movement in captured + [
            entry.get("movement") or {} for entry in support_resolved
        ]:
            if movement.get("status") == "moved" and movement.get("zone") == "receptacle":
                vessel_triggers.extend(self.queue_rules_zone_entry_triggers(
                    movement.get("cardId"), movement.get("ownerId"),
                    movement.get("containerId"), "receptacle", defer=True,
                ))
        vessel_triggers.extend(self.queue_rules_observed_event_triggers(defer=True))
        if vessel_triggers:
            self.queue_or_defer_rules_simultaneous_actions(vessel_triggers)
            result["triggeredActions"] = vessel_triggers
        result["rematchItemIds"] = list(rematch_item_ids)
        persist_candidates = [
            item for item in own_items if self.rules_item_has_persist(item)
        ]
        own_items.extend(stalemate_own)
        result["stalemateWonItemIds"] = [item["id"] for item in stalemate_own]
        result["persisted"] = []
        if len(persist_candidates) == 1:
            persisted = persist_candidates[0]
            result["persisted"].append(
                self._mark_rules_persisted_first(persisted, winner_id)
            )
            own_items.remove(persisted)
        elif len(persist_candidates) > 1:
            result["pendingOwnItemIds"] = [
                item["id"] for item in own_items if item not in persist_candidates
            ]
            choice = {
                "id": new_id(),
                "kind": "persist_first_manifestation",
                "playerId": winner_id,
                "candidateItemIds": [item["id"] for item in persist_candidates],
            }
            self.rules_engine["pendingChoice"] = choice
            result["status"] = "cleanup_choice"
            self.prune_rules_ongoing_effects()
            return result
        result["pendingOwnItemIds"] = [item["id"] for item in own_items]
        result["status"] = "cleanup"
        self.prune_rules_ongoing_effects()
        self._queue_next_rules_confrontation_destination()
        return result

    def reset_rules_confrontation_turn(self):
        persisted_firsts = [
            item for item in self.battlefield
            if item.get("persistedFirst")
            and self.rules_field_zone(item) == "confrontation"
        ]
        first_ids = {}
        for item in persisted_firsts:
            controller_id = item.get("controllerId") or item.get("ownerId")
            if controller_id in self.players:
                first_ids[controller_id] = item["id"]
        self.rules_engine["firstManifestationItemIds"] = first_ids
        self.rules_engine["firstManifestationValidatedPlayerIds"] = list(first_ids)
        self.rules_engine["firstManifestationComplete"] = bool(
            len(first_ids) >= NUM_SEATS
        )
        self.rules_engine["firstManifestationTriggersQueued"] = False
        self.rules_engine["trapPlayerIds"] = []
        self.flush_rules_traps()
        self.rules_engine["confrontationEntrySequence"] = max(
            (
                int(item.get("confrontationOrder") or 0)
                for item in self.rules_confrontation_items()
            ),
            default=0,
        )
        self.rules_engine["confrontationResult"] = None
        self.rules_engine["forcedConfrontationWinnerId"] = None
        self.rules_engine["forcedConfrontationStalemate"] = False

    def ready_rules_exhausted_cards(self):
        """Return exhausted battlefield cards to their upright orientation."""
        readied_item_ids = []
        for item in self.battlefield:
            rotation = float(item.get("rotation") or 0)
            if int(round(rotation)) % 180 == 0:
                continue
            item["rotation"] = 0.0
            readied_item_ids.append(item["id"])
        return readied_item_ids

    def rules_persistent_wills_as_ephemeral(self, player_id):
        return any(
            self.rules_item_controller_id(item) == player_id
            and self.rules_field_zone(item) == "interzone"
            for item in self.rules_active_passive_sources("persistent_wills_as_ephemeral")
        )
