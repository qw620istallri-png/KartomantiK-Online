"""Strict semantic coverage for five Tribute-economy passive cards."""

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


TEAPOT = "pxp1zvyxfv16bdd_en"
FOG = "ul1tffi1wn5l3q5_en"
ORATOR = "birhlimm9e8lq3d_en"
BRABATABA = "zhzp6kenpqrym9h_en"
CAULDRON = "90cwtv2us78k76w_en"

EXPECTED_ABILITIES = {
    TEAPOT: [{
        "id": "reduce-controller-will-tribute",
        "passiveEffect": {"kind": "reduce_will_tribute", "value": 1},
    }],
    FOG: [{
        "id": "all-wills-cost-one-more",
        "passiveEffect": {"kind": "increase_will_tribute", "value": 1},
    }],
    ORATOR: [{
        "id": "field-manifestations-as-tribute",
        "passiveEffect": {"kind": "field_manifestations_as_tribute"},
    }],
    BRABATABA: [{
        "id": "vessel-manifestations-as-tribute",
        "passiveEffect": {"kind": "vessel_manifestations_as_tribute"},
    }],
    CAULDRON: [{
        "id": "retain-excess-essences",
        "passiveEffect": {"kind": "retain_excess_essence"},
    }],
}


class TributeEconomyFamily(RealCardRulesCase):
    ALL = (TEAPOT, FOG, ORATOR, BRABATABA, CAULDRON)

    def started(self, phase="confrontation_reaction"):
        session, p1, p2 = self.make_session()
        session.phase_tracker.update(
            index=ADVANCED_PHASES.index(phase), turn=4,
        )
        session.rules_engine.update(
            readyPlayerIds=["p1", "p2"], priorityPlayerId="p1",
            priorityPasses=[], actionStack=[], pendingChoice=None,
        )
        return session, p1, p2

    def active_item(self, session, owner_id, card_id, *, item_id=None,
                    field_zone="field", controller_id=None, **extra):
        item = self.field_item(
            item_id or card_id, owner_id, card_id, field_zone,
            controllerId=controller_id or owner_id,
            x=0.0, y=0.0, rotation=0.0, **extra,
        )
        session.battlefield.append(item)
        return item

    @staticmethod
    def will_source(card_id, player_id):
        return {
            "cardId": card_id, "cardType": "ephemeral_will",
            "controllerId": player_id, "zone": "hand",
        }

    def requirements(self, session, card_id, player_id, **source_extra):
        requirements, enforced = session.rules_tribute_requirements(
            "play_card",
            {**self.will_source(card_id, player_id), **source_extra},
            player_id=player_id,
        )
        self.assertTrue(enforced)
        return requirements

    def test_compiles_all_five_exact_contracts(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        for card_id, abilities in EXPECTED_ABILITIES.items():
            with self.subTest(card_id=card_id):
                self.assertEqual(self.ABILITIES[card_id], abilities)
                self.assertEqual(
                    rules[card_id]["passiveEffects"],
                    [abilities[0]["passiveEffect"]],
                )

    def test_teapot_reduces_only_its_controllers_wills_from_the_interzone(self):
        session, _p1, _p2 = self.started()
        session.card_rules["will-three"] = {
            "type": "ephemeral_will", "powerCost": "{R}{R}{R}",
        }
        teapot = self.active_item(
            session, "p1", TEAPOT, item_id="teapot", field_zone="interzone",
        )
        self.assertEqual(
            sum(self.requirements(session, "will-three", "p1").values()), 2,
        )
        self.assertEqual(
            sum(self.requirements(session, "will-three", "p2").values()), 3,
        )
        teapot["fieldZone"] = "confrontation"
        self.assertEqual(
            sum(self.requirements(session, "will-three", "p1").values()), 3,
        )

    def test_teapot_never_makes_a_zero_cost_will_negative_or_changes_manifestations(self):
        session, _p1, _p2 = self.started()
        session.card_rules["will-zero"] = {
            "type": "ephemeral_will", "powerCost": "", "cost": 0,
        }
        self.active_item(session, "p1", TEAPOT, field_zone="interzone")
        self.assertEqual(self.requirements(session, "will-zero", "p1"), {})
        requirements, enforced = session.rules_tribute_requirements(
            "play_card",
            {"cardId": "m-0", "cardType": "manifestation", "controllerId": "p1"},
            player_id="p1",
        )
        self.assertEqual((requirements, enforced), ({}, True))

    def test_fog_adds_one_hollow_to_every_players_printed_will(self):
        session, _p1, _p2 = self.started()
        session.card_rules["will-two"] = {
            "type": "persistent_will", "powerCost": "{R}{R}",
        }
        self.active_item(session, "p1", FOG)
        for player_id in ("p1", "p2"):
            with self.subTest(player_id=player_id):
                self.assertEqual(
                    self.requirements(session, "will-two", player_id),
                    {"choleric": 2, "hollow": 1},
                )

    def test_fog_does_not_tax_manifestations_or_an_explicit_free_permission(self):
        session, _p1, _p2 = self.started()
        session.card_rules["will-two"] = {
            "type": "ephemeral_will", "powerCost": "{R}{R}",
        }
        self.active_item(session, "p1", FOG)
        requirements, enforced = session.rules_tribute_requirements(
            "play_card",
            {"cardId": "m-0", "cardType": "manifestation", "controllerId": "p1"},
            player_id="p1",
        )
        self.assertEqual((requirements, enforced), ({}, True))
        self.assertEqual(
            self.requirements(session, "will-two", "p1", noTribute=True), {},
        )

    def test_teapot_and_fog_combine_before_the_zero_floor(self):
        session, _p1, _p2 = self.started()
        session.card_rules["will-zero"] = {
            "type": "ephemeral_will", "powerCost": "", "cost": 0,
        }
        session.card_rules["will-two"] = {
            "type": "ephemeral_will", "powerCost": "{R}{R}",
        }
        self.active_item(session, "p1", TEAPOT, field_zone="interzone")
        self.active_item(session, "p2", FOG)
        self.assertEqual(self.requirements(session, "will-zero", "p1"), {})
        self.assertEqual(
            sum(self.requirements(session, "will-two", "p1").values()), 2,
        )
        self.assertEqual(
            sum(self.requirements(session, "will-two", "p2").values()), 3,
        )

    def test_orator_globally_allows_each_players_controlled_field_tribute(self):
        session, _p1, _p2 = self.started()
        self.active_item(session, "p2", ORATOR, item_id="orator")
        donor_p1 = self.active_item(
            session, "p2", "m-1", item_id="donor-p1",
            field_zone="confrontation", controller_id="p1",
        )
        donor_p2 = self.active_item(
            session, "p2", "m-2", item_id="donor-p2",
            field_zone="interzone", controller_id="p2",
        )
        for player_id, donor in (("p1", donor_p1), ("p2", donor_p2)):
            with self.subTest(player_id=player_id):
                error, payment = session.rules_action_payment(
                    player_id, "activated_effect", None,
                    [f"battlefield|{donor['id']}"], {"tribute": "{H}"},
                )
                self.assertIsNone(error, error)
                paid = session.pay_rules_tribute(player_id, payment)
                self.assertEqual(paid["movements"][0]["destination"], "graveyard")
                self.assertIn(donor["cardId"], session.players["p2"]["zones"]["graveyard"])

    def test_orator_rejects_opponent_controlled_stalemate_and_inactive_sources(self):
        cases = ("opponent", "stalemate", "blanked")
        for case in cases:
            with self.subTest(case=case):
                session, _p1, _p2 = self.started()
                orator = self.active_item(session, "p1", ORATOR, item_id="orator")
                donor = self.active_item(
                    session, "p1", "m-1", item_id="donor",
                    field_zone="stalemate" if case == "stalemate" else "interzone",
                    controller_id="p2" if case == "opponent" else "p1",
                )
                if case == "blanked":
                    orator["effectsDisabled"] = True
                error, payment = session.rules_action_payment(
                    "p1", "activated_effect", None,
                    [f"battlefield|{donor['id']}"], {"tribute": "{H}"},
                )
                self.assertIn("cannot pay Tribute from the field", error)
                self.assertIsNone(payment)

    def test_brabataba_makes_own_vessel_manifestation_transcendent_and_exiles_it(self):
        session, p1, p2 = self.started()
        session.card_rules["m-3"].update(
            power=3, temperaments=["phlegmatic"],
        )
        self.put(p1, "receptacle", {"m-3": "p2"})
        self.active_item(session, "p1", BRABATABA, item_id="brabataba")
        error, payment = session.rules_action_payment(
            "p1", "activated_effect", None,
            ["receptacle|m-3"], {"tribute": "{R}{Y}{B}"},
        )
        self.assertIsNone(error, error)
        paid = session.pay_rules_tribute("p1", payment)
        self.assertEqual(paid["movements"], [{
            "cardId": "m-3", "ownerId": "p2",
            "fromZone": "receptacle", "destination": "exile",
        }])
        self.assertNotIn("m-3", p1["zones"]["receptacle"])
        self.assertEqual(p2["zones"]["exile"], ["m-3"])

    def test_brabataba_is_controller_scoped_and_blanking_removes_permission(self):
        for mode in ("opponent_vessel", "blanked"):
            with self.subTest(mode=mode):
                session, p1, p2 = self.started()
                brabataba = self.active_item(
                    session, "p1", BRABATABA, item_id="brabataba",
                )
                if mode == "opponent_vessel":
                    self.put(p2, "receptacle", {"m-3": "p1"})
                else:
                    self.put(p1, "receptacle", {"m-3": "p2"})
                    brabataba["effectsDisabled"] = True
                error, payment = session.rules_action_payment(
                    "p1", "activated_effect", None,
                    ["receptacle|m-3"], {"tribute": "{H}"},
                )
                self.assertTrue(error)
                self.assertIsNone(payment)

    def essence(self, token_id, owner_id, amount, *, neutral=False):
        return {
            "id": token_id, "ownerId": owner_id, "isEssence": True,
            "temperament": "phlegmatic", "isNeutralCounter": neutral,
            "isExcess": not neutral, "counters": {"essence": amount},
            "expiresTurn": 4,
        }

    def test_cauldron_retains_only_its_controllers_excess_at_end_of_turn(self):
        session, _p1, _p2 = self.started()
        self.active_item(session, "p1", CAULDRON)
        p1_token = self.essence("p1-excess", "p1", 3)
        p2_token = self.essence("p2-excess", "p2", 2)
        neutral = self.essence("neutral", "p2", 1, neutral=True)
        session.tokens = [p1_token, p2_token, neutral]
        expired = session.expire_rules_excess_essence(4)
        self.assertEqual([token["id"] for token in expired], ["p2-excess"])
        self.assertEqual(
            [token["id"] for token in session.tokens], ["p1-excess", "neutral"],
        )
        self.assertEqual(p1_token["counters"]["essence"], 3)

    def test_cauldron_source_must_still_be_active_at_cleanup(self):
        session, _p1, _p2 = self.started()
        cauldron = self.active_item(session, "p1", CAULDRON)
        token = self.essence("p1-excess", "p1", 3)
        session.tokens = [token]
        session.battlefield.remove(cauldron)
        self.assertEqual(session.expire_rules_excess_essence(4), [token])
        self.assertEqual(session.tokens, [])

    def test_cauldron_does_not_create_extra_essence(self):
        session, _p1, _p2 = self.started()
        self.active_item(session, "p1", CAULDRON)
        created = session.add_rules_excess_essence(
            "p1", [{"temperament": "choleric", "amount": 3}],
        )
        self.assertEqual(sum(entry["amount"] for entry in created), 3)
        self.assertEqual(
            sum(token["counters"]["essence"] for token in session.tokens), 3,
        )

