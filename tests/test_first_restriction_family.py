"""Strict contracts for the two remaining First Manifestation restrictions."""

import copy

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


FIRST_RESTRICTION_NAMES = (
    "Diabolical Giant",
    "Brioski, the Aerial",
)

CARD_IDS = {
    "Diabolical Giant": "0kcy08a6jd7ez7k_en",
    "Brioski, the Aerial": "inner-deserts-031",
}

GIANT_ABILITY = {
    "id": "lose-ten-to-gain-support",
    "oncePerTurnSupport": True,
    "immediate": True,
    "sourceZones": ["hand", "battlefield"],
    "sourceFieldZone": "interzone",
    "loseScore": 10,
    "targets": {"min": 0, "max": 0},
    "result": {"kind": "grant_source_support_until_end_turn"},
}


class FirstRestrictionFamily(RealCardRulesCase):
    ALL = tuple(CARD_IDS.values())

    def started(self, phase="confrontation_reaction", first_complete=True):
        session, p1, p2 = self.make_session()
        session.rules_engine.update(
            readyPlayerIds=["p1", "p2"],
            firstManifestationComplete=first_complete,
            firstManifestationTriggersQueued=first_complete,
            firstManifestationItemIds={},
            firstManifestationValidatedPlayerIds=[],
            priorityPlayerId="p1",
            actionStack=[],
            pendingChoice=None,
        )
        session.phase_tracker["index"] = ADVANCED_PHASES.index(phase)
        return session, p1, p2

    @staticmethod
    def snapshot(session):
        return copy.deepcopy((
            session.players, session.battlefield, session.rules_engine,
            session.phase_tracker,
        ))

    def activate_giant(self, session, source):
        return session.declare_rules_action(
            "p1", "Diabolical Giant gains Support",
            kind="activated_effect", source=source,
            ability_id=GIANT_ABILITY["id"], targets=[],
        )

    def resolve_top(self, session):
        self.assertIsNone(session.pass_rules_priority("p2")[0])
        error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error, error)
        return resolution

    def test_both_compile_the_exact_printed_contracts(self):
        giant = CARD_IDS["Diabolical Giant"]
        brioski = CARD_IDS["Brioski, the Aerial"]
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        self.assertEqual(self.ABILITIES[giant], [GIANT_ABILITY])
        self.assertEqual(rules[giant]["activatedAbilities"], [GIANT_ABILITY])
        self.assertFalse(rules[giant]["canBeFirstManifestation"])

        self.assertEqual(self.ABILITIES.get(brioski, []), [])
        self.assertEqual(rules[brioski]["activatedAbilities"], [])
        self.assertFalse(rules[brioski]["canBeFirstManifestation"])
        self.assertTrue(rules[brioski]["supportFromHand"])
        self.assertTrue(rules[brioski]["supportFromInterzone"])
        self.assertTrue(rules[brioski]["float"])

    def test_both_are_rejected_atomically_as_first_but_do_not_poison_the_hand(self):
        for name in FIRST_RESTRICTION_NAMES:
            with self.subTest(card=name):
                card_id = CARD_IDS[name]
                session, p1, _p2 = self.started(
                    "confrontation_choose", first_complete=False,
                )
                self.put(p1, "hand", [card_id])
                self.assertFalse(
                    session.rules_card_can_be_first_manifestation(card_id, "p1")
                )
                self.assertFalse(session.rules_opening_hand_is_playable("p1"))
                candidate = self.field_item(
                    f"first-{card_id}", "p1", card_id, faceUp=False,
                )
                before = self.snapshot(session)
                error = session.register_first_manifestation("p1", candidate)
                self.assertIn("first play", error)
                self.assertEqual(self.snapshot(session), before)

                self.put(p1, "hand", [card_id, "m-0"])
                self.assertTrue(session.rules_opening_hand_is_playable("p1"))
                ordinary = self.field_item("ordinary", "p1", "m-0", faceUp=False)
                self.assertIsNone(
                    session.register_first_manifestation("p1", ordinary)
                )
                self.assertEqual(
                    session.rules_engine["firstManifestationItemIds"],
                    {"p1": "ordinary"},
                )

    def test_giant_rejects_neighbor_phase_and_wrong_field_zone_without_payment(self):
        giant = CARD_IDS["Diabolical Giant"]
        session, p1, _p2 = self.started("end_actions")
        p1["score"] = 40
        self.put(p1, "hand", [giant])
        before = self.snapshot(session)
        error, action = self.activate_giant(
            session, {"cardId": giant, "zone": "hand"},
        )
        self.assertIn("current phase", error)
        self.assertIsNone(action)
        self.assertEqual(self.snapshot(session), before)

        session, p1, _p2 = self.started()
        p1["score"] = 40
        source = self.field_item(
            "giant", "p1", giant, field_zone="confrontation",
        )
        session.battlefield = [source]
        before = self.snapshot(session)
        error, action = self.activate_giant(session, {
            "cardId": giant, "zone": "battlefield", "itemId": "giant",
        })
        self.assertIn("field zone", error)
        self.assertIsNone(action)
        self.assertEqual(self.snapshot(session), before)

    def test_giant_pays_once_then_really_enters_support_from_hand_or_interzone(self):
        giant = CARD_IDS["Diabolical Giant"]
        for origin in ("hand", "interzone"):
            with self.subTest(origin=origin):
                session, p1, _p2 = self.started()
                p1["score"] = 40
                if origin == "hand":
                    self.put(p1, "hand", [giant])
                    source = {"cardId": giant, "zone": "hand"}
                else:
                    item = self.field_item(
                        "giant", "p1", giant, field_zone="interzone",
                    )
                    session.battlefield = [item]
                    source = {
                        "cardId": giant, "zone": "battlefield",
                        "itemId": "giant",
                    }
                error, action = self.activate_giant(session, source)
                self.assertIsNone(error, error)
                self.assertTrue(action["immediate"])
                self.assertEqual(action["ability"]["loseScore"], 10)
                self.assertEqual(p1["score"], 30)
                resolved = session.resolve_rules_immediate_actions()
                result = resolved[0]["action"]["effectResult"]
                self.assertEqual(result["status"], "granted")

                if origin == "hand":
                    self.assertTrue(
                        session.rules_support_from_hand_available("p1", giant)
                    )
                    permission = session.rules_engine["playPermissions"][-1]
                    self.assertEqual(
                        (permission["cardId"], permission["turn"],
                         permission["asSupport"]),
                        (giant, session.phase_tracker["turn"], True),
                    )
                    play_source = {"cardId": giant, "zone": "hand"}
                else:
                    self.assertEqual(
                        session.find_battlefield_item("giant")["supportUntilTurn"],
                        session.phase_tracker["turn"],
                    )
                    play_source = {
                        "cardId": giant, "zone": "battlefield",
                        "itemId": "giant",
                    }
                error, play = session.declare_rules_action(
                    "p1", "Play Giant in Support", kind="play_card",
                    source=play_source, as_support=True,
                )
                self.assertIsNone(error, error)
                self.assertEqual(p1["score"], 30)
                resolution = self.resolve_top(session)
                entered = session.find_battlefield_item(
                    resolution["action"]["sourceResolution"]["itemId"]
                )
                self.assertEqual(
                    (entered["cardId"], entered["fieldZone"], entered["isSupport"]),
                    (giant, "confrontation", True),
                )
                self.assertEqual(entered["supportUsedTurn"], session.phase_tracker["turn"])

    def test_brioski_really_enters_support_from_hand_and_interzone(self):
        brioski = CARD_IDS["Brioski, the Aerial"]
        for origin in ("hand", "interzone"):
            with self.subTest(origin=origin):
                session, p1, _p2 = self.started()
                if origin == "hand":
                    self.put(p1, "hand", [brioski])
                    source = {"cardId": brioski, "zone": "hand"}
                else:
                    item = self.field_item(
                        "brioski", "p1", brioski, field_zone="interzone",
                    )
                    session.battlefield = [item]
                    source = {
                        "cardId": brioski, "zone": "battlefield",
                        "itemId": "brioski",
                    }
                error, action = session.declare_rules_action(
                    "p1", "Play Brioski in Support", kind="play_card",
                    source=source, as_support=True,
                )
                self.assertIsNone(error, error)
                self.assertTrue(action["asSupport"])
                resolution = self.resolve_top(session)
                entered = session.find_battlefield_item(
                    resolution["action"]["sourceResolution"]["itemId"]
                )
                self.assertEqual(
                    (entered["cardId"], entered["fieldZone"], entered["isSupport"]),
                    (brioski, "confrontation", True),
                )

        session, p1, _p2 = self.started("end_actions")
        self.put(p1, "hand", [brioski])
        before = self.snapshot(session)
        error, action = session.declare_rules_action(
            "p1", "Too late", kind="play_card",
            source={"cardId": brioski, "zone": "hand"}, as_support=True,
        )
        self.assertIn("during Reaction", error)
        self.assertIsNone(action)
        self.assertEqual(self.snapshot(session), before)

    def test_brioski_float_shares_a_full_interzone_slot_on_cleanup(self):
        brioski = CARD_IDS["Brioski, the Aerial"]
        session, _p1, _p2 = self.started()
        entering = self.field_item(
            "brioski", "p1", brioski, field_zone="confrontation",
        )
        interzone = [
            self.field_item(
                f"slot-{index}", "p1", f"m-{index}",
                field_zone="interzone",
            )
            for index in range(3)
        ]
        session.battlefield = [*interzone, entering]
        session.rules_engine["confrontationResult"] = {
            "winnerId": "p1", "pendingOwnItemIds": ["brioski"],
            "status": "cleanup", "returned": [],
        }
        session.rules_engine["pendingChoice"] = {
            "id": "destination", "kind": "confrontation_destination",
            "playerId": "p1", "itemId": "brioski", "cardId": brioski,
            "options": ["interzone", "deck_bottom"],
        }
        error, result = session.resolve_rules_choice(
            "p1", "destination", option="interzone",
        )
        self.assertIsNone(error, error)
        self.assertEqual(result["destination"], "interzone")
        self.assertEqual(entering["stackedOn"], "slot-0")
        self.assertEqual(session.rules_interzone_slot_count("p1"), 3)
        self.assertTrue(session.rules_item_has_float(entering))


if __name__ == "__main__":
    import unittest

    unittest.main()
