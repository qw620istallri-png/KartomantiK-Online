"""Publish strict selected-clause proof for five reactive passive cards."""

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from card_tribute_economy_audit import EvidenceResult, ROOT, source_digest

sys.path.insert(0, str(ROOT / "tests"))
from test_reactive_passives_family import (  # noqa: E402
    HONOR,
    LIFE,
    MASS,
    OUTCAST,
    SOUP,
    ReactivePassivesFamily,
)


CARD_METHODS = {
    OUTCAST: (
        "compiles_all_five_exact_contracts",
        "outcast_acceptance_swaps_the_complete_position_and_target",
        "outcast_real_declaration_can_be_declined_without_mutating_payment",
        "outcast_requires_opposing_effect_eligible_source_and_confrontation_target",
    ),
    SOUP: (
        "compiles_all_five_exact_contracts",
        "soup_allows_a_real_persistent_will_response_only_for_its_controller",
        "soup_requires_an_active_interzone_source_and_keeps_empty_stack_limits",
    ),
    MASS: (
        "compiles_all_five_exact_contracts",
        "mass_redirects_only_opposing_targets_of_allied_manifestations",
        "mass_does_not_redirect_a_will_and_deduplicates_multiple_redirects",
        "mass_requires_an_active_retargetable_source_and_follows_control",
    ),
    HONOR: (
        "compiles_all_five_exact_contracts",
        "honor_scores_ten_only_for_exactly_one_winning_manifestation",
        "honor_sources_stack_but_only_for_the_winner_and_while_active",
    ),
    LIFE: (
        "compiles_all_five_exact_contracts",
        "life_sustains_exact_zero_and_permanently_removes_effects",
        "life_destroys_below_zero_and_exact_zero_without_an_active_source",
        "life_is_global_applies_to_tokens_and_ends_for_sustained_zero_cards",
    ),
}

EXPECTED_BEHAVIORS = {
    OUTCAST: (
        "While an active Wandering Outcast is in its controller's Interzone, that controller may answer an opposing card or effect targeting one of their Confrontation Manifestations by swapping the two complete field positions and retargeting the effect to Outcast. The choice is atomic and optional; own effects, non-Manifestations, other zones, disabled sources, protection, Immunity, and the opt-out preference do not swap.",
    ),
    SOUP: (
        "While an active Soup is in its controller's Interzone, only that controller may play a Persistent Will in every timing window where an Ephemeral Will could be played, including as a response. This changes timing only: printed empty-Stack restrictions remain, and a missing, face-down, disabled, or wrongly positioned Soup grants no permission.",
    ),
    MASS: (
        "While an active Obtrusive Mass is on its controller's field, an opposing card or effect that would target another Manifestation controlled by that player targets Mass instead. Own effects, opposing cards, Wills, Mass itself, inactive sources, and a Mass protected or Immune from the incoming controller are not redirected; current control governs the effect and duplicate redirected targets collapse to one target.",
    ),
    HONOR: (
        "Each active Honor and Respect controlled by the confrontation winner gives that player exactly 10 Points when, after state actions, they control exactly one Manifestation in the Confrontation Zone. Two winning Manifestations, a losing controller, or an inactive source gives nothing; multiple active copies each apply once.",
    ),
    LIFE: (
        "While at least one active Life Sustainer is on the field, every Manifestation, including Tokens and either player's cards, that reaches exactly zero Power remains and permanently loses its effects. A Manifestation below zero is still destroyed; without an active source an exact-zero card is destroyed, and a sustained card still at zero is destroyed when the last source leaves.",
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
        ReactivePassivesFamily,
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
            "This proof certifies the five printed paragraphs of Wandering Outcast, Soup, Obtrusive Mass, Honor and Respect, and Life Sustainer across the selected strict branches.",
            "It does not independently re-certify every generic target, protection, Immunity, Stack timing, confrontation, state-action, or token contract.",
        ],
    }
    out = ROOT / "reports/systematic-audit/reactive-passives-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
