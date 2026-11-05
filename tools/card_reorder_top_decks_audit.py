"""Publish strict proof for the five top-of-Deck reorder cards."""
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_reorder_top_decks_family import (  # noqa: E402
    REORDER_NAMES,
    ReorderTopDecksFamily,
)


METHODS = (
    "all_five_compile_the_exact_reorder_contract",
    "shababba_and_dissect_reorder_the_printed_decks_atomically",
    "tut_pays_one_hollow_and_enforces_two_top_one_bottom",
    "glimpse_draws_and_eviscerate_discards_after_the_chosen_order",
)

EXPECTED_BEHAVIORS = {
    "Shababba, Divining Cube": (
        "Only an Interzone Shababba triggers at end of turn; it exposes exactly the top four cards of its controller's Deck and applies the chosen top and bottom order.",
    ),
    "Glimpse the Omens": (
        "Glimpse exposes exactly the top four cards of its controller's Deck, applies any valid top and bottom order, then draws the new top card.",
    ),
    "Tut, Rhythmic Whirlwind": (
        "Tut's field activation spends one Hollow Essence, exposes up to three cards, and requires exactly two on top and one on the bottom when three are available.",
    ),
    "Dissect": (
        "Dissect exposes the top three cards of every player's Deck and commits every owner's chosen top and bottom order atomically.",
    ),
    "Eviscerate Morality": (
        "Eviscerate Morality exposes exactly the top four cards of its controller's Deck, applies the chosen order, then discards the resulting top two cards.",
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
        ReorderTopDecksFamily
    )
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
    for name in REORDER_NAMES:
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
            "This proof certifies the five printed reorder clauses, their legal choice shape and their first authoritative continuation.",
            "It does not re-certify generic Deck privacy, reconnect persistence or unrelated draw and discard replacement families.",
        ],
    }
    out = ROOT / "reports/systematic-audit/reorder-top-decks-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
