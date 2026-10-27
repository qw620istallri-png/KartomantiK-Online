"""Mixed-protocol draw choices over real local sockets; phase driver isolated."""
import unittest
from unittest.mock import AsyncMock, patch

import test_state_transport_integration as transport
import test_bounce_replay_integration as bounce
import test_discard_draw_clauses as clauses


class DiscardDrawIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = transport.StateTransportIntegration.asyncSetUp
    asyncTearDown = transport.StateTransportIntegration.asyncTearDown
    join = transport.StateTransportIntegration.join
    receive_until = transport.StateTransportIntegration.receive_until
    send = transport.StateTransportIntegration.send
    prepare_active_rules = transport.StateTransportIntegration.prepare_active_rules
    pass_stack = bounce.BounceReplayIntegration.pass_stack

    def setup_rules(self):
        f, s = clauses.DiscardDrawClauses(), self.session
        self.prepare_active_rules("confrontation_reaction")
        s.phase_tracker.update(enabled=True, advanced=True, turn=2)
        s.rules_engine.update(firstManifestationComplete=True, firstManifestationTriggersQueued=True)
        fixture = f.world()
        for cid in ("m2", "m3", "m4", "w2", "pw3"):
            s.card_rules[cid] = fixture.card_rules[cid]
            if cid.startswith("m"):
                s.manifestation_ids.add(cid)
        f.kanon(s)
        return f, s

    async def reconnect_p1(self, choice_id):
        await self.ws1.close()
        ws, _ = await self.join({"type": "join", "code": self.code, "name": "P1", "clientId": "p1"})
        restored = await self.receive_until(ws, lambda m: m.get("type") == "state")
        self.assertEqual(restored["rulesEngine"]["pendingChoice"]["id"], choice_id)
        self.assertEqual(self.wires[ws][-1]["stateRevision"], 1)
        return ws, restored

    @patch("main.auto_advance_rules_phases", new_callable=AsyncMock, return_value=False)
    async def test_pray_reconnect_preserves_discard_then_kanon_and_rejects_replay(self, _driver):
        f, s = self.setup_rules()
        f.put(s, "p1", "hand", [f.cid(f.PRAY), "w2"])
        f.put(s, "p1", "deck", ["m2", "m3", "m4"])
        await self.send(self.ws1, {"type": "declare_rules_action", "label": "Pray", "kind": "play_card",
            "source": {"cardId": f.cid(f.PRAY), "zone": "hand"}, "abilityId": "discard-one-then-draw-two"})
        await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and len(m["rulesEngine"]["actionStack"]) == 1)
        await self.pass_stack(self.ws2, self.ws1)
        paused = await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and (m["rulesEngine"]["pendingChoice"] or {}).get("kind") == "discard_from_hand")
        old_id = paused["rulesEngine"]["pendingChoice"]["id"]
        ws, _ = await self.reconnect_p1(old_id)
        before = f.snapshot(s)
        await self.send(ws, {"type": "resolve_rules_choice", "choiceId": old_id, "cardIds": []})
        await self.receive_until(ws, lambda m: m.get("type") == "error")
        self.assertEqual(f.snapshot(s), before)
        await self.send(ws, {"type": "resolve_rules_choice", "choiceId": old_id, "cardIds": ["w2"]})
        replaced = await self.receive_until(ws, lambda m: m.get("type") == "state" and (m["rulesEngine"]["pendingChoice"] or {}).get("kind") == "draw_replacement")
        choice = replaced["rulesEngine"]["pendingChoice"]
        self.assertEqual(choice["cardIds"], ["m2", "m3"])
        self.assertEqual(replaced["players"]["p1"]["zones"]["hand"]["cards"], [])
        peer = await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and (m["rulesEngine"]["pendingChoice"] or {}).get("id") == choice["id"])
        self.assertNotIn("cardIds", peer["rulesEngine"]["pendingChoice"])
        self.assertNotIn("_cardIds", choice)
        before = f.snapshot(s)
        await self.send(ws, {"type": "resolve_rules_choice", "choiceId": old_id, "cardIds": ["w2"]})
        await self.receive_until(ws, lambda m: m.get("type") == "error")
        self.assertEqual(f.snapshot(s), before)
        answer = {"type": "resolve_rules_choice", "choiceId": choice["id"], "cardIds": ["m2"]}
        await self.send(ws, answer)
        done = await self.receive_until(ws, lambda m: m.get("type") == "state" and m["rulesEngine"]["pendingChoice"] is None)
        self.assertEqual(done["players"]["p1"]["zones"]["hand"]["cards"], ["m3"])
        self.assertEqual(s.players["p1"]["zones"]["deck"], ["m4"])
        self.assertIn("m2", s.players["p1"]["zones"]["graveyard"])
        before = f.snapshot(s)
        await self.send(ws, answer)
        await self.receive_until(ws, lambda m: m.get("type") == "error")
        self.assertEqual(f.snapshot(s), before)

    @patch("main.auto_advance_rules_phases", new_callable=AsyncMock, return_value=False)
    async def test_martyrize_kanon_keeps_paid_exile_cost_through_reconnect(self, _driver):
        f, s = self.setup_rules()
        f.put(s, "p1", "hand", [f.cid(f.MARTYRIZE), "m3"])
        f.put(s, "p1", "deck", ["m2", "m4", "w2", "pw3"])
        s.add_rules_excess_essence("p1", [{"temperament": "hollow", "amount": 1}])
        await self.send(self.ws1, {"type": "declare_rules_action", "label": "Martyrize", "kind": "play_card",
            "source": {"cardId": f.cid(f.MARTYRIZE), "zone": "hand"}, "costCardId": "m3",
            "abilityId": "martyrize-exiles-hand-manifestation-to-draw"})
        await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and len(m["rulesEngine"]["actionStack"]) == 1)
        self.assertEqual(s.players["p1"]["zones"]["exile"], ["m3"])
        self.assertEqual(s.players["p1"]["zones"]["hand"], [])
        await self.pass_stack(self.ws2, self.ws1)
        paused = await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and (m["rulesEngine"]["pendingChoice"] or {}).get("kind") == "draw_replacement")
        choice_id = paused["rulesEngine"]["pendingChoice"]["id"]
        self.assertCountEqual(s.players["p1"]["zones"]["exile"], ["m3", f.cid(f.MARTYRIZE)])
        ws, restored = await self.reconnect_p1(choice_id)
        self.assertEqual(restored["rulesEngine"]["pendingChoice"]["count"], 2)
        self.assertEqual(restored["rulesEngine"]["actionStack"], [])
        before = f.snapshot(s)
        await self.send(ws, {"type": "resolve_rules_choice", "choiceId": choice_id, "cardIds": ["m2"]})
        await self.receive_until(ws, lambda m: m.get("type") == "error")
        self.assertEqual(f.snapshot(s), before)
        await self.send(ws, {"type": "resolve_rules_choice", "choiceId": choice_id, "cardIds": ["m2", "m4"]})
        done = await self.receive_until(ws, lambda m: m.get("type") == "state" and m["rulesEngine"]["pendingChoice"] is None)
        self.assertEqual(done["players"]["p1"]["zones"]["hand"]["cards"], ["w2"])
        self.assertEqual(s.players["p1"]["zones"]["deck"], ["pw3"])
        self.assertCountEqual(s.players["p1"]["zones"]["exile"], ["m3", f.cid(f.MARTYRIZE)])


if __name__ == "__main__":
    unittest.main()
