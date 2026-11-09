"""Strict semantic coverage for five independent continuous-effect cards."""

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


BALANCE = "inner-deserts-137"
DISCOMBOBULATOR = "inner-deserts-092"
ASCIUGOTH = "inner-deserts-135"
OIL_DOG = "inner-deserts-133"
SOLITARY_COMBHAND = "inner-deserts-110"

EXPECTED_ABILITIES = {
    BALANCE: [{
        "id": "balance-redirects-points",
        "passiveEffect": {"kind": "balance_points"},
    }],
    DISCOMBOBULATOR: [
        {
            "id": "discombobulator-upkeep-or-exile",
            "trigger": {"event": "before_revelation"},
            "result": {
                "kind": "unless_payment_exile_source",
                "payment": "{H}{H}{H}{H}",
            },
        },
        {
            "id": "discombobulator-blanks-the-field",
            "passiveEffect": {"kind": "disable_other_effects"},
        },
    ],
    ASCIUGOTH: [{
        "id": "asciugoth-absorbs-entering-temperament",
        "passiveEffect": {"kind": "entering_manifestation_becomes_hollow"},
    }],
    OIL_DOG: [{
        "id": "excess-essence-is-hollow",
        "passiveEffect": {"kind": "excess_essence_as_hollow"},
    }],
    SOLITARY_COMBHAND: [{
        "id": "draw-for-empty-interzone-spaces",
        "passiveEffect": {"kind": "extra_recovery_draw_per_empty_interzone"},
    }],
}


class GroupedPassivesFamily(RealCardRulesCase):
    ALL = (
        BALANCE, DISCOMBOBULATOR, ASCIUGOTH, OIL_DOG,
        SOLITARY_COMBHAND,
    )

    def started(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker.update(
            index=ADVANCED_PHASES.index("confrontation_reaction"), turn=4,
        )
        session.rules_engine["readyPlayerIds"] = ["p1", "p2"]
        return session, p1, p2

    @staticmethod
    def target(item):
        return {
            "kind": "card", "itemId": item["id"],
            "cardId": item["cardId"], "ownerId": item["ownerId"],
        }

    def apply_ability(self, session, card_id, ability_id, item):
        return session.apply_rules_action_result({
            "id": "test-action", "controllerId": item["ownerId"],
            "source": {
                "cardId": card_id, "itemId": item["id"],
                "ownerId": item["ownerId"], "zone": "battlefield",
            },
            "targets": [],
            "ability": self.ability(card_id, ability_id),
        })

    @staticmethod
    def essence(session, player_id):
        return {
            token["temperament"]: token["counters"]["essence"]
            for token in session.tokens
            if token.get("isEssence") and token.get("ownerId") == player_id
            and int(token.get("counters", {}).get("essence") or 0) > 0
        }

    def test_compiles_all_five_exact_contracts(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        for card_id, abilities in EXPECTED_ABILITIES.items():
            with self.subTest(card_id=card_id):
                self.assertEqual(self.ABILITIES[card_id], abilities)
        self.assertEqual(
            rules[BALANCE]["passiveEffects"],
            [{"kind": "balance_points"}],
        )
        self.assertEqual(
            rules[DISCOMBOBULATOR]["triggeredAbilities"],
            [EXPECTED_ABILITIES[DISCOMBOBULATOR][0]],
        )
        self.assertEqual(
            rules[DISCOMBOBULATOR]["passiveEffects"],
            [{"kind": "disable_other_effects"}],
        )

    def test_balance_redirects_only_strict_richest_gain_and_poorest_loss(self):
        session, p1, p2 = self.started()
        p1["score"], p2["score"] = 100, 50
        session.battlefield = [self.field_item("balance", "p1", BALANCE, "field")]
        self.assertEqual(session.adjust_rules_score("p1", 20), 0)
        self.assertEqual((p1["score"], p2["score"]), (100, 70))
        self.assertEqual(session.adjust_rules_score("p2", -10), 0)
        self.assertEqual((p1["score"], p2["score"]), (90, 70))
        self.assertEqual(session.adjust_rules_score("p1", -5), -5)
        self.assertEqual(session.adjust_rules_score("p2", 4), 4)
        self.assertEqual((p1["score"], p2["score"]), (85, 74))

    def test_balance_uses_vessel_card_points_and_ties_do_not_redirect(self):
        session, p1, p2 = self.started()
        session.battlefield = [self.field_item("balance", "p1", BALANCE, "field")]
        session.card_points.update({"rich-card": 9, "poor-card": 1})
        self.put(p1, "receptacle", ["rich-card"])
        self.put(p2, "receptacle", ["poor-card"])
        self.assertEqual(session.adjust_rules_score("p1", 3), 0)
        self.assertEqual((p1["score"], p2["score"]), (0, 3))
        p1["score"], p2["score"] = 0, 8
        self.assertEqual(session.rules_vessel_total("p1"), 9)
        self.assertEqual(session.rules_vessel_total("p2"), 9)
        self.assertEqual(session.adjust_rules_score("p1", 2), 2)
        self.assertEqual((p1["score"], p2["score"]), (2, 8))

    def test_global_point_prevention_runs_before_balance(self):
        session, p1, p2 = self.started()
        p1["score"], p2["score"] = 20, 1
        session.battlefield = [self.field_item("balance", "p1", BALANCE, "field")]
        session.rules_engine["ongoingEffects"].append({
            "id": "halt-points", "kind": "prevent_point_changes",
            "duration": "until_end_of_turn", "startedTurn": 4,
        })
        self.assertEqual(session.adjust_rules_score("p1", 5), 0)
        self.assertEqual((p1["score"], p2["score"]), (20, 1))

    def test_discombobulator_can_pay_four_hollow_and_remain(self):
        session, _p1, _p2 = self.started()
        disco = self.field_item("disco", "p1", DISCOMBOBULATOR, "field")
        session.battlefield = [disco]
        session.add_rules_excess_essence(
            "p1", [{"temperament": "hollow", "amount": 4}],
        )
        payload = self.apply_ability(
            session, DISCOMBOBULATOR,
            "discombobulator-upkeep-or-exile", disco,
        )
        self.assertEqual(payload["choiceKind"], "effect_payment")
        choice = session.rules_engine["pendingChoice"]
        error, result = session.resolve_rules_choice(
            "p1", choice["id"], option="pay",
        )
        self.assertIsNone(error, error)
        self.assertEqual(result["status"], "paid")
        self.assertIn(disco, session.battlefield)
        self.assertEqual(self.essence(session, "p1"), {})

    def test_discombobulator_decline_exiles_it_and_releases_other_cards(self):
        session, p1, _p2 = self.started()
        disco = self.field_item("disco", "p1", DISCOMBOBULATOR, "field")
        other = self.field_item("other", "p2", "m-1", "confrontation")
        session.battlefield = [disco, other]
        self.assertFalse(session.rules_item_effects_active(other))
        self.apply_ability(
            session, DISCOMBOBULATOR,
            "discombobulator-upkeep-or-exile", disco,
        )
        choice = session.rules_engine["pendingChoice"]
        error, result = session.resolve_rules_choice(
            "p1", choice["id"], option="decline",
        )
        self.assertIsNone(error, error)
        self.assertTrue(result["exiled"])
        self.assertIn(DISCOMBOBULATOR, p1["zones"]["exile"])
        self.assertTrue(session.rules_item_effects_active(other))

    def test_first_discombobulator_blanks_later_copy_but_keeps_own_upkeep(self):
        session, _p1, _p2 = self.started()
        first = self.field_item("first-disco", "p1", DISCOMBOBULATOR, "field")
        second = self.field_item("second-disco", "p2", DISCOMBOBULATOR, "field")
        ordinary = self.field_item("ordinary", "p2", "m-1", "confrontation")
        session.battlefield = [ordinary, first, second]
        self.assertTrue(session.rules_item_effects_active(first))
        self.assertFalse(session.rules_item_effects_active(second))
        self.assertFalse(session.rules_item_effects_active(ordinary))
        actions = session.queue_rules_before_revelation_triggers(defer=True)
        self.assertEqual(
            [(action["source"]["itemId"], action["ability"]["id"])
             for action in actions],
            [("first-disco", "discombobulator-upkeep-or-exile")],
        )
        session.battlefield.remove(first)
        self.assertTrue(session.rules_item_effects_active(second))
        self.assertFalse(session.rules_item_effects_active(ordinary))

    def test_stalemate_is_outside_discombobulators_field_blanking(self):
        session, _p1, _p2 = self.started()
        session.card_rules["stalemate-probe"] = {
            "type": "manifestation", "power": 1,
            "temperaments": ["phlegmatic"],
            "passiveEffects": [{"kind": "stalemate_win_blocked"}],
        }
        disco = self.field_item("disco", "p1", DISCOMBOBULATOR, "field")
        probe = self.field_item("probe", "p2", "stalemate-probe", "stalemate")
        session.battlefield = [disco, probe]
        self.assertTrue(session.rules_item_effects_active(probe))
        disco["fieldZone"] = "stalemate"
        probe["fieldZone"] = "confrontation"
        self.assertFalse(session.rules_item_effects_active(disco))
        self.assertTrue(session.rules_item_effects_active(probe))

    def test_asciugoth_absorbs_entering_temperament_and_hollows_card_and_token(self):
        session, _p1, _p2 = self.started()
        session.card_rules["m-1"]["temperaments"] = ["choleric"]
        asci = self.field_item("asci", "p1", ASCIUGOTH, "field")
        entering = self.field_item("entering", "p2", "m-1", "confrontation")
        session.battlefield = [asci, entering]
        session.queue_rules_manifestation_entry_watchers(entering, defer=True)
        self.assertEqual(self.essence(session, "p1"), {"choleric": 1})
        self.assertEqual(
            session.rules_manifestation_characteristics(entering)["temperament"],
            "hollow",
        )
        token = session.create_rules_token_copy("m-1", "p2")
        self.assertEqual(
            session.rules_manifestation_characteristics(token)["temperament"],
            "hollow",
        )
        self.assertEqual(self.essence(session, "p1"), {"choleric": 2})

    def test_asciugoth_does_not_absorb_itself_and_first_source_wins_ties(self):
        session, _p1, _p2 = self.started()
        lone = self.field_item("lone", "p1", ASCIUGOTH, "field")
        session.battlefield = [lone]
        session.queue_rules_manifestation_entry_watchers(lone, defer=True)
        self.assertNotIn("temperamentOverride", lone)
        self.assertEqual(self.essence(session, "p1"), {})

        first = self.field_item("first", "p1", ASCIUGOTH, "field")
        second = self.field_item("second", "p2", ASCIUGOTH, "field")
        entering = self.field_item("entering", "p2", "m-2", "confrontation")
        session.battlefield = [first, second, entering]
        session.queue_rules_manifestation_entry_watchers(entering, defer=True)
        self.assertEqual(self.essence(session, "p1"), {"phlegmatic": 1})
        self.assertEqual(self.essence(session, "p2"), {})

    def test_cleanse_restores_asciugoths_original_temperament(self):
        session, _p1, _p2 = self.started()
        session.card_rules["m-1"]["temperaments"] = ["melancholic"]
        asci = self.field_item("asci", "p1", ASCIUGOTH, "field")
        entering = self.field_item("entering", "p2", "m-1", "confrontation")
        session.battlefield = [asci, entering]
        session.queue_rules_manifestation_entry_watchers(entering, defer=True)
        result = session.apply_rules_action_result({
            "id": "cleanse", "controllerId": "p2",
            "source": {"cardId": "inner-deserts-145"},
            "targets": [self.target(entering)],
            "ability": {"result": {"kind": "cleanse_target"}},
        })
        self.assertEqual(result["status"], "cleansed")
        self.assertEqual(
            session.rules_manifestation_characteristics(entering)["temperament"],
            "melancholic",
        )

    def test_oil_dog_changes_payment_view_without_mutating_stored_essence(self):
        session, _p1, _p2 = self.started()
        dog = self.field_item("dog", "p1", OIL_DOG, "interzone")
        session.battlefield = [dog]
        session.add_rules_excess_essence(
            "p1", [{"temperament": "transcendent", "amount": 3}],
        )
        self.assertEqual(self.essence(session, "p1"), {"transcendent": 3})
        remaining, spent = session.rules_essence_payment_plan(
            "p1", {"hollow": 3},
        )
        self.assertEqual(remaining, {"hollow": 0})
        self.assertEqual(sum(entry["amount"] for entry in spent), 3)
        remaining, spent = session.rules_essence_payment_plan(
            "p1", {"choleric": 1},
        )
        self.assertEqual((remaining, spent), ({"choleric": 1}, []))
        session.battlefield.remove(dog)
        remaining, spent = session.rules_essence_payment_plan(
            "p1", {"choleric": 1},
        )
        self.assertEqual(remaining, {"choleric": 0})
        self.assertEqual(sum(entry["amount"] for entry in spent), 1)
        self.assertEqual(self.essence(session, "p1"), {"transcendent": 3})

    def test_multiple_oil_dogs_do_not_stack_and_one_remaining_keeps_effect(self):
        session, _p1, _p2 = self.started()
        first = self.field_item("dog-1", "p1", OIL_DOG, "field")
        second = self.field_item("dog-2", "p2", OIL_DOG, "field")
        session.battlefield = [first, second]
        session.add_rules_excess_essence(
            "p1", [{"temperament": "capricious", "amount": 2}],
        )
        for removed in (None, first):
            if removed is not None:
                session.battlefield.remove(removed)
            remaining, spent = session.rules_essence_payment_plan(
                "p1", {"capricious": 2},
            )
            self.assertEqual((remaining, spent), ({"capricious": 2}, []))
        session.battlefield.remove(second)
        remaining, spent = session.rules_essence_payment_plan(
            "p1", {"capricious": 2},
        )
        self.assertEqual(remaining, {"capricious": 0})
        self.assertEqual(sum(entry["amount"] for entry in spent), 2)

    def test_oil_dog_does_not_turn_an_unspent_gem_counter_into_essence(self):
        session, _p1, _p2 = self.started()
        dog = self.field_item("dog", "p1", OIL_DOG, "field")
        gem = self.field_item(
            "gem", "p1", "gem-probe", "field", counters={"Gem": 1},
        )
        session.card_rules["gem-probe"] = {"type": "persistent_will"}
        session.battlefield = [dog, gem]
        self.assertEqual(
            session.rules_essence_payment_plan("p1", {"hollow": 1}),
            ({"hollow": 1}, []),
        )
        session.add_rules_excess_essence(
            "p1", [{"temperament": "choleric", "amount": 1}],
        )
        remaining, spent = session.rules_essence_payment_plan(
            "p1", {"hollow": 1},
        )
        self.assertEqual(remaining, {"hollow": 0})
        self.assertEqual(sum(entry["amount"] for entry in spent), 1)
        self.assertEqual(gem["counters"]["Gem"], 1)

    def test_solitary_combhand_counts_current_empty_interzone_slots(self):
        session, p1, _p2 = self.started()
        solitary = self.field_item(
            "solitary", "p1", SOLITARY_COMBHAND, "interzone",
        )
        session.battlefield = [solitary]
        self.put(p1, "deck", [f"m-{index}" for index in range(12)])
        error, result = session._draw_rules_recovery_hand("p1")
        self.assertIsNone(error, error)
        self.assertEqual((result["handLimit"], result["count"]), (9, 9))
        session.battlefield.extend([
            self.field_item("slot-2", "p1", "m-10", "interzone"),
            self.field_item("slot-3", "p1", "m-11", "interzone"),
        ])
        self.assertEqual(session.rules_recovery_hand_limit("p1"), 7)

    def test_solitary_combhand_counts_float_stacks_as_one_slot(self):
        session, _p1, _p2 = self.started()
        solitary = self.field_item(
            "solitary", "p1", SOLITARY_COMBHAND, "interzone",
        )
        anchor = self.field_item("anchor", "p1", "m-1", "interzone")
        stacked = self.field_item(
            "stacked", "p1", "m-2", "interzone", stackedOn="anchor",
        )
        session.battlefield = [solitary, anchor, stacked]
        self.assertEqual(session.rules_interzone_slot_count("p1"), 2)
        self.assertEqual(session.rules_recovery_hand_limit("p1"), 8)

    def test_solitary_combhand_uses_extended_capacity_not_printed_three(self):
        session, _p1, _p2 = self.started()
        session.card_rules["extender"] = {
            "type": "manifestation", "power": 1,
            "temperaments": ["phlegmatic"],
            "passiveEffects": [{"kind": "extend_interzone", "value": 3}],
        }
        solitary = self.field_item(
            "solitary", "p1", SOLITARY_COMBHAND, "interzone",
        )
        extender = self.field_item("extender", "p1", "extender", "interzone")
        session.battlefield = [solitary, extender]
        self.assertEqual(session.rules_interzone_capacity("p1"), 6)
        self.assertEqual(session.rules_interzone_slot_count("p1"), 2)
        self.assertEqual(session.rules_recovery_hand_limit("p1"), 11)

    def test_solitary_combhand_outside_interzone_grants_no_extra_draw(self):
        session, _p1, _p2 = self.started()
        solitary = self.field_item(
            "solitary", "p1", SOLITARY_COMBHAND, "confrontation",
        )
        session.battlefield = [solitary]
        self.assertEqual(session.rules_recovery_hand_limit("p1"), 7)


if __name__ == "__main__":
    import unittest

    unittest.main()
