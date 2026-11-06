"""Strict contracts for Mourning Offal and Twin-headed Druid Support."""

import copy

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


CONDITIONAL_SUPPORT_NAMES = (
    "Mourning Offal",
    "Twin-headed Druid",
)

OFFAL = "k7bnhqhxkij5lsl_en"
DRUID = "ymsp3bnm3142ji3_en"

OFFAL_ABILITY = {
    "id": "mourning-offal-support-after-limbo-exit",
    "passiveEffect": {
        "kind": "conditional_support",
        "condition": "limbo_exit_this_turn",
    },
}

DRUID_ABILITY = {
    "id": "twin-headed-druid-support-after-loss",
    "passiveEffect": {
        "kind": "conditional_support",
        "condition": "lost_previous_confrontation",
    },
}


class ConditionalSupportFamily(RealCardRulesCase):
    ALL = (OFFAL, DRUID)

    def started(self, phase="confrontation_reaction", turn=3):
        session, p1, p2 = self.make_session()
        session.phase_tracker.update(
            index=ADVANCED_PHASES.index(phase),
            turn=turn,
        )
        session.rules_engine.update(
            readyPlayerIds=["p1", "p2"],
            firstManifestationComplete=True,
            firstManifestationTriggersQueued=True,
            priorityPlayerId="p1",
            actionStack=[],
            pendingChoice=None,
        )
        return session, p1, p2

    @staticmethod
    def snapshot(session):
        return copy.deepcopy((
            session.players,
            session.battlefield,
            session.rules_engine,
        ))

    def resolve_top(self, session):
        self.assertIsNone(session.pass_rules_priority("p2")[0])
        error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error, error)
        return resolution

    def assert_support_entry(self, card_id, origin, condition):
        session, p1, _p2 = self.started()
        condition(session)
        if origin == "hand":
            self.put(p1, "hand", [card_id])
            source = {"cardId": card_id, "zone": "hand"}
        else:
            item = self.field_item(
                "conditional", "p1", card_id, field_zone="interzone",
            )
            session.battlefield = [item]
            source = {
                "cardId": card_id,
                "zone": "battlefield",
                "itemId": item["id"],
            }
        error, action = session.declare_rules_action(
            "p1",
            "Conditional Support",
            kind="play_card",
            source=source,
            as_support=True,
        )
        self.assertIsNone(error, error)
        self.assertTrue(action["asSupport"])
        resolution = self.resolve_top(session)
        entered = session.find_battlefield_item(
            resolution["action"]["sourceResolution"]["itemId"]
        )
        self.assertEqual(
            (entered["cardId"], entered["fieldZone"], entered["isSupport"]),
            (card_id, "confrontation", True),
        )

    def test_both_compile_the_exact_printed_contract(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        self.assertEqual(self.ABILITIES[OFFAL], [OFFAL_ABILITY])
        self.assertEqual(self.ABILITIES[DRUID], [DRUID_ABILITY])
        self.assertEqual(rules[OFFAL]["passiveEffects"], [OFFAL_ABILITY["passiveEffect"]])
        self.assertEqual(rules[DRUID]["passiveEffects"], [DRUID_ABILITY["passiveEffect"]])
        self.assertEqual(rules[OFFAL]["supportCondition"], "limbo_exit_this_turn")
        self.assertEqual(rules[DRUID]["supportCondition"], "lost_previous_confrontation")

    def test_without_the_exact_history_neither_card_has_support(self):
        for card_id in (OFFAL, DRUID):
            with self.subTest(card_id=card_id):
                session, p1, _p2 = self.started()
                item = self.field_item("conditional", "p1", card_id, "interzone")
                session.battlefield = [item]
                self.put(p1, "hand", [card_id])
                self.assertFalse(session.rules_card_can_enter_support(item))
                self.assertIn(
                    "does not have Support from Hand",
                    session.rules_support_from_hand_error("p1", card_id),
                )
                self.assertNotIn(
                    card_id,
                    session.rules_conditional_support_hand_card_ids()["p1"],
                )
                before = self.snapshot(session)
                error, action = session.declare_rules_action(
                    "p1",
                    "No conditional Support",
                    kind="play_card",
                    source={"cardId": card_id, "zone": "hand"},
                    as_support=True,
                )
                self.assertIsNotNone(error)
                self.assertIsNone(action)
                self.assertEqual(self.snapshot(session), before)

    def test_offal_follows_any_real_limbo_exit_and_really_enters_support(self):
        def any_limbo_exit(session):
            p2 = session.players["p2"]
            self.put(p2, "graveyard", ["m-5"])
            error, _owner, _result = session.move_zone_card_by_effect(
                "p2", "graveyard", "p2", "hand", "m-5", "top",
            )
            self.assertIsNone(error, error)
            self.assertEqual(session.rules_engine["limboExitTurn"], 3)

        for origin in ("hand", "interzone"):
            with self.subTest(origin=origin):
                self.assert_support_entry(OFFAL, origin, any_limbo_exit)

    def test_playing_a_will_from_limbo_activates_offal_for_this_turn_only(self):
        session, p1, _p2 = self.started()
        self.put(p1, "graveyard", ["will-x"])
        session.rules_engine["playPermissions"] = [{
            "id": "play-from-limbo",
            "playerId": "p1",
            "fromZone": "graveyard",
            "cardId": "will-x",
            "noTribute": True,
            "exileOnLeave": True,
            "turn": 3,
            "phaseIds": ["confrontation_reaction"],
        }]
        error, _action = session.declare_rules_action(
            "p1",
            "Play Will from Limbo",
            kind="play_card",
            source={
                "cardId": "will-x",
                "zone": "graveyard",
                "containerId": "p1",
            },
        )
        self.assertIsNone(error, error)
        self.resolve_top(session)
        self.assertEqual(session.rules_engine["limboExitTurn"], 3)
        self.assertIn("will-x", p1["zones"]["exile"])

        item = self.field_item("offal", "p1", OFFAL, "interzone")
        session.battlefield = [item]
        self.put(p1, "hand", [OFFAL])
        self.assertTrue(session.rules_card_can_enter_support(item))
        self.assertIn(
            OFFAL,
            session.rules_conditional_support_hand_card_ids()["p1"],
        )
        session.phase_tracker["turn"] = 4
        self.assertFalse(session.rules_card_can_enter_support(item))
        self.assertNotIn(
            OFFAL,
            session.rules_conditional_support_hand_card_ids()["p1"],
        )

    def test_limbo_entry_reorder_failure_and_old_exit_do_not_activate_offal(self):
        session, p1, _p2 = self.started()
        item = self.field_item("offal", "p1", OFFAL, "interzone")
        session.battlefield = [item]
        self.put(p1, "graveyard", ["m-1", "m-2"])
        self.assertFalse(session.rules_card_can_enter_support(item))

        error, _owner = session.move_zone_card(
            "p1", "graveyard", "p1", "graveyard", "m-1", "bottom",
        )
        self.assertIsNone(error, error)
        self.assertFalse(session.rules_card_can_enter_support(item))
        self.assertIsNone(session.rules_engine["limboExitTurn"])

        before = self.snapshot(session)
        error, _owner, result = session.move_zone_card_by_effect(
            "p1", "graveyard", "p1", "hand", "missing", "top",
        )
        self.assertIsNotNone(error)
        self.assertIsNone(result)
        self.assertEqual(self.snapshot(session), before)

        session.rules_engine["limboExitTurn"] = 2
        self.assertFalse(session.rules_card_can_enter_support(item))

    def test_druid_requires_its_controllers_loss_on_exactly_the_previous_turn(self):
        session, _p1, _p2 = self.started(turn=4)
        item = self.field_item("druid", "p1", DRUID, "interzone")
        session.battlefield = [item]
        for losses, expected in (
            ({"4": "p1"}, False),
            ({"2": "p1"}, False),
            ({"3": "p2"}, False),
            ({"3": "p1"}, True),
        ):
            with self.subTest(losses=losses):
                session.rules_engine["confrontationLosses"] = losses
                self.assertEqual(
                    session.rules_card_can_enter_support(item), expected,
                )
        session.rules_engine["confrontationLosses"] = {}
        session.rules_engine["confrontationStalemates"] = {"3": True}
        self.assertFalse(session.rules_card_can_enter_support(item))

        item["controllerId"] = "p2"
        session.rules_engine["confrontationLosses"] = {"3": "p2"}
        self.assertTrue(session.rules_card_can_enter_support(item))

    def test_actual_previous_confrontation_loss_lets_druid_enter_support(self):
        def previous_loss(session):
            session.phase_tracker["index"] = ADVANCED_PHASES.index(
                "resolution_compare"
            )
            session.card_rules["m-0"]["power"] = 1
            session.card_rules["m-1"]["power"] = 3
            session.battlefield = [
                self.field_item("loser", "p1", "m-0", "confrontation"),
                self.field_item("winner", "p2", "m-1", "confrontation"),
            ]
            result = session.prepare_rules_confrontation_result()
            self.assertEqual((result["winnerId"], result["loserId"]), ("p2", "p1"))
            self.assertEqual(session.rules_engine["confrontationLosses"], {"3": "p1"})
            session.phase_tracker.update(
                index=ADVANCED_PHASES.index("confrontation_reaction"),
                turn=4,
            )
            session.rules_engine.update(
                confrontationResult=None,
                priorityPlayerId="p1",
                actionStack=[],
                pendingChoice=None,
            )
            session.battlefield = []

        for origin in ("hand", "interzone"):
            with self.subTest(origin=origin):
                session, p1, _p2 = self.started(turn=3)
                previous_loss(session)
                if origin == "hand":
                    self.put(p1, "hand", [DRUID])
                    source = {"cardId": DRUID, "zone": "hand"}
                else:
                    item = self.field_item("druid", "p1", DRUID, "interzone")
                    session.battlefield = [item]
                    source = {
                        "cardId": DRUID,
                        "zone": "battlefield",
                        "itemId": item["id"],
                    }
                error, _action = session.declare_rules_action(
                    "p1",
                    "Druid enters Support",
                    kind="play_card",
                    source=source,
                    as_support=True,
                )
                self.assertIsNone(error, error)
                resolution = self.resolve_top(session)
                entered = session.find_battlefield_item(
                    resolution["action"]["sourceResolution"]["itemId"]
                )
                self.assertTrue(entered["isSupport"])
                self.assertEqual(entered["cardId"], DRUID)


if __name__ == "__main__":
    import unittest

    unittest.main()
