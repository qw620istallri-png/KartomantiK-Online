"""Independent printed-text regressions for catalogue positions 151 through 300.

Expected numbers/branches below are literal interpretations of the English
catalogue and creator rulings, never copied from ability result metadata.
"""
import copy
from unittest.mock import patch

import test_game_state as game


class SemanticBatch151To300Tests(game.RealCardRulesCase):
    HOGMA = "dm0hz9sb5i737gx_en"
    TRIM = "t42gc95tma8uhzm_en"
    EQUALIZE = "qahv0guk18jyo6i_en"
    OUTCAST = "h67753m250gg2h6_en"
    KARMAPULT = "e049wxg2j24nczl_en"
    POTATO = "b4yyd5uut0ga9df_en"
    DARK = "g02zvmqx3loxlcv_en"
    JIJA = "02y2r5cvbw1mauv_en"
    RADIANCE = "yca1lsjic3cktj1_en"
    PLINIUS = "chj7vmavn3d5c4s_en"
    MUTATE = "odqcx9kkqe029se_en"
    GREED = "9phkl58pqrs2j2f_en"
    KARMA = "9d2y8uy9ut7omyo_en"
    KAOS = "b0amfkmb3xewx7x_en"
    QU_LOM = "rf5srmnqyh235tm_en"
    QUORUM = "201ug66mqu6gslx_en"
    SOLAR = "7j3udrfh5t8vl25_en"
    WEAKEN = "bithch9c4vi77cu_en"
    DAMAGE = "goxjkkrwos0lhx4_en"
    TEARS = "67009ud077sgz7b_en"
    CAULDRON = "90cwtv2us78k76w_en"
    BRABATABA = "zhzp6kenpqrym9h_en"
    NUMBI = "wer3o71zo9myece_en"
    GRUDGE = "2hszv736kwwmi7n_en"
    GLABRON = "x15xumjqqhrnrds_en"
    ZUM = "282b0n6ldnzdp0p_en"
    LOVER = "2z1svoyvo77ta03_en"
    PILLAR = "7gaov0c4cjndl9w_en"
    PIN_DOWN = "kmyzmxtakzhj58p_en"
    ARENA = "4phs0d8l223jk7t_en"
    NULLIFY = "fwh3yrkvg9n09vg_en"
    COLOSSUS = "o1b1hf2xpmkt8j2_en"
    TRAP = "xzh48oy0ramirce_en"
    JAW = "y6g3tex9ypttk8u_en"
    IGNORE = "ey6fuk5gguasrb0_en"
    ALL = (HOGMA, TRIM, EQUALIZE, OUTCAST, KARMAPULT, POTATO, DARK,
           JIJA, RADIANCE, PLINIUS, MUTATE, GREED, KARMA, KAOS, QU_LOM,
           QUORUM, SOLAR, WEAKEN, DAMAGE, TEARS, CAULDRON, BRABATABA, NUMBI,
           GRUDGE, GLABRON, ZUM, LOVER, PILLAR, PIN_DOWN, ARENA,
           NULLIFY, COLOSSUS, TRAP, JAW, IGNORE)

    def started(self):
        session, p1, p2 = self.make_session()
        session.rules_engine.update(enabled=True, readyPlayerIds=["p1", "p2"],
            firstManifestationComplete=True, priorityPlayerId="p1", autoSkipPhases=False)
        session.phase_tracker["index"] = game.ADVANCED_PHASES.index("confrontation_reaction")
        session.add_rules_excess_essence("p1", [{"temperament": "transcendent", "amount": 50}])
        session.card_rules["m-0"]["power"] = 12
        session.card_rules["m-1"]["power"] = 8
        session.battlefield = [self.field_item("mine", "p1", "m-0"),
                               self.field_item("foe", "p2", "m-1")]
        session.rules_engine["firstManifestationItemIds"] = {"p1": "mine", "p2": "foe"}
        return session, p1, p2

    @staticmethod
    def target(item):
        return {"kind": "card", "itemId": item["id"], "cardId": item.get("cardId"), "ownerId": item["ownerId"]}

    def isolated_action(self, cid, host, ability_index=0, targets=(), controller="p1"):
        return {"id": "semantic-" + cid, "kind": "triggered_effect", "controllerId": controller,
                "source": {"cardId": cid, "itemId": host["id"], "ownerId": host["ownerId"], "zone": "battlefield"},
                "targets": list(targets), "ability": copy.deepcopy(self.ABILITIES[cid][ability_index])}

    def test_hogma_silences_itself_and_own_allies_but_not_opponents(self):
        session, _p1, _p2 = self.started()
        host = self.field_item("hogma", "p1", self.HOGMA)
        session.battlefield.append(host)
        session.create_rules_ongoing_effects(self.isolated_action(self.HOGMA, host))
        self.assertFalse(session.rules_item_effects_active(host), "Printed 'all manifestations you currently control' includes Hogma")
        self.assertFalse(session.rules_item_effects_active(session.find_battlefield_item("mine")))
        self.assertTrue(session.rules_item_effects_active(session.find_battlefield_item("foe")))

    def test_trim_and_equalize_prevent_later_power_color_and_silence_modifiers(self):
        for cid, expected in ((self.TRIM, 12), (self.EQUALIZE, 8)):
            with self.subTest(card=cid):
                session, _p1, _p2 = self.started()
                mine = session.find_battlefield_item("mine")
                host = {"id": "spell", "ownerId": "p1"}
                session.apply_rules_action_result(self.isolated_action(cid, host))
                self.assertEqual(self.power_of(session, "mine"), expected)
                for modifier in ({"kind": "power_modifier", "value": -2},
                                 {"kind": "temperament_override", "temperament": "choleric"},
                                 {"kind": "lose_effects"}):
                    action = {"id": "later", "controllerId": "p2", "source": {"cardId": "will-x"},
                              "targets": [self.target(mine)],
                              "ability": {"ongoingEffect": {**modifier, "duration": "until_end_of_turn"}}}
                    session.create_rules_ongoing_effects(action)
                self.assertEqual(self.power_of(session, "mine"), expected)
                self.assertEqual(session.rules_manifestation_characteristics(mine)["temperament"], "phlegmatic")
                self.assertTrue(session.rules_item_effects_active(mine))

    def test_outcast_can_replace_a_targeted_support(self):
        session, _p1, _p2 = self.started()
        host = self.field_item("outcast", "p1", self.OUTCAST, field_zone="interzone")
        support = self.field_item("support", "p1", "m-2", isSupport=True)
        session.battlefield += [host, support]
        result = session.rules_redirect_targets("p2", [self.target(support)])
        self.assertEqual(result[0]["itemId"], "outcast")
        self.assertEqual(session.rules_field_zone(support), "interzone")
        self.assertEqual(session.rules_field_zone(host), "confrontation")
        self.assertTrue(host.get("isSupport"))

    def test_karmapult_sacrifices_as_activation_cost_and_survives_source_departure(self):
        session, p1, _p2 = self.started()
        host = self.field_item("karmapult", "p1", self.KARMAPULT, field_zone="field",
            attachedCards=[{"cardId": "m-2", "ownerId": "p1"}, {"cardId": "m-3", "ownerId": "p1"}])
        session.battlefield.append(host)
        error, _action = session.declare_rules_action("p1", "Karmapult", kind="activated_effect",
            source={"cardId": self.KARMAPULT, "itemId": host["id"], "zone": "battlefield"},
            targets=[self.target(session.find_battlefield_item("foe"))],
            ability_id="karmapult-sacrifices-for-power-loss")
        self.assertIsNone(error)
        self.assertEqual(host.get("attachedCards"), [], "Everything before the colon is paid before responses")
        self.assertTrue({"m-2", "m-3"}.issubset(p1["zones"]["graveyard"]))
        session._rules_remove_field_item(host, "p1", "exile", "top")
        session.resolve_rules_top_action()
        self.assertEqual(self.power_of(session, "foe"), 6, "Two previously sacrificed cards give -2 even after source departure")

    def test_hot_potato_end_turn_loss_survives_source_departure(self):
        session, _p1, p2 = self.started()
        p2["score"] = 100
        host = self.field_item("potato", "p1", self.POTATO, field_zone="field", controllerId="p2", counters={"Burn": 2})
        session.battlefield.append(host)
        actions = session.queue_rules_triggers(self.POTATO, "p1", "end_of_turn",
            zone="field", item_id=host["id"], controller_id="p2", defer=True)
        self.assertEqual(len(actions), 1)
        session.rules_engine["actionStack"].extend(actions)
        session._rules_remove_field_item(host, "p1", "exile", "top")
        session.resolve_rules_top_action()
        self.assertEqual(p2["score"], 60, "The captured controller still loses 40; destruction can do nothing")

    def test_buddhan_dark_win_remembers_actual_discard_count_after_departure(self):
        session, p1, p2 = self.started()
        host = self.field_item("dark", "p1", self.DARK)
        session.battlefield.append(host)
        self.put(p1, "deck", ["m-2", "m-3", "m-4", "m-5"])
        self.put(p2, "deck", ["m-6", "m-7", "m-8", "m-9"])
        with patch("game.effects.dice.random.randint", return_value=3):
            session.apply_rules_action_result(self.isolated_action(self.DARK, host))
        self.assertEqual(len(p1["zones"]["graveyard"]), 3)
        actions = session.queue_rules_triggers(self.DARK, "p1", "wins_confrontation",
            item_id=host["id"], controller_id="p1", event_controller_id="p1", defer=True)
        self.assertEqual(len(actions), 1)
        session.rules_engine["actionStack"].extend(actions)
        session._rules_remove_field_item(host, "p1", "exile", "top")
        session.resolve_rules_top_action()
        self.assertEqual(p2["zones"]["graveyard"], ["m-8", "m-7", "m-6"])
        self.assertEqual(p2["zones"]["deck"], ["m-9"])

    def test_jija_bottom_deck_placement_shuffles_but_top_does_not(self):
        for position, expected_calls in (("bottom", 1), ("top", 0)):
            with self.subTest(position=position):
                session, p1, _p2 = self.started()
                self.put(p1, "hand", [self.JIJA])
                self.put(p1, "deck", ["m-2", "m-3", "m-4"])
                with patch("game.zones.random.shuffle") as shuffle:
                    error, _owner = session.move_zone_card("p1", "hand", "p1", "deck", self.JIJA, position)
                self.assertIsNone(error)
                self.assertEqual(shuffle.call_count, expected_calls)

    def test_radiance_entry_is_one_compound_trigger(self):
        session, _p1, _p2 = self.started()
        host = self.field_item("radiance", "p1", self.RADIANCE, field_zone="field")
        session.battlefield.append(host)
        actions = session.queue_rules_triggers(self.RADIANCE, "p1", "enters_field",
            item_id=host["id"], controller_id="p1", face_up=True, defer=True)
        self.assertEqual(len(actions), 1, "Counters and color choice share the same printed When clause")

    def test_plinius_every_die_face_has_correct_lasting_sign(self):
        for roll, expected in ((1, 6), (2, 14), (3, 6), (4, 14), (5, 6), (6, 14)):
            with self.subTest(roll=roll):
                session, _p1, _p2 = self.started()
                session.card_rules[self.PLINIUS]["power"] = 10
                host = self.field_item("plinius", "p1", self.PLINIUS)
                session.battlefield.append(host)
                with patch("game.effects.dice.random.randint", return_value=roll):
                    session.apply_rules_action_result(self.isolated_action(self.PLINIUS, host))
                self.assertEqual(self.power_of(session, "plinius"), expected)
                session.phase_tracker["turn"] += 1
                session.prune_rules_ongoing_effects()
                self.assertEqual(self.power_of(session, "plinius"), expected, "No printed end-turn expiry")

    def test_mutate_every_die_face_exact_result_and_lifetime(self):
        for roll, expected, temperament in ((1, None, None), (2, None, None),
                (3, 8, "hollow"), (4, 10, "phlegmatic"),
                (5, 10, "phlegmatic"), (6, 11, "phlegmatic")):
            with self.subTest(roll=roll):
                session, _p1, p2 = self.started()
                host = {"id": "spell", "ownerId": "p1"}
                foe = session.find_battlefield_item("foe")
                with patch("game.effects.dice.random.randint", return_value=roll):
                    session.apply_rules_action_result(self.isolated_action(self.MUTATE, host, targets=[self.target(foe)]))
                if expected is None:
                    self.assertIsNone(session.find_battlefield_item("foe"))
                    self.assertIn("m-1", p2["zones"]["graveyard"])
                else:
                    self.assertEqual(session.rules_manifestation_characteristics(foe), {"power": expected, "temperament": temperament})
                    session.phase_tracker["turn"] += 1
                    session.prune_rules_ongoing_effects()
                    self.assertEqual(session.rules_manifestation_characteristics(foe), {"power": expected, "temperament": temperament})

    def test_greed_every_die_face_exact_lasting_reduction(self):
        for roll, expected in ((1, 8), (2, 8), (3, 7), (4, 7), (5, 6), (6, 6)):
            with self.subTest(roll=roll):
                session, _p1, _p2 = self.started()
                host = self.field_item("greed", "p1", self.GREED, field_zone="field")
                session.battlefield.append(host)
                foe = session.find_battlefield_item("foe")
                with patch("game.effects.dice.random.randint", return_value=roll):
                    session.apply_rules_action_result(self.isolated_action(self.GREED, host, ability_index=1, targets=[self.target(foe)]))
                self.assertEqual(self.power_of(session, "foe"), expected)
                session.phase_tracker["turn"] += 1
                session.prune_rules_ongoing_effects()
                self.assertEqual(self.power_of(session, "foe"), expected)

    def test_karma_and_kaos_roll_independently_for_both_players(self):
        for cid in (self.KARMA, self.KAOS):
            for rolls, hits in (((1, 6), 2), ((2, 5), 0), ((3, 1), 1)):
                with self.subTest(card=cid, rolls=rolls):
                    session, p1, _p2 = self.started()
                    p1["score"] = 100
                    host = self.field_item("bro", "p1", cid)
                    session.battlefield.append(host)
                    targets = [self.target(session.find_battlefield_item(i)) for i in ("mine", "foe")]
                    with patch("game.effects.dice.random.randint", side_effect=rolls):
                        session.apply_rules_action_result(self.isolated_action(cid, host, targets=targets))
                    if cid == self.KARMA:
                        self.assertEqual(p1["score"], 100 + 10 * hits)
                        self.assertIsNotNone(session.find_battlefield_item("mine"))
                        self.assertIsNotNone(session.find_battlefield_item("foe"))
                    else:
                        self.assertEqual(sum(session.find_battlefield_item(i) is None for i in ("mine", "foe")), hits)
                        self.assertIsNotNone(session.find_battlefield_item("bro"))

    def test_buddhan_dark_counts_actual_short_deck_not_die_face(self):
        session, p1, p2 = self.started()
        host = self.field_item("dark", "p1", self.DARK)
        session.card_rules[self.DARK]["power"] = 10
        session.battlefield.append(host)
        self.put(p1, "deck", ["m-2", "m-3"])
        self.put(p2, "deck", ["m-4", "m-5", "m-6", "m-7"])
        with patch("game.effects.dice.random.randint", return_value=6):
            session.apply_rules_action_result(self.isolated_action(self.DARK, host))
        self.assertEqual(self.power_of(session, "dark"), 12)
        session.apply_rules_action_result(self.isolated_action(self.DARK, host, ability_index=1))
        self.assertEqual(p2["zones"]["deck"], ["m-6", "m-7"])
        self.assertEqual(len(p2["zones"]["graveyard"]), 2)

    def test_grudge_spend_ability_does_not_inherit_previous_paragraph_zone_condition(self):
        session, _p1, _p2 = self.started()
        host = self.field_item("grudge", "p1", self.GRUDGE, counters={"Grudge": 2})
        session.battlefield.append(host)
        error, _action = session.declare_rules_action("p1", "Grudge", kind="activated_effect",
            source={"cardId": self.GRUDGE, "itemId": host["id"], "zone": "battlefield"},
            ability_id="spend-grudges-for-support", targets=[])
        self.assertIsNone(error, "Only gaining the Grudge counters is restricted to Interzone")
        self.assertEqual(host["counters"]["Grudge"], 0)

    def test_everspring_allows_zero_targets_in_up_to_three(self):
        session, _p1, _p2 = self.started()
        host = self.field_item("spring", "p1", self.TEARS, field_zone="field", counters={"Tear": 3})
        session.battlefield.append(host)
        error, _action = session.declare_rules_action("p1", "Everspring", kind="activated_effect",
            source={"cardId": self.TEARS, "itemId": host["id"], "zone": "battlefield"},
            ability_id="everspring-spend-tears-to-exile-vessel", targets=[])
        self.assertIsNone(error)
        self.assertEqual(host["counters"]["Tear"], 0, "Choosing zero does not waive the activation cost")

    def test_glabron_can_choose_itself_as_own_interzone_manifestation(self):
        session, _p1, _p2 = self.started()
        host = self.field_item("glabron", "p1", self.GLABRON, field_zone="interzone")
        session.battlefield.append(host)
        action = self.isolated_action(self.GLABRON, host, targets=[self.target(host)])
        session.apply_rules_action_result(action)
        self.assertEqual(session.rules_field_zone(host), "stalemate", "Printed own Interzone manifestation does not say another")

    def test_zum_support_gain_has_no_invented_end_turn_expiry(self):
        session, _p1, _p2 = self.started()
        host = self.field_item("zum", "p1", self.ZUM, field_zone="interzone")
        session.battlefield.append(host)
        source = {"cardId": self.ZUM, "itemId": host["id"], "zone": "battlefield"}
        # Isolate the persistent grant after five activations; the dedicated
        # action tests elsewhere cover costs and once-per-turn declaration.
        for ability in self.ABILITIES[self.ZUM]:
            session.pay_rules_activation_cost(source, copy.deepcopy(ability))
        self.assertTrue(session.rules_card_can_enter_support(host))
        session.phase_tracker["turn"] += 1
        session.prune_rules_ongoing_effects()
        self.assertTrue(session.rules_card_can_enter_support(host), "Creator ruling: no printed duration persists on field")

    def test_zum_requires_all_five_uses_in_the_same_turn(self):
        session, _p1, _p2 = self.started()
        host = self.field_item("zum", "p1", self.ZUM, field_zone="interzone")
        session.battlefield.append(host)
        source = {"cardId": self.ZUM, "itemId": host["id"], "zone": "battlefield"}
        for ability in self.ABILITIES[self.ZUM][:4]:
            session.pay_rules_activation_cost(source, copy.deepcopy(ability))
        self.assertFalse(session.rules_card_can_enter_support(host))
        session.phase_tracker["turn"] += 1
        session.pay_rules_activation_cost(source, copy.deepcopy(self.ABILITIES[self.ZUM][4]))
        self.assertFalse(session.rules_card_can_enter_support(host))

    def test_cleanse_removes_zums_permanent_support_grant(self):
        session, _p1, _p2 = self.started()
        host = self.field_item("zum", "p1", self.ZUM, field_zone="interzone")
        session.battlefield.append(host)
        source = {"cardId": self.ZUM, "itemId": host["id"], "zone": "battlefield"}
        for ability in self.ABILITIES[self.ZUM]:
            session.pay_rules_activation_cost(source, copy.deepcopy(ability))
        session.apply_rules_action_result({"id": "cleanse", "controllerId": "p1", "source": {"cardId": "will-x"},
            "targets": [self.target(host)], "ability": {"result": {"kind": "cleanse_target"}}})
        self.assertFalse(session.rules_card_can_enter_support(host))
        session.phase_tracker["turn"] += 1
        self.assertFalse(session.rules_card_can_enter_support(host))

    def test_pillar_suppresses_piercing_lovers_end_game_penalty_in_its_vessel(self):
        session, _p1, p2 = self.started()
        session.card_rules[self.LOVER]["power"] = 3
        self.put(p2, "receptacle", {self.LOVER: "p1", "m-2": "p1", "m-3": "p1"})
        self.assertEqual(session.rules_end_game_points("p2"), -10)
        pillar = self.field_item("pillar", "p2", self.PILLAR, field_zone="field")
        session.battlefield.append(pillar)
        self.assertEqual(session.rules_end_game_points("p2"), 0, "Vessel manifestations lose ALL effects while Pillar is active")
        pillar["effectsDisabled"] = True
        self.assertEqual(session.rules_end_game_points("p2"), -10)

    def test_pin_down_blocks_tokens_put_in_cz_by_a_previously_queued_jija(self):
        session, _p1, _p2 = self.started()
        host = self.field_item("jija", "p1", self.JIJA)
        session.battlefield += [host, self.field_item("reserve", "p2", "m-2", field_zone="interzone")]
        queued = self.isolated_action(self.JIJA, host, targets=[{"kind": "player", "playerId": "p2"}])
        session.apply_rules_action_result(self.isolated_action(self.PIN_DOWN, {"id": "pin", "ownerId": "p1"}))
        session.apply_rules_action_result(queued)
        self.assertEqual(session.rules_confrontation_items(), [], "Pin Down forbids putting manifestations into CZ, including tokens by an older queued effect")

    def test_wretched_arena_play_prohibition_does_not_block_token_creation(self):
        session, _p1, _p2 = self.started()
        arena = self.field_item("arena", "p1", self.ARENA, field_zone="field")
        host = self.field_item("jija", "p1", self.JIJA)
        session.battlefield += [arena, host, self.field_item("reserve", "p2", "m-2", field_zone="interzone")]
        session.apply_rules_action_result(self.isolated_action(self.ARENA, arena))
        session.apply_rules_action_result(self.isolated_action(self.JIJA, host, targets=[{"kind": "player", "playerId": "p2"}]))
        created = [i for i in session.battlefield if i.get("isTokenCard")]
        self.assertEqual(len(created), 1, "The printed Arena prohibition says play; Jija puts a token without playing it")

    def test_nullify_excludes_revealed_ephemeral_trap(self):
        session, _p1, _p2 = self.started()
        trap = self.field_item("trap", "p2", self.TRAP, field_zone="field")
        session.battlefield.append(trap)
        target = [self.target(trap)]
        nullify_contract = self.ABILITIES[self.NULLIFY][0]["targets"]
        self.assertIsNotNone(session.rules_ability_targets_error(nullify_contract, target, "p1"),
            "Nullify explicitly restricts Wills to Persistent")

    def test_colossus_includes_any_will_including_revealed_ephemeral_trap(self):
        session, _p1, _p2 = self.started()
        trap = self.field_item("trap", "p2", self.TRAP, field_zone="field")
        session.battlefield.append(trap)
        target = [self.target(trap)]
        colossus_contract = self.ABILITIES[self.COLOSSUS][0]["targets"]
        self.assertIsNone(session.rules_ability_targets_error(colossus_contract, target, "p1"),
            "Knobbly Colossus says Will without a Persistent qualifier")

    def declare_jaw_and_choose_entry_target(self, session, target):
        session.phase_tracker["index"] = game.ADVANCED_PHASES.index("end_actions")
        session.put_zone_card("p1", "hand", self.JAW, "p1")
        error, played = session.declare_rules_action("p1", "Flaying Jaw", kind="play_card",
            source={"cardId": self.JAW, "zone": "hand"})
        self.assertIsNone(error)
        self.assertIsNone(played.get("ability"), "The Will itself does not choose or apply its ETB target")
        session.resolve_rules_top_action()
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "trigger_targets")
        host = session.find_battlefield_item(choice["sourceItemId"])
        self.assertIsNotNone(host)
        error, _response = session.resolve_rules_choice("p1", choice["id"], targets=[self.target(target)])
        self.assertIsNone(error)
        self.assertEqual(len(session.rules_engine["actionStack"]), 1)
        trigger = session.rules_engine["actionStack"][-1]
        self.assertEqual(trigger["kind"], "triggered_effect")
        self.assertFalse(trigger.get("immediate"))
        self.assertEqual(trigger["source"]["itemId"], host["id"])
        return host, trigger

    def test_jaw_normal_play_has_separate_etb_then_cleanse_retarget_and_source_lifetime(self):
        session, _p1, _p2 = self.started()
        foe = session.find_battlefield_item("foe")
        host, _trigger = self.declare_jaw_and_choose_entry_target(session, foe)
        self.assertEqual(self.power_of(session, "foe"), 8, "Target choice has not resolved the ETB")
        session.resolve_rules_top_action()
        self.assertEqual(self.power_of(session, "foe"), 6)
        session.apply_rules_action_result({"id": "cleanse", "controllerId": "p1", "source": {"cardId": "will-x"},
            "targets": [self.target(foe)], "ability": {"result": {"kind": "cleanse_target"}}})
        self.assertEqual(self.power_of(session, "foe"), 8)
        self.assertEqual(len(session.rules_engine["ongoingEffects"]), 0)
        session.rules_engine["priorityPlayerId"] = "p1"
        error, _action = session.declare_rules_action("p1", "Retarget Jaw", kind="activated_effect",
            source={"cardId": self.JAW, "itemId": host["id"], "zone": "battlefield"},
            targets=[self.target(session.find_battlefield_item("mine"))], ability_id="flaying-jaw-retarget")
        self.assertIsNone(error, "Retarget rebuilds its template from triggeredAbilities after Cleanse")
        self.assertEqual(int(host.get("rotation") or 0), 90)
        session.resolve_rules_top_action()
        self.assertEqual(self.power_of(session, "mine"), 10)
        self.assertEqual(self.power_of(session, "foe"), 8)
        session._rules_remove_field_item(host, "p1", "graveyard", "top")
        session.prune_rules_ongoing_effects()
        self.assertEqual(self.power_of(session, "mine"), 12)

    def test_jaw_etb_allows_opponent_response_and_can_be_canceled_separately(self):
        session, _p1, p2 = self.started()
        foe = session.find_battlefield_item("foe")
        host, trigger = self.declare_jaw_and_choose_entry_target(session, foe)
        session.put_zone_card("p2", "hand", self.IGNORE, "p2")
        session.add_rules_excess_essence("p2", [{"temperament": "transcendent", "amount": 10}])
        session.rules_engine["priorityPlayerId"] = "p2"
        error, _response = session.declare_rules_action("p2", "Ignore Jaw ETB", kind="play_card",
            source={"cardId": self.IGNORE, "zone": "hand"}, ability_id="ignore-stack-effect-unless-paid",
            targets=[{"kind": "stack_effect", "actionId": trigger["id"]}])
        self.assertIsNone(error)
        self.assertEqual(len(session.rules_engine["actionStack"]), 2)
        session.resolve_rules_top_action()
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "stack_counter_payment")
        error, _result = session.resolve_rules_choice("p1", choice["id"], option="decline")
        self.assertIsNone(error)
        self.assertEqual(session.rules_engine["actionStack"], [])
        self.assertIsNotNone(session.find_battlefield_item(host["id"]), "Canceling the ETB does not neutralize its Will")
        self.assertEqual(self.power_of(session, "foe"), 8)
        self.assertNotIn(self.JAW, p2["zones"]["graveyard"])

    def test_jaw_direct_face_up_entry_and_token_copy_each_trigger_once(self):
        for copied in (False, True):
            with self.subTest(copy=copied):
                session, _p1, _p2 = self.started()
                foe = session.find_battlefield_item("foe")
                if copied:
                    host = session.create_rules_token_copy(self.JAW, "p1")
                    actions = session.queue_rules_token_copy_entry_triggers(host)
                else:
                    host = self.field_item("jaw-direct", "p1", self.JAW, field_zone="field")
                    session.battlefield.append(host)
                    actions = session.queue_rules_battlefield_entry_triggers(self.JAW, "p1", host["id"], True, defer=True)
                    session.queue_rules_simultaneous_actions(actions)
                self.assertEqual(len(actions), 1)
                choice = session.rules_engine["pendingChoice"]
                self.assertEqual(choice["kind"], "trigger_targets")
                error, _result = session.resolve_rules_choice("p1", choice["id"], targets=[self.target(foe)])
                self.assertIsNone(error)
                self.assertEqual(len(session.rules_engine["actionStack"]), 1)
                session.resolve_rules_top_action()
                self.assertEqual(self.power_of(session, "foe"), 6)
                self.assertEqual(session.rules_engine["ongoingEffects"][0]["source"]["itemId"], host["id"])

    def test_jaw_can_enter_without_a_manifestation_and_face_down_entry_does_not_trigger(self):
        session, _p1, _p2 = self.started()
        session.battlefield = []
        session.phase_tracker["index"] = game.ADVANCED_PHASES.index("end_actions")
        session.put_zone_card("p1", "hand", self.JAW, "p1")
        error, _played = session.declare_rules_action("p1", "Jaw empty field", kind="play_card",
            source={"cardId": self.JAW, "zone": "hand"})
        self.assertIsNone(error)
        session.resolve_rules_top_action()
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertEqual(len(session.battlefield), 1)
        concealed = self.field_item("concealed-jaw", "p1", self.JAW, field_zone="field")
        concealed["faceUp"] = False
        session.battlefield.append(concealed)
        self.assertEqual(session.queue_rules_battlefield_entry_triggers(self.JAW, "p1", concealed["id"], False), [])
