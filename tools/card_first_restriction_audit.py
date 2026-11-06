"""Publish strict proof for the two remaining First Manifestation restrictions."""

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_first_restriction_family import (  # noqa: E402
    FIRST_RESTRICTION_NAMES,
    FirstRestrictionFamily,
)


METHODS = (
    "both_compile_the_exact_printed_contracts",
    "both_are_rejected_atomically_as_first_but_do_not_poison_the_hand",
    "giant_rejects_neighbor_phase_and_wrong_field_zone_without_payment",
    "giant_pays_once_then_really_enters_support_from_hand_or_interzone",
    "brioski_really_enters_support_from_hand_and_interzone",
    "brioski_float_shares_a_full_interzone_slot_on_cleanup",
)

EXPECTED_BEHAVIORS = {
    "Diabolical Giant": (
        "Diabolical Giant is never a legal First Manifestation; rejecting it leaves the simultaneous choice unchanged and does not make another legal card in the same hand unavailable.",
        "During Reaction, Diabolical Giant may pay exactly 10 points from its controller's Hand or active Interzone to gain Support until end of turn, after which it can really enter Support without paying the cost again; neighboring phases and other field zones are rejected atomically.",
    ),
    "Brioski, the Aerial": (
        "Brioski may really enter Support from either Hand or Interzone during Reaction, and Float lets it share an occupied slot when cleanup returns it to a full Interzone.",
        "Brioski is never a legal First Manifestation; rejecting it leaves the simultaneous choice unchanged and does not make another legal card in the same hand unavailable.",
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
        FirstRestrictionFamily
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
    for name in FIRST_RESTRICTION_NAMES:
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
            "This proof certifies the four printed paragraphs, the simultaneous First Manifestation refusals and each card's first authoritative Support or Float transition.",
            "It does not re-certify generic priority, all Support cleanup destinations, every opening-hand mulligan sequence or other cards sharing the same keywords.",
        ],
    }
    out = ROOT / "reports/systematic-audit/first-restriction-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
