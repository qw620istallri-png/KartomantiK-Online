"""Publish strict selected-clause proof for the final three uncovered cards."""

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from card_tribute_economy_audit import EvidenceResult, ROOT, source_digest

sys.path.insert(0, str(ROOT / "tests"))
from test_final_three_cards_family import (  # noqa: E402
    GLOB_GLOB,
    QUASIMILLENARY,
    SLY_FROG,
    FinalThreeCardsFamily,
)


CARD_METHODS = {
    QUASIMILLENARY: (
        "compiles_all_three_exact_contracts",
        "quasi_offers_one_private_recovery_choice_and_decline_draws_from_deck",
        "quasi_yes_shuffles_limbo_draws_it_first_then_fills_from_deck_and_reveals",
        "quasi_requires_its_controllers_active_interzone_source_and_nonempty_limbo",
        "quasi_marked_hand_card_exiles_instead_of_entering_limbo_or_deck",
        "quasi_field_card_exiles_on_nonvessel_exit_but_vessel_clears_mark",
    ),
    GLOB_GLOB: (
        "compiles_all_three_exact_contracts",
        "glob_glob_hand_tribute_goes_to_bottom_of_immutable_owners_deck",
        "glob_glob_field_tribute_uses_the_same_owner_deck_replacement",
        "special_tribute_destinations_do_not_apply_to_ordinary_moves",
    ),
    SLY_FROG: (
        "compiles_all_three_exact_contracts",
        "sly_frog_hand_tribute_creates_one_stalemate_occurrence",
        "sly_frog_field_tribute_moves_the_existing_occurrence_to_stalemate",
        "special_tribute_destinations_do_not_apply_to_ordinary_moves",
    ),
}

EXPECTED_BEHAVIORS = {
    QUASIMILLENARY: (
        "During each Recovery draw, the controller of an active Quasimillenary in their Interzone may privately decline and draw normally, or shuffle their nonempty Limbo, draw from it first, and fill any remaining hand slots from the Deck. Limbo-drawn cards stay publicly uncovered and marked after Quasimillenary leaves: entering a Deck or Limbo, or leaving the field for any non-Vessel zone, exiles them instead; entering a Vessel is allowed and clears the mark.",
    ),
    GLOB_GLOB: (
        "Only when Glob-glob is actually used as Tribute, from the Hand or legally from the field, its destination is replaced with the bottom of its immutable owner's Deck instead of the Limbo. Current control determines who pays, ordinary moves remain ordinary, and the movement reports its true source zone and replacement destination.",
    ),
    SLY_FROG: (
        "Only when Sly Frog is actually used as Tribute, from the Hand or legally from the field, its existing or newly created occurrence enters the Stalemate Zone instead of the Limbo. Immutable ownership and current control are preserved, ordinary moves remain ordinary, and no duplicate Limbo card is created.",
    ),
}


def catalog():
    cards = json.loads(
        (ROOT / "public/cards-data.json").read_text(encoding="utf-8")
    )
    cards += json.loads(
        (ROOT / "public/extensions/inner-desert/cards.json").read_text(
            encoding="utf-8"
        )
    )
    return {card["id"]: card for card in cards if card["id"] in CARD_METHODS}


def main():
    start = source_digest()
    cards = catalog()
    result = unittest.TextTestRunner(
        verbosity=1, resultclass=EvidenceResult,
    ).run(unittest.defaultTestLoader.loadTestsFromTestCase(
        FinalThreeCardsFamily,
    ))
    executions = {
        test["testId"].rsplit(".", 1)[-1]: test
        for test in result.executions
    }
    clauses = []
    for card_id, methods in CARD_METHODS.items():
        card = cards[card_id]
        paragraphs = [
            line.strip() for line in str(card.get("effect") or "").splitlines()
            if line.strip()
        ]
        behaviors = EXPECTED_BEHAVIORS[card_id]
        if len(paragraphs) != len(behaviors):
            raise AssertionError(
                f"{card_id}: {len(paragraphs)} paragraphs != {len(behaviors)}"
            )
        tests = [executions["test_" + method] for method in methods]
        for index, (printed, behavior) in enumerate(zip(paragraphs, behaviors)):
            clauses.append({
                "cardId": card_id,
                "name": card["name"],
                "paragraphIndex": index,
                "printedParagraph": printed,
                "paragraphSha256": hashlib.sha256(printed.encode()).hexdigest(),
                "expectedBehavior": behavior,
                "testIds": [test["testId"] for test in tests],
                "status": (
                    "selected-branches-pass"
                    if all(test["status"] == "pass" for test in tests)
                    else "fail"
                ),
                "allBranchesCertified": False,
            })
    if source_digest() != start:
        raise RuntimeError("Sources changed during execution")
    proof = {
        "schemaVersion": 1,
        "sourceDigest": start,
        "published": False,
        "finishedAt": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "executed": result.testsRun,
            "passed": sum(test["status"] == "pass" for test in result.executions),
            "failed": len(result.failures) + len(result.errors),
            "skipped": len(result.skipped),
            "selectedClauses": len(clauses),
            "cardsWithSelectedClauseProof": len(CARD_METHODS),
            "fullCatalogSemanticCertification": False,
        },
        "clauses": clauses,
        "tests": result.executions,
        "limits": [
            "This proof closes the three remaining printed paragraphs for Quasimillenary, Glob-glob, and Sly Frog across their selected strict branches.",
            "It does not independently re-certify every generic Recovery, privacy, zone replacement, field-Tribute permission, Stack payment, or Stalemate contract.",
        ],
    }
    out = ROOT / "reports/systematic-audit/final-three-cards-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
