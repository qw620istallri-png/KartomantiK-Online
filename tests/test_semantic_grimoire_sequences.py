"""Printed Grimoire clauses and the reported Sermon/Strengthen timeline."""
import copy
import unittest
import test_semantic_batch_001_150 as fixtures

main = fixtures.main


class GrimoireSequenceTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.SemanticBatch001150()
        self.s = self.f.world()
        self.host = self.f.field(self.s, self.f.cid("Grimoire"), zone="field")
        self.will = self.f.cid("Strengthen")
        self.f.put(self.s, "p1", "hand", [self.will, self.will, "m2"])

    def offer(self):
        self.s.apply_rules_action_result(self.f.action("Grimoire", self.host, ability_id="grimoire-places-hand-wills"))
        return self.s.rules_engine["pendingChoice"]

    def test_zero_one_or_duplicate_wills_are_placed_without_discard_events(self):
        for count in (0, 1, 2):
            with self.subTest(count=count):
                self.setUp()
                choice = self.offer()
                error, result = self.s.resolve_rules_choice("p1", choice["id"], card_ids=[self.will] * count)
                self.assertIsNone(error)
                self.assertEqual(result["count"], count)
                self.assertEqual(len(self.host.get("attachedCards", [])), count)
                self.assertEqual(self.host["counters"].get("Placed", 0), count)
                self.assertEqual(self.s.players["p1"]["zones"]["hand"], [self.will] * (2 - count) + ["m2"])
                self.assertEqual(self.s.players["p1"]["zones"]["graveyard"], [])
                self.assertFalse(any(e.get("kind") == "cards_discarded" for e in self.s.rules_engine.get("observedEvents", [])))

    def test_invalid_manifestation_or_extra_copy_is_atomic_and_keeps_choice(self):
        choice = self.offer()
        for cards in (["m2"], [self.will] * 3):
            before = copy.deepcopy((self.s.players, self.host))
            error, _ = self.s.resolve_rules_choice("p1", choice["id"], card_ids=cards)
            self.assertIsNotNone(error)
            self.assertEqual((self.s.players, self.host), before)
            self.assertEqual(self.s.rules_engine["pendingChoice"]["id"], choice["id"])

    def test_placed_wills_are_face_up_in_both_players_views_and_keep_owner(self):
        self.s.players["p1"]["zoneOwners"]["hand"][self.will] = "p2"
        choice = self.offer()
        self.assertIsNone(self.s.resolve_rules_choice("p1", choice["id"], card_ids=[self.will])[0])
        for viewer in ("p1", "p2"):
            public = self.s.serialize_for(viewer, "player")
            host = next(i for i in public["battlefield"] if i["id"] == self.host["id"])
            self.assertEqual(host["attachedCards"], [{"cardId": self.will, "ownerId": "p2"}])

    def test_missing_host_keeps_hand_intact(self):
        choice = self.offer()
        self.s.battlefield.remove(self.host)
        before = copy.deepcopy(self.s.players)
        error, _ = self.s.resolve_rules_choice("p1", choice["id"], card_ids=[self.will])
        self.assertIsNotNone(error)
        self.assertEqual(self.s.players, before)

    def test_host_leaves_exiles_each_attached_copy_to_original_owner(self):
        self.host["attachedCards"] = [{"cardId": self.will, "ownerId": "p1"}, {"cardId": self.will, "ownerId": "p2"}]
        self.s._rules_remove_field_item(self.host, "p1", "hand")
        for pid in ("p1", "p2"):
            self.assertEqual(self.s.players[pid]["zones"]["exile"], [self.will])

    def test_foreign_owned_will_is_played_as_from_hand_and_returns_to_owner_limbo(self):
        self.host["attachedCards"] = [{"cardId": self.will, "ownerId": "p2"}]
        target = self.f.field(self.s, "m2", item="target")
        self.f.put(self.s, "p1", "hand", ["m2"])
        self.s.rules_engine["priorityPlayerId"] = "p1"
        self.assertTrue(self.s.rules_player_can_act("p1"))
        for targets, payment in (([self.f.target(target)], []), ([], ["m2"])):
            before = copy.deepcopy((self.s.players, self.host))
            error, _ = self.s.declare_rules_action("p1", "Strengthen", kind="play_card",
                source={"cardId": self.will, "zone": "attached", "itemId": self.host["id"]},
                targets=targets, payment_card_ids=payment, ability_id="strengthen-power-modifier")
            self.assertIsNotNone(error)
            self.assertEqual((self.s.players, self.host), before)
        error, action = self.s.declare_rules_action("p1", "Strengthen", kind="play_card",
            source={"cardId": self.will, "zone": "attached", "itemId": self.host["id"]},
            targets=[self.f.target(target)], payment_card_ids=["m2"], ability_id="strengthen-power-modifier")
        self.assertIsNone(error, error)
        self.assertEqual(action["source"]["ownerId"], "p2")
        self.s.resolve_rules_top_action()
        self.assertEqual(self.s.rules_manifestation_characteristics(target)["power"], 5)
        self.assertEqual(self.s.players["p2"]["zones"]["graveyard"], [self.will])
        self.assertFalse(self.host["attachedCards"])


class ConfrontationStackSequenceTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.SemanticBatch001150()
        self.s = self.f.world()
        self.sermon = self.f.field(self.s, self.f.cid("Sermon, Obscene Quadrumane"), item="sermon")
        self.tong = self.f.field(self.s, self.f.cid("Tong, the Expansive"), item="tong", owner="p2")
        self.s.rules_engine.update(priorityPlayerId="p1", autoSkipPhases=False,
            firstManifestationItemIds={"p1": "sermon", "p2": "tong"})

    def test_strengthen_on_stack_must_resolve_before_reaction_can_advance(self):
        will = self.f.cid("Strengthen")
        self.f.put(self.s, "p1", "hand", [will, "m2"])
        error, _ = self.s.declare_rules_action("p1", "Strengthen", kind="play_card",
            source={"cardId": will, "zone": "hand"}, targets=[self.f.target(self.sermon)], payment_card_ids=["m2"], ability_id="strengthen-power-modifier")
        self.assertIsNone(error)
        for pid in ("p2", "p1"):
            error, result = self.s.pass_rules_priority(pid)
            self.assertIsNone(error)
            self.assertEqual(self.s.current_phase_id(), "confrontation_reaction")
            self.assertIsNone(self.s.rules_engine.get("confrontationResult"))
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(self.s.rules_manifestation_characteristics(self.sermon)["power"], 8)
        for _ in range(2):
            self.assertIsNone(self.s.pass_rules_priority(self.s.rules_engine["priorityPlayerId"])[0])
        self.assertEqual(self.s.rules_engine["confrontationResult"]["totals"], {"p1": 8, "p2": 6})
        self.assertEqual(self.s.rules_engine["confrontationResult"]["winnerId"], "p1")

    def test_strengthen_after_comparison_gives_three_power_without_retroactive_win(self):
        self.s.phase_tracker["index"] = fixtures.ADVANCED_PHASES.index("resolution_compare")
        result = self.s.prepare_rules_confrontation_result()
        self.assertEqual(result["totals"], {"p1": 5, "p2": 6})
        self.s.phase_tracker["index"] = fixtures.ADVANCED_PHASES.index("resolution_effects")
        action = self.f.action("Strengthen", targets=[self.f.target(self.sermon)])
        self.s.create_rules_ongoing_effects(action)
        self.assertEqual(self.s.rules_manifestation_characteristics(self.sermon)["power"], 8)
        self.assertEqual(result["winnerId"], "p2")
        self.assertEqual(result["totals"], {"p1": 5, "p2": 6})
