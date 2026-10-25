"""Availability must agree with declaration gates and each recipient's targeting rights."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import card_scenario_batches as batches


class RulesAvailabilityTests(unittest.TestCase):
    def prepared(self, card_id, ability_id):
        ability = next(entry for entry in batches.main.CARD_ABILITIES[card_id] if entry["id"] == ability_id)
        session, actor, source, targets, _cost = batches.prepare_action(card_id, ability)
        return session, actor, source, ability

    def test_zum_usage_is_unavailable_until_the_next_turn(self):
        session, actor, source, ability = self.prepared("282b0n6ldnzdp0p_en", "zum-draw")
        item = session.find_battlefield_item(source["itemId"])
        item["abilityTurnUses"] = {ability["id"]: session.phase_tracker["turn"]}
        self.assertFalse(session.rules_field_ability_usable(item, ability, "confrontation", session.current_phase_id()))
        view = session.serialize_for(actor, "player")
        self.assertNotIn(ability["id"], next(entry for entry in view["battlefield"] if entry["id"] == item["id"])["usableAbilityIds"])
        session.phase_tracker["turn"] += 1
        self.assertTrue(session.rules_field_ability_usable(item, ability, "confrontation", session.current_phase_id()))

    def test_jija_needs_its_own_controlled_token(self):
        session, actor, source, ability = self.prepared("02y2r5cvbw1mauv_en", "sacrifice-created-token-for-power-loss")
        item = session.find_battlefield_item(source["itemId"])
        token = session.find_battlefield_item("source-token")
        self.assertTrue(session.rules_field_ability_usable(item, ability, "confrontation", session.current_phase_id()))
        token["createdByItemId"] = "someone-else"
        self.assertFalse(session.rules_field_ability_usable(item, ability, "confrontation", session.current_phase_id()))
        token["createdByItemId"] = item["id"]
        token["controllerId"] = "p2"
        self.assertFalse(session.rules_field_ability_usable(item, ability, "confrontation", session.current_phase_id()))

    def test_chabak_hand_gate_updates_the_server_hint(self):
        session, actor, source, ability = self.prepared("inner-deserts-084", "chabak-plays-in-support-for-two-manifestations")
        self.assertIn(source["cardId"], session.rules_usable_hand_ability_card_ids(actor))
        session.players[actor]["zones"]["hand"] = [source["cardId"]]
        self.assertNotIn(source["cardId"], session.rules_usable_hand_ability_card_ids(actor))

    def test_opponents_paid_ability_preserves_priority(self):
        card_id, abilities = next((cid, abilities) for cid, abilities in batches.main.CARD_ABILITIES.items()
                                  if any(entry.get("opponentOnly") for entry in abilities))
        ability = next(entry for entry in abilities if entry.get("opponentOnly"))
        session, actor, source, _targets, _cost = batches.prepare_action(card_id, ability)
        item = session.find_battlefield_item(source["itemId"])
        session.battlefield = [item]
        session.players[actor]["zones"]["hand"] = []
        self.assertNotEqual(actor, session.rules_item_controller_id(item))
        self.assertTrue(session.rules_player_can_act(actor))
        session.tokens = []
        self.assertFalse(session.rules_player_can_act(actor))

    def test_tribute_search_keeps_the_thirteenth_candidate_and_reserves_source(self):
        session, actor, source, ability = self.prepared("282b0n6ldnzdp0p_en", "zum-draw")
        session.battlefield = []
        session.tokens = []
        for index in range(12):
            session.card_rules[f"red-{index}"] = {"type": "manifestation", "power": 1, "temperaments": ["choleric"]}
        session.card_rules["green-last"] = {"type": "manifestation", "power": 5, "temperaments": ["phlegmatic"]}
        hand = session.players[actor]["zones"]["hand"] = [f"red-{index}" for index in range(12)] + ["green-last"]
        self.assertTrue(session.rules_requirements_affordable(actor, {"phlegmatic": 5}))
        self.assertFalse(session.rules_requirements_affordable(actor, {"phlegmatic": 5}, "green-last"))
        hand.append("green-last")
        self.assertTrue(session.rules_requirements_affordable(actor, {"phlegmatic": 5}, "green-last"))

    def test_target_rights_are_viewer_specific_and_hidden_cards_stay_private(self):
        session, actor, source, ability = self.prepared("282b0n6ldnzdp0p_en", "zum-weaken")
        session.rules_engine["ongoingEffects"] = [{"kind": "protection", "duration": "end_of_turn",
                                                  "fromOpponents": True, "target": {"itemId": "own-con"}}]
        hidden = session.find_battlefield_item("own-inter")
        hidden["faceUp"] = False
        for viewer, targetable in (("p1", True), ("p2", False)):
            view = {entry["id"]: entry for entry in session.serialize_for(viewer, "player")["battlefield"]}
            self.assertEqual(view["own-con"]["effectTargetable"], targetable)
            self.assertNotIn("usableAbilityIds", view["own-inter"])
            self.assertNotIn("effectTargetable", view["own-inter"])
        self.assertIsNone(next(entry for entry in session.serialize_for("p2", "player")["battlefield"] if entry["id"] == hidden["id"])["cardId"])

    def test_field_source_does_not_reserve_another_copy_in_hand(self):
        session, actor, source, ability = self.prepared("282b0n6ldnzdp0p_en", "zum-draw")
        session.tokens = []
        session.players[actor]["zones"]["hand"] = [source["cardId"]]
        field_ability = {"id": "copy-pays", "tribute": "{H}", "targets": {"min": 0, "max": 0}}
        self.assertFalse(session.rules_ability_clearly_unusable(actor, field_ability, session.current_phase_id(), source["cardId"], source["itemId"]))
        self.assertTrue(session.rules_ability_clearly_unusable(actor, field_ability, session.current_phase_id(), source["cardId"]))

    def test_retarget_rights_use_the_original_effect_controller_without_mutation(self):
        session, actor, source, ability = self.prepared("z2gm0fc6fxlnsb1_en", "beacon-changes-a-target")
        action = session.rules_engine["actionStack"][0]
        session.rules_engine["ongoingEffects"] = [{"kind": "protection", "duration": "end_of_turn",
                                                  "fromOpponents": True, "target": {"itemId": "own-con"}}]
        view = session.rules_stack_action_for_view(action, "p1", "player")
        self.assertFalse(session.rules_item_is_protected(session.find_battlefield_item("own-con"), "p1"))
        self.assertNotIn("own-con", view["retargetableItemIds"])
        self.assertNotIn("retargetableItemIds", action)


if __name__ == "__main__":
    unittest.main()
