"""Real WebSocket flushing must not duplicate or invent observed triggers."""
import unittest

import test_websocket_integration as network


class ObservedEventsIntegrationTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = network.WebSocketRulesIntegrationTests.asyncSetUp
    asyncTearDown = network.WebSocketRulesIntegrationTests.asyncTearDown
    join = network.WebSocketRulesIntegrationTests.join
    receive_until = network.WebSocketRulesIntegrationTests.receive_until
    send = network.WebSocketRulesIntegrationTests.send
    prepare_active_rules = network.WebSocketRulesIntegrationTests.prepare_active_rules

    def setup_effect(self, capped=False):
        self.prepare_active_rules("confrontation_reaction")
        session = self.session
        session.rules_engine["firstManifestationComplete"] = True
        # Keep a legal response for both players so automatic Stack passes do
        # not resolve Imgurd before its intermediate state can be inspected.
        for pid, player in session.players.items():
            player["zones"]["hand"] = ["inner-deserts-047"]
            session.add_rules_excess_essence(pid, [{"temperament": "transcendent", "amount": 8}])
        session.card_rules["observed-target"] = {"type": "manifestation", "power": 3, "temperaments": ["choleric"]}
        session.battlefield = [
            {"id": "target", "cardId": "observed-target", "ownerId": "p1", "fieldZone": "confrontation",
             "faceUp": True, "counters": {}, "x": 700, "y": 800, "rotation": 0},
            {"id": "imgurd", "cardId": "kae4oy2v7jtkgn2_en", "ownerId": "p1", "fieldZone": "interzone",
             "faceUp": True, "counters": {}, "x": 600, "y": 800, "rotation": 0},
        ]
        if capped:
            session.battlefield.append({"id": "berta", "cardId": "inner-deserts-009", "ownerId": "p2",
                "fieldZone": "interzone", "faceUp": True, "counters": {}, "x": 600, "y": 525, "rotation": 0})
        session.rules_engine["actionStack"] = [{"id": "observed-effect", "kind": "activated_effect",
            "label": "Observed power loss", "controllerId": "p2", "source": {"cardId": "pqi88s5ytyfnalf_en"},
            "targets": [{"kind": "card", "itemId": "target", "cardId": "observed-target"}],
            "ability": {"id": "observed-effect", "result": {"kind": "humiliate_target"}}}]

    async def resolve_top(self, first, second, action_id):
        player_id = self.session.rules_engine["priorityPlayerId"]
        await self.send(first, {"type": "pass_priority"})
        await self.receive_until(first, lambda m: m.get("type") == "state" and
            m["rulesEngine"].get("priorityPasses") == [player_id])
        await self.send(second, {"type": "pass_priority"})
        return await self.receive_until(second, lambda m: m.get("type") == "state" and
            (m["rulesEngine"].get("lastResolvedAction") or {}).get("id") == action_id)

    async def test_real_loss_triggers_once_and_survives_reconnect(self):
        self.setup_effect()
        state = await self.resolve_top(self.ws1, self.ws2, "observed-effect")
        stack = state["rulesEngine"]["actionStack"]
        self.assertEqual(len(stack), 1)
        self.assertEqual(stack[0]["ability"]["id"], "imgurd-gains-points-when-power-is-lost")
        self.assertEqual(self.session.players["p1"]["score"], -5)
        await self.ws1.close()
        resumed, _ = await self.join({"type": "join", "code": self.code, "clientId": "p1", "name": "P1"})
        restored = await self.receive_until(resumed, lambda m: m.get("type") == "state")
        self.assertEqual([a["id"] for a in restored["rulesEngine"]["actionStack"]], [stack[0]["id"]])
        self.assertEqual(self.session.queue_rules_observed_event_triggers(defer=True), [])
        priority = self.session.rules_engine["priorityPlayerId"]
        first, second = (resumed, self.ws2) if priority == "p1" else (self.ws2, resumed)
        await self.resolve_top(first, second, stack[0]["id"])
        self.assertEqual(self.session.players["p1"]["score"], 0)
        self.assertEqual(self.session.rules_engine["actionStack"], [])
        resolutions = [entry for entry in self.session.log if entry["type"] == "rules_action_resolved"
                       and entry["details"]["actionId"] == stack[0]["id"]]
        self.assertEqual(len(resolutions), 1)

    async def test_prevented_loss_never_creates_a_trigger_or_choice(self):
        self.setup_effect(capped=True)
        state = await self.resolve_top(self.ws1, self.ws2, "observed-effect")
        self.assertEqual(state["rulesEngine"]["actionStack"], [])
        self.assertIsNone(state["rulesEngine"]["pendingChoice"])
        self.assertEqual(self.session.players["p1"]["score"], -5)
        self.assertEqual(self.session.queue_rules_observed_event_triggers(defer=True), [])
