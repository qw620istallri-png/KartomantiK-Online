"""Selected printed clauses, with independent numeric expectations.

Real card definitions and production Stack/choice paths; helper Manifestations
only supply targets. These cases do not certify every clause interaction.
"""
import copy
import unittest

import test_semantic_batch_001_150 as fixtures


class DistributionTokenClauses(unittest.TestCase):
    cid = staticmethod(fixtures.SemanticBatch001150.cid)
    world = fixtures.SemanticBatch001150.world
    field = staticmethod(fixtures.SemanticBatch001150.field)
    target = staticmethod(fixtures.SemanticBatch001150.target)
    action = fixtures.SemanticBatch001150.action
    ECHO = "Echo of the Wilds"
    BROOD = "Stampeding Brood"

    def power(self, s, item):
        return s.rules_manifestation_characteristics(item)["power"]

    def resolve(self, s, action):
        s.rules_engine["actionStack"].append(action)
        return s.resolve_rules_top_action()

    def echo(self, s, count):
        source = self.field(s, self.cid(self.ECHO))
        items = [self.field(s, "m2", f"target-{n}", zone="interzone") for n in range(count)]
        self.resolve(s, self.action(self.ECHO, source, [self.target(i) for i in items]))
        return source, items

    def brood(self, s, owner="p1", container="p2"):
        cid = self.cid(self.BROOD)
        s.put_zone_card(container, "receptacle", cid, owner)
        actions = s.queue_rules_zone_entry_triggers(cid, owner, container, "receptacle", defer=True)
        self.assertEqual(len(actions), 1)
        self.resolve(s, actions[0])
        return s.rules_engine["pendingChoice"]

    def choose_count(self, s, count, player="p1"):
        choice = s.rules_engine["pendingChoice"]
        error, result = s.resolve_rules_choice(player, choice["id"], option=str(count))
        self.assertIsNone(error)
        return result

    def test_echo_one_target_receives_all_three_without_a_choice(self):
        s = self.world()
        _, items = self.echo(s, 1)
        self.assertEqual(self.power(s, items[0]), 5)
        self.assertIsNone(s.rules_engine["pendingChoice"])

    def test_echo_two_targets_player_chooses_which_receives_two(self):
        for extra in (0, 1):
            with self.subTest(extra=extra):
                s = self.world()
                _, items = self.echo(s, 2)
                self.assertEqual([self.power(s, i) for i in items], [2, 2])
                choice = s.rules_engine["pendingChoice"]
                self.assertEqual((choice["kind"], choice["playerId"]), ("pick_distribution_extra", "p1"))
                self.assertIsNone(s.resolve_rules_choice("p1", choice["id"], item_id=items[extra]["id"])[0])
                self.assertEqual([self.power(s, i) for i in items], [4, 3] if extra == 0 else [3, 4])

    def test_echo_three_targets_each_receive_one(self):
        s = self.world()
        _, items = self.echo(s, 3)
        self.assertEqual([self.power(s, i) for i in items], [3, 3, 3])
        self.assertIsNone(s.rules_engine["pendingChoice"])

    def test_echo_invalid_extra_target_and_wrong_player_do_not_mutate_choice(self):
        s = self.world()
        self.echo(s, 2)
        choice = s.rules_engine["pendingChoice"]
        before = copy.deepcopy((s.rules_engine, s.battlefield))
        for player, item in (("p1", "missing"), ("p2", "target-0")):
            with self.subTest(player=player, item=item):
                self.assertIsNotNone(s.resolve_rules_choice(player, choice["id"], item_id=item)[0])
                self.assertEqual((s.rules_engine, s.battlefield), before)

    def test_echo_modifier_survives_next_turn_and_source_departure(self):
        s = self.world()
        source, items = self.echo(s, 1)
        s._rules_remove_field_item(source, "p1", "graveyard")
        s.phase_tracker["turn"] += 1
        s.prune_rules_ongoing_effects()
        self.assertEqual(self.power(s, items[0]), 5)

    def test_echo_cleanse_and_field_exit_remove_the_modifier(self):
        for removal in ("cleanse", "leave"):
            with self.subTest(removal=removal):
                s = self.world()
                _, items = self.echo(s, 1)
                item = items[0]
                if removal == "cleanse":
                    self.resolve(s, self.action("Cleanse", targets=[self.target(item)]))
                else:
                    s._rules_remove_field_item(item, "p1", "graveyard")
                    s.prune_rules_ongoing_effects()
                    item = self.field(s, "m2", "new-entry", zone="interzone")
                self.assertEqual(self.power(s, item), 2)

    def test_echo_targets_require_controller_interzone_and_one_to_three_cards(self):
        s = self.world()
        source = self.field(s, self.cid(self.ECHO))
        own = self.field(s, "m2", "own", zone="interzone")
        enemy = self.field(s, "m3", "enemy", owner="p2", zone="interzone")
        cz = self.field(s, "m4", "cz")
        rules = self.action(self.ECHO, source)["ability"]["targets"]
        self.assertIsNone(s.rules_ability_targets_error(rules, [self.target(own)], "p1"))
        for targets in ([], [self.target(enemy)], [self.target(cz)], [self.target(own)] * 4):
            with self.subTest(targets=targets):
                self.assertIsNotNone(s.rules_ability_targets_error(rules, targets, "p1"))

    def test_echo_only_defeat_of_a_participant_triggers(self):
        for outcome, participant, expected in (("loss", True, 1), ("win", True, 0),
                                                ("stalemate", True, 0), ("loss", False, 0)):
            with self.subTest(outcome=outcome, participant=participant):
                s = self.world()
                source = self.field(s, self.cid(self.ECHO))
                self.field(s, "m2", "candidate", zone="interzone")
                s.rules_engine["confrontationResult"] = {
                    "turn": 2, "stalemate": outcome == "stalemate",
                    "winnerId": None if outcome == "stalemate" else "p2" if outcome == "loss" else "p1",
                    "loserId": None if outcome == "stalemate" else "p1" if outcome == "loss" else "p2",
                    "participantItemIds": [source["id"]] if participant else [],
                }
                actions = s.queue_rules_confrontation_win_triggers(defer=True)
                # Mandatory targeted loss triggers ask for targets before stacking.
                pending = s.rules_engine["pendingChoice"]
                self.assertEqual(len(actions) + int(pending is not None), expected)
                if expected:
                    self.assertEqual((pending["kind"], pending["sourceCardId"]), ("trigger_targets", source["cardId"]))

    def test_echo_loss_target_selection_enters_stack_before_power_is_applied(self):
        s = self.world()
        source = self.field(s, self.cid(self.ECHO))
        target = self.field(s, "m2", "candidate", zone="interzone")
        s.rules_engine["confrontationResult"] = {
            "turn": 2, "winnerId": "p2", "loserId": "p1", "stalemate": False,
            "participantItemIds": [source["id"]],
        }
        s.queue_rules_confrontation_win_triggers()
        choice = s.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "trigger_targets")
        self.assertIsNone(s.resolve_rules_choice("p1", choice["id"], targets=[self.target(target)])[0])
        self.assertEqual(len(s.rules_engine["actionStack"]), 1)
        self.assertEqual(self.power(s, target), 2)
        s.resolve_rules_top_action()
        self.assertEqual(self.power(s, target), 5)

    def test_echo_no_legal_interzone_target_does_not_request_a_choice(self):
        s = self.world()
        source = self.field(s, self.cid(self.ECHO))
        self.field(s, "m2", "enemy", owner="p2", zone="interzone")
        s.rules_engine["confrontationResult"] = {
            "turn": 2, "winnerId": "p2", "loserId": "p1", "stalemate": False,
            "participantItemIds": [source["id"]],
        }
        self.assertEqual(s.queue_rules_confrontation_win_triggers(), [])
        self.assertIsNone(s.rules_engine["pendingChoice"])
        self.assertEqual(s.rules_engine["actionStack"], [])

    def test_echo_disappeared_target_does_not_receive_a_modifier(self):
        s = self.world()
        source = self.field(s, self.cid(self.ECHO))
        target = self.field(s, "m2", "candidate", zone="interzone")
        action = self.action(self.ECHO, source, [self.target(target)])
        s._rules_remove_field_item(target, "p1", "graveyard")
        self.resolve(s, action)
        self.assertEqual(s.rules_engine["ongoingEffects"], [])
        self.assertIsNone(s.rules_engine["pendingChoice"])

    def test_brood_zero_one_two_are_real_choices_with_exact_characteristics(self):
        for count in (0, 1, 2):
            with self.subTest(count=count):
                s = self.world()
                choice = self.brood(s)
                self.assertEqual((choice["kind"], choice["options"]), ("token_count", ["0", "1", "2"]))
                self.assertEqual(s.battlefield, [])
                self.choose_count(s, count)
                self.assertEqual(len(s.battlefield), count)
                for token in s.battlefield:
                    self.assertEqual((token["ownerId"], token["controllerId"], token["fieldZone"]), ("p1", "p1", "interzone"))
                    self.assertTrue(token["isTokenCard"] and token["isSupport"] and token["permanent"])
                    self.assertEqual((self.power(s, token), s.rules_manifestation_characteristics(token)["temperament"]), (1, "phlegmatic"))
                self.assertIn(self.cid(self.BROOD), s.players["p2"]["zones"]["receptacle"])

    def test_brood_available_spaces_limit_choice_without_overflow(self):
        for occupied, options in ((1, ["0", "1", "2"]), (2, ["0", "1"]), (3, None)):
            with self.subTest(occupied=occupied):
                s = self.world()
                for n in range(occupied):
                    self.field(s, "m2", f"existing-{n}", zone="interzone")
                choice = self.brood(s)
                if options is None:
                    self.assertIsNone(choice)
                else:
                    self.assertEqual(choice["options"], options)
                    self.choose_count(s, options[-1])
                self.assertEqual(s.rules_interzone_slot_count("p1"), 3)

    def test_brood_invalid_count_and_wrong_player_leave_state_unchanged(self):
        s = self.world()
        choice = self.brood(s)
        before = copy.deepcopy((s.rules_engine, s.battlefield, s.players))
        for player, option in (("p1", "3"), ("p1", "-1"), ("p2", "1")):
            with self.subTest(player=player, option=option):
                self.assertIsNotNone(s.resolve_rules_choice(player, choice["id"], option=option)[0])
                self.assertEqual((s.rules_engine, s.battlefield, s.players), before)

    def test_brood_tokens_belong_to_owner_not_vessel_container(self):
        s = self.world()
        choice = self.brood(s, owner="p2", container="p1")
        self.assertEqual(choice["playerId"], "p2")
        self.choose_count(s, 2, player="p2")
        self.assertEqual([i["controllerId"] for i in s.battlefield], ["p2", "p2"])

    def test_brood_own_vessel_and_other_zones_do_not_trigger(self):
        for container, zone in (("p1", "receptacle"), ("p2", "graveyard"), ("p2", "hand")):
            with self.subTest(container=container, zone=zone):
                s = self.world()
                self.assertEqual(s.queue_rules_zone_entry_triggers(self.cid(self.BROOD), "p1", container, zone, defer=True), [])

    def test_brood_interzone_tokens_survive_resolution_and_next_turn(self):
        s = self.world()
        self.brood(s)
        self.choose_count(s, 2)
        ids = [i["id"] for i in s.battlefield]
        s.rules_engine["confrontationResult"] = {
            "turn": 2, "status": "effects", "winnerId": "p1", "loserId": "p2",
            "stalemate": False, "participantItemIds": [], "winnerItemIds": [], "loserItemIds": [],
        }
        s.begin_rules_confrontation_cleanup()
        s.phase_tracker["turn"] += 1
        s.prune_rules_ongoing_effects()
        self.assertEqual([i["id"] for i in s.battlefield], ids)
        self.assertEqual([self.power(s, i) for i in s.battlefield], [1, 1])

    def test_brood_token_choice_cannot_be_replayed(self):
        s = self.world()
        choice = self.brood(s)
        self.choose_count(s, 2)
        before = copy.deepcopy(s.battlefield)
        self.assertIsNotNone(s.resolve_rules_choice("p1", choice["id"], option="2")[0])
        self.assertEqual(s.battlefield, before)

    def test_brood_interzone_creation_does_not_bypass_support_prohibition_into_cz(self):
        s = self.world()
        s.rules_engine["supportLocks"] = [{"turn": 2, "playerId": "p1"}]
        self.brood(s)
        self.choose_count(s, 2)
        self.assertEqual([i["fieldZone"] for i in s.battlefield], ["interzone", "interzone"])
        self.assertEqual(s.rules_confrontation_items("p1", ("confrontation",)), [])


if __name__ == "__main__":
    unittest.main()
