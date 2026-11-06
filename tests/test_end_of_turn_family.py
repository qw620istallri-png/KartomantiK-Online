"""Strict contracts for the three remaining end-of-turn trigger cards."""

import copy

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


END_OF_TURN_NAMES = (
    "Ergorath, Scribe of the Limbo",
    "Grimoire",
    "Tax of the Malignant",
)

CARD_IDS = {
    "Ergorath, Scribe of the Limbo": "e1zg2gsn0tfqo1y_en",
    "Grimoire": "omhqwnu5tvwlzzg_en",
    "Tax of the Malignant": "inner-deserts-069",
}

EXPECTED_ABILITIES = {
    "Ergorath, Scribe of the Limbo": [
        {
            "id": "ergorath-play-wills-from-limbo",
            "passiveEffect": {
                "kind": "play_wills_from_limbo_hollow_tribute",
            },
        },
        {
            "id": "ergorath-interzone-penalty",
            "trigger": {"event": "end_of_turn", "zone": "interzone"},
            "result": {"kind": "lose_points_shuffle_source_into_deck"},
        },
    ],
    "Grimoire": [
        {
            "id": "grimoire-lets-placed-wills-be-played",
            "passiveEffect": {"kind": "play_attached_wills"},
        },
        {
            "id": "grimoire-places-hand-wills",
            "optional": True,
            "trigger": {"event": "end_of_turn", "zone": "field"},
            "result": {"kind": "grimoire_place"},
        },
    ],
    "Tax of the Malignant": [
        {
            "id": "tax-on-resolution",
            "trigger": {"event": "resolution"},
            "result": {
                "kind": "lose_excess_essence_or_points", "value": 5,
            },
        },
        {
            "id": "tax-at-end-of-turn",
            "trigger": {"event": "end_of_turn"},
            "result": {
                "kind": "lose_excess_essence_or_points", "value": 5,
            },
        },
    ],
}


class EndOfTurnFamily(RealCardRulesCase):
    ALL = tuple(CARD_IDS.values())

    def started(self, phase="end_triggers"):
        session, p1, p2 = self.make_session()
        session.rules_engine.update(
            readyPlayerIds=["p1", "p2"],
            firstManifestationComplete=True,
            priorityPlayerId="p1",
            actionStack=[],
            pendingChoice=None,
        )
        session.phase_tracker["index"] = ADVANCED_PHASES.index(phase)
        return session, p1, p2

    @staticmethod
    def snapshot(session):
        return copy.deepcopy((
            session.players,
            session.battlefield,
            session.tokens,
            session.rules_engine,
        ))

    def source(self, card_id, item_id, owner="p1", controller="p1", zone="field"):
        return self.field_item(
            item_id, owner, card_id, field_zone=zone,
            controllerId=controller, x=0, y=0, rotation=0, stackedOn=None,
        )

    def test_all_three_compile_the_exact_printed_contracts(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        for name in END_OF_TURN_NAMES:
            with self.subTest(card=name):
                card_id = CARD_IDS[name]
                expected = EXPECTED_ABILITIES[name]
                self.assertEqual(self.ABILITIES[card_id], expected)
                compiled = rules[card_id]
                triggered = [
                    ability for ability in expected if ability.get("trigger")
                ]
                passives = [
                    ability["passiveEffect"] for ability in expected
                    if ability.get("passiveEffect")
                ]
                self.assertEqual(compiled["triggeredAbilities"], triggered)
                self.assertEqual(compiled["passiveEffects"], passives)

    def test_end_trigger_source_zones_activity_and_skipped_phase_are_exact(self):
        ergorath = CARD_IDS["Ergorath, Scribe of the Limbo"]
        grimoire = CARD_IDS["Grimoire"]
        tax = CARD_IDS["Tax of the Malignant"]
        cases = (
            (ergorath, "ergorath", "field", "interzone"),
            (grimoire, "grimoire", "interzone", "field"),
        )
        for card_id, item_id, wrong_zone, right_zone in cases:
            with self.subTest(card=card_id):
                session, p1, _p2 = self.started()
                self.put(p1, "hand", ["will-x"])
                item = self.source(card_id, item_id, zone=wrong_zone)
                session.battlefield = [item]
                before = self.snapshot(session)
                self.assertEqual(session.build_rules_end_turn_field_triggers(), [])
                self.assertEqual(self.snapshot(session), before)

                item["fieldZone"] = right_zone
                queued = session.build_rules_end_turn_field_triggers()
                self.assertEqual(len(queued), 1)
                self.assertEqual(
                    queued[0]["ability"]["trigger"]["event"], "end_of_turn"
                )
                item["effectsDisabled"] = True
                self.assertEqual(session.build_rules_end_turn_field_triggers(), [])
                item["effectsDisabled"] = False
                session.rules_engine["skipEndPhaseTurns"] = {
                    "p1": session.phase_tracker["turn"],
                }
                self.assertEqual(session.build_rules_end_turn_field_triggers(), [])

        session, _p1, _p2 = self.started()
        item = self.source(tax, "tax")
        session.battlefield = [item]
        self.assertEqual(
            [action["ability"]["id"] for action in
             session.build_rules_end_turn_field_triggers()],
            ["tax-at-end-of-turn"],
        )
        item["faceUp"] = False
        self.assertEqual(session.build_rules_end_turn_field_triggers(), [])

    def test_ergorath_plays_limbo_wills_for_one_hollow_and_exiles_them(self):
        ergorath = CARD_IDS["Ergorath, Scribe of the Limbo"]

        session, p1, _p2 = self.started("confrontation_reaction")
        session.card_rules["limbo-eph"] = {
            "type": "ephemeral_will", "cost": 2,
            "powerCost": "{G}{G}", "temperaments": ["phlegmatic"],
        }
        self.put(p1, "graveyard", ["limbo-eph"])
        self.put(p1, "hand", ["m-0"])
        session.battlefield = [
            self.source(ergorath, "ergorath", zone="interzone")
        ]
        error, action = session.declare_rules_action(
            "p1", "Play from Limbo", kind="play_card",
            source={"cardId": "limbo-eph", "zone": "graveyard"},
            payment_card_ids=["m-0"],
        )
        self.assertIsNone(error, error)
        self.assertEqual(action["source"]["fixedTribute"], {"hollow": 1})
        self.assertEqual(action["cost"]["tributeRequirements"], {"hollow": 1})
        self.assertIn("m-0", p1["zones"]["graveyard"])
        resolution = session.resolve_rules_top_action()["action"]
        self.assertEqual(resolution["sourceResolution"]["destination"], "exile")
        self.assertIn("limbo-eph", p1["zones"]["exile"])

        session, p1, _p2 = self.started("end_actions")
        session.card_rules["limbo-per"] = {
            "type": "persistent_will", "cost": 2,
            "powerCost": "{G}{G}", "temperaments": ["phlegmatic"],
        }
        self.put(p1, "graveyard", ["limbo-per"])
        self.put(p1, "hand", ["m-0"])
        session.battlefield = [
            self.source(ergorath, "ergorath", zone="interzone")
        ]
        error, _action = session.declare_rules_action(
            "p1", "Play Persistent from Limbo", kind="play_card",
            source={"cardId": "limbo-per", "zone": "graveyard"},
            payment_card_ids=["m-0"],
        )
        self.assertIsNone(error, error)
        resolution = session.resolve_rules_top_action()["action"]
        played = session.find_battlefield_item(
            resolution["sourceResolution"]["itemId"]
        )
        self.assertTrue(played["exileIfLeaves"])
        session._rules_remove_field_item_by_effect(played, "p1", "hand")
        self.assertIn("limbo-per", p1["zones"]["exile"])
        self.assertNotIn("limbo-per", p1["zones"]["hand"])

    def test_ergorath_end_trigger_penalizes_controller_then_shuffles_to_owner(self):
        ergorath = CARD_IDS["Ergorath, Scribe of the Limbo"]
        session, p1, p2 = self.started()
        item = self.source(
            ergorath, "ergorath", owner="p1", controller="p2",
            zone="interzone",
        )
        session.battlefield = [item]
        before_p1, before_p2 = p1["score"], p2["score"]
        queued = session.build_rules_end_turn_field_triggers()
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0]["controllerId"], "p2")
        result = session.apply_rules_action_result(queued[0])
        self.assertEqual(result["status"], "moved")
        self.assertEqual((p1["score"], p2["score"]), (before_p1, before_p2 - 10))
        self.assertIsNone(session.find_battlefield_item("ergorath"))
        self.assertIn(ergorath, p1["zones"]["deck"])
        self.assertNotIn(ergorath, p2["zones"]["deck"])

    def test_grimoire_places_plays_and_exiles_its_attached_wills(self):
        grimoire = CARD_IDS["Grimoire"]
        session, p1, _p2 = self.started()
        session.card_rules["will-p"] = {
            "type": "persistent_will", "cost": 1,
            "powerCost": "{H}", "temperaments": ["hollow"],
        }
        self.put(p1, "hand", ["will-x", "will-p", "m-1"])
        host = self.source(grimoire, "grimoire")
        session.battlefield = [host]
        queued = session.build_rules_end_turn_field_triggers()
        self.assertEqual(len(queued), 1)
        action = queued[0]
        self.assertTrue(action["optional"])
        action["optionalAccepted"] = True
        result = session.apply_rules_action_result(action)
        self.assertEqual(result["choiceKind"], "discard_from_hand")
        choice = session.rules_engine["pendingChoice"]
        before = self.snapshot(session)
        error, _ = session.resolve_rules_choice(
            "p1", choice["id"], card_ids=["m-1"]
        )
        self.assertIsNotNone(error)
        self.assertEqual(self.snapshot(session), before)
        error, placed = session.resolve_rules_choice(
            "p1", choice["id"], card_ids=["will-x", "will-p"]
        )
        self.assertIsNone(error, error)
        self.assertEqual(placed["count"], 2)
        self.assertEqual(p1["zones"]["hand"], ["m-1"])
        self.assertEqual(
            [entry["cardId"] for entry in host["attachedCards"]],
            ["will-x", "will-p"],
        )

        session.phase_tracker["index"] = ADVANCED_PHASES.index("end_actions")
        session.rules_engine.update(priorityPlayerId="p1", pendingChoice=None)
        session.add_rules_excess_essence(
            "p1", [{"temperament": "hollow", "amount": 1}]
        )
        error, play = session.declare_rules_action(
            "p1", "Play attached Will", kind="play_card",
            source={
                "cardId": "will-p", "zone": "attached",
                "itemId": "grimoire",
            },
        )
        self.assertIsNone(error, error)
        self.assertEqual(play["source"]["zone"], "attached")
        self.assertEqual(
            [entry["cardId"] for entry in host["attachedCards"]], ["will-x"]
        )
        session.resolve_rules_top_action()
        self.assertTrue(any(
            item.get("cardId") == "will-p" for item in session.battlefield
        ))

        session._rules_remove_field_item(host, "p1", "graveyard")
        self.assertIn("will-x", p1["zones"]["exile"])
        self.assertNotIn("will-p", p1["zones"]["exile"])

    def test_tax_applies_both_printed_events_and_both_payment_branches(self):
        tax = CARD_IDS["Tax of the Malignant"]

        session, p1, p2 = self.started("resolution_effects")
        session.battlefield = [self.source(tax, "tax")]
        session.add_rules_excess_essence(
            "p1", [{"temperament": "hollow", "amount": 3}]
        )
        before_scores = (p1["score"], p2["score"])
        queued = session.queue_rules_resolution_field_triggers(defer=True)
        self.assertEqual(
            [action["ability"]["id"] for action in queued],
            ["tax-on-resolution"],
        )
        result = session.apply_rules_action_result(queued[0])
        self.assertEqual(result["status"], "applied")
        self.assertFalse(any(
            token.get("ownerId") == "p1" and token.get("isExcess")
            for token in session.tokens
        ))
        self.assertEqual(
            (p1["score"], p2["score"]),
            (before_scores[0], before_scores[1] - 5),
        )

        session, p1, p2 = self.started()
        session.battlefield = [self.source(tax, "tax")]
        session.add_rules_excess_essence(
            "p2", [{"temperament": "phlegmatic", "amount": 2}]
        )
        before_scores = (p1["score"], p2["score"])
        queued = session.build_rules_end_turn_field_triggers()
        self.assertEqual(
            [action["ability"]["id"] for action in queued],
            ["tax-at-end-of-turn"],
        )
        result = session.apply_rules_action_result(queued[0])
        self.assertEqual(result["status"], "applied")
        self.assertFalse(any(
            token.get("ownerId") == "p2" and token.get("isExcess")
            for token in session.tokens
        ))
        self.assertEqual(
            (p1["score"], p2["score"]),
            (before_scores[0] - 5, before_scores[1]),
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
