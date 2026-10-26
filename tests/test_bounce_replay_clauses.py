"""Selected printed clauses: return to owner, costs, copies and replay locks.

Shipped abilities are used for the cards under audit. Synthetic Manifestations
only provide targets/payments. Some cases isolate resolution from declaration.
"""
import copy
import unittest

import test_semantic_batch_001_150 as fixtures


class BounceReplayClauses(unittest.TestCase):
    cid = staticmethod(fixtures.SemanticBatch001150.cid)
    field = staticmethod(fixtures.SemanticBatch001150.field)
    put = staticmethod(fixtures.SemanticBatch001150.put)
    target = staticmethod(fixtures.SemanticBatch001150.target)
    action = fixtures.SemanticBatch001150.action
    PIGON = "Pigon, the Apprentice"
    CHIFF = "Chiff and Chaff"
    ATAVIC = "Atavic Introspection"
    ABANDON = "Abandon"
    SINGLE = ((PIGON, "pigon-return-support-card"), (CHIFF, "return-opposing-support-card"),
              (ATAVIC, "spend-controls-to-bounce-manifestation"))

    def world(self):
        s = fixtures.SemanticBatch001150.world(self)
        s.rules_engine.update(priorityPlayerId="p1", autoSkipPhases=False)
        s.card_rules["replay-man"] = {"type": "manifestation", "power": 3,
            "temperaments": ["phlegmatic"], "powerCost": "{G}{G}{G}", "supportFromHand": True}
        s.manifestation_ids.add("replay-man")
        return s

    def snapshot(self, s):
        return copy.deepcopy((s.players, s.rules_engine, s.battlefield, s.tokens))

    def resolve(self, s, action):
        s.rules_engine["actionStack"].append(action)
        return s.resolve_rules_top_action()

    def bounce(self, s, name, ability, *, owner="p2", controller="p2", card="replay-man"):
        source = self.field(s, self.cid(name), "host", zone="field")
        item = self.field(s, card, "returned", owner=owner, controller=controller, support=True, power_bonus=2)
        self.resolve(s, self.action(name, source, [self.target(item)], ability_id=ability))
        return source, item

    def play(self, s, player="p2", card="replay-man"):
        s.rules_engine["priorityPlayerId"] = player
        return s.declare_rules_action(player, "Play returned card", kind="play_card",
            source={"cardId": card, "zone": "hand"}, as_support=True)

    def test_single_returns_owner_and_restricts_only_after_resolution(self):
        for name, ability in self.SINGLE:
            with self.subTest(card=name):
                s = self.world()
                source = self.field(s, self.cid(name), "host", zone="field")
                item = self.field(s, "replay-man", "target", owner="p2", support=True)
                action = self.action(name, source, [self.target(item)], ability_id=ability)
                s.rules_engine["actionStack"] = [action]
                self.assertEqual(s.rules_engine["playRestrictions"], [])
                self.assertIn(item, s.battlefield)
                s.resolve_rules_top_action()
                self.assertNotIn(item, s.battlefield)
                self.assertEqual(s.players["p2"]["zones"]["hand"], ["replay-man"])
                self.assertEqual(s.rules_play_restriction_count("p2", "replay-man"), 1)

    def test_foreign_control_returns_to_owner_and_locks_owner_not_controller(self):
        for name, ability in self.SINGLE:
            with self.subTest(card=name):
                s = self.world()
                self.bounce(s, name, ability, owner="p1", controller="p2")
                self.assertEqual(s.players["p1"]["zones"]["hand"], ["replay-man"])
                self.assertEqual(s.players["p2"]["zones"]["hand"], [])
                self.assertEqual(s.rules_play_restriction_count("p1", "replay-man"), 1)
                self.assertEqual(s.rules_play_restriction_count("p2", "replay-man"), 0)

    def test_returned_card_cannot_bypass_lock_through_stack_declaration(self):
        for name, ability in self.SINGLE:
            with self.subTest(card=name):
                s = self.world()
                self.bounce(s, name, ability)
                s.rules_engine["priorityPlayerId"] = "p2"
                before = self.snapshot(s)
                self.assertIsNotNone(self.play(s)[0])
                self.assertEqual(self.snapshot(s), before)

    def test_returned_card_cannot_be_chained_from_hand(self):
        for name, ability in self.SINGLE:
            with self.subTest(card=name):
                s = self.world()
                self.bounce(s, name, ability)
                before = self.snapshot(s)
                self.assertIsNotNone(s.chain_rules_manifestation("p2", "hand", "replay-man")[0])
                self.assertEqual(self.snapshot(s), before)

    def test_another_hand_copy_can_play_once_without_unlocking_returned_copy(self):
        for name, ability in self.SINGLE:
            with self.subTest(card=name):
                s = self.world()
                self.put(s, "p2", "hand", ["replay-man"])
                self.bounce(s, name, ability)
                self.assertIsNone(self.play(s)[0])
                s.resolve_rules_top_action()
                self.assertEqual(s.players["p2"]["zones"]["hand"], ["replay-man"])
                self.assertIsNone(s.rules_engine["pendingChoice"], "Another card entering Support must not retrigger Chiff")
                self.assertIsNotNone(self.play(s)[0])

    def test_locked_hand_card_is_not_reported_as_a_playable_support(self):
        for name, ability in self.SINGLE:
            with self.subTest(card=name):
                s = self.world()
                self.bounce(s, name, ability)
                s.rules_engine["priorityPlayerId"] = "p2"
                self.assertFalse(s.rules_support_from_hand_available("p2", "replay-man"))
                self.assertFalse(s.rules_player_can_act("p2"))
                s.put_zone_card("p2", "hand", "replay-man", "p2")
                self.assertTrue(s.rules_support_from_hand_available("p2", "replay-man"))
                self.assertTrue(s.rules_player_can_act("p2"))

    def test_next_turn_expires_lock_and_play_has_printed_power_without_old_bonus(self):
        for name, ability in self.SINGLE:
            with self.subTest(card=name):
                s = self.world()
                self.bounce(s, name, ability)
                s.phase_tracker["turn"] += 1
                s.prune_rules_play_restrictions()
                self.assertEqual(s.rules_engine["playRestrictions"], [])
                self.assertIsNone(self.play(s)[0])
                s.resolve_rules_top_action()
                item = next(i for i in s.battlefield if i.get("cardId") == "replay-man")
                self.assertEqual(s.rules_manifestation_characteristics(item)["power"], 3)

    def test_source_departure_and_cleanse_do_not_remove_replay_lock(self):
        for name, ability in self.SINGLE:
            with self.subTest(card=name):
                s = self.world()
                source, _ = self.bounce(s, name, ability)
                self.resolve(s, self.action("Cleanse", targets=[self.target(source)]))
                s._rules_remove_field_item(source, "p1", "graveyard")
                self.assertIsNotNone(s.rules_card_play_restriction_error("p2", "replay-man"))

    def test_invalidated_target_does_not_create_a_replay_lock(self):
        for name, ability in self.SINGLE:
            for invalidation in ("missing", "protected"):
                with self.subTest(card=name, invalidation=invalidation):
                    s = self.world()
                    source = self.field(s, self.cid(name), "host", zone="field")
                    item = self.field(s, "replay-man", "target", owner="p2", support=True)
                    action = self.action(name, source, [self.target(item)], ability_id=ability)
                    if invalidation == "missing":
                        s._rules_remove_field_item(item, "p2", "graveyard")
                    else:
                        s.rules_engine["ongoingEffects"].append({"id": "shield", "kind": "protection", "target": self.target(item),
                            "duration": "until_end_of_turn", "startedTurn": 2})
                    self.resolve(s, action)
                    self.assertEqual(s.rules_engine["playRestrictions"], [])
                    self.assertEqual(s.players["p2"]["zones"]["hand"], [])

    def test_restriction_does_not_forbid_discard_activation_from_hand(self):
        s = self.world()
        card = self.cid("Bivalv, the Circumspect")
        self.bounce(s, self.PIGON, self.SINGLE[0][1], card=card)
        target = self.field(s, "m2", "protected", owner="p2")
        s.rules_engine["priorityPlayerId"] = "p2"
        ability = s.card_rules[card]["activatedAbilities"][0]
        error, _ = s.declare_rules_action("p2", "Bivalv", kind="activated_effect",
            source={"cardId": card, "zone": "hand"}, targets=[self.target(target)], ability_id=ability["id"])
        self.assertIsNone(error)
        self.assertIn(card, s.players["p2"]["zones"]["graveyard"])

    def pigon_activation(self, s, target):
        source = self.field(s, self.cid(self.PIGON), "pigon")
        s.add_rules_excess_essence("p1", [{"temperament": "hollow", "amount": 2}])
        error, action = s.declare_rules_action("p1", "Pigon", kind="activated_effect",
            source={"cardId": source["cardId"], "itemId": source["id"], "zone": "battlefield"},
            targets=[self.target(target)], ability_id=self.SINGLE[0][1])
        self.assertIsNone(error)
        return source, action

    def test_pigon_pays_two_and_exhausts_before_opponent_response(self):
        s = self.world()
        item = self.field(s, "replay-man", "target", owner="p2", support=True)
        source, action = self.pigon_activation(s, item)
        self.assertEqual(source["rotation"], 90)
        self.assertEqual(sum(e["amount"] for e in action["cost"]["essenceSpent"]), 2)
        self.assertIn(item, s.battlefield)
        self.assertEqual(s.rules_engine["playRestrictions"], [])
        self.assertEqual(s.rules_engine["priorityPlayerId"], "p2")
        s._rules_remove_field_item(source, "p1", "graveyard")
        s.resolve_rules_top_action()
        self.assertEqual(s.players["p2"]["zones"]["hand"], ["replay-man"])

    def test_pigon_cannot_target_non_support_or_activate_while_exhausted(self):
        for support, rotation in ((False, 0), (True, 90)):
            with self.subTest(support=support, rotation=rotation):
                s = self.world()
                source = self.field(s, self.cid(self.PIGON), "pigon")
                source["rotation"] = rotation
                target = self.field(s, "m2", "target", owner="p2", support=support)
                s.add_rules_excess_essence("p1", [{"temperament": "hollow", "amount": 2}])
                before = self.snapshot(s)
                error, _ = s.declare_rules_action("p1", "Pigon", kind="activated_effect",
                    source={"cardId": source["cardId"], "itemId": source["id"], "zone": "battlefield"},
                    targets=[self.target(target)], ability_id=self.SINGLE[0][1])
                self.assertIsNotNone(error)
                self.assertEqual(self.snapshot(s), before)

    def test_pigon_failed_resolution_does_not_refund_paid_cost(self):
        s = self.world()
        item = self.field(s, "replay-man", "target", owner="p2", support=True)
        source, action = self.pigon_activation(s, item)
        s.battlefield.remove(item)
        tokens = copy.deepcopy(s.tokens)
        s.resolve_rules_top_action()
        self.assertEqual(s.tokens, tokens)
        self.assertEqual(source["rotation"], 90)
        self.assertEqual(sum(e["amount"] for e in action["cost"]["essenceSpent"]), 2)
        self.assertEqual(s.rules_engine["playRestrictions"], [])

    def test_chiff_support_condition_needs_opponent_interzone_entry(self):
        for actor, origin, expected in (("p2", "interzone", True), ("p1", "interzone", False), ("p2", "hand", False)):
            with self.subTest(actor=actor, origin=origin):
                s = self.world()
                s.rules_engine["supportEntries"] = [{"controllerId": actor, "fromZone": origin, "turn": 2}]
                self.assertEqual(s.rules_support_from_hand_available("p1", self.cid(self.CHIFF)), expected)

    def test_chiff_real_support_entry_queues_return_without_moving_target_early(self):
        s = self.world()
        source = self.field(s, self.cid(self.CHIFF), "chiff", support=True)
        target = self.field(s, "replay-man", "opponent", owner="p2", support=True)
        actions = s.queue_rules_support_entry_triggers(source, played=True, from_zone="hand", event_targets=[self.target(target)], defer=True)
        self.assertEqual(len(actions), 1)
        self.assertIn(target, s.battlefield)
        self.resolve(s, actions[0])
        self.assertEqual(s.players["p2"]["zones"]["hand"], ["replay-man"])
        self.assertIn(source, s.battlefield)

    def test_chiff_does_not_trigger_when_another_players_or_own_other_card_enters_support(self):
        for actor in ("p1", "p2"):
            with self.subTest(entrant=actor):
                s = self.world()
                self.field(s, self.cid(self.CHIFF), "chiff", support=True)
                enemy = self.field(s, "m2", "enemy", owner="p2", support=True)
                entered = self.field(s, "m3", "entered", owner=actor, support=True)
                actions = s.queue_rules_support_entry_triggers(entered, played=True, from_zone="interzone",
                    event_targets=[self.target(enemy)], defer=True)
                self.assertEqual(actions, [])
                self.assertIsNone(s.rules_engine["pendingChoice"])

    def test_atavic_spends_exactly_five_counters_before_resolving(self):
        for count, accepted in ((4, False), (6, True)):
            with self.subTest(counters=count):
                s = self.world()
                source = self.field(s, self.cid(self.ATAVIC), "atavic", zone="field")
                source["counters"]["Control"] = count
                target = self.field(s, "m2", "target", owner="p2", zone="interzone")
                before = self.snapshot(s)
                error, _ = s.declare_rules_action("p1", "Atavic", kind="activated_effect",
                    source={"cardId": source["cardId"], "itemId": source["id"], "zone": "battlefield"},
                    targets=[self.target(target)], ability_id=self.SINGLE[2][1])
                self.assertEqual(error is None, accepted)
                if accepted:
                    self.assertEqual(source["counters"]["Control"], 1)
                    self.assertIn(target, s.battlefield)
                    s.resolve_rules_top_action()
                    self.assertEqual(s.players["p2"]["zones"]["hand"], ["m2"])
                else:
                    self.assertEqual(self.snapshot(s), before)

    def abandon(self, s, target="p2"):
        return self.resolve(s, self.action(self.ABANDON, targets=[{"kind": "player", "playerId": target}]))

    def test_abandon_returns_only_target_players_cz_supports_to_each_owner(self):
        s = self.world()
        a = self.field(s, "m2", "own-owned", owner="p1", controller="p2", support=True)
        b = self.field(s, "m3", "enemy-owned", owner="p2", support=True)
        keep = [self.field(s, "m4", "first", owner="p2"), self.field(s, "m2", "iz", owner="p2", zone="interzone", support=True),
                self.field(s, "m3", "mine", owner="p1", support=True)]
        self.abandon(s)
        self.assertNotIn(a, s.battlefield)
        self.assertNotIn(b, s.battlefield)
        self.assertEqual(s.players["p1"]["zones"]["hand"], ["m2"])
        self.assertEqual(s.players["p2"]["zones"]["hand"], ["m3"])
        self.assertTrue(all(i in s.battlefield for i in keep))

    def test_abandon_adamant_only_prevents_opponents_return_and_creates_no_lock(self):
        for target, expected in (("p2", False), ("p1", True)):
            with self.subTest(target=target):
                s = self.world()
                s.card_rules["replay-man"]["adamant"] = True
                item = self.field(s, "replay-man", "adamant", owner=target, support=True)
                self.abandon(s, target)
                self.assertEqual(item not in s.battlefield, expected)
                self.assertEqual(s.rules_play_restriction_count(target, "replay-man"), int(expected))

    def test_abandon_duplicate_returned_copies_all_locked_but_third_copy_available(self):
        s = self.world()
        self.field(s, "replay-man", "a", owner="p2", support=True)
        self.field(s, "replay-man", "b", owner="p2", support=True)
        self.abandon(s)
        self.assertEqual(s.rules_play_restriction_count("p2", "replay-man"), 2)
        self.assertIsNotNone(self.play(s)[0])
        s.put_zone_card("p2", "hand", "replay-man", "p2")
        self.assertIsNone(self.play(s)[0])
        s.resolve_rules_top_action()
        self.assertIsNotNone(self.play(s)[0])

    def test_abandon_empty_supports_does_not_request_choice_or_create_locks(self):
        s = self.world()
        self.field(s, "m2", "first", owner="p2")
        self.abandon(s)
        self.assertEqual(s.rules_engine["playRestrictions"], [])
        self.assertIsNone(s.rules_engine["pendingChoice"])

    def test_abandon_token_return_creates_neither_hand_card_nor_lock(self):
        s = self.world()
        token = s.create_rules_token_copy(None, "p2", generic_power=1, generic_temperament="hollow")
        self.abandon(s)
        self.assertNotIn(token, s.battlefield)
        self.assertEqual(s.players["p2"]["zones"]["hand"], [])
        self.assertEqual(s.rules_engine["playRestrictions"], [])


if __name__ == "__main__":
    unittest.main()
