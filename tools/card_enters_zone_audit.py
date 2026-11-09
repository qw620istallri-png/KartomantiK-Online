"""Publish strict opponent-Vessel entry proof for Nimbus and Worm Bomb."""

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_enters_zone_family import (  # noqa: E402
    ENTERS_ZONE_NAMES,
    EntersZoneFamily,
)


METHODS = (
    "both_compile_the_exact_printed_contract",
    "both_trigger_only_when_they_enter_an_opponents_vessel",
    "nimbus_grants_the_card_owner_one_free_hand_will_this_turn",
    "nimbus_permission_cannot_be_reused_or_carried_to_the_next_turn",
    "worm_bomb_destroys_exactly_three_other_random_manifestations",
    "worm_bomb_destroys_all_available_manifestations_up_to_three",
    "unreachable_pillar_suppresses_both_vessel_entry_effects",
)

EXPECTED_BEHAVIORS = {
    "Inspired Nimbus": (
        "When Inspired Nimbus enters an opponent's Empathic Vessel, its immutable owner receives one permission for the current turn to play any Will from hand without Tribute. The Vessel player receives no permission, the permission is consumed by one declaration and cannot carry into the next turn, and Unreachable Pillar suppresses the Vessel entry effect while active.",
    ),
    "Worm Bomb": (
        "When Worm Bomb enters an opponent's Empathic Vessel, up to three random other Manifestations in that Vessel are destroyed to their respective owners' Limbo. Worm Bomb itself and all Wills are excluded, fewer than three eligible cards are all destroyed, and Unreachable Pillar suppresses the Vessel entry effect while active.",
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
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(EntersZoneFamily)
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
    for name in ENTERS_ZONE_NAMES:
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
            "This proof certifies both printed opponent-Vessel entry clauses, exact zone and ownership relations, Nimbus permission scope, consumption and lifetime, Worm Bomb's random pool, maximum count and owner destinations, and Unreachable Pillar suppression.",
            "It does not re-certify all confrontation-cleanup ordering, every Will playable through Nimbus, or all destruction replacements that may alter a Worm Bomb destination.",
        ],
    }
    out = ROOT / "reports/systematic-audit/enters-zone-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
