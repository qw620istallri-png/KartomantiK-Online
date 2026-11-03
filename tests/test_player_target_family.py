"""Strict player-target contracts for eleven uncovered cards."""
import copy
import unittest

import card_ability_smoke as smoke
import main


PLAYER_TARGET_NAMES = (
    "Haltan, the Favored",
    "Gobres, the Collector",
    "Suspend Judgment",
    "Shymon, the Mastermind",
    "Rogue Tadpole",
    "Tardigramo",
    "Rude Exterminator",
    "Ababash, the Ambassador",
    "Nullify Reason",
    "Remove by Chance",
    "Walk the Oblivion",
)

OPPONENT_ONLY_NAMES = {
    "Gobres, the Collector",
    "Shymon, the Mastermind",
    "Tardigramo",
    "Rude Exterminator",
    "Walk the Oblivion",
}


class PlayerTargetFamily(unittest.TestCase):
    @staticmethod
    def card(name):
        return next(card for card in main.CARD_DATA if card["name"] == name)

    def ability(self, name):
        card = self.card(name)
        matches = [
            ability for ability in main.CARD_ABILITIES[card["id"]]
            if (ability.get("targets") or {}).get("kind") == "player"
        ]
        self.assertEqual(len(matches), 1, name)
        return card, matches[0]

    def fixture(self, name):
        card, ability = self.ability(name)
        session, source, _stack = smoke.make_session(card["id"], ability)
        return card, ability, session, source

    def test_all_eleven_compile_one_exact_single_player_target(self):
        self.assertEqual(len(PLAYER_TARGET_NAMES), 11)
        for name in PLAYER_TARGET_NAMES:
            with self.subTest(card=name):
                card, ability = self.ability(name)
                contract = ability["targets"]
                self.assertEqual(contract["kind"], "player")
                self.assertEqual(contract["min"], 1)
                self.assertEqual(contract["max"], 1)
                self.assertIn("target", card["effect"].lower())
                if name in OPPONENT_ONLY_NAMES:
                    self.assertEqual(contract.get("controller"), "opponent")
                    self.assertIn("opponent", card["effect"].lower())
                else:
                    self.assertIsNone(contract.get("controller"))

    def test_each_accepts_a_valid_player_and_rejects_a_card_target(self):
        for name in PLAYER_TARGET_NAMES:
            with self.subTest(card=name):
                card, ability, session, source = self.fixture(name)
                error, targets = session.rules_action_targets(
                    [{"kind": "player", "playerId": "p2"}], "p1"
                )
                self.assertIsNone(error)
                self.assertEqual(
                    session.rules_ability_targets_error(
                        ability["targets"],
                        targets,
                        "p1",
                        source_item_id=source["id"],
                        source_card_id=card["id"],
                    ),
                    None,
                )
                wrong = [{
                    "kind": "card",
                    "itemId": "opp-con",
                    "cardId": "opp-man",
                    "ownerId": "p2",
                }]
                self.assertEqual(
                    session.rules_ability_targets_error(
                        ability["targets"],
                        wrong,
                        "p1",
                        source_item_id=source["id"],
                        source_card_id=card["id"],
                    ),
                    "This effect requires a player target.",
                )

    def test_opponent_only_contracts_reject_self_and_open_contracts_allow_self(self):
        for name in PLAYER_TARGET_NAMES:
            with self.subTest(card=name):
                card, ability, session, source = self.fixture(name)
                self_target = [{"kind": "player", "playerId": "p1"}]
                error = session.rules_ability_targets_error(
                    ability["targets"],
                    self_target,
                    "p1",
                    source_item_id=source["id"],
                    source_card_id=card["id"],
                )
                if name in OPPONENT_ONLY_NAMES:
                    self.assertEqual(
                        error,
                        "This effect requires an opponent player.",
                    )
                else:
                    self.assertIsNone(error)

    def test_missing_and_unknown_player_targets_are_rejected_without_mutation(self):
        for name in PLAYER_TARGET_NAMES:
            with self.subTest(card=name):
                card, ability, session, source = self.fixture(name)
                before = copy.deepcopy((
                    session.players,
                    session.battlefield,
                    session.rules_engine,
                ))
                self.assertEqual(
                    session.rules_ability_targets_error(
                        ability["targets"],
                        [],
                        "p1",
                        source_item_id=source["id"],
                        source_card_id=card["id"],
                    ),
                    "Choose the required number of targets for this effect.",
                )
                error, targets = session.rules_action_targets(
                    [{"kind": "player", "playerId": "missing"}], "p1"
                )
                self.assertEqual(
                    error,
                    "A selected player target is no longer in the game.",
                )
                self.assertIsNone(targets)
                self.assertEqual(
                    (
                        session.players,
                        session.battlefield,
                        session.rules_engine,
                    ),
                    before,
                )


if __name__ == "__main__":
    unittest.main()
