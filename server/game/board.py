"""Field layout, item state, Interzone and Support entry rules."""

import random

from .common import (
    NUM_SEATS, RULES_WILL_TYPES, RULES_STALEMATE_PASSIVE_KINDS, RULES_COPIED_EFFECT_KEYS, new_id
)


class BoardMixin:
    # -- assisted confrontation resolution ----------------------------
    def rules_field_zone(self, item):
        explicit = item.get("fieldZone")
        if explicit in {"field", "confrontation", "interzone", "stalemate"}:
            return explicit
        if item.get("id") in self.rules_engine.get("firstManifestationItemIds", {}).values():
            return "confrontation"
        return "field"

    # -- board layout (assisted rules) ---------------------------------
    # Slots on board-bg.webp, in logical coordinates (card = 150 x 210, seat 0 plays at the bottom)
    def rules_layout_slot(self, zone, seat, index):
        top = seat == 1
        if zone == "interzone":
            return 445.0 + (index % 3) * 305.0 + (index // 3) * 20.0, (285.0 if top else 1064.0) + (index // 3) * 14.0
        if zone == "confrontation":
            row = 525.0 if top else 800.0
            lift = (index // 4) * 30.0
            return 445.0 + (index % 4) * 215.0 + (index // 4) * 40.0, row + (lift if top else -lift)
        if zone == "stalemate":
            return 1429.0 + (index // 2) * 40.0, 560.0 + (index % 2) * 230.0
        return 445.0 + (index % 5) * 170.0, (45.0 if top else 1300.0) + (index // 5) * 14.0

    @staticmethod
    def rules_layout_rect(zone, seat):
        top = seat == 1
        if zone == "interzone":
            return (415.0, 271.0, 1322.0, 498.0) if top else (415.0, 1050.0, 1322.0, 1278.0)
        if zone == "confrontation":
            # each player keeps to their own half of the Confrontation Zone
            return (415.0, 510.0, 1322.0, 773.0) if top else (415.0, 773.0, 1322.0, 1037.0)
        if zone == "stalemate":
            return (1354.0, 543.0, 1703.0, 1008.0)
        return (415.0, 35.0, 1322.0, 270.0) if top else (415.0, 1290.0, 1322.0, 1515.0)

    def rules_auto_layout(self):
        """Put cards that just changed zone on a free slot of their zone; later manual moves are kept."""
        if not self.rules_engine.get("enabled") or len(self.players) < NUM_SEATS:
            return
        first_ids = set((self.rules_engine.get("firstManifestationItemIds") or {}).values())
        for item in self.battlefield:
            if item.get("stackedOn") or item.get("isTokenCard") and not item.get("faceUp"):
                continue
            metadata = self.rules_item_card_rules(item)
            card_type = metadata.get("type")
            is_manifestation = card_type == "manifestation" or item.get("isTokenCard")
            if not (
                is_manifestation and (item.get("faceUp") or item.get("id") in first_ids)
                or card_type == "persistent_will" and item.get("faceUp")
                or item.get("isSupport") and item.get("faceUp")
            ):
                continue
            zone = self.rules_field_zone(item)
            if zone == "field" and card_type != "persistent_will" and not metadata.get("playAsPersistentWill"):
                continue
            controller_id = self.rules_item_controller_id(item)
            seat = (self.players.get(controller_id) or {}).get("seat")
            key = f"{zone}:{controller_id}"
            if item.get("layoutKey") == key:
                continue
            left, top_edge, right, bottom = self.rules_layout_rect(zone, seat)
            card_x = float(item.get("x") or 0)
            card_y = float(item.get("y") or 0)
            dropped_in_zone = (
                left - 10 <= card_x and card_x + 150.0 <= right + 10
                and top_edge - 10 <= card_y and card_y + 210.0 <= bottom + 10
            )
            taken = {
                other.get("layoutSlot") for other in self.battlefield
                if other is not item and other.get("layoutKey") == key
                and not other.get("stackedOn")
            }
            free = [i for i in range(64) if i not in taken]
            if dropped_in_zone:
                # the drop only steers the card: it takes the free slot of its zone closest to where it was released
                index = min(free[:4], key=lambda i: (
                    (self.rules_layout_slot(zone, seat, i)[0] - card_x) ** 2
                    + (self.rules_layout_slot(zone, seat, i)[1] - card_y) ** 2
                ))
            else:
                index = free[0]
            item["layoutKey"] = key
            item["layoutSlot"] = index
            item["x"], item["y"] = self.rules_layout_slot(zone, seat, index)

    def rules_ongoing_effect_active(self, effect):
        """A temporarily blanked continuous source keeps its link, but applies nothing."""
        if effect.get("duration") not in {"while_source_and_target_on_field", "while_source_on_field"}:
            return True
        source = self.find_battlefield_item((effect.get("source") or {}).get("itemId"))
        if source is None:
            return False
        # Mimer's activated copying modifier already resolved independently.
        if effect.get("kind") == "copy_power_temperament":
            return True
        checking = getattr(self, "_rules_checking_effects", None)
        if checking is None:
            checking = self._rules_checking_effects = set()
        key = id(effect)
        if key in checking:
            return False
        checking.add(key)
        try:
            return self.rules_item_effects_active(source)
        finally:
            checking.remove(key)

    def rules_item_controller_id(self, item):
        linked = next((
            effect for effect in reversed(
                self.rules_engine.get("ongoingEffects") or []
            )
            if effect.get("kind") == "control_link"
            and effect.get("target", {}).get("itemId") == (item or {}).get("id")
            and self.rules_ongoing_effect_active(effect)
        ), None)
        return (
            linked.get("controllerId")
            if linked
            else (item or {}).get("controllerId") or (item or {}).get("ownerId")
        )

    def rules_item_card_rules(self, item, visiting=None):
        metadata = self._rules_item_card_rules_base(item, visiting)
        if isinstance(item, dict) and item.get("isTokenCard") and not item.get("isCopy"):
            # Generic Tokens have no printed cardId, but are Manifestations
            # for targeting and effects that enumerate Manifestations. Legacy
            # copies also carry this flag and keep their copied card's type.
            metadata = {**metadata, "type": "manifestation", "power": int(item.get("power") or 0)}
        manifestation = item.get("willManifestation") if isinstance(item, dict) else None
        if manifestation:
            # Rinq / Ju Lien: a Will that is a Manifestation until the Resolution.
            metadata = {
                **metadata, "type": "manifestation",
                "power": int(manifestation.get("power") or 0),
            }
        return metadata

    def _rules_item_card_rules_base(self, item, visiting=None):
        if not isinstance(item, dict):
            return {}
        metadata = dict(self.card_rules.get(item.get("cardId"), {}))
        visiting = set(visiting or ())
        item_id = item.get("id")
        if not item_id or item_id in visiting:
            return metadata
        visiting.add(item_id)
        if item.get("gummoCopy"):
            # Gummo: gains the effects of a Vessel card in addition to its own.
            copied = self.card_rules.get(item["gummoCopy"], {})
            for key in RULES_COPIED_EFFECT_KEYS:
                if key not in copied:
                    continue
                if isinstance(copied[key], list):
                    metadata[key] = list(metadata.get(key) or []) + list(copied[key])
                elif key not in metadata:
                    metadata[key] = copied[key]
        copy_effect = next((
            effect for effect in reversed(
                self.rules_engine.get("ongoingEffects") or []
            )
            if effect.get("kind") == "copy_power_effects"
            and effect.get("source", {}).get("itemId") == item_id
        ), None)
        if copy_effect is None:
            return metadata
        copied_metadata = copy_effect.get("copiedRules") or {}
        for key in RULES_COPIED_EFFECT_KEYS:
            if key in copied_metadata:
                metadata[key] = copied_metadata[key]
        return metadata

    def _move_random_zone_card(self, container_id, result):
        from_zone = result.get("fromZone")
        destination = result.get("zone")
        position = result.get("position")
        reason = result.get("reason")
        container = self.players.get(container_id)
        candidates = [
            card_id for card_id in (container or {}).get("zones", {}).get(from_zone, [])
            if self.card_rules.get(card_id, {}).get("type") == result.get("cardType")
        ]
        if not candidates:
            payload = {
                "kind": "move_card", "status": "no_eligible_card", "random": True,
                "fromZone": from_zone, "fromContainerId": container_id,
                "toZone": destination, "position": position,
            }
            if reason:
                payload["reason"] = reason
            return payload
        card_id = random.choice(candidates)
        owner_id = self.card_owner_in_zone(container_id, from_zone, card_id)
        error, _owner_id, replacement = self.move_zone_card_by_effect(
            container_id, from_zone, owner_id, destination, card_id, position,
        )
        payload = {
            "kind": "move_card",
            "status": (
                "target_missing" if error
                else replacement["status"] if replacement
                else "moved"
            ),
            "random": True, "cardId": card_id, "ownerId": owner_id,
            "fromZone": from_zone, "fromContainerId": container_id,
            "toZone": destination, "position": position,
        }
        if reason:
            payload["reason"] = reason
        if replacement:
            payload["replacement"] = replacement
        return payload

    def rules_will_tribute_cost(self, card_id):
        metadata = self.card_rules.get(card_id, {})
        symbols = sum(self.rules_requirements_from_symbols(metadata.get("powerCost")).values())
        return int(symbols or metadata.get("cost") or 0)

    def revert_rules_will_manifestation(self, item):
        item.pop("willManifestation", None)
        item["isSupport"] = False
        if self.rules_field_zone(item) in {"confrontation", "stalemate"}:
            item["fieldZone"] = "field"
        item["stackedOn"] = None

    def settle_rules_will_manifestations(self, result, participant_ids):
        """End of the confrontation: Rinq / Ju Lien Wills stop being Manifestations."""
        settled = []
        for item in list(self.battlefield):
            manifestation = item.get("willManifestation")
            if not manifestation or item.get("id") not in participant_ids:
                continue
            controller_id = self.rules_item_controller_id(item)
            if result.get("stalemate"):
                key = "onStalemate"
            elif result.get("winnerId") == controller_id:
                key = "onWin"
            else:
                key = "onLoss"
            outcome = manifestation.get(key) or "revert"
            owner_id = item.get("ownerId")
            if outcome == "revert":
                self.revert_rules_will_manifestation(item)
                entry = {"status": "reverted"}
            elif outcome == "destroy":
                entry = self._rules_remove_field_item_by_effect(
                    item, owner_id, "graveyard", "top", reason="destroy"
                )
            elif outcome == "exile":
                entry = self._rules_remove_field_item(item, owner_id, "exile", "top")
            else:
                # Ju Lien: the Will stays on the field (effects still off) and can
                # be played from there, without tribute, until the end of the turn.
                self.revert_rules_will_manifestation(item)
                item["playableFree"] = self.phase_tracker["turn"]
                entry = {"status": "playable_free"}
            participant_ids.discard(item.get("id"))
            settled.append({**entry, "itemId": item.get("id"), "cardId": item.get("cardId"), "outcome": outcome})
        if settled:
            result["willManifestations"] = settled
        return settled

    def rules_item_functions_in_stalemate(self, item):
        """Cards keep their effects in the Stalemate Zone only when their text
        says so (Fee-fee's "As long as it is in the Stalemate Zone", Nubilung's
        Support from the Stalemate Zone)."""
        metadata = self.rules_item_card_rules(item)
        if metadata.get("supportFromStalemate"):
            return True
        if any(
            (ability.get("trigger") or {}).get("zone") == "stalemate"
            for ability in metadata.get("triggeredAbilities") or []
        ):
            return True
        return any(
            passive.get("kind") in RULES_STALEMATE_PASSIVE_KINDS
            for passive in metadata.get("passiveEffects") or []
        )

    def rules_item_effects_active(self, item):
        if not item or item not in self.battlefield or not item.get("faceUp"):
            return False
        # the Stalemate Zone is not part of the field: its cards lose their effects
        if (
            self.rules_field_zone(item) == "stalemate"
            and not self.rules_item_functions_in_stalemate(item)
        ):
            return False
        if item.get("effectsDisabled"):
            return False
        if int(round(float(item.get("rotation") or 0))) % 180 and any(
            passive.get("kind") == "no_effects_while_exhausted"
            for passive in self.rules_item_card_rules(item).get(
                "passiveEffects"
            ) or []
        ):
            return False
        if self._rules_effects_blanked_by_other(item):
            return False
        return not any(
            effect.get("kind") in {"lose_effects", "obscure_lock", "interzone_lock"}
            and effect.get("target", {}).get("itemId") == item.get("id")
            and self.rules_ongoing_effect_active(effect)
            for effect in self.rules_engine.get("ongoingEffects") or []
        )

    def _rules_effects_blanked_by_other(self, item):
        """Discombobulator: while on the field, every other card has no effects."""
        for other in self.battlefield:
            if (
                other is item or not other.get("faceUp") or other.get("effectsDisabled")
                or self.rules_field_zone(other) == "stalemate"
                or not any(
                    passive.get("kind") == "disable_other_effects"
                    for passive in self.rules_item_card_rules(other).get("passiveEffects") or []
                )
            ):
                continue
            if any(
                effect.get("kind") == "lose_effects"
                and effect.get("target", {}).get("itemId") == other.get("id")
                and self.rules_ongoing_effect_active(effect)
                for effect in self.rules_engine.get("ongoingEffects") or []
            ):
                continue
            return True
        return False

    def rules_interzone_item_replaceable(self, item):
        if item and self.rules_item_effects_active(item) and any(
            passive.get("kind") == "unreplaceable_in_interzone"
            for passive in self.rules_item_card_rules(item).get(
                "passiveEffects"
            ) or []
        ):
            return False
        return not any(
            effect.get("kind") == "interzone_lock"
            and effect.get("target", {}).get("itemId") == (item or {}).get("id")
            for effect in self.rules_engine.get("ongoingEffects") or []
        )

    def rules_vessel_locked(self, container_id):
        """Unreachable Pillar: Vessel cards are Protected and have no effects."""
        return any(
            self.rules_item_controller_id(source) == container_id
            for source in self.rules_active_passive_sources(
                "vessel_protected_no_effects"
            )
        )

    def rules_active_passive_sources(self, kind):
        return [
            item for item in self.battlefield
            if self.rules_item_effects_active(item)
            and self.rules_field_zone(item) != "stalemate"
            and any(
                passive.get("kind") == kind
                for passive in self.rules_item_card_rules(
                    item
                ).get("passiveEffects") or []
            )
        ]

    def apply_rules_drill_drain(self, item_id):
        """Parasitic Drill: whenever the linked Will triggers or is activated, its controller loses points."""
        if not item_id:
            return 0
        target = self.find_battlefield_item(item_id)
        if target is None:
            return 0
        lost = 0
        for effect in list(self.rules_engine.get("ongoingEffects") or []):
            if (
                effect.get("kind") != "drill_link"
                or (effect.get("target") or {}).get("itemId") != item_id
            ):
                continue
            source = self.find_battlefield_item((effect.get("source") or {}).get("itemId"))
            if source is None or not self.rules_item_effects_active(source):
                continue
            amount = int(effect.get("value") or 10)
            self.adjust_rules_score(self.rules_item_controller_id(target), -amount)
            lost += amount
        return lost

    def rules_exiles_incoming_manifestations(self, player_id, card_id):
        """Nullify Reason: Manifestations about to enter this player's Interzone, deck or Limbo are exiled."""
        if (
            not hasattr(self, "rules_engine")
            or not self.rules_engine.get("enabled")
            or self.card_rules.get(card_id, {}).get("type") != "manifestation"
        ):
            return False
        return any(
            effect.get("kind") == "exile_incoming_manifestations"
            and (effect.get("target") or {}).get("playerId") == player_id
            for effect in self.rules_engine.get("ongoingEffects") or []
        )

    def toggle_rules_item_option(self, player_id, item_id, option):
        item = self.find_battlefield_item(item_id)
        if (
            item is None or option not in {"outcastOff", "karmapultAuto"}
            or self.rules_item_controller_id(item) != player_id
        ):
            return "This option is not available.", None
        if item.get(option):
            item.pop(option)
        else:
            item[option] = True
        return None, {"itemId": item_id, "option": option, "enabled": bool(item.get(option))}

    def mark_rules_interzone_entry(self, item):
        holder = self.rules_karmapult_holder(self.rules_item_controller_id(item), item)
        if (
            holder is not None and holder.get("karmapultAuto") and holder is not item
            and item in self.battlefield
            and not item.get("isCopy") and not item.get("isTokenCard")
        ):
            # Karmapult: put on it instead of entering the Interzone.
            self.battlefield.remove(item)
            for other in self.battlefield:
                if other.get("stackedOn") == item.get("id"):
                    other["stackedOn"] = None
            holder.setdefault("attachedCards", []).append({
                "cardId": item["cardId"], "ownerId": item["ownerId"],
            })
            self.rules_sync_attached_counter(holder)
            return
        item["interzoneTurn"] = int(self.phase_tracker.get("turn") or 1)
        if self.rules_exiles_incoming_manifestations(
            self.rules_item_controller_id(item), item.get("cardId")
        ) and not item.get("isCopy") and not item.get("isTokenCard"):
            if item in self.battlefield:
                self._rules_remove_field_item(item, item.get("ownerId"), "exile", "top")
            else:
                item["pendingExile"] = True
            return
        self.apply_rules_interzone_entry_penalty(item)

    def apply_rules_interzone_entry_penalty(self, item):
        """Spiked Pit: a Manifestation entering an opponent's Interzone loses Power."""
        if (
            not self.rules_engine.get("enabled")
            or self.rules_item_card_rules(item).get("type")
            != "manifestation"
        ):
            return 0
        controller_id = self.rules_item_controller_id(item)
        total = sum(
            int(passive.get("value") or 0)
            for source in self.rules_active_passive_sources(
                "interzone_entry_penalty"
            )
            if self.rules_item_controller_id(source) != controller_id
            for passive in self.rules_item_card_rules(source).get(
                "passiveEffects"
            ) or []
            if passive.get("kind") == "interzone_entry_penalty"
        )
        if not total:
            return 0
        self.adjust_rules_power_counter(item, total)
        return total

    def mark_rules_confrontation_entry(self, item):
        self.rules_engine["confrontationEntrySequence"] += 1
        item["fieldZone"] = "confrontation"
        item["confrontationOrder"] = self.rules_engine["confrontationEntrySequence"]

    def mark_rules_support_entry(self, item):
        item["isSupport"] = True
        item["fieldZone"] = "confrontation"
        metadata = self.rules_item_card_rules(item)
        destination = metadata.get("supportWinDestination")
        if destination == "exile":
            item["supportWinDestination"] = destination
        effect = metadata.get("supportWinEffect")
        if isinstance(effect, dict) and effect.get("kind") == "opponent_vessel_score":
            item["supportWinEffect"] = {
                "kind": "opponent_vessel_score",
                "value": max(0, min(int(effect.get("value") or 0), 999)),
            }
        self.mark_rules_confrontation_entry(item)
        turn = self.phase_tracker["turn"]
        item["supportUsedTurn"] = turn
        for bonus in self.rules_engine.get("supportEntryBonuses") or []:
            if bonus.get("turn") == turn and bonus.get("playerId") == self.rules_item_controller_id(item):
                self.append_rules_ongoing_effect({
                    "id": new_id(), "actionId": None, "abilityId": "support-entry-bonus",
                    "controllerId": bonus["playerId"],
                    "source": {"cardId": bonus.get("sourceCardId")},
                    "target": {
                        "kind": "card", "itemId": item["id"],
                        "cardId": item.get("cardId"), "ownerId": item.get("ownerId"),
                    },
                    "kind": "power_modifier", "value": int(bonus.get("value") or 1),
                    "duration": "until_end_of_turn", "startedTurn": turn,
                })

    def rules_player_lost_confrontation_this_turn(self, player_id):
        """Loop and "if you lost the confrontation" effects: a confrontation lost this turn, even once its
        result has been cleared (a rematch, The Stomper ending the confrontation)."""
        turn = self.phase_tracker["turn"]
        if (self.rules_engine.get("confrontationLosses") or {}).get(str(turn)) == player_id:
            return True
        outcome = self.rules_engine.get("confrontationResult") or {}
        return outcome.get("turn") == turn and outcome.get("loserId") == player_id

    def rules_support_condition_met(self, item, condition):
        if not condition:
            return False
        owner_id = self.rules_item_controller_id(item)
        turn = self.phase_tracker["turn"]
        if condition == "lost_previous_confrontation":
            return (self.rules_engine.get("confrontationLosses") or {}).get(str(turn - 1)) == owner_id
        if condition == "limbo_exit_this_turn":
            return int(self.rules_engine.get("limboExitTurn") or 0) == turn
        if condition == "five_wills_in_limbo":
            return sum(
                1 for card_id in self.players.get(owner_id, {}).get("zones", {}).get("graveyard", [])
                if self.card_rules.get(card_id, {}).get("type") in RULES_WILL_TYPES
            ) >= 5
        return False

    def rules_confrontation_entry_blocked(self, player_id, metadata):
        if metadata.get("cannotEnterConfrontation"):
            return True
        needed = int(metadata.get("confrontationEntryLimboWills") or 0)
        if needed and player_id in self.players:
            return sum(
                1 for card_id in self.players[player_id]["zones"].get("graveyard", [])
                if self.card_rules.get(card_id, {}).get("type") in RULES_WILL_TYPES
            ) < needed
        return False

    def rules_card_can_enter_support(self, item, from_zone="interzone"):
        metadata = self.rules_item_card_rules(item)
        if self.rules_confrontation_entry_blocked(
            self.rules_item_controller_id(item), metadata
        ):
            return False
        if not self.rules_item_effects_active(item):
            return False
        if from_zone == "hand":
            return self.rules_support_from_hand_available(item.get("ownerId"), item.get("cardId"))
        if any(
            effect.get("kind") == "grant_support"
            and effect.get("target", {}).get("itemId") == item.get("id")
            and self.rules_ongoing_effect_active(effect)
            for effect in self.rules_engine.get("ongoingEffects") or []
        ):
            return True
        if from_zone == "stalemate":
            return bool(metadata.get("supportFromStalemate"))
        counter_name = metadata.get("supportWhenNoCounter")
        return bool(
            metadata.get("supportFromInterzone")
            or self.rules_support_condition_met(item, metadata.get("supportCondition"))
            or int(item.get("supportUntilTurn") or 0) == self.phase_tracker["turn"]
            or (
                counter_name
                and int((item.get("counters") or {}).get(counter_name) or 0) <= 0
            )
        )

    def rules_item_has_float(self, item):
        if not self.rules_item_effects_active(item):
            return False
        effects = [
            effect for effect in self.rules_engine.get("ongoingEffects") or []
            if effect.get("target", {}).get("itemId") == item.get("id")
        ]
        latest = next((effect for effect in reversed(effects)
                       if effect.get("kind") in {"grant_float", "remove_float"}
                       and self.rules_ongoing_effect_active(effect)), None)
        if latest is not None:
            return latest["kind"] == "grant_float"
        if self.rules_item_card_rules(item).get("float") or item.get("hasFloat"):
            return True
        return any(
            passive.get("kind") == "float_with_counter"
            and int((item.get("counters") or {}).get(
                passive.get("counter")
            ) or 0) > 0
            for source in self.rules_active_passive_sources(
                "float_with_counter"
            )
            if self.rules_item_controller_id(source)
            == self.rules_item_controller_id(item)
            for passive in self.rules_item_card_rules(
                source
            ).get("passiveEffects") or []
        )

    def rules_item_has_persist(self, item):
        if not self.rules_item_effects_active(item):
            return False
        if self.rules_item_card_rules(item).get("persist") or item.get("gainsPersist"):
            return True
        return any(
            effect.get("kind") == "grant_persist"
            and effect.get("target", {}).get("itemId") == item.get("id")
            for effect in self.rules_engine.get("ongoingEffects") or []
        )

    def rules_interzone_share_anchor(self, player_id, entering_item):
        interzone_items = self.rules_confrontation_items(player_id, ("interzone",))
        if not interzone_items:
            return None
        if self.rules_item_has_float(entering_item):
            anchor = next(
                (item for item in interzone_items if not item.get("stackedOn")),
                interzone_items[0],
            )
            return anchor.get("stackedOn") or anchor.get("id")
        floating = next(
            (item for item in interzone_items if self.rules_item_has_float(item)),
            None,
        )
        return (floating.get("stackedOn") or floating.get("id")) if floating else None

    def rules_interzone_capacity(self, player_id):
        bonus = 0
        for item in self.rules_active_passive_sources("extend_interzone"):
            if self.rules_item_controller_id(item) != player_id:
                continue
            bonus += sum(
                int(passive.get("value") or 0)
                for passive in self.rules_item_card_rules(item).get(
                    "passiveEffects"
                ) or []
                if passive.get("kind") == "extend_interzone"
            )
        return 3 + max(0, bonus)

    def rules_interzone_slot_count(self, player_id):
        return sum(
            1 for item in self.rules_confrontation_items(player_id, ("interzone",))
            if not item.get("stackedOn")
        )

    def rules_stack_action_targets_field_card(self, stack_action):
        return any(
            entry.get("kind") == "card"
            and self.find_battlefield_item(entry.get("itemId")) is not None
            for entry in (stack_action or {}).get("targets") or []
        )

    def rules_retarget_error(self, targets):
        """Scrambling Beacon: the new target must be legal for the redirected card or effect."""
        stack_entry, new_target = (list(targets) + [None, None])[:2]
        target_action = next((
            entry for entry in self.rules_engine.get("actionStack") or []
            if stack_entry and entry.get("id") == stack_entry.get("actionId")
        ), None)
        if target_action is None or not isinstance(new_target, dict):
            return "The selected card or effect is no longer on the Stack."
        rules = self.rules_action_target_rules(target_action)
        if not rules or "groups" in rules or int(rules.get("max") or 0) != 1:
            return "The target of this card or effect cannot be changed."
        error = self.rules_ability_targets_error(
            rules, [new_target], target_action.get("controllerId"),
            source_item_id=(target_action.get("source") or {}).get("itemId"),
        )
        return error or (
            None if new_target.get("kind") == "card"
            else "Choose a card on the field as the new target."
        )

    def rules_stack_action_targets_confrontation(self, stack_action):
        return any(
            entry.get("kind") == "card"
            and (item := self.find_battlefield_item(entry.get("itemId"))) is not None
            and self.rules_field_zone(item) == "confrontation"
            and self.rules_item_card_rules(item).get("type") == "manifestation"
            for entry in (stack_action or {}).get("targets") or []
        )

    def rules_last_opponent_support(self, player_id, max_base_power):
        """Ranba: the last Manifestation an opponent put in Support, if still there and weak enough."""
        entry = next((
            entry for entry in reversed(self.rules_engine.get("supportEntries") or [])
            if entry.get("controllerId") != player_id
        ), None)
        if entry is None:
            return None
        item = self.find_battlefield_item(entry.get("itemId"))
        if item is None or not item.get("isSupport"):
            return None
        if self.rules_item_controller_id(item) == player_id:
            return None
        power = self.rules_manifestation_base_power(item)
        if power > max_base_power:
            return None
        return item

    def rules_top_of_stack_is_will(self):
        stack = self.rules_engine.get("actionStack") or []
        return bool(stack) and (
            stack[-1].get("kind") == "play_card"
            and self.card_rules.get((stack[-1].get("source") or {}).get("cardId"), {}).get("type")
            in RULES_WILL_TYPES
        )

    def rules_support_from_hand_available_anytime(self, card_id):
        condition = self.card_rules.get(card_id, {}).get("supportFromHandCondition") or {}
        return condition.get("kind") == "top_of_stack_is_will" and self.rules_top_of_stack_is_will()

    def rules_conditional_support_hand_card_ids(self):
        """Hand cards whose conditional Support (passive) is currently active, per player."""
        result = {}
        for player_id, player in self.players.items():
            ids = []
            for card_id in dict.fromkeys(player["zones"].get("hand", [])):
                metadata = self.card_rules.get(card_id, {})
                condition = metadata.get("supportCondition")
                if condition and self.rules_support_condition_met(
                    {"ownerId": player_id, "controllerId": player_id}, condition
                ):
                    ids.append(card_id)
                # conditional Support from hand (Unruly Flail...): the server decides,
                # so the client never has to re-derive it from the card text
                elif metadata.get("supportFromHandCondition") and self.rules_support_from_hand_available(player_id, card_id):
                    ids.append(card_id)
            result[player_id] = ids
        return result

    def rules_support_from_hand_available(self, player_id, card_id):
        metadata = self.card_rules.get(card_id, {})
        if metadata.get("supportFromHand"):
            return True
        if any(
            entry.get("playerId") == player_id
            and entry.get("cardId") == card_id
            and entry.get("fromZone") == "hand"
            and entry.get("asSupport")
            and int(entry.get("turn") or 0) == self.phase_tracker["turn"]
            for entry in self.rules_engine.get("playPermissions") or []
        ):
            return True
        if metadata.get("supportCondition") and self.rules_support_condition_met(
            {"ownerId": player_id, "controllerId": player_id}, metadata.get("supportCondition")
        ):
            return True
        condition = metadata.get("supportFromHandCondition") or {}
        if condition.get("kind") == "top_of_stack_is_will":
            return self.rules_top_of_stack_is_will()
        if condition.get("kind") == "opponent_will_on_stack_targets_confrontation":
            return any(
                entry.get("controllerId") != player_id
                and entry.get("kind") == "play_card"
                and self.card_rules.get(
                    (entry.get("source") or {}).get("cardId"), {}
                ).get("type") in RULES_WILL_TYPES
                and self.rules_stack_action_targets_confrontation(entry)
                for entry in self.rules_engine.get("actionStack") or []
            )
        if condition.get("kind") != "opponent_support_from_interzone_this_turn":
            return False
        return any(
            int(entry.get("turn") or 0) == self.phase_tracker["turn"]
            and entry.get("controllerId") != player_id
            and entry.get("fromZone") == "interzone"
            for entry in self.rules_engine.get("supportEntries") or []
        )

    def rules_play_restriction_count(self, player_id, card_id):
        turn = self.phase_tracker["turn"]
        return sum(
            1 for restriction in self.rules_engine.get("playRestrictions") or []
            if restriction.get("playerId") == player_id
            and restriction.get("cardId") == card_id
            and int(restriction.get("turn") or 0) == turn
        )

    def rules_card_play_restriction_error(self, player_id, card_id):
        restricted = self.rules_play_restriction_count(player_id, card_id)
        if restricted <= 0:
            return None
        hand_count = self.players.get(player_id, {}).get("zones", {}).get("hand", []).count(card_id)
        return "This card cannot be played again until the end of the turn." if hand_count <= restricted else None

    def rules_card_chain_restriction_error(self, player_id, card_id):
        if self.card_rules.get(card_id, {}).get("playAsPersistentWill"):
            return "This Manifestation can only be played as a Persistent Will and cannot be Chained."
        return self.rules_card_play_restriction_error(player_id, card_id)

    def prune_rules_play_restrictions(self):
        current_turn = self.phase_tracker["turn"]
        self.rules_engine["playRestrictions"] = [
            restriction for restriction in self.rules_engine.get("playRestrictions") or []
            if int(restriction.get("turn") or 0) >= current_turn
        ]
        self.rules_engine["supportEntries"] = [
            entry for entry in self.rules_engine.get("supportEntries") or []
            if int(entry.get("turn") or 0) >= current_turn
        ]

    def rules_support_from_hand_error(self, player_id, card_id):
        if not self.rules_engine["enabled"]:
            return None
        if self.current_phase_group() == "end" and self.rules_player_skips_end_phase(player_id):
            return "You skip your End Phase this turn."
        metadata = self.card_rules.get(card_id, {})
        if metadata.get("type") != "manifestation":
            return None
        if self.rules_confrontation_entry_blocked(player_id, metadata):
            return "This Manifestation cannot enter the Confrontation Zone."
        if metadata.get("endPhaseInterzonePlay"):
            if self.current_phase_id() == "end_actions":
                if self.rules_engine.get("priorityPlayerId") != player_id:
                    return "You do not have priority."
                if self.rules_engine.get("actionStack"):
                    return "Resolve the Stack before playing this Manifestation."
                if self.rules_interzone_slot_count(player_id) >= self.rules_interzone_capacity(player_id):
                    return "Your Interzone is full."
                return None
            if self.current_phase_id() != "confrontation_reaction":
                return "This Manifestation can only be played into the Interzone during the End Phase."
        if (
            self.current_phase_id() != "confrontation_reaction"
            and not self.rules_support_from_hand_available_anytime(card_id)
        ):
            return "A Support Manifestation can only be played from Hand during Reaction."
        if self.rules_engine.get("priorityPlayerId") != player_id:
            return "You do not have priority."
        if not self.rules_support_from_hand_available(player_id, card_id):
            return "This Manifestation does not have Support from Hand."
        return None
