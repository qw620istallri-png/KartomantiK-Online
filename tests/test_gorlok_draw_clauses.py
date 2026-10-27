"""Gorlok's printed draw event, instance lifetime and exact outcomes.

Draw stimuli use the shared request path; queued shipped triggers resolve
through the Stack. No VFX, scheduler or physical-device certification.
"""
import json
import unittest
import test_kanon_event_clauses as base


class GorlokDrawClauses(unittest.TestCase):
    world = base.KanonEventClauses.world
    cid = staticmethod(base.KanonEventClauses.cid)
    field = staticmethod(base.KanonEventClauses.field)
    put = staticmethod(base.KanonEventClauses.put)
    snapshot = base.KanonEventClauses.snapshot
    choose = base.KanonEventClauses.choose
    NAME = base.KanonEventClauses.GORLOK

    def setup(self, deck=("m2", "m3", "m4", "w2"), hand=()):
        s = self.world()
        host = self.field(s, self.cid(self.NAME), "gorlok", zone="interzone")
        self.put(s, "p2", "deck", deck)
        self.put(s, "p2", "hand", hand)
        return s, host

    def draw(self, s, count, player="p2"):
        s.request_rules_draw(player, count)
        return [a for a in s.queue_rules_observed_event_triggers(defer=True)
                if (a.get("source") or {}).get("cardId") == self.cid(self.NAME)]

    def resolve(self, s, action):
        s.rules_engine["actionStack"].append(action)
        return s.resolve_rules_top_action()["action"]["effectResult"]

    def shown(self, s):
        self.assertIsNotNone(s.rules_engine["pendingChoice"])
        self.assertEqual(s.rules_engine["pendingChoice"]["purpose"], "gorlok")
        return s.rules_engine["pendingChoice"]["cardIds"]

    def immune(self, s):
        self.field(s, "inner-deserts-134", "bob", power_bonus=8)
        self.assertTrue(s.rules_hands_are_immune())

    def test_single_draw_shows_exact_cards_exiles_one_and_loses_shown_count(self):
        s, host = self.setup(hand=["pw3"])
        before = s.rules_manifestation_characteristics(host)["power"]
        action, = self.draw(s, 3)
        self.resolve(s, action)
        self.assertEqual(self.shown(s), ["m2", "m3", "m4"])
        result = self.choose(s, option="1")
        self.assertEqual((result["cardId"], result["shown"]), ("m3", 3))
        self.assertEqual(s.players["p2"]["zones"]["hand"], ["pw3", "m2", "m4"])
        self.assertEqual(s.players["p2"]["zones"]["exile"], ["m3"])
        self.assertEqual(s.rules_manifestation_characteristics(host)["power"], before - 3)

    def test_two_draw_events_same_flush_keep_separate_lifo_choices(self):
        s, host = self.setup()
        before = s.rules_manifestation_characteristics(host)["power"]
        s.request_rules_draw("p2", 1)
        s.request_rules_draw("p2", 2)
        actions = s.queue_rules_observed_event_triggers(defer=True)
        self.assertEqual(len(actions), 2)
        s.rules_engine["actionStack"] = actions
        s.resolve_rules_top_action()
        self.assertEqual(self.shown(s), ["m3", "m4"])
        self.choose(s, option="0")
        s.resolve_rules_top_action()
        self.assertEqual(self.shown(s), ["m2"])
        self.choose(s, option="0")
        self.assertEqual(s.players["p2"]["zones"]["hand"], ["m4"])
        self.assertEqual(s.rules_manifestation_characteristics(host)["power"], before - 3)

    def test_new_draw_while_first_effect_waits_does_not_change_first_snapshot(self):
        s, _ = self.setup()
        first, = self.draw(s, 1)
        second, = self.draw(s, 2)
        self.resolve(s, first)
        self.assertEqual(self.shown(s), ["m2"])
        self.choose(s, option="0")
        self.resolve(s, second)
        self.assertEqual(self.shown(s), ["m3", "m4"])

    def test_draw_before_gorlok_enters_is_not_part_of_its_later_event(self):
        s, host = self.setup()
        s.battlefield.remove(host)
        self.assertEqual(self.draw(s, 1), [])
        s.battlefield.append(host)
        action, = self.draw(s, 1)
        self.resolve(s, action)
        self.assertEqual(self.shown(s), ["m3"])

    def test_two_gorloks_each_keep_the_same_event_and_remaining_cards(self):
        s, host = self.setup()
        other = self.field(s, self.cid(self.NAME), "gorlok-2", zone="interzone")
        before = s.rules_manifestation_characteristics(host)["power"]
        actions = self.draw(s, 2)
        self.assertEqual(len(actions), 2)
        self.resolve(s, actions[0])
        self.assertEqual(self.shown(s), ["m2", "m3"])
        self.choose(s, option="0")
        self.resolve(s, actions[1])
        self.assertEqual(self.shown(s), ["m3"])
        self.choose(s, option="0")
        self.assertEqual(s.rules_manifestation_characteristics(host)["power"], before - 2)
        self.assertEqual(s.rules_manifestation_characteristics(other)["power"], before - 1)

    def test_source_departure_does_not_cancel_exile_of_drawn_cards(self):
        s, host = self.setup()
        action, = self.draw(s, 2)
        s._rules_remove_field_item(host, "p1", "graveyard")
        self.resolve(s, action)
        self.assertEqual(self.shown(s), ["m2", "m3"])
        self.choose(s, option="1")
        self.assertEqual(s.players["p2"]["zones"]["exile"], ["m3"])

    def test_source_return_does_not_apply_old_power_loss_to_new_instance(self):
        s, host = self.setup()
        action, = self.draw(s, 2)
        s._rules_remove_field_item(host, "p1", "graveyard")
        s.take_zone_card("p1", "graveyard", self.cid(self.NAME))
        new_host = self.field(s, self.cid(self.NAME), "returned-gorlok", zone="interzone")
        before = s.rules_manifestation_characteristics(new_host)["power"]
        self.resolve(s, action)
        self.choose(s, option="0")
        self.assertEqual(s.players["p2"]["zones"]["exile"], ["m2"])
        self.assertEqual(s.rules_manifestation_characteristics(new_host)["power"], before)

    def test_source_controller_change_keeps_original_effect_controller(self):
        s, host = self.setup()
        action, = self.draw(s, 2)
        host["controllerId"] = "p2"
        self.resolve(s, action)
        self.assertEqual(s.rules_engine["pendingChoice"]["playerId"], "p1")
        self.assertEqual(s.rules_engine["pendingChoice"]["targetPlayerId"], "p2")
        self.choose(s, option="0")
        self.assertEqual(s.players["p2"]["zones"]["exile"], ["m2"])

    def test_one_drawn_card_leaves_before_resolution_only_remaining_is_shown(self):
        s, host = self.setup()
        before = s.rules_manifestation_characteristics(host)["power"]
        action, = self.draw(s, 2)
        s.move_zone_card("p2", "hand", "p2", "graveyard", "m2")
        self.resolve(s, action)
        self.assertEqual(self.shown(s), ["m3"])
        self.choose(s, option="0")
        self.assertEqual(s.rules_manifestation_characteristics(host)["power"], before - 1)

    def test_all_drawn_cards_leave_effect_resolves_without_choice_or_power_loss(self):
        s, host = self.setup()
        before = s.rules_manifestation_characteristics(host)["power"]
        action, = self.draw(s, 1)
        s.move_zone_card("p2", "hand", "p2", "graveyard", "m2")
        self.resolve(s, action)
        self.assertIsNone(s.rules_engine["pendingChoice"])
        self.assertEqual(s.rules_manifestation_characteristics(host)["power"], before)

    def test_departure_and_return_to_hand_invalidates_original_drawn_instance(self):
        s, _ = self.setup()
        action, = self.draw(s, 2)
        s.move_zone_card("p2", "hand", "p2", "graveyard", "m2")
        s.move_zone_card("p2", "graveyard", "p2", "hand", "m2", "bottom")
        self.resolve(s, action)
        self.assertEqual(self.shown(s), ["m3"])

    def test_old_identical_hand_copy_leaves_but_drawn_copy_remains_valid(self):
        s, _ = self.setup(hand=["m2"])
        action, = self.draw(s, 2)
        s.move_zone_card("p2", "hand", "p2", "graveyard", "m2")
        self.resolve(s, action)
        self.assertEqual(self.shown(s), ["m2", "m3"])

    def test_identical_drawn_copies_count_twice_but_only_one_is_exiled(self):
        s, host = self.setup(deck=["m2", "m2"])
        before = s.rules_manifestation_characteristics(host)["power"]
        action, = self.draw(s, 2)
        self.resolve(s, action)
        self.assertEqual(self.shown(s), ["m2", "m2"])
        self.choose(s, option="1")
        self.assertEqual(s.players["p2"]["zones"]["hand"], ["m2"])
        self.assertEqual(s.players["p2"]["zones"]["exile"], ["m2"])
        self.assertEqual(s.rules_manifestation_characteristics(host)["power"], before - 2)

    def test_reordering_within_hand_keeps_the_original_drawn_instances(self):
        s, _ = self.setup(hand=["pw3"])
        action, = self.draw(s, 2)
        s.move_zone_card("p2", "hand", "p2", "hand", "m2", "bottom")
        self.assertEqual(s.players["p2"]["zones"]["hand"], ["pw3", "m3", "m2"])
        self.resolve(s, action)
        self.assertEqual(self.shown(s), ["m2", "m3"])
        self.choose(s, option="0")
        self.assertEqual(s.players["p2"]["zones"]["hand"], ["pw3", "m3"])

    def test_two_identical_draw_events_exile_the_selected_instance_only(self):
        s, host = self.setup(deck=["m2", "m2"])
        before = s.rules_manifestation_characteristics(host)["power"]
        first, = self.draw(s, 1)
        second, = self.draw(s, 1)
        self.resolve(s, second)
        self.assertEqual(self.shown(s), ["m2"])
        self.choose(s, option="0")
        self.resolve(s, first)
        self.assertEqual(self.shown(s), ["m2"])
        self.choose(s, option="0")
        self.assertEqual(s.players["p2"]["zones"]["exile"], ["m2", "m2"])
        self.assertEqual(s.rules_manifestation_characteristics(host)["power"], before - 2)

    def test_immune_hand_prevents_reveal_exile_and_power_loss(self):
        s, host = self.setup()
        before = s.rules_manifestation_characteristics(host)["power"]
        action, = self.draw(s, 2)
        self.immune(s)
        self.resolve(s, action)
        self.assertIsNone(s.rules_engine["pendingChoice"])
        self.assertEqual(s.players["p2"]["zones"]["exile"], [])
        self.assertEqual(s.rules_manifestation_characteristics(host)["power"], before)

    def test_late_hand_immunity_rejects_exile_without_partial_power_loss(self):
        s, _ = self.setup()
        action, = self.draw(s, 2)
        self.resolve(s, action)
        self.immune(s)
        choice = s.rules_engine["pendingChoice"]
        before = self.snapshot(s)
        self.assertIsNotNone(s.resolve_rules_choice("p1", choice["id"], option="0")[0])
        self.assertEqual(self.snapshot(s), before)

    def test_pending_choice_rejects_returned_card_even_with_same_card_id(self):
        s, _ = self.setup()
        action, = self.draw(s, 2)
        self.resolve(s, action)
        choice = s.rules_engine["pendingChoice"]
        s.move_zone_card("p2", "hand", "p2", "graveyard", "m2")
        s.move_zone_card("p2", "graveyard", "p2", "hand", "m2", "bottom")
        before = self.snapshot(s)
        self.assertIsNotNone(s.resolve_rules_choice("p1", choice["id"], option="0")[0])
        self.assertEqual(self.snapshot(s), before)
        self.choose(s, option="1")
        self.assertIn("m3", s.players["p2"]["zones"]["exile"])

    def test_invalid_indices_and_wrong_player_are_atomic(self):
        for actor, option in (("p2", "0"), ("p1", "-1"), ("p1", "2"), ("p1", "bad"),
                              ("p1", {}), ("p1", 0.5), ("p1", True)):
            with self.subTest(actor=actor, option=option):
                s, _ = self.setup()
                action, = self.draw(s, 2)
                self.resolve(s, action)
                choice = s.rules_engine["pendingChoice"]
                before = self.snapshot(s)
                self.assertIsNotNone(s.resolve_rules_choice(actor, choice["id"], option=option)[0])
                self.assertEqual(self.snapshot(s), before)

    def test_duplicate_answer_cannot_exile_or_reduce_power_again(self):
        s, _ = self.setup()
        action, = self.draw(s, 2)
        self.resolve(s, action)
        choice = s.rules_engine["pendingChoice"]
        self.choose(s, option="0")
        before = self.snapshot(s)
        self.assertIsNotNone(s.resolve_rules_choice("p1", choice["id"], option="0")[0])
        self.assertEqual(self.snapshot(s), before)

    def test_no_trigger_for_own_recovery_empty_or_locked_draw(self):
        from session import ADVANCED_PHASES
        for excluded in ("own", "recovery", "empty", "locked"):
            with self.subTest(excluded=excluded):
                s, _ = self.setup()
                if excluded == "recovery":
                    s.phase_tracker["index"] = ADVANCED_PHASES.index("recovery_draw")
                if excluded == "empty":
                    self.put(s, "p2", "deck", [])
                if excluded == "locked":
                    s.rules_engine["drawLocks"] = [{"playerId": "p2", "turn": 2}]
                if excluded == "own":
                    self.put(s, "p1", "deck", ["m2", "m3"])
                self.assertEqual(self.draw(s, 2, player="p1" if excluded == "own" else "p2"), [])
                if excluded == "own":
                    self.assertEqual(s.players["p1"]["zones"]["hand"], ["m2", "m3"])

    def test_no_trigger_outside_interzone_face_down_or_silenced(self):
        for excluded in ("field", "face_down", "silenced"):
            with self.subTest(excluded=excluded):
                s, host = self.setup()
                if excluded == "field":
                    host["fieldZone"] = "confrontation"
                elif excluded == "face_down":
                    host["faceUp"] = False
                else:
                    s.rules_engine["ongoingEffects"].append({"id": "silence", "kind": "lose_effects",
                        "target": {"kind": "card", "itemId": host["id"]}, "duration": "while_target_on_field"})
                self.assertEqual(self.draw(s, 2), [])

    def test_draw_snapshot_stays_private_until_effect_resolution(self):
        s, _ = self.setup()
        action, = self.draw(s, 2)
        s.rules_engine["actionStack"] = [action]
        state = s.serialize_for("p1", "player")
        self.assertNotIn("cards", state["players"]["p2"]["zones"]["hand"])
        self.assertNotIn('"m2"', json.dumps(state["rulesEngine"]["actionStack"]))
        self.resolve(s, s.rules_engine["actionStack"].pop())
        self.assertEqual(self.shown(s), ["m2", "m3"])


if __name__ == "__main__":
    unittest.main()
