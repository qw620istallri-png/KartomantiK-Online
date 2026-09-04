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
            # a small tail of the action log, piggybacked on every state sync so
            # the opponent-row mini activity feed updates live without a
            # separate poll — the full log (request_log) is still the
            # authoritative, complete history used for the debug/download panel
            "recentLog": self.log[-30:],
        }

    def serialize_log(self):
        return {"type": "log", "entries": self.log}
