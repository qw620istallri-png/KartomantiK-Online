"""Mixed-version sockets for chosen discards and privately shown hands."""
import json
import unittest
from unittest.mock import AsyncMock, patch
import test_state_transport_integration as transport
import test_bounce_replay_integration as bounce
import test_private_hand_clauses as clauses

main = transport.main


class PrivateHandIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = transport.StateTransportIntegration.asyncSetUp
    asyncTearDown = transport.StateTransportIntegration.asyncTearDown
    join = transport.StateTransportIntegration.join
    receive_until = transport.StateTransportIntegration.receive_until
    send = transport.StateTransportIntegration.send
    prepare_active_rules = transport.StateTransportIntegration.prepare_active_rules
    pass_stack = bounce.BounceReplayIntegration.pass_stack

    def setup_rules(self, hand):
        f, s = clauses.PrivateHandClauses(), self.session
        self.prepare_active_rules("confrontation_reaction")
        s.phase_tracker.update(enabled=True, advanced=True, turn=2)
        s.rules_engine.update(firstManifestationComplete=True, firstManifestationTriggersQueued=True)
        fixture = f.world()
        for cid in ("m2", "m3", "m4", "w2", "pw3"):
            s.card_rules[cid] = fixture.card_rules[cid]
            if cid.startswith("m"):
                s.manifestation_ids.add(cid)
        for player in s.players.values():
            player["score"] = 50
        f.put(s, "p2", "hand", hand)
        return f, s

    async def reconnect(self, choice_id):
        await self.ws1.close()
        self.ws1, _ = await self.join({"type": "join", "code": self.code, "name": "P1", "clientId": "p1"})
        state = await self.receive_until(self.ws1, lambda m: m.get("type") == "state")
        self.assertEqual(state["rulesEngine"]["pendingChoice"]["id"], choice_id)
        self.assertEqual(self.wires[self.ws1][-1]["stateRevision"], 1)
        return state

    async def start_womb(self, f, s):
        f.field(s, f.cid(f.WOMB), "womb", zone="field")
        s.queue_rules_reaction_triggers()  # Explicit phase-event stimulus; actual passes/choices follow.
        s.rules_engine["priorityPlayerId"] = "p2"
        await main.broadcast_state(s)
        await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and bool(m["rulesEngine"]["actionStack"]))
        await self.pass_stack(self.ws2, self.ws1)
        return await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and
            (m["rulesEngine"]["pendingChoice"] or {}).get("purpose") == "womb_show")

    async def spectator(self, s):
        s.mode, s.status = "tournament", "active"
        s.code_player1, s.code_player2, s.code_spectator = self.code, "PLAYER02", "WATCHER1"
        ws, _ = await self.join({"type": "join", "code": s.code_spectator, "name": "Watcher", "clientId": "watcher"})
        await self.receive_until(ws, lambda m: m.get("type") == "state")
        return ws

    @patch("main.auto_advance_rules_phases", new_callable=AsyncMock, return_value=False)
    async def test_traumatize_reconnect_keeps_optional_replacement_and_pays_once(self, _driver):
        tenebro = clauses.PrivateHandClauses.cid("Tenebro, Night Assailant")
        f, s = self.setup_rules([tenebro, "w2"])
        f.put(s, "p1", "hand", [f.cid(f.TRAUMA)])
        s.add_rules_excess_essence("p1", [{"temperament": "melancholic", "amount": 2}])
        await self.send(self.ws1, {"type": "declare_rules_action", "label": "Traumatize", "kind": "play_card",
            "source": {"cardId": f.cid(f.TRAUMA), "zone": "hand"}, "abilityId": "traumatize",
            "targets": [{"kind": "player", "playerId": "p2"}]})
        await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and bool(m["rulesEngine"]["actionStack"]))
        self.assertEqual(s.players["p1"]["score"], 50)
        await self.pass_stack(self.ws2, self.ws1)
        paused = await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and
            (m["rulesEngine"]["pendingChoice"] or {}).get("kind") == "reveal_hand_discard")
        self.assertEqual(s.players["p1"]["score"], 45)
        choice_id = paused["rulesEngine"]["pendingChoice"]["id"]
        await self.reconnect(choice_id)
        await self.send(self.ws1, {"type": "resolve_rules_choice", "choiceId": choice_id, "option": "0"})
        replaced = await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and
            (m["rulesEngine"]["pendingChoice"] or {}).get("purpose") == "discard_support_replacement")
        self.assertEqual(s.players["p2"]["zones"]["hand"], [tenebro, "w2"])
        replacement_id = replaced["rulesEngine"]["pendingChoice"]["id"]
        await self.send(self.ws2, {"type": "resolve_rules_choice", "choiceId": replacement_id, "option": "yes"})
        await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and m["rulesEngine"]["pendingChoice"] is None)
        self.assertEqual(s.players["p1"]["score"], 45)
        self.assertTrue(any(i["cardId"] == tenebro and i.get("isSupport") for i in s.battlefield))
        before = f.snapshot(s)
        await self.send(self.ws1, {"type": "resolve_rules_choice", "choiceId": choice_id, "option": "0"})
        await self.receive_until(self.ws1, lambda m: m.get("type") == "error")
        self.assertEqual(f.snapshot(s), before)

    @patch("main.auto_advance_rules_phases", new_callable=AsyncMock, return_value=False)
    async def test_womb_shows_full_hand_privately_then_chains_after_reconnect(self, _driver):
        f, s = self.setup_rules(["m2", "w2"])
        watch = await self.spectator(s)
        paused = await self.start_womb(f, s)
        await self.send(self.ws2, {"type": "resolve_rules_choice", "choiceId": paused["rulesEngine"]["pendingChoice"]["id"], "option": "yes"})
        picked = await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and
            (m["rulesEngine"]["pendingChoice"] or {}).get("purpose") == "womb")
        self.assertEqual(picked["rulesEngine"]["pendingChoice"]["revealedHandCardIds"], ["m2", "w2"])
        owner = await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and
            (m["rulesEngine"]["pendingChoice"] or {}).get("purpose") == "womb")
        self.assertEqual(owner["rulesEngine"]["pendingChoice"]["revealedHandCardIds"], ["m2", "w2"])
        hidden = await self.receive_until(watch, lambda m: m.get("type") == "state" and
            (m["rulesEngine"]["pendingChoice"] or {}).get("purpose") == "womb")
        self.assertNotIn('"w2"', json.dumps(hidden))
        self.assertFalse(any(m.get("type") == "reveal" for m in self.wires[watch]))
        choice_id = picked["rulesEngine"]["pendingChoice"]["id"]
        restored = await self.reconnect(choice_id)
        self.assertEqual(restored["rulesEngine"]["pendingChoice"]["revealedHandCardIds"], ["m2", "w2"])
        self.assertEqual(restored["rulesEngine"]["pendingChoice"]["cardIds"], ["m2"])
        await self.send(self.ws1, {"type": "resolve_rules_choice", "choiceId": choice_id, "option": "0"})
        await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and m["rulesEngine"]["pendingChoice"] is None)
        chained = [i for i in s.battlefield if i.get("isChained")]
        self.assertEqual([(i["cardId"], i["controllerId"]) for i in chained], [("m2", "p2")])
        await self.send(watch, {"type": "request_log"})
        denied = await self.receive_until(watch, lambda m: m.get("type") == "error")
        self.assertIn("restricted", denied["message"])
        s.status = "ended"  # Explicit log-access fixture, not an endgame scenario.
        await self.send(watch, {"type": "request_log"})
        logged = await self.receive_until(watch, lambda m: m.get("type") == "log")
        self.assertNotIn('"w2"', json.dumps(logged))

    @patch("main.auto_advance_rules_phases", new_callable=AsyncMock, return_value=False)
    async def test_womb_no_chainable_hand_still_shows_privately_before_token_result(self, _driver):
        f, s = self.setup_rules(["w2", "pw3"])
        watch = await self.spectator(s)
        paused = await self.start_womb(f, s)
        await self.send(self.ws2, {"type": "resolve_rules_choice", "choiceId": paused["rulesEngine"]["pendingChoice"]["id"], "option": "yes"})
        reveal = await self.receive_until(self.ws1, lambda m: m.get("type") == "reveal" or
            (m.get("type") == "state" and m["rulesEngine"]["pendingChoice"] is None
             and len([i for i in m["battlefield"] if i.get("isTokenCard")]) == 2))
        self.assertEqual(reveal["type"], "reveal")
        self.assertEqual(reveal["cards"], ["w2", "pw3"])
        await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and m["rulesEngine"]["pendingChoice"] is None)
        f.tokens(s)
        spectator = await self.receive_until(watch, lambda m: m.get("type") == "state" and m["rulesEngine"]["pendingChoice"] is None
            and len([i for i in m["battlefield"] if i.get("isTokenCard")]) == 2)
        self.assertNotIn('"w2"', json.dumps(spectator))
        self.assertNotIn('"pw3"', json.dumps(spectator))
        self.assertFalse(any(m.get("type") == "reveal" for m in self.wires[watch]))


if __name__ == "__main__":
    unittest.main()
