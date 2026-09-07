import os
import sys
import unittest

SERVER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server"))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from session import Session


class CardOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.session = Session()
        self.p1 = self.session.get_or_create_player("p1", "P1")
        self.p2 = self.session.get_or_create_player("p2", "P2")
        self.p1["zones"]["deck"] = ["card-a"]
        self.p1["zoneOwners"]["deck"] = {"card-a": "p1"}

    def test_owner_is_preserved_in_opponent_vessel(self):
        error, owner_id = self.session.move_zone_card("p1", "deck", "p2", "receptacle", "card-a")
        self.assertIsNone(error)
        self.assertEqual(owner_id, "p1")
        self.assertEqual(self.session.card_owner_in_zone("p2", "receptacle", "card-a"), "p1")

    def test_card_cannot_enter_owners_vessel(self):
        error, owner_id = self.session.move_zone_card("p1", "deck", "p1", "receptacle", "card-a")
        self.assertIn("owner's Empathic Vessel", error)
        self.assertEqual(owner_id, "p1")
        self.assertIn("card-a", self.p1["zones"]["deck"])

    def test_card_cannot_enter_opponents_limbo_or_exile(self):
        for zone in ("graveyard", "exile"):
            with self.subTest(zone=zone):
                error, owner_id = self.session.move_zone_card("p1", "deck", "p2", zone, "card-a")
                self.assertIn("only enter its owner's", error)
                self.assertEqual(owner_id, "p1")
                self.assertIn("card-a", self.p1["zones"]["deck"])

    def test_reset_returns_captured_card_to_original_owner(self):
        self.session.move_zone_card("p1", "deck", "p2", "receptacle", "card-a")
        self.session.reset_cards_to_owners()
        self.assertEqual(self.p1["zones"]["deck"], ["card-a"])
        self.assertEqual(self.p2["zones"]["receptacle"], [])


class PhaseTrackerTests(unittest.TestCase):
    def setUp(self):
        self.session = Session()
        self.session.get_or_create_player("p1", "P1")
        self.session.get_or_create_player("p2", "P2")
        self.session.configure_phases(enabled=True)

    def test_both_players_must_pass_to_advance(self):
        self.assertEqual(self.session.pass_phase("p1"), "passed")
        self.assertEqual(self.session.phase_tracker["index"], 0)
        self.assertEqual(self.session.pass_phase("p2"), "advanced")
        self.assertEqual(self.session.phase_tracker["index"], 1)
        self.assertEqual(self.session.phase_passes, set())

    def test_player_can_cancel_pass(self):
        self.assertEqual(self.session.pass_phase("p1"), "passed")
        self.assertEqual(self.session.pass_phase("p1"), "cancelled")
        self.assertEqual(self.session.phase_tracker["index"], 0)
        self.assertEqual(self.session.phase_passes, set())

    def test_explicit_pass_state_is_idempotent_and_cancellable(self):
        self.assertEqual(self.session.pass_phase("p1", passed=True), "passed")
        self.assertEqual(self.session.pass_phase("p1", passed=True), "passed")
        self.assertEqual(self.session.phase_passes, {"p1"})
        self.assertEqual(self.session.pass_phase("p1", passed=False), "cancelled")
        self.assertEqual(self.session.pass_phase("p1", passed=False), "cancelled")
        self.assertEqual(self.session.phase_tracker["index"], 0)
        self.assertEqual(self.session.phase_passes, set())

    def test_enabled_toggle_preserves_phase_and_turn(self):
        self.session.phase_tracker.update({"index": 2, "turn": 4})
        self.session.phase_passes.add("p1")
        self.session.configure_phases(enabled=False)
        self.session.configure_phases(enabled=True)
        self.assertEqual(self.session.phase_tracker["index"], 2)
        self.assertEqual(self.session.phase_tracker["turn"], 4)
        self.assertEqual(self.session.phase_passes, {"p1"})

    def test_advanced_mode_keeps_current_phase_group(self):
        self.session.pass_phase("p1")
        self.session.pass_phase("p2")
        self.assertEqual(self.session.current_phase_group(), "confrontation")
        self.session.configure_phases(advanced=True)
        self.assertEqual(self.session.current_phase_group(), "confrontation")
        self.assertEqual(self.session.phase_tracker["index"], 3)
        self.assertEqual(len(self.session.phase_sequence()), 14)


if __name__ == "__main__":
    unittest.main()
