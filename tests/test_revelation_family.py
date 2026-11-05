"""Strict Revelation-trigger contracts for six previously uncovered cards."""
import copy

from test_game_state import ADVANCED_PHASES, RealCardRulesCase


REVELATION_NAMES = (
    "The Stomper",
    "Numbi, the Irritating",
    "Sermon, Obscene Quadrumane",
    "Hermetic Hourglass",
    "Healing Bond",
    "Overwhelming Persuasion",
)

CARD_IDS = {
    "The Stomper": "om4qbiofb0ihq6p_en",
    "Numbi, the Irritating": "wer3o71zo9myece_en",
    "Sermon, Obscene Quadrumane": "ny6t2mdwbxfvwxw_en",
    "Hermetic Hourglass": "lmx5uff1z53fo0g_en",
    "Healing Bond": "inner-deserts-020",
    "Overwhelming Persuasion": "inner-deserts-120",
}

EXPECTED_CONTRACTS = {
    "The Stomper": (None, True, "force_win_if_highest_base_first"),
    "Numbi, the Irritating": ("interzone", False, "chain_from_zone"),
    "Sermon, Obscene Quadrumane": (
        None, True, "skip_confrontation_unless_points",
    ),
    "Hermetic Hourglass": (
        None, True, "stalemate_unless_opponent_pays",
    ),
    "Healing Bond": (None, False, "healing_bond"),
    "Overwhelming Persuasion": (None, False, "persuasion_force"),
}


class RevelationFamily(RealCardRulesCase):
    ALL = tuple(CARD_IDS.values())

    def revelation_ability(self, name):
        card_id = CARD_IDS[name]
        matches = [
            ability for ability in self.ABILITIES[card_id]
            if (ability.get("trigger") or {}).get("event") == "revelation"
        ]
        self.assertEqual(len(matches), 1, name)
        return card_id, matches[0]

    def fixture(self, name):
        card_id, ability = self.revelation_ability(name)
        session, p1, p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index(
            "confrontation_immediate"
        )
        session.card_rules["m-1"]["power"] = 4
        session.card_rules["m-2"]["power"] = 2
        source_zone = EXPECTED_CONTRACTS[name][0] or "field"
        source = self.field_item("source", "p1", card_id, source_zone)

        if name == "The Stomper":
            source["fieldZone"] = "confrontation"
            source["confrontationOrder"] = 1
            opponent = self.field_item(
                "theirs", "p2", "m-2", confrontationOrder=2,
            )
            session.battlefield = [source, opponent]
            session.rules_engine["firstManifestationItemIds"] = {
                "p1": "source", "p2": "theirs",
            }
        else:
            if name == "Hermetic Hourglass":
                session.card_rules["m-1"]["power"] = 1
                session.card_rules["m-2"]["power"] = 3
            mine = self.field_item(
                "mine", "p1", "m-1", confrontationOrder=1,
            )
            opponent = self.field_item(
                "theirs", "p2", "m-2", confrontationOrder=2,
            )
            session.battlefield = [source, mine, opponent]
            session.rules_engine["firstManifestationItemIds"] = {
                "p1": "mine", "p2": "theirs",
            }

        if name == "Numbi, the Irritating":
            self.put(p2, "hand", ["m-3", "will-x"])
        elif name == "Overwhelming Persuasion":
            self.put(p2, "hand", ["will-x", "m-3"])
        return card_id, ability, session, p1, p2, source

    @staticmethod
    def queued_action(session):
        queued = session.queue_rules_revelation_triggers(defer=True)
        if len(queued) != 1:
            raise AssertionError(f"expected one Revelation trigger, got {len(queued)}")
        return queued[0]

    def test_all_six_compile_the_exact_revelation_contract(self):
        self.assertEqual(len(REVELATION_NAMES), 6)
        for name in REVELATION_NAMES:
            with self.subTest(card=name):
                _card_id, ability = self.revelation_ability(name)
                zone, immediate, result_kind = EXPECTED_CONTRACTS[name]
                self.assertEqual(ability["trigger"]["event"], "revelation")
                self.assertEqual(ability["trigger"].get("zone"), zone)
                self.assertEqual(bool(ability.get("immediate")), immediate)
                self.assertEqual(ability["result"]["kind"], result_kind)

        _card_id, numbi = self.revelation_ability("Numbi, the Irritating")
        self.assertTrue(numbi["optional"])
        self.assertEqual(numbi["result"]["zone"], "hand")
        self.assertEqual(numbi["result"]["players"], "each_opponent")
        self.assertEqual(
            numbi["result"]["afterChain"],
            {"kind": "boost_controller_first", "value": 2},
        )
        _card_id, sermon = self.revelation_ability(
            "Sermon, Obscene Quadrumane"
        )
        self.assertEqual(sermon["result"]["points"], 10)
        _card_id, hourglass = self.revelation_ability("Hermetic Hourglass")
        self.assertEqual(hourglass["result"]["payment"], "{H}{H}")

    def test_each_live_face_up_source_queues_its_revelation_action(self):
        for name in REVELATION_NAMES:
            with self.subTest(card=name):
                card_id, ability, session, _p1, _p2, source = self.fixture(name)
                action = self.queued_action(session)
                self.assertEqual(action["ability"]["id"], ability["id"])
                self.assertEqual(action["source"]["cardId"], card_id)
                self.assertEqual(action["source"]["itemId"], source["id"])
                self.assertEqual(action["controllerId"], "p1")

    def test_hidden_disabled_absent_and_wrong_zone_sources_do_not_trigger(self):
        for name in REVELATION_NAMES:
            with self.subTest(hidden=name):
                _cid, _ability, session, _p1, _p2, source = self.fixture(name)
                source["faceUp"] = False
                before = copy.deepcopy((session.players, session.rules_engine))
                self.assertEqual(
                    session.queue_rules_revelation_triggers(defer=True), [],
                )
                self.assertEqual(session.players, before[0])
                self.assertEqual(session.rules_engine["actionStack"], [])

            with self.subTest(disabled=name):
                _cid, _ability, session, _p1, _p2, source = self.fixture(name)
                source["effectsDisabled"] = True
                self.assertEqual(
                    session.queue_rules_revelation_triggers(defer=True), [],
                )

            with self.subTest(absent=name):
                card_id, _ability, session, p1, _p2, source = self.fixture(name)
                session.battlefield.remove(source)
                self.put(p1, "hand", [card_id])
                self.assertEqual(
                    session.queue_rules_revelation_triggers(defer=True), [],
                )

        _cid, _ability, session, _p1, _p2, source = self.fixture(
            "Numbi, the Irritating"
        )
        source["fieldZone"] = "confrontation"
        self.assertEqual(session.queue_rules_revelation_triggers(defer=True), [])

    def test_each_card_specific_result_begins_after_the_valid_revelation(self):
        for name in REVELATION_NAMES:
            with self.subTest(card=name):
                _cid, _ability, session, _p1, p2, _source = self.fixture(name)
                action = self.queued_action(session)
                if name == "Numbi, the Irritating":
                    action["optionalAccepted"] = True
                before_p2_score = p2["score"]
                payload = session.apply_rules_action_result(action)

                if name == "The Stomper":
                    self.assertEqual(payload["status"], "forced")
                    self.assertEqual(
                        payload["confrontationResult"]["winnerId"], "p1",
                    )
                elif name == "Numbi, the Irritating":
                    self.assertEqual(payload["choiceKind"], "chain_manifestation")
                    self.assertEqual(payload["playerId"], "p2")
                    self.assertEqual(
                        session.rules_engine["pendingChoice"]["afterChain"],
                        {"kind": "boost_controller_first", "value": 2},
                    )
                elif name == "Sermon, Obscene Quadrumane":
                    self.assertEqual(
                        payload["choiceKind"], "skip_confrontation_payment",
                    )
                    self.assertEqual(payload["playerId"], "p2")
                    self.assertEqual(
                        session.rules_engine["pendingChoice"]["points"], 10,
                    )
                elif name == "Hermetic Hourglass":
                    self.assertEqual(
                        payload["choiceKind"], "immediate_effect_payment",
                    )
                    self.assertEqual(payload["playerId"], "p2")
                    self.assertEqual(
                        session.rules_engine["pendingChoice"]["requirements"],
                        {"hollow": 2},
                    )
                elif name == "Healing Bond":
                    self.assertEqual(payload["playerIds"], ["p2"])
                    self.assertEqual(self.power_of(session, "theirs"), 4)
                    self.assertEqual(p2["score"], before_p2_score + 10)
                elif name == "Overwhelming Persuasion":
                    self.assertEqual(payload["choiceKind"], "discard_from_hand")
                    self.assertEqual(payload["playerId"], "p2")
                    self.assertEqual(
                        session.rules_engine["pendingChoice"]["destination"],
                        "persuasion_place",
                    )


if __name__ == "__main__":
    import unittest

    unittest.main()
