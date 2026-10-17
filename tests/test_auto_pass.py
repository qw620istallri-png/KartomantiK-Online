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
        manifestation_ids = {f"m-{index}" for index in range(20)} | {"m-support"}
        card_rules = {
            **{card_id: {"type": "manifestation", "power": 1, "temperaments": ["phlegmatic"]}
               for card_id in manifestation_ids},
            "m-support": {"type": "manifestation", "power": 1, "temperaments": ["phlegmatic"], "supportFromHand": True},
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
        p1["zones"]["hand"] = ["will-ephemeral", "m-5"]
        self.goto(session, "resolution_effects")
        self.assertIsNone(session.rules_auto_pass_player())

    def test_pass_all_lock_passes_even_with_playable_cards_until_released(self):
        session, p1, p2 = self.make_session()
        p1["zones"]["hand"] = ["will-ephemeral", "m-5"]
        self.goto(session, "resolution_effects")
        self.assertIsNone(session.rules_auto_pass_player())
        self.assertIsNone(session.set_rules_pass_all("p1", True)[0])
        self.assertEqual(session.serialize_for("p1", "player")["rulesEngine"]["passAllPlayerIds"], ["p1"])
        self.assertEqual(session.rules_auto_pass_player(), "p1")
        # works with phase skipping turned off, never for the opponent's priority
        session.rules_engine["autoSkipPhases"] = False
        self.assertEqual(session.rules_auto_pass_player(), "p1")
        p2["zones"]["hand"] = ["will-ephemeral", "m-6"]
        session.rules_engine["priorityPlayerId"] = "p2"
        self.assertIsNone(session.rules_auto_pass_player())
        # a required choice still stops it
        session.rules_engine["priorityPlayerId"] = "p1"
        session.rules_engine["pendingChoice"] = {"id": "c", "kind": "discard_from_hand", "playerId": "p1"}
        self.assertIsNone(session.rules_auto_pass_player())
        session.rules_engine["pendingChoice"] = None
        self.assertIsNone(session.set_rules_pass_all("p1", False)[0])
        self.assertIsNone(session.rules_auto_pass_player())

    def test_held_enter_lock_is_set_and_released_over_the_socket_handler(self):
        session, p1, _p2 = self.make_session()
        p1["zones"]["hand"] = ["will-ephemeral", "m-5"]
        self.goto(session, "end_actions")
        self.assertIsNone(session.rules_auto_pass_player())
        error, result = session.set_rules_pass_all("p1", True)
        self.assertIsNone(error)
        self.assertEqual(result, {"playerId": "p1", "enabled": True})
        session.set_rules_pass_all("p1", True)
        self.assertEqual(session.rules_engine["passAllPlayerIds"], ["p1"])
        self.assertTrue(asyncio.run(server_main.auto_advance_rules_phases(session, "p1")))
        self.assertNotEqual(session.current_phase_id(), "end_actions")
        self.assertIn("set_rules_pass_all", server_main.AUTO_PASS_MESSAGE_TYPES)

    def test_pass_all_can_be_released_while_the_opponent_is_deciding(self):
        session, _p1, _p2 = self.make_session()
        self.goto(session, "end_actions", priority="p2")
        session.status = "active"
        session.set_rules_pass_all("p1", True)
        session.rules_engine["pendingChoice"] = {"id": "c", "kind": "binary_choice", "playerId": "p2"}
        sent = []
        original_send_error, original_broadcast = server_main.send_error, server_main.broadcast_state

        async def fake_error(_ws, message, code=None):
            sent.append(message)

        async def fake_broadcast(_session):
            return None

        server_main.send_error, server_main.broadcast_state = fake_error, fake_broadcast
        try:
            info = {"session": session, "playerId": "p1", "role": "player"}
            asyncio.run(server_main.handle_message(None, info, {"type": "set_rules_pass_all", "enabled": False}))
        finally:
            server_main.send_error, server_main.broadcast_state = original_send_error, original_broadcast
        self.assertEqual(sent, [])
        self.assertEqual(session.rules_engine["passAllPlayerIds"], [])

    def test_a_will_that_cannot_be_paid_does_not_keep_the_player_in_control(self):
        session, p1, p2 = self.make_session()
        p1["zones"]["hand"] = ["will-ephemeral"]
        self.goto(session, "resolution_effects")
        self.assertEqual(session.rules_auto_pass_player(), "p1")

    def test_the_confrontation_is_never_resolved_while_someone_can_still_act(self):
        session, p1, p2 = self.make_session()
        session.players["p1"]["zones"]["hand"] = ["will-ephemeral", "m-support"]
        session.rules_engine["essenceTokens"] = []
        self.goto(session, "confrontation_reaction")
        session.battlefield = [{
            "id": "tok", "ownerId": "p1", "controllerId": "p1", "cardId": None, "isTokenCard": True,
            "power": 3, "temperament": "phlegmatic", "faceUp": True, "fieldZone": "confrontation",
            "x": 0, "y": 0, "rotation": 0, "counters": {}, "stackedOn": None,
        }]
        # a Support Manifestation playable from hand keeps p1 in control: no prompt, no auto pass
        self.assertIsNone(session.rules_auto_pass_player())
        self.assertFalse(session.rules_confrontation_resolve_prompt())
        # the opponent holding priority with a playable card is not passed either
        p1["zones"]["hand"] = []
        p2["zones"]["hand"] = ["m-support"]
        session.rules_engine["priorityPlayerId"] = "p2"
        self.assertIsNone(session.rules_auto_pass_player())
        self.assertFalse(session.rules_confrontation_resolve_prompt())

    def test_a_plain_manifestation_in_hand_is_not_a_support_action(self):
        session, p1, p2 = self.make_session()
        p1["zones"]["hand"] = ["m-1"]
        self.goto(session, "confrontation_reaction")
        # nobody can act: the engine asks before resolving the Confrontation
        self.assertIsNone(session.rules_auto_pass_player())
        self.assertTrue(session.rules_confrontation_resolve_prompt())
        # once the holder confirmed (passed), the other player is passed automatically
        session.rules_engine["priorityPasses"] = ["p1"]
        session.rules_engine["priorityPlayerId"] = "p2"
        self.assertFalse(session.rules_confrontation_resolve_prompt())
        self.assertEqual(session.rules_auto_pass_player(), "p2")

    def test_a_field_ability_without_enough_counters_is_not_an_action(self):
        session, p1, p2 = self.make_session()
        session.card_rules["counter-card"] = {
            "type": "persistent_will",
            "activatedAbilities": [{"id": "spend", "removeCountersFromSource": {"name": "Union", "amount": 5}}],
        }
        item = {"id": "cc", "ownerId": "p1", "cardId": "counter-card", "faceUp": True,
                "fieldZone": "field", "counters": {"Union": 2}}
        session.battlefield = [item]
        self.goto(session, "resolution_effects")
        self.assertEqual(session.rules_auto_pass_player(), "p1")
        item["counters"]["Union"] = 5
        self.assertIsNone(session.rules_auto_pass_player())

    def test_an_ephemeral_will_is_not_an_action_outside_response_windows(self):
        session, p1, p2 = self.make_session()
        p1["zones"]["hand"] = ["will-ephemeral"]
        self.goto(session, "confrontation_entry")
        self.assertEqual(session.rules_auto_pass_player(), "p1")

    def test_a_persistent_will_only_counts_in_end_actions(self):
        session, p1, p2 = self.make_session()
        p1["zones"]["hand"] = ["will-persistent", "m-5", "m-6"]
        self.goto(session, "resolution_effects")
        self.assertEqual(session.rules_auto_pass_player(), "p1")
        self.goto(session, "end_actions")
        self.assertIsNone(session.rules_auto_pass_player())

    def test_a_manifestation_in_hand_can_enter_support_during_reaction(self):
        session, p1, p2 = self.make_session()
        p1["zones"]["hand"] = ["m-support"]
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
        p2["zones"]["hand"] = ["will-ephemeral", "m-5"]
        self.goto(session, "confrontation_before_revelation")
        asyncio.run(server_main.auto_advance_rules_phases(session, "p1"))
        self.assertIn(session.current_phase_id(), {"confrontation_reaction"})
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p2")
        # Once P2 passes, P1 (nothing to do) is passed for and the phase moves on.
        session.pass_rules_priority("p2")
        asyncio.run(server_main.auto_advance_rules_phases(session, "p2"))
        self.assertNotEqual(session.current_phase_id(), "confrontation_reaction")

    def test_copies_and_tokens_never_choose_deck_or_interzone_unless_permanent(self):
        session, p1, p2 = self.make_session()
        def item(item_id, **extra):
            return {
                "id": item_id, "ownerId": "p1", "controllerId": "p1", "cardId": "m-1",
                "faceUp": True, "fieldZone": "confrontation", "x": 0, "y": 0,
                "rotation": 0, "counters": {}, "stackedOn": None, **extra,
            }
        session.battlefield = [
            item("temp-copy", isCopy=True), item("perm-token", isTokenCard=True, permanent=True),
        ]
        session.rules_engine["confrontationResult"] = {
            "winnerId": "p1", "pendingOwnItemIds": ["temp-copy", "perm-token"],
        }
        choice = session._queue_next_rules_confrontation_destination()
        self.assertEqual(choice["itemId"], "perm-token")
        self.assertEqual(choice["options"], ["interzone"])
        self.assertIsNone(session.find_battlefield_item("temp-copy"))

    def test_cards_entering_a_zone_are_laid_out_on_free_slots(self):
        session, p1, p2 = self.make_session()
        def item(item_id, zone, owner="p1", x=10.0, y=10.0):
            return {
                "id": item_id, "ownerId": owner, "controllerId": owner, "cardId": "m-1",
                "faceUp": True, "fieldZone": zone, "x": x, "y": y,
                "rotation": 0, "counters": {}, "stackedOn": None,
            }
        session.battlefield = [
            item("a", "interzone"), item("b", "interzone"),
            item("c", "confrontation", owner="p2"),
            item("kept", "confrontation", x=500.0, y=800.0),
        ]
        session.rules_auto_layout()
        a, b, c, kept = session.battlefield
        self.assertEqual((a["x"], a["y"]), (445.0, 1064.0))
        self.assertEqual((b["x"], b["y"]), (750.0, 1064.0))
        self.assertEqual(c["y"], 525.0)
        self.assertEqual((kept["x"], kept["y"]), (445.0, 800.0))  # a drop only steers the card to the nearest free slot
        a["x"] = 900.0
        session.rules_auto_layout()
        self.assertEqual(a["x"], 900.0)


if __name__ == "__main__":
    unittest.main()
