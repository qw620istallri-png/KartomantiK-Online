"""Play-test regressions for beta 139.2, using the shipped card texts and rules."""
import unittest
import test_game_state as game_tests
from session import ADVANCED_PHASES


class Release1392Tests(game_tests.RealCardRulesCase):
    FATE = "z2fen73ktw8pbqz_en"
    RECOVER = "0coh7nrbvcvan1i_en"
    GRIMOIRE = "omhqwnu5tvwlzzg_en"
    OPPRESS = "obn1uv72ewxv3y5_en"
    JUGGERNUT = "inner-deserts-100"
    MULTI = "inner-deserts-138"
    SPLENDOR = "inner-deserts-143"
    OBELISK = "9bkn03sc9veaa88_en"
    ALL = (FATE, RECOVER, GRIMOIRE, OPPRESS, JUGGERNUT, MULTI, SPLENDOR, OBELISK)

    def started(self, phase="confrontation_reaction"):
        session, p1, p2 = self.make_session()
        session.rules_engine.update(readyPlayerIds=["p1", "p2"], firstManifestationComplete=True, priorityPlayerId="p1")
        session.rules_engine["autoSkipPhases"] = True
        session.phase_tracker["index"] = ADVANCED_PHASES.index(phase)
        session.battlefield = [self.field_item("first-a", "p1", "m-1"), self.field_item("first-b", "p2", "m-2")]
        return session, p1, p2

    def test_grimoire_plays_the_attached_cards_own_ability(self):
        for card, ability, target in [
            (self.RECOVER, "return-limbo-card-to-hand", {"kind": "zone_card", "containerId": "p1", "zone": "graveyard", "cardId": "m-9"}),
            (self.OPPRESS, "oppress-power-modifier", {"kind": "card", "itemId": "first-b", "cardId": "m-2"}),
        ]:
            with self.subTest(card=card):
                session, p1, _ = self.started()
                self.put(p1, "graveyard", ["m-9"])
                host = self.field_item("book", "p1", self.GRIMOIRE, "field", attachedCards=[{"cardId": card, "ownerId": "p1"}])
                session.battlefield.append(host)
                session.add_rules_excess_essence("p1", [{"temperament": "transcendent", "amount": 2}])
                error, action = session.declare_rules_action("p1", "Play from Grimoire", kind="play_card", source={"zone": "attached", "itemId": "book", "cardId": card}, ability_id=ability, targets=[target])
                self.assertIsNone(error)
                self.assertEqual(action["ability"]["id"], ability)
                self.assertEqual(host["attachedCards"], [])
                outcome = session.resolve_rules_top_action()["action"]
                self.assertNotEqual(outcome.get("effectResult", {}).get("kind"), "invalid_targets")
                if card == self.RECOVER:
                    self.assertIn("m-9", p1["zones"]["hand"])

    def test_reforging_fate_uses_an_opponents_limbo_and_keeps_ownership(self):
        session, p1, p2 = self.started()
        self.put(p1, "hand", [self.FATE])
        self.put(p2, "graveyard", ["m-9"])
        session.add_rules_excess_essence("p1", [{"temperament": "melancholic", "amount": 3}])
        error, _ = session.declare_rules_action("p1", "Reforge", kind="play_card", source={"zone": "hand", "cardId": self.FATE}, ability_id="reforging-fate-support-from-limbo", targets=[{"kind": "zone_card", "containerId": "p2", "zone": "graveyard", "cardId": "m-9"}])
        self.assertIsNone(error)
        session.resolve_rules_top_action()
        item = next(item for item in session.battlefield if item.get("cardId") == "m-9")
        self.assertEqual((item["ownerId"], item["controllerId"], item["fieldZone"]), ("p2", "p1", "confrontation"))
        self.assertTrue(item["isSupport"])
        self.assertNotIn("m-9", p2["zones"]["graveyard"])

    def test_juggernut_is_free_to_play_but_charges_for_its_field_ability(self):
        session, p1, _ = self.started("end_actions")
        self.put(p1, "hand", [self.JUGGERNUT])
        error, action = session.declare_rules_action("p1", "Juggernut", kind="play_card", source={"zone": "hand", "cardId": self.JUGGERNUT})
        self.assertIsNone(error)
        self.assertEqual(action["cost"]["tributeRequirements"], {})
        result = session.resolve_rules_top_action()["action"]["sourceResolution"]
        item_id = result["itemId"]
        session.phase_tracker["index"] = ADVANCED_PHASES.index("recovery_end")
        session.battlefield = [item for item in session.battlefield if item["id"] == item_id]
        session.rules_engine["firstManifestationComplete"] = False
        session.rules_engine["firstManifestationItemIds"] = {}
        session.rules_engine["priorityPlayerId"] = "p1"
        error, _ = session.declare_rules_action("p1", "Charge", kind="activated_effect", source={"zone": "battlefield", "itemId": item_id, "cardId": self.JUGGERNUT}, ability_id="juggernut-charges-into-confrontation")
        self.assertIsNotNone(error)
        session.add_rules_excess_essence("p1", [{"temperament": "hollow", "amount": 2}])
        error, action = session.declare_rules_action("p1", "Charge", kind="activated_effect", source={"zone": "battlefield", "itemId": item_id, "cardId": self.JUGGERNUT}, ability_id="juggernut-charges-into-confrontation")
        self.assertIsNone(error)
        self.assertEqual(action["cost"]["tributeRequirements"], {"hollow": 2})

    def test_immediate_triggers_stay_above_the_other_players_normal_triggers(self):
        session, _, _ = self.started("confrontation_immediate")
        def action(key, player, immediate):
            return {"id": key, "controllerId": player, "kind": "triggered_effect", "source": {"cardId": "m-1", "zone": "battlefield"}, "ability": {}, "immediate": immediate, "targets": []}
        session.queue_rules_simultaneous_actions([action("immediate", "p1", True), action("normal", "p2", False)], priority_player_id="p1")
        self.assertEqual(session.rules_engine["actionStack"][-1]["id"], "immediate")
        resolved = session.resolve_rules_immediate_actions()
        self.assertEqual([entry["action"]["id"] for entry in resolved], ["immediate"])

    def test_reaction_does_not_auto_pass_a_player_holding_a_will(self):
        session, p1, _ = self.started()
        self.put(p1, "hand", [self.OPPRESS])
        self.assertIsNone(session.rules_auto_pass_player())

    def test_match_reset_clears_triggers_waiting_for_immediates(self):
        session, _, _ = self.started()
        session.rules_engine["deferredAfterImmediateActions"] = [{"id": "old-trigger"}]
        session.reset_phase_tracker()
        self.assertEqual(session.rules_engine["deferredAfterImmediateActions"], [])

    def test_normal_optional_trigger_waits_for_immediate_and_rechecks_its_source(self):
        for source_survives in [True, False]:
            with self.subTest(source_survives=source_survives):
                session, _, _ = self.started("confrontation_immediate")
                immediate = {"id": "immediate", "controllerId": "p1", "kind": "triggered_effect", "source": {}, "ability": {}, "immediate": True, "targets": []}
                normal = {"id": "normal", "controllerId": "p2", "kind": "triggered_effect", "source": {"itemId": "first-b", "cardId": "m-2", "zone": "battlefield"}, "ability": {"trigger": {"event": "enters_field"}}, "immediate": False, "optional": True, "targets": []}
                session.queue_rules_simultaneous_actions([normal, immediate], priority_player_id="p1")
                self.assertIsNone(session.rules_engine["pendingChoice"])
                if not source_survives:
                    session.battlefield.remove(session.find_battlefield_item("first-b"))
                session.resolve_rules_immediate_actions()
                choice = session.rules_engine["pendingChoice"]
                if source_survives:
                    self.assertEqual(choice["kind"], "optional_stack_action")
                    self.assertEqual(choice["actionId"], "normal")
                else:
                    self.assertIsNone(choice)
                    self.assertFalse(session.rules_engine["actionStack"])

    def test_entry_target_picker_waits_until_opponents_immediate_has_resolved(self):
        session, _, _ = self.started("confrontation_immediate")
        session.card_rules["m-1"]["triggeredAbilities"] = [{
            "id": "normal-entry", "trigger": {"event": "enters_field"},
            "targets": {"min": 1, "max": 1, "kind": "card", "cardType": "manifestation", "zones": ["battlefield"]},
            "ongoingEffect": {"kind": "power_modifier", "value": 1, "duration": "until_end_of_turn"},
        }]
        session.card_rules["m-2"]["triggeredAbilities"] = [{
            "id": "immediate-entry", "trigger": {"event": "enters_field"}, "immediate": True,
            "result": {"kind": "add_counter_source", "counter": "Echo", "value": 1},
        }]
        actions = session.queue_rules_battlefield_entry_triggers("m-1", "p1", "first-a", True, defer=True)
        actions.extend(session.queue_rules_battlefield_entry_triggers("m-2", "p2", "first-b", True, defer=True))
        self.assertIsNone(session.rules_engine["pendingChoice"])
        session.queue_rules_simultaneous_actions(actions)
        self.assertIsNone(session.rules_engine["pendingChoice"])
        resolved = session.resolve_rules_immediate_actions()
        self.assertEqual(resolved[0]["action"]["ability"]["id"], "immediate-entry")
        self.assertEqual(session.find_battlefield_item("first-b")["counters"]["Echo"], 1)
        self.assertEqual(session.rules_engine["pendingChoice"]["kind"], "trigger_targets")

    def test_multicastigate_spends_the_surplus_of_the_tribute_for_its_second_target(self):
        for tributes, powers in [(["m-5"], [5]), (["m-2", "m-3"], [2, 3])]:
            with self.subTest(tributes=tributes):
                session, p1, _ = self.started()
                self.put(p1, "hand", [self.MULTI, *tributes])
                for card_id, power in zip(tributes, powers):
                    session.card_rules[card_id]["power"] = power
                session.battlefield = [self.field_item("support-a", "p2", "m-7", isSupport=True), self.field_item("support-b", "p2", "m-8", isSupport=True)]
                error, action = session.declare_rules_action("p1", "Multicastigate", kind="play_card", source={"zone": "hand", "cardId": self.MULTI}, ability_id="destroy-one-or-two-support-manifestations", payment_card_ids=tributes, targets=[{"kind": "card", "itemId": key, "cardId": card} for key, card in [("support-a", "m-7"), ("support-b", "m-8")]])
                self.assertIsNone(error)
                self.assertEqual(action["cost"]["excessEssence"], [])
                session.resolve_rules_top_action()
                self.assertFalse(session.battlefield)

    def test_obelisk_triggers_only_at_reaction_and_gift_is_chosen_on_resolution(self):
        session, p1, p2 = self.started("confrontation_immediate")
        self.put(p1, "hand", ["m-9"])
        session.battlefield.append(self.field_item("obelisk", "p1", self.OBELISK, "field"))
        self.assertFalse(session.queue_rules_revelation_triggers(defer=True))
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
        session.queue_rules_reaction_triggers()
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "optional_stack_action")
        session.resolve_rules_choice("p1", choice["id"], option="accept")
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertEqual(len(session.rules_engine["actionStack"]), 1)
        self.assertIn("m-9", p1["zones"]["hand"])
        # The opponent responds before any gift has been selected.
        self.put(p2, "hand", [self.OPPRESS])
        session.add_rules_excess_essence("p2", [{"temperament": "choleric", "amount": 2}])
        error, _ = session.declare_rules_action("p2", "Respond to Obelisk", kind="play_card", source={"zone": "hand", "cardId": self.OPPRESS}, ability_id="oppress-power-modifier", targets=[{"kind": "card", "itemId": "first-b", "cardId": "m-2"}])
        self.assertIsNone(error)
        self.assertEqual(len(session.rules_engine["actionStack"]), 2)
        self.assertIsNone(session.rules_engine["pendingChoice"])
        session.resolve_rules_top_action()
        self.assertIsNone(session.rules_engine["pendingChoice"])
        session.resolve_rules_top_action()
        self.assertEqual(session.rules_engine["pendingChoice"]["destination"], "obelisk_gift")
        # While that resolution waits for a gift, neither player gets a new
        # response window between the exchange's choices.
        error, _ = session.declare_rules_action("p1", "Interrupt gift", kind="play_card", source={"zone": "hand", "cardId": self.OPPRESS})
        self.assertEqual(error, "A required card choice must be completed first.")

    def test_obelisk_controller_can_decline_before_it_enters_the_stack(self):
        session, p1, _ = self.started()
        self.put(p1, "hand", ["m-9"])
        session.battlefield.append(self.field_item("obelisk", "p1", self.OBELISK, "field"))
        session.queue_rules_reaction_triggers()
        choice = session.rules_engine["pendingChoice"]
        error, _ = session.resolve_rules_choice("p1", choice["id"], option="decline")
        self.assertIsNone(error)
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertFalse(session.rules_engine["actionStack"])
        self.assertIn("m-9", p1["zones"]["hand"])

    def test_multicastigate_combines_floating_white_essence_and_tribute(self):
        for floating, tribute in [(5, []), (1, ["m-4"])]:
            with self.subTest(floating=floating):
                session, p1, _ = self.started()
                self.put(p1, "hand", [self.MULTI, *tribute])
                session.card_rules["m-4"]["power"] = 4
                session.battlefield = [self.field_item("a", "p2", "m-7", isSupport=True), self.field_item("b", "p2", "m-8", isSupport=True)]
                session.add_rules_excess_essence("p1", [{"temperament": "transcendent", "amount": floating}])
                error, action = session.declare_rules_action("p1", "Multicastigate", kind="play_card", source={"zone": "hand", "cardId": self.MULTI}, ability_id="destroy-one-or-two-support-manifestations", payment_card_ids=tribute, transcendent_payment={"hollow": floating}, targets=[{"kind": "card", "itemId": key, "cardId": card} for key, card in [("a", "m-7"), ("b", "m-8")]])
                self.assertIsNone(error)
                self.assertEqual(sum(entry["amount"] for entry in action["cost"]["essenceSpent"]), floating)
                self.assertEqual(action["cost"]["excessEssence"], [])

    def test_interzone_support_remains_visible_until_its_movement_resolves(self):
        for cancelled in [False, True]:
            with self.subTest(cancelled=cancelled):
                session, p1, _ = self.started()
                session.card_rules["m-5"]["supportFromInterzone"] = True
                item = self.field_item("support", "p1", "m-5", "interzone")
                session.battlefield.append(item)
                error, action = session.declare_rules_action("p1", "Enter Support", kind="play_card", source={"zone": "battlefield", "itemId": "support", "cardId": "m-5"}, as_support=True)
                self.assertIsNone(error)
                self.assertIn(item, session.battlefield)
                self.assertEqual(item["fieldZone"], "interzone")
                self.assertEqual(item["pendingSupportActionId"], action["id"])
                self.assertFalse(action["sourceOnStack"])
                self.assertTrue(session.rules_stack_target_matches(action, "stack_effect"))
                if cancelled:
                    session.counter_rules_stack_action(action, "cancel")
                    self.assertEqual(item["fieldZone"], "interzone")
                    self.assertNotIn("m-5", p1["zones"]["graveyard"])
                else:
                    session.resolve_rules_top_action()
                    self.assertEqual(item["fieldZone"], "confrontation")
                    self.assertTrue(item["isSupport"])
                    self.assertEqual(sum(entry["id"] == "support" for entry in session.battlefield), 1)
                self.assertNotIn("pendingSupportActionId", item)

    def test_support_destroyed_in_response_is_not_resurrected(self):
        session, _, _ = self.started()
        session.card_rules["m-5"]["supportFromInterzone"] = True
        item = self.field_item("support", "p1", "m-5", "interzone")
        session.battlefield.append(item)
        error, _action = session.declare_rules_action("p1", "Enter Support", kind="play_card", source={"zone": "battlefield", "itemId": "support", "cardId": "m-5"}, as_support=True)
        self.assertIsNone(error)
        session.battlefield.remove(item)
        session.resolve_rules_top_action()
        self.assertIsNone(session.find_battlefield_item("support"))

    def test_gems_are_optional_and_last_gem_exiles_splendor(self):
        session, p1, _ = self.started()
        self.put(p1, "hand", [self.OPPRESS])
        item = self.field_item("splendor", "p1", self.SPLENDOR, "field", counters={"Gem": 2}, chosenTemperament="choleric")
        session.battlefield.append(item)
        self.assertTrue(session.rules_will_affordable("p1", self.OPPRESS))
        self.assertEqual(session.tokens, [])
        ability_id = "splendor-spends-a-gem-as-excess-essence"
        error, _ = session.spend_rules_counter_essence("p2", item["id"], ability_id)
        self.assertIsNotNone(error)
        self.assertEqual(item["counters"]["Gem"], 2)
        for remaining in [1, 0]:
            error, result = session.spend_rules_counter_essence("p1", item["id"], ability_id)
            self.assertIsNone(error)
            self.assertEqual(result["amount"], 1)
            self.assertEqual(item["counters"].get("Gem", 0), remaining)
        self.assertIn(self.SPLENDOR, p1["zones"]["exile"])
        self.assertEqual(sum(token["counters"]["essence"] for token in session.tokens), 2)
        self.assertFalse(session.rules_engine["actionStack"])
        error, _ = session.declare_rules_action("p1", "Oppress", kind="play_card", source={"zone": "hand", "cardId": self.OPPRESS}, ability_id="oppress-power-modifier", targets=[{"kind": "card", "itemId": "first-b", "cardId": "m-2"}])
        self.assertIsNone(error)

    def test_suspension_preserves_hidden_information(self):
        session, _, _ = self.started()
        for item in session.battlefield:
            item.update(x=0, y=0, rotation=0)
        session.rules_engine["suspendedCards"] = [
            {"id": "visible", "cardId": "m-5", "ownerId": "p1", "fromContainerId": "p1", "fromZone": "battlefield"},
            {"id": "hidden", "cardId": self.OPPRESS, "ownerId": "p1", "fromContainerId": "p1", "fromZone": "hand"},
        ]
        view = session.serialize_for("p2", "player")["rulesEngine"]["suspendedCards"]
        self.assertEqual(view[0]["cardId"], "m-5")
        self.assertIsNone(view[1]["cardId"])


if __name__ == "__main__":
    unittest.main()
