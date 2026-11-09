"""Strict semantic coverage for five standalone outcome cards."""

import copy
from unittest.mock import patch

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


MUTATE = "odqcx9kkqe029se_en"
KISS = "inner-deserts-116"
FREENYA = "b6ebpyb30urtas2_en"
VETERAN = "iwpmdq754ew0mw7_en"
OBELISK = "9bkn03sc9veaa88_en"

EXPECTED_ABILITIES = {
    MUTATE: [{
        "id": "roll-mutation-table",
        "action": "play_card",
        "targets": {
            "min": 1, "max": 1, "cardType": "manifestation",
            "zones": ["battlefield"],
        },
        "result": {"kind": "roll_d6_target_table", "table": "mutation"},
    }],
    KISS: [{
        "id": "immediate-end-confrontation-unless-payment",
        "action": "play_card",
        "immediate": True,
        "targets": {"min": 0, "max": 0},
        "result": {
            "kind": "end_confrontation_unless_payment",
            "payment": "{H}{H}{H}",
            "exileOnDecline": True,
            "reduceWinnerManifestationOnControllerDefeat": True,
        },
    }],
    FREENYA: [{
        "id": "freenya-free-limbo-will",
        "optional": True,
        "trigger": {
            "event": "card_played", "eventController": "owner",
            "playedFromZone": "hand",
            "eventCardTypes": ["ephemeral_will", "persistent_will"],
        },
        "result": {"kind": "grant_limbo_will_play"},
    }],
    VETERAN: [{
        "id": "support-from-limbo-this-turn",
        "playPermission": {
            "conditionEvent": "beginning_of_turn",
            "requiredZone": "graveyard", "playFromZone": "graveyard",
            "phaseIds": ["confrontation_reaction"], "asSupport": True,
            "temperamentOverride": "hollow",
            "winAsSupportDestination": "exile",
            "duration": "until_end_of_turn",
        },
    }],
    OBELISK: [{
        "id": "obelisk-exchanges-gifts",
        "optional": True,
        "trigger": {"event": "reaction"},
        "result": {"kind": "obelisk_gift"},
    }],
}


class StandaloneOutcomesFamily(RealCardRulesCase):
    ALL = (MUTATE, KISS, FREENYA, VETERAN, OBELISK)

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

    @staticmethod
    def target(item):
        return {
            "kind": "card", "itemId": item["id"],
            "cardId": item["cardId"], "ownerId": item["ownerId"],
        }

    def apply_ability(self, session, card_id, item=None, targets=None):
        ability = self.ABILITIES[card_id][0]
        owner_id = (item or {}).get("ownerId", "p1")
        return session.apply_rules_action_result({
            "id": "strict-action", "controllerId": owner_id,
            "source": {
                "cardId": card_id, "itemId": (item or {}).get("id"),
                "ownerId": owner_id,
            },
            "targets": list(targets or []), "ability": ability,
        })

    def resolve_top(self, session):
        self.assertIsNone(session.pass_rules_priority("p2")[0])
        error, result = session.pass_rules_priority("p1")
        self.assertIsNone(error, error)
        return result

    def test_compiles_all_five_exact_contracts(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        for card_id, abilities in EXPECTED_ABILITIES.items():
            with self.subTest(card_id=card_id):
                self.assertEqual(self.ABILITIES[card_id], abilities)
        self.assertEqual(rules[MUTATE]["playedAbilities"], EXPECTED_ABILITIES[MUTATE])
        self.assertEqual(rules[KISS]["playedAbilities"], EXPECTED_ABILITIES[KISS])
        self.assertEqual(rules[FREENYA]["triggeredAbilities"], EXPECTED_ABILITIES[FREENYA])
        self.assertEqual(rules[VETERAN]["playPermissions"], EXPECTED_ABILITIES[VETERAN])
        self.assertEqual(rules[OBELISK]["triggeredAbilities"], EXPECTED_ABILITIES[OBELISK])

    def test_mutate_all_six_faces_have_exact_permanent_outcomes(self):
        outcomes = {
            1: (None, None), 2: (None, None), 3: (5, "hollow"),
            4: (7, "phlegmatic"), 5: (7, "phlegmatic"),
            6: (8, "phlegmatic"),
        }
        for roll, (expected_power, expected_temperament) in outcomes.items():
            with self.subTest(roll=roll):
                session, _p1, p2 = self.started()
                session.card_rules["m-1"].update(
                    power=5, temperaments=["phlegmatic"],
                )
                victim = self.field_item("victim", "p2", "m-1")
                session.battlefield = [victim]
                with patch("game.effects.dice.random.randint", return_value=roll):
                    result = self.apply_ability(
                        session, MUTATE, targets=[self.target(victim)],
                    )
                self.assertEqual(result["roll"], roll)
                if expected_power is None:
                    self.assertIsNone(session.find_battlefield_item("victim"))
                    self.assertEqual(p2["zones"]["graveyard"], ["m-1"])
                    continue
                self.assertEqual(
                    session.rules_manifestation_characteristics(victim),
                    {
                        "power": expected_power,
                        "temperament": expected_temperament,
                    },
                )
                session.phase_tracker["turn"] += 1
                session.prune_rules_ongoing_effects()
                self.assertEqual(
                    session.rules_manifestation_characteristics(victim),
                    {
                        "power": expected_power,
                        "temperament": expected_temperament,
                    },
                )

    def test_mutate_missing_target_rolls_but_changes_nothing(self):
        session, p1, p2 = self.started()
        before = copy.deepcopy((session.battlefield, p1["zones"], p2["zones"]))
        with patch("game.effects.dice.random.randint", return_value=6):
            result = self.apply_ability(
                session, MUTATE,
                targets=[{
                    "kind": "card", "itemId": "gone",
                    "cardId": "m-1", "ownerId": "p2",
                }],
            )
        self.assertEqual((result["status"], result["roll"]), ("target_missing", 6))
        self.assertEqual((session.battlefield, p1["zones"], p2["zones"]), before)

    def kiss_setup(self, *, tied=False):
        session, p1, p2 = self.started()
        session.card_rules["m-1"].update(power=2, temperaments=["phlegmatic"])
        session.card_rules["m-2"].update(
            power=2 if tied else 5, temperaments=["phlegmatic"],
        )
        own = self.field_item(
            "own", "p1", "m-1", counters={"power": 0 if tied else -1},
        )
        winner = self.field_item("winner", "p2", "m-2")
        session.battlefield = [own, winner]
        self.put(p1, "graveyard", [KISS])
        result = self.apply_ability(session, KISS)
        self.assertEqual(result["choiceKind"], "immediate_effect_payment")
        return session, p1, p2, own, winner

    def test_kiss_payment_is_atomic_and_keeps_phase_and_source(self):
        session, p1, _p2, _own, _winner = self.kiss_setup()
        session.add_rules_excess_essence(
            "p2", [{"temperament": "hollow", "amount": 3}],
        )
        choice = session.rules_engine["pendingChoice"]
        error, action = session.declare_rules_action(
            "p1", "Cannot interrupt", kind="play_card",
            source={"cardId": "will-x", "zone": "hand"},
        )
        self.assertIn("choice", error.lower())
        self.assertIsNone(action)
        error, result = session.resolve_rules_choice(
            "p2", choice["id"], option="pay",
        )
        self.assertIsNone(error, error)
        self.assertEqual(result["status"], "paid")
        self.assertEqual(session.current_phase_id(), "confrontation_reaction")
        self.assertIn(KISS, p1["zones"]["graveyard"])
        self.assertNotIn(KISS, p1["zones"]["exile"])
        self.assertIsNone(session.rules_engine["pendingChoice"])

    def test_kiss_decline_ends_phase_exiles_source_and_uses_base_not_current_power(self):
        session, p1, _p2, own, winner = self.kiss_setup()
        self.assertEqual(session.rules_manifestation_characteristics(own)["power"], 1)
        choice = session.rules_engine["pendingChoice"]
        error, result = session.resolve_rules_choice(
            "p2", choice["id"], option="decline",
        )
        self.assertIsNone(error, error)
        self.assertEqual(result["powerLoss"], 2)
        self.assertEqual(session.current_phase_id(), "resolution_compare")
        self.assertIn(KISS, p1["zones"]["exile"])
        followup = session.rules_engine["pendingChoice"]
        error, _ = session.resolve_rules_choice(
            "p1", followup["id"], targets=[self.target(winner)],
        )
        self.assertIsNone(error, error)
        resolved = session.resolve_rules_immediate_actions()[0]
        self.assertEqual(resolved["action"]["effectResult"]["value"], -2)
        self.assertEqual(
            session.rules_manifestation_characteristics(winner)["power"], 3,
        )

    def test_kiss_stalemate_has_no_winner_power_followup_but_still_exiles(self):
        session, p1, _p2, _own, _winner = self.kiss_setup(tied=True)
        choice = session.rules_engine["pendingChoice"]
        error, result = session.resolve_rules_choice(
            "p2", choice["id"], option="decline",
        )
        self.assertIsNone(error, error)
        self.assertTrue(result["confrontationResult"]["stalemate"])
        self.assertNotIn("followupChoiceId", result)
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertIn(KISS, p1["zones"]["exile"])

    def freenya_setup(self):
        session, p1, p2 = self.started()
        session.card_rules.update({
            "hand-will": {
                "type": "ephemeral_will", "cost": 1,
                "powerCost": "{G}", "temperaments": ["phlegmatic"],
            },
            "limbo-eph": {
                "type": "ephemeral_will", "cost": 6,
                "powerCost": "{R}{R}{R}{R}{R}{R}",
                "temperaments": ["choleric"],
            },
            "limbo-per": {
                "type": "persistent_will", "cost": 6,
                "powerCost": "{R}{R}{R}{R}{R}{R}",
                "temperaments": ["choleric"],
            },
        })
        freenya = self.field_item("freenya", "p1", FREENYA, "field")
        session.battlefield = [freenya]
        return session, p1, p2, freenya

    def grant_freenya(self, session, freenya):
        result = self.apply_ability(session, FREENYA, freenya)
        self.assertEqual(result["status"], "granted")
        self.assertEqual(len(session.rules_engine["playPermissions"]), 1)

    def play_free_limbo_will(self, session, card_id):
        error, action = session.declare_rules_action(
            "p1", "Freenya free Will", kind="play_card",
            source={
                "cardId": card_id, "zone": "graveyard", "containerId": "p1",
            },
        )
        self.assertIsNone(error, error)
        self.assertFalse(action["cost"]["tributePaid"])
        self.assertEqual(action["cost"]["tributeRequirements"], {})
        return action, self.resolve_top(session)

    def test_freenya_triggers_only_for_owners_will_played_from_hand(self):
        session, _p1, _p2, freenya = self.freenya_setup()

        def queued(card_id, controller, zone):
            return session.queue_rules_triggers(
                FREENYA, "p1", "card_played", zone="field",
                item_id=freenya["id"], face_up=True, controller_id="p1",
                event_controller_id=controller, event_card_id=card_id,
                played=True, defer=True,
                related_action={
                    "id": "played-action",
                    "source": {"cardId": card_id, "zone": zone},
                },
            )

        self.assertEqual(len(queued("hand-will", "p1", "hand")), 1)
        self.assertEqual(queued("hand-will", "p2", "hand"), [])
        self.assertEqual(queued("hand-will", "p1", "graveyard"), [])
        self.assertEqual(queued("m-1", "p1", "hand"), [])
        freenya["fieldZone"] = "stalemate"
        self.assertEqual(queued("hand-will", "p1", "hand"), [])

    def test_freenya_optional_trigger_can_be_declined_without_grant(self):
        session, _p1, _p2, freenya = self.freenya_setup()
        session.queue_rules_triggers(
            FREENYA, "p1", "card_played", zone="field",
            item_id=freenya["id"], face_up=True, controller_id="p1",
            event_controller_id="p1", event_card_id="hand-will",
            event_source_zone="hand", played=True,
        )
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "optional_stack_action")
        error, _ = session.resolve_rules_choice(
            "p1", choice["id"], option="decline",
        )
        self.assertIsNone(error, error)
        self.assertEqual(session.rules_engine["playPermissions"], [])
        self.assertEqual(session.rules_engine["actionStack"], [])

    def test_freenya_grants_exactly_one_free_limbo_play_without_recursion(self):
        session, p1, _p2, freenya = self.freenya_setup()
        self.put(p1, "graveyard", ["limbo-eph", "limbo-per"])
        self.grant_freenya(session, freenya)
        _action, _resolution = self.play_free_limbo_will(session, "limbo-eph")
        self.assertIn("limbo-eph", p1["zones"]["exile"])
        self.assertEqual(session.rules_engine["playPermissions"], [])
        session.rules_engine.update(priorityPlayerId="p1", priorityPasses=[])
        error, action = session.declare_rules_action(
            "p1", "No second free Will", kind="play_card",
            source={
                "cardId": "limbo-per", "zone": "graveyard",
                "containerId": "p1",
            },
        )
        self.assertIn("no effect", error.lower())
        self.assertIsNone(action)

    def test_freenya_persistent_will_exiles_for_hand_limbo_or_deck_but_not_vessel(self):
        for destination, expected in (
            ("hand", "exile"), ("graveyard", "exile"),
            ("deck", "exile"), ("receptacle", "receptacle"),
        ):
            with self.subTest(destination=destination):
                session, p1, _p2, freenya = self.freenya_setup()
                session.phase_tracker["index"] = ADVANCED_PHASES.index(
                    "end_actions"
                )
                self.put(p1, "graveyard", ["limbo-per"])
                self.grant_freenya(session, freenya)
                _action, resolution = self.play_free_limbo_will(
                    session, "limbo-per",
                )
                item = session.find_battlefield_item(
                    resolution["action"]["sourceResolution"]["itemId"],
                )
                self.assertTrue(item["exileIfLeaves"])
                session._rules_remove_field_item_by_effect(
                    item, "p1", destination, "top",
                )
                self.assertIn("limbo-per", p1["zones"][expected])

    def test_veteran_permission_is_snapshotted_at_turn_start_and_used_once(self):
        session, p1, _p2 = self.started("recovery_start")
        self.put(p1, "graveyard", [VETERAN])
        permissions = session.grant_rules_beginning_turn_permissions()
        self.assertEqual(len(permissions), 1)
        self.assertEqual(
            (
                permissions[0]["cardId"], permissions[0]["asSupport"],
                permissions[0]["temperamentOverride"],
                permissions[0]["winAsSupportDestination"],
            ),
            (VETERAN, True, "hollow", "exile"),
        )
        session.phase_tracker["index"] = ADVANCED_PHASES.index(
            "confrontation_reaction"
        )
        session.rules_engine["priorityPlayerId"] = "p1"
        error, action = session.declare_rules_action(
            "p1", "Veteran Support", kind="play_card", as_support=True,
            source={
                "cardId": VETERAN, "zone": "graveyard", "containerId": "p1",
            },
        )
        self.assertIsNone(error, error)
        self.assertTrue(action["sourceOnStack"])
        resolution = self.resolve_top(session)
        item = session.find_battlefield_item(
            resolution["action"]["sourceResolution"]["itemId"],
        )
        self.assertTrue(item["isSupport"])
        self.assertEqual(
            session.rules_manifestation_characteristics(item)["temperament"],
            "hollow",
        )
        self.assertEqual(item["supportWinDestination"], "exile")
        self.assertEqual(session.rules_engine["playPermissions"], [])

    def test_veteran_entering_limbo_after_turn_start_gets_no_permission(self):
        session, p1, _p2 = self.started("recovery_start")
        self.assertEqual(session.grant_rules_beginning_turn_permissions(), [])
        self.put(p1, "graveyard", [VETERAN])
        session.phase_tracker["index"] = ADVANCED_PHASES.index(
            "confrontation_reaction"
        )
        session.rules_engine["priorityPlayerId"] = "p1"
        error, permission = session.rules_zone_play_permission(
            "p1", "p1", "graveyard", VETERAN,
        )
        self.assertIn("beginning-of-turn", error)
        self.assertIsNone(permission)

    def test_veteran_winning_as_support_exiles_but_winning_normally_does_not(self):
        for support in (True, False):
            with self.subTest(support=support):
                session, p1, _p2 = self.started("resolution_compare")
                session.card_rules[VETERAN]["power"] = 5
                session.card_rules["m-1"]["power"] = 1
                veteran = self.field_item(
                    "veteran", "p1", VETERAN, "confrontation",
                )
                if support:
                    session.mark_rules_support_entry(veteran)
                else:
                    session.mark_rules_confrontation_entry(veteran)
                loser = self.field_item(
                    "loser", "p2", "m-1", "confrontation",
                )
                session.mark_rules_confrontation_entry(loser)
                session.battlefield = [veteran, loser]
                result = session.prepare_rules_confrontation_result()
                self.assertEqual(result["winnerId"], "p1")
                session.phase_tracker["index"] = ADVANCED_PHASES.index(
                    "resolution_move"
                )
                session.begin_rules_confrontation_cleanup()
                if support:
                    self.assertIn(VETERAN, p1["zones"]["exile"])
                    self.assertIsNone(session.find_battlefield_item("veteran"))
                else:
                    self.assertNotIn(VETERAN, p1["zones"]["exile"])

    def obelisk_setup(self, first_power=5, second_power=2):
        session, p1, p2 = self.started()
        session.card_rules["m-1"]["power"] = first_power
        session.card_rules["m-2"]["power"] = second_power
        self.put(p1, "hand", ["m-1", "m-3"])
        self.put(p2, "hand", ["m-2"])
        obelisk = self.field_item(
            "obelisk", "p1", OBELISK, "field", x=100.0, y=100.0,
            rotation=0.0, stackedOn=None,
        )
        first1 = self.field_item(
            "first1", "p1", "m-4", x=200.0, y=200.0,
            rotation=0.0, stackedOn=None,
        )
        first2 = self.field_item(
            "first2", "p2", "m-5", x=300.0, y=300.0,
            rotation=0.0, stackedOn=None,
        )
        session.battlefield = [obelisk, first1, first2]
        session.rules_engine["firstManifestationItemIds"] = {
            "p1": "first1", "p2": "first2",
        }
        return session, p1, p2, obelisk, first1, first2

    def offer_obelisk(self, session, option="accept"):
        session.queue_rules_reaction_triggers()
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "optional_stack_action")
        error, result = session.resolve_rules_choice(
            "p1", choice["id"], option=option,
        )
        self.assertIsNone(error, error)
        return result

    def resolve_obelisk_to_gift(self, session):
        self.offer_obelisk(session)
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertEqual(len(session.rules_engine["actionStack"]), 1)
        self.resolve_top(session)
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["destination"], "obelisk_gift")
        return choice

    def test_obelisk_can_be_declined_before_stack_without_revealing_or_moving(self):
        session, p1, p2, _ob, _first1, _first2 = self.obelisk_setup()
        before = copy.deepcopy((p1["zones"], p2["zones"], session.battlefield))
        self.offer_obelisk(session, option="decline")
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertEqual(session.rules_engine["actionStack"], [])
        self.assertEqual((p1["zones"], p2["zones"], session.battlefield), before)

    def test_obelisk_selects_gifts_only_on_resolution_and_hides_first_choice(self):
        session, p1, _p2, _ob, _first1, _first2 = self.obelisk_setup()
        self.offer_obelisk(session)
        self.assertIn("m-1", p1["zones"]["hand"])
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.resolve_top(session)
        choice = session.rules_engine["pendingChoice"]
        error, _ = session.resolve_rules_choice(
            "p1", choice["id"], card_ids=["m-1"],
        )
        self.assertIsNone(error, error)
        reply = session.rules_engine["pendingChoice"]
        self.assertEqual(reply["destination"], "obelisk_reply")
        public = session.serialize_for("p2", "player")["rulesEngine"][
            "pendingChoice"
        ]
        self.assertNotIn("_giftCardId", public)
        error, action = session.declare_rules_action(
            "p1", "No interruption", kind="play_card",
            source={"cardId": "will-x", "zone": "hand"},
        )
        self.assertIn("choice", error.lower())
        self.assertIsNone(action)

    def test_obelisk_exchange_preserves_owners_and_boosts_higher_givers_first(self):
        session, p1, p2, _ob, first1, first2 = self.obelisk_setup(5, 2)
        choice = self.resolve_obelisk_to_gift(session)
        self.assertIsNone(
            session.resolve_rules_choice(
                "p1", choice["id"], card_ids=["m-1"],
            )[0]
        )
        reply = session.rules_engine["pendingChoice"]
        error, result = session.resolve_rules_choice(
            "p2", reply["id"], card_ids=["m-2"],
        )
        self.assertIsNone(error, error)
        self.assertEqual(result["status"], "exchanged")
        self.assertIn("m-1", p2["zones"]["receptacle"])
        self.assertIn("m-2", p1["zones"]["receptacle"])
        self.assertEqual(
            session.card_owner_in_zone("p2", "receptacle", "m-1"), "p1",
        )
        self.assertEqual(
            session.card_owner_in_zone("p1", "receptacle", "m-2"), "p2",
        )
        self.assertEqual(
            session.rules_manifestation_characteristics(first1)["power"],
            session.card_rules["m-4"]["power"] + 3,
        )
        self.assertEqual(
            session.rules_manifestation_characteristics(first2)["power"],
            session.card_rules["m-5"]["power"],
        )
        session.phase_tracker["turn"] += 1
        session.prune_rules_ongoing_effects()
        self.assertEqual(
            session.rules_manifestation_characteristics(first1)["power"],
            session.card_rules["m-4"]["power"],
        )

    def test_obelisk_equal_gifts_exchange_without_any_boost(self):
        session, p1, p2, _ob, first1, first2 = self.obelisk_setup(3, 3)
        base = (
            session.rules_manifestation_characteristics(first1)["power"],
            session.rules_manifestation_characteristics(first2)["power"],
        )
        choice = self.resolve_obelisk_to_gift(session)
        self.assertIsNone(
            session.resolve_rules_choice(
                "p1", choice["id"], card_ids=["m-1"],
            )[0]
        )
        reply = session.rules_engine["pendingChoice"]
        error, result = session.resolve_rules_choice(
            "p2", reply["id"], card_ids=["m-2"],
        )
        self.assertIsNone(error, error)
        self.assertIsNone(result["boosted"])
        self.assertEqual(
            (
                session.rules_manifestation_characteristics(first1)["power"],
                session.rules_manifestation_characteristics(first2)["power"],
            ),
            base,
        )
        self.assertIn("m-2", p1["zones"]["receptacle"])
        self.assertIn("m-1", p2["zones"]["receptacle"])

    def test_obelisk_invalid_gift_is_atomic(self):
        session, p1, p2, _ob, _first1, _first2 = self.obelisk_setup()
        session.card_rules["will-x"]["type"] = "ephemeral_will"
        self.put(p1, "hand", ["m-1", "will-x"])
        choice = self.resolve_obelisk_to_gift(session)
        before = copy.deepcopy((p1["zones"], p2["zones"], choice))
        error, result = session.resolve_rules_choice(
            "p1", choice["id"], card_ids=["will-x"],
        )
        self.assertIsNotNone(error)
        self.assertIsNone(result)
        self.assertEqual(
            (p1["zones"], p2["zones"], session.rules_engine["pendingChoice"]),
            before,
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
