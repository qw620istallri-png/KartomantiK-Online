"""Live two-seat auto-driver: large Stacks, choices and published pacing.

Only animation sleeps are shortened; the auto-driver is not mocked.
"""
import asyncio
import unittest
from unittest.mock import patch

import test_latency_stack_sequences as latency

main = latency.main


class AutoPhaseIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = latency.LatencyStackSequences.asyncSetUp
    asyncTearDown = latency.LatencyStackSequences.asyncTearDown
    join = latency.LatencyStackSequences.join
    receive_until = latency.LatencyStackSequences.receive_until
    send = latency.LatencyStackSequences.send
    prepare = latency.LatencyStackSequences.prepare
    effect = staticmethod(latency.LatencyStackSequences.effect)
    hand = latency.LatencyStackSequences.hand
    start_auto = latency.LatencyStackSequences.start_auto
    resolved = latency.LatencyStackSequences.resolved

    @patch.object(main, "STACK_RESOLUTION_PAUSE_SECONDS", 0)
    async def test_both_seats_observe_all_thirty_three_cards_without_a_second_command(self):
        self.prepare([self.effect(f"long-{n}") for n in range(33)], auto=True)
        await self.start_auto(auto=True)
        for resolved_count, n in enumerate(reversed(range(33)), 1):
            states = await asyncio.gather(self.resolved(self.ws1, f"long-{n}"), self.resolved(self.ws2, f"long-{n}"))
            for state in states:
                self.assertEqual(len(state["rulesEngine"]["actionStack"]), 33 - resolved_count)
                self.assertEqual(state["players"]["p1"]["score"], resolved_count)
                self.assertEqual(state["phaseTracker"]["index"], latency.PHASES.index("confrontation_reaction"))
                self.assertIsNone(state["rulesEngine"]["confrontationResult"])
        self.assertTrue(self.session.rules_confrontation_resolve_prompt())

    async def test_each_immediate_and_normal_effect_publishes_then_requests_the_readability_pause(self):
        self.prepare([self.effect("normal", 1), self.effect("immediate-low", 10, True), self.effect("immediate-high", 100, True)])
        original_sleep = asyncio.sleep
        pauses = []

        async def shortened_sleep(delay, *args, **kwargs):
            if delay == main.STACK_RESOLUTION_PAUSE_SECONDS:
                pauses.append((self.session.rules_engine["lastResolvedAction"]["id"], len(self.session.rules_engine["actionStack"])))
            await original_sleep(0)

        self.assertEqual(main.STACK_RESOLUTION_PAUSE_SECONDS, 1.7)
        with patch.object(main.asyncio, "sleep", side_effect=shortened_sleep):
            await self.start_auto()
            for key, score, remaining in (("immediate-high", 100, 2), ("immediate-low", 110, 1), ("normal", 111, 0)):
                for ws in (self.ws1, self.ws2):
                    state = await self.resolved(ws, key)
                    self.assertEqual(state["players"]["p1"]["score"], score)
                    self.assertEqual(len(state["rulesEngine"]["actionStack"]), remaining)
        self.assertEqual(pauses, [("immediate-high", 2), ("immediate-low", 1), ("normal", 0)])

    @patch.object(main, "STACK_RESOLUTION_PAUSE_SECONDS", 0)
    async def test_choice_after_the_budget_boundary_blocks_then_resumes_once(self):
        stack = [self.effect(f"after-choice-{n}") for n in range(3)]
        discard = self.effect("discard-after-boundary")
        discard.update(targets=[{"kind": "player", "playerId": "p2"}], ability={"result": {"kind": "discard_hand_target", "value": 1}})
        stack.append(discard)
        stack.extend(self.effect(f"before-choice-{n}") for n in range(31))
        self.prepare(stack)
        self.hand("p2", ["seq-m2"])
        await self.start_auto()
        _, state = await asyncio.gather(self.resolved(self.ws1, "discard-after-boundary"), self.resolved(self.ws2, "discard-after-boundary"))
        choice = state["rulesEngine"]["pendingChoice"]
        self.assertEqual(choice["kind"], "discard_from_hand")
        self.assertEqual(len(state["rulesEngine"]["actionStack"]), 3)
        self.assertEqual(state["players"]["p1"]["score"], 31)
        await self.send(self.ws2, {"type": "resolve_rules_choice", "choiceId": choice["id"], "cardIds": ["seq-m2"]})
        _, final = await asyncio.gather(self.resolved(self.ws1, "after-choice-0"), self.resolved(self.ws2, "after-choice-0"))
        self.assertEqual(final["rulesEngine"]["actionStack"], [])
        self.assertEqual(final["players"]["p1"]["score"], 34)
        self.assertEqual(self.session.current_phase_id(), "confrontation_reaction")
        self.assertEqual(sum(e["type"] == "rules_action_resolved" and e["details"]["actionId"] == "after-choice-0" for e in self.session.log), 1)


if __name__ == "__main__":
    unittest.main()
