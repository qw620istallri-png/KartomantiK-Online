"""Availability and settlement of special payments using the shipped cards."""
import json
from functools import lru_cache
import test_game_state as game_tests
from session import ADVANCED_PHASES


class SpecialPaymentTests(game_tests.RealCardRulesCase):
    ALL = tuple(card["id"] for filename in ["public/cards-data.json", "public/extensions/inner-desert/cards.json"] for card in json.loads((game_tests.RealCardRulesCase.ROOT / filename).read_text(encoding="utf-8")))

    @classmethod
    @lru_cache(maxsize=1)
    def real_rules(cls):
        return super().real_rules()

    def started(self):
        session, p1, p2 = self.make_session()
        # Sessions may mutate metadata; isolate the cached catalogue per case.
        session.card_rules = json.loads(json.dumps(session.card_rules))
        session.rules_engine.update(readyPlayerIds=["p1", "p2"], firstManifestationComplete=True, priorityPlayerId="p1")
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
        session.battlefield = [self.field_item("first-a", "p1", "m-1"), self.field_item("first-b", "p2", "m-2")]
        return session, p1, p2

    def test_drildrill_requires_two_real_essences_and_exhausts_only_after_payment(self):
        for amount in [0, 1, 2]:
            with self.subTest(amount=amount):
                session, p1, _ = self.started()
                source = self.field_item("drill", "p1", "inner-deserts-131", rotation=0)
                session.battlefield += [source, self.field_item("will", "p2", "9bkn03sc9veaa88_en", "field")]
                self.put(p1, "hand", ["m-5"])
                session.add_rules_excess_essence("p1", [{"temperament": "hollow", "amount": amount}])
                error, action = session.declare_rules_action("p1", "Drill", kind="activated_effect", source={"zone": "battlefield", "itemId": "drill", "cardId": "inner-deserts-131"}, ability_id="drildrill-destroys-persistent-will", targets=[{"kind": "card", "itemId": "will", "cardId": "9bkn03sc9veaa88_en"}])
                if amount < 2:
                    self.assertIsNotNone(error)
                    self.assertEqual(source["rotation"], 0)
                    self.assertFalse(session.rules_engine["actionStack"])
                else:
                    self.assertIsNone(error)
                    self.assertEqual(sum(entry["amount"] for entry in action["cost"]["essenceSpent"]), 2)
                    self.assertEqual(source["rotation"], 90)

    def test_subjugate_uses_tribute_surplus_for_point_based_extra_cost(self):
        session, p1, _ = self.started()
        self.put(p1, "hand", ["inner-deserts-140", "m-3"])
        session.card_rules["m-3"]["power"] = 3
        session.card_points["m-2"] = 30
        error, action = session.declare_rules_action("p1", "Subjugate", kind="play_card", source={"zone": "hand", "cardId": "inner-deserts-140"}, ability_id="exile-by-essence-total", payment_card_ids=["m-3"], targets=[{"kind": "card", "itemId": "first-b", "cardId": "m-2"}])
        self.assertIsNone(error)
        self.assertEqual(action["cost"]["excessEssence"], [])
        session.resolve_rules_top_action()
        self.assertIsNone(session.find_battlefield_item("first-b"))

    def test_all_printed_interzone_tributes_can_pay_their_value(self):
        rules = self.real_rules()
        for card_id, metadata in rules.items():
            if not metadata.get("canPayTributeFromInterzone"):
                continue
            with self.subTest(card_id=card_id):
                session, _, _ = self.started()
                item = self.field_item("tribute", "p1", card_id, "interzone")
                session.battlefield.append(item)
                value = session.rules_tribute_power_override("p1", metadata)
                value = value if value is not None else metadata["power"]
                error, payment = session.rules_action_payment("p1", "activated_effect", None, ["battlefield|tribute"], {"tribute": "{H}" * int(value)})
                self.assertIsNone(error)
                session.pay_rules_tribute("p1", payment)
                self.assertIsNone(session.find_battlefield_item("tribute"))

    def test_every_encoded_tribute_and_essence_cost_accepts_a_sufficient_pool(self):
        for card_id, abilities in self.ABILITIES.items():
            for ability in abilities:
                if not (ability.get("tribute") or ability.get("essenceCost")):
                    continue
                with self.subTest(card_id=card_id, ability=ability["id"]):
                    session, _, _ = self.started()
                    session.add_rules_excess_essence("p1", [{"temperament": "transcendent", "amount": 40}])
                    error, payment = session.rules_action_payment("p1", "activated_effect", {"cardId": card_id, "zone": "battlefield"}, [], ability)
                    self.assertIsNone(error)
                    self.assertIsNotNone(payment)
                    expected = sum(session.rules_requirements_from_symbols(ability.get("tribute")).values()) + sum(session.rules_requirements_from_symbols(ability.get("essenceCost")).values())
                    self.assertEqual(sum(entry["amount"] for entry in payment["essenceSpent"]), expected)
                    session.tokens = []
                    error, _ = session.rules_action_payment("p1", "activated_effect", {"cardId": card_id, "zone": "battlefield"}, [], ability)
                    self.assertIsNotNone(error)

    def test_gems_can_pay_own_requested_cost_but_not_interrupt_another_choice(self):
        for kind in ["stack_counter_payment", "effect_memory_payment", "effect_payment", "immediate_effect_payment"]:
            with self.subTest(kind=kind):
                session, _, _ = self.started()
                item = self.field_item("gem", "p1", "inner-deserts-143", "field", counters={"Gem": 2}, chosenTemperament="choleric")
                session.battlefield.append(item)
                choice = {"id": "payment", "kind": kind, "playerId": "p1", "payment": "{R}"}
                session.rules_engine.update(pendingChoice=choice, priorityPlayerId="p2")
                error, _ = session.spend_rules_counter_essence("p1", "gem", "splendor-spends-a-gem-as-excess-essence")
                self.assertIsNone(error)
                self.assertIs(session.rules_engine["pendingChoice"], choice)
                self.assertEqual(item["counters"]["Gem"], 1)
                choice["playerId"] = "p2"
                error, _ = session.spend_rules_counter_essence("p1", "gem", "splendor-spends-a-gem-as-excess-essence")
                self.assertIsNotNone(error)
                choice.update(playerId="p1", kind="discard_from_hand")
                error, _ = session.spend_rules_counter_essence("p1", "gem", "splendor-spends-a-gem-as-excess-essence")
                self.assertIsNotNone(error)
