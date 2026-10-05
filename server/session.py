"""In-memory session/game-state model for Kartomantik Online.

No rules engine here: sessions just hold zones, a shared battlefield, tokens,
scores and an action log. Permission checks (who can see/act on what) live
here too, since they must be enforced server-side to be meaningful.
"""
import random
import string
import time
import uuid

PRIVATE_ZONES = {"deck", "hand"}
SHARED_ZONES = {"graveyard", "exile", "receptacle"}
ALL_ZONES = PRIVATE_ZONES | SHARED_ZONES

NORMAL_PHASES = ("recovery", "confrontation", "resolution", "end")
ADVANCED_PHASES = (
    "recovery_start", "recovery_draw", "recovery_before_revelation",
    "confrontation_choose", "confrontation_reveal", "confrontation_immediate", "confrontation_entry", "confrontation_reaction",
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


def gen_code(length=6):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I ambiguity
    return "".join(random.choices(alphabet, k=length))


def new_id():
    return uuid.uuid4().hex[:12]


def validate_tournament_deck(card_ids, sideboard_ids, card_points, policy=None, card_labels=None):
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
    if sum(card_points[card_id] for card_id in card_ids) > 500:
        return "A tournament deck cannot exceed 500 points."
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
    def __init__(self, mode="casual", tournament_policy=None, card_points=None, card_labels=None):
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
        self.card_points = card_points
        self.card_labels = card_labels or {}
        self.players = {}  # player_id -> player dict, in join order
        self.battlefield = []  # list of dict: id, ownerId, cardId, x, y, faceUp, rotation, counters
        self.tokens = []  # list of dict: id, ownerId, x, y, label, color, counters
        self.strokes = []  # freehand annotation strokes: id, ownerId, color, points:[[x,y],...]
        self.log = []  # chronological, sequence-numbered audit trail
        self.log_sequence = 0
        self.pending_hand_requests = {}  # requestId -> {requesterId, targetId, index, action}
        self.phase_tracker = {"enabled": False, "advanced": False, "index": 0, "turn": 1}
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
        if card_id not in player["zones"][zone]:
            player.setdefault("zoneOwners", {}).setdefault(zone, {}).pop(card_id, None)
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
        return True

    @staticmethod
    def destination_error(card_owner_id, container_id, zone):
        if zone == "receptacle":
            if card_owner_id == container_id:
                return "A card cannot enter its owner's Empathic Vessel."
        elif card_owner_id != container_id:
            return "A card can only enter its owner's Deck, Hand, Limbo, or Exile."
        return None

    def move_zone_card(self, from_container_id, from_zone, to_container_id, to_zone, card_id, position="top"):
        owner_id = self.card_owner_in_zone(from_container_id, from_zone, card_id)
        if owner_id is None or card_id not in self.players[from_container_id]["zones"][from_zone]:
            return "Card not found in source zone.", None
        error = self.destination_error(owner_id, to_container_id, to_zone)
        if error:
            return error, owner_id
        self.take_zone_card(from_container_id, from_zone, card_id)
        self.put_zone_card(to_container_id, to_zone, card_id, owner_id, position)
        return None, owner_id

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
        for owner_id, player in self.players.items():
            player["zones"] = {zone: [] for zone in ALL_ZONES}
            player["zoneOwners"] = {zone: {} for zone in ALL_ZONES}
            player["zones"]["deck"] = cards_by_owner[owner_id]
            player["zoneOwners"]["deck"] = {card_id: owner_id for card_id in cards_by_owner[owner_id]}
        self.battlefield = []

    def reset_cards_to_active_decks(self, decks_by_player):
        """Discard every live card location and rebuild from saved deck definitions."""
        self.battlefield = []
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
        if not self.phase_tracker["enabled"] or player_id not in self.players:
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

    def reset_phase_tracker(self):
        self.phase_tracker["index"] = 0
        self.phase_tracker["turn"] = 1
        self.phase_passes.clear()

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
        self.battlefield.append(item)
        return None, item

    # -- serialization (permission-filtered per viewer) ------------------
    def serialize_for(self, viewer_id, role):
        role = normalize_role(role)
        can_view_hidden = role in PRIVILEGED_VIEW_ROLES
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
            "phaseTracker": self.serialize_phase_tracker(),
            # a small tail of the action log, piggybacked on every state sync so
            # the opponent-row mini activity feed updates live without a
            # separate poll — the full log (request_log) is still the
            # authoritative, complete history used for the debug/download panel
            "recentLog": [self.log_entry_for_role(entry, role) for entry in self.log[-30:]],
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
