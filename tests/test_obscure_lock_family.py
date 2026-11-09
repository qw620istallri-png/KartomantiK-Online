"""Strict semantic coverage for Obscure's three printed paragraphs."""

import copy

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


OBSCURE = "inner-deserts-043"
ABILITY = {
    "id": "obscure-card-until-end-turn",
    "action": "play_card",
    "resolveSourceTo": "exile",
    "targets": {
        "min": 1,
        "max": 1,
        "cardTypes": ["manifestation", "persistent_will"],
        "zones": ["battlefield"],
    },
    "ongoingEffect": {
        "kind": "obscure_lock",
        "duration": "until_end_of_turn",
    },
}


class ObscureLockFamily(RealCardRulesCase):
    ALL = (OBSCURE,)

    def started(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker.update(
            index=ADVANCED_PHASES.index("confrontation_reaction"), turn=4,
        )
        session.rules_engine.update(
            readyPlayerIds=["p1", "p2"],
            firstManifestationComplete=True,
            firstManifestationTriggersQueued=True,
            priorityPlayerId="p1",
            priorityPasses=[],
            actionStack=[],
            pendingChoice=None,
        )
        session.add_rules_excess_essence(
            "p1", [{"temperament": "vitreous", "amount": 20}],
        )
        return session, p1, p2

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

    def manifestation(self, session, owner="p2", item_id="target"):
        session.card_rules["m-1"].update({
            "power": 5,
            "persist": True,
            "activatedAbilities": [{
                "id": "printed-action", "targets": {"min": 0, "max": 0},
            }],
        })
        return self.field_item(
            item_id, owner, "m-1", field_zone="confrontation",
            rotation=0.0,
        )

    def persistent_will(self, session, owner="p2"):
        session.card_rules["persistent-probe"] = {
            "type": "persistent_will", "cost": 1,
            "temperaments": ["vitreous"],
            "activatedAbilities": [{
                "id": "probe-action", "targets": {"min": 0, "max": 0},
            }],
        }
        return self.field_item(
            "persistent", owner, "persistent-probe", field_zone="field",
            rotation=0.0,
        )

    def declare(self, session, p1, item):
        self.put(p1, "hand", [OBSCURE])
        return session.declare_rules_action(
            "p1", "Obscure", kind="play_card",
            source={"cardId": OBSCURE, "zone": "hand"},
            ability_id=ABILITY["id"], targets=[self.target(item)],
        )

    def resolve_top(self, session):
        self.assertIsNone(session.pass_rules_priority("p2")[0])
        error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error, error)
        return resolution

    def obscure(self, session, p1, item):
        error, action = self.declare(session, p1, item)
        self.assertIsNone(error, error)
        resolution = self.resolve_top(session)
        self.assertEqual(resolution["status"], "resolved")
        return action, resolution

    def test_compiles_the_exact_three_paragraph_contract(self):
        rules = self.real_rules()[OBSCURE]
        self.assertEqual(self.ABILITIES[OBSCURE], [ABILITY])
        self.assertEqual(rules["playedAbilities"], [ABILITY])
        self.assertEqual(rules["type"], "ephemeral_will")
        self.assertEqual(rules["powerCost"], "{B}{B}{B}{B}")

    def test_invalid_targets_are_rejected_without_payment(self):
        for mode in ("ephemeral", "stalemate", "missing", "immune"):
            with self.subTest(mode=mode):
                session, p1, _p2 = self.started()
                target = self.manifestation(session)
                session.battlefield = [target]
                if mode == "ephemeral":
                    session.card_rules["field-ephemeral"] = {
                        "type": "ephemeral_will", "cost": 1,
                    }
                    target = self.field_item(
                        "ephemeral", "p2", "field-ephemeral",
                        field_zone="field",
                    )
                    session.battlefield = [target]
                elif mode == "stalemate":
                    target["fieldZone"] = "stalemate"
                elif mode == "missing":
                    session.battlefield = []
                else:
                    session.rules_engine["ongoingEffects"].append({
                        "id": "immune", "kind": "immune",
                        "target": self.target(target),
                        "duration": "until_end_of_turn", "startedTurn": 4,
                    })
                self.put(p1, "hand", [OBSCURE])
                before = self.snapshot(session)
                error, action = session.declare_rules_action(
                    "p1", "Obscure", kind="play_card",
                    source={"cardId": OBSCURE, "zone": "hand"},
                    ability_id=ABILITY["id"], targets=[self.target(target)],
                )
                self.assertIsNotNone(error)
                self.assertIsNone(action)
                self.assertEqual(self.snapshot(session), before)

    def test_manifestation_loses_effects_is_fully_immune_and_contributes_zero(self):
        session, p1, _p2 = self.started()
        target = self.manifestation(session)
        session.battlefield = [target]
        action, resolution = self.obscure(session, p1, target)
        self.assertEqual(
            sum(entry["amount"] for entry in action["cost"]["essenceSpent"]),
            4,
        )
        self.assertEqual(p1["zones"]["exile"], [OBSCURE])
        self.assertFalse(session.rules_item_effects_active(target))
        self.assertFalse(session.rules_item_has_persist(target))
        self.assertTrue(session.rules_item_is_immune(target, "p1"))
        self.assertTrue(session.rules_item_is_immune(target, "p2"))
        self.assertEqual(session.rules_confrontation_power(target), 0)
        effect = resolution["action"]["ongoingEffects"][0]
        self.assertEqual(
            (effect["kind"], effect["duration"], effect["startedTurn"]),
            ("obscure_lock", "until_end_of_turn", 4),
        )

    def test_persistent_will_loses_effects_and_is_immune_without_manifestation_power_rule(self):
        session, p1, _p2 = self.started()
        target = self.persistent_will(session)
        session.battlefield = [target]
        self.obscure(session, p1, target)
        self.assertFalse(session.rules_item_effects_active(target))
        self.assertTrue(session.rules_item_is_immune(target, "p1"))
        self.assertTrue(session.rules_item_is_immune(target, "p2"))
        self.assertEqual(
            session.rules_item_card_rules(target)["type"],
            "persistent_will",
        )

    def test_immunity_blocks_both_controllers_after_obscure_resolves(self):
        session, p1, _p2 = self.started()
        target = self.manifestation(session)
        session.battlefield = [target]
        self.obscure(session, p1, target)
        contract = {
            "min": 1, "max": 1, "cardType": "manifestation",
            "zones": ["battlefield"],
        }
        for controller in ("p1", "p2"):
            with self.subTest(controller=controller):
                error = session.rules_ability_targets_error(
                    contract, [self.target(target)], controller,
                )
                self.assertIn("Immune", error or "")

    def test_late_invalid_target_fizzles_but_obscure_still_exiles_itself(self):
        for mode in ("gone", "stalemate", "immune"):
            with self.subTest(mode=mode):
                session, p1, p2 = self.started()
                target = self.manifestation(session)
                session.battlefield = [target]
                error, _action = self.declare(session, p1, target)
                self.assertIsNone(error, error)
                if mode == "gone":
                    session._rules_remove_field_item(
                        target, "p2", "graveyard", "top",
                    )
                elif mode == "stalemate":
                    target["fieldZone"] = "stalemate"
                else:
                    session.rules_engine["ongoingEffects"].append({
                        "id": "immune", "kind": "immune",
                        "target": self.target(target),
                        "duration": "until_end_of_turn", "startedTurn": 4,
                    })
                resolution = self.resolve_top(session)
                resolved = resolution["action"]
                self.assertEqual(p1["zones"]["exile"], [OBSCURE])
                self.assertEqual(
                    resolved["effectResult"]["status"], "no_effect",
                )
                self.assertNotIn("ongoingEffects", resolved)
                self.assertFalse(any(
                    effect.get("kind") == "obscure_lock"
                    for effect in session.rules_engine["ongoingEffects"]
                ))
                if mode == "gone":
                    self.assertEqual(p2["zones"]["graveyard"], ["m-1"])

    def test_cleanse_removes_the_modifier_without_undoing_obscures_exile(self):
        session, p1, _p2 = self.started()
        target = self.manifestation(session)
        session.battlefield = [target]
        self.obscure(session, p1, target)
        result = session.apply_rules_action_result({
            "id": "cleanse", "controllerId": "p2",
            "source": {"cardId": "inner-deserts-145"},
            "targets": [self.target(target)],
            "ability": {"result": {"kind": "cleanse_target"}},
        })
        self.assertEqual(result["status"], "cleansed")
        self.assertTrue(session.rules_item_effects_active(target))
        self.assertTrue(session.rules_item_has_persist(target))
        self.assertFalse(session.rules_item_is_immune(target, "p1"))
        self.assertEqual(session.rules_confrontation_power(target), 5)
        self.assertEqual(p1["zones"]["exile"], [OBSCURE])

    def test_turn_expiry_restores_effects_immunity_and_confrontation_power(self):
        session, p1, _p2 = self.started()
        target = self.manifestation(session)
        session.battlefield = [target]
        self.obscure(session, p1, target)
        session.phase_tracker["turn"] = 5
        removed = session.prune_rules_ongoing_effects()
        self.assertEqual([effect["kind"] for effect in removed], ["obscure_lock"])
        self.assertTrue(session.rules_item_effects_active(target))
        self.assertTrue(session.rules_item_has_persist(target))
        self.assertFalse(session.rules_item_is_immune(target, "p1"))
        self.assertEqual(session.rules_confrontation_power(target), 5)

    def test_neutralized_obscure_goes_to_limbo_and_creates_no_lock(self):
        session, p1, _p2 = self.started()
        target = self.manifestation(session)
        session.battlefield = [target]
        error, action = self.declare(session, p1, target)
        self.assertIsNone(error, error)
        before_essence = sum(
            token.get("counters", {}).get("essence", 0)
            for token in session.tokens
            if token.get("ownerId") == "p1"
        )
        result = session.counter_rules_stack_action(action, "neutralize")
        self.assertEqual(result["status"], "neutralized")
        self.assertEqual(p1["zones"]["graveyard"], [OBSCURE])
        self.assertEqual(p1["zones"]["exile"], [])
        self.assertTrue(session.rules_item_effects_active(target))
        self.assertEqual(session.rules_engine["ongoingEffects"], [])
        self.assertEqual(
            sum(
                token.get("counters", {}).get("essence", 0)
                for token in session.tokens
                if token.get("ownerId") == "p1"
            ),
            before_essence,
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
