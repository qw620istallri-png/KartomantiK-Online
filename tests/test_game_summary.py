import os
import sys
import unittest

SERVER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server"))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from session import Session  # noqa: E402


class GameSummaryTests(unittest.TestCase):
    def setUp(self):
        self.session = Session(card_points={"won": 20, "other": 5})
        self.p1 = self.session.get_or_create_player("p1", "P1")
        self.p2 = self.session.get_or_create_player("p2", "P2")

    def test_score_history_records_each_turn_once(self):
        self.p1["zones"]["receptacle"] = ["won"]
        self.p1["score"] = -3
        self.session.record_score_history(1)
        self.session.record_score_history(1)
        self.assertEqual(self.session.score_history, [{"turn": 1, "scores": {"p1": 17, "p2": 0}}])

    def test_manual_turn_change_records_the_turn_that_ended(self):
        self.session.phase_tracker["enabled"] = True
        self.session.phase_tracker["index"] = len(self.session.phase_sequence()) - 1
        self.p2["zones"]["receptacle"] = ["other"]
        self.session.phase_passes.update({"p1"})
        self.assertEqual(self.session.pass_phase("p2"), "advanced")
        self.assertEqual(self.session.score_history[-1], {"turn": 1, "scores": {"p1": 0, "p2": 5}})

    def test_summary_counts_wins_and_picks_the_key_card(self):
        self.session.phase_tracker["turn"] = 3
        self.session.record_score_history(1)
        self.session.add_log("p1", "rules_action_declared", {"source": {"cardId": "other"}})
        self.session.add_log("p1", "rules_confrontation_compared", {"winnerId": "p1", "winnerCardIds": ["won"]})
        self.session.add_log("p1", "rules_confrontation_compared", {"winnerId": "p1", "winnerCardIds": ["won", "other"]})
        self.session.add_log("p2", "rules_confrontation_compared", {"winnerId": None, "stalemate": True})
        self.session.add_log("p2", "rules_action_declared", {"source": {"cardId": "other"}})
        self.p1["zones"]["receptacle"] = ["won"]
        summary = self.session.game_summary()
        self.assertEqual(summary["turns"], 3)
        self.assertEqual(summary["stalemates"], 1)
        self.assertEqual(summary["players"]["p1"], {"confrontationsWon": 2, "actions": 1, "keyCardId": "won", "keyCardWins": 2})
        # no confrontation won: the card played the most
        self.assertEqual(summary["players"]["p2"]["keyCardId"], "other")
        self.assertEqual(summary["players"]["p2"]["keyCardWins"], 0)
        self.assertEqual([entry["turn"] for entry in summary["scoreHistory"]], [1, 3])
        self.assertEqual(summary["scoreHistory"][-1]["scores"], {"p1": 20, "p2": 0})

    def test_summary_is_sent_once_the_game_has_ended(self):
        self.assertIsNone(self.session.serialize_for("p1", "player")["gameSummary"])
        self.session.concede("p2")
        self.assertEqual(self.session.serialize_for("p1", "player")["gameSummary"]["players"]["p1"]["confrontationsWon"], 0)


if __name__ == "__main__":
    unittest.main()
