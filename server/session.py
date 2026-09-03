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

SESSION_TTL_SECONDS = 6 * 60 * 60  # expire an inactive session after 6h

# Fixed on-field pile positions, matching the official playmat art's printed
# zone slots (board-bg.png, 1549x1549). Positions are NOT player-adjustable
# any more by default (a client-side "unlock piles" mode still lets someone
# drag their own local view for personal comfort, but that never reaches the
# server — see pileOverrides/flipXY in app.js).
#
# Earlier attempts derived cluster B (seat 1) from cluster A by mirroring
# through a measured axis (screenshot pixel analysis, then live-render grid
# overlays, then label-text centres — each an improvement, none quite right).
# That approach was abandoned: dragging cluster A's own piles while actually
# viewing seat 0, and cluster B's while actually viewing seat 1, and comparing
# against the SAME piles dragged from the opposite (mirrored) viewpoint,
# showed a consistent ~(26,70)px disagreement between "direct" and "mirrored"
# placement — i.e. no single mirror axis reproduces the art exactly for both
# clusters. So the two clusters below are independently calibrated, each
# measured only from its own seat's direct (unflipped) view, with no formula
# relating one to the other. The client's flipXY still mirrors whichever
# cluster is "away" for a seat-1 viewer at render time (see app.js) — that
# per-viewer rendering step is unrelated to how these stored values were set.
_CLUSTER_A = {
    "deck": {"x": 1194, "y": 1039},
    "graveyard": {"x": 1366, "y": 1039},
    "receptacle": {"x": 1192, "y": 1297},
    "exile": {"x": 1366, "y": 1297},
}
_CLUSTER_B = {
    "deck": {"x": 234, "y": 375},
    "graveyard": {"x": 59, "y": 375},
    "receptacle": {"x": 235, "y": 121},
    "exile": {"x": 62, "y": 121},
}
DEFAULT_ZONE_POSITIONS = [_CLUSTER_A, _CLUSTER_B]


def gen_code(length=6):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I ambiguity
    return "".join(random.choices(alphabet, k=length))


def new_id():
    return uuid.uuid4().hex[:12]


def make_player(player_id, name, cluster_index=0):
    seat = cluster_index % len(DEFAULT_ZONE_POSITIONS)
    positions = DEFAULT_ZONE_POSITIONS[seat]
    return {
        "id": player_id,
        "name": name,
        "connected": False,
        "score": 0,
        "seat": seat,
        "zones": {zone: [] for zone in ALL_ZONES},
        "zonePositions": {zone: dict(pos) for zone, pos in positions.items()},
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
                    zones_view[zone] = {"cards": list(cards)}
                else:
                    zones_view[zone] = {"count": len(cards)}
            players_view[pid] = {
                "id": pid,
                "name": player["name"],
                "connected": player["connected"],
                "score": player["score"],
                "seat": player["seat"],
                "zones": zones_view,
                "zonePositions": player["zonePositions"],
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
            battlefield_view.append(entry)

        return {
            "type": "state",
            "players": players_view,
            "battlefield": battlefield_view,
            "tokens": list(self.tokens),
            "strokes": list(self.strokes),
            "ended": self.ended,
        }

    def serialize_log(self):
        return {"type": "log", "entries": self.log}
