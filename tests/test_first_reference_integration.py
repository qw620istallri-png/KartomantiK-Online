"""A real Exile response, promotion, reconnect and delayed points calculation."""
import unittest

import test_departure_resolution_integration as departures


class FirstReferenceIntegrationTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = departures.DepartureResolutionIntegrationTests.asyncSetUp
    asyncTearDown = departures.DepartureResolutionIntegrationTests.asyncTearDown
    join = departures.DepartureResolutionIntegrationTests.join
    receive_until = departures.DepartureResolutionIntegrationTests.receive_until
    send = departures.DepartureResolutionIntegrationTests.send
    prepare_active_rules = departures.DepartureResolutionIntegrationTests.prepare_active_rules
    resolve_top = departures.DepartureResolutionIntegrationTests.resolve_top
    active = departures.DepartureResolutionIntegrationTests.active

    async def test_exile_promotes_next_first_and_reconnect_keeps_current_reference(self):
        self.active()
        session = self.session
        lombric, exile = "inner-deserts-014", "1q6crbc7nwugrgs_en"
        for cid, power in (("old-first", 8), ("next-first", 2)):
            session.card_rules[cid] = {"type": "manifestation", "power": power, "temperaments": ["phlegmatic"]}
        session.battlefield = [
            {"id": "winner", "cardId": lombric, "ownerId": "p1", "confrontationOrder": 1},
            {"id": "departing", "cardId": "old-first", "ownerId": "p2", "confrontationOrder": 2},
            {"id": "promoted", "cardId": "next-first", "ownerId": "p2", "confrontationOrder": 3, "isSupport": True},
        ]
        for item in session.battlefield:
            item.update(faceUp=True, fieldZone="confrontation", counters={}, rotation=0, x=500, y=300)
        session.rules_engine["firstManifestationItemIds"] = {"p1": "winner", "p2": "departing"}
        # Fixture starts after the win event; the trigger is built by the real catalog.
        queued = session.queue_rules_triggers(lombric, "p1", "wins_confrontation", item_id="winner",
            event_controller_id="p1", target_player_id="p2", defer=True)
        self.assertEqual(len(queued), 1)
        session.rules_engine["actionStack"].extend(queued)
        trigger_id = queued[0]["id"]
        session.put_zone_card("p1", "hand", exile, "p1")
        await self.send(self.ws1, {"type": "declare_rules_action", "kind": "play_card", "label": "Exile response",
            "source": {"zone": "hand", "cardId": exile}, "abilityId": "exile-manifestation",
            "targets": [{"kind": "card", "itemId": "departing"}]})
        state = await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and len(m["rulesEngine"]["actionStack"]) == 2)
        exile_id = state["rulesEngine"]["actionStack"][-1]["id"]
        state = await self.resolve_top(self.ws2, self.ws1, exile_id)
        self.assertEqual(state["rulesEngine"]["firstManifestationItemIds"]["p2"], "promoted")
        await self.ws2.close()
        resumed, _ = await self.join({"type": "join", "code": self.code, "clientId": "p2", "name": "P2"})
        state = await self.receive_until(resumed, lambda m: m.get("type") == "state" and len(m["rulesEngine"]["actionStack"]) == 1)
        self.assertEqual(state["rulesEngine"]["firstManifestationItemIds"]["p2"], "promoted")
        first, second = (self.ws1, resumed) if session.rules_engine["priorityPlayerId"] == "p1" else (resumed, self.ws1)
        state = await self.resolve_top(first, second, trigger_id)
        self.assertEqual(state["players"]["p1"]["score"], 15)  # (printed 5 - current 2) × 5
        peer = first
        state = await self.receive_until(peer, lambda m: m.get("type") == "state" and (m["rulesEngine"].get("lastResolvedAction") or {}).get("id") == trigger_id)
        self.assertEqual(state["players"]["p1"]["score"], 15)
        self.assertEqual(state["rulesEngine"]["firstManifestationItemIds"]["p2"], "promoted")
