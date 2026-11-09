"""Publish strict selected-clause proof for Obscure."""

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_obscure_lock_family import (  # noqa: E402
    OBSCURE,
    ObscureLockFamily,
)


METHODS = (
    "compiles_the_exact_three_paragraph_contract",
    "invalid_targets_are_rejected_without_payment",
    "manifestation_loses_effects_is_fully_immune_and_contributes_zero",
    "persistent_will_loses_effects_and_is_immune_without_manifestation_power_rule",
    "immunity_blocks_both_controllers_after_obscure_resolves",
    "late_invalid_target_fizzles_but_obscure_still_exiles_itself",
    "cleanse_removes_the_modifier_without_undoing_obscures_exile",
    "turn_expiry_restores_effects_immunity_and_confrontation_power",
    "neutralized_obscure_goes_to_limbo_and_creates_no_lock",
)

EXPECTED_BEHAVIORS = (
    "On resolution, one legal Manifestation or Persistent Will on the field loses its effects and becomes Immune to cards and effects from every controller until the end of the turn. A missing, unsupported-type, Stalemate, or already Immune target is illegal; a target that becomes illegal before resolution receives no lock. Cleanse removes the modifier without undoing already completed source movement.",
    "If the resolved target is a Manifestation, its current power contributes exactly zero to confrontation resolution until turn end, without changing its printed or effective power. This extra rule does not apply to a Persistent Will. Cleanse or normal turn expiry restores the Manifestation's contribution.",
    "A resolving Obscure moves to its immutable owner's Exile even if its only target became illegal in response. If Obscure itself is neutralized instead of resolving, it enters its owner's Limbo, creates no lock, and its already-paid cost remains paid.",
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
        ObscureLockFamily,
    )
    result = unittest.TextTestRunner(
        verbosity=1, resultclass=EvidenceResult,
    ).run(suite)
    executions = {
        test["testId"].rsplit(".", 1)[-1]: test
        for test in result.executions
    }
    tests = [executions["test_" + method] for method in METHODS]
    card = audit.batches.CATALOG.cards[OBSCURE]
    paragraphs = printed_paragraphs(card["effect"])
    if len(paragraphs) != 3:
        raise AssertionError("Obscure must expose exactly three paragraphs")
    clauses = []
    for index, (printed, behavior) in enumerate(zip(
        paragraphs, EXPECTED_BEHAVIORS,
    )):
        clauses.append({
            "cardId": OBSCURE,
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
            "This proof certifies Obscure's three paragraphs: target types and field scope, loss of effects, full Immunity, Manifestation-only confrontation-power suppression, turn lifetime, Cleanse removal, source Exile, late target invalidation, and neutralization.",
            "It does not re-certify every card whose printed effect may be blanked, every replacement that could alter source movement, simultaneous modifier ordering beyond Immunity and loss of effects, or Cleanse's complete independent contract.",
        ],
    }
    out = ROOT / "reports/systematic-audit/obscure-lock-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
