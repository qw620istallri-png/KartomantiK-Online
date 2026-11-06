"""Strict contracts for Vexing Thorn and Embottle's lose-effects clauses."""

import copy

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


LOSE_EFFECTS_NAMES = (
    "Vexing Thorn",
    "Embottle",
)

THORN = "3bq6ahxkf9435k5_en"
EMBOTTLE = "inner-deserts-091"
NECTAR = "7gd19pmexrjlrap_en"

THORN_ABILITY = {
    "id": "vexing-thorn-disable-target",
    "sourceFieldZone": "interzone",
    "reduceSourcePower": 2,
    "targets": {
        "min": 1,
        "max": 1,
        "cardType": "manifestation",
        "zones": ["battlefield"],
    },
    "ongoingEffect": {
        "kind": "lose_effects",
        "duration": "while_target_on_field",
    },
}

EMBOTTLE_ABILITY = {
    "id": "embottle-disable-card",
    "action": "play_card",
    "targets": {
        "min": 1,
        "max": 1,
        "cardTypes": ["manifestation", "persistent_will"],
        "zones": ["battlefield"],
    },
    "ongoingEffect": {
        "kind": "lose_effects",
        "duration": "while_target_on_field",
    },
}


class LoseEffectsFamily(RealCardRulesCase):
    ALL = (THORN, EMBOTTLE, NECTAR)

    def started(self, phase="end_actions"):
        session, p1, p2 = self.make_session()
        session.phase_tracker["index"] = ADVANCED_PHASES.index(phase)
        session.rules_engine.update(
            readyPlayerIds=["p1", "p2"],
            firstManifestationComplete=True,
            firstManifestationTriggersQueued=True,
            priorityPlayerId="p1",
            actionStack=[],
            pendingChoice=None,
        )
        return session, p1, p2

    @staticmethod
    def card_target(item):
        return {
            "kind": "card",
            "itemId": item["id"],
            "cardId": item["cardId"],
        }

    @staticmethod
    def snapshot(session):
        return copy.deepcopy((
            session.players,
            session.battlefield,
            session.rules_engine,
        ))

    def resolve_top(self, session):
        self.assertIsNone(session.pass_rules_priority("p2")[0])
        error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error, error)
        return resolution

    def declare_thorn(self, session, source, target):
        return session.declare_rules_action(
            "p1",
            "Vexing Thorn disables a Manifestation",
            kind="activated_effect",
            source={
                "cardId": THORN,
                "zone": "battlefield",
                "itemId": source["id"],
            },
            ability_id=THORN_ABILITY["id"],
            targets=[self.card_target(target)],
        )

    def play_embottle(self, session, p1, target):
        tributes = [f"m-{index}" for index in range(4)]
        for card_id in tributes:
            session.card_rules[card_id]["temperaments"] = ["capricious"]
        self.put(p1, "hand", [EMBOTTLE, *tributes])
        return session.declare_rules_action(
            "p1",
            "Embottle",
            kind="play_card",
            source={"cardId": EMBOTTLE, "zone": "hand"},
            payment_card_ids=tributes,
            ability_id=EMBOTTLE_ABILITY["id"],
            targets=[self.card_target(target)],
        )

    def test_both_compile_the_exact_printed_contract(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        self.assertEqual(self.ABILITIES[THORN], [THORN_ABILITY])
        self.assertEqual(self.ABILITIES[EMBOTTLE], [EMBOTTLE_ABILITY])
        self.assertEqual(rules[THORN]["activatedAbilities"], [THORN_ABILITY])
        self.assertEqual(rules[EMBOTTLE]["playedAbilities"], [EMBOTTLE_ABILITY])
        self.assertEqual(rules[THORN]["power"], 5)
        self.assertEqual(rules[EMBOTTLE]["powerCost"], "{Y}{Y}{Y}{Y}")

    def test_invalid_sources_and_targets_are_rejected_without_payment(self):
        session, p1, _p2 = self.started("confrontation_reaction")
        source = self.field_item("thorn", "p1", THORN)
        target = self.field_item("target", "p2", THORN)
        session.battlefield = [source, target]
        before = self.snapshot(session)
        error, action = self.declare_thorn(session, source, target)
        self.assertIn("different field zone", error)
        self.assertIsNone(action)
        self.assertEqual(self.snapshot(session), before)

        for invalid in (
            self.field_item("will", "p2", NECTAR, field_zone="field"),
            self.field_item("stalemate", "p2", THORN, field_zone="stalemate"),
        ):
            with self.subTest(thorn_target=invalid["id"]):
                session, _p1, _p2 = self.started("confrontation_reaction")
                source = self.field_item("thorn", "p1", THORN, "interzone")
                session.battlefield = [source, invalid]
                before = self.snapshot(session)
                error, action = self.declare_thorn(session, source, invalid)
                self.assertIsNotNone(error)
                self.assertIsNone(action)
                self.assertEqual(self.snapshot(session), before)

        for invalid in (
            self.field_item("ephemeral", "p2", "will-x", field_zone="field"),
            self.field_item("stalemate", "p2", THORN, field_zone="stalemate"),
        ):
            with self.subTest(embottle_target=invalid["id"]):
                session, p1, _p2 = self.started()
                session.battlefield = [invalid]
                tributes = [f"m-{index}" for index in range(4)]
                for card_id in tributes:
                    session.card_rules[card_id]["temperaments"] = ["capricious"]
                self.put(p1, "hand", [EMBOTTLE, *tributes])
                before = self.snapshot(session)
                error, action = session.declare_rules_action(
                    "p1",
                    "Embottle",
                    kind="play_card",
                    source={"cardId": EMBOTTLE, "zone": "hand"},
                    payment_card_ids=tributes,
                    ability_id=EMBOTTLE_ABILITY["id"],
                    targets=[self.card_target(invalid)],
                )
                self.assertIsNotNone(error)
                self.assertIsNone(action)
                self.assertEqual(self.snapshot(session), before)

    def test_thorn_pays_two_power_then_disables_the_live_target(self):
        session, _p1, _p2 = self.started("confrontation_reaction")
        source = self.field_item("thorn-source", "p1", THORN, "interzone")
        target = self.field_item("thorn-target", "p2", THORN, "interzone")
        session.battlefield = [source, target]

        error, action = self.declare_thorn(session, source, target)
        self.assertIsNone(error, error)
        self.assertEqual(action["cost"]["reducedSourcePower"], 2)
        self.assertEqual(self.power_of(session, source["id"]), 3)
        resolution = self.resolve_top(session)
        self.assertEqual(resolution["status"], "resolved")
        self.assertFalse(session.rules_item_effects_active(target))
        effect = next(
            entry for entry in session.rules_engine["ongoingEffects"]
            if entry.get("target", {}).get("itemId") == target["id"]
        )
        self.assertEqual(
            (effect["kind"], effect["duration"]),
            ("lose_effects", "while_target_on_field"),
        )

        session.rules_engine["priorityPlayerId"] = "p2"
        error, action = session.declare_rules_action(
            "p2",
            "Blanked Thorn cannot activate",
            kind="activated_effect",
            source={"cardId": THORN, "zone": "battlefield", "itemId": target["id"]},
            ability_id=THORN_ABILITY["id"],
            targets=[self.card_target(source)],
        )
        self.assertIn("lost its effects", error)
        self.assertIsNone(action)

    def test_thorn_cost_remains_paid_when_the_target_leaves_in_response(self):
        session, _p1, p2 = self.started("confrontation_reaction")
        source = self.field_item("thorn-source", "p1", THORN, "interzone")
        target = self.field_item("target", "p2", THORN, "confrontation")
        session.battlefield = [source, target]
        error, action = self.declare_thorn(session, source, target)
        self.assertIsNone(error, error)
        self.assertEqual(action["cost"]["reducedSourcePower"], 2)

        session._rules_remove_field_item(target, "p2", "graveyard", "top")
        resolution = self.resolve_top(session)
        self.assertEqual(resolution["status"], "resolved")
        self.assertEqual(self.power_of(session, source["id"]), 3)
        self.assertEqual(p2["zones"]["graveyard"], [THORN])
        self.assertFalse(any(
            entry.get("target", {}).get("itemId") == target["id"]
            for entry in session.rules_engine["ongoingEffects"]
        ))

    def test_embottle_pays_four_and_disables_each_printed_card_type(self):
        cases = (
            ("manifestation", THORN, "interzone"),
            ("persistent_will", NECTAR, "field"),
        )
        for card_type, card_id, field_zone in cases:
            with self.subTest(card_type=card_type):
                session, p1, _p2 = self.started()
                target = self.field_item("target", "p2", card_id, field_zone)
                session.battlefield = [target]
                error, action = self.play_embottle(session, p1, target)
                self.assertIsNone(error, error)
                self.assertEqual(len(action["cost"]["tributeMovements"]), 4)
                resolution = self.resolve_top(session)
                self.assertEqual(resolution["status"], "resolved")
                self.assertIn(EMBOTTLE, p1["zones"]["graveyard"])
                self.assertEqual(
                    sorted(card for card in p1["zones"]["graveyard"] if card.startswith("m-")),
                    ["m-0", "m-1", "m-2", "m-3"],
                )
                self.assertFalse(session.rules_item_effects_active(target))
                effect = next(
                    entry for entry in session.rules_engine["ongoingEffects"]
                    if entry.get("target", {}).get("itemId") == target["id"]
                )
                self.assertIsNone(effect["source"].get("itemId"))
                self.assertEqual(effect["kind"], "lose_effects")

    def test_resolved_silence_survives_its_source_but_not_target_reentry(self):
        session, p1, _p2 = self.started()
        target = self.field_item("old-target", "p2", THORN, "interzone")
        session.battlefield = [target]
        error, _action = self.play_embottle(session, p1, target)
        self.assertIsNone(error, error)
        self.resolve_top(session)
        self.assertFalse(session.rules_item_effects_active(target))

        session._rules_remove_field_item(target, "p2", "graveyard", "top")
        session.prune_rules_ongoing_effects()
        self.assertFalse(any(
            entry.get("target", {}).get("itemId") == "old-target"
            for entry in session.rules_engine["ongoingEffects"]
        ))
        returned = self.field_item("new-target", "p2", THORN, "interzone")
        session.battlefield.append(returned)
        self.assertTrue(session.rules_item_effects_active(returned))
        self.assertEqual(self.power_of(session, returned["id"]), 5)


if __name__ == "__main__":
    import unittest

    unittest.main()
