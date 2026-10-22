"""Card-specific effect results that do not fit a generic family."""

from ..common import ADVANCED_PHASES, RULES_WILL_TYPES, new_id


class SignatureEffectsMixin:
    def _rules_result_flower_of_evil_burst(self, action, result, player_id, player):
        owner_id = action.get("controllerId") or player_id
        gained = {}
        for pid in self.players:
            if pid != owner_id:
                gained[pid] = self.adjust_rules_score(pid, 5)
        self.add_rules_excess_essence(
            owner_id, [{"temperament": "transcendent", "amount": 1}]
        )
        return {
            "kind": result.get("kind"), "status": "resolved",
            "opponentGains": gained, "essences": 1,
        }

    def _rules_result_extortionist_womb(self, action, result, player_id, player):
        opponents = [pid for pid in self.players if pid != player_id]
        if not opponents:
            return {"kind": result.get("kind"), "status": "no_opponent"}
        chooser_id = opponents[0]
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "binary_choice", "purpose": "womb_show",
            "playerId": chooser_id, "options": ["yes", "no"],
            "headingKey": "rulesWombHeading", "textKey": "rulesWombText",
            "yesKey": "rulesWombYes", "noKey": "rulesWombNo",
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "relatedCardId": (action.get("source") or {}).get("cardId"),
            "controllerId": player_id, "actionId": action.get("id"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "binary_choice", "playerId": chooser_id,
        }

    def _rules_result_obelisk_gift(self, action, result, player_id, player):
        opponents = [pid for pid in self.players if pid != player_id]
        hand = player["zones"]["hand"]
        if not opponents or not any(self.card_rules.get(c, {}).get("type") == "manifestation" for c in hand):
            return {"kind": result.get("kind"), "status": "no_hand_card"}
        if not action.get("optionalAccepted"):
            return {"kind": result.get("kind"), "status": "declined"}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "discard_from_hand",
            "playerId": player_id, "count": 1, "requireManifestation": True,
            "destination": "obelisk_gift", "chooserId": opponents[0],
            "actionId": action.get("id"),
            "controllerId": action.get("controllerId"),
            "sourceCardId": (action.get("source") or {}).get("cardId"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "discard_from_hand", "playerId": player_id,
            "count": 1, "requireManifestation": True,
        }

    def _rules_result_slumberer_wakes(self, action, result, player_id, player):
        host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
        if host is None or int((host.get("counters") or {}).get("Sleep") or 0) > 0:
            return {"kind": result.get("kind"), "status": "still_asleep"}
        host["gainsPersist"] = True
        if not self.rules_item_becomes_first_manifestation(host, player_id):
            return {"kind": result.get("kind"), "status": "no_first_slot"}
        return {
            "kind": result.get("kind"), "status": "first_manifestation",
            "itemId": host["id"], "cardId": host.get("cardId"),
        }

    def _rules_result_grimoire_place(self, action, result, player_id, player):
        host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
        hand = player["zones"]["hand"]
        wills = [c for c in hand if self.card_rules.get(c, {}).get("type") in RULES_WILL_TYPES]
        if host is None or not wills:
            return {"kind": result.get("kind"), "status": "no_hand_card"}
        if not action.get("optionalAccepted"):
            return {"kind": result.get("kind"), "status": "declined"}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "discard_from_hand",
            "playerId": player_id, "count": len(wills), "upTo": True,
            "requireTypes": sorted(RULES_WILL_TYPES),
            "destination": "attach_to_source", "sourceItemId": host["id"],
            "actionId": action.get("id"),
            "controllerId": action.get("controllerId"),
            "sourceCardId": (action.get("source") or {}).get("cardId"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "discard_from_hand", "playerId": player_id,
            "count": len(wills), "upTo": True, "requireTypes": sorted(RULES_WILL_TYPES),
        }

    def _rules_result_bullyboo_reveal(self, action, result, player_id, player):
        hand = player["zones"]["hand"]
        if not any(self.card_rules.get(c, {}).get("type") in RULES_WILL_TYPES for c in hand):
            return {"kind": result.get("kind"), "status": "no_hand_card"}
        if not action.get("optionalAccepted"):
            return {"kind": result.get("kind"), "status": "declined"}
        opponents = [pid for pid in self.players if pid != player_id]
        if not opponents:
            return {"kind": result.get("kind"), "status": "no_opponent"}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "discard_from_hand",
            "playerId": player_id, "count": 1,
            "requireTypes": sorted(RULES_WILL_TYPES),
            "destination": "bullyboo_reveal", "chooserId": opponents[0],
            "actionId": action.get("id"),
            "controllerId": action.get("controllerId"),
            "sourceCardId": (action.get("source") or {}).get("cardId"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "discard_from_hand", "playerId": player_id,
            "count": 1, "requireTypes": sorted(RULES_WILL_TYPES),
        }

    def _rules_result_amphora_offer(self, action, result, player_id, player):
        hand = player["zones"]["hand"]
        if sum(1 for c in hand if self.card_rules.get(c, {}).get("type") == "manifestation") < 2:
            return {"kind": result.get("kind"), "status": "no_hand_card"}
        if not action.get("optionalAccepted"):
            return {"kind": result.get("kind"), "status": "declined"}
        opponents = [pid for pid in self.players if pid != player_id]
        if not opponents:
            return {"kind": result.get("kind"), "status": "no_opponent"}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "discard_from_hand",
            "playerId": player_id, "count": 2, "requireManifestation": True,
            "destination": "amphora_offer", "chooserId": opponents[0],
            "actionId": action.get("id"),
            "controllerId": action.get("controllerId"),
            "sourceCardId": (action.get("source") or {}).get("cardId"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "discard_from_hand", "playerId": player_id,
            "count": 2, "requireManifestation": True,
        }

    def _rules_result_tebebe_unearth(self, action, result, player_id, player):
        host_id = (action.get("source") or {}).get("itemId")
        sacrificed = []
        for item in list(self.rules_confrontation_items(player_id, ("interzone",))):
            if item.get("id") == host_id:
                continue
            if self.card_rules.get(item.get("cardId"), {}).get("type") != "manifestation":
                continue
            movement = self._rules_remove_field_item_by_effect(
                item, item.get("ownerId"), "graveyard", "top", reason="sacrifice",
            )
            if movement.get("status") in {"moved", "removed_copy"}:
                sacrificed.append(item["id"])
        seat = self.players[player_id].get("seat")
        concealed = []
        deck = self.players[player_id]["zones"]["deck"]
        for card_id in list(deck[:3]):
            self.take_zone_card(player_id, "deck", card_id)
            new_item = {
                "id": new_id(), "ownerId": player_id, "controllerId": player_id,
                "cardId": card_id, "x": 740.0, "y": 800.0 if seat != 1 else 525.0,
                "faceUp": False, "rotation": 0.0, "counters": {}, "stackedOn": None,
                "fieldZone": "field", "concealedWill": True, "tebebeConcealed": True,
            }
            self.battlefield.append(new_item)
            concealed.append(new_item["id"])
        self.prune_rules_ongoing_effects()
        return {
            "kind": result.get("kind"), "status": "unearthed",
            "sacrificed": sacrificed, "concealedItemIds": concealed,
        }

    def _rules_result_spite_upkeep(self, action, result, player_id, player):
        host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
        if host is None or self.rules_field_zone(host) != "stalemate":
            return {"kind": result.get("kind"), "status": "source_missing"}
        counters = host.setdefault("counters", {})
        key = next((k for k in counters if str(k).casefold() == "spite"), "Spite")
        counters[key] = int(counters.get(key) or 0) + 1
        payer_id = self.rules_item_controller_id(host)
        opponent_id = self.other_rules_player_id(payer_id)
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "effect_payment", "playerId": payer_id,
            "payment": "{H}" * counters[key],
            "requirements": self.rules_requirements_from_symbols("{H}" * counters[key]),
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "targetCardId": (action.get("source") or {}).get("cardId"),
            "onDecline": {
                "kind": "to_opponent_vessel", "itemId": host["id"],
                "opponentId": opponent_id,
            },
            "actionId": action.get("id"),
            "controllerId": action.get("controllerId"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "effect_payment", "playerId": payer_id,
            "payment": "{H}" * counters[key],
        }

    def _rules_result_persuasion_force(self, action, result, player_id, player):
        host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
        opponent_id = self.other_rules_player_id(player_id)
        wills = [
            c for c in self.players[opponent_id]["zones"]["hand"]
            if self.card_rules.get(c, {}).get("type") in RULES_WILL_TYPES
        ]
        if host is None or not wills:
            return {"kind": result.get("kind"), "status": "no_hand_will"}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "discard_from_hand",
            "playerId": opponent_id, "count": 1, "requireTypes": sorted(RULES_WILL_TYPES),
            "destination": "persuasion_place", "hostItemId": host["id"],
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "actionId": action.get("id"), "controllerId": action.get("controllerId"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "discard_from_hand", "playerId": opponent_id, "count": 1,
        }

    def _rules_result_persuasion_penalty(self, action, result, player_id, player):
        host_id = (action.get("source") or {}).get("itemId")
        remaining = [
            item for item in self.battlefield
            if item.get("persuaded") and item.get("persuadedBy") == host_id
        ]
        lost = {}
        for item in remaining:
            owner_id = self.rules_item_controller_id(item)
            lost[owner_id] = lost.get(owner_id, 0) + 5
        deltas = {pid: self.adjust_rules_score(pid, -amount) for pid, amount in lost.items()}
        return {"kind": result.get("kind"), "status": "resolved" if deltas else "nothing", "deltas": deltas}

    def _rules_result_lunar_liturgy(self, action, result, player_id, player):
        host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
        if host is None:
            return {"kind": result.get("kind"), "status": "source_missing"}
        if not self.rules_lunar_entries(player_id):
            self.rules_engine["skipEndPhaseTurn"] = self.phase_tracker["turn"]
            movement = self._rules_remove_field_item_by_effect(
                host, host.get("ownerId"), "graveyard", "top", reason="destroy",
            )
            return {"kind": result.get("kind"), "status": "destroyed", "movement": movement}
        order = [player_id] + [pid for pid in self.players if pid != player_id]
        choice_id = self.rules_lunar_next(
            host["id"], player_id, order,
            (action.get("source") or {}).get("cardId"), action.get("id"),
        )
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "reveal_hand_discard",
            "playerId": self.rules_engine["pendingChoice"]["playerId"],
        }

    def _rules_result_thoughtcutter_surge(self, action, result, player_id, player):
        host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
        count = sum(
            1 for entry in self.rules_engine.get("actionStack") or []
            if entry.get("controllerId") != player_id and entry.get("id") != action.get("id")
        )
        if host is None or count <= 0:
            return {"kind": result.get("kind"), "status": "nothing", "value": 0}
        self.create_rules_ongoing_effects({
            **action,
            "targets": [{"kind": "card", "itemId": host["id"], "cardId": host.get("cardId"), "ownerId": host.get("ownerId")}],
            "ability": {
                "id": f'{(action.get("ability") or {}).get("id")}:surge',
                "ongoingEffect": {"kind": "power_modifier", "value": count, "duration": "until_end_of_turn"},
            },
        })
        return {"kind": result.get("kind"), "status": "surged", "value": count}

    def _rules_result_pescojolero_trade(self, action, result, player_id, player):
        opponents = [pid for pid in self.players if pid != player_id]
        if not opponents:
            return {"kind": result.get("kind"), "status": "target_missing"}
        opponent_id = opponents[0]
        points_of = lambda card: int((self.card_points or {}).get(card, 0) or 0)
        moved_points = 0
        moved = []
        for entry in action.get("targets") or []:
            item = self.find_battlefield_item(entry.get("itemId"))
            if (
                item is None or self.rules_field_zone(item) != "stalemate"
                or item.get("ownerId") == opponent_id
                or self.card_rules.get(item.get("cardId"), {}).get("type") != "manifestation"
            ):
                continue
            movement = self._rules_remove_field_item_by_effect(
                item, opponent_id, "receptacle", "top", reason="vessel",
            )
            if movement.get("status") == "moved":
                moved_points += points_of(item.get("cardId"))
                moved.append(item.get("cardId"))
        if not moved:
            return {"kind": result.get("kind"), "status": "nothing_moved"}
        candidates = [
            card_id for card_id in self.players[opponent_id]["zones"]["receptacle"]
            if self.card_rules.get(card_id, {}).get("type") == "manifestation"
            and points_of(card_id) <= moved_points
        ]
        if not candidates:
            return {"kind": result.get("kind"), "status": "moved_only", "cardIds": moved}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "reveal_hand_discard", "purpose": "pescojolero",
            "playerId": player_id, "targetPlayerId": opponent_id, "cardIds": candidates,
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "actionId": action.get("id"), "controllerId": action.get("controllerId"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "reveal_hand_discard", "playerId": player_id,
        }

    def _rules_result_auction_offer(self, action, result, player_id, player):
        hand = player["zones"]["hand"]
        if not any(self.card_rules.get(c, {}).get("type") == "manifestation" for c in hand):
            return {"kind": result.get("kind"), "status": "no_hand_card"}
        if not action.get("optionalAccepted"):
            return {"kind": result.get("kind"), "status": "declined"}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "discard_from_hand",
            "playerId": player_id, "count": 1, "requireManifestation": True,
            "destination": "auction_bid",
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "actionId": action.get("id"), "controllerId": action.get("controllerId"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "discard_from_hand", "playerId": player_id, "count": 1,
        }

    def _rules_result_chabak_wins(self, action, result, player_id, player):
        host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
        if host is None:
            return {"kind": result.get("kind"), "status": "source_missing"}
        returned = []
        for item in list(self.battlefield):
            if (
                self.rules_field_zone(item) != "confrontation"
                or self.rules_item_controller_id(item) == player_id
                or self.card_rules.get(item.get("cardId"), {}).get("type") != "manifestation"
            ):
                continue
            movement = self._rules_remove_field_item_by_effect(
                item, item.get("ownerId"), "deck", "bottom", reason="deck",
            )
            if movement.get("status") in {"moved", "removed_copy"}:
                returned.append(item.get("cardId"))
        exiled = self._rules_remove_field_item_by_effect(
            host, host.get("ownerId"), "exile", "top", reason="exile",
        )
        return {"kind": result.get("kind"), "status": "returned", "cardIds": returned, "movement": exiled}

    def _rules_result_paciphint_swap(self, action, result, player_id, player):
        cards = [entry for entry in action.get("targets") or [] if entry.get("kind") == "card"]
        if len(cards) != 2:
            return {"kind": result.get("kind"), "status": "target_missing"}
        mine = self.find_battlefield_item(cards[0].get("itemId"))
        other = self.find_battlefield_item(cards[1].get("itemId"))
        if mine is None or self.rules_item_controller_id(mine) != player_id:
            return {"kind": result.get("kind"), "status": "target_missing"}
        movement = self._rules_remove_field_item_by_effect(
            mine, mine.get("ownerId"), "deck", "bottom", reason="deck",
        )
        if movement.get("status") != "moved" or other is None:
            return {"kind": result.get("kind"), "status": movement.get("status"), "movement": movement}
        self.create_rules_ongoing_effects({
            **action,
            "targets": [{
                "kind": "card", "itemId": other["id"], "cardId": other.get("cardId"),
                "ownerId": other.get("ownerId"),
            }],
            "ability": {
                "id": f'{(action.get("ability") or {}).get("id")}:ignored',
                "ongoingEffect": {"kind": "power_ignored", "duration": "until_end_of_turn"},
            },
        })
        return {
            "kind": result.get("kind"), "status": "swapped",
            "movement": movement, "ignoredItemId": other["id"],
        }

    def _rules_result_consul_wins(self, action, result, player_id, player):
        # Moaning Consul: the other friendly Confrontation Manifestations trigger as if they lost, then it goes to an opponent's Vessel.
        host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
        if host is None:
            return {"kind": result.get("kind"), "status": "source_missing"}
        participant_ids = set((self.rules_engine.get("confrontationResult") or {}).get("participantItemIds") or [])
        queued = []
        for item in list(self.battlefield):
            if (
                item is host or item.get("id") not in participant_ids
                or self.rules_item_controller_id(item) != player_id
                or not self.rules_item_effects_active(item)
            ):
                continue
            queued.extend(self.queue_rules_triggers(
                item.get("cardId"), item.get("ownerId"), "loses_confrontation",
                item_id=item.get("id"), face_up=True, event_controller_id=player_id,
                defer=True, controller_id=player_id,
            ))
        if queued:
            self.queue_rules_simultaneous_actions(queued)
        opponent_id = self.other_rules_player_id(player_id)
        movement = self._rules_remove_field_item_by_effect(
            host, opponent_id, "receptacle", "top", reason="vessel",
        )
        return {
            "kind": result.get("kind"), "status": movement.get("status"),
            "triggered": len(queued), "movement": movement,
        }

    def _rules_result_healing_bond(self, action, result, player_id, player):
        firsts = {}
        for pid, item_id in (self.rules_engine.get("firstManifestationItemIds") or {}).items():
            item = self.find_battlefield_item(item_id)
            if item is not None:
                firsts[pid] = item
        bases = {
            pid: self.rules_manifestation_base_power(item)
            for pid, item in firsts.items()
        }
        highest = max(bases.values()) if bases else 0
        boosted = []
        for pid, item in firsts.items():
            if bases[pid] >= highest:
                continue
            self.create_rules_ongoing_effects({
                **action,
                "targets": [{
                    "kind": "card", "itemId": item["id"], "cardId": item.get("cardId"),
                    "ownerId": item.get("ownerId"),
                }],
                "ability": {
                    "id": f'{(action.get("ability") or {}).get("id")}:bond',
                    "ongoingEffect": {
                        "kind": "power_modifier", "value": 2,
                        "duration": "until_end_of_turn",
                    },
                },
            })
            self.adjust_rules_score(pid, 10)
            boosted.append(pid)
        return {
            "kind": result.get("kind"),
            "status": "boosted" if boosted else "nothing", "playerIds": boosted,
        }

    def _rules_result_return_turn_tributes_end_turn(self, action, result, player_id, player):
        turn = self.phase_tracker["turn"]
        memories = []
        for entry in self.rules_engine.get("tributeLog") or []:
            if entry.get("turn") != turn or entry.get("playerId") != player_id:
                continue
            memory = self.create_rules_effect_memory(
                entry["ownerId"], entry["cardId"], "return_from_limbo_end_turn",
                controller_id=player_id, source_action_id=action.get("id"),
            )
            if memory:
                memories.append(entry["cardId"])
        return {"kind": result.get("kind"), "status": "scheduled" if memories else "nothing", "cardIds": memories}

    def _rules_result_hold_winner_manifestations(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "player"
        ), None)
        target_id = (target or {}).get("playerId")
        confrontation = self.rules_engine.get("confrontationResult") or {}
        if (
            target_id not in self.players
            or confrontation.get("turn") != self.phase_tracker["turn"]
            or confrontation.get("stalemate")
            or confrontation.get("winnerId") != target_id
        ):
            return {"kind": result.get("kind"), "status": "not_winner"}
        held = []
        for item in self.rules_confrontation_items_owned_by(target_id, ("confrontation",)):
            item["holdUntilResolution"] = self.phase_tracker["turn"] + 1
            held.append(item["id"])
        return {"kind": result.get("kind"), "status": "held", "itemIds": held}

    def _rules_result_force_win_if_highest_base_first(self, action, result, player_id, player):
        source_item = self.find_battlefield_item(
            (action.get("source") or {}).get("itemId")
        )
        if source_item is None:
            return {
                "kind": result.get("kind"),
                "status": "source_missing",
            }
        controller_id = self.rules_item_controller_id(source_item)
        first_ids = self.rules_engine.get("firstManifestationItemIds", {})
        first_items = [
            self.find_battlefield_item(item_id)
            for item_id in first_ids.values()
        ]
        first_items = [item for item in first_items if item]
        source_power = self.rules_manifestation_base_power(source_item)
        highest = max((
            self.rules_manifestation_base_power(item)
            for item in first_items
        ), default=source_power)
        qualifies = self.rules_is_strictly_highest_base_first(source_item)
        confrontation = None
        if qualifies:
            self.rules_engine["forcedConfrontationWinnerId"] = controller_id
            self.phase_tracker["index"] = ADVANCED_PHASES.index(
                "resolution_compare"
            )
            self.rules_engine["priorityPasses"] = []
            confrontation = self.prepare_rules_confrontation_result()
        return {
            "kind": result.get("kind"),
            "status": "forced" if qualifies else "condition_failed",
            "playerId": controller_id,
            "basePower": source_power,
            "highestBasePower": highest,
            "phaseId": self.current_phase_id(),
            "confrontationResult": confrontation,
        }

    def _rules_result_each_player_recovery_choice(self, action, result, player_id, player):
        player_ids = [
            entry["id"] for entry in sorted(
                self.players.values(), key=lambda entry: entry.get("seat", 0)
            )
        ]
        choice = self._set_next_rules_recovery_choice(player_ids, action)
        if choice is None:
            return None
        return {
            "kind": "choice_required",
            "choiceId": choice["id"],
            "choiceKind": choice["kind"],
            "playerId": choice["playerId"],
            "options": list(choice["options"]),
        }

    def _rules_result_disable_source_effects(self, action, result, player_id, player):
        source_item = self.find_battlefield_item(
            (action.get("source") or {}).get("itemId")
        )
        if source_item is None:
            return {"kind": result.get("kind"), "status": "source_missing"}
        source_item["effectsDisabled"] = True
        self.prune_rules_ongoing_effects()
        return {
            "kind": result.get("kind"), "status": "disabled",
            "itemId": source_item["id"], "cardId": source_item.get("cardId"),
        }

    def _rules_result_clemency_choice(self, action, result, player_id, player):
        trigger = (action.get("ability") or {}).get("trigger") or {}
        chooser_id = trigger.get("eventControllerId")
        gain = int(result.get("value") or 0)
        if chooser_id not in self.players:
            delta = self.adjust_rules_score(player_id, gain)
            return {"kind": result.get("kind"), "status": "gained", "delta": delta}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "clemency_choice", "playerId": chooser_id,
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "sourceItemId": (action.get("source") or {}).get("itemId"),
            "sourceControllerId": action.get("controllerId"),
            "relatedActionId": trigger.get("relatedActionId"),
            "relatedCardId": trigger.get("relatedCardId"),
            "points": gain, "options": ["allow", "neutralize"],
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "clemency_choice", "playerId": chooser_id,
            "points": gain,
        }
