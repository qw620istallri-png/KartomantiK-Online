"""Real two-seat protocol: public search cards and pre-Stack name costs.

Automatic phase driving is held to isolate choices/transport, not certified here.
"""
import copy
import unittest
from unittest.mock import AsyncMock, patch

import test_websocket_integration as network
import test_deck_search_clause_audit as clauses
import main


class DeckSearchIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = network.WebSocketRulesIntegrationTests.asyncSetUp
    asyncTearDown = network.WebSocketRulesIntegrationTests.asyncTearDown
    join = network.WebSocketRulesIntegrationTests.join
    receive_until = network.WebSocketRulesIntegrationTests.receive_until
    send = network.WebSocketRulesIntegrationTests.send
    prepare_active_rules = network.WebSocketRulesIntegrationTests.prepare_active_rules

    def setup_rules(self):
        self.prepare_active_rules("confrontation_reaction")
        self.session.phase_tracker.update(enabled=True, advanced=True, turn=2)
        self.session.rules_engine.update(firstManifestationComplete=True, firstManifestationTriggersQueued=True)
        return clauses.DeckSearchClauses(), self.session

    @patch("main.auto_advance_rules_phases", new_callable=AsyncMock, return_value=False)
    async def test_hermeto_reconnect_keeps_search_private_then_reveals_selected_card_to_peer(self, _driver):
        f, s = self.setup_rules()
        chosen, hidden = f.cid("Wind Sprout"), f.cid("Weaken")
        f.put(s, "p1", "deck", [chosen, hidden])
        f.search(s, f.HERMETO)
        choice_id = s.rules_engine["pendingChoice"]["id"]
        await main.broadcast_state(s)
        other = await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and (m["rulesEngine"]["pendingChoice"] or {}).get("id") == choice_id)
        self.assertNotIn("candidateCardIds", other["rulesEngine"]["pendingChoice"])
        await self.ws1.close()
        ws, _ = await self.join({"type": "join", "code": self.code, "name": "P1", "clientId": "p1"})
        restored = await self.receive_until(ws, lambda m: m.get("type") == "state")
        self.assertEqual(restored["rulesEngine"]["pendingChoice"]["id"], choice_id)
        await self.send(ws, {"type": "resolve_rules_choice", "choiceId": choice_id, "cardIds": [chosen]})
        other = await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and m["rulesEngine"]["pendingChoice"] is None)
        self.assertEqual(other["players"]["p1"]["zones"]["hand"]["revealed"], [{"index": 0, "cardId": chosen}])
        self.assertNotIn("cards", other["players"]["p1"]["zones"]["deck"])
        result = next(e["details"] for e in other["recentLog"] if e["type"] == "rules_choice_resolved" and e["details"].get("kind") == "search_deck")
        self.assertEqual(result["cardIds"], [chosen])
        self.assertNotIn(hidden, result["cardIds"])

    @patch("main.auto_advance_rules_phases", new_callable=AsyncMock, return_value=False)
    async def test_mejik_protocol_commits_name_before_peer_can_react_and_resolves_without_second_choice(self, _driver):
        f, s = self.setup_rules()
        card = f.cid("Wind Sprout")
        f.put(s, "p2", "deck", [card])
        source = f.field(s, f.cid(f.MEJIK), "mejik", zone="interzone")
        await self.send(self.ws1, {"type": "declare_rules_action", "label": "Mejik", "kind": "activated_effect",
            "source": {"cardId": source["cardId"], "itemId": source["id"], "zone": "battlefield"},
            "abilityId": "mejik-declare-and-discard", "targets": [{"kind": "player", "playerId": "p2"}]})
        own = await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and (m["rulesEngine"]["pendingChoice"] or {}).get("declarationCost"))
        choice_id = own["rulesEngine"]["pendingChoice"]["id"]
        self.assertEqual(own["rulesEngine"]["actionStack"], [])
        before = copy.deepcopy((s.rules_engine, s.battlefield, s.players))
        await self.send(self.ws2, {"type": "resolve_rules_choice", "choiceId": choice_id, "option": card})
        await self.receive_until(self.ws2, lambda m: m.get("type") == "error")
        self.assertEqual((s.rules_engine, s.battlefield, s.players), before)
        await self.send(self.ws1, {"type": "resolve_rules_choice", "choiceId": choice_id, "option": card})
        peer = await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and len(m["rulesEngine"]["actionStack"]) == 1)
        self.assertEqual(peer["rulesEngine"]["actionStack"][0]["cost"]["declaredCardId"], card)
        self.assertEqual(peer["rulesEngine"]["priorityPlayerId"], "p2")
        self.assertEqual(source["rotation"], 90)
        self.assertEqual(s.players["p2"]["zones"]["deck"], [card])
        self.assertEqual(len([e for e in peer["recentLog"] if e["type"] == "rules_action_declared"]), 1)
        for ws in (self.ws2, self.ws1):
            await self.send(ws, {"type": "pass_priority", "passed": True})
        done = await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and m["players"]["p2"]["zones"]["graveyard"]["cards"] == [card])
        self.assertIsNone(done["rulesEngine"]["pendingChoice"])
        self.assertEqual(done["rulesEngine"]["actionStack"], [])


if __name__ == "__main__":
    unittest.main()
