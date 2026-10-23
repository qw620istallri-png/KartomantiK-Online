"""Payable must mean an actual legal payment, including alternate sources."""
import copy
import random
import unittest

import test_special_payments as special


class SpecialAffordabilityAuditTests(unittest.TestCase):
    case = special.SpecialPaymentTests()

    def assert_affordable_without_spending(self, session, cost, expected=True):
        before = copy.deepcopy((session.players, session.battlefield, session.tokens, session.rules_engine))
        self.assertEqual(session.rules_can_afford_tribute("p1", cost), expected)
        self.assertEqual((session.players, session.battlefield, session.tokens, session.rules_engine), before)

    def test_every_printed_interzone_tribute_is_counted_and_settles(self):
        for cid, metadata in self.case.real_rules().items():
            if not metadata.get("canPayTributeFromInterzone"):
                continue
            with self.subTest(cid=cid):
                session, p1, _ = self.case.started()
                self.case.put(p1, "hand", [])
                session.battlefield.append(self.case.field_item("tribute", "p1", cid, "interzone"))
                cost = "{H}"
                error, payment = session.rules_action_payment("p1", "activated_effect", None, ["battlefield|tribute"], {"tribute": cost})
                self.assertIsNone(error)
                self.assert_affordable_without_spending(session, cost)
                session.pay_rules_tribute("p1", payment)
                self.assertIsNone(session.find_battlefield_item("tribute"))

    def test_printed_limbo_tribute_and_formula_permission_are_counted_live(self):
        for printed in (True, False):
            with self.subTest(printed=printed):
                session, p1, _ = self.case.started()
                cid = "g3zumpyf623hto6_en" if printed else "m-3"
                self.case.put(p1, "hand", [])
                self.case.put(p1, "graveyard", [cid])
                if not printed:
                    session.battlefield.append(self.case.field_item("press", "p1", "ze99bj8uw2oisfx_en", "field", counters={"Formula": 1}))
                cost = "{H}" * int(session.card_rules[cid]["power"])
                error, payment = session.rules_action_payment("p1", "activated_effect", None, [f"graveyard|{cid}"], {"tribute": cost})
                self.assertIsNone(error)
                self.assert_affordable_without_spending(session, cost)
                session.pay_rules_tribute("p1", payment)
                self.assert_affordable_without_spending(session, "{H}", False)

    def test_vessel_tribute_is_white_and_respects_the_permission_controller(self):
        session, p1, _ = self.case.started()
        self.case.put(p1, "hand", [])
        self.case.put(p1, "receptacle", {"m-3": "p2"})
        session.card_rules["m-3"]["power"] = 2
        source = self.case.field_item("brabataba", "p1", "zhzp6kenpqrym9h_en", "field")
        session.battlefield.append(source)
        self.assert_affordable_without_spending(session, "{B}{R}")
        source["effectsDisabled"] = True
        self.assert_affordable_without_spending(session, "{B}{R}", False)
        source.pop("effectsDisabled")
        source["controllerId"] = "p2"
        self.assert_affordable_without_spending(session, "{B}{R}", False)

    def test_orator_allows_a_controlled_field_tribute_even_when_the_owner_differs(self):
        session, p1, _ = self.case.started()
        self.case.put(p1, "hand", [])
        session.battlefield = [
            self.case.field_item("orator", "p2", "birhlimm9e8lq3d_en", "field"),
            self.case.field_item("tribute", "p2", "m-3", controllerId="p1"),
        ]
        self.assert_affordable_without_spending(session, "{H}")
        error, payment = session.rules_action_payment("p1", "activated_effect", None, ["battlefield|tribute"], {"tribute": "{H}"})
        self.assertIsNone(error)
        session.pay_rules_tribute("p1", payment)
        self.assertIn("m-3", session.players["p2"]["zones"]["graveyard"])

    def test_convertible_gems_count_without_consuming_the_real_resource(self):
        session, p1, _ = self.case.started()
        self.case.put(p1, "hand", [])
        source = self.case.field_item("splendor", "p1", "inner-deserts-143", "field", counters={"Gem": 2}, chosenTemperament="choleric")
        session.battlefield.append(source)
        self.assert_affordable_without_spending(session, "{R}{R}")
        source["counters"]["Gem"] = 1
        self.assert_affordable_without_spending(session, "{R}{R}", False)

    def test_kanopo_sacrifice_and_tribute_cannot_use_the_same_field_card_twice(self):
        session, p1, _ = self.case.started()
        self.case.put(p1, "hand", ["inner-deserts-052"])
        donor = self.case.field_item("donor", "p1", "m-3", "interzone")
        session.battlefield = [donor]
        self.assert_affordable_without_spending(session, "{H}" * 6)
        error, payment = session.rules_action_payment("p1", "activated_effect", None,
            ["inner-deserts-052", "sacrifice|donor"], {"tribute": "{H}" * 6})
        self.assertIsNone(error)
        session.pay_rules_tribute("p1", payment)
        self.assertEqual(len(session.battlefield), 0)
        self.assert_affordable_without_spending(session, "{H}" * 6, False)

    def test_formula_budget_cannot_be_counted_once_for_each_limbo_card(self):
        session, p1, _ = self.case.started()
        self.case.put(p1, "hand", [])
        self.case.put(p1, "graveyard", ["m-3", "m-4"])
        source = self.case.field_item("press", "p1", "ze99bj8uw2oisfx_en", "field", counters={"Formula": 1})
        session.battlefield = [source]
        self.assert_affordable_without_spending(session, "{H}{H}", False)
        source["counters"]["Formula"] = 2
        self.assert_affordable_without_spending(session, "{H}{H}")

    def test_affordability_respects_the_settlement_limit_on_tribute_card_count(self):
        session, p1, _ = self.case.started()
        self.case.put(p1, "hand", [f"m-{i}" for i in range(8)])
        self.assert_affordable_without_spending(session, "{H}" * 8, False)

    def test_a_large_hand_cannot_hide_the_tribute_card_limit(self):
        session, p1, _ = self.case.started()
        self.case.put(p1, "hand", ["m-0"] * 30)
        self.assert_affordable_without_spending(session, "{H}" * 8, False)

    def test_a_kanopo_donor_cannot_also_contribute_its_own_tribute_power(self):
        session, p1, _ = self.case.started()
        self.case.put(p1, "hand", ["inner-deserts-052"])
        session.battlefield = [self.case.field_item("donor", "p1", "m-3", "interzone"),
            self.case.field_item("orator", "p2", "birhlimm9e8lq3d_en", "field")]
        self.assert_affordable_without_spending(session, "{H}" * 7, False)

    def test_counter_probe_does_not_change_the_games_random_stream(self):
        session, p1, _ = self.case.started()
        self.case.put(p1, "hand", [])
        session.battlefield.append(self.case.field_item("gem", "p1", "inner-deserts-143", "field",
            counters={"Gem": 1}, chosenTemperament="choleric"))
        state = random.getstate()
        self.assert_affordable_without_spending(session, "{R}")
        self.assertEqual(random.getstate(), state)

    def test_gem_payment_witness_can_be_executed_during_bullyboos_required_payment(self):
        session, p1, p2 = self.case.started()
        self.case.put(p1, "hand", [])
        self.case.put(p2, "hand", ["q6rha5kz42bkxle_en"])
        session.battlefield.append(self.case.field_item("gem", "p1", "inner-deserts-143", "field",
            counters={"Gem": 2}, chosenTemperament="vitreous"))
        session.rules_engine["pendingChoice"] = {"id": "reveal", "kind": "discard_from_hand", "playerId": "p2",
            "count": 1, "destination": "bullyboo_reveal", "chooserId": "p1", "sourceCardId": "gz2zjrxqc2rbcwq_en"}
        error, result = session.resolve_rules_choice("p2", "reveal", card_ids=["q6rha5kz42bkxle_en"])
        self.assertIsNone(error)
        self.assertEqual(result["status"], "payment_required")
        choice = session.rules_engine["pendingChoice"]
        for _ in range(2):
            error, _ = session.spend_rules_counter_essence("p1", "gem", "splendor-spends-a-gem-as-excess-essence")
            self.assertIsNone(error)
        error, result = session.resolve_rules_choice("p1", choice["id"], option="pay", card_ids=[])
        self.assertIsNone(error)
        self.assertEqual(result["status"], "paid")
        self.assertIsNone(session.rules_engine["pendingChoice"])
