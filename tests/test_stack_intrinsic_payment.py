"""Duel Honorably: literal printed payment timing and resource oracles.

A player may pay two hollow essences while the card is on the Stack to
neutralize it. Neither requesting nor declining that payment resolves Duel.
"""
import copy
import json
import unittest

import test_semantic_batch_001_150 as fixtures

main = fixtures.main
ADVANCED_PHASES = fixtures.ADVANCED_PHASES


class StackIntrinsicPaymentTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.SemanticBatch001150()
        self.s = self.f.world()
        self.duel = self.f.cid("Duel Honorably")
        self.s.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_before_revelation")
        self.s.rules_engine["priorityPlayerId"] = "p1"
        self.f.put(self.s, "p1", "hand", [self.duel])
        error, self.action = self.s.declare_rules_action("p1", "Duel Honorably", kind="play_card",
            source={"cardId": self.duel, "zone": "hand"},
            ability_id="lock-support-entries-unless-opponent-pays")
        self.assertIsNone(error)
        self.assertEqual(self.s.rules_engine["actionStack"], [self.action])
        self.assertIsNone(self.s.rules_engine["pendingChoice"])

    def resources(self):
        return copy.deepcopy({"players": self.s.players, "tokens": self.s.tokens,
                              "battlefield": self.s.battlefield})

    def white(self, pid, amount):
        self.s.add_rules_excess_essence(pid, [{"temperament": "transcendent", "amount": amount}])

    def essence(self, pid, temperament=None):
        return sum(int(t.get("counters", {}).get("essence", 0)) for t in self.s.tokens
                   if t.get("ownerId") == pid and t.get("isEssence")
                   and (temperament is None or t.get("temperament") == temperament))

    def request(self, pid):
        error, result = self.s.request_rules_stack_payment(pid, self.action["id"])
        self.assertIsNone(error)
        choice = self.s.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "effect_payment")
        self.assertEqual(choice["playerId"], pid)
        self.assertEqual(choice["payment"], "{H}{H}")
        self.assertEqual(choice["requirements"], {"hollow": 2})
        self.assertTrue(choice["_neutralizeOnPay"])
        self.assertEqual(choice["targetActionId"], self.action["id"])
        self.assertEqual(result["choiceId"], choice["id"])
        self.assertIn(self.action, self.s.rules_engine["actionStack"])
        self.assertNotIn(self.duel, self.s.players["p1"]["zones"]["graveyard"])
        return choice

    def test_both_players_can_pay_with_priority_before_resolution_including_own_will(self):
        for payer in ("p1", "p2"):
            with self.subTest(payer=payer):
                self.setUp()
                self.white(payer, 3)
                if payer == "p1":
                    self.assertEqual(self.s.rules_engine["priorityPlayerId"], "p2")
                    self.assertIsNone(self.s.pass_rules_priority("p2")[0])
                    self.assertEqual(self.s.rules_engine["priorityPlayerId"], "p1")
                self.assertTrue(self.s.rules_player_can_act(payer))
                self.assertIsNone(self.s.rules_auto_pass_player())
                before = self.resources()
                choice = self.request(payer)
                self.assertEqual(self.resources(), before, "Opening payment spends no resources")
                self.assertIsNotNone(self.s.pass_rules_priority(payer)[0], "Cannot advance while payment is pending")
                error, result = self.s.resolve_rules_choice(payer, choice["id"], option="pay")
                self.assertIsNone(error)
                self.assertEqual(result["neutralized"]["status"], "neutralized")
                self.assertEqual(self.essence(payer), 1)
                self.assertEqual(self.s.rules_engine["actionStack"], [])
                self.assertEqual(self.s.players["p1"]["zones"]["graveyard"], [self.duel])
                self.assertEqual(self.s.rules_engine["priorityPasses"], [])
                self.assertIsNone(self.s.rules_engine["pendingChoice"])
                self.assertFalse(self.s.rules_support_entry_locked("p1"))
                self.assertFalse(self.s.rules_support_entry_locked("p2"))

    def test_decline_keeps_card_stack_and_put_lock_only_appears_when_duel_resolves(self):
        self.white("p2", 2)
        before = self.resources()
        choice = self.request("p2")
        error, result = self.s.resolve_rules_choice("p2", choice["id"], option="decline")
        self.assertIsNone(error)
        self.assertEqual(result["status"], "declined")
        self.assertEqual(self.resources(), before)
        self.assertEqual(self.s.rules_engine["actionStack"], [self.action])
        self.assertFalse(self.s.rules_support_entry_locked("p1"))
        self.assertFalse(self.s.rules_support_entry_locked("p2"))
        self.assertIsNone(self.s.pass_rules_priority("p2")[0])
        error, resolution = self.s.pass_rules_priority("p1")
        self.assertIsNone(error)
        self.assertEqual(resolution["status"], "resolved")
        self.assertEqual(self.s.rules_engine["actionStack"], [])
        self.assertIsNone(self.s.rules_engine["pendingChoice"], "Duel resolution does not open a second unless-payment prompt")
        self.assertTrue(self.s.rules_support_entry_locked("p1"))
        self.assertTrue(self.s.rules_support_entry_locked("p2"))

    def test_request_can_be_reopened_after_decline_without_spending(self):
        self.white("p2", 2)
        first = self.request("p2")
        self.assertIsNone(self.s.resolve_rules_choice("p2", first["id"], option="decline")[0])
        second = self.request("p2")
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(self.essence("p2"), 2)
        self.assertIsNone(self.s.resolve_rules_choice("p2", second["id"], option="pay")[0])
        self.assertEqual(self.essence("p2"), 0)

    def test_wrong_priority_nonplayer_missing_and_noneligible_target_requests_are_atomic(self):
        self.white("p1", 5)
        self.white("p2", 5)
        for pid, action_id in (("p1", self.action["id"]), ("spectator", self.action["id"]),
                               ("p2", "gone"), ("p2", None)):
            with self.subTest(player=pid, target=action_id):
                before = copy.deepcopy((self.resources(), self.s.rules_engine))
                self.assertIsNotNone(self.s.request_rules_stack_payment(pid, action_id)[0])
                self.assertEqual((self.resources(), self.s.rules_engine), before)
        unrelated = {"id": "unrelated", "kind": "play_card", "sourceOnStack": True,
                     "controllerId": "p1", "source": {"cardId": self.f.cid("Ponder"), "ownerId": "p1"}}
        self.s.rules_engine["actionStack"].append(unrelated)
        before = copy.deepcopy((self.resources(), self.s.rules_engine))
        self.assertIsNotNone(self.s.request_rules_stack_payment("p2", "unrelated")[0])
        self.assertEqual((self.resources(), self.s.rules_engine), before)

    def test_insufficient_payment_invalid_option_and_wrong_chooser_do_not_spend(self):
        self.white("p2", 1)
        choice = self.request("p2")
        for pid, option in (("p2", "pay"), ("p2", "bogus"), ("p1", "pay")):
            with self.subTest(player=pid, option=option):
                before = copy.deepcopy((self.resources(), self.s.rules_engine))
                self.assertIsNotNone(self.s.resolve_rules_choice(pid, choice["id"], option=option)[0])
                self.assertEqual((self.resources(), self.s.rules_engine), before)

    def test_duplicate_request_while_pending_does_not_replace_choice(self):
        choice = self.request("p2")
        before = copy.deepcopy((self.resources(), self.s.rules_engine))
        self.assertIsNotNone(self.s.request_rules_stack_payment("p2", self.action["id"])[0])
        self.assertEqual((self.resources(), self.s.rules_engine), before)
        self.assertEqual(self.s.rules_engine["pendingChoice"]["id"], choice["id"])

    def test_target_disappears_before_payment_no_resources_are_spent(self):
        self.white("p2", 4)
        choice = self.request("p2")
        self.s.rules_engine["actionStack"].remove(self.action)
        before = self.resources()
        self.assertIsNotNone(self.s.resolve_rules_choice("p2", choice["id"], option="pay")[0])
        self.assertEqual(self.resources(), before)
        self.assertIsNone(self.s.rules_engine["pendingChoice"])
        self.assertEqual(self.essence("p2"), 4)

    def test_payment_can_neutralize_duel_below_another_stack_card_without_resolving_either(self):
        self.white("p2", 2)
        unrelated = {"id": "upper", "kind": "play_card", "sourceOnStack": True,
                     "controllerId": "p1", "source": {"cardId": self.f.cid("Ponder"), "ownerId": "p1"}}
        self.s.rules_engine["actionStack"].append(unrelated)
        choice = self.request("p2")
        self.assertIsNone(self.s.resolve_rules_choice("p2", choice["id"], option="pay")[0])
        self.assertEqual(self.s.rules_engine["actionStack"], [unrelated])
        self.assertEqual(self.s.players["p1"]["zones"]["graveyard"], [self.duel])
        self.assertFalse(self.s.rules_support_entry_locked("p1"))

    def test_tribute_payment_uses_real_manifestation_and_preserves_surplus(self):
        self.f.put(self.s, "p2", "hand", ["m3"])
        choice = self.request("p2")
        error, result = self.s.resolve_rules_choice("p2", choice["id"], option="pay", card_ids=["m3"])
        self.assertIsNone(error)
        self.assertEqual(result["neutralized"]["status"], "neutralized")
        self.assertEqual(self.s.players["p2"]["zones"]["hand"], [])
        self.assertIn("m3", self.s.players["p2"]["zones"]["graveyard"])
        self.assertEqual(self.essence("p2", "phlegmatic"), 1, "Three green paid for two hollow leaves one green")

    def test_tribute_payment_preserves_optional_mirror_trigger_choice(self):
        self.f.field(self.s, self.f.cid("Melancholic Mirror"), item="mirror", owner="p2", zone="field")
        self.f.put(self.s, "p2", "hand", ["m3"])
        choice = self.request("p2")
        error, result = self.s.resolve_rules_choice("p2", choice["id"], option="pay", card_ids=["m3"])
        self.assertIsNone(error)
        self.assertEqual(result["neutralized"]["status"], "neutralized")
        self.assertEqual(len(result["triggeredActions"]), 1)
        pending = self.s.rules_engine["pendingChoice"]
        self.assertIsNotNone(pending, "The completed payment must not erase a new optional Tribute trigger's choice")
        self.assertEqual(pending["playerId"], "p2")
        self.assertEqual(pending["kind"], "optional_stack_action")
        self.assertEqual(pending["sourceCardId"], self.f.cid("Melancholic Mirror"))

    def test_gem_conversion_inside_pending_payment_works_without_putting_new_effect_on_stack(self):
        splendor = self.f.field(self.s, self.f.cid("Temperamental Splendor"), item="splendor", owner="p2", zone="field")
        splendor.update(chosenTemperament="choleric", counters={"Gem": 2})
        choice = self.request("p2")
        for expected in (1, 2):
            error, result = self.s.spend_rules_counter_essence("p2", splendor["id"], "splendor-spends-a-gem-as-excess-essence")
            self.assertIsNone(error)
            self.assertEqual(result["amount"], 1)
            self.assertEqual(self.essence("p2", "choleric"), expected)
            self.assertEqual(self.s.rules_engine["actionStack"], [self.action])
            self.assertEqual(self.s.rules_engine["pendingChoice"]["id"], choice["id"])
        self.assertIsNone(self.s.resolve_rules_choice("p2", choice["id"], option="pay")[0])
        self.assertEqual(self.essence("p2"), 0)
        self.assertEqual(self.s.rules_engine["actionStack"], [])

    def test_autopass_keeps_intrinsic_payment_with_white_tribute_or_gems(self):
        for resources in ("white", "tribute", "gems"):
            with self.subTest(resources=resources):
                self.setUp()
                if resources == "white":
                    self.white("p2", 2)
                elif resources == "tribute":
                    self.f.put(self.s, "p2", "hand", ["m2"])
                else:
                    obj = self.f.field(self.s, self.f.cid("Temperamental Splendor"), owner="p2", zone="field")
                    obj.update(chosenTemperament="vitreous", counters={"Gem": 2})
                self.assertTrue(self.s.rules_player_can_act("p2"))
                self.assertIsNone(self.s.rules_auto_pass_player())

    def test_no_payment_resources_can_autopass_and_immediate_effect_blocks_request(self):
        self.assertFalse(self.s.rules_player_can_act("p2"))
        self.assertEqual(self.s.rules_auto_pass_player(), "p2")
        self.s.rules_engine["actionStack"].append({"id": "immediate", "immediate": True})
        before = copy.deepcopy((self.resources(), self.s.rules_engine))
        self.assertIsNotNone(self.s.request_rules_stack_payment("p2", self.action["id"])[0])
        self.assertEqual((self.resources(), self.s.rules_engine), before)

    def test_resolved_duel_cannot_be_paid_later(self):
        self.s.resolve_rules_top_action()
        self.white("p2", 2)
        before = copy.deepcopy((self.resources(), self.s.rules_engine))
        self.assertIsNotNone(self.s.request_rules_stack_payment("p2", self.action["id"])[0])
        self.assertEqual((self.resources(), self.s.rules_engine), before)


class CaptureSocket:
    def __init__(self):
        self.messages = []

    async def send(self, raw):
        self.messages.append(json.loads(raw))


class StackIntrinsicPaymentObserverTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_only_roles_cannot_request_or_spend_even_with_a_real_player_id(self):
        for role in ("observer", "spectator", "judge", "organizer"):
            with self.subTest(role=role):
                fixture = StackIntrinsicPaymentTests()
                fixture.setUp()
                fixture.white("p2", 4)
                socket = CaptureSocket()
                before = copy.deepcopy((fixture.resources(), fixture.s.rules_engine))
                await main.handle_message(socket, {"session": fixture.s, "playerId": "p2", "role": role},
                    {"type": "request_rules_stack_payment", "actionId": fixture.action["id"]})
                self.assertTrue(any(m.get("type") == "error" for m in socket.messages))
                self.assertEqual((fixture.resources(), fixture.s.rules_engine), before)

    async def test_read_only_roles_cannot_commit_or_convert_gems_in_a_players_pending_payment(self):
        for role in ("observer", "spectator", "judge", "organizer"):
            with self.subTest(role=role):
                fixture = StackIntrinsicPaymentTests()
                fixture.setUp()
                fixture.white("p2", 4)
                splendor = fixture.f.field(fixture.s, fixture.f.cid("Temperamental Splendor"),
                                           item="splendor", owner="p2", zone="field")
                splendor.update(chosenTemperament="choleric", counters={"Gem": 2})
                choice = fixture.request("p2")
                for message in (
                        {"type": "resolve_rules_choice", "choiceId": choice["id"], "option": "pay"},
                        {"type": "spend_counter_essence", "itemId": "splendor", "abilityId": "splendor-spends-a-gem-as-excess-essence"}):
                    socket = CaptureSocket()
                    before = copy.deepcopy((fixture.resources(), fixture.s.rules_engine))
                    await main.handle_message(socket, {"session": fixture.s, "playerId": "p2", "role": role}, message)
                    self.assertTrue(any(m.get("type") == "error" for m in socket.messages))
                    self.assertEqual((fixture.resources(), fixture.s.rules_engine), before)


if __name__ == "__main__":
    unittest.main()
