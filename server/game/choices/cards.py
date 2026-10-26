"""Pending choices that pick, reveal, reorder or discard cards."""

import random

from ..common import RULES_WILL_TYPES, new_id


class CardsChoicesMixin:
    def _rules_choice_token_count(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if str(option) not in choice.get("options", []):
            return "Choose how many tokens to create.", None
        self.rules_engine["pendingChoice"] = None
        payload = self.apply_rules_action_result({
            **(choice.get("_action") or {}), "_tokenCount": int(option),
        })
        return None, {**payload, "playerId": player_id}

    def _rules_choice_pick_distribution_extra(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if item_id not in choice.get("candidateItemIds", []):
            return "Choose one of the targets.", None
        action = choice.get("_action") or {}
        base = int(choice.get("_base") or 1)
        shares = {
            candidate: base + (1 if candidate == item_id else 0)
            for candidate in choice["candidateItemIds"]
        }
        self.rules_engine["pendingChoice"] = None
        payload = self.rules_apply_power_distribution(
            action, shares, int(choice.get("sign") or 1)
        )
        self.prune_rules_ongoing_effects()
        return None, {**payload, "playerId": player_id, "itemId": item_id}

    def _rules_choice_reveal_hand_discard(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if choice.get("kind") == "reveal_hand_discard" and choice.get("purpose") == "lunar":
            try:
                index = int(option)
            except (TypeError, ValueError):
                return "Choose a Manifestation to put into the Stalemate Zone.", None
            entries = choice.get("entries") or []
            if not 0 <= index < len(entries):
                return "Choose a Manifestation to put into the Stalemate Zone.", None
            entry = entries[index]
            if entry["from"] == "interzone":
                picked = self.find_battlefield_item(entry["itemId"])
                if picked is None or self.rules_item_controller_id(picked) != player_id:
                    return "That Manifestation is no longer available.", None
                self.rules_stalemate_item(picked["id"])
            else:
                owner_id = self.take_zone_card(player_id, "receptacle", entry["cardId"])
                if owner_id is None:
                    return "That Manifestation is no longer available.", None
                seat = self.players[player_id].get("seat")
                self.battlefield.append({
                    "id": new_id(), "ownerId": owner_id, "controllerId": player_id,
                    "cardId": entry["cardId"], "x": 650.0, "y": 800.0 if seat != 1 else 525.0,
                    "faceUp": True, "rotation": 0.0, "counters": {}, "stackedOn": None,
                    "fieldZone": "stalemate",
                })
            next_id = self.rules_lunar_next(
                choice.get("hostItemId"), choice.get("controllerId"),
                list(choice.get("_pending") or []), choice.get("sourceCardId"), choice.get("actionId"),
            )
            return None, {
                "kind": "lunar_liturgy", "status": "placed", "playerId": player_id,
                "cardId": entry["cardId"], "nextChoiceId": next_id,
            }

        if choice.get("kind") == "reveal_hand_discard":
            try:
                index = int(option)
            except (TypeError, ValueError):
                return "Choose a card from the revealed hand.", None
            target_id = choice.get("targetPlayerId")
            hand = self.players[target_id]["zones"][{"bloatuba": "deck", "gummo": "receptacle", "wish": "receptacle", "pescojolero": "receptacle"}.get(choice.get("purpose"), "hand")] if target_id in self.players else []
            card_ids = choice.get("cardIds") or []
            if not 0 <= index < len(card_ids) or card_ids[index] not in hand:
                return "Choose a card from the revealed hand.", None
            card_id = card_ids[index]
            if choice.get("purpose") == "gummo":
                host = self.find_battlefield_item(choice.get("sourceItemId"))
                self.rules_engine["pendingChoice"] = None
                if host is None:
                    return None, {"kind": "gummo_copy", "status": "target_missing"}
                host["gummoCopy"] = card_id
                return None, {
                    "kind": "gummo_copy", "status": "copied", "playerId": player_id,
                    "itemId": host["id"], "cardId": card_id,
                }
            if choice.get("purpose") == "pescojolero":
                self.rules_engine["pendingChoice"] = None
                placed = self.place_rules_card_in_interzone(player_id, target_id, "receptacle", card_id)
                return None, {
                    "kind": "pescojolero_take", "playerId": player_id,
                    "status": "taken" if placed else "interzone_full", "cardId": card_id,
                    "itemId": (placed or {}).get("id"),
                    "sourceCardId": choice.get("sourceCardId"),
                }
            if choice.get("purpose") == "wish":
                caster_id = choice.get("casterId")
                mine_id = choice.get("chosenCardId")
                if mine_id not in self.players[caster_id]["zones"]["receptacle"]:
                    self.rules_engine["pendingChoice"] = None
                    return None, {"kind": "wish_exchange", "status": "target_missing"}
                mine_owner = self.take_zone_card(caster_id, "receptacle", mine_id)
                theirs_owner = self.take_zone_card(target_id, "receptacle", card_id)
                self.put_zone_card(mine_owner if mine_owner in self.players else target_id, "deck", mine_id, mine_owner, "top")
                self.put_zone_card(theirs_owner if theirs_owner in self.players else caster_id, "deck", card_id, theirs_owner, "top")
                self.rules_engine["pendingChoice"] = None
                return None, {
                    "kind": "wish_exchange", "status": "exchanged", "playerId": player_id,
                    "cardIds": [mine_id, card_id], "sourceCardId": choice.get("sourceCardId"),
                }
            if choice.get("purpose") == "gorlok":
                error, _owner_id, _replacement = self.move_zone_card_by_effect(
                    target_id, "hand", target_id, "exile", card_id, "top",
                )
                if error:
                    return error, None
                host = self.find_battlefield_item(choice.get("sourceItemId"))
                if host is not None:
                    self.adjust_rules_power_counter(host, -len(card_ids))
                self.rules_engine["pendingChoice"] = None
                return None, {
                    "kind": "gorlok_exile", "playerId": player_id, "targetPlayerId": target_id,
                    "cardId": card_id, "shown": len(card_ids),
                    "sourceCardId": choice.get("sourceCardId"),
                }
            if choice.get("purpose") == "bloatuba":
                owner_id = self.take_zone_card(target_id, "deck", card_id)
                if owner_id is None:
                    return "That card is no longer on top of the Deck.", None
                seat = self.players[target_id].get("seat")
                stalemate_item = {
                    "id": new_id(), "ownerId": owner_id, "controllerId": target_id,
                    "cardId": card_id, "x": 650.0, "y": 800.0 if seat != 1 else 525.0,
                    "faceUp": True, "rotation": 0.0, "counters": {}, "stackedOn": None,
                    "fieldZone": "stalemate",
                    "rarity": self.players[owner_id].get("cardRarities", {}).get(card_id),
                }
                self.battlefield.append(stalemate_item)
                remaining = [c for c in choice.get("_revealed") or [] if c != card_id]
                self.rules_engine["pendingChoice"] = (
                    self.make_bloatuba_reorder(
                        choice.get("controllerId"), target_id, remaining, choice.get("sourceCardId"),
                    ) if remaining else None
                )
                return None, {
                    "kind": "bloatuba_pick", "playerId": player_id,
                    "targetPlayerId": target_id, "cardId": card_id,
                    "itemId": stalemate_item["id"],
                    "remaining": remaining,
                }
            if choice.get("purpose") == "womb":
                self.rules_engine["pendingChoice"] = None
                return self.chain_rules_manifestation(
                    target_id, "hand", card_id,
                    action_id=choice.get("actionId"),
                    source_card_id=choice.get("sourceCardId"),
                    chain_controller_id=player_id,
                )
            error, _owner_id = self.move_zone_card(
                target_id, "hand", target_id, "graveyard", card_id, "top"
            )
            if error:
                return error, None
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "reveal_hand_discard", "playerId": player_id,
                "targetPlayerId": target_id, "cardId": card_id,
                "sourceCardId": choice.get("sourceCardId"),
            }

    def _rules_choice_pick_own_item(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if item_id not in choice.get("candidateItemIds", []):
            return "Choose one of your Manifestations.", None
        done = list(choice.get("_done") or [])
        if choice.get("purpose") == "sacrifice":
            picked = self.find_battlefield_item(item_id)
            done.append(self._rules_remove_field_item_by_effect(
                picked, picked.get("ownerId"), "graveyard", "top",
                reason="sacrifice",
            ))
        else:
            done.append(self.rules_stalemate_item(item_id))
        self.rules_engine["pendingChoice"] = None
        next_choice = None
        if choice.get("_queue"):
            next_choice = self.rules_next_pick_own_item_choice(
                choice["_queue"], choice.get("actionId"),
                choice.get("sourceCardId"), done,
                purpose=choice.get("purpose") or "stalemate",
            )
        self.prune_rules_ongoing_effects()
        return None, {
            "kind": "pick_own_item", "purpose": choice.get("purpose"),
            "playerId": player_id, "itemId": item_id,
            "itemIds": done, "sourceCardId": choice.get("sourceCardId"),
            "nextChoiceId": next_choice["id"] if next_choice else None,
        }

    def _rules_choice_deck_reorder(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if not isinstance(option, dict) or not isinstance(option.get("groups"), list):
            return "Choose the top and bottom order for every revealed deck group.", None
        groups = list(choice.get("_groups") or [])
        supplied = option["groups"]
        if len(supplied) != len(groups):
            return "Order every revealed deck group exactly once.", None
        validated_groups = []
        supplied_players = [entry.get("playerId") if isinstance(entry, dict) else None for entry in supplied]
        if (
            not all(isinstance(pid, str) for pid in supplied_players)
            or len(set(supplied_players)) != len(supplied_players)
            or set(supplied_players) != {group.get("playerId") for group in groups}
        ):
            return "Order every revealed deck group exactly once.", None
        for group in groups:
            submitted = next((
                entry for entry in supplied
                if isinstance(entry, dict)
                and entry.get("playerId") == group.get("playerId")
            ), None)
            if submitted is None:
                return "Order every revealed deck group exactly once.", None
            top = submitted.get("top")
            bottom = submitted.get("bottom")
            extra = submitted.get("extra") if group.get("extraSide") else []
            if not isinstance(extra, list):
                return "Use every revealed card exactly once.", None
            if group.get("extraSide") and not (
                int(group.get("extraMin") or 0) <= len(extra) <= int(group.get("extraMax") or 0)
            ):
                return "Choose the allowed number of cards to set aside.", None
            if (
                not isinstance(top, list)
                or not isinstance(bottom, list)
                or not all(isinstance(card_id, str) for card_id in top + bottom + extra)
                or len(top) != len(set(top))
                or len(bottom) != len(set(bottom))
                or set(top) & set(bottom)
                or set(extra) & (set(top) | set(bottom))
                or len(extra) != len(set(extra))
                or sorted(top + bottom + extra) != sorted(group.get("cardIds") or [])
            ):
                return "Use every revealed card exactly once.", None
            if (
                group.get("topCount") is not None
                and len(top) != int(group.get("topCount") or 0)
            ):
                return "Choose the required number of cards for the top of the Deck.", None
            if (
                group.get("bottomCount") is not None
                and len(bottom) != int(group.get("bottomCount") or 0)
            ):
                return "Choose the required number of cards for the bottom of the Deck.", None
            target_id = group.get("playerId")
            from_zone = group.get("fromZone") or "deck"
            source_cards = self.players.get(target_id, {}).get("zones", {}).get(from_zone, [])
            remaining = list(source_cards)
            owners = {}
            for card_id in group.get("cardIds") or []:
                if card_id not in remaining:
                    return "A revealed card is no longer in its expected zone.", None
                owners[card_id] = self.card_owner_in_zone(
                    target_id, from_zone, card_id
                )
                remaining.remove(card_id)
            transfers = (
                [(card_id, target_id, "deck") for card_id in top + bottom]
                if from_zone != "deck" else []
            )
            transfers.extend(
                (card_id, player_id if group.get("extraSide") == "hand" else owners[card_id],
                 "hand" if group.get("extraSide") == "hand" else "exile")
                for card_id in extra
            )
            for card_id, recipient, destination in transfers:
                error = self.rules_source_reservation_error(target_id, from_zone, card_id)
                if error:
                    return error, None
                if from_zone == "hand" and self.rules_hands_are_immune():
                    return "Cards in Hand are Immune to cards and effects.", None
                suspended_instead = any(
                    self.rules_active_suspension_source(zone) is not None
                    for zone in {from_zone, destination} if zone in {"deck", "graveyard"}
                )
                if not suspended_instead:
                    error = self.destination_error(owners[card_id], recipient, destination)
                    if error:
                        return error, None
            validated_groups.append((group, target_id, from_zone, owners, top, bottom, extra))

        # No card or metadata changes until every group and transfer is valid.
        resolved_groups = []
        for group, target_id, from_zone, owners, top, bottom, extra in validated_groups:
            movements = []
            placed = {"top": [], "bottom": [], "extra": []}
            if from_zone == "deck":
                # Reordering within a Deck does not enter or leave that zone.
                # Cards set aside below are actual transfers and can Suspend.
                for card_id in top + bottom:
                    self.take_zone_card(target_id, from_zone, card_id)
                placed["top"], placed["bottom"] = list(top), list(bottom)
            else:
                for side, ordered in [("top", reversed(top)), ("bottom", bottom)]:
                    for card_id in ordered:
                        error, _owner, replacement = self.move_zone_card_by_effect(
                            target_id, from_zone, target_id, "deck", card_id, side,
                        )
                        if error:
                            return error, None
                        if replacement:
                            movements.append(replacement)
                        elif side == "top":
                            placed[side].insert(0, card_id)
                        else:
                            placed[side].append(card_id)
            for card_id in extra:
                destination = "hand" if group.get("extraSide") == "hand" else "exile"
                recipient = player_id if destination == "hand" else owners[card_id]
                error, _owner, replacement = self.move_zone_card_by_effect(
                    target_id, from_zone, recipient, destination, card_id, "top",
                )
                if error:
                    return error, None
                if replacement:
                    movements.append(replacement)
                else:
                    placed["extra"].append(card_id)
            if from_zone == "deck":
                existing = list(self.players[target_id]["zones"]["deck"])
                self.players[target_id]["zones"]["deck"] = list(top) + existing + list(bottom)
                self.players[target_id]["zoneOwners"]["deck"].update({
                    card_id: owners[card_id] for card_id in top + bottom
                })
            resolved_groups.append({
                "playerId": target_id,
                "top": placed["top"],
                "bottom": placed["bottom"],
                "fromZone": from_zone,
                **({"extraSide": group["extraSide"], "extra": placed["extra"]} if extra else {}),
                **({"replacements": movements} if movements else {}),
            })
        self.rules_engine["pendingChoice"] = None
        payload = {
            "kind": "deck_reorder",
            "playerId": player_id,
            "groups": resolved_groups,
            "sourceCardId": choice.get("sourceCardId"),
        }
        if int(choice.get("_afterDiscard") or 0) > 0:
            discard_deck = self.players[player_id]["zones"]["deck"]
            discarded_cards = []
            for _index in range(min(int(choice["_afterDiscard"]), len(discard_deck))):
                top_card = discard_deck[0]
                move_error, _owner, replaced = self.move_zone_card_by_effect(
                    player_id, "deck", player_id, "graveyard", top_card, "top"
                )
                if move_error:
                    break
                if not replaced:
                    discarded_cards.append(top_card)
            payload["discarded"] = discarded_cards
        if int(choice.get("_afterDraw") or 0) > 0:
            payload["draw"] = self.draw_rules_cards(
                player_id, int(choice["_afterDraw"])
            )
        if choice.get("_queue"):
            next_choice = self.rules_next_deck_order_choice(
                choice["_queue"], choice.get("sourceCardId")
            )
            payload["nextChoiceId"] = next_choice["id"]
        return None, payload

    def _rules_choice_peek_top_card(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if option not in {"keep", "bottom"} and not (option == "swap" and choice.get("allowSwap")):
            return "Choose whether to keep the card on top or move it to the bottom.", None
        card_id = choice.get("_cardId")
        deck = self.players[player_id]["zones"]["deck"]
        if not deck or deck[0] != card_id:
            self.rules_engine["pendingChoice"] = None
            return "The inspected top card is no longer available.", None
        if option == "swap":
            hand = self.players[player_id]["zones"]["hand"]
            swap_id = (card_ids or [None])[0]
            if swap_id not in hand:
                return "Choose a card from your Hand to swap.", None
            swap_owner = self.take_zone_card(player_id, "hand", swap_id)
            top_owner = self.take_zone_card(player_id, "deck", card_id)
            self.put_zone_card(player_id, "hand", card_id, top_owner, "top")
            self.put_zone_card(player_id, "deck", swap_id, swap_owner, "top")
        if option == "bottom":
            deck.append(deck.pop(0))
        self.rules_engine["pendingChoice"] = None
        return None, {
            "kind": "peek_top_card",
            "playerId": player_id,
            "cardId": card_id,
            "destination": "bottom" if option == "bottom" else "top",
            "sourceCardId": choice.get("sourceCardId"),
        }

    def _rules_choice_guess_top_card(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if not isinstance(option, dict):
            return "Declare the card type, Temperament, and power or cost value.", None
        guessed_type = str(option.get("type") or "")
        guessed_temperament = str(option.get("temperament") or "")
        try:
            guessed_value = int(option.get("value"))
        except (TypeError, ValueError):
            return "Declare a valid power or cost value.", None
        if (
            guessed_type not in choice.get("types", [])
            or guessed_temperament not in choice.get("temperaments", [])
            or guessed_value not in choice.get("values", [])
        ):
            return "Declare a valid card type, Temperament, and value.", None
        target_id = choice.get("targetPlayerId")
        card_id = choice.get("_cardId")
        target_deck = self.players.get(target_id, {}).get("zones", {}).get("deck", [])
        if not target_deck or target_deck[0] != card_id:
            self.rules_engine["pendingChoice"] = None
            return "The guessed top card is no longer available.", None
        metadata = self.card_rules.get(card_id, {})
        actual_type = (
            "manifestation"
            if metadata.get("type") == "manifestation" else "will"
        )
        actual_temperaments = list(metadata.get("temperaments") or [])
        actual_value = (
            int(metadata.get("power") or 0)
            if actual_type == "manifestation"
            else int(metadata.get("cost") or 0)
        )
        correct = sum((
            guessed_type == actual_type,
            guessed_temperament in actual_temperaments,
            guessed_value == actual_value,
        ))
        score_delta = correct * 10
        score_delta = self.adjust_rules_score(
            player_id, score_delta
        )
        follow_up = None
        self.rules_engine["pendingChoice"] = None
        if correct == 1 and self.players[player_id]["zones"]["deck"]:
            own_card_id = self.players[player_id]["zones"]["deck"][0]
            follow_choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": follow_choice_id,
                "kind": "peek_top_card",
                "playerId": player_id,
                "sourceCardId": choice.get("sourceCardId"),
                "cardId": own_card_id,
                "_cardId": own_card_id,
            }
            follow_up = {
                "kind": "choice_required",
                "choiceId": follow_choice_id,
                "choiceKind": "peek_top_card",
                "playerId": player_id,
            }
        elif correct == 2:
            drawn = self.draw_rules_cards(player_id, 2)
            follow_up = {"kind": "draw", "count": len(drawn)}
        elif correct == 3 and self.players[player_id]["zones"]["deck"]:
            own_card_id = self.players[player_id]["zones"]["deck"][0]
            own_type = self.card_rules.get(own_card_id, {}).get("type")
            if own_type == "manifestation":
                error, follow_up = self.chain_rules_manifestation(
                    player_id, "deck", own_card_id,
                    source_card_id=choice.get("sourceCardId"),
                )
                if error:
                    follow_up = {"kind": "chain_manifestation", "error": error}
            elif own_type in RULES_WILL_TYPES:
                error, owner_id, replacement = self.rules_zone_move_replacement(
                    player_id, "deck", "battlefield", own_card_id,
                    to_container_id=player_id,
                )
                if not error and not replacement:
                    self.take_zone_card(player_id, "deck", own_card_id)
                    seat = self.players[player_id].get("seat")
                    revealed = {
                        "id": new_id(), "ownerId": owner_id,
                        "controllerId": player_id, "cardId": own_card_id,
                        "x": 740.0, "y": 800.0 if seat != 1 else 525.0,
                        "faceUp": True, "rotation": 0.0, "counters": {},
                        "stackedOn": None, "fieldZone": "field",
                        # A revealed Will awaits its play action, just like a
                        # concealed free Will. Revealing it is not playing it.
                        "concealedWill": True, "concealedFree": True,
                        "revealedFreeWill": True, "effectsDisabled": True,
                    }
                    self.battlefield.append(revealed)
                    follow_up = {
                        "kind": "play_permission",
                        "cardId": own_card_id,
                        "itemId": revealed["id"], "fromZone": "battlefield",
                        "noTribute": True,
                    }
                elif replacement:
                    follow_up = {"kind": "play_permission", **replacement}
        return None, {
            "kind": "guess_top_card",
            "playerId": player_id,
            "targetPlayerId": target_id,
            "cardId": card_id,
            "guess": {
                "type": guessed_type,
                "temperament": guessed_temperament,
                "value": guessed_value,
            },
            "actual": {
                "type": actual_type,
                "temperaments": actual_temperaments,
                "value": actual_value,
            },
            "correct": correct,
            "scoreDelta": score_delta,
            "score": self.players[player_id]["score"],
            "followUp": follow_up,
            "sourceCardId": choice.get("sourceCardId"),
            "_overflowPlayerId": (
                player_id
                if len(self.players[player_id]["zones"]["hand"])
                > self.rules_hand_limit(player_id)
                else None
            ),
        }

    def _rules_choice_optional_discard_draw(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if option not in choice.get("options", []):
            return "Choose whether to discard a card and draw.", None
        if option == "decline":
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "optional_discard_draw",
                "status": "declined",
                "playerId": player_id,
                "sourceCardId": choice.get("sourceCardId"),
            }
        next_choice = {
            "id": new_id(),
            "kind": "discard_from_hand",
            "playerId": player_id,
            "count": 1,
            "drawAfter": int(choice.get("draw") or 0),
            "sourceCardId": choice.get("sourceCardId"),
        }
        self.rules_engine["pendingChoice"] = next_choice
        return None, {
            "kind": "optional_discard_draw",
            "status": "accepted",
            "playerId": player_id,
            "nextChoiceId": next_choice["id"],
            "sourceCardId": choice.get("sourceCardId"),
        }

    def _rules_choice_declare_card_name(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        declared = option if isinstance(option, str) else None
        if declared not in self.card_labels:
            return "Declare the name of an existing card.", None
        if choice.get("_declaration"):
            self.rules_engine["pendingChoice"] = None
            error, action = self.declare_rules_action(
                player_id, **choice["_declaration"], declared_card_id=declared,
            )
            if error:
                self.rules_engine["pendingChoice"] = choice
                return error, None
            if action.get("status") == "choice_required":
                return None, action
            return None, {
                "kind": "declare_card_name", "mode": choice.get("mode"), "status": "declared",
                "playerId": player_id, "declaredCardId": declared,
                "sourceCardId": choice.get("sourceCardId"), "_declaredActions": [action],
            }
        declared_name = self.card_labels.get(declared)
        owner_id = choice.get("targetPlayerId")
        deck = self.players[owner_id]["zones"]["deck"]
        self.rules_engine["pendingChoice"] = None
        payload = {
            "kind": "declare_card_name", "mode": choice.get("mode"),
            "playerId": player_id, "targetPlayerId": owner_id,
            "declaredCardId": declared, "sourceCardId": choice.get("sourceCardId"),
        }
        if choice.get("mode") == "top_card_power":
            if not deck:
                return None, {**payload, "status": "deck_empty"}
            top_card = deck[0]
            matched = self.card_labels.get(top_card) == declared_name
            payload.update({"revealedCardId": top_card, "matched": matched})
            if matched:
                source_item = self.find_battlefield_item(choice.get("sourceItemId"))
                if source_item is not None:
                    self.append_rules_ongoing_effect({
                        "id": new_id(), "actionId": choice.get("actionId"),
                        "abilityId": "declared-name-power",
                        "controllerId": player_id,
                        "source": {"cardId": choice.get("sourceCardId"), "itemId": source_item["id"]},
                        "target": {
                            "kind": "card", "itemId": source_item["id"],
                            "cardId": source_item.get("cardId"),
                            "ownerId": source_item.get("ownerId"),
                        },
                        "kind": "power_modifier",
                        "value": int(choice.get("value") or 0),
                        "duration": "until_end_of_turn",
                        "startedTurn": self.phase_tracker["turn"],
                    })
                return None, {**payload, "status": "matched"}
            error, _owner, replacement = self.move_zone_card_by_effect(
                owner_id, "deck", owner_id, "graveyard", top_card, "top",
            )
            return None, {
                **payload,
                "status": "discarded" if not error and not replacement else "unmoved",
            }
        return None, self.rules_resolve_declared_deck_search(
            player_id, owner_id, declared, choice.get("sourceCardId")
        )

    def rules_resolve_declared_deck_search(self, player_id, owner_id, declared, source_card_id):
        deck = self.players[owner_id]["zones"]["deck"]
        declared_name = self.card_labels[declared]
        payload = {"kind": "declare_card_name", "mode": "search_deck",
                   "playerId": player_id, "targetPlayerId": owner_id,
                   "declaredCardId": declared, "sourceCardId": source_card_id}
        found = next((
            card_id for card_id in deck
            if self.card_labels.get(card_id) == declared_name
        ), None)
        if found is None:
            random.shuffle(deck)
            return {**payload, "status": "not_found"}
        error, _owner, replacement = self.move_zone_card_by_effect(
            owner_id, "deck", owner_id, "graveyard", found, "top",
        )
        random.shuffle(self.players[owner_id]["zones"]["deck"])
        return {
            **payload, "cardId": found,
            "status": "discarded" if not error and not replacement else "unmoved",
        }

    def _rules_choice_hand_overflow(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if not isinstance(card_ids, list) or not all(
            isinstance(card_id, str) for card_id in card_ids
        ):
            return "Choose the required excess cards.", None
        required = int(choice.get("count") or 0)
        if len(card_ids) != required:
            return "Choose the required excess cards.", None
        hand = list(self.players[player_id]["zones"]["hand"])
        for card_id in card_ids:
            if card_id not in hand:
                return "An excess card is no longer in your Hand.", None
            hand.remove(card_id)
        destination = choice.get("destination")
        zone = "deck" if destination == "deck_bottom" else "graveyard"
        position = "bottom" if destination == "deck_bottom" else "top"
        for card_id in card_ids:
            error, _owner_id = self.move_zone_card(
                player_id, "hand", player_id, zone, card_id, position
            )
            if error:
                return error, None
        remaining = list(choice.get("remainingPlayerIds") or [])
        self.rules_engine["pendingChoice"] = None
        next_choice = self.set_rules_hand_overflow_choice(remaining)
        return None, {
            "kind": "hand_overflow",
            "playerId": player_id,
            "cardIds": list(card_ids),
            "destination": destination,
            "nextPlayerId": (
                next_choice.get("playerId") if next_choice else None
            ),
        }

    def _rules_choice_draw_replacement(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        offered = list(choice.get("_cardIds") or [])
        if not isinstance(card_ids, list) or len(card_ids) != int(
            choice.get("count") or 0
        ):
            return "Choose the required cards to discard.", None
        if len(set(card_ids)) != len(card_ids) or not set(card_ids) <= set(offered):
            return "Choose only the inspected draw cards.", None
        deck = self.players[player_id]["zones"]["deck"]
        if deck[:len(offered)] != offered:
            self.rules_engine["pendingChoice"] = None
            return "The inspected draw cards are no longer available.", None
        drawn_ids = [card_id for card_id in offered if card_id not in card_ids]
        for card_id in offered:
            owner_id = self.card_owner_in_zone(player_id, "deck", card_id)
            self.take_zone_card(player_id, "deck", card_id)
            self.put_zone_card(
                player_id,
                "graveyard" if card_id in card_ids else "hand",
                card_id, owner_id, "top" if card_id in card_ids else "bottom",
            )
        will_count = sum(
            self.card_rules.get(card_id, {}).get("type") in RULES_WILL_TYPES
            for card_id in card_ids
        )
        self.rules_engine["pendingChoice"] = None
        follow_up = None
        if will_count:
            source_controller_id = choice.get("sourceControllerId")
            target_rules = {"min": 1, "max": 1, "cardType": "manifestation", "controller": "opponent"}
            candidates = [
                item["id"] for item in self.battlefield
                if item.get("faceUp")
                and self.rules_ability_targets_error(target_rules, [{
                    "kind": "card", "itemId": item["id"], "cardId": item.get("cardId"),
                }], source_controller_id) is None
            ]
            if candidates:
                follow_up = {
                    "id": new_id(),
                    "kind": "power_loss_distribution",
                    "playerId": source_controller_id,
                    "count": will_count,
                    "candidateItemIds": candidates,
                    "targetRules": target_rules,
                    "sourceCardId": choice.get("sourceCardId"),
                }
                self.rules_engine["pendingChoice"] = follow_up
        return None, {
            "kind": "draw_replacement",
            "playerId": player_id,
            "discardedCardIds": list(card_ids),
            "drawnCardIds": drawn_ids,
            "willCount": will_count,
            "followUpChoiceId": follow_up.get("id") if follow_up else None,
        }

    def _resolve_rules_discard_choice(self, player_id, choice_id, choice, card_ids):
        if choice.get("kind") != "discard_from_hand":
            return "Unknown card choice.", None
        if not isinstance(card_ids, list) or not all(isinstance(card_id, str) for card_id in card_ids):
            return "Choose the required number of cards.", None
        selected = list(card_ids)
        required = int(choice.get("count") or 0)
        if len(selected) > required or (len(selected) != required and not choice.get("upTo")):
            return "Choose the required number of cards.", None
        if choice.get("destination") == "limbo_exile_add_power":
            limbo_zone = list(self.players[player_id]["zones"]["graveyard"])
            for card_id in selected:
                if card_id not in choice["candidateCardIds"] or card_id not in limbo_zone:
                    return "A selected card is not in your Limbo.", None
                limbo_zone.remove(card_id)
            self.rules_engine["pendingChoice"] = None
            resolution = self.apply_rules_action_result({
                "id": choice.get("actionId"), "controllerId": player_id,
                "source": choice.get("_source") or {}, "_limboChosen": True,
                "targets": [
                    {"kind": "zone_card", "containerId": player_id, "zone": "graveyard",
                     "cardId": card_id, "ownerId": player_id}
                    for card_id in selected
                ],
                "ability": {"result": {"kind": "exile_limbo_targets_add_power"}},
            })
            return None, {
                "kind": "exile_limbo_targets_add_power", "playerId": player_id,
                "cardIds": (resolution or {}).get("cardIds", []), "choiceId": choice_id,
                "power": (resolution or {}).get("power", 0),
                "sourceCardId": choice.get("sourceCardId"),
            }
        if choice.get("candidateCardIds") is not None:
            deck_zone = list(self.players[player_id]["zones"]["deck"])
            for card_id in selected:
                if card_id not in choice["candidateCardIds"] or card_id not in deck_zone:
                    return "A selected card is not available in your deck.", None
                deck_zone.remove(card_id)
            if choice.get("destination") == "interzone_from_search":
                card_id = selected[0]
                placed = self.place_rules_card_in_interzone(player_id, player_id, "deck", card_id)
                random.shuffle(self.players[player_id]["zones"]["deck"])
                self.rules_engine["pendingChoice"] = None
                return None, {
                    "kind": "search_deck", "playerId": player_id, "count": 1,
                    "cardIds": [card_id], "choiceId": choice_id,
                    "interzone": bool(placed), "itemId": (placed or {}).get("id"),
                    "actionId": choice.get("actionId"),
                    "controllerId": choice.get("controllerId"),
                    "sourceCardId": choice.get("sourceCardId"),
                }
            if choice.get("destination") == "concealed_field":
                seat = self.players[player_id].get("seat")
                for card_id in selected:
                    self.take_zone_card(player_id, "deck", card_id)
                    self.battlefield.append({
                        "id": new_id(), "ownerId": player_id, "controllerId": player_id,
                        "cardId": card_id, "x": 740.0, "y": 800.0 if seat != 1 else 525.0,
                        "faceUp": False, "rotation": 0.0, "counters": {}, "stackedOn": None,
                        "fieldZone": "field", "concealedWill": True,
                        "jigonItemId": choice.get("jigonItemId"),
                    })
                random.shuffle(self.players[player_id]["zones"]["deck"])
                self.rules_engine["pendingChoice"] = None
                return None, {
                    "kind": "search_deck", "playerId": player_id,
                    "count": len(selected), "cardIds": selected, "choiceId": choice_id,
                    "concealed": True,
                    "actionId": choice.get("actionId"),
                    "controllerId": choice.get("controllerId"),
                    "sourceCardId": choice.get("sourceCardId"),
                }
            for card_id in selected:
                error, _owner_id = self.move_zone_card(
                    player_id, "deck", player_id, "hand", card_id, "top"
                )
                if error:
                    return error, None
            if choice.get("revealSelected"):
                self.mark_hand_revealed(player_id, selected)
            random.shuffle(self.players[player_id]["zones"]["deck"])
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "search_deck", "playerId": player_id,
                "count": len(selected), "cardIds": selected, "choiceId": choice_id,
                "revealed": bool(choice.get("revealSelected")),
                "actionId": choice.get("actionId"),
                "controllerId": choice.get("controllerId"),
                "sourceCardId": choice.get("sourceCardId"),
            }
        hand_remaining = list(self.players[player_id]["zones"]["hand"])
        for card_id in selected:
            if card_id not in hand_remaining:
                return "A selected card is no longer in your hand.", None
            hand_remaining.remove(card_id)
        if choice.get("requireManifestation") and any(
            self.card_rules.get(card_id, {}).get("type") != "manifestation"
            for card_id in selected
        ):
            return "Choose a manifestation from your hand.", None
        if choice.get("requireTypes") and any(
            self.card_rules.get(card_id, {}).get("type") not in choice["requireTypes"]
            for card_id in selected
        ):
            return "Choose a valid card type from your hand.", None
        destination = choice.get("destination")
        if destination == "persuasion_place":
            card_id = selected[0]
            owner_id = self.take_zone_card(player_id, "hand", card_id)
            if owner_id is None:
                return "That Will is no longer in your Hand.", None
            seat = self.players[player_id].get("seat")
            item = {
                "id": new_id(), "ownerId": owner_id, "controllerId": player_id,
                "cardId": card_id, "x": 740.0, "y": 800.0 if seat != 1 else 525.0,
                "faceUp": True, "rotation": 0.0, "counters": {}, "stackedOn": None,
                "fieldZone": "field", "persuaded": True, "persuadedBy": choice.get("hostItemId"),
                "rarity": self.players[owner_id].get("cardRarities", {}).get(card_id),
            }
            self.battlefield.append(item)
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "persuasion_place", "playerId": player_id, "cardIds": [card_id],
                "itemId": item["id"], "choiceId": choice_id,
                "actionId": choice.get("actionId"), "controllerId": choice.get("controllerId"),
                "sourceCardId": choice.get("sourceCardId"),
            }
        destination = choice.get("destination")
        if destination in {"auction_bid", "auction_answer"}:
            seat = self.players[player_id].get("seat")
            points_of = lambda card: int((self.card_points or {}).get(card, 0) or 0)
            if destination == "auction_answer":
                total = sum(points_of(card_id) for card_id in selected)
                if total < int(choice.get("requiredPoints") or 0):
                    selected = []
                    self.rules_engine["forcedConfrontationWinnerId"] = choice.get("bidderId")
            for card_id in selected:
                owner_id = self.take_zone_card(player_id, "hand", card_id)
                if owner_id is None:
                    continue
                self.battlefield.append({
                    "id": new_id(), "ownerId": owner_id, "controllerId": player_id,
                    "cardId": card_id, "x": 650.0, "y": 800.0 if seat != 1 else 525.0,
                    "faceUp": True, "rotation": 0.0, "counters": {},
                    "rarity": self.players[owner_id].get("cardRarities", {}).get(card_id),
                    "stackedOn": None, "fieldZone": "stalemate",
                })
            self.rules_engine["pendingChoice"] = None
            payload = {
                "kind": destination, "playerId": player_id, "cardIds": selected,
                "choiceId": choice_id, "actionId": choice.get("actionId"),
                "controllerId": choice.get("controllerId"),
                "sourceCardId": choice.get("sourceCardId"),
            }
            if destination == "auction_bid":
                required = points_of(selected[0])
                opponent_id = self.other_rules_player_id(player_id)
                answers = [
                    c for c in self.players[opponent_id]["zones"]["hand"]
                    if self.card_rules.get(c, {}).get("type") == "manifestation"
                ]
                if sum(points_of(c) for c in answers) < required:
                    self.rules_engine["forcedConfrontationWinnerId"] = player_id
                    payload["opponentLoses"] = True
                else:
                    next_id = new_id()
                    self.rules_engine["pendingChoice"] = {
                        "id": next_id, "kind": "discard_from_hand",
                        "playerId": opponent_id, "count": len(answers), "upTo": True,
                        "requireManifestation": True, "destination": "auction_answer",
                        "requiredPoints": required, "bidderId": player_id,
                        "sourceCardId": choice.get("sourceCardId"),
                        "actionId": choice.get("actionId"),
                        "controllerId": choice.get("controllerId"),
                    }
                    payload["nextChoiceId"] = next_id
            return None, payload
        destination = choice.get("destination")
        if destination == "stalemate_for_support":
            support_id = choice.get("sourceCardId")
            if support_id not in hand_remaining:
                return "Choose two other Manifestations; Chabak must stay in your Hand.", None
            seat = self.players[player_id].get("seat")
            moved = []
            for card_id in selected:
                owner_id = self.take_zone_card(player_id, "hand", card_id)
                if owner_id is None:
                    continue
                self.battlefield.append({
                    "id": new_id(), "ownerId": owner_id, "controllerId": player_id,
                    "cardId": card_id, "x": 650.0, "y": 800.0 if seat != 1 else 525.0,
                    "faceUp": True, "rotation": 0.0, "counters": {},
                    "rarity": self.players[owner_id].get("cardRarities", {}).get(card_id),
                    "stackedOn": None, "fieldZone": "stalemate",
                })
                moved.append(card_id)
            support_item = self.place_rules_hand_card_in_support(player_id, support_id)
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "stalemate_for_support", "playerId": player_id, "cardIds": moved,
                "choiceId": choice_id, "itemId": (support_item or {}).get("id"),
                "actionId": choice.get("actionId"),
                "controllerId": choice.get("controllerId"),
                "sourceCardId": choice.get("sourceCardId"),
            }
        destination = choice.get("destination")
        if destination in {"obelisk_gift", "obelisk_reply"}:
            gift_id = selected[0]
            if destination == "obelisk_gift":
                reply_id = choice.get("chooserId")
                if any(
                    self.card_rules.get(c, {}).get("type") == "manifestation"
                    for c in self.players[reply_id]["zones"]["hand"]
                ):
                    new_choice_id = new_id()
                    self.rules_engine["pendingChoice"] = {
                        "id": new_choice_id, "kind": "discard_from_hand",
                        "playerId": reply_id, "count": 1, "requireManifestation": True,
                        "destination": "obelisk_reply", "chooserId": player_id,
                        "_giftCardId": gift_id,
                        "actionId": choice.get("actionId"),
                        "controllerId": choice.get("controllerId"),
                        "sourceCardId": choice.get("sourceCardId"),
                    }
                    return None, {
                        "kind": "obelisk_gift", "status": "waiting_reply", "playerId": player_id,
                        "choiceId": new_choice_id, "cardIds": [],
                        "actionId": choice.get("actionId"),
                        "controllerId": choice.get("controllerId"),
                        "sourceCardId": choice.get("sourceCardId"),
                    }
                giver_id, giver_card, other_id, other_card = player_id, gift_id, reply_id, None
            else:
                giver_id, giver_card, other_id, other_card = choice.get("chooserId"), choice.get("_giftCardId"), player_id, gift_id
            self.rules_engine["pendingChoice"] = None
            exchanged = []
            entered = []
            for from_id, to_id, card_id in ((giver_id, other_id, giver_card), (other_id, giver_id, other_card)):
                if not card_id or card_id not in self.players[from_id]["zones"]["hand"]:
                    continue
                owner_id = self.take_zone_card(from_id, "hand", card_id)
                self.put_zone_card(to_id, "receptacle", card_id, owner_id, "top")
                exchanged.append({"cardId": card_id, "fromId": from_id, "toId": to_id})
                entered.extend(self.queue_rules_zone_entry_triggers(
                    card_id, owner_id, to_id, "receptacle", defer=True,
                ))
            powers = {
                entry["fromId"]: int(self.card_rules.get(entry["cardId"], {}).get("power") or 0)
                for entry in exchanged
            }
            boosted = None
            if powers:
                top = max(powers.values())
                winners = [pid for pid, value in powers.items() if value == top]
                if len(winners) == 1:
                    first = self.find_battlefield_item(
                        self.rules_engine.get("firstManifestationItemIds", {}).get(winners[0])
                    )
                    if first is not None:
                        self.append_rules_ongoing_effect({
                            "id": new_id(), "actionId": choice.get("actionId"),
                            "abilityId": "obelisk-gift-boost",
                            "controllerId": winners[0],
                            "source": {"cardId": choice.get("sourceCardId")},
                            "target": {
                                "kind": "card", "itemId": first["id"],
                                "cardId": first.get("cardId"), "ownerId": first.get("ownerId"),
                            },
                            "kind": "power_modifier", "value": 3,
                            "duration": "until_end_of_turn",
                            "startedTurn": self.phase_tracker["turn"],
                        })
                        boosted = {"playerId": winners[0], "itemId": first["id"], "value": 3}
            if entered:
                self.queue_rules_simultaneous_actions(entered)
            return None, {
                "kind": "obelisk_gift", "status": "exchanged", "playerId": player_id,
                "exchanged": exchanged, "cardIds": [e["cardId"] for e in exchanged],
                "boosted": boosted, "choiceId": choice_id,
                "actionId": choice.get("actionId"),
                "controllerId": choice.get("controllerId"),
                "sourceCardId": choice.get("sourceCardId"),
            }
        if destination == "deck_bottom_from_hand":
            card_id = selected[0]
            owner_id = self.take_zone_card(player_id, "hand", card_id)
            if owner_id is None:
                return "That card is no longer in your Hand.", None
            self.put_zone_card(player_id, "deck", card_id, owner_id, "bottom")
            host = self.find_battlefield_item(choice.get("sourceItemId"))
            removal = choice.get("removeCounter") or {}
            if host is not None and removal.get("name"):
                counters = host.setdefault("counters", {})
                key = next((k for k in counters if str(k).casefold() == str(removal["name"]).casefold()), removal["name"])
                counters[key] = max(0, int(counters.get(key) or 0) - int(removal.get("amount") or 0))
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "deck_bottom_from_hand", "playerId": player_id, "cardIds": [card_id],
                "choiceId": choice_id, "actionId": choice.get("actionId"),
                "controllerId": choice.get("controllerId"),
                "sourceCardId": choice.get("sourceCardId"),
            }
        if destination == "attach_to_source":
            host = self.find_battlefield_item(choice.get("sourceItemId"))
            if host is None:
                return "The card to place them on is gone.", None
            placed = []
            for card_id in selected:
                owner_id = self.take_zone_card(player_id, "hand", card_id)
                if owner_id is None:
                    continue
                host.setdefault("attachedCards", []).append({"cardId": card_id, "ownerId": owner_id})
                placed.append(card_id)
            self.rules_sync_attached_counter(host)
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "attach_to_source", "playerId": player_id, "cardIds": placed,
                "count": len(placed), "itemId": host["id"], "choiceId": choice_id,
                "actionId": choice.get("actionId"),
                "controllerId": choice.get("controllerId"),
                "sourceCardId": choice.get("sourceCardId"),
            }
        if destination == "bullyboo_reveal":
            will_id = selected[0]
            payer_id = choice.get("chooserId")
            cost = self.card_rules.get(will_id, {}).get("powerCost")
            revealed = {
                "kind": "bullyboo_reveal", "playerId": player_id, "cardIds": [will_id],
                "handProof": [will_id], "handProofPlayerId": player_id,
                "actionId": choice.get("actionId"),
                "controllerId": choice.get("controllerId"),
                "sourceCardId": choice.get("sourceCardId"),
            }
            if self.rules_can_afford_tribute(payer_id, cost):
                new_choice_id = new_id()
                self.rules_engine["pendingChoice"] = {
                    "id": new_choice_id, "kind": "immediate_effect_payment",
                    "purpose": "bullyboo", "mustPay": True, "playerId": payer_id,
                    "payment": cost,
                    "requirements": self.rules_requirements_from_symbols(cost),
                    "sourceCardId": choice.get("sourceCardId"),
                    "relatedCardId": will_id, "willCardId": will_id,
                    "actionId": choice.get("actionId"),
                    "controllerId": player_id,
                }
                return None, {**revealed, "status": "payment_required", "choiceId": new_choice_id}
            self.rules_engine["pendingChoice"] = None
            lost = -self.adjust_rules_score(payer_id, -10)
            self.move_zone_card(player_id, "hand", player_id, "graveyard", will_id, "top")
            return None, {
                **revealed, "status": "cannot_pay", "lost": lost,
                "payerId": payer_id,
                "payerHand": list(self.players[payer_id]["zones"]["hand"]),
                "handProof": list(self.players[payer_id]["zones"]["hand"]),
                "handProofPlayerId": payer_id,
            }
        if destination == "amphora_offer":
            new_choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": new_choice_id, "kind": "binary_choice", "purpose": "amphora_pick",
                "playerId": choice.get("chooserId"), "options": ["yes", "no"],
                "headingKey": "rulesAmphoraHeading", "textKey": "rulesAmphoraText",
                "yesKey": "rulesAmphoraFirst", "noKey": "rulesAmphoraSecond",
                "sourceCardId": choice.get("sourceCardId"),
                "relatedCardId": choice.get("sourceCardId"),
                "controllerId": player_id, "offeredCardIds": list(selected),
            }
            return None, {
                "kind": "amphora_offer", "status": "offered", "playerId": player_id,
                "choiceId": new_choice_id, "cardIds": [],
                "actionId": choice.get("actionId"),
                "controllerId": choice.get("controllerId"),
                "sourceCardId": choice.get("sourceCardId"),
            }
        for card_id in selected:
            if destination == "support_manifestation":
                moved = self.apply_rules_action_result({
                    "id": new_id(), "controllerId": player_id,
                    "source": {"cardId": choice.get("sourceCardId"), "ownerId": player_id},
                    "targets": [{
                        "kind": "zone_card", "containerId": player_id, "zone": "hand",
                        "cardId": card_id, "ownerId": player_id,
                    }],
                    "ability": {"result": {"kind": "put_hand_will_as_support_manifestation"}},
                })
                if (moved or {}).get("status") != "moved":
                    return "This Will cannot enter Support right now.", None
                continue
            if destination == "interzone":
                moved = self.apply_rules_action_result({
                    "id": new_id(), "controllerId": player_id,
                    "source": {"cardId": choice.get("sourceCardId")},
                    "targets": [{
                        "kind": "zone_card", "containerId": player_id, "zone": "hand",
                        "cardId": card_id, "ownerId": player_id,
                    }],
                    "ability": {"result": {"kind": "move_zone_target_to_field_zone", "fieldZone": "interzone"}},
                })
                if (moved or {}).get("status") != "moved":
                    return "Your Interzone has no room for this Manifestation.", None
                continue
            error, _owner_id = self.move_zone_card(
                player_id, "hand", player_id, "exile" if destination == "exile" else "graveyard",
                card_id, "top",
            )
            if error:
                return error, None
        destroyed = None
        if choice.get("destroyTargetItemId") and selected:
            target_item = self.find_battlefield_item(choice["destroyTargetItemId"])
            revealed_base = int(self.card_rules.get(selected[0], {}).get("power") or 0)
            if (
                target_item is not None
                and self.rules_manifestation_base_power(target_item) <= revealed_base
            ):
                movement = self._rules_remove_field_item_by_effect(
                    target_item, target_item.get("ownerId"), "graveyard", "top", reason="destroy"
                )
                self.prune_rules_ongoing_effects()
                destroyed = {"itemId": target_item["id"], "status": movement.get("status")}
        weakened = None
        if choice.get("weakenTargetItemId"):
            weak_item = self.find_battlefield_item(choice["weakenTargetItemId"])
            base = int(self.card_rules.get(selected[0], {}).get("power") or 0) if selected else 0
            if weak_item is not None and base:
                self.adjust_rules_power_counter(weak_item, -base)
                weakened = {"itemId": weak_item["id"], "value": -base}
        power_gain = None
        if choice.get("sourcePowerPerDiscard") and selected:
            source_item = self.find_battlefield_item(choice.get("sourceItemId"))
            if source_item is not None:
                value = len(selected) * int(choice["sourcePowerPerDiscard"])
                self.append_rules_ongoing_effect({
                    "id": new_id(), "actionId": choice.get("actionId"),
                    "abilityId": "discard-wills-for-power",
                    "controllerId": choice.get("controllerId") or player_id,
                    "source": {
                        "cardId": choice.get("sourceCardId"),
                        "itemId": choice.get("sourceItemId"), "zone": "battlefield",
                    },
                    "target": {
                        "kind": "card", "itemId": source_item["id"],
                        "cardId": source_item.get("cardId"),
                        "ownerId": source_item.get("ownerId"),
                    },
                    "kind": "power_modifier", "value": value,
                    "duration": "until_end_of_turn",
                    "startedTurn": self.phase_tracker["turn"],
                })
                power_gain = {"itemId": source_item["id"], "value": value}
        points_lost = 0
        if choice.get("lossPerRemaining"):
            remaining = len(self.players[player_id]["zones"]["hand"])
            points_lost = -self.adjust_rules_score(
                player_id, -int(choice["lossPerRemaining"]) * remaining
            ) if remaining else 0
        drawn = 0
        requested_draw = max(0, min(int(choice.get("drawAfter") or 0), 50))
        if choice.get("drawByBasePower") and selected:
            requested_draw = max(0, min(int(self.card_rules.get(selected[0], {}).get("power") or 0), 50))
        for _index in range(min(requested_draw, len(self.players[player_id]["zones"]["deck"]))):
            card_id = self.players[player_id]["zones"]["deck"][0]
            error, _owner_id = self.move_zone_card(
                player_id, "deck", player_id, "hand", card_id, "bottom"
            )
            if error:
                break
            drawn += 1
        self.rules_engine["pendingChoice"] = None
        return None, {
            "kind": "discard_then_draw" if requested_draw else "discard",
            "playerId": player_id,
            "count": len(selected),
            "cardIds": selected,
            "drawCount": drawn,
            "choiceId": choice_id,
            "actionId": choice.get("actionId"),
            "controllerId": choice.get("controllerId"),
            "sourceCardId": choice.get("sourceCardId"),
            **({"destroyed": destroyed} if destroyed else {}),
            **({"weakened": weakened} if weakened else {}),
            **({"powerGain": power_gain} if power_gain else {}),
            **({"pointsLost": points_lost} if points_lost else {}),
        }
