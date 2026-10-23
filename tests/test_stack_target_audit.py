"""Stack resolution uses live targets and preserves independent/dependent roles."""
import copy

import test_game_state as game_tests


class StackTargetAuditTests(game_tests.RealCardRulesCase):
    MULTICASTIGATE = "inner-deserts-138"
    SPLENDOR = "inner-deserts-143"
    OPPRESS = "obn1uv72ewxv3y5_en"
    SABOTEUR = "ymcx9cg62eg0vgm_en"
    SHATTERING = "k7dq8ye448xwj54_en"
    EXCHANGE = "0ujeinffs84nrvq_en"
    ALL = (MULTICASTIGATE, SPLENDOR, OPPRESS, SABOTEUR, SHATTERING, EXCHANGE)

    def started(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker["index"] = game_tests.ADVANCED_PHASES.index("confrontation_reaction")
        session.rules_engine.update(readyPlayerIds=["p1", "p2"], firstManifestationComplete=True, priorityPlayerId="p1")
        session.card_rules["m-0"]["power"] = 6
        session.card_rules["m-1"]["power"] = 6
        first = self.field_item("first", "p2", "m-0", isSupport=True)
        second = self.field_item("second", "p2", "m-1", isSupport=True)
        session.battlefield = [first, second]
        return session, p1, p2, first, second

    @staticmethod
    def target(item):
        return {"kind": "card", "itemId": item["id"], "cardId": item["cardId"], "ownerId": item["ownerId"]}

    def spell(self, session, card_id, items):
        action = {"id": "spell", "controllerId": "p1", "kind": "play_card", "sourceOnStack": True,
            "source": {"cardId": card_id, "cardType": "ephemeral_will", "ownerId": "p1", "zone": "hand"},
            "targets": [self.target(item) for item in items], "ability": copy.deepcopy(self.ABILITIES[card_id][0])}
        session.rules_engine["actionStack"].append(action)
        return action

    def protect(self, session, item):
        session.rules_engine["ongoingEffects"].append({"id": "wall", "kind": "protection",
            "target": self.target(item), "duration": "until_end_of_turn", "startedTurn": session.phase_tracker["turn"]})

    def test_multicastigate_resolves_remaining_target_without_refund_or_rewriting_history(self):
        for invalidation in ("missing", "protected", "not_support", "changed_type", "stalemate"):
            for invalid_index in (0, 1):
                with self.subTest(invalidation=invalidation, invalid_index=invalid_index):
                    session, p1, p2, first, second = self.started()
                    action = self.spell(session, self.MULTICASTIGATE, [first, second])
                    original = copy.deepcopy(action["targets"])
                    invalid, valid = [first, second][invalid_index], [first, second][1 - invalid_index]
                    if invalidation == "missing":
                        session.battlefield.remove(invalid)
                    elif invalidation == "protected":
                        self.protect(session, invalid)
                    elif invalidation == "not_support":
                        invalid["isSupport"] = False
                    elif invalidation == "changed_type":
                        invalid["cardId"] = self.SPLENDOR
                    else:
                        invalid["fieldZone"] = "stalemate"
                    self.assertFalse(session.rules_top_action_has_no_valid_targets())
                    session.resolve_rules_top_action()
                    self.assertIsNone(session.find_battlefield_item(valid["id"]))
                    self.assertIn(valid["cardId"], p2["zones"]["graveyard"])
                    self.assertNotIn(invalid["cardId"], p2["zones"]["graveyard"])
                    self.assertEqual(p1["zones"]["graveyard"], [self.MULTICASTIGATE])
                    self.assertEqual(action["targets"], original)
                    self.assertEqual(action["invalidTargetIndices"], [invalid_index])

    def test_all_invalid_targets_have_no_effect_but_played_will_still_leaves_stack(self):
        session, p1, _, first, second = self.started()
        action = self.spell(session, self.MULTICASTIGATE, [first, second])
        for item in (first, second):
            self.protect(session, item)
        self.assertTrue(session.rules_top_action_has_no_valid_targets())
        session.resolve_rules_top_action()
        self.assertEqual(action["effectResult"]["kind"], "invalid_targets")
        self.assertEqual(len(session.battlefield), 2)
        self.assertEqual(p1["zones"]["graveyard"], [self.MULTICASTIGATE])

    def test_ongoing_modifier_only_attaches_to_remaining_valid_target(self):
        session, _, _, first, second = self.started()
        action = self.spell(session, self.OPPRESS, [first, second])
        action["ability"]["targets"].update(min=2, max=2)
        self.protect(session, first)
        session.resolve_rules_top_action()
        self.assertEqual(self.power_of(session, "first"), 6)
        self.assertEqual(self.power_of(session, "second"), 3)
        self.assertEqual([e["target"]["itemId"] for e in action["ongoingEffects"]], ["second"])

    def test_grouped_independent_effect_keeps_each_valid_target(self):
        session, _, p2, first, second = self.started()
        action = self.spell(session, self.MULTICASTIGATE, [first, second])
        action["ability"]["targetGroups"] = [copy.deepcopy(action["ability"]["targets"])] * 2
        for group in action["ability"]["targetGroups"]:
            group.update(min=1, max=1)
        self.protect(session, first)
        session.resolve_rules_top_action()
        self.assertIs(session.find_battlefield_item("first"), first)
        self.assertIn(second["cardId"], p2["zones"]["graveyard"])

    def test_dependent_counter_transfer_needs_both_targets(self):
        for grouped in (False, True):
            for invalid_index in (0, 1):
                with self.subTest(grouped=grouped, invalid_index=invalid_index):
                    session, _, _, first, second = self.started()
                    first["counters"] = {"Gem": 2}
                    action = self.spell(session, self.MULTICASTIGATE, [first, second])
                    contract = {"min": 2, "max": 2, "cardType": "manifestation"}
                    action["ability"] = {"id": "transfer", "targets": contract,
                        "result": {"kind": "move_counter", "counter": "Gem", "value": 1}}
                    if grouped:
                        action["ability"]["targetGroups"] = [{**contract, "min": 1, "max": 1}] * 2
                    self.protect(session, [first, second][invalid_index])
                    session.resolve_rules_top_action()
                    self.assertEqual(first["counters"], {"Gem": 2})
                    self.assertEqual(second["counters"], {})
                    self.assertEqual(action["effectResult"]["status"], "target_missing")

    def test_partial_resolution_does_not_accept_wrong_declaration_cardinality(self):
        session, _, _, first, second = self.started()
        action = self.spell(session, self.MULTICASTIGATE, [first, second])
        action["ability"]["targets"].update(min=1, max=1)
        self.protect(session, first)
        session.resolve_rules_top_action()
        self.assertEqual(action["effectResult"]["kind"], "invalid_targets")
        self.assertIs(session.find_battlefield_item("second"), second)

    def test_shattering_discards_even_when_its_manifestation_target_is_protected(self):
        session, _, p2, first, _ = self.started()
        self.put(p2, "deck", ["m-2", "m-3", "m-4"])
        action = self.spell(session, self.SHATTERING, [first])
        action["targets"].insert(0, {"kind": "player", "playerId": "p2"})
        self.protect(session, first)
        session.resolve_rules_top_action()
        self.assertEqual(p2["zones"]["deck"], [])
        self.assertEqual(set(p2["zones"]["graveyard"]), {"m-2", "m-3", "m-4"})
        self.assertEqual(self.power_of(session, "first"), 6)
        self.assertEqual(action["effectResult"]["effects"], 0)

    def test_control_exchange_does_not_take_half_of_a_protected_pair(self):
        session, _, _, first, second = self.started()
        second["ownerId"] = "p1"
        for item in (first, second):
            item["fieldZone"] = "interzone"
        action = self.spell(session, self.EXCHANGE, [first, second])
        self.protect(session, first)
        session.resolve_rules_top_action()
        self.assertEqual(action["effectResult"]["status"], "target_missing")
        self.assertEqual(session.rules_item_controller_id(first), "p2")
        self.assertEqual(session.rules_item_controller_id(second), "p1")

    def test_resolved_stack_effect_keeps_its_controller_after_source_departure_or_control_change(self):
        for source_change in ("departure", "control"):
            with self.subTest(source_change=source_change):
                session, _, _, first, second = self.started()
                first["controllerId"] = "p1"
                action = {"id": "ability", "controllerId": "p1", "kind": "activated_effect",
                    "source": {"itemId": "first", "cardId": "m-0", "zone": "battlefield", "ownerId": "p2"},
                    "targets": [self.target(second)],
                    "ability": {"id": "boost", "targets": {"min": 1, "max": 1, "controller": "opponent"},
                        "ongoingEffect": {"kind": "power_modifier", "value": 2, "duration": "until_end_of_turn"}}}
                session.rules_engine["actionStack"].append(action)
                if source_change == "departure":
                    session.battlefield.remove(first)
                else:
                    first["controllerId"] = "p2"
                session.resolve_rules_top_action()
                self.assertEqual(self.power_of(session, "second"), 8)
                self.assertEqual(action["ongoingEffects"][0]["controllerId"], "p1")

    def take_control(self, session, item):
        source = self.field_item("saboteur", "p1", self.SABOTEUR, "interzone")
        session.battlefield.append(source)
        session.create_rules_ongoing_effects({"id": "take", "controllerId": "p1",
            "source": {"zone": "battlefield", "itemId": source["id"], "cardId": self.SABOTEUR},
            "targets": [self.target(item)], "ability": self.ABILITIES[self.SABOTEUR][0]})
        self.assertEqual(session.rules_item_controller_id(item), "p1")
        return source

    def test_target_contract_uses_active_control_link_and_tracks_blanking(self):
        session, _, _, first, _ = self.started()
        first["fieldZone"] = "interzone"
        source = self.take_control(session, first)
        target = [self.target(first)]
        contract = {"min": 1, "max": 1, "cardType": "manifestation", "controller": "self"}
        self.assertIsNone(session.rules_ability_targets_error(contract, target, "p1"))
        self.assertIsNotNone(session.rules_ability_targets_error(contract, target, "p2"))
        source["effectsDisabled"] = True
        self.assertIsNotNone(session.rules_ability_targets_error(contract, target, "p1"))
        self.assertIsNone(session.rules_ability_targets_error(contract, target, "p2"))

    def test_controller_requirement_is_rechecked_at_resolution(self):
        session, _, _, first, _ = self.started()
        action = self.spell(session, self.OPPRESS, [first])
        action["ability"]["targets"]["controller"] = "opponent"
        self.take_control(session, first)
        session.resolve_rules_top_action()
        self.assertEqual(action["effectResult"]["kind"], "invalid_targets")
        self.assertEqual(self.power_of(session, "first"), 6)

    def test_live_animated_type_is_used_without_changing_printed_zone_cards(self):
        session, p1, _, first, _ = self.started()
        first["cardId"] = self.SPLENDOR
        first["willManifestation"] = {"power": 6}
        target = [self.target(first)]
        contract = {"min": 1, "max": 1, "cardType": "manifestation"}
        self.assertIsNone(session.rules_ability_targets_error(contract, target, "p1"))
        self.assertIsNotNone(session.rules_ability_targets_error({**contract, "cardType": "persistent_will"}, target, "p1"))
        self.put(p1, "graveyard", [self.SPLENDOR])
        zone_target = [{"kind": "zone_card", "zone": "graveyard", "containerId": "p1", "ownerId": "p1", "cardId": self.SPLENDOR}]
        self.assertIsNotNone(session.rules_ability_targets_error({**contract, "zones": ["graveyard"]}, zone_target, "p1"))
        action = self.spell(session, self.OPPRESS, [first])
        session.revert_rules_will_manifestation(first)
        session.resolve_rules_top_action()
        self.assertEqual(action["effectResult"]["kind"], "invalid_targets")

    def test_grouped_stack_copy_requests_legal_targets_for_its_new_controller(self):
        session, _, _, first, second = self.started()
        second["ownerId"] = "p1"
        original = self.spell(session, self.MULTICASTIGATE, [first, second])
        original["controllerId"] = "p2"
        original["source"]["ownerId"] = "p2"
        original["ability"]["targetGroups"] = [
            {"min": 1, "max": 1, "cardType": "manifestation", "controller": "self"},
            {"min": 1, "max": 1, "cardType": "manifestation", "controller": "opponent"},
        ]
        result = session.apply_rules_action_result({"id": "copy", "controllerId": "p1", "source": {},
            "targets": [{"kind": "stack_action", "actionId": original["id"]}],
            "ability": {"id": "copy", "result": {"kind": "copy_stack_action"}}})
        self.assertEqual(result["kind"], "choice_required")
        choice = session.rules_engine["pendingChoice"]
        before = copy.deepcopy(session.rules_engine["actionStack"])
        error, _ = session.resolve_rules_choice("p1", choice["id"], option="keep")
        self.assertIsNotNone(error)
        self.assertEqual(before, session.rules_engine["actionStack"])
        error, _ = session.resolve_rules_choice("p1", choice["id"], option="retarget", targets=[self.target(second), self.target(first)])
        self.assertIsNone(error)
        copied = session.rules_engine["actionStack"][-1]
        self.assertTrue(copied["isStackCopy"])
        self.assertEqual(copied["controllerId"], "p1")
        session.resolve_rules_top_action()
        self.assertNotIn(self.MULTICASTIGATE, session.players["p1"]["zones"]["graveyard"])
        self.assertEqual(session.rules_engine["actionStack"], [original])
