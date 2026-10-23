"""Cleanse and paid recapturing of a removed link through real player messages."""
import unittest

import test_websocket_integration as network


class CleanseStateIntegrationTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_cleanse_reconnect_then_paid_nectar_retarget(self):
        self.prepare_active_rules("end_actions")
        session = self.session
        session.rules_engine["firstManifestationComplete"] = True
        session.card_rules["cleanse-target"] = {"type": "manifestation", "power": 5, "temperaments": ["choleric"]}
        session.battlefield = [
            {"id": "mine", "cardId": "cleanse-target", "ownerId": "p1", "fieldZone": "confrontation",
             "faceUp": True, "rotation": 0, "x": 700, "y": 800, "counters": {"Gem": 2, "power": -1}},
            {"id": "foe", "cardId": "cleanse-target", "ownerId": "p2", "fieldZone": "confrontation",
             "faceUp": True, "rotation": 0, "x": 700, "y": 525, "counters": {}},
            {"id": "nectar", "cardId": "7gd19pmexrjlrap_en", "ownerId": "p1", "fieldZone": "field",
             "faceUp": True, "rotation": 0, "x": 600, "y": 800, "counters": {}},
        ]
        session.create_rules_ongoing_effects({"id": "old-link", "controllerId": "p1",
            "source": {"cardId": "7gd19pmexrjlrap_en", "itemId": "nectar"},
            "targets": [{"kind": "card", "itemId": "mine"}],
            "ability": network.server_main.CARD_ABILITIES["7gd19pmexrjlrap_en"][0]})
        for pid, player in session.players.items():
            player["zones"]["hand"] = ["inner-deserts-047"]
            session.add_rules_excess_essence(pid, [{"temperament": "transcendent", "amount": 8}])
        session.players["p1"]["zones"]["hand"].append("inner-deserts-145")
        await self.send(self.ws1, {"type": "declare_rules_action", "label": "Cleanse", "kind": "play_card",
            "source": {"zone": "hand", "cardId": "inner-deserts-145"},
            "abilityId": network.server_main.CARD_ABILITIES["inner-deserts-145"][0]["id"],
            "targets": [{"kind": "card", "itemId": "mine", "cardId": "cleanse-target"}]})
        declared = await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and bool(m["rulesEngine"]["actionStack"]))
        action_id = declared["rulesEngine"]["actionStack"][-1]["id"]
        state = await self.resolve_top(self.ws2, self.ws1, action_id)
        mine = next(item for item in state["battlefield"] if item["id"] == "mine")
        self.assertEqual(mine["counters"], {"Gem": 2})
        self.assertEqual(mine["effectivePower"], 5)
        self.assertEqual(state["rulesEngine"]["ongoingEffects"], [])
        await self.ws1.close()
        resumed, _ = await self.join({"type": "join", "code": self.code, "clientId": "p1", "name": "P1"})
        await self.receive_until(resumed, lambda m: m.get("type") == "state")
        if session.rules_engine["priorityPlayerId"] == "p2":
            await self.send(self.ws2, {"type": "pass_priority"})
            await self.receive_until(resumed, lambda m: m.get("type") == "state" and m["rulesEngine"]["priorityPlayerId"] == "p1")
        before = sum(t.get("counters", {}).get("essence", 0) for t in session.tokens if t.get("isEssence") and t["ownerId"] == "p1")
        await self.send(resumed, {"type": "declare_rules_action", "label": "Retarget Nectar", "kind": "activated_effect",
            "source": {"zone": "battlefield", "cardId": "7gd19pmexrjlrap_en", "itemId": "nectar"},
            "abilityId": "nectar-retarget-disable", "targets": [{"kind": "card", "itemId": "foe", "cardId": "cleanse-target"}]})
        declared = await self.receive_until(resumed, lambda m: m.get("type") == "state" and bool(m["rulesEngine"]["actionStack"]))
        self.assertEqual(session.find_battlefield_item("nectar")["rotation"], 90)
        after = sum(t.get("counters", {}).get("essence", 0) for t in session.tokens if t.get("isEssence") and t["ownerId"] == "p1")
        self.assertEqual(before - after, 1)
        state = await self.resolve_top(self.ws2, resumed, declared["rulesEngine"]["actionStack"][-1]["id"])
        self.assertEqual(len(state["rulesEngine"]["ongoingEffects"]), 1)
        self.assertEqual(state["rulesEngine"]["ongoingEffects"][0]["target"]["itemId"], "foe")
        self.assertTrue(session.rules_item_effects_active(session.find_battlefield_item("mine")))
        self.assertFalse(session.rules_item_effects_active(session.find_battlefield_item("foe")))
