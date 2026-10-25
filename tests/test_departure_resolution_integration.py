"""Source departure and restored memories through real two-player sockets."""
import copy
import unittest

import test_websocket_integration as network
import test_stack_target_integration as target_network
import main as server_main


class DepartureResolutionIntegrationTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = network.WebSocketRulesIntegrationTests.asyncSetUp
    asyncTearDown = network.WebSocketRulesIntegrationTests.asyncTearDown
    join = network.WebSocketRulesIntegrationTests.join
    receive_until = network.WebSocketRulesIntegrationTests.receive_until
    send = network.WebSocketRulesIntegrationTests.send
    prepare_active_rules = network.WebSocketRulesIntegrationTests.prepare_active_rules
    resolve_top = target_network.StackTargetIntegrationTests.resolve_top

    def active(self):
        self.prepare_active_rules("confrontation_reaction")
        session = self.session
        session.rules_engine.update(firstManifestationComplete=True, autoSkipPhases=False)
        for pid, player in session.players.items():
            player["zones"]["hand"] = ["inner-deserts-047"]
            player["zoneOwners"]["hand"] = {"inner-deserts-047": pid}
            session.add_rules_excess_essence(pid, [{"temperament": "transcendent", "amount": 20}])

    async def test_exile_response_then_reconnect_preserves_the_queued_activation(self):
        self.active()
        session = self.session
        bolba, exile = "pgvrly9397pua77_en", "1q6crbc7nwugrgs_en"
        session.card_rules["departure-foe"] = {"type": "manifestation", "power": 8, "temperaments": ["phlegmatic"]}
        session.battlefield = [
            {"id": "bolba", "cardId": bolba, "ownerId": "p1", "faceUp": True,
             "fieldZone": "interzone", "counters": {}, "rotation": 0, "x": 0, "y": 0},
            {"id": "foe", "cardId": "departure-foe", "ownerId": "p2", "faceUp": True,
             "fieldZone": "confrontation", "counters": {}, "rotation": 0, "x": 0, "y": 0},
        ]
        session.put_zone_card("p2", "hand", exile, "p2")
        await self.send(self.ws1, {"type": "declare_rules_action", "kind": "activated_effect", "label": "Bolbakazim",
            "source": {"zone": "battlefield", "itemId": "bolba", "cardId": bolba},
            "abilityId": "reduce-manifestation-power", "targets": [{"kind": "card", "itemId": "foe"}]})
        state = await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and len(m["rulesEngine"]["actionStack"]) == 1)
        ability_id = state["rulesEngine"]["actionStack"][0]["id"]
        await self.send(self.ws2, {"type": "declare_rules_action", "kind": "play_card", "label": "Exile",
            "source": {"zone": "hand", "cardId": exile}, "abilityId": "exile-manifestation",
            "targets": [{"kind": "card", "itemId": "bolba"}]})
        state = await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and len(m["rulesEngine"]["actionStack"]) == 2)
        exile_id = state["rulesEngine"]["actionStack"][-1]["id"]
        await self.resolve_top(self.ws1, self.ws2, exile_id)
        self.assertIsNone(session.find_battlefield_item("bolba"))
        self.assertIn(bolba, session.players["p1"]["zones"]["exile"])
        await self.ws1.close()
        resumed, _ = await self.join({"type": "join", "code": self.code, "clientId": "p1", "name": "P1"})
        state = await self.receive_until(resumed, lambda m: m.get("type") == "state")
        self.assertEqual(state["rulesEngine"]["actionStack"][0]["id"], ability_id)
        state = await self.resolve_top(self.ws2, resumed, ability_id)
        foe = next(item for item in state["battlefield"] if item["id"] == "foe")
        self.assertEqual(foe["effectivePower"], 6)
        peer = await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and
            (m["rulesEngine"].get("lastResolvedAction") or {}).get("id") == ability_id)
        self.assertEqual(next(i["effectivePower"] for i in peer["battlefield"] if i["id"] == "foe"), 6)

    async def test_restored_chain_memory_keeps_its_controller_through_reconnect(self):
        self.active()
        session = self.session
        grant, cid = "inner-deserts-012", "departure-chained"
        session.card_rules[cid] = {"type": "manifestation", "power": 4, "temperaments": ["phlegmatic"]}
        session.put_zone_card("p2", "receptacle", cid, "p1")
        error, first = session.chain_rules_manifestation("p2", "receptacle", cid, container_id="p2",
            source_card_id=grant, chain_controller_id="p2",
            chain_abilities=copy.deepcopy(server_main.CARD_ABILITIES[grant][0]["result"]["chainAbilities"]))
        self.assertIsNone(error)
        session._rules_remove_field_item_by_effect(session.find_battlefield_item(first["itemId"]), "p1", "hand")
        error, returned = session.chain_rules_manifestation("p1", "hand", cid)
        self.assertIsNone(error)
        item = session.find_battlefield_item(returned["itemId"])
        queued = session.queue_rules_chain_outcome_triggers(item, "wins_confrontation", "p1")
        self.assertEqual(len(queued), 1)
        session.rules_engine["actionStack"] = queued
        session.rules_engine["priorityPlayerId"] = "p1"
        await self.ws2.close()
        resumed, _ = await self.join({"type": "join", "code": self.code, "clientId": "p2", "name": "P2"})
        state = await self.receive_until(resumed, lambda m: m.get("type") == "state")
        self.assertEqual(state["rulesEngine"]["actionStack"][0]["controllerId"], "p2")
        state = await self.resolve_top(self.ws1, resumed, queued[0]["id"])
        self.assertEqual(state["players"]["p1"]["score"], 0)
        self.assertEqual(state["players"]["p2"]["score"], 20)

    async def test_reentered_limbo_card_does_not_revive_a_recover_target_after_reconnect(self):
        self.active()
        session = self.session
        recover, cid = "0coh7nrbvcvan1i_en", "departure-limbo"
        session.card_rules[cid] = {"type": "manifestation", "power": 4, "temperaments": ["phlegmatic"]}
        session.put_zone_card("p1", "graveyard", cid, "p1")
        session.put_zone_card("p1", "hand", recover, "p1")
        await self.send(self.ws1, {"type": "declare_rules_action", "kind": "play_card", "label": "Recover",
            "source": {"zone": "hand", "cardId": recover}, "abilityId": "return-limbo-card-to-hand",
            "targets": [{"kind": "zone_card", "containerId": "p1", "zone": "graveyard", "cardId": cid}]})
        state = await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and len(m["rulesEngine"]["actionStack"]) == 1)
        action_id = state["rulesEngine"]["actionStack"][0]["id"]
        await self.ws2.close()
        resumed, _ = await self.join({"type": "join", "code": self.code, "clientId": "p2", "name": "P2"})
        await self.receive_until(resumed, lambda m: m.get("type") == "state" and len(m["rulesEngine"]["actionStack"]) == 1)
        # Fixture represents an intervening effect that leaves then reenters Limbo.
        for source, destination in (("graveyard", "hand"), ("hand", "graveyard")):
            error, _, _ = session.move_zone_card_by_effect("p1", source, "p1", destination, cid)
            self.assertIsNone(error)
        await self.send(resumed, {"type": "pass_priority"})
        for ws in (self.ws1, resumed):
            state = await self.receive_until(ws, lambda m: m.get("type") == "state" and
                (m["rulesEngine"].get("lastResolvedAction") or {}).get("id") == action_id)
            self.assertEqual(state["rulesEngine"]["lastResolvedAction"]["effectResult"]["kind"], "invalid_targets")
            self.assertFalse(state["rulesEngine"]["actionStack"])
        self.assertIn(cid, session.players["p1"]["zones"]["graveyard"])
        self.assertNotIn(cid, session.players["p1"]["zones"]["hand"])
