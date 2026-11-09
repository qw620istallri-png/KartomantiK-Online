"""Strict semantic coverage for five reactive continuous-effect cards."""

import copy

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


OUTCAST = "h67753m250gg2h6_en"
SOUP = "s4dofvhan101mew_en"
MASS = "6vxm454ffuni41x_en"
HONOR = "y4muuingw5y9l7z_en"
LIFE = "my6shp6k59b1eig_en"
WEAKEN = "bithch9c4vi77cu_en"

EXPECTED_ABILITIES = {
    OUTCAST: [{
        "id": "wandering-outcast-swaps-with-targeted",
        "passiveEffect": {
            "kind": "swap_with_targeted_confrontation_manifestation",
        },
    }],
    SOUP: [{
        "id": "soup-persistent-wills-at-ephemeral-timing",
        "passiveEffect": {"kind": "persistent_wills_as_ephemeral"},
    }],
    MASS: [{
        "id": "redirect-opponent-targeting",
        "passiveEffect": {
            "kind": "redirect_opponent_targeting_to_source",
        },
    }],
    HONOR: [{
        "id": "gain-ten-when-winning-with-a-single-manifestation",
        "passiveEffect": {
            "kind": "solo_confrontation_win_points", "value": 10,
        },
    }],
    LIFE: [{
        "id": "sustain-manifestations-at-exact-zero",
        "passiveEffect": {"kind": "sustain_exact_zero"},
    }],
}


class ReactivePassivesFamily(RealCardRulesCase):
    ALL = (OUTCAST, SOUP, MASS, HONOR, LIFE)

    def started(self):
        session, p1, p2 = self.make_session()
        session.phase_tracker.update(
            index=ADVANCED_PHASES.index("confrontation_reaction"), turn=6,
        )
        session.rules_engine.update(
            readyPlayerIds=["p1", "p2"],
            priorityPlayerId="p1",
            firstManifestationComplete=True,
        )
        return session, p1, p2

    @staticmethod
    def target(item):
        return {
            "kind": "card", "itemId": item["id"],
            "cardId": item["cardId"], "ownerId": item["ownerId"],
        }

    def add_weaken(self, session, player):
        session.card_rules[WEAKEN] = {
            "type": "ephemeral_will", "cost": 0, "powerCost": "",
            "temperaments": ["phlegmatic"],
            "playedAbilities": self.ABILITIES[WEAKEN],
        }
        self.put(player, "hand", [WEAKEN])

    @staticmethod
    def add_persistent_probe(session, player, *, empty_stack_only=False):
        card_id = "persistent-probe"
        session.card_rules[card_id] = {
            "type": "persistent_will", "cost": 0, "powerCost": "",
            "temperaments": ["phlegmatic"],
            "playOnlyEmptyStack": empty_stack_only,
        }
        ReactivePassivesFamily.put(player, "hand", [card_id])
        return card_id

    def forced_confrontation(self, session, winner_id="p1"):
        session.phase_tracker["index"] = ADVANCED_PHASES.index(
            "resolution_compare"
        )
        session.rules_engine["forcedConfrontationWinnerId"] = winner_id
        return session.prepare_rules_confrontation_result()

    def test_compiles_all_five_exact_contracts(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        for card_id, abilities in EXPECTED_ABILITIES.items():
            with self.subTest(card_id=card_id):
                self.assertEqual(self.ABILITIES[card_id], abilities)
                self.assertEqual(
                    rules[card_id]["passiveEffects"],
                    [ability["passiveEffect"] for ability in abilities],
                )

    def test_outcast_acceptance_swaps_the_complete_position_and_target(self):
        session, _p1, _p2 = self.started()
        outcast = self.field_item(
            "outcast", "p1", OUTCAST, "interzone",
            x=100, y=200, stackedOn="anchor", stackOffsetX=4,
        )
        victim = self.field_item(
            "victim", "p1", "m-1", "confrontation",
            x=500, y=600, confrontationOrder=2,
        )
        child = self.field_item(
            "child", "p1", "m-2", "interzone", stackedOn="victim",
        )
        session.battlefield = [outcast, victim, child]

        redirected = session.rules_redirect_targets(
            "p2", [self.target(victim)], source_card_id=WEAKEN,
        )

        self.assertEqual([target["itemId"] for target in redirected], ["outcast"])
        self.assertEqual(session.rules_field_zone(outcast), "confrontation")
        self.assertEqual((outcast["x"], outcast["y"]), (500, 600))
        self.assertEqual(outcast["confrontationOrder"], 2)
        self.assertEqual(session.rules_field_zone(victim), "interzone")
        self.assertEqual((victim["x"], victim["y"]), (100, 200))
        self.assertEqual(victim["stackedOn"], "anchor")
        self.assertEqual(child["stackedOn"], "outcast")

    def test_outcast_real_declaration_can_be_declined_without_mutating_payment(self):
        session, _p1, p2 = self.started()
        outcast = self.field_item("outcast", "p1", OUTCAST, "interzone")
        victim = self.field_item("victim", "p1", "m-1", "confrontation")
        session.battlefield = [outcast, victim]
        self.add_weaken(session, p2)
        session.rules_engine["priorityPlayerId"] = "p2"
        before = copy.deepcopy((session.players, session.battlefield, session.tokens))

        error, proposal = session.declare_rules_action(
            "p2", "Weaken", kind="play_card",
            source={"cardId": WEAKEN, "zone": "hand"},
            targets=[self.target(victim)],
            ability_id="weaken-power-modifier",
        )

        self.assertIsNone(error, error)
        self.assertEqual(proposal["status"], "choice_required")
        self.assertEqual((session.players, session.battlefield, session.tokens), before)
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(
            (choice["playerId"], choice["purpose"], choice["incomingCardId"]),
            ("p1", "outcast_swap", WEAKEN),
        )
        self.assertIsNotNone(
            session.resolve_rules_choice("p2", choice["id"], option="no")[0]
        )
        error, _result = session.resolve_rules_choice(
            "p1", choice["id"], option="no",
        )
        self.assertIsNone(error, error)
        self.assertEqual(len(session.rules_engine["actionStack"]), 1)
        self.assertEqual(
            session.rules_engine["actionStack"][0]["targets"][0]["itemId"],
            "victim",
        )
        self.assertEqual(session.rules_field_zone(outcast), "interzone")
        self.assertEqual(session.rules_field_zone(victim), "confrontation")

    def test_outcast_requires_opposing_effect_eligible_source_and_confrontation_target(self):
        cases = (
            ("own-effect", "p1", "confrontation", "manifestation", {}),
            ("target-interzone", "p2", "interzone", "manifestation", {}),
            ("target-will", "p2", "confrontation", "persistent_will", {}),
            ("source-disabled", "p2", "confrontation", "manifestation", {"effectsDisabled": True}),
            ("preference-off", "p2", "confrontation", "manifestation", {"outcastOff": True}),
        )
        for label, actor, target_zone, target_type, source_extra in cases:
            with self.subTest(label=label):
                session, _p1, _p2 = self.started()
                session.card_rules["target-probe"] = {
                    "type": target_type, "power": 1,
                    "temperaments": ["phlegmatic"],
                }
                outcast = self.field_item(
                    "outcast", "p1", OUTCAST, "interzone", **source_extra,
                )
                victim = self.field_item(
                    "victim", "p1", "target-probe", target_zone,
                )
                session.battlefield = [outcast, victim]
                self.assertEqual(
                    session.rules_redirect_targets(actor, [self.target(victim)]),
                    [self.target(victim)],
                )

    def test_soup_allows_a_real_persistent_will_response_only_for_its_controller(self):
        for actor, soup_controller, expected_error in (
            ("p1", "p1", False),
            ("p2", "p1", True),
        ):
            with self.subTest(actor=actor):
                session, p1, p2 = self.started()
                player = p1 if actor == "p1" else p2
                probe = self.add_persistent_probe(session, player)
                soup = self.field_item(
                    "soup", soup_controller, SOUP, "interzone",
                )
                session.battlefield = [soup]
                session.rules_engine["actionStack"] = [{
                    "id": "existing", "controllerId": "p2",
                    "source": {"cardId": "will-x", "zone": "hand"},
                    "targets": [], "ability": {},
                }]
                session.rules_engine["priorityPlayerId"] = actor
                error, action = session.declare_rules_action(
                    actor, "Persistent response", kind="play_card",
                    source={"cardId": probe, "zone": "hand"},
                )
                if expected_error:
                    self.assertIn("Persistent Will", error)
                    self.assertIsNone(action)
                    self.assertIn(probe, player["zones"]["hand"])
                else:
                    self.assertIsNone(error, error)
                    self.assertEqual(action["source"]["cardId"], probe)
                    self.assertNotIn(probe, player["zones"]["hand"])

    def test_soup_requires_an_active_interzone_source_and_keeps_empty_stack_limits(self):
        cases = (
            ("absent", None, {}),
            ("confrontation", "confrontation", {}),
            ("face-down", "interzone", {"faceUp": False}),
            ("disabled", "interzone", {"effectsDisabled": True}),
        )
        for label, zone, extra in cases:
            with self.subTest(label=label):
                session, p1, _p2 = self.started()
                probe = self.add_persistent_probe(session, p1)
                session.battlefield = (
                    [] if zone is None else [self.field_item(
                        "soup", "p1", SOUP, zone, **extra,
                    )]
                )
                session.rules_engine["actionStack"] = [{"id": "existing"}]
                error, _action = session.declare_rules_action(
                    "p1", "Persistent response", kind="play_card",
                    source={"cardId": probe, "zone": "hand"},
                )
                self.assertIn("Persistent Will", error)

        session, p1, _p2 = self.started()
        probe = self.add_persistent_probe(
            session, p1, empty_stack_only=True,
        )
        session.battlefield = [self.field_item(
            "soup", "p1", SOUP, "interzone",
        )]
        session.rules_engine["actionStack"] = [{"id": "existing"}]
        error, _action = session.declare_rules_action(
            "p1", "Restricted response", kind="play_card",
            source={"cardId": probe, "zone": "hand"},
        )
        self.assertIn("Stack is empty", error)

    def test_mass_redirects_only_opposing_targets_of_allied_manifestations(self):
        session, _p1, _p2 = self.started()
        mass = self.field_item("mass", "p1", MASS, "interzone")
        ally = self.field_item("ally", "p1", "m-1", "confrontation")
        enemy = self.field_item("enemy", "p2", "m-2", "confrontation")
        session.battlefield = [mass, ally, enemy]

        self.assertEqual(
            session.rules_redirect_targets("p2", [self.target(ally)]),
            [self.target(mass)],
        )
        self.assertEqual(
            session.rules_redirect_targets("p1", [self.target(ally)]),
            [self.target(ally)],
        )
        self.assertEqual(
            session.rules_redirect_targets("p1", [self.target(enemy)]),
            [self.target(enemy)],
        )
        self.assertEqual(
            session.rules_redirect_targets("p2", [self.target(mass)]),
            [self.target(mass)],
        )

    def test_mass_does_not_redirect_a_will_and_deduplicates_multiple_redirects(self):
        session, _p1, _p2 = self.started()
        session.card_rules["will-probe"] = {"type": "persistent_will"}
        mass = self.field_item("mass", "p1", MASS, "field")
        first = self.field_item("first", "p1", "m-1", "confrontation")
        second = self.field_item("second", "p1", "m-2", "interzone")
        will = self.field_item("will", "p1", "will-probe", "field")
        session.battlefield = [mass, first, second, will]

        self.assertEqual(
            session.rules_redirect_targets("p2", [self.target(will)]),
            [self.target(will)],
        )
        self.assertEqual(
            session.rules_redirect_targets(
                "p2", [self.target(first), self.target(second)],
            ),
            [self.target(mass)],
        )

    def test_mass_requires_an_active_retargetable_source_and_follows_control(self):
        for label, extra in (
            ("face-down", {"faceUp": False}),
            ("disabled", {"effectsDisabled": True}),
            ("stalemate", {"fieldZone": "stalemate"}),
        ):
            with self.subTest(label=label):
                session, _p1, _p2 = self.started()
                mass = self.field_item(
                    "mass", "p1", MASS, "field", **extra,
                )
                ally = self.field_item("ally", "p1", "m-1")
                session.battlefield = [mass, ally]
                self.assertEqual(
                    session.rules_redirect_targets("p2", [self.target(ally)]),
                    [self.target(ally)],
                )

        session, _p1, _p2 = self.started()
        mass = self.field_item("mass", "p1", MASS, "field")
        ally = self.field_item("ally", "p1", "m-1")
        session.battlefield = [mass, ally]
        session.rules_engine["ongoingEffects"].append({
            "id": "mass-immunity", "kind": "immune",
            "target": {"itemId": "mass"}, "fromOpponents": True,
        })
        self.assertEqual(
            session.rules_redirect_targets("p2", [self.target(ally)]),
            [self.target(ally)],
        )

        session, _p1, _p2 = self.started()
        mass = self.field_item(
            "mass", "p1", MASS, "field", controllerId="p2",
        )
        new_ally = self.field_item(
            "new-ally", "p2", "m-2", "confrontation",
        )
        old_ally = self.field_item(
            "old-ally", "p1", "m-1", "confrontation",
        )
        session.battlefield = [mass, new_ally, old_ally]
        self.assertEqual(
            session.rules_redirect_targets("p1", [self.target(new_ally)]),
            [self.target(mass)],
        )
        self.assertEqual(
            session.rules_redirect_targets("p2", [self.target(old_ally)]),
            [self.target(old_ally)],
        )

    def test_honor_scores_ten_only_for_exactly_one_winning_manifestation(self):
        for winner_count, expected_score in ((1, 10), (2, 0)):
            with self.subTest(winner_count=winner_count):
                session, p1, _p2 = self.started()
                session.battlefield = [
                    self.field_item("honor", "p1", HONOR, "field"),
                    self.field_item("foe", "p2", "m-9", "confrontation"),
                ] + [
                    self.field_item(
                        f"winner-{index}", "p1", f"m-{index}",
                        "confrontation",
                    )
                    for index in range(winner_count)
                ]
                result = self.forced_confrontation(session)
                self.assertEqual(p1["score"], expected_score)
                self.assertEqual(
                    len(result.get("automaticEffects") or []),
                    1 if winner_count == 1 else 0,
                )

    def test_honor_sources_stack_but_only_for_the_winner_and_while_active(self):
        session, p1, p2 = self.started()
        session.battlefield = [
            self.field_item("honor-a", "p1", HONOR, "field"),
            self.field_item("honor-b", "p1", HONOR, "interzone"),
            self.field_item(
                "honor-disabled", "p1", HONOR, "field",
                effectsDisabled=True,
            ),
            self.field_item("honor-foe", "p2", HONOR, "field"),
            self.field_item("winner", "p1", "m-1", "confrontation"),
            self.field_item("loser", "p2", "m-2", "confrontation"),
        ]
        result = self.forced_confrontation(session)
        self.assertEqual((p1["score"], p2["score"]), (20, 0))
        self.assertEqual(len(result["automaticEffects"]), 2)

    def test_life_sustains_exact_zero_and_permanently_removes_effects(self):
        session, _p1, _p2 = self.started()
        session.card_rules["effectful"] = {
            "type": "manifestation", "power": 1,
            "temperaments": ["phlegmatic"], "persist": True,
            "activatedAbilities": [{"id": "probe"}],
        }
        life = self.field_item("life", "p1", LIFE, "field")
        target = self.field_item("target", "p2", "effectful")
        target["counters"]["power"] = -1
        session.battlefield = [life, target]

        state = session.resolve_rules_state_actions({"target": 1})

        self.assertEqual(state["destroyed"], [])
        self.assertEqual(state["replacements"][0]["replacement"], "sustain_exact_zero")
        self.assertTrue(target["effectsDisabled"])
        self.assertTrue(target["zeroPowerSustained"])
        self.assertFalse(session.rules_item_has_persist(target))
        target["counters"]["power"] = 2
        session.resolve_rules_state_actions({"target": 0})
        self.assertIn(target, session.battlefield)
        self.assertTrue(target["effectsDisabled"])

    def test_life_destroys_below_zero_and_exact_zero_without_an_active_source(self):
        cases = (
            ("below-zero", -2, "field", True, True),
            ("source-absent", -1, None, True, True),
            ("source-face-down", -1, "field", False, True),
            ("exact-zero-active", -1, "field", True, False),
        )
        for label, counter, zone, face_up, destroyed in cases:
            with self.subTest(label=label):
                session, _p1, p2 = self.started()
                target = self.field_item("target", "p2", "m-1")
                target["counters"]["power"] = counter
                session.battlefield = [target]
                if zone is not None:
                    session.battlefield.insert(0, self.field_item(
                        "life", "p1", LIFE, zone, faceUp=face_up,
                    ))
                state = session.resolve_rules_state_actions({"target": 1})
                self.assertEqual(
                    session.find_battlefield_item("target") is None,
                    destroyed,
                )
                self.assertEqual(bool(state["destroyed"]), destroyed)
                if destroyed:
                    self.assertIn("m-1", p2["zones"]["graveyard"])

    def test_life_is_global_applies_to_tokens_and_ends_for_sustained_zero_cards(self):
        session, _p1, _p2 = self.started()
        life = self.field_item("life", "p1", LIFE, "interzone")
        token = self.field_item(
            "token", "p2", "token-card", "confrontation",
            isTokenCard=True, basePower=0,
        )
        session.battlefield = [life, token]
        session.resolve_rules_state_actions({"token": 1})
        self.assertIn(token, session.battlefield)
        self.assertTrue(token["effectsDisabled"])

        session.battlefield.remove(life)
        state = session.resolve_rules_state_actions({"token": 0})
        self.assertIsNone(session.find_battlefield_item("token"))
        self.assertEqual(state["destroyed"][0]["itemId"], "token")


if __name__ == "__main__":
    import unittest

    unittest.main()
