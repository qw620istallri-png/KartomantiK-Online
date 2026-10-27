"""Handwritten oracles for selected Atavic play counters and end-turn branches.

Counter event fixtures isolate the event from declaration; actual activated
Oppression declarations verify costs and discard-before-draw sequencing.
"""
import copy
import unittest
from unittest.mock import patch

import test_bounce_replay_clauses as base


class AtavicEndClauses(unittest.TestCase):
    world = base.BounceReplayClauses.world
    cid = staticmethod(base.BounceReplayClauses.cid)
    field = staticmethod(base.BounceReplayClauses.field)
    put = staticmethod(base.BounceReplayClauses.put)
    target = staticmethod(base.BounceReplayClauses.target)
    action = base.BounceReplayClauses.action
    snapshot = base.BounceReplayClauses.snapshot
    INTROSPECTION = "Atavic Introspection"
    OPPRESSION = "Atavic Oppression"
    CARDS = ((INTROSPECTION, "Control", "vitreous"), (OPPRESSION, "Fatigue", "melancholic"))

    def host(self, s, name, counter, amount=10, owner="p1", controller="p1"):
        item = self.field(s, self.cid(name), "host", owner=owner, controller=controller, zone="field")
        item["counters"][counter] = amount
        return item

    def event(self, s, color, player="p1", kind="play_card"):
        s.card_rules["event-will"] = {"type": "ephemeral_will", "temperaments": [color]}
        action = {"id": "played-stimulus", "kind": kind, "controllerId": player,
                  "source": {"cardId": "event-will", "ownerId": player}}
        s.rules_engine["actionStack"] = [action]
        queued = s.queue_rules_tribute_triggers([], player, simultaneous_action_id=action["id"])
        s.rules_engine["actionStack"] = []
        return queued

    def offer(self, s):
        actions = s.build_rules_end_turn_field_triggers()
        s.queue_rules_simultaneous_actions(actions)
        return actions

    def choose(self, s, **kwargs):
        choice = s.rules_engine["pendingChoice"]
        error, result = s.resolve_rules_choice(choice["playerId"], choice["id"], **kwargs)
        self.assertIsNone(error)
        return result

    def introspection(self, cards=("m2", "w2"), deck=("m4", "m3")):
        s = self.world()
        host = self.host(s, self.INTROSPECTION, "Control")
        self.put(s, "p1", "graveyard", cards)
        self.put(s, "p1", "deck", deck)
        return s, host

    def split_choice(self, s, cards=("m2", "w2"), depart=False):
        self.offer(s)
        self.choose(s, option="accept")
        self.assertEqual(s.rules_engine["pendingChoice"]["kind"], "trigger_targets")
        targets = [{"kind": "zone_card", "zone": "graveyard", "containerId": "p1", "cardId": cid} for cid in cards]
        self.choose(s, targets=targets)
        self.assertEqual(len(s.rules_engine["actionStack"]), 1)
        self.assertEqual(s.players["p1"]["zones"]["graveyard"], list(cards))
        if depart:
            s._rules_remove_field_item(s.find_battlefield_item("host"), "p1", "graveyard")
        s.resolve_rules_top_action()
        self.assertEqual(s.rules_engine["pendingChoice"]["kind"], "deck_reorder")
        return s.rules_engine["pendingChoice"]

    def activate_oppression(self, s, count=5):
        host = self.host(s, self.OPPRESSION, "Fatigue", count)
        error, action = s.declare_rules_action("p1", "Oppression", kind="activated_effect",
            source={"cardId": host["cardId"], "zone": "battlefield", "itemId": host["id"]},
            ability_id="spend-fatigues-to-make-opponent-discard")
        return host, error, action

    def test_matching_plays_add_one_counter_per_distinct_event(self):
        for name, counter, color in self.CARDS:
            with self.subTest(card=name):
                s = self.world()
                host = self.host(s, name, counter, 9)
                self.event(s, color)
                self.assertEqual(host["counters"][counter], 10)
                self.event(s, color)
                self.assertEqual(host["counters"][counter], 11)

    def test_wrong_color_opponent_play_and_activation_do_not_count(self):
        for name, counter, color in self.CARDS:
            for played, player, kind in (("choleric", "p1", "play_card"), (color, "p2", "play_card"), (color, "p1", "activated_effect")):
                with self.subTest(card=name, played=played, player=player, kind=kind):
                    s = self.world()
                    host = self.host(s, name, counter, 4)
                    self.event(s, played, player, kind)
                    self.assertEqual(host["counters"][counter], 4)

    def test_counter_follows_current_controller_not_immutable_owner(self):
        for name, counter, color in self.CARDS:
            with self.subTest(card=name):
                s = self.world()
                host = self.host(s, name, counter, 0, controller="p2")
                self.event(s, color, "p1")
                self.assertEqual(host["counters"][counter], 0)
                self.event(s, color, "p2")
                self.assertEqual(host["counters"][counter], 1)

    def test_face_down_or_blanked_source_does_not_collect(self):
        for name, counter, color in self.CARDS:
            for blank in (False, True):
                with self.subTest(card=name, blank=blank):
                    s = self.world()
                    host = self.host(s, name, counter, 0)
                    if blank:
                        s.rules_engine["ongoingEffects"].append({"id": "silence", "kind": "lose_effects", "target": self.target(host), "duration": "while_target_on_field"})
                    else:
                        host["faceUp"] = False
                    self.event(s, color)
                    self.assertEqual(host["counters"][counter], 0)

    def test_end_trigger_needs_ten_and_does_not_spend_counters(self):
        for name, counter, _ in self.CARDS:
            for amount in (9, 10, 15):
                with self.subTest(card=name, amount=amount):
                    s = self.world()
                    host = self.host(s, name, counter, amount)
                    self.put(s, "p1", "graveyard", ["m2", "w2"])
                    self.put(s, "p1", "hand", ["m3"])
                    actions = self.offer(s)
                    self.assertEqual(len(actions), 0 if amount == 9 else 1)
                    self.assertEqual(host["counters"][counter], amount)
                    if amount >= 10:
                        self.assertEqual(s.rules_engine["pendingChoice"]["kind"], "optional_stack_action")

    def test_skipped_end_phase_suppresses_only_its_controller(self):
        for name, counter, _ in self.CARDS:
            for skipped in ("p1", "p2"):
                with self.subTest(card=name, skipped=skipped):
                    s = self.world()
                    self.host(s, name, counter)
                    self.put(s, "p1", "graveyard", ["m2", "w2"])
                    self.put(s, "p1", "hand", ["m3"])
                    s.rules_engine["skipEndPhaseTurns"] = {skipped: 2}
                    self.assertEqual(len(self.offer(s)), 0 if skipped == "p1" else 1)

    def test_introspection_does_not_offer_with_fewer_than_two_cards(self):
        for cards in ([], ["m2"]):
            with self.subTest(cards=cards):
                s, _ = self.introspection(cards)
                self.offer(s)
                self.assertIsNone(s.rules_engine["pendingChoice"])
                self.assertEqual(s.rules_engine["actionStack"], [])

    def test_declining_end_effect_does_not_move_cards_or_spend_counters(self):
        for name, counter, _ in self.CARDS:
            with self.subTest(card=name):
                s = self.world()
                host = self.host(s, name, counter)
                self.put(s, "p1", "graveyard", ["m2", "w2"])
                self.put(s, "p1", "hand", ["m3"])
                zones = copy.deepcopy(s.players)
                self.offer(s)
                self.choose(s, option="decline")
                self.assertEqual(s.players, zones)
                self.assertEqual(host["counters"][counter], 10)
                self.assertIsNone(s.rules_engine["pendingChoice"])
                self.assertEqual(s.rules_engine["actionStack"], [])

    def test_introspection_places_exact_top_and_bottom_in_either_order(self):
        for cards in (("m2", "w2"), (self.cid("Trap"), "pw3")):
            for reverse in (False, True):
                with self.subTest(cards=cards, reverse=reverse):
                    s, host = self.introspection(cards)
                    self.split_choice(s, cards)
                    top, bottom = reversed(cards) if reverse else cards
                    with patch("game.zones.random.shuffle") as shuffle:
                        self.choose(s, option={"groups": [{"playerId": "p1", "top": [top], "bottom": [bottom]}]})
                    self.assertEqual(s.players["p1"]["zones"]["deck"], [top, "m4", "m3", bottom])
                    self.assertEqual(s.players["p1"]["zones"]["graveyard"], [])
                    self.assertEqual(host["counters"]["Control"], 10)
                    shuffle.assert_not_called()

    def test_introspection_invalid_orders_and_wrong_player_are_atomic(self):
        for option, player in (({"top": ["m2", "w2"], "bottom": []}, "p1"),
                               ({"top": ["m2"], "bottom": ["m2"]}, "p1"),
                               ({"top": ["m2"], "bottom": ["m4"]}, "p1"),
                               ({"top": ["m2"], "bottom": ["w2"]}, "p2")):
            with self.subTest(option=option, player=player):
                s, _ = self.introspection()
                choice = self.split_choice(s)
                before = self.snapshot(s)
                self.assertIsNotNone(s.resolve_rules_choice(player, choice["id"], option={"groups": [{"playerId": "p1", **option}]})[0])
                self.assertEqual(self.snapshot(s), before)

    def test_introspection_effect_survives_source_departure_after_targets(self):
        s, host = self.introspection()
        self.split_choice(s, depart=True)
        self.choose(s, option={"groups": [{"playerId": "p1", "top": ["m2"], "bottom": ["w2"]}]})
        self.assertEqual(s.players["p1"]["zones"]["deck"], ["m2", "m4", "m3", "w2"])

    def test_oppression_optional_discard_accepts_zero_one_or_two(self):
        for hand in (["m2"], ["m2", "m3", "m4"]):
            for count in range(min(2, len(hand)) + 1):
                with self.subTest(hand=hand, count=count):
                    s = self.world()
                    host = self.host(s, self.OPPRESSION, "Fatigue")
                    self.put(s, "p1", "hand", hand)
                    self.offer(s)
                    self.choose(s, option="accept")
                    s.resolve_rules_top_action()
                    self.choose(s, card_ids=hand[:count])
                    self.assertEqual(s.players["p1"]["zones"]["hand"], hand[count:])
                    self.assertCountEqual(s.players["p1"]["zones"]["graveyard"], hand[:count])
                    self.assertEqual(host["counters"]["Fatigue"], 10)

    def test_oppression_empty_hand_has_no_end_offer(self):
        s = self.world()
        self.host(s, self.OPPRESSION, "Fatigue")
        self.offer(s)
        self.assertIsNone(s.rules_engine["pendingChoice"])
        self.assertEqual(s.rules_engine["actionStack"], [])

    def test_oppression_activation_pays_five_before_responses(self):
        for amount in (4, 5, 11):
            with self.subTest(amount=amount):
                s = self.world()
                host, error, action = self.activate_oppression(s, amount)
                if amount == 4:
                    self.assertIsNotNone(error)
                    self.assertEqual(host["counters"]["Fatigue"], 4)
                    self.assertEqual(s.rules_engine["actionStack"], [])
                else:
                    self.assertIsNone(error)
                    self.assertEqual(host["counters"]["Fatigue"], amount - 5)
                    self.assertEqual(s.rules_engine["priorityPlayerId"], "p2")

    def test_oppression_discards_before_owner_draws(self):
        s = self.world()
        self.put(s, "p1", "deck", ["m4", "m3"])
        self.put(s, "p2", "hand", ["m2"])
        _, error, _ = self.activate_oppression(s)
        self.assertIsNone(error)
        s.resolve_rules_top_action()
        self.assertEqual(s.players["p1"]["zones"]["hand"], [], "The opponent discards before the owner draws")
        self.assertEqual(s.players["p1"]["zones"]["deck"], ["m4", "m3"])
        self.choose(s, card_ids=["m2"])
        self.assertEqual(s.players["p2"]["zones"]["graveyard"], ["m2"])
        self.assertEqual(s.players["p1"]["zones"]["hand"], ["m4"])
        self.assertEqual(s.players["p1"]["zones"]["deck"], ["m3"])

    def test_oppression_draw_still_happens_when_opponent_cannot_discard(self):
        for immune in (False, True):
            with self.subTest(immune=immune):
                s = self.world()
                self.put(s, "p1", "deck", ["m4"])
                self.put(s, "p2", "hand", ["m2"] if immune else [])
                self.activate_oppression(s)
                with patch.object(s, "rules_hand_is_immune", return_value=immune):
                    s.resolve_rules_top_action()
                self.assertEqual(s.players["p1"]["zones"]["hand"], ["m4"])
                self.assertIsNone(s.rules_engine["pendingChoice"])

    def test_oppression_source_departure_and_duplicate_choice_do_not_cancel_or_redraw(self):
        s = self.world()
        self.put(s, "p1", "deck", ["m4", "m3"])
        self.put(s, "p2", "hand", ["m2"])
        host, _, _ = self.activate_oppression(s)
        s._rules_remove_field_item(host, "p1", "graveyard")
        s.resolve_rules_top_action()
        choice = s.rules_engine["pendingChoice"]
        self.choose(s, card_ids=["m2"])
        before = self.snapshot(s)
        self.assertIsNotNone(s.resolve_rules_choice("p2", choice["id"], card_ids=["m2"])[0])
        self.assertEqual(self.snapshot(s), before)
        self.assertEqual(s.players["p1"]["zones"]["hand"], ["m4"])

    def test_putting_a_manifestation_on_field_is_not_a_play_event(self):
        for name, counter, color in self.CARDS:
            with self.subTest(card=name):
                s = self.world()
                host = self.host(s, name, counter, 2)
                s.card_rules["m2"]["temperaments"] = [color]
                entered = self.field(s, "m2", "put", zone="interzone")
                s.queue_rules_manifestation_entry_watchers(entered, played=False)
                self.assertEqual(host["counters"][counter], 2)

    def test_oppression_invalid_discard_cannot_draw_or_change_the_pending_choice(self):
        s = self.world()
        self.put(s, "p1", "deck", ["m4"])
        self.put(s, "p2", "hand", ["m2"])
        self.activate_oppression(s)
        s.resolve_rules_top_action()
        choice = s.rules_engine["pendingChoice"]
        for player, cards in (("p1", ["m2"]), ("p2", []), ("p2", ["m3"]), ("p2", ["m2", "m2"])):
            with self.subTest(player=player, cards=cards):
                before = self.snapshot(s)
                self.assertIsNotNone(s.resolve_rules_choice(player, choice["id"], card_ids=cards)[0])
                self.assertEqual(self.snapshot(s), before)

    def test_oppression_preserves_kanon_draw_replacement_after_discard(self):
        s = self.world()
        self.put(s, "p1", "deck", ["m4", "m3"])
        self.put(s, "p2", "hand", ["m2"])
        self.field(s, self.cid("Kanon, the Deathdealer"), "kanon", owner="p2")
        self.activate_oppression(s)
        s.resolve_rules_top_action()
        self.assertEqual(s.rules_engine["pendingChoice"]["playerId"], "p2")
        self.choose(s, card_ids=["m2"])
        follow = s.rules_engine["pendingChoice"]
        self.assertIsNotNone(follow, "Kanon's replacement must survive the discard continuation")
        self.assertEqual((follow["kind"], follow["playerId"]), ("draw_replacement", "p1"))
        self.choose(s, card_ids=["m4"])
        self.assertEqual(s.players["p1"]["zones"]["graveyard"], ["m4"])
        self.assertEqual(s.players["p1"]["zones"]["hand"], [])
        self.assertEqual(s.players["p1"]["zones"]["deck"], ["m3"])


if __name__ == "__main__":
    unittest.main()
