"""Effect results that draw, discard, search or reorder cards in decks, hands and Limbos."""

import random

from ..common import ADVANCED_PHASES, RULES_WILL_TYPES, RULES_TEMPERAMENTS, new_id


class CardsEffectsMixin:
    def _rules_result_shuffle_owner_deck(self, action, result, player_id, player):
        random.shuffle(player["zones"]["deck"])
        return {
            "kind": result.get("kind"),
            "status": "shuffled",
            "playerId": player_id,
            "count": len(player["zones"]["deck"]),
        }

    def _rules_result_destroy_support_targets_draw(self, action, result, player_id, player):
        draws = {}
        destroyed = []
        for target in action.get("targets") or []:
            item = self.find_battlefield_item(target.get("itemId"))
            if item is None or not item.get("isSupport"):
                continue
            controller_id = self.rules_item_controller_id(item)
            movement = self._rules_remove_field_item_by_effect(
                item, item.get("ownerId"), "graveyard", "top", reason="destroy"
            )
            if movement.get("status") in {"moved", "removed_copy"}:
                destroyed.append(item["id"])
                draws[controller_id] = draws.get(controller_id, 0) + 2
        self.prune_rules_ongoing_effects()
        for pid, count in draws.items():
            self.draw_rules_cards(pid, count)
        return {
            "kind": result.get("kind"),
            "status": "destroyed" if destroyed else "nothing",
            "itemIds": destroyed, "draws": draws,
        }

    def _rules_result_mill_deck_per_confrontation_manifestation(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "player"
        ), None)
        target_id = (target or {}).get("playerId")
        if target_id not in self.players:
            return {"kind": result.get("kind"), "status": "target_missing"}
        count = len([
            item for item in self.rules_confrontation_items(target_id, ("confrontation",))
            if not item.get("isTokenCard") and not item.get("isTokenCopy")
        ])
        for _index in range(count):
            deck = self.players[target_id]["zones"]["deck"]
            if not deck:
                break
            error, _owner, replacement = self.move_zone_card_by_effect(
                target_id, "deck", target_id, "graveyard", deck[0], "top"
            )
            if error:
                break
        return {
            "kind": result.get("kind"),
            "status": "discarded" if count else "nothing",
            "count": count, "targetPlayerId": target_id,
        }

    def _rules_result_exile_source_then_shuffle_limbo_and_interzone(self, action, result, player_id, player):
        source = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
        if source is not None:
            self._rules_remove_field_item(source, source.get("ownerId"), "exile", "top")
        moved = []
        for item in list(self.rules_confrontation_items(zones=("interzone",))):
            movement = self._rules_remove_field_item(
                item, item.get("ownerId"), "deck", "top"
            )
            if movement.get("status") == "moved":
                moved.append(item.get("cardId"))
        for pid in self.players:
            for card_id in list(self.players[pid]["zones"]["graveyard"]):
                error, _owner, replacement = self.move_zone_card_by_effect(
                    pid, "graveyard", pid, "deck", card_id, "top"
                )
                if not error and not replacement:
                    moved.append(card_id)
        for pid in self.players:
            random.shuffle(self.players[pid]["zones"]["deck"])
        self.prune_rules_ongoing_effects()
        return {"kind": result.get("kind"), "status": "shuffled", "cardIds": moved}

    def _rules_result_timidette_support_to_deck_bottom(self, action, result, player_id, player):
        source_id = (action.get("source") or {}).get("itemId")
        kept = {source_id} | {
            entry.get("itemId") for entry in action.get("targets") or []
            if entry.get("kind") == "card"
        }
        groups = []
        for owner_id in self.players:
            item_ids = [item["id"] for item in self.battlefield
                        if item.get("isSupport") and item.get("id") not in kept
                        and item.get("faceUp", True) and item.get("ownerId") == owner_id]
            if item_ids:
                # "In any order": Timidette's controller orders each owner's Deck.
                groups.append({"controllerId": player_id, "itemIds": item_ids})
        continuation = self._continue_rules_support_return_groups(
            groups, {}, action, position="bottom", boost_firsts=False,
        )
        if continuation.get("kind") == "support_return_order":
            return {"kind": "choice_required", "choiceId": continuation["id"],
                    "choiceKind": "support_return_order", "playerId": player_id}
        return {"kind": result.get("kind"), "status": "resolved", **continuation}

    def _rules_result_optional_discard_up_to(self, action, result, player_id, player):
        hand = player["zones"]["hand"]
        if not hand:
            return {"kind": result.get("kind"), "status": "no_hand_card"}
        if not action.get("optionalAccepted"):
            return {"kind": result.get("kind"), "status": "declined"}
        count = min(int(result.get("value") or 1), len(hand))
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "discard_from_hand",
            "playerId": player_id, "count": count, "upTo": True,
            "actionId": action.get("id"),
            "controllerId": action.get("controllerId"),
            "sourceCardId": (action.get("source") or {}).get("cardId"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "discard_from_hand", "playerId": player_id,
            "count": count, "upTo": True,
        }

    def _rules_result_return_source_to_hand_restricted(self, action, result, player_id, player):
        source_item = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
        if source_item is None:
            return {"kind": result.get("kind"), "status": "source_missing"}
        movement = self._rules_remove_field_item_by_effect(
            source_item, source_item.get("ownerId"), "hand", "top", reason="return"
        )
        if movement.get("status") == "moved":
            self.rules_engine["playRestrictions"].append({
                "id": new_id(), "playerId": source_item["ownerId"],
                "cardId": source_item["cardId"], "turn": self.phase_tracker["turn"],
                "sourceActionId": action.get("id"),
            })
        self.prune_rules_ongoing_effects()
        return {
            "kind": result.get("kind"), "status": movement.get("status"),
            "cardId": source_item.get("cardId"), "playRestrictedUntilTurnEnd": True,
        }

    def _rules_result_chain_discarded_manifestation_from_target_deck(self, action, result, player_id, player):
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
        error, chained = self.chain_rules_manifestation(
            player_id, "deck", found, container_id=target_id,
            action_id=action.get("id"),
            source_card_id=(action.get("source") or {}).get("cardId"),
            chain_controller_id=player_id,
        )
        if error:
            return {
                "kind": result.get("kind"), "status": "blocked",
                "error": error, "discarded": discarded, "cardId": found,
            }
        return {
            "kind": result.get("kind"), "status": "chained",
            "cardId": found, "discarded": discarded,
            "targetPlayerId": target_id,
            **({"chain": chained} if isinstance(chained, dict) else {}),
        }

    def _rules_result_discard_any_then_lose_per_remaining(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "player"
        ), None)
        target_id = (target or {}).get("playerId")
        if target_id not in self.players:
            return {"kind": result.get("kind"), "status": "target_missing"}
        if self.rules_hand_is_immune(target_id, player_id):
            return {"kind": result.get("kind"), "status": "prevented_immunity"}
        hand = self.players[target_id]["zones"]["hand"]
        if not hand:
            return {"kind": result.get("kind"), "status": "no_hand_card"}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "discard_from_hand",
            "playerId": target_id, "count": len(hand), "upTo": True,
            "lossPerRemaining": 5,
            "actionId": action.get("id"),
            "controllerId": action.get("controllerId"),
            "sourceCardId": (action.get("source") or {}).get("cardId"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "discard_from_hand", "playerId": target_id,
            "count": len(hand), "upTo": True,
        }

    def _rules_result_choose_hand_will_as_support_manifestation(self, action, result, player_id, player):
        if self.rules_support_entry_locked(player_id):
            return {"kind": result.get("kind"), "status": "prevented"}
        hand = player["zones"]["hand"]
        if not any(self.card_rules.get(c, {}).get("type") in RULES_WILL_TYPES for c in hand):
            return {"kind": result.get("kind"), "status": "no_hand_card"}
        if not action.get("optionalAccepted"):
            return {"kind": result.get("kind"), "status": "declined"}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "discard_from_hand",
            "playerId": player_id, "count": 1,
            "requireTypes": sorted(RULES_WILL_TYPES),
            "destination": "support_manifestation",
            "actionId": action.get("id"),
            "controllerId": action.get("controllerId"),
            "sourceCardId": (action.get("source") or {}).get("cardId"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "discard_from_hand", "playerId": player_id,
            "count": 1, "requireTypes": sorted(RULES_WILL_TYPES),
        }

    def _rules_result_peek_top_swap(self, action, result, player_id, player):
        deck = player["zones"]["deck"]
        if not deck:
            return {"kind": result.get("kind"), "status": "empty_deck"}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "peek_top_card", "playerId": player_id,
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "cardId": deck[0], "_cardId": deck[0], "allowSwap": True,
            "handCardIds": list(player["zones"]["hand"]),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "peek_top_card", "playerId": player_id,
        }

    def _rules_result_return_other_limbo_card_to_hand(self, action, result, player_id, player):
        source_card = (action.get("source") or {}).get("cardId")
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "zone_card" and entry.get("cardId") != source_card
        ), None)
        if target is None:
            return {"kind": result.get("kind"), "status": "target_missing"}
        error, _owner, replacement = self.move_zone_card_by_effect(
            target.get("containerId"), "graveyard", target.get("containerId"),
            "hand", target.get("cardId"), "top",
        )
        return {
            "kind": result.get("kind"),
            "status": "error" if error else "returned",
            "cardId": target.get("cardId"),
        }

    def _rules_result_shuffle_limbo_targets_into_deck(self, action, result, player_id, player):
        source_card = (action.get("source") or {}).get("cardId")
        moved = []
        for target in action.get("targets") or []:
            if target.get("kind") != "zone_card" or target.get("cardId") == source_card:
                continue
            error, owner_id, replacement = self.move_zone_card_by_effect(
                target.get("containerId"), "graveyard", target.get("containerId"),
                "deck", target.get("cardId"), "top",
            )
            if not error and not replacement:
                moved.append(target.get("cardId"))
        for pid in {t.get("containerId") for t in action.get("targets") or []}:
            if pid in self.players:
                random.shuffle(self.players[pid]["zones"]["deck"])
        return {
            "kind": result.get("kind"),
            "status": "shuffled" if moved else "nothing", "cardIds": moved,
        }

    def _rules_result_unless_payment_deck_discard(self, action, result, player_id, player):
        if result.get("kind") == "unless_payment_exile_source":
            host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
            if host is None:
                return {"kind": result.get("kind"), "status": "source_missing"}
            payer_id = self.rules_item_controller_id(host)
            on_decline = {"kind": "exile_source", "itemId": host["id"]}
        elif result.get("kind") == "unless_opponent_payment_lock_support_entries":
            payer_id = self.other_rules_player_id(player_id)
            on_decline = {"kind": "lock_support_entries"}
        elif result.get("kind") == "unless_payment_deck_discard":
            payer_id = (action.get("source") or {}).get("containerId")
            on_decline = {"kind": "deck_discard", "count": int(result.get("count") or 1)}
        else:
            target = next((
                entry for entry in action.get("targets") or [] if entry.get("kind") == "card"
            ), None)
            item = self.find_battlefield_item((target or {}).get("itemId"))
            if item is None:
                return {"kind": result.get("kind"), "status": "target_missing"}
            # Nullify: "unless its owner pays"
            payer_id = item.get("ownerId") or self.rules_item_controller_id(item)
            on_decline = {"kind": "lose_effects", "itemId": item["id"]}
        if payer_id not in self.players:
            return {"kind": result.get("kind"), "status": "payer_missing"}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "effect_payment", "playerId": payer_id,
            "payment": result.get("payment"),
            "requirements": self.rules_requirements_from_symbols(result.get("payment")),
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "targetCardId": (action.get("source") or {}).get("cardId"),
            "onDecline": on_decline,
            "actionId": action.get("id"),
            "controllerId": action.get("controllerId"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "effect_payment", "playerId": payer_id,
            "payment": result.get("payment"),
        }

    def _rules_result_search_deck_to_hand(self, action, result, player_id, player):
        deck = list(player["zones"]["deck"])
        if not deck:
            return {"kind": result.get("kind"), "status": "no_cards"}
        count = min(int(result.get("count") or 1), len(deck))
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "discard_from_hand",
            "playerId": player_id, "count": count, "upTo": bool(result.get("upTo")),
            "candidateCardIds": sorted(deck),
            "actionId": action.get("id"),
            "controllerId": action.get("controllerId"),
            "sourceCardId": (action.get("source") or {}).get("cardId"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "discard_from_hand", "playerId": player_id,
            "count": count, "upTo": bool(result.get("upTo")), "search": True,
        }

    def _rules_result_hand_manifestation_choice(self, action, result, player_id, player):
        if result.get("kind") == "hand_manifestation_choice" and (action.get("cost") or {}).get("revealedCard"):
            revealed = action["cost"]["revealedCard"]
            payload = {
                "kind": result.get("kind"), "status": "resolved",
                "cardId": revealed.get("cardId"), "power": revealed.get("power"),
            }
            if result.get("destroyTarget"):
                target = next((
                    entry for entry in action.get("targets") or [] if entry.get("kind") == "card"
                ), None)
                target_item = self.find_battlefield_item((target or {}).get("itemId"))
                if (
                    target_item is not None
                    and self.rules_manifestation_base_power(target_item) <= int(revealed.get("power") or 0)
                ):
                    movement = self._rules_remove_field_item_by_effect(
                        target_item, target_item.get("ownerId"), "graveyard", "top", reason="destroy"
                    )
                    self.prune_rules_ongoing_effects()
                    payload["destroyed"] = {"itemId": target_item["id"], "status": movement.get("status")}
                else:
                    payload["destroyed"] = None
            if result.get("drawByBasePower"):
                payload["drawn"] = self.draw_rules_cards(player_id, int(revealed.get("power") or 0))
            return payload
        if result.get("kind") == "hand_manifestation_choice":
            hand = player["zones"]["hand"]
            if not any(self.card_rules.get(c, {}).get("type") == "manifestation" for c in hand):
                return {"kind": result.get("kind"), "status": "no_hand_card"}
            if result.get("optional") and not action.get("optionalAccepted"):
                return {"kind": result.get("kind"), "status": "declined"}
            target = next((
                entry for entry in action.get("targets") or [] if entry.get("kind") == "card"
            ), None)
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "discard_from_hand",
                "playerId": player_id, "count": 1, "requireManifestation": True,
                "destination": result.get("destination"),
                "drawByBasePower": bool(result.get("drawByBasePower")),
                "destroyTargetItemId": (
                    (target or {}).get("itemId") if result.get("destroyTarget") else None
                ),
                "actionId": action.get("id"),
                "controllerId": action.get("controllerId"),
                "sourceCardId": (action.get("source") or {}).get("cardId"),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "discard_from_hand", "playerId": player_id,
                "count": 1, "requireManifestation": True,
            }

    def _rules_result_exile_source_card_from_limbo(self, action, result, player_id, player):
        source = action.get("source") or {}
        owner_id = source.get("ownerId") or player_id
        card_id = source.get("cardId")
        if card_id not in self.players.get(owner_id, {}).get("zones", {}).get("graveyard", []):
            return {"kind": result.get("kind"), "status": "source_missing"}
        error, _owner, _replacement = self.move_zone_card_by_effect(
            owner_id, "graveyard", owner_id, "exile", card_id, "top"
        )
        return {
            "kind": result.get("kind"),
            "status": "error" if error else "exiled", "cardId": card_id,
        }

    def _rules_result_gorlok_peek(self, action, result, player_id, player):
        host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
        opponent_id = self.other_rules_player_id(player_id)
        entry = (self.rules_engine.get("drawnOutsideRecovery") or {}).get(opponent_id) or {}
        hand = self.players[opponent_id]["zones"]["hand"]
        shown = [c for c in entry.get("cardIds") or [] if c in hand] if entry.get("turn") == self.phase_tracker["turn"] else []
        if host is None or not shown:
            return {"kind": result.get("kind"), "status": "nothing_shown"}
        self.rules_engine["drawnOutsideRecovery"].pop(opponent_id, None)
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "reveal_hand_discard", "purpose": "gorlok",
            "playerId": player_id, "targetPlayerId": opponent_id, "cardIds": shown,
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "sourceItemId": host["id"],
            "actionId": action.get("id"), "controllerId": action.get("controllerId"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "reveal_hand_discard", "playerId": player_id,
        }

    def _rules_result_exile_source_grant_limbo_will_play(self, action, result, player_id, player):
        # Nghoul-ong: exile it from the Limbo, then an Ephemeral Will of cost <= its base power is free.
        source = action.get("source") or {}
        owner_id = source.get("ownerId") or player_id
        card_id = source.get("cardId")
        if card_id not in self.players.get(owner_id, {}).get("zones", {}).get("graveyard", []):
            return {"kind": result.get("kind"), "status": "source_missing"}
        error, _owner, _replacement = self.move_zone_card_by_effect(
            owner_id, "graveyard", owner_id, "exile", card_id, "top"
        )
        if error:
            return {"kind": result.get("kind"), "status": "error"}
        max_cost = int(self.card_rules.get(card_id, {}).get("power") or 0)
        self.rules_engine["playPermissions"].append({
            "id": new_id(), "abilityId": (action.get("ability") or {}).get("id"),
            "playerId": owner_id, "anyWill": True, "fromZone": "graveyard",
            "phaseIds": list(ADVANCED_PHASES), "asSupport": False,
            "noTribute": True, "exileOnLeave": True,
            "ephemeralOnly": True, "maxCost": max_cost,
            "turn": self.phase_tracker["turn"], "sourceCardId": card_id,
        })
        return {"kind": result.get("kind"), "status": "granted", "playerId": owner_id, "maxCost": max_cost}

    def _rules_result_limbo_source_to_support(self, action, result, player_id, player):
        source = action.get("source") or {}
        owner_id = source.get("ownerId") or player_id
        card_id = source.get("cardId")
        if (
            owner_id not in self.players
            or card_id not in self.players[owner_id]["zones"]["graveyard"]
        ):
            return {"kind": result.get("kind"), "status": "source_missing"}
        self.take_zone_card(owner_id, "graveyard", card_id)
        seat = self.players[owner_id].get("seat")
        item = {
            "id": new_id(), "ownerId": owner_id, "controllerId": owner_id,
            "cardId": card_id, "x": 740.0, "y": 800.0 if seat != 1 else 525.0,
            "faceUp": True, "rotation": 0.0, "counters": {}, "stackedOn": None,
        }
        self.mark_rules_support_entry(item)
        self.battlefield.append(item)
        self.queue_rules_effect_support_entry(item)
        return {
            "kind": result.get("kind"), "status": "support",
            "cardId": card_id, "itemId": item["id"],
        }

    def _rules_result_exile_limbo_targets_create_tokens(self, action, result, player_id, player):
        exiled = []
        for target in action.get("targets") or []:
            if target.get("kind") != "zone_card":
                continue
            error, _owner, replacement = self.move_zone_card_by_effect(
                target.get("containerId"), "graveyard", target.get("containerId"),
                "exile", target.get("cardId"), "top",
            )
            if not error and not replacement:
                exiled.append(target.get("cardId"))
        source = action.get("source") or {}
        tokens = [
            self.create_rules_token_copy(
                source.get("cardId"), player_id, source_item_id=source.get("itemId"),
                effects_disabled=True, generic_power=1,
                generic_temperament="choleric",
            )["id"]
            for _index in exiled
        ]
        return {
            "kind": result.get("kind"),
            "status": "created" if tokens else "nothing",
            "cardIds": exiled, "tokens": len(tokens),
        }

    def _rules_result_shuffle_hand_into_deck_and_draw(self, action, result, player_id, player):
        player = self.players[player_id]
        for card_id in list(player["zones"]["hand"]):
            self.move_zone_card_by_effect(
                player_id, "hand", player_id, "deck", card_id, "top"
            )
        random.shuffle(player["zones"]["deck"])
        drawn = self.draw_rules_cards(player_id, 7)
        return {"kind": result.get("kind"), "status": "done", "draw": drawn}

    def _rules_result_move_source_to_owner_deck_top(self, action, result, player_id, player):
        source_item = self.find_battlefield_item(
            (action.get("source") or {}).get("itemId")
        )
        if source_item is None:
            return {
                "kind": result.get("kind"),
                "status": "source_missing",
            }
        destination = (
            "exile"
            if result.get("kind") == "move_source_to_owner_exile"
            else "deck"
        )
        movement = self._rules_remove_field_item(
            source_item, source_item.get("ownerId"), destination, "top"
        )
        self.prune_rules_ongoing_effects()
        return {
            "kind": result.get("kind"),
            "status": movement.get("status"),
            "movement": movement,
        }

    def _rules_result_play_limbo_target_as_support(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "zone_card"
        ), None)
        if target is None:
            return {
                "kind": result.get("kind"),
                "status": "target_missing",
            }
        error, owner_id, replacement = self.rules_zone_move_replacement(
            target.get("containerId"), "graveyard", "battlefield", target.get("cardId"),
        )
        if error or owner_id is None:
            return {
                "kind": result.get("kind"),
                "status": "target_missing",
            }
        if replacement:
            return {"kind": result.get("kind"), **replacement}
        owner_id = self.take_zone_card(
            target.get("containerId"), "graveyard",
            target.get("cardId"),
        )
        if owner_id is None:
            return {"kind": result.get("kind"), "status": "target_missing"}
        self.record_rules_observed_event(
            "manifestation_left_by_effect", target.get("containerId"),
            cardId=target.get("cardId"),
        )
        seat = self.players[player_id].get("seat")
        item = {
            "id": new_id(), "ownerId": owner_id,
            "controllerId": player_id,
            "cardId": target.get("cardId"),
            "x": 740.0, "y": 800.0 if seat != 1 else 525.0,
            "faceUp": True, "rotation": 0.0, "counters": {},
            "stackedOn": None,
        }
        self.mark_rules_support_entry(item)
        if result.get("winDestination") == "exile":
            item["supportWinDestination"] = "exile"
        if result.get("losesEffects"):
            item["effectsDisabled"] = True
        if result.get("exileInsteadOfLeaving"):
            item["exileInsteadOfLeaving"] = True
        self.battlefield.append(item)
        triggered = []
        if self.rules_item_effects_active(item):
            triggered.extend(self.queue_rules_battlefield_entry_triggers(
                item["cardId"], player_id, item["id"], True, defer=True,
            ))
            triggered.extend(self.queue_rules_field_zone_entry_triggers(
                item, "confrontation", defer=True,
            ))
        triggered.extend(self.queue_rules_support_entry_triggers(
            item, played=False, from_zone="graveyard", defer=True,
        ))
        triggered.extend(self.queue_rules_manifestation_entry_watchers(
            item, played=False, defer=True,
        ))
        return {
            "kind": result.get("kind"),
            "status": "moved",
            "itemId": item["id"],
            "cardId": item["cardId"],
            "ownerId": owner_id,
            "controllerId": player_id,
            "resolutionTriggers": triggered,
        }

    def _rules_result_reveal_hand_discard_choice(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "player"
        ), None)
        target_id = (target or {}).get("playerId")
        if target_id not in self.players:
            return {"kind": result.get("kind"), "status": "target_missing"}
        lost = 0
        if int(result.get("scoreCost") or 0):
            lost = -self.adjust_rules_score(
                player_id, -int(result["scoreCost"])
            )
        if self.rules_hand_is_immune(target_id, player_id):
            return {
                "kind": result.get("kind"), "status": "prevented_immunity",
                "playerId": target_id, "lost": lost,
            }
        hand = list(self.players[target_id]["zones"]["hand"])
        if not hand:
            return {
                "kind": result.get("kind"), "status": "empty_hand",
                "playerId": target_id, "lost": lost, "cardIds": [],
            }
        choice = {
            "id": new_id(), "kind": "reveal_hand_discard",
            "playerId": player_id, "targetPlayerId": target_id,
            "cardIds": hand,
            "sourceCardId": (action.get("source") or {}).get("cardId"),
        }
        self.rules_engine["pendingChoice"] = choice
        return {
            "kind": "choice_required", "choiceId": choice["id"],
            "choiceKind": "reveal_hand_discard", "playerId": player_id,
            "targetPlayerId": target_id, "lost": lost,
        }

    def _rules_result_shuffle_hands_then_draw(self, action, result, player_id, player):
        draw_count = int(result.get("value") or 0)
        moved = {}
        drawn = {}
        for current_id, current in self.players.items():
            moved[current_id] = []
            for card_id in list(current["zones"]["hand"]):
                error, _owner_id, replacement = self.move_zone_card_by_effect(
                    current_id, "hand", current_id, "deck",
                    card_id, "bottom",
                )
                if not error and not replacement:
                    moved[current_id].append(card_id)
            random.shuffle(current["zones"]["deck"])
            drawn[current_id] = 0
            for _index in range(min(draw_count, len(current["zones"]["deck"]))):
                card_id = current["zones"]["deck"][0]
                error, _owner_id, replacement = self.move_zone_card_by_effect(
                    current_id, "deck", current_id, "hand",
                    card_id, "bottom",
                )
                if error:
                    break
                if not replacement:
                    drawn[current_id] += 1
        return {
            "kind": "shuffle_hands_then_draw",
            "movedCounts": {
                current_id: len(card_ids)
                for current_id, card_ids in moved.items()
            },
            "drawn": drawn,
        }

    def _rules_result_exile_all_limbos(self, action, result, player_id, player):
        source = action.get("source") or {}
        excluded_source = (
            source.get("cardId")
            if (action.get("sourceResolution") or {}).get("destination") == "graveyard"
            else None
        )
        excluded_owner = source.get("ownerId")
        exiled = {}
        for current_id, current in self.players.items():
            exiled[current_id] = []
            skipped_source = False
            for card_id in list(current["zones"]["graveyard"]):
                if (
                    not skipped_source
                    and card_id == excluded_source
                    and current_id == excluded_owner
                ):
                    skipped_source = True
                    continue
                error, _owner_id, replacement = self.move_zone_card_by_effect(
                    current_id, "graveyard", current_id, "exile",
                    card_id, "top",
                )
                if not error and not replacement:
                    exiled[current_id].append(card_id)
        return {
            "kind": "exile_all_limbos",
            "cardIdsByPlayer": exiled,
        }

    def _rules_result_resolve_top_deck_by_type(self, action, result, player_id, player):
        if not player["zones"]["deck"]:
            return {
                "kind": "resolve_top_deck_by_type",
                "status": "deck_empty",
                "playerId": player_id,
            }
        card_id = player["zones"]["deck"][0]
        card_type = self.card_rules.get(card_id, {}).get("type")
        if (
            card_type == "manifestation"
            and result.get("manifestation") == "chain"
        ):
            error, chained = self.chain_rules_manifestation(
                player_id, "deck", card_id,
                action_id=action.get("id"),
                source_card_id=(action.get("source") or {}).get("cardId"),
            )
            if error:
                return {
                    "kind": "resolve_top_deck_by_type",
                    "status": "failed",
                    "error": error,
                    "cardId": card_id,
                }
            return {
                "kind": "resolve_top_deck_by_type",
                "status": chained.get("status"),
                "cardId": card_id,
                "cardType": card_type,
                "resolution": chained,
            }
        if card_type in RULES_WILL_TYPES and result.get("will") == "draw":
            drawn = self.draw_rules_cards(player_id, 1)
            # an uncovered Will drawn this way stays known in its owner's hand
            if drawn:
                self.mark_hand_revealed(player_id, [card_id])
            return {
                "kind": "resolve_top_deck_by_type",
                "status": "drawn" if drawn else "failed",
                "cardId": card_id,
                "cardType": card_type,
            }
        return {
            "kind": "resolve_top_deck_by_type",
            "status": "revealed_no_effect",
            "cardId": card_id,
            "cardType": card_type,
        }

    def _rules_result_reorder_top_decks(self, action, result, player_id, player):
        count = int(result.get("count") or 0)
        target_player_ids = (
            list(self.players) if result.get("eachPlayer") else [player_id]
        )
        if result.get("targetPlayer"):
            chosen = next((
                entry.get("playerId") for entry in action.get("targets") or []
                if entry.get("kind") == "player"
            ), None)
            if chosen not in self.players:
                return {"kind": "reorder_top_decks", "status": "target_missing"}
            target_player_ids = [chosen]
        groups = []
        for target_player_id in target_player_ids:
            card_ids = list(
                self.players[target_player_id]["zones"]["deck"][:count]
            )
            if card_ids:
                # Tut puts one card on the bottom, then the remaining cards on
                # top, even when fewer than three remain in the Deck.
                bottom_count = result.get("bottomCount")
                top_count = result.get("topCount")
                if bottom_count is not None:
                    bottom_count = min(int(bottom_count), len(card_ids))
                if top_count is not None:
                    top_count = min(int(top_count), len(card_ids) - (bottom_count or 0))
                groups.append({
                    "playerId": target_player_id,
                    "cardIds": card_ids,
                    "topCount": top_count,
                    "bottomCount": bottom_count,
                    **({
                        "extraSide": result["extraSide"],
                        "extraMin": int(result.get("extraMin") or 0),
                        "extraMax": int(result.get("extraMax") or 0),
                    } if result.get("extraSide") else {}),
                })
        if not groups:
            return {
                "kind": "reorder_top_decks",
                "status": "no_cards",
            }
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id,
            "kind": "deck_reorder",
            "playerId": player_id,
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "groups": groups,
            "_groups": groups,
            "_afterDraw": int(result.get("afterDraw") or 0),
            "_afterDiscard": int(result.get("afterDiscard") or 0),
        }
        if all(
            len(group["cardIds"]) == len(self.players[group["playerId"]]["zones"]["deck"]) == 1
            and not group.get("extraSide") for group in groups
        ):
            # A whole one-card Deck is identical with that card on top or on
            # the bottom. Run the usual continuation without asking to order it.
            choice = self.rules_engine["pendingChoice"]
            option = {"groups": [{
                "playerId": group["playerId"],
                "top": [] if group.get("bottomCount") else list(group["cardIds"]),
                "bottom": list(group["cardIds"]) if group.get("bottomCount") else [],
            } for group in groups]}
            error, payload = self._rules_choice_deck_reorder(
                player_id, choice_id, choice, None, option, None, None, None,
            )
            if error is None:
                return {**payload, "kind": "reorder_top_decks", "status": "automatic"}
        return {
            "kind": "choice_required",
            "choiceId": choice_id,
            "choiceKind": "deck_reorder",
            "playerId": player_id,
        }

    def _rules_result_split_targeted_limbo_cards(self, action, result, player_id, player):
        targets = [
            target for target in action.get("targets") or []
            if target.get("kind") == "zone_card"
            and target.get("zone") == "graveyard"
        ]
        if not targets:
            return {
                "kind": "split_targeted_limbo_cards",
                "status": "no_targets",
            }
        container_ids = {target.get("containerId") for target in targets}
        if len(container_ids) != 1:
            return {
                "kind": "split_targeted_limbo_cards",
                "status": "mixed_limbos",
            }
        card_ids = [target.get("cardId") for target in targets]
        choice_id = new_id()
        bottom_count = (len(card_ids) + 1) // 2
        groups = [{
            "playerId": next(iter(container_ids)),
            "cardIds": card_ids,
            "topCount": len(card_ids) - bottom_count,
            "bottomCount": bottom_count,
            "fromZone": "graveyard",
        }]
        self.rules_engine["pendingChoice"] = {
            "id": choice_id,
            "kind": "deck_reorder",
            "playerId": player_id,
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "groups": groups,
            "_groups": groups,
        }
        return {
            "kind": "choice_required",
            "choiceId": choice_id,
            "choiceKind": "deck_reorder",
            "playerId": player_id,
        }

    def _rules_result_guess_top_card(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "player"
        ), None)
        target_id = target.get("playerId") if target else None
        if target_id not in self.players:
            return {"kind": "guess_top_card", "status": "target_missing"}
        if not self.players[target_id]["zones"]["deck"]:
            return {"kind": "guess_top_card", "status": "deck_empty"}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id,
            "kind": "guess_top_card",
            "playerId": player_id,
            "targetPlayerId": target_id,
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "types": ["manifestation", "will"],
            "temperaments": sorted(RULES_TEMPERAMENTS),
            "values": list(range(0, 13)),
            "_cardId": self.players[target_id]["zones"]["deck"][0],
        }
        return {
            "kind": "choice_required",
            "choiceId": choice_id,
            "choiceKind": "guess_top_card",
            "playerId": player_id,
        }

    def _rules_result_exile_limbos_create_token_copies(self, action, result, player_id, player):
        created = []
        exiled = []
        for current_id, current in self.players.items():
            for card_id in list(current["zones"]["graveyard"]):
                if self.card_rules.get(card_id, {}).get("type") != "manifestation":
                    continue
                error, _owner_id, replacement = self.move_zone_card_by_effect(
                    current_id, "graveyard", current_id, "exile",
                    card_id, "top",
                )
                if error or replacement:
                    continue
                exiled.append({"playerId": current_id, "cardId": card_id})
                created.append(self.create_rules_token_copy(
                    card_id, current_id, hollow=True,
                    effects_disabled=True,
                ))
        return {
            "kind": result.get("kind"),
            "status": "resolved",
            "exiled": exiled,
            "createdItemIds": [item["id"] for item in created],
        }

    def _rules_result_search_deck_will_conceal(self, action, result, player_id, player):
        wills = sorted(
            card_id for card_id in player["zones"]["deck"]
            if self.card_rules.get(card_id, {}).get("type") in RULES_WILL_TYPES
        )
        if not wills:
            random.shuffle(player["zones"]["deck"])
            return {"kind": result.get("kind"), "status": "no_cards"}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "discard_from_hand",
            "playerId": player_id, "count": 1, "upTo": False,
            "candidateCardIds": wills,
            "destination": "concealed_field",
            "jigonItemId": (action.get("source") or {}).get("itemId"),
            "actionId": action.get("id"),
            "controllerId": action.get("controllerId"),
            "sourceCardId": (action.get("source") or {}).get("cardId"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "discard_from_hand", "playerId": player_id,
            "count": 1, "search": True,
        }

    def _rules_result_grant_limbo_will_play(self, action, result, player_id, player):
        owner_id = (action.get("source") or {}).get("ownerId") or player_id
        if owner_id not in self.players:
            return {"kind": result.get("kind"), "status": "target_missing"}
        self.rules_engine["playPermissions"].append({
            "id": new_id(), "abilityId": (action.get("ability") or {}).get("id"),
            "playerId": owner_id, "anyWill": True, "fromZone": "graveyard",
            "phaseIds": [self.current_phase_id()], "asSupport": False,
            "noTribute": True, "exileOnLeave": True,
            "turn": self.phase_tracker["turn"],
            "sourceCardId": (action.get("source") or {}).get("cardId"),
        })
        return {"kind": result.get("kind"), "status": "granted", "playerId": owner_id}

    def _rules_result_lock_next_turn_draws(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "player"
        ), None)
        target_id = (target or {}).get("playerId")
        if target_id not in self.players:
            return {"kind": result.get("kind"), "status": "target_missing"}
        turn = self.phase_tracker["turn"] + 1
        self.rules_engine["drawLocks"] = [
            entry for entry in self.rules_engine.get("drawLocks") or []
            if entry.get("turn") >= self.phase_tracker["turn"]
        ] + [{
            "playerId": target_id, "turn": turn,
            "sourceCardId": (action.get("source") or {}).get("cardId"),
        }]
        return {
            "kind": result.get("kind"), "status": "scheduled",
            "playerId": target_id, "turn": turn,
        }

    def _rules_result_schedule_next_turn_hand_limit(self, action, result, player_id, player):
        target_id = (action.get("source") or {}).get("containerId")
        if target_id not in self.players:
            return {
                "kind": result.get("kind"),
                "status": "target_missing",
            }
        effect = {
            "id": new_id(),
            "playerId": target_id,
            "turn": self.phase_tracker["turn"] + 1,
            "delta": int(result.get("delta") or 0),
            "overflowDestination": result.get(
                "overflowDestination", "graveyard"
            ),
            "sourceCardId": (action.get("source") or {}).get("cardId"),
        }
        self.rules_engine["handLimitEffects"].append(effect)
        return {
            "kind": result.get("kind"),
            "status": "scheduled",
            **effect,
        }

    def _rules_result_optional_discard_then_draw(self, action, result, player_id, player):
        if not player["zones"]["hand"]:
            return {
                "kind": result.get("kind"),
                "status": "no_hand_card",
            }
        if action.get("optionalAccepted"):
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id,
                "kind": "discard_from_hand",
                "playerId": player_id,
                "count": 1,
                "drawAfter": int(result.get("draw") or 0),
                "actionId": action.get("id"),
                "controllerId": action.get("controllerId"),
                "sourceCardId": (action.get("source") or {}).get("cardId"),
            }
            return {
                "kind": "choice_required",
                "choiceId": choice_id,
                "choiceKind": "discard_from_hand",
                "playerId": player_id,
                "count": 1,
                "drawAfter": int(result.get("draw") or 0),
            }
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id,
            "kind": "optional_discard_draw",
            "playerId": player_id,
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "draw": int(result.get("draw") or 0),
            "options": ["accept", "decline"],
        }
        return {
            "kind": "choice_required",
            "choiceId": choice_id,
            "choiceKind": "optional_discard_draw",
            "playerId": player_id,
        }

    def _rules_result_suspend_opponent_hand_will(self, action, result, player_id, player):
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
        eligible = [
            card_id for card_id in self.players[target_id]["zones"]["hand"]
            if self.card_rules.get(card_id, {}).get("type")
            in RULES_WILL_TYPES
        ]
        if not eligible:
            return {
                "kind": result.get("kind"),
                "status": "no_eligible_card",
                "handProof": list(
                    self.players[target_id]["zones"]["hand"]
                ),
                "handProofPlayerId": target_id,
            }
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id,
            "kind": "suspend_hand_will",
            "playerId": target_id,
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "sourceItemId": (action.get("source") or {}).get("itemId"),
            "playableByPlayerId": player_id,
            "cardIds": eligible,
            "_cardIds": eligible,
        }
        return {
            "kind": "choice_required",
            "choiceId": choice_id,
            "choiceKind": "suspend_hand_will",
            "playerId": target_id,
        }

    def _rules_result_discard_hand_each_opponent(self, action, result, player_id, player):
        if int(result.get("drawOwner") or 0):
            self.request_rules_draw(
                player_id, int(result["drawOwner"]),
                source_controller_id=action.get("controllerId"),
            )
        return self.apply_rules_action_result({
            **action,
            "targets": [{
                "kind": "player",
                "playerId": self.other_rules_player_id(player_id),
            }],
            "ability": {
                **(action.get("ability") or {}),
                "result": {
                    "kind": "discard_hand_target",
                    "value": result.get("value"),
                },
            },
        })

    def _rules_result_draw_owner(self, action, result, player_id, player):
        if (
            result.get("kind") in {"draw_owner", "discard_deck_owner"}
            and result.get("targetPlayer")
        ):
            # Zum: "a target player draws / discards from the top of the deck"
            target_id = next((
                entry.get("playerId") for entry in action.get("targets") or []
                if entry.get("kind") == "player"
            ), None)
            if target_id not in self.players:
                return {"kind": result.get("kind"), "status": "target_missing"}
            player_id, player = target_id, self.players[target_id]
        if result.get("kind") == "draw_owner":
            requested = max(0, min(int(result.get("value") or 0), 50))
            return self.request_rules_draw(
                player_id, requested,
                source_controller_id=action.get("controllerId"),
            )
        if result.get("kind") == "discard_deck_owner":
            requested = max(0, min(int(result.get("value") or 0), 50))
            discarded = []
            for _index in range(min(requested, len(player["zones"]["deck"]))):
                card_id = player["zones"]["deck"][0]
                error, _owner_id, replacement = self.move_zone_card_by_effect(
                    player_id, "deck", player_id, "graveyard", card_id, "top"
                )
                if error:
                    break
                if not replacement:
                    discarded.append(card_id)
            return {
                "kind": "discard_deck",
                "playerId": player_id,
                "count": len(discarded),
                "cardIds": discarded,
            }

    def _rules_result_discard_hand_target(self, action, result, player_id, player):
        target = next(
            (entry for entry in action.get("targets") or [] if entry.get("kind") == "player"),
            None,
        )
        target_id = target.get("playerId") if target else None
        target_player = self.players.get(target_id)
        if target_player is None:
            return None
        if self.rules_hand_is_immune(target_id, player_id):
            return {
                "kind": "discard",
                "status": "prevented_immunity",
                "playerId": target_id,
                "count": 0,
                "cardIds": [],
            }
        requested = max(0, min(int(result.get("value") or 0), 7))
        target_hand = target_player["zones"]["hand"]
        count = min(requested, len(target_hand))
        hand_proof = list(target_hand) if len(target_hand) < requested else None
        if count == 0:
            payload = {
                "kind": "discard", "playerId": target_id,
                "count": 0, "cardIds": [],
            }
            if hand_proof is not None:
                payload["handProof"] = hand_proof
                payload["handProofPlayerId"] = target_id
            return payload
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id,
            "kind": "discard_from_hand",
            "playerId": target_id,
            "count": count,
            "actionId": action.get("id"),
            "controllerId": action.get("controllerId"),
            "sourceCardId": (action.get("source") or {}).get("cardId"),
        }
        payload = {
            "kind": "choice_required",
            "choiceId": choice_id,
            "choiceKind": "discard_from_hand",
            "playerId": target_id,
            "count": count,
        }
        if hand_proof is not None:
            payload["handProof"] = hand_proof
            payload["handProofPlayerId"] = target_id
        return payload

    def _rules_result_discard_hand_owner_then_draw(self, action, result, player_id, player):
        if self.rules_hand_is_immune(player_id, action.get("controllerId")):
            return {
                "kind": "discard_then_draw",
                "status": "prevented_immunity",
                "playerId": player_id,
                "count": 0,
                "cardIds": [],
                "drawCount": 0,
            }
        requested = max(0, min(int(result.get("discard") or 0), 7))
        owner_hand = player["zones"]["hand"]
        count = min(requested, len(owner_hand))
        hand_proof = list(owner_hand) if len(owner_hand) < requested else None
        if count == 0:
            payload = {
                "kind": "discard_then_draw", "status": "not_paid",
                "playerId": player_id, "count": 0, "cardIds": [], "drawCount": 0,
            }
            if hand_proof is not None:
                payload["handProof"] = hand_proof
                payload["handProofPlayerId"] = player_id
            return payload
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id,
            "kind": "discard_from_hand",
            "playerId": player_id,
            "count": count,
            "drawAfter": max(0, min(int(result.get("draw") or 0), 50)),
            "actionId": action.get("id"),
            "controllerId": action.get("controllerId"),
            "sourceCardId": (action.get("source") or {}).get("cardId"),
        }
        payload = {
            "kind": "choice_required",
            "choiceId": choice_id,
            "choiceKind": "discard_from_hand",
            "playerId": player_id,
            "count": count,
            "drawAfter": self.rules_engine["pendingChoice"]["drawAfter"],
        }
        if hand_proof is not None:
            payload["handProof"] = hand_proof
            payload["handProofPlayerId"] = player_id
        return payload

    def _rules_result_move_hand_source_to_interzone(self, action, result, player_id, player):
        source = action.get("source") or {}
        owner_id = source.get("ownerId") or player_id
        card_id = source.get("cardId")
        if owner_id not in self.players or card_id not in self.players[
            owner_id
        ]["zones"]["hand"]:
            return {"kind": result.get("kind"), "status": "source_missing"}
        if (
            self.rules_interzone_slot_count(owner_id)
            >= self.rules_interzone_capacity(owner_id)
        ):
            return {"kind": result.get("kind"), "status": "no_space"}
        self.take_zone_card(owner_id, "hand", card_id)
        position = self.clean_rules_board_position(None)
        item = {
            "id": new_id(), "ownerId": owner_id, "controllerId": owner_id,
            "cardId": card_id, "x": position["x"], "y": position["y"],
            "faceUp": True, "rotation": 0.0, "counters": {},
            "rarity": (self.players.get(owner_id) or {}).get(
                "cardRarities", {}
            ).get(card_id),
            "stackedOn": None, "fieldZone": "interzone",
        }
        self.mark_rules_interzone_entry(item)
        self.battlefield.append(item)
        triggered_actions = self.queue_rules_battlefield_entry_triggers(
            card_id, owner_id, item["id"], True, defer=True,
        )
        triggered_actions.extend(self.queue_rules_field_zone_entry_triggers(
            item, "interzone", defer=True,
        ))
        triggered_actions.extend(
            self.queue_rules_manifestation_entry_watchers(
                item, defer=True, played=False,
            )
        )
        if triggered_actions:
            self.queue_rules_simultaneous_actions(triggered_actions)
        return {
            "kind": result.get("kind"), "status": "moved",
            "cardId": card_id, "itemId": item["id"],
            "triggeredActions": triggered_actions,
        }

    def _rules_result_move_source_to_owner_hand(self, action, result, player_id, player):
        source_item = self.find_battlefield_item(
            (action.get("source") or {}).get("itemId")
        )
        if source_item is None:
            return {"kind": result.get("kind"), "status": "source_missing"}
        movement = self._rules_remove_field_item_by_effect(
            source_item, source_item.get("ownerId"), "hand", "top",
            reason="return",
        )
        return {
            "kind": "move_card",
            "status": movement.get("status"),
            "cardId": source_item.get("cardId"),
            "itemId": source_item.get("id"),
            "toZone": "hand",
            "reason": "return",
        }
