"""A played controller choice must not become the target of a targetless ETB."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import card_scenario_batches as batches


class ChosenEntryControlTests(unittest.TestCase):
    def prepare(self):
        cid = "inner-deserts-127"
        ability = next(a for a in batches.main.CARD_ABILITIES[cid] if a.get("action") == "play_card")
        session, actor, source, _, _ = batches.prepare_action(cid, ability)
        return session, actor, source, ability

    def test_bibi_accepts_either_controller_without_reusing_it_as_etb_target(self):
        for controller in ("p1", "p2"):
            with self.subTest(controller=controller):
                session, actor, source, ability = self.prepare()
                error, action = session.declare_rules_action(actor, "Bibi chosen controller", kind="play_card",
                    source=source, ability_id=ability["id"], as_support=True,
                    targets=[{"kind": "player", "playerId": controller}])
                self.assertIsNone(error)
                session.resolve_rules_top_action()
                item = next(i for i in session.battlefield if i["cardId"] == "inner-deserts-127")
                self.assertEqual(session.rules_item_controller_id(item), controller)
                self.assertEqual(item["ownerId"], "p1")
                rolls = [a for a in session.rules_engine["actionStack"] if a["ability"]["id"] == "roll-on-enter-field"]
                self.assertEqual(len(rolls), 1)
                self.assertEqual(rolls[0]["targets"], [])
                self.assertEqual(rolls[0]["controllerId"], controller)
                self.assertEqual(rolls[0]["source"]["ownerId"], "p1")

    def test_bibi_given_to_opponent_draws_for_its_entry_controller(self):
        session, actor, source, ability = self.prepare()
        before = {pid: len(p["zones"]["hand"]) for pid, p in session.players.items()}
        error, _ = session.declare_rules_action(actor, "Give Bibi", kind="play_card", source=source,
            ability_id=ability["id"], as_support=True, targets=[{"kind": "player", "playerId": "p2"}])
        self.assertIsNone(error)
        session.resolve_rules_top_action()
        with patch("game.effects.dice.random.randint", return_value=2):
            session.resolve_rules_top_action()
        self.assertEqual(len(session.players["p1"]["zones"]["hand"]), before["p1"] - 1)
        self.assertEqual(len(session.players["p2"]["zones"]["hand"]), before["p2"] + 1)

    def test_targeted_entry_still_rejects_an_unrelated_player_target(self):
        # Flower Tender needs a Manifestation, not the played controller choice.
        cid = next(cid for cid, card in batches.CATALOG.cards.items() if card["name"] == "Flower Tender")
        session, _, _ = batches.smoke.make_session(cid, {})
        error = session.rules_trigger_target_error(cid, "enters_field_zone", face_up=True, event_zone="confrontation",
            trigger_targets=[{"kind": "player", "playerId": "p2"}], controller_id="p1")
        self.assertIsNotNone(error)
