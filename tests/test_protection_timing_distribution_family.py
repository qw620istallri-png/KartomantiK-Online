"""Strict semantic coverage for protection, timing, and distribution cards."""

import copy

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


RITUAL = "l3ne0zha51w387z_en"
TRAP = "xzh48oy0ramirce_en"
CARESS = "inner-deserts-024"
PALM = "inner-deserts-144"
SCUTTLER = "7badn4v9w72srad_en"

EXPECTED_ABILITIES = {
    RITUAL: [{
        "id": "protect-controller-hand",
        "passiveEffect": {"kind": "protect_controller_hand"},
    }],
    TRAP: [{
        "id": "trap-at-revelation",
        "action": "play_card",
        "targets": {"min": 0, "max": 0},
        "result": {"kind": "first_manifestation_trap"},
    }],
    CARESS: [{
        "id": "split-recent-limbo-cards-between-deck-ends",
        "action": "play_card",
        "targets": {
            "min": 0, "max": 4,
            "cardTypes": [
                "manifestation", "persistent_will", "ephemeral_will",
            ],
            "zones": ["graveyard"],
            "enteredThisTurn": True,
            "sameContainer": True,
        },
        "result": {"kind": "split_targeted_limbo_cards"},
    }],
    PALM: [{
        "id": "limit-each-hand-to-six",
        "passiveEffect": {
            "kind": "hand_limit_all", "value": 6,
            "overflowDestination": "deck_bottom",
        },
    }],
    SCUTTLER: [{
        "id": "stalemate-winner-after-loss",
        "trigger": {"event": "loses_confrontation"},
        "result": {
            "kind": "stalemate_confrontation", "scope": "winner",
            "lockZone": True,
        },
    }],
}


class ProtectionTimingDistributionFamily(RealCardRulesCase):
    ALL = (RITUAL, TRAP, CARESS, PALM, SCUTTLER)

    def started(self, phase="confrontation_reaction"):
        session, p1, p2 = self.make_session()
        session.phase_tracker.update(
            index=ADVANCED_PHASES.index(phase), turn=4,
        )
        session.rules_engine.update(
            readyPlayerIds=["p1", "p2"], priorityPlayerId="p1",
            priorityPasses=[], actionStack=[], pendingChoice=None,
        )
        return session, p1, p2

    @staticmethod
    def zone_target(container_id, card_id, owner_id=None):
        return {
            "kind": "zone_card", "containerId": container_id,
            "zone": "graveyard", "cardId": card_id,
            "ownerId": owner_id or container_id,
        }

    def apply_ability(self, session, card_id, *, item=None, targets=None):
        ability = self.ABILITIES[card_id][0]
        controller_id = session.rules_item_controller_id(item) if item else "p1"
        return session.apply_rules_action_result({
            "id": "strict-action", "controllerId": controller_id,
            "source": {
                "cardId": card_id, "itemId": (item or {}).get("id"),
                "ownerId": (item or {}).get("ownerId", controller_id),
            },
            "targets": list(targets or []), "ability": ability,
        })

    def active_item(self, session, owner_id, card_id, *, item_id=None,
                    field_zone="confrontation"):
        item = self.field_item(
            item_id or card_id, owner_id, card_id, field_zone,
            x=0.0, y=0.0, rotation=0.0,
        )
        session.battlefield.append(item)
        return item

    def test_compiles_all_five_exact_contracts(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        for card_id, abilities in EXPECTED_ABILITIES.items():
            with self.subTest(card_id=card_id):
                self.assertEqual(self.ABILITIES[card_id], abilities)
        self.assertEqual(rules[RITUAL]["passiveEffects"], [{
            "kind": "protect_controller_hand",
        }])
        self.assertEqual(rules[TRAP]["playedAbilities"], EXPECTED_ABILITIES[TRAP])
        self.assertEqual(rules[CARESS]["playedAbilities"], EXPECTED_ABILITIES[CARESS])
        self.assertEqual(rules[PALM]["passiveEffects"], [{
            "kind": "hand_limit_all", "value": 6,
            "overflowDestination": "deck_bottom",
        }])
        self.assertEqual(
            rules[SCUTTLER]["triggeredAbilities"], EXPECTED_ABILITIES[SCUTTLER],
        )

    def test_ritual_blocks_hostile_discard_but_not_self_discard(self):
        session, p1, _p2 = self.started()
        self.active_item(session, "p1", RITUAL, field_zone="field")
        self.put(p1, "hand", ["m-0"])
        hostile = session.apply_rules_action_result({
            "controllerId": "p2",
            "targets": [{"kind": "player", "playerId": "p1"}],
            "ability": {"result": {"kind": "discard_hand_target", "value": 1}},
        })
        self.assertEqual(hostile["status"], "prevented_immunity")
        self.assertEqual(p1["zones"]["hand"], ["m-0"])

        own = session.apply_rules_action_result({
            "controllerId": "p1",
            "targets": [{"kind": "player", "playerId": "p1"}],
            "ability": {"result": {"kind": "discard_hand_target", "value": 1}},
        })
        self.assertEqual(own["choiceKind"], "discard_from_hand")
        choice = session.rules_engine["pendingChoice"]
        error, _result = session.resolve_rules_choice(
            "p1", choice["id"], card_ids=["m-0"],
        )
        self.assertIsNone(error, error)
        self.assertEqual(p1["zones"]["graveyard"], ["m-0"])

    def test_ritual_protects_only_its_controller_hand(self):
        session, _p1, p2 = self.started()
        self.active_item(session, "p1", RITUAL, field_zone="field")
        self.put(p2, "hand", ["m-2"])
        result = session.apply_rules_action_result({
            "controllerId": "p1",
            "targets": [{"kind": "player", "playerId": "p2"}],
            "ability": {"result": {"kind": "discard_hand_target", "value": 1}},
        })
        self.assertEqual(result["choiceKind"], "discard_from_hand")
        self.assertNotEqual(result.get("status"), "prevented_immunity")

    def test_trap_waits_hidden_then_reveals_after_opponent_first(self):
        session, p1, _p2 = self.started("confrontation_choose")
        session.rules_engine["firstManifestationComplete"] = False
        self.put(p1, "hand", [TRAP, "m-0"])
        p1["score"] = 100
        error, placed = session.play_first_manifestation_trap("p1", TRAP)
        self.assertIsNone(error, error)
        self.assertEqual(placed, {"playerId": "p1", "delta": 0})
        self.assertEqual(p1["score"], 100)
        self.assertIsNone(
            session.serialize_for("p2", "player")["rulesEngine"]
            ["trapCards"]["p1"]["cardId"]
        )
        self.assertEqual(
            session.serialize_for("p1", "player")["rulesEngine"]
            ["trapCards"]["p1"]["cardId"], TRAP,
        )

        mine = self.field_item("mine", "p1", "m-0", faceUp=False)
        theirs = self.field_item("theirs", "p2", "m-1", faceUp=False)
        session.battlefield = [mine, theirs]
        self.assertIn("Trap", session.register_first_manifestation("p1", mine))
        self.assertIsNone(session.register_first_manifestation("p2", theirs))
        error, revealed = session.validate_first_manifestation("p2")
        self.assertIsNone(error, error)
        self.assertTrue(theirs["faceUp"])
        self.assertEqual(revealed["trapsRevealed"][0]["cardId"], TRAP)
        self.assertEqual(p1["score"], 95)
        self.assertIn(TRAP, p1["zones"]["graveyard"])

        self.assertIsNone(session.register_first_manifestation("p1", mine))
        error, completed = session.validate_first_manifestation("p1")
        self.assertIsNone(error, error)
        self.assertTrue(completed["selectionComplete"])
        self.assertTrue(mine["faceUp"])

    def test_trap_cannot_be_played_as_an_ordinary_reaction_even_with_permission(self):
        session, p1, _p2 = self.started("confrontation_reaction")
        self.put(p1, "hand", [TRAP])
        session.rules_engine["playPermissions"].append({
            "playerId": "p1", "cardId": TRAP, "fromZone": "hand",
            "turn": session.phase_tracker["turn"],
            "phaseIds": ["confrontation_reaction"], "free": True,
        })
        error, action = session.declare_rules_action(
            "p1", "Trap", kind="play_card",
            source={"cardId": TRAP, "zone": "hand"},
            ability_id="trap-at-revelation",
        )
        self.assertIn("Revelation", error)
        self.assertIsNone(action)
        self.assertIn(TRAP, p1["zones"]["hand"])

    def caress_targets(self, session, p1, count, *, container="p1"):
        targets = []
        for index in range(count):
            card_id = f"m-{index}"
            session.put_zone_card(container, "graveyard", card_id, container)
            targets.append(self.zone_target(container, card_id))
        return targets

    def test_caress_zero_and_four_targets_are_legal_but_five_mixed_or_stale_are_not(self):
        session, p1, _p2 = self.started()
        rules = self.ABILITIES[CARESS][0]["targets"]
        self.assertIsNone(session.rules_ability_targets_error(rules, [], "p1"))
        four = self.caress_targets(session, p1, 4)
        self.assertIsNone(session.rules_ability_targets_error(rules, four, "p1"))
        session.put_zone_card("p1", "graveyard", "m-4", "p1")
        five = four + [self.zone_target("p1", "m-4")]
        self.assertTrue(session.rules_ability_targets_error(rules, five, "p1"))

        session.put_zone_card("p2", "graveyard", "m-5", "p2")
        mixed = four[:1] + [self.zone_target("p2", "m-5")]
        self.assertIn(
            "single", session.rules_ability_targets_error(rules, mixed, "p1").lower(),
        )
        session.rules_engine["zoneEntryTurns"]["p1:graveyard:m-0"] = 3
        self.assertIn(
            "this turn",
            session.rules_ability_targets_error(rules, four[:1], "p1"),
        )

    def test_caress_splits_three_and_four_with_exact_order(self):
        cases = [
            (3, ["m-2"], ["m-1", "m-0"]),
            (4, ["m-3", "m-2"], ["m-1", "m-0"]),
        ]
        for count, top, bottom in cases:
            with self.subTest(count=count):
                session, p1, _p2 = self.started()
                self.put(p1, "deck", ["m-9"])
                targets = self.caress_targets(session, p1, count)
                required = self.apply_ability(session, CARESS, targets=targets)
                self.assertEqual(required["choiceKind"], "deck_reorder")
                choice = session.rules_engine["pendingChoice"]
                error, _result = session.resolve_rules_choice(
                    "p1", choice["id"], option={"groups": [{
                        "playerId": "p1", "top": top, "bottom": bottom,
                    }]},
                )
                self.assertIsNone(error, error)
                self.assertEqual(p1["zones"]["deck"], top + ["m-9"] + bottom)
                self.assertEqual(p1["zones"]["graveyard"], [])

    def test_caress_with_zero_targets_resolves_without_a_choice(self):
        session, _p1, _p2 = self.started()
        result = self.apply_ability(session, CARESS)
        self.assertEqual(result, {
            "kind": "split_targeted_limbo_cards", "status": "no_targets",
        })
        self.assertIsNone(session.rules_engine["pendingChoice"])

    def test_caress_invalid_order_is_atomic(self):
        session, p1, _p2 = self.started()
        self.put(p1, "deck", ["m-9"])
        targets = self.caress_targets(session, p1, 3)
        self.apply_ability(session, CARESS, targets=targets)
        choice = session.rules_engine["pendingChoice"]
        before = copy.deepcopy((p1["zones"], p1["zoneOwners"]))
        error, result = session.resolve_rules_choice(
            "p1", choice["id"], option={"groups": [{
                "playerId": "p1", "top": ["m-2"],
                "bottom": ["m-1", "m-1"],
            }]},
        )
        self.assertTrue(error)
        self.assertIsNone(result)
        self.assertEqual((p1["zones"], p1["zoneOwners"]), before)

    def test_caress_returns_foreign_owned_card_to_its_owners_deck(self):
        session, p1, p2 = self.started()
        session.put_zone_card("p1", "graveyard", "m-2", "p2")
        target = self.zone_target("p1", "m-2", "p2")
        self.apply_ability(session, CARESS, targets=[target])
        choice = session.rules_engine["pendingChoice"]
        error, _result = session.resolve_rules_choice(
            "p1", choice["id"], option={"groups": [{
                "playerId": "p1", "top": [], "bottom": ["m-2"],
            }]},
        )
        self.assertIsNone(error, error)
        self.assertNotIn("m-2", p1["zones"]["deck"])
        self.assertEqual(p2["zones"]["deck"], ["m-2"])

    def test_palm_applies_to_both_players_but_only_after_a_draw(self):
        session, p1, p2 = self.started()
        self.active_item(session, "p1", PALM, field_zone="field")
        self.assertEqual(session.rules_hand_limit("p1"), 6)
        self.assertEqual(session.rules_hand_limit("p2"), 6)
        self.put(p1, "hand", [f"m-{index}" for index in range(7)])
        self.assertIsNone(session.rules_engine["pendingChoice"])

        self.put(p2, "hand", [f"m-{index}" for index in range(10, 15)])
        self.put(p2, "deck", ["m-15", "m-16", "m-17"])
        drawn = session.request_rules_draw("p2", 3, "p2", include_drawn=True)
        self.assertEqual(drawn["drawn"], ["m-15", "m-16", "m-17"])
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual((choice["kind"], choice["playerId"], choice["count"]), (
            "hand_overflow", "p2", 2,
        ))
        error, resolved = session.resolve_rules_choice(
            "p2", choice["id"], card_ids=["m-16", "m-15"],
        )
        self.assertIsNone(error, error)
        self.assertEqual(len(p2["zones"]["hand"]), 6)
        self.assertEqual(p2["zones"]["deck"], ["m-16", "m-15"])
        self.assertEqual(resolved["destination"], "deck_bottom")

    def test_palm_overflow_uses_deck_entry_replacements(self):
        session, p1, _p2 = self.started()
        self.active_item(session, "p1", PALM, field_zone="field")
        session.card_rules["bob"] = {
            "type": "manifestation", "power": 5,
            "temperaments": ["phlegmatic"],
            "suspensionThresholds": {"deck": 5},
        }
        self.active_item(session, "p1", "bob", item_id="bob")
        self.put(p1, "hand", [f"m-{index}" for index in range(7)])
        choice = session.set_rules_hand_overflow_choice(["p1"])
        error, resolved = session.resolve_rules_choice(
            "p1", choice["id"], card_ids=["m-0"],
        )
        self.assertIsNone(error, error)
        self.assertNotIn("m-0", p1["zones"]["deck"])
        self.assertNotIn("m-0", p1["zones"]["hand"])
        self.assertEqual(
            [(entry["cardId"], entry["sourceItemId"])
             for entry in resolved["replacements"]],
            [("m-0", "bob")],
        )
        self.assertEqual(
            [(entry["cardId"], entry["sourceEffectId"])
             for entry in session.rules_engine["suspendedCards"]],
            [("m-0", "bob")],
        )

    def test_palm_sequences_each_players_post_draw_overflow(self):
        session, p1, p2 = self.started()
        self.active_item(session, "p1", PALM, field_zone="field")
        self.put(p1, "hand", [f"m-{index}" for index in range(6)])
        self.put(p2, "hand", [f"m-{index}" for index in range(10, 16)])
        self.put(p1, "deck", ["m-8"])
        self.put(p2, "deck", ["m-18"])

        results = session.continue_rules_draw_requests([
            {"playerId": "p1", "count": 1, "sourceControllerId": "p1"},
            {"playerId": "p2", "count": 1, "sourceControllerId": "p1"},
        ])
        self.assertEqual(len(results), 1)
        first = session.rules_engine["pendingChoice"]
        self.assertEqual((first["playerId"], first["count"]), ("p1", 1))
        error, _resolved = session.resolve_rules_choice(
            "p1", first["id"], card_ids=["m-8"],
        )
        self.assertIsNone(error, error)

        second = session.rules_engine["pendingChoice"]
        self.assertEqual((second["playerId"], second["count"]), ("p2", 1))
        error, _resolved = session.resolve_rules_choice(
            "p2", second["id"], card_ids=["m-18"],
        )
        self.assertIsNone(error, error)
        self.assertEqual((len(p1["zones"]["hand"]), len(p2["zones"]["hand"])), (6, 6))
        self.assertEqual((p1["zones"]["deck"], p2["zones"]["deck"]), (
            ["m-8"], ["m-18"],
        ))

    def test_palm_overflow_choice_keeps_the_hand_private(self):
        session, p1, _p2 = self.started()
        self.active_item(session, "p1", PALM, field_zone="field")
        self.put(p1, "hand", [f"m-{index}" for index in range(7)])
        session.set_rules_hand_overflow_choice(["p1"])
        own = session.serialize_for("p1", "player")["rulesEngine"]["pendingChoice"]
        opposing = session.serialize_for("p2", "player")["rulesEngine"]["pendingChoice"]
        self.assertEqual((own["count"], opposing["count"]), (1, 1))
        self.assertNotIn("cardIds", opposing)
        self.assertNotIn("m-0", str(opposing))

    def test_scuttler_loss_queues_only_its_trigger_and_stalemates_winner(self):
        session, _p1, _p2 = self.started()
        scuttler = self.active_item(session, "p1", SCUTTLER, item_id="scuttler")
        loser = self.active_item(session, "p1", "m-0", item_id="loser")
        winner_a = self.active_item(session, "p2", "m-1", item_id="winner-a")
        winner_b = self.active_item(session, "p2", "m-2", item_id="winner-b")
        session.rules_engine["confrontationResult"] = {
            "turn": 4, "winnerId": "p2", "loserId": "p1",
            "participantItemIds": [
                "scuttler", "loser", "winner-a", "winner-b",
            ],
        }
        queued = session.queue_rules_confrontation_win_triggers(defer=True)
        self.assertEqual(
            [entry["ability"]["id"] for entry in queued],
            ["stalemate-winner-after-loss"],
        )
        result = self.apply_ability(session, SCUTTLER, item=scuttler)
        self.assertEqual(set(result["itemIds"]), {"winner-a", "winner-b"})
        self.assertEqual(
            [session.rules_field_zone(item) for item in (winner_a, winner_b)],
            ["stalemate", "stalemate"],
        )
        self.assertEqual(
            [session.rules_field_zone(item) for item in (scuttler, loser)],
            ["confrontation", "confrontation"],
        )
        self.assertTrue(session.rules_item_zone_locked(winner_a))
        self.assertTrue(session.rules_item_zone_locked(winner_b))

        blocked = session.apply_rules_action_result({
            "id": "hostile-move", "controllerId": "p1",
            "source": {"cardId": "will-x"},
            "targets": [{
                "kind": "card", "itemId": "winner-a", "cardId": "m-1",
                "ownerId": "p2",
            }],
            "ability": {"result": {
                "kind": "move_target", "zone": "graveyard", "position": "top",
            }},
        })
        self.assertEqual(blocked["status"], "prevented_zone_lock")
        self.assertIs(session.find_battlefield_item("winner-a"), winner_a)

    def test_scuttler_does_not_trigger_without_a_loss_and_lock_expires_next_turn(self):
        session, _p1, _p2 = self.started()
        scuttler = self.active_item(session, "p1", SCUTTLER, item_id="scuttler")
        winner = self.active_item(session, "p2", "m-1", item_id="winner")
        session.rules_engine["confrontationResult"] = {
            "turn": 4, "winnerId": "p1", "loserId": "p2",
            "participantItemIds": ["scuttler", "winner"],
        }
        self.assertEqual(
            session.queue_rules_confrontation_win_triggers(defer=True), [],
        )

        session.rules_engine["confrontationResult"] = {
            "turn": 4, "winnerId": "p2", "loserId": "p1",
            "participantItemIds": ["scuttler", "winner"],
        }
        self.apply_ability(session, SCUTTLER, item=scuttler)
        self.assertTrue(session.rules_item_zone_locked(winner))
        session.phase_tracker["turn"] = 5
        self.assertFalse(session.rules_item_zone_locked(winner))

