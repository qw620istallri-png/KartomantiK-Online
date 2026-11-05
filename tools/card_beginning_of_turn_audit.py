"""Publish the strict beginning-of-turn family proof."""
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_beginning_of_turn_family import (  # noqa: E402
    BEGINNING_OF_TURN_NAMES,
    BeginningOfTurnFamily,
)


METHODS = (
    "all_eight_compile_the_exact_beginning_of_turn_contract",
    "each_queues_once_from_its_exact_live_zone",
    "wrong_zone_face_down_owner_vessel_and_counter_threshold_do_not_trigger",
    "each_card_specific_result_begins_after_the_valid_trigger",
)


def printed_beginning_paragraph(effect):
    paragraphs = [
        paragraph.strip()
        for paragraph in str(effect or "").replace("\r\n", "\n").split("\n")
        if paragraph.strip()
    ]
    return next(
        paragraph for paragraph in paragraphs
        if "beginning" in paragraph.lower()
    )


def main():
    start = audit.digest()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BeginningOfTurnFamily)
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
    for name in BEGINNING_OF_TURN_NAMES:
        card = catalog[name]
        printed = printed_beginning_paragraph(card["effect"])
        clauses.append({
            "cardId": card["id"],
            "name": name,
            "paragraphIndex": None,
            "printedParagraph": printed,
            "paragraphSha256": hashlib.sha256(
                printed.encode()
            ).hexdigest(),
            "expectedBehavior": (
                "At the beginning of a turn, the shipped trigger is eligible "
                "only from its exact live zone, vessel relationship and source "
                "counter threshold. It queues once per turn, remains inactive "
                "when face down or otherwise ineligible, and a valid trigger "
                "begins the printed card-specific result or ongoing effect."
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
            "This proof certifies beginning-of-turn eligibility, once-per-turn queuing and the first card-specific transition, not every downstream choice branch.",
            "Payment acceptance or refusal, later hand-limit enforcement, multi-player follow-up choices and complete end-of-turn cleanup remain covered by their dedicated families.",
        ],
    }
    out = ROOT / "reports/systematic-audit/beginning-of-turn-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
