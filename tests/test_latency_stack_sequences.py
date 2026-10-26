"""Two real WebSocket seats, deterministic pauses and late player commands."""
import asyncio
from contextlib import asynccontextmanager
import unittest
from unittest.mock import patch

import test_websocket_integration as sockets

main = sockets.server_main
PHASES = sockets.ADVANCED_PHASES


class LatencyStackSequences(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = sockets.WebSocketRulesIntegrationTests.asyncSetUp
    asyncTearDown = sockets.WebSocketRulesIntegrationTests.asyncTearDown
    join = sockets.WebSocketRulesIntegrationTests.join
    receive_until = sockets.WebSocketRulesIntegrationTests.receive_until
    send = sockets.WebSocketRulesIntegrationTests.send

    def prepare(self, stack=(), auto=False):
        s = self.session
        s.phase_tracker.update(enabled=True, advanced=True, turn=2, index=PHASES.index("confrontation_reaction"))
        s.rules_engine.update(deckConfirmedPlayerIds=["p1", "p2"], readyPlayerIds=["p1", "p2"],
            firstManifestationComplete=True, firstManifestationTriggersQueued=True,
            priorityPlayerId="p1", priorityPasses=[], pendingChoice=None, autoSkipPhases=auto)
        for pid in ("p1", "p2"):
            s.players[pid]["score"] = 0
            s.players[pid]["zones"]["hand"] = []
        for cid, power in (("seq-m2", 2), ("seq-m4", 4)):
            s.card_rules[cid] = {"type": "manifestation", "power": power,
                                "powerCost": "{G}" * power, "temperaments": ["phlegmatic"]}
            s.manifestation_ids.add(cid)
        s.battlefield = [{"id": pid+"-first", "cardId": cid, "ownerId": pid, "controllerId": pid,
                          "faceUp": True, "fieldZone": "confrontation", "counters": {},
                          "x": 0, "y": 0, "rotation": 0}
                         for pid, cid in (("p1", "seq-m2"), ("p2", "seq-m4"))]
        s.rules_engine["firstManifestationItemIds"] = {pid: pid+"-first" for pid in ("p1", "p2")}
        s.rules_engine["actionStack"] = list(stack)

    @staticmethod
    def effect(key, points=1, immediate=False):
        return {"id": key, "label": key, "kind": "triggered_effect", "controllerId": "p1",
                "source": {}, "targets": [], "immediate": immediate,
                "ability": {"result": {"kind": "score_owner", "value": points}}}

    def hand(self, pid, cards):
        self.session.players[pid]["zones"]["hand"] = list(cards)
        self.session.players[pid]["zoneOwners"]["hand"] = {cid: pid for cid in cards}

    def context(self):
        stack = self.session.rules_engine["actionStack"]
        return {"turn": 2, "phaseId": self.session.current_phase_id(),
                "topActionId": stack[-1]["id"] if stack else None}

    async def start_auto(self, auto=False):
        await self.send(self.ws1, {"type": "set_rules_auto_skip", "enabled": auto})

    @asynccontextmanager
    async def hold_resolution(self, action_id):
        entered, release = asyncio.Event(), asyncio.Event()
        original = main.broadcast_state

        async def gated(session):
            await original(session)
            if (session is self.session and not entered.is_set()
                    and (session.rules_engine.get("lastResolvedAction") or {}).get("id") == action_id):
                entered.set()
                await asyncio.wait_for(release.wait(), 5)

        with patch.object(main, "broadcast_state", side_effect=gated), patch.object(main, "STACK_RESOLUTION_PAUSE_SECONDS", 0):
            try:
                yield entered, release
            finally:
                release.set()

                async def idle():
                    while getattr(self.session, "_auto_advance_running", False):
                        await asyncio.sleep(.001)

                await asyncio.wait_for(idle(), 3)

    async def resolved(self, ws, action_id):
        return await self.receive_until(ws, lambda m: m.get("type") == "state"
            and (m.get("rulesEngine", {}).get("lastResolvedAction") or {}).get("id") == action_id)

    async def test_two_seats_observe_every_resolution_without_advancing_reaction(self):
        self.prepare([self.effect("bottom", 1), self.effect("middle", 10), self.effect("top", 100)], auto=True)
        async with self.hold_resolution("top") as (entered, release):
            await self.start_auto(auto=True)
            await asyncio.wait_for(entered.wait(), 2)
            top1, top2 = await asyncio.gather(self.resolved(self.ws1, "top"), self.resolved(self.ws2, "top"))
            for state in (top1, top2):
                self.assertEqual(len(state["rulesEngine"]["actionStack"]), 2)
                self.assertEqual(state["players"]["p1"]["score"], 100)
                self.assertIsNone(state["rulesEngine"]["confrontationResult"])
            release.set()
            for ws in (self.ws1, self.ws2):
                middle = await self.resolved(ws, "middle")
                self.assertEqual(len(middle["rulesEngine"]["actionStack"]), 1)
                self.assertEqual(middle["players"]["p1"]["score"], 110)
                bottom = await self.resolved(ws, "bottom")
                self.assertEqual(bottom["rulesEngine"]["actionStack"], [])
                self.assertEqual(bottom["players"]["p1"]["score"], 111)
        self.assertEqual(self.session.current_phase_id(), "confrontation_reaction")
        self.assertTrue(self.session.rules_confrontation_resolve_prompt())

    async def test_other_seat_can_add_a_response_during_the_resolution_pause(self):
        self.prepare([self.effect("bottom"), self.effect("top", 10)])
        self.session.rules_engine.update(priorityPlayerId="p1", priorityPasses=["p2"])
        will = "lo85kdsow36bymu_en"
        self.hand("p2", [will, "seq-m2"])
        async with self.hold_resolution("top") as (entered, release):
            await self.start_auto()
            await asyncio.wait_for(entered.wait(), 2)
            await self.send(self.ws2, {"type": "declare_rules_action", "label": "Latency response", "kind": "play_card",
                "source": {"cardId": will, "zone": "hand"}, "abilityId": "strengthen-power-modifier",
                "targets": [{"kind": "card", "itemId": "p2-first", "cardId": "seq-m4", "ownerId": "p2"}],
                "paymentCardIds": ["seq-m2"], "rulesContext": self.context()})
            response = await self.receive_until(self.ws2, lambda m: m.get("type") == "error" or
                m.get("type") == "state" and any(a.get("label") == "Latency response" for a in m["rulesEngine"]["actionStack"]))
            self.assertEqual(response["type"], "state")
            response_id = response["rulesEngine"]["actionStack"][-1]["id"]
            release.set()
            applied = await self.resolved(self.ws2, response_id)
            self.assertEqual([a["id"] for a in applied["rulesEngine"]["actionStack"]], ["bottom"])
            final = await self.resolved(self.ws2, "bottom")
            self.assertEqual(final["players"]["p1"]["score"], 11)
        target = self.session.find_battlefield_item("p2-first")
        self.assertEqual(self.session.rules_manifestation_characteristics(target)["power"], 7)

    async def test_reconnection_restores_a_required_choice_and_resumes_exactly_once(self):
        top = self.effect("discard")
        top["targets"] = [{"kind": "player", "playerId": "p2"}]
        top["ability"]["result"] = {"kind": "discard_hand_target", "value": 1}
        self.prepare([self.effect("bottom", 7), top])
        self.hand("p2", ["seq-m2"])
        async with self.hold_resolution("discard") as (entered, release):
            await self.start_auto()
            await asyncio.wait_for(entered.wait(), 2)
            choice = self.session.rules_engine["pendingChoice"]
            self.assertEqual(choice["kind"], "discard_from_hand")
            await self.ws2.close()
            reconnected, _ = await self.join({"type": "join", "code": self.code, "name": "P2", "clientId": "p2"})
            restored = await self.receive_until(reconnected, lambda m: m.get("type") == "state" and
                (m["rulesEngine"].get("pendingChoice") or {}).get("id") == choice["id"])
            self.assertEqual(restored["players"]["p2"]["zones"]["hand"]["cards"], ["seq-m2"])
            await self.send(reconnected, {"type": "resolve_rules_choice", "choiceId": choice["id"], "cardIds": ["seq-m2"]})
            await self.receive_until(reconnected, lambda m: m.get("type") == "state" and not m["rulesEngine"].get("pendingChoice"))
            await self.send(reconnected, {"type": "resolve_rules_choice", "choiceId": choice["id"], "cardIds": ["seq-m2"]})
            duplicate = await self.receive_until(reconnected, lambda m: m.get("type") == "error")
            self.assertIn("choice", duplicate["message"].lower())
            release.set()
            final = await self.resolved(reconnected, "bottom")
            self.assertEqual(final["players"]["p1"]["score"], 7)
        self.assertEqual(self.session.players["p2"]["zones"]["graveyard"], ["seq-m2"])
        self.assertEqual(sum(e["type"] == "rules_action_resolved" and e["details"]["actionId"] == "bottom" for e in self.session.log), 1)

    async def test_late_pass_for_a_removed_stack_top_cannot_confirm_end_of_reaction(self):
        self.prepare([self.effect("top")], auto=True)
        self.session.rules_engine.update(priorityPlayerId="p1", priorityPasses=["p2"])
        old_context = self.context()
        async with self.hold_resolution("top") as (entered, release):
            await self.start_auto(auto=True)
            await asyncio.wait_for(entered.wait(), 2)
            await self.send(self.ws1, {"type": "pass_priority", "passed": True, "rulesContext": old_context})
            # The driver uses ws1, so use the independently processed second
            # socket for the same seat, as after a reconnect/duplicate send.
            peer, _ = await self.join({"type": "join", "code": self.code, "name": "P1", "clientId": "p1"})
            await self.send(peer, {"type": "pass_priority", "passed": True, "rulesContext": old_context})
            result = await self.receive_until(peer, lambda m: m.get("type") == "error" or
                m.get("type") == "state" and m["rulesEngine"].get("priorityPasses") == ["p1"])
            self.assertEqual(result["type"], "error", "An old Stack pass was applied to an empty Stack")
            self.assertEqual(self.session.rules_engine["priorityPasses"], [])
            release.set()
        self.assertEqual(self.session.current_phase_id(), "confrontation_reaction")

    async def test_late_reaction_will_is_not_silently_played_after_comparison(self):
        self.prepare()
        will = "lo85kdsow36bymu_en"
        self.hand("p1", [will, "seq-m2"])
        old_context = self.context()
        # Real empty-Stack passes advance through comparison into Resolution.
        for _ in range(4):
            self.assertIsNone(self.session.pass_rules_priority(self.session.rules_engine["priorityPlayerId"])[0])
        self.assertEqual(self.session.current_phase_id(), "resolution_effects")
        if self.session.rules_engine["priorityPlayerId"] != "p1":
            self.assertIsNone(self.session.pass_rules_priority(self.session.rules_engine["priorityPlayerId"])[0])
        await self.send(self.ws1, {"type": "declare_rules_action", "label": "Late Strengthen", "kind": "play_card",
            "source": {"cardId": will, "zone": "hand"}, "abilityId": "strengthen-power-modifier",
            "targets": [{"kind": "card", "itemId": "p1-first", "cardId": "seq-m2", "ownerId": "p1"}],
            "paymentCardIds": ["seq-m2"], "rulesContext": old_context})
        result = await self.receive_until(self.ws1, lambda m: m.get("type") == "error" or
            m.get("type") == "state" and any(e.get("type") == "rules_action_declared" and e["details"].get("label") == "Late Strengthen" for e in m.get("recentLog", [])))
        self.assertEqual(result["type"], "error", "A Reaction intent was accepted during Resolution")
        self.assertEqual(self.session.players["p1"]["zones"]["hand"], [will, "seq-m2"])
        self.assertEqual(self.session.rules_engine["actionStack"], [])

    async def test_a_rejected_old_choice_cannot_drive_automatic_phase_changes(self):
        self.prepare(auto=True)
        self.session.phase_tracker["index"] = PHASES.index("end_actions")
        await self.send(self.ws1, {"type": "resolve_rules_choice", "choiceId": "completed-choice", "cardIds": []})
        await self.receive_until(self.ws1, lambda m: m.get("type") == "error")
        await self.send(self.ws1, {"type": "chat_message", "text": "after rejected choice"})
        await self.receive_until(self.ws1, lambda m: m.get("type") == "chat_message" and m.get("text") == "after rejected choice")
        self.assertEqual(self.session.current_phase_id(), "end_actions")
        self.assertEqual(self.session.phase_tracker["turn"], 2)
        self.assertEqual(self.session.rules_engine["priorityPasses"], [])

    async def test_a_changed_stack_top_rejects_the_old_pass_without_resolving_either_card(self):
        self.prepare([self.effect("bottom")])
        old_context = self.context()
        self.session.rules_engine["actionStack"].append(self.effect("new-top", 10))
        await self.send(self.ws1, {"type": "pass_priority", "passed": True, "rulesContext": old_context})
        error = await self.receive_until(self.ws1, lambda m: m.get("type") == "error")
        self.assertEqual(error.get("code"), "rules_context_changed")
        await self.send(self.ws1, {"type": "chat_message", "text": "after rejected pass"})
        await self.receive_until(self.ws1, lambda m: m.get("type") == "chat_message" and m.get("text") == "after rejected pass")
        self.assertEqual([a["id"] for a in self.session.rules_engine["actionStack"]], ["bottom", "new-top"])
        self.assertEqual(self.session.players["p1"]["score"], 0)

    async def test_old_turn_and_malformed_contexts_do_not_pass_priority(self):
        self.prepare()
        valid = self.context()
        for context in (None, [], "old", {}, {**valid, "turn": True}, {**valid, "turn": 1},
                        {**valid, "topActionId": "gone"}):
            with self.subTest(context=context):
                await self.send(self.ws1, {"type": "pass_priority", "passed": True, "rulesContext": context})
                error = await self.receive_until(self.ws1, lambda m: m.get("type") == "error")
                self.assertEqual(error.get("code"), "rules_context_changed")
                self.assertEqual(self.session.rules_engine["priorityPasses"], [])
        await self.send(self.ws1, {"type": "pass_priority", "passed": True, "rulesContext": valid})
        await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and m["rulesEngine"].get("priorityPasses") == ["p1"])
        await self.send(self.ws1, {"type": "pass_priority", "passed": False, "rulesContext": valid})
        await self.receive_until(self.ws1, lambda m: m.get("type") == "state" and not m["rulesEngine"].get("priorityPasses") and m["rulesEngine"]["priorityPlayerId"] == "p1")
        self.assertEqual(self.session.current_phase_id(), "confrontation_reaction")

    async def test_cancelling_a_gone_memory_really_resumes_the_suspended_stack(self):
        self.prepare([self.effect("bottom", 7)])
        self.session.rules_engine["pendingChoice"] = {"id": "obsolete-memory", "kind": "effect_memory_return",
            "playerId": "p1", "memoryId": "removed-memory", "sourceCardId": "lo85kdsow36bymu_en"}
        with patch.object(main, "STACK_RESOLUTION_PAUSE_SECONDS", 0):
            await self.send(self.ws1, {"type": "resolve_rules_choice", "choiceId": "obsolete-memory", "option": "return"})
            await self.receive_until(self.ws1, lambda m: m.get("type") == "error")
            final = await self.resolved(self.ws1, "bottom")
        self.assertIsNone(final["rulesEngine"]["pendingChoice"])
        self.assertEqual(final["rulesEngine"]["actionStack"], [])
        self.assertEqual(final["players"]["p1"]["score"], 7)
        self.assertEqual(self.session.current_phase_id(), "confrontation_reaction")

    async def test_immediate_sequence_blocks_responses_until_normal_stack_resumes(self):
        self.prepare([self.effect("bottom"), self.effect("immediate-middle", 10, True), self.effect("immediate-top", 100, True)])
        will = "lo85kdsow36bymu_en"
        self.hand("p2", [will, "seq-m2"])
        async with self.hold_resolution("immediate-top") as (entered, release):
            await self.start_auto()
            await asyncio.wait_for(entered.wait(), 2)
            await self.send(self.ws2, {"type": "declare_rules_action", "label": "Forbidden response", "kind": "play_card",
                "source": {"cardId": will, "zone": "hand"}, "abilityId": "strengthen-power-modifier",
                "targets": [{"kind": "card", "itemId": "p2-first", "cardId": "seq-m4", "ownerId": "p2"}],
                "paymentCardIds": ["seq-m2"], "rulesContext": self.context()})
            error = await self.receive_until(self.ws2, lambda m: m.get("type") == "error")
            self.assertIn("Immediate", error["message"])
            self.assertEqual(self.session.players["p2"]["zones"]["hand"], [will, "seq-m2"])
            release.set()
            final = await self.resolved(self.ws2, "immediate-middle")
            self.assertEqual([a["id"] for a in final["rulesEngine"]["actionStack"]], ["bottom"])
            self.assertEqual(final["players"]["p1"]["score"], 110)
        self.assertEqual(self.session.rules_engine["priorityPlayerId"], "p2")
        self.assertEqual([a["id"] for a in self.session.rules_engine["actionStack"]], ["bottom"])
