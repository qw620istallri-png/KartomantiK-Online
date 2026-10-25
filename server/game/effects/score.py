"""Effect results that move points between players."""

import random

from ..common import new_id


class ScoreEffectsMixin:
    def _rules_result_move_source_to_target_vessel_score(self, action, result, player_id, player):
        target_id = next((target.get("playerId") for target in action.get("targets") or []
                          if target.get("kind") == "player"), None)
        if target_id not in self.players:
            return {"kind": result.get("kind"), "status": "target_missing"}
        source = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
        movement = self._rules_remove_field_item_by_effect(
            source, target_id, "receptacle", "top", reason="move",
        ) if source is not None else None
        delta = self.adjust_rules_score(target_id, int(result.get("value") or 0))
        return {"kind": result.get("kind"), "status": "resolved", "playerId": target_id,
                "delta": delta, "movement": movement}

    def _rules_result_score_target(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "player"
        ), None)
        target_id = (target or {}).get("playerId")
        if target_id not in self.players:
            return {
                "kind": result.get("kind"),
                "status": "target_missing",
            }
        amount = int(result.get("value") or 0)
        if result.get("perCount"):
            amount *= self.rules_score_count(
                result["perCount"], target_id, action
            )
        delta = self.adjust_rules_score(target_id, amount)
        return {
            "kind": result.get("kind"),
            "status": "prevented" if not delta else "resolved",
            "playerId": target_id,
            "delta": delta,
            "score": self.players[target_id]["score"],
        }

    def _rules_result_score_each_opponent(self, action, result, player_id, player):
        deltas = {}
        opponent_of = player_id
        if result.get("opponentOfEventController"):
            # Looj rewards the opponent of the losing card's controller,
            # even if a different player controlled the Chain-granting effect.
            event_controller = ((action.get("ability") or {}).get("trigger") or {}).get("eventControllerId")
            if event_controller in self.players:
                opponent_of = event_controller
        multiplier = (
            self.rules_score_count(result["perCount"], player_id, action)
            if result.get("perCount") else 1
        )
        for other_id in self.players:
            if other_id != opponent_of:
                deltas[other_id] = self.adjust_rules_score(
                    other_id, int(result.get("value") or 0) * multiplier
                )
        return {
            "kind": "score_each_opponent",
            "status": "resolved" if any(deltas.values()) else "prevented",
            "deltas": deltas,
        }

    def _rules_result_score_source_container(self, action, result, player_id, player):
        container_id = (action.get("source") or {}).get("containerId")
        if container_id not in self.players:
            return {"kind": result.get("kind"), "status": "target_missing"}
        delta = self.adjust_rules_score(
            container_id, int(result.get("value") or 0)
        )
        return {
            "kind": result.get("kind"),
            "status": "prevented" if not delta else "resolved",
            "playerId": container_id,
            "delta": delta,
            "score": self.players[container_id]["score"],
        }

    def _rules_result_interzone_score_and_draw(self, action, result, player_id, player):
        count = self.rules_score_count(
            "own_interzone_manifestations", player_id, action
        )
        delta = self.adjust_rules_score(
            player_id, int(result.get("score") or 0) * count
        )
        free = max(0, self.rules_interzone_capacity(player_id) - len([
            entry for entry in self.battlefield
            if self.rules_item_controller_id(entry) == player_id
            and self.rules_field_zone(entry) == "interzone"
            and not entry.get("stackedOn")
        ]))
        draw = self.request_rules_draw(
            player_id, free,
            source_controller_id=action.get("controllerId"),
        ) if free else None
        return {
            "kind": "score",
            "playerId": player_id,
            "delta": delta,
            "score": player["score"],
            "freeInterzoneSpaces": free,
            "draw": draw,
        }

    def _rules_result_humiliate_target(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "card"
        ), None)
        item = self.find_battlefield_item((target or {}).get("itemId"))
        if item is None:
            return {"kind": result.get("kind"), "status": "target_missing"}
        self.set_rules_item_temperament(item, "hollow", action)
        self.adjust_rules_power_counter(item, -1)
        controller_id = self.rules_item_controller_id(item)
        self.adjust_rules_score(controller_id, -5)
        return {
            "kind": result.get("kind"), "status": "humiliated",
            "itemId": item["id"], "controllerId": controller_id,
        }

    def _rules_result_score_owner_silent(self, action, result, player_id, player):
        delta = self.adjust_rules_score(
            action.get("controllerId") or player_id, int(result.get("value") or 0),
            observe=False,
        )
        return {"kind": result.get("kind"), "status": "scored", "delta": delta}

    def _rules_result_choose_points_or_weaken_first(self, action, result, player_id, player):
        payer_id = (action.get("source") or {}).get("containerId")
        if payer_id not in self.players:
            return {"kind": result.get("kind"), "status": "target_missing"}
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id, "kind": "points_or_weaken_first", "playerId": payer_id,
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "points": int(result.get("points") or 10), "power": int(result.get("power") or 2),
            "options": ["lose_points", "weaken_first"],
        }
        return {
            "kind": "choice_required", "choiceId": choice_id,
            "choiceKind": "points_or_weaken_first", "playerId": payer_id,
        }

    def _rules_result_exile_tribute_manifestation_score_others(self, action, result, player_id, player):
        trigger = (action.get("ability") or {}).get("trigger") or {}
        card_id = trigger.get("relatedCardId")
        owner_id = trigger.get("relatedOwnerId")
        payer_id = trigger.get("eventControllerId") or owner_id
        exiled = False
        if card_id and owner_id in self.players and card_id in self.players[owner_id]["zones"]["graveyard"]:
            error, _owner, _replacement = self.move_zone_card_by_effect(
                owner_id, "graveyard", owner_id, "exile", card_id, "top"
            )
            exiled = not error
        for pid in self.players:
            if pid != payer_id:
                self.adjust_rules_score(pid, 5)
        return {
            "kind": result.get("kind"),
            "status": "exiled" if exiled else "scored", "cardId": card_id,
        }

    def _rules_result_destroy_target_gain_points(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "card"
        ), None)
        item = self.find_battlefield_item((target or {}).get("itemId"))
        if item is None:
            return {"kind": result.get("kind"), "status": "target_missing"}
        points = int((self.card_points or {}).get(item.get("cardId"), 0) or 0)
        movement = self._rules_remove_field_item_by_effect(
            item, item.get("ownerId"), "graveyard", "top", reason="destroy"
        )
        self.prune_rules_ongoing_effects()
        if movement.get("status") == "moved" and points:
            self.adjust_rules_score(player_id, points)
        return {
            "kind": result.get("kind"), "status": movement.get("status"),
            "cardId": item.get("cardId"), "points": points,
        }

    def _rules_result_score_source_owner(self, action, result, player_id, player):
        source_item = self.find_battlefield_item(
            (action.get("source") or {}).get("itemId")
        )
        owner_id = (
            source_item.get("ownerId")
            if source_item is not None
            else (action.get("source") or {}).get("ownerId")
        )
        delta = self.adjust_rules_score(
            owner_id, int(result.get("value") or 0)
        )
        return {
            "kind": result.get("kind"),
            "status": "prevented" if not delta else "resolved",
            "playerId": owner_id,
            "delta": delta,
            "score": self.players.get(owner_id, {}).get("score"),
        }

    def _rules_result_choose_target_score_delta(self, action, result, player_id, player):
        target = next((
            entry for entry in action.get("targets") or []
            if entry.get("kind") == "player"
        ), None)
        if target is None:
            return {
                "kind": result.get("kind"),
                "status": "target_missing",
            }
        if self.rules_points_changes_prevented():
            return {
                "kind": result.get("kind"),
                "status": "prevented",
                "targetPlayerId": target.get("playerId"),
            }
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id,
            "kind": "score_delta_choice",
            "playerId": player_id,
            "targetPlayerId": target.get("playerId"),
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "value": int(result.get("value") or 0),
            "options": ["gain", "lose"],
        }
        return {
            "kind": "choice_required",
            "choiceId": choice_id,
            "choiceKind": "score_delta_choice",
            "playerId": player_id,
            "targetPlayerId": target.get("playerId"),
        }

    def _rules_result_lose_points_shuffle_source_into_deck(self, action, result, player_id, player):
        source_item = self.find_battlefield_item(
            (action.get("source") or {}).get("itemId")
        )
        if source_item is None:
            return {"kind": result.get("kind"), "status": "source_missing"}
        delta = self.adjust_rules_score(
            self.rules_item_controller_id(source_item), -10
        )
        owner_id = source_item.get("ownerId")
        movement = self._rules_remove_field_item(source_item, owner_id, "deck", "top")
        if owner_id in self.players:
            random.shuffle(self.players[owner_id]["zones"]["deck"])
        self.prune_rules_ongoing_effects()
        return {
            "kind": result.get("kind"), "status": movement.get("status"),
            "delta": delta, "movement": movement,
        }

    def _rules_result_lose_excess_essence_or_points(self, action, result, player_id, player):
        value = int(result.get("value") or 0)
        outcomes = []
        for current_id in self.players:
            excess = [
                token for token in self.tokens
                if token.get("ownerId") == current_id
                and token.get("isExcess")
                and int((token.get("counters") or {}).get("essence") or 0) > 0
            ]
            if excess:
                lost = sum(int(token["counters"]["essence"]) for token in excess)
                gone = {token["id"] for token in excess}
                self.tokens = [t for t in self.tokens if t.get("id") not in gone]
                outcomes.append({"playerId": current_id, "essenceLost": lost})
            else:
                lost_points = -self.adjust_rules_score(current_id, -value)
                outcomes.append({"playerId": current_id, "pointsLost": lost_points})
        return {"kind": result.get("kind"), "status": "applied", "players": outcomes}

    def _rules_result_choose_points_or_hand_limit(self, action, result, player_id, player):
        target_id = (action.get("source") or {}).get("containerId")
        if target_id not in self.players:
            return {
                "kind": result.get("kind"),
                "status": "target_missing",
            }
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id,
            "kind": "points_or_hand_limit",
            "playerId": target_id,
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "points": int(result.get("points") or 0),
            "limit": int(result.get("limit") or 0),
            "options": ["lose_points", "limit_hand"],
        }
        return {
            "kind": "choice_required",
            "choiceId": choice_id,
            "choiceKind": "points_or_hand_limit",
            "playerId": target_id,
        }

    def _rules_result_skip_confrontation_unless_points(self, action, result, player_id, player):
        source_controller_id = action.get("controllerId")
        opponent_id = self.other_rules_player_id(source_controller_id)
        own_first = self.find_battlefield_item(
            self.rules_engine.get("firstManifestationItemIds", {}).get(
                source_controller_id
            )
        )
        opponent_first = self.find_battlefield_item(
            self.rules_engine.get("firstManifestationItemIds", {}).get(
                opponent_id
            )
        )
        own_power = self.rules_manifestation_base_power(own_first)
        opponent_power = self.rules_manifestation_base_power(opponent_first)
        if own_power <= opponent_power:
            return {
                "kind": result.get("kind"),
                "status": "condition_failed",
            }
        choice_id = new_id()
        self.rules_engine["pendingChoice"] = {
            "id": choice_id,
            "kind": "skip_confrontation_payment",
            "playerId": opponent_id,
            "sourceCardId": (action.get("source") or {}).get("cardId"),
            "points": int(result.get("points") or 0),
            "options": ["lose_points", "skip"],
        }
        return {
            "kind": "choice_required",
            "choiceId": choice_id,
            "choiceKind": "skip_confrontation_payment",
            "playerId": opponent_id,
        }

    def _rules_result_score_owner(self, action, result, player_id, player):
        amount = int(result.get("value") or 0)
        if result.get("perCount"):
            amount *= self.rules_score_count(
                result["perCount"], player_id, action
            )
        delta = self.adjust_rules_score(player_id, amount)
        return {
            "kind": "score",
            "playerId": player_id,
            "delta": delta,
            "score": player["score"],
        }
