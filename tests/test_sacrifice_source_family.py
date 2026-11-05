"""Strict contracts for the three remaining sacrifice-source cards."""

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


SACRIFICE_SOURCE_NAMES = (
    "Gusted Nebula",
    "Cirrocumulus",
    "Rah-kio, the Flyswatter",
)

CARD_IDS = {
    "Gusted Nebula": "inner-deserts-010",
    "Cirrocumulus": "inner-deserts-080",
    "Rah-kio, the Flyswatter": "inner-deserts-109",
}

EXPECTED_ABILITIES = {
    "Gusted Nebula": {
        "id": "sacrifice-to-return-supports",
        "sourceFieldZone": "interzone",
        "sacrificeSource": True,
        "targets": {"min": 0, "max": 0},
        "result": {"kind": "return_supports_and_boost_firsts"},
    },
    "Cirrocumulus": {
        "id": "sacrifice-to-resolve-controlled-stack-item",
        "sourceFieldZone": "interzone",
        "sacrificeSource": True,
        "targets": {
            "kind": "stack_item", "min": 1, "max": 1,
            "controller": "self",
        },
        "result": {"kind": "resolve_target_stack_immediately"},
    },
    "Rah-kio, the Flyswatter": {
        "id": "rah-kio-swat-tokens",
        "exhaustSource": True,
        "sacrificeSource": True,
        "targets": {"min": 0, "max": 0},
        "result": {"kind": "destroy_all_tokens"},
    },
}


class SacrificeSourceFamily(RealCardRulesCase):
    ALL = tuple(CARD_IDS.values())

    def started(self):
        session, p1, p2 = self.make_session()
        session.rules_engine.update(
            readyPlayerIds=["p1", "p2"],
            firstManifestationComplete=True,
            priorityPlayerId="p1",
            actionStack=[],
            pendingChoice=None,
        )
        session.phase_tracker["index"] = ADVANCED_PHASES.index(
            "confrontation_reaction"
        )
        return session, p1, p2

    def activate(self, session, card_id, item_id, targets=None):
        return session.declare_rules_action(
            "p1", f"Activate {card_id}", kind="activated_effect",
            source={
                "cardId": card_id, "zone": "battlefield",
                "itemId": item_id,
            },
            targets=targets or [],
            ability_id=EXPECTED_ABILITIES[
                next(name for name, value in CARD_IDS.items() if value == card_id)
            ]["id"],
        )

    def resolve_top(self, session):
        self.assertIsNone(session.pass_rules_priority("p2")[0])
        error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error, error)
        return resolution

    def test_all_three_compile_the_exact_sacrifice_contract(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        for name in SACRIFICE_SOURCE_NAMES:
            with self.subTest(card=name):
                card_id = CARD_IDS[name]
                expected = EXPECTED_ABILITIES[name]
                self.assertEqual(self.ABILITIES[card_id], [expected])
                self.assertEqual(rules[card_id]["activatedAbilities"], [expected])
        for name in ("Gusted Nebula", "Cirrocumulus"):
            metadata = rules[CARD_IDS[name]]
            self.assertTrue(metadata["supportFromHand"])
            self.assertTrue(metadata["float"])

    def test_nebulas_enter_support_from_hand_and_really_have_float(self):
        for name in ("Gusted Nebula", "Cirrocumulus"):
            with self.subTest(card=name):
                card_id = CARD_IDS[name]
                session, p1, _p2 = self.started()
                self.put(p1, "hand", [card_id])
                error, action = session.declare_rules_action(
                    "p1", f"Support {name}", kind="play_card",
                    source={"cardId": card_id, "zone": "hand"},
                    as_support=True, placement={"x": 100, "y": 200},
                )
                self.assertIsNone(error, error)
                self.assertTrue(action["asSupport"])
                self.assertEqual(action["cost"]["tributeRequirements"], {})
                self.assertEqual(action["cost"]["essenceSpent"], [])
                self.resolve_top(session)
                item = next(
                    entry for entry in session.battlefield
                    if entry.get("cardId") == card_id
                )
                self.assertTrue(item["isSupport"])
                self.assertTrue(session.rules_item_has_float(item))

                item["isSupport"] = False
                item["fieldZone"] = "interzone"
                anchor = self.field_item(
                    "anchor", "p1", "m-1", field_zone="interzone"
                )
                session.battlefield = [anchor, item]
                self.assertEqual(
                    session.rules_interzone_share_anchor("p1", item),
                    "anchor",
                )

    def test_gusted_nebula_sacrifices_from_interzone_then_returns_supports(self):
        gusted = CARD_IDS["Gusted Nebula"]
        session, p1, p2 = self.started()
        source = self.field_item("gusted", "p1", gusted)
        first1 = self.field_item("first1", "p1", "m-1")
        first2 = self.field_item("first2", "p2", "m-2")
        support1 = self.field_item("support1", "p1", "m-3", isSupport=True)
        support2 = self.field_item("support2", "p2", "m-4", isSupport=True)
        session.battlefield = [source, first1, first2, support1, support2]
        session.rules_engine["firstManifestationItemIds"] = {
            "p1": "first1", "p2": "first2",
        }
        before = list(session.battlefield)
        error, action = self.activate(session, gusted, "gusted")
        self.assertIn("field zone", error)
        self.assertIsNone(action)
        self.assertEqual(session.battlefield, before)
        source["fieldZone"] = "interzone"
        error, action = self.activate(session, gusted, "gusted")
        self.assertIsNone(error, error)
        self.assertTrue(action["cost"]["sourceSacrificed"])
        self.assertEqual(
            action["cost"]["sacrificedCards"][0]["cardId"], gusted,
        )
        self.assertIsNone(session.find_battlefield_item("gusted"))
        self.assertIn(gusted, p1["zones"]["graveyard"])
        resolution = self.resolve_top(session)
        result = resolution["action"]["effectResult"]
        self.assertEqual(result["status"], "resolved")
        self.assertIn("m-3", p1["zones"]["deck"])
        self.assertIn("m-4", p2["zones"]["deck"])
        self.assertEqual(session.rules_manifestation_characteristics(first1)["power"], 2)
        self.assertEqual(session.rules_manifestation_characteristics(first2)["power"], 2)

    def test_cirrocumulus_rejects_a_foreign_stack_item_then_resolves_its_own(self):
        cirro = CARD_IDS["Cirrocumulus"]
        session, p1, _p2 = self.started()
        source = self.field_item(
            "cirro", "p1", cirro, field_zone="interzone"
        )
        target_action = {
            "id": "target-action", "controllerId": "p2",
            "kind": "triggered_effect",
            "source": {"cardId": "m-1", "ownerId": "p2"},
            "targets": [],
            "ability": {
                "id": "score", "result": {"kind": "score_owner", "value": 5},
            },
            "cost": {},
        }
        session.battlefield = [source]
        session.rules_engine["actionStack"] = [target_action]
        target = [{
            "kind": "stack_item", "actionId": "target-action",
            "cardId": "m-1",
        }]
        error, action = self.activate(session, cirro, "cirro", target)
        self.assertIn("control", error.lower())
        self.assertIsNone(action)
        self.assertIsNotNone(session.find_battlefield_item("cirro"))
        self.assertEqual(p1["zones"]["graveyard"], [])

        target_action["controllerId"] = "p1"
        error, action = self.activate(session, cirro, "cirro", target)
        self.assertIsNone(error, error)
        self.assertTrue(action["cost"]["sourceSacrificed"])
        self.assertIsNone(session.find_battlefield_item("cirro"))
        self.assertIn(cirro, p1["zones"]["graveyard"])
        resolution = self.resolve_top(session)
        result = resolution["action"]["effectResult"]
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["targetActionId"], "target-action")
        self.assertEqual(p1["score"], 5)
        self.assertEqual(session.rules_engine["actionStack"], [])

    def test_rah_kio_pays_both_costs_then_destroys_only_field_tokens(self):
        rah = CARD_IDS["Rah-kio, the Flyswatter"]
        session, p1, _p2 = self.started()
        source = self.field_item("rah", "p1", rah, rotation=90)
        physical = self.field_item("physical", "p2", "m-1")
        generic = self.field_item(
            "generic", "p1", "m-2", isTokenCard=True
        )
        copied = self.field_item(
            "copy", "p2", "m-3", isTokenCard=True, isCopy=True
        )
        session.card_rules["token-will"] = {"type": "persistent_will"}
        will_token = self.field_item(
            "will-token", "p2", "token-will", isTokenCard=True
        )
        stalemate = self.field_item(
            "stalemate-token", "p2", "m-4",
            field_zone="stalemate", isTokenCard=True,
        )
        session.battlefield = [
            source, physical, generic, copied, will_token, stalemate,
        ]
        before_ids = [item["id"] for item in session.battlefield]
        error, action = self.activate(session, rah, "rah")
        self.assertIn("exhausted", error.lower())
        self.assertIsNone(action)
        self.assertEqual([item["id"] for item in session.battlefield], before_ids)
        self.assertEqual(p1["zones"]["graveyard"], [])

        source["rotation"] = 0
        error, action = self.activate(session, rah, "rah")
        self.assertIsNone(error, error)
        self.assertTrue(action["cost"]["sourceExhausted"])
        self.assertTrue(action["cost"]["sourceSacrificed"])
        self.assertIsNone(session.find_battlefield_item("rah"))
        self.assertIn(rah, p1["zones"]["graveyard"])
        resolution = self.resolve_top(session)
        result = resolution["action"]["effectResult"]
        self.assertEqual(result["status"], "destroyed")
        self.assertEqual(
            set(result["itemIds"]), {"generic", "copy", "will-token"},
        )
        self.assertIsNotNone(session.find_battlefield_item("physical"))
        self.assertIsNotNone(session.find_battlefield_item("stalemate-token"))


if __name__ == "__main__":
    import unittest

    unittest.main()
