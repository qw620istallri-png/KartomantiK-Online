import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "tools" / "automation_coverage.py"
SPEC = importlib.util.spec_from_file_location("automation_coverage", MODULE_PATH)
coverage_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(coverage_tool)


class AutomationCoverageTests(unittest.TestCase):
    def test_committed_registry_is_current(self):
        committed = (
            ROOT / "public" / "automation-coverage.json"
        ).read_text(encoding="utf-8")
        self.assertEqual(committed, coverage_tool.serialized_registry())

    def test_every_catalog_card_has_one_valid_status(self):
        registry = coverage_tool.build_registry()
        self.assertEqual(registry["summary"]["catalogCards"], 450)
        self.assertEqual(len(registry["cards"]), 450)
        self.assertEqual(
            sum(registry["summary"]["statuses"].values()), 450
        )
        self.assertTrue(all(
            entry["status"] in coverage_tool.ALLOWED_STATUSES
            for entry in registry["cards"].values()
        ))

    def test_explicit_abilities_and_automated_overrides_are_consistent(self):
        registry = coverage_tool.build_registry()
        abilities = json.loads(
            (ROOT / "public" / "card-abilities.json").read_text(encoding="utf-8")
        )
        explicit = {
            card_id for card_id, entry in registry["cards"].items()
            if entry["abilityIds"]
        }
        self.assertEqual(explicit, set(abilities))
        automated = [
            entry for entry in registry["cards"].values()
            if entry["status"] == "automated"
        ]
        self.assertTrue(automated)
        self.assertTrue(all(entry["testRefs"] for entry in automated))

    def test_audited_statuses_require_evidence_or_missing_mechanics(self):
        overrides = coverage_tool.load_overrides()["cards"]
        for card_id, override in overrides.items():
            with self.subTest(card_id=card_id):
                if override["status"] == "automated":
                    self.assertTrue(override.get("testRefs"))
                elif override["status"] in {"partial", "manual"}:
                    self.assertTrue(override.get("notes"))

    def test_generic_card_audit_is_complete(self):
        registry = coverage_tool.build_registry()
        statuses = registry["summary"]["statuses"]
        self.assertEqual(statuses["generic"], 0)
        self.assertEqual(
            sum(statuses.values()), registry["summary"]["catalogCards"]
        )

    def test_generic_audit_representative_classifications(self):
        cards = coverage_tool.build_registry()["cards"]

        self.assertEqual(cards["6jz7otalrdq0q8u_en"]["status"], "automated")
        self.assertTrue(cards["6jz7otalrdq0q8u_en"]["testRefs"])
        self.assertEqual(cards["jh2nsqxr9x2ii1l_en"]["status"], "automated")
        self.assertTrue(cards["jh2nsqxr9x2ii1l_en"]["testRefs"])
        self.assertEqual(cards["tdy2112mspb7u97_en"]["status"], "automated")
        self.assertTrue(cards["tdy2112mspb7u97_en"]["testRefs"])
        self.assertEqual(cards["inner-deserts-027"]["status"], "automated")
        self.assertEqual(cards["inner-deserts-031"]["status"], "automated")
        self.assertTrue(cards["inner-deserts-031"]["testRefs"])
        self.assertEqual(cards["inner-deserts-086"]["status"], "manual")


if __name__ == "__main__":
    unittest.main()
