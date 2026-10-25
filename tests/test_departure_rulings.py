"""Creator rulings: printed stats after departure; a zone return is a new entry."""
import copy

import test_game_state as game_tests
import test_departure_resolution_audit as departures
import test_quantitative_card_audit as numeric


class DepartureRulingTests(game_tests.RealCardRulesCase):
    MUKKABELL = "inner-deserts-012"
    ENTRUST = "ud9clfoj2c6x96o_en"
    REFEREN = "inner-deserts-038"
    LOMBRIC = "inner-deserts-014"
    PACHY = "9ypw4x4igfon1qi_en"
    RECOVER = "0coh7nrbvcvan1i_en"
    REFORGE = "z2fen73ktw8pbqz_en"
    DISSOLVE = "inner-deserts-019"
    ALL = (MUKKABELL, ENTRUST, REFEREN, LOMBRIC, PACHY, RECOVER, REFORGE, DISSOLVE)
    target = staticmethod(departures.DepartureResolutionAuditTests.target)
    chain = departures.DepartureResolutionAuditTests.chain
    declare = numeric.QuantitativeCardAuditTests.declare

    def started(self):
        result = departures.DepartureResolutionAuditTests.started(self)
        result[0].add_rules_excess_essence("p1", [{"temperament": "transcendent", "amount": 100}])
        return result

    def roundtrip(self, session, cid, through="hand", zone="graveyard", container="p1"):
        recipient = "p1" if through != "receptacle" else "p2"
        if through == "suspended":
            error, entry = session.suspend_zone_card(container, zone, cid)
            self.assertIsNone(error)
            error, _ = session.restore_suspended_card(entry["id"], zone)
            self.assertIsNone(error)
        else:
            for source, destination, actor, target in ((zone, through, container, recipient), (through, zone, recipient, container)):
                error, _, _ = session.move_zone_card_by_effect(actor, source, target, destination, cid)
                self.assertIsNone(error)

    def test_mukkabell_reads_modified_base_on_field_and_printed_base_after_departure(self):
        for zone in (None, "hand", "graveyard", "receptacle", "deck", "exile"):
            with self.subTest(destination=zone):
                session, p1, _, _, _ = self.started()
                session.card_rules["m-2"]["power"] = 4
                item = self.chain(session, self.MUKKABELL, cid="m-2")
                queued = session.queue_rules_chain_outcome_triggers(item, "wins_confrontation", "p1")
                self.assertEqual(len(queued), 1)
                # A response doubles base power after the trigger was created.
                self.declare(session, self.ENTRUST, [self.target(item)])
                session.resolve_rules_top_action()
                self.assertEqual(session.rules_manifestation_base_power(item), 8)
                item["counters"]["power"] = 3  # never part of the base-power count
                if zone:
                    session._rules_remove_field_item_by_effect(item, "p2" if zone == "receptacle" else "p1", zone)
                    session.prune_rules_ongoing_effects()
                session.rules_engine["actionStack"].extend(queued)
                session.resolve_rules_top_action()
                self.assertEqual(p1["score"], 20 if zone else 40)

    def test_referen_reads_current_power_only_while_its_original_instance_remains(self):
        for destination in (None, "hand", "graveyard", "exile"):
            with self.subTest(destination=destination):
                session, _, _, mine, _ = self.started()
                mine.update(cardId=self.REFEREN, counters={"power": 3})  # printed 2, current 5
                queued = session.queue_rules_triggers(self.REFEREN, "p1", "loses_confrontation",
                    item_id=mine["id"], event_controller_id="p1", defer=True)
                self.assertEqual(len(queued), 1)
                session.tokens = []
                if destination:
                    session._rules_remove_field_item_by_effect(mine, "p1", destination)
                session.rules_engine["actionStack"].extend(queued)
                session.resolve_rules_top_action()
                amount = sum(t["counters"]["essence"] for t in session.tokens if t.get("isEssence"))
                self.assertEqual(amount, 2 if destination else 5)

    def test_excess_power_effects_use_the_sources_printed_power_after_it_leaves(self):
        for cid, expected in ((self.LOMBRIC, (5, 0)), (self.PACHY, (0, -5))):
            for destination in ("hand", "graveyard", "exile"):
                with self.subTest(card=cid, destination=destination):
                    session, p1, p2, mine, foe = self.started()
                    mine.update(cardId=cid, counters={"power": 5})  # printed 5, current 10
                    session.card_rules["m-1"]["power"] = 3
                    foe["counters"]["power"] = 1  # opponent still on field at current 4
                    queued = session.queue_rules_triggers(cid, "p1", "wins_confrontation", item_id="mine",
                        event_controller_id="p1", target_player_id="p2", defer=True)
                    self.assertEqual(len(queued), 1)
                    session._rules_remove_field_item_by_effect(mine, "p1", destination)
                    session.rules_engine["actionStack"].extend(queued)
                    session.resolve_rules_top_action()
                    self.assertEqual((p1["score"], p2["score"]), expected)

    def test_recover_and_reforge_reject_the_old_limbo_entry_after_roundtrip(self):
        for cid in (self.RECOVER, self.REFORGE):
            for through in ("hand", "exile", "receptacle", "suspended"):
                with self.subTest(card=cid, through=through):
                    session, p1, _, _, _ = self.started()
                    session.put_zone_card("p1", "graveyard", "m-2", "p1")
                    action = self.declare(session, cid, [{"kind": "zone_card", "containerId": "p1", "zone": "graveyard", "cardId": "m-2"}])
                    self.roundtrip(session, "m-2", through)
                    self.assertTrue(session.rules_top_action_has_no_valid_targets())
                    session.resolve_rules_top_action()
                    self.assertEqual(action["effectResult"]["kind"], "invalid_targets")
                    self.assertIn("m-2", p1["zones"]["graveyard"])
                    self.assertNotIn("m-2", p1["zones"]["hand"])
                    self.assertFalse(any(i.get("cardId") == "m-2" for i in session.battlefield))

    def test_untouched_target_and_reordered_same_zone_remain_valid(self):
        for change in ("none", "reorder", "other-card-roundtrip"):
            with self.subTest(change=change):
                session, p1, _, _, _ = self.started()
                for cid in ("m-2", "m-3"):
                    session.put_zone_card("p1", "graveyard", cid, "p1")
                action = self.declare(session, self.RECOVER, [{"kind": "zone_card", "containerId": "p1", "zone": "graveyard", "cardId": "m-2"}])
                if change == "reorder":
                    error, _, _ = session.move_zone_card_by_effect("p1", "graveyard", "p1", "graveyard", "m-2", "bottom")
                    self.assertIsNone(error)
                elif change == "other-card-roundtrip":
                    self.roundtrip(session, "m-3")
                self.assertFalse(session.rules_top_action_has_no_valid_targets())
                session.resolve_rules_top_action()
                self.assertNotEqual(action["effectResult"]["kind"], "invalid_targets")
                self.assertIn("m-2", p1["zones"]["hand"])

    def test_public_vessel_targets_resolve_only_the_remaining_valid_entry(self):
        session, p1, _, _, _ = self.started()
        for cid in ("m-2", "m-3"):
            session.put_zone_card("p1", "receptacle", cid, "p2")
        action = self.declare(session, self.DISSOLVE, [
            {"kind": "zone_card", "containerId": "p1", "zone": "receptacle", "cardId": cid} for cid in ("m-2", "m-3")])
        # The owner of Vessel cards is p2; leave and reenter via their Limbo.
        error, _, _ = session.move_zone_card_by_effect("p1", "receptacle", "p2", "graveyard", "m-2")
        self.assertIsNone(error)
        error, _, _ = session.move_zone_card_by_effect("p2", "graveyard", "p1", "receptacle", "m-2")
        self.assertIsNone(error)
        self.assertFalse(session.rules_top_action_has_no_valid_targets())
        session.resolve_rules_top_action()
        self.assertEqual(action.get("invalidTargetIndices"), [0])
        self.assertIn("m-2", p1["zones"]["receptacle"])
        self.assertNotIn("m-3", p1["zones"]["receptacle"])
        self.assertEqual(p1["score"], 30)

    def test_inherited_copy_targets_keep_the_old_entry_but_new_targets_can_be_selected(self):
        session, p1, _, _, _ = self.started()
        session.put_zone_card("p1", "graveyard", "m-2", "p1")
        original = self.declare(session, self.RECOVER, [{"kind": "zone_card", "containerId": "p1", "zone": "graveyard", "cardId": "m-2"}])
        inherited = session.build_rules_stack_copy(original, "p1", "copy")
        self.roundtrip(session, "m-2")
        # An already-bound target cannot be laundered through target cleaning.
        error, _ = session.rules_action_targets(inherited["targets"], "p1")
        self.assertIsNotNone(error)
        session.rules_engine["actionStack"].append(inherited)
        session.resolve_rules_top_action()
        self.assertEqual(inherited["effectResult"]["kind"], "invalid_targets")
        error, fresh = session.rules_action_targets([{"kind": "zone_card", "containerId": "p1", "zone": "graveyard", "cardId": "m-2"}], "p1")
        self.assertIsNone(error)
        replacement = session.build_rules_stack_copy(original, "p1", "retargeted-copy")
        replacement["targets"] = fresh
        session.rules_engine["actionStack"].append(replacement)
        session.resolve_rules_top_action()
        self.assertIn("m-2", p1["zones"]["hand"])

    def test_target_enumeration_and_refused_declarations_do_not_mutate_identity(self):
        session, _, _, _, _ = self.started()
        session.put_zone_card("p1", "graveyard", "m-2", "p1")
        before = copy.deepcopy(session.rules_engine)
        contract = self.ABILITIES[self.RECOVER][0]["targets"]
        candidates = session.rules_legal_target_candidates(contract, "p1")
        self.assertEqual(session.rules_engine, before)
        self.assertEqual(len(candidates), 1)
        old = candidates[0]
        self.roundtrip(session, "m-2")
        before = copy.deepcopy((session.players, session.rules_engine, session.tokens))
        error, _ = session.rules_action_targets([old], "p1")
        self.assertIsNotNone(error)
        self.assertEqual((session.players, session.rules_engine, session.tokens), before)

    def test_new_source_instance_does_not_restore_modifiers_to_the_old_effect(self):
        session, p1, _, _, _ = self.started()
        session.card_rules["m-2"]["power"] = 4
        item = self.chain(session, self.MUKKABELL, cid="m-2")
        queued = session.queue_rules_chain_outcome_triggers(item, "wins_confrontation", "p1")
        self.declare(session, self.ENTRUST, [self.target(item)])
        session.resolve_rules_top_action()
        session._rules_remove_field_item_by_effect(item, "p1", "hand")
        error, returned = session.chain_rules_manifestation("p1", "hand", "m-2")
        self.assertIsNone(error)
        new_item = session.find_battlefield_item(returned["itemId"])
        self.declare(session, self.ENTRUST, [self.target(new_item)])
        session.resolve_rules_top_action()
        self.assertEqual(session.rules_manifestation_base_power(new_item), 8)
        session.rules_engine["actionStack"].extend(queued)
        session.resolve_rules_top_action()
        self.assertEqual(p1["score"], 20)

    def test_an_untouched_private_hand_target_can_also_be_bound_without_mutation(self):
        session, p1, _, _, _ = self.started()
        self.put(p1, "hand", ["m-2"])
        before = copy.deepcopy(session.rules_engine)
        error, targets = session.rules_action_targets([
            {"kind": "zone_card", "containerId": "p1", "zone": "hand", "cardId": "m-2"}], "p1")
        self.assertIsNone(error)
        self.assertEqual(session.rules_engine, before)
        self.roundtrip(session, "m-2", "graveyard", zone="hand")
        error, _ = session.rules_action_targets(targets, "p1")
        self.assertIsNotNone(error)
