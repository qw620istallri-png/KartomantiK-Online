"""Regressions for zone transfers, BOB replacements and reanimation entry."""
import unittest
import test_special_payments as special_payments


class ZoneTransitionAuditTests(unittest.TestCase):
    case = special_payments.SpecialPaymentTests()
    REFORGE = "z2fen73ktw8pbqz_en"
    EXTINGUISH = "inner-deserts-115"
    BOB = "inner-deserts-134"
    CARESS = "inner-deserts-024"
    SWINE = "l4suqymyd2ehsue_en"
    SEEKER = "fvk7w9y8xidbuwa_en"

    def setup(self, source=REFORGE, target=SWINE, power=None, container="p2"):
        session, p1, p2 = self.case.started()
        self.case.put(p1, "hand", [source])
        self.case.put(session.players[container], "graveyard", [target])
        for pid in ["p1", "p2"]:
            session.add_rules_excess_essence(pid, [{"temperament": "transcendent", "amount": 20}])
        if power is not None:
            session.battlefield.append(self.case.field_item("bob", "p1", self.BOB, counters={"power": power - 2}))
        return session, p1, p2

    def target(self, card=SWINE, container="p2"):
        return {"kind": "zone_card", "zone": "graveyard", "containerId": container, "cardId": card}

    def play(self, session, source, targets, player="p1"):
        error, action = session.declare_rules_action(player, source, kind="play_card",
            source={"cardId": source, "zone": "hand"},
            ability_id=self.case.ABILITIES[source][0]["id"], targets=targets)
        self.assertIsNone(error)
        return action

    def test_reforging_cannot_reanimate_a_target_exiled_in_response(self):
        session, _, p2 = self.setup()
        self.case.put(p2, "hand", [self.EXTINGUISH])
        self.play(session, self.REFORGE, [self.target()])
        self.play(session, self.EXTINGUISH, [], "p2")
        session.resolve_rules_top_action()
        result = session.resolve_rules_top_action()["action"]["effectResult"]
        self.assertEqual(result["status"], "no_effect")
        self.assertIn(self.SWINE, p2["zones"]["exile"])
        self.assertFalse(any(i["cardId"] == self.SWINE for i in session.battlefield))

    def test_reanimation_handler_also_checks_extraction(self):
        session, _, p2 = self.setup()
        session.take_zone_card("p2", "graveyard", self.SWINE)
        result = session.apply_rules_action_result({"controllerId": "p1", "source": {},
            "targets": [self.target()], "ability": self.case.ABILITIES[self.REFORGE][0]})
        self.assertEqual(result["status"], "target_missing")
        self.assertFalse(any(i["cardId"] == self.SWINE for i in session.battlefield))

    def test_bob_suspends_reanimation_and_releases_to_owners_deck(self):
        for power in [None, 2, 5]:
            with self.subTest(power=power):
                session, _, p2 = self.setup(power=power)
                self.play(session, self.REFORGE, [self.target()])
                result = session.resolve_rules_top_action()["action"]["effectResult"]
                self.assertNotIn(self.SWINE, p2["zones"]["graveyard"])
                self.assertEqual(any(i["cardId"] == self.SWINE for i in session.battlefield), power != 5)
                entries = session.rules_engine["suspendedCards"]
                self.assertEqual(len(entries), 1 if power == 5 else 0)
                if power == 5:
                    self.assertEqual(result["status"], "suspended")
                    self.assertEqual(entries[0]["sourceEffectId"], "bob")
                    session.release_rules_suspended_by("bob")
                    self.assertIn(self.SWINE, p2["zones"]["deck"])

    def test_caress_transfers_honor_bob_after_the_reorder_choice(self):
        for power in [None, 2, 5]:
            with self.subTest(power=power):
                session, _, p2 = self.setup(self.CARESS, power=power)
                session.rules_engine.setdefault("zoneEntryTurns", {})[f"p2:graveyard:{self.SWINE}"] = session.phase_tracker["turn"]
                self.play(session, self.CARESS, [self.target()])
                session.resolve_rules_top_action()
                choice = session.rules_engine["pendingChoice"]
                error, _ = session.resolve_rules_choice("p1", choice["id"], option={"groups": [
                    {"playerId": "p2", "top": [], "bottom": [self.SWINE]}]})
                self.assertIsNone(error)
                self.assertIsNone(session.rules_engine["pendingChoice"])
                self.assertEqual(self.SWINE in p2["zones"]["deck"], power is None)
                self.assertEqual(len(session.rules_engine["suspendedCards"]), 0 if power is None else 1)

    def test_reanimated_seeker_triggers_once_under_its_new_controller(self):
        session, p1, p2 = self.setup(target=self.SEEKER)
        self.case.put(p1, "deck", ["m-0"])
        self.play(session, self.REFORGE, [self.target(self.SEEKER)])
        session.resolve_rules_top_action()
        self.assertEqual(len(session.rules_engine["actionStack"]), 1)
        entry = session.rules_engine["actionStack"][0]
        self.assertEqual(entry["ability"]["id"], "draw-on-enter-field")
        self.assertEqual(entry["controllerId"], "p1")
        session.resolve_rules_top_action()
        self.assertIn("m-0", p1["zones"]["hand"])
        self.assertNotIn("m-0", p2["zones"]["hand"])
        self.assertFalse(session.rules_engine["actionStack"])

    def test_urolong_reanimation_without_effects_does_not_trigger_seeker(self):
        session, p1, _ = self.setup(target=self.SEEKER, container="p1")
        source = "pekwxpsy3c0ro3l_en"
        session.battlefield.append(self.case.field_item("urolong", "p1", source, "interzone"))
        self.case.put(p1, "deck", ["m-0"])
        error, _ = session.declare_rules_action("p1", "Urolong", kind="activated_effect",
            source={"cardId": source, "zone": "battlefield", "itemId": "urolong"},
            ability_id=self.case.ABILITIES[source][0]["id"], targets=[self.target(self.SEEKER, "p1")])
        self.assertIsNone(error)
        session.resolve_rules_top_action()
        self.assertFalse(session.rules_engine["actionStack"])
        self.assertNotIn("m-0", p1["zones"]["hand"])
        self.assertTrue(next(i for i in session.battlefield if i["cardId"] == self.SEEKER)["effectsDisabled"])

    def test_bob_allows_in_deck_order_but_suspends_the_card_set_aside(self):
        session, p1, _ = self.setup(power=2)
        self.case.put(p1, "deck", ["m-0", "m-3", "m-4", "m-5"])
        session.rules_engine["pendingChoice"] = {"id": "reorder", "kind": "deck_reorder", "playerId": "p1",
            "_groups": [{"playerId": "p1", "cardIds": ["m-0", "m-3", "m-4"],
                         "extraSide": "hand", "extraMin": 1, "extraMax": 1}]}
        error, _ = session.resolve_rules_choice("p1", "reorder", option={"groups": [
            {"playerId": "p1", "top": ["m-3"], "bottom": ["m-0"], "extra": ["m-4"]}]})
        self.assertIsNone(error)
        self.assertEqual(p1["zones"]["deck"], ["m-3", "m-5", "m-0"])
        self.assertNotIn("m-4", p1["zones"]["hand"])
        self.assertEqual([e["cardId"] for e in session.rules_engine["suspendedCards"]], ["m-4"])
