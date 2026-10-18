import json
import math
import os
import sys
import unittest

SERVER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server"))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

import main as server_main
from session import Session


class HiddenStateSerializationTests(unittest.TestCase):
    def setUp(self):
        self.session = Session(rules_beta=True)
        p1 = self.session.get_or_create_player("p1", "P1")
        p2 = self.session.get_or_create_player("p2", "P2")
        p1["zones"]["hand"] = ["secret-card"]
        p1["zones"]["deck"] = ["secret-deck-card"]
        p1["zones"]["exile"] = ["secret-exile-card"]
        p1["cardRarities"] = {"secret-rarity-card": "foil"}
        p1["deckDefinition"] = {"name": "secret-deck-definition"}
        p1["sideboard"] = ["secret-sideboard-card"]
        p2["zones"]["hand"] = ["own-card"]
        self.session.rules_engine["zoneEntryTurns"] = {
            "p1:hand:secret-card": 1,
            "p1:deck:secret-deck-card": 1,
            "p1:exile:secret-exile-card": 1,
            "p2:hand:own-card": 1,
            "p1:graveyard:public-card": 1,
        }
        self.session.rules_conditional_support_hand_card_ids = lambda: {
            "p1": ["conditional-secret"],
            "p2": ["conditional-own"],
        }
        self.session.rules_engine["playPermissions"] = [
            {"playerId": "p1", "cardId": "secret-permission-card", "fromZone": "hand"},
            {"playerId": "p2", "cardId": "own-permission-card", "fromZone": "hand"},
        ]

    def test_player_receives_only_visible_zone_metadata(self):
        rules = self.session.serialize_for("p2", "player")["rulesEngine"]
        self.assertNotIn("p1:hand:secret-card", rules["zoneEntryTurns"])
        self.assertEqual(rules["zoneEntryTurns"]["p2:hand:own-card"], 1)
        self.assertEqual(rules["zoneEntryTurns"]["p1:graveyard:public-card"], 1)
        self.assertEqual(rules["conditionalSupportHandCardIds"], {"p2": ["conditional-own"]})
        self.assertEqual(
            rules["playPermissions"],
            [{"playerId": "p2", "cardId": "own-permission-card", "fromZone": "hand"}],
        )

    def test_no_private_sentinel_occurs_anywhere_in_opponent_snapshot(self):
        serialized = json.dumps(self.session.serialize_for("p2", "player"))
        for sentinel in (
            "secret-card", "secret-deck-card", "secret-exile-card",
            "secret-rarity-card", "secret-deck-definition",
            "secret-sideboard-card", "conditional-secret", "secret-permission-card",
        ):
            with self.subTest(sentinel=sentinel):
                self.assertNotIn(sentinel, serialized)

    def test_privileged_observer_receives_complete_metadata(self):
        rules = self.session.serialize_for(None, "judge")["rulesEngine"]
        self.assertIn("p1:hand:secret-card", rules["zoneEntryTurns"])
        self.assertEqual(set(rules["conditionalSupportHandCardIds"]), {"p1", "p2"})
        self.assertEqual(len(rules["playPermissions"]), 2)


class ClientNumericValidationTests(unittest.TestCase):
    def test_rejects_non_finite_and_malformed_values(self):
        for payload in (
            {"type": "add_token", "x": float("nan")},
            {"type": "move_token", "y": float("inf")},
            {"type": "draw", "count": "many"},
            {"type": "add_stroke", "points": [[0, 1], [2, "bad"]]},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(server_main.InvalidClientValue):
                    server_main.validate_client_numerics(payload)

    def test_normalizes_valid_numeric_strings(self):
        payload = {"type": "place_card", "x": "12.5", "y": "-3", "rotation": "90"}
        server_main.validate_client_numerics(payload)
        self.assertEqual(payload["x"], 12.5)
        self.assertEqual(payload["y"], -3.0)
        self.assertEqual(payload["rotation"], 90.0)

    def test_json_encoder_never_emits_nan(self):
        with self.assertRaises(ValueError):
            server_main.encode_message({"x": math.nan})


class SessionCleanupTests(unittest.TestCase):
    def tearDown(self):
        server_main.sessions.clear()
        server_main.connections.clear()

    def test_expired_disconnected_sessions_are_removed(self):
        expired = Session()
        expired.last_activity = 0
        fresh = Session()
        server_main.sessions.update({"OLD": expired, "NEW": fresh})
        self.assertEqual(server_main.cleanup_expired_sessions(), ["OLD"])
        self.assertEqual(set(server_main.sessions), {"NEW"})

    def test_connected_session_is_not_removed_even_when_expired(self):
        session = Session()
        session.last_activity = 0
        server_main.sessions["ACTIVE"] = session
        server_main.connections[object()] = {"session": session}
        self.assertEqual(server_main.cleanup_expired_sessions(), [])
        self.assertIn("ACTIVE", server_main.sessions)


if __name__ == "__main__":
    unittest.main()
