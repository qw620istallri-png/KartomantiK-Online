import test_game_state as game_tests
from session import ADVANCED_PHASES


class LoopJigonTests(game_tests.RealCardRulesCase):
    LOOP = "1a8wzhi7xhbcenj_en"
    JIGON = "z6awx4mwwkfrvdd_en"
    HOURGLASS = "lmx5uff1z53fo0g_en"
    ALL = (LOOP, JIGON, HOURGLASS)

    def started(self, phase):
        session, p1, p2 = self.make_session()
        session.rules_engine.update(readyPlayerIds=["p1", "p2"], firstManifestationComplete=True, priorityPlayerId="p1")
        session.phase_tracker["index"] = ADVANCED_PHASES.index(phase)
        return session, p1, p2

    def test_loop_only_offers_its_delayed_effect_after_a_loss_this_turn(self):
        for outcome in ["win", "loss", "draw", "none", "old_loss", "cleared_loss"]:
            with self.subTest(outcome=outcome):
                session, p1, _ = self.started("end_triggers")
                self.put(p1, "graveyard", [self.HOURGLASS])
                turn = session.phase_tracker["turn"]
                session.create_rules_effect_memory("p1", self.HOURGLASS, "return_from_limbo_end_turn", controller_id="p1", data={"effectSourceCardId": self.LOOP, "optional": True, "requireLostConfrontation": True})
                if outcome in {"loss", "win", "draw", "old_loss"}:
                    session.rules_engine["confrontationResult"] = {"turn": turn - (outcome == "old_loss"), "winnerId": "p1" if outcome == "win" else None, "loserId": "p1" if outcome in {"loss", "old_loss"} else "p2" if outcome == "win" else None}
                if outcome == "cleared_loss":
                    session.rules_engine["confrontationLosses"] = {str(turn): "p1"}
                queued = session.queue_rules_end_turn_memory_triggers()
                if outcome in {"loss", "cleared_loss"}:
                    self.assertEqual(len(queued), 1)
                    self.assertEqual(session.rules_engine["pendingChoice"]["kind"], "optional_stack_action")
                else:
                    self.assertFalse(queued)
                    self.assertIsNone(session.rules_engine["pendingChoice"])
                    self.assertFalse(session.rules_engine["actionStack"])
                    self.assertFalse(session.rules_engine["effectMemories"])

    def test_other_delayed_returns_are_still_offered_without_a_loss(self):
        session, p1, _ = self.started("end_triggers")
        self.put(p1, "graveyard", [self.HOURGLASS])
        session.create_rules_effect_memory("p1", self.HOURGLASS, "return_from_limbo_end_turn", controller_id="p1", data={"optional": True})
        self.assertEqual(len(session.queue_rules_end_turn_memory_triggers()), 1)

    def test_jigons_hourglass_can_be_played_concealed_with_its_normal_or_free_tribute(self):
        for phase in ["end_actions"]:
            for free in [False, True]:
                with self.subTest(phase=phase, free=free):
                    session, p1, _ = self.started(phase)
                    hidden = self.field_item("hidden", "p1", self.HOURGLASS, "field", faceUp=False, concealedWill=True, concealedFree=free, jigonItemId="jigon", x=445, y=1300, rotation=0)
                    session.battlefield = [hidden]
                    source = {"cardId": self.HOURGLASS, "zone": "battlefield", "itemId": "hidden"}
                    if not free:
                        self.assertIsNotNone(session.declare_rules_action("p1", "Hourglass", kind="play_card", source=source)[0])
                        self.assertIn(hidden, session.battlefield)
                        session.add_rules_excess_essence("p1", [{"temperament": "vitreous", "amount": 2}, {"temperament": "capricious", "amount": 2}])
                    error, action = session.declare_rules_action("p1", "Hourglass", kind="play_card", source=source)
                    self.assertIsNone(error)
                    self.assertEqual(action["cost"]["tributeRequirements"], {} if free else {"vitreous": 2, "capricious": 2})
                    self.assertNotIn(hidden, session.battlefield)
                    result = session.resolve_rules_top_action()["action"]["sourceResolution"]
                    played = session.find_battlefield_item(result["itemId"])
                    self.assertTrue(played["faceUp"])
                    self.assertEqual(played["fieldZone"], "field")

    def test_free_concealed_hourglass_still_obeys_persistent_will_timing(self):
        for phase in ["confrontation_reaction", "confrontation_before_revelation"]:
            with self.subTest(phase=phase):
                session, _, _ = self.started(phase)
                hidden = self.field_item("hidden", "p1", self.HOURGLASS, "field", faceUp=False, concealedWill=True, concealedFree=True)
                session.battlefield = [hidden]
                error, _ = session.declare_rules_action("p1", "Hourglass", kind="play_card", source={"cardId": self.HOURGLASS, "zone": "battlefield", "itemId": "hidden"})
                self.assertIsNotNone(error)
                self.assertIn(hidden, session.battlefield)
