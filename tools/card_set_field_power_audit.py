"""Publish strict proof for Trim the Excess and Equalize."""

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_set_field_power_family import (  # noqa: E402
    SET_FIELD_POWER_NAMES,
    SetFieldPowerFamily,
)


METHODS = (
    "both_compile_the_exact_printed_contract",
    "trim_really_restores_each_current_field_manifestation_to_its_base",
    "equalize_uses_the_lowest_live_base_on_the_field_not_stalemate",
    "both_prevent_new_modifiers_on_each_affected_occurrence",
    "only_manifestations_present_at_resolution_are_locked",
    "modifier_lock_expires_on_the_next_turn",
    "both_resolve_and_pay_normally_with_no_field_manifestation",
)

EXPECTED_BEHAVIORS = {
    "Trim the Excess": (
        "Trim the Excess pays two Capricious Tributes, then every Manifestation currently on the field returns to its own live base power and rejects new modifiers until the end of the turn. This includes both players' Confrontation, Support and Interzone Manifestations, excludes Stalemate and Wills, does not lock later entries or re-entered occurrences, and expires on the next turn.",
    ),
    "Equalize": (
        "Equalize pays two Capricious Tributes, finds the lowest live base power among all Manifestations currently on the field, gives that power to each of those occurrences and rejects new modifiers until the end of the turn. Stalemate does not contribute to the minimum, later entries and re-entered occurrences are not locked, and the effect expires on the next turn.",
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
        SetFieldPowerFamily
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
    for name in SET_FIELD_POWER_NAMES:
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
            "This proof certifies both printed field-wide power assignments, real Capricious Tribute payment, field and Stalemate scope, modifier prevention, occurrence snapshot and turn lifetime.",
            "It does not re-certify every individual modifier-producing card, all characteristic-copy interactions, or other cards sharing the set_field_power primitive.",
        ],
    }
    out = ROOT / "reports/systematic-audit/set-field-power-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
