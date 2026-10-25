"""Tenebro's optional discard replacement, with literal destination/event oracles."""
import copy
import json
import unittest

import test_semantic_batch_001_150 as semantic


class TenebroReplacementAudit(unittest.TestCase):
    fixture = semantic.SemanticBatch001150()
    TENEBRO = "kl0n8mt9m1fwly0_en"
    BOB = "inner-deserts-134"

    def world(self, zone="hand", *, watcher=False):
        s = self.fixture.world()
        self.fixture.put(s, "p1", zone, [self.TENEBRO])
        if watcher:
            o = self.fixture.field(s, self.fixture.cid("Otranth, the Bloodthirsty"),
                                   "otranth", zone="interzone")
            o["counters"]["Shackle"] = 2
        return s

    @staticmethod
    def snapshot(s):
        return copy.deepcopy((s.players, s.battlefield, s.tokens))

    def choose(self, s, yes, player="p1"):
        choice = s.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "binary_choice")
        self.assertEqual(choice["purpose"], "discard_support_replacement")
        error, result = s.resolve_rules_choice(player, choice["id"], option="yes" if yes else "no")
        self.assertIsNone(error)
        return result

    def test_hand_discard_accept_and_refuse_before_any_move(self):
        for yes in (True, False):
            with self.subTest(accept=yes):
                s = self.world(watcher=True)
                before = self.snapshot(s)
                self.assertIsNone(s.move_zone_card("p1", "hand", "p1", "graveyard", self.TENEBRO)[0])
                self.assertEqual(self.snapshot(s), before)
                self.choose(s, yes)
                self.assertIsNone(s.rules_engine["pendingChoice"])
                self.assertNotIn(self.TENEBRO, s.players["p1"]["zones"]["hand"])
                self.assertEqual(self.TENEBRO in s.players["p1"]["zones"]["graveyard"], not yes)
                entries = [e for e in s.rules_engine["recentLimboEntries"] if e["cardId"] == self.TENEBRO]
                self.assertEqual(len(entries), 0 if yes else 1)
                actions = s.queue_rules_observed_event_triggers(defer=True)
                self.assertEqual([a["ability"]["id"] for a in actions],
                                 [] if yes else ["otranth-loses-shackle-when-manifestation-enters-limbo"])
                for action in actions:
                    s.apply_rules_action_result(action)
                self.assertEqual(s.find_battlefield_item("otranth")["counters"]["Shackle"], 2 if yes else 1)
                support = [i for i in s.battlefield if i.get("cardId") == self.TENEBRO]
                self.assertEqual(len(support), int(yes))
                if yes:
                    self.assertTrue(support[0]["isSupport"])
                    self.assertEqual(support[0]["supportWinDestination"], "exile")

    def test_deck_discard_accept_and_refuse_preserve_other_cards(self):
        for yes in (True, False):
            with self.subTest(accept=yes):
                s = self.world("deck")
                s.players["p1"]["zones"]["deck"].append("m2")
                s.players["p1"]["zoneOwners"]["deck"]["m2"] = "p1"
                before = self.snapshot(s)
                error, _owner, result = s.move_zone_card_by_effect(
                    "p1", "deck", "p1", "graveyard", self.TENEBRO)
                self.assertIsNone(error)
                self.assertEqual(result["choiceKind"], "binary_choice")
                self.assertEqual(self.snapshot(s), before)
                self.choose(s, yes)
                self.assertEqual(s.players["p1"]["zones"]["deck"], ["m2"])
                self.assertEqual(self.TENEBRO in s.players["p1"]["zones"]["graveyard"], not yes)
                kinds = [event["kind"] for event in s.rules_engine["observedEvents"]]
                self.assertIn("cards_discarded", kinds)
                self.assertIn("deck_cards_discarded", kinds)
                self.assertEqual("card_entered_limbo" in kinds, not yes)

    def test_multi_discard_collects_two_choices_before_any_card_changes(self):
        for first, second in ((True, True), (True, False), (False, True), (False, False)):
            with self.subTest(first=first, second=second):
                s = self.world("deck")
                # Distinct object identity with the same printed replacement.
                other = "second-tenebro-object"
                s.card_rules[other] = copy.deepcopy(s.card_rules[self.TENEBRO])
                self.fixture.put(s, "p1", "deck", [self.TENEBRO, other, "m2"])
                action = {"id": "discard-three", "controllerId": "p1", "kind": "triggered_effect",
                          "source": {"cardId": "discard-effect"},
                          "ability": {"result": {"kind": "discard_deck_owner", "value": 3}}}
                before = self.snapshot(s)
                result = s.apply_rules_action_result(action)
                self.assertEqual(result["choiceKind"], "binary_choice")
                self.assertEqual(self.snapshot(s), before)
                self.choose(s, first)
                self.assertEqual(self.snapshot(s), before, "first answer must not partially discard the Deck")
                self.choose(s, second)
                self.assertFalse(bool(s.rules_engine["pendingChoice"]), "both answers must complete the original discard once")
                self.assertEqual(s.players["p1"]["zones"]["deck"], [])
                self.assertEqual(self.TENEBRO in s.players["p1"]["zones"]["graveyard"], not first)
                self.assertEqual(other in s.players["p1"]["zones"]["graveyard"], not second)
                self.assertIn("m2", s.players["p1"]["zones"]["graveyard"])
                self.assertEqual(sum(i.get("isSupport", False) for i in s.battlefield), int(first) + int(second))

    def test_tribute_is_not_a_discard_and_does_not_offer_support(self):
        s = self.world()
        self.fixture.put(s, "p1", "hand", [self.TENEBRO, "w2"])
        s.rules_engine["priorityPlayerId"] = "p1"
        error, action = s.declare_rules_action("p1", "Pay Will", kind="play_card",
            source={"cardId": "w2", "zone": "hand"}, payment_card_ids=[self.TENEBRO])
        self.assertIsNone(error)
        self.assertIsNone(s.rules_engine["pendingChoice"])
        self.assertIn(self.TENEBRO, s.players["p1"]["zones"]["graveyard"])
        self.assertEqual(action["cost"]["tributeCardIds"], [self.TENEBRO])
        self.assertFalse(any(i.get("cardId") == self.TENEBRO for i in s.battlefield))
        self.assertFalse(any(e["kind"] == "cards_discarded" for e in s.rules_engine["observedEvents"]))

    def test_three_discard_choices_survive_reconnect_projection_before_commit(self):
        s = self.world("deck")
        copies = [self.TENEBRO, "second-tenebro-object", "third-tenebro-object"]
        for cid in copies[1:]:
            s.card_rules[cid] = copy.deepcopy(s.card_rules[self.TENEBRO])
        self.fixture.put(s, "p1", "deck", copies)
        action = {"id": "discard-three", "controllerId": "p1", "kind": "triggered_effect",
                  "source": {"cardId": "discard-effect"},
                  "ability": {"result": {"kind": "discard_deck_owner", "value": 3}}}
        before = self.snapshot(s)
        s.apply_rules_action_result(action)
        for index, accept in enumerate((True, False, True)):
            choice = s.rules_engine["pendingChoice"]
            self.assertEqual(choice["sourceCardId"], copies[index])
            for viewer in ("p1", "p2"):
                public = s.serialize_for(viewer, "player")["rulesEngine"]["pendingChoice"]
                self.assertEqual(public["id"], choice["id"])
                self.assertFalse(any(key.startswith("_") for key in public))
            self.assertEqual(self.snapshot(s), before)
            self.choose(s, accept)
        self.assertFalse(bool(s.rules_engine["pendingChoice"]))
        self.assertEqual(s.players["p1"]["zones"]["deck"], [])
        self.assertEqual(s.players["p1"]["zones"]["graveyard"], [copies[1]])
        self.assertEqual([item["cardId"] for item in s.battlefield], [copies[0], copies[2]])
        self.assertEqual(len(s.rules_engine["recentLimboEntries"]), 1)

    def test_immediate_discard_hand_overflow_keeps_original_choice_atomic(self):
        for yes in (True, False):
            with self.subTest(accept=yes):
                s = self.world()
                other_cards = [f"overflow-card-{n}" for n in range(7)]
                self.fixture.put(s, "p1", "hand", [self.TENEBRO, *other_cards])
                s.rules_engine["handLimitEffects"] = [{"turn": 2, "playerId": "p1", "limit": 7,
                                                      "overflowDestination": "graveyard"}]
                original = s.set_rules_hand_overflow_choice(["p1"])
                before = self.snapshot(s)
                error, result = s.resolve_rules_choice("p1", original["id"], card_ids=[self.TENEBRO])
                self.assertIsNone(error)
                self.assertEqual(result["choiceKind"], "binary_choice")
                self.assertEqual(self.snapshot(s), before)
                self.choose(s, yes)
                self.assertEqual(s.players["p1"]["zones"]["hand"], other_cards)
                self.assertEqual(self.TENEBRO in s.players["p1"]["zones"]["graveyard"], not yes)
                self.assertIsNone(s.rules_engine["pendingChoice"])

    def test_normal_overflow_deck_bottom_is_not_a_discard(self):
        s = self.world()
        self.fixture.put(s, "p1", "hand", [self.TENEBRO, *[f"c-{n}" for n in range(7)]])
        choice = s.set_rules_hand_overflow_choice(["p1"])
        self.assertIsNone(s.resolve_rules_choice("p1", choice["id"], card_ids=[self.TENEBRO])[0])
        self.assertIn(self.TENEBRO, s.players["p1"]["zones"]["deck"])
        self.assertIsNone(s.rules_engine["pendingChoice"])
        self.assertFalse(any(i.get("cardId") == self.TENEBRO for i in s.battlefield))

    def test_pending_choice_survives_reconnect_views_without_private_operation_data(self):
        s = self.world()
        self.fixture.put(s, "p1", "hand", [self.TENEBRO, "w2"])
        s.move_zone_card("p1", "hand", "p1", "graveyard", self.TENEBRO)
        cid = s.rules_engine["pendingChoice"]["id"]
        for _ in range(2):
            for viewer in ("p1", "p2"):
                view = s.serialize_for(viewer, "player")
                # serialize_for is the same reconnect state projection used by the server.
                public = view["rulesEngine"]["pendingChoice"]
                self.assertEqual(public["id"], cid)
                self.assertFalse(any(key.startswith("_") for key in public))
                self.assertNotIn("w2", json.dumps(public))
        self.choose(s, True)
        self.assertIsNone(s.rules_engine["pendingChoice"])

    def test_opponent_or_invalid_answer_cannot_choose_the_replacement(self):
        s = self.world()
        s.move_zone_card("p1", "hand", "p1", "graveyard", self.TENEBRO)
        choice = s.rules_engine["pendingChoice"]
        for player, option in (("p2", "yes"), ("p1", "maybe")):
            before = copy.deepcopy((s.players, s.battlefield, s.rules_engine))
            self.assertIsNotNone(s.resolve_rules_choice(player, choice["id"], option=option)[0])
            self.assertEqual((s.players, s.battlefield, s.rules_engine), before)
        self.choose(s, False)

    def test_pin_down_blocks_put_but_arena_play_only_lock_allows_it(self):
        for play_only, expected_choice in ((False, False), (True, True)):
            with self.subTest(playOnly=play_only):
                s = self.world()
                s.rules_engine["supportLocks"] = [{"turn": 2, "playerId": None, "playOnly": play_only}]
                s.move_zone_card("p1", "hand", "p1", "graveyard", self.TENEBRO)
                self.assertEqual(bool(s.rules_engine["pendingChoice"]), expected_choice)
                if expected_choice:
                    self.choose(s, True)
                    self.assertTrue(any(i.get("cardId") == self.TENEBRO for i in s.battlefield))
                else:
                    self.assertIn(self.TENEBRO, s.players["p1"]["zones"]["graveyard"])

    def test_bob_competing_order_then_optional_yes_or_no(self):
        for first, accept in (("support", True), ("support", False), ("suspend", None)):
            with self.subTest(first=first, accept=accept):
                s = self.world()
                bob = self.fixture.field(s, self.BOB, "bob")
                bob["counters"]["power"] = 3  # printed2 +3 reaches Limbo suspension at5.
                before = self.snapshot(s)
                error, _owner, result = s.move_zone_card_by_effect("p1", "hand", "p1", "graveyard", self.TENEBRO)
                self.assertIsNone(error)
                self.assertEqual(result["choiceKind"], "replacement_order")
                choice = s.rules_engine["pendingChoice"]
                order = [e["actionId"] for e in sorted(choice["actions"], key=lambda e: e["replacementKind"] == first)]
                self.assertEqual(self.snapshot(s), before)
                self.assertIsNone(s.resolve_rules_choice("p1", choice["id"], card_ids=order)[0])
                if first == "support":
                    self.assertEqual(self.snapshot(s), before)
                    self.choose(s, accept)
                self.assertIsNone(s.rules_engine["pendingChoice"])
                supported = any(i.get("cardId") == self.TENEBRO for i in s.battlefield)
                self.assertEqual(supported, first == "support" and accept)
                self.assertEqual(bool(s.rules_engine["suspendedCards"]), not supported)
                self.assertNotIn(self.TENEBRO, s.players["p1"]["zones"]["graveyard"])


if __name__ == "__main__":
    unittest.main()
