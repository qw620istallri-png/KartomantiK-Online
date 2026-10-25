"""Current First Manifestation references, under the creator's 2026-10-24 ruling."""
import copy
import unittest

import test_game_state as game
import test_departure_resolution_audit as departures


class FirstReferenceAuditTests(game.RealCardRulesCase):
    LOMBRIC = "inner-deserts-014"
    PACHY = "9ypw4x4igfon1qi_en"
    MIMER = departures.DepartureResolutionAuditTests.MIMER
    BOLBA = departures.DepartureResolutionAuditTests.BOLBA
    MAMELATH = "inner-deserts-017"
    HOURGLASS = "lmx5uff1z53fo0g_en"
    ALL = (LOMBRIC, PACHY, MIMER, BOLBA, MAMELATH, HOURGLASS)
    def started(self):
        result = departures.DepartureResolutionAuditTests.started(self)
        for item in result[0].battlefield:
            item.update(x=500, y=300, rotation=0, stackedOn=None)
        return result
    target = staticmethod(departures.DepartureResolutionAuditTests.target)
    declare = departures.DepartureResolutionAuditTests.declare

    def queued_win(self, session, cid, mine):
        mine.update(cardId=cid, counters={"power": 5}, confrontationOrder=1)
        queued = session.queue_rules_triggers(cid, "p1", "wins_confrontation", item_id=mine["id"],
            event_controller_id="p1", target_player_id="p2", defer=True)
        self.assertEqual(len(queued), 1)
        return queued

    def support(self, session, iid="next", order=2, power=3, zone="confrontation"):
        session.card_rules["m-2"]["power"] = power
        item = self.field_item(iid, "p2", "m-2", zone)
        item.update(isSupport=True, confrontationOrder=order, x=500, y=300, rotation=0, stackedOn=None)
        session.battlefield.append(item)
        return item

    def test_empty_opponent_compares_against_zero_even_when_both_original_cards_leave(self):
        for cid in (self.LOMBRIC, self.PACHY):
            for source_leaves in (False, True):
                for zone in ("hand", "graveyard", "exile", "receptacle"):
                    with self.subTest(card=cid, sourceLeaves=source_leaves, destination=zone):
                        session, p1, p2, mine, foe = self.started()
                        queued = self.queued_win(session, cid, mine)
                        session._rules_remove_field_item_by_effect(foe, "p2", zone)
                        if source_leaves:
                            session._rules_remove_field_item_by_effect(mine, "p1", "hand")
                        session.prune_rules_ongoing_effects()
                        session.rules_engine["actionStack"].extend(queued)
                        session.resolve_rules_top_action()
                        amount = 25 if source_leaves else 50
                        self.assertEqual((p1["score"], p2["score"]), (amount, 0) if cid == self.LOMBRIC else (0, -amount))

    def test_next_support_is_promoted_by_entry_order_and_its_current_power_is_read(self):
        for cid in (self.LOMBRIC, self.PACHY):
            with self.subTest(card=cid):
                session, p1, p2, mine, foe = self.started()
                queued = self.queued_win(session, cid, mine)
                self.support(session, "later", order=3)
                next_item = self.support(session, order=2)
                next_item["counters"]["power"] = 1  # current 4, printed 3
                session._rules_remove_field_item_by_effect(foe, "p2", "exile")
                session.prune_rules_ongoing_effects()
                self.assertEqual(session.rules_engine["firstManifestationItemIds"]["p2"], "next")
                self.assertTrue(next_item["isSupport"])  # entry properties are not replayed
                session.rules_engine["actionStack"].extend(queued)
                session.resolve_rules_top_action()
                self.assertEqual((p1["score"], p2["score"]), (30, 0) if cid == self.LOMBRIC else (0, -30))

    def test_retreat_promotes_but_interzone_stalemate_and_hidden_supports_do_not_qualify(self):
        session, _, _, _, foe = self.started()
        foe["fieldZone"] = "interzone"
        self.support(session, "interzone", zone="interzone")
        self.support(session, "stalemate", zone="stalemate")
        hidden = self.support(session, "hidden")
        hidden["faceUp"] = False
        session.prune_rules_ongoing_effects()
        self.assertNotIn("p2", session.rules_engine["firstManifestationItemIds"])
        revealed = self.support(session, "revealed", order=4)
        session.prune_rules_ongoing_effects()
        self.assertEqual(session.rules_engine["firstManifestationItemIds"]["p2"], revealed["id"])

    def test_mimer_old_target_fizzles_and_new_declaration_can_target_promoted_first(self):
        session, _, _, mine, foe = self.started()
        mine["cardId"] = self.MIMER
        next_item = self.support(session)
        self.declare(session, mine, "copy-first-manifestation", [self.target(foe)])
        session._rules_remove_field_item_by_effect(foe, "p2", "graveyard")
        session.prune_rules_ongoing_effects()
        session.resolve_rules_top_action()
        self.assertFalse(any(effect.get("kind") == "copy_power_temperament" for effect in session.rules_engine["ongoingEffects"]))
        session.rules_engine["priorityPlayerId"] = "p1"
        self.declare(session, mine, "copy-first-manifestation", [self.target(next_item)])
        session.resolve_rules_top_action()
        self.assertEqual(session.rules_manifestation_base_power(mine), 3)

    def test_promotion_is_public_without_replaying_entry_or_mutating_target_enumeration(self):
        session, _, _, _, foe = self.started()
        next_item = self.support(session)
        session._rules_remove_field_item_by_effect(foe, "p2", "graveyard")
        session.prune_rules_ongoing_effects()
        for viewer, role in (("p1", "player"), ("p2", "player"), (None, "observer")):
            self.assertEqual(session.serialize_for(viewer, role)["rulesEngine"]["firstManifestationItemIds"].get("p2"), next_item["id"])
        self.assertEqual(session.rules_engine["actionStack"], [])
        self.assertIsNone(session.rules_engine["pendingChoice"])
        before = copy.deepcopy(session.rules_engine)
        candidates = session.rules_legal_target_candidates({"kind": "card", "min": 1, "max": 1, "firstManifestationOnly": True}, "p1")
        self.assertIn(next_item["id"], [target.get("itemId") for target in candidates])
        self.assertEqual(session.rules_engine, before)

    def test_state_destruction_promotes_without_generating_a_new_entry_trigger(self):
        session, _, _, _, foe = self.started()
        self.support(session)
        foe["counters"]["power"] = -8
        result = session.resolve_rules_state_actions()
        self.assertEqual(len(result["destroyed"]), 1)
        self.assertEqual(session.rules_engine["firstManifestationItemIds"]["p2"], "next")
        self.assertEqual(result["triggeredActions"], [])
        self.assertEqual(session.rules_engine["actionStack"], [])

    def test_strict_base_comparison_uses_the_promoted_first_not_the_departed_one(self):
        session, _, _, mine, foe = self.started()
        next_item = self.support(session, power=5)
        mine["counters"]["power"] = 100  # comparison must still read base 4
        session._rules_remove_field_item_by_effect(foe, "p2", "exile")
        self.assertTrue(session.rules_is_strictly_highest_base_first(next_item))
        session.card_rules["m-2"]["power"] = 4
        self.assertFalse(session.rules_is_strictly_highest_base_first(next_item))

    def test_unrevealed_initial_selection_is_not_replaced_by_refresh(self):
        session, _, _, _, foe = self.started()
        session.rules_engine["firstManifestationComplete"] = False
        foe["faceUp"] = False
        self.support(session)
        session.prune_rules_ongoing_effects()
        self.assertEqual(session.rules_engine["firstManifestationItemIds"]["p2"], foe["id"])

    def test_mamelath_counts_modified_bases_of_the_moved_firsts_not_printed_values_or_bonuses(self):
        session, p1, _, mine, foe = self.started()
        session.card_rules["m-1"]["power"] = 3
        mine.update(baseDoublings=1, counters={"power": 2})  # base 8, current 10
        foe.update(baseDoublings=1, counters={"power": 7})  # base 6, current 13
        result = session._rules_result_first_manifestations_to_interzone_tokens(
            {"controllerId": "p1", "source": {"cardId": self.MAMELATH}},
            {"kind": "first_manifestations_to_interzone_tokens"}, "p1", p1)
        counts = {pid: sum(bool(item.get("isTokenCard")) and session.rules_item_controller_id(item) == pid
                          for item in session.battlefield) for pid in session.players}
        self.assertEqual(counts, {"p1": 8, "p2": 6})
        self.assertEqual((mine["fieldZone"], foe["fieldZone"]), ("interzone", "interzone"))

    def test_hourglass_compares_modified_base_power_and_excludes_additive_bonuses(self):
        for own_doubles, other_doubles, own_bonus, expects_choice in ((1, 0, 0, False), (1, 1, 0, True), (0, 0, 100, True)):
            with self.subTest(ownDoubles=own_doubles, otherDoubles=other_doubles, bonus=own_bonus):
                session, p1, _, mine, foe = self.started()
                mine.update(baseDoublings=own_doubles, counters={"power": own_bonus})
                foe["baseDoublings"] = other_doubles
                result = session._rules_result_stalemate_unless_opponent_pays(
                    {"id": "hourglass", "controllerId": "p1", "source": {"cardId": self.HOURGLASS}},
                    {"kind": "stalemate_unless_opponent_pays", "payment": "{H}{H}"}, "p1", p1)
                self.assertEqual(bool(session.rules_engine["pendingChoice"]), expects_choice)


if __name__ == "__main__":
    unittest.main()
