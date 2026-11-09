"""Publish strict proof for Phimosino and Piercing Lover."""

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_end_of_game_family import (  # noqa: E402
    END_OF_GAME_NAMES,
    EndOfGameFamily,
)


METHODS = (
    "both_compile_the_exact_printed_contract",
    "phimosino_gives_fifty_points_only_from_its_owners_deck",
    "phimosino_scores_for_whichever_owner_has_it_in_their_deck",
    "piercing_lover_requires_an_opponents_empathic_vessel",
    "piercing_lover_counts_only_manifestations_with_base_power_at_most_two",
    "each_players_end_game_adjustment_is_independent_and_additive",
    "unreachable_pillar_suppresses_the_lover_only_while_active",
)

EXPECTED_BEHAVIORS = {
    "Phimosino": (
        "At final scoring, Phimosino gives exactly 50 end-game points to the owner whose deck contains it. It gives no such points from the hand, field, Empathic Vessel, Limbo or exile, and its 50 points remain additive with ordinary deck and effect points.",
    ),
    "Piercing Lover": (
        "At final scoring, Piercing Lover applies only while it is owned by a player other than the controller of the Empathic Vessel containing it. That Vessel player loses exactly 5 points for each Manifestation there whose printed base power is at most 2, regardless of those Manifestations' owners; Wills and higher-base-power Manifestations do not count. Unreachable Pillar suppresses the penalty while it removes that Vessel's effects.",
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
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(EndOfGameFamily)
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
    for name in END_OF_GAME_NAMES:
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
            "This proof certifies both printed final-score clauses, their exact zones, values, ownership or Vessel relation, Piercing Lover's card-type and base-power count, additive score integration and Unreachable Pillar suppression.",
            "It does not re-certify ordinary Vessel card points, deck points, alternate-victory rules, or every other final-score passive.",
        ],
    }
    out = ROOT / "reports/systematic-audit/end-of-game-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
