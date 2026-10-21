import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
from session import ADVANCED_PHASES, Session


class WhiteEssencePaymentTests(unittest.TestCase):
    def make_session(self, white=1):
        cards = {
            "will": {"type": "persistent_will", "powerCost": "{R}{G}", "cost": 2, "temperaments": ["choleric", "phlegmatic"]},
            "red": {"type": "manifestation", "power": 1, "temperaments": ["choleric"]},
            "green": {"type": "manifestation", "power": 1, "temperaments": ["phlegmatic"]},
        }
        session = Session(rules_beta=True, card_rules=cards)
        p1 = session.get_or_create_player("p1", "P1", seat=0)
        session.get_or_create_player("p2", "P2", seat=1)
        session.rules_engine.update(deckConfirmedPlayerIds=["p1", "p2"], readyPlayerIds=["p1", "p2"], firstManifestationComplete=True, priorityPlayerId="p1")
        session.phase_tracker["index"] = ADVANCED_PHASES.index("end_actions")
        p1["zones"]["hand"] = ["will", "red", "green"]
        p1["zoneOwners"]["hand"] = {card: "p1" for card in p1["zones"]["hand"]}
        session.add_rules_excess_essence("p1", [{"temperament": "transcendent", "amount": white}])
        return session, p1

    def test_player_can_choose_either_colour_and_keep_the_other_manifestation(self):
        for colour, tribute, kept in [("phlegmatic", "red", "green"), ("choleric", "green", "red")]:
            with self.subTest(colour=colour):
                session, p1 = self.make_session()
                error, action = session.declare_rules_action(
                    "p1", "Multicolour Will", kind="play_card", source={"cardId": "will", "zone": "hand"},
                    payment_card_ids=[tribute], transcendent_payment={colour: 1},
                )
                self.assertIsNone(error)
                self.assertEqual(action["cost"]["essenceSpent"][0]["pays"], colour)
                self.assertEqual(action["cost"]["tributeCardIds"], [tribute])
                self.assertIn(kept, p1["zones"]["hand"])
                self.assertIn(tribute, p1["zones"]["graveyard"])

    def test_affordability_checks_all_white_allocations(self):
        session, p1 = self.make_session()
        p1["zones"]["hand"] = ["will", "red"]
        self.assertTrue(session.rules_requirements_affordable("p1", {"choleric": 1, "phlegmatic": 1}, "will"))
        self.assertTrue(session.rules_player_can_act("p1"))
        self.assertIsNone(session.rules_auto_pass_player())

    def test_forged_or_stale_allocation_is_rejected_without_spending(self):
        invalid = [{}, {"phlegmatic": 2}, {"vitreous": 1}, {"phlegmatic": -1}, {"phlegmatic": True}, {"phlegmatic": 1.5}, [], "green"]
        for allocation in invalid:
            with self.subTest(allocation=allocation):
                session, p1 = self.make_session()
                tokens = [dict(token, counters=dict(token["counters"])) for token in session.tokens]
                error, action = session.declare_rules_action(
                    "p1", "Multicolour Will", kind="play_card", source={"cardId": "will", "zone": "hand"},
                    payment_card_ids=["red"], transcendent_payment=allocation,
                )
                self.assertIsNotNone(error)
                self.assertIsNone(action)
                self.assertEqual(session.tokens, tokens)
                self.assertEqual(p1["zones"]["hand"], ["will", "red", "green"])

    def test_specific_essences_are_spent_before_white_allocation(self):
        session, _p1 = self.make_session()
        session.add_rules_excess_essence("p1", [{"temperament": "choleric", "amount": 1}])
        error, payment = session.rules_action_payment(
            "p1", "play_card", {"cardId": "will", "cardType": "persistent_will"}, [],
            transcendent_payment={"phlegmatic": 1},
        )
        self.assertIsNone(error)
        self.assertEqual([(entry["temperament"], entry["pays"]) for entry in payment["essenceSpent"]], [("choleric", "choleric"), ("transcendent", "phlegmatic")])
        error, _payment = session.rules_action_payment(
            "p1", "play_card", {"cardId": "will", "cardType": "persistent_will"}, [],
            transcendent_payment={"choleric": 1},
        )
        self.assertIsNotNone(error)

    def test_white_can_split_between_multiple_requirements(self):
        session, _p1 = self.make_session(white=2)
        requirements = {"choleric": 2, "phlegmatic": 2}
        left, spent = session.rules_essence_payment_plan("p1", requirements, transcendent_payment={"choleric": 1, "phlegmatic": 1})
        self.assertEqual(left, {"choleric": 1, "phlegmatic": 1})
        self.assertEqual(sum(entry["amount"] for entry in spent), 2)

    def test_legacy_and_unambiguous_payment_stays_automatic(self):
        session, _p1 = self.make_session(white=3)
        left, spent = session.rules_essence_payment_plan("p1", {"choleric": 1, "phlegmatic": 1})
        self.assertEqual(left, {"choleric": 0, "phlegmatic": 0})
        self.assertEqual(sum(entry["amount"] for entry in spent), 2)


if __name__ == "__main__":
    unittest.main()
