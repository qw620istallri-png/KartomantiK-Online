"""Resolving the top of the Stack and passing priority."""

from .common import ADVANCED_PHASES
from .replacements import replacement_checkpoint


class ResolutionMixin:
    def rules_valid_action_target_indices(self, action, target_rules):
        """Revalidate each declared target without changing grouped target roles."""
        targets = action.get("targets") or []
        groups = target_rules.get("groups")
        if isinstance(groups, list):
            if len(groups) != len(targets):
                return None
            contracts = groups
        else:
            minimum = max(0, int(target_rules.get("min") or 0))
            maximum = max(minimum, len(targets) if target_rules.get("anyNumber") else int(target_rules.get("max") or minimum))
            if not minimum <= len(targets) <= maximum:
                return None
            contracts = [{**target_rules, "min": 1, "max": 1}] * len(targets)
        return [
            index for index, (contract, target) in enumerate(zip(contracts, targets))
            if self.rules_ability_targets_error(
                contract, [target], action.get("controllerId"),
                event_item_id=((action.get("ability") or {}).get("trigger") or {}).get("eventItemId"),
                source_item_id=(action.get("source") or {}).get("itemId"),
            ) is None
        ]

    def rules_top_action_has_no_valid_targets(self):
        engine = self.rules_engine
        if (
            not engine.get("enabled") or not self.phase_tracker.get("enabled")
            or self.ended or len(self.players) < 2 or engine.get("pendingChoice")
            or not engine.get("actionStack") or not self.rules_match_started()
            or self.rules_first_manifestation_active() or self.rules_recovery_mulligan_active()
        ):
            return False
        action = engine["actionStack"][-1]
        targets = action.get("targets") or []
        target_rules = self.rules_action_target_rules(action)
        # Untargeted effects and choices made during resolution still need their
        # normal response window. Never inspect a lower Stack entry here.
        if not targets or target_rules is None:
            return False
        return self.rules_valid_action_target_indices(action, target_rules) == []

    @replacement_checkpoint("resolution")
    def resolve_rules_top_action(self):
        if self.ended:
            return None
        action_stack = self.rules_engine["actionStack"]
        if not action_stack:
            return None
        resolved = action_stack.pop()
        power_before_resolution = {
            item.get("id"): self.rules_manifestation_characteristics(item)["power"]
            for item in self.battlefield
            if item.get("faceUp")
            and (
                self.rules_item_card_rules(item).get("type") == "manifestation"
                or item.get("isTokenCard")
            )
        }
        source_resolution = self.resolve_rules_action_source(resolved)
        if source_resolution:
            resolved["sourceResolution"] = source_resolution
        triggered_actions = []
        if (
            source_resolution and source_resolution.get("destination") == "battlefield"
            and source_resolution.get("status") == "moved"
            and source_resolution.get("enteredBattlefield", True)
        ):
            triggered_actions = self.queue_rules_battlefield_entry_triggers(
                source_resolution.get("cardId"), resolved.get("controllerId"),
                source_resolution.get("itemId"), True,
                event_targets=resolved.get("targets"),
                defer=True,
            )
            entered_item = self.find_battlefield_item(
                source_resolution.get("itemId")
            )
            triggered_actions.extend(
                self.queue_rules_manifestation_entry_watchers(
                    entered_item, defer=True
                )
            )
            triggered_actions.extend(
                self.queue_rules_persistent_will_entry_watchers(
                    entered_item, defer=True
                )
            )
        if (
            source_resolution and source_resolution.get("fieldZone") == "interzone"
            and source_resolution.get("status") == "moved"
        ):
            interzone_item = self.find_battlefield_item(source_resolution.get("itemId"))
            if interzone_item and self.rules_field_zone(interzone_item) == "interzone":
                triggered_actions.extend(
                    self.queue_rules_field_zone_entry_triggers(
                        interzone_item, "interzone",
                        event_targets=resolved.get("targets"), defer=True,
                    )
                )
        if source_resolution and source_resolution.get("asSupport"):
            support_item = self.find_battlefield_item(source_resolution.get("itemId"))
            triggered_actions.extend(self.queue_rules_support_entry_triggers(
                support_item, played=True, from_zone=source_resolution.get("fromZone"),
                event_targets=resolved.get("targets"), defer=True,
            ))
            triggered_actions.extend(
                self.queue_rules_field_zone_entry_triggers(
                    support_item, "confrontation",
                    event_targets=resolved.get("targets"), defer=True
                )
            )
        target_rules = self.rules_action_target_rules(resolved)
        target_error = self.rules_ability_targets_error(
            target_rules,
            resolved.get("targets") or [],
            resolved.get("controllerId"),
            event_item_id=(
                (resolved.get("ability") or {}).get("trigger") or {}
            ).get("eventItemId"),
            source_item_id=(resolved.get("source") or {}).get("itemId"),
        ) if target_rules is not None else None
        execution_action = resolved
        if target_error:
            valid_indices = self.rules_valid_action_target_indices(resolved, target_rules)
            original_targets = resolved.get("targets") or []
            if valid_indices and len(valid_indices) < len(original_targets):
                # Keep the declaration intact for logs. Group positions carry
                # roles (e.g. counter donor/recipient), so never compact them.
                grouped = isinstance(target_rules.get("groups"), list)
                execution_action = {
                    **resolved,
                    "targets": [
                        target if index in valid_indices else {"kind": "invalid_target"}
                        for index, target in enumerate(original_targets)
                        if grouped or index in valid_indices
                    ],
                }
                resolved["invalidTargetIndices"] = [
                    index for index in range(len(original_targets)) if index not in valid_indices
                ]
                target_error = None
        if target_error:
            resolved["targetValidationError"] = target_error
            resolved["effectResult"] = {
                "kind": "invalid_targets",
                "status": "no_effect",
                "error": target_error,
            }
        else:
            effect_result = self.apply_rules_action_result(execution_action)
            if effect_result:
                resolved["effectResult"] = effect_result
                if isinstance(effect_result, dict):
                    triggered_actions.extend(
                        effect_result.pop("resolutionTriggers", None) or []
                    )
            ongoing_effects = self.create_rules_ongoing_effects(execution_action)
            if ongoing_effects:
                resolved["ongoingEffects"] = ongoing_effects
                for effect in ongoing_effects:
                    if effect.get("kind") == "copy_power_effects":
                        triggered_actions.extend(
                            self.queue_rules_copied_entry_triggers(effect)
                        )
        state_actions = self.resolve_rules_state_actions(power_before_resolution, pending_triggers=triggered_actions)
        if state_actions["destroyed"]:
            resolved["stateActions"] = {
                "destroyed": state_actions["destroyed"],
            }
        if state_actions["replacements"]:
            resolved.setdefault("stateActions", {})["replacements"] = (
                state_actions["replacements"]
            )
        if state_actions["thresholdExiled"]:
            resolved.setdefault("stateActions", {})["thresholdExiled"] = (
                state_actions["thresholdExiled"]
            )
        triggered_actions.extend(state_actions["triggeredActions"])
        triggered_actions.extend(
            self.queue_rules_observed_event_triggers(defer=True)
        )
        if triggered_actions:
            self.queue_or_defer_rules_simultaneous_actions(triggered_actions)
        self.rules_engine["lastResolvedAction"] = resolved
        if action_stack:
            next_controller = action_stack[-1]["controllerId"]
            next_priority = self.other_rules_player_id(next_controller)
        else:
            normal_priority = (
                self.rules_lowest_confrontation_power_player()
                if self.current_phase_group() == "confrontation"
                else self.rules_engine.get("lastConfrontationWinnerId")
            )
            next_priority = (
                normal_priority if normal_priority in self.players
                else self.other_rules_player_id(resolved["controllerId"])
            )
        if (
            resolved.get("immediate") and not action_stack
            and ((resolved.get("ability") or {}).get("result") or {}).get("kind") == "grant_source_support_until_end_turn"
        ):
            # paying the cost is immediate: the player keeps priority to play the card in Support right away
            next_priority = resolved.get("controllerId")
        self.rules_engine["priorityPlayerId"] = next_priority
        return {
            "status": "resolved",
            "action": resolved,
            "triggeredActions": triggered_actions,
            "stackDepth": len(action_stack),
        }

    def resolve_rules_immediate_actions(self):
        resolved = []
        while (
            not self.ended and self.rules_engine["actionStack"]
            and self.rules_engine["actionStack"][-1].get("immediate")
            and not self.rules_engine.get("pendingChoice")
        ):
            result = self.resolve_rules_top_action()
            if result and result.get("status") == "resolved":
                resolved.append(result)
        if not self.ended and not self.rules_engine.get("pendingChoice") and not any(action.get("immediate") for action in self.rules_engine["actionStack"]):
            deferred = self.rules_engine.pop("deferredAfterImmediateActions", [])
            valid = []
            for action in deferred:
                trigger = (action.get("ability") or {}).get("trigger") or {}
                source = action.get("source") or {}
                if trigger.get("event") in {"enters_field", "enters_field_zone", "revelation", "reaction"}:
                    item = self.find_battlefield_item(source.get("itemId"))
                    if item is None or not self.rules_item_effects_active(item):
                        continue
                valid.append(action)
            if valid:
                self.queue_rules_simultaneous_actions(valid)
        return resolved

    @replacement_checkpoint("priority")
    def pass_rules_priority(self, player_id, passed=None):
        if not self.rules_engine["enabled"]:
            return "Assisted rules are not active.", None
        if self.ended or player_id not in self.players:
            return "Unable to pass priority.", None
        if len(self.players) < 2:
            return "Both players must join before using priority.", None
        if self.rules_engine.get("pendingChoice"):
            return "A required card choice must be completed first.", None
        if self.rules_engine["actionStack"] and self.rules_engine["actionStack"][-1].get("immediate"):
            return "Immediate Effects must resolve before priority can be passed.", None
        if self.rules_recovery_mulligan_active():
            return "Complete the required Recovery Mulligan before playing.", None
        if passed is False:
            if self.rules_engine["priorityPasses"] == [player_id]:
                self.rules_engine["priorityPasses"] = []
                self.rules_engine["priorityPlayerId"] = player_id
                return None, {
                    "status": "cancelled",
                    "stackDepth": len(self.rules_engine["actionStack"]),
                }
            return "You have not passed priority.", None
        if self.rules_engine["priorityPlayerId"] != player_id:
            return "You do not have priority.", None
        # Freenya: the free Limbo play is offered once, when its effect resolves.
        self.rules_engine["playPermissions"] = [
            entry for entry in self.rules_engine.get("playPermissions") or []
            if not (
                entry.get("playerId") == player_id
                and entry.get("fromZone") == "graveyard"
                and entry.get("exileOnLeave")
                and entry.get("anyWill")
            )
        ]

        previous_passes = self.rules_engine["priorityPasses"]
        if not previous_passes:
            self.rules_engine["priorityPasses"] = [player_id]
            self.rules_engine["priorityPlayerId"] = self.other_rules_player_id(player_id)
            return None, {
                "status": "passed",
                "stackDepth": len(self.rules_engine["actionStack"]),
            }

        self.rules_engine["priorityPasses"] = []
        action_stack = self.rules_engine["actionStack"]
        if action_stack:
            return None, self.resolve_rules_top_action()

        previous_phase_id = self.current_phase_id()
        if previous_phase_id == "end_expire":
            overflow = self.set_rules_hand_overflow_choice(list(self.players))
            if overflow:
                return None, {
                    "status": "choice_required",
                    "choiceKind": "hand_overflow",
                    "playerId": overflow["playerId"],
                    "stackDepth": 0,
                }
        powers_before_phase = {
            item.get("id"): self.rules_manifestation_characteristics(item)["power"]
            for item in self.battlefield if item.get("faceUp")
        }
        sequence = self.phase_sequence()
        next_index = self.phase_tracker["index"] + 1
        started_new_turn = False
        rematch_started = False
        expired_essence_tokens = []
        rematch = self.rules_engine.get("rematchPending") or {}
        if (
            previous_phase_id == "resolution_move"
            and int(rematch.get("turn") or 0) == self.phase_tracker["turn"]
        ):
            next_index = ADVANCED_PHASES.index("confrontation_reaction")
            rematch_started = True
        if next_index >= len(sequence):
            next_index = 0
            expired_essence_tokens = self.expire_rules_excess_essence(
                self.phase_tracker["turn"]
            )
            self.record_score_history(self.phase_tracker["turn"])
            self.phase_tracker["turn"] += 1
            started_new_turn = True
        self.phase_tracker["index"] = next_index
        expired_effects = self.prune_rules_ongoing_effects()
        phase_state_actions = self.resolve_rules_state_actions(powers_before_phase) if expired_effects else {}
        phase_triggers = list(phase_state_actions.get("triggeredActions") or [])
        if phase_state_actions:
            phase_triggers.extend(self.queue_rules_observed_event_triggers(defer=True))
        self.prune_rules_play_restrictions()
        self.phase_passes.clear()
        self.rules_engine["priorityPlayerId"] = self.other_rules_player_id(player_id)
        if rematch_started:
            first_ids = {}
            for item_id in rematch.get("protectedItemIds") or []:
                item = self.find_battlefield_item(item_id)
                if item:
                    controller_id = item.get("controllerId") or item.get("ownerId")
                    first_ids[controller_id] = item_id
            self.rules_engine["firstManifestationItemIds"] = first_ids
            self.rules_engine["firstManifestationValidatedPlayerIds"] = list(first_ids)
            self.rules_engine["firstManifestationComplete"] = True
            self.rules_engine["firstManifestationTriggersQueued"] = True
            self.rules_engine["confrontationResult"] = None
            self.rules_engine["rematchPending"] = None
        revealed_item_ids = []
        if (
            previous_phase_id == "confrontation_before_revelation"
            and self.current_phase_id() == "confrontation_reveal"
        ):
            for selected_id in self.rules_engine["firstManifestationItemIds"].values():
                item = self.find_battlefield_item(selected_id)
                if item:
                    item["faceUp"] = True
                    revealed_item_ids.append(selected_id)
        automatic_recovery = None
        beginning_triggered_actions = []
        end_triggered_actions = []
        resolution_triggered_actions = []
        readied_item_ids = []
        if started_new_turn:
            self.expire_rules_temporary_suspensions(
                self.phase_tracker["turn"] - 1
            )
            self.rules_engine["handLimitEffects"] = [
                effect for effect in self.rules_engine.get(
                    "handLimitEffects"
                ) or []
                if int(effect.get("turn") or 0) >= self.phase_tracker["turn"]
            ]
            readied_item_ids = self.ready_rules_exhausted_cards()
            self.reset_rules_confrontation_turn()
            self.grant_rules_beginning_turn_permissions()
            beginning_triggered_actions = self.queue_rules_beginning_turn_triggers(defer=True)
        if phase_triggers or beginning_triggered_actions:
            self.queue_or_defer_rules_simultaneous_actions([*phase_triggers, *beginning_triggered_actions])
        if started_new_turn and not beginning_triggered_actions and not phase_triggers and not self.rules_engine.get("pendingChoice"):
            self.phase_tracker["index"] = ADVANCED_PHASES.index("recovery_draw")
        if self.current_phase_id() == "confrontation_choose":
            self.register_rules_existing_first_manifestations()
        if (
            self.current_phase_id() == "recovery_draw"
            and self.rules_engine["recoveryDrawTurn"] != self.phase_tracker["turn"]
        ):
            recovery_error, automatic_recovery = self.resolve_recovery_draw()
            if recovery_error:
                return recovery_error, None
        if self.current_phase_group() == "confrontation":
            lower_power_player = self.rules_lowest_confrontation_power_player()
            if lower_power_player:
                self.rules_engine["priorityPlayerId"] = lower_power_player
        if self.current_phase_id() == "end_triggers":
            end_triggered_actions = self.build_rules_end_turn_field_triggers()
            end_triggered_actions.extend(
                self.queue_rules_end_turn_memory_triggers(defer=True)
            )
            if end_triggered_actions:
                self.queue_rules_simultaneous_actions(end_triggered_actions)
        if self.current_phase_id() == "confrontation_reaction":
            resolution_triggered_actions.extend(self.queue_rules_reaction_triggers())
        if self.current_phase_id() == "resolution_effects":
            resolution_triggered_actions = (
                self.queue_rules_resolution_memory_triggers()
            )
            resolution_triggered_actions.extend(
                self.queue_rules_confrontation_win_triggers()
            )
            resolution_triggered_actions.extend(
                self.queue_rules_resolution_field_triggers()
            )
        confrontation_result = None
        if self.current_phase_id() == "resolution_compare":
            confrontation_result = self.prepare_rules_confrontation_result()
        elif self.current_phase_id() == "resolution_move":
            confrontation_result = self.begin_rules_confrontation_cleanup()
            if isinstance(confrontation_result, dict):
                resolution_triggered_actions.extend(
                    confrontation_result.pop("triggeredActions", None) or []
                )
        return None, {
            "status": "advanced",
            "previousPhaseId": previous_phase_id,
            "phaseId": self.current_phase_id(),
            "turn": self.phase_tracker["turn"],
            "stackDepth": 0,
            "expiredEffectIds": [effect["id"] for effect in expired_effects],
            "confrontationResult": confrontation_result,
            "automaticRecovery": automatic_recovery,
            "beginningTriggeredActions": beginning_triggered_actions,
            "endTriggeredActions": end_triggered_actions,
            "resolutionTriggeredActions": resolution_triggered_actions,
            "phaseTriggeredActions": phase_triggers,
            "phaseStateActions": {key: value for key, value in phase_state_actions.items() if key != "triggeredActions"},
            "readiedItemIds": readied_item_ids,
            "revealedItemIds": revealed_item_ids,
            "expiredEssenceTokenIds": [
                token["id"] for token in expired_essence_tokens
            ],
            "rematchStarted": rematch_started,
        }
