"""Retours joueurs du 25/11 : reproductions."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_game_state import RealCardRulesCase  # noqa: E402


class LoudmouthRepro(RealCardRulesCase):
    LOUD = "a9bsslut738hm0k_en"
    ALL = (LOUD,)

    def setup_reaction(self):
        session, p1, p2 = self.make_session()
        session.rules_engine["enabled"] = True
        session.phase_tracker["index"] = session.phase_sequence().index("confrontation_reaction")
        for cid in ("m-5", "m-6"):
            session.card_rules[cid].update({"supportFromHand": True, "power": 1})
        self.put(p1, "hand", [self.LOUD, "m-5", "m-6"])
        session.battlefield = [
            self.field_item("b1", "p1", "m-1"), self.field_item("b2", "p2", "m-2"),
        ]
        for it in session.battlefield:
            session.mark_rules_confrontation_entry(it)
        session.card_rules["m-1"]["power"] = 5
        session.rules_engine["priorityPlayerId"] = "p1"
        return session, p1, p2

    def compare(self, s):
        s.phase_tracker["index"] = s.phase_sequence().index("resolution_compare")
        return s.prepare_rules_confrontation_result()

    def play(self, session, pid, cid):
        err, act = session.declare_rules_action(pid, cid, kind="play_card", as_support=True,
            source={"cardId": cid, "zone": "hand"}, placement={"x": 400, "y": 500})
        self.assertIsNone(err)
        return act

    def resolve_top(self, session):
        a = session.rules_engine["priorityPlayerId"]
        session.pass_rules_priority(a)
        b = session.rules_engine["priorityPlayerId"]
        err, res = session.pass_rules_priority(b)
        self.assertIsNone(err)
        return res

    def test_two_later_supports_one_by_one(self):
        s, p1, p2 = self.setup_reaction()
        self.play(s, "p1", self.LOUD); self.resolve_top(s)
        s.rules_engine["priorityPlayerId"] = "p1"
        self.play(s, "p1", "m-5"); self.resolve_top(s)
        s.rules_engine["priorityPlayerId"] = "p1"
        self.play(s, "p1", "m-6"); self.resolve_top(s)
        self.assertFalse(self.compare(s)["stalemate"])

    def test_two_supports_stacked_on_top_of_loudmouth(self):
        s, p1, p2 = self.setup_reaction()
        self.play(s, "p1", self.LOUD)
        s.rules_engine["priorityPlayerId"] = "p1"
        self.play(s, "p1", "m-5")
        s.rules_engine["priorityPlayerId"] = "p1"
        self.play(s, "p1", "m-6")
        for _ in range(3):
            self.resolve_top(s)
        # Answered on the Stack, the two later Supports resolve first: the
        # Loudmouth is really the last to enter, so the stalemate is right.
        order = [i["cardId"] for i in sorted(s.battlefield, key=lambda i: i["confrontationOrder"])]
        self.assertEqual(order[-1], self.LOUD)
        self.assertTrue(self.compare(s)["stalemate"])


if __name__ == "__main__":
    unittest.main()


class KoxZizekSupportEntryTests(RealCardRulesCase):
    """Rapports 25/11 : Zizek enchaîné sans 6 Volontés, Consulter qui pose Kox."""

    KOX, ZIZEK, CONSULT = "40lqhpf5xr5v5sk_en", "ir09smkker8rgxd_en", "9c7s9dn3sa5dcko_en"
    ALL = (KOX, ZIZEK, CONSULT)

    def session(self):
        session, p1, p2 = self.make_session()
        session.rules_engine["enabled"] = True
        for index in range(6):
            session.card_rules[f"w-{index}"] = {"type": "ephemeral_will", "cost": 1}
        return session, p1, p2

    def test_zizek_cannot_be_chained_without_six_wills_in_limbo(self):
        session, p1, _p2 = self.session()
        self.put(p1, "hand", [self.ZIZEK, "m-1"])
        self.put(p1, "graveyard", [f"w-{i}" for i in range(5)])
        self.assertIn("cannot enter", session.rules_card_chain_restriction_error("p1", self.ZIZEK))
        self.assertEqual(list(session.rules_chain_candidates("p1", "hand")), ["m-1"])
        error, _ = session.chain_rules_manifestation("p1", "hand", self.ZIZEK)
        self.assertIn("cannot enter the Confrontation Zone", error)
        self.assertIn(self.ZIZEK, p1["zones"]["hand"])
        # With 6 Wills in the Limbo it can be Chained.
        self.put(p1, "graveyard", [f"w-{i}" for i in range(6)])
        self.assertIn(self.ZIZEK, session.rules_chain_candidates("p1", "hand"))

    def test_kox_cannot_be_chained(self):
        session, p1, _p2 = self.session()
        self.put(p1, "hand", [self.KOX])
        self.assertEqual(session.rules_chain_candidates("p1", "hand"), {})

    def test_consult_does_not_put_kox_in_support(self):
        session, p1, p2 = self.session()
        self.put(p1, "deck", ["w-0", self.KOX, "m-5"])
        session.apply_rules_action_result({
            "id": "c", "controllerId": "p1", "source": {"cardId": self.CONSULT, "ownerId": "p1"},
            "targets": [{"kind": "player", "playerId": "p1"}],
            "ability": {"result": {"kind": "consult_support"}},
        })
        self.assertFalse(any(item["cardId"] == self.KOX for item in session.battlefield))
        self.assertEqual(p1["zones"]["graveyard"], ["w-0"])
        self.assertEqual(p1["zones"]["deck"][0], self.KOX)
