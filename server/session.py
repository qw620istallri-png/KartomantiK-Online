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
    "recovery_start", "recovery_draw", "recovery_first", "recovery_before_revelation",
    "confrontation_choose", "confrontation_reveal", "confrontation_immediate", "confrontation_entry", "confrontation_reaction",
    "resolution_compare", "resolution_effects", "resolution_move",
    "end_actions", "end_triggers", "end_expire", "end_cleanup",
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


def gen_code(length=6):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I ambiguity
    return "".join(random.choices(alphabet, k=length))


def new_id():
    return uuid.uuid4().hex[:12]


def make_player(player_id, name, cluster_index=0):
    seat = cluster_index % NUM_SEATS
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
        "activity": None,  # transient "what menu are they in" hint, never private
    }


class Session:
    def __init__(self):
        self.code_player = gen_code()
        self.code_observer = gen_code()
        self.players = {}  # player_id -> player dict, in join order
        self.battlefield = []  # list of dict: id, ownerId, cardId, x, y, faceUp, rotation, counters
        self.tokens = []  # list of dict: id, ownerId, x, y, label, color, counters
        self.strokes = []  # freehand annotation strokes: id, ownerId, color, points:[[x,y],...]
        self.log = []  # list of dict: timestamp, actorId, actorName, type, details
        self.pending_hand_requests = {}  # requestId -> {requesterId, targetId, index, action}
        self.phase_tracker = {"enabled": False, "advanced": False, "index": 0, "turn": 1}
        self.phase_passes = set()
        self.created_at = time.time()
        self.last_activity = time.time()
        self.ended = False

    # -- bookkeeping -------------------------------------------------
    def touch(self):
        self.last_activity = time.time()

    def is_expired(self):
        return (time.time() - self.last_activity) > SESSION_TTL_SECONDS

    def add_log(self, actor_id, action_type, details=None):
        actor = self.players.get(actor_id)
        self.log.append(
            {
                "timestamp": time.time(),
                "actorId": actor_id,
                "actorName": actor["name"] if actor else None,
                "type": action_type,
                "details": details or {},
            }
        )

    # -- players ------------------------------------------------------
    def get_or_create_player(self, player_id, name):
        player = self.players.get(player_id)
        if player is None:
            player = make_player(player_id, name, cluster_index=len(self.players))
            self.players[player_id] = player
        elif name:
            player["name"] = name
        return player

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
            if not item.get("isTokenCard") and item.get("ownerId") in cards_by_owner:
                cards_by_owner[item["ownerId"]].append(item["cardId"])
        for owner_id, player in self.players.items():
            player["zones"] = {zone: [] for zone in ALL_ZONES}
            player["zoneOwners"] = {zone: {} for zone in ALL_ZONES}
            player["zones"]["deck"] = cards_by_owner[owner_id]
            player["zoneOwners"]["deck"] = {card_id: owner_id for card_id in cards_by_owner[owner_id]}
        self.battlefield = []

    # -- shared phase tracker -------------------------------------------
    def phase_sequence(self):
        return ADVANCED_PHASES if self.phase_tracker["advanced"] else NORMAL_PHASES

    def current_phase_group(self):
        sequence = self.phase_sequence()
        phase_id = sequence[min(self.phase_tracker["index"], len(sequence) - 1)]
        return PHASE_GROUP.get(phase_id, phase_id)

    def configure_phases(self, enabled=None, advanced=None):
        if enabled is not None and bool(enabled) != self.phase_tracker["enabled"]:
            self.phase_tracker.update({"enabled": bool(enabled), "index": 0, "turn": 1})
            self.phase_passes.clear()
        if advanced is not None and bool(advanced) != self.phase_tracker["advanced"]:
            current_group = self.current_phase_group()
            self.phase_tracker["advanced"] = bool(advanced)
            sequence = self.phase_sequence()
            self.phase_tracker["index"] = next(
                (index for index, phase_id in enumerate(sequence) if PHASE_GROUP.get(phase_id, phase_id) == current_group),
                0,
            )
            self.phase_passes.clear()

    def pass_phase(self, player_id):
        if not self.phase_tracker["enabled"] or player_id not in self.players:
            return False
        self.phase_passes.add(player_id)
        player_ids = list(self.players)
        if len(player_ids) < 2 or not all(pid in self.phase_passes for pid in player_ids):
            return False
        sequence = self.phase_sequence()
        next_index = self.phase_tracker["index"] + 1
        if next_index >= len(sequence):
            next_index = 0
            self.phase_tracker["turn"] += 1
        self.phase_tracker["index"] = next_index
        self.phase_passes.clear()
        return True

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
    def can_view_zone(self, viewer_id, is_observer, owner_id, zone):
        if zone in SHARED_ZONES:
            return True
        # private zone: the owner, or a trusted read-only observer, but never another player
        if is_observer:
            return True
        return viewer_id == owner_id

    def can_act_on_zone(self, actor_id, is_observer, owner_id, zone):
        if is_observer:
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

    # -- serialization (permission-filtered per viewer) ------------------
    def serialize_for(self, viewer_id, is_observer):
        players_view = {}
        for pid, player in self.players.items():
            zones_view = {}
            for zone, cards in player["zones"].items():
                if self.can_view_zone(viewer_id, is_observer, pid, zone):
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
                "cardRarities": dict(player.get("cardRarities", {})) if is_observer or pid == viewer_id else {},
                "activity": player.get("activity"),
            }

        battlefield_view = []
        for item in self.battlefield:
            # the owner sees their own hidden cards; a trusted observer sees everything too
            can_peek = is_observer or item["ownerId"] == viewer_id
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
            "phaseTracker": self.serialize_phase_tracker(),
            # a small tail of the action log, piggybacked on every state sync so
            # the opponent-row mini activity feed updates live without a
            # separate poll — the full log (request_log) is still the
            # authoritative, complete history used for the debug/download panel
            "recentLog": self.log[-30:],
        }

    def serialize_log(self):
        return {"type": "log", "entries": self.log}
