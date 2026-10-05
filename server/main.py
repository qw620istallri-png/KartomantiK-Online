"""Kartomantik Online — relay server.

Serves the static client from ../public and relays game actions over
WebSocket. Holds no game rules: it only enforces WHO may see/touch WHICH
zone (see session.py), applies the action, and rebroadcasts a
permission-filtered state snapshot to every connection in the session.
"""
import asyncio
import copy
import json
import logging
import mimetypes
import os
import random
import sys
import time

from websockets.asyncio.server import serve
from websockets.http11 import Response
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed

from session import Session, new_id, validate_tournament_deck, PRIVATE_ZONES, SHARED_ZONES, ALL_ZONES

mimetypes.add_type("image/webp", ".webp")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("kartomantik-online")

PUBLIC_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "public"))
HAND_LIMIT = 7
TEMPERAMENTS = {"capricious", "choleric", "hollow", "melancholic", "phlegmatic", "transcendent", "vitreous"}
RARITIES = {"foil", "silver", "gold", "desert", "galaxy", "void", "common-glitter", "foil-glitter", "silver-glitter", "gold-glitter", "desert-glitter"}
VERSIONED_CACHE = "public, max-age=31536000, immutable"
STATIC_CACHE = "public, max-age=86400, stale-while-revalidate=604800"
STATIC_CACHE_EXTENSIONS = {".avif", ".gif", ".ico", ".jpeg", ".jpg", ".png", ".svg", ".ttf", ".webp", ".woff", ".woff2"}


def load_card_data():
    with open(os.path.join(PUBLIC_DIR, "cards-data.json"), "r", encoding="utf-8") as card_file:
        return json.load(card_file)


CARD_DATA = load_card_data()
CARD_POINTS = {card["id"]: int(card.get("points") or 0) for card in CARD_DATA}
CARD_LABELS = {card["id"]: f'{card.get("name") or card["id"]} ({int(card.get("collectionNumber") or 0):03d})' for card in CARD_DATA}
CARD_ID_BY_NUMBER = {int(card.get("collectionNumber") or 0): card["id"] for card in CARD_DATA}
DEFAULT_TOURNAMENT_POLICY = {
    "bannedCardIds": [CARD_ID_BY_NUMBER[number] for number in (82, 128, 86)],
    "restrictedGroups": [{
        "id": "restricted-1",
        "name": "Restricted group 1",
        "cardIds": [CARD_ID_BY_NUMBER[number] for number in (267, 284, 281)],
    }],
}


def find_player_ws(session, player_id):
    for ws, info in connections.items():
        if info["session"] is session and info["playerId"] == player_id and info.get("role") == "player":
            return ws
    return None


def apply_stack_fields(session, item, data):
    """Set, clear, or leave untouched an item's stackedOn relationship from a
    place_card/move_battlefield_item payload. The offset is screen-space pixels
    (never flipped for either viewer — see flipY in app.js), so the server just
    stores it opaquely; it never does the math. Returns an error message, or
    None on success.

    Three explicit outcomes, not two: callers that don't mention stacking at
    all (e.g. the "exhaust"/rotate action, which only ever sends x/y unchanged
    plus rotation) must NOT silently detach a stacked card as a side effect —
    only an explicit stackOnId (attach) or unstack flag (detach) may change it.
    """
    if data.get("stackOnId"):
        stack_on_id = data["stackOnId"]
    elif data.get("unstack"):
        item["stackedOn"] = None
        return None
    else:
        return None
    if stack_on_id == item["id"]:
        return "A card cannot stack on itself."
    anchor = session.find_battlefield_item(stack_on_id)
    if anchor is None:
        return "Stack target not found."
    if anchor.get("stackedOn"):
        return "Cannot stack on a card that is itself stacked (no chains)."
    item["stackedOn"] = stack_on_id
    item["stackOffsetX"] = float(data.get("offsetX") or 0)
    item["stackOffsetY"] = float(data.get("offsetY") or 0)
    return None


def unstack_dependents(session, removed_item_id):
    """When an anchor leaves the battlefield, whatever was stacked on it falls back
    to its own last x/y (frozen from before it was stacked — see apply_stack_fields)
    rather than staying attached to a card that no longer exists."""
    for other in session.battlefield:
        if other.get("stackedOn") == removed_item_id:
            other["stackedOn"] = None

sessions: dict[str, Session] = {}  # keyed by the session's creator/player code
connections: dict[object, dict] = {}  # websocket -> session, playerId, role, isObserver


def find_session_by_code(code):
    code = (code or "").strip().upper()
    if not code:
        return None, None, None
    for session in sessions.values():
        if session.mode == "casual":
            if session.code_player == code:
                return session, "player", None
            if session.code_observer == code:
                return session, "observer", None
        else:
            role_codes = {
                session.code_player1: ("player", 0),
                session.code_player2: ("player", 1),
                session.code_spectator: ("spectator", None),
                session.code_judge: ("judge", None),
                session.code_organizer: ("organizer", None),
            }
            if code in role_codes:
                role, seat = role_codes[code]
                return session, role, seat
    return None, None, None


# ---------------------------------------------------------------- static files

async def serve_static(path):
    versioned = "?v=" in path
    if path in ("", "/"):
        path = "/index.html"
    path = path.split("?", 1)[0]
    safe_rel = os.path.normpath(path).lstrip("\\/")
    full_path = os.path.normpath(os.path.join(PUBLIC_DIR, safe_rel))
    # websockets' HTTP support is a thin layer meant for the WS handshake, not
    # a real static file server — it doesn't reliably handle a browser reusing
    # one keep-alive connection for a page's many sequential asset requests
    # (seen as intermittent 404s/broken images through a real proxy, never
    # locally). Forcing a fresh connection per request sidesteps that instead
    # of trying to make keep-alive work in a library not built for it.
    if not (full_path == PUBLIC_DIR or full_path.startswith(PUBLIC_DIR + os.sep)):
        return Response(403, "Forbidden", Headers([("Connection", "close")]), b"Forbidden")
    if not os.path.isfile(full_path):
        return Response(404, "Not Found", Headers([("Connection", "close")]), b"Not Found")
    with open(full_path, "rb") as f:
        body = f.read()
    content_type, _ = mimetypes.guess_type(full_path)
    headers = Headers()
    headers["Content-Type"] = content_type or "application/octet-stream"
    headers["Content-Length"] = str(len(body))
    extension = os.path.splitext(full_path)[1].lower()
    if safe_rel == "index.html":
        headers["Cache-Control"] = "no-cache"
    elif versioned:
        headers["Cache-Control"] = VERSIONED_CACHE
    elif extension in STATIC_CACHE_EXTENSIONS:
        headers["Cache-Control"] = STATIC_CACHE
    else:
        headers["Cache-Control"] = "no-cache"
    headers["Connection"] = "close"
    return Response(200, "OK", headers, body)


async def process_request(connection, request):
    if request.headers.get("Upgrade", "").lower() == "websocket":
        return None
    return await serve_static(request.path)


# ---------------------------------------------------------------- broadcasting

def encode_message(payload):
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


async def broadcast_state(session):
    stale = []
    role_counts = {
        role: sum(1 for info in connections.values() if info["session"] is session and info.get("role") == role)
        for role in ("observer", "spectator", "judge", "organizer")
    }
    role_participants = {
        role: [
            info.get("displayName") or role.title()
            for info in connections.values()
            if info["session"] is session and info.get("role") == role
        ]
        for role in ("spectator", "judge", "organizer")
    }
    for ws, info in list(connections.items()):
        if info["session"] is not session:
            continue
        payload = session.serialize_for(info["playerId"], info.get("role", "player"))
        payload["observerCount"] = sum(role_counts.values())
        payload["roleCounts"] = role_counts
        payload["roleParticipants"] = role_participants if info.get("role") in {"organizer", "judge"} else {}
        try:
            await ws.send(encode_message(payload))
        except ConnectionClosed:
            stale.append(ws)
    for ws in stale:
        connections.pop(ws, None)


async def send_to(ws, payload):
    try:
        await ws.send(encode_message(payload))
    except ConnectionClosed:
        connections.pop(ws, None)


async def send_error(ws, message, code=None):
    payload = {"type": "error", "message": message}
    if code:
        payload["code"] = code
    await send_to(ws, payload)


# ---------------------------------------------------------------- action handlers

def extract_deck_card_pools(deck_json):
    deck_ids = []
    sideboard_ids = []
    for group in deck_json.get("groups", []) or []:
        kind = str(group.get("kind") or "").lower()
        if kind == "maybeboard":
            continue
        target = sideboard_ids if kind == "sideboard" else deck_ids
        for cid in group.get("cardIds", []) or []:
            if isinstance(cid, str):
                target.append(cid)
    return deck_ids, sideboard_ids


def extract_deck_card_ids(deck_json):
    """Backward-compatible main-deck helper used by older integrations."""
    return extract_deck_card_pools(deck_json)[0]


def extract_deck_card_rarities(deck_json, card_ids):
    allowed_cards = set(card_ids)
    raw = deck_json.get("cardRarities") or {}
    if not isinstance(raw, dict):
        return {}
    return {
        card_id: rarity
        for card_id, rarity in raw.items()
        if card_id in allowed_cards and rarity in RARITIES
    }


async def handle_message(ws, info, data):
    session = info["session"]
    actor_id = info["playerId"]
    role = info.get("role", "observer" if info.get("isObserver") else "player")
    is_observer = role != "player"
    msg_type = data.get("type")

    if session.mode == "tournament" and role == "player":
        lobby_messages = {"import_deck", "set_activity", "chat_message", "leave_session", "request_log"}
        ended_messages = {"chat_message", "leave_session", "request_log"}
        if session.status == "lobby" and msg_type not in lobby_messages:
            return await send_error(ws, "The tournament match has not started yet.")
        if session.status == "ended" and msg_type not in ended_messages:
            return await send_error(ws, "The tournament match has ended.")
        search_followup_actions = {
            "draw", "draw_to_limit", "mulligan", "pass_phase", "move_card", "place_card",
            "copy_card", "reorder", "reveal", "scry", "request_hand_action", "respond_hand_action",
        }
        if session.status == "active" and msg_type in search_followup_actions:
            for alert in session.escalate_pending_searches(actor_id, msg_type):
                session.add_log(actor_id, "search_without_shuffle", {
                    "ownerId": alert["ownerId"], "zone": alert["zone"], "followupAction": msg_type,
                })

    if msg_type == "import_deck":
        if is_observer:
            return await send_error(ws, "Observers cannot import a deck.")
        if session.mode == "tournament" and session.status != "lobby":
            return await send_error(ws, "Tournament decks are locked once the match starts.")
        player = session.players.get(actor_id)
        if player is None:
            return await send_error(ws, "Unknown player.")
        deck_json = data.get("deck") or {}
        card_ids, sideboard_ids = extract_deck_card_pools(deck_json)
        if session.mode == "tournament":
            validation_error = validate_tournament_deck(
                card_ids, sideboard_ids, CARD_POINTS, session.tournament_policy, CARD_LABELS
            )
            if validation_error:
                return await send_error(ws, validation_error)
        card_rarities = extract_deck_card_rarities(deck_json, card_ids + sideboard_ids)
        reset_own_board = bool(data.get("resetOwnBoard"))
        random.shuffle(card_ids)
        if reset_own_board:
            session.replace_player_deck(
                actor_id, card_ids, sideboard_ids, card_rarities, copy.deepcopy(deck_json)
            )
        else:
            player["zones"]["deck"] = card_ids
            player["zones"]["hand"] = []
            player["zones"]["graveyard"] = []
            player["zones"]["exile"] = []
            player["zones"]["receptacle"] = []
            player["zoneOwners"] = {zone: {} for zone in ALL_ZONES}
            player["zoneOwners"]["deck"] = {card_id: actor_id for card_id in card_ids}
            player["cardRarities"] = card_rarities
            player["sideboard"] = sideboard_ids
            player["deckDefinition"] = copy.deepcopy(deck_json)
            player["score"] = 0
        session.add_log(actor_id, "import_deck", {"count": len(card_ids)})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "copy_card":
        error, item = session.copy_card(
            actor_id, is_observer, item_id=data.get("itemId"),
            source_owner=data.get("fromOwnerId"), source_zone=data.get("fromZone"),
            card_id=data.get("cardId"), x=data.get("x"), y=data.get("y"),
        )
        if error:
            return await send_error(ws, error)
        session.add_log(actor_id, "copy_card", {"itemId": item["id"], "cardId": item["cardId"]})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "draw":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        player = session.players.get(actor_id)
        if player is None:
            return await send_error(ws, "Unknown player.")
        count = max(1, min(int(data.get("count") or 1), 50))
        drawn = []
        for _ in range(min(count, len(player["zones"]["deck"]))):
            card_id = player["zones"]["deck"][0]
            error, _ = session.move_zone_card(actor_id, "deck", actor_id, "hand", card_id, "bottom")
            if error:
                return await send_error(ws, error)
            drawn.append(card_id)
        session.add_log(actor_id, "draw", {"count": len(drawn)})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "draw_to_limit":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        player = session.players.get(actor_id)
        if player is None:
            return await send_error(ws, "Unknown player.")
        needed = max(0, HAND_LIMIT - len(player["zones"]["hand"]))
        drawn = []
        for _ in range(min(needed, len(player["zones"]["deck"]))):
            card_id = player["zones"]["deck"][0]
            error, _ = session.move_zone_card(actor_id, "deck", actor_id, "hand", card_id, "bottom")
            if error:
                return await send_error(ws, error)
            drawn.append(card_id)
        session.add_log(actor_id, "draw_to_limit", {"count": len(drawn)})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "mulligan":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        player = session.players.get(actor_id)
        if player is None:
            return await send_error(ws, "Unknown player.")
        while player["zones"]["hand"]:
            card_id = player["zones"]["hand"][0]
            error, _ = session.move_zone_card(actor_id, "hand", actor_id, "deck", card_id, "bottom")
            if error:
                return await send_error(ws, error)
        random.shuffle(player["zones"]["deck"])
        drawn = []
        for _ in range(min(HAND_LIMIT, len(player["zones"]["deck"]))):
            card_id = player["zones"]["deck"][0]
            error, _ = session.move_zone_card(actor_id, "deck", actor_id, "hand", card_id, "bottom")
            if error:
                return await send_error(ws, error)
            drawn.append(card_id)
        session.add_log(actor_id, "mulligan", {"count": len(drawn)})
        session.touch()
        await broadcast_state(session)

    elif msg_type in ("shuffle", "reorder", "reveal"):
        owner_id = data.get("ownerId") or actor_id
        zone = data.get("zone")
        if zone not in ALL_ZONES:
            return await send_error(ws, "Unknown zone.")
        player = session.players.get(owner_id)
        if player is None:
            return await send_error(ws, "Unknown player.")

        if msg_type == "reveal":
            # only the owner can choose to reveal their own zone; shared zones are already visible
            if zone in PRIVATE_ZONES and (is_observer or actor_id != owner_id):
                return await send_error(ws, "Only the owner can reveal this zone.")
            zone_cards = player["zones"][zone]
            requested_card_id = data.get("cardId")
            count = data.get("count")
            if requested_card_id:
                if requested_card_id not in zone_cards:
                    return await send_error(ws, "Card not found in that zone.")
                cards_to_reveal = [requested_card_id]
            elif count:
                cards_to_reveal = zone_cards[: max(1, min(int(count), 10))]
            else:
                cards_to_reveal = list(zone_cards)
            session.add_log(actor_id, "reveal", {"ownerId": owner_id, "zone": zone, "count": len(cards_to_reveal)})
            session.touch()
            reveal_payload = {
                "type": "reveal",
                "ownerId": owner_id,
                "zone": zone,
                "cards": cards_to_reveal,
            }
            for other_ws, other_info in list(connections.items()):
                if other_info["session"] is session:
                    await send_to(other_ws, reveal_payload)
            return

        if not session.can_act_on_zone(actor_id, is_observer, owner_id, zone):
            return await send_error(ws, "You cannot act on this zone.")

        if msg_type == "shuffle":
            random.shuffle(player["zones"][zone])
            session.add_log(actor_id, "shuffle", {"ownerId": owner_id, "zone": zone})
            resolved_search = session.resolve_search(actor_id, owner_id, zone)
            if resolved_search:
                session.add_log(actor_id, "search_followed_by_shuffle", {"ownerId": owner_id, "zone": zone})
        else:  # reorder
            order = data.get("order") or []
            current = player["zones"][zone]
            if sorted(order) != sorted(current):
                return await send_error(ws, "Reorder must be a permutation of the current zone.")
            player["zones"][zone] = order
            session.add_log(actor_id, "reorder", {"ownerId": owner_id, "zone": zone})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "scry":
        # private peek at the top N cards of your own deck: sent only back to the
        # requester, never broadcast, so it can't be used as a live info leak.
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        player = session.players.get(actor_id)
        if player is None:
            return await send_error(ws, "Unknown player.")
        count = max(1, min(int(data.get("count") or 1), 10))
        cards = player["zones"]["deck"][:count]
        session.add_log(actor_id, "scry", {"count": len(cards)})
        session.touch()
        await send_to(ws, {"type": "scry_result", "cards": cards})

    elif msg_type == "request_hand_action":
        # asking to see someone else's hand only ever gets you a live COUNT
        # (see can_view_zone) — this lets you point at "the card in slot i" and
        # ask its owner to discard/show it, but they must explicitly agree
        # before anything happens; we never resolve it to a cardId ourselves.
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        target_id = data.get("targetPlayerId")
        action = data.get("action")
        if action not in ("discard", "show"):
            return await send_error(ws, "Unknown hand action.")
        if target_id == actor_id or target_id not in session.players:
            return await send_error(ws, "Invalid target player.")
        try:
            index = int(data.get("index"))
        except (TypeError, ValueError):
            return await send_error(ws, "Invalid card index.")
        target_hand = session.players[target_id]["zones"]["hand"]
        if index < 0 or index >= len(target_hand):
            return await send_error(ws, "That card no longer exists.")
        request_id = new_id()
        session.pending_hand_requests[request_id] = {
            "requesterId": actor_id, "targetId": target_id, "index": index, "action": action,
        }
        requester = session.players.get(actor_id)
        target_ws = find_player_ws(session, target_id)
        if target_ws is not None:
            # naming the card here is safe: it only ever goes to the target,
            # about a card that's already theirs
            await send_to(target_ws, {
                "type": "hand_action_request", "requestId": request_id,
                "fromPlayerId": actor_id, "fromName": requester["name"] if requester else actor_id,
                "action": action, "cardId": target_hand[index],
            })

    elif msg_type == "respond_hand_action":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        pending = session.pending_hand_requests.pop(data.get("requestId"), None)
        if pending is None or pending["targetId"] != actor_id:
            return await send_error(ws, "That request is no longer valid.")
        requester_ws = find_player_ws(session, pending["requesterId"])
        if not data.get("accepted"):
            if requester_ws is not None:
                actor = session.players.get(actor_id)
                await send_to(requester_ws, {"type": "hand_action_declined", "byName": actor["name"] if actor else actor_id})
            return
        player = session.players.get(actor_id)
        hand = player["zones"]["hand"] if player else []
        index = pending["index"]
        if player is None or index >= len(hand):
            if requester_ws is not None:
                await send_to(requester_ws, {"type": "hand_action_failed"})
            return
        card_id = hand[index]
        requester_name = (session.players.get(pending["requesterId"]) or {}).get("name") or pending["requesterId"]
        if pending["action"] == "discard":
            error, _ = session.move_zone_card(actor_id, "hand", actor_id, "graveyard", card_id)
            if error:
                return await send_error(ws, error)
            session.add_log(actor_id, "move_card", {
                "fromOwnerId": actor_id, "fromZone": "hand", "toOwnerId": actor_id, "toZone": "graveyard",
                "position": "top", "cardId": card_id, "requestedBy": requester_name,
            })
            session.touch()
            await broadcast_state(session)
        else:  # show
            session.add_log(actor_id, "reveal", {"ownerId": actor_id, "zone": "hand", "count": 1, "requestedBy": requester_name})
            session.touch()
            reveal_payload = {"type": "reveal", "ownerId": actor_id, "zone": "hand", "cards": [card_id]}
            for other_ws, other_info in list(connections.items()):
                if other_info["session"] is session:
                    await send_to(other_ws, reveal_payload)

    elif msg_type == "move_card":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        from_owner = data.get("fromOwnerId") or actor_id
        to_owner = data.get("toOwnerId") or actor_id
        from_zone = data.get("fromZone")
        to_zone = data.get("toZone")
        card_id = data.get("cardId")
        if from_zone not in ALL_ZONES or to_zone not in ALL_ZONES:
            return await send_error(ws, "Unknown zone.")
        if not session.can_act_on_zone(actor_id, is_observer, from_owner, from_zone):
            return await send_error(ws, "You cannot act on the source zone.")
        if not session.can_act_on_zone(actor_id, is_observer, to_owner, to_zone):
            return await send_error(ws, "You cannot act on the destination zone.")
        from_player = session.players.get(from_owner)
        to_player = session.players.get(to_owner)
        if from_player is None or to_player is None:
            return await send_error(ws, "Unknown player.")
        if data.get("random"):
            if not from_player["zones"][from_zone]:
                return await send_error(ws, "That zone is empty.")
            card_id = random.choice(from_player["zones"][from_zone])
        elif not card_id:
            # no card specified: take the top/front card (e.g. "discard top of deck")
            if not from_player["zones"][from_zone]:
                return await send_error(ws, "That zone is empty.")
            card_id = from_player["zones"][from_zone][0]
        position = data.get("position") or "top"
        error, card_owner_id = session.move_zone_card(from_owner, from_zone, to_owner, to_zone, card_id, position)
        if error:
            return await send_error(ws, error)
        move_details = {
            "fromOwnerId": from_owner, "fromZone": from_zone,
            "toOwnerId": to_owner, "toZone": to_zone, "position": position,
            "cardOwnerId": card_owner_id,
        }
        # only name the card in the log when doing so doesn't leak a private
        # zone's contents — safe whenever either side is already public
        if from_zone in SHARED_ZONES or to_zone in SHARED_ZONES:
            move_details["cardId"] = card_id
        session.add_log(actor_id, "move_card", move_details)
        session.touch()
        await broadcast_state(session)

    elif msg_type == "place_card":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        source_container_id = data.get("ownerId") or actor_id
        from_zone = data.get("fromZone")
        card_id = data.get("cardId")
        if from_zone not in ALL_ZONES:
            return await send_error(ws, "Unknown zone.")
        if not session.can_act_on_zone(actor_id, is_observer, source_container_id, from_zone):
            return await send_error(ws, "You cannot act on this zone.")
        source_player = session.players.get(source_container_id)
        if source_player is None or card_id not in source_player["zones"][from_zone]:
            return await send_error(ws, "Card not found in that zone.")
        card_owner_id = session.card_owner_in_zone(source_container_id, from_zone, card_id)
        owner_player = session.players.get(card_owner_id)
        if owner_player is None:
            return await send_error(ws, "Card owner is no longer in the session.")
        item = {
            "id": new_id(),
            "ownerId": card_owner_id,
            "cardId": card_id,
            "x": float(data.get("x") or 0),
            "y": float(data.get("y") or 0),
            "faceUp": bool(data.get("faceUp", True)),
            "rotation": float(data.get("rotation") or 0),
            "counters": {},
            "rarity": owner_player.get("cardRarities", {}).get(card_id),
            "stackedOn": None,
        }
        stack_error = apply_stack_fields(session, item, data)
        if stack_error:
            return await send_error(ws, stack_error)
        session.take_zone_card(source_container_id, from_zone, card_id)
        session.battlefield.append(item)
        place_details = {"ownerId": card_owner_id, "sourceContainerId": source_container_id, "fromZone": from_zone, "itemId": item["id"], "faceUp": item["faceUp"]}
        if item["faceUp"]:
            place_details["cardId"] = card_id
        session.add_log(actor_id, "place_card", place_details)
        session.touch()
        await broadcast_state(session)

    elif msg_type == "move_battlefield_item":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        item = session.find_battlefield_item(data.get("itemId"))
        if item is None:
            return await send_error(ws, "Item not found.")
        item["x"] = float(data.get("x", item["x"]))
        item["y"] = float(data.get("y", item["y"]))
        if "rotation" in data:
            item["rotation"] = float(data.get("rotation") or 0)
        stack_error = apply_stack_fields(session, item, data)
        if stack_error:
            return await send_error(ws, stack_error)
        session.add_log(actor_id, "move_battlefield_item", {"itemId": item["id"]})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "reorder_battlefield_item":
        # paint order == array order (see renderBattlefield in app.js), so
        # this is unrelated to stackedOn — any card can be sent to the front
        # or back of the whole battlefield, stacked or not
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        item = session.find_battlefield_item(data.get("itemId"))
        if item is None:
            return await send_error(ws, "Item not found.")
        session.battlefield.remove(item)
        if data.get("position") == "back":
            session.battlefield.insert(0, item)
        else:
            session.battlefield.append(item)
        session.add_log(actor_id, "reorder_battlefield_item", {"itemId": item["id"], "position": data.get("position") or "front"})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "flip_card":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        item = session.find_battlefield_item(data.get("itemId"))
        if item is None:
            return await send_error(ws, "Item not found.")
        if item["ownerId"] != actor_id:
            return await send_error(ws, "Only the owner can flip this card.")
        item["faceUp"] = not item["faceUp"]
        flip_details = {"itemId": item["id"], "faceUp": item["faceUp"]}
        # newly face-up is already public to everyone at the table, so it's safe
        # (and useful) to name it; newly face-down must not leak what it was
        if item["faceUp"]:
            flip_details["cardId"] = item["cardId"]
        session.add_log(actor_id, "flip_card", flip_details)
        session.touch()
        await broadcast_state(session)

    elif msg_type == "remove_battlefield_item":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        item = session.find_battlefield_item(data.get("itemId"))
        if item is None:
            return await send_error(ws, "Item not found.")
        if item.get("isCopy"):
            # Copies are battlefield-only. Any attempt to send one to Deck,
            # Hand, Limbo, Exile or EV destroys it instead.
            session.battlefield.remove(item)
            unstack_dependents(session, item["id"])
            session.add_log(actor_id, "remove_battlefield_item", {"itemId": item["id"], "copyCard": True, "cardId": item.get("cardId")})
            session.touch()
            return await broadcast_state(session)
        if item.get("isTokenCard"):
            # a synthetic Token has no real cardId and no zone of its own —
            # "moving" it anywhere just removes it from the field
            if item["ownerId"] != actor_id:
                return await send_error(ws, "Only the owner can remove this token.")
            session.battlefield.remove(item)
            unstack_dependents(session, item["id"])
            session.add_log(actor_id, "remove_battlefield_item", {"itemId": item["id"], "tokenCard": True})
            session.touch()
            return await broadcast_state(session)
        to_owner = data.get("toOwnerId") or item["ownerId"]
        to_zone = data.get("toZone")
        if to_zone not in ALL_ZONES:
            return await send_error(ws, "Unknown destination zone.")
        if not session.can_act_on_zone(actor_id, is_observer, to_owner, to_zone):
            return await send_error(ws, "You cannot act on that destination zone.")
        player = session.players.get(to_owner)
        if player is None:
            return await send_error(ws, "Unknown destination player.")
        destination_error = session.destination_error(item["ownerId"], to_owner, to_zone)
        if destination_error:
            return await send_error(ws, destination_error)
        session.battlefield.remove(item)
        unstack_dependents(session, item["id"])
        # index 0 is always "the last card that entered" / the top of a deck,
        # so shared-zone piles can show it and drawing keeps working intuitively
        position = data.get("position") or "top"
        session.put_zone_card(to_owner, to_zone, item["cardId"], item["ownerId"], position)
        remove_details = {"itemId": item["id"], "toOwnerId": to_owner, "toZone": to_zone, "position": position, "faceUp": item["faceUp"]}
        # safe to name whenever it was already public (face-up) or becomes public
        # (landing in a shared zone) — same rule as move_card above
        if item["faceUp"] or to_zone in SHARED_ZONES:
            remove_details["cardId"] = item["cardId"]
        session.add_log(actor_id, "remove_battlefield_item", remove_details)
        session.touch()
        await broadcast_state(session)

    elif msg_type == "add_stroke":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        points = data.get("points") or []
        if not isinstance(points, list) or not points:
            return await send_error(ws, "A stroke needs at least one point.")
        stroke = {
            "id": data.get("id") or new_id(),
            "ownerId": actor_id,
            "color": str(data.get("color") or "#b58a24")[:20],
            "points": [[float(p[0]), float(p[1])] for p in points[:400]],
        }
        session.strokes.append(stroke)
        session.add_log(actor_id, "add_stroke", {"strokeId": stroke["id"]})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "remove_stroke":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        stroke_id = data.get("strokeId")
        session.strokes = [s for s in session.strokes if s["id"] != stroke_id]
        session.add_log(actor_id, "remove_stroke", {"strokeId": stroke_id})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "remove_strokes_in_rect":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        x0, y0, x1, y1 = (float(data.get(k) or 0) for k in ("x0", "y0", "x1", "y1"))
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        removed_ids = [
            s["id"] for s in session.strokes
            if any(x0 <= px <= x1 and y0 <= py <= y1 for px, py in s["points"])
        ]
        session.strokes = [s for s in session.strokes if s["id"] not in removed_ids]
        session.add_log(actor_id, "remove_strokes_in_rect", {"count": len(removed_ids)})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "clear_own_strokes":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        session.strokes = [s for s in session.strokes if s["ownerId"] != actor_id]
        session.add_log(actor_id, "clear_own_strokes", {})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "add_token":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        token = {
            "id": new_id(),
            "ownerId": actor_id,
            "x": float(data.get("x") or 0),
            "y": float(data.get("y") or 0),
            "label": str(data.get("label") or "")[:40],
            "color": str(data.get("color") or "#b58a24")[:20],
            "counters": {},
        }
        session.tokens.append(token)
        session.add_log(actor_id, "add_token", {"tokenId": token["id"]})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "create_token_card":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        temperament = data.get("temperament")
        if temperament not in TEMPERAMENTS:
            return await send_error(ws, "Unknown temperament.")
        try:
            power = int(data.get("power") or 0)
        except (TypeError, ValueError):
            power = 0
        power = max(-20, min(20, power))
        item = {
            "id": new_id(),
            "ownerId": actor_id,
            "cardId": None,
            "isTokenCard": True,
            "temperament": temperament,
            "power": power,
            "x": float(data.get("x") or 0),
            "y": float(data.get("y") or 0),
            "faceUp": True,
            "rotation": 0.0,
            "counters": {},
        }
        session.battlefield.append(item)
        session.add_log(actor_id, "create_token_card", {"itemId": item["id"], "temperament": temperament, "power": power})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "create_essence_token":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        neutral = bool(data.get("neutral"))
        temperament = data.get("temperament")
        if not neutral and temperament not in TEMPERAMENTS:
            return await send_error(ws, "Unknown temperament.")
        try:
            count = int(data.get("count") or 1)
        except (TypeError, ValueError):
            count = 1
        count = max(-99, min(99, count))
        token = {
            "id": new_id(),
            "ownerId": actor_id,
            "x": float(data.get("x") or 0),
            "y": float(data.get("y") or 0),
            "isEssence": True,
            "temperament": None if neutral else temperament,
            "isNeutralCounter": neutral,
            "label": str(data.get("label") or "")[:40] if neutral else "",
            "color": str(data.get("color") or "#b58a24")[:20],
            "counters": {"essence": count},
        }
        session.tokens.append(token)
        session.add_log(actor_id, "create_essence_token", {
            "tokenId": token["id"], "temperament": temperament, "count": count,
            "neutral": neutral, "label": token["label"],
        })
        session.touch()
        await broadcast_state(session)

    elif msg_type == "rename_token":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        token = session.find_token(data.get("tokenId"))
        if token is None or not token.get("isNeutralCounter"):
            return await send_error(ws, "Neutral counter not found.")
        token["label"] = str(data.get("label") or "")[:40]
        session.add_log(actor_id, "rename_token", {"tokenId": token["id"]})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "move_token":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        token = session.find_token(data.get("tokenId"))
        if token is None:
            return await send_error(ws, "Token not found.")
        token["x"] = float(data.get("x", token["x"]))
        token["y"] = float(data.get("y", token["y"]))
        session.add_log(actor_id, "move_token", {"tokenId": token["id"]})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "remove_token":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        token = session.find_token(data.get("tokenId"))
        if token is None:
            return await send_error(ws, "Token not found.")
        session.tokens.remove(token)
        session.add_log(actor_id, "remove_token", {"tokenId": token["id"]})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "add_counter":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        target = session.find_battlefield_item(data.get("itemId")) or session.find_token(data.get("tokenId"))
        if target is None:
            return await send_error(ws, "Target not found.")
        key = str(data.get("counterKey") or "counter")[:20]
        delta = int(data.get("delta") or 0)
        target["counters"][key] = target["counters"].get(key, 0) + delta
        session.add_log(actor_id, "add_counter", {"key": key, "delta": delta, "itemId": data.get("itemId"), "tokenId": data.get("tokenId")})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "reset_counter":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        target = session.find_battlefield_item(data.get("itemId")) or session.find_token(data.get("tokenId"))
        if target is None:
            return await send_error(ws, "Target not found.")
        key = str(data.get("counterKey") or "counter")[:20]
        target["counters"][key] = 0
        session.add_log(actor_id, "reset_counter", {"key": key, "itemId": data.get("itemId"), "tokenId": data.get("tokenId")})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "set_activity":
        # transient "what menu are they in" hint for the opponent's row, e.g.
        # scrying/searching/rolling dice — never private, so no observer check
        player = session.players.get(actor_id)
        if player is None:
            return
        activity = data.get("activity")
        player["activity"] = str(activity)[:20] if activity else None
        await broadcast_state(session)

    elif msg_type == "chat_message":
        text = str(data.get("text") or "").strip()[:500]
        if not text:
            return await send_error(ws, "Empty message.")
        actor = session.players.get(actor_id)
        by_name = actor["name"] if actor else role.title()
        session.add_log(actor_id, "chat_message", {"text": text}, actor_name=by_name)
        session.touch()
        payload = {"type": "chat_message", "byId": actor_id, "byName": by_name, "text": text, "timestamp": time.time()}
        for other_ws, other_info in list(connections.items()):
            if other_info["session"] is session:
                await send_to(other_ws, payload)

    elif msg_type == "roll_dice":
        # dice/coin results are always public by nature (no hidden info to
        # leak), so — like reveal — this is both logged (for the downloadable
        # record) and pushed live to everyone at the table, not just broadcast
        # via the normal state snapshot.
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        mode = data.get("mode")
        if mode not in ("d6", "coin"):
            return await send_error(ws, "Unknown dice mode.")
        count = max(1, min(int(data.get("count") or 1), 20))
        if mode == "d6":
            results = [random.randint(1, 6) for _ in range(count)]
        else:
            results = [random.choice(["H", "T"]) for _ in range(count)]
        actor = session.players.get(actor_id)
        session.add_log(actor_id, "roll_dice", {"mode": mode, "results": results})
        session.touch()
        payload = {"type": "dice_result", "byId": actor_id, "byName": actor["name"] if actor else actor_id, "mode": mode, "results": results}
        for other_ws, other_info in list(connections.items()):
            if other_info["session"] is session:
                await send_to(other_ws, payload)

    elif msg_type == "configure_phases":
        if is_observer or actor_id not in session.players:
            return await send_error(ws, "Observers cannot configure game phases.")
        enabled = data.get("enabled") if "enabled" in data else None
        advanced = data.get("advanced") if "advanced" in data else None
        if enabled is None and advanced is None:
            return await send_error(ws, "No phase setting supplied.")
        if advanced is not None and session.players[actor_id].get("seat") != 0:
            return await send_error(ws, "Only the first player can change the advanced phase mode.")
        session.configure_phases(enabled=enabled, advanced=advanced)
        session.add_log(actor_id, "configure_phases", {"enabled": session.phase_tracker["enabled"], "advanced": session.phase_tracker["advanced"]})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "pass_phase":
        if is_observer or actor_id not in session.players:
            return await send_error(ws, "Observers cannot pass phases.")
        if not session.phase_tracker["enabled"]:
            return await send_error(ws, "Game phases are not active.")
        if "passed" in data and not isinstance(data["passed"], bool):
            return await send_error(ws, "Phase pass state must be a boolean.")
        action = session.pass_phase(actor_id, passed=data.get("passed"))
        if action is None:
            return await send_error(ws, "Unable to update the phase pass.")
        # Passing and cancelling are temporary player states. Only persist the
        # shared transition once every player has passed.
        if action == "advanced":
            session.add_log(actor_id, "pass_phase", {
                "action": action,
                "phase": session.current_phase_group(),
                "phaseId": session.current_phase_id(),
                "turn": session.phase_tracker["turn"],
                "advancedMode": session.phase_tracker["advanced"],
            })
        session.touch()
        await broadcast_state(session)

    elif msg_type == "set_score":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        target_id = data.get("playerId") or actor_id
        player = session.players.get(target_id)
        if player is None:
            return await send_error(ws, "Unknown player.")
        player["score"] = int(data.get("value") if data.get("value") is not None else player["score"] + int(data.get("delta") or 0))
        session.add_log(actor_id, "set_score", {"playerId": target_id, "score": player["score"]})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "reset_board":
        # Discard every live card location, then rebuild only from each player's
        # last imported deck definition. This prevents cards from an older deck
        # that are still on the field or in a pile from leaking into the active one.
        player = session.players.get(actor_id)
        if session.mode == "tournament":
            return await send_error(ws, "Tournament matches cannot be reset by a player.")
        if is_observer or player is None or player.get("seat") != 0:
            return await send_error(ws, "Only the session's first player can reset the board.")
        active_decks = {}
        for player_id, current_player in session.players.items():
            deck_definition = copy.deepcopy(current_player.get("deckDefinition"))
            deck_json = deck_definition if isinstance(deck_definition, dict) else {}
            card_ids, sideboard_ids = extract_deck_card_pools(deck_json)
            card_rarities = extract_deck_card_rarities(deck_json, card_ids + sideboard_ids)
            random.shuffle(card_ids)
            active_decks[player_id] = {
                "cardIds": card_ids,
                "sideboardIds": sideboard_ids,
                "cardRarities": card_rarities,
                "deckDefinition": deck_definition,
            }
        session.reset_cards_to_active_decks(active_decks)
        for p in session.players.values():
            p["score"] = 0
        session.reset_phase_tracker()
        session.tokens = []
        session.strokes = []
        session.add_log(actor_id, "reset_board", {})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "end_session":
        player = session.players.get(actor_id)
        if session.mode == "tournament":
            return await send_error(ws, "Only the tournament organizer can end this match.")
        if is_observer or player is None or player.get("seat") != 0:
            return await send_error(ws, "Only the session's first player can end it for everyone.")
        session.ended = True
        session.add_log(actor_id, "end_session", {})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "leave_session":
        # unlike a disconnect (network blip, refresh — where the same clientId
        # should reconnect into the same seat), this is a deliberate "I'm done"
        # that actually frees the seat for a different browser to take
        if is_observer:
            return
        if actor_id in session.players:
            leaving_player = session.players[actor_id]
            seat = leaving_player.get("seat")
            leaving_name = leaving_player.get("name")
            if session.mode == "tournament" and session.status != "lobby":
                session.players[actor_id]["connected"] = False
            else:
                del session.players[actor_id]
                if session.mode == "tournament":
                    session.seat_claims[seat] = None
            info["left"] = True
            session.add_log(actor_id, "leave_session", {}, actor_name=leaving_name)
            session.touch()
            await broadcast_state(session)

    elif msg_type == "update_tournament_policy":
        if session.mode != "tournament" or role != "organizer":
            return await send_error(ws, "Only the tournament organizer can edit deck restrictions.")
        if session.status != "lobby":
            return await send_error(ws, "Deck restrictions lock when the match starts.")
        raw_policy = data.get("policy") or {}
        if not isinstance(raw_policy, dict):
            return await send_error(ws, "Deck restrictions must be an object.")
        raw_banned_ids = raw_policy.get("bannedCardIds") or []
        raw_restricted_groups = raw_policy.get("restrictedGroups") or []
        if not isinstance(raw_banned_ids, list) or not isinstance(raw_restricted_groups, list):
            return await send_error(ws, "Deck restriction lists are invalid.")
        if any(not isinstance(card_id, str) for card_id in raw_banned_ids):
            return await send_error(ws, "The banned list contains an invalid card.")
        banned_ids = list(dict.fromkeys(raw_banned_ids))[:100]
        if any(card_id not in CARD_POINTS for card_id in banned_ids):
            return await send_error(ws, "The banned list contains an unknown card.")
        restricted_groups = []
        for index, raw_group in enumerate(raw_restricted_groups[:20]):
            if not isinstance(raw_group, dict) or not isinstance(raw_group.get("cardIds") or [], list):
                return await send_error(ws, "A restricted group is invalid.")
            raw_card_ids = raw_group.get("cardIds") or []
            if any(not isinstance(card_id, str) for card_id in raw_card_ids):
                return await send_error(ws, "A restricted group contains an invalid card.")
            card_ids = list(dict.fromkeys(raw_card_ids))[:100]
            if any(card_id not in CARD_POINTS for card_id in card_ids):
                return await send_error(ws, "A restricted group contains an unknown card.")
            if set(card_ids) & set(banned_ids):
                return await send_error(ws, "A banned card cannot also belong to a restricted group.")
            restricted_groups.append({
                "id": str(raw_group.get("id") or f"restricted-{index + 1}")[:40],
                "name": str(raw_group.get("name") or f"Restricted group {index + 1}")[:60],
                "cardIds": card_ids,
            })
        session.tournament_policy = {"bannedCardIds": banned_ids, "restrictedGroups": restricted_groups}
        session.add_log(actor_id, "update_tournament_policy", {
            "bannedCount": len(banned_ids), "restrictedGroupCount": len(restricted_groups),
        }, actor_name="Organizer")
        session.touch()
        await broadcast_state(session)

    elif msg_type == "start_tournament":
        if session.mode != "tournament" or role != "organizer":
            return await send_error(ws, "Only the tournament organizer can start this match.")
        seats = session.tournament_summary()["seats"]
        if not all(seat["connected"] for seat in seats):
            return await send_error(ws, "Both players must be connected before the match starts.")
        if not all(seat["deckReady"] for seat in seats):
            return await send_error(ws, "Both players must import a valid 30-card deck before the match starts.")
        session.status = "active"
        session.add_log(actor_id, "start_tournament", {}, actor_name="Organizer")
        session.touch()
        await broadcast_state(session)

    elif msg_type == "search_zone":
        if is_observer:
            return await send_error(ws, "Observers cannot search a pile.")
        owner_id = data.get("ownerId") or actor_id
        zone = data.get("zone")
        if zone not in ALL_ZONES or owner_id not in session.players:
            return await send_error(ws, "Unknown pile.")
        if not session.can_view_zone(actor_id, role, owner_id, zone):
            return await send_error(ws, "You cannot search this pile.")
        count = len(session.players[owner_id]["zones"][zone])
        requires_shuffle = zone == "deck"
        session.add_log(actor_id, "search_zone", {
            "ownerId": owner_id, "zone": zone, "count": count, "requiresShuffle": requires_shuffle,
        })
        if session.mode == "tournament" and requires_shuffle:
            previous = session.pending_searches.get((actor_id, owner_id, zone))
            if previous:
                previous["status"] = "unshuffled"
                previous["severity"] = "critical"
                session.add_log(actor_id, "search_without_shuffle", {
                    "ownerId": owner_id, "zone": zone, "followupAction": "search_zone",
                })
            session.record_search(actor_id, owner_id, zone)
        session.touch()
        await broadcast_state(session)

    elif msg_type == "end_tournament":
        if session.mode != "tournament" or role != "organizer":
            return await send_error(ws, "Only the tournament organizer can end this match.")
        if session.status == "ended":
            return
        for alert in list(session.pending_searches.values()):
            if alert.get("status") == "pending":
                alert["status"] = "unshuffled"
                alert["severity"] = "critical"
                session.add_log(alert["actorId"], "search_without_shuffle", {
                    "ownerId": alert["ownerId"], "zone": alert["zone"], "followupAction": "end_tournament",
                })
        session.status = "ended"
        session.ended = True
        session.add_log(actor_id, "end_tournament", {}, actor_name="Organizer")
        session.touch()
        await broadcast_state(session)

    elif msg_type == "request_log":
        if session.mode == "tournament" and role not in {"organizer", "judge"} and session.status != "ended":
            return await send_error(ws, "The full tournament log is restricted to organizers and judges during the match.")
        log_role = "judge" if session.mode == "tournament" and session.status == "ended" and role == "player" else role
        await send_to(ws, session.serialize_log(log_role))

    else:
        await send_error(ws, f"Unknown message type: {msg_type}")


# ---------------------------------------------------------------- connection lifecycle

async def handle_join(ws, data):
    code = data.get("code")
    name = str(data.get("name") or "Player")[:30]
    client_id = str(data.get("clientId") or "")[:64]
    if not client_id:
        return await send_error(ws, "Missing clientId.")

    if data.get("createTournament"):
        session = Session(
            mode="tournament",
            tournament_policy=copy.deepcopy(DEFAULT_TOURNAMENT_POLICY),
            card_points=CARD_POINTS,
            card_labels=CARD_LABELS,
        )
        sessions[session.code_organizer] = session
        role = "organizer"
        seat = None
        session.add_log(client_id, "create_tournament", {}, actor_name=name)
        log.info("Tournament created: organizer=%s", session.code_organizer)
    elif data.get("createNew"):
        session = Session()
        sessions[session.code_player] = session
        role = "player"
        seat = None
        log.info("Session created: player=%s observer=%s", session.code_player, session.code_observer)
    else:
        session, role, seat = find_session_by_code(code)
        if session is None:
            return await send_error(ws, "No session found for that code.", code="session_not_found")

    is_observer = role != "player"
    if is_observer:
        player_id = client_id
    else:
        if session.mode == "tournament":
            claimed_by = session.seat_claims.get(seat)
            if claimed_by and claimed_by != client_id:
                return await send_error(ws, "This tournament seat has already been claimed.")
            if client_id in session.players and session.players[client_id].get("seat") != seat:
                return await send_error(ws, "This browser is already assigned to the other tournament seat.")
            session.seat_claims[seat] = client_id
        elif client_id not in session.players and len(session.players) >= 2:
            return await send_error(ws, "This session already has 2 players.")
        player = session.get_or_create_player(client_id, name, seat=seat)
        player["connected"] = True
        player_id = client_id

    connections[ws] = {
        "session": session,
        "playerId": player_id,
        "displayName": name,
        "role": role,
        "isObserver": is_observer,
    }
    session.add_log(player_id, "role_joined", {"role": role, "seat": seat}, actor_name=name)
    session.touch()

    await send_to(ws, {
        "type": "joined",
        "playerId": player_id,
        "isObserver": is_observer,
        "role": role,
        "mode": session.mode,
        "codePlayer": session.code_player if not is_observer else None,
        "codeObserver": session.code_observer,
        "codeOrganizer": session.code_organizer if role == "organizer" else None,
        "tournamentCodes": session.tournament_codes() if role == "organizer" else None,
    })
    await broadcast_state(session)


async def handler(ws):
    try:
        async for raw in ws:
            try:
                data = json.loads(raw)
            except (ValueError, TypeError):
                await send_error(ws, "Invalid message.")
                continue
            if ws not in connections:
                if data.get("type") == "join":
                    await handle_join(ws, data)
                else:
                    await send_error(ws, "Join a session first.")
                continue
            info = connections[ws]
            if data.get("type") == "join":
                # allow re-join (e.g. reconnect flow) to refresh player info
                await handle_join(ws, data)
                continue
            await handle_message(ws, info, data)
    except ConnectionClosed:
        pass
    finally:
        info = connections.pop(ws, None)
        if info:
            if info.get("role") == "player" and not info.get("left"):
                player = info["session"].players.get(info["playerId"])
                if player:
                    player["connected"] = False
                    info["session"].add_log(info["playerId"], "player_disconnected", {"seat": player.get("seat")})
            await broadcast_state(info["session"])


async def main():
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8787"))
    async with serve(handler, host, port, process_request=process_request, compression="deflate"):
        log.info("Kartomantik Online listening on %s:%s", host, port)
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
