"""Phase sequence and the per-turn phase tracker."""

from .common import (
    NORMAL_PHASES, ADVANCED_PHASES, PHASE_GROUP, make_rules_engine,
)


class PhasesMixin:
    # -- shared phase tracker -------------------------------------------
    def phase_sequence(self):
        return ADVANCED_PHASES if self.phase_tracker["advanced"] else NORMAL_PHASES

    def current_phase_id(self):
        sequence = self.phase_sequence()
        return sequence[min(self.phase_tracker["index"], len(sequence) - 1)]

    def current_phase_group(self):
        phase_id = self.current_phase_id()
        return PHASE_GROUP.get(phase_id, phase_id)

    def configure_phases(self, enabled=None, advanced=None):
        if self.rules_engine["enabled"]:
            # Assisted rules use the exact rulebook steps. They are selected
            # before the match and cannot silently fall back to the four-step
            # presentation once play has started.
            self.phase_tracker["enabled"] = True
            self.phase_tracker["advanced"] = True
            return
        # Showing or hiding the phase bubbles is client-local. Even a direct
        # enabled toggle must preserve the shared phase, turn, and pass state.
        if enabled is not None:
            self.phase_tracker["enabled"] = bool(enabled)
        if advanced is not None and bool(advanced) != self.phase_tracker["advanced"]:
            current_group = self.current_phase_group()
            self.phase_tracker["advanced"] = bool(advanced)
            sequence = self.phase_sequence()
            self.phase_tracker["index"] = next(
                (index for index, phase_id in enumerate(sequence) if PHASE_GROUP.get(phase_id, phase_id) == current_group),
                0,
            )
            self.phase_passes.clear()

    def pass_phase(self, player_id, passed=None):
        if self.ended or not self.phase_tracker["enabled"] or player_id not in self.players:
            return None
        # New clients send the state they want, making pass/cancel idempotent
        # across delayed or duplicated websocket messages. ``None`` preserves
        # the toggle semantics used by older clients.
        if passed is False or (passed is None and player_id in self.phase_passes):
            self.phase_passes.discard(player_id)
            return "cancelled"
        if passed is True and player_id in self.phase_passes:
            return "passed"
        self.phase_passes.add(player_id)
        player_ids = list(self.players)
        if len(player_ids) < 2 or not all(pid in self.phase_passes for pid in player_ids):
            return "passed"
        sequence = self.phase_sequence()
        next_index = self.phase_tracker["index"] + 1
        if next_index >= len(sequence):
            next_index = 0
            self.record_score_history(self.phase_tracker["turn"])
            self.phase_tracker["turn"] += 1
        self.phase_tracker["index"] = next_index
        self.phase_passes.clear()
        return "advanced"

    def reset_phase_tracker(self, return_stack_sources=True):
        preferences = {
            "enabled": bool(self.rules_engine.get("enabled")),
            "autoSkipPhases": bool(
                self.rules_engine.get("autoSkipPhases", True)
            ),
            "autoSkipOffPlayerIds": list(
                self.rules_engine.get("autoSkipOffPlayerIds") or []
            ),
            "passAllPlayerIds": list(
                self.rules_engine.get("passAllPlayerIds") or []
            ),
        }
        if return_stack_sources:
            for action in self.rules_engine.get("actionStack") or []:
                source = action.get("source") or {}
                if not action.get("sourceOnStack"):
                    continue
                if source.get("zone") == "battlefield" and action.get("sourceBattlefieldItem"):
                    self.battlefield.append(action["sourceBattlefieldItem"])
                    continue
                owner_id = source.get("ownerId")
                zone = source.get("zone")
                container_id = source.get("containerId") or owner_id
                if owner_id in self.players and container_id in self.players and zone in {"hand", "graveyard"} and source.get("cardId"):
                    self.put_zone_card(container_id, zone, source["cardId"], owner_id, "bottom")
        self.phase_tracker["index"] = 0
        self.phase_tracker["turn"] = 1
        self.score_history = []
        self.final_summary = None
        self.phase_passes.clear()
        self.rules_engine = make_rules_engine(preferences["enabled"])
        self.rules_engine.update(preferences)
        self.reset_rules_confrontation_turn()
        self.rules_engine["priorityPlayerId"] = next(iter(self.players), None)

    def serialize_phase_tracker(self):
        return {
            **self.phase_tracker,
            "passedPlayerIds": [pid for pid in self.players if pid in self.phase_passes],
        }
