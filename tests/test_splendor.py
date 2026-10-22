import test_game_state as game_tests
from session import ADVANCED_PHASES


class SplendorTests(game_tests.RealCardRulesCase):
    CARD = "inner-deserts-143"
    ABILITY = "splendor-spends-a-gem-as-excess-essence"
    ALL = (CARD,)

    def started(self):
        session, p1, p2 = self.make_session()
        session.rules_engine.update(readyPlayerIds=["p1", "p2"], firstManifestationComplete=True, priorityPlayerId="p1")
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
        item = self.field_item("gem", "p1", self.CARD, "field")
        session.battlefield = [item]
        return session, p1, item

    def test_arrival_is_one_stack_effect_that_adds_both_gems_then_chooses(self):
        session, _, item = self.started()
        queued = session.queue_rules_triggers(self.CARD, "p1", "enters_field", item_id="gem", face_up=True)
        self.assertEqual(len(queued), 1)
        self.assertEqual(len(session.rules_engine["actionStack"]), 1)
        self.assertFalse(session.rules_engine["pendingChoice"])
        self.assertFalse(item["counters"])
        session.resolve_rules_top_action()
        self.assertEqual(item["counters"], {"Gem": 2})
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "temperament_choice")
        self.assertEqual(len(choice["options"]), 5)
        self.assertIsNone(session.resolve_rules_choice("p1", choice["id"], option="choleric")[0])
        self.assertEqual(item["chosenTemperament"], "choleric")
        self.assertFalse(session.rules_engine["actionStack"])

    def test_conversion_preserves_stack_and_priority_and_exiles_after_last_gem(self):
        session, p1, item = self.started()
        item.update(counters={"Gem": 2}, chosenTemperament="choleric")
        action = {"id": "opponent-effect", "controllerId": "p2"}
        session.rules_engine["actionStack"] = [action]
        for remaining in [1, 0]:
            error, result = session.spend_rules_counter_essence("p1", "gem", self.ABILITY)
            self.assertIsNone(error)
            self.assertEqual(result["amount"], 1)
            self.assertEqual(item["counters"]["Gem"], remaining)
            self.assertEqual(session.rules_engine["actionStack"], [action])
            self.assertEqual(session.rules_engine["priorityPlayerId"], "p1")
        self.assertNotIn(item, session.battlefield)
        self.assertIn(self.CARD, p1["zones"]["exile"])

    def test_conversion_cannot_be_declared_as_a_stack_effect(self):
        session, _, item = self.started()
        item.update(counters={"Gem": 2}, chosenTemperament="choleric")
        error, _ = session.declare_rules_action("p1", "Gem", kind="activated_effect", source={"zone": "battlefield", "itemId": "gem", "cardId": self.CARD}, ability_id=self.ABILITY)
        self.assertIsNotNone(error)
        self.assertFalse(session.rules_engine["actionStack"])
        self.assertEqual(item["counters"]["Gem"], 2)
