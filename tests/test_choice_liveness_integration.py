"""A copied Will with no legal new target must not lock the real game."""
import unittest

import test_websocket_integration as network
import test_stack_target_integration as targets


class ChoiceLivenessIntegrationTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = network.WebSocketRulesIntegrationTests.asyncSetUp
    asyncTearDown = network.WebSocketRulesIntegrationTests.asyncTearDown
    join = network.WebSocketRulesIntegrationTests.join
    receive_until = network.WebSocketRulesIntegrationTests.receive_until
    send = network.WebSocketRulesIntegrationTests.send
    prepare_active_rules = network.WebSocketRulesIntegrationTests.prepare_active_rules
    resolve_top = targets.StackTargetIntegrationTests.resolve_top

    async def test_effect_payment_preserves_the_players_white_allocation(self):
        self.prepare_active_rules("confrontation_reaction")
        session = self.session
        session.rules_engine.update(firstManifestationComplete=True, autoSkipPhases=False)
        session.card_rules["blue-tribute"] = {"type": "manifestation", "power": 1, "temperaments": ["vitreous"]}
        session.players["p1"]["zones"]["hand"] = ["blue-tribute"]
        session.players["p2"]["zones"]["hand"] = ["inner-deserts-047"]
        session.add_rules_excess_essence("p1", [{"temperament": "transcendent", "amount": 1}])
        session.add_rules_excess_essence("p2", [{"temperament": "transcendent", "amount": 16}])
        session.rules_engine["pendingChoice"] = {"id": "white-payment", "kind": "effect_payment", "playerId": "p1",
            "payment": "{B}{R}", "sourceCardId": "q6rha5kz42bkxle_en", "controllerId": "p2", "onDecline": {}}
        await self.send(self.ws1, {"type": "resolve_rules_choice", "choiceId": "white-payment", "option": "pay",
            "cardIds": ["blue-tribute"], "transcendentPayment": {"vitreous": 1}})
        await self.receive_until(self.ws1, lambda m: m.get("type") == "error")
        self.assertEqual(session.players["p1"]["zones"]["hand"], ["blue-tribute"])
        await self.send(self.ws1, {"type": "resolve_rules_choice", "choiceId": "white-payment", "option": "pay",
            "cardIds": ["blue-tribute"], "transcendentPayment": {"choleric": 1}})
        await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and m["rulesEngine"]["pendingChoice"] is None)
        self.assertEqual(session.players["p1"]["zones"]["hand"], [])
        self.assertIn("blue-tribute", session.players["p1"]["zones"]["graveyard"])
        self.assertFalse(any(token.get("isEssence") and token["ownerId"] == "p1" for token in session.tokens))

    async def test_copy_without_friendly_manifestations_can_finish_after_reconnect_once(self):
        self.prepare_active_rules("confrontation_reaction", priority="p2")
        session = self.session
        session.rules_engine.update(firstManifestationComplete=True, autoSkipPhases=False)
        session.card_rules["target"] = {"type": "manifestation", "power": 5, "temperaments": ["choleric"]}
        session.battlefield = [{"id": "target", "cardId": "target", "ownerId": "p2", "fieldZone": "confrontation",
            "isSupport": True, "faceUp": True, "rotation": 0, "x": 600, "y": 525, "counters": {}}]
        for pid, player in session.players.items():
            player["zones"]["hand"] = ["inner-deserts-047"]
            session.add_rules_excess_essence(pid, [{"temperament": "transcendent", "amount": 16}])
        session.players["p2"]["zones"]["hand"].append("72zvsiuky5ytolh_en")
        session.players["p1"]["zones"]["hand"].append("q6rha5kz42bkxle_en")
        await self.send(self.ws2, {"type": "declare_rules_action", "label": "Mirror", "kind": "play_card",
            "source": {"zone": "hand", "cardId": "72zvsiuky5ytolh_en"}, "abilityId": "copy-friendly-manifestation-in-support",
            "targets": [{"kind": "card", "itemId": "target", "cardId": "target"}]})
        declared = await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and len(m["rulesEngine"]["actionStack"]) == 1)
        original_id = declared["rulesEngine"]["actionStack"][0]["id"]
        await self.send(self.ws1, {"type": "declare_rules_action", "label": "Imitate", "kind": "play_card",
            "source": {"zone": "hand", "cardId": "q6rha5kz42bkxle_en"},
            "abilityId": network.server_main.CARD_ABILITIES["q6rha5kz42bkxle_en"][0]["id"],
            "targets": [{"kind": "stack_action", "actionId": original_id}]})
        declared = await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and len(m["rulesEngine"]["actionStack"]) == 2)
        state = await self.resolve_top(self.ws2, self.ws1, declared["rulesEngine"]["actionStack"][-1]["id"])
        choice_id = state["rulesEngine"]["pendingChoice"]["id"]
        await self.ws1.close()
        resumed, _ = await self.join({"type": "join", "code": self.code, "clientId": "p1", "name": "P1"})
        state = await self.receive_until(resumed, lambda m: m.get("type") == "state")
        self.assertEqual(state["rulesEngine"]["pendingChoice"]["id"], choice_id)
        self.assertNotIn("_copyAction", state["rulesEngine"]["pendingChoice"])
        payload = {"type": "resolve_rules_choice", "choiceId": choice_id, "option": "keep", "targets": []}
        await self.send(resumed, payload)
        state = await self.receive_until(resumed, lambda m: m.get("type") == "state" and
            (m["rulesEngine"].get("lastResolvedAction") or {}).get("copiedFromActionId") == original_id)
        self.assertIsNone(state["rulesEngine"]["pendingChoice"])
        self.assertEqual([a["id"] for a in state["rulesEngine"]["actionStack"]], [original_id])
        self.assertEqual(state["rulesEngine"]["lastResolvedAction"]["effectResult"]["kind"], "invalid_targets")
        self.assertEqual(len(state["battlefield"]), 1)
        self.assertEqual(session.players["p1"]["zones"]["graveyard"], ["q6rha5kz42bkxle_en"])
        await self.send(resumed, payload)
        await self.receive_until(resumed, lambda m: m.get("type") == "error")
        self.assertEqual([a["id"] for a in session.rules_engine["actionStack"]], [original_id])
        logs = [entry for entry in session.log if entry.get("type") == "rules_choice_resolved" and
            (entry.get("details") or {}).get("choiceId") == choice_id]
        self.assertEqual(len(logs), 1)
