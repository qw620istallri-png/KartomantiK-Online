"""Auto-pass invariants: phases, finite large Stacks, blocking choices and races.

Synthetic score effects isolate scheduling. The availability differential uses
real card definitions but is not certification of their printed effects.
"""
import asyncio
import copy
import unittest
from unittest.mock import patch

import test_auto_pass as fixtures
import test_semantic_batch_001_150 as cards
import card_scenario_batches as batches

main = fixtures.server_main
PHASES = fixtures.ADVANCED_PHASES


class AutoPhaseAudit(unittest.IsolatedAsyncioTestCase):
    make_session = fixtures.AutoPassTests.make_session
    goto = fixtures.AutoPassTests.goto

    @staticmethod
    def effect(key, value=1, immediate=False):
        return {"id": key, "label": key, "kind": "triggered_effect", "controllerId": "p1",
                "source": {}, "targets": [], "immediate": immediate,
                "ability": {"result": {"kind": "score_owner", "value": value}}}

    def started(self, count=0, phase="confrontation_reaction", auto=False):
        s, _, _ = self.make_session()
        self.goto(s, phase)
        s.phase_tracker["turn"] = 2
        s.rules_engine["autoSkipPhases"] = auto
        s.rules_engine["actionStack"] = [self.effect(f"effect-{n}") for n in range(count)]
        return s

    async def test_all_fifteen_steps_resolve_stack_before_any_phase_or_turn_change(self):
        for phase in PHASES:
            with self.subTest(phase=phase):
                s = self.started(phase=phase)
                s.rules_engine["actionStack"] = [self.effect("bottom", 1), self.effect("middle", 10), self.effect("top", 100)]
                seen = []
                original = main.record_rules_resolution

                async def record(session, result, actor):
                    seen.append((result["action"]["id"], len(session.rules_engine["actionStack"]), session.current_phase_id(), session.phase_tracker["turn"]))
                    await original(session, result, actor)

                with patch.object(main, "record_rules_resolution", side_effect=record):
                    await main.auto_advance_rules_phases(s, "p1")
                self.assertEqual(seen, [("top", 2, phase, 2), ("middle", 1, phase, 2), ("bottom", 0, phase, 2)])
                self.assertEqual(s.players["p1"]["score"], 111)
                self.assertEqual(s.current_phase_id(), phase)

    async def test_large_finite_normal_stacks_finish_without_a_new_player_message(self):
        for count in (32, 61):
            with self.subTest(count=count):
                s = self.started(count)
                await main.auto_advance_rules_phases(s, "p1")
                self.assertEqual(s.rules_engine["actionStack"], [])
                self.assertEqual(s.players["p1"]["score"], count)
                self.assertEqual(s.current_phase_id(), "confrontation_reaction")
                self.assertFalse(s._auto_advance_running)

    async def test_large_invalid_target_stack_finishes_without_skipping_the_phase(self):
        s = self.started(65)
        for action in s.rules_engine["actionStack"]:
            action["targets"] = [{"kind": "card", "itemId": "gone", "cardId": "m-1"}]
            action["ability"]["targets"] = {"min": 1, "max": 1, "cardType": "manifestation"}
        await main.auto_advance_rules_phases(s, "p1")
        self.assertEqual(s.rules_engine["actionStack"], [])
        self.assertEqual(s.players["p1"]["score"], 0)
        self.assertEqual(s.current_phase_id(), "confrontation_reaction")
        self.assertEqual(len([e for e in s.log if e["type"] == "rules_action_resolved"]), 65)

    async def test_empty_stack_at_exact_budget_boundary_still_advances_skippable_phases(self):
        s = self.started(30, phase="end_actions", auto=True)
        for pid in ("p1", "p2"):
            s.players[pid]["zones"]["hand"] = [f"m-{n}" for n in range(7)]
            s.players[pid]["zoneOwners"]["hand"] = {f"m-{n}": pid for n in range(7)}
        await main.auto_advance_rules_phases(s, "p1")
        self.assertEqual(s.rules_engine["actionStack"], [])
        self.assertEqual(s.players["p1"]["score"], 30)
        self.assertEqual(s.phase_tracker["turn"], 3)
        self.assertEqual(s.current_phase_id(), "confrontation_choose")

    async def test_manual_or_disabled_phase_tracker_never_auto_resolves_immediates(self):
        for disabled in ("rules", "phases"):
            with self.subTest(disabled=disabled):
                s = self.started()
                s.rules_engine["actionStack"] = [self.effect("immediate", immediate=True)]
                if disabled == "rules":
                    s.rules_engine["enabled"] = False
                else:
                    s.phase_tracker["enabled"] = False
                before = copy.deepcopy((s.players, s.rules_engine, s.phase_tracker))
                self.assertEqual(await main.auto_advance_rules_phases(s, "p1"), 0)
                self.assertEqual((s.players, s.rules_engine, s.phase_tracker), before)

    async def test_every_required_choice_blocks_normal_and_immediate_auto_resolution(self):
        kinds = ("discard_from_hand", "declare_card_name", "replacement_order", "simultaneous_stack_order",
                 "trigger_targets", "effect_payment", "hand_overflow", "confrontation_destination", "optional_stack_action")
        for kind in kinds:
            for immediate in (True, False):
                with self.subTest(kind=kind, immediate=immediate):
                    s = self.started(auto=True)
                    s.rules_engine["actionStack"] = [self.effect("waiting", immediate=immediate)]
                    s.rules_engine["pendingChoice"] = {"id": "wait", "kind": kind, "playerId": "p2"}
                    before = copy.deepcopy((s.players, s.rules_engine, s.phase_tracker))
                    self.assertEqual(await main.auto_advance_rules_phases(s, "p1"), 0)
                    self.assertEqual((s.players, s.rules_engine, s.phase_tracker), before)

    async def test_large_stack_stops_at_choice_then_resumes_the_remaining_cards(self):
        s = self.started(64)
        s.players["p2"]["zones"]["hand"] = ["m-1"]
        s.players["p2"]["zoneOwners"]["hand"] = {"m-1": "p2"}
        choice_action = self.effect("choice")
        choice_action.update(targets=[{"kind": "player", "playerId": "p2"}], ability={"result": {"kind": "discard_hand_target", "value": 1}})
        s.rules_engine["actionStack"].insert(32, choice_action)
        await main.auto_advance_rules_phases(s, "p1")
        self.assertEqual(len(s.rules_engine["actionStack"]), 32)
        choice = s.rules_engine["pendingChoice"]
        self.assertIsNotNone(choice)
        self.assertEqual(s.players["p1"]["score"], 32)
        self.assertIsNone(s.resolve_rules_choice("p2", choice["id"], card_ids=["m-1"])[0])
        await main.auto_advance_rules_phases(s, "p2")
        self.assertEqual(s.rules_engine["actionStack"], [])
        self.assertEqual(s.players["p1"]["score"], 64)
        self.assertEqual(s.current_phase_id(), "confrontation_reaction")

    async def test_concurrent_driver_cannot_resolve_a_second_card_during_first_publication(self):
        s = self.started(2)
        entered, release = asyncio.Event(), asyncio.Event()
        original = main.record_rules_resolution

        async def record(session, result, actor):
            await original(session, result, actor)
            if result["action"]["id"] == "effect-1":
                entered.set()
                await release.wait()

        with patch.object(main, "record_rules_resolution", side_effect=record):
            task = asyncio.create_task(main.auto_advance_rules_phases(s, "p1"))
            try:
                await asyncio.wait_for(entered.wait(), 2)
                self.assertEqual(await main.auto_advance_rules_phases(s, "p2"), 0)
                self.assertEqual(s.players["p1"]["score"], 1)
                self.assertEqual(len(s.rules_engine["actionStack"]), 1)
            finally:
                release.set()
                await task
        self.assertEqual(s.players["p1"]["score"], 2)

    async def test_newly_available_response_stops_a_large_stack_after_budget_boundary(self):
        s = self.started(33)
        original = main.record_rules_resolution

        async def record(session, result, actor):
            await original(session, result, actor)
            if len(session.rules_engine["actionStack"]) == 2:
                session.players["p2"]["zones"]["hand"] = ["will-ephemeral", "m-1"]

        with patch.object(main, "record_rules_resolution", side_effect=record):
            await main.auto_advance_rules_phases(s, "p1")
        self.assertEqual(len(s.rules_engine["actionStack"]), 2)
        self.assertEqual(s.players["p1"]["score"], 31)
        self.assertEqual(s.rules_engine["priorityPlayerId"], "p2")

    async def test_first_manifestation_and_recovery_mulligan_block_phase_skipping(self):
        for phase in ("confrontation_choose", "recovery_draw"):
            with self.subTest(phase=phase):
                s = self.started(phase=phase, auto=True)
                if phase == "confrontation_choose":
                    s.rules_engine["firstManifestationComplete"] = False
                else:
                    s.rules_engine.update(recoveryMulliganTurn=2, recoveryMulliganRequiredPlayerIds=["p2"])
                self.assertEqual(await main.auto_advance_rules_phases(s, "p1"), 0)
                self.assertEqual((s.current_phase_id(), s.phase_tracker["turn"]), (phase, 2))

    async def test_end_overflow_choices_finish_before_new_turn_and_recovery(self):
        s = self.started(phase="end_expire", auto=True)
        for pid in ("p1", "p2"):
            s.players[pid]["zones"]["hand"] = [f"m-{n}" for n in range(8)]
            s.players[pid]["zoneOwners"]["hand"] = {f"m-{n}": pid for n in range(8)}
        await main.auto_advance_rules_phases(s, "p1")
        for _ in range(2):
            choice = s.rules_engine["pendingChoice"]
            self.assertEqual(choice["kind"], "hand_overflow")
            self.assertEqual((s.current_phase_id(), s.phase_tracker["turn"]), ("end_expire", 2))
            self.assertEqual(await main.auto_advance_rules_phases(s, "p1"), 0)
            self.assertIsNone(s.resolve_rules_choice(choice["playerId"], choice["id"], card_ids=["m-0"])[0])
        await main.auto_advance_rules_phases(s, "p1")
        self.assertEqual(s.phase_tracker["turn"], 3)
        self.assertEqual(s.current_phase_id(), "confrontation_choose")
        self.assertIsNone(s.rules_engine["pendingChoice"])

    async def test_end_skip_is_individual_and_other_player_keeps_their_action(self):
        s = self.started(phase="end_actions", auto=True)
        s.rules_engine["skipEndPhaseTurns"] = {"p1": 2}
        s.players["p2"]["zones"]["hand"] = ["will-persistent", "m-1", "m-2"]
        await main.auto_advance_rules_phases(s, "p1")
        self.assertEqual(s.current_phase_id(), "end_actions")
        self.assertEqual(s.rules_engine["priorityPlayerId"], "p2")

    async def test_stopping_pass_all_restores_response_window_after_one_resolution(self):
        s = self.started(2)
        s.players["p2"]["zones"]["hand"] = ["will-ephemeral", "m-1"]
        s.set_rules_pass_all("p2", True)
        original = main.record_rules_resolution

        async def record(session, result, actor):
            await original(session, result, actor)
            session.set_rules_pass_all("p2", False)

        with patch.object(main, "record_rules_resolution", side_effect=record):
            await main.auto_advance_rules_phases(s, "p1")
        self.assertEqual(len(s.rules_engine["actionStack"]), 1)
        self.assertEqual(s.rules_engine["priorityPlayerId"], "p2")
        self.assertEqual(s.players["p1"]["score"], 1)

    async def test_grimoire_limbo_and_suspended_wills_preserve_real_response_windows(self):
        f = cards.SemanticBatch001150()
        will = f.cid("Strengthen")
        for phase in ("confrontation_reaction", "resolution_effects", "end_actions"):
            for origin in ("attached", "graveyard", "suspended"):
                with self.subTest(phase=phase, origin=origin):
                    s = f.world()
                    s.phase_tracker["index"] = PHASES.index(phase)
                    s.rules_engine.update(priorityPlayerId="p1", autoSkipPhases=True)
                    target = f.field(s, "m2", "target")
                    s.add_rules_excess_essence("p1", [{"temperament": "transcendent", "amount": 6}])
                    source = {"cardId": will, "zone": origin}
                    if origin == "attached":
                        host = f.field(s, f.cid("Grimoire"), "grimoire", zone="field")
                        host["attachedCards"] = [{"cardId": will, "ownerId": "p1"}]
                        source["itemId"] = host["id"]
                    elif origin == "graveyard":
                        s.put_zone_card("p1", "graveyard", will, "p1")
                        s.rules_engine["playPermissions"] = [{"id": "free-limbo", "playerId": "p1", "fromZone": "graveyard",
                            "cardId": will, "noTribute": True, "exileOnLeave": True, "turn": 2, "phaseIds": [phase]}]
                    else:
                        s.put_zone_card("p1", "hand", will, "p1")
                        error, entry = s.suspend_zone_card("p1", "hand", will, playableByPlayerId="p1", anyTemperamentTribute=True)
                        self.assertIsNone(error)
                        source["suspensionId"] = entry["id"]
                    self.assertTrue(s.rules_player_can_act("p1"))
                    self.assertEqual(await main.auto_advance_rules_phases(s, "p1"), 0)
                    error, _ = s.declare_rules_action("p1", "Strengthen", kind="play_card", source=source,
                        ability_id="strengthen-power-modifier", targets=[f.target(target)])
                    self.assertIsNone(error)

    async def test_concession_during_resolution_stops_all_remaining_automatic_work(self):
        s = self.started(64, auto=True)
        original = main.record_rules_resolution

        async def record(session, result, actor):
            await original(session, result, actor)
            session.concede("p2")

        with patch.object(main, "record_rules_resolution", side_effect=record):
            await main.auto_advance_rules_phases(s, "p1")
        self.assertTrue(s.ended)
        self.assertEqual(s.players["p1"]["score"], 1)
        self.assertEqual(s.phase_tracker["turn"], 2)
        self.assertFalse(s._auto_advance_running)

    def test_catalogue_accepted_declarations_are_never_mistaken_for_no_action(self):
        checked, accepted = 0, 0
        for cid, abilities in batches.main.CARD_ABILITIES.items():
            for ability in abilities:
                if any(ability.get(k) for k in ("trigger", "passiveEffect", "playPermission")):
                    continue
                s, actor, source, targets, cost = batches.prepare_action(cid, ability)
                can_act = s.rules_player_can_act(actor)
                error, _ = s.declare_rules_action(actor, ability["id"], kind=ability.get("action") or "activated_effect",
                    source=source, targets=targets, ability_id=ability["id"], payment_card_ids=[], cost_card_id=cost,
                    extra_essence_count=1 if ability.get("optionalExtraEssence") else 0,
                    as_support=bool(s.card_rules[cid].get("type") == "manifestation" and ability.get("action") == "play_card"), placement={"x": 0, "y": 0})
                checked += 1
                if error is None:
                    accepted += 1
                    with self.subTest(card=cid, ability=ability["id"], phase=s.current_phase_id()):
                        self.assertTrue(can_act)
        self.assertEqual(checked, 182)
        self.assertGreaterEqual(accepted, 180)


if __name__ == "__main__":
    unittest.main()
