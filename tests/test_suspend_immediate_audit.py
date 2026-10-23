"""Suspend permissions and Immediate Effect priority invariants."""
import asyncio
import copy

import test_game_state as game_tests
import main as server_main
from session import ADVANCED_PHASES


class SuspendImmediateAuditTests(game_tests.RealCardRulesCase):
    ALL = ("inner-deserts-088", "inner-deserts-094", "inner-deserts-115", "inner-deserts-125")

    def started(self, phase="confrontation_reaction"):
        session, p1, p2 = self.make_session()
        session.rules_engine.update(readyPlayerIds=["p1", "p2"], firstManifestationComplete=True,
                                    priorityPlayerId="p1", autoSkipPhases=True)
        session.phase_tracker["index"] = ADVANCED_PHASES.index(phase)
        return session, p1, p2

    def suspended_will(self):
        session, p1, p2 = self.started()
        session.card_rules["suspended-will"] = {"type": "ephemeral_will", "cost": 3, "powerCost": "{R}{R}{R}", "temperaments": ["choleric"],
            "playedAbilities": [{"id": "suspended-score", "action": "play_card", "targets": {"min": 0, "max": 0}, "result": {"kind": "score_owner", "value": 5}}]}
        self.put(p2, "hand", ["suspended-will"])
        error, suspended = session.suspend_zone_card("p2", "hand", "suspended-will", source_effect_id="gobres",
            playableByPlayerId="p1", returnZone="hand", returnTurn=1, anyTemperamentTribute=True)
        self.assertIsNone(error)
        session.add_rules_excess_essence("p1", [{"temperament": "phlegmatic", "amount": 3}])
        return session, p1, p2, suspended

    def test_playable_suspended_will_holds_priority_and_accepts_any_temperament(self):
        session, p1, p2, suspended = self.suspended_will()
        self.assertTrue(session.rules_player_can_act("p1"))
        self.assertIsNone(session.rules_auto_pass_player())
        error, action = session.declare_rules_action("p1", "Play suspended Will", kind="play_card",
            source={"cardId": "suspended-will", "zone": "suspended", "suspensionId": suspended["id"]}, ability_id="suspended-score")
        self.assertIsNone(error)
        self.assertEqual(action["source"]["ownerId"], "p2")
        self.assertFalse(session.rules_engine["suspendedCards"])
        for viewer, role in [("p1", "player"), ("p2", "player"), (None, "spectator")]:
            self.assertEqual(session.serialize_for(viewer, role)["rulesEngine"]["actionStack"][0]["source"].get("cardId"), "suspended-will")
        session.resolve_rules_top_action()
        self.assertIn("suspended-will", p2["zones"]["graveyard"])
        self.assertEqual(p1["score"], 5)

    def test_stale_suspension_id_cannot_select_a_different_permission(self):
        session, _, _, _suspended = self.suspended_will()
        before = copy.deepcopy((session.players, session.tokens, session.rules_engine))
        error, action = session.declare_rules_action("p1", "Stale suspension", kind="play_card",
            source={"cardId": "suspended-will", "zone": "suspended", "suspensionId": "obsolete"}, ability_id="suspended-score")
        self.assertIsNotNone(error)
        self.assertIsNone(action)
        self.assertEqual((session.players, session.tokens, session.rules_engine), before)

    def test_priority_pass_cannot_open_a_response_window_above_an_immediate(self):
        session, _, _ = self.started()
        session.rules_engine["actionStack"] = [self.action("immediate", True)]
        before = copy.deepcopy(session.rules_engine)
        error, result = session.pass_rules_priority("p1")
        self.assertIsNotNone(error)
        self.assertIsNone(result)
        self.assertEqual(session.rules_engine, before)

    def test_suspended_persistent_will_keeps_its_timing_restriction(self):
        session, _, _, _ = self.suspended_will()
        session.card_rules["suspended-will"]["type"] = "persistent_will"
        self.assertFalse(session.rules_player_can_act("p1"))
        session.phase_tracker["index"] = ADVANCED_PHASES.index("end_actions")
        self.assertTrue(session.rules_player_can_act("p1"))

    def test_disabled_bob_does_not_exile_itself_or_its_suspended_cards_at_eleven(self):
        session, p1, _ = self.started()
        session.card_rules["bob"] = {"type": "manifestation", "power": 11, "temperaments": ["hollow"],
                                     "suspensionThresholds": {"deck": 2, "graveyard": 5, "handImmunity": 8, "exile": 11}}
        bob = self.field_item("bob", "p1", "bob", effectsDisabled=True)
        session.battlefield.append(bob)
        self.put(p1, "deck", ["m-3"])
        session.suspend_zone_card("p1", "deck", "m-3", source_effect_id="bob")
        result = session.resolve_rules_state_actions()
        self.assertFalse(result["thresholdExiled"])
        self.assertIsNotNone(session.find_battlefield_item("bob"))
        self.assertEqual(len(session.rules_engine["suspendedCards"]), 1)
        bob.pop("effectsDisabled")
        result = session.resolve_rules_state_actions()
        self.assertEqual(len(result["thresholdExiled"]), 1)
        self.assertFalse(session.rules_engine["suspendedCards"])
        self.assertCountEqual(p1["zones"]["exile"], ["bob", "m-3"])

    @staticmethod
    def action(key, immediate=False):
        return {"id": key, "controllerId": "p1", "label": key, "kind": "triggered_effect", "source": {}, "targets": [],
                "ability": {"result": {"kind": "score_owner", "value": 1}}, "immediate": immediate}

    def test_auto_advance_drains_immediates_before_looking_for_responses(self):
        session, p1, p2 = self.started()
        self.put(p1, "hand", ["will-x"])
        self.put(p2, "hand", ["will-x"])
        for pid in session.players:
            session.add_rules_excess_essence(pid, [{"temperament": "transcendent", "amount": 5}])
        session.rules_engine["actionStack"] = [self.action("normal"), self.action("immediate", True)]
        session.rules_engine["priorityPlayerId"] = "p2"
        asyncio.run(server_main.auto_advance_rules_phases(session, "p1"))
        self.assertEqual([a["id"] for a in session.rules_engine["actionStack"]], ["normal"])
        self.assertEqual(p1["score"], 1)
        self.assertEqual(session.rules_engine["priorityPasses"], [])

    def test_an_immediate_on_top_cannot_receive_a_voluntary_response(self):
        session, _, p2 = self.started()
        self.put(p2, "hand", ["will-x"])
        session.add_rules_excess_essence("p2", [{"temperament": "phlegmatic", "amount": 2}])
        session.rules_engine["actionStack"] = [self.action("immediate", True)]
        session.rules_engine["priorityPlayerId"] = "p2"
        before = copy.deepcopy((session.players, session.tokens, session.rules_engine))
        error, result = session.declare_rules_action("p2", "Respond", kind="play_card", source={"cardId": "will-x", "zone": "hand"})
        self.assertIsNotNone(error)
        self.assertIsNone(result)
        self.assertEqual((session.players, session.tokens, session.rules_engine), before)
