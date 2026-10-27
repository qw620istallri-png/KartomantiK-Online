"""Mixed-version two-seat choices and reconnect; phase driving is isolated."""
import unittest
from unittest.mock import AsyncMock, patch

import test_state_transport_integration as transport
import test_bounce_replay_integration as bounce
import test_atavic_end_clauses as clauses

main = transport.main


class AtavicEndIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = transport.StateTransportIntegration.asyncSetUp
    asyncTearDown = transport.StateTransportIntegration.asyncTearDown
    join = transport.StateTransportIntegration.join
    receive_until = transport.StateTransportIntegration.receive_until
    send = transport.StateTransportIntegration.send
    prepare_active_rules = transport.StateTransportIntegration.prepare_active_rules
    pass_stack = bounce.BounceReplayIntegration.pass_stack

    def setup_rules(self):
        f, s = clauses.AtavicEndClauses(), self.session
        self.prepare_active_rules("confrontation_reaction")
        s.phase_tracker.update(enabled=True, advanced=True, turn=2)
        s.rules_engine.update(firstManifestationComplete=True, firstManifestationTriggersQueued=True)
        fixture = f.world()
        for cid in ("m2", "m3", "m4", "w2", "pw3"):
            s.card_rules[cid] = fixture.card_rules[cid]
            if cid.startswith("m"):
                s.manifestation_ids.add(cid)
        return f, s

    @patch("main.auto_advance_rules_phases", new_callable=AsyncMock, return_value=False)
    async def test_oppression_reconnect_keeps_discard_then_draws_once_after_confirmation(self, _driver):
        f, s = self.setup_rules()
        host = f.host(s, f.OPPRESSION, "Fatigue", 5)
        f.put(s, "p1", "deck", ["m4", "m3"])
        f.put(s, "p2", "hand", ["m2"])
        await self.send(self.ws1, {"type": "declare_rules_action", "label": "Oppression", "kind": "activated_effect",
            "source": {"cardId": host["cardId"], "zone": "battlefield", "itemId": host["id"]},
            "abilityId": "spend-fatigues-to-make-opponent-discard"})
        await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and len(m["rulesEngine"]["actionStack"]) == 1)
        self.assertEqual(host["counters"]["Fatigue"], 0)
        await self.pass_stack(self.ws2, self.ws1)
        paused = await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and (m["rulesEngine"]["pendingChoice"] or {}).get("kind") == "discard_from_hand")
        choice_id = paused["rulesEngine"]["pendingChoice"]["id"]
        self.assertEqual(paused["players"]["p1"]["zones"]["hand"]["cards"], [])
        self.assertNotIn("_ownerDrawAfterDiscard", paused["rulesEngine"]["pendingChoice"])
        await self.ws2.close()
        ws, _ = await self.join({"type": "join", "code": self.code, "name": "P2", "clientId": "p2"})
        restored = await self.receive_until(ws, lambda m: m.get("type") == "state")
        self.assertEqual(restored["rulesEngine"]["pendingChoice"]["id"], choice_id)
        before = f.snapshot(s)
        await self.send(ws, {"type": "resolve_rules_choice", "choiceId": choice_id, "cardIds": []})
        await self.receive_until(ws, lambda m: m.get("type") == "error")
        self.assertEqual(f.snapshot(s), before)
        answer = {"type": "resolve_rules_choice", "choiceId": choice_id, "cardIds": ["m2"]}
        await self.send(ws, answer)
        done = await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and m["players"]["p1"]["zones"]["hand"]["cards"] == ["m4"])
        self.assertEqual(done["players"]["p2"]["zones"]["graveyard"]["cards"], ["m2"])
        self.assertIsNone(done["rulesEngine"]["pendingChoice"])
        before = f.snapshot(s)
        await self.send(ws, answer)
        await self.receive_until(ws, lambda m: m.get("type") == "error")
        self.assertEqual(f.snapshot(s), before)
        self.assertEqual(s.players["p1"]["zones"]["deck"], ["m3"])

    @patch("main.auto_advance_rules_phases", new_callable=AsyncMock, return_value=False)
    async def test_introspection_reconnect_preserves_exact_top_bottom_choice_and_rejects_bad_order(self, _driver):
        f, s = self.setup_rules()
        host = f.host(s, f.INTROSPECTION, "Control")
        f.put(s, "p1", "graveyard", ["m2", "w2"])
        f.put(s, "p1", "deck", ["m4", "m3"])
        f.offer(s)  # Explicit phase-event fixture; use the real optional/Stack protocol.
        choice_id = s.rules_engine["pendingChoice"]["id"]
        await self.send(self.ws1, {"type": "resolve_rules_choice", "choiceId": choice_id, "option": "accept"})
        targeted = await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and (m["rulesEngine"]["pendingChoice"] or {}).get("kind") == "trigger_targets")
        targets = [{"kind": "zone_card", "zone": "graveyard", "containerId": "p1", "cardId": cid} for cid in ("m2", "w2")]
        await self.send(self.ws1, {"type": "resolve_rules_choice", "choiceId": targeted["rulesEngine"]["pendingChoice"]["id"], "targets": targets})
        await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and len(m["rulesEngine"]["actionStack"]) == 1)
        self.assertEqual(s.players["p1"]["zones"]["graveyard"], ["m2", "w2"])
        first, second = (self.ws1, self.ws2) if s.rules_engine["priorityPlayerId"] == "p1" else (self.ws2, self.ws1)
        await self.pass_stack(first, second)
        ordered = await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and (m["rulesEngine"]["pendingChoice"] or {}).get("kind") == "deck_reorder")
        choice_id = ordered["rulesEngine"]["pendingChoice"]["id"]
        await self.ws1.close()
        ws, _ = await self.join({"type": "join", "code": self.code, "name": "P1", "clientId": "p1"})
        restored = await self.receive_until(ws, lambda m: m.get("type") == "state")
        self.assertEqual(restored["rulesEngine"]["pendingChoice"]["id"], choice_id)
        self.assertEqual(self.wires[ws][-1]["stateRevision"], 1)
        before = f.snapshot(s)
        await self.send(ws, {"type": "resolve_rules_choice", "choiceId": choice_id,
            "option": {"groups": [{"playerId": "p1", "top": ["w2", "m2"], "bottom": []}]}})
        await self.receive_until(ws, lambda m: m.get("type") == "error")
        self.assertEqual(f.snapshot(s), before)
        await self.send(ws, {"type": "resolve_rules_choice", "choiceId": choice_id,
            "option": {"groups": [{"playerId": "p1", "top": ["w2"], "bottom": ["m2"]}]}})
        await self.receive_until(ws, lambda m: m.get("type") == "state" and m["rulesEngine"]["pendingChoice"] is None)
        self.assertEqual(s.players["p1"]["zones"]["deck"], ["w2", "m4", "m3", "m2"])
        self.assertEqual(s.players["p1"]["zones"]["graveyard"], [])
        self.assertEqual(host["counters"]["Control"], 10)


if __name__ == "__main__":
    unittest.main()
