"""Gorlok over mixed-version sockets; draw/source mutations are explicit fixtures."""
import json
import unittest
from unittest.mock import AsyncMock, patch
import test_state_transport_integration as transport
import test_bounce_replay_integration as bounce
import test_gorlok_draw_clauses as clauses

main = transport.main


class GorlokDrawIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = transport.StateTransportIntegration.asyncSetUp
    asyncTearDown = transport.StateTransportIntegration.asyncTearDown
    join = transport.StateTransportIntegration.join
    receive_until = transport.StateTransportIntegration.receive_until
    send = transport.StateTransportIntegration.send
    prepare_active_rules = transport.StateTransportIntegration.prepare_active_rules
    pass_stack = bounce.BounceReplayIntegration.pass_stack

    def setup_rules(self, deck=("m2", "m3", "m4"), hand=()):
        f, s = clauses.GorlokDrawClauses(), self.session
        self.prepare_active_rules("confrontation_reaction", priority="p2")
        s.phase_tracker.update(enabled=True, advanced=True, turn=2)
        s.rules_engine.update(firstManifestationComplete=True, firstManifestationTriggersQueued=True)
        fixture = f.world()
        for cid in ("m2", "m3", "m4", "w2", "pw3"):
            s.card_rules[cid] = fixture.card_rules[cid]
            if cid.startswith("m"):
                s.manifestation_ids.add(cid)
        host = f.field(s, f.cid(f.NAME), "gorlok", zone="interzone")
        f.put(s, "p2", "deck", deck)
        f.put(s, "p2", "hand", hand)
        return f, s, host

    async def publish(self, actions):
        self.session.rules_engine["actionStack"] = actions
        await main.broadcast_state(self.session)
        return await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and
            len(m["rulesEngine"]["actionStack"]) == len(actions))

    async def resolve_top(self):
        sockets = {"p1": self.ws1, "p2": self.ws2}
        pid = self.session.rules_engine["priorityPlayerId"]
        await self.pass_stack(sockets[pid], sockets["p1" if pid == "p2" else "p2"])
        return await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and
            (m["rulesEngine"]["pendingChoice"] or {}).get("purpose") == "gorlok")

    async def answer(self, choice_id, index="0"):
        await self.send(self.ws1, {"type": "resolve_rules_choice", "choiceId": choice_id, "option": index})
        return await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and m["rulesEngine"]["pendingChoice"] is None)

    async def reconnect_player(self, player):
        old = self.ws1 if player == "p1" else self.ws2
        await old.close()
        ws, _ = await self.join({"type": "join", "code": self.code, "name": player.upper(), "clientId": player})
        if player == "p1":
            self.ws1 = ws
        else:
            self.ws2 = ws
        return await self.receive_until(ws, lambda m: m.get("type") == "state")

    @patch("main.auto_advance_rules_phases", new_callable=AsyncMock, return_value=False)
    async def test_delayed_draws_keep_separate_private_batches_through_reconnect(self, _driver):
        f, s, host = self.setup_rules()
        power = s.rules_manifestation_characteristics(host)["power"]
        first, = f.draw(s, 1)
        second, = f.draw(s, 2)
        queued = await self.publish([first, second])
        self.assertNotIn('"m2"', json.dumps(queued["rulesEngine"]["actionStack"]))
        self.assertNotIn("cards", queued["players"]["p2"]["zones"]["hand"])
        paused = await self.resolve_top()
        choice_id = paused["rulesEngine"]["pendingChoice"]["id"]
        self.assertEqual(paused["rulesEngine"]["pendingChoice"]["cardIds"], ["m3", "m4"])
        restored = await self.reconnect_player("p1")
        self.assertEqual(restored["rulesEngine"]["pendingChoice"]["id"], choice_id)
        self.assertNotIn("_drawnCards", restored["rulesEngine"]["pendingChoice"])
        self.assertEqual(self.wires[self.ws1][-1]["stateRevision"], 1)
        before = f.snapshot(s)
        await self.send(self.ws1, {"type": "resolve_rules_choice", "choiceId": choice_id, "option": "3"})
        await self.receive_until(self.ws1, lambda m: m.get("type") == "error")
        self.assertEqual(f.snapshot(s), before)
        await self.answer(choice_id)
        self.assertEqual(s.rules_manifestation_characteristics(host)["power"], power - 2)
        next_state = await self.resolve_top()
        second_id = next_state["rulesEngine"]["pendingChoice"]["id"]
        self.assertEqual(next_state["rulesEngine"]["pendingChoice"]["cardIds"], ["m2"])
        before = f.snapshot(s)
        await self.send(self.ws2, {"type": "resolve_rules_choice", "choiceId": second_id, "option": "0"})
        await self.receive_until(self.ws2, lambda m: m.get("type") == "error")
        self.assertEqual(f.snapshot(s), before)
        await self.answer(second_id)
        self.assertEqual(s.players["p2"]["zones"]["hand"], ["m4"])
        self.assertCountEqual(s.players["p2"]["zones"]["exile"], ["m2", "m3"])
        self.assertEqual(s.rules_manifestation_characteristics(host)["power"], power - 3)
        before = f.snapshot(s)
        await self.send(self.ws1, {"type": "resolve_rules_choice", "choiceId": second_id, "option": "0"})
        await self.receive_until(self.ws1, lambda m: m.get("type") == "error")
        self.assertEqual(f.snapshot(s), before)

    @patch("main.auto_advance_rules_phases", new_callable=AsyncMock, return_value=False)
    async def test_identical_draws_survive_hand_reorder_shuffle_and_legacy_reconnect(self, _driver):
        f, s, host = self.setup_rules(deck=["m2", "m2"], hand=["pw3"])
        power = s.rules_manifestation_characteristics(host)["power"]
        first, = f.draw(s, 1)
        second, = f.draw(s, 1)
        await self.publish([first, second])
        await self.send(self.ws2, {"type": "reorder", "ownerId": "p2", "zone": "hand", "order": ["m2", "pw3", "m2"]})
        await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and
            m["players"]["p2"]["zones"]["hand"]["cards"] == ["m2", "pw3", "m2"])
        await self.send(self.ws2, {"type": "shuffle", "ownerId": "p2", "zone": "hand"})
        await self.receive_until(self.ws2, lambda m: m.get("type") == "state" and any(
            e.get("type") == "shuffle" and e.get("details", {}).get("zone") == "hand" for e in m.get("recentLog", [])))
        restored = await self.reconnect_player("p2")
        self.assertNotIn("stateRevision", self.wires[self.ws2][-1])
        self.assertEqual(len(restored["rulesEngine"]["actionStack"]), 2)
        for _ in range(2):
            state = await self.resolve_top()
            self.assertEqual(state["rulesEngine"]["pendingChoice"]["cardIds"], ["m2"])
            await self.answer(state["rulesEngine"]["pendingChoice"]["id"])
        self.assertEqual(s.players["p2"]["zones"]["hand"], ["pw3"])
        self.assertEqual(s.players["p2"]["zones"]["exile"], ["m2", "m2"])
        self.assertEqual(s.rules_manifestation_characteristics(host)["power"], power - 2)

    @patch("main.auto_advance_rules_phases", new_callable=AsyncMock, return_value=False)
    async def test_departed_source_and_returned_hand_card_do_not_break_remaining_exile(self, _driver):
        f, s, host = self.setup_rules(deck=["m2", "m3"])
        action, = f.draw(s, 2)
        s._rules_remove_field_item(host, "p1", "graveyard")
        s.move_zone_card("p2", "hand", "p2", "graveyard", "m2")
        s.move_zone_card("p2", "graveyard", "p2", "hand", "m2", "bottom")
        await self.publish([action])
        restored = await self.reconnect_player("p1")
        self.assertFalse(any(i["id"] == host["id"] for i in restored["battlefield"]))
        state = await self.resolve_top()
        self.assertEqual(state["rulesEngine"]["pendingChoice"]["cardIds"], ["m3"])
        await self.answer(state["rulesEngine"]["pendingChoice"]["id"])
        self.assertEqual(s.players["p2"]["zones"]["hand"], ["m2"])
        self.assertEqual(s.players["p2"]["zones"]["exile"], ["m3"])


if __name__ == "__main__":
    unittest.main()
