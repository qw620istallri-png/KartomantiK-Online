import os
import json
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

SERVER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server"))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from session import ADVANCED_PHASES, Session, validate_tournament_deck


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

    def test_exile_is_face_down_to_opponents_but_visible_to_owner_and_judge(self):
        self.p1["zones"]["exile"] = ["card-a"]
        self.p1["zoneOwners"]["exile"] = {"card-a": "p1"}
        own = self.session.serialize_for("p1", "player")["players"]["p1"]["zones"]["exile"]
        opponent = self.session.serialize_for("p2", "player")["players"]["p1"]["zones"]["exile"]
        judge = self.session.serialize_for("judge", "judge")["players"]["p1"]["zones"]["exile"]
        spectator = self.session.serialize_for("spectator", "spectator")["players"]["p1"]["zones"]["exile"]
        self.assertEqual(own["cards"], ["card-a"])
        self.assertEqual(judge["cards"], ["card-a"])
        self.assertEqual(opponent, {"count": 1})
        self.assertEqual(spectator, {"count": 1})

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
        self.assertEqual(len(self.session.phase_sequence()), 15)


class StandardOpeningTests(unittest.TestCase):
    def test_second_validated_deck_draws_both_opening_hands(self):
        card_ids = [f"card-{index}" for index in range(60)]
        session = Session(card_points={card_id: 1 for card_id in card_ids})
        p1 = session.get_or_create_player("p1", "P1", seat=0)
        p2 = session.get_or_create_player("p2", "P2", seat=1)
        for player, deck_cards in ((p1, card_ids[:30]), (p2, card_ids[30:])):
            player["zones"]["deck"] = list(deck_cards)
            player["zoneOwners"]["deck"] = {card_id: player["id"] for card_id in deck_cards}
            player["deckDefinition"] = {"groups": [{"kind": "deck", "cardIds": deck_cards}]}

        error, first = session.confirm_casual_deck("p1")

        self.assertIsNone(error)
        self.assertFalse(first["started"])
        self.assertEqual(first["draws"], {})
        self.assertEqual(p1["zones"]["hand"], [])
        self.assertEqual(p2["zones"]["hand"], [])

        error, second = session.confirm_casual_deck("p2")

        self.assertIsNone(error)
        self.assertTrue(second["started"])
        self.assertEqual(second["draws"], {"p1": 7, "p2": 7})
        self.assertEqual(len(p1["zones"]["hand"]), 7)
        self.assertEqual(len(p2["zones"]["hand"]), 7)
        self.assertCountEqual(session.rules_engine["openingHandPlayerIds"], ["p1", "p2"])

    def test_reimport_before_second_confirmation_clears_first_confirmation(self):
        card_ids = [f"card-{index}" for index in range(60)]
        session = Session(card_points={card_id: 1 for card_id in card_ids})
        p1 = session.get_or_create_player("p1", "P1", seat=0)
        session.get_or_create_player("p2", "P2", seat=1)
        p1["zones"]["deck"] = card_ids[:30]
        p1["zoneOwners"]["deck"] = {card_id: "p1" for card_id in card_ids[:30]}
        p1["deckDefinition"] = {"groups": [{"kind": "deck", "cardIds": card_ids[:30]}]}
        self.assertIsNone(session.confirm_casual_deck("p1")[0])

        session.reset_rules_pregame_player("p1")

        self.assertNotIn("p1", session.rules_engine["deckConfirmedPlayerIds"])


class AssistedRulesTests(unittest.TestCase):
    def make_session(self):
        manifestation_ids = {f"m-{index}" for index in range(20)} | {"captured"}
        card_rules = {
            **{card_id: {"type": "manifestation", "power": 1, "temperaments": ["phlegmatic"]}
               for card_id in manifestation_ids},
            "will-ephemeral": {"type": "ephemeral_will", "cost": 1, "powerCost": "{G}", "temperaments": ["phlegmatic"]},
            "will-persistent": {"type": "persistent_will", "cost": 2, "powerCost": "{G}{G}", "temperaments": ["phlegmatic"]},
        }
        session = Session(
            rules_beta=True,
            card_points={"captured": 20},
            manifestation_ids=manifestation_ids,
            card_rules=card_rules,
        )
        p1 = session.get_or_create_player("p1", "P1", seat=0)
        p2 = session.get_or_create_player("p2", "P2", seat=1)
        session.rules_engine["deckConfirmedPlayerIds"] = ["p1", "p2"]
        session.phase_tracker["index"] = 1  # recovery_draw
        return session, p1, p2

    @staticmethod
    def fill_deck(player, card_ids):
        player["zones"]["deck"] = list(card_ids)
        player["zoneOwners"]["deck"] = {card_id: player["id"] for card_id in card_ids}

    def test_beta_starts_with_detailed_phases_locked_on(self):
        session, _p1, _p2 = self.make_session()
        self.assertTrue(session.phase_tracker["enabled"])
        self.assertTrue(session.phase_tracker["advanced"])
        session.configure_phases(enabled=False, advanced=False)
        self.assertTrue(session.phase_tracker["enabled"])
        self.assertTrue(session.phase_tracker["advanced"])

    def test_both_decks_must_be_validated_before_automatic_opening_hands(self):
        card_ids = [f"card-{index}" for index in range(60)]
        session = Session(rules_beta=True, card_points={card_id: 1 for card_id in card_ids})
        p1 = session.get_or_create_player("p1", "P1", seat=0)
        p2 = session.get_or_create_player("p2", "P2", seat=1)
        for player, deck_cards in ((p1, card_ids[:30]), (p2, card_ids[30:])):
            self.fill_deck(player, deck_cards)
            player["deckDefinition"] = {"groups": [{"kind": "deck", "cardIds": deck_cards}]}

        error, _result = session.draw_opening_hand("p1")
        self.assertIn("validate", error)
        self.assertIsNone(session.set_rules_deck_confirmed("p1", True)[0])
        error, _result = session.draw_opening_hand("p1")
        self.assertIn("Both players", error)
        error, result = session.set_rules_deck_confirmed("p2", True)
        self.assertIsNone(error)
        self.assertEqual(result["opening"]["draws"], {"p1": 7, "p2": 7})
        self.assertCountEqual(
            session.rules_engine["openingMulliganRequiredPlayerIds"], ["p1", "p2"]
        )
        repeated_error, _result = session.draw_opening_hand("p1")
        self.assertIn("already", repeated_error)
        locked_error, _result = session.set_rules_deck_confirmed("p1", False)
        self.assertIn("locked", locked_error)

    def test_repeated_deck_confirmation_does_not_repeat_opening_sequence(self):
        card_ids = [f"m-{index}" for index in range(60)]
        session = Session(
            rules_beta=True,
            card_points={card_id: 1 for card_id in card_ids},
            manifestation_ids=set(card_ids),
            card_rules={card_id: {"type": "manifestation"} for card_id in card_ids},
        )
        p1 = session.get_or_create_player("p1", "P1", seat=0)
        p2 = session.get_or_create_player("p2", "P2", seat=1)
        for player, deck_cards in ((p1, card_ids[:30]), (p2, card_ids[30:])):
            self.fill_deck(player, deck_cards)
            player["deckDefinition"] = {"groups": [{"kind": "deck", "cardIds": deck_cards}]}

        first_error, first = session.set_rules_deck_confirmed("p1", True)
        repeated_error, repeated = session.set_rules_deck_confirmed("p1", True)

        self.assertIsNone(first_error)
        self.assertFalse(first["opening"]["prepared"])
        self.assertIsNone(repeated_error)
        self.assertTrue(repeated["alreadyConfirmed"])
        self.assertIsNone(repeated["opening"])
        self.assertEqual(p1["zones"]["hand"], [])

    def test_first_manifestations_are_hidden_then_revealed_together(self):
        session, _p1, _p2 = self.make_session()
        session.phase_tracker["index"] = session.phase_sequence().index("confrontation_choose")
        session.card_rules["m-1"]["power"] = 1
        session.card_rules["m-2"]["power"] = 3
        first = {"id": "first-p1", "ownerId": "p1", "cardId": "m-1", "faceUp": True}
        second = {"id": "first-p2", "ownerId": "p2", "cardId": "m-2", "faceUp": True}
        session.battlefield.extend([first, second])
        self.assertIsNone(session.register_first_manifestation("p1", first))
        self.assertIsNone(session.register_first_manifestation("p2", second))
        self.assertFalse(first["faceUp"])
        self.assertFalse(second["faceUp"])
        self.assertFalse(session.validate_first_manifestation("p1")[1]["revealed"])
        result = session.validate_first_manifestation("p2")[1]
        self.assertTrue(result["selectionComplete"])
        self.assertFalse(result["revealed"])
        self.assertFalse(first["faceUp"])
        self.assertFalse(second["faceUp"])
        self.assertEqual(session.current_phase_id(), "confrontation_before_revelation")
        session.pass_rules_priority("p1")
        advance_error, advance = session.pass_rules_priority("p2")
        self.assertIsNone(advance_error)
        self.assertEqual(advance["revealedItemIds"], ["first-p1", "first-p2"])
        self.assertTrue(first["faceUp"])
        self.assertTrue(second["faceUp"])
        self.assertEqual(session.current_phase_id(), "confrontation_reveal")
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p1")

    def test_first_manifestation_validation_can_be_cancelled_before_opponent(self):
        session, _p1, _p2 = self.make_session()
        session.phase_tracker["index"] = session.phase_sequence().index("confrontation_choose")
        first = {"id": "first-p1", "ownerId": "p1", "cardId": "m-1", "faceUp": True}
        session.battlefield.append(first)
        self.assertIsNone(session.register_first_manifestation("p1", first))
        self.assertTrue(session.validate_first_manifestation("p1")[1]["validated"])
        cancelled = session.validate_first_manifestation("p1", validated=False)[1]
        self.assertFalse(cancelled["validated"])
        self.assertFalse(cancelled["revealed"])
        self.assertNotIn("p1", session.rules_engine["firstManifestationValidatedPlayerIds"])
        self.assertFalse(session.validate_first_manifestation("p1")[1]["revealed"])

    def test_first_priority_pass_can_be_cancelled(self):
        session, _p1, _p2 = self.make_session()
        session.rules_engine["priorityPlayerId"] = "p1"
        self.assertEqual(session.pass_rules_priority("p1")[1]["status"], "passed")
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p2")
        self.assertEqual(session.pass_rules_priority("p1", passed=False)[1]["status"], "cancelled")
        self.assertEqual(session.rules_engine["priorityPasses"], [])
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p1")

    def test_each_player_can_draw_one_opening_hand_without_triggering_recovery(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker["index"] = 0  # recovery_start
        self.fill_deck(p1, [f"m-{index}" for index in range(10)])
        self.fill_deck(p2, [f"m-{index}" for index in range(10, 20)])

        first_error, first = session.draw_opening_hand("p1")
        second_error, second = session.draw_opening_hand("p2")

        self.assertIsNone(first_error)
        self.assertIsNone(second_error)
        self.assertEqual(first["count"], 7)
        self.assertEqual(second["count"], 7)
        self.assertEqual(len(p1["zones"]["hand"]), 7)
        self.assertEqual(len(p2["zones"]["hand"]), 7)
        self.assertCountEqual(session.rules_engine["openingHandPlayerIds"], ["p1", "p2"])
        self.assertIsNone(session.rules_engine["recoveryDrawTurn"])
        self.assertFalse(session.ended)

        repeated_error, repeated = session.draw_opening_hand("p1")
        self.assertIn("already", repeated_error)
        self.assertIsNone(repeated)

    def test_opening_hand_limit_is_checked_before_and_after_the_draw(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = 0
        self.fill_deck(p1, [f"m-{index}" for index in range(10)])
        timings = []

        def opening_limit(_player_id, default_limit, timing):
            timings.append((default_limit, timing))
            return 8 if timing == "after_draw" else 7

        session.rules_opening_hand_limit = opening_limit
        error, result = session.draw_opening_hand("p1")

        self.assertIsNone(error)
        self.assertEqual(timings, [(7, "before_draw"), (7, "after_draw")])
        self.assertEqual(result, {"count": 8, "handLimit": 8})
        self.assertEqual(len(p1["zones"]["hand"]), 8)

    def test_opening_hand_is_rejected_after_the_first_recovery_start_step(self):
        session, p1, _p2 = self.make_session()
        self.fill_deck(p1, [f"m-{index}" for index in range(7)])

        error, result = session.draw_opening_hand("p1")

        self.assertIn("first Recovery start step", error)
        self.assertIsNone(result)
        self.assertEqual(p1["zones"]["hand"], [])

    def test_reset_clears_opening_hand_tracking(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = 0
        self.fill_deck(p1, [f"m-{index}" for index in range(7)])
        session.draw_opening_hand("p1")
        session.rules_engine["openingMulliganRequiredPlayerIds"] = ["p1"]
        session.mulligan_opening_hand("p1")

        session.reset_phase_tracker()

        self.assertEqual(session.rules_engine["openingHandPlayerIds"], [])
        self.assertEqual(session.rules_engine["mulliganPlayerIds"], [])
        self.assertEqual(session.rules_engine["openingMulliganRequiredPlayerIds"], [])
        self.assertEqual(session.rules_engine["openingMulliganFailedPlayerIds"], [])
        self.assertEqual(session.rules_engine["readyPlayerIds"], [])
        self.assertIsNone(session.rules_engine["recoveryMulliganTurn"])
        self.assertEqual(session.rules_engine["recoveryMulliganPlayerIds"], [])
        self.assertEqual(session.rules_engine["recoveryMulliganRequiredPlayerIds"], [])
        self.assertEqual(session.rules_engine["recoveryMulliganFailedPlayerIds"], [])

    def test_opening_mulligan_redraws_once_and_costs_ten_points(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = 0
        p1["zones"]["hand"] = [f"will-{index}" for index in range(7)]
        p1["zoneOwners"]["hand"] = {card_id: "p1" for card_id in p1["zones"]["hand"]}
        self.fill_deck(p1, [f"m-{index}" for index in range(7)])
        session.rules_engine["openingHandPlayerIds"] = ["p1"]
        session.rules_engine["openingMulliganRequiredPlayerIds"] = ["p1"]

        with patch("session.random.shuffle", lambda _cards: None):
            error, result = session.mulligan_opening_hand("p1")

        self.assertIsNone(error)
        self.assertEqual(result["count"], 7)
        self.assertEqual(result["scoreCost"], 10)
        self.assertTrue(result["playable"])
        self.assertFalse(result["started"])
        self.assertEqual(p1["score"], -10)
        self.assertEqual(len(p1["zones"]["hand"]), 7)
        self.assertEqual(len(p1["zones"]["deck"]), 7)
        repeated_error, repeated = session.mulligan_opening_hand("p1")
        self.assertIn("already taken", repeated_error)
        self.assertIsNone(repeated)
        self.assertEqual(p1["score"], -10)

    def test_valid_opening_hands_wait_for_both_players_to_keep_them(self):
        card_ids = [f"m-{index}" for index in range(60)]
        card_rules = {
            card_id: {"type": "manifestation", "power": 1, "temperaments": ["phlegmatic"]}
            for card_id in card_ids
        }
        session = Session(
            rules_beta=True,
            card_points={card_id: 1 for card_id in card_ids},
            manifestation_ids=set(card_ids),
            card_rules=card_rules,
        )
        p1 = session.get_or_create_player("p1", "P1", seat=0)
        p2 = session.get_or_create_player("p2", "P2", seat=1)
        for player, deck_cards in ((p1, card_ids[:30]), (p2, card_ids[30:])):
            self.fill_deck(player, deck_cards)
            player["deckDefinition"] = {"groups": [{"kind": "deck", "cardIds": deck_cards}]}

        self.assertIsNone(session.set_rules_deck_confirmed("p1", True)[0])
        error, result = session.set_rules_deck_confirmed("p2", True)

        self.assertIsNone(error)
        self.assertFalse(result["opening"]["started"])
        self.assertEqual(session.current_phase_id(), "recovery_start")
        self.assertEqual(session.rules_engine["readyPlayerIds"], [])
        first_ready_error, first_ready = session.set_rules_ready("p1")
        self.assertIsNone(first_ready_error)
        self.assertFalse(first_ready["started"])
        second_ready_error, second_ready = session.set_rules_ready("p2")
        self.assertIsNone(second_ready_error)
        self.assertTrue(second_ready["started"])
        self.assertEqual(session.current_phase_id(), "recovery_end")
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p1")
        self.assertEqual(session.rules_engine["readyPlayerIds"], ["p1", "p2"])
        self.assertEqual(len(p1["zones"]["hand"]), 7)
        self.assertEqual(len(p2["zones"]["hand"]), 7)

    def test_playable_opening_hand_may_take_one_voluntary_mulligan_for_ten_points(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker["index"] = 0
        p1["zones"]["hand"] = [f"m-{index}" for index in range(7)]
        p1["zoneOwners"]["hand"] = {card_id: "p1" for card_id in p1["zones"]["hand"]}
        self.fill_deck(p1, [f"m-{index}" for index in range(7, 14)])
        self.fill_deck(p2, [f"m-{index}" for index in range(14, 20)])
        session.rules_engine["openingHandPlayerIds"] = ["p1", "p2"]
        session.rules_engine["readyPlayerIds"] = ["p2"]

        with patch("session.random.shuffle", lambda _cards: None):
            error, result = session.mulligan_opening_hand("p1")

        self.assertIsNone(error)
        self.assertFalse(result["required"])
        self.assertTrue(result["playable"])
        self.assertFalse(result["started"])
        self.assertEqual(p1["score"], -10)
        self.assertNotIn("p1", session.rules_engine["readyPlayerIds"])
        repeated_error, repeated = session.mulligan_opening_hand("p1")
        self.assertIn("already taken", repeated_error)
        self.assertIsNone(repeated)
        ready_error, ready = session.set_rules_ready("p1")
        self.assertIsNone(ready_error)
        self.assertTrue(ready["started"])

    def test_untyped_extension_card_defers_first_manifestation_validation_to_players(self):
        session, p1, _p2 = self.make_session()
        session.manifestation_ids.discard("inner-deserts-001")
        session.card_rules["inner-deserts-001"] = {
            "type": "placeholder", "placeholder": True,
            "canBeFirstManifestation": True,
        }
        p1["zones"]["hand"] = ["inner-deserts-001", "will-ephemeral"]
        p1["zoneOwners"]["hand"] = {
            "inner-deserts-001": "p1", "will-ephemeral": "p1",
        }

        self.assertTrue(session.rules_opening_hand_is_playable("p1"))
        self.assertTrue(session.rules_card_can_be_first_manifestation("inner-deserts-001"))
        self.assertFalse(session.rules_card_can_be_first_manifestation("will-ephemeral"))

        session.phase_tracker["index"] = session.phase_sequence().index("confrontation_choose")
        item = {
            "id": "manual-inner-desert-first", "ownerId": "p1",
            "cardId": "inner-deserts-001", "faceUp": True,
        }
        self.assertIsNone(session.register_first_manifestation("p1", item))
        self.assertFalse(item["faceUp"])

    def test_required_mulligan_freezes_both_players_then_waits_for_the_new_hand(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker["index"] = 0
        session.rules_engine["openingHandPlayerIds"] = ["p1", "p2"]
        session.rules_engine["readyPlayerIds"] = ["p2"]
        session.rules_engine["openingMulliganRequiredPlayerIds"] = ["p1"]
        p1["zones"]["hand"] = [f"will-{index}" for index in range(7)]
        p1["zoneOwners"]["hand"] = {card_id: "p1" for card_id in p1["zones"]["hand"]}
        self.fill_deck(p1, [f"m-{index}" for index in range(7)])
        self.fill_deck(p2, [f"m-{index}" for index in range(7, 14)])

        with patch("session.random.shuffle", lambda _cards: None):
            error, result = session.mulligan_opening_hand("p1")

        self.assertIsNone(error)
        self.assertTrue(result["playable"])
        self.assertFalse(result["started"])
        self.assertEqual(session.current_phase_id(), "recovery_start")
        self.assertEqual(session.rules_engine["readyPlayerIds"], ["p2"])
        ready_error, ready = session.set_rules_ready("p1")
        self.assertIsNone(ready_error)
        self.assertTrue(ready["started"])
        self.assertEqual(session.current_phase_id(), "recovery_end")

    def test_invalid_required_mulligan_ends_game_as_defeat(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker["index"] = 0
        session.rules_engine["openingHandPlayerIds"] = ["p1", "p2"]
        session.rules_engine["readyPlayerIds"] = ["p2"]
        session.rules_engine["openingMulliganRequiredPlayerIds"] = ["p1"]
        invalid_cards = [f"will-{index}" for index in range(14)]
        p1["zones"]["hand"] = invalid_cards[:7]
        p1["zoneOwners"]["hand"] = {card_id: "p1" for card_id in invalid_cards[:7]}
        self.fill_deck(p1, invalid_cards[7:])
        self.fill_deck(p2, [f"m-{index}" for index in range(7)])

        with patch("session.random.shuffle", lambda _cards: None):
            error, result = session.mulligan_opening_hand("p1")

        self.assertIsNone(error)
        self.assertFalse(result["playable"])
        self.assertFalse(result["started"])
        self.assertTrue(session.ended)
        self.assertEqual(result["outcome"]["loserIds"], ["p1"])
        self.assertEqual(result["outcome"]["winnerIds"], ["p2"])

    def test_two_required_mulligans_stay_frozen_until_both_resolve(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker["index"] = 0
        session.rules_engine["openingHandPlayerIds"] = ["p1", "p2"]
        session.rules_engine["openingMulliganRequiredPlayerIds"] = ["p1", "p2"]
        for offset, player in ((0, p1), (20, p2)):
            invalid_cards = [f"will-{offset + index}" for index in range(14)]
            player["zones"]["hand"] = invalid_cards[:7]
            player["zoneOwners"]["hand"] = {
                card_id: player["id"] for card_id in invalid_cards[:7]
            }
            self.fill_deck(player, invalid_cards[7:])

        with patch("session.random.shuffle", lambda _cards: None):
            first_error, first_result = session.mulligan_opening_hand("p1")
            self.assertIsNone(first_error)
            self.assertFalse(session.ended)
            self.assertIsNone(first_result["outcome"])
            second_error, second_result = session.mulligan_opening_hand("p2")

        self.assertIsNone(second_error)
        self.assertTrue(session.ended)
        self.assertTrue(second_result["outcome"]["draw"])
        self.assertCountEqual(second_result["outcome"]["loserIds"], ["p1", "p2"])
        self.assertEqual(second_result["outcome"]["winnerIds"], [])

    def test_ready_message_cannot_bypass_opening_validation(self):
        session, _p1, _p2 = self.make_session()
        error, result = session.set_rules_ready("p1")
        self.assertIn("before the match begins", error)
        self.assertIsNone(result)

    def test_recovery_refills_both_players_before_checking_game_end(self):
        session, p1, p2 = self.make_session()
        self.fill_deck(p1, ["m-0", "m-1"])
        self.fill_deck(p2, [f"m-{index}" for index in range(2, 12)])
        p1["zones"]["receptacle"] = ["captured"]
        p1["zoneOwners"]["receptacle"] = {"captured": "p2"}
        p1["score"] = 5

        error, result = session.resolve_recovery_draw()

        self.assertIsNone(error)
        self.assertEqual(result["draws"], {"p1": 2, "p2": 7})
        self.assertEqual(len(p1["zones"]["hand"]), 2)
        self.assertEqual(len(p2["zones"]["hand"]), 7)
        self.assertEqual(len(p2["zones"]["deck"]), 3)
        self.assertTrue(session.ended)
        self.assertEqual(result["incompletePlayerIds"], ["p1"])
        self.assertEqual(result["outcome"]["scores"]["p1"]["total"], 25)
        self.assertEqual(result["outcome"]["scores"]["p2"]["deckBonus"], 15)

    def test_complete_recovery_hands_advance_before_revelation(self):
        session, p1, p2 = self.make_session()
        self.fill_deck(p1, [f"m-{index}" for index in range(7)])
        self.fill_deck(p2, [f"m-{index}" for index in range(7, 14)])

        error, result = session.resolve_recovery_draw()

        self.assertIsNone(error)
        self.assertFalse(session.ended)
        self.assertIsNone(result["outcome"])
        self.assertTrue(result["advanced"])
        self.assertEqual(session.current_phase_id(), "recovery_end")
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p1")
        repeated_error, repeated = session.resolve_recovery_draw()
        self.assertIn("Recovery draw step", repeated_error)
        self.assertIsNone(repeated)

    def test_recovery_without_playable_manifestation_freezes_both_players(self):
        session, p1, p2 = self.make_session()
        self.fill_deck(p1, [f"will-a-{index}" for index in range(7)])
        self.fill_deck(p2, [f"m-{index}" for index in range(7)])

        error, result = session.resolve_recovery_draw()

        self.assertIsNone(error)
        self.assertFalse(session.ended)
        self.assertFalse(result["advanced"])
        self.assertEqual(result["mulliganRequiredPlayerIds"], ["p1"])
        self.assertTrue(session.rules_recovery_mulligan_active())
        self.assertEqual(session.current_phase_id(), "recovery_draw")
        self.assertIsNone(session.rules_engine["priorityPlayerId"])
        pass_error, pass_result = session.pass_rules_priority("p2")
        self.assertIn("Recovery Mulligan", pass_error)
        self.assertIsNone(pass_result)

    def test_mandatory_recovery_mulligan_is_free_and_resumes_automatically(self):
        session, p1, p2 = self.make_session()
        invalid_hand = [f"will-hand-{index}" for index in range(7)]
        p1["zones"]["hand"] = invalid_hand
        p1["zoneOwners"]["hand"] = {card_id: "p1" for card_id in invalid_hand}
        self.fill_deck(p1, [f"m-{index}" for index in range(7)])
        self.fill_deck(p2, [f"m-{index}" for index in range(7, 14)])
        session.resolve_recovery_draw()

        with patch("session.random.shuffle", lambda _cards: None):
            error, result = session.mulligan_recovery_hand("p1")

        self.assertIsNone(error)
        self.assertTrue(result["playable"])
        self.assertTrue(result["resumed"])
        self.assertEqual(result["scoreCost"], 0)
        self.assertEqual(p1["score"], 0)
        self.assertEqual(session.current_phase_id(), "recovery_end")
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p1")
        self.assertFalse(session.rules_recovery_mulligan_active())

    def test_invalid_mandatory_recovery_mulligan_is_a_defeat(self):
        session, p1, p2 = self.make_session()
        invalid_hand = [f"will-hand-{index}" for index in range(7)]
        p1["zones"]["hand"] = invalid_hand
        p1["zoneOwners"]["hand"] = {card_id: "p1" for card_id in invalid_hand}
        self.fill_deck(p1, [f"will-deck-{index}" for index in range(7)])
        self.fill_deck(p2, [f"m-{index}" for index in range(7)])
        session.resolve_recovery_draw()

        with patch("session.random.shuffle", lambda _cards: None):
            error, result = session.mulligan_recovery_hand("p1")

        self.assertIsNone(error)
        self.assertFalse(result["playable"])
        self.assertFalse(result["resumed"])
        self.assertTrue(session.ended)
        self.assertEqual(result["outcome"]["reason"], "invalid_recovery_hand_after_mulligan")
        self.assertEqual(result["outcome"]["loserIds"], ["p1"])
        self.assertEqual(result["outcome"]["winnerIds"], ["p2"])

    def test_new_turn_runs_recovery_automatically_and_keeps_before_revelation_priority(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index("end_expire")
        session.rules_engine["priorityPlayerId"] = "p1"
        session.rules_engine["lastConfrontationWinnerId"] = "p2"
        self.fill_deck(p1, [f"m-{index}" for index in range(7)])
        self.fill_deck(p2, [f"m-{index}" for index in range(7, 14)])

        self.assertEqual(session.pass_rules_priority("p1")[1]["status"], "passed")
        error, result = session.pass_rules_priority("p2")

        self.assertIsNone(error)
        self.assertEqual(result["status"], "advanced")
        self.assertEqual(result["turn"], 2)
        self.assertEqual(result["phaseId"], "recovery_end")
        self.assertEqual(result["automaticRecovery"]["draws"], {"p1": 7, "p2": 7})
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p2")

    def test_beginning_of_turn_trigger_resolves_before_automatic_recovery(self):
        session, p1, p2 = self.make_session()
        session.card_rules["incubator"] = {
            "type": "manifestation",
            "triggeredAbilities": [{
                "id": "gain-ten",
                "trigger": {"event": "beginning_of_turn", "zone": "interzone"},
                "result": {"kind": "score_owner", "value": 10},
            }],
        }
        session.battlefield = [{
            "id": "incubator-field", "ownerId": "p1", "cardId": "incubator",
            "faceUp": True, "fieldZone": "interzone", "counters": {},
        }]
        session.phase_tracker["index"] = ADVANCED_PHASES.index("end_expire")
        session.rules_engine["priorityPlayerId"] = "p1"
        self.fill_deck(p1, [f"m-{index}" for index in range(7)])
        self.fill_deck(p2, [f"m-{index}" for index in range(7, 14)])

        session.pass_rules_priority("p1")
        error, transition = session.pass_rules_priority("p2")

        self.assertIsNone(error)
        self.assertEqual(transition["phaseId"], "recovery_start")
        self.assertIsNone(transition["automaticRecovery"])
        self.assertEqual(len(transition["beginningTriggeredActions"]), 1)
        self.assertEqual(len(session.rules_engine["actionStack"]), 1)
        self.assertEqual(p1["score"], 0)

        session.pass_rules_priority("p2")
        error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error)
        self.assertEqual(resolution["action"]["effectResult"]["delta"], 10)
        self.assertEqual(p1["score"], 10)
        self.assertEqual(session.current_phase_id(), "recovery_start")

        session.pass_rules_priority("p2")
        error, recovery = session.pass_rules_priority("p1")
        self.assertIsNone(error)
        self.assertEqual(recovery["phaseId"], "recovery_end")
        self.assertEqual(recovery["automaticRecovery"]["draws"], {"p1": 7, "p2": 7})

    def test_beginning_of_turn_zone_condition_is_enforced(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["incubator"] = {
            "type": "manifestation",
            "triggeredAbilities": [{
                "id": "gain-ten",
                "trigger": {"event": "beginning_of_turn", "zone": "interzone"},
                "result": {"kind": "score_owner", "value": 10},
            }],
        }
        session.phase_tracker["turn"] = 2
        session.phase_tracker["index"] = ADVANCED_PHASES.index("recovery_start")
        session.battlefield = [{
            "id": "incubator-field", "ownerId": "p1", "cardId": "incubator",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }]

        self.assertEqual(session.queue_rules_beginning_turn_triggers(), [])
        self.assertEqual(session.queue_rules_beginning_turn_triggers(), [])

    def test_wandering_veteran_grants_a_turn_permission_without_triggering(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["veteran"] = {
            "type": "manifestation", "power": 4, "temperaments": ["choleric"],
            "triggeredAbilities": [],
            "playPermissions": [{
                "id": "support-from-limbo-this-turn",
                "playPermission": {
                    "conditionEvent": "beginning_of_turn",
                    "requiredZone": "graveyard",
                    "playFromZone": "graveyard",
                    "phaseIds": ["confrontation_reaction"],
                    "asSupport": True,
                    "temperamentOverride": "hollow",
                    "winAsSupportDestination": "exile",
                },
            }],
        }
        p1["zones"]["graveyard"] = ["veteran"]
        p1["zoneOwners"]["graveyard"] = {"veteran": "p1"}
        session.phase_tracker["turn"] = 2
        session.phase_tracker["index"] = ADVANCED_PHASES.index("recovery_start")

        permissions = session.grant_rules_beginning_turn_permissions()

        self.assertEqual(session.queue_rules_beginning_turn_triggers(), [])
        self.assertEqual(len(session.rules_engine["actionStack"]), 0)
        self.assertEqual(len(permissions), 1)
        self.assertEqual(permissions[0]["cardId"], "veteran")
        self.assertEqual(permissions[0]["temperamentOverride"], "hollow")
        self.assertEqual(permissions[0]["winAsSupportDestination"], "exile")
        self.assertEqual(
            session.serialize_for("p1", "player")["rulesEngine"]["playPermissions"][0]["cardId"],
            "veteran",
        )

    def test_wandering_veteran_permission_requires_reaction_priority_and_current_limbo_card(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["veteran"] = {
            "type": "manifestation", "power": 4, "temperaments": ["choleric"],
            "playPermissions": [{
                "id": "support-from-limbo-this-turn",
                "playPermission": {
                    "conditionEvent": "beginning_of_turn", "requiredZone": "graveyard",
                    "playFromZone": "graveyard", "phaseIds": ["confrontation_reaction"],
                    "asSupport": True, "temperamentOverride": "hollow",
                },
            }],
        }
        p1["zones"]["graveyard"] = ["veteran"]
        p1["zoneOwners"]["graveyard"] = {"veteran": "p1"}
        session.phase_tracker["turn"] = 2
        session.grant_rules_beginning_turn_permissions()

        error, _permission = session.rules_zone_play_permission("p1", "p1", "graveyard", "veteran")
        self.assertIn("confrontation", error)

        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
        session.rules_engine["priorityPlayerId"] = "p2"
        error, _permission = session.rules_zone_play_permission("p1", "p1", "graveyard", "veteran")
        self.assertIn("priority", error)

        session.rules_engine["priorityPlayerId"] = "p1"
        error, permission = session.rules_zone_play_permission("p1", "p1", "graveyard", "veteran")
        self.assertIsNone(error)
        self.assertTrue(permission["asSupport"])

        error, action = session.declare_rules_action(
            "p1", "Wandering Veteran in Support", kind="play_card", as_support=True,
            source={"cardId": "veteran", "zone": "graveyard", "containerId": "p1"},
            placement={"x": 420, "y": 510},
        )
        self.assertIsNone(error)
        self.assertTrue(action["sourceOnStack"])
        self.assertNotIn("veteran", p1["zones"]["graveyard"])
        self.assertEqual(session.rules_engine["playPermissions"], [])
        session.pass_rules_priority("p2")
        error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error)
        item = session.find_battlefield_item(resolution["action"]["sourceResolution"]["itemId"])
        self.assertTrue(item["isSupport"])
        self.assertEqual(session.rules_manifestation_characteristics(item)["temperament"], "hollow")

    def test_wandering_veteran_entering_limbo_after_turn_start_gets_no_permission(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["veteran"] = {
            "type": "manifestation",
            "playPermissions": [{
                "id": "support-from-limbo-this-turn",
                "playPermission": {
                    "conditionEvent": "beginning_of_turn", "requiredZone": "graveyard",
                    "playFromZone": "graveyard", "phaseIds": ["confrontation_reaction"],
                },
            }],
        }
        session.phase_tracker["turn"] = 2
        self.assertEqual(session.grant_rules_beginning_turn_permissions(), [])
        p1["zones"]["graveyard"] = ["veteran"]
        p1["zoneOwners"]["graveyard"] = {"veteran": "p1"}
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
        session.rules_engine["priorityPlayerId"] = "p1"

        error, permission = session.rules_zone_play_permission("p1", "p1", "graveyard", "veteran")

        self.assertIn("beginning-of-turn", error)
        self.assertIsNone(permission)

    def test_shared_recovery_choice_pauses_each_player_in_seat_order(self):
        session, p1, p2 = self.make_session()
        session.card_rules["dunes"] = {
            "type": "persistent_will",
            "triggeredAbilities": [{
                "id": "shared-choice",
                "trigger": {"event": "beginning_of_turn"},
                "result": {"kind": "each_player_recovery_choice"},
            }],
        }
        session.battlefield = [{
            "id": "dunes-field", "ownerId": "p1", "cardId": "dunes",
            "faceUp": True, "counters": {},
        }]
        session.phase_tracker["index"] = ADVANCED_PHASES.index("end_expire")
        session.rules_engine["priorityPlayerId"] = "p1"
        p1_cards = [f"m-{index}" for index in range(10)]
        p2_cards = [f"m-{index}" for index in range(10, 20)]
        self.fill_deck(p1, p1_cards)
        self.fill_deck(p2, p2_cards)

        session.pass_rules_priority("p1")
        session.pass_rules_priority("p2")
        session.pass_rules_priority("p2")
        error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(error)
        self.assertEqual(resolution["action"]["effectResult"]["choiceKind"], "recovery_shared_choice")
        first_choice = session.rules_engine["pendingChoice"]
        self.assertEqual(first_choice["playerId"], "p1")
        self.assertIn("discard_deck_bottom_3", first_choice["options"])

        error, first = session.resolve_rules_choice(
            "p1", first_choice["id"], option="discard_deck_bottom_3"
        )
        self.assertIsNone(error)
        self.assertEqual(first["cardIds"], p1_cards[-3:][::-1])
        self.assertEqual(len(p1["zones"]["deck"]), 7)
        second_choice = session.rules_engine["pendingChoice"]
        self.assertEqual(second_choice["playerId"], "p2")

        error, second = session.resolve_rules_choice(
            "p2", second_choice["id"], option="lose_points_10"
        )
        self.assertIsNone(error)
        self.assertEqual(second["scoreDelta"], -10)
        self.assertEqual(p2["score"], -10)
        self.assertIsNone(session.rules_engine["pendingChoice"])

    def test_shared_recovery_choice_disallows_three_card_option_for_short_deck(self):
        session, p1, _p2 = self.make_session()
        self.fill_deck(p1, ["m-0", "m-1"])
        action = {
            "id": "dunes-action", "controllerId": "p1",
            "source": {"cardId": "dunes"},
            "ability": {"result": {"kind": "each_player_recovery_choice"}},
        }

        result = session.apply_rules_action_result(action)
        choice = session.rules_engine["pendingChoice"]

        self.assertEqual(result["choiceKind"], "recovery_shared_choice")
        self.assertEqual(choice["options"], ["lose_points_10"])
        error, denied = session.resolve_rules_choice(
            "p1", choice["id"], option="discard_deck_bottom_3"
        )
        self.assertIn("valid Recovery effect", error)
        self.assertIsNone(denied)

    def test_recovery_draw_is_rejected_outside_its_rulebook_step(self):
        session, p1, p2 = self.make_session()
        self.fill_deck(p1, ["m-0"])
        self.fill_deck(p2, ["m-1"])
        session.phase_tracker["index"] = 0

        error, result = session.resolve_recovery_draw()

        self.assertIn("Recovery draw step", error)
        self.assertIsNone(result)
        self.assertEqual(p1["zones"]["hand"], [])
        self.assertEqual(p2["zones"]["hand"], [])

    def test_rules_outcome_is_public_in_the_serialized_state(self):
        session, p1, p2 = self.make_session()
        self.fill_deck(p1, ["m-0"])
        self.fill_deck(p2, ["m-1"])
        session.resolve_recovery_draw()

        state = session.serialize_for("p1", "player")

        self.assertTrue(state["rulesEngine"]["enabled"])
        self.assertEqual(state["rulesEngine"]["outcome"]["reason"], "incomplete_recovery_hand")

    def test_priority_holder_alone_can_add_a_public_stack_action(self):
        session, _p1, _p2 = self.make_session()

        error, action = session.declare_rules_action("p1", "  Activate   Freenya  ")

        self.assertIsNone(error)
        self.assertEqual(action["label"], "Activate Freenya")
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p2")
        self.assertEqual(session.rules_engine["actionStack"], [action])
        denied, denied_action = session.declare_rules_action("p1", "Act again")
        self.assertIn("priority", denied)
        self.assertIsNone(denied_action)
        public_state = session.serialize_for("p2", "player")
        self.assertEqual(public_state["rulesEngine"]["actionStack"][0]["label"], "Activate Freenya")

    def test_two_priority_passes_resolve_only_the_top_action(self):
        session, _p1, _p2 = self.make_session()
        _, first = session.declare_rules_action("p1", "First action")
        _, second = session.declare_rules_action("p2", "Response")

        error, first_pass = session.pass_rules_priority("p1")
        self.assertIsNone(error)
        self.assertEqual(first_pass["status"], "passed")
        error, resolution = session.pass_rules_priority("p2")

        self.assertIsNone(error)
        self.assertEqual(resolution["status"], "resolved")
        self.assertEqual(resolution["action"]["id"], second["id"])
        self.assertEqual(session.rules_engine["actionStack"], [first])
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p2")

    def test_declared_ephemeral_will_leaves_hand_then_moves_to_limbo_on_resolution(self):
        session, p1, _p2 = self.make_session()
        p1["zones"]["hand"] = ["will-ephemeral", "m-0"]
        p1["zoneOwners"]["hand"] = {card_id: "p1" for card_id in p1["zones"]["hand"]}
        error, _action = session.declare_rules_action(
            "p1", "Play an Ephemeral Will", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            payment_card_ids=["m-0"],
        )
        self.assertIsNone(error)

        move_error, _ = session.move_zone_card(
            "p1", "hand", "p1", "graveyard", "will-ephemeral"
        )
        self.assertIn("not found", move_error)
        self.assertNotIn("will-ephemeral", p1["zones"]["hand"])
        self.assertTrue(session.rules_engine["actionStack"][-1]["sourceOnStack"])

        session.pass_rules_priority("p2")
        error, result = session.pass_rules_priority("p1")

        self.assertIsNone(error)
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["action"]["sourceResolution"]["status"], "moved")
        self.assertEqual(p1["zones"]["hand"], [])
        self.assertEqual(p1["zones"]["graveyard"], ["will-ephemeral", "m-0"])

    def test_resolved_persistent_will_enters_field_at_its_sanitized_drop_position(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index("end_actions")
        session.card_rules["m-0"].update({"power": 2, "temperaments": ["melancholic"]})
        session.card_rules["m-1"].update({"power": 1, "temperaments": ["melancholic"]})
        session.card_rules["m-2"]["power"] = 3
        session.card_rules["will-persistent"]["powerCost"] = "{P}{P}"
        session.card_rules["will-persistent"]["playedAbilities"] = [{
            "id": "persistent-power-link", "action": "play_card",
            "targets": {"min": 1, "max": 1, "cardType": "manifestation"},
            "ongoingEffect": {
                "kind": "power_modifier", "value": -2,
                "duration": "while_source_and_target_on_field",
            },
        }]
        session.card_rules["will-persistent"]["triggeredAbilities"] = [{
            "id": "persistent-enter-draw",
            "trigger": {"event": "enters_field", "visibility": "face_up"},
            "result": {"kind": "draw_owner", "value": 1},
        }]
        p1["zones"]["hand"] = ["will-persistent", "m-0", "m-1"]
        p1["zoneOwners"]["hand"] = {card_id: "p1" for card_id in p1["zones"]["hand"]}
        session.battlefield = [{
            "id": "persistent-target", "ownerId": "p2", "cardId": "m-2",
            "x": 200, "y": 200, "faceUp": True, "rotation": 0, "counters": {},
        }]

        error, action = session.declare_rules_action(
            "p1", "Play a Persistent Will", kind="play_card",
            source={"cardId": "will-persistent", "zone": "hand"},
            targets=[{"kind": "card", "itemId": "persistent-target", "cardId": "m-2"}],
            payment_card_ids=["m-0"], ability_id="persistent-power-link",
            placement={"x": 99999, "y": "not-a-coordinate"},
        )

        self.assertIsNone(error)
        self.assertEqual(action["placement"], {"x": 1741.0, "y": 670.0})
        self.assertNotIn("will-persistent", p1["zones"]["hand"])
        session.pass_rules_priority("p2")
        resolve_error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(resolve_error)
        self.assertEqual(resolution["status"], "resolved")
        source_result = resolution["action"]["sourceResolution"]
        self.assertEqual(source_result["destination"], "battlefield")
        self.assertEqual((source_result["x"], source_result["y"]), (1741.0, 670.0))
        self.assertEqual(p1["zones"]["hand"], ["m-1"])
        self.assertEqual(p1["zones"]["graveyard"], ["m-0"])
        self.assertEqual(len(session.battlefield), 2)
        self.assertEqual(session.battlefield[-1]["cardId"], "will-persistent")
        self.assertEqual(session.rules_manifestation_characteristics(session.battlefield[0])["power"], 1)
        self.assertEqual(len(session.rules_engine["ongoingEffects"]), 1)
        self.assertEqual(
            session.rules_engine["ongoingEffects"][0]["source"]["itemId"],
            source_result["itemId"],
        )
        self.assertEqual(len(resolution["triggeredActions"]), 1)
        self.assertEqual(session.rules_engine["actionStack"][-1]["ability"]["id"], "persistent-enter-draw")

    def test_two_priority_passes_with_empty_stack_advance_the_step(self):
        session, _p1, _p2 = self.make_session()
        starting_index = session.phase_tracker["index"]

        self.assertEqual(session.pass_rules_priority("p1")[1]["status"], "passed")
        error, result = session.pass_rules_priority("p2")

        self.assertIsNone(error)
        self.assertEqual(result["status"], "advanced")
        self.assertEqual(session.phase_tracker["index"], starting_index + 1)
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p1")
        self.assertEqual(session.rules_engine["priorityPasses"], [])

    def test_each_confrontation_step_gives_priority_to_the_lower_power_total(self):
        session, _p1, _p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reveal")
        session.card_rules["m-0"]["power"] = 1
        session.card_rules["m-1"]["power"] = 3
        session.battlefield = [
            {"id": "fight-p1", "ownerId": "p1", "cardId": "m-0", "faceUp": True, "fieldZone": "confrontation", "counters": {}},
            {"id": "fight-p2", "ownerId": "p2", "cardId": "m-1", "faceUp": True, "fieldZone": "confrontation", "counters": {}},
        ]

        session.pass_rules_priority("p1")
        error, result = session.pass_rules_priority("p2")

        self.assertIsNone(error)
        self.assertEqual(result["phaseId"], "confrontation_immediate")
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p1")

        session.card_rules["m-0"]["power"] = 4
        session.card_rules["m-1"]["power"] = 1
        session.pass_rules_priority("p1")
        error, result = session.pass_rules_priority("p2")

        self.assertIsNone(error)
        self.assertEqual(result["phaseId"], "confrontation_entry")
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p2")

    def test_support_cards_use_the_stack_and_resolve_last_in_first_out(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker["index"] = session.phase_sequence().index("confrontation_reaction")
        session.card_rules["m-0"].update({"supportFromHand": True, "power": 1})
        session.card_rules["m-1"].update({"supportFromHand": True, "power": 1})
        session.card_rules["m-2"]["power"] = 1
        session.card_rules["m-3"]["power"] = 4
        p1["zones"]["hand"] = ["m-0"]
        p1["zoneOwners"]["hand"] = {"m-0": "p1"}
        p2["zones"]["hand"] = ["m-1"]
        p2["zoneOwners"]["hand"] = {"m-1": "p2"}
        session.battlefield = [
            {"id": "base-p1", "ownerId": "p1", "cardId": "m-2", "faceUp": True, "fieldZone": "confrontation", "counters": {}},
            {"id": "base-p2", "ownerId": "p2", "cardId": "m-3", "faceUp": True, "fieldZone": "confrontation", "counters": {}},
        ]
        session.rules_engine["priorityPlayerId"] = "p1"

        error, first = session.declare_rules_action(
            "p1", "P1 Support", kind="play_card", as_support=True,
            source={"cardId": "m-0", "zone": "hand"}, placement={"x": 400, "y": 500},
        )
        self.assertIsNone(error)
        self.assertNotIn("m-0", p1["zones"]["hand"])
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p2")
        self.assertFalse(any(item.get("cardId") == "m-0" for item in session.battlefield))

        error, response = session.declare_rules_action(
            "p2", "P2 Support response", kind="play_card", as_support=True,
            source={"cardId": "m-1", "zone": "hand"}, placement={"x": 900, "y": 500},
        )
        self.assertIsNone(error)
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p1")
        self.assertEqual([action["id"] for action in session.rules_engine["actionStack"]], [first["id"], response["id"]])

        session.pass_rules_priority("p1")
        error, resolution = session.pass_rules_priority("p2")
        self.assertIsNone(error)
        self.assertEqual(resolution["action"]["id"], response["id"])
        self.assertTrue(session.battlefield[-1]["isSupport"])
        self.assertEqual(session.battlefield[-1]["cardId"], "m-1")
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p2")

        session.pass_rules_priority("p2")
        error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error)
        self.assertEqual(resolution["action"]["id"], first["id"])
        self.assertEqual(session.battlefield[-1]["cardId"], "m-0")
        self.assertTrue(session.battlefield[-1]["isSupport"])
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p1")

    def test_interzone_support_leaves_the_board_for_the_stack_then_returns_on_resolution(self):
        session, _p1, _p2 = self.make_session()
        session.phase_tracker["index"] = session.phase_sequence().index("confrontation_reaction")
        session.card_rules["m-0"]["supportFromInterzone"] = True
        session.card_rules["m-0"]["power"] = 1
        session.card_rules["m-1"]["power"] = 3
        waiting = {
            "id": "waiting", "ownerId": "p1", "cardId": "m-0", "faceUp": True,
            "x": 360, "y": 520, "fieldZone": "interzone", "counters": {},
        }
        session.battlefield = [
            waiting,
            {"id": "strong", "ownerId": "p2", "cardId": "m-1", "faceUp": True, "fieldZone": "confrontation", "counters": {}},
        ]
        session.rules_engine["priorityPlayerId"] = "p1"

        error, action = session.declare_rules_action(
            "p1", "Move into Support", kind="play_card", as_support=True,
            source={"cardId": "m-0", "zone": "battlefield", "itemId": "waiting"},
            placement={"x": 500, "y": 500},
        )
        self.assertIsNone(error)
        self.assertTrue(action["sourceOnStack"])
        self.assertIsNone(session.find_battlefield_item("waiting"))
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p2")

        session.pass_rules_priority("p2")
        error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error)
        restored = session.find_battlefield_item("waiting")
        self.assertIsNotNone(restored)
        self.assertTrue(restored["isSupport"])
        self.assertEqual(restored["fieldZone"], "confrontation")
        self.assertEqual(resolution["action"]["sourceResolution"]["fromZone"], "battlefield")
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p1")

    def test_reset_returns_an_unresolved_stack_source_to_its_owner_hand(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["will-ephemeral"].update({"cost": 0, "powerCost": ""})
        p1["zones"]["hand"] = ["will-ephemeral"]
        p1["zoneOwners"]["hand"] = {"will-ephemeral": "p1"}
        error, _action = session.declare_rules_action(
            "p1", "Pending Will", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
        )
        self.assertIsNone(error)
        self.assertEqual(p1["zones"]["hand"], [])

        session.reset_phase_tracker()

        self.assertEqual(p1["zones"]["hand"], ["will-ephemeral"])
        self.assertEqual(session.rules_engine["actionStack"], [])

    def test_reset_clears_stack_and_restores_first_player_priority(self):
        session, _p1, _p2 = self.make_session()
        session.declare_rules_action("p1", "Pending action")

        session.reset_phase_tracker()

        self.assertEqual(session.rules_engine["actionStack"], [])
        self.assertEqual(session.rules_engine["priorityPasses"], [])
        self.assertIsNone(session.rules_engine["lastResolvedAction"])
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p1")

    def test_structured_play_reveals_only_declared_source_target_and_tribute(self):
        session, p1, _p2 = self.make_session()
        self.fill_deck(p1, [])
        p1["zones"]["hand"] = ["will-ephemeral", "m-0", "m-1"]
        p1["zoneOwners"]["hand"] = {card_id: "p1" for card_id in p1["zones"]["hand"]}
        session.battlefield = [{
            "id": "target-1", "ownerId": "p2", "cardId": "m-2",
            "x": 200, "y": 100, "faceUp": True, "rotation": 0, "counters": {},
        }]

        error, action = session.declare_rules_action(
            "p1",
            "Play the Will",
            kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            target="P2's confrontation card",
            targets=[{"kind": "card", "itemId": "target-1", "cardId": "m-2"}],
            cost_note="Use one green Tribute",
            payment_card_ids=["m-0"],
        )

        self.assertIsNone(error)
        self.assertEqual(action["kind"], "play_card")
        self.assertEqual(action["source"]["cardId"], "will-ephemeral")
        self.assertEqual(action["target"], "P2's confrontation card")
        self.assertEqual(action["targets"], [{
            "kind": "card", "itemId": "target-1", "cardId": "m-2", "ownerId": "p2",
        }])
        self.assertEqual(action["cost"]["tributeCardIds"], ["m-0"])
        self.assertTrue(action["cost"]["tributePaid"])
        public = session.serialize_for("p2", "player")["rulesEngine"]["actionStack"][0]
        self.assertEqual(public["source"]["cardId"], "will-ephemeral")
        self.assertEqual(public["targets"][0]["itemId"], "target-1")
        self.assertEqual(public["cost"]["tributeCardIds"], ["m-0"])
        self.assertNotIn("m-1", repr(public))
        self.assertEqual(p1["zones"]["hand"], ["m-1"])
        self.assertEqual(p1["zones"]["graveyard"], ["m-0"])

    def test_tribute_payment_supports_two_identical_manifestations(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["will-ephemeral"].update({"cost": 2, "powerCost": "{G}{G}"})
        p1["zones"]["hand"] = ["will-ephemeral", "m-0", "m-0"]
        p1["zoneOwners"]["hand"] = {"will-ephemeral": "p1", "m-0": "p1"}

        error, action = session.declare_rules_action(
            "p1",
            "Pay with two copies",
            kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            payment_card_ids=["m-0", "m-0"],
        )

        self.assertIsNone(error)
        self.assertEqual(action["cost"]["tributeCardIds"], ["m-0", "m-0"])
        self.assertEqual(p1["zones"]["hand"], [])
        self.assertEqual(p1["zones"]["graveyard"], ["m-0", "m-0"])

    def test_matching_excess_essence_is_spent_before_manifestations(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["will-ephemeral"].update({"cost": 2, "powerCost": "{G}{G}"})
        p1["zones"]["hand"] = ["will-ephemeral", "m-0"]
        p1["zoneOwners"]["hand"] = {card_id: "p1" for card_id in p1["zones"]["hand"]}
        session.tokens = [{
            "id": "green-essence", "ownerId": "p1", "x": 0, "y": 0,
            "isEssence": True, "temperament": "phlegmatic", "isNeutralCounter": False,
            "label": "", "color": "#000", "counters": {"essence": 1},
        }]

        error, action = session.declare_rules_action(
            "p1", "Pay with Essence first", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            payment_card_ids=["m-0"],
        )

        self.assertIsNone(error)
        self.assertEqual(action["cost"]["essenceSpent"][0]["amount"], 1)
        self.assertEqual(session.tokens, [])
        self.assertEqual(p1["zones"]["graveyard"], ["m-0"])

    def test_essence_can_pay_the_full_printed_tribute_without_manifestations(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["will-ephemeral"].update({"cost": 2, "powerCost": "{G}{G}"})
        p1["zones"]["hand"] = ["will-ephemeral"]
        p1["zoneOwners"]["hand"] = {"will-ephemeral": "p1"}
        session.tokens = [{
            "id": "green-essence", "ownerId": "p1", "x": 0, "y": 0,
            "isEssence": True, "temperament": "phlegmatic", "isNeutralCounter": False,
            "label": "", "color": "#000", "counters": {"essence": 2},
        }]

        error, action = session.declare_rules_action(
            "p1", "Pay only with Essence", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
        )

        self.assertIsNone(error)
        self.assertEqual(action["cost"]["tributeCardIds"], [])
        self.assertEqual(action["cost"]["essenceSpent"][0]["amount"], 2)
        self.assertEqual(session.tokens, [])
        self.assertEqual(p1["zones"]["hand"], [])

    def test_transcendent_essence_pays_a_colored_printed_tribute(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["will-ephemeral"].update({"cost": 2, "powerCost": "{G}{G}"})
        p1["zones"]["hand"] = ["will-ephemeral"]
        p1["zoneOwners"]["hand"] = {"will-ephemeral": "p1"}
        session.tokens = [{
            "id": "transcendent-essence", "ownerId": "p1", "x": 0, "y": 0,
            "isEssence": True, "temperament": "transcendent", "isNeutralCounter": False,
            "label": "", "color": "#000", "counters": {"essence": 2},
        }]

        error, action = session.declare_rules_action(
            "p1", "Pay with Transcendent Essence", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
        )

        self.assertIsNone(error)
        self.assertEqual(action["cost"]["essenceSpent"], [{
            "tokenId": "transcendent-essence", "temperament": "transcendent",
            "amount": 2, "pays": "phlegmatic",
        }])
        self.assertEqual(session.tokens, [])

    def test_hollow_tribute_accepts_any_manifestation_but_hollow_essence_is_restricted(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["will-ephemeral"].update({
            "cost": 2, "powerCost": "{H}{H}", "temperaments": ["hollow"],
        })
        session.card_rules["m-1"].update({"power": 2, "temperaments": ["choleric"]})
        p1["zones"]["hand"] = ["will-ephemeral", "m-1"]
        p1["zoneOwners"]["hand"] = {card_id: "p1" for card_id in p1["zones"]["hand"]}

        error, action = session.declare_rules_action(
            "p1", "Pay Hollow with Choleric", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            payment_card_ids=["m-1"],
        )

        self.assertIsNone(error)
        self.assertEqual(action["cost"]["tributeCardIds"], ["m-1"])
        self.assertEqual(p1["zones"]["graveyard"], ["m-1"])

        session, p1, _p2 = self.make_session()
        p1["zones"]["hand"] = ["will-ephemeral", "m-0"]
        p1["zoneOwners"]["hand"] = {card_id: "p1" for card_id in p1["zones"]["hand"]}
        session.tokens = [{
            "id": "hollow-essence", "ownerId": "p1", "x": 0, "y": 0,
            "isEssence": True, "temperament": "hollow", "isNeutralCounter": False,
            "label": "", "color": "#000", "counters": {"essence": 1},
        }]

        error, action = session.declare_rules_action(
            "p1", "Hollow cannot pay green", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            payment_card_ids=["m-0"],
        )

        self.assertIsNone(error)
        self.assertEqual(action["cost"]["essenceSpent"], [])
        self.assertEqual(session.tokens[0]["counters"]["essence"], 1)

    def test_overpaid_manifestation_generates_excess_essence(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["will-ephemeral"].update({"cost": 2, "powerCost": "{G}{G}"})
        session.card_rules["m-0"]["power"] = 3
        p1["zones"]["hand"] = ["will-ephemeral", "m-0"]
        p1["zoneOwners"]["hand"] = {card_id: "p1" for card_id in p1["zones"]["hand"]}

        error, action = session.declare_rules_action(
            "p1", "Generate one excess Essence", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            payment_card_ids=["m-0"],
        )

        self.assertIsNone(error)
        self.assertEqual(action["cost"]["excessEssence"], [{"temperament": "phlegmatic", "amount": 1}])
        self.assertEqual(len(session.tokens), 1)
        self.assertEqual(session.tokens[0]["temperament"], "phlegmatic")
        self.assertEqual(session.tokens[0]["counters"]["essence"], 1)

    def test_printed_tribute_rejects_wrong_temperament_and_redundant_cards(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["will-ephemeral"].update({"cost": 2, "powerCost": "{G}{G}"})
        session.card_rules["m-0"].update({"power": 2, "temperaments": ["phlegmatic"]})
        session.card_rules["m-1"].update({"power": 1, "temperaments": ["choleric"]})
        p1["zones"]["hand"] = ["will-ephemeral", "m-0", "m-1"]
        p1["zoneOwners"]["hand"] = {card_id: "p1" for card_id in p1["zones"]["hand"]}

        wrong_error, _ = session.declare_rules_action(
            "p1", "Wrong color", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            payment_card_ids=["m-1"],
        )
        redundant_error, _ = session.declare_rules_action(
            "p1", "Too many cards", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            payment_card_ids=["m-0", "m-1"],
        )

        self.assertIn("full printed Tribute", wrong_error)
        self.assertIn("superfluous", redundant_error)
        self.assertEqual(p1["zones"]["hand"], ["will-ephemeral", "m-0", "m-1"])

    def test_printed_tribute_allows_any_non_superfluous_selection(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["will-ephemeral"].update({"cost": 2, "powerCost": "{G}{G}"})
        session.card_rules["m-0"].update({"power": 1, "temperaments": ["phlegmatic"]})
        session.card_rules["m-1"].update({"power": 1, "temperaments": ["phlegmatic"]})
        session.card_rules["m-2"].update({"power": 2, "temperaments": ["phlegmatic"]})
        p1["zones"]["hand"] = ["will-ephemeral", "m-0", "m-1", "m-2"]
        p1["zoneOwners"]["hand"] = {card_id: "p1" for card_id in p1["zones"]["hand"]}

        error, action = session.declare_rules_action(
            "p1", "Try two weaker cards", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            payment_card_ids=["m-0", "m-1"],
        )

        self.assertIsNone(error)
        self.assertIsNotNone(action)
        self.assertCountEqual(p1["zones"]["graveyard"], ["m-0", "m-1"])

    def test_structured_target_must_still_be_face_up_on_the_battlefield(self):
        session, p1, _p2 = self.make_session()
        p1["zones"]["hand"] = ["m-0"]
        p1["zoneOwners"]["hand"] = {"m-0": "p1"}
        session.battlefield = [{
            "id": "hidden-target", "ownerId": "p2", "cardId": "m-3",
            "x": 0, "y": 0, "faceUp": False, "rotation": 0, "counters": {},
        }]

        error, action = session.declare_rules_action(
            "p1",
            "Target hidden card",
            targets=[{"kind": "card", "itemId": "hidden-target", "cardId": "m-3"}],
            payment_card_ids=["m-0"],
        )

        self.assertIn("no longer face up", error)
        self.assertIsNone(action)
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p1")
        self.assertEqual(p1["zones"]["hand"], ["m-0"])
        self.assertEqual(p1["zones"]["graveyard"], [])

    def test_structured_action_rejects_invalid_tribute_and_hidden_field_source(self):
        session, p1, _p2 = self.make_session()
        p1["zones"]["hand"] = ["will-ephemeral", "will-persistent"]
        invalid_payment, _ = session.declare_rules_action(
            "p1",
            "Play",
            kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            payment_card_ids=["will-persistent"],
        )
        self.assertIn("Manifestations", invalid_payment)

        session.battlefield = [{
            "id": "hidden-source", "ownerId": "p1", "cardId": "m-0",
            "x": 0, "y": 0, "faceUp": False, "rotation": 0, "counters": {},
        }]
        hidden_error, _ = session.declare_rules_action(
            "p1",
            "Hidden effect",
            kind="activated_effect",
            source={"cardId": "m-0", "zone": "battlefield", "itemId": "hidden-source"},
        )
        self.assertIn("face-down", hidden_error)

    def test_encoded_activated_effect_pays_tribute_and_exhausts_its_source(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["m-0"]["activatedAbilities"] = [{
            "id": "test-ability",
            "tribute": "{H}{H}",
            "exhaustSource": True,
            "targets": {"min": 1, "max": 1, "cardType": "manifestation"},
        }]
        session.card_rules["m-1"]["power"] = 2
        p1["zones"]["hand"] = ["m-1"]
        p1["zoneOwners"]["hand"] = {"m-1": "p1"}
        source = {
            "id": "source-1", "ownerId": "p1", "cardId": "m-0",
            "x": 0, "y": 0, "faceUp": True, "rotation": 0, "counters": {},
        }
        target = {
            "id": "target-1", "ownerId": "p2", "cardId": "m-2",
            "x": 10, "y": 10, "faceUp": True, "rotation": 0, "counters": {},
        }
        session.battlefield = [source, target]

        missing_error, _ = session.declare_rules_action(
            "p1", "Try to skip encoded cost", kind="activated_effect",
            source={"cardId": "m-0", "zone": "battlefield", "itemId": "source-1"},
            targets=[{"kind": "card", "itemId": "target-1", "cardId": "m-2"}],
        )
        forged_error, _ = session.declare_rules_action(
            "p1", "Try a forged ability", kind="activated_effect",
            source={"cardId": "m-0", "zone": "battlefield", "itemId": "source-1"},
            targets=[{"kind": "card", "itemId": "target-1", "cardId": "m-2"}],
            ability_id="free-version",
        )
        self.assertIn("Choose the activated ability", missing_error)
        self.assertIn("Unknown activated ability", forged_error)

        error, action = session.declare_rules_action(
            "p1", "Use encoded effect", kind="activated_effect",
            source={"cardId": "m-0", "zone": "battlefield", "itemId": "source-1"},
            targets=[{"kind": "card", "itemId": "target-1", "cardId": "m-2"}],
            payment_card_ids=["m-1"], ability_id="test-ability",
        )

        self.assertIsNone(error)
        self.assertEqual(action["ability"]["id"], "test-ability")
        self.assertTrue(action["cost"]["sourceExhausted"])
        self.assertEqual(source["rotation"], 90.0)
        self.assertEqual(p1["zones"]["hand"], [])
        self.assertEqual(p1["zones"]["graveyard"], ["m-1"])
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p2")

    def test_encoded_activated_effect_rejects_wrong_target_type_or_exhausted_source_atomically(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["m-0"]["activatedAbilities"] = [{
            "id": "test-ability",
            "tribute": "{H}",
            "exhaustSource": True,
            "targets": {"min": 1, "max": 1, "cardType": "manifestation"},
        }]
        p1["zones"]["hand"] = ["m-1"]
        p1["zoneOwners"]["hand"] = {"m-1": "p1"}
        source = {
            "id": "source-1", "ownerId": "p1", "cardId": "m-0",
            "x": 0, "y": 0, "faceUp": True, "rotation": 0, "counters": {},
        }
        wrong_target = {
            "id": "target-1", "ownerId": "p2", "cardId": "will-persistent",
            "x": 10, "y": 10, "faceUp": True, "rotation": 0, "counters": {},
        }
        session.battlefield = [source, wrong_target]

        target_error, _ = session.declare_rules_action(
            "p1", "Illegal target", kind="activated_effect",
            source={"cardId": "m-0", "zone": "battlefield", "itemId": "source-1"},
            targets=[{"kind": "card", "itemId": "target-1", "cardId": "will-persistent"}],
            payment_card_ids=["m-1"], ability_id="test-ability",
        )
        self.assertIn("different type", target_error)
        self.assertEqual(source["rotation"], 0)
        self.assertEqual(p1["zones"]["hand"], ["m-1"])

        wrong_target["cardId"] = "m-2"
        source["rotation"] = 90
        exhaust_error, _ = session.declare_rules_action(
            "p1", "Already exhausted", kind="activated_effect",
            source={"cardId": "m-0", "zone": "battlefield", "itemId": "source-1"},
            targets=[{"kind": "card", "itemId": "target-1", "cardId": "m-2"}],
            payment_card_ids=["m-1"], ability_id="test-ability",
        )
        self.assertIn("already exhausted", exhaust_error)
        self.assertEqual(p1["zones"]["hand"], ["m-1"])
        self.assertEqual(p1["zones"]["graveyard"], [])

    def test_encoded_ongoing_effect_is_public_and_expires_at_the_next_turn(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["m-2"]["power"] = 3
        session.card_rules["m-0"]["activatedAbilities"] = [{
            "id": "temporary-power-loss",
            "tribute": "{H}",
            "exhaustSource": True,
            "targets": {"min": 1, "max": 1, "cardType": "manifestation"},
            "ongoingEffect": {"kind": "power_modifier", "value": -2, "duration": "until_end_of_turn"},
        }]
        p1["zones"]["hand"] = ["m-1"]
        p1["zoneOwners"]["hand"] = {"m-1": "p1"}
        session.battlefield = [
            {"id": "source-1", "ownerId": "p1", "cardId": "m-0", "x": 0, "y": 0, "faceUp": True, "rotation": 0, "counters": {}},
            {"id": "target-1", "ownerId": "p2", "cardId": "m-2", "x": 10, "y": 10, "faceUp": True, "rotation": 0, "counters": {}},
        ]

        error, action = session.declare_rules_action(
            "p1", "Reduce power", kind="activated_effect",
            source={"cardId": "m-0", "zone": "battlefield", "itemId": "source-1"},
            targets=[{"kind": "card", "itemId": "target-1", "cardId": "m-2"}],
            payment_card_ids=["m-1"], ability_id="temporary-power-loss",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(error)
        self.assertEqual(resolution["status"], "resolved")
        self.assertEqual(len(resolution["action"]["ongoingEffects"]), 1)
        effect = session.serialize_for("p2", "player")["rulesEngine"]["ongoingEffects"][0]
        self.assertEqual(effect["source"]["itemId"], "source-1")
        self.assertEqual(effect["target"]["itemId"], "target-1")
        self.assertEqual(effect["value"], -2)

        session.phase_tracker["index"] = len(session.phase_sequence()) - 1
        session.pass_rules_priority("p2")
        _error, advance = session.pass_rules_priority("p1")
        self.assertEqual(advance["status"], "advanced")
        self.assertEqual(len(advance["expiredEffectIds"]), 1)
        self.assertEqual(session.rules_engine["ongoingEffects"], [])

    def test_encoded_played_will_uses_printed_tribute_and_applies_power_modifier(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["will-ephemeral"]["playedAbilities"] = [{
            "id": "strengthen-power-modifier",
            "action": "play_card",
            "targets": {"min": 1, "max": 1, "cardType": "manifestation"},
            "ongoingEffect": {"kind": "power_modifier", "value": 3, "duration": "until_end_of_turn"},
        }]
        p1["zones"]["hand"] = ["will-ephemeral", "m-0"]
        p1["zoneOwners"]["hand"] = {"will-ephemeral": "p1", "m-0": "p1"}
        session.battlefield = [{
            "id": "target-1", "ownerId": "p2", "cardId": "m-1",
            "x": 10, "y": 10, "faceUp": True, "rotation": 0, "counters": {},
        }]

        missing_error, _missing = session.declare_rules_action(
            "p1", "Strengthen", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            targets=[{"kind": "card", "itemId": "target-1", "cardId": "m-1"}],
            payment_card_ids=["m-0"],
        )
        self.assertIn("Choose the played ability", missing_error)
        self.assertEqual(p1["zones"]["hand"], ["will-ephemeral", "m-0"])

        error, action = session.declare_rules_action(
            "p1", "Strengthen", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            targets=[{"kind": "card", "itemId": "target-1", "cardId": "m-1"}],
            payment_card_ids=["m-0"], ability_id="strengthen-power-modifier",
        )

        self.assertIsNone(error)
        self.assertEqual(action["ability"]["tribute"], None)
        self.assertEqual(action["cost"]["tributeRequirements"], {"phlegmatic": 1})
        self.assertEqual(p1["zones"]["hand"], [])
        self.assertEqual(p1["zones"]["graveyard"], ["m-0"])
        session.pass_rules_priority("p2")
        resolve_error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(resolve_error)
        self.assertEqual(resolution["action"]["sourceResolution"]["status"], "moved")
        self.assertEqual(p1["zones"]["hand"], [])
        self.assertEqual(p1["zones"]["graveyard"], ["will-ephemeral", "m-0"])
        effect = session.rules_engine["ongoingEffects"][0]
        self.assertEqual(effect["target"]["itemId"], "target-1")
        self.assertEqual(effect["kind"], "power_modifier")
        self.assertEqual(effect["value"], 3)
        session.create_rules_ongoing_effects({
            "id": "second-strengthen", "controllerId": "p1",
            "source": {"cardId": "will-ephemeral", "zone": "hand", "itemId": None},
            "targets": [{"kind": "card", "itemId": "target-1", "cardId": "m-1", "ownerId": "p2"}],
            "ability": action["ability"],
        })
        self.assertEqual(len(session.rules_engine["ongoingEffects"]), 2)

    def test_neutralize_targets_a_played_stack_card_and_sends_both_wills_to_limbo(self):
        session, p1, p2 = self.make_session()
        target_card_id = "will-target"
        neutralize_card_id = "will-neutralize"
        session.card_rules[target_card_id] = {
            "type": "ephemeral_will", "cost": 0, "powerCost": "", "temperaments": [],
            "playedAbilities": [],
        }
        session.card_rules[neutralize_card_id] = {
            "type": "ephemeral_will", "cost": 0, "powerCost": "", "temperaments": [],
            "playedAbilities": [{
                "id": "neutralize-stack-card", "action": "play_card",
                "targets": {"kind": "stack_action", "min": 1, "max": 1},
                "result": {"kind": "neutralize_stack_action"},
            }],
        }
        p2["zones"]["hand"] = [target_card_id]
        p2["zoneOwners"]["hand"] = {target_card_id: "p2"}
        p1["zones"]["hand"] = [neutralize_card_id]
        p1["zoneOwners"]["hand"] = {neutralize_card_id: "p1"}
        session.rules_engine["priorityPlayerId"] = "p2"

        target_error, target_action = session.declare_rules_action(
            "p2", "Target Will", kind="play_card",
            source={"cardId": target_card_id, "zone": "hand"},
        )
        self.assertIsNone(target_error)
        self.assertEqual(p2["zones"]["hand"], [])
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p1")

        stale_error, stale_action = session.declare_rules_action(
            "p1", "Neutralize", kind="play_card",
            source={"cardId": neutralize_card_id, "zone": "hand"},
            targets=[{
                "kind": "stack_action", "actionId": "missing-action",
                "cardId": target_card_id,
            }],
            ability_id="neutralize-stack-card",
        )
        self.assertIn("no longer available on the Stack", stale_error)
        self.assertIsNone(stale_action)
        self.assertEqual(p1["zones"]["hand"], [neutralize_card_id])

        neutralize_error, neutralize_action = session.declare_rules_action(
            "p1", "Neutralize", kind="play_card",
            source={"cardId": neutralize_card_id, "zone": "hand"},
            targets=[{
                "kind": "stack_action", "actionId": target_action["id"],
                "cardId": target_card_id,
            }],
            ability_id="neutralize-stack-card",
        )
        self.assertIsNone(neutralize_error)
        self.assertEqual(neutralize_action["targets"], [{
            "kind": "stack_action", "actionId": target_action["id"],
            "cardId": target_card_id, "controllerId": "p2",
        }])
        self.assertEqual(p1["zones"]["hand"], [])
        self.assertEqual([action["id"] for action in session.rules_engine["actionStack"]], [
            target_action["id"], neutralize_action["id"],
        ])

        pass_error, first_pass = session.pass_rules_priority("p2")
        self.assertIsNone(pass_error)
        self.assertEqual(first_pass["status"], "passed")
        resolve_error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(resolve_error)
        self.assertEqual(resolution["status"], "resolved")
        self.assertEqual(resolution["stackDepth"], 0)
        self.assertEqual(resolution["action"]["effectResult"], {
            "kind": "neutralize_stack_action", "status": "neutralized",
            "actionId": target_action["id"], "cardId": target_card_id,
            "controllerId": "p2", "targetKind": "play_card",
            "sourceResolution": {
                "status": "moved", "destination": "graveyard",
                "ownerId": "p2", "cardId": target_card_id,
            },
        })
        self.assertEqual(p1["zones"]["graveyard"], [neutralize_card_id])
        self.assertEqual(p2["zones"]["graveyard"], [target_card_id])
        self.assertEqual(session.rules_engine["actionStack"], [])

    def test_imitate_copies_a_targeted_will_and_can_choose_a_new_target(self):
        session, p1, p2 = self.make_session()
        target_card_id = "will-target"
        imitate_card_id = "will-imitate"
        session.card_rules.update({
            "manifestation-a": {
                "type": "manifestation", "power": 3, "cost": 0,
                "powerCost": "", "temperaments": [], "playedAbilities": [],
            },
            "manifestation-b": {
                "type": "manifestation", "power": 4, "cost": 0,
                "powerCost": "", "temperaments": [], "playedAbilities": [],
            },
            target_card_id: {
                "type": "ephemeral_will", "cost": 0, "powerCost": "", "temperaments": [],
                "playedAbilities": [{
                    "id": "weaken-target", "action": "play_card",
                    "targets": {"kind": "card", "min": 1, "max": 1, "cardType": "manifestation"},
                    "ongoingEffect": {
                        "kind": "power_modifier", "value": -1,
                        "duration": "until_end_of_turn",
                    },
                }],
            },
            imitate_card_id: {
                "type": "ephemeral_will", "cost": 0, "powerCost": "", "temperaments": [],
                "playedAbilities": [{
                    "id": "copy-target-will-on-stack", "action": "play_card",
                    "targets": {
                        "kind": "stack_action", "min": 1, "max": 1,
                        "cardTypes": ["ephemeral_will", "persistent_will"],
                    },
                    "result": {"kind": "copy_stack_action"},
                }],
            },
        })
        session.battlefield = [
            {
                "id": "target-a", "ownerId": "p1", "controllerId": "p1",
                "cardId": "manifestation-a", "x": 20, "y": 30,
                "faceUp": True, "rotation": 0, "counters": {},
            },
            {
                "id": "target-b", "ownerId": "p1", "controllerId": "p1",
                "cardId": "manifestation-b", "x": 60, "y": 30,
                "faceUp": True, "rotation": 0, "counters": {},
            },
        ]
        p2["zones"]["hand"] = [target_card_id]
        p2["zoneOwners"]["hand"] = {target_card_id: "p2"}
        p1["zones"]["hand"] = [imitate_card_id]
        p1["zoneOwners"]["hand"] = {imitate_card_id: "p1"}
        session.rules_engine["priorityPlayerId"] = "p2"

        target_error, target_action = session.declare_rules_action(
            "p2", "Target Will", kind="play_card",
            source={"cardId": target_card_id, "zone": "hand"},
            targets=[{
                "kind": "card", "itemId": "target-a", "cardId": "manifestation-a",
            }],
            ability_id="weaken-target",
        )
        self.assertIsNone(target_error)
        imitate_error, imitate_action = session.declare_rules_action(
            "p1", "Imitate", kind="play_card",
            source={"cardId": imitate_card_id, "zone": "hand"},
            targets=[{
                "kind": "stack_action", "actionId": target_action["id"],
                "cardId": target_card_id,
            }],
            ability_id="copy-target-will-on-stack",
        )
        self.assertIsNone(imitate_error)
        self.assertIsNotNone(imitate_action)

        self.assertIsNone(session.pass_rules_priority("p2")[0])
        resolve_error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(resolve_error)
        self.assertEqual(resolution["action"]["effectResult"]["choiceKind"], "stack_copy_targets")
        self.assertEqual(p1["zones"]["graveyard"], [imitate_card_id])
        self.assertEqual(session.rules_engine["actionStack"], [target_action])
        choice = session.rules_engine["pendingChoice"]
        public_choice = session.serialize_for("p1", "player")["rulesEngine"]["pendingChoice"]
        self.assertNotIn("_copyAction", public_choice)

        choice_error, copied = session.resolve_rules_choice(
            "p1", choice["id"], option="retarget",
            targets=[{
                "kind": "card", "itemId": "target-b", "cardId": "manifestation-b",
            }],
        )
        self.assertIsNone(choice_error)
        self.assertEqual(copied["status"], "copied")
        self.assertFalse(copied["keptOriginalTargets"])
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p2")
        copied_action = session.rules_engine["actionStack"][-1]
        self.assertTrue(copied_action["isStackCopy"])
        self.assertEqual(copied_action["copiedFromActionId"], target_action["id"])
        self.assertEqual(copied_action["controllerId"], "p1")
        self.assertEqual(copied_action["targets"][0]["itemId"], "target-b")
        self.assertEqual(target_action["targets"][0]["itemId"], "target-a")

        self.assertIsNone(session.pass_rules_priority("p2")[0])
        copy_resolve_error, copy_resolution = session.pass_rules_priority("p1")
        self.assertIsNone(copy_resolve_error)
        self.assertEqual(copy_resolution["action"]["sourceResolution"]["status"], "copy_resolved")
        self.assertEqual(session.rules_engine["actionStack"], [target_action])
        self.assertEqual(p1["zones"]["graveyard"], [imitate_card_id])
        self.assertEqual(p2["zones"]["graveyard"], [])
        effect = session.rules_engine["ongoingEffects"][0]
        self.assertEqual(effect["target"]["itemId"], "target-b")
        self.assertEqual(effect["value"], -1)

    def test_imitate_rejects_a_non_will_stack_card(self):
        session, p1, p2 = self.make_session()
        session.card_rules["stack-manifestation"] = {
            "type": "manifestation", "power": 1, "cost": 0,
            "powerCost": "", "temperaments": [], "playedAbilities": [],
        }
        session.card_rules["will-imitate"] = {
            "type": "ephemeral_will", "cost": 0, "powerCost": "", "temperaments": [],
            "playedAbilities": [{
                "id": "copy-target-will-on-stack", "action": "play_card",
                "targets": {
                    "kind": "stack_action", "min": 1, "max": 1,
                    "cardTypes": ["ephemeral_will", "persistent_will"],
                },
                "result": {"kind": "copy_stack_action"},
            }],
        }
        p2["zones"]["hand"] = ["stack-manifestation"]
        p2["zoneOwners"]["hand"] = {"stack-manifestation": "p2"}
        p1["zones"]["hand"] = ["will-imitate"]
        p1["zoneOwners"]["hand"] = {"will-imitate": "p1"}
        session.rules_engine["priorityPlayerId"] = "p2"
        target_error, target_action = session.declare_rules_action(
            "p2", "Manifestation", kind="play_card",
            source={"cardId": "stack-manifestation", "zone": "hand"},
        )
        self.assertIsNone(target_error)

        imitate_error, imitate_action = session.declare_rules_action(
            "p1", "Imitate", kind="play_card",
            source={"cardId": "will-imitate", "zone": "hand"},
            targets=[{
                "kind": "stack_action", "actionId": target_action["id"],
                "cardId": "stack-manifestation",
            }],
            ability_id="copy-target-will-on-stack",
        )
        self.assertIn("different type of Stack card", imitate_error)
        self.assertIsNone(imitate_action)
        self.assertEqual(p1["zones"]["hand"], ["will-imitate"])

    def test_deny_owner_may_decline_payment_and_let_the_stack_card_be_neutralized(self):
        session, p1, p2 = self.make_session()
        target_card_id = "will-target"
        deny_card_id = "will-deny"
        session.card_rules[target_card_id] = {
            "type": "ephemeral_will", "cost": 0, "powerCost": "", "temperaments": [],
            "playedAbilities": [],
        }
        session.card_rules[deny_card_id] = {
            "type": "ephemeral_will", "cost": 0, "powerCost": "", "temperaments": [],
            "playedAbilities": [{
                "id": "deny-stack-card-unless-paid", "action": "play_card",
                "targets": {"kind": "stack_action", "min": 1, "max": 1},
                "result": {
                    "kind": "counter_stack_action_unless_payment", "payment": "{H}{H}",
                    "payer": "owner", "mode": "neutralize",
                },
            }],
        }
        p2["zones"]["hand"] = [target_card_id]
        p2["zoneOwners"]["hand"] = {target_card_id: "p2"}
        p1["zones"]["hand"] = [deny_card_id]
        p1["zoneOwners"]["hand"] = {deny_card_id: "p1"}
        session.rules_engine["priorityPlayerId"] = "p2"

        self.assertIsNone((error := session.declare_rules_action(
            "p2", "Target Will", kind="play_card",
            source={"cardId": target_card_id, "zone": "hand"},
        )[0]))
        target_action = session.rules_engine["actionStack"][0]
        deny_error, deny_action = session.declare_rules_action(
            "p1", "Deny", kind="play_card",
            source={"cardId": deny_card_id, "zone": "hand"},
            targets=[{
                "kind": "stack_action", "actionId": target_action["id"],
                "cardId": target_card_id,
            }],
            ability_id="deny-stack-card-unless-paid",
        )
        self.assertIsNone(deny_error)
        self.assertIsNotNone(deny_action)
        session.pass_rules_priority("p2")
        resolve_error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(resolve_error)
        self.assertEqual(resolution["action"]["effectResult"]["choiceKind"], "stack_counter_payment")
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["playerId"], "p2")
        self.assertEqual(choice["requirements"], {"hollow": 2})
        self.assertEqual(session.rules_engine["actionStack"], [target_action])
        choice_error, declined = session.resolve_rules_choice(
            "p2", choice["id"], option="decline",
        )

        self.assertIsNone(choice_error)
        self.assertEqual(declined["status"], "neutralized")
        self.assertEqual(declined["targetKind"], "play_card")
        self.assertEqual(p1["zones"]["graveyard"], [deny_card_id])
        self.assertEqual(p2["zones"]["graveyard"], [target_card_id])
        self.assertEqual(session.rules_engine["actionStack"], [])
        self.assertIsNone(session.rules_engine["pendingChoice"])

    def test_deny_owner_can_pay_hollow_tribute_and_keep_the_target_on_the_stack(self):
        session, p1, p2 = self.make_session()
        target_card_id = "will-target"
        deny_card_id = "will-deny"
        session.card_rules[target_card_id] = {
            "type": "ephemeral_will", "cost": 0, "powerCost": "", "temperaments": [],
            "playedAbilities": [],
        }
        session.card_rules[deny_card_id] = {
            "type": "ephemeral_will", "cost": 0, "powerCost": "", "temperaments": [],
            "playedAbilities": [{
                "id": "deny-stack-card-unless-paid", "action": "play_card",
                "targets": {"kind": "stack_action", "min": 1, "max": 1},
                "result": {
                    "kind": "counter_stack_action_unless_payment", "payment": "{H}{H}",
                    "payer": "owner", "mode": "neutralize",
                },
            }],
        }
        session.card_rules["m-0"]["power"] = 2
        p2["zones"]["hand"] = [target_card_id, "m-0"]
        p2["zoneOwners"]["hand"] = {target_card_id: "p2", "m-0": "p2"}
        p1["zones"]["hand"] = [deny_card_id]
        p1["zoneOwners"]["hand"] = {deny_card_id: "p1"}
        session.rules_engine["priorityPlayerId"] = "p2"

        _error, target_action = session.declare_rules_action(
            "p2", "Target Will", kind="play_card",
            source={"cardId": target_card_id, "zone": "hand"},
        )
        session.declare_rules_action(
            "p1", "Deny", kind="play_card",
            source={"cardId": deny_card_id, "zone": "hand"},
            targets=[{"kind": "stack_action", "actionId": target_action["id"], "cardId": target_card_id}],
            ability_id="deny-stack-card-unless-paid",
        )
        session.pass_rules_priority("p2")
        session.pass_rules_priority("p1")
        choice = session.rules_engine["pendingChoice"]
        choice_error, paid = session.resolve_rules_choice(
            "p2", choice["id"], ["m-0"], option="pay",
        )

        self.assertIsNone(choice_error)
        self.assertEqual(paid["status"], "paid")
        self.assertEqual(paid["cost"]["tributeRequirements"], {"hollow": 2})
        self.assertEqual(paid["cost"]["tributeCardIds"], ["m-0"])
        self.assertEqual(session.rules_engine["actionStack"], [target_action])
        self.assertEqual(p2["zones"]["graveyard"], ["m-0"])
        self.assertIsNone(session.rules_engine["pendingChoice"])

    def test_ignore_targets_an_effect_not_a_played_card_and_cancels_only_the_effect(self):
        session, p1, p2 = self.make_session()
        ignore_card_id = "will-ignore"
        session.card_rules[ignore_card_id] = {
            "type": "ephemeral_will", "cost": 0, "powerCost": "", "temperaments": [],
            "playedAbilities": [{
                "id": "ignore-stack-effect-unless-paid", "action": "play_card",
                "targets": {"kind": "stack_effect", "min": 1, "max": 1},
                "result": {
                    "kind": "counter_stack_action_unless_payment", "payment": "{H}{H}",
                    "payer": "controller", "mode": "cancel",
                },
            }],
        }
        source_item = {
            "id": "effect-source", "ownerId": "p2", "controllerId": "p2", "cardId": "m-1",
            "x": 100, "y": 100, "faceUp": True, "rotation": 0, "counters": {},
        }
        session.battlefield = [source_item]
        effect_action = {
            "id": "effect-action", "controllerId": "p2", "label": "Triggered effect",
            "kind": "triggered_effect",
            "source": {"cardId": "m-1", "zone": "battlefield", "itemId": "effect-source", "ownerId": "p2"},
            "targets": [], "cost": {}, "phaseId": session.current_phase_id(), "turn": 1,
        }
        session.rules_engine["actionStack"] = [effect_action]
        session.rules_engine["priorityPlayerId"] = "p1"
        p1["zones"]["hand"] = [ignore_card_id]
        p1["zoneOwners"]["hand"] = {ignore_card_id: "p1"}

        wrong_error, _wrong = session.declare_rules_action(
            "p1", "Ignore", kind="play_card",
            source={"cardId": ignore_card_id, "zone": "hand"},
            targets=[{"kind": "stack_action", "actionId": effect_action["id"], "cardId": "m-1"}],
            ability_id="ignore-stack-effect-unless-paid",
        )
        self.assertIn("card is no longer available", wrong_error)
        self.assertEqual(p1["zones"]["hand"], [ignore_card_id])

        ignore_error, _ignore = session.declare_rules_action(
            "p1", "Ignore", kind="play_card",
            source={"cardId": ignore_card_id, "zone": "hand"},
            targets=[{"kind": "stack_effect", "actionId": effect_action["id"], "cardId": "m-1"}],
            ability_id="ignore-stack-effect-unless-paid",
        )
        self.assertIsNone(ignore_error)
        session.pass_rules_priority("p2")
        session.pass_rules_priority("p1")
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["playerId"], "p2")
        choice_error, cancelled = session.resolve_rules_choice(
            "p2", choice["id"], option="decline",
        )

        self.assertIsNone(choice_error)
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(cancelled["targetKind"], "triggered_effect")
        self.assertEqual(session.rules_engine["actionStack"], [])
        self.assertEqual(session.battlefield, [source_item])
        self.assertEqual(p1["zones"]["graveyard"], [ignore_card_id])

    def test_ponder_pays_tribute_then_draws_three_only_on_resolution(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["will-ephemeral"].update({"cost": 1, "powerCost": "{H}"})
        session.card_rules["will-ephemeral"]["playedAbilities"] = [{
            "id": "draw-three-cards", "action": "play_card",
            "targets": {"min": 0, "max": 0},
            "result": {"kind": "draw_owner", "value": 3},
        }]
        session.card_rules["m-0"]["temperaments"] = ["hollow"]
        p1["zones"]["hand"] = ["will-ephemeral", "m-0"]
        p1["zoneOwners"]["hand"] = {"will-ephemeral": "p1", "m-0": "p1"}
        self.fill_deck(p1, ["m-1", "m-2", "m-3", "m-4"])

        error, action = session.declare_rules_action(
            "p1", "Ponder", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            targets=[], payment_card_ids=["m-0"], ability_id="draw-three-cards",
        )

        self.assertIsNone(error)
        self.assertEqual(action["ability"]["result"], {"kind": "draw_owner", "value": 3})
        self.assertEqual(p1["zones"]["hand"], [])
        self.assertEqual(p1["zones"]["graveyard"], ["m-0"])
        self.assertEqual(p1["zones"]["deck"], ["m-1", "m-2", "m-3", "m-4"])
        session.pass_rules_priority("p2")
        resolve_error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(resolve_error)
        self.assertEqual(resolution["action"]["effectResult"], {
            "kind": "draw", "playerId": "p1", "count": 3,
        })
        self.assertEqual(p1["zones"]["hand"], ["m-1", "m-2", "m-3"])
        self.assertEqual(p1["zones"]["deck"], ["m-4"])
        self.assertEqual(p1["zones"]["graveyard"], ["will-ephemeral", "m-0"])

    def test_pray_the_ether_discards_privately_then_draws_two(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["will-ephemeral"].update({"cost": 0, "powerCost": ""})
        session.card_rules["will-ephemeral"]["playedAbilities"] = [{
            "id": "discard-one-then-draw-two", "action": "play_card",
            "targets": {"min": 0, "max": 0},
            "result": {"kind": "discard_hand_owner_then_draw", "discard": 1, "draw": 2},
        }]
        p1["zones"]["hand"] = ["will-ephemeral", "m-0"]
        p1["zoneOwners"]["hand"] = {"will-ephemeral": "p1", "m-0": "p1"}
        self.fill_deck(p1, ["m-1", "m-2", "m-3"])

        error, action = session.declare_rules_action(
            "p1", "Pray the Ether", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            targets=[], ability_id="discard-one-then-draw-two",
        )

        self.assertIsNone(error)
        self.assertEqual(action["ability"]["result"], {
            "kind": "discard_hand_owner_then_draw", "discard": 1, "draw": 2,
        })
        session.pass_rules_priority("p2")
        resolve_error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(resolve_error)
        effect = resolution["action"]["effectResult"]
        self.assertEqual(effect["kind"], "choice_required")
        self.assertEqual(effect["drawAfter"], 2)
        self.assertEqual(p1["zones"]["hand"], ["m-0"])
        self.assertEqual(p1["zones"]["deck"], ["m-1", "m-2", "m-3"])
        pending = session.serialize_for("p1", "player")["rulesEngine"]["pendingChoice"]
        self.assertEqual(pending["drawAfter"], 2)
        self.assertNotIn("cardIds", pending)

        choice_error, result = session.resolve_rules_choice("p1", pending["id"], ["m-0"])

        self.assertIsNone(choice_error)
        self.assertEqual(result["kind"], "discard_then_draw")
        self.assertEqual(result["cardIds"], ["m-0"])
        self.assertEqual(result["drawCount"], 2)
        self.assertEqual(p1["zones"]["hand"], ["m-1", "m-2"])
        self.assertEqual(p1["zones"]["deck"], ["m-3"])
        self.assertEqual(p1["zones"]["graveyard"], ["m-0", "will-ephemeral"])

    def test_pray_the_ether_draws_nothing_when_discard_cannot_be_paid(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["will-ephemeral"].update({"cost": 0, "powerCost": ""})
        session.card_rules["will-ephemeral"]["playedAbilities"] = [{
            "id": "discard-one-then-draw-two", "action": "play_card",
            "targets": {"min": 0, "max": 0},
            "result": {"kind": "discard_hand_owner_then_draw", "discard": 1, "draw": 2},
        }]
        p1["zones"]["hand"] = ["will-ephemeral"]
        p1["zoneOwners"]["hand"] = {"will-ephemeral": "p1"}
        self.fill_deck(p1, ["m-1", "m-2"])
        error, _action = session.declare_rules_action(
            "p1", "Pray the Ether", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            targets=[], ability_id="discard-one-then-draw-two",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        resolve_error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(resolve_error)
        self.assertEqual(resolution["action"]["effectResult"], {
            "kind": "discard_then_draw", "status": "not_paid",
            "playerId": "p1", "count": 0, "cardIds": [], "drawCount": 0,
            "handProof": [], "handProofPlayerId": "p1",
        })
        self.assertEqual(p1["zones"]["hand"], [])
        self.assertEqual(p1["zones"]["deck"], ["m-1", "m-2"])
        self.assertIsNone(session.rules_engine["pendingChoice"])

    def test_encoded_move_target_effect_supports_type_sets_and_deck_positions(self):
        session, p1, p2 = self.make_session()
        session.card_rules["will-ephemeral"]["cost"] = 2
        session.card_rules["will-ephemeral"]["powerCost"] = "{B}{B}"
        session.card_rules["will-ephemeral"]["playedAbilities"] = [{
            "id": "defer-to-deck-top", "action": "play_card",
            "targets": {"min": 1, "max": 1, "cardTypes": ["manifestation", "persistent_will"]},
            "result": {"kind": "move_target", "zone": "deck", "position": "top"},
        }]
        for card_id in ("m-0", "m-1"):
            session.card_rules[card_id]["temperaments"] = ["vitreous"]
        p1["zones"]["hand"] = ["will-ephemeral", "m-0", "m-1"]
        p1["zoneOwners"]["hand"] = {card_id: "p1" for card_id in p1["zones"]["hand"]}
        p2["zones"]["deck"] = ["m-2"]
        p2["zoneOwners"]["deck"] = {"m-2": "p2"}
        session.battlefield = [{
            "id": "persistent-1", "ownerId": "p2", "cardId": "will-persistent",
            "x": 10, "y": 10, "faceUp": True, "rotation": 0, "counters": {},
        }]

        error, action = session.declare_rules_action(
            "p1", "Defer", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            targets=[{"kind": "card", "itemId": "persistent-1", "cardId": "will-persistent"}],
            payment_card_ids=["m-0", "m-1"], ability_id="defer-to-deck-top",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        resolve_error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(resolve_error)
        self.assertEqual(resolution["action"]["effectResult"], {
            "kind": "move_card", "status": "moved", "cardId": "will-persistent",
            "itemId": "persistent-1", "ownerId": "p2", "fromZone": "battlefield",
            "toZone": "deck", "position": "top",
        })
        self.assertEqual(p2["zones"]["deck"], ["will-persistent", "m-2"])
        self.assertEqual(session.battlefield, [])

        session.battlefield = [{
            "id": "manifestation-1", "ownerId": "p2", "cardId": "m-3",
            "x": 10, "y": 10, "faceUp": True, "rotation": 0, "counters": {},
        }]
        bottom_result = session.apply_rules_action_result({
            "controllerId": "p1",
            "targets": [{"kind": "card", "itemId": "manifestation-1", "cardId": "m-3"}],
            "ability": {"result": {"kind": "move_target", "zone": "deck", "position": "bottom"}},
        })
        self.assertEqual(bottom_result["status"], "moved")
        self.assertEqual(p2["zones"]["deck"], ["will-persistent", "m-2", "m-3"])

        missing_result = session.apply_rules_action_result({
            "controllerId": "p1",
            "targets": [{"kind": "card", "itemId": "gone", "cardId": "m-4"}],
            "ability": {"result": {"kind": "move_target", "zone": "deck", "position": "bottom"}},
        })
        self.assertEqual(missing_result["status"], "target_missing")

    def test_encoded_exile_can_target_a_manifestation_in_public_limbo(self):
        session, p1, p2 = self.make_session()
        session.card_rules["will-ephemeral"].update({"cost": 0, "powerCost": ""})
        session.card_rules["will-ephemeral"]["playedAbilities"] = [{
            "id": "exile-manifestation", "action": "play_card",
            "targets": {
                "min": 1, "max": 1, "cardType": "manifestation",
                "zones": ["battlefield", "graveyard"],
            },
            "result": {"kind": "move_target", "zone": "exile", "position": "top", "reason": "exile"},
        }]
        p1["zones"]["hand"] = ["will-ephemeral"]
        p1["zoneOwners"]["hand"] = {"will-ephemeral": "p1"}
        p2["zones"]["graveyard"] = ["m-3"]
        p2["zoneOwners"]["graveyard"] = {"m-3": "p2"}
        p2["zones"]["exile"] = ["m-4"]
        p2["zoneOwners"]["exile"] = {"m-4": "p2"}

        wrong_zone_error, _action = session.declare_rules_action(
            "p1", "Exile invalid target", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            targets=[{
                "kind": "zone_card", "containerId": "p2", "zone": "exile",
                "cardId": "m-4",
            }],
            ability_id="exile-manifestation",
        )
        self.assertIn("public zone", wrong_zone_error)

        error, action = session.declare_rules_action(
            "p1", "Exile", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            targets=[{
                "kind": "zone_card", "containerId": "p2", "zone": "graveyard",
                "cardId": "m-3",
            }],
            ability_id="exile-manifestation",
        )
        self.assertIsNone(error)
        self.assertEqual(action["targets"], [{
            "kind": "zone_card", "zone": "graveyard", "containerId": "p2",
            "cardId": "m-3", "ownerId": "p2",
        }])
        session.pass_rules_priority("p2")
        resolve_error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(resolve_error)
        self.assertEqual(p1["zones"]["graveyard"], ["will-ephemeral"])
        self.assertEqual(p2["zones"]["graveyard"], [])
        self.assertEqual(p2["zones"]["exile"], ["m-3", "m-4"])
        self.assertEqual(resolution["action"]["effectResult"], {
            "kind": "move_card", "status": "moved", "cardId": "m-3",
            "ownerId": "p2", "fromZone": "graveyard", "fromContainerId": "p2",
            "toZone": "exile", "position": "top", "reason": "exile",
        })

    def test_disfigure_checks_point_value_and_destroys_to_the_owners_limbo(self):
        session, p1, p2 = self.make_session()
        session.card_points.update({"m-3": 20, "m-4": 21})
        session.card_rules["will-ephemeral"].update({"cost": 2, "powerCost": "{P}{P}"})
        session.card_rules["will-ephemeral"]["playedAbilities"] = [{
            "id": "disfigure-destroy-manifestation", "action": "play_card",
            "targets": {
                "min": 1, "max": 1, "cardType": "manifestation",
                "zones": ["battlefield", "receptacle"], "maxPoints": 20,
            },
            "result": {
                "kind": "move_target", "zone": "graveyard",
                "position": "top", "reason": "destroy",
            },
        }]
        for tribute_id in ("m-0", "m-1"):
            session.card_rules[tribute_id]["temperaments"] = ["melancholic"]
        p1["zones"]["hand"] = ["will-ephemeral", "m-0", "m-1"]
        p1["zoneOwners"]["hand"] = {card_id: "p1" for card_id in p1["zones"]["hand"]}
        p2["zones"]["receptacle"] = ["m-3"]
        p2["zoneOwners"]["receptacle"] = {"m-3": "p1"}
        session.battlefield = [{
            "id": "too-valuable", "ownerId": "p2", "cardId": "m-4",
            "x": 10, "y": 10, "faceUp": True, "rotation": 0, "counters": {},
        }]

        point_error, _action = session.declare_rules_action(
            "p1", "Disfigure invalid target", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            targets=[{"kind": "card", "itemId": "too-valuable", "cardId": "m-4"}],
            payment_card_ids=["m-0", "m-1"],
            ability_id="disfigure-destroy-manifestation",
        )
        self.assertIn("lower point value", point_error)
        self.assertEqual(p1["zones"]["hand"], ["will-ephemeral", "m-0", "m-1"])

        error, action = session.declare_rules_action(
            "p1", "Disfigure", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            targets=[{
                "kind": "zone_card", "containerId": "p2", "zone": "receptacle",
                "cardId": "m-3",
            }],
            payment_card_ids=["m-0", "m-1"],
            ability_id="disfigure-destroy-manifestation",
        )
        self.assertIsNone(error)
        self.assertEqual(action["targets"][0]["ownerId"], "p1")
        session.pass_rules_priority("p2")
        resolve_error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(resolve_error)
        self.assertEqual(p2["zones"]["receptacle"], [])
        self.assertEqual(p1["zones"]["graveyard"], ["m-3", "will-ephemeral", "m-1", "m-0"])
        self.assertEqual(resolution["action"]["effectResult"], {
            "kind": "move_card", "status": "moved", "cardId": "m-3",
            "ownerId": "p1", "fromZone": "receptacle", "fromContainerId": "p2",
            "toZone": "graveyard", "position": "top", "reason": "destroy",
        })

    def test_destroy_targets_only_field_wills_or_interzone_manifestations(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index(
            "confrontation_reaction"
        )
        ability = {
            "id": "destroy-valid-field-target",
            "action": "play_card",
            "targets": {
                "min": 1, "max": 1,
                "cardTypes": [
                    "manifestation", "ephemeral_will", "persistent_will",
                ],
                "zones": ["battlefield"],
                "fieldZonesByType": {
                    "manifestation": ["interzone"],
                    "ephemeral_will": ["field"],
                    "persistent_will": ["field"],
                },
            },
            "result": {
                "kind": "move_target", "zone": "graveyard",
                "position": "top", "reason": "destroy",
            },
        }
        session.card_rules["destroy"] = {
            "type": "ephemeral_will", "cost": 0, "powerCost": "",
            "playedAbilities": [ability],
        }
        p1["zones"]["hand"] = ["destroy"]
        p1["zoneOwners"]["hand"] = {"destroy": "p1"}
        manifestation = {
            "id": "manifestation", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        field_will = {
            "id": "field-will", "ownerId": "p2",
            "cardId": "will-persistent", "faceUp": True,
            "fieldZone": "field", "counters": {},
        }
        session.battlefield = [manifestation, field_will]

        invalid_error, _action = session.declare_rules_action(
            "p1", "Destroy invalid", kind="play_card",
            source={"cardId": "destroy", "zone": "hand"},
            targets=[{
                "kind": "card", "itemId": "manifestation",
                "cardId": "m-2", "ownerId": "p2",
            }],
            ability_id="destroy-valid-field-target",
        )
        self.assertIn("different field zone", invalid_error)

        error, _action = session.declare_rules_action(
            "p1", "Destroy", kind="play_card",
            source={"cardId": "destroy", "zone": "hand"},
            targets=[{
                "kind": "card", "itemId": "field-will",
                "cardId": "will-persistent", "ownerId": "p2",
            }],
            ability_id="destroy-valid-field-target",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        session.pass_rules_priority("p1")
        self.assertIsNone(session.find_battlefield_item("field-will"))
        self.assertIn("will-persistent", p2["zones"]["graveyard"])

    def test_remove_by_chance_locks_player_then_destroys_random_eligible_vessel_card(self):
        session, p1, p2 = self.make_session()
        session.card_rules["will-ephemeral"].update({"cost": 0, "powerCost": ""})
        session.card_rules["will-ephemeral"]["playedAbilities"] = [{
            "id": "destroy-random-vessel-manifestation", "action": "play_card",
            "targets": {"kind": "player", "min": 1, "max": 1},
            "result": {
                "kind": "move_random_zone_card", "fromZone": "receptacle",
                "cardType": "manifestation", "zone": "graveyard",
                "position": "top", "reason": "destroy",
            },
        }]
        p1["zones"]["hand"] = ["will-ephemeral"]
        p1["zoneOwners"]["hand"] = {"will-ephemeral": "p1"}
        p2["zones"]["receptacle"] = ["will-persistent", "m-3"]
        p2["zoneOwners"]["receptacle"] = {"will-persistent": "p1", "m-3": "p1"}

        invalid_error, _action = session.declare_rules_action(
            "p1", "Invalid player target", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            targets=[{"kind": "player", "playerId": "missing"}],
            ability_id="destroy-random-vessel-manifestation",
        )
        self.assertIn("no longer in the game", invalid_error)

        error, action = session.declare_rules_action(
            "p1", "Remove by Chance", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            targets=[{"kind": "player", "playerId": "p2"}],
            ability_id="destroy-random-vessel-manifestation",
        )
        self.assertIsNone(error)
        self.assertEqual(action["targets"], [{"kind": "player", "playerId": "p2"}])
        session.pass_rules_priority("p2")
        resolve_error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(resolve_error)
        self.assertEqual(p2["zones"]["receptacle"], ["will-persistent"])
        self.assertEqual(p1["zones"]["graveyard"], ["m-3", "will-ephemeral"])
        self.assertEqual(resolution["action"]["effectResult"], {
            "kind": "move_card", "status": "moved", "random": True,
            "cardId": "m-3", "ownerId": "p1", "fromZone": "receptacle",
            "fromContainerId": "p2", "toZone": "graveyard", "position": "top",
            "reason": "destroy",
        })

        no_target = session.apply_rules_action_result({
            "controllerId": "p1", "targets": [{"kind": "player", "playerId": "p2"}],
            "ability": {"result": {
                "kind": "move_random_zone_card", "fromZone": "receptacle",
                "cardType": "manifestation", "zone": "graveyard",
                "position": "top", "reason": "destroy",
            }},
        })
        self.assertEqual(no_target, {
            "kind": "move_card", "status": "no_eligible_card", "random": True,
            "fromZone": "receptacle", "fromContainerId": "p2",
            "toZone": "graveyard", "position": "top", "reason": "destroy",
        })

    def test_eliminate_the_profane_only_accepts_a_vessel_manifestation(self):
        session, p1, p2 = self.make_session()
        session.card_rules["will-ephemeral"].update({"cost": 0, "powerCost": ""})
        session.card_rules["will-ephemeral"]["playedAbilities"] = [{
            "id": "destroy-vessel-manifestation", "action": "play_card",
            "targets": {
                "min": 1, "max": 1, "cardType": "manifestation",
                "zones": ["receptacle"],
            },
            "result": {
                "kind": "move_target", "zone": "graveyard",
                "position": "top", "reason": "destroy",
            },
        }]
        p1["zones"]["hand"] = ["will-ephemeral"]
        p1["zoneOwners"]["hand"] = {"will-ephemeral": "p1"}
        p2["zones"]["receptacle"] = ["m-3"]
        p2["zoneOwners"]["receptacle"] = {"m-3": "p1"}
        session.battlefield = [{
            "id": "field-manifestation", "ownerId": "p2", "cardId": "m-4",
            "x": 10, "y": 10, "faceUp": True, "rotation": 0, "counters": {},
        }]

        zone_error, _action = session.declare_rules_action(
            "p1", "Invalid field target", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            targets=[{"kind": "card", "itemId": "field-manifestation", "cardId": "m-4"}],
            ability_id="destroy-vessel-manifestation",
        )
        self.assertIn("different zone", zone_error)

        error, _action = session.declare_rules_action(
            "p1", "Eliminate the Profane", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            targets=[{
                "kind": "zone_card", "containerId": "p2", "zone": "receptacle",
                "cardId": "m-3",
            }],
            ability_id="destroy-vessel-manifestation",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        resolve_error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(resolve_error)
        self.assertEqual(p2["zones"]["receptacle"], [])
        self.assertEqual(p1["zones"]["graveyard"], ["m-3", "will-ephemeral"])
        self.assertEqual(resolution["action"]["effectResult"]["reason"], "destroy")

    def test_source_bound_ongoing_effect_is_replaced_and_pruned_with_its_source(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["m-0"]["activatedAbilities"] = [{
            "id": "copy-target",
            "tribute": "",
            "exhaustSource": False,
            "targets": {"min": 1, "max": 1, "cardType": "manifestation"},
            "ongoingEffect": {"kind": "copy_power_temperament", "duration": "while_source_and_target_on_field"},
        }]
        session.battlefield = [
            {"id": "source-1", "ownerId": "p1", "cardId": "m-0", "x": 0, "y": 0, "faceUp": True, "rotation": 0, "counters": {}},
            {"id": "target-1", "ownerId": "p2", "cardId": "m-1", "x": 10, "y": 10, "faceUp": True, "rotation": 0, "counters": {}},
            {"id": "target-2", "ownerId": "p2", "cardId": "m-2", "x": 20, "y": 20, "faceUp": True, "rotation": 0, "counters": {}},
        ]
        base = {
            "kind": "activated_effect",
            "source": {"cardId": "m-0", "zone": "battlefield", "itemId": "source-1"},
            "ability_id": "copy-target",
        }

        _error, first = session.declare_rules_action(
            "p1", "Copy first", targets=[{"kind": "card", "itemId": "target-1", "cardId": "m-1"}], **base
        )
        session.pass_rules_priority("p2")
        session.pass_rules_priority("p1")
        session.rules_engine["priorityPlayerId"] = "p1"
        _error, second = session.declare_rules_action(
            "p1", "Copy second", targets=[{"kind": "card", "itemId": "target-2", "cardId": "m-2"}], **base
        )
        session.pass_rules_priority("p2")
        session.pass_rules_priority("p1")

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(len(session.rules_engine["ongoingEffects"]), 1)
        self.assertEqual(session.rules_engine["ongoingEffects"][0]["target"]["itemId"], "target-2")
        session.battlefield = [item for item in session.battlefield if item["id"] != "source-1"]
        removed = session.prune_rules_ongoing_effects()
        self.assertEqual(len(removed), 1)
        self.assertEqual(session.rules_engine["ongoingEffects"], [])

    def test_sacrificing_an_encoded_source_pays_the_cost_and_marks_its_global_effect(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["m-1"]["power"] = 2
        session.card_rules["m-2"]["power"] = 2
        session.card_rules["m-0"]["activatedAbilities"] = [{
            "id": "sacrifice-all",
            "tribute": "",
            "exhaustSource": False,
            "sacrificeSource": True,
            "targets": {"min": 0, "max": 0},
            "ongoingEffect": {
                "kind": "power_modifier", "value": -1,
                "duration": "until_end_of_turn", "scope": "all_manifestations_on_field",
            },
        }]
        session.battlefield = [
            {"id": "source-1", "ownerId": "p1", "cardId": "m-0", "x": 0, "y": 0, "faceUp": True, "rotation": 0, "counters": {}},
            {"id": "target-1", "ownerId": "p1", "cardId": "m-1", "x": 10, "y": 10, "faceUp": True, "rotation": 0, "counters": {}},
            {"id": "target-2", "ownerId": "p2", "cardId": "m-2", "x": 20, "y": 20, "faceUp": True, "rotation": 0, "counters": {}},
        ]

        error, action = session.declare_rules_action(
            "p1", "Sacrifice source", kind="activated_effect",
            source={"cardId": "m-0", "zone": "battlefield", "itemId": "source-1"},
            targets=[], ability_id="sacrifice-all",
        )

        self.assertIsNone(error)
        self.assertTrue(action["cost"]["sourceSacrificed"])
        self.assertEqual(action["cost"]["sacrificedCards"][0]["cardId"], "m-0")
        self.assertIsNone(session.find_battlefield_item("source-1"))
        self.assertEqual(p1["zones"]["graveyard"], ["m-0"])
        self.assertEqual(session.rules_engine["ongoingEffects"], [])
        session.pass_rules_priority("p2")
        _error, resolution = session.pass_rules_priority("p1")
        self.assertEqual(resolution["status"], "resolved")
        self.assertEqual(len(resolution["action"]["ongoingEffects"]), 2)
        self.assertEqual(
            {effect["target"]["itemId"] for effect in session.rules_engine["ongoingEffects"]},
            {"target-1", "target-2"},
        )

    def test_activated_ability_can_require_its_source_to_be_in_the_interzone(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["m-0"]["activatedAbilities"] = [{
            "id": "interzone-only", "tribute": "", "sourceFieldZone": "interzone",
            "sacrificeSource": True, "targets": {"min": 0, "max": 0},
        }]
        source = {
            "id": "source-1", "ownerId": "p1", "cardId": "m-0", "x": 0, "y": 0,
            "faceUp": True, "rotation": 0, "counters": {}, "fieldZone": "confrontation",
        }
        session.battlefield = [source]

        error, action = session.declare_rules_action(
            "p1", "Sacrifice source", kind="activated_effect",
            source={"cardId": "m-0", "zone": "battlefield", "itemId": "source-1"},
            targets=[], ability_id="interzone-only",
        )
        self.assertIsNone(action)
        self.assertIn("field zone", error)
        self.assertIsNotNone(session.find_battlefield_item("source-1"))

        source["fieldZone"] = "interzone"
        session.mark_rules_support_entry(source)
        self.assertEqual(source["fieldZone"], "confrontation")
        error, action = session.declare_rules_action(
            "p1", "Sacrifice source", kind="activated_effect",
            source={"cardId": "m-0", "zone": "battlefield", "itemId": "source-1"},
            targets=[], ability_id="interzone-only",
        )
        self.assertIsNone(action)
        self.assertIn("field zone", error)

        source["isSupport"] = False
        source["fieldZone"] = "interzone"
        error, action = session.declare_rules_action(
            "p1", "Sacrifice source", kind="activated_effect",
            source={"cardId": "m-0", "zone": "battlefield", "itemId": "source-1"},
            targets=[], ability_id="interzone-only",
        )
        self.assertIsNone(error)
        self.assertTrue(action["cost"]["sourceSacrificed"])
        self.assertIsNone(session.find_battlefield_item("source-1"))

    def test_opponent_vessel_entry_queues_and_resolves_a_score_trigger(self):
        session, p1, p2 = self.make_session()
        session.card_rules["m-0"]["triggeredAbilities"] = [{
            "id": "gain-points-in-opponent-vessel",
            "trigger": {"event": "enters_zone", "zone": "receptacle", "container": "opponent"},
            "result": {"kind": "score_owner", "value": 20},
        }]
        p2["zones"]["receptacle"] = ["m-0"]
        p2["zoneOwners"]["receptacle"] = {"m-0": "p1"}

        actions = session.queue_rules_zone_entry_triggers("m-0", "p1", "p2", "receptacle")

        self.assertEqual(len(actions), 1)
        action = actions[0]
        self.assertEqual(action["kind"], "triggered_effect")
        self.assertEqual(action["controllerId"], "p1")
        self.assertEqual(action["source"]["containerId"], "p2")
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p2")
        self.assertEqual(p1["score"], 0)

        # A triggered effect stays on the Stack even if its source moves.
        move_error, _owner = session.move_zone_card("p2", "receptacle", "p1", "graveyard", "m-0")
        self.assertIsNone(move_error)
        session.pass_rules_priority("p2")
        resolve_error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(resolve_error)
        self.assertEqual(resolution["status"], "resolved")
        self.assertEqual(resolution["action"]["effectResult"], {
            "kind": "score", "playerId": "p1", "delta": 20, "score": 20,
        })
        self.assertEqual(p1["score"], 20)

    def test_opponent_vessel_trigger_does_not_queue_for_the_owners_container(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["m-0"]["triggeredAbilities"] = [{
            "id": "gain-points-in-opponent-vessel",
            "trigger": {"event": "enters_zone", "zone": "receptacle", "container": "opponent"},
            "result": {"kind": "score_owner", "value": 20},
        }]

        actions = session.queue_rules_zone_entry_triggers("m-0", "p1", "p1", "receptacle")

        self.assertEqual(actions, [])
        self.assertEqual(session.rules_engine["actionStack"], [])

    def test_face_up_battlefield_entry_queues_and_resolves_a_private_draw(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["m-0"]["triggeredAbilities"] = [{
            "id": "draw-on-enter-field",
            "trigger": {"event": "enters_field", "visibility": "face_up"},
            "result": {"kind": "draw_owner", "value": 1},
        }]
        self.fill_deck(p1, ["m-1", "m-2"])

        actions = session.queue_rules_battlefield_entry_triggers("m-0", "p1", "field-1", True)

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["source"]["zone"], "battlefield")
        self.assertEqual(actions[0]["source"]["itemId"], "field-1")
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p2")
        self.assertEqual(p1["zones"]["hand"], [])
        session.pass_rules_priority("p2")
        resolve_error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(resolve_error)
        self.assertEqual(resolution["action"]["effectResult"], {
            "kind": "draw", "playerId": "p1", "count": 1,
        })
        self.assertEqual(p1["zones"]["hand"], ["m-1"])
        self.assertEqual(p1["zones"]["deck"], ["m-2"])

    def test_pluff_discards_the_top_deck_card_only_when_its_trigger_resolves(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["m-0"]["triggeredAbilities"] = [{
            "id": "discard-top-card-on-enter-field",
            "trigger": {"event": "enters_field", "visibility": "face_up"},
            "result": {"kind": "discard_deck_owner", "value": 1},
        }]
        self.fill_deck(p1, ["m-1", "m-2"])

        actions = session.queue_rules_battlefield_entry_triggers("m-0", "p1", "pluff-1", True)

        self.assertEqual(len(actions), 1)
        self.assertEqual(p1["zones"]["deck"], ["m-1", "m-2"])
        self.assertEqual(p1["zones"]["graveyard"], [])
        session.pass_rules_priority("p2")
        resolve_error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(resolve_error)
        self.assertEqual(resolution["action"]["effectResult"], {
            "kind": "discard_deck", "playerId": "p1", "count": 1,
            "cardIds": ["m-1"],
        })
        self.assertEqual(p1["zones"]["deck"], ["m-2"])
        self.assertEqual(p1["zones"]["graveyard"], ["m-1"])
        self.assertFalse(session.ended)

        p1["zones"]["deck"] = []
        empty_result = session.apply_rules_action_result({
            "controllerId": "p1",
            "ability": {"result": {"kind": "discard_deck_owner", "value": 1}},
        })
        self.assertEqual(empty_result, {
            "kind": "discard_deck", "playerId": "p1", "count": 0, "cardIds": [],
        })

    def test_face_down_battlefield_entry_does_not_reveal_or_queue_its_trigger(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["m-0"]["triggeredAbilities"] = [{
            "id": "draw-on-enter-field",
            "trigger": {"event": "enters_field", "visibility": "face_up"},
            "result": {"kind": "draw_owner", "value": 1},
        }]

        actions = session.queue_rules_battlefield_entry_triggers("m-0", "p1", "field-1", False)

        self.assertEqual(actions, [])
        self.assertEqual(session.rules_engine["actionStack"], [])

    def test_support_entry_watchers_stack_discard_then_draw_with_normal_priority(self):
        session, p1, p2 = self.make_session()
        session.card_rules.update({
            "mazzolong": {
                "type": "manifestation", "triggeredAbilities": [{
                    "id": "draw-when-support-played",
                    "trigger": {"event": "enters_support", "sourceZone": "interzone", "played": True, "eventController": "owner"},
                    "result": {"kind": "draw_owner", "value": 1},
                }],
            },
            "wheel": {
                "type": "persistent_will", "triggeredAbilities": [{
                    "id": "support-controller-discards",
                    "trigger": {"event": "enters_support", "target": "event_controller"},
                    "targets": {"kind": "player", "min": 1, "max": 1},
                    "result": {"kind": "discard_hand_target", "value": 1},
                }],
            },
            "support": {"type": "manifestation", "power": 1, "temperaments": ["phlegmatic"]},
        })
        p1["zones"]["hand"] = ["discard-me"]
        p1["zones"]["deck"] = ["draw-me"]
        p1["zoneOwners"]["hand"] = {"discard-me": "p1"}
        p1["zoneOwners"]["deck"] = {"draw-me": "p1"}
        mazzolong = {
            "id": "mazzolong-field", "ownerId": "p1", "cardId": "mazzolong",
            "faceUp": True, "fieldZone": "interzone", "counters": {},
        }
        wheel = {
            "id": "wheel-field", "ownerId": "p2", "cardId": "wheel",
            "faceUp": True, "counters": {},
        }
        support = {
            "id": "support-entry", "ownerId": "p1", "cardId": "support",
            "faceUp": True, "fieldZone": "confrontation", "isSupport": True, "counters": {},
        }
        session.battlefield = [mazzolong, wheel, support]

        actions = session.queue_rules_support_entry_triggers(support, played=True)

        self.assertEqual([action["source"]["cardId"] for action in actions], ["mazzolong", "wheel"])
        self.assertEqual(actions[0]["source"]["zone"], "interzone")
        self.assertEqual(actions[1]["targets"], [{"kind": "player", "playerId": "p1"}])
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p1")

        self.assertIsNone(session.pass_rules_priority("p1")[0])
        error, wheel_resolution = session.pass_rules_priority("p2")
        self.assertIsNone(error)
        self.assertEqual(wheel_resolution["action"]["source"]["cardId"], "wheel")
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["playerId"], "p1")
        self.assertIsNone(session.resolve_rules_choice("p1", choice["id"], ["discard-me"])[0])
        self.assertEqual(p1["zones"]["graveyard"], ["discard-me"])

        self.assertIsNone(session.pass_rules_priority("p2")[0])
        error, mazzolong_resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error)
        self.assertEqual(mazzolong_resolution["action"]["source"]["cardId"], "mazzolong")
        self.assertEqual(mazzolong_resolution["action"]["effectResult"], {
            "kind": "draw", "playerId": "p1", "count": 1,
        })
        self.assertEqual(p1["zones"]["hand"], ["draw-me"])

    def test_mazzolong_ignores_support_put_by_an_effect_but_wheel_still_triggers(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["mazzolong"] = {
            "type": "manifestation", "triggeredAbilities": [{
                "id": "draw-when-support-played",
                "trigger": {"event": "enters_support", "sourceZone": "interzone", "played": True, "eventController": "owner"},
                "result": {"kind": "draw_owner", "value": 1},
            }],
        }
        session.card_rules["wheel"] = {
            "type": "persistent_will", "triggeredAbilities": [{
                "id": "support-controller-discards",
                "trigger": {"event": "enters_support", "target": "event_controller"},
                "targets": {"kind": "player", "min": 1, "max": 1},
                "result": {"kind": "discard_hand_target", "value": 1},
            }],
        }
        session.card_rules["support"] = {"type": "manifestation"}
        session.battlefield = [
            {"id": "mazzolong", "ownerId": "p1", "cardId": "mazzolong", "faceUp": True, "fieldZone": "interzone", "counters": {}},
            {"id": "wheel", "ownerId": "p2", "cardId": "wheel", "faceUp": True, "counters": {}},
            {"id": "support", "ownerId": "p1", "cardId": "support", "faceUp": True, "fieldZone": "confrontation", "isSupport": True, "counters": {}},
        ]

        actions = session.queue_rules_support_entry_triggers(session.battlefield[-1], played=False)

        self.assertEqual([action["source"]["cardId"] for action in actions], ["wheel"])
        session.rules_engine["actionStack"] = []
        session.battlefield[-1]["ownerId"] = "p2"
        opponent_actions = session.queue_rules_support_entry_triggers(session.battlefield[-1], played=True)
        self.assertEqual([action["source"]["cardId"] for action in opponent_actions], ["wheel"])

    def test_flower_tender_targets_another_low_power_confrontation_card(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules.update({
            "flower": {
                "type": "manifestation", "power": 1, "triggeredAbilities": [{
                    "id": "flower-boost",
                    "trigger": {
                        "event": "enters_field_zone",
                        "zone": "confrontation",
                    },
                    "targets": {
                        "kind": "card", "min": 1, "max": 1,
                        "cardType": "manifestation", "zones": ["battlefield"],
                        "fieldZone": "confrontation", "maxPower": 2,
                        "excludeEventSource": True,
                    },
                    "ongoingEffect": {
                        "kind": "power_modifier", "value": 2,
                        "duration": "until_end_of_turn",
                    },
                }],
            },
            "small": {"type": "manifestation", "power": 2},
            "large": {"type": "manifestation", "power": 3},
        })
        flower = {
            "id": "flower-field", "ownerId": "p1", "cardId": "flower",
            "faceUp": True, "fieldZone": "confrontation", "isSupport": True,
            "counters": {},
        }
        small = {
            "id": "small-field", "ownerId": "p1", "cardId": "small",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        large = {
            "id": "large-field", "ownerId": "p2", "cardId": "large",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield = [flower, small, large]

        self.assertIn("another Manifestation", session.rules_trigger_target_error(
            "flower", "enters_field_zone", controller_id="p1", event_item_id="flower-field",
            event_zone="confrontation",
            trigger_targets=[{"kind": "card", "itemId": "flower-field", "cardId": "flower"}],
        ))
        self.assertIn("lower Power", session.rules_trigger_target_error(
            "flower", "enters_field_zone", controller_id="p1", event_item_id="flower-field",
            event_zone="confrontation",
            trigger_targets=[{"kind": "card", "itemId": "large-field", "cardId": "large"}],
        ))
        targets = [{"kind": "card", "itemId": "small-field", "cardId": "small"}]
        self.assertIsNone(session.rules_trigger_target_error(
            "flower", "enters_field_zone", controller_id="p1", event_item_id="flower-field",
            event_zone="confrontation",
            trigger_targets=targets,
        ))

        actions = session.queue_rules_field_zone_entry_triggers(
            flower, "confrontation",
            event_targets=targets,
        )
        self.assertEqual(len(actions), 1)
        session.pass_rules_priority("p2")
        error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error)
        self.assertEqual(len(resolution["action"]["ongoingEffects"]), 1)
        self.assertEqual(session.rules_manifestation_characteristics(small)["power"], 4)

        flower["fieldZone"] = "interzone"
        flower["isSupport"] = False
        unrelated_support = {
            "id": "unrelated-support", "ownerId": "p1",
            "cardId": "small", "faceUp": True,
            "fieldZone": "confrontation", "isSupport": True,
            "counters": {},
        }
        session.battlefield.append(unrelated_support)
        self.assertEqual(
            session.queue_rules_support_entry_triggers(
                unrelated_support, played=True, from_zone="hand",
                event_targets=targets,
            ),
            [],
        )

    def test_chitinous_repeller_returns_and_restricts_one_physical_copy(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["repeller"] = {
            "type": "manifestation", "power": 2, "triggeredAbilities": [{
                "id": "repeller-return",
                "trigger": {"event": "enters_field", "visibility": "face_up"},
                "targets": {
                    "kind": "card", "min": 1, "max": 1,
                    "cardType": "manifestation", "zones": ["battlefield"],
                    "fieldZone": "confrontation", "controller": "self",
                },
                "result": {
                    "kind": "move_target", "zone": "hand", "position": "top",
                    "reason": "return", "restrictPlayUntilEndOfTurn": True,
                },
            }],
        }
        repeller = {"id": "repeller-field", "ownerId": "p1", "cardId": "repeller", "faceUp": True, "counters": {}}
        target = {
            "id": "target-field", "ownerId": "p1", "cardId": "m-1",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield = [repeller, target]
        targets = [{"kind": "card", "itemId": "target-field", "cardId": "m-1"}]

        actions = session.queue_rules_battlefield_entry_triggers(
            "repeller", "p1", "repeller-field", True, event_targets=targets,
        )
        self.assertEqual(len(actions), 1)
        session.pass_rules_priority("p2")
        error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(error)
        self.assertTrue(resolution["action"]["effectResult"]["playRestrictedUntilTurnEnd"])
        self.assertEqual(p1["zones"]["hand"], ["m-1"])
        self.assertIsNotNone(session.rules_card_play_restriction_error("p1", "m-1"))
        p1["zones"]["hand"].append("m-1")
        self.assertIsNone(session.rules_card_play_restriction_error("p1", "m-1"))
        session.phase_tracker["turn"] += 1
        session.prune_rules_play_restrictions()
        self.assertEqual(session.rules_engine["playRestrictions"], [])

    def test_chiff_and_chaff_unlocks_after_opponent_support_and_returns_it(self):
        session, p1, p2 = self.make_session()
        session.card_rules["chiff"] = {
            "type": "manifestation", "power": 3,
            "supportFromHandCondition": {"kind": "opponent_support_from_interzone_this_turn"},
            "triggeredAbilities": [{
                "id": "chiff-return",
                "trigger": {"event": "enters_support"},
                "targets": {
                    "kind": "card", "min": 1, "max": 1,
                    "cardType": "manifestation", "zones": ["battlefield"],
                    "supportOnly": True, "controller": "opponent",
                },
                "result": {
                    "kind": "move_target", "zone": "hand", "position": "top",
                    "reason": "return", "restrictPlayUntilEndOfTurn": True,
                },
            }],
        }
        opponent_support = {
            "id": "opponent-support", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation", "isSupport": True,
            "counters": {},
        }
        self.assertFalse(session.rules_support_from_hand_available("p1", "chiff"))
        session.battlefield = [opponent_support]
        session.queue_rules_support_entry_triggers(
            opponent_support, played=True, from_zone="interzone",
        )
        self.assertTrue(session.rules_support_from_hand_available("p1", "chiff"))

        chiff = {
            "id": "chiff-field", "ownerId": "p1", "cardId": "chiff",
            "faceUp": True, "fieldZone": "confrontation", "isSupport": True,
            "counters": {},
        }
        session.battlefield.append(chiff)
        targets = [{"kind": "card", "itemId": "opponent-support", "cardId": "m-2"}]
        actions = session.queue_rules_support_entry_triggers(
            chiff, played=True, from_zone="hand", event_targets=targets,
        )
        self.assertEqual(len(actions), 1)
        session.pass_rules_priority("p2")
        error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(error)
        self.assertEqual(resolution["action"]["effectResult"]["reason"], "return")
        self.assertEqual(p2["zones"]["hand"], ["m-2"])
        self.assertIsNotNone(session.rules_card_play_restriction_error("p2", "m-2"))

    def test_urocione_chain_resolves_into_a_private_board_choice_then_support(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["urocione"] = {
            "type": "manifestation", "power": 4, "triggeredAbilities": [{
                "id": "chain-from-hand",
                "optional": True,
                "trigger": {"event": "enters_field", "visibility": "face_up"},
                "result": {
                    "kind": "chain_from_zone", "zone": "hand", "optional": True,
                    "winDestination": "opponent_receptacle",
                },
            }],
        }
        p1["zones"]["hand"] = ["m-1", "will-ephemeral"]
        p1["zoneOwners"]["hand"] = {"m-1": "p1", "will-ephemeral": "p1"}
        session.battlefield = [{
            "id": "urocione-field", "ownerId": "p1", "cardId": "urocione",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }]

        actions = session.queue_rules_battlefield_entry_triggers(
            "urocione", "p1", "urocione-field", True,
        )
        self.assertEqual(len(actions), 1)
        optional_choice = session.rules_engine["pendingChoice"]
        self.assertEqual(optional_choice["kind"], "optional_stack_action")
        self.assertEqual(session.rules_engine["actionStack"], [])
        self.assertIsNone(session.resolve_rules_choice(
            "p1", optional_choice["id"], option="accept"
        )[0])
        session.pass_rules_priority("p2")
        error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(error)
        self.assertEqual(resolution["action"]["effectResult"]["choiceKind"], "chain_manifestation")
        self.assertEqual(p1["zones"]["hand"], ["m-1", "will-ephemeral"])
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["fromZone"], "hand")
        self.assertNotIn("cardIds", choice)

        invalid_error, _invalid = session.resolve_rules_choice(
            "p1", choice["id"], ["will-ephemeral"], placement={"x": 400, "y": 500},
        )
        self.assertIn("Manifestation", invalid_error)
        chain_error, chained = session.resolve_rules_choice(
            "p1", choice["id"], ["m-1"], placement={"x": 412, "y": 524},
        )

        self.assertIsNone(chain_error)
        self.assertEqual(chained["status"], "chained")
        item = session.find_battlefield_item(chained["itemId"])
        self.assertEqual((item["x"], item["y"]), (412.0, 524.0))
        self.assertTrue(item["isSupport"])
        self.assertTrue(item["isChained"])
        self.assertEqual(item["supportWinDestination"], "opponent_receptacle")
        self.assertEqual(p1["zones"]["hand"], ["will-ephemeral"])
        self.assertEqual(session.rules_engine["supportEntries"][-1]["fromZone"], "hand")
        self.assertTrue(session.rules_engine["supportEntries"][-1]["played"])
        self.assertIsNone(session.rules_engine["pendingChoice"])

    def test_urocione_chain_can_be_declined_and_winning_chain_enters_opponent_vessel(self):
        session, p1, p2 = self.make_session()
        session.card_rules["urocione"] = {
            "type": "manifestation", "power": 4,
            "triggeredAbilities": [{
                "id": "chain-from-hand",
                "optional": True,
                "trigger": {"event": "enters_field", "visibility": "face_up"},
                "result": {
                    "kind": "chain_from_zone", "zone": "hand",
                    "optional": True,
                    "winDestination": "opponent_receptacle",
                },
            }],
        }
        session.card_rules["m-1"]["power"] = 3
        p1["zones"]["hand"] = ["m-1"]
        p1["zoneOwners"]["hand"] = {"m-1": "p1"}
        session.battlefield = [{
            "id": "urocione-field", "ownerId": "p1", "cardId": "urocione",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }]
        session.queue_rules_battlefield_entry_triggers(
            "urocione", "p1", "urocione-field", True,
        )
        decline_choice = session.rules_engine["pendingChoice"]
        error, declined = session.resolve_rules_choice(
            "p1", decline_choice["id"], option="decline"
        )
        self.assertIsNone(error)
        self.assertEqual(declined["status"], "declined")
        self.assertEqual(p1["zones"]["hand"], ["m-1"])
        self.assertEqual(session.rules_engine["actionStack"], [])

        session.queue_rules_battlefield_entry_triggers(
            "urocione", "p1", "urocione-field", True,
        )
        accept_choice = session.rules_engine["pendingChoice"]
        self.assertIsNone(session.resolve_rules_choice(
            "p1", accept_choice["id"], option="accept"
        )[0])
        session.pass_rules_priority("p2")
        self.assertIsNone(session.pass_rules_priority("p1")[0])
        chain_choice = session.rules_engine["pendingChoice"]
        self.assertFalse(chain_choice["optional"])
        self.assertIsNone(session.resolve_rules_choice(
            "p1", chain_choice["id"], ["m-1"],
            placement={"x": 500, "y": 500},
        )[0])
        chained = next(item for item in session.battlefield if item.get("isChained"))
        opponent = {
            "id": "opponent-field", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield.append(opponent)
        session.phase_tracker["index"] = ADVANCED_PHASES.index("resolution_compare")

        comparison = session.prepare_rules_confrontation_result()
        self.assertEqual(comparison["winnerId"], "p1")
        cleanup = session.begin_rules_confrontation_cleanup()

        self.assertNotIn(chained, session.battlefield)
        self.assertEqual(p2["zones"]["receptacle"], ["m-1"])
        self.assertEqual(cleanup["supportResolved"][0]["kind"], "opponent_vessel")

    def test_controller_orders_paid_action_and_simultaneous_tribute_trigger(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["m-1"]["triggeredAbilities"] = [{
            "id": "draw-when-used-as-tribute",
            "trigger": {"event": "used_as_tribute"},
            "result": {"kind": "draw_owner", "value": 1},
        }]
        p1["zones"]["hand"] = ["will-ephemeral", "m-1"]
        p1["zoneOwners"]["hand"] = {"will-ephemeral": "p1", "m-1": "p1"}
        p1["zones"]["deck"] = ["m-2"]
        p1["zoneOwners"]["deck"] = {"m-2": "p1"}

        error, paid_action = session.declare_rules_action(
            "p1", "Play Will", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            payment_card_ids=["m-1"],
        )
        self.assertIsNone(error)
        triggers = session.queue_rules_tribute_triggers(
            paid_action["cost"]["tributeCardIds"], "p1",
            simultaneous_action_id=paid_action["id"],
        )

        self.assertEqual(len(triggers), 1)
        self.assertEqual(session.rules_engine["actionStack"], [])
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "simultaneous_stack_order")
        self.assertEqual(choice["playerId"], "p1")
        order_error, ordered = session.resolve_rules_choice(
            "p1", choice["id"], [paid_action["id"], triggers[0]["id"]],
        )
        self.assertIsNone(order_error)
        self.assertTrue(ordered["completed"])
        self.assertEqual(len(session.rules_engine["actionStack"]), 2)
        self.assertEqual(session.rules_engine["actionStack"][0]["id"], paid_action["id"])
        self.assertEqual(session.rules_engine["actionStack"][-1]["source"]["cardId"], "m-1")
        self.assertEqual(session.rules_engine["actionStack"][-1]["source"]["zone"], "graveyard")
        self.assertEqual(p1["zones"]["hand"], [])
        self.assertEqual(p1["zones"]["graveyard"], ["m-1"])

        session.pass_rules_priority("p2")
        resolve_error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(resolve_error)
        self.assertEqual(resolution["action"]["effectResult"], {
            "kind": "draw", "playerId": "p1", "count": 1,
        })
        self.assertEqual(p1["zones"]["hand"], ["m-2"])
        self.assertEqual(session.rules_engine["actionStack"][0]["id"], paid_action["id"])

    def test_simultaneous_triggers_use_priority_controller_order_atomically(self):
        session, _p1, _p2 = self.make_session()
        session.rules_engine["priorityPlayerId"] = "p2"
        session.card_rules["m-0"]["triggeredAbilities"] = [{
            "id": "p1-trigger",
            "trigger": {"event": "beginning_of_turn"},
            "result": {"kind": "score_owner", "value": 1},
        }]
        session.card_rules["m-1"]["triggeredAbilities"] = [{
            "id": "p2-trigger",
            "trigger": {"event": "beginning_of_turn"},
            "result": {"kind": "score_owner", "value": 1},
        }]
        session.battlefield = [
            {
                "id": "p1-source", "ownerId": "p1", "cardId": "m-0",
                "faceUp": True, "fieldZone": "interzone", "counters": {},
            },
            {
                "id": "p2-source", "ownerId": "p2", "cardId": "m-1",
                "faceUp": True, "fieldZone": "interzone", "counters": {},
            },
        ]

        actions = session.queue_rules_beginning_turn_triggers()

        self.assertEqual(len(actions), 2)
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertEqual(
            [action["controllerId"] for action in session.rules_engine["actionStack"]],
            ["p2", "p1"],
        )
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p2")

    def test_multiple_same_controller_triggers_wait_for_order_before_stacking(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["m-0"]["triggeredAbilities"] = [
            {
                "id": "first-trigger",
                "trigger": {"event": "beginning_of_turn"},
                "result": {"kind": "score_owner", "value": 1},
            },
            {
                "id": "second-trigger",
                "trigger": {"event": "beginning_of_turn"},
                "result": {"kind": "score_owner", "value": 2},
            },
        ]
        session.battlefield = [{
            "id": "source", "ownerId": "p1", "cardId": "m-0",
            "faceUp": True, "fieldZone": "interzone", "counters": {},
        }]

        actions = session.queue_rules_beginning_turn_triggers()

        self.assertEqual(session.rules_engine["actionStack"], [])
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "simultaneous_stack_order")
        self.assertEqual(
            {entry["actionId"] for entry in choice["actions"]},
            {action["id"] for action in actions},
        )
        error, result = session.resolve_rules_choice(
            "p1", choice["id"], [actions[1]["id"], actions[0]["id"]],
        )
        self.assertIsNone(error)
        self.assertTrue(result["completed"])
        self.assertEqual(
            [action["id"] for action in session.rules_engine["actionStack"]],
            [actions[1]["id"], actions[0]["id"]],
        )

    def test_negative_score_trigger_applies_only_after_resolution(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["m-0"]["triggeredAbilities"] = [{
            "id": "lose-points-on-enter-field",
            "trigger": {"event": "enters_field", "visibility": "face_up"},
            "result": {"kind": "score_owner", "value": -20},
        }]
        p1["score"] = 5

        actions = session.queue_rules_battlefield_entry_triggers("m-0", "p1", "half-han-1", True)

        self.assertEqual(len(actions), 1)
        self.assertEqual(p1["score"], 5)
        session.pass_rules_priority("p2")
        resolve_error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(resolve_error)
        self.assertEqual(resolution["action"]["effectResult"], {
            "kind": "score", "playerId": "p1", "delta": -20, "score": -15,
        })
        self.assertEqual(p1["score"], -15)

    def test_targeted_discard_trigger_waits_for_private_choice(self):
        session, _p1, p2 = self.make_session()
        session.card_rules["m-0"]["triggeredAbilities"] = [{
            "id": "target-player-discards-on-enter-field",
            "trigger": {"event": "enters_field", "visibility": "face_up"},
            "targets": {"kind": "player", "min": 1, "max": 1},
            "result": {"kind": "discard_hand_target", "value": 1},
        }]
        p2["zones"]["hand"] = ["m-1", "m-2"]
        p2["zoneOwners"]["hand"] = {"m-1": "p2", "m-2": "p2"}

        self.assertIn(
            "Choose a valid player",
            session.rules_trigger_target_error("m-0", "enters_field", None, face_up=True),
        )
        self.assertIsNone(
            session.rules_trigger_target_error("m-0", "enters_field", "p2", face_up=True)
        )
        actions = session.queue_rules_battlefield_entry_triggers(
            "m-0", "p1", "apparition-1", True, target_player_id="p2"
        )

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["targets"], [{"kind": "player", "playerId": "p2"}])
        session.pass_rules_priority("p2")
        resolve_error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(resolve_error)
        effect = resolution["action"]["effectResult"]
        self.assertEqual(effect["kind"], "choice_required")
        self.assertEqual(effect["playerId"], "p2")
        self.assertEqual(p2["zones"]["hand"], ["m-1", "m-2"])
        pending = session.serialize_for("p1", "player")["rulesEngine"]["pendingChoice"]
        self.assertEqual(pending["playerId"], "p2")
        self.assertNotIn("cardIds", pending)
        blocked_error, _blocked = session.pass_rules_priority("p2")
        self.assertIn("required card choice", blocked_error)

        choice_error, result = session.resolve_rules_choice("p2", pending["id"], ["m-2"])

        self.assertIsNone(choice_error)
        self.assertEqual(result["cardIds"], ["m-2"])
        self.assertEqual(p2["zones"]["hand"], ["m-1"])
        self.assertEqual(p2["zones"]["graveyard"], ["m-2"])
        self.assertIsNone(session.rules_engine["pendingChoice"])

    def test_persistent_will_cannot_be_declared_as_a_response(self):
        session, _p1, p2 = self.make_session()
        p2["zones"]["hand"] = ["will-persistent"]
        session.declare_rules_action("p1", "Open the Stack")

        error, action = session.declare_rules_action(
            "p2",
            "Persistent response",
            kind="play_card",
            source={"cardId": "will-persistent", "zone": "hand"},
        )

        self.assertIn("cannot be played as a response", error)
        self.assertIsNone(action)
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p2")


    def test_confrontation_compares_modified_power_then_temperament(self):
        session, _p1, _p2 = self.make_session()
        session.phase_tracker["index"] = session.phase_sequence().index("resolution_compare")
        session.card_rules["m-0"].update({"power": 2, "temperaments": ["choleric"]})
        session.card_rules["m-1"].update({"power": 3, "temperaments": ["phlegmatic"]})
        first = {"id": "fight-p1", "ownerId": "p1", "cardId": "m-0", "faceUp": True, "fieldZone": "confrontation", "confrontationOrder": 1, "counters": {}}
        second = {"id": "fight-p2", "ownerId": "p2", "cardId": "m-1", "faceUp": True, "fieldZone": "confrontation", "confrontationOrder": 2, "counters": {}}
        session.battlefield = [first, second]
        session.rules_engine["ongoingEffects"] = [{
            "id": "boost", "kind": "power_modifier", "value": 1,
            "target": {"itemId": "fight-p1"}, "duration": "until_end_of_turn", "startedTurn": 1,
        }]

        result = session.prepare_rules_confrontation_result()

        self.assertEqual(result["totals"], {"p1": 3, "p2": 3})
        self.assertEqual(result["reason"], "temperament")
        self.assertEqual(result["winnerId"], "p1")
        self.assertEqual(session.rules_engine["priorityPlayerId"], "p1")

    def test_support_continuous_power_rules_share_one_public_evaluator(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules.update({
            "tentacle": {
                "type": "manifestation", "power": 2, "temperaments": ["phlegmatic"],
                "continuousPowerRules": [{"kind": "self_min_confrontation_count", "minimum": 4, "value": 1}],
            },
            "whisperer": {
                "type": "manifestation", "power": 1, "temperaments": ["phlegmatic"],
                "continuousPowerRules": [{"kind": "friendly_support_flat", "value": 1}],
            },
            "gargullo": {
                "type": "manifestation", "power": 2, "temperaments": ["phlegmatic"],
                "continuousPowerRules": [{"kind": "friendly_support_per_other_non_token_confrontation", "value": 1}],
            },
            "skapus": {
                "type": "manifestation", "power": 1, "temperaments": ["choleric"],
                "continuousPowerRules": [{"kind": "self_only_friendly_support", "value": 2}],
            },
            "cimba": {
                "type": "manifestation", "power": 2, "temperaments": ["capricious"],
                "continuousPowerRules": [{"kind": "self_any_stalemate", "value": 1}],
            },
            "support": {"type": "manifestation", "power": 1, "temperaments": ["phlegmatic"]},
            "ally": {"type": "manifestation", "power": 1, "temperaments": ["phlegmatic"]},
        })
        card = lambda item_id, owner_id, card_id, zone="confrontation", **extra: {
            "id": item_id, "ownerId": owner_id, "cardId": card_id,
            "x": 0, "y": 0, "rotation": 0,
            "faceUp": True, "fieldZone": zone, "counters": {}, **extra,
        }

        tentacle = card("tentacle", "p1", "tentacle", isSupport=True)
        session.battlefield = [
            tentacle, card("ally-1", "p1", "ally"),
            card("ally-2", "p2", "ally"), card("ally-3", "p2", "ally"),
        ]
        self.assertEqual(session.rules_manifestation_characteristics(tentacle)["power"], 3)
        session.battlefield.pop()
        self.assertEqual(session.rules_manifestation_characteristics(tentacle)["power"], 2)

        whisperer = card("whisperer", "p1", "whisperer", zone="interzone")
        support = card("support", "p1", "support", isSupport=True)
        session.battlefield = [whisperer, support]
        self.assertEqual(session.rules_manifestation_characteristics(support)["power"], 2)

        gargullo = card("gargullo", "p1", "gargullo", zone="interzone")
        ally = card("gargullo-ally", "p1", "ally")
        token = card("gargullo-token", "p1", None, isTokenCard=True, temperament="phlegmatic", power=1)
        session.battlefield = [gargullo, support, ally, token]
        self.assertEqual(session.rules_manifestation_characteristics(support)["power"], 2)

        skapus = card("skapus", "p1", "skapus", isSupport=True)
        session.battlefield = [skapus]
        self.assertEqual(session.rules_manifestation_characteristics(skapus)["power"], 3)
        self.assertEqual(
            session.serialize_for(
                "p1", "player"
            )["battlefield"][0]["effectivePower"],
            3,
        )
        session.battlefield.append(support)
        self.assertEqual(session.rules_manifestation_characteristics(skapus)["power"], 1)

        cimba = card("cimba", "p1", "cimba")
        session.battlefield = [cimba, card("stalemate", "p2", "ally", zone="stalemate")]
        self.assertEqual(session.rules_manifestation_characteristics(cimba)["power"], 3)

    def test_rally_spends_optional_extra_essence_and_creates_support_tokens(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index(
            "confrontation_reaction"
        )
        session.card_rules["rally"] = {
            "type": "ephemeral_will", "cost": 2,
            "powerCost": "{G}{G}", "temperaments": ["phlegmatic"],
            "playedAbilities": [{
                "id": "rally",
                "action": "play_card",
                "targets": {"min": 0, "max": 0},
                "optionalExtraEssence": {
                    "temperament": "hollow", "max": 20,
                },
                "result": {
                    "kind":
                    "create_support_tokens_from_optional_extra_essence",
                },
            }],
        }
        p1["zones"]["hand"] = ["rally", "m-0", "m-1"]
        p1["zoneOwners"]["hand"] = {
            "rally": "p1", "m-0": "p1", "m-1": "p1",
        }
        session.tokens = [{
            "id": "hollow", "ownerId": "p1",
            "isEssence": True, "isNeutralCounter": False,
            "temperament": "hollow",
            "counters": {"essence": 2},
        }]

        extra_error, _action = session.declare_rules_action(
            "p1", "Rally", kind="play_card",
            source={"cardId": "rally", "zone": "hand"},
            payment_card_ids=["m-0", "m-1"],
            ability_id="rally",
            extra_essence_count=3,
        )
        self.assertIn("Not enough Essences", extra_error)

        error, action = session.declare_rules_action(
            "p1", "Rally", kind="play_card",
            source={"cardId": "rally", "zone": "hand"},
            payment_card_ids=["m-0", "m-1"],
            ability_id="rally",
            extra_essence_count=2,
        )
        self.assertIsNone(error)
        self.assertEqual(action["cost"]["optionalExtraEssenceSpent"], 2)
        self.assertEqual(session.tokens, [])
        session.pass_rules_priority("p2")
        resolve_error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(resolve_error)
        self.assertEqual(
            resolution["action"]["effectResult"]["count"], 2
        )
        support_tokens = [
            item for item in session.battlefield
            if item.get("isTokenCard") and item.get("isSupport")
        ]
        self.assertEqual(len(support_tokens), 2)
        self.assertTrue(all(item["power"] == 1 for item in support_tokens))

    def test_confrontation_cleanup_captures_loser_then_guides_winner(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = session.phase_sequence().index("resolution_compare")
        session.card_rules["m-0"]["power"] = 4
        session.card_rules["m-1"]["power"] = 1
        winner = {"id": "winner", "ownerId": "p1", "cardId": "m-0", "faceUp": True, "fieldZone": "confrontation", "confrontationOrder": 1, "counters": {}}
        loser = {"id": "loser", "ownerId": "p2", "cardId": "m-1", "faceUp": True, "fieldZone": "confrontation", "confrontationOrder": 2, "counters": {}}
        session.battlefield = [winner, loser]
        session.prepare_rules_confrontation_result()
        session.phase_tracker["index"] = session.phase_sequence().index("resolution_move")

        result = session.begin_rules_confrontation_cleanup()

        self.assertNotIn(loser, session.battlefield)
        self.assertEqual(p1["zones"]["receptacle"], ["m-1"])
        self.assertEqual(p1["zoneOwners"]["receptacle"]["m-1"], "p2")
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "confrontation_destination")
        error, resolution = session.resolve_rules_choice(
            "p1", choice["id"], option="deck_bottom"
        )
        self.assertIsNone(error)
        self.assertEqual(resolution["destination"], "deck_bottom")
        self.assertEqual(p1["zones"]["deck"][-1], "m-0")
        self.assertEqual(result["status"], "complete")

    def test_wandering_veteran_winning_as_support_is_exiled_without_destination_choice(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["veteran"] = {
            "type": "manifestation", "power": 2, "temperaments": ["choleric"],
            "supportWinDestination": "exile",
        }
        session.card_rules["m-1"]["power"] = 1
        session.phase_tracker["index"] = session.phase_sequence().index("resolution_compare")
        veteran = {
            "id": "veteran-support", "ownerId": "p1", "cardId": "veteran",
            "faceUp": True,
            "temperamentOverride": "hollow", "counters": {},
        }
        loser = {
            "id": "loser", "ownerId": "p2", "cardId": "m-1",
            "faceUp": True, "fieldZone": "confrontation", "confrontationOrder": 1,
            "counters": {},
        }
        session.mark_rules_support_entry(veteran)
        session.battlefield = [veteran, loser]
        result = session.prepare_rules_confrontation_result()
        session.phase_tracker["index"] = session.phase_sequence().index("resolution_move")

        session.begin_rules_confrontation_cleanup()

        self.assertEqual(result["winnerId"], "p1")
        self.assertEqual(result["supportExiled"][0]["cardId"], "veteran")
        self.assertEqual(p1["zones"]["exile"], ["veteran"])
        self.assertNotIn(veteran, session.battlefield)
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertEqual(result["status"], "complete")

    def test_merciful_pago_winning_as_support_enters_opponent_vessel_and_scores(self):
        session, _p1, p2 = self.make_session()
        session.card_rules["pago"] = {
            "type": "manifestation", "power": 3, "temperaments": ["phlegmatic"],
            "supportWinEffect": {"kind": "opponent_vessel_score", "value": 10},
        }
        session.card_rules["m-1"]["power"] = 1
        session.phase_tracker["index"] = session.phase_sequence().index("resolution_compare")
        pago = {
            "id": "pago-support", "ownerId": "p1", "cardId": "pago",
            "faceUp": True, "counters": {},
        }
        loser = {
            "id": "loser", "ownerId": "p2", "cardId": "m-1",
            "faceUp": True, "fieldZone": "confrontation", "confrontationOrder": 1,
            "counters": {},
        }
        session.mark_rules_support_entry(pago)
        session.battlefield = [pago, loser]
        result = session.prepare_rules_confrontation_result()
        session.phase_tracker["index"] = session.phase_sequence().index("resolution_move")

        session.begin_rules_confrontation_cleanup()

        resolved = result["supportResolved"][0]
        self.assertEqual(resolved["kind"], "opponent_vessel_score")
        self.assertEqual(resolved["cardId"], "pago")
        self.assertEqual(resolved["playerId"], "p2")
        self.assertEqual(resolved["delta"], 10)
        self.assertEqual(p2["score"], 10)
        self.assertEqual(p2["zones"]["receptacle"], ["pago"])
        self.assertEqual(p2["zoneOwners"]["receptacle"]["pago"], "p1")
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertEqual(result["status"], "complete")

    def test_equal_power_and_temperament_moves_cards_to_stalemate(self):
        session, _p1, _p2 = self.make_session()
        session.phase_tracker["index"] = session.phase_sequence().index("resolution_compare")
        first = {"id": "tie-p1", "ownerId": "p1", "cardId": "m-0", "faceUp": True, "fieldZone": "confrontation", "confrontationOrder": 1, "counters": {}}
        second = {"id": "tie-p2", "ownerId": "p2", "cardId": "m-1", "faceUp": True, "fieldZone": "confrontation", "confrontationOrder": 2, "counters": {}}
        session.battlefield = [first, second]
        result = session.prepare_rules_confrontation_result()
        session.phase_tracker["index"] = session.phase_sequence().index("resolution_move")

        session.begin_rules_confrontation_cleanup()

        self.assertTrue(result["stalemate"])
        self.assertEqual(first["fieldZone"], "stalemate")
        self.assertEqual(second["fieldZone"], "stalemate")
        self.assertEqual(result["status"], "complete")
        self.assertIsNone(session.rules_engine["pendingChoice"])

    def test_full_interzone_requires_a_replacement_choice(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = session.phase_sequence().index("resolution_compare")
        session.card_rules["m-0"]["power"] = 5
        session.card_rules["m-1"]["power"] = 1
        existing = [
            {"id": f"inter-{index}", "ownerId": "p1", "cardId": f"m-{index + 2}", "faceUp": True, "fieldZone": "interzone", "counters": {}}
            for index in range(3)
        ]
        winner = {"id": "new-inter", "ownerId": "p1", "cardId": "m-0", "faceUp": True, "fieldZone": "confrontation", "confrontationOrder": 1, "counters": {}}
        loser = {"id": "lost", "ownerId": "p2", "cardId": "m-1", "faceUp": True, "fieldZone": "confrontation", "confrontationOrder": 2, "counters": {}}
        session.battlefield = existing + [winner, loser]
        session.prepare_rules_confrontation_result()
        session.phase_tracker["index"] = session.phase_sequence().index("resolution_move")
        session.begin_rules_confrontation_cleanup()
        destination = session.rules_engine["pendingChoice"]
        session.resolve_rules_choice("p1", destination["id"], option="interzone")
        replacement = session.rules_engine["pendingChoice"]

        self.assertEqual(replacement["kind"], "confrontation_replace_interzone")
        error, resolution = session.resolve_rules_choice(
            "p1", replacement["id"], item_id="inter-0"
        )
        self.assertIsNone(error)
        self.assertEqual(resolution["replacedItemId"], "inter-0")
        self.assertEqual(winner["fieldZone"], "interzone")
        self.assertNotIn(existing[0], session.battlefield)
        self.assertEqual(p1["zones"]["deck"][-1], "m-2")
        self.assertEqual(len(session.rules_confrontation_items("p1", ("interzone",))), 3)

    def test_new_turn_reopens_first_manifestation_selection(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker["index"] = len(session.phase_sequence()) - 1
        session.rules_engine["firstManifestationComplete"] = True
        session.rules_engine["firstManifestationItemIds"] = {"p1": "old-1", "p2": "old-2"}
        session.rules_engine["priorityPlayerId"] = "p1"
        exhausted = {
            "id": "exhausted", "ownerId": "p1", "cardId": "m-0",
            "faceUp": True, "rotation": 90, "counters": {},
        }
        already_ready = {
            "id": "ready", "ownerId": "p2", "cardId": "m-1",
            "faceUp": True, "rotation": 180, "counters": {},
        }
        session.battlefield = [exhausted, already_ready]
        self.fill_deck(p1, [f"m-{index}" for index in range(7)])
        self.fill_deck(p2, [f"m-{index}" for index in range(7, 14)])

        session.pass_rules_priority("p1")
        error, result = session.pass_rules_priority("p2")

        self.assertIsNone(error)
        self.assertEqual(result["phaseId"], "recovery_end")
        self.assertEqual(session.phase_tracker["turn"], 2)
        self.assertFalse(session.rules_engine["firstManifestationComplete"])
        self.assertEqual(session.rules_engine["firstManifestationItemIds"], {})
        self.assertEqual(exhausted["rotation"], 0.0)
        self.assertEqual(already_ready["rotation"], 180)
        self.assertEqual(result["readiedItemIds"], ["exhausted"])

    def test_interzone_manifestation_can_enter_only_during_reaction(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["m-0"]["supportFromInterzone"] = True
        item = {
            "id": "waiting", "ownerId": "p1", "cardId": "m-0", "faceUp": True,
            "fieldZone": "interzone", "counters": {},
        }
        session.battlefield = [item]

        error, _result = session.set_rules_field_zone("p1", item["id"], "confrontation")
        self.assertIn("only during Reaction", error)
        session.phase_tracker["index"] = session.phase_sequence().index("confrontation_reaction")
        session.rules_engine["priorityPlayerId"] = "p1"
        error, result = session.set_rules_field_zone("p1", item["id"], "confrontation")

        self.assertIsNone(error)
        self.assertEqual(result["fieldZone"], "confrontation")
        self.assertEqual(item["fieldZone"], "confrontation")
        self.assertEqual(item["confrontationOrder"], 1)
        self.assertTrue(item["isSupport"])
        self.assertTrue(result["asSupport"])

    def test_interzone_manifestation_requires_support_and_priority(self):
        session, _p1, _p2 = self.make_session()
        session.phase_tracker["index"] = session.phase_sequence().index("confrontation_reaction")
        item = {
            "id": "waiting", "ownerId": "p1", "cardId": "m-0", "faceUp": True,
            "fieldZone": "interzone", "counters": {},
        }
        session.battlefield = [item]
        session.rules_engine["priorityPlayerId"] = "p1"

        error, result = session.set_rules_field_zone("p1", item["id"], "confrontation")
        self.assertIn("does not currently have Support", error)
        self.assertIsNone(result)

        session.card_rules["m-0"]["supportFromInterzone"] = True
        session.rules_engine["priorityPlayerId"] = "p2"
        error, result = session.set_rules_field_zone("p1", item["id"], "confrontation")
        self.assertIn("priority", error)
        self.assertIsNone(result)

    def test_support_from_hand_is_limited_to_printed_cards_during_reaction(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["m-0"]["supportFromHand"] = True
        session.rules_engine["priorityPlayerId"] = "p1"

        error = session.rules_support_from_hand_error("p1", "m-0")
        self.assertIn("during Reaction", error)

        session.phase_tracker["index"] = session.phase_sequence().index("confrontation_reaction")
        session.rules_engine["priorityPlayerId"] = "p2"
        error = session.rules_support_from_hand_error("p1", "m-0")
        self.assertIn("priority", error)

        session.rules_engine["priorityPlayerId"] = "p1"
        self.assertIsNone(session.rules_support_from_hand_error("p1", "m-0"))
        error = session.rules_support_from_hand_error("p1", "m-1")
        self.assertIn("does not have Support from Hand", error)

    def test_first_manifestation_rejects_cards_with_printed_restriction(self):
        session, _p1, _p2 = self.make_session()
        session.phase_tracker["index"] = session.phase_sequence().index("confrontation_choose")
        session.card_rules["m-0"]["canBeFirstManifestation"] = False
        item = {
            "id": "restricted-first", "ownerId": "p1", "cardId": "m-0",
            "faceUp": False, "counters": {},
        }

        error = session.register_first_manifestation("p1", item)

        self.assertIn("first play", error)
        self.assertNotIn("p1", session.rules_engine["firstManifestationItemIds"])

    def test_started_match_rejects_wills_outside_their_timing_windows(self):
        session, p1, _p2 = self.make_session()
        session.rules_engine["readyPlayerIds"] = ["p1", "p2"]
        session.rules_engine["priorityPlayerId"] = "p1"
        p1["zones"]["hand"] = ["will-ephemeral"]
        p1["zoneOwners"]["hand"] = {"will-ephemeral": "p1"}
        session.phase_tracker["index"] = session.phase_sequence().index("resolution_move")

        error, action = session.declare_rules_action(
            "p1", "Too late", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
        )

        self.assertIn("current step", error)
        self.assertIsNone(action)
        session.phase_tracker["index"] = session.phase_sequence().index("confrontation_reaction")
        session.tokens = [{
            "id": "essence", "ownerId": "p1", "isEssence": True,
            "isNeutralCounter": False, "temperament": "transcendent",
            "counters": {"essence": 1},
        }]
        error, action = session.declare_rules_action(
            "p1", "Legal reaction", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
        )
        self.assertIsNone(error)
        self.assertEqual(action["phaseId"], "confrontation_reaction")

    def test_targets_are_revalidated_with_their_full_contract_on_resolution(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
        session.card_rules["will-ephemeral"]["playedAbilities"] = [{
            "id": "boost-small", "action": "play_card",
            "targets": {
                "min": 1, "max": 1, "cardType": "manifestation",
                "maxPower": 2,
            },
            "ongoingEffect": {
                "kind": "power_modifier", "value": 2,
                "duration": "until_end_of_turn",
            },
        }]
        session.card_rules["m-2"]["power"] = 2
        target = {
            "id": "target", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation",
            "rotation": 0, "counters": {},
        }
        session.battlefield = [target]
        p1["zones"]["hand"] = ["will-ephemeral", "m-0"]
        p1["zoneOwners"]["hand"] = {"will-ephemeral": "p1", "m-0": "p1"}

        error, _action = session.declare_rules_action(
            "p1", "Boost small", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            targets=[{"kind": "card", "itemId": "target", "cardId": "m-2"}],
            payment_card_ids=["m-0"], ability_id="boost-small",
        )
        self.assertIsNone(error)
        target["counters"]["power"] = 1
        session.pass_rules_priority("p2")
        error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(error)
        self.assertEqual(
            resolution["action"]["effectResult"]["kind"], "invalid_targets"
        )
        self.assertEqual(session.rules_engine["ongoingEffects"], [])
        self.assertEqual(session.rules_manifestation_characteristics(target)["power"], 3)

    def test_power_reaching_zero_is_destroyed_immediately_after_resolution(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
        session.card_rules["will-ephemeral"]["playedAbilities"] = [{
            "id": "weaken-one", "action": "play_card",
            "targets": {"min": 1, "max": 1, "cardType": "manifestation"},
            "ongoingEffect": {
                "kind": "power_modifier", "value": -1,
                "duration": "until_end_of_turn",
            },
        }]
        target = {
            "id": "target", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation",
            "rotation": 0, "counters": {},
        }
        session.battlefield = [target]
        p1["zones"]["hand"] = ["will-ephemeral", "m-0"]
        p1["zoneOwners"]["hand"] = {"will-ephemeral": "p1", "m-0": "p1"}

        error, _action = session.declare_rules_action(
            "p1", "Weaken", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            targets=[{"kind": "card", "itemId": "target", "cardId": "m-2"}],
            payment_card_ids=["m-0"], ability_id="weaken-one",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(error)
        self.assertIsNone(session.find_battlefield_item("target"))
        self.assertEqual(session.players["p2"]["zones"]["graveyard"], ["m-2"])
        self.assertEqual(
            resolution["action"]["stateActions"]["destroyed"][0]["itemId"], "target"
        )
        self.assertEqual(session.rules_engine["ongoingEffects"], [])

    def test_generated_excess_essence_expires_but_manual_essence_does_not(self):
        session, _p1, _p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index("end_expire")
        session.rules_engine["priorityPlayerId"] = "p1"
        session.tokens = [{
            "id": "manual", "ownerId": "p1", "isEssence": True,
            "isNeutralCounter": False, "temperament": "phlegmatic",
            "counters": {"essence": 1},
        }]
        created = session.add_rules_excess_essence(
            "p1", [{"temperament": "phlegmatic", "amount": 1}]
        )
        generated_id = created[0]["tokenId"]

        session.pass_rules_priority("p1")
        error, result = session.pass_rules_priority("p2")

        self.assertIsNone(error)
        self.assertEqual(result["expiredEssenceTokenIds"], [generated_id])
        self.assertEqual([token["id"] for token in session.tokens], ["manual"])

    def test_adamant_prevents_an_opponents_encoded_zone_change(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
        session.card_rules["m-2"]["adamant"] = True
        session.card_rules["will-ephemeral"]["playedAbilities"] = [{
            "id": "return-target", "action": "play_card",
            "targets": {"min": 1, "max": 1, "cardType": "manifestation"},
            "result": {"kind": "move_target", "zone": "hand", "position": "top"},
        }]
        target = {
            "id": "adamant", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation",
            "rotation": 0, "counters": {},
        }
        session.battlefield = [target]
        p1["zones"]["hand"] = ["will-ephemeral", "m-0"]
        p1["zoneOwners"]["hand"] = {"will-ephemeral": "p1", "m-0": "p1"}

        error, _action = session.declare_rules_action(
            "p1", "Return target", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            targets=[{"kind": "card", "itemId": "adamant", "cardId": "m-2"}],
            payment_card_ids=["m-0"], ability_id="return-target",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(error)
        self.assertEqual(
            resolution["action"]["effectResult"]["status"], "prevented_adamant"
        )
        self.assertIsNotNone(session.find_battlefield_item("adamant"))
        self.assertEqual(session.players["p2"]["zones"]["hand"], [])

    def test_float_shares_a_full_interzone_slot_during_cleanup(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["m-0"]["float"] = True
        entering = {
            "id": "entering", "ownerId": "p1", "cardId": "m-0",
            "faceUp": True, "fieldZone": "confrontation",
            "rotation": 0, "counters": {},
        }
        interzone = [
            {
                "id": f"slot-{index}", "ownerId": "p1", "cardId": f"m-{index + 1}",
                "faceUp": True, "fieldZone": "interzone",
                "rotation": 0, "counters": {},
            }
            for index in range(3)
        ]
        session.battlefield = interzone + [entering]
        session.rules_engine["confrontationResult"] = {
            "winnerId": "p1", "pendingOwnItemIds": ["entering"],
            "status": "cleanup", "returned": [],
        }
        session.rules_engine["pendingChoice"] = {
            "id": "destination", "kind": "confrontation_destination",
            "playerId": "p1", "itemId": "entering", "cardId": "m-0",
            "options": ["interzone", "deck_bottom"],
        }

        error, result = session.resolve_rules_choice(
            "p1", "destination", option="interzone"
        )

        self.assertIsNone(error)
        self.assertEqual(result["destination"], "interzone")
        self.assertEqual(entering["stackedOn"], "slot-0")
        self.assertEqual(session.rules_interzone_slot_count("p1"), 3)

    def test_suspend_is_distinct_from_exile_and_can_restore_to_owner(self):
        session, p1, _p2 = self.make_session()
        p1["zones"]["hand"] = ["m-0"]
        p1["zoneOwners"]["hand"] = {"m-0": "p1"}

        error, suspended = session.suspend_zone_card(
            "p1", "hand", "m-0", source_effect_id="effect-1"
        )
        self.assertIsNone(error)
        self.assertEqual(p1["zones"]["hand"], [])
        self.assertEqual(p1["zones"]["exile"], [])
        self.assertEqual(suspended["sourceEffectId"], "effect-1")

        error, restored = session.restore_suspended_card(suspended["id"])
        self.assertIsNone(error)
        self.assertEqual(restored["cardId"], "m-0")
        self.assertEqual(p1["zones"]["hand"], ["m-0"])

    def test_power_limits_clamp_derived_power_after_modifiers(self):
        session, _p1, _p2 = self.make_session()
        item = {
            "id": "limited", "ownerId": "p1", "cardId": "m-0",
            "faceUp": True, "rotation": 0, "counters": {"power": 5},
            "maximumPower": 3,
        }
        self.assertEqual(session.rules_manifestation_characteristics(item)["power"], 3)
        item["counters"]["power"] = -5
        item["minimumPower"] = 2
        self.assertEqual(session.rules_manifestation_characteristics(item)["power"], 2)

    def test_pending_choice_blocks_new_stack_actions(self):
        session, _p1, _p2 = self.make_session()
        session.rules_engine["pendingChoice"] = {
            "id": "choice", "kind": "test", "playerId": "p1",
        }

        error, action = session.declare_rules_action(
            "p1", "Should wait", kind="manual"
        )

        self.assertIn("required card choice", error)
        self.assertIsNone(action)

    def test_unresolvable_hand_action_returns_public_proof(self):
        session, _p1, p2 = self.make_session()
        p2["zones"]["hand"] = ["will-ephemeral"]
        p2["zoneOwners"]["hand"] = {"will-ephemeral": "p2"}
        action = {
            "id": "discard-action",
            "controllerId": "p1",
            "targets": [{"kind": "player", "playerId": "p2"}],
            "ability": {
                "result": {"kind": "discard_hand_target", "value": 2},
            },
        }

        result = session.apply_rules_action_result(action)

        self.assertEqual(result["kind"], "choice_required")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["handProofPlayerId"], "p2")
        self.assertEqual(result["handProof"], ["will-ephemeral"])

    def test_persist_keeps_winner_as_first_manifestation_for_next_turn(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["m-0"]["power"] = 3
        session.card_rules["m-1"]["power"] = 1
        persisted = {
            "id": "persisted", "ownerId": "p1", "cardId": "m-0",
            "faceUp": True, "fieldZone": "confrontation",
            "confrontationOrder": 1, "counters": {},
        }
        opponent = {
            "id": "opponent", "ownerId": "p2", "cardId": "m-1",
            "faceUp": True, "fieldZone": "confrontation",
            "confrontationOrder": 2, "counters": {},
        }
        session.battlefield = [persisted, opponent]
        session.rules_engine["ongoingEffects"] = [{
            "id": "persist-effect", "kind": "grant_persist",
            "duration": "until_end_of_turn", "startedTurn": 1,
            "source": {"cardId": "will-ephemeral"},
            "target": {"itemId": "persisted", "cardId": "m-0"},
        }]
        session.phase_tracker["index"] = ADVANCED_PHASES.index("resolution_compare")

        result = session.prepare_rules_confrontation_result()
        self.assertEqual(result["winnerId"], "p1")
        cleanup = session.begin_rules_confrontation_cleanup()

        self.assertEqual(cleanup["status"], "complete")
        self.assertEqual(cleanup["persisted"][0]["itemId"], "persisted")
        self.assertTrue(persisted["persistedFirst"])
        self.assertEqual(persisted["fieldZone"], "confrontation")
        self.assertEqual(session.players["p1"]["zones"]["receptacle"], ["m-1"])

        session.reset_rules_confrontation_turn()

        self.assertEqual(
            session.rules_engine["firstManifestationItemIds"], {"p1": "persisted"}
        )
        self.assertEqual(
            session.rules_engine["firstManifestationValidatedPlayerIds"], ["p1"]
        )
        self.assertFalse(session.rules_engine["firstManifestationComplete"])

    def test_persisted_player_is_locked_while_opponent_selects_first(self):
        session, _p1, _p2 = self.make_session()
        persisted = {
            "id": "persisted", "ownerId": "p1", "cardId": "m-0",
            "faceUp": True, "fieldZone": "confrontation",
            "persistedFirst": True, "confrontationOrder": 1, "counters": {},
        }
        session.battlefield = [persisted]
        session.reset_rules_confrontation_turn()
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_choose")
        challenger = {
            "id": "challenger", "ownerId": "p2", "cardId": "m-1",
            "faceUp": True, "counters": {},
        }
        session.battlefield.append(challenger)

        cancel_error, _ = session.validate_first_manifestation("p1", validated=False)
        self.assertIn("locked", cancel_error)
        self.assertIsNone(session.register_first_manifestation("p2", challenger))
        validation_error, validation = session.validate_first_manifestation("p2")

        self.assertIsNone(validation_error)
        self.assertTrue(validation["selectionComplete"])
        self.assertEqual(
            session.current_phase_id(), "confrontation_before_revelation"
        )
        self.assertTrue(persisted["faceUp"])
        self.assertFalse(challenger["faceUp"])

    def test_multiple_persist_winners_require_a_first_manifestation_choice(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["m-0"]["persist"] = True
        session.card_rules["m-1"]["persist"] = True
        session.card_rules["m-0"]["power"] = 2
        session.card_rules["m-1"]["power"] = 2
        session.card_rules["m-2"]["power"] = 1
        first = {
            "id": "first", "ownerId": "p1", "cardId": "m-0",
            "faceUp": True, "fieldZone": "confrontation",
            "confrontationOrder": 1, "counters": {},
        }
        second = {
            "id": "second", "ownerId": "p1", "cardId": "m-1",
            "faceUp": True, "fieldZone": "confrontation",
            "confrontationOrder": 2, "isSupport": True, "counters": {},
        }
        opponent = {
            "id": "opponent", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation",
            "confrontationOrder": 3, "counters": {},
        }
        session.battlefield = [first, second, opponent]
        session.phase_tracker["index"] = ADVANCED_PHASES.index("resolution_compare")
        session.prepare_rules_confrontation_result()

        cleanup = session.begin_rules_confrontation_cleanup()

        self.assertEqual(cleanup["status"], "cleanup_choice")
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "persist_first_manifestation")
        error, selected = session.resolve_rules_choice(
            "p1", choice["id"], item_id="second"
        )
        self.assertIsNone(error)
        self.assertEqual(selected["itemId"], "second")
        self.assertTrue(second["persistedFirst"])
        self.assertEqual(session.players["p1"]["zones"]["deck"], ["m-0"])

    def test_source_only_target_contract_rejects_another_manifestation(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
        session.card_rules["m-0"]["activatedAbilities"] = [{
            "id": "self-persist",
            "tribute": "{H}",
            "sourceFieldZone": "confrontation",
            "targets": {
                "min": 1, "max": 1, "cardType": "manifestation",
                "fieldZone": "confrontation", "controller": "self",
                "sourceOnly": True,
            },
            "ongoingEffect": {
                "kind": "grant_persist", "duration": "until_end_of_turn",
            },
        }]
        source = {
            "id": "source", "ownerId": "p1", "cardId": "m-0",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        other = {
            "id": "other", "ownerId": "p1", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield = [source, other]
        p1["zones"]["hand"] = ["m-1"]
        p1["zoneOwners"]["hand"] = {"m-1": "p1"}

        error, action = session.declare_rules_action(
            "p1", "Persist other", kind="activated_effect",
            source={"cardId": "m-0", "zone": "battlefield", "itemId": "source"},
            targets=[{"kind": "card", "itemId": "other", "cardId": "m-2"}],
            payment_card_ids=["m-1"], ability_id="self-persist",
        )

        self.assertIn("source Manifestation", error)
        self.assertIsNone(action)

    def test_effect_memory_survives_public_zones_but_not_deck_or_exile(self):
        session, p1, p2 = self.make_session()
        p1["zones"]["graveyard"] = ["m-0"]
        p1["zoneOwners"]["graveyard"] = {"m-0": "p1"}
        memory = session.create_rules_effect_memory(
            "p1", "m-0", "return_from_limbo_end_turn"
        )

        self.assertIsNone(session.move_zone_card(
            "p1", "graveyard", "p1", "hand", "m-0"
        )[0])
        self.assertEqual(
            session.rules_engine["effectMemories"][0]["id"], memory["id"]
        )
        self.assertIsNone(session.move_zone_card(
            "p1", "hand", "p2", "receptacle", "m-0"
        )[0])
        self.assertEqual(len(session.rules_engine["effectMemories"]), 1)
        self.assertIsNone(session.move_zone_card(
            "p2", "receptacle", "p1", "deck", "m-0"
        )[0])
        self.assertEqual(session.rules_engine["effectMemories"], [])

    def test_lady_chain_memory_exiles_the_chained_winner_and_shuffles(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["lady"] = {
            "type": "manifestation", "power": 2,
            "temperaments": ["phlegmatic"],
            "triggeredAbilities": [{
                "id": "lady-chain",
                "trigger": {"event": "enters_field", "visibility": "face_up"},
                "result": {
                    "kind": "chain_from_zone", "zone": "deck",
                    "optional": False, "winDestination": "exile",
                    "shuffleAfter": True,
                },
            }],
        }
        session.card_rules["m-1"]["power"] = 3
        lady = {
            "id": "lady", "ownerId": "p1", "cardId": "lady",
            "x": 400, "y": 500, "rotation": 0,
            "faceUp": True, "fieldZone": "confrontation",
            "confrontationOrder": 1, "counters": {},
        }
        opponent = {
            "id": "opponent", "ownerId": "p2", "cardId": "m-2",
            "x": 800, "y": 500, "rotation": 0,
            "faceUp": True, "fieldZone": "confrontation",
            "confrontationOrder": 2, "counters": {},
        }
        session.battlefield = [lady, opponent]
        self.fill_deck(p1, ["m-1", "will-ephemeral", "m-3"])

        actions = session.queue_rules_battlefield_entry_triggers(
            "lady", "p1", "lady", True
        )
        self.assertEqual(len(actions), 1)
        session.pass_rules_priority("p2")
        error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error)
        self.assertEqual(
            resolution["action"]["effectResult"]["choiceKind"],
            "chain_manifestation",
        )
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["cardIds"], ["m-1", "m-3"])
        owner_choice = session.serialize_for(
            "p1", "player"
        )["rulesEngine"]["pendingChoice"]
        opponent_choice = session.serialize_for(
            "p2", "player"
        )["rulesEngine"]["pendingChoice"]
        self.assertEqual(owner_choice["cardIds"], ["m-1", "m-3"])
        self.assertNotIn("cardIds", opponent_choice)
        invalid_error, _invalid = session.resolve_rules_choice(
            "p1", choice["id"], ["will-ephemeral"],
            placement={"x": 400, "y": 500},
        )
        self.assertIn("not eligible", invalid_error)
        with patch("session.random.shuffle") as shuffle:
            error, chained = session.resolve_rules_choice(
                "p1", choice["id"], ["m-1"], placement={"x": 400, "y": 500}
            )
        self.assertIsNone(error)
        shuffle.assert_called_once_with(p1["zones"]["deck"])
        self.assertIsNotNone(chained["memoryId"])
        chained_item = session.find_battlefield_item(chained["itemId"])
        self.assertTrue(chained_item["isChained"])

        session.phase_tracker["index"] = ADVANCED_PHASES.index("resolution_compare")
        comparison = session.prepare_rules_confrontation_result()
        self.assertEqual(comparison["winnerId"], "p1")
        session.begin_rules_confrontation_cleanup()

        self.assertIn("m-1", p1["zones"]["exile"])
        self.assertIsNone(session.find_battlefield_item(chained["itemId"]))
        self.assertEqual(session.rules_engine["effectMemories"], [])

    def test_coral_skull_memory_can_return_the_paid_will_at_end_of_turn(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["m-1"]["triggeredAbilities"] = [{
            "id": "coral-memory",
            "trigger": {"event": "used_as_tribute"},
            "result": {
                "kind": "create_effect_memory",
                "memoryKind": "return_from_limbo_end_turn",
                "attachTo": "paid_action_source",
                "optional": True,
            },
        }]
        p1["zones"]["hand"] = ["will-ephemeral", "m-1"]
        p1["zoneOwners"]["hand"] = {
            "will-ephemeral": "p1", "m-1": "p1",
        }
        error, paid_action = session.declare_rules_action(
            "p1", "Play Will", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            payment_card_ids=["m-1"],
        )
        self.assertIsNone(error)
        triggers = session.queue_rules_tribute_triggers(
            ["m-1"], "p1", simultaneous_action_id=paid_action["id"]
        )
        order_choice = session.rules_engine["pendingChoice"]
        self.assertIsNone(session.resolve_rules_choice(
            "p1", order_choice["id"], [paid_action["id"], triggers[0]["id"]]
        )[0])
        session.pass_rules_priority("p2")
        self.assertIsNone(session.pass_rules_priority("p1")[0])
        self.assertEqual(
            session.rules_engine["effectMemories"][0]["cardId"],
            "will-ephemeral",
        )
        session.pass_rules_priority("p2")
        self.assertIsNone(session.pass_rules_priority("p1")[0])
        self.assertEqual(p1["zones"]["graveyard"], ["will-ephemeral", "m-1"])

        session.phase_tracker["index"] = ADVANCED_PHASES.index("end_actions")
        session.rules_engine["priorityPlayerId"] = "p1"
        session.pass_rules_priority("p1")
        error, advanced = session.pass_rules_priority("p2")
        self.assertIsNone(error)
        self.assertEqual(len(advanced["endTriggeredActions"]), 1)
        optional_choice = session.rules_engine["pendingChoice"]
        self.assertEqual(optional_choice["kind"], "optional_stack_action")
        self.assertEqual(session.rules_engine["actionStack"], [])
        self.assertIsNone(session.resolve_rules_choice(
            "p1", optional_choice["id"], option="accept"
        )[0])
        session.pass_rules_priority("p2")
        error, memory_resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error)
        self.assertEqual(
            memory_resolution["action"]["effectResult"]["status"], "returned"
        )
        self.assertIn("will-ephemeral", p1["zones"]["hand"])
        self.assertEqual(session.rules_engine["effectMemories"], [])

    def test_refrain_memory_opponent_can_pay_to_prevent_return(self):
        session, p1, p2 = self.make_session()
        p1["zones"]["graveyard"] = ["m-0"]
        p1["zoneOwners"]["graveyard"] = {"m-0": "p1"}
        p2["zones"]["hand"] = ["m-1"]
        p2["zoneOwners"]["hand"] = {"m-1": "p2"}
        memory = session.create_rules_effect_memory(
            "p1", "m-0", "return_from_limbo_end_turn",
            controller_id="p1",
            data={"opponentPayment": "{H}"},
        )
        session.phase_tracker["index"] = ADVANCED_PHASES.index("end_actions")
        session.rules_engine["priorityPlayerId"] = "p1"

        session.pass_rules_priority("p1")
        error, advanced = session.pass_rules_priority("p2")
        self.assertIsNone(error)
        self.assertEqual(advanced["endTriggeredActions"][0]["source"]["cardId"], "m-0")
        session.pass_rules_priority("p2")
        error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error)
        self.assertEqual(
            resolution["action"]["effectResult"]["choiceKind"],
            "effect_memory_payment",
        )
        payment_choice = session.rules_engine["pendingChoice"]
        error, paid = session.resolve_rules_choice(
            "p2", payment_choice["id"], ["m-1"], option="pay"
        )

        self.assertIsNone(error)
        self.assertEqual(paid["status"], "paid")
        self.assertIn("m-0", p1["zones"]["graveyard"])
        self.assertIn("m-1", p2["zones"]["graveyard"])
        self.assertIsNone(next((
            entry for entry in session.rules_engine["effectMemories"]
            if entry["id"] == memory["id"]
        ), None))

    def test_tribute_destination_replacements_use_deck_and_stalemate(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["m-0"].update({
            "power": 1, "temperaments": ["phlegmatic"],
            "tributeDestination": "deck_bottom",
        })
        p1["zones"]["hand"] = ["will-ephemeral", "m-0"]
        p1["zoneOwners"]["hand"] = {
            "will-ephemeral": "p1", "m-0": "p1",
        }
        error, deck_action = session.declare_rules_action(
            "p1", "Deck replacement", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            payment_card_ids=["m-0"],
        )
        self.assertIsNone(error)
        self.assertEqual(p1["zones"]["deck"], ["m-0"])
        self.assertEqual(p1["zones"]["graveyard"], [])
        self.assertEqual(
            deck_action["cost"]["tributeMovements"][0]["destination"],
            "deck_bottom",
        )

        session.reset_phase_tracker()
        session.rules_engine["priorityPlayerId"] = "p1"
        session.card_rules["m-1"].update({
            "power": 1, "temperaments": ["phlegmatic"],
            "tributeDestination": "stalemate",
        })
        p1["zones"]["hand"] = ["will-ephemeral", "m-1"]
        p1["zoneOwners"]["hand"] = {
            "will-ephemeral": "p1", "m-1": "p1",
        }
        error, stalemate_action = session.declare_rules_action(
            "p1", "Stalemate replacement", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            payment_card_ids=["m-1"],
        )
        self.assertIsNone(error)
        stalemate_item = next(
            item for item in session.battlefield if item.get("cardId") == "m-1"
        )
        self.assertEqual(stalemate_item["fieldZone"], "stalemate")
        self.assertEqual(
            stalemate_action["cost"]["tributeMovements"][0]["destination"],
            "stalemate",
        )

    def test_named_counters_can_be_generated_and_spent_as_an_activated_cost(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
        session.card_rules["blossom"] = {
            "type": "manifestation", "power": 2,
            "temperaments": ["phlegmatic"],
            "triggeredAbilities": [{
                "id": "gain-petal",
                "trigger": {
                    "event": "manifestation_enters_field",
                    "eventController": "owner",
                },
                "result": {
                    "kind": "add_counter_source",
                    "counter": "Petal", "value": 1,
                },
            }],
            "activatedAbilities": [{
                "id": "spend-petals",
                "tribute": "{H}{H}",
                "removeAllCountersFromSource": "Petal",
                "targets": {
                    "min": 1, "max": 1,
                    "cardType": "manifestation",
                },
                "ongoingEffect": {
                    "kind": "power_modifier",
                    "valuePerRemovedCounter": 1,
                    "duration": "until_end_of_turn",
                },
            }],
        }
        session.card_rules["m-1"]["power"] = 2
        blossom = {
            "id": "blossom", "ownerId": "p1", "cardId": "blossom",
            "faceUp": True, "fieldZone": "interzone", "counters": {},
        }
        entering = {
            "id": "entering", "ownerId": "p1", "cardId": "m-0",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        target = {
            "id": "target", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield = [blossom, entering, target]

        triggers = session.queue_rules_manifestation_entry_watchers(entering)
        self.assertEqual(len(triggers), 1)
        session.pass_rules_priority("p2")
        self.assertIsNone(session.pass_rules_priority("p1")[0])
        self.assertEqual(blossom["counters"]["Petal"], 1)

        blossom["counters"]["Petal"] = 3
        p1["zones"]["hand"] = ["m-1"]
        p1["zoneOwners"]["hand"] = {"m-1": "p1"}
        session.rules_engine["priorityPlayerId"] = "p1"
        error, action = session.declare_rules_action(
            "p1", "Spend petals", kind="activated_effect",
            source={
                "cardId": "blossom", "zone": "battlefield",
                "itemId": "blossom",
            },
            targets=[{
                "kind": "card", "itemId": "target", "cardId": "m-2",
            }],
            payment_card_ids=["m-1"], ability_id="spend-petals",
        )
        self.assertIsNone(error)
        self.assertEqual(action["cost"]["removedCounters"], [{
            "name": "Petal", "amount": 3,
        }])
        self.assertNotIn("Petal", blossom["counters"])
        session.pass_rules_priority("p2")
        error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error)
        self.assertEqual(
            resolution["action"]["ongoingEffects"][0]["value"], 3
        )
        self.assertEqual(
            session.rules_manifestation_characteristics(target)["power"], 4
        )

    def test_global_confrontation_modifier_does_not_touch_interzone(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
        session.card_rules["will-ephemeral"]["playedAbilities"] = [{
            "id": "corrode",
            "action": "play_card",
            "targets": {"min": 0, "max": 0},
            "ongoingEffect": {
                "kind": "power_modifier", "value": -1,
                "duration": "until_end_of_turn",
                "scope": "all_manifestations_in_confrontation",
            },
        }]
        session.card_rules["m-0"]["power"] = 2
        session.card_rules["m-2"]["power"] = 2
        confrontation = {
            "id": "fight", "ownerId": "p2", "cardId": "m-0",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        interzone = {
            "id": "reserve", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "interzone", "counters": {},
        }
        session.battlefield = [confrontation, interzone]
        p1["zones"]["hand"] = ["will-ephemeral", "m-1"]
        p1["zoneOwners"]["hand"] = {
            "will-ephemeral": "p1", "m-1": "p1",
        }
        error, _action = session.declare_rules_action(
            "p1", "Corrode", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            payment_card_ids=["m-1"], ability_id="corrode",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        self.assertIsNone(session.pass_rules_priority("p1")[0])
        self.assertEqual(
            session.rules_manifestation_characteristics(confrontation)["power"], 1
        )
        self.assertEqual(
            session.rules_manifestation_characteristics(interzone)["power"], 2
        )

    def test_alternate_tribute_temperaments_pay_matching_and_split_costs(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["will-ephemeral"]["powerCost"] = "{B}{B}"
        session.card_rules["m-0"].update({
            "power": 2,
            "temperaments": ["choleric"],
            "tributeTemperaments": ["choleric", "vitreous"],
        })
        p1["zones"]["hand"] = ["will-ephemeral", "m-0"]
        p1["zoneOwners"]["hand"] = {
            "will-ephemeral": "p1", "m-0": "p1",
        }
        error, action = session.declare_rules_action(
            "p1", "Alternate color", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            payment_card_ids=["m-0"],
        )
        self.assertIsNone(error)
        self.assertIsNotNone(action)

        session.reset_phase_tracker()
        session.rules_engine["priorityPlayerId"] = "p1"
        session.card_rules["will-ephemeral"]["powerCost"] = "{B}{G}"
        session.card_rules["m-1"].update({
            "power": 2,
            "temperaments": ["hollow"],
            "tributeTemperaments": ["hollow", "transcendent"],
        })
        p1["zones"]["hand"] = ["will-ephemeral", "m-1"]
        p1["zoneOwners"]["hand"] = {
            "will-ephemeral": "p1", "m-1": "p1",
        }
        error, action = session.declare_rules_action(
            "p1", "Transcendent tribute", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            payment_card_ids=["m-1"],
        )
        self.assertIsNone(error)
        self.assertIsNotNone(action)

    def test_rematch_preserves_first_manifestations_and_restarts_reaction(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index("resolution_effects")
        session.rules_engine["priorityPlayerId"] = "p1"
        session.card_rules["rematch"] = {
            "type": "ephemeral_will", "powerCost": "{R}{R}",
            "playedAbilities": [{
                "id": "rematch",
                "action": "play_card",
                "condition": "controller_lost_confrontation",
                "targets": {"min": 0, "max": 0},
                "result": {"kind": "schedule_rematch"},
            }],
        }
        session.card_rules["m-3"].update({
            "power": 2, "temperaments": ["choleric"],
        })
        first_p1 = {
            "id": "first-p1", "ownerId": "p1", "cardId": "m-0",
            "faceUp": True, "fieldZone": "confrontation",
            "confrontationOrder": 1, "counters": {},
        }
        first_p2 = {
            "id": "first-p2", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation",
            "confrontationOrder": 2, "counters": {},
        }
        session.battlefield = [first_p1, first_p2]
        session.rules_engine["firstManifestationItemIds"] = {
            "p1": "first-p1", "p2": "first-p2",
        }
        session.rules_engine["firstManifestationComplete"] = True
        session.rules_engine["confrontationResult"] = {
            "turn": 1, "status": "effects",
            "winnerId": "p2", "loserId": "p1", "stalemate": False,
            "participantItemIds": ["first-p1", "first-p2"],
            "captured": [], "returned": [],
        }
        p1["zones"]["hand"] = ["rematch", "m-3"]
        p1["zoneOwners"]["hand"] = {"rematch": "p1", "m-3": "p1"}

        error, _action = session.declare_rules_action(
            "p1", "Rematch", kind="play_card",
            source={"cardId": "rematch", "zone": "hand"},
            payment_card_ids=["m-3"], ability_id="rematch",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        self.assertIsNone(session.pass_rules_priority("p1")[0])
        self.assertIsNotNone(session.rules_engine["rematchPending"])

        session.rules_engine["priorityPlayerId"] = "p1"
        session.pass_rules_priority("p1")
        error, move_phase = session.pass_rules_priority("p2")
        self.assertIsNone(error)
        self.assertEqual(move_phase["phaseId"], "resolution_move")
        self.assertEqual(move_phase["confrontationResult"]["status"], "complete")
        session.rules_engine["priorityPlayerId"] = "p1"
        session.pass_rules_priority("p1")
        error, restarted = session.pass_rules_priority("p2")

        self.assertIsNone(error)
        self.assertTrue(restarted["rematchStarted"])
        self.assertEqual(restarted["phaseId"], "confrontation_reaction")
        self.assertEqual(self.session_turn(session), 1)
        self.assertIsNotNone(session.find_battlefield_item("first-p1"))
        self.assertIsNotNone(session.find_battlefield_item("first-p2"))

    @staticmethod
    def session_turn(session):
        return session.phase_tracker["turn"]

    def test_bob_thresholds_suspend_release_protect_hands_and_exile(self):
        session, p1, p2 = self.make_session()
        session.card_rules["bob"] = {
            "type": "manifestation", "power": 2,
            "temperaments": ["hollow"], "persist": True,
            "suspensionThresholds": {
                "deck": 2, "graveyard": 5,
                "handImmunity": 8, "exile": 11,
            },
            "triggeredAbilities": [{
                "id": "bob-grow",
                "trigger": {
                    "event": "beginning_of_turn",
                    "zone": "confrontation",
                },
                "result": {
                    "kind": "add_counter_source",
                    "counter": "power", "value": 3,
                },
            }],
        }
        bob = {
            "id": "bob", "ownerId": "p1", "cardId": "bob",
            "faceUp": True, "fieldZone": "confrontation",
            "confrontationOrder": 1, "counters": {},
        }
        session.battlefield = [bob]
        p1["zones"]["deck"] = ["m-0"]
        p1["zoneOwners"]["deck"] = {"m-0": "p1"}

        triggers = session.queue_rules_beginning_turn_triggers()
        self.assertEqual(len(triggers), 1)
        session.pass_rules_priority("p2")
        self.assertIsNone(session.pass_rules_priority("p1")[0])
        self.assertEqual(session.rules_manifestation_characteristics(bob)["power"], 5)

        error, _owner_id, replacement = session.move_zone_card_by_effect(
            "p1", "deck", "p1", "hand", "m-0", "top"
        )
        self.assertIsNone(error)
        self.assertEqual(replacement["status"], "suspended")
        self.assertEqual(p1["zones"]["deck"], [])
        self.assertEqual(len(session.rules_engine["suspendedCards"]), 1)

        bob["counters"]["power"] = 6
        p2["zones"]["hand"] = ["m-1"]
        p2["zoneOwners"]["hand"] = {"m-1": "p2"}
        prevented = session.apply_rules_action_result({
            "controllerId": "p1",
            "targets": [{"kind": "player", "playerId": "p2"}],
            "ability": {
                "result": {"kind": "discard_hand_target", "value": 1},
            },
        })
        self.assertEqual(prevented["status"], "prevented_immunity")
        self.assertEqual(p2["zones"]["hand"], ["m-1"])

        bob["counters"]["power"] = 9
        state_actions = session.resolve_rules_state_actions({"bob": 8})
        self.assertEqual(
            state_actions["thresholdExiled"][0]["itemId"], "bob"
        )
        self.assertIn("bob", p1["zones"]["exile"])
        self.assertIn("m-0", p1["zones"]["exile"])
        self.assertEqual(session.rules_engine["suspendedCards"], [])

    def test_life_sustainer_replaces_exact_zero_with_permanent_effect_loss(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["life"] = {
            "type": "persistent_will",
            "passiveEffects": [{"kind": "sustain_exact_zero"}],
        }
        session.card_rules["m-0"].update({
            "power": 1,
            "persist": True,
            "activatedAbilities": [{
                "id": "test-effect",
                "targets": {"min": 0, "max": 0},
            }],
            "triggeredAbilities": [{
                "id": "test-trigger",
                "trigger": {"event": "beginning_of_turn"},
                "result": {"kind": "score_owner", "value": 1},
            }],
        })
        life = {
            "id": "life", "ownerId": "p1", "cardId": "life",
            "faceUp": True, "fieldZone": "field", "counters": {},
        }
        target = {
            "id": "target", "ownerId": "p2", "cardId": "m-0",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield = [life, target]
        session.rules_engine["ongoingEffects"] = [{
            "id": "loss", "kind": "power_modifier", "value": -1,
            "duration": "until_end_of_turn", "startedTurn": 1,
            "source": {"itemId": "life"},
            "target": {"itemId": "target"},
        }]

        state = session.resolve_rules_state_actions({"target": 1})

        self.assertEqual(state["destroyed"], [])
        self.assertEqual(state["replacements"][0]["status"], "sustained")
        self.assertTrue(target["effectsDisabled"])
        self.assertTrue(target["zeroPowerSustained"])
        self.assertFalse(session.rules_item_has_persist(target))
        self.assertEqual(
            session.queue_rules_beginning_turn_triggers(), []
        )

        session._rules_remove_field_item(life, "p1", "graveyard", "top")
        state = session.resolve_rules_state_actions({"target": 0})
        self.assertEqual(state["destroyed"][0]["itemId"], "target")
        self.assertIn("m-0", session.players["p2"]["zones"]["graveyard"])

    def test_greed_trap_captures_opponent_at_exact_zero_before_life_sustains(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["life"] = {
            "type": "persistent_will",
            "passiveEffects": [{"kind": "sustain_exact_zero"}],
        }
        session.card_rules["greed"] = {
            "type": "persistent_will",
            "passiveEffects": [{"kind": "capture_opponent_exact_zero"}],
        }
        session.card_rules["m-0"]["power"] = 1
        life = {
            "id": "life", "ownerId": "p2", "cardId": "life",
            "faceUp": True, "fieldZone": "field", "counters": {},
        }
        greed = {
            "id": "greed", "ownerId": "p1", "cardId": "greed",
            "faceUp": True, "fieldZone": "field", "counters": {},
        }
        target = {
            "id": "target", "ownerId": "p2", "cardId": "m-0",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield = [life, greed, target]
        session.rules_engine["ongoingEffects"] = [{
            "id": "loss", "kind": "power_modifier", "value": -1,
            "duration": "until_end_of_turn", "startedTurn": 1,
            "source": {"itemId": "greed"},
            "target": {"itemId": "target"},
        }]

        state = session.resolve_rules_state_actions({"target": 1})

        self.assertEqual(state["destroyed"], [])
        self.assertEqual(
            state["replacements"][0]["replacement"],
            "capture_opponent_exact_zero",
        )
        self.assertEqual(session.players["p1"]["zones"]["receptacle"], ["m-0"])
        self.assertEqual(
            session.card_owner_in_zone("p1", "receptacle", "m-0"), "p2"
        )

    def test_berta_clamps_other_manifestations_to_base_power(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["berta"] = {
            "type": "manifestation", "power": 3,
            "adamant": True,
            "passiveEffects": [{"kind": "other_power_minimum_base"}],
        }
        session.card_rules["m-0"]["power"] = 2
        berta = {
            "id": "berta", "ownerId": "p1", "cardId": "berta",
            "faceUp": True, "fieldZone": "interzone", "counters": {},
        }
        target = {
            "id": "target", "ownerId": "p2", "cardId": "m-0",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield = [berta, target]
        session.rules_engine["ongoingEffects"] = [{
            "id": "loss", "kind": "power_modifier", "value": -5,
            "duration": "until_end_of_turn", "startedTurn": 1,
            "source": {"itemId": "berta"},
            "target": {"itemId": "target"},
        }]

        self.assertEqual(
            session.rules_manifestation_characteristics(target)["power"], 2
        )
        self.assertEqual(
            session.resolve_rules_state_actions({"target": 2})["destroyed"], []
        )

    def test_controlled_manifestation_counts_for_controller_but_keeps_owner(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["m-0"]["power"] = 4
        controlled = {
            "id": "controlled", "ownerId": "p1", "controllerId": "p2",
            "cardId": "m-0", "faceUp": True,
            "fieldZone": "confrontation", "counters": {},
            "x": 0, "y": 0, "rotation": 0,
        }
        own = {
            "id": "own", "ownerId": "p1", "cardId": "m-1",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
            "x": 10, "y": 10, "rotation": 0,
        }
        session.battlefield = [controlled, own]

        self.assertEqual(
            [item["id"] for item in session.rules_confrontation_items("p2")],
            ["controlled"],
        )
        self.assertEqual(
            [item["id"] for item in session.rules_confrontation_items_owned_by("p1")],
            ["controlled", "own"],
        )
        view = session.serialize_for("p1", "player")
        serialized = next(
            item for item in view["battlefield"] if item["id"] == "controlled"
        )
        self.assertEqual(serialized["ownerId"], "p1")
        self.assertEqual(serialized["controllerId"], "p2")

    def test_hot_potato_enters_under_target_opponent_control(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index("end_actions")
        session.card_rules["hot-potato"] = {
            "type": "persistent_will",
            "powerCost": "{Y}{Y}",
            "playedAbilities": [{
                "id": "give-control",
                "action": "play_card",
                "targets": {
                    "kind": "player", "min": 1, "max": 1,
                    "controller": "opponent",
                },
                "result": {
                    "kind": "change_source_control",
                    "counter": "Burn", "counterValue": 1,
                },
            }],
        }
        session.card_rules["m-0"].update({
            "power": 2, "temperaments": ["capricious"],
        })
        p1["zones"]["hand"] = ["hot-potato", "m-0"]
        p1["zoneOwners"]["hand"] = {
            "hot-potato": "p1", "m-0": "p1",
        }

        error, action = session.declare_rules_action(
            "p1", "Hot Potato", kind="play_card",
            source={"cardId": "hot-potato", "zone": "hand"},
            targets=[{"kind": "player", "playerId": "p2"}],
            payment_card_ids=["m-0"], ability_id="give-control",
            placement={"x": 700, "y": 500},
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error)
        item_id = resolution["action"]["sourceResolution"]["itemId"]
        hot_potato = session.find_battlefield_item(item_id)

        self.assertEqual(hot_potato["ownerId"], "p1")
        self.assertEqual(hot_potato["controllerId"], "p2")
        self.assertEqual(hot_potato["counters"]["Burn"], 1)
        self.assertEqual(
            resolution["action"]["effectResult"]["previousControllerId"], "p1"
        )
        movement = session._rules_remove_field_item(
            hot_potato, "p1", "graveyard", "top"
        )
        self.assertEqual(movement["ownerId"], "p1")
        self.assertIn("hot-potato", p1["zones"]["graveyard"])

    def test_hot_potato_dynamic_transfer_and_end_trigger_use_current_controller(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index("end_actions")
        session.card_rules["hot"] = {
            "type": "persistent_will",
            "activatedAbilities": [{
                "id": "pass-hot",
                "tributeFromSourceCounter": "Burn",
                "targets": {
                    "kind": "player", "min": 1, "max": 1,
                    "controller": "opponent",
                },
                "result": {
                    "kind": "change_source_control",
                    "counter": "Burn", "counterValue": 1,
                    "incrementCounter": True,
                },
            }],
            "triggeredAbilities": [{
                "id": "burn-controller",
                "trigger": {"event": "end_of_turn", "zone": "field"},
                "result": {
                    "kind": "score_controller_then_destroy_source",
                    "value": -40,
                },
            }],
        }
        session.card_rules["m-0"]["power"] = 1
        hot = {
            "id": "hot", "ownerId": "p1", "controllerId": "p2",
            "cardId": "hot", "faceUp": True, "fieldZone": "field",
            "counters": {"Burn": 1},
        }
        session.battlefield = [hot]
        p2["zones"]["hand"] = ["m-0"]
        p2["zoneOwners"]["hand"] = {"m-0": "p2"}
        session.rules_engine["priorityPlayerId"] = "p2"

        error, action = session.declare_rules_action(
            "p2", "Pass Hot Potato", kind="activated_effect",
            source={"cardId": "hot", "zone": "battlefield", "itemId": "hot"},
            targets=[{"kind": "player", "playerId": "p1"}],
            payment_card_ids=["m-0"], ability_id="pass-hot",
        )
        self.assertIsNone(error)
        self.assertEqual(action["cost"]["tributeRequirements"], {"hollow": 1})
        session.pass_rules_priority("p1")
        self.assertIsNone(session.pass_rules_priority("p2")[0])
        self.assertEqual(session.rules_item_controller_id(hot), "p1")
        self.assertEqual(hot["counters"]["Burn"], 2)

        session.phase_tracker["index"] = ADVANCED_PHASES.index("end_actions")
        session.rules_engine["priorityPlayerId"] = "p1"
        session.pass_rules_priority("p1")
        error, advanced = session.pass_rules_priority("p2")
        self.assertIsNone(error)
        self.assertEqual(len(advanced["endTriggeredActions"]), 1)
        session.pass_rules_priority("p2")
        error, resolution = session.pass_rules_priority("p1")

        self.assertIsNone(error)
        self.assertEqual(
            resolution["action"]["effectResult"]["playerId"], "p1"
        )
        self.assertEqual(p1["score"], -40)
        self.assertIn("hot", p1["zones"]["graveyard"])
        self.assertIsNone(session.find_battlefield_item("hot"))

    def test_thought_saboteur_control_link_starts_from_interzone_choice(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["thought"] = {
            "type": "manifestation", "power": 4,
            "triggeredAbilities": [{
                "id": "thought-control",
                "trigger": {
                    "event": "enters_field_zone", "zone": "interzone",
                },
                "targets": {
                    "min": 1, "max": 1,
                    "cardTypes": ["manifestation", "persistent_will"],
                    "zones": ["battlefield"],
                    "controller": "opponent",
                    "fieldZonesByType": {
                        "manifestation": ["interzone"],
                        "persistent_will": ["field"],
                    },
                },
                "ongoingEffect": {
                    "kind": "control_link",
                    "duration": "while_source_and_target_on_field",
                },
            }],
        }
        thought = {
            "id": "thought", "ownerId": "p1", "cardId": "thought",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        target = {
            "id": "target", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "interzone", "counters": {},
        }
        session.battlefield = [thought, target]
        session.rules_engine["confrontationResult"] = {
            "winnerId": "p1", "pendingOwnItemIds": ["thought"],
            "status": "cleanup", "returned": [],
        }
        session.rules_engine["pendingChoice"] = {
            "id": "destination", "kind": "confrontation_destination",
            "playerId": "p1", "itemId": "thought", "cardId": "thought",
            "options": ["interzone", "deck_bottom"],
        }

        error, destination = session.resolve_rules_choice(
            "p1", "destination", option="interzone"
        )
        self.assertIsNone(error)
        self.assertEqual(destination["destination"], "interzone")
        target_choice = session.rules_engine["pendingChoice"]
        self.assertEqual(target_choice["kind"], "trigger_targets")
        error, selected = session.resolve_rules_choice(
            "p1", target_choice["id"],
            targets=[{
                "kind": "card", "itemId": "target", "cardId": "m-2",
            }],
        )
        self.assertIsNone(error)
        self.assertEqual(selected["kind"], "trigger_targets")
        session.pass_rules_priority("p2")
        self.assertIsNone(session.pass_rules_priority("p1")[0])
        self.assertEqual(session.rules_item_controller_id(target), "p1")

        session._rules_remove_field_item(
            thought, "p1", "graveyard", "top"
        )
        session.prune_rules_ongoing_effects()
        self.assertEqual(session.rules_item_controller_id(target), "p2")

    def test_invert_emotions_exchanges_asymmetric_interzone_targets(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
        session.card_rules["invert"] = {
            "type": "ephemeral_will", "powerCost": "{Y}{Y}{Y}",
            "playedAbilities": [{
                "id": "invert",
                "action": "play_card",
                "targetGroups": [
                    {
                        "min": 1, "max": 1,
                        "cardType": "manifestation",
                        "zones": ["battlefield"],
                        "fieldZone": "interzone",
                        "controller": "opponent",
                    },
                    {
                        "min": 1, "max": 1,
                        "cardType": "manifestation",
                        "zones": ["battlefield"],
                        "fieldZone": "interzone",
                        "controller": "self",
                    },
                ],
                "result": {"kind": "exchange_control_targets"},
            }],
        }
        session.card_rules["m-0"].update({
            "power": 3, "temperaments": ["capricious"],
        })
        mine = {
            "id": "mine", "ownerId": "p1", "cardId": "m-1",
            "faceUp": True, "fieldZone": "interzone", "counters": {},
        }
        theirs = {
            "id": "theirs", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "interzone", "counters": {},
        }
        session.battlefield = [mine, theirs]
        p1["zones"]["hand"] = ["invert", "m-0"]
        p1["zoneOwners"]["hand"] = {"invert": "p1", "m-0": "p1"}

        error, _action = session.declare_rules_action(
            "p1", "Invert", kind="play_card",
            source={"cardId": "invert", "zone": "hand"},
            targets=[
                {"kind": "card", "itemId": "theirs", "cardId": "m-2"},
                {"kind": "card", "itemId": "mine", "cardId": "m-1"},
            ],
            payment_card_ids=["m-0"], ability_id="invert",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        self.assertIsNone(session.pass_rules_priority("p1")[0])
        self.assertEqual(session.rules_item_controller_id(mine), "p2")
        self.assertEqual(session.rules_item_controller_id(theirs), "p1")

    def test_dominate_aspects_moves_exchanged_cards_to_owner_decks_at_resolution(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
        session.card_rules["dominate"] = {
            "type": "ephemeral_will", "powerCost": "{B}{B}{B}",
            "playedAbilities": [{
                "id": "dominate",
                "action": "play_card",
                "targetGroups": [
                    {
                        "min": 1, "max": 1, "cardType": "manifestation",
                        "zones": ["battlefield"],
                        "fieldZone": "confrontation", "controller": "self",
                    },
                    {
                        "min": 1, "max": 1, "cardType": "manifestation",
                        "zones": ["battlefield"],
                        "fieldZone": "confrontation", "controller": "opponent",
                    },
                ],
                "result": {
                    "kind": "exchange_control_targets",
                    "rememberAtResolution": True,
                },
            }],
        }
        session.card_rules["m-0"].update({
            "power": 3, "temperaments": ["vitreous"],
        })
        mine = {
            "id": "mine", "ownerId": "p1", "cardId": "m-1",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        theirs = {
            "id": "theirs", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield = [mine, theirs]
        p1["zones"]["hand"] = ["dominate", "m-0"]
        p1["zoneOwners"]["hand"] = {"dominate": "p1", "m-0": "p1"}
        error, _action = session.declare_rules_action(
            "p1", "Dominate", kind="play_card",
            source={"cardId": "dominate", "zone": "hand"},
            targets=[
                {"kind": "card", "itemId": "mine", "cardId": "m-1"},
                {"kind": "card", "itemId": "theirs", "cardId": "m-2"},
            ],
            payment_card_ids=["m-0"], ability_id="dominate",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        self.assertIsNone(session.pass_rules_priority("p1")[0])
        self.assertEqual(len(session.rules_engine["effectMemories"]), 2)

        actions = session.queue_rules_resolution_memory_triggers()
        order_choice = session.rules_engine["pendingChoice"]
        if order_choice:
            self.assertIsNone(session.resolve_rules_choice(
                "p1", order_choice["id"],
                [action["id"] for action in actions],
            )[0])
        while session.rules_engine["actionStack"]:
            session.resolve_rules_top_action()

        self.assertIsNone(session.find_battlefield_item("mine"))
        self.assertIsNone(session.find_battlefield_item("theirs"))
        self.assertEqual(p1["zones"]["deck"], ["m-1"])
        self.assertEqual(session.players["p2"]["zones"]["deck"], ["m-2"])

    def test_lose_effects_and_obscure_disable_actions_and_confrontation_power(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
        session.card_rules["obscure"] = {
            "type": "ephemeral_will", "powerCost": "{B}",
            "playedAbilities": [{
                "id": "obscure",
                "action": "play_card",
                "resolveSourceTo": "exile",
                "targets": {
                    "min": 1, "max": 1,
                    "cardType": "manifestation",
                },
                "ongoingEffect": {
                    "kind": "obscure_lock",
                    "duration": "until_end_of_turn",
                },
            }],
        }
        session.card_rules["m-0"].update({
            "power": 1, "temperaments": ["vitreous"],
        })
        session.card_rules["m-2"].update({
            "power": 4,
            "persist": True,
            "activatedAbilities": [{
                "id": "target-effect",
                "targets": {"min": 0, "max": 0},
            }],
        })
        target = {
            "id": "target", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield = [target]
        p1["zones"]["hand"] = ["obscure", "m-0"]
        p1["zoneOwners"]["hand"] = {"obscure": "p1", "m-0": "p1"}
        error, _action = session.declare_rules_action(
            "p1", "Obscure", kind="play_card",
            source={"cardId": "obscure", "zone": "hand"},
            targets=[{"kind": "card", "itemId": "target", "cardId": "m-2"}],
            payment_card_ids=["m-0"], ability_id="obscure",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        resolution = session.pass_rules_priority("p1")[1]

        self.assertIn("obscure", p1["zones"]["exile"])
        self.assertFalse(session.rules_item_effects_active(target))
        self.assertFalse(session.rules_item_has_persist(target))
        self.assertEqual(session.rules_confrontation_power(target), 0)
        self.assertEqual(
            resolution["action"]["ongoingEffects"][0]["kind"], "obscure_lock"
        )

    def test_source_bound_effect_can_retarget_and_vexing_reduce_is_paid(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index("end_actions")
        session.card_rules["nectar"] = {
            "type": "persistent_will", "powerCost": "{Y}",
            "playedAbilities": [{
                "id": "disable",
                "action": "play_card",
                "targets": {"min": 1, "max": 1, "cardType": "manifestation"},
                "ongoingEffect": {
                    "kind": "lose_effects",
                    "duration": "while_source_and_target_on_field",
                },
            }],
            "activatedAbilities": [{
                "id": "retarget",
                "tribute": "{Y}",
                "exhaustSource": True,
                "targets": {"min": 1, "max": 1, "cardType": "manifestation"},
                "result": {
                    "kind": "retarget_source_effect",
                    "effectKind": "lose_effects",
                },
            }],
        }
        session.card_rules["thorn"] = {
            "type": "manifestation", "power": 5,
            "activatedAbilities": [{
                "id": "thorn-disable",
                "sourceFieldZone": "interzone",
                "reduceSourcePower": 2,
                "targets": {"min": 1, "max": 1, "cardType": "manifestation"},
                "ongoingEffect": {
                    "kind": "lose_effects",
                    "duration": "while_target_on_field",
                },
            }],
        }
        session.card_rules["m-0"].update({
            "power": 1, "temperaments": ["capricious"],
        })
        first = {
            "id": "first", "ownerId": "p2", "cardId": "m-1",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        second = {
            "id": "second", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        thorn = {
            "id": "thorn", "ownerId": "p1", "cardId": "thorn",
            "faceUp": True, "fieldZone": "interzone", "counters": {},
        }
        session.battlefield = [first, second, thorn]
        p1["zones"]["hand"] = ["nectar", "m-0"]
        p1["zoneOwners"]["hand"] = {"nectar": "p1", "m-0": "p1"}
        error, _action = session.declare_rules_action(
            "p1", "Nectar", kind="play_card",
            source={"cardId": "nectar", "zone": "hand"},
            targets=[{"kind": "card", "itemId": "first", "cardId": "m-1"}],
            payment_card_ids=["m-0"], ability_id="disable",
            placement={"x": 700, "y": 500},
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        played = session.pass_rules_priority("p1")[1]
        source_item_id = played["action"]["sourceResolution"]["itemId"]
        self.assertFalse(session.rules_item_effects_active(first))

        session.rules_engine["priorityPlayerId"] = "p1"
        p1["zones"]["hand"] = ["m-0"]
        p1["zoneOwners"]["hand"] = {"m-0": "p1"}
        error, _action = session.declare_rules_action(
            "p1", "Retarget", kind="activated_effect",
            source={"cardId": "nectar", "zone": "battlefield", "itemId": source_item_id},
            targets=[{"kind": "card", "itemId": "second", "cardId": "m-2"}],
            payment_card_ids=["m-0"], ability_id="retarget",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        self.assertIsNone(session.pass_rules_priority("p1")[0])
        self.assertTrue(session.rules_item_effects_active(first))
        self.assertFalse(session.rules_item_effects_active(second))

        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
        session.rules_engine["priorityPlayerId"] = "p1"
        error, action = session.declare_rules_action(
            "p1", "Thorn", kind="activated_effect",
            source={"cardId": "thorn", "zone": "battlefield", "itemId": "thorn"},
            targets=[{"kind": "card", "itemId": "first", "cardId": "m-1"}],
            ability_id="thorn-disable",
        )
        self.assertIsNone(error)
        self.assertEqual(action["cost"]["reducedSourcePower"], 2)
        self.assertEqual(
            session.rules_manifestation_characteristics(thorn)["power"], 3
        )

    def test_starkaz_and_mirrorbeast_use_scope_and_resolution_duration(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["starkaz"] = {
            "type": "manifestation", "power": 5,
            "triggeredAbilities": [{
                "id": "starkaz",
                "trigger": {"event": "enters_field_zone", "zone": "confrontation"},
                "targets": {"min": 0, "max": 0},
                "ongoingEffect": {
                    "kind": "lose_effects",
                    "duration": "until_end_of_turn",
                    "scope": "all_manifestations_on_field",
                    "excludeSource": True,
                },
            }],
        }
        session.card_rules["mirror"] = {
            "type": "manifestation", "power": 1,
            "triggeredAbilities": [{
                "id": "mirror",
                "trigger": {"event": "enters_field_zone", "zone": "confrontation"},
                "targets": {
                    "min": 1, "max": 1, "cardType": "manifestation",
                    "fieldZone": "confrontation",
                    "excludeEventSource": True,
                },
                "ongoingEffect": {
                    "kind": "copy_power_effects",
                    "duration": "until_resolution",
                },
            }],
        }
        starkaz = {
            "id": "starkaz", "ownerId": "p1", "cardId": "starkaz",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        mirror = {
            "id": "mirror", "ownerId": "p1", "cardId": "mirror",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        target = {
            "id": "target", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.card_rules["m-2"]["power"] = 4
        session.battlefield = [starkaz, mirror, target]
        starkaz_actions = session.queue_rules_field_zone_entry_triggers(
            starkaz, "confrontation"
        )
        self.assertEqual(len(starkaz_actions), 1)
        session.pass_rules_priority("p2")
        self.assertIsNone(session.pass_rules_priority("p1")[0])
        self.assertTrue(session.rules_item_effects_active(starkaz))
        self.assertFalse(session.rules_item_effects_active(mirror))
        self.assertFalse(session.rules_item_effects_active(target))

        session.rules_engine["ongoingEffects"] = []
        mirror_actions = session.queue_rules_triggers(
            "mirror", "p1", "enters_field_zone",
            zone="confrontation", item_id="mirror",
            event_item_id="mirror",
            event_targets=[{
                "kind": "card", "itemId": "target", "cardId": "m-2",
            }],
        )
        self.assertEqual(len(mirror_actions), 1)
        session.pass_rules_priority("p2")
        self.assertIsNone(session.pass_rules_priority("p1")[0])
        self.assertEqual(
            session.rules_manifestation_characteristics(mirror)["power"], 4
        )
        session.phase_tracker["index"] = ADVANCED_PHASES.index("end_actions")
        session.prune_rules_ongoing_effects()
        self.assertEqual(
            session.rules_manifestation_characteristics(mirror)["power"], 1
        )

    def test_passive_protection_and_hand_immunity_block_opponents_only(self):
        session, _p1, p2 = self.make_session()
        session.card_rules["sanctuary"] = {
            "type": "manifestation",
            "passiveEffects": [{
                "kind": "protect_other_friendly_confrontation",
            }],
        }
        session.card_rules["ritual"] = {
            "type": "persistent_will",
            "passiveEffects": [{"kind": "protect_controller_hand"}],
        }
        sanctuary = {
            "id": "sanctuary", "ownerId": "p1", "cardId": "sanctuary",
            "faceUp": True, "fieldZone": "interzone", "counters": {},
        }
        ritual = {
            "id": "ritual", "ownerId": "p1", "cardId": "ritual",
            "faceUp": True, "fieldZone": "field", "counters": {},
        }
        target = {
            "id": "target", "ownerId": "p1", "cardId": "m-1",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield = [sanctuary, ritual, target]
        error = session.rules_ability_targets_error(
            {"min": 1, "max": 1, "cardType": "manifestation"},
            [{"kind": "card", "itemId": "target", "cardId": "m-1"}],
            "p2",
        )
        self.assertIn("Protected", error)
        self.assertIsNone(session.rules_ability_targets_error(
            {"min": 1, "max": 1, "cardType": "manifestation"},
            [{"kind": "card", "itemId": "target", "cardId": "m-1"}],
            "p1",
        ))

        p2["zones"]["hand"] = ["m-2"]
        p2["zoneOwners"]["hand"] = {"m-2": "p2"}
        prevented = session.apply_rules_action_result({
            "controllerId": "p1",
            "targets": [{"kind": "player", "playerId": "p2"}],
            "ability": {
                "result": {"kind": "discard_hand_target", "value": 1},
            },
        })
        self.assertNotEqual(prevented.get("status"), "prevented_immunity")
        session.players["p1"]["zones"]["hand"] = ["m-0"]
        session.players["p1"]["zoneOwners"]["hand"] = {"m-0": "p1"}
        prevented = session.apply_rules_action_result({
            "controllerId": "p2",
            "targets": [{"kind": "player", "playerId": "p1"}],
            "ability": {
                "result": {"kind": "discard_hand_target", "value": 1},
            },
        })
        self.assertEqual(prevented["status"], "prevented_immunity")

    def test_protect_will_creates_opponent_only_protection(self):
        session, _p1, _p2 = self.make_session()
        source = {
            "id": "source", "ownerId": "p1", "cardId": "m-0",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        target = {
            "id": "target", "ownerId": "p1", "cardId": "m-1",
            "faceUp": True, "fieldZone": "interzone", "counters": {},
        }
        session.battlefield = [source, target]
        action = {
            "id": "protect", "controllerId": "p1",
            "source": {"cardId": "protect"},
            "targets": [],
            "ability": {
                "id": "protect",
                "ongoingEffect": {
                    "kind": "protection",
                    "duration": "until_end_of_turn",
                    "scope": "friendly_cards_on_field",
                    "fromOpponents": True,
                },
            },
        }
        session.create_rules_ongoing_effects(action)
        self.assertTrue(session.rules_item_is_protected(target, "p2"))
        self.assertFalse(session.rules_item_is_protected(target, "p1"))

    def test_player_target_relation_rejects_self_for_opponent_effect(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["will-ephemeral"]["playedAbilities"] = [{
            "id": "opponent-only",
            "action": "play_card",
            "targets": {
                "kind": "player", "min": 1, "max": 1,
                "controller": "opponent",
            },
            "result": {"kind": "score_owner", "value": 1},
        }]
        p1["zones"]["hand"] = ["will-ephemeral", "m-0"]
        p1["zoneOwners"]["hand"] = {
            "will-ephemeral": "p1", "m-0": "p1",
        }

        error, action = session.declare_rules_action(
            "p1", "Invalid self target", kind="play_card",
            source={"cardId": "will-ephemeral", "zone": "hand"},
            targets=[{"kind": "player", "playerId": "p1"}],
            payment_card_ids=["m-0"], ability_id="opponent-only",
        )

        self.assertIn("opponent player", error)
        self.assertIsNone(action)

    def test_immediate_shuffle_resolves_without_priority_passes(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
        session.card_rules["pontificate"] = {
            "type": "ephemeral_will", "powerCost": "{Y}{Y}",
            "playedAbilities": [{
                "id": "shuffle-draw",
                "action": "play_card",
                "immediate": True,
                "targets": {"min": 0, "max": 0},
                "result": {
                    "kind": "shuffle_hands_then_draw", "value": 4,
                },
            }],
        }
        session.card_rules["m-0"].update({
            "power": 2, "temperaments": ["capricious"],
        })
        p1["zones"]["hand"] = ["pontificate", "m-0", "m-1"]
        p1["zoneOwners"]["hand"] = {
            card_id: "p1" for card_id in p1["zones"]["hand"]
        }
        p2["zones"]["hand"] = ["m-2"]
        p2["zoneOwners"]["hand"] = {"m-2": "p2"}
        self.fill_deck(p1, ["m-3", "m-4", "m-5", "m-6"])
        self.fill_deck(p2, ["m-7", "m-8", "m-9", "m-10"])

        error, action = session.declare_rules_action(
            "p1", "Pontificate", kind="play_card",
            source={"cardId": "pontificate", "zone": "hand"},
            payment_card_ids=["m-0"], ability_id="shuffle-draw",
        )
        self.assertIsNone(error)
        self.assertTrue(action["immediate"])
        resolutions = session.resolve_rules_immediate_actions()

        self.assertEqual(len(resolutions), 1)
        self.assertEqual(session.rules_engine["actionStack"], [])
        self.assertEqual(
            resolutions[0]["action"]["effectResult"]["kind"],
            "shuffle_hands_then_draw",
        )
        self.assertEqual(len(p1["zones"]["hand"]), 4)
        self.assertEqual(len(p2["zones"]["hand"]), 4)
        self.assertIn("pontificate", p1["zones"]["graveyard"])

    def test_immediate_limbo_exile_does_not_exile_its_own_source(self):
        session, p1, p2 = self.make_session()
        session.card_rules["extinguish"] = {
            "type": "ephemeral_will", "powerCost": "{R}{R}{R}{R}",
            "playedAbilities": [{
                "id": "exile-limbos",
                "action": "play_card",
                "immediate": True,
                "targets": {"min": 0, "max": 0},
                "result": {"kind": "exile_all_limbos"},
            }],
        }
        session.card_rules["m-0"].update({
            "power": 4, "temperaments": ["choleric"],
        })
        p1["zones"]["hand"] = ["extinguish", "m-0"]
        p1["zoneOwners"]["hand"] = {
            "extinguish": "p1", "m-0": "p1",
        }
        p1["zones"]["graveyard"] = ["m-1"]
        p1["zoneOwners"]["graveyard"] = {"m-1": "p1"}
        p2["zones"]["graveyard"] = ["m-2"]
        p2["zoneOwners"]["graveyard"] = {"m-2": "p2"}

        error, _action = session.declare_rules_action(
            "p1", "Extinguish", kind="play_card",
            source={"cardId": "extinguish", "zone": "hand"},
            payment_card_ids=["m-0"], ability_id="exile-limbos",
        )
        self.assertIsNone(error)
        resolution = session.resolve_rules_immediate_actions()[0]

        self.assertEqual(
            resolution["action"]["effectResult"]["kind"],
            "exile_all_limbos",
        )
        self.assertEqual(p1["zones"]["graveyard"], ["extinguish"])
        self.assertCountEqual(p1["zones"]["exile"], ["m-0", "m-1"])
        self.assertEqual(p2["zones"]["exile"], ["m-2"])

    def test_immediate_paid_action_resolves_above_tribute_trigger(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["immediate"] = {
            "type": "ephemeral_will", "powerCost": "{G}",
            "playedAbilities": [{
                "id": "immediate-draw",
                "action": "play_card",
                "immediate": True,
                "targets": {"min": 0, "max": 0},
                "result": {"kind": "draw_owner", "value": 1},
            }],
        }
        session.card_rules["m-1"]["triggeredAbilities"] = [{
            "id": "tribute-draw",
            "trigger": {"event": "used_as_tribute"},
            "result": {"kind": "draw_owner", "value": 1},
        }]
        p1["zones"]["hand"] = ["immediate", "m-1"]
        p1["zoneOwners"]["hand"] = {
            "immediate": "p1", "m-1": "p1",
        }
        self.fill_deck(p1, ["m-2", "m-3"])
        error, paid_action = session.declare_rules_action(
            "p1", "Immediate", kind="play_card",
            source={"cardId": "immediate", "zone": "hand"},
            payment_card_ids=["m-1"], ability_id="immediate-draw",
        )
        self.assertIsNone(error)
        triggers = session.queue_rules_tribute_triggers(
            ["m-1"], "p1",
            simultaneous_action_id=paid_action["id"],
            tribute_movements=paid_action["cost"]["tributeMovements"],
        )

        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertEqual(
            [action["id"] for action in session.rules_engine["actionStack"]],
            [triggers[0]["id"], paid_action["id"]],
        )
        immediate_resolution = session.resolve_rules_immediate_actions()
        self.assertEqual(len(immediate_resolution), 1)
        self.assertEqual(
            session.rules_engine["actionStack"][0]["id"], triggers[0]["id"]
        )

    def test_immediate_confrontation_end_waits_for_opponent_payment_choice(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
        session.card_rules["kiss"] = {
            "type": "ephemeral_will", "powerCost": "{R}{R}",
            "playedAbilities": [{
                "id": "kiss",
                "action": "play_card",
                "immediate": True,
                "targets": {"min": 0, "max": 0},
                "result": {
                    "kind": "end_confrontation_unless_payment",
                    "payment": "{H}{H}{H}",
                    "exileOnDecline": True,
                    "reduceWinnerManifestationOnControllerDefeat": True,
                },
            }],
        }
        session.card_rules["m-0"].update({
            "power": 2, "temperaments": ["choleric"],
        })
        session.card_rules["m-1"]["power"] = 1
        session.card_rules["m-2"]["power"] = 3
        session.battlefield = [
            {
                "id": "p1-first", "ownerId": "p1", "cardId": "m-1",
                "faceUp": True, "fieldZone": "confrontation",
                "confrontationOrder": 1, "counters": {},
            },
            {
                "id": "p2-first", "ownerId": "p2", "cardId": "m-2",
                "faceUp": True, "fieldZone": "confrontation",
                "confrontationOrder": 2, "counters": {},
            },
        ]
        p1["zones"]["hand"] = ["kiss", "m-0"]
        p1["zoneOwners"]["hand"] = {"kiss": "p1", "m-0": "p1"}
        error, _action = session.declare_rules_action(
            "p1", "Kiss", kind="play_card",
            source={"cardId": "kiss", "zone": "hand"},
            payment_card_ids=["m-0"], ability_id="kiss",
        )
        self.assertIsNone(error)
        resolution = session.resolve_rules_immediate_actions()[0]
        self.assertEqual(
            resolution["action"]["effectResult"]["choiceKind"],
            "immediate_effect_payment",
        )
        choice = session.rules_engine["pendingChoice"]
        error, declined = session.resolve_rules_choice(
            "p2", choice["id"], option="decline"
        )

        self.assertIsNone(error)
        self.assertEqual(declined["status"], "declined")
        self.assertEqual(session.current_phase_id(), "resolution_compare")
        self.assertIn("kiss", p1["zones"]["exile"])
        followup = session.rules_engine["pendingChoice"]
        self.assertEqual(followup["kind"], "trigger_targets")
        self.assertEqual(followup["playerId"], "p1")
        error, selected = session.resolve_rules_choice(
            "p1", followup["id"],
            targets=[{
                "kind": "card", "itemId": "p2-first",
                "cardId": "m-2",
            }],
        )
        self.assertIsNone(error)
        self.assertEqual(selected["kind"], "trigger_targets")
        immediate = session.resolve_rules_immediate_actions()[0]
        self.assertEqual(
            immediate["action"]["effectResult"]["value"], -1
        )
        self.assertEqual(
            session.rules_manifestation_characteristics(
                session.find_battlefield_item("p2-first")
            )["power"],
            2,
        )

    def test_top_deck_type_resolution_chains_manifestations_and_draws_wills(self):
        session, p1, _p2 = self.make_session()
        self.fill_deck(p1, ["m-1", "will-ephemeral"])
        action = {
            "id": "triad-action",
            "controllerId": "p1",
            "source": {"cardId": "triad"},
            "ability": {"result": {
                "kind": "resolve_top_deck_by_type",
                "manifestation": "chain",
                "will": "draw",
            }},
        }

        chained = session.apply_rules_action_result(action)

        self.assertEqual(chained["status"], "chained")
        self.assertTrue(session.find_battlefield_item(
            chained["resolution"]["itemId"]
        )["isChained"])
        drawn = session.apply_rules_action_result(action)
        self.assertEqual(drawn["status"], "drawn")
        self.assertIn("will-ephemeral", p1["zones"]["hand"])

    def test_deck_reorder_choice_is_private_and_server_authoritative(self):
        session, p1, p2 = self.make_session()
        self.fill_deck(p1, ["m-1", "m-2", "m-3", "m-4"])
        self.fill_deck(p2, ["m-5", "m-6", "m-7", "m-8"])
        action = {
            "id": "dissect-action",
            "controllerId": "p1",
            "source": {"cardId": "dissect"},
            "ability": {"result": {
                "kind": "reorder_top_decks", "count": 3,
                "eachPlayer": True,
            }},
        }

        required = session.apply_rules_action_result(action)
        choice = session.rules_engine["pendingChoice"]
        own_view = session.serialize_for("p1", "player")["rulesEngine"]["pendingChoice"]
        opponent_view = session.serialize_for("p2", "player")["rulesEngine"]["pendingChoice"]

        self.assertEqual(required["choiceKind"], "deck_reorder")
        self.assertIn("cardIds", own_view["groups"][0])
        self.assertNotIn("cardIds", opponent_view["groups"][0])
        error, resolved = session.resolve_rules_choice(
            "p1", choice["id"], option={"groups": [
                {"playerId": "p1", "top": ["m-2"], "bottom": ["m-3", "m-1"]},
                {"playerId": "p2", "top": ["m-7", "m-5"], "bottom": ["m-6"]},
            ]}
        )
        self.assertIsNone(error)
        self.assertEqual(resolved["kind"], "deck_reorder")
        self.assertEqual(p1["zones"]["deck"], ["m-2", "m-4", "m-3", "m-1"])
        self.assertEqual(p2["zones"]["deck"], ["m-7", "m-5", "m-8", "m-6"])

    def test_recent_limbo_split_enforces_turn_and_half_rounding(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["turn"] = 3
        for card_id in ("m-1", "m-2", "m-3"):
            session.put_zone_card("p1", "graveyard", card_id, "p1")
        session.rules_engine["zoneEntryTurns"]["p1:graveyard:m-3"] = 2
        target_rules = {
            "min": 0, "max": 4, "cardType": "manifestation",
            "zones": ["graveyard"], "enteredThisTurn": True,
        }
        current_targets = [
            {"kind": "zone_card", "containerId": "p1", "zone": "graveyard",
             "cardId": "m-1", "ownerId": "p1"},
            {"kind": "zone_card", "containerId": "p1", "zone": "graveyard",
             "cardId": "m-2", "ownerId": "p1"},
        ]
        stale_targets = current_targets + [{
            "kind": "zone_card", "containerId": "p1", "zone": "graveyard",
            "cardId": "m-3", "ownerId": "p1",
        }]
        self.assertIsNone(session.rules_ability_targets_error(
            target_rules, current_targets, "p1"
        ))
        self.assertIn("this turn", session.rules_ability_targets_error(
            target_rules, stale_targets, "p1"
        ))
        action = {
            "id": "caress-action",
            "controllerId": "p1",
            "source": {"cardId": "caress"},
            "targets": current_targets,
            "ability": {"result": {"kind": "split_targeted_limbo_cards"}},
        }
        session.apply_rules_action_result(action)
        choice = session.rules_engine["pendingChoice"]
        error, _resolved = session.resolve_rules_choice(
            "p1", choice["id"], option={"groups": [{
                "playerId": "p1", "top": ["m-2"], "bottom": ["m-1"],
            }]}
        )
        self.assertIsNone(error)
        self.assertEqual(p1["zones"]["deck"], ["m-2", "m-1"])
        self.assertEqual(p1["zones"]["graveyard"], ["m-3"])

    def test_hidden_top_card_guess_reveals_and_grants_one_use_free_will(self):
        session, p1, p2 = self.make_session()
        session.card_rules["m-5"].update({
            "power": 1, "temperaments": ["phlegmatic"],
        })
        self.fill_deck(p2, ["m-5"])
        self.fill_deck(p1, ["will-persistent"])
        action = {
            "id": "jodorosk-action",
            "controllerId": "p1",
            "source": {"cardId": "jodorosk"},
            "targets": [{"kind": "player", "playerId": "p2"}],
            "ability": {"result": {"kind": "guess_top_card"}},
        }
        session.apply_rules_action_result(action)
        choice = session.rules_engine["pendingChoice"]

        error, resolved = session.resolve_rules_choice(
            "p1", choice["id"], option={
                "type": "manifestation",
                "temperament": "phlegmatic",
                "value": 1,
            }
        )

        self.assertIsNone(error)
        self.assertEqual(resolved["correct"], 3)
        self.assertEqual(resolved["cardId"], "m-5")
        self.assertEqual(p1["score"], 30)
        self.assertIn("will-persistent", p1["zones"]["hand"])
        permission = session.rules_engine["playPermissions"][0]
        self.assertTrue(permission["noTribute"])
        session.phase_tracker["index"] = ADVANCED_PHASES.index(
            "confrontation_reaction"
        )
        source_error, source = session.rules_action_source(
            "p1", "play_card",
            {"cardId": "will-persistent", "zone": "hand"},
        )
        self.assertIsNone(source_error)
        self.assertEqual(session.rules_tribute_requirements(
            "play_card", source
        ), ({}, True))

    def test_source_created_tokens_can_be_sacrificed_for_an_encoded_effect(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["jija"] = {
            "type": "manifestation", "power": 3,
            "temperaments": ["hollow"],
        }
        source = {
            "id": "jija-item", "ownerId": "p1", "controllerId": "p1",
            "cardId": "jija", "faceUp": True,
            "fieldZone": "confrontation", "counters": {},
        }
        target = {
            "id": "target", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield = [source, target]
        create_action = {
            "controllerId": "p1",
            "source": {"cardId": "jija", "itemId": "jija-item"},
            "targets": [{"kind": "player", "playerId": "p2"}],
            "ability": {"result": {
                "kind": "create_tokens_for_target_interzone_count"
            }},
        }
        session.battlefield.extend([
            {
                "id": "inter-a", "ownerId": "p2", "cardId": "m-3",
                "faceUp": True, "fieldZone": "interzone", "counters": {},
            },
            {
                "id": "inter-b", "ownerId": "p2", "cardId": "m-4",
                "faceUp": True, "fieldZone": "interzone", "counters": {},
            },
        ])
        created = session.apply_rules_action_result(create_action)
        self.assertEqual(created["count"], 2)
        ability = {
            "sacrificeTokenCreatedBySource": True,
            "loseScore": 5,
        }
        paid = session.pay_rules_activation_cost({
            "itemId": "jija-item", "controllerId": "p1",
        }, ability)
        self.assertEqual(len(paid["sacrificedCards"]), 1)
        self.assertEqual(p1["score"], -5)
        self.assertEqual(
            len([item for item in session.battlefield if item.get("isTokenCard")]),
            1,
        )

    def test_bratto_capture_preserves_owner_and_creates_support_copy(self):
        session, _p1, _p2 = self.make_session()
        target = {
            "id": "stalemate", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "stalemate", "counters": {},
        }
        session.battlefield = [target]
        action = {
            "controllerId": "p1",
            "source": {"cardId": "bratto", "itemId": "bratto-item"},
            "targets": [{"kind": "card", "itemId": "stalemate", "cardId": "m-2"}],
            "ability": {"result": {"kind": "capture_stalemate_and_copy"}},
        }

        resolved = session.apply_rules_action_result(action)

        self.assertEqual(resolved["status"], "resolved")
        self.assertEqual(
            session.card_owner_in_zone("p1", "receptacle", "m-2"), "p2"
        )
        copy = session.find_battlefield_item(resolved["copyItemId"])
        self.assertTrue(copy["isCopy"])
        self.assertTrue(copy["isSupport"])

    def test_melancholic_mirror_offers_optional_exhaust_and_copy(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["mirror"] = {
            "type": "persistent_will",
            "triggeredAbilities": [{
                "id": "mirror-copy",
                "optional": True,
                "trigger": {"event": "manifestation_used_as_tribute"},
                "result": {"kind": "copy_related_tribute_if_exhaust"},
            }],
        }
        source = {
            "id": "mirror-item", "ownerId": "p1", "cardId": "mirror",
            "faceUp": True, "rotation": 0, "fieldZone": "field",
            "counters": {},
        }
        session.battlefield = [source]
        actions = session.queue_rules_triggers(
            "mirror", "p1", "manifestation_used_as_tribute",
            item_id="mirror-item", controller_id="p1",
            related_action={"source": {"cardId": "m-1", "ownerId": "p1"}},
        )
        choice = session.rules_engine["pendingChoice"]

        self.assertEqual(choice["kind"], "optional_stack_action")
        self.assertEqual(session.rules_engine["actionStack"], [])
        error, accepted = session.resolve_rules_choice(
            "p1", choice["id"], option="accept"
        )
        self.assertIsNone(error)
        self.assertEqual(accepted["status"], "accepted")
        result = session.apply_rules_action_result(
            session.rules_engine["actionStack"].pop()
        )
        self.assertEqual(result["status"], "accepted")
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertEqual(source["rotation"], 90.0)
        self.assertTrue(
            session.find_battlefield_item(result["createdItemId"])["isCopy"]
        )

    def test_recall_exiles_limbo_manifestations_and_creates_hollow_copies(self):
        session, p1, p2 = self.make_session()
        p1["zones"]["graveyard"] = ["m-1", "will-ephemeral"]
        p1["zoneOwners"]["graveyard"] = {
            "m-1": "p1", "will-ephemeral": "p1",
        }
        p2["zones"]["graveyard"] = ["m-2"]
        p2["zoneOwners"]["graveyard"] = {"m-2": "p2"}
        action = {
            "controllerId": "p1",
            "source": {"cardId": "recall"},
            "ability": {"result": {
                "kind": "exile_limbos_create_token_copies"
            }},
        }

        resolved = session.apply_rules_action_result(action)

        self.assertCountEqual(p1["zones"]["exile"], ["m-1"])
        self.assertEqual(p2["zones"]["exile"], ["m-2"])
        self.assertEqual(p1["zones"]["graveyard"], ["will-ephemeral"])
        copies = [
            session.find_battlefield_item(item_id)
            for item_id in resolved["createdItemIds"]
        ]
        self.assertTrue(all(copy["effectsDisabled"] for copy in copies))
        self.assertTrue(all(
            copy["temperamentOverride"] == "hollow" for copy in copies
        ))

    def test_tuxnu_copies_non_token_persistent_will_for_other_player(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["tuxnu"] = {
            "type": "manifestation",
            "triggeredAbilities": [{
                "id": "tuxnu-copy",
                "trigger": {"event": "persistent_will_enters_field"},
                "result": {
                    "kind": "copy_entering_persistent_will_for_others"
                },
            }],
        }
        source = {
            "id": "tuxnu-item", "ownerId": "p1", "cardId": "tuxnu",
            "faceUp": True, "fieldZone": "interzone", "counters": {},
        }
        will = {
            "id": "will-item", "ownerId": "p2", "cardId": "will-persistent",
            "faceUp": True, "fieldZone": "field", "counters": {},
        }
        session.battlefield = [source, will]
        actions = session.queue_rules_persistent_will_entry_watchers(
            will, defer=True
        )
        resolved = session.apply_rules_action_result(actions[0])

        self.assertEqual(len(resolved["createdItemIds"]), 1)
        copy = session.find_battlefield_item(resolved["createdItemIds"][0])
        self.assertEqual(session.rules_item_controller_id(copy), "p1")
        self.assertTrue(copy["isTokenCopy"])
        self.assertEqual(copy["fieldZone"], "field")

    def test_possessed_pyramid_schedules_next_turn_hand_reduction(self):
        session, _p1, _p2 = self.make_session()
        action = {
            "controllerId": "p1",
            "source": {
                "cardId": "pyramid", "containerId": "p2",
            },
            "ability": {"result": {
                "kind": "schedule_next_turn_hand_limit",
                "delta": -1,
                "overflowDestination": "graveyard",
            }},
        }

        resolved = session.apply_rules_action_result(action)

        self.assertEqual(resolved["playerId"], "p2")
        self.assertEqual(resolved["turn"], session.phase_tracker["turn"] + 1)
        session.phase_tracker["turn"] = resolved["turn"]
        self.assertEqual(session.rules_hand_limit("p2"), 6)

    def test_red_plague_choice_applies_points_or_immediate_hand_limit(self):
        session, _p1, p2 = self.make_session()
        p2["zones"]["hand"] = [f"m-{index}" for index in range(7)]
        p2["zoneOwners"]["hand"] = {
            card_id: "p2" for card_id in p2["zones"]["hand"]
        }
        action = {
            "controllerId": "p1",
            "source": {"cardId": "plague", "containerId": "p2"},
            "ability": {"result": {
                "kind": "choose_points_or_hand_limit",
                "points": 10, "limit": 5,
            }},
        }
        session.apply_rules_action_result(action)
        choice = session.rules_engine["pendingChoice"]

        error, limited = session.resolve_rules_choice(
            "p2", choice["id"], option="limit_hand"
        )

        self.assertIsNone(error)
        self.assertEqual(limited["limit"], 5)
        overflow = session.rules_engine["pendingChoice"]
        self.assertEqual(overflow["kind"], "hand_overflow")
        self.assertEqual(overflow["count"], 2)

    def test_palm_coercer_limits_hands_and_sends_excess_to_deck_bottom(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["palm"] = {
            "type": "persistent_will",
            "passiveEffects": [{
                "kind": "hand_limit_all", "value": 6,
                "overflowDestination": "deck_bottom",
            }],
        }
        session.battlefield = [{
            "id": "palm", "ownerId": "p1", "cardId": "palm",
            "faceUp": True, "fieldZone": "field", "counters": {},
        }]
        p1["zones"]["hand"] = [f"m-{index}" for index in range(7)]
        p1["zoneOwners"]["hand"] = {
            card_id: "p1" for card_id in p1["zones"]["hand"]
        }

        choice = session.set_rules_hand_overflow_choice(["p1"])
        error, resolved = session.resolve_rules_choice(
            "p1", choice["id"], card_ids=["m-0"]
        )

        self.assertIsNone(error)
        self.assertEqual(resolved["destination"], "deck_bottom")
        self.assertEqual(p1["zones"]["deck"][-1], "m-0")
        self.assertEqual(len(p1["zones"]["hand"]), 6)

    def test_solitary_combhand_draws_for_empty_interzone_slots(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["combhand"] = {
            "type": "manifestation",
            "passiveEffects": [{
                "kind": "extra_recovery_draw_per_empty_interzone"
            }],
        }
        session.battlefield = [{
            "id": "combhand", "ownerId": "p1", "cardId": "combhand",
            "faceUp": True, "fieldZone": "interzone", "counters": {},
        }]
        self.fill_deck(p1, [f"m-{index}" for index in range(10)])

        error, result = session._draw_rules_recovery_hand("p1")

        self.assertIsNone(error)
        self.assertEqual(result["handLimit"], 9)
        self.assertEqual(result["count"], 9)

    def test_kanon_replaces_nonrecovery_draw_and_assigns_will_power_loss(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index(
            "confrontation_reaction"
        )
        session.card_rules["kanon"] = {
            "type": "manifestation",
            "passiveEffects": [{
                "kind": "replace_opponent_nonrecovery_draw"
            }],
        }
        kanon = {
            "id": "kanon", "ownerId": "p1", "cardId": "kanon",
            "faceUp": True, "fieldZone": "interzone", "counters": {},
        }
        target = {
            "id": "target", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield = [kanon, target]
        self.fill_deck(p2, ["will-ephemeral", "m-3", "will-persistent"])

        required = session.request_rules_draw("p2", 3, "p2")
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(required["choiceKind"], "draw_replacement")
        error, replaced = session.resolve_rules_choice(
            "p2", choice["id"],
            card_ids=["will-ephemeral", "will-persistent"],
        )
        self.assertIsNone(error)
        self.assertEqual(replaced["willCount"], 2)
        distribution = session.rules_engine["pendingChoice"]
        error, applied = session.resolve_rules_choice(
            "p1", distribution["id"],
            option={"itemIds": ["target", "target"]},
        )
        self.assertIsNone(error)
        self.assertEqual(len(applied["effectIds"]), 2)
        self.assertEqual(
            session.rules_manifestation_characteristics(target)["power"], -1
        )
        self.assertEqual(p2["zones"]["hand"], ["m-3"])

    def test_arcane_teapot_reduces_controller_will_tribute_by_one(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["teapot"] = {
            "type": "manifestation",
            "passiveEffects": [{
                "kind": "reduce_will_tribute", "value": 1,
            }],
        }
        session.battlefield = [{
            "id": "teapot", "ownerId": "p1", "cardId": "teapot",
            "faceUp": True, "fieldZone": "interzone", "counters": {},
        }]
        source = {
            "cardId": "will-persistent", "cardType": "persistent_will",
            "controllerId": "p1",
        }

        requirements, enforced = session.rules_tribute_requirements(
            "play_card", source, player_id="p1"
        )

        self.assertTrue(enforced)
        self.assertEqual(sum(requirements.values()), 1)

    def test_alchemical_press_uses_limbo_tribute_and_formula_counter(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["press"] = {
            "type": "persistent_will",
            "passiveEffects": [{
                "kind": "allow_limbo_tribute_with_counter",
                "counter": "Formula",
            }],
        }
        press = {
            "id": "press", "ownerId": "p1", "cardId": "press",
            "faceUp": True, "fieldZone": "field",
            "counters": {"Formula": 2},
        }
        session.battlefield = [press]
        p1["zones"]["graveyard"] = ["m-1"]
        p1["zoneOwners"]["graveyard"] = {"m-1": "p1"}

        error, payment = session.rules_action_payment(
            "p1", "play_card",
            {"cardId": "will-ephemeral", "cardType": "ephemeral_will",
             "controllerId": "p1"},
            ["graveyard|m-1"],
        )
        self.assertIsNone(error)
        paid = session.pay_rules_tribute("p1", payment)

        self.assertEqual(press["counters"]["Formula"], 1)
        self.assertEqual(p1["zones"]["exile"], ["m-1"])
        self.assertEqual(paid["movements"][0]["fromZone"], "graveyard")

    def test_alchemical_press_will_watcher_offers_optional_discard_draw(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["press"] = {
            "type": "persistent_will",
            "triggeredAbilities": [{
                "id": "press-cycle",
                "optional": True,
                "trigger": {"event": "will_played"},
                "result": {
                    "kind": "optional_discard_then_draw", "draw": 1,
                },
            }],
        }
        press = {
            "id": "press", "ownerId": "p1", "cardId": "press",
            "faceUp": True, "fieldZone": "field", "counters": {},
        }
        session.battlefield = [press]
        p1["zones"]["hand"] = ["m-1"]
        p1["zoneOwners"]["hand"] = {"m-1": "p1"}
        paid_action = {
            "id": "paid", "controllerId": "p1", "kind": "play_card",
            "source": {"cardId": "will-ephemeral", "ownerId": "p1"},
        }
        session.rules_engine["actionStack"] = [paid_action]
        queued = session.queue_rules_tribute_triggers(
            [], "p1", simultaneous_action_id="paid"
        )
        watcher = next(
            action for action in queued
            if action["source"]["cardId"] == "press"
        )
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "optional_stack_action")
        self.assertEqual(session.rules_engine["actionStack"], [])
        self.assertIsNone(session.resolve_rules_choice(
            "p1", choice["id"], option="accept"
        )[0])
        order_choice = session.rules_engine["pendingChoice"]
        self.assertEqual(order_choice["kind"], "simultaneous_stack_order")
        self.assertIsNone(session.resolve_rules_choice(
            "p1", order_choice["id"], [paid_action["id"], watcher["id"]]
        )[0])
        self.assertEqual(session.rules_engine["actionStack"][-1]["id"], watcher["id"])
        result = session.apply_rules_action_result(
            session.rules_engine["actionStack"].pop()
        )

        self.assertEqual(result["choiceKind"], "discard_from_hand")

    def test_hermetic_threshold_draws_on_each_players_first_will_per_turn(self):
        session, p1, p2 = self.make_session()
        session.card_rules["hermetic"] = {
            "type": "persistent_will",
            "triggeredAbilities": [{
                "id": "draw-on-first-will-of-turn",
                "trigger": {"event": "will_played", "firstWillOfTurn": True},
                "result": {"kind": "draw_owner", "value": 1},
            }],
        }
        session.battlefield = [{
            "id": "hermetic", "ownerId": "p1", "cardId": "hermetic",
            "faceUp": True, "fieldZone": "field", "counters": {},
        }]
        session.card_rules["will-x"] = {"type": "ephemeral_will"}

        def play_will(owner_id, n):
            action = {
                "id": f"paid-{n}", "controllerId": owner_id, "kind": "play_card",
                "source": {"cardId": "will-x", "ownerId": owner_id},
            }
            session.rules_engine["actionStack"] = [action]
            session.rules_engine["pendingChoice"] = None
            return [
                queued for queued in session.queue_rules_tribute_triggers(
                    [], owner_id, simultaneous_action_id=action["id"]
                ) if queued["source"]["cardId"] == "hermetic"
            ]

        self.assertEqual(len(play_will("p1", 1)), 1)
        self.assertEqual(play_will("p1", 2), [])
        self.assertEqual(len(play_will("p2", 3)), 1)
        self.assertEqual(play_will("p2", 4), [])
        session.phase_tracker["turn"] += 1
        self.assertEqual(len(play_will("p1", 5)), 1)

    def test_optional_targeted_trigger_asks_before_targeting_and_stacking(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["greed"] = {
            "type": "persistent_will",
            "triggeredAbilities": [{
                "id": "greed-roll",
                "optional": True,
                "trigger": {
                    "event": "will_played",
                    "eventController": "opponent",
                },
                "targets": {
                    "min": 1, "max": 1,
                    "cardType": "manifestation",
                    "zones": ["battlefield"],
                    "fieldZone": "confrontation",
                    "controller": "opponent",
                },
                "result": {
                    "kind": "roll_d6_target_table",
                    "table": "greed",
                },
            }],
        }
        source = {
            "id": "greed-field", "ownerId": "p1", "cardId": "greed",
            "faceUp": True, "fieldZone": "field", "counters": {},
        }
        target = {
            "id": "target-field", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield = [source, target]

        session.queue_rules_triggers(
            "greed", "p1", "will_played",
            item_id="greed-field", controller_id="p1",
            event_controller_id="p2",
        )

        optional_choice = session.rules_engine["pendingChoice"]
        self.assertEqual(optional_choice["kind"], "optional_stack_action")
        self.assertEqual(session.rules_engine["actionStack"], [])
        self.assertIsNone(session.resolve_rules_choice(
            "p1", optional_choice["id"], option="accept"
        )[0])
        target_choice = session.rules_engine["pendingChoice"]
        self.assertEqual(target_choice["kind"], "trigger_targets")
        self.assertEqual(session.rules_engine["actionStack"], [])
        target_error, targeted = session.resolve_rules_choice(
            "p1", target_choice["id"],
            targets=[{
                "kind": "card", "itemId": "target-field",
                "cardId": "m-2", "ownerId": "p2",
            }],
        )

        self.assertIsNone(target_error)
        self.assertEqual(targeted["actionId"], optional_choice["actionId"])
        self.assertEqual(len(session.rules_engine["actionStack"]), 1)

    def test_inflate_reduces_cost_and_sets_first_power_to_ten(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["first"] = {
            "type": "manifestation", "power": 5,
            "temperaments": ["choleric"],
        }
        first = {
            "id": "first", "ownerId": "p1", "cardId": "first",
            "faceUp": True, "fieldZone": "confrontation",
            "counters": {"power": 4},
        }
        session.battlefield = [first]
        session.rules_engine["firstManifestationItemIds"] = {"p1": "first"}
        ability = {
            "id": "inflate",
            "costReduction": {"kind": "half_first_base_power"},
            "ongoingEffect": {
                "kind": "power_set_maximum", "value": 10,
                "duration": "until_end_of_turn",
            },
            "targets": {},
        }
        source = {
            "cardId": "inflate", "cardType": "ephemeral_will",
            "controllerId": "p1",
        }
        session.card_rules["inflate"] = {
            "type": "ephemeral_will", "powerCost": "{R}{R}{R}{R}{R}",
            "temperaments": ["choleric"],
        }
        requirements, _ = session.rules_tribute_requirements(
            "play_card", source, ability, "p1"
        )
        action = {
            "id": "inflate-action", "controllerId": "p1",
            "source": source,
            "targets": [{"kind": "card", "itemId": "first",
                         "cardId": "first", "ownerId": "p1"}],
            "ability": ability,
        }
        session.create_rules_ongoing_effects(action)

        self.assertEqual(sum(requirements.values()), 3)
        self.assertEqual(
            session.rules_manifestation_characteristics(first)["power"], 10
        )

    def test_multicastigate_spends_three_extra_essences_for_two_targets(self):
        session, p1, _p2 = self.make_session()
        session.tokens = [{
            "id": "essence", "ownerId": "p1", "isEssence": True,
            "temperament": "hollow", "isNeutralCounter": False,
            "counters": {"essence": 5},
        }]
        p1["zones"]["hand"] = ["m-1"]
        p1["zoneOwners"]["hand"] = {"m-1": "p1"}
        ability = {
            "tribute": "{H}{H}",
            "extraEssenceByTargetCount": {
                "targetCount": 2, "amount": 3,
            },
        }
        targets = [
            {"kind": "card", "itemId": "a", "cardId": "m-2"},
            {"kind": "card", "itemId": "b", "cardId": "m-3"},
        ]

        error, payment = session.rules_action_payment(
            "p1", "play_card",
            {"cardId": "multi", "cardType": "ephemeral_will",
             "controllerId": "p1"},
            [], ability, targets,
        )

        self.assertIsNone(error)
        self.assertEqual(
            sum(entry["amount"] for entry in payment["essenceSpent"]), 5
        )

    def test_subjugate_requires_essences_matching_target_points(self):
        session, _p1, _p2 = self.make_session()
        session.card_points["m-2"] = 30
        session.tokens = [{
            "id": "essence", "ownerId": "p1", "isEssence": True,
            "temperament": "hollow", "isNeutralCounter": False,
            "counters": {"essence": 3},
        }]
        ability = {
            "tribute": "{H}",
            "extraEssenceForTargetPoints": {
                "multiplier": 10, "maxExtra": 4,
            },
        }

        error, payment = session.rules_action_payment(
            "p1", "play_card",
            {"cardId": "subjugate", "cardType": "ephemeral_will",
             "controllerId": "p1"},
            [], ability,
            [{"kind": "card", "itemId": "target", "cardId": "m-2"}],
        )

        self.assertIsNone(error)
        self.assertEqual(
            sum(entry["amount"] for entry in payment["essenceSpent"]), 3
        )

    def test_essence_cauldron_retains_generated_essence(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["cauldron"] = {
            "type": "persistent_will",
            "passiveEffects": [{"kind": "retain_excess_essence"}],
        }
        session.battlefield = [{
            "id": "cauldron", "ownerId": "p1", "cardId": "cauldron",
            "faceUp": True, "fieldZone": "field", "counters": {},
        }]
        session.tokens = [{
            "id": "essence", "ownerId": "p1", "isEssence": True,
            "temperament": "phlegmatic", "isNeutralCounter": False,
            "counters": {"essence": 2}, "expiresTurn": 1,
        }]

        expired = session.expire_rules_excess_essence(1)

        self.assertEqual(expired, [])
        self.assertEqual(len(session.tokens), 1)

    def test_greed_trap_roll_applies_server_owned_power_loss(self):
        session, _p1, _p2 = self.make_session()
        target = {
            "id": "target", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield = [target]
        action = {
            "id": "greed", "controllerId": "p1",
            "source": {"cardId": "greed"},
            "targets": [{"kind": "card", "itemId": "target",
                         "cardId": "m-2", "ownerId": "p2"}],
            "ability": {"result": {
                "kind": "roll_d6_target_table", "table": "greed",
            }},
        }

        with patch("session.random.randint", return_value=6):
            result = session.apply_rules_action_result(action)

        self.assertEqual(result["value"], -2)
        self.assertEqual(
            session.rules_manifestation_characteristics(target)["power"], -1
        )

    def test_plinius_rolls_parity_power_modifier(self):
        session, _p1, _p2 = self.make_session()
        source = {
            "id": "plinius", "ownerId": "p1", "cardId": "m-1",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield = [source]
        action = {
            "id": "plinius-action", "controllerId": "p1",
            "source": {"cardId": "m-1", "itemId": "plinius"},
            "ability": {"id": "roll", "result": {
                "kind": "roll_d6_power_by_parity", "even": 4, "odd": -4,
            }},
        }

        with patch("session.random.randint", return_value=2):
            result = session.apply_rules_action_result(action)

        self.assertEqual(result["value"], 4)
        self.assertEqual(
            session.rules_manifestation_characteristics(source)["power"], 5
        )

    def test_mutate_uncontrollably_uses_full_d6_table(self):
        session, _p1, _p2 = self.make_session()
        target = {
            "id": "target", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield = [target]
        action = {
            "id": "mutate", "controllerId": "p1",
            "source": {"cardId": "mutate"},
            "targets": [{"kind": "card", "itemId": "target",
                         "cardId": "m-2", "ownerId": "p2"}],
            "ability": {"result": {
                "kind": "roll_d6_target_table", "table": "mutation",
            }},
        }

        with patch("session.random.randint", return_value=3):
            result = session.apply_rules_action_result(action)

        self.assertEqual(result["roll"], 3)
        self.assertEqual(target["temperamentOverride"], "hollow")

    def test_bibi_odd_roll_targets_friendly_card_and_win_uses_stored_roll(self):
        session, _p1, _p2 = self.make_session()
        bibi = {
            "id": "bibi", "ownerId": "p1", "controllerId": "p2",
            "cardId": "bibi-card", "faceUp": True,
            "fieldZone": "confrontation", "counters": {},
        }
        friendly = {
            "id": "friendly", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield = [bibi, friendly]
        action = {
            "id": "bibi-roll", "controllerId": "p2",
            "source": {"cardId": "bibi-card", "itemId": "bibi"},
            "ability": {"result": {"kind": "roll_d6_conditional_source"}},
        }
        with patch("session.random.randint", return_value=5):
            required = session.apply_rules_action_result(action)
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(required["choiceKind"], "random_target_effect")
        self.assertIsNone(session.resolve_rules_choice(
            "p2", choice["id"], item_id="friendly"
        )[0])
        win_action = {
            "controllerId": "p2",
            "source": {"cardId": "bibi-card", "itemId": "bibi"},
            "ability": {"result": {
                "kind": "score_controller_by_source_roll_then_exile"
            }},
        }
        result = session.apply_rules_action_result(win_action)

        self.assertEqual(result["delta"], -15)
        self.assertEqual(session.players["p2"]["score"], -15)
        self.assertIn("bibi-card", session.players["p1"]["zones"]["exile"])

    def test_pillarpede_rolls_five_and_requires_odd_discards(self):
        session, p1, _p2 = self.make_session()
        source = {
            "id": "pillar", "ownerId": "p1", "cardId": "m-1",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield = [source]
        p1["zones"]["hand"] = ["m-2", "m-3", "m-4"]
        p1["zoneOwners"]["hand"] = {
            card_id: "p1" for card_id in p1["zones"]["hand"]
        }
        action = {
            "controllerId": "p1",
            "source": {"cardId": "m-1", "itemId": "pillar"},
            "ability": {"result": {
                "kind": "roll_multiple_even_power_odd_discard", "rolls": 5,
            }},
        }
        with patch(
            "session.random.randint",
            side_effect=[2, 3, 4, 5, 6],
        ):
            result = session.apply_rules_action_result(action)

        self.assertEqual(result["evenCount"], 3)
        self.assertEqual(result["oddCount"], 2)
        self.assertEqual(source["counters"]["power"], 3)
        self.assertEqual(session.rules_engine["pendingChoice"]["count"], 2)

    def test_stomper_forces_winner_when_highest_base_first(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["stomper"] = {
            "type": "manifestation", "power": 4,
            "temperaments": ["capricious"],
        }
        session.card_rules["other-first"] = {
            "type": "manifestation", "power": 3,
            "temperaments": ["phlegmatic"],
        }
        stomper = {
            "id": "stomper", "ownerId": "p1", "cardId": "stomper",
            "faceUp": True, "fieldZone": "confrontation",
            "confrontationOrder": 1, "counters": {},
        }
        other = {
            "id": "other", "ownerId": "p2", "cardId": "other-first",
            "faceUp": True, "fieldZone": "confrontation",
            "confrontationOrder": 2, "counters": {"power": 10},
        }
        session.battlefield = [stomper, other]
        session.rules_engine["firstManifestationItemIds"] = {
            "p1": "stomper", "p2": "other",
        }
        result = session.apply_rules_action_result({
            "controllerId": "p1",
            "source": {"cardId": "stomper", "itemId": "stomper"},
            "ability": {"result": {
                "kind": "force_win_if_highest_base_first"
            }},
        })
        session.phase_tracker["index"] = ADVANCED_PHASES.index(
            "resolution_compare"
        )
        comparison = session.prepare_rules_confrontation_result()

        self.assertEqual(result["status"], "forced")
        self.assertEqual(comparison["winnerId"], "p1")
        self.assertEqual(comparison["reason"], "forced")

    def test_sermon_choice_can_skip_to_resolution_compare(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["strong"] = {
            "type": "manifestation", "power": 4,
        }
        session.card_rules["weak"] = {
            "type": "manifestation", "power": 2,
        }
        session.battlefield = [
            {"id": "strong", "ownerId": "p1", "cardId": "strong",
             "faceUp": True, "fieldZone": "confrontation", "counters": {}},
            {"id": "weak", "ownerId": "p2", "cardId": "weak",
             "faceUp": True, "fieldZone": "confrontation", "counters": {}},
        ]
        session.rules_engine["firstManifestationItemIds"] = {
            "p1": "strong", "p2": "weak",
        }
        required = session.apply_rules_action_result({
            "controllerId": "p1",
            "source": {"cardId": "sermon", "itemId": "sermon"},
            "ability": {"result": {
                "kind": "skip_confrontation_unless_points", "points": 10,
            }},
        })
        choice = session.rules_engine["pendingChoice"]
        error, skipped = session.resolve_rules_choice(
            "p2", choice["id"], option="skip"
        )

        self.assertEqual(required["choiceKind"], "skip_confrontation_payment")
        self.assertIsNone(error)
        self.assertEqual(skipped["phaseId"], "resolution_compare")

    def test_last_entry_loudmouth_forces_stalemate(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["loudmouth"] = {
            "type": "manifestation", "power": 1,
            "passiveEffects": [{
                "kind": "stalemate_if_last_confrontation_entry"
            }],
        }
        session.card_rules["m-1"]["power"] = 10
        session.battlefield = [
            {"id": "strong", "ownerId": "p1", "cardId": "m-1",
             "faceUp": True, "fieldZone": "confrontation",
             "confrontationOrder": 1, "counters": {}},
            {"id": "loud", "ownerId": "p2", "cardId": "loudmouth",
             "faceUp": True, "fieldZone": "confrontation",
             "confrontationOrder": 2, "counters": {}},
        ]
        session.phase_tracker["index"] = ADVANCED_PHASES.index(
            "resolution_compare"
        )

        result = session.prepare_rules_confrontation_result()

        self.assertTrue(result["stalemate"])
        self.assertIsNone(result["winnerId"])

    def test_half_han_excludes_normal_win_and_enables_negative_score_win(self):
        session, p1, p2 = self.make_session()
        session.card_rules["half"] = {
            "type": "manifestation",
            "passiveEffects": [{"kind": "negative_score_victory"}],
        }
        p1["zones"]["graveyard"] = ["half"]
        p1["zoneOwners"]["graveyard"] = {"half": "p1"}
        p1["score"] = -130
        p2["score"] = 100

        outcome = session.calculate_final_scores()

        self.assertEqual(outcome["winnerIds"], ["p1"])
        self.assertEqual(outcome["alternateVictoryPlayerIds"], ["p1"])
        p1["score"] = 200
        outcome = session.calculate_final_scores()
        self.assertEqual(outcome["winnerIds"], ["p2"])
        self.assertIn("p1", outcome["normalVictoryExcludedPlayerIds"])

    def test_jeovak_relocates_confrontation_and_skips_resolution(self):
        session, _p1, _p2 = self.make_session()
        jeovak = {
            "id": "jeovak", "ownerId": "p1", "cardId": "jeovak-card",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        own = {
            "id": "own", "ownerId": "p1", "cardId": "m-1",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        opposing = {
            "id": "opposing", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield = [jeovak, own, opposing]
        required = session.apply_rules_action_result({
            "controllerId": "p1",
            "source": {"cardId": "jeovak-card", "itemId": "jeovak"},
            "ability": {"result": {
                "kind": "end_confrontation_relocate_all"
            }},
        })
        choice = session.rules_engine["pendingChoice"]
        error, resolved = session.resolve_rules_choice(
            "p1", choice["id"], option={"groups": [
                {"playerId": "p1", "interzone": ["own"], "deckBottom": []},
                {"playerId": "p2", "interzone": [], "deckBottom": ["opposing"]},
            ]}
        )

        self.assertEqual(required["choiceKind"], "confrontation_relocation")
        self.assertIsNone(error)
        self.assertEqual(resolved["phaseId"], "end_actions")
        self.assertIn("jeovak-card", session.players["p1"]["zones"]["exile"])
        self.assertEqual(session.find_battlefield_item("own")["fieldZone"], "interzone")
        self.assertIn("m-2", session.players["p2"]["zones"]["deck"])
        self.assertEqual(session.players["p2"]["score"], 50)

    def test_float_can_be_granted_removed_and_derived_from_counters(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["tower"] = {
            "type": "persistent_will",
            "passiveEffects": [
                {"kind": "float_with_counter", "counter": "Abstraction"},
                {"kind": "friendly_float_power_bonus", "value": 1},
            ],
        }
        tower = {
            "id": "tower", "ownerId": "p1", "cardId": "tower",
            "faceUp": True, "fieldZone": "field", "counters": {},
        }
        target = {
            "id": "target", "ownerId": "p1", "cardId": "m-1",
            "faceUp": True, "fieldZone": "interzone",
            "counters": {"Abstraction": 1},
        }
        session.battlefield = [tower, target]
        self.assertTrue(session.rules_item_has_float(target))
        self.assertEqual(
            session.rules_manifestation_characteristics(target)["power"], 2
        )
        session.rules_engine["ongoingEffects"].append({
            "id": "remove", "kind": "remove_float",
            "duration": "while_target_on_field",
            "target": {"itemId": "target"},
            "source": {"cardId": "sever"},
        })
        self.assertFalse(session.rules_item_has_float(target))
        session.rules_engine["ongoingEffects"].append({
            "id": "grant", "kind": "grant_float",
            "duration": "while_target_on_field",
            "target": {"itemId": "target"},
            "source": {"cardId": "float"},
        })
        self.assertFalse(
            session.rules_item_has_float(target),
            "remove_float remains the absolute prohibition",
        )
        session.rules_engine["ongoingEffects"] = [
            effect for effect in session.rules_engine["ongoingEffects"]
            if effect["id"] != "remove"
        ]
        self.assertTrue(session.rules_item_has_float(target))

    def test_adamant_does_not_stop_an_opponents_destruction(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["adamant-card"] = {
            "type": "manifestation", "power": 2, "adamant": True,
        }
        session.battlefield = [{
            "id": "adamant", "ownerId": "p2", "cardId": "adamant-card",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }]
        result = session.apply_rules_action_result({
            "controllerId": "p1",
            "targets": [{"kind": "card", "itemId": "adamant",
                         "cardId": "adamant-card", "ownerId": "p2"}],
            "ability": {"result": {
                "kind": "move_target", "zone": "graveyard",
                "position": "top", "reason": "destroy",
            }},
        })
        self.assertNotEqual(result["status"], "prevented_adamant")
        self.assertIsNone(session.find_battlefield_item("adamant"))

    def test_adamant_keyword_protects_any_compiled_card_from_opposing_move(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["adamant-card"] = {
            "type": "manifestation", "power": 2,
            "adamant": True,
        }
        target = {
            "id": "adamant", "ownerId": "p2",
            "cardId": "adamant-card", "faceUp": True,
            "fieldZone": "interzone", "counters": {},
        }
        session.battlefield = [target]
        action = {
            "controllerId": "p1",
            "targets": [{"kind": "card", "itemId": "adamant",
                         "cardId": "adamant-card", "ownerId": "p2"}],
            "ability": {"result": {
                "kind": "move_target", "zone": "hand",
                "position": "top",
            }},
        }

        result = session.apply_rules_action_result(action)

        self.assertEqual(result["status"], "prevented_adamant")
        self.assertIsNotNone(session.find_battlefield_item("adamant"))

    def test_gobres_suspends_private_will_and_allows_any_temperament_payment(self):
        session, p1, p2 = self.make_session()
        source = {
            "id": "gobres", "ownerId": "p1", "cardId": "gobres-card",
            "faceUp": True, "fieldZone": "interzone", "counters": {},
            "x": 0, "y": 0, "rotation": 0,
        }
        session.battlefield = [source]
        p2["zones"]["hand"] = ["will-persistent", "m-2"]
        p2["zoneOwners"]["hand"] = {
            "will-persistent": "p2", "m-2": "p2",
        }
        required = session.apply_rules_action_result({
            "controllerId": "p1",
            "source": {"cardId": "gobres-card", "itemId": "gobres"},
            "targets": [{"kind": "player", "playerId": "p2"}],
            "ability": {"result": {
                "kind": "suspend_opponent_hand_will"
            }},
        })
        choice = session.rules_engine["pendingChoice"]
        own_view = session.serialize_for("p2", "player")["rulesEngine"]["pendingChoice"]
        opponent_view = session.serialize_for("p1", "player")["rulesEngine"]["pendingChoice"]
        self.assertEqual(required["choiceKind"], "suspend_hand_will")
        self.assertIn("cardIds", own_view)
        self.assertNotIn("cardIds", opponent_view)
        error, suspended = session.resolve_rules_choice(
            "p2", choice["id"], card_ids=["will-persistent"]
        )
        self.assertIsNone(error)
        entry = session.rules_engine["suspendedCards"][0]
        self.assertEqual(entry["playableByPlayerId"], "p1")
        session.phase_tracker["index"] = ADVANCED_PHASES.index("end_actions")
        source_error, clean_source = session.rules_action_source(
            "p1", "play_card",
            {"cardId": "will-persistent", "zone": "suspended"},
        )
        self.assertIsNone(source_error)
        requirements, _ = session.rules_tribute_requirements(
            "play_card", clean_source, player_id="p1"
        )
        self.assertEqual(requirements, {"hollow": 2})
        self.assertEqual(suspended["cardId"], "will-persistent")

    def test_temporary_suspension_returns_to_hand_at_turn_end_or_source_exit(self):
        session, _p1, p2 = self.make_session()
        p2["zones"]["hand"] = ["will-ephemeral"]
        p2["zoneOwners"]["hand"] = {"will-ephemeral": "p2"}
        error, suspended = session.suspend_zone_card(
            "p2", "hand", "will-ephemeral",
            source_effect_id="gobres",
            returnZone="hand", returnTurn=1,
            playableByPlayerId="p1",
        )
        self.assertIsNone(error)
        expired = session.expire_rules_temporary_suspensions(1)
        self.assertEqual(expired[0]["id"], suspended["id"])
        self.assertIn("will-ephemeral", p2["zones"]["hand"])

    def test_any_player_can_pay_to_destroy_a_shared_source(self):
        session, _p1, p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index("end_actions")
        session.rules_engine["priorityPlayerId"] = "p2"
        session.card_rules["psychowall"] = {
            "type": "persistent_will",
            "activatedAbilities": [{
                "id": "destroy",
                "anyPlayer": True,
                "tribute": "{H}{H}{H}{H}",
                "targets": {"min": 0, "max": 0},
                "result": {"kind": "destroy_source"},
            }],
        }
        wall = {
            "id": "wall", "ownerId": "p1", "controllerId": "p1",
            "cardId": "psychowall", "faceUp": True,
            "fieldZone": "field", "counters": {},
        }
        session.battlefield = [wall]
        tribute_ids = ["m-0", "m-1", "m-2", "m-3"]
        for card_id in tribute_ids:
            session.card_rules[card_id].update({
                "power": 1,
                "temperaments": ["hollow"],
            })
        p2["zones"]["hand"] = list(tribute_ids)
        p2["zoneOwners"]["hand"] = {
            card_id: "p2" for card_id in tribute_ids
        }

        error, action = session.declare_rules_action(
            "p2", "Destroy Psychowall", kind="activated_effect",
            source={
                "cardId": "psychowall", "zone": "battlefield",
                "itemId": "wall",
            },
            payment_card_ids=tribute_ids,
            ability_id="destroy",
        )

        self.assertIsNone(error)
        self.assertEqual(action["controllerId"], "p2")
        self.assertEqual(action["source"]["ownerId"], "p1")
        self.assertCountEqual(p2["zones"]["graveyard"], tribute_ids)
        session.pass_rules_priority("p1")
        resolution = session.pass_rules_priority("p2")[1]
        self.assertEqual(
            resolution["action"]["effectResult"]["status"], "moved"
        )
        self.assertNotIn(wall, session.battlefield)
        self.assertIn("psychowall", session.players["p1"]["zones"]["graveyard"])

    def test_abstraction_counters_enter_and_move_between_valid_targets(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index("end_actions")
        session.rules_engine["priorityPlayerId"] = "p1"
        session.card_rules["tower"] = {
            "type": "persistent_will",
            "triggeredAbilities": [{
                "id": "enter-counters",
                "trigger": {"event": "enters_field"},
                "result": {
                    "kind": "add_counter_source",
                    "counter": "Abstraction",
                    "value": 3,
                },
            }],
            "activatedAbilities": [{
                "id": "move-counter",
                "tribute": "{B}",
                "targetGroups": [
                    {
                        "min": 1, "max": 1,
                        "cardTypes": ["manifestation", "persistent_will"],
                        "zones": ["battlefield"], "controller": "self",
                        "counter": "Abstraction", "minCounters": 1,
                    },
                    {
                        "min": 1, "max": 1,
                        "cardType": "manifestation",
                        "zones": ["battlefield"],
                    },
                ],
                "result": {
                    "kind": "move_counter",
                    "counter": "Abstraction",
                    "value": 1,
                },
            }],
        }
        tower = {
            "id": "tower", "ownerId": "p1", "cardId": "tower",
            "faceUp": True, "fieldZone": "field", "counters": {},
        }
        target = {
            "id": "target", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield = [tower, target]
        triggers = session.queue_rules_triggers(
            "tower", "p1", "enters_field",
            item_id="tower", event_item_id="tower",
        )
        self.assertEqual(len(triggers), 1)
        session.pass_rules_priority("p2")
        session.pass_rules_priority("p1")
        self.assertEqual(tower["counters"]["Abstraction"], 3)

        session.card_rules["m-0"].update({
            "power": 1, "temperaments": ["vitreous"],
        })
        p1["zones"]["hand"] = ["m-0"]
        p1["zoneOwners"]["hand"] = {"m-0": "p1"}
        session.rules_engine["priorityPlayerId"] = "p1"
        error, _action = session.declare_rules_action(
            "p1", "Move Abstraction", kind="activated_effect",
            source={
                "cardId": "tower", "zone": "battlefield",
                "itemId": "tower",
            },
            targets=[
                {"kind": "card", "itemId": "tower", "cardId": "tower"},
                {"kind": "card", "itemId": "target", "cardId": "m-2"},
            ],
            payment_card_ids=["m-0"],
            ability_id="move-counter",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        resolution = session.pass_rules_priority("p1")[1]
        moved = resolution["action"]["effectResult"]
        self.assertEqual(moved["status"], "moved")
        self.assertEqual(tower["counters"]["Abstraction"], 2)
        self.assertEqual(target["counters"]["Abstraction"], 1)

    def test_first_manifestation_support_and_counter_target_contracts_revalidate(self):
        session, _p1, _p2 = self.make_session()
        mine = {
            "id": "mine", "ownerId": "p1", "cardId": "m-1",
            "faceUp": True, "fieldZone": "confrontation",
            "isSupport": True, "counters": {},
        }
        theirs = {
            "id": "theirs", "ownerId": "p2", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation",
            "counters": {"Abstraction": 1},
        }
        session.battlefield = [mine, theirs]
        session.rules_engine["firstManifestationItemIds"] = {
            "p1": "mine", "p2": "theirs",
        }
        opponent_first = {
            "min": 1, "max": 1, "cardType": "manifestation",
            "controller": "opponent", "firstManifestationOnly": True,
        }
        support = {
            "min": 1, "max": 1, "cardType": "manifestation",
            "supportOnly": True,
        }
        counter = {
            "min": 1, "max": 1, "cardType": "manifestation",
            "counter": "Abstraction", "minCounters": 1,
        }
        self.assertIsNone(session.rules_ability_targets_error(
            opponent_first,
            [{"kind": "card", "itemId": "theirs", "cardId": "m-2"}],
            "p1",
        ))
        self.assertIsNone(session.rules_ability_targets_error(
            support,
            [{"kind": "card", "itemId": "mine", "cardId": "m-1"}],
            "p1",
        ))
        self.assertIsNone(session.rules_ability_targets_error(
            counter,
            [{"kind": "card", "itemId": "theirs", "cardId": "m-2"}],
            "p1",
        ))
        theirs["counters"] = {}
        self.assertIn("counters", session.rules_ability_targets_error(
            counter,
            [{"kind": "card", "itemId": "theirs", "cardId": "m-2"}],
            "p1",
        ))

    def test_stack_card_protection_blocks_targeting_and_follows_permanents(self):
        session, _p1, _p2 = self.make_session()
        target_action = {
            "id": "target-action",
            "controllerId": "p2",
            "kind": "play_card",
            "sourceOnStack": True,
            "source": {
                "cardId": "will-persistent", "cardType": "persistent_will",
                "ownerId": "p2", "zone": "hand",
            },
            "ability": None,
            "targets": [],
        }
        wall_action = {
            "id": "wall-action",
            "controllerId": "p1",
            "kind": "play_card",
            "source": {"cardId": "wall-off"},
            "targets": [{
                "kind": "stack_action", "actionId": "target-action",
                "cardId": "will-persistent", "controllerId": "p2",
            }],
            "ability": {
                "id": "protect",
                "ongoingEffect": {
                    "kind": "protection",
                    "duration": "until_end_of_turn",
                },
            },
        }
        session.rules_engine["actionStack"] = [target_action]
        effects = session.create_rules_ongoing_effects(wall_action)
        self.assertEqual(effects[0]["target"]["actionId"], "target-action")
        error = session.rules_ability_targets_error(
            {
                "kind": "stack_action", "min": 1, "max": 1,
                "cardType": "persistent_will",
            },
            wall_action["targets"],
            "p1",
        )
        self.assertIn("Protected", error)

        session.players["p2"]["zones"]["hand"] = ["will-persistent"]
        session.players["p2"]["zoneOwners"]["hand"] = {
            "will-persistent": "p2"
        }
        target_action["placement"] = {"x": 10, "y": 20}
        resolved = session.resolve_rules_action_source(target_action)
        protected = session.find_battlefield_item(resolved["itemId"])
        self.assertTrue(session.rules_item_is_protected(protected, "p1"))
        self.assertEqual(effects[0]["target"]["itemId"], protected["id"])

    def test_mirrorbeast_copies_activated_passive_and_entry_effects(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index(
            "confrontation_reaction"
        )
        session.card_rules["mirror"] = {
            "type": "manifestation", "power": 1,
            "triggeredAbilities": [],
        }
        session.card_rules["copied"] = {
            "type": "manifestation", "power": 4, "persist": True,
            "passiveEffects": [{"kind": "float_with_counter", "counter": "Copy"}],
            "triggeredAbilities": [{
                "id": "copied-entry-draw",
                "trigger": {"event": "enters_field"},
                "result": {"kind": "draw_owner", "value": 1},
            }],
            "activatedAbilities": [{
                "id": "copied-boost",
                "targets": {
                    "min": 1, "max": 1,
                    "cardType": "manifestation",
                },
                "ongoingEffect": {
                    "kind": "power_modifier",
                    "value": 2,
                    "duration": "until_end_of_turn",
                },
            }],
        }
        mirror = {
            "id": "mirror", "ownerId": "p1", "cardId": "mirror",
            "faceUp": True, "fieldZone": "confrontation",
            "counters": {"Copy": 1},
        }
        copied = {
            "id": "copied", "ownerId": "p2", "cardId": "copied",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield = [mirror, copied]
        action = {
            "id": "copy-action",
            "controllerId": "p1",
            "source": {
                "cardId": "mirror", "itemId": "mirror",
                "ownerId": "p1",
            },
            "targets": [{
                "kind": "card", "itemId": "copied",
                "cardId": "copied", "ownerId": "p2",
            }],
            "ability": {
                "id": "copy",
                "ongoingEffect": {
                    "kind": "copy_power_effects",
                    "duration": "until_resolution",
                },
            },
        }
        effect = session.create_rules_ongoing_effects(action)[0]
        effective = session.rules_item_card_rules(mirror)
        self.assertTrue(effective["persist"])
        self.assertEqual(
            effective["activatedAbilities"][0]["id"], "copied-boost"
        )
        self.assertTrue(session.rules_item_has_float(mirror))
        self.assertEqual(
            session.rules_manifestation_characteristics(mirror)["power"], 4
        )

        self.fill_deck(p1, ["m-3"])
        copied_entry = session.queue_rules_copied_entry_triggers(effect)
        self.assertEqual(len(copied_entry), 1)
        session.queue_rules_simultaneous_actions(copied_entry)
        session.pass_rules_priority("p2")
        session.pass_rules_priority("p1")
        self.assertEqual(p1["zones"]["hand"], ["m-3"])

        session.rules_engine["priorityPlayerId"] = "p1"
        error, _action = session.declare_rules_action(
            "p1", "Copied boost", kind="activated_effect",
            source={
                "cardId": "mirror", "zone": "battlefield",
                "itemId": "mirror",
            },
            targets=[{
                "kind": "card", "itemId": "mirror", "cardId": "mirror",
            }],
            ability_id="copied-boost",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        session.pass_rules_priority("p1")
        self.assertEqual(
            session.rules_manifestation_characteristics(mirror)["power"], 6
        )

    def test_world_spore_pays_tribute_from_interzone_at_two_power(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index(
            "confrontation_reaction"
        )
        session.card_rules["spore"] = {
            "type": "manifestation", "power": 1,
            "temperaments": ["phlegmatic"],
            "tributeTemperaments": ["phlegmatic"],
            "canPayTributeFromInterzone": True,
            "interzoneTributePower": 2,
        }
        session.card_rules["will-persistent"]["powerCost"] = "{G}{G}"
        p1["zones"]["hand"] = ["will-persistent"]
        p1["zoneOwners"]["hand"] = {"will-persistent": "p1"}
        session.battlefield = [{
            "id": "spore-field", "ownerId": "p1", "cardId": "spore",
            "faceUp": True, "fieldZone": "interzone", "counters": {},
        }]

        error, action = session.declare_rules_action(
            "p1", "Play Will", kind="play_card",
            source={"cardId": "will-persistent", "zone": "hand"},
            payment_card_ids=["battlefield|spore-field"],
        )

        self.assertIsNone(error)
        self.assertEqual(action["cost"]["tributeCardIds"], ["spore"])
        self.assertEqual(
            action["cost"]["tributeMovements"][0]["fromZone"], "interzone"
        )
        self.assertIsNone(session.find_battlefield_item("spore-field"))
        self.assertEqual(p1["zones"]["graveyard"], ["spore"])

    def test_hand_and_interzone_activations_can_grant_support(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index(
            "confrontation_reaction"
        )
        support_ability = {
            "id": "gain-support",
            "sourceZones": ["hand", "battlefield"],
            "sourceFieldZone": "interzone",
            "loseScore": 10,
            "targets": {"min": 0, "max": 0},
            "result": {"kind": "grant_source_support_until_end_turn"},
        }
        session.card_rules["giant"] = {
            "type": "manifestation", "power": 3,
            "activatedAbilities": [support_ability],
        }
        p1["score"] = 40
        p1["zones"]["hand"] = ["giant"]
        p1["zoneOwners"]["hand"] = {"giant": "p1"}

        error, _action = session.declare_rules_action(
            "p1", "Gain Support", kind="activated_effect",
            source={"cardId": "giant", "zone": "hand"},
            ability_id="gain-support",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        session.pass_rules_priority("p1")
        self.assertEqual(p1["score"], 30)
        self.assertTrue(
            session.rules_support_from_hand_available("p1", "giant")
        )

        session.card_rules["chobariki"] = {
            "type": "manifestation", "power": 2,
            "activatedAbilities": [{
                "id": "essence-support",
                "sourceFieldZone": "interzone",
                "essenceCost": "{G}",
                "targets": {"min": 0, "max": 0},
                "result": {
                    "kind": "grant_source_support_until_end_turn"
                },
            }],
        }
        source = {
            "id": "chobariki-field", "ownerId": "p1",
            "cardId": "chobariki", "faceUp": True,
            "fieldZone": "interzone", "counters": {},
        }
        session.battlefield = [source]
        session.tokens = [{
            "id": "green-essence", "ownerId": "p1",
            "isEssence": True, "isNeutralCounter": False,
            "temperament": "phlegmatic", "counters": {"essence": 1},
        }]
        session.rules_engine["priorityPlayerId"] = "p1"
        error, _action = session.declare_rules_action(
            "p1", "Gain Support", kind="activated_effect",
            source={
                "cardId": "chobariki", "zone": "battlefield",
                "itemId": "chobariki-field",
            },
            ability_id="essence-support",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        session.pass_rules_priority("p1")
        self.assertEqual(session.tokens, [])
        self.assertEqual(
            source["supportUntilTurn"], session.phase_tracker["turn"]
        )

    def test_chobariki_rewards_owner_on_loss_and_returns_after_win(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["chobariki"] = {
            "type": "manifestation", "power": 2,
            "triggeredAbilities": [{
                "id": "owner-score",
                "trigger": {
                    "event": "loses_confrontation",
                    "sourceController": "not_owner",
                },
                "result": {
                    "kind": "score_source_owner", "value": 10
                },
            }, {
                "id": "return-owner-deck",
                "trigger": {
                    "event": "wins_confrontation",
                    "sourceController": "not_owner",
                },
                "result": {
                    "kind": "move_source_to_owner_deck_top"
                },
            }],
        }
        item = {
            "id": "chobariki", "ownerId": "p1",
            "controllerId": "p2", "cardId": "chobariki",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield = [item]
        session.rules_engine["confrontationResult"] = {
            "turn": session.phase_tracker["turn"],
            "winnerId": "p1", "loserId": "p2",
            "participantItemIds": ["chobariki"],
        }

        actions = session.queue_rules_confrontation_win_triggers()
        self.assertEqual(len(actions), 1)
        session.pass_rules_priority("p1")
        session.pass_rules_priority("p2")
        self.assertEqual(p1["score"], 10)

        session.rules_engine["confrontationResult"] = {
            "turn": session.phase_tracker["turn"],
            "winnerId": "p2", "loserId": "p1",
            "participantItemIds": ["chobariki"],
        }
        session.rules_engine["priorityPlayerId"] = "p2"
        actions = session.queue_rules_confrontation_win_triggers()
        self.assertEqual(len(actions), 1)
        session.pass_rules_priority("p1")
        session.pass_rules_priority("p2")
        self.assertIsNone(session.find_battlefield_item("chobariki"))
        self.assertEqual(p1["zones"]["deck"][0], "chobariki")

    def test_gusted_nebula_orders_support_returns_and_boosts_firsts(self):
        session, p1, _p2 = self.make_session()
        for card_id in ("support-a", "support-b", "first"):
            session.card_rules[card_id] = {
                "type": "manifestation", "power": 1,
                "temperaments": ["phlegmatic"],
            }
        first = {
            "id": "first", "ownerId": "p1", "cardId": "first",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        support_a = {
            "id": "support-a", "ownerId": "p1", "cardId": "support-a",
            "faceUp": True, "fieldZone": "confrontation",
            "isSupport": True, "counters": {},
        }
        support_b = {
            "id": "support-b", "ownerId": "p1", "cardId": "support-b",
            "faceUp": True, "fieldZone": "confrontation",
            "isSupport": True, "counters": {},
        }
        session.battlefield = [first, support_a, support_b]
        session.rules_engine["firstManifestationItemIds"] = {"p1": "first"}
        action = {
            "id": "gusted-action", "controllerId": "p1",
            "source": {"cardId": "gusted"},
            "ability": {
                "id": "gusted",
                "result": {
                    "kind": "return_supports_and_boost_firsts"
                },
            },
        }

        result = session.apply_rules_action_result(action)
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(result["choiceKind"], "support_return_order")
        error, ordered = session.resolve_rules_choice(
            "p1", choice["id"], ["support-a", "support-b"]
        )

        self.assertIsNone(error)
        self.assertEqual(ordered["status"], "completed")
        self.assertEqual(p1["zones"]["deck"][:2], [
            "support-a", "support-b",
        ])
        self.assertEqual(
            session.rules_manifestation_characteristics(first)["power"], 3
        )

    def test_leadenshroud_reanimates_recent_discard_with_win_exile(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index(
            "confrontation_reaction"
        )
        session.card_rules["leadenshroud"] = {
            "type": "manifestation", "power": 1,
            "activatedAbilities": [{
                "id": "reanimate",
                "sourceFieldZone": "interzone",
                "sacrificeSource": True,
                "targets": {
                    "kind": "zone_card", "min": 1, "max": 1,
                    "cardType": "manifestation",
                    "zones": ["graveyard"],
                    "enteredThisTurn": True,
                    "limboReasons": ["destroy", "discard"],
                },
                "result": {
                    "kind": "play_limbo_target_as_support",
                    "winDestination": "exile",
                },
            }],
        }
        p1["zones"]["hand"] = ["m-1"]
        p1["zoneOwners"]["hand"] = {"m-1": "p1"}
        self.assertIsNone(session.move_zone_card(
            "p1", "hand", "p1", "graveyard", "m-1"
        )[0])
        session.battlefield = [{
            "id": "leadenshroud", "ownerId": "p1",
            "cardId": "leadenshroud", "faceUp": True,
            "fieldZone": "interzone", "counters": {},
        }]

        error, _action = session.declare_rules_action(
            "p1", "Reanimate", kind="activated_effect",
            source={
                "cardId": "leadenshroud", "zone": "battlefield",
                "itemId": "leadenshroud",
            },
            targets=[{
                "kind": "zone_card", "containerId": "p1",
                "zone": "graveyard", "cardId": "m-1",
            }],
            ability_id="reanimate",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        session.pass_rules_priority("p1")
        revived = next(
            item for item in session.battlefield
            if item.get("cardId") == "m-1"
        )
        self.assertTrue(revived["isSupport"])
        self.assertEqual(revived["supportWinDestination"], "exile")
        self.assertEqual(revived["controllerId"], "p1")

    def test_cirrocumulus_stormmace_and_lugione_resolve_shared_primitives(self):
        session, p1, _p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index(
            "confrontation_reaction"
        )
        target_action = {
            "id": "controlled-effect", "controllerId": "p1",
            "kind": "triggered_effect",
            "source": {"cardId": "m-1", "ownerId": "p1"},
            "targets": [],
            "ability": {
                "id": "score",
                "result": {"kind": "score_owner", "value": 5},
            },
            "cost": {},
        }
        cirro = {
            "id": "cirro", "ownerId": "p1", "cardId": "cirro",
            "faceUp": True, "fieldZone": "interzone", "counters": {},
        }
        session.card_rules["cirro"] = {
            "type": "manifestation",
            "activatedAbilities": [{
                "id": "resolve",
                "sourceFieldZone": "interzone",
                "sacrificeSource": True,
                "targets": {
                    "kind": "stack_item", "min": 1, "max": 1,
                    "controller": "self",
                },
                "result": {
                    "kind": "resolve_target_stack_immediately"
                },
            }],
        }
        session.battlefield = [cirro]
        session.rules_engine["actionStack"] = [target_action]
        session.rules_engine["priorityPlayerId"] = "p1"
        error, _action = session.declare_rules_action(
            "p1", "Resolve now", kind="activated_effect",
            source={
                "cardId": "cirro", "zone": "battlefield",
                "itemId": "cirro",
            },
            targets=[{
                "kind": "stack_item", "actionId": "controlled-effect",
                "cardId": "m-1",
            }],
            ability_id="resolve",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        session.pass_rules_priority("p1")
        self.assertEqual(p1["score"], 5)
        self.assertEqual(session.rules_engine["actionStack"], [])

        first = {
            "id": "first", "ownerId": "p1", "cardId": "m-2",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        storm = {
            "id": "storm", "ownerId": "p1", "cardId": "storm",
            "faceUp": True, "fieldZone": "interzone", "counters": {},
        }
        session.card_rules["storm"] = {
            "type": "manifestation",
            "activatedAbilities": [{
                "id": "protect",
                "sourceFieldZone": "interzone",
                "sacrificeSource": True,
                "targets": {
                    "min": 1, "max": 1,
                    "cardType": "manifestation",
                    "zones": ["battlefield"],
                    "controller": "self",
                    "firstManifestationOnly": True,
                },
                "ongoingEffects": [
                    {
                        "kind": "power_modifier", "value": 2,
                        "duration": "until_end_of_turn",
                    },
                    {
                        "kind": "protection",
                        "duration": "until_end_of_turn",
                        "fromOpponents": True,
                    },
                ],
            }],
        }
        session.battlefield = [first, storm]
        session.rules_engine["firstManifestationItemIds"] = {"p1": "first"}
        session.rules_engine["priorityPlayerId"] = "p1"
        error, _action = session.declare_rules_action(
            "p1", "Protect first", kind="activated_effect",
            source={
                "cardId": "storm", "zone": "battlefield",
                "itemId": "storm",
            },
            targets=[{
                "kind": "card", "itemId": "first",
                "cardId": "m-2", "ownerId": "p1",
            }],
            ability_id="protect",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        session.pass_rules_priority("p1")
        self.assertEqual(
            session.rules_manifestation_characteristics(first)["power"], 3
        )
        self.assertTrue(session.rules_item_is_protected(first, "p2"))

        prey = {
            "id": "prey", "ownerId": "p2", "cardId": "m-3",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        lugione = {
            "id": "lugione", "ownerId": "p1", "cardId": "lugione",
            "faceUp": True, "fieldZone": "interzone", "counters": {},
        }
        session.card_rules["m-3"]["power"] = 4
        session.card_rules["lugione"] = {
            "type": "manifestation",
            "activatedAbilities": [{
                "id": "destroy",
                "sourceFieldZone": "interzone",
                "sacrificeSource": True,
                "targets": {
                    "min": 1, "max": 1,
                    "cardType": "manifestation",
                    "zones": ["battlefield"],
                    "minPower": 4,
                },
                "result": {
                    "kind": "move_target", "zone": "graveyard",
                    "position": "top", "reason": "destroy",
                },
            }],
        }
        session.battlefield.extend([prey, lugione])
        session.rules_engine["priorityPlayerId"] = "p1"
        error, _action = session.declare_rules_action(
            "p1", "Destroy prey", kind="activated_effect",
            source={
                "cardId": "lugione", "zone": "battlefield",
                "itemId": "lugione",
            },
            targets=[{
                "kind": "card", "itemId": "prey",
                "cardId": "m-3", "ownerId": "p2",
            }],
            ability_id="destroy",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        session.pass_rules_priority("p1")
        self.assertIn("m-3", session.players["p2"]["zones"]["graveyard"])
        self.assertTrue(any(
            entry["cardId"] == "m-3" and entry["reason"] == "destroy"
            for entry in session.rules_engine["recentLimboEntries"]
        ))

    def test_bakato_permission_and_haltan_point_prevention(self):
        session, p1, p2 = self.make_session()
        session.card_rules["bakato"] = {
            "type": "manifestation", "power": 1,
            "playPermissions": [{
                "id": "bakato-limbo",
                "playPermission": {
                    "conditionEvent": "beginning_of_turn",
                    "requiredZone": "graveyard",
                    "playFromZone": "graveyard",
                    "phaseIds": ["confrontation_reaction"],
                    "asSupport": True,
                    "winAsSupportDestination": "exile",
                },
            }],
        }
        p1["zones"]["graveyard"] = ["bakato"]
        p1["zoneOwners"]["graveyard"] = {"bakato": "p1"}
        session.grant_rules_beginning_turn_permissions()
        session.phase_tracker["index"] = ADVANCED_PHASES.index(
            "confrontation_reaction"
        )
        error, _action = session.declare_rules_action(
            "p1", "Play Bakato", kind="play_card",
            source={
                "cardId": "bakato", "zone": "graveyard",
                "containerId": "p1",
            },
            as_support=True,
            placement={"x": 10, "y": 20},
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        session.pass_rules_priority("p1")
        bakato = next(
            item for item in session.battlefield
            if item.get("cardId") == "bakato"
        )
        self.assertEqual(bakato["supportWinDestination"], "exile")

        haltan = {
            "id": "haltan", "ownerId": "p1", "cardId": "haltan",
            "faceUp": True, "fieldZone": "confrontation",
            "rotation": 0, "counters": {},
        }
        session.card_rules["haltan"] = {
            "type": "manifestation",
            "activatedAbilities": [{
                "id": "change-score", "exhaustSource": True,
                "targets": {"kind": "player", "min": 1, "max": 1},
                "result": {
                    "kind": "choose_target_score_delta", "value": 10
                },
            }, {
                "id": "prevent-score", "exhaustSource": True,
                "sacrificeSource": True, "immediate": True,
                "targets": {"min": 0, "max": 0},
                "ongoingEffect": {
                    "kind": "prevent_point_changes",
                    "duration": "until_end_of_turn",
                    "scope": "global",
                },
            }],
        }
        session.battlefield.append(haltan)
        session.rules_engine["priorityPlayerId"] = "p1"
        error, _action = session.declare_rules_action(
            "p1", "Change score", kind="activated_effect",
            source={
                "cardId": "haltan", "zone": "battlefield",
                "itemId": "haltan",
            },
            targets=[{"kind": "player", "playerId": "p2"}],
            ability_id="change-score",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        session.pass_rules_priority("p1")
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "score_delta_choice")
        self.assertIsNone(session.resolve_rules_choice(
            "p1", choice["id"], option="lose"
        )[0])
        self.assertEqual(p2["score"], -10)

        haltan["rotation"] = 0
        session.rules_engine["priorityPlayerId"] = "p1"
        error, _action = session.declare_rules_action(
            "p1", "Prevent score", kind="activated_effect",
            source={
                "cardId": "haltan", "zone": "battlefield",
                "itemId": "haltan",
            },
            ability_id="prevent-score",
        )
        self.assertIsNone(error)
        immediate = session.resolve_rules_immediate_actions()
        self.assertEqual(len(immediate), 1)
        self.assertTrue(session.rules_points_changes_prevented())
        score_result = session.apply_rules_action_result({
            "controllerId": "p1",
            "source": {"cardId": "m-1"},
            "ability": {
                "result": {"kind": "score_owner", "value": 10}
            },
        })
        self.assertEqual(score_result["delta"], 0)
        self.assertEqual(p1["score"], 0)

    def test_simple_watchers_draw_score_shuffle_and_create_essence(self):
        session, p1, p2 = self.make_session()
        self.fill_deck(p1, ["m-3", "m-4"])
        callus = {
            "id": "callus", "ownerId": "p1", "cardId": "callus",
            "faceUp": True, "fieldZone": "interzone", "counters": {},
        }
        cannon = {
            "id": "cannon", "ownerId": "p1", "cardId": "cannon",
            "faceUp": True, "fieldZone": "field", "counters": {},
        }
        forager = {
            "id": "forager", "ownerId": "p1", "cardId": "forager",
            "faceUp": True, "fieldZone": "field", "counters": {},
        }
        session.card_rules["callus"] = {
            "type": "manifestation",
            "triggeredAbilities": [{
                "id": "draw", "trigger": {
                    "event": "will_played", "eventController": "owner",
                    "zone": "interzone",
                },
                "result": {"kind": "draw_owner", "value": 1},
            }],
        }
        session.card_rules["cannon"] = {
            "type": "persistent_will",
            "triggeredAbilities": [{
                "id": "punish",
                "trigger": {
                    "event": "will_played",
                    "target": "event_controller",
                },
                "targets": {
                    "kind": "player", "min": 1, "max": 1,
                },
                "result": {"kind": "score_target", "value": -5},
            }],
        }
        session.card_rules["forager"] = {
            "type": "persistent_will",
            "triggeredAbilities": [{
                "id": "essence",
                "trigger": {
                    "event": "beginning_of_turn", "zone": "field",
                },
                "result": {
                    "kind": "create_essence",
                    "temperament": "transcendent", "value": 1,
                },
            }],
        }
        session.battlefield = [callus, cannon, forager]

        actions = []
        for item in (callus, cannon):
            actions.extend(session.queue_rules_triggers(
                item["cardId"], item["ownerId"], "will_played",
                item_id=item["id"], event_controller_id="p1",
                controller_id="p1", defer=True,
            ))
        session.queue_rules_simultaneous_actions(actions)
        order_choice = session.rules_engine["pendingChoice"]
        self.assertIsNone(session.resolve_rules_choice(
            "p1", order_choice["id"],
            [action["id"] for action in actions],
        )[0])
        while session.rules_engine["actionStack"]:
            priority = session.rules_engine["priorityPlayerId"]
            session.pass_rules_priority(priority)
            session.pass_rules_priority(
                session.rules_engine["priorityPlayerId"]
            )
        self.assertEqual(p1["zones"]["hand"], ["m-3"])
        self.assertEqual(p1["score"], -5)

        essence_action = session.queue_rules_triggers(
            "forager", "p1", "beginning_of_turn",
            zone="field", item_id="forager", controller_id="p1",
        )[0]
        session.rules_engine["actionStack"] = []
        result = session.apply_rules_action_result(essence_action)
        self.assertEqual(result["temperament"], "transcendent")
        self.assertEqual(session.tokens[0]["counters"]["essence"], 1)

        session.card_rules["crickelob"] = {
            "type": "manifestation",
            "triggeredAbilities": [{
                "id": "shuffle",
                "trigger": {"event": "used_as_tribute"},
                "result": {"kind": "shuffle_owner_deck"},
            }],
        }
        with patch("session.random.shuffle") as shuffle:
            action = session.queue_rules_triggers(
                "crickelob", "p1", "used_as_tribute",
                container_id="p1", defer=True,
            )[0]
            shuffled = session.apply_rules_action_result(action)
        self.assertEqual(shuffled["status"], "shuffled")
        shuffle.assert_called_once_with(p1["zones"]["deck"])
        self.assertEqual(p2["score"], 0)

    def test_simple_zone_moves_to_hand_and_interzone(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["recover"] = {
            "type": "ephemeral_will",
            "playedAbilities": [{
                "id": "recover", "action": "play_card",
                "targets": {
                    "kind": "zone_card", "min": 1, "max": 1,
                    "zones": ["graveyard"], "owner": "self",
                },
                "result": {
                    "kind": "move_target", "zone": "hand",
                    "position": "top", "reason": "return",
                },
            }],
        }
        session.card_rules["revive"] = {
            "type": "ephemeral_will",
            "playedAbilities": [{
                "id": "revive", "action": "play_card",
                "targets": {
                    "kind": "zone_card", "min": 1, "max": 1,
                    "cardType": "manifestation",
                    "zones": ["graveyard"], "owner": "self",
                },
                "result": {
                    "kind": "move_zone_target_to_field_zone",
                    "fieldZone": "interzone",
                },
            }],
        }
        p1["zones"]["graveyard"] = ["m-1", "m-2"]
        p1["zoneOwners"]["graveyard"] = {"m-1": "p1", "m-2": "p1"}

        recovered = session.apply_rules_action_result({
            "controllerId": "p1",
            "targets": [{
                "kind": "zone_card", "containerId": "p1",
                "zone": "graveyard", "cardId": "m-1",
                "ownerId": "p1",
            }],
            "ability": {
                "result": {
                    "kind": "move_target", "zone": "hand",
                    "position": "top", "reason": "return",
                },
            },
        })
        self.assertEqual(recovered["status"], "moved")
        self.assertEqual(p1["zones"]["hand"], ["m-1"])

        revived = session.apply_rules_action_result({
            "controllerId": "p1",
            "targets": [{
                "kind": "zone_card", "containerId": "p1",
                "zone": "graveyard", "cardId": "m-2",
                "ownerId": "p1",
            }],
            "ability": {
                "result": {
                    "kind": "move_zone_target_to_field_zone",
                    "fieldZone": "interzone",
                },
            },
        })
        self.assertEqual(revived["status"], "moved")
        self.assertEqual(
            session.find_battlefield_item(revived["itemId"])["fieldZone"],
            "interzone",
        )

        p1["zones"]["hand"].append("m-3")
        p1["zoneOwners"]["hand"]["m-3"] = "p1"
        hidden = session.apply_rules_action_result({
            "controllerId": "p1",
            "targets": [{
                "kind": "zone_card", "containerId": "p1",
                "zone": "hand", "cardId": "m-3", "ownerId": "p1",
            }],
            "ability": {
                "result": {
                    "kind": "move_zone_target_to_field_zone",
                    "fieldZone": "interzone",
                },
            },
        })
        self.assertEqual(hidden["status"], "moved")
        self.assertNotIn("m-3", p1["zones"]["hand"])

    def test_simple_copy_and_support_grant_results(self):
        session, _p1, _p2 = self.make_session()
        target = {
            "id": "target", "ownerId": "p1", "cardId": "m-1",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        interzone = {
            "id": "interzone", "ownerId": "p1", "cardId": "m-2",
            "faceUp": True, "fieldZone": "interzone", "counters": {},
        }
        session.battlefield = [target, interzone]

        copied = session.apply_rules_action_result({
            "controllerId": "p1",
            "source": {"cardId": "mirror"},
            "targets": [{
                "kind": "card", "itemId": "target",
                "cardId": "m-1", "ownerId": "p1",
            }],
            "ability": {
                "result": {
                    "kind": "create_target_token_copy_in_support"
                },
            },
        })
        copy = session.find_battlefield_item(copied["createdItemId"])
        self.assertTrue(copy["isCopy"])
        self.assertTrue(copy["isSupport"])

        granted = session.apply_rules_action_result({
            "controllerId": "p1",
            "source": {"cardId": "unite"},
            "ability": {
                "result": {
                    "kind":
                    "grant_friendly_interzone_support_until_end_turn"
                },
            },
        })
        self.assertEqual(granted["itemIds"], ["interzone"])
        self.assertEqual(
            interzone["supportUntilTurn"], session.phase_tracker["turn"]
        )

    def test_simple_continuous_power_rules_use_live_zone_counts(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["monument"] = {
            "type": "persistent_will",
            "continuousPowerRules": [{
                "kind": "friendly_confrontation_flat", "value": 1,
            }],
        }
        session.card_rules["tipson"] = {
            "type": "manifestation", "power": 1,
            "continuousPowerRules": [{
                "kind": "self_per_controller_hand_card", "value": 1,
            }],
        }
        session.card_rules["beak"] = {
            "type": "manifestation", "power": 4,
            "continuousPowerRules": [{
                "kind": "self_per_stalemate_manifestation", "value": 1,
            }],
        }
        session.card_rules["urn"] = {
            "type": "manifestation", "power": 1,
            "continuousPowerRules": [{
                "kind": "self_per_controller_limbo_manifestation",
                "value": 1,
            }],
        }
        monument = {
            "id": "monument", "ownerId": "p1", "cardId": "monument",
            "faceUp": True, "fieldZone": "field", "counters": {},
        }
        tipson = {
            "id": "tipson", "ownerId": "p1", "cardId": "tipson",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        beak = {
            "id": "beak", "ownerId": "p1", "cardId": "beak",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        urn = {
            "id": "urn", "ownerId": "p1", "cardId": "urn",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        stalemate = {
            "id": "stalemate", "ownerId": "p2", "cardId": "m-5",
            "faceUp": True, "fieldZone": "stalemate", "counters": {},
        }
        session.battlefield = [monument, tipson, beak, urn, stalemate]
        p1["zones"]["hand"] = ["m-6", "m-7"]
        p1["zoneOwners"]["hand"] = {"m-6": "p1", "m-7": "p1"}
        p1["zones"]["graveyard"] = ["m-8", "will-ephemeral"]
        p1["zoneOwners"]["graveyard"] = {
            "m-8": "p1", "will-ephemeral": "p1",
        }

        self.assertEqual(
            session.rules_manifestation_characteristics(tipson)["power"], 4
        )
        self.assertEqual(
            session.rules_manifestation_characteristics(beak)["power"], 6
        )
        self.assertEqual(
            session.rules_manifestation_characteristics(urn)["power"], 3
        )

    def test_cleanse_restores_base_card_but_preserves_zone_and_counters(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["target"] = {
            "type": "manifestation", "power": 3,
            "temperaments": ["phlegmatic"],
        }
        item = {
            "id": "target", "ownerId": "p1", "controllerId": "p2",
            "cardId": "target", "faceUp": True,
            "fieldZone": "interzone", "isSupport": True,
            "rotation": 90, "counters": {"power": 2, "Atavic": 3},
            "effectsDisabled": True, "zeroPowerSustained": True,
            "temperamentOverride": "choleric",
            "supportUntilTurn": session.phase_tracker["turn"],
            "hasFloat": True, "supportWinDestination": "exile",
        }
        session.battlefield = [item]
        session.rules_engine["ongoingEffects"] = [{
            "id": "power-effect", "kind": "power_modifier",
            "source": {"itemId": "other"},
            "target": {"kind": "card", "itemId": "target"},
            "duration": "until_end_of_turn", "value": 4,
        }, {
            "id": "copy-effect", "kind": "copy_power_effects",
            "source": {"itemId": "target"},
            "target": {"kind": "card", "itemId": "other"},
            "duration": "until_end_of_turn",
        }]

        result = session.apply_rules_action_result({
            "controllerId": "p1",
            "targets": [{
                "kind": "card", "itemId": "target",
                "cardId": "target", "ownerId": "p1",
            }],
            "ability": {"result": {"kind": "cleanse_target"}},
        })

        self.assertEqual(result["status"], "cleansed")
        self.assertEqual(item["fieldZone"], "interzone")
        self.assertTrue(item["isSupport"])
        self.assertEqual(item["rotation"], 90)
        self.assertEqual(item["counters"], {"power": 2, "Atavic": 3})
        self.assertEqual(item["controllerId"], "p1")
        self.assertNotIn("effectsDisabled", item)
        self.assertNotIn("temperamentOverride", item)
        self.assertNotIn("supportUntilTurn", item)
        self.assertNotIn("hasFloat", item)
        self.assertNotIn("supportWinDestination", item)
        self.assertEqual(session.rules_engine["ongoingEffects"], [])
        self.assertEqual(
            session.rules_manifestation_characteristics(item),
            {"power": 5, "temperament": "phlegmatic"},
        )

    def test_support_entry_batch_uses_reusable_trigger_scopes_and_token_result(self):
        abilities = json.loads(
            (Path(__file__).resolve().parent.parent / "public" / "card-abilities.json")
            .read_text(encoding="utf-8")
        )
        session, _p1, _p2 = self.make_session()
        card_powers = {
            "l6ragmkyw5oyued_en": 2,
            "ypvac71teuck2za_en": 3,
            "inner-deserts-002": 1,
            "inner-deserts-005": 2,
            "inner-deserts-079": 2,
            "friendly": 4,
            "opposing": 5,
        }
        for card_id, power in card_powers.items():
            session.card_rules[card_id] = {
                "type": "manifestation", "power": power,
                "temperaments": ["phlegmatic"],
                "triggeredAbilities": abilities.get(card_id, []),
            }

        friendly_presence = {
            "id": "friendly-presence", "ownerId": "p1",
            "controllerId": "p1", "cardId": "l6ragmkyw5oyued_en",
            "faceUp": True, "fieldZone": "confrontation", "counters": {},
        }
        friendly = {
            "id": "friendly", "ownerId": "p1", "controllerId": "p1",
            "cardId": "friendly", "faceUp": True,
            "fieldZone": "confrontation", "counters": {},
        }
        opposing = {
            "id": "opposing", "ownerId": "p2", "controllerId": "p2",
            "cardId": "opposing", "faceUp": True,
            "fieldZone": "confrontation", "counters": {},
        }
        session.battlefield = [friendly_presence, friendly, opposing]
        entry_actions = session.queue_rules_field_zone_entry_triggers(
            friendly_presence, "confrontation", defer=True,
        )
        self.assertEqual(len(entry_actions), 1)
        effects = session.create_rules_ongoing_effects(entry_actions[0])
        self.assertEqual([effect["target"]["itemId"] for effect in effects], ["opposing"])
        self.assertEqual(session.rules_manifestation_characteristics(friendly)["power"], 4)
        self.assertEqual(session.rules_manifestation_characteristics(opposing)["power"], 3)

        worn = {
            "id": "worn", "ownerId": "p1", "controllerId": "p1",
            "cardId": "ypvac71teuck2za_en", "faceUp": True,
            "fieldZone": "confrontation", "isSupport": True, "counters": {},
        }
        session.battlefield = [worn]
        self.assertEqual(session.queue_rules_support_entry_triggers(
            worn, played=True, from_zone="hand", defer=True,
        ), [])
        worn_actions = session.queue_rules_support_entry_triggers(
            worn, played=True, from_zone="interzone", defer=True,
        )
        self.assertEqual(len(worn_actions), 1)
        session.create_rules_ongoing_effects(worn_actions[0])
        self.assertEqual(session.rules_manifestation_characteristics(worn)["power"], 2)

        manibirbo = {
            "id": "manibirbo", "ownerId": "p1", "controllerId": "p1",
            "cardId": "inner-deserts-005", "faceUp": True,
            "fieldZone": "confrontation", "isSupport": True, "counters": {},
        }
        session.battlefield = [manibirbo]
        manibirbo_actions = session.queue_rules_support_entry_triggers(
            manibirbo, played=True, from_zone="hand", defer=True,
        )
        self.assertEqual(len(manibirbo_actions), 1)
        session.create_rules_ongoing_effects(manibirbo_actions[0])
        self.assertEqual(session.rules_confrontation_power(manibirbo), 0)

        pegasso = {
            "id": "pegasso", "ownerId": "p1", "controllerId": "p1",
            "cardId": "inner-deserts-079", "faceUp": True,
            "fieldZone": "confrontation", "isSupport": True, "counters": {},
        }
        session.battlefield = [pegasso]
        pegasso_actions = session.queue_rules_field_zone_entry_triggers(
            pegasso, "confrontation", defer=True,
        )
        self.assertEqual(len(pegasso_actions), 1)
        session.create_rules_ongoing_effects(pegasso_actions[0])
        self.assertEqual(session.rules_manifestation_characteristics(pegasso)["power"], 3)
        pegasso_win_actions = session.queue_rules_triggers(
            pegasso["cardId"], "p1", "wins_confrontation",
            item_id=pegasso["id"], event_controller_id="p1",
            controller_id="p1", defer=True,
        )
        self.assertEqual(len(pegasso_win_actions), 1)
        pegasso_exile = session.apply_rules_action_result(pegasso_win_actions[0])
        self.assertEqual(pegasso_exile["movement"]["zone"], "exile")
        self.assertIn(pegasso["cardId"], session.players["p1"]["zones"]["exile"])

        buuz = {
            "id": "buuz", "ownerId": "p1", "controllerId": "p1",
            "cardId": "inner-deserts-002", "faceUp": True,
            "fieldZone": "confrontation", "isSupport": True, "counters": {},
        }
        session.battlefield = [buuz]
        buuz_actions = session.queue_rules_battlefield_entry_triggers(
            buuz["cardId"], "p1", buuz["id"], True, defer=True,
        )
        self.assertEqual(len(buuz_actions), 1)
        created = session.apply_rules_action_result(buuz_actions[0])
        token = session.find_battlefield_item(created["createdItemId"])
        self.assertTrue(token["isTokenCard"])
        self.assertTrue(token["isSupport"])
        self.assertEqual(token["power"], 1)
        self.assertEqual(token["temperament"], "phlegmatic")
        self.assertEqual(token["createdByItemId"], "buuz")


class ConfrontationOutcomePilotTests(unittest.TestCase):
    """Cards whose printed text reacts to winning or losing a Confrontation.

    The abilities come straight from public/card-abilities.json so the
    shipped encoding, not a hand-copied one, is what gets exercised.
    """

    ABILITIES = json.loads(
        (Path(__file__).resolve().parent.parent / "public" / "card-abilities.json")
        .read_text(encoding="utf-8")
    )
    SOLENERO = "icxqhki0ivfgqu0_en"
    SALLOW_THIEF = "rgjdtrcaw4o9381_en"
    KNOBBLY = "o1b1hf2xpmkt8j2_en"
    BOROMBO = "70wsdfb29mmcsqf_en"
    TARDIGRAMO = "mxbi84phhueeolc_en"
    DANCER = "fr1414jedqssttr_en"

    def make_session(self, *source_card_ids):
        manifestation_ids = {f"m-{index}" for index in range(20)}
        card_rules = {
            card_id: {"type": "manifestation", "power": 1, "temperaments": ["phlegmatic"]}
            for card_id in manifestation_ids
        }
        card_rules["field-will"] = {"type": "persistent_will", "cost": 1}
        for card_id in source_card_ids:
            card_rules[card_id] = {
                "type": "manifestation", "power": 3,
                "triggeredAbilities": [
                    ability for ability in self.ABILITIES[card_id]
                    if ability.get("trigger")
                ],
            }
        session = Session(
            rules_beta=True, card_points={}, manifestation_ids=manifestation_ids,
            card_rules=card_rules,
        )
        p1 = session.get_or_create_player("p1", "P1", seat=0)
        p2 = session.get_or_create_player("p2", "P2", seat=1)
        session.rules_engine["deckConfirmedPlayerIds"] = ["p1", "p2"]
        session.phase_tracker["index"] = 1
        return session, p1, p2

    @staticmethod
    def put(player, zone, cards):
        owners = cards if isinstance(cards, dict) else {card_id: player["id"] for card_id in cards}
        player["zones"][zone] = list(owners)
        player["zoneOwners"][zone] = dict(owners)

    @staticmethod
    def field_item(item_id, owner_id, card_id, field_zone="confrontation", **extra):
        return {
            "id": item_id, "ownerId": owner_id, "cardId": card_id,
            "faceUp": True, "fieldZone": field_zone, "counters": {}, **extra,
        }

    @staticmethod
    def set_outcome(session, winner_id, loser_id, *item_ids):
        session.rules_engine["confrontationResult"] = {
            "turn": session.phase_tracker["turn"],
            "winnerId": winner_id, "loserId": loser_id,
            "participantItemIds": list(item_ids),
        }

    def accept_and_target(self, session, player_id, targets):
        choice = session.rules_engine["pendingChoice"]
        if choice["kind"] == "optional_stack_action":
            self.assertIsNone(session.resolve_rules_choice(
                player_id, choice["id"], option="accept"
            )[0])
            choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "trigger_targets")
        return session.resolve_rules_choice(player_id, choice["id"], targets=targets)

    @staticmethod
    def resolve_stack(session):
        session.pass_rules_priority("p2")
        session.pass_rules_priority("p1")

    def test_blue_entity_buffs_other_friendly_confrontation_manifestations_on_own_will(self):
        session, p1, p2 = self.make_session("nbms08jb9t9eqbh_en")
        session.card_rules["will-x"] = {"type": "ephemeral_will"}
        session.battlefield = [
            self.field_item("blue", "p1", "nbms08jb9t9eqbh_en"),
            self.field_item("ally", "p1", "m-1"),
            self.field_item("ally-int", "p1", "m-2", field_zone="interzone"),
            self.field_item("foe", "p2", "m-3"),
        ]

        def play_will(owner_id, n):
            action = {
                "id": f"paid-{n}", "controllerId": owner_id, "kind": "play_card",
                "source": {"cardId": "will-x", "ownerId": owner_id},
            }
            session.rules_engine["actionStack"] = [action]
            session.rules_engine["pendingChoice"] = None
            return [
                queued for queued in session.queue_rules_tribute_triggers(
                    [], owner_id, simultaneous_action_id=action["id"]
                ) if queued["source"]["cardId"] == "nbms08jb9t9eqbh_en"
            ]

        self.assertEqual(play_will("p2", 1), [])
        queued = play_will("p1", 2)
        self.assertEqual(len(queued), 1)
        session.create_rules_ongoing_effects(queued[0])
        self.assertEqual(self.power_of(session, "ally"), 2)
        self.assertEqual(self.power_of(session, "blue"), 3)
        self.assertEqual(self.power_of(session, "ally-int"), 1)
        self.assertEqual(self.power_of(session, "foe"), 1)

    def test_observer_cards_react_to_discards_point_losses_destruction_and_vessel_entries(self):
        pale, conflux, orchard = (
            "874751ghrblya5j_en", "mwby5hp16qdnjpj_en", "i6oj7gtnkfd1jja_en"
        )
        session, p1, p2 = self.make_session(pale)
        for card_id in (conflux, orchard):
            session.card_rules[card_id] = {
                "type": "persistent_will",
                "triggeredAbilities": [
                    ability for ability in self.ABILITIES[card_id]
                    if ability.get("trigger")
                ],
            }
        session.battlefield = [
            self.field_item("pale", "p1", pale, field_zone="interzone"),
            self.field_item("conflux", "p1", conflux, field_zone="field"),
            self.field_item("orchard", "p1", orchard, field_zone="field"),
            self.field_item("foe", "p2", "m-3"),
            self.field_item("mine", "p1", "m-4"),
        ]
        self.put(p2, "hand", ["m-5"])

        def flush():
            return session.queue_rules_observed_event_triggers(defer=True)

        def names(actions):
            return sorted(a["ability"]["id"] for a in actions)

        # A discard from either player: Pale gains, Conflux asks for a target.
        self.assertIsNone(session.move_zone_card("p2", "hand", "p2", "graveyard", "m-5")[0])
        queued = flush()
        self.assertEqual(
            names([a for a in queued if a["source"]["cardId"] == pale]),
            ["gain-when-player-discards"],
        )
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "trigger_targets")
        session.rules_engine["pendingChoice"] = None

        # Losing points is seen by Pale only.
        session.adjust_rules_score("p2", -5)
        queued = flush()
        self.assertEqual(names(queued), ["gain-when-player-loses-points"])
        session.adjust_rules_score("p2", 5)
        self.assertEqual(flush(), [])

        # Destroying an opponent's Manifestation pays Conflux's controller only.
        item = session.find_battlefield_item("foe")
        session._rules_remove_field_item_by_effect(
            item, "p2", "graveyard", "top", reason="destroy"
        )
        queued = flush()
        self.assertEqual(names(queued), ["gain-when-opponent-manifestation-destroyed"])
        item = session.find_battlefield_item("mine")
        session._rules_remove_field_item_by_effect(
            item, "p1", "graveyard", "top", reason="destroy"
        )
        self.assertEqual(flush(), [])

        # Orchard: only the owner's Manifestation entering the opponent's Vessel.
        session.battlefield.append(self.field_item("mine2", "p1", "m-6"))
        session._rules_remove_field_item(
            session.find_battlefield_item("mine2"), "p2", "receptacle"
        )
        self.assertEqual(
            names(flush()), ["gain-when-own-manifestation-enters-opponent-vessel"]
        )
        session.battlefield.append(self.field_item("theirs", "p2", "m-7"))
        session._rules_remove_field_item(
            session.find_battlefield_item("theirs"), "p1", "receptacle"
        )
        self.assertEqual(flush(), [])

    ATAVIC = {
        "erkwir53va9m8gm_en": ("Union", "phlegmatic"),
        "265f4wdooq43pjn_en": ("Control", "vitreous"),
        "a058t24med4h5nx_en": ("Fatigue", "melancholic"),
        "rqvzo3iji2a1l65_en": ("Coil", "capricious"),
        "m2l3v60n0iakrm2_en": ("Violence", "choleric"),
    }

    def atavic_session(self, card_id):
        session, p1, p2 = self.make_session()
        abilities = self.ABILITIES[card_id]
        session.card_rules[card_id] = {
            "type": "persistent_will", "playBeforeRevelation": True,
            "temperaments": [self.ATAVIC[card_id][1]],
            "triggeredAbilities": [a for a in abilities if a.get("trigger")],
            "activatedAbilities": [
                a for a in abilities
                if not a.get("trigger") and a.get("action") != "play_card"
            ],
        }
        item = self.field_item("atavic", "p1", card_id, field_zone="field")
        session.battlefield = [item]
        return session, p1, p2, item

    def play_card_of(self, session, owner_id, temperament, n):
        card_id = f"will-{temperament}-{n}"
        session.card_rules[card_id] = {
            "type": "ephemeral_will", "temperaments": [temperament],
        }
        action = {
            "id": f"paid-{n}", "controllerId": owner_id, "kind": "play_card",
            "source": {"cardId": card_id, "ownerId": owner_id},
        }
        session.rules_engine["actionStack"] = [action]
        session.rules_engine["pendingChoice"] = None
        return session.queue_rules_tribute_triggers(
            [], owner_id, simultaneous_action_id=action["id"]
        )

    def test_every_atavic_counts_only_own_cards_of_its_temperament(self):
        for card_id, (counter, temperament) in self.ATAVIC.items():
            session, _p1, _p2, item = self.atavic_session(card_id)
            other = "choleric" if temperament != "choleric" else "vitreous"
            for owner, played in (("p1", other), ("p2", temperament)):
                queued = [
                    a for a in self.play_card_of(session, owner, played, 1)
                    if a["source"]["cardId"] == card_id
                ]
                self.assertEqual(queued, [], (card_id, owner, played))
            queued = [
                a for a in self.play_card_of(session, "p1", temperament, 2)
                if a["source"]["cardId"] == card_id
            ]
            self.assertEqual(len(queued), 1, card_id)
            session.apply_rules_action_result(queued[0])
            self.assertEqual(item["counters"][counter], 1)

    def test_atavic_manifestations_entering_the_field_also_count(self):
        session, _p1, _p2, item = self.atavic_session("erkwir53va9m8gm_en")
        session.battlefield.append(self.field_item("entering", "p1", "m-1"))
        queued = session.queue_rules_manifestation_entry_watchers(
            session.find_battlefield_item("entering"), defer=True
        )
        self.assertEqual(
            [a["ability"]["id"] for a in queued
             if a["source"]["cardId"] == "erkwir53va9m8gm_en"],
            ["union-counter-on-own-green-card"],
        )

    def test_atavic_welcome_spends_five_unions_for_two_support_tokens(self):
        session, p1, _p2, item = self.atavic_session("erkwir53va9m8gm_en")
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
        session.rules_engine["priorityPlayerId"] = "p1"
        item["counters"]["Union"] = 4
        source = {"cardId": item["cardId"], "zone": "battlefield", "itemId": "atavic"}
        error, _action = session.declare_rules_action(
            "p1", "Union", kind="activated_effect", source=source,
            ability_id="spend-unions-for-support-tokens",
        )
        self.assertIn("5 Union counters", error)
        item["counters"]["Union"] = 6
        error, _action = session.declare_rules_action(
            "p1", "Union", kind="activated_effect", source=source,
            ability_id="spend-unions-for-support-tokens",
        )
        self.assertIsNone(error)
        self.assertEqual(item["counters"]["Union"], 1)
        session.pass_rules_priority("p2")
        session.pass_rules_priority("p1")
        tokens = [i for i in session.battlefield if i.get("isTokenCard")]
        self.assertEqual(len(tokens), 2)
        for token in tokens:
            self.assertEqual(
                (token["power"], token["temperament"], token["ownerId"]),
                (1, "phlegmatic", "p1"),
            )
            self.assertTrue(token["isSupport"])

    def test_atavic_welcome_ten_unions_pays_five_points_per_support_entry(self):
        session, p1, _p2, item = self.atavic_session("erkwir53va9m8gm_en")
        support = self.field_item("sup", "p1", "m-1", isSupport=True)
        session.battlefield.append(support)
        item["counters"]["Union"] = 9
        self.assertEqual(
            [a for a in session.queue_rules_support_entry_triggers(support, defer=True)
             if a["source"]["cardId"] == "erkwir53va9m8gm_en"], [],
        )
        item["counters"]["Union"] = 10
        queued = [
            a for a in session.queue_rules_support_entry_triggers(support, defer=True)
            if a["source"]["cardId"] == "erkwir53va9m8gm_en"
        ]
        self.assertEqual(len(queued), 1)
        session.apply_rules_action_result(queued[0])
        self.assertEqual(p1["score"], 5)

    def test_atavic_introspection_bounces_a_manifestation_and_blocks_replaying_it(self):
        session, p1, p2, item = self.atavic_session("265f4wdooq43pjn_en")
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
        session.rules_engine["priorityPlayerId"] = "p1"
        item["counters"]["Control"] = 5
        session.battlefield.append(self.field_item("foe", "p2", "m-3"))
        error, _action = session.declare_rules_action(
            "p1", "Control", kind="activated_effect",
            source={"cardId": item["cardId"], "zone": "battlefield", "itemId": "atavic"},
            targets=[{"kind": "card", "itemId": "foe", "cardId": "m-3"}],
            ability_id="spend-controls-to-bounce-manifestation",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        session.pass_rules_priority("p1")
        self.assertIsNone(session.find_battlefield_item("foe"))
        self.assertIn("m-3", p2["zones"]["hand"])
        self.assertEqual(item["counters"]["Control"], 0)

    def test_atavic_introspection_splits_two_limbo_cards_after_ten_controls(self):
        session, p1, _p2, item = self.atavic_session("265f4wdooq43pjn_en")
        self.put(p1, "graveyard", ["m-3", "m-4"])
        item["counters"]["Control"] = 9
        self.assertEqual(session.build_rules_end_turn_field_triggers(), [])
        item["counters"]["Control"] = 10
        queued = session.build_rules_end_turn_field_triggers()
        self.assertEqual(
            [a["ability"]["id"] for a in queued],
            ["split-two-limbo-cards-at-end-of-turn-with-ten-controls"],
        )
        self.assertTrue(queued[0]["optional"])

    def test_atavic_oppression_makes_the_opponent_discard_while_its_owner_draws(self):
        session, p1, p2, item = self.atavic_session("a058t24med4h5nx_en")
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
        session.rules_engine["priorityPlayerId"] = "p1"
        self.put(p1, "deck", ["m-8"])
        self.put(p2, "hand", ["m-5", "m-6"])
        item["counters"]["Fatigue"] = 5
        error, _action = session.declare_rules_action(
            "p1", "Fatigue", kind="activated_effect",
            source={"cardId": item["cardId"], "zone": "battlefield", "itemId": "atavic"},
            ability_id="spend-fatigues-to-make-opponent-discard",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        session.pass_rules_priority("p1")
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual((choice["kind"], choice["playerId"]), ("discard_from_hand", "p2"))
        self.assertIn("m-8", p1["zones"]["hand"])

    def test_atavic_volatility_disables_a_target_each_turn_after_ten_coils(self):
        session, p1, _p2, item = self.atavic_session("rqvzo3iji2a1l65_en")
        session.battlefield.append(self.field_item("foe", "p2", "m-3"))
        item["counters"]["Coil"] = 9
        self.assertEqual(session.queue_rules_beginning_turn_triggers(), [])
        item["counters"]["Coil"] = 10
        session.rules_engine["beginningTriggersTurn"] = None
        session.queue_rules_beginning_turn_triggers()
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "optional_stack_action")

    def test_atavic_fury_shrinks_a_target_and_pays_ten_points_on_wins_after_ten(self):
        session, p1, p2, item = self.atavic_session("m2l3v60n0iakrm2_en")
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
        session.rules_engine["priorityPlayerId"] = "p1"
        session.card_rules["m-3"]["power"] = 4
        session.battlefield.append(self.field_item("foe", "p2", "m-3"))
        item["counters"]["Violence"] = 5
        error, _action = session.declare_rules_action(
            "p1", "Violence", kind="activated_effect",
            source={"cardId": item["cardId"], "zone": "battlefield", "itemId": "atavic"},
            targets=[{"kind": "card", "itemId": "foe", "cardId": "m-3"}],
            ability_id="spend-violence-to-shrink-manifestation",
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        session.pass_rules_priority("p1")
        self.assertEqual(self.power_of(session, "foe"), 2)
        item["counters"]["Violence"] = 10
        self.set_outcome(session, "p1", "p2", "foe")
        queued = [
            a for a in session.queue_rules_confrontation_win_triggers(defer=True)
            if a["source"]["cardId"] == item["cardId"]
        ]
        self.assertEqual(len(queued), 1)
        session.apply_rules_action_result(queued[0])
        self.assertEqual(p1["score"], 10)
        self.set_outcome(session, "p2", "p1", "foe")
        item["counters"]["Violence"] = 9
        self.assertEqual([
            a for a in session.queue_rules_confrontation_win_triggers(defer=True)
            if a["source"]["cardId"] == item["cardId"]
        ], [])

    def test_before_the_revelation_persistent_will_window(self):
        session, p1, _p2, _item = self.atavic_session("m2l3v60n0iakrm2_en")
        session.card_rules["plain"] = {"type": "persistent_will"}
        session.phase_tracker["turn"] = 2
        session.phase_tracker["index"] = ADVANCED_PHASES.index(
            "confrontation_before_revelation"
        )
        flagged = session.rules_action_timing_error(
            "play_card", {"cardId": "m2l3v60n0iakrm2_en", "cardType": "persistent_will"}
        )
        plain = session.rules_action_timing_error(
            "play_card", {"cardId": "plain", "cardType": "persistent_will"}
        )
        self.assertIsNone(flagged)
        self.assertIn("End actions", plain)

    def watcher_session(self, *card_ids, zone="interzone"):
        session, p1, p2 = self.make_session()
        for card_id in card_ids:
            abilities = self.ABILITIES[card_id]
            session.card_rules[card_id] = {
                "type": "manifestation", "power": 3,
                "triggeredAbilities": [a for a in abilities if a.get("trigger")],
                "passiveEffects": [
                    a["passiveEffect"] for a in abilities if a.get("passiveEffect")
                ],
            }
            session.battlefield.append(
                self.field_item(f"w-{card_id}", "p1", card_id, field_zone=zone)
            )
        return session, p1, p2

    CHAIN = "inner-deserts-036"

    def chain_session(self, *card_ids):
        session, p1, p2 = self.watcher_session(*card_ids)
        for card_id in card_ids:
            session.card_rules[card_id]["power"] = 3
        return session, p1, p2

    def chain_action(self, card_id, controller="p1", item_id=None, targets=None):
        ability = self.ABILITIES[card_id][0]
        return {
            "id": "chain-action", "controllerId": controller,
            "source": {"cardId": card_id, "itemId": item_id or f"w-{card_id}"},
            "targets": targets or [], "optionalAccepted": True,
            "ability": {"result": ability["result"]},
        }

    def test_looj_chain_returns_to_hand_and_pays_the_opponent_when_it_loses(self):
        looj = "inner-deserts-036"
        session, p1, p2 = self.chain_session(looj)
        session.card_rules["m-1"]["power"] = 2
        session.card_points["m-1"] = 20
        self.put(p1, "hand", ["m-1"])
        action = self.chain_action(looj)
        payload = session.apply_rules_action_result(action)
        self.assertEqual(payload["choiceKind"], "chain_manifestation")
        choice = session.rules_engine["pendingChoice"]
        self.assertFalse(choice["optional"])
        error, chained = session.resolve_rules_choice(
            "p1", choice["id"], ["m-1"], placement={"x": 10, "y": 10}
        )
        self.assertIsNone(error)
        item = session.find_battlefield_item(chained["itemId"])
        self.assertEqual(len(item["chainAbilities"]), 2)
        self.set_outcome(session, "p2", "p1", item["id"])
        session.rules_engine["actionStack"] = []
        queued = session.queue_rules_confrontation_win_triggers(defer=True)
        chain_actions = [a for a in queued if a["source"]["cardId"] == "m-1"]
        self.assertEqual(len(chain_actions), 2)
        for queued_action in chain_actions:
            session.apply_rules_action_result(queued_action)
        self.assertIn("m-1", p1["zones"]["hand"])
        self.assertIsNone(session.find_battlefield_item(item["id"]))
        self.assertEqual(p2["score"], 20)

    def test_looj_without_manifestation_in_hand_shows_the_hand(self):
        looj = "inner-deserts-036"
        session, p1, _p2 = self.chain_session(looj)
        self.put(p1, "hand", ["field-will"])
        payload = session.apply_rules_action_result(self.chain_action(looj))
        self.assertEqual(payload["status"], "no_eligible_card")
        self.assertEqual(payload["handProofs"][0]["playerId"], "p1")
        self.assertEqual(payload["handProofs"][0]["cardIds"], ["field-will"])

    def test_mukkabell_chain_pays_five_points_per_base_power_on_a_win(self):
        mukkabell = "inner-deserts-012"
        session, p1, _p2 = self.chain_session(mukkabell)
        session.card_rules["m-1"]["power"] = 4
        self.put(p1, "hand", ["m-1"])
        session.apply_rules_action_result(self.chain_action(mukkabell))
        choice = session.rules_engine["pendingChoice"]
        self.assertTrue(choice["optional"] is False)
        _error, chained = session.resolve_rules_choice(
            "p1", choice["id"], ["m-1"], placement={"x": 10, "y": 10}
        )
        self.set_outcome(session, "p1", "p2", chained["itemId"])
        session.rules_engine["actionStack"] = []
        queued = session.queue_rules_confrontation_win_triggers(defer=True)
        for queued_action in [a for a in queued if a["source"]["cardId"] == "m-1"]:
            session.apply_rules_action_result(queued_action)
        self.assertEqual(p1["score"], 20)

    def test_zrutrug_chain_discards_the_chained_base_power_from_the_deck(self):
        zrutrug = "k4m0j5h0l3f61hs_en"
        session, p1, _p2 = self.chain_session(zrutrug)
        session.card_rules["m-1"]["power"] = 3
        self.put(p1, "hand", ["m-1"])
        self.put(p1, "deck", ["m-2", "m-3", "m-4", "m-5"])
        session.apply_rules_action_result(self.chain_action(zrutrug))
        choice = session.rules_engine["pendingChoice"]
        session.resolve_rules_choice(
            "p1", choice["id"], ["m-1"], placement={"x": 10, "y": 10}
        )
        self.assertEqual(p1["zones"]["deck"], ["m-5"])
        self.assertEqual(len(p1["zones"]["graveyard"]), 3)

    def test_larman_doz_gives_the_opponent_target_power_counters(self):
        larman = "inner-deserts-008"
        session, p1, _p2 = self.chain_session(larman)
        session.card_rules["m-1"]["power"] = 2
        self.put(p1, "hand", ["m-1"])
        session.battlefield.append(self.field_item("foe", "p2", "m-3"))
        action = self.chain_action(
            larman, targets=[{"kind": "card", "itemId": "foe", "cardId": "m-3"}]
        )
        session.apply_rules_action_result(action)
        choice = session.rules_engine["pendingChoice"]
        session.resolve_rules_choice(
            "p1", choice["id"], ["m-1"], placement={"x": 10, "y": 10}
        )
        self.assertEqual(self.power_of(session, "foe"), 3)

    def test_help_costs_ten_points_and_exiles_a_winning_chain(self):
        help_card = "mv2vad6gwrfbi1l_en"
        session, p1, _p2 = self.chain_session()
        session.card_rules[help_card] = {"type": "ephemeral_will"}
        self.put(p1, "hand", ["m-1"])
        action = {
            "id": "help", "controllerId": "p1",
            "source": {"cardId": help_card},
            "ability": {"result": self.ABILITIES[help_card][0]["result"]},
        }
        session.apply_rules_action_result(action)
        self.assertEqual(p1["score"], -10)
        choice = session.rules_engine["pendingChoice"]
        _error, chained = session.resolve_rules_choice(
            "p1", choice["id"], ["m-1"], placement={"x": 10, "y": 10}
        )
        self.assertEqual(chained["status"], "chained")
        self.assertTrue(any(
            m.get("kind") == "win_destination_exile"
            for m in session.rules_engine.get("effectMemories", [])
        ))

    def test_first_stone_makes_each_opponent_chain_and_shows_hands_otherwise(self):
        first_stone = "4rnpxnnceu8x9o9_en"
        session, p1, p2 = self.chain_session(first_stone)
        self.put(p1, "hand", ["m-1"])
        self.put(p2, "hand", ["field-will"])
        payload = session.apply_rules_action_result(self.chain_action(first_stone))
        self.assertEqual(payload["status"], "no_eligible_card")
        self.assertEqual(payload["handProofs"], [
            {"playerId": "p2", "cardIds": ["field-will"]}
        ])
        self.put(p2, "hand", ["m-2"])
        payload = session.apply_rules_action_result(self.chain_action(first_stone))
        self.assertEqual(payload["playerId"], "p2")
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["playerId"], "p2")
        self.assertFalse(choice["optional"])
        error, chained = session.resolve_rules_choice(
            "p2", choice["id"], ["m-2"], placement={"x": 10, "y": 10}
        )
        self.assertIsNone(error)
        self.assertEqual(session.find_battlefield_item(chained["itemId"])["controllerId"], "p2")

    def test_advocate_of_catharsis_makes_every_player_chain_in_turn(self):
        advocate = "46id1c09q8inlkz_en"
        session, p1, p2 = self.chain_session(advocate)
        self.put(p1, "hand", ["m-1"])
        self.put(p2, "hand", ["m-2"])
        payload = session.apply_rules_action_result(self.chain_action(advocate))
        self.assertEqual(payload["playerId"], "p1")
        choice = session.rules_engine["pendingChoice"]
        session.resolve_rules_choice(
            "p1", choice["id"], ["m-1"], placement={"x": 10, "y": 10}
        )
        self.assertIsNone(session.rules_engine["pendingChoice"])
        session.resolve_rules_chain_sequences()
        second = session.rules_engine["pendingChoice"]
        self.assertEqual(second["playerId"], "p2")
        error, _chained = session.resolve_rules_choice(
            "p2", second["id"], ["m-2"], placement={"x": 20, "y": 20}
        )
        self.assertIsNone(error)
        self.assertEqual(p2["zones"]["hand"], [])

    def test_mollino_puts_the_first_manifestation_under_the_deck_before_the_chain(self):
        mollino = "inner-deserts-081"
        session, p1, p2 = self.chain_session(mollino)
        session.battlefield.append(self.field_item("first", "p2", "m-3"))
        session.rules_engine["firstManifestationItemIds"] = {"p2": "first"}
        self.put(p2, "hand", ["m-2"])
        self.put(p2, "deck", ["m-4"])
        session.apply_rules_action_result(self.chain_action(mollino))
        self.assertIsNone(session.find_battlefield_item("first"))
        self.assertEqual(p2["zones"]["deck"], ["m-4", "m-3"])
        self.assertEqual(session.rules_engine["pendingChoice"]["playerId"], "p2")

    def test_kazadur_gains_power_per_opponent_manifestation_up_to_three(self):
        kazadur = "inner-deserts-112"
        session, _p1, _p2 = self.chain_session()
        session.card_rules[kazadur] = {
            "type": "manifestation", "power": 4,
            "continuousPowerRules": [{"kind": "self_per_opponent_confrontation_total", "value": 1, "cap": 3}],
        }
        session.battlefield = [self.field_item("kaz", "p1", kazadur)]
        self.assertEqual(self.power_of(session, "kaz"), 4)
        for index in range(5):
            session.battlefield.append(self.field_item(f"foe{index}", "p2", f"m-{index + 5}"))
            expected = 4 + min(index + 1, 3)
            self.assertEqual(self.power_of(session, "kaz"), expected)

    def cast(self, session, card_id, controller="p1", targets=None, source_extra=None):
        ability = self.ABILITIES[card_id][0]
        action = {
            "id": f"cast-{card_id}", "controllerId": controller,
            "source": {"cardId": card_id, **(source_extra or {})},
            "targets": targets or [], "ability": {"result": ability["result"]},
        }
        error = session.rules_ability_targets_error(
            ability.get("targets"), action["targets"], controller
        )
        return error, action

    def test_claim_the_forsaken_takes_a_manifestation_that_just_entered_an_opponent_limbo(self):
        claim = "zd6h16he0m4kuwb_en"
        session, p1, p2 = self.make_session()
        session.card_rules[claim] = {"type": "ephemeral_will"}
        self.put(p2, "hand", ["m-1", "m-2"])
        session.move_zone_card("p2", "hand", "p2", "graveyard", "m-1")
        target = {"kind": "zone_card", "containerId": "p2", "zone": "graveyard",
                  "cardId": "m-1", "ownerId": "p2"}
        error, action = self.cast(session, claim, targets=[target])
        self.assertIsNone(error)
        session.rules_engine["zoneEntryTurns"]["p2:graveyard:m-1"] = 0
        stale_error, _ = self.cast(session, claim, targets=[target])
        self.assertIn("this turn", stale_error)
        session.rules_engine["zoneEntryTurns"]["p2:graveyard:m-1"] = session.phase_tracker["turn"]
        own_error, _ = self.cast(session, claim, targets=[{
            **target, "containerId": "p1", "ownerId": "p1",
        }])
        self.assertIsNotNone(own_error)
        session.apply_rules_action_result(action)
        self.assertNotIn("m-1", p2["zones"]["graveyard"])
        self.assertEqual(p1["zones"]["receptacle"], ["m-1"])
        self.assertEqual(p1["zoneOwners"]["receptacle"]["m-1"], "p2")

    def test_salvage_and_mock_fate_put_recent_cards_into_stalemate(self):
        salvage, mock = "xeeg6rdiy9xeew5_en", "inner-deserts-095"
        session, p1, p2 = self.make_session()
        session.card_rules[salvage] = {"type": "ephemeral_will"}
        session.card_rules[mock] = {"type": "ephemeral_will"}
        session.put_zone_card("p2", "receptacle", "m-1", "p1")
        session.put_zone_card("p1", "graveyard", "m-2", "p1")
        vessel = {"kind": "zone_card", "containerId": "p2", "zone": "receptacle",
                  "cardId": "m-1", "ownerId": "p1"}
        error, action = self.cast(session, salvage, targets=[vessel])
        self.assertIsNone(error)
        session.apply_rules_action_result(action)
        stalemate = [i for i in session.battlefield if i["cardId"] == "m-1"]
        self.assertEqual([i["fieldZone"] for i in stalemate], ["stalemate"])
        self.assertEqual(p2["zones"]["receptacle"], [])
        limbo = {"kind": "zone_card", "containerId": "p1", "zone": "graveyard",
                 "cardId": "m-2", "ownerId": "p1"}
        error, action = self.cast(session, mock, targets=[limbo])
        self.assertIsNone(error)
        session.apply_rules_action_result(action)
        self.assertTrue(any(
            i["cardId"] == "m-2" and i["fieldZone"] == "stalemate"
            for i in session.battlefield
        ))
        session.rules_engine["zoneEntryTurns"]["p1:graveyard:m-3"] = 0
        session.put_zone_card("p1", "graveyard", "m-3", "p1")
        session.rules_engine["zoneEntryTurns"]["p1:graveyard:m-3"] = 0
        old = {**limbo, "cardId": "m-3"}
        error, _ = self.cast(session, mock, targets=[old])
        self.assertIn("this turn", error)

    def test_mock_fate_can_only_be_played_in_reaction_with_an_empty_stack(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["mock"] = {"type": "ephemeral_will", "reactionEmptyStackOnly": True}
        session.rules_engine["firstManifestationComplete"] = True
        session.phase_tracker["turn"] = 2
        source = {"cardType": "ephemeral_will", "cardId": "mock"}
        session.current_phase_id = lambda: "confrontation_reaction"
        session.rules_engine["actionStack"] = []
        self.assertIsNone(session.rules_action_timing_error("play_card", source))
        session.rules_engine["actionStack"] = [{"id": "x"}]
        self.assertIn("Stack is empty", session.rules_action_timing_error("play_card", source))
        session.rules_engine["actionStack"] = []
        session.current_phase_id = lambda: "end_actions"
        self.assertIsNotNone(session.rules_action_timing_error("play_card", source))

    def test_abandon_returns_target_player_support_and_blocks_replaying_this_turn(self):
        abandon = "knnq85hihrxuafj_en"
        session, p1, p2 = self.make_session()
        session.card_rules[abandon] = {"type": "ephemeral_will"}
        session.card_rules["m-3"]["adamant"] = True
        session.battlefield = [
            self.field_item("sup1", "p2", "m-1", isSupport=True),
            self.field_item("sup2", "p2", "m-3", isSupport=True),
            self.field_item("plain", "p2", "m-2"),
            self.field_item("mine", "p1", "m-4", isSupport=True),
        ]
        error, action = self.cast(
            session, abandon, targets=[{"kind": "player", "playerId": "p2"}]
        )
        self.assertIsNone(error)
        payload = session.apply_rules_action_result(action)
        self.assertEqual(payload["itemIds"], ["sup1"])
        self.assertEqual(payload["preventedItemIds"], ["sup2"])
        self.assertEqual(p2["zones"]["hand"], ["m-1"])
        self.assertIsNotNone(session.rules_card_play_restriction_error("p2", "m-1"))
        self.assertEqual(
            sorted(i["id"] for i in session.battlefield), ["mine", "plain", "sup2"]
        )

    def test_rogue_tadpole_returns_the_target_interzone_to_the_deck_tops(self):
        tadpole = "uycbbilf0zlttb9_en"
        session, p1, p2 = self.make_session(tadpole)
        session.battlefield = [
            self.field_item("a", "p2", "m-1", field_zone="interzone"),
            self.field_item("b", "p2", "m-2", field_zone="interzone"),
            self.field_item("c", "p2", "m-3"),
        ]
        self.put(p2, "deck", ["m-9"])
        action = {
            "id": "t", "controllerId": "p1", "source": {"cardId": tadpole},
            "targets": [{"kind": "player", "playerId": "p2"}],
            "ability": {"result": self.ABILITIES[tadpole][0]["result"]},
        }
        session.apply_rules_action_result(action)
        self.assertEqual(set(p2["zones"]["deck"][:2]), {"m-1", "m-2"})
        self.assertEqual(p2["zones"]["deck"][2], "m-9")
        self.assertEqual([i["id"] for i in session.battlefield], ["c"])

    def test_manipulate_intellect_steals_a_manifestation_that_entered_the_interzone_this_turn(self):
        manipulate = "343xggqp4a0zfw1_en"
        session, p1, p2 = self.make_session()
        session.card_rules[manipulate] = {"type": "ephemeral_will"}
        session.battlefield = [
            self.field_item("fresh", "p2", "m-1", field_zone="interzone"),
            self.field_item("stale", "p2", "m-2", field_zone="interzone"),
            self.field_item("mine", "p1", "m-3", field_zone="interzone"),
        ]
        session.mark_rules_interzone_entry(session.battlefield[0])
        session.mark_rules_interzone_entry(session.battlefield[2])
        session.battlefield[1]["interzoneTurn"] = session.phase_tracker["turn"] - 1

        def target(item_id, card_id):
            return [{"kind": "card", "itemId": item_id, "cardId": card_id}]

        error, action = self.cast(session, manipulate, targets=target("fresh", "m-1"))
        self.assertIsNone(error)
        stale_error, _ = self.cast(session, manipulate, targets=target("stale", "m-2"))
        self.assertIn("this turn", stale_error)
        own_error, _ = self.cast(session, manipulate, targets=target("mine", "m-3"))
        self.assertIsNotNone(own_error)
        session.apply_rules_action_result(action)
        self.assertIsNone(session.find_battlefield_item("fresh"))
        self.assertEqual(p1["zones"]["receptacle"], ["m-1"])
        self.assertEqual(p1["zoneOwners"]["receptacle"]["m-1"], "p2")

    def manual_batch_session(self, *card_ids, card_type="ephemeral_will"):
        session, p1, p2 = self.make_session()
        for card_id in card_ids:
            abilities = self.ABILITIES[card_id]
            session.card_rules[card_id] = {
                "type": card_type, "power": 2,
                "triggeredAbilities": [a for a in abilities if a.get("trigger")],
            }
        return session, p1, p2

    def run_ability(self, session, card_id, targets=None, controller="p1", item_id=None):
        ability = self.ABILITIES[card_id][0]
        error = session.rules_ability_targets_error(
            ability.get("targets"), targets or [], controller
        )
        self.assertIsNone(error)
        action = {
            "id": f"run-{card_id}", "controllerId": controller,
            "source": {"cardId": card_id, "itemId": item_id},
            "targets": targets or [], "ability": ability,
        }
        return session.apply_rules_action_result({
            **action, "ability": {"result": ability["result"]},
        }), action

    def test_gar_fild_and_pinpia_keep_their_essences_past_the_end_of_the_turn(self):
        gar, pinpia = "rl4ppd0wsyov7lw_en", "5xurdeiiyq7kgir_en"
        session, p1, _p2 = self.manual_batch_session(gar, pinpia, card_type="manifestation")
        session.battlefield = [
            self.field_item("a", "p1", "m-1", field_zone="interzone"),
            self.field_item("b", "p1", "m-2", field_zone="interzone"),
        ]
        self.run_ability(session, gar)
        self.run_ability(session, pinpia)
        pool = {
            token["temperament"]: token["counters"]["essence"]
            for token in session.tokens if token.get("isEssence")
        }
        self.assertEqual(pool, {"transcendent": 6})
        self.assertTrue(all(token["expiresTurn"] == 0 for token in session.tokens))
        session.expire_rules_excess_essence(session.phase_tracker["turn"])
        self.assertEqual(len([t for t in session.tokens if t.get("isEssence")]), 1)

    def test_entrust_doubles_the_target_base_power(self):
        entrust = "ud9clfoj2c6x96o_en"
        session, _p1, _p2 = self.manual_batch_session(entrust)
        session.card_rules["m-1"]["power"] = 3
        session.battlefield = [self.field_item("t", "p2", "m-1")]
        self.run_ability(session, entrust, [{"kind": "card", "itemId": "t", "cardId": "m-1"}])
        self.assertEqual(self.power_of(session, "t"), 6)

    def test_glimpse_the_omens_reorders_four_cards_then_draws_one(self):
        glimpse = "9yylrq6xancbn0m_en"
        session, p1, _p2 = self.manual_batch_session(glimpse)
        self.put(p1, "deck", ["m-1", "m-2", "m-3", "m-4", "m-5"])
        payload, _action = self.run_ability(session, glimpse)
        self.assertEqual(payload["choiceKind"], "deck_reorder")
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["groups"][0]["cardIds"], ["m-1", "m-2", "m-3", "m-4"])
        error, resolved = session.resolve_rules_choice("p1", choice["id"], option={"groups": [{
            "playerId": "p1", "top": ["m-3", "m-1"], "bottom": ["m-2", "m-4"],
        }]})
        self.assertIsNone(error)
        self.assertEqual(p1["zones"]["hand"], ["m-3"])
        self.assertEqual(p1["zones"]["deck"], ["m-1", "m-5", "m-2", "m-4"])

    def test_rude_exterminator_destroys_a_random_interzone_manifestation(self):
        exterminator = "unk0z0mamdx1el5_en"
        session, _p1, p2 = self.manual_batch_session(exterminator, card_type="manifestation")
        session.battlefield = [
            self.field_item("a", "p2", "m-1", field_zone="interzone"),
            self.field_item("conf", "p2", "m-2"),
        ]
        payload, _action = self.run_ability(
            session, exterminator, [{"kind": "player", "playerId": "p2"}]
        )
        self.assertEqual(payload["status"], "moved")
        self.assertEqual(p2["zones"]["graveyard"], ["m-1"])
        self.assertIsNotNone(session.find_battlefield_item("conf"))
        payload, _action = self.run_ability(
            session, exterminator, [{"kind": "player", "playerId": "p2"}]
        )
        self.assertEqual(payload["status"], "nothing_to_destroy")

    def test_shattering_the_self_weakens_per_discarded_manifestation(self):
        shattering = "k7dq8ye448xwj54_en"
        session, _p1, p2 = self.manual_batch_session(shattering)
        session.card_rules["will"] = {"type": "ephemeral_will"}
        session.card_rules["m-1"]["power"] = 4
        self.put(p2, "deck", ["m-2", "will", "m-3", "m-4"])
        session.battlefield = [self.field_item("foe", "p2", "m-1")]
        targets = [
            {"kind": "player", "playerId": "p2"},
            {"kind": "card", "itemId": "foe", "cardId": "m-1"},
        ]
        payload, _action = self.run_ability(session, shattering, targets)
        self.assertEqual(payload["manifestations"], 2)
        self.assertEqual(p2["zones"]["deck"], ["m-4"])
        self.assertEqual(self.power_of(session, "foe"), 2)

    def test_deviate_and_repress_the_self_use_the_confrontation_outcome(self):
        deviate, repress = "ynp0apjx1risrpt_en", "yk0ic6ev7465bxo_en"
        session, p1, p2 = self.manual_batch_session(deviate, repress)
        session.card_points["m-1"] = 25
        session.battlefield = [
            self.field_item("mine", "p1", "m-1"),
            self.field_item("theirs", "p2", "m-2"),
        ]
        self.set_outcome(session, "p1", "p2", "mine", "theirs")
        target = lambda item, card: [{"kind": "card", "itemId": item, "cardId": card}]
        winner_error = session.rules_ability_targets_error(
            self.ABILITIES[deviate][0]["targets"], target("mine", "m-1"), "p1"
        )
        self.assertIn("lost", winner_error)
        self.run_ability(session, deviate, target("theirs", "m-2"))
        self.assertEqual(p2["zones"]["graveyard"], ["m-2"])
        self.run_ability(session, repress, target("mine", "m-1"))
        self.assertEqual((p1["zones"]["graveyard"], p1["score"]), (["m-1"], 25))

    def test_incite_to_sacrifice_adds_power_and_exiles_the_winner(self):
        incite = "bc3esblt60j7at5_en"
        session, p1, _p2 = self.manual_batch_session(incite)
        session.battlefield = [self.field_item("t", "p1", "m-1")]
        target = [{"kind": "card", "itemId": "t", "cardId": "m-1"}]
        payload, action = self.run_ability(session, incite, target)
        self.assertEqual(payload["status"], "marked")
        effects = session.create_rules_ongoing_effects(action)
        self.assertEqual(len(effects), 1)
        self.assertEqual(self.power_of(session, "t"), 7)
        self.assertTrue(any(
            m["kind"] == "win_destination_exile"
            for m in session.rules_engine.get("effectMemories", [])
        ))

    def test_carcass_devourer_exiles_limbo_manifestations_for_their_power(self):
        carcass = "zh4rjhzon9qes6m_en"
        session, p1, _p2 = self.manual_batch_session(carcass, card_type="manifestation")
        session.card_rules["m-1"]["power"] = 3
        session.card_rules["m-2"]["power"] = 2
        self.put(p1, "graveyard", ["m-1", "m-2"])
        session.battlefield = [self.field_item("carcass", "p1", carcass)]
        targets = [
            {"kind": "zone_card", "containerId": "p1", "zone": "graveyard", "cardId": cid, "ownerId": "p1"}
            for cid in ("m-1", "m-2")
        ]
        session.rules_engine["zoneEntryTurns"] = {}
        self.run_ability(session, carcass, targets, item_id="carcass")
        self.assertEqual(p1["zones"]["graveyard"], [])
        self.assertEqual(sorted(p1["zones"]["exile"]), ["m-1", "m-2"])
        self.assertEqual(session.find_battlefield_item("carcass")["counters"]["power"], 5)

    def test_deny_fate_is_only_playable_before_the_revelation_and_redraws_seven(self):
        deny = "f18fccv1k2co206_en"
        session, p1, _p2 = self.manual_batch_session(deny)
        session.card_rules[deny]["playPhases"] = ["confrontation_before_revelation"]
        session.rules_engine["firstManifestationComplete"] = True
        session.phase_tracker["turn"] = 2
        source = {"cardType": "ephemeral_will", "cardId": deny}
        session.current_phase_id = lambda: "confrontation_reaction"
        self.assertIsNotNone(session.rules_action_timing_error("play_card", source))
        session.current_phase_id = lambda: "confrontation_before_revelation"
        self.assertIsNone(session.rules_action_timing_error("play_card", source))
        self.put(p1, "hand", ["m-1", "m-2"])
        self.put(p1, "deck", [f"m-{i}" for i in range(3, 13)])
        self.run_ability(session, deny)
        self.assertEqual(len(p1["zones"]["hand"]), 7)
        self.assertEqual(len(p1["zones"]["deck"]), 5)

    def test_urolong_raises_a_limbo_manifestation_without_its_effects(self):
        urolong = "pekwxpsy3c0ro3l_en"
        session, p1, _p2 = self.manual_batch_session(urolong, card_type="manifestation")
        self.put(p1, "graveyard", ["m-1"])
        session.rules_engine["zoneEntryTurns"] = {}
        target = [{"kind": "zone_card", "containerId": "p1", "zone": "graveyard", "cardId": "m-1", "ownerId": "p1"}]
        self.run_ability(session, urolong, target)
        item = next(i for i in session.battlefield if i["cardId"] == "m-1")
        self.assertTrue(item["isSupport"])
        self.assertTrue(item["effectsDisabled"])
        self.assertEqual(item["supportWinDestination"], "exile")

    def card_target(self, item_id, card_id):
        return {"kind": "card", "itemId": item_id, "cardId": card_id}

    def test_easy_batch_power_effects(self):
        judgment, fly, desertion, humiliate = (
            "inner-deserts-046", "inner-deserts-101", "inner-deserts-148", "pqi88s5ytyfnalf_en",
        )
        session, p1, _p2 = self.manual_batch_session(judgment, fly, desertion, humiliate)
        session.card_rules["m-1"] = {"type": "manifestation", "power": 6, "temperaments": ["phlegmatic"]}
        session.battlefield = [
            self.field_item("t", "p2", "m-1"),
            self.field_item("s", "p2", "m-2", isSupport=True),
        ]
        session.card_rules["m-2"] = {"type": "manifestation", "power": 3, "temperaments": ["phlegmatic"]}
        self.put(p1, "hand", ["m-3", "m-4", "m-5"])
        self.run_ability(session, judgment, [self.card_target("t", "m-1")])
        self.assertEqual(self.power_of(session, "t"), 3)
        self.run_ability(session, desertion, [self.card_target("t", "m-1"), self.card_target("s", "m-2")])
        self.assertEqual(self.power_of(session, "t"), 0)
        session.battlefield.append(self.field_item("w", "p1", "m-6", field_zone="interzone"))
        fly_ability = self.ABILITIES[fly][1]
        self.assertEqual(fly_ability["result"], {"kind": "add_power_counter_target", "value": -2})
        session.apply_rules_action_result({
            "id": "fly", "controllerId": "p1", "source": {"cardId": fly},
            "targets": [self.card_target("w", "m-6")],
            "ability": {"result": fly_ability["result"]},
        })
        self.assertEqual(self.power_of(session, "w"), -1)
        self.run_ability(session, humiliate, [self.card_target("t", "m-1")])
        item = session.find_battlefield_item("t")
        self.assertEqual(item["temperamentOverride"], "hollow")
        self.assertEqual(session.players["p2"].get("score"), -5)

    def test_easy_batch_dissolve_convert_and_rah_kio(self):
        dissolve, convert, rah = "inner-deserts-019", "inner-deserts-021", "inner-deserts-109"
        session, p1, p2 = self.manual_batch_session(dissolve, convert, rah)
        self.put(p1, "receptacle", ["m-1", "m-2"])
        targets = [
            {"kind": "zone_card", "containerId": "p1", "zone": "receptacle", "cardId": cid, "ownerId": "p1"}
            for cid in ("m-1", "m-2")
        ]
        self.run_ability(session, dissolve, targets)
        self.assertEqual(p1["zones"]["receptacle"], [])
        self.assertEqual(sorted(p1["zones"]["deck"]), ["m-1", "m-2"])
        self.assertEqual(p1.get("score"), 60)
        self.put(p1, "deck", [f"m-{i}" for i in range(5, 12)])
        self.put(p2, "deck", [f"m-{i}" for i in range(12, 19)])
        session.battlefield = [
            self.field_item("a", "p1", "m-3", isSupport=True),
            self.field_item("b", "p2", "m-4", isSupport=True),
            self.field_item("tok", "p2", "captured", isTokenCard=True),
        ]
        self.run_ability(session, convert, [self.card_target("a", "m-3"), self.card_target("b", "m-4")])
        self.assertEqual(len(p1["zones"]["hand"]), 2)
        self.assertEqual(len(p2["zones"]["hand"]), 2)
        self.assertEqual(session.battlefield[0]["id"], "tok")
        self.run_ability(session, rah)
        self.assertEqual(session.battlefield, [])

    def test_easy_batch_volcano_and_consult(self):
        volcano, consult = "2xqczn7vzkm5n50_en", "9c7s9dn3sa5dcko_en"
        session, p1, _p2 = self.manual_batch_session(volcano, consult)
        session.card_rules["w"] = {"type": "persistent_will"}
        session.battlefield = [
            self.field_item("w", "p2", "w", field_zone="field"),
            self.field_item("i", "p2", "m-1", field_zone="interzone"),
            self.field_item("c", "p2", "m-2", field_zone="confrontation"),
        ]
        self.run_ability(session, volcano)
        self.assertEqual([i["id"] for i in session.battlefield], ["c"])
        session.card_rules["will-x"] = {"type": "ephemeral_will"}
        self.put(p1, "deck", ["will-x", "will-ephemeral", "m-5", "m-6"])
        self.run_ability(session, consult, [{"kind": "player", "playerId": "p1"}])
        self.assertEqual(sorted(p1["zones"]["graveyard"]), ["will-ephemeral", "will-x"])
        support = next(i for i in session.battlefield if i["cardId"] == "m-5")
        self.assertTrue(support["isSupport"])

    def test_easy_batch_eviscerate_discards_after_reorder(self):
        card = "inner-deserts-068"
        session, p1, _p2 = self.manual_batch_session(card)
        self.put(p1, "deck", [f"m-{i}" for i in range(1, 9)])
        result, action = self.run_ability(session, card)
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "deck_reorder")
        self.assertEqual(choice.get("_afterDiscard"), 2)

    def test_easy_batch_pigon_cage_veer_and_husk_definitions(self):
        pigon, cage, veer, husk = (
            "2oka6j26ibu19l9_en", "gpxqooqq57loyb8_en", "inner-deserts-044", "8g5pn3mukkuniog_en",
        )
        session, p1, _p2 = self.manual_batch_session(pigon, cage, veer, husk)
        session.battlefield = [self.field_item("s", "p2", "m-1", isSupport=True)]
        self.run_ability(session, pigon, [self.card_target("s", "m-1")])
        self.assertEqual(session.battlefield, [])
        self.assertIn("m-1", session.players["p2"]["zones"]["hand"])
        self.put(p1, "graveyard", ["m-2"])
        session.rules_engine["zoneEntryTurns"] = {}
        self.run_ability(session, cage, [
            {"kind": "zone_card", "containerId": "p1", "zone": "graveyard", "cardId": "m-2", "ownerId": "p1"}
        ])
        entered = next(i for i in session.battlefield if i["cardId"] == "m-2")
        self.assertEqual(session.rules_field_zone(entered), "interzone")
        self.assertEqual(self.ABILITIES[cage][0]["sacrificeDestination"], "exile")
        self.assertEqual(self.ABILITIES[veer][0]["result"]["destination"], "hand")
        self.assertEqual(
            self.ABILITIES[husk][0]["ongoingEffect"]["duration"], "while_source_and_target_on_field"
        )

    def test_partial_batch_lament_nameless_arcane_and_ononok(self):
        lament, arcane, ononok = "lmjn89wobbttfop_en", "inner-deserts-059", "tzoadjk7wb5qj5f_en"
        session, p1, p2 = self.manual_batch_session(lament, arcane, ononok, card_type="manifestation")
        self.put(p2, "deck", [f"m-{i}" for i in range(1, 9)])
        session.battlefield = [
            self.field_item("a", "p2", "m-10"),
            self.field_item("b", "p2", "m-11", isSupport=True),
            self.field_item("tok", "p2", "m-12", isTokenCard=True),
        ]
        self.run_ability(session, lament, [{"kind": "player", "playerId": "p2"}])
        self.assertEqual(len(p2["zones"]["graveyard"]), 2)
        self.assertEqual(len(p2["zones"]["deck"]), 6)
        session.battlefield = [
            self.field_item("src", "p1", arcane),
            self.field_item("x", "p1", "m-1"),
            self.field_item("y", "p1", "m-2", isSupport=True),
            self.field_item("z", "p2", "m-3"),
        ]
        self.run_ability(session, arcane, item_id="src")
        self.assertEqual(sorted(i["id"] for i in session.battlefield), ["src", "z"])
        pool = {t["temperament"]: t["counters"]["essence"] for t in session.tokens if t.get("isEssence")}
        self.assertEqual(pool, {"transcendent": 2})
        self.put(p1, "graveyard", ["m-4"])
        self.put(p1, "deck", ["m-5"])
        session.battlefield = [
            self.field_item("on", "p1", ononok, field_zone="interzone"),
            self.field_item("iz", "p2", "m-6", field_zone="interzone"),
        ]
        self.run_ability(session, ononok, item_id="on")
        self.assertEqual(session.battlefield, [])
        self.assertIn(ononok, p1["zones"]["exile"])
        self.assertEqual(sorted(p1["zones"]["deck"]), ["m-4", "m-5"])
        self.assertIn("m-6", p2["zones"]["deck"])

    def test_partial_batch_lilitha_mamelath_silem_timidette(self):
        lilitha, mamelath, silem, timidette = (
            "inner-deserts-113", "inner-deserts-017", "inner-deserts-089", "inner-deserts-041",
        )
        session, p1, p2 = self.manual_batch_session(lilitha, mamelath, silem, timidette, card_type="manifestation")
        for cid in (lilitha, mamelath, silem, timidette):
            self.assertEqual(self.ABILITIES[cid][-1]["result"], {"kind": "move_source_to_owner_exile"})
        session.card_rules["m-1"]["power"] = 3
        session.battlefield = [self.field_item("t", "p2", "m-1")]
        self.run_ability(session, lilitha, [self.card_target("t", "m-1")], item_id="src")
        tokens = [i for i in session.battlefield if i.get("isTokenCard")]
        self.assertEqual(len(tokens), 3)
        self.assertTrue(all(i["ownerId"] == "p2" and i["power"] == 1 for i in tokens))
        self.assertIn("m-1", p2["zones"]["graveyard"])
        session.battlefield = [
            self.field_item("f1", "p1", "m-2"), self.field_item("f2", "p2", "m-3"),
        ]
        session.card_rules["m-2"]["power"] = 2
        session.card_rules["m-3"]["power"] = 4
        session.rules_engine["firstManifestationItemIds"] = {"p1": "f1", "p2": "f2"}
        self.run_ability(session, mamelath, item_id="src")
        self.assertEqual(session.rules_field_zone(session.find_battlefield_item("f1")), "interzone")
        counts = {pid: len([i for i in session.battlefield if i.get("isTokenCard") and i["ownerId"] == pid]) for pid in ("p1", "p2")}
        self.assertEqual(counts, {"p1": 2, "p2": 4})
        session.battlefield = [
            self.field_item("s1", "p1", "m-4", field_zone="stalemate"),
            self.field_item("s2", "p2", "m-5", field_zone="stalemate"),
        ]
        self.run_ability(session, silem, item_id="src")
        s1 = session.find_battlefield_item("s1")
        self.assertTrue(s1["isSupport"])
        self.assertEqual(session.rules_field_zone(s1), "confrontation")
        self.assertEqual(session.rules_field_zone(session.find_battlefield_item("s2")), "stalemate")
        self.assertFalse(session.rules_item_effects_active(s1))
        session.battlefield = [
            self.field_item("src", "p1", timidette, isSupport=True),
            self.field_item("keep", "p2", "m-6", isSupport=True),
            self.field_item("gone", "p2", "m-7", isSupport=True),
            self.field_item("mine", "p1", "m-8", isSupport=True),
        ]
        self.run_ability(session, timidette, [self.card_target("keep", "m-6")], item_id="src")
        self.assertEqual(sorted(i["id"] for i in session.battlefield), ["keep", "src"])
        self.assertEqual(p2["zones"]["deck"][-1], "m-7")
        self.assertEqual(p1["zones"]["deck"][-1], "m-8")

    def test_partial_batch_drildrill_refunds_the_tribute_as_essence(self):
        drildrill = "inner-deserts-131"
        session, p1, _p2 = self.manual_batch_session(drildrill, card_type="manifestation")
        session.card_rules["pw"] = {"type": "persistent_will", "cost": 3, "temperaments": ["choleric"]}
        session.battlefield = [self.field_item("pw", "p2", "pw", field_zone="field")]
        self.run_ability(session, drildrill, [self.card_target("pw", "pw")], item_id="src")
        self.assertEqual(session.battlefield, [])
        pool = {t["temperament"]: t["counters"]["essence"] for t in session.tokens if t.get("isEssence") and t["ownerId"] == "p2"}
        self.assertEqual(pool, {"choleric": 3})
        ability = self.ABILITIES[drildrill][0]
        self.assertEqual(ability["extraEssenceByTargetCount"], {"targetCount": 1, "amount": 2})

    def test_partial_batch_phalanx_tower_discards_a_manifestation_to_weaken(self):
        tower = "inner-deserts-111"
        session, p1, _p2 = self.manual_batch_session(tower, card_type="manifestation")
        session.card_rules["m-1"]["power"] = 6
        session.card_rules["m-2"]["power"] = 3
        session.battlefield = [self.field_item("t", "p2", "m-1")]
        self.put(p1, "hand", ["will-ephemeral"])
        ability = self.ABILITIES[tower][0]
        action = {
            "id": "ph", "controllerId": "p1", "optionalAccepted": True,
            "source": {"cardId": tower}, "targets": [self.card_target("t", "m-1")],
            "ability": {"result": ability["result"]},
        }
        self.assertEqual(session.apply_rules_action_result(action)["status"], "no_hand_card")
        self.put(p1, "hand", ["will-ephemeral", "m-2"])
        payload = session.apply_rules_action_result(action)
        self.assertEqual(payload["choiceKind"], "discard_from_hand")
        choice_id = session.rules_engine["pendingChoice"]["id"]
        error, _ = session.resolve_rules_choice("p1", choice_id, card_ids=["will-ephemeral"])
        self.assertIsNotNone(error)
        error, resolved = session.resolve_rules_choice("p1", choice_id, card_ids=["m-2"])
        self.assertIsNone(error)
        self.assertEqual(resolved["weakened"]["value"], -3)
        self.assertEqual(self.power_of(session, "t"), 3)
        self.assertIn("m-2", p1["zones"]["graveyard"])

    def test_partial_batch_makaboon_and_denblew_watch_discard_and_draw(self):
        makaboon, denblew = "inner-deserts-056", "inner-deserts-026"
        session, p1, p2 = self.make_session(makaboon, denblew)
        session.battlefield = [
            self.field_item("mk", "p1", makaboon, field_zone="interzone"),
            self.field_item("dn", "p1", denblew, field_zone="confrontation"),
        ]
        self.put(p2, "deck", ["m-1", "m-2", "m-3"])
        self.put(p2, "hand", ["m-4", "m-5"])
        self.put(p1, "deck", ["m-6", "m-7"])
        session.rules_engine["observedEvents"] = []
        session.move_zone_card("p2", "deck", "p2", "graveyard", "m-1", "top")
        session.move_zone_card("p2", "deck", "p2", "graveyard", "m-2", "top")
        queued = session.queue_rules_observed_event_triggers(defer=True)
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0]["targets"], [{"kind": "player", "playerId": "p2"}])
        payload = session.apply_rules_action_result({
            **queued[0], "ability": {"result": queued[0]["ability"]["result"]},
        })
        self.assertEqual(payload["choiceKind"], "discard_from_hand")
        self.assertEqual(session.rules_engine["pendingChoice"]["playerId"], "p2")
        session.rules_engine["pendingChoice"] = None
        # Denblew: only draws outside the Recovery Phase, once per turn, opponents only.
        session.current_phase_id = lambda: "recovery_draw"
        session.move_zone_card("p2", "deck", "p2", "hand", "m-3", "bottom")
        self.assertEqual(session.queue_rules_observed_event_triggers(defer=True), [])
        session.current_phase_id = lambda: "confrontation_reaction"
        self.put(p2, "deck", ["m-8", "m-9"])
        session.move_zone_card("p2", "deck", "p2", "hand", "m-8", "bottom")
        queued = session.queue_rules_observed_event_triggers(defer=True)
        self.assertEqual([q["source"]["cardId"] for q in queued], [denblew])
        session.move_zone_card("p2", "deck", "p2", "hand", "m-9", "bottom")
        self.assertEqual(session.queue_rules_observed_event_triggers(defer=True), [])
        session.move_zone_card("p1", "deck", "p1", "hand", "m-6", "bottom")
        self.assertEqual(session.queue_rules_observed_event_triggers(defer=True), [])

    def test_partial_batch_atavic_oppression_end_of_turn_discard_needs_ten_fatigue(self):
        oppression = "a058t24med4h5nx_en"
        session, p1, _p2 = self.make_session(oppression)
        session.card_rules[oppression]["type"] = "persistent_will"
        session.battlefield = [self.field_item("op", "p1", oppression, field_zone="field")]
        session.battlefield[0]["counters"] = {"Fatigue": 9}
        self.assertEqual(session.build_rules_end_turn_field_triggers(), [])
        session.battlefield[0]["counters"] = {"Fatigue": 10}
        queued = session.build_rules_end_turn_field_triggers()
        self.assertEqual(len(queued), 1)
        self.assertTrue(queued[0]["optional"])
        self.put(p1, "hand", ["m-1", "m-2", "m-3"])
        payload = session.apply_rules_action_result({
            **queued[0], "optionalAccepted": True,
            "ability": {"result": queued[0]["ability"]["result"]},
        })
        self.assertEqual(payload["count"], 2)
        choice_id = session.rules_engine["pendingChoice"]["id"]
        error, _ = session.resolve_rules_choice("p1", choice_id, card_ids=["m-1", "m-2", "m-3"])
        self.assertIsNotNone(error)
        error, resolved = session.resolve_rules_choice("p1", choice_id, card_ids=["m-1"])
        self.assertIsNone(error)
        self.assertEqual(resolved["count"], 1)
        self.assertEqual(p1["zones"]["hand"], ["m-2", "m-3"])

    def test_partial_batch_tigrolione_goes_to_the_winner_interzone_instead_of_a_vessel(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker["index"] = session.phase_sequence().index("resolution_compare")
        session.card_rules["m-0"]["power"] = 4
        session.card_rules["tiger"] = {
            "type": "manifestation", "power": 1, "temperaments": ["phlegmatic"],
            "lossDestination": "winner_interzone",
        }
        winner = {"id": "winner", "ownerId": "p1", "cardId": "m-0", "faceUp": True, "fieldZone": "confrontation", "confrontationOrder": 1, "counters": {}}
        loser = {"id": "loser", "ownerId": "p2", "cardId": "tiger", "faceUp": True, "fieldZone": "confrontation", "confrontationOrder": 2, "counters": {}}
        session.battlefield = [winner, loser]
        session.prepare_rules_confrontation_result()
        session.phase_tracker["index"] = session.phase_sequence().index("resolution_move")
        session.begin_rules_confrontation_cleanup()
        self.assertIn(loser, session.battlefield)
        self.assertEqual(loser["controllerId"], "p1")
        self.assertEqual(loser["ownerId"], "p2")
        self.assertEqual(session.rules_field_zone(loser), "interzone")
        self.assertEqual(p1["zones"]["receptacle"], [])

    def test_partial_batch_absent_trinket_returns_when_a_friendly_manifestation_is_targeted(self):
        trinket = "ptwyrc2a26wqwc8_en"
        session, p1, p2 = self.make_session(trinket)
        session.battlefield = [
            self.field_item("tr", "p1", trinket, field_zone="confrontation", isSupport=True),
            self.field_item("mine", "p1", "m-1"),
            self.field_item("theirs", "p2", "m-2"),
        ]
        will_action = {
            "id": "w1", "controllerId": "p2", "kind": "play_card",
            "targets": [self.card_target("theirs", "m-2")],
        }
        self.assertEqual(session.queue_rules_will_target_watchers(will_action), [])
        will_action["targets"] = [self.card_target("mine", "m-1")]
        queued = session.rules_engine["actionStack"]
        before = len(queued)
        result = session.queue_rules_will_target_watchers(will_action)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source"]["cardId"], trinket)
        payload = session.apply_rules_action_result({
            **result[0], "ability": {"result": result[0]["ability"]["result"]},
        })
        self.assertEqual(payload["status"], "moved")
        self.assertIn(trinket, p1["zones"]["hand"])
        self.assertEqual(
            [r["cardId"] for r in session.rules_engine["playRestrictions"]], [trinket]
        )

    def test_partial_batch_yzzit_rolls_before_entering_a_vessel(self):
        session, p1, p2 = self.make_session()
        session.card_rules["yz"] = {
            "type": "manifestation", "power": 1, "temperaments": ["phlegmatic"],
            "vesselEntryRoll": True,
        }
        for roll, zone in ((3, "hand"), (4, "receptacle")):
            item = self.field_item("y", "p2", "yz")
            session.battlefield = [item]
            for target in (p1, p2):
                for z in ("hand", "receptacle"):
                    target["zones"][z] = []
                    target["zoneOwners"][z] = {}
            with unittest.mock.patch("random.randint", return_value=roll):
                movement = session._rules_remove_field_item(item, "p1", "receptacle", "top")
            self.assertEqual(movement["vesselRoll"], roll)
            expected = (p2 if zone == "hand" else p1)["zones"][zone]
            self.assertEqual(expected, ["yz"])
        session.battlefield = [self.field_item("n", "p2", "m-1")]
        movement = session._rules_remove_field_item(session.battlefield[0], "p1", "receptacle", "top")
        self.assertNotIn("vesselRoll", movement)

    def test_partial_batch_jesterina_chains_the_first_manifestation_of_the_opponent_deck(self):
        jesterina = "inner-deserts-065"
        session, p1, p2 = self.manual_batch_session(jesterina, card_type="manifestation")
        self.assertEqual(self.ABILITIES[jesterina][1]["result"], {"kind": "move_source_to_owner_exile"})
        session.card_rules["w1"] = {"type": "ephemeral_will"}
        session.card_rules["w2"] = {"type": "persistent_will"}
        self.put(p2, "deck", ["w1", "w2", "m-3", "m-4"])
        payload, _action = self.run_ability(session, jesterina, [{"kind": "player", "playerId": "p2"}])
        self.assertEqual(payload["status"], "chained")
        self.assertEqual(payload["discarded"], ["w1", "w2"])
        self.assertEqual(sorted(p2["zones"]["graveyard"]), ["w1", "w2"])
        self.assertEqual(p2["zones"]["deck"], ["m-4"])
        chained = next(i for i in session.battlefield if i["cardId"] == "m-3")
        self.assertEqual(chained["controllerId"], "p1")
        self.assertEqual(chained["ownerId"], "p2")
        self.assertTrue(chained["isSupport"])
        self.put(p2, "deck", ["w1"])
        payload, _action = self.run_ability(session, jesterina, [{"kind": "player", "playerId": "p2"}])
        self.assertEqual(payload["status"], "no_manifestation")

    def test_partial_batch_linoleus_adds_points_and_power_without_looping(self):
        linoleus = "inner-deserts-016"
        session, p1, p2 = self.make_session(linoleus)
        session.battlefield = [
            self.field_item("li", "p1", linoleus, field_zone="interzone"),
            self.field_item("ally", "p1", "m-1"),
        ]
        session.rules_engine["observedEvents"] = []
        session.adjust_rules_score("p2", 10)
        self.assertEqual(session.queue_rules_observed_event_triggers(defer=True), [])
        session.adjust_rules_score("p1", 10)
        queued = session.queue_rules_observed_event_triggers(defer=True)
        self.assertEqual(len(queued), 1)
        action = queued[0]
        self.assertEqual(action["targets"], [self.card_target("ally", "m-1")] if action["targets"] else [])
        before = p1["score"]
        session.apply_rules_action_result({
            **action, "ability": {"result": action["ability"]["result"]},
        })
        self.assertEqual(p1["score"], before + 5)
        self.assertEqual(session.rules_engine["observedEvents"], [])

    def test_partial_batch_inert_anchorstone_gains_support_when_its_block_counters_run_out(self):
        stone = "3oiehnpbub1byg6_en"
        session, p1, _p2 = self.make_session(stone)
        session.card_rules[stone]["supportWhenNoCounter"] = "Block"
        item = self.field_item("st", "p1", stone, field_zone="interzone")
        session.battlefield = [item]
        enter, remove = self.ABILITIES[stone]
        def fire(ability):
            session.apply_rules_action_result({
                "id": "a", "controllerId": "p1",
                "source": {"cardId": stone, "itemId": "st"}, "targets": [],
                "ability": {"result": ability["result"]},
            })
        fire(enter)
        self.assertEqual(item["counters"]["Block"], 4)
        self.assertFalse(session.rules_card_can_enter_support(item, "interzone"))
        for _ in range(3):
            fire(remove)
        self.assertFalse(session.rules_card_can_enter_support(item, "interzone"))
        fire(remove)
        fire(remove)
        self.assertEqual(item["counters"]["Block"], 0)
        self.assertTrue(session.rules_card_can_enter_support(item, "interzone"))

    def test_manual_lot_two_tribute_and_trigger_effects(self):
        filth, zozok, zuto, flower = (
            "0tcphe9viq39a5b_en", "inner-deserts-130", "5h7k3m44jsn0esy_en", "inner-deserts-142",
        )
        session, p1, p2 = self.manual_batch_session(filth, zozok, zuto, flower, card_type="manifestation")
        self.put(p2, "hand", ["m-1", "m-2"])
        payload, _ = self.run_ability(session, filth, [{"kind": "player", "playerId": "p2"}])
        self.assertEqual(payload["choiceKind"], "discard_from_hand")
        session.rules_engine["pendingChoice"] = None
        for roll, expected in ((1, 1), (2, 1), (3, 2), (6, 3)):
            with unittest.mock.patch("random.randint", return_value=roll):
                payload, _ = self.run_ability(session, zozok)
            self.assertEqual(payload["essences"], expected)
        retained = [t for t in session.tokens if t.get("isEssence") and t["ownerId"] == "p1"]
        self.assertTrue(all(t["expiresTurn"] == 0 for t in retained))
        self.assertEqual(sum(t["counters"]["essence"] for t in retained), 1 + 1 + 2 + 3)
        session.battlefield = [
            self.field_item("iz", "p1", "m-3", field_zone="interzone"),
            self.field_item("conf", "p1", zuto),
        ]
        payload, _ = self.run_ability(session, zuto, [self.card_target("iz", "m-3")])
        iz = session.find_battlefield_item("iz")
        self.assertTrue(iz["isSupport"])
        self.assertEqual(session.rules_field_zone(iz), "confrontation")
        session.battlefield = [self.field_item("fl", "p1", flower)]
        ability_enter, ability_burst = self.ABILITIES[flower]
        session.apply_rules_action_result({
            "id": "a", "controllerId": "p1", "source": {"cardId": flower, "itemId": "fl"},
            "targets": [], "ability": {"result": ability_enter["result"]},
        })
        self.assertEqual(session.battlefield[0]["counters"]["Berry"], 5)
        before = p2["score"]
        session.apply_rules_action_result({
            "id": "b", "controllerId": "p1", "source": {"cardId": flower, "itemId": "fl"},
            "targets": [], "ability": {"result": ability_burst["result"]},
        })
        self.assertEqual(p2["score"], before + 5)

    def test_manual_lot_two_shattered_memory_compensate_ohmom_walk_quorum(self):
        memory, compensate, ohmom, walk, quorum = (
            "inner-deserts-136", "inner-deserts-149", "bx0uyxxb3c6pas2_en",
            "inner-deserts-071", "201ug66mqu6gslx_en",
        )
        session, p1, p2 = self.manual_batch_session(memory, compensate, ohmom, walk, quorum)
        self.put(p2, "graveyard", ["m-1"])
        self.run_ability(session, memory, [
            {"kind": "zone_card", "containerId": "p2", "zone": "graveyard", "cardId": "m-1", "ownerId": "p2"}
        ])
        self.assertIn("m-1", p2["zones"]["exile"])
        self.assertEqual(self.ABILITIES[memory][1]["sacrificeDestination"], "exile")
        # Compensate refunds the neutralized Persistent Will's tribute as excess essence.
        session.card_rules["pw"] = {"type": "persistent_will", "cost": 3, "temperaments": ["vitreous"]}
        stack_action = {
            "id": "stk", "controllerId": "p2", "kind": "play_card", "sourceOnStack": True,
            "source": {"cardId": "pw", "zone": "hand", "ownerId": "p2", "cardType": "persistent_will"},
            "targets": [], "ability": None, "cost": {},
        }
        session.rules_engine["actionStack"] = [stack_action]
        payload, _ = self.run_ability(
            session, compensate, [{"kind": "stack_action", "actionId": "stk", "cardId": "pw"}]
        )
        self.assertEqual(payload["status"], "neutralized")
        pool = {t["temperament"]: t["counters"]["essence"] for t in session.tokens if t.get("isEssence") and t["ownerId"] == "p2"}
        self.assertEqual(pool, {"vitreous": 3})
        # Walk the Oblivion: discard any number, then lose 5 per card still in hand.
        self.put(p2, "hand", ["m-2", "m-3", "m-4"])
        payload, _ = self.run_ability(session, walk, [{"kind": "player", "playerId": "p2"}])
        self.assertEqual(payload["choiceKind"], "discard_from_hand")
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual((choice["count"], choice["upTo"]), (3, True))
        before = p2.get("score", 0)
        error, resolved = session.resolve_rules_choice("p2", choice["id"], card_ids=["m-2"])
        self.assertIsNone(error)
        self.assertEqual(p2["score"], before - 10)
        self.assertEqual(p2["zones"]["hand"], ["m-3", "m-4"])
        # Quorum: only Wills may be discarded; +3 power each until end of turn.
        session.card_rules["q"] = {"type": "manifestation", "power": 1}
        session.battlefield = [self.field_item("qu", "p1", quorum)]
        session.card_rules[quorum]["power"] = 2
        session.card_rules["will-ephemeral"] = {"type": "ephemeral_will"}
        session.card_rules["will-persistent"] = {"type": "persistent_will"}
        self.put(p1, "hand", ["will-ephemeral", "will-persistent", "m-5"])
        action = {
            "id": "qa", "controllerId": "p1", "optionalAccepted": True,
            "source": {"cardId": quorum, "itemId": "qu"}, "targets": [],
            "ability": {"result": self.ABILITIES[quorum][0]["result"]},
        }
        payload = session.apply_rules_action_result(action)
        self.assertEqual(payload.get("count"), 2, payload)
        choice_id = session.rules_engine["pendingChoice"]["id"]
        error, _ = session.resolve_rules_choice("p1", choice_id, card_ids=["m-5"])
        self.assertIsNotNone(error)
        error, resolved = session.resolve_rules_choice("p1", choice_id, card_ids=["will-ephemeral", "will-persistent"])
        self.assertIsNone(error)
        self.assertEqual(resolved["powerGain"]["value"], 6)
        self.assertEqual(self.power_of(session, "qu"), 8)
        # Ohmom is wired to its own Will plays from the Interzone.
        trigger = self.ABILITIES[ohmom][0]["trigger"]
        self.assertEqual((trigger["event"], trigger["zone"], trigger["eventController"]), ("will_played", "interzone", "owner"))

    def test_manual_lot_three_limbo_entry_triggers(self):
        zombie, memento, tombloom, tenebro = (
            "bu1y6jwy7iaywqu_en", "inner-deserts-063", "inner-deserts-050", "kl0n8mt9m1fwly0_en",
        )
        session, p1, p2 = self.make_session(zombie, memento, tombloom, tenebro)
        session.rules_engine["observedEvents"] = []
        # A discard fires "discarded" and "enters_limbo" for the card itself.
        self.put(p1, "hand", [tombloom])
        session.move_zone_card("p1", "hand", "p1", "graveyard", tombloom, "top")
        queued = session.queue_rules_observed_event_triggers(defer=True)
        # Tombloom's mandatory target opens a target choice instead of queueing directly.
        pending = session.rules_engine["pendingChoice"]
        self.assertEqual(pending["kind"], "trigger_targets")
        queued = [pending["_triggerAction"]]
        session.rules_engine["pendingChoice"] = None
        self.assertEqual([a["ability"]["id"] for a in queued], ["tombloom-exiles-itself-and-weakens"])
        self.assertEqual(queued[0]["source"]["ownerId"], "p1")
        payload = session.apply_rules_action_result({
            **queued[0], "ability": {"result": queued[0]["ability"]["result"]},
        })
        self.assertEqual(payload["status"], "exiled")
        self.assertIn(tombloom, p1["zones"]["exile"])
        self.assertNotIn(tombloom, p1["zones"]["graveyard"])
        # Tenebro rises into Support when discarded.
        self.put(p1, "hand", [tenebro])
        session.move_zone_card("p1", "hand", "p1", "graveyard", tenebro, "top")
        queued = session.queue_rules_observed_event_triggers(defer=True)
        self.assertEqual(len(queued), 1)
        self.assertTrue(queued[0]["optional"])
        session.apply_rules_action_result({
            **queued[0], "optionalAccepted": True,
            "ability": {"result": queued[0]["ability"]["result"]},
        })
        support = next(i for i in session.battlefield if i["cardId"] == tenebro)
        self.assertTrue(support["isSupport"])
        self.assertNotIn(tenebro, p1["zones"]["graveyard"])
        # Zombieswing and Memento only react to entering Limbo, never to other cards.
        self.put(p1, "graveyard", ["m-1", "m-2", "m-3"])
        session.rules_engine["observedEvents"] = []
        self.run_ability(session, zombie, [
            {"kind": "zone_card", "containerId": "p1", "zone": "graveyard", "cardId": "m-1", "ownerId": "p1"}
        ])
        self.assertIn("m-1", p1["zones"]["hand"])
        self.put(p1, "deck", ["m-9"])
        self.run_ability(session, memento, [
            {"kind": "zone_card", "containerId": "p1", "zone": "graveyard", "cardId": cid, "ownerId": "p1"}
            for cid in ("m-2", "m-3", memento)
        ][:2])
        self.assertEqual(sorted(p1["zones"]["deck"]), ["m-2", "m-3", "m-9"])
        self.assertEqual(self.ABILITIES[zombie][0]["trigger"]["event"], "enters_limbo")

    def test_manual_lot_three_board_effects(self):
        watchtower, bond, fintus, gorb, arena, augustus = (
            "tm9kt43d14h9ub1_en", "inner-deserts-020", "0um05ree31uu6e2_en",
            "o4p1r7347u6sff2_en", "4phs0d8l223jk7t_en", "inner-deserts-108",
        )
        session, p1, p2 = self.manual_batch_session(watchtower, bond, fintus, gorb, arena, augustus, card_type="manifestation")
        ability = self.ABILITIES[watchtower][0]
        session.battlefield = [self.field_item("e", "p2", "m-1")]
        session.apply_rules_action_result({
            "id": "w", "controllerId": "p1", "source": {"cardId": watchtower},
            "targets": [self.card_target("e", "m-1")], "ability": {"result": ability["result"]},
        })
        self.assertEqual(self.power_of(session, "e"), 0)
        # Healing Bond: the First Manifestation below the highest base power gets +2 and 10 points.
        session.card_rules["m-2"]["power"] = 5
        session.card_rules["m-3"]["power"] = 2
        session.battlefield = [self.field_item("f1", "p1", "m-2"), self.field_item("f2", "p2", "m-3")]
        session.rules_engine["firstManifestationItemIds"] = {"p1": "f1", "p2": "f2"}
        payload, _ = self.run_ability(session, bond)
        self.assertEqual(payload["playerIds"], ["p2"])
        self.assertEqual(self.power_of(session, "f2"), 4)
        self.assertEqual(p2["score"], 10)
        # Fintus: the next opposing entry into the Confrontation Zone is destroyed.
        self.run_ability(session, fintus)
        entering = self.field_item("enter", "p2", "m-4")
        session.battlefield = [entering]
        self.assertEqual(session.queue_rules_field_zone_entry_triggers(entering, "confrontation"), [])
        self.assertEqual(session.battlefield, [])
        self.assertIn("m-4", p2["zones"]["graveyard"])
        # Gorb locks the controller's Support entries; Wretched Arena locks everyone's.
        self.run_ability(session, gorb)
        self.assertTrue(session.rules_support_entry_locked("p1"))
        self.assertFalse(session.rules_support_entry_locked("p2"))
        self.run_ability(session, arena)
        self.assertTrue(session.rules_support_entry_locked("p2"))
        # Horned Augustus: exile up to three Limbo cards, one 1-power Support token each.
        self.put(p1, "graveyard", ["m-5", "m-6"])
        session.battlefield = []
        self.run_ability(session, augustus, [
            {"kind": "zone_card", "containerId": "p1", "zone": "graveyard", "cardId": cid, "ownerId": "p1"}
            for cid in ("m-5", "m-6")
        ])
        tokens = [i for i in session.battlefield if i.get("isTokenCard")]
        self.assertEqual((len(tokens), sorted(p1["zones"]["exile"])), (2, ["m-5", "m-6"]))
        self.assertTrue(all(t["isSupport"] and t["power"] == 1 for t in tokens))

    def run_ability_at(self, session, card_id, index, targets=None, source=None, trigger=None, controller="p1"):
        ability = self.ABILITIES[card_id][index]
        full = {**ability, "trigger": {**(ability.get("trigger") or {}), **(trigger or {})}}
        return session.apply_rules_action_result({
            "id": f"run-{card_id}-{index}", "controllerId": controller,
            "source": {"cardId": card_id, **(source or {})},
            "targets": targets or [], "ability": {**full, "result": ability["result"]},
        })

    def test_manual_lot_four_vessel_roll_and_memory_effects(self):
        bomb, buddhan, qulom, loop, brood = (
            "7jaany95hy1h5pz_en", "g02zvmqx3loxlcv_en", "rf5srmnqyh235tm_en",
            "1a8wzhi7xhbcenj_en", "je9rwgrjwk97oes_en",
        )
        session, p1, p2 = self.manual_batch_session(bomb, buddhan, qulom, loop, brood, card_type="manifestation")
        # Worm Bomb destroys up to three other manifestations in the vessel it entered.
        self.put(p2, "receptacle", [bomb, "m-1", "m-2", "m-3", "m-4"])
        payload = self.run_ability_at(session, bomb, 0, source={"zone": "receptacle", "containerId": "p2"})
        self.assertEqual(len(payload["cardIds"]), 3)
        self.assertIn(bomb, p2["zones"]["receptacle"])
        self.assertEqual(len(p2["zones"]["receptacle"]), 2)
        # Buddhan the Dark discards a rolled amount and wins for the same amount from opponents.
        self.put(p1, "deck", [f"d-{i}" for i in range(8)])
        self.put(p2, "deck", [f"e-{i}" for i in range(8)])
        session.battlefield = [self.field_item("bd", "p1", buddhan)]
        payload = self.run_ability_at(session, buddhan, 0, source={"itemId": "bd"})
        rolled = payload["discarded"]
        self.assertEqual(len(p1["zones"]["deck"]), 8 - rolled)
        self.assertEqual(self.power_of(session, "bd"), session.card_rules[buddhan]["power"] + rolled)
        self.run_ability_at(session, buddhan, 1, source={"itemId": "bd"})
        self.assertEqual(len(p2["zones"]["deck"]), 8 - rolled)
        # Qu Lom: the end-of-turn roll returns it to hand (even) or exiles it (odd).
        self.put(p1, "graveyard", [qulom])
        memory = session.create_rules_effect_memory(
            "p1", qulom, "return_from_limbo_end_turn", controller_id="p1",
            data={"rollReturnOrExile": True},
        )
        payload = session.apply_rules_action_result({
            "id": "m", "controllerId": "p1", "source": {"cardId": qulom},
            "ability": {"result": {"kind": "resolve_effect_memory", "memoryId": memory["id"]}},
        })
        self.assertEqual(
            qulom in p1["zones"]["hand"] if payload["roll"] % 2 == 0 else qulom in p1["zones"]["exile"], True,
        )
        # Loop only returns the Will after a lost confrontation.
        self.put(p1, "graveyard", [loop])
        memory = session.create_rules_effect_memory(
            "p1", loop, "return_from_limbo_end_turn", controller_id="p1",
            data={"requireLostConfrontation": True, "optional": True},
        )
        session.rules_engine["confrontationResult"] = {"turn": session.phase_tracker["turn"], "loserId": "p2"}
        payload = session.apply_rules_action_result({
            "id": "m2", "controllerId": "p1", "source": {"cardId": loop},
            "ability": {"result": {"kind": "resolve_effect_memory", "memoryId": memory["id"]}},
        })
        self.assertEqual(payload["status"], "condition_failed")
        self.assertIn(loop, p1["zones"]["graveyard"])
        memory = session.create_rules_effect_memory(
            "p1", loop, "return_from_limbo_end_turn", controller_id="p1",
            data={"requireLostConfrontation": True, "optional": True},
        )
        session.rules_engine["confrontationResult"]["loserId"] = "p1"
        payload = session.apply_rules_action_result({
            "id": "m3", "controllerId": "p1", "source": {"cardId": loop},
            "ability": {"result": {"kind": "resolve_effect_memory", "memoryId": memory["id"]}},
        })
        self.assertEqual(payload["kind"], "choice_required")
        # Stampeding Brood leaves two 1-power tokens in the owner's Interzone.
        session.battlefield = []
        self.run_ability_at(session, brood, 0)
        tokens = [i for i in session.battlefield if i.get("isTokenCard")]
        self.assertEqual([t["fieldZone"] for t in tokens], ["interzone", "interzone"])

    def test_manual_lot_four_board_effects(self):
        rancor, tripod, mountain, doom, drain = (
            "inner-deserts-141", "inner-deserts-103", "inner-deserts-123",
            "inner-deserts-038", "inner-deserts-119",
        )
        session, p1, p2 = self.manual_batch_session(rancor, tripod, mountain, doom, drain, card_type="manifestation")
        # Explosive Rancor exiles the Confrontation and Stalemate zones and itself.
        session.battlefield = [
            self.field_item("c1", "p1", "m-1"), self.field_item("c2", "p2", "m-2", field_zone="stalemate"),
            self.field_item("i1", "p1", "m-3", field_zone="interzone"),
            self.field_item("rc", "p1", rancor, field_zone="field"),
        ]
        self.run_ability_at(session, rancor, 0, source={"itemId": "rc"})
        self.assertEqual([i["id"] for i in session.battlefield], ["i1"])
        self.assertEqual(sorted(p1["zones"]["exile"] + p2["zones"]["exile"]), sorted([rancor, "m-1", "m-2"]))
        # Punitive Tripod: +2 power on entering, Interzone power becomes 1 on a loss.
        session.battlefield = [
            self.field_item("tr", "p1", tripod), self.field_item("z1", "p1", "m-4", field_zone="interzone"),
            self.field_item("z2", "p2", "m-5", field_zone="interzone"),
        ]
        base = self.power_of(session, "tr")
        self.run_ability_at(session, tripod, 0, source={"itemId": "tr"})
        self.assertEqual(self.power_of(session, "tr"), base + 2)
        session.card_rules["m-4"]["power"] = 5
        self.run_ability_at(session, tripod, 1, source={"itemId": "tr"})
        self.assertEqual((self.power_of(session, "z1"), self.power_of(session, "z2")), (1, 1))
        # Sacred Mountain exiles the tribute and the other player gains 5 points.
        self.put(p1, "graveyard", ["m-6"])
        self.run_ability_at(session, mountain, 0, trigger={
            "relatedCardId": "m-6", "relatedOwnerId": "p1", "eventControllerId": "p1",
        })
        self.assertIn("m-6", p1["zones"]["exile"])
        self.assertEqual((p1["score"], p2["score"]), (0, 5))
        # Referen-Doom exiles Limbo Wills for +1 power each.
        session.card_rules["will-1"] = {"type": "ephemeral_will", "temperaments": [], "power": 0}
        session.card_rules["will-2"] = {"type": "persistent_will", "temperaments": [], "power": 0}
        self.put(p1, "graveyard", ["will-1", "will-2", "m-7"])
        session.battlefield = [self.field_item("rd", "p1", doom)]
        base = self.power_of(session, "rd")
        self.run_ability_at(session, doom, 0, source={"itemId": "rd"}, targets=[
            {"kind": "zone_card", "containerId": "p1", "zone": "graveyard", "cardId": cid, "ownerId": "p1"}
            for cid in ("will-1", "will-2", "m-7")
        ])
        self.assertEqual(self.power_of(session, "rd"), base + 2)
        self.assertIn("m-7", p1["zones"]["graveyard"])
        # Drain the Substance removes all excess essence and adds it to the target.
        session.add_rules_excess_essence("p1", [{"temperament": "hollow", "amount": 3}])
        session.add_rules_excess_essence("p2", [{"temperament": "choleric", "amount": 2}])
        base = self.power_of(session, "rd")
        self.run_ability_at(session, drain, 0, targets=[self.card_target("rd", doom)])
        self.assertEqual(self.power_of(session, "rd"), base + 5)
        self.assertEqual([t for t in session.tokens if t.get("isEssence")], [])

    def test_manual_lot_five_end_of_game_and_loss_destination(self):
        phimosino, lover, chariot, kox = (
            "inner-deserts-035", "2z1svoyvo77ta03_en", "inner-deserts-132", "40lqhpf5xr5v5sk_en",
        )
        session, p1, p2 = self.manual_batch_session(phimosino, lover, chariot, kox, card_type="manifestation")
        for cid in ("m-1", "m-2", "m-3"):
            session.card_rules[cid]["power"] = 2
        session.card_rules["m-3"]["power"] = 4
        self.put(p1, "deck", [phimosino])
        # Piercing Lover sits in p2's vessel (owned by p1): p2 loses 5 per manifestation with base power <= 2 there.
        self.put(p2, "receptacle", [lover, "m-1", "m-2", "m-3"])
        p2["zoneOwners"]["receptacle"] = {lover: "p1", "m-1": "p1", "m-2": "p1", "m-3": "p1"}
        scores = session.calculate_final_scores()["scores"]
        self.assertEqual(scores["p1"]["endGamePoints"], 50)
        self.assertEqual(scores["p2"]["endGamePoints"], -5 * 3)  # Lover itself (power from catalog) counts too if <= 2
        # Losers' Chariot goes to its owner's Interzone instead of the winner's vessel.
        session.card_rules[chariot]["lossDestination"] = "own_interzone"
        session.battlefield = [self.field_item("lc", "p1", chariot)]
        session.rules_engine["confrontationResult"] = {
            "turn": session.phase_tracker["turn"], "status": "effects", "winnerId": "p2",
            "loserId": "p1", "participantItemIds": ["lc"], "stalemate": False,
        }
        session.begin_rules_confrontation_cleanup()
        self.assertEqual(session.battlefield[0]["fieldZone"], "interzone")
        self.assertEqual(session.battlefield[0]["controllerId"] if "controllerId" in session.battlefield[0] else "p1", "p1")
        self.assertNotIn(chariot, p2["zones"]["receptacle"])
        # Kox gifts opponents 50 points on entering the field.
        payload = self.run_ability_at(session, kox, 0, source={"itemId": "x"})
        self.assertEqual(p2["score"], 50)

    def test_shababba_reorders_the_deck_top_at_end_of_turn_only_from_the_interzone(self):
        shababba = "i7h2c7ku2gt1yvg_en"
        session, p1, _p2 = self.manual_batch_session(shababba, card_type="manifestation")
        self.put(p1, "deck", ["m-1", "m-2", "m-3", "m-4", "m-5"])
        session.battlefield = [self.field_item("sh", "p1", shababba, field_zone="field")]
        self.assertEqual(session.build_rules_end_turn_field_triggers(), [])
        session.battlefield = [self.field_item("sh", "p1", shababba, field_zone="interzone")]
        queued = session.build_rules_end_turn_field_triggers()
        self.assertEqual(len(queued), 1)
        payload = session.apply_rules_action_result(queued[0])
        self.assertEqual(payload["choiceKind"], "deck_reorder")

    def first_stone_flow(self, p2_hand):
        stone = "4rnpxnnceu8x9o9_en"
        session, p1, p2 = self.make_session(stone)
        session.card_rules[stone]["supportFromHand"] = True
        session.phase_tracker["index"] = session.phase_sequence().index("confrontation_reaction")
        session.battlefield = [
            self.field_item("base-p1", "p1", "m-5"),
            self.field_item("base-p2", "p2", "m-6"),
        ]
        self.put(p1, "hand", [stone])
        self.put(p2, "hand", p2_hand)
        session.rules_engine["priorityPlayerId"] = "p1"
        error, _action = session.declare_rules_action(
            "p1", "First Stone in Support", kind="play_card", as_support=True,
            source={"cardId": stone, "zone": "hand"}, placement={"x": 400, "y": 500},
        )
        self.assertIsNone(error)
        session.pass_rules_priority("p2")
        error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error)
        return session, p1, p2, resolution

    def test_first_stone_played_in_support_makes_the_opponent_chain(self):
        session, p1, p2, _resolution = self.first_stone_flow(["m-1", "field-will"])
        stack = session.rules_engine["actionStack"]
        self.assertEqual([a["source"]["cardId"] for a in stack], ["4rnpxnnceu8x9o9_en"])
        session.pass_rules_priority("p2")
        error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error)
        self.assertEqual(resolution["action"]["effectResult"]["choiceKind"], "chain_manifestation")
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual((choice["playerId"], choice["optional"]), ("p2", False))
        error, chained = session.resolve_rules_choice(
            "p2", choice["id"], ["m-1"], placement={"x": 700, "y": 500}
        )
        self.assertIsNone(error)
        item = session.find_battlefield_item(chained["itemId"])
        self.assertEqual(item["controllerId"], "p2")
        self.assertTrue(item["isSupport"])
        self.assertEqual(p2["zones"]["hand"], ["field-will"])
        self.assertEqual(p1["zones"]["hand"], [])

    def test_first_stone_reveals_the_opponent_hand_when_they_cannot_chain(self):
        session, _p1, p2, _resolution = self.first_stone_flow(["field-will"])
        session.pass_rules_priority("p2")
        error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error)
        result = resolution["action"]["effectResult"]
        self.assertEqual(result["status"], "no_eligible_card")
        self.assertEqual(result["handProofs"], [{"playerId": "p2", "cardIds": ["field-will"]}])
        self.assertIsNone(session.rules_engine["pendingChoice"])

    def test_forfog_and_ehgog_punish_discards(self):
        forfog, ehgog = "d6jip43i66i34xk_en", "fknxa83uens94ju_en"
        session, p1, p2 = self.watcher_session(forfog, ehgog)
        self.put(p1, "hand", ["m-1"])
        self.put(p2, "hand", ["m-2"])
        session.battlefield.append(self.field_item("foe", "p2", "m-3"))
        session.move_zone_card("p1", "hand", "p1", "graveyard", "m-1")
        queued = session.queue_rules_observed_event_triggers(defer=True)
        self.assertEqual(queued, [])
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(
            (choice["kind"], choice["sourceCardId"]), ("trigger_targets", ehgog)
        )
        session.rules_engine["pendingChoice"] = None
        session.move_zone_card("p2", "hand", "p2", "graveyard", "m-2")
        queued = session.queue_rules_observed_event_triggers(defer=True)
        forfog_action = next(a for a in queued if a["source"]["cardId"] == forfog)
        self.assertEqual(forfog_action["targets"], [{"kind": "player", "playerId": "p2"}])
        session.apply_rules_action_result(forfog_action)
        self.assertEqual(p2["score"], -5)

    def test_shuk_makes_the_other_players_lose_points_when_you_lose_some(self):
        shuk = "16hmmz3fw32r27q_en"
        session, p1, p2 = self.watcher_session(shuk)
        session.adjust_rules_score("p2", -3)
        self.assertEqual(session.queue_rules_observed_event_triggers(defer=True), [])
        session.adjust_rules_score("p1", -3)
        queued = session.queue_rules_observed_event_triggers(defer=True)
        self.assertEqual(len(queued), 1)
        session.apply_rules_action_result(queued[0])
        self.assertEqual((p1["score"], p2["score"]), (-3, -8))

    def test_agrupol_counts_owned_manifestations_in_every_vessel(self):
        agrupol = "j2a7x783j5ql0ab_en"
        session, p1, p2 = self.watcher_session(agrupol)
        self.put(p1, "receptacle", {"m-1": "p1", "m-2": "p2"})
        self.put(p2, "receptacle", {"m-3": "p1", "m-4": "p2"})
        action = {
            "controllerId": "p1", "targets": [], "source": {"cardId": agrupol},
            "ability": {"result": self.ABILITIES[agrupol][0]["result"]},
        }
        session.apply_rules_action_result(action)
        self.assertEqual(p1["score"], 10)

    def test_reap_what_you_have_sown_scores_per_manifestation_and_draws_per_free_space(self):
        reap = "8xi4zh0ekdl42me_en"
        session, p1, _p2 = self.make_session()
        session.battlefield = [
            self.field_item("a", "p1", "m-1", field_zone="interzone"),
            self.field_item("b", "p1", "m-2", field_zone="interzone"),
            self.field_item("foe", "p2", "m-3", field_zone="interzone"),
        ]
        self.put(p1, "deck", ["m-5", "m-6", "m-7"])
        cleaned = session.clean_rules_action_result(self.ABILITIES[reap][0]["result"])
        session.apply_rules_action_result({
            "controllerId": "p1", "targets": [], "source": {"cardId": reap},
            "ability": {"result": cleaned},
        })
        self.assertEqual(p1["score"], 10)
        self.assertEqual(p1["zones"]["hand"], ["m-5"])

    def test_interzone_capacity_grows_with_tong_and_cozy_bunk(self):
        tong, bunk = "5enwyodanyu1it8_en", "gybb0ktsth7clz5_en"
        session, _p1, _p2 = self.watcher_session(tong, zone="confrontation")
        self.assertEqual(session.rules_interzone_capacity("p1"), 6)
        self.assertEqual(session.rules_interzone_capacity("p2"), 3)
        session.card_rules[bunk] = {
            "type": "persistent_will",
            "passiveEffects": [self.ABILITIES[bunk][0]["passiveEffect"]],
        }
        session.battlefield.append(self.field_item("bunk", "p1", bunk, field_zone="field"))
        self.assertEqual(session.rules_interzone_capacity("p1"), 7)

    def test_lombriculpop_and_pachywyrm_score_the_excess_over_the_opposing_first(self):
        lombri, pachy = "inner-deserts-014", "9ypw4x4igfon1qi_en"
        session, p1, p2 = self.watcher_session(lombri, pachy, zone="confrontation")
        session.card_rules["m-3"]["power"] = 2
        session.battlefield.append(self.field_item("first", "p2", "m-3"))
        session.rules_engine["firstManifestationItemIds"] = {"p2": "first"}
        for card_id, who in ((lombri, p1), (pachy, p2)):
            result = self.ABILITIES[card_id][0]["result"]
            session.apply_rules_action_result({
                "controllerId": "p1", "source": {
                    "cardId": card_id, "itemId": f"w-{card_id}",
                },
                "targets": [{"kind": "player", "playerId": "p2"}],
                "ability": {"result": session.clean_rules_action_result(result)
                            or session.clean_rules_trigger_result(result)},
            })
        self.assertEqual(p1["score"], 5)
        self.assertEqual(p2["score"], -5)
        session.card_rules["m-3"]["power"] = 9
        session.apply_rules_action_result({
            "controllerId": "p1", "source": {"cardId": lombri, "itemId": f"w-{lombri}"},
            "targets": [{"kind": "player", "playerId": "p2"}],
            "ability": {"result": session.clean_rules_action_result(
                self.ABILITIES[lombri][0]["result"])},
        })
        self.assertEqual(p1["score"], 5)

    def test_honor_and_respect_needs_exactly_one_confrontation_manifestation(self):
        honor = "y4muuingw5y9l7z_en"
        session, p1, _p2 = self.make_session()
        session.card_rules[honor] = {
            "type": "persistent_will",
            "triggeredAbilities": self.ABILITIES[honor],
        }
        session.battlefield = [
            self.field_item("honor", "p1", honor, field_zone="field"),
            self.field_item("a", "p1", "m-1"),
            self.field_item("foe", "p2", "m-3"),
        ]
        self.set_outcome(session, "p1", "p2", "a", "foe")
        queued = [
            a for a in session.queue_rules_confrontation_win_triggers(defer=True)
            if a["source"]["cardId"] == honor
        ]
        self.assertEqual(len(queued), 1)
        session.battlefield.append(self.field_item("b", "p1", "m-2"))
        self.assertEqual([
            a for a in session.queue_rules_confrontation_win_triggers(defer=True)
            if a["source"]["cardId"] == honor
        ], [])

    def test_soul_borer_drains_the_vessel_owner_every_turn(self):
        borer = "wfxxi0znaojxiti_en"
        session, p1, p2 = self.make_session()
        session.card_rules[borer] = {
            "type": "manifestation", "power": 1,
            "triggeredAbilities": self.ABILITIES[borer],
        }
        self.put(p1, "receptacle", {borer: "p1"})
        self.assertEqual(session.queue_rules_beginning_turn_triggers(), [])
        self.put(p1, "receptacle", {})
        self.put(p2, "receptacle", {borer: "p1"})
        session.rules_engine["beginningTriggersTurn"] = None
        queued = session.queue_rules_beginning_turn_triggers()
        self.assertEqual(len(queued), 1)
        session.apply_rules_action_result(queued[0])
        self.assertEqual((p1["score"], p2["score"]), (0, -5))

    def test_solenero_returns_a_limbo_card_only_when_it_loses(self):
        session, p1, p2 = self.make_session(self.SOLENERO)
        self.put(p1, "graveyard", ["m-3"])
        self.put(p2, "graveyard", ["m-4"])
        session.battlefield = [self.field_item("solenero", "p1", self.SOLENERO)]

        self.set_outcome(session, "p1", "p2", "solenero")
        self.assertEqual(session.queue_rules_confrontation_win_triggers(), [])

        self.set_outcome(session, "p2", "p1", "solenero")
        self.assertEqual(len(session.queue_rules_confrontation_win_triggers()), 1)
        error, _ = self.accept_and_target(session, "p1", [{
            "kind": "zone_card", "containerId": "p2", "zone": "graveyard",
            "cardId": "m-4", "ownerId": "p2",
        }])
        self.assertIn("you own", error)
        error, _ = self.accept_and_target(session, "p1", [{
            "kind": "zone_card", "containerId": "p1", "zone": "graveyard",
            "cardId": "m-3", "ownerId": "p1",
        }])
        self.assertIsNone(error)
        self.resolve_stack(session)
        self.assertEqual(p1["zones"]["hand"], ["m-3"])
        self.assertEqual(p1["zones"]["graveyard"], [])
        self.assertEqual(p2["zones"]["graveyard"], ["m-4"])

    def test_solenero_trigger_can_be_declined(self):
        session, p1, _p2 = self.make_session(self.SOLENERO)
        self.put(p1, "graveyard", ["m-3"])
        session.battlefield = [self.field_item("solenero", "p1", self.SOLENERO)]
        self.set_outcome(session, "p2", "p1", "solenero")
        session.queue_rules_confrontation_win_triggers()
        choice = session.rules_engine["pendingChoice"]
        self.assertIsNone(session.resolve_rules_choice(
            "p1", choice["id"], option="decline"
        )[0])
        self.assertEqual(session.rules_engine["actionStack"], [])
        self.assertEqual(p1["zones"]["graveyard"], ["m-3"])

    def test_sallow_thief_retrieves_only_own_cards_from_an_opponent_vessel(self):
        session, p1, p2 = self.make_session(self.SALLOW_THIEF)
        self.put(p2, "receptacle", {"m-5": "p1", "m-6": "p2"})
        self.put(p1, "receptacle", {"m-7": "p1"})
        session.battlefield = [self.field_item("thief", "p1", self.SALLOW_THIEF)]
        self.set_outcome(session, "p1", "p2", "thief")
        session.queue_rules_confrontation_win_triggers()

        def target(container, card_id, owner):
            return [{
                "kind": "zone_card", "containerId": container, "zone": "receptacle",
                "cardId": card_id, "ownerId": owner,
            }]
        self.assertIn("you own", self.accept_and_target(session, "p1", target("p2", "m-6", "p2"))[0])
        self.assertIn("opponent's zone", self.accept_and_target(session, "p1", target("p1", "m-7", "p1"))[0])
        self.assertIsNone(self.accept_and_target(session, "p1", target("p2", "m-5", "p1"))[0])
        self.resolve_stack(session)
        self.assertEqual(p1["zones"]["hand"], ["m-5"])
        self.assertEqual(p2["zones"]["receptacle"], ["m-6"])
        self.assertEqual(p1["zones"]["receptacle"], ["m-7"])

    def test_knobbly_colossus_destroys_an_opponent_will_or_manifestation(self):
        session, p1, p2 = self.make_session(self.KNOBBLY)
        session.battlefield = [
            self.field_item("knobbly", "p1", self.KNOBBLY),
            self.field_item("mine", "p1", "m-1", "interzone"),
            self.field_item("theirs", "p2", "m-2", "interzone"),
            self.field_item("their-will", "p2", "field-will", None),
        ]
        self.set_outcome(session, "p1", "p2", "knobbly")
        session.queue_rules_confrontation_win_triggers()

        def target(item_id, card_id):
            return [{"kind": "card", "itemId": item_id, "cardId": card_id}]
        self.assertIn("opponent", self.accept_and_target(session, "p1", target("mine", "m-1"))[0])
        self.assertIsNone(self.accept_and_target(session, "p1", target("their-will", "field-will"))[0])
        self.resolve_stack(session)
        self.assertIsNone(session.find_battlefield_item("their-will"))
        self.assertIsNotNone(session.find_battlefield_item("theirs"))
        self.assertIn("field-will", p2["zones"]["graveyard"])

    def test_borombo_destroys_an_opposing_confrontation_card_when_it_loses(self):
        session, p1, p2 = self.make_session(self.BOROMBO)
        session.battlefield = [
            self.field_item("borombo", "p1", self.BOROMBO),
            self.field_item("winner", "p2", "m-2"),
            self.field_item("spare", "p2", "m-3", "interzone"),
        ]
        self.set_outcome(session, "p2", "p1", "borombo", "winner")
        session.queue_rules_confrontation_win_triggers()
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "trigger_targets")
        error, _ = session.resolve_rules_choice("p1", choice["id"], targets=[
            {"kind": "card", "itemId": "spare", "cardId": "m-3"},
        ])
        self.assertIn("different field zone", error)
        error, _ = session.resolve_rules_choice("p1", choice["id"], targets=[
            {"kind": "card", "itemId": "winner", "cardId": "m-2"},
        ])
        self.assertIsNone(error)
        self.resolve_stack(session)
        self.assertIsNone(session.find_battlefield_item("winner"))
        self.assertEqual(p2["zones"]["graveyard"], ["m-2"])

    def test_tardigramo_exiles_a_random_vessel_manifestation_of_the_opponent(self):
        session, p1, p2 = self.make_session(self.TARDIGRAMO)
        self.put(p2, "receptacle", ["m-8"])
        session.battlefield = [self.field_item("tardi", "p1", self.TARDIGRAMO)]
        self.set_outcome(session, "p1", "p2", "tardi")
        session.queue_rules_confrontation_win_triggers()
        error, _ = self.accept_and_target(session, "p1", [{"kind": "player", "playerId": "p1"}])
        self.assertIn("opponent", error)
        error, _ = self.accept_and_target(session, "p1", [{"kind": "player", "playerId": "p2"}])
        self.assertIsNone(error)
        self.resolve_stack(session)
        self.assertEqual(p2["zones"]["receptacle"], [])
        self.assertEqual(p2["zones"]["exile"], ["m-8"])

    def test_tardigramo_with_an_empty_vessel_resolves_without_a_card(self):
        session, p1, p2 = self.make_session(self.TARDIGRAMO)
        session.battlefield = [self.field_item("tardi", "p1", self.TARDIGRAMO)]
        self.set_outcome(session, "p1", "p2", "tardi")
        session.queue_rules_confrontation_win_triggers()
        self.assertIsNone(self.accept_and_target(session, "p1", [{"kind": "player", "playerId": "p2"}])[0])
        self.resolve_stack(session)
        self.assertEqual(p2["zones"]["exile"], [])

    def test_floating_dancer_scores_five_per_own_interzone_manifestation(self):
        session, p1, p2 = self.make_session(self.DANCER)
        session.battlefield = [
            self.field_item("dancer", "p1", self.DANCER),
            self.field_item("i1", "p1", "m-1", "interzone"),
            self.field_item("i2", "p1", "m-2", "interzone"),
            self.field_item("i3", "p1", "m-3", "interzone"),
            self.field_item("theirs", "p2", "m-4", "interzone"),
        ]
        self.set_outcome(session, "p1", "p2", "dancer")
        self.assertEqual(len(session.queue_rules_confrontation_win_triggers()), 1)
        self.resolve_stack(session)
        self.assertEqual(p1["score"], 15)
        self.assertEqual(p2["score"], 0)

    def test_floating_dancer_scores_nothing_without_an_interzone_or_a_win(self):
        session, p1, _p2 = self.make_session(self.DANCER)
        session.battlefield = [self.field_item("dancer", "p1", self.DANCER)]
        self.set_outcome(session, "p1", "p2", "dancer")
        session.queue_rules_confrontation_win_triggers()
        self.resolve_stack(session)
        self.assertEqual(p1["score"], 0)
        self.set_outcome(session, "p2", "p1", "dancer")
        self.assertEqual(session.queue_rules_confrontation_win_triggers(), [])

    def test_flem_family_plays_into_the_interzone_only_in_the_end_phase(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["flem"] = {
            "type": "manifestation", "power": 1, "temperaments": ["phlegmatic"],
            "canPayTributeFromInterzone": True, "endPhaseInterzonePlay": True,
        }
        p1["zones"]["hand"] = ["flem", "m-1"]
        session.rules_engine["priorityPlayerId"] = "p1"

        for phase_id in ("recovery_end", "confrontation_choose", "resolution_effects"):
            session.phase_tracker["index"] = ADVANCED_PHASES.index(phase_id)
            self.assertIn(
                "End Phase", session.rules_support_from_hand_error("p1", "flem"),
                phase_id,
            )
        session.phase_tracker["index"] = ADVANCED_PHASES.index("end_actions")
        self.assertIsNone(session.rules_support_from_hand_error("p1", "flem"))
        # An ordinary Manifestation still cannot be played from Hand then.
        self.assertIsNotNone(session.rules_support_from_hand_error("p1", "m-1"))

        session.rules_engine["priorityPlayerId"] = "p2"
        self.assertEqual(
            session.rules_support_from_hand_error("p1", "flem"),
            "You do not have priority.",
        )
        session.rules_engine["priorityPlayerId"] = "p1"
        session.rules_engine["actionStack"] = [{"id": "pending"}]
        self.assertIn("Stack", session.rules_support_from_hand_error("p1", "flem"))
        session.rules_engine["actionStack"] = []
        session.battlefield = [
            self.interzone_item(f"slot-{index}", f"m-{index + 2}") for index in range(3)
        ]
        self.assertEqual(
            session.rules_support_from_hand_error("p1", "flem"),
            "Your Interzone is full.",
        )

    @staticmethod
    def interzone_item(item_id, card_id):
        return {
            "id": item_id, "ownerId": "p1", "cardId": card_id, "faceUp": True,
            "fieldZone": "interzone", "counters": {},
        }

    def test_flem_in_the_interzone_pays_its_printed_power_as_tribute(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["flem"] = {
            "type": "manifestation", "power": 1, "temperaments": ["phlegmatic"],
            "canPayTributeFromInterzone": True, "endPhaseInterzonePlay": True,
        }
        flem = [{"cardId": "flem", "zone": "battlefield"}]
        self.assertTrue(session.rules_manifestations_cover(flem, {"phlegmatic": 1})[0])
        self.assertFalse(session.rules_manifestations_cover(flem, {"phlegmatic": 2})[0])

    def power_of(self, session, item_id):
        return session.rules_manifestation_characteristics(
            session.find_battlefield_item(item_id)
        )["power"]

    def test_kelona_loses_one_power_per_limbo_card_down_to_minus_six(self):
        session, p1, _p2 = self.make_session()
        session.card_rules["kelona"] = {
            "type": "manifestation", "power": 9, "canPayTribute": False,
            "continuousPowerRules": [
                {"kind": "self_per_controller_limbo_card", "value": -1, "floor": -6},
            ],
        }
        session.battlefield = [self.field_item("kelona", "p1", "kelona")]
        self.put(p1, "graveyard", ["m-1", "m-2", "will-ephemeral"])
        self.assertEqual(self.power_of(session, "kelona"), 6)
        self.put(p1, "graveyard", [f"m-{index}" for index in range(10)])
        self.assertEqual(self.power_of(session, "kelona"), 3)
        session.battlefield[0]["fieldZone"] = "interzone"
        self.assertEqual(self.power_of(session, "kelona"), 9)

    def test_lucerco_counts_the_opponents_confrontation_manifestations(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["lucerco"] = {
            "type": "manifestation", "power": 2, "continuousPowerRules": [
                {"kind": "self_per_opponent_confrontation_manifestation", "value": 1},
            ],
        }
        session.battlefield = [
            self.field_item("lucerco", "p1", "lucerco"),
            self.field_item("mine", "p1", "m-1"),
            self.field_item("theirs-1", "p2", "m-2"),
            self.field_item("theirs-2", "p2", "m-3", isSupport=True),
            self.field_item("theirs-parked", "p2", "m-4", "interzone"),
        ]
        self.assertEqual(self.power_of(session, "lucerco"), 4)

    def test_vengeful_vilupera_counts_own_manifestations_in_every_vessel(self):
        session, p1, p2 = self.make_session()
        session.card_rules["vilupera"] = {
            "type": "manifestation", "power": 1, "continuousPowerRules": [
                {"kind": "self_per_owned_vessel_manifestation", "value": 1},
            ],
        }
        session.battlefield = [self.field_item("vilupera", "p1", "vilupera")]
        self.put(p2, "receptacle", {"m-1": "p1", "m-2": "p1", "m-3": "p2"})
        self.put(p1, "receptacle", {"m-4": "p1", "m-5": "p2"})
        self.assertEqual(self.power_of(session, "vilupera"), 4)

    def test_prospero_boosts_only_the_first_manifestation_while_in_the_interzone(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["prospero"] = {
            "type": "manifestation", "power": 1, "continuousPowerRules": [
                {"kind": "first_manifestation_per_interzone_manifestation", "value": 1},
            ],
        }
        session.battlefield = [
            self.field_item("prospero", "p1", "prospero", "interzone"),
            self.field_item("i-1", "p1", "m-1", "interzone"),
            self.field_item("first", "p1", "m-2"),
            self.field_item("support", "p1", "m-3", isSupport=True),
            self.field_item("their-first", "p2", "m-4"),
        ]
        session.rules_engine["firstManifestationItemIds"] = {"p1": "first", "p2": "their-first"}
        self.assertEqual(self.power_of(session, "first"), 3)
        self.assertEqual(self.power_of(session, "support"), 1)
        self.assertEqual(self.power_of(session, "their-first"), 1)
        session.find_battlefield_item("prospero")["fieldZone"] = "confrontation"
        self.assertEqual(self.power_of(session, "first"), 1)

    def test_bell_boosts_a_lone_confrontation_manifestation_from_the_interzone(self):
        session, _p1, _p2 = self.make_session()
        session.card_rules["bell"] = {
            "type": "manifestation", "power": 1, "continuousPowerRules": [
                {"kind": "only_friendly_confrontation_manifestation", "value": 2},
            ],
        }
        session.battlefield = [
            self.field_item("bell", "p1", "bell", "interzone"),
            self.field_item("lone", "p1", "m-1"),
            self.field_item("theirs", "p2", "m-2"),
        ]
        self.assertEqual(self.power_of(session, "lone"), 3)
        self.assertEqual(self.power_of(session, "theirs"), 1)
        session.battlefield.append(self.field_item("second", "p1", "m-3", isSupport=True))
        self.assertEqual(self.power_of(session, "lone"), 1)
        self.assertEqual(self.power_of(session, "second"), 1)

    def test_plea_for_generosity_scores_per_non_token_manifestation_of_the_target(self):
        session, p1, p2 = self.make_session()
        ability = next(
            entry for entry in self.ABILITIES["31k2b7hz7ockvvn_en"]
            if entry["id"] == "score-per-target-player-confrontation-manifestation"
        )
        cleaned = session.clean_rules_action_result(ability["result"])
        self.assertEqual(cleaned, ability["result"])
        session.battlefield = [
            self.field_item("a", "p2", "m-1"),
            self.field_item("b", "p2", "m-2", isSupport=True),
            self.field_item("token", "p2", "m-3", isTokenCard=True),
            self.field_item("copy", "p2", "m-4", isCopy=True),
            self.field_item("parked", "p2", "m-5", "interzone"),
            self.field_item("mine", "p1", "m-6"),
        ]
        session.rules_engine["priorityPlayerId"] = "p1"

        def play(target_player_id):
            action = {
                "id": f"plea-{target_player_id}", "controllerId": "p1",
                "source": {"cardId": "m-0"},
                "targets": [{"kind": "player", "playerId": target_player_id}],
                "ability": {"id": ability["id"], "result": cleaned},
            }
            return session.apply_rules_action_result(action)

        result = play("p2")
        self.assertEqual((result["kind"], result["delta"]), ("score", 10))
        self.assertEqual(p1["score"], 10)
        play("p1")
        self.assertEqual(p1["score"], 15)
        self.assertEqual(p2["score"], 0)

    def test_incinerate_and_punish_the_winners_destroy_only_matching_manifestations(self):
        session, p1, p2 = self.make_session()
        session.card_rules["adam"] = {
            "type": "manifestation", "power": 1, "adamant": True,
        }

        def play(ability_id, card_id):
            ability = next(
                entry for entry in self.ABILITIES[card_id]
                if entry["id"] == ability_id
            )
            cleaned = session.clean_rules_action_result(ability["result"])
            self.assertEqual(cleaned, ability["result"])
            return session.apply_rules_action_result({
                "id": "will", "controllerId": "p1", "source": {"cardId": "m-0"},
                "targets": [], "ability": {"id": ability_id, "result": cleaned},
            })

        session.battlefield = [
            self.field_item("old-support", "p2", "m-1", isSupport=True),
            self.field_item("new-support", "p2", "m-2", isSupport=True),
            self.field_item("new-adamant", "p2", "adam", isSupport=True),
            self.field_item("mine-support", "p1", "m-3", isSupport=True),
            self.field_item("plain", "p2", "m-4"),
        ]
        turn = session.phase_tracker["turn"]
        session.rules_engine["supportEntries"] = [
            {"turn": turn - 1, "itemId": "old-support", "controllerId": "p2"},
            {"turn": turn, "itemId": "new-support", "controllerId": "p2"},
            {"turn": turn, "itemId": "new-adamant", "controllerId": "p2"},
            {"turn": turn, "itemId": "mine-support", "controllerId": "p1"},
        ]
        result = play("destroy-manifestations-that-entered-support", "4naoqbqz6ebozj5_en")
        self.assertEqual(len(result["destroyed"]), 3)
        remaining = {item["id"] for item in session.battlefield}
        self.assertEqual(remaining, {"old-support", "plain"})
        self.assertIn("m-2", p2["zones"]["graveyard"])

        session.rules_engine["confrontationResult"] = None
        play("destroy-confrontation-winners", "nupb1i59d98g3md_en")
        self.assertEqual(len(session.battlefield), 2)
        self.set_outcome(session, "p2", "p1", "plain", "old-support")
        self.assertIsNotNone(play("destroy-confrontation-winners", "nupb1i59d98g3md_en"))
        remaining = {item["id"] for item in session.battlefield}
        self.assertEqual(remaining, set())

    def test_mind_parasite_chains_from_limbo_and_exiles_the_chain_on_win(self):
        mind_parasite = "ydijk2x1ne8w93g_en"
        session, p1, _p2 = self.make_session(mind_parasite)
        self.put(p1, "graveyard", ["m-3"])
        item = self.field_item("parasite", "p1", mind_parasite)
        session.battlefield = [item]

        session.queue_rules_field_zone_entry_triggers(item, "confrontation")
        optional_choice = session.rules_engine["pendingChoice"]
        self.assertEqual(optional_choice["kind"], "optional_stack_action")
        self.assertIsNone(session.resolve_rules_choice(
            "p1", optional_choice["id"], option="accept"
        )[0])
        self.resolve_stack(session)
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["fromZone"], "graveyard")
        error, chained = session.resolve_rules_choice(
            "p1", choice["id"], ["m-3"], placement={"x": 400, "y": 500},
        )
        self.assertIsNone(error)
        revived = session.find_battlefield_item(chained["itemId"])
        self.assertTrue(revived["isSupport"])
        memories = session.rules_engine["effectMemories"]
        self.assertEqual(
            [(m["kind"], m["cardId"], m["data"]["itemId"]) for m in memories],
            [("win_destination_exile", "m-3", revived["id"])],
        )
        self.assertEqual(p1["zones"]["graveyard"], [])

    def test_reforging_fate_targets_any_limbo_manifestation_and_exiles_it_on_win(self):
        session, p1, p2 = self.make_session()
        ability = next(
            entry for entry in self.ABILITIES["z2fen73ktw8pbqz_en"]
            if entry["id"] == "reforging-fate-support-from-limbo"
        )
        self.put(p2, "graveyard", ["m-9"])
        own = [{"kind": "zone_card", "containerId": "p2", "zone": "graveyard", "cardId": "m-9", "ownerId": "p2"}]
        self.assertIsNone(session.rules_ability_targets_error(ability["targets"], own, "p1"))
        wrong_zone = [{**own[0], "zone": "receptacle"}]
        self.assertIsNotNone(session.rules_ability_targets_error(ability["targets"], wrong_zone, "p1"))
        action = {
            "id": "fate", "controllerId": "p1", "source": {"cardId": "m-0"},
            "targets": own, "ability": {"id": ability["id"], "result": ability["result"]},
        }
        result = session.apply_rules_action_result(action)
        self.assertNotEqual(result.get("status"), "target_missing")
        revived = next(item for item in session.battlefield if item.get("cardId") == "m-9")
        self.assertTrue(revived["isSupport"])
        self.assertEqual(revived["controllerId"], "p1")
        self.assertEqual(revived["supportWinDestination"], "exile")
        self.assertEqual(p2["zones"]["graveyard"], [])

    def test_agrupol_shuffles_when_an_effect_puts_it_on_deck_bottom(self):
        agrupol = "j2a7x783j5ql0ab_en"
        session, p1, _p2 = self.make_session(agrupol)
        session.card_rules[agrupol]["shuffleWhenPutDeckBottom"] = True
        self.put(p1, "hand", [agrupol])
        self.put(p1, "deck", ["m-1", "m-2"])

        with patch("session.random.shuffle") as shuffle:
            error, owner_id = session.move_zone_card(
                "p1", "hand", "p1", "deck", agrupol, "bottom"
            )

        self.assertIsNone(error)
        self.assertEqual(owner_id, "p1")
        shuffle.assert_called_once_with(p1["zones"]["deck"])

    def test_jondo_gains_support_only_when_its_base_power_exceeds_own_first(self):
        jondo = "dbevnzpvngas8pg_en"
        session, _p1, _p2 = self.make_session(jondo)
        session.card_rules[jondo]["power"] = 4
        session.card_rules["m-1"]["power"] = 3
        source = self.field_item("jondo", "p1", jondo, field_zone="interzone")
        first = self.field_item("first", "p1", "m-1")
        session.battlefield = [source, first]
        session.rules_engine["firstManifestationItemIds"] = {"p1": first["id"]}

        actions = session.queue_rules_revelation_triggers(defer=True)
        result = session.apply_rules_action_result(actions[0])

        self.assertEqual(result["status"], "granted")
        self.assertEqual(source["supportUntilTurn"], session.phase_tracker["turn"])
        source.pop("supportUntilTurn", None)
        session.card_rules[jondo]["power"] = 2
        result = session.apply_rules_action_result(actions[0])
        self.assertEqual(result["status"], "condition_failed")
        self.assertNotIn("supportUntilTurn", source)

    def test_hogma_suppresses_only_other_friendly_confrontation_manifestations(self):
        hogma_id = "dm0hz9sb5i737gx_en"
        session, _p1, _p2 = self.make_session(hogma_id)
        hogma = self.field_item("hogma", "p1", hogma_id)
        ally = self.field_item("ally", "p1", "m-1")
        interzone = self.field_item("interzone", "p1", "m-2", field_zone="interzone")
        opponent = self.field_item("opponent", "p2", "m-3")
        session.battlefield = [hogma, ally, interzone, opponent]

        actions = session.queue_rules_field_zone_entry_triggers(
            hogma, "confrontation", defer=True
        )
        session.create_rules_ongoing_effects(actions[0])

        affected = {
            effect["target"]["itemId"]
            for effect in session.rules_engine["ongoingEffects"]
            if effect["kind"] == "lose_effects"
        }
        self.assertEqual(affected, {"ally"})

    def test_zborh_returns_from_interzone_when_its_controller_loses(self):
        zborh_id = "inner-deserts-015"
        session, p1, _p2 = self.make_session(zborh_id)
        zborh = self.field_item("zborh", "p1", zborh_id, field_zone="interzone")
        loser = self.field_item("loser", "p1", "m-1")
        winner = self.field_item("winner", "p2", "m-2")
        session.battlefield = [zborh, loser, winner]
        self.set_outcome(session, "p2", "p1", "loser", "winner")

        actions = session.queue_rules_confrontation_win_triggers(defer=True)
        action = next(entry for entry in actions if entry["source"]["itemId"] == "zborh")
        result = session.apply_rules_action_result(action)

        self.assertEqual(result["status"], "moved")
        self.assertIn(zborh_id, p1["zones"]["hand"])
        self.assertIsNone(session.find_battlefield_item("zborh"))

    def test_ippokridal_creates_vitreous_token_only_for_own_reaction_will(self):
        ippokridal_id = "inner-deserts-040"
        session, _p1, _p2 = self.make_session(ippokridal_id)
        source = self.field_item("ippokridal", "p1", ippokridal_id)
        session.battlefield = [source]
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")

        actions = session.queue_rules_triggers(
            ippokridal_id, "p1", "will_played", item_id=source["id"],
            event_controller_id="p1", controller_id="p1", defer=True,
        )
        created = session.apply_rules_action_result(actions[0])
        token = session.find_battlefield_item(created["createdItemId"])
        self.assertEqual((token["power"], token["temperament"]), (1, "vitreous"))
        self.assertTrue(token["isSupport"])

        session.phase_tracker["index"] = ADVANCED_PHASES.index("end_actions")
        self.assertEqual(session.queue_rules_triggers(
            ippokridal_id, "p1", "will_played", item_id=source["id"],
            event_controller_id="p1", controller_id="p1", defer=True,
        ), [])

    def test_manymaws_sacrifices_a_chosen_friendly_confrontation_manifestation(self):
        manymaws_id = "inner-deserts-053"
        session, p1, _p2 = self.make_session(manymaws_id)
        source = self.field_item("manymaws", "p1", manymaws_id)
        ally = self.field_item("ally", "p1", "m-1")
        session.battlefield = [source, ally]
        target = {
            "kind": "card", "itemId": ally["id"], "cardId": ally["cardId"],
            "ownerId": "p1", "controllerId": "p1", "zone": "battlefield",
        }

        actions = session.queue_rules_triggers(
            manymaws_id, "p1", "enters_field_zone", zone="confrontation",
            item_id=source["id"], event_item_id=source["id"],
            controller_id="p1", event_targets=[target], defer=True,
        )
        result = session.apply_rules_action_result(actions[0])

        self.assertEqual((result["status"], result["reason"]), ("moved", "sacrifice"))
        self.assertIn("m-1", p1["zones"]["graveyard"])
        self.assertIsNotNone(session.find_battlefield_item("manymaws"))

    def test_ozzit_moves_to_stalemate_only_on_an_odd_roll(self):
        ozzit_id = "inner-deserts-075"
        session, _p1, _p2 = self.make_session(ozzit_id)
        source = self.field_item("ozzit", "p1", ozzit_id)
        session.battlefield = [source]
        actions = session.queue_rules_field_zone_entry_triggers(
            source, "confrontation", defer=True
        )

        with patch("session.random.randint", return_value=3):
            result = session.apply_rules_action_result(actions[0])
        self.assertEqual((result["status"], source["fieldZone"]), ("moved", "stalemate"))

        source["fieldZone"] = "confrontation"
        with patch("session.random.randint", return_value=4):
            result = session.apply_rules_action_result(actions[0])
        self.assertEqual((result["status"], source["fieldZone"]), ("unchanged", "confrontation"))


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
