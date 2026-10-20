"""Pending binary or numeric decisions offered by card effects."""

from ..common import new_id


class DecisionsChoicesMixin:
    def _rules_choice_score_delta_choice(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if option not in choice.get("options", []):
            return "Choose whether the target gains or loses Points.", None
        value = int(choice.get("value") or 0)
        requested = value if option == "gain" else -value
        applied = self.adjust_rules_score(
            choice.get("targetPlayerId"), requested
        )
        self.rules_engine["pendingChoice"] = None
        return None, {
            "kind": "score_delta_choice",
            "status": "prevented" if not applied else "resolved",
            "playerId": player_id,
            "targetPlayerId": choice.get("targetPlayerId"),
            "delta": applied,
            "score": self.players.get(
                choice.get("targetPlayerId"), {}
            ).get("score"),
            "sourceCardId": choice.get("sourceCardId"),
        }

    def _rules_choice_effect_memory_return(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if option not in {"return", "decline"}:
            return "Choose whether to return the remembered card.", None
        memory = next((
            entry for entry in self.rules_engine.get("effectMemories") or []
            if entry.get("id") == choice.get("memoryId")
        ), None)
        if memory is None:
            self.rules_engine["pendingChoice"] = None
            return "This remembered effect is no longer available.", None
        card_id = memory.get("cardId")
        owner_id = memory.get("ownerId")
        status = "declined"
        if option == "return":
            error, _owner_id, replacement = self.move_zone_card_by_effect(
                owner_id, "graveyard", owner_id, "hand", card_id, "top"
            )
            status = (
                "target_missing" if error
                else "suspended" if replacement
                else "returned"
            )
        self.remove_rules_effect_memory(memory["id"])
        self.rules_engine["pendingChoice"] = None
        return None, {
            "kind": "effect_memory_return",
            "status": status,
            "playerId": player_id,
            "cardId": card_id,
            "memoryId": memory["id"],
        }

    def _rules_choice_points_or_weaken_first(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if option not in choice.get("options", []):
            return "Choose whether to lose points or weaken your First Manifestation.", None
        outcome = {}
        if option == "lose_points":
            outcome["delta"] = self.adjust_rules_score(player_id, -int(choice.get("points") or 0))
        else:
            first = self.find_battlefield_item(
                (self.rules_engine.get("firstManifestationItemIds") or {}).get(player_id)
            )
            if first is not None:
                self.rules_engine["ongoingEffects"].append({
                    "id": new_id(), "actionId": None, "abilityId": "points-or-weaken-first",
                    "controllerId": player_id,
                    "source": {"cardId": choice.get("sourceCardId")},
                    "target": {
                        "kind": "card", "itemId": first["id"],
                        "cardId": first.get("cardId"), "ownerId": first.get("ownerId"),
                    },
                    "kind": "power_modifier", "duration": "until_end_of_turn",
                    "startedTurn": self.phase_tracker["turn"],
                    "value": -int(choice.get("power") or 0),
                })
                outcome["itemId"] = first["id"]
        self.rules_engine["pendingChoice"] = None
        return None, {
            "kind": "points_or_weaken_first",
            "status": "lost_points" if option == "lose_points" else "weakened",
            "playerId": player_id, "sourceCardId": choice.get("sourceCardId"), **outcome,
        }

    def _rules_choice_temperament_choice(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if option not in choice.get("options", []):
            return "Choose a base temperament.", None
        self.rules_engine["pendingChoice"] = None
        item = self.find_battlefield_item(choice.get("sourceItemId"))
        if item is not None:
            item["chosenTemperament"] = option
            label = option.capitalize()
            item.setdefault("counters", {})[label] = 1
        return None, {
            "kind": "temperament_choice", "status": "chosen",
            "temperament": option, "itemId": choice.get("sourceItemId"),
        }

    def _rules_choice_binary_choice(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if choice.get("kind") == "binary_choice" and choice.get("purpose") == "quasimillenary":
            if option not in choice.get("options", []):
                return "Choose yes or no.", None
            self.rules_engine["pendingChoice"] = None
            self.rules_engine.setdefault("limboRecoveryDecided", {})[player_id] = self.phase_tracker["turn"]
            enabled = self.rules_engine.setdefault("limboRecoveryPlayerIds", [])
            if option == "yes" and player_id not in enabled:
                enabled.append(player_id)
            elif option == "no" and player_id in enabled:
                enabled.remove(player_id)
            error, recovery = self.resolve_recovery_draw(int(choice.get("handLimit") or 7))
            if error:
                return error, None
            return None, {
                "kind": "quasimillenary_choice", "status": "limbo" if option == "yes" else "deck",
                "playerId": player_id, "recovery": recovery,
            }

        if choice.get("kind") == "binary_choice" and choice.get("purpose") == "womb_show":
            if option not in choice.get("options", []):
                return "Choose yes or no.", None
            self.rules_engine["pendingChoice"] = None
            controller_id = choice.get("controllerId")
            hand = list(self.players[player_id]["zones"]["hand"])
            chainable = [
                c for c in hand
                if self.card_rules.get(c, {}).get("type") == "manifestation"
                and self.rules_card_play_restriction_error(player_id, c) is None
            ] if option == "yes" and not self.rules_hands_are_immune() else []
            if not chainable:
                tokens = self.apply_rules_action_result({
                    "id": choice.get("actionId") or new_id(), "controllerId": controller_id,
                    "source": {"cardId": choice.get("sourceCardId"), "ownerId": controller_id},
                    "targets": [],
                    "ability": {"result": {
                        "kind": "create_support_tokens", "count": 2, "power": 2,
                        "temperament": "hollow",
                    }},
                })
                return None, {
                    "kind": "womb_show", "status": "tokens",
                    "shown": option == "yes", "tokens": tokens,
                    "handProof": hand if option == "yes" else [],
                }
            new_choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": new_choice_id, "kind": "reveal_hand_discard", "purpose": "womb",
                "playerId": controller_id, "targetPlayerId": player_id,
                "cardIds": chainable,
                "sourceCardId": choice.get("sourceCardId"),
                "actionId": choice.get("actionId"),
            }
            return None, {
                "kind": "womb_show", "status": "shown", "handProof": hand,
                "choiceId": new_choice_id,
            }

        if choice.get("kind") == "binary_choice" and choice.get("purpose") == "amphora_pick":
            if option not in choice.get("options", []):
                return "Choose one of the two manifestations.", None
            self.rules_engine["pendingChoice"] = None
            owner_id = choice.get("controllerId")
            offered = list(choice.get("offeredCardIds") or [])
            hand = self.players[owner_id]["zones"]["hand"]
            if len(offered) != 2 or any(c not in hand for c in offered):
                return None, {"kind": "amphora_pick", "status": "target_missing"}
            kept, discarded = (offered[0], offered[1]) if option == "yes" else (offered[1], offered[0])
            moved = self.apply_rules_action_result({
                "id": new_id(), "controllerId": owner_id,
                "source": {"cardId": choice.get("sourceCardId"), "ownerId": owner_id},
                "targets": [{
                    "kind": "zone_card", "containerId": owner_id, "zone": "hand",
                    "cardId": kept, "ownerId": owner_id,
                }],
                "ability": {"result": {"kind": "move_zone_target_to_field_zone", "asSupport": True}},
            })
            self.move_zone_card(owner_id, "hand", owner_id, "graveyard", discarded, "top")
            return None, {
                "kind": "amphora_pick", "status": (moved or {}).get("status"),
                "cardId": kept, "discardedCardId": discarded,
            }

        if choice.get("kind") == "binary_choice" and choice.get("purpose") == "support_else_chain":
            if option not in choice.get("options", []):
                return "Choose yes or no.", None
            self.rules_engine["pendingChoice"] = None
            item = self.find_battlefield_item(choice.get("targetItemId"))
            moved = False
            if (
                option == "yes" and item is not None
                and self.rules_field_zone(item) == "interzone"
                and not self.rules_support_entry_locked(player_id)
            ):
                item["stackedOn"] = None
                self.mark_rules_support_entry(item)
                triggered = self.queue_rules_support_entry_triggers(
                    item, played=False, from_zone="interzone", defer=True,
                )
                if triggered:
                    self.queue_rules_simultaneous_actions(triggered)
                moved = True
            if moved:
                return None, {
                    "kind": "binary_choice", "status": "support",
                    "itemId": item["id"], "cardId": item.get("cardId"),
                }
            controller_id = choice.get("controllerId")
            if controller_id not in self.players:
                return None, {"kind": "binary_choice", "status": "declined"}
            chain = self.begin_rules_chain_sequence(
                controller_id, [controller_id],
                {"kind": "chain_from_zone", "zone": "hand", "optional": True},
                dict(choice.get("_action") or {}),
            )
            return None, {**chain, "declined": True}

    def _rules_choice_clemency_choice(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if option not in choice.get("options", []):
            return "Choose whether to neutralize your Will.", None
        controller_id = choice.get("sourceControllerId")
        self.rules_engine["pendingChoice"] = None
        countered = None
        target_action = next((
            entry for entry in self.rules_engine.get("actionStack") or []
            if entry.get("id") == choice.get("relatedActionId")
            and entry.get("kind") == "play_card"
        ), None)
        if option == "neutralize" and target_action is not None:
            countered = self.counter_rules_stack_action(target_action, "neutralize")
        if countered and countered.get("status") == "neutralized":
            source_item = self.find_battlefield_item(choice.get("sourceItemId"))
            if source_item is not None:
                source_item["rotation"] = 90.0
            return None, {
                "kind": "clemency_choice", "status": "neutralized",
                "playerId": player_id, "sourceCardId": choice.get("sourceCardId"),
                "neutralized": countered,
            }
        delta = (
            self.adjust_rules_score(controller_id, int(choice.get("points") or 0))
            if controller_id in self.players else 0
        )
        return None, {
            "kind": "clemency_choice", "status": "gained",
            "playerId": player_id, "gainerId": controller_id, "delta": delta,
            "sourceCardId": choice.get("sourceCardId"),
        }

    def _rules_choice_points_or_hand_limit(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if option not in choice.get("options", []):
            return "Choose whether to lose points or limit your Hand.", None
        if option == "lose_points":
            delta = self.adjust_rules_score(
                player_id, -int(choice.get("points") or 0)
            )
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "points_or_hand_limit",
                "status": "lost_points",
                "playerId": player_id,
                "delta": delta,
                "score": self.players[player_id]["score"],
                "sourceCardId": choice.get("sourceCardId"),
            }
        self.rules_engine["handLimitEffects"].append({
            "id": new_id(),
            "playerId": player_id,
            "turn": self.phase_tracker["turn"],
            "limit": int(choice.get("limit") or 0),
            "overflowDestination": "graveyard",
            "sourceCardId": choice.get("sourceCardId"),
        })
        self.rules_engine["pendingChoice"] = None
        overflow = self.set_rules_hand_overflow_choice([player_id])
        return None, {
            "kind": "points_or_hand_limit",
            "status": "limited_hand",
            "playerId": player_id,
            "limit": int(choice.get("limit") or 0),
            "overflowChoiceId": overflow.get("id") if overflow else None,
            "sourceCardId": choice.get("sourceCardId"),
        }

    def _rules_choice_power_loss_distribution(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        item_ids = (
            option.get("itemIds")
            if isinstance(option, dict) else None
        )
        if (
            not isinstance(item_ids, list)
            or len(item_ids) != int(choice.get("count") or 0)
            or not all(item_id in choice.get("candidateItemIds", []) for item_id in item_ids)
        ):
            return "Choose one valid target for each discarded Will.", None
        applied = []
        for item_id in item_ids:
            item = self.find_battlefield_item(item_id)
            if item is None:
                return "A selected Manifestation is no longer on the field.", None
            effect = {
                "id": new_id(),
                "actionId": choice.get("id"),
                "abilityId": "draw-replacement-power-loss",
                "controllerId": player_id,
                "source": {
                    "cardId": choice.get("sourceCardId"),
                    "zone": "battlefield",
                },
                "target": {
                    "kind": "card", "itemId": item_id,
                    "cardId": item.get("cardId"),
                    "ownerId": item.get("ownerId"),
                },
                "kind": "power_modifier",
                "duration": "until_end_of_turn",
                "startedTurn": self.phase_tracker["turn"],
                "value": -1,
            }
            self.rules_engine["ongoingEffects"].append(effect)
            applied.append(effect["id"])
        self.rules_engine["pendingChoice"] = None
        overflow = (
            self.set_rules_hand_overflow_choice(
                [choice.get("_overflowPlayerId")]
            )
            if choice.get("_overflowPlayerId") else None
        )
        return None, {
            "kind": "power_loss_distribution",
            "playerId": player_id,
            "itemIds": list(item_ids),
            "effectIds": applied,
            "sourceCardId": choice.get("sourceCardId"),
            "overflowChoiceId": overflow.get("id") if overflow else None,
        }

    def _rules_choice_random_target_effect(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if item_id not in choice.get("candidateItemIds", []):
            return "Choose a valid card for the random effect.", None
        item = self.find_battlefield_item(item_id)
        if item is None:
            return "The selected card is no longer on the field.", None
        effect = {
            "id": new_id(),
            "actionId": choice.get("id"),
            "abilityId": "random-target-effect",
            "controllerId": player_id,
            "source": {
                "cardId": choice.get("sourceCardId"),
                "itemId": choice.get("sourceItemId"),
                "zone": "battlefield",
            },
            "target": {
                "kind": "card", "itemId": item_id,
                "cardId": item.get("cardId"),
                "ownerId": item.get("ownerId"),
            },
            "kind": choice.get("effectKind"),
            "duration": "until_end_of_turn",
            "startedTurn": self.phase_tracker["turn"],
        }
        self.rules_engine["ongoingEffects"].append(effect)
        self.rules_engine["pendingChoice"] = None
        return None, {
            "kind": "random_target_effect",
            "playerId": player_id,
            "itemId": item_id,
            "effectId": effect["id"],
            "roll": choice.get("roll"),
            "sourceCardId": choice.get("sourceCardId"),
        }

    def _rules_choice_suspend_hand_will(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if (
            not isinstance(card_ids, list)
            or len(card_ids) != 1
            or card_ids[0] not in choice.get("_cardIds", [])
        ):
            return "Choose one eligible Will to Suspend.", None
        card_id = card_ids[0]
        error, suspended = self.suspend_zone_card(
            player_id, "hand", card_id,
            source_effect_id=choice.get("sourceItemId"),
            returnZone="hand",
            returnTurn=self.phase_tracker["turn"],
            playableByPlayerId=choice.get("playableByPlayerId"),
            anyTemperamentTribute=True,
        )
        if error:
            return error, None
        self.rules_engine["pendingChoice"] = None
        return None, {
            "kind": "suspend_hand_will",
            "playerId": player_id,
            "cardId": card_id,
            "suspensionId": suspended.get("id"),
            "playableByPlayerId": choice.get("playableByPlayerId"),
            "sourceCardId": choice.get("sourceCardId"),
        }
