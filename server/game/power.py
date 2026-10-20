"""Continuous power, characteristics, immunity and protection."""

from .common import RULES_TEMPERAMENTS


class PowerMixin:
    def rules_continuous_power_modifier(self, item):
        """Resolve printed, public power rules without creating Stack objects."""
        if item not in self.battlefield or not item.get("faceUp"):
            return 0
        modifier = 0
        confrontation_items = None
        stalemate_items = None
        for source in self.battlefield:
            if not self.rules_item_effects_active(source):
                continue
            rules = self.rules_item_card_rules(source).get(
                "continuousPowerRules"
            ) or []
            for rule in rules:
                kind = rule.get("kind")
                value = int(rule.get("value") or 0)
                if kind == "self_min_confrontation_count" and source is item:
                    if confrontation_items is None:
                        confrontation_items = self.rules_confrontation_items()
                    if len(confrontation_items) >= int(rule.get("minimum") or 0):
                        modifier += value
                elif kind == "self_in_confrontation_with_five_limbo_wills":
                    if (
                        source is item
                        and self.rules_field_zone(item) == "confrontation"
                        and self.rules_support_condition_met(item, "five_wills_in_limbo")
                    ):
                        modifier += value
                elif kind == "friendly_support_flat":
                    if self.rules_item_controller_id(item) == self.rules_item_controller_id(source) and item.get("isSupport"):
                        modifier += value
                elif kind == "friendly_support_per_other_non_token_confrontation":
                    if (
                        self.rules_item_controller_id(item) == self.rules_item_controller_id(source)
                        and item.get("isSupport")
                        and not item.get("isTokenCard")
                        and not item.get("isCopy")
                    ):
                        if confrontation_items is None:
                            confrontation_items = self.rules_confrontation_items()
                        others = sum(
                            1 for candidate in confrontation_items
                            if candidate is not item
                            and self.rules_item_controller_id(candidate) == self.rules_item_controller_id(source)
                            and not candidate.get("isTokenCard")
                            and not candidate.get("isCopy")
                        )
                        modifier += value * others
                elif kind == "self_only_friendly_support" and source is item and item.get("isSupport"):
                    support_count = sum(
                        1 for candidate in self.battlefield
                        if candidate.get("faceUp")
                        and self.rules_item_controller_id(candidate) == self.rules_item_controller_id(item)
                        and candidate.get("isSupport")
                    )
                    if support_count == 1:
                        modifier += value
                elif kind == "self_any_stalemate" and source is item:
                    if stalemate_items is None:
                        stalemate_items = self.rules_confrontation_items(zones=("stalemate",))
                    if stalemate_items:
                        modifier += value
                elif kind == "friendly_confrontation_flat":
                    if (
                        self.rules_item_controller_id(item)
                        == self.rules_item_controller_id(source)
                        and self.rules_field_zone(item) == "confrontation"
                    ):
                        modifier += value
                elif (
                    kind == "self_per_controller_hand_card"
                    and source is item
                    and self.rules_field_zone(item) == "confrontation"
                ):
                    controller_id = self.rules_item_controller_id(item)
                    modifier += value * len(
                        self.players.get(controller_id, {})
                        .get("zones", {}).get("hand", [])
                    )
                elif (
                    kind == "self_per_stalemate_manifestation"
                    and source is item
                    and self.rules_field_zone(item) == "confrontation"
                ):
                    if stalemate_items is None:
                        stalemate_items = self.rules_confrontation_items(
                            zones=("stalemate",)
                        )
                    modifier += value * sum(
                        1 for candidate in stalemate_items
                        if self.rules_item_card_rules(candidate).get("type")
                        == "manifestation"
                    )
                elif (
                    kind == "self_per_controller_limbo_manifestation"
                    and source is item
                    and self.rules_field_zone(item) == "confrontation"
                ):
                    controller_id = self.rules_item_controller_id(item)
                    modifier += value * sum(
                        1 for card_id in self.players.get(
                            controller_id, {}
                        ).get("zones", {}).get("graveyard", [])
                        if self.card_rules.get(card_id, {}).get("type")
                        == "manifestation"
                    )
                elif (
                    kind == "self_per_controller_limbo_card"
                    and source is item
                    and self.rules_field_zone(item) == "confrontation"
                ):
                    controller_id = self.rules_item_controller_id(item)
                    limbo_count = len(
                        self.players.get(controller_id, {})
                        .get("zones", {}).get("graveyard", [])
                    )
                    modifier += max(
                        int(rule.get("floor") or -999), value * limbo_count
                    )
                elif (
                    kind == "self_per_opponent_confrontation_manifestation"
                    and source is item
                    and self.rules_field_zone(item) == "confrontation"
                ):
                    controller_id = self.rules_item_controller_id(item)
                    opponent_counts = {}
                    for candidate in self.rules_confrontation_items():
                        candidate_controller = self.rules_item_controller_id(candidate)
                        if candidate_controller != controller_id:
                            opponent_counts[candidate_controller] = (
                                opponent_counts.get(candidate_controller, 0) + 1
                            )
                    modifier += value * max(opponent_counts.values(), default=0)
                elif (
                    kind == "self_per_opponent_confrontation_total"
                    and source is item
                    and self.rules_field_zone(item) == "confrontation"
                ):
                    controller_id = self.rules_item_controller_id(item)
                    opponent_total = sum(
                        1 for candidate in self.rules_confrontation_items()
                        if self.rules_item_controller_id(candidate) != controller_id
                    )
                    modifier += min(
                        int(rule.get("cap") or 999), value * opponent_total
                    )
                elif (
                    kind == "self_per_owned_vessel_manifestation"
                    and source is item
                    and self.rules_field_zone(item) == "confrontation"
                ):
                    controller_id = self.rules_item_controller_id(item)
                    owned = 0
                    for container_id, container in self.players.items():
                        for card_id in container["zones"].get("receptacle", []):
                            if (
                                self.card_owner_in_zone(
                                    container_id, "receptacle", card_id
                                ) == controller_id
                                and self.card_rules.get(card_id, {}).get("type")
                                == "manifestation"
                            ):
                                owned += 1
                    modifier += value * owned
                elif (
                    kind == "first_manifestation_per_interzone_manifestation"
                    and self.rules_field_zone(source) == "interzone"
                ):
                    controller_id = self.rules_item_controller_id(source)
                    first_item_id = (
                        self.rules_engine.get("firstManifestationItemIds") or {}
                    ).get(controller_id)
                    if item.get("id") == first_item_id and first_item_id:
                        modifier += value * len(
                            self.rules_confrontation_items(
                                controller_id, ("interzone",)
                            )
                        )
                elif (
                    kind == "only_friendly_confrontation_manifestation"
                    and self.rules_field_zone(source) == "interzone"
                    and self.rules_field_zone(item) == "confrontation"
                    and self.rules_item_controller_id(item)
                    == self.rules_item_controller_id(source)
                ):
                    controller_id = self.rules_item_controller_id(source)
                    friendly = self.rules_confrontation_items(controller_id)
                    if len(friendly) == 1 and friendly[0] is item:
                        modifier += value
            for passive in self.rules_item_card_rules(
                source
            ).get("passiveEffects") or []:
                if (
                    passive.get("kind") == "friendly_float_power_bonus"
                    and self.rules_item_controller_id(item)
                    == self.rules_item_controller_id(source)
                    and self.rules_item_has_float(item)
                ):
                    modifier += int(passive.get("value") or 0)
                elif (
                    passive.get("kind") == "interzone_allies_penalty"
                    and source is not item
                    and self.rules_field_zone(source) == "interzone"
                    and self.rules_field_zone(item) == "interzone"
                    and self.rules_item_controller_id(item)
                    == self.rules_item_controller_id(source)
                ):
                    modifier += int(passive.get("value") or 0)
        return modifier

    def rules_manifestation_characteristics(self, item, visiting=None):
        """Return current Power and Temperament without confrontation-only suppression."""
        if item is None:
            return {"power": 0, "temperament": None}
        visiting = set(visiting or ())
        if item.get("id") in visiting:
            return {"power": 0, "temperament": None}
        visiting.add(item.get("id"))
        metadata = self.card_rules.get(item.get("cardId"), {})
        power = item.get("power") if item.get("isTokenCard") else metadata.get("power")
        if item.get("willManifestation"):
            power = item["willManifestation"].get("power")
        if item.get("gummoCopy"):
            power = self.card_rules.get(item["gummoCopy"], {}).get("power")
        power = int(power or 0) * (2 ** int(item.get("baseDoublings") or 0))
        base_power = power
        temperaments = (
            [item.get("temperament")]
            if item.get("isTokenCard")
            else list(metadata.get("temperaments") or [])
        )
        temperament = item.get("temperamentOverride") or (temperaments[0] if temperaments else None)

        copy_effect = next((
            effect for effect in reversed(self.rules_engine.get("ongoingEffects") or [])
            if effect.get("kind") in {
                "copy_power_temperament", "copy_power_effects"
            }
            and effect.get("source", {}).get("itemId") == item.get("id")
        ), None)
        if copy_effect:
            copied_item = self.find_battlefield_item(copy_effect.get("target", {}).get("itemId"))
            if copied_item is not None:
                copied = self.rules_manifestation_characteristics(copied_item, visiting)
                # Mimer keeps the copied values once its target has left the field
                copy_effect["snapshot"] = {
                    "power": copied["power"], "temperament": copied["temperament"],
                    "basePower": self.rules_manifestation_base_power(copied_item, visiting),
                }
            else:
                copied = copy_effect.get("snapshot") or {"power": 0, "temperament": None}
            power = copied["power"]
            if copy_effect.get("kind") == "copy_power_temperament":
                temperament = copied["temperament"]
        override_effect = next((
            effect for effect in reversed(self.rules_engine.get("ongoingEffects") or [])
            if effect.get("kind") == "temperament_override"
            and effect.get("target", {}).get("itemId") == item.get("id")
        ), None)
        if override_effect and override_effect.get("temperament") in RULES_TEMPERAMENTS:
            temperament = override_effect["temperament"]

        power += int((item.get("counters") or {}).get("power") or 0)
        power += int((item.get("counters") or {}).get("tempCounter") or 0)
        power += sum(
            int(effect.get("value") or 0)
            for effect in self.rules_engine.get("ongoingEffects") or []
            if effect.get("kind") == "power_modifier"
            and effect.get("target", {}).get("itemId") == item.get("id")
        )
        power += self.rules_continuous_power_modifier(item)
        set_effect = next((
            effect for effect in reversed(
                self.rules_engine.get("ongoingEffects") or []
            )
            if effect.get("kind") == "power_set_maximum"
            and effect.get("target", {}).get("itemId") == item.get("id")
        ), None)
        if set_effect:
            power = int(set_effect.get("value") or 0)
        if (
            self.rules_field_zone(item) != "stalemate"
            and any(
                source is not item
                for source in self.rules_active_passive_sources(
                    "other_power_minimum_base"
                )
            )
        ):
            power = max(power, base_power)
        minimum_power = item.get("minimumPower")
        maximum_power = item.get("maximumPower")
        for effect in self.rules_engine.get("ongoingEffects") or []:
            if effect.get("target", {}).get("itemId") != item.get("id"):
                continue
            if effect.get("kind") == "power_minimum":
                minimum_power = max(
                    int(minimum_power) if isinstance(minimum_power, (int, float)) else -999,
                    int(effect.get("value") or 0),
                )
            elif effect.get("kind") == "power_maximum":
                maximum_power = min(
                    int(maximum_power) if isinstance(maximum_power, (int, float)) else 999,
                    int(effect.get("value") or 0),
                )
            elif effect.get("kind") == "power_set_maximum":
                maximum_power = min(
                    int(maximum_power) if isinstance(maximum_power, (int, float)) else 999,
                    int(effect.get("value") or 0),
                )
        if isinstance(minimum_power, (int, float)):
            power = max(power, int(minimum_power))
        if isinstance(maximum_power, (int, float)):
            power = min(power, int(maximum_power))
        return {"power": power, "temperament": temperament}

    def rules_manifestation_base_power(self, item, visiting=None):
        if item is None:
            return 0
        visiting = set(visiting or ())
        item_id = item.get("id")
        if item_id in visiting:
            return 0
        visiting.add(item_id)
        copy_effect = next((
            effect for effect in reversed(
                self.rules_engine.get("ongoingEffects") or []
            )
            if effect.get("kind") in {
                "copy_power_temperament", "copy_power_effects"
            }
            and effect.get("source", {}).get("itemId") == item_id
        ), None)
        if copy_effect:
            copied_item = self.find_battlefield_item(
                copy_effect.get("target", {}).get("itemId")
            )
            if copied_item is not None:
                return self.rules_manifestation_base_power(
                    copied_item, visiting
                )
            if (copy_effect.get("snapshot") or {}).get("basePower") is not None:
                return int(copy_effect["snapshot"]["basePower"])
        # Entrust doubles the base power itself: a modifier kept while the card stays on the field
        doubling = 2 ** int(item.get("baseDoublings") or 0)
        if item.get("isTokenCard"):
            return int(item.get("power") or 0) * doubling
        if item.get("gummoCopy"):
            return int(self.card_rules.get(item["gummoCopy"], {}).get("power") or 0) * doubling
        return int(
            self.card_rules.get(item.get("cardId"), {}).get("power") or 0
        ) * doubling

    def rules_stalemate_win_blocked(self, item):
        return (
            self.rules_field_zone(item) == "stalemate"
            and self.rules_item_effects_active(item)
            and any(
                passive.get("kind") == "stalemate_win_blocked"
                for passive in self.rules_item_card_rules(item).get("passiveEffects") or []
            )
        )

    def rules_spite_ignore_threshold(self):
        best = 0
        for host in self.battlefield:
            if (
                self.rules_field_zone(host) != "stalemate"
                or not self.rules_item_effects_active(host)
                or not any(
                    passive.get("kind") == "stalemate_ignores_low_power"
                    for passive in self.rules_item_card_rules(host).get("passiveEffects") or []
                )
            ):
                continue
            spite = sum(
                int(value or 0) for key, value in (host.get("counters") or {}).items()
                if str(key).casefold() == "spite"
            )
            best = max(best, spite)
        return best

    def rules_confrontation_power(self, item):
        threshold = self.rules_spite_ignore_threshold()
        if threshold > 0 and max(
            0, self.rules_manifestation_characteristics(item)["power"]
        ) <= threshold:
            return 0
        ignored = any(
            effect.get("kind") in {"power_ignored", "obscure_lock"}
            and effect.get("target", {}).get("itemId") == item.get("id")
            for effect in self.rules_engine.get("ongoingEffects") or []
        )
        if ignored:
            return 0
        return max(0, self.rules_manifestation_characteristics(item)["power"])

    def rules_item_is_immune(self, item, controller_id=None):
        for effect in self.rules_engine.get("ongoingEffects") or []:
            if (
                effect.get("kind") in {"immune", "obscure_lock"}
                and effect.get("target", {}).get("itemId") == (item or {}).get("id")
                and (
                    not effect.get("fromOpponents")
                    or controller_id != self.rules_item_controller_id(item)
                )
            ):
                return True
        if controller_id is not None and any(
            passive.get("kind") == "mutual_opponent_immunity"
            for source in self.rules_active_passive_sources(
                "mutual_opponent_immunity"
            )
            for passive in self.rules_item_card_rules(
                source
            ).get("passiveEffects") or []
        ):
            return controller_id != self.rules_item_controller_id(item)
        return False

    def rules_item_is_protected(self, item, controller_id):
        item_controller = self.rules_item_controller_id(item)
        for effect in self.rules_engine.get("ongoingEffects") or []:
            if (
                effect.get("kind") == "protection"
                and effect.get("target", {}).get("itemId") == (item or {}).get("id")
                and (
                    not effect.get("fromOpponents")
                    or controller_id != item_controller
                )
            ):
                return True
        for source in self.rules_active_passive_sources(
            "protect_other_friendly_confrontation"
        ):
            if (
                source is not item
                and self.rules_item_controller_id(source) == item_controller
                and self.rules_field_zone(item) == "confrontation"
                and controller_id != item_controller
            ):
                return True
        for source in self.rules_active_passive_sources(
            "protect_friendly_interzone_and_wills"
        ):
            if self.rules_item_controller_id(source) != item_controller:
                continue
            metadata = self.card_rules.get(item.get("cardId"), {})
            if (
                controller_id != item_controller
                and (
                    metadata.get("type") == "persistent_will"
                    or (
                        source is not item
                        and metadata.get("type") == "manifestation"
                        and self.rules_field_zone(item) == "interzone"
                    )
                )
            ):
                return True
        return False

    def rules_confrontation_items(self, player_id=None, zones=("confrontation",)):
        items = []
        for item in self.battlefield:
            if not item.get("faceUp"):
                continue
            if self.rules_item_card_rules(item).get("type") != "manifestation" and not item.get("isTokenCard"):
                continue
            if player_id is not None and self.rules_item_controller_id(item) != player_id:
                continue
            if self.rules_field_zone(item) not in zones:
                continue
            items.append(item)
        return items

    def rules_confrontation_items_owned_by(self, owner_id,
                                           zones=("confrontation",)):
        return [
            item for item in self.rules_confrontation_items(zones=zones)
            if item.get("ownerId") == owner_id
        ]
