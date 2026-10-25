"""Live clients see one resolved action per state, with time to read it."""
import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

import test_auto_pass as fixtures
import test_semantic_batch_001_150 as cards

main = fixtures.server_main


class StackPacingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fixture = fixtures.AutoPassTests()
        self.s, self.p1, self.p2 = self.fixture.make_session()
        self.fixture.goto(self.s, "resolution_effects")
        self.s.rules_engine["autoSkipPhases"] = False
        self.frames = []
        self.ws = type("Peer", (), {"send": AsyncMock(side_effect=lambda raw: self.frames.append(json.loads(raw)))})()
        self.peers = patch.dict(main.connections, {self.ws: {"session": self.s, "playerId": "p1", "role": "player"}}, clear=True)
        self.peers.start()
        self.addCleanup(self.peers.stop)

    def stack(self, *immediates):
        self.s.rules_engine["actionStack"] = [{
            "id": str(i), "label": str(i), "kind": "triggered_effect",
            "controllerId": "p1", "source": {}, "targets": [], "immediate": immediate,
            "ability": {"result": {"kind": "score_owner", "value": i + 1}},
        } for i, immediate in enumerate(immediates)]

    async def test_ordinary_stack_publishes_lifo_intermediate_scores_and_waits(self):
        self.stack(False, False, False)
        with patch.object(main.asyncio, "sleep", new_callable=AsyncMock) as pause:
            await main.auto_advance_rules_phases(self.s, "p1")
        self.assertEqual([len(f["rulesEngine"]["actionStack"]) for f in self.frames], [2, 1, 0])
        self.assertEqual([f["players"]["p1"]["score"] for f in self.frames], [3, 5, 6])
        self.assertEqual([f["rulesEngine"]["lastResolvedAction"]["id"] for f in self.frames], ["2", "1", "0"])
        self.assertEqual(pause.await_count, 3)
        pause.assert_awaited_with(main.STACK_RESOLUTION_PAUSE_SECONDS)

    async def test_immediates_are_published_individually_before_normal_action(self):
        self.stack(False, True, True)
        with patch.object(main.asyncio, "sleep", new_callable=AsyncMock):
            await main.auto_advance_rules_phases(self.s, "p1")
        self.assertEqual([len(f["rulesEngine"]["actionStack"]) for f in self.frames], [2, 1, 0])
        self.assertEqual([f["players"]["p1"]["score"] for f in self.frames], [3, 5, 6])

    async def test_response_becoming_available_during_pause_stops_drain(self):
        self.stack(False, False)

        async def during_pause(_seconds):
            self.assertEqual(await main.auto_advance_rules_phases(self.s, "p2"), 0)
            self.p2["zones"]["hand"] = ["will-ephemeral", "m-5"]

        with patch.object(main.asyncio, "sleep", side_effect=during_pause):
            await main.auto_advance_rules_phases(self.s, "p1")
        self.assertEqual([a["id"] for a in self.s.rules_engine["actionStack"]], ["0"])
        self.assertEqual(len(self.frames), 1)
        self.assertFalse(self.s._auto_advance_running)

    async def test_cancelled_driver_releases_guard(self):
        self.stack(False, False)
        with patch.object(main.asyncio, "sleep", side_effect=asyncio.CancelledError):
            with self.assertRaises(asyncio.CancelledError):
                await main.auto_advance_rules_phases(self.s, "p1")
        self.assertFalse(self.s._auto_advance_running)
        self.assertEqual([a["id"] for a in self.s.rules_engine["actionStack"]], ["0"])

    async def test_reaction_auto_pass_resolves_strengthen_before_computing_winner(self):
        f = cards.SemanticBatch001150()
        self.s = f.world()
        # Replace the live peer's session with the real catalog scenario.
        main.connections[self.ws]["session"] = self.s
        self.s.rules_engine.update(priorityPlayerId="p1", autoSkipPhases=True)
        sermon = f.field(self.s, f.cid("Sermon, Obscene Quadrumane"), item="sermon")
        f.field(self.s, f.cid("Tong, the Expansive"), item="tong", owner="p2")
        will = f.cid("Strengthen")
        f.put(self.s, "p1", "hand", [will, "m2"])
        error, action = self.s.declare_rules_action("p1", "Strengthen", kind="play_card",
            source={"cardId": will, "zone": "hand"}, targets=[f.target(sermon)],
            payment_card_ids=["m2"], ability_id="strengthen-power-modifier")
        self.assertIsNone(error)
        # Both hands are now empty: auto-pass must drain the Stack first.
        async def after_resolution(_seconds):
            self.assertEqual(self.s.current_phase_id(), "confrontation_reaction")
            self.assertIsNone(self.s.rules_engine.get("confrontationResult"))
            self.assertEqual(self.s.rules_manifestation_characteristics(sermon)["power"], 8)

        with patch.object(main.asyncio, "sleep", side_effect=after_resolution):
            await main.auto_advance_rules_phases(self.s, "p1")
        self.assertEqual(self.s.current_phase_id(), "confrontation_reaction")
        self.assertEqual(self.s.rules_engine["actionStack"], [])
        self.assertIsNone(self.s.rules_engine.get("confrontationResult"))
        self.assertTrue(self.s.rules_confrontation_resolve_prompt())
        # Empty Stack confirmation, followed by the opponent's automatic pass.
        self.assertIsNone(await main.apply_rules_pass(self.s, self.s.rules_engine["priorityPlayerId"]))
        await main.auto_advance_rules_phases(self.s, "p1")
        comparisons = [e["details"] for e in self.s.log if e["type"] == "rules_confrontation_compared"]
        self.assertEqual(len(comparisons), 1)
        self.assertEqual(comparisons[0]["totals"], {"p1": 8, "p2": 6})
        self.assertEqual(comparisons[0]["winnerId"], "p1")

    async def test_finishing_immediate_choice_releases_deferred_normal_triggers(self):
        self.stack(False)
        normal = self.s.rules_engine["actionStack"].pop()
        self.s.rules_engine["deferredAfterImmediateActions"] = [normal]
        with patch.object(main.asyncio, "sleep", new_callable=AsyncMock):
            count = await main.resolve_and_record_rules_immediates(self.s, "p1")
        self.assertEqual(count, 0)
        self.assertEqual([a["id"] for a in self.s.rules_engine["actionStack"]], ["0"])
