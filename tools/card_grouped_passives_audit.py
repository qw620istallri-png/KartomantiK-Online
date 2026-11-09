"""Publish strict selected-clause proof for five continuous-effect cards."""

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_grouped_passives_family import (  # noqa: E402
    ASCIUGOTH,
    BALANCE,
    DISCOMBOBULATOR,
    OIL_DOG,
    SOLITARY_COMBHAND,
    GroupedPassivesFamily,
)


CARD_METHODS = {
    BALANCE: (
        "compiles_all_five_exact_contracts",
        "balance_redirects_only_strict_richest_gain_and_poorest_loss",
        "balance_uses_vessel_card_points_and_ties_do_not_redirect",
        "global_point_prevention_runs_before_balance",
    ),
    DISCOMBOBULATOR: (
        "compiles_all_five_exact_contracts",
        "discombobulator_can_pay_four_hollow_and_remain",
        "discombobulator_decline_exiles_it_and_releases_other_cards",
        "first_discombobulator_blanks_later_copy_but_keeps_own_upkeep",
        "stalemate_is_outside_discombobulators_field_blanking",
    ),
    ASCIUGOTH: (
        "compiles_all_five_exact_contracts",
        "asciugoth_absorbs_entering_temperament_and_hollows_card_and_token",
        "asciugoth_does_not_absorb_itself_and_first_source_wins_ties",
        "cleanse_restores_asciugoths_original_temperament",
    ),
    OIL_DOG: (
        "compiles_all_five_exact_contracts",
        "oil_dog_changes_payment_view_without_mutating_stored_essence",
        "multiple_oil_dogs_do_not_stack_and_one_remaining_keeps_effect",
        "oil_dog_does_not_turn_an_unspent_gem_counter_into_essence",
    ),
    SOLITARY_COMBHAND: (
        "compiles_all_five_exact_contracts",
        "solitary_combhand_counts_current_empty_interzone_slots",
        "solitary_combhand_counts_float_stacks_as_one_slot",
        "solitary_combhand_uses_extended_capacity_not_printed_three",
        "solitary_combhand_outside_interzone_grants_no_extra_draw",
    ),
}

EXPECTED_BEHAVIORS = {
    BALANCE: (
        "A strictly richest Vessel cannot gain points: its gain is prevented and every other player gains exactly that amount once. Vessel totals include both score and printed points of Vessel cards; tied totals are not redirected; a global point-change prevention effect takes precedence.",
        "A strictly poorest Vessel cannot lose points: its loss is prevented and every other player loses exactly that amount once. Ordinary losses by the richest and gains by the poorest are unchanged, and the redirected change cannot recursively invoke Balance.",
    ),
    DISCOMBOBULATOR: (
        "Before Revelation, the active Discombobulator's controller may pay exactly four Hollow Tribute and keep it. Declining exiles that source and immediately releases cards it had blanked; a copy already blanked by an earlier copy does not create an upkeep trigger.",
        "The earliest active Discombobulator in battlefield order keeps its own effects and removes the effects of every other card on the field, including later copies. Stalemate is outside the field: cards there are not blanked and a Discombobulator there does not blank field cards.",
    ),
    ASCIUGOTH: (
        "For each entering Manifestation, the earliest active Asciugoth gains one excess essence of the entering card's current Temperament and that card becomes Hollow. Token Manifestations are included, Asciugoth never replaces its own entry, multiple copies do not duplicate the replacement, and Cleanse restores the printed Temperament.",
    ),
    OIL_DOG: (
        "While at least one active Oil-Dog is on the field, every stored excess essence has Hollow payment identity without changing its stored Temperament. This removes Transcendent and matching-color flexibility, does not stack across copies, ends when the last source leaves, and never turns an unspent Gem counter into essence.",
    ),
    SOLITARY_COMBHAND: (
        "While Solitary Combhand is in its controller's Interzone, Recovery hand size increases by the number of currently empty Interzone slots. Occupancy counts Float stacks once and capacity includes active extensions rather than assuming three slots. A full Interzone or a Combhand outside the Interzone grants no extra draw.",
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
        GroupedPassivesFamily,
    )
    result = unittest.TextTestRunner(
        verbosity=1, resultclass=EvidenceResult,
    ).run(suite)
    executions = {
        test["testId"].rsplit(".", 1)[-1]: test
        for test in result.executions
    }
    clauses = []
    for card_id, methods in CARD_METHODS.items():
        card = audit.batches.CATALOG.cards[card_id]
        paragraphs = printed_paragraphs(card["effect"])
        behaviors = EXPECTED_BEHAVIORS[card_id]
        if len(paragraphs) != len(behaviors):
            raise AssertionError(
                f"{card_id} exposes {len(paragraphs)} paragraphs, "
                f"expected {len(behaviors)}"
            )
        tests = [executions["test_" + method] for method in methods]
        for index, (printed, behavior) in enumerate(zip(paragraphs, behaviors)):
            clauses.append({
                "cardId": card_id,
                "name": card["name"],
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
            "cardsWithSelectedClauseProof": len(CARD_METHODS),
            "fullCatalogSemanticCertification": False,
        },
        "clauses": clauses,
        "tests": result.executions,
        "limits": [
            "This proof certifies the seven printed paragraphs of Balance of the Spirit, Discombobulator, Asciugoth, Tricephalous Oil-Dog, and Solitary Combhand across the selected strict branches and interactions.",
            "It does not re-certify the complete generic contracts of Cleanse, Float, Interzone extension, point-change prevention, token copying, or the full payment engine independently of these five cards.",
        ],
    }
    out = ROOT / "reports/systematic-audit/grouped-passives-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
