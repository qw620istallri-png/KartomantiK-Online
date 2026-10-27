"""Real mixed-version WebSockets: privacy, snapshots, reconnect and each resolution."""
import asyncio
import copy
import json
import os
import unittest
from unittest.mock import patch

import test_websocket_integration as network
import test_latency_stack_sequences as latency
from test_state_transport import reconstruct

main = network.server_main


class StateTransportIntegration(unittest.IsolatedAsyncioTestCase):
    asyncTearDown = network.WebSocketRulesIntegrationTests.asyncTearDown
    send = network.WebSocketRulesIntegrationTests.send
    prepare_active_rules = network.WebSocketRulesIntegrationTests.prepare_active_rules
    prepare = latency.LatencyStackSequences.prepare
    effect = staticmethod(latency.LatencyStackSequences.effect)
    hand = latency.LatencyStackSequences.hand
    start_auto = latency.LatencyStackSequences.start_auto
    resolved = latency.LatencyStackSequences.resolved

    async def asyncSetUp(self):
        self.baselines, self.wires, self.revisions = {}, {}, {}
        await network.WebSocketRulesIntegrationTests.asyncSetUp(self)

    async def join(self, payload):
        # P1 negotiates diffs; P2 represents an already-open legacy client.
        if payload.get("clientId") != "p2":
            payload.setdefault("stateDeltaVersion", 1)
        return await network.WebSocketRulesIntegrationTests.join(self, payload)

    async def receive_until(self, ws, predicate, limit=100):
        for _ in range(limit):
            raw = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
            self.wires.setdefault(ws, []).append(raw)
            message = raw
            if raw.get("type") == "joined":
                self.baselines.pop(ws, None)
                self.revisions.pop(ws, None)
            elif raw.get("type") == "state_patch":
                self.assertEqual(raw["baseRevision"], self.revisions[ws])
                self.assertEqual(raw["stateRevision"], self.revisions[ws] + 1)
                message = reconstruct(self.baselines[ws], raw)
                self.baselines[ws] = copy.deepcopy(message)
                self.revisions[ws] = raw["stateRevision"]
            elif raw.get("type") == "state":
                message = reconstruct(None, raw)
                self.baselines[ws] = copy.deepcopy(message)
                self.revisions[ws] = raw.get("stateRevision")
            if predicate(message):
                return message
        self.fail("Expected transport message not received")

    async def test_mixed_versions_receive_exact_role_filtered_state_without_private_patch_leaks(self):
        s = self.session
        s.players["p1"]["zones"]["hand"] = ["inner-deserts-143"]
        s.players["p2"]["zones"]["hand"] = ["inner-deserts-100"]
        s.players["p1"]["score"] = 12
        await main.broadcast_state(s)
        own = await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and m["players"]["p1"]["score"] == 12)
        peer = await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and m["players"]["p1"]["score"] == 12)
        self.assertEqual(own["players"]["p1"]["zones"]["hand"]["cards"], ["inner-deserts-143"])
        self.assertNotIn("cards", own["players"]["p2"]["zones"]["hand"])
        self.assertNotIn("cards", peer["players"]["p1"]["zones"]["hand"])
        self.assertEqual(self.wires[self.ws1][-1]["type"], "state_patch")
        self.assertEqual(self.wires[self.ws2][-1]["type"], "state")
        for state, pid in ((own, "p1"), (peer, "p2")):
            expected = s.serialize_for(pid, "player")
            self.assertEqual({k: v for k, v in state.items() if k in expected}, expected)
        s.rules_engine["pendingChoice"] = {"id": "private", "kind": "discard_from_hand", "playerId": "p1", "candidateCardIds": ["inner-deserts-143"]}
        await main.broadcast_state(s)
        await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and (m["rulesEngine"]["pendingChoice"] or {}).get("id") == "private")
        await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and (m["rulesEngine"]["pendingChoice"] or {}).get("id") == "private")
        self.assertNotIn("candidateCardIds", self.wires[self.ws2][-1]["rulesEngine"]["pendingChoice"])
        observer, _ = await self.join({"type": "join", "code": s.code_observer, "name": "Observer", "clientId": "watcher"})
        observed = await self.receive_until(observer, lambda m: m.get("type") == "state")
        # Casual observers are trusted viewers in the existing permissions model.
        self.assertEqual(observed["rulesEngine"]["pendingChoice"], s.serialize_for("watcher", "observer")["rulesEngine"]["pendingChoice"])
        self.assertEqual(observed["players"]["p1"]["zones"]["hand"]["cards"], ["inner-deserts-143"])

    async def test_resync_is_full_even_unchanged_then_diffs_resume(self):
        previous = next(info["_state_stream"].revision for info in main.connections.values() if info["playerId"] == "p1")
        await self.send(self.ws1, {"type": "request_state"})
        await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and self.wires[self.ws1][-1].get("type") == "state"
                                 and self.wires[self.ws1][-1].get("stateRevision", 0) > previous)
        self.assertEqual(self.wires[self.ws1][-1]["type"], "state")
        revision = self.wires[self.ws1][-1]["stateRevision"]
        self.session.players["p1"]["score"] = 19
        await main.broadcast_state(self.session)
        await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and m["players"]["p1"]["score"] == 19)
        self.assertEqual(self.wires[self.ws1][-1]["baseRevision"], revision)

    async def test_reconnect_and_role_change_start_new_full_private_baselines(self):
        s = self.session
        s.players["p1"]["zones"]["hand"] = ["inner-deserts-143"]
        s.players["p2"]["zones"]["hand"] = ["inner-deserts-100"]
        await self.ws1.close()
        ws, joined = await self.join({"type": "join", "code": self.code, "name": "P1", "clientId": "p1"})
        await self.receive_until(ws, lambda m: m.get("type") == "state")
        self.assertEqual(self.wires[ws][-1]["stateRevision"], 1)
        self.assertEqual(joined["stateDeltaVersion"], 1)
        await self.send(ws, {"type": "join", "code": s.code_observer, "name": "Watcher", "clientId": "watcher", "stateDeltaVersion": 1})
        await self.receive_until(ws, lambda m: m.get("type") == "joined")
        state = await self.receive_until(ws, lambda m: m.get("type") == "state")
        self.assertEqual(self.wires[ws][-1]["stateRevision"], 1)
        self.assertIn("cards", state["players"]["p2"]["zones"]["hand"])
        await self.send(ws, {"type": "join", "code": self.code, "name": "P1", "clientId": "p1", "stateDeltaVersion": 1})
        await self.receive_until(ws, lambda m: m.get("type") == "joined")
        state = await self.receive_until(ws, lambda m: m.get("type") == "state")
        self.assertEqual(self.wires[ws][-1]["stateRevision"], 1)
        self.assertNotIn("cards", state["players"]["p2"]["zones"]["hand"])

    async def test_tournament_spectators_do_not_receive_private_snapshots_or_patches(self):
        await self.join({"type": "join", "createTournament": True, "name": "Host", "clientId": "host"})
        s = next(s for s in main.sessions.values() if s.mode == "tournament")
        s.get_or_create_player("one", "One", seat=0)
        s.players["one"]["zones"]["hand"] = ["inner-deserts-143"]
        s.rules_engine["pendingChoice"] = {"id": "secret", "kind": "discard_from_hand", "playerId": "one", "candidateCardIds": ["inner-deserts-143"]}
        ws, _ = await self.join({"type": "join", "code": s.code_spectator, "name": "Spectator", "clientId": "spectator"})
        first = await self.receive_until(ws, lambda m: m.get("type") == "state")
        self.assertNotIn("cards", first["players"]["one"]["zones"]["hand"])
        self.assertNotIn("candidateCardIds", first["rulesEngine"]["pendingChoice"])
        s.players["one"]["score"] = 9
        s.players["one"]["zones"]["hand"] = ["inner-deserts-100"]
        await main.broadcast_state(s)
        state = await self.receive_until(ws, lambda m: m.get("type") == "state" and m["players"]["one"]["score"] == 9)
        self.assertEqual(self.wires[ws][-1]["type"], "state_patch")
        self.assertNotIn("inner-deserts-100", json.dumps(self.wires[ws][-1]))
        self.assertNotIn("cards", state["players"]["one"]["zones"]["hand"])

    async def test_server_rollback_and_unsupported_versions_keep_complete_states(self):
        for version, disabled in ((1, True), (2, False), (True, False)):
            with self.subTest(version=version, disabled=disabled):
                with patch.dict(os.environ, {"KKO_STATE_DELTAS": "0" if disabled else "1"}):
                    await self.send(self.ws1, {"type": "join", "code": self.code, "name": "P1", "clientId": "p1", "stateDeltaVersion": version})
                    joined = await self.receive_until(self.ws1, lambda m: m.get("type") == "joined")
                    self.assertEqual(joined["stateDeltaVersion"], 0)
                    await self.receive_until(self.ws1, lambda m: m.get("type") == "state")
                    self.assertNotIn("stateRevision", self.wires[self.ws1][-1])

    @patch.object(main, "STACK_RESOLUTION_PAUSE_SECONDS", 0)
    async def test_new_and_old_clients_observe_each_of_thirty_three_resolutions(self):
        self.prepare([self.effect(f"wire-{n}") for n in range(33)], auto=True)
        await self.start_auto(auto=True)
        for count, n in enumerate(reversed(range(33)), 1):
            states = await asyncio.gather(self.resolved(self.ws1, f"wire-{n}"), self.resolved(self.ws2, f"wire-{n}"))
            for state in states:
                self.assertEqual(state["players"]["p1"]["score"], count)
                self.assertEqual(len(state["rulesEngine"]["actionStack"]), 33 - count)
        self.assertTrue(any(m["type"] == "state_patch" for m in self.wires[self.ws1]))
        self.assertFalse(any(m["type"] == "state_patch" for m in self.wires[self.ws2]))


if __name__ == "__main__":
    unittest.main()
