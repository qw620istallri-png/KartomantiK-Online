"""Publish strict selected-clause proof for Inflate the Ego."""

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_inflate_the_ego_family import (  # noqa: E402
    INFLATE,
    InflateTheEgoFamily,
)


METHODS = (
    "compiles_the_exact_two_paragraph_contract",
    "requires_the_controllers_current_first_manifestation_atomically",
    "base_five_discount_sets_current_four_to_ten_without_mutating_printed_cost",
    "discount_uses_modified_base_power_and_never_makes_cost_negative",
    "later_malus_lowers_power_but_later_bonus_is_capped_at_ten",
    "new_first_between_payment_and_resolution_invalidates_the_old_target",
    "cleanse_removes_the_cap_and_resets_other_power_changes",
    "turn_end_expiration_restores_the_underlying_power",
)

EXPECTED_BEHAVIORS = (
    "Inflate the Ego costs five choleric Tribute less half the modified base power of its controller's current First Manifestation, rounded down, with the final cost floored at zero. The printed cost is never mutated. Without a legal own First Manifestation, declaration is rejected atomically.",
    "On resolution, the selected own First Manifestation's current power becomes exactly 10 and is capped at 10 until turn end. Later maluses can lower it and later bonuses cannot raise it above 10. If the selected card is no longer the controller's First Manifestation at resolution, no modifier is created. Cleanse removes the cap together with the target's other removable power changes; normal turn expiry removes only the temporary cap and restores the underlying power.",
)


def printed_paragraphs(effect):
    return [
        paragraph.strip()
        for paragraph in str(effect or "").replace("\r\n", "\n").split("\n")
        if paragraph.strip()
    ]


def main():
    start = audit.digest()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        InflateTheEgoFamily,
    )
    result = unittest.TextTestRunner(
        verbosity=1, resultclass=EvidenceResult,
    ).run(suite)
    executions = {
        test["testId"].rsplit(".", 1)[-1]: test
        for test in result.executions
    }
    tests = [executions["test_" + method] for method in METHODS]
    card = audit.batches.CATALOG.cards[INFLATE]
    paragraphs = printed_paragraphs(card["effect"])
    if len(paragraphs) != 2:
        raise AssertionError("Inflate the Ego must expose exactly two paragraphs")
    clauses = []
    for index, (printed, behavior) in enumerate(zip(
        paragraphs, EXPECTED_BEHAVIORS,
    )):
        clauses.append({
            "cardId": INFLATE,
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
            "cardsWithSelectedClauseProof": 1,
            "fullCatalogSemanticCertification": False,
        },
        "clauses": clauses,
        "tests": result.executions,
        "limits": [
            "This proof certifies Inflate the Ego's two paragraphs: modified-base discount, rounding and zero floor, unchanged printed cost, own-First targeting, resolution-time revalidation, set-to-10 behavior, maximum 10, later modifiers, Cleanse, and turn expiry.",
            "It does not re-certify every base-power modifier, every generic target replacement, Cleanse's complete independent contract, or all interactions with effects that prevent modifiers.",
        ],
    }
    out = ROOT / "reports/systematic-audit/power-set-maximum-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
