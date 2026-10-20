"""Tribute, Essence and activation costs."""

import math
import re

from .common import TRIBUTE_SYMBOL_TEMPERAMENT, RULES_WILL_TYPES, new_id


class PaymentMixin:
    @staticmethod
    def rules_requirements_from_symbols(power_cost):
        requirements = {}
        symbols = re.findall(r"\{([A-Z])\}", str(power_cost or ""))
        for symbol in symbols:
            temperament = TRIBUTE_SYMBOL_TEMPERAMENT.get(symbol)
            if temperament:
                requirements[temperament] = requirements.get(temperament, 0) + 1
        return requirements

    def rules_redirect_targets(self, controller_id, targets):
        """Obtrusive Mass: opponents' cards and effects target it instead."""
        redirected = []
        changed = False
        for target in targets or []:
            item = (
                self.find_battlefield_item(target.get("itemId"))
                if target.get("kind") == "card" else None
            )
            mass = None
            if item is not None and self.rules_item_controller_id(item) != controller_id:
                owner_id = self.rules_item_controller_id(item)
                outcast = next((
                    source for source in self.rules_active_passive_sources(
                        "swap_with_targeted_confrontation_manifestation"
                    )
                    if self.rules_item_controller_id(source) == owner_id
                    and self.rules_field_zone(source) == "interzone"
                    and not source.get("outcastOff")
                    and self.rules_field_zone(item) == "confrontation"
                    and not item.get("isSupport")
                    and self.card_rules.get(item.get("cardId"), {}).get("type") == "manifestation"
                    and not self.rules_item_is_immune(source, controller_id)
                    and not self.rules_item_is_protected(source, controller_id)
                ), None)
                if outcast is not None:
                    # Swap positions, then the effect targets Wandering Outcast.
                    for key in ("fieldZone", "x", "y", "stackedOn", "stackOffsetX", "stackOffsetY",
                                "confrontationOrder", "isSupport"):
                        a, b = item.get(key), outcast.get(key)
                        for holder, value in ((item, b), (outcast, a)):
                            if value is None:
                                holder.pop(key, None)
                            else:
                                holder[key] = value
                    for other in self.battlefield:
                        if other.get("stackedOn") == item["id"]:
                            other["stackedOn"] = outcast["id"]
                        elif other.get("stackedOn") == outcast["id"]:
                            other["stackedOn"] = item["id"]
                    changed = True
                    redirected.append({
                        "kind": "card", "itemId": outcast["id"], "cardId": outcast.get("cardId"),
                        "ownerId": outcast.get("ownerId"),
                    })
                    continue
                mass = next((
                    source for source in self.rules_active_passive_sources(
                        "redirect_opponent_targeting_to_source"
                    )
                    if self.rules_item_controller_id(source) == owner_id
                    and source is not item
                    and self.card_rules.get(source.get("cardId"), {}).get("type") == "manifestation"
                    and not self.rules_item_is_immune(source, controller_id)
                    and not self.rules_item_is_protected(source, controller_id)
                ), None)
            if mass is not None:
                changed = True
                redirected.append({
                    "kind": "card", "itemId": mass["id"], "cardId": mass.get("cardId"),
                    "ownerId": mass.get("ownerId"),
                })
            else:
                redirected.append(target)
        if not changed:
            return targets
        unique = []
        for target in redirected:
            if not any(
                target.get("kind") == "card" and other.get("kind") == "card"
                and other.get("itemId") == target.get("itemId")
                for other in unique
            ):
                unique.append(target)
        return unique

    def rules_tribute_extra_power_loss(self, action):
        source = action.get("source") or {}
        if (
            action.get("kind") != "play_card"
            or self.card_rules.get(source.get("cardId"), {}).get("type")
            != "ephemeral_will"
        ):
            return 0
        return sum(
            int(self.card_rules.get(card_id, {}).get("tributeExtraPowerLoss") or 0)
            for card_id in (action.get("cost") or {}).get("tributeCardIds") or []
        )

    def rules_tribute_requirements(self, kind, source, ability=None,
                                   player_id=None):
        if ability and ability.get("tribute") is not None:
            return self.rules_requirements_from_symbols(ability.get("tribute")), True
        if kind != "play_card" or not source:
            return {}, False
        if source.get("noTribute"):
            return {}, True
        if source.get("fixedTribute"):
            return dict(source["fixedTribute"]), True
        metadata = self.card_rules.get(source.get("cardId"), {})
        if (source.get("cardType") or metadata.get("type")) not in RULES_WILL_TYPES:
            return {}, True
        requirements = self.rules_requirements_from_symbols(metadata.get("powerCost"))
        if source.get("anyTemperamentTribute"):
            total = sum(requirements.values()) or int(metadata.get("cost") or 0)
            requirements = {"hollow": total} if total > 0 else {}
        if not requirements and int(metadata.get("cost") or 0) > 0:
            temperaments = list(metadata.get("temperaments") or [])
            if len(temperaments) == 1:
                requirements[temperaments[0]] = int(metadata["cost"])
        player_id = player_id or source.get("controllerId")
        reduction = 0
        if player_id in self.players:
            reduction += sum(
                int(passive.get("value") or 0)
                for field_source in self.rules_active_passive_sources(
                    "reduce_will_tribute"
                )
                if self.rules_item_controller_id(field_source) == player_id
                and self.rules_field_zone(field_source) == "interzone"
                for passive in self.card_rules.get(
                    field_source.get("cardId"), {}
                ).get("passiveEffects") or []
                if passive.get("kind") == "reduce_will_tribute"
            )
        cost_reduction = (ability or {}).get("costReduction") or {}
        if (
            cost_reduction.get("kind") == "half_first_base_power"
            and player_id in self.players
        ):
            first_item = self.find_battlefield_item(
                self.rules_engine.get("firstManifestationItemIds", {}).get(
                    player_id
                )
            )
            base_power = self.rules_manifestation_base_power(first_item)
            reduction += base_power // 2
        increase = sum(
            int(passive.get("value") or 0)
            for field_source in self.rules_active_passive_sources(
                "increase_will_tribute"
            )
            for passive in self.card_rules.get(
                field_source.get("cardId"), {}
            ).get("passiveEffects") or []
            if passive.get("kind") == "increase_will_tribute"
        )
        for _index in range(max(0, reduction)):
            payable = max(
                requirements,
                key=lambda temperament: requirements[temperament],
                default=None,
            )
            if payable is None or requirements[payable] <= 0:
                break
            requirements[payable] -= 1
        increase += int(source.get("extraTribute") or 0)
        if increase > 0:
            requirements["hollow"] = requirements.get("hollow", 0) + increase
        requirements = {
            temperament: amount
            for temperament, amount in requirements.items() if amount > 0
        }
        return requirements, True

    def rules_essence_payment_plan(self, player_id, requirements,
                                   already_spent=None):
        remaining = dict(requirements)
        essence_tokens = [
            token for token in self.tokens
            if token.get("ownerId") == player_id
            and token.get("isEssence")
            and not token.get("isNeutralCounter")
            and token.get("temperament")
            and int(token.get("counters", {}).get("essence") or 0) > 0
        ]
        available = {
            token["id"]: int(token.get("counters", {}).get("essence") or 0)
            for token in essence_tokens
        }
        for entry in already_spent or []:
            token_id = entry.get("tokenId")
            if token_id in available:
                available[token_id] -= int(entry.get("amount") or 0)
        spent = []

        def consume(requirement, candidates):
            needed = remaining.get(requirement, 0)
            for token in candidates:
                if needed <= 0:
                    break
                amount = min(needed, available[token["id"]])
                if amount <= 0:
                    continue
                available[token["id"]] -= amount
                needed -= amount
                spent.append({
                    "tokenId": token["id"],
                    "temperament": token["temperament"],
                    "amount": amount,
                    "pays": requirement,
                })
            remaining[requirement] = needed

        # Preserve versatile Essences whenever a more specific Essence is
        # available. Hollow Tributes accept every temperament, but Hollow
        # Essences themselves never pay a non-Hollow requirement.
        for temperament in requirements:
            if temperament == "hollow":
                continue
            consume(temperament, [
                token for token in essence_tokens if token.get("temperament") == temperament
            ])
        if "hollow" in requirements:
            hollow_order = [
                token for token in essence_tokens
                if token.get("temperament") not in {"transcendent"}
            ]
            hollow_order.sort(key=lambda token: token.get("temperament") != "hollow")
            consume("hollow", hollow_order)
        transcendent = [
            token for token in essence_tokens if token.get("temperament") == "transcendent"
        ]
        for temperament in requirements:
            consume(temperament, transcendent)
        return remaining, spent

    def rules_tribute_power_override(self, player_id, metadata):
        override = metadata.get("tributePowerOverride")
        if not override or player_id not in self.players:
            return None
        condition = override.get("condition")
        turn = self.phase_tracker["turn"]
        if condition == "two_wills_played_this_turn":
            played = self.rules_engine.get("willsPlayed") or {}
            if played.get("turn") != turn or int(played.get(player_id) or 0) < 2:
                return None
        elif condition == "lost_or_stalemate_previous_turn":
            if (
                (self.rules_engine.get("confrontationLosses") or {}).get(str(turn - 1)) != player_id
                and not (self.rules_engine.get("confrontationStalemates") or {}).get(str(turn - 1))
            ):
                return None
        elif condition:
            return None
        return int(override.get("power") or 0)

    def rules_tribute_power_overrides_snapshot(self):
        snapshot = {}
        for player_id, player in self.players.items():
            entries = {}
            for card_id in set(player["zones"].get("hand", [])):
                power = self.rules_tribute_power_override(
                    player_id, self.card_rules.get(card_id, {})
                )
                if power is not None:
                    entries[card_id] = power
            if entries:
                snapshot[player_id] = entries
        return snapshot

    def rules_manifestations_cover(self, card_ids, requirements, include_excess=False,
                                   player_id=None):
        remaining = dict(requirements)
        excess = {}
        cards = []
        for entry in card_ids:
            if isinstance(entry, dict):
                card_id = entry.get("cardId")
                metadata = self.card_rules.get(card_id, {})
                power = (
                    int(
                        metadata.get("interzoneTributePower")
                        or metadata.get("power") or 0
                    )
                    if entry.get("zone") == "battlefield"
                    else int(metadata.get("power") or 0)
                )
            else:
                card_id = entry
                metadata = self.card_rules.get(card_id, {})
                power = int(metadata.get("power") or 0)
            override = self.rules_tribute_power_override(player_id, metadata)
            if override is not None:
                power = override
            if isinstance(entry, dict) and entry.get("powerOverride") is not None:
                power = int(entry["powerOverride"])
            if isinstance(entry, dict) and entry.get("zone") == "receptacle":
                metadata = {**metadata, "tributeTemperaments": ["transcendent"]}
            cards.append((card_id, metadata, max(0, power)))
        cards.sort(key=lambda item: "transcendent" in (
            item[1].get("tributeTemperaments")
            or item[1].get("temperaments")
            or []
        ))

        def spend(state, card):
            """Every way this card can pay the remaining requirements."""
            _card_id, metadata, power = card
            printed = next(iter(metadata.get("temperaments") or []), None)
            tribute = list(
                metadata.get("tributeTemperaments")
                or metadata.get("temperaments")
                or []
            )
            if "transcendent" in tribute:
                left = dict(state)
                used = 0
                for required in left:
                    amount = min(power - used, left[required])
                    left[required] -= amount
                    used += amount
                    if used >= power:
                        break
                return [(left, "transcendent", used)]
            options = []
            for candidate in tribute + ["hollow"]:
                if state.get(candidate, 0) > 0:
                    left = dict(state)
                    used = min(power, left[candidate])
                    left[candidate] -= used
                    options.append((
                        left,
                        printed if candidate == "hollow" else candidate,
                        used,
                    ))
            return options or [(dict(state), printed, 0)]

        best = {}

        def search(index, state, spent):
            if index == len(cards):
                missing = sum(max(0, amount) for amount in state.values())
                wasted = sum(power - used for (_c, _m, power), (_t, used) in zip(cards, spent))
                score = (missing, wasted)
                if not best or score < best["score"]:
                    best.update(score=score, state=state, spent=list(spent))
                return
            for left, temperament, used in spend(state, cards[index]):
                search(index + 1, left, spent + [(temperament, used)])
                if best and best["score"] == (0, 0):
                    return

        search(0, remaining, [])
        remaining = best["state"] if best else remaining
        if include_excess and best:
            for (_card_id, metadata, power), (temperament, used) in zip(cards, best["spent"]):
                if power > used and temperament:
                    key = (temperament, "retained") if metadata.get("retainsExcessEssence") else temperament
                    excess[key] = excess.get(key, 0) + power - used
        covered = all(amount <= 0 for amount in remaining.values())
        return covered, excess

    def rules_action_payment(self, player_id, kind, source, payment_card_ids,
                             ability=None, targets=None,
                             extra_essence_count=0, extra_payment_card_ids=None):
        if payment_card_ids is None:
            payment_card_ids = []
        if not isinstance(payment_card_ids, list):
            return "Tribute cards must be supplied as a list.", None
        clean_refs = [str(card_id or "") for card_id in payment_card_ids if str(card_id or "")]
        sacrifice_item_ids = [
            ref.partition("|")[2] for ref in clean_refs if ref.startswith("sacrifice|")
        ]
        clean_refs = [ref for ref in clean_refs if not ref.startswith("sacrifice|")]
        clean_entries = []
        for reference in clean_refs:
            zone, separator, card_id = reference.partition("|")
            if not separator:
                zone, card_id = "hand", reference
            if zone not in {"hand", "graveyard", "battlefield", "receptacle"}:
                return "A selected Tribute card uses an unsupported zone.", None
            if zone == "battlefield":
                item = self.find_battlefield_item(card_id)
                if item is None:
                    return "A selected Interzone Tribute is no longer on the field.", None
                clean_entries.append({
                    "zone": zone,
                    "cardId": item.get("cardId"),
                    "itemId": item.get("id"),
                })
            else:
                clean_entries.append({"zone": zone, "cardId": card_id})
        sacrifice_items = []
        if sacrifice_item_ids:
            kanopo_entries = [
                entry for entry in clean_entries
                if self.card_rules.get(entry["cardId"], {}).get("tributeSacrificePower")
            ]
            if len(set(sacrifice_item_ids)) != len(sacrifice_item_ids) or len(
                sacrifice_item_ids
            ) > len(kanopo_entries):
                return "There is no Tribute effect that needs this sacrifice.", None
            tribute_item_ids = {
                entry.get("itemId") for entry in clean_entries if entry.get("itemId")
            }
            for item_id, entry in zip(sacrifice_item_ids, kanopo_entries):
                item = self.find_battlefield_item(item_id)
                if (
                    item is None
                    or self.rules_item_controller_id(item) != player_id
                    or self.rules_field_zone(item) != "interzone"
                    or self.card_rules.get(item.get("cardId"), {}).get("type") != "manifestation"
                    or item_id in tribute_item_ids
                    or (source or {}).get("itemId") == item_id
                ):
                    return "The sacrificed Manifestation must be in your Interzone.", None
                sacrifice_items.append(item)
                entry["powerOverride"] = int(
                    self.card_rules[entry["cardId"]]["tributeSacrificePower"]
                )
        clean_ids = [entry["cardId"] for entry in clean_entries]
        if len(clean_ids) > 7:
            return "Too many Tribute cards were selected.", None
        hand = self.players[player_id]["zones"]["hand"]
        limbo_source = next((
            candidate for candidate in self.rules_active_passive_sources(
                "allow_limbo_tribute_with_counter"
            )
            if self.rules_item_controller_id(candidate) == player_id
            and int((candidate.get("counters") or {}).get("Formula") or 0) > 0
        ), None)
        requested_counts = {}
        limbo_count = 0
        battlefield_item_ids = [
            entry.get("itemId") for entry in clean_entries
            if entry["zone"] == "battlefield"
        ]
        for entry in clean_entries:
            card_id = entry["cardId"]
            key = (entry["zone"], card_id)
            requested_counts[key] = requested_counts.get(key, 0) + 1
            reserved_source = 1 if source and source.get("zone") == "hand" and source.get("cardId") == card_id else 0
            if entry["zone"] == "hand":
                if requested_counts[key] > hand.count(card_id) - reserved_source:
                    return "A selected Tribute card is no longer in your Hand.", None
            elif entry["zone"] == "receptacle":
                if not any(
                    self.rules_item_controller_id(source) == player_id
                    for source in self.rules_active_passive_sources(
                        "vessel_manifestations_as_tribute"
                    )
                ):
                    return "Your Empathic Vessel cannot currently pay Tribute.", None
                if requested_counts[key] > self.players[player_id]["zones"].get(
                    "receptacle", []
                ).count(card_id):
                    return "A selected Empathic Vessel card cannot currently pay Tribute.", None
            else:
                if entry["zone"] == "battlefield":
                    item = self.find_battlefield_item(entry.get("itemId"))
                    metadata = self.card_rules.get(card_id, {})
                    if (
                        item is None
                        or self.rules_item_controller_id(item) != player_id
                        or item.get("isTokenCard")
                        or (source or {}).get("itemId") == item.get("id")
                        or battlefield_item_ids.count(item.get("id")) > 1
                    ):
                        return "A selected Manifestation cannot pay Tribute from the field.", None
                    in_interzone = self.rules_field_zone(item) == "interzone"
                    if not (
                        (in_interzone and metadata.get("canPayTributeFromInterzone"))
                        or (
                            self.rules_field_zone(item) in {"interzone", "confrontation"}
                            and metadata.get("type") == "manifestation"
                            and metadata.get("canPayTribute", True)
                            and self.rules_active_passive_sources(
                                "field_manifestations_as_tribute"
                            )
                        )
                    ):
                        return "A selected Manifestation cannot pay Tribute from the field.", None
                    continue
                if self.card_rules.get(card_id, {}).get("canPayTributeFromLimbo"):
                    if requested_counts[key] > self.players[player_id]["zones"]["graveyard"].count(card_id):
                        return "A selected Limbo card cannot currently pay Tribute.", None
                else:
                    limbo_count += 1
                    if (
                        limbo_source is None
                        or requested_counts[key]
                        > self.players[player_id]["zones"]["graveyard"].count(card_id)
                    ):
                        return "A selected Limbo card cannot currently pay Tribute.", None
            if self.card_rules.get(card_id, {}).get("type") != "manifestation":
                return "Only Manifestations from your Hand can be declared as Tribute here.", None
            if not self.card_rules.get(card_id, {}).get("canPayTribute", True):
                return "This Manifestation cannot be used to pay Tribute.", None
        if limbo_count > int(
            ((limbo_source or {}).get("counters") or {}).get("Formula") or 0
        ):
            return "There are not enough Formula counters for those Limbo Tributes.", None
        requirements, enforce_printed_cost = self.rules_tribute_requirements(
            kind, source, ability, player_id
        )
        essence_remaining, essence_spent = self.rules_essence_payment_plan(player_id, requirements)
        excess = {}
        if enforce_printed_cost:
            covered, excess = self.rules_manifestations_cover(
                clean_entries, essence_remaining, include_excess=True,
                player_id=player_id,
            )
            if not covered:
                return "The selected Manifestations do not pay the full printed Tribute.", None
            for entry in clean_entries:
                if entry.get("powerOverride") is None:
                    continue
                plain_payment = [
                    {k: v for k, v in other.items() if k != "powerOverride"}
                    if other is entry else other
                    for other in clean_entries
                ]
                if self.rules_manifestations_cover(
                    plain_payment, essence_remaining, player_id=player_id
                )[0]:
                    return "The sacrifice is superfluous to this Tribute.", None
            for index in range(len(clean_ids)):
                reduced_payment = clean_entries[:index] + clean_entries[index + 1:]
                if self.rules_manifestations_cover(
                    reduced_payment, essence_remaining, player_id=player_id
                )[0]:
                    return "A selected Manifestation is superfluous to this Tribute.", None
        essence_cost = str((ability or {}).get("essenceCost") or "")
        if essence_cost:
            essence_requirements = self.rules_requirements_from_symbols(
                essence_cost
            )
            if not essence_requirements:
                return "This ability has an invalid Essence cost.", None
            essence_cost_remaining, essence_cost_spent = (
                self.rules_essence_payment_plan(
                    player_id, essence_requirements, essence_spent
                )
            )
            if any(amount > 0 for amount in essence_cost_remaining.values()):
                return "Not enough compatible Essences are available.", None
            essence_spent.extend(essence_cost_spent)
        extra_essence_needed = 0
        target_count_rule = (ability or {}).get("extraEssenceByTargetCount") or {}
        if (
            len(targets or []) >= int(target_count_rule.get("targetCount") or 999)
        ):
            extra_essence_needed = max(
                extra_essence_needed,
                int(target_count_rule.get("amount") or 0),
            )
        point_rule = (ability or {}).get("extraEssenceForTargetPoints") or {}
        if point_rule:
            target = next((
                entry for entry in targets or []
                if entry.get("kind") in {"card", "zone_card"}
            ), None)
            points = (
                self.card_points.get(target.get("cardId"), 0)
                if target and self.card_points else 0
            )
            multiplier = max(1, int(point_rule.get("multiplier") or 10))
            required_total = math.ceil(points / multiplier)
            max_total = 1 + max(0, int(point_rule.get("maxExtra") or 0))
            if required_total > max_total:
                return "The target requires too many Essences for this effect.", None
            extra_essence_needed = max(
                extra_essence_needed,
                required_total - sum(
                    int(entry.get("amount") or 0) for entry in essence_spent
                ),
            )
        if extra_essence_needed > 0:
            already_spent = {
                entry["tokenId"]: sum(
                    spent.get("amount") or 0
                    for spent in essence_spent
                    if spent["tokenId"] == entry["tokenId"]
                )
                for entry in essence_spent
            }
            for token in self.tokens:
                if extra_essence_needed <= 0:
                    break
                if (
                    token.get("ownerId") != player_id
                    or not token.get("isEssence")
                    or token.get("isNeutralCounter")
                ):
                    continue
                available = int(token.get("counters", {}).get("essence") or 0) - already_spent.get(token["id"], 0)
                amount = min(extra_essence_needed, max(0, available))
                if amount:
                    essence_spent.append({
                        "tokenId": token["id"],
                        "temperament": token.get("temperament"),
                        "amount": amount,
                        "pays": "extra",
                    })
                    extra_essence_needed -= amount
            if extra_essence_needed:
                return "Not enough Essences are available for the extra cost.", None
        optional_extra = (ability or {}).get("optionalExtraEssence") or {}
        try:
            optional_extra_count = int(extra_essence_count or 0)
        except (TypeError, ValueError):
            return "The optional extra Essence count is invalid.", None
        optional_extra_count = max(0, optional_extra_count)
        if optional_extra_count and not optional_extra:
            return "This action cannot spend optional extra Essences.", None
        if optional_extra_count > int(optional_extra.get("max") or 0):
            return "Too many optional extra Essences were selected.", None
        if optional_extra_count:
            optional_remaining, optional_spent = (
                self.rules_essence_payment_plan(
                    player_id,
                    {
                        optional_extra["temperament"]:
                        optional_extra_count
                    },
                    essence_spent,
                )
            )
            if any(
                amount > 0 for amount in optional_remaining.values()
            ):
                return "Not enough Essences are available for the optional extra cost.", None
            for entry in optional_spent:
                entry["pays"] = "optional_extra"
            essence_spent.extend(optional_spent)
        extra_cards = [str(c) for c in (extra_payment_card_ids or []) if str(c)]
        if extra_cards:
            if not optional_extra:
                return "This action cannot spend optional extra Tribute.", None
            pool = list(hand)
            if source and source.get("zone") == "hand" and source.get("cardId") in pool:
                pool.remove(source["cardId"])
            for entry in clean_entries:
                if entry["zone"] == "hand" and entry["cardId"] in pool:
                    pool.remove(entry["cardId"])
            for card_id in extra_cards:
                metadata = self.card_rules.get(card_id, {})
                if card_id not in pool or metadata.get("type") != "manifestation":
                    return "An extra Tribute card is no longer in your Hand.", None
                if not metadata.get("canPayTribute", True):
                    return "This Manifestation cannot be used to pay Tribute.", None
                pool.remove(card_id)
                value = self.rules_tribute_power_override(player_id, metadata)
                if value is None:
                    value = int(metadata.get("power") or 0)
                optional_extra_count += max(0, int(value))
                clean_entries.append({"zone": "hand", "cardId": card_id})
                clean_ids.append(card_id)
            if optional_extra_count > int(optional_extra.get("max") or 0):
                return "Too many optional extra Essences were selected.", None
        return None, {
            "cardIds": clean_ids,
            "cardEntries": clean_entries,
            "requirements": requirements,
            "essenceSpent": essence_spent,
            "excessEssence": [
                (
                    {"temperament": key[0], "amount": amount, "retained": True}
                    if isinstance(key, tuple)
                    else {"temperament": key, "amount": amount}
                )
                for key, amount in excess.items() if amount > 0
            ],
            "validated": enforce_printed_cost,
            "sacrificeItemIds": [item["id"] for item in sacrifice_items],
            "optionalExtraEssenceSpent": optional_extra_count,
            "limboTributeSourceItemId": (
                limbo_source.get("id") if limbo_count and limbo_source else None
            ),
        }

    def record_rules_power_gained(self, item_id):
        item = self.find_battlefield_item(item_id)
        if item is not None:
            self.record_rules_observed_event(
                "power_gained", self.rules_item_controller_id(item), itemId=item_id,
            )

    def record_rules_power_lost(self, item_id):
        item = self.find_battlefield_item(item_id)
        if item is not None:
            self.record_rules_observed_event(
                "power_lost", self.rules_item_controller_id(item), itemId=item_id,
            )

    def rules_lunar_entries(self, player_id):
        """Manifestations a player can put into the Stalemate Zone from the Interzone or Vessel."""
        entries = [
            {"cardId": item["cardId"], "itemId": item["id"], "from": "interzone"}
            for item in self.battlefield
            if self.rules_item_controller_id(item) == player_id
            and self.rules_field_zone(item) == "interzone"
            and not item.get("isTokenCard") and not item.get("isCopy")
            and self.card_rules.get(item.get("cardId"), {}).get("type") == "manifestation"
        ]
        entries.extend(
            {"cardId": card_id, "itemId": None, "from": "vessel"}
            for card_id in self.players[player_id]["zones"]["receptacle"]
            if self.card_rules.get(card_id, {}).get("type") == "manifestation"
        )
        return entries

    def rules_lunar_next(self, host_id, controller_id, pending_ids, host_card_id, action_id):
        """Ask the next player (if any) to feed the Stalemate Zone; skip the End Phase for anyone who cannot."""
        while pending_ids:
            pid = pending_ids.pop(0)
            entries = self.rules_lunar_entries(pid)
            if not entries:
                self.rules_engine["skipEndPhaseTurn"] = self.phase_tracker["turn"]
                continue
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "reveal_hand_discard", "purpose": "lunar",
                "playerId": pid, "targetPlayerId": pid,
                "cardIds": [entry["cardId"] for entry in entries], "entries": entries,
                "_pending": list(pending_ids), "hostItemId": host_id, "controllerId": controller_id,
                "sourceCardId": host_card_id, "actionId": action_id,
            }
            return choice_id
        self.rules_engine["pendingChoice"] = None
        return None

    def rules_stalemate_item(self, item_id):
        item = self.find_battlefield_item(item_id)
        if item is None:
            return None
        item["fieldZone"] = "stalemate"
        item.pop("isSupport", None)
        item.pop("supportUntilTurn", None)
        return item_id

    def rules_next_deck_order_choice(self, queue, source_card_id):
        head, rest = queue[0], queue[1:]
        groups = [{
            "playerId": head["playerId"], "cardIds": list(head["cardIds"]),
            "topCount": None, "bottomCount": None,
        }]
        choice = {
            "id": new_id(), "kind": "deck_reorder",
            "playerId": head["playerId"], "sourceCardId": source_card_id,
            "groups": groups, "_groups": groups, "_queue": rest,
        }
        self.rules_engine["pendingChoice"] = choice
        return choice

    def rules_apply_power_distribution(self, action, shares, sign):
        applied = []
        for item_id, amount in shares.items():
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("itemId") == item_id
            ), None)
            if target is None or self.find_battlefield_item(item_id) is None:
                continue
            effects = self.create_rules_ongoing_effects({
                **action,
                "targets": [target],
                "ability": {
                    "id": f'{(action.get("ability") or {}).get("id")}:distribute',
                    "ongoingEffect": {
                        "kind": "power_modifier", "value": sign * int(amount),
                        # printed "distribute" without a duration is a permanent modifier
                        "duration": (
                            ((action.get("ability") or {}).get("result") or {}).get("duration")
                            or "until_end_of_turn"
                        ),
                    },
                },
            })
            if effects:
                applied.append({
                    "itemId": item_id, "cardId": target.get("cardId"),
                    "value": effects[0].get("value"),
                })
        return {"kind": "distribute_power", "status": "done", "applied": applied}

    def rules_next_pick_own_item_choice(self, queue, action_id, source_card_id, done,
                                        purpose="stalemate"):
        head, rest = queue[0], queue[1:]
        choice = {
            "id": new_id(), "kind": "pick_own_item",
            "playerId": head["playerId"],
            "candidateItemIds": list(head["candidateItemIds"]),
            "purpose": purpose,
            "actionId": action_id, "sourceCardId": source_card_id,
            "_queue": rest, "_done": list(done),
        }
        self.rules_engine["pendingChoice"] = choice
        return choice

    def rules_item_zone_locked(self, item):
        return bool(item) and item.get("zoneLockTurn") == self.phase_tracker["turn"]

    def rules_support_entry_locked(self, player_id):
        turn = self.phase_tracker["turn"]
        return any(
            lock.get("turn") == turn
            and lock.get("playerId") in {None, player_id}
            for lock in self.rules_engine.get("supportLocks") or []
        )

    def rules_refund_stack_action_essence(self, stack_action):
        """Give the Will's controller excess essence equal to its Tribute cost."""
        card_id = (stack_action.get("source") or {}).get("cardId")
        metadata = self.card_rules.get(card_id, {})
        owner_id = stack_action.get("controllerId")
        cost = int(metadata.get("cost") or 0)
        if owner_id not in self.players or cost <= 0:
            return []
        temperament = next(iter(metadata.get("temperaments") or []), "hollow")
        return self.add_rules_excess_essence(
            owner_id, [{"temperament": temperament, "amount": cost}]
        )

    def add_rules_excess_essence(self, player_id, generated):
        seat = self.players[player_id].get("seat")
        created = []
        all_hollow = bool(self.rules_active_passive_sources("excess_essence_as_hollow"))
        for index, entry in enumerate(generated):
            temperament = "hollow" if all_hollow else entry["temperament"]
            amount = int(entry["amount"])
            expires_turn = 0 if entry.get("retained") else self.phase_tracker["turn"]
            token = next((
                candidate for candidate in self.tokens
                if candidate.get("ownerId") == player_id
                and candidate.get("isEssence")
                and not candidate.get("isNeutralCounter")
                and candidate.get("temperament") == temperament
                and int(candidate.get("expiresTurn") or 0) == expires_turn
                and int(candidate.get("counters", {}).get("essence") or 0) >= 0
            ), None)
            if token is None:
                token = {
                    "id": new_id(),
                    "ownerId": player_id,
                    "x": 700 + (index * 58),
                    "y": 1120 if seat != 1 else 330,
                    "isEssence": True,
                    "temperament": temperament,
                    "isNeutralCounter": False,
                    "isExcess": True,
                    "label": "",
                    "color": "#b58a24",
                    "counters": {"essence": 0},
                    "expiresTurn": expires_turn,
                }
                self.tokens.append(token)
            token["counters"]["essence"] = int(token["counters"].get("essence") or 0) + amount
            created.append({
                "tokenId": token["id"], "temperament": temperament, "amount": amount,
            })
        return created

    def expire_rules_excess_essence(self, completed_turn):
        expired = [
            token for token in self.tokens
            if token.get("isEssence")
            and not token.get("isNeutralCounter")
            and int(token.get("expiresTurn") or 0) <= int(completed_turn)
            and int(token.get("expiresTurn") or 0) > 0
            and not any(
                self.rules_item_controller_id(source) == token.get("ownerId")
                for source in self.rules_active_passive_sources(
                    "retain_excess_essence"
                )
            )
        ]
        expired_ids = {token["id"] for token in expired}
        if expired_ids:
            self.tokens = [
                token for token in self.tokens if token.get("id") not in expired_ids
            ]
        return expired

    def pay_rules_tribute(self, player_id, payment):
        """Apply a fully validated Essence/Manifestation Tribute payment."""
        spent_by_token = {}
        for entry in payment["essenceSpent"]:
            spent_by_token[entry["tokenId"]] = spent_by_token.get(entry["tokenId"], 0) + entry["amount"]
        for token_id, amount in spent_by_token.items():
            token = self.find_token(token_id)
            token["counters"]["essence"] -= amount
            if token["counters"]["essence"] <= 0:
                self.tokens.remove(token)
        movements = []
        for sacrifice_id in payment.get("sacrificeItemIds") or []:
            sacrificed = self.find_battlefield_item(sacrifice_id)
            if sacrificed is not None:
                self._rules_remove_field_item_by_effect(
                    sacrificed, sacrificed.get("ownerId"), "graveyard", "top",
                    reason="sacrifice",
                )
        limbo_source = self.find_battlefield_item(
            payment.get("limboTributeSourceItemId")
        )
        for entry in payment.get("cardEntries") or [
            {"zone": "hand", "cardId": card_id}
            for card_id in payment["cardIds"]
        ]:
            card_id = entry["cardId"]
            from_zone = entry["zone"]
            if from_zone == "battlefield":
                item = self.find_battlefield_item(entry.get("itemId"))
                if item is None:
                    raise RuntimeError(
                        "Validated Interzone Tribute payment disappeared."
                    )
                movement = self._rules_remove_field_item(
                    item, item.get("ownerId"), "graveyard", "top"
                )
                self.rules_engine["tributeLog"] = [
                    entry for entry in self.rules_engine.get("tributeLog") or []
                    if entry.get("turn") == self.phase_tracker["turn"]
                ] + [{
                    "turn": self.phase_tracker["turn"], "playerId": player_id,
                    "cardId": card_id, "ownerId": item.get("ownerId"),
                }]
                movements.append({
                    "cardId": card_id, "ownerId": item.get("ownerId"),
                    "fromZone": "interzone",
                    "destination": "graveyard",
                    "itemId": item.get("id"),
                    "status": movement.get("status"),
                })
                continue
            owner_id = self.card_owner_in_zone(player_id, from_zone, card_id)
            if from_zone == "receptacle":
                error, _owner_id, replacement = self.move_zone_card_by_effect(
                    player_id, "receptacle", owner_id, "exile", card_id, "top",
                )
                if error or replacement:
                    raise RuntimeError("Validated Vessel Tribute payment failed.")
                movements.append({
                    "cardId": card_id, "ownerId": owner_id,
                    "fromZone": "receptacle", "destination": "exile",
                })
                continue
            if from_zone == "graveyard":
                error, _owner_id, replacement = self.move_zone_card_by_effect(
                    player_id, "graveyard", owner_id, "exile",
                    card_id, "top",
                )
                if error or replacement:
                    raise RuntimeError(
                        "Validated Limbo Tribute payment failed."
                    )
                if not self.card_rules.get(card_id, {}).get("canPayTributeFromLimbo"):
                    counters = limbo_source.setdefault("counters", {})
                    counters["Formula"] = int(counters.get("Formula") or 0) - 1
                movements.append({
                    "cardId": card_id, "ownerId": owner_id,
                    "fromZone": "graveyard", "destination": "exile",
                })
                continue
            destination = self.card_rules.get(card_id, {}).get(
                "tributeDestination", "graveyard"
            )
            if destination == "stalemate":
                taken_owner_id = self.take_zone_card(player_id, "hand", card_id)
                if taken_owner_id is None:
                    raise RuntimeError("Validated Tribute payment card disappeared.")
                seat = self.players[player_id].get("seat")
                item = {
                    "id": new_id(), "ownerId": owner_id,
                    "controllerId": player_id, "cardId": card_id,
                    "x": 650.0, "y": 800.0 if seat != 1 else 525.0,
                    "faceUp": True, "rotation": 0.0, "counters": {},
                    "rarity": self.players[owner_id].get(
                        "cardRarities", {}
                    ).get(card_id),
                    "stackedOn": None, "fieldZone": "stalemate",
                }
                self.battlefield.append(item)
                movements.append({
                    "cardId": card_id, "ownerId": owner_id,
                    "destination": "stalemate", "itemId": item["id"],
                })
                continue
            zone = "deck" if destination == "deck_bottom" else "graveyard"
            position = "bottom" if destination == "deck_bottom" else "top"
            error, _ = self.move_zone_card(
                player_id, "hand", owner_id, zone, card_id, position,
                limbo_reason="tribute",
            )
            if error:
                raise RuntimeError(f"Validated Tribute payment failed: {error}")
            self.rules_engine["tributeLog"] = [
                entry for entry in self.rules_engine.get("tributeLog") or []
                if entry.get("turn") == self.phase_tracker["turn"]
            ] + [{
                "turn": self.phase_tracker["turn"], "playerId": player_id,
                "cardId": card_id, "ownerId": owner_id,
            }] if destination == "graveyard" else self.rules_engine.get("tributeLog") or []
            movements.append({
                "cardId": card_id, "ownerId": owner_id,
                "destination": destination,
            })
        return {
            "createdEssence": self.add_rules_excess_essence(
                player_id, payment["excessEssence"]
            ),
            "movements": movements,
        }

    def pay_rules_activation_cost(self, source, ability):
        result = {
            "sacrificedCards": [],
            "removedCounters": [],
            "reducedSourcePower": 0,
            "reducedSourcePower": 0,
        }
        if not ability:
            return result
        item = self.find_battlefield_item(source.get("itemId"))
        if (ability.get("exhaustSource") or ability.get("sacrificeSource")) and item is None:
            raise RuntimeError("Validated activated source disappeared before paying its cost.")
        if ability.get("exhaustSource"):
            item["rotation"] = 90.0
        if ability.get("sacrificeSource"):
            self.battlefield.remove(item)
            for other in self.battlefield:
                if other.get("stackedOn") == item.get("id"):
                    other["stackedOn"] = None
            sacrifice_zone = "exile" if ability.get("sacrificeDestination") == "exile" else "graveyard"
            if item.get("isCopy") or item.get("isTokenCard"):
                sacrifice_zone = None
            if sacrifice_zone:
                self.put_zone_card(item["ownerId"], sacrifice_zone, item["cardId"], item["ownerId"], "top")
            result["sacrificedCards"].append({
                "itemId": item["id"], "cardId": item["cardId"], "ownerId": item["ownerId"],
                "destination": sacrifice_zone or "removed",
            })
            self.prune_rules_ongoing_effects()
        if ability.get("sacrificeTokenCreatedBySource"):
            token = next((
                candidate for candidate in self.battlefield
                if candidate.get("isTokenCard")
                and candidate.get("createdByItemId") == source.get("itemId")
                and self.rules_item_controller_id(candidate)
                == source.get("controllerId")
            ), None)
            if token is None:
                raise RuntimeError(
                    "Validated source-created Token disappeared before payment."
                )
            self.battlefield.remove(token)
            result["sacrificedCards"].append({
                "itemId": token["id"], "cardId": token.get("cardId"),
                "ownerId": token.get("ownerId"), "destination": "removed",
            })
        score_cost = int(ability.get("loseScore") or 0)
        if score_cost > 0:
            controller_id = source.get("controllerId")
            paid = self.adjust_rules_score(controller_id, -score_cost)
            if paid != -score_cost:
                raise RuntimeError(
                    "Validated Point cost became unavailable before payment."
                )
            result["scorePaid"] = score_cost
        counter_name = ability.get("removeAllCountersFromSource")
        if counter_name:
            if item is None:
                raise RuntimeError("Validated counter source disappeared before payment.")
            counters = item.setdefault("counters", {})
            counter_key = next((
                key for key in counters
                if str(key).casefold() == str(counter_name).casefold()
            ), counter_name)
            removed = max(0, int(counters.get(counter_key) or 0))
            if counter_key in counters:
                counters.pop(counter_key)
            result["removedCounters"].append({
                "name": counter_name,
                "amount": removed,
            })
        counter_cost = ability.get("removeCountersFromSource")
        if isinstance(counter_cost, dict) and counter_cost.get("name"):
            if item is None:
                raise RuntimeError("Validated counter source disappeared before payment.")
            counters = item.setdefault("counters", {})
            counter_key = next((
                key for key in counters
                if str(key).casefold() == str(counter_cost["name"]).casefold()
            ), counter_cost["name"])
            amount = max(0, int(counter_cost.get("amount") or 0))
            if int(counters.get(counter_key) or 0) < amount:
                raise RuntimeError("Validated counter cost became unavailable before payment.")
            counters[counter_key] = int(counters.get(counter_key) or 0) - amount
            result["removedCounters"].append({
                "name": counter_cost["name"], "amount": amount,
            })
        counter_gain = ability.get("addCountersToSource")
        if isinstance(counter_gain, dict) and counter_gain.get("name"):
            if item is None:
                raise RuntimeError("Validated counter source disappeared before payment.")
            counters = item.setdefault("counters", {})
            gain_key = next((
                key for key in counters
                if str(key).casefold() == str(counter_gain["name"]).casefold()
            ), counter_gain["name"])
            counters[gain_key] = int(counters.get(gain_key) or 0) + max(0, int(counter_gain.get("amount") or 0))
        reduction = int(ability.get("reduceSourcePower") or 0)
        if reduction > 0:
            if item is None:
                raise RuntimeError("Validated Reduce source disappeared before payment.")
            counters = item.setdefault("counters", {})
            counters["power"] = int(counters.get("power") or 0) - reduction
            result["reducedSourcePower"] = reduction
        if ability.get("usePerTurn") and item is not None:
            turn_uses = item.setdefault("abilityTurnUses", {})
            turn_uses[str(ability.get("id"))] = self.phase_tracker["turn"]
            required = ability.get("supportWhenAllUsed") or []
            if required and all(
                turn_uses.get(str(entry)) == self.phase_tracker["turn"]
                for entry in required
            ):
                item["supportUntilTurn"] = self.phase_tracker["turn"]
                result["grantedSupport"] = True
        if int(ability.get("useLimit") or 0) > 0 and item is not None:
            uses = item.setdefault("abilityUses", {})
            uses[str(ability.get("id"))] = int(uses.get(str(ability.get("id"))) or 0) + 1
        return result
