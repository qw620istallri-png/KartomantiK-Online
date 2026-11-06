"""Publish strict proof for the three remaining will-played trigger cards."""

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_will_played_family import (  # noqa: E402
    WILL_PLAYED_NAMES,
    WillPlayedFamily,
)


METHODS = (
    "all_three_compile_the_exact_printed_contracts",
    "real_will_carriers_require_exact_controller_zone_phase_and_activity",
    "blue_entity_buffs_only_other_friendly_confrontation_manifestations_until_end",
    "greed_trap_choice_is_atomic_and_all_six_rolls_are_exact",
    "greed_trap_captures_only_opposing_manifestations_at_exactly_zero",
    "ippokridal_creates_the_printed_token_and_adamant_blocks_only_moves",
)

EXPECTED_BEHAVIORS = {
    "Blue Entity": (
        "Only an active Blue Entity in its controller's Confrontation Zone reacts to that controller actually playing a Will; every other friendly Confrontation manifestation gets +1 power until end of turn while Blue Entity, other zones and opposing cards remain unchanged.",
    ),
    "Greed Trap": (
        "An active Greed Trap replaces destruction only for an opposing field manifestation at exactly zero power, moving that card into Greed Trap's current controller's Empathic Vessel; negative-power, friendly or inactive-source cases are destroyed normally.",
        "When an opponent actually plays a Will, an active Greed Trap offers its controller the optional effect and requires exactly one manifestation controlled by that opponent in the Confrontation Zone.",
        "On a Greed Trap roll of 1 or 2 the target receives no power modifier.",
        "On a Greed Trap roll of 3 or 4 the target permanently gets -1 power while it remains on the field.",
        "On a Greed Trap roll of 5 or 6 the target permanently gets -2 power while it remains on the field.",
    ),
    "Ippokridal, of Icy Fervor": (
        "Adamant prevents a non-destroy movement caused by an opponent while leaving destruction legal.",
        "Only an active Ippokridal reacts to its controller actually playing a Will during Reaction, creating under that controller a Support Token with 1 vitreous power.",
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
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(WillPlayedFamily)
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
    for name in WILL_PLAYED_NAMES:
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
            "This proof certifies the eight printed paragraphs, their actual Will-played carriers, source activity gates, target restrictions and first authoritative transitions.",
            "It does not re-certify generic Will payment, Stack ordering, all movement replacements or every global Power interaction owned by other families.",
        ],
    }
    out = ROOT / "reports/systematic-audit/will-played-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
