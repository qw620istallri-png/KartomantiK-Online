"""Kox, the Amoral raises the construction limit by 50 points: it is not worth
-50 points, neither in the deck total nor in an Empathic Vessel."""
import os
import sys
import unittest

SERVER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server"))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

import main as server_main  # noqa: E402
from session import Session  # noqa: E402

KOX = server_main.CARD_ID_BY_NUMBER[248]


class KoxPointsTest(unittest.TestCase):
    def test_kox_is_worth_no_points(self):
        self.assertEqual(server_main.CARD_POINTS[KOX], 0)

    def test_kox_in_a_vessel_does_not_remove_points(self):
        session = Session(card_points=server_main.CARD_POINTS, card_labels=server_main.CARD_LABELS,
                          manifestation_ids=server_main.CARD_MANIFESTATION_IDS,
                          card_rules=server_main.CARD_RULES, rules_beta=True)
        player = session.get_or_create_player("p1", "P1", seat=0)
        player["zones"]["receptacle"] = [KOX]
        self.assertEqual(session.rules_vessel_total("p1"), 0)

    def test_kox_allows_550_points_without_counting_minus_50(self):
        points = dict(server_main.CARD_POINTS)
        deck = [KOX] + [f"x-{i}" for i in range(29)]
        for i in range(29):
            points[f"x-{i}"] = 0
        points["x-0"] = 550  # 550 in total: legal only thanks to Kox's +50 limit
        bonus = sum(int(server_main.CARD_RULES.get(c, {}).get("constructionLimitBonus") or 0) for c in deck)
        self.assertEqual(bonus, 50)
        self.assertIsNone(server_main.validate_tournament_deck(deck, [], points, limit_bonus=bonus))
        points["x-0"] = 551
        self.assertIsNotNone(server_main.validate_tournament_deck(deck, [], points, limit_bonus=bonus))


if __name__ == "__main__":
    unittest.main()
