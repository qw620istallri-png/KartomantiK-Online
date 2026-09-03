"""Kartomantik Online — relay server.

Serves the static client from ../public and relays game actions over
WebSocket. Holds no game rules: it only enforces WHO may see/touch WHICH
zone (see session.py), applies the action, and rebroadcasts a
permission-filtered state snapshot to every connection in the session.
"""
import asyncio
import json
import logging
import mimetypes
import os
import random
import sys

from websockets.asyncio.server import serve
from websockets.http11 import Response
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed

from session import Session, new_id, PRIVATE_ZONES, SHARED_ZONES, ALL_ZONES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("kartomantik-online")

PUBLIC_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "public"))
HAND_LIMIT = 7
TEMPERAMENTS = {"capricious", "choleric", "hollow", "melancholic", "phlegmatic", "transcendent", "vitreous"}


def find_player_ws(session, player_id):
    for ws, info in connections.items():
        if info["session"] is session and info["playerId"] == player_id and not info["isObserver"]:
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

sessions: dict[str, Session] = {}  # keyed by a canonical session id (player code)
connections: dict[object, dict] = {}  # websocket -> {"session": Session, "playerId": str, "isObserver": bool}


def find_session_by_code(code):
    code = (code or "").strip().upper()
    if not code:
        return None, False
    for session in sessions.values():
        if session.code_player == code:
            return session, False
        if session.code_observer == code:
            return session, True
    return None, False


# ---------------------------------------------------------------- static files

async def serve_static(path):
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
    headers["Cache-Control"] = "no-cache"
    headers["Connection"] = "close"
    return Response(200, "OK", headers, body)


async def process_request(connection, request):
    if request.headers.get("Upgrade", "").lower() == "websocket":
        return None
    return await serve_static(request.path)


# ---------------------------------------------------------------- broadcasting

async def broadcast_state(session):
    stale = []
    observer_count = sum(1 for info in connections.values() if info["session"] is session and info["isObserver"])
    for ws, info in list(connections.items()):
        if info["session"] is not session:
            continue
        payload = session.serialize_for(info["playerId"], info["isObserver"])
        payload["observerCount"] = observer_count
        try:
            await ws.send(json.dumps(payload))
        except ConnectionClosed:
            stale.append(ws)
    for ws in stale:
        connections.pop(ws, None)


async def send_to(ws, payload):
    try:
        await ws.send(json.dumps(payload))
    except ConnectionClosed:
        connections.pop(ws, None)


async def send_error(ws, message):
    await send_to(ws, {"type": "error", "message": message})


# ---------------------------------------------------------------- action handlers

def extract_deck_card_ids(deck_json):
    ids = []
    for group in deck_json.get("groups", []) or []:
        if group.get("kind") == "maybeboard":
            continue
        for cid in group.get("cardIds", []) or []:
            if isinstance(cid, str):
                ids.append(cid)
    return ids


async def handle_message(ws, info, data):
    session = info["session"]
    actor_id = info["playerId"]
    is_observer = info["isObserver"]
    msg_type = data.get("type")

    if msg_type == "import_deck":
        if is_observer:
            return await send_error(ws, "Observers cannot import a deck.")
        player = session.players.get(actor_id)
        if player is None:
            return await send_error(ws, "Unknown player.")
        card_ids = extract_deck_card_ids(data.get("deck") or {})
        random.shuffle(card_ids)
        player["zones"]["deck"] = card_ids
        player["zones"]["hand"] = []
        player["zones"]["graveyard"] = []
        player["zones"]["exile"] = []
        player["zones"]["receptacle"] = []
        player["score"] = 0
        session.add_log(actor_id, "import_deck", {"count": len(card_ids)})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "draw":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        player = session.players.get(actor_id)
        if player is None:
            return await send_error(ws, "Unknown player.")
        count = max(1, min(int(data.get("count") or 1), 50))
        deck = player["zones"]["deck"]
        drawn = deck[:count]
        player["zones"]["deck"] = deck[count:]
        player["zones"]["hand"].extend(drawn)
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
        deck = player["zones"]["deck"]
        drawn = deck[:needed]
        player["zones"]["deck"] = deck[needed:]
        player["zones"]["hand"].extend(drawn)
        session.add_log(actor_id, "draw_to_limit", {"count": len(drawn)})
        session.touch()
        await broadcast_state(session)

    elif msg_type == "mulligan":
        if is_observer:
            return await send_error(ws, "Observers cannot act.")
        player = session.players.get(actor_id)
        if player is None:
            return await send_error(ws, "Unknown player.")
        player["zones"]["deck"].extend(player["zones"]["hand"])
        player["zones"]["hand"] = []
        random.shuffle(player["zones"]["deck"])
        drawn = player["zones"]["deck"][:HAND_LIMIT]
        player["zones"]["deck"] = player["zones"]["deck"][HAND_LIMIT:]
        player["zones"]["hand"] = drawn
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
            hand.remove(card_id)
            player["zones"]["graveyard"].insert(0, card_id)
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
        if card_id not in from_player["zones"][from_zone]:
            return await send_error(ws, "Card not found in source zone.")
        from_player["zones"][from_zone].remove(card_id)
        position = data.get("position") or "top"
        if position == "bottom":
            to_player["zones"][to_zone].append(card_id)
        else:
            to_player["zones"][to_zone].insert(0, card_id)
        move_details = {
            "fromOwnerId": from_owner, "fromZone": from_zone,
            "toOwnerId": to_owner, "toZone": to_zone, "position": position,
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
        owner_id = data.get("ownerId") or actor_id
        from_zone = data.get("fromZone")
        card_id = data.get("cardId")
        if from_zone not in ALL_ZONES:
            return await send_error(ws, "Unknown zone.")
        if not session.can_act_on_zone(actor_id, is_observer, owner_id, from_zone):
            return await send_error(ws, "You cannot act on this zone.")
        player = session.players.get(owner_id)
        if player is None or card_id not in player["zones"][from_zone]:
            return await send_error(ws, "Card not found in that zone.")
        player["zones"][from_zone].remove(card_id)
        item = {
            "id": new_id(),
            "ownerId": owner_id,
            "cardId": card_id,
            "x": float(data.get("x") or 0),
            "y": float(data.get("y") or 0),
            "faceUp": bool(data.get("faceUp", True)),
            "rotation": float(data.get("rotation") or 0),
            "counters": {},
            "stackedOn": None,
        }
        stack_error = apply_stack_fields(session, item, data)
        if stack_error:
            return await send_error(ws, stack_error)
        session.battlefield.append(item)
        place_details = {"ownerId": owner_id, "fromZone": from_zone, "itemId": item["id"], "faceUp": item["faceUp"]}
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
        session.battlefield.remove(item)
        unstack_dependents(session, item["id"])
        # index 0 is always "the last card that entered" / the top of a deck,
        # so shared-zone piles can show it and drawing keeps working intuitively
        position = data.get("position") or "top"
        if position == "bottom":
            player["zones"][to_zone].append(item["cardId"])
        else:
            player["zones"][to_zone].insert(0, item["cardId"])
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
        temperament = data.get("temperament")
        if temperament not in TEMPERAMENTS:
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
            "temperament": temperament,
            "label": "",
            "color": str(data.get("color") or "#b58a24")[:20],
            "counters": {"essence": count},
        }
        session.tokens.append(token)
        session.add_log(actor_id, "create_essence_token", {"tokenId": token["id"], "temperament": temperament, "count": count})
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

    elif msg_type == "end_session":
        player = session.players.get(actor_id)
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
            del session.players[actor_id]
            session.add_log(actor_id, "leave_session", {})
            session.touch()
            await broadcast_state(session)

    elif msg_type == "request_log":
        await send_to(ws, session.serialize_log())

    else:
        await send_error(ws, f"Unknown message type: {msg_type}")


# ---------------------------------------------------------------- connection lifecycle

async def handle_join(ws, data):
    code = data.get("code")
    name = str(data.get("name") or "Player")[:30]
    client_id = str(data.get("clientId") or "")[:64]
    if not client_id:
        return await send_error(ws, "Missing clientId.")

    if data.get("createNew"):
        session = Session()
        sessions[session.code_player] = session
        is_observer = False
        log.info("Session created: player=%s observer=%s", session.code_player, session.code_observer)
    else:
        session, is_observer = find_session_by_code(code)
        if session is None:
            return await send_error(ws, "No session found for that code.")

    if is_observer:
        player_id = client_id
    else:
        if client_id not in session.players and len(session.players) >= 2:
            return await send_error(ws, "This session already has 2 players.")
        player = session.get_or_create_player(client_id, name)
        player["connected"] = True
        player_id = client_id

    connections[ws] = {"session": session, "playerId": player_id, "isObserver": is_observer}
    session.touch()

    await send_to(ws, {
        "type": "joined",
        "playerId": player_id,
        "isObserver": is_observer,
        "codePlayer": session.code_player if not is_observer else None,
        "codeObserver": session.code_observer,
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
        if info and not info["isObserver"]:
            player = info["session"].players.get(info["playerId"])
            if player:
                player["connected"] = False
                await broadcast_state(info["session"])


async def main():
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8787"))
    async with serve(handler, host, port, process_request=process_request):
        log.info("Kartomantik Online listening on %s:%s", host, port)
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
