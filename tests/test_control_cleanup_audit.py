"""Victory overrides and BOB's zone lifetime, with owner-based normal cleanup."""
import unittest
import test_special_payments as special_payments


class ControlCleanupAuditTests(unittest.TestCase):
    case = special_payments.SpecialPaymentTests()
    REFORGE = "z2fen73ktw8pbqz_en"
    BOB = "inner-deserts-134"
    SWINE = "l4suqymyd2ehsue_en"

    def compare(self, session):
        session.phase_tracker["index"] = session.phase_sequence().index("resolution_compare")
        return session.prepare_rules_confrontation_result()

    def finish(self, session):
        for _ in range(12):
            choice = session.rules_engine.get("pendingChoice")
            if not choice:
                return
            self.assertEqual(choice["kind"], "confrontation_destination")
            error, _ = session.resolve_rules_choice(choice["playerId"], choice["id"], option="deck_bottom")
            self.assertIsNone(error)
        self.fail("Confrontation cleanup did not finish")

    def reanimate(self, owner, wins=True):
        session, p1, p2 = self.case.started()
        self.case.put(p1, "hand", [self.REFORGE])
        self.case.put(session.players[owner], "graveyard", [self.SWINE])
        session.card_rules["m-1"]["power"] = 5 if wins else 1
        session.card_rules["m-2"]["power"] = 1 if wins else 5
        session.add_rules_excess_essence("p1", [{"temperament": "transcendent", "amount": 20}])
        error, _ = session.declare_rules_action("p1", "Reforge", kind="play_card",
            source={"cardId": self.REFORGE, "zone": "hand"},
            ability_id=self.case.ABILITIES[self.REFORGE][0]["id"],
            targets=[{"kind": "zone_card", "zone": "graveyard", "containerId": owner, "cardId": self.SWINE}])
        self.assertIsNone(error)
        session.resolve_rules_top_action()
        return session, p1, p2

    def test_reanimation_exile_depends_on_victory_not_ownership(self):
        for owner in ["p1", "p2"]:
            for wins in [False, True]:
                with self.subTest(owner=owner, wins=wins):
                    session, p1, p2 = self.reanimate(owner, wins)
                    result = self.compare(session)
                    self.assertEqual(result["winnerId"], "p1" if wins else "p2")
                    session.begin_rules_confrontation_cleanup()
                    self.finish(session)
                    self.assertEqual(self.SWINE in session.players[owner]["zones"]["exile"], wins)
                    if not wins:
                        destination = p2["zones"]["receptacle"] if owner == "p1" else p2["zones"]["deck"]
                        self.assertIn(self.SWINE, destination)

    def test_normal_capture_keeps_the_rulebooks_owner_based_destination(self):
        session, p1, p2 = self.case.started()
        session.battlefield.append(self.case.field_item("borrowed", "p2", self.SWINE, controllerId="p1"))
        session.card_rules["m-1"]["power"] = 5
        self.assertEqual(self.compare(session)["winnerId"], "p1")
        session.begin_rules_confrontation_cleanup()
        self.finish(session)
        self.assertIn(self.SWINE, p1["zones"]["receptacle"])
        self.assertEqual(p1["zoneOwners"]["receptacle"][self.SWINE], "p2")

    def test_victory_override_keeps_the_comparison_outcome_after_control_changes(self):
        session, _, p2 = self.reanimate("p2")
        self.compare(session)
        borrowed = next(i for i in session.battlefield if i["cardId"] == self.SWINE)
        borrowed["controllerId"] = "p2"
        session.begin_rules_confrontation_cleanup()
        self.finish(session)
        self.assertIn(self.SWINE, p2["zones"]["exile"])

    def bob(self):
        session, p1, p2 = self.case.started()
        item = self.case.field_item("bob", "p1", self.BOB, counters={"power": 3})
        session.battlefield.append(item)
        self.case.put(p1, "graveyard", [self.SWINE])
        error, _, replacement = session.move_zone_card_by_effect("p1", "graveyard", "p1", "hand", self.SWINE)
        self.assertIsNone(error)
        self.assertIsNotNone(replacement)
        return session, p1, p2, item

    def test_bob_releases_after_a_real_stalemate(self):
        session, p1, _, bob = self.bob()
        session.battlefield = [bob, self.case.field_item("other-bob", "p2", self.BOB, counters={"power": 3})]
        self.assertTrue(self.compare(session)["stalemate"])
        session.begin_rules_confrontation_cleanup()
        self.assertEqual(bob["fieldZone"], "stalemate")
        self.assertIn(self.SWINE, p1["zones"]["deck"])
        self.assertFalse(session.rules_engine["suspendedCards"])

    def test_state_pass_releases_bob_after_it_moves_to_another_field_zone(self):
        for zone in ["interzone", "stalemate"]:
            with self.subTest(zone=zone):
                session, p1, _, bob = self.bob()
                bob["fieldZone"] = zone
                session.resolve_rules_state_actions()
                session.prune_rules_ongoing_effects()
                self.assertIn(self.SWINE, p1["zones"]["deck"])
                self.assertFalse(session.rules_engine["suspendedCards"])
                session.prune_rules_ongoing_effects()
                self.assertEqual(p1["zones"]["deck"].count(self.SWINE), 1)

    def test_bob_threshold_eleven_exiles_the_suspended_cards(self):
        session, p1, _, bob = self.bob()
        bob["counters"]["power"] = 9
        session.resolve_rules_state_actions()
        self.assertIn(self.SWINE, p1["zones"]["exile"])
        self.assertIn(self.BOB, p1["zones"]["exile"])
        self.assertFalse(session.rules_engine["suspendedCards"])

    def test_power_loss_without_leaving_cz_does_not_release_suspended_cards(self):
        session, p1, _, bob = self.bob()
        bob["counters"]["power"] = 0
        session.prune_rules_ongoing_effects()
        self.assertNotIn(self.SWINE, p1["zones"]["deck"])
        self.assertEqual(len(session.rules_engine["suspendedCards"]), 1)

    def test_loss_destinations_follow_actual_defeat_before_owner_based_cleanup(self):
        for card in ["xw1fbhs6hwz6thc_en", "inner-deserts-132"]:
            with self.subTest(card=card):
                session, _, _ = self.case.started()
                item = self.case.field_item("borrowed", "p2", card, controllerId="p1")
                session.battlefield.append(item)
                session.card_rules["m-2"]["power"] = 100
                self.assertEqual(self.compare(session)["loserId"], "p1")
                session.begin_rules_confrontation_cleanup()
                self.finish(session)
                self.assertIsNotNone(session.find_battlefield_item("borrowed"))
                self.assertEqual(item["fieldZone"], "interzone")
                self.assertEqual(session.rules_item_controller_id(item), "p2" if card == "xw1fbhs6hwz6thc_en" else "p1")

    def test_owner_destination_can_return_a_losing_borrowed_card_to_its_interzone(self):
        session, _, _ = self.case.started()
        borrowed = self.case.field_item("borrowed", "p2", self.SWINE, controllerId="p1")
        session.battlefield.append(borrowed)
        session.card_rules["m-2"]["power"] = 100
        self.compare(session)
        session.begin_rules_confrontation_cleanup()
        for _ in range(8):
            choice = session.rules_engine.get("pendingChoice")
            if not choice:
                break
            error, _ = session.resolve_rules_choice(choice["playerId"], choice["id"],
                option="interzone" if choice["itemId"] == "borrowed" else "deck_bottom")
            self.assertIsNone(error)
        self.assertEqual(borrowed["fieldZone"], "interzone")
        self.assertEqual(session.rules_item_controller_id(borrowed), "p2")

    def test_stalemate_entry_returns_borrowed_cards_to_owner_control(self):
        session, _, _ = self.case.started()
        borrowed = self.case.field_item("borrowed", "p2", self.SWINE, controllerId="p1")
        session.battlefield = [borrowed, self.case.field_item("other", "p2", self.SWINE)]
        self.assertTrue(self.compare(session)["stalemate"])
        session.begin_rules_confrontation_cleanup()
        self.assertEqual(borrowed["fieldZone"], "stalemate")
        self.assertEqual(session.rules_item_controller_id(borrowed), "p2")
