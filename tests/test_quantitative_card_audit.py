"""Printed-text numeric oracles; expected values never read ability.value.

Voluntary Wills use declaration/payment and Stack resolution. Triggered effects
are isolated at resolution, except Mukkabell which also exercises Chain and win.
This is a bounded semantic pass, not certification of every clause of a card.
"""
import copy

import test_game_state as game_tests


class QuantitativeCardAuditTests(game_tests.RealCardRulesCase):
    INDUCE = "inner-deserts-148"
    MIMER = "pwsjhnw4vpvqgkv_en"
    ENTRUST = "ud9clfoj2c6x96o_en"
    MUKKABELL = "inner-deserts-012"
    DANCER = "fr1414jedqssttr_en"
    PINPIA = "5xurdeiiyq7kgir_en"
    PLEA = "31k2b7hz7ockvvn_en"
    AGRUPOL = "j2a7x783j5ql0ab_en"
    DONMO = "inner-deserts-121"
    HUMILIATE = "pqi88s5ytyfnalf_en"
    JUDGMENT = "inner-deserts-046"
    PIMBO = "ng6w09m6mrjq3xc_en"
    CORRODE = "w3jt07uuk00nmaj_en"
    FRIENDLY = "l6ragmkyw5oyued_en"
    VIPER = "3gy8gbbbmamc8d0_en"
    JAW = "y6g3tex9ypttk8u_en"
    LOMBRIC = "inner-deserts-014"
    PACHY = "9ypw4x4igfon1qi_en"
    PETAL = "aumzs91roqg77y1_en"
    STRENGTHEN = "lo85kdsow36bymu_en"
    WEAKEN = "bithch9c4vi77cu_en"
    OPPRESS = "obn1uv72ewxv3y5_en"
    ACCENTUATE = "ztunjt1msq1ofsv_en"
    REAP = "8xi4zh0ekdl42me_en"
    PROTECT = "whwfrjzl6flgww9_en"
    STARKAZ = "ei33difzdc81zha_en"
    SEVER = "inner-deserts-150"
    ALL = (INDUCE, MIMER, ENTRUST, MUKKABELL, DANCER, PINPIA, PLEA,
           AGRUPOL, DONMO, HUMILIATE, JUDGMENT, PIMBO, CORRODE, FRIENDLY,
           VIPER, JAW, LOMBRIC, PACHY, PETAL, STRENGTHEN, WEAKEN, OPPRESS,
           ACCENTUATE, REAP, PROTECT, STARKAZ, SEVER)

    def started(self):
        session, p1, p2 = self.make_session()
        session.rules_engine.update(readyPlayerIds=["p1", "p2"],
            firstManifestationComplete=True, priorityPlayerId="p1", autoSkipPhases=False)
        session.phase_tracker["index"] = game_tests.ADVANCED_PHASES.index("confrontation_reaction")
        session.card_rules["m-0"]["power"] = 20
        session.card_rules["m-1"]["power"] = 4
        mine = self.field_item("mine", "p1", "m-0")
        foe = self.field_item("foe", "p2", "m-1")
        session.battlefield = [mine, foe]
        session.rules_engine["firstManifestationItemIds"] = {"p1": "mine", "p2": "foe"}
        session.add_rules_excess_essence("p1", [{"temperament": "transcendent", "amount": 100}])
        return session, p1, p2, mine, foe

    def target(self, item):
        return {"kind": "card", "itemId": item["id"],
                "cardId": item.get("cardId"), "ownerId": item["ownerId"]}

    def declare(self, session, cid, targets=()):
        session.rules_engine["priorityPlayerId"] = "p1"
        session.put_zone_card("p1", "hand", cid, "p1")
        ability = next(a for a in self.ABILITIES[cid] if a.get("action") == "play_card")
        error, action = session.declare_rules_action("p1", cid, kind="play_card",
            source={"cardId": cid, "zone": "hand"}, ability_id=ability["id"], targets=list(targets))
        self.assertIsNone(error)
        return action

    def play(self, session, cid, targets=()):
        self.declare(session, cid, targets)
        return self.resolve_top(session)

    def resolve_top(self, session):
        outcome = session.resolve_rules_top_action()
        self.assertIsNotNone(outcome)
        self.assertNotEqual(outcome["action"].get("effectResult", {}).get("kind"), "invalid_targets")
        return outcome

    def effect(self, session, cid, host, targets=(), ability_id=None):
        ability = self.ability(cid, ability_id) if ability_id else self.ABILITIES[cid][0]
        action = {"id": "numeric-" + cid, "label": cid, "kind": "triggered_effect",
                  "controllerId": session.rules_item_controller_id(host),
                  "source": {"cardId": cid, "itemId": host["id"],
                             "ownerId": host["ownerId"], "zone": "battlefield"},
                  "targets": list(targets), "ability": copy.deepcopy(ability)}
        session.rules_engine["actionStack"].append(action)
        return self.resolve_top(session)

    def host(self, session, cid, zone="interzone", **extra):
        item = self.field_item("host-" + cid, "p1", cid, zone, **extra)
        session.battlefield.append(item)
        return item

    def token(self, session, controller="p1", zone="interzone", power=8):
        return session.create_rules_token_copy(None, controller,
            generic_power=power, generic_temperament="phlegmatic", field_zone=zone)

    def expire(self, session):
        session.phase_tracker["turn"] += 1
        session.prune_rules_ongoing_effects()

    def test_induce_uses_doubled_base_and_excludes_additive_bonus(self):
        session, _, _, mine, foe = self.started()
        support = self.field_item("support", "p1", "m-1", isSupport=True,
                                  counters={"power": 3})
        session.battlefield.append(support)
        self.play(session, self.ENTRUST, [self.target(support)])
        self.assertEqual(self.power_of(session, "support"), 11)  # 4 * 2 + 3
        self.play(session, self.INDUCE, [self.target(mine), self.target(support)])
        self.assertEqual(self.power_of(session, "mine"), 12)  # 20 - base 8, not 4 or 11
        self.assertEqual(self.power_of(session, "foe"), 4)
        self.expire(session)
        self.assertEqual(self.power_of(session, "mine"), 12)  # no printed expiry

    def test_induce_uses_mimers_snapshot_base_and_not_its_bonus(self):
        session, _, _, mine, foe = self.started()
        support = self.host(session, self.MIMER, "confrontation", isSupport=True,
                            counters={"power": 2})
        foe["counters"]["power"] = 1
        self.effect(session, self.MIMER, support, [self.target(foe)])
        foe["counters"]["power"] = 6  # copy stays at 5, even when original changes
        self.assertEqual(self.power_of(session, support["id"]), 7)
        self.play(session, self.INDUCE, [self.target(mine), self.target(support)])
        self.assertEqual(self.power_of(session, "mine"), 15)

    def test_induce_counts_generic_token_base(self):
        session, _, _, mine, _ = self.started()
        support = self.token(session, zone="confrontation", power=6)
        support["counters"]["power"] = 2
        self.play(session, self.INDUCE, [self.target(mine), self.target(support)])
        self.assertEqual(self.power_of(session, "mine"), 14)

    def test_mukkabell_win_uses_chained_modified_base_not_print_or_bonus(self):
        session, p1, _, _, _ = self.started()
        mukkabell = self.host(session, self.MUKKABELL)
        session.put_zone_card("p1", "hand", "m-1", "p1")
        # Exercise the real Chain choice and granted win ability.
        self.effect(session, self.MUKKABELL, mukkabell)
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "chain_manifestation")
        error, chained = session.resolve_rules_choice("p1", choice["id"], ["m-1"], placement={"x": 10, "y": 10})
        self.assertIsNone(error)
        item = session.find_battlefield_item(chained["itemId"])
        item["counters"]["power"] = 3
        self.play(session, self.ENTRUST, [self.target(item)])
        session.rules_engine["confrontationResult"] = {"winnerId": "p1", "loserId": "p2", "participantItemIds": [item["id"]]}
        queued = session.queue_rules_confrontation_win_triggers(defer=True)
        action = next(a for a in queued if a["ability"]["id"] == "mukkabell-chained-wins")
        session.rules_engine["actionStack"].append(action)
        self.resolve_top(session)
        self.assertEqual(p1["score"], 40)  # base 4 * 2, then 5 points each

    def interzone_roster(self, session):
        self.host(session, "m-2")
        self.token(session)
        # Neither an ordinary Will nor an opponent's Manifestation counts.
        self.host(session, "will-x")
        self.host(session, "m-3", controllerId="p2")

    def test_dancer_counts_tokens_under_current_control(self):
        session, p1, p2, _, _ = self.started()
        dancer = self.host(session, self.DANCER, "confrontation")
        self.interzone_roster(session)
        self.effect(session, self.DANCER, dancer)
        self.assertEqual((p1["score"], p2["score"]), (10, 0))

    def test_pinpia_creates_one_retained_essence_per_actual_interzone_manifestation(self):
        session, _, _, _, _ = self.started()
        session.tokens = []
        host = self.host(session, self.PINPIA, "confrontation")
        self.interzone_roster(session)
        self.effect(session, self.PINPIA, host)
        essences = [t for t in session.tokens if t.get("isEssence")]
        self.assertEqual(sum(t["counters"]["essence"] for t in essences), 2)
        self.assertTrue(all(t.get("expiresTurn") == 0 for t in essences))
        session.expire_rules_excess_essence(session.phase_tracker["turn"])
        self.assertEqual(sum(t["counters"]["essence"] for t in session.tokens if t.get("isEssence")), 2)

    def test_generic_token_targeting_keeps_type_visibility_and_protection_checks(self):
        session, _, _, _, _ = self.started()
        token = self.token(session, "p2", "confrontation")
        contract = {"kind": "card", "cardType": "manifestation", "min": 1, "max": 1}
        def legal():
            return {t["itemId"] for t in session.rules_legal_target_candidates(contract, "p1")}
        self.assertIn(token["id"], legal())
        self.assertNotIn(token["id"], {t["itemId"] for t in session.rules_legal_target_candidates(
            {**contract, "cardType": "persistent_will"}, "p1")})
        token["faceUp"] = False
        self.assertNotIn(token["id"], legal())
        token["faceUp"] = True
        session.rules_engine["ongoingEffects"].append({"kind": "protection", "fromOpponents": True,
            "duration": "until_end_of_turn", "startedTurn": session.phase_tracker["turn"],
            "target": {"kind": "card", "itemId": token["id"]}})
        self.assertNotIn(token["id"], legal())
        session.rules_engine["ongoingEffects"] = []
        self.play(session, self.OPPRESS, [self.target(token)])
        self.assertEqual(self.power_of(session, token["id"]), 5)

    def test_plea_excludes_tokens_and_copies_but_counts_animated_will(self):
        session, p1, p2, _, _ = self.started()
        self.token(session, "p2", "confrontation")
        session.create_rules_token_copy("m-3", "p2")
        session.battlefield.append(self.field_item("animated", "p2", self.JAW,
            willManifestation={"power": 7, "turn": session.phase_tracker["turn"]}))
        self.play(session, self.PLEA, [{"kind": "player", "playerId": "p2"}])
        self.assertEqual((p1["score"], p2["score"]), (10, 0))

    def test_agrupol_counts_ownership_across_both_vessels(self):
        session, p1, p2, _, _ = self.started()
        self.put(p1, "receptacle", {"m-3": "p2"})
        self.put(p2, "receptacle", {"m-4": "p1", "m-5": "p1", "will-x": "p1"})
        host = self.host(session, self.AGRUPOL, "confrontation")
        self.effect(session, self.AGRUPOL, host)
        self.assertEqual((p1["score"], p2["score"]), (10, 0))

    def test_reap_counts_tokens_for_score_and_draws_only_for_free_spaces(self):
        for full in (False, True):
            with self.subTest(full_interzone=full):
                session, p1, _, _, _ = self.started()
                self.token(session)
                self.host(session, "m-2")
                if full:
                    self.token(session)
                self.put(p1, "deck", ["m-6", "m-7", "m-8"])
                self.play(session, self.REAP)
                self.assertEqual(p1["score"], 15 if full else 10)
                self.assertEqual(len(p1["zones"]["hand"]), 0 if full else 1)
                self.assertEqual(len(p1["zones"]["deck"]), 3 if full else 2)

    def test_donmo_counts_exhaustion_and_control_not_ownership_or_type(self):
        session, p1, p2, mine, foe = self.started()
        host = self.host(session, self.DONMO, rotation=90)
        mine.update(rotation=180)  # restored, despite non-zero rotation
        foe.update(controllerId="p1", rotation=270)  # borrowed, exhausted
        self.host(session, self.JAW, "field", rotation=90)
        self.host(session, "m-3", controllerId="p2", rotation=90)
        self.effect(session, self.DONMO, host, ability_id="donmo-gives-opponents-points-for-exhausted")
        self.assertEqual((p1["score"], p2["score"]), (0, 15))

    def test_humiliate_penalizes_current_controller_and_persists(self):
        session, p1, p2, _, foe = self.started()
        foe["controllerId"] = "p1"
        self.play(session, self.HUMILIATE, [self.target(foe)])
        self.assertEqual((p1["score"], p2["score"]), (-5, 0))
        self.assertEqual(session.rules_manifestation_characteristics(foe), {"power": 3, "temperament": "hollow"})
        self.expire(session)
        self.assertEqual(session.rules_manifestation_characteristics(foe), {"power": 3, "temperament": "hollow"})

    def test_judgment_snapshots_hand_on_resolution_excluding_played_will(self):
        session, p1, _, mine, _ = self.started()
        self.put(p1, "hand", ["m-2", "m-3"])
        self.declare(session, self.JUDGMENT, [self.target(mine)])
        self.assertEqual(len(p1["zones"]["hand"]), 2)
        session.put_zone_card("p1", "hand", "m-4", "p1")  # response draws one
        self.resolve_top(session)
        self.assertEqual(self.power_of(session, "mine"), 17)
        session.put_zone_card("p1", "hand", "m-5", "p1")
        self.assertEqual(self.power_of(session, "mine"), 17)
        self.expire(session)
        self.assertEqual(self.power_of(session, "mine"), 20)

    def test_printed_fixed_modifiers_have_exact_amount_and_expiry(self):
        for cid, expected in ((self.STRENGTHEN, 23), (self.ACCENTUATE, 21),
                              (self.WEAKEN, 19), (self.OPPRESS, 17)):
            with self.subTest(card=cid):
                session, _, _, mine, foe = self.started()
                self.play(session, cid, [self.target(mine)])
                self.assertEqual(self.power_of(session, "mine"), expected)
                self.assertEqual(self.power_of(session, "foe"), 4)
                self.expire(session)
                self.assertEqual(self.power_of(session, "mine"), 20)

    def test_corrode_affects_both_sides_and_tokens_but_only_existing_cz(self):
        session, _, _, mine, foe = self.started()
        token = self.token(session, "p2", "confrontation")
        inter = self.host(session, "m-1")
        self.play(session, self.CORRODE)
        self.assertEqual([self.power_of(session, i["id"]) for i in (mine, foe, token, inter)], [19, 3, 7, 4])
        newcomer = self.token(session, "p2", "confrontation")
        self.assertEqual(self.power_of(session, newcomer["id"]), 8)
        self.expire(session)
        self.assertEqual(self.power_of(session, token["id"]), 8)

    def test_pimbo_includes_generic_tokens_and_animated_wills_on_field(self):
        session, _, _, mine, foe = self.started()
        host = self.host(session, self.PIMBO)
        token = self.token(session)
        animated = self.host(session, self.JAW, "confrontation", willManifestation={"power": 7, "turn": session.phase_tracker["turn"]})
        error, _ = session.declare_rules_action("p1", "Pimbo", kind="activated_effect",
            source={"cardId": self.PIMBO, "itemId": host["id"], "zone": "battlefield"},
            ability_id="sacrifice-field-power-loss")
        self.assertIsNone(error)
        self.resolve_top(session)
        self.assertIsNone(session.find_battlefield_item(host["id"]))
        self.assertEqual([self.power_of(session, i["id"]) for i in (mine, foe, token, animated)], [19, 3, 7, 6])
        newcomer = self.token(session)
        self.assertEqual(self.power_of(session, newcomer["id"]), 8)
        self.expire(session)
        self.assertEqual(self.power_of(session, token["id"]), 8)

    def test_friendly_presence_targets_current_opponent_cz_only(self):
        session, _, _, mine, foe = self.started()
        host = self.host(session, self.FRIENDLY, "confrontation")
        token = self.token(session, "p2", "confrontation")
        inter = self.token(session, "p2")
        self.effect(session, self.FRIENDLY, host)
        self.assertEqual([self.power_of(session, i["id"]) for i in (mine, foe, token, inter)], [20, 2, 6, 8])
        newcomer = self.token(session, "p2", "confrontation")
        self.assertEqual(self.power_of(session, newcomer["id"]), 8)
        self.expire(session)
        self.assertEqual(self.power_of(session, token["id"]), 8)

    def test_pimbo_does_not_reach_stalemate_which_is_outside_the_field(self):
        session, _, _, _, _ = self.started()
        host = self.host(session, self.PIMBO)
        outside = self.host(session, "m-1", "stalemate")
        token = self.token(session)
        token["fieldZone"] = "stalemate"
        error, _ = session.declare_rules_action("p1", "Pimbo", kind="activated_effect",
            source={"cardId": self.PIMBO, "itemId": host["id"], "zone": "battlefield"},
            ability_id="sacrifice-field-power-loss")
        self.assertIsNone(error)
        self.resolve_top(session)
        self.assertEqual(self.power_of(session, outside["id"]), 4)
        self.assertEqual(self.power_of(session, token["id"]), 8)

    def test_protect_covers_current_controlled_field_cards_but_not_stalemate(self):
        session, _, _, mine, foe = self.started()
        token = self.token(session)
        will = self.host(session, self.JAW, "field")
        outside = self.host(session, "m-3", "stalemate")
        self.play(session, self.PROTECT)
        protected = {e["target"]["itemId"] for e in session.rules_engine["ongoingEffects"] if e["kind"] == "protection"}
        self.assertEqual(protected, {mine["id"], token["id"], will["id"]})
        self.assertFalse(session.rules_item_is_protected(foe, "p1"))
        newcomer = self.token(session)
        self.assertFalse(session.rules_item_is_protected(newcomer, "p2"))
        self.expire(session)
        self.assertFalse(session.rules_item_is_protected(token, "p2"))

    def test_starkaz_and_sever_share_field_scope_without_reaching_stalemate(self):
        for cid, kind in ((self.STARKAZ, "lose_effects"), (self.SEVER, "remove_float")):
            with self.subTest(card=cid):
                session, _, _, mine, foe = self.started()
                token = self.token(session)
                inter = self.host(session, "m-3")
                self.host(session, "m-4", "stalemate")
                if cid == self.STARKAZ:
                    source = self.host(session, cid, "confrontation")
                    self.effect(session, cid, source)
                else:
                    self.play(session, cid)
                affected = {e["target"]["itemId"] for e in session.rules_engine["ongoingEffects"] if e["kind"] == kind}
                self.assertEqual(affected, {mine["id"], foe["id"], token["id"], inter["id"]})
                newcomer = self.token(session)
                self.assertNotIn(newcomer["id"], affected)

    def test_viper_locks_existing_opponent_interzone_including_tokens(self):
        session, _, _, mine, _ = self.started()
        host = self.host(session, self.VIPER, "confrontation")
        token = self.token(session, "p2")
        other = self.host(session, "m-3", controllerId="p2")
        self.effect(session, self.VIPER, host, [{"kind": "player", "playerId": "p2"}])
        locks = [e for e in session.rules_engine["ongoingEffects"] if e["kind"] == "interzone_lock"]
        self.assertEqual({e["target"]["itemId"] for e in locks}, {token["id"], other["id"]})
        newcomer = self.token(session, "p2")
        self.assertNotIn(newcomer["id"], {e["target"]["itemId"] for e in locks})
        self.expire(session)
        self.assertTrue(all(session.rules_ongoing_effect_active(e) for e in locks))
        self.expire(session)
        self.assertFalse(any(e["kind"] == "interzone_lock" for e in session.rules_engine["ongoingEffects"]))

    def test_excess_power_points_use_current_first_power_and_floor_at_zero(self):
        for cid, difference, expected in ((self.LOMBRIC, 3, (15, 0)),
                (self.PACHY, 3, (0, -15)), (self.LOMBRIC, 0, (0, 0)),
                (self.PACHY, -2, (0, 0))):
            with self.subTest(card=cid, difference=difference):
                session, p1, p2, _, foe = self.started()
                host = self.host(session, cid, "confrontation")
                # Printed base differs; bonuses establish the intended current powers.
                host["counters"]["power"] = 10 - session.rules_manifestation_base_power(host)
                foe["counters"]["power"] = 10 - difference - 4
                self.host(session, "m-0", "confrontation", controllerId="p2", isSupport=True)
                self.effect(session, cid, host, [{"kind": "player", "playerId": "p2"}])
                self.assertEqual((p1["score"], p2["score"]), expected)

    def test_graceful_petal_rewards_immutable_owner_after_vessel_entry(self):
        session, p1, p2, _, _ = self.started()
        self.put(p1, "hand", [self.PETAL])
        error, _, _ = session.move_zone_card_by_effect("p1", "hand", "p2", "receptacle", self.PETAL)
        self.assertIsNone(error)
        session.queue_rules_zone_entry_triggers(self.PETAL, "p1", "p2", "receptacle")
        action = next(a for a in session.rules_engine["actionStack"] if a["source"]["cardId"] == self.PETAL)
        self.assertEqual(action["source"]["ownerId"], "p1")
        self.resolve_top(session)
        self.assertEqual((p1["score"], p2["score"]), (20, 0))
