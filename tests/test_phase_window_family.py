"""Strict Reaction-window contracts for the three remaining phase-window cards."""

import copy

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


PHASE_WINDOW_NAMES = (
    "Timid Brain",
    "Ranba, Silent Abductor",
    "Denegath, the Regulator",
)

CARD_IDS = {
    "Timid Brain": "5zgq2zcogt4g4d0_en",
    "Ranba, Silent Abductor": "fdnhc537c4xu2wo_en",
    "Denegath, the Regulator": "inner-deserts-039",
}

EXPECTED_ABILITIES = {
    "Timid Brain": {
        "id": "timid-brain-discard-will-for-support",
        "immediate": True,
        "sourceZones": ["hand"],
        "phaseIds": ["confrontation_reaction"],
        "additionalCost": "discard_hand_will",
        "targets": {"min": 0, "max": 0},
        "result": {"kind": "grant_source_support_until_end_turn"},
    },
    "Ranba, Silent Abductor": {
        "id": "ranba-abduct-weak-support",
        "sourceZones": ["hand"],
        "sourceCost": "discard_source",
        "phaseIds": ["confrontation_reaction"],
        "condition": "last_opponent_support_low_power",
        "targets": {"min": 0, "max": 0},
        "result": {"kind": "take_last_opponent_support_to_vessel"},
    },
    "Denegath, the Regulator": {
        "id": "denegath-returns-first-then-chains",
        "sourceFieldZone": "interzone",
        "exhaustSource": True,
        "essenceCost": "{H}{H}",
        "phaseIds": ["confrontation_reaction"],
        "targets": {"min": 0, "max": 0},
        "result": {"kind": "return_first_then_chain"},
    },
}


class PhaseWindowFamily(RealCardRulesCase):
    ALL = tuple(CARD_IDS.values())

    def started(self, phase="confrontation_reaction"):
        session, p1, p2 = self.make_session()
        session.rules_engine.update(
            readyPlayerIds=["p1", "p2"],
            firstManifestationComplete=True,
            priorityPlayerId="p1",
            actionStack=[],
            pendingChoice=None,
        )
        session.phase_tracker["index"] = ADVANCED_PHASES.index(phase)
        return session, p1, p2

    @staticmethod
    def snapshot(session):
        return copy.deepcopy((
            session.players,
            session.battlefield,
            session.tokens,
            session.rules_engine,
        ))

    def activate(self, session, name, source, cost_card_id=None):
        return session.declare_rules_action(
            "p1", f"Activate {name}", kind="activated_effect",
            source=source, targets=[],
            ability_id=EXPECTED_ABILITIES[name]["id"],
            cost_card_id=cost_card_id,
        )

    def resolve_top(self, session):
        self.assertIsNone(session.pass_rules_priority("p2")[0])
        error, resolution = session.pass_rules_priority("p1")
        self.assertIsNone(error, error)
        return resolution

    def support(self, session, card_id="m-1", power=2, owner="p2"):
        session.card_rules[card_id]["power"] = power
        item = self.field_item(
            "support", owner, card_id, isSupport=True, controllerId="p2"
        )
        session.battlefield = [item]
        session.rules_engine["supportEntries"].append({
            "turn": session.phase_tracker["turn"],
            "itemId": "support", "cardId": card_id,
            "controllerId": "p2",
        })
        return item

    def test_all_three_compile_the_exact_reaction_contract(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        for name in PHASE_WINDOW_NAMES:
            with self.subTest(card=name):
                card_id = CARD_IDS[name]
                expected = EXPECTED_ABILITIES[name]
                self.assertEqual(self.ABILITIES[card_id], [expected])
                self.assertEqual(rules[card_id]["activatedAbilities"], [expected])

    def test_neighbor_phase_rejections_are_atomic_for_all_three_cards(self):
        timid = CARD_IDS["Timid Brain"]
        ranba = CARD_IDS["Ranba, Silent Abductor"]
        denegath = CARD_IDS["Denegath, the Regulator"]
        cases = (
            ("Timid Brain", {"cardId": timid, "zone": "hand"}, [timid, "will-x"]),
            ("Ranba, Silent Abductor", {"cardId": ranba, "zone": "hand"}, [ranba]),
        )
        for name, source, hand in cases:
            with self.subTest(card=name):
                session, p1, _p2 = self.started("end_actions")
                self.put(p1, "hand", hand)
                if name.startswith("Ranba"):
                    self.support(session)
                before = self.snapshot(session)
                error, action = self.activate(
                    session, name, source,
                    cost_card_id="will-x" if name == "Timid Brain" else None,
                )
                self.assertIn("current phase", error)
                self.assertIsNone(action)
                self.assertEqual(self.snapshot(session), before)

        session, _p1, _p2 = self.started("end_actions")
        session.battlefield = [self.field_item(
            "denegath", "p1", denegath, field_zone="interzone"
        )]
        session.add_rules_excess_essence(
            "p1", [{"temperament": "hollow", "amount": 2}]
        )
        before = self.snapshot(session)
        error, action = self.activate(session, "Denegath, the Regulator", {
            "cardId": denegath, "zone": "battlefield", "itemId": "denegath",
        })
        self.assertIn("current phase", error)
        self.assertIsNone(action)
        self.assertEqual(self.snapshot(session), before)

    def test_timid_brain_pays_a_distinct_will_then_plays_as_support(self):
        timid = CARD_IDS["Timid Brain"]
        session, p1, _p2 = self.started()
        self.put(p1, "hand", [timid])
        before = self.snapshot(session)
        error, action = self.activate(
            session, "Timid Brain", {"cardId": timid, "zone": "hand"}
        )
        self.assertIn("Will in hand", error)
        self.assertIsNone(action)
        self.assertEqual(self.snapshot(session), before)

        self.put(p1, "hand", [timid, "will-x"])
        error, action = self.activate(
            session, "Timid Brain", {"cardId": timid, "zone": "hand"},
            cost_card_id="will-x",
        )
        self.assertIsNone(error, error)
        self.assertTrue(action["immediate"])
        self.assertEqual(action["cost"]["discardedCard"]["cardId"], "will-x")
        self.assertEqual(p1["zones"]["graveyard"], ["will-x"])

        resolved = session.resolve_rules_immediate_actions()
        self.assertEqual(resolved[0]["action"]["effectResult"]["status"], "played")
        self.assertEqual(session.rules_engine["playPermissions"], [])
        play = session.rules_engine["actionStack"][-1]
        self.assertEqual(
            (play["kind"], play["asSupport"], play["source"]["cardId"]),
            ("play_card", True, timid),
        )
        self.resolve_top(session)
        entered = next(item for item in session.battlefield if item["cardId"] == timid)
        self.assertTrue(entered["isSupport"])
        self.assertEqual(entered["fieldZone"], "confrontation")

    def test_ranba_rejects_a_strong_last_support_then_takes_a_weak_one(self):
        ranba = CARD_IDS["Ranba, Silent Abductor"]
        session, p1, _p2 = self.started()
        self.put(p1, "hand", [ranba])
        support = self.support(session, power=3)
        before = self.snapshot(session)
        error, action = self.activate(
            session, "Ranba, Silent Abductor",
            {"cardId": ranba, "zone": "hand"},
        )
        self.assertIn("power of 2 or less", error)
        self.assertIsNone(action)
        self.assertEqual(self.snapshot(session), before)

        session.card_rules[support["cardId"]]["power"] = 2
        error, action = self.activate(
            session, "Ranba, Silent Abductor",
            {"cardId": ranba, "zone": "hand"},
        )
        self.assertIsNone(error, error)
        self.assertEqual(action["cost"]["discardedSource"]["cardId"], ranba)
        self.assertIn(ranba, p1["zones"]["graveyard"])
        resolution = self.resolve_top(session)
        result = resolution["action"]["effectResult"]
        self.assertEqual(result["status"], "taken")
        self.assertIsNone(session.find_battlefield_item("support"))
        self.assertIn("m-1", p1["zones"]["receptacle"])

    def test_ranba_discards_but_does_not_abduct_a_card_you_own(self):
        ranba = CARD_IDS["Ranba, Silent Abductor"]
        session, p1, _p2 = self.started()
        self.put(p1, "hand", [ranba])
        self.support(session, power=2, owner="p1")
        error, action = self.activate(
            session, "Ranba, Silent Abductor",
            {"cardId": ranba, "zone": "hand"},
        )
        self.assertIsNone(error, error)
        self.assertEqual(action["cost"]["discardedSource"]["cardId"], ranba)
        resolution = self.resolve_top(session)
        self.assertEqual(
            resolution["action"]["effectResult"]["status"], "own_card"
        )
        self.assertIsNotNone(session.find_battlefield_item("support"))
        self.assertEqual(p1["zones"]["receptacle"], [])

    def test_denegath_gates_source_and_payment_then_returns_and_chains(self):
        denegath = CARD_IDS["Denegath, the Regulator"]
        session, p1, _p2 = self.started()
        source = self.field_item("denegath", "p1", denegath)
        first = self.field_item("first", "p1", "m-1")
        session.battlefield = [source, first]
        session.rules_engine["firstManifestationItemIds"] = {"p1": "first"}
        self.put(p1, "hand", ["m-2"])
        source_ref = {
            "cardId": denegath, "zone": "battlefield", "itemId": "denegath",
        }

        before = self.snapshot(session)
        error, action = self.activate(
            session, "Denegath, the Regulator", source_ref
        )
        self.assertIn("field zone", error)
        self.assertIsNone(action)
        self.assertEqual(self.snapshot(session), before)

        source["fieldZone"] = "interzone"
        before = self.snapshot(session)
        error, action = self.activate(
            session, "Denegath, the Regulator", source_ref
        )
        self.assertIsNotNone(error)
        self.assertIsNone(action)
        self.assertEqual(self.snapshot(session), before)

        session.add_rules_excess_essence(
            "p1", [{"temperament": "hollow", "amount": 2}]
        )
        error, action = self.activate(
            session, "Denegath, the Regulator", source_ref
        )
        self.assertIsNone(error, error)
        self.assertTrue(action["cost"]["sourceExhausted"])
        self.assertEqual(sum(
            entry["amount"] for entry in action["cost"]["essenceSpent"]
        ), 2)
        self.assertEqual(source["rotation"], 90)

        resolution = self.resolve_top(session)
        result = resolution["action"]["effectResult"]
        self.assertEqual(result["choiceKind"], "chain_manifestation")
        self.assertEqual(result["returned"]["status"], "moved")
        self.assertEqual(sorted(p1["zones"]["hand"]), ["m-1", "m-2"])
        self.assertIsNotNone(
            session.rules_card_play_restriction_error("p1", "m-1")
        )
        choice = session.rules_engine["pendingChoice"]
        self.assertEqual(choice["_cardIds"], ["m-2"])
        error, chained = session.resolve_rules_choice(
            "p1", choice["id"], ["m-2"], placement={"x": 400, "y": 300}
        )
        self.assertIsNone(error, error)
        item = session.find_battlefield_item(chained["itemId"])
        self.assertEqual((item["cardId"], item["isChained"]), ("m-2", True))
        self.assertEqual(p1["zones"]["hand"], ["m-1"])


if __name__ == "__main__":
    import unittest

    unittest.main()
