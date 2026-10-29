"""Triggered abilities, simultaneous batches and zone-entry watchers."""

import re
import time
from itertools import combinations

from .common import (
    RULES_SCORE_COUNTS, RULES_AFTER_CHAIN, ADVANCED_PHASES, NUM_SEATS,
    TRIBUTE_SYMBOL_TEMPERAMENT, RULES_WILL_TYPES, RULES_ENTRY_EVENTS, RULES_EFFECT_DURATIONS,
    RULES_TEMPERAMENTS, new_id
)


class TriggersMixin:
    def queue_rules_will_target_watchers(self, action):
        """Fire "a manifestation became the target of a Will on the Stack" watchers."""
        queued = []
        for target in action.get("targets") or []:
            if target.get("kind") != "card":
                continue
            target_item = self.find_battlefield_item(target.get("itemId"))
            if target_item is None:
                continue
            target_controller = self.rules_item_controller_id(target_item)
            for source in list(self.battlefield):
                if not self.rules_item_effects_active(source):
                    continue
                queued.extend(self.queue_rules_triggers(
                    source.get("cardId"), source.get("ownerId"),
                    "manifestation_targeted_by_will",
                    zone=self.rules_field_zone(source),
                    item_id=source.get("id"), face_up=True,
                    event_controller_id=target_controller,
                    event_item_id=target_item.get("id"), defer=True,
                    controller_id=self.rules_item_controller_id(source),
                ))
        if queued:
            self.queue_rules_simultaneous_actions(queued)
        return queued

    @classmethod
    def clean_rules_trigger_result(cls, result):
        kind = result.get("kind")
        if kind == "create_effect_memory":
            memory_kind = str(result.get("memoryKind") or "")
            attach_to = str(result.get("attachTo") or "")
            if (
                memory_kind not in {
                    "return_from_limbo_end_turn",
                    "win_destination_exile",
                }
                or attach_to not in {"event_card", "paid_action_source"}
            ):
                return None
            clean = {
                "kind": kind,
                "memoryKind": memory_kind,
                "attachTo": attach_to,
                "optional": bool(result.get("optional")),
            }
            if result.get("rollReturnOrExile"):
                clean["rollReturnOrExile"] = True
            if result.get("requireLostConfrontation"):
                clean["requireLostConfrontation"] = True
            payment = str(result.get("opponentPayment") or "")
            if payment:
                symbols = re.findall(r"\{([A-Z])\}", payment)
                if (
                    not symbols
                    or any(symbol not in TRIBUTE_SYMBOL_TEMPERAMENT for symbol in symbols)
                ):
                    return None
                clean["opponentPayment"] = payment
            return clean
        if kind == "protect_related_will":
            return {"kind": kind}
        if kind == "add_counter_source":
            counter = str(result.get("counter") or "")[:64]
            value = result.get("value")
            if not counter or not isinstance(value, (int, float)):
                return None
            clean = {
                "kind": kind,
                "counter": counter,
                "value": max(-999, min(int(value), 999)),
            }
            if result.get("onZeroTemperament") in RULES_TEMPERAMENTS:
                clean["onZeroTemperament"] = result["onZeroTemperament"]
            return clean
        if kind == "lose_excess_essence_or_points":
            value = result.get("value")
            if not isinstance(value, (int, float)) or int(value) < 1:
                return None
            return {"kind": kind, "value": min(int(value), 999)}
        if kind == "each_player_recovery_choice":
            return {"kind": kind}
        if kind == "chain_from_zone":
            zone = str(result.get("zone") or "")
            if zone not in {"hand", "graveyard", "deck", "receptacle"}:
                return None
            clean = {"kind": kind, "zone": zone, "optional": bool(result.get("optional"))}
            if result.get("winDestination") in {"opponent_receptacle", "exile"}:
                clean["winDestination"] = result["winDestination"]
            if result.get("shuffleAfter"):
                clean["shuffleAfter"] = True
            if result.get("returnToVessel"):
                clean["returnToVessel"] = True
            if result.get("players") in {"each_opponent", "all"}:
                clean["players"] = result["players"]
            if result.get("simultaneous"):
                clean["simultaneous"] = True
            if isinstance(result.get("scoreCost"), (int, float)) and result["scoreCost"] < 0:
                clean["scoreCost"] = max(-999, int(result["scoreCost"]))
            if result.get("preMove") == "first_manifestation_to_deck_bottom":
                clean["preMove"] = result["preMove"]
            after_chain = result.get("afterChain")
            if isinstance(after_chain, dict) and after_chain.get("kind") in RULES_AFTER_CHAIN:
                clean["afterChain"] = {"kind": after_chain["kind"]}
                if isinstance(after_chain.get("value"), (int, float)):
                    clean["afterChain"]["value"] = max(
                        -99, min(int(after_chain["value"]), 99)
                    )
            chain_abilities = []
            for chained in result.get("chainAbilities") or []:
                if not isinstance(chained, dict):
                    continue
                event = (chained.get("trigger") or {}).get("event")
                inner = chained.get("result")
                inner_clean = (
                    cls.clean_rules_trigger_result(inner)
                    or cls.clean_rules_action_result(inner)
                ) if isinstance(inner, dict) and inner.get("kind") != "chain_from_zone" else None
                if event in {"wins_confrontation", "loses_confrontation"} and inner_clean:
                    chain_abilities.append({
                        "id": str(chained.get("id") or "")[:80],
                        "trigger": {"event": event},
                        "result": inner_clean,
                    })
            if chain_abilities:
                clean["chainAbilities"] = chain_abilities
            return clean
        value = result.get("value")
        if kind not in {"score_owner", "draw_owner", "discard_hand_target", "discard_deck_owner"} or not isinstance(value, (int, float)):
            return None
        clean_value = (
            max(-999, min(int(value), 999))
            if kind == "score_owner"
            else max(0, min(int(value), 7 if kind == "discard_hand_target" else 50))
        )
        clean = {"kind": kind, "value": clean_value}
        if kind == "score_owner" and result.get("perCount") in RULES_SCORE_COUNTS:
            clean["perCount"] = result["perCount"]
        if kind in {"draw_owner", "discard_deck_owner"} and result.get("targetPlayer"):
            clean["targetPlayer"] = True
        return clean

    def rules_legal_target_candidates(self, target_rules, controller_id, event_item_id=None,
                                     source_item_id=None, source_card_id=None):
        """Enumerate public targets using the same validation as declarations."""
        kind = str(target_rules.get("kind") or "card")
        zones = set(target_rules.get("zones") or ["battlefield"])
        candidates = [
            {"kind": "card", "itemId": item.get("id"), "cardId": item.get("cardId")}
            for item in self.battlefield
            if kind in {"card", "card_or_stack_action"} and "battlefield" in zones
        ]
        candidates.extend(
            {"kind": "zone_card", "containerId": container_id, "zone": zone, "cardId": card_id}
            for container_id, player in self.players.items()
            for zone in zones - {"battlefield"}
            for card_id in set(player.get("zones", {}).get(zone, []))
            if kind in {"card", "zone_card"}
        )
        if kind == "player":
            candidates.extend({"kind": "player", "playerId": pid} for pid in self.players)
        if kind in {"stack_action", "stack_effect", "stack_item", "card_or_stack_action"}:
            candidates.extend({
                "kind": "stack_action" if kind == "card_or_stack_action" else kind,
                "actionId": action.get("id"),
            } for action in self.rules_engine.get("actionStack") or [])
        legal = []
        for candidate in candidates:
            error, clean = self.rules_action_targets([candidate], controller_id)
            if error:
                continue
            if self.rules_ability_targets_error(
                {**target_rules, "min": 1, "max": 1}, clean, controller_id, event_item_id=event_item_id,
                source_item_id=source_item_id, source_card_id=source_card_id,
            ) is None:
                legal.extend(clean)
        return legal

    def rules_trigger_has_no_legal_target(self, target_rules, controller_id, event_item_id=None,
                                         source_item_id=None, source_card_id=None):
        """Required groups need a complete assignment of distinct legal targets."""
        target_rules = target_rules or {}
        context = {"event_item_id": event_item_id, "source_item_id": source_item_id,
                   "source_card_id": source_card_id}
        groups = target_rules.get("groups")
        if isinstance(groups, list):
            candidates = [self.rules_legal_target_candidates(group, controller_id, **context) for group in groups]

            def assign(index, chosen):
                if index == len(candidates):
                    error, clean = self.rules_action_targets(chosen, controller_id)
                    return not error and len(clean) == len(chosen)
                return any(target not in chosen and assign(index + 1, chosen + [target])
                           for target in candidates[index])

            return not assign(0, [])
        minimum = int(target_rules.get("min") or 0)
        if minimum < 1:
            return False
        candidates = self.rules_legal_target_candidates(target_rules, controller_id, **context)
        return not any(self.rules_ability_targets_error(
            target_rules, list(chosen), controller_id, **context,
        ) is None for chosen in combinations(candidates, minimum))

    def rules_trigger_target_error(self, card_id, event, target_player_id=None, *,
                                   face_up=True, trigger_targets=None, controller_id=None,
                                   event_item_id=None, event_zone=None):
        """Validate required public targets before a placement becomes irreversible."""
        if not self.rules_engine["enabled"] or (event == "enters_field" and not face_up):
            return None
        target_error, clean_targets = self.rules_action_targets(trigger_targets)
        if target_error:
            return target_error
        source_item = self.find_battlefield_item(event_item_id)
        abilities = (
            self.rules_item_card_rules(source_item).get(
                "triggeredAbilities"
            ) or []
            if source_item is not None
            else self.card_rules.get(card_id, {}).get(
                "triggeredAbilities"
            ) or []
        )
        for ability in abilities:
            trigger = ability.get("trigger") or {}
            if trigger.get("event") != event:
                continue
            trigger_phase_ids = {
                phase_id for phase_id in trigger.get("phaseIds") or []
                if phase_id in ADVANCED_PHASES
            }
            if trigger_phase_ids and self.current_phase_id() not in trigger_phase_ids:
                continue
            if (
                trigger.get("zone")
                and (
                    event_zone
                    if event == "enters_field_zone"
                    else (
                        self.rules_field_zone(source_item)
                        if source_item is not None else None
                    )
                ) != trigger.get("zone")
            ):
                continue
            target_rules = self.rules_action_target_rules({"ability": ability}) or {}
            if isinstance(target_rules.get("groups"), list):
                target_rules = {**target_rules, "min": len(target_rules["groups"]), "max": len(target_rules["groups"])}
            # A played ability may choose a controller while a separate entry
            # trigger has no targets (Bibi). Match the trigger queue's filtering
            # rather than interpreting that played choice as an ETB target.
            targets = clean_targets if int(target_rules.get("max") or target_rules.get("min") or 0) > 0 else []
            if target_rules.get("kind") == "player":
                if target_player_id in self.players:
                    targets = [{"kind": "player", "playerId": target_player_id}]
                elif not any(
                    target.get("kind") == "player" and target.get("playerId") in self.players
                    for target in targets
                ) and int(target_rules.get("min") or 0) > 0:
                    return "Choose a valid player for this triggered effect."
            error = self.rules_ability_targets_error(
                target_rules, targets, controller_id, event_item_id=event_item_id,
                source_item_id=event_item_id, source_card_id=card_id,
            )
            if error and not targets and event in RULES_ENTRY_EVENTS and self.rules_trigger_has_no_legal_target(
                target_rules, controller_id, event_item_id,
                source_item_id=event_item_id, source_card_id=card_id,
            ):
                continue
            if error:
                return error
        return None

    def queue_rules_triggers(self, card_id, owner_id, event, *, zone=None,
                             container_id=None, item_id=None, face_up=True,
                             target_player_id=None, event_controller_id=None,
                             event_item_id=None, played=False, event_targets=None,
                             defer=False, related_action=None,
                             event_source_zone=None, controller_id=None,
                             resume_confrontation_cleanup=False,
                             abilities_override=None,
                             first_will_of_turn=False,
                             event_card_id=None, discard_source=None):
        """Put server-verifiable triggers for one completed event on the Stack."""
        if not self.rules_engine["enabled"] or self.ended or len(self.players) < NUM_SEATS:
            return []
        if owner_id not in self.players:
            return []
        if event_item_id is None and event in RULES_ENTRY_EVENTS:
            event_item_id = item_id
        controller_id = (
            controller_id if controller_id in self.players else owner_id
        )
        if event == "end_of_turn" and self.rules_player_skips_end_phase(controller_id):
            return []
        if event == "enters_zone" and container_id not in self.players:
            return []
        if (
            zone == "receptacle"
            and container_id in self.players
            and self.rules_vessel_locked(container_id)
        ):
            return []
        if event == "enters_field" and not face_up:
            return []
        if item_id:
            source_item = self.find_battlefield_item(item_id)
            if source_item is not None and not self.rules_item_effects_active(source_item):
                return []

        target_error, supplied_targets = self.rules_action_targets(event_targets)
        if target_error:
            return []
        queued = []
        abilities = abilities_override
        if abilities is None:
            source_item = self.find_battlefield_item(item_id)
            abilities = (
                self.rules_item_card_rules(source_item).get(
                    "triggeredAbilities"
                ) or []
                if source_item is not None
                else self.card_rules.get(card_id, {}).get(
                    "triggeredAbilities"
                ) or []
            )
        for ability in abilities:
            trigger = ability.get("trigger") or {}
            if trigger.get("event") != event:
                continue
            trigger_phase_ids = {
                phase_id for phase_id in trigger.get("phaseIds") or []
                if phase_id in ADVANCED_PHASES
            }
            if trigger_phase_ids and self.current_phase_id() not in trigger_phase_ids:
                continue
            trigger_source_item = self.find_battlefield_item(item_id)
            if trigger.get("supportOnly") and not (trigger_source_item or {}).get("isSupport"):
                continue
            if (
                trigger.get("zone")
                and event not in {
                    "enters_zone", "enters_field_zone",
                    "beginning_of_turn", "end_of_turn", "vessel_revelation",
                }
                and (
                    trigger_source_item is None
                    or self.rules_field_zone(trigger_source_item)
                    != trigger.get("zone")
                )
            ):
                continue
            if event == "vessel_revelation" and trigger.get("zone") != zone:
                continue
            if event == "enters_zone":
                if trigger.get("zone") != zone:
                    continue
                if trigger.get("container") == "opponent" and container_id == owner_id:
                    continue
            if event == "enters_field_zone" and trigger.get("zone") != zone:
                continue
            if (
                trigger.get("playedFromZone")
                and isinstance(related_action, dict)
                and (related_action.get("source") or {}).get("zone")
                != trigger.get("playedFromZone")
            ):
                continue
            if trigger.get("firstWillOfTurn") and not first_will_of_turn:
                continue
            if trigger.get("eventCardTypes") and self.card_rules.get(
                event_card_id, {}
            ).get("type") not in trigger["eventCardTypes"]:
                continue
            if trigger.get("cardTemperament") and trigger[
                "cardTemperament"
            ] not in (
                self.card_rules.get(event_card_id, {}).get("temperaments") or []
            ):
                continue
            if "controllerConfrontationManifestations" in trigger and len(
                self.rules_confrontation_items(controller_id)
            ) != int(trigger["controllerConfrontationManifestations"]):
                continue
            if (
                event in {"beginning_of_turn", "vessel_revelation"}
                and trigger.get("container") == "opponent"
                and container_id == owner_id
            ):
                continue
            counter_min = trigger.get("sourceCounterMin")
            if isinstance(counter_min, dict):
                source_counters = (
                    self.find_battlefield_item(item_id) or {}
                ).get("counters") or {}
                counter_total = sum(
                    int(value or 0) for key, value in source_counters.items()
                    if str(key).casefold()
                    == str(counter_min.get("name") or "").casefold()
                )
                if counter_total < int(counter_min.get("min") or 0):
                    continue
            if trigger.get("playedAs") == "support_or_hand_will":
                if event_item_id:
                    played_item = self.find_battlefield_item(event_item_id)
                    if played_item is None or not played_item.get("isSupport"):
                        continue
                elif (
                    not isinstance(related_action, dict)
                    or (related_action.get("source") or {}).get("zone") != "hand"
                ):
                    continue
            if trigger.get("eventNonToken"):
                token_item = self.find_battlefield_item(event_item_id)
                if token_item is None or token_item.get("isTokenCard") or token_item.get(
                    "isCopy"
                ) or token_item.get("isTokenCopy"):
                    continue
            if "sourceLeftVessel" in trigger and bool(trigger["sourceLeftVessel"]) != (
                f"{owner_id}:{card_id}" in (self.rules_engine.get("leftVesselCards") or [])
            ):
                continue
            counter_max = trigger.get("sourceCounterMax")
            if isinstance(counter_max, dict):
                source_counters = (
                    self.find_battlefield_item(item_id) or {}
                ).get("counters") or {}
                counter_total = sum(
                    int(value or 0) for key, value in source_counters.items()
                    if str(key).casefold()
                    == str(counter_max.get("name") or "").casefold()
                )
                if counter_total > int(counter_max.get("max") or 0):
                    continue
            if event == "beginning_of_turn" and trigger.get("zone") and trigger.get("zone") != zone:
                continue
            if event == "end_of_turn" and trigger.get("zone") and trigger.get("zone") != zone:
                continue
            if event == "enters_field" and trigger.get("visibility") == "face_up" and not face_up:
                continue
            if event == "enters_support":
                if trigger.get("sourceZone") and trigger.get("sourceZone") != zone:
                    continue
                if trigger.get("played") and not played:
                    continue
                if trigger.get("eventController") == "owner" and event_controller_id != (
                    controller_id if controller_id is not None else owner_id
                ):
                    continue
                if (
                    trigger.get("enteredFromZone")
                    and trigger.get("enteredFromZone") != event_source_zone
                ):
                    continue
                if trigger.get("eventSourceOnly") and item_id != event_item_id:
                    continue
            if (
                trigger.get("eventController") == "opponent"
                and event_controller_id == controller_id
            ):
                continue
            if (
                trigger.get("eventController") == "owner"
                and event_controller_id is not None
                and event_controller_id != controller_id
            ):
                continue
            if (
                trigger.get("sourceController") == "not_owner"
                and controller_id == owner_id
            ):
                continue
            if trigger.get("oncePerTurn"):
                fired = self.rules_engine.setdefault("oncePerTurnFired", {})
                fired_key = f'{item_id or card_id}:{ability.get("id")}'
                if fired.get(fired_key) == self.phase_tracker["turn"]:
                    continue
                fired[fired_key] = self.phase_tracker["turn"]
            raw_result = ability.get("result") or {}
            if (
                raw_result.get("kind") == "force_win_if_highest_base_first"
                and not self.rules_is_strictly_highest_base_first(trigger_source_item)
            ):
                continue
            if (
                event == "card_played"
                and raw_result.get("kind") == "add_counter_source"
                and not ability.get("optional")
            ):
                # Atavic counters are automatic: no Stack, applied as the card is played
                if self.rules_add_source_counter(item_id, raw_result):
                    self.add_log(
                        controller_id, "rules_counter_added",
                        {"cardId": card_id, "counter": raw_result.get("counter"), "value": raw_result.get("value")},
                    )
                continue
            clean_result = self.clean_rules_trigger_result(raw_result) or self.clean_rules_action_result(raw_result)
            target_rules = self.rules_action_target_rules({"ability": ability}) or {}
            if isinstance(target_rules.get("groups"), list):
                target_rules = {**target_rules, "min": len(target_rules["groups"]), "max": len(target_rules["groups"])}
            clean_targets = (
                list(supplied_targets)
                if int(target_rules.get("max") or target_rules.get("min") or 0) > 0
                else []
            )
            if target_rules.get("kind") == "player" and trigger.get("target") == "event_controller":
                resolved_target_player_id = (
                    event_controller_id
                    if trigger.get("target") == "event_controller"
                    else target_player_id
                )
                if resolved_target_player_id not in self.players:
                    continue
                clean_targets = [{"kind": "player", "playerId": resolved_target_player_id}]
            elif target_rules.get("kind") == "player" and target_player_id in self.players:
                clean_targets = [{"kind": "player", "playerId": target_player_id}]
            if (
                not clean_targets and target_rules.get("kind") == "player"
                and int(target_rules.get("min") or 0) == 1 and int(target_rules.get("max") or 1) == 1
            ):
                # a single legal player (the only opponent): nothing to choose
                legal_players = [
                    candidate_id for candidate_id in self.players
                    if self.rules_ability_targets_error(
                        target_rules, [{"kind": "player", "playerId": candidate_id}],
                        controller_id, event_item_id=event_item_id,
                    ) is None
                ]
                if len(legal_players) == 1:
                    clean_targets = [{"kind": "player", "playerId": legal_players[0]}]
            target_validation_error = self.rules_ability_targets_error(
                target_rules, clean_targets, controller_id,
                event_item_id=event_item_id,
                source_item_id=item_id, source_card_id=card_id,
            )
            needs_target_choice = bool(
                not clean_targets and (
                    target_validation_error and int(target_rules.get("min") or 0) > 0
                    or (clean_result or {}).get("kind") in {
                        "shuffle_limbo_targets_into_deck", "exile_limbo_wills_add_power_each",
                        "exile_limbo_targets_add_power",
                    }
                )
            )
            if target_validation_error and not needs_target_choice:
                continue
            if needs_target_choice and self.rules_trigger_has_no_legal_target(
                # a card's own entry: it is the event source (Flower Tender
                # cannot target itself)
                target_rules, controller_id,
                event_item_id or (item_id if event in RULES_ENTRY_EVENTS else None),
                source_item_id=item_id, source_card_id=card_id,
            ):
                continue
            if clean_targets:
                clean_targets = self.rules_redirect_targets(controller_id, clean_targets, card_id)
            self.apply_rules_drill_drain(item_id)
            ongoing_definition = ability.get("ongoingEffect") or {}
            clean_ongoing_effect = None
            duration = str(ongoing_definition.get("duration") or "")
            if ongoing_definition.get("kind") and duration in RULES_EFFECT_DURATIONS:
                clean_ongoing_effect = {
                    "kind": str(ongoing_definition["kind"])[:64],
                    "duration": duration,
                }
                if isinstance(ongoing_definition.get("value"), (int, float)):
                    clean_ongoing_effect["value"] = ongoing_definition["value"]
                if ongoing_definition.get("scope") in {
                    "all_manifestations_on_field",
                    "all_manifestations_in_confrontation",
                    "opponent_manifestations_in_confrontation",
                    "friendly_cards_on_field",
                    "friendly_manifestations_in_interzone",
                    "friendly_manifestations_in_confrontation",
                    "target_player_manifestations_in_interzone",
                    "source",
                }:
                    clean_ongoing_effect["scope"] = ongoing_definition["scope"]
                if ongoing_definition.get("excludeSource"):
                    clean_ongoing_effect["excludeSource"] = True
                if ongoing_definition.get("fromOpponents"):
                    clean_ongoing_effect["fromOpponents"] = True
            if clean_result is None and clean_ongoing_effect is None:
                continue
            source_zone = {
                "enters_zone": zone,
                "enters_field": "battlefield",
                "used_as_tribute": event_source_zone or "graveyard",
                "beginning_of_turn": zone or "battlefield",
                "enters_support": zone,
                "manifestation_enters_field": "battlefield",
                "manifestation_used_as_tribute": "battlefield",
                "persistent_will_enters_field": "battlefield",
                "will_played": "battlefield",
                "card_played": "battlefield",
                "player_wins_confrontation": "battlefield",
                "player_loses_confrontation": "battlefield",
                "points_lost": "battlefield",
                "power_lost": "battlefield",
                "power_gained": "battlefield",
                "manifestation_left_by_effect": "battlefield",
                "cards_discarded": "battlefield",
                "deck_cards_discarded": "battlefield",
                "cards_drawn": "battlefield",
                "points_gained": "battlefield",
                "manifestation_entered_limbo": "battlefield",
                "enters_limbo": "graveyard",
                "discarded": "graveyard",
                "manifestation_targeted_by_will": "battlefield",
                "manifestation_destroyed": "battlefield",
                "manifestation_enters_opponent_vessel": "battlefield",
                "wins_confrontation": "battlefield",
                "loses_confrontation": "battlefield",
                "confrontation_stalemate": "battlefield",
                "revelation": "battlefield",
                "reaction": "battlefield",
                "vessel_revelation": zone,
                "before_revelation": "battlefield",
                "enters_field_zone": "battlefield",
                "end_of_turn": "battlefield",
                "resolution": "battlefield",
            }.get(event)
            if source_zone is None:
                continue
            action = {
                "id": new_id(),
                "controllerId": controller_id,
                "label": f'{self.card_labels.get(card_id, card_id)} — triggered effect',
                "kind": "triggered_effect",
                "optional": bool(ability.get("optional")),
                "source": {
                    "cardId": card_id,
                    "zone": source_zone,
                    "itemId": item_id if event in {
                        "enters_field", "enters_support",
                        "manifestation_enters_field", "beginning_of_turn",
                        "manifestation_used_as_tribute",
                        "persistent_will_enters_field",
                        "will_played", "card_played",
                        "player_wins_confrontation",
                        "player_loses_confrontation",
                        "points_lost", "power_lost", "power_gained",
                        "manifestation_left_by_effect", "cards_discarded",
                        "deck_cards_discarded", "cards_drawn", "points_gained",
                        "manifestation_entered_limbo", "manifestation_targeted_by_will",
                        "manifestation_destroyed",
                        "manifestation_enters_opponent_vessel",
                        "wins_confrontation",
                        "loses_confrontation",
                        "confrontation_stalemate",
                        "revelation",
                        "reaction",
                        "before_revelation",
                        "enters_field_zone", "end_of_turn", "resolution",
                    } else None,
                    "cardType": self.card_rules.get(card_id, {}).get("type"),
                    "ownerId": owner_id,
                    "containerId": container_id,
                },
                "target": None,
                "targets": clean_targets,
                "ability": {
                    "id": str(ability.get("id") or "")[:80],
                    "trigger": {
                        "event": event, "zone": zone,
                        "container": str(trigger.get("container") or "")[:32],
                        "visibility": str(trigger.get("visibility") or "")[:32],
                        "sourceZone": str(trigger.get("sourceZone") or "")[:32],
                        "enteredFromZone": str(trigger.get("enteredFromZone") or "")[:32],
                        "eventSourceOnly": bool(trigger.get("eventSourceOnly")),
                        "played": bool(trigger.get("played")),
                        "firstWillOfTurn": bool(trigger.get("firstWillOfTurn")),
                        "phaseIds": [
                            phase_id for phase_id in trigger.get("phaseIds") or []
                            if phase_id in ADVANCED_PHASES
                        ],
                        "eventController": str(trigger.get("eventController") or "")[:32],
                        "sourceController": str(trigger.get("sourceController") or "")[:32],
                        "eventControllerId": event_controller_id,
                        "eventItemId": event_item_id,
                        "sourceRollDiscarded": int((trigger_source_item or {}).get("rollDiscarded") or 0),
                        "relatedActionId": (
                            related_action.get("id")
                            if isinstance(related_action, dict) else None
                        ),
                        "relatedCardId": (
                            (related_action.get("source") or {}).get("cardId")
                            if isinstance(related_action, dict) else None
                        ),
                        "relatedOwnerId": (
                            (related_action.get("source") or {}).get("ownerId")
                            if isinstance(related_action, dict) else None
                        ),
                    },
                    "result": clean_result,
                    "ongoingEffect": clean_ongoing_effect,
                    "targets": {
                        key: list(value) if isinstance(value, list) else value
                        for key, value in target_rules.items()
                        if key in {
                            "kind", "min", "max", "cardType", "cardTypes", "zones",
                            "controller", "fieldZone", "supportOnly", "exhaustedOnly", "maxPoints",
                            "maxPower", "minPower", "excludeEventSource", "excludeSource", "sourceOnly",
                            "fieldZonesByType", "enteredThisTurn", "enteredInterzoneThisTurn", "confrontationOutcome", "owner",
                            "firstManifestationOnly", "counter", "minCounters", "distinctTemperaments", "sameContainer", "distinctTargets", "anyNumber", "maxCost",
                            "limboReasons", "container", "targetsConfrontationManifestation", "groups",
                        }
                    },
                },
                "cost": {
                    "note": None,
                    "tributeCardIds": [],
                    "tributeRequirements": {},
                    "essenceSpent": [],
                    "excessEssence": [],
                    "tributeValidated": False,
                    "tributePaid": False,
                    "sourceExhausted": False,
                    "sourceSacrificed": False,
                    "sacrificedCards": [],
                },
                "phaseId": self.current_phase_id(),
                "turn": self.phase_tracker["turn"],
                "createdAt": time.time(),
            }
            if ability.get("immediate"):
                action["immediate"] = True
            if event == "discarded" and discard_source:
                action["_discardSource"] = dict(discard_source)
                action["source"].update(discard_source)
            if (event == "used_as_tribute"
                    and (clean_result or {}).get("kind") == "create_effect_memory"
                    and clean_result.get("memoryKind") == "return_from_limbo_end_turn"):
                # This records the condition for a delayed End trigger. It is
                # not a second effect to respond to while paying the Will.
                # Loss requirements and optional returns are checked at End.
                if (clean_result.get("attachTo") == "paid_action_source"
                        and (not isinstance(related_action, dict)
                             or related_action.get("kind") != "play_card")):
                    continue  # Paying an activation does not play its source Will.
                self.apply_rules_action_result(action)
                continue
            if needs_target_choice:
                # Another trigger of the same event already waits for its targets
                # (Borombo losing while the winner also triggers): never overwrite
                # that choice, ask for these targets when the batch reaches it.
                target_choice_pending = (
                    (self.rules_engine.get("pendingChoice") or {}).get("kind")
                    == "trigger_targets"
                )
                # Collect the full event before asking for normal targets:
                # another source may have an Immediate that resolves first.
                defer_entry_targets = defer and event in (
                    RULES_ENTRY_EVENTS | {"revelation", "reaction"}
                )
                if defer_entry_targets or action["optional"] or target_choice_pending:
                    action["_preStackTargetChoice"] = {
                        "targetRules": action["ability"]["targets"],
                        "resumeConfrontationCleanup": bool(
                            resume_confrontation_cleanup
                        ),
                    }
                    queued.append(action)
                    continue
                self.rules_engine["pendingChoice"] = {
                    "id": new_id(),
                    "kind": "trigger_targets",
                    "playerId": controller_id,
                    "sourceCardId": card_id,
                    "targetRules": action["ability"]["targets"],
                    "sourceItemId": (action.get("source") or {}).get("itemId"),
                    "eventItemId": (action["ability"].get("trigger") or {}).get("eventItemId"),
                    "_triggerAction": action,
                    "_resumeConfrontationCleanup": bool(
                        resume_confrontation_cleanup
                    ),
                }
                self.rules_engine["priorityPasses"] = []
                self.rules_engine["priorityPlayerId"] = controller_id
                return queued
            queued.append(action)

        if queued and not defer:
            self.queue_rules_simultaneous_actions(queued)
        return queued

    def queue_rules_copied_entry_triggers(self, effect):
        source_item = self.find_battlefield_item(
            (effect.get("source") or {}).get("itemId")
        )
        if source_item is None:
            return []
        abilities = [
            ability
            for ability in (effect.get("copiedRules") or {}).get("triggeredAbilities") or []
            if (ability.get("ongoingEffect") or {}).get("kind")
            != "copy_power_effects"
        ]
        if not abilities:
            return []
        controller_id = self.rules_item_controller_id(source_item)
        owner_id = source_item.get("ownerId")
        events = [
            ("enters_field", {}),
            (
                "enters_field_zone",
                {"zone": self.rules_field_zone(source_item)},
            ),
            (
                "manifestation_enters_field",
                {"event_controller_id": controller_id},
            ),
        ]
        if source_item.get("isSupport"):
            events.append((
                "enters_support",
                {"event_controller_id": controller_id, "played": True},
            ))
        queued = []
        for event, kwargs in events:
            queued.extend(self.queue_rules_triggers(
                source_item.get("cardId"), owner_id, event,
                item_id=source_item.get("id"),
                event_item_id=source_item.get("id"),
                controller_id=controller_id,
                face_up=True,
                defer=True,
                abilities_override=abilities,
                **kwargs,
            ))
            if self.rules_engine.get("pendingChoice"):
                break
        return queued

    def _complete_rules_simultaneous_batch(self, ordered_actions):
        if ordered_actions:
            ordered_actions = [action for action in ordered_actions if not action.get("immediate")] + [action for action in ordered_actions if action.get("immediate")]
            self.rules_engine["actionStack"].extend(ordered_actions)
            self.rules_engine["priorityPasses"] = []
            self.rules_engine["priorityPlayerId"] = self.other_rules_player_id(
                ordered_actions[-1]["controllerId"]
            )
        self.rules_engine["pendingChoice"] = None
        return ordered_actions

    def _continue_rules_simultaneous_batch(self, groups, ordered_actions):
        groups = [list(group) for group in groups if group]
        while groups:
            group = groups.pop(0)
            regular = [action for action in group if not action.get("immediate")]
            immediate = [action for action in group if action.get("immediate")]
            group = [*regular, *immediate]
            if len(group) == 1:
                ordered_actions.extend(group)
                continue
            if len(regular) <= 1 and len(immediate) <= 1:
                ordered_actions.extend(group)
                continue
            controller_id = group[0]["controllerId"]
            self.rules_engine["pendingChoice"] = {
                "id": new_id(),
                "kind": "simultaneous_stack_order",
                "playerId": controller_id,
                "actions": [{
                    "actionId": action["id"],
                    "label": action.get("label"),
                    "abilityId": (action.get("ability") or {}).get("id"),
                    "cardId": (action.get("source") or {}).get("cardId"),
                    "kind": action.get("kind"),
                    "immediate": bool(action.get("immediate")),
                } for action in group],
                "_group": group,
                "_remainingGroups": groups,
                "_orderedActions": ordered_actions,
            }
            self.rules_engine["priorityPasses"] = []
            self.rules_engine["priorityPlayerId"] = controller_id
            return False
        self._complete_rules_simultaneous_batch(ordered_actions)
        return True

    def _queue_rules_simultaneous_actions_ready(self, actions,
                                                priority_player_id=None):
        actions = [action for action in actions if isinstance(action, dict)]
        if not actions:
            return True
        controllers = []
        for action in actions:
            controller_id = action.get("controllerId")
            if controller_id in self.players and controller_id not in controllers:
                controllers.append(controller_id)
        priority_player_id = (
            priority_player_id
            if priority_player_id in controllers
            else self.rules_engine.get("priorityPlayerId")
        )
        controller_order = []
        if priority_player_id in controllers:
            controller_order.append(priority_player_id)
        controller_order.extend(
            player["id"] for player in sorted(
                self.players.values(), key=lambda entry: entry.get("seat", 0)
            )
            if player["id"] in controllers and player["id"] not in controller_order
        )
        groups = [
            [action for action in actions if action.get("controllerId") == controller_id]
            for controller_id in controller_order
        ]
        return self._continue_rules_simultaneous_batch(groups, [])

    def rules_optional_trigger_available(self, action):
        """Avoid offering optional effects with no usable payment/card to choose.

        Only known immediate prerequisites are checked here. Effects that create
        permissions for later in the turn must still be offered with empty zones.
        The result handlers recheck availability when the Stack resolves.
        """
        ability = action.get("ability") or {}
        result = ability.get("result") or {}
        kind = result.get("kind")
        player_id = action.get("controllerId")
        player = self.players.get(player_id) or {}
        zones = player.get("zones") or {}
        hand = zones.get("hand") or []
        source = action.get("source") or {}
        if kind == "choose_hand_will_as_support_manifestation" and self.rules_support_entry_locked(player_id):
            return False
        if kind == "optional_discard_then_draw":
            return bool(hand) and not self.rules_hand_is_immune(player_id, player_id)
        if kind == "exile_source_grant_limbo_will_play":
            return self.rules_self_discard_source_available(action)
        if kind == "optional_discard_up_to":
            return bool(hand)
        if kind in {
            "optional_discard_wills_for_power", "choose_hand_will_as_support_manifestation",
            "bullyboo_reveal", "grimoire_place",
        }:
            return any(self.card_rules.get(cid, {}).get("type") in RULES_WILL_TYPES for cid in hand)
        if kind in {
            "optional_discard_manifestation_weaken_target", "hand_manifestation_choice",
            "amphora_offer", "obelisk_gift", "auction_offer",
        }:
            if (action.get("cost") or {}).get("revealedCard"):
                return True
            minimum = 2 if kind == "amphora_offer" else 1
            return sum(self.card_rules.get(cid, {}).get("type") == "manifestation" for cid in hand) >= minimum
        if kind == "gummo_copy_vessel":
            return bool(self.find_battlefield_item(source.get("itemId"))) and any(
                self.card_rules.get(cid, {}).get("type") == "manifestation"
                for cid in zones.get("receptacle") or []
            )
        if kind == "copy_related_tribute_if_exhaust":
            host = self.find_battlefield_item(source.get("itemId"))
            related = (ability.get("trigger") or {}).get("relatedCardId")
            return bool(host) and not int(round(float(host.get("rotation") or 0))) % 180 and (
                self.card_rules.get(related, {}).get("type") == "manifestation"
            )
        if kind == "chain_from_zone":
            # Numbi still reveals an opponent's Hand if they cannot Chain.
            if result.get("players") == "each_opponent" and result.get("zone") == "hand":
                return any(
                    other["zones"]["hand"] for pid, other in self.players.items() if pid != player_id
                )
            if result.get("players") in {"each_opponent", "all"}:
                return True
            return bool(self.rules_chain_candidates(player_id, result.get("zone")))
        if kind == "exile_limbo_targets_add_power":
            return any(
                self.card_rules.get(cid, {}).get("type") == "manifestation"
                for cid in zones.get("graveyard") or []
            )
        if kind in {"shuffle_limbo_targets_into_deck", "exile_limbo_wills_add_power_each"}:
            return not self.rules_trigger_has_no_legal_target(
                {**(ability.get("targets") or {}), "min": 1}, player_id,
                source_item_id=source.get("itemId"), source_card_id=source.get("cardId"),
            )
        return True

    def _continue_rules_optional_stack_choices(
        self, actions, next_index=0, accepted_actions=None,
        priority_player_id=None,
    ):
        if self.ended:
            return True
        actions = [action for action in actions if isinstance(action, dict)]
        accepted_actions = list(accepted_actions or [])
        # A prompt temporarily gives priority to its chooser. Keep the event's
        # original priority throughout this batch, including target selections.
        if priority_player_id not in self.players:
            priority_player_id = self.rules_engine.get("priorityPlayerId")
        while next_index < len(actions):
            action = actions[next_index]
            next_index += 1
            target_choice = action.get("_preStackTargetChoice")
            source = action.get("source") or {}
            if target_choice and self.rules_trigger_has_no_legal_target(
                target_choice.get("targetRules"), action.get("controllerId"),
                event_item_id=((action.get("ability") or {}).get("trigger") or {}).get("eventItemId"),
                source_item_id=source.get("itemId"), source_card_id=source.get("cardId"),
            ):
                # An Immediate may have removed the last candidate since this
                # batch was collected. Do not open an impossible target picker.
                if target_choice.get("resumeConfrontationCleanup"):
                    self.rules_engine["resumeConfrontationCleanupAfterChoices"] = True
                continue
            if (
                action.get("optional") and not action.get("optionalAccepted")
                and not self.rules_optional_trigger_available(action)
            ):
                continue
            if (
                ((action.get("ability") or {}).get("result") or {}).get("kind") == "grimoire_place"
                and not any(
                    self.card_rules.get(card_id, {}).get("type") in RULES_WILL_TYPES
                    for card_id in (self.players.get(action.get("controllerId")) or {}).get("zones", {}).get("hand", [])
                )
            ):
                # nothing to place on the Grimoire: the effect is not even offered
                continue
            chain_result = (action.get("ability") or {}).get("result") or {}
            if (
                action.get("optional") and not action.get("optionalAccepted")
                and chain_result.get("kind") == "chain_from_zone" and chain_result.get("zone") == "hand"
                and chain_result.get("players") not in {"each_opponent", "all"}
            ):
                # Chain from the hand: no "use the effect?" question; the player simply drags a card or passes
                if not self.rules_chain_candidates(action.get("controllerId"), "hand"):
                    continue
                action["optionalAccepted"] = True
                action["chainDeclinable"] = True
                accepted_actions.append(action)
                continue
            if action.get("optional") and not action.get("optionalAccepted"):
                controller_id = action.get("controllerId")
                self.rules_engine["pendingChoice"] = {
                    "id": new_id(),
                    "kind": "optional_stack_action",
                    "playerId": controller_id,
                    "sourceCardId": (action.get("source") or {}).get("cardId"),
                    "actionId": action.get("id"),
                    "label": action.get("label"),
                    "options": ["accept", "decline"],
                    "_action": action,
                    "_actions": actions,
                    "_nextIndex": next_index,
                    "_acceptedActions": accepted_actions,
                    "_priorityPlayerId": priority_player_id,
                }
                self.rules_engine["priorityPasses"] = []
                self.rules_engine["priorityPlayerId"] = controller_id
                return False
            target_choice = action.pop("_preStackTargetChoice", None)
            if target_choice:
                # a mandatory trigger whose targets were deferred: its controller
                # chooses them now, then the rest of the batch continues
                controller_id = action.get("controllerId")
                self.rules_engine["pendingChoice"] = {
                    "id": new_id(),
                    "kind": "trigger_targets",
                    "playerId": controller_id,
                    "sourceCardId": (action.get("source") or {}).get("cardId"),
                    "targetRules": target_choice.get("targetRules") or {},
                    "sourceItemId": (action.get("source") or {}).get("itemId"),
                    "eventItemId": ((action.get("ability") or {}).get("trigger") or {}).get("eventItemId"),
                    "_triggerAction": action,
                    "_resumeConfrontationCleanup": bool(
                        target_choice.get("resumeConfrontationCleanup")
                    ),
                    "_optionalStackBatch": {
                        "actions": actions,
                        "nextIndex": next_index,
                        "acceptedActions": accepted_actions,
                        "priorityPlayerId": priority_player_id,
                    },
                }
                self.rules_engine["priorityPasses"] = []
                self.rules_engine["priorityPlayerId"] = controller_id
                return False
            accepted_actions.append(action)
        completed = self._queue_rules_simultaneous_actions_ready(
            accepted_actions, priority_player_id
        )
        self.resume_rules_confrontation_cleanup_after_choices()
        return completed

    def resume_rules_confrontation_cleanup_after_choices(self):
        if self.ended:
            return
        if not self.rules_engine.get("pendingChoice") and self.rules_engine.pop(
            "resumeConfrontationCleanupAfterChoices", False
        ):
            self._queue_next_rules_confrontation_destination()

    def queue_rules_simultaneous_actions(self, actions, priority_player_id=None):
        """Confirm optional triggers, then queue one simultaneous event atomically."""
        if self.ended:
            return True
        pending = self.rules_engine.get("pendingChoice") or {}
        new_actions = [action for action in actions or [] if isinstance(action, dict)]
        immediate = [action for action in new_actions if action.get("immediate")]
        if immediate or any(action.get("immediate") for action in self.rules_engine["actionStack"]):
            regular = [action for action in new_actions if not action.get("immediate")]
            self.rules_engine.setdefault("deferredAfterImmediateActions", []).extend(regular)
            new_actions = immediate
            actions = immediate
            if not immediate:
                return True
        if new_actions and pending.get("kind") == "trigger_targets":
            # A trigger of this event is waiting for its targets (Borombo): the
            # other simultaneous triggers join its batch instead of replacing
            # the choice, and are confirmed once the targets are chosen.
            batch = pending.get("_optionalStackBatch")
            if not isinstance(batch, dict):
                batch = pending["_optionalStackBatch"] = {
                    "actions": [], "nextIndex": 0, "acceptedActions": [],
                    "priorityPlayerId": priority_player_id,
                }
            batch["actions"] = [*(batch.get("actions") or []), *new_actions]
            return False
        return self._continue_rules_optional_stack_choices(
            actions, priority_player_id=priority_player_id
        )

    def queue_or_defer_rules_simultaneous_actions(self, actions,
                                                  priority_player_id=None):
        if self.ended:
            return True
        actions = [action for action in actions if isinstance(action, dict)]
        if not actions:
            return True
        pending = self.rules_engine.get("pendingChoice")
        if pending and pending.get("kind") != "simultaneous_stack_order":
            self.rules_engine["deferredSimultaneousActions"].extend(actions)
            return False
        return self.queue_rules_simultaneous_actions(actions, priority_player_id)

    def flush_rules_deferred_simultaneous_actions(self):
        if self.ended:
            return []
        if self.rules_engine.get("pendingChoice"):
            return []
        self.resume_rules_confrontation_cleanup_after_choices()
        if self.rules_engine.get("pendingChoice"):
            return []
        observed = self.queue_rules_observed_event_triggers(defer=True)
        if observed:
            self.queue_or_defer_rules_simultaneous_actions(observed)
        self.resolve_rules_chain_sequences()
        if self.rules_engine.get("pendingChoice"):
            return observed
        actions = list(self.rules_engine.get("deferredSimultaneousActions") or [])
        self.rules_engine["deferredSimultaneousActions"] = []
        if actions:
            self.queue_rules_simultaneous_actions(actions)
        return actions

    def queue_rules_zone_entry_triggers(self, card_id, owner_id, container_id, zone,
                                        defer=False):
        return self.queue_rules_triggers(
            card_id, owner_id, "enters_zone", zone=zone, container_id=container_id,
            defer=defer,
        )

    def queue_rules_field_zone_entry_triggers(self, item, zone,
                                              event_targets=None,
                                              resume_confrontation_cleanup=False,
                                              defer=False):
        if not item or not item.get("faceUp"):
            return []
        if zone == "confrontation" and self.rules_engine.get("destroyNextEntries"):
            doomed = next((
                entry for entry in self.rules_engine["destroyNextEntries"]
                if entry.get("turn") == self.phase_tracker["turn"]
                and entry.get("controllerId") == self.rules_item_controller_id(item)
            ), None)
            if doomed is not None:
                self.rules_engine["destroyNextEntries"].remove(doomed)
                self._rules_remove_field_item_by_effect(
                    item, item.get("ownerId"), "graveyard", "top", reason="destroy"
                )
                self.prune_rules_ongoing_effects()
                return []
        return self.queue_rules_triggers(
            item.get("cardId"), item.get("ownerId"),
            "enters_field_zone",
            zone=zone,
            item_id=item.get("id"),
            face_up=True,
            controller_id=self.rules_item_controller_id(item),
            event_targets=event_targets,
            resume_confrontation_cleanup=resume_confrontation_cleanup,
            defer=defer,
        )

    def queue_rules_battlefield_entry_triggers(self, card_id, owner_id, item_id, face_up,
                                               target_player_id=None, event_targets=None,
                                               defer=False):
        item = self.find_battlefield_item(item_id)
        self.restore_rules_item_memories(item)
        return self.queue_rules_triggers(
            card_id, item.get("ownerId") if item else owner_id, "enters_field", item_id=item_id, face_up=face_up,
            controller_id=self.rules_item_controller_id(item) if item else owner_id,
            target_player_id=target_player_id, event_targets=event_targets,
            defer=defer,
        )

    def queue_rules_tribute_triggers(self, card_ids, owner_id,
                                     simultaneous_action_id=None,
                                     tribute_movements=None,
                                     defer_if_choice=False):
        queued = []
        movements_by_card = {
            movement.get("cardId"): movement
            for movement in (tribute_movements or [])
        }
        paid_action = next((
            action for action in self.rules_engine["actionStack"]
            if action.get("id") == simultaneous_action_id
        ), None) if simultaneous_action_id else None
        for card_id in card_ids or []:
            tribute_owner_id = movements_by_card.get(card_id, {}).get("ownerId") or owner_id
            queued.extend(self.queue_rules_triggers(
                card_id, tribute_owner_id, "used_as_tribute", container_id=tribute_owner_id,
                controller_id=owner_id,
                defer=True, related_action=paid_action,
                event_source_zone=(
                    "deck"
                    if movements_by_card.get(card_id, {}).get("destination") == "deck_bottom"
                    else movements_by_card.get(card_id, {}).get("destination")
                ),
            ))
            for source in list(self.battlefield):
                if not self.rules_item_effects_active(source):
                    continue
                queued.extend(self.queue_rules_triggers(
                    source.get("cardId"), source.get("ownerId"),
                    "manifestation_used_as_tribute",
                    item_id=source.get("id"),
                    face_up=True,
                    event_controller_id=owner_id,
                    defer=True,
                    controller_id=self.rules_item_controller_id(source),
                    related_action={
                        "id": simultaneous_action_id,
                        "source": {
                            "cardId": card_id,
                            "ownerId": owner_id,
                        },
                    },
                ))
        if (
            paid_action
            and paid_action.get("kind") == "play_card"
            and self.card_rules.get(
                (paid_action.get("source") or {}).get("cardId"), {}
            ).get("type") in RULES_WILL_TYPES
        ):
            for source in list(self.battlefield):
                if not self.rules_item_effects_active(source):
                    continue
                queued.extend(self.queue_rules_triggers(
                    source.get("cardId"), source.get("ownerId"),
                    "card_played",
                    event_card_id=(paid_action.get("source") or {}).get("cardId"),
                    item_id=source.get("id"),
                    face_up=True,
                    event_controller_id=owner_id,
                    defer=True,
                    controller_id=self.rules_item_controller_id(source),
                    related_action=paid_action,
                ))
            wills_seen = self.rules_engine.setdefault("willsPlayed", {})
            turn_key = int(self.phase_tracker.get("turn") or 0)
            if wills_seen.get("turn") != turn_key:
                wills_seen.clear()
                wills_seen["turn"] = turn_key
            first_will = not wills_seen.get(owner_id)
            wills_seen[owner_id] = int(wills_seen.get(owner_id) or 0) + 1
            for source in list(self.battlefield):
                if not self.rules_item_effects_active(source):
                    continue
                queued.extend(self.queue_rules_triggers(
                    source.get("cardId"), source.get("ownerId"),
                    "will_played",
                    first_will_of_turn=first_will,
                    item_id=source.get("id"),
                    face_up=True,
                    event_controller_id=owner_id,
                    defer=True,
                    controller_id=self.rules_item_controller_id(source),
                    related_action=paid_action,
                ))
        if simultaneous_action_id and queued:
            if paid_action is not None:
                self.rules_engine["actionStack"].remove(paid_action)
                self.queue_rules_simultaneous_actions(
                    [paid_action, *queued],
                    priority_player_id=owner_id,
                )
                return queued
        if queued:
            if defer_if_choice:
                # a Tribute paid inside a choice: its triggers wait for any choice still open
                self.queue_or_defer_rules_simultaneous_actions(queued)
            else:
                self.queue_rules_simultaneous_actions(queued)
        return queued

    def queue_rules_effect_support_entry(self, item, from_zone=None, *, enters_field=True):
        """A put enters the CZ; only a card arriving from outside also enters the field."""
        triggered = []
        if enters_field:
            triggered.extend(self.queue_rules_battlefield_entry_triggers(
                item["cardId"], item["ownerId"], item["id"], True, defer=True,
            ))
        triggered.extend(self.queue_rules_support_entry_triggers(
            item, played=False, from_zone=from_zone, defer=True,
        ))
        triggered.extend(self.queue_rules_field_zone_entry_triggers(
            item, "confrontation", defer=True,
        ))
        if enters_field:
            triggered.extend(self.queue_rules_manifestation_entry_watchers(
                item, played=False, defer=True,
            ))
        if triggered:
            self.queue_rules_simultaneous_actions(triggered)
        return triggered

    def queue_rules_support_entry_triggers(self, item, *, played=False, from_zone=None,
                                           event_targets=None, defer=False):
        """Queue public watcher effects after a Manifestation enters Support."""
        if not item or not item.get("isSupport") or not item.get("faceUp"):
            return []
        event_controller_id = item.get("controllerId") or item.get("ownerId")
        if event_controller_id not in self.players:
            return []
        self.rules_engine["supportEntries"].append({
            "turn": self.phase_tracker["turn"],
            "itemId": item.get("id"),
            "cardId": item.get("cardId"),
            "controllerId": event_controller_id,
            "fromZone": from_zone,
            "played": bool(played),
        })
        queued = []
        sources = sorted(
            self.battlefield,
            key=lambda source: (
                self.players.get(source.get("ownerId"), {}).get("seat", 0),
                self.battlefield.index(source),
            ),
        )
        for source in sources:
            if not source.get("faceUp"):
                continue
            queued.extend(self.queue_rules_triggers(
                source.get("cardId"), source.get("ownerId"), "enters_support",
                zone=self.rules_field_zone(source), item_id=source.get("id"), face_up=True,
                event_controller_id=event_controller_id, event_item_id=item.get("id"),
                played=played, event_targets=event_targets, defer=True,
                event_source_zone=from_zone,
                controller_id=self.rules_item_controller_id(source),
            ))
        if queued and not defer:
            self.queue_rules_simultaneous_actions(queued)
        return queued

    def apply_rules_entering_manifestation_replacements(self, item):
        """Asciugoth: an entering Manifestation pays out its Temperament, then turns Hollow."""
        if item.get("hollowAbsorbed"):
            return False
        for source in self.rules_active_passive_sources("entering_manifestation_becomes_hollow"):
            if source is item:
                continue
            absorbed = self.rules_manifestation_characteristics(item)["temperament"]
            if absorbed in RULES_TEMPERAMENTS:
                self.add_rules_excess_essence(
                    self.rules_item_controller_id(source),
                    [{"temperament": absorbed, "amount": 1}],
                )
            item["temperamentOverride"] = "hollow"
            item["hollowAbsorbed"] = True
            return True
        return False

    def queue_rules_manifestation_entry_watchers(self, item, defer=False, played=True):
        if (
            not item
            or not item.get("faceUp")
            or self.rules_item_card_rules(item).get("type") != "manifestation"
        ):
            return []
        event_controller_id = item.get("controllerId") or item.get("ownerId")
        self.apply_rules_entering_manifestation_replacements(item)
        queued = []
        for source in list(self.battlefield):
            if not source.get("faceUp"):
                continue
            queued.extend(self.queue_rules_triggers(
                source.get("cardId"), source.get("ownerId"),
                "manifestation_enters_field",
                zone=self.rules_field_zone(source),
                item_id=source.get("id"),
                event_controller_id=event_controller_id,
                event_item_id=item.get("id"),
                defer=True,
                controller_id=self.rules_item_controller_id(source),
            ))
            # a card "put" somewhere is moved, not played (Malaleuco into the Interzone)
            if played and self.rules_item_effects_active(source):
                queued.extend(self.queue_rules_triggers(
                    source.get("cardId"), source.get("ownerId"),
                    "card_played",
                    event_card_id=item.get("cardId"),
                    item_id=source.get("id"),
                    event_controller_id=event_controller_id,
                    event_item_id=item.get("id"),
                    defer=True,
                    controller_id=self.rules_item_controller_id(source),
                ))
        if queued and not defer:
            self.queue_rules_simultaneous_actions(queued)
        return queued

    def rules_add_source_counter(self, item_id, result):
        item = self.find_battlefield_item(item_id)
        if item is None:
            return False
        counter_name = str(result.get("counter") or "")
        if not counter_name:
            return False
        counters = item.setdefault("counters", {})
        counter_key = next((
            key for key in counters if str(key).casefold() == counter_name.casefold()
        ), counter_name)
        before = self.rules_field_power_snapshot()
        counters[counter_key] = max(0, int(counters.get(counter_key) or 0) + int(result.get("value") or 0))
        self.record_rules_power_changes(before)
        return True

    def queue_rules_persistent_will_entry_watchers(self, item, defer=False):
        if (
            not item
            or not item.get("faceUp")
            or item.get("isTokenCopy")
            or self.rules_item_card_rules(item).get("type")
            != "persistent_will"
        ):
            return []
        event_controller_id = self.rules_item_controller_id(item)
        queued = []
        for source in list(self.battlefield):
            if source is item or not self.rules_item_effects_active(source):
                continue
            queued.extend(self.queue_rules_triggers(
                source.get("cardId"), source.get("ownerId"),
                "persistent_will_enters_field",
                item_id=source.get("id"),
                face_up=True,
                event_controller_id=event_controller_id,
                defer=True,
                controller_id=self.rules_item_controller_id(source),
                related_action={
                    "source": {
                        "cardId": item.get("cardId"),
                        "ownerId": item.get("ownerId"),
                    },
                },
            ))
        if queued and not defer:
            self.queue_rules_simultaneous_actions(queued)
        return queued

    def queue_rules_beginning_turn_triggers(self, defer=False):
        """Queue public beginning-of-turn effects exactly once for this turn.

        Optional play permissions such as Wandering Veteran are deliberately
        not triggers and therefore do not belong in this scan.
        """
        turn = self.phase_tracker["turn"]
        if self.rules_engine["beginningTriggersTurn"] == turn:
            return []
        self.rules_engine["beginningTriggersTurn"] = turn
        queued = []
        items = sorted(
            self.battlefield,
            key=lambda item: (
                self.players.get(item.get("ownerId"), {}).get("seat", 0),
                int(item.get("confrontationEntrySequence") or 0),
                str(item.get("id") or ""),
            ),
        )
        for item in items:
            if not item.get("faceUp"):
                continue
            queued.extend(self.queue_rules_triggers(
                item.get("cardId"), item.get("ownerId"), "beginning_of_turn",
                zone=self.rules_field_zone(item), item_id=item.get("id"), face_up=True,
                defer=True,
                controller_id=self.rules_item_controller_id(item),
            ))
        for container_id, player in self.players.items():
            for card_id in list(player["zones"]["receptacle"]):
                queued.extend(self.queue_rules_triggers(
                    card_id,
                    self.card_owner_in_zone(
                        container_id, "receptacle", card_id
                    ),
                    "beginning_of_turn",
                    zone="receptacle",
                    container_id=container_id,
                    face_up=True,
                    defer=True,
                ))
        if queued and not defer:
            self.queue_rules_simultaneous_actions(queued)
        return queued

    def queue_rules_end_turn_memory_triggers(self, defer=False):
        turn = self.phase_tracker["turn"]
        queued = []
        registrations = [entry for entry in self.rules_engine.get("turnTributeReturns") or []
                         if entry.get("turn") == turn]
        self.rules_engine["turnTributeReturns"] = registrations
        for registration in registrations:
            for entry in self.rules_engine.get("tributeLog") or []:
                if entry.get("turn") != turn or entry.get("playerId") != registration.get("playerId"):
                    continue
                if any(memory.get("kind") == "return_from_limbo_end_turn"
                       and memory.get("createdTurn") == turn
                       and memory.get("ownerId") == entry.get("ownerId")
                       and memory.get("cardId") == entry.get("cardId")
                       and (memory.get("data") or {}).get("effectSourceCardId") == registration.get("sourceCardId")
                       for memory in self.rules_engine.get("effectMemories") or []):
                    continue
                self.create_rules_effect_memory(
                    entry["ownerId"], entry["cardId"], "return_from_limbo_end_turn",
                    controller_id=registration["playerId"],
                    source_action_id=registration.get("sourceActionId"),
                    data={"effectSourceCardId": registration.get("sourceCardId")},
                )
        for memory in list(self.rules_engine.get("effectMemories") or []):
            if memory.get("kind") != "return_from_limbo_end_turn":
                continue
            if self.rules_player_skips_end_phase(memory.get("controllerId") or memory.get("ownerId")):
                continue
            if int(memory.get("createdTurn") or 0) != turn:
                continue
            if int(memory.get("queuedTurn") or 0) == turn:
                continue
            if memory.get("cardId") not in self.players.get(memory.get("ownerId"), {}).get("zones", {}).get("graveyard", []):
                self.remove_rules_effect_memory(memory["id"])
                continue
            if (memory.get("data") or {}).get("requireLostConfrontation") and not self.rules_player_lost_confrontation_this_turn(memory.get("controllerId") or memory.get("ownerId")):
                self.remove_rules_effect_memory(memory["id"])
                continue
            memory["queuedTurn"] = turn
            # the delayed effect belongs to the card that created it (Coral Skull), not to the Will it returns
            shown_card_id = (
                (memory.get("data") or {}).get("effectSourceCardId")
                or memory.get("cardId")
            )
            queued.append({
                "id": new_id(),
                "controllerId": memory.get("controllerId") or memory.get("ownerId"),
                "label": (
                    f'{self.card_labels.get(shown_card_id, shown_card_id)}'
                    " — delayed effect"
                ),
                "kind": "triggered_effect",
                "optional": bool(
                    (memory.get("data") or {}).get("optional")
                ),
                "source": {
                    "cardId": shown_card_id,
                    "zone": "memory",
                    "ownerId": memory.get("ownerId"),
                    "cardType": self.card_rules.get(
                        memory.get("cardId"), {}
                    ).get("type"),
                },
                "target": None,
                "targets": [],
                "ability": {
                    "id": f'memory-{memory.get("kind")}',
                    "trigger": {"event": "end_of_turn"},
                    "result": {
                        "kind": "resolve_effect_memory",
                        "memoryId": memory["id"],
                    },
                    "ongoingEffect": None,
                    "targets": {},
                },
                "cost": {
                    "note": None, "tributeCardIds": [],
                    "tributeRequirements": {}, "essenceSpent": [],
                    "excessEssence": [], "tributeValidated": False,
                    "tributePaid": False, "sourceExhausted": False,
                    "sourceSacrificed": False, "sacrificedCards": [],
                },
                "phaseId": self.current_phase_id(),
                "turn": turn,
                "createdAt": time.time(),
            })
        if queued and not defer:
            self.queue_rules_simultaneous_actions(queued)
        return queued

    def queue_rules_resolution_memory_triggers(self, defer=False):
        turn = self.phase_tracker["turn"]
        queued = []
        # The delayed effect belongs to the card that created it (Dominate
        # the Aspects): one trigger per source, moving every card it marked.
        groups = {}
        for memory in list(self.rules_engine.get("effectMemories") or []):
            if memory.get("kind") != "move_to_deck_at_resolution":
                continue
            if int(memory.get("queuedTurn") or 0) == turn:
                continue
            if int(memory.get("createdTurn") or turn) < turn:
                # a return "at the Resolution" only concerns the turn it was
                # created in: never move a card a turn later
                self.remove_rules_effect_memory(memory["id"])
                continue
            memory["queuedTurn"] = turn
            data = memory.get("data") or {}
            source_card_id = data.get("sourceCardId")
            key = (
                (memory.get("sourceActionId"), source_card_id)
                if source_card_id else ("memory", memory["id"])
            )
            groups.setdefault(key, []).append(memory)
        for memories in groups.values():
            memory = memories[0]
            data = memory.get("data") or {}
            source_card_id = data.get("sourceCardId") or memory.get("cardId")
            source_owner_id = (
                data.get("sourceOwnerId") if data.get("sourceCardId")
                else memory.get("ownerId")
            ) or memory.get("ownerId")
            item_ids = [
                (entry.get("data") or {}).get("itemId") for entry in memories
            ]
            queued.append({
                "id": new_id(),
                "controllerId": memory.get("controllerId") or memory.get("ownerId"),
                "label": (
                    f'{self.card_labels.get(source_card_id, source_card_id)}'
                    " — delayed Resolution effect"
                ),
                "kind": "triggered_effect",
                "source": {
                    "cardId": source_card_id,
                    "zone": "memory",
                    "ownerId": source_owner_id,
                    "cardType": self.card_rules.get(
                        source_card_id, {}
                    ).get("type"),
                },
                "target": None,
                "targets": [
                    {
                        "kind": "card", "itemId": entry_item_id,
                        "cardId": entry.get("cardId"),
                    }
                    for entry, entry_item_id in zip(memories, item_ids)
                    if entry_item_id
                ],
                "ability": {
                    "id": "memory-move-to-deck-at-resolution",
                    "trigger": {"event": "at_resolution"},
                    "result": {
                        "kind": "resolve_effect_memory",
                        "memoryId": memory["id"],
                        "memoryIds": [entry["id"] for entry in memories],
                    },
                    "ongoingEffect": None,
                    "targets": None,
                },
                "cost": {
                    "note": None, "tributeCardIds": [],
                    "tributeRequirements": {}, "essenceSpent": [],
                    "excessEssence": [], "tributeValidated": False,
                    "tributePaid": False, "sourceExhausted": False,
                    "sourceSacrificed": False, "sacrificedCards": [],
                },
                "phaseId": self.current_phase_id(),
                "turn": turn,
                "createdAt": time.time(),
            })
        if queued and not defer:
            self.queue_rules_simultaneous_actions(queued)
        return queued

    def queue_rules_chain_outcome_triggers(self, item, event, player_id):
        # Granted outcome rules are memories: they survive a Hand/Limbo visit
        # and retain the controller of the effect which granted them. Several
        # separate Chains may have granted rules to the same physical card.
        memories = [] if item.get("isCopy") or item.get("isTokenCard") else [
            memory for memory in self.rules_effect_memories_for(
                item.get("ownerId"), item.get("cardId"), "chain_outcome_abilities"
            ) if (memory.get("data") or {}).get("itemId") == item.get("id")
        ]
        groups = [((memory.get("data") or {}).get("abilities") or [], memory.get("controllerId"))
                  for memory in memories] if memories else [
            (item.get("chainAbilities") or [], (item.get("chainSource") or {}).get("controllerId")
             or self.rules_item_controller_id(item))
        ]
        queued = []
        for granted, controller_id in groups:
            abilities = [ability for ability in granted
                         if (ability.get("trigger") or {}).get("event") == event]
            if abilities:
                queued.extend(self.queue_rules_triggers(
                    item.get("cardId"), item.get("ownerId"), event,
                    item_id=item.get("id"), face_up=True,
                    event_controller_id=player_id, defer=True,
                    controller_id=controller_id, abilities_override=abilities,
                ))
        return queued

    def queue_rules_confrontation_win_triggers(self, defer=False):
        result = self.rules_engine.get("confrontationResult") or {}
        winner_id = result.get("winnerId")
        if winner_id not in self.players and result.get("stalemate"):
            stalemate_queued = []
            for item in list(self.battlefield):
                if not self.rules_item_effects_active(item):
                    continue
                stalemate_queued.extend(self.queue_rules_triggers(
                    item.get("cardId"), item.get("ownerId"), "confrontation_stalemate",
                    item_id=item.get("id"), face_up=True, defer=True,
                    event_controller_id=self.rules_item_controller_id(item),
                    controller_id=self.rules_item_controller_id(item),
                ))
            if stalemate_queued and not defer:
                self.queue_rules_simultaneous_actions(stalemate_queued)
            return stalemate_queued
        if winner_id not in self.players:
            return []
        participant_ids = set(result.get("participantItemIds") or [])
        queued = []
        for item in list(self.battlefield):
            if (
                item.get("id") not in participant_ids
                or self.rules_item_controller_id(item) != winner_id
                or not self.rules_item_effects_active(item)
            ):
                continue
            queued.extend(self.queue_rules_triggers(
                item.get("cardId"), item.get("ownerId"),
                "wins_confrontation",
                item_id=item.get("id"),
                face_up=True,
                event_controller_id=winner_id,
                defer=True,
                controller_id=self.rules_item_controller_id(item),
            ))
            queued.extend(self.queue_rules_chain_outcome_triggers(
                item, "wins_confrontation", winner_id
            ))
        loser_id = result.get("loserId")
        if loser_id in self.players:
            for item in list(self.battlefield):
                if (
                    item.get("id") not in participant_ids
                    or self.rules_item_controller_id(item) != loser_id
                    or not self.rules_item_effects_active(item)
                ):
                    continue
                queued.extend(self.queue_rules_triggers(
                    item.get("cardId"), item.get("ownerId"),
                    "loses_confrontation",
                    item_id=item.get("id"),
                    face_up=True,
                    event_controller_id=loser_id,
                    defer=True,
                    controller_id=self.rules_item_controller_id(item),
                ))
                queued.extend(self.queue_rules_chain_outcome_triggers(
                    item, "loses_confrontation", loser_id
                ))
        for player_event, player_id in (
            ("player_wins_confrontation", winner_id),
            ("player_loses_confrontation", loser_id),
        ):
            if player_id not in self.players:
                continue
            for item in list(self.battlefield):
                if not self.rules_item_effects_active(item):
                    continue
                queued.extend(self.queue_rules_triggers(
                    item.get("cardId"), item.get("ownerId"), player_event,
                    item_id=item.get("id"),
                    face_up=True,
                    event_controller_id=player_id,
                    defer=True,
                    controller_id=self.rules_item_controller_id(item),
                ))
        if queued and not defer:
            self.queue_rules_simultaneous_actions(queued)
        return queued

    def queue_rules_revelation_triggers(self, defer=False):
        queued = []
        for container_id, container in self.players.items():
            for card_id in list(container["zones"]["receptacle"]):
                queued.extend(self.queue_rules_triggers(
                    card_id, self.card_owner_in_zone(container_id, "receptacle", card_id),
                    "vessel_revelation", zone="receptacle", container_id=container_id,
                    face_up=True, defer=True,
                ))
        for item in list(self.battlefield):
            if not self.rules_item_effects_active(item):
                continue
            queued.extend(self.queue_rules_triggers(
                item.get("cardId"), item.get("ownerId"),
                "revelation",
                item_id=item.get("id"),
                face_up=True,
                event_controller_id=self.rules_item_controller_id(item),
                defer=True,
                controller_id=self.rules_item_controller_id(item),
            ))
        if queued and not defer:
            self.queue_rules_simultaneous_actions(queued)
        return queued

    def queue_rules_reaction_triggers(self):
        queued = []
        for item in list(self.battlefield):
            if self.rules_item_effects_active(item):
                queued.extend(self.queue_rules_triggers(
                    item.get("cardId"), item.get("ownerId"), "reaction",
                    item_id=item.get("id"), face_up=True,
                    controller_id=self.rules_item_controller_id(item), defer=True,
                ))
        if queued:
            self.queue_rules_simultaneous_actions(queued)
        return queued

    def queue_rules_before_revelation_triggers(self, defer=False):
        queued = []
        for item in list(self.battlefield):
            if not self.rules_item_effects_active(item):
                continue
            controller_id = self.rules_item_controller_id(item)
            queued.extend(self.queue_rules_triggers(
                item.get("cardId"), item.get("ownerId"),
                "before_revelation",
                item_id=item.get("id"),
                face_up=True,
                target_player_id=self.other_rules_player_id(controller_id),
                defer=True,
                controller_id=controller_id,
            ))
        if queued and not defer:
            self.queue_rules_simultaneous_actions(queued)
        return queued

    def queue_rules_resolution_field_triggers(self, defer=False):
        queued = []
        for item in list(self.battlefield):
            if not self.rules_item_effects_active(item):
                continue
            controller_id = self.rules_item_controller_id(item)
            queued.extend(self.queue_rules_triggers(
                item.get("cardId"), item.get("ownerId"),
                "resolution",
                item_id=item.get("id"),
                face_up=True,
                defer=True,
                controller_id=controller_id,
            ))
        if queued and not defer:
            self.queue_rules_simultaneous_actions(queued)
        return queued

    def build_rules_end_turn_field_triggers(self):
        queued = []
        for item in list(self.battlefield):
            if not self.rules_item_effects_active(item):
                continue
            queued.extend(self.queue_rules_triggers(
                item.get("cardId"), item.get("ownerId"),
                "end_of_turn",
                zone=self.rules_field_zone(item),
                item_id=item.get("id"),
                face_up=True,
                defer=True,
                controller_id=self.rules_item_controller_id(item),
            ))
        return queued

    def grant_rules_beginning_turn_permissions(self):
        """Snapshot conditional play rights without moving or revealing cards.

        Wandering Veteran is not a triggered effect: being in Limbo when the
        turn begins grants a permission for that turn.  The card itself stays
        in Limbo until its owner uses that permission during a confrontation.
        """
        turn = self.phase_tracker["turn"]
        if self.rules_engine["beginningPermissionsTurn"] == turn:
            return list(self.rules_engine["playPermissions"])
        self.rules_engine["beginningPermissionsTurn"] = turn
        self.rules_engine["playPermissions"] = []
        for player in sorted(self.players.values(), key=lambda entry: entry.get("seat", 0)):
            player_id = player["id"]
            for card_id in player["zones"]["graveyard"]:
                for ability in self.card_rules.get(card_id, {}).get("playPermissions") or []:
                    permission = ability.get("playPermission") or {}
                    if (
                        permission.get("conditionEvent") != "beginning_of_turn"
                        or permission.get("requiredZone") != "graveyard"
                        or permission.get("playFromZone") != "graveyard"
                    ):
                        continue
                    self.rules_engine["playPermissions"].append({
                        "id": new_id(),
                        "abilityId": str(ability.get("id") or "")[:80],
                        "playerId": player_id,
                        "cardId": card_id,
                        "fromZone": "graveyard",
                        "phaseIds": [
                            phase_id for phase_id in permission.get("phaseIds") or []
                            if phase_id in ADVANCED_PHASES
                        ],
                        "asSupport": bool(permission.get("asSupport")),
                        "temperamentOverride": (
                            permission.get("temperamentOverride")
                            if permission.get("temperamentOverride") in RULES_TEMPERAMENTS else None
                        ),
                        "winAsSupportDestination": (
                            "exile" if permission.get("winAsSupportDestination") == "exile" else None
                        ),
                        "turn": turn,
                    })
        return list(self.rules_engine["playPermissions"])

    def rules_zone_play_permission(self, player_id, container_id, zone, card_id):
        """Validate and return a card's current conditional zone-play right."""
        definitions = self.card_rules.get(card_id, {}).get("playPermissions") or []
        relevant = [
            ability for ability in definitions
            if (ability.get("playPermission") or {}).get("playFromZone") == zone
        ]
        if not self.rules_engine["enabled"] or not relevant:
            return None, None
        permission = next((
            entry for entry in self.rules_engine.get("playPermissions") or []
            if entry.get("playerId") == player_id
            and entry.get("cardId") == card_id
            and entry.get("fromZone") == zone
            and entry.get("turn") == self.phase_tracker["turn"]
        ), None)
        if container_id != player_id or permission is None:
            return "This card did not meet its beginning-of-turn play condition.", None
        if card_id not in self.players[player_id]["zones"].get(zone, []):
            return "This card is no longer in its required zone.", None
        if self.current_phase_id() not in permission.get("phaseIds", []):
            return "This card can only be played in Support during a confrontation.", None
        if self.rules_engine.get("priorityPlayerId") != player_id:
            return "You do not have priority.", None
        return None, permission

    def consume_rules_zone_play_permission(self, permission_id):
        self.rules_engine["playPermissions"] = [
            entry for entry in self.rules_engine.get("playPermissions") or []
            if entry.get("id") != permission_id
        ]

    def _set_next_rules_recovery_choice(self, player_ids, action):
        if not player_ids:
            self.rules_engine["pendingChoice"] = None
            return None
        player_id = player_ids[0]
        available_options = ["lose_points_10"]
        if len(self.players[player_id]["zones"]["deck"]) >= 3:
            available_options.insert(0, "discard_deck_bottom_3")
        choice = {
            "id": new_id(),
            "kind": "recovery_shared_choice",
            "playerId": player_id,
            "options": available_options,
            "remainingPlayerIds": list(player_ids[1:]),
            "actionId": action.get("id"),
            "controllerId": action.get("controllerId"),
            "sourceCardId": (action.get("source") or {}).get("cardId"),
        }
        self.rules_engine["pendingChoice"] = choice
        return choice
