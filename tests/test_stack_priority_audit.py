"""Rules 2.2 / 2.3 / 3.1 regressions from the stack and priority audit."""
import asyncio
import itertools

import test_game_state as game_tests
import main as server_main
from session import ADVANCED_PHASES


class StackPriorityAuditTests(game_tests.RealCardRulesCase):
    JUGGERNUT = "inner-deserts-100"
    GUMMO = "hcgvp7lbadlng1h_en"
    ARENA = "4phs0d8l223jk7t_en"
    ATAVIC = "265f4wdooq43pjn_en"
    SOUP = "s4dofvhan101mew_en"
    OBELISK = "9bkn03sc9veaa88_en"
    ZOMBIE = "bu1y6jwy7iaywqu_en"
    ALL = (JUGGERNUT, GUMMO, ARENA, ATAVIC, SOUP, OBELISK, ZOMBIE)

    def started(self, phase="confrontation_reaction", priority="p1"):
        session, p1, p2 = self.make_session()
        session.rules_engine.update(readyPlayerIds=["p1", "p2"], firstManifestationComplete=True,
                                    priorityPlayerId=priority, autoSkipPhases=True)
        session.phase_tracker["index"] = ADVANCED_PHASES.index(phase)
        session.battlefield = [self.field_item("first-a", "p1", "m-0"), self.field_item("first-b", "p2", "m-1")]
        session.rules_engine["firstManifestationItemIds"] = {"p1": "first-a", "p2": "first-b"}
        return session, p1, p2

    @staticmethod
    def pending_action(controller="p2"):
        return {"id": "pending", "label": "Pending effect", "kind": "triggered_effect", "controllerId": controller,
                "source": {"cardId": "m-0", "ownerId": controller}, "targets": [],
                "ability": {"id": "pending", "result": {"kind": "score_owner", "value": 1}}}

    def test_phase_specific_activations_prevent_auto_pass_and_can_be_paid(self):
        for cid, ability_id, phase, zone, cost in [
            (self.JUGGERNUT, "juggernut-charges-into-confrontation", "recovery_end", "field", 2),
            (self.GUMMO, "gummo-becomes-first-manifestation", "recovery_end", "interzone", 3),
            (self.ARENA, "wretched-arena-locks-support-entries", "confrontation_before_revelation", "field", 3),
        ]:
            for paid in [False, True]:
                with self.subTest(card=cid, paid=paid):
                    session, p1, _ = self.started(phase)
                    if phase == "recovery_end":
                        session.rules_engine.update(firstManifestationComplete=False, firstManifestationItemIds={})
                        session.battlefield = []
                    session.battlefield.append(self.field_item("source", "p1", cid, zone))
                    if paid:
                        session.add_rules_excess_essence("p1", [{"temperament": "hollow", "amount": cost}])
                    self.assertEqual(session.rules_player_can_act("p1"), paid)
                    self.assertEqual(session.rules_auto_pass_player(), None if paid else "p1")
                    if paid:
                        self.assertEqual(asyncio.run(server_main.auto_advance_rules_phases(session, "p1")), 0)
                        self.assertEqual(session.current_phase_id(), phase)
                        error, _ = session.declare_rules_action("p1", "Activate", kind="activated_effect",
                            source={"cardId": cid, "zone": "battlefield", "itemId": "source"}, ability_id=ability_id)
                        self.assertIsNone(error)
                        session.resolve_rules_top_action()
                        if cid in {self.JUGGERNUT, self.GUMMO}:
                            self.assertEqual(session.find_battlefield_item("source")["fieldZone"], "confrontation")

    def test_persistent_timing_and_empty_stack_rule_including_soup_and_juggernut(self):
        for cid, soup, phase, occupied in itertools.product(
            [self.ATAVIC, self.ARENA, self.JUGGERNUT], [False, True],
            ["end_actions", "confrontation_before_revelation", "confrontation_reaction"], [False, True],
        ):
            with self.subTest(card=cid, soup=soup, phase=phase, occupied=occupied):
                session, p1, _ = self.started(phase)
                self.put(p1, "hand", [cid])
                if soup:
                    session.battlefield.append(self.field_item("soup", "p1", self.SOUP, "interzone"))
                if occupied:
                    session.rules_engine["actionStack"] = [self.pending_action()]
                session.add_rules_excess_essence("p1", [{"temperament": color, "amount": 10}
                    for color in ["hollow", "phlegmatic", "choleric", "melancholic", "vitreous", "capricious"]])
                phase_ok = phase == "end_actions" or (phase == "confrontation_before_revelation" and cid == self.ATAVIC) or (phase == "confrontation_reaction" and soup)
                expected = phase_ok and (not occupied or soup)
                error, played = session.declare_rules_action("p1", "Play", kind="play_card", source={"cardId": cid, "zone": "hand"})
                self.assertEqual(error is None, expected, error)
                self.assertEqual(played is not None, expected)
                if not expected:
                    self.assertIn(cid, p1["zones"]["hand"])
                    self.assertEqual(len(session.rules_engine["actionStack"]), int(occupied))

    def test_unanswerable_persistent_will_does_not_hold_auto_resolution_open(self):
        session, p1, _ = self.started("end_actions")
        self.put(p1, "hand", [self.ATAVIC])
        session.rules_engine["actionStack"] = [self.pending_action()]
        self.assertFalse(session.rules_player_can_act("p1"))
        self.assertEqual(session.rules_auto_pass_player(), "p1")
        session.battlefield.append(self.field_item("soup", "p1", self.SOUP, "interzone"))
        self.assertTrue(session.rules_player_can_act("p1"))
        self.assertIsNone(session.rules_auto_pass_player())

    def test_optional_simultaneous_effects_preserve_initial_priority_in_either_source_order(self):
        for initial, order in itertools.product(["p1", "p2"], [("p1", "p2"), ("p2", "p1")]):
            with self.subTest(initial=initial, order=order):
                session, p1, p2 = self.started(priority=initial)
                session.battlefield += [self.field_item(f"obelisk-{pid}", pid, self.OBELISK, "field") for pid in order]
                for player in [p1, p2]:
                    self.put(player, "hand", ["m-2"])
                session.queue_rules_reaction_triggers()
                for chooser in order:
                    choice = session.rules_engine["pendingChoice"]
                    self.assertEqual((choice["kind"], choice["playerId"]), ("optional_stack_action", chooser))
                    self.assertEqual(choice["_priorityPlayerId"], initial)
                    error, _ = session.resolve_rules_choice(chooser, choice["id"], option="accept")
                    self.assertIsNone(error)
                self.assertIsNone(session.rules_engine["pendingChoice"])
                stack = session.rules_engine["actionStack"]
                self.assertEqual([a["controllerId"] for a in stack], [initial, session.other_rules_player_id(initial)])
                self.assertEqual(session.rules_engine["priorityPlayerId"], initial)
                # The gift is still selected at resolution, after the response window.
                session.resolve_rules_top_action()
                self.assertEqual(session.rules_engine["pendingChoice"]["destination"], "obelisk_gift")

    def test_optional_target_pickers_also_preserve_the_batch_priority(self):
        for initial in ["p1", "p2"]:
            session, p1, p2 = self.started(priority=initial)
            batch = []
            for player, candidate in [(p1, "m-2"), (p2, "m-3")]:
                self.put(player, "graveyard", [self.ZOMBIE, candidate])
                batch += session.queue_rules_triggers(self.ZOMBIE, player["id"], "enters_limbo", zone="graveyard",
                    container_id=player["id"], controller_id=player["id"], defer=True)
            session.queue_rules_simultaneous_actions(batch)
            for pid, candidate in [("p1", "m-2"), ("p2", "m-3")]:
                choice = session.rules_engine["pendingChoice"]
                self.assertEqual(choice["kind"], "optional_stack_action")
                self.assertIsNone(session.resolve_rules_choice(pid, choice["id"], option="accept")[0])
                choice = session.rules_engine["pendingChoice"]
                self.assertEqual(choice["kind"], "trigger_targets")
                self.assertIsNone(session.resolve_rules_choice(pid, choice["id"], targets=[{
                    "kind": "zone_card", "containerId": pid, "zone": "graveyard", "cardId": candidate,
                }])[0])
            self.assertEqual([a["controllerId"] for a in session.rules_engine["actionStack"]],
                             [initial, session.other_rules_player_id(initial)])
