"""Strict live-card target contracts for seven previously uncovered cards."""
import copy
import unittest

import card_ability_smoke as smoke
import main


CARD_TARGET_NAMES = (
    "Logos, the Lost",
    "Glabron, the Oppressing",
    "Censor",
    "Swindley, the Festive",
    "Lugione, the Hungry",
    "Drain the Substance",
    "Cleanse",
)

ABILITY_CASES = (
    ("Logos, the Lost", "logos-stalemates-interzone-target-after-win"),
    ("Logos, the Lost", "logos-and-winner-stalemate-after-loss"),
    ("Glabron, the Oppressing", "glabron-stalemates-own-interzone-card-for-support"),
    ("Censor", "censor-exiles-hand-manifestation-to-destroy"),
    ("Swindley, the Festive", "swindley-stalemate-to-return"),
    ("Lugione, the Hungry", "sacrifice-to-destroy-power-four"),
    ("Drain the Substance", "drain-the-substance-removes-excess-essence"),
    ("Cleanse", "remove-target-modifiers"),
)

EXPECTED_CONTRACTS = {
    "logos-stalemates-interzone-target-after-win": {
        "cardType": "manifestation", "fieldZone": "interzone",
    },
    "logos-and-winner-stalemate-after-loss": {
        "cardType": "manifestation", "confrontationOutcome": "won",
    },
    "glabron-stalemates-own-interzone-card-for-support": {
        "cardType": "manifestation", "fieldZone": "interzone",
        "controller": "self",
    },
    "censor-exiles-hand-manifestation-to-destroy": {
        "cardType": "manifestation", "fieldZone": "confrontation",
    },
    "swindley-stalemate-to-return": {
        "cardType": "manifestation", "fieldZone": "stalemate",
    },
    "sacrifice-to-destroy-power-four": {
        "cardType": "manifestation", "minPower": 4,
    },
    "drain-the-substance-removes-excess-essence": {
        "cardType": "manifestation",
    },
    "remove-target-modifiers": {},
}


class CardTargetFamily(unittest.TestCase):
    @staticmethod
    def card(name):
        return next(card for card in main.CARD_DATA if card["name"] == name)

    def ability(self, name, ability_id):
        card = self.card(name)
        matches = [
            ability for ability in main.CARD_ABILITIES[card["id"]]
            if ability.get("id") == ability_id
        ]
        self.assertEqual(len(matches), 1, ability_id)
        return card, matches[0]

    def fixture(self, name, ability_id):
        card, ability = self.ability(name, ability_id)
        session, source, _stack = smoke.make_session(card["id"], ability)
        if ability_id == "logos-and-winner-stalemate-after-loss":
            session.rules_engine["confrontationResult"] = {
                "winnerId": "p2", "loserId": "p1",
                "participantItemIds": ["source", "own-con", "opp-con"],
            }
        if ability_id == "sacrifice-to-destroy-power-four":
            session.card_rules["opp-man"]["power"] = 4
            session.find_battlefield_item("opp-con")["counters"].pop("power", None)
        return card, ability, session, source

    @staticmethod
    def target_item_id(ability_id):
        return {
            "logos-stalemates-interzone-target-after-win": "own-inter",
            "logos-and-winner-stalemate-after-loss": "opp-con",
            "glabron-stalemates-own-interzone-card-for-support": "own-inter",
            "censor-exiles-hand-manifestation-to-destroy": "opp-con",
            "swindley-stalemate-to-return": "stalemate",
            "sacrifice-to-destroy-power-four": "opp-con",
            "drain-the-substance-removes-excess-essence": "opp-con",
            "remove-target-modifiers": "own-will-field",
        }[ability_id]

    def target(self, session, ability_id):
        item = session.find_battlefield_item(self.target_item_id(ability_id))
        self.assertIsNotNone(item, ability_id)
        return {
            "kind": "card", "itemId": item["id"],
            "cardId": item["cardId"], "ownerId": item["ownerId"],
        }

    @staticmethod
    def action(card, ability, source, target):
        source_zone = "hand" if card["name"] in {
            "Censor", "Swindley, the Festive", "Drain the Substance", "Cleanse",
        } else "battlefield"
        return {
            "id": f'{card["id"]}-card-target-proof',
            "controllerId": "p1",
            "kind": ability.get("action") or "activated_effect",
            "source": {
                "cardId": card["id"], "ownerId": "p1",
                "itemId": source.get("id") if source_zone == "battlefield" else None,
                "zone": source_zone,
            },
            "targets": [target],
            "ability": copy.deepcopy(ability),
            "cost": {},
        }

    def assert_valid(self, session, card, ability, source, target):
        self.assertIsNone(session.rules_ability_targets_error(
            ability["targets"], [target], "p1",
            source_item_id=source["id"], source_card_id=card["id"],
        ))

    def test_all_eight_abilities_compile_the_exact_card_target_contract(self):
        self.assertEqual(len(CARD_TARGET_NAMES), 7)
        self.assertEqual(len(ABILITY_CASES), 8)
        for name, ability_id in ABILITY_CASES:
            with self.subTest(card=name, ability=ability_id):
                card, ability = self.ability(name, ability_id)
                contract = ability["targets"]
                self.assertEqual(contract["kind"], "card")
                self.assertEqual(contract["min"], 1)
                self.assertEqual(contract["max"], 1)
                self.assertEqual(contract["zones"], ["battlefield"])
                expected = EXPECTED_CONTRACTS[ability_id]
                for key in (
                    "cardType", "fieldZone", "controller",
                    "confrontationOutcome", "minPower",
                ):
                    self.assertEqual(contract.get(key), expected.get(key))
                self.assertIn("manifestation" if name != "Cleanse" else "card",
                              card["effect"].lower())

    def test_each_accepts_its_canonical_live_target_and_rejects_wrong_kind(self):
        for name, ability_id in ABILITY_CASES:
            with self.subTest(card=name, ability=ability_id):
                card, ability, session, source = self.fixture(name, ability_id)
                target = self.target(session, ability_id)
                self.assert_valid(session, card, ability, source, target)
                self.assertEqual(session.rules_ability_targets_error(
                    ability["targets"], [{"kind": "player", "playerId": "p2"}],
                    "p1", source_item_id=source["id"], source_card_id=card["id"],
                ), "This effect requires a card target.")

    def test_cardinality_staleness_and_stalemate_field_boundary_are_authoritative(self):
        for name, ability_id in ABILITY_CASES:
            with self.subTest(card=name, ability=ability_id):
                card, ability, session, source = self.fixture(name, ability_id)
                target = self.target(session, ability_id)
                contract = ability["targets"]
                self.assertEqual(session.rules_ability_targets_error(
                    contract, [], "p1", source_item_id=source["id"],
                    source_card_id=card["id"],
                ), "Choose the required number of targets for this effect.")
                self.assertEqual(session.rules_ability_targets_error(
                    contract, [target, target], "p1", source_item_id=source["id"],
                    source_card_id=card["id"],
                ), "Choose the required number of targets for this effect.")

                session.battlefield = [
                    item for item in session.battlefield
                    if item["id"] != target["itemId"]
                ]
                stable = copy.deepcopy(
                    (session.players, session.battlefield, session.rules_engine)
                )
                self.assertEqual(session.rules_ability_targets_error(
                    contract, [target], "p1", source_item_id=source["id"],
                    source_card_id=card["id"],
                ), "The selected battlefield target is no longer available.")
                self.assertEqual(
                    (session.players, session.battlefield, session.rules_engine), stable,
                )

        card, ability, session, source = self.fixture(
            "Drain the Substance", "drain-the-substance-removes-excess-essence",
        )
        stale = session.find_battlefield_item("stalemate")
        target = {
            "kind": "card", "itemId": stale["id"],
            "cardId": stale["cardId"], "ownerId": stale["ownerId"],
        }
        self.assertEqual(session.rules_ability_targets_error(
            ability["targets"], [target], "p1", source_item_id=source["id"],
            source_card_id=card["id"],
        ), "A card in the Stalemate Zone is not on the field.")

    def test_zone_controller_outcome_type_and_power_constraints(self):
        invalid_cases = (
            (
                "Logos, the Lost", "logos-stalemates-interzone-target-after-win",
                "own-con", "This effect requires a target in a different field zone.",
            ),
            (
                "Logos, the Lost", "logos-and-winner-stalemate-after-loss",
                "own-con", "This effect requires a Manifestation that won the Confrontation this turn.",
            ),
            (
                "Glabron, the Oppressing", "glabron-stalemates-own-interzone-card-for-support",
                "opp-inter", "This effect requires a Manifestation you control.",
            ),
            (
                "Censor", "censor-exiles-hand-manifestation-to-destroy",
                "own-inter", "This effect requires a target in a different field zone.",
            ),
            (
                "Swindley, the Festive", "swindley-stalemate-to-return",
                "opp-con", "This effect requires a target in a different field zone.",
            ),
            (
                "Drain the Substance", "drain-the-substance-removes-excess-essence",
                "own-will-field", "This effect requires a different type of target.",
            ),
            (
                "Cleanse", "remove-target-modifiers",
                "stalemate", "A card in the Stalemate Zone is not on the field.",
            ),
        )
        for name, ability_id, item_id, expected_error in invalid_cases:
            with self.subTest(card=name, ability=ability_id):
                card, ability, session, source = self.fixture(name, ability_id)
                item = session.find_battlefield_item(item_id)
                target = {
                    "kind": "card", "itemId": item["id"],
                    "cardId": item["cardId"], "ownerId": item["ownerId"],
                }
                stable = copy.deepcopy(
                    (session.players, session.battlefield, session.rules_engine)
                )
                self.assertEqual(session.rules_ability_targets_error(
                    ability["targets"], [target], "p1",
                    source_item_id=source["id"], source_card_id=card["id"],
                ), expected_error)
                self.assertEqual(
                    (session.players, session.battlefield, session.rules_engine), stable,
                )

        card, ability, session, source = self.fixture(
            "Lugione, the Hungry", "sacrifice-to-destroy-power-four",
        )
        weak = session.find_battlefield_item("own-con")
        weak["counters"].pop("power", None)
        session.card_rules[weak["cardId"]]["power"] = 3
        target = {
            "kind": "card", "itemId": weak["id"],
            "cardId": weak["cardId"], "ownerId": weak["ownerId"],
        }
        self.assertEqual(session.rules_ability_targets_error(
            ability["targets"], [target], "p1", source_item_id=source["id"],
            source_card_id=card["id"],
        ), "This effect requires a Manifestation with higher Power.")

    def test_each_card_specific_result_begins_from_a_valid_card_target(self):
        for name, ability_id in ABILITY_CASES:
            with self.subTest(card=name, ability=ability_id):
                card, ability, session, source = self.fixture(name, ability_id)
                target = self.target(session, ability_id)
                self.assert_valid(session, card, ability, source, target)
                action = self.action(card, ability, source, target)

                if name == "Drain the Substance":
                    session.add_rules_excess_essence("p1", [{
                        "temperament": "phlegmatic", "amount": 2,
                    }])
                    session.add_rules_excess_essence("p2", [{
                        "temperament": "choleric", "amount": 1,
                    }])
                if name == "Cleanse":
                    item = session.find_battlefield_item(target["itemId"])
                    item["counters"].update({"power": 2, "Gem": 1})
                    session.rules_engine["ongoingEffects"].append({
                        "id": "cleanse-me", "actionId": "old",
                        "abilityId": "old-modifier", "controllerId": "p2",
                        "source": {"cardId": "opp-will"},
                        "target": copy.deepcopy(target),
                        "kind": "power_modifier", "duration": "until_end_of_turn",
                        "startedTurn": session.phase_tracker["turn"], "value": 3,
                    })

                payload = session.apply_rules_action_result(action)
                self.assertIsNotNone(payload)

                if ability_id == "logos-stalemates-interzone-target-after-win":
                    moved = session.find_battlefield_item(target["itemId"])
                    self.assertEqual(moved["fieldZone"], "stalemate")
                    self.assertEqual(moved["zoneLockTurn"], session.phase_tracker["turn"])
                elif ability_id == "logos-and-winner-stalemate-after-loss":
                    moved = session.find_battlefield_item(target["itemId"])
                    host = session.find_battlefield_item(source["id"])
                    self.assertEqual(moved["fieldZone"], "stalemate")
                    self.assertEqual(host["fieldZone"], "stalemate")
                    self.assertEqual(moved["zoneLockTurn"], session.phase_tracker["turn"])
                    self.assertEqual(host["zoneLockTurn"], session.phase_tracker["turn"])
                elif name == "Glabron, the Oppressing":
                    self.assertEqual(
                        session.find_battlefield_item(target["itemId"])["fieldZone"],
                        "stalemate",
                    )
                    self.assertEqual(
                        source["supportUntilTurn"], session.phase_tracker["turn"],
                    )
                elif name == "Censor":
                    self.assertEqual(payload["choiceKind"], "discard_from_hand")
                    self.assertEqual(
                        session.rules_engine["pendingChoice"]["destroyTargetItemId"],
                        target["itemId"],
                    )
                elif name == "Swindley, the Festive":
                    self.assertIsNone(session.find_battlefield_item(target["itemId"]))
                    self.assertIn(target["cardId"], session.players["p2"]["zones"]["hand"])
                elif name == "Lugione, the Hungry":
                    self.assertIsNone(session.find_battlefield_item(target["itemId"]))
                    self.assertIn(
                        target["cardId"], session.players["p2"]["zones"]["graveyard"],
                    )
                elif name == "Drain the Substance":
                    self.assertEqual(payload["status"], "drained")
                    self.assertEqual(payload["essence"], 3)
                    self.assertFalse([
                        token for token in session.tokens if token.get("isEssence")
                    ])
                    effect = session.rules_engine["ongoingEffects"][-1]
                    self.assertEqual(effect["target"]["itemId"], target["itemId"])
                    self.assertEqual(effect["value"], 3)
                elif name == "Cleanse":
                    item = session.find_battlefield_item(target["itemId"])
                    self.assertEqual(payload["status"], "cleansed")
                    self.assertNotIn("power", item["counters"])
                    self.assertEqual(item["counters"]["Gem"], 1)
                    self.assertFalse(any(
                        effect.get("id") == "cleanse-me"
                        for effect in session.rules_engine["ongoingEffects"]
                    ))


if __name__ == "__main__":
    unittest.main()
