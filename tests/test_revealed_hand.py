import os
import sys
import unittest

SERVER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server"))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from session import Session  # noqa: E402


class RevealedHandTests(unittest.TestCase):
    def setUp(self):
        self.session = Session()
        self.p1 = self.session.get_or_create_player("p1", "P1")
        self.p2 = self.session.get_or_create_player("p2", "P2")
        self.p1["zones"]["hand"] = ["a", "b", "c", "b"]
        self.p1["zoneOwners"]["hand"] = {card_id: "p1" for card_id in "abc"}

    def opponent_view(self):
        return self.session.serialize_for("p2", "player")["players"]["p1"]["zones"]["hand"]

    def test_revealed_card_is_shown_at_its_real_place(self):
        self.session.mark_hand_revealed("p1", ["c"])
        self.assertEqual(self.opponent_view(), {"count": 4, "revealed": [{"index": 2, "cardId": "c"}]})
        self.assertEqual(self.session.serialize_for("p1", "player")["players"]["p1"]["zones"]["hand"]["revealedIndices"], [2])

    def test_revealed_card_is_forgotten_once_it_leaves_the_hand(self):
        self.session.mark_hand_revealed("p1", ["c"])
        self.opponent_view()
        error, _ = self.session.move_zone_card("p1", "hand", "p1", "graveyard", "c")
        self.assertIsNone(error)
        self.assertEqual(self.opponent_view(), {"count": 3})

    def test_a_remaining_copy_is_not_shown_once_the_revealed_copy_left(self):
        self.session.mark_hand_revealed("p1", ["b"])
        self.opponent_view()
        self.session.move_zone_card("p1", "hand", "p1", "graveyard", "b")
        self.assertEqual(self.opponent_view(), {"count": 3})

    def test_cards_drawn_after_a_reveal_keep_the_revealed_card_in_place(self):
        self.session.mark_hand_revealed("p1", ["c"])
        self.opponent_view()
        self.p1["zones"]["hand"].insert(0, "d")
        self.assertEqual(self.opponent_view()["revealed"], [{"index": 3, "cardId": "c"}])

    def test_mulligan_forgets_the_revealed_cards(self):
        self.session.mark_hand_revealed("p1", ["a"])
        self.session.forget_revealed_hand("p1")
        self.assertEqual(self.opponent_view(), {"count": 4})


if __name__ == "__main__":
    unittest.main()
