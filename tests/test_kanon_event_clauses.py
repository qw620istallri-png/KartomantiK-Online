"""Printed-text oracles for Kanon's replacement and its observed events.

Real shipped rules are used for sources/watchers. Synthetic cards provide
known values and duplicates. Trigger resolution is isolated where stated.
"""
import copy
import unittest
from unittest.mock import patch
import test_discard_draw_clauses as base


class KanonEventClauses(unittest.TestCase):
    world = base.DiscardDrawClauses.world
    cid = staticmethod(base.DiscardDrawClauses.cid)
    field = staticmethod(base.DiscardDrawClauses.field)
    put = staticmethod(base.DiscardDrawClauses.put)
    snapshot = base.DiscardDrawClauses.snapshot
    choose = base.DiscardDrawClauses.choose
    KANON = "Kanon, the Deathdealer"
    DENBLEW = "Denblew, the Puritan"
    MAKA = "Makaboon"
    GORLOK = "Gorlok, the Blinded Indiscreet"
    TOMB = "Tombloom"
    TENE = "Tenebro, Night Assailant"

    def setup(self, deck=("m2", "m3", "m4", "w2")):
        s = self.world()
        host = self.field(s, self.cid(self.KANON), "kanon", owner="p2")
        self.put(s, "p1", "deck", deck)
        return s, host

    def replace(self, s, count, discarded):
        result = s.request_rules_draw("p1", count, source_controller_id="p1")
        self.assertEqual(result["kind"], "choice_required")
        return self.choose(s, card_ids=list(discarded))

    def watcher(self, s, name, owner="p2", zone="confrontation"):
        return self.field(s, self.cid(name), "watcher", owner=owner, zone=zone)

    @staticmethod
    def watcher_actions(s, host):
        return [a for a in s.queue_rules_observed_event_triggers(defer=True)
                if (a.get("source") or {}).get("itemId") == host["id"]]

    @staticmethod
    def resolve_isolated(s, actions):
        for action in actions:
            s.apply_rules_action_result(action)
            s.create_rules_ongoing_effects(action)

    def test_half_rounded_up_and_short_deck_quantities(self):
        for deck, count, discard, kept in ((["m2"], 1, ["m2"], []),
                (["m2", "m3"], 2, ["m2"], ["m3"]),
                (["m2", "m3", "m4"], 3, ["m2", "m3"], ["m4"]),
                (["m2", "m3", "m4"], 8, ["m2", "m3"], ["m4"])):
            with self.subTest(deck=deck, count=count):
                s, _ = self.setup(deck)
                result = self.replace(s, count, discard)
                self.assertEqual(result["drawnCardIds"], kept)
                self.assertEqual(s.players["p1"]["zones"]["hand"], kept)
                self.assertCountEqual(s.players["p1"]["zones"]["graveyard"], discard)
                self.assertEqual(s.players["p1"]["zones"]["deck"], [])

    def test_inspection_does_not_move_cards_before_confirmation(self):
        s, _ = self.setup()
        before = copy.deepcopy(s.players)
        s.request_rules_draw("p1", 4)
        self.assertEqual(s.players, before)
        self.assertEqual(s.rules_engine.get("observedEvents") or [], [])

    def test_invalid_choices_are_atomic_including_malformed_ids(self):
        for actor, cards in (("p2", ["m2", "m3"]), ("p1", []), ("p1", ["m2"]),
                ("p1", ["m2", "absent"]), ("p1", ["m2", "m2"]), ("p1", [{}, "m2"])):
            with self.subTest(actor=actor, cards=cards):
                s, _ = self.setup()
                s.request_rules_draw("p1", 4)
                choice = s.rules_engine["pendingChoice"]
                before = self.snapshot(s)
                self.assertIsNotNone(s.resolve_rules_choice(actor, choice["id"], card_ids=cards)[0])
                self.assertEqual(self.snapshot(s), before)

    def test_identical_copies_are_selected_by_quantity(self):
        for deck, discard, kept in ((["m2", "m2", "m2", "m2"], ["m2", "m2"], ["m2", "m2"]),
                (["m2", "m2", "m3", "m4"], ["m2", "m3"], ["m2", "m4"])):
            with self.subTest(deck=deck):
                s, _ = self.setup(deck)
                result = self.replace(s, 4, discard)
                self.assertEqual(result["drawnCardIds"], kept)
                self.assertEqual(s.players["p1"]["zones"]["hand"], kept)
                self.assertCountEqual(s.players["p1"]["zones"]["graveyard"], discard)

    def test_discards_all_chosen_cards_before_drawing_the_rest(self):
        s, _ = self.setup()
        with patch.object(s, "put_zone_card", wraps=s.put_zone_card) as moved:
            self.replace(s, 4, ["m3", "w2"])
        self.assertEqual([call.args[1] for call in moved.call_args_list],
                         ["graveyard", "graveyard", "hand", "hand"])

    def test_draw_records_only_kept_cards_and_one_batch(self):
        s, _ = self.setup()
        self.replace(s, 4, ["m2", "m3"])
        events = [e for e in s.rules_engine.get("observedEvents") or [] if e["kind"] == "cards_drawn"]
        self.assertEqual(len(events), 2)
        self.assertEqual(len({e["drawBatchId"] for e in events}), 1)
        self.assertTrue(events[0]["drawBatchId"])
        self.assertEqual(s.rules_engine["drawnOutsideRecovery"]["p1"]["cardIds"], ["m4", "w2"])

    def test_denblew_gets_one_bonus_for_multi_card_kept_draw(self):
        s, _ = self.setup()
        host = self.watcher(s, self.DENBLEW)
        before = s.rules_manifestation_characteristics(host)["power"]
        self.replace(s, 4, ["m2", "m3"])
        actions = self.watcher_actions(s, host)
        self.assertEqual(len(actions), 1)
        self.resolve_isolated(s, actions)
        self.assertEqual(s.rules_manifestation_characteristics(host)["power"], before + 1)

    def test_denblew_sees_two_distinct_replaced_draws_before_flush(self):
        s, _ = self.setup()
        host = self.watcher(s, self.DENBLEW)
        before = s.rules_manifestation_characteristics(host)["power"]
        self.replace(s, 2, ["m2"])
        self.replace(s, 2, ["m4"])
        actions = self.watcher_actions(s, host)
        self.assertEqual(len(actions), 2)
        self.resolve_isolated(s, actions)
        self.assertEqual(s.rules_manifestation_characteristics(host)["power"], before + 2)

    def test_denblew_separates_normal_and_replaced_draw_batches(self):
        s, _ = self.setup()
        host = self.watcher(s, self.DENBLEW)
        s.draw_rules_cards("p1", 1)  # Explicit non-replaced event fixture.
        self.replace(s, 2, ["m3"])
        self.assertEqual(len(self.watcher_actions(s, host)), 2)

    def test_denblew_no_bonus_when_no_cards_are_drawn_or_own_player_draws(self):
        for owner in ("p1", "p2"):
            with self.subTest(owner=owner):
                s, _ = self.setup()
                host = self.watcher(s, self.DENBLEW, owner=owner)
                self.replace(s, 1 if owner == "p2" else 2, ["m2"])
                self.assertEqual(self.watcher_actions(s, host), [])

    def test_inactive_watchers_do_not_trigger(self):
        for inactive in ("face_down", "silenced"):
            with self.subTest(inactive=inactive):
                s, _ = self.setup()
                host = self.watcher(s, self.DENBLEW)
                if inactive == "face_down":
                    host["faceUp"] = False
                else:
                    s.rules_engine["ongoingEffects"].append({"id": "silence", "kind": "lose_effects",
                        "target": {"kind": "card", "itemId": host["id"]}, "duration": "while_target_on_field"})
                self.replace(s, 2, ["m2"])
                self.assertEqual(self.watcher_actions(s, host), [])

    def test_makaboon_discards_one_extra_from_hand_per_deck_discard_batch(self):
        s, _ = self.setup()
        host = self.watcher(s, self.MAKA)
        self.replace(s, 4, ["m2", "m3"])
        actions = self.watcher_actions(s, host)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["targets"], [{"kind": "player", "playerId": "p1"}])
        self.resolve_isolated(s, actions)
        self.assertEqual(s.rules_engine["pendingChoice"]["kind"], "discard_from_hand")
        self.choose(s, card_ids=["w2"])
        self.assertEqual(s.players["p1"]["zones"]["hand"], ["m4"])
        self.assertEqual(self.watcher_actions(s, host), [], "A hand discard is not another deck discard")

    def test_makaboon_empty_hand_does_not_open_an_impossible_choice(self):
        s, _ = self.setup(["m2"])
        host = self.watcher(s, self.MAKA)
        self.replace(s, 1, ["m2"])
        actions = self.watcher_actions(s, host)
        self.assertEqual(len(actions), 1)
        self.resolve_isolated(s, actions)
        self.assertIsNone(s.rules_engine["pendingChoice"])

    def test_discard_score_watchers_trigger_once_for_two_discards(self):
        for name, zone, player, expected in (("Pale Entity", "interzone", "p2", 55),
                ("Forfog, the Hanged", "interzone", "p1", 45)):
            with self.subTest(card=name):
                s, _ = self.setup()
                host = self.watcher(s, name, zone=zone)
                self.replace(s, 4, ["m2", "m3"])
                actions = self.watcher_actions(s, host)
                self.assertEqual(len(actions), 1)
                self.resolve_isolated(s, actions)
                self.assertEqual(s.players[player]["score"], expected)

    def test_tombloom_discard_trigger_exiles_source_and_weakens_target(self):
        s, _ = self.setup([self.cid(self.TOMB), "m2"])
        target = self.field(s, "m4", "target")
        self.replace(s, 2, [self.cid(self.TOMB)])
        entries = [e for e in s.rules_engine["recentLimboEntries"] if e["cardId"] == self.cid(self.TOMB)]
        self.assertEqual([(e["fromZone"], e["reason"]) for e in entries], [("deck", "discard")])
        s.queue_rules_observed_event_triggers(defer=True)
        choice = s.rules_engine["pendingChoice"]
        self.assertIsNotNone(choice)
        self.assertEqual((choice["kind"], choice["sourceCardId"]), ("trigger_targets", self.cid(self.TOMB)))
        self.choose(s, targets=[{"kind": "card", "itemId": target["id"], "cardId": target["cardId"]}])
        self.assertEqual(len(s.rules_engine["actionStack"]), 1)
        s.resolve_rules_top_action()
        self.assertIn(self.cid(self.TOMB), s.players["p1"]["zones"]["exile"])
        self.assertEqual(s.rules_manifestation_characteristics(target)["power"], 2)

    def test_gorlok_single_event_shows_only_kept_cards_then_exiles_one(self):
        s, _ = self.setup()
        host = self.watcher(s, self.GORLOK, zone="interzone")
        before = s.rules_manifestation_characteristics(host)["power"]
        self.replace(s, 4, ["m2", "m3"])
        actions = self.watcher_actions(s, host)
        self.assertEqual(len(actions), 1)
        self.resolve_isolated(s, actions)
        self.assertEqual(s.rules_engine["pendingChoice"]["cardIds"], ["m4", "w2"])
        self.choose(s, option="0")
        self.assertEqual(s.players["p1"]["zones"]["hand"], ["w2"])
        self.assertIn("m4", s.players["p1"]["zones"]["exile"])
        self.assertEqual(s.rules_manifestation_characteristics(host)["power"], before - 2)

    def test_tenebro_optional_replacement_is_offered_without_partial_movement(self):
        for option in ("yes", "no"):
            with self.subTest(option=option):
                card = self.cid(self.TENE)
                s, _ = self.setup([card, "m2"])
                s.request_rules_draw("p1", 2)
                before = copy.deepcopy(s.players)
                self.choose(s, card_ids=[card])
                pending = s.rules_engine["pendingChoice"]
                self.assertIsNotNone(pending)
                self.assertTrue(pending.get("_optionalReplacement"))
                self.assertEqual(pending["playerId"], "p1")
                self.assertEqual(s.players, before)
                self.choose(s, option=option)
                self.assertEqual(s.players["p1"]["zones"]["hand"], ["m2"])
                self.assertEqual(card in s.players["p1"]["zones"]["graveyard"], option == "no")
                items = [i for i in s.battlefield if i["cardId"] == card]
                self.assertEqual(len(items), int(option == "yes"))
                if items:
                    self.assertTrue(items[0]["isSupport"])
                kinds = [e["kind"] for e in s.rules_engine.get("observedEvents") or []]
                self.assertEqual(kinds.count("cards_discarded"), 1)
                self.assertEqual(kinds.count("deck_cards_discarded"), 1)

    def test_suspension_replaces_movements_without_draw_discard_or_will_penalty(self):
        # Historical evidence ID retained. The 2026-10-28 ruling supersedes its
        # original interpretation: replaced discards and Will penalties remain.
        s, _ = self.setup(["w2", "pw3", "m2", "m3"])
        self.field(s, "inner-deserts-134", "bob", power_bonus=2)
        target = self.field(s, "m4", "target")
        result = self.replace(s, 4, ["w2", "pw3"])
        self.assertEqual(result["willCount"], 2)
        self.assertEqual(result["drawnCardIds"], [])
        self.assertEqual(result["discardedCardIds"], [])
        self.assertEqual(s.players["p1"]["zones"]["hand"], [])
        self.assertEqual(s.players["p1"]["zones"]["graveyard"], [])
        self.assertCountEqual([c["cardId"] for c in s.rules_engine["suspendedCards"]], ["w2", "pw3", "m2", "m3"])
        kinds=[e["kind"] for e in s.rules_engine.get("observedEvents") or []]
        self.assertEqual(kinds.count("cards_discarded"),2)
        self.assertEqual(kinds.count("deck_cards_discarded"),2)
        self.assertNotIn("cards_drawn",kinds)
        self.assertNotIn("card_entered_limbo",kinds)
        self.assertEqual(s.rules_engine["pendingChoice"]["kind"],"power_loss_distribution")
        self.assertEqual(s.rules_manifestation_characteristics(target)["power"], 4)
        self.choose(s,option={"itemIds":[target["id"],target["id"]]})
        self.assertEqual(s.rules_manifestation_characteristics(target)["power"],2)

    def test_discarded_wills_allow_split_or_repeated_target_and_exact_power_loss(self):
        for targets in (["a", "a"], ["a", "b"]):
            with self.subTest(targets=targets):
                s, _ = self.setup(["w2", "pw3", "m2", "m3"])
                a, b = self.field(s, "m4", "a"), self.field(s, "m3", "b", zone="interzone")
                result = self.replace(s, 4, ["w2", "pw3"])
                self.assertEqual(result["willCount"], 2)
                self.assertEqual(s.rules_engine["pendingChoice"]["kind"], "power_loss_distribution")
                self.choose(s, option={"itemIds": targets})
                self.assertEqual(s.rules_manifestation_characteristics(a)["power"], 4 - targets.count("a"))
                self.assertEqual(s.rules_manifestation_characteristics(b)["power"], 3 - targets.count("b"))

    def test_no_will_penalty_choice_without_a_legal_target(self):
        for absent in ("missing", "protected"):
            with self.subTest(absent=absent):
                s, _ = self.setup(["w2", "m2"])
                if absent == "protected":
                    target = self.field(s, "m4", "protected")
                    s.rules_engine["ongoingEffects"].append({"id": "shield", "kind": "protection",
                        "target": {"kind": "card", "itemId": target["id"]}, "duration": "while_target_on_field"})
                self.replace(s, 2, ["w2"])
                self.assertIsNone(s.rules_engine["pendingChoice"])

    def test_source_departure_does_not_cancel_already_created_replacement(self):
        s, host = self.setup()
        s.request_rules_draw("p1", 4)
        s._rules_remove_field_item(host, "p2", "graveyard")
        self.choose(s, card_ids=["m2", "m3"])
        self.assertEqual(s.players["p1"]["zones"]["hand"], ["m4", "w2"])

    def test_repeated_answer_cannot_move_or_trigger_again(self):
        s, _ = self.setup()
        s.request_rules_draw("p1", 2)
        choice = s.rules_engine["pendingChoice"]
        self.choose(s, card_ids=["m2"])
        before = self.snapshot(s)
        self.assertIsNotNone(s.resolve_rules_choice("p1", choice["id"], card_ids=["m2"])[0])
        self.assertEqual(self.snapshot(s), before)

    def test_stale_inspected_deck_is_cancelled_without_moving_cards(self):
        s, _ = self.setup()
        s.request_rules_draw("p1", 2)
        choice = s.rules_engine["pendingChoice"]
        s.players["p1"]["zones"]["deck"][:2] = ["m3", "m2"]
        before = copy.deepcopy(s.players)
        self.assertIsNotNone(s.resolve_rules_choice("p1", choice["id"], card_ids=["m2"])[0])
        self.assertIsNone(s.rules_engine["pendingChoice"])
        self.assertEqual(s.players, before)


if __name__ == "__main__":
    unittest.main()
