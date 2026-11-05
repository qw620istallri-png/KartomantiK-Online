"""Strict wins-confrontation contracts for six previously uncovered cards."""
import copy

from test_game_state import RealCardRulesCase


WINS_CONFRONTATION_NAMES = (
    "Gar Fild, the Malleable",
    "Jurat, the Strategist",
    "Dew Invoker",
    "Zaguor, Greedy Pedal",
    "Bullyboo",
    "Ycar, the Fleeting Flow",
)

CARD_IDS = {
    "Gar Fild, the Malleable": "rl4ppd0wsyov7lw_en",
    "Jurat, the Strategist": "t9yazjrbj1d37yu_en",
    "Dew Invoker": "nt0bixroxp0ftnk_en",
    "Zaguor, Greedy Pedal": "l9enna0sfy13yab_en",
    "Bullyboo": "gz2zjrxqc2rbcwq_en",
    "Ycar, the Fleeting Flow": "inner-deserts-013",
}

EXPECTED_RESULTS = {
    "Gar Fild, the Malleable": {
        "kind": "create_essence", "temperament": "transcendent",
        "value": 4, "retained": True,
    },
    "Jurat, the Strategist": {"kind": "return_turn_tributes_end_turn"},
    "Dew Invoker": {
        "kind": "hand_manifestation_choice", "destination": "interzone",
        "optional": True,
    },
    "Zaguor, Greedy Pedal": {
        "kind": "exile_source_take_control_to_interzone",
    },
    "Bullyboo": {"kind": "bullyboo_reveal"},
    "Ycar, the Fleeting Flow": {"kind": "ycar_exchange"},
}

EXPECTED_TARGETS = {
    "Zaguor, Greedy Pedal": {
        "min": 1, "max": 1, "cardType": "manifestation",
        "zones": ["battlefield", "receptacle"], "container": "opponent",
        "fieldZone": "interzone", "controller": "opponent",
    },
    "Ycar, the Fleeting Flow": {
        "min": 1, "max": 1, "cardType": "manifestation",
        "zones": ["battlefield"], "fieldZone": "interzone",
        "controller": "self", "owner": "self",
    },
}


class WinsConfrontationFamily(RealCardRulesCase):
    ALL = tuple(CARD_IDS.values())

    def win_ability(self, name):
        card_id = CARD_IDS[name]
        matches = [
            ability for ability in self.ABILITIES[card_id]
            if (ability.get("trigger") or {}).get("event")
            == "wins_confrontation"
        ]
        self.assertEqual(len(matches), 1, name)
        return card_id, matches[0]

    def fixture(self, name):
        card_id, ability = self.win_ability(name)
        session, p1, p2 = self.make_session()
        source = self.field_item(
            "source", "p1", card_id, controllerId="p1",
        )
        session.battlefield = [source]

        if name == "Dew Invoker":
            self.put(p1, "hand", ["m-1"])
        elif name == "Jurat, the Strategist":
            self.put(p1, "graveyard", ["m-1"])
            session.rules_engine["tributeLog"] = [{
                "turn": session.phase_tracker["turn"],
                "playerId": "p1", "ownerId": "p1", "cardId": "m-1",
            }]
        elif name == "Zaguor, Greedy Pedal":
            victim = self.field_item(
                "victim", "p2", "m-2", field_zone="interzone",
                controllerId="p2",
            )
            session.battlefield.append(victim)
        elif name == "Bullyboo":
            self.put(p1, "hand", ["will-x"])
        elif name == "Ycar, the Fleeting Flow":
            offered = self.field_item(
                "offered", "p1", "m-1", field_zone="interzone",
                controllerId="p1",
            )
            session.battlefield.append(offered)
            self.put(p1, "deck", ["m-3", "will-x"])

        session.rules_engine["confrontationResult"] = {
            "turn": session.phase_tracker["turn"],
            "winnerId": "p1", "loserId": "p2", "stalemate": False,
            "participantItemIds": ["source"],
        }
        return card_id, ability, session, p1, p2, source

    def queued_action(self, name):
        fixture = self.fixture(name)
        session = fixture[2]
        actions = session.queue_rules_confrontation_win_triggers(defer=True)
        matching = [
            action for action in actions
            if (action.get("source") or {}).get("itemId") == "source"
        ]
        self.assertEqual(len(matching), 1, name)
        return fixture, matching[0]

    def test_all_six_compile_the_exact_wins_confrontation_contract(self):
        self.assertEqual(len(WINS_CONFRONTATION_NAMES), 6)
        for name in WINS_CONFRONTATION_NAMES:
            with self.subTest(card=name):
                _card_id, ability = self.win_ability(name)
                self.assertEqual(
                    ability["trigger"], {"event": "wins_confrontation"},
                )
                self.assertEqual(ability["result"], EXPECTED_RESULTS[name])
                self.assertEqual(
                    bool(ability.get("optional")),
                    name in {
                        "Dew Invoker", "Zaguor, Greedy Pedal", "Bullyboo",
                        "Ycar, the Fleeting Flow",
                    },
                )
                self.assertEqual(
                    ability.get("targets"), EXPECTED_TARGETS.get(name),
                )

    def test_each_actual_winning_participant_queues_exactly_once(self):
        for name in WINS_CONFRONTATION_NAMES:
            with self.subTest(card=name):
                (card_id, ability, session, _p1, _p2, source), action = (
                    self.queued_action(name)
                )
                self.assertEqual(action["ability"]["id"], ability["id"])
                self.assertEqual(action["source"]["cardId"], card_id)
                self.assertEqual(action["source"]["itemId"], source["id"])
                self.assertEqual(action["controllerId"], "p1")
                self.assertEqual(session.rules_engine["actionStack"], [])

    def test_loser_nonparticipant_hidden_and_disabled_sources_do_not_trigger(self):
        mutations = {
            "loser": lambda session, source: session.rules_engine[
                "confrontationResult"
            ].update(winnerId="p2", loserId="p1"),
            "nonparticipant": lambda session, source: session.rules_engine[
                "confrontationResult"
            ].update(participantItemIds=[]),
            "hidden": lambda session, source: source.update(faceUp=False),
            "disabled": lambda session, source: source.update(
                effectsDisabled=True,
            ),
        }
        for name in WINS_CONFRONTATION_NAMES:
            for label, mutate in mutations.items():
                with self.subTest(card=name, condition=label):
                    _cid, _ability, session, _p1, _p2, source = self.fixture(
                        name
                    )
                    mutate(session, source)
                    before = copy.deepcopy(session.players)
                    queued = session.queue_rules_confrontation_win_triggers(
                        defer=True
                    )
                    self.assertFalse(any(
                        (action.get("source") or {}).get("itemId") == "source"
                        for action in queued
                    ))
                    self.assertEqual(session.players, before)
                    self.assertEqual(session.rules_engine["actionStack"], [])

    def test_each_card_specific_first_transition_is_authoritative(self):
        for name in WINS_CONFRONTATION_NAMES:
            with self.subTest(card=name):
                (_cid, _ability, session, p1, p2, _source), action = (
                    self.queued_action(name)
                )
                action["optionalAccepted"] = True
                if name == "Zaguor, Greedy Pedal":
                    action["targets"] = [{
                        "kind": "card", "itemId": "victim",
                        "cardId": "m-2", "ownerId": "p2",
                        "controllerId": "p2",
                    }]
                elif name == "Ycar, the Fleeting Flow":
                    action["targets"] = [{
                        "kind": "card", "itemId": "offered",
                        "cardId": "m-1", "ownerId": "p1",
                        "controllerId": "p1",
                    }]

                payload = session.apply_rules_action_result(action)

                if name == "Gar Fild, the Malleable":
                    self.assertEqual(
                        (payload["status"], payload["amount"]), ("created", 4),
                    )
                    retained = [
                        token for token in session.tokens
                        if token.get("temperament") == "transcendent"
                    ]
                    self.assertEqual(len(retained), 1)
                    self.assertEqual(retained[0]["counters"]["essence"], 4)
                    self.assertEqual(retained[0]["expiresTurn"], 0)
                elif name == "Jurat, the Strategist":
                    self.assertEqual(
                        (payload["status"], payload["cardIds"]),
                        ("scheduled", ["m-1"]),
                    )
                    self.assertEqual(
                        session.rules_engine["turnTributeReturns"][0][
                            "playerId"
                        ],
                        "p1",
                    )
                    self.assertEqual(
                        session.rules_engine["effectMemories"][0]["cardId"],
                        "m-1",
                    )
                elif name == "Dew Invoker":
                    self.assertEqual(payload["kind"], "choice_required")
                    choice = session.rules_engine["pendingChoice"]
                    self.assertEqual(
                        (choice["playerId"], choice["destination"]),
                        ("p1", "interzone"),
                    )
                elif name == "Zaguor, Greedy Pedal":
                    self.assertEqual(payload["status"], "taken")
                    self.assertIn(CARD_IDS[name], p1["zones"]["exile"])
                    victim = session.find_battlefield_item("victim")
                    self.assertEqual(
                        (victim["controllerId"], victim["fieldZone"]),
                        ("p1", "interzone"),
                    )
                elif name == "Bullyboo":
                    self.assertEqual(payload["kind"], "choice_required")
                    choice = session.rules_engine["pendingChoice"]
                    self.assertEqual(
                        (choice["playerId"], choice["destination"]),
                        ("p1", "bullyboo_reveal"),
                    )
                elif name == "Ycar, the Fleeting Flow":
                    self.assertEqual(payload["kind"], "choice_required")
                    self.assertIn("m-1", p2["zones"]["receptacle"])
                    choice = session.rules_engine["pendingChoice"]
                    self.assertEqual(choice["candidateCardIds"], ["m-3"])
                    self.assertEqual(
                        choice["destination"], "interzone_from_search",
                    )


if __name__ == "__main__":
    import unittest

    unittest.main()
