"""Effect results that change power, counters and temperaments."""

from ..common import RULES_WILL_TYPES, RULES_TEMPERAMENTS, new_id


class PowerEffectsMixin:
    def set_rules_item_temperament(self, item, temperament, action):
        if self.rules_modifiers_prevented(item):
            return []
        item["temperamentOverride"] = temperament
        return self.create_rules_ongoing_effects({
            **action,
            "targets": [{"kind": "card", "itemId": item["id"], "cardId": item.get("cardId")}],
            "ability": {"id": (action.get("ability") or {}).get("id"), "ongoingEffect": {
                "kind": "temperament_override", "temperament": temperament, "duration": "while_target_on_field",
            }},
        })

    def _rules_result_add_power_counter_target(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "card"
        ), None)
        item = self.find_battlefield_item((target or {}).get("itemId"))
        if item is None:
            return {"kind": result.get("kind"), "status": "target_missing"}
        self.adjust_rules_power_counter(item, int(result.get("value") or 0))
        return {
            "kind": result.get("kind"), "status": "changed",
            "itemId": item["id"], "value": int(result.get("value") or 0),
        }

    def _rules_result_weaken_target_per_hand_card(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "card"
        ), None)
        count = len(self.players[player_id]["zones"]["hand"])
        if target is None or count <= 0:
            return {"kind": result.get("kind"), "status": "nothing", "count": count}
        effects = self.create_rules_ongoing_effects({
            **action,
            "targets": [target],
            "ability": {
                "id": f'{(action.get("ability") or {}).get("id")}:weaken',
                "ongoingEffect": {
                    "kind": "power_modifier", "value": -count,
                    "duration": "until_end_of_turn",
                },
            },
        })
        return {
            "kind": result.get("kind"), "status": "weakened",
            "count": count, "effects": len(effects),
        }

    def _rules_result_power_counter_from_other_target(self, action, result, player_id, player):
        cards = [
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "card"
        ]
        if len(cards) != 2:
            return {"kind": result.get("kind"), "status": "target_missing"}
        weakened = self.find_battlefield_item(cards[0].get("itemId"))
        reference = self.find_battlefield_item(cards[1].get("itemId"))
        if (
            weakened is None or reference is None
            or self.rules_item_controller_id(weakened)
            != self.rules_item_controller_id(reference)
            or not reference.get("isSupport")
        ):
            return {"kind": result.get("kind"), "status": "target_missing"}
        base = self.rules_manifestation_base_power(reference)
        self.adjust_rules_power_counter(weakened, -base)
        return {
            "kind": result.get("kind"), "status": "weakened",
            "itemId": weakened["id"], "value": -base,
        }

    def _rules_result_optional_discard_manifestation_weaken_target(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "card"
        ), None)
        hand = player["zones"]["hand"]
        if (
            target is None
            or not any(self.card_rules.get(c, {}).get("type") == "manifestation" for c in hand)
        ):
            return {"kind": result.get("kind"), "status": "no_hand_card"}
        if not action.get("optionalAccepted"):
            return {"kind": result.get("kind"), "status": "declined"}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "discard_from_hand",
            "playerId": player_id, "count": 1,
            "requireManifestation": True,
            "weakenTargetItemId": target.get("itemId"),
            "actionId": action.get("id"),
            "controllerId": action.get("controllerId"),
            "sourceCardId": (action.get("source") or {}).get("cardId"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "discard_from_hand", "playerId": player_id,
            "count": 1, "requireManifestation": True,
        }

    def _rules_result_bottom_hand_card_remove_counters(self, action, result, player_id, player):
        if not player["zones"]["hand"]:
            return {"kind": result.get("kind"), "status": "no_hand_card"}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "discard_from_hand",
            "playerId": player_id, "count": 1,
            "destination": "deck_bottom_from_hand",
            "sourceItemId": (action.get("source") or {}).get("itemId"),
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "removeCounter": {"name": "Enigma", "amount": 2},
            "actionId": action.get("id"),
            "controllerId": action.get("controllerId"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "discard_from_hand", "playerId": player_id, "count": 1,
        }

    def _rules_result_restore_exhausted_targets(self, action, result, player_id, player):
        restored = []
        temperaments = set()
        for entry in action.get("targets") or []:
            item = self.find_battlefield_item(entry.get("itemId"))
            if item is None or int(round(float(item.get("rotation") or 0))) % 180 == 0:
                continue
            temperament = self.rules_manifestation_characteristics(item)["temperament"]
            if item.get("id") == (action.get("source") or {}).get("itemId") or temperament in temperaments:
                continue
            temperaments.add(temperament)
            item["rotation"] = 0.0
            restored.append(item["id"])
        return {"kind": result.get("kind"), "status": "restored", "itemIds": restored}

    def _rules_result_optional_discard_wills_for_power(self, action, result, player_id, player):
        hand = player["zones"]["hand"]
        wills = [c for c in hand if self.card_rules.get(c, {}).get("type") in RULES_WILL_TYPES]
        if not wills:
            return {"kind": result.get("kind"), "status": "no_hand_card"}
        if not action.get("optionalAccepted"):
            return {"kind": result.get("kind"), "status": "declined"}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "discard_from_hand",
            "playerId": player_id, "count": len(wills), "upTo": True,
            "requireTypes": sorted(RULES_WILL_TYPES),
            "sourcePowerPerDiscard": int(result.get("value") or 1),
            "sourceItemId": (action.get("source") or {}).get("itemId"),
            "actionId": action.get("id"),
            "controllerId": action.get("controllerId"),
            "sourceCardId": (action.get("source") or {}).get("cardId"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "discard_from_hand", "playerId": player_id,
            "count": len(wills), "upTo": True,
            "requireTypes": sorted(RULES_WILL_TYPES),
        }

    def _rules_result_restore_source_counter(self, action, result, player_id, player):
        source_item = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
        if source_item is None:
            return {"kind": result.get("kind"), "status": "source_missing"}
        counters = source_item.setdefault("counters", {})
        name = str(result.get("counter") or "")
        key = next((k for k in counters if str(k).casefold() == name.casefold()), name)
        counters[key] = int(result.get("value") or 0)
        return {"kind": result.get("kind"), "status": "restored", "counter": name, "value": counters[key]}

    def _rules_result_set_interzone_power(self, action, result, player_id, player):
        effects = []
        for item in self.rules_confrontation_items(None, ("interzone",)):
            effect = {
                "id": new_id(), "actionId": action.get("id"),
                "abilityId": (action.get("ability") or {}).get("id"),
                "controllerId": player_id,
                "source": dict(action.get("source") or {}),
                "target": {
                    "kind": "card", "itemId": item["id"],
                    "cardId": item.get("cardId"), "ownerId": item.get("ownerId"),
                },
                "kind": "power_set",
                "duration": "until_end_of_turn",
                "startedTurn": self.phase_tracker["turn"],
                "value": int(result.get("value") or 1),
            }
            effect["powerAdjustment"] = effect["value"] - self.rules_manifestation_characteristics(item)["power"]
            self.append_rules_ongoing_effect(effect)
            effects.append(effect["id"])
        return {
            "kind": result.get("kind"),
            "status": "set" if effects else "nothing", "effectIds": effects,
        }

    def _rules_result_exile_limbo_wills_add_power_each(self, action, result, player_id, player):
        source_item = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
        exiled = []
        for target in action.get("targets") or []:
            if target.get("kind") != "zone_card" or target.get("zone") != "graveyard":
                continue
            container_id = target.get("containerId")
            card_id = target.get("cardId")
            if self.card_rules.get(card_id, {}).get("type") not in RULES_WILL_TYPES:
                continue
            owner_id = self.card_owner_in_zone(container_id, "graveyard", card_id)
            if owner_id is None:
                continue
            error, _owner, _replacement = self.move_zone_card_by_effect(
                container_id, "graveyard", owner_id, "exile", card_id, "top"
            )
            if not error and not _replacement:
                exiled.append(card_id)
        if exiled and source_item is not None:
            self.append_rules_ongoing_effect({
                "id": new_id(), "actionId": action.get("id"),
                "abilityId": (action.get("ability") or {}).get("id"),
                "controllerId": player_id,
                "source": dict(action.get("source") or {}),
                "target": {
                    "kind": "card", "itemId": source_item["id"],
                    "cardId": source_item.get("cardId"), "ownerId": source_item.get("ownerId"),
                },
                "kind": "power_modifier", "duration": "until_end_of_turn",
                "startedTurn": self.phase_tracker["turn"], "value": len(exiled),
            })
        return {
            "kind": result.get("kind"),
            "status": "exiled" if exiled else "nothing", "cardIds": exiled,
        }

    def _rules_result_drain_excess_essence_power(self, action, result, player_id, player):
        total = 0
        for token in list(self.tokens):
            if token.get("isEssence") and not token.get("isNeutralCounter"):
                total += max(0, int(token.get("counters", {}).get("essence") or 0))
                self.tokens.remove(token)
        target = next((
            entry for entry in action.get("targets") or [] if entry.get("kind") == "card"
        ), None)
        item = self.find_battlefield_item((target or {}).get("itemId"))
        if item is not None and total:
            self.append_rules_ongoing_effect({
                "id": new_id(), "actionId": action.get("id"),
                "abilityId": (action.get("ability") or {}).get("id"),
                "controllerId": player_id,
                "source": dict(action.get("source") or {}),
                "target": {
                    "kind": "card", "itemId": item["id"],
                    "cardId": item.get("cardId"), "ownerId": item.get("ownerId"),
                },
                "kind": "power_modifier", "duration": "until_end_of_turn",
                "startedTurn": self.phase_tracker["turn"], "value": total,
            })
        return {
            "kind": result.get("kind"),
            "status": "drained" if total else "nothing", "essence": total,
        }

    def _rules_result_set_field_power(self, action, result, player_id, player):
        # "on the field": the Stalemate Zone is not part of the field
        items = self.rules_confrontation_items(None, ("interzone", "confrontation"))
        bases = {item["id"]: self.rules_manifestation_base_power(item) for item in items}
        floor = min(bases.values()) if bases else 0
        effect_ids = []
        for item in items:
            value = bases[item["id"]] if result.get("mode") == "base" else floor
            effect = {
                "id": new_id(), "actionId": action.get("id"),
                "abilityId": (action.get("ability") or {}).get("id"),
                "controllerId": player_id,
                "source": dict(action.get("source") or {}),
                "target": {
                    "kind": "card", "itemId": item["id"],
                    "cardId": item.get("cardId"), "ownerId": item.get("ownerId"),
                },
                "kind": "power_set_maximum", "duration": "until_end_of_turn",
                "startedTurn": self.phase_tracker["turn"], "value": int(value), "preventsModifiers": True,
            }
            effect["powerAdjustment"] = effect["value"] - self.rules_manifestation_characteristics(item)["power"]
            if self.append_rules_ongoing_effect(effect):
                effect_ids.append(effect["id"])
        return {
            "kind": result.get("kind"), "status": "set" if effect_ids else "nothing",
            "mode": result.get("mode"), "effectIds": effect_ids,
        }

    def _rules_result_double_target_base_power(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "card"
        ), None)
        item = self.find_battlefield_item((target or {}).get("itemId"))
        if item is None:
            return {"kind": result.get("kind"), "status": "target_missing"}
        base = self.rules_manifestation_base_power(item)
        self.create_rules_ongoing_effects({
            **action, "targets": [target],
            "ability": {"id": (action.get("ability") or {}).get("id"), "ongoingEffect": {
                "kind": "base_power_double", "duration": "while_target_on_field",
            }},
        })
        return {
            "kind": result.get("kind"), "status": "doubled",
            "itemId": item["id"], "value": base,
        }

    def _rules_result_exile_limbo_targets_add_power(self, action, result, player_id, player):
        source_item = self.find_battlefield_item(
            (action.get("source") or {}).get("itemId")
        )
        if (not action.get("targets") and not action.get("_limboChosen")
                and not (action.get("ability") or {}).get("targets")):
            # Carcass Devourer: ask which Manifestations to exile from Limbo
            limbo = [
                card_id for card_id in player["zones"]["graveyard"]
                if self.card_rules.get(card_id, {}).get("type") == "manifestation"
            ]
            if not limbo:
                return {"kind": result.get("kind"), "status": "nothing", "cardIds": [], "power": 0}
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "discard_from_hand",
                "playerId": player_id, "count": 2, "upTo": True,
                "candidateCardIds": limbo, "destination": "limbo_exile_add_power",
                "actionId": action.get("id"),
                "controllerId": action.get("controllerId"),
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "_source": dict(action.get("source") or {}),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "discard_from_hand", "playerId": player_id,
                "count": 2, "upTo": True, "search": True,
            }
        exiled, added = [], 0
        for target in action.get("targets") or []:
            if target.get("kind") != "zone_card" or target.get("zone") != "graveyard":
                continue
            container_id = target.get("containerId")
            card_id = target.get("cardId")
            owner_id = self.card_owner_in_zone(container_id, "graveyard", card_id)
            if owner_id is None:
                continue
            error, _owner, _replacement = self.move_zone_card_by_effect(
                container_id, "graveyard", owner_id, "exile", card_id, "top"
            )
            if error or _replacement:
                continue
            exiled.append(card_id)
            added += int(self.card_rules.get(card_id, {}).get("power") or 0)
        if exiled and source_item is not None:
            self.adjust_rules_power_counter(source_item, added)
        return {
            "kind": result.get("kind"), "status": "exiled" if exiled else "nothing",
            "cardIds": exiled, "power": added,
        }

    def _rules_result_deck_discard_then_weaken(self, action, result, player_id, player):
        player_target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "player"
        ), None)
        card_target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "card"
        ), None)
        discarded_player = (player_target or {}).get("playerId")
        if discarded_player not in self.players:
            return {"kind": result.get("kind"), "status": "target_missing"}
        deck = self.players[discarded_player]["zones"]["deck"]
        discarded = []
        for _index in range(min(int(result.get("count") or 3), len(deck))):
            top_card = deck[0]
            error, _owner, replacement = self.move_zone_card_by_effect(
                discarded_player, "deck", discarded_player, "graveyard",
                top_card, "top",
            )
            if error:
                break
            if not replacement:
                discarded.append(top_card)
        manifestations = sum(
            1 for card_id in discarded
            if self.card_rules.get(card_id, {}).get("type") == "manifestation"
        )
        effects = []
        if manifestations and card_target is not None:
            effects = self.create_rules_ongoing_effects({
                **action,
                "targets": [card_target],
                "ability": {
                    "id": f'{(action.get("ability") or {}).get("id")}:weaken',
                    "ongoingEffect": {
                        "kind": "power_modifier", "value": -manifestations,
                        "duration": "while_target_on_field",
                    },
                },
            })
        return {
            "kind": result.get("kind"), "status": "done",
            # the targeted player is the one whose deck was discarded
            "playerId": discarded_player,
            "count": len(discarded), "cardIds": list(discarded),
            "discarded": discarded, "manifestations": manifestations,
            "effects": len(effects),
        }

    def _rules_result_cleanse_target(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "card"
        ), None)
        item = self.find_battlefield_item(
            (target or {}).get("itemId")
        )
        if item is None:
            return {
                "kind": result.get("kind"),
                "status": "target_missing",
            }
        item_id = item.get("id")
        powers_before = self.rules_field_power_snapshot()
        removed_effects = [
            effect for effect in self.rules_engine.get(
                "ongoingEffects"
            ) or []
            if (
                (effect.get("target", {}).get("itemId") == item_id
                 and effect.get("kind") not in {"copy_power_temperament", "copy_power_effects"})
                or (
                    effect.get("source", {}).get("itemId") == item_id
                    and effect.get("kind") in {
                        "copy_power_temperament",
                        "copy_power_effects",
                    }
                )
            )
        ]
        self.rules_engine["ongoingEffects"] = [
            effect for effect in self.rules_engine.get(
                "ongoingEffects"
            ) or []
            if effect not in removed_effects
        ]
        item["controllerId"] = item.get("ownerId")
        # These two legacy counter slots hold stat modifiers, not resources
        # such as Gem, Quiet or Shackle counters.
        for key in ("power", "tempCounter"):
            (item.get("counters") or {}).pop(key, None)
        for key in {
            "effectsDisabled", "zeroPowerSustained",
            "temperamentOverride", "supportUntilTurn", "hasFloat",
            "baseDoublings", "gummoCopy", "minimumPower", "maximumPower",
        }:
            item.pop(key, None)
        if item.get("willManifestation"):
            self.revert_rules_will_manifestation(item)
        metadata = self.rules_item_card_rules(item)
        if metadata.get("supportWinDestination"):
            item["supportWinDestination"] = metadata[
                "supportWinDestination"
            ]
        else:
            item.pop("supportWinDestination", None)
        if metadata.get("supportWinEffect"):
            item["supportWinEffect"] = dict(
                metadata["supportWinEffect"]
            )
        else:
            item.pop("supportWinEffect", None)
        self.prune_rules_ongoing_effects()
        self.record_rules_power_changes(powers_before)
        return {
            "kind": result.get("kind"),
            "status": "cleansed",
            "itemId": item_id,
            "cardId": item.get("cardId"),
            "removedEffectIds": [
                effect.get("id") for effect in removed_effects
            ],
            "counters": dict(item.get("counters") or {}),
            "fieldZone": self.rules_field_zone(item),
        }

    def _rules_result_add_counter_source(self, action, result, player_id, player):
        source_item = self.find_battlefield_item(
            (action.get("source") or {}).get("itemId")
        )
        if source_item is None:
            return {
                "kind": "add_counter_source",
                "status": "source_missing",
            }
        counter_name = str(result.get("counter") or "")
        power_before = self.rules_manifestation_characteristics(source_item)["power"]
        counters = source_item.setdefault("counters", {})
        counter_key = next((
            key for key in counters
            if str(key).casefold() == counter_name.casefold()
        ), counter_name)
        counters[counter_key] = max(0, int(counters.get(counter_key) or 0) + int(
            result.get("value") or 0
        ))
        self.record_rules_power_change(source_item, power_before)
        if (
            result.get("onZeroTemperament") in RULES_TEMPERAMENTS
            and counters[counter_key] == 0 and int(result.get("value") or 0) < 0
        ):
            self.set_rules_item_temperament(source_item, result["onZeroTemperament"], action)
        return {
            "kind": "add_counter_source",
            "status": "added",
            "itemId": source_item.get("id"),
            "cardId": source_item.get("cardId"),
            "counter": counter_name,
            "value": counters[counter_key],
        }

    def _rules_result_return_supports_and_boost_firsts(self, action, result, player_id, player):
        groups = []
        for controller_id in self.players:
            item_ids = [
                item.get("id") for item in self.battlefield
                if item.get("isSupport")
                and self.rules_item_controller_id(item) == controller_id
            ]
            if item_ids:
                groups.append({
                    "controllerId": controller_id,
                    "itemIds": item_ids,
                })
        continuation = self._continue_rules_support_return_groups(
            groups, {}, action
        )
        if continuation.get("kind") == "support_return_order":
            return {
                "kind": "choice_required",
                "choiceId": continuation["id"],
                "choiceKind": "support_return_order",
                "playerId": continuation["playerId"],
            }
        return {
            "kind": result.get("kind"),
            "status": "resolved",
            **continuation,
        }

    def _rules_result_distribute_power(self, action, result, player_id, player):
        items = []
        for entry in action.get("targets") or []:
            if (
                entry.get("kind") == "card"
                and self.find_battlefield_item(entry.get("itemId")) is not None
                and all(entry.get("itemId") != other[0] for other in items)
            ):
                items.append((entry.get("itemId"), entry))
        if not items:
            return {"kind": result.get("kind"), "status": "target_missing"}
        total = int(result.get("total") or 0)
        count = len(items)
        base, extra = divmod(total, count)
        if base == 0:
            items = items[:total]
            base, extra = 1, 0
        if extra == 1 and count > 1:
            choice = {
                "id": new_id(), "kind": "pick_distribution_extra",
                "playerId": player_id,
                "candidateItemIds": [item_id for item_id, _entry in items],
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "total": total, "sign": int(result.get("sign") or 1),
                "_action": action, "_base": base,
            }
            self.rules_engine["pendingChoice"] = choice
            return {
                "kind": "choice_required", "choiceId": choice["id"],
                "choiceKind": "pick_distribution_extra",
                "playerId": player_id,
            }
        shares = {
            item_id: base + (1 if index < extra else 0)
            for index, (item_id, _entry) in enumerate(items)
        }
        return self.rules_apply_power_distribution(
            action, shares, int(result.get("sign") or 1)
        )

    def _rules_result_move_counter(self, action, result, player_id, player):
        card_targets = [
            target for target in action.get("targets") or []
            if target.get("kind") == "card"
        ]
        if len(card_targets) != 2:
            return {
                "kind": "move_counter",
                "status": "target_missing",
            }
        source_item = self.find_battlefield_item(
            card_targets[0].get("itemId")
        )
        target_item = self.find_battlefield_item(
            card_targets[1].get("itemId")
        )
        counter_name = str(result.get("counter") or "")
        amount = int(result.get("value") or 0)
        if source_item is None or target_item is None:
            return {
                "kind": "move_counter",
                "status": "target_missing",
                "counter": counter_name,
            }
        source_counters = source_item.setdefault("counters", {})
        source_key = next((
            key for key in source_counters
            if str(key).casefold() == counter_name.casefold()
        ), counter_name)
        if int(source_counters.get(source_key) or 0) < amount:
            return {
                "kind": "move_counter",
                "status": "counter_missing",
                "counter": counter_name,
            }
        powers_before = self.rules_field_power_snapshot()
        source_counters[source_key] = int(
            source_counters.get(source_key) or 0
        ) - amount
        if source_counters[source_key] <= 0:
            source_counters.pop(source_key, None)
        target_counters = target_item.setdefault("counters", {})
        target_key = next((
            key for key in target_counters
            if str(key).casefold() == counter_name.casefold()
        ), counter_name)
        target_counters[target_key] = int(
            target_counters.get(target_key) or 0
        ) + amount
        self.record_rules_power_changes(powers_before)
        return {
            "kind": "move_counter",
            "status": "moved",
            "counter": counter_name,
            "value": amount,
            "fromItemId": source_item.get("id"),
            "toItemId": target_item.get("id"),
            "fromValue": int(source_counters.get(source_key) or 0),
            "toValue": target_counters[target_key],
        }

    def _rules_result_adjust_target_power(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "card"
        ), None)
        target_item = self.find_battlefield_item(
            target.get("itemId")
        ) if target else None
        if target_item is None:
            return {
                "kind": "adjust_target_power",
                "status": "target_missing",
            }
        value = int(result.get("value") or 0)
        self.adjust_rules_power_counter(target_item, value)
        return {
            "kind": "adjust_target_power",
            "status": "adjusted",
            "itemId": target_item.get("id"),
            "cardId": target_item.get("cardId"),
            "value": value,
            "power": self.rules_manifestation_characteristics(
                target_item
            )["power"],
        }

    def _rules_result_choose_source_temperament(self, action, result, player_id, player):
        source = action.get("source") or {}
        item = self.find_battlefield_item(source.get("itemId"))
        if item is None:
            return {"kind": result.get("kind"), "status": "source_missing"}
        if result.get("addCounters"):
            self._rules_result_add_counter_source(action, result["addCounters"], player_id, player)
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "temperament_choice", "playerId": player_id,
            "options": sorted(
                RULES_TEMPERAMENTS - ({"hollow", "transcendent"} if result.get("baseOnly") else set())
            ),
            "sourceCardId": source.get("cardId"), "sourceItemId": item.get("id"),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "temperament_choice", "playerId": player_id,
        }

    def _rules_result_declare_name_top_card_power(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "player"
        ), None)
        target_id = (target or {}).get("playerId") or player_id
        if target_id not in self.players:
            return {"kind": result.get("kind"), "status": "target_missing"}
        declared = (action.get("cost") or {}).get("declaredCardId")
        if result.get("kind") == "declare_name_search_deck" and declared in self.card_labels:
            return self.rules_resolve_declared_deck_search(
                player_id, target_id, declared, (action.get("source") or {}).get("cardId")
            )
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "declare_card_name", "playerId": player_id,
            "mode": (
                "top_card_power"
                if result.get("kind") == "declare_name_top_card_power"
                else "search_deck"
            ),
            "targetPlayerId": target_id,
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "sourceItemId": (action.get("source") or {}).get("itemId"),
            "actionId": action.get("id"),
            "value": int(result.get("value") or 0),
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "declare_card_name", "playerId": player_id,
        }
