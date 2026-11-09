"""Strict contracts for Phimosino and Piercing Lover."""

from test_game_state import RealCardRulesCase


END_OF_GAME_NAMES = (
    "Phimosino",
    "Piercing Lover",
)

PHIMOSINO = "inner-deserts-035"
LOVER = "2z1svoyvo77ta03_en"
PILLAR = "7gaov0c4cjndl9w_en"

PHIMOSINO_ABILITY = {
    "id": "phimosino-scores-from-the-deck",
    "trigger": {"event": "end_of_game", "zone": "deck"},
    "result": {"kind": "final_deck_points", "value": 50},
}

LOVER_ABILITY = {
    "id": "piercing-lover-penalises-vessel-owner",
    "trigger": {"event": "end_of_game", "zone": "receptacle"},
    "result": {
        "kind": "final_vessel_penalty",
        "value": 5,
        "maxBasePower": 2,
    },
}


class EndOfGameFamily(RealCardRulesCase):
    ALL = (PHIMOSINO, LOVER)

    @staticmethod
    def manifestation(session, card_id, power):
        session.card_rules[card_id] = {
            "type": "manifestation",
            "power": power,
            "temperaments": ["phlegmatic"],
        }

    def lover_vessel(self, session, player, owner="p1", extras=None):
        extras = extras or {}
        self.put(player, "receptacle", {LOVER: owner, **extras})

    def test_both_compile_the_exact_printed_contract(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        self.assertEqual(self.ABILITIES[PHIMOSINO], [PHIMOSINO_ABILITY])
        self.assertEqual(self.ABILITIES[LOVER], [LOVER_ABILITY])
        self.assertEqual(
            rules[PHIMOSINO]["triggeredAbilities"], [PHIMOSINO_ABILITY],
        )
        self.assertEqual(
            rules[LOVER]["triggeredAbilities"], [LOVER_ABILITY],
        )

    def test_phimosino_gives_fifty_points_only_from_its_owners_deck(self):
        session, p1, p2 = self.make_session()
        self.put(p1, "deck", [PHIMOSINO, "m-1"])
        self.put(p2, "deck", ["m-2"])

        scores = session.calculate_final_scores()["scores"]
        self.assertEqual(scores["p1"]["endGamePoints"], 50)
        self.assertEqual(scores["p2"]["endGamePoints"], 0)
        self.assertEqual(scores["p1"]["deckBonus"], 10)
        self.assertEqual(scores["p1"]["total"], 60)

        for zone in ("hand", "graveyard", "exile", "receptacle"):
            with self.subTest(zone=zone):
                other, owner, _opponent = self.make_session()
                self.put(owner, zone, [PHIMOSINO])
                self.assertEqual(other.rules_end_game_points("p1"), 0)

    def test_phimosino_scores_for_whichever_owner_has_it_in_their_deck(self):
        session, p1, p2 = self.make_session()
        self.put(p1, "deck", ["m-1"])
        self.put(p2, "deck", [PHIMOSINO, "m-2"])

        self.assertEqual(session.rules_end_game_points("p1"), 0)
        self.assertEqual(session.rules_end_game_points("p2"), 50)

    def test_piercing_lover_requires_an_opponents_empathic_vessel(self):
        session, p1, p2 = self.make_session()
        self.manifestation(session, "m-low", 2)

        self.lover_vessel(session, p1, extras={"m-low": "p2"})
        self.assertEqual(session.rules_end_game_points("p1"), 0)

        self.lover_vessel(session, p2, extras={"m-low": "p2"})
        self.assertEqual(session.rules_end_game_points("p2"), -5)
        self.assertEqual(session.rules_end_game_points("p1"), 0)

        self.lover_vessel(
            session, p2, owner="p2", extras={"m-low": "p2"},
        )
        self.assertEqual(session.rules_end_game_points("p2"), 0)

    def test_piercing_lover_counts_only_manifestations_with_base_power_at_most_two(self):
        session, _p1, p2 = self.make_session()
        for card_id, power in (("m-zero", 0), ("m-two", 2), ("m-three", 3)):
            self.manifestation(session, card_id, power)
        session.card_rules["low-will"] = {
            "type": "persistent_will",
            "power": 1,
            "temperaments": ["phlegmatic"],
        }
        self.lover_vessel(session, p2, extras={
            "m-zero": "p1",
            "m-two": "p2",
            "m-three": "p1",
            "low-will": "p1",
        })

        self.assertEqual(session.card_rules[LOVER]["power"], 3)
        self.assertEqual(session.rules_end_game_points("p2"), -10)

    def test_each_players_end_game_adjustment_is_independent_and_additive(self):
        session, p1, p2 = self.make_session()
        self.manifestation(session, "m-one", 1)
        self.put(p1, "deck", [PHIMOSINO])
        self.lover_vessel(session, p2, extras={"m-one": "p2"})
        p1["score"] = 7
        p2["score"] = 20

        scores = session.calculate_final_scores()["scores"]
        self.assertEqual(scores["p1"]["endGamePoints"], 50)
        self.assertEqual(scores["p1"]["effectPoints"], 7)
        self.assertEqual(scores["p2"]["endGamePoints"], -5)
        self.assertEqual(scores["p2"]["effectPoints"], 20)

    def test_unreachable_pillar_suppresses_the_lover_only_while_active(self):
        session, _p1, p2 = self.make_session()
        self.manifestation(session, "m-low", 2)
        self.lover_vessel(session, p2, extras={"m-low": "p2"})
        session.card_rules[PILLAR] = {
            "type": "persistent_will",
            "passiveEffects": [
                self.ABILITIES[PILLAR][0]["passiveEffect"],
            ],
        }
        pillar = self.field_item(
            "pillar", "p2", PILLAR, field_zone="field",
        )
        session.battlefield = [pillar]

        self.assertTrue(session.rules_vessel_locked("p2"))
        self.assertEqual(session.rules_end_game_points("p2"), 0)
        pillar["effectsDisabled"] = True
        self.assertFalse(session.rules_vessel_locked("p2"))
        self.assertEqual(session.rules_end_game_points("p2"), -5)

