import test_game_state as game_tests
from session import ADVANCED_PHASES


class HonorAndRespectTests(game_tests.RealCardRulesCase):
    CARD = "y4muuingw5y9l7z_en"
    ALL = (CARD,)

    def started(self, count=1, winner="p1", copies=1, **source_flags):
        session, p1, p2 = self.make_session()
        session.rules_engine.update(readyPlayerIds=["p1", "p2"], firstManifestationComplete=True, priorityPlayerId="p1", forcedConfrontationWinnerId=winner)
        session.phase_tracker["index"] = ADVANCED_PHASES.index("resolution_compare")
        session.battlefield = [self.field_item(f"mine-{i}", "p1", f"m-{i}") for i in range(count)]
        session.battlefield.append(self.field_item("foe", "p2", "m-9"))
        session.battlefield += [self.field_item(f"honor-{i}", "p1", self.CARD, "field", **source_flags) for i in range(copies)]
        return session, p1, p2

    def test_win_applies_ten_points_immediately_without_a_stack_action_or_choice(self):
        session, p1, _ = self.started()
        action = {"id": "existing", "controllerId": "p2"}
        session.rules_engine["actionStack"] = [action]
        priority = session.rules_engine["priorityPlayerId"]
        result = session.prepare_rules_confrontation_result()
        self.assertEqual(result["winnerId"], "p1")
        self.assertEqual(p1["score"], 10)
        self.assertEqual(session.rules_engine["actionStack"], [action])
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertEqual(session.rules_engine["priorityPlayerId"], priority)
        self.assertFalse(session.card_rules[self.CARD].get("triggeredAbilities"))
        self.assertFalse(session.queue_rules_confrontation_win_triggers())
        session.prepare_rules_confrontation_result()
        self.assertEqual(p1["score"], 10)
        logs = [entry for entry in session.log if entry["details"].get("automatic")]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["details"]["effectResult"]["delta"], 10)

    def test_no_bonus_with_multiple_manifestations_or_without_a_win(self):
        for count, winner in [(0, "p2"), (2, "p1"), (1, "p2"), (1, None)]:
            with self.subTest(count=count, winner=winner):
                session, p1, _ = self.started(count=count, winner=winner)
                if winner is None:
                    session.rules_engine["forcedConfrontationStalemate"] = True
                session.prepare_rules_confrontation_result()
                self.assertEqual(p1["score"], 0)

    def test_inactive_sources_do_not_apply_and_each_active_copy_applies_once(self):
        for flags in [{"effectsDisabled": True}, {"faceUp": False}]:
            with self.subTest(flags=flags):
                session, p1, _ = self.started(**flags)
                session.prepare_rules_confrontation_result()
                self.assertEqual(p1["score"], 0)
        session, p1, _ = self.started(copies=2)
        session.prepare_rules_confrontation_result()
        session.prepare_rules_confrontation_result()
        self.assertEqual(p1["score"], 20)

    def test_bonus_follows_the_controller_and_respects_point_gain_prevention(self):
        session, p1, p2 = self.started(winner="p2")
        session.find_battlefield_item("honor-0")["controllerId"] = "p2"
        session.prepare_rules_confrontation_result()
        self.assertEqual((p1["score"], p2["score"]), (0, 10))
        session, p1, _ = self.started()
        session.rules_points_changes_prevented = lambda: True
        session.prepare_rules_confrontation_result()
        self.assertEqual(p1["score"], 0)
