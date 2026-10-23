"""Observed events must describe a real change, once, after replacements."""
import copy
from unittest.mock import patch
import test_game_state as game_tests


class ObservedEventsAuditTests(game_tests.RealCardRulesCase):
    GUART = "xzb2jwtkunq5tys_en"
    IMGURD = "kae4oy2v7jtkgn2_en"
    KATUN = "kw78e3qfnqw6sms_en"
    BOB = "inner-deserts-134"
    BERTA = "inner-deserts-009"
    HUMILIATE = "pqi88s5ytyfnalf_en"
    INFLATE = "inner-deserts-118"
    MIMER = "pwsjhnw4vpvqgkv_en"
    JAW = "y6g3tex9ypttk8u_en"
    ALL = (GUART, IMGURD, KATUN, BOB, BERTA, HUMILIATE, INFLATE, MIMER, JAW)

    def started(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker["index"] = game_tests.ADVANCED_PHASES.index("confrontation_reaction")
        session.rules_engine.update(readyPlayerIds=["p1", "p2"], firstManifestationComplete=True, priorityPlayerId="p1")
        session.card_rules["m-0"].update(power=3, temperaments=["choleric"])
        session.card_rules["m-1"].update(power=4, temperaments=["vitreous"])
        mine = self.field_item("mine", "p1", "m-0")
        foe = self.field_item("foe", "p2", "m-1")
        session.battlefield = [mine, foe, self.field_item("guart", "p1", self.GUART, "interzone"),
                               self.field_item("imgurd", "p1", self.IMGURD, "interzone")]
        return session, p1, p2, mine, foe

    def action(self, result=None, target="mine", ongoing=None):
        return {"id": "audit", "controllerId": "p1", "source": {"cardId": self.HUMILIATE, "itemId": "mine"},
                "targets": [{"kind": "card", "itemId": target}],
                "ability": {"id": "audit", "result": result, "ongoingEffect": ongoing}}

    def modifier(self, session, value, target="mine"):
        return session.create_rules_ongoing_effects(self.action(target=target, ongoing={
            "kind": "power_modifier", "value": value, "duration": "until_end_of_turn"}))

    def event_kinds(self, session):
        return [event["kind"] for event in session.rules_engine.get("observedEvents") or []]

    def test_no_gain_or_guart_trigger_when_a_maximum_blocks_the_bonus(self):
        session, _, _, _, foe = self.started()
        foe["maximumPower"] = 4
        self.modifier(session, 2, "foe")
        self.assertEqual(session.rules_manifestation_characteristics(foe)["power"], 4)
        self.assertEqual(self.event_kinds(session), [])
        self.assertEqual(session.queue_rules_observed_event_triggers(defer=True), [])

    def test_no_loss_or_imgurd_trigger_when_berta_blocks_the_malus(self):
        session, _, _, mine, _ = self.started()
        session.battlefield.append(self.field_item("berta", "p2", self.BERTA))
        self.modifier(session, -2)
        self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 3)
        self.assertEqual(self.event_kinds(session), [])

    def test_counter_malus_at_a_minimum_does_not_announce_a_loss(self):
        session, _, _, mine, _ = self.started()
        mine["minimumPower"] = 3
        session.apply_rules_action_result(self.action({"kind": "add_power_counter_target", "value": -1}))
        self.assertEqual(self.event_kinds(session), [])

    def test_partial_change_announces_one_event_and_flush_cannot_replay_it(self):
        session, _, _, mine, _ = self.started()
        mine["minimumPower"] = 2
        self.modifier(session, -3)
        self.assertEqual(self.event_kinds(session), ["power_lost"])
        queued = session.queue_rules_observed_event_triggers(defer=True)
        ids = self.trigger_ids(session, queued)
        self.assertEqual(ids.count("imgurd-gains-points-when-power-is-lost"), 1)
        self.assertEqual(ids.count("guart-answers-own-power-loss"), 1)
        self.assertEqual(session.queue_rules_observed_event_triggers(defer=True), [])

    def test_humiliate_announces_its_real_power_loss(self):
        session, _, _, mine, _ = self.started()
        session.apply_rules_action_result(self.action({"kind": "humiliate_target"}))
        self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 2)
        self.assertEqual(self.event_kinds(session).count("power_lost"), 1)

    def test_generic_source_power_counter_is_observed_but_resource_counters_are_not(self):
        session, _, _, mine, _ = self.started()
        for counter in ("Gem", "Quiet"):
            session.apply_rules_action_result(self.action({"kind": "add_counter_source", "counter": counter, "value": 2}))
        self.assertEqual(self.event_kinds(session), [])
        session.apply_rules_action_result(self.action({"kind": "add_counter_source", "counter": "power", "value": 2}))
        self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 5)
        self.assertEqual(self.event_kinds(session), ["power_gained"])

    def test_adjust_target_power_is_observed(self):
        session, _, _, _, _ = self.started()
        session.apply_rules_action_result(self.action({"kind": "adjust_target_power", "value": -1}))
        self.assertEqual(self.event_kinds(session), ["power_lost"])

    def test_fixed_power_increase_and_decrease_are_observed(self):
        for value, kind in ((10, "power_gained"), (2, "power_lost"), (3, None)):
            with self.subTest(value=value):
                session, _, _, _, _ = self.started()
                session.create_rules_ongoing_effects(self.action(ongoing={
                    "kind": "power_set_maximum", "value": value, "duration": "until_end_of_turn"}))
                self.assertEqual(self.event_kinds(session), [kind] if kind else [])

    def test_katun_sees_a_field_exit_replaced_by_suspension(self):
        session, _, _, mine, _ = self.started()
        session.battlefield += [self.field_item("katun", "p1", self.KATUN, "interzone"),
                                self.field_item("bob", "p2", self.BOB, counters={"power": 3})]
        result = session._rules_remove_field_item_by_effect(mine, "p1", "graveyard", reason="destroy")
        self.assertEqual(result["status"], "suspended")
        self.assertEqual(self.event_kinds(session).count("manifestation_left_by_effect"), 1)
        queued = session.queue_rules_observed_event_triggers(defer=True)
        self.assertEqual([a["source"]["itemId"] for a in queued], ["katun"])

    def test_katun_sees_a_limbo_exit_replaced_by_suspension(self):
        session, p1, _, _, _ = self.started()
        session.battlefield += [self.field_item("katun", "p1", self.KATUN, "interzone"),
                                self.field_item("bob", "p2", self.BOB, counters={"power": 3})]
        self.put(p1, "graveyard", ["m-2"])
        error, _, result = session.move_zone_card_by_effect("p1", "graveyard", "p1", "hand", "m-2")
        self.assertIsNone(error)
        self.assertEqual(result["status"], "suspended")
        self.assertEqual(self.event_kinds(session), ["manifestation_left_by_effect"])

    def test_rejected_move_emits_nothing_and_preserves_the_game(self):
        session, _, _, _, _ = self.started()
        before = copy.deepcopy((session.players, session.battlefield, session.rules_engine))
        error, _, _ = session.move_zone_card_by_effect("p1", "hand", "p1", "graveyard", "absent")
        self.assertIsNotNone(error)
        self.assertEqual(before, (session.players, session.battlefield, session.rules_engine))

    def test_destroyed_will_is_not_a_destroyed_manifestation(self):
        session, _, _, _, _ = self.started()
        session.card_rules["will-x"]["type"] = "persistent_will"
        will = self.field_item("will", "p2", "will-x", "field")
        session.battlefield.append(will)
        session._rules_remove_field_item_by_effect(will, "p2", "graveyard", reason="destroy")
        self.assertNotIn("manifestation_destroyed", self.event_kinds(session))

    def test_will_entering_a_vessel_is_not_a_manifestation_entry(self):
        session, _, _, _, _ = self.started()
        will = self.field_item("will", "p2", "will-x", "field")
        session.battlefield.append(will)
        session._rules_remove_field_item(will, "p1", "receptacle")
        self.assertNotIn("manifestation_enters_opponent_vessel", self.event_kinds(session))

    def test_source_sacrifice_enters_limbo_once_without_discard_or_destruction(self):
        session, _, _, mine, _ = self.started()
        session.pay_rules_activation_cost({"itemId": "mine", "controllerId": "p1"}, {"sacrificeSource": True})
        self.assertNotIn(mine, session.battlefield)
        kinds = self.event_kinds(session)
        self.assertEqual(kinds.count("card_entered_limbo"), 1)
        self.assertEqual(kinds.count("manifestation_entered_limbo"), 1)
        self.assertNotIn("cards_discarded", kinds)
        self.assertNotIn("manifestation_destroyed", kinds)

    def test_reordering_inside_limbo_is_not_a_zone_exit(self):
        session, p1, _, _, _ = self.started()
        self.put(p1, "graveyard", ["m-2", "m-3"])
        session.move_zone_card_by_effect("p1", "graveyard", "p1", "graveyard", "m-2", "bottom")
        self.assertEqual(self.event_kinds(session), [])

    def test_grouped_discards_trigger_once_but_limbo_entries_stay_per_card(self):
        session, p1, _, _, _ = self.started()
        self.put(p1, "hand", ["m-2", "m-3"])
        for cid in ("m-2", "m-3"):
            session.move_zone_card_by_effect("p1", "hand", "p1", "graveyard", cid)
        self.assertEqual(self.event_kinds(session).count("manifestation_entered_limbo"), 2)
        session.card_rules["group-watcher"] = {"type": "manifestation", "power": 1, "triggeredAbilities": [{
            "id": "one-or-more", "trigger": {"event": "cards_discarded"}, "result": {"kind": "score_owner", "value": 1}}]}
        session.battlefield.append(self.field_item("group-watcher", "p1", "group-watcher"))
        queued = session.queue_rules_observed_event_triggers(defer=True)
        self.assertEqual(self.trigger_ids(session, queued).count("one-or-more"), 1)
        self.assertEqual(session.queue_rules_observed_event_triggers(defer=True), [])

    def test_expiration_does_not_announce_power_loss_or_gain(self):
        session, _, _, _, _ = self.started()
        self.modifier(session, 1)
        session.queue_rules_observed_event_triggers(defer=True)
        session.phase_tracker["turn"] += 1
        session.prune_rules_ongoing_effects()
        self.assertEqual(self.event_kinds(session), [])

    def test_destruction_replaced_by_suspension_or_exile_only_announces_exit(self):
        for replacement in ("suspend", "exile"):
            with self.subTest(replacement=replacement):
                session, p1, _, mine, _ = self.started()
                if replacement == "suspend":
                    session.battlefield.append(self.field_item("bob", "p2", self.BOB, counters={"power": 3}))
                else:
                    mine["exileIfLeaves"] = True
                session._rules_remove_field_item_by_effect(mine, "p1", "graveyard", reason="destroy")
                self.assertEqual(self.event_kinds(session), ["manifestation_left_by_effect"])
                self.assertNotIn("m-0", p1["zones"]["graveyard"])

    def test_mimer_reactivation_compares_with_previous_copy_not_printed_power(self):
        session, _, _, mine, foe = self.started()
        mine["cardId"] = self.MIMER
        action = self.action(target="foe", ongoing=self.ability(self.MIMER, "copy-first-manifestation")["ongoingEffect"])
        session.create_rules_ongoing_effects(action)
        session.rules_engine["observedEvents"] = []
        session.create_rules_ongoing_effects(action)
        self.assertEqual(self.event_kinds(session), [])
        foe["counters"]["power"] = -1
        session.create_rules_ongoing_effects(action)
        self.assertEqual(self.event_kinds(session), ["power_lost"])

    def test_move_power_counter_observes_each_real_change_once(self):
        session, _, _, mine, _ = self.started()
        mine["counters"]["power"] = 1
        action = self.action({"kind": "move_counter", "counter": "power", "value": 1})
        action["targets"].append({"kind": "card", "itemId": "foe"})
        session.apply_rules_action_result(action)
        self.assertEqual(self.event_kinds(session), ["power_lost", "power_gained"])

    def test_reduce_activation_cost_is_not_power_lost_due_to_a_card_or_effect(self):
        for blocked in (False, True):
            with self.subTest(blocked=blocked):
                session, _, _, mine, _ = self.started()
                if blocked:
                    mine["minimumPower"] = 3
                session.pay_rules_activation_cost({"itemId": "mine", "controllerId": "p1"}, {"reduceSourcePower": 1})
                self.assertEqual(self.event_kinds(session), [])
                self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 3 if blocked else 2)

    def test_dice_power_gain_is_observed_once(self):
        session, _, _, _, _ = self.started()
        with patch("game.effects.dice.random.randint", return_value=2):
            session.apply_rules_action_result(self.action({"kind": "roll_multiple_even_power_odd_discard", "rolls": 3}))
        self.assertEqual(self.event_kinds(session), ["power_gained"])

    def test_power_choice_emits_only_after_a_valid_answer(self):
        session, _, _, _, _ = self.started()
        session.rules_engine["firstManifestationItemIds"] = {"p1": "mine"}
        session.rules_engine["pendingChoice"] = {"id": "choice", "kind": "points_or_weaken_first",
            "playerId": "p1", "options": ["lose_points", "weaken"], "points": 5, "power": 1}
        self.assertIsNotNone(session.resolve_rules_choice("p1", "choice", option="invalid")[0])
        self.assertEqual(self.event_kinds(session), [])
        self.assertIsNone(session.resolve_rules_choice("p1", "choice", option="weaken")[0])
        self.assertEqual(self.event_kinds(session), ["power_lost"])

    def test_cleanse_and_retarget_observe_changes_but_natural_expiry_does_not(self):
        session, _, _, _, _ = self.started()
        jaw = self.field_item("jaw", "p1", self.JAW, "field")
        session.battlefield.append(jaw)
        session.create_rules_ongoing_effects({**self.action(), "source": {"cardId": self.JAW, "itemId": "jaw"},
            "ability": {"id": "jaw", "ongoingEffect": {
                "kind": "power_modifier", "value": -1, "duration": "while_source_and_target_on_field"}}})
        session.rules_engine["observedEvents"] = []
        session.apply_rules_action_result({**self.action({"kind": "retarget_source_effect", "effectKind": "power_modifier"}, target="foe"),
                                          "source": {"cardId": self.JAW, "itemId": "jaw"}})
        self.assertEqual(self.event_kinds(session), ["power_gained", "power_lost"])
        session.rules_engine["observedEvents"] = []
        session.apply_rules_action_result(self.action({"kind": "cleanse_target"}, target="foe"))
        self.assertEqual(self.event_kinds(session), ["power_gained"])

    def test_natural_field_removal_does_not_announce_an_effect_exit(self):
        session, _, _, mine, _ = self.started()
        session._rules_remove_field_item(mine, "p1", "graveyard")
        self.assertNotIn("manifestation_left_by_effect", self.event_kinds(session))

    def test_zone_entry_is_recorded_once_for_destruction_and_ordinary_move(self):
        for reason in ("destroy", "discard", None):
            with self.subTest(reason=reason):
                session, _, _, mine, _ = self.started()
                session._rules_remove_field_item_by_effect(mine, "p1", "graveyard", reason=reason)
                kinds = self.event_kinds(session)
                self.assertEqual(kinds.count("card_entered_limbo"), 1)
                self.assertEqual(kinds.count("manifestation_entered_limbo"), 1)
                self.assertEqual(kinds.count("manifestation_destroyed"), int(reason == "destroy"))
                self.assertEqual(kinds.count("cards_discarded"), int(reason == "discard"))

    def test_token_effect_exit_is_observed_without_a_fake_limbo_entry(self):
        session, p1, _, mine, _ = self.started()
        mine["isCopy"] = True
        session._rules_remove_field_item_by_effect(mine, "p1", "graveyard", reason="destroy")
        self.assertEqual(self.event_kinds(session), ["manifestation_left_by_effect"])
        self.assertNotIn("m-0", p1["zones"]["graveyard"])
