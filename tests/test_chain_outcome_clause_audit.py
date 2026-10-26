"""Printed Chain clauses: exact destinations, ownership and delayed consequences.

Only targets use synthetic Manifestations. Actions, effects, choices, movement
and cleanup use shipped definitions. This is selected-branch proof, not a full
certification of each card or every interaction between delayed memories.
"""
import copy
import unittest
from unittest.mock import patch

import test_semantic_batch_001_150 as fixtures


class ChainOutcomeClauseAudit(unittest.TestCase):
    cid = staticmethod(fixtures.SemanticBatch001150.cid)
    world = fixtures.SemanticBatch001150.world
    field = staticmethod(fixtures.SemanticBatch001150.field)
    put = staticmethod(fixtures.SemanticBatch001150.put)
    target = staticmethod(fixtures.SemanticBatch001150.target)
    action = fixtures.SemanticBatch001150.action
    URO = "Urocione, the Anarchist"
    LADY = "Lady of the Humps"

    def begin(self, s, name, owner="p1", controller="p1"):
        host = self.field(s, self.cid(name), "host", owner=owner, controller=controller)
        actions = (s.queue_rules_field_zone_entry_triggers(host, "confrontation", defer=True)
                   if name == "Mind Parasite" else
                   s.queue_rules_battlefield_entry_triggers(host["cardId"], owner, host["id"], True, defer=True))
        s.queue_rules_simultaneous_actions(actions)
        choice = s.rules_engine["pendingChoice"]
        if choice and choice["kind"] == "optional_stack_action":
            self.assertIsNone(s.resolve_rules_choice(controller, choice["id"], option="accept")[0])
        if s.rules_engine["actionStack"]:
            s.resolve_rules_top_action()
        return host, s.rules_engine["pendingChoice"]

    def choose(self, s, card="m3"):
        choice = s.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "chain_manifestation")
        error, result = s.resolve_rules_choice(choice["playerId"], choice["id"], card_ids=[card])
        self.assertIsNone(error)
        return s.find_battlefield_item(result.get("itemId")), result

    def outcome(self, s, winner="p1", *, stalemate=False):
        participants = s.rules_confrontation_items()
        s.rules_engine["confrontationResult"] = {
            "turn": s.phase_tracker["turn"], "status": "effects", "stalemate": stalemate,
            "winnerId": None if stalemate else winner,
            "loserId": None if stalemate else ("p2" if winner == "p1" else "p1"),
            "participantItemIds": [i["id"] for i in participants],
            "winnerItemIds": [] if stalemate else [i["id"] for i in participants if s.rules_item_controller_id(i) == winner],
            "loserItemIds": [] if stalemate else [i["id"] for i in participants if s.rules_item_controller_id(i) != winner],
        }

    def uro(self, s, owner="p1"):
        s.put_zone_card("p1", "hand", "m3", owner)
        host, choice = self.begin(s, self.URO)
        self.assertIsNotNone(choice)
        item, _ = self.choose(s)
        return host, item

    def test_urocione_private_choice_can_be_declined_without_spending_or_moving(self):
        s = self.world()
        self.put(s, "p1", "hand", ["m3", "w2"])
        _, choice = self.begin(s, self.URO)
        self.assertTrue(choice["optional"])
        opponent = s.serialize_for("p2", "player")["rulesEngine"]["pendingChoice"]
        self.assertNotIn("cardIds", opponent)
        self.assertNotIn("_cardIds", opponent)
        before = copy.deepcopy((s.players, s.battlefield, s.tokens))
        self.assertIsNone(s.resolve_rules_choice("p1", choice["id"], option="decline")[0])
        self.assertEqual((s.players, s.battlefield, s.tokens), before)
        self.assertIsNone(s.rules_engine["pendingChoice"])

    def test_urocione_no_chainable_hand_does_not_request_an_empty_choice(self):
        for hand in ([], ["w2"], [self.cid("The Slumberer")]):
            with self.subTest(hand=hand):
                s = self.world()
                self.put(s, "p1", "hand", hand)
                self.begin(s, self.URO)
                self.assertIsNone(s.rules_engine["pendingChoice"])
                self.assertEqual(s.rules_engine["actionStack"], [])
                self.assertEqual(s.players["p1"]["zones"]["hand"], hand)

    def test_urocione_winner_goes_to_opponent_of_immutable_owner(self):
        for owner, destination in (("p1", "p2"), ("p2", "p1")):
            with self.subTest(owner=owner):
                s = self.world()
                _, item = self.uro(s, owner)
                self.outcome(s)
                s.begin_rules_confrontation_cleanup()
                self.assertIsNone(s.find_battlefield_item(item["id"]))
                self.assertIn("m3", s.players[destination]["zones"]["receptacle"])
                self.assertEqual(s.card_owner_in_zone(destination, "receptacle", "m3"), owner)

    def test_urocione_victory_memory_survives_cleanse_and_source_departure(self):
        s = self.world()
        host, item = self.uro(s)
        item["counters"]["power"] = 2
        s.apply_rules_action_result(self.action("Cleanse", targets=[self.target(item)]))
        self.assertEqual(s.rules_manifestation_characteristics(item)["power"], 3)
        s._rules_remove_field_item(host, "p1", "graveyard")
        self.outcome(s)
        s.begin_rules_confrontation_cleanup()
        self.assertIsNone(s.find_battlefield_item(item["id"]))
        self.assertEqual(s.players["p2"]["zones"]["receptacle"], ["m3"])

    def test_urocione_snapshot_win_does_not_change_after_later_control_change(self):
        s = self.world()
        _, item = self.uro(s)
        self.outcome(s)
        item["controllerId"] = "p2"
        s.begin_rules_confrontation_cleanup()
        self.assertIn("m3", s.players["p2"]["zones"]["receptacle"])

    def test_urocione_memory_survives_hand_limbo_and_vessel_then_new_entry(self):
        for zone in ("hand", "graveyard", "receptacle"):
            with self.subTest(zone=zone):
                s = self.world()
                _, item = self.uro(s)
                s._rules_remove_field_item(item, "p1", zone)
                error, payload = s.chain_rules_manifestation("p1", zone, "m3")
                self.assertIsNone(error)
                returned = s.find_battlefield_item(payload["itemId"])
                self.assertNotEqual(returned["id"], item["id"])
                self.outcome(s)
                s.begin_rules_confrontation_cleanup()
                self.assertIn("m3", s.players["p2"]["zones"]["receptacle"])

    def test_urocione_memory_is_forgotten_after_deck_or_exile(self):
        for zone in ("deck", "exile"):
            with self.subTest(zone=zone):
                s = self.world()
                _, item = self.uro(s)
                s._rules_remove_field_item(item, "p1", zone)
                if zone == "exile":
                    s.take_zone_card("p1", "exile", "m3")
                    s.put_zone_card("p1", "hand", "m3", "p1")
                self.assertIsNone(s.chain_rules_manifestation("p1", "deck" if zone == "deck" else "hand", "m3")[0])
                self.outcome(s)
                s.begin_rules_confrontation_cleanup()
                self.assertNotIn("m3", s.players["p2"]["zones"]["receptacle"])

    def test_urocione_memory_does_not_attach_to_another_copy_still_in_hand(self):
        s = self.world()
        _, first = self.uro(s)
        self.put(s, "p1", "hand", ["m3"])
        error, payload = s.chain_rules_manifestation("p1", "hand", "m3")
        self.assertIsNone(error)
        second = s.find_battlefield_item(payload["itemId"])
        self.outcome(s)
        s.begin_rules_confrontation_cleanup()
        self.assertIsNone(s.find_battlefield_item(first["id"]))
        self.assertIsNotNone(s.find_battlefield_item(second["id"]))
        self.assertEqual(s.players["p2"]["zones"]["receptacle"].count("m3"), 1)

    def test_urocione_stalemate_does_not_apply_victory_destination(self):
        s = self.world()
        _, item = self.uro(s)
        self.outcome(s, stalemate=True)
        s.begin_rules_confrontation_cleanup()
        self.assertEqual(item["fieldZone"], "stalemate")
        self.assertEqual(s.players["p2"]["zones"]["receptacle"], [])

    def test_urocione_memory_applies_after_reentry_as_first_and_while_original_effects_are_lost(self):
        s = self.world()
        host, item = self.uro(s)
        s._rules_remove_field_item(item, "p1", "hand")
        s._rules_remove_field_item(host, "p1", "graveyard")
        s.phase_tracker["turn"] = 3
        s.rules_engine.update(firstManifestationComplete=False, firstManifestationItemIds={})
        returned = s.place_rules_card_in_interzone("p1", "p1", "hand", "m3")
        s.queue_rules_battlefield_entry_triggers("m3", "p1", returned["id"], True)
        self.assertTrue(s.rules_item_becomes_first_manifestation(returned, "p1"))
        self.assertFalse(returned.get("isSupport", False))
        returned["effectsDisabled"] = True
        self.outcome(s)
        s.begin_rules_confrontation_cleanup()
        self.assertEqual(s.players["p2"]["zones"]["receptacle"], ["m3"])

    def test_lady_search_is_mandatory_and_shuffles_only_after_a_valid_selection(self):
        s = self.world()
        self.put(s, "p1", "deck", ["w2", "m3", "m4"])
        with patch("game.chain.random.shuffle") as shuffle:
            _, choice = self.begin(s, self.LADY)
            self.assertEqual(shuffle.call_count, 0)
            self.assertFalse(choice["optional"])
            self.assertIsNotNone(s.resolve_rules_choice("p1", choice["id"], option="decline")[0])
            self.assertIsNotNone(s.resolve_rules_choice("p1", choice["id"], card_ids=["w2"])[0])
            self.assertEqual(shuffle.call_count, 0)
            item, _ = self.choose(s)
            self.assertEqual(item["cardId"], "m3")
            self.assertEqual(shuffle.call_count, 1)
            self.assertIs(shuffle.call_args.args[0], s.players["p1"]["zones"]["deck"])
        self.assertEqual(s.players["p1"]["zones"]["deck"], ["w2", "m4"])

    def test_lady_failed_search_still_shuffles_deck_without_revealing_it(self):
        for deck in ([], ["w2", "pw3"], [self.cid("The Slumberer"), "w2"]):
            with self.subTest(deck=deck):
                s = self.world()
                self.put(s, "p1", "deck", deck)
                with patch("game.chain.random.shuffle") as shuffle:
                    _, choice = self.begin(s, self.LADY)
                    self.assertIsNone(choice)
                    self.assertEqual(shuffle.call_count, 1)
                self.assertEqual(s.players["p1"]["zones"]["deck"], deck)

    def test_lady_suspension_replaces_chain_but_does_not_skip_final_shuffle(self):
        s = self.world()
        bob = self.field(s, self.cid("BOB"), "bob")
        bob["counters"]["power"] = 2
        self.put(s, "p1", "deck", ["m3", "w2"])
        with patch("game.chain.random.shuffle") as shuffle:
            self.begin(s, self.LADY)
            item, result = self.choose(s)
            self.assertIsNone(item)
            self.assertEqual(result["status"], "suspended")
            self.assertEqual(shuffle.call_count, 1)
        self.assertEqual(s.players["p1"]["zones"]["deck"], ["w2"])
        self.assertEqual([c["cardId"] for c in s.rules_engine["suspendedCards"]], ["m3"])

    def test_lady_win_exiles_foreign_owned_chain_after_cleanse_and_host_departure(self):
        s = self.world()
        s.put_zone_card("p1", "deck", "m3", "p2")
        host, _ = self.begin(s, self.LADY)
        item, _ = self.choose(s)
        s.apply_rules_action_result(self.action("Cleanse", targets=[self.target(item)]))
        s._rules_remove_field_item(host, "p1", "graveyard")
        self.outcome(s, winner="p2")
        s.begin_rules_confrontation_cleanup()
        self.assertIsNone(s.find_battlefield_item(item["id"]))
        self.assertIn("m3", s.players["p2"]["zones"]["exile"])
        self.assertNotIn("m3", s.players["p1"]["zones"]["exile"])

    def test_lady_nonwinning_chain_is_not_exiled(self):
        for draw in (False, True):
            with self.subTest(stalemate=draw):
                s = self.world()
                self.put(s, "p1", "deck", ["m3"])
                self.begin(s, self.LADY)
                item, _ = self.choose(s)
                self.outcome(s, winner="p2", stalemate=draw)
                s.begin_rules_confrontation_cleanup()
                self.assertNotIn("m3", s.players["p1"]["zones"]["exile"])
                if draw:
                    self.assertEqual(item["fieldZone"], "stalemate")
                else:
                    self.assertIn("m3", s.players["p2"]["zones"]["receptacle"])

    def test_chain_play_locks_filter_candidates_and_prevent_direct_mutation(self):
        for name in ("Pin Down", "Wretched Arena"):
            for zone in ("hand", "deck", "graveyard", "receptacle"):
                with self.subTest(lock=name, zone=zone):
                    s = self.world()
                    self.put(s, "p1", zone, ["m3"])
                    s.apply_rules_action_result(self.action(name))
                    self.assertEqual(s.rules_chain_candidates("p1", zone), {})
                    before = copy.deepcopy((s.players, s.battlefield, s.tokens, s.rules_engine))
                    error, _ = s.chain_rules_manifestation("p1", zone, "m3")
                    self.assertIsNotNone(error)
                    self.assertEqual((s.players, s.battlefield, s.tokens, s.rules_engine), before)

    def test_previously_queued_urocione_cannot_chain_after_a_support_play_lock(self):
        for name in ("Pin Down", "Wretched Arena"):
            with self.subTest(lock=name):
                s = self.world()
                self.put(s, "p1", "hand", ["m3"])
                host = self.field(s, self.cid(self.URO), "host")
                s.queue_rules_battlefield_entry_triggers(host["cardId"], "p1", "host", True)
                s.apply_rules_action_result(self.action(name))
                s.resolve_rules_top_action()
                self.assertIsNone(s.rules_engine["pendingChoice"])
                self.assertEqual(s.players["p1"]["zones"]["hand"], ["m3"])
                self.assertFalse(any(i.get("isChained") for i in s.battlefield))

    def test_chain_lock_only_applies_to_its_player_and_current_turn(self):
        for player, turn, blocked in (("p1", 2, True), ("p2", 2, False), ("p1", 1, False)):
            with self.subTest(player=player, turn=turn):
                s = self.world()
                self.put(s, "p1", "hand", ["m3"])
                s.rules_engine["supportLocks"] = [{"playerId": player, "turn": turn, "playOnly": True}]
                error, _ = s.chain_rules_manifestation("p1", "hand", "m3")
                self.assertEqual(error is not None, blocked)
                self.assertEqual(s.players["p1"]["zones"]["hand"], ["m3"] if blocked else [])

    def test_mind_parasite_exile_memory_survives_source_departure(self):
        s = self.world()
        self.put(s, "p1", "graveyard", ["m3"])
        host, _ = self.begin(s, "Mind Parasite")
        item, _ = self.choose(s)
        s._rules_remove_field_item(host, "p1", "hand")
        self.outcome(s)
        s.begin_rules_confrontation_cleanup()
        self.assertIsNone(s.find_battlefield_item(item["id"]))
        self.assertIn("m3", s.players["p1"]["zones"]["exile"])

    def test_help_loses_exactly_ten_even_without_a_chainable_hand(self):
        for hand in ([], ["w2"], ["m3"]):
            with self.subTest(hand=hand):
                s = self.world()
                self.put(s, "p1", "hand", hand)
                s.apply_rules_action_result(self.action("Help!"))
                self.assertEqual(s.players["p1"]["score"], 40)
                self.assertEqual(s.players["p2"]["score"], 50)
                self.assertEqual(s.rules_engine["pendingChoice"] is not None, hand == ["m3"])

    def test_help_winning_chain_is_exiled_without_exiling_the_source_will_again(self):
        s = self.world()
        will = self.cid("Help!")
        self.put(s, "p1", "hand", [will, "m3"])
        s.add_rules_excess_essence("p1", [{"temperament": "transcendent", "amount": 10}])
        s.rules_engine["priorityPlayerId"] = "p1"
        error, _ = s.declare_rules_action("p1", "Help!", kind="play_card",
            source={"cardId": will, "zone": "hand"}, ability_id="help-lose-points-then-chain")
        self.assertIsNone(error)
        s.resolve_rules_top_action()
        self.assertIn(will, s.players["p1"]["zones"]["graveyard"])
        item, _ = self.choose(s)
        self.outcome(s)
        s.begin_rules_confrontation_cleanup()
        self.assertIn("m3", s.players["p1"]["zones"]["exile"])
        self.assertNotIn(self.cid("Help!"), s.players["p1"]["zones"]["exile"])
        self.assertEqual(s.players["p1"]["zones"]["graveyard"].count(will), 1)
        self.assertEqual(s.players["p1"]["score"], 40)

    def test_looj_loss_returns_to_owner_and_scores_printed_five_for_actual_winning_opponent(self):
        for reverse_order in (False, True):
            with self.subTest(reverse_order=reverse_order):
                s = self.world()
                sprout = self.cid("Wind Sprout")
                self.put(s, "p1", "hand", [sprout])
                host, _ = self.begin(s, "Looj, Cautious Agitator")
                item, _ = self.choose(s, sprout)
                s._rules_remove_field_item(host, "p1", "graveyard")
                self.outcome(s, winner="p2")
                actions = s.queue_rules_confrontation_win_triggers(defer=True)
                self.assertEqual(len(actions), 2)
                if reverse_order:
                    actions.reverse()
                for action in actions:
                    s.rules_engine["actionStack"].append(action)
                    s.resolve_rules_top_action()
                self.assertIsNone(s.find_battlefield_item(item["id"]))
                self.assertIn(sprout, s.players["p1"]["zones"]["hand"])
                self.assertEqual((s.players["p1"]["score"], s.players["p2"]["score"]), (50, 55))

    def test_dol_can_chain_owned_cards_from_either_vessel_but_not_opponents_cards(self):
        for container in ("p1", "p2"):
            with self.subTest(container=container):
                s = self.world()
                s.put_zone_card(container, "receptacle", "m3", "p1")
                s.put_zone_card(container, "receptacle", "m4", "p2")
                self.begin(s, "Dol, the Aching")
                self.assertEqual(s.rules_engine["pendingChoice"]["_cardIds"], ["m3"])
                item, _ = self.choose(s)
                self.assertEqual((item["ownerId"], item["controllerId"]), ("p1", "p1"))
                self.assertEqual(s.players[container]["zones"]["receptacle"], ["m4"])

    def test_dol_effect_exit_returns_to_original_vessel_even_after_source_departure(self):
        for container in ("p1", "p2"):
            with self.subTest(container=container):
                s = self.world()
                s.put_zone_card(container, "receptacle", "m3", "p1")
                host, _ = self.begin(s, "Dol, the Aching")
                item, _ = self.choose(s)
                s._rules_remove_field_item(host, "p1", "hand")
                result = s._rules_remove_field_item_by_effect(item, "p1", "hand", reason="return")
                self.assertEqual((result["zone"], result["containerId"]), ("receptacle", container))
                self.assertEqual(s.players[container]["zones"]["receptacle"], ["m3"])
                self.assertNotIn("m3", s.players["p1"]["zones"]["hand"])

    def test_dol_win_exile_is_not_replaced_by_its_effect_exit_rule(self):
        s = self.world()
        s.put_zone_card("p2", "receptacle", "m3", "p1")
        self.begin(s, "Dol, the Aching")
        item, _ = self.choose(s)
        self.outcome(s)
        s.begin_rules_confrontation_cleanup()
        self.assertIsNone(s.find_battlefield_item(item["id"]))
        self.assertEqual(s.players["p1"]["zones"]["exile"], ["m3"])
        self.assertEqual(s.players["p2"]["zones"]["receptacle"], [])

    def test_dol_return_memory_survives_vessel_hand_and_a_later_field_entry(self):
        s = self.world()
        s.put_zone_card("p2", "receptacle", "m3", "p1")
        self.begin(s, "Dol, the Aching")
        item, _ = self.choose(s)
        s._rules_remove_field_item_by_effect(item, "p1", "hand", reason="return")
        self.assertIsNotNone(s.take_zone_card("p2", "receptacle", "m3"))
        s.put_zone_card("p1", "hand", "m3", "p1")
        self.assertIsNone(s.chain_rules_manifestation("p1", "hand", "m3")[0])
        returned = next(i for i in s.battlefield if i["cardId"] == "m3")
        result = s._rules_remove_field_item_by_effect(returned, "p1", "graveyard", reason="destroy")
        self.assertEqual((result["zone"], result["containerId"]), ("receptacle", "p2"))
        self.assertEqual(s.players["p2"]["zones"]["receptacle"], ["m3"])
        self.assertNotIn("m3", s.players["p1"]["zones"]["graveyard"])

    def test_dol_return_memory_is_not_a_modifier_removed_by_cleanse(self):
        s = self.world()
        s.put_zone_card("p2", "receptacle", "m3", "p1")
        self.begin(s, "Dol, the Aching")
        item, _ = self.choose(s)
        s.apply_rules_action_result(self.action("Cleanse", targets=[self.target(item)]))
        result = s._rules_remove_field_item_by_effect(item, "p1", "graveyard", reason="destroy")
        self.assertEqual((result["zone"], result["containerId"]), ("receptacle", "p2"))

    def test_dol_return_memory_is_forgotten_at_deck_or_exile(self):
        for zone in ("deck", "exile"):
            with self.subTest(zone=zone):
                s = self.world()
                s.put_zone_card("p2", "receptacle", "m3", "p1")
                self.begin(s, "Dol, the Aching")
                item, _ = self.choose(s)
                # Rule movement, not an effect: Dol does not replace it.
                s._rules_remove_field_item(item, "p1", zone)
                s.take_zone_card("p1", zone, "m3")
                s.put_zone_card("p1", "hand", "m3", "p1")
                self.assertIsNone(s.chain_rules_manifestation("p1", "hand", "m3")[0])
                returned = next(i for i in s.battlefield if i["cardId"] == "m3")
                result = s._rules_remove_field_item_by_effect(returned, "p1", "graveyard", reason="destroy")
                self.assertEqual((result["zone"], result["containerId"]), ("graveyard", "p1"))

    def test_dol_return_memory_does_not_apply_to_another_copy_on_field(self):
        s = self.world()
        s.put_zone_card("p2", "receptacle", "m3", "p1")
        self.begin(s, "Dol, the Aching")
        first, _ = self.choose(s)
        self.put(s, "p1", "hand", ["m3"])
        self.assertIsNone(s.chain_rules_manifestation("p1", "hand", "m3")[0])
        second = next(i for i in s.battlefield if i["cardId"] == "m3" and i["id"] != first["id"])
        result = s._rules_remove_field_item_by_effect(second, "p1", "graveyard", reason="destroy")
        self.assertEqual((result["zone"], result["containerId"]), ("graveyard", "p1"))
        self.assertIsNotNone(s.find_battlefield_item(first["id"]))


if __name__ == "__main__":
    unittest.main()
