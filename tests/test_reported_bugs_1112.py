"""Bugs reported by Istallri on 12/11 while playing against the bot."""

import asyncio

import main as server_main
import test_game_state as game_tests
from session import ADVANCED_PHASES


class PowerZeroAfterChoiceTests(game_tests.RealCardRulesCase):
    """Flem took -2 and stayed on the field at -1: a power change made while
    answering a choice (here: two Spiked Pits when Flem goes to the Interzone
    after the confrontation) never checked for destruction."""

    FLEM = "inner-deserts-001"
    PIT = "inner-deserts-117"
    ALL = (FLEM, PIT)

    def test_flem_dropping_below_one_in_a_choice_is_destroyed(self):
        session, p1, _p2 = self.make_session()
        session.rules_engine.update(readyPlayerIds=["p1", "p2"], firstManifestationComplete=True)
        session.phase_tracker["index"] = ADVANCED_PHASES.index("resolution_move")
        flem = self.field_item("flem", "p1", self.FLEM)
        pits = [self.field_item(f"pit-{n}", "p2", self.PIT, "field") for n in (1, 2)]
        session.battlefield = [flem, *pits]
        session.rules_engine["confrontationResult"] = {
            "turn": session.phase_tracker["turn"], "winnerId": "p1", "loserId": "p2",
            "pendingOwnItemIds": ["flem"], "participantItemIds": ["flem"],
        }
        session.rules_engine["pendingChoice"] = {
            "id": "dest", "kind": "confrontation_destination", "playerId": "p1",
            "itemId": "flem", "cardId": self.FLEM, "options": ["interzone", "deck_bottom"],
        }
        error, payload = session.resolve_rules_choice("p1", "dest", option="interzone")
        self.assertIsNone(error, error)
        self.assertIsNone(session.find_battlefield_item("flem"))
        self.assertIn(self.FLEM, p1["zones"]["graveyard"])
        self.assertEqual(payload["stateActions"]["destroyed"][0]["cardId"], self.FLEM)

    def test_a_choice_that_leaves_power_above_zero_destroys_nothing(self):
        session, _p1, _p2 = self.make_session()
        session.rules_engine.update(readyPlayerIds=["p1", "p2"], firstManifestationComplete=True)
        session.phase_tracker["index"] = ADVANCED_PHASES.index("resolution_move")
        session.card_rules["m-3"]["power"] = 4
        keeper = self.field_item("keeper", "p1", "m-3")
        session.battlefield = [keeper, self.field_item("pit-1", "p2", self.PIT, "field")]
        session.rules_engine["confrontationResult"] = {
            "turn": session.phase_tracker["turn"], "winnerId": "p1", "loserId": "p2",
            "pendingOwnItemIds": ["keeper"], "participantItemIds": ["keeper"],
        }
        session.rules_engine["pendingChoice"] = {
            "id": "dest", "kind": "confrontation_destination", "playerId": "p1",
            "itemId": "keeper", "cardId": "m-3", "options": ["interzone"],
        }
        error, payload = session.resolve_rules_choice("p1", "dest", option="interzone")
        self.assertIsNone(error, error)
        self.assertEqual(self.power_of(session, "keeper"), 3)
        self.assertNotIn("stateActions", payload)



class FirstStoneAlreadyInConfrontationTests(game_tests.RealCardRulesCase):
    """First Stone Chained by Help! in the End Phase stays in the Confrontation
    Zone, becomes the next First Manifestation, and must not trigger again at
    the Revelation: it entered the zone only once."""

    STONE = "4rnpxnnceu8x9o9_en"
    ALL = (STONE,)

    def reveal(self, stone_face_up_before):
        session, p1, p2 = self.make_session()
        session.rules_engine.update(readyPlayerIds=["p1", "p2"], firstManifestationComplete=False,
                                    firstManifestationItemIds={}, firstManifestationValidatedPlayerIds=[])
        self.put(p2, "hand", ["m-4"])
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_choose")
        stone = self.field_item("stone", "p1", self.STONE, faceUp=stone_face_up_before, confrontationOrder=1)
        foe = self.field_item("foe", "p2", "m-3", faceUp=False, confrontationOrder=2)
        session.battlefield = [stone, foe]
        if stone_face_up_before:
            session.register_rules_existing_first_manifestations()
        else:
            session.rules_engine["firstManifestationItemIds"]["p1"] = "stone"
        session.rules_engine["firstManifestationItemIds"]["p2"] = "foe"
        session.rules_engine["firstManifestationComplete"] = True
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_immediate")
        stone["faceUp"] = foe["faceUp"] = True
        result = {
            "status": "advanced", "previousPhaseId": "confrontation_reveal",
            "phaseId": "confrontation_immediate", "turn": session.phase_tracker["turn"],
            "stackDepth": 0,
        }
        asyncio.run(server_main.record_rules_pass_result(session, result, "p1"))
        stack = [entry["ability"]["id"] for entry in session.rules_engine["actionStack"]]
        choice = session.rules_engine.get("pendingChoice") or {}
        pending = (choice.get("_triggerAction") or {}).get("ability", {}).get("id")
        return [*stack, *([pending] if pending else []), *([choice.get("kind")] if choice and not pending else [])]

    def test_a_first_stone_already_on_the_field_does_not_trigger_again(self):
        self.assertEqual(self.reveal(stone_face_up_before=True), [])

    def test_a_first_stone_revealed_as_first_manifestation_still_triggers(self):
        self.assertNotEqual(self.reveal(stone_face_up_before=False), [])



class TrimRevertsMimerTests(game_tests.RealCardRulesCase):
    """Istallri, 12/11: under Trim the Excess, Mimer goes back to its own
    power 3; the copied Temperament stays."""

    MIMER = "pwsjhnw4vpvqgkv_en"
    PROB = "inner-deserts-078"
    TRIM = "t42gc95tma8uhzm_en"
    ALL = (MIMER, PROB, TRIM)

    def test_mimer_returns_to_three_and_keeps_the_copied_temperament(self):
        session, p1, p2 = self.make_session()
        session.rules_engine.update(readyPlayerIds=["p1", "p2"], firstManifestationComplete=True,
                                    priorityPlayerId="p2", actionStack=[], pendingChoice=None)
        session.phase_tracker.update(index=ADVANCED_PHASES.index("confrontation_reaction"), turn=3)
        session.card_rules[self.PROB]["temperaments"] = ["choleric"]
        prob = self.field_item("prob", "p1", self.PROB, confrontationOrder=1)
        mimer = self.field_item("mimer", "p2", self.MIMER, confrontationOrder=1)
        session.battlefield = [prob, mimer]
        session.rules_engine["firstManifestationItemIds"] = {"p1": "prob", "p2": "mimer"}
        session.add_rules_excess_essence("p2", [{"temperament": "hollow", "amount": 3}])
        error, _ = session.declare_rules_action(
            "p2", "Mimer", kind="activated_effect",
            source={"cardId": self.MIMER, "zone": "battlefield", "itemId": "mimer"},
            targets=[{"kind": "card", "itemId": "prob", "cardId": self.PROB}],
            ability_id="copy-first-manifestation",
        )
        self.assertIsNone(error, error)
        session.resolve_rules_top_action()
        self.assertEqual(session.rules_manifestation_characteristics(mimer), {"power": 5, "temperament": "choleric"})
        session.apply_rules_action_result({
            "id": "trim", "controllerId": "p1", "source": {"cardId": self.TRIM},
            "targets": [], "ability": self.ability(self.TRIM, "trim-field-to-base-power"),
        })
        self.assertEqual(session.rules_manifestation_characteristics(mimer), {"power": 3, "temperament": "choleric"})
        session.phase_tracker["turn"] = 4
        session.prune_rules_ongoing_effects()
        self.assertEqual(self.power_of(session, "mimer"), 3)


if __name__ == "__main__":
    import unittest
    unittest.main()
