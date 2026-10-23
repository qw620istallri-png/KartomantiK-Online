import asyncio
import unittest

import test_auto_pass as auto_pass_tests
import main as server_main


class InvalidStackAutoResolutionTests(unittest.TestCase):
    make_session = auto_pass_tests.AutoPassTests.make_session
    goto = auto_pass_tests.AutoPassTests.goto

    def started(self):
        session, p1, p2 = self.make_session()
        self.goto(session, "confrontation_reaction")
        session.rules_engine["autoSkipPhases"] = False
        for player in (p1, p2):
            player["zones"]["hand"] = ["will-ephemeral", "m-5"]
            player["zoneOwners"]["hand"] = {cid: player["id"] for cid in player["zones"]["hand"]}
        session.battlefield = [{
            "id": "target", "cardId": "m-1", "ownerId": "p2", "faceUp": True,
            "fieldZone": "confrontation", "x": 0, "y": 0, "rotation": 0, "counters": {},
        }]
        action = {
            "id": "doomed", "label": "Targeted effect", "controllerId": "p1",
            "kind": "triggered_effect", "source": {"cardId": "m-0", "ownerId": "p1"},
            "targets": [{"kind": "card", "itemId": "target", "cardId": "m-1"}],
            "ability": {"id": "targeted", "targets": {"min": 1, "max": 1, "cardType": "manifestation"},
                        "ongoingEffect": {"kind": "power_modifier", "value": 2, "duration": "until_end_of_turn"}},
        }
        session.rules_engine["actionStack"] = [action]
        return session, action

    def advance(self, session):
        return asyncio.run(server_main.auto_advance_rules_phases(session, "p2"))

    def test_missing_target_resolves_once_without_passes_or_refunding_the_will(self):
        session, action = self.started()
        session.card_rules["doomed-will"] = {"type": "ephemeral_will"}
        action.update(kind="play_card", sourceOnStack=True,
                      source={"zone": "hand", "cardId": "doomed-will", "ownerId": "p1", "cardType": "ephemeral_will"})
        session.battlefield = []
        session.rules_engine["priorityPasses"] = ["p2"]
        self.assertEqual(self.advance(session), 1)
        self.assertEqual(session.rules_engine["actionStack"], [])
        self.assertEqual(action["effectResult"]["kind"], "invalid_targets")
        self.assertEqual(session.players["p1"]["zones"]["graveyard"], ["doomed-will"])
        self.assertEqual(session.current_phase_id(), "confrontation_reaction")
        self.assertEqual(session.rules_engine["priorityPasses"], [])
        self.assertEqual(self.advance(session), 0)
        resolved_logs = [entry for entry in session.log if entry.get("type") == "rules_action_resolved"]
        self.assertEqual(len(resolved_logs), 1)

    def test_target_that_no_longer_meets_power_requirement_resolves_automatically(self):
        session, action = self.started()
        action["ability"]["targets"]["maxPower"] = 1
        session.battlefield[0]["counters"]["power"] = 1
        self.assertEqual(self.advance(session), 1)
        self.assertEqual(action["effectResult"]["kind"], "invalid_targets")
        self.assertEqual(session.rules_engine["ongoingEffects"], [])

    def test_valid_target_or_untargeted_effect_still_allows_responses(self):
        for targeted in (True, False):
            with self.subTest(targeted=targeted):
                session, action = self.started()
                if not targeted:
                    action["targets"] = []
                    action["ability"].pop("targets")
                self.assertEqual(self.advance(session), 0)
                self.assertEqual(session.rules_engine["actionStack"], [action])

    def test_one_remaining_legal_target_preserves_response_window(self):
        for grouped in (False, True):
            with self.subTest(grouped=grouped):
                session, action = self.started()
                action["targets"].append({"kind": "card", "itemId": "missing", "cardId": "m-2"})
                if grouped:
                    action["ability"]["targetGroups"] = [dict(action["ability"]["targets"])] * 2
                else:
                    action["ability"]["targets"].update(min=2, max=2)
                self.assertEqual(self.advance(session), 0)
                self.assertEqual(session.rules_engine["actionStack"], [action])

    def test_all_invalid_targets_resolve_for_single_and_grouped_contracts(self):
        for grouped in (False, True):
            with self.subTest(grouped=grouped):
                session, action = self.started()
                action["targets"].append({"kind": "card", "itemId": "missing", "cardId": "m-2"})
                if grouped:
                    action["ability"]["targetGroups"] = [dict(action["ability"]["targets"])] * 2
                else:
                    action["ability"]["targets"].update(min=2, max=2)
                session.battlefield = []
                self.assertEqual(self.advance(session), 1)
                self.assertEqual(action["effectResult"]["kind"], "invalid_targets")

    def test_an_invalid_effect_below_a_valid_top_is_not_removed_early(self):
        session, action = self.started()
        action["targets"][0]["itemId"] = "missing"
        valid = {**action, "id": "valid", "targets": [{"kind": "card", "itemId": "target", "cardId": "m-1"}]}
        session.rules_engine["actionStack"].append(valid)
        self.assertEqual(self.advance(session), 0)
        self.assertEqual(session.rules_engine["actionStack"], [action, valid])

    def test_missing_limbo_and_stack_targets_resolve_automatically(self):
        for kind in ("zone_card", "stack_action"):
            with self.subTest(kind=kind):
                session, action = self.started()
                action["ability"]["targets"] = {"kind": kind, "min": 1, "max": 1}
                if kind == "zone_card":
                    action["ability"]["targets"]["zones"] = ["graveyard"]
                    action["targets"] = [{"kind": kind, "containerId": "p2", "ownerId": "p2", "zone": "graveyard", "cardId": "m-2"}]
                else:
                    action["targets"] = [{"kind": kind, "actionId": "gone"}]
                self.assertEqual(self.advance(session), 1)
                self.assertEqual(action["effectResult"]["kind"], "invalid_targets")

    def test_pending_choice_ended_game_or_manual_mode_prevents_automatic_resolution(self):
        for condition in ("choice", "ended", "manual"):
            with self.subTest(condition=condition):
                session, action = self.started()
                session.battlefield = []
                if condition == "choice":
                    session.rules_engine["pendingChoice"] = {"id": "wait", "playerId": "p1", "kind": "binary_choice"}
                elif condition == "ended":
                    session.ended = True
                else:
                    session.rules_engine["enabled"] = False
                self.assertEqual(self.advance(session), 0)
                self.assertEqual(session.rules_engine["actionStack"], [action])
