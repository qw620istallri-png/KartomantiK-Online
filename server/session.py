"""In-memory session/game-state model for Kartomantik Online.

Sessions hold zones, the shared tabletop, visibility permissions and the
optional assisted-rules beta state.  Card effects remain player-led for now;
the beta only owns rules that can already be proven from shared state.
"""
import random
import re
import string
import time
import uuid
import math

PRIVATE_ZONES = {"deck", "hand", "exile"}
SHARED_ZONES = {"graveyard", "receptacle"}
RULES_SCORE_COUNTS = {
    "own_interzone_manifestations",
    "target_player_confrontation_non_token_manifestations",
    "own_manifestations_in_vessels",
    "excess_power_over_target_first_manifestation",
    "source_base_power",
    "source_current_power",
    "source_card_points",
}
RULES_AFTER_CHAIN = {
    "discard_deck_per_base_power", "power_counter_target_per_base_power",
}
ALL_ZONES = PRIVATE_ZONES | SHARED_ZONES

NORMAL_PHASES = ("recovery", "confrontation", "resolution", "end")
ADVANCED_PHASES = (
    "recovery_start", "recovery_draw", "recovery_end",
    "confrontation_choose", "confrontation_before_revelation", "confrontation_reveal",
    "confrontation_immediate", "confrontation_entry", "confrontation_reaction",
    "resolution_compare", "resolution_effects", "resolution_move",
    "end_actions", "end_triggers", "end_expire",
)
PHASE_GROUP = {phase_id: phase_id.split("_", 1)[0] for phase_id in ADVANCED_PHASES}

SESSION_TTL_SECONDS = 6 * 60 * 60  # expire an inactive session after 6h

# On-field pile SCREEN positions are no longer server state at all — they're
# a pure function of (viewer's seat, pile owner's seat, zone), with no runtime
# transform/mirroring involved, so they live entirely client-side now (see
# PILE_SCREEN_POS in app.js). That replaced an earlier attempt at deriving a
# single mirrored pair of clusters from one axis: dragging a pile while
# actually viewing it directly, vs. viewing that same pile from the OTHER
# seat (mirrored), gave measurably different "looks right" coordinates — i.e.
# no single per-owner position can look correct from both viewpoints at once.
# The only fix is a value per (viewer, owner, zone) triple, which needs no
# server involvement since it depends on nothing session-specific.
NUM_SEATS = 2
READ_ONLY_ROLES = {"observer", "spectator", "judge", "organizer"}
PRIVILEGED_VIEW_ROLES = {"observer", "judge"}
RULES_ACTION_KINDS = {
    "manual", "play_card", "activated_effect", "triggered_effect",
}
TRIBUTE_SYMBOL_TEMPERAMENT = {
    "G": "phlegmatic",
    "B": "vitreous",
    "P": "melancholic",
    "Y": "capricious",
    "R": "choleric",
    "H": "hollow",
    "T": "transcendent",
}
RULES_WILL_TYPES = {"ephemeral_will", "persistent_will"}
RULES_DESTROY_MATCHES = {
    "entered_support_this_turn", "won_confrontation_this_turn",
}
RULES_EFFECT_DURATIONS = {
    "until_end_of_turn",
    "until_end_of_next_turn",
    "while_source_and_target_on_field",
    "while_target_on_field",
    "until_resolution",
}
RULES_TEMPERAMENTS = {
    "capricious", "choleric", "hollow", "melancholic", "phlegmatic",
    "transcendent", "vitreous",
}
RULES_COPIED_EFFECT_KEYS = {
    "adamant", "float", "persist", "canPayTribute", "suspensionThresholds",
    "canPayTributeFromInterzone", "interzoneTributePower",
    "supportFromHand", "supportFromHandCondition", "supportFromInterzone",
    "supportFromStalemate",
    "lossDestination", "supportWhenNoCounter", "supportCondition",
    "playOnlyEmptyStack", "supportWinDestination", "supportWinEffect",
    "continuousPowerRules", "activatedAbilities", "triggeredAbilities",
    "playPermissions", "passiveEffects",
}
TEMPERAMENT_DOMINANCE = {
    "phlegmatic": {"vitreous", "capricious"},
    "vitreous": {"melancholic", "choleric"},
    "melancholic": {"capricious", "phlegmatic"},
    "capricious": {"choleric", "vitreous"},
    "choleric": {"phlegmatic", "melancholic"},
    "transcendent": {"phlegmatic", "vitreous", "melancholic", "capricious", "choleric", "hollow"},
    "hollow": set(),
}


def gen_code(length=6):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I ambiguity
    return "".join(random.choices(alphabet, k=length))


def new_id():
    return uuid.uuid4().hex[:12]


def validate_tournament_deck(card_ids, sideboard_ids, card_points, policy=None, card_labels=None, limit_bonus=0):
    policy = policy or {}
    card_labels = card_labels or {}
    label = lambda card_id: card_labels.get(card_id, card_id)
    if len(card_ids) != 30 or len(set(card_ids)) != 30:
        return "A tournament deck must contain exactly 30 unique cards."
    if len(sideboard_ids) > 6 or len(set(sideboard_ids)) != len(sideboard_ids):
        return "A tournament sideboard may contain at most 6 unique cards."
    if set(card_ids) & set(sideboard_ids):
        return "A card cannot be in both the tournament deck and sideboard."
    if any(card_id not in card_points for card_id in card_ids + sideboard_ids):
        return "The tournament deck contains an unknown card."
    point_limit = 500 + max(0, int(limit_bonus or 0))
    if sum(card_points[card_id] for card_id in card_ids) > point_limit:
        return f"A tournament deck cannot exceed {point_limit} points."
    combined = set(card_ids + sideboard_ids)
    banned = [card_id for card_id in policy.get("bannedCardIds", []) if card_id in combined]
    if banned:
        return "Banned card(s): " + ", ".join(label(card_id) for card_id in banned) + "."
    for group in policy.get("restrictedGroups", []):
        present = [card_id for card_id in group.get("cardIds", []) if card_id in combined]
        if len(present) > 1:
            group_name = group.get("name") or "Restricted group"
            return f'{group_name}: only one of these cards is allowed across deck and sideboard ({", ".join(label(card_id) for card_id in present)}).'
    return None


def normalize_role(role):
    """Accept the old observer boolean while newer callers use named roles."""
    if isinstance(role, bool):
        return "observer" if role else "player"
    return role or "player"


def make_player(player_id, name, cluster_index=0, seat=None):
    seat = cluster_index % NUM_SEATS if seat is None else int(seat)
    return {
        "id": player_id,
        "name": name,
        "connected": False,
        "score": 0,
        "seat": seat,
        "zones": {zone: [] for zone in ALL_ZONES},
        # Cards remain owned by the player who imported them even while they
        # sit in an opponent's Empathic Vessel. Values are keyed by card id;
        # Kartomantik decks contain unique cards, so this stays unambiguous.
        "zoneOwners": {zone: {} for zone in ALL_ZONES},
        "cardRarities": {},
        "deckDefinition": None,
        # The sideboard is deliberately not a game zone: it stays private,
        # does not count as the Deck, and cards can only enter play after a
        # fresh validated deck import.
        "sideboard": [],
        "activity": None,  # transient "what menu are they in" hint, never private
    }


class Session:
    def __init__(self, mode="casual", tournament_policy=None, card_points=None, card_labels=None,
                 manifestation_ids=None, card_rules=None, rules_beta=False, ban_list_enabled=False):
        self.mode = "tournament" if mode == "tournament" else "casual"
        self.status = "lobby" if self.mode == "tournament" else "active"
        self.code_player = gen_code() if self.mode == "casual" else None
        self.code_observer = gen_code() if self.mode == "casual" else None
        self.code_player1 = gen_code(8) if self.mode == "tournament" else None
        self.code_player2 = gen_code(8) if self.mode == "tournament" else None
        self.code_spectator = gen_code(8) if self.mode == "tournament" else None
        self.code_judge = gen_code(8) if self.mode == "tournament" else None
        self.code_organizer = gen_code(10) if self.mode == "tournament" else None
        self.seat_claims = {0: None, 1: None}
        self.tournament_policy = tournament_policy or {"bannedCardIds": [], "restrictedGroups": []}
        self.ban_list_enabled = self.mode == "tournament" or bool(ban_list_enabled)
        self.card_points = None if card_points is None else dict(card_points)
        self.card_labels = card_labels or {}
        self.manifestation_ids = set(manifestation_ids or ())
        self.card_rules = {card_id: dict(metadata) for card_id, metadata in (card_rules or {}).items()}
        self.players = {}  # player_id -> player dict, in join order
        self.battlefield = []  # list of dict: id, ownerId, cardId, x, y, faceUp, rotation, counters
        self.tokens = []  # list of dict: id, ownerId, x, y, label, color, counters
        self.strokes = []  # freehand annotation strokes: id, ownerId, color, points:[[x,y],...]
        self.log = []  # chronological, sequence-numbered audit trail
        self.log_sequence = 0
        self.pending_hand_requests = {}  # requestId -> {requesterId, targetId, index, action}
        self.rules_engine = {
            "enabled": bool(rules_beta),
            "deckConfirmedPlayerIds": [],
            "openingHandPlayerIds": [],
            "mulliganPlayerIds": [],
            "openingMulliganRequiredPlayerIds": [],
            "openingMulliganFailedPlayerIds": [],
            "readyPlayerIds": [],
            "recoveryDrawTurn": None,
            "recoveryMulliganTurn": None,
            "recoveryMulliganPlayerIds": [],
            "recoveryMulliganRequiredPlayerIds": [],
            "recoveryMulliganFailedPlayerIds": [],
            "beginningTriggersTurn": None,
            "beginningPermissionsTurn": None,
            "playPermissions": [],
            "supportEntries": [],
            "playRestrictions": [],
            "zoneEntryTurns": {},
            "recentLimboEntries": [],
            "handLimitEffects": [],
            "outcome": None,
            "priorityPlayerId": None,
            "priorityPasses": [],
            "actionStack": [],
            "deferredSimultaneousActions": [],
            "suspendedCards": [],
            "lastResolvedAction": None,
            "ongoingEffects": [],
            "effectMemories": [],
            "pendingChoice": None,
            "firstManifestationItemIds": {},
            "firstManifestationValidatedPlayerIds": [],
            "firstManifestationComplete": False,
            "firstManifestationTriggersQueued": False,
            "confrontationEntrySequence": 0,
            "confrontationResult": None,
            "lastConfrontationWinnerId": None,
            "rematchPending": None,
            "forcedConfrontationWinnerId": None,
        }
        self.phase_tracker = {
            "enabled": bool(rules_beta),
            "advanced": bool(rules_beta),
            "index": 0,
            "turn": 1,
        }
        self.phase_passes = set()
        self.pending_searches = {}
        self.audit_alerts = []
        self.created_at = time.time()
        self.last_activity = time.time()
        self.ended = False

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

    def player_for_seat(self, seat):
        return next((player for player in self.players.values() if player.get("seat") == seat), None)

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

    def move_zone_card(self, from_container_id, from_zone, to_container_id, to_zone, card_id, position="top"):
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
                owner_id, card_id, "discard", from_zone=from_zone
            )
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
        self.players[player_id]["score"] = int(
            self.players[player_id].get("score") or 0
        ) + delta
        if delta < 0:
            self.record_rules_observed_event("points_lost", player_id)
        elif delta > 0 and observe:
            self.record_rules_observed_event("points_gained", player_id)
        return delta

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
        return error, owner_id, None

    def reset_cards_to_owners(self):
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

    # -- shared phase tracker -------------------------------------------
    def phase_sequence(self):
        return ADVANCED_PHASES if self.phase_tracker["advanced"] else NORMAL_PHASES

    def current_phase_id(self):
        sequence = self.phase_sequence()
        return sequence[min(self.phase_tracker["index"], len(sequence) - 1)]

    def current_phase_group(self):
        phase_id = self.current_phase_id()
        return PHASE_GROUP.get(phase_id, phase_id)

    def configure_phases(self, enabled=None, advanced=None):
        if self.rules_engine["enabled"]:
            # Assisted rules use the exact rulebook steps. They are selected
            # before the match and cannot silently fall back to the four-step
            # presentation once play has started.
            self.phase_tracker["enabled"] = True
            self.phase_tracker["advanced"] = True
            return
        # Showing or hiding the phase bubbles is client-local. Even a direct
        # enabled toggle must preserve the shared phase, turn, and pass state.
        if enabled is not None:
            self.phase_tracker["enabled"] = bool(enabled)
        if advanced is not None and bool(advanced) != self.phase_tracker["advanced"]:
            current_group = self.current_phase_group()
            self.phase_tracker["advanced"] = bool(advanced)
            sequence = self.phase_sequence()
            self.phase_tracker["index"] = next(
                (index for index, phase_id in enumerate(sequence) if PHASE_GROUP.get(phase_id, phase_id) == current_group),
                0,
            )
            self.phase_passes.clear()

    def pass_phase(self, player_id, passed=None):
        if self.ended or not self.phase_tracker["enabled"] or player_id not in self.players:
            return None
        # New clients send the state they want, making pass/cancel idempotent
        # across delayed or duplicated websocket messages. ``None`` preserves
        # the toggle semantics used by older clients.
        if passed is False or (passed is None and player_id in self.phase_passes):
            self.phase_passes.discard(player_id)
            return "cancelled"
        if passed is True and player_id in self.phase_passes:
            return "passed"
        self.phase_passes.add(player_id)
        player_ids = list(self.players)
        if len(player_ids) < 2 or not all(pid in self.phase_passes for pid in player_ids):
            return "passed"
        sequence = self.phase_sequence()
        next_index = self.phase_tracker["index"] + 1
        if next_index >= len(sequence):
            next_index = 0
            self.phase_tracker["turn"] += 1
        self.phase_tracker["index"] = next_index
        self.phase_passes.clear()
        return "advanced"

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
                and entry.get("cardId") == card_id
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
            if not item.get("faceUp"):
                return "A face-down card cannot declare an effect.", None
            if kind == "play_card" and not as_support:
                return "A card already on the field cannot be played again.", None
            if as_support:
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
            "cardType": metadata.get("type"),
            "ownerId": (
                self.card_owner_in_zone(player_id, "hand", card_id)
                if zone == "hand" else (
                    self.card_owner_in_zone(container_id, zone, card_id)
                        if zone == "graveyard" else (
                            suspension.get("ownerId")
                            if zone == "suspended"
                            else self.find_battlefield_item(item_id).get("ownerId")
                        )
                    )
            ),
            "controllerId": player_id,
        }
        if zone == "hand" and kind == "activated_effect":
            clean_source["activatedFromZone"] = "hand"
        if zone == "hand" and permission:
            clean_source.update({
                "permissionId": permission.get("id"),
                "noTribute": bool(permission.get("noTribute")),
            })
        if zone == "graveyard":
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
            return action.get("kind") in {"activated_effect", "triggered_effect"}
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

    def rules_action_targets(self, targets):
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
                if not container_id or zone not in SHARED_ZONES or not card_id:
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

    @staticmethod
    def clean_rules_action_result(result):
        if not isinstance(result, dict):
            return None
        kind = result.get("kind")
        if kind == "chain_from_zone":
            return Session.clean_rules_trigger_result(result)
        if kind == "move_source_to_owner_hand":
            return {"kind": kind}
        if kind == "draw_owner" and isinstance(result.get("value"), (int, float)):
            return {"kind": kind, "value": max(0, min(int(result["value"]), 50))}
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
                temperament not in RULES_TEMPERAMENTS
                or not isinstance(value, (int, float))
            ):
                return None
            clean = {
                "kind": kind,
                "temperament": temperament,
                "value": max(1, min(int(value), 20)),
            }
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
            "unless_opponent_payment_lock_support_entries",
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
        if kind == "roll_multiple_even_power_odd_discard":
            rolls = result.get("rolls")
            if not isinstance(rolls, (int, float)):
                return None
            return {"kind": kind, "rolls": max(1, min(int(rolls), 20))}
        if kind == "score_controller_by_source_roll_then_exile":
            return {"kind": kind}
        if kind in {
            "force_win_if_highest_base_first",
            "skip_confrontation_unless_points",
            "end_confrontation_relocate_all",
            "suspend_opponent_hand_will",
        }:
            clean = {"kind": kind}
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
            field_zones_by_type = target_rules.get("fieldZonesByType") or {}
            allowed_field_zones = field_zones_by_type.get(metadata.get("type"))
            if (
                isinstance(allowed_field_zones, list)
                and self.rules_field_zone(item) not in allowed_field_zones
            ):
                return "This effect requires this card type in a different field zone."
            if target_rules.get("supportOnly") and not item.get("isSupport"):
                return "This effect requires a Manifestation in Support."
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
            if source_item is not None
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
            if str(zone) in {"hand", "battlefield"}
        ]
        if source_zones and source.get("zone") not in source_zones:
            return "This ability cannot be activated from the source card's current zone.", None

        condition = str(ability.get("condition") or "")
        if condition == "controller_lost_confrontation":
            confrontation = self.rules_engine.get("confrontationResult") or {}
            if (
                confrontation.get("turn") != self.phase_tracker["turn"]
                or confrontation.get("loserId") != player_id
            ):
                return "This ability requires you to have lost the current confrontation.", None

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

        if ability.get("exhaustSource"):
            item = self.find_battlefield_item(source.get("itemId"))
            if item is None or int(round(float(item.get("rotation") or 0))) % 180:
                return "The source card is already exhausted.", None
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
        use_limit = max(0, min(int(ability.get("useLimit") or 0), 99))
        if use_limit:
            used = int(((
                self.find_battlefield_item(source.get("itemId")) or {}
            ).get("abilityUses") or {}).get(str(ability.get("id")), 0))
            if used >= use_limit:
                return f"This effect can be used at most {use_limit} times.", None
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
                    "global",
                }:
                    clean["scope"] = ongoing_effect["scope"]
                if ongoing_effect.get("excludeSource"):
                    clean["excludeSource"] = True
                if ongoing_effect.get("fromOpponents"):
                    clean["fromOpponents"] = True
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
        allowed_target_keys = {
            "kind", "min", "max", "cardType", "cardTypes", "zones", "controller",
            "fieldZone", "supportOnly", "maxPoints", "maxPower", "minPower",
            "excludeEventSource",
            "sourceOnly", "fieldZonesByType", "enteredThisTurn", "enteredInterzoneThisTurn", "confrontationOutcome", "owner",
            "firstManifestationOnly",
            "counter", "minCounters", "limboReasons", "container",
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
            "useLimit": max(0, min(int(ability.get("useLimit") or 0), 99)) or None,
            "additionalCost": (
                "exile_hand_manifestation"
                if ability.get("additionalCost") == "exile_hand_manifestation" else None
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
                for group in ability.get("targetGroups") or []
                if isinstance(group, dict)
            ],
        }

    @staticmethod
    def rules_requirements_from_symbols(power_cost):
        requirements = {}
        symbols = re.findall(r"\{([A-Z])\}", str(power_cost or ""))
        for symbol in symbols:
            temperament = TRIBUTE_SYMBOL_TEMPERAMENT.get(symbol)
            if temperament:
                requirements[temperament] = requirements.get(temperament, 0) + 1
        return requirements

    def rules_tribute_requirements(self, kind, source, ability=None,
                                   player_id=None):
        if ability and ability.get("tribute") is not None:
            return self.rules_requirements_from_symbols(ability.get("tribute")), True
        if kind != "play_card" or not source:
            return {}, False
        if source.get("noTribute"):
            return {}, True
        metadata = self.card_rules.get(source.get("cardId"), {})
        if metadata.get("type") not in RULES_WILL_TYPES:
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
            base_power = int(self.card_rules.get(
                (first_item or {}).get("cardId"), {}
            ).get("power") or 0)
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

    def rules_manifestations_cover(self, card_ids, requirements, include_excess=False):
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
            cards.append((card_id, metadata, max(0, power)))
        cards.sort(key=lambda item: "transcendent" in (
            item[1].get("tributeTemperaments")
            or item[1].get("temperaments")
            or []
        ))
        for _card_id, metadata, power in cards:
            printed_temperament = next(
                iter(metadata.get("temperaments") or []), None
            )
            tribute_temperaments = list(
                metadata.get("tributeTemperaments")
                or metadata.get("temperaments")
                or []
            )
            temperament = printed_temperament
            used = 0
            if "transcendent" in tribute_temperaments:
                temperament = "transcendent"
                for required_temperament in remaining:
                    amount = min(power - used, remaining[required_temperament])
                    remaining[required_temperament] -= amount
                    used += amount
                    if used >= power:
                        break
            else:
                payable = next((
                    candidate for candidate in tribute_temperaments
                    if candidate in remaining and remaining[candidate] > 0
                ), None)
                if payable is None and remaining.get("hollow", 0) > 0:
                    payable = "hollow"
                if payable in remaining:
                    used = min(power, remaining[payable])
                    remaining[payable] -= used
                    if payable != "hollow":
                        temperament = payable
            if include_excess and power > used and temperament:
                excess[temperament] = excess.get(temperament, 0) + power - used
        covered = all(amount <= 0 for amount in remaining.values())
        return covered, excess

    def rules_action_payment(self, player_id, kind, source, payment_card_ids,
                             ability=None, targets=None,
                             extra_essence_count=0):
        if payment_card_ids is None:
            payment_card_ids = []
        if not isinstance(payment_card_ids, list):
            return "Tribute cards must be supplied as a list.", None
        clean_refs = [str(card_id or "") for card_id in payment_card_ids if str(card_id or "")]
        clean_entries = []
        for reference in clean_refs:
            zone, separator, card_id = reference.partition("|")
            if not separator:
                zone, card_id = "hand", reference
            if zone not in {"hand", "graveyard", "battlefield"}:
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
        for entry in clean_entries:
            card_id = entry["cardId"]
            key = (entry["zone"], card_id)
            requested_counts[key] = requested_counts.get(key, 0) + 1
            reserved_source = 1 if source and source.get("zone") == "hand" and source.get("cardId") == card_id else 0
            if entry["zone"] == "hand":
                if requested_counts[key] > hand.count(card_id) - reserved_source:
                    return "A selected Tribute card is no longer in your Hand.", None
            else:
                if entry["zone"] == "battlefield":
                    item = self.find_battlefield_item(entry.get("itemId"))
                    metadata = self.card_rules.get(card_id, {})
                    if (
                        item is None
                        or self.rules_item_controller_id(item) != player_id
                        or self.rules_field_zone(item) != "interzone"
                        or not metadata.get("canPayTributeFromInterzone")
                    ):
                        return "A selected Manifestation cannot pay Tribute from the Interzone.", None
                    continue
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
                clean_entries, essence_remaining, include_excess=True
            )
            if not covered:
                return "The selected Manifestations do not pay the full printed Tribute.", None
            for index in range(len(clean_ids)):
                reduced_payment = clean_entries[:index] + clean_entries[index + 1:]
                if self.rules_manifestations_cover(
                    reduced_payment, essence_remaining
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
        return None, {
            "cardIds": clean_ids,
            "cardEntries": clean_entries,
            "requirements": requirements,
            "essenceSpent": essence_spent,
            "excessEssence": [
                {"temperament": temperament, "amount": amount}
                for temperament, amount in excess.items() if amount > 0
            ],
            "validated": enforce_printed_cost,
            "optionalExtraEssenceSpent": optional_extra_count,
            "limboTributeSourceItemId": (
                limbo_source.get("id") if limbo_count and limbo_source else None
            ),
        }

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

    def rules_next_pick_own_item_choice(self, queue, action_id, source_card_id, done):
        head, rest = queue[0], queue[1:]
        choice = {
            "id": new_id(), "kind": "pick_own_item",
            "playerId": head["playerId"],
            "candidateItemIds": list(head["candidateItemIds"]),
            "purpose": "stalemate",
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
        for index, entry in enumerate(generated):
            temperament = entry["temperament"]
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
                movements.append({
                    "cardId": card_id, "ownerId": item.get("ownerId"),
                    "fromZone": "interzone",
                    "destination": "graveyard",
                    "itemId": item.get("id"),
                    "status": movement.get("status"),
                })
                continue
            owner_id = self.card_owner_in_zone(player_id, from_zone, card_id)
            if from_zone == "graveyard":
                error, _owner_id, replacement = self.move_zone_card_by_effect(
                    player_id, "graveyard", owner_id, "exile",
                    card_id, "top",
                )
                if error or replacement:
                    raise RuntimeError(
                        "Validated Limbo Tribute payment failed."
                    )
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
                    "x": 650.0, "y": 520.0 if seat != 1 else 980.0,
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
                player_id, "hand", owner_id, zone, card_id, position
            )
            if error:
                raise RuntimeError(f"Validated Tribute payment failed: {error}")
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
        reduction = int(ability.get("reduceSourcePower") or 0)
        if reduction > 0:
            if item is None:
                raise RuntimeError("Validated Reduce source disappeared before payment.")
            counters = item.setdefault("counters", {})
            counters["power"] = int(counters.get("power") or 0) - reduction
            result["reducedSourcePower"] = reduction
        if int(ability.get("useLimit") or 0) > 0 and item is not None:
            uses = item.setdefault("abilityUses", {})
            uses[str(ability.get("id"))] = int(uses.get(str(ability.get("id"))) or 0) + 1
        return result

    def resolve_rules_action_source(self, action):
        source = action.get("source") or {}
        if action.get("isStackCopy"):
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
            if player is None or not source_on_stack or owner_id not in self.players:
                return {"status": "source_missing", "destination": "battlefield", "asSupport": True}
            placement = action.get("placement") or {}
            stored_item = action.get("sourceBattlefieldItem")
            from_zone = (
                stored_item.get("fieldZone")
                if isinstance(stored_item, dict)
                else None
            ) or source.get("zone")
            item = dict(stored_item) if isinstance(stored_item, dict) else {
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
            if source.get("temperamentOverride") in RULES_TEMPERAMENTS:
                item["temperamentOverride"] = source["temperamentOverride"]
            if source.get("winAsSupportDestination") == "exile":
                item["supportWinDestination"] = "exile"
            self.mark_rules_support_entry(item)
            self.battlefield.append(item)
            self.transfer_rules_stack_protection(action, item)
            return {
                "status": "moved", "destination": "battlefield", "itemId": item["id"],
                "cardId": card_id, "ownerId": owner_id, "x": item["x"], "y": item["y"],
                "asSupport": True, "fromZone": from_zone,
                "enteredBattlefield": source.get("zone") != "battlefield",
            }
        if source.get("zone") not in {"hand", "suspended"}:
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
                "rarity": (self.players.get(owner_id) or {}).get("cardRarities", {}).get(card_id),
                "stackedOn": None,
            }
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
        if action.get("kind") != "play_card" or not action.get("sourceOnStack"):
            return None
        owner_id = source.get("ownerId")
        card_id = source.get("cardId")
        if owner_id not in self.players or not card_id:
            return {"status": "source_missing", "destination": "graveyard"}
        if destination not in {"graveyard", "hand"}:
            destination = "graveyard"
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

    @staticmethod
    def clean_rules_action_placement(kind, source, placement, as_support=False):
        if kind != "play_card" or (
            not as_support and (source or {}).get("cardType") != "persistent_will"
        ):
            return None
        return Session.clean_rules_board_position(placement)

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
        if duration == "while_source_and_target_on_field" and source_on_field is None:
            return []
        if definition.get("scope") == "all_manifestations_on_field":
            targets = [
                {"kind": "card", "itemId": item["id"], "cardId": item["cardId"], "ownerId": item["ownerId"]}
                for item in self.battlefield
                if item.get("faceUp") and self.card_rules.get(item.get("cardId"), {}).get("type") == "manifestation"
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
                and self.card_rules.get(item.get("cardId"), {}).get("type")
                == "manifestation"
            ]
        elif definition.get("scope") == "global":
            targets = [{"kind": "global"}]

        # A source with a continuous copying-style ability can only maintain one
        # target for that ability. Re-resolving it replaces the previous link.
        if duration == "while_source_and_target_on_field":
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
            self.rules_engine["ongoingEffects"].append(effect)
            created.append(effect)
        return created

    def prune_rules_ongoing_effects(self):
        battlefield_ids = {item.get("id") for item in self.battlefield}
        current_turn = self.phase_tracker["turn"]
        kept = []
        removed = []
        for effect in self.rules_engine["ongoingEffects"]:
            target = effect.get("target", {})
            target_present = (
                target.get("itemId") in battlefield_ids
                if target.get("itemId")
                else any(
                    action.get("id") == target.get("actionId")
                    for action in self.rules_engine.get("actionStack") or []
                )
            )
            source_required = effect.get("duration") == "while_source_and_target_on_field"
            source_item = self.find_battlefield_item(
                effect.get("source", {}).get("itemId")
            )
            source_present = (
                source_item is not None
                and self.rules_item_effects_active(source_item)
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
        return removed

    # -- assisted confrontation resolution ----------------------------
    def rules_field_zone(self, item):
        explicit = item.get("fieldZone")
        if explicit in {"field", "confrontation", "interzone", "stalemate"}:
            return explicit
        if item.get("id") in self.rules_engine.get("firstManifestationItemIds", {}).values():
            return "confrontation"
        return "field"

    def rules_item_controller_id(self, item):
        linked = next((
            effect for effect in reversed(
                self.rules_engine.get("ongoingEffects") or []
            )
            if effect.get("kind") == "control_link"
            and effect.get("target", {}).get("itemId") == (item or {}).get("id")
        ), None)
        return (
            linked.get("controllerId")
            if linked
            else (item or {}).get("controllerId") or (item or {}).get("ownerId")
        )

    def rules_item_card_rules(self, item, visiting=None):
        if not isinstance(item, dict):
            return {}
        metadata = dict(self.card_rules.get(item.get("cardId"), {}))
        visiting = set(visiting or ())
        item_id = item.get("id")
        if not item_id or item_id in visiting:
            return metadata
        visiting.add(item_id)
        copy_effect = next((
            effect for effect in reversed(
                self.rules_engine.get("ongoingEffects") or []
            )
            if effect.get("kind") == "copy_power_effects"
            and effect.get("source", {}).get("itemId") == item_id
        ), None)
        copied_item = self.find_battlefield_item(
            (copy_effect or {}).get("target", {}).get("itemId")
        )
        if copied_item is None:
            return metadata
        copied_metadata = self.rules_item_card_rules(copied_item, visiting)
        for key in RULES_COPIED_EFFECT_KEYS:
            if key in copied_metadata:
                metadata[key] = copied_metadata[key]
        return metadata

    def rules_item_effects_active(self, item):
        if not item or item not in self.battlefield or not item.get("faceUp"):
            return False
        if item.get("effectsDisabled"):
            return False
        return not any(
            effect.get("kind") in {"lose_effects", "obscure_lock", "interzone_lock"}
            and effect.get("target", {}).get("itemId") == item.get("id")
            for effect in self.rules_engine.get("ongoingEffects") or []
        )

    def rules_interzone_item_replaceable(self, item):
        return not any(
            effect.get("kind") == "interzone_lock"
            and effect.get("target", {}).get("itemId") == (item or {}).get("id")
            for effect in self.rules_engine.get("ongoingEffects") or []
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

    def mark_rules_interzone_entry(self, item):
        item["interzoneTurn"] = int(self.phase_tracker.get("turn") or 1)

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

    def rules_card_can_enter_support(self, item, from_zone="interzone"):
        metadata = self.rules_item_card_rules(item)
        if metadata.get("cannotEnterConfrontation"):
            return False
        if not self.rules_item_effects_active(item):
            return False
        if from_zone == "hand":
            return self.rules_support_from_hand_available(item.get("ownerId"), item.get("cardId"))
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
        if any(effect.get("kind") == "remove_float" for effect in effects):
            return False
        if any(effect.get("kind") == "grant_float" for effect in effects):
            return True
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
        if self.rules_item_card_rules(item).get("persist"):
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
        condition = metadata.get("supportFromHandCondition") or {}
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
        metadata = self.card_rules.get(card_id, {})
        if metadata.get("type") != "manifestation":
            return None
        if metadata.get("cannotEnterConfrontation"):
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
        if self.current_phase_id() != "confrontation_reaction":
            return "A Support Manifestation can only be played from Hand during Reaction."
        if self.rules_engine.get("priorityPlayerId") != player_id:
            return "You do not have priority."
        if not self.rules_support_from_hand_available(player_id, card_id):
            return "This Manifestation does not have Support from Hand."
        return None

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
        power = int(power or 0)
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
            copied = self.rules_manifestation_characteristics(
                self.find_battlefield_item(copy_effect.get("target", {}).get("itemId")), visiting
            )
            power = copied["power"]
            if copy_effect.get("kind") == "copy_power_temperament":
                temperament = copied["temperament"]

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
        if item.get("isTokenCard"):
            return int(item.get("power") or 0)
        return int(
            self.card_rules.get(item.get("cardId"), {}).get("power") or 0
        )

    def rules_confrontation_power(self, item):
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
            if self.card_rules.get(item.get("cardId"), {}).get("type") != "manifestation" and not item.get("isTokenCard"):
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

    def resolve_rules_state_actions(self, previous_powers=None):
        """Destroy face-up Manifestations whose current Power is zero or less."""
        previous_powers = dict(previous_powers or {})
        destroyed = []
        replacements = []
        triggered_actions = []
        threshold_exiled = []
        for item in list(self.rules_confrontation_items()):
            threshold = self.rules_item_card_rules(item).get(
                "suspensionThresholds", {}
            ).get("exile")
            if (
                isinstance(threshold, (int, float))
                and self.rules_manifestation_characteristics(item)["power"] >= threshold
            ):
                suspended = self.release_rules_suspended_by(
                    item.get("id"), exile=True
                )
                movement = self._rules_remove_field_item(
                    item, item.get("ownerId"), "exile", "top",
                    release_suspended=False,
                )
                movement["exiledSuspended"] = suspended
                threshold_exiled.append(movement)
        while True:
            candidates = [
                item for item in list(self.battlefield)
                if item.get("faceUp")
                and (
                    self.card_rules.get(item.get("cardId"), {}).get("type") == "manifestation"
                    or item.get("isTokenCard")
                )
                and (
                    item.get("id") not in previous_powers
                    or previous_powers[item.get("id")] > 0
                    or item.get("zeroPowerSustained")
                )
                and self.rules_manifestation_characteristics(item)["power"] <= 0
            ]
            if not candidates:
                break
            removed_items = []
            sustained_any = False
            life_sources = self.rules_active_passive_sources(
                "sustain_exact_zero"
            )
            greed_sources = self.rules_active_passive_sources(
                "capture_opponent_exact_zero"
            )
            for item in candidates:
                power = self.rules_manifestation_characteristics(item)["power"]
                item_controller = item.get("controllerId") or item.get("ownerId")
                greed_source = next((
                    source for source in greed_sources
                    if (source.get("controllerId") or source.get("ownerId"))
                    != item_controller
                ), None)
                if power == 0 and greed_source:
                    destination_player_id = (
                        greed_source.get("controllerId")
                        or greed_source.get("ownerId")
                    )
                    movement = self._rules_remove_field_item(
                        item, destination_player_id, "receptacle", "top"
                    )
                    movement["replacement"] = "capture_opponent_exact_zero"
                    replacements.append(movement)
                    removed_items.append(item)
                    continue
                if power == 0 and life_sources:
                    if not item.get("effectsDisabled"):
                        item["effectsDisabled"] = True
                        item["zeroPowerSustained"] = True
                        replacements.append({
                            "status": "sustained",
                            "replacement": "sustain_exact_zero",
                            "itemId": item.get("id"),
                            "cardId": item.get("cardId"),
                        })
                        self.prune_rules_ongoing_effects()
                    sustained_any = True
                    continue
                movement = self._rules_remove_field_item_by_effect(
                    item, item.get("ownerId"), "graveyard", "top",
                    reason="destroy",
                )
                destroyed.append(movement)
                removed_items.append(item)
                if movement.get("status") == "moved":
                    triggered_actions.extend(self.queue_rules_zone_entry_triggers(
                        item.get("cardId"), item.get("ownerId"),
                        item.get("ownerId"), "graveyard", defer=True,
                    ))
            if not removed_items:
                if sustained_any:
                    break
                break
            powers_before_removal = {
                item.get("id"): self.rules_manifestation_characteristics(item)["power"]
                for item in self.battlefield
            }
            self.prune_rules_ongoing_effects()
            previous_powers = powers_before_removal
        return {
            "destroyed": destroyed,
            "replacements": replacements,
            "triggeredActions": triggered_actions,
            "thresholdExiled": threshold_exiled,
        }

    @staticmethod
    def rules_temperament_winner(first, second):
        if first == second or (not first and not second):
            return None
        if first == "transcendent" or second == "hollow":
            return 0
        if second == "transcendent" or first == "hollow":
            return 1
        if second in TEMPERAMENT_DOMINANCE.get(first, set()):
            return 0
        if first in TEMPERAMENT_DOMINANCE.get(second, set()):
            return 1
        return None

    @staticmethod
    def rules_priority_roll(player_ids):
        while True:
            rolls = {player_id: random.randint(1, 6) for player_id in player_ids}
            high = max(rolls.values())
            winners = [player_id for player_id, value in rolls.items() if value == high]
            if len(winners) == 1:
                return winners[0], rolls

    def _rules_remove_field_item(self, item, container_id, zone, position="top",
                                 release_suspended=True):
        if item not in self.battlefield:
            return {"status": "missing", "itemId": item.get("id")}
        rolls_for_vessel = bool(
            zone == "receptacle"
            and self.rules_item_card_rules(item).get("vesselEntryRoll")
            and self.rules_item_effects_active(item)
        )
        self.battlefield.remove(item)
        for other in self.battlefield:
            if other.get("stackedOn") == item.get("id"):
                other["stackedOn"] = None
        if item.get("isCopy") or item.get("isTokenCard"):
            return {
                "status": "removed_copy", "itemId": item.get("id"),
                "cardId": item.get("cardId"), "ownerId": item.get("ownerId"),
            }
        vessel_roll = None
        if rolls_for_vessel:
            vessel_roll = random.randint(1, 6)
            self.rules_engine["lastVesselRoll"] = {
                "cardId": item.get("cardId"), "roll": vessel_roll,
                "turn": self.phase_tracker["turn"],
            }
            if vessel_roll % 2 == 1:
                container_id, zone, position = item["ownerId"], "hand", "top"
        self.put_zone_card(container_id, zone, item["cardId"], item["ownerId"], position)
        if zone == "receptacle" and container_id != item.get("ownerId"):
            self.record_rules_observed_event(
                "manifestation_enters_opponent_vessel", item.get("ownerId")
            )
        if zone in {"deck", "exile"}:
            self.clear_rules_effect_memories(item["ownerId"], item["cardId"])
        released = (
            self.release_rules_suspended_by(item.get("id"))
            if release_suspended
            and any(
                entry.get("sourceEffectId") == item.get("id")
                for entry in self.rules_engine.get("suspendedCards") or []
            )
            else []
        )
        return {
            "status": "moved", "itemId": item.get("id"), "cardId": item.get("cardId"),
            "ownerId": item.get("ownerId"), "containerId": container_id,
            "zone": zone, "position": position, "releasedSuspended": released,
            **({"vesselRoll": vessel_roll} if vessel_roll is not None else {}),
        }

    def _rules_remove_field_item_by_effect(self, item, container_id, zone,
                                           position="top", reason=None):
        if item.get("isCopy") or item.get("isTokenCard"):
            return self._rules_remove_field_item(
                item, container_id, zone, position
            )
        suspension_source = (
            self.rules_active_suspension_source(zone)
            if zone in {"deck", "graveyard"} else None
        )
        if suspension_source:
            self.battlefield.remove(item)
            for other in self.battlefield:
                if other.get("stackedOn") == item.get("id"):
                    other["stackedOn"] = None
            suspended = {
                "id": new_id(),
                "cardId": item.get("cardId"),
                "ownerId": item.get("ownerId"),
                "fromContainerId": item.get("ownerId"),
                "fromZone": "battlefield",
                "sourceEffectId": suspension_source.get("id"),
            }
            self.rules_engine["suspendedCards"].append(suspended)
            self.prune_rules_ongoing_effects()
            released = (
                self.release_rules_suspended_by(suspension_source.get("id"))
                if item.get("id") == suspension_source.get("id") else []
            )
            return {
                "status": "suspended",
                "itemId": item.get("id"),
                "cardId": item.get("cardId"),
                "ownerId": item.get("ownerId"),
                "suspensionId": suspended["id"],
                "sourceItemId": suspension_source.get("id"),
                "releasedSuspended": released,
            }
        movement = self._rules_remove_field_item(
            item, container_id, zone, position
        )
        if (
            movement.get("status") == "moved"
            and zone == "graveyard"
            and reason in {"destroy", "discard"}
        ):
            self.record_rules_limbo_entry(
                item.get("ownerId"), item.get("cardId"), reason,
                from_zone="battlefield",
            )
            if reason == "destroy":
                self.record_rules_observed_event(
                    "manifestation_destroyed",
                    self.rules_item_controller_id(item),
                )
            else:
                self.record_rules_observed_event(
                    "cards_discarded", item.get("ownerId")
                )
        return movement

    def prepare_rules_confrontation_result(self):
        if not self.rules_engine["enabled"] or self.current_phase_id() != "resolution_compare":
            return None
        existing = self.rules_engine.get("confrontationResult")
        if existing and existing.get("turn") == self.phase_tracker["turn"]:
            return existing

        state_actions = self.resolve_rules_state_actions()
        destroyed = state_actions["destroyed"]
        if state_actions["triggeredActions"]:
            self.queue_rules_simultaneous_actions(
                state_actions["triggeredActions"]
            )
        self.prune_rules_ongoing_effects()

        player_ids = list(self.players)
        totals = {}
        last_temperaments = {}
        participant_ids = []
        for player_id in player_ids:
            items = self.rules_confrontation_items(player_id)
            participant_ids.extend(item["id"] for item in items)
            totals[player_id] = sum(self.rules_confrontation_power(item) for item in items)
            last_item = max(
                items,
                key=lambda item: (
                    int(item.get("confrontationOrder") or 0),
                    self.battlefield.index(item),
                ),
                default=None,
            )
            last_temperaments[player_id] = (
                self.rules_manifestation_characteristics(last_item)["temperament"]
                if last_item else None
            )

        winner_id = None
        loser_id = None
        reason = "stalemate"
        priority_rolls = None
        forced_winner_id = self.rules_engine.get(
            "forcedConfrontationWinnerId"
        )
        loudmouth_forces_stalemate = any(
            passive.get("kind") == "stalemate_if_last_confrontation_entry"
            and int(source.get("confrontationOrder") or 0)
            == max((
                int(item.get("confrontationOrder") or 0)
                for item in self.rules_confrontation_items()
            ), default=0)
            for source in self.rules_active_passive_sources(
                "stalemate_if_last_confrontation_entry"
            )
            for passive in self.card_rules.get(
                source.get("cardId"), {}
            ).get("passiveEffects") or []
        )
        if forced_winner_id in self.players and not loudmouth_forces_stalemate:
            winner_id = forced_winner_id
            loser_id = self.other_rules_player_id(winner_id)
            reason = "forced"
        elif len(player_ids) == 2 and not loudmouth_forces_stalemate:
            first_id, second_id = player_ids
            if totals[first_id] != totals[second_id]:
                winner_id = first_id if totals[first_id] > totals[second_id] else second_id
                reason = "power"
            else:
                temperament_winner = self.rules_temperament_winner(
                    last_temperaments[first_id], last_temperaments[second_id]
                )
                if temperament_winner is not None:
                    winner_id = player_ids[temperament_winner]
                    reason = "temperament"
            if winner_id:
                loser_id = second_id if winner_id == first_id else first_id

        if winner_id:
            priority_id = winner_id
            self.rules_engine["lastConfrontationWinnerId"] = winner_id
        elif player_ids:
            priority_id, priority_rolls = self.rules_priority_roll(player_ids)
        else:
            priority_id = None
        self.rules_engine["priorityPlayerId"] = priority_id
        result = {
            "turn": self.phase_tracker["turn"], "status": "effects",
            "winnerId": winner_id, "loserId": loser_id,
            "stalemate": winner_id is None, "reason": reason,
            "totals": totals, "lastTemperaments": last_temperaments,
            "participantItemIds": participant_ids, "destroyed": destroyed,
            "stateReplacements": state_actions["replacements"],
            "priorityPlayerId": priority_id, "priorityRolls": priority_rolls,
            "captured": [], "returned": [],
        }
        self.rules_engine["confrontationResult"] = result
        if loser_id:
            self.rules_engine.setdefault("confrontationLosses", {})[
                str(self.phase_tracker["turn"])
            ] = loser_id
        return result

    def rules_revelation_order(self):
        """Return First Manifestations in the official simultaneous-trigger order."""
        player_ids = list(self.players)
        if len(player_ids) != 2:
            return list(self.rules_engine["firstManifestationItemIds"].values()), None, None
        items_by_player = {
            player_id: self.find_battlefield_item(
                self.rules_engine["firstManifestationItemIds"].get(player_id)
            )
            for player_id in player_ids
        }
        totals = {
            player_id: sum(self.rules_confrontation_power(item) for item in self.rules_confrontation_items(player_id))
            for player_id in player_ids
        }
        first_id, second_id = player_ids
        advantaged_id = None
        if totals[first_id] != totals[second_id]:
            advantaged_id = first_id if totals[first_id] > totals[second_id] else second_id
        else:
            first_temperament = self.rules_manifestation_characteristics(items_by_player[first_id])["temperament"]
            second_temperament = self.rules_manifestation_characteristics(items_by_player[second_id])["temperament"]
            temperament_winner = self.rules_temperament_winner(first_temperament, second_temperament)
            if temperament_winner is not None:
                advantaged_id = player_ids[temperament_winner]
        if advantaged_id:
            priority_id = second_id if advantaged_id == first_id else first_id
            order = [priority_id, advantaged_id]
            rolls = None
        else:
            priority_id, rolls = self.rules_priority_roll(player_ids)
            order = [priority_id, self.other_rules_player_id(priority_id)]
        return [
            items_by_player[player_id]["id"]
            for player_id in order if items_by_player.get(player_id)
        ], priority_id, rolls

    def rules_lowest_confrontation_power_player(self):
        """Return the player who would lose if the confrontation resolved now."""
        player_ids = list(self.players)
        if len(player_ids) != NUM_SEATS:
            return None
        items_by_player = {
            player_id: self.rules_confrontation_items(player_id)
            for player_id in player_ids
        }
        totals = {
            player_id: sum(self.rules_confrontation_power(item) for item in items)
            for player_id, items in items_by_player.items()
        }
        first_id, second_id = player_ids
        if totals[first_id] != totals[second_id]:
            return first_id if totals[first_id] < totals[second_id] else second_id
        last_items = {
            player_id: max(
                items,
                key=lambda item: (
                    int(item.get("confrontationOrder") or 0),
                    self.battlefield.index(item),
                ),
                default=None,
            )
            for player_id, items in items_by_player.items()
        }
        first_temperament = self.rules_manifestation_characteristics(
            last_items[first_id]
        )["temperament"]
        second_temperament = self.rules_manifestation_characteristics(
            last_items[second_id]
        )["temperament"]
        temperament_winner = self.rules_temperament_winner(
            first_temperament, second_temperament
        )
        if temperament_winner is None:
            return None
        return second_id if temperament_winner == 0 else first_id

    def _queue_next_rules_confrontation_destination(self):
        result = self.rules_engine.get("confrontationResult") or {}
        pending = result.get("pendingOwnItemIds") or []
        while pending and self.find_battlefield_item(pending[0]) is None:
            pending.pop(0)
        if not pending:
            result["status"] = "complete"
            result.pop("pendingOwnItemIds", None)
            self.rules_engine["pendingChoice"] = None
            self.prune_rules_ongoing_effects()
            return None
        item = self.find_battlefield_item(pending[0])
        choice = {
            "id": new_id(), "kind": "confrontation_destination",
            "playerId": result.get("winnerId"), "itemId": item["id"],
            "cardId": item.get("cardId"), "options": ["interzone", "deck_bottom"],
        }
        self.rules_engine["pendingChoice"] = choice
        result["status"] = "cleanup_choice"
        return choice

    def _mark_rules_persisted_first(self, item, player_id):
        for other in self.battlefield:
            if (other.get("controllerId") or other.get("ownerId")) == player_id:
                other.pop("persistedFirst", None)
        item["fieldZone"] = "confrontation"
        item["isSupport"] = False
        item["persistedFirst"] = True
        item["stackedOn"] = None
        self.rules_engine["firstManifestationItemIds"][player_id] = item["id"]
        return {
            "status": "persisted",
            "itemId": item["id"],
            "cardId": item.get("cardId"),
            "playerId": player_id,
        }

    def begin_rules_confrontation_cleanup(self):
        result = self.rules_engine.get("confrontationResult")
        if not result or result.get("turn") != self.phase_tracker["turn"]:
            result = self.prepare_rules_confrontation_result()
        if not result or result.get("status") not in {"effects", "cleanup"}:
            return result
        participant_ids = set(result.get("participantItemIds") or [])
        if result.get("stalemate"):
            moved = []
            for item in list(self.battlefield):
                if item.get("id") not in participant_ids:
                    continue
                if item.get("isCopy") or item.get("isTokenCard"):
                    moved.append(self._rules_remove_field_item(item, item.get("ownerId"), "exile", "top"))
                else:
                    item["fieldZone"] = "stalemate"
                    moved.append({"status": "stalemate", "itemId": item["id"], "cardId": item.get("cardId")})
            result["returned"] = moved
            result["status"] = "complete"
            self.prune_rules_ongoing_effects()
            return result

        winner_id = result.get("winnerId")
        loser_id = result.get("loserId")
        rematch = self.rules_engine.get("rematchPending") or {}
        rematch_item_ids = set(
            rematch.get("protectedItemIds") or []
            if int(rematch.get("turn") or 0) == self.phase_tracker["turn"]
            else []
        )
        captured = []
        for item in list(self.rules_confrontation_items_owned_by(
            loser_id, ("confrontation", "stalemate")
        )):
            if item.get("id") in rematch_item_ids or self.rules_item_zone_locked(item):
                continue
            if (
                self.rules_item_card_rules(item).get("lossDestination") == "winner_interzone"
                and winner_id in self.players
                and not item.get("isCopy") and not item.get("isTokenCard")
            ):
                if self.rules_interzone_slot_count(winner_id) >= self.rules_interzone_capacity(winner_id):
                    anchor = self.rules_interzone_share_anchor(winner_id, item)
                    item.update({
                        "stackedOn": anchor, "stackOffsetX": 18.0, "stackOffsetY": 18.0,
                    } if anchor else {"stackedOn": None})
                else:
                    item["stackedOn"] = None
                item["controllerId"] = winner_id
                item["fieldZone"] = "interzone"
                item["isSupport"] = False
                self.mark_rules_interzone_entry(item)
                captured.append({
                    "status": "moved_to_winner_interzone", "itemId": item.get("id"),
                    "cardId": item.get("cardId"), "ownerId": item.get("ownerId"),
                    "containerId": winner_id, "zone": "interzone",
                })
                continue
            if (
                self.rules_item_card_rules(item).get("lossDestination") == "own_interzone"
                and not item.get("isCopy") and not item.get("isTokenCard")
            ):
                owner_id = self.rules_item_controller_id(item)
                if self.rules_interzone_slot_count(owner_id) >= self.rules_interzone_capacity(owner_id):
                    anchor = self.rules_interzone_share_anchor(owner_id, item)
                    item.update({
                        "stackedOn": anchor, "stackOffsetX": 18.0, "stackOffsetY": 18.0,
                    } if anchor else {"stackedOn": None})
                else:
                    item["stackedOn"] = None
                item["fieldZone"] = "interzone"
                item["isSupport"] = False
                self.mark_rules_interzone_entry(item)
                captured.append({
                    "status": "moved_to_own_interzone", "itemId": item.get("id"),
                    "cardId": item.get("cardId"), "ownerId": item.get("ownerId"),
                    "containerId": owner_id, "zone": "interzone",
                })
                continue
            captured.append(self._rules_remove_field_item(item, winner_id, "receptacle", "top"))
        own_items = [
            item for item in self.rules_confrontation_items_owned_by(
                winner_id, ("confrontation", "stalemate")
            )
            if item.get("id") not in rematch_item_ids
            and not self.rules_item_zone_locked(item)
        ]
        support_exiled = []
        support_resolved = []
        for item in list(own_items):
            win_exile_memory = next((
                memory for memory in self.rules_effect_memories_for(
                    item.get("ownerId"), item.get("cardId"),
                    "win_destination_exile",
                )
                if (memory.get("data") or {}).get("itemId") == item.get("id")
            ), None)
            if win_exile_memory:
                support_exiled.append(self._rules_remove_field_item(
                    item, item.get("ownerId"), "exile", "top"
                ))
                own_items.remove(item)
                continue
            if not item.get("isSupport"):
                continue
            support_effect = item.get("supportWinEffect") or {}
            if support_effect.get("kind") == "opponent_vessel_score" and loser_id in self.players:
                movement = self._rules_remove_field_item(item, loser_id, "receptacle", "top")
                delta = max(0, min(int(support_effect.get("value") or 0), 999))
                delta = self.adjust_rules_score(loser_id, delta)
                support_resolved.append({
                    "kind": "opponent_vessel_score", "cardId": item.get("cardId"),
                    "itemId": item.get("id"), "playerId": loser_id,
                    "delta": delta, "score": self.players[loser_id]["score"],
                    "movement": movement,
                })
                own_items.remove(item)
            elif item.get("supportWinDestination") == "exile":
                support_exiled.append(self._rules_remove_field_item(
                    item, item.get("ownerId"), "exile", "top"
                ))
                own_items.remove(item)
            elif item.get("supportWinDestination") == "opponent_receptacle" and loser_id in self.players:
                movement = self._rules_remove_field_item(item, loser_id, "receptacle", "top")
                support_resolved.append({
                    "kind": "opponent_vessel", "cardId": item.get("cardId"),
                    "itemId": item.get("id"), "playerId": loser_id,
                    "movement": movement,
                })
                own_items.remove(item)
        result["captured"] = captured
        result["supportExiled"] = support_exiled
        result["supportResolved"] = support_resolved
        result["rematchItemIds"] = list(rematch_item_ids)
        persist_candidates = [
            item for item in own_items if self.rules_item_has_persist(item)
        ]
        result["persisted"] = []
        if len(persist_candidates) == 1:
            persisted = persist_candidates[0]
            result["persisted"].append(
                self._mark_rules_persisted_first(persisted, winner_id)
            )
            own_items.remove(persisted)
        elif len(persist_candidates) > 1:
            result["pendingOwnItemIds"] = [
                item["id"] for item in own_items if item not in persist_candidates
            ]
            choice = {
                "id": new_id(),
                "kind": "persist_first_manifestation",
                "playerId": winner_id,
                "candidateItemIds": [item["id"] for item in persist_candidates],
            }
            self.rules_engine["pendingChoice"] = choice
            result["status"] = "cleanup_choice"
            self.prune_rules_ongoing_effects()
            return result
        result["pendingOwnItemIds"] = [item["id"] for item in own_items]
        result["status"] = "cleanup"
        self.prune_rules_ongoing_effects()
        self._queue_next_rules_confrontation_destination()
        return result

    def reset_rules_confrontation_turn(self):
        persisted_firsts = [
            item for item in self.battlefield
            if item.get("persistedFirst")
            and self.rules_field_zone(item) == "confrontation"
        ]
        first_ids = {}
        for item in persisted_firsts:
            controller_id = item.get("controllerId") or item.get("ownerId")
            if controller_id in self.players:
                first_ids[controller_id] = item["id"]
        self.rules_engine["firstManifestationItemIds"] = first_ids
        self.rules_engine["firstManifestationValidatedPlayerIds"] = list(first_ids)
        self.rules_engine["firstManifestationComplete"] = bool(
            len(first_ids) >= NUM_SEATS
        )
        self.rules_engine["firstManifestationTriggersQueued"] = False
        self.rules_engine["confrontationEntrySequence"] = max(
            (
                int(item.get("confrontationOrder") or 0)
                for item in self.rules_confrontation_items()
            ),
            default=0,
        )
        self.rules_engine["confrontationResult"] = None
        self.rules_engine["forcedConfrontationWinnerId"] = None

    def ready_rules_exhausted_cards(self):
        """Return exhausted battlefield cards to their upright orientation."""
        readied_item_ids = []
        for item in self.battlefield:
            rotation = float(item.get("rotation") or 0)
            if int(round(rotation)) % 180 == 0:
                continue
            item["rotation"] = 0.0
            readied_item_ids.append(item["id"])
        return readied_item_ids

    def rules_action_timing_error(self, kind, source, as_support=False):
        """Reject voluntary card actions outside the rulebook response windows.

        Older saved games and focused engine tests can lack the pre-game ready
        markers.  Once a real assisted match has started, however, the server
        must not trust the client-side playable aura as its only guard.
        """
        started = bool(
            self.phase_tracker["turn"] > 1
            or len(self.rules_engine.get("readyPlayerIds") or []) >= NUM_SEATS
            or self.rules_engine.get("firstManifestationComplete")
            or self.rules_engine.get("firstManifestationItemIds")
        )
        if as_support:
            return None if self.current_phase_id() == "confrontation_reaction" else "A Support Manifestation can only be played during Reaction."
        if not started or kind not in {"play_card", "activated_effect"}:
            return None
        phase_id = self.current_phase_id()
        response_phases = {"confrontation_reaction", "resolution_effects", "end_actions"}
        if kind == "activated_effect":
            return None if phase_id in response_phases else "This effect cannot be activated during the current step."
        card_type = (source or {}).get("cardType")
        if (card_type == "ephemeral_will" and self.card_rules.get((source or {}).get("cardId"), {}).get("reactionEmptyStackOnly")):
            if phase_id != "confrontation_reaction" or self.rules_engine["actionStack"]:
                return "This card can only be played during Reaction while the Stack is empty."
            return None
        play_phases = self.card_rules.get((source or {}).get("cardId"), {}).get("playPhases")
        if card_type == "ephemeral_will" and play_phases:
            return None if phase_id in play_phases else "This Will cannot be played during the current step."
        if card_type == "ephemeral_will":
            return None if phase_id in response_phases else "An Ephemeral Will cannot be played during the current step."
        if card_type == "persistent_will":
            if phase_id == "end_actions":
                return None
            if (
                phase_id == "confrontation_before_revelation"
                and self.card_rules.get((source or {}).get("cardId"), {}).get(
                    "playBeforeRevelation"
                )
            ):
                return None
            return "A Persistent Will can only be played during End actions."
        return "This card cannot be played as a Stack action during the current step."

    def declare_rules_action(self, player_id, label, kind="manual", source=None, target=None,
                             targets=None, cost_note=None, payment_card_ids=None, ability_id=None,
                             placement=None, as_support=False,
                             extra_essence_count=0, cost_card_id=None):
        if not self.rules_engine["enabled"]:
            return "Assisted rules are not active.", None
        if self.ended or player_id not in self.players:
            return "Unable to declare an action.", None
        if len(self.players) < 2:
            return "Both players must join before using priority.", None
        if self.rules_engine.get("pendingChoice"):
            return "A required card choice must be completed first.", None
        if self.rules_engine["priorityPlayerId"] != player_id:
            return "You do not have priority.", None
        kind = str(kind or "manual")
        if kind not in RULES_ACTION_KINDS:
            return "Unknown action type.", None
        if as_support and self.rules_support_entry_locked(player_id):
            return "Manifestations cannot be put in Support until the end of the turn.", None
        clean_label = " ".join(str(label or "").split())[:160]
        if not clean_label:
            return "Describe the action before adding it to the Stack.", None
        clean_target = " ".join(str(target or "").split())[:240]
        clean_cost_note = " ".join(str(cost_note or "").split())[:240]
        as_support = bool(as_support)
        if as_support and kind != "play_card":
            return "Support must be declared as a played card.", None
        source_error, clean_source = self.rules_action_source(
            player_id, kind, source, as_support=as_support,
            ability_id=str(ability_id or ""),
        )
        if source_error:
            return source_error, None
        timing_error = self.rules_action_timing_error(kind, clean_source, as_support=as_support)
        if timing_error:
            return timing_error, None
        target_error, clean_targets = self.rules_action_targets(targets)
        if target_error:
            return target_error, None
        if as_support:
            for event in (
                "enters_field", "enters_support", "enters_field_zone",
            ):
                if event == "enters_field" and clean_source.get("zone") == "battlefield":
                    continue
                trigger_error = self.rules_trigger_target_error(
                    clean_source["cardId"], event, face_up=True,
                    trigger_targets=clean_targets, controller_id=player_id,
                    event_item_id=clean_source.get("itemId"),
                    event_zone=(
                        "confrontation"
                        if event == "enters_field_zone" else None
                    ),
                )
                if trigger_error:
                    return trigger_error, None
        ability_error, clean_ability = self.rules_action_ability(
            player_id, kind, clean_source, str(ability_id or ""), clean_targets
        )
        if ability_error:
            return ability_error, None
        payment_error, clean_payment = self.rules_action_payment(
            player_id,
            kind,
            clean_source,
            payment_card_ids,
            clean_ability,
            clean_targets,
            extra_essence_count,
        )
        if payment_error:
            return payment_error, None
        cost_card_id = str(cost_card_id) if cost_card_id else None
        if clean_ability and clean_ability.get("additionalCost") == "exile_hand_manifestation":
            hand_cards = list(self.players[player_id]["zones"]["hand"])
            if clean_source.get("zone") == "hand" and clean_source.get("cardId") in hand_cards:
                hand_cards.remove(clean_source["cardId"])
            if not any(
                self.card_rules.get(card_id, {}).get("type") == "manifestation"
                for card_id in hand_cards
            ):
                return "You need a Manifestation in hand to reveal and exile as an additional cost.", None
            if (
                cost_card_id not in hand_cards
                or self.card_rules.get(cost_card_id, {}).get("type") != "manifestation"
            ):
                return "Choose the Manifestation from your hand to reveal and exile.", None
        else:
            cost_card_id = None
        action = {
            "id": new_id(),
            "controllerId": player_id,
            "label": clean_label,
            "kind": kind,
            "source": clean_source,
            "target": clean_target or None,
            "targets": clean_targets,
            "ability": clean_ability,
            "cost": {
                "note": clean_cost_note or None,
                "tributeCardIds": clean_payment["cardIds"],
                "tributeRequirements": clean_payment["requirements"],
                "essenceSpent": clean_payment["essenceSpent"],
                "excessEssence": clean_payment["excessEssence"],
                "tributeValidated": clean_payment["validated"],
                "tributePaid": bool(clean_payment["requirements"]),
                "sourceExhausted": bool(clean_ability and clean_ability.get("exhaustSource")),
                "sourceSacrificed": bool(clean_ability and clean_ability.get("sacrificeSource")),
                "sacrificedCards": [],
                "removedCounters": [],
                "optionalExtraEssenceSpent": clean_payment[
                    "optionalExtraEssenceSpent"
                ],
            },
            "phaseId": self.current_phase_id(),
            "turn": self.phase_tracker["turn"],
            "createdAt": time.time(),
        }
        if as_support:
            action["asSupport"] = True
        if clean_ability and clean_ability.get("immediate"):
            action["immediate"] = True
        clean_placement = self.clean_rules_action_placement(
            kind, clean_source, placement, as_support=as_support
        )
        if clean_placement is not None:
            action["placement"] = clean_placement
        if kind == "play_card" and clean_source.get("zone") in {"hand", "graveyard", "suspended"}:
            container_id = clean_source.get("containerId") or player_id
            if clean_source.get("zone") == "suspended":
                suspended = next((
                    entry for entry in self.rules_engine.get("suspendedCards") or []
                    if entry.get("id") == clean_source.get("suspensionId")
                ), None)
                owner_id = suspended.get("ownerId") if suspended else None
                if suspended:
                    self.rules_engine["suspendedCards"].remove(suspended)
            else:
                owner_id = self.take_zone_card(
                    container_id, clean_source["zone"],
                    clean_source["cardId"]
                )
            if owner_id is None:
                return "The source card is no longer in its declared zone.", None
            action["sourceOnStack"] = True
            if clean_source.get("permissionId"):
                self.consume_rules_zone_play_permission(clean_source["permissionId"])
        elif as_support and clean_source.get("zone") == "battlefield":
            source_item = self.find_battlefield_item(clean_source.get("itemId"))
            if source_item is None:
                return "This Manifestation is no longer in your Interzone.", None
            action["sourceBattlefieldItem"] = {
                **source_item, "counters": dict(source_item.get("counters") or {})
            }
            self.battlefield.remove(source_item)
            for other in self.battlefield:
                if other.get("stackedOn") == source_item.get("id"):
                    other["stackedOn"] = None
            action["sourceOnStack"] = True
        tribute_result = self.pay_rules_tribute(player_id, clean_payment)
        action["cost"]["tributeMovements"] = tribute_result["movements"]
        action["cost"]["createdEssence"] = tribute_result["createdEssence"]
        activation_payment = self.pay_rules_activation_cost(clean_source, clean_ability)
        action["cost"]["sacrificedCards"] = activation_payment["sacrificedCards"]
        action["cost"]["removedCounters"] = activation_payment["removedCounters"]
        action["cost"]["reducedSourcePower"] = activation_payment[
            "reducedSourcePower"
        ]
        if cost_card_id:
            cost_owner = self.card_owner_in_zone(player_id, "hand", cost_card_id) or player_id
            cost_error, _owner, _replacement = self.move_zone_card_by_effect(
                player_id, "hand", cost_owner, "exile", cost_card_id, "top"
            )
            if not cost_error:
                action["cost"]["revealedCard"] = {
                    "cardId": cost_card_id, "ownerId": cost_owner,
                    "power": int(self.card_rules.get(cost_card_id, {}).get("power") or 0),
                }
        self.rules_engine["actionStack"].append(action)
        self.rules_engine["priorityPasses"] = []
        self.rules_engine["priorityPlayerId"] = self.other_rules_player_id(player_id)
        if (
            kind == "play_card"
            and self.card_rules.get(clean_source.get("cardId"), {}).get("type") in RULES_WILL_TYPES
        ):
            self.queue_rules_will_target_watchers(action)
        return None, action

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

    @staticmethod
    def clean_rules_trigger_result(result):
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
        if kind == "add_counter_source":
            counter = str(result.get("counter") or "")[:64]
            value = result.get("value")
            if not counter or not isinstance(value, (int, float)):
                return None
            return {
                "kind": kind,
                "counter": counter,
                "value": max(-999, min(int(value), 999)),
            }
        if kind == "each_player_recovery_choice":
            return {"kind": kind}
        if kind == "chain_from_zone":
            zone = str(result.get("zone") or "")
            if zone not in {"hand", "graveyard", "deck"}:
                return None
            clean = {"kind": kind, "zone": zone, "optional": bool(result.get("optional"))}
            if result.get("winDestination") in {"opponent_receptacle", "exile"}:
                clean["winDestination"] = result["winDestination"]
            if result.get("shuffleAfter"):
                clean["shuffleAfter"] = True
            if result.get("players") in {"each_opponent", "all"}:
                clean["players"] = result["players"]
            if isinstance(result.get("scoreCost"), (int, float)) and result["scoreCost"] < 0:
                clean["scoreCost"] = max(-999, int(result["scoreCost"]))
            if result.get("preMove") == "first_manifestation_to_deck_bottom":
                clean["preMove"] = result["preMove"]
            after_chain = result.get("afterChain")
            if isinstance(after_chain, dict) and after_chain.get("kind") in RULES_AFTER_CHAIN:
                clean["afterChain"] = {"kind": after_chain["kind"]}
            chain_abilities = []
            for chained in result.get("chainAbilities") or []:
                if not isinstance(chained, dict):
                    continue
                event = (chained.get("trigger") or {}).get("event")
                inner = chained.get("result")
                inner_clean = (
                    Session.clean_rules_trigger_result(inner)
                    or Session.clean_rules_action_result(inner)
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
        return clean

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
            target_rules = ability.get("targets") or {}
            targets = clean_targets
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
            )
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
                             event_card_id=None):
        """Put server-verifiable triggers for one completed event on the Stack."""
        if not self.rules_engine["enabled"] or self.ended or len(self.players) < NUM_SEATS:
            return []
        if owner_id not in self.players:
            return []
        controller_id = (
            controller_id if controller_id in self.players else owner_id
        )
        if event == "enters_zone" and container_id not in self.players:
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
            if trigger.get("firstWillOfTurn") and not first_will_of_turn:
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
                if trigger.get("eventController") == "owner" and event_controller_id != owner_id:
                    continue
                if (
                    trigger.get("enteredFromZone")
                    and trigger.get("enteredFromZone") != event_source_zone
                ):
                    continue
                if trigger.get("eventSourceOnly") and item_id != event_item_id:
                    continue
            if (
                event == "manifestation_enters_field"
                and trigger.get("eventController") == "owner"
                and event_controller_id != owner_id
            ):
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
            clean_result = self.clean_rules_trigger_result(raw_result) or self.clean_rules_action_result(raw_result)
            target_rules = ability.get("targets") or {}
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
            target_validation_error = self.rules_ability_targets_error(
                target_rules, clean_targets, controller_id,
                event_item_id=event_item_id,
            )
            needs_target_choice = bool(
                target_validation_error
                and not clean_targets
                and int(target_rules.get("min") or 0) > 0
            )
            if target_validation_error and not needs_target_choice:
                continue
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
                "revelation": "battlefield",
                "vessel_revelation": zone,
                "before_revelation": "battlefield",
                "enters_field_zone": "battlefield",
                "end_of_turn": "battlefield",
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
                        "points_lost", "cards_discarded",
                        "deck_cards_discarded", "cards_drawn", "points_gained",
                        "manifestation_entered_limbo", "manifestation_targeted_by_will",
                        "manifestation_destroyed",
                        "manifestation_enters_opponent_vessel",
                        "wins_confrontation",
                        "loses_confrontation",
                        "revelation",
                        "before_revelation",
                        "enters_field_zone", "end_of_turn",
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
                            "controller", "fieldZone", "supportOnly", "maxPoints",
                            "maxPower", "minPower", "excludeEventSource", "sourceOnly",
                            "fieldZonesByType", "enteredThisTurn", "enteredInterzoneThisTurn", "confrontationOutcome", "owner",
                            "firstManifestationOnly", "counter", "minCounters",
                            "limboReasons", "container",
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
            if needs_target_choice:
                if action["optional"]:
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
        copied_item = self.find_battlefield_item(
            (effect.get("target") or {}).get("itemId")
        )
        if source_item is None or copied_item is None:
            return []
        abilities = [
            ability
            for ability in self.rules_item_card_rules(
                copied_item
            ).get("triggeredAbilities") or []
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

    def _continue_rules_optional_stack_choices(
        self, actions, next_index=0, accepted_actions=None,
        priority_player_id=None,
    ):
        actions = [action for action in actions if isinstance(action, dict)]
        accepted_actions = list(accepted_actions or [])
        while next_index < len(actions):
            action = actions[next_index]
            next_index += 1
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
            accepted_actions.append(action)
        return self._queue_rules_simultaneous_actions_ready(
            accepted_actions, priority_player_id
        )

    def queue_rules_simultaneous_actions(self, actions, priority_player_id=None):
        """Confirm optional triggers, then queue one simultaneous event atomically."""
        return self._continue_rules_optional_stack_choices(
            actions, priority_player_id=priority_player_id
        )

    def queue_or_defer_rules_simultaneous_actions(self, actions,
                                                  priority_player_id=None):
        actions = [action for action in actions if isinstance(action, dict)]
        if not actions:
            return True
        pending = self.rules_engine.get("pendingChoice")
        if pending and pending.get("kind") != "simultaneous_stack_order":
            self.rules_engine["deferredSimultaneousActions"].extend(actions)
            return False
        return self.queue_rules_simultaneous_actions(actions, priority_player_id)

    def flush_rules_deferred_simultaneous_actions(self):
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
        return self.queue_rules_triggers(
            card_id, owner_id, "enters_field", item_id=item_id, face_up=face_up,
            target_player_id=target_player_id, event_targets=event_targets,
            defer=defer,
        )

    def queue_rules_tribute_triggers(self, card_ids, owner_id,
                                     simultaneous_action_id=None,
                                     tribute_movements=None):
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
            queued.extend(self.queue_rules_triggers(
                card_id, owner_id, "used_as_tribute", container_id=owner_id,
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
            self.queue_rules_simultaneous_actions(queued)
        return queued

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

    def queue_rules_manifestation_entry_watchers(self, item, defer=False):
        if (
            not item
            or not item.get("faceUp")
            or self.card_rules.get(item.get("cardId"), {}).get("type") != "manifestation"
        ):
            return []
        event_controller_id = item.get("controllerId") or item.get("ownerId")
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
            if self.rules_item_effects_active(source):
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

    def queue_rules_persistent_will_entry_watchers(self, item, defer=False):
        if (
            not item
            or not item.get("faceUp")
            or item.get("isTokenCopy")
            or self.card_rules.get(item.get("cardId"), {}).get("type")
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

    def queue_rules_beginning_turn_triggers(self):
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
        if queued:
            self.queue_rules_simultaneous_actions(queued)
        return queued

    def queue_rules_end_turn_memory_triggers(self, defer=False):
        turn = self.phase_tracker["turn"]
        queued = []
        for memory in list(self.rules_engine.get("effectMemories") or []):
            if memory.get("kind") != "return_from_limbo_end_turn":
                continue
            if int(memory.get("createdTurn") or 0) != turn:
                continue
            if int(memory.get("queuedTurn") or 0) == turn:
                continue
            memory["queuedTurn"] = turn
            queued.append({
                "id": new_id(),
                "controllerId": memory.get("controllerId") or memory.get("ownerId"),
                "label": (
                    f'{self.card_labels.get(memory.get("cardId"), memory.get("cardId"))}'
                    " — delayed effect"
                ),
                "kind": "triggered_effect",
                "optional": bool(
                    (memory.get("data") or {}).get("optional")
                ),
                "source": {
                    "cardId": memory.get("cardId"),
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
        for memory in list(self.rules_engine.get("effectMemories") or []):
            if memory.get("kind") != "move_to_deck_at_resolution":
                continue
            if int(memory.get("queuedTurn") or 0) == turn:
                continue
            memory["queuedTurn"] = turn
            queued.append({
                "id": new_id(),
                "controllerId": memory.get("controllerId") or memory.get("ownerId"),
                "label": (
                    f'{self.card_labels.get(memory.get("cardId"), memory.get("cardId"))}'
                    " — delayed Resolution effect"
                ),
                "kind": "triggered_effect",
                "source": {
                    "cardId": memory.get("cardId"),
                    "zone": "memory",
                    "ownerId": memory.get("ownerId"),
                    "cardType": self.card_rules.get(
                        memory.get("cardId"), {}
                    ).get("type"),
                },
                "target": None,
                "targets": [],
                "ability": {
                    "id": "memory-move-to-deck-at-resolution",
                    "trigger": {"event": "at_resolution"},
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

    def queue_rules_chain_outcome_triggers(self, item, event, player_id):
        abilities = [
            ability for ability in item.get("chainAbilities") or []
            if (ability.get("trigger") or {}).get("event") == event
        ]
        if not abilities:
            return []
        return self.queue_rules_triggers(
            item.get("cardId"), item.get("ownerId"), event,
            item_id=item.get("id"), face_up=True,
            event_controller_id=player_id, defer=True,
            controller_id=(item.get("chainSource") or {}).get("controllerId")
            or self.rules_item_controller_id(item),
            abilities_override=abilities,
        )

    def queue_rules_confrontation_win_triggers(self, defer=False):
        result = self.rules_engine.get("confrontationResult") or {}
        winner_id = result.get("winnerId")
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
            "fieldZone", "supportOnly", "maxPoints", "maxPower", "excludeEventSource",
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
                                  action_targets=None, container_id=None):
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

    def draw_rules_cards(self, player_id, count):
        drawn = []
        player = self.players[player_id]
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
            matching[-1].get("overflowDestination", "graveyard")
            if matching else "graveyard"
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
        overflow = self.set_rules_hand_overflow_choice([player_id])
        payload = {
            "kind": "draw",
            "playerId": player_id,
            "count": len(drawn),
        }
        if overflow:
            payload["overflowChoiceId"] = overflow["id"]
        return payload

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
            "y": 620.0 if seat != 1 else 880.0,
            "faceUp": True,
            "rotation": 0.0,
            "counters": {},
            "stackedOn": None,
            "createdByItemId": source_item_id,
        }
        if metadata.get("type") == "persistent_will":
            item["fieldZone"] = "field"
        else:
            item["fieldZone"] = "confrontation"
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
        self.battlefield.append(item)
        return item

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

    def apply_rules_action_result(self, action):
        result = (action.get("ability") or {}).get("result") or {}
        player_id = action.get("controllerId")
        player = self.players.get(player_id)
        if player is None:
            return None
        if result.get("kind") == "score_target":
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
        if result.get("kind") == "score_each_opponent":
            deltas = {}
            multiplier = (
                self.rules_score_count(result["perCount"], player_id, action)
                if result.get("perCount") else 1
            )
            for other_id in self.players:
                if other_id != player_id:
                    deltas[other_id] = self.adjust_rules_score(
                        other_id, int(result.get("value") or 0) * multiplier
                    )
            return {
                "kind": "score_each_opponent",
                "status": "resolved" if any(deltas.values()) else "prevented",
                "deltas": deltas,
            }
        if result.get("kind") == "score_source_container":
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
        if result.get("kind") == "interzone_score_and_draw":
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
        if result.get("kind") == "shuffle_owner_deck":
            random.shuffle(player["zones"]["deck"])
            return {
                "kind": result.get("kind"),
                "status": "shuffled",
                "playerId": player_id,
                "count": len(player["zones"]["deck"]),
            }
        if result.get("kind") == "create_essence":
            amount = int(result.get("value") or 0)
            if result.get("perCount") in RULES_SCORE_COUNTS:
                amount *= self.rules_score_count(
                    result["perCount"], player_id, action
                )
            if amount <= 0:
                return {"kind": result.get("kind"), "status": "nothing", "amount": 0}
            created = self.add_rules_excess_essence(player_id, [{
                "temperament": result.get("temperament"),
                "amount": amount,
                "retained": bool(result.get("retained")),
            }])
            return {
                "kind": result.get("kind"),
                "status": "created",
                "playerId": player_id,
                "temperament": result.get("temperament"),
                "amount": amount,
                "tokens": created,
            }
        if result.get("kind") == "move_zone_target_to_field_zone":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "zone_card"
            ), None)
            if target is None:
                return {
                    "kind": result.get("kind"),
                    "status": "target_missing",
                }
            container_id = target.get("containerId")
            zone = target.get("zone")
            card_id = target.get("cardId")
            owner_id = self.card_owner_in_zone(
                container_id, zone, card_id
            )
            if owner_id is None:
                return {
                    "kind": result.get("kind"),
                    "status": "target_missing",
                }
            seat = self.players[player_id].get("seat")
            item = {
                "id": new_id(), "ownerId": owner_id,
                "controllerId": player_id, "cardId": card_id,
                "x": 740.0, "y": 620.0 if seat != 1 else 880.0,
                "faceUp": True, "rotation": 0.0, "counters": {},
                "stackedOn": None,
            }
            field_zone = result.get("fieldZone")
            if field_zone == "interzone":
                if self.rules_interzone_slot_count(player_id) >= self.rules_interzone_capacity(player_id):
                    anchor = self.rules_interzone_share_anchor(
                        player_id, item
                    )
                    if not anchor:
                        return {
                            "kind": result.get("kind"),
                            "status": "interzone_full",
                        }
                    item.update({
                        "stackedOn": anchor,
                        "stackOffsetX": 18.0,
                        "stackOffsetY": 18.0,
                    })
                item["fieldZone"] = "interzone"
                self.mark_rules_interzone_entry(item)
            elif result.get("asSupport"):
                self.mark_rules_support_entry(item)
            else:
                item["fieldZone"] = field_zone
            self.take_zone_card(container_id, zone, card_id)
            self.battlefield.append(item)
            return {
                "kind": result.get("kind"),
                "status": "moved",
                "itemId": item["id"],
                "cardId": card_id,
                "ownerId": owner_id,
                "controllerId": player_id,
                "fieldZone": item.get("fieldZone"),
            }
        if result.get("kind") == "move_target_to_own_vessel":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "card"
            ), None)
            item = self.find_battlefield_item((target or {}).get("itemId"))
            if item is None or item.get("ownerId") == player_id:
                return {"kind": result.get("kind"), "status": "target_missing"}
            if (
                self.rules_item_card_rules(item).get("adamant")
                and self.rules_item_effects_active(item)
                and self.rules_item_controller_id(item) != player_id
            ):
                return {"kind": result.get("kind"), "status": "prevented_adamant",
                        "cardId": item.get("cardId"), "itemId": item.get("id")}
            movement = self._rules_remove_field_item(item, player_id, "receptacle")
            self.prune_rules_ongoing_effects()
            return {"kind": result.get("kind"), "status": movement.get("status"),
                    "cardId": item.get("cardId"), "itemId": item.get("id"),
                    "containerId": player_id, "zone": "receptacle"}
        if result.get("kind") == "add_power_counter_target":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "card"
            ), None)
            item = self.find_battlefield_item((target or {}).get("itemId"))
            if item is None:
                return {"kind": result.get("kind"), "status": "target_missing"}
            counters = item.setdefault("counters", {})
            counters["power"] = int(counters.get("power") or 0) + int(result.get("value") or 0)
            return {
                "kind": result.get("kind"), "status": "changed",
                "itemId": item["id"], "value": int(result.get("value") or 0),
            }
        if result.get("kind") == "weaken_target_per_hand_card":
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
        if result.get("kind") == "dissolve_vessel_targets":
            moved, gained = [], 0
            for target in action.get("targets") or []:
                if target.get("kind") != "zone_card" or target.get("zone") != "receptacle":
                    continue
                container_id = target.get("containerId")
                card_id = target.get("cardId")
                owner_id = self.card_owner_in_zone(container_id, "receptacle", card_id)
                if owner_id is None or container_id != player_id:
                    continue
                error, _owner, replacement = self.move_zone_card_by_effect(
                    container_id, "receptacle", owner_id, "deck", card_id, "top"
                )
                if error:
                    continue
                random.shuffle(self.players[owner_id]["zones"]["deck"])
                moved.append(card_id)
                if not replacement:
                    gained += int(result.get("value") or 0)
            if gained:
                self.adjust_rules_score(player_id, gained)
            return {
                "kind": result.get("kind"),
                "status": "moved" if moved else "nothing",
                "cardIds": moved, "points": gained,
            }
        if result.get("kind") == "destroy_support_targets_draw":
            draws = {}
            destroyed = []
            for target in action.get("targets") or []:
                item = self.find_battlefield_item(target.get("itemId"))
                if item is None or not item.get("isSupport"):
                    continue
                controller_id = self.rules_item_controller_id(item)
                movement = self._rules_remove_field_item_by_effect(
                    item, item.get("ownerId"), "graveyard", "top", reason="destroy"
                )
                if movement.get("status") in {"moved", "removed_copy"}:
                    destroyed.append(item["id"])
                    draws[controller_id] = draws.get(controller_id, 0) + 2
            self.prune_rules_ongoing_effects()
            for pid, count in draws.items():
                self.draw_rules_cards(pid, count)
            return {
                "kind": result.get("kind"),
                "status": "destroyed" if destroyed else "nothing",
                "itemIds": destroyed, "draws": draws,
            }
        if result.get("kind") == "power_counter_from_other_target":
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
            base = int(self.card_rules.get(reference.get("cardId"), {}).get("power") or 0)
            counters = weakened.setdefault("counters", {})
            counters["power"] = int(counters.get("power") or 0) - base
            return {
                "kind": result.get("kind"), "status": "weakened",
                "itemId": weakened["id"], "value": -base,
            }
        if result.get("kind") == "destroy_all_tokens":
            removed = []
            for item in list(self.battlefield):
                if item.get("isTokenCard"):
                    movement = self._rules_remove_field_item(
                        item, item.get("ownerId"), "graveyard", "top"
                    )
                    if movement.get("status") in {"moved", "removed_copy"}:
                        removed.append(item["id"])
            self.prune_rules_ongoing_effects()
            return {
                "kind": result.get("kind"),
                "status": "destroyed" if removed else "nothing",
                "itemIds": removed,
            }
        if result.get("kind") == "exile_all_wills_and_interzones":
            removed = []
            for item in list(self.battlefield):
                card_type = self.card_rules.get(item.get("cardId"), {}).get("type")
                in_interzone = (
                    card_type == "manifestation"
                    and self.rules_field_zone(item) == "interzone"
                )
                if card_type not in RULES_WILL_TYPES and not in_interzone:
                    continue
                movement = self._rules_remove_field_item(
                    item, item.get("ownerId"), "exile", "top"
                )
                if movement.get("status") in {"moved", "removed_copy"}:
                    removed.append(item["id"])
            self.prune_rules_ongoing_effects()
            return {
                "kind": result.get("kind"),
                "status": "exiled" if removed else "nothing",
                "itemIds": removed,
            }
        if result.get("kind") == "consult_support":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "player"
            ), None)
            target_id = (target or {}).get("playerId")
            if target_id not in self.players:
                return {"kind": result.get("kind"), "status": "target_missing"}
            deck = self.players[target_id]["zones"]["deck"]
            discarded, found = [], None
            while deck:
                top_card = deck[0]
                if self.card_rules.get(top_card, {}).get("type") == "manifestation":
                    found = top_card
                    break
                error, _owner, replacement = self.move_zone_card_by_effect(
                    target_id, "deck", target_id, "graveyard", top_card, "top"
                )
                if error:
                    break
                if not replacement:
                    discarded.append(top_card)
            if found is None:
                return {
                    "kind": result.get("kind"), "status": "no_manifestation",
                    "discarded": discarded,
                }
            owner_id = self.take_zone_card(target_id, "deck", found)
            seat = self.players[target_id].get("seat")
            item = {
                "id": new_id(), "ownerId": owner_id, "controllerId": target_id,
                "cardId": found, "x": 740.0, "y": 620.0 if seat != 1 else 880.0,
                "faceUp": True, "rotation": 0.0, "counters": {}, "stackedOn": None,
            }
            self.mark_rules_support_entry(item)
            self.battlefield.append(item)
            return {
                "kind": result.get("kind"), "status": "support",
                "cardId": found, "itemId": item["id"],
                "controllerId": target_id, "discarded": discarded,
            }
        if result.get("kind") == "humiliate_target":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "card"
            ), None)
            item = self.find_battlefield_item((target or {}).get("itemId"))
            if item is None:
                return {"kind": result.get("kind"), "status": "target_missing"}
            item["temperamentOverride"] = "hollow"
            counters = item.setdefault("counters", {})
            counters["power"] = int(counters.get("power") or 0) - 1
            controller_id = self.rules_item_controller_id(item)
            self.adjust_rules_score(controller_id, -5)
            return {
                "kind": result.get("kind"), "status": "humiliated",
                "itemId": item["id"], "controllerId": controller_id,
            }
        if result.get("kind") == "mill_deck_per_confrontation_manifestation":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "player"
            ), None)
            target_id = (target or {}).get("playerId")
            if target_id not in self.players:
                return {"kind": result.get("kind"), "status": "target_missing"}
            count = len([
                item for item in self.rules_confrontation_items(target_id, ("confrontation",))
                if not item.get("isTokenCard") and not item.get("isTokenCopy")
            ])
            for _index in range(count):
                deck = self.players[target_id]["zones"]["deck"]
                if not deck:
                    break
                error, _owner, replacement = self.move_zone_card_by_effect(
                    target_id, "deck", target_id, "graveyard", deck[0], "top"
                )
                if error:
                    break
            return {
                "kind": result.get("kind"),
                "status": "discarded" if count else "nothing",
                "count": count, "targetPlayerId": target_id,
            }
        if result.get("kind") == "sacrifice_other_confrontation_for_essence":
            source_id = (action.get("source") or {}).get("itemId")
            sacrificed, limbo = [], 0
            for item in list(self.rules_confrontation_items(player_id, ("confrontation",))):
                if item.get("id") == source_id:
                    continue
                movement = self._rules_remove_field_item(
                    item, item.get("ownerId"), "graveyard", "top"
                )
                if movement.get("status") == "moved":
                    limbo += 1
                if movement.get("status") in {"moved", "removed_copy"}:
                    sacrificed.append(item["id"])
            self.prune_rules_ongoing_effects()
            if limbo:
                self.add_rules_excess_essence(
                    player_id, [{"temperament": "transcendent", "amount": limbo}]
                )
            return {
                "kind": result.get("kind"),
                "status": "sacrificed" if sacrificed else "nothing",
                "itemIds": sacrificed, "essences": limbo,
            }
        if result.get("kind") == "exile_source_then_shuffle_limbo_and_interzone":
            source = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
            if source is not None:
                self._rules_remove_field_item(source, source.get("ownerId"), "exile", "top")
            moved = []
            for item in list(self.rules_confrontation_items(zones=("interzone",))):
                movement = self._rules_remove_field_item(
                    item, item.get("ownerId"), "deck", "top"
                )
                if movement.get("status") == "moved":
                    moved.append(item.get("cardId"))
            for pid in self.players:
                for card_id in list(self.players[pid]["zones"]["graveyard"]):
                    error, _owner, replacement = self.move_zone_card_by_effect(
                        pid, "graveyard", pid, "deck", card_id, "top"
                    )
                    if not error and not replacement:
                        moved.append(card_id)
            for pid in self.players:
                random.shuffle(self.players[pid]["zones"]["deck"])
            self.prune_rules_ongoing_effects()
            return {"kind": result.get("kind"), "status": "shuffled", "cardIds": moved}
        if result.get("kind") == "destroy_target_tokens_for_controller":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "card"
            ), None)
            item = self.find_battlefield_item((target or {}).get("itemId"))
            if item is None:
                return {"kind": result.get("kind"), "status": "target_missing"}
            controller_id = self.rules_item_controller_id(item)
            if item.get("isTokenCard"):
                base = int(item.get("power") or 0)
            else:
                base = int(self.card_rules.get(item.get("cardId"), {}).get("power") or 0)
            movement = self._rules_remove_field_item_by_effect(
                item, item.get("ownerId"), "graveyard", "top", reason="destroy"
            )
            self.prune_rules_ongoing_effects()
            if movement.get("status") not in {"moved", "removed_copy"}:
                return {"kind": result.get("kind"), "status": movement.get("status")}
            created = [
                self.create_rules_token_copy(
                    (action.get("source") or {}).get("cardId"), controller_id,
                    source_item_id=(action.get("source") or {}).get("itemId"),
                    hollow=True, effects_disabled=True, generic_power=1,
                )
                for _index in range(max(0, base))
            ]
            return {
                "kind": result.get("kind"), "status": "destroyed",
                "controllerId": controller_id, "tokens": len(created),
            }
        if result.get("kind") == "first_manifestations_to_interzone_tokens":
            counts = {}
            for pid in self.players:
                first = self.find_battlefield_item(
                    self.rules_engine.get("firstManifestationItemIds", {}).get(pid)
                )
                if (
                    first is None
                    or self.rules_item_controller_id(first) != pid
                    or self.rules_field_zone(first) != "confrontation"
                ):
                    continue
                base = (
                    int(first.get("power") or 0) if first.get("isTokenCard")
                    else int(self.card_rules.get(first.get("cardId"), {}).get("power") or 0)
                )
                if self.rules_interzone_slot_count(pid) >= self.rules_interzone_capacity(pid):
                    anchor = self.rules_interzone_share_anchor(pid, first)
                    if anchor:
                        first.update({
                            "stackedOn": anchor, "stackOffsetX": 18.0,
                            "stackOffsetY": 18.0,
                        })
                    else:
                        first["stackedOn"] = None
                else:
                    first["stackedOn"] = None
                first["fieldZone"] = "interzone"
                first["isSupport"] = False
                self.mark_rules_interzone_entry(first)
                counts[pid] = max(0, base)
            source = action.get("source") or {}
            created = {}
            for pid, count in counts.items():
                created[pid] = [
                    self.create_rules_token_copy(
                        source.get("cardId"), pid,
                        source_item_id=source.get("itemId"),
                        hollow=True, effects_disabled=True, generic_power=1,
                    )["id"]
                    for _index in range(count)
                ]
            return {
                "kind": result.get("kind"),
                "status": "resolved" if counts else "nothing",
                "tokens": {pid: len(ids) for pid, ids in created.items()},
            }
        if result.get("kind") == "stalemate_to_support_disabled":
            moved = []
            for item in list(self.rules_confrontation_items(player_id, ("stalemate",))):
                item["stackedOn"] = None
                self.mark_rules_support_entry(item)
                moved.append(item["id"])
            effects = []
            for item_id in moved:
                item = self.find_battlefield_item(item_id)
                effects.extend(self.create_rules_ongoing_effects({
                    **action,
                    "targets": [{
                        "kind": "card", "itemId": item_id,
                        "cardId": item.get("cardId"), "ownerId": item.get("ownerId"),
                    }],
                    "ability": {
                        "id": f'{(action.get("ability") or {}).get("id")}:disabled',
                        "ongoingEffect": {
                            "kind": "lose_effects", "duration": "until_end_of_turn",
                        },
                    },
                }))
            return {
                "kind": result.get("kind"),
                "status": "supported" if moved else "nothing",
                "itemIds": moved, "effects": len(effects),
            }
        if result.get("kind") == "timidette_support_to_deck_bottom":
            source_id = (action.get("source") or {}).get("itemId")
            kept = {source_id} | {
                entry.get("itemId") for entry in action.get("targets") or []
                if entry.get("kind") == "card"
            }
            moved = []
            for item in list(self.battlefield):
                if (
                    not item.get("isSupport") or item.get("id") in kept
                    or not item.get("faceUp", True)
                ):
                    continue
                movement = self._rules_remove_field_item(
                    item, item.get("ownerId"), "deck", "bottom"
                )
                if movement.get("status") in {"moved", "removed_copy"}:
                    moved.append(item["id"])
            self.prune_rules_ongoing_effects()
            return {
                "kind": result.get("kind"),
                "status": "moved" if moved else "nothing", "itemIds": moved,
            }
        if result.get("kind") == "destroy_persistent_will_refund_essence":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "card"
            ), None)
            item = self.find_battlefield_item((target or {}).get("itemId"))
            metadata = self.card_rules.get((item or {}).get("cardId"), {})
            if item is None or metadata.get("type") != "persistent_will":
                return {"kind": result.get("kind"), "status": "target_missing"}
            controller_id = self.rules_item_controller_id(item)
            cost = int(metadata.get("cost") or 0)
            temperament = next(iter(metadata.get("temperaments") or []), "hollow")
            movement = self._rules_remove_field_item_by_effect(
                item, item.get("ownerId"), "graveyard", "top", reason="destroy"
            )
            self.prune_rules_ongoing_effects()
            if movement.get("status") not in {"moved", "removed_copy"}:
                return {"kind": result.get("kind"), "status": movement.get("status")}
            if cost > 0:
                self.add_rules_excess_essence(
                    controller_id, [{"temperament": temperament, "amount": cost}]
                )
            return {
                "kind": result.get("kind"), "status": "destroyed",
                "controllerId": controller_id, "essences": cost,
                "temperament": temperament,
            }
        if result.get("kind") == "optional_discard_manifestation_weaken_target":
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
        if result.get("kind") == "optional_discard_up_to":
            hand = player["zones"]["hand"]
            if not hand:
                return {"kind": result.get("kind"), "status": "no_hand_card"}
            if not action.get("optionalAccepted"):
                return {"kind": result.get("kind"), "status": "declined"}
            count = min(int(result.get("value") or 1), len(hand))
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "discard_from_hand",
                "playerId": player_id, "count": count, "upTo": True,
                "actionId": action.get("id"),
                "controllerId": action.get("controllerId"),
                "sourceCardId": (action.get("source") or {}).get("cardId"),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "discard_from_hand", "playerId": player_id,
                "count": count, "upTo": True,
            }
        if result.get("kind") == "return_source_to_hand_restricted":
            source_item = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
            if source_item is None:
                return {"kind": result.get("kind"), "status": "source_missing"}
            movement = self._rules_remove_field_item_by_effect(
                source_item, source_item.get("ownerId"), "hand", "top", reason="return"
            )
            if movement.get("status") == "moved":
                self.rules_engine["playRestrictions"].append({
                    "id": new_id(), "playerId": source_item["ownerId"],
                    "cardId": source_item["cardId"], "turn": self.phase_tracker["turn"],
                    "sourceActionId": action.get("id"),
                })
            self.prune_rules_ongoing_effects()
            return {
                "kind": result.get("kind"), "status": movement.get("status"),
                "cardId": source_item.get("cardId"), "playRestrictedUntilTurnEnd": True,
            }
        if result.get("kind") == "chain_discarded_manifestation_from_target_deck":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "player"
            ), None)
            target_id = (target or {}).get("playerId")
            if target_id not in self.players:
                return {"kind": result.get("kind"), "status": "target_missing"}
            deck = self.players[target_id]["zones"]["deck"]
            discarded, found = [], None
            while deck:
                top_card = deck[0]
                if self.card_rules.get(top_card, {}).get("type") == "manifestation":
                    found = top_card
                    break
                error, _owner, replacement = self.move_zone_card_by_effect(
                    target_id, "deck", target_id, "graveyard", top_card, "top"
                )
                if error:
                    break
                if not replacement:
                    discarded.append(top_card)
            if found is None:
                return {
                    "kind": result.get("kind"), "status": "no_manifestation",
                    "discarded": discarded,
                }
            error, chained = self.chain_rules_manifestation(
                player_id, "deck", found, container_id=target_id,
                action_id=action.get("id"),
                source_card_id=(action.get("source") or {}).get("cardId"),
                chain_controller_id=player_id,
            )
            if error:
                return {
                    "kind": result.get("kind"), "status": "blocked",
                    "error": error, "discarded": discarded, "cardId": found,
                }
            return {
                "kind": result.get("kind"), "status": "chained",
                "cardId": found, "discarded": discarded,
                "targetPlayerId": target_id,
                **({"chain": chained} if isinstance(chained, dict) else {}),
            }
        if result.get("kind") == "score_owner_silent":
            delta = self.adjust_rules_score(
                action.get("controllerId") or player_id, int(result.get("value") or 0),
                observe=False,
            )
            return {"kind": result.get("kind"), "status": "scored", "delta": delta}
        if result.get("kind") == "roll_d6_gain_half_essence":
            roll = random.randint(1, 6)
            amount = (roll + 1) // 2
            owner_id = action.get("controllerId") or player_id
            self.add_rules_excess_essence(
                owner_id, [{"temperament": "transcendent", "amount": amount, "retained": True}]
            )
            return {
                "kind": result.get("kind"), "status": "rolled",
                "roll": roll, "essences": amount, "playerId": owner_id,
            }
        if result.get("kind") == "interzone_target_to_support":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "card"
            ), None)
            item = self.find_battlefield_item((target or {}).get("itemId"))
            if item is None or self.rules_field_zone(item) != "interzone":
                return {"kind": result.get("kind"), "status": "target_missing"}
            item["stackedOn"] = None
            self.mark_rules_support_entry(item)
            triggered = self.queue_rules_support_entry_triggers(
                item, played=False, from_zone="interzone", defer=True,
            )
            if triggered:
                self.queue_rules_simultaneous_actions(triggered)
            return {
                "kind": result.get("kind"), "status": "support",
                "itemId": item["id"], "cardId": item.get("cardId"),
            }
        if result.get("kind") == "flower_of_evil_burst":
            owner_id = action.get("controllerId") or player_id
            gained = {}
            for pid in self.players:
                if pid != owner_id:
                    gained[pid] = self.adjust_rules_score(pid, 5)
            self.add_rules_excess_essence(
                owner_id, [{"temperament": "transcendent", "amount": 1}]
            )
            return {
                "kind": result.get("kind"), "status": "resolved",
                "opponentGains": gained, "essences": 1,
            }
        if result.get("kind") == "discard_any_then_lose_per_remaining":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "player"
            ), None)
            target_id = (target or {}).get("playerId")
            if target_id not in self.players:
                return {"kind": result.get("kind"), "status": "target_missing"}
            if self.rules_hand_is_immune(target_id, player_id):
                return {"kind": result.get("kind"), "status": "prevented_immunity"}
            hand = self.players[target_id]["zones"]["hand"]
            if not hand:
                return {"kind": result.get("kind"), "status": "no_hand_card"}
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "discard_from_hand",
                "playerId": target_id, "count": len(hand), "upTo": True,
                "lossPerRemaining": 5,
                "actionId": action.get("id"),
                "controllerId": action.get("controllerId"),
                "sourceCardId": (action.get("source") or {}).get("cardId"),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "discard_from_hand", "playerId": target_id,
                "count": len(hand), "upTo": True,
            }
        if result.get("kind") == "optional_discard_wills_for_power":
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
        if result.get("kind") == "return_other_limbo_card_to_hand":
            source_card = (action.get("source") or {}).get("cardId")
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "zone_card" and entry.get("cardId") != source_card
            ), None)
            if target is None:
                return {"kind": result.get("kind"), "status": "target_missing"}
            error, _owner, replacement = self.move_zone_card_by_effect(
                target.get("containerId"), "graveyard", target.get("containerId"),
                "hand", target.get("cardId"), "top",
            )
            return {
                "kind": result.get("kind"),
                "status": "error" if error else "returned",
                "cardId": target.get("cardId"),
            }
        if result.get("kind") == "shuffle_limbo_targets_into_deck":
            source_card = (action.get("source") or {}).get("cardId")
            moved = []
            for target in action.get("targets") or []:
                if target.get("kind") != "zone_card" or target.get("cardId") == source_card:
                    continue
                error, owner_id, replacement = self.move_zone_card_by_effect(
                    target.get("containerId"), "graveyard", target.get("containerId"),
                    "deck", target.get("cardId"), "top",
                )
                if not error and not replacement:
                    moved.append(target.get("cardId"))
            for pid in {t.get("containerId") for t in action.get("targets") or []}:
                if pid in self.players:
                    random.shuffle(self.players[pid]["zones"]["deck"])
            return {
                "kind": result.get("kind"),
                "status": "shuffled" if moved else "nothing", "cardIds": moved,
            }
        if result.get("kind") in {
            "unless_payment_deck_discard", "unless_payment_lose_effects",
            "unless_opponent_payment_lock_support_entries",
        }:
            if result.get("kind") == "unless_opponent_payment_lock_support_entries":
                payer_id = self.other_rules_player_id(player_id)
                on_decline = {"kind": "lock_support_entries"}
            elif result.get("kind") == "unless_payment_deck_discard":
                payer_id = (action.get("source") or {}).get("containerId")
                on_decline = {"kind": "deck_discard", "count": int(result.get("count") or 1)}
            else:
                target = next((
                    entry for entry in action.get("targets") or [] if entry.get("kind") == "card"
                ), None)
                item = self.find_battlefield_item((target or {}).get("itemId"))
                if item is None:
                    return {"kind": result.get("kind"), "status": "target_missing"}
                payer_id = self.rules_item_controller_id(item)
                on_decline = {"kind": "lose_effects", "itemId": item["id"]}
            if payer_id not in self.players:
                return {"kind": result.get("kind"), "status": "payer_missing"}
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "effect_payment", "playerId": payer_id,
                "payment": result.get("payment"),
                "requirements": self.rules_requirements_from_symbols(result.get("payment")),
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "targetCardId": (action.get("source") or {}).get("cardId"),
                "onDecline": on_decline,
                "actionId": action.get("id"),
                "controllerId": action.get("controllerId"),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "effect_payment", "playerId": payer_id,
                "payment": result.get("payment"),
            }
        if result.get("kind") == "restore_source_counter":
            source_item = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
            if source_item is None:
                return {"kind": result.get("kind"), "status": "source_missing"}
            counters = source_item.setdefault("counters", {})
            name = str(result.get("counter") or "")
            key = next((k for k in counters if str(k).casefold() == name.casefold()), name)
            counters[key] = int(result.get("value") or 0)
            return {"kind": result.get("kind"), "status": "restored", "counter": name, "value": counters[key]}
        if result.get("kind") == "choose_points_or_weaken_first":
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
        if result.get("kind") == "search_deck_to_hand":
            deck = list(player["zones"]["deck"])
            if not deck:
                return {"kind": result.get("kind"), "status": "no_cards"}
            count = min(int(result.get("count") or 1), len(deck))
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "discard_from_hand",
                "playerId": player_id, "count": count, "upTo": bool(result.get("upTo")),
                "candidateCardIds": sorted(deck),
                "actionId": action.get("id"),
                "controllerId": action.get("controllerId"),
                "sourceCardId": (action.get("source") or {}).get("cardId"),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "discard_from_hand", "playerId": player_id,
                "count": count, "upTo": bool(result.get("upTo")), "search": True,
            }
        if result.get("kind") == "hand_manifestation_choice" and (action.get("cost") or {}).get("revealedCard"):
            revealed = action["cost"]["revealedCard"]
            payload = {
                "kind": result.get("kind"), "status": "resolved",
                "cardId": revealed.get("cardId"), "power": revealed.get("power"),
            }
            if result.get("destroyTarget"):
                target = next((
                    entry for entry in action.get("targets") or [] if entry.get("kind") == "card"
                ), None)
                target_item = self.find_battlefield_item((target or {}).get("itemId"))
                if (
                    target_item is not None
                    and self.rules_manifestation_base_power(target_item) <= int(revealed.get("power") or 0)
                ):
                    movement = self._rules_remove_field_item_by_effect(
                        target_item, target_item.get("ownerId"), "graveyard", "top", reason="destroy"
                    )
                    self.prune_rules_ongoing_effects()
                    payload["destroyed"] = {"itemId": target_item["id"], "status": movement.get("status")}
                else:
                    payload["destroyed"] = None
            if result.get("drawByBasePower"):
                payload["drawn"] = self.draw_rules_cards(player_id, int(revealed.get("power") or 0))
            return payload
        if result.get("kind") == "hand_manifestation_choice":
            hand = player["zones"]["hand"]
            if not any(self.card_rules.get(c, {}).get("type") == "manifestation" for c in hand):
                return {"kind": result.get("kind"), "status": "no_hand_card"}
            if result.get("optional") and not action.get("optionalAccepted"):
                return {"kind": result.get("kind"), "status": "declined"}
            target = next((
                entry for entry in action.get("targets") or [] if entry.get("kind") == "card"
            ), None)
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "discard_from_hand",
                "playerId": player_id, "count": 1, "requireManifestation": True,
                "destination": result.get("destination"),
                "drawByBasePower": bool(result.get("drawByBasePower")),
                "destroyTargetItemId": (
                    (target or {}).get("itemId") if result.get("destroyTarget") else None
                ),
                "actionId": action.get("id"),
                "controllerId": action.get("controllerId"),
                "sourceCardId": (action.get("source") or {}).get("cardId"),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "discard_from_hand", "playerId": player_id,
                "count": 1, "requireManifestation": True,
            }
        if result.get("kind") == "destroy_random_vessel_manifestations":
            source = action.get("source") or {}
            container_id = source.get("containerId")
            if container_id not in self.players:
                return {"kind": result.get("kind"), "status": "source_missing"}
            pool = list(self.players[container_id]["zones"].get("receptacle", []))
            if source.get("cardId") in pool:
                pool.remove(source.get("cardId"))
            pool = [
                cid for cid in pool
                if self.card_rules.get(cid, {}).get("type") == "manifestation"
            ]
            random.shuffle(pool)
            destroyed = []
            for card_id in pool[:int(result.get("count") or 1)]:
                owner_id = self.card_owner_in_zone(container_id, "receptacle", card_id)
                if owner_id is None:
                    continue
                error, _owner, replacement = self.move_zone_card_by_effect(
                    container_id, "receptacle", owner_id, "graveyard", card_id, "top"
                )
                if not error and not replacement:
                    destroyed.append(card_id)
            return {
                "kind": result.get("kind"),
                "status": "destroyed" if destroyed else "nothing", "cardIds": destroyed,
            }
        if result.get("kind") in {"roll_discard_deck_gain_power", "opponents_discard_deck_by_source_roll"}:
            source_item = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
            if source_item is None:
                return {"kind": result.get("kind"), "status": "source_missing"}
            if result.get("kind") == "roll_discard_deck_gain_power":
                roll = random.randint(1, 6)
                discarded = 0
                deck = self.players[player_id]["zones"]["deck"]
                for _index in range(min(roll, len(deck))):
                    error, _owner, replacement = self.move_zone_card_by_effect(
                        player_id, "deck", player_id, "graveyard", deck[0], "top"
                    )
                    if error:
                        break
                    if not replacement:
                        discarded += 1
                source_item["rollDiscarded"] = discarded
                if discarded:
                    counters = source_item.setdefault("counters", {})
                    counters["power"] = int(counters.get("power") or 0) + discarded
                return {
                    "kind": result.get("kind"), "status": "resolved",
                    "roll": roll, "discarded": discarded,
                }
            amount = int(source_item.get("rollDiscarded") or 0)
            discarded = {}
            for pid in self.players:
                if pid == player_id:
                    continue
                deck = self.players[pid]["zones"]["deck"]
                for _index in range(min(amount, len(deck))):
                    error, _owner, replacement = self.move_zone_card_by_effect(
                        pid, "deck", pid, "graveyard", deck[0], "top"
                    )
                    if error:
                        break
                    discarded[pid] = discarded.get(pid, 0) + (0 if replacement else 1)
            return {
                "kind": result.get("kind"),
                "status": "discarded" if discarded else "nothing", "discarded": discarded,
            }
        if result.get("kind") == "exile_confrontation_stalemate_and_source":
            removed = []
            source_id = (action.get("source") or {}).get("itemId")
            for item in list(self.rules_confrontation_items(None, ("confrontation", "stalemate"))):
                movement = self._rules_remove_field_item(item, item.get("ownerId"), "exile", "top")
                if movement.get("status") in {"moved", "removed_copy"}:
                    removed.append(item["id"])
            source_item = self.find_battlefield_item(source_id)
            if source_item is not None:
                self._rules_remove_field_item(source_item, source_item.get("ownerId"), "exile", "top")
            self.prune_rules_ongoing_effects()
            return {
                "kind": result.get("kind"),
                "status": "exiled" if removed else "nothing", "itemIds": removed,
            }
        if result.get("kind") == "set_interzone_power":
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
                    "kind": "power_set_maximum",
                    "duration": "until_end_of_turn",
                    "startedTurn": self.phase_tracker["turn"],
                    "value": int(result.get("value") or 1),
                }
                self.rules_engine["ongoingEffects"].append(effect)
                effects.append(effect["id"])
            return {
                "kind": result.get("kind"),
                "status": "set" if effects else "nothing", "effectIds": effects,
            }
        if result.get("kind") == "exile_tribute_manifestation_score_others":
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
        if result.get("kind") == "exile_limbo_wills_add_power_each":
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
                if not error:
                    exiled.append(card_id)
            if exiled and source_item is not None:
                self.rules_engine["ongoingEffects"].append({
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
        if result.get("kind") == "drain_excess_essence_power":
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
                self.rules_engine["ongoingEffects"].append({
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
        if result.get("kind") == "exile_source_card_from_limbo":
            source = action.get("source") or {}
            owner_id = source.get("ownerId") or player_id
            card_id = source.get("cardId")
            if card_id not in self.players.get(owner_id, {}).get("zones", {}).get("graveyard", []):
                return {"kind": result.get("kind"), "status": "source_missing"}
            error, _owner, _replacement = self.move_zone_card_by_effect(
                owner_id, "graveyard", owner_id, "exile", card_id, "top"
            )
            return {
                "kind": result.get("kind"),
                "status": "error" if error else "exiled", "cardId": card_id,
            }
        if result.get("kind") == "limbo_source_to_support":
            source = action.get("source") or {}
            owner_id = source.get("ownerId") or player_id
            card_id = source.get("cardId")
            if (
                owner_id not in self.players
                or card_id not in self.players[owner_id]["zones"]["graveyard"]
            ):
                return {"kind": result.get("kind"), "status": "source_missing"}
            self.take_zone_card(owner_id, "graveyard", card_id)
            seat = self.players[owner_id].get("seat")
            item = {
                "id": new_id(), "ownerId": owner_id, "controllerId": owner_id,
                "cardId": card_id, "x": 740.0, "y": 620.0 if seat != 1 else 880.0,
                "faceUp": True, "rotation": 0.0, "counters": {}, "stackedOn": None,
            }
            self.mark_rules_support_entry(item)
            self.battlefield.append(item)
            return {
                "kind": result.get("kind"), "status": "support",
                "cardId": card_id, "itemId": item["id"],
            }
        if result.get("kind") == "healing_bond":
            firsts = {}
            for pid, item_id in (self.rules_engine.get("firstManifestationItemIds") or {}).items():
                item = self.find_battlefield_item(item_id)
                if item is not None:
                    firsts[pid] = item
            bases = {
                pid: (
                    int(item.get("power") or 0) if item.get("isTokenCard")
                    else int(self.card_rules.get(item.get("cardId"), {}).get("power") or 0)
                )
                for pid, item in firsts.items()
            }
            highest = max(bases.values()) if bases else 0
            boosted = []
            for pid, item in firsts.items():
                if bases[pid] >= highest:
                    continue
                self.create_rules_ongoing_effects({
                    **action,
                    "targets": [{
                        "kind": "card", "itemId": item["id"], "cardId": item.get("cardId"),
                        "ownerId": item.get("ownerId"),
                    }],
                    "ability": {
                        "id": f'{(action.get("ability") or {}).get("id")}:bond',
                        "ongoingEffect": {
                            "kind": "power_modifier", "value": 2,
                            "duration": "until_end_of_turn",
                        },
                    },
                })
                self.adjust_rules_score(pid, 10)
                boosted.append(pid)
            return {
                "kind": result.get("kind"),
                "status": "boosted" if boosted else "nothing", "playerIds": boosted,
            }
        if result.get("kind") == "destroy_next_opponent_confrontation_entry":
            for pid in self.players:
                if pid != player_id:
                    self.rules_engine.setdefault("destroyNextEntries", []).append({
                        "controllerId": pid, "turn": self.phase_tracker["turn"],
                    })
            return {"kind": result.get("kind"), "status": "armed"}
        if result.get("kind") == "each_player_stalemate_own_confrontation":
            moved, queue = [], []
            for pid in self.players:
                candidates = [
                    item["id"] for item in self.rules_confrontation_items(pid)
                    if not self.rules_item_zone_locked(item)
                ]
                if len(candidates) == 1:
                    moved.append(self.rules_stalemate_item(candidates[0]))
                elif candidates:
                    queue.append({"playerId": pid, "candidateItemIds": candidates})
            payload = {"kind": result.get("kind"), "status": "stalemated", "itemIds": moved}
            if queue:
                choice = self.rules_next_pick_own_item_choice(
                    queue, action.get("id"),
                    (action.get("source") or {}).get("cardId"), moved,
                )
                payload.update({
                    "kind": "choice_required", "choiceId": choice["id"],
                    "choiceKind": "pick_own_item", "playerId": choice["playerId"],
                })
            return payload
        if result.get("kind") == "stalemate_confrontation":
            if result.get("scope") == "winner":
                winner_id = (self.rules_engine.get("confrontationResult") or {}).get("winnerId")
                items = (
                    self.rules_confrontation_items(winner_id)
                    if winner_id in self.players else []
                )
            else:
                items = self.rules_confrontation_items()
            moved = []
            for item in items:
                item["fieldZone"] = "stalemate"
                item.pop("isSupport", None)
                item.pop("supportUntilTurn", None)
                if result.get("lockZone"):
                    item["zoneLockTurn"] = self.phase_tracker["turn"]
                moved.append(item["id"])
            if result.get("lockSupportEntries"):
                self.rules_engine.setdefault("supportLocks", []).append({
                    "turn": self.phase_tracker["turn"], "playerId": None,
                })
            self.prune_rules_ongoing_effects()
            return {
                "kind": result.get("kind"), "status": "stalemated" if moved else "nothing",
                "itemIds": moved, "locked": bool(result.get("lockZone")),
            }
        if result.get("kind") == "lock_support_entries":
            self.rules_engine.setdefault("supportLocks", []).append({
                "turn": self.phase_tracker["turn"],
                "playerId": player_id if result.get("scope") == "controller" else None,
            })
            return {"kind": result.get("kind"), "status": "locked", "scope": result.get("scope")}
        if result.get("kind") == "exile_limbo_targets_create_tokens":
            exiled = []
            for target in action.get("targets") or []:
                if target.get("kind") != "zone_card":
                    continue
                error, _owner, replacement = self.move_zone_card_by_effect(
                    target.get("containerId"), "graveyard", target.get("containerId"),
                    "exile", target.get("cardId"), "top",
                )
                if not error and not replacement:
                    exiled.append(target.get("cardId"))
            source = action.get("source") or {}
            tokens = [
                self.create_rules_token_copy(
                    source.get("cardId"), player_id, source_item_id=source.get("itemId"),
                    effects_disabled=True, generic_power=1,
                    generic_temperament="choleric",
                )["id"]
                for _index in exiled
            ]
            return {
                "kind": result.get("kind"),
                "status": "created" if tokens else "nothing",
                "cardIds": exiled, "tokens": len(tokens),
            }
        if result.get("kind") == "double_target_base_power":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "card"
            ), None)
            item = self.find_battlefield_item((target or {}).get("itemId"))
            if item is None:
                return {"kind": result.get("kind"), "status": "target_missing"}
            base = int(self.card_rules.get(item.get("cardId"), {}).get("power") or 0)
            counters = item.setdefault("counters", {})
            counters["power"] = int(counters.get("power") or 0) + base
            return {
                "kind": result.get("kind"), "status": "doubled",
                "itemId": item["id"], "value": base,
            }
        if result.get("kind") == "destroy_random_interzone_target_player":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "player"
            ), None)
            target_id = (target or {}).get("playerId")
            candidates = [
                item for item in self.rules_confrontation_items(target_id, ("interzone",))
            ] if target_id in self.players else []
            if not candidates:
                return {"kind": result.get("kind"), "status": "nothing_to_destroy"}
            item = random.choice(candidates)
            movement = self._rules_remove_field_item_by_effect(
                item, item.get("ownerId"), "graveyard", "top", reason="destroy"
            )
            self.prune_rules_ongoing_effects()
            return {
                "kind": result.get("kind"), "status": movement.get("status"),
                "targetPlayerId": target_id, "cardId": item.get("cardId"),
                "itemId": item.get("id"),
            }
        if result.get("kind") == "destroy_target_gain_points":
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
        if result.get("kind") == "exile_target_on_win":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "card"
            ), None)
            item = self.find_battlefield_item((target or {}).get("itemId"))
            if item is None:
                return {"kind": result.get("kind"), "status": "target_missing"}
            self.create_rules_effect_memory(
                item["ownerId"], item["cardId"], "win_destination_exile",
                controller_id=player_id, source_action_id=action.get("id"),
                data={"itemId": item["id"]},
            )
            return {"kind": result.get("kind"), "status": "marked", "itemId": item["id"]}
        if result.get("kind") == "shuffle_hand_into_deck_and_draw":
            player = self.players[player_id]
            for card_id in list(player["zones"]["hand"]):
                self.move_zone_card_by_effect(
                    player_id, "hand", player_id, "deck", card_id, "top"
                )
            random.shuffle(player["zones"]["deck"])
            drawn = self.draw_rules_cards(player_id, 7)
            return {"kind": result.get("kind"), "status": "done", "draw": drawn}
        if result.get("kind") == "exile_limbo_targets_add_power":
            source_item = self.find_battlefield_item(
                (action.get("source") or {}).get("itemId")
            )
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
                if error:
                    continue
                exiled.append(card_id)
                added += int(self.card_rules.get(card_id, {}).get("power") or 0)
            if exiled and source_item is not None:
                counters = source_item.setdefault("counters", {})
                counters["power"] = int(counters.get("power") or 0) + added
            return {
                "kind": result.get("kind"), "status": "exiled" if exiled else "nothing",
                "cardIds": exiled, "power": added,
            }
        if result.get("kind") == "deck_discard_then_weaken":
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
                            "duration": "until_end_of_turn",
                        },
                    },
                })
            return {
                "kind": result.get("kind"), "status": "done",
                "discarded": discarded, "manifestations": manifestations,
                "effects": len(effects),
            }
        if result.get("kind") == "move_zone_target_to_own_vessel":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "zone_card"
            ), None)
            container_id = (target or {}).get("containerId")
            zone = (target or {}).get("zone")
            card_id = (target or {}).get("cardId")
            owner_id = self.card_owner_in_zone(container_id, zone, card_id)
            if owner_id is None or owner_id == player_id:
                return {"kind": result.get("kind"), "status": "target_missing"}
            self.take_zone_card(container_id, zone, card_id)
            self.put_zone_card(player_id, "receptacle", card_id, owner_id)
            self.record_rules_observed_event(
                "manifestation_enters_opponent_vessel", owner_id
            )
            return {
                "kind": result.get("kind"), "status": "moved",
                "cardId": card_id, "ownerId": owner_id,
                "containerId": player_id, "zone": "receptacle",
            }
        if result.get("kind") in {
            "return_target_player_support",
            "return_target_player_interzone_to_deck_top",
        }:
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "player"
            ), None)
            target_id = (target or {}).get("playerId")
            if target_id not in self.players:
                return {"kind": result.get("kind"), "status": "target_missing"}
            support_mode = result.get("kind") == "return_target_player_support"
            moved, prevented = [], []
            returned_by_owner = {}
            for item in list(self.battlefield):
                if (
                    self.rules_item_controller_id(item) != target_id
                    or self.rules_item_card_rules(item).get("type") != "manifestation"
                ):
                    continue
                if support_mode:
                    if not item.get("isSupport") or self.rules_field_zone(item) != "confrontation":
                        continue
                elif self.rules_field_zone(item) != "interzone":
                    continue
                if (
                    self.rules_item_card_rules(item).get("adamant")
                    and self.rules_item_effects_active(item)
                    and target_id != player_id
                ):
                    prevented.append(item["id"])
                    continue
                movement = self._rules_remove_field_item_by_effect(
                    item, item.get("ownerId"),
                    "hand" if support_mode else "deck", "top", reason="return",
                )
                if movement.get("status") != "moved":
                    continue
                moved.append(item["id"])
                if not support_mode:
                    returned_by_owner.setdefault(item["ownerId"], []).append(item["cardId"])
                if support_mode:
                    self.rules_engine["playRestrictions"].append({
                        "id": new_id(), "playerId": item["ownerId"],
                        "cardId": item["cardId"], "turn": self.phase_tracker["turn"],
                        "sourceActionId": action.get("id"),
                    })
            self.prune_rules_ongoing_effects()
            payload = {
                "kind": result.get("kind"), "status": "moved",
                "targetPlayerId": target_id, "itemIds": moved,
                "preventedItemIds": prevented,
            }
            order_queue = [
                {"playerId": owner_id, "cardIds": list(reversed(card_ids))}
                for owner_id, card_ids in returned_by_owner.items()
                if len(card_ids) > 1
            ]
            if order_queue:
                choice = self.rules_next_deck_order_choice(
                    order_queue, (action.get("source") or {}).get("cardId")
                )
                payload.update({
                    "kind": "choice_required", "choiceId": choice["id"],
                    "choiceKind": "deck_reorder", "playerId": choice["playerId"],
                    "returned": moved,
                })
            return payload
        if result.get("kind") == "create_target_token_copy_in_support":
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
            copy = self.create_rules_token_copy(
                item.get("cardId"), player_id,
                source_item_id=(action.get("source") or {}).get("itemId"),
            )
            return {
                "kind": result.get("kind"),
                "status": "created",
                "targetItemId": item.get("id"),
                "createdItemId": copy["id"],
            }
        if result.get("kind") == "grant_friendly_interzone_support_until_end_turn":
            item_ids = []
            for item in self.rules_confrontation_items(
                player_id, ("interzone",)
            ):
                item["supportUntilTurn"] = self.phase_tracker["turn"]
                item_ids.append(item["id"])
            return {
                "kind": result.get("kind"),
                "status": "granted",
                "itemIds": item_ids,
            }
        if (
            result.get("kind")
            == "create_support_tokens_from_optional_extra_essence"
        ):
            count = max(
                0, int(
                    (action.get("cost") or {}).get(
                        "optionalExtraEssenceSpent"
                    ) or 0
                )
            )
            tokens = [
                self.create_rules_token_copy(
                    None, player_id,
                    source_item_id=(
                        action.get("sourceResolution") or {}
                    ).get("itemId"),
                    hollow=True,
                    effects_disabled=True,
                    generic_power=1,
                )
                for _index in range(count)
            ]
            return {
                "kind": result.get("kind"),
                "status": "created",
                "count": count,
                "itemIds": [item["id"] for item in tokens],
            }
        if result.get("kind") == "create_support_token":
            token = self.create_rules_token_copy(
                None, player_id,
                source_item_id=(action.get("source") or {}).get("itemId"),
                generic_power=result.get("power"),
                generic_temperament=result.get("temperament"),
            )
            return {
                "kind": result.get("kind"),
                "status": "created",
                "createdItemId": token["id"],
                "power": token["power"],
                "temperament": token["temperament"],
            }
        if result.get("kind") == "cleanse_target":
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
            removed_effects = [
                effect for effect in self.rules_engine.get(
                    "ongoingEffects"
                ) or []
                if (
                    effect.get("target", {}).get("itemId") == item_id
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
            metadata = self.rules_item_card_rules(item)
            item["controllerId"] = item.get("ownerId")
            for key in {
                "effectsDisabled", "zeroPowerSustained",
                "temperamentOverride", "supportUntilTurn", "hasFloat",
            }:
                item.pop(key, None)
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
        if result.get("kind") == "create_effect_memory":
            trigger = (action.get("ability") or {}).get("trigger") or {}
            attach_to = result.get("attachTo")
            if attach_to == "event_card":
                owner_id = (action.get("source") or {}).get("ownerId") or player_id
                card_id = (action.get("source") or {}).get("cardId")
            else:
                owner_id = trigger.get("relatedOwnerId") or player_id
                card_id = trigger.get("relatedCardId")
                related_type = self.card_rules.get(card_id, {}).get("type")
                if related_type not in RULES_WILL_TYPES:
                    return {
                        "kind": "create_effect_memory",
                        "status": "related_action_not_will",
                    }
            memory = self.create_rules_effect_memory(
                owner_id, card_id, result.get("memoryKind"),
                controller_id=player_id,
                source_action_id=action.get("id"),
                data={
                    "optional": bool(
                        result.get("optional")
                        and not action.get("optionalAccepted")
                    ),
                    "opponentPayment": result.get("opponentPayment"),
                    "rollReturnOrExile": bool(result.get("rollReturnOrExile")),
                    "requireLostConfrontation": bool(result.get("requireLostConfrontation")),
                },
            )
            return {
                "kind": "create_effect_memory",
                "status": "created" if memory else "invalid",
                "memoryId": memory.get("id") if memory else None,
                "memoryKind": result.get("memoryKind"),
                "cardId": card_id,
                "ownerId": owner_id,
            }
        if result.get("kind") == "add_counter_source":
            source_item = self.find_battlefield_item(
                (action.get("source") or {}).get("itemId")
            )
            if source_item is None:
                return {
                    "kind": "add_counter_source",
                    "status": "source_missing",
                }
            counter_name = str(result.get("counter") or "")
            counters = source_item.setdefault("counters", {})
            counter_key = next((
                key for key in counters
                if str(key).casefold() == counter_name.casefold()
            ), counter_name)
            counters[counter_key] = max(0, int(counters.get(counter_key) or 0) + int(
                result.get("value") or 0
            ))
            return {
                "kind": "add_counter_source",
                "status": "added",
                "itemId": source_item.get("id"),
                "cardId": source_item.get("cardId"),
                "counter": counter_name,
                "value": counters[counter_key],
            }
        if result.get("kind") == "destroy_source":
            source_item = self.find_battlefield_item(
                (action.get("source") or {}).get("itemId")
            )
            if source_item is None:
                return {
                    "kind": "destroy_source",
                    "status": "source_missing",
                }
            movement = self._rules_remove_field_item_by_effect(
                source_item, source_item.get("ownerId"), "graveyard", "top",
                reason="destroy",
            )
            self.prune_rules_ongoing_effects()
            return {
                "kind": "destroy_source",
                "status": movement.get("status"),
                "itemId": source_item.get("id"),
                "cardId": source_item.get("cardId"),
                "ownerId": source_item.get("ownerId"),
                "destination": "graveyard",
                **({
                    "replacement": movement,
                } if movement.get("status") == "suspended" else {}),
            }
        if result.get("kind") == "grant_source_support_until_end_turn":
            source = action.get("source") or {}
            source_item = self.find_battlefield_item(source.get("itemId"))
            if source_item is not None:
                source_item["supportUntilTurn"] = self.phase_tracker["turn"]
                return {
                    "kind": result.get("kind"),
                    "status": "granted",
                    "itemId": source_item.get("id"),
                    "cardId": source_item.get("cardId"),
                    "zone": self.rules_field_zone(source_item),
                }
            if (
                source.get("zone") == "hand"
                and source.get("cardId")
                in self.players[player_id]["zones"]["hand"]
            ):
                permission = {
                    "id": new_id(),
                    "abilityId": (action.get("ability") or {}).get("id"),
                    "playerId": player_id,
                    "cardId": source.get("cardId"),
                    "fromZone": "hand",
                    "phaseIds": ["confrontation_reaction"],
                    "asSupport": True,
                    "turn": self.phase_tracker["turn"],
                }
                self.rules_engine["playPermissions"].append(permission)
                return {
                    "kind": result.get("kind"),
                    "status": "granted",
                    "permissionId": permission["id"],
                    "cardId": source.get("cardId"),
                    "zone": "hand",
                }
            return {
                "kind": result.get("kind"),
                "status": "source_missing",
            }
        if result.get("kind") == "grant_source_support_if_base_higher_than_own_first":
            source_item = self.find_battlefield_item(
                (action.get("source") or {}).get("itemId")
            )
            if source_item is None:
                return {
                    "kind": result.get("kind"),
                    "status": "source_missing",
                }
            controller_id = self.rules_item_controller_id(source_item)
            first_item = self.find_battlefield_item(
                (self.rules_engine.get("firstManifestationItemIds") or {}).get(
                    controller_id
                )
            )
            source_base = int(self.card_rules.get(
                source_item.get("cardId"), {}
            ).get("power") or 0)
            first_base = int(self.card_rules.get(
                (first_item or {}).get("cardId"), {}
            ).get("power") or 0)
            granted = first_item is not None and source_base > first_base
            if granted:
                source_item["supportUntilTurn"] = self.phase_tracker["turn"]
            return {
                "kind": result.get("kind"),
                "status": "granted" if granted else "condition_failed",
                "itemId": source_item.get("id"),
                "sourceBasePower": source_base,
                "firstBasePower": first_base if first_item is not None else None,
            }
        if result.get("kind") == "roll_d6_move_source_to_stalemate_on_odd":
            source_item = self.find_battlefield_item(
                (action.get("source") or {}).get("itemId")
            )
            roll = random.randint(1, 6)
            if source_item is None:
                return {
                    "kind": result.get("kind"),
                    "status": "source_missing", "roll": roll,
                }
            source_item.setdefault("counters", {})["Roll"] = roll
            moved = roll % 2 == 1
            if moved:
                source_item["fieldZone"] = "stalemate"
                source_item.pop("isSupport", None)
                source_item.pop("supportUntilTurn", None)
            return {
                "kind": result.get("kind"),
                "status": "moved" if moved else "unchanged",
                "roll": roll, "itemId": source_item.get("id"),
                "fieldZone": self.rules_field_zone(source_item),
            }
        if result.get("kind") == "score_source_owner":
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
        if result.get("kind") in {
            "move_source_to_owner_deck_top", "move_source_to_owner_exile",
        }:
            source_item = self.find_battlefield_item(
                (action.get("source") or {}).get("itemId")
            )
            if source_item is None:
                return {
                    "kind": result.get("kind"),
                    "status": "source_missing",
                }
            destination = (
                "exile"
                if result.get("kind") == "move_source_to_owner_exile"
                else "deck"
            )
            movement = self._rules_remove_field_item(
                source_item, source_item.get("ownerId"), destination, "top"
            )
            self.prune_rules_ongoing_effects()
            return {
                "kind": result.get("kind"),
                "status": movement.get("status"),
                "movement": movement,
            }
        if result.get("kind") == "return_supports_and_boost_firsts":
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
        if result.get("kind") == "play_limbo_target_as_support":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "zone_card"
            ), None)
            if target is None:
                return {
                    "kind": result.get("kind"),
                    "status": "target_missing",
                }
            owner_id = self.card_owner_in_zone(
                target.get("containerId"), "graveyard",
                target.get("cardId"),
            )
            if owner_id is None:
                return {
                    "kind": result.get("kind"),
                    "status": "target_missing",
                }
            self.take_zone_card(
                target.get("containerId"), "graveyard",
                target.get("cardId"),
            )
            seat = self.players[player_id].get("seat")
            item = {
                "id": new_id(), "ownerId": owner_id,
                "controllerId": player_id,
                "cardId": target.get("cardId"),
                "x": 740.0, "y": 620.0 if seat != 1 else 880.0,
                "faceUp": True, "rotation": 0.0, "counters": {},
                "stackedOn": None,
            }
            self.mark_rules_support_entry(item)
            if result.get("winDestination") == "exile":
                item["supportWinDestination"] = "exile"
            if result.get("losesEffects"):
                item["effectsDisabled"] = True
            self.battlefield.append(item)
            return {
                "kind": result.get("kind"),
                "status": "moved",
                "itemId": item["id"],
                "cardId": item["cardId"],
                "ownerId": owner_id,
                "controllerId": player_id,
            }
        if result.get("kind") == "resolve_target_stack_immediately":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") in {
                    "stack_action", "stack_effect", "stack_item"
                }
            ), None)
            target_action = next((
                entry for entry in self.rules_engine.get("actionStack") or []
                if entry.get("id") == (target or {}).get("actionId")
            ), None)
            if target_action is None:
                return {
                    "kind": result.get("kind"),
                    "status": "target_missing",
                }
            self.rules_engine["actionStack"].remove(target_action)
            self.rules_engine["actionStack"].append(target_action)
            nested = self.resolve_rules_top_action()
            return {
                "kind": result.get("kind"),
                "status": "resolved",
                "targetActionId": target_action.get("id"),
                "resolution": nested,
            }
        if result.get("kind") == "choose_target_score_delta":
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
        if result.get("kind") == "move_counter":
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
        if result.get("kind") == "adjust_target_power":
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
            counters = target_item.setdefault("counters", {})
            counters["power"] = int(counters.get("power") or 0) + value
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
        if result.get("kind") == "schedule_rematch":
            protected_item_ids = [
                item_id for item_id in self.rules_engine.get(
                    "firstManifestationItemIds", {}
                ).values()
                if self.find_battlefield_item(item_id)
            ]
            self.rules_engine["rematchPending"] = {
                "turn": self.phase_tracker["turn"],
                "controllerId": player_id,
                "protectedItemIds": protected_item_ids,
                "sourceActionId": action.get("id"),
            }
            return {
                "kind": "schedule_rematch",
                "status": "scheduled",
                "protectedItemIds": protected_item_ids,
            }
        if result.get("kind") == "change_source_control":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "player"
            ), None)
            controller_id = target.get("playerId") if target else None
            source_item_id = (
                (action.get("sourceResolution") or {}).get("itemId")
                or (action.get("source") or {}).get("itemId")
            )
            source_item = self.find_battlefield_item(source_item_id)
            if source_item is None:
                return {
                    "kind": "change_source_control",
                    "status": "source_missing",
                }
            if controller_id not in self.players:
                controller_id = self.rules_item_controller_id(source_item)
            previous_controller_id = self.rules_item_controller_id(source_item)
            source_item["controllerId"] = controller_id
            if result.get("counter"):
                counters = source_item.setdefault("counters", {})
                current = int(counters.get(result["counter"]) or 0)
                counters[result["counter"]] = (
                    current + int(result.get("counterValue") or 0)
                    if result.get("incrementCounter")
                    else int(result.get("counterValue") or 0)
                )
            return {
                "kind": "change_source_control",
                "status": "changed",
                "itemId": source_item["id"],
                "cardId": source_item.get("cardId"),
                "ownerId": source_item.get("ownerId"),
                "previousControllerId": previous_controller_id,
                "controllerId": controller_id,
                "counter": result.get("counter"),
                "counterValue": result.get("counterValue"),
            }
        if result.get("kind") == "score_controller_then_destroy_source":
            source_item = self.find_battlefield_item(
                (action.get("source") or {}).get("itemId")
            )
            if source_item is None:
                return {
                    "kind": result.get("kind"),
                    "status": "source_missing",
                }
            controller_id = self.rules_item_controller_id(source_item)
            delta = self.adjust_rules_score(
                controller_id, int(result.get("value") or 0)
            )
            movement = self._rules_remove_field_item_by_effect(
                source_item, source_item.get("ownerId"), "graveyard", "top",
                reason="destroy",
            )
            return {
                "kind": result.get("kind"),
                "status": "resolved",
                "playerId": controller_id,
                "delta": delta,
                "score": self.players[controller_id]["score"],
                "movement": movement,
            }
        if result.get("kind") == "shuffle_hands_then_draw":
            draw_count = int(result.get("value") or 0)
            moved = {}
            drawn = {}
            for current_id, current in self.players.items():
                moved[current_id] = []
                for card_id in list(current["zones"]["hand"]):
                    error, _owner_id, replacement = self.move_zone_card_by_effect(
                        current_id, "hand", current_id, "deck",
                        card_id, "bottom",
                    )
                    if not error and not replacement:
                        moved[current_id].append(card_id)
                random.shuffle(current["zones"]["deck"])
                drawn[current_id] = 0
                for _index in range(min(draw_count, len(current["zones"]["deck"]))):
                    card_id = current["zones"]["deck"][0]
                    error, _owner_id, replacement = self.move_zone_card_by_effect(
                        current_id, "deck", current_id, "hand",
                        card_id, "bottom",
                    )
                    if error:
                        break
                    if not replacement:
                        drawn[current_id] += 1
            return {
                "kind": "shuffle_hands_then_draw",
                "movedCounts": {
                    current_id: len(card_ids)
                    for current_id, card_ids in moved.items()
                },
                "drawn": drawn,
            }
        if result.get("kind") == "exile_all_limbos":
            source = action.get("source") or {}
            excluded_source = (
                source.get("cardId")
                if (action.get("sourceResolution") or {}).get("destination") == "graveyard"
                else None
            )
            excluded_owner = source.get("ownerId")
            exiled = {}
            for current_id, current in self.players.items():
                exiled[current_id] = []
                skipped_source = False
                for card_id in list(current["zones"]["graveyard"]):
                    if (
                        not skipped_source
                        and card_id == excluded_source
                        and current_id == excluded_owner
                    ):
                        skipped_source = True
                        continue
                    error, _owner_id, replacement = self.move_zone_card_by_effect(
                        current_id, "graveyard", current_id, "exile",
                        card_id, "top",
                    )
                    if not error and not replacement:
                        exiled[current_id].append(card_id)
            return {
                "kind": "exile_all_limbos",
                "cardIdsByPlayer": exiled,
            }
        if result.get("kind") == "resolve_top_deck_by_type":
            if not player["zones"]["deck"]:
                return {
                    "kind": "resolve_top_deck_by_type",
                    "status": "deck_empty",
                    "playerId": player_id,
                }
            card_id = player["zones"]["deck"][0]
            card_type = self.card_rules.get(card_id, {}).get("type")
            if (
                card_type == "manifestation"
                and result.get("manifestation") == "chain"
            ):
                error, chained = self.chain_rules_manifestation(
                    player_id, "deck", card_id,
                    action_id=action.get("id"),
                    source_card_id=(action.get("source") or {}).get("cardId"),
                )
                if error:
                    return {
                        "kind": "resolve_top_deck_by_type",
                        "status": "failed",
                        "error": error,
                        "cardId": card_id,
                    }
                return {
                    "kind": "resolve_top_deck_by_type",
                    "status": chained.get("status"),
                    "cardId": card_id,
                    "cardType": card_type,
                    "resolution": chained,
                }
            if card_type in RULES_WILL_TYPES and result.get("will") == "draw":
                drawn = self.draw_rules_cards(player_id, 1)
                return {
                    "kind": "resolve_top_deck_by_type",
                    "status": "drawn" if drawn else "failed",
                    "cardId": card_id,
                    "cardType": card_type,
                }
            return {
                "kind": "resolve_top_deck_by_type",
                "status": "revealed_no_effect",
                "cardId": card_id,
                "cardType": card_type,
            }
        if result.get("kind") == "reorder_top_decks":
            count = int(result.get("count") or 0)
            target_player_ids = (
                list(self.players) if result.get("eachPlayer") else [player_id]
            )
            groups = []
            for target_player_id in target_player_ids:
                card_ids = list(
                    self.players[target_player_id]["zones"]["deck"][:count]
                )
                if card_ids:
                    groups.append({
                        "playerId": target_player_id,
                        "cardIds": card_ids,
                        "topCount": None,
                        "bottomCount": None,
                    })
            if not groups:
                return {
                    "kind": "reorder_top_decks",
                    "status": "no_cards",
                }
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id,
                "kind": "deck_reorder",
                "playerId": player_id,
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "groups": groups,
                "_groups": groups,
                "_afterDraw": int(result.get("afterDraw") or 0),
                "_afterDiscard": int(result.get("afterDiscard") or 0),
            }
            return {
                "kind": "choice_required",
                "choiceId": choice_id,
                "choiceKind": "deck_reorder",
                "playerId": player_id,
            }
        if result.get("kind") == "split_targeted_limbo_cards":
            targets = [
                target for target in action.get("targets") or []
                if target.get("kind") == "zone_card"
                and target.get("zone") == "graveyard"
            ]
            if not targets:
                return {
                    "kind": "split_targeted_limbo_cards",
                    "status": "no_targets",
                }
            container_ids = {target.get("containerId") for target in targets}
            if len(container_ids) != 1:
                return {
                    "kind": "split_targeted_limbo_cards",
                    "status": "mixed_limbos",
                }
            card_ids = [target.get("cardId") for target in targets]
            choice_id = new_id()
            bottom_count = (len(card_ids) + 1) // 2
            groups = [{
                "playerId": next(iter(container_ids)),
                "cardIds": card_ids,
                "topCount": len(card_ids) - bottom_count,
                "bottomCount": bottom_count,
                "fromZone": "graveyard",
            }]
            self.rules_engine["pendingChoice"] = {
                "id": choice_id,
                "kind": "deck_reorder",
                "playerId": player_id,
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "groups": groups,
                "_groups": groups,
            }
            return {
                "kind": "choice_required",
                "choiceId": choice_id,
                "choiceKind": "deck_reorder",
                "playerId": player_id,
            }
        if result.get("kind") == "guess_top_card":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "player"
            ), None)
            target_id = target.get("playerId") if target else None
            if target_id not in self.players:
                return {"kind": "guess_top_card", "status": "target_missing"}
            if not self.players[target_id]["zones"]["deck"]:
                return {"kind": "guess_top_card", "status": "deck_empty"}
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id,
                "kind": "guess_top_card",
                "playerId": player_id,
                "targetPlayerId": target_id,
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "types": ["manifestation", "will"],
                "temperaments": sorted(RULES_TEMPERAMENTS),
                "values": list(range(0, 13)),
                "_cardId": self.players[target_id]["zones"]["deck"][0],
            }
            return {
                "kind": "choice_required",
                "choiceId": choice_id,
                "choiceKind": "guess_top_card",
                "playerId": player_id,
            }
        if result.get("kind") == "create_tokens_for_target_interzone_count":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "player"
            ), None)
            target_id = target.get("playerId") if target else None
            if target_id not in self.players:
                return {
                    "kind": result.get("kind"),
                    "status": "target_missing",
                }
            count = len(self.rules_confrontation_items(
                target_id, ("interzone",)
            ))
            source_item_id = (action.get("source") or {}).get("itemId")
            created = [
                self.create_rules_token_copy(
                    (action.get("source") or {}).get("cardId"),
                    player_id,
                    source_item_id=source_item_id,
                    hollow=True,
                    effects_disabled=True,
                    generic_power=1,
                )
                for _index in range(count)
            ]
            return {
                "kind": result.get("kind"),
                "status": "created",
                "count": len(created),
                "itemIds": [item["id"] for item in created],
                "targetPlayerId": target_id,
            }
        if result.get("kind") == "capture_stalemate_and_copy":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "card"
            ), None)
            item = self.find_battlefield_item(
                target.get("itemId") if target else None
            )
            if item is None:
                return {
                    "kind": result.get("kind"),
                    "status": "target_missing",
                }
            card_id = item.get("cardId")
            movement = self._rules_remove_field_item_by_effect(
                item, player_id, "receptacle", "top"
            )
            copy = self.create_rules_token_copy(
                card_id, player_id,
                source_item_id=(action.get("source") or {}).get("itemId"),
            )
            return {
                "kind": result.get("kind"),
                "status": "resolved",
                "movement": movement,
                "copyItemId": copy["id"],
            }
        if result.get("kind") == "copy_related_tribute_if_exhaust":
            source_item = self.find_battlefield_item(
                (action.get("source") or {}).get("itemId")
            )
            related_card_id = (
                (action.get("ability") or {}).get("trigger") or {}
            ).get("relatedCardId")
            if (
                source_item is None
                or int(round(float(source_item.get("rotation") or 0))) % 180
                or self.card_rules.get(related_card_id, {}).get("type")
                != "manifestation"
            ):
                return {
                    "kind": result.get("kind"),
                    "status": "unavailable",
                }
            if action.get("optionalAccepted"):
                source_item["rotation"] = 90.0
                copy = self.create_rules_token_copy(
                    related_card_id, player_id,
                    source_item_id=source_item.get("id"),
                )
                return {
                    "kind": result.get("kind"),
                    "status": "accepted",
                    "playerId": player_id,
                    "relatedCardId": related_card_id,
                    "createdItemId": copy["id"],
                }
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id,
                "kind": "optional_trigger",
                "playerId": player_id,
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "options": ["accept", "decline"],
                "_effect": "copy_related_tribute_if_exhaust",
                "_sourceItemId": source_item["id"],
                "_relatedCardId": related_card_id,
            }
            return {
                "kind": "choice_required",
                "choiceId": choice_id,
                "choiceKind": "optional_trigger",
                "playerId": player_id,
            }
        if result.get("kind") == "exile_limbos_create_token_copies":
            created = []
            exiled = []
            for current_id, current in self.players.items():
                for card_id in list(current["zones"]["graveyard"]):
                    if self.card_rules.get(card_id, {}).get("type") != "manifestation":
                        continue
                    error, _owner_id, replacement = self.move_zone_card_by_effect(
                        current_id, "graveyard", current_id, "exile",
                        card_id, "top",
                    )
                    if error or replacement:
                        continue
                    exiled.append({"playerId": current_id, "cardId": card_id})
                    created.append(self.create_rules_token_copy(
                        card_id, current_id, hollow=True,
                        effects_disabled=True,
                    ))
            return {
                "kind": result.get("kind"),
                "status": "resolved",
                "exiled": exiled,
                "createdItemIds": [item["id"] for item in created],
            }
        if result.get("kind") == "copy_entering_persistent_will_for_others":
            trigger = (action.get("ability") or {}).get("trigger") or {}
            card_id = trigger.get("relatedCardId")
            event_controller_id = trigger.get("eventControllerId")
            if (
                self.card_rules.get(card_id, {}).get("type") != "persistent_will"
                or event_controller_id not in self.players
            ):
                return {
                    "kind": result.get("kind"),
                    "status": "event_missing",
                }
            created = [
                self.create_rules_token_copy(
                    card_id, current_id,
                    source_item_id=(action.get("source") or {}).get("itemId"),
                )
                for current_id in self.players
                if current_id != event_controller_id
            ]
            return {
                "kind": result.get("kind"),
                "status": "created",
                "createdItemIds": [item["id"] for item in created],
            }
        if result.get("kind") == "schedule_next_turn_hand_limit":
            target_id = (action.get("source") or {}).get("containerId")
            if target_id not in self.players:
                return {
                    "kind": result.get("kind"),
                    "status": "target_missing",
                }
            effect = {
                "id": new_id(),
                "playerId": target_id,
                "turn": self.phase_tracker["turn"] + 1,
                "delta": int(result.get("delta") or 0),
                "overflowDestination": result.get(
                    "overflowDestination", "graveyard"
                ),
                "sourceCardId": (action.get("source") or {}).get("cardId"),
            }
            self.rules_engine["handLimitEffects"].append(effect)
            return {
                "kind": result.get("kind"),
                "status": "scheduled",
                **effect,
            }
        if result.get("kind") == "choose_points_or_hand_limit":
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
        if result.get("kind") == "move_targets":
            movements = []
            for target in action.get("targets") or []:
                nested = {
                    **action,
                    "targets": [target],
                    "ability": {
                        **(action.get("ability") or {}),
                        "result": {
                            "kind": "move_target",
                            "zone": result.get("zone"),
                            "position": result.get("position"),
                            "reason": result.get("reason"),
                        },
                    },
                }
                movement = self.apply_rules_action_result(nested)
                if movement:
                    movements.append(movement)
            return {
                "kind": "move_targets",
                "status": "resolved",
                "movements": movements,
            }
        if result.get("kind") == "optional_discard_then_draw":
            if not player["zones"]["hand"]:
                return {
                    "kind": result.get("kind"),
                    "status": "no_hand_card",
                }
            if action.get("optionalAccepted"):
                choice_id = new_id()
                self.rules_engine["pendingChoice"] = {
                    "id": choice_id,
                    "kind": "discard_from_hand",
                    "playerId": player_id,
                    "count": 1,
                    "drawAfter": int(result.get("draw") or 0),
                    "actionId": action.get("id"),
                    "controllerId": action.get("controllerId"),
                    "sourceCardId": (action.get("source") or {}).get("cardId"),
                }
                return {
                    "kind": "choice_required",
                    "choiceId": choice_id,
                    "choiceKind": "discard_from_hand",
                    "playerId": player_id,
                    "count": 1,
                    "drawAfter": int(result.get("draw") or 0),
                }
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id,
                "kind": "optional_discard_draw",
                "playerId": player_id,
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "draw": int(result.get("draw") or 0),
                "options": ["accept", "decline"],
            }
            return {
                "kind": "choice_required",
                "choiceId": choice_id,
                "choiceKind": "optional_discard_draw",
                "playerId": player_id,
            }
        if result.get("kind") == "roll_d6_power_by_parity":
            roll = random.randint(1, 6)
            value = (
                int(result.get("even") or 0)
                if roll % 2 == 0 else int(result.get("odd") or 0)
            )
            source_item = self.find_battlefield_item(
                (action.get("source") or {}).get("itemId")
            )
            if source_item is None:
                return {
                    "kind": result.get("kind"),
                    "status": "source_missing",
                    "roll": roll,
                }
            effect = {
                "id": new_id(), "actionId": action.get("id"),
                "abilityId": (action.get("ability") or {}).get("id"),
                "controllerId": player_id,
                "source": dict(action.get("source") or {}),
                "target": {
                    "kind": "card", "itemId": source_item["id"],
                    "cardId": source_item.get("cardId"),
                    "ownerId": source_item.get("ownerId"),
                },
                "kind": "power_modifier",
                "duration": "until_end_of_turn",
                "startedTurn": self.phase_tracker["turn"],
                "value": value,
            }
            self.rules_engine["ongoingEffects"].append(effect)
            return {
                "kind": result.get("kind"),
                "status": "resolved",
                "roll": roll, "value": value,
                "effectId": effect["id"],
            }
        if result.get("kind") == "roll_d6_target_table":
            roll = random.randint(1, 6)
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "card"
            ), None)
            item = self.find_battlefield_item(
                target.get("itemId") if target else None
            )
            if item is None:
                return {
                    "kind": result.get("kind"),
                    "status": "target_missing", "roll": roll,
                }
            table = result.get("table")
            if table == "greed":
                value = 0 if roll <= 2 else -1 if roll <= 4 else -2
                if value:
                    effect = {
                        "id": new_id(), "actionId": action.get("id"),
                        "abilityId": (action.get("ability") or {}).get("id"),
                        "controllerId": player_id,
                        "source": dict(action.get("source") or {}),
                        "target": dict(target),
                        "kind": "power_modifier",
                        "duration": "until_end_of_turn",
                        "startedTurn": self.phase_tracker["turn"],
                        "value": value,
                    }
                    self.rules_engine["ongoingEffects"].append(effect)
                return {
                    "kind": result.get("kind"),
                    "status": "resolved", "table": table,
                    "roll": roll, "value": value,
                }
            if roll <= 2:
                nested = {
                    **action,
                    "ability": {
                        **(action.get("ability") or {}),
                        "result": {
                            "kind": "move_target",
                            "zone": "graveyard",
                            "position": "top",
                            "reason": "destroy",
                        },
                    },
                }
                effect_result = self.apply_rules_action_result(nested)
            elif roll == 3:
                item["temperamentOverride"] = "hollow"
                effect_result = {"status": "temperament", "temperament": "hollow"}
            else:
                value = 2 if roll <= 5 else 3
                effect = {
                    "id": new_id(), "actionId": action.get("id"),
                    "abilityId": (action.get("ability") or {}).get("id"),
                    "controllerId": player_id,
                    "source": dict(action.get("source") or {}),
                    "target": dict(target),
                    "kind": "power_modifier",
                    "duration": "until_end_of_turn",
                    "startedTurn": self.phase_tracker["turn"],
                    "value": value,
                }
                self.rules_engine["ongoingEffects"].append(effect)
                effect_result = {"status": "power", "value": value}
            return {
                "kind": result.get("kind"),
                "status": "resolved", "table": table,
                "roll": roll, "outcome": effect_result,
            }
        if result.get("kind") == "roll_d6_conditional_source":
            roll = random.randint(1, 6)
            source_item = self.find_battlefield_item(
                (action.get("source") or {}).get("itemId")
            )
            if source_item is None:
                return {
                    "kind": result.get("kind"),
                    "status": "source_missing", "roll": roll,
                }
            source_item.setdefault("counters", {})["Roll"] = roll
            if roll % 2 == 0:
                draw = self.request_rules_draw(player_id, 1, player_id)
                return {
                    "kind": result.get("kind"),
                    "status": "draw", "roll": roll,
                    "draw": draw,
                }
            candidates = [
                item["id"] for item in self.battlefield
                if item is not source_item
                and item.get("faceUp")
                and self.rules_item_controller_id(item) == player_id
            ]
            if not candidates:
                return {
                    "kind": result.get("kind"),
                    "status": "no_target", "roll": roll,
                }
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id,
                "kind": "random_target_effect",
                "playerId": player_id,
                "sourceCardId": source_item.get("cardId"),
                "sourceItemId": source_item.get("id"),
                "candidateItemIds": candidates,
                "roll": roll,
                "effectKind": "lose_effects",
            }
            return {
                "kind": "choice_required",
                "choiceId": choice_id,
                "choiceKind": "random_target_effect",
                "playerId": player_id,
                "roll": roll,
            }
        if result.get("kind") == "roll_multiple_even_power_odd_discard":
            rolls = [
                random.randint(1, 6)
                for _index in range(int(result.get("rolls") or 0))
            ]
            even_count = sum(roll % 2 == 0 for roll in rolls)
            odd_count = len(rolls) - even_count
            source_item = self.find_battlefield_item(
                (action.get("source") or {}).get("itemId")
            )
            if source_item is not None and even_count:
                source_item.setdefault("counters", {})["power"] = int(
                    source_item.get("counters", {}).get("power") or 0
                ) + even_count
            discard_count = min(
                odd_count, len(self.players[player_id]["zones"]["hand"])
            )
            choice_id = None
            if discard_count:
                choice_id = new_id()
                self.rules_engine["pendingChoice"] = {
                    "id": choice_id,
                    "kind": "discard_from_hand",
                    "playerId": player_id,
                    "count": discard_count,
                    "sourceCardId": (action.get("source") or {}).get("cardId"),
                }
            return {
                "kind": result.get("kind"),
                "status": "resolved",
                "rolls": rolls,
                "evenCount": even_count,
                "oddCount": odd_count,
                "discardChoiceId": choice_id,
            }
        if result.get("kind") == "score_controller_by_source_roll_then_exile":
            source_item = self.find_battlefield_item(
                (action.get("source") or {}).get("itemId")
            )
            if source_item is None:
                return {
                    "kind": result.get("kind"),
                    "status": "source_missing",
                }
            roll = int((source_item.get("counters") or {}).get("Roll") or 0)
            loss = 5 if roll <= 2 else 10 if roll <= 4 else 15
            controller_id = self.rules_item_controller_id(source_item)
            delta = self.adjust_rules_score(controller_id, -loss)
            movement = self._rules_remove_field_item_by_effect(
                source_item, source_item.get("ownerId"), "exile", "top"
            )
            return {
                "kind": result.get("kind"),
                "status": "resolved", "roll": roll,
                "playerId": controller_id, "delta": delta,
                "score": self.players[controller_id]["score"],
                "movement": movement,
            }
        if result.get("kind") == "force_win_if_highest_base_first":
            source_item = self.find_battlefield_item(
                (action.get("source") or {}).get("itemId")
            )
            if source_item is None:
                return {
                    "kind": result.get("kind"),
                    "status": "source_missing",
                }
            controller_id = self.rules_item_controller_id(source_item)
            first_ids = self.rules_engine.get("firstManifestationItemIds", {})
            first_items = [
                self.find_battlefield_item(item_id)
                for item_id in first_ids.values()
            ]
            first_items = [item for item in first_items if item]
            source_power = int(self.card_rules.get(
                source_item.get("cardId"), {}
            ).get("power") or 0)
            highest = max((
                int(self.card_rules.get(item.get("cardId"), {}).get("power") or 0)
                for item in first_items
            ), default=source_power)
            qualifies = (
                first_ids.get(controller_id) == source_item.get("id")
                and source_power >= highest
            )
            if qualifies:
                self.rules_engine["forcedConfrontationWinnerId"] = controller_id
            return {
                "kind": result.get("kind"),
                "status": "forced" if qualifies else "condition_failed",
                "playerId": controller_id,
                "basePower": source_power,
                "highestBasePower": highest,
            }
        if result.get("kind") == "skip_confrontation_unless_points":
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
            own_power = int(self.card_rules.get(
                (own_first or {}).get("cardId"), {}
            ).get("power") or 0)
            opponent_power = int(self.card_rules.get(
                (opponent_first or {}).get("cardId"), {}
            ).get("power") or 0)
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
        if result.get("kind") == "end_confrontation_relocate_all":
            source_item = self.find_battlefield_item(
                (action.get("source") or {}).get("itemId")
            )
            if source_item is None:
                return {
                    "kind": result.get("kind"),
                    "status": "source_missing",
                }
            source_movement = self._rules_remove_field_item_by_effect(
                source_item, source_item.get("ownerId"), "exile", "top"
            )
            groups = []
            for owner_id in self.players:
                item_ids = [
                    item["id"] for item in self.rules_confrontation_items()
                    if item.get("ownerId") == owner_id
                ]
                if not item_ids:
                    continue
                groups.append({
                    "playerId": owner_id,
                    "itemIds": item_ids,
                    "interzoneSlots": max(
                        0, 3 - self.rules_interzone_slot_count(owner_id)
                    ),
                })
            if not groups:
                self.phase_tracker["index"] = ADVANCED_PHASES.index(
                    "end_actions"
                )
                opponent_id = self.other_rules_player_id(player_id)
                if opponent_id:
                    self.adjust_rules_score(opponent_id, 50)
                return {
                    "kind": result.get("kind"),
                    "status": "ended",
                    "sourceMovement": source_movement,
                }
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id,
                "kind": "confrontation_relocation",
                "playerId": player_id,
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "groups": groups,
                "_groups": groups,
                "_sourceMovement": source_movement,
            }
            return {
                "kind": "choice_required",
                "choiceId": choice_id,
                "choiceKind": "confrontation_relocation",
                "playerId": player_id,
            }
        if result.get("kind") == "suspend_opponent_hand_will":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "player"
            ), None)
            target_id = target.get("playerId") if target else None
            if target_id not in self.players:
                return {
                    "kind": result.get("kind"),
                    "status": "target_missing",
                }
            eligible = [
                card_id for card_id in self.players[target_id]["zones"]["hand"]
                if self.card_rules.get(card_id, {}).get("type")
                in RULES_WILL_TYPES
            ]
            if not eligible:
                return {
                    "kind": result.get("kind"),
                    "status": "no_eligible_card",
                    "handProof": list(
                        self.players[target_id]["zones"]["hand"]
                    ),
                    "handProofPlayerId": target_id,
                }
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id,
                "kind": "suspend_hand_will",
                "playerId": target_id,
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "sourceItemId": (action.get("source") or {}).get("itemId"),
                "playableByPlayerId": player_id,
                "cardIds": eligible,
                "_cardIds": eligible,
            }
            return {
                "kind": "choice_required",
                "choiceId": choice_id,
                "choiceKind": "suspend_hand_will",
                "playerId": target_id,
            }
        if result.get("kind") == "end_confrontation_unless_payment":
            opponent_id = self.other_rules_player_id(player_id)
            choice_id = new_id()
            controller_base_power = sum(
                self.rules_manifestation_base_power(item)
                for item in self.rules_confrontation_items(player_id)
            )
            self.rules_engine["pendingChoice"] = {
                "id": choice_id,
                "kind": "immediate_effect_payment",
                "playerId": opponent_id,
                "payment": result.get("payment"),
                "requirements": self.rules_requirements_from_symbols(
                    result.get("payment")
                ),
                "actionId": action.get("id"),
                "controllerId": player_id,
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "exileOnDecline": bool(result.get("exileOnDecline")),
                "reduceWinnerManifestationOnControllerDefeat": bool(
                    result.get(
                        "reduceWinnerManifestationOnControllerDefeat"
                    )
                ),
                "controllerBasePower": controller_base_power,
            }
            return {
                "kind": "choice_required",
                "choiceId": choice_id,
                "choiceKind": "immediate_effect_payment",
                "playerId": opponent_id,
                "payment": result.get("payment"),
            }
        if result.get("kind") == "exchange_control_targets":
            card_targets = [
                target for target in action.get("targets") or []
                if target.get("kind") == "card"
            ]
            if len(card_targets) != 2:
                return {
                    "kind": "exchange_control_targets",
                    "status": "target_missing",
                }
            first = self.find_battlefield_item(card_targets[0].get("itemId"))
            second = self.find_battlefield_item(card_targets[1].get("itemId"))
            if first is None or second is None:
                return {
                    "kind": "exchange_control_targets",
                    "status": "target_missing",
                }
            first_controller = self.rules_item_controller_id(first)
            second_controller = self.rules_item_controller_id(second)
            first["controllerId"] = second_controller
            second["controllerId"] = first_controller
            memory_ids = []
            if result.get("rememberAtResolution"):
                for item in (first, second):
                    memory = self.create_rules_effect_memory(
                        item.get("ownerId"), item.get("cardId"),
                        "move_to_deck_at_resolution",
                        controller_id=player_id,
                        source_action_id=action.get("id"),
                        data={"itemId": item.get("id")},
                    )
                    if memory:
                        memory_ids.append(memory["id"])
            return {
                "kind": "exchange_control_targets",
                "status": "exchanged",
                "itemIds": [first["id"], second["id"]],
                "controllerIds": [
                    self.rules_item_controller_id(first),
                    self.rules_item_controller_id(second),
                ],
                "memoryIds": memory_ids,
            }
        if result.get("kind") == "retarget_source_effect":
            source_item_id = (action.get("source") or {}).get("itemId")
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "card"
            ), None)
            target_item = self.find_battlefield_item(
                target.get("itemId") if target else None
            )
            effect = next((
                entry for entry in reversed(
                    self.rules_engine.get("ongoingEffects") or []
                )
                if entry.get("source", {}).get("itemId") == source_item_id
                and entry.get("kind") == result.get("effectKind")
            ), None)
            if effect is None or target_item is None:
                return {
                    "kind": "retarget_source_effect",
                    "status": "target_missing",
                }
            previous_item_id = effect.get("target", {}).get("itemId")
            effect["target"] = {
                "kind": "card",
                "itemId": target_item.get("id"),
                "cardId": target_item.get("cardId"),
                "ownerId": target_item.get("ownerId"),
            }
            return {
                "kind": "retarget_source_effect",
                "status": "retargeted",
                "effectId": effect.get("id"),
                "previousItemId": previous_item_id,
                "itemId": target_item.get("id"),
            }
        if result.get("kind") == "resolve_effect_memory":
            memory = next((
                entry for entry in self.rules_engine.get("effectMemories") or []
                if entry.get("id") == result.get("memoryId")
            ), None)
            if memory is None:
                return {
                    "kind": "resolve_effect_memory",
                    "status": "memory_missing",
                }
            owner_id = memory.get("ownerId")
            card_id = memory.get("cardId")
            if memory.get("kind") == "move_to_deck_at_resolution":
                item = self.find_battlefield_item(
                    (memory.get("data") or {}).get("itemId")
                )
                if item is None:
                    self.remove_rules_effect_memory(memory["id"])
                    return {
                        "kind": "resolve_effect_memory",
                        "status": "card_not_on_field",
                        "memoryId": memory["id"],
                        "cardId": card_id,
                    }
                movement = self._rules_remove_field_item_by_effect(
                    item, owner_id, "deck", "bottom"
                )
                self.remove_rules_effect_memory(memory["id"])
                return {
                    "kind": "resolve_effect_memory",
                    "status": movement.get("status"),
                    "memoryId": memory["id"],
                    "cardId": card_id,
                    "movement": movement,
                }
            if card_id not in self.players.get(owner_id, {}).get("zones", {}).get("graveyard", []):
                self.remove_rules_effect_memory(memory["id"])
                return {
                    "kind": "resolve_effect_memory",
                    "status": "card_not_in_limbo",
                    "memoryId": memory["id"],
                    "cardId": card_id,
                }
            data = memory.get("data") or {}
            if data.get("requireLostConfrontation"):
                outcome = self.rules_engine.get("confrontationResult") or {}
                if (
                    outcome.get("turn") != self.phase_tracker["turn"]
                    or outcome.get("loserId") != memory.get("controllerId")
                ):
                    self.remove_rules_effect_memory(memory["id"])
                    return {
                        "kind": "resolve_effect_memory",
                        "status": "condition_failed",
                        "memoryId": memory["id"], "cardId": card_id,
                    }
            if data.get("rollReturnOrExile"):
                roll = random.randint(1, 6)
                destination = "hand" if roll % 2 == 0 else "exile"
                error, _owner_id, replacement = self.move_zone_card_by_effect(
                    owner_id, "graveyard", owner_id, destination, card_id, "top"
                )
                self.remove_rules_effect_memory(memory["id"])
                return {
                    "kind": "resolve_effect_memory",
                    "status": "target_missing" if error else "suspended" if replacement else (
                        "returned" if destination == "hand" else "exiled"
                    ),
                    "memoryId": memory["id"], "cardId": card_id, "roll": roll,
                }
            opponent_payment = data.get("opponentPayment")
            if opponent_payment:
                opponent_id = self.other_rules_player_id(memory.get("controllerId"))
                choice_id = new_id()
                self.rules_engine["pendingChoice"] = {
                    "id": choice_id,
                    "kind": "effect_memory_payment",
                    "playerId": opponent_id,
                    "payment": opponent_payment,
                    "requirements": self.rules_requirements_from_symbols(opponent_payment),
                    "memoryId": memory["id"],
                    "sourceCardId": card_id,
                    "targetCardId": card_id,
                }
                return {
                    "kind": "choice_required",
                    "choiceId": choice_id,
                    "choiceKind": "effect_memory_payment",
                    "playerId": opponent_id,
                    "payment": opponent_payment,
                    "memoryId": memory["id"],
                    "cardId": card_id,
                }
            if data.get("optional") and not action.get("optionalAccepted"):
                choice_id = new_id()
                self.rules_engine["pendingChoice"] = {
                    "id": choice_id,
                    "kind": "effect_memory_return",
                    "playerId": owner_id,
                    "memoryId": memory["id"],
                    "sourceCardId": card_id,
                    "options": ["return", "decline"],
                }
                return {
                    "kind": "choice_required",
                    "choiceId": choice_id,
                    "choiceKind": "effect_memory_return",
                    "playerId": owner_id,
                    "memoryId": memory["id"],
                    "cardId": card_id,
                }
            error, _owner_id, replacement = self.move_zone_card_by_effect(
                owner_id, "graveyard", owner_id, "hand", card_id, "top"
            )
            self.remove_rules_effect_memory(memory["id"])
            return {
                "kind": "resolve_effect_memory",
                "status": (
                    "target_missing" if error
                    else "suspended" if replacement
                    else "returned"
                ),
                "memoryId": memory["id"],
                "cardId": card_id,
                "playerId": owner_id,
            }
        if result.get("kind") == "neutralize_stack_action":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "stack_action"
            ), None)
            target_action = next((
                entry for entry in self.rules_engine.get("actionStack") or []
                if target and entry.get("id") == target.get("actionId")
            ), None)
            if target_action is None:
                return {
                    "kind": "neutralize_stack_action", "status": "target_missing",
                    "actionId": target.get("actionId") if target else None,
                    "cardId": target.get("cardId") if target else None,
                }
            countered = self.counter_rules_stack_action(
                target_action, "neutralize",
                result.get("destination") or "graveyard",
            )
            if result.get("refundEssence"):
                refunded = self.rules_refund_stack_action_essence(target_action)
                if refunded:
                    countered["refundedEssence"] = refunded
            return {
                "kind": "neutralize_stack_action",
                **countered,
            }
        if result.get("kind") == "counter_stack_action_unless_payment":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") in {"stack_action", "stack_effect"}
            ), None)
            target_action = next((
                entry for entry in self.rules_engine.get("actionStack") or []
                if target and entry.get("id") == target.get("actionId")
            ), None)
            if target_action is None:
                return {
                    "kind": "counter_stack_action_unless_payment", "status": "target_missing",
                    "actionId": target.get("actionId") if target else None,
                    "cardId": target.get("cardId") if target else None,
                    "mode": result.get("mode"),
                }
            payer_id = (
                (target_action.get("source") or {}).get("ownerId")
                if result.get("payer") == "owner"
                else target_action.get("controllerId")
            )
            if payer_id not in self.players:
                payer_id = target_action.get("controllerId")
            choice_id = new_id()
            requirements = self.rules_requirements_from_symbols(result.get("payment"))
            self.rules_engine["pendingChoice"] = {
                "id": choice_id,
                "kind": "stack_counter_payment",
                "playerId": payer_id,
                "payment": result.get("payment"),
                "requirements": requirements,
                "mode": result.get("mode"),
                "actionId": action.get("id"),
                "controllerId": action.get("controllerId"),
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "targetActionId": target_action.get("id"),
                "targetCardId": (target_action.get("source") or {}).get("cardId"),
                "targetControllerId": target_action.get("controllerId"),
                "targetKind": target.get("kind"),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "stack_counter_payment", "playerId": payer_id,
                "payment": result.get("payment"), "requirements": requirements,
                "mode": result.get("mode"),
                "targetActionId": target_action.get("id"),
                "targetCardId": (target_action.get("source") or {}).get("cardId"),
                "targetKind": target.get("kind"),
            }
        if result.get("kind") == "copy_stack_action":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "stack_action"
            ), None)
            target_action = next((
                entry for entry in self.rules_engine.get("actionStack") or []
                if target and entry.get("id") == target.get("actionId")
            ), None)
            if not self.rules_stack_target_matches(target_action, "stack_action"):
                return {
                    "kind": "copy_stack_action", "status": "target_missing",
                    "actionId": target.get("actionId") if target else None,
                    "cardId": target.get("cardId") if target else None,
                }
            target_rules = self.rules_action_target_rules(target_action)
            copied_action = self.build_rules_stack_copy(target_action, player_id, action.get("id"))
            if target_rules and int(target_rules.get("max") or 0) > 0:
                choice_id = new_id()
                original_targets = [dict(entry) for entry in target_action.get("targets") or []]
                self.rules_engine["pendingChoice"] = {
                    "id": choice_id,
                    "kind": "stack_copy_targets",
                    "playerId": player_id,
                    "sourceCardId": (action.get("source") or {}).get("cardId"),
                    "targetActionId": target_action.get("id"),
                    "targetCardId": (target_action.get("source") or {}).get("cardId"),
                    "targetRules": target_rules,
                    "originalTargets": original_targets,
                    "_copyAction": copied_action,
                }
                return {
                    "kind": "choice_required", "choiceId": choice_id,
                    "choiceKind": "stack_copy_targets", "playerId": player_id,
                    "targetActionId": target_action.get("id"),
                    "targetCardId": (target_action.get("source") or {}).get("cardId"),
                }
            self.rules_engine["actionStack"].append(copied_action)
            return {
                "kind": "copy_stack_action", "status": "copied",
                "actionId": copied_action["id"],
                "copiedFromActionId": target_action.get("id"),
                "cardId": (target_action.get("source") or {}).get("cardId"),
                "targets": [dict(entry) for entry in copied_action.get("targets") or []],
            }
        if result.get("kind") == "each_player_recovery_choice":
            player_ids = [
                entry["id"] for entry in sorted(
                    self.players.values(), key=lambda entry: entry.get("seat", 0)
                )
            ]
            choice = self._set_next_rules_recovery_choice(player_ids, action)
            if choice is None:
                return None
            return {
                "kind": "choice_required",
                "choiceId": choice["id"],
                "choiceKind": choice["kind"],
                "playerId": choice["playerId"],
                "options": list(choice["options"]),
            }
        if result.get("kind") == "create_support_tokens":
            source_item = self.find_battlefield_item(
                (action.get("source") or {}).get("itemId")
            )
            created = [
                self.create_rules_token_copy(
                    None, player_id,
                    source_item_id=(source_item or {}).get("id"),
                    generic_power=result.get("power"),
                    generic_temperament=result.get("temperament"),
                    field_zone=result.get("fieldZone"),
                )
                for _index in range(int(result.get("count") or 1))
            ]
            return {
                "kind": "create_support_tokens",
                "status": "created",
                "count": len(created),
                "itemIds": [item["id"] for item in created],
            }
        if result.get("kind") == "discard_hand_each_opponent":
            if int(result.get("drawOwner") or 0):
                self.request_rules_draw(
                    player_id, int(result["drawOwner"]),
                    source_controller_id=action.get("controllerId"),
                )
            return self.apply_rules_action_result({
                **action,
                "targets": [{
                    "kind": "player",
                    "playerId": self.other_rules_player_id(player_id),
                }],
                "ability": {
                    **(action.get("ability") or {}),
                    "result": {
                        "kind": "discard_hand_target",
                        "value": result.get("value"),
                    },
                },
            })
        if result.get("kind") == "destroy_matching_on_field":
            turn = self.phase_tracker["turn"]
            if result.get("match") == "entered_support_this_turn":
                matched_ids = {
                    entry.get("itemId")
                    for entry in self.rules_engine.get("supportEntries") or []
                    if int(entry.get("turn") or 0) == turn
                }
            else:
                outcome = self.rules_engine.get("confrontationResult") or {}
                winner_id = (
                    outcome.get("winnerId")
                    if outcome.get("turn") == turn else None
                )
                matched_ids = {
                    item_id for item_id in outcome.get("participantItemIds") or []
                    if winner_id is not None
                    and self.rules_item_controller_id(
                        self.find_battlefield_item(item_id)
                    ) == winner_id
                }
            destroyed = []
            for item in list(self.battlefield):
                if item.get("id") not in matched_ids or not item.get("faceUp"):
                    continue
                if (
                    self.card_rules.get(item.get("cardId"), {}).get("type")
                    != "manifestation"
                    and not item.get("isTokenCard")
                ):
                    continue
                movement = self._rules_remove_field_item_by_effect(
                    item, item.get("ownerId"), "graveyard", "top",
                    reason="destroy",
                )
                if movement.get("status") in {"moved", "removed_copy", "suspended"}:
                    destroyed.append(movement)
            return {
                "kind": "destroy_matching_on_field",
                "match": result.get("match"),
                "destroyed": destroyed,
            }
        if result.get("kind") == "move_random_zone_card":
            target = next(
                (entry for entry in action.get("targets") or [] if entry.get("kind") == "player"),
                None,
            )
            container_id = target.get("playerId") if target else None
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
                    else "suspended" if replacement
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
        if result.get("kind") == "move_target":
            target = next(
                (entry for entry in action.get("targets") or [] if entry.get("kind") in {"card", "zone_card"}),
                None,
            )
            destination = result.get("zone")
            position = result.get("position")
            reason = result.get("reason")
            def movement(payload):
                if reason:
                    payload["reason"] = reason
                return payload
            if target and target.get("kind") == "zone_card":
                container_id = target.get("containerId")
                from_zone = target.get("zone")
                card_id = target.get("cardId")
                owner_id = self.card_owner_in_zone(container_id, from_zone, card_id)
                if (
                    owner_id is None
                    or card_id not in self.players.get(container_id, {}).get("zones", {}).get(from_zone, [])
                ):
                    return movement({
                        "kind": "move_card", "status": "target_missing",
                        "cardId": card_id, "fromZone": from_zone,
                        "fromContainerId": container_id, "toZone": destination,
                        "position": position,
                    })
                error, _owner_id, replacement = self.move_zone_card_by_effect(
                    container_id, from_zone, owner_id, destination, card_id, position,
                )
                if error:
                    return movement({
                        "kind": "move_card", "status": "target_missing",
                        "cardId": card_id, "fromZone": from_zone,
                        "fromContainerId": container_id, "toZone": destination,
                        "position": position,
                    })
                payload = {
                    "kind": "move_card",
                    "status": "suspended" if replacement else "moved",
                    "cardId": card_id,
                    "ownerId": owner_id, "fromZone": from_zone,
                    "fromContainerId": container_id, "toZone": destination,
                    "position": position,
                }
                if replacement:
                    payload["replacement"] = replacement
                return movement(payload)
            item = self.find_battlefield_item(target.get("itemId")) if target else None
            if item is None:
                return movement({
                    "kind": "move_card", "status": "target_missing",
                    "cardId": target.get("cardId") if target else None,
                    "itemId": target.get("itemId") if target else None,
                    "toZone": result.get("zone"), "position": result.get("position"),
                })
            item_controller = item.get("controllerId") or item.get("ownerId")
            if self.rules_item_zone_locked(item):
                return movement({
                    "kind": "move_card", "status": "prevented_zone_lock",
                    "cardId": item.get("cardId"), "itemId": item.get("id"),
                    "ownerId": item.get("ownerId"), "fromZone": "battlefield",
                    "toZone": destination, "position": position,
                })
            if (
                self.rules_item_card_rules(item).get("adamant")
                and self.rules_item_effects_active(item)
                and item_controller != player_id
                and reason != "destroy"
            ):
                return movement({
                    "kind": "move_card", "status": "prevented_adamant",
                    "cardId": item.get("cardId"), "itemId": item.get("id"),
                    "ownerId": item.get("ownerId"), "fromZone": "battlefield",
                    "toZone": destination, "position": position,
                })
            movement_result = self._rules_remove_field_item_by_effect(
                item, item.get("ownerId"), destination, position,
                reason=result.get("reason"),
            )
            status = movement_result.get("status")
            if status == "moved":
                if destination == "hand" and result.get("restrictPlayUntilEndOfTurn"):
                    self.rules_engine["playRestrictions"].append({
                        "id": new_id(), "playerId": item["ownerId"],
                        "cardId": item["cardId"], "turn": self.phase_tracker["turn"],
                        "sourceActionId": action.get("id"),
                    })
            self.prune_rules_ongoing_effects()
            payload = {
                "kind": "move_card", "status": status,
                "cardId": item.get("cardId"), "itemId": item.get("id"),
                "ownerId": item.get("ownerId"), "fromZone": "battlefield",
                "toZone": destination, "position": position,
            }
            if status == "suspended":
                payload["replacement"] = movement_result
            if status == "moved" and destination == "hand" and result.get("restrictPlayUntilEndOfTurn"):
                payload["playRestrictedUntilTurnEnd"] = True
            return movement(payload)
        if result.get("kind") == "score_owner":
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
        if result.get("kind") == "draw_owner":
            requested = max(0, min(int(result.get("value") or 0), 50))
            return self.request_rules_draw(
                player_id, requested,
                source_controller_id=action.get("controllerId"),
            )
        if result.get("kind") == "discard_deck_owner":
            requested = max(0, min(int(result.get("value") or 0), 50))
            discarded = []
            for _index in range(min(requested, len(player["zones"]["deck"]))):
                card_id = player["zones"]["deck"][0]
                error, _owner_id, replacement = self.move_zone_card_by_effect(
                    player_id, "deck", player_id, "graveyard", card_id, "top"
                )
                if error:
                    break
                if not replacement:
                    discarded.append(card_id)
            return {
                "kind": "discard_deck",
                "playerId": player_id,
                "count": len(discarded),
                "cardIds": discarded,
            }
        if result.get("kind") == "discard_hand_target":
            target = next(
                (entry for entry in action.get("targets") or [] if entry.get("kind") == "player"),
                None,
            )
            target_id = target.get("playerId") if target else None
            target_player = self.players.get(target_id)
            if target_player is None:
                return None
            if self.rules_hand_is_immune(target_id, player_id):
                return {
                    "kind": "discard",
                    "status": "prevented_immunity",
                    "playerId": target_id,
                    "count": 0,
                    "cardIds": [],
                }
            requested = max(0, min(int(result.get("value") or 0), 7))
            target_hand = target_player["zones"]["hand"]
            count = min(requested, len(target_hand))
            hand_proof = list(target_hand) if len(target_hand) < requested else None
            if count == 0:
                payload = {
                    "kind": "discard", "playerId": target_id,
                    "count": 0, "cardIds": [],
                }
                if hand_proof is not None:
                    payload["handProof"] = hand_proof
                    payload["handProofPlayerId"] = target_id
                return payload
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id,
                "kind": "discard_from_hand",
                "playerId": target_id,
                "count": count,
                "actionId": action.get("id"),
                "controllerId": action.get("controllerId"),
                "sourceCardId": (action.get("source") or {}).get("cardId"),
            }
            payload = {
                "kind": "choice_required",
                "choiceId": choice_id,
                "choiceKind": "discard_from_hand",
                "playerId": target_id,
                "count": count,
            }
            if hand_proof is not None:
                payload["handProof"] = hand_proof
                payload["handProofPlayerId"] = target_id
            return payload
        if result.get("kind") == "discard_hand_owner_then_draw":
            if self.rules_hand_is_immune(player_id, action.get("controllerId")):
                return {
                    "kind": "discard_then_draw",
                    "status": "prevented_immunity",
                    "playerId": player_id,
                    "count": 0,
                    "cardIds": [],
                    "drawCount": 0,
                }
            requested = max(0, min(int(result.get("discard") or 0), 7))
            owner_hand = player["zones"]["hand"]
            count = min(requested, len(owner_hand))
            hand_proof = list(owner_hand) if len(owner_hand) < requested else None
            if count == 0:
                payload = {
                    "kind": "discard_then_draw", "status": "not_paid",
                    "playerId": player_id, "count": 0, "cardIds": [], "drawCount": 0,
                }
                if hand_proof is not None:
                    payload["handProof"] = hand_proof
                    payload["handProofPlayerId"] = player_id
                return payload
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id,
                "kind": "discard_from_hand",
                "playerId": player_id,
                "count": count,
                "drawAfter": max(0, min(int(result.get("draw") or 0), 50)),
                "actionId": action.get("id"),
                "controllerId": action.get("controllerId"),
                "sourceCardId": (action.get("source") or {}).get("cardId"),
            }
            payload = {
                "kind": "choice_required",
                "choiceId": choice_id,
                "choiceKind": "discard_from_hand",
                "playerId": player_id,
                "count": count,
                "drawAfter": self.rules_engine["pendingChoice"]["drawAfter"],
            }
            if hand_proof is not None:
                payload["handProof"] = hand_proof
                payload["handProofPlayerId"] = player_id
            return payload
        if result.get("kind") == "chain_from_zone":
            if int(result.get("scoreCost") or 0) < 0:
                self.adjust_rules_score(player_id, int(result["scoreCost"]))
            if result.get("players") == "each_opponent":
                chain_players = [pid for pid in self.players if pid != player_id]
            elif result.get("players") == "all":
                chain_players = [player_id] + [
                    pid for pid in self.players if pid != player_id
                ]
            else:
                chain_players = [player_id]
            return self.begin_rules_chain_sequence(
                player_id, chain_players, result, action
            )
        if result.get("kind") == "move_source_to_owner_hand":
            source_item = self.find_battlefield_item(
                (action.get("source") or {}).get("itemId")
            )
            if source_item is None:
                return {"kind": result.get("kind"), "status": "source_missing"}
            movement = self._rules_remove_field_item_by_effect(
                source_item, source_item.get("ownerId"), "hand", "top",
                reason="return",
            )
            return {
                "kind": "move_card",
                "status": movement.get("status"),
                "cardId": source_item.get("cardId"),
                "itemId": source_item.get("id"),
                "toZone": "hand",
                "reason": "return",
            }
        return None

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
            eligible = [
                card_id for card_id in member["zones"].get(zone, [])
                if self.card_rules.get(card_id, {}).get("type") == "manifestation"
                and self.rules_card_play_restriction_error(
                    chain_player_id, card_id
                ) is None
            ]
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

    def make_rules_chain_choice(self, chain_player_id, controller_id, result,
                                action, next_players=()):
        zone = result.get("zone")
        eligible = [
            card_id for card_id in self.players[chain_player_id]["zones"].get(zone, [])
            if self.card_rules.get(card_id, {}).get("type") == "manifestation"
            and self.rules_card_play_restriction_error(
                chain_player_id, card_id
            ) is None
        ]
        choice = {
            "id": new_id(),
            "kind": "chain_manifestation",
            "playerId": chain_player_id,
            "fromZone": zone,
            "optional": bool(
                result.get("optional")
                and not action.get("optionalAccepted")
                and chain_player_id == controller_id
            ),
            "winDestination": result.get("winDestination"),
            "shuffleAfter": bool(result.get("shuffleAfter")),
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

    def resolve_rules_choice(self, player_id, choice_id, card_ids=None, option=None, item_id=None,
                             placement=None, targets=None):
        choice = self.rules_engine.get("pendingChoice")
        if not choice or choice.get("id") != choice_id or choice.get("playerId") != player_id:
            return "This card choice is no longer available.", None

        if choice.get("kind") == "optional_stack_action":
            if option not in choice.get("options", []):
                return "Choose whether to put this optional effect on the Stack.", None
            action = choice.get("_action")
            if not isinstance(action, dict):
                self.rules_engine["pendingChoice"] = None
                return "This optional triggered effect is no longer available.", None
            accepted_actions = list(choice.get("_acceptedActions") or [])
            self.rules_engine["pendingChoice"] = None
            if option == "accept":
                action["optionalAccepted"] = True
                target_choice = action.pop("_preStackTargetChoice", None)
                if target_choice:
                    self.rules_engine["pendingChoice"] = {
                        "id": new_id(),
                        "kind": "trigger_targets",
                        "playerId": player_id,
                        "sourceCardId": (
                            action.get("source") or {}
                        ).get("cardId"),
                        "targetRules": target_choice.get("targetRules") or {},
                        "_triggerAction": action,
                        "_resumeConfrontationCleanup": bool(
                            target_choice.get("resumeConfrontationCleanup")
                        ),
                        "_optionalStackBatch": {
                            "actions": choice.get("_actions") or [],
                            "nextIndex": int(choice.get("_nextIndex") or 0),
                            "acceptedActions": accepted_actions,
                            "priorityPlayerId": choice.get(
                                "_priorityPlayerId"
                            ),
                        },
                    }
                    self.rules_engine["priorityPasses"] = []
                    self.rules_engine["priorityPlayerId"] = player_id
                    return None, {
                        "kind": "optional_stack_action",
                        "status": "accepted",
                        "playerId": player_id,
                        "sourceCardId": choice.get("sourceCardId"),
                        "actionId": action.get("id"),
                        "nextChoiceId": self.rules_engine[
                            "pendingChoice"
                        ]["id"],
                    }
                accepted_actions.append(action)
            self._continue_rules_optional_stack_choices(
                choice.get("_actions") or [],
                int(choice.get("_nextIndex") or 0),
                accepted_actions,
                choice.get("_priorityPlayerId"),
            )
            return None, {
                "kind": "optional_stack_action",
                "status": "accepted" if option == "accept" else "declined",
                "playerId": player_id,
                "sourceCardId": choice.get("sourceCardId"),
                "actionId": action.get("id"),
            }

        if choice.get("kind") == "support_return_order":
            expected_ids = [
                item.get("itemId") for item in choice.get("items") or []
            ]
            supplied_ids = [str(item_id or "") for item_id in (card_ids or [])]
            if (
                len(supplied_ids) != len(expected_ids)
                or len(set(supplied_ids)) != len(supplied_ids)
                or set(supplied_ids) != set(expected_ids)
            ):
                return "Order every Support Manifestation exactly once.", None
            counts = dict(choice.get("_counts") or {})
            moved = []
            for item_id in reversed(supplied_ids):
                item = self.find_battlefield_item(item_id)
                if item is None or not item.get("isSupport"):
                    continue
                controller_id = self.rules_item_controller_id(item)
                movement = self._rules_remove_field_item(
                    item, item.get("ownerId"), "deck", "top"
                )
                moved.append(movement)
                counts[controller_id] = counts.get(controller_id, 0) + 1
            self.rules_engine["pendingChoice"] = None
            continuation = self._continue_rules_support_return_groups(
                choice.get("_remainingGroups") or [],
                counts,
                choice.get("_action") or {},
            )
            return None, {
                "kind": "support_return_order",
                "status": (
                    "continued"
                    if continuation.get("kind") == "support_return_order"
                    else "completed"
                ),
                "playerId": player_id,
                "itemIds": supplied_ids,
                "movements": moved,
                "nextChoiceId": (
                    continuation.get("id")
                    if continuation.get("kind") == "support_return_order"
                    else None
                ),
                "counts": continuation.get("counts"),
            }

        if choice.get("kind") == "score_delta_choice":
            if option not in choice.get("options", []):
                return "Choose whether the target gains or loses Points.", None
            value = int(choice.get("value") or 0)
            requested = value if option == "gain" else -value
            applied = self.adjust_rules_score(
                choice.get("targetPlayerId"), requested
            )
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "score_delta_choice",
                "status": "prevented" if not applied else "resolved",
                "playerId": player_id,
                "targetPlayerId": choice.get("targetPlayerId"),
                "delta": applied,
                "score": self.players.get(
                    choice.get("targetPlayerId"), {}
                ).get("score"),
                "sourceCardId": choice.get("sourceCardId"),
            }

        if choice.get("kind") == "simultaneous_stack_order":
            group = choice.get("_group") or []
            expected_ids = [action.get("id") for action in group]
            supplied_ids = [str(action_id or "") for action_id in (card_ids or [])]
            if (
                len(supplied_ids) != len(expected_ids)
                or len(set(supplied_ids)) != len(supplied_ids)
                or set(supplied_ids) != set(expected_ids)
            ):
                return "Order every simultaneous Stack action exactly once.", None
            actions_by_id = {action["id"]: action for action in group}
            supplied_actions = [actions_by_id[action_id] for action_id in supplied_ids]
            first_immediate = next((
                index for index, action in enumerate(supplied_actions)
                if action.get("immediate")
            ), len(supplied_actions))
            if any(
                not action.get("immediate")
                for action in supplied_actions[first_immediate:]
            ):
                return "Immediate Effects must remain above other simultaneous actions.", None
            ordered_actions = list(choice.get("_orderedActions") or [])
            ordered_actions.extend(supplied_actions)
            remaining_groups = list(choice.get("_remainingGroups") or [])
            self.rules_engine["pendingChoice"] = None
            completed = self._continue_rules_simultaneous_batch(
                remaining_groups, ordered_actions
            )
            next_choice = self.rules_engine.get("pendingChoice")
            return None, {
                "kind": "simultaneous_stack_order",
                "playerId": player_id,
                "actionIds": supplied_ids,
                "completed": completed,
                "nextPlayerId": (
                    next_choice.get("playerId")
                    if next_choice and next_choice.get("kind") == "simultaneous_stack_order"
                    else None
                ),
                "stackDepth": len(self.rules_engine["actionStack"]),
            }

        if choice.get("kind") == "persist_first_manifestation":
            if item_id not in choice.get("candidateItemIds", []):
                return "Choose a valid Persist Manifestation.", None
            candidates = [
                self.find_battlefield_item(candidate_id)
                for candidate_id in choice.get("candidateItemIds") or []
            ]
            if any(candidate is None for candidate in candidates):
                return "A Persist Manifestation is no longer available.", None
            result = self.rules_engine.get("confrontationResult") or {}
            persisted = self.find_battlefield_item(item_id)
            persisted_result = self._mark_rules_persisted_first(
                persisted, player_id
            )
            result.setdefault("persisted", []).append(persisted_result)
            returned = []
            for candidate in candidates:
                if candidate.get("id") == item_id:
                    continue
                returned.append(self._rules_remove_field_item(
                    candidate, candidate.get("ownerId"), "deck", "bottom"
                ))
            result.setdefault("returned", []).extend(returned)
            self.rules_engine["pendingChoice"] = None
            self._queue_next_rules_confrontation_destination()
            return None, {
                "kind": "persist_first_manifestation",
                "playerId": player_id,
                "itemId": item_id,
                "cardId": persisted.get("cardId"),
                "returnedItemIds": [
                    movement.get("itemId") for movement in returned
                ],
            }

        if choice.get("kind") == "pick_own_item":
            if item_id not in choice.get("candidateItemIds", []):
                return "Choose one of your Manifestations.", None
            done = list(choice.get("_done") or [])
            done.append(self.rules_stalemate_item(item_id))
            self.rules_engine["pendingChoice"] = None
            next_choice = None
            if choice.get("_queue"):
                next_choice = self.rules_next_pick_own_item_choice(
                    choice["_queue"], choice.get("actionId"),
                    choice.get("sourceCardId"), done,
                )
            self.prune_rules_ongoing_effects()
            return None, {
                "kind": "pick_own_item", "playerId": player_id, "itemId": item_id,
                "itemIds": done, "sourceCardId": choice.get("sourceCardId"),
                "nextChoiceId": next_choice["id"] if next_choice else None,
            }

        if choice.get("kind") == "effect_memory_return":
            if option not in {"return", "decline"}:
                return "Choose whether to return the remembered card.", None
            memory = next((
                entry for entry in self.rules_engine.get("effectMemories") or []
                if entry.get("id") == choice.get("memoryId")
            ), None)
            if memory is None:
                self.rules_engine["pendingChoice"] = None
                return "This remembered effect is no longer available.", None
            card_id = memory.get("cardId")
            owner_id = memory.get("ownerId")
            status = "declined"
            if option == "return":
                error, _owner_id, replacement = self.move_zone_card_by_effect(
                    owner_id, "graveyard", owner_id, "hand", card_id, "top"
                )
                status = (
                    "target_missing" if error
                    else "suspended" if replacement
                    else "returned"
                )
            self.remove_rules_effect_memory(memory["id"])
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "effect_memory_return",
                "status": status,
                "playerId": player_id,
                "cardId": card_id,
                "memoryId": memory["id"],
            }

        if choice.get("kind") == "deck_reorder":
            if not isinstance(option, dict) or not isinstance(option.get("groups"), list):
                return "Choose the top and bottom order for every revealed deck group.", None
            groups = list(choice.get("_groups") or [])
            supplied = option["groups"]
            if len(supplied) != len(groups):
                return "Order every revealed deck group exactly once.", None
            resolved_groups = []
            for group in groups:
                submitted = next((
                    entry for entry in supplied
                    if isinstance(entry, dict)
                    and entry.get("playerId") == group.get("playerId")
                ), None)
                if submitted is None:
                    return "Order every revealed deck group exactly once.", None
                top = submitted.get("top")
                bottom = submitted.get("bottom")
                if (
                    not isinstance(top, list)
                    or not isinstance(bottom, list)
                    or not all(isinstance(card_id, str) for card_id in top + bottom)
                    or len(top) != len(set(top))
                    or len(bottom) != len(set(bottom))
                    or set(top) & set(bottom)
                    or sorted(top + bottom) != sorted(group.get("cardIds") or [])
                ):
                    return "Use every revealed card exactly once.", None
                if (
                    group.get("topCount") is not None
                    and len(top) != int(group.get("topCount") or 0)
                ):
                    return "Choose the required number of cards for the top of the Deck.", None
                if (
                    group.get("bottomCount") is not None
                    and len(bottom) != int(group.get("bottomCount") or 0)
                ):
                    return "Choose the required number of cards for the bottom of the Deck.", None
                target_id = group.get("playerId")
                from_zone = group.get("fromZone") or "deck"
                source_cards = self.players.get(target_id, {}).get("zones", {}).get(from_zone, [])
                remaining = list(source_cards)
                owners = {}
                for card_id in group.get("cardIds") or []:
                    if card_id not in remaining:
                        return "A revealed card is no longer in its expected zone.", None
                    owners[card_id] = self.card_owner_in_zone(
                        target_id, from_zone, card_id
                    )
                    remaining.remove(card_id)
                for card_id in group.get("cardIds") or []:
                    self.take_zone_card(target_id, from_zone, card_id)
                if from_zone == "deck":
                    existing = list(self.players[target_id]["zones"]["deck"])
                    self.players[target_id]["zones"]["deck"] = (
                        list(top) + existing + list(bottom)
                    )
                    self.players[target_id]["zoneOwners"]["deck"].update({
                        card_id: owners[card_id] for card_id in top + bottom
                    })
                else:
                    for card_id in reversed(top):
                        self.put_zone_card(
                            target_id, "deck", card_id, owners[card_id], "top"
                        )
                    for card_id in bottom:
                        self.put_zone_card(
                            target_id, "deck", card_id, owners[card_id], "bottom"
                        )
                resolved_groups.append({
                    "playerId": target_id,
                    "top": list(top),
                    "bottom": list(bottom),
                    "fromZone": from_zone,
                })
            self.rules_engine["pendingChoice"] = None
            payload = {
                "kind": "deck_reorder",
                "playerId": player_id,
                "groups": resolved_groups,
                "sourceCardId": choice.get("sourceCardId"),
            }
            if int(choice.get("_afterDiscard") or 0) > 0:
                discard_deck = self.players[player_id]["zones"]["deck"]
                discarded_cards = []
                for _index in range(min(int(choice["_afterDiscard"]), len(discard_deck))):
                    top_card = discard_deck[0]
                    move_error, _owner, replaced = self.move_zone_card_by_effect(
                        player_id, "deck", player_id, "graveyard", top_card, "top"
                    )
                    if move_error:
                        break
                    if not replaced:
                        discarded_cards.append(top_card)
                payload["discarded"] = discarded_cards
            if int(choice.get("_afterDraw") or 0) > 0:
                payload["draw"] = self.draw_rules_cards(
                    player_id, int(choice["_afterDraw"])
                )
            if choice.get("_queue"):
                next_choice = self.rules_next_deck_order_choice(
                    choice["_queue"], choice.get("sourceCardId")
                )
                payload["nextChoiceId"] = next_choice["id"]
            return None, payload

        if choice.get("kind") == "peek_top_card":
            if option not in {"keep", "bottom"}:
                return "Choose whether to keep the card on top or move it to the bottom.", None
            card_id = choice.get("_cardId")
            deck = self.players[player_id]["zones"]["deck"]
            if not deck or deck[0] != card_id:
                self.rules_engine["pendingChoice"] = None
                return "The inspected top card is no longer available.", None
            if option == "bottom":
                deck.append(deck.pop(0))
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "peek_top_card",
                "playerId": player_id,
                "cardId": card_id,
                "destination": "bottom" if option == "bottom" else "top",
                "sourceCardId": choice.get("sourceCardId"),
            }

        if choice.get("kind") == "guess_top_card":
            if not isinstance(option, dict):
                return "Declare the card type, Temperament, and power or cost value.", None
            guessed_type = str(option.get("type") or "")
            guessed_temperament = str(option.get("temperament") or "")
            try:
                guessed_value = int(option.get("value"))
            except (TypeError, ValueError):
                return "Declare a valid power or cost value.", None
            if (
                guessed_type not in choice.get("types", [])
                or guessed_temperament not in choice.get("temperaments", [])
                or guessed_value not in choice.get("values", [])
            ):
                return "Declare a valid card type, Temperament, and value.", None
            target_id = choice.get("targetPlayerId")
            card_id = choice.get("_cardId")
            target_deck = self.players.get(target_id, {}).get("zones", {}).get("deck", [])
            if not target_deck or target_deck[0] != card_id:
                self.rules_engine["pendingChoice"] = None
                return "The guessed top card is no longer available.", None
            metadata = self.card_rules.get(card_id, {})
            actual_type = (
                "manifestation"
                if metadata.get("type") == "manifestation" else "will"
            )
            actual_temperaments = list(metadata.get("temperaments") or [])
            actual_value = (
                int(metadata.get("power") or 0)
                if actual_type == "manifestation"
                else int(metadata.get("cost") or 0)
            )
            correct = sum((
                guessed_type == actual_type,
                guessed_temperament in actual_temperaments,
                guessed_value == actual_value,
            ))
            score_delta = correct * 10
            score_delta = self.adjust_rules_score(
                player_id, score_delta
            )
            follow_up = None
            self.rules_engine["pendingChoice"] = None
            if correct == 1 and self.players[player_id]["zones"]["deck"]:
                own_card_id = self.players[player_id]["zones"]["deck"][0]
                follow_choice_id = new_id()
                self.rules_engine["pendingChoice"] = {
                    "id": follow_choice_id,
                    "kind": "peek_top_card",
                    "playerId": player_id,
                    "sourceCardId": choice.get("sourceCardId"),
                    "cardId": own_card_id,
                    "_cardId": own_card_id,
                }
                follow_up = {
                    "kind": "choice_required",
                    "choiceId": follow_choice_id,
                    "choiceKind": "peek_top_card",
                    "playerId": player_id,
                }
            elif correct == 2:
                drawn = self.draw_rules_cards(player_id, 2)
                follow_up = {"kind": "draw", "count": len(drawn)}
            elif correct == 3 and self.players[player_id]["zones"]["deck"]:
                own_card_id = self.players[player_id]["zones"]["deck"][0]
                own_type = self.card_rules.get(own_card_id, {}).get("type")
                if own_type == "manifestation":
                    error, follow_up = self.chain_rules_manifestation(
                        player_id, "deck", own_card_id,
                        source_card_id=choice.get("sourceCardId"),
                    )
                    if error:
                        follow_up = {"kind": "chain_manifestation", "error": error}
                elif own_type in RULES_WILL_TYPES:
                    owner_id = self.card_owner_in_zone(
                        player_id, "deck", own_card_id
                    )
                    error, _owner_id, replacement = self.move_zone_card_by_effect(
                        player_id, "deck", owner_id, "hand",
                        own_card_id, "bottom",
                    )
                    if not error and not replacement:
                        permission = {
                            "id": new_id(),
                            "abilityId": "play-revealed-will-without-tribute",
                            "playerId": player_id,
                            "cardId": own_card_id,
                            "fromZone": "hand",
                            "phaseIds": [
                                "confrontation_reaction",
                                "resolution_effects",
                                "end_actions",
                            ],
                            "asSupport": False,
                            "noTribute": True,
                            "turn": self.phase_tracker["turn"],
                        }
                        self.rules_engine["playPermissions"].append(permission)
                        follow_up = {
                            "kind": "play_permission",
                            "cardId": own_card_id,
                            "permissionId": permission["id"],
                            "noTribute": True,
                        }
            return None, {
                "kind": "guess_top_card",
                "playerId": player_id,
                "targetPlayerId": target_id,
                "cardId": card_id,
                "guess": {
                    "type": guessed_type,
                    "temperament": guessed_temperament,
                    "value": guessed_value,
                },
                "actual": {
                    "type": actual_type,
                    "temperaments": actual_temperaments,
                    "value": actual_value,
                },
                "correct": correct,
                "scoreDelta": score_delta,
                "score": self.players[player_id]["score"],
                "followUp": follow_up,
                "sourceCardId": choice.get("sourceCardId"),
                "_overflowPlayerId": (
                    player_id
                    if len(self.players[player_id]["zones"]["hand"])
                    > self.rules_hand_limit(player_id)
                    else None
                ),
            }

        if choice.get("kind") == "optional_trigger":
            if option not in choice.get("options", []):
                return "Choose whether to use the optional triggered effect.", None
            status = "declined"
            created_item_id = None
            if option == "accept":
                source_item = self.find_battlefield_item(
                    choice.get("_sourceItemId")
                )
                if (
                    source_item is None
                    or int(round(float(source_item.get("rotation") or 0))) % 180
                ):
                    return "The optional source is no longer ready.", None
                source_item["rotation"] = 90.0
                copy = self.create_rules_token_copy(
                    choice.get("_relatedCardId"), player_id,
                    source_item_id=source_item.get("id"),
                )
                created_item_id = copy["id"]
                status = "accepted"
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "optional_trigger",
                "status": status,
                "playerId": player_id,
                "sourceCardId": choice.get("sourceCardId"),
                "relatedCardId": choice.get("_relatedCardId"),
                "createdItemId": created_item_id,
            }

        if choice.get("kind") == "optional_discard_draw":
            if option not in choice.get("options", []):
                return "Choose whether to discard a card and draw.", None
            if option == "decline":
                self.rules_engine["pendingChoice"] = None
                return None, {
                    "kind": "optional_discard_draw",
                    "status": "declined",
                    "playerId": player_id,
                    "sourceCardId": choice.get("sourceCardId"),
                }
            next_choice = {
                "id": new_id(),
                "kind": "discard_from_hand",
                "playerId": player_id,
                "count": 1,
                "drawAfter": int(choice.get("draw") or 0),
                "sourceCardId": choice.get("sourceCardId"),
            }
            self.rules_engine["pendingChoice"] = next_choice
            return None, {
                "kind": "optional_discard_draw",
                "status": "accepted",
                "playerId": player_id,
                "nextChoiceId": next_choice["id"],
                "sourceCardId": choice.get("sourceCardId"),
            }

        if choice.get("kind") == "points_or_weaken_first":
            if option not in choice.get("options", []):
                return "Choose whether to lose points or weaken your First Manifestation.", None
            outcome = {}
            if option == "lose_points":
                outcome["delta"] = self.adjust_rules_score(player_id, -int(choice.get("points") or 0))
            else:
                first = self.find_battlefield_item(
                    (self.rules_engine.get("firstManifestationItemIds") or {}).get(player_id)
                )
                if first is not None:
                    self.rules_engine["ongoingEffects"].append({
                        "id": new_id(), "actionId": None, "abilityId": "points-or-weaken-first",
                        "controllerId": player_id,
                        "source": {"cardId": choice.get("sourceCardId")},
                        "target": {
                            "kind": "card", "itemId": first["id"],
                            "cardId": first.get("cardId"), "ownerId": first.get("ownerId"),
                        },
                        "kind": "power_modifier", "duration": "until_end_of_turn",
                        "startedTurn": self.phase_tracker["turn"],
                        "value": -int(choice.get("power") or 0),
                    })
                    outcome["itemId"] = first["id"]
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "points_or_weaken_first",
                "status": "lost_points" if option == "lose_points" else "weakened",
                "playerId": player_id, "sourceCardId": choice.get("sourceCardId"), **outcome,
            }

        if choice.get("kind") == "points_or_hand_limit":
            if option not in choice.get("options", []):
                return "Choose whether to lose points or limit your Hand.", None
            if option == "lose_points":
                delta = self.adjust_rules_score(
                    player_id, -int(choice.get("points") or 0)
                )
                self.rules_engine["pendingChoice"] = None
                return None, {
                    "kind": "points_or_hand_limit",
                    "status": "lost_points",
                    "playerId": player_id,
                    "delta": delta,
                    "score": self.players[player_id]["score"],
                    "sourceCardId": choice.get("sourceCardId"),
                }
            self.rules_engine["handLimitEffects"].append({
                "id": new_id(),
                "playerId": player_id,
                "turn": self.phase_tracker["turn"],
                "limit": int(choice.get("limit") or 0),
                "overflowDestination": "graveyard",
                "sourceCardId": choice.get("sourceCardId"),
            })
            self.rules_engine["pendingChoice"] = None
            overflow = self.set_rules_hand_overflow_choice([player_id])
            return None, {
                "kind": "points_or_hand_limit",
                "status": "limited_hand",
                "playerId": player_id,
                "limit": int(choice.get("limit") or 0),
                "overflowChoiceId": overflow.get("id") if overflow else None,
                "sourceCardId": choice.get("sourceCardId"),
            }

        if choice.get("kind") == "hand_overflow":
            if not isinstance(card_ids, list) or not all(
                isinstance(card_id, str) for card_id in card_ids
            ):
                return "Choose the required excess cards.", None
            required = int(choice.get("count") or 0)
            if len(card_ids) != required:
                return "Choose the required excess cards.", None
            hand = list(self.players[player_id]["zones"]["hand"])
            for card_id in card_ids:
                if card_id not in hand:
                    return "An excess card is no longer in your Hand.", None
                hand.remove(card_id)
            destination = choice.get("destination")
            zone = "deck" if destination == "deck_bottom" else "graveyard"
            position = "bottom" if destination == "deck_bottom" else "top"
            for card_id in card_ids:
                error, _owner_id = self.move_zone_card(
                    player_id, "hand", player_id, zone, card_id, position
                )
                if error:
                    return error, None
            remaining = list(choice.get("remainingPlayerIds") or [])
            self.rules_engine["pendingChoice"] = None
            next_choice = self.set_rules_hand_overflow_choice(remaining)
            return None, {
                "kind": "hand_overflow",
                "playerId": player_id,
                "cardIds": list(card_ids),
                "destination": destination,
                "nextPlayerId": (
                    next_choice.get("playerId") if next_choice else None
                ),
            }

        if choice.get("kind") == "draw_replacement":
            offered = list(choice.get("_cardIds") or [])
            if not isinstance(card_ids, list) or len(card_ids) != int(
                choice.get("count") or 0
            ):
                return "Choose the required cards to discard.", None
            if len(set(card_ids)) != len(card_ids) or not set(card_ids) <= set(offered):
                return "Choose only the inspected draw cards.", None
            deck = self.players[player_id]["zones"]["deck"]
            if deck[:len(offered)] != offered:
                self.rules_engine["pendingChoice"] = None
                return "The inspected draw cards are no longer available.", None
            drawn_ids = [card_id for card_id in offered if card_id not in card_ids]
            for card_id in offered:
                owner_id = self.card_owner_in_zone(player_id, "deck", card_id)
                self.take_zone_card(player_id, "deck", card_id)
                self.put_zone_card(
                    player_id,
                    "graveyard" if card_id in card_ids else "hand",
                    card_id, owner_id, "top" if card_id in card_ids else "bottom",
                )
            will_count = sum(
                self.card_rules.get(card_id, {}).get("type") in RULES_WILL_TYPES
                for card_id in card_ids
            )
            self.rules_engine["pendingChoice"] = None
            follow_up = self.set_rules_hand_overflow_choice([player_id])
            if will_count:
                source_controller_id = choice.get("sourceControllerId")
                candidates = [
                    item["id"] for item in self.battlefield
                    if item.get("faceUp")
                    and (
                        self.card_rules.get(item.get("cardId"), {}).get("type")
                        == "manifestation" or item.get("isTokenCard")
                    )
                    and self.rules_item_controller_id(item)
                    != source_controller_id
                ]
                if candidates:
                    follow_up = {
                        "id": new_id(),
                        "kind": "power_loss_distribution",
                        "playerId": source_controller_id,
                        "count": will_count,
                        "candidateItemIds": candidates,
                        "sourceCardId": choice.get("sourceCardId"),
                    }
                    self.rules_engine["pendingChoice"] = follow_up
            return None, {
                "kind": "draw_replacement",
                "playerId": player_id,
                "discardedCardIds": list(card_ids),
                "drawnCardIds": drawn_ids,
                "willCount": will_count,
                "followUpChoiceId": follow_up.get("id") if follow_up else None,
            }

        if choice.get("kind") == "power_loss_distribution":
            item_ids = (
                option.get("itemIds")
                if isinstance(option, dict) else None
            )
            if (
                not isinstance(item_ids, list)
                or len(item_ids) != int(choice.get("count") or 0)
                or not all(item_id in choice.get("candidateItemIds", []) for item_id in item_ids)
            ):
                return "Choose one valid target for each discarded Will.", None
            applied = []
            for item_id in item_ids:
                item = self.find_battlefield_item(item_id)
                if item is None:
                    return "A selected Manifestation is no longer on the field.", None
                effect = {
                    "id": new_id(),
                    "actionId": choice.get("id"),
                    "abilityId": "draw-replacement-power-loss",
                    "controllerId": player_id,
                    "source": {
                        "cardId": choice.get("sourceCardId"),
                        "zone": "battlefield",
                    },
                    "target": {
                        "kind": "card", "itemId": item_id,
                        "cardId": item.get("cardId"),
                        "ownerId": item.get("ownerId"),
                    },
                    "kind": "power_modifier",
                    "duration": "until_end_of_turn",
                    "startedTurn": self.phase_tracker["turn"],
                    "value": -1,
                }
                self.rules_engine["ongoingEffects"].append(effect)
                applied.append(effect["id"])
            self.rules_engine["pendingChoice"] = None
            overflow = (
                self.set_rules_hand_overflow_choice(
                    [choice.get("_overflowPlayerId")]
                )
                if choice.get("_overflowPlayerId") else None
            )
            return None, {
                "kind": "power_loss_distribution",
                "playerId": player_id,
                "itemIds": list(item_ids),
                "effectIds": applied,
                "sourceCardId": choice.get("sourceCardId"),
                "overflowChoiceId": overflow.get("id") if overflow else None,
            }

        if choice.get("kind") == "random_target_effect":
            if item_id not in choice.get("candidateItemIds", []):
                return "Choose a valid card for the random effect.", None
            item = self.find_battlefield_item(item_id)
            if item is None:
                return "The selected card is no longer on the field.", None
            effect = {
                "id": new_id(),
                "actionId": choice.get("id"),
                "abilityId": "random-target-effect",
                "controllerId": player_id,
                "source": {
                    "cardId": choice.get("sourceCardId"),
                    "itemId": choice.get("sourceItemId"),
                    "zone": "battlefield",
                },
                "target": {
                    "kind": "card", "itemId": item_id,
                    "cardId": item.get("cardId"),
                    "ownerId": item.get("ownerId"),
                },
                "kind": choice.get("effectKind"),
                "duration": "until_end_of_turn",
                "startedTurn": self.phase_tracker["turn"],
            }
            self.rules_engine["ongoingEffects"].append(effect)
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "random_target_effect",
                "playerId": player_id,
                "itemId": item_id,
                "effectId": effect["id"],
                "roll": choice.get("roll"),
                "sourceCardId": choice.get("sourceCardId"),
            }

        if choice.get("kind") == "skip_confrontation_payment":
            if option not in choice.get("options", []):
                return "Choose whether to lose points or skip the Confrontation.", None
            if option == "lose_points":
                requested = -int(choice.get("points") or 0)
                delta = self.adjust_rules_score(player_id, requested)
                status = "paid" if delta == requested else "prevented"
            else:
                self.phase_tracker["index"] = ADVANCED_PHASES.index(
                    "resolution_compare"
                )
                self.rules_engine["priorityPasses"] = []
                status = "skipped"
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "skip_confrontation_payment",
                "status": status,
                "playerId": player_id,
                "score": self.players[player_id]["score"],
                "phaseId": self.current_phase_id(),
                "sourceCardId": choice.get("sourceCardId"),
            }

        if choice.get("kind") == "confrontation_relocation":
            groups = choice.get("_groups") or []
            supplied = (
                option.get("groups")
                if isinstance(option, dict) else None
            )
            if not isinstance(supplied, list) or len(supplied) != len(groups):
                return "Choose a destination for every Confrontation Manifestation.", None
            movements = []
            for group in groups:
                submitted = next((
                    entry for entry in supplied
                    if isinstance(entry, dict)
                    and entry.get("playerId") == group.get("playerId")
                ), None)
                if submitted is None:
                    return "Choose every player's Confrontation destinations.", None
                interzone_ids = submitted.get("interzone")
                deck_ids = submitted.get("deckBottom")
                expected = list(group.get("itemIds") or [])
                if (
                    not isinstance(interzone_ids, list)
                    or not isinstance(deck_ids, list)
                    or len(interzone_ids) > int(group.get("interzoneSlots") or 0)
                    or len(set(interzone_ids + deck_ids)) != len(expected)
                    or set(interzone_ids + deck_ids) != set(expected)
                ):
                    return "Use every Confrontation Manifestation exactly once within the Interzone limit.", None
                for current_id in interzone_ids:
                    item = self.find_battlefield_item(current_id)
                    if item is None:
                        return "A Confrontation Manifestation is no longer available.", None
                    item["fieldZone"] = "interzone"
                    self.mark_rules_interzone_entry(item)
                    item["isSupport"] = False
                    item["stackedOn"] = None
                    movements.append({
                        "itemId": current_id, "cardId": item.get("cardId"),
                        "destination": "interzone",
                    })
                for current_id in deck_ids:
                    item = self.find_battlefield_item(current_id)
                    if item is None:
                        return "A Confrontation Manifestation is no longer available.", None
                    movements.append(self._rules_remove_field_item_by_effect(
                        item, item.get("ownerId"), "deck", "bottom"
                    ))
            opponent_id = self.other_rules_player_id(player_id)
            if opponent_id:
                self.adjust_rules_score(opponent_id, 50)
            self.phase_tracker["index"] = ADVANCED_PHASES.index("end_actions")
            self.rules_engine["priorityPasses"] = []
            self.rules_engine["confrontationResult"] = None
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "confrontation_relocation",
                "status": "ended",
                "playerId": player_id,
                "movements": movements,
                "opponentId": opponent_id,
                "opponentScore": (
                    self.players[opponent_id]["score"] if opponent_id else None
                ),
                "phaseId": self.current_phase_id(),
                "sourceMovement": choice.get("_sourceMovement"),
                "sourceCardId": choice.get("sourceCardId"),
            }

        if choice.get("kind") == "suspend_hand_will":
            if (
                not isinstance(card_ids, list)
                or len(card_ids) != 1
                or card_ids[0] not in choice.get("_cardIds", [])
            ):
                return "Choose one eligible Will to Suspend.", None
            card_id = card_ids[0]
            error, suspended = self.suspend_zone_card(
                player_id, "hand", card_id,
                source_effect_id=choice.get("sourceItemId"),
                returnZone="hand",
                returnTurn=self.phase_tracker["turn"],
                playableByPlayerId=choice.get("playableByPlayerId"),
                anyTemperamentTribute=True,
            )
            if error:
                return error, None
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "suspend_hand_will",
                "playerId": player_id,
                "cardId": card_id,
                "suspensionId": suspended.get("id"),
                "playableByPlayerId": choice.get("playableByPlayerId"),
                "sourceCardId": choice.get("sourceCardId"),
            }

        if choice.get("kind") == "effect_memory_payment":
            if option not in {"pay", "decline"}:
                return "Choose whether to pay the requested Tribute.", None
            memory = next((
                entry for entry in self.rules_engine.get("effectMemories") or []
                if entry.get("id") == choice.get("memoryId")
            ), None)
            if memory is None:
                self.rules_engine["pendingChoice"] = None
                return "This remembered effect is no longer available.", None
            if option == "pay":
                payment_error, payment = self.rules_action_payment(
                    player_id, "activated_effect", None, card_ids,
                    {"tribute": choice.get("payment")},
                )
                if payment_error:
                    return payment_error, None
                self.pay_rules_tribute(player_id, payment)
                status = "paid"
            else:
                owner_id = memory.get("ownerId")
                card_id = memory.get("cardId")
                error, _owner_id, replacement = self.move_zone_card_by_effect(
                    owner_id, "graveyard", owner_id, "hand", card_id, "top"
                )
                status = (
                    "target_missing" if error
                    else "suspended" if replacement
                    else "returned"
                )
            self.remove_rules_effect_memory(memory["id"])
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "effect_memory_payment",
                "status": status,
                "playerId": player_id,
                "cardId": memory.get("cardId"),
                "memoryId": memory["id"],
                "payment": choice.get("payment"),
            }

        if choice.get("kind") == "immediate_effect_payment":
            if option not in {"pay", "decline"}:
                return "Choose whether to pay the requested Tribute.", None
            if option == "pay":
                payment_error, payment = self.rules_action_payment(
                    player_id, "activated_effect", None, card_ids,
                    {"tribute": choice.get("payment")},
                )
                if payment_error:
                    return payment_error, None
                self.pay_rules_tribute(player_id, payment)
                status = "paid"
                confrontation = None
            else:
                status = "declined"
                source_card_id = choice.get("sourceCardId")
                controller_id = choice.get("controllerId")
                if (
                    choice.get("exileOnDecline")
                    and source_card_id in self.players.get(
                        controller_id, {}
                    ).get("zones", {}).get("graveyard", [])
                ):
                    self.move_zone_card_by_effect(
                        controller_id, "graveyard",
                        controller_id, "exile", source_card_id, "top",
                    )
                self.phase_tracker["index"] = ADVANCED_PHASES.index(
                    "resolution_compare"
                )
                self.rules_engine["priorityPasses"] = []
                confrontation = self.prepare_rules_confrontation_result()
            followup_choice = None
            if (
                status == "declined"
                and confrontation
                and choice.get(
                    "reduceWinnerManifestationOnControllerDefeat"
                )
                and confrontation.get("loserId")
                == choice.get("controllerId")
                and int(choice.get("controllerBasePower") or 0) > 0
            ):
                controller_id = choice.get("controllerId")
                target_rules = {
                    "min": 1,
                    "max": 1,
                    "cardType": "manifestation",
                    "zones": ["battlefield"],
                    "fieldZone": "confrontation",
                    "controller": "opponent",
                }
                candidates = [
                    item for item in self.rules_confrontation_items(
                        confrontation.get("winnerId")
                    )
                    if self.rules_ability_targets_error(
                        target_rules,
                        [{
                            "kind": "card",
                            "itemId": item.get("id"),
                            "cardId": item.get("cardId"),
                            "ownerId": item.get("ownerId"),
                        }],
                        controller_id,
                    ) is None
                ]
                if candidates:
                    followup_action = {
                        "id": new_id(),
                        "controllerId": controller_id,
                        "label": (
                            f'{self.card_labels.get(choice.get("sourceCardId"), choice.get("sourceCardId"))}'
                            " — immediate power loss"
                        ),
                        "kind": "triggered_effect",
                        "source": {
                            "cardId": choice.get("sourceCardId"),
                            "zone": "exile",
                            "itemId": None,
                            "cardType": "ephemeral_will",
                            "ownerId": controller_id,
                        },
                        "target": None,
                        "targets": [],
                        "ability": {
                            "id": "immediate-controller-defeat-power-loss",
                            "trigger": {
                                "event": "immediate_controller_defeat",
                            },
                            "result": {
                                "kind": "adjust_target_power",
                                "value": -int(
                                    choice.get("controllerBasePower") or 0
                                ),
                            },
                            "ongoingEffect": None,
                            "targets": target_rules,
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
                        "immediate": True,
                    }
                    followup_choice = {
                        "id": new_id(),
                        "kind": "trigger_targets",
                        "playerId": controller_id,
                        "sourceCardId": choice.get("sourceCardId"),
                        "targetRules": target_rules,
                        "_triggerAction": followup_action,
                    }
            self.rules_engine["pendingChoice"] = followup_choice
            if followup_choice:
                self.rules_engine["priorityPlayerId"] = (
                    followup_choice["playerId"]
                )
            payload = {
                "kind": "immediate_effect_payment",
                "status": status,
                "playerId": player_id,
                "sourceCardId": choice.get("sourceCardId"),
                "phaseId": self.current_phase_id(),
                "confrontationResult": confrontation,
            }
            if followup_choice:
                payload["followupChoiceId"] = followup_choice["id"]
                payload["powerLoss"] = int(
                    choice.get("controllerBasePower") or 0
                )
            return None, payload

        if choice.get("kind") == "trigger_targets":
            target_error, clean_targets = self.rules_action_targets(targets)
            if target_error:
                return target_error, None
            ability_error = self.rules_ability_targets_error(
                choice.get("targetRules"), clean_targets, player_id,
                source_item_id=(
                    (choice.get("_triggerAction") or {}).get("source") or {}
                ).get("itemId"),
            )
            if ability_error:
                return ability_error, None
            action = choice.get("_triggerAction")
            if not isinstance(action, dict):
                self.rules_engine["pendingChoice"] = None
                return "This triggered effect is no longer available.", None
            action["targets"] = clean_targets
            resume_cleanup = bool(choice.get("_resumeConfrontationCleanup"))
            optional_batch = choice.get("_optionalStackBatch")
            self.rules_engine["pendingChoice"] = None
            if optional_batch:
                self._continue_rules_optional_stack_choices(
                    optional_batch.get("actions") or [],
                    int(optional_batch.get("nextIndex") or 0),
                    [
                        *(optional_batch.get("acceptedActions") or []),
                        action,
                    ],
                    optional_batch.get("priorityPlayerId"),
                )
            else:
                self.queue_rules_simultaneous_actions([action])
            if resume_cleanup:
                self._queue_next_rules_confrontation_destination()
            return None, {
                "kind": "trigger_targets",
                "playerId": player_id,
                "sourceCardId": choice.get("sourceCardId"),
                "actionId": action.get("id"),
                "targets": clean_targets,
            }

        if choice.get("kind") == "stack_copy_targets":
            if option not in {"keep", "retarget"}:
                return "Choose whether to keep or replace the copied Will's target.", None
            copied_action = choice.get("_copyAction")
            if not isinstance(copied_action, dict):
                self.rules_engine["pendingChoice"] = None
                return "The copied Stack action is no longer available.", None
            selected_targets = choice.get("originalTargets") if option == "keep" else targets
            target_error, clean_targets = self.rules_action_targets(selected_targets)
            if target_error:
                return target_error, None
            ability_error = self.rules_ability_targets_error(
                choice.get("targetRules"), clean_targets, player_id,
            )
            if ability_error:
                return ability_error, None
            copied_action["targets"] = clean_targets
            self.rules_engine["actionStack"].append(copied_action)
            self.rules_engine["pendingChoice"] = None
            self.rules_engine["priorityPasses"] = []
            self.rules_engine["priorityPlayerId"] = self.other_rules_player_id(player_id)
            return None, {
                "kind": "stack_copy_targets", "status": "copied",
                "playerId": player_id, "choiceId": choice_id,
                "sourceCardId": choice.get("sourceCardId"),
                "targetCardId": choice.get("targetCardId"),
                "targetActionId": choice.get("targetActionId"),
                "copyActionId": copied_action.get("id"),
                "keptOriginalTargets": option == "keep",
                "targets": [dict(entry) for entry in clean_targets],
            }

        if choice.get("kind") == "effect_payment":
            if option not in {"pay", "decline"}:
                return "Choose whether to pay the requested Tribute.", None
            on_decline = choice.get("onDecline") or {}
            if option == "pay":
                payment_error, payment = self.rules_action_payment(
                    player_id, "activated_effect", None, card_ids,
                    {"tribute": choice.get("payment")},
                )
                if payment_error:
                    return payment_error, None
                self.pay_rules_tribute(player_id, payment)
                triggered_actions = self.queue_rules_tribute_triggers(payment["cardIds"], player_id)
                self.rules_engine["pendingChoice"] = None
                return None, {
                    "kind": "effect_payment", "status": "paid", "playerId": player_id,
                    "choiceId": choice_id, "sourceCardId": choice.get("sourceCardId"),
                    "triggeredActions": triggered_actions,
                }
            outcome = {}
            if on_decline.get("kind") == "deck_discard":
                deck = self.players[player_id]["zones"]["deck"]
                discarded = 0
                for _index in range(min(int(on_decline.get("count") or 0), len(deck))):
                    error, _owner, replacement = self.move_zone_card_by_effect(
                        player_id, "deck", player_id, "graveyard", deck[0], "top"
                    )
                    if error:
                        break
                    if not replacement:
                        discarded += 1
                outcome["discarded"] = discarded
            elif on_decline.get("kind") == "lock_support_entries":
                self.rules_engine.setdefault("supportLocks", []).append({
                    "turn": self.phase_tracker["turn"], "playerId": None,
                })
                outcome["locked"] = True
            elif on_decline.get("kind") == "lose_effects":
                item = self.find_battlefield_item(on_decline.get("itemId"))
                if item is not None:
                    self.rules_engine["ongoingEffects"].append({
                        "id": new_id(), "actionId": choice.get("actionId"),
                        "abilityId": "effect-payment-declined",
                        "controllerId": choice.get("controllerId") or player_id,
                        "source": {"cardId": choice.get("sourceCardId")},
                        "target": {
                            "kind": "card", "itemId": item["id"],
                            "cardId": item.get("cardId"), "ownerId": item.get("ownerId"),
                        },
                        "kind": "lose_effects", "duration": "permanent",
                        "startedTurn": self.phase_tracker["turn"],
                    })
                    outcome["itemId"] = item["id"]
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "effect_payment", "status": "declined", "playerId": player_id,
                "choiceId": choice_id, "sourceCardId": choice.get("sourceCardId"),
                **outcome,
            }

        if choice.get("kind") == "stack_counter_payment":
            if option not in {"pay", "decline"}:
                return "Choose whether to pay the requested Tribute.", None
            target_action = next((
                action for action in self.rules_engine.get("actionStack") or []
                if action.get("id") == choice.get("targetActionId")
            ), None)
            if not self.rules_stack_target_matches(target_action, choice.get("targetKind")):
                self.rules_engine["pendingChoice"] = None
                return None, {
                    "kind": "stack_counter_payment", "status": "target_missing",
                    "playerId": player_id, "choiceId": choice_id,
                    "sourceCardId": choice.get("sourceCardId"),
                    "targetActionId": choice.get("targetActionId"),
                    "targetCardId": choice.get("targetCardId"),
                    "mode": choice.get("mode"),
                }
            if option == "pay":
                payment_error, payment = self.rules_action_payment(
                    player_id, "activated_effect", None, card_ids,
                    {"tribute": choice.get("payment")},
                )
                if payment_error:
                    return payment_error, None
                self.pay_rules_tribute(player_id, payment)
                triggered_actions = self.queue_rules_tribute_triggers(payment["cardIds"], player_id)
                self.rules_engine["pendingChoice"] = None
                return None, {
                    "kind": "stack_counter_payment", "status": "paid",
                    "playerId": player_id, "choiceId": choice_id,
                    "sourceCardId": choice.get("sourceCardId"),
                    "targetActionId": choice.get("targetActionId"),
                    "targetCardId": choice.get("targetCardId"),
                    "mode": choice.get("mode"),
                    "cost": {
                        "tributeCardIds": payment["cardIds"],
                        "tributeRequirements": payment["requirements"],
                        "essenceSpent": payment["essenceSpent"],
                        "excessEssence": payment["excessEssence"],
                    },
                    "triggeredActions": triggered_actions,
                }
            countered = self.counter_rules_stack_action(target_action, choice.get("mode"))
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "stack_counter_payment", "playerId": player_id,
                "choiceId": choice_id, "sourceCardId": choice.get("sourceCardId"),
                "targetActionId": choice.get("targetActionId"),
                "targetCardId": choice.get("targetCardId"),
                "mode": choice.get("mode"),
                **countered,
            }

        if choice.get("kind") == "recovery_shared_choice":
            if option not in choice.get("options", []):
                return "Choose a valid Recovery effect.", None
            discarded = []
            score_delta = 0
            if option == "discard_deck_bottom_3":
                if len(self.players[player_id]["zones"]["deck"]) < 3:
                    return "Your Deck no longer has three cards to discard.", None
                for _index in range(3):
                    card_id = self.players[player_id]["zones"]["deck"][-1]
                    error, _owner_id = self.move_zone_card(
                        player_id, "deck", player_id, "graveyard", card_id, "top"
                    )
                    if error:
                        return error, None
                    discarded.append(card_id)
            else:
                score_delta = self.adjust_rules_score(player_id, -10)
            remaining = list(choice.get("remainingPlayerIds") or [])
            source_action = {
                "id": choice.get("actionId"),
                "controllerId": choice.get("controllerId"),
                "source": {"cardId": choice.get("sourceCardId")},
            }
            self.rules_engine["pendingChoice"] = None
            next_choice = self._set_next_rules_recovery_choice(remaining, source_action)
            return None, {
                "kind": "recovery_shared_choice",
                "playerId": player_id,
                "option": option,
                "cardIds": discarded,
                "count": len(discarded),
                "scoreDelta": score_delta,
                "score": self.players[player_id]["score"],
                "choiceId": choice_id,
                "actionId": choice.get("actionId"),
                "controllerId": choice.get("controllerId"),
                "sourceCardId": choice.get("sourceCardId"),
                "nextPlayerId": next_choice.get("playerId") if next_choice else None,
            }

        if choice.get("kind") == "confrontation_destination":
            if option not in choice.get("options", []):
                return "Choose a valid confrontation destination.", None
            item = self.find_battlefield_item(choice.get("itemId"))
            if item is None or item.get("ownerId") != player_id:
                return "This confrontation card is no longer available.", None
            result = self.rules_engine.get("confrontationResult") or {}
            if option == "deck_bottom":
                movement = self._rules_remove_field_item(item, item["ownerId"], "deck", "bottom")
                result.setdefault("returned", []).append(movement)
                pending = result.get("pendingOwnItemIds") or []
                if pending and pending[0] == item["id"]:
                    pending.pop(0)
                self.rules_engine["pendingChoice"] = None
                self._queue_next_rules_confrontation_destination()
                return None, {
                    "kind": "confrontation_destination", "playerId": player_id,
                    "cardId": item.get("cardId"), "itemId": item.get("id"),
                    "destination": "deck_bottom",
                }

            interzone_items = self.rules_confrontation_items(player_id, ("interzone",))
            if self.rules_interzone_slot_count(player_id) >= self.rules_interzone_capacity(player_id):
                share_anchor = self.rules_interzone_share_anchor(player_id, item)
                if share_anchor:
                    item["fieldZone"] = "interzone"
                    self.mark_rules_interzone_entry(item)
                    item["stackedOn"] = share_anchor
                    result.setdefault("returned", []).append({
                        "status": "interzone", "itemId": item["id"],
                        "cardId": item.get("cardId"), "stackedOn": share_anchor,
                    })
                    pending = result.get("pendingOwnItemIds") or []
                    if pending and pending[0] == item["id"]:
                        pending.pop(0)
                    self.rules_engine["pendingChoice"] = None
                    triggered_actions = self.queue_rules_field_zone_entry_triggers(
                        item, "interzone",
                        resume_confrontation_cleanup=True,
                    )
                    if not self.rules_engine.get("pendingChoice"):
                        self._queue_next_rules_confrontation_destination()
                    return None, {
                        "kind": "confrontation_destination", "playerId": player_id,
                        "cardId": item.get("cardId"), "itemId": item.get("id"),
                        "destination": "interzone", "stackedOn": share_anchor,
                        "triggeredActions": triggered_actions,
                    }
                replacement_candidates = [
                    entry["id"] for entry in interzone_items
                    if self.rules_interzone_item_replaceable(entry)
                ]
                if not replacement_candidates:
                    return "No Manifestation in your Interzone can currently be replaced.", None
                replacement = {
                    "id": new_id(), "kind": "confrontation_replace_interzone",
                    "playerId": player_id, "itemId": item["id"], "cardId": item.get("cardId"),
                    "candidateItemIds": replacement_candidates,
                }
                self.rules_engine["pendingChoice"] = replacement
                return None, {
                    "kind": "confrontation_replacement_required", "playerId": player_id,
                    "cardId": item.get("cardId"), "itemId": item.get("id"),
                }
            item["fieldZone"] = "interzone"
            self.mark_rules_interzone_entry(item)
            result.setdefault("returned", []).append({
                "status": "interzone", "itemId": item["id"], "cardId": item.get("cardId"),
            })
            pending = result.get("pendingOwnItemIds") or []
            if pending and pending[0] == item["id"]:
                pending.pop(0)
            self.rules_engine["pendingChoice"] = None
            triggered_actions = self.queue_rules_field_zone_entry_triggers(
                item, "interzone",
                resume_confrontation_cleanup=True,
            )
            if not self.rules_engine.get("pendingChoice"):
                self._queue_next_rules_confrontation_destination()
            return None, {
                "kind": "confrontation_destination", "playerId": player_id,
                "cardId": item.get("cardId"), "itemId": item.get("id"),
                "destination": "interzone",
                "triggeredActions": triggered_actions,
            }

        if choice.get("kind") == "confrontation_replace_interzone":
            if item_id not in choice.get("candidateItemIds", []):
                return "Choose a valid Interzone card to replace.", None
            entering = self.find_battlefield_item(choice.get("itemId"))
            replaced = self.find_battlefield_item(item_id)
            if (
                entering is None
                or replaced is None
                or self.rules_item_controller_id(replaced) != player_id
                or not self.rules_interzone_item_replaceable(replaced)
            ):
                return "This Interzone choice is no longer available.", None
            movement = self._rules_remove_field_item(replaced, replaced["ownerId"], "deck", "bottom")
            entering["fieldZone"] = "interzone"
            self.mark_rules_interzone_entry(entering)
            result = self.rules_engine.get("confrontationResult") or {}
            result.setdefault("returned", []).extend([
                movement,
                {"status": "interzone", "itemId": entering["id"], "cardId": entering.get("cardId")},
            ])
            pending = result.get("pendingOwnItemIds") or []
            if pending and pending[0] == entering["id"]:
                pending.pop(0)
            self.rules_engine["pendingChoice"] = None
            triggered_actions = self.queue_rules_field_zone_entry_triggers(
                entering, "interzone",
                resume_confrontation_cleanup=True,
            )
            if not self.rules_engine.get("pendingChoice"):
                self._queue_next_rules_confrontation_destination()
            return None, {
                "kind": "confrontation_replace_interzone", "playerId": player_id,
                "cardId": entering.get("cardId"), "itemId": entering.get("id"),
                "replacedCardId": replaced.get("cardId"), "replacedItemId": replaced.get("id"),
                "triggeredActions": triggered_actions,
            }

        if choice.get("kind") == "chain_manifestation":
            if option == "decline":
                if not choice.get("optional"):
                    return "This Chain effect cannot be declined.", None
                self.rules_engine["pendingChoice"] = None
                self.queue_rules_chain_continuation(choice)
                return None, {
                    "kind": "chain_manifestation", "status": "declined",
                    "playerId": player_id, "fromZone": choice.get("fromZone"),
                    "sourceCardId": choice.get("sourceCardId"),
                }
            if not isinstance(card_ids, list) or len(card_ids) != 1 or not isinstance(card_ids[0], str):
                return "Choose one Manifestation to Chain.", None
            card_id = card_ids[0]
            zone = choice.get("fromZone")
            if card_id not in choice.get("_cardIds", []):
                return "The selected Manifestation is not eligible for this Chain effect.", None
            if card_id not in self.players[player_id]["zones"].get(zone, []):
                return "The selected Manifestation is no longer in the required zone.", None
            if self.card_rules.get(card_id, {}).get("type") != "manifestation":
                return "Only a Manifestation can be Chained.", None
            if zone == "hand" and self.rules_hands_are_immune():
                return "Cards in Hand are Immune to cards and effects.", None
            self.rules_engine["pendingChoice"] = None
            self.queue_rules_chain_continuation(choice)
            return self.chain_rules_manifestation(
                player_id, zone, card_id,
                placement=placement,
                win_destination=choice.get("winDestination"),
                action_id=choice.get("actionId"),
                source_card_id=choice.get("sourceCardId"),
                shuffle_after=bool(choice.get("shuffleAfter")),
                after_chain=choice.get("afterChain"),
                chain_abilities=choice.get("chainAbilities"),
                chain_controller_id=choice.get("controllerId"),
                action_targets=choice.get("_actionTargets"),
            )

        if choice.get("kind") != "discard_from_hand":
            return "Unknown card choice.", None
        if not isinstance(card_ids, list) or not all(isinstance(card_id, str) for card_id in card_ids):
            return "Choose the required number of cards.", None
        selected = list(card_ids)
        required = int(choice.get("count") or 0)
        if len(selected) > required or (len(selected) != required and not choice.get("upTo")):
            return "Choose the required number of cards.", None
        if choice.get("candidateCardIds") is not None:
            deck_zone = list(self.players[player_id]["zones"]["deck"])
            for card_id in selected:
                if card_id not in choice["candidateCardIds"] or card_id not in deck_zone:
                    return "A selected card is not available in your deck.", None
                deck_zone.remove(card_id)
            for card_id in selected:
                error, _owner_id = self.move_zone_card(
                    player_id, "deck", player_id, "hand", card_id, "top"
                )
                if error:
                    return error, None
            random.shuffle(self.players[player_id]["zones"]["deck"])
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "search_deck", "playerId": player_id,
                "count": len(selected), "cardIds": selected, "choiceId": choice_id,
                "actionId": choice.get("actionId"),
                "controllerId": choice.get("controllerId"),
                "sourceCardId": choice.get("sourceCardId"),
            }
        hand_remaining = list(self.players[player_id]["zones"]["hand"])
        for card_id in selected:
            if card_id not in hand_remaining:
                return "A selected card is no longer in your hand.", None
            hand_remaining.remove(card_id)
        if choice.get("requireManifestation") and any(
            self.card_rules.get(card_id, {}).get("type") != "manifestation"
            for card_id in selected
        ):
            return "Choose a manifestation from your hand.", None
        if choice.get("requireTypes") and any(
            self.card_rules.get(card_id, {}).get("type") not in choice["requireTypes"]
            for card_id in selected
        ):
            return "Choose a valid card type from your hand.", None
        destination = choice.get("destination")
        for card_id in selected:
            if destination == "interzone":
                moved = self.apply_rules_action_result({
                    "id": new_id(), "controllerId": player_id,
                    "source": {"cardId": choice.get("sourceCardId")},
                    "targets": [{
                        "kind": "zone_card", "containerId": player_id, "zone": "hand",
                        "cardId": card_id, "ownerId": player_id,
                    }],
                    "ability": {"result": {"kind": "move_zone_target_to_field_zone", "fieldZone": "interzone"}},
                })
                if (moved or {}).get("status") != "moved":
                    return "Your Interzone has no room for this Manifestation.", None
                continue
            error, _owner_id = self.move_zone_card(
                player_id, "hand", player_id, "exile" if destination == "exile" else "graveyard",
                card_id, "top",
            )
            if error:
                return error, None
        destroyed = None
        if choice.get("destroyTargetItemId") and selected:
            target_item = self.find_battlefield_item(choice["destroyTargetItemId"])
            revealed_base = int(self.card_rules.get(selected[0], {}).get("power") or 0)
            if (
                target_item is not None
                and self.rules_manifestation_base_power(target_item) <= revealed_base
            ):
                movement = self._rules_remove_field_item_by_effect(
                    target_item, target_item.get("ownerId"), "graveyard", "top", reason="destroy"
                )
                self.prune_rules_ongoing_effects()
                destroyed = {"itemId": target_item["id"], "status": movement.get("status")}
        weakened = None
        if choice.get("weakenTargetItemId"):
            weak_item = self.find_battlefield_item(choice["weakenTargetItemId"])
            base = int(self.card_rules.get(selected[0], {}).get("power") or 0) if selected else 0
            if weak_item is not None and base:
                counters = weak_item.setdefault("counters", {})
                counters["power"] = int(counters.get("power") or 0) - base
                weakened = {"itemId": weak_item["id"], "value": -base}
        power_gain = None
        if choice.get("sourcePowerPerDiscard") and selected:
            source_item = self.find_battlefield_item(choice.get("sourceItemId"))
            if source_item is not None:
                value = len(selected) * int(choice["sourcePowerPerDiscard"])
                self.rules_engine["ongoingEffects"].append({
                    "id": new_id(), "actionId": choice.get("actionId"),
                    "abilityId": "discard-wills-for-power",
                    "controllerId": choice.get("controllerId") or player_id,
                    "source": {
                        "cardId": choice.get("sourceCardId"),
                        "itemId": choice.get("sourceItemId"), "zone": "battlefield",
                    },
                    "target": {
                        "kind": "card", "itemId": source_item["id"],
                        "cardId": source_item.get("cardId"),
                        "ownerId": source_item.get("ownerId"),
                    },
                    "kind": "power_modifier", "value": value,
                    "duration": "until_end_of_turn",
                    "startedTurn": self.phase_tracker["turn"],
                })
                power_gain = {"itemId": source_item["id"], "value": value}
        points_lost = 0
        if choice.get("lossPerRemaining"):
            remaining = len(self.players[player_id]["zones"]["hand"])
            points_lost = -self.adjust_rules_score(
                player_id, -int(choice["lossPerRemaining"]) * remaining
            ) if remaining else 0
        drawn = 0
        requested_draw = max(0, min(int(choice.get("drawAfter") or 0), 50))
        if choice.get("drawByBasePower") and selected:
            requested_draw = max(0, min(int(self.card_rules.get(selected[0], {}).get("power") or 0), 50))
        for _index in range(min(requested_draw, len(self.players[player_id]["zones"]["deck"]))):
            card_id = self.players[player_id]["zones"]["deck"][0]
            error, _owner_id = self.move_zone_card(
                player_id, "deck", player_id, "hand", card_id, "bottom"
            )
            if error:
                break
            drawn += 1
        self.rules_engine["pendingChoice"] = None
        return None, {
            "kind": "discard_then_draw" if requested_draw else "discard",
            "playerId": player_id,
            "count": len(selected),
            "cardIds": selected,
            "drawCount": drawn,
            "choiceId": choice_id,
            "actionId": choice.get("actionId"),
            "controllerId": choice.get("controllerId"),
            "sourceCardId": choice.get("sourceCardId"),
            **({"destroyed": destroyed} if destroyed else {}),
            **({"weakened": weakened} if weakened else {}),
            **({"powerGain": power_gain} if power_gain else {}),
            **({"pointsLost": points_lost} if points_lost else {}),
        }

    def resolve_rules_top_action(self):
        action_stack = self.rules_engine["actionStack"]
        if not action_stack:
            return None
        resolved = action_stack.pop()
        power_before_resolution = {
            item.get("id"): self.rules_manifestation_characteristics(item)["power"]
            for item in self.battlefield
            if item.get("faceUp")
            and (
                self.card_rules.get(item.get("cardId"), {}).get("type") == "manifestation"
                or item.get("isTokenCard")
            )
        }
        source_resolution = self.resolve_rules_action_source(resolved)
        if source_resolution:
            resolved["sourceResolution"] = source_resolution
        triggered_actions = []
        if (
            source_resolution and source_resolution.get("destination") == "battlefield"
            and source_resolution.get("status") == "moved"
            and source_resolution.get("enteredBattlefield", True)
        ):
            triggered_actions = self.queue_rules_battlefield_entry_triggers(
                source_resolution.get("cardId"), resolved.get("controllerId"),
                source_resolution.get("itemId"), True,
                event_targets=resolved.get("targets"),
                defer=True,
            )
            entered_item = self.find_battlefield_item(
                source_resolution.get("itemId")
            )
            triggered_actions.extend(
                self.queue_rules_manifestation_entry_watchers(
                    entered_item, defer=True
                )
            )
            triggered_actions.extend(
                self.queue_rules_persistent_will_entry_watchers(
                    entered_item, defer=True
                )
            )
        if source_resolution and source_resolution.get("asSupport"):
            support_item = self.find_battlefield_item(source_resolution.get("itemId"))
            triggered_actions.extend(self.queue_rules_support_entry_triggers(
                support_item, played=True, from_zone=source_resolution.get("fromZone"),
                event_targets=resolved.get("targets"), defer=True,
            ))
            triggered_actions.extend(
                self.queue_rules_field_zone_entry_triggers(
                    support_item, "confrontation",
                    event_targets=resolved.get("targets"), defer=True
                )
            )
        target_rules = self.rules_action_target_rules(resolved)
        target_error = self.rules_ability_targets_error(
            target_rules,
            resolved.get("targets") or [],
            resolved.get("controllerId"),
            event_item_id=(
                (resolved.get("ability") or {}).get("trigger") or {}
            ).get("eventItemId"),
            source_item_id=(resolved.get("source") or {}).get("itemId"),
        ) if target_rules is not None else None
        if target_error:
            resolved["targetValidationError"] = target_error
            resolved["effectResult"] = {
                "kind": "invalid_targets",
                "status": "no_effect",
                "error": target_error,
            }
        else:
            effect_result = self.apply_rules_action_result(resolved)
            if effect_result:
                resolved["effectResult"] = effect_result
            ongoing_effects = self.create_rules_ongoing_effects(resolved)
            if ongoing_effects:
                resolved["ongoingEffects"] = ongoing_effects
                for effect in ongoing_effects:
                    if effect.get("kind") == "copy_power_effects":
                        triggered_actions.extend(
                            self.queue_rules_copied_entry_triggers(effect)
                        )
        state_actions = self.resolve_rules_state_actions(power_before_resolution)
        if state_actions["destroyed"]:
            resolved["stateActions"] = {
                "destroyed": state_actions["destroyed"],
            }
        if state_actions["replacements"]:
            resolved.setdefault("stateActions", {})["replacements"] = (
                state_actions["replacements"]
            )
        if state_actions["thresholdExiled"]:
            resolved.setdefault("stateActions", {})["thresholdExiled"] = (
                state_actions["thresholdExiled"]
            )
        triggered_actions.extend(state_actions["triggeredActions"])
        triggered_actions.extend(
            self.queue_rules_observed_event_triggers(defer=True)
        )
        if triggered_actions:
            self.queue_or_defer_rules_simultaneous_actions(triggered_actions)
        self.rules_engine["lastResolvedAction"] = resolved
        if action_stack:
            next_controller = action_stack[-1]["controllerId"]
            next_priority = self.other_rules_player_id(next_controller)
        else:
            normal_priority = (
                self.rules_lowest_confrontation_power_player()
                if self.current_phase_group() == "confrontation"
                else self.rules_engine.get("lastConfrontationWinnerId")
            )
            next_priority = (
                normal_priority if normal_priority in self.players
                else self.other_rules_player_id(resolved["controllerId"])
            )
        self.rules_engine["priorityPlayerId"] = next_priority
        return {
            "status": "resolved",
            "action": resolved,
            "triggeredActions": triggered_actions,
            "stackDepth": len(action_stack),
        }

    def resolve_rules_immediate_actions(self):
        resolved = []
        while (
            self.rules_engine["actionStack"]
            and self.rules_engine["actionStack"][-1].get("immediate")
            and not self.rules_engine.get("pendingChoice")
        ):
            result = self.resolve_rules_top_action()
            if result:
                resolved.append(result)
        return resolved

    def pass_rules_priority(self, player_id, passed=None):
        if not self.rules_engine["enabled"]:
            return "Assisted rules are not active.", None
        if self.ended or player_id not in self.players:
            return "Unable to pass priority.", None
        if len(self.players) < 2:
            return "Both players must join before using priority.", None
        if self.rules_engine.get("pendingChoice"):
            return "A required card choice must be completed first.", None
        if self.rules_recovery_mulligan_active():
            return "Complete the required Recovery Mulligan before playing.", None
        if passed is False:
            if self.rules_engine["priorityPasses"] == [player_id]:
                self.rules_engine["priorityPasses"] = []
                self.rules_engine["priorityPlayerId"] = player_id
                return None, {
                    "status": "cancelled",
                    "stackDepth": len(self.rules_engine["actionStack"]),
                }
            return "You have not passed priority.", None
        if self.rules_engine["priorityPlayerId"] != player_id:
            return "You do not have priority.", None

        previous_passes = self.rules_engine["priorityPasses"]
        if not previous_passes:
            self.rules_engine["priorityPasses"] = [player_id]
            self.rules_engine["priorityPlayerId"] = self.other_rules_player_id(player_id)
            return None, {
                "status": "passed",
                "stackDepth": len(self.rules_engine["actionStack"]),
            }

        self.rules_engine["priorityPasses"] = []
        action_stack = self.rules_engine["actionStack"]
        if action_stack:
            return None, self.resolve_rules_top_action()

        previous_phase_id = self.current_phase_id()
        sequence = self.phase_sequence()
        next_index = self.phase_tracker["index"] + 1
        started_new_turn = False
        rematch_started = False
        expired_essence_tokens = []
        rematch = self.rules_engine.get("rematchPending") or {}
        if (
            previous_phase_id == "resolution_move"
            and int(rematch.get("turn") or 0) == self.phase_tracker["turn"]
        ):
            next_index = ADVANCED_PHASES.index("confrontation_reaction")
            rematch_started = True
        if next_index >= len(sequence):
            next_index = 0
            expired_essence_tokens = self.expire_rules_excess_essence(
                self.phase_tracker["turn"]
            )
            self.phase_tracker["turn"] += 1
            started_new_turn = True
        self.phase_tracker["index"] = next_index
        expired_effects = self.prune_rules_ongoing_effects()
        self.prune_rules_play_restrictions()
        self.phase_passes.clear()
        self.rules_engine["priorityPlayerId"] = self.other_rules_player_id(player_id)
        if rematch_started:
            first_ids = {}
            for item_id in rematch.get("protectedItemIds") or []:
                item = self.find_battlefield_item(item_id)
                if item:
                    controller_id = item.get("controllerId") or item.get("ownerId")
                    first_ids[controller_id] = item_id
            self.rules_engine["firstManifestationItemIds"] = first_ids
            self.rules_engine["firstManifestationValidatedPlayerIds"] = list(first_ids)
            self.rules_engine["firstManifestationComplete"] = True
            self.rules_engine["firstManifestationTriggersQueued"] = True
            self.rules_engine["confrontationResult"] = None
            self.rules_engine["rematchPending"] = None
        revealed_item_ids = []
        if (
            previous_phase_id == "confrontation_before_revelation"
            and self.current_phase_id() == "confrontation_reveal"
        ):
            for selected_id in self.rules_engine["firstManifestationItemIds"].values():
                item = self.find_battlefield_item(selected_id)
                if item:
                    item["faceUp"] = True
                    revealed_item_ids.append(selected_id)
        automatic_recovery = None
        beginning_triggered_actions = []
        end_triggered_actions = []
        resolution_triggered_actions = []
        readied_item_ids = []
        if started_new_turn:
            self.expire_rules_temporary_suspensions(
                self.phase_tracker["turn"] - 1
            )
            self.rules_engine["handLimitEffects"] = [
                effect for effect in self.rules_engine.get(
                    "handLimitEffects"
                ) or []
                if int(effect.get("turn") or 0) >= self.phase_tracker["turn"]
            ]
            readied_item_ids = self.ready_rules_exhausted_cards()
            self.reset_rules_confrontation_turn()
            self.grant_rules_beginning_turn_permissions()
            beginning_triggered_actions = self.queue_rules_beginning_turn_triggers()
        if started_new_turn and not beginning_triggered_actions:
            self.phase_tracker["index"] = ADVANCED_PHASES.index("recovery_draw")
        if (
            self.current_phase_id() == "recovery_draw"
            and self.rules_engine["recoveryDrawTurn"] != self.phase_tracker["turn"]
        ):
            recovery_error, automatic_recovery = self.resolve_recovery_draw()
            if recovery_error:
                return recovery_error, None
        if self.current_phase_group() == "confrontation":
            lower_power_player = self.rules_lowest_confrontation_power_player()
            if lower_power_player:
                self.rules_engine["priorityPlayerId"] = lower_power_player
        if self.current_phase_id() == "end_triggers":
            end_triggered_actions = self.build_rules_end_turn_field_triggers()
            end_triggered_actions.extend(
                self.queue_rules_end_turn_memory_triggers(defer=True)
            )
            if end_triggered_actions:
                self.queue_rules_simultaneous_actions(end_triggered_actions)
        if self.current_phase_id() == "resolution_effects":
            resolution_triggered_actions = (
                self.queue_rules_resolution_memory_triggers()
            )
            resolution_triggered_actions.extend(
                self.queue_rules_confrontation_win_triggers()
            )
        confrontation_result = None
        if self.current_phase_id() == "resolution_compare":
            confrontation_result = self.prepare_rules_confrontation_result()
        elif self.current_phase_id() == "resolution_move":
            confrontation_result = self.begin_rules_confrontation_cleanup()
        return None, {
            "status": "advanced",
            "previousPhaseId": previous_phase_id,
            "phaseId": self.current_phase_id(),
            "turn": self.phase_tracker["turn"],
            "stackDepth": 0,
            "expiredEffectIds": [effect["id"] for effect in expired_effects],
            "confrontationResult": confrontation_result,
            "automaticRecovery": automatic_recovery,
            "beginningTriggeredActions": beginning_triggered_actions,
            "endTriggeredActions": end_triggered_actions,
            "resolutionTriggeredActions": resolution_triggered_actions,
            "readiedItemIds": readied_item_ids,
            "revealedItemIds": revealed_item_ids,
            "expiredEssenceTokenIds": [
                token["id"] for token in expired_essence_tokens
            ],
            "rematchStarted": rematch_started,
        }

    def reset_phase_tracker(self, return_stack_sources=True):
        if return_stack_sources:
            for action in self.rules_engine.get("actionStack") or []:
                source = action.get("source") or {}
                if not action.get("sourceOnStack"):
                    continue
                if source.get("zone") == "battlefield" and action.get("sourceBattlefieldItem"):
                    self.battlefield.append(action["sourceBattlefieldItem"])
                    continue
                owner_id = source.get("ownerId")
                zone = source.get("zone")
                container_id = source.get("containerId") or owner_id
                if owner_id in self.players and container_id in self.players and zone in {"hand", "graveyard"} and source.get("cardId"):
                    self.put_zone_card(container_id, zone, source["cardId"], owner_id, "bottom")
        self.phase_tracker["index"] = 0
        self.phase_tracker["turn"] = 1
        self.phase_passes.clear()
        self.rules_engine["recoveryDrawTurn"] = None
        self.rules_engine["recoveryMulliganTurn"] = None
        self.rules_engine["recoveryMulliganPlayerIds"] = []
        self.rules_engine["recoveryMulliganRequiredPlayerIds"] = []
        self.rules_engine["recoveryMulliganFailedPlayerIds"] = []
        self.rules_engine["beginningTriggersTurn"] = None
        self.rules_engine["beginningPermissionsTurn"] = None
        self.rules_engine["playPermissions"] = []
        self.rules_engine["deckConfirmedPlayerIds"] = []
        self.rules_engine["openingHandPlayerIds"] = []
        self.rules_engine["mulliganPlayerIds"] = []
        self.rules_engine["openingMulliganRequiredPlayerIds"] = []
        self.rules_engine["openingMulliganFailedPlayerIds"] = []
        self.rules_engine["readyPlayerIds"] = []
        self.rules_engine["outcome"] = None
        self.rules_engine["priorityPasses"] = []
        self.rules_engine["actionStack"] = []
        self.rules_engine["deferredSimultaneousActions"] = []
        self.rules_engine["lastResolvedAction"] = None
        self.rules_engine["ongoingEffects"] = []
        self.rules_engine["effectMemories"] = []
        self.rules_engine["supportEntries"] = []
        self.rules_engine["playRestrictions"] = []
        self.rules_engine["zoneEntryTurns"] = {}
        self.rules_engine["recentLimboEntries"] = []
        self.rules_engine["handLimitEffects"] = []
        self.rules_engine["pendingChoice"] = None
        self.rules_engine["rematchPending"] = None
        self.reset_rules_confrontation_turn()
        self.rules_engine["lastConfrontationWinnerId"] = None
        self.rules_engine["priorityPlayerId"] = next(iter(self.players), None)

    def serialize_phase_tracker(self):
        return {
            **self.phase_tracker,
            "passedPlayerIds": [pid for pid in self.players if pid in self.phase_passes],
        }

    # -- zone permissioning --------------------------------------------
    def can_view_zone(self, viewer_id, role, owner_id, zone):
        role = normalize_role(role)
        if zone in SHARED_ZONES:
            return True
        # private zone: the owner, or a trusted read-only observer, but never another player
        if role in PRIVILEGED_VIEW_ROLES:
            return True
        return viewer_id == owner_id

    def can_act_on_zone(self, actor_id, role, owner_id, zone):
        role = normalize_role(role)
        if role in READ_ONLY_ROLES:
            return False
        if zone in SHARED_ZONES:
            return True
        return actor_id == owner_id

    # -- battlefield helpers --------------------------------------------
    def find_battlefield_item(self, item_id):
        for item in self.battlefield:
            if item["id"] == item_id:
                return item
        return None

    def find_token(self, token_id):
        for token in self.tokens:
            if token["id"] == token_id:
                return token
        return None

    def copy_card(self, actor_id, is_observer, item_id=None, source_owner=None, source_zone=None,
                  card_id=None, x=None, y=None):
        if is_observer:
            return "Observers cannot act.", None
        source = self.find_battlefield_item(item_id)
        if source is not None:
            if source.get("isTokenCard") or source.get("isCopy"):
                return "Only a real card can be copied.", None
            if not source.get("faceUp") or not source.get("cardId"):
                return "A face-down card cannot be copied.", None
            card_id = source["cardId"]
            rarity = source.get("rarity")
            default_x, default_y = source["x"] + 24, source["y"] + 24
            rotation = float(source.get("rotation") or 0)
        else:
            source_owner = source_owner or actor_id
            if source_zone not in ALL_ZONES:
                return "Unknown source zone.", None
            if not self.can_act_on_zone(actor_id, is_observer, source_owner, source_zone):
                return "You cannot copy from that zone.", None
            source_player = self.players.get(source_owner)
            if source_player is None or card_id not in source_player["zones"][source_zone]:
                return "Card not found in that zone.", None
            card_owner = self.card_owner_in_zone(source_owner, source_zone, card_id)
            rarity = (self.players.get(card_owner) or {}).get("cardRarities", {}).get(card_id)
            default_x, default_y = 0, 0
            rotation = 0.0
        item = {
            "id": new_id(), "ownerId": actor_id, "cardId": card_id,
            "x": float(default_x if x is None else x),
            "y": float(default_y if y is None else y),
            "faceUp": True, "rotation": rotation, "counters": {},
            "rarity": rarity, "stackedOn": None, "isCopy": True,
        }
        if self.rules_engine["enabled"] and self.card_rules.get(card_id, {}).get("type") == "manifestation":
            if self.current_phase_group() == "confrontation":
                self.mark_rules_confrontation_entry(item)
            else:
                item["fieldZone"] = "interzone"
                self.mark_rules_interzone_entry(item)
        self.battlefield.append(item)
        return None, item

    # -- serialization (permission-filtered per viewer) ------------------
    def serialize_for(self, viewer_id, role):
        role = normalize_role(role)
        can_view_hidden = role in PRIVILEGED_VIEW_ROLES
        pending_choice = self.rules_engine.get("pendingChoice")
        pending_choice_view = (
            {
                key: value for key, value in pending_choice.items()
                if not key.startswith("_")
            }
            if pending_choice else None
        )
        if (
            pending_choice_view
            and pending_choice.get("kind") in {
                "deck_reorder", "peek_top_card", "guess_top_card",
                "draw_replacement",
                "suspend_hand_will", "chain_manifestation",
            }
            and viewer_id != pending_choice.get("playerId")
            and not can_view_hidden
        ):
            pending_choice_view.pop("cardId", None)
            pending_choice_view.pop("cardIds", None)
            if "groups" in pending_choice_view:
                pending_choice_view["groups"] = [{
                    key: value for key, value in group.items()
                    if key != "cardIds"
                } for group in pending_choice_view["groups"]]
        if (
            pending_choice_view
            and "candidateCardIds" in pending_choice_view
            and viewer_id != pending_choice.get("playerId")
            and not can_view_hidden
        ):
            pending_choice_view.pop("candidateCardIds", None)
        players_view = {}
        for pid, player in self.players.items():
            zones_view = {}
            for zone, cards in player["zones"].items():
                if self.can_view_zone(viewer_id, role, pid, zone):
                    zones_view[zone] = {
                        "cards": list(cards),
                        "owners": {card_id: self.card_owner_in_zone(pid, zone, card_id) for card_id in cards},
                    }
                else:
                    zones_view[zone] = {"count": len(cards)}
            players_view[pid] = {
                "id": pid,
                "name": player["name"],
                "connected": player["connected"],
                "score": player["score"],
                "seat": player["seat"],
                "zones": zones_view,
                "cardRarities": dict(player.get("cardRarities", {})) if can_view_hidden or pid == viewer_id else {},
                "deckDefinition": player.get("deckDefinition") if can_view_hidden or pid == viewer_id else None,
                "sideboard": list(player.get("sideboard", [])) if can_view_hidden or pid == viewer_id else {"count": len(player.get("sideboard", []))},
                "activity": player.get("activity"),
            }

        battlefield_view = []
        for item in self.battlefield:
            # the owner sees their own hidden cards; a trusted observer sees everything too
            can_peek = can_view_hidden or item["ownerId"] == viewer_id
            if item["faceUp"] or can_peek:
                card_id = item["cardId"]
            else:
                card_id = None
            entry = {
                "id": item["id"],
                "ownerId": item["ownerId"],
                "cardId": card_id,
                "x": item["x"],
                "y": item["y"],
                "faceUp": item["faceUp"],
                "rotation": item["rotation"],
                "counters": item["counters"],
            }
            if item.get("fieldZone"):
                entry["fieldZone"] = item["fieldZone"]
            if item.get("isSupport"):
                entry["isSupport"] = True
            if item.get("supportUntilTurn"):
                entry["supportUntilTurn"] = item["supportUntilTurn"]
            if (
                self.rules_engine["enabled"] and item.get("faceUp")
                and item.get("fieldZone") == "interzone"
                and self.card_rules.get(item.get("cardId"), {}).get("type") == "manifestation"
                and self.rules_card_can_enter_support(item)
            ):
                entry["canEnterSupport"] = True
            if item.get("isChained"):
                entry["isChained"] = True
            controller_id = self.rules_item_controller_id(item)
            if controller_id and controller_id != item.get("ownerId"):
                entry["controllerId"] = controller_id
            if item.get("temperamentOverride") in RULES_TEMPERAMENTS:
                entry["temperamentOverride"] = item["temperamentOverride"]
            if item.get("confrontationOrder"):
                entry["confrontationOrder"] = item["confrontationOrder"]
            if item.get("effectsDisabled"):
                entry["effectsDisabled"] = True
            if item.get("isTokenCard"):
                entry["isTokenCard"] = True
                entry["temperament"] = item["temperament"]
                entry["power"] = item["power"]
            elif item.get("isCopy"):
                entry["isCopy"] = True
                if card_id is not None and item.get("rarity"):
                    entry["rarity"] = item["rarity"]
            elif card_id is not None and item.get("rarity"):
                entry["rarity"] = item["rarity"]
            if (
                self.rules_engine["enabled"] and item.get("faceUp")
                and (item.get("isTokenCard") or self.card_rules.get(item.get("cardId"), {}).get("type") == "manifestation")
            ):
                entry["effectivePower"] = self.rules_manifestation_characteristics(item)["power"]
            if item.get("stackedOn"):
                entry["stackedOn"] = item["stackedOn"]
                entry["stackOffsetX"] = item["stackOffsetX"]
                entry["stackOffsetY"] = item["stackOffsetY"]
            battlefield_view.append(entry)

        return {
            "type": "state",
            "players": players_view,
            "battlefield": battlefield_view,
            "tokens": list(self.tokens),
            "strokes": list(self.strokes),
            "ended": self.ended,
            "mode": self.mode,
            "tournament": self.tournament_summary(role) if self.mode == "tournament" else None,
            "deckPolicy": {
                "enabled": self.ban_list_enabled,
                "policy": self.tournament_policy if self.ban_list_enabled else {"bannedCardIds": [], "restrictedGroups": []},
            },
            "phaseTracker": self.serialize_phase_tracker(),
            "rulesEngine": {
                "enabled": self.rules_engine["enabled"],
                "deckConfirmedPlayerIds": list(self.rules_engine["deckConfirmedPlayerIds"]),
                "openingHandPlayerIds": list(self.rules_engine["openingHandPlayerIds"]),
                "mulliganPlayerIds": list(self.rules_engine["mulliganPlayerIds"]),
                "openingMulliganRequiredPlayerIds": list(self.rules_engine["openingMulliganRequiredPlayerIds"]),
                "openingMulliganFailedPlayerIds": list(self.rules_engine["openingMulliganFailedPlayerIds"]),
                "readyPlayerIds": list(self.rules_engine["readyPlayerIds"]),
                "recoveryMulliganTurn": self.rules_engine["recoveryMulliganTurn"],
                "recoveryMulliganPlayerIds": list(self.rules_engine["recoveryMulliganPlayerIds"]),
                "recoveryMulliganRequiredPlayerIds": list(self.rules_engine["recoveryMulliganRequiredPlayerIds"]),
                "recoveryMulliganFailedPlayerIds": list(self.rules_engine["recoveryMulliganFailedPlayerIds"]),
                "beginningTriggersTurn": self.rules_engine["beginningTriggersTurn"],
                "beginningPermissionsTurn": self.rules_engine["beginningPermissionsTurn"],
                "playPermissions": [dict(entry) for entry in self.rules_engine["playPermissions"]],
                "supportEntries": [dict(entry) for entry in self.rules_engine["supportEntries"]],
                "playRestrictions": [dict(entry) for entry in self.rules_engine["playRestrictions"]],
                "zoneEntryTurns": dict(self.rules_engine["zoneEntryTurns"]),
                "recentLimboEntries": [
                    dict(entry)
                    for entry in self.rules_engine.get(
                        "recentLimboEntries"
                    ) or []
                    if int(entry.get("turn") or 0)
                    == self.phase_tracker["turn"]
                ],
                "handLimitEffects": [
                    dict(entry) for entry in self.rules_engine["handLimitEffects"]
                ],
                "outcome": self.rules_engine["outcome"],
                "priorityPlayerId": self.rules_engine["priorityPlayerId"],
                "priorityPasses": list(self.rules_engine["priorityPasses"]),
                "actionStack": list(self.rules_engine["actionStack"]),
                "lastResolvedAction": self.rules_engine["lastResolvedAction"],
                "ongoingEffects": list(self.rules_engine["ongoingEffects"]),
                "effectMemories": [
                    {
                        "id": memory.get("id"),
                        "ownerId": memory.get("ownerId"),
                        "controllerId": memory.get("controllerId"),
                        "cardId": memory.get("cardId"),
                        "kind": memory.get("kind"),
                        "createdTurn": memory.get("createdTurn"),
                        "data": dict(memory.get("data") or {}),
                    }
                    for memory in self.rules_engine.get("effectMemories") or []
                ],
                "suspendedCards": [{
                    "id": entry.get("id"),
                    "ownerId": entry.get("ownerId"),
                    "cardId": (
                        entry.get("cardId")
                        if entry.get("fromZone") == "battlefield"
                        or viewer_id == entry.get("playableByPlayerId")
                        or self.can_view_zone(
                            viewer_id, role,
                            entry.get("fromContainerId") or entry.get("ownerId"),
                            entry.get("fromZone"),
                        )
                        else None
                    ),
                    "sourceEffectId": entry.get("sourceEffectId"),
                    "playableByPlayerId": entry.get("playableByPlayerId"),
                    "returnTurn": entry.get("returnTurn"),
                } for entry in self.rules_engine.get("suspendedCards") or []],
                "pendingChoice": pending_choice_view,
                "firstManifestationItemIds": dict(self.rules_engine["firstManifestationItemIds"]),
                "firstManifestationValidatedPlayerIds": list(self.rules_engine["firstManifestationValidatedPlayerIds"]),
                "firstManifestationComplete": self.rules_engine["firstManifestationComplete"],
                "confrontationResult": dict(self.rules_engine["confrontationResult"]) if self.rules_engine["confrontationResult"] else None,
                "lastConfrontationWinnerId": self.rules_engine["lastConfrontationWinnerId"],
            },
            # a small tail of the action log, piggybacked on every state sync so
            # the opponent-row mini activity feed updates live without a
            # separate poll — the full log (request_log) is still the
            # authoritative, complete history used for the debug/download panel
            "recentLog": [self.log_entry_for_role(entry, role) for entry in self.log[-30:]],
        }

    # -- first assisted-rules slice ------------------------------------
    def _draw_player_to_limit(self, player_id, hand_limit=7):
        player = self.players[player_id]
        needed = max(0, hand_limit - len(player["zones"]["hand"]))
        drawn = []
        for _ in range(min(needed, len(player["zones"]["deck"]))):
            card_id = player["zones"]["deck"][0]
            error, _ = self.move_zone_card(player_id, "deck", player_id, "hand", card_id, "bottom")
            if error:
                return error, drawn
            drawn.append(card_id)
        return None, drawn

    def rules_opening_hand_limit(self, player_id, default_limit=7, timing="before_draw"):
        """Return the hand size used by the opening sequence.

        The timing argument is deliberately explicit: encoded effects that alter
        the opening hand can later be applied before or after the first draw
        without duplicating the sequence.  No currently encoded card changes the
        limit, so the rulebook default remains authoritative today.
        """
        _ = player_id, timing
        return max(0, int(default_limit))

    def rules_card_can_be_first_manifestation(self, card_id):
        metadata = self.card_rules.get(card_id, {})
        is_manifestation = card_id in self.manifestation_ids or metadata.get("type") == "manifestation"
        # Inner Deserts art is already playable, but its machine-readable card
        # types are still placeholders. Assisted rules must not turn missing
        # metadata into a false mandatory Mulligan. Such a card is accepted as
        # a manually verified first Manifestation until the catalog is typed.
        manually_verified_placeholder = bool(metadata.get("placeholder"))
        return bool(
            (is_manifestation or manually_verified_placeholder)
            and metadata.get("canBeFirstManifestation", True)
        )

    def rules_opening_hand_is_playable(self, player_id):
        player = self.players.get(player_id)
        return bool(player and any(
            self.rules_card_can_be_first_manifestation(card_id)
            for card_id in player["zones"]["hand"]
        ))

    def _draw_rules_opening_hand(self, player_id, default_limit=7):
        before_limit = self.rules_opening_hand_limit(player_id, default_limit, "before_draw")
        error, drawn = self._draw_player_to_limit(player_id, before_limit)
        if error:
            return error, None
        after_limit = self.rules_opening_hand_limit(player_id, before_limit, "after_draw")
        if after_limit != before_limit:
            error, adjusted = self._draw_player_to_limit(player_id, after_limit)
            if error:
                return error, None
            drawn.extend(adjusted)
        return None, {"count": len(drawn), "handLimit": after_limit}

    def rules_recovery_hand_limit(self, player_id, default_limit=7, timing="before_draw"):
        """Return the hand size used by a normal-turn Recovery draw.

        Keeping the before/after timing explicit lets encoded effects alter the
        limit later without making the clients responsible for draw order.
        """
        limit = self.rules_hand_limit(player_id, default_limit)
        if timing == "before_draw":
            extra = 0
            for source in self.rules_active_passive_sources(
                "extra_recovery_draw_per_empty_interzone"
            ):
                if (
                    self.rules_item_controller_id(source) == player_id
                    and self.rules_field_zone(source) == "interzone"
                ):
                    occupied = self.rules_interzone_slot_count(player_id)
                    extra += max(0, 3 - occupied)
            limit += extra
        return max(0, limit)

    def _draw_rules_recovery_hand(self, player_id, default_limit=7):
        before_limit = self.rules_recovery_hand_limit(player_id, default_limit, "before_draw")
        error, drawn = self._draw_player_to_limit(player_id, before_limit)
        if error:
            return error, None
        return None, {"count": len(drawn), "handLimit": before_limit}

    def _start_rules_match_after_opening(self):
        self.phase_tracker["index"] = ADVANCED_PHASES.index("recovery_end")
        self.phase_passes.clear()
        self.rules_engine["priorityPasses"] = []
        first_player = self.player_for_seat(0) or next(iter(self.players.values()), None)
        self.rules_engine["priorityPlayerId"] = first_player.get("id") if first_player else None

    def prepare_rules_opening_hands(self, hand_limit=7):
        """Draw and validate both opening hands as one server-owned sequence."""
        if not self.rules_pregame_active():
            return "The opening-hand setup is no longer active.", None
        player_ids = list(self.players)
        confirmed_ids = self.rules_engine["deckConfirmedPlayerIds"]
        if len(player_ids) < NUM_SEATS or not all(pid in confirmed_ids for pid in player_ids):
            return None, {"prepared": False, "draws": {}, "started": False}

        draws = {}
        required = self.rules_engine["openingMulliganRequiredPlayerIds"]
        ready = self.rules_engine["readyPlayerIds"]
        for player_id in player_ids:
            if player_id not in self.rules_engine["openingHandPlayerIds"]:
                error, result = self._draw_rules_opening_hand(player_id, hand_limit)
                if error:
                    return error, None
                self.rules_engine["openingHandPlayerIds"].append(player_id)
                draws[player_id] = result["count"]
            if self.rules_opening_hand_is_playable(player_id):
                if player_id in required:
                    required.remove(player_id)
            elif player_id not in required and player_id not in self.rules_engine["mulliganPlayerIds"]:
                required.append(player_id)

        started = not required and all(player_id in ready for player_id in player_ids)
        if started:
            self._start_rules_match_after_opening()
        return None, {
            "prepared": True,
            "draws": draws,
            "mulliganRequiredPlayerIds": list(required),
            "started": started,
        }

    def draw_opening_hand(self, player_id, hand_limit=7):
        """Draw one player's initial hand without invoking Recovery or game end."""
        if not self.rules_engine["enabled"]:
            return "Assisted rules are not active.", None
        if self.ended:
            return "The game has already ended.", None
        if player_id not in self.players:
            return "Unknown player.", None
        if self.phase_tracker["turn"] != 1 or self.current_phase_id() != "recovery_start":
            return "Opening hands can only be drawn during the first Recovery start step.", None
        player_ids = list(self.players)
        confirmed_ids = self.rules_engine["deckConfirmedPlayerIds"]
        if len(player_ids) < NUM_SEATS or not all(pid in confirmed_ids for pid in player_ids):
            return "Both players must validate their decks before drawing opening hands.", None
        if player_id in self.rules_engine["openingHandPlayerIds"]:
            return "You have already drawn your opening hand.", None

        error, result = self._draw_rules_opening_hand(player_id, hand_limit)
        if error:
            return error, None
        self.rules_engine["openingHandPlayerIds"].append(player_id)
        return None, result

    def rules_pregame_active(self):
        return bool(
            self.rules_engine["enabled"]
            and not self.ended
            and self.phase_tracker["turn"] == 1
            and self.current_phase_id() == "recovery_start"
        )

    def casual_deck_setup_active(self):
        return bool(
            self.mode == "casual"
            and not self.rules_engine["enabled"]
            and not self.ended
            and self.phase_tracker["turn"] == 1
            and self.current_phase_group() == "recovery"
            and not self.rules_engine["openingHandPlayerIds"]
        )

    def reset_rules_pregame_player(self, player_id):
        """Invalidate only this player's setup choices after a deck replacement."""
        if not (self.rules_pregame_active() or self.casual_deck_setup_active()):
            return
        for key in (
            "deckConfirmedPlayerIds", "openingHandPlayerIds", "mulliganPlayerIds",
            "openingMulliganRequiredPlayerIds", "openingMulliganFailedPlayerIds", "readyPlayerIds",
        ):
            self.rules_engine[key] = [pid for pid in self.rules_engine[key] if pid != player_id]

    def confirm_casual_deck(self, player_id, hand_limit=7):
        """Validate a normal-game deck and draw both opening hands once ready."""
        if not self.casual_deck_setup_active():
            return "Deck selection is locked after the opening hands are drawn.", None
        if player_id not in self.players:
            return "Unknown player.", None
        error = self.deck_validation_error(player_id)
        if error:
            return error, None
        confirmed_ids = self.rules_engine["deckConfirmedPlayerIds"]
        if player_id not in confirmed_ids:
            confirmed_ids.append(player_id)
        player_ids = list(self.players)
        if len(player_ids) < NUM_SEATS or not all(pid in confirmed_ids for pid in player_ids):
            return None, {"confirmed": True, "draws": {}, "started": False}

        draws = {}
        for opening_player_id in player_ids:
            error, drawn = self._draw_player_to_limit(opening_player_id, hand_limit)
            if error:
                return error, None
            draws[opening_player_id] = len(drawn)
            self.rules_engine["openingHandPlayerIds"].append(opening_player_id)
        return None, {"confirmed": True, "draws": draws, "started": True}

    def deck_validation_error(self, player_id):
        player = self.players.get(player_id)
        definition = player.get("deckDefinition") if player else None
        if not isinstance(definition, dict):
            return "Import a deck before validating it."
        main_cards = []
        sideboard_cards = []
        for group in definition.get("groups") or []:
            kind = str(group.get("kind") or "").lower()
            if kind == "maybeboard":
                continue
            (sideboard_cards if kind == "sideboard" else main_cards).extend(group.get("cardIds") or [])
        policy = self.tournament_policy if self.ban_list_enabled else None
        return validate_tournament_deck(
            main_cards, sideboard_cards, self.card_points or {}, policy, self.card_labels,
            limit_bonus=self.rules_deck_limit_bonus(main_cards),
        )

    def rules_deck_limit_bonus(self, card_ids):
        return sum(
            int(self.card_rules.get(card_id, {}).get("constructionLimitBonus") or 0)
            for card_id in card_ids
        )

    def set_rules_deck_confirmed(self, player_id, confirmed=True):
        if not self.rules_pregame_active():
            return "Deck selection is locked after the match begins.", None
        if player_id not in self.players:
            return "Unknown player.", None
        confirmed_ids = self.rules_engine["deckConfirmedPlayerIds"]
        if not confirmed:
            player_ids = list(self.players)
            if len(player_ids) >= NUM_SEATS and all(pid in confirmed_ids for pid in player_ids):
                return "Decks are locked after both players validate.", None
            self.rules_engine["deckConfirmedPlayerIds"] = [pid for pid in confirmed_ids if pid != player_id]
            return None, {"confirmed": False}
        error = self.deck_validation_error(player_id)
        if error:
            return error, None
        if player_id in confirmed_ids:
            return None, {"confirmed": True, "opening": None, "alreadyConfirmed": True}
        if player_id not in confirmed_ids:
            confirmed_ids.append(player_id)
        error, opening = self.prepare_rules_opening_hands()
        if error:
            return error, None
        return None, {"confirmed": True, "opening": opening}

    def rules_first_manifestation_active(self):
        return bool(
            self.rules_engine["enabled"]
            and not self.ended
            and self.current_phase_id() == "confrontation_choose"
            and not self.rules_engine["firstManifestationComplete"]
        )

    def register_first_manifestation(self, player_id, item):
        if not self.rules_first_manifestation_active():
            return None
        if item.get("ownerId") != player_id or not self.rules_card_can_be_first_manifestation(item.get("cardId")):
            return "Your first play must be one of your Manifestations."
        selected = self.rules_engine["firstManifestationItemIds"]
        if player_id in selected:
            return "You have already chosen your first Manifestation."
        item["faceUp"] = False
        self.mark_rules_confrontation_entry(item)
        selected[player_id] = item["id"]
        return None

    def set_rules_field_zone(self, player_id, item_id, field_zone):
        if not self.rules_engine["enabled"]:
            return "Assisted rules are not active.", None
        if field_zone != "confrontation" or self.current_phase_id() != "confrontation_reaction":
            return "A Manifestation can enter Support only during Reaction.", None
        item = self.find_battlefield_item(item_id)
        if item is None or self.rules_item_controller_id(item) != player_id:
            return "This Manifestation is not under your control.", None
        if self.card_rules.get(item.get("cardId"), {}).get("type") != "manifestation":
            return "Only a Manifestation can enter the confrontation.", None
        if self.rules_support_entry_locked(player_id):
            return "Manifestations cannot be put in Support until the end of the turn.", None
        if self.rules_item_zone_locked(item):
            return "This Manifestation cannot change zone until the end of the turn.", None
        source_field_zone = self.rules_field_zone(item)
        if source_field_zone not in {"interzone", "stalemate"}:
            return "This Manifestation is not in a zone from which it can enter Support.", None
        if self.rules_engine.get("priorityPlayerId") != player_id:
            return "You do not have priority.", None
        if not self.rules_card_can_enter_support(item, source_field_zone):
            return "This Manifestation does not currently have Support.", None
        self.mark_rules_support_entry(item)
        return None, {
            "itemId": item_id, "cardId": item.get("cardId"),
            "fieldZone": "confrontation", "asSupport": True,
        }

    def validate_first_manifestation(self, player_id, validated=True):
        if not self.rules_first_manifestation_active():
            return "The simultaneous first Manifestation step is not active.", None
        confirmed_players = self.rules_engine["firstManifestationValidatedPlayerIds"]
        if not validated:
            selected_item = self.find_battlefield_item(
                self.rules_engine["firstManifestationItemIds"].get(player_id)
            )
            if selected_item and selected_item.get("persistedFirst"):
                return "A Persisted First Manifestation is already locked in.", None
            opponent_confirmed = any(
                confirmed_id != player_id for confirmed_id in confirmed_players
            )
            if opponent_confirmed:
                return "The opponent has already validated their first Manifestation.", None
            if player_id in confirmed_players:
                confirmed_players.remove(player_id)
            return None, {"validated": False, "revealed": False}
        item_id = self.rules_engine["firstManifestationItemIds"].get(player_id)
        if not item_id or not self.find_battlefield_item(item_id):
            return "Play a Manifestation face down before validating.", None
        if player_id not in confirmed_players:
            confirmed_players.append(player_id)
        player_ids = list(self.players)
        revealed = len(player_ids) >= NUM_SEATS and all(pid in confirmed_players for pid in player_ids)
        if revealed:
            self.rules_engine["firstManifestationComplete"] = True
            self.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_before_revelation")
            self.rules_engine["priorityPasses"] = []
            first_player = self.player_for_seat(0) or next(iter(self.players.values()), None)
            last_winner = self.rules_engine.get("lastConfrontationWinnerId")
            self.rules_engine["priorityPlayerId"] = (
                last_winner if last_winner in self.players
                else (first_player.get("id") if first_player else None)
            )
        return None, {"validated": True, "selectionComplete": revealed, "revealed": False}

    def mulligan_opening_hand(self, player_id, hand_limit=7):
        if not self.rules_pregame_active():
            return "Mulligans are only available before both players are ready.", None
        if player_id not in self.players:
            return "Unknown player.", None
        if player_id not in self.rules_engine["openingHandPlayerIds"]:
            return "Draw your opening hand before taking a mulligan.", None
        if player_id in self.rules_engine["mulliganPlayerIds"]:
            return "You have already taken your opening mulligan.", None
        if player_id in self.rules_engine["readyPlayerIds"]:
            return "Your opening hand is already confirmed.", None

        player = self.players[player_id]
        mulligan_required = player_id in self.rules_engine["openingMulliganRequiredPlayerIds"]
        while player["zones"]["hand"]:
            card_id = player["zones"]["hand"][0]
            error, _owner_id = self.move_zone_card(
                player_id, "hand", player_id, "deck", card_id, "bottom"
            )
            if error:
                return error, None
        random.shuffle(player["zones"]["deck"])
        error, draw_result = self._draw_rules_opening_hand(player_id, hand_limit)
        if error:
            return error, None
        player["score"] = int(player.get("score") or 0) - 10
        self.rules_engine["mulliganPlayerIds"].append(player_id)
        if mulligan_required:
            self.rules_engine["openingMulliganRequiredPlayerIds"].remove(player_id)
        playable = self.rules_opening_hand_is_playable(player_id)
        if not playable and player_id not in self.rules_engine["openingMulliganFailedPlayerIds"]:
            self.rules_engine["openingMulliganFailedPlayerIds"].append(player_id)

        remaining = self.rules_engine["openingMulliganRequiredPlayerIds"]
        failed = self.rules_engine["openingMulliganFailedPlayerIds"]
        started = False
        outcome = None
        if not remaining:
            if failed:
                winner_ids = [pid for pid in self.players if pid not in failed]
                outcome = {
                    "reason": "invalid_opening_hand_after_mulligan",
                    "loserIds": list(failed),
                    "winnerIds": winner_ids,
                    "draw": len(winner_ids) != 1,
                }
                self.rules_engine["outcome"] = outcome
                self.rules_engine["priorityPlayerId"] = None
                self.ended = True
            elif all(
                candidate_id in self.rules_engine["readyPlayerIds"]
                for candidate_id in self.players
            ):
                started = True
                self._start_rules_match_after_opening()
        return None, {
            "count": draw_result["count"],
            "handLimit": draw_result["handLimit"],
            "scoreCost": 10,
            "score": player["score"],
            "required": mulligan_required,
            "playable": playable,
            "started": started,
            "remainingMulliganPlayerIds": list(remaining),
            "outcome": outcome,
        }

    def set_rules_ready(self, player_id):
        if not self.rules_pregame_active():
            return "Opening hands can only be confirmed before the match begins.", None
        if player_id not in self.players:
            return "Unknown player.", None
        if player_id not in self.rules_engine["openingHandPlayerIds"]:
            return "Draw your opening hand before confirming it.", None
        if player_id in self.rules_engine["openingMulliganRequiredPlayerIds"]:
            return "Complete the required opening Mulligan before confirming your hand.", None
        if player_id in self.rules_engine["openingMulliganFailedPlayerIds"]:
            return "This opening hand cannot be confirmed.", None
        if not self.rules_opening_hand_is_playable(player_id):
            return "Your opening hand needs a playable Manifestation.", None
        ready = self.rules_engine["readyPlayerIds"]
        if player_id not in ready:
            ready.append(player_id)
        player_ids = list(self.players)
        started = (
            len(player_ids) >= NUM_SEATS
            and not self.rules_engine["openingMulliganRequiredPlayerIds"]
            and all(pid in ready for pid in player_ids)
        )
        if started:
            self._start_rules_match_after_opening()
        return None, {"ready": True, "started": started}

    def rules_end_game_points(self, player_id):
        """Points from cards that score "at the end of the game"."""
        def end_game_results(card_id):
            for ability in self.card_rules.get(card_id, {}).get("triggeredAbilities") or []:
                if (ability.get("trigger") or {}).get("event") == "end_of_game":
                    yield ability.get("result") or {}

        total = 0
        player = self.players[player_id]
        for card_id in player["zones"]["deck"]:
            for result in end_game_results(card_id):
                if result.get("kind") == "final_deck_points":
                    total += int(result.get("value") or 0)
        for container in self.players.values():
            owners = container["zoneOwners"].get("receptacle", {})
            for card_id in container["zones"]["receptacle"]:
                if container["id"] != player_id:
                    continue
                if owners.get(card_id, container["id"]) == player_id:
                    continue
                for result in end_game_results(card_id):
                    if result.get("kind") != "final_vessel_penalty":
                        continue
                    limit = int(result.get("maxBasePower") or 0)
                    count = sum(
                        1 for other_id in container["zones"]["receptacle"]
                        if self.card_rules.get(other_id, {}).get("type") == "manifestation"
                        and int(self.card_rules.get(other_id, {}).get("power") or 0) <= limit
                    )
                    total -= int(result.get("value") or 0) * count
        return total

    def calculate_final_scores(self):
        scores = {}
        for player_id, player in self.players.items():
            vessel_cards = player["zones"]["receptacle"]
            card_points = self.card_points or {}
            vessel_points = sum(card_points.get(card_id, 0) for card_id in vessel_cards)
            remaining_manifestations = sum(
                1 for card_id in player["zones"]["deck"] if card_id in self.manifestation_ids
            )
            effect_points = int(player.get("score") or 0)
            deck_bonus = remaining_manifestations * 5
            end_game_points = self.rules_end_game_points(player_id)
            scores[player_id] = {
                "vesselPoints": vessel_points,
                "effectPoints": effect_points,
                "remainingManifestations": remaining_manifestations,
                "deckBonus": deck_bonus,
                "endGamePoints": end_game_points,
                "total": vessel_points + effect_points + deck_bonus + end_game_points,
            }
        alternate_players = {
            player_id for player_id, player in self.players.items()
            if any(
                passive.get("kind") == "negative_score_victory"
                for card_id in player["zones"]["graveyard"]
                for passive in self.card_rules.get(
                    card_id, {}
                ).get("passiveEffects") or []
            )
        }
        alternate_winners = [
            player_id for player_id in alternate_players
            if scores[player_id]["total"] <= -130
        ]
        if alternate_winners:
            winner_ids = alternate_winners
        else:
            eligible = {
                player_id: score for player_id, score in scores.items()
                if player_id not in alternate_players
            }
            best = max(
                (score["total"] for score in eligible.values()),
                default=0,
            )
            winner_ids = [
                player_id for player_id, score in eligible.items()
                if score["total"] == best
            ]
        return {
            "reason": "incomplete_recovery_hand",
            "scores": scores,
            "winnerIds": winner_ids,
            "draw": len(winner_ids) != 1,
            "alternateVictoryPlayerIds": alternate_winners,
            "normalVictoryExcludedPlayerIds": list(alternate_players),
        }

    def rules_recovery_mulligan_active(self):
        return bool(
            self.rules_engine["enabled"]
            and not self.ended
            and self.current_phase_id() == "recovery_draw"
            and self.rules_engine["recoveryMulliganTurn"] == self.phase_tracker["turn"]
            and self.rules_engine["recoveryMulliganRequiredPlayerIds"]
        )

    def _advance_rules_after_recovery(self):
        self.phase_tracker["index"] = ADVANCED_PHASES.index("recovery_end")
        self.phase_passes.clear()
        self.rules_engine["priorityPasses"] = []
        first_player = self.player_for_seat(0) or next(iter(self.players.values()), None)
        last_winner = self.rules_engine.get("lastConfrontationWinnerId")
        self.rules_engine["priorityPlayerId"] = (
            last_winner if last_winner in self.players
            else (first_player.get("id") if first_player else None)
        )

    def mulligan_recovery_hand(self, player_id, hand_limit=7):
        """Resolve the cost-free mandatory Mulligan used from turn two onward."""
        if not self.rules_recovery_mulligan_active():
            return "No Recovery Mulligan is currently required.", None
        if player_id not in self.players:
            return "Unknown player.", None
        required = self.rules_engine["recoveryMulliganRequiredPlayerIds"]
        if player_id not in required:
            return "Your Recovery hand already contains a playable Manifestation.", None

        player = self.players[player_id]
        while player["zones"]["hand"]:
            card_id = player["zones"]["hand"][0]
            error, _owner_id = self.move_zone_card(
                player_id, "hand", player_id, "deck", card_id, "bottom"
            )
            if error:
                return error, None
        random.shuffle(player["zones"]["deck"])
        error, draw_result = self._draw_rules_recovery_hand(player_id, hand_limit)
        if error:
            return error, None

        required.remove(player_id)
        attempted = self.rules_engine["recoveryMulliganPlayerIds"]
        if player_id not in attempted:
            attempted.append(player_id)
        playable = self.rules_opening_hand_is_playable(player_id)
        failed = self.rules_engine["recoveryMulliganFailedPlayerIds"]
        if not playable and player_id not in failed:
            failed.append(player_id)

        resumed = False
        outcome = None
        if not required:
            if failed:
                winner_ids = [pid for pid in self.players if pid not in failed]
                outcome = {
                    "reason": "invalid_recovery_hand_after_mulligan",
                    "loserIds": list(failed),
                    "winnerIds": winner_ids,
                    "draw": len(winner_ids) != 1,
                    "turn": self.phase_tracker["turn"],
                }
                self.rules_engine["outcome"] = outcome
                self.rules_engine["priorityPlayerId"] = None
                self.ended = True
            else:
                resumed = True
                self._advance_rules_after_recovery()
        return None, {
            "count": draw_result["count"],
            "handLimit": draw_result["handLimit"],
            "scoreCost": 0,
            "score": player["score"],
            "playable": playable,
            "resumed": resumed,
            "remainingMulliganPlayerIds": list(required),
            "outcome": outcome,
        }

    def resolve_recovery_draw(self, hand_limit=7):
        """Refill both hands as one Recovery action, then evaluate game end.

        The draw is deliberately simultaneous from the rules engine's point of
        view: even if the first player's deck runs short, the opponent still
        consumes every card needed to reach seven before scores are counted.
        """
        if not self.rules_engine["enabled"]:
            return "Assisted rules are not active.", None
        if self.ended:
            return "The game has already ended.", None
        if self.current_phase_id() != "recovery_draw":
            return "Recovery hands can only be refilled during the Recovery draw step.", None
        turn = self.phase_tracker["turn"]
        if self.rules_engine["recoveryDrawTurn"] == turn:
            return "Recovery hands have already been refilled this turn.", None
        if len(self.players) != NUM_SEATS:
            return "Both players must be seated before resolving the Recovery draw.", None

        draws = {}
        hand_limits = {}
        for player in sorted(self.players.values(), key=lambda current: current.get("seat", 0)):
            player_id = player["id"]
            error, draw_result = self._draw_rules_recovery_hand(player_id, hand_limit)
            if error:
                return error, None
            draws[player_id] = draw_result["count"]
            hand_limits[player_id] = draw_result["handLimit"]
        overflow = self.set_rules_hand_overflow_choice(list(self.players))

        self.rules_engine["recoveryDrawTurn"] = turn
        self.rules_engine["recoveryMulliganTurn"] = turn
        self.rules_engine["recoveryMulliganPlayerIds"] = []
        self.rules_engine["recoveryMulliganRequiredPlayerIds"] = []
        self.rules_engine["recoveryMulliganFailedPlayerIds"] = []
        incomplete_player_ids = [
            player_id for player_id, player in self.players.items()
            if len(player["zones"]["hand"]) < hand_limits[player_id]
        ]
        if incomplete_player_ids:
            self.rules_engine["outcome"] = self.calculate_final_scores()
            self.rules_engine["outcome"]["incompletePlayerIds"] = incomplete_player_ids
            self.rules_engine["priorityPlayerId"] = None
            self.ended = True
        else:
            required = [
                player_id for player_id in self.players
                if not self.rules_opening_hand_is_playable(player_id)
            ]
            self.rules_engine["recoveryMulliganRequiredPlayerIds"] = required
            if required:
                self.rules_engine["priorityPlayerId"] = None
            else:
                self._advance_rules_after_recovery()
        return None, {
            "draws": draws,
            "handLimits": hand_limits,
            "overflowChoiceId": overflow.get("id") if overflow else None,
            "incompletePlayerIds": incomplete_player_ids,
            "mulliganRequiredPlayerIds": list(self.rules_engine["recoveryMulliganRequiredPlayerIds"]),
            "advanced": not self.ended and self.current_phase_id() == "recovery_end",
            "phaseId": self.current_phase_id(),
            "outcome": self.rules_engine["outcome"],
        }

    def log_entry_for_role(self, entry, role):
        if self.mode != "tournament" or normalize_role(role) not in {"player", "spectator"}:
            return entry
        redacted = dict(entry)
        details = dict(entry.get("details") or {})
        for key in ("cardId", "cardIds", "cards", "deck", "deckDefinition", "sideboard"):
            details.pop(key, None)
        redacted["details"] = details
        return redacted

    def serialize_log(self, role="observer"):
        return {"type": "log", "entries": [self.log_entry_for_role(entry, role) for entry in self.log]}
