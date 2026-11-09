"""Strict semantic coverage for Inflate the Ego's two paragraphs."""

import copy

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


INFLATE = "inner-deserts-118"
ABILITY = {
    "id": "reduce-cost-and-set-first-power",
    "action": "play_card",
    "costReduction": {"kind": "half_first_base_power"},
    "targets": {
        "min": 1,
        "max": 1,
        "cardType": "manifestation",
        "zones": ["battlefield"],
        "controller": "self",
        "firstManifestationOnly": True,
    },
    "ongoingEffect": {
        "kind": "power_set_maximum",
        "value": 10,
        "duration": "until_end_of_turn",
    },
}


class InflateTheEgoFamily(RealCardRulesCase):
    ALL = (INFLATE,)

    def started(self, *, base_power=5, current_adjustment=-1):
        session, p1, p2 = self.make_session()
        session.phase_tracker.update(
            index=ADVANCED_PHASES.index("confrontation_reaction"), turn=4,
        )
        session.rules_engine.update(
            readyPlayerIds=["p1", "p2"],
            firstManifestationComplete=True,
            firstManifestationTriggersQueued=True,
            firstManifestationItemIds={"p1": "first"},
            priorityPlayerId="p1",
            priorityPasses=[],
            actionStack=[],
            pendingChoice=None,
        )
        session.card_rules["m-1"].update({
            "power": base_power,
            "temperaments": ["choleric"],
        })
        first = self.field_item(
            "first", "p1", "m-1", field_zone="confrontation",
            counters={"power": current_adjustment}, rotation=0.0,
        )
        session.battlefield = [first]
        session.add_rules_excess_essence(
            "p1", [{"temperament": "choleric", "amount": 20}],
        )
        return session, p1, p2, first

    @staticmethod
    def target(item):
        return {
            "kind": "card", "itemId": item["id"],
            "cardId": item["cardId"], "ownerId": item["ownerId"],
        }

    @staticmethod
    def snapshot(session):
        return copy.deepcopy((
            session.players, session.battlefield, session.rules_engine,
            session.tokens,
        ))

    def declare(self, session, p1, target):
        self.put(p1, "hand", [INFLATE])
        return session.declare_rules_action(
            "p1", "Inflate the Ego", kind="play_card",
            source={"cardId": INFLATE, "zone": "hand"},
            ability_id=ABILITY["id"], targets=[self.target(target)],
        )

    def resolve_top(self, session):
        self.assertIsNone(session.pass_rules_priority("p2")[0])
        error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error, error)
        return resolution

    def inflate(self, session, p1, target):
        error, action = self.declare(session, p1, target)
        self.assertIsNone(error, error)
        resolution = self.resolve_top(session)
        self.assertEqual(resolution["status"], "resolved")
        return action, resolution

    def add_power_modifier(self, session, target, value, effect_id):
        session.rules_engine["ongoingEffects"].append({
            "id": effect_id,
            "kind": "power_modifier",
            "value": value,
            "target": self.target(target),
            "duration": "until_end_of_turn",
            "startedTurn": 4,
        })

    def test_compiles_the_exact_two_paragraph_contract(self):
        rules = self.real_rules()[INFLATE]
        self.assertEqual(self.ABILITIES[INFLATE], [ABILITY])
        self.assertEqual(rules["playedAbilities"], [ABILITY])
        self.assertEqual(rules["type"], "ephemeral_will")
        self.assertEqual(rules["powerCost"], "{R}{R}{R}{R}{R}")

    def test_requires_the_controllers_current_first_manifestation_atomically(self):
        for mode in ("no-first", "own-non-first", "opponent-first", "stalemate"):
            with self.subTest(mode=mode):
                session, p1, _p2, first = self.started()
                other = self.field_item(
                    "other", "p1", "m-2", field_zone="interzone",
                )
                session.battlefield.append(other)
                target = first
                if mode == "no-first":
                    session.rules_engine["firstManifestationItemIds"] = {}
                elif mode == "own-non-first":
                    target = other
                elif mode == "opponent-first":
                    first["ownerId"] = "p2"
                    session.rules_engine["firstManifestationItemIds"] = {
                        "p2": "first",
                    }
                else:
                    first["fieldZone"] = "stalemate"
                self.put(p1, "hand", [INFLATE])
                before = self.snapshot(session)
                error, action = session.declare_rules_action(
                    "p1", "Inflate the Ego", kind="play_card",
                    source={"cardId": INFLATE, "zone": "hand"},
                    ability_id=ABILITY["id"],
                    targets=[self.target(target)],
                )
                self.assertIsNotNone(error)
                self.assertIsNone(action)
                self.assertEqual(self.snapshot(session), before)

    def test_base_five_discount_sets_current_four_to_ten_without_mutating_printed_cost(self):
        session, p1, _p2, first = self.started()
        self.assertEqual(
            session.rules_manifestation_characteristics(first)["power"], 4,
        )
        action, resolution = self.inflate(session, p1, first)
        self.assertEqual(
            sum(entry["amount"] for entry in action["cost"]["essenceSpent"]),
            3,
        )
        self.assertEqual(
            session.rules_manifestation_characteristics(first)["power"], 10,
        )
        self.assertEqual(session.card_rules[INFLATE]["powerCost"], "{R}{R}{R}{R}{R}")
        self.assertEqual(p1["zones"]["graveyard"], [INFLATE])
        effect = resolution["action"]["ongoingEffects"][0]
        self.assertEqual(
            (effect["kind"], effect["value"], effect["powerAdjustment"]),
            ("power_set_maximum", 10, 6),
        )

    def test_discount_uses_modified_base_power_and_never_makes_cost_negative(self):
        for base_power, doubled, expected_cost in ((5, True, 0), (12, False, 0)):
            with self.subTest(base_power=base_power, doubled=doubled):
                session, p1, _p2, first = self.started(
                    base_power=base_power, current_adjustment=0,
                )
                if doubled:
                    session.rules_engine["ongoingEffects"].append({
                        "id": "double-base", "kind": "base_power_double",
                        "target": self.target(first), "duration": "permanent",
                    })
                self.assertGreaterEqual(
                    session.rules_manifestation_base_power(first), 10,
                )
                error, action = self.declare(session, p1, first)
                self.assertIsNone(error, error)
                self.assertEqual(
                    sum(action["cost"]["tributeRequirements"].values()),
                    expected_cost,
                )
                self.assertEqual(action["cost"]["essenceSpent"], [])

    def test_later_malus_lowers_power_but_later_bonus_is_capped_at_ten(self):
        session, p1, _p2, first = self.started()
        self.inflate(session, p1, first)
        self.add_power_modifier(session, first, -2, "later-malus")
        self.assertEqual(
            session.rules_manifestation_characteristics(first)["power"], 8,
        )
        self.add_power_modifier(session, first, 5, "later-bonus")
        self.assertEqual(
            session.rules_manifestation_characteristics(first)["power"], 10,
        )

    def test_new_first_between_payment_and_resolution_invalidates_the_old_target(self):
        session, p1, _p2, first = self.started()
        successor = self.field_item(
            "successor", "p1", "m-2", field_zone="interzone",
            counters={"power": 0},
        )
        session.battlefield.append(successor)
        before_first = session.rules_manifestation_characteristics(first)["power"]
        before_successor = session.rules_manifestation_characteristics(successor)["power"]
        error, action = self.declare(session, p1, first)
        self.assertIsNone(error, error)
        paid = sum(
            entry["amount"] for entry in action["cost"]["essenceSpent"]
        )
        session.rules_engine["firstManifestationItemIds"]["p1"] = "successor"
        resolution = self.resolve_top(session)
        resolved = resolution["action"]
        self.assertEqual(resolved["effectResult"]["kind"], "invalid_targets")
        self.assertNotIn("ongoingEffects", resolved)
        self.assertEqual(
            session.rules_manifestation_characteristics(first)["power"],
            before_first,
        )
        self.assertEqual(
            session.rules_manifestation_characteristics(successor)["power"],
            before_successor,
        )
        self.assertEqual(paid, 3)
        self.assertEqual(p1["zones"]["graveyard"], [INFLATE])

    def test_cleanse_removes_the_cap_and_resets_other_power_changes(self):
        session, p1, _p2, first = self.started()
        self.inflate(session, p1, first)
        result = session.apply_rules_action_result({
            "id": "cleanse", "controllerId": "p1",
            "source": {"cardId": "inner-deserts-145"},
            "targets": [self.target(first)],
            "ability": {"result": {"kind": "cleanse_target"}},
        })
        self.assertEqual(result["status"], "cleansed")
        self.assertEqual(
            session.rules_manifestation_characteristics(first)["power"], 5,
        )
        self.assertNotIn("power", first["counters"])
        self.assertEqual(p1["zones"]["graveyard"], [INFLATE])

    def test_turn_end_expiration_restores_the_underlying_power(self):
        session, p1, _p2, first = self.started()
        self.inflate(session, p1, first)
        session.phase_tracker["turn"] = 5
        removed = session.prune_rules_ongoing_effects()
        self.assertEqual(
            [effect["kind"] for effect in removed], ["power_set_maximum"],
        )
        self.assertEqual(
            session.rules_manifestation_characteristics(first)["power"], 4,
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
