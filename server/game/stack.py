"""Resolving, countering and cleaning up Stack actions; ongoing effects."""

import math
from copy import deepcopy

from .common import RULES_COPIED_EFFECT_KEYS, RULES_EFFECT_DURATIONS, RULES_TEMPERAMENTS, new_id


class StackMixin:
    def resolve_rules_action_source(self, action):
        source = action.get("source") or {}
        if action.get("isStackCopy"):
            if source.get("cardType") == "persistent_will":
                item = self.create_rules_token_copy(source.get("cardId"), action.get("controllerId"))
                self.transfer_rules_stack_protection(action, item)
                return {
                    "status": "moved", "destination": "battlefield", "itemId": item["id"],
                    "cardId": item["cardId"], "ownerId": item["ownerId"],
                    "x": item["x"], "y": item["y"],
                }
            return {
                "status": "copy_resolved", "destination": "stack",
                "cardId": source.get("cardId"),
            }
        if action.get("kind") != "play_card":
            return None
        controller_id = action.get("controllerId")
        card_id = source.get("cardId")
        player = self.players.get(controller_id)
        source_on_stack = bool(action.get("sourceOnStack"))
        if action.get("asSupport"):
            owner_id = source.get("ownerId")
            on_field = bool(action.get("sourceRemainsOnField"))
            existing = self.find_battlefield_item(source.get("itemId")) if on_field else None
            if player is None or (not source_on_stack and not existing) or owner_id not in self.players:
                return {"status": "source_missing", "destination": "battlefield", "asSupport": True}
            placement = action.get("placement") or {}
            stored_item = action.get("sourceBattlefieldItem")
            from_zone = (
                stored_item.get("fieldZone")
                if isinstance(stored_item, dict)
                else None
            ) or source.get("zone")
            item = existing if existing is not None else dict(stored_item) if isinstance(stored_item, dict) else {
                "id": new_id(), "ownerId": owner_id, "controllerId": controller_id,
                "cardId": card_id, "faceUp": True, "rotation": 0.0, "counters": {},
                "rarity": (self.players.get(owner_id) or {}).get("cardRarities", {}).get(card_id),
                "stackedOn": None,
            }
            item.update({
                "x": float(placement.get("x") or item.get("x") or 0),
                "y": float(placement.get("y") or item.get("y") or 0),
                "faceUp": True,
            })
            if ((action.get("ability") or {}).get("result") or {}).get("kind") == "change_source_control":
                chosen_controller = next((target.get("playerId") for target in action.get("targets") or []
                                          if target.get("kind") == "player"), None)
                if chosen_controller in self.players:
                    # "Put in Support under any player's control" applies as it
                    # enters, before entry triggers/watchers capture control.
                    item["controllerId"] = chosen_controller
            if source.get("temperamentOverride") in RULES_TEMPERAMENTS:
                item["temperamentOverride"] = source["temperamentOverride"]
            if source.get("winAsSupportDestination") == "exile":
                item["supportWinDestination"] = "exile"
            self.mark_rules_support_entry(item)
            item.pop("pendingSupportActionId", None)
            if item not in self.battlefield:
                self.battlefield.append(item)
            self.transfer_rules_stack_protection(action, item)
            return {
                "status": "moved", "destination": "battlefield", "itemId": item["id"],
                "cardId": card_id, "ownerId": owner_id, "x": item["x"], "y": item["y"],
                "asSupport": True, "fromZone": from_zone,
                "enteredBattlefield": source.get("zone") != "battlefield",
            }
        stored_item = action.get("sourceBattlefieldItem")
        if (
            source.get("zone") == "battlefield" and source.get("cardType") == "manifestation"
            and isinstance(stored_item, dict) and stored_item.get("tebebeConcealed")
        ):
            # Tebebe: a Manifestation played this way is put into the Interzone
            owner_id = source.get("ownerId")
            if player is None or not source_on_stack or owner_id not in self.players:
                return {"status": "source_missing", "destination": "battlefield"}
            seat = player.get("seat")
            item = {
                key: value for key, value in stored_item.items()
                if key not in {"concealedWill", "tebebeConcealed", "stackedOn", "stackOffsetX", "stackOffsetY"}
            }
            item.update({
                "controllerId": controller_id, "faceUp": True, "rotation": 0.0,
                "counters": dict(stored_item.get("counters") or {}),
                "x": 740.0, "y": 800.0 if seat != 1 else 525.0, "stackedOn": None,
            })
            if self.rules_interzone_slot_count(controller_id) >= self.rules_interzone_capacity(controller_id):
                anchor = self.rules_interzone_share_anchor(controller_id, item)
                if not anchor:
                    self.put_zone_card(owner_id, "graveyard", card_id, owner_id, "top")
                    return {"status": "interzone_full", "destination": "graveyard", "ownerId": owner_id}
                item.update({"stackedOn": anchor, "stackOffsetX": 18.0, "stackOffsetY": 18.0})
            item["fieldZone"] = "interzone"
            self.battlefield.append(item)
            self.mark_rules_interzone_entry(item)
            self.transfer_rules_stack_protection(action, item)
            return {
                "status": "moved", "destination": "battlefield", "itemId": item["id"],
                "cardId": card_id, "ownerId": owner_id, "x": item["x"], "y": item["y"],
                "fieldZone": "interzone", "fromZone": "field",
            }
        if source.get("zone") not in {"hand", "suspended", "graveyard", "battlefield", "attached", "deck"}:
            return None
        if player is None or (not source_on_stack and card_id not in player["zones"]["hand"]):
            destination = "battlefield" if source.get("cardType") == "persistent_will" else "graveyard"
            return {"status": "source_missing", "destination": destination}
        if source.get("cardType") == "persistent_will":
            owner_id = source.get("ownerId") if source_on_stack else self.take_zone_card(controller_id, "hand", card_id)
            if owner_id is None:
                return {"status": "source_missing", "destination": "battlefield"}
            placement = action.get("placement") or {}
            item = {
                "id": new_id(), "ownerId": owner_id,
                "controllerId": controller_id, "cardId": card_id,
                "x": float(placement.get("x") or 0), "y": float(placement.get("y") or 0),
                "faceUp": True, "rotation": 0.0, "counters": {},
                "fieldZone": "field",
                "rarity": (self.players.get(owner_id) or {}).get("cardRarities", {}).get(card_id),
                "stackedOn": None,
            }
            if source.get("exileOnLeave"):
                item["exileIfLeaves"] = True
            self.battlefield.append(item)
            self.transfer_rules_stack_protection(action, item)
            return {
                "status": "moved", "destination": "battlefield", "itemId": item["id"],
                "cardId": card_id, "ownerId": owner_id, "x": item["x"], "y": item["y"],
            }
        if source.get("cardType") != "ephemeral_will":
            return {"status": "manual_placement", "destination": "battlefield"}
        owner_id = source.get("ownerId") if source_on_stack else self.card_owner_in_zone(controller_id, "hand", card_id)
        destination = (action.get("ability") or {}).get(
            "resolveSourceTo"
        ) or "graveyard"
        if source.get("exileOnLeave") and destination in {"graveyard", "hand", "deck"}:
            destination = "exile"
        if source_on_stack:
            if owner_id is None or not self.put_zone_card(owner_id, destination, card_id, owner_id, "top"):
                return {"status": "source_missing", "destination": destination}
        else:
            error, _ = self.move_zone_card(
                controller_id, "hand", owner_id, destination, card_id, "top"
            )
            if error:
                return {"status": "source_missing", "destination": destination}
        self.rules_engine["ongoingEffects"] = [
            effect for effect in self.rules_engine.get("ongoingEffects") or []
            if effect.get("target", {}).get("actionId") != action.get("id")
        ]
        return {"status": "moved", "destination": destination, "ownerId": owner_id}

    def transfer_rules_stack_protection(self, action, item):
        for effect in self.rules_engine.get("ongoingEffects") or []:
            if (
                effect.get("kind") == "protection"
                and effect.get("target", {}).get("actionId")
                == action.get("id")
            ):
                effect["target"] = {
                    "kind": "card",
                    "itemId": item.get("id"),
                    "cardId": item.get("cardId"),
                    "ownerId": item.get("ownerId"),
                }

    def neutralize_rules_action_source(self, action, destination="graveyard"):
        """Move a neutralized played card from the Stack to its owner's Limbo."""
        source = action.get("source") or {}
        if action.get("isStackCopy"):
            return None  # A token disappearing must never move its original card.
        if action.get("sourceRemainsOnField"):
            item = self.find_battlefield_item(source.get("itemId"))
            if item:
                item.pop("pendingSupportActionId", None)
            return None
        if action.get("kind") != "play_card" or not action.get("sourceOnStack"):
            return None
        owner_id = source.get("ownerId")
        card_id = source.get("cardId")
        if owner_id not in self.players or not card_id:
            return {"status": "source_missing", "destination": "graveyard"}
        if destination not in {"graveyard", "hand"}:
            destination = "graveyard"
        if source.get("exileOnLeave"):
            destination = "exile"
        if not self.put_zone_card(owner_id, destination, card_id, owner_id, "top"):
            return {"status": "source_missing", "destination": destination}
        return {
            "status": "moved", "destination": destination,
            "ownerId": owner_id, "cardId": card_id,
        }

    def counter_rules_stack_action(self, target_action, mode, destination="graveyard"):
        """Remove one validated Stack entry while preserving already-paid costs."""
        if target_action not in self.rules_engine.get("actionStack", []):
            return None
        if target_action.get("cannotBeNeutralized"):
            return {
                "status": "prevented", "mode": mode,
                "actionId": target_action.get("id"),
                "cardId": (target_action.get("source") or {}).get("cardId"),
            }
        self.rules_engine["actionStack"].remove(target_action)
        self.rules_engine["ongoingEffects"] = [
            effect for effect in self.rules_engine.get("ongoingEffects") or []
            if effect.get("target", {}).get("actionId")
            != target_action.get("id")
        ]
        source_resolution = (
            self.neutralize_rules_action_source(target_action, destination)
            if target_action.get("kind") == "play_card" else None
        )
        result = {
            "status": "neutralized" if mode == "neutralize" else "cancelled",
            "actionId": target_action.get("id"),
            "cardId": (target_action.get("source") or {}).get("cardId"),
            "controllerId": target_action.get("controllerId"),
            "targetKind": target_action.get("kind"),
        }
        if source_resolution:
            result["sourceResolution"] = source_resolution
        ability_result = (target_action.get("ability") or {}).get("result") or {}
        if ability_result.get("kind") == "resolve_effect_memory":
            for memory_id in ability_result.get("memoryIds") or []:
                if memory_id != ability_result.get("memoryId"):
                    self.remove_rules_effect_memory(memory_id)
            removed_memory = self.remove_rules_effect_memory(
                ability_result.get("memoryId")
            )
            if removed_memory:
                result["memoryId"] = removed_memory["id"]
        return result

    @staticmethod
    def clean_rules_board_position(placement, default_x=795.0, default_y=670.0):
        placement = placement if isinstance(placement, dict) else {}

        def coordinate(name, default, minimum, maximum):
            try:
                value = float(placement.get(name, default))
            except (TypeError, ValueError):
                value = default
            if not math.isfinite(value):
                value = default
            return max(minimum, min(value, maximum))

        return {
            "x": coordinate("x", default_x, -150.0, 1741.0),
            "y": coordinate("y", default_y, -210.0, 1549.0),
        }

    @classmethod
    def clean_rules_action_placement(cls, kind, source, placement, as_support=False):
        if kind != "play_card" or (
            not as_support and (source or {}).get("cardType") != "persistent_will"
        ):
            return None
        return cls.clean_rules_board_position(placement)

    def create_rules_ongoing_effects(self, action):
        ability = action.get("ability") or {}
        definitions = [
            definition for definition in ability.get("ongoingEffects") or []
            if isinstance(definition, dict)
        ]
        if definitions:
            created = []
            for index, definition in enumerate(definitions):
                nested = {
                    **action,
                    "ability": {
                        **ability,
                        "id": f'{ability.get("id")}:{index}',
                        "ongoingEffect": definition,
                        "ongoingEffects": [],
                    },
                }
                created.extend(self.create_rules_ongoing_effects(nested))
            return created
        definition = ability.get("ongoingEffect") or {}
        source = dict(action.get("source") or {})
        source_resolution = action.get("sourceResolution") or {}
        if source_resolution.get("status") == "moved" and source_resolution.get("destination") == "battlefield":
            source.update({
                "zone": "battlefield",
                "itemId": source_resolution.get("itemId"),
            })
        targets = action.get("targets") or []
        duration = definition.get("duration")
        if duration not in RULES_EFFECT_DURATIONS:
            return []
        source_on_field = self.find_battlefield_item(source.get("itemId")) if source.get("itemId") else None
        copying = definition.get("kind") in {"copy_power_temperament", "copy_power_effects"}
        if copying and source_on_field is None:
            return []
        if duration in {"while_source_and_target_on_field", "while_source_on_field"} and source_on_field is None:
            return []
        if definition.get("scope") == "all_manifestations_on_field":
            targets = [
                {"kind": "card", "itemId": item["id"], "cardId": item["cardId"], "ownerId": item["ownerId"]}
                for item in self.battlefield
                if item.get("faceUp") and self.rules_item_card_rules(item).get("type") == "manifestation"
                and self.rules_field_zone(item) != "stalemate"
                and not (
                    definition.get("excludeSource")
                    and item.get("id") == source.get("itemId")
                )
            ]
        elif definition.get("scope") == "all_manifestations_in_confrontation":
            targets = [
                {
                    "kind": "card", "itemId": item["id"],
                    "cardId": item["cardId"], "ownerId": item["ownerId"],
                }
                for item in self.rules_confrontation_items()
                if not (
                    definition.get("excludeSource")
                    and item.get("id") == source.get("itemId")
                )
            ]
        elif definition.get("scope") == "opponent_manifestations_in_confrontation":
            targets = [
                {
                    "kind": "card", "itemId": item["id"],
                    "cardId": item["cardId"], "ownerId": item["ownerId"],
                }
                for item in self.rules_confrontation_items()
                if self.rules_item_controller_id(item) != action.get("controllerId")
            ]
        elif definition.get("scope") == "source":
            targets = [{
                "kind": "card", "itemId": source_on_field["id"],
                "cardId": source_on_field["cardId"],
                "ownerId": source_on_field["ownerId"],
            }] if source_on_field is not None else []
        elif definition.get("scope") == "friendly_cards_on_field":
            targets = [
                {
                    "kind": "card", "itemId": item["id"],
                    "cardId": item["cardId"], "ownerId": item["ownerId"],
                }
                for item in self.battlefield
                if item.get("faceUp")
                and self.rules_field_zone(item) != "stalemate"
                and self.rules_item_controller_id(item) == action.get("controllerId")
            ]
        elif definition.get("scope") == "friendly_manifestations_in_confrontation":
            targets = [
                {
                    "kind": "card", "itemId": item["id"],
                    "cardId": item["cardId"], "ownerId": item["ownerId"],
                }
                for item in self.rules_confrontation_items(
                    action.get("controllerId")
                )
                if not (
                    definition.get("excludeSource")
                    and item.get("id") == source.get("itemId")
                )
            ]
        elif definition.get("scope") == "friendly_manifestations_in_interzone":
            targets = [
                {
                    "kind": "card", "itemId": item["id"],
                    "cardId": item["cardId"], "ownerId": item["ownerId"],
                }
                for item in self.rules_confrontation_items(
                    action.get("controllerId"), ("interzone",)
                )
            ]
        elif definition.get("scope") == "target_player_manifestations_in_interzone":
            target_player_id = next((
                target.get("playerId") for target in targets
                if target.get("kind") == "player"
            ), None)
            targets = [
                {
                    "kind": "card", "itemId": item["id"],
                    "cardId": item["cardId"], "ownerId": item["ownerId"],
                }
                for item in self.battlefield
                if target_player_id in self.players
                and self.rules_item_controller_id(item) == target_player_id
                and self.rules_field_zone(item) == "interzone"
                and self.rules_item_card_rules(item).get("type")
                == "manifestation"
            ]
        elif definition.get("scope") == "target_player":
            targets = [
                {"kind": "player", "playerId": target.get("playerId")}
                for target in targets
                if target.get("kind") == "player"
                and target.get("playerId") in self.players
            ]
        elif definition.get("scope") == "global":
            targets = [{"kind": "global"}]

        powers_before = self.rules_field_power_snapshot()
        # A source-bound ability can only maintain one modifier for that
        # ability. Re-resolving it replaces the previous modifier.
        if duration in {"while_source_and_target_on_field", "while_source_on_field"}:
            self.rules_engine["ongoingEffects"] = [
                effect for effect in self.rules_engine["ongoingEffects"]
                if not (
                    effect.get("source", {}).get("itemId") == source.get("itemId")
                    and effect.get("abilityId") == ability.get("id")
                )
            ]
        created = []
        for target in targets:
            target_kind = target.get("kind")
            target_present = (
                self.find_battlefield_item(target.get("itemId")) is not None
                if target_kind == "card"
                else any(
                    entry.get("id") == target.get("actionId")
                    for entry in self.rules_engine.get("actionStack") or []
                )
                if target_kind in {"stack_action", "stack_effect"}
                else True
                if target_kind == "global"
                else target.get("playerId") in self.players
                if target_kind == "player"
                else False
            )
            if not target_present:
                continue
            effect = {
                "id": new_id(),
                "actionId": action.get("id"),
                "abilityId": ability.get("id"),
                "controllerId": action.get("controllerId"),
                "source": dict(source),
                "target": dict(target),
                "kind": definition.get("kind"),
                "duration": duration,
                "startedTurn": self.phase_tracker["turn"],
            }
            if definition.get("temperament") in RULES_TEMPERAMENTS:
                effect["temperament"] = definition["temperament"]
            if "value" in definition:
                effect["value"] = definition["value"]
            elif isinstance(definition.get("valuePerRemovedCounter"), (int, float)):
                removed_total = sum(
                    int(entry.get("amount") or 0)
                    for entry in (action.get("cost") or {}).get("removedCounters") or []
                )
                effect["value"] = (
                    removed_total * definition["valuePerRemovedCounter"]
                )
            if definition.get("fromOpponents"):
                effect["fromOpponents"] = True
            if copying and target_kind == "card":
                copied_item = self.find_battlefield_item(target.get("itemId"))
                effect["snapshot"] = self.rules_manifestation_characteristics(copied_item)
                effect["snapshot"]["basePower"] = effect["snapshot"]["power"]
                if effect["kind"] == "copy_power_effects":
                    copied_rules = self.rules_item_card_rules(copied_item)
                    effect["copiedRules"] = deepcopy({
                        key: copied_rules[key] for key in RULES_COPIED_EFFECT_KEYS
                        if key in copied_rules
                    })
            if effect["kind"] == "power_set_maximum" and target_kind == "card":
                current = self.rules_manifestation_characteristics(self.find_battlefield_item(target.get("itemId")))["power"]
                effect["powerAdjustment"] = int(effect.get("value") or 0) - current
            if (
                effect["kind"] == "power_modifier"
                and int(effect.get("value") or 0) < 0
            ):
                effect["value"] = (
                    int(effect["value"])
                    - self.rules_tribute_extra_power_loss(action)
                )
            if self.rules_modifier_is_prevented(effect):
                continue
            self.rules_engine["ongoingEffects"].append(effect)
            created.append(effect)
        self.record_rules_power_changes(powers_before)
        return created

    def prune_rules_ongoing_effects(self):
        self.refresh_rules_first_manifestations()
        # BOB's cards return as soon as it leaves the CZ, even while BOB
        # remains on the field. Gobres uses a different suspension lifetime.
        for source_id in {entry.get("sourceEffectId") for entry in self.rules_engine.get("suspendedCards") or []}:
            source = self.find_battlefield_item(source_id)
            if (
                source is not None
                and self.rules_item_card_rules(source).get("suspensionThresholds")
                and self.rules_field_zone(source) != "confrontation"
            ):
                self.release_rules_suspended_by(source_id)
        for pending in [entry for entry in self.battlefield if entry.get("pendingExile")]:
            self._rules_remove_field_item(pending, pending.get("ownerId"), "exile", "top")
        for expired in [
            entry for entry in self.battlefield
            if entry.get("playableFree") and entry["playableFree"] != self.phase_tracker["turn"]
        ]:
            expired.pop("playableFree", None)
        for stale in [
            entry for entry in self.battlefield
            if entry.get("willManifestation")
            and (
                entry["willManifestation"].get("turn") != self.phase_tracker["turn"]
                or self.rules_field_zone(entry) not in {"confrontation", "stalemate"}
            )
        ]:
            self.revert_rules_will_manifestation(stale)
        battlefield_ids = {item.get("id") for item in self.battlefield}
        current_turn = self.phase_tracker["turn"]
        kept = []
        removed = []
        for effect in self.rules_engine["ongoingEffects"]:
            target = effect.get("target", {})
            target_present = (
                target.get("itemId") in battlefield_ids
                if target.get("itemId")
                else target.get("playerId") in self.players
                if target.get("kind") == "player"
                else True
                if target.get("kind") == "global"
                else any(
                    action.get("id") == target.get("actionId")
                    for action in self.rules_engine.get("actionStack") or []
                )
            )
            copying = effect.get("kind") in {"copy_power_temperament", "copy_power_effects"}
            if not copying and effect.get("duration") == "while_source_and_target_on_field":
                target_item = self.find_battlefield_item(target.get("itemId"))
                if target_item is not None and self.rules_field_zone(target_item) == "stalemate":
                    target_present = False  # Stalemate is outside the field.
            source_required = copying or effect.get("duration") in {
                "while_source_and_target_on_field", "while_source_on_field",
            }
            if copying or effect.get("duration") == "while_source_on_field":
                target_present = True
            source_item = self.find_battlefield_item(
                effect.get("source", {}).get("itemId")
            )
            source_present = (
                source_item is not None
                and (copying
                     or self.rules_field_zone(source_item) != "stalemate")
            )
            turn_active = not (
                effect.get("duration") == "until_end_of_turn"
                and int(effect.get("startedTurn") or 0) < current_turn
            )
            next_turn_active = not (
                effect.get("duration") == "until_end_of_next_turn"
                and int(effect.get("startedTurn") or 0) + 1 < current_turn
            )
            resolution_active = not (
                effect.get("duration") == "until_resolution"
                and self.current_phase_group() in {"end", "recovery"}
            )
            if (
                target_present and turn_active and next_turn_active
                and resolution_active
                and (not source_required or source_present)
            ):
                kept.append(effect)
            else:
                removed.append(effect)
        self.rules_engine["ongoingEffects"] = kept
        for effect in removed:
            if effect.get("kind") != "drill_link":
                continue
            drill = self.find_battlefield_item((effect.get("source") or {}).get("itemId"))
            if drill is not None and (effect.get("target") or {}).get("itemId") not in battlefield_ids:
                # Parasitic Drill: the linked Will left the field, so the Drill is sacrificed.
                self._rules_remove_field_item(drill, drill.get("ownerId"), "graveyard", "top")
        self.refresh_rules_first_manifestations()
        return removed
