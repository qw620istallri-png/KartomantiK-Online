"""Strict semantic coverage for Quasimillenary, Glob-glob, and Sly Frog."""

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


QUASIMILLENARY = "v6slubph4q5ijfb_en"
GLOB_GLOB = "inner-deserts-027"
SLY_FROG = "inner-deserts-074"

EXPECTED_QUASI_ABILITY = [{
    "id": "quasimillenary-recovery-draw-from-limbo",
    "passiveEffect": {"kind": "recovery_draw_from_limbo"},
}]


class FinalThreeCardsFamily(RealCardRulesCase):
    ALL = (QUASIMILLENARY, GLOB_GLOB, SLY_FROG)

    def started(self, phase_id="recovery_draw"):
        session, p1, p2 = self.make_session()
        session.phase_tracker.update(
            index=ADVANCED_PHASES.index(phase_id), turn=8,
        )
        session.rules_engine.update(
            readyPlayerIds=["p1", "p2"],
            priorityPlayerId="p1",
            firstManifestationComplete=True,
        )
        return session, p1, p2

    def add_quasi(self, session, controller="p1", zone="interzone", **extra):
        item = self.field_item(
            "quasi", controller, QUASIMILLENARY, zone,
            controllerId=controller, x=0, y=0, rotation=0,
            stackedOn=None, **extra,
        )
        session.battlefield.append(item)
        return item

    def add_will(self, session, player, card_id, temperament):
        symbol = {"vitreous": "B", "capricious": "Y"}[temperament]
        session.card_rules[card_id] = {
            "type": "ephemeral_will", "cost": 2,
            "powerCost": f"{{{symbol}}}{{{symbol}}}",
            "temperaments": [temperament],
        }
        self.put(player, "hand", [card_id])

    def declare_with_tribute(self, session, card_id, reference, temperament):
        will_id = f"will-{temperament}"
        player = session.players["p1"]
        existing = list(player["zones"]["hand"])
        owners = dict(player["zoneOwners"]["hand"])
        self.add_will(session, player, will_id, temperament)
        player["zones"]["hand"] = existing + [will_id]
        player["zoneOwners"]["hand"] = {**owners, will_id: "p1"}
        session.rules_engine["priorityPlayerId"] = "p1"
        error, action = session.declare_rules_action(
            "p1", "Final-card tribute", kind="play_card",
            source={"cardId": will_id, "zone": "hand"},
            payment_card_ids=[reference],
        )
        self.assertIsNone(error, error)
        self.assertEqual(action["cost"]["tributeCardIds"], [card_id])
        return action

    def enable_field_tributes(self, session):
        session.card_rules["orator-probe"] = {
            "type": "manifestation", "power": 1,
            "temperaments": ["hollow"],
            "passiveEffects": [{"kind": "field_manifestations_as_tribute"}],
        }
        session.battlefield.append(self.field_item(
            "orator", "p2", "orator-probe", "interzone",
        ))

    def test_compiles_all_three_exact_contracts(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        self.assertEqual(self.ABILITIES[QUASIMILLENARY], EXPECTED_QUASI_ABILITY)
        self.assertEqual(rules[QUASIMILLENARY]["passiveEffects"], [
            {"kind": "recovery_draw_from_limbo"},
        ])
        self.assertNotIn(GLOB_GLOB, self.ABILITIES)
        self.assertNotIn(SLY_FROG, self.ABILITIES)
        self.assertEqual(rules[GLOB_GLOB]["tributeDestination"], "deck_bottom")
        self.assertEqual(rules[SLY_FROG]["tributeDestination"], "stalemate")

    def test_quasi_offers_one_private_recovery_choice_and_decline_draws_from_deck(self):
        session, p1, p2 = self.started()
        self.add_quasi(session)
        self.put(p1, "graveyard", ["m-1"])
        self.put(p1, "deck", ["m-2", "m-3"])
        self.put(p2, "deck", ["m-4", "m-5"])

        error, pending = session.resolve_recovery_draw(hand_limit=2)
        self.assertIsNone(error, error)
        self.assertTrue(pending["awaitingChoice"])
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(
            (choice["kind"], choice["purpose"], choice["playerId"]),
            ("binary_choice", "quasimillenary", "p1"),
        )
        self.assertIsNotNone(
            session.resolve_rules_choice("p2", choice["id"], option="no")[0]
        )
        error, result = session.resolve_rules_choice(
            "p1", choice["id"], option="no",
        )
        self.assertIsNone(error, error)
        self.assertEqual(result["status"], "deck")
        self.assertEqual(p1["zones"]["graveyard"], ["m-1"])
        self.assertCountEqual(p1["zones"]["hand"], ["m-2", "m-3"])
        self.assertEqual(session.rules_engine["limboDrawn"], {})

    def test_quasi_yes_shuffles_limbo_draws_it_first_then_fills_from_deck_and_reveals(self):
        session, p1, p2 = self.started()
        self.add_quasi(session)
        self.put(p1, "hand", ["m-0"])
        self.put(p1, "graveyard", ["m-1", "m-2"])
        self.put(p1, "deck", ["m-3", "m-4"])
        self.put(p2, "deck", ["m-5", "m-6", "m-7", "m-8"])
        error, pending = session.resolve_recovery_draw(hand_limit=4)
        self.assertIsNone(error, error)
        choice = session.rules_engine["pendingChoice"]
        error, result = session.resolve_rules_choice(
            "p1", choice["id"], option="yes",
        )
        self.assertIsNone(error, error)
        self.assertEqual(result["status"], "limbo")
        self.assertEqual(p1["zones"]["graveyard"], [])
        self.assertCountEqual(p1["zones"]["hand"], ["m-0", "m-1", "m-2", "m-3"])
        self.assertCountEqual(
            session.rules_engine["limboDrawn"]["p1"], ["m-1", "m-2"],
        )
        opponent_view = session.serialize_for("p2", "player")["rulesEngine"]
        self.assertCountEqual(
            opponent_view["uncoveredHand"]["p1"], ["m-1", "m-2"],
        )
        self.assertEqual(session.rules_engine["limboRecoveryPlayerIds"], [])

    def test_quasi_requires_its_controllers_active_interzone_source_and_nonempty_limbo(self):
        for label, controller, zone, extra, has_limbo in (
            ("wrong-controller", "p2", "interzone", {}, True),
            ("wrong-zone", "p1", "confrontation", {}, True),
            ("face-down", "p1", "interzone", {"faceUp": False}, True),
            ("disabled", "p1", "interzone", {"effectsDisabled": True}, True),
            ("empty-limbo", "p1", "interzone", {}, False),
        ):
            with self.subTest(label=label):
                session, p1, p2 = self.started()
                self.add_quasi(session, controller, zone, **extra)
                if has_limbo:
                    self.put(p1, "graveyard", ["m-1"])
                self.put(p1, "deck", ["m-2"])
                self.put(p2, "deck", ["m-3"])
                error, result = session.resolve_recovery_draw(hand_limit=1)
                self.assertIsNone(error, error)
                self.assertFalse(result.get("awaitingChoice", False))
                self.assertIsNone(session.rules_engine["pendingChoice"])
                self.assertEqual(p1["zones"]["hand"], ["m-2"])

    def test_quasi_marked_hand_card_exiles_instead_of_entering_limbo_or_deck(self):
        for zone in ("graveyard", "deck"):
            with self.subTest(zone=zone):
                session, p1, _p2 = self.started()
                self.put(p1, "hand", ["m-1"])
                session.rules_engine["limboDrawn"] = {"p1": ["m-1"]}
                session.battlefield = []
                error, _owner = session.move_zone_card(
                    "p1", "hand", "p1", zone, "m-1", "top",
                )
                self.assertIsNone(error, error)
                self.assertEqual(p1["zones"]["exile"], ["m-1"])
                self.assertNotIn("m-1", p1["zones"][zone])
                self.assertEqual(session.rules_engine["limboDrawn"]["p1"], [])

    def test_quasi_field_card_exiles_on_nonvessel_exit_but_vessel_clears_mark(self):
        session, p1, p2 = self.started()
        session.rules_engine["limboDrawn"] = {"p1": ["m-1", "m-2"]}
        first = self.field_item("first", "p1", "m-1", "confrontation")
        second = self.field_item("second", "p1", "m-2", "confrontation")
        session.battlefield = [first, second]

        moved = session._rules_remove_field_item_by_effect(
            first, "p1", "graveyard", "top", reason="destroy",
        )
        self.assertEqual((moved["status"], moved["zone"]), ("moved", "exile"))
        self.assertIn("m-1", p1["zones"]["exile"])

        moved = session._rules_remove_field_item_by_effect(
            second, "p2", "receptacle", "top", reason="vessel",
        )
        self.assertEqual((moved["status"], moved["zone"]), ("moved", "receptacle"))
        self.assertIn("m-2", p2["zones"]["receptacle"])
        self.assertEqual(p2["zoneOwners"]["receptacle"]["m-2"], "p1")
        self.assertEqual(session.rules_engine["limboDrawn"]["p1"], [])

    def test_glob_glob_hand_tribute_goes_to_bottom_of_immutable_owners_deck(self):
        session, p1, p2 = self.started("confrontation_reaction")
        self.put(p1, "hand", {GLOB_GLOB: "p2"})
        action = self.declare_with_tribute(
            session, GLOB_GLOB, GLOB_GLOB, "vitreous",
        )
        movement = action["cost"]["tributeMovements"][0]
        self.assertEqual(movement["destination"], "deck_bottom")
        self.assertEqual(p2["zones"]["deck"][-1], GLOB_GLOB)
        self.assertEqual(p2["zoneOwners"]["deck"][GLOB_GLOB], "p2")
        self.assertNotIn(GLOB_GLOB, p1["zones"]["graveyard"])

    def test_glob_glob_field_tribute_uses_the_same_owner_deck_replacement(self):
        session, p1, p2 = self.started("confrontation_reaction")
        self.enable_field_tributes(session)
        glob = self.field_item(
            "glob", "p2", GLOB_GLOB, "confrontation", controllerId="p1",
        )
        session.battlefield.append(glob)
        action = self.declare_with_tribute(
            session, GLOB_GLOB, "battlefield|glob", "vitreous",
        )
        movement = action["cost"]["tributeMovements"][0]
        self.assertEqual(
            (movement["fromZone"], movement["destination"]),
            ("confrontation", "deck_bottom"),
        )
        self.assertIsNone(session.find_battlefield_item("glob"))
        self.assertEqual(p2["zones"]["deck"][-1], GLOB_GLOB)
        self.assertNotIn(GLOB_GLOB, p1["zones"]["graveyard"])

    def test_sly_frog_hand_tribute_creates_one_stalemate_occurrence(self):
        session, p1, p2 = self.started("confrontation_reaction")
        self.put(p1, "hand", {SLY_FROG: "p2"})
        action = self.declare_with_tribute(
            session, SLY_FROG, SLY_FROG, "capricious",
        )
        movement = action["cost"]["tributeMovements"][0]
        frog = session.find_battlefield_item(movement["itemId"])
        self.assertEqual(movement["destination"], "stalemate")
        self.assertEqual(session.rules_field_zone(frog), "stalemate")
        self.assertEqual((frog["ownerId"], frog["controllerId"]), ("p2", "p1"))
        self.assertNotIn(SLY_FROG, p1["zones"]["graveyard"])
        self.assertNotIn(SLY_FROG, p2["zones"]["graveyard"])

    def test_sly_frog_field_tribute_moves_the_existing_occurrence_to_stalemate(self):
        session, p1, _p2 = self.started("confrontation_reaction")
        self.enable_field_tributes(session)
        frog = self.field_item(
            "frog", "p1", SLY_FROG, "interzone", controllerId="p1",
        )
        session.battlefield.append(frog)
        action = self.declare_with_tribute(
            session, SLY_FROG, "battlefield|frog", "capricious",
        )
        movement = action["cost"]["tributeMovements"][0]
        self.assertEqual(
            (movement["fromZone"], movement["destination"], movement["itemId"]),
            ("interzone", "stalemate", "frog"),
        )
        self.assertIs(session.find_battlefield_item("frog"), frog)
        self.assertEqual(session.rules_field_zone(frog), "stalemate")
        self.assertNotIn(SLY_FROG, p1["zones"]["graveyard"])

    def test_special_tribute_destinations_do_not_apply_to_ordinary_moves(self):
        for card_id in (GLOB_GLOB, SLY_FROG):
            with self.subTest(card_id=card_id):
                session, p1, _p2 = self.started()
                self.put(p1, "hand", [card_id])
                error, _owner = session.move_zone_card(
                    "p1", "hand", "p1", "graveyard", card_id, "top",
                    limbo_reason="discard",
                )
                self.assertIsNone(error, error)
                self.assertIn(card_id, p1["zones"]["graveyard"])
                self.assertFalse(any(
                    item.get("cardId") == card_id
                    for item in session.battlefield
                ))


if __name__ == "__main__":
    import unittest

    unittest.main()
