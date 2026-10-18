import json
import os
import sys
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS = os.path.join(ROOT, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import card_scenario_batches as batches  # noqa: E402


class CardScenarioBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = batches.build_report()

    def test_all_cards_pass_server_player_and_client_layers(self):
        summary = self.report["summary"]
        self.assertEqual(summary["cards"], 450)
        self.assertEqual(summary["batches"], 45)
        self.assertEqual(summary["passed"], 450)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["serverPassed"], 450)
        self.assertEqual(summary["playerPassed"], 450)
        self.assertEqual(summary["clientPassed"], 450)
        self.assertEqual(summary["abilities"], 493)
        self.assertEqual(summary["carriers"], 497)
        self.assertEqual(summary["playerActions"], 181)

    def test_batches_hold_ten_cards_and_keep_manual_cards_visible(self):
        cards = []
        for number, batch in enumerate(self.report["batches"], 1):
            self.assertEqual(batch["batch"], number)
            self.assertLessEqual(len(batch["cards"]), 10)
            self.assertTrue(batch["ok"])
            cards.extend(batch["cards"])
        self.assertEqual(len(cards), 450)
        manual = {entry["name"] for entry in cards if entry["manualReview"]}
        self.assertEqual(manual, {"Karma Bro", "Kaos Bro"})

    def test_phase_specific_activated_actions_reach_the_server(self):
        wanted = {
            "wretched-arena-locks-support-entries",
            "gummo-becomes-first-manifestation",
            "juggernut-charges-into-confrontation",
        }
        found = set()
        for card_id, abilities in batches.main.CARD_ABILITIES.items():
            for ability in abilities:
                if ability.get("id") not in wanted:
                    continue
                failures, messages = batches._run_player_action(card_id, ability)
                self.assertEqual(failures, [], ability.get("id"))
                self.assertGreater(messages, 0)
                found.add(ability["id"])
        self.assertEqual(found, wanted)

    def test_committed_reports_are_current(self):
        expected = json.dumps(self.report, ensure_ascii=False, indent=2) + "\n"
        with open(batches.SUMMARY_JSON, encoding="utf-8") as report_file:
            self.assertEqual(report_file.read(), expected)
        for batch in self.report["batches"]:
            path = batches.REPORT_DIR / f"lot-{batch['batch']:02d}.md"
            self.assertTrue(path.is_file())
            self.assertEqual(path.read_text(encoding="utf-8"), batches._batch_markdown(batch))


if __name__ == "__main__":
    unittest.main()
