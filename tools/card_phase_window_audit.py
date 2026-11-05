"""Publish strict proof for the three remaining Reaction-window cards."""

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_phase_window_family import (  # noqa: E402
    PHASE_WINDOW_NAMES,
    PhaseWindowFamily,
)


METHODS = (
    "all_three_compile_the_exact_reaction_contract",
    "neighbor_phase_rejections_are_atomic_for_all_three_cards",
    "timid_brain_pays_a_distinct_will_then_plays_as_support",
    "ranba_rejects_a_strong_last_support_then_takes_a_weak_one",
    "ranba_discards_but_does_not_abduct_a_card_you_own",
    "denegath_gates_source_and_payment_then_returns_and_chains",
)

EXPECTED_BEHAVIORS = {
    "Timid Brain": (
        "Only during Reaction and while Timid Brain remains in Hand, its controller may discard a distinct Will; the Immediate Effect then creates a normal responseable play of Timid Brain in Support and leaves no stale permission.",
    ),
    "Ranba, Silent Abductor": (
        "Only during Reaction, when the latest opposing Support entry still has base power 2 or less, Ranba is revealed and discarded from Hand; on resolution that Support enters the controller's Vessel only if the controller does not own it.",
    ),
    "Denegath, the Regulator": (
        "Only during Reaction from the Interzone, a ready Denegath exhausts and pays two Hollow Essence; on resolution its controller's First Manifestation returns to its owner's Hand, is barred from play for the turn, and a different legal Hand Manifestation is chained.",
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
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PhaseWindowFamily)
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
    covered_card_ids = set()
    for name in PHASE_WINDOW_NAMES:
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
            "This proof certifies the three printed paragraphs, their exact Reaction windows, legal source or cost gates, atomic refusals and first authoritative transitions.",
            "It does not re-certify every generic Stack response, movement replacement, Vessel capacity interaction or Chain outcome owned by other families.",
        ],
    }
    out = ROOT / "reports/systematic-audit/phase-window-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
