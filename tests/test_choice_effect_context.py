import test_game_state as game_tests
from session import ADVANCED_PHASES


class ChoiceEffectContextTests(game_tests.RealCardRulesCase):
    PIDUE = "inner-deserts-129"
    ALL = (PIDUE,)

    def triggered(self, temperament):
        session, p1, p2 = self.make_session()
        session.rules_engine.update(readyPlayerIds=["p1", "p2"], firstManifestationComplete=True, priorityPlayerId="p1")
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
        session.battlefield = [self.field_item("pidue", "p1", self.PIDUE, x=200, y=500, rotation=0), self.field_item("victim", "p2", "m-1", x=400, y=500, rotation=0)]
        session.card_rules["played"] = {"type": "ephemeral_will", "temperaments": [temperament]}
        self.put(p2, "hand", ["m-2", "m-3"])
        session.queue_rules_triggers(self.PIDUE, "p1", "card_played", event_card_id="played", item_id="pidue", face_up=True, event_controller_id="p2", controller_id="p1", defer=True, related_action={"source": {"cardId": "played", "zone": "hand", "ownerId": "p2"}})
        return session, p1, p2

    def test_target_choice_names_the_exact_pidue_branch_without_private_action_data(self):
        for temperament, expected in [("choleric", "pidue-choleric-weakens"), ("capricious", "pidue-capricious-silences"), ("melancholic", "pidue-melancholic-discards")]:
            with self.subTest(temperament=temperament):
                session, _, _ = self.triggered(temperament)
                choice = session.serialize_for("p1", "player")["rulesEngine"]["pendingChoice"]
                self.assertEqual(choice["kind"], "trigger_targets")
                self.assertEqual(choice["sourceAbilityId"], expected)
                self.assertNotIn("_triggerAction", choice)

    def test_discard_choice_keeps_the_resolving_branch_for_the_other_player(self):
        session, _, _ = self.triggered("melancholic")
        choice = session.rules_engine["pendingChoice"]
        error, _ = session.resolve_rules_choice("p1", choice["id"], targets=[{"kind": "player", "playerId": "p2"}])
        self.assertIsNone(error)
        session.resolve_rules_top_action()
        view = session.serialize_for("p2", "player")
        self.assertEqual(view["rulesEngine"]["pendingChoice"]["kind"], "discard_from_hand")
        self.assertEqual(view["rulesEngine"]["pendingChoice"]["sourceAbilityId"], "pidue-melancholic-discards")

    def test_simultaneous_order_distinguishes_pidue_branches(self):
        session, _, _ = self.triggered("vitreous")
        session.rules_engine["pendingChoice"] = None
        actions = []
        for key in ["pidue-vitreous-draws", "pidue-phlegmatic-token"]:
            actions.append({"id": key, "kind": "triggered_effect", "controllerId": "p1", "source": {"cardId": self.PIDUE}, "ability": {"id": key}})
        session.queue_rules_simultaneous_actions(actions)
        view = session.serialize_for("p1", "player")["rulesEngine"]["pendingChoice"]
        self.assertEqual({action["abilityId"] for action in view["actions"]}, {action["id"] for action in actions})
