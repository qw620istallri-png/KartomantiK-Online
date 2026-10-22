from test_game_state import ADVANCED_PHASES, RealCardRulesCase


class StomperTests(RealCardRulesCase):
    STOMPER = "om4qbiofb0ihq6p_en"
    ALL = (STOMPER,)

    def revelation(self, opposing_power, opposing_temperament="phlegmatic"):
        session, _, _ = self.make_session()
        session.card_rules["m-0"].update(
            power=opposing_power, temperaments=[opposing_temperament],
        )
        session.battlefield = [
            self.field_item("stomper", "p1", self.STOMPER),
            self.field_item("other", "p2", "m-0"),
        ]
        session.rules_engine["firstManifestationItemIds"] = {
            "p1": "stomper", "p2": "other",
        }
        session.phase_tracker["index"] = ADVANCED_PHASES.index(
            "confrontation_immediate"
        )
        return session

    def test_equal_base_power_does_not_trigger_even_when_dominant(self):
        for temperament in ("choleric", "capricious", "transcendent"):
            with self.subTest(temperament=temperament):
                session = self.revelation(4, temperament)
                if temperament == "choleric":
                    self.assertEqual(session.rules_temperament_winner("capricious", temperament), 0)
                session.battlefield[0]["counters"]["power"] = 2
                self.assertEqual(session.queue_rules_revelation_triggers(), [])
                self.assertEqual(session.resolve_rules_immediate_actions(), [])
                self.assertIsNone(session.rules_engine.get("forcedConfrontationWinnerId"))
                self.assertEqual(session.current_phase_id(), "confrontation_immediate")

    def test_strictly_higher_base_triggers_despite_opposing_power_bonus(self):
        session = self.revelation(3)
        session.battlefield[1]["counters"]["power"] = 10
        actions = session.queue_rules_revelation_triggers()
        self.assertEqual(len(actions), 1)
        resolved = session.resolve_rules_immediate_actions()
        result = resolved[0]["action"]["effectResult"]
        self.assertEqual(result["status"], "forced")
        self.assertEqual(result["confrontationResult"]["winnerId"], "p1")

    def test_lower_base_does_not_trigger_despite_own_power_bonus(self):
        session = self.revelation(5)
        session.battlefield[0]["counters"]["power"] = 10
        self.assertEqual(session.queue_rules_revelation_triggers(), [])

    def test_support_stomper_does_not_trigger(self):
        session = self.revelation(3)
        session.battlefield.append(self.field_item("first", "p1", "m-1"))
        session.rules_engine["firstManifestationItemIds"]["p1"] = "first"
        self.assertEqual(session.queue_rules_revelation_triggers(), [])

    def test_resolution_cannot_force_a_win_on_equal_base_power(self):
        session = self.revelation(4)
        result = session.apply_rules_action_result({
            "controllerId": "p1",
            "source": {"cardId": self.STOMPER, "itemId": "stomper"},
            "ability": {"result": {"kind": "force_win_if_highest_base_first"}},
        })
        self.assertEqual(result["status"], "condition_failed")
        self.assertIsNone(session.rules_engine.get("forcedConfrontationWinnerId"))
