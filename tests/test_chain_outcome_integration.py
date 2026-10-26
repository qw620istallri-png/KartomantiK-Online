"""Two real WebSocket seats: private Chain choices, reconnect and replay safety.

Automatic phase driving is held to isolate transport and exact effect outcomes;
the separate latency sequence tests cover the automatic driver.
"""
import copy
import unittest
from unittest.mock import AsyncMock, patch

import test_websocket_integration as network
import test_chain_outcome_clause_audit as clauses
import main


class ChainOutcomeIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = network.WebSocketRulesIntegrationTests.asyncSetUp
    asyncTearDown = network.WebSocketRulesIntegrationTests.asyncTearDown
    join = network.WebSocketRulesIntegrationTests.join
    receive_until = network.WebSocketRulesIntegrationTests.receive_until
    send = network.WebSocketRulesIntegrationTests.send
    prepare_active_rules = network.WebSocketRulesIntegrationTests.prepare_active_rules

    def setup_choice(self, name, zone):
        self.prepare_active_rules("confrontation_reaction")
        s = self.session
        s.phase_tracker.update(enabled=True, advanced=True, turn=2)
        s.rules_engine.update(firstManifestationComplete=True, firstManifestationTriggersQueued=True)
        for p in s.players.values():
            p["score"] = 50
        fixture = clauses.ChainOutcomeClauseAudit()
        sprout = fixture.cid("Wind Sprout")
        will = fixture.cid("Weaken")
        s.put_zone_card("p1", zone, sprout, "p2" if name == fixture.URO else "p1")
        s.put_zone_card("p1", zone, will, "p1")
        fixture.begin(s, name)
        self.assertEqual(s.rules_engine["pendingChoice"]["kind"], "chain_manifestation")
        return fixture, sprout, will

    @patch("main.auto_advance_rules_phases", new_callable=AsyncMock, return_value=False)
    async def test_urocione_reconnect_keeps_private_choice_and_foreign_owner_victory_destination(self, _driver):
        fixture, sprout, _will = self.setup_choice("Urocione, the Anarchist", "hand")
        s = self.session
        choice_id = s.rules_engine["pendingChoice"]["id"]
        await main.broadcast_state(s)
        other = await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and (m["rulesEngine"]["pendingChoice"] or {}).get("id") == choice_id)
        self.assertNotIn("cardIds", other["rulesEngine"]["pendingChoice"])
        self.assertNotIn("_cardIds", other["rulesEngine"]["pendingChoice"])
        before = copy.deepcopy((s.players, s.battlefield))
        await self.send(self.ws2, {"type": "resolve_rules_choice", "choiceId": choice_id, "cardIds": [sprout]})
        await self.receive_until(self.ws2, lambda m: m.get("type") == "error")
        self.assertEqual((s.players, s.battlefield), before)
        await self.ws1.close()
        reconnected, _ = await self.join({"type": "join", "code": self.code, "name": "P1", "clientId": "p1"})
        restored = await self.receive_until(reconnected, lambda m: m.get("type") == "state")
        self.assertEqual(restored["rulesEngine"]["pendingChoice"]["id"], choice_id)
        await self.send(reconnected, {"type": "resolve_rules_choice", "choiceId": choice_id, "cardIds": [sprout]})
        await self.receive_until(reconnected, lambda m: m.get("type") == "state" and m["rulesEngine"]["pendingChoice"] is None)
        chained = [i for i in s.battlefield if i.get("isChained")]
        self.assertEqual(len(chained), 1)
        self.assertEqual((chained[0]["ownerId"], chained[0]["controllerId"]), ("p2", "p1"))
        fixture.outcome(s)
        s.begin_rules_confrontation_cleanup()
        await main.broadcast_state(s)
        visible = await self.receive_until(reconnected, lambda m: m.get("type") == "state" and sprout in m["players"]["p1"]["zones"]["receptacle"]["cards"])
        self.assertIn(sprout, visible["players"]["p1"]["zones"]["receptacle"]["cards"])
        self.assertEqual(s.card_owner_in_zone("p1", "receptacle", sprout), "p2")

    @patch("main.auto_advance_rules_phases", new_callable=AsyncMock, return_value=False)
    async def test_lady_rejected_choice_retry_and_replay_shuffle_exactly_once(self, _driver):
        fixture, sprout, will = self.setup_choice("Lady of the Humps", "deck")
        s = self.session
        choice_id = s.rules_engine["pendingChoice"]["id"]
        with patch("game.chain.random.shuffle") as shuffle:
            before = copy.deepcopy((s.players, s.battlefield))
            await self.send(self.ws1, {"type": "resolve_rules_choice", "choiceId": choice_id, "cardIds": [will]})
            await self.receive_until(self.ws1, lambda m: m.get("type") == "error")
            self.assertEqual((s.players, s.battlefield), before)
            self.assertEqual(shuffle.call_count, 0)
            valid = {"type": "resolve_rules_choice", "choiceId": choice_id, "cardIds": [sprout]}
            await self.send(self.ws1, valid)
            await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and m["rulesEngine"]["pendingChoice"] is None)
            self.assertEqual(shuffle.call_count, 1)
            after = copy.deepcopy((s.players, s.battlefield))
            await self.send(self.ws1, valid)
            await self.receive_until(self.ws1, lambda m: m.get("type") == "error")
            self.assertEqual(shuffle.call_count, 1)
            self.assertEqual((s.players, s.battlefield), after)
        self.assertEqual(s.players["p1"]["zones"]["deck"], [will])
        self.assertEqual(len([i for i in s.battlefield if i.get("cardId") == sprout]), 1)


if __name__ == "__main__":
    unittest.main()
