import test_game_state as game_tests
from session import ADVANCED_PHASES


class SandokaronTests(game_tests.RealCardRulesCase):
    CARD = "inner-deserts-114"
    ALL = (CARD,)

    def started(self, banners=1):
        session, p1, p2 = self.make_session()
        session.rules_engine.update(readyPlayerIds=["p1", "p2"], firstManifestationComplete=True, priorityPlayerId="p1")
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
        source = self.field_item("sando", "p1", self.CARD, "interzone", counters={"Banner": banners})
        session.battlefield = [source, self.field_item("mine", "p1", "m-1"), self.field_item("theirs", "p2", "m-2")]
        return session, p1, source

    def test_entering_and_confrontation_results_change_banners_without_an_activation_choice(self):
        for won in [True, False]:
            with self.subTest(won=won):
                session, _, source = self.started(banners=0)
                session.queue_rules_battlefield_entry_triggers(self.CARD, "p1", "sando", True)
                self.assertIsNone(session.rules_engine["pendingChoice"])
                session.resolve_rules_top_action()
                self.assertEqual(source["counters"]["Banner"], 1)
                session.rules_engine["confrontationResult"] = {"turn": session.phase_tracker["turn"], "winnerId": "p1" if won else "p2", "loserId": "p2" if won else "p1", "participantItemIds": ["mine", "theirs"]}
                queued = session.queue_rules_confrontation_win_triggers()
                self.assertEqual(len(queued), 1)
                self.assertFalse(queued[0].get("optional"))
                self.assertIsNone(session.rules_engine["pendingChoice"])
                session.resolve_rules_top_action()
                self.assertEqual(source["counters"]["Banner"], 2 if won else 0)

    def test_each_banner_mode_spends_one_counter_and_exile_waits_for_end_of_turn(self):
        for mode in ["power", "essence"]:
            with self.subTest(mode=mode):
                session, p1, source = self.started()
                target = session.find_battlefield_item("mine")
                base = session.rules_manifestation_characteristics(target)["power"]
                targets = [{"kind": "card", "itemId": "mine", "cardId": "m-1"}] if mode == "power" else []
                error, _ = session.declare_rules_action("p1", "Spend 1 Banner", kind="activated_effect", source={"cardId": self.CARD, "zone": "battlefield", "itemId": "sando"}, ability_id=f"sandokaron-banner-{mode}", targets=targets)
                self.assertIsNone(error)
                self.assertEqual(source["counters"]["Banner"], 0)
                session.resolve_rules_top_action()
                self.assertIn(source, session.battlefield)
                if mode == "power":
                    self.assertEqual(session.rules_manifestation_characteristics(target)["power"], base + 3)
                else:
                    self.assertEqual(sum(token["counters"]["essence"] for token in session.tokens if token.get("temperament") == "choleric"), 2)
                session.phase_tracker["index"] = ADVANCED_PHASES.index("end_triggers")
                queued = session.build_rules_end_turn_field_triggers()
                self.assertEqual([action["ability"]["id"] for action in queued], ["sandokaron-exile-without-banner"])
                session.queue_rules_simultaneous_actions(queued)
                self.assertIsNone(session.rules_engine["pendingChoice"])
                session.resolve_rules_top_action()
                self.assertNotIn(source, session.battlefield)
                self.assertIn(self.CARD, p1["zones"]["exile"])
