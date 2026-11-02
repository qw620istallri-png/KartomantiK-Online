"""Publish selected printed clauses exercised through multi-step transitions."""
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_rules_transition_matrix import RulesTransitionMatrix


CONTRACTS = [
    (
        "Stampeding Brood",
        "The permanent Support token can be canceled while entering Support, retried, resolved, returned to Interzone after a win, and played again next turn.",
        ["token_support_cancel_retry_resolve_return_and_next_turn"],
    ),
    (
        "Ignore",
        "The payment choice cancels a target Token Support effect on the Stack when its controller declines.",
        ["token_support_cancel_retry_resolve_return_and_next_turn"],
    ),
    (
        "Herbaceous Whisperer",
        "Its +1 applies while the friendly token is actually in Support, not while that token waits in Interzone.",
        ["token_support_cancel_retry_resolve_return_and_next_turn"],
    ),
    (
        "Gnarlipuff, the Slimy",
        "The owner can activate it from an opponent's Vessel; availability, auto-pass, declaration, payment and destination agree.",
        ["receptacle_activation_availability_declaration_and_resolution_agree"],
    ),
    (
        "Rematch!",
        "The same-turn rematch preserves the recorded loss while restarting Reaction with both First Manifestations.",
        ["rematch_preserves_loss_for_recall_then_reset_clears_it"],
    ),
    (
        "Recall",
        "Recall remains legal after a same-turn rematch because the prior confrontation loss is still authoritative.",
        ["rematch_preserves_loss_for_recall_then_reset_clears_it"],
    ),
]


def main():
    start = audit.digest()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        RulesTransitionMatrix
    )
    result = unittest.TextTestRunner(
        verbosity=1, resultclass=EvidenceResult
    ).run(suite)
    executions = {
        test["testId"].rsplit(".", 1)[-1]: test
        for test in result.executions
    }
    catalog = {
        card["name"]: card for card in audit.batches.CATALOG.cards.values()
    }
    clauses = []
    for name, expectation, methods in CONTRACTS:
        card = catalog[name]
        printed = card["effect"].strip()
        tests = [executions["test_" + method] for method in methods]
        clauses.append({
            "cardId": card["id"],
            "name": name,
            "paragraphIndex": 0,
            "printedParagraph": printed,
            "paragraphSha256": hashlib.sha256(
                printed.encode()
            ).hexdigest(),
            "expectedBehavior": expectation,
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
            "selectedParagraphs": len(clauses),
            "cardsWithSelectedClauseProof": len(clauses),
            "fullCatalogSemanticCertification": False,
        },
        "clauses": clauses,
        "tests": result.executions,
        "limits": [
            "Selected transition branches only; no whole-card certification.",
            "Reset is asserted as the final boundary but is not itself a printed card clause.",
            "Browser playability remains covered by the separate client/server parity suite.",
        ],
    }
    out = ROOT / "reports/systematic-audit/transition-matrix-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
