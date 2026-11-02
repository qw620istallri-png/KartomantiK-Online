"""Publish text-grounded evidence for the ten Interzone Tribute cards."""
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_interzone_tribute_family_clauses import (
    END_PHASE_FAMILY,
    FIXED_TWO_FAMILY,
    InterzoneTributeFamilyClauses,
)


def main():
    start = audit.digest()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        InterzoneTributeFamilyClauses
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

    def add(name, paragraph_index, expectation, methods, extra_ids=()):
        card = catalog[name]
        printed = [
            line.strip()
            for line in card["effect"].splitlines()
            if line.strip()
        ][paragraph_index]
        tests = [executions["test_" + method] for method in methods]
        clauses.append({
            "cardId": card["id"],
            "name": name,
            "paragraphIndex": paragraph_index,
            "printedParagraph": printed,
            "paragraphSha256": hashlib.sha256(
                printed.encode()
            ).hexdigest(),
            "expectedBehavior": expectation,
            "testIds": [
                *[test["testId"] for test in tests],
                *extra_ids,
            ],
            "status": (
                "selected-branches-pass"
                if all(test["status"] == "pass" for test in tests)
                else "fail"
            ),
            "allBranchesCertified": False,
        })

    for name in END_PHASE_FAMILY:
        add(
            name, 0,
            "Playable from Hand into the Interzone only during End actions with priority, an empty Stack and available Interzone space.",
            (
                "family_text_and_compilation_are_exact",
                "end_phase_family_has_exact_timing_and_printed_interzone_tribute",
            ),
            (
                "test_websocket_integration.WebSocketRulesIntegrationTests.test_flem_is_played_into_the_interzone_only_during_end_actions",
            ) if name == "Flem" else (),
        )
        add(
            name, 1,
            "Can pay Tribute from the Interzone for exactly its printed one Power.",
            (
                "family_text_and_compilation_are_exact",
                "end_phase_family_has_exact_timing_and_printed_interzone_tribute",
            ),
        )
    for name in FIXED_TWO_FAMILY:
        add(
            name, 0,
            "Can be selected as Tribute from the Interzone.",
            (
                "family_text_and_compilation_are_exact",
                "fixed_two_family_is_worth_two_from_hand_and_interzone_not_five",
            ),
        )
        add(
            name, 1,
            "Whenever used as Tribute, from Hand or Interzone, its value is exactly two of its printed temperament rather than printed Power five.",
            (
                "family_text_and_compilation_are_exact",
                "fixed_two_family_is_worth_two_from_hand_and_interzone_not_five",
            ),
        )
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
            "cardsWithSelectedClauseProof": 10,
            "fullCatalogSemanticCertification": False,
        },
        "clauses": clauses,
        "tests": result.executions,
        "limits": [
            "The shared End-action placement path has a real WebSocket proof on Flem and identical per-card timing gates for all five cards.",
            "Other cards that alter Tribute values or Interzone permissions remain separate interactions.",
        ],
    }
    out = ROOT / "reports/systematic-audit/interzone-tribute-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
