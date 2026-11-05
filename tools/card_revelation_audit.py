"""Publish the strict Revelation-trigger family proof."""
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_revelation_family import (  # noqa: E402
    REVELATION_NAMES,
    RevelationFamily,
)


METHODS = (
    "all_six_compile_the_exact_revelation_contract",
    "each_live_face_up_source_queues_its_revelation_action",
    "hidden_disabled_absent_and_wrong_zone_sources_do_not_trigger",
    "each_card_specific_result_begins_after_the_valid_revelation",
)


def printed_revelation_paragraph(name, effect):
    paragraphs = [
        paragraph.strip()
        for paragraph in str(effect or "").replace("\r\n", "\n").split("\n")
        if paragraph.strip()
    ]
    if name == "Hermetic Hourglass":
        return next(
            paragraph for paragraph in paragraphs
            if "confrontation ends" in paragraph.lower()
        )
    return next(
        paragraph for paragraph in paragraphs
        if "revelation" in paragraph.lower()
    )


def main():
    start = audit.digest()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RevelationFamily)
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
    for name in REVELATION_NAMES:
        card = catalog[name]
        printed = printed_revelation_paragraph(name, card["effect"])
        clauses.append({
            "cardId": card["id"],
            "name": name,
            "paragraphIndex": None,
            "printedParagraph": printed,
            "paragraphSha256": hashlib.sha256(
                printed.encode()
            ).hexdigest(),
            "expectedBehavior": (
                "At Revelation, the shipped trigger is eligible only from a "
                "live face-up source and its exact printed zone. A hidden, "
                "disabled, absent or wrongly placed source does not trigger, "
                "and a valid trigger begins the printed card-specific result."
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
            "This proof certifies Revelation eligibility and the first card-specific transition, not every downstream choice branch.",
            "Payment acceptance or refusal, completed Chain resolution, end-of-turn cleanup and Persuasion's later penalty remain covered by their dedicated families.",
        ],
    }
    out = ROOT / "reports/systematic-audit/revelation-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
