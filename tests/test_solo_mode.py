import asyncio
import json
import os
import sys
import unittest

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve


SERVER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server"))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

import main as server_main
from session import ADVANCED_PHASES


class SoloModeIntegrationTests(unittest.IsolatedAsyncioTestCase):
    STARTER_DECKS = json.loads(
        open(
            os.path.join(SERVER_DIR, "..", "public", "starter-decks.json"),
            encoding="utf-8",
        ).read()
    )

    async def asyncSetUp(self):
        server_main.sessions.clear()
        server_main.connections.clear()
        self.server = await serve(
            server_main.handler,
            "127.0.0.1",
            0,
            process_request=server_main.process_request,
            compression=None,
        )
        port = self.server.sockets[0].getsockname()[1]
        self.uri = f"ws://127.0.0.1:{port}/ws"
        self.clients = []

    async def asyncTearDown(self):
        for websocket in self.clients:
            await websocket.close()
        await asyncio.sleep(0)
        self.server.close()
        await self.server.wait_closed()
        server_main.sessions.clear()
        server_main.connections.clear()

    async def receive_until(self, websocket, predicate, limit=50):
        for _index in range(limit):
            message = json.loads(
                await asyncio.wait_for(websocket.recv(), timeout=2)
            )
            if predicate(message):
                return message
        self.fail("Expected WebSocket message was not received.")

    async def join(self, payload):
        websocket = await connect(self.uri)
        self.clients.append(websocket)
        await websocket.send(json.dumps({"type": "join", **payload}))
        message = await self.receive_until(
            websocket,
            lambda entry: entry.get("type") in {"joined", "error"},
        )
        return websocket, message

    async def create_solo(self, rules=False):
        websocket, joined = await self.join({
            "createSolo": True,
            "rulesBeta": rules,
            "name": "P1",
            "opponentName": "P2",
            "clientId": "solo-browser",
        })
        self.assertEqual(joined["type"], "joined")
        await self.receive_until(
            websocket, lambda entry: entry.get("type") == "state"
        )
        return websocket, joined, server_main.sessions[joined["codePlayer"]]

    async def test_solo_creation_has_two_controlled_seats_and_full_visibility(self):
        websocket, joined, session = await self.create_solo()
        p1, p2 = joined["controlledPlayerIds"]
        self.assertTrue(joined["solo"])
        self.assertEqual(joined["mode"], "solo")
        self.assertEqual(list(session.players), [p1, p2])
        self.assertEqual([session.players[p1]["seat"], session.players[p2]["seat"]], [0, 1])
        session.put_zone_card(p1, "hand", "p1-secret", p1)
        session.put_zone_card(p2, "hand", "p2-secret", p2)
        session.put_zone_card(p2, "deck", "p2-deck-secret", p2)

        state = session.serialize_for(p1, "player")

        self.assertEqual(state["players"][p1]["zones"]["hand"]["cards"], ["p1-secret"])
        self.assertEqual(state["players"][p2]["zones"]["hand"]["cards"], ["p2-secret"])
        self.assertEqual(state["players"][p2]["zones"]["deck"]["cards"], ["p2-deck-secret"])
        self.assertEqual(state["solo"]["controlledPlayerIds"], [p1, p2])

    async def test_solo_connection_can_act_for_either_seat(self):
        websocket, joined, session = await self.create_solo()
        p1, p2 = joined["controlledPlayerIds"]
        await websocket.send(json.dumps({
            "type": "set_score",
            "actingPlayerId": p2,
            "playerId": p2,
            "value": 17,
        }))
        state = await self.receive_until(
            websocket,
            lambda entry: entry.get("type") == "state"
            and entry.get("players", {}).get(p2, {}).get("score") == 17,
        )
        self.assertEqual(state["players"][p1]["score"], 0)
        self.assertEqual(session.players[p2]["score"], 17)

    async def test_solo_assisted_priority_can_be_passed_for_p2(self):
        websocket, joined, session = await self.create_solo(rules=True)
        p1, p2 = joined["controlledPlayerIds"]
        session.rules_engine.update({
            "deckConfirmedPlayerIds": [p1, p2],
            "readyPlayerIds": [p1, p2],
            "firstManifestationComplete": True,
            "priorityPlayerId": p2,
            "priorityPasses": [],
            "autoSkipPhases": False,
        })
        session.phase_tracker["turn"] = 2
        session.phase_tracker["index"] = ADVANCED_PHASES.index(
            "confrontation_reaction"
        )
        await websocket.send(json.dumps({
            "type": "pass_priority",
            "actingPlayerId": p2,
            "passed": True,
        }))
        state = await self.receive_until(
            websocket,
            lambda entry: entry.get("type") == "state"
            and entry.get("rulesEngine", {}).get("priorityPlayerId") == p1,
        )
        self.assertEqual(state["rulesEngine"]["priorityPasses"], [p2])

    async def test_solo_can_import_and_confirm_a_deck_for_each_seat(self):
        websocket, joined, session = await self.create_solo()
        p1, p2 = joined["controlledPlayerIds"]
        for player_id, deck in zip((p1, p2), self.STARTER_DECKS[:2]):
            await websocket.send(json.dumps({
                "type": "import_deck",
                "actingPlayerId": player_id,
                "deck": deck,
                "name": deck["name"],
                "confirmDeck": True,
            }))
            response = await self.receive_until(
                websocket,
                lambda entry: entry.get("type") in {"state", "error"},
            )
            self.assertEqual(response.get("type"), "state", response)
            self.assertIn(
                player_id,
                response.get("rulesEngine", {}).get(
                    "deckConfirmedPlayerIds", []
                ),
            )
        self.assertEqual(
            set(session.rules_engine["deckConfirmedPlayerIds"]), {p1, p2}
        )
        self.assertTrue(session.players[p1]["deckDefinition"])
        self.assertTrue(session.players[p2]["deckDefinition"])
        self.assertEqual(
            [
                len(session.players[player_id]["zones"]["hand"])
                for player_id in (p1, p2)
            ],
            [7, 7],
        )

    async def test_normal_session_rejects_acting_as_the_other_player(self):
        websocket, joined = await self.join({
            "createNew": True,
            "name": "P1",
            "clientId": "normal-p1",
        })
        self.assertEqual(joined["type"], "joined")
        code = joined["codePlayer"]
        _peer, peer_joined = await self.join({
            "code": code,
            "name": "P2",
            "clientId": "normal-p2",
        })
        await websocket.send(json.dumps({
            "type": "set_score",
            "actingPlayerId": peer_joined["playerId"],
            "playerId": peer_joined["playerId"],
            "value": 99,
        }))
        error = await self.receive_until(
            websocket, lambda entry: entry.get("type") == "error"
        )
        self.assertIn("cannot act", error["message"])

    async def test_solo_reconnect_requires_the_original_browser_identity(self):
        websocket, joined, session = await self.create_solo()
        code = joined["codePlayer"]
        await websocket.close()
        reconnect, rejoined = await self.join({
            "code": code,
            "name": "P1",
            "clientId": "solo-browser",
        })
        self.assertEqual(rejoined["controlledPlayerIds"], joined["controlledPlayerIds"])
        self.assertEqual(list(session.players), joined["controlledPlayerIds"])
        await reconnect.close()
        _other, rejected = await self.join({
            "code": code,
            "name": "Other",
            "clientId": "other-browser",
        })
        self.assertEqual(rejected["type"], "error")
        self.assertIn("belongs to another browser", rejected["message"])


if __name__ == "__main__":
    unittest.main()
