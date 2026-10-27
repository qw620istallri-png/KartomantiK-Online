"""Selected printed clauses for Traumatize and Extortionist Womb."""
import json
import unittest
import test_discard_draw_clauses as base


class PrivateHandClauses(unittest.TestCase):
    world = base.DiscardDrawClauses.world
    cid = staticmethod(base.DiscardDrawClauses.cid)
    field = staticmethod(base.DiscardDrawClauses.field)
    put = staticmethod(base.DiscardDrawClauses.put)
    action = base.DiscardDrawClauses.action
    snapshot = base.DiscardDrawClauses.snapshot
    choose = base.DiscardDrawClauses.choose
    TRAUMA = "Traumatize"
    WOMB = "Extortionist Womb"

    def trauma(self, s, target="p2", resolve=True):
        card = self.cid(self.TRAUMA)
        self.put(s, "p1", "hand", [*s.players["p1"]["zones"]["hand"], card])
        s.add_rules_excess_essence("p1", [{"temperament": "melancholic", "amount": 2}])
        error, action = s.declare_rules_action("p1", "Traumatize", kind="play_card",
            source={"cardId": card, "zone": "hand"}, ability_id="traumatize",
            targets=[{"kind": "player", "playerId": target}])
        self.assertIsNone(error)
        if resolve:
            s.resolve_rules_top_action()
        return action

    def womb(self, s, resolve=True):
        host = self.field(s, self.cid(self.WOMB), "womb", zone="field")
        action = self.action(self.WOMB, host)
        s.rules_engine["actionStack"].append(action)
        if resolve:
            s.resolve_rules_top_action()
        return host

    def pick(self, name, hand=("m2", "m3")):
        s = self.world()
        self.put(s, "p2", "hand", hand)
        if name == self.TRAUMA:
            self.trauma(s)
        else:
            self.womb(s)
            self.choose(s, option="yes")
        return s

    def tokens(self, s):
        items = [i for i in s.battlefield if i.get("isTokenCard") and i.get("controllerId") == "p1"]
        self.assertEqual(len(items), 2)
        self.assertTrue(all(i.get("isSupport") for i in items))
        for item in items:
            stats = s.rules_manifestation_characteristics(item)
            self.assertEqual((stats["power"], stats["temperament"]), (2, "hollow"))

    def protect_hand(self, s):
        self.field(s, "l3ne0zha51w387z_en", "ritual", owner="p2", zone="field")
        self.assertTrue(s.rules_hand_is_immune("p2", "p1"))

    def test_traumatize_pays_essence_before_response_but_loses_points_at_resolution(self):
        s = self.world()
        self.put(s, "p2", "hand", ["m2", "w2"])
        action = self.trauma(s, resolve=False)
        self.assertEqual(sum(entry.get("amount", 0) for entry in action["cost"]["essenceSpent"]), 2)
        self.assertEqual(s.players["p1"]["score"], 50)
        self.assertEqual(s.rules_engine["priorityPlayerId"], "p2")
        s.resolve_rules_top_action()
        self.assertEqual(s.players["p1"]["score"], 45)
        self.assertEqual(s.rules_engine["pendingChoice"]["cardIds"], ["m2", "w2"])
        self.choose(s, option="1")
        self.assertEqual(s.players["p2"]["zones"]["graveyard"], ["w2"])
        self.assertEqual(s.players["p2"]["zones"]["hand"], ["m2"])
        self.assertEqual(s.players["p1"]["score"], 45)

    def test_traumatize_empty_or_immune_hand_still_loses_five_without_choice(self):
        for case in ("empty", "immune"):
            with self.subTest(case=case):
                s = self.world()
                if case == "immune":
                    self.put(s, "p2", "hand", ["m2"])
                    self.protect_hand(s)
                self.trauma(s)
                self.assertEqual(s.players["p1"]["score"], 45)
                self.assertIsNone(s.rules_engine["pendingChoice"])

    def test_traumatize_can_choose_self_and_own_ritual_does_not_prevent_discard(self):
        s = self.world()
        self.put(s, "p1", "hand", ["m2"])
        self.field(s, "l3ne0zha51w387z_en", "ritual", zone="field")
        self.trauma(s, target="p1")
        self.choose(s, option="0")
        self.assertIn("m2", s.players["p1"]["zones"]["graveyard"])
        self.assertEqual(s.players["p1"]["score"], 45)

    def test_traumatize_late_hand_immunity_rejects_discard_atomically(self):
        s = self.pick(self.TRAUMA)
        self.protect_hand(s)
        choice = s.rules_engine["pendingChoice"]
        before = self.snapshot(s)
        self.assertIsNotNone(s.resolve_rules_choice("p1", choice["id"], option="0")[0])
        self.assertEqual(self.snapshot(s), before)

    def test_traumatize_discard_respects_bob_limbo_suspension(self):
        s = self.pick(self.TRAUMA)
        self.field(s, "inner-deserts-134", "bob", power_bonus=5)
        self.choose(s, option="0")
        self.assertEqual(s.players["p2"]["zones"]["graveyard"], [])
        self.assertEqual([c["cardId"] for c in s.rules_engine["suspendedCards"]], ["m2"])
        self.assertFalse(any(e["kind"] == "cards_discarded" for e in s.rules_engine.get("observedEvents") or []))

    def test_traumatize_tenebro_discard_offers_atomic_optional_support(self):
        card = self.cid("Tenebro, Night Assailant")
        s = self.pick(self.TRAUMA, [card, "w2"])
        self.choose(s, option="0")
        self.assertTrue((s.rules_engine["pendingChoice"] or {}).get("_optionalReplacement"))
        self.assertEqual(s.players["p2"]["zones"]["hand"], [card, "w2"])
        self.choose(s, option="yes")
        self.assertTrue(any(i["cardId"] == card and i.get("isSupport") for i in s.battlefield))
        self.assertEqual(s.players["p1"]["score"], 45)

    def test_selecting_identical_second_copy_preserves_the_first_instance(self):
        for name in (self.TRAUMA, self.WOMB):
            with self.subTest(card=name):
                s = self.world()
                self.put(s, "p2", "hand", ["m2"])
                self.put(s, "p2", "deck", ["m2"])
                self.field(s, self.cid("Gorlok, the Blinded Indiscreet"), "gorlok", zone="interzone")
                s.request_rules_draw("p2", 1)
                gorlok, = s.queue_rules_observed_event_triggers(defer=True)
                if name == self.TRAUMA:
                    self.trauma(s)
                else:
                    self.womb(s)
                    self.choose(s, option="yes")
                self.choose(s, option="1")
                self.assertEqual(s.players["p2"]["zones"]["hand"], ["m2"])
                s.rules_engine["actionStack"].append(gorlok)
                s.resolve_rules_top_action()
                self.assertIsNone(s.rules_engine["pendingChoice"], "The drawn copy was selected, so Gorlok has no surviving drawn card")

    def test_returned_hand_card_is_not_an_old_selection(self):
        for name in (self.TRAUMA, self.WOMB):
            with self.subTest(card=name):
                s = self.pick(name)
                choice = s.rules_engine["pendingChoice"]
                s.move_zone_card("p2", "hand", "p2", "graveyard", "m2")
                s.move_zone_card("p2", "graveyard", "p2", "hand", "m2", "bottom")
                before = self.snapshot(s)
                self.assertIsNotNone(s.resolve_rules_choice("p1", choice["id"], option="0")[0])
                self.assertEqual(self.snapshot(s), before)
                self.choose(s, option="1")

    def test_indices_and_wrong_actor_are_rejected_without_mutation(self):
        for name in (self.TRAUMA, self.WOMB):
            for actor, option in (("p2", "0"), ("p1", "-1"), ("p1", "2"), ("p1", {}), ("p1", True), ("p1", 0.5)):
                with self.subTest(card=name, actor=actor, option=option):
                    s = self.pick(name)
                    choice = s.rules_engine["pendingChoice"]
                    before = self.snapshot(s)
                    self.assertIsNotNone(s.resolve_rules_choice(actor, choice["id"], option=option)[0])
                    self.assertEqual(self.snapshot(s), before)

    def test_duplicate_reply_neither_pays_again_nor_chains_again(self):
        for name in (self.TRAUMA, self.WOMB):
            with self.subTest(card=name):
                s = self.pick(name)
                choice = s.rules_engine["pendingChoice"]
                self.choose(s, option="0")
                before = self.snapshot(s)
                self.assertIsNotNone(s.resolve_rules_choice("p1", choice["id"], option="0")[0])
                self.assertEqual(self.snapshot(s), before)

    def test_womb_triggers_in_reaction_after_revelation_and_waits_on_stack(self):
        s = self.world()
        self.field(s, self.cid(self.WOMB), "womb", zone="field")
        self.assertEqual(s.queue_rules_revelation_triggers(defer=True), [])
        queued = s.queue_rules_reaction_triggers()
        self.assertEqual(len(queued), 1)
        self.assertEqual(len(s.rules_engine["actionStack"]), 1)
        self.assertIsNone(s.rules_engine["pendingChoice"])
        s.resolve_rules_top_action()
        self.assertEqual(s.rules_engine["pendingChoice"]["purpose"], "womb_show")

    def test_womb_refusal_produces_exact_two_power_two_hollow_supports(self):
        s = self.world()
        self.put(s, "p2", "hand", ["m2", "w2"])
        self.womb(s)
        self.choose(s, option="no")
        self.tokens(s)
        self.assertEqual(s.players["p2"]["zones"]["hand"], ["m2", "w2"])

    def test_womb_yes_shows_the_whole_hand_but_only_manifestations_are_selectable(self):
        s = self.world()
        self.put(s, "p2", "hand", ["w2", "m2", "pw3", "m3"])
        self.womb(s)
        result = self.choose(s, option="yes")
        self.assertEqual(result["handProof"], ["w2", "m2", "pw3", "m3"])
        self.assertEqual(s.rules_engine["pendingChoice"]["cardIds"], ["m2", "m3"])
        self.assertEqual(s.rules_engine["pendingChoice"]["revealedHandCardIds"], ["w2", "m2", "pw3", "m3"])
        self.choose(s, option="1")
        chained = [i for i in s.battlefield if i.get("isChained")]
        self.assertEqual(len(chained), 1)
        self.assertEqual((chained[0]["cardId"], chained[0]["ownerId"], chained[0]["controllerId"]), ("m3", "p2", "p2"))
        self.assertEqual(s.players["p2"]["zones"]["hand"], ["w2", "m2", "pw3"])

    def test_womb_no_chainable_manifestation_or_empty_hand_uses_fallback(self):
        for hand in ([], ["w2"], ["nlbgn1ranlrd09r_en", "inner-deserts-100"]):
            with self.subTest(hand=hand):
                s = self.world()
                self.put(s, "p2", "hand", hand)
                self.womb(s)
                self.choose(s, option="yes")
                self.tokens(s)
                self.assertIsNone(s.rules_engine["pendingChoice"])

    def test_womb_protected_hand_is_not_shown_and_cannot_be_chained(self):
        s = self.world()
        self.put(s, "p2", "hand", ["m2", "w2"])
        self.protect_hand(s)
        self.womb(s)
        result = self.choose(s, option="yes")
        self.tokens(s)
        self.assertFalse(result.get("handProof"))
        self.assertFalse(result.get("_privateHandReveal"))
        self.assertEqual(s.players["p2"]["zones"]["hand"], ["m2", "w2"])

    def test_womb_support_lock_after_show_uses_fallback_without_losing_choice_to_an_error(self):
        s = self.pick(self.WOMB)
        s.rules_engine["supportLocks"] = [{"playerId": "p2", "turn": 2}]
        self.choose(s, option="0")
        self.tokens(s)
        self.assertIsNone(s.rules_engine["pendingChoice"])
        self.assertEqual(s.players["p2"]["zones"]["hand"], ["m2", "m3"])

    def test_womb_late_hand_immunity_uses_fallback_without_chain(self):
        s = self.pick(self.WOMB)
        self.protect_hand(s)
        self.choose(s, option="0")
        self.tokens(s)
        self.assertEqual(s.players["p2"]["zones"]["hand"], ["m2", "m3"])

    def test_womb_source_departure_does_not_cancel_either_branch(self):
        for option in ("yes", "no"):
            with self.subTest(option=option):
                s = self.world()
                self.put(s, "p2", "hand", ["m2"])
                host = self.womb(s, resolve=False)
                s._rules_remove_field_item(host, "p1", "graveyard")
                s.resolve_rules_top_action()
                self.choose(s, option=option)
                if option == "no":
                    self.tokens(s)
                else:
                    self.choose(s, option="0")
                    self.assertTrue(any(i.get("isChained") and i["cardId"] == "m2" for i in s.battlefield))

    def test_private_hand_choices_hide_card_lists_from_spectators_but_not_the_players(self):
        for name in (self.TRAUMA, self.WOMB):
            with self.subTest(card=name):
                s = self.pick(name)
                for viewer in ("p1", "p2"):
                    self.assertEqual(s.serialize_for(viewer, "player")["rulesEngine"]["pendingChoice"]["cardIds"], ["m2", "m3"])
                spectator = s.serialize_for("spectator", "spectator")
                self.assertNotIn("cardIds", spectator["rulesEngine"]["pendingChoice"])
                self.assertNotIn('"m2"', json.dumps(spectator["rulesEngine"]["pendingChoice"]))
                self.assertEqual(s.serialize_for("judge", "judge")["rulesEngine"]["pendingChoice"]["cardIds"], ["m2", "m3"])

    def test_womb_private_hand_proof_is_redacted_in_spectator_logs(self):
        s = self.world()
        s.mode = "tournament"
        self.put(s, "p2", "hand", ["m2", "w2"])
        self.womb(s)
        result = self.choose(s, option="yes")
        s.add_log("p2", "rules_choice_resolved", result)
        self.assertNotIn("handProof", s.serialize_log("spectator", "spectator")["entries"][-1]["details"])
        for viewer in ("p1", "p2"):
            self.assertEqual(s.serialize_log("player", viewer)["entries"][-1]["details"]["handProof"], ["m2", "w2"])


if __name__ == "__main__":
    unittest.main()
