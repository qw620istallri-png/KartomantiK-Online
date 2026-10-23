"""Expiry replacement choices resume through the WebSocket handler exactly once."""
import unittest

import test_websocket_integration as network


class ModifierOrderIntegrationTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = network.WebSocketRulesIntegrationTests.asyncSetUp
    asyncTearDown = network.WebSocketRulesIntegrationTests.asyncTearDown
    join = network.WebSocketRulesIntegrationTests.join
    receive_until = network.WebSocketRulesIntegrationTests.receive_until
    send = network.WebSocketRulesIntegrationTests.send
    prepare_active_rules = network.WebSocketRulesIntegrationTests.prepare_active_rules

    async def test_expiry_choice_reconnect_and_replay_advances_and_logs_once(self):
        self.prepare_active_rules("end_expire")
        session = self.session
        session.rules_engine["firstManifestationComplete"] = True
        session.card_rules["expiry-target"] = {"type": "manifestation", "power": 3, "temperaments": ["capricious"]}
        session.battlefield = [{"id": "target", "cardId": "expiry-target", "ownerId": "p1",
                                "fieldZone": "interzone", "faceUp": True, "counters": {"power": -3},
                                "x": 700, "y": 800, "rotation": 0}]
        for item_id in ("bob-a", "bob-b"):
            session.battlefield.append({"id": item_id, "cardId": "inner-deserts-134", "ownerId": "p2",
                                        "fieldZone": "confrontation", "faceUp": True, "counters": {"power": 3},
                                        "isCopy": True, "isTokenCopy": True, "x": 700, "y": 525, "rotation": 0})
        for player in session.players.values():
            player["zones"]["hand"] = ["inner-deserts-047"] * 7
        turn = session.phase_tracker["turn"]
        session.rules_engine["ongoingEffects"] = [{"id": "expiring", "kind": "power_modifier", "value": 1,
            "duration": "until_end_of_turn", "startedTurn": turn, "target": {"kind": "card", "itemId": "target"}}]
        await self.send(self.ws1, {"type": "pass_priority"})
        await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and m["rulesEngine"]["priorityPasses"] == ["p1"])
        await self.send(self.ws2, {"type": "pass_priority"})
        state = await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and bool(m["rulesEngine"]["pendingChoice"]))
        choice = state["rulesEngine"]["pendingChoice"]
        self.assertEqual(choice["kind"], "replacement_order")
        self.assertEqual(session.phase_tracker["turn"], turn)
        self.assertIsNotNone(session.find_battlefield_item("target"))
        await self.ws2.close()
        resumed, _ = await self.join({"type": "join", "code": self.code, "clientId": "p2", "name": "P2"})
        restored = await self.receive_until(resumed, lambda m: m.get("type") == "state")
        self.assertEqual(restored["rulesEngine"]["pendingChoice"]["id"], choice["id"])
        payload = {"type": "resolve_rules_choice", "choiceId": choice["id"],
                   "cardIds": [entry["actionId"] for entry in choice["actions"]]}
        await self.send(resumed, payload)
        await self.send(resumed, payload)
        await self.receive_until(resumed, lambda m: m.get("type") == "state" and (m["rulesEngine"]["pendingChoice"] or {}).get("kind") == "simultaneous_stack_order")
        await self.receive_until(resumed, lambda m: m.get("type") == "error")
        self.assertEqual(session.phase_tracker["turn"], turn + 1)
        self.assertEqual(session.current_phase_id(), "recovery_start")
        self.assertIsNone(session.find_battlefield_item("target"))
        self.assertEqual(len(session.rules_engine["suspendedCards"]), 1)
        logs = [entry for entry in session.log if entry["type"] == "rules_phase_advanced"]
        self.assertEqual(len(logs), 1)
        self.assertTrue(logs[0]["details"]["stateActions"]["destroyed"])
