"""Printed oracles for draw requests after a discard or additional cost.

Pray and Martyrize use actual declarations; some Press cases isolate its
triggered effect, with one real Will-play interaction checked separately.
"""
import copy
import unittest
import test_atavic_end_clauses as base


class DiscardDrawClauses(unittest.TestCase):
    world = base.AtavicEndClauses.world
    cid = staticmethod(base.AtavicEndClauses.cid)
    field = staticmethod(base.AtavicEndClauses.field)
    put = staticmethod(base.AtavicEndClauses.put)
    action = base.AtavicEndClauses.action
    snapshot = base.AtavicEndClauses.snapshot
    choose = base.AtavicEndClauses.choose
    PRAY = "Pray the Ether"
    PRESS = "Alchemical Press"
    MARTYRIZE = "Martyrize"
    DISCARDERS = (PRAY, PRESS)

    def setup_discard(self, name, hand=("w2",), deck=("m2", "m3", "m4"), resolve=True):
        s = self.world()
        self.put(s, "p1", "deck", deck)
        host = None
        if name == self.PRAY:
            self.put(s, "p1", "hand", [self.cid(name), *hand])
            error, action = s.declare_rules_action("p1", "Pray", kind="play_card",
                source={"cardId": self.cid(name), "zone": "hand"}, ability_id="discard-one-then-draw-two")
            self.assertIsNone(error)
        else:
            self.put(s, "p1", "hand", hand)
            host = self.field(s, self.cid(name), "press", zone="field")
            host["counters"]["Formula"] = 5
            action = self.action(name, host, ability_id="discard-to-draw-after-will")
            s.rules_engine["actionStack"] = [action]
        if resolve:
            s.resolve_rules_top_action()
        return s, host

    def martyrize(self, s, donor="m3"):
        card = self.cid(self.MARTYRIZE)
        self.put(s, "p1", "hand", [card, donor])
        s.add_rules_excess_essence("p1", [{"temperament": "hollow", "amount": 1}])
        return s.declare_rules_action("p1", "Martyrize", kind="play_card",
            source={"cardId": card, "zone": "hand"}, cost_card_id=donor,
            ability_id="martyrize-exiles-hand-manifestation-to-draw")

    def kanon(self, s, owner="p2"):
        return self.field(s, self.cid("Kanon, the Deathdealer"), "kanon", owner=owner)

    def immune_hands(self, s):
        self.field(s, "inner-deserts-134", "bob", power_bonus=10)
        self.assertTrue(s.rules_hands_are_immune())

    def test_normal_draw_count_and_discard_before_draw(self):
        for name, amount in ((self.PRAY, 2), (self.PRESS, 1)):
            with self.subTest(card=name):
                s, _ = self.setup_discard(name)
                self.assertEqual(s.players["p1"]["zones"]["hand"], ["w2"])
                self.assertEqual(s.players["p1"]["zones"]["deck"], ["m2", "m3", "m4"])
                self.choose(s, card_ids=["w2"])
                self.assertEqual(s.players["p1"]["zones"]["hand"], ["m2", "m3"][:amount])
                self.assertIn("w2", s.players["p1"]["zones"]["graveyard"])

    def test_empty_hand_cannot_pay_discard_and_draws_nothing(self):
        for name in self.DISCARDERS:
            with self.subTest(card=name):
                s, _ = self.setup_discard(name, hand=[])
                self.assertIsNone(s.rules_engine["pendingChoice"])
                self.assertEqual(s.players["p1"]["zones"]["deck"], ["m2", "m3", "m4"])
                self.assertEqual(s.players["p1"]["zones"]["hand"], [])

    def test_draw_lock_is_respected_after_discard(self):
        for name in self.DISCARDERS:
            with self.subTest(card=name):
                s, _ = self.setup_discard(name)
                s.rules_engine["drawLocks"] = [{"playerId": "p1", "turn": 2}]
                self.choose(s, card_ids=["w2"])
                self.assertEqual(s.players["p1"]["zones"]["hand"], [])
                self.assertEqual(s.players["p1"]["zones"]["deck"], ["m2", "m3", "m4"])
                self.assertIn("w2", s.players["p1"]["zones"]["graveyard"])

    def test_kanon_replaces_the_post_discard_draw(self):
        for name, requested in ((self.PRAY, 2), (self.PRESS, 1)):
            with self.subTest(card=name):
                s, _ = self.setup_discard(name)
                self.kanon(s)
                self.choose(s, card_ids=["w2"])
                choice = s.rules_engine["pendingChoice"]
                self.assertIsNotNone(choice)
                self.assertEqual((choice["kind"], choice["playerId"], choice["count"]), ("draw_replacement", "p1", 1))
                self.assertEqual(choice["_cardIds"], ["m2", "m3"][:requested])
                self.choose(s, card_ids=["m2"])
                self.assertEqual(s.players["p1"]["zones"]["hand"], ["m3"] if requested == 2 else [])
                self.assertEqual(s.players["p1"]["zones"]["deck"], ["m4"] if requested == 2 else ["m3", "m4"])

    def test_kanon_does_not_replace_its_controller_own_draws(self):
        for name, amount in ((self.PRAY, 2), (self.PRESS, 1)):
            with self.subTest(card=name):
                s, _ = self.setup_discard(name)
                self.kanon(s, "p1")
                self.choose(s, card_ids=["w2"])
                self.assertEqual(len(s.players["p1"]["zones"]["hand"]), amount)
                self.assertIsNone(s.rules_engine["pendingChoice"])

    def test_recovery_draw_fixture_ignores_nonrecovery_lock_and_kanon(self):
        from session import ADVANCED_PHASES
        for name, amount in ((self.PRAY, 2), (self.PRESS, 1)):
            with self.subTest(card=name):
                s, _ = self.setup_discard(name)
                self.kanon(s)
                s.rules_engine["drawLocks"] = [{"playerId": "p1", "turn": 2}]
                # Explicit timing fixture, not a claim that these effects move phases.
                s.phase_tracker["index"] = ADVANCED_PHASES.index("recovery_draw")
                self.choose(s, card_ids=["w2"])
                self.assertEqual(len(s.players["p1"]["zones"]["hand"]), amount)
                self.assertIsNone(s.rules_engine["pendingChoice"])

    def test_martyrize_pays_reveal_exile_before_responses_then_draws_base_power(self):
        s = self.world()
        self.put(s, "p1", "deck", ["m2", "m4", "w2", "pw3"])
        error, action = self.martyrize(s)
        self.assertIsNone(error)
        self.assertEqual(action["cost"]["revealedCard"]["power"], 3)
        self.assertEqual(s.players["p1"]["zones"]["exile"], ["m3"])
        self.assertEqual(s.rules_engine["priorityPlayerId"], "p2")
        self.assertEqual(s.players["p1"]["zones"]["hand"], [])
        result = s.resolve_rules_top_action()["action"]["effectResult"]
        self.assertEqual(result["drawn"], ["m2", "m4", "w2"])
        self.assertEqual(s.players["p1"]["zones"]["deck"], ["pw3"])
        self.assertCountEqual(s.players["p1"]["zones"]["exile"], ["m3", self.cid(self.MARTYRIZE)])

    def test_martyrize_respects_draw_lock_without_refunding_cost(self):
        s = self.world()
        self.put(s, "p1", "deck", ["m2", "m4", "w2"])
        self.martyrize(s)
        s.rules_engine["drawLocks"] = [{"playerId": "p1", "turn": 2}]
        s.resolve_rules_top_action()
        self.assertEqual(s.players["p1"]["zones"]["hand"], [])
        self.assertEqual(s.players["p1"]["zones"]["deck"], ["m2", "m4", "w2"])
        self.assertIn("m3", s.players["p1"]["zones"]["exile"])

    def test_martyrize_kanon_keeps_paid_cost_and_replaces_three_draws(self):
        s = self.world()
        self.put(s, "p1", "deck", ["m2", "m4", "w2", "pw3"])
        self.kanon(s)
        self.martyrize(s)
        s.resolve_rules_top_action()
        choice = s.rules_engine["pendingChoice"]
        self.assertIsNotNone(choice)
        self.assertEqual((choice["kind"], choice["count"]), ("draw_replacement", 2))
        self.assertCountEqual(s.players["p1"]["zones"]["exile"], ["m3", self.cid(self.MARTYRIZE)])
        self.choose(s, card_ids=["m2", "m4"])
        self.assertEqual(s.players["p1"]["zones"]["hand"], ["w2"])
        self.assertEqual(s.players["p1"]["zones"]["deck"], ["pw3"])

    def test_martyrize_invalid_additional_card_is_rejected_atomically(self):
        s = self.world()
        self.put(s, "p1", "hand", [self.cid(self.MARTYRIZE), "w2"])
        s.add_rules_excess_essence("p1", [{"temperament": "hollow", "amount": 1}])
        before = self.snapshot(s)
        error, _ = s.declare_rules_action("p1", "Martyrize", kind="play_card",
            source={"cardId": self.cid(self.MARTYRIZE), "zone": "hand"}, cost_card_id="w2",
            ability_id="martyrize-exiles-hand-manifestation-to-draw")
        self.assertIsNotNone(error)
        self.assertEqual(self.snapshot(s), before)

    def press_trigger(self, s, host):
        return s.queue_rules_triggers(host["cardId"], "p1", "will_played", zone="field",
            item_id=host["id"], event_card_id=self.cid(self.PRAY), event_controller_id="p1", controller_id="p1", defer=True)

    def test_press_can_decline_without_discarding_or_drawing(self):
        s, host = self.setup_discard(self.PRESS, resolve=False)
        s.rules_engine["actionStack"] = []
        s.queue_rules_simultaneous_actions(self.press_trigger(s, host))
        zones = copy.deepcopy(s.players)
        self.choose(s, option="decline")
        self.assertEqual(s.players, zones)
        self.assertIsNone(s.rules_engine["pendingChoice"])

    def test_press_empty_hand_does_not_offer_a_pointless_trigger(self):
        s, host = self.setup_discard(self.PRESS, hand=[], resolve=False)
        s.rules_engine["actionStack"] = []
        s.queue_rules_simultaneous_actions(self.press_trigger(s, host))
        self.assertIsNone(s.rules_engine["pendingChoice"])

    def test_press_immune_hand_does_not_offer_an_unpayable_trigger(self):
        s, host = self.setup_discard(self.PRESS, resolve=False)
        s.rules_engine["actionStack"] = []
        self.immune_hands(s)
        s.queue_rules_simultaneous_actions(self.press_trigger(s, host))
        self.assertIsNone(s.rules_engine["pendingChoice"])

    def test_press_late_hand_immunity_does_not_open_an_impossible_choice(self):
        s, _ = self.setup_discard(self.PRESS, resolve=False)
        self.immune_hands(s)
        s.resolve_rules_top_action()
        self.assertIsNone(s.rules_engine["pendingChoice"])
        self.assertEqual(s.players["p1"]["zones"]["hand"], ["w2"])

    def test_press_late_empty_hand_does_not_open_an_impossible_choice(self):
        s, _ = self.setup_discard(self.PRESS, resolve=False)
        self.put(s, "p1", "hand", [])
        s.resolve_rules_top_action()
        self.assertIsNone(s.rules_engine["pendingChoice"])

    def test_press_source_departure_and_duplicate_choice_draw_only_once(self):
        s, host = self.setup_discard(self.PRESS)
        choice = s.rules_engine["pendingChoice"]
        s._rules_remove_field_item(host, "p1", "graveyard")
        self.choose(s, card_ids=["w2"])
        before = self.snapshot(s)
        self.assertIsNotNone(s.resolve_rules_choice("p1", choice["id"], card_ids=["w2"])[0])
        self.assertEqual(self.snapshot(s), before)
        self.assertEqual(s.players["p1"]["zones"]["hand"], ["m2"])

    def test_invalid_discard_is_atomic_and_does_not_draw(self):
        for name in self.DISCARDERS:
            for actor, cards in (("p2", ["w2"]), ("p1", []), ("p1", ["m4"]), ("p1", ["w2", "w2"])):
                with self.subTest(card=name, actor=actor, cards=cards):
                    s, _ = self.setup_discard(name)
                    before = self.snapshot(s)
                    choice = s.rules_engine["pendingChoice"]
                    self.assertIsNotNone(s.resolve_rules_choice(actor, choice["id"], card_ids=cards)[0])
                    self.assertEqual(self.snapshot(s), before)

    def test_multi_card_draw_is_one_denblew_event(self):
        for name in self.DISCARDERS:
            with self.subTest(card=name):
                s, _ = self.setup_discard(name)
                denblew = self.field(s, self.cid("Denblew, the Puritan"), "denblew", owner="p2")
                self.choose(s, card_ids=["w2"])
                queued = s.queue_rules_observed_event_triggers(defer=True)
                self.assertEqual(len([a for a in queued if (a.get("source") or {}).get("itemId") == denblew["id"]]), 1)

    def test_press_then_pray_each_draws_after_its_own_discard(self):
        s = self.world()
        host = self.field(s, self.cid(self.PRESS), "press", zone="field")
        self.put(s, "p1", "hand", [self.cid(self.PRAY), "w2"])
        self.put(s, "p1", "deck", ["m2", "m3", "m4"])
        error, action = s.declare_rules_action("p1", "Pray", kind="play_card",
            source={"cardId": self.cid(self.PRAY), "zone": "hand"}, ability_id="discard-one-then-draw-two")
        self.assertIsNone(error)
        # The server logs declarations and then queues their paid/play events.
        s.queue_rules_tribute_triggers([], "p1", simultaneous_action_id=action["id"])
        self.assertEqual(s.rules_engine["pendingChoice"]["kind"], "optional_stack_action")
        self.choose(s, option="accept")
        self.assertEqual(s.rules_engine["pendingChoice"]["kind"], "simultaneous_stack_order")
        group = s.rules_engine["pendingChoice"]["_group"]
        self.choose(s, card_ids=[action["id"], *[a["id"] for a in group if a["id"] != action["id"]]])
        self.assertEqual(len(s.rules_engine["actionStack"]), 2)
        s.resolve_rules_top_action()
        self.choose(s, card_ids=["w2"])
        self.assertEqual(s.players["p1"]["zones"]["hand"], ["m2"])
        s.resolve_rules_top_action()
        self.choose(s, card_ids=["m2"])
        self.assertEqual(s.players["p1"]["zones"]["hand"], ["m3", "m4"])

    def test_other_players_draw_lock_does_not_block_own_draw(self):
        for name, amount in ((self.PRAY, 2), (self.PRESS, 1)):
            with self.subTest(card=name):
                s, _ = self.setup_discard(name)
                s.rules_engine["drawLocks"] = [{"playerId": "p2", "turn": 2}]
                self.choose(s, card_ids=["w2"])
                self.assertEqual(len(s.players["p1"]["zones"]["hand"]), amount)

    def test_draw_lock_prevents_kanon_offering_a_replacement(self):
        for name in (*self.DISCARDERS, self.MARTYRIZE):
            with self.subTest(card=name):
                if name == self.MARTYRIZE:
                    s = self.world()
                    self.put(s, "p1", "deck", ["m2", "m4", "w2"])
                    self.martyrize(s)
                else:
                    s, _ = self.setup_discard(name)
                self.kanon(s)
                s.rules_engine["drawLocks"] = [{"playerId": "p1", "turn": 2}]
                if name == self.MARTYRIZE:
                    s.resolve_rules_top_action()
                else:
                    self.choose(s, card_ids=["w2"])
                self.assertIsNone(s.rules_engine["pendingChoice"])
                self.assertEqual(s.players["p1"]["zones"]["hand"], [])

    def test_press_legacy_accept_rechecks_discard_availability(self):
        for unavailable in ("empty", "immune"):
            with self.subTest(unavailable=unavailable):
                s, _ = self.setup_discard(self.PRESS, resolve=False)
                s.rules_engine["actionStack"][-1]["optionalAccepted"] = False
                s.resolve_rules_top_action()
                self.assertEqual(s.rules_engine["pendingChoice"]["kind"], "optional_discard_draw")
                if unavailable == "empty":
                    self.put(s, "p1", "hand", [])
                else:
                    self.immune_hands(s)
                deck = list(s.players["p1"]["zones"]["deck"])
                self.choose(s, option="accept")
                self.assertIsNone(s.rules_engine["pendingChoice"])
                self.assertEqual(s.players["p1"]["zones"]["deck"], deck)


if __name__ == "__main__":
    unittest.main()
