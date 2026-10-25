"""Modifiers applied after card choices follow their printed lifetime."""

import copy

import test_game_state as game_tests
import test_stack_target_audit as target_tests


class ChoiceModifierLifetimeTests(game_tests.RealCardRulesCase):
    KANON = "inner-deserts-064"
    DULFER = "inner-deserts-104"
    SHATTERING = "k7dq8ye448xwj54_en"
    QUORUM = "201ug66mqu6gslx_en"
    ALL = (KANON, DULFER, SHATTERING, QUORUM)
    started = target_tests.StackTargetAuditTests.started
    target = staticmethod(target_tests.StackTargetAuditTests.target)

    def next_turn(self, session):
        session.phase_tracker["turn"] += 1
        session.phase_tracker["index"] = game_tests.ADVANCED_PHASES.index("recovery_start")
        session.prune_rules_ongoing_effects()

    def assert_permanent_until_target_leaves(self, session, target, expected):
        self.assertEqual(self.power_of(session, target["id"]), expected)
        self.next_turn(session)
        self.assertEqual(self.power_of(session, target["id"]), expected)
        session.battlefield.remove(target)
        session.prune_rules_ongoing_effects()
        session.battlefield.append(target)
        self.assertEqual(self.power_of(session, target["id"]), 6)

    def test_kanon_power_loss_survives_turn_and_source_departure(self):
        session, _, p2, first, _ = self.started()
        kanon = self.field_item("kanon", "p1", self.KANON, "interzone")
        session.battlefield.append(kanon)
        self.put(p2, "deck", ["will-x", self.SHATTERING, "m-5"])
        session.request_rules_draw("p2", 3, "p2")
        draw_choice = session.rules_engine["pendingChoice"]
        error, _ = session.resolve_rules_choice("p2", draw_choice["id"], card_ids=["will-x", self.SHATTERING])
        self.assertIsNone(error)
        distribution = session.rules_engine["pendingChoice"]
        error, _ = session.resolve_rules_choice("p1", distribution["id"], option={"itemIds": [first["id"], first["id"]]})
        self.assertIsNone(error)
        session.battlefield.remove(kanon)
        session.prune_rules_ongoing_effects()
        self.assert_permanent_until_target_leaves(session, first, 4)

    def test_dulfer_choice_power_loss_survives_turn(self):
        session, _, p2, first, _ = self.started()
        session.rules_engine["firstManifestationItemIds"] = {"p2": first["id"]}
        self.put(p2, "receptacle", {self.DULFER: "p1"})
        session.apply_rules_action_result({"id": "dulfer", "controllerId": "p1",
            "source": {"cardId": self.DULFER, "zone": "receptacle", "containerId": "p2"},
            "ability": copy.deepcopy(self.ABILITIES[self.DULFER][0])})
        choice = session.rules_engine["pendingChoice"]
        error, _ = session.resolve_rules_choice("p2", choice["id"], option="weaken_first")
        self.assertIsNone(error)
        self.assert_permanent_until_target_leaves(session, first, 4)

    def test_shattering_the_self_power_loss_survives_turn(self):
        session, _, p2, first, _ = self.started()
        self.put(p2, "deck", ["m-2", "will-x", "m-3"])
        session.apply_rules_action_result({"id": "shattering", "controllerId": "p1",
            "source": {"cardId": self.SHATTERING, "zone": "hand"},
            "targets": [{"kind": "player", "playerId": "p2"}, self.target(first)],
            "ability": copy.deepcopy(self.ABILITIES[self.SHATTERING][0])})
        self.assert_permanent_until_target_leaves(session, first, 4)

    def test_quorum_explicit_end_of_turn_bonus_still_expires(self):
        session, p1, _, _, _ = self.started()
        quorum = self.field_item("quorum", "p1", self.QUORUM)
        session.battlefield.append(quorum)
        self.put(p1, "hand", ["will-x"])
        base = self.power_of(session, quorum["id"])
        session.apply_rules_action_result({"id": "quorum", "controllerId": "p1", "optionalAccepted": True,
            "source": {"cardId": self.QUORUM, "itemId": quorum["id"], "zone": "battlefield"},
            "ability": copy.deepcopy(self.ABILITIES[self.QUORUM][0])})
        choice = session.rules_engine["pendingChoice"]
        error, _ = session.resolve_rules_choice("p1", choice["id"], card_ids=["will-x"])
        self.assertIsNone(error)
        self.assertEqual(self.power_of(session, quorum["id"]), base + 3)
        self.next_turn(session)
        self.assertEqual(self.power_of(session, quorum["id"]), base)
