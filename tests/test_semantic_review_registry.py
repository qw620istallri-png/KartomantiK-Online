"""Registry validation tests: omissions and stale evidence must stay visible."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("card_semantic_audit", ROOT / "tools/card_semantic_audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class SemanticReviewRegistryTests(unittest.TestCase):
    def fixture(self):
        catalog = [{"id": "card-a", "name": "A", "effect": "Draw 2 cards.\nDiscard 1 card."},
                   {"id": "card-b", "name": "B", "effect": ""}]
        records = []
        for position, card in enumerate(catalog, 1):
            records.append({"cardId": card["id"], "catalogPosition": position, "name": card["name"],
                            "printedText": card["effect"], "printedTextSha256": audit.sha(card["effect"].encode()),
                            "status": "reviewed-match", "clauses": [
                                {"text": text, "expectedBehavior": "Literal specified outcome", "branchesAndExactOracles": ["No cards remain: zero moved"], "status": "reviewed-match"}
                                for text in audit.paragraphs(card["effect"])],
                            "noEffectTextReview": {"expectedBehavior": "No printed ability or synthetic trigger"}})
        return catalog, [("review.json", {"records": records})]

    def test_valid_registry_counts_paragraphs_without_certifying_execution(self):
        catalog, docs = self.fixture()
        result = audit.validate_reviews(catalog, docs, expected_count=2)
        self.assertTrue(result["valid"])
        self.assertEqual(result["summary"]["catalogParagraphs"], 2)
        self.assertEqual(result["summary"]["matchedParagraphEntries"], 2)
        self.assertNotIn("executionStatus", result["cards"][0])

    def test_duplicate_ids_and_wrong_positions_are_not_repaired(self):
        catalog, docs = self.fixture()
        docs[0][1]["records"][1].update(cardId="card-a", catalogPosition=1)
        codes = {item["code"] for item in audit.validate_reviews(catalog, docs, 2)["diagnostics"]}
        self.assertTrue({"duplicate-cardId", "duplicate-catalogPosition", "missing-card"} <= codes)

    def test_text_hash_missing_paragraph_expectation_and_branches_are_diagnosed(self):
        catalog, docs = self.fixture()
        record = docs[0][1]["records"][0]
        record["printedText"] = "Stale text"
        record["printedTextSha256"] = "stale"
        record["clauses"].pop()
        record["clauses"][0].update(expectedBehavior="", branchesAndExactOracles=[])
        codes = {item["code"] for item in audit.validate_reviews(catalog, docs, 2)["diagnostics"]}
        self.assertTrue({"printed-text-mismatch", "printed-text-sha-mismatch", "paragraph-coverage", "missing-expectation", "missing-branches"} <= codes)

    def test_second_review_schema_preserves_historical_defect(self):
        catalog, docs = self.fixture()
        record = docs[0][1]["records"][0]
        record["status"] = "reviewed-defect"
        record["clauseReview"] = [{"originalText": clause["text"], "independentCardContract": clause["expectedBehavior"],
                                   "negativeAlternativeAndNumericScenario": clause["branchesAndExactOracles"], "status": "reviewed-defect"}
                                  for clause in record.pop("clauses")]
        result = audit.validate_reviews(catalog, [("review.json", {"cards": docs[0][1]["records"]})], 2)
        self.assertTrue(result["valid"])
        self.assertEqual(result["cards"][0]["recordedStatus"], "reviewed-defect")

    def test_ast_mentions_exact_literals_and_constants_never_infer_name_or_clause(self):
        catalog, _ = self.fixture()
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "test_example.py"
            path.write_text('class Cases:\n    CARD = "card-b"\n    def test_draw_card_a(self):\n        name = "A"\n    def test_other(self):\n        value = "prefix card-a suffix"\n', encoding="utf-8")
            tests = audit.test_mentions(catalog, [path])
        self.assertEqual({item["cardId"] for item in tests[0]["cardMentions"]}, {"card-a", "card-b"})
        self.assertEqual({item["cardId"] for item in tests[1]["cardMentions"]}, {"card-b"})
        self.assertTrue(all(not test["provesWholeClause"] for test in tests))

    def test_stale_runtime_pass_does_not_certify_current_execution(self):
        mentions = [{"testId": "test_example.Cases.test_case"}]
        report = {"sourceDigest": "old", "tests": [{"testId": mentions[0]["testId"], "status": "pass"}]}
        result = audit.attach_runtime(mentions, report, "new")
        self.assertFalse(result["fresh"])
        self.assertEqual(mentions[0]["execution"]["recordedStatus"], "pass")
        self.assertFalse(mentions[0]["execution"]["currentExecutionCertified"])
        audit.attach_runtime(mentions, report, "old")
        self.assertTrue(mentions[0]["execution"]["currentExecutionCertified"])

    def test_remote_art_hash_checks_detect_changes_and_refuse_external_paths(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            (root / "input.json").write_bytes(b"now")
            report = {"inputHashes": {"input.json": audit.sha(b"before"), "../outside.json": "x"}}
            result = audit.validate_art_inputs(root, report)
        self.assertFalse(result["inputHashesValid"])
        self.assertEqual({item["code"] for item in result["diagnostics"]}, {"input-hash-mismatch", "input-outside-workspace"})


if __name__ == "__main__":
    unittest.main()
