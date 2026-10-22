"""Choice retries, replay and reconnection through the real WebSocket server."""
import copy
import json
import unittest

import test_websocket_integration as websocket_tests
import main as server_main


class ChoiceReconnectTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = websocket_tests.WebSocketRulesIntegrationTests.asyncSetUp
    asyncTearDown = websocket_tests.WebSocketRulesIntegrationTests.asyncTearDown
    join = websocket_tests.WebSocketRulesIntegrationTests.join
    receive_until = websocket_tests.WebSocketRulesIntegrationTests.receive_until
    send = websocket_tests.WebSocketRulesIntegrationTests.send
    prepare_active_rules = websocket_tests.WebSocketRulesIntegrationTests.prepare_active_rules

    def pending_order(self):
        self.prepare_active_rules("end_actions")
        self.session.rules_engine["firstManifestationComplete"] = True
        # Keep priority open after validation so this test does not auto-pass
        # through unrelated phases or draw cards from the decks being checked.
        will = "lmx5uff1z53fo0g_en"
        self.session.players["p1"]["zones"]["hand"] = [will]
        self.session.players["p1"]["zoneOwners"]["hand"] = {will: "p1"}
        self.session.add_rules_excess_essence("p1", [{"temperament": "transcendent", "amount": 8}])
        cards = [cid for cid, metadata in self.session.card_rules.items()
                 if metadata.get("type") == "manifestation"][:6]
        for pid, selected in [("p1", cards[:3]), ("p2", cards[3:])]:
            self.session.players[pid]["zones"]["deck"] = list(selected)
            self.session.players[pid]["zoneOwners"]["deck"] = {cid: pid for cid in selected}
        self.session.apply_rules_action_result({"controllerId": "p1", "source": {"cardId": "inner-deserts-047"},
            "ability": server_main.CARD_ABILITIES["inner-deserts-047"][0]})
        return {"type": "resolve_rules_choice", "choiceId": self.session.rules_engine["pendingChoice"]["id"],
            "option": {"groups": [{"playerId": "p1", "top": [cards[1]], "bottom": [cards[2], cards[0]]},
                                  {"playerId": "p2", "top": [cards[4]], "bottom": [cards[5], cards[3]]}]}}

    def state(self):
        return copy.deepcopy((self.session.players, self.session.battlefield, self.session.tokens,
                              self.session.rules_engine, self.session.phase_tracker))

    async def test_reconnect_can_retry_and_the_old_submission_cannot_apply_twice(self):
        valid = self.pending_order()
        invalid = copy.deepcopy(valid)
        invalid["option"]["groups"][1]["top"] = ["not-in-deck"]
        before = self.state()
        await self.send(self.ws1, invalid)
        await self.receive_until(self.ws1, lambda m: m.get("type") == "error")
        self.assertEqual(self.state(), before)
        await self.ws1.close()
        reconnected, joined = await self.join({"type": "join", "code": self.code,
                                              "name": "P1", "clientId": "p1"})
        self.assertEqual(joined["playerId"], "p1")
        restored = await self.receive_until(reconnected, lambda m: m.get("type") == "state")
        self.assertEqual(restored["rulesEngine"]["pendingChoice"]["id"], valid["choiceId"])
        await self.send(reconnected, valid)
        resolved = await self.receive_until(reconnected, lambda m: m.get("type") == "state"
            and m["rulesEngine"]["pendingChoice"] is None)
        self.assertEqual(resolved["players"]["p1"]["zones"]["deck"]["cards"],
                         valid["option"]["groups"][0]["top"] + valid["option"]["groups"][0]["bottom"])
        after = self.state()
        await self.send(reconnected, valid)
        await self.receive_until(reconnected, lambda m: m.get("type") == "error")
        self.assertEqual(self.state(), after)

    async def test_opponent_cannot_answer_and_obsolete_id_cannot_replace_current_choice(self):
        valid = self.pending_order()
        before = self.state()
        await self.send(self.ws2, valid)
        await self.receive_until(self.ws2, lambda m: m.get("type") == "error")
        self.assertEqual(self.state(), before)
        valid["choiceId"] = "obsolete-id"
        await self.send(self.ws1, valid)
        await self.receive_until(self.ws1, lambda m: m.get("type") == "error")
        self.assertEqual(self.state(), before)

    async def test_two_immediate_validations_apply_the_choice_once(self):
        valid = self.pending_order()
        await self.send(self.ws1, valid)
        await self.send(self.ws1, valid)
        await self.receive_until(self.ws1, lambda m: m.get("type") == "state"
            and m["rulesEngine"]["pendingChoice"] is None)
        await self.receive_until(self.ws1, lambda m: m.get("type") == "error")
        matching = [entry for entry in self.session.log
                    if entry["type"] == "rules_choice_resolved"
                    and entry["details"].get("kind") == "deck_reorder"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(self.session.players["p1"]["zones"]["deck"],
                         valid["option"]["groups"][0]["top"] + valid["option"]["groups"][0]["bottom"])

    async def test_cancelled_obsolete_current_choice_is_broadcast_to_both_players(self):
        self.prepare_active_rules("end_actions")
        self.session.players["p1"]["zones"]["deck"] = []
        self.session.rules_engine["pendingChoice"] = {"id": "peek", "kind": "peek_top_card",
            "playerId": "p1", "_cardId": "gone", "sourceCardId": "test-source"}
        await server_main.broadcast_state(self.session)
        for ws in [self.ws1, self.ws2]:
            await self.receive_until(ws, lambda m: m.get("type") == "state"
                and (m["rulesEngine"]["pendingChoice"] or {}).get("id") == "peek")
        await self.send(self.ws1, {"type": "resolve_rules_choice", "choiceId": "peek", "option": "keep"})
        await self.receive_until(self.ws1, lambda m: m.get("type") == "error")
        self.assertIsNone(self.session.rules_engine["pendingChoice"])
        for ws in [self.ws1, self.ws2]:
            await self.receive_until(ws, lambda m: m.get("type") == "state"
                and m["rulesEngine"]["pendingChoice"] is None)


    async def test_private_deck_order_stays_private_after_resolution_log_and_reconnect(self):
        valid = self.pending_order()
        hidden = list(self.session.players['p1']['zones']['deck'])
        await self.send(self.ws1, valid)
        state = await self.receive_until(self.ws2, lambda m: m.get('type') == 'state'
            and m['rulesEngine']['pendingChoice'] is None
            and any(e['type'] == 'rules_choice_resolved' for e in m['recentLog']))
        for cid in hidden:
            self.assertNotIn(cid, json.dumps(state))
        await self.send(self.ws2, {'type': 'request_log'})
        log = await self.receive_until(self.ws2, lambda m: m.get('type') == 'log')
        for cid in hidden:
            self.assertNotIn(cid, json.dumps(log))
        await self.ws2.close()
        restored_ws, _ = await self.join({'type': 'join', 'code': self.code, 'name': 'P2', 'clientId': 'p2'})
        restored = await self.receive_until(restored_ws, lambda m: m.get('type') == 'state')
        for cid in hidden:
            self.assertNotIn(cid, json.dumps(restored))
