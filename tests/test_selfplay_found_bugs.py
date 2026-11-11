"""Regression tests for engine bugs found by bot-versus-bot self-play.

- a Tribute naming a Hand card already declared on the Stack crashed the server;
- a Point cost blocked by Balance of the Spirit crashed after validation;
- Dew Invoker froze the game when no Hand Manifestation fitted the Interzone;
- a hand whose Manifestations cannot enter the Confrontation counted as playable,
  so no Recovery Mulligan was required and the game waited forever.
"""
import os
import sys
import unittest

SERVER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server"))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

import main as server_main  # noqa: E402
from session import ADVANCED_PHASES, Session  # noqa: E402

CARD = server_main.CARD_ID_BY_NUMBER
STRENGTHEN, TRIBUTE, TARGET = CARD[266], CARD[190], CARD[2]
DEW_INVOKER = CARD[74]
KOX = CARD[248]
BALANCE_OF_THE_SPIRIT = "inner-deserts-137"
POINT_COST_CARD = "0kcy08a6jd7ez7k_en"  # ability lose-ten-to-gain-support


def make_session(phase_id="confrontation_reaction"):
    session = Session(
        card_points=server_main.CARD_POINTS, card_labels=server_main.CARD_LABELS,
        manifestation_ids=server_main.CARD_MANIFESTATION_IDS, card_rules=server_main.CARD_RULES,
        rules_beta=True,
    )
    for seat, player_id in enumerate(("p1", "p2")):
        player = session.get_or_create_player(player_id, player_id.upper(), seat=seat)
        player["zones"]["hand"] = []
    rules = session.rules_engine
    rules.update(deckConfirmedPlayerIds=["p1", "p2"], readyPlayerIds=["p1", "p2"],
                 priorityPlayerId="p1", priorityPasses=[], pendingChoice=None,
                 autoSkipPhases=False, firstManifestationComplete=True)
    session.phase_tracker["index"] = ADVANCED_PHASES.index(phase_id)
    return session


def give_hand(session, player_id, cards):
    player = session.players[player_id]
    player["zones"]["hand"] = list(cards)
    player["zoneOwners"]["hand"] = {card_id: player_id for card_id in cards}


def field_item(item_id, card_id, owner, zone):
    return {"id": item_id, "ownerId": owner, "controllerId": owner, "cardId": card_id,
            "x": 0, "y": 0, "faceUp": True, "rotation": 0, "counters": {},
            "stackedOn": None, "fieldZone": zone}


class StackReservedTributeTests(unittest.TestCase):
    def test_a_card_waiting_on_the_stack_cannot_pay_a_tribute(self):
        session = make_session()
        give_hand(session, "p1", [STRENGTHEN, TRIBUTE])
        session.battlefield = [field_item("target", TARGET, "p1", "confrontation")]
        session.rules_engine["actionStack"] = [{
            "id": "waiting", "controllerId": "p1", "kind": "activated_effect", "label": "waiting",
            "source": {"cardId": TRIBUTE, "zone": "hand", "itemId": None},
            "targets": [], "ability": {"id": "x", "result": {"kind": "none"}},
        }]
        ability_id = server_main.CARD_ABILITIES[STRENGTHEN][0]["id"]
        error, action = session.declare_rules_action(
            "p1", "Strengthen", kind="play_card", source={"cardId": STRENGTHEN, "zone": "hand"},
            targets=[{"kind": "card", "itemId": "target", "cardId": TARGET}],
            payment_card_ids=[TRIBUTE], ability_id=ability_id,
        )
        self.assertIsNone(action)
        self.assertIn("declared in the Stack", error)
        self.assertEqual(session.players["p1"]["zones"]["hand"], [STRENGTHEN, TRIBUTE])
        self.assertEqual(len(session.rules_engine["actionStack"]), 1)


class BalancedPointCostTests(unittest.TestCase):
    def test_the_poorest_player_cannot_pay_a_point_cost_under_balance(self):
        session = make_session()
        session.battlefield = [field_item("balance", BALANCE_OF_THE_SPIRIT, "p2", "field")]
        session.players["p2"]["score"] = 30
        self.assertTrue(session.rules_point_cost_unpayable("p1"))
        self.assertFalse(session.rules_point_cost_unpayable("p2"))
        ability = next(a for a in server_main.CARD_ABILITIES[POINT_COST_CARD] if a["id"] == "lose-ten-to-gain-support")
        give_hand(session, "p1", [POINT_COST_CARD])
        error, action = session.declare_rules_action(
            "p1", "pay points", kind="activated_effect",
            source={"cardId": POINT_COST_CARD, "zone": "hand"}, ability_id=ability["id"],
        )
        self.assertIsNone(action)
        self.assertTrue(error)

    def test_without_balance_the_cost_stays_payable(self):
        session = make_session()
        self.assertFalse(session.rules_point_cost_unpayable("p1"))


class DewInvokerFullInterzoneTests(unittest.TestCase):
    def resolve(self, session):
        manifestation = next(c for c in session.players["p1"]["zones"]["hand"])
        action = {"id": "dew", "controllerId": "p1", "optionalAccepted": True,
                  "source": {"cardId": DEW_INVOKER, "zone": "battlefield"}, "targets": []}
        result = {"kind": "hand_manifestation_choice", "destination": "interzone", "optional": True}
        return manifestation, session._rules_result_hand_manifestation_choice(
            action, result, "p1", session.players["p1"])

    def test_no_choice_is_asked_when_the_interzone_is_full(self):
        session = make_session("resolution_effects")
        give_hand(session, "p1", [TRIBUTE])
        session.battlefield = [field_item(f"i{n}", CARD[n + 10], "p1", "interzone") for n in range(3)]
        _card, payload = self.resolve(session)
        self.assertEqual(payload["status"], "interzone_full")
        self.assertIsNone(session.rules_engine["pendingChoice"])

    def test_the_choice_is_still_asked_when_there_is_room(self):
        session = make_session("resolution_effects")
        give_hand(session, "p1", [TRIBUTE])
        _card, payload = self.resolve(session)
        self.assertEqual(payload["kind"], "choice_required")
        self.assertEqual(session.rules_engine["pendingChoice"]["kind"], "discard_from_hand")


class FirstManifestationPlayabilityTests(unittest.TestCase):
    def test_a_hand_that_cannot_enter_the_confrontation_is_not_playable(self):
        session = make_session("recovery_draw")
        give_hand(session, "p1", [KOX, STRENGTHEN])
        self.assertFalse(session.rules_card_can_be_first_manifestation(KOX, "p1"))
        self.assertFalse(session.rules_opening_hand_is_playable("p1"))
        give_hand(session, "p1", [KOX, TRIBUTE])
        self.assertTrue(session.rules_opening_hand_is_playable("p1"))


if __name__ == "__main__":
    unittest.main()
