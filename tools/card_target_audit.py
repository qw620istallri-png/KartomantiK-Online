"""Publish the strict live-card target family proof."""
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_card_target_family import (  # noqa: E402
    CARD_TARGET_NAMES,
    CardTargetFamily,
)


METHODS = (
    "all_eight_abilities_compile_the_exact_card_target_contract",
    "each_accepts_its_canonical_live_target_and_rejects_wrong_kind",
    "cardinality_staleness_and_stalemate_field_boundary_are_authoritative",
    "zone_controller_outcome_type_and_power_constraints",
    "each_card_specific_result_begins_from_a_valid_card_target",
)


def printed_target_text(effect):
    paragraphs = [
        paragraph.strip()
        for paragraph in str(effect or "").replace("\r\n", "\n").split("\n")
        if paragraph.strip()
    ]
    explicit = [
        paragraph for paragraph in paragraphs
        if "target" in paragraph.lower()
    ]
    if explicit:
        return "\n".join(explicit)
    return next(
        paragraph for paragraph in paragraphs
        if "manifestation" in paragraph.lower()
    )


def main():
    start = audit.digest()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CardTargetFamily)
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
    for name in CARD_TARGET_NAMES:
        card = catalog[name]
        printed = printed_target_text(card["effect"])
        clauses.append({
            "cardId": card["id"],
            "name": name,
            "paragraphIndex": None,
            "printedParagraph": printed,
            "paragraphSha256": hashlib.sha256(
                printed.encode()
            ).hexdigest(),
            "expectedBehavior": (
                "The printed live-card target accepts exactly one authoritative "
                "card on the field and enforces its declared card type, field "
                "zone, controller, confrontation outcome and power threshold. "
                "The Stalemate Zone is excluded unless named, stale or malformed "
                "targets are rejected without mutation, and a valid target "
                "begins the printed card-specific result."
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
            "This proof certifies the live-card target boundary and the first card-specific transition, not every downstream cost, replacement or trigger branch.",
            "Censor's complete additional-cost lifecycle, later confrontation consequences and end-of-turn cleanup remain covered by their dedicated families.",
        ],
    }
    out = ROOT / "reports/systematic-audit/card-target-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
