"""Independent printed-text oracles for Inner Deserts, not registry assertions.

The expected numbers/permissions below are authored from English card text.
Failures deliberately expose semantic discrepancies for the owning fix pass.
"""
import copy
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import card_scenario_batches as batches
import test_game_state as game_tests


class InnerDesertsSemanticTests(game_tests.RealCardRulesCase):
    ALL = tuple(f"inner-deserts-{number:03}" for number in range(1, 151))

    def fixture(self, number, result_kind=None):
        cid = f"inner-deserts-{number:03}"
        abilities = batches.main.CARD_ABILITIES[cid]
        ability = next((entry for entry in abilities
                        if (entry.get("result") or {}).get("kind") == result_kind), abilities[0])
        session, actor, source, targets, _ = batches.prepare_action(cid, ability)
        action = {"id": "semantic-oracle", "controllerId": actor,
                  "kind": "triggered_effect", "source": source,
                  "targets": targets, "ability": copy.deepcopy(ability)}
        return session, actor, session.find_battlefield_item(source.get("itemId")), action

    @staticmethod
    def target(item):
        return {"kind": "card", "itemId": item["id"], "cardId": item.get("cardId"),
                "ownerId": item["ownerId"]}

    def test_manymaws_may_sacrifice_itself(self):
        session, actor, host, action = self.fixture(53)
        action["targets"] = [self.target(host)]
        error = session.rules_ability_targets_error(
            action["ability"]["targets"], action["targets"], actor,
            source_item_id=host["id"], event_item_id=host["id"])
        self.assertIsNone(error, "Manymaws does not say another Manifestation")
        session.apply_rules_action_result(action)
        self.assertIsNone(session.find_battlefield_item(host["id"]))
        self.assertIn("inner-deserts-053", session.players[actor]["zones"]["graveyard"])

    def test_lilitha_may_destroy_itself_and_create_two_tokens(self):
        session, actor, host, action = self.fixture(113, "destroy_target_tokens_for_controller")
        action["targets"] = [self.target(host)]
        error = session.rules_ability_targets_error(
            action["ability"]["targets"], action["targets"], actor,
            source_item_id=host["id"], event_item_id=host["id"])
        self.assertIsNone(error, "Lilitha's text does not exclude Lilitha")
        outcome = session.apply_rules_action_result(action)
        self.assertEqual(outcome["tokens"], 2)
        self.assertIsNone(session.find_battlefield_item(host["id"]))

    def test_donmo_cannot_restore_two_cards_of_the_same_temperament(self):
        session, actor, host, action = self.fixture(121, "restore_exhausted_targets")
        targets = []
        for index in range(2):
            item = self.field_item(f"same-{index}", actor, "own-man", rotation=90)
            session.battlefield.append(item)
            targets.append(self.target(item))
        error, _ = session.rules_action_ability(actor, "activated_effect", action["source"],
                                               action["ability"]["id"], targets)
        self.assertIsNotNone(error, "one target per Temperament forbids two Phlegmatic targets")

    def test_donmo_cannot_restore_itself(self):
        session, actor, host, action = self.fixture(121, "restore_exhausted_targets")
        host["rotation"] = 90
        error, _ = session.rules_action_ability(actor, "activated_effect", action["source"],
                                               action["ability"]["id"], [self.target(host)])
        self.assertIsNotNone(error, "Donmo explicitly says other than Donmo")

    def test_thoughtcutter_counts_cards_but_not_activated_effects(self):
        session, actor, host, action = self.fixture(86)
        session.rules_engine["actionStack"] = [
            {"id": "opponent-effect", "kind": "activated_effect", "controllerId": "p2",
             "source": {"cardId": "own-man", "zone": "battlefield"}},
            {"id": "opponent-card", "kind": "play_card", "sourceOnStack": True,
             "controllerId": "p2", "source": {"cardId": "scenario-will", "zone": "hand"}},
        ]
        before = session.rules_manifestation_characteristics(host)["power"]
        outcome = session.apply_rules_action_result(action)
        self.assertEqual(outcome["value"], 1)
        self.assertEqual(session.rules_manifestation_characteristics(host)["power"], before + 1)

    def test_wall_off_can_protect_an_ephemeral_will_on_the_stack(self):
        session, actor, host, action = self.fixture(146)
        session.card_rules["ephemeral-on-stack"] = {"type": "ephemeral_will"}
        session.rules_engine["actionStack"] = [{
            "id": "spell", "kind": "play_card", "sourceOnStack": True,
            "controllerId": "p2", "source": {"cardId": "ephemeral-on-stack", "zone": "hand"},
        }]
        error = session.rules_ability_targets_error(action["ability"]["targets"],
            [{"kind": "stack_action", "actionId": "spell"}], actor)
        self.assertIsNone(error, "a target card on the Stack includes an Ephemeral Will")

    def test_quper_actual_sacrifice_gives_two_power(self):
        session, p1, _ = self.make_session()
        ally = self.field_item("ally", "p1", "m-0")
        quper = self.field_item("quper", "p1", "inner-deserts-004", counters={"power": 3})
        session.battlefield = [ally, quper]
        session.resolve_rules_state_actions()
        self.assertIsNone(session.find_battlefield_item("quper"))
        self.assertEqual(session.rules_manifestation_characteristics(ally)["power"], 3)

    def test_linoleus_other_manifestation_excludes_linoleus(self):
        session, actor, host, action = self.fixture(16)
        error = session.rules_ability_targets_error(action["ability"]["targets"],
            [self.target(host)], actor, source_item_id=host["id"])
        self.assertIsNotNone(error, "another Manifestation excludes Linoleus itself")

    def test_punitive_tripod_sets_one_without_an_unprinted_maximum(self):
        session, actor, host, action = self.fixture(103, "set_interzone_power")
        ally = self.field_item("tripod-ally", actor, "own-man", "interzone")
        session.battlefield.append(ally)
        session.apply_rules_action_result(action)
        self.assertEqual(session.rules_manifestation_characteristics(ally)["power"], 1)
        session.adjust_rules_power_counter(ally, 2)
        self.assertEqual(session.rules_manifestation_characteristics(ally)["power"], 3,
                         "becomes 1 does not also say maximum 1")

    def test_caress_cannot_select_cards_from_two_limbos(self):
        session, actor, host, action = self.fixture(24)
        targets = []
        for owner in ("p1", "p2"):
            cid = f"caress-{owner}"
            session.card_rules[cid] = {"type": "manifestation", "power": 1}
            session.put_zone_card(owner, "graveyard", cid, owner)
            targets.append({"kind": "zone_card", "zone": "graveyard", "containerId": owner,
                            "ownerId": owner, "cardId": cid})
        error = session.rules_ability_targets_error(action["ability"]["targets"], targets, actor)
        self.assertIsNotNone(error, "Caress targets cards in a single player's Limbo")

    def test_gobres_in_confrontation_does_not_trigger_before_revelation(self):
        session, _, _ = self.make_session()
        gobres = self.field_item("gobres", "p1", "inner-deserts-088")
        session.battlefield = [gobres]
        session.put_zone_card("p2", "hand", "inner-deserts-043", "p2")
        queued = session.queue_rules_before_revelation_triggers(defer=True)
        self.assertEqual(queued, [], "Gobres must be in the Interzone")

    def test_jodorosk_three_correct_will_remains_visible_on_field(self):
        session, actor, host, action = self.fixture(126)
        session.card_rules["guess-manifestation"] = {
            "type": "manifestation", "power": 2, "temperaments": ["phlegmatic"]}
        self.put(session.players["p2"], "deck", ["guess-manifestation"])
        self.put(session.players[actor], "deck", ["inner-deserts-043"])
        action["targets"] = [{"kind": "player", "playerId": "p2"}]
        session.apply_rules_action_result(action)
        choice = session.rules_engine["pendingChoice"]
        error, result = session.resolve_rules_choice(actor, choice["id"],
            option={"type": "manifestation", "temperament": "phlegmatic", "value": 2})
        self.assertIsNone(error)
        self.assertEqual(result["correct"], 3)
        self.assertEqual(result["scoreDelta"], 30)
        self.assertNotIn("inner-deserts-043", session.players[actor]["zones"]["hand"])
        revealed = [item for item in session.battlefield if item.get("cardId") == "inner-deserts-043"]
        self.assertEqual(len(revealed), 1)
        self.assertTrue(revealed[0]["faceUp"])

    def test_induce_desertion_requires_two_different_manifestations(self):
        session, actor, host, action = self.fixture(148)
        support = self.field_item("same-support", actor, "own-man", isSupport=True)
        session.battlefield.append(support)
        error = session.rules_ability_targets_error(action["ability"]["targets"],
            [self.target(support), self.target(support)], actor)
        self.assertIsNotNone(error, "another target Manifestation cannot be the first target itself")

    def test_timidette_must_keep_one_opposing_support_if_available(self):
        session, actor, host, action = self.fixture(41)
        self.assertTrue(any(item.get("isSupport") and session.rules_item_controller_id(item) != actor
                            for item in session.battlefield))
        error = session.rules_ability_targets_error(action["ability"]["targets"], [], actor,
                                                   source_item_id=host["id"])
        self.assertIsNotNone(error, "choose a target under each opponent's control is mandatory if possible")

    def test_referen_doom_has_no_arbitrary_twenty_target_limit(self):
        session, actor, host, action = self.fixture(38, "exile_limbo_wills_add_power_each")
        host["counters"] = {}
        targets = []
        for index in range(21):
            cid = f"limbo-will-{index}"
            session.card_rules[cid] = {"type": "ephemeral_will", "cost": 1}
            session.put_zone_card(actor, "graveyard", cid, actor)
            targets.append({"kind": "zone_card", "containerId": actor, "zone": "graveyard",
                            "ownerId": actor, "cardId": cid})
        error = session.rules_ability_targets_error(action["ability"]["targets"], targets, actor)
        self.assertIsNone(error, "any number is not limited to twenty")
        action["targets"] = targets
        result = session.apply_rules_action_result(action)
        self.assertEqual(len(result["cardIds"]), 21)
        self.assertEqual(session.rules_manifestation_characteristics(host)["power"], 23)

    def test_pescojolero_can_choose_seven_stalemate_manifestations(self):
        session, actor, host, action = self.fixture(90)
        targets = []
        for index in range(7):
            item = self.field_item(f"stalemate-{index}", actor, "own-man", "stalemate")
            session.battlefield.append(item)
            targets.append(self.target(item))
        error = session.rules_ability_targets_error(action["ability"]["targets"], targets, actor)
        self.assertIsNone(error, "one or more is not limited to six")

    def test_nameless_arcane_uses_bob_replacement_without_unearned_essence(self):
        session, actor, host, action = self.fixture(59)
        ally = self.field_item("arcane-ally", actor, "own-man")
        bob = self.field_item("bob", "p2", "inner-deserts-134", counters={"power": 3})
        session.card_rules["inner-deserts-134"] = copy.deepcopy(batches.main.CARD_RULES["inner-deserts-134"])
        session.battlefield = [host, ally, bob]
        result = session.apply_rules_action_result(action)
        self.assertEqual(result["essences"], 0)
        self.assertTrue(any(entry["cardId"] == "own-man"
                            for entry in session.rules_engine["suspendedCards"]))

    def test_rah_kio_does_not_destroy_tokens_in_stalemate(self):
        session, actor, host, action = self.fixture(109)
        token = session.create_rules_token_copy(None, actor, generic_power=1,
                                                generic_temperament="hollow")
        token["fieldZone"] = "stalemate"
        token["isSupport"] = False
        result = session.apply_rules_action_result(action)
        self.assertIsNotNone(session.find_battlefield_item(token["id"]),
                             "Stalemate is not on the field")

    def test_splendor_with_no_gems_is_exiled_without_activation(self):
        session, _, _ = self.make_session()
        splendor = self.field_item("splendor", "p1", "inner-deserts-143", "field",
                                   chosenTemperament="vitreous")
        session.battlefield = [splendor]
        session.resolve_rules_state_actions()
        self.assertIsNone(session.find_battlefield_item("splendor"),
                          "zero Gems condition applies even when last counter did not pay Essence")
        self.assertIn("inner-deserts-143", session.players["p1"]["zones"]["exile"])

    def test_nghoulong_free_permission_is_bound_to_the_targeted_will(self):
        session, actor, host, action = self.fixture(55)
        session.battlefield.remove(host)
        session.put_zone_card(actor, "graveyard", "inner-deserts-055", actor)
        for cid in ("chosen-will", "other-will"):
            session.card_rules[cid] = {"type": "ephemeral_will", "cost": 2}
            session.put_zone_card(actor, "graveyard", cid, actor)
        action["targets"] = [{"kind": "zone_card", "zone": "graveyard", "containerId": actor,
                              "ownerId": actor, "cardId": "chosen-will"}]
        session.apply_rules_action_result(action)
        permissions = session.rules_engine["playPermissions"]
        self.assertEqual(len(permissions), 1)
        self.assertEqual(permissions[0].get("cardId"), "chosen-will",
                         "permission must remain attached to the targeted Will")

    def test_chabak_returns_opponent_cards_in_their_owners_chosen_order(self):
        session, actor, host, action = self.fixture(84, "chabak_wins")
        session.battlefield = [host]
        for index in range(2):
            session.battlefield.append(self.field_item(f"chabak-other-{index}", "p2", f"m-{index}"))
            session.card_rules[f"m-{index}"] = {"type": "manifestation", "power": 2}
        session.apply_rules_action_result(action)
        choice = session.rules_engine.get("pendingChoice")
        self.assertIsNotNone(choice, "two cards returning to one Deck require an owner order choice")
        self.assertEqual(choice["playerId"], "p2")

    def test_literal_tribute_overrides_and_interzone_permissions(self):
        # These literal costs come from the card faces, not tributePowerOverride.
        for number, expected in ((3, 4), (6, 2), (30, 2), (54, 2), (78, 2), (102, 2)):
            with self.subTest(card=number):
                session, _, _ = self.make_session()
                metadata = session.card_rules[f"inner-deserts-{number:03}"]
                override = session.rules_tribute_power_override("p1", metadata)
                self.assertEqual(override, expected)
        for number in (1, 6, 25, 30, 49, 54, 73, 78, 97, 102):
            with self.subTest(interzoneTribute=number):
                session, _, _ = self.make_session()
                self.assertTrue(session.card_rules[f"inner-deserts-{number:03}"]["canPayTributeFromInterzone"])

    def test_cannot_be_first_and_never_tribute_are_independent_restrictions(self):
        session, _, _ = self.make_session()
        for number in (2, 5, 11, 17, 26, 31, 41, 51, 53, 65, 75, 76, 79, 89, 111, 113, 122, 127):
            with self.subTest(notFirst=number):
                self.assertFalse(session.rules_card_can_be_first_manifestation(f"inner-deserts-{number:03}"))
        for number in (62, 106, 121):
            with self.subTest(noTribute=number):
                self.assertFalse(session.card_rules[f"inner-deserts-{number:03}"]["canPayTribute"])

    def test_buuz_ippokridal_and_pidue_each_create_one_correct_colored_token(self):
        for number, ability_id, temperament in (
            (2, "create-phlegmatic-support-token-on-entry", "phlegmatic"),
            (40, "create-vitreous-support-token-on-reaction-will", "vitreous"),
            (129, "pidue-phlegmatic-token", "phlegmatic"),
        ):
            with self.subTest(card=number):
                session, actor, host, action = self.fixture(number, "create_support_token")
                action["ability"] = self.ability(f"inner-deserts-{number:03}", ability_id)
                before = len(session.battlefield)
                result = session.apply_rules_action_result(action)
                token = session.find_battlefield_item(result["createdItemId"])
                self.assertEqual(len(session.battlefield), before + 1)
                self.assertEqual(session.rules_manifestation_characteristics(token)["power"], 1)
                self.assertEqual(session.rules_manifestation_characteristics(token)["temperament"], temperament)
                self.assertTrue(token["isSupport"])

    def test_literal_entry_counters(self):
        for number, counter, expected in ((18, "Flower", 2), (45, "Abstraction", 3),
                                          (67, "Bone", 3), (93, "Enigma", 1),
                                          (114, "Banner", 1), (142, "Berry", 5)):
            with self.subTest(card=number):
                session, actor, host, action = self.fixture(number, "add_counter_source")
                host["counters"] = {}
                session.apply_rules_action_result(action)
                self.assertEqual(host["counters"], {counter: expected})

    def test_ozzit_odd_even_six_exact_die_branches(self):
        for roll in range(1, 7):
            with self.subTest(roll=roll):
                session, actor, host, action = self.fixture(75)
                with patch("game.effects.dice.random.randint", return_value=roll):
                    result = session.apply_rules_action_result(action)
                self.assertEqual(result["roll"], roll)
                self.assertEqual(session.rules_field_zone(host), "stalemate" if roll % 2 else "confrontation")

    def test_zozok_six_exact_rounding_branches_and_retention(self):
        for roll, expected in ((1, 1), (2, 1), (3, 2), (4, 2), (5, 3), (6, 3)):
            with self.subTest(roll=roll):
                session, actor, host, action = self.fixture(130)
                session.tokens = []
                with patch("game.effects.dice.random.randint", return_value=roll):
                    result = session.apply_rules_action_result(action)
                self.assertEqual(result["essences"], expected)
                self.assertEqual(sum(token["counters"]["essence"] for token in session.tokens), expected)
                session.expire_rules_excess_essence(session.phase_tracker["turn"])
                self.assertEqual(sum(token["counters"]["essence"] for token in session.tokens), expected)

    def test_pillarpede_even_odd_counts_all_even_all_odd_and_mixed(self):
        for rolls, power, discarded in (((2, 4, 6, 2, 4), 7, 0),
                                         ((1, 3, 5, 1, 3), 2, 5),
                                         ((1, 2, 3, 4, 6), 5, 2)):
            with self.subTest(rolls=rolls):
                session, actor, host, action = self.fixture(128)
                session.players[actor]["zones"]["hand"] = [f"discard-{index}" for index in range(5)]
                host["counters"] = {}
                with patch("game.effects.dice.random.randint", side_effect=rolls):
                    result = session.apply_rules_action_result(action)
                self.assertEqual(session.rules_manifestation_characteristics(host)["power"], power)
                choice = session.rules_engine.get("pendingChoice")
                self.assertEqual(choice["count"] if choice else 0, discarded)

    def test_kelona_exact_capped_limbo_curve_and_zone_condition(self):
        for count, expected in ((0, 7), (1, 6), (5, 2), (6, 1), (9, 1)):
            with self.subTest(limbo=count):
                session, _, _ = self.make_session()
                kelona = self.field_item("kelona", "p1", "inner-deserts-106")
                session.battlefield = [kelona]
                session.players["p1"]["zones"]["graveyard"] = [f"limbo-{index}" for index in range(count)]
                self.assertEqual(session.rules_manifestation_characteristics(kelona)["power"], expected)
                kelona["fieldZone"] = "interzone"
                self.assertEqual(session.rules_manifestation_characteristics(kelona)["power"], 7)

    def test_kazadur_exact_opposing_manifestation_bonus_cap(self):
        for count, expected in ((0, 4), (1, 5), (2, 6), (3, 7), (5, 7)):
            with self.subTest(opposing=count):
                session, _, _ = self.make_session()
                kazadur = self.field_item("kazadur", "p1", "inner-deserts-112")
                session.battlefield = [kazadur] + [self.field_item(f"opponent-{index}", "p2", "m-0")
                                                    for index in range(count)]
                self.assertEqual(session.rules_manifestation_characteristics(kazadur)["power"], expected)

    def test_healing_bond_strict_lower_base_and_tied_base(self):
        for bases, expected_scores, expected_powers in (((2, 4), (10, 0), (4, 4)),
                                                         ((4, 4), (0, 0), (4, 4)),
                                                         ((5, 2), (0, 10), (5, 4))):
            with self.subTest(bases=bases):
                session, actor, host, action = self.fixture(20)
                session.battlefield = []
                session.rules_engine["firstManifestationItemIds"] = {}
                for index, owner in enumerate(("p1", "p2")):
                    cid = f"bond-{index}"
                    session.card_rules[cid] = {"type": "manifestation", "power": bases[index],
                                               "temperaments": ["phlegmatic"]}
                    item = self.field_item(cid, owner, cid)
                    session.battlefield.append(item)
                    session.rules_engine["firstManifestationItemIds"][owner] = cid
                    session.players[owner]["score"] = 0
                session.apply_rules_action_result(action)
                self.assertEqual(tuple(session.players[owner]["score"] for owner in ("p1", "p2")), expected_scores)
                self.assertEqual(tuple(session.rules_manifestation_characteristics(item)["power"]
                                       for item in session.battlefield), expected_powers)

    def test_bibi_six_win_loss_score_branches(self):
        for roll, expected in ((1, -5), (2, -5), (3, -10), (4, -10), (5, -15), (6, -15)):
            with self.subTest(roll=roll):
                session, actor, host, action = self.fixture(127, "score_controller_by_source_roll_then_exile")
                host["counters"] = {"Roll": roll}
                session.players[actor]["score"] = 0
                result = session.apply_rules_action_result(action)
                self.assertEqual(result["delta"], expected)
                self.assertEqual(session.players[actor]["score"], expected)
                self.assertIn("inner-deserts-127", session.players[actor]["zones"]["exile"])

    def test_tax_removes_retained_excess_or_exactly_five_points(self):
        session, actor, host, action = self.fixture(69)
        session.tokens = []
        for player in session.players.values():
            player["score"] = 0
        session.add_rules_excess_essence("p1", [{"temperament": "transcendent", "amount": 2, "retained": True}])
        session.apply_rules_action_result(action)
        self.assertEqual(session.players["p1"]["score"], 0)
        self.assertEqual(session.players["p2"]["score"], -5)
        self.assertFalse(any(token.get("isExcess") for token in session.tokens))
        session.apply_rules_action_result(action)
        self.assertEqual(session.players["p1"]["score"], -5)
        self.assertEqual(session.players["p2"]["score"], -10)

    def test_flower_of_evil_score_then_rainbow_essence(self):
        session, actor, host, action = self.fixture(142, "flower_of_evil_burst")
        session.tokens = []
        for player in session.players.values():
            player["score"] = 0
        session.apply_rules_action_result(action)
        self.assertEqual(session.players["p1"]["score"], 0)
        self.assertEqual(session.players["p2"]["score"], 5)
        self.assertEqual(sum(token["counters"]["essence"] for token in session.tokens
                              if token.get("ownerId") == actor and token.get("temperament") == "transcendent"), 1)

    def test_dissolve_zero_one_two_successful_targets_give_zero_thirty_sixty(self):
        for count, expected in ((0, 0), (1, 30), (2, 60)):
            with self.subTest(count=count):
                session, actor, host, action = self.fixture(19)
                session.players[actor]["score"] = 0
                action["targets"] = []
                for index in range(count):
                    cid = f"dissolve-{index}"
                    session.card_rules[cid] = {"type": "manifestation", "power": 2}
                    session.put_zone_card(actor, "receptacle", cid, "p2")
                    action["targets"].append({"kind": "zone_card", "containerId": actor,
                        "zone": "receptacle", "cardId": cid, "ownerId": "p2"})
                result = session.apply_rules_action_result(action)
                self.assertEqual(session.players[actor]["score"], expected)
                for index in range(count):
                    self.assertIn(f"dissolve-{index}", session.players["p2"]["zones"]["deck"])

    def test_entry_power_bonuses_have_exact_magnitudes(self):
        for number, ability_id, expected in ((79, "gain-power-through-resolution-on-entry", 3),
                                             (101, "fasces-fly-enters-confrontation", 5),
                                             (103, "punitive-tripod-gains-power-entering-confrontation", 4)):
            with self.subTest(card=number):
                session, actor, host, action = self.fixture(number)
                host["counters"] = {}
                ability = self.ability(f"inner-deserts-{number:03}", ability_id)
                action["ability"] = copy.deepcopy(ability)
                session.apply_rules_action_result(action)
                session.create_rules_ongoing_effects(action)
                self.assertEqual(session.rules_manifestation_characteristics(host)["power"], expected)

    def test_jodorosk_zero_one_two_correct_nonwill_branches(self):
        for guess, correct, score, draw_count in (
            ({"type": "will", "temperament": "choleric", "value": 3}, 0, 0, 0),
            ({"type": "manifestation", "temperament": "choleric", "value": 3}, 1, 10, 0),
            ({"type": "manifestation", "temperament": "phlegmatic", "value": 3}, 2, 20, 2),
        ):
            with self.subTest(correct=correct):
                session, actor, host, action = self.fixture(126)
                session.card_rules["guess-man"] = {"type": "manifestation", "power": 2,
                                                    "temperaments": ["phlegmatic"]}
                self.put(session.players["p2"], "deck", ["guess-man"])
                self.put(session.players[actor], "deck", ["own-man", "own-man-2", "hand-will"])
                action["targets"] = [{"kind": "player", "playerId": "p2"}]
                before = len(session.players[actor]["zones"]["hand"])
                session.apply_rules_action_result(action)
                choice = session.rules_engine["pendingChoice"]
                error, result = session.resolve_rules_choice(actor, choice["id"], option=guess)
                self.assertIsNone(error)
                self.assertEqual(result["correct"], correct)
                self.assertEqual(result["scoreDelta"], score)
                self.assertEqual(len(session.players[actor]["zones"]["hand"]) - before, draw_count)
                self.assertEqual(session.players["p2"]["zones"]["deck"], ["guess-man"])

    def test_pontificate_reshuffles_before_drawing_four_for_both_players(self):
        session, actor, host, action = self.fixture(94)
        for owner in ("p1", "p2"):
            self.put(session.players[owner], "hand", [f"{owner}-h-{index}" for index in range(3)])
            self.put(session.players[owner], "deck", [f"{owner}-d-{index}" for index in range(5)])
        session.apply_rules_action_result(action)
        for owner in ("p1", "p2"):
            self.assertEqual(len(session.players[owner]["zones"]["hand"]), 4)
            self.assertEqual(len(session.players[owner]["zones"]["deck"]), 4)
            self.assertEqual(len(set(session.players[owner]["zones"]["hand"] +
                                     session.players[owner]["zones"]["deck"])), 8)

    def test_extinguish_exiles_both_limbos_including_wills(self):
        session, actor, host, action = self.fixture(115)
        for owner in ("p1", "p2"):
            self.put(session.players[owner], "graveyard", [f"{owner}-manifestation", f"{owner}-will"])
        session.apply_rules_action_result(action)
        for owner in ("p1", "p2"):
            self.assertEqual(session.players[owner]["zones"]["graveyard"], [])
            self.assertEqual(set(session.players[owner]["zones"]["exile"]),
                             {f"{owner}-manifestation", f"{owner}-will"})

    def test_float_regained_after_sever_follows_resolution_order(self):
        for removal_first in (True, False):
            with self.subTest(removalFirst=removal_first):
                session, _, _ = self.make_session()
                target = self.field_item("float-target", "p1", "m-0", "interzone")
                session.battlefield = [target]
                grant = {"id": "grant", "controllerId": "p1", "kind": "play_card",
                    "source": {"cardId": "inner-deserts-147", "zone": "hand"},
                    "targets": [self.target(target)], "ability": self.ABILITIES["inner-deserts-147"][0]}
                remove = {"id": "remove", "controllerId": "p2", "kind": "play_card",
                    "source": {"cardId": "inner-deserts-150", "zone": "hand"},
                    "targets": [], "ability": self.ABILITIES["inner-deserts-150"][0]}
                for action in ([remove, grant] if removal_first else [grant, remove]):
                    session.create_rules_ongoing_effects(action)
                self.assertEqual(session.rules_item_has_float(target), removal_first,
                                 "the later resolved Float change wins")

    def test_denblew_counts_each_separate_opposing_draw_event(self):
        session, _, _ = self.make_session()
        host = self.field_item("denblew", "p1", "inner-deserts-026", isSupport=True)
        session.battlefield = [host]
        session.phase_tracker["index"] = game_tests.ADVANCED_PHASES.index("confrontation_reaction")
        self.put(session.players["p2"], "deck", ["m-0", "m-1", "m-2"])
        for amount in (1, 2):
            session.draw_rules_cards("p2", amount)
            queued = session.queue_rules_observed_event_triggers(defer=True)
            self.assertEqual(len(queued), 1)
            session.create_rules_ongoing_effects(queued[0])
        self.assertEqual(session.rules_manifestation_characteristics(host)["power"], 3)
        session.phase_tracker["index"] = game_tests.ADVANCED_PHASES.index("recovery_draw")
        self.put(session.players["p2"], "deck", ["m-3"])
        session.draw_rules_cards("p2", 1)
        self.assertEqual(session.queue_rules_observed_event_triggers(defer=True), [])

    def test_balance_tied_vessel_totals_do_not_redirect_points(self):
        for delta in (10, -10):
            with self.subTest(delta=delta):
                session, _, _ = self.make_session()
                session.battlefield = [self.field_item("balance", "p1", "inner-deserts-137", "field")]
                session.players["p1"]["score"] = 50
                session.players["p2"]["score"] = 50
                session.adjust_rules_score("p1", delta)
                self.assertEqual(session.players["p1"]["score"], 50 + delta)
                self.assertEqual(session.players["p2"]["score"], 50)

    def test_jesterina_chains_found_manifestation_without_discarding_it(self):
        session, actor, host, action = self.fixture(65, "chain_discarded_manifestation_from_target_deck")
        self.put(session.players["p2"], "deck", ["hand-will", "opp-man", "opp-man-2"])
        self.put(session.players["p2"], "graveyard", [])
        action["targets"] = [{"kind": "player", "playerId": "p2"}]
        result = session.apply_rules_action_result(action)
        self.assertEqual(result["status"], "chained")
        self.assertEqual(session.players["p2"]["zones"]["graveyard"], ["hand-will"])
        self.assertEqual(session.players["p2"]["zones"]["deck"], ["opp-man-2"])
        self.assertFalse(any(entry.get("cardId") == "opp-man" and entry.get("reason") == "discard"
                             for entry in session.rules_engine.get("recentLimboEntries", [])))
        chained = [item for item in session.battlefield
                   if item.get("cardId") == "opp-man" and item.get("isChained")]
        self.assertEqual(len(chained), 1)
        self.assertEqual(session.rules_item_controller_id(chained[0]), actor)

    def test_jodorosk_staged_will_can_be_played_free_once_after_next_turn(self):
        for cid, phase in (("inner-deserts-043", "confrontation_reaction"),
                           ("inner-deserts-045", "end_actions")):
            with self.subTest(will=cid):
                session, actor, host, action = self.fixture(126)
                session.card_rules["guess-man"] = {"type": "manifestation", "power": 2,
                                                    "temperaments": ["phlegmatic"]}
                self.put(session.players["p2"], "deck", ["guess-man"])
                self.put(session.players[actor], "deck", [cid])
                action["targets"] = [{"kind": "player", "playerId": "p2"}]
                session.apply_rules_action_result(action)
                choice = session.rules_engine["pendingChoice"]
                error, _ = session.resolve_rules_choice(actor, choice["id"],
                    option={"type": "manifestation", "temperament": "phlegmatic", "value": 2})
                self.assertIsNone(error)
                staged = next(item for item in session.battlefield if item.get("cardId") == cid)
                self.assertTrue(staged["faceUp"])
                self.assertFalse(session.rules_item_effects_active(staged))
                session.phase_tracker["turn"] += 1
                session.phase_tracker["index"] = game_tests.ADVANCED_PHASES.index(phase)
                session.rules_engine["priorityPlayerId"] = actor
                session.rules_engine["actionStack"] = []
                targets = [self.target(session.find_battlefield_item("own-con"))] if cid.endswith("043") else []
                ability_id = self.ABILITIES[cid][0]["id"] if cid.endswith("043") else None
                error, played = session.declare_rules_action(actor, "Play revealed Will", kind="play_card",
                    source={"cardId": cid, "itemId": staged["id"], "zone": "battlefield"},
                    targets=targets, ability_id=ability_id)
                self.assertIsNone(error)
                self.assertFalse(played["cost"]["tributePaid"])
                self.assertTrue(played["sourceOnStack"])
                self.assertIsNone(session.find_battlefield_item(staged["id"]))

    def test_nghoulong_does_not_grant_free_play_when_source_was_suspended(self):
        session, actor, host, action = self.fixture(55)
        session.put_zone_card(actor, "graveyard", "inner-deserts-055", actor)
        session.put_zone_card(actor, "graveyard", "hand-will", actor)
        action["targets"] = [{"kind": "zone_card", "containerId": actor, "zone": "graveyard",
                              "cardId": "hand-will", "ownerId": actor}]
        bob = self.field_item("bob", "p2", "inner-deserts-134", counters={"power": 3})
        session.card_rules["inner-deserts-134"] = copy.deepcopy(batches.main.CARD_RULES["inner-deserts-134"])
        session.battlefield = [bob]
        result = session.apply_rules_action_result(action)
        self.assertEqual(result["status"], "suspended")
        self.assertEqual(session.rules_engine["playPermissions"], [])

    def test_nghoulong_permission_survives_priority_pass_but_not_limbo_reentry(self):
        session, actor, host, action = self.fixture(55)
        session.battlefield.remove(host)
        session.put_zone_card(actor, "graveyard", "inner-deserts-055", actor)
        session.put_zone_card(actor, "graveyard", "hand-will", actor)
        action["targets"] = [{"kind": "zone_card", "zone": "graveyard", "containerId": actor,
                              "ownerId": actor, "cardId": "hand-will"}]
        result = session.apply_rules_action_result(action)
        self.assertEqual(result["status"], "granted")
        session.rules_engine["actionStack"] = []
        session.rules_engine["priorityPlayerId"] = actor
        error, _ = session.pass_rules_priority(actor)
        self.assertIsNone(error)
        self.assertEqual(len(session.rules_engine["playPermissions"]), 1,
                         "until end of turn does not mean until priority is passed")
        session.rules_engine["priorityPlayerId"] = actor
        source = {"cardId": "hand-will", "zone": "graveyard", "containerId": actor}
        error, _ = session.rules_action_source(actor, "play_card", source)
        self.assertIsNone(error)
        session.move_zone_card(actor, "graveyard", actor, "hand", "hand-will")
        session.move_zone_card(actor, "hand", actor, "graveyard", "hand-will")
        error, _ = session.rules_action_source(actor, "play_card", source)
        self.assertIsNotNone(error, "returning to the Limbo is a new instance, not the targeted Will")

    def test_quper_replaced_sacrifice_does_not_give_bonus(self):
        session, p1, _ = self.make_session()
        ally = self.field_item("ally", "p1", "m-0")
        quper = self.field_item("quper", "p1", "inner-deserts-004", counters={"power": 3})
        bob = self.field_item("bob", "p2", "inner-deserts-134", counters={"power": 3})
        session.battlefield = [ally, quper, bob]
        session.resolve_rules_state_actions()
        self.assertIsNone(session.find_battlefield_item("quper"))
        self.assertTrue(any(entry["cardId"] == "inner-deserts-004"
                            for entry in session.rules_engine["suspendedCards"]))
        self.assertEqual(session.rules_manifestation_characteristics(ally)["power"], 1)

    def test_drildrill_refunds_printed_cost_when_bob_replaces_destruction(self):
        # Textual interpretation, not a new creator ruling: the refund is a
        # separate instruction, without "if destroyed". Resolve that instruction
        # even when BOB replaces the preceding destruction with suspension.
        session, actor, host, action = self.fixture(131)
        hourglass_id = "lmx5uff1z53fo0g_en"
        session.card_rules[hourglass_id] = copy.deepcopy(batches.main.CARD_RULES[hourglass_id])
        session.card_rules["inner-deserts-134"] = copy.deepcopy(batches.main.CARD_RULES["inner-deserts-134"])
        hourglass = self.field_item("refund-hourglass", actor, hourglass_id, "field", controllerId="p2")
        bob = self.field_item("refund-bob", "p2", "inner-deserts-134", counters={"power": 3})
        session.battlefield = [host, hourglass, bob]
        session.tokens = []
        action["targets"] = [self.target(hourglass)]

        session.apply_rules_action_result(action)

        self.assertIsNone(session.find_battlefield_item(hourglass["id"]))
        self.assertTrue(any(entry["cardId"] == hourglass_id
                            for entry in session.rules_engine["suspendedCards"]))
        for player in session.players.values():
            self.assertNotIn(hourglass_id, player["zones"]["graveyard"])
        # Hermetic Hourglass prints {B}{B}{Y}{Y}; its current controller,
        # rather than its immutable owner, receives precisely those essences.
        refund = {}
        for token in session.tokens:
            if token.get("isEssence") and token.get("ownerId") == "p2":
                color = token["temperament"]
                refund[color] = refund.get(color, 0) + token["counters"]["essence"]
        self.assertEqual(refund, {"vitreous": 2, "capricious": 2})
        self.assertFalse(any(token.get("isEssence") and token.get("ownerId") == actor
                             for token in session.tokens))


if __name__ == "__main__":
    import unittest
    unittest.main()
