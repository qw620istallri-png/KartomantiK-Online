"""Regression coverage for the combined-payment audit, using shipped cards."""
import copy
import unittest

import test_special_payments as special_payments


class CombinedPaymentAuditTests(unittest.TestCase):
    case = special_payments.SpecialPaymentTests()
    MARTYRIZE = "3gqrmx5jegwz8kb_en"
    CENSOR = "op83bq67vaf368q_en"
    RALLY = "5q6t7i5pzctbi8s_en"
    HOURGLASS = "lmx5uff1z53fo0g_en"
    SWINE = "l4suqymyd2ehsue_en"

    def pool(self, session, player_id="p1"):
        result = {}
        for token in session.tokens:
            if token.get("ownerId") == player_id and token.get("isEssence"):
                colour = token["temperament"]
                result[colour] = result.get(colour, 0) + token["counters"]["essence"]
        return result

    def test_additional_cost_cannot_reuse_the_only_tribute_copy(self):
        for source in [self.MARTYRIZE, self.CENSOR]:
            for extra in [False, True]:
                with self.subTest(source=source, extra=extra):
                    session, p1, _ = self.case.started()
                    from_limbo = source == self.CENSOR
                    self.case.put(p1, "hand", [self.SWINE] + ([] if from_limbo else [source]))
                    if from_limbo:
                        self.case.put(p1, "graveyard", [source])
                        session.battlefield.append(self.case.field_item("ergorath", "p1", "e1zg2gsn0tfqo1y_en", "field"))
                    ability = copy.deepcopy(self.case.ABILITIES[source][0])
                    if extra:
                        ability["optionalExtraEssence"] = {"temperament": "hollow", "max": 20}
                        session.card_rules[source]["playedAbilities"] = [ability]
                        session.add_rules_excess_essence("p1", [{"temperament": "hollow", "amount": 1}])
                    before = copy.deepcopy((session.players, session.tokens, session.battlefield, session.rules_engine))
                    error, action = session.declare_rules_action("p1", "Invalid overlap", kind="play_card",
                        source={"cardId": source, "zone": "graveyard" if from_limbo else "hand"},
                        ability_id=ability["id"], cost_card_id=self.SWINE,
                        payment_card_ids=[] if extra else [self.SWINE],
                        extra_payment_card_ids=[self.SWINE] if extra else [],
                        targets=[{"kind": "card", "itemId": "first-b", "cardId": "m-2"}] if from_limbo else [])
                    self.assertIsNotNone(error)
                    self.assertIsNone(action)
                    self.assertEqual((session.players, session.tokens, session.battlefield, session.rules_engine), before)

    def test_separate_copies_can_pay_tribute_and_additional_cost(self):
        session, p1, _ = self.case.started()
        self.case.put(p1, "hand", [self.MARTYRIZE, self.SWINE, self.SWINE])
        p1["zones"]["hand"].append(self.SWINE)
        self.case.put(p1, "deck", ["m-0", "m-3", "m-4"])
        error, action = session.declare_rules_action("p1", "Martyrize", kind="play_card",
            source={"cardId": self.MARTYRIZE, "zone": "hand"},
            ability_id=self.case.ABILITIES[self.MARTYRIZE][0]["id"],
            payment_card_ids=[self.SWINE], cost_card_id=self.SWINE)
        self.assertIsNone(error)
        self.assertEqual(action["cost"]["revealedCard"]["cardId"], self.SWINE)
        self.assertEqual(p1["zones"]["graveyard"].count(self.SWINE), 1)
        self.assertEqual(p1["zones"]["exile"].count(self.SWINE), 1)
        result = session.resolve_rules_top_action()["action"]["effectResult"]
        self.assertEqual(len(result["drawn"]), 2)

    def test_rally_optional_payment_combines_pool_surplus_and_extra_tribute(self):
        green5 = next(cid for cid, meta in self.case.real_rules().items()
                      if meta.get("type") == "manifestation" and meta.get("power") == 5
                      and meta.get("temperaments") == ["phlegmatic"] and meta.get("canPayTribute", True))
        for requested, available, extra_tribute, expected_count, expected_pool in [
            (0, 0, False, 0, {"phlegmatic": 3}),
            (2, 0, False, 2, {"phlegmatic": 1}),
            (3, 0, False, 3, {}),
            (4, 1, False, 4, {}),
            (3, 0, True, 5, {}),
        ]:
            with self.subTest(requested=requested, available=available, extra=extra_tribute):
                session, p1, _ = self.case.started()
                self.case.put(p1, "hand", [self.RALLY, green5] + ([self.SWINE] if extra_tribute else []))
                if available:
                    session.add_rules_excess_essence("p1", [{"temperament": "hollow", "amount": available}])
                error, action = session.declare_rules_action("p1", "Rally", kind="play_card",
                    source={"cardId": self.RALLY, "zone": "hand"},
                    ability_id=self.case.ABILITIES[self.RALLY][0]["id"], payment_card_ids=[green5],
                    extra_essence_count=requested, extra_payment_card_ids=[self.SWINE] if extra_tribute else [])
                self.assertIsNone(error)
                self.assertEqual(self.pool(session), expected_pool)
                self.assertEqual(action["cost"]["optionalExtraEssenceSpent"], expected_count)
                result = session.resolve_rules_top_action()["action"]["effectResult"]
                self.assertEqual(result["count"], expected_count)

    def test_rally_cannot_overspend_tribute_surplus(self):
        session, p1, _ = self.case.started()
        self.case.put(p1, "hand", [self.RALLY, self.SWINE])
        before = copy.deepcopy((session.players, session.tokens, session.rules_engine))
        error, action = session.declare_rules_action("p1", "Too much", kind="play_card",
            source={"cardId": self.RALLY, "zone": "hand"},
            ability_id=self.case.ABILITIES[self.RALLY][0]["id"],
            payment_card_ids=[self.SWINE], extra_essence_count=1)
        self.assertIsNotNone(error)
        self.assertIsNone(action)
        self.assertEqual((session.players, session.tokens, session.rules_engine), before)

    def test_multicolour_refunds_preserve_printed_distribution(self):
        for mechanism in ["compensate", "drildrill"]:
            with self.subTest(mechanism=mechanism):
                session, _, _ = self.case.started()
                if mechanism == "compensate":
                    session.rules_engine["actionStack"] = [{"id": "hourglass", "kind": "play_card",
                        "controllerId": "p2", "sourceOnStack": True,
                        "source": {"cardId": self.HOURGLASS, "ownerId": "p2", "zone": "hand"}}]
                    source = "inner-deserts-149"
                    targets = [{"kind": "stack_action", "actionId": "hourglass", "cardId": self.HOURGLASS}]
                else:
                    session.battlefield.append(self.case.field_item("hourglass", "p2", self.HOURGLASS, "field"))
                    source = "inner-deserts-131"
                    targets = [{"kind": "card", "itemId": "hourglass", "cardId": self.HOURGLASS}]
                result = session.apply_rules_action_result({"id": "refund", "controllerId": "p1",
                    "source": {"cardId": source, "ownerId": "p1"}, "targets": targets,
                    "ability": self.case.ABILITIES[source][0]})
                self.assertIn(result["status"], {"neutralized", "destroyed"})
                self.assertEqual(self.pool(session, "p2"), {"vitreous": 2, "capricious": 2})

    def test_compensate_refunds_owner_and_uses_printed_cost(self):
        session, _, _ = self.case.started()
        refunded = session.rules_refund_stack_action_essence({"controllerId": "p1",
            "source": {"cardId": self.HOURGLASS, "ownerId": "p2"}, "cost": {"essenceSpent": []}})
        self.assertEqual(sum(entry["amount"] for entry in refunded), 4)
        self.assertEqual(self.pool(session, "p2"), {"vitreous": 2, "capricious": 2})
        self.assertEqual(self.pool(session), {})

    def test_bob_hand_immunity_does_not_prevent_paying_an_additional_cost(self):
        for source in [self.MARTYRIZE, self.CENSOR]:
            with self.subTest(source=source):
                session, p1, _ = self.case.started()
                session.battlefield.append(self.case.field_item("bob", "p1", "inner-deserts-134", counters={"power": 6}))
                self.case.put(p1, "hand", [source, self.SWINE])
                session.add_rules_excess_essence("p1", [{"temperament": "hollow", "amount": 1}])
                error, action = session.declare_rules_action("p1", "Pay additional cost", kind="play_card",
                    source={"cardId": source, "zone": "hand"},
                    ability_id=self.case.ABILITIES[source][0]["id"], cost_card_id=self.SWINE,
                    targets=[{"kind": "card", "itemId": "first-b", "cardId": "m-2"}] if source == self.CENSOR else [])
                self.assertIsNone(error)
                self.assertEqual(action["cost"].get("revealedCard", {}).get("cardId"), self.SWINE)
                self.assertIn(self.SWINE, p1["zones"]["exile"])
                self.assertNotIn(self.SWINE, p1["zones"]["hand"])
