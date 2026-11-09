"""Strict semantic coverage for five mass/distribution outcome cards."""

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


ENTRUST = "ud9clfoj2c6x96o_en"
PUNISH = "nupb1i59d98g3md_en"
DAMAGE = "goxjkkrwos0lhx4_en"
RECALL = "inner-deserts-072"
EXTINGUISH = "inner-deserts-115"

EXPECTED_ABILITIES = {
    ENTRUST: [{
        "id": "entrust-double-base-power", "action": "play_card",
        "targets": {
            "min": 1, "max": 1, "cardType": "manifestation",
            "zones": ["battlefield"],
        },
        "result": {"kind": "double_target_base_power"},
    }],
    PUNISH: [{
        "id": "destroy-confrontation-winners", "action": "play_card",
        "targets": {"min": 0, "max": 0},
        "result": {
            "kind": "destroy_matching_on_field",
            "match": "won_confrontation_this_turn",
        },
    }],
    DAMAGE: [{
        "id": "damage-distribute-weakness", "action": "play_card",
        "targets": {
            "min": 1, "max": 3, "cardType": "manifestation",
            "zones": ["battlefield"], "fieldZone": "interzone",
            "controller": "opponent",
        },
        "result": {
            "kind": "distribute_power", "total": 3, "sign": -1,
            "duration": "while_target_on_field",
        },
    }],
    RECALL: [{
        "id": "exile-limbos-create-hollow-copies", "action": "play_card",
        "targets": {"min": 0, "max": 0},
        "result": {"kind": "exile_limbos_create_token_copies"},
    }],
    EXTINGUISH: [{
        "id": "immediate-exile-all-limbos", "action": "play_card",
        "immediate": True, "targets": {"min": 0, "max": 0},
        "result": {"kind": "exile_all_limbos"},
    }],
}


class MassDistributionOutcomesFamily(RealCardRulesCase):
    ALL = (ENTRUST, PUNISH, DAMAGE, RECALL, EXTINGUISH)

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
    def target(item):
        return {
            "kind": "card", "itemId": item["id"],
            "cardId": item["cardId"], "ownerId": item["ownerId"],
        }

    def active_item(self, session, owner_id, card_id, *, item_id=None,
                    field_zone="confrontation", controller_id=None, **extra):
        item = self.field_item(
            item_id or card_id, owner_id, card_id, field_zone,
            controllerId=controller_id or owner_id,
            x=0.0, y=0.0, rotation=0.0, **extra,
        )
        session.battlefield.append(item)
        return item

    def apply_ability(self, session, card_id, *, targets=None,
                      controller_id="p1", action_id="strict-action",
                      source_extra=None):
        return session.apply_rules_action_result({
            "id": action_id, "controllerId": controller_id,
            "source": {"cardId": card_id, "ownerId": controller_id,
                       **(source_extra or {})},
            "targets": list(targets or []),
            "ability": self.ABILITIES[card_id][0],
        })

    def test_compiles_all_five_exact_contracts(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        for card_id, abilities in EXPECTED_ABILITIES.items():
            with self.subTest(card_id=card_id):
                self.assertEqual(self.ABILITIES[card_id], abilities)
                self.assertEqual(rules[card_id]["playedAbilities"], abilities)

    def test_entrust_doubles_current_base_repeatedly_without_doubling_bonus(self):
        session, _p1, _p2 = self.started()
        session.card_rules["m-1"].update(power=3)
        item = self.active_item(
            session, "p1", "m-1", item_id="target",
            counters={"power": 2},
        )
        self.apply_ability(
            session, ENTRUST, targets=[self.target(item)], action_id="entrust-1",
        )
        self.assertEqual(session.rules_manifestation_base_power(item), 6)
        self.assertEqual(session.rules_manifestation_characteristics(item)["power"], 8)
        self.apply_ability(
            session, ENTRUST, targets=[self.target(item)], action_id="entrust-2",
        )
        self.assertEqual(session.rules_manifestation_base_power(item), 12)
        self.assertEqual(session.rules_manifestation_characteristics(item)["power"], 14)

        cleansed = session.apply_rules_action_result({
            "id": "cleanse", "controllerId": "p1",
            "source": {"cardId": "will-x"}, "targets": [self.target(item)],
            "ability": {"result": {"kind": "cleanse_target"}},
        })
        self.assertEqual(cleansed["status"], "cleansed")
        self.assertEqual(session.rules_manifestation_base_power(item), 3)

    def test_entrust_doubles_a_generic_token_base(self):
        session, _p1, _p2 = self.started()
        token = session.create_rules_token_copy(
            None, "p1", generic_power=2, generic_temperament="hollow",
        )
        self.apply_ability(session, ENTRUST, targets=[self.target(token)])
        self.assertEqual(session.rules_manifestation_base_power(token), 4)
        self.assertEqual(session.rules_manifestation_characteristics(token)["power"], 4)

    def test_punish_destroys_only_present_winning_participants_of_this_turn(self):
        session, p1, p2 = self.started()
        winner_a = self.active_item(session, "p1", "m-1", item_id="winner-a")
        winner_b = self.active_item(
            session, "p2", "m-2", item_id="winner-b", controller_id="p1",
        )
        loser = self.active_item(session, "p2", "m-3", item_id="loser")
        newcomer = self.active_item(session, "p1", "m-4", item_id="newcomer")
        session.rules_engine["confrontationResult"] = {
            "turn": 4, "winnerId": "p1", "loserId": "p2",
            "participantItemIds": ["winner-a", "winner-b", "loser", "departed"],
        }
        result = self.apply_ability(session, PUNISH, controller_id="p2")
        self.assertEqual(
            {entry["itemId"] for entry in result["destroyed"]},
            {"winner-a", "winner-b"},
        )
        self.assertIn("m-1", p1["zones"]["graveyard"])
        self.assertIn("m-2", p2["zones"]["graveyard"])
        self.assertIs(session.find_battlefield_item("loser"), loser)
        self.assertIs(session.find_battlefield_item("newcomer"), newcomer)

    def test_punish_is_mass_nontargeting_but_respects_immunity(self):
        session, p1, _p2 = self.started()
        protected = self.active_item(session, "p1", "m-1", item_id="protected")
        immune = self.active_item(session, "p1", "m-2", item_id="immune")
        session.rules_engine["ongoingEffects"] = [{
            "id": "protect", "kind": "protection", "duration": "until_end_of_turn",
            "startedTurn": 4, "fromOpponents": True,
            "target": {"kind": "card", "itemId": "protected"},
        }, {
            "id": "immune", "kind": "immune", "duration": "until_end_of_turn",
            "startedTurn": 4, "fromOpponents": True,
            "target": {"kind": "card", "itemId": "immune"},
        }]
        session.rules_engine["confrontationResult"] = {
            "turn": 4, "winnerId": "p1", "loserId": "p2",
            "participantItemIds": ["protected", "immune"],
        }
        result = self.apply_ability(session, PUNISH, controller_id="p2")
        self.assertEqual(
            [entry["itemId"] for entry in result["destroyed"]], ["protected"],
        )
        self.assertIn("m-1", p1["zones"]["graveyard"])
        self.assertIs(session.find_battlefield_item("immune"), immune)

    def damage_world(self, count):
        session, _p1, _p2 = self.started()
        items = []
        for index in range(count):
            card_id = f"m-{index + 1}"
            session.card_rules[card_id].update(power=5)
            items.append(self.active_item(
                session, "p2", card_id, item_id=f"target-{index + 1}",
                field_zone="interzone",
            ))
        return session, items

    def test_damage_distributes_exactly_three_across_one_two_or_three_targets(self):
        expected = {
            1: [2],
            2: [4, 3],
            3: [4, 4, 4],
        }
        for count in (1, 2, 3):
            with self.subTest(count=count):
                session, items = self.damage_world(count)
                result = self.apply_ability(
                    session, DAMAGE, targets=[self.target(item) for item in items],
                )
                if count == 2:
                    self.assertEqual(result["choiceKind"], "pick_distribution_extra")
                    choice = session.rules_engine["pendingChoice"]
                    error, _resolved = session.resolve_rules_choice(
                        "p1", choice["id"], item_id=items[1]["id"],
                    )
                    self.assertIsNone(error, error)
                self.assertEqual(
                    [session.rules_manifestation_characteristics(item)["power"]
                     for item in items], expected[count],
                )

    def test_damage_rejects_wrong_zone_controller_and_invalid_extra_choice_atomically(self):
        session, items = self.damage_world(2)
        rules = self.ABILITIES[DAMAGE][0]["targets"]
        own = self.active_item(
            session, "p1", "m-3", item_id="own", field_zone="interzone",
        )
        confrontation = self.active_item(
            session, "p2", "m-4", item_id="confrontation",
        )
        self.assertTrue(session.rules_ability_targets_error(
            rules, [self.target(own)], "p1",
        ))
        self.assertTrue(session.rules_ability_targets_error(
            rules, [self.target(confrontation)], "p1",
        ))
        self.apply_ability(
            session, DAMAGE, targets=[self.target(item) for item in items],
        )
        choice = session.rules_engine["pendingChoice"]
        error, result = session.resolve_rules_choice(
            "p1", choice["id"], item_id="own",
        )
        self.assertEqual(error, "Choose one of the targets.")
        self.assertIsNone(result)
        self.assertEqual(
            [session.rules_manifestation_characteristics(item)["power"]
             for item in items], [5, 5],
        )

    def test_damage_modifier_persists_while_target_stays_on_field(self):
        session, items = self.damage_world(1)
        self.apply_ability(session, DAMAGE, targets=[self.target(items[0])])
        session.phase_tracker["turn"] = 5
        session.prune_rules_ongoing_effects()
        self.assertEqual(session.rules_manifestation_characteristics(items[0])["power"], 2)

    def test_recall_exiles_manifestations_and_creates_hollow_effectless_supports_per_limbo(self):
        session, p1, p2 = self.started()
        session.card_rules["m-1"].update(power=3)
        self.put(p1, "graveyard", ["m-1", "m-2", "will-x"])
        self.put(p2, "graveyard", ["m-3"])
        result = self.apply_ability(session, RECALL)
        self.assertCountEqual(p1["zones"]["exile"], ["m-1", "m-2"])
        self.assertEqual(p2["zones"]["exile"], ["m-3"])
        self.assertEqual(p1["zones"]["graveyard"], ["will-x"])
        copies = [session.find_battlefield_item(item_id) for item_id in result["createdItemIds"]]
        self.assertEqual(
            [session.rules_item_controller_id(item) for item in copies].count("p1"), 2,
        )
        self.assertEqual(
            [session.rules_item_controller_id(item) for item in copies].count("p2"), 1,
        )
        self.assertTrue(all(item["isCopy"] and item["isTokenCopy"] for item in copies))
        self.assertTrue(all(item["effectsDisabled"] for item in copies))
        self.assertTrue(all(item["temperamentOverride"] == "hollow" for item in copies))
        self.assertTrue(all(item["isSupport"] for item in copies))
        copy_m1 = next(item for item in copies if item["cardId"] == "m-1")
        self.assertEqual(session.rules_manifestation_base_power(copy_m1), 3)
        self.assertNotIn("points", copy_m1)

    def test_recall_replacement_prevents_exile_and_copy(self):
        session, p1, _p2 = self.started()
        session.card_rules["bob"] = {
            "type": "manifestation", "power": 5,
            "temperaments": ["phlegmatic"],
            "suspensionThresholds": {"graveyard": 5},
        }
        self.active_item(session, "p1", "bob", item_id="bob")
        self.put(p1, "graveyard", ["m-1"])
        result = self.apply_ability(session, RECALL)
        self.assertEqual(result["createdItemIds"], [])
        self.assertEqual(p1["zones"]["exile"], [])
        self.assertEqual(
            [(entry["cardId"], entry["sourceEffectId"])
             for entry in session.rules_engine["suspendedCards"]],
            [("m-1", "bob")],
        )

    def test_recall_foreign_owned_card_exiles_to_owner_but_copy_stays_with_limbo_player(self):
        session, p1, p2 = self.started()
        self.put(p1, "graveyard", {"m-2": "p2"})
        result = self.apply_ability(session, RECALL)
        self.assertNotIn("m-2", p1["zones"]["exile"])
        self.assertEqual(p2["zones"]["exile"], ["m-2"])
        copy = session.find_battlefield_item(result["createdItemIds"][0])
        self.assertEqual(session.rules_item_controller_id(copy), "p1")
        self.assertEqual(copy["ownerId"], "p1")

    def test_extinguish_is_immediate_exiles_every_limbo_but_not_its_resolving_source(self):
        session, p1, p2 = self.started()
        session.card_rules["m-0"].update(
            power=4, temperaments=["choleric"],
        )
        self.put(p1, "hand", [EXTINGUISH, "m-0"])
        self.put(p1, "graveyard", ["m-1", "will-x"])
        self.put(p2, "graveyard", ["m-2", "m-3"])
        error, action = session.declare_rules_action(
            "p1", "Extinguish", kind="play_card",
            source={"cardId": EXTINGUISH, "zone": "hand"},
            payment_card_ids=["m-0"], ability_id="immediate-exile-all-limbos",
        )
        self.assertIsNone(error, error)
        self.assertTrue(action["immediate"])
        error, blocked = session.declare_rules_action(
            "p1", "Cannot respond", kind="manual",
        )
        self.assertIn("Immediate Effects", error)
        self.assertIsNone(blocked)
        error, blocked = session.pass_rules_priority("p1")
        self.assertIn("Immediate Effects", error)
        self.assertIsNone(blocked)
        resolution = session.resolve_rules_immediate_actions()[0]
        self.assertEqual(resolution["action"]["effectResult"]["kind"], "exile_all_limbos")
        self.assertEqual(p1["zones"]["graveyard"], [EXTINGUISH])
        self.assertCountEqual(p1["zones"]["exile"], ["m-0", "m-1", "will-x"])
        self.assertCountEqual(p2["zones"]["exile"], ["m-2", "m-3"])

    def test_extinguish_limbo_exit_replacement_prevents_exile(self):
        session, p1, _p2 = self.started()
        session.card_rules["bob"] = {
            "type": "manifestation", "power": 5,
            "temperaments": ["phlegmatic"],
            "suspensionThresholds": {"graveyard": 5},
        }
        self.active_item(session, "p1", "bob", item_id="bob")
        self.put(p1, "graveyard", ["m-1", "will-x"])
        result = self.apply_ability(session, EXTINGUISH)
        self.assertEqual(result["cardIdsByPlayer"]["p1"], [])
        self.assertEqual(p1["zones"]["exile"], [])
        self.assertCountEqual(
            [entry["cardId"] for entry in session.rules_engine["suspendedCards"]],
            ["m-1", "will-x"],
        )

    def test_extinguish_foreign_owned_card_exiles_to_immutable_owner(self):
        session, p1, p2 = self.started()
        self.put(p1, "graveyard", {"m-2": "p2"})
        self.apply_ability(session, EXTINGUISH)
        self.assertEqual(p1["zones"]["graveyard"], [])
        self.assertEqual(p1["zones"]["exile"], [])
        self.assertEqual(p2["zones"]["exile"], ["m-2"])

