"""Rejected choices must leave the game intact and remain retryable."""
import copy
import unittest

import test_special_payments as special_payments


class ChoiceAtomicityTests(unittest.TestCase):
    case = special_payments.SpecialPaymentTests()

    def snapshot(self, session):
        return copy.deepcopy((session.players, session.battlefield, session.tokens,
                              session.rules_engine, session.phase_tracker))

    def dissect(self):
        session, p1, p2 = self.case.started()
        for item in session.battlefield:
            item.update(x=0, y=0, rotation=0, stackedOn=None)
        self.case.put(p1, "deck", ["m-0", "m-3", "m-4"])
        self.case.put(p2, "deck", ["m-5", "m-6", "m-7"])
        session.apply_rules_action_result({"controllerId": "p1", "source": {"cardId": "inner-deserts-047"},
            "ability": self.case.ABILITIES["inner-deserts-047"][0]})
        self.assertEqual(session.rules_engine["pendingChoice"]["kind"], "deck_reorder")
        return session, p1, p2

    def deck_option(self):
        return {"groups": [
            {"playerId": "p1", "top": ["m-3"], "bottom": ["m-4", "m-0"]},
            {"playerId": "p2", "top": ["m-6"], "bottom": ["m-7", "m-5"]}]}

    def reject_unchanged(self, session, **args):
        before = self.snapshot(session)
        choice_id = session.rules_engine["pendingChoice"]["id"]
        error, result = session.resolve_rules_choice("p1", choice_id, **args)
        self.assertIsNotNone(error)
        self.assertIsNone(result)
        self.assertEqual(self.snapshot(session), before)

    def test_second_deck_group_rejected_without_applying_the_first(self):
        for failure in ["unknown_card", "duplicate_group", "missing_card", "bad_shape"]:
            with self.subTest(failure=failure):
                session, _, p2 = self.dissect()
                option = self.deck_option()
                if failure == "unknown_card":
                    option["groups"][1]["top"] = ["not-in-deck"]
                elif failure == "duplicate_group":
                    option["groups"][1] = copy.deepcopy(option["groups"][0])
                elif failure == "missing_card":
                    p2["zones"]["deck"].remove("m-7")
                else:
                    option["groups"][1]["bottom"] = [None]
                self.reject_unchanged(session, option=option)

    def test_failed_transfer_does_not_remove_the_cards_being_reordered(self):
        session, _, _ = self.dissect()
        choice = session.rules_engine["pendingChoice"]
        choice["_groups"] = [{"playerId": "p2", "cardIds": ["m-5", "m-6", "m-7"],
            "extraSide": "hand", "extraMin": 1, "extraMax": 1}]
        self.reject_unchanged(session, option={"groups": [{"playerId": "p2",
            "top": ["m-6"], "bottom": ["m-5"], "extra": ["m-7"]}]})

    def test_valid_retry_after_rejection_and_duplicate_submission(self):
        session, p1, p2 = self.dissect()
        choice_id = session.rules_engine["pendingChoice"]["id"]
        invalid = self.deck_option()
        invalid["groups"][1]["top"] = []
        self.reject_unchanged(session, option=invalid)
        error, result = session.resolve_rules_choice("p1", choice_id, option=self.deck_option())
        self.assertIsNone(error)
        self.assertEqual(p1["zones"]["deck"], ["m-3", "m-4", "m-0"])
        self.assertEqual(p2["zones"]["deck"], ["m-6", "m-7", "m-5"])
        self.assertIsNone(session.rules_engine["pendingChoice"])
        after = self.snapshot(session)
        error, _ = session.resolve_rules_choice("p1", choice_id, option=self.deck_option())
        self.assertIsNotNone(error)
        self.assertEqual(self.snapshot(session), after)

    def test_wrong_player_or_obsolete_choice_id_cannot_change_current_choice(self):
        session, _, _ = self.dissect()
        current = session.rules_engine["pendingChoice"]["id"]
        for player, choice in [("p2", current), ("p1", "old-choice"), ("unknown", current)]:
            with self.subTest(player=player, choice=choice):
                before = self.snapshot(session)
                error, result = session.resolve_rules_choice(player, choice, option=self.deck_option())
                self.assertIsNotNone(error)
                self.assertIsNone(result)
                self.assertEqual(self.snapshot(session), before)

    def relocation(self):
        session, _, _ = self.case.started()
        session.rules_engine["pendingChoice"] = {"id": "relocate", "kind": "confrontation_relocation", "playerId": "p1",
            "_groups": [{"playerId": "p1", "itemIds": ["first-a"], "interzoneSlots": 3},
                        {"playerId": "p2", "itemIds": ["first-b"], "interzoneSlots": 3}]}
        return session

    def test_relocation_validates_all_groups_and_sources_before_moving(self):
        for failure in ["unknown_item", "missing_item", "changed_zone", "bad_shape"]:
            with self.subTest(failure=failure):
                session = self.relocation()
                option = {"groups": [{"playerId": "p1", "interzone": ["first-a"], "deckBottom": []},
                                     {"playerId": "p2", "interzone": ["first-b"], "deckBottom": []}]}
                if failure == "unknown_item":
                    option["groups"][1]["interzone"] = ["unknown"]
                elif failure == "missing_item":
                    session.battlefield.pop()
                elif failure == "changed_zone":
                    session.battlefield[1]["fieldZone"] = "interzone"
                else:
                    option["groups"][1]["interzone"] = [{}]
                self.reject_unchanged(session, option=option)

    def test_relocation_success_scores_and_ends_the_confrontation_once(self):
        session = self.relocation()
        option = {"groups": [{"playerId": "p1", "interzone": ["first-a"], "deckBottom": []},
                             {"playerId": "p2", "interzone": [], "deckBottom": ["first-b"]}]}
        error, result = session.resolve_rules_choice("p1", "relocate", option=option)
        self.assertIsNone(error)
        self.assertEqual(session.players["p2"]["score"], 50)
        self.assertEqual(session.current_phase_id(), "end_actions")
        self.assertEqual(session.battlefield[0]["fieldZone"], "interzone")
        after = self.snapshot(session)
        self.assertIsNotNone(session.resolve_rules_choice("p1", "relocate", option=option)[0])
        self.assertEqual(self.snapshot(session), after)

    def test_power_distribution_rejects_stale_target_without_partial_modifier(self):
        session, _, _ = self.case.started()
        session.rules_engine["pendingChoice"] = {"id": "loss", "kind": "power_loss_distribution", "playerId": "p1",
            "count": 2, "candidateItemIds": ["first-a", "gone"], "sourceCardId": "test-source"}
        self.reject_unchanged(session, option={"itemIds": ["first-a", "gone"]})

    def test_power_distribution_can_assign_multiple_losses_to_one_target(self):
        session, _, _ = self.case.started()
        session.rules_engine["pendingChoice"] = {"id": "loss", "kind": "power_loss_distribution", "playerId": "p1",
            "count": 2, "candidateItemIds": ["first-a"], "sourceCardId": "test-source"}
        error, result = session.resolve_rules_choice("p1", "loss", option={"itemIds": ["first-a", "first-a"]})
        self.assertIsNone(error)
        self.assertEqual(len(result["effectIds"]), 2)
        self.assertEqual(sum(e["value"] for e in session.rules_engine["ongoingEffects"]), -2)

    def test_snapshot_keeps_pending_choice_ready_for_reconnection(self):
        session, _, _ = self.dissect()
        before = self.snapshot(session)
        first = session.serialize_for("p1", "player")["rulesEngine"]["pendingChoice"]
        again = session.serialize_for("p1", "player")["rulesEngine"]["pendingChoice"]
        self.assertEqual(first, again)
        self.assertEqual(first["id"], session.rules_engine["pendingChoice"]["id"])
        self.assertEqual(len(first["groups"]), 2)
        self.assertNotIn("_groups", first)
        self.assertEqual(self.snapshot(session), before)
