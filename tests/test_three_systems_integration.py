"""Grouped choices, alternate payments and terminal state through real messages."""
import copy
import unittest
from unittest.mock import patch

import test_websocket_integration as network
import test_stack_target_integration as targets


class ThreeSystemsIntegrationTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = network.WebSocketRulesIntegrationTests.asyncSetUp
    asyncTearDown = network.WebSocketRulesIntegrationTests.asyncTearDown
    join = network.WebSocketRulesIntegrationTests.join
    receive_until = network.WebSocketRulesIntegrationTests.receive_until
    send = network.WebSocketRulesIntegrationTests.send
    prepare_active_rules = network.WebSocketRulesIntegrationTests.prepare_active_rules
    resolve_top = targets.StackTargetIntegrationTests.resolve_top

    async def test_bro_group_context_survives_reconnect_and_wrong_roles_are_rejected(self):
        self.prepare_active_rules("confrontation_reaction")
        session = self.session
        session.rules_engine.update(firstManifestationComplete=True, autoSkipPhases=False)
        session.card_rules["target-card"] = {"type": "manifestation", "power": 3, "temperaments": ["phlegmatic"]}
        session.battlefield = [{"id": iid, "cardId": "b0amfkmb3xewx7x_en" if iid == "bro" else "target-card",
            "ownerId": "p2" if iid == "foe" else "p1", "fieldZone": "confrontation", "faceUp": True,
            "x": 600, "y": 525 if iid == "foe" else 800, "rotation": 0, "counters": {}}
            for iid in ("bro", "mine", "foe")]
        for pid, player in session.players.items():
            player["zones"]["hand"] = ["inner-deserts-047"]
            session.add_rules_excess_essence(pid, [{"temperament": "transcendent", "amount": 8}])
        session.queue_rules_field_zone_entry_triggers(session.battlefield[0], "confrontation")
        await self.ws1.close()
        resumed, _ = await self.join({"type": "join", "code": self.code, "clientId": "p1", "name": "P1"})
        state = await self.receive_until(resumed, lambda m: m.get("type") == "state")
        choice = state["rulesEngine"]["pendingChoice"]
        self.assertEqual(choice["sourceItemId"], "bro")
        self.assertEqual(choice["eventItemId"], "bro")
        self.assertEqual(len(choice["targetRules"]["groups"]), 2)
        self.assertNotIn("_triggerAction", choice)
        before = copy.deepcopy(session.rules_engine)
        await self.send(resumed, {"type": "resolve_rules_choice", "choiceId": choice["id"],
            "targets": [{"kind": "card", "itemId": "foe"}, {"kind": "card", "itemId": "mine"}]})
        await self.receive_until(resumed, lambda m: m.get("type") == "error")
        self.assertEqual(session.rules_engine, before)
        await self.send(resumed, {"type": "resolve_rules_choice", "choiceId": choice["id"],
            "targets": [{"kind": "card", "itemId": "mine"}, {"kind": "card", "itemId": "foe"}]})
        state = await self.receive_until(resumed, lambda m: m.get("type") == "state" and bool(m["rulesEngine"]["actionStack"]))
        action_id = state["rulesEngine"]["actionStack"][-1]["id"]
        with patch("game.effects.dice.random.randint", return_value=1):
            state = await self.resolve_top(self.ws2, resumed, action_id)
        self.assertEqual([item["id"] for item in state["battlefield"]], ["bro"])

    async def test_bullyboo_allows_a_real_vessel_payment_with_an_empty_hand(self):
        self.prepare_active_rules("confrontation_reaction")
        session = self.session
        session.rules_engine.update(firstManifestationComplete=True, autoSkipPhases=False)
        session.card_rules["vessel-tribute"] = {"type": "manifestation", "power": 2, "temperaments": ["phlegmatic"]}
        p1, p2 = session.players["p1"], session.players["p2"]
        p1["zones"]["hand"] = ["q6rha5kz42bkxle_en"]
        p2["zones"]["hand"] = []
        p2["zones"]["receptacle"] = ["vessel-tribute"]
        p2["zoneOwners"]["receptacle"] = {"vessel-tribute": "p1"}
        session.battlefield = [{"id": "brabataba", "cardId": "zhzp6kenpqrym9h_en", "ownerId": "p2",
            "fieldZone": "field", "faceUp": True, "rotation": 0, "x": 600, "y": 525, "counters": {}}]
        session.apply_rules_action_result({"id": "bullyboo", "controllerId": "p1", "optionalAccepted": True,
            "source": {"cardId": "gz2zjrxqc2rbcwq_en"},
            "ability": network.server_main.CARD_ABILITIES["gz2zjrxqc2rbcwq_en"][0]})
        choice_id = session.rules_engine["pendingChoice"]["id"]
        await self.send(self.ws1, {"type": "resolve_rules_choice", "choiceId": choice_id, "cardIds": ["q6rha5kz42bkxle_en"]})
        state = await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and
            (m["rulesEngine"].get("pendingChoice") or {}).get("kind") == "immediate_effect_payment")
        self.assertTrue(state["rulesEngine"]["pendingChoice"]["mustPay"])
        await self.send(self.ws2, {"type": "resolve_rules_choice", "choiceId": state["rulesEngine"]["pendingChoice"]["id"],
            "option": "pay", "cardIds": ["receptacle|vessel-tribute"]})
        await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and m["rulesEngine"]["pendingChoice"] is None)
        self.assertEqual(p2["zones"]["receptacle"], [])
        self.assertEqual(p2["score"], 0)
        self.assertIn("vessel-tribute", p1["zones"]["exile"])
        self.assertIn("q6rha5kz42bkxle_en", p1["zones"]["hand"])

    async def test_recovery_result_cancels_deferred_work_and_rejects_late_messages(self):
        self.prepare_active_rules("recovery_draw")
        session = self.session
        session.phase_tracker["turn"] = 2
        session.rules_engine["firstManifestationComplete"] = True
        for player in session.players.values():
            player["zones"]["hand"] = []
            player["zones"]["deck"] = []
        session.rules_engine["pendingChoice"] = {"id": "recovery", "kind": "binary_choice", "purpose": "quasimillenary",
            "playerId": "p1", "options": ["yes", "no"], "handLimit": 7}
        session.rules_engine["deferredSimultaneousActions"] = [{"id": "late", "controllerId": "p1", "optional": True,
            "source": {}, "ability": {"id": "late", "result": {"kind": "score_owner", "value": 50}}}]
        await self.send(self.ws1, {"type": "resolve_rules_choice", "choiceId": "recovery", "option": "no"})
        state = await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and m.get("ended"))
        self.assertIsNone(state["rulesEngine"]["pendingChoice"])
        self.assertIsNone(state["rulesEngine"]["priorityPlayerId"])
        before = copy.deepcopy((session.players, session.rules_engine))
        await self.send(self.ws2, {"type": "pass_priority"})
        await self.receive_until(self.ws2, lambda m: m.get("type") == "error")
        await self.send(self.ws1, {"type": "resolve_rules_choice", "choiceId": "recovery", "option": "no"})
        await self.receive_until(self.ws1, lambda m: m.get("type") == "error")
        self.assertEqual((session.players, session.rules_engine), before)
        await self.ws1.close()
        resumed, _ = await self.join({"type": "join", "code": self.code, "clientId": "p1", "name": "P1"})
        state = await self.receive_until(resumed, lambda m: m.get("type") == "state")
        self.assertTrue(state["ended"])
        self.assertIsNone(state["rulesEngine"]["pendingChoice"])
