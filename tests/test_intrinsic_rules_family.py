"""Strict intrinsic-rule contracts for six previously unclassified cards."""

from test_game_state import RealCardRulesCase


INTRINSIC_RULE_NAMES = (
    "Forgotten Pile",
    "Solar Apparition",
    "Zizek, the Immolated",
    "Alakazim, the Magician",
    "Kanopo, the Headless",
    "Palgonphio",
)

CARD_IDS = {
    "Forgotten Pile": "g3zumpyf623hto6_en",
    "Solar Apparition": "7j3udrfh5t8vl25_en",
    "Zizek, the Immolated": "ir09smkker8rgxd_en",
    "Alakazim, the Magician": "inner-deserts-028",
    "Kanopo, the Headless": "inner-deserts-052",
    "Palgonphio": "inner-deserts-099",
}

EXPECTED_INTRINSICS = {
    "Forgotten Pile": {
        "canPayTributeFromLimbo": True,
    },
    "Solar Apparition": {
        "canPayTributeFromInterzone": True,
        "tributeExtraPowerLoss": 2,
    },
    "Zizek, the Immolated": {
        "confrontationEntryLimboWills": 6,
        "retainsExcessEssence": True,
    },
    "Alakazim, the Magician": {
        "tributePowerOverride": {
            "power": 3, "condition": "two_wills_played_this_turn",
        },
    },
    "Kanopo, the Headless": {
        "tributeSacrificePower": 6,
    },
    "Palgonphio": {
        "tributePowerOverride": {
            "power": 4,
            "condition": "lost_or_stalemate_previous_turn",
        },
    },
}


class IntrinsicRulesFamily(RealCardRulesCase):
    ALL = tuple(CARD_IDS.values())

    def fixed_source(self, amount, temperament="hollow"):
        return {
            "cardId": "will-x", "cardType": "ephemeral_will",
            "controllerId": "p1", "fixedTribute": {temperament: amount},
        }

    def test_all_six_compile_the_exact_intrinsic_contract(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        for name in INTRINSIC_RULE_NAMES:
            with self.subTest(card=name):
                metadata = rules[CARD_IDS[name]]
                for key, expected in EXPECTED_INTRINSICS[name].items():
                    self.assertEqual(metadata.get(key), expected)

    def test_forgotten_pile_and_solar_use_their_printed_tribute_zones(self):
        pile = CARD_IDS["Forgotten Pile"]
        session, p1, _p2 = self.make_session()
        self.put(p1, "graveyard", [pile, "m-0"])
        source = self.fixed_source(2)
        error, _payment = session.rules_action_payment(
            "p1", "play_card", source, ["graveyard|m-0"],
        )
        self.assertIn("cannot currently pay Tribute", error)
        error, payment = session.rules_action_payment(
            "p1", "play_card", source, [f"graveyard|{pile}"],
        )
        self.assertIsNone(error, error)
        paid = session.pay_rules_tribute("p1", payment)
        self.assertEqual(paid["movements"][0]["destination"], "exile")
        self.assertIn(pile, p1["zones"]["exile"])
        self.assertNotIn(pile, p1["zones"]["graveyard"])

        solar = CARD_IDS["Solar Apparition"]
        session, p1, _p2 = self.make_session()
        session.card_rules["m-1"]["power"] = 4
        target = self.field_item("target", "p2", "m-1")
        tribute = self.field_item(
            "solar", "p1", solar, field_zone="interzone",
            controllerId="p1",
        )
        ordinary = self.field_item(
            "ordinary", "p1", "m-0", field_zone="interzone",
            controllerId="p1",
        )
        session.battlefield = [target, tribute, ordinary]
        source = self.fixed_source(3, "choleric")
        error, _payment = session.rules_action_payment(
            "p1", "play_card", source, ["battlefield|ordinary"],
        )
        self.assertIn("cannot pay Tribute from the field", error)
        error, payment = session.rules_action_payment(
            "p1", "play_card", source, ["battlefield|solar"],
        )
        self.assertIsNone(error, error)
        paid = session.pay_rules_tribute("p1", payment)
        self.assertEqual(paid["movements"][0]["fromZone"], "interzone")
        self.assertIsNone(session.find_battlefield_item("solar"))
        action = {
            "id": "solar-will", "kind": "play_card", "controllerId": "p1",
            "source": {"cardId": "will-x"},
            "cost": {"tributeCardIds": payment["cardIds"]},
            "targets": [{
                "kind": "card", "itemId": "target", "cardId": "m-1",
                "ownerId": "p2",
            }],
            "ability": {"ongoingEffect": {
                "kind": "power_modifier", "value": -1,
                "duration": "until_end_of_turn",
            }},
        }
        session.create_rules_ongoing_effects(action)
        self.assertEqual(self.power_of(session, "target"), 1)

    def test_conditional_tribute_values_require_the_exact_printed_history(self):
        alakazim = CARD_IDS["Alakazim, the Magician"]
        session, p1, _p2 = self.make_session()
        self.put(p1, "hand", [alakazim])
        source = self.fixed_source(3)
        self.assertIn(
            "do not pay",
            session.rules_action_payment(
                "p1", "play_card", source, [alakazim],
            )[0],
        )
        session.rules_engine["willsPlayed"] = {
            "turn": session.phase_tracker["turn"], "p1": 1,
        }
        self.assertIn(
            "do not pay",
            session.rules_action_payment(
                "p1", "play_card", source, [alakazim],
            )[0],
        )
        session.rules_engine["willsPlayed"]["p1"] = 2
        error, payment = session.rules_action_payment(
            "p1", "play_card", source, [alakazim],
        )
        self.assertIsNone(error, error)
        self.assertEqual(payment["excessEssence"], [])

        palgonphio = CARD_IDS["Palgonphio"]
        for history in ("loss", "stalemate"):
            with self.subTest(palgonphio=history):
                session, p1, _p2 = self.make_session()
                self.put(p1, "hand", [palgonphio])
                source = self.fixed_source(4)
                self.assertIn(
                    "do not pay",
                    session.rules_action_payment(
                        "p1", "play_card", source, [palgonphio],
                    )[0],
                )
                previous = str(session.phase_tracker["turn"] - 1)
                if history == "loss":
                    session.rules_engine["confrontationLosses"] = {
                        previous: "p1",
                    }
                else:
                    session.rules_engine["confrontationStalemates"] = {
                        previous: True,
                    }
                error, payment = session.rules_action_payment(
                    "p1", "play_card", source, [palgonphio],
                )
                self.assertIsNone(error, error)
                self.assertEqual(payment["excessEssence"], [])

        kanopo = CARD_IDS["Kanopo, the Headless"]
        session, p1, p2 = self.make_session()
        self.put(p1, "hand", [kanopo])
        donor = self.field_item(
            "donor", "p1", "m-1", field_zone="interzone",
            controllerId="p1",
        )
        foreign = self.field_item(
            "foreign", "p2", "m-2", field_zone="interzone",
            controllerId="p2",
        )
        session.battlefield = [donor, foreign]
        source = self.fixed_source(6)
        self.assertIn(
            "do not pay",
            session.rules_action_payment(
                "p1", "play_card", source, [kanopo],
            )[0],
        )
        error, _payment = session.rules_action_payment(
            "p1", "play_card", source,
            [kanopo, "sacrifice|foreign"],
        )
        self.assertIn("must be in your Interzone", error)
        error, payment = session.rules_action_payment(
            "p1", "play_card", source, [kanopo, "sacrifice|donor"],
        )
        self.assertIsNone(error, error)
        self.assertEqual(payment["sacrificeItemIds"], ["donor"])
        session.pay_rules_tribute("p1", payment)
        self.assertIsNone(session.find_battlefield_item("donor"))
        self.assertIn("m-1", p1["zones"]["graveyard"])
        self.assertIn(kanopo, p1["zones"]["graveyard"])
        self.assertIsNotNone(session.find_battlefield_item("foreign"))
        self.assertEqual(p2["zones"]["graveyard"], [])

    def test_zizek_requires_six_limbo_wills_and_retains_its_excess(self):
        zizek = CARD_IDS["Zizek, the Immolated"]
        session, p1, _p2 = self.make_session()
        for index in range(6):
            session.card_rules[f"limbo-will-{index}"] = {
                "type": "ephemeral_will",
            }
        self.put(p1, "graveyard", [
            f"limbo-will-{index}" for index in range(5)
        ])
        self.assertTrue(session.rules_confrontation_entry_blocked(
            "p1", session.card_rules[zizek],
        ))
        p1["zones"]["graveyard"].append("limbo-will-5")
        p1["zoneOwners"]["graveyard"]["limbo-will-5"] = "p1"
        self.assertFalse(session.rules_confrontation_entry_blocked(
            "p1", session.card_rules[zizek],
        ))

        self.put(p1, "hand", [zizek])
        error, payment = session.rules_action_payment(
            "p1", "play_card", self.fixed_source(2), [zizek],
        )
        self.assertIsNone(error, error)
        self.assertEqual(payment["excessEssence"], [{
            "temperament": "transcendent", "amount": 3, "retained": True,
        }])
        paid = session.pay_rules_tribute("p1", payment)
        self.assertEqual(paid["createdEssence"][0]["amount"], 3)
        retained = [
            token for token in session.tokens
            if token.get("temperament") == "transcendent"
        ]
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0]["expiresTurn"], 0)
        session.expire_rules_excess_essence(session.phase_tracker["turn"])
        self.assertIn(retained[0], session.tokens)


if __name__ == "__main__":
    import unittest

    unittest.main()
