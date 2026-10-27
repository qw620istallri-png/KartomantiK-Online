"""Creator ruling: either Limbo, exactly two cards from one player's zone."""
import copy
import unittest
import test_atavic_end_clauses as fixtures


class AtavicLimboRuling(unittest.TestCase):
    world = fixtures.AtavicEndClauses.world
    host = fixtures.AtavicEndClauses.host
    offer = fixtures.AtavicEndClauses.offer
    choose = fixtures.AtavicEndClauses.choose
    cid = staticmethod(fixtures.AtavicEndClauses.cid)
    field = staticmethod(fixtures.AtavicEndClauses.field)
    put = staticmethod(fixtures.AtavicEndClauses.put)
    INTROSPECTION = "Atavic Introspection"

    def world_with_limbos(self, own=(), opponent=()):
        s = self.world()
        self.host(s, self.INTROSPECTION, "Control")
        self.put(s, "p1", "graveyard", own)
        self.put(s, "p2", "graveyard", opponent)
        return s

    @staticmethod
    def refs(player, cards):
        return [{"kind": "zone_card", "containerId": player, "zone": "graveyard", "cardId": c} for c in cards]

    def test_opponent_limbo_alone_offers_the_trigger(self):
        s = self.world_with_limbos(opponent=["m2", "w2"])
        self.offer(s)
        self.assertIsNotNone(s.rules_engine["pendingChoice"])
        self.assertEqual(s.rules_engine["pendingChoice"]["kind"], "optional_stack_action")

    def test_two_cards_in_either_single_limbo_are_legal(self):
        for player in ("p1", "p2"):
            with self.subTest(player=player):
                s = self.world_with_limbos(["m2", "w2"], ["m3", "pw3"])
                self.offer(s)
                self.choose(s, option="accept")
                cards = ["m2", "w2"] if player == "p1" else ["m3", "pw3"]
                self.choose(s, targets=self.refs(player, cards))
                action = s.rules_engine["actionStack"][-1]
                self.assertEqual({t["containerId"] for t in action["targets"]}, {player})
                self.assertEqual(s.players[player]["zones"]["graveyard"], cards)

    def test_one_card_per_limbo_is_not_an_available_pair(self):
        s = self.world_with_limbos(["m2"], ["m3"])
        self.offer(s)
        self.assertIsNone(s.rules_engine["pendingChoice"])
        self.assertEqual(s.rules_engine["actionStack"], [])

    def test_mixed_limbo_target_submission_is_rejected_atomically(self):
        s = self.world_with_limbos(["m2", "w2"], ["m3", "pw3"])
        self.offer(s)
        self.choose(s, option="accept")
        choice = s.rules_engine["pendingChoice"]
        before = copy.deepcopy((s.players, s.rules_engine))
        error, _ = s.resolve_rules_choice("p1", choice["id"], targets=self.refs("p1", ["m2"]) + self.refs("p2", ["m3"]))
        self.assertIsNotNone(error)
        self.assertEqual((s.players, s.rules_engine), before)

    def test_single_available_limbo_does_not_force_the_other_one(self):
        s = self.world_with_limbos(["m2"], ["m3", "pw3"])
        self.offer(s)
        self.assertIsNotNone(s.rules_engine["pendingChoice"])
        self.choose(s, option="accept")
        self.choose(s, targets=self.refs("p2", ["m3", "pw3"]))
        self.assertEqual(len(s.rules_engine["actionStack"]), 1)

    def test_mixing_is_disallowed_by_target_rules_even_with_many_cards(self):
        s = self.world_with_limbos(["m2", "w2"], ["m3", "pw3"])
        ability = next(a for a in s.card_rules[self.cid(self.INTROSPECTION)]["triggeredAbilities"]
                       if a["id"] == "split-two-limbo-cards-at-end-of-turn-with-ten-controls")
        self.assertIsNotNone(s.rules_ability_targets_error(ability["targets"], self.refs("p1", ["m2"]) + self.refs("p2", ["m3"]), "p1"))

    def test_selected_cards_go_to_the_original_owners_deck_in_both_cases(self):
        for container in ("p1", "p2"):
            for reverse in (False, True):
                with self.subTest(container=container, reverse=reverse):
                    s = self.world_with_limbos(["m2", "w2"], ["m3", "pw3"])
                    self.put(s, "p1", "deck", ["m4"])
                    self.put(s, "p2", "deck", ["replay-man"])
                    cards = ["m2", "w2"] if container == "p1" else ["m3", "pw3"]
                    untouched = "p2" if container == "p1" else "p1"
                    before_other = copy.deepcopy(s.players[untouched])
                    middle = list(s.players[container]["zones"]["deck"])
                    self.offer(s)
                    self.choose(s, option="accept")
                    self.choose(s, targets=self.refs(container, cards))
                    s.resolve_rules_top_action()
                    group = s.rules_engine["pendingChoice"]["groups"][0]
                    self.assertEqual(group["playerId"], container)
                    top, bottom = reversed(cards) if reverse else cards
                    self.choose(s, option={"groups": [{"playerId": container, "top": [top], "bottom": [bottom]}]})
                    self.assertEqual(s.players[container]["zones"]["deck"], [top, *middle, bottom])
                    self.assertEqual(s.players[container]["zones"]["graveyard"], [])
                    self.assertEqual(s.players[untouched], before_other)
                    self.assertTrue(all(s.card_owner_in_zone(container, "deck", c) == container for c in cards))

    def test_changed_controller_chooses_but_does_not_receive_foreign_cards(self):
        s = self.world_with_limbos(["m2", "w2"], ["m3", "pw3"])
        s.find_battlefield_item("host")["controllerId"] = "p2"
        self.put(s, "p1", "deck", ["m4"])
        self.offer(s)
        self.assertEqual(s.rules_engine["pendingChoice"]["playerId"], "p2")
        self.choose(s, option="accept")
        self.choose(s, targets=self.refs("p1", ["m2", "w2"]))
        s.resolve_rules_top_action()
        self.assertEqual(s.rules_engine["pendingChoice"]["playerId"], "p2")
        self.choose(s, option={"groups": [{"playerId": "p1", "top": ["w2"], "bottom": ["m2"]}]})
        self.assertEqual(s.players["p1"]["zones"]["deck"], ["w2", "m4", "m2"])
        self.assertEqual(s.players["p2"]["zones"]["deck"], [])


if __name__ == "__main__":
    unittest.main()
