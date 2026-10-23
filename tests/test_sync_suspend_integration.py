"""Two-viewer Suspend and Immediate Effect recovery through real sockets."""
import copy
import unittest

import test_websocket_integration as network
import main as server_main


class SyncSuspendIntegrationTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = network.WebSocketRulesIntegrationTests.asyncSetUp
    asyncTearDown = network.WebSocketRulesIntegrationTests.asyncTearDown
    join = network.WebSocketRulesIntegrationTests.join
    receive_until = network.WebSocketRulesIntegrationTests.receive_until
    send = network.WebSocketRulesIntegrationTests.send
    prepare_active_rules = network.WebSocketRulesIntegrationTests.prepare_active_rules

    def hold_priority(self):
        self.prepare_active_rules("confrontation_reaction")
        self.session.rules_engine["firstManifestationComplete"] = True
        for pid, player in self.session.players.items():
            player["zones"]["hand"] = ["inner-deserts-047"]
            player["zoneOwners"]["hand"] = {"inner-deserts-047": pid}
            self.session.add_rules_excess_essence(pid, [{"temperament": "transcendent", "amount": 8}])

    async def test_closing_an_old_socket_keeps_the_reconnected_seat_online(self):
        resumed, _ = await self.join({"type": "join", "code": self.code, "clientId": "p1", "name": "P1"})
        await self.receive_until(resumed, lambda m: m.get("type") == "state")
        await self.ws1.close()
        # Drain the close broadcast before checking presence on both live sockets.
        await self.receive_until(self.ws2, lambda m: m.get("type") == "state")
        await self.send(resumed, {"type": "chat_message", "text": "alive"})
        await self.receive_until(self.ws2, lambda m: m.get("type") == "chat_message" and m.get("text") == "alive")
        self.assertTrue(self.session.players["p1"]["connected"])
        self.assertFalse(any(e["type"] == "player_disconnected" and e.get("actorId") == "p1" for e in self.session.log))

    async def test_suspend_choice_permission_and_owner_survive_reconnect_without_leaking_candidates(self):
        self.hold_priority()
        owner = self.session.players["p2"]
        owner["zones"]["hand"] = ["inner-deserts-115", "inner-deserts-047"]
        owner["zoneOwners"]["hand"] = {cid: "p2" for cid in owner["zones"]["hand"]}
        self.session.apply_rules_action_result({"id": "gobres-effect", "controllerId": "p1", "source": {"cardId": "inner-deserts-088", "itemId": "gobres"},
            "targets": [{"kind": "player", "playerId": "p2"}], "ability": {"result": {"kind": "suspend_opponent_hand_will"}}})
        choice_id = self.session.rules_engine["pendingChoice"]["id"]
        await server_main.broadcast_state(self.session)
        first = await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and (m["rulesEngine"]["pendingChoice"] or {}).get("id") == choice_id)
        self.assertNotIn("cardIds", first["rulesEngine"]["pendingChoice"])
        await self.ws2.close()
        resumed, _ = await self.join({"type": "join", "code": self.code, "clientId": "p2", "name": "P2"})
        state = await self.receive_until(resumed, lambda m: m.get("type") == "state")
        self.assertCountEqual(state["rulesEngine"]["pendingChoice"]["cardIds"], owner["zones"]["hand"])
        payload = {"type": "resolve_rules_choice", "choiceId": choice_id, "cardIds": ["inner-deserts-115"]}
        await self.send(resumed, payload)
        for ws in (self.ws1, resumed):
            state = await self.receive_until(ws, lambda m: m.get("type") == "state" and bool(m["rulesEngine"]["suspendedCards"]))
            entry = state["rulesEngine"]["suspendedCards"][0]
            self.assertEqual((entry["cardId"], entry["ownerId"], entry["playableByPlayerId"]), ("inner-deserts-115", "p2", "p1"))
        before = copy.deepcopy((self.session.players, self.session.rules_engine, self.session.tokens))
        await self.send(resumed, payload)
        await self.receive_until(resumed, lambda m: m.get("type") == "error")
        self.assertEqual((self.session.players, self.session.rules_engine, self.session.tokens), before)
        hidden = self.session.serialize_for(None, "spectator")
        self.assertIsNone(hidden["rulesEngine"]["suspendedCards"][0]["cardId"])

    async def test_private_bob_suspension_stays_private_in_state_log_and_reconnect(self):
        self.hold_priority()
        self.session.players["p1"]["zones"]["deck"] = ["inner-deserts-143"]
        self.session.players["p1"]["zoneOwners"]["deck"] = {"inner-deserts-143": "p1"}
        error, entry = self.session.suspend_zone_card("p1", "deck", "inner-deserts-143", source_effect_id="bob")
        self.assertIsNone(error)
        self.session.add_log("p1", "rules_action_resolved", {"effectResult": {"status": "suspended", "suspensionId": entry["id"],
            "cardId": entry["cardId"], "ownerId": "p1", "fromZone": "deck"}})
        await self.ws2.close()
        resumed, _ = await self.join({"type": "join", "code": self.code, "clientId": "p2", "name": "P2"})
        state = await self.receive_until(resumed, lambda m: m.get("type") == "state")
        self.assertIsNone(state["rulesEngine"]["suspendedCards"][0]["cardId"])
        matching = [e for e in state["recentLog"] if e["type"] == "rules_action_resolved"]
        self.assertNotIn("cardId", matching[-1]["details"]["effectResult"])

    async def test_immediate_payment_reconnect_blocks_responses_and_resumes_remaining_immediates(self):
        self.hold_priority()
        self.session.rules_engine["actionStack"] = [
            {"id": "next-immediate", "controllerId": "p1", "label": "Next immediate", "kind": "triggered_effect", "source": {}, "targets": [],
             "immediate": True, "ability": {"result": {"kind": "score_owner", "value": 1}}},
            {"id": "kiss", "controllerId": "p1", "label": "Kiss", "kind": "play_card", "source": {"cardId": "inner-deserts-116"}, "targets": [],
             "immediate": True, "ability": {"result": {"kind": "end_confrontation_unless_payment", "payment": "{H}{H}{H}"}}},
        ]
        for result in self.session.resolve_rules_immediate_actions():
            await server_main.record_rules_resolution(self.session, result, "p1")
        choice_id = self.session.rules_engine["pendingChoice"]["id"]
        await self.ws2.close()
        resumed, _ = await self.join({"type": "join", "code": self.code, "clientId": "p2", "name": "P2"})
        state = await self.receive_until(resumed, lambda m: m.get("type") == "state")
        self.assertEqual(state["rulesEngine"]["pendingChoice"]["id"], choice_id)
        await self.send(resumed, {"type": "declare_rules_action", "label": "Response", "kind": "play_card", "source": {"zone": "hand", "cardId": "inner-deserts-047"}})
        await self.receive_until(resumed, lambda m: m.get("type") == "error")
        await self.send(resumed, {"type": "resolve_rules_choice", "choiceId": choice_id, "option": "pay", "cardIds": []})
        for ws in (self.ws1, resumed):
            state = await self.receive_until(ws, lambda m: m.get("type") == "state" and not m["rulesEngine"]["pendingChoice"] and not m["rulesEngine"]["actionStack"]
                and any(e.get("details", {}).get("actionId") == "next-immediate" for e in m.get("recentLog", [])))
            self.assertEqual(state["players"]["p1"]["score"], 1)
        self.assertEqual(sum(t["counters"]["essence"] for t in self.session.tokens if t.get("isEssence") and t["ownerId"] == "p2"), 5)
