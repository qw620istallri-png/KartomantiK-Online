"""Statistical check: a Mulligan really returns the hand, reshuffles and redraws."""
import os
import random
import sys
import unittest
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
from session import Session  # noqa: E402

DECK = [f"c{i:02d}" for i in range(30)]


def opening_session(manifestations):
    rules = {c: {"type": "manifestation" if c in manifestations else "will"} for c in DECK}
    session = Session(mode="casual", manifestation_ids=manifestations, card_rules=rules, rules_beta=True)
    for seat, pid in enumerate(("A", "B")):
        session.get_or_create_player(pid, pid, seat)
        deck = list(DECK)
        random.shuffle(deck)  # what import_deck does
        session.players[pid]["zones"]["deck"] = deck
        session.players[pid]["zoneOwners"]["deck"] = {c: pid for c in deck}
    session.rules_engine["deckConfirmedPlayerIds"] = ["A", "B"]
    error, result = session.prepare_rules_opening_hands(7)
    assert not error, error
    return session, result


class MulliganShuffleTest(unittest.TestCase):
    def setUp(self):
        random.seed(1234)

    def test_voluntary_mulligan_redraws_from_a_shuffled_full_deck(self):
        overlaps, seen = [], Counter()
        for _ in range(1500):
            session, _ = opening_session(set(DECK))
            before = list(session.players["A"]["zones"]["hand"])
            error, _ = session.mulligan_opening_hand("A", 7)
            self.assertIsNone(error)
            after = session.players["A"]["zones"]["hand"]
            self.assertEqual(len(after), 7)
            self.assertEqual(sorted(after + session.players["A"]["zones"]["deck"]), sorted(DECK))
            overlaps.append(len(set(before) & set(after)))
            seen.update(after)
        # 7 of 30 redrawn: about 7*7/30 = 1.63 cards in common on average
        self.assertAlmostEqual(sum(overlaps) / len(overlaps), 49 / 30, delta=0.15)
        expected = 1500 * 7 / 30
        chi2 = sum((seen[c] - expected) ** 2 / expected for c in DECK)
        self.assertLess(chi2, 49.6)  # 29 degrees of freedom, 1 % threshold

    def test_forced_mulligan_uses_the_same_shuffle(self):
        overlaps = []
        while len(overlaps) < 600:
            session, result = opening_session(set(DECK[:3]))
            if "A" not in result["mulliganRequiredPlayerIds"]:
                continue
            before = list(session.players["A"]["zones"]["hand"])
            error, _ = session.mulligan_opening_hand("A", 7)
            self.assertIsNone(error)
            overlaps.append(len(set(before) & set(session.players["A"]["zones"]["hand"])))
        self.assertAlmostEqual(sum(overlaps) / len(overlaps), 49 / 30, delta=0.2)


if __name__ == "__main__":
    unittest.main()
