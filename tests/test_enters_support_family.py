"""Strict enters-Support contracts for Gomeran and Unruly Flail."""

import copy

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


ENTERS_SUPPORT_NAMES = (
    "Gomeran, Echo Mistress",
    "Unruly Flail",
)

GOMERAN = "xfgbjv2gjb09fj9_en"
FLAIL = "tdy2112mspb7u97_en"

GOMERAN_ABILITY = {
    "id": "gomeran-copies-support-entry",
    "trigger": {
        "event": "enters_support",
        "zone": "confrontation",
        "eventController": "owner",
        "eventNonToken": True,
    },
    "result": {"kind": "create_event_token_copy_in_support"},
}

FLAIL_ABILITY = {
    "id": "unruly-flail-neutralize-will",
    "trigger": {
        "event": "enters_support",
        "enteredFromZone": "hand",
        "eventSourceOnly": True,
    },
    "targets": {
        "kind": "stack_action",
        "min": 1,
        "max": 1,
        "cardTypes": ["ephemeral_will", "persistent_will"],
        "controller": "opponent",
        "targetsConfrontationManifestation": True,
    },
    "result": {"kind": "neutralize_stack_action"},
}


class EntersSupportFamily(RealCardRulesCase):
    ALL = (GOMERAN, FLAIL)

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
        session.card_rules["attack-will"] = {
            "type": "ephemeral_will",
            "cost": 1,
            "powerCost": "{Y}",
            "temperaments": ["capricious"],
        }
        session.card_rules["plain-manifestation"] = {
            "type": "manifestation",
            "power": 2,
            "temperaments": ["phlegmatic"],
        }
        return session, p1, p2

    @staticmethod
    def stack_will(action_id="will-action", controller="p2", target="victim"):
        return {
            "id": action_id,
            "kind": "play_card",
            "controllerId": controller,
            "sourceOnStack": True,
            "source": {
                "cardId": "attack-will",
                "zone": "hand",
                "ownerId": controller,
            },
            "targets": [{
                "kind": "card",
                "itemId": target,
                "cardId": "plain-manifestation",
                "ownerId": "p1",
            }],
        }

    def eligible_stack(self, session):
        session.battlefield = [
            self.field_item(
                "victim", "p1", "plain-manifestation",
                field_zone="confrontation",
            ),
        ]
        action = self.stack_will()
        session.rules_engine["actionStack"] = [action]
        return action

    def test_both_compile_the_exact_selected_support_contract(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        self.assertEqual(self.ABILITIES[GOMERAN], [GOMERAN_ABILITY])
        self.assertEqual(self.ABILITIES[FLAIL], [FLAIL_ABILITY])
        self.assertEqual(
            rules[GOMERAN]["triggeredAbilities"], [GOMERAN_ABILITY],
        )
        self.assertEqual(
            rules[FLAIL]["triggeredAbilities"], [FLAIL_ABILITY],
        )
        self.assertEqual(rules[FLAIL]["powerCost"], "{Y}{Y}")
        self.assertEqual(rules[FLAIL]["supportFromHandCondition"], {
            "kind": "opponent_will_on_stack_targets_confrontation",
        })

    def test_gomeran_really_copies_an_allied_non_token_support_entry(self):
        session, p1, _p2 = self.started()
        session.card_rules["support-entry"] = {
            "type": "manifestation",
            "power": 4,
            "temperaments": ["capricious"],
            "supportFromHand": True,
        }
        gomeran = self.field_item("gomeran", "p1", GOMERAN)
        session.battlefield = [gomeran]
        self.put(p1, "hand", ["support-entry"])

        error, action = session.declare_rules_action(
            "p1",
            "Support entry",
            kind="play_card",
            source={"cardId": "support-entry", "zone": "hand"},
            as_support=True,
        )
        self.assertIsNone(error, error)
        self.assertIsNotNone(action)
        resolution = session.resolve_rules_top_action()
        entered = session.find_battlefield_item(
            resolution["action"]["sourceResolution"]["itemId"]
        )
        self.assertEqual(
            (entered["cardId"], entered["isSupport"], entered["controllerId"]),
            ("support-entry", True, "p1"),
        )
        self.assertEqual(p1["zones"]["graveyard"], [])
        self.assertEqual(
            [entry["ability"]["id"] for entry in resolution["triggeredActions"]],
            [GOMERAN_ABILITY["id"]],
        )

        copied = session.resolve_rules_top_action()
        effect = copied["action"]["effectResult"]
        self.assertEqual(effect["status"], "created")
        token = session.find_battlefield_item(effect["itemId"])
        self.assertEqual(
            (token["cardId"], token["controllerId"], token["isSupport"]),
            ("support-entry", "p1", True),
        )
        self.assertTrue(token["isCopy"] and token["isTokenCopy"])

    def test_gomeran_requires_its_controller_and_a_non_token_entry(self):
        session, _p1, _p2 = self.started()
        gomeran = self.field_item("gomeran", "p1", GOMERAN)
        own = self.field_item(
            "own", "p1", "plain-manifestation", isSupport=True,
        )
        opponent = self.field_item(
            "opponent", "p2", "plain-manifestation", isSupport=True,
        )
        token = self.field_item(
            "token", "p1", "plain-manifestation", isSupport=True,
            isTokenCopy=True, isCopy=True,
        )
        session.battlefield = [gomeran, own, opponent, token]

        self.assertEqual(
            [entry["ability"]["id"] for entry in
             session.queue_rules_support_entry_triggers(own, defer=True)],
            [GOMERAN_ABILITY["id"]],
        )
        self.assertEqual(
            session.queue_rules_support_entry_triggers(opponent, defer=True),
            [],
        )
        self.assertEqual(
            session.queue_rules_support_entry_triggers(token, defer=True),
            [],
        )

    def test_gomeran_requires_an_active_source_in_the_confrontation_zone(self):
        for change, expected in (
            ("normal", True),
            ("support", True),
            ("interzone", False),
            ("stalemate", False),
            ("hidden", False),
            ("disabled", False),
            ("gone", False),
        ):
            with self.subTest(change=change):
                session, _p1, _p2 = self.started()
                gomeran = self.field_item("gomeran", "p1", GOMERAN)
                entering = self.field_item(
                    "entering", "p1", "plain-manifestation",
                    isSupport=True,
                )
                session.battlefield = [gomeran, entering]
                if change == "support":
                    gomeran["isSupport"] = True
                elif change == "interzone":
                    gomeran["fieldZone"] = "interzone"
                elif change == "stalemate":
                    gomeran["fieldZone"] = "stalemate"
                elif change == "hidden":
                    gomeran["faceUp"] = False
                elif change == "disabled":
                    gomeran["effectsDisabled"] = True
                elif change == "gone":
                    session.battlefield.remove(gomeran)
                queued = session.queue_rules_support_entry_triggers(
                    entering, defer=True,
                )
                self.assertEqual(bool(queued), expected)

    def test_gomerans_created_token_does_not_copy_itself_again(self):
        session, _p1, _p2 = self.started()
        gomeran = self.field_item("gomeran", "p1", GOMERAN)
        entering = self.field_item(
            "entering", "p1", "plain-manifestation", isSupport=True,
        )
        session.battlefield = [gomeran, entering]
        action = session.queue_rules_support_entry_triggers(
            entering, defer=True,
        )[0]

        result = session.apply_rules_action_result(action)
        self.assertEqual(result["status"], "created")
        self.assertNotIn(
            GOMERAN_ABILITY["id"],
            [entry["ability"]["id"] for entry in result["triggeredActions"]],
        )

    def test_flail_support_is_available_for_exactly_an_eligible_opposing_will(self):
        session, _p1, _p2 = self.started()
        eligible = self.eligible_stack(session)
        self.assertTrue(session.rules_support_from_hand_available("p1", FLAIL))
        self.assertFalse(session.rules_support_from_hand_available("p2", FLAIL))

        cases = []
        own = copy.deepcopy(eligible)
        own["controllerId"] = "p1"
        cases.append(("own", [own]))
        wrong_type = copy.deepcopy(eligible)
        session.card_rules["plain-stack-source"] = {
            "type": "manifestation", "power": 1,
        }
        wrong_type["source"]["cardId"] = "plain-stack-source"
        cases.append(("manifestation", [wrong_type]))
        wrong_zone = copy.deepcopy(eligible)
        session.battlefield.append(self.field_item(
            "reserve", "p1", "plain-manifestation", field_zone="interzone",
        ))
        wrong_zone["targets"][0].update(
            itemId="reserve", cardId="plain-manifestation",
        )
        cases.append(("interzone", [wrong_zone]))
        no_target = copy.deepcopy(eligible)
        no_target["targets"] = [{"kind": "player", "playerId": "p1"}]
        cases.append(("player", [no_target]))

        for label, stack in cases:
            with self.subTest(label=label):
                session.rules_engine["actionStack"] = stack
                self.assertFalse(
                    session.rules_support_from_hand_available("p1", FLAIL)
                )

        session.rules_engine["actionStack"] = [
            eligible,
            {"id": "unrelated", "kind": "activated_effect", "controllerId": "p1"},
        ]
        self.assertTrue(session.rules_support_from_hand_available("p1", FLAIL))

    def test_flail_really_enters_support_without_tribute_and_neutralizes_the_chosen_will(self):
        session, p1, p2 = self.started()
        will = self.eligible_stack(session)
        self.put(p1, "hand", [FLAIL])

        error, action = session.declare_rules_action(
            "p1",
            "Unruly Flail",
            kind="play_card",
            source={"cardId": FLAIL, "zone": "hand"},
            targets=[{
                "kind": "stack_action",
                "actionId": will["id"],
                "cardId": "attack-will",
            }],
            as_support=True,
        )
        self.assertIsNone(error, error)
        self.assertIsNotNone(action)
        entered = session.resolve_rules_top_action()
        flail = next(
            item for item in session.battlefield if item.get("cardId") == FLAIL
        )
        self.assertTrue(flail["isSupport"])
        self.assertEqual(p1["zones"]["graveyard"], [])
        self.assertEqual(
            [entry["ability"]["id"] for entry in entered["triggeredActions"]],
            [FLAIL_ABILITY["id"]],
        )
        self.assertIsNone(session.rules_engine["pendingChoice"])
        neutralized = session.resolve_rules_top_action()["action"]["effectResult"]
        self.assertEqual(
            (neutralized["status"], neutralized["actionId"]),
            ("neutralized", will["id"]),
        )
        self.assertNotIn(will, session.rules_engine["actionStack"])
        self.assertIn("attack-will", p2["zones"]["graveyard"])

    def test_flail_triggers_only_for_its_own_entry_from_hand(self):
        session, _p1, _p2 = self.started()
        self.eligible_stack(session)
        flail = self.field_item("flail", "p1", FLAIL, isSupport=True)
        other = self.field_item(
            "other", "p1", "plain-manifestation", isSupport=True,
        )
        session.battlefield.extend([flail, other])

        self.assertEqual(
            session.queue_rules_support_entry_triggers(
                other, played=True, from_zone="hand", defer=True,
            ),
            [],
        )
        self.assertEqual(
            session.queue_rules_support_entry_triggers(
                flail, played=True, from_zone="interzone", defer=True,
            ),
            [],
        )
        queued = session.queue_rules_support_entry_triggers(
            flail, played=True, from_zone="hand", defer=True,
        )
        self.assertEqual(
            [entry["ability"]["id"] for entry in queued],
            [FLAIL_ABILITY["id"]],
        )

