"""Timing, legality of actions, auto-pass and declaring actions."""

import time

from .common import (
    ADVANCED_PHASES, NUM_SEATS, RULES_ACTION_KINDS, RULES_WILL_TYPES,
    RULES_SUPPORT_ENTRY_RESULTS, new_id
)


class PriorityMixin:
    def rules_action_timing_error(self, kind, source, as_support=False, player_id=None):
        """Reject voluntary card actions outside the rulebook response windows.

        Older saved games and focused engine tests can lack the pre-game ready
        markers.  Once a real assisted match has started, however, the server
        must not trust the client-side playable aura as its only guard.
        """
        started = bool(
            self.phase_tracker["turn"] > 1
            or len(self.rules_engine.get("readyPlayerIds") or []) >= NUM_SEATS
            or self.rules_engine.get("firstManifestationComplete")
            or self.rules_engine.get("firstManifestationItemIds")
        )
        if as_support:
            if self.rules_support_from_hand_available_anytime((source or {}).get("cardId")):
                return None
            return None if self.current_phase_id() == "confrontation_reaction" else "A Support Manifestation can only be played during Reaction."
        if not started or kind not in {"play_card", "activated_effect"}:
            return None
        phase_id = self.current_phase_id()
        response_phases = {"confrontation_reaction", "resolution_effects", "end_actions"}
        if kind == "activated_effect":
            abilities = self.card_rules.get((source or {}).get("cardId"), {}).get(
                "activatedAbilities"
            ) or []
            has_phase_ability = any(
                phase_id in (ability.get("phaseIds") or [])
                for ability in abilities
            )
            return (
                None
                if phase_id in response_phases or has_phase_ability
                else "This effect cannot be activated during the current step."
            )
        card_type = (source or {}).get("cardType")
        if card_type == "manifestation" and (source or {}).get("zone") == "battlefield":
            played_item = self.find_battlefield_item((source or {}).get("itemId"))
            if played_item and played_item.get("tebebeConcealed"):
                # played "as if it were in your hand": the Manifestation windows
                if phase_id in {"confrontation_reaction", "end_actions"}:
                    return None
                return "This Manifestation can only be played during Reaction or End actions."
        if (card_type == "ephemeral_will" and self.card_rules.get((source or {}).get("cardId"), {}).get("reactionEmptyStackOnly")):
            if phase_id != "confrontation_reaction" or self.rules_engine["actionStack"]:
                return "This card can only be played during Reaction while the Stack is empty."
            return None
        play_phases = self.card_rules.get((source or {}).get("cardId"), {}).get("playPhases")
        if card_type == "ephemeral_will" and play_phases:
            return None if phase_id in play_phases else "This Will cannot be played during the current step."
        if card_type == "ephemeral_will":
            return None if phase_id in response_phases else "An Ephemeral Will cannot be played during the current step."
        if card_type == "persistent_will":
            if phase_id == "end_actions":
                return None
            if (
                phase_id in response_phases and player_id
                and self.rules_persistent_wills_as_ephemeral(player_id)
            ):
                return None
            if (
                phase_id == "confrontation_before_revelation"
                and self.card_rules.get((source or {}).get("cardId"), {}).get(
                    "playBeforeRevelation"
                )
            ):
                return None
            return "A Persistent Will can only be played during End actions."
        return "This card cannot be played as a Stack action during the current step."

    def rules_match_started(self):
        return bool(
            self.phase_tracker["turn"] > 1
            or len(self.rules_engine.get("readyPlayerIds") or []) >= NUM_SEATS
            or self.rules_engine.get("firstManifestationComplete")
            or self.rules_engine.get("firstManifestationItemIds")
        )

    def rules_field_ability_usable(self, item, ability, zone, phase_id):
        """Cheap check that an activated ability of a field card could be used right now."""
        source_zones = ability.get("sourceZones")
        if source_zones and "battlefield" not in source_zones:
            return False
        required_zone = ability.get("sourceFieldZone")
        if required_zone and required_zone != zone:
            return False
        phase_ids = ability.get("phaseIds")
        if phase_ids and phase_id not in phase_ids:
            return False
        if ability.get("exhaustSource") and int(round(float(item.get("rotation") or 0))) % 180:
            return False  # already exhausted
        if self.rules_ability_clearly_unusable(
            self.rules_item_controller_id(item), ability, phase_id, item.get("cardId"),
        ):
            return False
        turn = self.phase_tracker["turn"]
        if ability.get("oncePerTurnSupport") and turn in (item.get("supportUsedTurn"), item.get("supportUntilTurn")):
            return False
        removal = ability.get("removeCountersFromSource")
        if isinstance(removal, dict):
            counters = item.get("counters") or {}
            have = sum(
                int(value or 0) for key, value in counters.items()
                if str(key).casefold() == str(removal.get("name") or "").casefold()
            )
            if have < int(removal.get("amount") or 0):
                return False
        return True

    def rules_will_affordable(self, player_id, card_id):
        """Whether the Tribute of a Will can be paid with what the player has.

        Generous whenever an unusual payment source exists, so a phase is never
        skipped by mistake.
        """
        metadata = self.card_rules.get(card_id, {})
        if metadata.get("playAsPersistentWill"):
            return True
        if self.rules_exotic_tribute_available(player_id) or any(
            entry.get("playerId") == player_id and (entry.get("noTribute") or entry.get("anyWill"))
            for entry in self.rules_engine.get("playPermissions") or []
        ):
            return True
        try:
            requirements, _enforced = self.rules_tribute_requirements(
                "play_card", {"cardId": card_id, "cardType": metadata.get("type")}, None, player_id,
            )
        except Exception:  # never skip a phase because of a computation problem
            return True
        return self.rules_requirements_affordable(player_id, requirements, card_id)

    def rules_exotic_tribute_available(self, player_id):
        """An unusual Tribute source (Limbo, Vessel, field): affordability is not computed."""
        player = self.players[player_id]
        if self.rules_counter_essence_sources(player_id):
            return True
        if any(
            self.rules_active_passive_sources(kind)
            for kind in (
                "allow_limbo_tribute_with_counter", "vessel_manifestations_as_tribute",
                "field_manifestations_as_tribute",
            )
        ):
            return True
        return any(
            self.card_rules.get(other, {}).get("canPayTributeFromLimbo")
            for other in player["zones"]["graveyard"]
        ) or any(
            self.rules_item_controller_id(item) == player_id
            and self.card_rules.get(item.get("cardId"), {}).get("canPayTributeFromInterzone")
            for item in self.battlefield
        )

    def rules_requirements_affordable(self, player_id, requirements, exclude_card_id=None):
        """Whether Essences plus hand Manifestations can pay these Tribute requirements."""
        player = self.players[player_id]
        try:
            candidates = [
                other for other in player["zones"]["hand"]
                if other != exclude_card_id and self.card_rules.get(other, {}).get("type") == "manifestation"
                and self.card_rules.get(other, {}).get("canPayTribute", True)
            ][:12]
            for allocation in self.rules_transcendent_payment_options(player_id, requirements):
                remaining, _spent = self.rules_essence_payment_plan(
                    player_id, requirements, transcendent_payment=allocation,
                )
                if all(amount <= 0 for amount in remaining.values()):
                    return True
                for mask in range(1, 1 << len(candidates)):
                    selected = [card for index, card in enumerate(candidates) if mask & (1 << index)]
                    if self.rules_manifestations_cover(selected, remaining, player_id=player_id)[0]:
                        return True
            return False
        except Exception:  # never skip a phase because of a computation problem
            return True

    def rules_hand_additional_cost_available(self, player_id, source_card_id, ability):
        """Whether the hand holds the card an additional cost needs (Censor:
        a Manifestation to reveal and exile; Timid Brain: a Will to discard).
        The source card itself never pays its own additional cost."""
        additional_cost = (ability or {}).get("additionalCost")
        if additional_cost not in {"exile_hand_manifestation", "discard_hand_will"}:
            return True
        hand_cards = list(self.players[player_id]["zones"]["hand"])
        if source_card_id in hand_cards:
            hand_cards.remove(source_card_id)
        cost_types = (
            RULES_WILL_TYPES if additional_cost == "discard_hand_will"
            else {"manifestation"}
        )
        return any(
            self.card_rules.get(card_id, {}).get("type") in cost_types
            for card_id in hand_cards
        )

    def rules_played_ability_has_field_target(self, player_id, card_id):
        """False only when the played ability needs a card on the field and none is legal."""
        ability = next(iter(self.card_rules.get(card_id, {}).get("playedAbilities") or []), None)
        target_rules = (ability or {}).get("targets") or {}
        if int(target_rules.get("min") or 0) < 1 or target_rules.get("groups"):
            return True
        if target_rules.get("kind") == "zone_card" and set(target_rules.get("zones") or []) <= {"graveyard", "receptacle"}:
            # Revive, Claim the Forsaken: a card must wait in a Limbo or a Vessel
            try:
                return any(
                    self.rules_ability_targets_error(
                        target_rules,
                        [{
                            "kind": "zone_card", "containerId": container_id, "zone": zone,
                            "cardId": card_id,
                            "ownerId": self.card_owner_in_zone(container_id, zone, card_id),
                        }],
                        player_id,
                    ) is None
                    for container_id, container in self.players.items()
                    for zone in target_rules.get("zones") or []
                    for card_id in dict.fromkeys(container["zones"].get(zone) or [])
                )
            except Exception:  # never skip a phase because of a computation problem
                return True
        if target_rules.get("kind") not in {None, "card"} or (target_rules.get("zones") or ["battlefield"]) != ["battlefield"]:
            return True
        return any(
            self.rules_ability_targets_error(
                target_rules,
                [{"kind": "card", "itemId": item.get("id"), "cardId": item.get("cardId")}],
                player_id,
            ) is None
            for item in self.battlefield
        )

    def rules_ability_clearly_unusable(self, player_id, ability, phase_id, source_card_id=None):
        """Cheap checks shared by auto-pass: condition, step, Essence cost and
        a required target on the field or the Stack. True only when the
        ability certainly cannot be used now."""
        ability = ability or {}
        condition = str(ability.get("condition") or "")
        if condition == "controller_lost_confrontation":
            if not self.rules_player_lost_confrontation_this_turn(player_id):
                return True
        if condition == "last_opponent_support_low_power" and self.rules_last_opponent_support(player_id, 2) is None:
            return True
        phase_ids = [str(entry) for entry in ability.get("phaseIds") or [] if str(entry) in ADVANCED_PHASES]
        if phase_ids and phase_id not in phase_ids:
            return True
        result_kind = (ability.get("result") or {}).get("kind")
        if result_kind in {"field_becomes_first_manifestation", "interzone_becomes_first_manifestation"} and self.rules_first_manifestation_slot_taken(player_id):
            return True
        if result_kind in {"grant_source_support_until_end_turn", "stalemate_target_grant_source_support"} and phase_id != "confrontation_reaction":
            # Support only matters while Supports can still be played
            return True
        if result_kind in RULES_SUPPORT_ENTRY_RESULTS and player_id in self.players and self.rules_support_entry_locked(player_id):
            # Pin Down: nothing can be put into the Confrontation Zone this turn
            return True
        if result_kind == "first_manifestation_trap" and phase_id != "confrontation_choose":
            return True
        if result_kind == "chain_from_zone" and (ability.get("result") or {}).get("zone") == "hand":
            hand = list(self.players[player_id]["zones"]["hand"])
            if source_card_id in hand:
                hand.remove(source_card_id)
            if not any(self.card_rules.get(card, {}).get("type") == "manifestation" for card in hand):
                return True
        tribute = str(ability.get("tribute") or "")
        if tribute and player_id in self.players and not self.rules_exotic_tribute_available(player_id):
            try:
                requirements = self.rules_requirements_from_symbols(tribute)
            except Exception:  # never skip a phase because of a computation problem
                requirements = None
            if requirements and not self.rules_requirements_affordable(
                player_id, requirements, source_card_id,
            ):
                return True
        essence_cost = str(ability.get("essenceCost") or "")
        if essence_cost:
            try:
                requirements = self.rules_requirements_from_symbols(essence_cost)
                remaining, _spent = self.rules_essence_payment_plan(player_id, requirements)
                if requirements and any(amount > 0 for amount in remaining.values()) and not self.rules_counter_essence_sources(player_id):
                    return True
            except Exception:  # never skip a phase because of a computation problem
                pass
        target_rules = ability.get("targets") or {}
        if int(target_rules.get("min") or 0) >= 1 and not target_rules.get("groups"):
            kind = target_rules.get("kind")
            if kind in {"stack_action", "stack_effect"}:
                stack = self.rules_engine.get("actionStack") or []
                if kind == "stack_effect":
                    stack = [entry for entry in stack if entry.get("kind") != "play_card"]
                if target_rules.get("controller") == "self":
                    stack = [entry for entry in stack if entry.get("controllerId") == player_id]
                card_types = target_rules.get("cardTypes")
                if card_types:
                    stack = [
                        entry for entry in stack
                        if self.card_rules.get((entry.get("source") or {}).get("cardId"), {}).get("type") in card_types
                    ]
                if not stack:
                    return True
            elif kind in {None, "card"} and (target_rules.get("zones") or ["battlefield"]) == ["battlefield"]:
                if not any(
                    self.rules_ability_targets_error(
                        target_rules,
                        [{"kind": "card", "itemId": item.get("id"), "cardId": item.get("cardId")}],
                        player_id,
                    ) is None
                    for item in self.battlefield
                ):
                    return True
        return False

    def rules_usable_hand_ability_card_ids(self, player_id):
        if not self.rules_engine.get("enabled") or player_id not in self.players:
            return []
        phase_id = self.current_phase_id()
        usable = []
        for card_id in dict.fromkeys(self.players[player_id]["zones"]["hand"]):
            if any(
                "hand" in (ability.get("sourceZones") or [])
                and self.rules_hand_additional_cost_available(player_id, card_id, ability)
                and not self.rules_ability_clearly_unusable(player_id, ability, phase_id, card_id)
                for ability in self.card_rules.get(card_id, {}).get("activatedAbilities") or []
            ):
                usable.append(card_id)
        return usable

    def rules_player_can_act(self, player_id):
        """True when the player has any voluntary action available in the current step.

        Deliberately generous: timing and zones are checked, and Will Tributes only
        when the player clearly cannot pay them, so a phase is never skipped by mistake.
        """
        player = self.players[player_id]
        phase_id = self.current_phase_id()
        response = phase_id in {"confrontation_reaction", "resolution_effects", "end_actions"}
        support_locked = self.rules_support_entry_locked(player_id)

        def can_play(card_id, card_type):
            return self.rules_action_timing_error(
                "play_card", {"cardId": card_id, "cardType": card_type},
                player_id=player_id,
            ) is None

        def can_support(card_id):
            return not support_locked and self.rules_action_timing_error(
                "play_card", {"cardId": card_id, "cardType": "manifestation"},
                as_support=True, player_id=player_id,
            ) is None

        for card_id in set(player["zones"]["hand"]):
            metadata = self.card_rules.get(card_id, {})
            card_type = "persistent_will" if metadata.get("playAsPersistentWill") else metadata.get("type")
            # Reaction is the last chance to change the Confrontation. A Will in
            # hand keeps the decision with its player, even if the cheap payment
            # or target preview cannot prove it playable yet.
            if phase_id == "confrontation_reaction" and card_type == "ephemeral_will" and can_play(card_id, card_type):
                return True
            if (
                card_type in RULES_WILL_TYPES and can_play(card_id, card_type)
                and self.rules_will_affordable(player_id, card_id)
                and all(
                    self.rules_hand_additional_cost_available(player_id, card_id, ability)
                    for ability in (metadata.get("playedAbilities") or [])[:1]
                )
                and self.rules_played_ability_has_field_target(player_id, card_id)
                and not any(
                    self.rules_ability_clearly_unusable(player_id, ability, phase_id, card_id)
                    for ability in (metadata.get("playedAbilities") or [])[:1]
                )
            ):
                return True
            if (
                card_type == "manifestation" and can_support(card_id)
                and self.rules_support_from_hand_available(player_id, card_id)
            ):
                return True
            if response and any(
                "hand" in (ability.get("sourceZones") or [])
                and self.rules_hand_additional_cost_available(player_id, card_id, ability)
                and not self.rules_ability_clearly_unusable(player_id, ability, phase_id, card_id)
                for ability in metadata.get("activatedAbilities") or []
            ):
                return True
        if response:
            for card_id in set(player["zones"]["receptacle"]):
                if any(
                    "receptacle" in (ability.get("sourceZones") or [])
                    and not self.rules_ability_clearly_unusable(player_id, ability, phase_id, card_id)
                    for ability in self.card_rules.get(card_id, {}).get("activatedAbilities") or []
                ):
                    return True
            if any(
                self.rules_play_permission_usable(player_id, entry, phase_id)
                for entry in self.rules_engine.get("playPermissions") or []
            ):
                return True
        for item in self.battlefield:
            if self.rules_item_controller_id(item) != player_id:
                continue
            metadata = self.rules_item_card_rules(item)
            card_type = metadata.get("type")
            zone = self.rules_field_zone(item)
            if (
                card_type in RULES_WILL_TYPES
                and (
                    item.get("concealedWill") or item.get("persuaded")
                    or item.get("playableFree") == self.phase_tracker["turn"]
                )
                and can_play(item.get("cardId"), card_type)
            ):
                return True
            # Grimoire: the Wills placed on it are played as if they were in the hand
            if item.get("attachedCards") and self.rules_item_effects_active(item) and any(
                passive.get("kind") == "play_attached_wills"
                for passive in metadata.get("passiveEffects") or []
            ) and any(
                entry.get("ownerId") == player_id
                and self.card_rules.get(entry.get("cardId"), {}).get("type") in RULES_WILL_TYPES
                and can_play(entry.get("cardId"), self.card_rules[entry["cardId"]]["type"])
                and self.rules_will_affordable(player_id, entry.get("cardId"))
                for entry in item["attachedCards"]
            ):
                return True
            if (
                card_type == "manifestation" and item.get("tebebeConcealed")
                and self.rules_action_timing_error(
                    "play_card",
                    {"cardId": item.get("cardId"), "cardType": card_type, "zone": "battlefield", "itemId": item.get("id")},
                    player_id=player_id,
                ) is None
            ):
                return True
            if (
                card_type == "manifestation" and zone in {"interzone", "stalemate"}
                and can_support(item.get("cardId"))
                and self.rules_card_can_enter_support(item, from_zone=zone)
                and not self.rules_item_zone_locked(item)
            ):
                return True
            if (
                response and item.get("faceUp")
                and self.rules_item_effects_active(item)
                and any(
                    self.rules_field_ability_usable(item, ability, zone, phase_id)
                    for ability in metadata.get("activatedAbilities") or []
                )
            ):
                return True
        return False

    def rules_play_permission_usable(self, player_id, entry, phase_id):
        """A play permission counts as an action only while its card can be played now
        (Wandering Veteran's Support from the Limbo is no action in End actions)."""
        if entry.get("playerId") != player_id:
            return False
        if int(entry.get("turn") or self.phase_tracker["turn"]) != self.phase_tracker["turn"]:
            return False
        if entry.get("phaseIds") and phase_id not in entry["phaseIds"]:
            return False
        zone_cards = self.players[player_id]["zones"].get(entry.get("fromZone") or "hand") or []
        if entry.get("cardId"):
            card_ids = [entry["cardId"]] if entry["cardId"] in zone_cards else []
        elif entry.get("anyWill"):
            card_ids = [
                card_id for card_id in zone_cards
                if self.card_rules.get(card_id, {}).get("type") in (
                    {"ephemeral_will"} if entry.get("ephemeralOnly") else RULES_WILL_TYPES
                )
                and (
                    entry.get("maxCost") is None
                    or int(self.card_rules.get(card_id, {}).get("cost") or 0) <= int(entry["maxCost"])
                )
            ]
        else:
            return True  # unknown shape: stay generous
        for card_id in dict.fromkeys(card_ids):
            card_type = self.card_rules.get(card_id, {}).get("type")
            if entry.get("asSupport"):
                if (
                    not self.rules_support_entry_locked(player_id)
                    and not self.rules_confrontation_entry_blocked(player_id, self.card_rules.get(card_id, {}))
                    and self.rules_action_timing_error(
                        "play_card", {"cardId": card_id, "cardType": "manifestation"},
                        as_support=True, player_id=player_id,
                    ) is None
                ):
                    return True
                continue
            if self.rules_action_timing_error(
                "play_card", {"cardId": card_id, "cardType": card_type}, player_id=player_id,
            ) is None:
                return True
        return False

    def rules_confrontation_resolve_prompt(self):
        """True when the Reaction step is open, the Stack is empty and nobody can
        play a card or an effect: the engine asks before resolving the Confrontation."""
        engine = self.rules_engine
        if (
            not engine.get("enabled")
            or not self.rules_auto_skip_enabled(engine.get("priorityPlayerId"))
            or self.ended or len(self.players) < NUM_SEATS
            or not self.phase_tracker.get("enabled")
            or self.current_phase_id() != "confrontation_reaction"
            or engine.get("actionStack") or engine.get("priorityPasses")
            or engine.get("pendingChoice")
            or not self.rules_match_started()
            or self.rules_first_manifestation_active()
            or self.rules_recovery_mulligan_active()
            or engine.get("priorityPlayerId") not in self.players
        ):
            return False
        return not any(self.rules_player_can_act(pid) for pid in self.players)

    def rules_auto_skip_enabled(self, player_id):
        """Whether the engine may skip phases for this player (each player's own option)."""
        engine = self.rules_engine
        return bool(engine.get("autoSkipPhases", True)) and player_id not in (
            engine.get("autoSkipOffPlayerIds") or []
        )

    def set_rules_auto_skip(self, player_id, enabled):
        if player_id not in self.players:
            return "Unable to change this option.", None
        off = [
            pid for pid in self.rules_engine.get("autoSkipOffPlayerIds") or []
            if pid != player_id and pid in self.players
        ]
        if not enabled:
            off.append(player_id)
        self.rules_engine["autoSkipOffPlayerIds"] = off
        return None, {"playerId": player_id, "enabled": bool(enabled)}

    def set_rules_pass_all(self, player_id, enabled):
        if not self.rules_engine.get("enabled") or player_id not in self.players:
            return "Assisted rules are not active.", None
        locked = [
            pid for pid in self.rules_engine.get("passAllPlayerIds") or []
            if pid != player_id and pid in self.players
        ]
        if enabled:
            locked.append(player_id)
        self.rules_engine["passAllPlayerIds"] = locked
        return None, {"playerId": player_id, "enabled": bool(enabled)}

    def rules_auto_pass_player(self):
        """The priority holder when no legal response or auto-skippable action exists."""
        engine = self.rules_engine
        pass_all = engine.get("priorityPlayerId") in (engine.get("passAllPlayerIds") or [])
        stack_waiting = bool(engine.get("actionStack"))
        if (
            not engine.get("enabled")
            or not (stack_waiting or self.rules_auto_skip_enabled(engine.get("priorityPlayerId")) or pass_all)
            or not self.phase_tracker.get("enabled") or self.ended
            or len(self.players) < NUM_SEATS or engine.get("pendingChoice")
            or not self.rules_match_started()
            or self.rules_first_manifestation_active()
            or self.rules_recovery_mulligan_active()
        ):
            return None
        player_id = engine.get("priorityPlayerId")
        if player_id not in self.players:
            return None
        if pass_all:
            return player_id
        if self.rules_player_can_act(player_id):
            return None
        if self.rules_confrontation_resolve_prompt():
            return None  # ask before resolving the Confrontation
        return player_id

    def declare_rules_action(self, player_id, label, kind="manual", source=None, target=None,
                             targets=None, cost_note=None, payment_card_ids=None, ability_id=None,
                             placement=None, as_support=False,
                             extra_essence_count=0, cost_card_id=None, internal=False,
                             extra_payment_card_ids=None, transcendent_payment=None):
        if not self.rules_engine["enabled"]:
            return "Assisted rules are not active.", None
        if self.ended or player_id not in self.players:
            return "Unable to declare an action.", None
        if len(self.players) < 2:
            return "Both players must join before using priority.", None
        if self.rules_engine.get("pendingChoice"):
            return "A required card choice must be completed first.", None
        if self.rules_engine["priorityPlayerId"] != player_id and not internal:
            return "You do not have priority.", None
        kind = str(kind or "manual")
        if kind not in RULES_ACTION_KINDS:
            return "Unknown action type.", None
        if as_support and self.rules_support_entry_locked(player_id):
            return "Manifestations cannot be put in Support until the end of the turn.", None
        clean_label = " ".join(str(label or "").split())[:160]
        if not clean_label:
            return "Describe the action before adding it to the Stack.", None
        clean_target = " ".join(str(target or "").split())[:240]
        clean_cost_note = " ".join(str(cost_note or "").split())[:240]
        as_support = bool(as_support)
        if as_support and kind != "play_card":
            return "Support must be declared as a played card.", None
        source_error, clean_source = self.rules_action_source(
            player_id, kind, source, as_support=as_support,
            ability_id=str(ability_id or ""),
        )
        if source_error:
            return source_error, None
        timing_error = None if internal else self.rules_action_timing_error(
            kind, clean_source, as_support=as_support, player_id=player_id,
        )
        if timing_error:
            return timing_error, None
        target_error, clean_targets = self.rules_action_targets(targets, player_id)
        if target_error:
            return target_error, None
        ingredients = (
            {clean_source.get("cardId")}
            if (clean_source or {}).get("zone") == "hand" else set()
        )
        for refs in (payment_card_ids, extra_payment_card_ids):
            if isinstance(refs, list):
                ingredients.update(
                    card_id for zone, _sep, card_id in (
                        str(ref or "").rpartition("|") for ref in refs
                    )
                    if zone in {"", "hand"}
                )
        if any(
            entry.get("kind") == "zone_card" and entry.get("zone") == "hand"
            and entry.get("cardId") in ingredients
            for entry in clean_targets
        ):
            return "The played card and its tribute cannot be chosen as its target.", None
        if as_support:
            for event in (
                "enters_field", "enters_support", "enters_field_zone",
            ):
                if event == "enters_field" and clean_source.get("zone") == "battlefield":
                    continue
                trigger_error = self.rules_trigger_target_error(
                    clean_source["cardId"], event, face_up=True,
                    trigger_targets=clean_targets, controller_id=player_id,
                    event_item_id=clean_source.get("itemId"),
                    event_zone=(
                        "confrontation"
                        if event == "enters_field_zone" else None
                    ),
                )
                if trigger_error:
                    return trigger_error, None
        ability_error, clean_ability = self.rules_action_ability(
            player_id, kind, clean_source, str(ability_id or ""), clean_targets
        )
        if ability_error:
            return ability_error, None
        if (
            kind == "activated_effect" and clean_ability
            and (clean_ability.get("result") or {}).get("kind") == "create_essence"
            and (clean_ability.get("result") or {}).get("temperament") == "source_chosen"
            and clean_ability.get("removeCountersFromSource")
        ):
            return "Use this card's Essence counters directly, without the Stack.", None
        payment_error, clean_payment = self.rules_action_payment(
            player_id,
            kind,
            clean_source,
            payment_card_ids,
            clean_ability,
            clean_targets,
            extra_essence_count,
            extra_payment_card_ids,
            transcendent_payment=transcendent_payment,
        )
        if payment_error:
            return payment_error, None
        cost_card_id = str(cost_card_id) if cost_card_id else None
        if clean_ability and clean_ability.get("sourceCost") and not (
            clean_source.get("zone") == "hand"
            and clean_source.get("cardId") in self.players[player_id]["zones"]["hand"]
        ):
            return "This effect's cost needs its source card in your Hand.", None
        additional_cost = (clean_ability or {}).get("additionalCost")
        if additional_cost in {"exile_hand_manifestation", "discard_hand_will"}:
            hand_cards = list(self.players[player_id]["zones"]["hand"])
            if clean_source.get("zone") == "hand" and clean_source.get("cardId") in hand_cards:
                hand_cards.remove(clean_source["cardId"])
            cost_types = (
                RULES_WILL_TYPES if additional_cost == "discard_hand_will"
                else {"manifestation"}
            )
            if not any(
                self.card_rules.get(card_id, {}).get("type") in cost_types
                for card_id in hand_cards
            ):
                return (
                    "You need a Will in hand to discard as an additional cost."
                    if additional_cost == "discard_hand_will"
                    else "You need a Manifestation in hand to reveal and exile as an additional cost."
                ), None
            if (
                cost_card_id not in hand_cards
                or self.card_rules.get(cost_card_id, {}).get("type") not in cost_types
            ):
                return (
                    "Choose the Will from your hand to discard."
                    if additional_cost == "discard_hand_will"
                    else "Choose the Manifestation from your hand to reveal and exile."
                ), None
        else:
            cost_card_id = None
        clean_targets = self.rules_redirect_targets(player_id, clean_targets)
        action = {
            "id": new_id(),
            "controllerId": player_id,
            "label": clean_label,
            "kind": kind,
            "source": clean_source,
            "target": clean_target or None,
            "targets": clean_targets,
            "ability": clean_ability,
            "cost": {
                "note": clean_cost_note or None,
                "tributeCardIds": clean_payment["cardIds"],
                "tributeRequirements": clean_payment["requirements"],
                "essenceSpent": clean_payment["essenceSpent"],
                "excessEssence": clean_payment["excessEssence"],
                "tributeValidated": clean_payment["validated"],
                "tributePaid": bool(clean_payment["requirements"]),
                "sourceExhausted": bool(clean_ability and clean_ability.get("exhaustSource")),
                "sourceSacrificed": bool(clean_ability and clean_ability.get("sacrificeSource")),
                "sacrificedCards": [],
                "removedCounters": [],
                "optionalExtraEssenceSpent": clean_payment[
                    "optionalExtraEssenceSpent"
                ],
            },
            "phaseId": self.current_phase_id(),
            "turn": self.phase_tracker["turn"],
            "createdAt": time.time(),
        }
        if as_support:
            action["asSupport"] = True
        if clean_ability and clean_ability.get("immediate"):
            action["immediate"] = True
        clean_placement = self.clean_rules_action_placement(
            kind, clean_source, placement, as_support=as_support
        )
        if clean_placement is not None:
            action["placement"] = clean_placement
        if kind == "play_card" and clean_source.get("zone") in {"hand", "graveyard", "suspended", "deck"}:
            container_id = clean_source.get("containerId") or player_id
            if clean_source.get("zone") == "suspended":
                suspended = next((
                    entry for entry in self.rules_engine.get("suspendedCards") or []
                    if entry.get("id") == clean_source.get("suspensionId")
                ), None)
                owner_id = suspended.get("ownerId") if suspended else None
                if suspended:
                    self.rules_engine["suspendedCards"].remove(suspended)
            else:
                owner_id = self.take_zone_card(
                    container_id, clean_source["zone"],
                    clean_source["cardId"]
                )
            if owner_id is None:
                return "The source card is no longer in its declared zone.", None
            action["sourceOnStack"] = True
            if clean_source.get("permissionId"):
                self.consume_rules_zone_play_permission(clean_source["permissionId"])
        elif clean_source and clean_source.get("zone") == "attached" and kind == "play_card":
            host = self.find_battlefield_item(clean_source.get("itemId"))
            entry = next((
                e for e in (host or {}).get("attachedCards") or []
                if e.get("cardId") == clean_source["cardId"]
            ), None)
            if entry is None:
                return "This Will is no longer placed on that card.", None
            host["attachedCards"].remove(entry)
            self.rules_sync_attached_counter(host)
            action["sourceOnStack"] = True
        elif clean_source and clean_source.get("zone") == "battlefield" and kind == "play_card":
            source_item = self.find_battlefield_item(clean_source.get("itemId"))
            if source_item is None:
                return "This Manifestation is no longer in your Interzone.", None
            action["sourceBattlefieldItem"] = {
                **source_item, "counters": dict(source_item.get("counters") or {})
            }
            if as_support:
                source_item["pendingSupportActionId"] = action["id"]
                action["sourceRemainsOnField"] = True
                action["sourceOnStack"] = False
            else:
                self.battlefield.remove(source_item)
                for other in self.battlefield:
                    if other.get("stackedOn") == source_item.get("id"):
                        other["stackedOn"] = None
                action["sourceOnStack"] = True
        tribute_result = self.pay_rules_tribute(player_id, clean_payment)
        action["cost"]["tributeMovements"] = tribute_result["movements"]
        action["cost"]["createdEssence"] = tribute_result["createdEssence"]
        activation_payment = self.pay_rules_activation_cost(clean_source, clean_ability)
        action["cost"]["sacrificedCards"] = activation_payment["sacrificedCards"]
        action["cost"]["removedCounters"] = activation_payment["removedCounters"]
        action["cost"]["reducedSourcePower"] = activation_payment[
            "reducedSourcePower"
        ]
        if cost_card_id and additional_cost == "discard_hand_will":
            cost_owner = self.card_owner_in_zone(player_id, "hand", cost_card_id) or player_id
            cost_error, _owner, _replacement = self.move_zone_card_by_effect(
                player_id, "hand", cost_owner, "graveyard", cost_card_id, "top"
            )
            if not cost_error:
                action["cost"]["discardedCard"] = {
                    "cardId": cost_card_id, "ownerId": cost_owner,
                }
        elif cost_card_id:
            cost_owner = self.card_owner_in_zone(player_id, "hand", cost_card_id) or player_id
            cost_error, _owner, _replacement = self.move_zone_card_by_effect(
                player_id, "hand", cost_owner, "exile", cost_card_id, "top"
            )
            if not cost_error:
                action["cost"]["revealedCard"] = {
                    "cardId": cost_card_id, "ownerId": cost_owner,
                    "power": int(self.card_rules.get(cost_card_id, {}).get("power") or 0),
                }
        source_cost = (clean_ability or {}).get("sourceCost")
        if source_cost == "discard_source":
            source_owner = self.card_owner_in_zone(
                player_id, "hand", clean_source["cardId"]
            ) or player_id
            source_error, _owner, _replacement = self.move_zone_card_by_effect(
                player_id, "hand", source_owner, "graveyard",
                clean_source["cardId"], "top",
            )
            if not source_error:
                action["cost"]["discardedSource"] = {
                    "cardId": clean_source["cardId"], "ownerId": source_owner,
                }
        elif source_cost == "stalemate_source":
            source_owner = self.take_zone_card(
                player_id, "hand", clean_source["cardId"]
            )
            if source_owner is not None:
                seat = self.players[player_id].get("seat")
                stalemate_item = {
                    "id": new_id(), "ownerId": source_owner,
                    "controllerId": player_id, "cardId": clean_source["cardId"],
                    "x": 650.0, "y": 800.0 if seat != 1 else 525.0,
                    "faceUp": True, "rotation": 0.0, "counters": {},
                    "rarity": self.players[source_owner].get(
                        "cardRarities", {}
                    ).get(clean_source["cardId"]),
                    "stackedOn": None, "fieldZone": "stalemate",
                }
                self.battlefield.append(stalemate_item)
                action["cost"]["stalematedSource"] = {
                    "cardId": clean_source["cardId"], "ownerId": source_owner,
                    "itemId": stalemate_item["id"],
                }
        if kind == "activated_effect":
            self.apply_rules_drill_drain(clean_source.get("itemId"))
        self.rules_engine["actionStack"].append(action)
        self.rules_engine["priorityPasses"] = []
        self.rules_engine["priorityPlayerId"] = self.other_rules_player_id(player_id)
        if (
            kind == "play_card"
            and self.card_rules.get(clean_source.get("cardId"), {}).get("type") in RULES_WILL_TYPES
        ):
            self.queue_rules_will_target_watchers(action)
        return None, action
