"""Printed timing: remember a Tribute now; trigger the stated effect at End."""
import copy
import unittest
from unittest.mock import patch

import test_semantic_batch_001_150 as fixtures

main = fixtures.main


class DelayedTributeMemoryTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.SemanticBatch001150()
        self.s = self.f.world()
        self.mine = self.f.field(self.s, "m2", item="mine")
        self.enemy = self.f.field(self.s, "m4", item="enemy", owner="p2")
        self.will = self.f.cid("Strengthen")

    def pay(self, name, owner="p1"):
        tribute = self.f.cid(name)
        self.f.put(self.s, "p1", "hand", [self.will, tribute])
        self.s.players["p1"]["zoneOwners"]["hand"][tribute] = owner
        self.s.rules_engine["priorityPlayerId"] = "p1"
        error, action = self.s.declare_rules_action("p1", "Strengthen", kind="play_card",
            source={"cardId": self.will, "zone": "hand"}, targets=[self.f.target(self.enemy)],
            payment_card_ids=[tribute], ability_id="strengthen-power-modifier")
        self.assertIsNone(error)
        main.log_rules_declared_action(self.s, action)
        return tribute, action

    def resolve_will(self):
        self.assertIsNone(self.s.pass_rules_priority("p2")[0])
        error, result = self.s.pass_rules_priority("p1")
        self.assertIsNone(error)
        self.assertEqual(result["status"], "resolved")

    def compare(self, outcome):
        self.mine["counters"]["power"] = {"lost": 0, "won": 6, "stalemate": 5}[outcome]
        self.s.phase_tracker["index"] = fixtures.ADVANCED_PHASES.index("resolution_compare")
        result = self.s.prepare_rules_confrontation_result()
        self.assertEqual(result["loserId"], {"lost": "p1", "won": "p2", "stalemate": None}[outcome])
        return result

    def end(self):
        self.s.phase_tracker["index"] = fixtures.ADVANCED_PHASES.index("end_triggers")
        return self.s.queue_rules_end_turn_memory_triggers()

    def test_loop_tribute_only_records_memory_without_stack_action_or_choice(self):
        tribute, action = self.pay("Loop, the Insistent")
        self.assertEqual([a["id"] for a in self.s.rules_engine["actionStack"]], [action["id"]])
        self.assertIsNone(self.s.rules_engine["pendingChoice"])
        memories = self.s.rules_engine["effectMemories"]
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0]["cardId"], self.will)
        self.assertTrue(memories[0]["data"]["requireLostConfrontation"])
        self.assertFalse(any(e["type"] == "rules_action_triggered" and e["details"]["source"]["cardId"] == tribute for e in self.s.log))

    def test_loop_offers_return_at_end_only_after_loss_and_returns_paid_will(self):
        tribute, _ = self.pay("Loop, the Insistent")
        self.resolve_will()
        self.compare("lost")
        self.assertIsNone(self.s.rules_engine["pendingChoice"])
        self.assertEqual(self.s.rules_engine["actionStack"], [])
        queued = self.end()
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0]["source"]["cardId"], tribute)
        choice = self.s.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "optional_stack_action")
        self.assertIsNone(self.s.resolve_rules_choice("p1", choice["id"], option="accept")[0])
        self.resolve_will()
        self.assertIn(self.will, self.s.players["p1"]["zones"]["hand"])
        self.assertIn(tribute, self.s.players["p1"]["zones"]["graveyard"])
        self.assertEqual(self.s.rules_engine["effectMemories"], [])

    def test_loop_has_no_end_trigger_after_win_stalemate_or_without_a_loss(self):
        for outcome in ("won", "stalemate", None):
            with self.subTest(outcome=outcome):
                self.setUp()
                self.pay("Loop, the Insistent")
                self.resolve_will()
                if outcome:
                    self.compare(outcome)
                self.assertEqual(self.end(), [])
                self.assertIsNone(self.s.rules_engine["pendingChoice"])

    def test_all_four_delayed_tribute_cards_record_without_early_stack_or_choices(self):
        for name in ("Loop, the Insistent", "Coral Skull", "Refrain Repeater", "Qu Lom, Haphazard Martyr"):
            with self.subTest(card=name):
                self.setUp()
                with patch("game.effects.stack.random.randint") as roll:
                    tribute, action = self.pay(name)
                self.assertEqual([a["id"] for a in self.s.rules_engine["actionStack"]], [action["id"]])
                self.assertIsNone(self.s.rules_engine["pendingChoice"])
                self.assertEqual(len(self.s.rules_engine["effectMemories"]), 1)
                self.assertEqual(self.s.rules_engine["effectMemories"][0]["cardId"], self.will if name in ("Loop, the Insistent", "Coral Skull") else tribute)
                roll.assert_not_called()

    def test_loop_can_be_paid_after_the_loss_and_does_not_need_the_live_result(self):
        self.compare("lost")
        self.s.rules_engine["confrontationResult"] = None
        self.s.phase_tracker["index"] = fixtures.ADVANCED_PHASES.index("end_actions")
        self.pay("Loop, the Insistent")
        self.resolve_will()
        self.assertEqual(len(self.end()), 1)
        self.assertEqual(self.s.rules_engine["pendingChoice"]["kind"], "optional_stack_action")

    def test_loop_decline_never_returns_the_will_or_repeats_the_offer(self):
        self.pay("Loop, the Insistent")
        self.resolve_will()
        self.compare("lost")
        self.end()
        choice = self.s.rules_engine["pendingChoice"]
        self.assertIsNone(self.s.resolve_rules_choice("p1", choice["id"], option="decline")[0])
        self.assertEqual(self.s.rules_engine["actionStack"], [])
        self.assertIn(self.will, self.s.players["p1"]["zones"]["graveyard"])
        self.assertEqual(self.end(), [])

    def test_loop_and_coral_skull_still_remember_a_neutralized_paid_will(self):
        for name in ("Loop, the Insistent", "Coral Skull"):
            with self.subTest(card=name):
                self.setUp()
                _, action = self.pay(name)
                self.assertEqual(self.s.counter_rules_stack_action(action, "neutralize")["status"], "neutralized")
                self.assertIn(self.will, self.s.players["p1"]["zones"]["graveyard"])
                self.compare("lost")
                self.assertEqual(len(self.end()), 1)
                choice = self.s.rules_engine["pendingChoice"]
                self.assertIsNone(self.s.resolve_rules_choice("p1", choice["id"], option="accept")[0])
                self.resolve_will()
                self.assertIn(self.will, self.s.players["p1"]["zones"]["hand"])

    def test_missing_paid_will_skipped_end_or_previous_turn_loss_gives_no_offer(self):
        for branch in ("hand", "exile", "deck", "skip_end", "previous_loss"):
            with self.subTest(branch=branch):
                self.setUp()
                self.pay("Loop, the Insistent")
                self.resolve_will()
                self.compare("lost")
                if branch in ("hand", "exile", "deck"):
                    self.assertIsNone(self.s.move_zone_card("p1", "graveyard", "p1", branch, self.will, "top")[0])
                elif branch == "skip_end":
                    self.s.rules_engine["skipEndPhaseTurns"] = {"p1": 2}
                else:
                    self.s.rules_engine["confrontationLosses"] = {"1": "p1"}
                    self.s.rules_engine["confrontationResult"] = None
                self.assertEqual(self.end(), [])
                self.assertIsNone(self.s.rules_engine["pendingChoice"])

    def test_qu_lom_rolls_only_at_end_and_uses_both_parities(self):
        for roll, destination in ((4, "hand"), (3, "exile")):
            with self.subTest(roll=roll):
                self.setUp()
                tribute, _ = self.pay("Qu Lom, Haphazard Martyr")
                self.resolve_will()
                self.assertEqual(len(self.end()), 1)
                self.assertIsNone(self.s.rules_engine["pendingChoice"])
                with patch("game.effects.stack.random.randint", return_value=roll) as die:
                    self.resolve_will()
                die.assert_called_once_with(1, 6)
                self.assertIn(tribute, self.s.players["p1"]["zones"][destination])
                self.assertEqual(self.s.rules_engine["effectMemories"], [])

    def test_refrain_opponent_payment_is_only_requested_at_end(self):
        for payment in ("pay", "decline"):
            with self.subTest(payment=payment):
                self.setUp()
                tribute, _ = self.pay("Refrain Repeater")
                self.resolve_will()
                self.f.put(self.s, "p2", "hand", ["m2"])
                self.assertEqual(len(self.end()), 1)
                self.assertIsNone(self.s.rules_engine["pendingChoice"])
                self.resolve_will()
                choice = self.s.rules_engine["pendingChoice"]
                self.assertEqual((choice["kind"], choice["playerId"]), ("effect_memory_payment", "p2"))
                error, _ = self.s.resolve_rules_choice("p2", choice["id"], card_ids=["m2"] if payment == "pay" else [], option=payment)
                self.assertIsNone(error)
                self.assertIn(tribute, self.s.players["p1"]["zones"]["graveyard" if payment == "pay" else "hand"])

    def test_coral_skull_has_no_loss_requirement(self):
        self.pay("Coral Skull")
        self.resolve_will()
        self.compare("won")
        self.assertEqual(len(self.end()), 1)
        self.assertEqual(self.s.rules_engine["pendingChoice"]["kind"], "optional_stack_action")

    def test_return_self_memories_keep_the_real_owner_of_a_foreign_tribute(self):
        for name in ("Refrain Repeater", "Qu Lom, Haphazard Martyr"):
            with self.subTest(card=name):
                self.setUp()
                tribute, _ = self.pay(name, owner="p2")
                self.assertIn(tribute, self.s.players["p2"]["zones"]["graveyard"])
                memory = self.s.rules_engine["effectMemories"][0]
                self.assertEqual(memory["ownerId"], "p2")
                self.assertEqual(memory["controllerId"], "p1")
                self.resolve_will()
                self.assertEqual(len(self.end()), 1)
                with patch("game.effects.stack.random.randint", return_value=4):
                    self.resolve_will()
                if name == "Refrain Repeater":
                    choice = self.s.rules_engine["pendingChoice"]
                    self.assertIsNone(self.s.resolve_rules_choice("p2", choice["id"], option="decline")[0])
                self.assertIn(tribute, self.s.players["p2"]["zones"]["hand"])
                self.assertNotIn(tribute, self.s.players["p1"]["zones"]["hand"])

    def test_loop_and_coral_skull_do_not_remember_a_will_activation_as_a_played_will(self):
        for name in ("Loop, the Insistent", "Coral Skull"):
            with self.subTest(card=name):
                self.setUp()
                host = self.f.field(self.s, "ufujqhwlpmaw12y_en", item="host", zone="field")
                self.enemy["isSupport"] = True
                tribute = self.f.cid(name)
                self.f.put(self.s, "p1", "hand", [tribute])
                self.s.rules_engine["priorityPlayerId"] = "p1"
                error, action = self.s.declare_rules_action("p1", "Ignore Support power", kind="activated_effect",
                    source={"cardId": host["cardId"], "zone": "battlefield", "itemId": host["id"]},
                    targets=[self.f.target(self.enemy)], payment_card_ids=[tribute], ability_id="ignore-support-power")
                self.assertIsNone(error)
                main.log_rules_declared_action(self.s, action)
                self.assertEqual(self.s.rules_engine["effectMemories"], [])
                self.assertEqual([a["id"] for a in self.s.rules_engine["actionStack"]], [action["id"]])

    def test_an_actual_tribute_trigger_still_enters_the_stack_batch(self):
        tribute, action = self.pay("Filth-eater")
        choice = self.s.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "trigger_targets")
        self.assertEqual(choice["sourceCardId"], tribute)
        self.assertIsNone(self.s.resolve_rules_choice("p1", choice["id"], targets=[{"kind": "player", "playerId": "p2"}])[0])
        stack = self.s.rules_engine["actionStack"]
        self.assertEqual(len(stack), 2)
        self.assertTrue(any(a["id"] == action["id"] for a in stack))
        effect = next(a for a in stack if a["source"]["cardId"] == tribute)
        self.assertEqual(effect["ability"]["result"]["kind"], "discard_hand_target")
        self.assertEqual(self.s.rules_engine["effectMemories"], [])
