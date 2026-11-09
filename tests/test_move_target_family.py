"""Strict contracts for Destroy and Eliminate the Profane."""

import copy

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


MOVE_TARGET_NAMES = (
    "Destroy",
    "Eliminate the Profane",
)

DESTROY = "f2cj2wys3jhbzci_en"
ELIMINATE = "5x4aca4v6w9ma1f_en"

DESTROY_ABILITY = {
    "id": "destroy-field-will-or-interzone-manifestation",
    "action": "play_card",
    "targets": {
        "min": 1,
        "max": 1,
        "cardTypes": [
            "manifestation",
            "ephemeral_will",
            "persistent_will",
        ],
        "zones": ["battlefield"],
        "fieldZonesByType": {
            "manifestation": ["interzone"],
            "ephemeral_will": ["field"],
            "persistent_will": ["field"],
        },
    },
    "result": {
        "kind": "move_target",
        "zone": "graveyard",
        "position": "top",
        "reason": "destroy",
    },
}

ELIMINATE_ABILITY = {
    "id": "destroy-vessel-manifestation",
    "action": "play_card",
    "targets": {
        "min": 1,
        "max": 1,
        "cardType": "manifestation",
        "zones": ["receptacle"],
    },
    "result": {
        "kind": "move_target",
        "zone": "graveyard",
        "position": "top",
        "reason": "destroy",
    },
}


class MoveTargetFamily(RealCardRulesCase):
    ALL = (DESTROY, ELIMINATE)

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
        session.card_rules.update({
            "persistent-target": {
                "type": "persistent_will",
                "cost": 1,
                "temperaments": ["phlegmatic"],
            },
            "ephemeral-target": {
                "type": "ephemeral_will",
                "cost": 1,
                "temperaments": ["phlegmatic"],
            },
        })
        return session, p1, p2

    @staticmethod
    def snapshot(session):
        return copy.deepcopy((
            session.players,
            session.battlefield,
            session.rules_engine,
        ))

    def fund(self, session, player, source_id, amount):
        payers = [f"m-{index}" for index in range(amount)]
        for card_id in payers:
            session.card_rules[card_id]["temperaments"] = ["hollow"]
        self.put(player, "hand", [source_id, *payers])
        return payers

    def resolve_top(self, session):
        self.assertIsNone(session.pass_rules_priority("p2")[0])
        error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error, error)
        return resolution

    @staticmethod
    def field_target(item):
        return {
            "kind": "card",
            "itemId": item["id"],
            "cardId": item["cardId"],
            "ownerId": item["ownerId"],
        }

    @staticmethod
    def vessel_target(container_id, card_id, owner_id):
        return {
            "kind": "zone_card",
            "containerId": container_id,
            "zone": "receptacle",
            "cardId": card_id,
            "ownerId": owner_id,
        }

    def declare(self, session, player, card_id, target, payers):
        ability_id = (
            DESTROY_ABILITY["id"]
            if card_id == DESTROY
            else ELIMINATE_ABILITY["id"]
        )
        return session.declare_rules_action(
            player,
            "Destroy target",
            kind="play_card",
            source={"cardId": card_id, "zone": "hand"},
            targets=[target] if target is not None else [],
            payment_card_ids=payers,
            ability_id=ability_id,
        )

    def test_both_compile_the_exact_printed_contract(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        self.assertEqual(self.ABILITIES[DESTROY], [DESTROY_ABILITY])
        self.assertEqual(self.ABILITIES[ELIMINATE], [ELIMINATE_ABILITY])
        self.assertEqual(rules[DESTROY]["playedAbilities"], [DESTROY_ABILITY])
        self.assertEqual(
            rules[ELIMINATE]["playedAbilities"], [ELIMINATE_ABILITY],
        )

    def test_destroy_rejects_every_other_type_zone_and_cardinality_atomically(self):
        invalid_cases = (
            ("manifestation in confrontation", "card", "m-10", "confrontation"),
            ("manifestation in stalemate", "card", "m-10", "stalemate"),
            ("persistent Will in interzone", "card", "persistent-target", "interzone"),
            ("persistent Will in stalemate", "card", "persistent-target", "stalemate"),
            ("manifestation in vessel", "zone_card", "m-10", "receptacle"),
        )
        for label, kind, target_id, zone in invalid_cases:
            with self.subTest(label=label):
                session, p1, p2 = self.started()
                payers = self.fund(session, p1, DESTROY, 3)
                if kind == "card":
                    item = self.field_item(
                        "invalid", "p2", target_id, field_zone=zone,
                    )
                    session.battlefield = [item]
                    target = self.field_target(item)
                else:
                    self.put(p2, zone, {target_id: "p1"})
                    target = self.vessel_target("p2", target_id, "p1")
                before = self.snapshot(session)
                error, action = self.declare(
                    session, "p1", DESTROY, target, payers,
                )
                self.assertIsNotNone(error)
                self.assertIsNone(action)
                self.assertEqual(self.snapshot(session), before)

        session, p1, _p2 = self.started()
        payers = self.fund(session, p1, DESTROY, 3)
        before = self.snapshot(session)
        error, action = self.declare(
            session, "p1", DESTROY, None, payers,
        )
        self.assertIsNotNone(error)
        self.assertIsNone(action)
        self.assertEqual(self.snapshot(session), before)

    def test_eliminate_rejects_non_manifestations_and_non_vessel_zones_atomically(self):
        for label, target_kind, target_id, zone in (
            ("persistent Will in vessel", "zone_card", "persistent-target", "receptacle"),
            ("manifestation in interzone", "card", "m-10", "interzone"),
            ("manifestation on field", "card", "m-10", "confrontation"),
            ("manifestation in hand", "zone_card", "m-10", "hand"),
        ):
            with self.subTest(label=label):
                session, p1, p2 = self.started()
                payers = self.fund(session, p1, ELIMINATE, 4)
                if target_kind == "card":
                    item = self.field_item(
                        "invalid", "p2", target_id, field_zone=zone,
                    )
                    session.battlefield = [item]
                    target = self.field_target(item)
                else:
                    self.put(p2, zone, {target_id: "p1"})
                    target = {
                        "kind": "zone_card",
                        "containerId": "p2",
                        "zone": zone,
                        "cardId": target_id,
                        "ownerId": "p1",
                    }
                before = self.snapshot(session)
                error, action = self.declare(
                    session, "p1", ELIMINATE, target, payers,
                )
                self.assertIsNotNone(error)
                self.assertIsNone(action)
                self.assertEqual(self.snapshot(session), before)

    def test_destroy_really_destroys_each_printed_target_category(self):
        cases = (
            ("persistent Will", "persistent-target", "field", "p2"),
            ("ephemeral Will", "ephemeral-target", "field", "p2"),
            ("own Interzone manifestation", "m-10", "interzone", "p1"),
            ("opposing Interzone manifestation", "m-10", "interzone", "p2"),
        )
        for label, target_id, zone, owner_id in cases:
            with self.subTest(label=label):
                session, p1, _p2 = self.started()
                payers = self.fund(session, p1, DESTROY, 3)
                target = self.field_item(
                    "victim", owner_id, target_id, field_zone=zone,
                    controllerId=owner_id,
                )
                session.battlefield = [target]
                error, action = self.declare(
                    session, "p1", DESTROY,
                    self.field_target(target), payers,
                )
                self.assertIsNone(error, error)
                self.assertIsNotNone(action)
                resolution = self.resolve_top(session)
                effect = resolution["action"]["effectResult"]
                self.assertEqual(
                    (effect["status"], effect["reason"], effect["toZone"]),
                    ("moved", "destroy", "graveyard"),
                )
                self.assertIsNone(session.find_battlefield_item("victim"))
                self.assertIn(
                    target_id, session.players[owner_id]["zones"]["graveyard"],
                )
                self.assertIn(DESTROY, p1["zones"]["graveyard"])

    def test_eliminate_reaches_any_players_vessel_and_routes_to_the_owner(self):
        for container_id, owner_id in (("p1", "p2"), ("p2", "p1")):
            with self.subTest(container_id=container_id, owner_id=owner_id):
                session, p1, _p2 = self.started()
                payers = self.fund(session, p1, ELIMINATE, 4)
                target_id = "m-10"
                self.put(
                    session.players[container_id], "receptacle",
                    {target_id: owner_id},
                )
                error, action = self.declare(
                    session, "p1", ELIMINATE,
                    self.vessel_target(container_id, target_id, owner_id),
                    payers,
                )
                self.assertIsNone(error, error)
                self.assertIsNotNone(action)
                resolution = self.resolve_top(session)
                effect = resolution["action"]["effectResult"]
                self.assertEqual(
                    (effect["status"], effect["reason"], effect["fromZone"]),
                    ("moved", "destroy", "receptacle"),
                )
                self.assertNotIn(
                    target_id,
                    session.players[container_id]["zones"]["receptacle"],
                )
                self.assertIn(
                    target_id, session.players[owner_id]["zones"]["graveyard"],
                )
                self.assertIn(ELIMINATE, p1["zones"]["graveyard"])

    def test_destroy_cost_stays_paid_when_field_target_leaves_in_response(self):
        session, p1, p2 = self.started()
        payers = self.fund(session, p1, DESTROY, 3)
        target = self.field_item(
            "escaping-will", "p2", "persistent-target", field_zone="field",
        )
        session.battlefield = [target]
        error, action = self.declare(
            session, "p1", DESTROY, self.field_target(target), payers,
        )
        self.assertIsNone(error, error)
        self.assertIsNotNone(action)
        moved = session._rules_remove_field_item(
            target, "p2", "hand", "top",
        )
        self.assertEqual(moved["status"], "moved")

        resolution = self.resolve_top(session)
        self.assertEqual(
            resolution["action"]["effectResult"]["status"],
            "no_effect",
        )
        self.assertIn("persistent-target", p2["zones"]["hand"])
        self.assertIn(DESTROY, p1["zones"]["graveyard"])
        for payer in payers:
            self.assertIn(payer, p1["zones"]["graveyard"])

    def test_eliminate_cost_stays_paid_when_vessel_target_leaves_in_response(self):
        session, p1, p2 = self.started()
        payers = self.fund(session, p1, ELIMINATE, 4)
        self.put(p2, "receptacle", {"m-10": "p1"})
        error, action = self.declare(
            session, "p1", ELIMINATE,
            self.vessel_target("p2", "m-10", "p1"), payers,
        )
        self.assertIsNone(error, error)
        self.assertIsNotNone(action)
        move_error, _owner, _replacement = session.move_zone_card_by_effect(
            "p2", "receptacle", "p1", "hand", "m-10", "top",
        )
        self.assertIsNone(move_error, move_error)

        resolution = self.resolve_top(session)
        self.assertEqual(
            resolution["action"]["effectResult"]["status"],
            "no_effect",
        )
        self.assertIn("m-10", p1["zones"]["hand"])
        self.assertIn(ELIMINATE, p1["zones"]["graveyard"])
        for payer in payers:
            self.assertIn(payer, p1["zones"]["graveyard"])


if __name__ == "__main__":
    import unittest

    unittest.main()
