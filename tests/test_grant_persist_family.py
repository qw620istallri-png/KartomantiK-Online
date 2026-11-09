"""Strict semantic coverage for Gigabonblade's three printed paragraphs."""

import copy

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


GIGABONBLADE = "inner-deserts-062"
ABILITY = {
    "id": "gigabonblade-gains-persist",
    "tribute": "",
    "sourceFieldZone": "confrontation",
    "reduceSourcePower": 2,
    "targets": {
        "min": 1,
        "max": 1,
        "cardType": "manifestation",
        "zones": ["battlefield"],
        "fieldZone": "confrontation",
        "controller": "self",
        "sourceOnly": True,
    },
    "ongoingEffect": {
        "kind": "grant_persist",
        "duration": "until_end_of_turn",
    },
}


class GrantPersistFamily(RealCardRulesCase):
    ALL = (GIGABONBLADE,)

    def started(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker.update(
            index=ADVANCED_PHASES.index("confrontation_reaction"), turn=4,
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

    def giga(self, **extra):
        return self.field_item(
            "giga", "p1", GIGABONBLADE,
            field_zone="confrontation", rotation=0.0, **extra,
        )

    @staticmethod
    def target(item):
        return {
            "kind": "card", "itemId": item["id"],
            "cardId": item["cardId"], "ownerId": item["ownerId"],
        }

    @staticmethod
    def snapshot(session):
        return copy.deepcopy((
            session.players, session.battlefield, session.rules_engine,
        ))

    def declare(self, session, item):
        return session.declare_rules_action(
            "p1", "Gigabonblade gains Persist",
            kind="activated_effect",
            source={
                "cardId": GIGABONBLADE,
                "zone": "battlefield",
                "itemId": item["id"],
            },
            ability_id=ABILITY["id"],
            targets=[self.target(item)],
        )

    def resolve_top(self, session):
        self.assertIsNone(session.pass_rules_priority("p2")[0])
        error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error, error)
        return resolution

    @staticmethod
    def set_result(session, winner, loser, winner_items, loser_items):
        participant_ids = [
            item["id"] for item in [*winner_items, *loser_items]
        ]
        session.rules_engine["confrontationResult"] = {
            "turn": session.phase_tracker["turn"],
            "status": "effects",
            "winnerId": winner,
            "loserId": loser,
            "stalemate": False,
            "participantItemIds": participant_ids,
            "winnerItemIds": [item["id"] for item in winner_items],
            "loserItemIds": [item["id"] for item in loser_items],
        }

    def test_compiles_the_exact_three_paragraph_contract(self):
        rules = self.real_rules()[GIGABONBLADE]
        self.assertEqual(self.ABILITIES[GIGABONBLADE], [ABILITY])
        self.assertEqual(rules["activatedAbilities"], [ABILITY])
        self.assertEqual(rules["power"], 6)
        self.assertFalse(rules["canPayTribute"])
        self.assertTrue(rules["exileIfLeavesConfrontationByEffect"])
        self.assertEqual(rules["exiledByEffectFieldPenalty"], 2)

    def test_cannot_be_used_as_tribute_from_hand(self):
        session, p1, _p2 = self.started()
        self.put(p1, "hand", ["will-x", GIGABONBLADE])
        error, action = session.declare_rules_action(
            "p1", "Play Will", kind="play_card",
            source={"cardId": "will-x", "zone": "hand"},
            payment_card_ids=[GIGABONBLADE],
        )
        self.assertIn("cannot be used to pay Tribute", error or "")
        self.assertIsNone(action)
        self.assertEqual(p1["zones"]["hand"], ["will-x", GIGABONBLADE])

    def test_activation_scope_and_insufficient_power_are_atomic(self):
        for mode in ("interzone", "other_target", "inactive", "power_one"):
            with self.subTest(mode=mode):
                session, _p1, _p2 = self.started()
                giga = self.giga()
                other = self.field_item("other", "p1", "m-1")
                session.battlefield = [giga, other]
                target = giga
                if mode == "interzone":
                    giga["fieldZone"] = "interzone"
                elif mode == "other_target":
                    target = other
                elif mode == "inactive":
                    giga["effectsDisabled"] = True
                else:
                    giga["counters"] = {"power": -5}
                before = self.snapshot(session)
                error, action = session.declare_rules_action(
                    "p1", "Gigabonblade gains Persist",
                    kind="activated_effect",
                    source={
                        "cardId": GIGABONBLADE,
                        "zone": "battlefield", "itemId": giga["id"],
                    },
                    ability_id=ABILITY["id"],
                    targets=[self.target(target)],
                )
                self.assertIsNotNone(error)
                self.assertIsNone(action)
                self.assertEqual(self.snapshot(session), before)

    def test_pays_two_power_and_grants_persist_only_until_turn_end(self):
        session, _p1, _p2 = self.started()
        giga = self.giga()
        session.battlefield = [giga]
        error, action = self.declare(session, giga)
        self.assertIsNone(error, error)
        self.assertEqual(action["cost"]["reducedSourcePower"], 2)
        self.assertEqual(self.power_of(session, "giga"), 4)
        resolution = self.resolve_top(session)
        self.assertEqual(resolution["status"], "resolved")
        self.assertTrue(session.rules_item_has_persist(giga))
        effect = next(
            entry for entry in session.rules_engine["ongoingEffects"]
            if entry.get("target", {}).get("itemId") == "giga"
        )
        self.assertEqual(
            (effect["kind"], effect["duration"], effect["startedTurn"]),
            ("grant_persist", "until_end_of_turn", 4),
        )
        session.phase_tracker["turn"] = 5
        session.prune_rules_ongoing_effects()
        self.assertFalse(session.rules_item_has_persist(giga))

    def test_winning_with_persist_keeps_gigabonblade_as_next_first(self):
        session, _p1, _p2 = self.started()
        giga = self.giga()
        loser = self.field_item("loser", "p2", "m-1")
        session.battlefield = [giga, loser]
        self.assertIsNone(self.declare(session, giga)[0])
        self.resolve_top(session)
        self.set_result(session, "p1", "p2", [giga], [loser])
        result = session.begin_rules_confrontation_cleanup()
        self.assertEqual(result["persisted"][0]["itemId"], "giga")
        self.assertIn(giga, session.battlefield)
        self.assertTrue(giga["persistedFirst"])
        self.assertEqual(giga["fieldZone"], "confrontation")
        session.reset_rules_confrontation_turn()
        self.assertEqual(
            session.rules_engine["firstManifestationItemIds"],
            {"p1": "giga"},
        )

    def test_natural_confrontation_loss_captures_without_exile_or_penalty(self):
        session, p1, p2 = self.started()
        giga = self.giga()
        winner = self.field_item("winner", "p2", "m-1")
        observer = self.field_item("observer", "p1", "m-2", "interzone")
        session.battlefield = [giga, winner, observer]
        self.set_result(session, "p2", "p1", [winner], [giga])
        result = session.begin_rules_confrontation_cleanup()
        self.assertNotIn(giga, session.battlefield)
        self.assertIn(GIGABONBLADE, p2["zones"]["receptacle"])
        self.assertNotIn(GIGABONBLADE, p1["zones"]["exile"])
        self.assertEqual(observer.get("counters"), {})
        self.assertEqual(result["captured"][0]["zone"], "receptacle")

    def test_effect_departure_exiles_and_weakens_each_current_field_manifestation(self):
        session, p1, _p2 = self.started()
        giga = self.giga()
        confrontation = self.field_item("foe", "p2", "m-1")
        support = self.field_item(
            "support", "p1", "m-2", "confrontation", isSupport=True,
        )
        stalemate = self.field_item("waiting", "p2", "m-3", "stalemate")
        session.battlefield = [giga, confrontation, support, stalemate]
        movement = session._rules_remove_field_item_by_effect(
            giga, "p1", "graveyard", "top", reason="destroy",
        )
        self.assertEqual((movement["status"], movement["zone"]), ("moved", "exile"))
        self.assertEqual(p1["zones"]["exile"], [GIGABONBLADE])
        self.assertEqual(confrontation["counters"], {"power": -2})
        self.assertEqual(support["counters"], {"power": -2})
        self.assertEqual(stalemate["counters"], {})

    def test_suspension_or_inactive_text_prevents_exile_rider_and_penalty(self):
        for mode in ("suspended", "inactive"):
            with self.subTest(mode=mode):
                session, p1, _p2 = self.started()
                giga = self.giga()
                other = self.field_item("other", "p2", "m-1")
                session.battlefield = [giga, other]
                if mode == "suspended":
                    session.card_rules["suspender"] = {
                        "type": "manifestation", "power": 1,
                        "suspensionThresholds": {"graveyard": 0},
                    }
                    suspender = self.field_item(
                        "suspender", "p1", "suspender",
                    )
                    session.battlefield.append(suspender)
                else:
                    giga["effectsDisabled"] = True
                movement = session._rules_remove_field_item_by_effect(
                    giga, "p1", "graveyard", "top", reason="destroy",
                )
                if mode == "suspended":
                    self.assertEqual(movement["status"], "suspended")
                    self.assertEqual(
                        session.rules_engine["suspendedCards"][0]["cardId"],
                        GIGABONBLADE,
                    )
                else:
                    self.assertEqual(movement["zone"], "graveyard")
                    self.assertEqual(p1["zones"]["graveyard"], [GIGABONBLADE])
                self.assertEqual(p1["zones"]["exile"], [])
                self.assertEqual(other["counters"], {})


if __name__ == "__main__":
    import unittest

    unittest.main()
