"""Strict contracts for Trim the Excess and Equalize."""

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


SET_FIELD_POWER_NAMES = (
    "Trim the Excess",
    "Equalize",
)

TRIM = "t42gc95tma8uhzm_en"
EQUALIZE = "qahv0guk18jyo6i_en"

TRIM_ABILITY = {
    "id": "trim-field-to-base-power",
    "action": "play_card",
    "targets": {"min": 0, "max": 0},
    "result": {"kind": "set_field_power", "mode": "base"},
}

EQUALIZE_ABILITY = {
    "id": "equalize-field-to-lowest-base",
    "action": "play_card",
    "targets": {"min": 0, "max": 0},
    "result": {"kind": "set_field_power", "mode": "lowest_base"},
}


class SetFieldPowerFamily(RealCardRulesCase):
    ALL = (TRIM, EQUALIZE)

    def started(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker.update(
            index=ADVANCED_PHASES.index("confrontation_reaction"),
            turn=3,
        )
        session.rules_engine.update(
            readyPlayerIds=["p1", "p2"],
            firstManifestationComplete=True,
            firstManifestationTriggersQueued=True,
            priorityPlayerId="p1",
            actionStack=[],
            pendingChoice=None,
        )
        session.card_rules["persistent-target"] = {
            "type": "persistent_will",
            "cost": 1,
            "temperaments": ["phlegmatic"],
        }
        return session, p1, p2

    def fund(self, session, player, source_id):
        payers = ["m-0", "m-1"]
        for card_id in payers:
            session.card_rules[card_id]["temperaments"] = ["capricious"]
        self.put(player, "hand", [source_id, *payers])
        return payers

    def resolve_top(self, session):
        self.assertIsNone(session.pass_rules_priority("p2")[0])
        error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error, error)
        return resolution

    def play(self, session, player, card_id):
        payers = self.fund(session, player, card_id)
        ability_id = (
            TRIM_ABILITY["id"] if card_id == TRIM else EQUALIZE_ABILITY["id"]
        )
        error, action = session.declare_rules_action(
            "p1",
            "Set field power",
            kind="play_card",
            source={"cardId": card_id, "zone": "hand"},
            targets=[],
            payment_card_ids=payers,
            ability_id=ability_id,
        )
        self.assertIsNone(error, error)
        self.assertIsNotNone(action)
        return self.resolve_top(session), payers

    @staticmethod
    def configure_manifestation(session, card_id, power):
        session.card_rules[card_id] = {
            "type": "manifestation",
            "power": power,
            "temperaments": ["phlegmatic"],
        }

    def power(self, session, item_id):
        return session.rules_manifestation_characteristics(
            session.find_battlefield_item(item_id)
        )["power"]

    def field_fixture(self, session):
        for card_id, power in (
            ("m-10", 5),
            ("m-11", 2),
            ("m-12", 4),
            ("m-13", 1),
        ):
            self.configure_manifestation(session, card_id, power)
        items = {
            "first": self.field_item(
                "first", "p1", "m-10", "confrontation",
                counters={"power": 3},
            ),
            "interzone": self.field_item(
                "interzone", "p2", "m-11", "interzone",
                counters={"power": -1},
            ),
            "support": self.field_item(
                "support", "p2", "m-12", "confrontation",
                counters={"power": 2}, isSupport=True,
            ),
            "stalemate": self.field_item(
                "stalemate", "p2", "m-13", "stalemate",
                counters={"power": 5},
            ),
            "will": self.field_item(
                "will", "p2", "persistent-target", "field",
            ),
        }
        session.battlefield = list(items.values())
        return items

    def test_both_compile_the_exact_printed_contract(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        self.assertEqual(self.ABILITIES[TRIM], [TRIM_ABILITY])
        self.assertEqual(self.ABILITIES[EQUALIZE], [EQUALIZE_ABILITY])
        self.assertEqual(rules[TRIM]["playedAbilities"], [TRIM_ABILITY])
        self.assertEqual(
            rules[EQUALIZE]["playedAbilities"], [EQUALIZE_ABILITY],
        )

    def test_trim_really_restores_each_current_field_manifestation_to_its_base(self):
        session, p1, _p2 = self.started()
        self.field_fixture(session)
        self.assertEqual(
            [self.power(session, item_id) for item_id in (
                "first", "interzone", "support", "stalemate",
            )],
            [8, 1, 6, 6],
        )

        resolution, payers = self.play(session, p1, TRIM)
        effect = resolution["action"]["effectResult"]
        self.assertEqual((effect["status"], effect["mode"]), ("set", "base"))
        self.assertEqual(len(effect["effectIds"]), 3)
        self.assertEqual(
            [self.power(session, item_id) for item_id in (
                "first", "interzone", "support", "stalemate",
            )],
            [5, 2, 4, 6],
        )
        self.assertFalse(any(
            entry.get("target", {}).get("itemId") == "will"
            for entry in session.rules_engine["ongoingEffects"]
        ))
        self.assertIn(TRIM, p1["zones"]["graveyard"])
        for payer in payers:
            self.assertIn(payer, p1["zones"]["graveyard"])

    def test_equalize_uses_the_lowest_live_base_on_the_field_not_stalemate(self):
        session, p1, _p2 = self.started()
        self.field_fixture(session)
        session.find_battlefield_item("interzone")["baseDoublings"] = 1
        self.assertEqual(
            session.rules_manifestation_base_power(
                session.find_battlefield_item("interzone")
            ),
            4,
        )

        resolution, payers = self.play(session, p1, EQUALIZE)
        effect = resolution["action"]["effectResult"]
        self.assertEqual(
            (effect["status"], effect["mode"]),
            ("set", "lowest_base"),
        )
        self.assertEqual(len(effect["effectIds"]), 3)
        self.assertEqual(
            [self.power(session, item_id) for item_id in (
                "first", "interzone", "support", "stalemate",
            )],
            [4, 4, 4, 6],
        )
        self.assertIn(EQUALIZE, p1["zones"]["graveyard"])
        for payer in payers:
            self.assertIn(payer, p1["zones"]["graveyard"])

    def test_both_prevent_new_modifiers_on_each_affected_occurrence(self):
        for card_id, expected in ((TRIM, 6), (EQUALIZE, 2)):
            with self.subTest(card_id=card_id):
                session, p1, _p2 = self.started()
                self.configure_manifestation(session, "m-10", 6)
                self.configure_manifestation(session, "m-11", 2)
                target = self.field_item(
                    "target", "p1", "m-10", counters={"power": 2},
                )
                floor = self.field_item("floor", "p2", "m-11")
                session.battlefield = [target, floor]
                self.play(session, p1, card_id)
                self.assertEqual(self.power(session, "target"), expected)

                counters_before = dict(target["counters"])
                session.adjust_rules_power_counter(target, 9)
                self.assertEqual(target["counters"], counters_before)
                self.assertFalse(session.append_rules_ongoing_effect({
                    "id": "later-power",
                    "kind": "power_modifier",
                    "duration": "until_end_of_turn",
                    "startedTurn": 3,
                    "value": 7,
                    "target": {"kind": "card", "itemId": "target"},
                }))
                session.set_rules_item_temperament(
                    target, "hollow", {"source": {}, "ability": {"id": "color"}},
                )
                self.assertNotIn("temperamentOverride", target)
                created = session.create_rules_ongoing_effects({
                    "id": "later-support",
                    "controllerId": "p1",
                    "source": {},
                    "targets": [{
                        "kind": "card", "itemId": "target",
                        "cardId": "m-10", "ownerId": "p1",
                    }],
                    "ability": {
                        "id": "later-support",
                        "ongoingEffect": {
                            "kind": "grant_support",
                            "duration": "while_target_on_field",
                        },
                    },
                })
                self.assertEqual(created, [])
                self.assertEqual(self.power(session, "target"), expected)

    def test_only_manifestations_present_at_resolution_are_locked(self):
        for card_id in (TRIM, EQUALIZE):
            with self.subTest(card_id=card_id):
                session, p1, _p2 = self.started()
                self.configure_manifestation(session, "m-10", 5)
                self.configure_manifestation(session, "m-11", 3)
                locked = self.field_item(
                    "locked", "p1", "m-10", counters={"power": 4},
                )
                session.battlefield = [locked]
                self.play(session, p1, card_id)

                newcomer = self.field_item(
                    "newcomer", "p2", "m-11", counters={"power": 2},
                )
                session.battlefield.append(newcomer)
                self.assertEqual(self.power(session, "newcomer"), 5)
                session.adjust_rules_power_counter(newcomer, 1)
                self.assertEqual(self.power(session, "newcomer"), 6)

                session._rules_remove_field_item(
                    locked, "p1", "hand", "top",
                )
                returned = self.field_item(
                    "returned", "p1", "m-10", counters={"power": 1},
                )
                session.battlefield.append(returned)
                self.assertEqual(self.power(session, "returned"), 6)
                session.adjust_rules_power_counter(returned, 1)
                self.assertEqual(self.power(session, "returned"), 7)

    def test_modifier_lock_expires_on_the_next_turn(self):
        for card_id in (TRIM, EQUALIZE):
            with self.subTest(card_id=card_id):
                session, p1, _p2 = self.started()
                self.configure_manifestation(session, "m-10", 5)
                target = self.field_item(
                    "target", "p1", "m-10", counters={"power": 3},
                )
                session.battlefield = [target]
                self.play(session, p1, card_id)
                self.assertEqual(self.power(session, "target"), 5)

                session.phase_tracker["turn"] = 4
                removed = session.prune_rules_ongoing_effects()
                self.assertTrue(any(
                    effect.get("preventsModifiers") for effect in removed
                ))
                self.assertEqual(self.power(session, "target"), 8)
                session.adjust_rules_power_counter(target, 1)
                self.assertEqual(self.power(session, "target"), 9)

    def test_both_resolve_and_pay_normally_with_no_field_manifestation(self):
        for card_id in (TRIM, EQUALIZE):
            with self.subTest(card_id=card_id):
                session, p1, _p2 = self.started()
                session.battlefield = [self.field_item(
                    "will", "p2", "persistent-target", "field",
                )]
                resolution, payers = self.play(session, p1, card_id)
                effect = resolution["action"]["effectResult"]
                self.assertEqual(effect["status"], "nothing")
                self.assertEqual(effect["effectIds"], [])
                self.assertIn(card_id, p1["zones"]["graveyard"])
                for payer in payers:
                    self.assertIn(payer, p1["zones"]["graveyard"])


if __name__ == "__main__":
    import unittest

    unittest.main()
