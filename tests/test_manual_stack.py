import sys
import unittest
from pathlib import Path

SERVER_DIR = str(Path(__file__).resolve().parents[1] / "server")
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

import main as server_main
from session import Session


class ManualStackTests(unittest.TestCase):
    def make_session(self, rules_beta=False):
        session = Session(rules_beta=rules_beta, card_points={}, manifestation_ids={"m-1"}, card_rules={})
        session.get_or_create_player("p1", "P1", seat=0)
        session.get_or_create_player("p2", "P2", seat=1)
        item = {"id": "a", "ownerId": "p1", "cardId": "m-1", "x": 10.0, "y": 20.0,
                "faceUp": True, "rotation": 0.0, "counters": {}, "stackedOn": "b"}
        session.battlefield = [item]
        return session, item

    def test_a_card_goes_on_the_manual_stack_and_comes_back_out(self):
        session, item = self.make_session()
        server_main.apply_manual_stack_field(session, item, {"manualStack": True})
        self.assertTrue(item["manualStack"])
        self.assertIsNone(item["stackedOn"])
        entry = session.serialize_for("p2", "player")["battlefield"][0]
        self.assertEqual(entry["manualStack"], item["manualStack"])
        # a move that does not mention it leaves the card in the Stack
        server_main.apply_manual_stack_field(session, item, {"x": 5})
        self.assertIn("manualStack", item)
        server_main.apply_manual_stack_field(session, item, {"manualStack": False})
        self.assertNotIn("manualStack", item)

    def test_the_assisted_rules_never_use_the_manual_stack(self):
        session, item = self.make_session(rules_beta=True)
        server_main.apply_manual_stack_field(session, item, {"manualStack": True})
        self.assertNotIn("manualStack", item)


class RandomVesselDiscardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import asyncio
        import json
        from websockets.asyncio.client import connect
        from websockets.asyncio.server import serve
        self.json, self.asyncio = json, asyncio
        server_main.sessions.clear()
        server_main.connections.clear()
        self.server = await serve(server_main.handler, "127.0.0.1", 0, process_request=server_main.process_request, compression=None)
        uri = f"ws://127.0.0.1:{self.server.sockets[0].getsockname()[1]}/ws"
        self.ws1 = await connect(uri)
        await self.ws1.send(json.dumps({"type": "join", "createNew": True, "name": "P1", "clientId": "p1"}))
        joined = await self.until(lambda m: m.get("type") == "joined")
        self.ws2 = await connect(uri)
        await self.ws2.send(json.dumps({"type": "join", "code": joined["codePlayer"], "name": "P2", "clientId": "p2"}))
        self.session = server_main.sessions[joined["codePlayer"]]

    async def asyncTearDown(self):
        await self.ws1.close()
        await self.ws2.close()
        self.server.close()
        await self.server.wait_closed()
        server_main.sessions.clear()
        server_main.connections.clear()

    async def until(self, predicate):
        for _ in range(40):
            message = self.json.loads(await self.asyncio.wait_for(self.ws1.recv(), timeout=2))
            if predicate(message):
                return message
        self.fail("message not received")

    async def test_a_random_vessel_card_goes_to_its_owners_limbo(self):
        p1, p2 = self.session.players["p1"], self.session.players["p2"]
        p1["zones"]["receptacle"] = ["mine", "theirs"]
        p1["zoneOwners"]["receptacle"] = {"mine": "p1", "theirs": "p2"}
        await self.ws1.send(self.json.dumps({
            "type": "move_card", "fromOwnerId": "p1", "fromZone": "receptacle", "toOwnerId": "p1",
            "toZone": "graveyard", "random": True, "toCardOwner": True,
        }))
        await self.until(lambda m: m.get("type") == "state" and len(m["players"]["p1"]["zones"]["receptacle"].get("cards", [])) == 1)
        moved = ({"mine", "theirs"} - set(p1["zones"]["receptacle"])).pop()
        owner = p1 if moved == "mine" else p2
        self.assertIn(moved, owner["zones"]["graveyard"])


if __name__ == "__main__":
    unittest.main()
