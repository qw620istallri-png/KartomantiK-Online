"""Chaining Manifestations, drawing, token copies and Support returns."""

import random
import time

from .common import RULES_TEMPERAMENTS, new_id


class ChainMixin:
    def rules_action_target_rules(self, action):
        """Return the encoded target contract for a public Stack action."""
        action_groups = (action.get("ability") or {}).get("targetGroups")
        if isinstance(action_groups, list) and action_groups:
            return {"groups": [
                {
                    key: list(value) if isinstance(value, list) else value
                    for key, value in group.items()
                }
                for group in action_groups
            ]}
        action_targets = (action.get("ability") or {}).get("targets")
        if isinstance(action_targets, dict):
            return {
                key: list(value) if isinstance(value, list) else value
                for key, value in action_targets.items()
            }
        source = action.get("source") or {}
        ability_id = (action.get("ability") or {}).get("id")
        if not source.get("cardId") or not ability_id:
            return None
        ability_group = "playedAbilities" if action.get("kind") == "play_card" else "activatedAbilities"
        ability = next((
            entry for entry in self.card_rules.get(source["cardId"], {}).get(ability_group) or []
            if entry.get("id") == ability_id
        ), None)
        target_rules = (ability or {}).get("targets")
        if not isinstance(target_rules, dict):
            return None
        allowed_keys = {
            "kind", "min", "max", "cardType", "cardTypes", "zones", "controller",
            "fieldZone", "supportOnly", "exhaustedOnly", "maxPoints", "maxPower", "excludeEventSource", "excludeSource",
            "sourceOnly", "fieldZonesByType", "enteredThisTurn", "enteredInterzoneThisTurn", "confrontationOutcome",
            "owner", "firstManifestationOnly", "counter", "minCounters",
        }
        return {
            key: list(value) if isinstance(value, list) else value
            for key, value in target_rules.items() if key in allowed_keys
        }

    @staticmethod
    def build_rules_stack_copy(target_action, controller_id, copying_action_id):
        """Create a cost-free Stack object that copies an existing Will's effect."""
        return {
            "id": new_id(),
            "controllerId": controller_id,
            "label": target_action.get("label") or "Copied Will",
            "kind": target_action.get("kind"),
            "source": dict(target_action.get("source") or {}),
            "target": target_action.get("target"),
            "targets": [dict(entry) for entry in target_action.get("targets") or []],
            "ability": dict(target_action.get("ability") or {}),
            "cost": {
                "note": None, "tributeCardIds": [], "tributeRequirements": {},
                "essenceSpent": [], "excessEssence": [], "tributeValidated": True,
                "tributePaid": False, "sourceExhausted": False,
                "sourceSacrificed": False, "sacrificedCards": [],
            },
            "phaseId": target_action.get("phaseId"),
            "turn": target_action.get("turn"),
            "createdAt": time.time(),
            "isStackCopy": True,
            "copiedFromActionId": target_action.get("id"),
            "copyingActionId": copying_action_id,
        }

    def chain_rules_manifestation(self, player_id, zone, card_id, *,
                                  placement=None, win_destination=None,
                                  action_id=None, source_card_id=None,
                                  shuffle_after=False, after_chain=None,
                                  chain_abilities=None, chain_controller_id=None,
                                  action_targets=None, container_id=None,
                                  return_to_vessel=False):
        container_id = container_id if container_id in self.players else player_id
        if card_id not in self.players[container_id]["zones"].get(zone, []):
            return "The selected Manifestation is no longer in the required zone.", None
        if self.card_rules.get(card_id, {}).get("type") != "manifestation":
            return "Only a Manifestation can be Chained.", None
        restriction_error = self.rules_card_play_restriction_error(
            player_id, card_id
        )
        if restriction_error:
            return restriction_error, None
        suspension_source = (
            self.rules_active_suspension_source(zone)
            if zone in {"deck", "graveyard"} else None
        )
        if suspension_source:
            error, suspended = self.suspend_zone_card(
                container_id, zone, card_id,
                source_effect_id=suspension_source.get("id"),
            )
            return error, {
                "kind": "chain_manifestation",
                "status": "suspended",
                "playerId": player_id,
                "fromZone": zone,
                "cardId": card_id,
                "sourceCardId": source_card_id,
                "suspensionId": suspended.get("id") if suspended else None,
            }
        owner_id = self.take_zone_card(container_id, zone, card_id)
        if owner_id is None:
            return "The selected Manifestation is no longer in the required zone.", None
        position = self.clean_rules_board_position(placement)
        item = {
            "id": new_id(), "ownerId": owner_id, "controllerId": player_id,
            "cardId": card_id, "x": position["x"], "y": position["y"],
            "faceUp": True, "rotation": 0.0, "counters": {},
            "rarity": (self.players.get(owner_id) or {}).get(
                "cardRarities", {}
            ).get(card_id),
            "stackedOn": None, "isChained": True,
        }
        if return_to_vessel and zone == "receptacle":
            item["returnToVesselId"] = container_id
        self.mark_rules_support_entry(item)
        if win_destination == "opponent_receptacle":
            item["supportWinDestination"] = "opponent_receptacle"
        if chain_abilities:
            item["chainAbilities"] = [dict(entry) for entry in chain_abilities]
            item["chainSource"] = {
                "cardId": source_card_id,
                "controllerId": chain_controller_id or player_id,
            }
        self.battlefield.append(item)
        memory = None
        if win_destination == "exile":
            memory = self.create_rules_effect_memory(
                owner_id, card_id, "win_destination_exile",
                controller_id=player_id,
                source_action_id=action_id,
                data={"itemId": item["id"]},
            )
        if shuffle_after:
            random.shuffle(self.players[player_id]["zones"]["deck"])
        triggered_actions = self.queue_rules_battlefield_entry_triggers(
            card_id, player_id, item["id"], True, defer=True,
        )
        triggered_actions.extend(self.queue_rules_support_entry_triggers(
            item, played=True, from_zone=zone, defer=True,
        ))
        triggered_actions.extend(self.queue_rules_field_zone_entry_triggers(
            item, "confrontation", defer=True,
        ))
        triggered_actions.extend(
            self.queue_rules_manifestation_entry_watchers(item, defer=True)
        )
        after_result = None
        pending_pick = None
        if isinstance(after_chain, dict):
            base_power = int(self.card_rules.get(card_id, {}).get("power") or 0)
            if after_chain.get("kind") == "discard_deck_per_base_power":
                discarder_id = chain_controller_id or player_id
                discarded = []
                deck = self.players[discarder_id]["zones"]["deck"]
                for _index in range(min(base_power, len(deck))):
                    top_card = deck[0]
                    move_error, _owner, replacement = self.move_zone_card_by_effect(
                        discarder_id, "deck", discarder_id, "graveyard",
                        top_card, "top",
                    )
                    if move_error:
                        break
                    if not replacement:
                        discarded.append(top_card)
                after_result = {
                    "kind": "discard_deck", "playerId": discarder_id,
                    "count": len(discarded), "cardIds": discarded,
                }
            elif after_chain.get("kind") == "look_top_pick_hand":
                chain_player_id = chain_controller_id or player_id
                card_ids = list(
                    self.players[chain_player_id]["zones"]["deck"][:base_power]
                )
                if card_ids:
                    groups = [{
                        "playerId": chain_player_id, "cardIds": card_ids,
                        "topCount": None, "bottomCount": None,
                        "extraSide": "hand", "extraMin": 1, "extraMax": 1,
                    }]
                    pending_pick = {
                        "id": new_id(), "kind": "deck_reorder",
                        "playerId": chain_player_id,
                        "sourceCardId": source_card_id,
                        "groups": groups, "_groups": groups,
                    }
                    after_result = {
                        "kind": "look_top_pick_hand", "playerId": chain_player_id,
                        "count": len(card_ids),
                    }
            elif after_chain.get("kind") == "reveal_top_opponent_suspend":
                chain_player_id = chain_controller_id or player_id
                victims = [pid for pid in self.players if pid != chain_player_id]
                if victims and base_power > 0:
                    victim_id = victims[0]
                    revealed = list(self.players[victim_id]["zones"]["deck"][:base_power])
                    if revealed:
                        pending_pick = self.make_bloatuba_choice(
                            chain_player_id, victim_id, revealed, source_card_id,
                        )
                        after_result = {
                            "kind": "reveal_top_opponent_suspend", "playerId": victim_id,
                            "cardIds": revealed,
                        }
            elif after_chain.get("kind") == "boost_controller_first":
                boost_player_id = chain_controller_id or player_id
                first_item = self.find_battlefield_item(
                    (self.rules_engine.get("firstManifestationItemIds") or {}).get(
                        boost_player_id
                    )
                )
                boost = int(after_chain.get("value") or 0)
                if first_item is not None and boost:
                    self.rules_engine["ongoingEffects"].append({
                        "id": new_id(), "actionId": action_id,
                        "abilityId": "chain-controller-boost",
                        "controllerId": boost_player_id,
                        "source": {"cardId": source_card_id},
                        "target": {
                            "kind": "card", "itemId": first_item["id"],
                            "cardId": first_item.get("cardId"),
                            "ownerId": first_item.get("ownerId"),
                        },
                        "kind": "power_modifier", "value": boost,
                        "duration": "until_end_of_turn",
                        "startedTurn": self.phase_tracker["turn"],
                    })
                    after_result = {
                        "kind": "power_modifier", "itemId": first_item["id"],
                        "value": boost,
                    }
            elif after_chain.get("kind") == "power_counter_target_per_base_power":
                target = next((
                    entry for entry in action_targets or []
                    if entry.get("kind") == "card"
                ), None)
                target_item = self.find_battlefield_item(
                    (target or {}).get("itemId")
                )
                if target_item is not None:
                    counters = target_item.setdefault("counters", {})
                    counters["power"] = int(counters.get("power") or 0) + base_power
                    after_result = {
                        "kind": "power_counter", "itemId": target_item["id"],
                        "value": base_power,
                    }
        if triggered_actions:
            self.queue_rules_simultaneous_actions(triggered_actions)
        if pending_pick is not None and not self.rules_engine.get("pendingChoice"):
            self.rules_engine["pendingChoice"] = pending_pick
        return None, {
            "kind": "chain_manifestation", "status": "chained",
            "playerId": player_id, "fromZone": zone,
            "cardId": card_id, "itemId": item["id"],
            "afterChain": after_result,
            "sourceCardId": source_card_id,
            "memoryId": memory.get("id") if memory else None,
            "shuffled": bool(shuffle_after),
            "x": item["x"], "y": item["y"],
            "triggeredActions": triggered_actions,
        }

    def rules_draw_locked(self, player_id):
        return (
            self.current_phase_group() != "recovery"
            and any(
                entry.get("playerId") == player_id
                and entry.get("turn") == self.phase_tracker["turn"]
                for entry in self.rules_engine.get("drawLocks") or []
            )
        )

    def draw_rules_cards(self, player_id, count):
        drawn = []
        player = self.players[player_id]
        if self.rules_draw_locked(player_id):
            return drawn
        for _index in range(min(max(0, int(count)), len(player["zones"]["deck"]))):
            card_id = player["zones"]["deck"][0]
            error, _owner_id, replacement = self.move_zone_card_by_effect(
                player_id, "deck", player_id, "hand", card_id, "bottom"
            )
            if error:
                break
            if not replacement:
                drawn.append(card_id)
        return drawn

    def rules_hand_limit(self, player_id, default_limit=7):
        limit = max(0, int(default_limit))
        for source in self.rules_active_passive_sources("hand_limit_all"):
            passive = next((
                entry for entry in self.card_rules.get(
                    source.get("cardId"), {}
                ).get("passiveEffects") or []
                if entry.get("kind") == "hand_limit_all"
            ), None)
            if passive:
                limit = min(limit, max(0, int(passive.get("value") or limit)))
        for effect in self.rules_engine.get("handLimitEffects") or []:
            if (
                effect.get("playerId") != player_id
                or int(effect.get("turn") or 0) != self.phase_tracker["turn"]
            ):
                continue
            if effect.get("limit") is not None:
                limit = min(limit, max(0, int(effect["limit"])))
            limit = max(0, limit + int(effect.get("delta") or 0))
        return limit

    def rules_hand_overflow_destination(self, player_id):
        if self.rules_active_passive_sources("hand_limit_all"):
            return "deck_bottom"
        matching = [
            effect for effect in self.rules_engine.get("handLimitEffects") or []
            if effect.get("playerId") == player_id
            and int(effect.get("turn") or 0) == self.phase_tracker["turn"]
        ]
        return (
            matching[-1].get("overflowDestination", "deck_bottom")
            if matching else "deck_bottom"
        )

    def set_rules_hand_overflow_choice(self, player_ids):
        remaining = [
            current_id for current_id in player_ids
            if current_id in self.players
            and len(self.players[current_id]["zones"]["hand"])
            > self.rules_hand_limit(current_id)
        ]
        if not remaining:
            self.rules_engine["pendingChoice"] = None
            return None
        current_id = remaining[0]
        count = (
            len(self.players[current_id]["zones"]["hand"])
            - self.rules_hand_limit(current_id)
        )
        choice = {
            "id": new_id(),
            "kind": "hand_overflow",
            "playerId": current_id,
            "count": count,
            "destination": self.rules_hand_overflow_destination(current_id),
            "remainingPlayerIds": remaining[1:],
        }
        self.rules_engine["pendingChoice"] = choice
        return choice

    def request_rules_draw(self, player_id, count, source_controller_id=None):
        requested = max(0, min(int(count), 50))
        replacement_source = next((
            source for source in self.rules_active_passive_sources(
                "replace_opponent_nonrecovery_draw"
            )
            if self.rules_item_controller_id(source) != player_id
        ), None)
        if (
            replacement_source
            and self.current_phase_group() != "recovery"
            and requested > 0
        ):
            card_ids = list(
                self.players[player_id]["zones"]["deck"][:requested]
            )
            discard_count = (len(card_ids) + 1) // 2
            if card_ids:
                choice_id = new_id()
                self.rules_engine["pendingChoice"] = {
                    "id": choice_id,
                    "kind": "draw_replacement",
                    "playerId": player_id,
                    "sourceCardId": replacement_source.get("cardId"),
                    "sourceControllerId": self.rules_item_controller_id(
                        replacement_source
                    ),
                    "sourceItemId": replacement_source.get("id"),
                    "cardIds": card_ids,
                    "count": discard_count,
                    "_cardIds": card_ids,
                }
                return {
                    "kind": "choice_required",
                    "choiceId": choice_id,
                    "choiceKind": "draw_replacement",
                    "playerId": player_id,
                    "count": discard_count,
                }
        drawn = self.draw_rules_cards(player_id, requested)
        return {
            "kind": "draw",
            "playerId": player_id,
            "count": len(drawn),
        }

    def create_rules_token_copy(self, card_id, controller_id, *,
                                source_item_id=None, hollow=False,
                                effects_disabled=False, generic_power=None,
                                generic_temperament=None, field_zone=None):
        metadata = self.card_rules.get(card_id, {})
        seat = self.players[controller_id].get("seat")
        item = {
            "id": new_id(),
            "ownerId": controller_id,
            "controllerId": controller_id,
            "cardId": card_id,
            "x": 740.0,
            "y": 800.0 if seat != 1 else 525.0,
            "faceUp": True,
            "rotation": 0.0,
            "counters": {},
            "stackedOn": None,
            "createdByItemId": source_item_id,
        }
        if metadata.get("type") == "persistent_will":
            item["fieldZone"] = "field"
        else:
            # a token entering is the latest Confrontation entry (Unpredictable Loudmouth)
            self.mark_rules_confrontation_entry(item)
            item["isSupport"] = True
        if generic_power is not None:
            item.update({
                "isTokenCard": True,
                "power": max(0, int(generic_power)),
                "temperament": generic_temperament if generic_temperament in RULES_TEMPERAMENTS else "hollow" if hollow else (
                    next(iter(metadata.get("temperaments") or []), "hollow")
                ),
            })
        else:
            item["isCopy"] = True
            item["isTokenCopy"] = True
            if hollow:
                item["temperamentOverride"] = "hollow"
        if effects_disabled:
            item["effectsDisabled"] = True
        if field_zone == "interzone":
            item["fieldZone"] = "interzone"
        elif item.get("isSupport"):
            self.mark_rules_support_entry(item)
        if item.get("isTokenCard") or metadata.get("type") == "manifestation":
            self.apply_rules_entering_manifestation_replacements(item)
        self.battlefield.append(item)
        return item

    def queue_rules_token_copy_entry_triggers(self, copy):
        """A token copy of a real card enters the battlefield like the card
        itself: its "enters the field" effects trigger."""
        if (
            copy is None or copy.get("isTokenCard") or copy.get("effectsDisabled")
            or not self.rules_engine["enabled"]
        ):
            return []
        triggered = self.queue_rules_battlefield_entry_triggers(
            copy["cardId"], copy["ownerId"], copy["id"], True, defer=True,
        )
        triggered.extend(self.queue_rules_support_entry_triggers(
            copy, played=False, defer=True,
        ))
        triggered.extend(self.queue_rules_field_zone_entry_triggers(
            copy, self.rules_field_zone(copy) or "confrontation", defer=True,
        ))
        if triggered:
            self.queue_rules_simultaneous_actions(triggered)
        return triggered

    def _finish_rules_support_returns(self, counts, action):
        effects = []
        for controller_id, count in counts.items():
            first_item = self.find_battlefield_item(
                self.rules_engine.get("firstManifestationItemIds", {}).get(
                    controller_id
                )
            )
            if first_item is None or count <= 0:
                continue
            effect = {
                "id": new_id(),
                "actionId": action.get("id"),
                "abilityId": (
                    (action.get("ability") or {}).get("id")
                ),
                "controllerId": action.get("controllerId"),
                "source": dict(action.get("source") or {}),
                "target": {
                    "kind": "card", "itemId": first_item.get("id"),
                    "cardId": first_item.get("cardId"),
                    "ownerId": first_item.get("ownerId"),
                },
                "kind": "power_modifier",
                "duration": "until_end_of_turn",
                "startedTurn": self.phase_tracker["turn"],
                "value": count,
            }
            self.rules_engine["ongoingEffects"].append(effect)
            effects.append(effect)
        return effects

    def _continue_rules_support_return_groups(self, groups, counts, action):
        groups = [dict(group) for group in groups if group.get("itemIds")]
        while groups:
            group = groups.pop(0)
            items = [
                self.find_battlefield_item(item_id)
                for item_id in group.get("itemIds") or []
            ]
            items = [item for item in items if item is not None and item.get("isSupport")]
            if len(items) <= 1:
                for item in items:
                    controller_id = self.rules_item_controller_id(item)
                    self._rules_remove_field_item(
                        item, item.get("ownerId"), "deck", "top"
                    )
                    counts[controller_id] = counts.get(controller_id, 0) + 1
                continue
            choice = {
                "id": new_id(),
                "kind": "support_return_order",
                "playerId": group.get("controllerId"),
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "items": [{
                    "itemId": item.get("id"),
                    "cardId": item.get("cardId"),
                    "ownerId": item.get("ownerId"),
                } for item in items],
                "_remainingGroups": groups,
                "_counts": counts,
                "_action": action,
            }
            self.rules_engine["pendingChoice"] = choice
            self.rules_engine["priorityPasses"] = []
            self.rules_engine["priorityPlayerId"] = choice["playerId"]
            return choice
        effects = self._finish_rules_support_returns(counts, action)
        self.rules_engine["pendingChoice"] = None
        return {
            "kind": "support_returns_completed",
            "counts": dict(counts),
            "ongoingEffectIds": [effect["id"] for effect in effects],
        }

    def begin_rules_chain_sequence(self, controller_id, chain_players, result, action):
        """Offer the Chain choice to each listed player, one after the other."""
        zone = result.get("zone")
        ready = []
        proofs = []
        for chain_player_id in chain_players:
            member = self.players.get(chain_player_id)
            if member is None:
                continue
            if result.get("preMove") == "first_manifestation_to_deck_bottom":
                first = self.find_battlefield_item(
                    (self.rules_engine.get("firstManifestationItemIds") or {}).get(
                        chain_player_id
                    )
                )
                if first is not None:
                    self._rules_remove_field_item(
                        first, first.get("ownerId"), "deck", "bottom"
                    )
            eligible = list(self.rules_chain_candidates(chain_player_id, zone))
            if eligible:
                ready.append(chain_player_id)
            else:
                proofs.append(chain_player_id)
        forced = [
            pid for pid in proofs
            if zone == "hand" and (
                pid != controller_id
                or not (
                    result.get("optional") and not action.get("optionalAccepted")
                )
            )
        ]
        proof_payload = {}
        if forced:
            proof_payload = {
                "handProof": list(self.players[forced[0]]["zones"]["hand"]),
                "handProofPlayerId": forced[0],
                "handProofs": [
                    {
                        "playerId": pid,
                        "cardIds": list(self.players[pid]["zones"]["hand"]),
                    }
                    for pid in forced
                ],
            }
        if not ready:
            return {
                "kind": "chain_manifestation", "status": "no_eligible_card",
                "playerId": chain_players[0] if chain_players else controller_id,
                "fromZone": zone,
                **proof_payload,
            }
        first_player_id = ready[0]
        choice = self.make_rules_chain_choice(
            first_player_id, controller_id, result, action,
            next_players=ready[1:],
        )
        self.rules_engine["pendingChoice"] = choice
        payload = {
            "kind": "choice_required", "choiceId": choice["id"],
            "choiceKind": "chain_manifestation", "playerId": first_player_id,
            "fromZone": zone, "optional": choice["optional"],
        }
        payload.update(proof_payload)
        return payload

    def make_bloatuba_choice(self, controller_id, victim_id, revealed, source_card_id):
        """Opponent picks a revealed Manifestation to suspend, else the controller orders."""
        picks = [c for c in revealed if self.card_rules.get(c, {}).get("type") == "manifestation"]
        if picks:
            return {
                "id": new_id(), "kind": "reveal_hand_discard", "purpose": "bloatuba",
                "playerId": victim_id, "targetPlayerId": victim_id,
                "cardIds": picks, "_revealed": list(revealed),
                "controllerId": controller_id, "sourceCardId": source_card_id,
            }
        return self.make_bloatuba_reorder(controller_id, victim_id, revealed, source_card_id)

    def make_bloatuba_reorder(self, controller_id, victim_id, remaining, source_card_id):
        group = {
            "playerId": victim_id, "cardIds": list(remaining),
            "topCount": 0, "bottomCount": len(remaining),
        }
        return {
            "id": new_id(), "kind": "deck_reorder", "playerId": controller_id,
            "sourceCardId": source_card_id, "groups": [group], "_groups": [group],
        }

    def rules_item_becomes_first_manifestation(self, item, player_id):
        """Gummo / The Slumberer: enters the Confrontation Zone as First Manifestation."""
        first_ids = self.rules_engine["firstManifestationItemIds"]
        if player_id in first_ids or self.rules_engine.get("firstManifestationComplete"):
            return False
        self.mark_rules_confrontation_entry(item)
        self._mark_rules_persisted_first(item, player_id)
        validated = self.rules_engine.setdefault("firstManifestationValidatedPlayerIds", [])
        if player_id not in validated:
            validated.append(player_id)
        return True

    def place_rules_hand_card_in_support(self, player_id, card_id):
        """Play a Manifestation from hand into Support by an effect (queues its entry triggers)."""
        owner_id = self.take_zone_card(player_id, "hand", card_id)
        if owner_id is None:
            return None
        seat = self.players[player_id].get("seat")
        item = {
            "id": new_id(), "ownerId": owner_id, "controllerId": player_id,
            "cardId": card_id, "x": 740.0, "y": 800.0 if seat != 1 else 525.0,
            "faceUp": True, "rotation": 0.0, "counters": {}, "stackedOn": None,
            "rarity": self.players[owner_id].get("cardRarities", {}).get(card_id),
        }
        self.mark_rules_support_entry(item)
        self.battlefield.append(item)
        triggered = self.queue_rules_battlefield_entry_triggers(card_id, owner_id, item["id"], True, defer=True)
        triggered.extend(self.queue_rules_field_zone_entry_triggers(item, "confrontation", defer=True))
        triggered.extend(self.queue_rules_manifestation_entry_watchers(item, defer=True))
        if triggered:
            self.queue_rules_simultaneous_actions(triggered)
        return item

    def place_rules_card_in_interzone(self, player_id, container_id, zone, card_id):
        """Put a card from a player zone into player_id's Interzone (shared slot when full)."""
        owner_id = self.card_owner_in_zone(container_id, zone, card_id)
        if owner_id is None:
            return None
        seat = self.players[player_id].get("seat")
        item = {
            "id": new_id(), "ownerId": owner_id, "controllerId": player_id,
            "cardId": card_id, "x": 740.0, "y": 800.0 if seat != 1 else 525.0,
            "faceUp": True, "rotation": 0.0, "counters": {}, "stackedOn": None,
        }
        if self.rules_interzone_slot_count(player_id) >= self.rules_interzone_capacity(player_id):
            anchor = self.rules_interzone_share_anchor(player_id, item)
            if not anchor:
                return None
            item.update({"stackedOn": anchor, "stackOffsetX": 18.0, "stackOffsetY": 18.0})
        item["fieldZone"] = "interzone"
        self.mark_rules_interzone_entry(item)
        self.take_zone_card(container_id, zone, card_id)
        self.battlefield.append(item)
        return item

    def rules_uncovered_deck_top(self, player_id):
        """Peropero: the top card of the deck is played uncovered."""
        if not self.rules_engine.get("enabled"):
            return None
        deck = self.players[player_id]["zones"]["deck"]
        if not deck or not any(
            self.rules_item_controller_id(source) == player_id
            for source in self.rules_active_passive_sources("deck_top_uncovered")
        ):
            return None
        return deck[0]

    def rules_karmapult_holder(self, player_id, item=None):
        if item is not None and self.card_rules.get(item.get("cardId"), {}).get("type") != "manifestation":
            return None
        return next((
            source for source in self.rules_active_passive_sources("interzone_substitute_holder")
            if self.rules_item_controller_id(source) == player_id
            and self.rules_field_zone(source) == "field"
        ), None)

    def rules_sync_attached_counter(self, host):
        count = len(host.get("attachedCards") or [])
        counters = host.setdefault("counters", {})
        if count:
            counters["Placed"] = count
        else:
            counters.pop("Placed", None)

    def rules_can_afford_tribute(self, player_id, cost):
        """True when some set of cards in hand (plus Essence) covers `cost`."""
        hand = list(self.players[player_id]["zones"]["hand"])
        if not self.rules_requirements_from_symbols(cost):
            return True
        pool = [c for c in hand if self.card_rules.get(c, {}).get("type") == "manifestation"][:7]
        for mask in range(1 << len(pool)):
            picked = [pool[i] for i in range(len(pool)) if mask >> i & 1]
            error, _payment = self.rules_action_payment(
                player_id, "activated_effect", None, picked, {"tribute": cost},
            )
            if not error:
                return True
        return False

    def rules_chain_candidates(self, chain_player_id, zone):
        """Chainable Manifestations as {card_id: container_id}.

        A Vessel Chain looks into every Empathic Vessel for cards the chaining
        player owns; other zones are the player's own.
        """
        if zone == "receptacle":
            containers = list(self.players)
        else:
            containers = [chain_player_id]
        found = {}
        for container_id in containers:
            for card_id in self.players[container_id]["zones"].get(zone, []):
                if zone == "receptacle" and self.card_owner_in_zone(
                    container_id, zone, card_id
                ) != chain_player_id:
                    continue
                if (
                    card_id not in found
                    and self.card_rules.get(card_id, {}).get("type") == "manifestation"
                    and self.rules_card_play_restriction_error(
                        chain_player_id, card_id
                    ) is None
                ):
                    found[card_id] = container_id
        return found

    def make_rules_chain_choice(self, chain_player_id, controller_id, result,
                                action, next_players=()):
        zone = result.get("zone")
        candidates = self.rules_chain_candidates(chain_player_id, zone)
        eligible = list(candidates)
        choice = {
            "id": new_id(),
            "kind": "chain_manifestation",
            "playerId": chain_player_id,
            "fromZone": zone,
            "optional": bool(
                result.get("optional")
                and (not action.get("optionalAccepted") or action.get("chainDeclinable"))
                and chain_player_id == controller_id
            ),
            "winDestination": result.get("winDestination"),
            "shuffleAfter": bool(result.get("shuffleAfter")),
            "returnToVessel": bool(result.get("returnToVessel")),
            "afterChain": result.get("afterChain"),
            "chainAbilities": result.get("chainAbilities"),
            "actionId": action.get("id"),
            "controllerId": action.get("controllerId") or controller_id,
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "_actionTargets": [dict(t) for t in action.get("targets") or []],
            "_cardIds": list(eligible),
            "_nextPlayers": list(next_players),
            "_result": dict(result),
            "_action": {
                "id": action.get("id"),
                "controllerId": action.get("controllerId"),
                "source": dict(action.get("source") or {}),
                "targets": [dict(t) for t in action.get("targets") or []],
                "optionalAccepted": True,
            },
        }
        if zone == "receptacle":
            choice["_cardContainers"] = dict(candidates)
        if zone != "hand":
            choice["cardIds"] = list(eligible)
        return choice

    def queue_rules_chain_continuation(self, choice):
        remaining = list(choice.get("_nextPlayers") or [])
        if not remaining:
            return
        self.rules_engine.setdefault("pendingChainSequences", []).append({
            "controllerId": choice.get("controllerId"),
            "players": remaining,
            "result": dict(choice.get("_result") or {}),
            "action": dict(choice.get("_action") or {}),
        })

    def resolve_rules_chain_sequences(self):
        sequences = self.rules_engine.get("pendingChainSequences") or []
        if self.rules_engine.get("pendingChoice") or not sequences:
            return None
        sequence = sequences.pop(0)
        return self.begin_rules_chain_sequence(
            sequence["controllerId"], sequence["players"],
            sequence["result"], sequence["action"],
        )
