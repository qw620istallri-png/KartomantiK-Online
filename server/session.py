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
    "own_exhausted_cards",
}
RULES_AFTER_CHAIN = {
    "discard_deck_per_base_power", "power_counter_target_per_base_power",
    "look_top_pick_hand", "boost_controller_first", "reveal_top_opponent_suspend",
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
# passives that only work from the Stalemate Zone (Fee-fee)
RULES_STALEMATE_PASSIVE_KINDS = {"stalemate_win_blocked", "stalemate_ignores_low_power"}
# activated results whose purpose is to put a Manifestation into Support
RULES_SUPPORT_ENTRY_RESULTS = {
    "grant_source_support_until_end_turn", "stalemate_target_grant_source_support",
    "play_limbo_target_as_support", "play_vessel_target_as_support", "chabak_support",
    "will_becomes_support_manifestation", "grant_friendly_interzone_support_until_end_turn",
}
# Entering a zone with a required target and nothing to target: the card still enters.
RULES_ENTRY_EVENTS = {"enters_field", "enters_support", "enters_field_zone"}
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
            "autoSkipPhases": True,
            # players who turned off "skip phases without action" for themselves
            "autoSkipOffPlayerIds": [],
            # players who held Enter: the engine passes for them, even with
            # playable cards, until they press Enter again
            "passAllPlayerIds": [],
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
            "trapPlayerIds": [],
            "trapCards": {},
            "limboRecoveryPlayerIds": [],
            "limboDrawn": {},
            "firstManifestationComplete": False,
            "firstManifestationTriggersQueued": False,
            "confrontationEntrySequence": 0,
            "confrontationResult": None,
            "lastConfrontationWinnerId": None,
            "rematchPending": None,
            "forcedConfrontationWinnerId": None,
            "forcedConfrontationStalemate": False,
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

    @staticmethod
    def clean_rules_action_result(result):
        if not isinstance(result, dict):
            return None
        kind = result.get("kind")
        if kind == "chain_from_zone":
            return Session.clean_rules_trigger_result(result)
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
            return {
                "kind": kind, "total": min(total, 20),
                "sign": -1 if result.get("sign") == -1 else 1,
            }
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
                        "duration": "until_end_of_turn",
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
                player_id, "hand", owner_id, zone, card_id, position
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
        stored_item = action.get("sourceBattlefieldItem")
        if (
            source.get("zone") == "battlefield" and source.get("cardType") == "manifestation"
            and isinstance(stored_item, dict) and stored_item.get("tebebeConcealed")
        ):
            # Tebebe: a Manifestation played this way is put into the Interzone
            owner_id = source.get("ownerId")
            if player is None or not source_on_stack or owner_id not in self.players:
                return {"status": "source_missing", "destination": "battlefield"}
            seat = player.get("seat")
            item = {
                key: value for key, value in stored_item.items()
                if key not in {"concealedWill", "tebebeConcealed", "stackedOn", "stackOffsetX", "stackOffsetY"}
            }
            item.update({
                "controllerId": controller_id, "faceUp": True, "rotation": 0.0,
                "counters": dict(stored_item.get("counters") or {}),
                "x": 740.0, "y": 800.0 if seat != 1 else 525.0, "stackedOn": None,
            })
            if self.rules_interzone_slot_count(controller_id) >= self.rules_interzone_capacity(controller_id):
                anchor = self.rules_interzone_share_anchor(controller_id, item)
                if not anchor:
                    self.put_zone_card(owner_id, "graveyard", card_id, owner_id, "top")
                    return {"status": "interzone_full", "destination": "graveyard", "ownerId": owner_id}
                item.update({"stackedOn": anchor, "stackOffsetX": 18.0, "stackOffsetY": 18.0})
            item["fieldZone"] = "interzone"
            self.battlefield.append(item)
            self.mark_rules_interzone_entry(item)
            self.transfer_rules_stack_protection(action, item)
            return {
                "status": "moved", "destination": "battlefield", "itemId": item["id"],
                "cardId": card_id, "ownerId": owner_id, "x": item["x"], "y": item["y"],
                "fieldZone": "interzone", "fromZone": "field",
            }
        if source.get("zone") not in {"hand", "suspended", "graveyard", "battlefield", "attached", "deck"}:
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
            if source.get("exileOnLeave"):
                item["exileIfLeaves"] = True
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
        if source.get("exileOnLeave") and destination in {"graveyard", "hand", "deck"}:
            destination = "exile"
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
        if source.get("exileOnLeave"):
            destination = "exile"
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
        if target_action.get("cannotBeNeutralized"):
            return {
                "status": "prevented", "mode": mode,
                "actionId": target_action.get("id"),
                "cardId": (target_action.get("source") or {}).get("cardId"),
            }
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
            for memory_id in ability_result.get("memoryIds") or []:
                if memory_id != ability_result.get("memoryId"):
                    self.remove_rules_effect_memory(memory_id)
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
                if item.get("faceUp") and self.rules_item_card_rules(item).get("type") == "manifestation"
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
                and self.rules_item_card_rules(item).get("type")
                == "manifestation"
            ]
        elif definition.get("scope") == "target_player":
            targets = [
                {"kind": "player", "playerId": target.get("playerId")}
                for target in targets
                if target.get("kind") == "player"
                and target.get("playerId") in self.players
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
                else target.get("playerId") in self.players
                if target_kind == "player"
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
            if definition.get("temperament") in RULES_TEMPERAMENTS:
                effect["temperament"] = definition["temperament"]
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
            if (
                effect["kind"] == "power_modifier"
                and int(effect.get("value") or 0) < 0
            ):
                effect["value"] = (
                    int(effect["value"])
                    - self.rules_tribute_extra_power_loss(action)
                )
            self.rules_engine["ongoingEffects"].append(effect)
            created.append(effect)
            if (
                effect["kind"] == "power_modifier" and target_kind == "card"
                and int(effect.get("value") or 0) < 0
            ):
                self.record_rules_power_lost(target.get("itemId"))
            if (
                effect["kind"] == "power_modifier" and target_kind == "card"
                and int(effect.get("value") or 0) > 0
            ):
                self.record_rules_power_gained(target.get("itemId"))
        return created

    def prune_rules_ongoing_effects(self):
        for pending in [entry for entry in self.battlefield if entry.get("pendingExile")]:
            self._rules_remove_field_item(pending, pending.get("ownerId"), "exile", "top")
        for expired in [
            entry for entry in self.battlefield
            if entry.get("playableFree") and entry["playableFree"] != self.phase_tracker["turn"]
        ]:
            expired.pop("playableFree", None)
        for stale in [
            entry for entry in self.battlefield
            if entry.get("willManifestation")
            and (
                entry["willManifestation"].get("turn") != self.phase_tracker["turn"]
                or self.rules_field_zone(entry) not in {"confrontation", "stalemate"}
            )
        ]:
            self.revert_rules_will_manifestation(stale)
        battlefield_ids = {item.get("id") for item in self.battlefield}
        current_turn = self.phase_tracker["turn"]
        kept = []
        removed = []
        for effect in self.rules_engine["ongoingEffects"]:
            target = effect.get("target", {})
            target_present = (
                target.get("itemId") in battlefield_ids
                if target.get("itemId")
                else target.get("playerId") in self.players
                if target.get("kind") == "player"
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
        for effect in removed:
            if effect.get("kind") != "drill_link":
                continue
            drill = self.find_battlefield_item((effect.get("source") or {}).get("itemId"))
            if drill is not None and (effect.get("target") or {}).get("itemId") not in battlefield_ids:
                # Parasitic Drill: the linked Will left the field, so the Drill is sacrificed.
                self._rules_remove_field_item(drill, drill.get("ownerId"), "graveyard", "top")
        return removed

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
            if zone == "field" and card_type != "persistent_will":
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
        metadata = self._rules_item_card_rules_base(item, visiting)
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
        counters = item.setdefault("counters", {})
        counters["power"] = int(counters.get("power") or 0) + total
        if total < 0:
            self.record_rules_power_lost(item.get("id"))
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
                self.rules_engine["ongoingEffects"].append({
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
        power = self.card_rules.get(item.get("cardId"), {}).get("power")
        if not isinstance(power, (int, float)) or power > max_base_power:
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
        if item.get("isTokenCard"):
            return int(item.get("power") or 0)
        if item.get("gummoCopy"):
            return int(self.card_rules.get(item["gummoCopy"], {}).get("power") or 0)
        return int(
            self.card_rules.get(item.get("cardId"), {}).get("power") or 0
        )

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

    def resolve_rules_state_actions(self, previous_powers=None):
        """Destroy face-up Manifestations whose current Power is zero or less."""
        previous_powers = dict(previous_powers or {})
        destroyed = []
        replacements = []
        triggered_actions = []
        threshold_exiled = []
        for item in list(self.battlefield):
            if (
                not item.get("faceUp")
                or self.rules_item_card_rules(item).get("type") != "manifestation"
                or not self.rules_item_effects_active(item)
                or self.rules_field_zone(item) == "stalemate"
            ):
                continue
            passive = next((
                entry for entry in self.rules_item_card_rules(item).get("passiveEffects") or []
                if entry.get("kind") == "sacrifice_at_power"
            ), None)
            if (
                passive is None
                or self.rules_manifestation_characteristics(item)["power"]
                < int(passive.get("threshold") or 0)
            ):
                continue
            controller_id = self.rules_item_controller_id(item)
            movement = self._rules_remove_field_item_by_effect(
                item, item.get("ownerId"), "graveyard", "top", reason="sacrifice",
            )
            movement["replacement"] = "sacrifice_at_power"
            replacements.append(movement)
            if movement.get("status") == "moved":
                triggered_actions.extend(self.queue_rules_zone_entry_triggers(
                    item.get("cardId"), item.get("ownerId"),
                    item.get("ownerId"), "graveyard", defer=True,
                ))
            for other in self.rules_confrontation_items(controller_id):
                self.rules_engine["ongoingEffects"].append({
                    "id": new_id(), "actionId": None,
                    "abilityId": "sacrifice-at-power-bonus",
                    "controllerId": controller_id,
                    "source": {"cardId": item.get("cardId")},
                    "target": {
                        "kind": "card", "itemId": other["id"],
                        "cardId": other.get("cardId"), "ownerId": other.get("ownerId"),
                    },
                    "kind": "power_modifier", "value": int(passive.get("bonus") or 0),
                    "duration": "until_end_of_turn",
                    "startedTurn": self.phase_tracker["turn"],
                })
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
                    self.rules_item_card_rules(item).get("type") == "manifestation"
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
        if first == second or not first or not second:
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
        if (
            item.get("exileIfLeaves")
            and zone in {"graveyard", "hand", "deck"}
            and not item.get("isCopy") and not item.get("isTokenCard")
        ):
            container_id, zone, position = item.get("ownerId"), "exile", "top"
        self.battlefield.remove(item)
        for entry in item.pop("attachedCards", None) or []:
            self.put_zone_card(entry["ownerId"], "exile", entry["cardId"], entry["ownerId"], "top")
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
        if (
            item.get("exileIfLeaves")
            and zone in {"graveyard", "hand", "deck"}
            and not item.get("isCopy") and not item.get("isTokenCard")
        ):
            container_id, zone, position = item.get("ownerId"), "exile", "top"
        home_vessel = item.get("returnToVesselId")
        if (
            home_vessel in self.players
            and zone != "receptacle"
            and self.rules_field_zone(item) == "confrontation"
            and not item.get("isCopy") and not item.get("isTokenCard")
        ):
            # Dol: a Chained card leaving the Confrontation Zone by an effect
            # goes back to the Vessel it came from instead.
            container_id, zone, position = home_vessel, "receptacle", "top"
        elif (
            item.get("exileInsteadOfLeaving")
            and zone != "exile"
            and self.rules_field_zone(item) == "confrontation"
            and not item.get("isCopy") and not item.get("isTokenCard")
        ):
            # Regurgitating Catacomb: the raised Manifestation is exiled
            # instead of leaving the Confrontation Zone due to an effect.
            container_id, zone, position = item.get("ownerId"), "exile", "top"
        field_penalty = 0
        if (
            zone != "exile"
            and self.rules_field_zone(item) == "confrontation"
            and not item.get("isCopy") and not item.get("isTokenCard")
            and self.rules_item_card_rules(item).get("exileIfLeavesConfrontationByEffect")
            and self.rules_item_effects_active(item)
        ):
            # Gigabonblade: exiled instead, and every field Manifestation weakens.
            container_id, zone, position = item.get("ownerId"), "exile", "top"
            field_penalty = int(self.rules_item_card_rules(item).get("exiledByEffectFieldPenalty") or 0)
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
        controller_before = self.rules_item_controller_id(item)
        movement = self._rules_remove_field_item(
            item, container_id, zone, position
        )
        if field_penalty and movement.get("status") == "moved":
            for other in self.battlefield:
                if self.card_rules.get(other.get("cardId"), {}).get("type") == "manifestation":
                    counters = other.setdefault("counters", {})
                    counters["power"] = int(counters.get("power") or 0) - field_penalty
        if (
            movement.get("status") == "moved"
            and self.rules_item_card_rules(item).get("type") == "manifestation"
        ):
            self.record_rules_observed_event(
                "manifestation_left_by_effect", controller_before,
                cardId=item.get("cardId"),
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
        loudmouth_forces_stalemate = (
            loudmouth_forces_stalemate
            or bool(self.rules_engine.get("forcedConfrontationStalemate"))
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
            elif totals[first_id] <= 0:
                # 0 against 0: nobody wins, Temperaments do not decide it
                pass
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
        elif winner_id is None:
            self.rules_engine.setdefault("confrontationStalemates", {})[
                str(self.phase_tracker["turn"])
            ] = True
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
        while pending:
            candidate = self.find_battlefield_item(pending[0])
            if candidate is None:
                pending.pop(0)
            elif (
                (candidate.get("isCopy") or candidate.get("isTokenCard"))
                and not candidate.get("permanent")
            ):
                # temporary Copies and Tokens end with the turn: no deck, no Interzone
                result.setdefault("returned", []).append(
                    self._rules_remove_field_item(
                        candidate, candidate.get("ownerId"), "exile", "top"
                    )
                )
                pending.pop(0)
            else:
                break
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
        if item.get("isCopy") or item.get("isTokenCard"):
            # a permanent Copy or Token can only stay in the Interzone
            choice["options"] = ["interzone"]
        elif self.rules_karmapult_holder(result.get("winnerId"), item):
            choice["options"].append("karmapult")
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
        self.settle_rules_will_manifestations(result, participant_ids)
        support_returned = []
        for item in list(self.battlefield):
            support_return = item.get("supportReturn")
            if not support_return or item.get("id") not in participant_ids:
                continue
            if self.rules_item_zone_locked(item):
                continue
            controller_id = support_return.get("controllerId")
            if (
                not result.get("stalemate")
                and result.get("winnerId") == controller_id
                and controller_id in self.players
            ):
                support_returned.append(self._rules_remove_field_item(
                    item, controller_id, "receptacle", "top"
                ))
            else:
                support_returned.append(self._rules_remove_field_item(
                    item, item.get("ownerId"), "hand", "top"
                ))
        if support_returned:
            result["supportReturned"] = support_returned
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
        # cards in Stalemate never take part in the resolution
        for item in list(self.rules_confrontation_items_owned_by(
            loser_id, ("confrontation",)
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
        # The Stalemate Zone is settled by the first confrontation with a winner
        # (FAQ "How is a Stalemate resolved?"): the winner takes the opponent's
        # waiting Manifestations into their Vessel and places their own like
        # winning cards. They are neither winners nor losers, so no win or loss
        # effect triggers. Cards an effect locked there this turn stay.
        stalemate_own = []
        if winner_id in self.players:
            for item in list(self.battlefield):
                if self.rules_field_zone(item) != "stalemate" or self.rules_item_zone_locked(item):
                    continue
                if item.get("ownerId") == winner_id:
                    if not self.rules_stalemate_win_blocked(item):
                        stalemate_own.append(item)
                    continue
                movement = self._rules_remove_field_item(
                    item, winner_id,
                    "exile" if item.get("isCopy") or item.get("isTokenCard") else "receptacle",
                    "top",
                )
                movement["fromStalemate"] = True
                captured.append(movement)
        own_items = [
            item for item in self.rules_confrontation_items_owned_by(
                winner_id, ("confrontation",)
            )
            if item.get("id") not in rematch_item_ids
            and not self.rules_item_zone_locked(item)
            and int(item.get("holdUntilResolution") or 0) <= self.phase_tracker["turn"]
            and not self.rules_stalemate_win_blocked(item)
        ]
        for held_item in self.battlefield:
            if int(held_item.get("holdUntilResolution") or 0) == self.phase_tracker["turn"]:
                held_item.pop("holdUntilResolution", None)
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
            if (
                loser_id in self.players
                and self.rules_item_effects_active(item)
                and not item.get("isCopy") and not item.get("isTokenCard")
                and any(
                    passive.get("kind") == "win_to_opponent_interzone"
                    for passive in self.rules_item_card_rules(item).get(
                        "passiveEffects"
                    ) or []
                )
            ):
                if self.rules_interzone_slot_count(loser_id) >= self.rules_interzone_capacity(loser_id):
                    anchor = self.rules_interzone_share_anchor(loser_id, item)
                    item.update({
                        "stackedOn": anchor, "stackOffsetX": 18.0, "stackOffsetY": 18.0,
                    } if anchor else {"stackedOn": None})
                else:
                    item["stackedOn"] = None
                item["controllerId"] = loser_id
                item["fieldZone"] = "interzone"
                item["isSupport"] = False
                self.mark_rules_interzone_entry(item)
                support_resolved.append({
                    "kind": "win_to_opponent_interzone", "cardId": item.get("cardId"),
                    "itemId": item.get("id"), "playerId": loser_id,
                })
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
        # Inspired Nimbus & co.: cards captured into a Vessel trigger their own
        # "enters an Empathic Vessel" abilities, and Vessel watchers react now.
        vessel_triggers = []
        for movement in captured + [
            entry.get("movement") or {} for entry in support_resolved
        ]:
            if movement.get("status") == "moved" and movement.get("zone") == "receptacle":
                vessel_triggers.extend(self.queue_rules_zone_entry_triggers(
                    movement.get("cardId"), movement.get("ownerId"),
                    movement.get("containerId"), "receptacle", defer=True,
                ))
        vessel_triggers.extend(self.queue_rules_observed_event_triggers(defer=True))
        if vessel_triggers:
            self.queue_or_defer_rules_simultaneous_actions(vessel_triggers)
            result["triggeredActions"] = vessel_triggers
        result["rematchItemIds"] = list(rematch_item_ids)
        persist_candidates = [
            item for item in own_items if self.rules_item_has_persist(item)
        ]
        own_items.extend(stalemate_own)
        result["stalemateWonItemIds"] = [item["id"] for item in stalemate_own]
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
        self.rules_engine["trapPlayerIds"] = []
        self.flush_rules_traps()
        self.rules_engine["confrontationEntrySequence"] = max(
            (
                int(item.get("confrontationOrder") or 0)
                for item in self.rules_confrontation_items()
            ),
            default=0,
        )
        self.rules_engine["confrontationResult"] = None
        self.rules_engine["forcedConfrontationWinnerId"] = None
        self.rules_engine["forcedConfrontationStalemate"] = False

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

    def rules_persistent_wills_as_ephemeral(self, player_id):
        return any(
            self.rules_item_controller_id(item) == player_id
            and self.rules_field_zone(item) == "interzone"
            for item in self.rules_active_passive_sources("persistent_wills_as_ephemeral")
        )

    def rules_action_timing_error(self, kind, source, as_support=False, player_id=None):
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
            if self.rules_support_from_hand_available_anytime((source or {}).get("cardId")):
                return None
            return None if self.current_phase_id() == "confrontation_reaction" else "A Support Manifestation can only be played during Reaction."
        if not started or kind not in {"play_card", "activated_effect"}:
            return None
        phase_id = self.current_phase_id()
        response_phases = {"confrontation_reaction", "resolution_effects", "end_actions"}
        if kind == "activated_effect":
            abilities = self.card_rules.get((source or {}).get("cardId"), {}).get(
                "activatedAbilities"
            ) or []
            has_phase_ability = any(
                phase_id in (ability.get("phaseIds") or [])
                for ability in abilities
            )
            return (
                None
                if phase_id in response_phases or has_phase_ability
                else "This effect cannot be activated during the current step."
            )
        card_type = (source or {}).get("cardType")
        if card_type == "manifestation" and (source or {}).get("zone") == "battlefield":
            played_item = self.find_battlefield_item((source or {}).get("itemId"))
            if played_item and played_item.get("tebebeConcealed"):
                # played "as if it were in your hand": the Manifestation windows
                if phase_id in {"confrontation_reaction", "end_actions"}:
                    return None
                return "This Manifestation can only be played during Reaction or End actions."
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
                phase_id in response_phases and player_id
                and self.rules_persistent_wills_as_ephemeral(player_id)
            ):
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

    def rules_match_started(self):
        return bool(
            self.phase_tracker["turn"] > 1
            or len(self.rules_engine.get("readyPlayerIds") or []) >= NUM_SEATS
            or self.rules_engine.get("firstManifestationComplete")
            or self.rules_engine.get("firstManifestationItemIds")
        )

    def rules_field_ability_usable(self, item, ability, zone, phase_id):
        """Cheap check that an activated ability of a field card could be used right now."""
        source_zones = ability.get("sourceZones")
        if source_zones and "battlefield" not in source_zones:
            return False
        required_zone = ability.get("sourceFieldZone")
        if required_zone and required_zone != zone:
            return False
        phase_ids = ability.get("phaseIds")
        if phase_ids and phase_id not in phase_ids:
            return False
        if ability.get("exhaustSource") and int(round(float(item.get("rotation") or 0))) % 180:
            return False  # already exhausted
        if self.rules_ability_clearly_unusable(
            self.rules_item_controller_id(item), ability, phase_id, item.get("cardId"),
        ):
            return False
        turn = self.phase_tracker["turn"]
        if ability.get("oncePerTurnSupport") and turn in (item.get("supportUsedTurn"), item.get("supportUntilTurn")):
            return False
        removal = ability.get("removeCountersFromSource")
        if isinstance(removal, dict):
            counters = item.get("counters") or {}
            have = sum(
                int(value or 0) for key, value in counters.items()
                if str(key).casefold() == str(removal.get("name") or "").casefold()
            )
            if have < int(removal.get("amount") or 0):
                return False
        return True

    def rules_will_affordable(self, player_id, card_id):
        """Whether the Tribute of a Will can be paid with what the player has.

        Generous whenever an unusual payment source exists, so a phase is never
        skipped by mistake.
        """
        metadata = self.card_rules.get(card_id, {})
        if self.rules_exotic_tribute_available(player_id) or any(
            entry.get("playerId") == player_id and (entry.get("noTribute") or entry.get("anyWill"))
            for entry in self.rules_engine.get("playPermissions") or []
        ):
            return True
        try:
            requirements, _enforced = self.rules_tribute_requirements(
                "play_card", {"cardId": card_id, "cardType": metadata.get("type")}, None, player_id,
            )
        except Exception:  # never skip a phase because of a computation problem
            return True
        return self.rules_requirements_affordable(player_id, requirements, card_id)

    def rules_exotic_tribute_available(self, player_id):
        """An unusual Tribute source (Limbo, Vessel, field): affordability is not computed."""
        player = self.players[player_id]
        if any(
            self.rules_active_passive_sources(kind)
            for kind in (
                "allow_limbo_tribute_with_counter", "vessel_manifestations_as_tribute",
                "field_manifestations_as_tribute",
            )
        ):
            return True
        return any(
            self.card_rules.get(other, {}).get("canPayTributeFromLimbo")
            for other in player["zones"]["graveyard"]
        ) or any(
            self.rules_item_controller_id(item) == player_id
            and self.card_rules.get(item.get("cardId"), {}).get("canPayTributeFromInterzone")
            for item in self.battlefield
        )

    def rules_requirements_affordable(self, player_id, requirements, exclude_card_id=None):
        """Whether Essences plus hand Manifestations can pay these Tribute requirements."""
        player = self.players[player_id]
        try:
            remaining, _spent = self.rules_essence_payment_plan(player_id, requirements)
            if all(amount <= 0 for amount in remaining.values()):
                return True
            candidates = [
                other for other in player["zones"]["hand"]
                if other != exclude_card_id and self.card_rules.get(other, {}).get("type") == "manifestation"
                and self.card_rules.get(other, {}).get("canPayTribute", True)
            ][:12]
            for mask in range(1, 1 << len(candidates)):
                selected = [card for index, card in enumerate(candidates) if mask & (1 << index)]
                if self.rules_manifestations_cover(selected, remaining, player_id=player_id)[0]:
                    return True
            return False
        except Exception:  # never skip a phase because of a computation problem
            return True

    def rules_hand_additional_cost_available(self, player_id, source_card_id, ability):
        """Whether the hand holds the card an additional cost needs (Censor:
        a Manifestation to reveal and exile; Timid Brain: a Will to discard).
        The source card itself never pays its own additional cost."""
        additional_cost = (ability or {}).get("additionalCost")
        if additional_cost not in {"exile_hand_manifestation", "discard_hand_will"}:
            return True
        hand_cards = list(self.players[player_id]["zones"]["hand"])
        if source_card_id in hand_cards:
            hand_cards.remove(source_card_id)
        cost_types = (
            RULES_WILL_TYPES if additional_cost == "discard_hand_will"
            else {"manifestation"}
        )
        return any(
            self.card_rules.get(card_id, {}).get("type") in cost_types
            for card_id in hand_cards
        )

    def rules_played_ability_has_field_target(self, player_id, card_id):
        """False only when the played ability needs a card on the field and none is legal."""
        ability = next(iter(self.card_rules.get(card_id, {}).get("playedAbilities") or []), None)
        target_rules = (ability or {}).get("targets") or {}
        if int(target_rules.get("min") or 0) < 1 or target_rules.get("groups"):
            return True
        if target_rules.get("kind") == "zone_card" and set(target_rules.get("zones") or []) <= {"graveyard", "receptacle"}:
            # Revive, Claim the Forsaken: a card must wait in a Limbo or a Vessel
            try:
                return any(
                    self.rules_ability_targets_error(
                        target_rules,
                        [{
                            "kind": "zone_card", "containerId": container_id, "zone": zone,
                            "cardId": card_id,
                            "ownerId": self.card_owner_in_zone(container_id, zone, card_id),
                        }],
                        player_id,
                    ) is None
                    for container_id, container in self.players.items()
                    for zone in target_rules.get("zones") or []
                    for card_id in dict.fromkeys(container["zones"].get(zone) or [])
                )
            except Exception:  # never skip a phase because of a computation problem
                return True
        if target_rules.get("kind") not in {None, "card"} or (target_rules.get("zones") or ["battlefield"]) != ["battlefield"]:
            return True
        return any(
            self.rules_ability_targets_error(
                target_rules,
                [{"kind": "card", "itemId": item.get("id"), "cardId": item.get("cardId")}],
                player_id,
            ) is None
            for item in self.battlefield
        )

    def rules_ability_clearly_unusable(self, player_id, ability, phase_id, source_card_id=None):
        """Cheap checks shared by auto-pass: condition, step, Essence cost and
        a required target on the field or the Stack. True only when the
        ability certainly cannot be used now."""
        ability = ability or {}
        condition = str(ability.get("condition") or "")
        if condition == "controller_lost_confrontation":
            if not self.rules_player_lost_confrontation_this_turn(player_id):
                return True
        if condition == "last_opponent_support_low_power" and self.rules_last_opponent_support(player_id, 2) is None:
            return True
        phase_ids = [str(entry) for entry in ability.get("phaseIds") or [] if str(entry) in ADVANCED_PHASES]
        if phase_ids and phase_id not in phase_ids:
            return True
        result_kind = (ability.get("result") or {}).get("kind")
        if result_kind in {"grant_source_support_until_end_turn", "stalemate_target_grant_source_support"} and phase_id != "confrontation_reaction":
            # Support only matters while Supports can still be played
            return True
        if result_kind in RULES_SUPPORT_ENTRY_RESULTS and player_id in self.players and self.rules_support_entry_locked(player_id):
            # Pin Down: nothing can be put into the Confrontation Zone this turn
            return True
        if result_kind == "first_manifestation_trap" and phase_id != "confrontation_choose":
            return True
        if result_kind == "chain_from_zone" and (ability.get("result") or {}).get("zone") == "hand":
            hand = list(self.players[player_id]["zones"]["hand"])
            if source_card_id in hand:
                hand.remove(source_card_id)
            if not any(self.card_rules.get(card, {}).get("type") == "manifestation" for card in hand):
                return True
        tribute = str(ability.get("tribute") or "")
        if tribute and player_id in self.players and not self.rules_exotic_tribute_available(player_id):
            try:
                requirements = self.rules_requirements_from_symbols(tribute)
            except Exception:  # never skip a phase because of a computation problem
                requirements = None
            if requirements and not self.rules_requirements_affordable(
                player_id, requirements, source_card_id,
            ):
                return True
        essence_cost = str(ability.get("essenceCost") or "")
        if essence_cost:
            try:
                requirements = self.rules_requirements_from_symbols(essence_cost)
                remaining, _spent = self.rules_essence_payment_plan(player_id, requirements)
                if requirements and any(amount > 0 for amount in remaining.values()):
                    return True
            except Exception:  # never skip a phase because of a computation problem
                pass
        target_rules = ability.get("targets") or {}
        if int(target_rules.get("min") or 0) >= 1 and not target_rules.get("groups"):
            kind = target_rules.get("kind")
            if kind in {"stack_action", "stack_effect"}:
                stack = self.rules_engine.get("actionStack") or []
                if kind == "stack_effect":
                    stack = [entry for entry in stack if entry.get("kind") != "play_card"]
                if target_rules.get("controller") == "self":
                    stack = [entry for entry in stack if entry.get("controllerId") == player_id]
                card_types = target_rules.get("cardTypes")
                if card_types:
                    stack = [
                        entry for entry in stack
                        if self.card_rules.get((entry.get("source") or {}).get("cardId"), {}).get("type") in card_types
                    ]
                if not stack:
                    return True
            elif kind in {None, "card"} and (target_rules.get("zones") or ["battlefield"]) == ["battlefield"]:
                if not any(
                    self.rules_ability_targets_error(
                        target_rules,
                        [{"kind": "card", "itemId": item.get("id"), "cardId": item.get("cardId")}],
                        player_id,
                    ) is None
                    for item in self.battlefield
                ):
                    return True
        return False

    def rules_usable_hand_ability_card_ids(self, player_id):
        if not self.rules_engine.get("enabled") or player_id not in self.players:
            return []
        phase_id = self.current_phase_id()
        usable = []
        for card_id in dict.fromkeys(self.players[player_id]["zones"]["hand"]):
            if any(
                "hand" in (ability.get("sourceZones") or [])
                and self.rules_hand_additional_cost_available(player_id, card_id, ability)
                and not self.rules_ability_clearly_unusable(player_id, ability, phase_id, card_id)
                for ability in self.card_rules.get(card_id, {}).get("activatedAbilities") or []
            ):
                usable.append(card_id)
        return usable

    def rules_player_can_act(self, player_id):
        """True when the player has any voluntary action available in the current step.

        Deliberately generous: timing and zones are checked, and Will Tributes only
        when the player clearly cannot pay them, so a phase is never skipped by mistake.
        """
        player = self.players[player_id]
        phase_id = self.current_phase_id()
        response = phase_id in {"confrontation_reaction", "resolution_effects", "end_actions"}
        support_locked = self.rules_support_entry_locked(player_id)

        def can_play(card_id, card_type):
            return self.rules_action_timing_error(
                "play_card", {"cardId": card_id, "cardType": card_type},
                player_id=player_id,
            ) is None

        def can_support(card_id):
            return not support_locked and self.rules_action_timing_error(
                "play_card", {"cardId": card_id, "cardType": "manifestation"},
                as_support=True, player_id=player_id,
            ) is None

        for card_id in set(player["zones"]["hand"]):
            metadata = self.card_rules.get(card_id, {})
            card_type = metadata.get("type")
            if (
                card_type in RULES_WILL_TYPES and can_play(card_id, card_type)
                and self.rules_will_affordable(player_id, card_id)
                and all(
                    self.rules_hand_additional_cost_available(player_id, card_id, ability)
                    for ability in (metadata.get("playedAbilities") or [])[:1]
                )
                and self.rules_played_ability_has_field_target(player_id, card_id)
                and not any(
                    self.rules_ability_clearly_unusable(player_id, ability, phase_id, card_id)
                    for ability in (metadata.get("playedAbilities") or [])[:1]
                )
            ):
                return True
            if (
                card_type == "manifestation" and can_support(card_id)
                and self.rules_support_from_hand_available(player_id, card_id)
            ):
                return True
            if response and any(
                "hand" in (ability.get("sourceZones") or [])
                and self.rules_hand_additional_cost_available(player_id, card_id, ability)
                and not self.rules_ability_clearly_unusable(player_id, ability, phase_id, card_id)
                for ability in metadata.get("activatedAbilities") or []
            ):
                return True
        if response:
            for card_id in set(player["zones"]["receptacle"]):
                if any(
                    "receptacle" in (ability.get("sourceZones") or [])
                    and not self.rules_ability_clearly_unusable(player_id, ability, phase_id, card_id)
                    for ability in self.card_rules.get(card_id, {}).get("activatedAbilities") or []
                ):
                    return True
            if any(
                self.rules_play_permission_usable(player_id, entry, phase_id)
                for entry in self.rules_engine.get("playPermissions") or []
            ):
                return True
        for item in self.battlefield:
            if self.rules_item_controller_id(item) != player_id:
                continue
            metadata = self.rules_item_card_rules(item)
            card_type = metadata.get("type")
            zone = self.rules_field_zone(item)
            if (
                card_type in RULES_WILL_TYPES
                and (
                    item.get("concealedWill") or item.get("persuaded")
                    or item.get("playableFree") == self.phase_tracker["turn"]
                )
                and can_play(item.get("cardId"), card_type)
            ):
                return True
            # Grimoire: the Wills placed on it are played as if they were in the hand
            if item.get("attachedCards") and self.rules_item_effects_active(item) and any(
                passive.get("kind") == "play_attached_wills"
                for passive in metadata.get("passiveEffects") or []
            ) and any(
                entry.get("ownerId") == player_id
                and self.card_rules.get(entry.get("cardId"), {}).get("type") in RULES_WILL_TYPES
                and can_play(entry.get("cardId"), self.card_rules[entry["cardId"]]["type"])
                and self.rules_will_affordable(player_id, entry.get("cardId"))
                for entry in item["attachedCards"]
            ):
                return True
            if (
                card_type == "manifestation" and item.get("tebebeConcealed")
                and self.rules_action_timing_error(
                    "play_card",
                    {"cardId": item.get("cardId"), "cardType": card_type, "zone": "battlefield", "itemId": item.get("id")},
                    player_id=player_id,
                ) is None
            ):
                return True
            if (
                card_type == "manifestation" and zone in {"interzone", "stalemate"}
                and can_support(item.get("cardId"))
                and self.rules_card_can_enter_support(item, from_zone=zone)
                and not self.rules_item_zone_locked(item)
            ):
                return True
            if (
                response and item.get("faceUp")
                and self.rules_item_effects_active(item)
                and any(
                    self.rules_field_ability_usable(item, ability, zone, phase_id)
                    for ability in metadata.get("activatedAbilities") or []
                )
            ):
                return True
        return False

    def rules_play_permission_usable(self, player_id, entry, phase_id):
        """A play permission counts as an action only while its card can be played now
        (Wandering Veteran's Support from the Limbo is no action in End actions)."""
        if entry.get("playerId") != player_id:
            return False
        if int(entry.get("turn") or self.phase_tracker["turn"]) != self.phase_tracker["turn"]:
            return False
        if entry.get("phaseIds") and phase_id not in entry["phaseIds"]:
            return False
        zone_cards = self.players[player_id]["zones"].get(entry.get("fromZone") or "hand") or []
        if entry.get("cardId"):
            card_ids = [entry["cardId"]] if entry["cardId"] in zone_cards else []
        elif entry.get("anyWill"):
            card_ids = [
                card_id for card_id in zone_cards
                if self.card_rules.get(card_id, {}).get("type") in (
                    {"ephemeral_will"} if entry.get("ephemeralOnly") else RULES_WILL_TYPES
                )
                and (
                    entry.get("maxCost") is None
                    or int(self.card_rules.get(card_id, {}).get("cost") or 0) <= int(entry["maxCost"])
                )
            ]
        else:
            return True  # unknown shape: stay generous
        for card_id in dict.fromkeys(card_ids):
            card_type = self.card_rules.get(card_id, {}).get("type")
            if entry.get("asSupport"):
                if (
                    not self.rules_support_entry_locked(player_id)
                    and not self.rules_confrontation_entry_blocked(player_id, self.card_rules.get(card_id, {}))
                    and self.rules_action_timing_error(
                        "play_card", {"cardId": card_id, "cardType": "manifestation"},
                        as_support=True, player_id=player_id,
                    ) is None
                ):
                    return True
                continue
            if self.rules_action_timing_error(
                "play_card", {"cardId": card_id, "cardType": card_type}, player_id=player_id,
            ) is None:
                return True
        return False

    def rules_confrontation_resolve_prompt(self):
        """True when the Reaction step is open, the Stack is empty and nobody can
        play a card or an effect: the engine asks before resolving the Confrontation."""
        engine = self.rules_engine
        if (
            not engine.get("enabled")
            or not self.rules_auto_skip_enabled(engine.get("priorityPlayerId"))
            or self.ended or len(self.players) < NUM_SEATS
            or not self.phase_tracker.get("enabled")
            or self.current_phase_id() != "confrontation_reaction"
            or engine.get("actionStack") or engine.get("priorityPasses")
            or engine.get("pendingChoice")
            or not self.rules_match_started()
            or self.rules_first_manifestation_active()
            or self.rules_recovery_mulligan_active()
            or engine.get("priorityPlayerId") not in self.players
        ):
            return False
        return not any(self.rules_player_can_act(pid) for pid in self.players)

    def rules_auto_skip_enabled(self, player_id):
        """Whether the engine may skip phases for this player (each player's own option)."""
        engine = self.rules_engine
        return bool(engine.get("autoSkipPhases", True)) and player_id not in (
            engine.get("autoSkipOffPlayerIds") or []
        )

    def set_rules_auto_skip(self, player_id, enabled):
        if player_id not in self.players:
            return "Unable to change this option.", None
        off = [
            pid for pid in self.rules_engine.get("autoSkipOffPlayerIds") or []
            if pid != player_id and pid in self.players
        ]
        if not enabled:
            off.append(player_id)
        self.rules_engine["autoSkipOffPlayerIds"] = off
        return None, {"playerId": player_id, "enabled": bool(enabled)}

    def set_rules_pass_all(self, player_id, enabled):
        if not self.rules_engine.get("enabled") or player_id not in self.players:
            return "Assisted rules are not active.", None
        locked = [
            pid for pid in self.rules_engine.get("passAllPlayerIds") or []
            if pid != player_id and pid in self.players
        ]
        if enabled:
            locked.append(player_id)
        self.rules_engine["passAllPlayerIds"] = locked
        return None, {"playerId": player_id, "enabled": bool(enabled)}

    def rules_auto_pass_player(self):
        """The priority holder when no legal response or auto-skippable action exists."""
        engine = self.rules_engine
        pass_all = engine.get("priorityPlayerId") in (engine.get("passAllPlayerIds") or [])
        stack_waiting = bool(engine.get("actionStack"))
        if (
            not engine.get("enabled")
            or not (stack_waiting or self.rules_auto_skip_enabled(engine.get("priorityPlayerId")) or pass_all)
            or not self.phase_tracker.get("enabled") or self.ended
            or len(self.players) < NUM_SEATS or engine.get("pendingChoice")
            or not self.rules_match_started()
            or self.rules_first_manifestation_active()
            or self.rules_recovery_mulligan_active()
        ):
            return None
        player_id = engine.get("priorityPlayerId")
        if player_id not in self.players:
            return None
        if pass_all:
            return player_id
        if self.rules_player_can_act(player_id):
            return None
        if self.rules_confrontation_resolve_prompt():
            return None  # ask before resolving the Confrontation
        return player_id

    def declare_rules_action(self, player_id, label, kind="manual", source=None, target=None,
                             targets=None, cost_note=None, payment_card_ids=None, ability_id=None,
                             placement=None, as_support=False,
                             extra_essence_count=0, cost_card_id=None, internal=False,
                             extra_payment_card_ids=None):
        if not self.rules_engine["enabled"]:
            return "Assisted rules are not active.", None
        if self.ended or player_id not in self.players:
            return "Unable to declare an action.", None
        if len(self.players) < 2:
            return "Both players must join before using priority.", None
        if self.rules_engine.get("pendingChoice"):
            return "A required card choice must be completed first.", None
        if self.rules_engine["priorityPlayerId"] != player_id and not internal:
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
        timing_error = None if internal else self.rules_action_timing_error(
            kind, clean_source, as_support=as_support, player_id=player_id,
        )
        if timing_error:
            return timing_error, None
        target_error, clean_targets = self.rules_action_targets(targets, player_id)
        if target_error:
            return target_error, None
        ingredients = (
            {clean_source.get("cardId")}
            if (clean_source or {}).get("zone") == "hand" else set()
        )
        for refs in (payment_card_ids, extra_payment_card_ids):
            if isinstance(refs, list):
                ingredients.update(
                    card_id for zone, _sep, card_id in (
                        str(ref or "").rpartition("|") for ref in refs
                    )
                    if zone in {"", "hand"}
                )
        if any(
            entry.get("kind") == "zone_card" and entry.get("zone") == "hand"
            and entry.get("cardId") in ingredients
            for entry in clean_targets
        ):
            return "The played card and its tribute cannot be chosen as its target.", None
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
            extra_payment_card_ids,
        )
        if payment_error:
            return payment_error, None
        cost_card_id = str(cost_card_id) if cost_card_id else None
        if clean_ability and clean_ability.get("sourceCost") and not (
            clean_source.get("zone") == "hand"
            and clean_source.get("cardId") in self.players[player_id]["zones"]["hand"]
        ):
            return "This effect's cost needs its source card in your Hand.", None
        additional_cost = (clean_ability or {}).get("additionalCost")
        if additional_cost in {"exile_hand_manifestation", "discard_hand_will"}:
            hand_cards = list(self.players[player_id]["zones"]["hand"])
            if clean_source.get("zone") == "hand" and clean_source.get("cardId") in hand_cards:
                hand_cards.remove(clean_source["cardId"])
            cost_types = (
                RULES_WILL_TYPES if additional_cost == "discard_hand_will"
                else {"manifestation"}
            )
            if not any(
                self.card_rules.get(card_id, {}).get("type") in cost_types
                for card_id in hand_cards
            ):
                return (
                    "You need a Will in hand to discard as an additional cost."
                    if additional_cost == "discard_hand_will"
                    else "You need a Manifestation in hand to reveal and exile as an additional cost."
                ), None
            if (
                cost_card_id not in hand_cards
                or self.card_rules.get(cost_card_id, {}).get("type") not in cost_types
            ):
                return (
                    "Choose the Will from your hand to discard."
                    if additional_cost == "discard_hand_will"
                    else "Choose the Manifestation from your hand to reveal and exile."
                ), None
        else:
            cost_card_id = None
        clean_targets = self.rules_redirect_targets(player_id, clean_targets)
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
        if kind == "play_card" and clean_source.get("zone") in {"hand", "graveyard", "suspended", "deck"}:
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
        elif clean_source and clean_source.get("zone") == "attached" and kind == "play_card":
            host = self.find_battlefield_item(clean_source.get("itemId"))
            entry = next((
                e for e in (host or {}).get("attachedCards") or []
                if e.get("cardId") == clean_source["cardId"]
            ), None)
            if entry is None:
                return "This Will is no longer placed on that card.", None
            host["attachedCards"].remove(entry)
            self.rules_sync_attached_counter(host)
            action["sourceOnStack"] = True
        elif clean_source and clean_source.get("zone") == "battlefield" and kind == "play_card":
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
        if cost_card_id and additional_cost == "discard_hand_will":
            cost_owner = self.card_owner_in_zone(player_id, "hand", cost_card_id) or player_id
            cost_error, _owner, _replacement = self.move_zone_card_by_effect(
                player_id, "hand", cost_owner, "graveyard", cost_card_id, "top"
            )
            if not cost_error:
                action["cost"]["discardedCard"] = {
                    "cardId": cost_card_id, "ownerId": cost_owner,
                }
        elif cost_card_id:
            cost_owner = self.card_owner_in_zone(player_id, "hand", cost_card_id) or player_id
            cost_error, _owner, _replacement = self.move_zone_card_by_effect(
                player_id, "hand", cost_owner, "exile", cost_card_id, "top"
            )
            if not cost_error:
                action["cost"]["revealedCard"] = {
                    "cardId": cost_card_id, "ownerId": cost_owner,
                    "power": int(self.card_rules.get(cost_card_id, {}).get("power") or 0),
                }
        source_cost = (clean_ability or {}).get("sourceCost")
        if source_cost == "discard_source":
            source_owner = self.card_owner_in_zone(
                player_id, "hand", clean_source["cardId"]
            ) or player_id
            source_error, _owner, _replacement = self.move_zone_card_by_effect(
                player_id, "hand", source_owner, "graveyard",
                clean_source["cardId"], "top",
            )
            if not source_error:
                action["cost"]["discardedSource"] = {
                    "cardId": clean_source["cardId"], "ownerId": source_owner,
                }
        elif source_cost == "stalemate_source":
            source_owner = self.take_zone_card(
                player_id, "hand", clean_source["cardId"]
            )
            if source_owner is not None:
                seat = self.players[player_id].get("seat")
                stalemate_item = {
                    "id": new_id(), "ownerId": source_owner,
                    "controllerId": player_id, "cardId": clean_source["cardId"],
                    "x": 650.0, "y": 800.0 if seat != 1 else 525.0,
                    "faceUp": True, "rotation": 0.0, "counters": {},
                    "rarity": self.players[source_owner].get(
                        "cardRarities", {}
                    ).get(clean_source["cardId"]),
                    "stackedOn": None, "fieldZone": "stalemate",
                }
                self.battlefield.append(stalemate_item)
                action["cost"]["stalematedSource"] = {
                    "cardId": clean_source["cardId"], "ownerId": source_owner,
                    "itemId": stalemate_item["id"],
                }
        if kind == "activated_effect":
            self.apply_rules_drill_drain(clean_source.get("itemId"))
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

    def rules_trigger_has_no_legal_target(self, target_rules, controller_id, event_item_id=None):
        """True when a required single card target cannot be met by anything on the field.

        The card still enters; its triggered effect is simply not put on the Stack.
        """
        target_rules = target_rules or {}
        if (
            target_rules.get("groups") or str(target_rules.get("kind") or "card") != "card"
            or int(target_rules.get("min") or 0) < 1
            or int(target_rules.get("min") or 0) > 1
            or set(target_rules.get("zones") or ["battlefield"]) - {"battlefield"}
        ):
            return False
        for item in self.battlefield:
            error, clean = self.rules_action_targets([{
                "kind": "card", "itemId": item.get("id"), "cardId": item.get("cardId"),
            }])
            if error:
                continue
            if self.rules_ability_targets_error(
                target_rules, clean, controller_id, event_item_id=event_item_id,
            ) is None:
                return False
        return True

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
            if error and not targets and event in RULES_ENTRY_EVENTS and self.rules_trigger_has_no_legal_target(
                target_rules, controller_id, event_item_id
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
            )
            needs_target_choice = bool(
                target_validation_error
                and not clean_targets
                and int(target_rules.get("min") or 0) > 0
            )
            if target_validation_error and not needs_target_choice:
                continue
            if needs_target_choice and event in RULES_ENTRY_EVENTS and self.rules_trigger_has_no_legal_target(
                # a card's own entry: it is the event source (Flower Tender
                # cannot target itself)
                target_rules, controller_id, event_item_id or item_id
            ):
                continue
            if clean_targets:
                clean_targets = self.rules_redirect_targets(controller_id, clean_targets)
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
                            "firstManifestationOnly", "counter", "minCounters",
                            "limboReasons", "container", "targetsConfrontationManifestation",
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
                # Another trigger of the same event already waits for its targets
                # (Borombo losing while the winner also triggers): never overwrite
                # that choice, ask for these targets when the batch reaches it.
                target_choice_pending = (
                    (self.rules_engine.get("pendingChoice") or {}).get("kind")
                    == "trigger_targets"
                )
                if action["optional"] or target_choice_pending:
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
        return self._queue_rules_simultaneous_actions_ready(
            accepted_actions, priority_player_id
        )

    def queue_rules_simultaneous_actions(self, actions, priority_player_id=None):
        """Confirm optional triggers, then queue one simultaneous event atomically."""
        pending = self.rules_engine.get("pendingChoice") or {}
        new_actions = [action for action in actions or [] if isinstance(action, dict)]
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

    def queue_rules_effect_support_entry(self, item, from_zone=None):
        """Queue enter-the-field triggers for a face-up Support put in play by an effect."""
        triggered = self.queue_rules_battlefield_entry_triggers(
            item["cardId"], item["ownerId"], item["id"], True, defer=True,
        )
        triggered.extend(self.queue_rules_support_entry_triggers(
            item, played=False, from_zone=from_zone, defer=True,
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

    def queue_rules_manifestation_entry_watchers(self, item, defer=False):
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
        counters[counter_key] = max(0, int(counters.get(counter_key) or 0) + int(result.get("value") or 0))
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
            temperament = result.get("temperament")
            source_item = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
            if temperament == "source_chosen":
                temperament = (source_item or {}).get("chosenTemperament")
                if temperament not in RULES_TEMPERAMENTS:
                    return {"kind": result.get("kind"), "status": "no_temperament", "amount": 0}
            created = self.add_rules_excess_essence(player_id, [{
                "temperament": temperament,
                "amount": amount,
                "retained": bool(result.get("retained")),
            }])
            exiled = False
            counter_name = result.get("exileSourceIfNoCounter")
            if counter_name and source_item is not None:
                held = sum(
                    int(v or 0) for k, v in (source_item.get("counters") or {}).items()
                    if str(k).casefold() == str(counter_name).casefold()
                )
                if held <= 0:
                    self._rules_remove_field_item_by_effect(
                        source_item, source_item.get("ownerId"), "exile", "top", reason="exile",
                    )
                    exiled = True
            return {
                "kind": result.get("kind"),
                "status": "created",
                "playerId": player_id,
                "temperament": temperament,
                "amount": amount,
                "tokens": created,
                **({"sourceExiled": True} if exiled else {}),
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
                "x": 740.0, "y": 800.0 if seat != 1 else 525.0,
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
            elif field_zone == "confrontation":
                self.mark_rules_confrontation_entry(item)
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
            if int(result.get("value") or 0) < 0:
                self.record_rules_power_lost(item["id"])
            elif int(result.get("value") or 0) > 0:
                self.record_rules_power_gained(item["id"])
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
                card_type = self.rules_item_card_rules(item).get("type")
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
                "cardId": found, "x": 740.0, "y": 800.0 if seat != 1 else 525.0,
                "faceUp": True, "rotation": 0.0, "counters": {}, "stackedOn": None,
            }
            self.mark_rules_support_entry(item)
            self.battlefield.append(item)
            self.queue_rules_effect_support_entry(item, "deck")
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
        if result.get("kind") == "choose_hand_will_as_support_manifestation":
            hand = player["zones"]["hand"]
            if not any(self.card_rules.get(c, {}).get("type") in RULES_WILL_TYPES for c in hand):
                return {"kind": result.get("kind"), "status": "no_hand_card"}
            if not action.get("optionalAccepted"):
                return {"kind": result.get("kind"), "status": "declined"}
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "discard_from_hand",
                "playerId": player_id, "count": 1,
                "requireTypes": sorted(RULES_WILL_TYPES),
                "destination": "support_manifestation",
                "actionId": action.get("id"),
                "controllerId": action.get("controllerId"),
                "sourceCardId": (action.get("source") or {}).get("cardId"),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "discard_from_hand", "playerId": player_id,
                "count": 1, "requireTypes": sorted(RULES_WILL_TYPES),
            }
        if result.get("kind") == "extortionist_womb":
            opponents = [pid for pid in self.players if pid != player_id]
            if not opponents:
                return {"kind": result.get("kind"), "status": "no_opponent"}
            chooser_id = opponents[0]
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "binary_choice", "purpose": "womb_show",
                "playerId": chooser_id, "options": ["yes", "no"],
                "headingKey": "rulesWombHeading", "textKey": "rulesWombText",
                "yesKey": "rulesWombYes", "noKey": "rulesWombNo",
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "relatedCardId": (action.get("source") or {}).get("cardId"),
                "controllerId": player_id, "actionId": action.get("id"),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "binary_choice", "playerId": chooser_id,
            }
        if result.get("kind") == "gummo_copy_vessel":
            host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
            vessel = [
                c for c in player["zones"]["receptacle"]
                if self.card_rules.get(c, {}).get("type") == "manifestation"
            ]
            if host is None or not vessel:
                return {"kind": result.get("kind"), "status": "no_vessel_card"}
            if not action.get("optionalAccepted"):
                return {"kind": result.get("kind"), "status": "declined"}
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "reveal_hand_discard", "purpose": "gummo",
                "playerId": player_id, "targetPlayerId": player_id,
                "cardIds": list(dict.fromkeys(vessel)), "sourceItemId": host["id"],
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "actionId": action.get("id"),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "reveal_hand_discard", "playerId": player_id,
            }
        if result.get("kind") == "interzone_becomes_first_manifestation":
            host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
            if host is None or self.rules_field_zone(host) != "interzone":
                return {"kind": result.get("kind"), "status": "target_missing"}
            if not self.rules_item_becomes_first_manifestation(host, player_id):
                return {"kind": result.get("kind"), "status": "target_missing"}
            return {
                "kind": result.get("kind"), "status": "first_manifestation",
                "itemId": host["id"], "cardId": host.get("cardId"),
            }
        if result.get("kind") == "field_becomes_first_manifestation":
            # Juggernut: the Will on the field enters the Confrontation Zone as First Manifestation.
            host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
            if host is None or self.rules_field_zone(host) != "field":
                return {"kind": result.get("kind"), "status": "target_missing"}
            if not self.rules_item_becomes_first_manifestation(host, player_id):
                return {"kind": result.get("kind"), "status": "no_first_slot"}
            return {
                "kind": result.get("kind"), "status": "first_manifestation",
                "itemId": host["id"], "cardId": host.get("cardId"),
            }
        if result.get("kind") == "peek_top_swap":
            deck = player["zones"]["deck"]
            if not deck:
                return {"kind": result.get("kind"), "status": "empty_deck"}
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "peek_top_card", "playerId": player_id,
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "cardId": deck[0], "_cardId": deck[0], "allowSwap": True,
                "handCardIds": list(player["zones"]["hand"]),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "peek_top_card", "playerId": player_id,
            }
        if result.get("kind") == "bottom_hand_card_remove_counters":
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
        if result.get("kind") == "restore_exhausted_targets":
            restored = []
            for entry in action.get("targets") or []:
                item = self.find_battlefield_item(entry.get("itemId"))
                if item is None or int(round(float(item.get("rotation") or 0))) % 180 == 0:
                    continue
                item["rotation"] = 0.0
                restored.append(item["id"])
            return {"kind": result.get("kind"), "status": "restored", "itemIds": restored}
        if result.get("kind") == "obelisk_gift":
            opponents = [pid for pid in self.players if pid != player_id]
            hand = player["zones"]["hand"]
            if not opponents or not any(self.card_rules.get(c, {}).get("type") == "manifestation" for c in hand):
                return {"kind": result.get("kind"), "status": "no_hand_card"}
            if not action.get("optionalAccepted"):
                return {"kind": result.get("kind"), "status": "declined"}
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "discard_from_hand",
                "playerId": player_id, "count": 1, "requireManifestation": True,
                "destination": "obelisk_gift", "chooserId": opponents[0],
                "actionId": action.get("id"),
                "controllerId": action.get("controllerId"),
                "sourceCardId": (action.get("source") or {}).get("cardId"),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "discard_from_hand", "playerId": player_id,
                "count": 1, "requireManifestation": True,
            }
        if result.get("kind") == "slumberer_wakes":
            host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
            if host is None or int((host.get("counters") or {}).get("Sleep") or 0) > 0:
                return {"kind": result.get("kind"), "status": "still_asleep"}
            host["gainsPersist"] = True
            if not self.rules_item_becomes_first_manifestation(host, player_id):
                return {"kind": result.get("kind"), "status": "no_first_slot"}
            return {
                "kind": result.get("kind"), "status": "first_manifestation",
                "itemId": host["id"], "cardId": host.get("cardId"),
            }
        if result.get("kind") == "source_to_winner_vessel":
            host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
            winner_id = (self.rules_engine.get("confrontationResult") or {}).get("winnerId")
            if host is None or winner_id not in self.players:
                return {"kind": result.get("kind"), "status": "target_missing"}
            movement = self._rules_remove_field_item_by_effect(
                host, winner_id, "receptacle", "top", reason="vessel",
            )
            return {"kind": result.get("kind"), "status": "taken", "movement": movement,
                    "winnerId": winner_id}
        if result.get("kind") == "grimoire_place":
            host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
            hand = player["zones"]["hand"]
            wills = [c for c in hand if self.card_rules.get(c, {}).get("type") in RULES_WILL_TYPES]
            if host is None or not wills:
                return {"kind": result.get("kind"), "status": "no_hand_card"}
            if not action.get("optionalAccepted"):
                return {"kind": result.get("kind"), "status": "declined"}
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "discard_from_hand",
                "playerId": player_id, "count": len(wills), "upTo": True,
                "requireTypes": sorted(RULES_WILL_TYPES),
                "destination": "attach_to_source", "sourceItemId": host["id"],
                "actionId": action.get("id"),
                "controllerId": action.get("controllerId"),
                "sourceCardId": (action.get("source") or {}).get("cardId"),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "discard_from_hand", "playerId": player_id,
                "count": len(wills), "upTo": True, "requireTypes": sorted(RULES_WILL_TYPES),
            }
        if result.get("kind") == "karmapult_sacrifice":
            host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
            target = next((e for e in action.get("targets") or [] if e.get("kind") == "card"), None)
            target_item = self.find_battlefield_item((target or {}).get("itemId"))
            if host is None or target_item is None:
                return {"kind": result.get("kind"), "status": "target_missing"}
            sacrificed = [dict(entry) for entry in host.get("attachedCards") or []]
            host["attachedCards"] = []
            self.rules_sync_attached_counter(host)
            for entry in sacrificed:
                self.put_zone_card(entry["ownerId"], "graveyard", entry["cardId"], entry["ownerId"], "top")
            if sacrificed:
                self.rules_engine["ongoingEffects"].append({
                    "id": new_id(), "actionId": action.get("id"),
                    "abilityId": "karmapult-power-loss",
                    "controllerId": action.get("controllerId") or player_id,
                    "source": {"cardId": host.get("cardId"), "itemId": host["id"], "zone": "battlefield"},
                    "target": {
                        "kind": "card", "itemId": target_item["id"],
                        "cardId": target_item.get("cardId"), "ownerId": target_item.get("ownerId"),
                    },
                    "kind": "power_modifier", "value": -len(sacrificed),
                    "duration": "until_end_of_turn",
                    "startedTurn": self.phase_tracker["turn"],
                })
            return {
                "kind": result.get("kind"), "status": "sacrificed" if sacrificed else "nothing_placed",
                "count": len(sacrificed), "cardIds": [e["cardId"] for e in sacrificed],
                "itemId": target_item["id"], "value": -len(sacrificed),
            }
        if result.get("kind") == "bullyboo_reveal":
            hand = player["zones"]["hand"]
            if not any(self.card_rules.get(c, {}).get("type") in RULES_WILL_TYPES for c in hand):
                return {"kind": result.get("kind"), "status": "no_hand_card"}
            if not action.get("optionalAccepted"):
                return {"kind": result.get("kind"), "status": "declined"}
            opponents = [pid for pid in self.players if pid != player_id]
            if not opponents:
                return {"kind": result.get("kind"), "status": "no_opponent"}
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "discard_from_hand",
                "playerId": player_id, "count": 1,
                "requireTypes": sorted(RULES_WILL_TYPES),
                "destination": "bullyboo_reveal", "chooserId": opponents[0],
                "actionId": action.get("id"),
                "controllerId": action.get("controllerId"),
                "sourceCardId": (action.get("source") or {}).get("cardId"),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "discard_from_hand", "playerId": player_id,
                "count": 1, "requireTypes": sorted(RULES_WILL_TYPES),
            }
        if result.get("kind") == "amphora_offer":
            hand = player["zones"]["hand"]
            if sum(1 for c in hand if self.card_rules.get(c, {}).get("type") == "manifestation") < 2:
                return {"kind": result.get("kind"), "status": "no_hand_card"}
            if not action.get("optionalAccepted"):
                return {"kind": result.get("kind"), "status": "declined"}
            opponents = [pid for pid in self.players if pid != player_id]
            if not opponents:
                return {"kind": result.get("kind"), "status": "no_opponent"}
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "discard_from_hand",
                "playerId": player_id, "count": 2, "requireManifestation": True,
                "destination": "amphora_offer", "chooserId": opponents[0],
                "actionId": action.get("id"),
                "controllerId": action.get("controllerId"),
                "sourceCardId": (action.get("source") or {}).get("cardId"),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "discard_from_hand", "playerId": player_id,
                "count": 2, "requireManifestation": True,
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
        if result.get("kind") == "tebebe_unearth":
            host_id = (action.get("source") or {}).get("itemId")
            sacrificed = []
            for item in list(self.rules_confrontation_items(player_id, ("interzone",))):
                if item.get("id") == host_id:
                    continue
                if self.card_rules.get(item.get("cardId"), {}).get("type") != "manifestation":
                    continue
                movement = self._rules_remove_field_item_by_effect(
                    item, item.get("ownerId"), "graveyard", "top", reason="sacrifice",
                )
                if movement.get("status") in {"moved", "removed_copy"}:
                    sacrificed.append(item["id"])
            seat = self.players[player_id].get("seat")
            concealed = []
            deck = self.players[player_id]["zones"]["deck"]
            for card_id in list(deck[:3]):
                self.take_zone_card(player_id, "deck", card_id)
                new_item = {
                    "id": new_id(), "ownerId": player_id, "controllerId": player_id,
                    "cardId": card_id, "x": 740.0, "y": 800.0 if seat != 1 else 525.0,
                    "faceUp": False, "rotation": 0.0, "counters": {}, "stackedOn": None,
                    "fieldZone": "field", "concealedWill": True, "tebebeConcealed": True,
                }
                self.battlefield.append(new_item)
                concealed.append(new_item["id"])
            self.prune_rules_ongoing_effects()
            return {
                "kind": result.get("kind"), "status": "unearthed",
                "sacrificed": sacrificed, "concealedItemIds": concealed,
            }
        if result.get("kind") == "spite_upkeep":
            host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
            if host is None or self.rules_field_zone(host) != "stalemate":
                return {"kind": result.get("kind"), "status": "source_missing"}
            counters = host.setdefault("counters", {})
            key = next((k for k in counters if str(k).casefold() == "spite"), "Spite")
            counters[key] = int(counters.get(key) or 0) + 1
            payer_id = self.rules_item_controller_id(host)
            opponent_id = self.other_rules_player_id(payer_id)
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "effect_payment", "playerId": payer_id,
                "payment": "{H}" * counters[key],
                "requirements": self.rules_requirements_from_symbols("{H}" * counters[key]),
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "targetCardId": (action.get("source") or {}).get("cardId"),
                "onDecline": {
                    "kind": "to_opponent_vessel", "itemId": host["id"],
                    "opponentId": opponent_id,
                },
                "actionId": action.get("id"),
                "controllerId": action.get("controllerId"),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "effect_payment", "playerId": payer_id,
                "payment": "{H}" * counters[key],
            }
        if result.get("kind") in {
            "unless_payment_deck_discard", "unless_payment_lose_effects",
            "unless_opponent_payment_lock_support_entries", "unless_payment_exile_source",
        }:
            if result.get("kind") == "unless_payment_exile_source":
                host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
                if host is None:
                    return {"kind": result.get("kind"), "status": "source_missing"}
                payer_id = self.rules_item_controller_id(host)
                on_decline = {"kind": "exile_source", "itemId": host["id"]}
            elif result.get("kind") == "unless_opponent_payment_lock_support_entries":
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
            if (
                container_id != action.get("controllerId")
                and self.rules_vessel_locked(container_id)
            ):
                pool = []
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
        if result.get("kind") == "persuasion_force":
            host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
            opponent_id = self.other_rules_player_id(player_id)
            wills = [
                c for c in self.players[opponent_id]["zones"]["hand"]
                if self.card_rules.get(c, {}).get("type") in RULES_WILL_TYPES
            ]
            if host is None or not wills:
                return {"kind": result.get("kind"), "status": "no_hand_will"}
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "discard_from_hand",
                "playerId": opponent_id, "count": 1, "requireTypes": sorted(RULES_WILL_TYPES),
                "destination": "persuasion_place", "hostItemId": host["id"],
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "actionId": action.get("id"), "controllerId": action.get("controllerId"),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "discard_from_hand", "playerId": opponent_id, "count": 1,
            }
        if result.get("kind") == "persuasion_penalty":
            host_id = (action.get("source") or {}).get("itemId")
            remaining = [
                item for item in self.battlefield
                if item.get("persuaded") and item.get("persuadedBy") == host_id
            ]
            lost = {}
            for item in remaining:
                owner_id = self.rules_item_controller_id(item)
                lost[owner_id] = lost.get(owner_id, 0) + 5
            deltas = {pid: self.adjust_rules_score(pid, -amount) for pid, amount in lost.items()}
            return {"kind": result.get("kind"), "status": "resolved" if deltas else "nothing", "deltas": deltas}
        if result.get("kind") == "lunar_liturgy":
            host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
            if host is None:
                return {"kind": result.get("kind"), "status": "source_missing"}
            if not self.rules_lunar_entries(player_id):
                self.rules_engine["skipEndPhaseTurn"] = self.phase_tracker["turn"]
                movement = self._rules_remove_field_item_by_effect(
                    host, host.get("ownerId"), "graveyard", "top", reason="destroy",
                )
                return {"kind": result.get("kind"), "status": "destroyed", "movement": movement}
            order = [player_id] + [pid for pid in self.players if pid != player_id]
            choice_id = self.rules_lunar_next(
                host["id"], player_id, order,
                (action.get("source") or {}).get("cardId"), action.get("id"),
            )
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "reveal_hand_discard",
                "playerId": self.rules_engine["pendingChoice"]["playerId"],
            }
        if result.get("kind") == "thoughtcutter_surge":
            host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
            count = sum(
                1 for entry in self.rules_engine.get("actionStack") or []
                if entry.get("controllerId") != player_id and entry.get("id") != action.get("id")
            )
            if host is None or count <= 0:
                return {"kind": result.get("kind"), "status": "nothing", "value": 0}
            self.create_rules_ongoing_effects({
                **action,
                "targets": [{"kind": "card", "itemId": host["id"], "cardId": host.get("cardId"), "ownerId": host.get("ownerId")}],
                "ability": {
                    "id": f'{(action.get("ability") or {}).get("id")}:surge',
                    "ongoingEffect": {"kind": "power_modifier", "value": count, "duration": "until_end_of_turn"},
                },
            })
            return {"kind": result.get("kind"), "status": "surged", "value": count}
        if result.get("kind") == "pescojolero_trade":
            opponents = [pid for pid in self.players if pid != player_id]
            if not opponents:
                return {"kind": result.get("kind"), "status": "target_missing"}
            opponent_id = opponents[0]
            points_of = lambda card: int((self.card_points or {}).get(card, 0) or 0)
            moved_points = 0
            moved = []
            for entry in action.get("targets") or []:
                item = self.find_battlefield_item(entry.get("itemId"))
                if (
                    item is None or self.rules_field_zone(item) != "stalemate"
                    or item.get("ownerId") == opponent_id
                    or self.card_rules.get(item.get("cardId"), {}).get("type") != "manifestation"
                ):
                    continue
                movement = self._rules_remove_field_item_by_effect(
                    item, opponent_id, "receptacle", "top", reason="vessel",
                )
                if movement.get("status") == "moved":
                    moved_points += points_of(item.get("cardId"))
                    moved.append(item.get("cardId"))
            if not moved:
                return {"kind": result.get("kind"), "status": "nothing_moved"}
            candidates = [
                card_id for card_id in self.players[opponent_id]["zones"]["receptacle"]
                if self.card_rules.get(card_id, {}).get("type") == "manifestation"
                and points_of(card_id) <= moved_points
            ]
            if not candidates:
                return {"kind": result.get("kind"), "status": "moved_only", "cardIds": moved}
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "reveal_hand_discard", "purpose": "pescojolero",
                "playerId": player_id, "targetPlayerId": opponent_id, "cardIds": candidates,
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "actionId": action.get("id"), "controllerId": action.get("controllerId"),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "reveal_hand_discard", "playerId": player_id,
            }
        if result.get("kind") == "wish_exchange":
            target = next((e for e in action.get("targets") or [] if e.get("kind") == "zone_card"), None)
            mine_id = (target or {}).get("cardId")
            vessel = player["zones"]["receptacle"]
            if mine_id not in vessel:
                return {"kind": result.get("kind"), "status": "target_missing"}
            points_of = lambda card: int((self.card_points or {}).get(card, 0) or 0)
            owner_id = self.card_owner_in_zone(player_id, "receptacle", mine_id)
            if owner_id not in self.players:
                return {"kind": result.get("kind"), "status": "target_missing"}
            candidates = [
                card_id for card_id in self.players[owner_id]["zones"]["receptacle"]
                if self.card_owner_in_zone(owner_id, "receptacle", card_id) == player_id
                and self.card_rules.get(card_id, {}).get("type") == "manifestation"
                and points_of(card_id) >= points_of(mine_id)
                and not (owner_id == player_id and card_id == mine_id)
            ]
            if not candidates:
                return {"kind": result.get("kind"), "status": "owner_cannot"}
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "reveal_hand_discard", "purpose": "wish",
                "playerId": owner_id, "targetPlayerId": owner_id, "cardIds": candidates,
                "casterId": player_id, "chosenCardId": mine_id,
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "actionId": action.get("id"), "controllerId": action.get("controllerId"),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "reveal_hand_discard", "playerId": owner_id,
            }
        if result.get("kind") == "gorlok_peek":
            host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
            opponent_id = self.other_rules_player_id(player_id)
            entry = (self.rules_engine.get("drawnOutsideRecovery") or {}).get(opponent_id) or {}
            hand = self.players[opponent_id]["zones"]["hand"]
            shown = [c for c in entry.get("cardIds") or [] if c in hand] if entry.get("turn") == self.phase_tracker["turn"] else []
            if host is None or not shown:
                return {"kind": result.get("kind"), "status": "nothing_shown"}
            self.rules_engine["drawnOutsideRecovery"].pop(opponent_id, None)
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "reveal_hand_discard", "purpose": "gorlok",
                "playerId": player_id, "targetPlayerId": opponent_id, "cardIds": shown,
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "sourceItemId": host["id"],
                "actionId": action.get("id"), "controllerId": action.get("controllerId"),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "reveal_hand_discard", "playerId": player_id,
            }
        if result.get("kind") == "auction_offer":
            hand = player["zones"]["hand"]
            if not any(self.card_rules.get(c, {}).get("type") == "manifestation" for c in hand):
                return {"kind": result.get("kind"), "status": "no_hand_card"}
            if not action.get("optionalAccepted"):
                return {"kind": result.get("kind"), "status": "declined"}
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "discard_from_hand",
                "playerId": player_id, "count": 1, "requireManifestation": True,
                "destination": "auction_bid",
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "actionId": action.get("id"), "controllerId": action.get("controllerId"),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "discard_from_hand", "playerId": player_id, "count": 1,
            }
        if result.get("kind") == "chabak_support":
            source = action.get("source") or {}
            hand = player["zones"]["hand"]
            others = list(hand)
            if source.get("cardId") in others:
                others.remove(source["cardId"])
            if (
                source.get("cardId") not in hand
                or sum(1 for c in others if self.card_rules.get(c, {}).get("type") == "manifestation") < 2
            ):
                return {"kind": result.get("kind"), "status": "source_missing"}
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "discard_from_hand",
                "playerId": player_id, "count": 2, "requireManifestation": True,
                "destination": "stalemate_for_support",
                "sourceCardId": source.get("cardId"),
                "actionId": action.get("id"),
                "controllerId": action.get("controllerId"),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "discard_from_hand", "playerId": player_id, "count": 2,
            }
        if result.get("kind") == "chabak_wins":
            host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
            if host is None:
                return {"kind": result.get("kind"), "status": "source_missing"}
            returned = []
            for item in list(self.battlefield):
                if (
                    self.rules_field_zone(item) != "confrontation"
                    or self.rules_item_controller_id(item) == player_id
                    or self.card_rules.get(item.get("cardId"), {}).get("type") != "manifestation"
                ):
                    continue
                movement = self._rules_remove_field_item_by_effect(
                    item, item.get("ownerId"), "deck", "bottom", reason="deck",
                )
                if movement.get("status") in {"moved", "removed_copy"}:
                    returned.append(item.get("cardId"))
            exiled = self._rules_remove_field_item_by_effect(
                host, host.get("ownerId"), "exile", "top", reason="exile",
            )
            return {"kind": result.get("kind"), "status": "returned", "cardIds": returned, "movement": exiled}
        if result.get("kind") == "paciphint_swap":
            cards = [entry for entry in action.get("targets") or [] if entry.get("kind") == "card"]
            if len(cards) != 2:
                return {"kind": result.get("kind"), "status": "target_missing"}
            mine = self.find_battlefield_item(cards[0].get("itemId"))
            other = self.find_battlefield_item(cards[1].get("itemId"))
            if mine is None or self.rules_item_controller_id(mine) != player_id:
                return {"kind": result.get("kind"), "status": "target_missing"}
            movement = self._rules_remove_field_item_by_effect(
                mine, mine.get("ownerId"), "deck", "bottom", reason="deck",
            )
            if movement.get("status") != "moved" or other is None:
                return {"kind": result.get("kind"), "status": movement.get("status"), "movement": movement}
            self.create_rules_ongoing_effects({
                **action,
                "targets": [{
                    "kind": "card", "itemId": other["id"], "cardId": other.get("cardId"),
                    "ownerId": other.get("ownerId"),
                }],
                "ability": {
                    "id": f'{(action.get("ability") or {}).get("id")}:ignored',
                    "ongoingEffect": {"kind": "power_ignored", "duration": "until_end_of_turn"},
                },
            })
            return {
                "kind": result.get("kind"), "status": "swapped",
                "movement": movement, "ignoredItemId": other["id"],
            }
        if result.get("kind") == "consul_wins":
            # Moaning Consul: the other friendly Confrontation Manifestations trigger as if they lost, then it goes to an opponent's Vessel.
            host = self.find_battlefield_item((action.get("source") or {}).get("itemId"))
            if host is None:
                return {"kind": result.get("kind"), "status": "source_missing"}
            participant_ids = set((self.rules_engine.get("confrontationResult") or {}).get("participantItemIds") or [])
            queued = []
            for item in list(self.battlefield):
                if (
                    item is host or item.get("id") not in participant_ids
                    or self.rules_item_controller_id(item) != player_id
                    or not self.rules_item_effects_active(item)
                ):
                    continue
                queued.extend(self.queue_rules_triggers(
                    item.get("cardId"), item.get("ownerId"), "loses_confrontation",
                    item_id=item.get("id"), face_up=True, event_controller_id=player_id,
                    defer=True, controller_id=player_id,
                ))
            if queued:
                self.queue_rules_simultaneous_actions(queued)
            opponent_id = self.other_rules_player_id(player_id)
            movement = self._rules_remove_field_item_by_effect(
                host, opponent_id, "receptacle", "top", reason="vessel",
            )
            return {
                "kind": result.get("kind"), "status": movement.get("status"),
                "triggered": len(queued), "movement": movement,
            }
        if result.get("kind") == "ycar_exchange":
            opponents = [pid for pid in self.players if pid != player_id]
            target = next((
                entry for entry in action.get("targets") or [] if entry.get("kind") == "card"
            ), None)
            item = self.find_battlefield_item((target or {}).get("itemId"))
            if (
                not opponents or item is None or self.rules_field_zone(item) != "interzone"
                or item.get("ownerId") in opponents
            ):
                return {"kind": result.get("kind"), "status": "target_missing"}
            opponent_id = opponents[0]
            movement = self._rules_remove_field_item_by_effect(
                item, opponent_id, "receptacle", "top", reason="vessel",
            )
            if movement.get("status") != "moved":
                return {"kind": result.get("kind"), "status": movement.get("status")}
            candidates = sorted(
                card_id for card_id in player["zones"]["deck"]
                if self.card_rules.get(card_id, {}).get("type") == "manifestation"
            )
            if not candidates:
                random.shuffle(player["zones"]["deck"])
                return {"kind": result.get("kind"), "status": "no_cards", "movement": movement}
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "discard_from_hand",
                "playerId": player_id, "count": 1, "upTo": False,
                "candidateCardIds": candidates, "destination": "interzone_from_search",
                "actionId": action.get("id"),
                "controllerId": action.get("controllerId"),
                "sourceCardId": (action.get("source") or {}).get("cardId"),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "discard_from_hand", "playerId": player_id,
                "count": 1, "search": True,
            }
        if result.get("kind") == "exile_source_grant_limbo_will_play":
            # Nghoul-ong: exile it from the Limbo, then an Ephemeral Will of cost <= its base power is free.
            source = action.get("source") or {}
            owner_id = source.get("ownerId") or player_id
            card_id = source.get("cardId")
            if card_id not in self.players.get(owner_id, {}).get("zones", {}).get("graveyard", []):
                return {"kind": result.get("kind"), "status": "source_missing"}
            error, _owner, _replacement = self.move_zone_card_by_effect(
                owner_id, "graveyard", owner_id, "exile", card_id, "top"
            )
            if error:
                return {"kind": result.get("kind"), "status": "error"}
            max_cost = int(self.card_rules.get(card_id, {}).get("power") or 0)
            self.rules_engine["playPermissions"].append({
                "id": new_id(), "abilityId": (action.get("ability") or {}).get("id"),
                "playerId": owner_id, "anyWill": True, "fromZone": "graveyard",
                "phaseIds": list(ADVANCED_PHASES), "asSupport": False,
                "noTribute": True, "exileOnLeave": True,
                "ephemeralOnly": True, "maxCost": max_cost,
                "turn": self.phase_tracker["turn"], "sourceCardId": card_id,
            })
            return {"kind": result.get("kind"), "status": "granted", "playerId": owner_id, "maxCost": max_cost}
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
                "cardId": card_id, "x": 740.0, "y": 800.0 if seat != 1 else 525.0,
                "faceUp": True, "rotation": 0.0, "counters": {}, "stackedOn": None,
            }
            self.mark_rules_support_entry(item)
            self.battlefield.append(item)
            self.queue_rules_effect_support_entry(item)
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
        if result.get("kind") == "set_field_power":
            items = self.rules_confrontation_items(None, ("interzone", "confrontation", "stalemate"))
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
                    "startedTurn": self.phase_tracker["turn"], "value": int(value),
                }
                self.rules_engine["ongoingEffects"].append(effect)
                effect_ids.append(effect["id"])
            return {
                "kind": result.get("kind"), "status": "set" if effect_ids else "nothing",
                "mode": result.get("mode"), "effectIds": effect_ids,
            }
        if result.get("kind") in {"stalemate_targets", "stalemate_target_grant_source_support"}:
            source = action.get("source") or {}
            item_ids = [
                entry.get("itemId") for entry in action.get("targets") or []
                if entry.get("kind") == "card"
            ]
            if result.get("kind") == "stalemate_target_grant_source_support":
                item_ids = [item_id for item_id in item_ids if item_id != source.get("itemId")]
                if not item_ids:
                    return {"kind": result.get("kind"), "status": "target_missing"}
            if result.get("includeSource") and source.get("itemId"):
                item_ids.append(source.get("itemId"))
            moved = []
            for item_id in item_ids:
                item = self.find_battlefield_item(item_id)
                if item is None or self.rules_item_zone_locked(item):
                    continue
                item["stackedOn"] = None
                self.rules_stalemate_item(item_id)
                if result.get("lockZone"):
                    item["zoneLockTurn"] = self.phase_tracker["turn"]
                moved.append(item_id)
            self.prune_rules_ongoing_effects()
            payload = {
                "kind": result.get("kind"),
                "status": "stalemated" if moved else "nothing", "itemIds": moved,
            }
            if result.get("kind") == "stalemate_target_grant_source_support" and moved:
                payload["support"] = self.apply_rules_action_result({
                    **action,
                    "ability": {**(action.get("ability") or {}), "result": {"kind": "grant_source_support_until_end_turn"}},
                })
            return payload
        if result.get("kind") == "grant_support_entry_bonus":
            turn = self.phase_tracker["turn"]
            if result.get("requireLostPrevious") and (
                (self.rules_engine.get("confrontationLosses") or {}).get(str(turn - 1)) != player_id
            ):
                return {"kind": result.get("kind"), "status": "condition_failed"}
            self.rules_engine.setdefault("supportEntryBonuses", []).append({
                "turn": turn, "playerId": player_id, "value": int(result.get("value") or 1),
                "sourceCardId": (action.get("source") or {}).get("cardId"),
            })
            return {"kind": result.get("kind"), "status": "armed", "value": int(result.get("value") or 1)}
        if result.get("kind") == "return_turn_tributes_end_turn":
            turn = self.phase_tracker["turn"]
            memories = []
            for entry in self.rules_engine.get("tributeLog") or []:
                if entry.get("turn") != turn or entry.get("playerId") != player_id:
                    continue
                memory = self.create_rules_effect_memory(
                    entry["ownerId"], entry["cardId"], "return_from_limbo_end_turn",
                    controller_id=player_id, source_action_id=action.get("id"),
                )
                if memory:
                    memories.append(entry["cardId"])
            return {"kind": result.get("kind"), "status": "scheduled" if memories else "nothing", "cardIds": memories}
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
            if not action.get("targets") and not action.get("_limboChosen"):
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
                # the targeted player is the one whose deck was discarded
                "playerId": discarded_player,
                "count": len(discarded), "cardIds": list(discarded),
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
            triggered_actions = self.queue_rules_token_copy_entry_triggers(copy)
            return {
                "kind": result.get("kind"),
                "status": "created",
                "targetItemId": item.get("id"),
                "createdItemId": copy["id"],
                "triggeredActions": triggered_actions,
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
                    "effectSourceCardId": (action.get("source") or {}).get("cardId"),
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
        if result.get("kind") == "protect_related_will":
            trigger = (action.get("ability") or {}).get("trigger") or {}
            related = next((
                entry for entry in self.rules_engine.get("actionStack") or []
                if entry.get("id") == trigger.get("relatedActionId")
                and entry.get("kind") == "play_card"
                and (entry.get("source") or {}).get("zone") == "hand"
                and self.card_rules.get(
                    (entry.get("source") or {}).get("cardId"), {}
                ).get("type") in RULES_WILL_TYPES
            ), None)
            if related is None:
                return {"kind": result.get("kind"), "status": "related_action_not_hand_will"}
            related["cannotBeNeutralized"] = True
            related_source = related.get("source") or {}
            if self.card_rules.get(related_source.get("cardId"), {}).get("type") == "persistent_will":
                self.rules_engine["ongoingEffects"].append({
                    "id": new_id(), "actionId": action.get("id"),
                    "abilityId": (action.get("ability") or {}).get("id"),
                    "controllerId": related.get("controllerId"),
                    "source": {"cardId": (action.get("source") or {}).get("cardId")},
                    "target": {
                        "kind": "stack_action", "actionId": related.get("id"),
                        "cardId": related_source.get("cardId"),
                        "ownerId": related_source.get("ownerId"),
                    },
                    "kind": "protection", "fromOpponents": True,
                    "duration": "until_end_of_turn",
                    "startedTurn": self.phase_tracker["turn"],
                })
            return {
                "kind": result.get("kind"), "status": "protected",
                "actionId": related.get("id"),
                "cardId": related_source.get("cardId"),
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
            if (
                result.get("onZeroTemperament") in RULES_TEMPERAMENTS
                and counters[counter_key] == 0 and int(result.get("value") or 0) < 0
            ):
                source_item["temperamentOverride"] = result["onZeroTemperament"]
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
                "x": 740.0, "y": 800.0 if seat != 1 else 525.0,
                "faceUp": True, "rotation": 0.0, "counters": {},
                "stackedOn": None,
            }
            self.mark_rules_support_entry(item)
            if result.get("winDestination") == "exile":
                item["supportWinDestination"] = "exile"
            if result.get("losesEffects"):
                item["effectsDisabled"] = True
            if result.get("exileInsteadOfLeaving"):
                item["exileInsteadOfLeaving"] = True
            self.battlefield.append(item)
            return {
                "kind": result.get("kind"),
                "status": "moved",
                "itemId": item["id"],
                "cardId": item["cardId"],
                "ownerId": owner_id,
                "controllerId": player_id,
            }
        if result.get("kind") == "distribute_power":
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
        if result.get("kind") == "reveal_hand_discard_choice":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "player"
            ), None)
            target_id = (target or {}).get("playerId")
            if target_id not in self.players:
                return {"kind": result.get("kind"), "status": "target_missing"}
            lost = 0
            if int(result.get("scoreCost") or 0):
                lost = -self.adjust_rules_score(
                    player_id, -int(result["scoreCost"])
                )
            if self.rules_hand_is_immune(target_id, player_id):
                return {
                    "kind": result.get("kind"), "status": "prevented_immunity",
                    "playerId": target_id, "lost": lost,
                }
            hand = list(self.players[target_id]["zones"]["hand"])
            if not hand:
                return {
                    "kind": result.get("kind"), "status": "empty_hand",
                    "playerId": target_id, "lost": lost, "cardIds": [],
                }
            choice = {
                "id": new_id(), "kind": "reveal_hand_discard",
                "playerId": player_id, "targetPlayerId": target_id,
                "cardIds": hand,
                "sourceCardId": (action.get("source") or {}).get("cardId"),
            }
            self.rules_engine["pendingChoice"] = choice
            return {
                "kind": "choice_required", "choiceId": choice["id"],
                "choiceKind": "reveal_hand_discard", "playerId": player_id,
                "targetPlayerId": target_id, "lost": lost,
            }
        if result.get("kind") == "play_vessel_target_as_support":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "zone_card"
            ), None)
            container_id = (target or {}).get("containerId")
            card_id = (target or {}).get("cardId")
            owner_id = (
                self.card_owner_in_zone(container_id, "receptacle", card_id)
                if container_id in self.players else None
            )
            if owner_id is None:
                return {"kind": result.get("kind"), "status": "target_missing"}
            self.take_zone_card(container_id, "receptacle", card_id)
            seat = self.players[player_id].get("seat")
            item = {
                "id": new_id(), "ownerId": owner_id,
                "controllerId": player_id, "cardId": card_id,
                "x": 740.0, "y": 800.0 if seat != 1 else 525.0,
                "faceUp": True, "rotation": 0.0, "counters": {},
                "stackedOn": None,
                "supportReturn": {"controllerId": player_id},
            }
            self.mark_rules_support_entry(item)
            self.battlefield.append(item)
            return {
                "kind": result.get("kind"), "status": "moved",
                "itemId": item["id"], "cardId": card_id,
                "ownerId": owner_id, "controllerId": player_id,
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
            if result.get("targetPlayer"):
                chosen = next((
                    entry.get("playerId") for entry in action.get("targets") or []
                    if entry.get("kind") == "player"
                ), None)
                if chosen not in self.players:
                    return {"kind": "reorder_top_decks", "status": "target_missing"}
                target_player_ids = [chosen]
            groups = []
            for target_player_id in target_player_ids:
                card_ids = list(
                    self.players[target_player_id]["zones"]["deck"][:count]
                )
                if card_ids:
                    groups.append({
                        "playerId": target_player_id,
                        "cardIds": card_ids,
                        "topCount": result.get("topCount"),
                        "bottomCount": result.get("bottomCount"),
                        **({
                            "extraSide": result["extraSide"],
                            "extraMin": int(result.get("extraMin") or 0),
                            "extraMax": int(result.get("extraMax") or 0),
                        } if result.get("extraSide") else {}),
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
            triggered_actions = self.queue_rules_token_copy_entry_triggers(copy)
            return {
                "kind": result.get("kind"),
                "status": "resolved",
                "movement": movement,
                "copyItemId": copy["id"],
                "triggeredActions": triggered_actions,
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
                triggered_actions = self.queue_rules_token_copy_entry_triggers(copy)
                return {
                    "kind": result.get("kind"),
                    "status": "accepted",
                    "playerId": player_id,
                    "relatedCardId": related_card_id,
                    "createdItemId": copy["id"],
                    "triggeredActions": triggered_actions,
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
            triggered_actions = []
            for created_item in created:
                triggered_actions.extend(
                    self.queue_rules_token_copy_entry_triggers(created_item)
                )
            return {
                "kind": result.get("kind"),
                "status": "created",
                "createdItemIds": [item["id"] for item in created],
                "triggeredActions": triggered_actions,
            }
        if result.get("kind") == "take_last_opponent_support_to_vessel":
            item = self.rules_last_opponent_support(player_id, 2)
            if item is None:
                return {"kind": result.get("kind"), "status": "target_missing"}
            if item.get("ownerId") == player_id:
                return {"kind": result.get("kind"), "status": "own_card"}
            movement = self._rules_remove_field_item_by_effect(item, player_id, "receptacle", "top", reason="vessel")
            return {"kind": result.get("kind"), "status": "taken", "movement": movement}
        if result.get("kind") == "grant_free_will_play":
            owner_id = (action.get("source") or {}).get("ownerId") or player_id
            if owner_id not in self.players:
                return {"kind": result.get("kind"), "status": "target_missing"}
            self.rules_engine["playPermissions"].append({
                "id": new_id(), "abilityId": (action.get("ability") or {}).get("id"),
                "playerId": owner_id, "anyWill": True, "fromZone": "hand",
                "phaseIds": list(ADVANCED_PHASES), "asSupport": False,
                "noTribute": True, "turn": self.phase_tracker["turn"],
                "sourceCardId": (action.get("source") or {}).get("cardId"),
            })
            return {"kind": result.get("kind"), "status": "granted", "playerId": owner_id}
        if result.get("kind") in {
            "will_becomes_support_manifestation", "put_hand_will_as_support_manifestation",
        }:
            from_hand = result.get("kind") == "put_hand_will_as_support_manifestation"
            if self.rules_support_entry_locked(player_id):
                return {"kind": result.get("kind"), "status": "prevented"}
            if from_hand:
                target = next((
                    entry for entry in action.get("targets") or []
                    if entry.get("kind") == "zone_card"
                ), None)
                card_id = (target or {}).get("cardId")
                owner_id = self.card_owner_in_zone(player_id, "hand", card_id) if card_id else None
                if (
                    owner_id is None
                    or self.card_rules.get(card_id, {}).get("type") not in RULES_WILL_TYPES
                    or not self.take_zone_card(player_id, "hand", card_id)
                ):
                    return {"kind": result.get("kind"), "status": "target_missing"}
                seat = self.players[player_id].get("seat")
                item = {
                    "id": new_id(), "ownerId": owner_id,
                    "controllerId": player_id, "cardId": card_id,
                    "x": 740.0, "y": 800.0 if seat != 1 else 525.0,
                    "faceUp": True, "rotation": 0.0, "counters": {},
                    "stackedOn": None,
                    # Put onto the field, not played: its own effects stay off.
                    "effectsDisabled": True,
                }
                self.battlefield.append(item)
                outcomes = {"onWin": "free_play", "onLoss": "exile", "onStalemate": "exile"}
            else:
                target = next((
                    entry for entry in action.get("targets") or []
                    if entry.get("kind") == "card"
                ), None)
                item = self.find_battlefield_item((target or {}).get("itemId"))
                if (
                    item is None
                    or self.rules_item_card_rules(item).get("type") != "persistent_will"
                    or self.rules_item_controller_id(item) != player_id
                    or self.rules_field_zone(item) != "field"
                    or item.get("willManifestation")
                ):
                    return {"kind": result.get("kind"), "status": "target_missing"}
                outcomes = {"onWin": "revert", "onLoss": "destroy", "onStalemate": "revert"}
            will_cost = self.rules_will_tribute_cost(item.get("cardId"))
            item["willManifestation"] = {
                "power": will_cost, "turn": self.phase_tracker["turn"], **outcomes,
            }
            item["controllerId"] = player_id
            item["stackedOn"] = None
            self.mark_rules_support_entry(item)
            triggered = self.queue_rules_support_entry_triggers(
                item, played=False, from_zone="hand" if from_hand else "field", defer=True,
            )
            triggered.extend(self.queue_rules_field_zone_entry_triggers(
                item, "confrontation", defer=True,
            ))
            if triggered:
                self.queue_rules_simultaneous_actions(triggered)
            return {
                "kind": result.get("kind"), "status": "moved",
                "itemId": item["id"], "cardId": item.get("cardId"), "power": will_cost,
            }
        if result.get("kind") == "search_deck_will_conceal":
            wills = sorted(
                card_id for card_id in player["zones"]["deck"]
                if self.card_rules.get(card_id, {}).get("type") in RULES_WILL_TYPES
            )
            if not wills:
                random.shuffle(player["zones"]["deck"])
                return {"kind": result.get("kind"), "status": "no_cards"}
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "discard_from_hand",
                "playerId": player_id, "count": 1, "upTo": False,
                "candidateCardIds": wills,
                "destination": "concealed_field",
                "jigonItemId": (action.get("source") or {}).get("itemId"),
                "actionId": action.get("id"),
                "controllerId": action.get("controllerId"),
                "sourceCardId": (action.get("source") or {}).get("cardId"),
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "discard_from_hand", "playerId": player_id,
                "count": 1, "search": True,
            }
        if result.get("kind") == "free_concealed_wills":
            source_id = (action.get("source") or {}).get("itemId")
            freed = []
            for item in self.battlefield:
                if item.get("concealedWill") and item.get("jigonItemId") == source_id:
                    item["concealedFree"] = True
                    freed.append(item["id"])
            return {"kind": result.get("kind"), "status": "freed", "itemIds": freed}
        if result.get("kind") == "hold_winner_manifestations":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "player"
            ), None)
            target_id = (target or {}).get("playerId")
            confrontation = self.rules_engine.get("confrontationResult") or {}
            if (
                target_id not in self.players
                or confrontation.get("turn") != self.phase_tracker["turn"]
                or confrontation.get("stalemate")
                or confrontation.get("winnerId") != target_id
            ):
                return {"kind": result.get("kind"), "status": "not_winner"}
            held = []
            for item in self.rules_confrontation_items_owned_by(target_id, ("confrontation",)):
                item["holdUntilResolution"] = self.phase_tracker["turn"] + 1
                held.append(item["id"])
            return {"kind": result.get("kind"), "status": "held", "itemIds": held}
        if result.get("kind") == "grant_limbo_will_play":
            owner_id = (action.get("source") or {}).get("ownerId") or player_id
            if owner_id not in self.players:
                return {"kind": result.get("kind"), "status": "target_missing"}
            self.rules_engine["playPermissions"].append({
                "id": new_id(), "abilityId": (action.get("ability") or {}).get("id"),
                "playerId": owner_id, "anyWill": True, "fromZone": "graveyard",
                "phaseIds": [self.current_phase_id()], "asSupport": False,
                "noTribute": True, "exileOnLeave": True,
                "turn": self.phase_tracker["turn"],
                "sourceCardId": (action.get("source") or {}).get("cardId"),
            })
            return {"kind": result.get("kind"), "status": "granted", "playerId": owner_id}
        if result.get("kind") == "lose_points_shuffle_source_into_deck":
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
        if result.get("kind") == "lose_excess_essence_or_points":
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
        if result.get("kind") == "lock_next_turn_draws":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "player"
            ), None)
            target_id = (target or {}).get("playerId")
            if target_id not in self.players:
                return {"kind": result.get("kind"), "status": "target_missing"}
            turn = self.phase_tracker["turn"] + 1
            self.rules_engine["drawLocks"] = [
                entry for entry in self.rules_engine.get("drawLocks") or []
                if entry.get("turn") >= self.phase_tracker["turn"]
            ] + [{
                "playerId": target_id, "turn": turn,
                "sourceCardId": (action.get("source") or {}).get("cardId"),
            }]
            return {
                "kind": result.get("kind"), "status": "scheduled",
                "playerId": target_id, "turn": turn,
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
        if result.get("kind") == "roll_d6_each_target":
            rolls = []
            hits = []
            for target in action.get("targets") or []:
                if target.get("kind") != "card":
                    continue
                roll = random.randint(1, 6)
                hit = roll in {1, 6}
                entry = {"cardId": target.get("cardId"), "itemId": target.get("itemId"), "roll": roll, "hit": hit}
                rolls.append(roll)
                if hit and result.get("onHit") == "destroy":
                    if self.find_battlefield_item(target.get("itemId")) is None:
                        entry["status"] = "target_missing"
                    else:
                        entry["movement"] = self.apply_rules_action_result({
                            **action,
                            "targets": [dict(target)],
                            "ability": {
                                **(action.get("ability") or {}),
                                "result": {"kind": "move_target", "zone": "graveyard", "position": "top", "reason": "destroy"},
                            },
                        })
                hits.append(entry)
            payload = {
                "kind": "roll_d6_each_target", "status": "resolved", "onHit": result.get("onHit"),
                "rolls": rolls, "results": hits, "hitCount": sum(entry["hit"] for entry in hits),
            }
            if result.get("onHit") == "points":
                payload["playerId"] = player_id
                payload["delta"] = self.adjust_rules_score(player_id, int(result.get("points") or 0) * payload["hitCount"])
                payload["score"] = self.players.get(player_id, {}).get("score")
            return payload
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
            confrontation = None
            if qualifies:
                self.rules_engine["forcedConfrontationWinnerId"] = controller_id
                self.phase_tracker["index"] = ADVANCED_PHASES.index(
                    "resolution_compare"
                )
                self.rules_engine["priorityPasses"] = []
                confrontation = self.prepare_rules_confrontation_result()
            return {
                "kind": result.get("kind"),
                "status": "forced" if qualifies else "condition_failed",
                "playerId": controller_id,
                "basePower": source_power,
                "highestBasePower": highest,
                "phaseId": self.current_phase_id(),
                "confrontationResult": confrontation,
            }
        if result.get("kind") == "stalemate_unless_opponent_pays":
            controller_id = action.get("controllerId")
            opponent_id = self.other_rules_player_id(controller_id)
            first_ids = self.rules_engine.get("firstManifestationItemIds", {})
            powers = {}
            for pid in (controller_id, opponent_id):
                first = self.find_battlefield_item(first_ids.get(pid))
                if first is not None:
                    powers[pid] = int(self.card_rules.get(first.get("cardId"), {}).get("power") or 0)
            if (
                controller_id not in powers or opponent_id not in powers
                or powers[controller_id] >= powers[opponent_id]
            ):
                return {"kind": result.get("kind"), "status": "condition_failed", "powers": powers}
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "immediate_effect_payment", "playerId": opponent_id,
                "payment": result.get("payment"),
                "requirements": self.rules_requirements_from_symbols(result.get("payment")),
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "actionId": action.get("id"),
                "controllerId": controller_id,
                "stalemateOnDecline": True,
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "immediate_effect_payment", "playerId": opponent_id,
                "payment": result.get("payment"),
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
                        data={
                            "itemId": item.get("id"),
                            "sourceCardId": (action.get("source") or {}).get("cardId"),
                            "sourceOwnerId": (
                                (action.get("source") or {}).get("ownerId")
                                or player_id
                            ),
                        },
                    )
                    if memory:
                        memory_ids.append(memory["id"])
            # played during the Resolution (Dominate the Aspects in the
            # Effects step): the "at the Resolution" return was already
            # collected for this turn, so it fires right away, before the
            # cards are moved by the outcome of the Confrontation.
            resolution_triggers = (
                self.queue_rules_resolution_memory_triggers(defer=True)
                if memory_ids and self.current_phase_id() == "resolution_effects"
                else []
            )
            return {
                "kind": "exchange_control_targets",
                "status": "exchanged",
                **({"resolutionTriggers": resolution_triggers} if resolution_triggers else {}),
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
        if (
            result.get("kind") == "resolve_effect_memory"
            and len(result.get("memoryIds") or []) > 1
        ):
            results = []
            for memory_id in result["memoryIds"]:
                single = dict(action)
                single["ability"] = {
                    **(action.get("ability") or {}),
                    "result": {"kind": "resolve_effect_memory", "memoryId": memory_id},
                }
                results.append(self.apply_rules_action_result(single) or {})
            moved = [entry for entry in results if entry.get("movement")]
            return {
                "kind": "resolve_effect_memory",
                "status": "moved" if moved else (results[0].get("status") if results else "memory_missing"),
                "memoryIds": list(result["memoryIds"]),
                "cardIds": [entry.get("cardId") for entry in results if entry.get("cardId")],
                "results": results,
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
                if not self.rules_player_lost_confrontation_this_turn(memory.get("controllerId")):
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
        if result.get("kind") == "choose_source_temperament":
            source = action.get("source") or {}
            item = self.find_battlefield_item(source.get("itemId"))
            if item is None:
                return {"kind": result.get("kind"), "status": "source_missing"}
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
        if result.get("kind") == "cancel_target_stack_effect":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "stack_effect"
            ), None)
            target_action = next((
                entry for entry in self.rules_engine.get("actionStack") or []
                if target and entry.get("id") == target.get("actionId")
            ), None)
            if target_action is None:
                return {"kind": result.get("kind"), "status": "target_missing"}
            countered = self.counter_rules_stack_action(target_action, "cancel")
            return {"kind": result.get("kind"), **(countered or {"status": "target_missing"})}
        if result.get("kind") == "retarget_stack_action":
            stack_entry = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") in {"stack_action", "stack_effect", "stack_item"}
            ), None)
            new_target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "card"
            ), None)
            target_action = next((
                entry for entry in self.rules_engine.get("actionStack") or []
                if stack_entry and entry.get("id") == stack_entry.get("actionId")
            ), None)
            if target_action is None or new_target is None:
                return {"kind": result.get("kind"), "status": "target_missing"}
            error = self.rules_retarget_error([stack_entry, new_target])
            if error:
                return {"kind": result.get("kind"), "status": "invalid_target", "error": error}
            replaced = False
            updated = []
            for entry in target_action.get("targets") or []:
                if not replaced and entry.get("kind") == "card":
                    updated.append(dict(new_target))
                    replaced = True
                else:
                    updated.append(entry)
            target_action["targets"] = updated
            if isinstance(target_action.get("target"), dict) and target_action["target"].get("kind") == "card":
                target_action["target"] = dict(new_target)
            return {
                "kind": result.get("kind"), "status": "retargeted",
                "actionId": target_action.get("id"),
                "cardId": (target_action.get("source") or {}).get("cardId"),
                "newTarget": dict(new_target),
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
            if result.get("refundEssence") and countered.get("status") != "prevented":
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
            if result.get("permanent"):
                # "not lost at the Resolution": these tokens stay and can only go to the Interzone
                for token in created:
                    token["permanent"] = True
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
                    self.rules_item_card_rules(item).get("type")
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
            if result.get("eachPlayer"):
                moves = [
                    self._move_random_zone_card(container_id, result)
                    for container_id in list(self.players)
                ]
                return {"kind": "move_card", "status": "moved", "random": True, "each": moves}
            target = next(
                (entry for entry in action.get("targets") or [] if entry.get("kind") == "player"),
                None,
            )
            return self._move_random_zone_card(target.get("playerId") if target else None, result)
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
        if result.get("kind") == "disable_source_effects":
            source_item = self.find_battlefield_item(
                (action.get("source") or {}).get("itemId")
            )
            if source_item is None:
                return {"kind": result.get("kind"), "status": "source_missing"}
            source_item["effectsDisabled"] = True
            self.prune_rules_ongoing_effects()
            return {
                "kind": result.get("kind"), "status": "disabled",
                "itemId": source_item["id"], "cardId": source_item.get("cardId"),
            }
        if result.get("kind") == "move_hand_source_to_interzone":
            source = action.get("source") or {}
            owner_id = source.get("ownerId") or player_id
            card_id = source.get("cardId")
            if owner_id not in self.players or card_id not in self.players[
                owner_id
            ]["zones"]["hand"]:
                return {"kind": result.get("kind"), "status": "source_missing"}
            if (
                self.rules_interzone_slot_count(owner_id)
                >= self.rules_interzone_capacity(owner_id)
            ):
                return {"kind": result.get("kind"), "status": "no_space"}
            self.take_zone_card(owner_id, "hand", card_id)
            position = self.clean_rules_board_position(None)
            item = {
                "id": new_id(), "ownerId": owner_id, "controllerId": owner_id,
                "cardId": card_id, "x": position["x"], "y": position["y"],
                "faceUp": True, "rotation": 0.0, "counters": {},
                "rarity": (self.players.get(owner_id) or {}).get(
                    "cardRarities", {}
                ).get(card_id),
                "stackedOn": None, "fieldZone": "interzone",
            }
            self.mark_rules_interzone_entry(item)
            self.battlefield.append(item)
            triggered_actions = self.queue_rules_battlefield_entry_triggers(
                card_id, owner_id, item["id"], True, defer=True,
            )
            triggered_actions.extend(self.queue_rules_field_zone_entry_triggers(
                item, "interzone", defer=True,
            ))
            triggered_actions.extend(
                self.queue_rules_manifestation_entry_watchers(item, defer=True)
            )
            if triggered_actions:
                self.queue_rules_simultaneous_actions(triggered_actions)
            return {
                "kind": result.get("kind"), "status": "moved",
                "cardId": card_id, "itemId": item["id"],
                "triggeredActions": triggered_actions,
            }
        if result.get("kind") == "create_event_token_copy_in_support":
            trigger = (action.get("ability") or {}).get("trigger") or {}
            event_item = self.find_battlefield_item(trigger.get("eventItemId"))
            if (
                event_item is None
                or event_item.get("isTokenCard") or event_item.get("isCopy")
                or event_item.get("isTokenCopy")
                or self.card_rules.get(event_item.get("cardId"), {}).get("type")
                != "manifestation"
            ):
                return {"kind": result.get("kind"), "status": "not_applicable"}
            copy = self.create_rules_token_copy(
                event_item["cardId"], action.get("controllerId") or player_id,
                source_item_id=(action.get("source") or {}).get("itemId"),
            )
            triggered_actions = self.queue_rules_token_copy_entry_triggers(copy)
            return {
                "kind": result.get("kind"), "status": "created",
                "cardId": copy.get("cardId"), "itemId": copy["id"],
                "triggeredActions": triggered_actions,
            }
        if result.get("kind") == "clemency_choice":
            trigger = (action.get("ability") or {}).get("trigger") or {}
            chooser_id = trigger.get("eventControllerId")
            gain = int(result.get("value") or 0)
            if chooser_id not in self.players:
                delta = self.adjust_rules_score(player_id, gain)
                return {"kind": result.get("kind"), "status": "gained", "delta": delta}
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "clemency_choice", "playerId": chooser_id,
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "sourceItemId": (action.get("source") or {}).get("itemId"),
                "sourceControllerId": action.get("controllerId"),
                "relatedActionId": trigger.get("relatedActionId"),
                "relatedCardId": trigger.get("relatedCardId"),
                "points": gain, "options": ["allow", "neutralize"],
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "clemency_choice", "playerId": chooser_id,
                "points": gain,
            }
        if result.get("kind") in {"declare_name_top_card_power", "declare_name_search_deck"}:
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "player"
            ), None)
            target_id = (target or {}).get("playerId") or player_id
            if target_id not in self.players:
                return {"kind": result.get("kind"), "status": "target_missing"}
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
        if result.get("kind") == "offer_support_else_chain":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") == "card"
            ), None)
            item = self.find_battlefield_item((target or {}).get("itemId"))
            if item is None or self.rules_field_zone(item) != "interzone":
                return {"kind": result.get("kind"), "status": "target_missing"}
            chooser_id = self.rules_item_controller_id(item)
            if chooser_id not in self.players:
                return {"kind": result.get("kind"), "status": "target_missing"}
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "binary_choice", "purpose": "support_else_chain",
                "playerId": chooser_id, "options": ["yes", "no"],
                "headingKey": "rulesSupportElseChainHeading",
                "textKey": "rulesSupportElseChainText",
                "yesKey": "rulesSupportElseChainYes", "noKey": "rulesSupportElseChainNo",
                "sourceCardId": (action.get("source") or {}).get("cardId"),
                "relatedCardId": item.get("cardId"),
                "targetItemId": item.get("id"),
                "controllerId": action.get("controllerId"),
                "_action": {
                    "id": action.get("id"), "controllerId": action.get("controllerId"),
                    "source": dict(action.get("source") or {}),
                },
            }
            return {
                "kind": "choice_required", "choiceId": choice_id,
                "choiceKind": "binary_choice", "playerId": chooser_id,
            }
        if result.get("kind") == "return_first_then_chain":
            first = self.find_battlefield_item(
                (self.rules_engine.get("firstManifestationItemIds") or {}).get(player_id)
            )
            if first is None or self.rules_item_zone_locked(first):
                return {"kind": result.get("kind"), "status": "no_first_manifestation"}
            owner_id = first.get("ownerId")
            card_id = first.get("cardId")
            movement = self._rules_remove_field_item_by_effect(
                first, owner_id, "hand", "top"
            )
            if movement.get("status") == "moved":
                self.rules_engine["playRestrictions"].append({
                    "id": new_id(), "playerId": owner_id, "cardId": card_id,
                    "turn": self.phase_tracker["turn"],
                    "sourceActionId": action.get("id"),
                })
            self.prune_rules_ongoing_effects()
            chain = self.begin_rules_chain_sequence(
                player_id, [player_id],
                {"kind": "chain_from_zone", "zone": "hand", "optional": False},
                action,
            )
            return {**chain, "returned": {
                "status": movement.get("status"), "cardId": card_id,
                "ownerId": owner_id, "playRestrictedUntilTurnEnd": True,
            }}
        if result.get("kind") == "exile_source_take_control_to_interzone":
            target = next((
                entry for entry in action.get("targets") or []
                if entry.get("kind") in {"card", "zone_card"}
            ), None)
            source_item = self.find_battlefield_item(
                (action.get("source") or {}).get("itemId")
            )
            if target is None or source_item is None:
                return {"kind": result.get("kind"), "status": "target_missing"}
            if target.get("kind") == "zone_card" and (
                self.rules_interzone_slot_count(player_id)
                >= self.rules_interzone_capacity(player_id)
                and not self.rules_interzone_share_anchor(player_id, {
                    "id": "incoming", "cardId": target.get("cardId"),
                    "ownerId": target.get("ownerId"),
                })
            ):
                return {"kind": result.get("kind"), "status": "interzone_full"}
            if target.get("kind") == "card":
                taken = self.find_battlefield_item(target.get("itemId"))
                if (
                    taken is None
                    or self.rules_field_zone(taken) != "interzone"
                    or self.rules_item_controller_id(taken) == player_id
                    or self.rules_item_zone_locked(taken)
                    or self.card_rules.get(taken.get("cardId"), {}).get("type") != "manifestation"
                ):
                    return {"kind": result.get("kind"), "status": "target_missing"}
                if (
                    self.rules_interzone_slot_count(player_id)
                    >= self.rules_interzone_capacity(player_id)
                    and not self.rules_interzone_share_anchor(player_id, taken)
                ):
                    return {"kind": result.get("kind"), "status": "interzone_full"}
            exiled = self._rules_remove_field_item_by_effect(
                source_item, source_item.get("ownerId"), "exile", "top",
                reason="exile",
            )
            payload = {
                "kind": result.get("kind"), "status": "taken", "exiled": exiled,
                "cardId": target.get("cardId"),
            }
            if target.get("kind") == "zone_card":
                payload["movement"] = self.apply_rules_action_result({
                    **action,
                    "ability": {**(action.get("ability") or {}), "result": {
                        "kind": "move_zone_target_to_field_zone",
                        "fieldZone": "interzone",
                    }},
                })
                return payload
            if self.rules_interzone_slot_count(player_id) >= self.rules_interzone_capacity(player_id):
                anchor = self.rules_interzone_share_anchor(player_id, taken)
                taken.update({
                    "stackedOn": anchor, "stackOffsetX": 18.0, "stackOffsetY": 18.0,
                })
            else:
                taken["stackedOn"] = None
            taken["controllerId"] = player_id
            taken["fieldZone"] = "interzone"
            taken["isSupport"] = False
            self.mark_rules_interzone_entry(taken)
            self.prune_rules_ongoing_effects()
            payload["itemId"] = taken["id"]
            return payload
        if result.get("kind") == "destroy_vessel_target_owner_sacrifices":
            destroyed = self.apply_rules_action_result({
                **action,
                "ability": {**(action.get("ability") or {}), "result": {
                    "kind": "move_target", "zone": "graveyard",
                    "position": "top", "reason": "destroy",
                }},
            })
            if not destroyed or destroyed.get("status") not in {"moved", "suspended"}:
                return {"kind": result.get("kind"), "status": "target_missing",
                        "destroyed": destroyed}
            sacrificer_id = destroyed.get("ownerId")
            candidates = [
                item["id"] for item in self.battlefield
                if self.rules_item_controller_id(item) == sacrificer_id
                and self.rules_item_card_rules(item).get("type") == "manifestation"
                and not self.rules_item_zone_locked(item)
            ]
            payload = {
                "kind": result.get("kind"), "status": "destroyed",
                "destroyed": destroyed, "sacrificerId": sacrificer_id,
            }
            if len(candidates) == 1:
                picked = self.find_battlefield_item(candidates[0])
                payload["sacrificed"] = self._rules_remove_field_item_by_effect(
                    picked, picked.get("ownerId"), "graveyard", "top",
                    reason="sacrifice",
                )
                self.prune_rules_ongoing_effects()
            elif candidates:
                choice = self.rules_next_pick_own_item_choice(
                    [{"playerId": sacrificer_id, "candidateItemIds": candidates}],
                    action.get("id"), (action.get("source") or {}).get("cardId"),
                    [], purpose="sacrifice",
                )
                payload.update({
                    "kind": "choice_required", "choiceId": choice["id"],
                    "choiceKind": "pick_own_item", "playerId": sacrificer_id,
                    "purpose": "sacrifice",
                })
            return payload
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

        if choice.get("kind") == "pick_distribution_extra":
            if item_id not in choice.get("candidateItemIds", []):
                return "Choose one of the targets.", None
            action = choice.get("_action") or {}
            base = int(choice.get("_base") or 1)
            shares = {
                candidate: base + (1 if candidate == item_id else 0)
                for candidate in choice["candidateItemIds"]
            }
            self.rules_engine["pendingChoice"] = None
            payload = self.rules_apply_power_distribution(
                action, shares, int(choice.get("sign") or 1)
            )
            self.prune_rules_ongoing_effects()
            return None, {**payload, "playerId": player_id, "itemId": item_id}

        if choice.get("kind") == "reveal_hand_discard" and choice.get("purpose") == "lunar":
            try:
                index = int(option)
            except (TypeError, ValueError):
                return "Choose a Manifestation to put into the Stalemate Zone.", None
            entries = choice.get("entries") or []
            if not 0 <= index < len(entries):
                return "Choose a Manifestation to put into the Stalemate Zone.", None
            entry = entries[index]
            if entry["from"] == "interzone":
                picked = self.find_battlefield_item(entry["itemId"])
                if picked is None or self.rules_item_controller_id(picked) != player_id:
                    return "That Manifestation is no longer available.", None
                self.rules_stalemate_item(picked["id"])
            else:
                owner_id = self.take_zone_card(player_id, "receptacle", entry["cardId"])
                if owner_id is None:
                    return "That Manifestation is no longer available.", None
                seat = self.players[player_id].get("seat")
                self.battlefield.append({
                    "id": new_id(), "ownerId": owner_id, "controllerId": player_id,
                    "cardId": entry["cardId"], "x": 650.0, "y": 800.0 if seat != 1 else 525.0,
                    "faceUp": True, "rotation": 0.0, "counters": {}, "stackedOn": None,
                    "fieldZone": "stalemate",
                })
            next_id = self.rules_lunar_next(
                choice.get("hostItemId"), choice.get("controllerId"),
                list(choice.get("_pending") or []), choice.get("sourceCardId"), choice.get("actionId"),
            )
            return None, {
                "kind": "lunar_liturgy", "status": "placed", "playerId": player_id,
                "cardId": entry["cardId"], "nextChoiceId": next_id,
            }

        if choice.get("kind") == "reveal_hand_discard":
            try:
                index = int(option)
            except (TypeError, ValueError):
                return "Choose a card from the revealed hand.", None
            target_id = choice.get("targetPlayerId")
            hand = self.players[target_id]["zones"][{"bloatuba": "deck", "gummo": "receptacle", "wish": "receptacle", "pescojolero": "receptacle"}.get(choice.get("purpose"), "hand")] if target_id in self.players else []
            card_ids = choice.get("cardIds") or []
            if not 0 <= index < len(card_ids) or card_ids[index] not in hand:
                return "Choose a card from the revealed hand.", None
            card_id = card_ids[index]
            if choice.get("purpose") == "gummo":
                host = self.find_battlefield_item(choice.get("sourceItemId"))
                self.rules_engine["pendingChoice"] = None
                if host is None:
                    return None, {"kind": "gummo_copy", "status": "target_missing"}
                host["gummoCopy"] = card_id
                return None, {
                    "kind": "gummo_copy", "status": "copied", "playerId": player_id,
                    "itemId": host["id"], "cardId": card_id,
                }
            if choice.get("purpose") == "pescojolero":
                self.rules_engine["pendingChoice"] = None
                placed = self.place_rules_card_in_interzone(player_id, target_id, "receptacle", card_id)
                return None, {
                    "kind": "pescojolero_take", "playerId": player_id,
                    "status": "taken" if placed else "interzone_full", "cardId": card_id,
                    "itemId": (placed or {}).get("id"),
                    "sourceCardId": choice.get("sourceCardId"),
                }
            if choice.get("purpose") == "wish":
                caster_id = choice.get("casterId")
                mine_id = choice.get("chosenCardId")
                if mine_id not in self.players[caster_id]["zones"]["receptacle"]:
                    self.rules_engine["pendingChoice"] = None
                    return None, {"kind": "wish_exchange", "status": "target_missing"}
                mine_owner = self.take_zone_card(caster_id, "receptacle", mine_id)
                theirs_owner = self.take_zone_card(target_id, "receptacle", card_id)
                self.put_zone_card(mine_owner if mine_owner in self.players else target_id, "deck", mine_id, mine_owner, "top")
                self.put_zone_card(theirs_owner if theirs_owner in self.players else caster_id, "deck", card_id, theirs_owner, "top")
                self.rules_engine["pendingChoice"] = None
                return None, {
                    "kind": "wish_exchange", "status": "exchanged", "playerId": player_id,
                    "cardIds": [mine_id, card_id], "sourceCardId": choice.get("sourceCardId"),
                }
            if choice.get("purpose") == "gorlok":
                error, _owner_id, _replacement = self.move_zone_card_by_effect(
                    target_id, "hand", target_id, "exile", card_id, "top",
                )
                if error:
                    return error, None
                host = self.find_battlefield_item(choice.get("sourceItemId"))
                if host is not None:
                    counters = host.setdefault("counters", {})
                    counters["power"] = int(counters.get("power") or 0) - len(card_ids)
                self.rules_engine["pendingChoice"] = None
                return None, {
                    "kind": "gorlok_exile", "playerId": player_id, "targetPlayerId": target_id,
                    "cardId": card_id, "shown": len(card_ids),
                    "sourceCardId": choice.get("sourceCardId"),
                }
            if choice.get("purpose") == "bloatuba":
                owner_id = self.take_zone_card(target_id, "deck", card_id)
                if owner_id is None:
                    return "That card is no longer on top of the Deck.", None
                seat = self.players[target_id].get("seat")
                stalemate_item = {
                    "id": new_id(), "ownerId": owner_id, "controllerId": target_id,
                    "cardId": card_id, "x": 650.0, "y": 800.0 if seat != 1 else 525.0,
                    "faceUp": True, "rotation": 0.0, "counters": {}, "stackedOn": None,
                    "fieldZone": "stalemate",
                    "rarity": self.players[owner_id].get("cardRarities", {}).get(card_id),
                }
                self.battlefield.append(stalemate_item)
                remaining = [c for c in choice.get("_revealed") or [] if c != card_id]
                self.rules_engine["pendingChoice"] = (
                    self.make_bloatuba_reorder(
                        choice.get("controllerId"), target_id, remaining, choice.get("sourceCardId"),
                    ) if remaining else None
                )
                return None, {
                    "kind": "bloatuba_pick", "playerId": player_id,
                    "targetPlayerId": target_id, "cardId": card_id,
                    "itemId": stalemate_item["id"],
                    "remaining": remaining,
                }
            if choice.get("purpose") == "womb":
                self.rules_engine["pendingChoice"] = None
                return self.chain_rules_manifestation(
                    target_id, "hand", card_id,
                    action_id=choice.get("actionId"),
                    source_card_id=choice.get("sourceCardId"),
                    chain_controller_id=player_id,
                )
            error, _owner_id = self.move_zone_card(
                target_id, "hand", target_id, "graveyard", card_id, "top"
            )
            if error:
                return error, None
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "reveal_hand_discard", "playerId": player_id,
                "targetPlayerId": target_id, "cardId": card_id,
                "sourceCardId": choice.get("sourceCardId"),
            }

        if choice.get("kind") == "pick_own_item":
            if item_id not in choice.get("candidateItemIds", []):
                return "Choose one of your Manifestations.", None
            done = list(choice.get("_done") or [])
            if choice.get("purpose") == "sacrifice":
                picked = self.find_battlefield_item(item_id)
                done.append(self._rules_remove_field_item_by_effect(
                    picked, picked.get("ownerId"), "graveyard", "top",
                    reason="sacrifice",
                ))
            else:
                done.append(self.rules_stalemate_item(item_id))
            self.rules_engine["pendingChoice"] = None
            next_choice = None
            if choice.get("_queue"):
                next_choice = self.rules_next_pick_own_item_choice(
                    choice["_queue"], choice.get("actionId"),
                    choice.get("sourceCardId"), done,
                    purpose=choice.get("purpose") or "stalemate",
                )
            self.prune_rules_ongoing_effects()
            return None, {
                "kind": "pick_own_item", "purpose": choice.get("purpose"),
                "playerId": player_id, "itemId": item_id,
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
                extra = submitted.get("extra") if group.get("extraSide") else []
                if not isinstance(extra, list):
                    return "Use every revealed card exactly once.", None
                if group.get("extraSide") and not (
                    int(group.get("extraMin") or 0) <= len(extra) <= int(group.get("extraMax") or 0)
                ):
                    return "Choose the allowed number of cards to set aside.", None
                if (
                    not isinstance(top, list)
                    or not isinstance(bottom, list)
                    or not all(isinstance(card_id, str) for card_id in top + bottom + extra)
                    or len(top) != len(set(top))
                    or len(bottom) != len(set(bottom))
                    or set(top) & set(bottom)
                    or set(extra) & (set(top) | set(bottom))
                    or len(extra) != len(set(extra))
                    or sorted(top + bottom + extra) != sorted(group.get("cardIds") or [])
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
                for card_id in extra:
                    if group.get("extraSide") == "hand":
                        self.put_zone_card(
                            player_id, "hand", card_id, owners[card_id], "top"
                        )
                    else:
                        self.put_zone_card(
                            owners[card_id], "exile", card_id, owners[card_id], "top"
                        )
                resolved_groups.append({
                    "playerId": target_id,
                    "top": list(top),
                    "bottom": list(bottom),
                    "fromZone": from_zone,
                    **({"extraSide": group["extraSide"], "extra": list(extra)} if extra else {}),
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
            if option not in {"keep", "bottom"} and not (option == "swap" and choice.get("allowSwap")):
                return "Choose whether to keep the card on top or move it to the bottom.", None
            card_id = choice.get("_cardId")
            deck = self.players[player_id]["zones"]["deck"]
            if not deck or deck[0] != card_id:
                self.rules_engine["pendingChoice"] = None
                return "The inspected top card is no longer available.", None
            if option == "swap":
                hand = self.players[player_id]["zones"]["hand"]
                swap_id = (card_ids or [None])[0]
                if swap_id not in hand:
                    return "Choose a card from your Hand to swap.", None
                swap_owner = self.take_zone_card(player_id, "hand", swap_id)
                top_owner = self.take_zone_card(player_id, "deck", card_id)
                self.put_zone_card(player_id, "hand", card_id, top_owner, "top")
                self.put_zone_card(player_id, "deck", swap_id, swap_owner, "top")
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
            copy_triggered = []
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
                self.rules_engine["pendingChoice"] = None
                copy_triggered = self.queue_rules_token_copy_entry_triggers(copy)
                status = "accepted"
            else:
                self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "optional_trigger",
                "status": status,
                "playerId": player_id,
                "sourceCardId": choice.get("sourceCardId"),
                "relatedCardId": choice.get("_relatedCardId"),
                "createdItemId": created_item_id,
                "triggeredActions": copy_triggered,
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

        if choice.get("kind") == "declare_card_name":
            declared = option if isinstance(option, str) else None
            if declared not in self.card_labels:
                return "Declare the name of an existing card.", None
            declared_name = self.card_labels.get(declared)
            owner_id = choice.get("targetPlayerId")
            deck = self.players[owner_id]["zones"]["deck"]
            self.rules_engine["pendingChoice"] = None
            payload = {
                "kind": "declare_card_name", "mode": choice.get("mode"),
                "playerId": player_id, "targetPlayerId": owner_id,
                "declaredCardId": declared, "sourceCardId": choice.get("sourceCardId"),
            }
            if choice.get("mode") == "top_card_power":
                if not deck:
                    return None, {**payload, "status": "deck_empty"}
                top_card = deck[0]
                matched = self.card_labels.get(top_card) == declared_name
                payload.update({"revealedCardId": top_card, "matched": matched})
                if matched:
                    source_item = self.find_battlefield_item(choice.get("sourceItemId"))
                    if source_item is not None:
                        self.rules_engine["ongoingEffects"].append({
                            "id": new_id(), "actionId": choice.get("actionId"),
                            "abilityId": "declared-name-power",
                            "controllerId": player_id,
                            "source": {"cardId": choice.get("sourceCardId"), "itemId": source_item["id"]},
                            "target": {
                                "kind": "card", "itemId": source_item["id"],
                                "cardId": source_item.get("cardId"),
                                "ownerId": source_item.get("ownerId"),
                            },
                            "kind": "power_modifier",
                            "value": int(choice.get("value") or 0),
                            "duration": "until_end_of_turn",
                            "startedTurn": self.phase_tracker["turn"],
                        })
                        self.record_rules_power_gained(source_item["id"])
                    return None, {**payload, "status": "matched"}
                error, _owner, replacement = self.move_zone_card_by_effect(
                    owner_id, "deck", owner_id, "graveyard", top_card, "top",
                )
                return None, {
                    **payload,
                    "status": "discarded" if not error and not replacement else "unmoved",
                }
            found = next((
                card_id for card_id in deck
                if self.card_labels.get(card_id) == declared_name
            ), None)
            if found is None:
                random.shuffle(deck)
                return None, {**payload, "status": "not_found"}
            error, _owner, replacement = self.move_zone_card_by_effect(
                owner_id, "deck", owner_id, "graveyard", found, "top",
            )
            random.shuffle(self.players[owner_id]["zones"]["deck"])
            return None, {
                **payload, "cardId": found,
                "status": "discarded" if not error and not replacement else "unmoved",
            }

        if choice.get("kind") == "temperament_choice":
            if option not in choice.get("options", []):
                return "Choose a base temperament.", None
            self.rules_engine["pendingChoice"] = None
            item = self.find_battlefield_item(choice.get("sourceItemId"))
            if item is not None:
                item["chosenTemperament"] = option
                label = option.capitalize()
                item.setdefault("counters", {})[label] = 1
            return None, {
                "kind": "temperament_choice", "status": "chosen",
                "temperament": option, "itemId": choice.get("sourceItemId"),
            }

        if choice.get("kind") == "binary_choice" and choice.get("purpose") == "quasimillenary":
            if option not in choice.get("options", []):
                return "Choose yes or no.", None
            self.rules_engine["pendingChoice"] = None
            self.rules_engine.setdefault("limboRecoveryDecided", {})[player_id] = self.phase_tracker["turn"]
            enabled = self.rules_engine.setdefault("limboRecoveryPlayerIds", [])
            if option == "yes" and player_id not in enabled:
                enabled.append(player_id)
            elif option == "no" and player_id in enabled:
                enabled.remove(player_id)
            error, recovery = self.resolve_recovery_draw(int(choice.get("handLimit") or 7))
            if error:
                return error, None
            return None, {
                "kind": "quasimillenary_choice", "status": "limbo" if option == "yes" else "deck",
                "playerId": player_id, "recovery": recovery,
            }

        if choice.get("kind") == "binary_choice" and choice.get("purpose") == "womb_show":
            if option not in choice.get("options", []):
                return "Choose yes or no.", None
            self.rules_engine["pendingChoice"] = None
            controller_id = choice.get("controllerId")
            hand = list(self.players[player_id]["zones"]["hand"])
            chainable = [
                c for c in hand
                if self.card_rules.get(c, {}).get("type") == "manifestation"
                and self.rules_card_play_restriction_error(player_id, c) is None
            ] if option == "yes" and not self.rules_hands_are_immune() else []
            if not chainable:
                tokens = self.apply_rules_action_result({
                    "id": choice.get("actionId") or new_id(), "controllerId": controller_id,
                    "source": {"cardId": choice.get("sourceCardId"), "ownerId": controller_id},
                    "targets": [],
                    "ability": {"result": {
                        "kind": "create_support_tokens", "count": 2, "power": 2,
                        "temperament": "hollow",
                    }},
                })
                return None, {
                    "kind": "womb_show", "status": "tokens",
                    "shown": option == "yes", "tokens": tokens,
                    "handProof": hand if option == "yes" else [],
                }
            new_choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": new_choice_id, "kind": "reveal_hand_discard", "purpose": "womb",
                "playerId": controller_id, "targetPlayerId": player_id,
                "cardIds": chainable,
                "sourceCardId": choice.get("sourceCardId"),
                "actionId": choice.get("actionId"),
            }
            return None, {
                "kind": "womb_show", "status": "shown", "handProof": hand,
                "choiceId": new_choice_id,
            }

        if choice.get("kind") == "binary_choice" and choice.get("purpose") == "amphora_pick":
            if option not in choice.get("options", []):
                return "Choose one of the two manifestations.", None
            self.rules_engine["pendingChoice"] = None
            owner_id = choice.get("controllerId")
            offered = list(choice.get("offeredCardIds") or [])
            hand = self.players[owner_id]["zones"]["hand"]
            if len(offered) != 2 or any(c not in hand for c in offered):
                return None, {"kind": "amphora_pick", "status": "target_missing"}
            kept, discarded = (offered[0], offered[1]) if option == "yes" else (offered[1], offered[0])
            moved = self.apply_rules_action_result({
                "id": new_id(), "controllerId": owner_id,
                "source": {"cardId": choice.get("sourceCardId"), "ownerId": owner_id},
                "targets": [{
                    "kind": "zone_card", "containerId": owner_id, "zone": "hand",
                    "cardId": kept, "ownerId": owner_id,
                }],
                "ability": {"result": {"kind": "move_zone_target_to_field_zone", "asSupport": True}},
            })
            self.move_zone_card(owner_id, "hand", owner_id, "graveyard", discarded, "top")
            return None, {
                "kind": "amphora_pick", "status": (moved or {}).get("status"),
                "cardId": kept, "discardedCardId": discarded,
            }

        if choice.get("kind") == "binary_choice" and choice.get("purpose") == "support_else_chain":
            if option not in choice.get("options", []):
                return "Choose yes or no.", None
            self.rules_engine["pendingChoice"] = None
            item = self.find_battlefield_item(choice.get("targetItemId"))
            moved = False
            if (
                option == "yes" and item is not None
                and self.rules_field_zone(item) == "interzone"
                and not self.rules_support_entry_locked(player_id)
            ):
                item["stackedOn"] = None
                self.mark_rules_support_entry(item)
                triggered = self.queue_rules_support_entry_triggers(
                    item, played=False, from_zone="interzone", defer=True,
                )
                if triggered:
                    self.queue_rules_simultaneous_actions(triggered)
                moved = True
            if moved:
                return None, {
                    "kind": "binary_choice", "status": "support",
                    "itemId": item["id"], "cardId": item.get("cardId"),
                }
            controller_id = choice.get("controllerId")
            if controller_id not in self.players:
                return None, {"kind": "binary_choice", "status": "declined"}
            chain = self.begin_rules_chain_sequence(
                controller_id, [controller_id],
                {"kind": "chain_from_zone", "zone": "hand", "optional": True},
                dict(choice.get("_action") or {}),
            )
            return None, {**chain, "declined": True}

        if choice.get("kind") == "clemency_choice":
            if option not in choice.get("options", []):
                return "Choose whether to neutralize your Will.", None
            controller_id = choice.get("sourceControllerId")
            self.rules_engine["pendingChoice"] = None
            countered = None
            target_action = next((
                entry for entry in self.rules_engine.get("actionStack") or []
                if entry.get("id") == choice.get("relatedActionId")
                and entry.get("kind") == "play_card"
            ), None)
            if option == "neutralize" and target_action is not None:
                countered = self.counter_rules_stack_action(target_action, "neutralize")
            if countered and countered.get("status") == "neutralized":
                source_item = self.find_battlefield_item(choice.get("sourceItemId"))
                if source_item is not None:
                    source_item["rotation"] = 90.0
                return None, {
                    "kind": "clemency_choice", "status": "neutralized",
                    "playerId": player_id, "sourceCardId": choice.get("sourceCardId"),
                    "neutralized": countered,
                }
            delta = (
                self.adjust_rules_score(controller_id, int(choice.get("points") or 0))
                if controller_id in self.players else 0
            )
            return None, {
                "kind": "clemency_choice", "status": "gained",
                "playerId": player_id, "gainerId": controller_id, "delta": delta,
                "sourceCardId": choice.get("sourceCardId"),
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
            follow_up = None
            if will_count:
                source_controller_id = choice.get("sourceControllerId")
                candidates = [
                    item["id"] for item in self.battlefield
                    if item.get("faceUp")
                    and (
                        self.rules_item_card_rules(item).get("type")
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
            return None, {
                "kind": "power_loss_distribution",
                "playerId": player_id,
                "itemIds": list(item_ids),
                "effectIds": applied,
                "sourceCardId": choice.get("sourceCardId"),
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
                paid_card_ids = list(payment.get("cardIds") or [])
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
                # Melancholic Mirror and the other "used as tribute" triggers
                "triggeredActions": self.queue_rules_tribute_triggers(
                    paid_card_ids if status == "paid" else [], player_id, defer_if_choice=True,
                ),
            }

        if choice.get("kind") == "immediate_effect_payment" and choice.get("purpose") == "bullyboo":
            if option != "pay":
                return "You must pay this Tribute.", None
            payment_error, payment = self.rules_action_payment(
                player_id, "activated_effect", None, card_ids,
                {"tribute": choice.get("payment")},
            )
            if payment_error:
                return payment_error, None
            self.pay_rules_tribute(player_id, payment)
            self.rules_engine["pendingChoice"] = None
            controller_id = choice.get("controllerId")
            will_id = choice.get("willCardId")
            if will_id in self.players[controller_id]["zones"]["hand"]:
                self.rules_engine["playPermissions"].append({
                    "id": new_id(), "abilityId": "bullyboo-plays-revealed-will",
                    "playerId": controller_id, "cardId": will_id, "fromZone": "hand",
                    "phaseIds": list(ADVANCED_PHASES), "asSupport": False,
                    "noTribute": True, "turn": self.phase_tracker["turn"],
                    "sourceCardId": choice.get("sourceCardId"),
                })
            played = None
            if will_id in self.players[controller_id]["zones"]["hand"]:
                error, played = self.declare_rules_action(
                    controller_id, f"{self.card_labels.get(will_id, will_id)}",
                    kind="play_card", source={"cardId": will_id, "zone": "hand"},
                    internal=True,
                )
                if error:
                    played = None  # needs targets or a choice: the free-play right remains
            return None, {
                "kind": "immediate_effect_payment", "status": "paid",
                "playerId": player_id, "sourceCardId": choice.get("sourceCardId"),
                "willCardId": will_id, "freePlayGrantedTo": controller_id,
                "autoPlayed": bool(played),
                "triggeredActions": self.queue_rules_tribute_triggers(
                    list(payment.get("cardIds") or []), player_id, defer_if_choice=True,
                ),
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
                paid_card_ids = list(payment.get("cardIds") or [])
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
                if choice.get("stalemateOnDecline"):
                    self.rules_engine["forcedConfrontationStalemate"] = True
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
            if status == "paid":
                payload["triggeredActions"] = self.queue_rules_tribute_triggers(
                    paid_card_ids, player_id, defer_if_choice=True,
                )
            return None, payload

        if choice.get("kind") == "trigger_targets":
            target_error, clean_targets = self.rules_action_targets(targets, player_id)
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
            clean_targets = self.rules_redirect_targets(
                action.get("controllerId") or player_id, clean_targets
            )
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
            elif on_decline.get("kind") == "to_opponent_vessel":
                item = self.find_battlefield_item(on_decline.get("itemId"))
                target_id = on_decline.get("opponentId")
                if item is not None and target_id in self.players:
                    self._rules_remove_field_item(item, target_id, "receptacle", "top")
                    outcome["movedToVessel"] = target_id
            elif on_decline.get("kind") == "exile_source":
                item = self.find_battlefield_item(on_decline.get("itemId"))
                if item is not None:
                    self._rules_remove_field_item_by_effect(
                        item, item.get("ownerId"), "exile", "top", reason="exile",
                    )
                    outcome["exiled"] = True
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

            if option == "karmapult":
                holder = self.rules_karmapult_holder(player_id, item)
                if holder is None:
                    return "You have no Karmapult to place it on.", None
                self.battlefield.remove(item)
                for other in self.battlefield:
                    if other.get("stackedOn") == item.get("id"):
                        other["stackedOn"] = None
                holder.setdefault("attachedCards", []).append({
                    "cardId": item["cardId"], "ownerId": item["ownerId"],
                })
                self.rules_sync_attached_counter(holder)
                result.setdefault("returned", []).append({
                    "status": "karmapult", "itemId": item["id"], "cardId": item.get("cardId"),
                })
                pending = result.get("pendingOwnItemIds") or []
                if pending and pending[0] == item["id"]:
                    pending.pop(0)
                self.rules_engine["pendingChoice"] = None
                self._queue_next_rules_confrontation_destination()
                return None, {
                    "kind": "confrontation_destination", "playerId": player_id,
                    "cardId": item.get("cardId"), "itemId": item.get("id"),
                    "destination": "karmapult", "holderItemId": holder["id"],
                }

            # a Support (World Spore...) leaves the card it was under: it takes its own Interzone slot
            if item.get("isSupport") or item.get("stackedOn"):
                item["stackedOn"] = None
                item["isSupport"] = False
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
            container_id = (
                (choice.get("_cardContainers") or {}).get(card_id)
                if zone == "receptacle" else player_id
            )
            if container_id not in self.players or card_id not in self.players[
                container_id
            ]["zones"].get(zone, []):
                return "The selected Manifestation is no longer in the required zone.", None
            if self.card_rules.get(card_id, {}).get("type") != "manifestation":
                return "Only a Manifestation can be Chained.", None
            if zone == "hand" and self.rules_hands_are_immune():
                return "Cards in Hand are Immune to cards and effects.", None
            self.rules_engine["pendingChoice"] = None
            self.queue_rules_chain_continuation(choice)
            return self.chain_rules_manifestation(
                player_id, zone, card_id, container_id=container_id,
                placement=placement,
                win_destination=choice.get("winDestination"),
                action_id=choice.get("actionId"),
                source_card_id=choice.get("sourceCardId"),
                shuffle_after=bool(choice.get("shuffleAfter")),
                return_to_vessel=bool(choice.get("returnToVessel")),
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
        if choice.get("destination") == "limbo_exile_add_power":
            limbo_zone = list(self.players[player_id]["zones"]["graveyard"])
            for card_id in selected:
                if card_id not in choice["candidateCardIds"] or card_id not in limbo_zone:
                    return "A selected card is not in your Limbo.", None
                limbo_zone.remove(card_id)
            self.rules_engine["pendingChoice"] = None
            resolution = self.apply_rules_action_result({
                "id": choice.get("actionId"), "controllerId": player_id,
                "source": choice.get("_source") or {}, "_limboChosen": True,
                "targets": [
                    {"kind": "zone_card", "containerId": player_id, "zone": "graveyard",
                     "cardId": card_id, "ownerId": player_id}
                    for card_id in selected
                ],
                "ability": {"result": {"kind": "exile_limbo_targets_add_power"}},
            })
            return None, {
                "kind": "exile_limbo_targets_add_power", "playerId": player_id,
                "cardIds": (resolution or {}).get("cardIds", []), "choiceId": choice_id,
                "power": (resolution or {}).get("power", 0),
                "sourceCardId": choice.get("sourceCardId"),
            }
        if choice.get("candidateCardIds") is not None:
            deck_zone = list(self.players[player_id]["zones"]["deck"])
            for card_id in selected:
                if card_id not in choice["candidateCardIds"] or card_id not in deck_zone:
                    return "A selected card is not available in your deck.", None
                deck_zone.remove(card_id)
            if choice.get("destination") == "interzone_from_search":
                card_id = selected[0]
                placed = self.place_rules_card_in_interzone(player_id, player_id, "deck", card_id)
                random.shuffle(self.players[player_id]["zones"]["deck"])
                self.rules_engine["pendingChoice"] = None
                return None, {
                    "kind": "search_deck", "playerId": player_id, "count": 1,
                    "cardIds": [card_id], "choiceId": choice_id,
                    "interzone": bool(placed), "itemId": (placed or {}).get("id"),
                    "actionId": choice.get("actionId"),
                    "controllerId": choice.get("controllerId"),
                    "sourceCardId": choice.get("sourceCardId"),
                }
            if choice.get("destination") == "concealed_field":
                seat = self.players[player_id].get("seat")
                for card_id in selected:
                    self.take_zone_card(player_id, "deck", card_id)
                    self.battlefield.append({
                        "id": new_id(), "ownerId": player_id, "controllerId": player_id,
                        "cardId": card_id, "x": 740.0, "y": 800.0 if seat != 1 else 525.0,
                        "faceUp": False, "rotation": 0.0, "counters": {}, "stackedOn": None,
                        "fieldZone": "field", "concealedWill": True,
                        "jigonItemId": choice.get("jigonItemId"),
                    })
                random.shuffle(self.players[player_id]["zones"]["deck"])
                self.rules_engine["pendingChoice"] = None
                return None, {
                    "kind": "search_deck", "playerId": player_id,
                    "count": len(selected), "cardIds": selected, "choiceId": choice_id,
                    "concealed": True,
                    "actionId": choice.get("actionId"),
                    "controllerId": choice.get("controllerId"),
                    "sourceCardId": choice.get("sourceCardId"),
                }
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
        if destination == "persuasion_place":
            card_id = selected[0]
            owner_id = self.take_zone_card(player_id, "hand", card_id)
            if owner_id is None:
                return "That Will is no longer in your Hand.", None
            seat = self.players[player_id].get("seat")
            item = {
                "id": new_id(), "ownerId": owner_id, "controllerId": player_id,
                "cardId": card_id, "x": 740.0, "y": 800.0 if seat != 1 else 525.0,
                "faceUp": True, "rotation": 0.0, "counters": {}, "stackedOn": None,
                "fieldZone": "field", "persuaded": True, "persuadedBy": choice.get("hostItemId"),
                "rarity": self.players[owner_id].get("cardRarities", {}).get(card_id),
            }
            self.battlefield.append(item)
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "persuasion_place", "playerId": player_id, "cardIds": [card_id],
                "itemId": item["id"], "choiceId": choice_id,
                "actionId": choice.get("actionId"), "controllerId": choice.get("controllerId"),
                "sourceCardId": choice.get("sourceCardId"),
            }
        destination = choice.get("destination")
        if destination in {"auction_bid", "auction_answer"}:
            seat = self.players[player_id].get("seat")
            points_of = lambda card: int((self.card_points or {}).get(card, 0) or 0)
            if destination == "auction_answer":
                total = sum(points_of(card_id) for card_id in selected)
                if total < int(choice.get("requiredPoints") or 0):
                    selected = []
                    self.rules_engine["forcedConfrontationWinnerId"] = choice.get("bidderId")
            for card_id in selected:
                owner_id = self.take_zone_card(player_id, "hand", card_id)
                if owner_id is None:
                    continue
                self.battlefield.append({
                    "id": new_id(), "ownerId": owner_id, "controllerId": player_id,
                    "cardId": card_id, "x": 650.0, "y": 800.0 if seat != 1 else 525.0,
                    "faceUp": True, "rotation": 0.0, "counters": {},
                    "rarity": self.players[owner_id].get("cardRarities", {}).get(card_id),
                    "stackedOn": None, "fieldZone": "stalemate",
                })
            self.rules_engine["pendingChoice"] = None
            payload = {
                "kind": destination, "playerId": player_id, "cardIds": selected,
                "choiceId": choice_id, "actionId": choice.get("actionId"),
                "controllerId": choice.get("controllerId"),
                "sourceCardId": choice.get("sourceCardId"),
            }
            if destination == "auction_bid":
                required = points_of(selected[0])
                opponent_id = self.other_rules_player_id(player_id)
                answers = [
                    c for c in self.players[opponent_id]["zones"]["hand"]
                    if self.card_rules.get(c, {}).get("type") == "manifestation"
                ]
                if sum(points_of(c) for c in answers) < required:
                    self.rules_engine["forcedConfrontationWinnerId"] = player_id
                    payload["opponentLoses"] = True
                else:
                    next_id = new_id()
                    self.rules_engine["pendingChoice"] = {
                        "id": next_id, "kind": "discard_from_hand",
                        "playerId": opponent_id, "count": len(answers), "upTo": True,
                        "requireManifestation": True, "destination": "auction_answer",
                        "requiredPoints": required, "bidderId": player_id,
                        "sourceCardId": choice.get("sourceCardId"),
                        "actionId": choice.get("actionId"),
                        "controllerId": choice.get("controllerId"),
                    }
                    payload["nextChoiceId"] = next_id
            return None, payload
        destination = choice.get("destination")
        if destination == "stalemate_for_support":
            support_id = choice.get("sourceCardId")
            if support_id not in hand_remaining:
                return "Choose two other Manifestations; Chabak must stay in your Hand.", None
            seat = self.players[player_id].get("seat")
            moved = []
            for card_id in selected:
                owner_id = self.take_zone_card(player_id, "hand", card_id)
                if owner_id is None:
                    continue
                self.battlefield.append({
                    "id": new_id(), "ownerId": owner_id, "controllerId": player_id,
                    "cardId": card_id, "x": 650.0, "y": 800.0 if seat != 1 else 525.0,
                    "faceUp": True, "rotation": 0.0, "counters": {},
                    "rarity": self.players[owner_id].get("cardRarities", {}).get(card_id),
                    "stackedOn": None, "fieldZone": "stalemate",
                })
                moved.append(card_id)
            support_item = self.place_rules_hand_card_in_support(player_id, support_id)
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "stalemate_for_support", "playerId": player_id, "cardIds": moved,
                "choiceId": choice_id, "itemId": (support_item or {}).get("id"),
                "actionId": choice.get("actionId"),
                "controllerId": choice.get("controllerId"),
                "sourceCardId": choice.get("sourceCardId"),
            }
        destination = choice.get("destination")
        if destination in {"obelisk_gift", "obelisk_reply"}:
            gift_id = selected[0]
            if destination == "obelisk_gift":
                reply_id = choice.get("chooserId")
                if any(
                    self.card_rules.get(c, {}).get("type") == "manifestation"
                    for c in self.players[reply_id]["zones"]["hand"]
                ):
                    new_choice_id = new_id()
                    self.rules_engine["pendingChoice"] = {
                        "id": new_choice_id, "kind": "discard_from_hand",
                        "playerId": reply_id, "count": 1, "requireManifestation": True,
                        "destination": "obelisk_reply", "chooserId": player_id,
                        "_giftCardId": gift_id,
                        "actionId": choice.get("actionId"),
                        "controllerId": choice.get("controllerId"),
                        "sourceCardId": choice.get("sourceCardId"),
                    }
                    return None, {
                        "kind": "obelisk_gift", "status": "waiting_reply", "playerId": player_id,
                        "choiceId": new_choice_id, "cardIds": [],
                        "actionId": choice.get("actionId"),
                        "controllerId": choice.get("controllerId"),
                        "sourceCardId": choice.get("sourceCardId"),
                    }
                giver_id, giver_card, other_id, other_card = player_id, gift_id, reply_id, None
            else:
                giver_id, giver_card, other_id, other_card = choice.get("chooserId"), choice.get("_giftCardId"), player_id, gift_id
            self.rules_engine["pendingChoice"] = None
            exchanged = []
            entered = []
            for from_id, to_id, card_id in ((giver_id, other_id, giver_card), (other_id, giver_id, other_card)):
                if not card_id or card_id not in self.players[from_id]["zones"]["hand"]:
                    continue
                owner_id = self.take_zone_card(from_id, "hand", card_id)
                self.put_zone_card(to_id, "receptacle", card_id, owner_id, "top")
                exchanged.append({"cardId": card_id, "fromId": from_id, "toId": to_id})
                entered.extend(self.queue_rules_zone_entry_triggers(
                    card_id, owner_id, to_id, "receptacle", defer=True,
                ))
            powers = {
                entry["fromId"]: int(self.card_rules.get(entry["cardId"], {}).get("power") or 0)
                for entry in exchanged
            }
            boosted = None
            if powers:
                top = max(powers.values())
                winners = [pid for pid, value in powers.items() if value == top]
                if len(winners) == 1:
                    first = self.find_battlefield_item(
                        self.rules_engine.get("firstManifestationItemIds", {}).get(winners[0])
                    )
                    if first is not None:
                        self.rules_engine["ongoingEffects"].append({
                            "id": new_id(), "actionId": choice.get("actionId"),
                            "abilityId": "obelisk-gift-boost",
                            "controllerId": winners[0],
                            "source": {"cardId": choice.get("sourceCardId")},
                            "target": {
                                "kind": "card", "itemId": first["id"],
                                "cardId": first.get("cardId"), "ownerId": first.get("ownerId"),
                            },
                            "kind": "power_modifier", "value": 3,
                            "duration": "until_end_of_turn",
                            "startedTurn": self.phase_tracker["turn"],
                        })
                        boosted = {"playerId": winners[0], "itemId": first["id"], "value": 3}
            if entered:
                self.queue_rules_simultaneous_actions(entered)
            return None, {
                "kind": "obelisk_gift", "status": "exchanged", "playerId": player_id,
                "exchanged": exchanged, "cardIds": [e["cardId"] for e in exchanged],
                "boosted": boosted, "choiceId": choice_id,
                "actionId": choice.get("actionId"),
                "controllerId": choice.get("controllerId"),
                "sourceCardId": choice.get("sourceCardId"),
            }
        if destination == "deck_bottom_from_hand":
            card_id = selected[0]
            owner_id = self.take_zone_card(player_id, "hand", card_id)
            if owner_id is None:
                return "That card is no longer in your Hand.", None
            self.put_zone_card(player_id, "deck", card_id, owner_id, "bottom")
            host = self.find_battlefield_item(choice.get("sourceItemId"))
            removal = choice.get("removeCounter") or {}
            if host is not None and removal.get("name"):
                counters = host.setdefault("counters", {})
                key = next((k for k in counters if str(k).casefold() == str(removal["name"]).casefold()), removal["name"])
                counters[key] = max(0, int(counters.get(key) or 0) - int(removal.get("amount") or 0))
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "deck_bottom_from_hand", "playerId": player_id, "cardIds": [card_id],
                "choiceId": choice_id, "actionId": choice.get("actionId"),
                "controllerId": choice.get("controllerId"),
                "sourceCardId": choice.get("sourceCardId"),
            }
        if destination == "attach_to_source":
            host = self.find_battlefield_item(choice.get("sourceItemId"))
            if host is None:
                return "The card to place them on is gone.", None
            placed = []
            for card_id in selected:
                owner_id = self.take_zone_card(player_id, "hand", card_id)
                if owner_id is None:
                    continue
                host.setdefault("attachedCards", []).append({"cardId": card_id, "ownerId": owner_id})
                placed.append(card_id)
            self.rules_sync_attached_counter(host)
            self.rules_engine["pendingChoice"] = None
            return None, {
                "kind": "attach_to_source", "playerId": player_id, "cardIds": placed,
                "count": len(placed), "itemId": host["id"], "choiceId": choice_id,
                "actionId": choice.get("actionId"),
                "controllerId": choice.get("controllerId"),
                "sourceCardId": choice.get("sourceCardId"),
            }
        if destination == "bullyboo_reveal":
            will_id = selected[0]
            payer_id = choice.get("chooserId")
            cost = self.card_rules.get(will_id, {}).get("powerCost")
            revealed = {
                "kind": "bullyboo_reveal", "playerId": player_id, "cardIds": [will_id],
                "handProof": [will_id], "handProofPlayerId": player_id,
                "actionId": choice.get("actionId"),
                "controllerId": choice.get("controllerId"),
                "sourceCardId": choice.get("sourceCardId"),
            }
            if self.rules_can_afford_tribute(payer_id, cost):
                new_choice_id = new_id()
                self.rules_engine["pendingChoice"] = {
                    "id": new_choice_id, "kind": "immediate_effect_payment",
                    "purpose": "bullyboo", "mustPay": True, "playerId": payer_id,
                    "payment": cost,
                    "requirements": self.rules_requirements_from_symbols(cost),
                    "sourceCardId": choice.get("sourceCardId"),
                    "relatedCardId": will_id, "willCardId": will_id,
                    "actionId": choice.get("actionId"),
                    "controllerId": player_id,
                }
                return None, {**revealed, "status": "payment_required", "choiceId": new_choice_id}
            self.rules_engine["pendingChoice"] = None
            lost = -self.adjust_rules_score(payer_id, -10)
            self.move_zone_card(player_id, "hand", player_id, "graveyard", will_id, "top")
            return None, {
                **revealed, "status": "cannot_pay", "lost": lost,
                "payerId": payer_id,
                "payerHand": list(self.players[payer_id]["zones"]["hand"]),
                "handProof": list(self.players[payer_id]["zones"]["hand"]),
                "handProofPlayerId": payer_id,
            }
        if destination == "amphora_offer":
            new_choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": new_choice_id, "kind": "binary_choice", "purpose": "amphora_pick",
                "playerId": choice.get("chooserId"), "options": ["yes", "no"],
                "headingKey": "rulesAmphoraHeading", "textKey": "rulesAmphoraText",
                "yesKey": "rulesAmphoraFirst", "noKey": "rulesAmphoraSecond",
                "sourceCardId": choice.get("sourceCardId"),
                "relatedCardId": choice.get("sourceCardId"),
                "controllerId": player_id, "offeredCardIds": list(selected),
            }
            return None, {
                "kind": "amphora_offer", "status": "offered", "playerId": player_id,
                "choiceId": new_choice_id, "cardIds": [],
                "actionId": choice.get("actionId"),
                "controllerId": choice.get("controllerId"),
                "sourceCardId": choice.get("sourceCardId"),
            }
        for card_id in selected:
            if destination == "support_manifestation":
                moved = self.apply_rules_action_result({
                    "id": new_id(), "controllerId": player_id,
                    "source": {"cardId": choice.get("sourceCardId"), "ownerId": player_id},
                    "targets": [{
                        "kind": "zone_card", "containerId": player_id, "zone": "hand",
                        "cardId": card_id, "ownerId": player_id,
                    }],
                    "ability": {"result": {"kind": "put_hand_will_as_support_manifestation"}},
                })
                if (moved or {}).get("status") != "moved":
                    return "This Will cannot enter Support right now.", None
                continue
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
                self.rules_item_card_rules(item).get("type") == "manifestation"
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
        if (
            source_resolution and source_resolution.get("fieldZone") == "interzone"
            and source_resolution.get("status") == "moved"
        ):
            interzone_item = self.find_battlefield_item(source_resolution.get("itemId"))
            if interzone_item and self.rules_field_zone(interzone_item) == "interzone":
                triggered_actions.extend(
                    self.queue_rules_field_zone_entry_triggers(
                        interzone_item, "interzone",
                        event_targets=resolved.get("targets"), defer=True,
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
                if isinstance(effect_result, dict):
                    triggered_actions.extend(
                        effect_result.pop("resolutionTriggers", None) or []
                    )
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
        if (
            resolved.get("immediate") and not action_stack
            and ((resolved.get("ability") or {}).get("result") or {}).get("kind") == "grant_source_support_until_end_turn"
        ):
            # paying the cost is immediate: the player keeps priority to play the card in Support right away
            next_priority = resolved.get("controllerId")
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
        # Freenya: the free Limbo play is offered once, when its effect resolves.
        self.rules_engine["playPermissions"] = [
            entry for entry in self.rules_engine.get("playPermissions") or []
            if not (
                entry.get("playerId") == player_id
                and entry.get("fromZone") == "graveyard"
                and entry.get("exileOnLeave")
            )
        ]

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
        if previous_phase_id == "end_expire":
            overflow = self.set_rules_hand_overflow_choice(list(self.players))
            if overflow:
                return None, {
                    "status": "choice_required",
                    "choiceKind": "hand_overflow",
                    "playerId": overflow["playerId"],
                    "stackDepth": 0,
                }
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
        if (
            previous_phase_id == "resolution_move"
            and self.rules_engine.get("skipEndPhaseTurn") == self.phase_tracker["turn"]
        ):
            next_index = len(sequence)
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
            resolution_triggered_actions.extend(
                self.queue_rules_resolution_field_triggers()
            )
        confrontation_result = None
        if self.current_phase_id() == "resolution_compare":
            confrontation_result = self.prepare_rules_confrontation_result()
        elif self.current_phase_id() == "resolution_move":
            confrontation_result = self.begin_rules_confrontation_cleanup()
            if isinstance(confrontation_result, dict):
                resolution_triggered_actions.extend(
                    confrontation_result.pop("triggeredActions", None) or []
                )
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
        self.rules_engine["drawLocks"] = []
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
        if viewer_id == owner_id:
            return True
        return zone == "hand" and self.rules_hand_revealed_to(viewer_id, owner_id)

    def rules_hand_revealed_to(self, viewer_id, owner_id):
        """Gorte (always) and Bonzai (before the Revelation) reveal a Hand."""
        if not self.rules_engine.get("enabled") or viewer_id == owner_id:
            return False
        if any(
            self.rules_item_controller_id(source) != owner_id
            for source in self.rules_active_passive_sources("reveal_opponent_hands")
        ):
            return True
        if self.current_phase_id() not in {
            "confrontation_choose", "confrontation_before_revelation",
        }:
            return False
        container = self.players.get(owner_id)
        if container is None:
            return False
        return any(
            self.card_owner_in_zone(owner_id, "receptacle", card_id) == viewer_id
            and any(
                passive.get("kind") == "vessel_reveals_owner_hand"
                for passive in self.card_rules.get(card_id, {}).get(
                    "passiveEffects"
                ) or []
            )
            for card_id in container["zones"].get("receptacle", [])
        )

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

        zone_entry_turns_view = {}
        for entry_key, entry_turn in self.rules_engine["zoneEntryTurns"].items():
            parts = entry_key.split(":", 2)
            if len(parts) != 3:
                if can_view_hidden:
                    zone_entry_turns_view[entry_key] = entry_turn
                continue
            owner_id, zone, _card_id = parts
            if self.can_view_zone(viewer_id, role, owner_id, zone):
                zone_entry_turns_view[entry_key] = entry_turn

        conditional_support_hand_card_ids = self.rules_conditional_support_hand_card_ids()
        if not can_view_hidden:
            conditional_support_hand_card_ids = (
                {viewer_id: conditional_support_hand_card_ids.get(viewer_id, [])}
                if viewer_id in self.players else {}
            )

        play_permissions_view = [
            dict(entry) for entry in self.rules_engine["playPermissions"]
            if can_view_hidden or entry.get("playerId") == viewer_id
        ]

        battlefield_view = []
        for item in self.battlefield:
            # the owner sees their own hidden cards; a trusted observer sees everything too
            can_peek = can_view_hidden or item["ownerId"] == viewer_id
            if (
                not can_peek and self.rules_engine["enabled"]
                and item["id"] in (self.rules_engine.get("firstManifestationItemIds") or {}).values()
                and item["ownerId"] in self.rules_engine["firstManifestationValidatedPlayerIds"]
                and viewer_id in self.players and viewer_id != item["ownerId"]
                and self.rules_plays_first_manifestation_after(viewer_id)
            ):
                can_peek = True  # Hermetic Hourglass: the opponent's First Manifestation is shown first
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
            elif self.rules_engine.get("enabled") and self.rules_field_zone(item) == "confrontation":
                # a First Manifestation stands in the Confrontation (rules_field_zone):
                # say so, so every client check reads the same zone (Unruly Flail...)
                entry["fieldZone"] = "confrontation"
            if item.get("isSupport"):
                entry["isSupport"] = True
            if item.get("manualStack"):
                entry["manualStack"] = item["manualStack"]
            if item.get("chosenTemperament"):
                entry["chosenTemperament"] = item["chosenTemperament"]
            if item.get("supportUntilTurn"):
                entry["supportUntilTurn"] = item["supportUntilTurn"]
            controller_id = self.rules_item_controller_id(item)
            if (
                self.rules_engine["enabled"] and item.get("faceUp")
                and item.get("fieldZone") == "interzone"
                and self.rules_item_card_rules(item).get("type") == "manifestation"
                and not self.rules_support_entry_locked(controller_id)
                and self.rules_card_can_enter_support(item)
            ):
                entry["canEnterSupport"] = True
            if item.get("isChained"):
                entry["isChained"] = True
            if controller_id and controller_id != item.get("ownerId"):
                entry["controllerId"] = controller_id
            if item.get("temperamentOverride") in RULES_TEMPERAMENTS:
                entry["temperamentOverride"] = item["temperamentOverride"]
            if item.get("confrontationOrder"):
                entry["confrontationOrder"] = item["confrontationOrder"]
            if item.get("effectsDisabled"):
                entry["effectsDisabled"] = True
            elif (
                self.rules_engine["enabled"] and item.get("faceUp")
                and not self.rules_item_effects_active(item)
            ):
                # lost effects (Stalemate Zone, Discombobulator, lose_effects...): no action offered
                entry["effectsInactive"] = True
            if item.get("playableFree"):
                entry["playableFree"] = item["playableFree"]
            if item.get("willManifestation"):
                # Rinq / Ju Lien: a Will that counts as a Manifestation until the Resolution
                entry["willManifestation"] = True
            if item.get("attachedCards"):
                entry["attachedCards"] = [dict(card) for card in item["attachedCards"]]
            for option_key in ("outcastOff", "karmapultAuto", "gummoCopy", "persuaded"):
                if item.get(option_key):
                    entry[option_key] = item[option_key]
            if item.get("concealedWill") and can_peek:
                entry["concealedWill"] = True
                if item.get("concealedFree"):
                    entry["concealedFree"] = True
                if item.get("tebebeConcealed"):
                    entry["tebebeConcealed"] = True
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
                and (item.get("isTokenCard") or self.rules_item_card_rules(item).get("type") == "manifestation")
            ):
                characteristics = self.rules_manifestation_characteristics(item)
                entry["effectivePower"] = characteristics["power"]
                entry["effectiveTemperament"] = characteristics["temperament"]
                if self.rules_field_zone(item) == "confrontation":
                    # what this card really adds to the total compared at the Resolution
                    # (never below 0, ignored Power and Spite thresholds count as 0)
                    entry["confrontationPower"] = self.rules_confrontation_power(item)
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
                "autoSkipPhases": bool(self.rules_engine.get("autoSkipPhases", True)),
                "autoSkipOffPlayerIds": list(self.rules_engine.get("autoSkipOffPlayerIds") or []),
                "passAllPlayerIds": list(self.rules_engine.get("passAllPlayerIds") or []),
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
                "playPermissions": play_permissions_view,
                "supportEntries": [dict(entry) for entry in self.rules_engine["supportEntries"]],
                "supportEntryLockedPlayerIds": [
                    pid for pid in self.players if self.rules_support_entry_locked(pid)
                ],
                "playRestrictions": [dict(entry) for entry in self.rules_engine["playRestrictions"]],
                "zoneEntryTurns": zone_entry_turns_view,
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
                "tributePowerOverrides": self.rules_tribute_power_overrides_snapshot(),
                "outcome": self.rules_engine["outcome"],
                "priorityPlayerId": self.rules_engine["priorityPlayerId"],
                "resolvePrompt": self.rules_confrontation_resolve_prompt(),
                # Pin Down and similar locks: no Manifestation may enter the Confrontation Zone
                "supportEntryLocked": bool(
                    viewer_id in self.players and self.rules_support_entry_locked(viewer_id)
                ),
                "conditionalSupportHandCardIds": conditional_support_hand_card_ids,
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
                "trapPlayerIds": list(self.rules_engine.get("trapPlayerIds") or []),
                # hand cards whose hand effect the viewer could use now (Ranba's condition...)
                "usableHandAbilityCardIds": self.rules_usable_hand_ability_card_ids(viewer_id),
                # a Trap waiting in place of a First Manifestation: face down for the opponent
                "trapCards": {
                    pid: {
                        "cardId": trap["cardId"] if trap.get("revealed") or viewer_id == pid else None,
                        "revealed": bool(trap.get("revealed")),
                    }
                    for pid, trap in (self.rules_engine.get("trapCards") or {}).items()
                },
                "limboRecoveryPlayerIds": list(self.rules_engine.get("limboRecoveryPlayerIds") or []),
                "uncoveredHand": {
                    pid: [
                        c for c in dict.fromkeys(self.rules_engine.get("limboDrawn", {}).get(pid) or [])
                        if c in self.players[pid]["zones"]["hand"]
                    ]
                    for pid in self.players if self.rules_engine.get("limboDrawn", {}).get(pid)
                },
                "uncoveredTops": {
                    pid: self.players[pid]["zones"]["deck"][0]
                    for pid in self.players if self.rules_uncovered_deck_top(pid)
                },
                "firstManifestationComplete": self.rules_engine["firstManifestationComplete"],
                "confrontationResult": dict(self.rules_engine["confrontationResult"]) if self.rules_engine["confrontationResult"] else None,
                "lastConfrontationWinnerId": self.rules_engine["lastConfrontationWinnerId"],
            },
            # a small tail of the action log, piggybacked on every state sync so
            # the opponent-row mini activity feed updates live without a
            # separate poll — the full log (request_log) is still the
            # authoritative, complete history used for the debug/download panel
            "recentLog": [
                self.log_entry_for_role(entry, role) for entry in self.log[-30:]
                if self.log_entry_visible_to(entry, role)
            ],
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

    def rules_card_can_be_first_manifestation(self, card_id, player_id=None):
        metadata = self.card_rules.get(card_id, {})
        if player_id is not None and self.rules_confrontation_entry_blocked(player_id, metadata):
            return False
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

    def rules_quasimillenary_active(self, player_id):
        return player_id in (self.rules_engine.get("limboRecoveryPlayerIds") or []) and any(
            self.rules_item_controller_id(source) == player_id
            and self.rules_field_zone(source) == "interzone"
            for source in self.rules_active_passive_sources("recovery_draw_from_limbo")
        )

    def toggle_rules_limbo_recovery(self, player_id):
        if not any(
            self.rules_item_controller_id(source) == player_id
            and self.rules_field_zone(source) == "interzone"
            for source in self.rules_active_passive_sources("recovery_draw_from_limbo")
        ):
            return "Quasimillenary is not in your Interzone.", None
        enabled = self.rules_engine.setdefault("limboRecoveryPlayerIds", [])
        if player_id in enabled:
            enabled.remove(player_id)
        else:
            enabled.append(player_id)
        return None, {"enabled": player_id in enabled}

    def _draw_rules_recovery_hand(self, player_id, default_limit=7):
        before_limit = self.rules_recovery_hand_limit(player_id, default_limit, "before_draw")
        if self.rules_quasimillenary_active(player_id) and self.players[player_id]["zones"]["graveyard"]:
            player = self.players[player_id]
            random.shuffle(player["zones"]["graveyard"])
            needed = max(0, before_limit - len(player["zones"]["hand"]))
            drawn = []
            marked = self.rules_engine.setdefault("limboDrawn", {}).setdefault(player_id, [])
            for _ in range(min(needed, len(player["zones"]["graveyard"]))):
                card_id = player["zones"]["graveyard"][0]
                move_error, _owner = self.move_zone_card(player_id, "graveyard", player_id, "hand", card_id, "bottom")
                if move_error:
                    return move_error, None
                marked.append(card_id)
                drawn.append(card_id)
            # Not enough cards in Limbo: the rest comes from the deck as usual.
            error, from_deck = self._draw_player_to_limit(player_id, before_limit)
            if error:
                return error, None
            return None, {
                "count": len(drawn) + len(from_deck), "handLimit": before_limit,
                "fromLimbo": drawn,
            }
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

    def _rules_wants_first_manifestation_after(self, player_id):
        if player_id in (self.rules_engine.get("trapPlayerIds") or []):
            return True
        sources = self.rules_active_passive_sources("play_first_manifestation_after_opponents")
        mine = any(self.rules_item_controller_id(source) == player_id for source in sources)
        theirs = any(self.rules_item_controller_id(source) != player_id for source in sources)
        return mine and not theirs

    def rules_plays_first_manifestation_after(self, player_id):
        """Hermetic Hourglass or Trap: this player plays the First Manifestation after the opponent.

        When every player wants to play last (Trap against Hourglass, two Traps),
        the demands cancel out instead of leaving both players waiting.
        """
        if not self._rules_wants_first_manifestation_after(player_id):
            return False
        return not all(self._rules_wants_first_manifestation_after(pid) for pid in self.players)

    def rules_first_manifestation_order_error(self, player_id):
        if not self.rules_plays_first_manifestation_after(player_id):
            return None
        validated = self.rules_engine["firstManifestationValidatedPlayerIds"]
        if any(pid != player_id and pid in validated for pid in self.players):
            return None
        if player_id in (self.rules_engine.get("trapPlayerIds") or []):
            return "Your Trap makes you play your First Manifestation after the opponent: wait for their validated First Manifestation."
        return "Your Hermetic Hourglass makes you play after the opponent: wait for their validated First Manifestation."

    def rules_is_trap_card(self, card_id):
        return any(
            (ability.get("result") or {}).get("kind") == "first_manifestation_trap"
            for ability in self.card_rules.get(card_id, {}).get("playedAbilities") or []
        )

    def play_first_manifestation_trap(self, player_id, card_id):
        """Trap: played at Revelation in place of the First Manifestation, which is then played after the opponent's."""
        if not self.rules_first_manifestation_active():
            return "A Trap can only be played in place of the First Manifestation.", None
        player = self.players.get(player_id)
        if player is None or card_id not in player["zones"]["hand"] or not self.rules_is_trap_card(card_id):
            return "Choose a Trap from your Hand.", None
        if (
            player_id in self.rules_engine["firstManifestationItemIds"]
            or player_id in self.rules_engine["firstManifestationValidatedPlayerIds"]
            or player_id in self.rules_engine["trapPlayerIds"]
        ):
            return "You have already chosen your First Manifestation.", None
        # The Trap waits face down in the Confrontation Zone, like a First
        # Manifestation: it is turned over (and the 5 points lost) when the
        # opponent's First Manifestation is revealed.
        self.take_zone_card(player_id, "hand", card_id)
        self.rules_engine.setdefault("trapCards", {})[player_id] = {"cardId": card_id, "revealed": False}
        self.rules_engine["trapPlayerIds"].append(player_id)
        return None, {"playerId": player_id, "delta": 0}

    def reveal_rules_traps(self, player_ids):
        """Turn the waiting Traps over: each goes to its owner's Limbo and costs 5 points."""
        revealed = []
        for pid in player_ids:
            trap = (self.rules_engine.get("trapCards") or {}).get(pid)
            if not trap or trap.get("revealed") or pid not in self.players:
                continue
            card_id = trap["cardId"]
            trap["revealed"] = True
            self.put_zone_card(pid, "hand", card_id, pid, "bottom")
            self.move_zone_card(pid, "hand", pid, "graveyard", card_id, "top")
            delta = self.adjust_rules_score(pid, -5)
            revealed.append({"playerId": pid, "cardId": card_id, "delta": delta})
        return revealed

    def flush_rules_traps(self):
        """A Trap still face down when the step ends is turned over anyway."""
        revealed = self.reveal_rules_traps(list((self.rules_engine.get("trapCards") or {}).keys()))
        self.rules_engine["trapCards"] = {}
        return revealed

    def register_first_manifestation(self, player_id, item):
        if not self.rules_first_manifestation_active():
            return None
        order_error = self.rules_first_manifestation_order_error(player_id)
        if order_error and not item.get("persistedFirst"):
            return order_error
        if item.get("ownerId") != player_id or not self.rules_card_can_be_first_manifestation(item.get("cardId"), player_id):
            return "Your first play must be one of your Manifestations."
        selected = self.rules_engine["firstManifestationItemIds"]
        if player_id in selected:
            return "You have already chosen your first Manifestation."
        # Playing after the opponent (Trap, Hermetic Hourglass): their First
        # Manifestation is already revealed and this one arrives face up.
        item["faceUp"] = bool(
            self.rules_plays_first_manifestation_after(player_id)
            and not item.get("persistedFirst")
        )
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
        if self.rules_item_card_rules(item).get("type") != "manifestation":
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
            return "Your first Manifestation is final and locked in: it cannot be changed once placed.", None
        item_id = self.rules_engine["firstManifestationItemIds"].get(player_id)
        if not item_id or not self.find_battlefield_item(item_id):
            return "Play a Manifestation face down before validating.", None
        order_error = self.rules_first_manifestation_order_error(player_id)
        if order_error:
            return order_error, None
        if player_id not in confirmed_players:
            confirmed_players.append(player_id)
        after_ids = [pid for pid in self.players if self.rules_plays_first_manifestation_after(pid)]
        first_ids = [pid for pid in self.players if pid not in after_ids]
        traps_revealed = []
        if after_ids and all(pid in confirmed_players for pid in first_ids):
            for pid in first_ids:
                revealed_item = self.find_battlefield_item(
                    self.rules_engine["firstManifestationItemIds"].get(pid)
                )
                if revealed_item:
                    revealed_item["faceUp"] = True
            traps_revealed = self.reveal_rules_traps(after_ids)
        player_ids = list(self.players)
        revealed = len(player_ids) >= NUM_SEATS and all(pid in confirmed_players for pid in player_ids)
        if revealed:
            traps_revealed += self.flush_rules_traps()
            self.rules_engine["firstManifestationComplete"] = True
            self.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_before_revelation")
            self.rules_engine["priorityPasses"] = []
            first_player = self.player_for_seat(0) or next(iter(self.players.values()), None)
            last_winner = self.rules_engine.get("lastConfrontationWinnerId")
            self.rules_engine["priorityPlayerId"] = (
                last_winner if last_winner in self.players
                else (first_player.get("id") if first_player else None)
            )
        return None, {
            "validated": True, "selectionComplete": revealed, "revealed": False,
            "trapsRevealed": traps_revealed,
        }

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
        for item in self.battlefield:
            if (
                self.rules_item_controller_id(item) == player_id
                and self.rules_field_zone(item) == "interzone"
                and self.rules_item_effects_active(item)
            ):
                total += sum(
                    int(passive.get("value") or 0)
                    for passive in self.rules_item_card_rules(item).get(
                        "passiveEffects"
                    ) or []
                    if passive.get("kind") == "final_interzone_points"
                )
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

        # Quasimillenary: its controller chooses where this Recovery draw comes from.
        decided = self.rules_engine.setdefault("limboRecoveryDecided", {})
        for pid in sorted(self.players, key=lambda current: self.players[current].get("seat", 0)):
            if decided.get(pid) == turn or not self.players[pid]["zones"]["graveyard"]:
                continue
            if not any(
                self.rules_item_controller_id(source) == pid
                and self.rules_field_zone(source) == "interzone"
                for source in self.rules_active_passive_sources("recovery_draw_from_limbo")
            ):
                continue
            choice_id = new_id()
            self.rules_engine["pendingChoice"] = {
                "id": choice_id, "kind": "binary_choice", "purpose": "quasimillenary",
                "playerId": pid, "options": ["yes", "no"],
                "headingKey": "rulesQuasiHeading", "textKey": "rulesQuasiText",
                "yesKey": "rulesQuasiYes", "noKey": "rulesQuasiNo",
                "sourceCardId": next((
                    src.get("cardId") for src in self.rules_active_passive_sources("recovery_draw_from_limbo")
                    if self.rules_item_controller_id(src) == pid
                ), None),
                "controllerId": pid, "handLimit": hand_limit,
            }
            return None, {
                "awaitingChoice": True, "choiceId": choice_id, "draws": {},
                "handLimits": {}, "mulliganRequiredPlayerIds": [], "outcome": None,
                "phaseId": self.current_phase_id(), "advanced": False,
                "incompletePlayerIds": [],
            }
        draws = {}
        hand_limits = {}
        for player in sorted(self.players.values(), key=lambda current: current.get("seat", 0)):
            player_id = player["id"]
            error, draw_result = self._draw_rules_recovery_hand(player_id, hand_limit)
            if error:
                return error, None
            draws[player_id] = draw_result["count"]
            hand_limits[player_id] = draw_result["handLimit"]
        self.rules_engine["limboRecoveryPlayerIds"] = []

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
            "incompletePlayerIds": incomplete_player_ids,
            "mulliganRequiredPlayerIds": list(self.rules_engine["recoveryMulliganRequiredPlayerIds"]),
            "advanced": not self.ended and self.current_phase_id() == "recovery_end",
            "phaseId": self.current_phase_id(),
            "outcome": self.rules_engine["outcome"],
        }

    @staticmethod
    def log_entry_visible_to(entry, role):
        """The observers' own chat stays out of what the players receive."""
        return not (
            normalize_role(role) == "player"
            and entry.get("type") == "chat_message"
            and (entry.get("details") or {}).get("channel") == "observers"
        )

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
        return {"type": "log", "entries": [
            self.log_entry_for_role(entry, role) for entry in self.log
            if self.log_entry_visible_to(entry, role)
        ]}
