"""Publish the strict used-as-Tribute family proof."""
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_used_as_tribute_family import (  # noqa: E402
    USED_AS_TRIBUTE_NAMES,
    UsedAsTributeFamily,
)


METHODS = (
    "all_six_compile_the_exact_used_as_tribute_contract",
    "real_will_payment_moves_each_tribute_and_fires_exactly_once",
    "discard_is_not_tribute_and_paid_will_memories_require_a_will_play",
    "each_card_specific_first_transition_is_authoritative",
)


def printed_tribute_paragraph(name, effect):
    paragraphs = [
        paragraph.strip()
        for paragraph in str(effect or "").replace("\r\n", "\n").split("\n")
        if paragraph.strip()
    ]
    if name == "Zozok, the Void":
        return "\n".join(paragraphs)
    return next(
        paragraph for paragraph in paragraphs
        if "as tribute" in paragraph.lower()
    )


def main():
    start = audit.digest()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(UsedAsTributeFamily)
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
    for name in USED_AS_TRIBUTE_NAMES:
        card = catalog[name]
        printed = printed_tribute_paragraph(name, card["effect"])
        clauses.append({
            "cardId": card["id"],
            "name": name,
            "paragraphIndex": None,
            "printedParagraph": printed,
            "paragraphSha256": hashlib.sha256(
                printed.encode()
            ).hexdigest(),
            "expectedBehavior": (
                "A real Tribute payment moves the card to its authoritative "
                "destination and fires its used-as-Tribute trigger exactly "
                "once. A discard does not fire it; paid-Will memories require "
                "an actual Will play. The valid trigger begins the printed "
                "memory, shuffle or retained-essence result."
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
            "This proof certifies real Tribute-event eligibility and the first card-specific transition, not every delayed end-of-turn branch.",
            "Opponent payment, optional acceptance, Loop's later confrontation history and Qu Lom's final parity destinations remain covered by their dedicated delayed-memory family.",
        ],
    }
    out = ROOT / "reports/systematic-audit/used-as-tribute-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
