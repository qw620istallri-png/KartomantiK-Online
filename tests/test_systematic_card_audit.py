"""Guard the audit against turning absent or failing proof into green coverage."""
import io
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import card_behavior_audit as audit
import run_card_audit as runner


class SystematicCardAuditTests(unittest.TestCase):
    def test_missing_or_stale_proof_cannot_be_reused(self):
        import json
        with patch.object(Path, "is_file", return_value=False):
            with self.assertRaisesRegex(ValueError, "Missing execution"):
                runner.read_evidence("old.json")
        with patch.object(Path, "is_file", return_value=True), patch.object(Path, "read_text", return_value=json.dumps({"sourceDigest": "old"})):
            with self.assertRaisesRegex(ValueError, "Stale execution"):
                runner.read_evidence("old.json")

    def test_text_oracle_detects_a_wrong_compiled_permission(self):
        card = {"effect": "Adamant.\nCannot be played as First Manifestation."}
        checks = audit.printed_assertions(card, {"adamant": False, "canBeFirstManifestation": True})
        self.assertEqual([c["status"] for c in checks], ["fail", "fail"])

    def test_contract_generation_does_not_claim_execution_or_full_text_review(self):
        report = audit.build(execute=False)
        self.assertEqual(len(report["cards"]), 450)
        self.assertEqual(report["summary"]["abilities"], 496)
        self.assertFalse(report["executed"])
        for card in report["cards"]:
            self.assertNotIn("carrierExecution", card)
            self.assertEqual(card["semanticReview"], "full-text-review-required")
            self.assertEqual([c["text"] for c in card["clauseReview"]], card["clauses"])

    def test_recorded_rulings_have_real_card_and_test_references(self):
        import json
        rulings = json.loads(audit.DECISIONS.read_text(encoding="utf-8"))["decisions"]
        self.assertEqual(len({r["id"] for r in rulings}), len(rulings))
        for ruling in rulings:
            for cid in ruling.get("cards", []):
                self.assertIn(cid, audit.batches.CATALOG.cards, ruling["id"])
            for name in ruling.get("cardNames", []):
                self.assertTrue(any(name.casefold() in c["name"].casefold() for c in audit.batches.CATALOG.cards.values()), name)
            for module in ruling["tests"]:
                self.assertTrue((audit.ROOT / "tests" / (module + ".py")).is_file(), module)

    def test_execution_recorder_keeps_skips_and_failing_subtests_out_of_passes(self):
        class Passing(unittest.TestCase):
            def runTest(self):
                self.assertTrue(True)
        class Skipped(unittest.TestCase):
            @unittest.skip("fixture intentionally absent")
            def runTest(self):
                pass
        class Broken(unittest.TestCase):
            def runTest(self):
                with self.subTest(branch="fails"):
                    self.assertEqual(1, 2)
        proof = unittest.TextTestRunner(stream=io.StringIO(), resultclass=runner.EvidenceResult).run(
            unittest.TestSuite([Passing(), Skipped(), Broken()]))
        self.assertEqual([e["status"] for e in proof.executions], ["pass", "skip", "fail"])
        self.assertFalse(proof.wasSuccessful())
