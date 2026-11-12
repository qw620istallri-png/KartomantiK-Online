"""Strict semantic coverage for five zone, Revelation, and threshold cards."""

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


DULFER = "inner-deserts-104"
TUXNU = "inner-deserts-124"
QUPER = "inner-deserts-004"
BONZAI = "inner-deserts-034"
SPIKED_PIT = "inner-deserts-117"
PILLAR = "7gaov0c4cjndl9w_en"

EXPECTED_ABILITIES = {
    DULFER: [{
        "id": "dulfer-taxes-vessel-owner-at-revelation",
        "trigger": {
            "event": "vessel_revelation", "zone": "receptacle",
            "container": "opponent",
        },
        "result": {
            "kind": "choose_points_or_weaken_first",
            "points": 10, "power": 2,
        },
    }],
    TUXNU: [{
        "id": "copy-entering-persistent-will-for-other-players",
        "trigger": {"event": "persistent_will_enters_field"},
        "result": {"kind": "copy_entering_persistent_will_for_others"},
    }],
    QUPER: [{
        "id": "quper-sacrifice-at-five",
        "passiveEffect": {
            "kind": "sacrifice_at_power", "threshold": 5, "bonus": 2,
        },
    }],
    BONZAI: [{
        "id": "vessel-owner-shows-hand",
        "passiveEffect": {"kind": "vessel_reveals_owner_hand"},
    }],
    SPIKED_PIT: [{
        "id": "interzone-entry-penalty",
        "passiveEffect": {"kind": "interzone_entry_penalty", "value": -1},
    }],
}


class ZoneRevelationThresholdFamily(RealCardRulesCase):
    ALL = (DULFER, TUXNU, QUPER, BONZAI, SPIKED_PIT)

    def started(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker.update(
            index=ADVANCED_PHASES.index("confrontation_before_revelation"),
            turn=7,
        )
        session.rules_engine["readyPlayerIds"] = ["p1", "p2"]
        return session, p1, p2

    def test_compiles_all_five_exact_contracts(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        for card_id, abilities in EXPECTED_ABILITIES.items():
            with self.subTest(card_id=card_id):
                self.assertEqual(self.ABILITIES[card_id], abilities)
        self.assertEqual(rules[DULFER]["triggeredAbilities"], EXPECTED_ABILITIES[DULFER])
        self.assertEqual(rules[TUXNU]["triggeredAbilities"], EXPECTED_ABILITIES[TUXNU])
        for card_id in (QUPER, BONZAI, SPIKED_PIT):
            self.assertEqual(
                rules[card_id]["passiveEffects"],
                [EXPECTED_ABILITIES[card_id][0]["passiveEffect"]],
            )

    def test_dulfer_triggers_only_from_an_opponents_unlocked_vessel(self):
        session, p1, p2 = self.started()
        self.put(p2, "receptacle", {DULFER: "p1"})
        queued = session.queue_rules_revelation_triggers(defer=True)
        self.assertEqual(
            [action["ability"]["id"] for action in queued],
            ["dulfer-taxes-vessel-owner-at-revelation"],
        )
        self.assertEqual(queued[0]["source"]["containerId"], "p2")

        self.put(p2, "receptacle", {})
        self.put(p1, "receptacle", {DULFER: "p1"})
        self.assertEqual(session.queue_rules_revelation_triggers(defer=True), [])

        self.put(p1, "receptacle", {})
        self.put(p2, "receptacle", {DULFER: "p1"})
        session.card_rules[PILLAR] = {
            "type": "persistent_will",
            "passiveEffects": [{"kind": "vessel_protected_no_effects"}],
        }
        session.battlefield = [self.field_item("pillar", "p2", PILLAR, "field")]
        self.assertTrue(session.rules_vessel_locked("p2"))
        self.assertEqual(session.queue_rules_revelation_triggers(defer=True), [])

    def test_dulfer_vessel_owner_can_lose_exactly_ten_points(self):
        session, _p1, p2 = self.started()
        self.put(p2, "receptacle", {DULFER: "p1"})
        action = session.queue_rules_revelation_triggers(defer=True)[0]
        payload = session.apply_rules_action_result(action)
        self.assertEqual((payload["choiceKind"], payload["playerId"]), (
            "points_or_weaken_first", "p2",
        ))
        choice = session.rules_engine["pendingChoice"]
        before = p2["score"]
        self.assertIsNotNone(
            session.resolve_rules_choice(
                "p1", choice["id"], option="lose_points",
            )[0]
        )
        self.assertIsNotNone(
            session.resolve_rules_choice(
                "p2", choice["id"], option="invalid",
            )[0]
        )
        self.assertEqual(p2["score"], before)
        error, result = session.resolve_rules_choice(
            "p2", choice["id"], option="lose_points",
        )
        self.assertIsNone(error, error)
        self.assertEqual((result["status"], p2["score"]), (
            "lost_points", before - 10,
        ))

    def test_dulfer_weakens_the_current_first_until_that_occurrence_leaves(self):
        session, _p1, p2 = self.started()
        session.card_rules["m-1"]["power"] = 4  # survives the -2
        first = self.field_item("first", "p2", "m-1", "confrontation")
        session.battlefield = [first]
        session.rules_engine["firstManifestationItemIds"] = {"p2": "first"}
        self.put(p2, "receptacle", {DULFER: "p1"})
        action = session.queue_rules_revelation_triggers(defer=True)[0]
        session.apply_rules_action_result(action)
        choice = session.rules_engine["pendingChoice"]
        base = self.power_of(session, "first")
        error, result = session.resolve_rules_choice(
            "p2", choice["id"], option="weaken_first",
        )
        self.assertIsNone(error, error)
        self.assertEqual((result["status"], result["itemId"]), (
            "weakened", "first",
        ))
        self.assertEqual(self.power_of(session, "first"), base - 2)
        session.phase_tracker["turn"] += 1
        session.prune_rules_ongoing_effects()
        self.assertEqual(self.power_of(session, "first"), base - 2)

        session.battlefield.remove(first)
        returned = self.field_item("returned", "p2", "m-1", "confrontation")
        session.battlefield.append(returned)
        session.prune_rules_ongoing_effects()
        self.assertEqual(self.power_of(session, "returned"), base)

    def test_tuxnu_copies_a_non_token_persistent_will_for_each_other_player(self):
        session, _p1, _p2 = self.started()
        session.card_rules["persistent-probe"] = {"type": "persistent_will"}
        tuxnu = self.field_item("tuxnu", "p1", TUXNU, "interzone")
        entering = self.field_item(
            "entering", "p2", "persistent-probe", "field",
        )
        session.battlefield = [tuxnu, entering]
        actions = session.queue_rules_persistent_will_entry_watchers(
            entering, defer=True,
        )
        self.assertEqual(len(actions), 1)
        result = session.apply_rules_action_result(actions[0])
        self.assertEqual(result["status"], "created")
        self.assertEqual(len(result["createdItemIds"]), 1)
        copy = session.find_battlefield_item(result["createdItemIds"][0])
        self.assertEqual(session.rules_item_controller_id(copy), "p1")
        self.assertEqual(copy["cardId"], "persistent-probe")
        self.assertTrue(copy["isTokenCopy"])
        self.assertEqual(session.rules_field_zone(copy), "field")
        self.assertEqual(
            session.queue_rules_persistent_will_entry_watchers(
                copy, defer=True,
            ),
            [],
        )

    def test_tuxnu_excludes_wrong_types_hidden_cards_and_token_copies(self):
        session, _p1, _p2 = self.started()
        session.card_rules.update({
            "persistent-probe": {"type": "persistent_will"},
            "ephemeral-probe": {"type": "ephemeral_will"},
        })
        tuxnu = self.field_item("tuxnu", "p1", TUXNU, "field")
        session.battlefield = [tuxnu]
        cases = (
            self.field_item("manifestation", "p2", "m-1", "confrontation"),
            self.field_item("ephemeral", "p2", "ephemeral-probe", "field"),
            self.field_item(
                "hidden", "p2", "persistent-probe", "field", faceUp=False,
            ),
            self.field_item(
                "copy", "p2", "persistent-probe", "field",
                isCopy=True, isTokenCopy=True,
            ),
        )
        for item in cases:
            with self.subTest(item=item["id"]):
                session.battlefield.append(item)
                self.assertEqual(
                    session.queue_rules_persistent_will_entry_watchers(
                        item, defer=True,
                    ),
                    [],
                )
                session.battlefield.remove(item)

    def test_each_active_tuxnu_copies_once_without_recursive_growth(self):
        session, _p1, _p2 = self.started()
        session.card_rules["persistent-probe"] = {"type": "persistent_will"}
        entering = self.field_item(
            "entering", "p1", "persistent-probe", "field",
        )
        session.battlefield = [
            self.field_item("tuxnu-a", "p1", TUXNU, "field"),
            self.field_item("tuxnu-b", "p2", TUXNU, "interzone"),
            self.field_item(
                "tuxnu-disabled", "p2", TUXNU, "field",
                effectsDisabled=True,
            ),
            entering,
        ]
        actions = session.queue_rules_persistent_will_entry_watchers(
            entering, defer=True,
        )
        self.assertEqual(len(actions), 2)
        created = []
        for action in actions:
            created.extend(
                session.apply_rules_action_result(action)["createdItemIds"]
            )
        self.assertEqual(len(created), 2)
        self.assertTrue(all(
            session.rules_item_controller_id(
                session.find_battlefield_item(item_id)
            ) == "p2"
            for item_id in created
        ))
        self.assertEqual(len(session.battlefield), 6)

    def test_quper_sacrifices_at_five_and_boosts_only_current_allied_confrontation_cards(self):
        session, p1, _p2 = self.started()
        quper = self.field_item("quper", "p1", QUPER, "interzone")
        ally = self.field_item("ally", "p1", "m-1", "confrontation")
        support = self.field_item(
            "support", "p1", "m-2", "confrontation", isSupport=True,
        )
        waiting = self.field_item("waiting", "p1", "m-3", "interzone")
        enemy = self.field_item("enemy", "p2", "m-4", "confrontation")
        session.battlefield = [quper, ally, support, waiting, enemy]
        session.resolve_rules_state_actions()
        self.assertIsNotNone(session.find_battlefield_item("quper"))

        quper["counters"]["power"] = 3
        state = session.resolve_rules_state_actions()
        self.assertIsNone(session.find_battlefield_item("quper"))
        self.assertIn(QUPER, p1["zones"]["graveyard"])
        self.assertEqual(state["replacements"][0]["replacement"], "sacrifice_at_power")
        self.assertEqual(self.power_of(session, "ally"), 3)
        self.assertEqual(self.power_of(session, "support"), 3)
        self.assertEqual(self.power_of(session, "waiting"), 1)
        self.assertEqual(self.power_of(session, "enemy"), 1)

    def test_quper_uses_current_controller_and_bonus_expires_at_end_of_turn(self):
        session, p1, _p2 = self.started()
        quper = self.field_item(
            "quper", "p1", QUPER, "field",
            controllerId="p2", counters={"power": 3},
        )
        ally = self.field_item("ally", "p2", "m-1", "confrontation")
        old_ally = self.field_item("old-ally", "p1", "m-2", "confrontation")
        session.battlefield = [quper, ally, old_ally]
        session.resolve_rules_state_actions()
        self.assertIn(QUPER, p1["zones"]["graveyard"])
        self.assertEqual((self.power_of(session, "ally"), self.power_of(session, "old-ally")), (3, 1))

        late = self.field_item("late", "p2", "m-3", "confrontation")
        session.battlefield.append(late)
        self.assertEqual(self.power_of(session, "late"), 1)
        session.phase_tracker["turn"] += 1
        session.prune_rules_ongoing_effects()
        self.assertEqual(self.power_of(session, "ally"), 1)

    def test_quper_replaced_sacrifice_grants_no_bonus(self):
        session, _p1, _p2 = self.started()
        session.card_rules["bob"] = {
            "type": "manifestation", "power": 5,
            "temperaments": ["hollow"],
            "suspensionThresholds": {"graveyard": 5},
        }
        quper = self.field_item(
            "quper", "p1", QUPER, "interzone", counters={"power": 3},
        )
        ally = self.field_item("ally", "p1", "m-1", "confrontation")
        bob = self.field_item("bob", "p2", "bob", "confrontation")
        session.battlefield = [quper, ally, bob]
        state = session.resolve_rules_state_actions()
        self.assertEqual(state["replacements"][0]["status"], "suspended")
        self.assertEqual(self.power_of(session, "ally"), 1)

    def test_bonzai_reveals_only_the_vessel_owners_hand_to_its_owner_before_revelation(self):
        session, p1, p2 = self.started()
        self.put(p1, "hand", ["m-1"])
        self.put(p2, "hand", ["m-2"])
        self.put(p2, "receptacle", {BONZAI: "p1"})
        for phase_id, visible in (
            ("confrontation_choose", True),
            ("confrontation_before_revelation", True),
            ("confrontation_reaction", False),
            ("resolution_effects", False),
        ):
            with self.subTest(phase_id=phase_id):
                session.phase_tracker["index"] = ADVANCED_PHASES.index(phase_id)
                self.assertEqual(
                    session.can_view_zone("p1", "player", "p2", "hand"),
                    visible,
                )
                self.assertFalse(
                    session.can_view_zone("p2", "player", "p1", "hand")
                )

    def test_bonzai_uses_immutable_owner_and_stops_when_vessel_effects_are_locked(self):
        session, _p1, p2 = self.started()
        self.put(p2, "hand", ["m-2"])
        self.put(p2, "receptacle", {BONZAI: "p1"})
        self.assertTrue(session.rules_hand_revealed_to("p1", "p2"))
        self.assertFalse(session.rules_hand_revealed_to("p2", "p2"))

        session.card_rules[PILLAR] = {
            "type": "persistent_will",
            "passiveEffects": [{"kind": "vessel_protected_no_effects"}],
        }
        session.battlefield = [self.field_item("pillar", "p2", PILLAR, "field")]
        self.assertTrue(session.rules_vessel_locked("p2"))
        self.assertFalse(session.rules_hand_revealed_to("p1", "p2"))

    def test_spiked_pit_weakens_only_manifestations_entering_an_opponents_interzone(self):
        session, _p1, _p2 = self.started()
        pit = self.field_item("pit", "p1", SPIKED_PIT, "field")
        enemy = self.field_item("enemy", "p2", "m-1", "interzone")
        ally = self.field_item("ally", "p1", "m-2", "interzone")
        session.card_rules["will-probe"] = {"type": "persistent_will"}
        will = self.field_item("will", "p2", "will-probe", "interzone")
        session.battlefield = [pit, enemy, ally, will]
        self.assertEqual(session.apply_rules_interzone_entry_penalty(enemy), -1)
        self.assertEqual(session.apply_rules_interzone_entry_penalty(ally), 0)
        self.assertEqual(session.apply_rules_interzone_entry_penalty(will), 0)
        self.assertEqual((self.power_of(session, "enemy"), self.power_of(session, "ally")), (0, 1))

    def test_spiked_pits_stack_follow_current_control_and_require_active_sources(self):
        session, _p1, _p2 = self.started()
        enemy = self.field_item("enemy", "p2", "m-1", "interzone")
        session.card_rules["m-1"]["power"] = 4
        session.battlefield = [
            self.field_item("pit-a", "p1", SPIKED_PIT, "field"),
            self.field_item("pit-b", "p1", SPIKED_PIT, "interzone"),
            self.field_item(
                "pit-disabled", "p1", SPIKED_PIT, "field",
                effectsDisabled=True,
            ),
            self.field_item("pit-stalemate", "p1", SPIKED_PIT, "stalemate"),
            self.field_item(
                "pit-controlled", "p1", SPIKED_PIT, "field",
                controllerId="p2",
            ),
            enemy,
        ]
        self.assertEqual(session.apply_rules_interzone_entry_penalty(enemy), -2)
        self.assertEqual(self.power_of(session, "enemy"), 2)

    def test_spiked_pit_applies_to_generic_manifestation_tokens_but_not_retroactively(self):
        session, _p1, _p2 = self.started()
        pit = self.field_item("pit", "p1", SPIKED_PIT, "field")
        old = self.field_item("old", "p2", "m-1", "interzone")
        token = self.field_item(
            "token", "p2", "generic-token", "interzone",
            isTokenCard=True, power=2,
        )
        session.battlefield = [pit, old, token]
        self.assertEqual(self.power_of(session, "old"), 1)
        self.assertEqual(session.apply_rules_interzone_entry_penalty(token), -1)
        self.assertEqual(self.power_of(session, "token"), 1)
        self.assertEqual(self.power_of(session, "old"), 1)


if __name__ == "__main__":
    import unittest

    unittest.main()
