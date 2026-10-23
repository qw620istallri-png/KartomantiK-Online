"""Effect results that act on the Stack, effect memories and rematches."""

import random

from ..common import RULES_WILL_TYPES, new_id


class StackEffectsMixin:
    def _rules_result_create_effect_memory(self, action, result, player_id, player):
        trigger = (action.get("ability") or {}).get("trigger") or {}
        attach_to = result.get("attachTo")
        if attach_to == "event_card":
            owner_id = (action.get("source") or {}).get("ownerId") or player_id
            card_id = (action.get("source") or {}).get("cardId")
        else:
            owner_id = trigger.get("relatedOwnerId") or player_id
            card_id = trigger.get("relatedCardId")
            related_type = self.card_rules.get(card_id, {}).get("type")
            if related_type not in RULES_WILL_TYPES:
                return {
                    "kind": "create_effect_memory",
                    "status": "related_action_not_will",
                }
        memory = self.create_rules_effect_memory(
            owner_id, card_id, result.get("memoryKind"),
            controller_id=player_id,
            source_action_id=action.get("id"),
            data={
                "optional": bool(
                    result.get("optional")
                    and not action.get("optionalAccepted")
                ),
                "opponentPayment": result.get("opponentPayment"),
                "rollReturnOrExile": bool(result.get("rollReturnOrExile")),
                "requireLostConfrontation": bool(result.get("requireLostConfrontation")),
                "effectSourceCardId": (action.get("source") or {}).get("cardId"),
            },
        )
        return {
            "kind": "create_effect_memory",
            "status": "created" if memory else "invalid",
            "memoryId": memory.get("id") if memory else None,
            "memoryKind": result.get("memoryKind"),
            "cardId": card_id,
            "ownerId": owner_id,
        }

    def _rules_result_resolve_target_stack_immediately(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") in {
                "stack_action", "stack_effect", "stack_item"
            }
        ), None)
        target_action = next((
            entry for entry in self.rules_engine.get("actionStack") or []
            if entry.get("id") == (target or {}).get("actionId")
        ), None)
        if target_action is None:
            return {
                "kind": result.get("kind"),
                "status": "target_missing",
            }
        self.rules_engine["actionStack"].remove(target_action)
        self.rules_engine["actionStack"].append(target_action)
        nested = self.resolve_rules_top_action()
        return {
            "kind": result.get("kind"),
            "status": "resolved",
            "targetActionId": target_action.get("id"),
            "resolution": nested,
        }

    def _rules_result_schedule_rematch(self, action, result, player_id, player):
        protected_item_ids = [
            item_id for item_id in self.rules_engine.get(
                "firstManifestationItemIds", {}
            ).values()
            if self.find_battlefield_item(item_id)
        ]
        self.rules_engine["rematchPending"] = {
            "turn": self.phase_tracker["turn"],
            "controllerId": player_id,
            "protectedItemIds": protected_item_ids,
            "sourceActionId": action.get("id"),
        }
        return {
            "kind": "schedule_rematch",
            "status": "scheduled",
            "protectedItemIds": protected_item_ids,
        }

    def _rules_result_retarget_source_effect(self, action, result, player_id, player):
        source_item_id = (action.get("source") or {}).get("itemId")
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "card"
        ), None)
        target_item = self.find_battlefield_item(
            target.get("itemId") if target else None
        )
        effect = next((
            entry for entry in reversed(
                self.rules_engine.get("ongoingEffects") or []
            )
            if entry.get("source", {}).get("itemId") == source_item_id
            and entry.get("kind") == result.get("effectKind")
        ), None)
        if target_item is None:
            return {
                "kind": "retarget_source_effect",
                "status": "target_missing",
            }
        if effect is None:
            # Cleanse or the old target leaving removes the modifier, but the
            # persistent Will can still use its printed retargeting ability.
            source_item = self.find_battlefield_item(source_item_id)
            source_rules = self.rules_item_card_rules(source_item) if source_item else {}
            template = next((
                ability for ability in [*(source_rules.get("triggeredAbilities") or []),
                                        *(source_rules.get("playedAbilities") or [])]
                if (ability.get("ongoingEffect") or {}).get("kind") == result.get("effectKind")
            ), None)
            effects = self.create_rules_ongoing_effects({
                **action, "targets": [target], "ability": template,
            }) if template else []
            if not effects:
                return {"kind": "retarget_source_effect", "status": "target_missing"}
            return {
                "kind": "retarget_source_effect", "status": "retargeted",
                "effectId": effects[0]["id"], "previousItemId": None, "itemId": target_item["id"],
            }
        previous_item_id = effect.get("target", {}).get("itemId")
        powers_before = self.rules_field_power_snapshot()
        effect["target"] = {
            "kind": "card",
            "itemId": target_item.get("id"),
            "cardId": target_item.get("cardId"),
            "ownerId": target_item.get("ownerId"),
        }
        self.record_rules_power_changes(powers_before)
        return {
            "kind": "retarget_source_effect",
            "status": "retargeted",
            "effectId": effect.get("id"),
            "previousItemId": previous_item_id,
            "itemId": target_item.get("id"),
        }

    def _rules_result_resolve_effect_memory(self, action, result, player_id, player):
        if (
            result.get("kind") == "resolve_effect_memory"
            and len(result.get("memoryIds") or []) > 1
        ):
            results = []
            for memory_id in result["memoryIds"]:
                single = dict(action)
                single["ability"] = {
                    **(action.get("ability") or {}),
                    "result": {"kind": "resolve_effect_memory", "memoryId": memory_id},
                }
                results.append(self.apply_rules_action_result(single) or {})
            moved = [entry for entry in results if entry.get("movement")]
            return {
                "kind": "resolve_effect_memory",
                "status": "moved" if moved else (results[0].get("status") if results else "memory_missing"),
                "memoryIds": list(result["memoryIds"]),
                "cardIds": [entry.get("cardId") for entry in results if entry.get("cardId")],
                "results": results,
            }
        if result.get("kind") == "resolve_effect_memory":
            memory = next((
                entry for entry in self.rules_engine.get("effectMemories") or []
                if entry.get("id") == result.get("memoryId")
            ), None)
            if memory is None:
                return {
                    "kind": "resolve_effect_memory",
                    "status": "memory_missing",
                }
            owner_id = memory.get("ownerId")
            card_id = memory.get("cardId")
            if memory.get("kind") == "move_to_deck_at_resolution":
                item = self.find_battlefield_item(
                    (memory.get("data") or {}).get("itemId")
                )
                if item is None:
                    self.remove_rules_effect_memory(memory["id"])
                    return {
                        "kind": "resolve_effect_memory",
                        "status": "card_not_on_field",
                        "memoryId": memory["id"],
                        "cardId": card_id,
                    }
                movement = self._rules_remove_field_item_by_effect(
                    item, owner_id, "deck", "bottom"
                )
                self.remove_rules_effect_memory(memory["id"])
                return {
                    "kind": "resolve_effect_memory",
                    "status": movement.get("status"),
                    "memoryId": memory["id"],
                    "cardId": card_id,
                    "movement": movement,
                }
            if card_id not in self.players.get(owner_id, {}).get("zones", {}).get("graveyard", []):
                self.remove_rules_effect_memory(memory["id"])
                return {
                    "kind": "resolve_effect_memory",
                    "status": "card_not_in_limbo",
                    "memoryId": memory["id"],
                    "cardId": card_id,
                }
            data = memory.get("data") or {}
            if data.get("requireLostConfrontation"):
                if not self.rules_player_lost_confrontation_this_turn(memory.get("controllerId")):
                    self.remove_rules_effect_memory(memory["id"])
                    return {
                        "kind": "resolve_effect_memory",
                        "status": "condition_failed",
                        "memoryId": memory["id"], "cardId": card_id,
                    }
            if data.get("rollReturnOrExile"):
                roll = random.randint(1, 6)
                destination = "hand" if roll % 2 == 0 else "exile"
                error, _owner_id, replacement = self.move_zone_card_by_effect(
                    owner_id, "graveyard", owner_id, destination, card_id, "top"
                )
                self.remove_rules_effect_memory(memory["id"])
                return {
                    "kind": "resolve_effect_memory",
                    "status": "target_missing" if error else replacement["status"] if replacement else (
                        "returned" if destination == "hand" else "exiled"
                    ),
                    "memoryId": memory["id"], "cardId": card_id, "roll": roll,
                }
            opponent_payment = data.get("opponentPayment")
            if opponent_payment:
                opponent_id = self.other_rules_player_id(memory.get("controllerId"))
                choice_id = new_id()
                self.rules_engine["pendingChoice"] = {
                    "id": choice_id,
                    "kind": "effect_memory_payment",
                    "playerId": opponent_id,
                    "payment": opponent_payment,
                    "requirements": self.rules_requirements_from_symbols(opponent_payment),
                    "memoryId": memory["id"],
                    "sourceCardId": card_id,
                    "targetCardId": card_id,
                }
                return {
                    "kind": "choice_required",
                    "choiceId": choice_id,
                    "choiceKind": "effect_memory_payment",
                    "playerId": opponent_id,
                    "payment": opponent_payment,
                    "memoryId": memory["id"],
                    "cardId": card_id,
                }
            if data.get("optional") and not action.get("optionalAccepted"):
                choice_id = new_id()
                self.rules_engine["pendingChoice"] = {
                    "id": choice_id,
                    "kind": "effect_memory_return",
                    "playerId": owner_id,
                    "memoryId": memory["id"],
                    "sourceCardId": card_id,
                    "options": ["return", "decline"],
                }
                return {
                    "kind": "choice_required",
                    "choiceId": choice_id,
                    "choiceKind": "effect_memory_return",
                    "playerId": owner_id,
                    "memoryId": memory["id"],
                    "cardId": card_id,
                }
            error, _owner_id, replacement = self.move_zone_card_by_effect(
                owner_id, "graveyard", owner_id, "hand", card_id, "top"
            )
            self.remove_rules_effect_memory(memory["id"])
            return {
                "kind": "resolve_effect_memory",
                "status": (
                    "target_missing" if error
                    else replacement["status"] if replacement
                    else "returned"
                ),
                "memoryId": memory["id"],
                "cardId": card_id,
                "playerId": owner_id,
            }

    def _rules_result_cancel_target_stack_effect(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "stack_effect"
        ), None)
        target_action = next((
            entry for entry in self.rules_engine.get("actionStack") or []
            if target and entry.get("id") == target.get("actionId")
        ), None)
        if target_action is None:
            return {"kind": result.get("kind"), "status": "target_missing"}
        countered = self.counter_rules_stack_action(target_action, "cancel")
        return {"kind": result.get("kind"), **(countered or {"status": "target_missing"})}

    def _rules_result_retarget_stack_action(self, action, result, player_id, player):
        stack_entry = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") in {"stack_action", "stack_effect", "stack_item"}
        ), None)
        new_target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "card"
        ), None)
        target_action = next((
            entry for entry in self.rules_engine.get("actionStack") or []
            if stack_entry and entry.get("id") == stack_entry.get("actionId")
        ), None)
        if target_action is None or new_target is None:
            return {"kind": result.get("kind"), "status": "target_missing"}
        error = self.rules_retarget_error([stack_entry, new_target])
        if error:
            return {"kind": result.get("kind"), "status": "invalid_target", "error": error}
        replaced = False
        updated = []
        for entry in target_action.get("targets") or []:
            if not replaced and entry.get("kind") == "card":
                updated.append(dict(new_target))
                replaced = True
            else:
                updated.append(entry)
        target_action["targets"] = updated
        if isinstance(target_action.get("target"), dict) and target_action["target"].get("kind") == "card":
            target_action["target"] = dict(new_target)
        return {
            "kind": result.get("kind"), "status": "retargeted",
            "actionId": target_action.get("id"),
            "cardId": (target_action.get("source") or {}).get("cardId"),
            "newTarget": dict(new_target),
        }

    def _rules_result_neutralize_stack_action(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "stack_action"
        ), None)
        target_action = next((
            entry for entry in self.rules_engine.get("actionStack") or []
            if target and entry.get("id") == target.get("actionId")
        ), None)
        if target_action is None:
            return {
                "kind": "neutralize_stack_action", "status": "target_missing",
                "actionId": target.get("actionId") if target else None,
                "cardId": target.get("cardId") if target else None,
            }
        countered = self.counter_rules_stack_action(
            target_action, "neutralize",
            result.get("destination") or "graveyard",
        )
        if result.get("refundEssence") and countered.get("status") != "prevented":
            refunded = self.rules_refund_stack_action_essence(target_action)
            if refunded:
                countered["refundedEssence"] = refunded
        return {
            "kind": "neutralize_stack_action",
            **countered,
        }

    def _rules_result_counter_stack_action_unless_payment(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") in {"stack_action", "stack_effect"}
        ), None)
        target_action = next((
            entry for entry in self.rules_engine.get("actionStack") or []
            if target and entry.get("id") == target.get("actionId")
        ), None)
        if target_action is None:
            return {
                "kind": "counter_stack_action_unless_payment", "status": "target_missing",
                "actionId": target.get("actionId") if target else None,
                "cardId": target.get("cardId") if target else None,
                "mode": result.get("mode"),
            }
        payer_id = (
            (target_action.get("source") or {}).get("ownerId")
            if result.get("payer") == "owner"
            else target_action.get("controllerId")
        )
        if payer_id not in self.players:
            payer_id = target_action.get("controllerId")
        choice_id = new_id()
        requirements = self.rules_requirements_from_symbols(result.get("payment"))
        self.rules_engine["pendingChoice"] = {
            "id": choice_id,
            "kind": "stack_counter_payment",
            "playerId": payer_id,
            "payment": result.get("payment"),
            "requirements": requirements,
            "mode": result.get("mode"),
            "actionId": action.get("id"),
            "controllerId": action.get("controllerId"),
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "targetActionId": target_action.get("id"),
            "targetCardId": (target_action.get("source") or {}).get("cardId"),
            "targetControllerId": target_action.get("controllerId"),
            "targetKind": target.get("kind"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "stack_counter_payment", "playerId": payer_id,
            "payment": result.get("payment"), "requirements": requirements,
            "mode": result.get("mode"),
            "targetActionId": target_action.get("id"),
            "targetCardId": (target_action.get("source") or {}).get("cardId"),
            "targetKind": target.get("kind"),
        }

    def _rules_result_copy_stack_action(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "stack_action"
        ), None)
        target_action = next((
            entry for entry in self.rules_engine.get("actionStack") or []
            if target and entry.get("id") == target.get("actionId")
        ), None)
        if not self.rules_stack_target_matches(target_action, "stack_action"):
            return {
                "kind": "copy_stack_action", "status": "target_missing",
                "actionId": target.get("actionId") if target else None,
                "cardId": target.get("cardId") if target else None,
            }
        target_rules = self.rules_action_target_rules(target_action)
        copied_action = self.build_rules_stack_copy(target_action, player_id, action.get("id"))
        if target_rules and (target_rules.get("groups") or int(target_rules.get("max") or 0) > 0):
            choice_id = new_id()
            original_targets = [dict(entry) for entry in target_action.get("targets") or []]
            self.rules_engine["pendingChoice"] = {
                "id": choice_id,
                "kind": "stack_copy_targets",
                "playerId": player_id,
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "targetActionId": target_action.get("id"),
                "targetCardId": (target_action.get("source") or {}).get("cardId"),
                "targetRules": target_rules,
                "originalTargets": original_targets,
                "_copyAction": copied_action,
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "stack_copy_targets", "playerId": player_id,
                "targetActionId": target_action.get("id"),
                "targetCardId": (target_action.get("source") or {}).get("cardId"),
            }
        self.rules_engine["actionStack"].append(copied_action)
        return {
            "kind": "copy_stack_action", "status": "copied",
            "actionId": copied_action["id"],
            "copiedFromActionId": target_action.get("id"),
            "cardId": (target_action.get("source") or {}).get("cardId"),
            "targets": [dict(entry) for entry in copied_action.get("targets") or []],
        }
