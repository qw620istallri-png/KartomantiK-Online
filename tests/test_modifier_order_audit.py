import copy
import itertools
import test_game_state as game_tests


class ModifierOrderAuditTests(game_tests.RealCardRulesCase):
    MIMER = "pwsjhnw4vpvqgkv_en"
    MIRROR = "0e7afy7zmyhbfal_en"
    MASK = "1ixfmjkfewc0o42_en"
    ENTRUST = "ud9clfoj2c6x96o_en"
    INFLATE = "inner-deserts-118"
    CLEANSE = "inner-deserts-145"
    BERTA = "inner-deserts-009"
    HALTAN = "inner-deserts-125"
    JAW = "y6g3tex9ypttk8u_en"
    NECTAR = "7gd19pmexrjlrap_en"
    WEAKEN = "bithch9c4vi77cu_en"
    ACCENTUATE = "ztunjt1msq1ofsv_en"
    HUMILIATE = "pqi88s5ytyfnalf_en"
    BOB = "inner-deserts-134"
    ALL = (MIMER, MIRROR, MASK, ENTRUST, INFLATE, CLEANSE, BERTA, HALTAN, JAW, NECTAR, WEAKEN, ACCENTUATE, HUMILIATE, BOB)

    def started(self):
        session, p1, p2 = self.make_session()
        session.rules_engine.update(readyPlayerIds=["p1", "p2"], firstManifestationComplete=True, priorityPlayerId="p1")
        session.phase_tracker["index"] = game_tests.ADVANCED_PHASES.index("confrontation_reaction")
        session.card_rules["m-0"].update(power=3, temperaments=["capricious"])
        session.card_rules["m-1"].update(power=5, temperaments=["choleric"])
        mine = self.field_item("mine", "p1", "m-0", x=0, y=0, rotation=0)
        foe = self.field_item("foe", "p2", "m-1", x=200, y=0, rotation=0)
        session.battlefield = [mine, foe]
        session.rules_engine["firstManifestationItemIds"] = {"p1": "mine", "p2": "foe"}
        return session, p1, p2, mine, foe

    def resolve_card(self, session, cid, item_id="mine", ability_id=None):
        ability = next(a for a in self.ABILITIES[cid] if a["id"] == ability_id) if ability_id else next(a for a in self.ABILITIES[cid] if a.get("action") == "play_card")
        item = session.find_battlefield_item(item_id)
        action = {
            "id": f"test-{cid}-{len(session.players['p1']['zones']['graveyard'])}",
            "controllerId": "p1", "label": cid, "kind": "play_card", "sourceOnStack": True,
            "source": {"cardId": cid, "cardType": session.card_rules[cid]["type"], "ownerId": "p1", "zone": "hand"},
            "targets": [{"kind": "card", "itemId": item_id, "cardId": item["cardId"], "ownerId": item["ownerId"]}],
            "ability": ability,
        }
        if not ability.get("action"):
            host = next((entry for entry in session.battlefield if entry["cardId"] == cid), None)
            if host is None:
                host = self.field_item(f"host-{cid}", "p1", cid, "field")
                session.battlefield.append(host)
            action.update(kind="activated_effect", sourceOnStack=False,
                          source={"cardId": cid, "itemId": host["id"], "ownerId": "p1", "zone": "battlefield"})
        session.rules_engine["actionStack"].append(action)
        result = session.resolve_rules_top_action()
        self.assertNotEqual(result["action"].get("effectResult", {}).get("kind"), "invalid_targets")
        return result

    def copy_action(self, session, mine, foe):
        mine["cardId"] = self.MIMER
        return {"id": "copy", "label": "Mimer", "kind": "activated_effect", "controllerId": "p1",
                "source": {"cardId": self.MIMER, "itemId": "mine", "ownerId": "p1", "zone": "battlefield"},
                "targets": [{"kind": "card", "itemId": "foe", "cardId": foe["cardId"], "ownerId": "p2"}],
                "ability": self.ability(self.MIMER, "copy-first-manifestation")}

    def resolve_copy(self, session, mine, foe):
        session.rules_engine["actionStack"].append(self.copy_action(session, mine, foe))
        session.resolve_rules_top_action()

    def test_temperament_changes_follow_actual_stack_resolution_order(self):
        session, _, _, mine, foe = self.started()
        session.rules_engine["actionStack"].append(self.copy_action(session, mine, foe))
        # Mask is above the copy: it resolves first, then Mimer becomes red.
        self.resolve_card(session, self.MASK, ability_id="mask-becomes-vitreous")
        self.assertEqual(session.rules_manifestation_characteristics(mine)["temperament"], "vitreous")
        session.resolve_rules_top_action()
        self.assertEqual(session.rules_manifestation_characteristics(mine)["temperament"], "choleric")
        # A later Mask wins in turn. On expiry the permanent copy is visible again.
        self.resolve_card(session, self.MASK, ability_id="mask-becomes-melancholic")
        self.assertEqual(session.rules_manifestation_characteristics(mine)["temperament"], "melancholic")
        session.phase_tracker["turn"] += 1
        session.prune_rules_ongoing_effects()
        self.assertEqual(session.rules_manifestation_characteristics(mine)["temperament"], "choleric")

    def test_copy_replaces_base_stats_but_keeps_own_power_modifiers(self):
        session, _, _, mine, foe = self.started()
        mine["counters"]["power"] = 2
        foe["counters"]["power"] = 1
        self.resolve_copy(session, mine, foe)
        self.assertEqual(session.rules_manifestation_base_power(mine), 6)
        self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 8)

    def test_entrust_and_copy_update_base_power_in_resolution_order(self):
        for copy_first in (True, False):
            with self.subTest(copy_first=copy_first):
                session, _, _, mine, foe = self.started()
                mine["cardId"] = self.MIMER
                if copy_first:
                    self.resolve_copy(session, mine, foe)
                    self.resolve_card(session, self.ENTRUST)
                else:
                    self.resolve_card(session, self.ENTRUST)
                    self.resolve_copy(session, mine, foe)
                expected = 10 if copy_first else 5
                self.assertEqual(session.rules_manifestation_base_power(mine), expected)
                self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], expected)

    def test_inflate_sets_current_power_then_allows_later_maluses_below_its_cap(self):
        for weaken_first in (True, False):
            with self.subTest(weaken_first=weaken_first):
                session, _, _, mine, _ = self.started()
                if weaken_first:
                    self.resolve_card(session, self.WEAKEN)
                self.resolve_card(session, self.INFLATE)
                self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 10)
                if not weaken_first:
                    self.resolve_card(session, self.WEAKEN)
                    self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 9)
                self.resolve_card(session, self.ACCENTUATE)
                self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 10)

    def test_humiliate_after_mask_or_copy_really_changes_current_temperament(self):
        for copy_first in (True, False):
            with self.subTest(copy_first=copy_first):
                session, _, _, mine, foe = self.started()
                if copy_first:
                    self.resolve_copy(session, mine, foe)
                else:
                    self.resolve_card(session, self.MASK, ability_id="mask-becomes-vitreous")
                self.resolve_card(session, self.HUMILIATE)
                self.assertEqual(session.rules_manifestation_characteristics(mine)["temperament"], "hollow")

    def test_haltan_global_modifier_survives_cleanup_and_expires_next_turn(self):
        session, p1, p2, _, _ = self.started()
        haltan = self.field_item("haltan", "p1", self.HALTAN)
        session.battlefield.append(haltan)
        error, _ = session.declare_rules_action("p1", "Freeze Points", kind="activated_effect",
            source={"cardId": self.HALTAN, "itemId": "haltan", "zone": "battlefield"},
            ability_id="exhaust-sacrifice-to-prevent-point-changes")
        self.assertIsNone(error)
        session.resolve_rules_immediate_actions()
        self.assertNotIn(haltan, session.battlefield)
        for phase in ("confrontation_reaction", "resolution_effects", "end_actions", "end_expire"):
            session.phase_tracker["index"] = game_tests.ADVANCED_PHASES.index(phase)
            session.prune_rules_ongoing_effects()
            self.assertTrue(session.rules_points_changes_prevented(), phase)
            self.assertEqual(session.adjust_rules_score("p1", 10), 0)
            self.assertEqual(session.adjust_rules_score("p2", -10), 0)
        self.assertEqual((p1["score"], p2["score"]), (0, 0))
        session.phase_tracker["turn"] += 1
        session.phase_tracker["index"] = game_tests.ADVANCED_PHASES.index("recovery_start")
        session.prune_rules_ongoing_effects()
        self.assertFalse(session.rules_points_changes_prevented())
        self.assertEqual(session.adjust_rules_score("p1", 10), 10)

    def test_additive_bonuses_and_maluses_commute_and_expire_together(self):
        for cards in itertools.permutations((self.ACCENTUATE, self.WEAKEN)):
            with self.subTest(order=cards):
                session, _, _, mine, _ = self.started()
                for cid in cards:
                    self.resolve_card(session, cid)
                self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 3)
                session.phase_tracker["turn"] += 1
                session.prune_rules_ongoing_effects()
                self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 3)
                self.assertFalse(session.rules_engine["ongoingEffects"])

    def test_double_base_does_not_double_additive_modifiers(self):
        for cards in itertools.permutations((self.ACCENTUATE, self.ENTRUST)):
            with self.subTest(order=cards):
                session, _, _, mine, _ = self.started()
                for cid in cards:
                    self.resolve_card(session, cid)
                self.assertEqual(session.rules_manifestation_base_power(mine), 6)
                self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 7)
                session.phase_tracker["turn"] += 1
                session.prune_rules_ongoing_effects()
                self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 6)

    def test_temporary_blanking_of_a_continuous_source_suspends_its_modifier(self):
        session, _, _, mine, _ = self.started()
        self.resolve_card(session, self.JAW, ability_id="flaying-jaw-power-link")
        jaw = next(item for item in session.battlefield if item["cardId"] == self.JAW)
        self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 1)
        jaw["effectsDisabled"] = True
        session.prune_rules_ongoing_effects()
        self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 3)
        jaw.pop("effectsDisabled")
        self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 1)

    def test_cleanse_removes_resolved_modifiers_but_preserves_counters(self):
        session, _, _, mine, _ = self.started()
        mine["counters"] = {"Gem": 2}
        self.resolve_card(session, self.ENTRUST)
        self.resolve_card(session, self.ACCENTUATE)
        self.resolve_card(session, self.CLEANSE)
        self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 3)
        self.assertEqual(mine["counters"], {"Gem": 2})

    def test_resolved_copy_and_doubling_survive_blanking_and_stalemate_until_exit(self):
        session, _, _, mine, foe = self.started()
        mine["counters"]["power"] = 2
        self.resolve_copy(session, mine, foe)
        self.resolve_card(session, self.ENTRUST)
        for zone in ("stalemate", "interzone", "confrontation"):
            mine.update(fieldZone=zone, effectsDisabled=True)
            session.prune_rules_ongoing_effects()
            self.assertEqual(session.rules_manifestation_characteristics(mine), {"power": 12, "temperament": "choleric"})
        session._rules_remove_field_item(mine, "p1", "graveyard")
        session.prune_rules_ongoing_effects()
        self.assertFalse(session.rules_engine["ongoingEffects"])
        returned = self.field_item("returned", "p1", self.MIMER)
        session.battlefield.append(returned)
        self.assertEqual(session.rules_manifestation_base_power(returned), session.card_rules[self.MIMER]["power"])

    def test_mirror_copy_and_own_bonus_have_separate_expiration_times(self):
        session, _, _, mine, foe = self.started()
        mine["cardId"] = self.MIRROR
        self.resolve_card(session, self.ACCENTUATE)
        session.create_rules_ongoing_effects({
            "id": "mirror-copy", "controllerId": "p1", "source": {"cardId": self.MIRROR, "itemId": "mine"},
            "targets": [{"kind": "card", "itemId": "foe", "cardId": foe["cardId"]}],
            "ability": self.ability(self.MIRROR, "mirrorbeast-copy-power-and-effects"),
        })
        self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 6)
        session.phase_tracker["index"] = game_tests.ADVANCED_PHASES.index("end_actions")
        session.prune_rules_ongoing_effects()
        self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], session.card_rules[self.MIRROR]["power"] + 1)
        session.phase_tracker["turn"] += 1
        session.prune_rules_ongoing_effects()
        self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], session.card_rules[self.MIRROR]["power"])

    def test_berta_floor_uses_the_same_base_power_as_other_rules_after_a_copy(self):
        session, _, _, mine, foe = self.started()
        mine["cardId"] = self.MIMER
        session.battlefield.append(self.field_item("berta", "p2", self.BERTA, "interzone"))
        session.create_rules_ongoing_effects({
            "id": "mimer-copy", "controllerId": "p1", "source": {"cardId": self.MIMER, "itemId": "mine"},
            "targets": [{"kind": "card", "itemId": "foe", "cardId": foe["cardId"]}],
            "ability": self.ability(self.MIMER, "copy-first-manifestation"),
        })
        self.resolve_card(session, self.WEAKEN)
        self.assertGreaterEqual(session.rules_manifestation_characteristics(mine)["power"], session.rules_manifestation_base_power(mine))

    def test_expiring_buff_destroys_zero_power_before_beginning_turn_triggers(self):
        session, p1, p2, mine, foe = self.started()
        mine["fieldZone"] = "interzone"
        mine["counters"]["power"] = -3
        session.card_rules["m-0"]["triggeredAbilities"] = [{
            "id": "must-not-trigger", "trigger": {"event": "beginning_of_turn"},
            "result": {"kind": "score_owner", "value": 10},
        }]
        self.resolve_card(session, self.ACCENTUATE)
        self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 1)
        for player in (p1, p2):
            self.put(player, "hand", {f"m-{index}": player["id"] for index in range(7)})
        session.phase_tracker["index"] = game_tests.ADVANCED_PHASES.index("end_expire")
        session.rules_engine.update(priorityPlayerId="p1", priorityPasses=[])
        session.pass_rules_priority("p1")
        error, result = session.pass_rules_priority("p2")
        self.assertIsNone(error)
        self.assertNotIn(mine, session.battlefield)
        self.assertIn(mine["cardId"], p1["zones"]["graveyard"])
        self.assertFalse(any((action.get("ability") or {}).get("id") == "must-not-trigger" for action in session.rules_engine["actionStack"]))

    def test_expiration_replacement_is_chosen_before_advancing_the_turn(self):
        session, p1, p2, mine, _ = self.started()
        mine["fieldZone"] = "interzone"
        mine["counters"]["power"] = -3
        self.resolve_card(session, self.ACCENTUATE)
        for player in (p1, p2):
            self.put(player, "hand", {f"m-{index}": player["id"] for index in range(7)})
        for item_id in ("bob-a", "bob-b"):
            bob = self.field_item(item_id, "p2", self.BOB, "confrontation", counters={"power": 3})
            bob.update(isCopy=True, isTokenCopy=True)
            session.battlefield.append(bob)
        session.phase_tracker["index"] = game_tests.ADVANCED_PHASES.index("end_expire")
        session.rules_engine.update(priorityPlayerId="p1", priorityPasses=[])
        session.pass_rules_priority("p1")
        before = copy.deepcopy((session.players, session.battlefield, session.phase_tracker))
        error, result = session.pass_rules_priority("p2")
        self.assertIsNone(error)
        self.assertEqual(result["status"], "choice_required")
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "replacement_order")
        self.assertEqual(before, (session.players, session.battlefield, session.phase_tracker))
        order = [action["actionId"] for action in choice["actions"]]
        error, result = session.resolve_rules_choice("p2", choice["id"], order)
        self.assertIsNone(error)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["_priorityResults"][0]["status"], "advanced")
        self.assertEqual(session.phase_tracker["turn"], before[2]["turn"] + 1)
        self.assertIsNone(session.find_battlefield_item("mine"))
        self.assertEqual(len(session.rules_engine["suspendedCards"]), 1)
        self.assertEqual(session.current_phase_id(), "recovery_start")
        beginning = session.rules_engine["pendingChoice"]
        self.assertEqual(beginning["kind"], "simultaneous_stack_order")
        self.assertEqual(len(beginning["actions"]), 2)
        after = copy.deepcopy((session.players, session.battlefield, session.phase_tracker))
        self.assertIsNotNone(session.resolve_rules_choice("p2", choice["id"], order)[0])
        self.assertEqual(after, (session.players, session.battlefield, session.phase_tracker))
