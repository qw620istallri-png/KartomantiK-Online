"""Game completion must stop pending effects and choices without changing scoring rules."""
import copy

import test_game_state as game_tests


class TerminalStateAuditTests(game_tests.RealCardRulesCase):
    ALL = ("inner-deserts-143",)

    def started(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker["index"] = game_tests.ADVANCED_PHASES.index("confrontation_reaction")
        session.rules_engine.update(readyPlayerIds=["p1", "p2"], firstManifestationComplete=True, priorityPlayerId="p1")
        return session, p1, p2

    @staticmethod
    def action(immediate=False):
        return {"id": "after-end", "kind": "triggered_effect", "controllerId": "p1", "source": {},
            "immediate": immediate, "ability": {"id": "after-end", "result": {"kind": "score_owner", "value": 50}}}

    def test_concession_stops_stack_resolution_but_preserves_the_final_field(self):
        for immediate in (True, False):
            with self.subTest(immediate=immediate):
                session, p1, _ = self.started()
                session.battlefield = [self.field_item("final-card", "p1", "m-1")]
                session.rules_engine["actionStack"] = [self.action(immediate)]
                session.concede("p2")
                before = copy.deepcopy((session.players, session.battlefield, session.tokens, session.rules_engine))
                if immediate:
                    self.assertEqual(session.resolve_rules_immediate_actions(), [])
                else:
                    self.assertIsNone(session.resolve_rules_top_action())
                self.assertEqual((session.players, session.battlefield, session.tokens, session.rules_engine), before)
                self.assertEqual(p1["score"], 0)

    def test_concession_cancels_choices_and_continuations_without_discarding_cards(self):
        session, p1, _ = self.started()
        self.put(p1, "hand", ["m-2"])
        session.rules_engine.update(pendingChoice={"id": "old", "kind": "optional_stack_action", "playerId": "p1"},
            deferredSimultaneousActions=[{**self.action(), "optional": True}],
            deferredAfterImmediateActions=[self.action()],
            pendingChainSequences=[{"controllerId": "p1", "players": ["p1"], "result": {"kind": "chain_from_zone", "zone": "hand"}, "action": self.action()}],
            observedEvents=[{"kind": "points_gained", "playerId": "p1"}])
        session.concede("p2")
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertEqual(session.flush_rules_deferred_simultaneous_actions(), [])
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertEqual(session.rules_engine["priorityPlayerId"], None)
        for key in ("deferredSimultaneousActions", "deferredAfterImmediateActions", "pendingChainSequences", "observedEvents"):
            self.assertEqual(session.rules_engine[key], [])
        self.assertEqual(p1["zones"]["hand"], ["m-2"])

    def test_recovery_completion_from_a_choice_does_not_reopen_a_deferred_prompt(self):
        session, p1, p2 = self.started()
        session.phase_tracker.update(index=game_tests.ADVANCED_PHASES.index("recovery_draw"), turn=2)
        for player in (p1, p2):
            self.put(player, "deck", [])
            self.put(player, "hand", [])
        session.rules_engine["pendingChoice"] = {"id": "recovery", "kind": "binary_choice", "purpose": "quasimillenary",
            "playerId": "p1", "options": ["yes", "no"], "handLimit": 7}
        session.rules_engine["deferredSimultaneousActions"] = [{**self.action(), "optional": True}]
        error, result = session.resolve_rules_choice("p1", "recovery", option="no")
        self.assertIsNone(error)
        self.assertTrue(session.ended)
        self.assertEqual(result["recovery"]["outcome"]["reason"], "incomplete_recovery_hand")
        session.flush_rules_deferred_simultaneous_actions()
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertIsNone(session.rules_engine["priorityPlayerId"])

    def test_new_internal_batches_cannot_open_choices_after_the_game_ends(self):
        session, _, _ = self.started()
        session.concede("p2")
        session.queue_rules_simultaneous_actions([{**self.action(), "optional": True}])
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertEqual(session.rules_engine["actionStack"], [])
        self.assertIsNone(session.apply_rules_action_result(self.action()))

    def test_a_stale_payment_choice_cannot_spend_resources_after_completion(self):
        session, p1, _ = self.started()
        self.put(p1, "hand", ["m-2"])
        session.concede("p2")
        session.rules_engine["pendingChoice"] = {"id": "stale", "kind": "effect_payment", "playerId": "p1", "payment": "{H}"}
        before = copy.deepcopy((session.players, session.tokens, session.rules_engine))
        error, _ = session.resolve_rules_choice("p1", "stale", option="pay", card_ids=["m-2"])
        self.assertIsNotNone(error)
        self.assertEqual((session.players, session.tokens, session.rules_engine), before)

    def test_points_and_payments_do_not_introduce_a_new_mid_effect_victory_threshold(self):
        session, p1, _ = self.started()
        session.adjust_rules_score("p1", 1000)
        self.assertFalse(session.ended)
        result = session.apply_rules_action_result(self.action())
        self.assertIsNotNone(result)
        self.assertEqual(p1["score"], 1050)
        session.adjust_rules_score("p1", -2000)
        self.assertFalse(session.ended)
