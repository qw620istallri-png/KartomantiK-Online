import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from card_coverage_gaps import build_inventory
from card_coverage_status import (
    collect_selected_cards,
    evaluate_unit_evidence,
)


class CoverageGapInventoryTests(unittest.TestCase):
    def test_duplicate_unit_test_ids_are_rejected_explicitly(self):
        unit = {
            "summary": {
                "executed": 2, "passed": 2, "failed": 0, "skipped": 0,
            },
            "tests": [
                {"testId": "same.test", "status": "pass"},
                {"testId": "same.test", "status": "pass"},
            ],
        }
        executions, duplicates, passed = evaluate_unit_evidence(unit)
        self.assertEqual(executions, {"same.test": "pass"})
        self.assertEqual(duplicates, ["same.test"])
        self.assertFalse(passed)

    def test_blank_printed_text_requires_an_explicit_no_effect_contract(self):
        catalog = {
            "blank": {"name": "Blank", "effect": ""},
            "text": {"name": "Text", "effect": "Support."},
        }
        executions = {"proof": "pass"}
        documents = [("proof.json", {"cards": [
            {
                "cardId": "blank",
                "noEffectTextContract": True,
                "testIds": ["proof"],
                "allBranchesCertified": True,
            },
            {
                "cardId": "text",
                "noEffectTextContract": True,
                "testIds": ["proof"],
            },
        ]})]
        cards, excluded = collect_selected_cards(
            documents, executions, catalog
        )
        self.assertEqual([card["cardId"] for card in cards], ["blank"])
        self.assertTrue(cards[0]["allBranchesCertified"])
        self.assertEqual(
            cards[0]["proofs"][0]["proofKind"],
            "no-effect-contract",
        )
        self.assertEqual(excluded[0]["cardId"], "text")

    def test_inventory_is_exact_and_greedy_batches_do_not_duplicate_cards(self):
        catalog = [
            {"id": "a", "name": "A", "collectionNumber": 1, "type": "manifestation"},
            {"id": "b", "name": "B", "collectionNumber": 2, "type": "manifestation"},
            {"id": "c", "name": "C", "collectionNumber": 3, "type": "ephemeral_will"},
            {"id": "d", "name": "D", "collectionNumber": 4, "type": "persistent_will"},
        ]
        coverage = {
            "sourceDigest": "digest",
            "unitEvidence": "units.json",
            "cards": [{"cardId": "a"}],
        }
        automation = {"cards": {
            "a": {"mechanics": ["support"]},
            "b": {"mechanics": ["support", "move"], "abilityIds": ["b1"]},
            "c": {"mechanics": ["move"], "abilityIds": ["c1"]},
            "d": {"mechanics": [], "abilityIds": []},
        }}
        reviews = {
            "b": {"status": "reviewed-match", "clauses": [{
                "branchesAndExactOracles": ["positive", "negative"],
            }]},
            "c": {"status": "reviewed-match", "clauses": [{}, {}]},
            "d": {"status": "reviewed-match", "clauses": []},
        }

        report = build_inventory(coverage, automation, catalog, reviews)

        self.assertEqual(report["summary"]["uncoveredCards"], 3)
        self.assertEqual(report["summary"]["uncoveredClauses"], 3)
        self.assertEqual(report["summary"]["uncoveredBranchOracles"], 2)
        self.assertEqual(report["recommendedBatches"][0]["mechanic"], "move")
        selected = [
            card_id
            for batch in report["recommendedBatches"]
            for card_id in batch["cardIds"]
        ]
        self.assertEqual(sorted(selected), ["b", "c", "d"])
        self.assertEqual(len(selected), len(set(selected)))

    def test_real_inventory_matches_the_strict_register_complement(self):
        import json
        import main
        from card_coverage_gaps import semantic_reviews

        coverage = json.loads(
            (ROOT / "reports/systematic-audit/coverage-status.json").read_text(
                encoding="utf-8"
            )
        )
        automation = json.loads(
            (ROOT / "public/automation-coverage.json").read_text(
                encoding="utf-8"
            )
        )
        report = build_inventory(
            coverage, automation, main.CARD_DATA, semantic_reviews()
        )
        covered = {card["cardId"] for card in coverage["cards"]}
        uncovered = {card["cardId"] for card in report["cards"]}
        catalog = {card["id"] for card in main.CARD_DATA}
        self.assertEqual(covered | uncovered, catalog)
        self.assertFalse(covered & uncovered)
        self.assertEqual(
            len(uncovered),
            coverage["summary"]["cardsOutsideThisStrictRegister"],
        )


if __name__ == "__main__":
    unittest.main()
