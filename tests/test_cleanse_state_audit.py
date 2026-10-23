"""Cleanse removes modifiers, preserves named resources and respects field lifetimes."""
import copy
import test_game_state as game_tests


class CleanseStateAuditTests(game_tests.RealCardRulesCase):
    CLEANSE = "inner-deserts-145"
    HUMILIATE = "pqi88s5ytyfnalf_en"
    GUMMO = "hcgvp7lbadlng1h_en"
    JAW = "y6g3tex9ypttk8u_en"
    NECTAR = "7gd19pmexrjlrap_en"
    SPLENDOR = "inner-deserts-143"
    HALTAN = "inner-deserts-125"
    MIMER = "pwsjhnw4vpvqgkv_en"
    BOB = "inner-deserts-134"
    HUSK = "8g5pn3mukkuniog_en"
    INFLORESCENCE = "vt3extxbwd6gybn_en"
    ALL = (CLEANSE, HUMILIATE, GUMMO, JAW, NECTAR, SPLENDOR, HALTAN, MIMER, BOB, HUSK, INFLORESCENCE)

    def started(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker["index"] = game_tests.ADVANCED_PHASES.index("confrontation_reaction")
        session.rules_engine.update(readyPlayerIds=["p1", "p2"], firstManifestationComplete=True, priorityPlayerId="p1")
        session.card_rules["m-0"].update(power=3, temperaments=["choleric"])
        session.card_rules["m-1"].update(power=5, temperaments=["vitreous"])
        mine = self.field_item("mine", "p1", "m-0", x=700, y=800, rotation=0)
        foe = self.field_item("foe", "p2", "m-1", x=700, y=525, rotation=0)
        session.battlefield = [mine, foe]
        return session, p1, p2, mine, foe

    def cleanse(self, session, item):
        action = {"id": "cleanse", "controllerId": "p1", "kind": "play_card", "sourceOnStack": True,
            "source": {"cardId": self.CLEANSE, "cardType": "ephemeral_will", "ownerId": "p1", "zone": "hand"},
            "targets": [{"kind": "card", "itemId": item["id"], "cardId": item["cardId"], "ownerId": item["ownerId"]}],
            "ability": self.ABILITIES[self.CLEANSE][0]}
        session.rules_engine["actionStack"].append(action)
        return session.resolve_rules_top_action()

    def result(self, session, result, source="mine", target="mine"):
        return session.apply_rules_action_result({"id": "effect", "controllerId": "p1",
            "source": {"itemId": source}, "targets": [{"kind": "card", "itemId": target}],
            "ability": {"id": "effect", "result": result}})

    def test_cleanse_removes_internal_power_modifiers_but_keeps_named_resources(self):
        for value in (-2, 2):
            with self.subTest(value=value):
                session, _, _, mine, _ = self.started()
                mine["counters"] = {"Gem": 2, "Quiet": 1, "Shackle": 3, "Atavic": 4, "tempCounter": 1}
                self.result(session, {"kind": "add_power_counter_target", "value": value})
                self.cleanse(session, mine)
                self.assertEqual(mine["counters"], {"Gem": 2, "Quiet": 1, "Shackle": 3, "Atavic": 4})
                self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 3)

    def test_cleanse_removes_both_parts_of_humiliate(self):
        session, _, _, mine, _ = self.started()
        self.result(session, {"kind": "humiliate_target"})
        self.assertEqual(session.rules_manifestation_characteristics(mine), {"power": 2, "temperament": "hollow"})
        self.cleanse(session, mine)
        self.assertEqual(session.rules_manifestation_characteristics(mine), {"power": 3, "temperament": "choleric"})

    def test_cleanse_removes_direct_gummo_copy_and_restores_printed_rules(self):
        session, p1, _, mine, _ = self.started()
        mine["cardId"] = self.GUMMO
        self.put(p1, "receptacle", {"m-1": "p2"})
        session.card_rules["m-1"]["activatedAbilities"] = [{"id": "copied-ability", "result": {"kind": "score_owner", "value": 1}}]
        session.card_rules["m-1"]["supportWinDestination"] = "exile"
        session.rules_engine["pendingChoice"] = {"id": "copy", "kind": "reveal_hand_discard", "purpose": "gummo",
            "playerId": "p1", "targetPlayerId": "p1", "sourceItemId": "mine", "cardIds": ["m-1"]}
        error, _ = session.resolve_rules_choice("p1", "copy", option="0")
        self.assertIsNone(error)
        self.assertEqual(session.rules_manifestation_base_power(mine), 5)
        self.cleanse(session, mine)
        self.assertNotIn("gummoCopy", mine)
        self.assertNotIn("supportWinDestination", mine)
        self.assertEqual(session.rules_manifestation_base_power(mine), session.card_rules[self.GUMMO]["power"])
        self.assertFalse(any(a["id"] == "copied-ability" for a in session.rules_item_card_rules(mine).get("activatedAbilities") or []))

    def test_cleanse_removes_added_power_bounds_but_keeps_zone_role_and_orientation(self):
        session, _, _, mine, _ = self.started()
        mine.update(minimumPower=6, maximumPower=8, isSupport=True, rotation=90)
        self.cleanse(session, mine)
        self.assertNotIn("minimumPower", mine)
        self.assertNotIn("maximumPower", mine)
        self.assertEqual((mine["fieldZone"], mine["rotation"], mine["isSupport"]), ("confrontation", 90, True))
        self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 3)

    def test_cleanse_preserves_splendor_resources_and_choice_without_retriggering_etb(self):
        session, _, _, mine, _ = self.started()
        mine.update(cardId=self.SPLENDOR, fieldZone="field", chosenTemperament="vitreous", counters={"Gem": 1}, effectsDisabled=True)
        self.cleanse(session, mine)
        self.assertEqual(mine["counters"], {"Gem": 1})
        self.assertEqual(mine["chosenTemperament"], "vitreous")
        self.assertTrue(session.rules_item_effects_active(mine))
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertFalse(session.rules_engine["actionStack"])

    def test_cleanse_preserves_printed_float(self):
        session, _, _, mine, _ = self.started()
        mine.update(cardId=self.HALTAN, hasFloat=True)
        self.cleanse(session, mine)
        self.assertNotIn("hasFloat", mine)
        self.assertTrue(session.rules_item_has_float(mine))

    def test_cleanse_source_restores_its_blanked_continuous_link_without_new_etb(self):
        session, _, _, mine, _ = self.started()
        source = self.field_item("jaw", "p1", self.JAW, "field", effectsDisabled=True)
        session.battlefield.append(source)
        session.create_rules_ongoing_effects({"id": "jaw-link", "controllerId": "p1",
            "source": {"itemId": "jaw", "cardId": self.JAW}, "targets": [{"kind": "card", "itemId": "mine"}],
            "ability": self.ability(self.JAW, "flaying-jaw-power-link")})
        self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 3)
        self.cleanse(session, source)
        self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 1)
        self.assertEqual(len(session.rules_engine["ongoingEffects"]), 1)
        self.assertIsNone(session.rules_engine["pendingChoice"])

    def test_leave_and_return_uses_fresh_state_and_does_not_inherit_old_modifiers(self):
        for zone in ("hand", "graveyard", "deck"):
            with self.subTest(zone=zone):
                session, _, _, mine, _ = self.started()
                mine.update(counters={"Gem": 2, "power": 4}, effectsDisabled=True, gummoCopy="m-1", hasFloat=True)
                old = copy.deepcopy(mine)
                session._rules_remove_field_item(mine, "p1", zone)
                session.prune_rules_ongoing_effects()
                result = session.apply_rules_action_result({"id": "return", "controllerId": "p1",
                    "source": {"cardId": "test"}, "targets": [{"kind": "zone_card", "containerId": "p1", "zone": zone, "cardId": "m-0"}],
                    "ability": {"result": {"kind": "move_zone_target_to_field_zone", "asSupport": True}}})
                returned = next(item for item in session.battlefield if item["cardId"] == "m-0")
                self.assertNotEqual(returned["id"], old["id"])
                self.assertEqual(returned["counters"], {})
                self.assertFalse(any(key in returned for key in ("effectsDisabled", "gummoCopy", "hasFloat")))
                self.assertEqual(session.rules_manifestation_characteristics(returned)["power"], 3)

    def test_link_can_choose_a_new_target_after_previous_target_left_the_field(self):
        session, _, _, mine, foe = self.started()
        source = self.field_item("jaw", "p1", self.JAW, "field")
        session.battlefield.append(source)
        session.create_rules_ongoing_effects({"id": "jaw-link", "controllerId": "p1",
            "source": {"itemId": "jaw", "cardId": self.JAW}, "targets": [{"kind": "card", "itemId": "mine"}],
            "ability": self.ability(self.JAW, "flaying-jaw-power-link")})
        session._rules_remove_field_item(mine, "p1", "hand")
        session.prune_rules_ongoing_effects()
        result = self.result(session, {"kind": "retarget_source_effect", "effectKind": "power_modifier"}, source="jaw", target="foe")
        self.assertEqual(result["status"], "retargeted")
        self.assertEqual(session.rules_manifestation_characteristics(foe)["power"], 3)

    def test_suspension_then_return_discards_modifiers_and_counters(self):
        session, _, _, mine, _ = self.started()
        session.battlefield.append(self.field_item("bob", "p2", self.BOB, counters={"power": 3}))
        mine.update(counters={"Gem": 2, "power": 4}, effectsDisabled=True, hasFloat=True)
        result = session._rules_remove_field_item_by_effect(mine, "p1", "graveyard", reason="destroy")
        self.assertEqual(result["status"], "suspended")
        self.assertIsNone(session.restore_suspended_card(result["suspensionId"], "hand")[0])
        session.apply_rules_action_result({"id": "return", "controllerId": "p1", "source": {},
            "targets": [{"kind": "zone_card", "containerId": "p1", "zone": "hand", "cardId": "m-0"}],
            "ability": {"result": {"kind": "move_zone_target_to_field_zone", "asSupport": True}}})
        returned = next(item for item in session.battlefield if item["cardId"] == "m-0")
        self.assertNotEqual(returned["id"], mine["id"])
        self.assertEqual(returned["counters"], {})
        self.assertTrue(session.rules_item_effects_active(returned))
        self.assertFalse(session.rules_item_has_float(returned))

    def test_interzone_to_support_keeps_same_instance_and_its_resources(self):
        session, _, _, mine, _ = self.started()
        mine.update(fieldZone="interzone", counters={"Gem": 2, "power": 1})
        session.mark_rules_support_entry(mine)
        session.prune_rules_ongoing_effects()
        self.assertIs(session.find_battlefield_item("mine"), mine)
        self.assertEqual(mine["counters"], {"Gem": 2, "power": 1})
        self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 4)

    def test_resolved_modifier_survives_source_departure_until_target_is_cleansed(self):
        session, _, _, mine, foe = self.started()
        session.create_rules_ongoing_effects({"id": "resolved", "controllerId": "p2",
            "source": {"itemId": "foe"}, "targets": [{"kind": "card", "itemId": "mine"}],
            "ability": {"id": "boost", "ongoingEffect": {"kind": "power_modifier", "value": 2, "duration": "while_target_on_field"}}})
        session._rules_remove_field_item(foe, "p2", "graveyard")
        session.prune_rules_ongoing_effects()
        self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 5)
        self.cleanse(session, mine)
        self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 3)

    def test_cleansing_a_source_does_not_cancel_its_already_queued_effect(self):
        session, _, _, mine, foe = self.started()
        action = {"id": "queued", "kind": "activated_effect", "controllerId": "p1",
            "source": {"itemId": "mine", "cardId": mine["cardId"]},
            "targets": [{"kind": "card", "itemId": "foe"}],
            "ability": {"id": "queued", "result": {"kind": "adjust_target_power", "value": -1}}}
        session.rules_engine["actionStack"].append(action)
        self.cleanse(session, mine)
        self.assertEqual([a["id"] for a in session.rules_engine["actionStack"]], ["queued"])
        session.resolve_rules_top_action()
        self.assertEqual(session.rules_manifestation_characteristics(foe)["power"], 4)

    def test_cleanse_link_stays_removed_then_paid_retarget_restores_it(self):
        for cid in (self.JAW, self.NECTAR, self.HUSK, self.INFLORESCENCE):
            with self.subTest(card=cid):
                session, _, _, mine, foe = self.started()
                source = self.field_item("will", "p1", cid, "field", x=600, y=800, rotation=0)
                session.battlefield.append(source)
                ability, activation = self.ABILITIES[cid]
                session.create_rules_ongoing_effects({"id": "link", "controllerId": "p1",
                    "source": {"itemId": "will", "cardId": cid}, "targets": [{"kind": "card", "itemId": "mine"}], "ability": ability})
                self.cleanse(session, mine)
                session.prune_rules_ongoing_effects()
                session.serialize_for("p1", "player")
                self.assertFalse(session.rules_engine["ongoingEffects"])
                self.assertTrue(session.rules_item_effects_active(mine))
                session.phase_tracker["index"] = game_tests.ADVANCED_PHASES.index("end_actions")
                session.rules_engine["priorityPlayerId"] = "p1"
                session.add_rules_excess_essence("p1", [{"temperament": "transcendent", "amount": 3}])
                error, action = session.declare_rules_action("p1", "Retarget", kind="activated_effect",
                    source={"zone": "battlefield", "itemId": "will", "cardId": cid}, ability_id=activation["id"],
                    targets=[{"kind": "card", "itemId": "foe", "cardId": foe["cardId"]}])
                self.assertIsNone(error)
                self.assertEqual(source["rotation"], 90)
                session.resolve_rules_top_action()
                self.assertEqual(len(session.rules_engine["ongoingEffects"]), 1)
                effect = session.rules_engine["ongoingEffects"][0]
                self.assertEqual(effect["target"]["itemId"], "foe")
                self.assertEqual(effect["kind"], ability["ongoingEffect"]["kind"])
                self.assertFalse(session.rules_engine["actionStack"])

    def test_nectar_retarget_is_restricted_to_end_phase(self):
        session, _, _, _, foe = self.started()
        source = self.field_item("nectar", "p1", self.NECTAR, "field", x=600, y=800, rotation=0)
        session.battlefield.append(source)
        session.add_rules_excess_essence("p1", [{"temperament": "transcendent", "amount": 2}])
        before = copy.deepcopy((session.battlefield, session.tokens))
        error, _ = session.declare_rules_action("p1", "Retarget", kind="activated_effect",
            source={"zone": "battlefield", "itemId": "nectar", "cardId": self.NECTAR},
            ability_id="nectar-retarget-disable", targets=[{"kind": "card", "itemId": "foe", "cardId": foe["cardId"]}])
        self.assertIsNotNone(error)
        self.assertEqual(before, (session.battlefield, session.tokens))

    def test_cleanse_cancels_will_animation_immediately_without_leaving_the_field(self):
        session, _, _, mine, _ = self.started()
        mine.update(cardId=self.SPLENDOR, fieldZone="field", chosenTemperament="choleric", counters={"Gem": 2})
        self.result(session, {"kind": "will_becomes_support_manifestation"})
        self.assertEqual(session.rules_item_card_rules(mine)["type"], "manifestation")
        self.cleanse(session, mine)
        self.assertIs(session.find_battlefield_item("mine"), mine)
        self.assertEqual(session.rules_item_card_rules(mine)["type"], "persistent_will")
        self.assertEqual(mine["fieldZone"], "field")
        self.assertNotIn("willManifestation", mine)
        self.assertEqual(mine["counters"], {"Gem": 2})
        self.assertTrue(session.rules_item_effects_active(mine))
        self.assertNotIn(mine, session.rules_confrontation_items())

    def test_cleanse_keeps_exile_on_win_memory_and_it_still_resolves(self):
        session, p1, _, mine, foe = self.started()
        self.result(session, {"kind": "exile_target_on_win"})
        memory_id = session.rules_engine["effectMemories"][0]["id"]
        mine["counters"]["power"] = 2
        self.cleanse(session, mine)
        self.assertEqual(session.rules_engine["effectMemories"][0]["id"], memory_id)
        foe["counters"]["power"] = -4
        session.phase_tracker["index"] = game_tests.ADVANCED_PHASES.index("resolution_compare")
        self.assertEqual(session.prepare_rules_confrontation_result()["winnerId"], "p1")
        session.begin_rules_confrontation_cleanup()
        self.assertIn("m-0", p1["zones"]["exile"])
        self.assertFalse(session.rules_engine["effectMemories"])

    def test_memories_survive_limbo_and_hand_but_end_in_deck_or_exile(self):
        for zone in ("graveyard", "hand", "deck", "exile"):
            with self.subTest(zone=zone):
                session, _, _, mine, _ = self.started()
                self.result(session, {"kind": "exile_target_on_win"})
                self.cleanse(session, mine)
                session._rules_remove_field_item(mine, "p1", zone)
                self.assertEqual(bool(session.rules_engine["effectMemories"]), zone in {"graveyard", "hand"})

    def test_cleanse_can_reveal_zero_power_due_to_a_printed_passive(self):
        session, p1, _, mine, _ = self.started()
        mine.update(fieldZone="interzone", counters={"power": 2})
        session.card_rules["printed-penalty"] = {"type": "manifestation", "power": 3, "passiveEffects": [{
            "kind": "interzone_allies_penalty", "value": -4}]}
        session.battlefield.append(self.field_item("penalty", "p1", "printed-penalty", "interzone"))
        self.assertEqual(session.rules_manifestation_characteristics(mine)["power"], 1)
        self.cleanse(session, mine)
        self.assertIsNone(session.find_battlefield_item("mine"))
        self.assertIn("m-0", p1["zones"]["graveyard"])

    def test_external_printed_blanking_still_applies_after_cleanse(self):
        session, _, _, mine, _ = self.started()
        session.card_rules["printed-blanker"] = {"type": "manifestation", "power": 3,
            "passiveEffects": [{"kind": "disable_other_effects"}]}
        source = self.field_item("blanker", "p2", "printed-blanker")
        session.battlefield.append(source)
        self.cleanse(session, mine)
        self.assertFalse(session.rules_item_effects_active(mine))
        session._rules_remove_field_item(source, "p2", "hand")
        self.assertTrue(session.rules_item_effects_active(mine))
