"""Players, logs, searches and moving cards between zones."""
import random
import time
from collections import Counter

from .common import (
    ALL_ZONES, SESSION_TTL_SECONDS, NUM_SEATS, new_id, validate_tournament_deck, normalize_role,
    make_player
)


class ZonesMixin:
    # -- bookkeeping -------------------------------------------------
    def touch(self):
        self.last_activity = time.time()

    def is_expired(self):
        return (time.time() - self.last_activity) > SESSION_TTL_SECONDS

    def add_log(self, actor_id, action_type, details=None, actor_name=None):
        actor = self.players.get(actor_id)
        self.log_sequence += 1
        self.log.append(
            {
                "sequence": self.log_sequence,
                "timestamp": time.time(),
                "actorId": actor_id,
                "actorName": actor["name"] if actor else actor_name,
                "type": action_type,
                "details": details or {},
                "turn": self.phase_tracker["turn"],
                "phase": self.current_phase_id(),
            }
        )

    # -- players ------------------------------------------------------
    def get_or_create_player(self, player_id, name, seat=None):
        player = self.players.get(player_id)
        if player is None:
            player = make_player(player_id, name, cluster_index=len(self.players), seat=seat)
            self.players[player_id] = player
        elif name:
            player["name"] = name
        if self.rules_engine["enabled"] and self.rules_engine["priorityPlayerId"] is None:
            self.rules_engine["priorityPlayerId"] = player_id
        return player

    def mark_hand_revealed(self, player_id, card_ids):
        """Hand cards shown to the other players stay face up for them, at their
        real place in the hand, until they leave it."""
        player = self.players.get(player_id)
        if player is None:
            return
        self.prune_revealed_hand(player_id)
        in_hand = Counter(player["zones"]["hand"])
        revealed = self.revealed_hand.setdefault(player_id, Counter())
        for card_id in card_ids:
            if revealed[card_id] < in_hand[card_id]:
                revealed[card_id] += 1

    def prune_revealed_hand(self, player_id):
        """A copy that left the hand is no longer known (the revealed ones go first)."""
        in_hand = Counter(self.players[player_id]["zones"]["hand"])
        seen = self.revealed_hand_seen.get(player_id, in_hand)
        revealed = self.revealed_hand.get(player_id)
        if revealed:
            for card_id in list(revealed):
                left = max(0, seen[card_id] - in_hand[card_id])
                revealed[card_id] = max(0, min(revealed[card_id] - left, in_hand[card_id]))
                if not revealed[card_id]:
                    del revealed[card_id]
        self.revealed_hand_seen[player_id] = in_hand

    def forget_revealed_hand(self, player_id=None):
        """A hand put back into the deck (mulligan, new deck, reset) is unknown again."""
        for pid in [player_id] if player_id else list(self.revealed_hand):
            self.revealed_hand.pop(pid, None)
            self.revealed_hand_seen.pop(pid, None)

    def revealed_hand_indices(self, player_id):
        """Places in the hand of the revealed copies."""
        self.prune_revealed_hand(player_id)
        quota = Counter(self.revealed_hand.get(player_id) or {})
        indices = []
        for index, card_id in enumerate(self.players[player_id]["zones"]["hand"]):
            if quota[card_id] > 0:
                quota[card_id] -= 1
                indices.append(index)
        return indices

    def player_for_seat(self, seat):
        return next((player for player in self.players.values() if player.get("seat") == seat), None)

    def concede(self, player_id):
        """The conceding player loses at once; everyone else wins."""
        winner_ids = [pid for pid in self.players if pid != player_id]
        self.rules_engine["outcome"] = {
            "reason": "concession",
            "loserIds": [player_id],
            "winnerIds": winner_ids,
            "draw": len(winner_ids) != 1,
        }
        self.rules_engine["pendingChoice"] = None
        self.rules_engine["priorityPlayerId"] = None
        self.ended = True

    def tournament_codes(self):
        if self.mode != "tournament":
            return {}
        return {
            "player1": self.code_player1,
            "player2": self.code_player2,
            "spectator": self.code_spectator,
            "judge": self.code_judge,
        }

    def tournament_summary(self, role=None):
        seats = []
        for seat in range(NUM_SEATS):
            player = self.player_for_seat(seat)
            deck_definition = player.get("deckDefinition") if player else None
            if isinstance(deck_definition, dict):
                deck_count = sum(
                    len(group.get("cardIds") or [])
                    for group in (deck_definition.get("groups") or [])
                    if str(group.get("kind") or "").lower() not in {"sideboard", "maybeboard"}
                )
            else:
                deck_count = 0
            deck_error = None
            if player and isinstance(deck_definition, dict) and self.card_points is not None:
                main_cards = []
                sideboard_cards = []
                for group in deck_definition.get("groups") or []:
                    kind = str(group.get("kind") or "").lower()
                    if kind == "maybeboard":
                        continue
                    target = sideboard_cards if kind == "sideboard" else main_cards
                    target.extend(group.get("cardIds") or [])
                deck_error = validate_tournament_deck(
                    main_cards, sideboard_cards, self.card_points,
                    self.tournament_policy, self.card_labels,
                    limit_bonus=self.rules_deck_limit_bonus(main_cards),
                )
            seats.append(
                {
                    "seat": seat,
                    "name": player["name"] if player else None,
                    "connected": bool(player and player["connected"]),
                    "deckCount": deck_count,
                    "deckReady": deck_count == 30 and deck_error is None,
                    "deckError": deck_error,
                }
            )
        summary = {
            "enabled": True,
            "status": self.status,
            "seats": seats,
            "policy": self.tournament_policy,
            "auditAlerts": self.audit_alerts[-20:] if role is None or normalize_role(role) in {"organizer", "judge"} else [],
        }
        return summary

    def record_search(self, actor_id, owner_id, zone):
        key = (actor_id, owner_id, zone)
        alert = {
            "id": new_id(),
            "actorId": actor_id,
            "actorName": (self.players.get(actor_id) or {}).get("name") or actor_id,
            "ownerId": owner_id,
            "zone": zone,
            "timestamp": time.time(),
            "status": "pending",
            "severity": "warning",
        }
        self.pending_searches[key] = alert
        self.audit_alerts.append(alert)
        return alert

    def resolve_search(self, actor_id, owner_id, zone):
        alert = self.pending_searches.pop((actor_id, owner_id, zone), None)
        if alert:
            alert["status"] = "resolved"
            alert["resolvedAt"] = time.time()
        return alert

    def escalate_pending_searches(self, actor_id, action_type):
        escalated = []
        for (search_actor, _owner_id, _zone), alert in self.pending_searches.items():
            if search_actor != actor_id or alert.get("status") != "pending":
                continue
            alert["status"] = "unshuffled"
            alert["severity"] = "critical"
            alert["followupAction"] = action_type
            escalated.append(alert)
        return escalated

    def other_player_ids(self, player_id):
        return [pid for pid in self.players if pid != player_id]

    def other_rules_player_id(self, player_id):
        return next((pid for pid in self.players if pid != player_id), None)

    # -- immutable card ownership ---------------------------------------
    def card_owner_in_zone(self, container_id, zone, card_id):
        player = self.players.get(container_id)
        if player is None:
            return None
        return player.get("zoneOwners", {}).get(zone, {}).get(card_id, container_id)

    def take_zone_card(self, container_id, zone, card_id):
        player = self.players.get(container_id)
        if player is None or card_id not in player["zones"][zone]:
            return None
        owner_id = self.card_owner_in_zone(container_id, zone, card_id)
        player["zones"][zone].remove(card_id)
        if zone == "graveyard" and self.rules_engine.get("enabled"):
            self.rules_engine["limboExitTurn"] = self.phase_tracker["turn"]
        if zone == "receptacle" and self.rules_engine.get("enabled"):
            left = self.rules_engine.setdefault("leftVesselCards", [])
            if f"{owner_id}:{card_id}" not in left:
                left.append(f"{owner_id}:{card_id}")
        self.rules_engine.get("zoneEntryTurns", {}).pop(
            f"{container_id}:{zone}:{card_id}", None
        )
        if card_id not in player["zones"][zone]:
            player.setdefault("zoneOwners", {}).setdefault(zone, {}).pop(card_id, None)
        if self.rules_engine["enabled"]:
            self.rules_engine["playPermissions"] = [
                entry for entry in self.rules_engine.get("playPermissions") or []
                if not (
                    entry.get("playerId") == owner_id
                    and entry.get("fromZone") == zone
                    and entry.get("cardId") == card_id
                )
            ]
        return owner_id

    def put_zone_card(self, container_id, zone, card_id, owner_id, position="top"):
        player = self.players.get(container_id)
        if player is None:
            return False
        if zone in {"deck", "graveyard"} and self.rules_exiles_incoming_manifestations(
            container_id, card_id
        ):
            zone, position = "exile", "top"
        marked_cards = (
            self.rules_engine.get("limboDrawn", {}).get(container_id)
            if hasattr(self, "rules_engine") else None
        )
        if marked_cards and card_id in marked_cards:
            # Quasimillenary: cards drawn from Limbo are exiled instead of
            # returning to Limbo or the deck; they stay marked until they end
            # in the Vessel or the exile.
            if zone in {"deck", "graveyard"}:
                zone, position = "exile", "top"
            if zone in {"exile", "receptacle"}:
                marked_cards.remove(card_id)
        if position == "bottom":
            player["zones"][zone].append(card_id)
        else:
            player["zones"][zone].insert(0, card_id)
        player.setdefault("zoneOwners", {}).setdefault(zone, {})[card_id] = owner_id
        if (
            zone == "deck"
            and position == "bottom"
            and self.card_rules.get(card_id, {}).get(
                "shuffleWhenPutDeckBottom"
            )
        ):
            random.shuffle(player["zones"]["deck"])
        if hasattr(self, "rules_engine"):
            self.rules_engine.setdefault("zoneEntryTurns", {})[
                f"{container_id}:{zone}:{card_id}"
            ] = int(self.phase_tracker.get("turn") or 1)
        if zone in {"deck", "exile"} and hasattr(self, "rules_engine"):
            self.clear_rules_effect_memories(owner_id, card_id)
        return True

    @staticmethod
    def destination_error(card_owner_id, container_id, zone):
        if zone == "receptacle":
            if card_owner_id == container_id:
                return "A card cannot enter its owner's Empathic Vessel."
        elif card_owner_id != container_id:
            return "A card can only enter its owner's Deck, Hand, Limbo, or Exile."
        return None

    def rules_source_reservation_error(self, container_id, zone, card_id):
        if not self.rules_engine["enabled"] or zone != "hand":
            return None
        reserved = sum(
            1 for action in self.rules_engine["actionStack"]
            if action.get("controllerId") == container_id
            and not action.get("sourceOnStack")
            and (action.get("source") or {}).get("zone") == "hand"
            and (action.get("source") or {}).get("cardId") == card_id
        )
        available = self.players.get(container_id, {}).get("zones", {}).get("hand", []).count(card_id)
        if reserved and available <= reserved:
            return "A card declared in the Stack cannot leave your Hand before it resolves."
        return None

    def move_zone_card(self, from_container_id, from_zone, to_container_id, to_zone, card_id, position="top",
                       limbo_reason="discard"):
        owner_id = self.card_owner_in_zone(from_container_id, from_zone, card_id)
        if owner_id is None or card_id not in self.players[from_container_id]["zones"][from_zone]:
            return "Card not found in source zone.", None
        reservation_error = self.rules_source_reservation_error(from_container_id, from_zone, card_id)
        if reservation_error:
            return reservation_error, owner_id
        error = self.destination_error(owner_id, to_container_id, to_zone)
        if error:
            return error, owner_id
        self.take_zone_card(from_container_id, from_zone, card_id)
        self.put_zone_card(to_container_id, to_zone, card_id, owner_id, position)
        if (
            self.rules_engine.get("enabled")
            and to_zone == "graveyard"
            and from_zone in {"hand", "deck"}
        ):
            self.record_rules_limbo_entry(
                owner_id, card_id, limbo_reason, from_zone=from_zone
            )
            # Only a discard is a discard: a Tribute moved from the Hand is not
            if limbo_reason == "discard":
                self.record_rules_observed_event("cards_discarded", owner_id)
                if from_zone == "deck":
                    self.record_rules_observed_event("deck_cards_discarded", owner_id)
        if (
            self.rules_engine.get("enabled")
            and from_zone == "deck" and to_zone == "hand"
            and position == "bottom"
            and self.current_phase_id() not in {
                "recovery", "recovery_start", "recovery_draw", "recovery_end",
            }
            and to_container_id in self.players
        ):
            self.record_rules_observed_event("cards_drawn", to_container_id)
            drawn_log = self.rules_engine.setdefault("drawnOutsideRecovery", {})
            entry = drawn_log.get(to_container_id)
            if not entry or entry.get("turn") != self.phase_tracker["turn"]:
                entry = drawn_log[to_container_id] = {"turn": self.phase_tracker["turn"], "cardIds": []}
            entry["cardIds"].append(card_id)
        if to_zone in {"deck", "exile"}:
            self.clear_rules_effect_memories(owner_id, card_id)
        return None, owner_id

    def record_rules_limbo_entry(self, owner_id, card_id, reason, *,
                                 from_zone=None):
        if owner_id not in self.players or not card_id:
            return None
        entry = {
            "id": new_id(),
            "ownerId": owner_id,
            "cardId": card_id,
            "reason": str(reason or "")[:32],
            "fromZone": str(from_zone or "")[:32] or None,
            "turn": self.phase_tracker["turn"],
        }
        self.rules_engine.setdefault("recentLimboEntries", []).append(entry)
        self.record_rules_observed_event(
            "card_entered_limbo", owner_id, cardId=card_id, reason=entry["reason"],
        )
        if self.card_rules.get(card_id, {}).get("type") == "manifestation":
            self.record_rules_observed_event(
                "manifestation_entered_limbo", owner_id, cardId=card_id,
            )
        self.rules_engine["recentLimboEntries"] = [
            current
            for current in self.rules_engine["recentLimboEntries"]
            if int(current.get("turn") or 0) >= self.phase_tracker["turn"] - 1
        ]
        return entry

    def rules_points_changes_prevented(self):
        return any(
            effect.get("kind") == "prevent_point_changes"
            for effect in self.rules_engine.get("ongoingEffects") or []
        )

    def rules_score_count(self, count_kind, player_id, action):
        target_player_id = next((
            entry.get("playerId") for entry in action.get("targets") or []
            if entry.get("kind") == "player"
        ), None)
        if count_kind == "target_player_confrontation_non_token_manifestations":
            return (
                sum(
                    1 for entry in self.rules_confrontation_items(target_player_id)
                    if not entry.get("isTokenCard") and not entry.get("isCopy")
                )
                if target_player_id in self.players else 0
            )
        if count_kind == "own_interzone_manifestations":
            return sum(
                1 for entry in self.battlefield
                if self.rules_item_controller_id(entry) == player_id
                and self.rules_field_zone(entry) == "interzone"
                and self.card_rules.get(entry.get("cardId"), {}).get("type")
                == "manifestation"
            )
        if count_kind == "own_manifestations_in_vessels":
            return sum(
                1
                for container in self.players.values()
                for card_id in container["zones"]["receptacle"]
                if container["zoneOwners"].get("receptacle", {}).get(
                    card_id, container["id"]
                ) == player_id
                and self.card_rules.get(card_id, {}).get("type") == "manifestation"
            )
        if count_kind == "own_exhausted_cards":
            return sum(
                1 for entry in self.battlefield
                if self.rules_item_controller_id(entry) == player_id
                and int(round(float(entry.get("rotation") or 0))) % 180
            )
        if count_kind == "source_base_power":
            source_item = self.find_battlefield_item(
                (action.get("source") or {}).get("itemId")
            )
            return int(self.card_rules.get(
                (source_item or {}).get("cardId")
                or (action.get("source") or {}).get("cardId"), {}
            ).get("power") or 0)
        if count_kind == "source_current_power":
            source_item = self.find_battlefield_item(
                (action.get("source") or {}).get("itemId")
            )
            if source_item is not None:
                return max(
                    0,
                    int(self.rules_manifestation_characteristics(source_item)["power"]),
                )
            return max(0, int(self.card_rules.get(
                (action.get("source") or {}).get("cardId"), {}
            ).get("power") or 0))
        if count_kind == "source_card_points":
            return int((self.card_points or {}).get(
                (action.get("source") or {}).get("cardId"), 0
            ) or 0)
        if count_kind == "excess_power_over_target_first_manifestation":
            source_item = self.find_battlefield_item(
                (action.get("source") or {}).get("itemId")
            )
            first_item = self.find_battlefield_item(
                (self.rules_engine.get("firstManifestationItemIds") or {}).get(
                    target_player_id
                )
            )
            if source_item is None or first_item is None:
                return 0
            return max(
                0,
                self.rules_manifestation_characteristics(source_item)["power"]
                - self.rules_manifestation_characteristics(first_item)["power"],
            )
        return 0

    def adjust_rules_score(self, player_id, delta, observe=True):
        if player_id not in self.players:
            return 0
        delta = int(delta or 0)
        if delta and self.rules_points_changes_prevented():
            return 0
        if delta and self.rules_balance_redirect(player_id, delta, observe):
            return 0
        self.players[player_id]["score"] = int(
            self.players[player_id].get("score") or 0
        ) + delta
        if delta < 0:
            self.record_rules_observed_event("points_lost", player_id)
        elif delta > 0 and observe:
            self.record_rules_observed_event("points_gained", player_id)
        return delta

    def rules_vessel_total(self, player_id):
        """Points in a player's Empathic Vessel: card points plus effect points."""
        player = self.players[player_id]
        return int(player.get("score") or 0) + sum(
            int((self.card_points or {}).get(card_id, 0))
            for card_id in player["zones"]["receptacle"]
        )

    def rules_balance_redirect(self, player_id, delta, observe=True):
        """Balance of the Spirit: the richest player cannot gain nor the poorest lose."""
        if (
            not self.rules_engine.get("enabled")
            or getattr(self, "_balance_guard", False)
            or len(self.players) < 2
            or not self.rules_active_passive_sources("balance_points")
        ):
            return False
        totals = {pid: self.rules_vessel_total(pid) for pid in self.players}
        others = [pid for pid in self.players if pid != player_id]
        mine = totals[player_id]
        if delta > 0:
            blocked = all(mine > totals[pid] for pid in others)
        else:
            blocked = all(mine < totals[pid] for pid in others)
        if not blocked:
            return False
        self._balance_guard = True
        try:
            for pid in others:
                self.adjust_rules_score(pid, delta, observe)
        finally:
            self._balance_guard = False
        return True

    def record_rules_observed_event(self, kind, player_id, **data):
        """Remember an event that battlefield watchers react to at the next flush."""
        if not self.rules_engine.get("enabled") or player_id not in self.players:
            return
        self.rules_engine.setdefault("observedEvents", []).append(
            {"kind": kind, "playerId": player_id, **data}
        )

    def queue_rules_observed_event_triggers(self, defer=True):
        events = self.rules_engine.get("observedEvents") or []
        self.rules_engine["observedEvents"] = []
        grouped = []
        seen = set()
        for event in events:
            if event["kind"] in {
                "points_lost", "cards_discarded", "deck_cards_discarded", "cards_drawn",
                "points_gained",
            }:
                key = (event["kind"], event["playerId"])
                if key in seen:
                    continue
                seen.add(key)
            grouped.append(event)
        queued = []
        for event in grouped:
            if event["kind"] == "card_entered_limbo":
                card_id = event.get("cardId")
                event_names = ["enters_limbo"]
                if event.get("reason") == "discard":
                    event_names.append("discarded")
                for event_name in event_names:
                    queued.extend(self.queue_rules_triggers(
                        card_id, event["playerId"], event_name, zone="graveyard",
                        face_up=True, event_controller_id=event["playerId"],
                        defer=defer, controller_id=event["playerId"],
                    ))
                continue
            for source in list(self.battlefield):
                if not self.rules_item_effects_active(source):
                    continue
                queued.extend(self.queue_rules_triggers(
                    source.get("cardId"), source.get("ownerId"), event["kind"],
                    item_id=source.get("id"), face_up=True,
                    event_controller_id=event["playerId"], defer=defer,
                    controller_id=self.rules_item_controller_id(source),
                ))
        return queued

    def create_rules_effect_memory(self, owner_id, card_id, kind, *,
                                   controller_id=None, source_action_id=None,
                                   data=None):
        if owner_id not in self.players or not card_id or not kind:
            return None
        memory = {
            "id": new_id(),
            "ownerId": owner_id,
            "controllerId": (
                controller_id if controller_id in self.players else owner_id
            ),
            "cardId": card_id,
            "kind": kind,
            "sourceActionId": source_action_id,
            "createdTurn": self.phase_tracker["turn"],
            "data": dict(data or {}),
        }
        self.rules_engine["effectMemories"].append(memory)
        return memory

    def clear_rules_effect_memories(self, owner_id, card_id):
        removed = [
            memory for memory in self.rules_engine.get("effectMemories") or []
            if memory.get("ownerId") == owner_id
            and memory.get("cardId") == card_id
        ]
        if removed:
            removed_ids = {memory["id"] for memory in removed}
            self.rules_engine["effectMemories"] = [
                memory for memory in self.rules_engine["effectMemories"]
                if memory.get("id") not in removed_ids
            ]
        return removed

    def rules_effect_memories_for(self, owner_id, card_id, kind=None):
        return [
            memory for memory in self.rules_engine.get("effectMemories") or []
            if memory.get("ownerId") == owner_id
            and memory.get("cardId") == card_id
            and (kind is None or memory.get("kind") == kind)
        ]

    def remove_rules_effect_memory(self, memory_id):
        memory = next((
            entry for entry in self.rules_engine.get("effectMemories") or []
            if entry.get("id") == memory_id
        ), None)
        if memory:
            self.rules_engine["effectMemories"].remove(memory)
        return memory

    def suspend_zone_card(self, container_id, zone, card_id,
                          source_effect_id=None, **metadata):
        """Remove a card from normal game zones without treating it as Exiled."""
        owner_id = self.card_owner_in_zone(container_id, zone, card_id)
        if owner_id is None or card_id not in self.players[container_id]["zones"][zone]:
            return "Card not found in source zone.", None
        reservation_error = self.rules_source_reservation_error(container_id, zone, card_id)
        if reservation_error:
            return reservation_error, None
        self.take_zone_card(container_id, zone, card_id)
        suspended = {
            "id": new_id(),
            "cardId": card_id,
            "ownerId": owner_id,
            "fromContainerId": container_id,
            "fromZone": zone,
            "sourceEffectId": source_effect_id,
            **metadata,
        }
        self.rules_engine["suspendedCards"].append(suspended)
        return None, suspended

    def restore_suspended_card(self, suspension_id, zone="hand", position="top"):
        suspended = next((
            entry for entry in self.rules_engine.get("suspendedCards") or []
            if entry.get("id") == suspension_id
        ), None)
        if suspended is None:
            return "Suspended card not found.", None
        owner_id = suspended.get("ownerId")
        if owner_id not in self.players or zone not in ALL_ZONES:
            return "Suspended card cannot return to that zone.", None
        error = self.destination_error(owner_id, owner_id, zone)
        if error:
            return error, None
        self.rules_engine["suspendedCards"].remove(suspended)
        self.put_zone_card(owner_id, zone, suspended["cardId"], owner_id, position)
        return None, suspended

    def rules_active_suspension_source(self, zone):
        threshold_key = "graveyard" if zone == "graveyard" else zone
        candidates = []
        for item in self.rules_confrontation_items():
            if not self.rules_item_effects_active(item):
                continue
            threshold = self.rules_item_card_rules(item).get(
                "suspensionThresholds", {}
            ).get(threshold_key)
            if (
                isinstance(threshold, (int, float))
                and self.rules_manifestation_characteristics(item)["power"] >= threshold
            ):
                candidates.append(item)
        return candidates[0] if candidates else None

    def rules_hands_are_immune(self):
        return any(
            self.rules_manifestation_characteristics(item)["power"]
            >= int(self.rules_item_card_rules(item).get(
                "suspensionThresholds", {}
            ).get("handImmunity") or 999)
            for item in self.rules_confrontation_items()
            if self.rules_item_effects_active(item)
            if self.rules_item_card_rules(item).get(
                "suspensionThresholds", {}
            ).get("handImmunity")
        )

    def rules_hand_is_immune(self, player_id, controller_id):
        if self.rules_hands_are_immune():
            return True
        if player_id == controller_id:
            return False
        return any(
            self.rules_item_controller_id(source) == player_id
            for source in self.rules_active_passive_sources(
                "protect_controller_hand"
            )
        ) or bool(self.rules_active_passive_sources(
            "mutual_opponent_immunity"
        ))

    def release_rules_suspended_by(self, source_item_id, exile=False):
        released = [
            entry for entry in self.rules_engine.get("suspendedCards") or []
            if entry.get("sourceEffectId") == source_item_id
        ]
        if not released:
            return []
        released_ids = {entry["id"] for entry in released}
        self.rules_engine["suspendedCards"] = [
            entry for entry in self.rules_engine["suspendedCards"]
            if entry.get("id") not in released_ids
        ]
        shuffled_owner_ids = set()
        for entry in released:
            owner_id = entry.get("ownerId")
            zone = "exile" if exile else entry.get("returnZone") or "deck"
            self.put_zone_card(
                owner_id, zone, entry.get("cardId"), owner_id,
                "bottom" if zone == "deck" else "top"
            )
            if not exile and zone == "deck":
                shuffled_owner_ids.add(owner_id)
        for owner_id in shuffled_owner_ids:
            random.shuffle(self.players[owner_id]["zones"]["deck"])
        return [{
            "suspensionId": entry.get("id"),
            "cardId": entry.get("cardId"),
            "ownerId": entry.get("ownerId"),
            "destination": (
                "exile" if exile else entry.get("returnZone") or "deck"
            ),
        } for entry in released]

    def expire_rules_temporary_suspensions(self, completed_turn):
        expired = [
            entry for entry in self.rules_engine.get("suspendedCards") or []
            if entry.get("returnZone")
            and int(entry.get("returnTurn") or 0) <= int(completed_turn)
        ]
        for entry in expired:
            self.rules_engine["suspendedCards"].remove(entry)
            owner_id = entry.get("ownerId")
            self.put_zone_card(
                owner_id, entry.get("returnZone"), entry.get("cardId"),
                owner_id, "top",
            )
        return expired

    def move_zone_card_by_effect(self, from_container_id, from_zone,
                                 to_container_id, to_zone, card_id,
                                 position="top"):
        owner_id = self.card_owner_in_zone(
            from_container_id, from_zone, card_id
        )
        if from_zone == "hand" and self.rules_hands_are_immune():
            return "Cards in Hand are Immune to cards and effects.", owner_id, None
        suspension_source = next((
            source for zone in {from_zone, to_zone}
            if zone in {"deck", "graveyard"}
            for source in [self.rules_active_suspension_source(zone)]
            if source is not None
        ), None)
        if suspension_source:
            error, suspended = self.suspend_zone_card(
                from_container_id, from_zone, card_id,
                source_effect_id=suspension_source.get("id"),
            )
            return error, owner_id, ({
                "status": "suspended",
                "suspensionId": suspended.get("id"),
                "sourceItemId": suspension_source.get("id"),
                "cardId": card_id,
                "ownerId": owner_id,
            } if suspended else None)
        error, owner_id = self.move_zone_card(
            from_container_id, from_zone,
            to_container_id, to_zone, card_id, position,
        )
        if (
            not error
            and from_zone in {"graveyard", "receptacle"}
            and self.card_rules.get(card_id, {}).get("type") == "manifestation"
        ):
            self.record_rules_observed_event(
                "manifestation_left_by_effect", from_container_id,
                cardId=card_id,
            )
        return error, owner_id, None

    def reset_cards_to_owners(self):
        self.forget_revealed_hand()
        cards_by_owner = {pid: [] for pid in self.players}
        for container_id, player in self.players.items():
            for zone, cards in player["zones"].items():
                for card_id in cards:
                    owner_id = self.card_owner_in_zone(container_id, zone, card_id)
                    if owner_id in cards_by_owner:
                        cards_by_owner[owner_id].append(card_id)
        for item in self.battlefield:
            if not item.get("isTokenCard") and not item.get("isCopy") and item.get("ownerId") in cards_by_owner:
                cards_by_owner[item["ownerId"]].append(item["cardId"])
        for suspended in self.rules_engine.get("suspendedCards") or []:
            if suspended.get("ownerId") in cards_by_owner:
                cards_by_owner[suspended["ownerId"]].append(suspended["cardId"])
        for owner_id, player in self.players.items():
            player["zones"] = {zone: [] for zone in ALL_ZONES}
            player["zoneOwners"] = {zone: {} for zone in ALL_ZONES}
            player["zones"]["deck"] = cards_by_owner[owner_id]
            player["zoneOwners"]["deck"] = {card_id: owner_id for card_id in cards_by_owner[owner_id]}
        self.battlefield = []
        self.rules_engine["suspendedCards"] = []
        self.rules_engine["effectMemories"] = []
        self.prune_rules_ongoing_effects()

    def reset_cards_to_active_decks(self, decks_by_player):
        """Discard every live card location and rebuild from saved deck definitions."""
        self.forget_revealed_hand()
        self.battlefield = []
        self.rules_engine["suspendedCards"] = []
        self.rules_engine["effectMemories"] = []
        self.prune_rules_ongoing_effects()
        for player_id, player in self.players.items():
            active = decks_by_player.get(player_id) or {}
            card_ids = list(active.get("cardIds") or [])
            player["zones"] = {zone: [] for zone in ALL_ZONES}
            player["zoneOwners"] = {zone: {} for zone in ALL_ZONES}
            player["zones"]["deck"] = card_ids
            player["zoneOwners"]["deck"] = {card_id: player_id for card_id in card_ids}
            player["cardRarities"] = dict(active.get("cardRarities") or {})
            player["sideboard"] = list(active.get("sideboardIds") or [])
            player["deckDefinition"] = active.get("deckDefinition")

    def replace_player_deck(self, player_id, card_ids, sideboard_ids, card_rarities, deck_definition):
        """Reset one player's physical cards without disturbing the opponent's board."""
        self.forget_revealed_hand(player_id)
        player = self.players[player_id]
        for container_id, container in self.players.items():
            for zone, cards in container["zones"].items():
                kept = [
                    card_id for card_id in cards
                    if self.card_owner_in_zone(container_id, zone, card_id) != player_id
                ]
                container["zones"][zone] = kept
                owners = container.setdefault("zoneOwners", {}).setdefault(zone, {})
                container["zoneOwners"][zone] = {
                    card_id: owners.get(card_id, container_id) for card_id in kept
                }
        player["zones"]["deck"] = list(card_ids)
        player["zoneOwners"]["deck"] = {card_id: player_id for card_id in card_ids}
        self.battlefield = [item for item in self.battlefield if item.get("ownerId") != player_id]
        self.rules_engine["suspendedCards"] = [
            entry for entry in self.rules_engine.get("suspendedCards") or []
            if entry.get("ownerId") != player_id
        ]
        self.rules_engine["effectMemories"] = [
            memory for memory in self.rules_engine.get("effectMemories") or []
            if memory.get("ownerId") != player_id
        ]
        self.prune_rules_ongoing_effects()
        player["cardRarities"] = dict(card_rarities)
        player["sideboard"] = list(sideboard_ids)
        player["deckDefinition"] = deck_definition
