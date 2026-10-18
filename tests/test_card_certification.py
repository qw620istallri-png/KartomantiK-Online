import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "tools" / "card_certification.py"
SPEC = importlib.util.spec_from_file_location("card_certification", MODULE_PATH)
certification = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(certification)


class CardCertificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = certification.build_report()

    def test_every_catalog_card_is_exercised_without_failure(self):
        summary = self.report["summary"]
        self.assertEqual(summary["catalogCards"], 450)
        self.assertEqual(len(self.report["cards"]), 450)
        failures = {
            card["name"]: card["failures"]
            for card in self.report["cards"]
            if not card["passed"]
        }
        self.assertEqual(failures, {})

    def test_report_keeps_behavior_evidence_distinct_from_structure(self):
        levels = self.report["summary"]["levels"]
        self.assertGreater(levels["scenario"], 0)
        self.assertGreaterEqual(levels["simple"], 47)
        self.assertGreater(levels["ability"], 0)
        self.assertGreater(levels["static"], 0)
        self.assertEqual(sum(levels.values()), 450)

    def test_every_declarative_ability_executes_its_behavior_carriers(self):
        summary = self.report["summary"]
        self.assertEqual(summary["smokedAbilities"], 493)
        self.assertGreaterEqual(summary["smokedCarriers"], 493)
        for card in self.report["cards"]:
            with self.subTest(card=card["name"]):
                self.assertEqual(card["smokedAbilities"], card["explicitAbilities"])

    def test_every_declared_automated_card_has_test_references(self):
        for card in self.report["cards"]:
            if card["declaredStatus"] == "automated":
                with self.subTest(card=card["name"]):
                    self.assertTrue(card["testRefs"])

    def test_committed_reports_are_current(self):
        self.assertEqual(
            certification.OUTPUT_JSON.read_text(encoding="utf-8"),
            certification.serialized_json(self.report),
        )
        self.assertEqual(
            certification.OUTPUT_MARKDOWN.read_text(encoding="utf-8"),
            certification.serialized_markdown(self.report),
        )


if __name__ == "__main__":
    unittest.main()
