"""Card sandbox: every scenario loads, and every scripted scenario plays to its checks.

The scripts go through main.handle_message, the path the browser uses, so a card
that passes here behaves the same in the sandbox page (python server/main.py with
KKO_SANDBOX=1, then open /?sandbox).
"""

import asyncio
import os
import sys
import unittest

SERVER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server"))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

import main  # noqa: E402
import sandbox  # noqa: E402
from session import Session  # noqa: E402

CATALOG = sandbox.Catalog(main.CARD_DATA, main.CARD_ABILITIES, main.CARD_RULES)


def new_session():
    return Session(
        card_points=main.CARD_POINTS, card_labels=main.CARD_LABELS,
        manifestation_ids=main.CARD_MANIFESTATION_IDS, card_rules=main.CARD_RULES, rules_beta=True,
    )


def play(scenario):
    session = new_session()
    sandbox.apply_scenario(session, CATALOG, scenario, "tester")
    reports = asyncio.run(sandbox.run_script(
        session, main.handle_message, main.auto_advance_rules_phases, main.AUTO_PASS_MESSAGE_TYPES,
    ))
    return session, reports


class SandboxScenarioTests(unittest.TestCase):
    def test_every_written_scenario_names_a_known_card_and_step(self):
        for scenario in sandbox.load_scenarios():
            with self.subTest(scenario=scenario["id"]):
                self.assertIn(scenario["cardId"], CATALOG.cards)
                session = new_session()
                sandbox.apply_scenario(session, CATALOG, scenario, "tester")
                self.assertEqual(session.current_phase_id(), scenario["phase"])
                self.assertFalse(session.rules_pregame_active())

    def test_scripted_scenarios_reach_all_their_checks(self):
        scripted = [scenario for scenario in sandbox.load_scenarios() if scenario.get("script")]
        self.assertTrue(scripted)
        for scenario in scripted:
            with self.subTest(scenario=scenario["id"]):
                _session, reports = play(scenario)
                failures = [f"{report['label']}: {report['error']}" for report in reports if not report["ok"]]
                self.assertEqual(failures, [])
                self.assertEqual(len(reports), len(scenario["script"]))

    def test_every_card_gets_loadable_generic_scenarios(self):
        for card_id in CATALOG.order:
            for scenario in sandbox.generic_scenarios(CATALOG, card_id):
                with self.subTest(scenario=scenario["id"]):
                    session = new_session()
                    sandbox.apply_scenario(session, CATALOG, scenario, "tester")
                    self.assertEqual(len(session.players), 2)
                    self.assertEqual(session.current_phase_id(), scenario["phase"])
                    ids = [card for player in session.players.values() for zone in player["zones"].values() for card in zone]
                    ids += [item["cardId"] for item in session.battlefield]
                    self.assertEqual(len(ids), len(set(ids)), "a card id appears twice")

    def test_generic_scripts_play_for_every_card(self):
        """First Manifestation reveal for every Manifestation, keyword scripts for the simple cards."""
        failures = []
        for card_id in CATALOG.order:
            for scenario in sandbox.generic_scenarios(CATALOG, card_id):
                if scenario.get("script"):
                    failures += [f"{scenario['id']}: {report['label']}: {report['error']}"
                                 for report in play(scenario)[1] if not report["ok"]]
        self.assertEqual(failures, [])

    def test_keyword_only_cards_match_their_compiled_rules(self):
        self.assertGreaterEqual(len(CATALOG.simple), 47)
        for card_id in CATALOG.simple:
            with self.subTest(card=CATALOG.cards[card_id]["name"]):
                self.assertEqual(sandbox.check_simple_card(CATALOG, card_id), [])

    def test_a_wrong_keyword_flag_is_reported(self):
        card_id = next(card_id for card_id, keywords in CATALOG.simple.items() if "supportFromHand" in keywords)
        rules = dict(main.CARD_RULES, **{card_id: dict(main.CARD_RULES[card_id], supportFromHand=False)})
        broken = sandbox.Catalog(main.CARD_DATA, main.CARD_ABILITIES, rules)
        self.assertTrue(any("supportFromHand" in failure for failure in sandbox.check_simple_card(broken, card_id)))

    def test_cards_with_more_than_keywords_are_not_simple(self):
        by_name = {card["name"]: card["id"] for card in main.CARD_DATA}
        for name in ("Censor", "Borombo, the Mad", "Zizek, the Immolated", "Alakazim, the Magician"):
            self.assertNotIn(by_name[name], CATALOG.simple)
        # a fixed tribute value is simple: it holds from every zone
        self.assertEqual(CATALOG.simple[by_name["Faroc-Ko, the Insipid"]], ["canPayTributeFromInterzone", "tributePower:2"])


if __name__ == "__main__":
    unittest.main()
