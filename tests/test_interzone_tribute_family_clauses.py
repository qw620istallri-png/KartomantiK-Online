"""Printed contracts for the ten shared Interzone Tribute cards."""
import re
import unittest

import main
from session import ADVANCED_PHASES, Session


END_PHASE_FAMILY = (
    "Flem",
    "Viter",
    "Mal",
    "Capry",
    "Chol",
)
FIXED_TWO_FAMILY = (
    "Faroc-Ko, the Insipid",
    "Philfer, the Sharp",
    "Quasimolg, the Hunched",
    "Proboscidon, the Boor",
    "Orzo, the Greatmace",
)


class InterzoneTributeFamilyClauses(unittest.TestCase):
    def card(self, name):
        return next(card for card in main.CARD_DATA if card["name"] == name)

    def session(self):
        session = Session(
            card_points=main.CARD_POINTS,
            card_labels=main.CARD_LABELS,
            manifestation_ids=main.CARD_MANIFESTATION_IDS,
            card_rules=main.CARD_RULES,
            rules_beta=True,
        )
        for seat, player_id in enumerate(("p1", "p2")):
            session.get_or_create_player(
                player_id, player_id.upper(), seat=seat
            )
        session.rules_engine.update({
            "deckConfirmedPlayerIds": ["p1", "p2"],
            "readyPlayerIds": ["p1", "p2"],
            "firstManifestationComplete": True,
            "priorityPlayerId": "p1",
        })
        return session

    @staticmethod
    def interzone_item(card_id, item_id="tribute"):
        return {
            "id": item_id,
            "cardId": card_id,
            "ownerId": "p1",
            "controllerId": "p1",
            "faceUp": True,
            "fieldZone": "interzone",
            "x": 0,
            "y": 0,
            "rotation": 0,
            "counters": {},
            "stackedOn": None,
        }

    @staticmethod
    def symbol(card):
        return re.findall(r"\{([A-Z])\}", card["powerCost"])[0]

    def payment(self, card, zone, amount):
        session = self.session()
        symbol = self.symbol(card)
        if zone == "hand":
            session.put_zone_card("p1", "hand", card["id"], "p1")
            reference = card["id"]
        else:
            session.battlefield.append(
                self.interzone_item(card["id"])
            )
            reference = "battlefield|tribute"
        return session.rules_action_payment(
            "p1", "activated_effect", None, [reference],
            {"tribute": f"{{{symbol}}}" * amount},
        )

    def test_family_text_and_compilation_are_exact(self):
        for name in END_PHASE_FAMILY:
            with self.subTest(card=name):
                card = self.card(name)
                rules = main.CARD_RULES[card["id"]]
                self.assertEqual(
                    card["effect"].splitlines(),
                    [
                        f"In the End Phase, {name} can be played into the Interzone.",
                        f"{name} can be used as tribute from the Interzone.",
                    ],
                )
                self.assertTrue(rules["endPhaseInterzonePlay"])
                self.assertTrue(rules["canPayTributeFromInterzone"])
                self.assertIsNone(rules["tributePowerOverride"])
                self.assertEqual(rules["power"], 1)
        for name in FIXED_TWO_FAMILY:
            with self.subTest(card=name):
                card = self.card(name)
                rules = main.CARD_RULES[card["id"]]
                self.assertEqual(len(card["effect"].splitlines()), 2)
                self.assertIn(
                    "Can be used as tribute from the Interzone.",
                    card["effect"],
                )
                self.assertIn(
                    "considered to have a base power of",
                    card["effect"],
                )
                self.assertTrue(rules["canPayTributeFromInterzone"])
                self.assertEqual(rules["interzoneTributePower"], 2)
                self.assertEqual(
                    rules["tributePowerOverride"],
                    {"power": 2, "condition": None},
                )
                self.assertEqual(rules["power"], 5)

    def test_end_phase_family_has_exact_timing_and_printed_interzone_tribute(self):
        for name in END_PHASE_FAMILY:
            with self.subTest(card=name):
                card = self.card(name)
                session = self.session()
                session.put_zone_card("p1", "hand", card["id"], "p1")
                for phase in (
                    "recovery_end",
                    "confrontation_choose",
                    "resolution_effects",
                ):
                    session.phase_tracker["index"] = ADVANCED_PHASES.index(
                        phase
                    )
                    self.assertIn(
                        "End Phase",
                        session.rules_support_from_hand_error(
                            "p1", card["id"]
                        ),
                    )
                session.phase_tracker["index"] = ADVANCED_PHASES.index(
                    "end_actions"
                )
                self.assertIsNone(
                    session.rules_support_from_hand_error(
                        "p1", card["id"]
                    )
                )
                session.rules_engine["priorityPlayerId"] = "p2"
                self.assertEqual(
                    session.rules_support_from_hand_error(
                        "p1", card["id"]
                    ),
                    "You do not have priority.",
                )
                session.rules_engine["priorityPlayerId"] = "p1"
                session.rules_engine["actionStack"] = [{"id": "pending"}]
                self.assertIn(
                    "Stack",
                    session.rules_support_from_hand_error(
                        "p1", card["id"]
                    ),
                )
                error, _payment = self.payment(card, "interzone", 1)
                self.assertIsNone(error)
                error, _payment = self.payment(card, "interzone", 2)
                self.assertIsNotNone(error)

    def test_fixed_two_family_is_worth_two_from_hand_and_interzone_not_five(self):
        for name in FIXED_TWO_FAMILY:
            for zone in ("hand", "interzone"):
                with self.subTest(card=name, zone=zone):
                    card = self.card(name)
                    error, payment = self.payment(card, zone, 2)
                    self.assertIsNone(error)
                    self.assertEqual(
                        sum(payment["requirements"].values()), 2
                    )
                    self.assertEqual(payment["excessEssence"], [])
                    error, _payment = self.payment(card, zone, 3)
                    self.assertIsNotNone(error)


if __name__ == "__main__":
    unittest.main()
