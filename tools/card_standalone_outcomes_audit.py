"""Publish strict selected-clause proof for five standalone outcome cards."""

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_standalone_outcomes_family import (  # noqa: E402
    FREENYA,
    KISS,
    MUTATE,
    OBELISK,
    VETERAN,
    StandaloneOutcomesFamily,
)


CARD_METHODS = {
    MUTATE: (
        "compiles_all_five_exact_contracts",
        "mutate_all_six_faces_have_exact_permanent_outcomes",
        "mutate_missing_target_rolls_but_changes_nothing",
    ),
    KISS: (
        "compiles_all_five_exact_contracts",
        "kiss_payment_is_atomic_and_keeps_phase_and_source",
        "kiss_decline_ends_phase_exiles_source_and_uses_base_not_current_power",
        "kiss_stalemate_has_no_winner_power_followup_but_still_exiles",
    ),
    FREENYA: (
        "compiles_all_five_exact_contracts",
        "freenya_triggers_only_for_owners_will_played_from_hand",
        "freenya_optional_trigger_can_be_declined_without_grant",
        "freenya_grants_exactly_one_free_limbo_play_without_recursion",
        "freenya_persistent_will_exiles_for_hand_limbo_or_deck_but_not_vessel",
    ),
    VETERAN: (
        "compiles_all_five_exact_contracts",
        "veteran_permission_is_snapshotted_at_turn_start_and_used_once",
        "veteran_entering_limbo_after_turn_start_gets_no_permission",
        "veteran_winning_as_support_exiles_but_winning_normally_does_not",
    ),
    OBELISK: (
        "compiles_all_five_exact_contracts",
        "obelisk_can_be_declined_before_stack_without_revealing_or_moving",
        "obelisk_selects_gifts_only_on_resolution_and_hides_first_choice",
        "obelisk_exchange_preserves_owners_and_boosts_higher_givers_first",
        "obelisk_equal_gifts_exchange_without_any_boost",
        "obelisk_invalid_gift_is_atomic",
    ),
}

EXPECTED_BEHAVIORS = {
    MUTATE: (
        "Roll one D6 only after the selected battlefield Manifestation remains a valid target; a missing target changes no game state.",
        "On 1 or 2, destroy the target and move the physical card to its owner's Limbo.",
        "On 3, the target becomes Hollow for as long as that field object remains; normal turn expiry does not restore its printed Temperament.",
        "On 4 or 5, the target gets a lasting +2 power modifier; normal turn expiry does not remove it.",
        "On 6, the target gets a lasting +3 power modifier; normal turn expiry does not remove it.",
    ),
    KISS: (
        "This Immediate effect pauses atomically for an opponent to pay exactly three Hollow Tribute. Paying keeps the Confrontation in Reaction and leaves Kiss in Limbo; declining advances immediately to comparison.",
        "If declining makes Kiss's controller the loser, that controller selects one winner-controlled Confrontation Manifestation and it loses power equal to the sum of the controller's modified base powers, not current power. A stalemate creates no follow-up target or power loss.",
        "Declining the payment exiles Kiss from its controller's Limbo; paying never exiles it.",
    ),
    FREENYA: (
        "While active on the field, Freenya optionally triggers only from its owner's Will played from hand. Accepting grants exactly one tribute-free Will play from that owner's Limbo in the current phase; the Limbo play cannot recursively trigger Freenya and declining grants nothing.",
        "A Will played through Freenya is marked so later movement to a Limbo, hand, or deck is replaced by exile. Movement into an Empathic Vessel remains legal and is not replaced.",
    ),
    VETERAN: (
        "Presence in its owner's Limbo at the beginning of the turn snapshots a one-turn permission to play Wandering Veteran from that Limbo as Hollow Support during Confrontation Reaction. Entering Limbo later grants nothing and using the permission consumes it.",
        "When Wandering Veteran wins as Support it is exiled directly without a destination choice. Winning as an ordinary non-Support Manifestation does not invoke this destination.",
    ),
    OBELISK: (
        "At Reaction, Obelisk offers an optional normal Stack action. Declining changes nothing. After acceptance, both Manifestation gifts are selected atomically only during resolution; the first choice stays hidden, invalid choices are atomic, and the exchanged physical cards enter the recipient's Vessel with ownership preserved.",
        "Compare the printed base powers of the exchanged gifts. The unique higher giver's current First Manifestation gets +3 until turn end; equal gifts create no bonus, and normal turn expiry removes the bonus.",
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
        StandaloneOutcomesFamily,
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
            "This proof certifies the fourteen printed paragraphs of Mutate Uncontrollably, Kiss of the Myrmillo!, Freenya, Wandering Veteran, and Obelisk of Friendship across the selected strict branches and interactions.",
            "It does not independently re-certify the complete generic contracts of target replacement, confrontation comparison, Stack priority, ownership serialization, Support cleanup, or all zone-movement replacement effects.",
        ],
    }
    out = ROOT / "reports/systematic-audit/standalone-outcomes-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
