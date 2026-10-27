"""Real mixed-protocol sockets; draw stimulus and phase timing are isolated."""
import unittest
from unittest.mock import AsyncMock, patch

import test_state_transport_integration as transport
import test_bounce_replay_integration as bounce
import test_kanon_event_clauses as clauses

main = transport.main


class KanonEventsIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = transport.StateTransportIntegration.asyncSetUp
    asyncTearDown = transport.StateTransportIntegration.asyncTearDown
    join = transport.StateTransportIntegration.join
    receive_until = transport.StateTransportIntegration.receive_until
    send = transport.StateTransportIntegration.send
    prepare_active_rules = transport.StateTransportIntegration.prepare_active_rules
    pass_stack = bounce.BounceReplayIntegration.pass_stack

    def setup_rules(self, deck):
        f, s = clauses.KanonEventClauses(), self.session
        self.prepare_active_rules("confrontation_reaction")
        s.phase_tracker.update(enabled=True, advanced=True, turn=2)
        s.rules_engine.update(firstManifestationComplete=True, firstManifestationTriggersQueued=True)
        fixture = f.world()
        for cid in ("m2", "m3", "m4", "w2", "pw3"):
            s.card_rules[cid] = fixture.card_rules[cid]
            if cid.startswith("m"):
                s.manifestation_ids.add(cid)
        f.field(s, f.cid(f.KANON), "kanon", owner="p2")
        f.put(s, "p1", "deck", deck)
        return f, s

    async def start_draw(self, count):
        self.session.request_rules_draw("p1", count)
        await main.broadcast_state(self.session)
        return await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and
            (m["rulesEngine"]["pendingChoice"] or {}).get("kind") == "draw_replacement")

    async def reconnect(self, choice_id):
        await self.ws1.close()
        ws, _ = await self.join({"type": "join", "code": self.code, "name": "P1", "clientId": "p1"})
        state = await self.receive_until(ws, lambda m: m.get("type") == "state")
        self.assertEqual(state["rulesEngine"]["pendingChoice"]["id"], choice_id)
        self.assertEqual(self.wires[ws][-1]["stateRevision"], 1)
        return ws, state

    @patch("main.auto_advance_rules_phases", new_callable=AsyncMock, return_value=False)
    async def test_kanon_duplicate_copies_reconnect_and_denblew_exact_bonus(self, _driver):
        f, s = self.setup_rules(["m2"] * 4)
        watcher = f.watcher(s, f.DENBLEW)
        before_power = s.rules_manifestation_characteristics(watcher)["power"]
        inspected = await self.start_draw(4)
        choice_id = inspected["rulesEngine"]["pendingChoice"]["id"]
        peer = await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and
            (m["rulesEngine"]["pendingChoice"] or {}).get("id") == choice_id)
        self.assertNotIn("cardIds", peer["rulesEngine"]["pendingChoice"])
        ws, restored = await self.reconnect(choice_id)
        self.assertEqual(restored["rulesEngine"]["pendingChoice"]["cardIds"], ["m2"] * 4)
        for cards in (["m2"], ["m2", "m3"], [{}, "m2"]):
            before = f.snapshot(s)
            await self.send(ws, {"type": "resolve_rules_choice", "choiceId": choice_id, "cardIds": cards})
            await self.receive_until(ws, lambda m: m.get("type") == "error")
            self.assertEqual(f.snapshot(s), before)
        answer = {"type": "resolve_rules_choice", "choiceId": choice_id, "cardIds": ["m2", "m2"]}
        await self.send(ws, answer)
        done = await self.receive_until(ws, lambda m: m.get("type") == "state" and m["rulesEngine"]["pendingChoice"] is None
            and len(m["rulesEngine"]["actionStack"]) == 1)
        self.assertEqual(done["players"]["p1"]["zones"]["hand"]["cards"], ["m2", "m2"])
        self.assertEqual(s.players["p1"]["zones"]["graveyard"], ["m2", "m2"])
        self.assertEqual(s.players["p1"]["zones"]["deck"], [])
        self.assertEqual(done["rulesEngine"]["actionStack"][0]["source"]["cardId"], f.cid(f.DENBLEW))
        before = f.snapshot(s)
        await self.send(ws, answer)
        await self.receive_until(ws, lambda m: m.get("type") == "error")
        self.assertEqual(f.snapshot(s), before)
        sockets = {"p1": ws, "p2": self.ws2}
        first = s.rules_engine["priorityPlayerId"]
        await self.pass_stack(sockets[first], sockets["p2" if first == "p1" else "p1"])
        await self.receive_until(ws, lambda m: m.get("type") == "state" and not m["rulesEngine"]["actionStack"])
        self.assertEqual(s.rules_manifestation_characteristics(watcher)["power"], before_power + 1)

    @patch("main.auto_advance_rules_phases", new_callable=AsyncMock, return_value=False)
    async def test_tenebro_replacement_reconnect_keeps_the_whole_draw_atomic(self, _driver):
        card = clauses.KanonEventClauses.cid(clauses.KanonEventClauses.TENE)
        f, s = self.setup_rules([card, "m2"])
        inspected = await self.start_draw(2)
        await self.send(self.ws1, {"type": "resolve_rules_choice", "choiceId": inspected["rulesEngine"]["pendingChoice"]["id"], "cardIds": [card]})
        paused = await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and
            (m["rulesEngine"]["pendingChoice"] or {}).get("purpose") == "discard_support_replacement")
        choice_id = paused["rulesEngine"]["pendingChoice"]["id"]
        self.assertEqual(s.players["p1"]["zones"]["deck"], [card, "m2"])
        self.assertEqual(s.players["p1"]["zones"]["hand"], [])
        ws, restored = await self.reconnect(choice_id)
        self.assertNotIn("_operation", restored["rulesEngine"]["pendingChoice"])
        before = f.snapshot(s)
        await self.send(self.ws2, {"type": "resolve_rules_choice", "choiceId": choice_id, "option": "yes"})
        await self.receive_until(self.ws2, lambda m: m.get("type") == "error")
        self.assertEqual(f.snapshot(s), before)
        answer = {"type": "resolve_rules_choice", "choiceId": choice_id, "option": "yes"}
        await self.send(ws, answer)
        done = await self.receive_until(ws, lambda m: m.get("type") == "state" and m["rulesEngine"]["pendingChoice"] is None)
        self.assertEqual(done["players"]["p1"]["zones"]["hand"]["cards"], ["m2"])
        self.assertEqual(s.players["p1"]["zones"]["graveyard"], [])
        entered = [i for i in done["battlefield"] if i["cardId"] == card]
        self.assertEqual(len(entered), 1)
        self.assertTrue(entered[0]["isSupport"])
        self.assertEqual(s.players["p1"]["zones"]["deck"], [])
        before = f.snapshot(s)
        await self.send(ws, answer)
        await self.receive_until(ws, lambda m: m.get("type") == "error")
        self.assertEqual(f.snapshot(s), before)


if __name__ == "__main__":
    unittest.main()
