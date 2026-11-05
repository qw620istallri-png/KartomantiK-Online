"""Strict zone-card target contracts for eleven uncovered cards."""
import copy
import unittest

import card_ability_smoke as smoke
import main


ZONE_CARD_TARGET_NAMES = (
    "Solenero, the Contrite",
    "Zombieswing",
    "Reviving Cage",
    "Sallow Thief",
    "Reveal the Hidden",
    "Recover from the Abyss",
    "Dissolve and Coagulate",
    "Leadenshroud",
    "Memento, the Fallen",
    "Cradle the Putrescence",
    "Mock Fate",
)

EXPECTED_CONTRACTS = {
    "Solenero, the Contrite": (1, 1, ("graveyard",), "self", None, None),
    "Zombieswing": (1, 1, ("graveyard",), "self", "self", "manifestation"),
    "Reviving Cage": (1, 1, ("graveyard",), "self", None, "manifestation"),
    "Sallow Thief": (1, 1, ("receptacle",), "self", "opponent", "manifestation"),
    "Reveal the Hidden": (1, 1, ("hand",), "self", None, "manifestation"),
    "Recover from the Abyss": (1, 1, ("graveyard",), "self", None, None),
    "Dissolve and Coagulate": (0, 2, ("receptacle",), None, "self", "manifestation"),
    "Leadenshroud": (1, 1, ("graveyard",), None, None, "manifestation"),
    "Memento, the Fallen": (0, 3, ("graveyard",), "self", "self", None),
    "Cradle the Putrescence": (1, 1, ("receptacle",), None, "self", "manifestation"),
    "Mock Fate": (1, 1, ("graveyard",), None, None, "manifestation"),
}


class ZoneCardTargetFamily(unittest.TestCase):
    @staticmethod
    def card(name):
        return next(card for card in main.CARD_DATA if card["name"] == name)

    def ability(self, name):
        card = self.card(name)
        matches = [
            ability for ability in main.CARD_ABILITIES[card["id"]]
            if (ability.get("targets") or {}).get("kind") == "zone_card"
        ]
        self.assertEqual(len(matches), 1, name)
        return card, matches[0]

    def fixture(self, name):
        card, ability = self.ability(name)
        session, source, _stack = smoke.make_session(card["id"], ability)
        return card, ability, session, source

    @staticmethod
    def raw_target(name):
        if name == "Reveal the Hidden":
            return {
                "kind": "zone_card", "containerId": "p1",
                "zone": "hand", "cardId": "own-man-2",
            }
        if name == "Sallow Thief":
            return {
                "kind": "zone_card", "containerId": "p2",
                "zone": "receptacle", "cardId": "own-man",
            }
        if name in {"Dissolve and Coagulate", "Cradle the Putrescence"}:
            return {
                "kind": "zone_card", "containerId": "p1",
                "zone": "receptacle", "cardId": "opp-man",
            }
        return {
            "kind": "zone_card", "containerId": "p1",
            "zone": "graveyard", "cardId": "grave-man",
        }

    @staticmethod
    def prepare_temporal_contract(session, name, raw):
        key = f'{raw["containerId"]}:{raw["zone"]}:{raw["cardId"]}'
        if name in {"Leadenshroud", "Mock Fate"}:
            session.rules_engine.setdefault("zoneEntryTurns", {})[key] = (
                session.phase_tracker["turn"]
            )
        if name == "Leadenshroud":
            session.rules_engine["recentLimboEntries"] = [{
                "ownerId": "p1", "cardId": raw["cardId"],
                "reason": "destroy", "turn": session.phase_tracker["turn"],
            }]

    def clean_target(self, session, name):
        raw = self.raw_target(name)
        self.prepare_temporal_contract(session, name, raw)
        error, targets = session.rules_action_targets([raw], "p1")
        self.assertIsNone(error, name)
        self.assertEqual(len(targets), 1, name)
        return targets[0]

    @staticmethod
    def action(card, ability, source, targets):
        return {
            "id": f'{card["id"]}-zone-target-proof',
            "controllerId": "p1",
            "kind": ability.get("action") or "triggered_effect",
            "source": {
                "cardId": card["id"], "ownerId": "p1",
                "itemId": source["id"], "zone": "battlefield",
            },
            "targets": targets,
            "ability": copy.deepcopy(ability),
        }

    def assert_valid(self, name, session, card, ability, source, targets):
        self.assertIsNone(
            session.rules_ability_targets_error(
                ability["targets"], targets, "p1",
                source_item_id=source["id"],
                source_card_id=card["id"],
            ),
            name,
        )

    def test_all_eleven_compile_the_exact_zone_card_contract(self):
        self.assertEqual(len(ZONE_CARD_TARGET_NAMES), 11)
        for name in ZONE_CARD_TARGET_NAMES:
            with self.subTest(card=name):
                card, ability = self.ability(name)
                contract = ability["targets"]
                expected = EXPECTED_CONTRACTS[name]
                self.assertEqual(contract["kind"], "zone_card")
                self.assertEqual(contract["min"], expected[0])
                self.assertEqual(contract["max"], expected[1])
                self.assertEqual(tuple(contract["zones"]), expected[2])
                self.assertEqual(contract.get("owner"), expected[3])
                self.assertEqual(contract.get("container"), expected[4])
                self.assertEqual(contract.get("cardType"), expected[5])
                self.assertIn(
                    "target" if name != "Reveal the Hidden" else "from your hand",
                    card["effect"].lower(),
                )

    def test_each_accepts_its_canonical_zone_target_and_rejects_wrong_kind(self):
        for name in ZONE_CARD_TARGET_NAMES:
            with self.subTest(card=name):
                card, ability, session, source = self.fixture(name)
                target = self.clean_target(session, name)
                self.assert_valid(name, session, card, ability, source, [target])
                self.assertEqual(
                    session.rules_ability_targets_error(
                        ability["targets"],
                        [{"kind": "player", "playerId": "p2"}],
                        "p1", source_item_id=source["id"],
                        source_card_id=card["id"],
                    ),
                    "This effect requires a card target.",
                )

    def test_zone_visibility_versions_and_duplicate_normalization_are_authoritative(self):
        card, ability, session, source = self.fixture("Recover from the Abyss")
        before = copy.deepcopy((session.players, session.battlefield, session.rules_engine))
        error, targets = session.rules_action_targets([{
            "kind": "zone_card", "containerId": "p2",
            "zone": "hand", "cardId": "opp-man-2",
        }], "p1")
        self.assertEqual(error, "Only a card in a public zone can be selected as this target.")
        self.assertIsNone(targets)
        self.assertEqual((session.players, session.battlefield, session.rules_engine), before)

        target = self.clean_target(session, "Recover from the Abyss")
        error, deduplicated = session.rules_action_targets([target, target], "p1")
        self.assertIsNone(error)
        self.assertEqual(deduplicated, [target])
        session.bump_rules_zone_entry_version("p1", "graveyard", "grave-man")
        stable = copy.deepcopy((session.players, session.battlefield, session.rules_engine))
        error, stale = session.rules_action_targets([target], "p1")
        self.assertEqual(error, "The selected card left this zone after it was targeted.")
        self.assertIsNone(stale)
        self.assertEqual((session.players, session.battlefield, session.rules_engine), stable)
        self.assertEqual(
            session.rules_ability_targets_error(
                ability["targets"], [target], "p1",
                source_item_id=source["id"], source_card_id=card["id"],
            ),
            "The targeted card left this zone after it was targeted.",
        )

    def test_cardinality_owner_container_type_and_temporal_constraints(self):
        for name in ZONE_CARD_TARGET_NAMES:
            with self.subTest(card=name):
                card, ability, session, source = self.fixture(name)
                target = self.clean_target(session, name)
                contract = ability["targets"]
                if contract["min"]:
                    self.assertEqual(
                        session.rules_ability_targets_error(
                            contract, [], "p1", source_item_id=source["id"],
                            source_card_id=card["id"],
                        ),
                        "Choose the required number of targets for this effect.",
                    )
                else:
                    self.assertIsNone(session.rules_ability_targets_error(
                        contract, [], "p1", source_item_id=source["id"],
                        source_card_id=card["id"],
                    ))
                self.assertEqual(
                    session.rules_ability_targets_error(
                        contract, [target] * (contract["max"] + 1), "p1",
                        source_item_id=source["id"], source_card_id=card["id"],
                    ),
                    "Choose the required number of targets for this effect.",
                )

        for name in ("Solenero, the Contrite", "Sallow Thief", "Zombieswing"):
            with self.subTest(owner=name):
                card, ability, session, source = self.fixture(name)
                target = self.clean_target(session, name)
                target["ownerId"] = "p2"
                self.assertEqual(
                    session.rules_ability_targets_error(
                        ability["targets"], [target], "p1",
                        source_item_id=source["id"], source_card_id=card["id"],
                    ),
                    "This effect requires a card you own.",
                )

        for name in ("Zombieswing", "Memento, the Fallen"):
            with self.subTest(exclude_source=name):
                card, ability, session, source = self.fixture(name)
                session.put_zone_card("p1", "graveyard", card["id"], "p1")
                error, targets = session.rules_action_targets([{
                    "kind": "zone_card", "containerId": "p1",
                    "zone": "graveyard", "cardId": card["id"],
                }], "p1")
                self.assertIsNone(error)
                self.assertEqual(
                    session.rules_ability_targets_error(
                        ability["targets"], targets, "p1",
                        source_item_id=source["id"], source_card_id=card["id"],
                    ),
                    "This effect requires another card.",
                )

        for name in ("Leadenshroud", "Mock Fate"):
            with self.subTest(entered_this_turn=name):
                card, ability, session, source = self.fixture(name)
                target = self.clean_target(session, name)
                session.rules_engine["zoneEntryTurns"].clear()
                self.assertEqual(
                    session.rules_ability_targets_error(
                        ability["targets"], [target], "p1",
                        source_item_id=source["id"], source_card_id=card["id"],
                    ),
                    "This effect requires a card that entered that zone this turn.",
                )

        card, ability, session, source = self.fixture("Leadenshroud")
        target = self.clean_target(session, "Leadenshroud")
        session.rules_engine["recentLimboEntries"][0]["reason"] = "return"
        self.assertEqual(
            session.rules_ability_targets_error(
                ability["targets"], [target], "p1",
                source_item_id=source["id"], source_card_id=card["id"],
            ),
            "This effect requires a card destroyed or discarded this turn.",
        )

    def test_each_card_specific_result_begins_from_a_valid_zone_target(self):
        for name in ZONE_CARD_TARGET_NAMES:
            with self.subTest(card=name):
                card, ability, session, source = self.fixture(name)
                target = self.clean_target(session, name)
                self.assert_valid(name, session, card, ability, source, [target])
                before_score = session.players["p1"]["score"]
                payload = session.apply_rules_action_result(
                    self.action(card, ability, source, [target])
                )
                self.assertIsNotNone(payload)
                self.assertNotIn(payload.get("status"), {"target_missing", "error"})

                card_id = target["cardId"]
                if name in {
                    "Solenero, the Contrite", "Zombieswing",
                    "Sallow Thief", "Recover from the Abyss",
                }:
                    self.assertIn(card_id, session.players["p1"]["zones"]["hand"])
                elif name in {"Reviving Cage", "Reveal the Hidden"}:
                    moved = session.find_battlefield_item(payload["itemId"])
                    self.assertEqual(moved["fieldZone"], "interzone")
                    self.assertEqual(moved["controllerId"], "p1")
                elif name == "Dissolve and Coagulate":
                    self.assertIn(card_id, session.players["p2"]["zones"]["deck"])
                    self.assertEqual(session.players["p1"]["score"], before_score + 30)
                elif name == "Leadenshroud":
                    moved = session.find_battlefield_item(payload["itemId"])
                    self.assertTrue(moved["isSupport"])
                    self.assertEqual(moved["supportWinDestination"], "exile")
                elif name == "Memento, the Fallen":
                    self.assertIn(card_id, session.players["p1"]["zones"]["deck"])
                elif name == "Cradle the Putrescence":
                    self.assertIn(card_id, session.players["p2"]["zones"]["graveyard"])
                    self.assertEqual(payload["playerId"], "p2")
                    self.assertEqual(payload["purpose"], "sacrifice")
                elif name == "Mock Fate":
                    moved = session.find_battlefield_item(payload["itemId"])
                    self.assertEqual(moved["fieldZone"], "stalemate")


if __name__ == "__main__":
    unittest.main()
