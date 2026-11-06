"""Strict contracts for the three remaining will-played trigger cards."""

import copy
from unittest.mock import patch

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


WILL_PLAYED_NAMES = (
    "Blue Entity",
    "Greed Trap",
    "Ippokridal, of Icy Fervor",
)

CARD_IDS = {
    "Blue Entity": "nbms08jb9t9eqbh_en",
    "Greed Trap": "9phkl58pqrs2j2f_en",
    "Ippokridal, of Icy Fervor": "inner-deserts-040",
}

EXPECTED_ABILITIES = {
    "Blue Entity": [
        {
            "id": "friendly-confrontation-bonus-on-own-will",
            "trigger": {
                "event": "will_played", "eventController": "owner",
                "zone": "confrontation",
            },
            "ongoingEffect": {
                "kind": "power_modifier", "value": 1,
                "duration": "until_end_of_turn",
                "scope": "friendly_manifestations_in_confrontation",
                "excludeSource": True,
            },
        },
    ],
    "Greed Trap": [
        {
            "id": "capture-opponent-manifestation-at-exact-zero",
            "passiveEffect": {"kind": "capture_opponent_exact_zero"},
        },
        {
            "id": "roll-against-opponent-will",
            "optional": True,
            "trigger": {
                "event": "will_played", "eventController": "opponent",
            },
            "targets": {
                "min": 1, "max": 1, "cardType": "manifestation",
                "zones": ["battlefield"], "fieldZone": "confrontation",
                "controller": "opponent",
            },
            "result": {"kind": "roll_d6_target_table", "table": "greed"},
        },
    ],
    "Ippokridal, of Icy Fervor": [
        {
            "id": "create-vitreous-support-token-on-reaction-will",
            "trigger": {
                "event": "will_played", "eventController": "owner",
                "phaseIds": ["confrontation_reaction"],
            },
            "result": {
                "kind": "create_support_token", "power": 1,
                "temperament": "vitreous",
            },
        },
    ],
}


class WillPlayedFamily(RealCardRulesCase):
    ALL = tuple(CARD_IDS.values())

    def started(self, phase="confrontation_reaction"):
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
    def source(card_id, item_id, owner="p1", controller="p1", zone="field", **extra):
        return WillPlayedFamily.field_item(
            item_id, owner, card_id, field_zone=zone,
            controllerId=controller, x=0, y=0, rotation=0,
            stackedOn=None, **extra,
        )

    @staticmethod
    def card_target(item):
        return {
            "kind": "card", "itemId": item["id"],
            "cardId": item["cardId"], "ownerId": item["ownerId"],
            "controllerId": item.get("controllerId") or item["ownerId"],
            "zone": "battlefield",
        }

    @staticmethod
    def snapshot(session):
        return copy.deepcopy((
            session.players, session.battlefield, session.tokens,
            session.rules_engine,
        ))

    def play_will(self, session, player_id, suffix="1"):
        action_id = f"played-will-{suffix}"
        action = {
            "id": action_id,
            "kind": "play_card",
            "controllerId": player_id,
            "source": {
                "cardId": "will-x", "ownerId": player_id, "zone": "hand",
            },
        }
        session.rules_engine.update(
            actionStack=[action], pendingChoice=None,
            priorityPlayerId=player_id,
        )
        return session.queue_rules_tribute_triggers(
            [], player_id, simultaneous_action_id=action_id,
        )

    def accepted_greed_action(self, session, target):
        queued = self.play_will(session, "p2", "greed")
        self.assertEqual(
            [action["ability"]["id"] for action in queued],
            ["roll-against-opponent-will"],
        )
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "optional_stack_action")
        error, _ = session.resolve_rules_choice(
            "p1", choice["id"], option="accept",
        )
        self.assertIsNone(error, error)
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "trigger_targets")
        error, _ = session.resolve_rules_choice(
            "p1", choice["id"], targets=[self.card_target(target)],
        )
        self.assertIsNone(error, error)
        return next(
            action for action in session.rules_engine["actionStack"]
            if (action.get("source") or {}).get("cardId")
            == CARD_IDS["Greed Trap"]
        )

    def test_all_three_compile_the_exact_printed_contracts(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        for name in WILL_PLAYED_NAMES:
            with self.subTest(card=name):
                card_id = CARD_IDS[name]
                expected = EXPECTED_ABILITIES[name]
                self.assertEqual(self.ABILITIES[card_id], expected)
                compiled = rules[card_id]
                self.assertEqual(
                    compiled["triggeredAbilities"],
                    [ability for ability in expected if ability.get("trigger")],
                )
                self.assertEqual(
                    compiled["passiveEffects"],
                    [ability["passiveEffect"] for ability in expected
                     if ability.get("passiveEffect")],
                )
        self.assertTrue(rules[CARD_IDS["Ippokridal, of Icy Fervor"]]["adamant"])

    def test_real_will_carriers_require_exact_controller_zone_phase_and_activity(self):
        blue = CARD_IDS["Blue Entity"]
        session, _p1, _p2 = self.started()
        session.battlefield = [self.source(blue, "blue", zone="confrontation")]
        self.assertEqual(len(self.play_will(session, "p1", "blue-right")), 1)

        for player_id, zone, face_up, disabled in (
            ("p2", "confrontation", True, False),
            ("p1", "interzone", True, False),
            ("p1", "confrontation", False, False),
            ("p1", "confrontation", True, True),
        ):
            with self.subTest(card="Blue Entity", player=player_id, zone=zone,
                              face_up=face_up, disabled=disabled):
                session, _p1, _p2 = self.started()
                source = self.source(blue, "blue", zone=zone)
                source["faceUp"] = face_up
                source["effectsDisabled"] = disabled
                session.battlefield = [source]
                self.assertEqual(self.play_will(session, player_id, "blue-wrong"), [])

        greed = CARD_IDS["Greed Trap"]
        session, _p1, _p2 = self.started()
        foe = self.source("m-1", "foe", owner="p2", controller="p2",
                          zone="confrontation")
        session.battlefield = [self.source(greed, "greed"), foe]
        self.assertEqual(len(self.play_will(session, "p2", "greed-right")), 1)
        choice = session.rules_engine["pendingChoice"]
        error, declined = session.resolve_rules_choice(
            "p1", choice["id"], option="decline",
        )
        self.assertIsNone(error, error)
        self.assertEqual(declined["status"], "declined")
        self.assertFalse(any(
            (action.get("source") or {}).get("cardId") == greed
            for action in session.rules_engine["actionStack"]
        ))

        for player_id, zone, face_up, disabled in (
            ("p1", "field", True, False),
            ("p2", "stalemate", True, False),
            ("p2", "field", False, False),
            ("p2", "field", True, True),
        ):
            with self.subTest(card="Greed Trap", player=player_id, zone=zone,
                              face_up=face_up, disabled=disabled):
                session, _p1, _p2 = self.started()
                source = self.source(greed, "greed", zone=zone)
                source["faceUp"] = face_up
                source["effectsDisabled"] = disabled
                foe = self.source("m-1", "foe", owner="p2", controller="p2",
                                  zone="confrontation")
                session.battlefield = [source, foe]
                self.assertEqual(self.play_will(session, player_id, "greed-wrong"), [])

        ippokridal = CARD_IDS["Ippokridal, of Icy Fervor"]
        session, _p1, _p2 = self.started()
        session.battlefield = [self.source(ippokridal, "ippokridal")]
        self.assertEqual(len(self.play_will(session, "p1", "ippo-right")), 1)
        for player_id, phase, zone, face_up, disabled in (
            ("p2", "confrontation_reaction", "field", True, False),
            ("p1", "end_actions", "field", True, False),
            ("p1", "confrontation_reaction", "stalemate", True, False),
            ("p1", "confrontation_reaction", "field", False, False),
            ("p1", "confrontation_reaction", "field", True, True),
        ):
            with self.subTest(card="Ippokridal", player=player_id, phase=phase,
                              zone=zone, face_up=face_up, disabled=disabled):
                session, _p1, _p2 = self.started(phase)
                source = self.source(ippokridal, "ippokridal", zone=zone)
                source["faceUp"] = face_up
                source["effectsDisabled"] = disabled
                session.battlefield = [source]
                self.assertEqual(self.play_will(session, player_id, "ippo-wrong"), [])

    def test_blue_entity_buffs_only_other_friendly_confrontation_manifestations_until_end(self):
        blue = CARD_IDS["Blue Entity"]
        session, _p1, _p2 = self.started()
        source = self.source(blue, "blue", zone="confrontation")
        ally = self.source("m-1", "ally", zone="confrontation")
        interzone = self.source("m-2", "interzone", zone="interzone")
        foe = self.source("m-3", "foe", owner="p2", controller="p2",
                          zone="confrontation")
        session.battlefield = [source, ally, interzone, foe]
        before = {
            item["id"]: self.power_of(session, item["id"])
            for item in session.battlefield
        }
        queued = self.play_will(session, "p1", "blue-output")
        self.assertEqual(len(queued), 1)
        session.create_rules_ongoing_effects(queued[0])
        self.assertEqual(self.power_of(session, "ally"), before["ally"] + 1)
        for item_id in ("blue", "interzone", "foe"):
            self.assertEqual(self.power_of(session, item_id), before[item_id])
        session.phase_tracker["turn"] += 1
        session.prune_rules_ongoing_effects()
        self.assertEqual(self.power_of(session, "ally"), before["ally"])

    def test_greed_trap_choice_is_atomic_and_all_six_rolls_are_exact(self):
        expected_values = {1: 0, 2: 0, 3: -1, 4: -1, 5: -2, 6: -2}
        for roll, value in expected_values.items():
            with self.subTest(roll=roll):
                session, _p1, _p2 = self.started()
                source = self.source(CARD_IDS["Greed Trap"], "greed")
                ally = self.source("m-0", "ally", zone="confrontation")
                foe = self.source("m-1", "foe", owner="p2", controller="p2",
                                  zone="confrontation")
                other_zone = self.source(
                    "m-2", "other-zone", owner="p2", controller="p2",
                    zone="interzone",
                )
                session.card_rules["m-1"]["power"] = 8
                session.battlefield = [source, ally, foe, other_zone]
                queued = self.play_will(session, "p2", f"greed-{roll}")
                self.assertEqual(len(queued), 1)
                choice = session.rules_engine["pendingChoice"]
                error, _ = session.resolve_rules_choice(
                    "p1", choice["id"], option="accept",
                )
                self.assertIsNone(error, error)
                choice = session.rules_engine["pendingChoice"]
                before = self.snapshot(session)
                invalid = ally if roll % 2 else other_zone
                error, _ = session.resolve_rules_choice(
                    "p1", choice["id"], targets=[self.card_target(invalid)],
                )
                self.assertIsNotNone(error)
                self.assertEqual(self.snapshot(session), before)
                error, _ = session.resolve_rules_choice(
                    "p1", choice["id"], targets=[self.card_target(foe)],
                )
                self.assertIsNone(error, error)
                action = next(
                    entry for entry in session.rules_engine["actionStack"]
                    if (entry.get("source") or {}).get("cardId")
                    == CARD_IDS["Greed Trap"]
                )
                with patch("game.effects.dice.random.randint", return_value=roll):
                    result = session.apply_rules_action_result(action)
                self.assertEqual((result["roll"], result["value"]), (roll, value))
                self.assertEqual(self.power_of(session, "foe"), 8 + value)
                session.phase_tracker["turn"] += 1
                session.prune_rules_ongoing_effects()
                self.assertEqual(self.power_of(session, "foe"), 8 + value)

    def test_greed_trap_captures_only_opposing_manifestations_at_exactly_zero(self):
        greed = CARD_IDS["Greed Trap"]
        cases = (
            ("p2", 0, True, False, "captured"),
            ("p2", -1, True, False, "destroyed"),
            ("p1", 0, True, False, "destroyed"),
            ("p2", 0, False, False, "destroyed"),
            ("p2", 0, True, True, "destroyed"),
        )
        for victim_controller, power, face_up, disabled, expected in cases:
            with self.subTest(victim=victim_controller, power=power,
                              face_up=face_up, disabled=disabled):
                session, p1, p2 = self.started()
                source = self.source(greed, "greed")
                source["faceUp"] = face_up
                source["effectsDisabled"] = disabled
                session.card_rules["m-1"]["power"] = power
                victim = self.source(
                    "m-1", "victim", owner=victim_controller,
                    controller=victim_controller, zone="confrontation",
                )
                session.battlefield = [source, victim]
                result = session.resolve_rules_state_actions()
                self.assertIsNone(session.find_battlefield_item("victim"))
                if expected == "captured":
                    self.assertEqual(p1["zones"]["receptacle"], ["m-1"])
                    self.assertEqual(
                        result["replacements"][0]["replacement"],
                        "capture_opponent_exact_zero",
                    )
                    self.assertEqual(p2["zones"]["graveyard"], [])
                else:
                    owner = p1 if victim_controller == "p1" else p2
                    self.assertEqual(owner["zones"]["graveyard"], ["m-1"])
                    self.assertEqual(result["replacements"], [])

    def test_ippokridal_creates_the_printed_token_and_adamant_blocks_only_moves(self):
        ippokridal = CARD_IDS["Ippokridal, of Icy Fervor"]
        session, _p1, _p2 = self.started()
        source = self.source(ippokridal, "ippokridal")
        session.battlefield = [source]
        queued = self.play_will(session, "p1", "ippo-output")
        self.assertEqual(len(queued), 1)
        result = session.apply_rules_action_result(queued[0])
        token = session.find_battlefield_item(result["createdItemId"])
        self.assertEqual(
            (token["power"], token["temperament"], token["fieldZone"]),
            (1, "vitreous", "confrontation"),
        )
        self.assertTrue(token["isSupport"])
        self.assertEqual(token.get("controllerId") or token["ownerId"], "p1")

        def move_result(reason=None):
            isolated, _p1, _p2 = self.started()
            target = self.source(
                ippokridal, "ippokridal", owner="p2", controller="p2",
                zone="interzone",
            )
            isolated.battlefield = [target]
            result = isolated.apply_rules_action_result({
                "id": "opposing-move", "controllerId": "p1",
                "targets": [self.card_target(target)],
                "ability": {"result": {
                    "kind": "move_target",
                    "zone": "graveyard" if reason == "destroy" else "hand",
                    "position": "top", **({"reason": reason} if reason else {}),
                }},
            })
            return isolated, result

        protected, result = move_result()
        self.assertEqual(result["status"], "prevented_adamant")
        self.assertIsNotNone(protected.find_battlefield_item("ippokridal"))
        destroyed, result = move_result("destroy")
        self.assertEqual(result["status"], "moved")
        self.assertIsNone(destroyed.find_battlefield_item("ippokridal"))
