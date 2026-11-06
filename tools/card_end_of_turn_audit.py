"""Publish strict proof for the three remaining end-of-turn trigger cards."""

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_end_of_turn_family import (  # noqa: E402
    END_OF_TURN_NAMES,
    EndOfTurnFamily,
)


METHODS = (
    "all_three_compile_the_exact_printed_contracts",
    "end_trigger_source_zones_activity_and_skipped_phase_are_exact",
    "ergorath_plays_limbo_wills_for_one_hollow_and_exiles_them",
    "ergorath_end_trigger_penalizes_controller_then_shuffles_to_owner",
    "grimoire_places_plays_and_exiles_its_attached_wills",
    "tax_applies_both_printed_events_and_both_payment_branches",
)

EXPECTED_BEHAVIORS = {
    "Ergorath, Scribe of the Limbo": (
        "While an active Ergorath is on the field, its controller may play a Will from their Limbo for one Hollow Tribute instead of its printed Tribute.",
        "A Will played through Ergorath is marked so any later move toward a Limbo, Hand or Deck is replaced by exile, including resolution, neutralization and departure from the field.",
        "At end of turn only an active Interzone Ergorath triggers; on resolution its current controller loses 10 points, then Ergorath is shuffled into its owner's Deck.",
    ),
    "Grimoire": (
        "At end of turn an active Field Grimoire may receive any number of Wills from its controller's Hand; attached Wills remain playable with their own abilities and costs as if in Hand, and only Wills still attached are exiled when Grimoire leaves the field.",
    ),
    "Tax of the Malignant": (
        "An active Tax triggers both upon Resolution and at end of turn; for each player independently it removes all excess Essence when any exists, otherwise that player loses 5 points.",
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
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(EndOfTurnFamily)
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
    for name in END_OF_TURN_NAMES:
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
            "This proof certifies the five printed paragraphs, their exact end-of-turn or Resolution carriers, source activity gates and first authoritative transitions.",
            "It does not re-certify every generic Tribute allocation, random shuffle ordering, simultaneous-trigger order or movement replacement owned by other families.",
        ],
    }
    out = ROOT / "reports/systematic-audit/end-of-turn-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
