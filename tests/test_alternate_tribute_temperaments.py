"""Printed contracts for manifestations with alternate Tribute temperaments."""
import copy
import unittest

import main
from session import Session


SYMBOLS = {
    "choleric": "R",
    "phlegmatic": "G",
    "vitreous": "B",
    "melancholic": "P",
    "capricious": "Y",
    "hollow": "H",
}

ALTERNATE_TRIBUTE_CONTRACTS = {
    "Slumber Planner": ("phlegmatic", "vitreous"),
    "Tidying Torment": ("phlegmatic", "melancholic"),
    "Scrutinizing Figure": ("vitreous", "melancholic"),
    "Witty Scribe": ("vitreous", "capricious"),
    "Skin-shifting Tearer": ("melancholic", "choleric"),
    "Ridiculous Persecutor": ("melancholic", "capricious"),
    "Exalted Jester": ("capricious", "choleric"),
    "Peevish Sapling": ("capricious", "phlegmatic"),
    "Shimmering Seaguide": ("choleric", "vitreous"),
    "Blunt Leaf": ("choleric", "phlegmatic"),
    "Rocky Heartcrystal": ("hollow", "transcendent"),
}


class AlternateTributeTemperaments(unittest.TestCase):
    @staticmethod
    def card(name):
        return next(card for card in main.CARD_DATA if card["name"] == name)

    def make_session(self, name, power_cost):
        card = self.card(name)
        card_id = card["id"]
        rules = {
            card_id: copy.deepcopy(main.CARD_RULES[card_id]),
            "test-will": {
                "type": "ephemeral_will",
                "cost": 1,
                "powerCost": power_cost,
                "temperaments": ["phlegmatic"],
            },
        }
        session = Session(
            rules_beta=True,
            manifestation_ids={card_id},
            card_rules=rules,
        )
        player = session.get_or_create_player("p1", "P1", seat=0)
        session.get_or_create_player("p2", "P2", seat=1)
        session.rules_engine["deckConfirmedPlayerIds"] = ["p1", "p2"]
        session.rules_engine["priorityPlayerId"] = "p1"
        session.phase_tracker["index"] = 1
        player["zones"]["hand"] = ["test-will", card_id]
        player["zoneOwners"]["hand"] = {
            "test-will": "p1",
            card_id: "p1",
        }
        return session, player, card

    def declare_with(self, name, power_cost):
        session, player, card = self.make_session(name, power_cost)
        error, action = session.declare_rules_action(
            "p1",
            f"Tribute with {name}",
            kind="play_card",
            source={"cardId": "test-will", "zone": "hand"},
            payment_card_ids=[card["id"]],
        )
        return error, action, session, player, card

    def test_all_eleven_compile_the_exact_printed_tribute_contract(self):
        self.assertEqual(len(ALTERNATE_TRIBUTE_CONTRACTS), 11)
        for name, (printed, alternate) in ALTERNATE_TRIBUTE_CONTRACTS.items():
            with self.subTest(card=name):
                card = self.card(name)
                rules = main.CARD_RULES[card["id"]]
                self.assertEqual(rules["power"], 2)
                self.assertEqual(rules["temperaments"], [printed])
                self.assertIn(alternate, rules["tributeTemperaments"])
                self.assertIn("used as tribute", card["effect"].lower())

    def test_each_card_pays_a_real_will_with_its_alternate_temperament(self):
        for name, (_printed, alternate) in ALTERNATE_TRIBUTE_CONTRACTS.items():
            with self.subTest(card=name):
                if alternate == "transcendent":
                    power_cost = "{R}{B}"
                else:
                    symbol = SYMBOLS[alternate]
                    power_cost = f"{{{symbol}}}{{{symbol}}}"
                error, action, _session, player, card = self.declare_with(
                    name, power_cost
                )
                self.assertIsNone(error)
                self.assertIsNotNone(action)
                self.assertNotIn(card["id"], player["zones"]["hand"])
                self.assertIn(card["id"], player["zones"]["graveyard"])

    def test_additional_temperament_remains_a_choice_and_cannot_be_split(self):
        for name, (printed, alternate) in ALTERNATE_TRIBUTE_CONTRACTS.items():
            if alternate == "transcendent":
                continue
            with self.subTest(card=name):
                printed_symbol = SYMBOLS[printed]
                error, action, _session, _player, _card = self.declare_with(
                    name, f"{{{printed_symbol}}}{{{printed_symbol}}}"
                )
                self.assertIsNone(error)
                self.assertIsNotNone(action)

                alternate_symbol = SYMBOLS[alternate]
                error, action, _session, player, card = self.declare_with(
                    name, f"{{{printed_symbol}}}{{{alternate_symbol}}}"
                )
                self.assertEqual(
                    error,
                    "The selected Manifestations do not pay the full printed Tribute.",
                )
                self.assertIsNone(action)
                self.assertEqual(
                    player["zones"]["hand"], ["test-will", card["id"]]
                )
                self.assertEqual(player["zones"]["graveyard"], [])

    def test_rocky_is_transcendent_only_while_used_as_tribute(self):
        name = "Rocky Heartcrystal"
        card = self.card(name)
        rules = main.CARD_RULES[card["id"]]
        self.assertEqual(rules["temperaments"], ["hollow"])
        session, _player, _card = self.make_session(name, "{R}{B}")
        covered, _excess = session.rules_manifestations_cover(
            [card["id"]], {"choleric": 1, "vitreous": 1}
        )
        self.assertTrue(covered)
        covered, _excess = session.rules_manifestations_cover(
            [card["id"]],
            {"choleric": 1, "vitreous": 1, "phlegmatic": 1},
        )
        self.assertFalse(covered)
        self.assertEqual(session.card_rules[card["id"]]["temperaments"], ["hollow"])


if __name__ == "__main__":
    unittest.main()
