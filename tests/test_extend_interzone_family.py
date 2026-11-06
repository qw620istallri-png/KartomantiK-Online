"""Strict contracts for Tong, the Expansive and Cozy Bunk capacity."""

import copy

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


EXTEND_INTERZONE_NAMES = (
    "Tong, the Expansive",
    "Cozy Bunk",
)

TONG = "5enwyodanyu1it8_en"
BUNK = "gybb0ktsth7clz5_en"

TONG_ABILITY = {
    "id": "interzone-gains-three-spaces",
    "passiveEffect": {"kind": "extend_interzone", "value": 3},
}

BUNK_ABILITY = {
    "id": "interzone-gains-one-space",
    "passiveEffect": {"kind": "extend_interzone", "value": 1},
}


class ExtendInterzoneFamily(RealCardRulesCase):
    ALL = (TONG, BUNK)

    def started(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker.update(
            index=ADVANCED_PHASES.index("confrontation_reaction"),
            turn=3,
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

    def source(self, card_id, *, owner="p1", zone="field", **extra):
        return self.field_item(
            f"source-{card_id}-{owner}", owner, card_id,
            field_zone=zone, **extra,
        )

    def test_both_compile_the_exact_printed_contract(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        self.assertEqual(self.ABILITIES[TONG], [TONG_ABILITY])
        self.assertEqual(self.ABILITIES[BUNK], [BUNK_ABILITY])
        self.assertEqual(
            rules[TONG]["passiveEffects"],
            [TONG_ABILITY["passiveEffect"]],
        )
        self.assertEqual(
            rules[BUNK]["passiveEffects"],
            [BUNK_ABILITY["passiveEffect"]],
        )

    def test_bonuses_are_additive_and_only_help_their_controller(self):
        session, _p1, _p2 = self.started()
        session.battlefield = [
            self.source(TONG, zone="confrontation"),
            self.source(BUNK),
        ]
        self.assertEqual(session.rules_interzone_capacity("p1"), 7)
        self.assertEqual(session.rules_interzone_capacity("p2"), 3)

        second_bunk = self.field_item(
            "second-bunk", "p1", BUNK, field_zone="field",
        )
        session.battlefield.append(second_bunk)
        self.assertEqual(session.rules_interzone_capacity("p1"), 8)

    def test_tong_works_anywhere_on_the_field_but_not_in_stalemate(self):
        for zone, support, expected in (
            ("confrontation", False, 6),
            ("confrontation", True, 6),
            ("interzone", False, 6),
            ("stalemate", False, 3),
        ):
            with self.subTest(zone=zone, support=support):
                session, _p1, _p2 = self.started()
                session.battlefield = [
                    self.source(TONG, zone=zone, isSupport=support),
                ]
                self.assertEqual(
                    session.rules_interzone_capacity("p1"), expected,
                )

    def test_inactive_or_blanked_sources_stop_extending_immediately(self):
        for card_id, active_capacity in ((TONG, 6), (BUNK, 4)):
            with self.subTest(card_id=card_id):
                session, _p1, _p2 = self.started()
                source = self.source(
                    card_id,
                    zone="confrontation" if card_id == TONG else "field",
                )
                session.battlefield = [source]
                self.assertEqual(
                    session.rules_interzone_capacity("p1"), active_capacity,
                )
                source["faceUp"] = False
                self.assertEqual(session.rules_interzone_capacity("p1"), 3)
                source["faceUp"] = True
                source["effectsDisabled"] = True
                self.assertEqual(session.rules_interzone_capacity("p1"), 3)
                source.pop("effectsDisabled")
                session.rules_engine["ongoingEffects"] = [{
                    "kind": "lose_effects",
                    "target": {"itemId": source["id"]},
                }]
                self.assertEqual(session.rules_interzone_capacity("p1"), 3)
                session.rules_engine["ongoingEffects"] = []
                session.battlefield.remove(source)
                self.assertEqual(session.rules_interzone_capacity("p1"), 3)

    def test_bonus_follows_current_control_not_immutable_ownership(self):
        for card_id, bonus in ((TONG, 3), (BUNK, 1)):
            with self.subTest(card_id=card_id):
                session, _p1, _p2 = self.started()
                source = self.source(
                    card_id,
                    zone="confrontation" if card_id == TONG else "field",
                    controllerId="p2",
                )
                session.battlefield = [source]
                self.assertEqual(session.rules_interzone_capacity("p1"), 3)
                self.assertEqual(
                    session.rules_interzone_capacity("p2"), 3 + bonus,
                )

    def test_cozy_bunk_real_play_opens_and_departure_closes_one_space(self):
        session, p1, _p2 = self.started()
        session.phase_tracker["index"] = ADVANCED_PHASES.index("end_actions")
        self.put(p1, "hand", [BUNK, "m-0", "m-1"])
        error, action = session.declare_rules_action(
            "p1",
            "Play Cozy Bunk",
            kind="play_card",
            source={"cardId": BUNK, "zone": "hand"},
            payment_card_ids=["m-0", "m-1"],
        )
        self.assertIsNone(error, error)
        self.assertIsNotNone(action)
        self.assertEqual(session.rules_interzone_capacity("p1"), 3)
        resolution = self.resolve_top(session)
        source = session.find_battlefield_item(
            resolution["action"]["sourceResolution"]["itemId"]
        )
        self.assertEqual(source["cardId"], BUNK)
        self.assertEqual(session.rules_interzone_capacity("p1"), 4)
        self.assertCountEqual(p1["zones"]["graveyard"], ["m-0", "m-1"])

        movement = session._rules_remove_field_item(
            source, "p1", "graveyard", "top",
        )
        self.assertEqual(movement["status"], "moved")
        self.assertEqual(session.rules_interzone_capacity("p1"), 3)

    def test_each_bonus_really_admits_exactly_its_printed_extra_spaces(self):
        for card_id, expected in ((TONG, 6), (BUNK, 4)):
            with self.subTest(card_id=card_id):
                session, p1, _p2 = self.started()
                source = self.source(
                    card_id,
                    zone="confrontation" if card_id == TONG else "field",
                )
                session.battlefield = [source]
                card_ids = [f"m-{index}" for index in range(expected + 1)]
                self.put(p1, "hand", card_ids)
                for index, entering_id in enumerate(card_ids[:expected]):
                    entered = session.place_rules_card_in_interzone(
                        "p1", "p1", "hand", entering_id,
                    )
                    self.assertIsNotNone(entered, index)
                self.assertEqual(
                    session.rules_interzone_slot_count("p1"), expected,
                )
                before = self.snapshot(session)
                self.assertIsNone(session.place_rules_card_in_interzone(
                    "p1", "p1", "hand", card_ids[-1],
                ))
                self.assertEqual(self.snapshot(session), before)

                session._rules_remove_field_item(
                    source, "p1", "graveyard", "top",
                )
                self.assertEqual(session.rules_interzone_capacity("p1"), 3)
                self.assertEqual(
                    session.rules_interzone_slot_count("p1"), expected,
                )
                self.assertIsNone(session.place_rules_card_in_interzone(
                    "p1", "p1", "hand", card_ids[-1],
                ))


if __name__ == "__main__":
    import unittest

    unittest.main()
