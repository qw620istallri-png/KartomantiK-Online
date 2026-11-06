"""Publish strict proof for Mourning Offal and Twin-headed Druid Support."""

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_conditional_support_family import (  # noqa: E402
    CONDITIONAL_SUPPORT_NAMES,
    ConditionalSupportFamily,
)


METHODS = (
    "both_compile_the_exact_printed_contract",
    "without_the_exact_history_neither_card_has_support",
    "offal_follows_any_real_limbo_exit_and_really_enters_support",
    "playing_a_will_from_limbo_activates_offal_for_this_turn_only",
    "limbo_entry_reorder_failure_and_old_exit_do_not_activate_offal",
    "druid_requires_its_controllers_loss_on_exactly_the_previous_turn",
    "actual_previous_confrontation_loss_lets_druid_enter_support",
)

EXPECTED_BEHAVIORS = {
    "Mourning Offal": (
        "A real card exit or Will play from any Limbo during the current turn gives Mourning Offal Support from Hand or Interzone. A Limbo entry, an in-Limbo reorder, a failed move or an exit on an earlier turn does not, and the permission expires on the next turn.",
    ),
    "Twin-headed Druid": (
        "Twin-headed Druid has Support from Hand or Interzone exactly when its controller lost the previous turn's confrontation; a current-turn or older loss, the opponent's loss and a Stalemate do not qualify.",
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
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        ConditionalSupportFamily
    )
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
    for name in CONDITIONAL_SUPPORT_NAMES:
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
            "This proof certifies both printed Support conditions, their turn boundaries, real Hand and Interzone entries, and the distinction between leaving Limbo and merely entering or reordering it.",
            "It does not re-certify generic Support cleanup, all possible card effects that move cards out of Limbo, or every confrontation-resolution branch.",
        ],
    }
    out = ROOT / "reports/systematic-audit/conditional-support-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
