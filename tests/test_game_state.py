import os
import sys
import unittest

SERVER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server"))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from session import Session, validate_tournament_deck


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

    def test_reset_never_puts_a_copy_into_a_deck(self):
        self.p1["zones"]["deck"] = []
        self.session.battlefield.append({
            "id": "copy-1", "ownerId": "p1", "cardId": "card-a",
            "x": 0, "y": 0, "faceUp": True, "rotation": 0,
            "counters": {}, "isCopy": True,
        })
        self.session.reset_cards_to_owners()
        self.assertNotIn("card-a", self.p1["zones"]["deck"])

    def test_clean_reset_discards_old_cards_and_rebuilds_only_active_decks(self):
        self.p1["zones"]["deck"] = ["old-deck-card"]
        self.p1["zoneOwners"]["deck"] = {"old-deck-card": "p1"}
        self.p1["zones"]["hand"] = ["old-hand-card"]
        self.p1["zoneOwners"]["hand"] = {"old-hand-card": "p1"}
        self.p2["zones"]["graveyard"] = ["old-limbo-card"]
        self.p2["zoneOwners"]["graveyard"] = {"old-limbo-card": "p2"}
        self.session.battlefield = [
            {"id": "old-field-1", "ownerId": "p1", "cardId": "old-field-card-1", "faceUp": True},
            {"id": "old-field-2", "ownerId": "p2", "cardId": "old-field-card-2", "faceUp": True},
        ]
        p1_definition = {"name": "New P1", "groups": [{"kind": "deck", "cardIds": ["new-p1-a", "new-p1-b"]}]}
        p2_definition = {"name": "New P2", "groups": [{"kind": "deck", "cardIds": ["new-p2-a"]}]}

        self.session.reset_cards_to_active_decks({
            "p1": {
                "cardIds": ["new-p1-a", "new-p1-b"],
                "sideboardIds": ["new-p1-side"],
                "cardRarities": {"new-p1-a": "desert"},
                "deckDefinition": p1_definition,
            },
            "p2": {
                "cardIds": ["new-p2-a"],
                "sideboardIds": [],
                "cardRarities": {},
                "deckDefinition": p2_definition,
            },
        })

        self.assertEqual(self.p1["zones"]["deck"], ["new-p1-a", "new-p1-b"])
        self.assertEqual(self.p2["zones"]["deck"], ["new-p2-a"])
        for player in (self.p1, self.p2):
            for zone, cards in player["zones"].items():
                if zone != "deck":
                    self.assertEqual(cards, [])
        self.assertEqual(self.p1["sideboard"], ["new-p1-side"])
        self.assertEqual(self.p1["cardRarities"], {"new-p1-a": "desert"})
        self.assertEqual(self.p1["deckDefinition"], p1_definition)
        self.assertEqual(self.session.battlefield, [])
        all_deck_cards = self.p1["zones"]["deck"] + self.p2["zones"]["deck"]
        self.assertFalse(any(card_id.startswith("old-") for card_id in all_deck_cards))

    def test_sideboard_is_private_to_its_owner(self):
        self.p1["sideboard"] = ["card-a"]
        own_view = self.session.serialize_for("p1", False)["players"]["p1"]
        opponent_view = self.session.serialize_for("p2", False)["players"]["p1"]
        self.assertEqual(own_view["sideboard"], ["card-a"])
        self.assertEqual(opponent_view["sideboard"], {"count": 1})

    def test_replacing_one_deck_preserves_the_opponents_board_and_captured_cards(self):
        self.p1["zones"]["deck"] = []
        self.p1["zones"]["hand"] = ["card-a"]
        self.p1["zoneOwners"]["hand"] = {"card-a": "p1"}
        self.p1["zones"]["receptacle"] = ["card-b"]
        self.p1["zoneOwners"]["receptacle"] = {"card-b": "p2"}
        self.p2["zones"]["receptacle"] = ["card-c"]
        self.p2["zoneOwners"]["receptacle"] = {"card-c": "p1"}
        self.session.battlefield = [
            {"id": "mine", "ownerId": "p1", "cardId": "card-d", "faceUp": True},
            {"id": "theirs", "ownerId": "p2", "cardId": "card-e", "faceUp": True},
        ]
        definition = {"name": "Edited", "groups": []}

        self.session.replace_player_deck(
            "p1", ["card-a", "card-c", "card-d"], ["side-a"], {"card-a": "desert"}, definition
        )

        self.assertEqual(self.p1["zones"]["deck"], ["card-a", "card-c", "card-d"])
        self.assertEqual(self.p1["zones"]["receptacle"], ["card-b"])
        self.assertEqual(self.p2["zones"]["receptacle"], [])
        self.assertEqual([item["id"] for item in self.session.battlefield], ["theirs"])
        self.assertEqual(self.p1["sideboard"], ["side-a"])
        self.assertEqual(self.p1["cardRarities"], {"card-a": "desert"})
        self.assertEqual(self.p1["deckDefinition"], definition)

    def test_card_copy_can_be_created_from_every_requested_zone_without_moving_source(self):
        for index, zone in enumerate(("deck", "hand", "graveyard", "exile")):
            card_id = f"card-{zone}"
            self.p1["zones"][zone] = [card_id]
            self.p1["zoneOwners"][zone] = {card_id: "p1"}
            self.p1["cardRarities"][card_id] = "desert"
            error, item = self.session.copy_card(
                "p1", False, source_owner="p1", source_zone=zone,
                card_id=card_id, x=index, y=index,
            )
            self.assertIsNone(error)
            self.assertTrue(item["isCopy"])
            self.assertEqual(item["rarity"], "desert")
            self.assertEqual(self.p1["zones"][zone], [card_id])

        self.p2["zones"]["receptacle"] = ["card-vessel"]
        self.p2["zoneOwners"]["receptacle"] = {"card-vessel": "p1"}
        error, item = self.session.copy_card(
            "p1", False, source_owner="p2", source_zone="receptacle",
            card_id="card-vessel", x=8, y=9,
        )
        self.assertIsNone(error)
        self.assertEqual(item["cardId"], "card-vessel")
        self.assertEqual(self.p2["zones"]["receptacle"], ["card-vessel"])

    def test_battlefield_copy_keeps_copy_stamp_state_and_rejects_copy_of_copy(self):
        source = {
            "id": "field-card", "ownerId": "p1", "cardId": "card-a",
            "x": 10, "y": 20, "faceUp": True, "rotation": 90,
            "counters": {}, "rarity": "desert",
        }
        self.session.battlefield = [source]
        error, item = self.session.copy_card("p2", False, item_id="field-card")
        self.assertIsNone(error)
        self.assertEqual((item["x"], item["y"], item["rotation"]), (34.0, 44.0, 90.0))
        self.assertTrue(item["isCopy"])
        error, duplicate = self.session.copy_card("p2", False, item_id=item["id"])
        self.assertIn("real card", error)
        self.assertIsNone(duplicate)


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


class TournamentModeTests(unittest.TestCase):
    def setUp(self):
        self.session = Session(mode="tournament")
        cards = [f"card-{index}" for index in range(30)]
        self.p1 = self.session.get_or_create_player("p1", "P1", seat=0)
        self.p2 = self.session.get_or_create_player("p2", "P2", seat=1)
        self.p1["connected"] = True
        self.p2["connected"] = True
        self.p1["zones"]["deck"] = list(cards)
        self.p1["zones"]["hand"] = ["secret-hand"]
        self.p1["zoneOwners"]["deck"] = {card_id: "p1" for card_id in cards}
        self.p1["zoneOwners"]["hand"] = {"secret-hand": "p1"}
        self.p1["sideboard"] = ["secret-sideboard"]
        self.p1["cardRarities"] = {"secret-hand": "void"}
        self.p1["deckDefinition"] = {"groups": [{"kind": "deck", "cardIds": cards}]}
        self.session.battlefield = [{
            "id": "hidden-field", "ownerId": "p1", "cardId": "secret-field",
            "x": 10, "y": 20, "faceUp": False, "rotation": 0, "counters": {},
        }]

    def test_tournament_has_distinct_role_codes_and_starts_in_lobby(self):
        codes = self.session.tournament_codes()
        self.assertEqual(set(codes), {"player1", "player2", "spectator", "judge"})
        self.assertEqual(len(set(codes.values())), 4)
        self.assertNotIn(self.session.code_organizer, codes.values())
        self.assertEqual(self.session.status, "lobby")

    def test_tournament_summary_keeps_fixed_seats_and_deck_readiness(self):
        summary = self.session.tournament_summary()
        self.assertEqual([seat["name"] for seat in summary["seats"]], ["P1", "P2"])
        self.assertTrue(summary["seats"][0]["deckReady"])
        self.assertFalse(summary["seats"][1]["deckReady"])

    def test_spectator_never_receives_hidden_cards_or_deck_metadata(self):
        view = self.session.serialize_for("spectator-client", "spectator")
        p1 = view["players"]["p1"]
        self.assertEqual(p1["zones"]["hand"], {"count": 1})
        self.assertEqual(p1["zones"]["deck"], {"count": 30})
        self.assertEqual(p1["sideboard"], {"count": 1})
        self.assertEqual(p1["cardRarities"], {})
        self.assertIsNone(p1["deckDefinition"])
        self.assertIsNone(view["battlefield"][0]["cardId"])
        self.assertFalse(self.session.can_act_on_zone("spectator-client", "spectator", "p1", "graveyard"))

    def test_judge_sees_everything_but_cannot_act(self):
        view = self.session.serialize_for("judge-client", "judge")
        p1 = view["players"]["p1"]
        self.assertEqual(p1["zones"]["hand"]["cards"], ["secret-hand"])
        self.assertEqual(p1["sideboard"], ["secret-sideboard"])
        self.assertEqual(view["battlefield"][0]["cardId"], "secret-field")
        self.assertFalse(self.session.can_act_on_zone("judge-client", "judge", "p1", "graveyard"))

    def test_spectator_log_removes_card_identity_but_judge_log_keeps_it(self):
        self.session.add_log("p1", "move_card", {"cardId": "secret-hand", "fromZone": "hand", "toZone": "deck"})
        spectator_entry = self.session.serialize_log("spectator")["entries"][0]
        player_entry = self.session.serialize_for("p2", "player")["recentLog"][0]
        judge_entry = self.session.serialize_log("judge")["entries"][0]
        self.assertNotIn("cardId", spectator_entry["details"])
        self.assertNotIn("cardId", player_entry["details"])
        self.assertEqual(judge_entry["details"]["cardId"], "secret-hand")
        self.assertEqual(judge_entry["sequence"], 1)
        self.assertEqual(judge_entry["turn"], 1)

    def test_tournament_deck_validation_is_server_authoritative(self):
        card_ids = [f"card-{index}" for index in range(30)]
        points = {card_id: 10 for card_id in card_ids}
        points.update({"side-card": 1, "banned-card": 1, "restricted-a": 1, "restricted-b": 1})
        policy = {
            "bannedCardIds": ["banned-card"],
            "restrictedGroups": [{
                "id": "restricted-1", "name": "Opening tutors",
                "cardIds": ["restricted-a", "restricted-b"],
            }],
        }
        labels = {"banned-card": "Freenya (082)", "restricted-a": "Ponder (267)", "restricted-b": "Martyrize (284)"}
        self.assertIsNone(validate_tournament_deck(card_ids, ["side-card"], points))
        self.assertIn("30 unique", validate_tournament_deck(card_ids[:-1], [], points))
        duplicated = card_ids[:-1] + [card_ids[0]]
        self.assertIn("30 unique", validate_tournament_deck(duplicated, [], points))
        expensive = dict(points)
        expensive.update({card_id: 20 for card_id in card_ids})
        self.assertIn("500 points", validate_tournament_deck(card_ids, [], expensive))
        self.assertIn("both", validate_tournament_deck(card_ids, [card_ids[0]], points))
        self.assertIn("Freenya (082)", validate_tournament_deck(card_ids, ["banned-card"], points, policy, labels))
        self.assertIn("Opening tutors", validate_tournament_deck(card_ids, ["restricted-a", "restricted-b"], points, policy, labels))
        self.assertIsNone(validate_tournament_deck(card_ids, ["restricted-a"], points, policy, labels))

    def test_tournament_search_alert_tracks_shuffle_and_is_private_to_staff(self):
        alert = self.session.record_search("p1", "p1", "deck")
        self.assertEqual(alert["status"], "pending")
        self.assertEqual(self.session.tournament_summary("judge")["auditAlerts"][0]["severity"], "warning")
        self.assertEqual(self.session.tournament_summary("organizer")["auditAlerts"][0]["status"], "pending")
        self.assertEqual(self.session.tournament_summary("player")["auditAlerts"], [])
        self.assertEqual(self.session.tournament_summary("spectator")["auditAlerts"], [])
        resolved = self.session.resolve_search("p1", "p1", "deck")
        self.assertEqual(resolved["status"], "resolved")
        self.assertEqual(self.session.pending_searches, {})

    def test_tournament_search_becomes_critical_when_play_continues(self):
        self.session.record_search("p1", "p1", "deck")
        escalated = self.session.escalate_pending_searches("p1", "draw")
        self.assertEqual(len(escalated), 1)
        self.assertEqual(escalated[0]["status"], "unshuffled")
        self.assertEqual(escalated[0]["severity"], "critical")
        self.assertEqual(escalated[0]["followupAction"], "draw")


if __name__ == "__main__":
    unittest.main()
