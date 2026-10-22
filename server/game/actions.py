"""Describing a declared action: its source, targets, ability and result."""

import re

from .common import (
    SHARED_ZONES, RULES_SCORE_COUNTS, ADVANCED_PHASES, TRIBUTE_SYMBOL_TEMPERAMENT,
    RULES_WILL_TYPES, RULES_DESTROY_MATCHES, RULES_EFFECT_DURATIONS, RULES_TEMPERAMENTS
)


class ActionsMixin:
    def rules_action_source(self, player_id, kind, source, as_support=False,
                            ability_id=None):
        source = source if isinstance(source, dict) else {}
        card_id = str(source.get("cardId") or "")
        zone = str(source.get("zone") or "")
        item_id = str(source.get("itemId") or "")
        container_id = str(source.get("containerId") or player_id)
        if not card_id:
            if kind == "manual":
                return None, None
            return "Choose the card that creates this action.", None
        metadata = self.card_rules.get(card_id)
        if metadata is None:
            return "Unknown source card.", None
        if kind == "play_card" and self.rules_is_trap_card(card_id):
            return "A Trap can only be played at the Revelation, in place of the First Manifestation.", None
        if zone == "hand":
            if card_id not in self.players[player_id]["zones"]["hand"]:
                return "The source card is not in your Hand.", None
            activated_ability = next((
                entry for entry in metadata.get("activatedAbilities") or []
                if entry.get("id") == ability_id
            ), None)
            can_activate_from_hand = bool(
                kind == "activated_effect"
                and activated_ability
                and "hand" in (activated_ability.get("sourceZones") or [])
            )
            if kind != "play_card" and not can_activate_from_hand:
                return "A card in Hand must be declared as a played card.", None
            permission = next((
                entry for entry in self.rules_engine.get("playPermissions") or []
                if entry.get("playerId") == player_id
                and (
                    entry.get("cardId") == card_id
                    or (entry.get("anyWill") and metadata.get("type") in RULES_WILL_TYPES)
                )
                and entry.get("fromZone") == "hand"
                and entry.get("turn") == self.phase_tracker["turn"]
                and self.current_phase_id() in entry.get("phaseIds", [])
            ), None)
            if as_support:
                support_error = self.rules_support_from_hand_error(player_id, card_id)
                if support_error:
                    return support_error, None
        elif zone == "battlefield":
            item = self.find_battlefield_item(item_id)
            metadata = self.rules_item_card_rules(item) if item is not None else metadata
            ability = next((
                entry for entry in metadata.get("activatedAbilities") or []
                if entry.get("id") == ability_id
            ), None)
            any_player = bool(
                kind == "activated_effect"
                and ability_id
                and ability
                and ability.get("anyPlayer")
            )
            if (
                item is None
                or (
                    self.rules_item_controller_id(item) != player_id
                    and not any_player
                )
                or item.get("cardId") != card_id
            ):
                return "The source card is not on your side of the field.", None
            if (
                any_player and ability.get("opponentOnly")
                and self.rules_item_controller_id(item) == player_id
            ):
                return "Only an opponent can activate this effect.", None
            if not item.get("faceUp") and not (kind == "play_card" and item.get("concealedWill")):
                return "A face-down card cannot declare an effect.", None
            tebebe_manifestation = bool(
                kind == "play_card" and not as_support
                and item.get("tebebeConcealed")
                and metadata.get("type") == "manifestation"
            )
            if kind == "play_card" and not as_support and not tebebe_manifestation and not (
                metadata.get("type") in RULES_WILL_TYPES
                and (
                    item.get("playableFree") == self.phase_tracker["turn"]
                    or item.get("concealedWill")
                    or item.get("persuaded")
                )
            ):
                return "A card already on the field cannot be played again.", None
            if tebebe_manifestation:
                # Tebebe: a Concealed Manifestation is played into the Interzone
                if (
                    self.rules_interzone_slot_count(player_id) >= self.rules_interzone_capacity(player_id)
                    and not self.rules_interzone_share_anchor(player_id, item)
                ):
                    return "Your Interzone is full.", None
            if as_support:
                if item.get("pendingSupportActionId"):
                    return "This Manifestation is already entering Support.", None
                if self.current_phase_id() != "confrontation_reaction":
                    return "A Manifestation can enter Support only during Reaction.", None
                if metadata.get("type") != "manifestation":
                    return "Only a Manifestation can enter the confrontation.", None
                source_field_zone = self.rules_field_zone(item)
                if source_field_zone not in {"interzone", "stalemate"}:
                    return "This Manifestation is not in a zone from which it can enter Support.", None
                if not self.rules_card_can_enter_support(item, source_field_zone):
                    return "This Manifestation does not currently have Support.", None
        elif zone == "graveyard" and as_support:
            permission_error, permission = self.rules_zone_play_permission(
                player_id, container_id, zone, card_id
            )
            if permission_error:
                return permission_error, None
        elif zone == "deck" and kind == "play_card" and as_support:
            if (
                container_id != player_id
                or self.rules_uncovered_deck_top(player_id) != card_id
                or metadata.get("type") != "manifestation"
            ):
                return "Only the uncovered top card of your deck can be played this way.", None
            support_error = self.rules_support_from_hand_error(player_id, card_id)
            if support_error:
                return support_error, None
        elif zone == "attached" and kind == "play_card" and not as_support:
            host = self.find_battlefield_item(item_id)
            if (
                host is None or self.rules_item_controller_id(host) != player_id
                or not self.rules_item_effects_active(host)
                or not any(
                    passive.get("kind") == "play_attached_wills"
                    for passive in self.rules_item_card_rules(host).get("passiveEffects") or []
                )
                or not any(
                    entry.get("cardId") == card_id and entry.get("ownerId") == player_id
                    for entry in host.get("attachedCards") or []
                )
            ):
                return "This Will is not placed on a card you control.", None
            if metadata.get("type") not in RULES_WILL_TYPES:
                return "Only a Will can be played from here.", None
        elif zone == "graveyard" and kind == "play_card" and not as_support:
            if metadata.get("type") not in RULES_WILL_TYPES:
                return "Only a Will can be played from your Limbo this way.", None
            if container_id != player_id or card_id not in self.players[player_id]["zones"]["graveyard"]:
                return "This Will is not in your Limbo.", None
            permission = next((
                entry for entry in self.rules_engine.get("playPermissions") or []
                if entry.get("playerId") == player_id
                and entry.get("fromZone") == "graveyard"
                and entry.get("anyWill") and entry.get("exileOnLeave")
                and entry.get("turn") == self.phase_tracker["turn"]
                and self.current_phase_id() in entry.get("phaseIds", [])
                and (entry.get("maxCost") is None or int(metadata.get("cost") or 0) <= int(entry["maxCost"]))
                and (not entry.get("ephemeralOnly") or metadata.get("type") == "ephemeral_will")
            ), None)
            limbo_hollow = any(
                self.rules_item_controller_id(entry) == player_id
                for entry in self.rules_active_passive_sources("play_wills_from_limbo_hollow_tribute")
            )
            if permission is None and not limbo_hollow:
                return "You have no effect letting you play a Will from your Limbo.", None
        elif zone == "receptacle" and kind == "activated_effect":
            activated_ability = next((
                entry for entry in metadata.get("activatedAbilities") or []
                if entry.get("id") == ability_id
                and "receptacle" in (entry.get("sourceZones") or [])
            ), None)
            if activated_ability is None:
                return "This card has no effect usable from a Vessel.", None
            if (
                container_id not in self.players or container_id == player_id
                or card_id not in self.players[container_id]["zones"].get("receptacle", [])
                or self.card_owner_in_zone(container_id, "receptacle", card_id) != player_id
            ):
                return "This card must be in an opponent's Vessel and belong to you.", None
        elif zone == "suspended":
            suspension = next((
                entry for entry in self.rules_engine.get("suspendedCards") or []
                if entry.get("cardId") == card_id
                and entry.get("playableByPlayerId") == player_id
            ), None)
            if suspension is None or kind != "play_card":
                return "This Suspended card is not available to play.", None
        else:
            return "Unsupported source zone.", None
        if (
            kind == "play_card"
            and metadata.get("type") == "persistent_will"
            and self.rules_engine["actionStack"]
            and self.current_phase_id() != "end_actions"
            # the Atavic Wills, playable before the Revelation, may answer the
            # Stack there (even another Atavic)
            and not (
                self.current_phase_id() == "confrontation_before_revelation"
                and self.card_rules.get(card_id, {}).get("playBeforeRevelation")
            )
        ):
            return "A Persistent Will cannot be played as a response.", None
        if (
            kind == "play_card"
            and metadata.get("playOnlyEmptyStack")
            and self.rules_engine["actionStack"]
        ):
            return "This card can only be played while the Stack is empty.", None
        clean_source = {
            "cardId": card_id,
            "zone": zone,
            "itemId": item_id or None,
            "cardType": (
                "persistent_will"
                if zone == "hand" and kind == "play_card" and not as_support
                and metadata.get("playAsPersistentWill")
                else metadata.get("type")
            ),
            "ownerId": (
                self.card_owner_in_zone(player_id, "hand", card_id)
                if zone == "hand" else (
                    (player_id if zone == "attached" else self.card_owner_in_zone(container_id, zone, card_id))
                        if zone in {"graveyard", "receptacle", "attached", "deck"} else (
                            suspension.get("ownerId")
                            if zone == "suspended"
                            else self.find_battlefield_item(item_id).get("ownerId")
                        )
                    )
            ),
            "controllerId": player_id,
        }
        if zone == "receptacle":
            clean_source["containerId"] = container_id
        if zone == "hand" and kind == "activated_effect":
            clean_source["activatedFromZone"] = "hand"
        if (
            zone == "hand" and kind == "play_card" and not as_support
            and metadata.get("playAsPersistentWill")
        ):
            clean_source["noTribute"] = True
        if zone == "hand" and permission:
            clean_source.update({
                "permissionId": permission.get("id"),
                "noTribute": bool(permission.get("noTribute")),
            })
        if zone == "battlefield" and kind == "play_card" and not as_support:
            played_item = self.find_battlefield_item(item_id)
            if played_item and played_item.get("persuaded"):
                clean_source["extraTribute"] = 2
            if played_item and played_item.get("tebebeConcealed"):
                clean_source["fixedTribute"] = {"hollow": 3}
            elif played_item and (
                played_item.get("playableFree") == self.phase_tracker["turn"]
                or played_item.get("concealedFree")
            ):
                clean_source["noTribute"] = True
        if zone == "graveyard" and not as_support:
            clean_source.update({
                "containerId": container_id,
                "permissionId": permission.get("id") if permission else None,
                "exileOnLeave": True,
            })
            if permission:
                clean_source["noTribute"] = True
            else:
                clean_source["fixedTribute"] = {"hollow": 1}
        elif zone == "graveyard":
            clean_source.update({
                "containerId": container_id,
                "permissionId": permission.get("id"),
                "temperamentOverride": permission.get("temperamentOverride"),
                "winAsSupportDestination": permission.get("winAsSupportDestination"),
            })
        elif zone == "suspended":
            clean_source.update({
                "suspensionId": suspension.get("id"),
                "anyTemperamentTribute": bool(
                    suspension.get("anyTemperamentTribute")
                ),
            })
        return None, clean_source

    @staticmethod
    def rules_stack_target_matches(action, target_kind):
        if not isinstance(action, dict) or not (action.get("source") or {}).get("cardId"):
            return False
        if target_kind == "stack_action":
            return action.get("kind") == "play_card" and bool(action.get("sourceOnStack"))
        if target_kind == "stack_effect":
            return action.get("kind") in {"activated_effect", "triggered_effect"} or bool(action.get("sourceRemainsOnField"))
        return False

    def rules_stack_action_is_protected(self, action, controller_id):
        if not isinstance(action, dict):
            return False
        for effect in self.rules_engine.get("ongoingEffects") or []:
            if (
                effect.get("kind") == "protection"
                and effect.get("target", {}).get("actionId") == action.get("id")
                and (
                    not effect.get("fromOpponents")
                    or controller_id != action.get("controllerId")
                )
            ):
                return True
        return False

    def rules_action_targets(self, targets, player_id=None):
        """Clean structured targets; the declaring player's own Hand counts as
        a legal target zone (Reveal the Hidden), other private zones never do."""
        if targets is None:
            return None, []
        if not isinstance(targets, list):
            return "Targets must be supplied as a list.", None
        if len(targets) > 12:
            return "Too many targets were selected.", None
        clean_targets = []
        seen_targets = set()
        for target in targets:
            if not isinstance(target, dict):
                return "A structured target is invalid.", None
            kind = str(target.get("kind") or "card")
            if kind == "card":
                item_id = str(target.get("itemId") or "")
                target_key = (kind, item_id)
                if not item_id or target_key in seen_targets:
                    continue
                item = self.find_battlefield_item(item_id)
                if item is None or not item.get("faceUp") or not item.get("cardId"):
                    return "A selected target is no longer face up on the battlefield.", None
                supplied_card_id = str(target.get("cardId") or "")
                if supplied_card_id and supplied_card_id != item.get("cardId"):
                    return "A selected target no longer matches the declared card.", None
                clean_targets.append({
                    "kind": "card", "itemId": item_id,
                    "cardId": item["cardId"], "ownerId": item["ownerId"],
                })
            elif kind == "zone_card":
                container_id = str(target.get("containerId") or "")
                zone = str(target.get("zone") or "")
                card_id = str(target.get("cardId") or "")
                target_key = (kind, container_id, zone, card_id)
                own_hand = zone == "hand" and player_id is not None and container_id == player_id
                if not container_id or (zone not in SHARED_ZONES and not own_hand) or not card_id:
                    return "Only a card in a public zone can be selected as this target.", None
                if target_key in seen_targets:
                    continue
                container = self.players.get(container_id)
                if container is None or card_id not in container.get("zones", {}).get(zone, []):
                    return "A selected target is no longer in the declared public zone.", None
                clean_targets.append({
                    "kind": "zone_card", "zone": zone, "containerId": container_id,
                    "cardId": card_id,
                    "ownerId": self.card_owner_in_zone(container_id, zone, card_id),
                })
            elif kind == "player":
                player_id = str(target.get("playerId") or "")
                target_key = (kind, player_id)
                if not player_id or player_id not in self.players:
                    return "A selected player target is no longer in the game.", None
                if target_key in seen_targets:
                    continue
                clean_targets.append({"kind": "player", "playerId": player_id})
            elif kind in {"stack_action", "stack_effect", "stack_item"}:
                action_id = str(target.get("actionId") or "")
                target_key = (kind, action_id)
                stack_action = next((
                    action for action in self.rules_engine.get("actionStack") or []
                    if action.get("id") == action_id
                ), None)
                if (
                    not action_id
                    or target_key in seen_targets
                    or stack_action is None
                    or (
                        kind != "stack_item"
                        and not self.rules_stack_target_matches(stack_action, kind)
                    )
                ):
                    return (
                        "A selected card is no longer available on the Stack."
                        if kind == "stack_action"
                        else "A selected effect is no longer available on the Stack."
                    ), None
                supplied_card_id = str(target.get("cardId") or "")
                card_id = stack_action["source"]["cardId"]
                if supplied_card_id and supplied_card_id != card_id:
                    return "A selected Stack target no longer matches the declared card.", None
                clean_targets.append({
                    "kind": kind, "actionId": action_id,
                    "cardId": card_id, "controllerId": stack_action.get("controllerId"),
                })
            else:
                return "Only cards in public locations, cards or effects on the Stack, or current players can be selected here.", None
            seen_targets.add(target_key)
        return None, clean_targets

    @classmethod
    def clean_rules_action_result(cls, result):
        if not isinstance(result, dict):
            return None
        kind = result.get("kind")
        if kind == "chain_from_zone":
            return cls.clean_rules_trigger_result(result)
        if kind in {
            "move_source_to_owner_hand", "disable_source_effects",
            "destroy_vessel_target_owner_sacrifices",
            "declare_name_search_deck", "return_first_then_chain",
            "offer_support_else_chain", "retarget_stack_action",
            "cancel_target_stack_effect",
            "exile_source_take_control_to_interzone",
            "move_hand_source_to_interzone",
            "create_event_token_copy_in_support",
        }:
            return {"kind": kind}
        if kind == "choose_source_temperament":
            return {"kind": kind, **({"baseOnly": True} if result.get("baseOnly") else {})}
        if kind == "declare_name_top_card_power" and isinstance(result.get("value"), (int, float)):
            return {"kind": kind, "value": max(1, min(int(result["value"]), 99))}
        if kind == "clemency_choice" and isinstance(result.get("value"), (int, float)):
            return {"kind": kind, "value": max(1, min(int(result["value"]), 999))}
        if kind in {"draw_owner", "discard_deck_owner"} and isinstance(result.get("value"), (int, float)):
            clean = {"kind": kind, "value": max(0, min(int(result["value"]), 50))}
            if result.get("targetPlayer"):
                clean["targetPlayer"] = True
            return clean
        if kind == "score_owner" and isinstance(result.get("value"), (int, float)):
            clean = {
                "kind": kind,
                "value": max(-999, min(int(result["value"]), 999)),
            }
            if result.get("perCount") in RULES_SCORE_COUNTS:
                clean["perCount"] = result["perCount"]
            return clean
        if kind == "score_target" and isinstance(result.get("value"), (int, float)):
            clean = {
                "kind": kind,
                "value": max(-999, min(int(result["value"]), 999)),
            }
            if result.get("perCount") in RULES_SCORE_COUNTS:
                clean["perCount"] = result["perCount"]
            return clean
        if kind == "score_each_opponent" and isinstance(result.get("value"), (int, float)):
            clean = {
                "kind": kind,
                "value": max(-999, min(int(result["value"]), 999)),
            }
            if result.get("perCount") in RULES_SCORE_COUNTS:
                clean["perCount"] = result["perCount"]
            return clean
        if kind == "score_source_container" and isinstance(result.get("value"), (int, float)):
            return {
                "kind": kind,
                "value": max(-999, min(int(result["value"]), 999)),
            }
        if kind == "interzone_score_and_draw" and isinstance(result.get("score"), (int, float)):
            return {
                "kind": kind,
                "score": max(0, min(int(result["score"]), 999)),
            }
        if kind == "shuffle_owner_deck":
            return {"kind": kind}
        if kind == "create_essence":
            temperament = str(result.get("temperament") or "")
            value = result.get("value")
            if (
                (temperament not in RULES_TEMPERAMENTS and temperament != "source_chosen")
                or not isinstance(value, (int, float))
            ):
                return None
            clean = {
                "kind": kind,
                "temperament": temperament,
                "value": max(1, min(int(value), 20)),
            }
            if result.get("exileSourceIfNoCounter"):
                clean["exileSourceIfNoCounter"] = str(result["exileSourceIfNoCounter"])[:64]
            if result.get("retained"):
                clean["retained"] = True
            if result.get("perCount") in RULES_SCORE_COUNTS:
                clean["perCount"] = result["perCount"]
            return clean
        if kind == "move_zone_target_to_field_zone":
            field_zone = str(result.get("fieldZone") or "")
            if field_zone not in {"interzone", "confrontation", "field", "stalemate"}:
                return None
            return {
                "kind": kind,
                "fieldZone": field_zone,
                "asSupport": bool(result.get("asSupport")),
            }
        if kind in {"add_power_counter_target", "dissolve_vessel_targets"}:
            value = result.get("value")
            if not isinstance(value, (int, float)):
                return None
            return {"kind": kind, "value": max(-99, min(int(value), 99))}
        if kind == "deck_discard_then_weaken":
            return {
                "kind": kind,
                "count": max(1, min(int(result.get("count") or 3), 20)),
            }
        if kind in {
            "move_zone_target_to_own_vessel",
            "move_target_to_own_vessel",
            "double_target_base_power",
            "weaken_target_per_hand_card",
            "destroy_support_targets_draw",
            "power_counter_from_other_target",
            "destroy_all_tokens",
            "exile_all_wills_and_interzones",
            "consult_support",
            "humiliate_target",
            "destroy_random_interzone_target_player",
            "destroy_target_gain_points",
            "exile_target_on_win",
            "shuffle_hand_into_deck_and_draw",
            "exile_limbo_targets_add_power",
            "return_target_player_support",
            "return_target_player_interzone_to_deck_top",
            "create_target_token_copy_in_support",
            "grant_friendly_interzone_support_until_end_turn",
            "cleanse_target",
            "create_support_tokens_from_optional_extra_essence",
        }:
            return {"kind": kind}
        if kind == "create_support_token":
            power = result.get("power")
            temperament = str(result.get("temperament") or "")
            if (
                not isinstance(power, (int, float))
                or temperament not in RULES_TEMPERAMENTS
            ):
                return None
            return {
                "kind": kind,
                "power": max(0, min(int(power), 99)),
                "temperament": temperament,
            }
        if (
            kind == "discard_hand_owner_then_draw"
            and isinstance(result.get("discard"), (int, float))
            and isinstance(result.get("draw"), (int, float))
        ):
            return {
                "kind": kind,
                "discard": max(0, min(int(result["discard"]), 7)),
                "draw": max(0, min(int(result["draw"]), 50)),
            }
        if kind == "create_support_tokens":
            temperament = str(result.get("temperament") or "hollow")
            if temperament not in RULES_TEMPERAMENTS:
                return None
            clean = {
                "kind": kind,
                "count": max(1, min(int(result.get("count") or 1), 10)),
                "power": max(0, min(int(result.get("power") or 1), 99)),
                "temperament": temperament,
            }
            if result.get("fieldZone") == "interzone":
                clean["fieldZone"] = "interzone"
            if result.get("upTo"):
                clean["upTo"] = True
            if result.get("permanent"):
                clean["permanent"] = True
            return clean
        if kind == "discard_hand_each_opponent":
            return {
                "kind": kind,
                "value": max(1, min(int(result.get("value") or 1), 7)),
                "drawOwner": max(0, min(int(result.get("drawOwner") or 0), 7)),
            }
        if kind == "destroy_matching_on_field":
            match = str(result.get("match") or "")
            if match not in RULES_DESTROY_MATCHES:
                return None
            return {"kind": kind, "match": match}
        if kind == "move_random_zone_card":
            from_zone = str(result.get("fromZone") or "")
            zone = str(result.get("zone") or "")
            position = str(result.get("position") or "top")
            card_type = str(result.get("cardType") or "")
            reason = str(result.get("reason") or "")
            if from_zone not in SHARED_ZONES or zone not in {"deck", "hand", "graveyard", "exile"}:
                return None
            if position not in {"top", "bottom"} or card_type not in {"manifestation", *RULES_WILL_TYPES}:
                return None
            clean = {
                "kind": kind, "fromZone": from_zone, "cardType": card_type,
                "zone": zone, "position": position,
            }
            if reason in {"destroy", "exile"}:
                clean["reason"] = reason
            if result.get("eachPlayer"):
                clean["eachPlayer"] = True
            return clean
        if kind == "neutralize_stack_action":
            clean = {"kind": kind}
            if result.get("destination") == "hand":
                clean["destination"] = "hand"
            if result.get("refundEssence"):
                clean["refundEssence"] = True
            return clean
        if kind == "counter_stack_action_unless_payment":
            payment = str(result.get("payment") or "")
            symbols = re.findall(r"\{([A-Z])\}", payment)
            payer = str(result.get("payer") or "")
            mode = str(result.get("mode") or "")
            if (
                not symbols or len(symbols) > 7
                or any(symbol not in TRIBUTE_SYMBOL_TEMPERAMENT for symbol in symbols)
                or payer not in {"owner", "controller"}
                or mode not in {"neutralize", "cancel"}
            ):
                return None
            return {"kind": kind, "payment": payment, "payer": payer, "mode": mode}
        if kind == "copy_stack_action":
            return {"kind": kind}
        if kind == "destroy_source":
            return {"kind": kind}
        if kind == "score_owner_silent":
            return {"kind": kind, "value": max(-999, min(int(result.get("value") or 0), 999))}
        if kind == "optional_discard_wills_for_power":
            return {"kind": kind, "value": max(1, min(int(result.get("value") or 1), 20))}
        if kind == "lock_support_entries":
            return {"kind": kind, "scope": "controller" if result.get("scope") == "controller" else "all"}
        if kind == "set_field_power":
            mode = str(result.get("mode") or "")
            return {"kind": kind, "mode": mode} if mode in {"base", "lowest_base"} else None
        if kind == "stalemate_targets":
            return {
                "kind": kind, "includeSource": bool(result.get("includeSource")),
                "lockZone": bool(result.get("lockZone")),
            }
        if kind == "grant_support_entry_bonus":
            return {
                "kind": kind,
                "value": max(1, min(int(result.get("value") or 1), 20)),
                "requireLostPrevious": bool(result.get("requireLostPrevious")),
            }
        if kind in {"return_turn_tributes_end_turn", "stalemate_target_grant_source_support"}:
            return {"kind": kind}
        if kind == "stalemate_confrontation":
            return {
                "kind": kind,
                "scope": "winner" if result.get("scope") == "winner" else "all",
                "lockZone": bool(result.get("lockZone")),
                "lockSupportEntries": bool(result.get("lockSupportEntries")),
            }
        if kind == "optional_discard_up_to":
            return {"kind": kind, "value": max(1, min(int(result.get("value") or 1), 7))}
        if kind == "final_deck_points":
            return {"kind": kind, "value": max(0, min(int(result.get("value") or 0), 500))}
        if kind == "final_vessel_penalty":
            return {
                "kind": kind, "value": max(0, min(int(result.get("value") or 0), 500)),
                "maxBasePower": max(0, min(int(result.get("maxBasePower") or 0), 99)),
            }
        if kind in {
            "unless_payment_deck_discard", "unless_payment_lose_effects",
            "unless_opponent_payment_lock_support_entries", "unless_payment_exile_source",
        }:
            payment = str(result.get("payment") or "")
            symbols = re.findall(r"\{([A-Z])\}", payment)
            if not symbols or any(symbol not in TRIBUTE_SYMBOL_TEMPERAMENT for symbol in symbols):
                return None
            clean = {"kind": kind, "payment": payment}
            if kind == "unless_payment_deck_discard":
                clean["count"] = max(1, min(int(result.get("count") or 1), 20))
            return clean
        if kind == "restore_source_counter":
            counter = str(result.get("counter") or "")[:64]
            if not counter:
                return None
            return {"kind": kind, "counter": counter, "value": max(0, min(int(result.get("value") or 0), 99))}
        if kind == "choose_points_or_weaken_first":
            return {
                "kind": kind, "points": max(1, min(int(result.get("points") or 10), 999)),
                "power": max(1, min(int(result.get("power") or 2), 99)),
            }
        if kind == "search_deck_to_hand":
            return {
                "kind": kind, "count": max(1, min(int(result.get("count") or 1), 10)),
                "upTo": bool(result.get("upTo")),
            }
        if kind == "hand_manifestation_choice":
            destination = str(result.get("destination") or "")
            if destination not in {"interzone", "exile"}:
                return None
            clean = {"kind": kind, "destination": destination}
            for flag in ("drawByBasePower", "destroyTarget", "optional"):
                if result.get(flag):
                    clean[flag] = True
            return clean
        if kind == "destroy_random_vessel_manifestations":
            return {"kind": kind, "count": max(1, min(int(result.get("count") or 1), 10))}
        if kind == "distribute_power":
            total = int(result.get("total") or 0)
            if total < 1:
                return None
            clean = {
                "kind": kind, "total": min(total, 20),
                "sign": -1 if result.get("sign") == -1 else 1,
            }
            if result.get("duration") in RULES_EFFECT_DURATIONS:
                clean["duration"] = result["duration"]
            return clean
        if kind == "reveal_hand_discard_choice":
            return {
                "kind": kind,
                "scoreCost": max(0, min(int(result.get("scoreCost") or 0), 99)),
            }
        if kind == "set_interzone_power":
            return {"kind": kind, "value": max(0, min(int(result.get("value") or 1), 99))}
        if kind in {
            "each_player_stalemate_own_confrontation",
            "grant_source_support_until_end_turn",
            "grant_source_support_if_base_higher_than_own_first",
            "move_source_to_owner_deck_top",
            "move_source_to_owner_exile",
            "roll_d6_move_source_to_stalemate_on_odd",
            "return_supports_and_boost_firsts",
            "play_limbo_target_as_support",
            "resolve_target_stack_immediately",
            "choose_target_score_delta",
            "mill_deck_per_confrontation_manifestation",
            "sacrifice_other_confrontation_for_essence",
            "exile_source_then_shuffle_limbo_and_interzone",
            "destroy_target_tokens_for_controller",
            "first_manifestations_to_interzone_tokens",
            "stalemate_to_support_disabled",
            "timidette_support_to_deck_bottom",
            "destroy_persistent_will_refund_essence",
            "optional_discard_manifestation_weaken_target",
            "return_source_to_hand_restricted",
            "chain_discarded_manifestation_from_target_deck",
            "roll_d6_gain_half_essence",
            "return_other_limbo_card_to_hand",
            "shuffle_limbo_targets_into_deck",
            "exile_source_card_from_limbo",
            "limbo_source_to_support",
            "healing_bond",
            "destroy_next_opponent_confrontation_entry",
            "exile_limbo_targets_create_tokens",
            "interzone_target_to_support",
            "flower_of_evil_burst",
            "discard_any_then_lose_per_remaining",
            "roll_discard_deck_gain_power",
            "opponents_discard_deck_by_source_roll",
            "exile_confrontation_stalemate_and_source",
            "exile_tribute_manifestation_score_others",
            "exile_limbo_wills_add_power_each",
            "drain_excess_essence_power",
            "lock_next_turn_draws",
            "play_vessel_target_as_support",
            "grant_free_will_play",
            "grant_limbo_will_play",
            "will_becomes_support_manifestation",
            "choose_hand_will_as_support_manifestation",
            "amphora_offer",
            "extortionist_womb",
            "bullyboo_reveal",
            "grimoire_place",
            "gummo_copy_vessel",
            "interzone_becomes_first_manifestation",
            "source_to_winner_vessel",
            "slumberer_wakes",
            "field_becomes_first_manifestation",
            "persuasion_force",
            "persuasion_penalty",
            "lunar_liturgy",
            "spite_upkeep",
            "tebebe_unearth",
            "thoughtcutter_surge",
            "pescojolero_trade",
            "wish_exchange",
            "gorlok_peek",
            "auction_offer",
            "chabak_support",
            "chabak_wins",
            "paciphint_swap",
            "consul_wins",
            "ycar_exchange",
            "exile_source_grant_limbo_will_play",
            "restore_exhausted_targets",
            "peek_top_swap",
            "bottom_hand_card_remove_counters",
            "obelisk_gift",
            "karmapult_sacrifice",
            "hold_winner_manifestations",
            "search_deck_will_conceal",
            "free_concealed_wills",
            "lose_points_shuffle_source_into_deck",
            "take_last_opponent_support_to_vessel",
        }:
            clean = {"kind": kind}
            if kind == "play_limbo_target_as_support":
                clean["winDestination"] = (
                    "exile"
                    if result.get("winDestination") == "exile"
                    else None
                )
                if result.get("losesEffects"):
                    clean["losesEffects"] = True
                if result.get("exileInsteadOfLeaving"):
                    clean["exileInsteadOfLeaving"] = True
            if kind == "choose_target_score_delta":
                value = result.get("value")
                if not isinstance(value, (int, float)) or not int(value):
                    return None
                clean["value"] = max(1, min(abs(int(value)), 999))
            return clean
        if kind == "score_source_owner":
            value = result.get("value")
            if not isinstance(value, (int, float)) or not int(value):
                return None
            return {
                "kind": kind,
                "value": max(-999, min(int(value), 999)),
            }
        if kind == "move_counter":
            counter = str(result.get("counter") or "")[:64]
            value = result.get("value")
            if not counter or not isinstance(value, (int, float)):
                return None
            return {
                "kind": kind,
                "counter": counter,
                "value": max(1, min(int(value), 999)),
            }
        if kind == "adjust_target_power":
            value = result.get("value")
            if not isinstance(value, (int, float)) or not int(value):
                return None
            return {
                "kind": kind,
                "value": max(-999, min(int(value), 999)),
            }
        if kind == "schedule_rematch":
            return {"kind": kind}
        if kind == "change_source_control":
            counter = str(result.get("counter") or "")[:64]
            counter_value = result.get("counterValue")
            clean = {"kind": kind}
            if counter and isinstance(counter_value, (int, float)):
                clean["counter"] = counter
                clean["counterValue"] = max(
                    0, min(int(counter_value), 999)
                )
            if result.get("incrementCounter"):
                clean["incrementCounter"] = True
            return clean
        if kind == "score_controller_then_destroy_source":
            value = result.get("value")
            if not isinstance(value, (int, float)):
                return None
            return {
                "kind": kind,
                "value": max(-999, min(int(value), 999)),
            }
        if kind == "shuffle_hands_then_draw":
            value = result.get("value")
            if isinstance(value, (int, float)):
                return {
                    "kind": kind,
                    "value": max(0, min(int(value), 50)),
                }
            return None
        if kind == "exile_all_limbos":
            return {"kind": kind}
        if kind == "resolve_top_deck_by_type":
            return {
                "kind": kind,
                "manifestation": (
                    "chain" if result.get("manifestation") == "chain" else "none"
                ),
                "will": "draw" if result.get("will") == "draw" else "none",
            }
        if kind == "reorder_top_decks":
            count = result.get("count")
            if not isinstance(count, (int, float)):
                return None
            clean = {
                "kind": kind,
                "count": max(1, min(int(count), 12)),
                "eachPlayer": bool(result.get("eachPlayer")),
            }
            if isinstance(result.get("afterDraw"), (int, float)):
                clean["afterDraw"] = max(0, min(int(result["afterDraw"]), 10))
            if isinstance(result.get("afterDiscard"), (int, float)):
                clean["afterDiscard"] = max(0, min(int(result["afterDiscard"]), 10))
            for key in ("topCount", "bottomCount", "extraMin", "extraMax"):
                if isinstance(result.get(key), (int, float)):
                    clean[key] = max(0, min(int(result[key]), 12))
            if result.get("extraSide") in {"exile", "hand"}:
                clean["extraSide"] = result["extraSide"]
            if result.get("targetPlayer"):
                clean["targetPlayer"] = True
            return clean
        if kind == "split_targeted_limbo_cards":
            return {"kind": kind}
        if kind == "guess_top_card":
            return {"kind": kind}
        if kind in {
            "create_tokens_for_target_interzone_count",
            "capture_stalemate_and_copy",
            "copy_related_tribute_if_exhaust",
            "exile_limbos_create_token_copies",
            "copy_entering_persistent_will_for_others",
        }:
            return {"kind": kind}
        if kind == "schedule_next_turn_hand_limit":
            delta = result.get("delta")
            if not isinstance(delta, (int, float)):
                return None
            return {
                "kind": kind,
                "delta": max(-7, min(int(delta), 7)),
                "overflowDestination": (
                    "deck_bottom"
                    if result.get("overflowDestination") == "deck_bottom"
                    else "graveyard"
                ),
            }
        if kind == "choose_points_or_hand_limit":
            value = result.get("limit")
            points = result.get("points")
            if not isinstance(value, (int, float)) or not isinstance(points, (int, float)):
                return None
            return {
                "kind": kind,
                "limit": max(0, min(int(value), 20)),
                "points": max(0, min(int(points), 999)),
            }
        if kind == "move_targets":
            zone = str(result.get("zone") or "")
            position = str(result.get("position") or "top")
            reason = str(result.get("reason") or "")
            if zone not in {"deck", "hand", "graveyard", "exile"}:
                return None
            if position not in {"top", "bottom"}:
                return None
            clean = {"kind": kind, "zone": zone, "position": position}
            if reason in {"destroy", "exile", "return"}:
                clean["reason"] = reason
            return clean
        if kind == "optional_discard_then_draw":
            value = result.get("draw")
            if not isinstance(value, (int, float)):
                return None
            return {
                "kind": kind,
                "draw": max(0, min(int(value), 50)),
            }
        if kind == "roll_d6_power_by_parity":
            even = result.get("even")
            odd = result.get("odd")
            if not isinstance(even, (int, float)) or not isinstance(odd, (int, float)):
                return None
            return {
                "kind": kind,
                "even": max(-99, min(int(even), 99)),
                "odd": max(-99, min(int(odd), 99)),
            }
        if kind == "roll_d6_target_table":
            table = str(result.get("table") or "")
            return {
                "kind": kind,
                "table": table,
            } if table in {"greed", "mutation"} else None
        if kind == "roll_d6_conditional_source":
            return {"kind": kind}
        if kind == "roll_d6_each_target":
            # Kaos Bro (destroy) and Karma Bro (points): one die per target, a 1 or a 6 hits
            on_hit = str(result.get("onHit") or "")
            if on_hit == "destroy":
                return {"kind": kind, "onHit": on_hit}
            if on_hit == "points" and isinstance(result.get("points"), (int, float)):
                return {"kind": kind, "onHit": on_hit, "points": max(-99, min(int(result["points"]), 99))}
            return None
        if kind == "roll_multiple_even_power_odd_discard":
            rolls = result.get("rolls")
            if not isinstance(rolls, (int, float)):
                return None
            return {"kind": kind, "rolls": max(1, min(int(rolls), 20))}
        if kind == "score_controller_by_source_roll_then_exile":
            return {"kind": kind}
        if kind in {
            "force_win_if_highest_base_first",
            "stalemate_unless_opponent_pays",
            "skip_confrontation_unless_points",
            "end_confrontation_relocate_all",
            "suspend_opponent_hand_will",
        }:
            clean = {"kind": kind}
            if kind == "stalemate_unless_opponent_pays":
                payment = str(result.get("payment") or "")
                symbols = re.findall(r"\{([A-Z])\}", payment)
                if not symbols or any(symbol not in TRIBUTE_SYMBOL_TEMPERAMENT for symbol in symbols):
                    return None
                clean["payment"] = "".join(f"{{{symbol}}}" for symbol in symbols)
            if kind == "skip_confrontation_unless_points":
                points = result.get("points")
                if not isinstance(points, (int, float)):
                    return None
                clean["points"] = max(0, min(int(points), 999))
            return clean
        if kind == "end_confrontation_unless_payment":
            payment = str(result.get("payment") or "")
            symbols = re.findall(r"\{([A-Z])\}", payment)
            if (
                not symbols
                or any(symbol not in TRIBUTE_SYMBOL_TEMPERAMENT for symbol in symbols)
            ):
                return None
            return {
                "kind": kind,
                "payment": payment,
                "exileOnDecline": bool(result.get("exileOnDecline")),
                "reduceWinnerManifestationOnControllerDefeat": bool(
                    result.get(
                        "reduceWinnerManifestationOnControllerDefeat"
                    )
                ),
            }
        if kind == "exchange_control_targets":
            return {
                "kind": kind,
                "rememberAtResolution": bool(
                    result.get("rememberAtResolution")
                ),
            }
        if kind == "retarget_source_effect":
            effect_kind = str(result.get("effectKind") or "")[:64]
            return {
                "kind": kind,
                "effectKind": effect_kind,
            } if effect_kind else None
        if kind != "move_target":
            return None
        zone = str(result.get("zone") or "")
        position = str(result.get("position") or "top")
        if zone not in {"deck", "hand", "graveyard", "exile"}:
            return None
        if position not in {"top", "bottom"}:
            return None
        clean = {"kind": "move_target", "zone": zone, "position": position}
        reason = str(result.get("reason") or "")
        if reason in {"destroy", "exile", "return", "sacrifice"}:
            clean["reason"] = reason
        if result.get("restrictPlayUntilEndOfTurn"):
            clean["restrictPlayUntilEndOfTurn"] = True
        if isinstance(result.get("scoreCost"), (int, float)) and result["scoreCost"] > 0:
            clean["scoreCost"] = min(int(result["scoreCost"]), 999)
        return clean

    def rules_ability_targets_error(self, target_rules, targets, controller_id,
                                    event_item_id=None, source_item_id=None):
        target_rules = target_rules or {}
        groups = target_rules.get("groups")
        if isinstance(groups, list):
            if len(targets) != len(groups):
                return "Choose one valid target for each target group."
            for group, target in zip(groups, targets):
                error = self.rules_ability_targets_error(
                    group, [target], controller_id,
                    event_item_id=event_item_id,
                    source_item_id=source_item_id,
                )
                if error:
                    return error
            return None
        minimum = max(0, int(target_rules.get("min") or 0))
        maximum = max(minimum, int(target_rules.get("max") or minimum))
        if not minimum <= len(targets) <= maximum:
            return "Choose the required number of targets for this effect."
        required_types = set(target_rules.get("cardTypes") or [])
        if target_rules.get("cardType"):
            required_types.add(target_rules["cardType"])
        if isinstance(target_rules.get("maxTotalPoints"), (int, float)):
            total_points = sum(
                int((self.card_points or {}).get(entry.get("cardId"), 0))
                for entry in targets if entry.get("kind") in {"card", "zone_card"}
            )
            if total_points > target_rules["maxTotalPoints"]:
                return "The selected targets are worth too many points in total."
        for target in targets:
            target_kind = str(target_rules.get("kind") or "card")
            if target_kind == "player":
                if target.get("kind") != "player":
                    return "This effect requires a player target."
                relation = target_rules.get("controller")
                if relation == "self" and target.get("playerId") != controller_id:
                    return "This effect requires you as the target player."
                if relation == "opponent" and target.get("playerId") == controller_id:
                    return "This effect requires an opponent player."
                if (
                    target.get("playerId") != controller_id
                    and self.rules_active_passive_sources(
                        "mutual_opponent_immunity"
                    )
                ):
                    return "The selected player is Immune to opposing cards and effects."
                continue
            stack_target_kind = (
                "stack_action"
                if target_kind == "card_or_stack_action"
                and target.get("kind") == "stack_action"
                else target_kind
            )
            if stack_target_kind in {"stack_action", "stack_effect", "stack_item"}:
                if (
                    stack_target_kind != "stack_item"
                    and target.get("kind") != stack_target_kind
                ):
                    return (
                        "This effect requires a card on the Stack."
                        if stack_target_kind == "stack_action"
                        else "This effect requires an effect on the Stack."
                    )
                stack_action = next((
                    action for action in self.rules_engine.get("actionStack") or []
                    if action.get("id") == target.get("actionId")
                ), None)
                if (
                    stack_target_kind != "stack_item"
                    and not self.rules_stack_target_matches(
                        stack_action, stack_target_kind
                    )
                ):
                    return (
                        "The targeted card is no longer on the Stack."
                        if stack_target_kind == "stack_action"
                        else "The targeted effect is no longer on the Stack."
                    )
                if stack_action is None:
                    return "The targeted card or effect is no longer on the Stack."
                if self.rules_stack_action_is_protected(
                    stack_action, controller_id
                ):
                    return "The selected Stack card is Protected from cards and effects."
                relation = target_rules.get("controller")
                if relation == "self" and stack_action.get("controllerId") != controller_id:
                    return "This effect requires a Stack card you control."
                if relation == "opponent" and stack_action.get("controllerId") == controller_id:
                    return "This effect requires a Stack card controlled by an opponent."
                metadata = self.card_rules.get((stack_action.get("source") or {}).get("cardId"), {})
                if required_types and metadata.get("type") not in required_types:
                    return "This effect requires a different type of Stack card."
                if target_rules.get("targetsOwnFieldCard") and not any(
                    entry.get("kind") == "card"
                    and (field_item := self.find_battlefield_item(entry.get("itemId"))) is not None
                    and self.rules_item_controller_id(field_item) == controller_id
                    for entry in stack_action.get("targets") or []
                ):
                    return "This effect must target a card on the field you control."
                if target_rules.get("effectTemperamentChosenBySource"):
                    chosen = (self.find_battlefield_item(source_item_id) or {}).get("chosenTemperament")
                    effect_temperaments = self.card_rules.get(
                        (stack_action.get("source") or {}).get("cardId"), {}
                    ).get("temperaments") or []
                    if not chosen or chosen not in effect_temperaments:
                        return "This effect must have the chosen temperament."
                if (
                    target_rules.get("targetsFieldCard")
                    and not self.rules_stack_action_targets_field_card(stack_action)
                ):
                    return "This effect requires a card or effect that targets a card on the field."
                if (
                    target_rules.get("targetsConfrontationManifestation")
                    and not self.rules_stack_action_targets_confrontation(stack_action)
                ):
                    return "This effect requires a Will that targets a Manifestation in the Confrontation Zone."
                continue
            if (
                target_kind == "card_or_stack_action"
                and target.get("kind") != "card"
            ):
                return "This effect requires a card on the field or on the Stack."
            if target.get("kind") not in {"card", "zone_card"}:
                return "This effect requires a card target."
            allowed_zones = set(target_rules.get("zones") or ["battlefield"])
            if str(target.get("zone") or "battlefield") not in allowed_zones:
                return "This effect requires a target in a different zone."
            metadata = self.card_rules.get(target.get("cardId"), {})
            if required_types and metadata.get("type") not in required_types:
                return "This effect requires a different type of target."
            if isinstance(target_rules.get("maxPoints"), (int, float)):
                points = None if self.card_points is None else self.card_points.get(target.get("cardId"))
                if not isinstance(points, (int, float)) or points > target_rules["maxPoints"]:
                    return "This effect requires a target with a lower point value."
            if target.get("kind") != "card":
                if (
                    target.get("zone") == "receptacle"
                    and target.get("containerId") in self.players
                    and target.get("containerId") != controller_id
                    and self.rules_vessel_locked(target.get("containerId"))
                ):
                    return "The selected Empathic Vessel card is Protected from this controller."
                owner_relation = target_rules.get("owner")
                target_owner_id = target.get("ownerId")
                if owner_relation == "self" and target_owner_id != controller_id:
                    return "This effect requires a card you own."
                if owner_relation == "opponent" and target_owner_id == controller_id:
                    return "This effect requires a card you do not own."
                if (
                    target_rules.get("container") == "opponent"
                    and target.get("containerId") == controller_id
                ):
                    return "This effect requires a card in an opponent's zone."
                if (
                    target_rules.get("container") == "self"
                    and target.get("containerId") != controller_id
                ):
                    return "This effect requires a card in your own zone."
                if target_rules.get("enteredThisTurn"):
                    entry_turn = self.rules_engine.get("zoneEntryTurns", {}).get(
                        f'{target.get("containerId")}:{target.get("zone")}:{target.get("cardId")}'
                    )
                    if entry_turn != self.phase_tracker["turn"]:
                        return "This effect requires a card that entered that zone this turn."
                limbo_reasons = set(target_rules.get("limboReasons") or [])
                if limbo_reasons and not any(
                    entry.get("ownerId") == target.get("ownerId")
                    and entry.get("cardId") == target.get("cardId")
                    and entry.get("reason") in limbo_reasons
                    and int(entry.get("turn") or 0)
                    == self.phase_tracker["turn"]
                    for entry in self.rules_engine.get(
                        "recentLimboEntries"
                    ) or []
                ):
                    return "This effect requires a card destroyed or discarded this turn."
                continue
            item = self.find_battlefield_item(target.get("itemId"))
            if item is None:
                return "The selected battlefield target is no longer available."
            if self.rules_item_is_immune(item, controller_id):
                return "The selected card is Immune to cards and effects."
            if self.rules_item_is_protected(item, controller_id):
                return "The selected card is Protected from this controller."
            outcome_rule = target_rules.get("confrontationOutcome")
            if outcome_rule in {"won", "lost"}:
                outcome = self.rules_engine.get("confrontationResult") or {}
                side_id = outcome.get("winnerId" if outcome_rule == "won" else "loserId")
                if (
                    side_id not in self.players
                    or item.get("id") not in set(outcome.get("participantItemIds") or [])
                    or self.rules_item_controller_id(item) != side_id
                ):
                    return "This effect requires a Manifestation that %s the Confrontation this turn." % outcome_rule
            if (target_rules.get("enteredInterzoneThisTurn")
                    and (self.rules_field_zone(item) != "interzone"
                         or int(item.get("interzoneTurn") or 0) != self.phase_tracker["turn"])):
                return "This effect requires a Manifestation that entered the Interzone this turn."
            if target_rules.get("sourceOnly") and item.get("id") != source_item_id:
                return "This effect can only target its source Manifestation."
            if target_rules.get("firstManifestationOnly"):
                first_ids = set(self.rules_engine.get(
                    "firstManifestationItemIds", {}
                ).values())
                if item.get("id") not in first_ids:
                    return "This effect requires a First Manifestation."
            if target_rules.get("excludeEventSource") and item.get("id") == event_item_id:
                return "This effect requires another Manifestation."
            if target_rules.get("excludeSource") and item.get("id") == source_item_id:
                return "This effect requires another Manifestation."
            relation = target_rules.get("controller")
            item_controller = item.get("controllerId") or item.get("ownerId")
            if relation == "self" and item_controller != controller_id:
                return "This effect requires a Manifestation you control."
            if relation == "opponent" and item_controller == controller_id:
                return "This effect requires a Manifestation controlled by an opponent."
            owner_relation = target_rules.get("owner")
            if owner_relation == "self" and item.get("ownerId") != controller_id:
                return "This effect requires a card you own."
            if owner_relation == "opponent" and item.get("ownerId") == controller_id:
                return "This effect requires a card you do not own."
            if target_rules.get("fieldZone") and self.rules_field_zone(item) != target_rules["fieldZone"]:
                return "This effect requires a target in a different field zone."
            # the Stalemate Zone is not part of the field: only effects naming it reach it
            # (a target put into stalemate before its effect resolves is lost)
            if (
                self.rules_field_zone(item) == "stalemate"
                and target_rules.get("fieldZone") != "stalemate"
                and "stalemate" not in ((target_rules.get("fieldZonesByType") or {}).get(metadata.get("type")) or [])
            ):
                return "A card in the Stalemate Zone is not on the field."
            field_zones_by_type = target_rules.get("fieldZonesByType") or {}
            allowed_field_zones = field_zones_by_type.get(metadata.get("type"))
            if (
                isinstance(allowed_field_zones, list)
                and self.rules_field_zone(item) not in allowed_field_zones
            ):
                return "This effect requires this card type in a different field zone."
            if target_rules.get("supportOnly") and not item.get("isSupport"):
                return "This effect requires a Manifestation in Support."
            if target_rules.get("exhaustedOnly") and int(round(float(item.get("rotation") or 0))) % 180 == 0:
                return "This effect requires an Exhausted card."
            counter_name = str(target_rules.get("counter") or "")
            if counter_name:
                counter_key = next((
                    key for key in (item.get("counters") or {})
                    if str(key).casefold() == counter_name.casefold()
                ), counter_name)
                minimum_counters = max(
                    0, int(target_rules.get("minCounters") or 0)
                )
                if int((item.get("counters") or {}).get(counter_key) or 0) < minimum_counters:
                    return "This effect requires more counters on the selected card."
            if isinstance(target_rules.get("maxPower"), (int, float)):
                if self.rules_manifestation_characteristics(item)["power"] > target_rules["maxPower"]:
                    return "This effect requires a Manifestation with lower Power."
            if isinstance(target_rules.get("minPower"), (int, float)):
                if self.rules_manifestation_characteristics(item)["power"] < target_rules["minPower"]:
                    return "This effect requires a Manifestation with higher Power."
        return None

    def rules_action_ability(self, player_id, kind, source, ability_id, targets):
        if kind not in {"activated_effect", "play_card"} or not source:
            if ability_id:
                return "This action cannot use an encoded activated ability.", None
            return None, None
        ability_group = "playedAbilities" if kind == "play_card" else "activatedAbilities"
        source_item = self.find_battlefield_item(source.get("itemId"))
        metadata = (
            self.rules_item_card_rules(source_item)
            if source_item is not None and source.get("zone") == "battlefield"
            else self.card_rules.get(source.get("cardId"), {})
        )
        abilities = metadata.get(ability_group) or []
        if not abilities:
            if ability_id:
                return ("Unknown played ability." if kind == "play_card" else "Unknown activated ability."), None
            return None, None
        if not ability_id:
            return (
                "Choose the played ability to put on the Stack."
                if kind == "play_card"
                else "Choose the activated ability to put on the Stack."
            ), None
        ability = next((entry for entry in abilities if entry.get("id") == ability_id), None)
        if ability is None:
            return ("Unknown played ability." if kind == "play_card" else "Unknown activated ability."), None
        if (
            source.get("zone") == "battlefield"
            and not self.rules_item_effects_active(
                self.find_battlefield_item(source.get("itemId"))
            )
        ):
            return "This source Manifestation has lost its effects.", None

        source_zones = [
            str(zone) for zone in ability.get("sourceZones") or []
            if str(zone) in {"hand", "battlefield", "receptacle"}
        ]
        if source_zones and source.get("zone") not in source_zones:
            return "This ability cannot be activated from the source card's current zone.", None

        condition = str(ability.get("condition") or "")
        if condition == "controller_lost_confrontation":
            if not self.rules_player_lost_confrontation_this_turn(player_id):
                return "This ability requires you to have lost the current confrontation.", None

        if condition == "last_opponent_support_low_power":
            if self.rules_last_opponent_support(player_id, 2) is None:
                return "The last Manifestation an opponent put in Support must have a base power of 2 or less.", None

        phase_ids = [
            str(phase_id)
            for phase_id in ability.get("phaseIds") or []
            if str(phase_id) in ADVANCED_PHASES
        ]
        if phase_ids and self.current_phase_id() not in phase_ids:
            return "This ability cannot be activated during the current phase.", None

        required_source_field_zone = str(ability.get("sourceFieldZone") or "")
        if required_source_field_zone and source.get("zone") == "battlefield":
            item = self.find_battlefield_item(source.get("itemId"))
            if item is None or self.rules_field_zone(item) != required_source_field_zone:
                return "The source card must be in a different field zone to activate this effect.", None

        target_contract = (
            {"groups": ability.get("targetGroups")}
            if isinstance(ability.get("targetGroups"), list)
            else ability.get("targets")
        )
        target_error = self.rules_ability_targets_error(
            target_contract, targets, player_id,
            source_item_id=source.get("itemId"),
        )
        if target_error:
            return target_error, None
        if (ability.get("result") or {}).get("kind") == "retarget_stack_action":
            retarget_error = self.rules_retarget_error(targets)
            if retarget_error:
                return retarget_error, None

        if ability.get("exhaustSource"):
            item = self.find_battlefield_item(source.get("itemId"))
            if item is None or int(round(float(item.get("rotation") or 0))) % 180:
                return "The source card is already exhausted.", None
        if (
            (ability.get("result") or {}).get("kind") == "move_hand_source_to_interzone"
            and self.rules_interzone_slot_count(player_id)
            >= self.rules_interzone_capacity(player_id)
        ):
            return "There is no space left in your Interzone.", None
        if ability.get("loseScore") and self.rules_points_changes_prevented():
            return "Points cannot currently be gained or lost.", None
        counter_cost = ability.get("removeCountersFromSource")
        if isinstance(counter_cost, dict):
            cost_counters = (
                self.find_battlefield_item(source.get("itemId")) or {}
            ).get("counters") or {}
            held = sum(
                int(value or 0) for key, value in cost_counters.items()
                if str(key).casefold()
                == str(counter_cost.get("name") or "").casefold()
            )
            if held < int(counter_cost.get("amount") or 0):
                return (
                    f'This effect needs {int(counter_cost.get("amount") or 0)} '
                    f'{counter_cost.get("name")} counters on its source.'
                ), None
        counter_gate = ability.get("requireSourceCounter")
        if isinstance(counter_gate, dict):
            gate_counters = (
                self.find_battlefield_item(source.get("itemId")) or {}
            ).get("counters") or {}
            gate_held = sum(
                int(value or 0) for key, value in gate_counters.items()
                if str(key).casefold() == str(counter_gate.get("name") or "").casefold()
            )
            if gate_held < int(counter_gate.get("min") or 0) or gate_held > int(counter_gate.get("max", 99)):
                return f'This effect needs exactly the right number of {counter_gate.get("name")} counters.', None
        if ability.get("requireHandCard") and not self.players[player_id]["zones"]["hand"]:
            return "You need a card in your Hand for this effect.", None
        needed_hand_manifestations = int(ability.get("requireHandManifestations") or 0)
        if needed_hand_manifestations:
            hand_cards = list(self.players[player_id]["zones"]["hand"])
            if source.get("zone") == "hand" and source.get("cardId") in hand_cards:
                hand_cards.remove(source["cardId"])
            if sum(
                1 for card_id in hand_cards
                if self.card_rules.get(card_id, {}).get("type") == "manifestation"
            ) < needed_hand_manifestations:
                return f"You need {needed_hand_manifestations} other Manifestations in your Hand.", None
        use_limit = max(0, min(int(ability.get("useLimit") or 0), 99))
        if use_limit:
            used = int(((
                self.find_battlefield_item(source.get("itemId")) or {}
            ).get("abilityUses") or {}).get(str(ability.get("id")), 0))
            if used >= use_limit:
                return f"This effect can be used at most {use_limit} times.", None
        if ability.get("usePerTurn"):
            turn_uses = ((
                self.find_battlefield_item(source.get("itemId")) or {}
            ).get("abilityTurnUses") or {})
            if turn_uses.get(str(ability.get("id"))) == self.phase_tracker["turn"]:
                return "This effect can be used only once per turn.", None
        if ability.get("sacrificeTokenCreatedBySource") and not any(
            candidate.get("isTokenCard")
            and candidate.get("createdByItemId") == source.get("itemId")
            and self.rules_item_controller_id(candidate) == player_id
            for candidate in self.battlefield
        ):
            return "This ability requires a Token created by its source.", None
        def clean_ongoing_definition(ongoing_effect):
            if not isinstance(ongoing_effect, dict):
                return None
            effect_kind = str(ongoing_effect.get("kind") or "")[:64]
            duration = str(ongoing_effect.get("duration") or "")
            if effect_kind and duration in RULES_EFFECT_DURATIONS:
                clean = {"kind": effect_kind, "duration": duration}
                if isinstance(ongoing_effect.get("value"), (int, float)):
                    clean["value"] = ongoing_effect["value"]
                if isinstance(ongoing_effect.get("valuePerRemovedCounter"), (int, float)):
                    clean["valuePerRemovedCounter"] = ongoing_effect[
                        "valuePerRemovedCounter"
                    ]
                if ongoing_effect.get("scope") in {
                    "all_manifestations_on_field",
                    "all_manifestations_in_confrontation",
                    "friendly_cards_on_field",
                    "friendly_manifestations_in_interzone",
                    "friendly_manifestations_in_confrontation",
                    "target_player_manifestations_in_interzone",
                    "target_player",
                    "global",
                }:
                    clean["scope"] = ongoing_effect["scope"]
                if ongoing_effect.get("excludeSource"):
                    clean["excludeSource"] = True
                if ongoing_effect.get("fromOpponents"):
                    clean["fromOpponents"] = True
                if ongoing_effect.get("temperament") in RULES_TEMPERAMENTS:
                    clean["temperament"] = ongoing_effect["temperament"]
                return clean
            return None
        clean_ongoing_effect = clean_ongoing_definition(
            ability.get("ongoingEffect")
        )
        clean_ongoing_effects = [
            clean for clean in (
                clean_ongoing_definition(definition)
                for definition in ability.get("ongoingEffects") or []
            ) if clean
        ]
        dynamic_tribute = None
        counter_name = str(ability.get("tributeFromSourceCounter") or "")
        if counter_name:
            item = self.find_battlefield_item(source.get("itemId"))
            counters = (item or {}).get("counters") or {}
            counter_key = next((
                key for key in counters
                if str(key).casefold() == counter_name.casefold()
            ), counter_name)
            dynamic_tribute = "{H}" * max(
                0, min(int(counters.get(counter_key) or 0), 20)
            )
        clean_result = self.clean_rules_action_result(ability.get("result"))
        target_rules = ability.get("targets") or {}
        # a card may spell its groups either as targetGroups or as targets.groups
        raw_target_groups = (
            ability.get("targetGroups")
            if isinstance(ability.get("targetGroups"), list)
            else target_rules.get("groups")
        )
        allowed_target_keys = {
            "kind", "min", "max", "cardType", "cardTypes", "zones", "controller",
            "fieldZone", "supportOnly", "exhaustedOnly", "maxPoints", "maxPower", "minPower",
            "excludeEventSource", "excludeSource",
            "sourceOnly", "fieldZonesByType", "enteredThisTurn", "enteredInterzoneThisTurn", "confrontationOutcome", "owner",
            "firstManifestationOnly",
            "counter", "minCounters", "limboReasons", "container", "maxTotalPoints", "targetsConfrontationManifestation",
            "targetsFieldCard", "targetsOwnFieldCard", "effectTemperamentChosenBySource",
        }
        return None, {
            "id": ability["id"],
            "tribute": (
                dynamic_tribute
                if dynamic_tribute is not None
                else str(ability.get("tribute") or "")
                if "tribute" in ability else None
            ),
            "tributeFromSourceCounter": counter_name or None,
            "exhaustSource": bool(ability.get("exhaustSource")),
            "anyPlayer": bool(ability.get("anyPlayer")),
            "opponentOnly": bool(ability.get("opponentOnly")),
            "sacrificeSource": bool(ability.get("sacrificeSource")),
            "sacrificeDestination": (
                "exile" if ability.get("sacrificeDestination") == "exile" else None
            ),
            "sacrificeTokenCreatedBySource": bool(
                ability.get("sacrificeTokenCreatedBySource")
            ),
            "loseScore": max(0, min(int(ability.get("loseScore") or 0), 999)),
            "essenceCost": (
                str(ability.get("essenceCost") or "")
                if ability.get("essenceCost") is not None else None
            ),
            "sourceZones": source_zones,
            "costReduction": (
                dict(ability.get("costReduction"))
                if isinstance(ability.get("costReduction"), dict)
                else None
            ),
            "extraEssenceByTargetCount": (
                dict(ability.get("extraEssenceByTargetCount"))
                if isinstance(ability.get("extraEssenceByTargetCount"), dict)
                else None
            ),
            "extraEssenceForTargetPoints": (
                dict(ability.get("extraEssenceForTargetPoints"))
                if isinstance(ability.get("extraEssenceForTargetPoints"), dict)
                else None
            ),
            "optionalExtraEssence": ({
                "temperament": ability["optionalExtraEssence"].get(
                    "temperament"
                ),
                "max": max(
                    0, min(int(
                        ability["optionalExtraEssence"].get("max") or 0
                    ), 20)
                ),
            } if (
                isinstance(ability.get("optionalExtraEssence"), dict)
                and ability["optionalExtraEssence"].get("temperament")
                in RULES_TEMPERAMENTS
            ) else None),
            "removeAllCountersFromSource": (
                str(ability.get("removeAllCountersFromSource") or "")[:64] or None
            ),
            "removeCountersFromSource": (
                {
                    "name": str(ability["removeCountersFromSource"].get("name") or "")[:64],
                    "amount": max(0, min(int(
                        ability["removeCountersFromSource"].get("amount") or 0
                    ), 99)),
                }
                if isinstance(ability.get("removeCountersFromSource"), dict)
                and ability["removeCountersFromSource"].get("name")
                else None
            ),
            "reduceSourcePower": max(
                0, min(int(ability.get("reduceSourcePower") or 0), 999)
            ),
            "requireSourceCounter": (
                {
                    "name": str(ability["requireSourceCounter"].get("name") or "")[:64],
                    "min": max(0, min(int(ability["requireSourceCounter"].get("min") or 0), 99)),
                    "max": max(0, min(int(ability["requireSourceCounter"].get("max", 99)), 99)),
                }
                if isinstance(ability.get("requireSourceCounter"), dict)
                and ability["requireSourceCounter"].get("name")
                else None
            ),
            "addCountersToSource": (
                {
                    "name": str(ability["addCountersToSource"].get("name") or "")[:64],
                    "amount": max(0, min(int(ability["addCountersToSource"].get("amount") or 0), 99)),
                }
                if isinstance(ability.get("addCountersToSource"), dict)
                and ability["addCountersToSource"].get("name")
                else None
            ),
            "requireHandCard": bool(ability.get("requireHandCard")),
            "requireHandManifestations": max(0, min(int(ability.get("requireHandManifestations") or 0), 7)),
            "useLimit": max(0, min(int(ability.get("useLimit") or 0), 99)) or None,
            "usePerTurn": bool(ability.get("usePerTurn")),
            "supportWhenAllUsed": [
                str(entry)[:64] for entry in ability.get("supportWhenAllUsed") or []
            ][:6] if isinstance(ability.get("supportWhenAllUsed"), list) else None,
            "additionalCost": (
                ability["additionalCost"]
                if ability.get("additionalCost") in {
                    "exile_hand_manifestation", "discard_hand_will",
                } else None
            ),
            "sourceCost": (
                ability["sourceCost"]
                if ability.get("sourceCost") in {"discard_source", "stalemate_source"}
                else None
            ),
            "sourceFieldZone": required_source_field_zone or None,
            "condition": condition or None,
            "phaseIds": phase_ids,
            "immediate": bool(ability.get("immediate")),
            "resolveSourceTo": (
                str(ability.get("resolveSourceTo"))
                if ability.get("resolveSourceTo") in {"graveyard", "exile"}
                else None
            ),
            "ongoingEffect": clean_ongoing_effect,
            "ongoingEffects": clean_ongoing_effects,
            "result": clean_result,
            "targets": {
                key: list(value) if isinstance(value, list) else value
                for key, value in target_rules.items() if key in allowed_target_keys
            },
            "targetGroups": [
                {
                    key: list(value) if isinstance(value, list) else value
                    for key, value in group.items()
                    if key in allowed_target_keys
                }
                for group in raw_target_groups or []
                if isinstance(group, dict)
            ],
        }
