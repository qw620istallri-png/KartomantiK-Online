"""Pending choices about the Stack: ordering, optional actions, targets and chains."""

from ..common import new_id


class StackChoicesMixin:
    def _rules_choice_optional_stack_action(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if option not in choice.get("options", []):
            return "Choose whether to put this optional effect on the Stack.", None
        action = choice.get("_action")
        if not isinstance(action, dict):
            self.rules_engine["pendingChoice"] = None
            return "This optional triggered effect is no longer available.", None
        accepted_actions = list(choice.get("_acceptedActions") or [])
        self.rules_engine["pendingChoice"] = None
        if option == "accept":
            action["optionalAccepted"] = True
            target_choice = action.pop("_preStackTargetChoice", None)
            if target_choice:
                self.rules_engine["pendingChoice"] = {
                    "id": new_id(),
                    "kind": "trigger_targets",
                    "playerId": player_id,
                    "sourceCardId": (
                        action.get("source") or {}
                    ).get("cardId"),
                    "targetRules": target_choice.get("targetRules") or {},
                    "_triggerAction": action,
                    "_resumeConfrontationCleanup": bool(
                        target_choice.get("resumeConfrontationCleanup")
                    ),
                    "_optionalStackBatch": {
                        "actions": choice.get("_actions") or [],
                        "nextIndex": int(choice.get("_nextIndex") or 0),
                        "acceptedActions": accepted_actions,
                        "priorityPlayerId": choice.get(
                            "_priorityPlayerId"
                        ),
                    },
                }
                self.rules_engine["priorityPasses"] = []
                self.rules_engine["priorityPlayerId"] = player_id
                return None, {
                    "kind": "optional_stack_action",
                    "status": "accepted",
                    "playerId": player_id,
                    "sourceCardId": choice.get("sourceCardId"),
                    "actionId": action.get("id"),
                    "nextChoiceId": self.rules_engine[
                        "pendingChoice"
                    ]["id"],
                }
            accepted_actions.append(action)
        self._continue_rules_optional_stack_choices(
            choice.get("_actions") or [],
            int(choice.get("_nextIndex") or 0),
            accepted_actions,
            choice.get("_priorityPlayerId"),
        )
        return None, {
            "kind": "optional_stack_action",
            "status": "accepted" if option == "accept" else "declined",
            "playerId": player_id,
            "sourceCardId": choice.get("sourceCardId"),
            "actionId": action.get("id"),
        }

    def _rules_choice_support_return_order(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        expected_ids = [
            item.get("itemId") for item in choice.get("items") or []
        ]
        supplied_ids = [str(item_id or "") for item_id in (card_ids or [])]
        if (
            len(supplied_ids) != len(expected_ids)
            or len(set(supplied_ids)) != len(supplied_ids)
            or set(supplied_ids) != set(expected_ids)
        ):
            return "Order every Support Manifestation exactly once.", None
        counts = dict(choice.get("_counts") or {})
        moved = []
        for item_id in reversed(supplied_ids):
            item = self.find_battlefield_item(item_id)
            if item is None or not item.get("isSupport"):
                continue
            controller_id = self.rules_item_controller_id(item)
            movement = self._rules_remove_field_item(
                item, item.get("ownerId"), "deck", "top"
            )
            moved.append(movement)
            counts[controller_id] = counts.get(controller_id, 0) + 1
        self.rules_engine["pendingChoice"] = None
        continuation = self._continue_rules_support_return_groups(
            choice.get("_remainingGroups") or [],
            counts,
            choice.get("_action") or {},
        )
        return None, {
            "kind": "support_return_order",
            "status": (
                "continued"
                if continuation.get("kind") == "support_return_order"
                else "completed"
            ),
            "playerId": player_id,
            "itemIds": supplied_ids,
            "movements": moved,
            "nextChoiceId": (
                continuation.get("id")
                if continuation.get("kind") == "support_return_order"
                else None
            ),
            "counts": continuation.get("counts"),
        }

    def _rules_choice_simultaneous_stack_order(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        group = choice.get("_group") or []
        expected_ids = [action.get("id") for action in group]
        supplied_ids = [str(action_id or "") for action_id in (card_ids or [])]
        if (
            len(supplied_ids) != len(expected_ids)
            or len(set(supplied_ids)) != len(supplied_ids)
            or set(supplied_ids) != set(expected_ids)
        ):
            return "Order every simultaneous Stack action exactly once.", None
        actions_by_id = {action["id"]: action for action in group}
        supplied_actions = [actions_by_id[action_id] for action_id in supplied_ids]
        first_immediate = next((
            index for index, action in enumerate(supplied_actions)
            if action.get("immediate")
        ), len(supplied_actions))
        if any(
            not action.get("immediate")
            for action in supplied_actions[first_immediate:]
        ):
            return "Immediate Effects must remain above other simultaneous actions.", None
        ordered_actions = list(choice.get("_orderedActions") or [])
        ordered_actions.extend(supplied_actions)
        remaining_groups = list(choice.get("_remainingGroups") or [])
        self.rules_engine["pendingChoice"] = None
        completed = self._continue_rules_simultaneous_batch(
            remaining_groups, ordered_actions
        )
        next_choice = self.rules_engine.get("pendingChoice")
        return None, {
            "kind": "simultaneous_stack_order",
            "playerId": player_id,
            "actionIds": supplied_ids,
            "completed": completed,
            "nextPlayerId": (
                next_choice.get("playerId")
                if next_choice and next_choice.get("kind") == "simultaneous_stack_order"
                else None
            ),
            "stackDepth": len(self.rules_engine["actionStack"]),
        }

    def _rules_choice_optional_trigger(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if option not in choice.get("options", []):
            return "Choose whether to use the optional triggered effect.", None
        status = "declined"
        created_item_id = None
        copy_triggered = []
        if option == "accept":
            source_item = self.find_battlefield_item(
                choice.get("_sourceItemId")
            )
            if (
                source_item is None
                or int(round(float(source_item.get("rotation") or 0))) % 180
            ):
                return "The optional source is no longer ready.", None
            source_item["rotation"] = 90.0
            copy = self.create_rules_token_copy(
                choice.get("_relatedCardId"), player_id,
                source_item_id=source_item.get("id"),
            )
            created_item_id = copy["id"]
            self.rules_engine["pendingChoice"] = None
            copy_triggered = self.queue_rules_token_copy_entry_triggers(copy)
            status = "accepted"
        else:
            self.rules_engine["pendingChoice"] = None
        return None, {
            "kind": "optional_trigger",
            "status": status,
            "playerId": player_id,
            "sourceCardId": choice.get("sourceCardId"),
            "relatedCardId": choice.get("_relatedCardId"),
            "createdItemId": created_item_id,
            "triggeredActions": copy_triggered,
        }

    def _rules_choice_trigger_targets(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        target_error, clean_targets = self.rules_action_targets(targets, player_id)
        if target_error:
            return target_error, None
        ability_error = self.rules_ability_targets_error(
            choice.get("targetRules"), clean_targets, player_id,
            source_item_id=(
                (choice.get("_triggerAction") or {}).get("source") or {}
            ).get("itemId"),
            source_card_id=choice.get("sourceCardId"),
        )
        if ability_error:
            return ability_error, None
        action = choice.get("_triggerAction")
        if not isinstance(action, dict):
            self.rules_engine["pendingChoice"] = None
            return "This triggered effect is no longer available.", None
        clean_targets = self.rules_redirect_targets(
            action.get("controllerId") or player_id, clean_targets
        )
        action["targets"] = clean_targets
        resume_cleanup = bool(choice.get("_resumeConfrontationCleanup"))
        optional_batch = choice.get("_optionalStackBatch")
        self.rules_engine["pendingChoice"] = None
        if optional_batch:
            self._continue_rules_optional_stack_choices(
                optional_batch.get("actions") or [],
                int(optional_batch.get("nextIndex") or 0),
                [
                    *(optional_batch.get("acceptedActions") or []),
                    action,
                ],
                optional_batch.get("priorityPlayerId"),
            )
        else:
            self.queue_rules_simultaneous_actions([action])
        if resume_cleanup:
            self._queue_next_rules_confrontation_destination()
        return None, {
            "kind": "trigger_targets",
            "playerId": player_id,
            "sourceCardId": choice.get("sourceCardId"),
            "actionId": action.get("id"),
            "targets": clean_targets,
        }

    def _rules_choice_stack_copy_targets(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if option not in {"keep", "retarget"}:
            return "Choose whether to keep or replace the copied Will's target.", None
        copied_action = choice.get("_copyAction")
        if not isinstance(copied_action, dict):
            self.rules_engine["pendingChoice"] = None
            return "The copied Stack action is no longer available.", None
        selected_targets = choice.get("originalTargets") if option == "keep" else targets
        target_error, clean_targets = self.rules_action_targets(selected_targets)
        if target_error:
            return target_error, None
        ability_error = self.rules_ability_targets_error(
            choice.get("targetRules"), clean_targets, player_id,
        )
        if ability_error:
            return ability_error, None
        copied_action["targets"] = clean_targets
        self.rules_engine["actionStack"].append(copied_action)
        self.rules_engine["pendingChoice"] = None
        self.rules_engine["priorityPasses"] = []
        self.rules_engine["priorityPlayerId"] = self.other_rules_player_id(player_id)
        return None, {
            "kind": "stack_copy_targets", "status": "copied",
            "playerId": player_id, "choiceId": choice_id,
            "sourceCardId": choice.get("sourceCardId"),
            "targetCardId": choice.get("targetCardId"),
            "targetActionId": choice.get("targetActionId"),
            "copyActionId": copied_action.get("id"),
            "keptOriginalTargets": option == "keep",
            "targets": [dict(entry) for entry in clean_targets],
        }

    def _rules_choice_stack_counter_payment(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if option not in {"pay", "decline"}:
            return "Choose whether to pay the requested Tribute.", None
        target_action = next((
            action for action in self.rules_engine.get("actionStack") or []
            if action.get("id") == choice.get("targetActionId")
        ), None)
        if not self.rules_stack_target_matches(target_action, choice.get("targetKind")):
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "stack_counter_payment", "status": "target_missing",
                "playerId": player_id, "choiceId": choice_id,
                "sourceCardId": choice.get("sourceCardId"),
                "targetActionId": choice.get("targetActionId"),
                "targetCardId": choice.get("targetCardId"),
                "mode": choice.get("mode"),
            }
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
                "kind": "stack_counter_payment", "status": "paid",
                "playerId": player_id, "choiceId": choice_id,
                "sourceCardId": choice.get("sourceCardId"),
                "targetActionId": choice.get("targetActionId"),
                "targetCardId": choice.get("targetCardId"),
                "mode": choice.get("mode"),
                "cost": {
                    "tributeCardIds": payment["cardIds"],
                    "tributeRequirements": payment["requirements"],
                    "essenceSpent": payment["essenceSpent"],
                    "excessEssence": payment["excessEssence"],
                },
                "triggeredActions": triggered_actions,
            }
        countered = self.counter_rules_stack_action(target_action, choice.get("mode"))
        self.rules_engine["pendingChoice"] = None
        return None, {
            "kind": "stack_counter_payment", "playerId": player_id,
            "choiceId": choice_id, "sourceCardId": choice.get("sourceCardId"),
            "targetActionId": choice.get("targetActionId"),
            "targetCardId": choice.get("targetCardId"),
            "mode": choice.get("mode"),
            **countered,
        }

    def _rules_choice_chain_manifestation(self, player_id, choice_id, choice, card_ids, option, item_id, placement, targets):
        if option == "decline":
            if not choice.get("optional"):
                return "This Chain effect cannot be declined.", None
            self.rules_engine["pendingChoice"] = None
            self.queue_rules_chain_continuation(choice)
            return None, {
                "kind": "chain_manifestation", "status": "declined",
                "playerId": player_id, "fromZone": choice.get("fromZone"),
                "sourceCardId": choice.get("sourceCardId"),
            }
        if not isinstance(card_ids, list) or len(card_ids) != 1 or not isinstance(card_ids[0], str):
            return "Choose one Manifestation to Chain.", None
        card_id = card_ids[0]
        zone = choice.get("fromZone")
        if card_id not in choice.get("_cardIds", []):
            return "The selected Manifestation is not eligible for this Chain effect.", None
        container_id = (
            (choice.get("_cardContainers") or {}).get(card_id)
            if zone == "receptacle" else player_id
        )
        if container_id not in self.players or card_id not in self.players[
            container_id
        ]["zones"].get(zone, []):
            return "The selected Manifestation is no longer in the required zone.", None
        if self.card_rules.get(card_id, {}).get("type") != "manifestation":
            return "Only a Manifestation can be Chained.", None
        if zone == "hand" and self.rules_hands_are_immune():
            return "Cards in Hand are Immune to cards and effects.", None
        self.rules_engine["pendingChoice"] = None
        self.queue_rules_chain_continuation(choice)
        return self.chain_rules_manifestation(
            player_id, zone, card_id, container_id=container_id,
            placement=placement,
            win_destination=choice.get("winDestination"),
            action_id=choice.get("actionId"),
            source_card_id=choice.get("sourceCardId"),
            shuffle_after=bool(choice.get("shuffleAfter")),
            return_to_vessel=bool(choice.get("returnToVessel")),
            after_chain=choice.get("afterChain"),
            chain_abilities=choice.get("chainAbilities"),
            chain_controller_id=choice.get("controllerId"),
            action_targets=choice.get("_actionTargets"),
        )
