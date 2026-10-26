"""Two-seat protocol checks; automatic phase driving is isolated, not tested here."""
import copy
import unittest
from unittest.mock import AsyncMock, patch

import test_websocket_integration as network
import test_bounce_replay_clauses as clauses
import main


class BounceReplayIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = network.WebSocketRulesIntegrationTests.asyncSetUp
    asyncTearDown = network.WebSocketRulesIntegrationTests.asyncTearDown
    join = network.WebSocketRulesIntegrationTests.join
    receive_until = network.WebSocketRulesIntegrationTests.receive_until
    send = network.WebSocketRulesIntegrationTests.send
    prepare_active_rules = network.WebSocketRulesIntegrationTests.prepare_active_rules

    def setup_rules(self):
        self.prepare_active_rules("confrontation_reaction")
        s, f = self.session, clauses.BounceReplayClauses()
        s.phase_tracker.update(enabled=True, advanced=True, turn=2)
        s.rules_engine.update(firstManifestationComplete=True, firstManifestationTriggersQueued=True)
        s.card_rules["replay-man"] = copy.deepcopy(f.world().card_rules["replay-man"])
        s.manifestation_ids.add("replay-man")
        return f, s

    async def replay(self, ws):
        await self.send(ws, {"type": "declare_rules_action", "label": "Replay", "kind": "play_card",
            "source": {"cardId": "replay-man", "zone": "hand"}, "asSupport": True})

    async def pass_stack(self, first, second):
        first_id = self.session.rules_engine["priorityPlayerId"]
        await self.send(first, {"type": "pass_priority", "passed": True})
        ack = await self.receive_until(first, lambda m: m.get("type") == "error" or
            (m.get("type") == "state" and m["rulesEngine"]["priorityPasses"] == [first_id]))
        self.assertEqual(ack["type"], "state", ack)
        await self.send(second, {"type": "pass_priority", "passed": True})

    @patch("main.auto_advance_rules_phases", new_callable=AsyncMock, return_value=False)
    async def test_pigon_return_reconnect_rejects_stack_replay_but_next_turn_accepts(self, _driver):
        f, s = self.setup_rules()
        source = f.field(s, f.cid(f.PIGON), "pigon")
        target = f.field(s, "replay-man", "returned", owner="p2", support=True, power_bonus=2)
        s.add_rules_excess_essence("p1", [{"temperament": "hollow", "amount": 2}])
        await self.send(self.ws1, {"type": "declare_rules_action", "label": "Pigon", "kind": "activated_effect",
            "source": {"cardId": source["cardId"], "itemId": source["id"], "zone": "battlefield"},
            "abilityId": f.SINGLE[0][1], "targets": [f.target(target)]})
        queued = await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and len(m["rulesEngine"]["actionStack"]) == 1)
        self.assertTrue(any(i["id"] == "returned" for i in queued["battlefield"]))
        self.assertEqual(queued["rulesEngine"]["playRestrictions"], [])
        await self.pass_stack(self.ws2, self.ws1)
        await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and bool(m["rulesEngine"]["playRestrictions"]))
        await self.ws2.close()
        ws, _ = await self.join({"type": "join", "code": self.code, "name": "P2", "clientId": "p2"})
        restored = await self.receive_until(ws, lambda m: m.get("type") == "state")
        self.assertEqual(restored["players"]["p2"]["zones"]["hand"]["cards"], ["replay-man"])
        self.assertEqual(len(restored["rulesEngine"]["playRestrictions"]), 1)
        s.rules_engine["priorityPlayerId"] = "p2"
        before = f.snapshot(s)
        await self.replay(ws)
        await self.receive_until(ws, lambda m: m.get("type") == "error")
        self.assertEqual(f.snapshot(s), before)
        # Explicit turn fixture: this case checks expiry, not the phase scheduler.
        s.phase_tracker["turn"] += 1
        s.prune_rules_play_restrictions()
        await self.replay(ws)
        await self.receive_until(ws, lambda m: m.get("type") == "state" and len(m["rulesEngine"]["actionStack"]) == 1)
        await self.pass_stack(self.ws1, ws)
        done = await self.receive_until(ws, lambda m: m.get("type") == "state" and any(i.get("cardId") == "replay-man" for i in m["battlefield"]))
        self.assertEqual(done["rulesEngine"]["actionStack"], [])
        item = next(i for i in s.battlefield if i.get("cardId") == "replay-man")
        self.assertEqual(s.rules_manifestation_characteristics(item)["power"], 3)

    @patch("main.auto_advance_rules_phases", new_callable=AsyncMock, return_value=False)
    async def test_unrestricted_copy_can_play_without_triggering_chiff_again_or_unlocking_returned_copy(self, _driver):
        f, s = self.setup_rules()
        f.put(s, "p2", "hand", ["replay-man"])
        source = f.field(s, f.cid(f.CHIFF), "chiff", support=True)
        target = f.field(s, "replay-man", "returned", owner="p2", support=True)
        actions = s.queue_rules_support_entry_triggers(source, played=True, from_zone="hand",
            event_targets=[f.target(target)], defer=True)
        self.assertEqual(len(actions), 1)
        s.rules_engine["actionStack"] = actions
        s.rules_engine["priorityPlayerId"] = "p2"
        await self.pass_stack(self.ws2, self.ws1)
        await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and len(m["players"]["p2"]["zones"]["hand"]["cards"]) == 2)
        s.rules_engine["priorityPlayerId"] = "p2"
        await self.replay(self.ws2)
        await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and len(m["rulesEngine"]["actionStack"]) == 1)
        await self.pass_stack(self.ws1, self.ws2)
        done = await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and any(i.get("cardId") == "replay-man" for i in m["battlefield"]))
        self.assertEqual(done["rulesEngine"]["actionStack"], [])
        self.assertIsNone(done["rulesEngine"]["pendingChoice"])
        self.assertEqual(done["players"]["p2"]["zones"]["hand"]["cards"], ["replay-man"])
        s.rules_engine["priorityPlayerId"] = "p2"
        before = f.snapshot(s)
        await self.replay(self.ws2)
        await self.receive_until(self.ws2, lambda m: m.get("type") == "error")
        self.assertEqual(f.snapshot(s), before)


if __name__ == "__main__":
    unittest.main()
