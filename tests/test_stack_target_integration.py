"""A real response protects one Multicastigate target without saving the other."""
import unittest

import test_websocket_integration as network


class StackTargetIntegrationTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = network.WebSocketRulesIntegrationTests.asyncSetUp
    asyncTearDown = network.WebSocketRulesIntegrationTests.asyncTearDown
    join = network.WebSocketRulesIntegrationTests.join
    receive_until = network.WebSocketRulesIntegrationTests.receive_until
    send = network.WebSocketRulesIntegrationTests.send
    prepare_active_rules = network.WebSocketRulesIntegrationTests.prepare_active_rules

    async def resolve_top(self, first, second, action_id):
        priority = self.session.rules_engine["priorityPlayerId"]
        await self.send(first, {"type": "pass_priority"})
        await self.receive_until(first, lambda m: m.get("type") == "state" and
            m["rulesEngine"]["priorityPasses"] == [priority])
        await self.send(second, {"type": "pass_priority"})
        return await self.receive_until(second, lambda m: m.get("type") == "state" and
            (m["rulesEngine"].get("lastResolvedAction") or {}).get("id") == action_id)

    async def test_wall_off_response_leaves_other_multicastigate_target_destroyed(self):
        self.prepare_active_rules("confrontation_reaction")
        session = self.session
        session.rules_engine.update(firstManifestationComplete=True, autoSkipPhases=False)
        for index in (0, 1):
            session.card_rules[f"support-{index}"] = {"type": "manifestation", "power": 5, "temperaments": ["choleric"]}
        session.battlefield = [
            {"id": f"support-{index}", "cardId": f"support-{index}", "ownerId": "p2",
             "fieldZone": "confrontation", "isSupport": True, "faceUp": True,
             "rotation": 0, "x": 600 + index * 100, "y": 525, "counters": {}}
            for index in (0, 1)
        ]
        for pid, player in session.players.items():
            player["zones"]["hand"] = ["inner-deserts-047"]
            session.add_rules_excess_essence(pid, [{"temperament": "transcendent", "amount": 16}])
        session.players["p1"]["zones"]["hand"].append("inner-deserts-138")
        session.players["p2"]["zones"]["hand"].append("inner-deserts-146")
        await self.send(self.ws1, {"type": "declare_rules_action", "label": "Multicastigate", "kind": "play_card",
            "source": {"zone": "hand", "cardId": "inner-deserts-138"},
            "abilityId": "destroy-one-or-two-support-manifestations",
            "targets": [{"kind": "card", "itemId": f"support-{index}", "cardId": f"support-{index}"} for index in (0, 1)]})
        declared = await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and len(m["rulesEngine"]["actionStack"]) == 1)
        original_id = declared["rulesEngine"]["actionStack"][0]["id"]
        await self.send(self.ws2, {"type": "declare_rules_action", "label": "Wall off", "kind": "play_card",
            "source": {"zone": "hand", "cardId": "inner-deserts-146"},
            "abilityId": "protect-field-card-until-end-turn",
            "targets": [{"kind": "card", "itemId": "support-0", "cardId": "support-0"}]})
        declared = await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and len(m["rulesEngine"]["actionStack"]) == 2)
        wall_id = declared["rulesEngine"]["actionStack"][-1]["id"]
        state = await self.resolve_top(self.ws1, self.ws2, wall_id)
        self.assertEqual(len(state["rulesEngine"]["actionStack"]), 1)
        self.assertEqual({item["id"] for item in state["battlefield"]}, {"support-0", "support-1"})
        p1_essence_before = sum(t.get("counters", {}).get("essence", 0) for t in session.tokens if t.get("isEssence") and t["ownerId"] == "p1")
        state = await self.resolve_top(self.ws2, self.ws1, original_id)
        self.assertEqual({item["id"] for item in state["battlefield"]}, {"support-0"})
        self.assertIn("support-1", session.players["p2"]["zones"]["graveyard"])
        self.assertIn("inner-deserts-138", session.players["p1"]["zones"]["graveyard"])
        self.assertEqual(state["rulesEngine"]["lastResolvedAction"]["invalidTargetIndices"], [0])
        self.assertEqual(p1_essence_before, sum(t.get("counters", {}).get("essence", 0) for t in session.tokens if t.get("isEssence") and t["ownerId"] == "p1"))
