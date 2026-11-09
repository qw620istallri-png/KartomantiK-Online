"""Publish strict player-loss proof for Grudge Weaver and Zborh."""

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_player_loses_confrontation_family import (  # noqa: E402
    PLAYER_LOSES_CONFRONTATION_NAMES,
    PlayerLosesConfrontationFamily,
)


METHODS = (
    "both_compile_the_exact_selected_contracts",
    "real_loss_queues_both_global_interzone_triggers",
    "wrong_outcome_zone_or_inactive_source_does_not_trigger",
    "triggers_follow_current_controller_after_control_change",
    "grudge_adds_exactly_one_counter_per_loss",
    "grudge_spends_two_counters_for_support_this_turn_only",
    "zborh_returns_to_immutable_owner_hand_after_controller_loses",
)

SELECTED_PARAGRAPHS = {
    "Grudge Weaver": (0, 1),
    "Zborh, the Eternal": (1,),
}

EXPECTED_BEHAVIORS = {
    "Grudge Weaver": (
        "While active in the Interzone, Grudge Weaver receives exactly one Grudge counter whenever its current controller loses a non-stalemate confrontation. A win, stalemate, inactive source, wrong zone, or loss by a different player adds nothing.",
        "During the Reaction, removing exactly two Grudge counters from an active Grudge Weaver in any field zone grants that occurrence Support for the current turn only. Insufficient counters reject the declaration atomically.",
    ),
    "Zborh, the Eternal": (
        "While active in the Interzone, Zborh triggers when its current controller loses a non-stalemate confrontation and, upon resolution, returns that same occurrence to its immutable owner's hand. It does not trigger on a win, stalemate, wrong zone, inactive source, or another player's loss.",
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
        PlayerLosesConfrontationFamily,
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
    for name in PLAYER_LOSES_CONFRONTATION_NAMES:
        card = catalog[name]
        paragraphs = printed_paragraphs(card["effect"])
        selected = SELECTED_PARAGRAPHS[name]
        expected = EXPECTED_BEHAVIORS[name]
        if len(selected) != len(expected) or any(
            index >= len(paragraphs) for index in selected
        ):
            raise AssertionError(f"{name}: selected paragraph is unavailable")
        covered_card_ids.add(card["id"])
        for index, behavior in zip(selected, expected):
            printed = paragraphs[index]
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
            "This proof certifies both Grudge Weaver paragraphs and Zborh's controller-loss paragraph, including real confrontation outcomes, Interzone and active-source scope, current controller after control change, Grudge count and activation cost, Support lifetime, and Zborh's immutable-owner destination.",
            "It does not re-certify Zborh's separate Adamant keyword, every confrontation cleanup order, simultaneous ordering among multiple copies, or all movement replacements that may replace a return to hand.",
        ],
    }
    out = ROOT / "reports/systematic-audit/player-loses-confrontation-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
