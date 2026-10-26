"""Selected Support clauses: handwritten expectations from English card text.

Real shipped card definitions, production trigger/choice/Stack paths; helper
Manifestations are only targets. These cases do not certify every interaction.
"""
import copy
import unittest

import test_semantic_batch_001_150 as fixtures


class SupportClauseAudit(unittest.TestCase):
    cid = staticmethod(fixtures.SemanticBatch001150.cid)
    world = fixtures.SemanticBatch001150.world
    field = staticmethod(fixtures.SemanticBatch001150.field)
    put = staticmethod(fixtures.SemanticBatch001150.put)
    target = staticmethod(fixtures.SemanticBatch001150.target)
    action = fixtures.SemanticBatch001150.action

    def power(self, session, item):
        return session.rules_manifestation_characteristics(item)["power"]

    def resolve(self, session, action):
        session.rules_engine["actionStack"].append(action)
        outcome = session.resolve_rules_top_action()
        self.assertIsNotNone(outcome)
        return outcome

    def entry(self, session, item, zone="confrontation"):
        actions = session.queue_rules_field_zone_entry_triggers(item, zone, defer=True)
        self.assertEqual(len(actions), 1)
        return actions[0]

    def test_pan_interzone_put_fires_first_stone_cz_entry_once_without_reentering_field(self):
        s = self.world()
        pan = self.field(s, self.cid("Pan Zuto, the Beckoner"))
        stone = self.field(s, self.cid("First Stone"), "stone", zone="interzone")
        self.put(s, "p2", "hand", ["m3"])
        s.apply_rules_action_result(self.action("Pan Zuto, the Beckoner", pan, [self.target(stone)]))
        self.assertEqual((stone["fieldZone"], stone["isSupport"]), ("confrontation", True))
        self.assertEqual(len(s.rules_engine["actionStack"]), 1)
        followup = s.rules_engine["actionStack"][-1]
        self.assertEqual(followup["source"]["cardId"], self.cid("First Stone"))
        s.resolve_rules_top_action()
        choice = s.rules_engine["pendingChoice"]
        self.assertEqual((choice["kind"], choice["playerId"]), ("chain_manifestation", "p2"))
        self.assertIsNone(s.resolve_rules_choice("p2", choice["id"], card_ids=["m3"])[0])
        self.assertEqual(len([i for i in s.battlefield if i["cardId"] == "m3"]), 1)

    def test_pan_interzone_put_does_not_repeat_seeker_field_entry_or_trigger_mazzolong(self):
        s = self.world()
        pan = self.field(s, self.cid("Pan Zuto, the Beckoner"))
        seeker = self.field(s, self.cid("Keen-eyed Seeker"), "seeker", zone="interzone")
        self.field(s, self.cid("Mazzolong, the Log-chief"), "mazzo", zone="interzone")
        self.put(s, "p1", "deck", ["m2"])
        s.apply_rules_action_result(self.action("Pan Zuto, the Beckoner", pan, [self.target(seeker)]))
        self.assertEqual(s.rules_engine["actionStack"], [])
        self.assertEqual(s.players["p1"]["zones"]["hand"], [])
        self.assertEqual(s.players["p1"]["zones"]["deck"], ["m2"])

    def test_pan_target_still_needs_own_interzone_at_resolution(self):
        for change in ("opponent", "confrontation", "gone"):
            with self.subTest(change=change):
                s = self.world()
                pan = self.field(s, self.cid("Pan Zuto, the Beckoner"))
                item = self.field(s, "m3", "candidate", zone="interzone")
                action = self.action("Pan Zuto, the Beckoner", pan, [self.target(item)])
                if change == "opponent":
                    item["controllerId"] = "p2"
                elif change == "confrontation":
                    item["fieldZone"] = "confrontation"
                else:
                    s.battlefield.remove(item)
                self.resolve(s, action)
                self.assertFalse(item.get("isSupport", False))
                self.assertEqual(s.rules_engine["actionStack"], [])

    def test_pan_only_triggers_when_entering_cz_and_is_optional(self):
        for zone, expected in (("interzone", 0), ("field", 0), ("confrontation", 1)):
            with self.subTest(zone=zone):
                s = self.world()
                pan = self.field(s, self.cid("Pan Zuto, the Beckoner"), zone=zone)
                self.field(s, "m2", "candidate", zone="interzone")
                actions = s.queue_rules_field_zone_entry_triggers(pan, zone, defer=True)
                self.assertEqual(len(actions), expected)
                if actions:
                    s.queue_rules_simultaneous_actions(actions)
                    choice = s.rules_engine["pendingChoice"]
                    self.assertEqual((choice["kind"], choice["playerId"]), ("optional_stack_action", "p1"))
                    self.assertIsNone(s.resolve_rules_choice("p1", choice["id"], option="decline")[0])
                    self.assertEqual(s.rules_engine["actionStack"], [])
                    self.assertEqual(s.find_battlefield_item("candidate")["fieldZone"], "interzone")

    def test_consult_put_fires_first_stone_cz_trigger_and_not_mazzolong_play_trigger(self):
        s = self.world()
        self.field(s, self.cid("Mazzolong, the Log-chief"), "mazzo", zone="interzone")
        self.put(s, "p1", "deck", ["w2", self.cid("First Stone"), "m4"])
        self.put(s, "p2", "hand", ["m3"])
        action = self.action("Consult", targets=[{"kind": "player", "playerId": "p1"}])
        result = s.apply_rules_action_result(action)
        self.assertEqual(result["discarded"], ["w2"])
        self.assertEqual(s.players["p1"]["zones"]["deck"], ["m4"])
        self.assertEqual(s.players["p1"]["zones"]["graveyard"], ["w2"])
        self.assertEqual([a["source"]["cardId"] for a in s.rules_engine["actionStack"]], [self.cid("First Stone")])

    def test_twist_put_fires_seeker_field_entry_once_and_not_mazzolong_play_trigger(self):
        s = self.world()
        self.field(s, self.cid("Mazzolong, the Log-chief"), "mazzo", zone="interzone")
        seeker = self.cid("Keen-eyed Seeker")
        self.put(s, "p1", "receptacle", [seeker])
        self.put(s, "p1", "deck", ["m4", "m3"])
        target = {"kind": "zone_card", "cardId": seeker, "zone": "receptacle", "containerId": "p1", "ownerId": "p1"}
        s.apply_rules_action_result(self.action("Twist the Soul", targets=[target]))
        self.assertEqual(len(s.rules_engine["actionStack"]), 1)
        self.assertEqual(s.rules_engine["actionStack"][0]["source"]["cardId"], seeker)
        s.resolve_rules_top_action()
        self.assertEqual(s.players["p1"]["zones"]["hand"], ["m4"])
        self.assertEqual(s.players["p1"]["zones"]["deck"], ["m3"])

    def test_twist_put_fires_first_stone_cz_entry(self):
        s = self.world()
        stone = self.cid("First Stone")
        self.put(s, "p1", "receptacle", [stone])
        self.put(s, "p2", "hand", ["m3"])
        target = {"kind": "zone_card", "cardId": stone, "zone": "receptacle", "containerId": "p1", "ownerId": "p1"}
        s.apply_rules_action_result(self.action("Twist the Soul", targets=[target]))
        self.assertEqual([a["source"]["cardId"] for a in s.rules_engine["actionStack"]], [stone])

    def test_consult_and_twist_new_field_entries_trigger_blossom_but_pan_internal_move_does_not(self):
        for name, expected in (("Consult", 1), ("Twist the Soul", 1), ("Pan Zuto, the Beckoner", 0)):
            with self.subTest(card=name):
                s = self.world()
                blossom = self.field(s, self.cid("Intoxicating Blossom"), "blossom", zone="interzone")
                if name == "Consult":
                    self.put(s, "p1", "deck", ["m3"])
                    action = self.action(name, targets=[{"kind": "player", "playerId": "p1"}])
                elif name == "Twist the Soul":
                    self.put(s, "p1", "receptacle", ["m3"])
                    action = self.action(name, targets=[{"kind": "zone_card", "cardId": "m3", "zone": "receptacle", "containerId": "p1", "ownerId": "p1"}])
                else:
                    pan = self.field(s, self.cid(name), "pan")
                    item = self.field(s, "m3", "new", zone="interzone")
                    action = self.action(name, pan, [self.target(item)])
                s.apply_rules_action_result(action)
                self.assertEqual(len(s.rules_engine["actionStack"]), expected)
                for _ in range(expected):
                    s.resolve_rules_top_action()
                self.assertEqual(blossom["counters"].get("Petal", 0), expected)

    def test_consult_no_manifestation_discards_only_actual_deck_and_creates_no_support(self):
        s = self.world()
        self.put(s, "p2", "deck", ["w2", "pw3"])
        result = s.apply_rules_action_result(self.action("Consult", targets=[{"kind": "player", "playerId": "p2"}]))
        self.assertEqual(result["status"], "no_manifestation")
        self.assertEqual(s.players["p2"]["zones"]["deck"], [])
        self.assertCountEqual(s.players["p2"]["zones"]["graveyard"], ["w2", "pw3"])
        self.assertEqual(s.battlefield, [])

    def test_twist_outcome_returns_to_controller_vessel_on_win_and_owners_hand_otherwise(self):
        for outcome in ("win", "loss", "stalemate"):
            with self.subTest(outcome=outcome):
                s = self.world()
                s.put_zone_card("p1", "receptacle", "m3", "p2")
                target = {"kind": "zone_card", "cardId": "m3", "zone": "receptacle", "containerId": "p1", "ownerId": "p2"}
                result = s.apply_rules_action_result(self.action("Twist the Soul", targets=[target]))
                item = s.find_battlefield_item(result["itemId"])
                self.assertEqual((item["ownerId"], item["controllerId"]), ("p2", "p1"))
                s.rules_engine["confrontationResult"] = {
                    "turn": 2, "status": "effects", "stalemate": outcome == "stalemate",
                    "winnerId": "p1" if outcome == "win" else "p2" if outcome == "loss" else None,
                    "loserId": "p2" if outcome == "win" else "p1" if outcome == "loss" else None,
                    "participantItemIds": [item["id"]],
                    "winnerItemIds": [item["id"]] if outcome == "win" else [],
                    "loserItemIds": [item["id"]] if outcome == "loss" else [],
                }
                s.begin_rules_confrontation_cleanup()
                self.assertIsNone(s.find_battlefield_item(item["id"]))
                self.assertEqual(s.players["p1"]["zones"]["receptacle"], ["m3"] if outcome == "win" else [])
                self.assertEqual(s.players["p2"]["zones"]["hand"], [] if outcome == "win" else ["m3"])
                if outcome == "win":
                    self.assertEqual(s.card_owner_in_zone("p1", "receptacle", "m3"), "p2")

    def test_pin_down_prevents_queued_puts_but_wretched_arena_allows_them(self):
        for name in ("Pan Zuto, the Beckoner", "Consult", "Twist the Soul", "Silem, the Magnetic", "Regurgitating Catacomb"):
            for lock in ("Pin Down", "Wretched Arena"):
                with self.subTest(card=name, lock=lock):
                    s = self.world()
                    if name == "Consult":
                        self.put(s, "p1", "deck", ["m3"])
                        action = self.action(name, targets=[{"kind": "player", "playerId": "p1"}])
                    elif name in ("Twist the Soul", "Regurgitating Catacomb"):
                        zone = "receptacle" if name == "Twist the Soul" else "graveyard"
                        self.put(s, "p1", zone, ["m3"])
                        action = self.action(name, targets=[{"kind": "zone_card", "cardId": "m3", "zone": zone, "containerId": "p1", "ownerId": "p1"}],
                            ability_id="catacomb-raise-discarded-manifestation" if name == "Regurgitating Catacomb" else None)
                    else:
                        source = self.field(s, self.cid(name), "source")
                        item = self.field(s, "m3", "candidate", zone="interzone" if name.startswith("Pan") else "stalemate")
                        action = self.action(name, source, [self.target(item)] if name.startswith("Pan") else [])
                    s.apply_rules_action_result(self.action(lock))
                    s.apply_rules_action_result(action)
                    arrivals = [i for i in s.battlefield if i.get("cardId") == "m3" and i.get("fieldZone") == "confrontation"]
                    self.assertEqual(len(arrivals), int(lock == "Wretched Arena"))
                    if lock == "Pin Down":
                        if name == "Consult":
                            self.assertEqual(s.players["p1"]["zones"]["deck"], ["m3"])
                        elif name in ("Twist the Soul", "Regurgitating Catacomb"):
                            self.assertEqual(s.players["p1"]["zones"][zone], ["m3"])

    def test_consult_still_discards_prior_wills_when_support_entry_is_prevented(self):
        s = self.world()
        self.put(s, "p2", "deck", ["w2", "pw3", "m3", "m4"])
        s.apply_rules_action_result(self.action("Pin Down"))
        result = s.apply_rules_action_result(self.action("Consult", targets=[{"kind": "player", "playerId": "p2"}]))
        self.assertEqual(result["status"], "prevented")
        self.assertEqual(result["discarded"], ["w2", "pw3"])
        self.assertEqual(s.players["p2"]["zones"]["deck"], ["m3", "m4"])
        self.assertCountEqual(s.players["p2"]["zones"]["graveyard"], ["w2", "pw3"])

    def test_consult_checks_recipient_lock_and_old_turn_locks_expire(self):
        for locked_player, lock_turn, expected in (("p1", 2, True), ("p2", 2, False), ("p2", 1, True)):
            with self.subTest(locked_player=locked_player, lock_turn=lock_turn):
                s = self.world()
                self.put(s, "p2", "deck", ["m3"])
                s.rules_engine["supportLocks"] = [{"turn": lock_turn, "playerId": locked_player, "playOnly": False}]
                s.apply_rules_action_result(self.action("Consult", targets=[{"kind": "player", "playerId": "p2"}]))
                entrants = [i for i in s.battlefield if i["cardId"] == "m3"]
                self.assertEqual(len(entrants), int(expected))
                if entrants:
                    self.assertEqual(entrants[0]["controllerId"], "p2")

    def test_chabak_special_support_play_triggers_mazzolong_once_after_two_cards_are_stalemated(self):
        s = self.world()
        self.field(s, self.cid("Mazzolong, the Log-chief"), zone="interzone")
        chabak = self.cid("Chabak, the Ungrateful")
        self.put(s, "p1", "hand", [chabak, "m2", "m3"])
        self.put(s, "p1", "deck", ["m4"])
        s.rules_engine["priorityPlayerId"] = "p1"
        error, _ = s.declare_rules_action("p1", "Chabak", kind="activated_effect",
            source={"cardId": chabak, "zone": "hand"},
            ability_id="chabak-plays-in-support-for-two-manifestations")
        self.assertIsNone(error)
        s.resolve_rules_top_action()
        choice = s.rules_engine["pendingChoice"]
        self.assertIsNotNone(choice)
        self.assertIsNone(s.resolve_rules_choice("p1", choice["id"], card_ids=["m2", "m3"])[0])
        self.assertCountEqual([i["cardId"] for i in s.battlefield if i.get("fieldZone") == "stalemate"], ["m2", "m3"])
        self.assertEqual(len(s.rules_engine["actionStack"]), 1)
        s.resolve_rules_top_action()
        self.assertEqual(s.players["p1"]["zones"]["hand"], ["m4"])

    def test_silem_put_suppresses_arriving_cards_own_triggers_and_does_not_count_as_play(self):
        s = self.world()
        source = self.field(s, self.cid("Silem, the Magnetic"))
        stone = self.field(s, self.cid("First Stone"), "stone", zone="stalemate")
        self.field(s, self.cid("Mazzolong, the Log-chief"), "mazzo", zone="interzone")
        self.put(s, "p2", "hand", ["m3"])
        self.put(s, "p1", "deck", ["m4"])
        self.resolve(s, self.entry(s, source))
        self.assertEqual((stone["fieldZone"], stone["isSupport"]), ("confrontation", True))
        self.assertFalse(s.rules_item_effects_active(stone))
        self.assertEqual(s.rules_engine["actionStack"], [])
        self.assertIsNone(s.rules_engine["pendingChoice"])
        self.assertEqual(s.players["p1"]["zones"]["deck"], ["m4"])
        s.phase_tracker["turn"] = 3
        s.prune_rules_ongoing_effects()
        self.assertTrue(s.rules_item_effects_active(stone))
        self.assertEqual(s.rules_engine["actionStack"], [], "Expiry does not replay an entry trigger")

    def test_stoic_previous_turn_loss_is_required_for_future_support_bonus(self):
        for losses, expected in (({}, 3), ({"1": "p2"}, 3), ({"0": "p1"}, 3), ({"1": "p1"}, 4)):
            with self.subTest(losses=losses):
                s = self.world()
                snoozer = self.field(s, self.cid("Stoic Snoozer"))
                s.rules_engine["confrontationLosses"] = losses
                self.resolve(s, self.entry(s, snoozer))
                entrant = self.field(s, "m3", "new", zone="interzone")
                s.mark_rules_support_entry(entrant)
                self.assertEqual(self.power(s, entrant), expected)

    def test_stoic_bonus_is_prospective_control_scoped_and_expires(self):
        s = self.world()
        snoozer = self.field(s, self.cid("Stoic Snoozer"), owner="p2", controller="p1")
        old = self.field(s, "m3", "old", support=True)
        s.rules_engine["confrontationLosses"] = {"1": "p1"}
        self.resolve(s, self.entry(s, snoozer))
        self.assertEqual(self.power(s, old), 3)
        # A resolved effect remains effective after Snoozer leaves the field.
        s._rules_remove_field_item(snoozer, "p2", "graveyard")
        own = self.field(s, "m3", "own", owner="p2", controller="p1", zone="interzone")
        enemy = self.field(s, "m3", "enemy", owner="p1", controller="p2", zone="interzone")
        s.mark_rules_support_entry(own)
        s.mark_rules_support_entry(enemy)
        self.assertEqual((self.power(s, own), self.power(s, enemy)), (4, 3))
        s.phase_tracker["turn"] = 3
        s.prune_rules_ongoing_effects()
        later = self.field(s, "m3", "later", zone="interzone")
        s.mark_rules_support_entry(later)
        self.assertEqual((self.power(s, own), self.power(s, later)), (3, 3))

    def test_jondo_strict_base_comparison_ignores_additive_bonuses(self):
        for base, bonus, grants in ((3, 20, True), (4, -2, False), (5, -4, False)):
            with self.subTest(first_base=base, bonus=bonus):
                s = self.world()
                first = self.field(s, "m3", "first", power_bonus=bonus)
                s.card_rules["m3"]["power"] = base
                jondo = self.field(s, self.cid("Jondo, the Pure Heart"), "jondo", zone="interzone")
                s.rules_engine["firstManifestationItemIds"] = {"p1": first["id"]}
                actions = s.queue_rules_revelation_triggers(defer=True)
                self.assertEqual(len(actions), 1)
                self.resolve(s, actions[0])
                self.assertEqual(s.rules_card_can_enter_support(jondo), grants)
                s.phase_tracker["turn"] = 3
                self.assertFalse(s.rules_card_can_enter_support(jondo))

    def test_jondo_no_first_or_wrong_source_zone_does_not_grant_support(self):
        for zone in ("interzone", "confrontation", "stalemate"):
            with self.subTest(zone=zone):
                s = self.world()
                jondo = self.field(s, self.cid("Jondo, the Pure Heart"), zone=zone)
                actions = s.queue_rules_revelation_triggers(defer=True)
                self.assertEqual(len(actions), int(zone == "interzone"))
                for action in actions:
                    self.resolve(s, action)
                self.assertFalse(s.rules_card_can_enter_support(jondo))

    def test_jondo_only_winning_support_is_exiled_at_confrontation_cleanup(self):
        for support, won, expected_exile in ((True, True, True), (False, True, False), (True, False, False)):
            with self.subTest(support=support, won=won):
                s = self.world()
                first = self.field(s, "m3", "first")
                jondo = self.field(s, self.cid("Jondo, the Pure Heart"), "jondo")
                foe = self.field(s, "m4", "foe", owner="p2")
                if support:
                    s.mark_rules_support_entry(jondo)
                else:
                    s.battlefield.remove(first)
                s.rules_engine["confrontationResult"] = {
                    "turn": 2, "status": "effects", "winnerId": "p1" if won else "p2", "loserId": "p2" if won else "p1", "stalemate": False,
                    "participantItemIds": [i["id"] for i in s.battlefield],
                    "winnerItemIds": ["first", "jondo"] if won else ["foe"],
                    "loserItemIds": ["foe"] if won else ["first", "jondo"],
                }
                s.begin_rules_confrontation_cleanup()
                self.assertEqual(self.cid("Jondo, the Pure Heart") in s.players["p1"]["zones"]["exile"], expected_exile)

    def test_mazzolong_each_own_support_play_draws_one_but_put_and_other_player_do_not(self):
        for played, player, expected in ((True, "p1", 1), (False, "p1", 0), (True, "p2", 0)):
            with self.subTest(played=played, player=player):
                s = self.world()
                self.field(s, self.cid("Mazzolong, the Log-chief"), zone="interzone")
                item = self.field(s, "m3", "new", owner=player, support=True)
                self.put(s, "p1", "deck", ["m2", "m4"])
                actions = s.queue_rules_support_entry_triggers(item, played=played, from_zone="hand", defer=True)
                self.assertEqual(len(actions), expected)
                for action in actions:
                    self.resolve(s, action)
                self.assertEqual(s.players["p1"]["zones"]["hand"], ["m2"] if expected else [])

    def test_mazzolong_chain_counts_as_play_and_draws_to_current_controller(self):
        s = self.world()
        self.field(s, self.cid("Mazzolong, the Log-chief"), owner="p2", controller="p1", zone="interzone")
        self.put(s, "p1", "hand", ["m3"])
        self.put(s, "p1", "deck", ["m2", "m4"])
        error, _ = s.chain_rules_manifestation("p1", "hand", "m3")
        self.assertIsNone(error)
        self.assertEqual(len(s.rules_engine["actionStack"]), 1)
        s.resolve_rules_top_action()
        self.assertEqual(s.players["p1"]["zones"]["hand"], ["m2"])
        self.assertEqual(s.players["p2"]["zones"]["hand"], [])

    def test_mazzolong_outside_interzone_or_silenced_does_not_watch_support(self):
        for zone, silent in (("confrontation", False), ("stalemate", False), ("interzone", True)):
            with self.subTest(zone=zone, silent=silent):
                s = self.world()
                watcher = self.field(s, self.cid("Mazzolong, the Log-chief"), zone=zone)
                if silent:
                    watcher["effectsDisabled"] = True
                item = self.field(s, "m3", "new", support=True)
                self.assertEqual(s.queue_rules_support_entry_triggers(item, played=True, from_zone="hand", defer=True), [])

    def test_peropero_top_visibility_follows_control_and_disappears_when_source_leaves(self):
        s = self.world()
        pero = self.field(s, self.cid("Peropero, the Spirophant"), owner="p2", controller="p1", zone="interzone")
        self.put(s, "p1", "deck", ["m2", "m3"])
        self.put(s, "p2", "deck", ["m4"])
        for seat in ("p1", "p2"):
            self.assertEqual(s.serialize_for(seat, "player")["rulesEngine"]["uncoveredTops"], {"p1": "m2"})
        s.take_zone_card("p1", "deck", "m2")
        self.assertEqual(s.rules_uncovered_deck_top("p1"), "m3")
        pero["controllerId"] = "p2"
        self.assertIsNone(s.rules_uncovered_deck_top("p1"))
        self.assertEqual(s.rules_uncovered_deck_top("p2"), "m4")
        s.battlefield.remove(pero)
        self.assertIsNone(s.rules_uncovered_deck_top("p2"))

    def test_peropero_rejects_covered_manifestation_and_uncovered_will_atomically(self):
        for deck, card in ((["m2", self.cid("Wind Sprout")], self.cid("Wind Sprout")), (["w2", "m2"], "w2")):
            with self.subTest(deck=deck):
                s = self.world()
                self.field(s, self.cid("Peropero, the Spirophant"), zone="interzone")
                self.put(s, "p1", "deck", deck)
                s.rules_engine["priorityPlayerId"] = "p1"
                before = copy.deepcopy(s.players)
                error, action = s.declare_rules_action("p1", "play top", kind="play_card",
                    source={"zone": "deck", "cardId": card}, as_support=True)
                self.assertIsNotNone(error)
                self.assertIsNone(action)
                self.assertEqual(s.players, before)
                self.assertEqual(s.rules_engine["actionStack"], [])

    def test_peropero_legal_top_support_survives_source_departure_after_declaration(self):
        s = self.world()
        pero = self.field(s, self.cid("Peropero, the Spirophant"), zone="interzone")
        sprout = self.cid("Wind Sprout")
        self.put(s, "p1", "deck", [sprout, "m4"])
        s.rules_engine["priorityPlayerId"] = "p1"
        error, action = s.declare_rules_action("p1", "play top", kind="play_card",
            source={"zone": "deck", "cardId": sprout}, as_support=True)
        self.assertIsNone(error)
        self.assertEqual(s.players["p1"]["zones"]["deck"], ["m4"])
        s._rules_remove_field_item(pero, "p1", "graveyard")
        s.resolve_rules_top_action()
        entered = [i for i in s.battlefield if i.get("cardId") == sprout]
        self.assertEqual(len(entered), 1)
        self.assertEqual((entered[0]["isSupport"], self.power(s, entered[0])), (True, 1))


if __name__ == "__main__":
    unittest.main()
