"""Strict beginning-of-turn contracts for eight previously uncovered cards."""
import copy
import unittest

import card_ability_smoke as smoke
import main


BEGINNING_OF_TURN_NAMES = (
    "Lerxur, the Black Moon",
    "Red Plague",
    "Atavic Volatility",
    "Soul-devouring Dunes",
    "Essence Forager",
    "Fee-fee, the Afflicted",
    "Lunar Liturgy",
    "BOB",
)

EXPECTED_CONTRACTS = {
    "Lerxur, the Black Moon": (
        "receptacle", "opponent", "unless_payment_deck_discard",
    ),
    "Red Plague": (
        "receptacle", "opponent", "choose_points_or_hand_limit",
    ),
    "Atavic Volatility": ("field", None, None),
    "Soul-devouring Dunes": (None, None, "each_player_recovery_choice"),
    "Essence Forager": ("field", None, "create_essence"),
    "Fee-fee, the Afflicted": ("stalemate", None, "spite_upkeep"),
    "Lunar Liturgy": ("field", None, "lunar_liturgy"),
    "BOB": ("confrontation", None, "add_counter_source"),
}


class BeginningOfTurnFamily(unittest.TestCase):
    @staticmethod
    def card(name):
        return next(card for card in main.CARD_DATA if card["name"] == name)

    def ability(self, name):
        card = self.card(name)
        matches = [
            ability for ability in main.CARD_ABILITIES[card["id"]]
            if (ability.get("trigger") or {}).get("event")
            == "beginning_of_turn"
        ]
        self.assertEqual(len(matches), 1, name)
        return card, matches[0]

    def fixture(self, name):
        card, ability = self.ability(name)
        session, source, _stack = smoke.make_session(card["id"], ability)
        expected_zone = EXPECTED_CONTRACTS[name][0]
        if expected_zone == "receptacle":
            session.battlefield = [
                item for item in session.battlefield if item["id"] != source["id"]
            ]
            for player in session.players.values():
                player["zones"]["receptacle"] = []
                player["zoneOwners"]["receptacle"] = {}
            session.players["p2"]["zones"]["receptacle"] = [card["id"]]
            session.players["p2"]["zoneOwners"]["receptacle"] = {
                card["id"]: "p1",
            }
        else:
            source["fieldZone"] = expected_zone or "field"
            source["faceUp"] = True
        if name == "Atavic Volatility":
            source["counters"]["Coil"] = 10
        return card, ability, session, source

    @staticmethod
    def queued_action(session):
        queued = session.queue_rules_beginning_turn_triggers(defer=True)
        if len(queued) != 1:
            raise AssertionError(f"expected one beginning trigger, got {len(queued)}")
        return queued[0]

    def test_all_eight_compile_the_exact_beginning_of_turn_contract(self):
        self.assertEqual(len(BEGINNING_OF_TURN_NAMES), 8)
        for name in BEGINNING_OF_TURN_NAMES:
            with self.subTest(card=name):
                card, ability = self.ability(name)
                trigger = ability["trigger"]
                zone, container, result_kind = EXPECTED_CONTRACTS[name]
                self.assertEqual(trigger["event"], "beginning_of_turn")
                self.assertEqual(trigger.get("zone"), zone)
                self.assertEqual(trigger.get("container"), container)
                self.assertEqual(
                    (ability.get("result") or {}).get("kind"), result_kind,
                )
                self.assertIn("beginning", card["effect"].lower())

        _card, atavic = self.ability("Atavic Volatility")
        self.assertTrue(atavic["optional"])
        self.assertEqual(
            atavic["trigger"]["sourceCounterMin"],
            {"name": "Coil", "min": 10},
        )
        self.assertEqual(atavic["targets"]["min"], 1)
        self.assertEqual(atavic["targets"]["max"], 1)
        self.assertEqual(atavic["targets"]["cardType"], "manifestation")
        self.assertEqual(atavic["targets"]["zones"], ["battlefield"])
        self.assertEqual(
            atavic["ongoingEffect"],
            {"kind": "lose_effects", "duration": "until_end_of_turn"},
        )

        _card, lerxur = self.ability("Lerxur, the Black Moon")
        self.assertEqual(
            lerxur["result"],
            {
                "kind": "unless_payment_deck_discard",
                "payment": "{H}{H}",
                "count": 2,
            },
        )
        _card, bob = self.ability("BOB")
        self.assertEqual(
            bob["result"],
            {"kind": "add_counter_source", "counter": "power", "value": 3},
        )

    def test_each_queues_once_from_its_exact_live_zone(self):
        for name in BEGINNING_OF_TURN_NAMES:
            with self.subTest(card=name):
                card, ability, session, source = self.fixture(name)
                action = self.queued_action(session)
                self.assertEqual(action["ability"]["id"], ability["id"])
                self.assertEqual(action["source"]["cardId"], card["id"])
                self.assertEqual(
                    action["source"]["zone"], EXPECTED_CONTRACTS[name][0] or "field",
                )
                self.assertEqual(
                    action["source"].get("containerId"),
                    "p2" if EXPECTED_CONTRACTS[name][0] == "receptacle" else None,
                )
                if EXPECTED_CONTRACTS[name][0] != "receptacle":
                    self.assertEqual(action["source"]["itemId"], source["id"])
                if name == "Atavic Volatility":
                    self.assertIn("_preStackTargetChoice", action)
                self.assertEqual(
                    session.queue_rules_beginning_turn_triggers(defer=True), [],
                )

    def test_wrong_zone_face_down_owner_vessel_and_counter_threshold_do_not_trigger(self):
        for name in BEGINNING_OF_TURN_NAMES:
            if EXPECTED_CONTRACTS[name][0] == "receptacle":
                with self.subTest(owner_vessel=name):
                    card, _ability, session, _source = self.fixture(name)
                    session.players["p2"]["zones"]["receptacle"] = []
                    session.players["p2"]["zoneOwners"]["receptacle"] = {}
                    session.players["p1"]["zones"]["receptacle"] = [card["id"]]
                    session.players["p1"]["zoneOwners"]["receptacle"] = {
                        card["id"]: "p1",
                    }
                    before = copy.deepcopy(
                        (session.players, session.battlefield, session.rules_engine)
                    )
                    self.assertEqual(
                        session.queue_rules_beginning_turn_triggers(defer=True), [],
                    )
                    self.assertEqual(session.players, before[0])
                    self.assertEqual(session.battlefield, before[1])
                    self.assertEqual(
                        session.rules_engine["actionStack"],
                        before[2]["actionStack"],
                    )
                continue

            required = EXPECTED_CONTRACTS[name][0]
            if required is not None:
                with self.subTest(wrong_zone=name):
                    _card, _ability, session, source = self.fixture(name)
                    source["fieldZone"] = (
                        "interzone" if required != "interzone" else "confrontation"
                    )
                    self.assertEqual(
                        session.queue_rules_beginning_turn_triggers(defer=True), [],
                    )

            with self.subTest(face_down=name):
                _card, _ability, session, source = self.fixture(name)
                source["faceUp"] = False
                self.assertEqual(
                    session.queue_rules_beginning_turn_triggers(defer=True), [],
                )

        _card, _ability, session, source = self.fixture("Atavic Volatility")
        source["counters"]["Coil"] = 9
        self.assertEqual(
            session.queue_rules_beginning_turn_triggers(defer=True), [],
        )

    def test_each_card_specific_result_begins_after_the_valid_trigger(self):
        for name in BEGINNING_OF_TURN_NAMES:
            with self.subTest(card=name):
                _card, _ability, session, source = self.fixture(name)
                action = self.queued_action(session)

                if name == "Atavic Volatility":
                    target = session.find_battlefield_item("opp-con")
                    self.assertTrue(session.rules_item_effects_active(target))
                    action["targets"] = [{
                        "kind": "card", "itemId": target["id"],
                        "cardId": target["cardId"],
                        "ownerId": target["ownerId"],
                    }]
                    created = session.create_rules_ongoing_effects(action)
                    self.assertEqual(len(created), 1)
                    self.assertEqual(created[0]["kind"], "lose_effects")
                    self.assertFalse(session.rules_item_effects_active(target))
                    continue

                before_power = int(source.get("counters", {}).get("power") or 0)
                payload = session.apply_rules_action_result(action)
                self.assertIsNotNone(payload)

                if name == "Lerxur, the Black Moon":
                    self.assertEqual(payload["choiceKind"], "effect_payment")
                    self.assertEqual(payload["playerId"], "p2")
                    self.assertEqual(payload["payment"], "{H}{H}")
                    self.assertEqual(
                        session.rules_engine["pendingChoice"]["onDecline"],
                        {"kind": "deck_discard", "count": 2},
                    )
                elif name == "Red Plague":
                    self.assertEqual(payload["choiceKind"], "points_or_hand_limit")
                    self.assertEqual(payload["playerId"], "p2")
                    self.assertEqual(
                        session.rules_engine["pendingChoice"]["options"],
                        ["lose_points", "limit_hand"],
                    )
                elif name == "Soul-devouring Dunes":
                    self.assertEqual(payload["choiceKind"], "recovery_shared_choice")
                    self.assertEqual(payload["playerId"], "p1")
                elif name == "Essence Forager":
                    self.assertEqual(payload["status"], "created")
                    self.assertEqual(payload["temperament"], "transcendent")
                    self.assertEqual(payload["amount"], 1)
                    self.assertEqual(len(payload["tokens"]), 1)
                elif name == "Fee-fee, the Afflicted":
                    self.assertEqual(source["counters"]["Spite"], 1)
                    self.assertEqual(payload["choiceKind"], "effect_payment")
                    self.assertEqual(payload["playerId"], "p1")
                    self.assertEqual(payload["payment"], "{H}")
                elif name == "Lunar Liturgy":
                    self.assertEqual(payload["kind"], "choice_required")
                    self.assertEqual(payload["playerId"], "p1")
                    self.assertIsNotNone(session.rules_engine["pendingChoice"])
                elif name == "BOB":
                    self.assertEqual(payload["status"], "added")
                    self.assertEqual(
                        source["counters"]["power"], before_power + 3,
                    )


if __name__ == "__main__":
    unittest.main()
