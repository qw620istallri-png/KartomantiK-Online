"""Independent printed-text clauses for Deck searches and name declarations.

Production definitions/Stack/choices are exercised; helper cards only seed zones.
Selected branches, not complete certification of these cards or the catalogue.
"""
import copy
import unittest
from unittest.mock import patch

import test_semantic_batch_001_150 as fixtures


class DeckSearchClauses(unittest.TestCase):
    cid = staticmethod(fixtures.SemanticBatch001150.cid)
    field = staticmethod(fixtures.SemanticBatch001150.field)
    put = staticmethod(fixtures.SemanticBatch001150.put)
    target = staticmethod(fixtures.SemanticBatch001150.target)
    action = fixtures.SemanticBatch001150.action
    HERMETO = "Hermeto, the Observer"
    RECALL = "Recall"
    MEJIK = "Mejik, the Labyrinther"
    POOPOM = "Poopom, the Hydromancer"

    def world(self):
        s = fixtures.SemanticBatch001150.world(self)
        s.card_labels = {c["id"]: c["name"] for c in fixtures.main.CARD_DATA}
        s.rules_engine.update(priorityPlayerId="p1", autoSkipPhases=False)
        return s

    def resolve(self, s, action):
        s.rules_engine["actionStack"].append(action)
        return s.resolve_rules_top_action()

    def search(self, s, name, player="p1"):
        self.resolve(s, self.action(name, controller=player))
        return s.rules_engine["pendingChoice"]

    def answer(self, s, cards, player="p1"):
        choice = s.rules_engine["pendingChoice"]
        error, result = s.resolve_rules_choice(player, choice["id"], card_ids=cards)
        self.assertIsNone(error)
        return result

    def snapshot(self, s):
        return copy.deepcopy((s.players, s.battlefield, s.rules_engine, s.tokens, s.revealed_hand))

    def test_hermeto_zero_one_two_selection_moves_exact_cards_then_shuffles_once(self):
        cards = [self.cid(n) for n in ("Wind Sprout", "Weaken", "Cleanse")]
        for count in (0, 1, 2):
            with self.subTest(count=count):
                s = self.world()
                self.put(s, "p1", "deck", cards)
                choice = self.search(s, self.HERMETO)
                self.assertTrue(choice["upTo"])
                self.assertEqual(s.players["p1"]["zones"]["hand"], [])
                with patch("game.choices.cards.random.shuffle") as shuffle:
                    self.answer(s, cards[:count])
                    self.assertEqual(shuffle.call_count, 1)
                self.assertCountEqual(s.players["p1"]["zones"]["hand"], cards[:count])
                self.assertCountEqual(s.players["p1"]["zones"]["deck"], cards[count:])

    def test_search_empty_deck_still_executes_final_shuffle_without_empty_choice(self):
        for name in (self.HERMETO, self.RECALL):
            with self.subTest(card=name):
                s = self.world()
                with patch("game.effects.cards.random.shuffle") as shuffle:
                    self.search(s, name)
                    self.assertEqual(shuffle.call_count, 1)
                self.assertIsNone(s.rules_engine["pendingChoice"])

    def test_search_candidates_private_but_selected_cards_are_revealed(self):
        for name in (self.HERMETO, self.RECALL):
            with self.subTest(card=name):
                s = self.world()
                chosen, hidden = self.cid("Wind Sprout"), self.cid("Weaken")
                self.put(s, "p1", "deck", [chosen, hidden])
                self.search(s, name)
                self.assertNotIn("candidateCardIds", s.serialize_for("p2", "player")["rulesEngine"]["pendingChoice"])
                result = self.answer(s, [chosen])
                self.assertEqual(s.rules_payload_for_view(result, "p2", "player").get("cardIds"), [chosen])
                hand = s.serialize_for("p2", "player")["players"]["p1"]["zones"]["hand"]
                self.assertEqual(hand.get("revealed"), [{"index": 0, "cardId": chosen}])
                self.assertNotIn("cards", hand)

    def test_search_invalid_and_opposing_answers_do_not_move_or_shuffle(self):
        for name in (self.HERMETO, self.RECALL):
            for selected, player in ((["absent"], "p1"), ([], "p2")):
                with self.subTest(card=name, cards=selected, player=player):
                    s = self.world()
                    self.put(s, "p1", "deck", [self.cid("Wind Sprout"), self.cid("Weaken")])
                    choice = self.search(s, name)
                    before = self.snapshot(s)
                    with patch("game.choices.cards.random.shuffle") as shuffle:
                        self.assertIsNotNone(s.resolve_rules_choice(player, choice["id"], card_ids=selected)[0])
                        self.assertEqual(shuffle.call_count, 0)
                    self.assertEqual(self.snapshot(s), before)

    def test_search_duplicate_or_excess_cards_are_rejected_atomically(self):
        s = self.world()
        a, b, c = [self.cid(n) for n in ("Wind Sprout", "Weaken", "Cleanse")]
        self.put(s, "p1", "deck", [a, b, c])
        choice = self.search(s, self.HERMETO)
        before = self.snapshot(s)
        for selected in ([a, a], [a, b, c]):
            with self.subTest(cards=selected):
                self.assertIsNotNone(s.resolve_rules_choice("p1", choice["id"], card_ids=selected)[0])
                self.assertEqual(self.snapshot(s), before)

    def test_search_replay_cannot_move_or_shuffle_again(self):
        s = self.world()
        card = self.cid("Wind Sprout")
        self.put(s, "p1", "deck", [card])
        choice = self.search(s, self.RECALL)
        self.answer(s, [card])
        before = self.snapshot(s)
        with patch("game.choices.cards.random.shuffle") as shuffle:
            self.assertIsNotNone(s.resolve_rules_choice("p1", choice["id"], card_ids=[card])[0])
            self.assertEqual(shuffle.call_count, 0)
        self.assertEqual(self.snapshot(s), before)

    def test_hermeto_entry_uses_immutable_owner_and_only_opponent_vessel(self):
        for owner, container, zone, expected in (("p1", "p2", "receptacle", 1),
                ("p2", "p1", "receptacle", 1), ("p1", "p1", "receptacle", 0),
                ("p1", "p2", "graveyard", 0)):
            with self.subTest(owner=owner, container=container, zone=zone):
                s = self.world()
                self.put(s, owner, "deck", [self.cid("Wind Sprout")])
                actions = s.queue_rules_zone_entry_triggers(self.cid(self.HERMETO), owner, container, zone, defer=True)
                self.assertEqual(len(actions), expected)
                if actions:
                    self.resolve(s, actions[0])
                    self.assertEqual(s.rules_engine["pendingChoice"]["playerId"], owner)

    def test_hermeto_single_card_deck_caps_the_choice_at_one(self):
        s = self.world()
        card = self.cid("Wind Sprout")
        s.put_zone_card("p1", "deck", card, "p1")
        choice = self.search(s, self.HERMETO)
        self.assertEqual(choice["count"], 1)
        self.answer(s, [card])
        self.assertEqual(s.card_owner_in_zone("p1", "hand", card), "p1")

    def test_recall_requires_current_turn_loss_before_declaration(self):
        for turn, loser, allowed in ((2, "p1", True), (1, "p1", False), (2, "p2", False)):
            with self.subTest(turn=turn, loser=loser):
                s = self.world()
                self.put(s, "p1", "hand", [self.cid(self.RECALL)])
                s.rules_engine["confrontationResult"] = {"turn": turn, "loserId": loser, "winnerId": "p2" if loser == "p1" else "p1", "stalemate": False}
                error, _ = s.declare_rules_action("p1", "Recall", kind="play_card", source={"cardId": self.cid(self.RECALL), "zone": "hand"}, ability_id="recall-searches-after-loss")
                self.assertEqual(error is None, allowed)

    def test_recall_search_requires_exactly_one_card_when_available(self):
        s = self.world()
        self.put(s, "p1", "deck", [self.cid("Wind Sprout")])
        choice = self.search(s, self.RECALL)
        before = self.snapshot(s)
        self.assertIsNotNone(s.resolve_rules_choice("p1", choice["id"], card_ids=[])[0])
        self.assertEqual(self.snapshot(s), before)

    def test_recall_real_play_resolves_before_search_and_goes_to_limbo_once(self):
        s = self.world()
        card, found = self.cid(self.RECALL), self.cid("Wind Sprout")
        self.put(s, "p1", "hand", [card])
        self.put(s, "p1", "deck", [found])
        s.rules_engine["confrontationResult"] = {"turn": 2, "loserId": "p1", "winnerId": "p2", "stalemate": False}
        error, _ = s.declare_rules_action("p1", "Recall", kind="play_card",
            source={"cardId": card, "zone": "hand"}, ability_id="recall-searches-after-loss")
        self.assertIsNone(error)
        self.assertEqual(s.players["p1"]["zones"]["hand"], [])
        self.assertEqual(s.players["p1"]["zones"]["graveyard"], [])
        self.assertIsNone(s.rules_engine["pendingChoice"])
        s.resolve_rules_top_action()
        self.assertEqual(s.players["p1"]["zones"]["graveyard"], [card])
        self.answer(s, [found])
        self.assertEqual(s.players["p1"]["zones"]["graveyard"], [card])
        self.assertEqual(s.players["p1"]["zones"]["hand"], [found])

    def mejik(self, s, target="p2"):
        source = self.field(s, self.cid(self.MEJIK), zone="interzone")
        error, result = s.declare_rules_action("p1", "Mejik", kind="activated_effect",
            source={"cardId": source["cardId"], "itemId": source["id"], "zone": "battlefield"},
            targets=[{"kind": "player", "playerId": target}], ability_id="mejik-declare-and-discard")
        self.assertIsNone(error)
        return source, result

    def name(self, s, card):
        choice = s.rules_engine["pendingChoice"]
        self.assertIsNotNone(choice, "Mejik must declare the name before passing priority")
        error, result = s.resolve_rules_choice("p1", choice["id"], option=card)
        self.assertIsNone(error)
        return result

    def test_mejik_name_and_exhaustion_are_committed_before_opponent_priority(self):
        s = self.world()
        card = self.cid("Wind Sprout")
        self.put(s, "p2", "deck", [card])
        source, _ = self.mejik(s)
        self.assertEqual(s.rules_engine["actionStack"], [])
        self.assertEqual(source["rotation"], 0)
        self.assertEqual(s.rules_engine["priorityPlayerId"], "p1")
        self.name(s, card)
        action = s.rules_engine["actionStack"][-1]
        self.assertEqual(source["rotation"], 90)
        self.assertEqual(action["cost"]["declaredCardId"], card)
        self.assertEqual(s.rules_engine["priorityPlayerId"], "p2")
        self.assertEqual(s.players["p2"]["zones"]["deck"], [card])

    def test_mejik_declared_name_resolves_once_after_source_departure(self):
        s = self.world()
        card, other = self.cid("Wind Sprout"), self.cid("Weaken")
        self.put(s, "p2", "deck", [other, card])
        source, _ = self.mejik(s)
        self.name(s, card)
        s._rules_remove_field_item(source, "p1", "graveyard")
        with patch("game.choices.cards.random.shuffle") as shuffle:
            s.resolve_rules_top_action()
            self.assertEqual(shuffle.call_count, 1)
        self.assertIsNone(s.rules_engine["pendingChoice"])
        self.assertEqual(s.players["p2"]["zones"]["deck"], [other])
        self.assertEqual(s.players["p2"]["zones"]["graveyard"], [card])

    def test_mejik_failed_search_still_shuffles_only_target_deck(self):
        for target in ("p1", "p2"):
            with self.subTest(target=target):
                s = self.world()
                self.put(s, target, "deck", [self.cid("Weaken")])
                self.mejik(s, target)
                self.name(s, self.cid("Wind Sprout"))
                with patch("game.choices.cards.random.shuffle") as shuffle:
                    s.resolve_rules_top_action()
                    self.assertEqual(shuffle.call_count, 1)
                    self.assertIs(shuffle.call_args.args[0], s.players[target]["zones"]["deck"])
                self.assertIsNone(s.rules_engine["pendingChoice"])
                self.assertEqual(s.players[target]["zones"]["graveyard"], [])

    def test_mejik_invalid_name_and_wrong_player_preserve_unpaid_declaration(self):
        s = self.world()
        self.mejik(s)
        choice = s.rules_engine["pendingChoice"]
        self.assertIsNotNone(choice)
        before = self.snapshot(s)
        for player, card in (("p1", "absent"), ("p2", self.cid("Weaken"))):
            with self.subTest(player=player, card=card):
                self.assertIsNotNone(s.resolve_rules_choice(player, choice["id"], option=card)[0])
                self.assertEqual(self.snapshot(s), before)

    def test_mejik_only_interzone_unexhausted_source_can_start_declaration(self):
        for zone, rotation in (("confrontation", 0), ("interzone", 90)):
            with self.subTest(zone=zone, rotation=rotation):
                s = self.world()
                source = self.field(s, self.cid(self.MEJIK), zone=zone)
                source["rotation"] = rotation
                before = self.snapshot(s)
                error, _ = s.declare_rules_action("p1", "Mejik", kind="activated_effect",
                    source={"cardId": source["cardId"], "itemId": source["id"], "zone": "battlefield"},
                    targets=[{"kind": "player", "playerId": "p2"}], ability_id="mejik-declare-and-discard")
                self.assertIsNotNone(error)
                self.assertEqual(self.snapshot(s), before)

    def test_mejik_pending_cost_blocks_responses_and_replay_cannot_activate_twice(self):
        s = self.world()
        self.mejik(s)
        choice_id = s.rules_engine["pendingChoice"]["id"]
        before = self.snapshot(s)
        self.assertIsNotNone(s.declare_rules_action("p2", "Response")[0])
        self.assertEqual(self.snapshot(s), before)
        self.name(s, self.cid("Wind Sprout"))
        before = self.snapshot(s)
        self.assertIsNotNone(s.resolve_rules_choice("p1", choice_id, option=self.cid("Weaken"))[0])
        self.assertEqual(self.snapshot(s), before)

    def test_concealed_search_results_remain_private(self):
        s = self.world()
        card = self.cid("Weaken")
        payload = {"kind": "search_deck", "playerId": "p1", "cardIds": [card], "concealed": True}
        self.assertNotIn("cardIds", s.rules_payload_for_view(payload, "p2", "player"))
        self.assertEqual(s.rules_payload_for_view(payload, "p1", "player")["cardIds"], [card])

    def poopom(self, s):
        source = self.field(s, self.cid(self.POOPOM))
        actions = s.queue_rules_battlefield_entry_triggers(source["cardId"], "p1", source["id"], True, defer=True)
        self.assertEqual(len(actions), 1)
        self.resolve(s, actions[0])
        return source

    def test_poopom_matching_card_stays_on_top_and_gives_exact_four_until_turn_end(self):
        s = self.world()
        card, other = self.cid("Wind Sprout"), self.cid("Weaken")
        self.put(s, "p1", "deck", [card, other])
        source = self.poopom(s)
        base = s.rules_manifestation_characteristics(source)["power"]
        self.name(s, card)
        self.assertEqual(s.rules_manifestation_characteristics(source)["power"], base + 4)
        self.assertEqual(s.players["p1"]["zones"]["deck"], [card, other])
        self.assertEqual(s.players["p1"]["zones"]["hand"], [])
        s.phase_tracker["turn"] += 1
        s.prune_rules_ongoing_effects()
        self.assertEqual(s.rules_manifestation_characteristics(source)["power"], base)

    def test_poopom_wrong_name_discards_exactly_top_card_without_drawing(self):
        s = self.world()
        top, next_card = self.cid("Weaken"), self.cid("Cleanse")
        self.put(s, "p1", "deck", [top, next_card])
        source = self.poopom(s)
        base = s.rules_manifestation_characteristics(source)["power"]
        self.name(s, self.cid("Wind Sprout"))
        self.assertEqual(s.players["p1"]["zones"]["deck"], [next_card])
        self.assertEqual(s.players["p1"]["zones"]["graveyard"], [top])
        self.assertEqual(s.players["p1"]["zones"]["hand"], [])
        self.assertEqual(s.rules_manifestation_characteristics(source)["power"], base)

    def test_poopom_name_comparison_is_by_name_not_catalogue_id(self):
        s = self.world()
        declared, top = self.cid("Wind Sprout"), "alternate-printing"
        s.card_labels[top] = "Wind Sprout"
        s.card_rules[top] = dict(s.card_rules[declared])
        self.put(s, "p1", "deck", [top])
        source = self.poopom(s)
        base = s.rules_manifestation_characteristics(source)["power"]
        self.name(s, declared)
        self.assertEqual(s.rules_manifestation_characteristics(source)["power"], base + 4)
        self.assertEqual(s.players["p1"]["zones"]["deck"], [top])

    def test_poopom_source_departure_does_not_prevent_reveal_and_discard(self):
        s = self.world()
        card = self.cid("Weaken")
        self.put(s, "p1", "deck", [card])
        source = self.poopom(s)
        s._rules_remove_field_item(source, "p1", "graveyard")
        result = self.name(s, self.cid("Wind Sprout"))
        self.assertEqual(result["revealedCardId"], card)
        self.assertIn(card, s.players["p1"]["zones"]["graveyard"])
        self.assertEqual(s.rules_engine["ongoingEffects"], [])

    def test_poopom_invalid_name_does_not_reveal_or_change_the_deck(self):
        s = self.world()
        self.put(s, "p1", "deck", [self.cid("Weaken")])
        self.poopom(s)
        choice = s.rules_engine["pendingChoice"]
        before = self.snapshot(s)
        self.assertIsNotNone(s.resolve_rules_choice("p1", choice["id"], option="absent")[0])
        self.assertEqual(self.snapshot(s), before)


if __name__ == "__main__":
    unittest.main()
