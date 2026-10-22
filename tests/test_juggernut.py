import test_game_state as game_tests
from session import ADVANCED_PHASES


class JuggernutTests(game_tests.RealCardRulesCase):
    CARD = "inner-deserts-100"
    ALL = (CARD,)
    ABILITY = "juggernut-charges-into-confrontation"

    def started(self, phase="recovery_end"):
        session, p1, p2 = self.make_session()
        session.rules_engine.update(readyPlayerIds=["p1", "p2"], firstManifestationComplete=False, priorityPlayerId="p1")
        session.phase_tracker["index"] = ADVANCED_PHASES.index(phase)
        return session, p1, p2

    def charge(self, session, item_id="jugg"):
        return session.declare_rules_action("p1", "Charge", kind="activated_effect", source={"zone": "battlefield", "itemId": item_id, "cardId": self.CARD}, ability_id=self.ABILITY)

    def advance(self, session):
        for _ in range(2):
            error, result = session.pass_rules_priority(session.rules_engine["priorityPlayerId"])
            self.assertIsNone(error)
        return result

    def test_free_play_arrives_in_will_slots_even_if_dropped_on_the_cz(self):
        session, p1, _ = self.started("end_actions")
        self.put(p1, "hand", [self.CARD])
        error, _ = session.declare_rules_action("p1", "Juggernut", kind="play_card", source={"zone": "hand", "cardId": self.CARD}, placement={"x": 445, "y": 800})
        self.assertIsNone(error)
        result = session.resolve_rules_top_action()["action"]["sourceResolution"]
        item = session.find_battlefield_item(result["itemId"])
        self.assertEqual(item.get("fieldZone"), "field")
        session.rules_auto_layout()
        self.assertEqual(item["layoutKey"], "field:p1")
        self.assertEqual(item["y"], 1300)

    def test_recovery_charge_pays_then_becomes_the_only_first_manifestation(self):
        session, p1, _ = self.started()
        jugg = self.field_item("jugg", "p1", self.CARD, "field")
        session.battlefield = [jugg]
        self.put(p1, "hand", ["m-1"])
        session.card_rules["m-1"]["power"] = 2
        error, _ = self.charge(session)
        self.assertIsNotNone(error)
        error, _ = session.declare_rules_action("p1", "Charge", kind="activated_effect", source={"zone": "battlefield", "itemId": "jugg", "cardId": self.CARD}, ability_id=self.ABILITY, payment_card_ids=["m-1"])
        self.assertIsNone(error)
        self.assertEqual(jugg["fieldZone"], "field")
        session.resolve_rules_top_action()
        self.assertEqual(jugg["fieldZone"], "confrontation")
        self.advance(session)
        self.assertEqual(session.rules_engine["firstManifestationItemIds"]["p1"], "jugg")
        self.assertIsNotNone(session.register_first_manifestation("p1", self.field_item("another", "p1", "m-2")))

    def test_existing_cz_manifestation_is_registered_before_the_pm_step(self):
        session, _, _ = self.started()
        existing = self.field_item("existing", "p1", "m-1")
        session.battlefield = [existing]
        self.advance(session)
        self.assertEqual(session.rules_engine["firstManifestationItemIds"], {"p1": "existing"})
        self.assertIn("p1", session.rules_engine["firstManifestationValidatedPlayerIds"])
        self.assertTrue(existing["faceUp"])
        self.assertIsNotNone(session.register_first_manifestation("p1", self.field_item("another", "p1", "m-2")))

    def test_existing_cz_manifestation_blocks_charge_before_any_cost_is_paid(self):
        session, _, _ = self.started()
        session.battlefield = [self.field_item("existing", "p1", "m-1"), self.field_item("jugg", "p1", self.CARD, "field")]
        session.add_rules_excess_essence("p1", [{"temperament": "hollow", "amount": 2}])
        error, _ = self.charge(session)
        self.assertIsNotNone(error)
        self.assertFalse(session.rules_engine["actionStack"])
        self.assertEqual(sum(token["counters"]["essence"] for token in session.tokens), 2)

    def test_both_existing_firsts_continue_to_before_revelation(self):
        session, _, _ = self.started()
        session.battlefield = [self.field_item("a", "p1", "m-1"), self.field_item("b", "p2", "m-2")]
        self.advance(session)
        self.assertEqual(session.current_phase_id(), "confrontation_before_revelation")
        self.assertTrue(session.rules_engine["firstManifestationComplete"])

    def test_a_manifestation_already_in_the_cz_is_promoted_from_support_to_pm(self):
        session, _, _ = self.started()
        session.battlefield = [self.field_item("support", "p1", "m-1", isSupport=True)]
        self.advance(session)
        self.assertEqual(session.rules_engine["firstManifestationItemIds"], {"p1": "support"})
        self.assertFalse(session.battlefield[0]["isSupport"])
