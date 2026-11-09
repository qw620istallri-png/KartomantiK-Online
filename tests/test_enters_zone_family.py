"""Strict opponent-Vessel entry contracts for Inspired Nimbus and Worm Bomb."""

from unittest.mock import patch

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


ENTERS_ZONE_NAMES = (
    "Inspired Nimbus",
    "Worm Bomb",
)

NIMBUS = "shiox5powdvu5nl_en"
WORM_BOMB = "7jaany95hy1h5pz_en"
PILLAR = "7gaov0c4cjndl9w_en"

NIMBUS_ABILITY = {
    "id": "nimbus-grants-free-will-play",
    "trigger": {
        "event": "enters_zone",
        "zone": "receptacle",
        "container": "opponent",
    },
    "result": {"kind": "grant_free_will_play"},
}

WORM_BOMB_ABILITY = {
    "id": "worm-bomb-destroys-random-vessel-manifestations",
    "trigger": {
        "event": "enters_zone",
        "zone": "receptacle",
        "container": "opponent",
    },
    "result": {
        "kind": "destroy_random_vessel_manifestations",
        "count": 3,
    },
}


class EntersZoneFamily(RealCardRulesCase):
    ALL = (NIMBUS, WORM_BOMB)

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
            priorityPasses=[],
            actionStack=[],
            pendingChoice=None,
        )
        return session, p1, p2

    @staticmethod
    def manifestation(session, card_id, power=2):
        session.card_rules[card_id] = {
            "type": "manifestation",
            "power": power,
            "temperaments": ["phlegmatic"],
        }

    def opponent_vessel_action(self, session, card_id, owner="p1", container="p2"):
        actions = session.queue_rules_zone_entry_triggers(
            card_id,
            owner,
            container,
            "receptacle",
            defer=True,
        )
        self.assertEqual(len(actions), 1)
        return actions[0]

    def test_both_compile_the_exact_printed_contract(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        self.assertEqual(self.ABILITIES[NIMBUS], [NIMBUS_ABILITY])
        self.assertEqual(self.ABILITIES[WORM_BOMB], [WORM_BOMB_ABILITY])
        self.assertEqual(
            rules[NIMBUS]["triggeredAbilities"], [NIMBUS_ABILITY],
        )
        self.assertEqual(
            rules[WORM_BOMB]["triggeredAbilities"], [WORM_BOMB_ABILITY],
        )

    def test_both_trigger_only_when_they_enter_an_opponents_vessel(self):
        for card_id, ability_id in (
            (NIMBUS, NIMBUS_ABILITY["id"]),
            (WORM_BOMB, WORM_BOMB_ABILITY["id"]),
        ):
            with self.subTest(card_id=card_id):
                session, _p1, _p2 = self.started()
                own = session.queue_rules_zone_entry_triggers(
                    card_id, "p1", "p1", "receptacle", defer=True,
                )
                wrong_zone = session.queue_rules_zone_entry_triggers(
                    card_id, "p1", "p2", "graveyard", defer=True,
                )
                unknown = session.queue_rules_zone_entry_triggers(
                    card_id, "p1", "missing", "receptacle", defer=True,
                )
                opponent = session.queue_rules_zone_entry_triggers(
                    card_id, "p1", "p2", "receptacle", defer=True,
                )
                self.assertEqual((own, wrong_zone, unknown), ([], [], []))
                self.assertEqual(
                    [entry["ability"]["id"] for entry in opponent],
                    [ability_id],
                )
                self.assertEqual(
                    opponent[0]["source"]["containerId"], "p2",
                )

    def test_nimbus_grants_the_card_owner_one_free_hand_will_this_turn(self):
        session, p1, p2 = self.started()
        self.put(p2, "receptacle", {NIMBUS: "p1"})
        action = self.opponent_vessel_action(session, NIMBUS)

        result = session.apply_rules_action_result(action)
        self.assertEqual(
            (result["status"], result["playerId"]), ("granted", "p1"),
        )
        permission = session.rules_engine["playPermissions"][-1]
        self.assertEqual(
            (
                permission["playerId"], permission["fromZone"],
                permission["anyWill"], permission["noTribute"],
                permission["turn"],
            ),
            ("p1", "hand", True, True, 3),
        )
        self.assertNotEqual(permission["playerId"], p2["id"])

        session.card_rules["expensive-will"] = {
            "type": "ephemeral_will",
            "cost": 3,
            "powerCost": "{G}{G}{G}",
            "temperaments": ["phlegmatic"],
        }
        self.put(p1, "hand", ["expensive-will"])
        error, played = session.declare_rules_action(
            "p1",
            "Free Will",
            kind="play_card",
            source={"cardId": "expensive-will", "zone": "hand"},
        )
        self.assertIsNone(error, error)
        self.assertEqual(played["cost"]["tributeRequirements"], {})
        self.assertEqual(session.rules_engine["playPermissions"], [])
        session.resolve_rules_top_action()
        self.assertIn("expensive-will", p1["zones"]["graveyard"])

    def test_nimbus_permission_cannot_be_reused_or_carried_to_the_next_turn(self):
        for mode in ("consumed", "next_turn"):
            with self.subTest(mode=mode):
                session, p1, p2 = self.started()
                self.put(p2, "receptacle", {NIMBUS: "p1"})
                action = self.opponent_vessel_action(session, NIMBUS)
                session.apply_rules_action_result(action)
                session.card_rules["costly-will"] = {
                    "type": "ephemeral_will",
                    "cost": 2,
                    "powerCost": "{G}{G}",
                    "temperaments": ["phlegmatic"],
                }
                self.put(p1, "hand", ["costly-will"])
                if mode == "consumed":
                    error, _first = session.declare_rules_action(
                        "p1", "Free Will", kind="play_card",
                        source={"cardId": "costly-will", "zone": "hand"},
                    )
                    self.assertIsNone(error, error)
                    session.rules_engine["actionStack"] = []
                    self.put(p1, "hand", ["costly-will"])
                else:
                    session.phase_tracker["turn"] = 4
                error, action = session.declare_rules_action(
                    "p1", "No longer free", kind="play_card",
                    source={"cardId": "costly-will", "zone": "hand"},
                )
                self.assertIsNotNone(error)
                self.assertIsNone(action)

    def test_worm_bomb_destroys_exactly_three_other_random_manifestations(self):
        session, p1, p2 = self.started()
        for card_id in ("m-a", "m-b", "m-c", "m-d"):
            self.manifestation(session, card_id)
        session.card_rules["vessel-will"] = {
            "type": "persistent_will",
            "cost": 1,
            "powerCost": "{G}",
            "temperaments": ["phlegmatic"],
        }
        self.put(p2, "receptacle", {
            WORM_BOMB: "p1",
            "m-a": "p1",
            "m-b": "p2",
            "m-c": "p1",
            "m-d": "p2",
            "vessel-will": "p1",
        })
        action = self.opponent_vessel_action(session, WORM_BOMB)

        with patch("random.shuffle", new=lambda cards: None):
            result = session.apply_rules_action_result(action)
        self.assertEqual(
            (result["status"], result["cardIds"]),
            ("destroyed", ["m-a", "m-b", "m-c"]),
        )
        self.assertEqual(p1["zones"]["graveyard"], ["m-c", "m-a"])
        self.assertEqual(p2["zones"]["graveyard"], ["m-b"])
        self.assertEqual(
            p2["zones"]["receptacle"],
            [WORM_BOMB, "m-d", "vessel-will"],
        )

    def test_worm_bomb_destroys_all_available_manifestations_up_to_three(self):
        for count in (0, 1, 2):
            with self.subTest(count=count):
                session, _p1, p2 = self.started()
                others = [f"other-{index}" for index in range(count)]
                for card_id in others:
                    self.manifestation(session, card_id)
                session.card_rules["vessel-will"] = {
                    "type": "ephemeral_will",
                    "cost": 1,
                    "powerCost": "{G}",
                    "temperaments": ["phlegmatic"],
                }
                self.put(p2, "receptacle", {
                    WORM_BOMB: "p1",
                    **{card_id: "p2" for card_id in others},
                    "vessel-will": "p2",
                })
                action = self.opponent_vessel_action(session, WORM_BOMB)
                result = session.apply_rules_action_result(action)
                self.assertCountEqual(result["cardIds"], others)
                self.assertIn(WORM_BOMB, p2["zones"]["receptacle"])
                self.assertIn("vessel-will", p2["zones"]["receptacle"])

    def test_unreachable_pillar_suppresses_both_vessel_entry_effects(self):
        for card_id in (NIMBUS, WORM_BOMB):
            with self.subTest(card_id=card_id):
                session, _p1, _p2 = self.started()
                session.card_rules[PILLAR] = {
                    "type": "persistent_will",
                    "passiveEffects": [
                        self.ABILITIES[PILLAR][0]["passiveEffect"],
                    ],
                }
                pillar = self.field_item(
                    "pillar", "p2", PILLAR, field_zone="field",
                )
                session.battlefield = [pillar]
                self.assertTrue(session.rules_vessel_locked("p2"))
                self.assertEqual(
                    session.queue_rules_zone_entry_triggers(
                        card_id, "p1", "p2", "receptacle", defer=True,
                    ),
                    [],
                )
                pillar["effectsDisabled"] = True
                self.assertEqual(
                    len(session.queue_rules_zone_entry_triggers(
                        card_id, "p1", "p2", "receptacle", defer=True,
                    )),
                    1,
                )

