"""Strict contracts for the five cards that reorder the top of Decks."""

from session import ADVANCED_PHASES
from test_game_state import RealCardRulesCase


REORDER_NAMES = (
    "Shababba, Divining Cube",
    "Glimpse the Omens",
    "Tut, Rhythmic Whirlwind",
    "Dissect",
    "Eviscerate Morality",
)

CARD_IDS = {
    "Shababba, Divining Cube": "i7h2c7ku2gt1yvg_en",
    "Glimpse the Omens": "9yylrq6xancbn0m_en",
    "Tut, Rhythmic Whirlwind": "inner-deserts-037",
    "Dissect": "inner-deserts-047",
    "Eviscerate Morality": "inner-deserts-068",
}

EXPECTED_ABILITIES = {
    "Shababba, Divining Cube": {
        "id": "shababba-reorder-at-end-of-turn",
        "trigger": {"event": "end_of_turn", "zone": "interzone"},
        "result": {"kind": "reorder_top_decks", "count": 4},
    },
    "Glimpse the Omens": {
        "id": "glimpse-the-omens",
        "action": "play_card",
        "targets": {"min": 0, "max": 0},
        "result": {
            "kind": "reorder_top_decks", "count": 4, "afterDraw": 1,
        },
    },
    "Tut, Rhythmic Whirlwind": {
        "id": "tut-look-at-top-three",
        "essenceCost": "{H}",
        "targets": {"min": 0, "max": 0},
        "result": {
            "kind": "reorder_top_decks", "count": 3,
            "topCount": 2, "bottomCount": 1,
        },
    },
    "Dissect": {
        "id": "reorder-top-three-of-each-deck",
        "action": "play_card",
        "targets": {"min": 0, "max": 0},
        "result": {
            "kind": "reorder_top_decks", "count": 3,
            "eachPlayer": True,
        },
    },
    "Eviscerate Morality": {
        "id": "eviscerate-morality",
        "action": "play_card",
        "targets": {"min": 0, "max": 0},
        "result": {
            "kind": "reorder_top_decks", "count": 4,
            "afterDiscard": 2,
        },
    },
}


class ReorderTopDecksFamily(RealCardRulesCase):
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

    def apply_result(self, session, card_id, item_id=None):
        ability = self.ABILITIES[card_id][0]
        return session.apply_rules_action_result({
            "id": f"run-{card_id}",
            "controllerId": "p1",
            "source": {"cardId": card_id, "itemId": item_id},
            "targets": [],
            "ability": {"result": ability["result"]},
        })

    def resolve_order(self, session, groups):
        choice = session.rules_engine["pendingChoice"]
        return session.resolve_rules_choice(
            "p1", choice["id"], option={"groups": groups},
        )

    def test_all_five_compile_the_exact_reorder_contract(self):
        rules = self.real_rules()
        self.assertEqual(set(rules), set(self.ALL))
        for name in REORDER_NAMES:
            with self.subTest(card=name):
                card_id = CARD_IDS[name]
                expected = EXPECTED_ABILITIES[name]
                self.assertEqual(self.ABILITIES[card_id], [expected])
                compiled = rules[card_id]
                if name == "Shababba, Divining Cube":
                    bucket = "triggeredAbilities"
                elif name == "Tut, Rhythmic Whirlwind":
                    bucket = "activatedAbilities"
                else:
                    bucket = "playedAbilities"
                self.assertEqual(compiled[bucket], [expected])

    def test_shababba_and_dissect_reorder_the_printed_decks_atomically(self):
        shababba = CARD_IDS["Shababba, Divining Cube"]
        session, p1, _p2 = self.started("end_triggers")
        self.put(p1, "deck", ["m-1", "m-2", "m-3", "m-4", "m-5"])
        session.battlefield = [
            self.field_item("sh", "p1", shababba, field_zone="field")
        ]
        self.assertEqual(session.build_rules_end_turn_field_triggers(), [])
        session.battlefield[0]["fieldZone"] = "interzone"
        queued = session.build_rules_end_turn_field_triggers()
        self.assertEqual(len(queued), 1)
        required = session.apply_rules_action_result(queued[0])
        self.assertEqual(required["choiceKind"], "deck_reorder")
        self.assertEqual(
            session.rules_engine["pendingChoice"]["_groups"][0]["cardIds"],
            ["m-1", "m-2", "m-3", "m-4"],
        )
        error, resolved = self.resolve_order(session, [{
            "playerId": "p1", "top": ["m-4", "m-2"],
            "bottom": ["m-1", "m-3"],
        }])
        self.assertIsNone(error, error)
        self.assertEqual(resolved["kind"], "deck_reorder")
        self.assertEqual(
            p1["zones"]["deck"], ["m-4", "m-2", "m-5", "m-1", "m-3"],
        )

        dissect = CARD_IDS["Dissect"]
        session, p1, p2 = self.started()
        self.put(p1, "deck", ["m-1", "m-2", "m-3", "m-4"])
        self.put(p2, "deck", ["m-5", "m-6", "m-7", "m-8"])
        required = self.apply_result(session, dissect)
        self.assertEqual(required["choiceKind"], "deck_reorder")
        self.assertEqual(
            {group["playerId"]: group["cardIds"] for group in session.rules_engine["pendingChoice"]["_groups"]},
            {
                "p1": ["m-1", "m-2", "m-3"],
                "p2": ["m-5", "m-6", "m-7"],
            },
        )
        before = (list(p1["zones"]["deck"]), list(p2["zones"]["deck"]))
        error, _payload = self.resolve_order(session, [{
            "playerId": "p1", "top": ["m-3"],
            "bottom": ["m-1", "m-2"],
        }])
        self.assertIn("every revealed deck group", error.lower())
        self.assertEqual(
            (p1["zones"]["deck"], p2["zones"]["deck"]), before,
        )
        error, _resolved = self.resolve_order(session, [
            {"playerId": "p1", "top": ["m-3"], "bottom": ["m-1", "m-2"]},
            {"playerId": "p2", "top": ["m-7", "m-5"], "bottom": ["m-6"]},
        ])
        self.assertIsNone(error, error)
        self.assertEqual(p1["zones"]["deck"], ["m-3", "m-4", "m-1", "m-2"])
        self.assertEqual(p2["zones"]["deck"], ["m-7", "m-5", "m-8", "m-6"])

    def test_tut_pays_one_hollow_and_enforces_two_top_one_bottom(self):
        tut = CARD_IDS["Tut, Rhythmic Whirlwind"]
        session, p1, _p2 = self.started()
        session.battlefield = [self.field_item("tut", "p1", tut)]
        self.put(p1, "deck", ["m-1", "m-2", "m-3", "m-4"])
        session.add_rules_excess_essence(
            "p1", [{"temperament": "hollow", "amount": 1}],
        )
        error, action = session.declare_rules_action(
            "p1", "Tut", kind="activated_effect",
            source={"cardId": tut, "zone": "battlefield", "itemId": "tut"},
            ability_id=EXPECTED_ABILITIES["Tut, Rhythmic Whirlwind"]["id"],
        )
        self.assertIsNone(error, error)
        self.assertEqual(len(action["cost"]["essenceSpent"]), 1)
        spent = action["cost"]["essenceSpent"][0]
        self.assertEqual(
            (spent["temperament"], spent["amount"]), ("hollow", 1),
        )
        session.resolve_rules_top_action()
        group = session.rules_engine["pendingChoice"]["_groups"][0]
        self.assertEqual((group["topCount"], group["bottomCount"]), (2, 1))
        before = list(p1["zones"]["deck"])
        error, _payload = self.resolve_order(session, [{
            "playerId": "p1", "top": ["m-2"],
            "bottom": ["m-1", "m-3"],
        }])
        self.assertIn("required number", error.lower())
        self.assertEqual(p1["zones"]["deck"], before)
        error, _resolved = self.resolve_order(session, [{
            "playerId": "p1", "top": ["m-3", "m-1"],
            "bottom": ["m-2"],
        }])
        self.assertIsNone(error, error)
        self.assertEqual(p1["zones"]["deck"], ["m-3", "m-1", "m-4", "m-2"])

    def test_glimpse_draws_and_eviscerate_discards_after_the_chosen_order(self):
        glimpse = CARD_IDS["Glimpse the Omens"]
        session, p1, _p2 = self.started()
        self.put(p1, "deck", ["m-1", "m-2", "m-3", "m-4", "m-5"])
        self.apply_result(session, glimpse)
        error, resolved = self.resolve_order(session, [{
            "playerId": "p1", "top": ["m-3", "m-1"],
            "bottom": ["m-2", "m-4"],
        }])
        self.assertIsNone(error, error)
        self.assertEqual(resolved["draw"], ["m-3"])
        self.assertEqual(p1["zones"]["hand"], ["m-3"])
        self.assertEqual(p1["zones"]["deck"], ["m-1", "m-5", "m-2", "m-4"])

        eviscerate = CARD_IDS["Eviscerate Morality"]
        session, p1, _p2 = self.started()
        self.put(p1, "deck", ["m-1", "m-2", "m-3", "m-4", "m-5", "m-6"])
        self.apply_result(session, eviscerate)
        error, resolved = self.resolve_order(session, [{
            "playerId": "p1", "top": ["m-4", "m-2"],
            "bottom": ["m-1", "m-3"],
        }])
        self.assertIsNone(error, error)
        self.assertEqual(resolved["discarded"], ["m-4", "m-2"])
        self.assertEqual(p1["zones"]["graveyard"], ["m-2", "m-4"])
        self.assertEqual(p1["zones"]["deck"], ["m-5", "m-6", "m-1", "m-3"])


if __name__ == "__main__":
    import unittest

    unittest.main()
