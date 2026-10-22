"""Pending choices that pay (or refuse to pay) an effect cost."""

import time

from ..common import ADVANCED_PHASES, new_id


class PaymentChoicesMixin:
    def _rules_choice_skip_confrontation_payment(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if option not in choice.get("options", []):
            return "Choose whether to lose points or skip the Confrontation.", None
        if option == "lose_points":
            requested = -int(choice.get("points") or 0)
            delta = self.adjust_rules_score(player_id, requested)
            status = "paid" if delta == requested else "prevented"
        else:
            self.phase_tracker["index"] = ADVANCED_PHASES.index(
                "resolution_compare"
            )
            self.rules_engine["priorityPasses"] = []
            status = "skipped"
        self.rules_engine["pendingChoice"] = None
        return None, {
            "kind": "skip_confrontation_payment",
            "status": status,
            "playerId": player_id,
            "score": self.players[player_id]["score"],
            "phaseId": self.current_phase_id(),
            "sourceCardId": choice.get("sourceCardId"),
        }

    def _rules_choice_effect_memory_payment(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if option not in {"pay", "decline"}:
            return "Choose whether to pay the requested Tribute.", None
        memory = next((
            entry for entry in self.rules_engine.get("effectMemories") or []
            if entry.get("id") == choice.get("memoryId")
        ), None)
        if memory is None:
            self.rules_engine["pendingChoice"] = None
            return "This remembered effect is no longer available.", None
        if option == "pay":
            payment_error, payment = self.rules_action_payment(
                player_id, "activated_effect", None, card_ids,
                {"tribute": choice.get("payment")},
            )
            if payment_error:
                return payment_error, None
            self.pay_rules_tribute(player_id, payment)
            paid_card_ids = list(payment.get("cardIds") or [])
            status = "paid"
        else:
            owner_id = memory.get("ownerId")
            card_id = memory.get("cardId")
            error, _owner_id, replacement = self.move_zone_card_by_effect(
                owner_id, "graveyard", owner_id, "hand", card_id, "top"
            )
            status = (
                "target_missing" if error
                else replacement["status"] if replacement
                else "returned"
            )
        self.remove_rules_effect_memory(memory["id"])
        self.rules_engine["pendingChoice"] = None
        return None, {
            "kind": "effect_memory_payment",
            "status": status,
            "playerId": player_id,
            "cardId": memory.get("cardId"),
            "memoryId": memory["id"],
            "payment": choice.get("payment"),
            # Melancholic Mirror and the other "used as tribute" triggers
            "triggeredActions": self.queue_rules_tribute_triggers(
                paid_card_ids if status == "paid" else [], player_id, defer_if_choice=True,
            ),
        }

    def _rules_choice_immediate_effect_payment(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if choice.get("kind") == "immediate_effect_payment" and choice.get("purpose") == "bullyboo":
            if option != "pay":
                return "You must pay this Tribute.", None
            payment_error, payment = self.rules_action_payment(
                player_id, "activated_effect", None, card_ids,
                {"tribute": choice.get("payment")},
            )
            if payment_error:
                return payment_error, None
            self.pay_rules_tribute(player_id, payment)
            self.rules_engine["pendingChoice"] = None
            controller_id = choice.get("controllerId")
            will_id = choice.get("willCardId")
            if will_id in self.players[controller_id]["zones"]["hand"]:
                self.rules_engine["playPermissions"].append({
                    "id": new_id(), "abilityId": "bullyboo-plays-revealed-will",
                    "playerId": controller_id, "cardId": will_id, "fromZone": "hand",
                    "phaseIds": list(ADVANCED_PHASES), "asSupport": False,
                    "noTribute": True, "turn": self.phase_tracker["turn"],
                    "sourceCardId": choice.get("sourceCardId"),
                })
            played = None
            if will_id in self.players[controller_id]["zones"]["hand"]:
                error, played = self.declare_rules_action(
                    controller_id, f"{self.card_labels.get(will_id, will_id)}",
                    kind="play_card", source={"cardId": will_id, "zone": "hand"},
                    internal=True,
                )
                if error:
                    played = None  # needs targets or a choice: the free-play right remains
            return None, {
                "kind": "immediate_effect_payment", "status": "paid",
                "playerId": player_id, "sourceCardId": choice.get("sourceCardId"),
                "willCardId": will_id, "freePlayGrantedTo": controller_id,
                "autoPlayed": bool(played),
                "triggeredActions": self.queue_rules_tribute_triggers(
                    list(payment.get("cardIds") or []), player_id, defer_if_choice=True,
                ),
            }

        if choice.get("kind") == "immediate_effect_payment":
            if option not in {"pay", "decline"}:
                return "Choose whether to pay the requested Tribute.", None
            if option == "pay":
                payment_error, payment = self.rules_action_payment(
                    player_id, "activated_effect", None, card_ids,
                    {"tribute": choice.get("payment")},
                )
                if payment_error:
                    return payment_error, None
                self.pay_rules_tribute(player_id, payment)
                paid_card_ids = list(payment.get("cardIds") or [])
                status = "paid"
                confrontation = None
            else:
                status = "declined"
                source_card_id = choice.get("sourceCardId")
                controller_id = choice.get("controllerId")
                if (
                    choice.get("exileOnDecline")
                    and source_card_id in self.players.get(
                        controller_id, {}
                    ).get("zones", {}).get("graveyard", [])
                ):
                    self.move_zone_card_by_effect(
                        controller_id, "graveyard",
                        controller_id, "exile", source_card_id, "top",
                    )
                if choice.get("stalemateOnDecline"):
                    self.rules_engine["forcedConfrontationStalemate"] = True
                self.phase_tracker["index"] = ADVANCED_PHASES.index(
                    "resolution_compare"
                )
                self.rules_engine["priorityPasses"] = []
                confrontation = self.prepare_rules_confrontation_result()
            followup_choice = None
            if (
                status == "declined"
                and confrontation
                and choice.get(
                    "reduceWinnerManifestationOnControllerDefeat"
                )
                and confrontation.get("loserId")
                == choice.get("controllerId")
                and int(choice.get("controllerBasePower") or 0) > 0
            ):
                controller_id = choice.get("controllerId")
                target_rules = {
                    "min": 1,
                    "max": 1,
                    "cardType": "manifestation",
                    "zones": ["battlefield"],
                    "fieldZone": "confrontation",
                    "controller": "opponent",
                }
                candidates = [
                    item for item in self.rules_confrontation_items(
                        confrontation.get("winnerId")
                    )
                    if self.rules_ability_targets_error(
                        target_rules,
                        [{
                            "kind": "card",
                            "itemId": item.get("id"),
                            "cardId": item.get("cardId"),
                            "ownerId": item.get("ownerId"),
                        }],
                        controller_id,
                    ) is None
                ]
                if candidates:
                    followup_action = {
                        "id": new_id(),
                        "controllerId": controller_id,
                        "label": (
                            f'{self.card_labels.get(choice.get("sourceCardId"), choice.get("sourceCardId"))}'
                            " — immediate power loss"
                        ),
                        "kind": "triggered_effect",
                        "source": {
                            "cardId": choice.get("sourceCardId"),
                            "zone": "exile",
                            "itemId": None,
                            "cardType": "ephemeral_will",
                            "ownerId": controller_id,
                        },
                        "target": None,
                        "targets": [],
                        "ability": {
                            "id": "immediate-controller-defeat-power-loss",
                            "trigger": {
                                "event": "immediate_controller_defeat",
                            },
                            "result": {
                                "kind": "adjust_target_power",
                                "value": -int(
                                    choice.get("controllerBasePower") or 0
                                ),
                            },
                            "ongoingEffect": None,
                            "targets": target_rules,
                        },
                        "cost": {
                            "note": None,
                            "tributeCardIds": [],
                            "tributeRequirements": {},
                            "essenceSpent": [],
                            "excessEssence": [],
                            "tributeValidated": False,
                            "tributePaid": False,
                            "sourceExhausted": False,
                            "sourceSacrificed": False,
                            "sacrificedCards": [],
                        },
                        "phaseId": self.current_phase_id(),
                        "turn": self.phase_tracker["turn"],
                        "createdAt": time.time(),
                        "immediate": True,
                    }
                    followup_choice = {
                        "id": new_id(),
                        "kind": "trigger_targets",
                        "playerId": controller_id,
                        "sourceCardId": choice.get("sourceCardId"),
                        "targetRules": target_rules,
                        "_triggerAction": followup_action,
                    }
            self.rules_engine["pendingChoice"] = followup_choice
            if followup_choice:
                self.rules_engine["priorityPlayerId"] = (
                    followup_choice["playerId"]
                )
            payload = {
                "kind": "immediate_effect_payment",
                "status": status,
                "playerId": player_id,
                "sourceCardId": choice.get("sourceCardId"),
                "phaseId": self.current_phase_id(),
                "confrontationResult": confrontation,
            }
            if followup_choice:
                payload["followupChoiceId"] = followup_choice["id"]
                payload["powerLoss"] = int(
                    choice.get("controllerBasePower") or 0
                )
            if status == "paid":
                payload["triggeredActions"] = self.queue_rules_tribute_triggers(
                    paid_card_ids, player_id, defer_if_choice=True,
                )
            return None, payload

    def _rules_choice_effect_payment(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if option not in {"pay", "decline"}:
            return "Choose whether to pay the requested Tribute.", None
        on_decline = choice.get("onDecline") or {}
        if option == "pay":
            payment_error, payment = self.rules_action_payment(
                player_id, "activated_effect", None, card_ids,
                {"tribute": choice.get("payment")},
            )
            if payment_error:
                return payment_error, None
            self.pay_rules_tribute(player_id, payment)
            triggered_actions = self.queue_rules_tribute_triggers(payment["cardIds"], player_id)
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "effect_payment", "status": "paid", "playerId": player_id,
                "choiceId": choice_id, "sourceCardId": choice.get("sourceCardId"),
                "triggeredActions": triggered_actions,
            }
        outcome = {}
        if on_decline.get("kind") == "deck_discard":
            deck = self.players[player_id]["zones"]["deck"]
            discarded = 0
            for _index in range(min(int(on_decline.get("count") or 0), len(deck))):
                error, _owner, replacement = self.move_zone_card_by_effect(
                    player_id, "deck", player_id, "graveyard", deck[0], "top"
                )
                if error:
                    break
                if not replacement:
                    discarded += 1
            outcome["discarded"] = discarded
        elif on_decline.get("kind") == "lock_support_entries":
            self.rules_engine.setdefault("supportLocks", []).append({
                "turn": self.phase_tracker["turn"], "playerId": None,
            })
            outcome["locked"] = True
        elif on_decline.get("kind") == "to_opponent_vessel":
            item = self.find_battlefield_item(on_decline.get("itemId"))
            target_id = on_decline.get("opponentId")
            if item is not None and target_id in self.players:
                self._rules_remove_field_item(item, target_id, "receptacle", "top")
                outcome["movedToVessel"] = target_id
        elif on_decline.get("kind") == "exile_source":
            item = self.find_battlefield_item(on_decline.get("itemId"))
            if item is not None:
                self._rules_remove_field_item_by_effect(
                    item, item.get("ownerId"), "exile", "top", reason="exile",
                )
                outcome["exiled"] = True
        elif on_decline.get("kind") == "lose_effects":
            item = self.find_battlefield_item(on_decline.get("itemId"))
            if item is not None:
                self.rules_engine["ongoingEffects"].append({
                    "id": new_id(), "actionId": choice.get("actionId"),
                    "abilityId": "effect-payment-declined",
                    "controllerId": choice.get("controllerId") or player_id,
                    "source": {"cardId": choice.get("sourceCardId")},
                    "target": {
                        "kind": "card", "itemId": item["id"],
                        "cardId": item.get("cardId"), "ownerId": item.get("ownerId"),
                    },
                    "kind": "lose_effects", "duration": "permanent",
                    "startedTurn": self.phase_tracker["turn"],
                })
                outcome["itemId"] = item["id"]
        self.rules_engine["pendingChoice"] = None
        return None, {
            "kind": "effect_payment", "status": "declined", "playerId": player_id,
            "choiceId": choice_id, "sourceCardId": choice.get("sourceCardId"),
            **outcome,
        }
