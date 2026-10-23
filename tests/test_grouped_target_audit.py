"""Grouped targets retain their roles from entry through partial resolution."""
import copy
from unittest.mock import patch

import test_game_state as game_tests


class GroupedTargetAuditTests(game_tests.RealCardRulesCase):
    KAOS = "b0amfkmb3xewx7x_en"
    KARMA = "9d2y8uy9ut7omyo_en"
    BEACON = "z2gm0fc6fxlnsb1_en"
    PACIPHINT = "inner-deserts-018"
    ALL = (KAOS, KARMA, BEACON, PACIPHINT)

    def started(self, card_id=KAOS):
        session, p1, p2 = self.make_session()
        session.phase_tracker["index"] = game_tests.ADVANCED_PHASES.index("confrontation_reaction")
        session.rules_engine.update(readyPlayerIds=["p1", "p2"], firstManifestationComplete=True, priorityPlayerId="p1")
        source = self.field_item("bro", "p1", card_id)
        mine = self.field_item("mine", "p1", "m-0")
        foe = self.field_item("foe", "p2", "m-1")
        session.battlefield = [source, mine, foe]
        return session, p1, p2, source, mine, foe

    @staticmethod
    def target(item):
        return {"kind": "card", "itemId": item["id"], "cardId": item["cardId"]}

    def test_bro_entry_preserves_groups_and_rejects_wrong_roles_without_mutation(self):
        for cid in (self.KAOS, self.KARMA):
            with self.subTest(cid=cid):
                session, _, _, source, mine, foe = self.started(cid)
                session.queue_rules_field_zone_entry_triggers(source, "confrontation")
                choice = session.rules_engine["pendingChoice"]
                self.assertEqual(choice["targetRules"]["groups"], self.ABILITIES[cid][0]["targets"]["groups"])
                before = copy.deepcopy(session.rules_engine)
                for selected in ([foe, mine], [mine, source]):
                    error, _ = session.resolve_rules_choice("p1", choice["id"], targets=[self.target(item) for item in selected])
                    self.assertIsNotNone(error)
                    self.assertEqual(session.rules_engine, before)
                error, _ = session.resolve_rules_choice("p1", choice["id"], targets=[self.target(mine), self.target(foe)])
                self.assertIsNone(error)
                action = session.rules_engine["actionStack"][-1]
                self.assertEqual(action["ability"]["targets"]["groups"], choice["targetRules"]["groups"])
                session.rules_engine["ongoingEffects"].append({"id": "wall", "kind": "protection",
                    "target": self.target(foe), "duration": "until_end_of_turn"})
                with patch("game.effects.dice.random.randint", return_value=1):
                    session.resolve_rules_top_action()
                self.assertEqual(action["invalidTargetIndices"], [1])
                self.assertIs(session.find_battlefield_item("foe"), foe)
                if cid == self.KAOS:
                    self.assertIsNone(session.find_battlefield_item("mine"))
                else:
                    self.assertEqual(session.players["p1"]["score"], 10)

    def test_bro_with_no_other_friendly_card_never_opens_an_impossible_group(self):
        session, _, _, source, mine, _ = self.started()
        session.battlefield.remove(mine)
        error = session.rules_trigger_target_error(self.KAOS, "enters_field_zone", controller_id="p1",
            event_item_id=source["id"], event_zone="confrontation")
        self.assertIsNone(error)
        queued = session.queue_rules_field_zone_entry_triggers(source, "confrontation")
        self.assertEqual(queued, [])
        self.assertIsNone(session.rules_engine["pendingChoice"])

    def test_group_availability_requires_distinct_targets_across_overlapping_groups(self):
        session, _, _, source, mine, foe = self.started()
        contract = {"groups": [{"min": 1, "max": 1, "cardType": "manifestation"}] * 2}
        session.battlefield = [mine]
        self.assertTrue(session.rules_trigger_has_no_legal_target(contract, "p1"))
        session.battlefield.append(foe)
        self.assertFalse(session.rules_trigger_has_no_legal_target(contract, "p1"))

    def test_beacon_group_requires_both_a_targeting_stack_item_and_a_field_card(self):
        session, _, _, _, mine, _ = self.started()
        contract = {"groups": self.ABILITIES[self.BEACON][1]["targetGroups"]}
        self.assertTrue(session.rules_trigger_has_no_legal_target(contract, "p1"))
        session.rules_engine["actionStack"] = [{"id": "targeting", "controllerId": "p2", "kind": "activated_effect",
            "source": {"cardId": "m-0"}, "targets": [self.target(mine)]}]
        self.assertFalse(session.rules_trigger_has_no_legal_target(contract, "p1"))
        session.battlefield = []
        self.assertTrue(session.rules_trigger_has_no_legal_target(contract, "p1"))

    def test_immune_opponent_player_does_not_leave_a_required_player_picker(self):
        session, _, _, _, mine, _ = self.started()
        session.card_rules["m-0"]["passiveEffects"] = [{"kind": "mutual_opponent_immunity"}]
        contract = {"kind": "player", "min": 1, "max": 1, "controller": "opponent"}
        self.assertTrue(session.rules_trigger_has_no_legal_target(contract, "p1"))
        mine["effectsDisabled"] = True
        self.assertFalse(session.rules_trigger_has_no_legal_target(contract, "p1"))

    def test_a_player_target_does_not_change_whose_private_hand_can_be_selected(self):
        session, p1, p2, _, _, _ = self.started()
        self.put(p1, "hand", ["m-2"])
        self.put(p2, "hand", ["m-3"])
        player = {"kind": "player", "playerId": "p2"}
        hand = {"kind": "zone_card", "containerId": "p1", "zone": "hand", "cardId": "m-2"}
        error, cleaned = session.rules_action_targets([player, hand], "p1")
        self.assertIsNone(error)
        self.assertEqual(cleaned[1]["containerId"], "p1")
        error, _ = session.rules_action_targets([player, {**hand, "containerId": "p2", "cardId": "m-3"}], "p1")
        self.assertIsNotNone(error)
