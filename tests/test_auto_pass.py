import asyncio
import sys
import unittest
from pathlib import Path

SERVER_DIR = str(Path(__file__).resolve().parents[1] / "server")
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

import main as server_main
from session import ADVANCED_PHASES, Session


class AutoPassTests(unittest.TestCase):
    def make_session(self):
        manifestation_ids = {f"m-{index}" for index in range(20)}
        card_rules = {
            **{card_id: {"type": "manifestation", "power": 1, "temperaments": ["phlegmatic"]}
               for card_id in manifestation_ids},
            "will-ephemeral": {"type": "ephemeral_will", "cost": 1, "powerCost": "{G}", "temperaments": ["phlegmatic"]},
            "will-persistent": {"type": "persistent_will", "cost": 2, "powerCost": "{G}{G}", "temperaments": ["phlegmatic"]},
        }
        session = Session(rules_beta=True, card_points={}, manifestation_ids=manifestation_ids, card_rules=card_rules)
        p1 = session.get_or_create_player("p1", "P1", seat=0)
        p2 = session.get_or_create_player("p2", "P2", seat=1)
        session.rules_engine["deckConfirmedPlayerIds"] = ["p1", "p2"]
        session.rules_engine["readyPlayerIds"] = ["p1", "p2"]
        session.rules_engine["firstManifestationComplete"] = True
        for player in (p1, p2):
            player["zones"]["hand"] = []
        return session, p1, p2

    def goto(self, session, phase_id, priority="p1"):
        session.phase_tracker["index"] = ADVANCED_PHASES.index(phase_id)
        session.rules_engine["priorityPlayerId"] = priority
        session.rules_engine["priorityPasses"] = []

    def test_a_player_with_nothing_to_do_is_passed_automatically(self):
        session, p1, p2 = self.make_session()
        self.goto(session, "end_actions")
        self.assertEqual(session.rules_auto_pass_player(), "p1")

    def test_an_ephemeral_will_in_hand_keeps_the_player_in_control_during_reaction(self):
        session, p1, p2 = self.make_session()
        p1["zones"]["hand"] = ["will-ephemeral"]
        self.goto(session, "resolution_effects")
        self.assertIsNone(session.rules_auto_pass_player())

    def test_an_ephemeral_will_is_not_an_action_outside_response_windows(self):
        session, p1, p2 = self.make_session()
        p1["zones"]["hand"] = ["will-ephemeral"]
        self.goto(session, "confrontation_entry")
        self.assertEqual(session.rules_auto_pass_player(), "p1")

    def test_a_persistent_will_only_counts_in_end_actions(self):
        session, p1, p2 = self.make_session()
        p1["zones"]["hand"] = ["will-persistent"]
        self.goto(session, "resolution_effects")
        self.assertEqual(session.rules_auto_pass_player(), "p1")
        self.goto(session, "end_actions")
        self.assertIsNone(session.rules_auto_pass_player())

    def test_a_manifestation_in_hand_can_enter_support_during_reaction(self):
        session, p1, p2 = self.make_session()
        p1["zones"]["hand"] = ["m-1"]
        self.goto(session, "confrontation_reaction")
        self.assertIsNone(session.rules_auto_pass_player())
        self.goto(session, "resolution_compare")
        self.assertEqual(session.rules_auto_pass_player(), "p1")

    def test_the_option_a_pending_choice_and_an_unstarted_match_disable_it(self):
        session, p1, p2 = self.make_session()
        self.goto(session, "end_actions")
        session.rules_engine["autoSkipPhases"] = False
        self.assertIsNone(session.rules_auto_pass_player())
        session.rules_engine["autoSkipPhases"] = True
        session.rules_engine["pendingChoice"] = {"id": "c", "kind": "binary_choice", "playerId": "p1"}
        self.assertIsNone(session.rules_auto_pass_player())
        session.rules_engine["pendingChoice"] = None
        session.rules_engine["readyPlayerIds"] = []
        session.rules_engine["firstManifestationComplete"] = False
        self.assertIsNone(session.rules_auto_pass_player())

    def test_empty_hands_skip_phases_until_a_first_manifestation_is_needed(self):
        session, p1, p2 = self.make_session()
        self.goto(session, "resolution_compare")
        turn = session.phase_tracker["turn"]
        steps = asyncio.run(server_main.auto_advance_rules_phases(session, "p1"))
        self.assertGreater(steps, 0)
        self.assertEqual(session.phase_tracker["turn"], turn + 1)
        self.assertLess(steps, server_main.AUTO_PASS_MAX_STEPS)

    def test_the_loop_stops_at_the_phase_where_a_player_can_act(self):
        session, p1, p2 = self.make_session()
        p2["zones"]["hand"] = ["will-ephemeral"]
        self.goto(session, "confrontation_before_revelation")
        asyncio.run(server_main.auto_advance_rules_phases(session, "p1"))
        self.assertIn(session.current_phase_id(), {"confrontation_reaction"})
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p2")
        # Once P2 passes, P1 (nothing to do) is passed for and the phase moves on.
        session.pass_rules_priority("p2")
        asyncio.run(server_main.auto_advance_rules_phases(session, "p2"))
        self.assertNotEqual(session.current_phase_id(), "confrontation_reaction")


if __name__ == "__main__":
    unittest.main()
