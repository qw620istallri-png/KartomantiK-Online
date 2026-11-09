"""Publish strict proof for Destroy and Eliminate the Profane."""

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_move_target_family import (  # noqa: E402
    MOVE_TARGET_NAMES,
    MoveTargetFamily,
)


METHODS = (
    "both_compile_the_exact_printed_contract",
    "destroy_rejects_every_other_type_zone_and_cardinality_atomically",
    "eliminate_rejects_non_manifestations_and_non_vessel_zones_atomically",
    "destroy_really_destroys_each_printed_target_category",
    "eliminate_reaches_any_players_vessel_and_routes_to_the_owner",
    "destroy_cost_stays_paid_when_field_target_leaves_in_response",
    "eliminate_cost_stays_paid_when_vessel_target_leaves_in_response",
)

EXPECTED_BEHAVIORS = {
    "Destroy": (
        "Destroy pays three Hollow Tributes and targets exactly one Persistent or Ephemeral Will on the field, or one Manifestation in either player's Interzone. On resolution the target enters its owner's Limbo with destruction semantics; other field zones and card types are rejected atomically, while a target that leaves in response makes the effect do nothing without refunding the paid cost.",
    ),
    "Eliminate the Profane": (
        "Eliminate the Profane pays four Hollow Tributes and targets exactly one Manifestation in any player's Empathic Vessel, regardless of its owner. On resolution the target enters its owner's Limbo with destruction semantics; Wills and non-Vessel zones are rejected atomically, while a target that leaves in response makes the effect do nothing without refunding the paid cost.",
    ),
}


def printed_paragraphs(effect):
    return [
        paragraph.strip()
        for paragraph in str(effect or "").replace("\r\n", "\n").split("\n")
        if paragraph.strip()
    ]


def main():
    start = audit.digest()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MoveTargetFamily)
    result = unittest.TextTestRunner(
        verbosity=1, resultclass=EvidenceResult,
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
    covered_card_ids = set()
    for name in MOVE_TARGET_NAMES:
        card = catalog[name]
        paragraphs = printed_paragraphs(card["effect"])
        expected = EXPECTED_BEHAVIORS[name]
        if len(paragraphs) != len(expected):
            raise AssertionError(
                f"{name}: {len(paragraphs)} paragraphs, {len(expected)} oracles"
            )
        covered_card_ids.add(card["id"])
        for index, (printed, behavior) in enumerate(zip(paragraphs, expected)):
            clauses.append({
                "cardId": card["id"],
                "name": name,
                "paragraphIndex": index,
                "printedParagraph": printed,
                "paragraphSha256": hashlib.sha256(
                    printed.encode()
                ).hexdigest(),
                "expectedBehavior": behavior,
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
            "cardsWithSelectedClauseProof": len(covered_card_ids),
            "fullCatalogSemanticCertification": False,
        },
        "clauses": clauses,
        "tests": result.executions,
        "limits": [
            "This proof certifies both printed target domains, real Hollow Tribute payment, destruction into the immutable owner's Limbo, atomic invalid declarations and stale-target resolution.",
            "It does not re-certify every generic destruction replacement, all Protection or Immunity sources, or other cards that share the move_target primitive.",
        ],
    }
    out = ROOT / "reports/systematic-audit/move-target-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
