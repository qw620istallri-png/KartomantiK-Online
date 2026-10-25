"""Printed-rule regression oracles for sources/targets leaving their zone.

Rules 3.2: effects on the Stack are independent of their source; memories
survive Hand/Limbo visits but end on entering a Deck or Exile. No assumption
about last-known numeric information or Limbo round trips is made here.
"""
import copy

import test_game_state as game_tests


class DepartureResolutionAuditTests(game_tests.RealCardRulesCase):
    MUKKABELL = "inner-deserts-012"
    LOOJ = "inner-deserts-036"
    BOLBA = "pgvrly9397pua77_en"
    MIMER = "pwsjhnw4vpvqgkv_en"
    CLEANSE = "inner-deserts-145"
    OPPRESS = "obn1uv72ewxv3y5_en"
    ALL = (MUKKABELL, LOOJ, BOLBA, MIMER, CLEANSE, OPPRESS)

    def started(self):
        session, p1, p2 = self.make_session()
        session.rules_engine.update(readyPlayerIds=["p1", "p2"],
            firstManifestationComplete=True, priorityPlayerId="p1", autoSkipPhases=False)
        session.phase_tracker["index"] = game_tests.ADVANCED_PHASES.index("confrontation_reaction")
        session.card_rules["m-0"]["power"] = 4
        session.card_rules["m-1"]["power"] = 8
        mine = self.field_item("mine", "p1", "m-0")
        foe = self.field_item("foe", "p2", "m-1")
        session.battlefield = [mine, foe]
        session.rules_engine["firstManifestationItemIds"] = {"p1": "mine", "p2": "foe"}
        session.add_rules_excess_essence("p1", [{"temperament": "hollow", "amount": 20}])
        return session, p1, p2, mine, foe

    @staticmethod
    def target(item):
        return {"kind": "card", "itemId": item["id"], "cardId": item["cardId"], "ownerId": item["ownerId"]}

    def declare(self, session, host, ability_id, targets=()):
        session.rules_engine["priorityPlayerId"] = "p1"
        error, action = session.declare_rules_action("p1", host["cardId"], kind="activated_effect",
            source={"cardId": host["cardId"], "itemId": host["id"], "zone": "battlefield"},
            ability_id=ability_id, targets=list(targets))
        self.assertIsNone(error)
        return action

    def chain(self, session, grant=None, *, cid="m-0", player="p1", owner="p1", zone="hand"):
        container = player
        if cid not in session.players[container]["zones"][zone]:
            session.put_zone_card(container, zone, cid, owner)
        error, result = session.chain_rules_manifestation(player, zone, cid,
            container_id=container, source_card_id=grant, chain_controller_id=player,
            chain_abilities=(copy.deepcopy(self.ABILITIES[grant][0]["result"]["chainAbilities"]) if grant else None))
        self.assertIsNone(error)
        return session.find_battlefield_item(result["itemId"])

    def outcome(self, session, item, event="wins_confrontation"):
        actor = session.rules_item_controller_id(item)
        return session.queue_rules_chain_outcome_triggers(item, event, actor)

    def test_targeted_activation_resolves_after_source_returns_to_hand_or_is_exiled(self):
        for destination in ("hand", "graveyard", "exile"):
            with self.subTest(destination=destination):
                session, _, _, mine, foe = self.started()
                mine.update(cardId=self.BOLBA, fieldZone="interzone")
                self.declare(session, mine, "reduce-manifestation-power", [self.target(foe)])
                session._rules_remove_field_item_by_effect(mine, "p1", destination)
                session.prune_rules_ongoing_effects()
                session.resolve_rules_top_action()
                self.assertEqual(self.power_of(session, "foe"), 6)

    def test_source_changes_do_not_transfer_control_of_its_queued_effect(self):
        session, p1, p2, mine, foe = self.started()
        mine.update(cardId=self.BOLBA, fieldZone="interzone")
        action = self.declare(session, mine, "reduce-manifestation-power", [self.target(foe)])
        mine.update(controllerId="p2", effectsDisabled=True)
        session.resolve_rules_top_action()
        self.assertEqual(action["controllerId"], "p1")
        self.assertEqual(self.power_of(session, "foe"), 6)
        self.assertEqual((p1["score"], p2["score"]), (0, 0))

    def test_mimer_does_not_copy_a_reentered_instance_of_its_old_target(self):
        session, _, _, mine, foe = self.started()
        mine["cardId"] = self.MIMER
        action = self.declare(session, mine, "copy-first-manifestation", [self.target(foe)])
        session._rules_remove_field_item_by_effect(foe, "p2", "hand")
        replacement = self.chain(session, cid="m-1", player="p2", owner="p2")
        session.rules_engine["firstManifestationItemIds"]["p2"] = replacement["id"]
        session.resolve_rules_top_action()
        self.assertEqual(action["effectResult"]["kind"], "invalid_targets")
        self.assertEqual(self.power_of(session, "mine"), 3)
        self.assertEqual(self.power_of(session, replacement["id"]), 8)

    def test_self_modification_does_not_attach_to_a_new_instance_of_the_source(self):
        session, _, _, mine, foe = self.started()
        mine["cardId"] = self.MIMER
        self.declare(session, mine, "copy-first-manifestation", [self.target(foe)])
        session._rules_remove_field_item_by_effect(mine, "p1", "hand")
        replacement = self.chain(session, cid=self.MIMER)
        session.resolve_rules_top_action()
        self.assertEqual(self.power_of(session, replacement["id"]), 3)
        self.assertFalse(any(e.get("source", {}).get("itemId") == replacement["id"] for e in session.rules_engine["ongoingEffects"]))

    def test_mukkabells_queued_chain_resolves_after_mukkabell_leaves(self):
        session, p1, _, mine, _ = self.started()
        mine["cardId"] = self.MUKKABELL
        self.put(p1, "hand", ["m-2"])
        actions = session.queue_rules_battlefield_entry_triggers(self.MUKKABELL, "p1", "mine", True, defer=True)
        action = next(a for a in actions if a["ability"]["id"] == "mukkabell-chain-from-hand")
        action["optionalAccepted"] = True
        session.rules_engine["actionStack"].append(action)
        session._rules_remove_field_item_by_effect(mine, "p1", "graveyard")
        session.resolve_rules_top_action()
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["kind"], "chain_manifestation")
        error, result = session.resolve_rules_choice("p1", choice["id"], ["m-2"])
        self.assertIsNone(error)
        chained = session.find_battlefield_item(result["itemId"])
        self.assertEqual([a["ability"]["id"] for a in self.outcome(session, chained)], ["mukkabell-chained-wins"])

    def test_granted_chain_abilities_survive_hand_and_limbo_visits(self):
        for grant, event, expected in ((self.MUKKABELL, "wins_confrontation", ["mukkabell-chained-wins"]),
                (self.LOOJ, "loses_confrontation", ["looj-chained-loses", "looj-chained-loses-points"])):
            for destination in ("hand", "graveyard"):
                with self.subTest(grant=grant, destination=destination):
                    session, _, _, _, _ = self.started()
                    first = self.chain(session, grant, cid="m-2")
                    session._rules_remove_field_item_by_effect(first, "p1", destination)
                    error, returned = session.chain_rules_manifestation("p1", destination, "m-2")
                    self.assertIsNone(error)
                    item = session.find_battlefield_item(returned["itemId"])
                    self.assertEqual([a["ability"]["id"] for a in self.outcome(session, item, event)], expected)

    def test_granted_memory_keeps_original_effect_controller_after_reentry(self):
        session, p1, p2, _, _ = self.started()
        first = self.chain(session, self.MUKKABELL, cid="m-2", player="p2", owner="p1", zone="receptacle")
        session._rules_remove_field_item_by_effect(first, "p1", "hand")
        error, returned = session.chain_rules_manifestation("p1", "hand", "m-2")
        self.assertIsNone(error)
        item = session.find_battlefield_item(returned["itemId"])
        actions = self.outcome(session, item)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["controllerId"], "p2")
        session.rules_engine["actionStack"].extend(actions)
        session.resolve_rules_top_action()
        self.assertEqual((p1["score"], p2["score"]), (0, 5))

    def test_granted_memory_is_erased_in_deck_or_exile(self):
        for destination in ("deck", "exile"):
            with self.subTest(destination=destination):
                session, _, _, _, _ = self.started()
                first = self.chain(session, self.MUKKABELL, cid="m-2")
                session._rules_remove_field_item_by_effect(first, "p1", destination)
                error, returned = session.chain_rules_manifestation("p1", destination, "m-2")
                self.assertIsNone(error)
                self.assertEqual(self.outcome(session, session.find_battlefield_item(returned["itemId"])), [])

    def test_copy_does_not_inherit_the_real_cards_granted_memory(self):
        session, _, _, _, _ = self.started()
        first = self.chain(session, self.MUKKABELL, cid="m-2")
        token_copy = session.create_rules_token_copy("m-2", "p1")
        session.queue_rules_token_copy_entry_triggers(token_copy)
        self.assertEqual(self.outcome(session, token_copy), [])
        self.assertEqual(len(self.outcome(session, first)), 1)

    def test_a_second_chain_retains_each_grant_with_its_own_controller_once(self):
        session, p1, p2, _, _ = self.started()
        first = self.chain(session, self.MUKKABELL, cid="m-2", player="p2", owner="p1", zone="receptacle")
        session._rules_remove_field_item_by_effect(first, "p1", "hand")
        second = self.chain(session, self.MUKKABELL, cid="m-2")
        actions = self.outcome(session, second)
        self.assertEqual(sorted(a["controllerId"] for a in actions), ["p1", "p2"])
        session.rules_engine["actionStack"].extend(actions)
        while session.rules_engine["actionStack"]:
            session.resolve_rules_top_action()
        self.assertEqual((p1["score"], p2["score"]), (5, 5))
        # Merely refreshing entry metadata cannot duplicate either rule.
        session.queue_rules_battlefield_entry_triggers("m-2", "p1", second["id"], True, defer=True)
        self.assertEqual(len(self.outcome(session, second)), 2)

    def test_cleanse_preserves_granted_memory_after_a_limbo_roundtrip(self):
        session, _, _, _, _ = self.started()
        first = self.chain(session, self.MUKKABELL, cid="m-2")
        session._rules_remove_field_item_by_effect(first, "p1", "graveyard")
        error, result = session.chain_rules_manifestation("p1", "graveyard", "m-2")
        self.assertIsNone(error)
        item = session.find_battlefield_item(result["itemId"])
        item["counters"]["power"] = 2
        session.rules_engine["actionStack"].append({"id": "cleanse-memory", "kind": "play_card",
            "controllerId": "p1", "sourceOnStack": True,
            "source": {"cardId": self.CLEANSE, "cardType": "ephemeral_will", "ownerId": "p1", "zone": "hand"},
            "targets": [self.target(item)], "ability": self.ABILITIES[self.CLEANSE][0]})
        session.resolve_rules_top_action()
        self.assertEqual(self.power_of(session, item["id"]), 1)
        self.assertEqual(len(self.outcome(session, item)), 1)

    def test_another_live_physical_copy_cannot_inherit_the_grant(self):
        session, _, _, _, _ = self.started()
        first = self.chain(session, self.MUKKABELL, cid="m-2")
        second = self.chain(session, cid="m-2")
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(self.outcome(session, second), [])
        self.assertEqual(len(self.outcome(session, first)), 1)

    def test_exiling_another_physical_copy_does_not_erase_the_live_cards_memory(self):
        session, _, _, _, _ = self.started()
        first = self.chain(session, self.MUKKABELL, cid="m-2")
        second = self.chain(session, cid="m-2")
        session._rules_remove_field_item_by_effect(second, "p1", "exile")
        memories = session.rules_effect_memories_for("p1", "m-2", "chain_outcome_abilities")
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0]["data"]["itemId"], first["id"])
        session._rules_remove_field_item_by_effect(first, "p1", "hand")
        error, returned = session.chain_rules_manifestation("p1", "hand", "m-2")
        self.assertIsNone(error)
        self.assertEqual(len(self.outcome(session, session.find_battlefield_item(returned["itemId"]))), 1)

    def test_looj_rewards_the_actual_winner_after_the_chained_card_changes_control(self):
        session, p1, p2, _, _ = self.started()
        session.card_points["m-2"] = 20
        item = self.chain(session, self.LOOJ, cid="m-2", player="p2", owner="p1", zone="receptacle")
        item["controllerId"] = "p1"
        session.rules_engine["confrontationResult"] = {"winnerId": "p2", "loserId": "p1", "participantItemIds": [item["id"]]}
        actions = self.outcome(session, item, "loses_confrontation")
        self.assertEqual(len(actions), 2)
        self.assertTrue(all(a["controllerId"] == "p2" for a in actions))
        item["controllerId"] = "p2"  # later control cannot change the recorded loser/winner
        session.rules_engine["actionStack"].extend(actions)
        while session.rules_engine["actionStack"]:
            session.resolve_rules_top_action()
        self.assertIn("m-2", p1["zones"]["hand"])
        self.assertEqual((p1["score"], p2["score"]), (0, 20))
