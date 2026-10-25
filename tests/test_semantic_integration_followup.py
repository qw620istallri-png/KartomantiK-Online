"""Creator rulings and cross-system regressions from the independent text review."""
import copy
import unittest

import test_semantic_batch_001_150 as fixtures

main = fixtures.main
ADVANCED_PHASES = fixtures.ADVANCED_PHASES


class SemanticIntegrationFollowup(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.SemanticBatch001150()
        self.s = self.f.world()

    def field(self, name, **kwargs):
        return self.f.field(self.s, self.f.cid(name), **kwargs)

    def phase(self, phase):
        self.s.phase_tracker["index"] = ADVANCED_PHASES.index(phase)

    def test_denblew_one_bonus_per_distinct_draw_action_including_same_flush(self):
        source = self.field("Denblew, the Puritan")
        self.f.put(self.s, "p2", "deck", ["m2", "m3", "m4"])
        before = self.s.rules_manifestation_characteristics(source)["power"]
        self.s.draw_rules_cards("p2", 1)
        self.s.draw_rules_cards("p2", 2)
        actions = self.s.queue_rules_observed_event_triggers(defer=True)
        actions = [a for a in actions if a["source"].get("itemId") == source["id"]]
        self.assertEqual(len(actions), 2)
        for action in actions:
            self.s.apply_rules_action_result(action)
            self.s.create_rules_ongoing_effects(action)
        self.assertEqual(self.s.rules_manifestation_characteristics(source)["power"], before + 2)

    def test_denblew_does_not_trigger_in_recovery_or_on_empty_draw(self):
        self.field("Denblew, the Puritan")
        self.f.put(self.s, "p2", "deck", ["m2", "m3"])
        self.phase("recovery_draw")
        self.s.draw_rules_cards("p2", 2)
        self.phase("confrontation_reaction")
        self.s.draw_rules_cards("p2", 1)
        self.assertEqual(self.s.queue_rules_observed_event_triggers(defer=True), [])

    def test_balance_tie_has_no_redirection_for_gain_or_loss(self):
        for delta in (10, -10):
            with self.subTest(delta=delta):
                self.s.players["p1"]["score"] = self.s.players["p2"]["score"] = 50
                self.s.battlefield = []
                self.field("Balance of the Spirit", zone="field")
                self.s.adjust_rules_score("p1", delta)
                self.assertEqual(self.s.players["p1"]["score"], 50 + delta)
                self.assertEqual(self.s.players["p2"]["score"], 50)

    def test_jesterina_chains_from_deck_without_manifestation_discard(self):
        source = self.field("Jesterina, the Decadent")
        self.f.put(self.s, "p2", "deck", ["w2", "pw3", "m4"])
        action = self.f.action("Jesterina, the Decadent", source,
                               [{"kind": "player", "playerId": "p2"}])
        result = self.s.apply_rules_action_result(action)
        self.assertEqual(result["discarded"], ["w2", "pw3"])
        chained = next(i for i in self.s.battlefield if i["cardId"] == "m4")
        self.assertEqual((chained["ownerId"], chained["controllerId"]), ("p2", "p1"))
        self.assertNotIn("m4", self.s.players["p2"]["zones"]["graveyard"])
        self.assertFalse(any(e.get("cardId") == "m4" for e in self.s.rules_engine.get("recentLimboEntries", [])))

    def test_lunar_failure_applies_only_to_player_without_a_candidate(self):
        host = self.field("Lunar Liturgy", zone="field")
        self.f.field(self.s, "m2", item="payment", zone="interzone")
        action = self.f.action("Lunar Liturgy", host)
        self.s.apply_rules_action_result(action)
        choice = self.s.rules_engine["pendingChoice"]
        error, _ = self.s.resolve_rules_choice("p1", choice["id"], option="0")
        self.assertIsNone(error)
        self.assertEqual(self.s.rules_engine["skipEndPhaseTurns"], {"p2": 2})

    def test_lunar_controller_failure_destroys_liturgy_and_only_skips_controller(self):
        host = self.field("Lunar Liturgy", zone="field")
        result = self.s.apply_rules_action_result(self.f.action("Lunar Liturgy", host))
        self.assertEqual(result["status"], "destroyed")
        self.assertEqual(self.s.rules_engine["skipEndPhaseTurns"], {"p1": 2})
        self.assertIsNone(self.s.find_battlefield_item(host["id"]))

    def test_skipped_player_has_no_end_actions_but_opponent_keeps_them(self):
        self.phase("end_actions")
        self.s.rules_engine["skipEndPhaseTurns"] = {"p1": 2}
        for pid in ("p1", "p2"):
            self.f.put(self.s, pid, "hand", ["pw3", "m4"])
            self.s.rules_engine["priorityPlayerId"] = pid
            error, _ = self.s.declare_rules_action(pid, "Will", kind="play_card",
                source={"cardId": "pw3", "zone": "hand"}, payment_card_ids=["m4"])
            if pid == "p1":
                self.assertIn("skip", error)
                self.assertEqual(self.s.players[pid]["zones"]["hand"], ["pw3", "m4"])
            else:
                self.assertIsNone(error)

    def test_skipped_end_triggers_are_suppressed_without_blanking_other_effects(self):
        self.phase("end_triggers")
        self.s.card_rules["end-test"] = {"type": "persistent_will", "triggeredAbilities": [{
            "id": "score-at-end", "trigger": {"event": "end_of_turn"},
            "result": {"kind": "score_owner", "value": 5}}]}
        for pid in ("p1", "p2"):
            self.f.field(self.s, "end-test", item=pid, owner=pid, zone="field")
        self.s.rules_engine["skipEndPhaseTurns"] = {"p1": 2}
        actions = self.s.build_rules_end_turn_field_triggers()
        self.assertEqual([a["controllerId"] for a in actions], ["p2"])
        self.s.phase_tracker["turn"] = 3
        self.assertEqual(len(self.s.build_rules_end_turn_field_triggers()), 2)

    def test_rally_can_pay_21_extra_essences_and_rejects_missing_resources_atomically(self):
        cid = self.f.cid("Rally")
        self.f.put(self.s, "p1", "hand", [cid])
        self.s.add_rules_excess_essence("p1", [{"temperament": "transcendent", "amount": 50}])
        self.s.rules_engine["priorityPlayerId"] = "p1"
        before = copy.deepcopy((self.s.tokens, self.s.players["p1"]["zones"]))
        error, _ = self.s.declare_rules_action("p1", "Rally", kind="play_card",
            source={"cardId": cid, "zone": "hand"}, extra_essence_count=51, ability_id="rally-extra-essence-tokens")
        self.assertIsNotNone(error)
        self.assertEqual((self.s.tokens, self.s.players["p1"]["zones"]), before)
        error, action = self.s.declare_rules_action("p1", "Rally", kind="play_card",
            source={"cardId": cid, "zone": "hand"}, extra_essence_count=21, ability_id="rally-extra-essence-tokens")
        self.assertIsNone(error)
        self.assertEqual(action["cost"]["optionalExtraEssenceSpent"], 21)
        self.s.resolve_rules_top_action()
        self.assertEqual(len([i for i in self.s.battlefield if i.get("isTokenCard")]), 21)

    def test_splendor_pending_counter_entry_can_resolve_before_zero_counter_check(self):
        source = self.field("Temperamental Splendor", zone="field")
        actions = self.s.queue_rules_battlefield_entry_triggers(source["cardId"], "p1", source["id"], True, defer=True)
        self.s.resolve_rules_state_actions(pending_triggers=actions)
        self.assertIsNotNone(self.s.find_battlefield_item(source["id"]))
        self.s.apply_rules_action_result(actions[0])
        self.s.resolve_rules_state_actions()
        self.assertEqual(source["counters"]["Gem"], 2)
        self.assertIsNotNone(self.s.find_battlefield_item(source["id"]))

    def test_outcast_owner_can_accept_or_refuse_after_seeing_the_declared_target(self):
        for accept in (True, False):
            with self.subTest(accept=accept):
                s = self.f.world()
                outcast = self.f.field(s, self.f.cid("Wandering Outcast"), item="outcast", zone="interzone")
                target = self.f.field(s, "m3", item="target", support=True)
                weaken = self.f.cid("Weaken")
                self.f.put(s, "p2", "hand", [weaken])
                s.add_rules_excess_essence("p2", [{"temperament": "transcendent", "amount": 3}])
                s.rules_engine["priorityPlayerId"] = "p2"
                original = copy.deepcopy((s.players, s.battlefield, s.tokens))
                error, proposed = s.declare_rules_action("p2", "Weaken", kind="play_card",
                    source={"cardId": weaken, "zone": "hand"}, targets=[self.f.target(target)],
                    ability_id=main.CARD_ABILITIES[weaken][0]["id"])
                self.assertIsNone(error)
                self.assertEqual(proposed["status"], "choice_required")
                self.assertEqual((s.players, s.battlefield, s.tokens), original)
                choice = s.rules_engine["pendingChoice"]
                self.assertEqual((choice["playerId"], choice["purpose"], choice["incomingCardId"], choice["relatedCardId"]),
                                 ("p1", "outcast_swap", weaken, "m3"))
                self.assertIsNotNone(s.resolve_rules_choice("p2", choice["id"], option="yes")[0])
                error, _ = s.resolve_rules_choice("p1", choice["id"], option="yes" if accept else "no")
                self.assertIsNone(error)
                self.assertIsNone(s.rules_engine["pendingChoice"])
                self.assertEqual(len(s.rules_engine["actionStack"]), 1)
                action = s.rules_engine["actionStack"][0]
                self.assertEqual(action["targets"][0]["itemId"], "outcast" if accept else "target")
                self.assertEqual(s.rules_field_zone(outcast), "confrontation" if accept else "interzone")
                self.assertEqual(s.rules_field_zone(target), "interzone" if accept else "confrontation")

    def test_outcast_disabled_preference_keeps_original_target_without_prompt(self):
        outcast = self.field("Wandering Outcast", item="outcast", zone="interzone")
        outcast["outcastOff"] = True
        target = self.f.field(self.s, "m3", item="target")
        weaken = self.f.cid("Weaken")
        self.f.put(self.s, "p2", "hand", [weaken])
        self.s.add_rules_excess_essence("p2", [{"temperament": "transcendent", "amount": 3}])
        self.s.rules_engine["priorityPlayerId"] = "p2"
        error, action = self.s.declare_rules_action("p2", "Weaken", kind="play_card",
            source={"cardId": weaken, "zone": "hand"}, targets=[self.f.target(target)],
            ability_id=main.CARD_ABILITIES[weaken][0]["id"])
        self.assertIsNone(error)
        self.assertIsNone(self.s.rules_engine["pendingChoice"])
        self.assertEqual(action["targets"][0]["itemId"], "target")

    def test_match_reset_clears_jurat_registration_and_per_player_phase_skips(self):
        self.s.rules_engine["turnTributeReturns"] = [{"turn": 1, "playerId": "p1", "sourceCardId": "jurat"}]
        self.s.rules_engine["skipEndPhaseTurns"] = {"p1": 1}
        self.s.rules_engine["supportLocks"] = [{"turn": 1, "playerId": "p1"}]
        self.s.rules_engine["tributeLog"] = [{"turn": 1, "playerId": "p1", "ownerId": "p1", "cardId": "m3"}]
        self.s.rules_engine["drawnOutsideRecovery"] = {"p1": {"turn": 1, "cardIds": ["m3"]}}
        self.s.reset_phase_tracker()
        self.assertFalse(self.s.rules_support_entry_locked("p1"))
        self.assertEqual(self.s.rules_engine["tributeLog"], [])
        self.assertEqual(self.s.rules_engine["drawnOutsideRecovery"], {})
        self.s.rules_engine["tributeLog"] = [{"turn": 1, "playerId": "p1", "ownerId": "p1", "cardId": "m2"}]
        self.f.put(self.s, "p1", "graveyard", ["m2"])
        self.assertEqual(self.s.queue_rules_end_turn_memory_triggers(defer=True), [])
        self.assertFalse(self.s.rules_player_skips_end_phase("p1"))

    def test_trim_prevents_color_support_float_persist_and_power_ignore_modifiers(self):
        item = self.f.field(self.s, "m3")
        self.s.apply_rules_action_result({"id": "trim", "controllerId": "p1", "targets": [],
            "source": {}, "ability": {"result": {"kind": "set_field_power", "mode": "base"}}})
        self.s.set_rules_item_temperament(item, "hollow", {"source": {}, "ability": {"id": "color"}})
        self.assertNotIn("temperamentOverride", item)
        for kind in ("grant_support", "grant_float", "remove_float", "grant_persist", "power_ignored", "immune"):
            with self.subTest(kind=kind):
                effects = self.s.create_rules_ongoing_effects({"id": kind, "controllerId": "p1",
                    "source": {}, "targets": [self.f.target(item)],
                    "ability": {"id": kind, "ongoingEffect": {"kind": kind, "duration": "while_target_on_field"}}})
                self.assertEqual(effects, [])


if __name__ == "__main__":
    unittest.main()
