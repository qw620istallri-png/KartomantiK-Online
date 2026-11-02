"""Publish exact printed payment fragments for fourteen Tribute abilities."""
import hashlib
import json
import re
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_tribute_cost_family_clauses import (
    TRIBUTE_COSTS,
    TributeCostFamilyClauses,
)


METHODS = (
    "printed_and_encoded_tribute_amounts_match_exactly",
    "exact_tribute_is_spent_and_action_enters_the_stack",
    "missing_tribute_rejects_without_mutating_source_or_stack",
)


def payment_fragment(text):
    matches = re.findall(
        r"[Pp]ay (?:(?:\{H\})+|(?:\d+ )?🔘+)",
        text,
    )
    if not matches:
        raise RuntimeError(f"Missing printed payment fragment: {text}")
    return matches[-1]


def main():
    start = audit.digest()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        TributeCostFamilyClauses
    )
    result = unittest.TextTestRunner(
        verbosity=1, resultclass=EvidenceResult
    ).run(suite)
    executions = {
        test["testId"].rsplit(".", 1)[-1]: test
        for test in result.executions
    }
    tests = [executions["test_" + method] for method in METHODS]
    catalog = {
        card["name"]: card for card in audit.batches.CATALOG.cards.values()
    }
    clauses = []
    for name, amount in TRIBUTE_COSTS.items():
        card = catalog[name]
        printed = payment_fragment(card["effect"])
        clauses.append({
            "cardId": card["id"],
            "name": name,
            "paragraphIndex": None,
            "printedParagraph": printed,
            "paragraphSha256": hashlib.sha256(
                printed.encode()
            ).hexdigest(),
            "expectedBehavior": (
                f"The ability requires exactly {amount} Hollow Tribute. "
                "Exact payment declares the action and insufficient payment "
                "leaves source, players and Stack unchanged."
            ),
            "testIds": [test["testId"] for test in tests],
            "status": (
                "selected-branches-pass"
                if all(test["status"] == "pass" for test in tests)
                else "fail"
            ),
            "allBranchesCertified": False,
        })
    if audit.digest() != start:
        raise RuntimeError("Sources changed during execution")
    proof = {
        "schemaVersion": 1,
        "sourceDigest": start,
        "published": False,
        "finishedAt": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "executed": result.testsRun,
            "passed": sum(
                test["status"] == "pass" for test in result.executions
            ),
            "failed": len(result.failures) + len(result.errors),
            "skipped": len(result.skipped),
            "selectedClauses": len(clauses),
            "cardsWithSelectedClauseProof": len(clauses),
            "fullCatalogSemanticCertification": False,
        },
        "clauses": clauses,
        "tests": result.executions,
        "limits": [
            "This proof certifies the printed Tribute amount and payment atomicity, not every branch of the resulting effect.",
            "Targets, durations and destinations remain covered by card-specific tests.",
        ],
    }
    out = ROOT / "reports/systematic-audit/tribute-cost-family-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
