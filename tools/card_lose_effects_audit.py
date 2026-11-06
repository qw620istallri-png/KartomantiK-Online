"""Publish strict proof for Vexing Thorn and Embottle's lose-effects clauses."""

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_lose_effects_family import (  # noqa: E402
    LOSE_EFFECTS_NAMES,
    LoseEffectsFamily,
)


METHODS = (
    "both_compile_the_exact_printed_contract",
    "invalid_sources_and_targets_are_rejected_without_payment",
    "thorn_pays_two_power_then_disables_the_live_target",
    "thorn_cost_remains_paid_when_the_target_leaves_in_response",
    "embottle_pays_four_and_disables_each_printed_card_type",
    "resolved_silence_survives_its_source_but_not_target_reentry",
)

EXPECTED_BEHAVIORS = {
    "Vexing Thorn": (
        "While Vexing Thorn is active in its controller's Interzone, its controller may immediately reduce its power by exactly 2 to target a Manifestation on the field. On resolution that exact field occurrence loses its effects until it leaves the field; an invalid source or target is rejected without payment, while a target that leaves in response does not refund the paid reduction.",
    ),
    "Embottle": (
        "After its four Capricious Tributes are paid, Embottle may target exactly one Manifestation or Persistent Will on the field. That exact field occurrence loses its effects independently of Embottle until it leaves the field; Ephemeral Wills and cards in Stalemate are rejected atomically, and a later occurrence of the same physical card is active again.",
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
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(LoseEffectsFamily)
    result = unittest.TextTestRunner(
        verbosity=1,
        resultclass=EvidenceResult,
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
    for name in LOSE_EFFECTS_NAMES:
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
            "This proof certifies the two printed paragraphs, their legal source and target contracts, payment timing, first lose-effects transition and target-occurrence lifetime.",
            "It does not re-certify every card whose effects can be blanked, all generic Stack neutralization paths or other cards sharing the lose_effects engine primitive.",
        ],
    }
    out = ROOT / "reports/systematic-audit/lose-effects-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
