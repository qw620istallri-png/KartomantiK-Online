"""Strict used-as-Tribute contracts for six previously uncovered cards."""
import unittest
from unittest.mock import patch

import test_delayed_tribute_memory as delayed


USED_AS_TRIBUTE_NAMES = (
    "Refrain Repeater",
    "Coral Skull",
    "Loop, the Insistent",
    "Qu Lom, Haphazard Martyr",
    "Crickelob, the Vile",
    "Zozok, the Void",
)

EXPECTED_RESULTS = {
    "Refrain Repeater": {
        "kind": "create_effect_memory",
        "memoryKind": "return_from_limbo_end_turn",
        "attachTo": "event_card",
        "opponentPayment": "{H}",
    },
    "Coral Skull": {
        "kind": "create_effect_memory",
        "memoryKind": "return_from_limbo_end_turn",
        "attachTo": "paid_action_source",
        "optional": True,
    },
    "Loop, the Insistent": {
        "kind": "create_effect_memory",
        "memoryKind": "return_from_limbo_end_turn",
        "attachTo": "paid_action_source",
        "optional": True,
        "requireLostConfrontation": True,
    },
    "Qu Lom, Haphazard Martyr": {
        "kind": "create_effect_memory",
        "memoryKind": "return_from_limbo_end_turn",
        "attachTo": "event_card",
        "rollReturnOrExile": True,
    },
    "Crickelob, the Vile": {"kind": "shuffle_owner_deck"},
    "Zozok, the Void": {"kind": "roll_d6_gain_half_essence"},
}

MEMORY_NAMES = USED_AS_TRIBUTE_NAMES[:4]


class UsedAsTributeFamily(unittest.TestCase):
    @staticmethod
    def fixture():
        case = delayed.DelayedTributeMemoryTests()
        case.setUp()
        return case

    def ability(self, case, name):
        card_id = case.f.cid(name)
        matches = [
            ability
            for ability in case.s.card_rules[card_id]["triggeredAbilities"]
            if (ability.get("trigger") or {}).get("event") == "used_as_tribute"
        ]
        self.assertEqual(len(matches), 1, name)
        return card_id, matches[0]

    def test_all_six_compile_the_exact_used_as_tribute_contract(self):
        self.assertEqual(len(USED_AS_TRIBUTE_NAMES), 6)
        case = self.fixture()
        for name in USED_AS_TRIBUTE_NAMES:
            with self.subTest(card=name):
                _card_id, ability = self.ability(case, name)
                self.assertEqual(
                    ability["trigger"], {"event": "used_as_tribute"},
                )
                self.assertEqual(ability["result"], EXPECTED_RESULTS[name])

    def test_real_will_payment_moves_each_tribute_and_fires_exactly_once(self):
        for name in USED_AS_TRIBUTE_NAMES:
            with self.subTest(card=name):
                case = self.fixture()
                tribute, paid_action = case.pay(name)
                self.assertNotIn(
                    tribute, case.s.players["p1"]["zones"]["hand"],
                )
                self.assertIn(
                    tribute, case.s.players["p1"]["zones"]["graveyard"],
                )

                if name in MEMORY_NAMES:
                    self.assertIsNone(case.s.rules_engine["pendingChoice"])
                    self.assertEqual(
                        [entry["id"] for entry in case.s.rules_engine["actionStack"]],
                        [paid_action["id"]],
                    )
                    self.assertEqual(
                        len(case.s.rules_engine["effectMemories"]), 1,
                    )
                    continue

                choice = case.s.rules_engine["pendingChoice"]
                self.assertEqual(choice["kind"], "simultaneous_stack_order")
                triggers = [
                    action for action in choice["_group"]
                    if action["id"] != paid_action["id"]
                ]
                self.assertEqual(len(triggers), 1)
                _card_id, ability = self.ability(case, name)
                self.assertEqual(triggers[0]["ability"]["id"], ability["id"])
                self.assertEqual(triggers[0]["source"]["zone"], "graveyard")

    def test_discard_is_not_tribute_and_paid_will_memories_require_a_will_play(self):
        for name in USED_AS_TRIBUTE_NAMES:
            with self.subTest(discard=name):
                case = self.fixture()
                card_id, _ability = self.ability(case, name)
                case.f.put(case.s, "p1", "hand", [card_id])
                error, _movement = case.s.move_zone_card(
                    "p1", "hand", "p1", "graveyard", card_id, "top",
                )
                self.assertIsNone(error)
                self.assertEqual(case.s.rules_engine["effectMemories"], [])
                self.assertEqual(case.s.rules_engine["actionStack"], [])
                self.assertIsNone(case.s.rules_engine["pendingChoice"])

        for name in ("Coral Skull", "Loop, the Insistent"):
            with self.subTest(non_will_payment=name):
                case = self.fixture()
                host = case.f.field(
                    case.s, "ufujqhwlpmaw12y_en", item="host", zone="field",
                )
                case.enemy["isSupport"] = True
                tribute = case.f.cid(name)
                case.f.put(case.s, "p1", "hand", [tribute])
                case.s.rules_engine["priorityPlayerId"] = "p1"
                error, action = case.s.declare_rules_action(
                    "p1", "Ignore Support power", kind="activated_effect",
                    source={
                        "cardId": host["cardId"], "zone": "battlefield",
                        "itemId": host["id"],
                    },
                    targets=[case.f.target(case.enemy)],
                    payment_card_ids=[tribute],
                    ability_id="ignore-support-power",
                )
                self.assertIsNone(error)
                delayed.main.log_rules_declared_action(case.s, action)
                self.assertEqual(case.s.rules_engine["effectMemories"], [])
                self.assertEqual(
                    [entry["id"] for entry in case.s.rules_engine["actionStack"]],
                    [action["id"]],
                )

    def test_each_card_specific_first_transition_is_authoritative(self):
        expected_memories = {
            "Refrain Repeater": {
                "attach": "tribute", "optional": False,
                "opponentPayment": "{H}", "rollReturnOrExile": False,
                "requireLostConfrontation": False,
            },
            "Coral Skull": {
                "attach": "will", "optional": True,
                "opponentPayment": None, "rollReturnOrExile": False,
                "requireLostConfrontation": False,
            },
            "Loop, the Insistent": {
                "attach": "will", "optional": True,
                "opponentPayment": None, "rollReturnOrExile": False,
                "requireLostConfrontation": True,
            },
            "Qu Lom, Haphazard Martyr": {
                "attach": "tribute", "optional": False,
                "opponentPayment": None, "rollReturnOrExile": True,
                "requireLostConfrontation": False,
            },
        }
        for name, expected in expected_memories.items():
            with self.subTest(memory=name):
                case = self.fixture()
                with patch("game.effects.stack.random.randint") as die:
                    tribute, paid_action = case.pay(name)
                memory = case.s.rules_engine["effectMemories"][0]
                attached_card = (
                    tribute if expected["attach"] == "tribute" else case.will
                )
                self.assertEqual(memory["cardId"], attached_card)
                self.assertTrue(memory["sourceActionId"])
                self.assertEqual(
                    memory["data"],
                    {
                        "optional": expected["optional"],
                        "opponentPayment": expected["opponentPayment"],
                        "rollReturnOrExile": expected["rollReturnOrExile"],
                        "requireLostConfrontation": expected[
                            "requireLostConfrontation"
                        ],
                        "effectSourceCardId": tribute,
                    },
                )
                die.assert_not_called()

        case = self.fixture()
        case.f.put(case.s, "p1", "deck", ["m2", "m3", "m4"])
        _tribute, paid_action = case.pay("Crickelob, the Vile")
        choice = case.s.rules_engine["pendingChoice"]
        trigger = next(
            action for action in choice["_group"]
            if action["id"] != paid_action["id"]
        )
        self.assertIsNone(case.s.resolve_rules_choice(
            "p1", choice["id"], card_ids=[paid_action["id"], trigger["id"]],
        )[0])
        with patch("session.random.shuffle") as shuffle:
            resolved = case.s.resolve_rules_top_action()
        self.assertEqual(
            resolved["action"]["effectResult"]["status"], "shuffled",
        )
        shuffle.assert_called_once_with(case.s.players["p1"]["zones"]["deck"])

        case = self.fixture()
        _tribute, paid_action = case.pay("Zozok, the Void")
        choice = case.s.rules_engine["pendingChoice"]
        trigger = next(
            action for action in choice["_group"]
            if action["id"] != paid_action["id"]
        )
        self.assertIsNone(case.s.resolve_rules_choice(
            "p1", choice["id"], card_ids=[paid_action["id"], trigger["id"]],
        )[0])
        with patch("game.effects.dice.random.randint", return_value=5) as die:
            resolved = case.s.resolve_rules_top_action()
        effect = resolved["action"]["effectResult"]
        self.assertEqual(
            (effect["roll"], effect["essences"], effect["playerId"]),
            (5, 3, "p1"),
        )
        retained = [
            token for token in case.s.tokens
            if token.get("isEssence")
            and token.get("temperament") == "transcendent"
        ]
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0]["counters"]["essence"], 3)
        self.assertEqual(retained[0]["expiresTurn"], 0)
        die.assert_called_once_with(1, 6)


if __name__ == "__main__":
    unittest.main()
