"""Exact payment boundaries for uncovered printed Tribute-cost abilities."""
import copy
import re
import unittest

import card_scenario_batches as batches
import main


TRIBUTE_COSTS = {
    "Rinq, Shameless Slacker": 2,
    "Intoxicating Blossom": 2,
    "Nullifying Hat": 2,
    "Urolong, Rueful Necromancer": 2,
    "Mimer": 1,
    "Bratto, Tyrannical Scoundrel": 2,
    "Gornagor, the Magnificent": 3,
    "Gorte, Timeless": 4,
    "Empathic Mask": 1,
    "Karmapult": 1,
    "Volcano": 4,
    "Psychowall": 4,
    "Juggernut, the Overwhelming": 2,
    "Explosive Rancor": 4,
}


class TributeCostFamilyClauses(unittest.TestCase):
    @staticmethod
    def card(name):
        return next(card for card in main.CARD_DATA if card["name"] == name)

    def ability(self, name):
        card = self.card(name)
        abilities = [
            ability for ability in main.CARD_ABILITIES[card["id"]]
            if ability.get("tribute")
        ]
        if name == "Empathic Mask":
            abilities = abilities[:1]
        self.assertEqual(len(abilities), 1, name)
        return card, abilities[0]

    def declare(self, name, funded):
        card, ability = self.ability(name)
        session, actor, source, targets, _cost_card = (
            batches.prepare_action(card["id"], ability)
        )
        if not funded:
            session.tokens = []
        source_item = session.find_battlefield_item(source.get("itemId"))
        before = copy.deepcopy((
            source_item,
            session.players,
            session.rules_engine["actionStack"],
        ))
        error, action = session.declare_rules_action(
            actor, name,
            kind=ability.get("action") or "activated_effect",
            source=source,
            ability_id=ability["id"],
            targets=targets,
            payment_card_ids=[],
        )
        return session, source_item, before, error, action

    def test_printed_and_encoded_tribute_amounts_match_exactly(self):
        self.assertEqual(len(TRIBUTE_COSTS), 14)
        for name, expected in TRIBUTE_COSTS.items():
            with self.subTest(card=name):
                card, ability = self.ability(name)
                encoded = len(re.findall(r"\{H\}", ability["tribute"]))
                self.assertEqual(encoded, expected)
                printed = card["effect"]
                braces = max(
                    (len(match) for match in re.findall(
                        r"(?:\{H\})+", printed
                    )),
                    default=0,
                )
                printed_count = (
                    braces // 3 if braces else next(
                        (
                            int(value) if value else len(symbols)
                            for value, symbols in re.findall(
                                r"[Pp]ay (?:(\d+) )?(🔘+)", printed
                            )
                        ),
                        0,
                    )
                )
                self.assertEqual(printed_count, expected)

    def test_exact_tribute_is_spent_and_action_enters_the_stack(self):
        for name, expected in TRIBUTE_COSTS.items():
            with self.subTest(card=name):
                session, _source, _before, error, action = self.declare(
                    name, funded=True
                )
                self.assertIsNone(error)
                self.assertEqual(
                    sum(
                        entry["amount"]
                        for entry in action["cost"]["essenceSpent"]
                    ),
                    expected,
                )
                self.assertEqual(
                    session.rules_engine["actionStack"][-1]["id"],
                    action["id"],
                )

    def test_missing_tribute_rejects_without_mutating_source_or_stack(self):
        for name in TRIBUTE_COSTS:
            with self.subTest(card=name):
                session, source, before, error, action = self.declare(
                    name, funded=False
                )
                self.assertIsNotNone(error)
                self.assertIsNone(action)
                self.assertEqual(
                    (source, session.players, session.rules_engine["actionStack"]),
                    before,
                )


if __name__ == "__main__":
    unittest.main()
