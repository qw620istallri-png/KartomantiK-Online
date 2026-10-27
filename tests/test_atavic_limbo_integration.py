"""Real mixed-protocol seats: one opponent Limbo, controller's choice, owner's Deck."""
import unittest
from unittest.mock import AsyncMock, patch
import test_atavic_end_integration as previous

main = previous.main


class AtavicLimboIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = previous.AtavicEndIntegration.asyncSetUp
    asyncTearDown = previous.AtavicEndIntegration.asyncTearDown
    join = previous.AtavicEndIntegration.join
    receive_until = previous.AtavicEndIntegration.receive_until
    send = previous.AtavicEndIntegration.send
    prepare_active_rules = previous.AtavicEndIntegration.prepare_active_rules
    pass_stack = previous.AtavicEndIntegration.pass_stack
    setup_rules = previous.AtavicEndIntegration.setup_rules

    @patch("main.auto_advance_rules_phases", new_callable=AsyncMock, return_value=False)
    async def test_opponent_limbo_reconnect_and_owner_deck_with_mixed_targets_rejected(self, _driver):
        f, s = self.setup_rules()
        f.host(s, f.INTROSPECTION, "Control")
        f.put(s, "p1", "graveyard", ["m2"])
        f.put(s, "p2", "graveyard", ["w2", "pw3"])
        f.put(s, "p1", "deck", ["m4"])
        f.put(s, "p2", "deck", ["m3"])
        f.offer(s)
        initial = s.rules_engine["pendingChoice"]
        self.assertIsNotNone(initial)
        await main.broadcast_state(s)
        await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and (m["rulesEngine"]["pendingChoice"] or {}).get("id") == initial["id"])
        await self.send(self.ws1, {"type": "resolve_rules_choice", "choiceId": initial["id"], "option": "accept"})
        targeted = await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and (m["rulesEngine"]["pendingChoice"] or {}).get("kind") == "trigger_targets")
        choice_id = targeted["rulesEngine"]["pendingChoice"]["id"]
        ref = lambda pid, cid: {"kind": "zone_card", "containerId": pid, "zone": "graveyard", "cardId": cid}
        before = f.snapshot(s)
        await self.send(self.ws1, {"type": "resolve_rules_choice", "choiceId": choice_id,
            "targets": [ref("p1", "m2"), ref("p2", "w2")]})
        await self.receive_until(self.ws1, lambda m: m.get("type") == "error")
        self.assertEqual(f.snapshot(s), before)
        await self.send(self.ws1, {"type": "resolve_rules_choice", "choiceId": choice_id,
            "targets": [ref("p2", "w2"), ref("p2", "pw3")]})
        await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and len(m["rulesEngine"]["actionStack"]) == 1)
        self.assertEqual(s.players["p2"]["zones"]["graveyard"], ["w2", "pw3"])
        first, second = (self.ws1, self.ws2) if s.rules_engine["priorityPlayerId"] == "p1" else (self.ws2, self.ws1)
        await self.pass_stack(first, second)
        ordered = await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and (m["rulesEngine"]["pendingChoice"] or {}).get("kind") == "deck_reorder")
        choice_id = ordered["rulesEngine"]["pendingChoice"]["id"]
        self.assertEqual(ordered["rulesEngine"]["pendingChoice"]["playerId"], "p1")
        self.assertEqual(ordered["rulesEngine"]["pendingChoice"]["groups"][0]["playerId"], "p2")
        await self.ws1.close()
        ws, _ = await self.join({"type": "join", "code": self.code, "name": "P1", "clientId": "p1"})
        restored = await self.receive_until(ws, lambda m: m.get("type") == "state")
        self.assertEqual(restored["rulesEngine"]["pendingChoice"]["id"], choice_id)
        before = f.snapshot(s)
        answer = {"type": "resolve_rules_choice", "choiceId": choice_id,
                  "option": {"groups": [{"playerId": "p2", "top": ["pw3"], "bottom": ["w2"]}]}}
        await self.send(self.ws2, answer)
        await self.receive_until(self.ws2, lambda m: m.get("type") == "error")
        self.assertEqual(f.snapshot(s), before)
        await self.send(ws, answer)
        done = await self.receive_until(ws, lambda m: m.get("type") == "state" and m["rulesEngine"]["pendingChoice"] is None)
        self.assertEqual(s.players["p2"]["zones"]["deck"], ["pw3", "m3", "w2"])
        self.assertEqual(s.players["p1"]["zones"]["deck"], ["m4"])
        self.assertEqual(s.players["p1"]["zones"]["graveyard"], ["m2"])
        self.assertEqual(s.players["p2"]["zones"]["graveyard"], [])
        self.assertTrue(all(s.card_owner_in_zone("p2", "deck", cid) == "p2" for cid in ("w2", "pw3")))
        self.assertNotIn("cards", done["players"]["p2"]["zones"]["deck"])
        before = f.snapshot(s)
        await self.send(ws, answer)
        await self.receive_until(ws, lambda m: m.get("type") == "error")
        self.assertEqual(f.snapshot(s), before)


if __name__ == "__main__":
    unittest.main()
