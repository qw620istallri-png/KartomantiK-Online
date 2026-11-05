"""Publish the strict zone-card target family proof."""
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_zone_card_target_family import (  # noqa: E402
    ZONE_CARD_TARGET_NAMES,
    ZoneCardTargetFamily,
)


METHODS = (
    "all_eleven_compile_the_exact_zone_card_contract",
    "each_accepts_its_canonical_zone_target_and_rejects_wrong_kind",
    "zone_visibility_versions_and_duplicate_normalization_are_authoritative",
    "cardinality_owner_container_type_and_temporal_constraints",
    "each_card_specific_result_begins_from_a_valid_zone_target",
)


def printed_target_paragraph(effect):
    paragraphs = [
        paragraph.strip()
        for paragraph in str(effect or "").replace("\r\n", "\n").split("\n")
        if paragraph.strip()
    ]
    return next(
        paragraph for paragraph in paragraphs
        if "target" in paragraph.lower() or "from your hand" in paragraph.lower()
    )


def main():
    start = audit.digest()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ZoneCardTargetFamily)
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
    for name in ZONE_CARD_TARGET_NAMES:
        card = catalog[name]
        printed = printed_target_paragraph(card["effect"])
        clauses.append({
            "cardId": card["id"],
            "name": name,
            "paragraphIndex": None,
            "printedParagraph": printed,
            "paragraphSha256": hashlib.sha256(
                printed.encode()
            ).hexdigest(),
            "expectedBehavior": (
                "The printed effect accepts only the declared public-zone card "
                "or the controller's own Hand card, with exact cardinality, "
                "type, owner, container and temporal constraints. Missing, "
                "private, stale, duplicate or otherwise invalid targets are "
                "rejected without mutation. A valid target begins the printed "
                "card-specific result and its first authoritative state change."
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
            "This proof certifies the zone-card target contract and the first card-specific result transition, not every downstream trigger or replacement.",
            "Later choices, confrontation outcomes, immunity interactions and complete multi-step aftermath remain covered by their dedicated families.",
        ],
    }
    out = ROOT / "reports/systematic-audit/zone-card-target-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
