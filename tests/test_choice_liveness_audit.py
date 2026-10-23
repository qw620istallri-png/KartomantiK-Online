"""Choices must offer an exit without weakening legal targets or payments."""
import copy

import test_game_state as game_tests
import test_stack_target_audit as target_tests


class ChoiceLivenessAuditTests(game_tests.RealCardRulesCase):
    MIRROR = "72zvsiuky5ytolh_en"
    IMITATE = "q6rha5kz42bkxle_en"
    JU_LIEN = "qapv47r7rz6gqah_en"
    ZOMBIE = "bu1y6jwy7iaywqu_en"
    MACABRE = "inner-deserts-115"
    KANON = "inner-deserts-064"
    JIGON = "z6awx4mwwkfrvdd_en"
    RECALL = "cnqaie6oq458qgq_en"
    BULLYBOO = "gz2zjrxqc2rbcwq_en"
    SPLENDOR = "inner-deserts-143"
    MULTICASTIGATE = "inner-deserts-138"
    ALL = (MIRROR, IMITATE, JU_LIEN, ZOMBIE, MACABRE, KANON, JIGON, RECALL, BULLYBOO, SPLENDOR, MULTICASTIGATE)
    started = target_tests.StackTargetAuditTests.started
    target = staticmethod(target_tests.StackTargetAuditTests.target)
    spell = target_tests.StackTargetAuditTests.spell
    protect = target_tests.StackTargetAuditTests.protect

    def copy_choice(self, session, original):
        result = session.apply_rules_action_result({"id": "imitate", "controllerId": "p1",
            "source": {"cardId": self.IMITATE},
            "targets": [{"kind": "stack_action", "actionId": original["id"]}],
            "ability": self.ABILITIES[self.IMITATE][0]})
        self.assertEqual(result["kind"], "choice_required")
        return session.rules_engine["pendingChoice"]

    def test_copy_can_keep_inherited_targets_even_when_none_are_legal_for_new_controller(self):
        for invalidation in ("controller", "missing", "protected"):
            with self.subTest(invalidation=invalidation):
                session, p1, _, first, _ = self.started()
                original = self.spell(session, self.MIRROR, [first])
                original.update(controllerId="p2")
                original["source"]["ownerId"] = "p2"
                choice = self.copy_choice(session, original)
                if invalidation == "missing":
                    session.battlefield.remove(first)
                elif invalidation == "protected":
                    first["controllerId"] = "p1"
                    self.protect(session, first)
                error, _ = session.resolve_rules_choice("p1", choice["id"], option="keep",
                    targets=[{"kind": "card", "itemId": "forged"}])
                self.assertIsNone(error)
                self.assertIsNone(session.rules_engine["pendingChoice"])
                copied = session.rules_engine["actionStack"][-1]
                self.assertEqual(copied["targets"], original["targets"])
                self.assertTrue(session.rules_top_action_has_no_valid_targets())
                session.resolve_rules_top_action()
                self.assertEqual(copied["effectResult"]["kind"], "invalid_targets")
                self.assertEqual(session.rules_engine["actionStack"], [original])
                self.assertEqual(p1["zones"]["graveyard"], [])

    def test_new_copy_targets_still_require_legal_targets_and_refusal_is_atomic(self):
        session, _, _, first, _ = self.started()
        original = self.spell(session, self.MIRROR, [first])
        choice = self.copy_choice(session, original)
        before = copy.deepcopy(session.rules_engine)
        error, _ = session.resolve_rules_choice("p1", choice["id"], option="retarget", targets=[self.target(first)])
        self.assertIsNotNone(error)
        self.assertEqual(session.rules_engine, before)
        first["controllerId"] = "p1"
        error, _ = session.resolve_rules_choice("p1", choice["id"], option="retarget", targets=[self.target(first)])
        self.assertIsNone(error)
        session.resolve_rules_top_action()
        self.assertTrue(any(item.get("isCopy") and item["ownerId"] == "p1" for item in session.battlefield))

    def test_inherited_multitarget_copy_still_resolves_its_remaining_valid_target(self):
        session, _, _, first, second = self.started()
        original = self.spell(session, self.MULTICASTIGATE, [first, second])
        choice = self.copy_choice(session, original)
        self.protect(session, first)
        error, _ = session.resolve_rules_choice("p1", choice["id"], option="keep")
        self.assertIsNone(error)
        session.resolve_rules_top_action()
        self.assertIs(session.find_battlefield_item("first"), first)
        self.assertIsNone(session.find_battlefield_item("second"))

    def ju_lien_action(self, session):
        return {"id": "ju-lien", "controllerId": "p1", "optional": True, "optionalAccepted": True,
            "source": {"cardId": self.JU_LIEN}, "ability": self.ABILITIES[self.JU_LIEN][0]}

    def test_ju_lien_does_not_open_an_impossible_support_choice_after_a_lock_resolves(self):
        session, p1, _, _, _ = self.started()
        self.put(p1, "hand", [self.SPLENDOR])
        session.rules_engine["supportLocks"] = [{"turn": session.phase_tracker["turn"], "playerId": "p1"}]
        result = session.apply_rules_action_result(self.ju_lien_action(session))
        self.assertEqual(result["status"], "prevented")
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertEqual(p1["zones"]["hand"], [self.SPLENDOR])
        action = self.ju_lien_action(session)
        action.pop("optionalAccepted")
        self.assertFalse(session.rules_optional_trigger_available(action))

    def test_ju_lien_still_resolves_with_an_open_support_slot(self):
        session, p1, _, _, _ = self.started()
        self.put(p1, "hand", [self.SPLENDOR])
        session.apply_rules_action_result(self.ju_lien_action(session))
        choice = session.rules_engine["pendingChoice"]
        error, _ = session.resolve_rules_choice("p1", choice["id"], card_ids=[self.SPLENDOR])
        self.assertIsNone(error)
        self.assertEqual(p1["zones"]["hand"], [])
        self.assertTrue(any(item.get("willManifestation") for item in session.battlefield))

    def test_immediate_limbo_exile_drops_deferred_zombie_prompt_and_preserves_the_next_effect(self):
        session, p1, _, _, _ = self.started()
        self.put(p1, "graveyard", [self.ZOMBIE, "m-2"])
        queued = session.queue_rules_triggers(self.ZOMBIE, "p1", "enters_limbo", defer=True)
        self.assertTrue(queued[0].get("_preStackTargetChoice"))
        immediate = {"id": "macabre", "controllerId": "p2", "kind": "play_card", "immediate": True,
            "source": {"cardId": self.MACABRE}, "ability": self.ABILITIES[self.MACABRE][0], "targets": []}
        next_action = {"id": "next", "controllerId": "p1", "source": {}, "ability": {"id": "next"}}
        session.queue_rules_simultaneous_actions([*queued, next_action, immediate])
        session.resolve_rules_immediate_actions()
        self.assertEqual(p1["zones"]["graveyard"], [])
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertEqual([a["id"] for a in session.rules_engine["actionStack"]], ["next"])

    def test_mandatory_deferred_target_choice_is_rechecked_before_it_opens(self):
        session, _, _, first, _ = self.started()
        contract = {"min": 1, "max": 1, "cardType": "manifestation", "sourceOnly": True}
        action = {"id": "deferred", "controllerId": "p1", "source": {"itemId": "first"},
            "ability": {"id": "deferred", "targets": contract},
            "_preStackTargetChoice": {"targetRules": contract}}
        self.protect(session, first)
        session.queue_rules_simultaneous_actions([action])
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertEqual(session.rules_engine["actionStack"], [])

    def test_skipped_deferred_target_resumes_cleanup_after_other_choices_finish(self):
        session, _, _, first, second = self.started()
        contract = {"min": 1, "max": 1, "cardType": "manifestation", "sourceOnly": True}
        skipped = {"id": "deferred", "controllerId": "p1", "source": {"itemId": "first"},
            "ability": {"id": "deferred", "targets": contract},
            "_preStackTargetChoice": {"targetRules": contract, "resumeConfrontationCleanup": True}}
        optional = {"id": "optional", "controllerId": "p1", "optional": True, "source": {},
            "ability": {"id": "optional"}}
        self.protect(session, first)
        session.rules_engine["confrontationResult"] = {"winnerId": "p2", "pendingOwnItemIds": ["second"]}
        session.queue_rules_simultaneous_actions([skipped, optional])
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "optional_stack_action")
        error, _ = session.resolve_rules_choice("p1", choice["id"], option="decline")
        self.assertIsNone(error)
        cleanup = session.rules_engine["pendingChoice"]
        self.assertEqual(cleanup["kind"], "confrontation_destination")
        self.assertEqual(cleanup["itemId"], second["id"])
        self.assertNotIn("resumeConfrontationCleanupAfterChoices", session.rules_engine)

    def test_empty_searches_finish_without_a_card_picker(self):
        for card_id, deck in ((self.RECALL, []), (self.JIGON, []), (self.JIGON, ["m-2", "m-3"])):
            with self.subTest(card_id=card_id, deck=deck):
                session, p1, _, _, _ = self.started()
                self.put(p1, "deck", deck)
                result = session.apply_rules_action_result({"id": "search", "controllerId": "p1",
                    "source": {"cardId": card_id}, "ability": self.ABILITIES[card_id][0]})
                self.assertEqual(result["status"], "no_cards")
                self.assertIsNone(session.rules_engine["pendingChoice"])

    def test_nonempty_search_with_only_one_eligible_will_remains_completable(self):
        session, p1, _, _, _ = self.started()
        self.put(p1, "deck", ["m-2", self.SPLENDOR])
        session.apply_rules_action_result({"id": "search", "controllerId": "p1",
            "source": {"cardId": self.JIGON, "itemId": "jigon"}, "ability": self.ABILITIES[self.JIGON][0]})
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["candidateCardIds"], [self.SPLENDOR])
        error, _ = session.resolve_rules_choice("p1", choice["id"], card_ids=[self.SPLENDOR])
        self.assertIsNone(error)
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertTrue(any(item.get("concealedWill") for item in session.battlefield))

    def test_bullyboo_affordability_sees_the_eighth_manifestation_and_all_white_allocations(self):
        session, _, p2, _, _ = self.started()
        for index in range(7):
            session.card_rules[f"m-{index}"].update(power=1, temperaments=["choleric"])
        session.card_rules["m-7"].update(power=2, temperaments=["vitreous"])
        self.put(p2, "hand", [f"m-{index}" for index in range(8)])
        self.assertTrue(session.rules_can_afford_tribute("p2", "{B}{B}"))
        session.add_rules_excess_essence("p2", [{"temperament": "transcendent", "amount": 1}])
        self.put(p2, "hand", ["m-7"])
        session.card_rules["m-7"]["power"] = 1
        self.assertTrue(session.rules_can_afford_tribute("p2", "{B}{R}"))

    def test_bullyboo_cannot_pay_takes_the_fallback_without_a_mandatory_payment_prompt(self):
        session, p1, p2, _, _ = self.started()
        self.put(p1, "hand", [self.IMITATE])
        self.put(p2, "hand", [])
        session.rules_engine["pendingChoice"] = {"id": "reveal", "kind": "discard_from_hand", "playerId": "p1",
            "count": 1, "destination": "bullyboo_reveal", "chooserId": "p2", "sourceCardId": self.BULLYBOO}
        before_score = p2["score"]
        error, result = session.resolve_rules_choice("p1", "reveal", card_ids=[self.IMITATE])
        self.assertIsNone(error)
        self.assertEqual(result["status"], "cannot_pay")
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertEqual(before_score - p2["score"], 10)
        self.assertIn(self.IMITATE, p1["zones"]["graveyard"])

    def test_all_effect_payment_choices_accept_explicit_white_allocation_atomically(self):
        for kind in ("effect_payment", "effect_memory_payment", "stack_counter_payment", "immediate_effect_payment"):
            with self.subTest(kind=kind):
                session, p1, p2, first, _ = self.started()
                self.put(p1, "hand", ["m-7"])
                session.card_rules["m-7"].update(power=1, temperaments=["vitreous"])
                session.add_rules_excess_essence("p1", [{"temperament": "transcendent", "amount": 1}])
                choice = {"id": "payment", "kind": kind, "playerId": "p1", "payment": "{B}{R}",
                    "sourceCardId": self.BULLYBOO, "controllerId": "p2", "onDecline": {}}
                if kind == "effect_memory_payment":
                    self.put(p2, "graveyard", [self.IMITATE])
                    memory = session.create_rules_effect_memory("p2", self.IMITATE, "return_from_limbo_end_turn")
                    choice["memoryId"] = memory["id"]
                if kind == "stack_counter_payment":
                    original = self.spell(session, self.MIRROR, [first])
                    choice.update(targetActionId=original["id"], targetKind="stack_action", mode="cancel")
                session.rules_engine["pendingChoice"] = choice
                before = copy.deepcopy((session.players, session.tokens, session.rules_engine))
                error, _ = session.resolve_rules_choice("p1", "payment", option="pay", card_ids=["m-7"],
                    transcendent_payment={"vitreous": 1})
                self.assertIsNotNone(error)
                self.assertEqual((session.players, session.tokens, session.rules_engine), before)
                error, result = session.resolve_rules_choice("p1", "payment", option="pay", card_ids=["m-7"],
                    transcendent_payment={"choleric": 1})
                self.assertIsNone(error)
                self.assertEqual(result["status"], "paid")
                self.assertEqual(p1["zones"]["hand"], [])
                self.assertIsNone(session.rules_engine["pendingChoice"])
                self.assertFalse(any(token.get("isEssence") and token["ownerId"] == "p1" for token in session.tokens))

    def test_bullyboo_required_payment_can_finish_with_alternate_white_allocation(self):
        session, p1, p2, _, _ = self.started()
        self.put(p1, "hand", [self.IMITATE])
        session.card_rules[self.IMITATE]["powerCost"] = "{B}{R}"
        self.put(p2, "hand", ["m-7"])
        session.card_rules["m-7"].update(power=1, temperaments=["vitreous"])
        session.add_rules_excess_essence("p2", [{"temperament": "transcendent", "amount": 1}])
        session.rules_engine["pendingChoice"] = {"id": "reveal", "kind": "discard_from_hand", "playerId": "p1",
            "count": 1, "destination": "bullyboo_reveal", "chooserId": "p2", "sourceCardId": self.BULLYBOO}
        error, result = session.resolve_rules_choice("p1", "reveal", card_ids=[self.IMITATE])
        self.assertIsNone(error)
        self.assertEqual(result["status"], "payment_required")
        choice = session.rules_engine["pendingChoice"]
        error, result = session.resolve_rules_choice("p2", choice["id"], option="pay", card_ids=["m-7"],
            transcendent_payment={"choleric": 1})
        self.assertIsNone(error)
        self.assertEqual(result["status"], "paid")
        self.assertIsNone(session.rules_engine["pendingChoice"])
        self.assertEqual(p2["zones"]["hand"], [])

    def test_kanon_followup_only_offers_legal_field_manifestations(self):
        session, _, p2, first, second = self.started()
        kanon = self.field_item("kanon", "p1", self.KANON, "interzone")
        token_will = self.field_item("will-token", "p2", self.SPLENDOR, "field", isTokenCard=True, isCopy=True)
        session.battlefield.extend([kanon, token_will])
        self.protect(session, first)
        second["fieldZone"] = "stalemate"
        self.put(p2, "deck", [self.IMITATE])
        session.request_rules_draw("p2", 1, "p2")
        choice = session.rules_engine["pendingChoice"]
        error, _ = session.resolve_rules_choice("p2", choice["id"], card_ids=[self.IMITATE])
        self.assertIsNone(error)
        self.assertIsNone(session.rules_engine["pendingChoice"])

    def test_kanon_legal_distribution_remains_retryable_after_an_invalid_target(self):
        session, _, p2, first, second = self.started()
        session.battlefield.append(self.field_item("kanon", "p1", self.KANON, "interzone"))
        self.protect(session, first)
        self.put(p2, "deck", [self.IMITATE])
        session.request_rules_draw("p2", 1, "p2")
        error, _ = session.resolve_rules_choice("p2", session.rules_engine["pendingChoice"]["id"], card_ids=[self.IMITATE])
        self.assertIsNone(error)
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["candidateItemIds"], ["second"])
        before = copy.deepcopy(session.rules_engine)
        error, _ = session.resolve_rules_choice("p1", choice["id"], option={"itemIds": ["first"]})
        self.assertIsNotNone(error)
        self.assertEqual(session.rules_engine, before)
        error, _ = session.resolve_rules_choice("p1", choice["id"], option={"itemIds": ["second"]})
        self.assertIsNone(error)
        self.assertEqual(self.power_of(session, "second"), 5)
        self.assertIsNone(session.rules_engine["pendingChoice"])
