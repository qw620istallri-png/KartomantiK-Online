"""Publish strict proof for Tong and Cozy Bunk Interzone capacity."""

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_extend_interzone_family import (  # noqa: E402
    EXTEND_INTERZONE_NAMES,
    ExtendInterzoneFamily,
)


METHODS = (
    "both_compile_the_exact_printed_contract",
    "bonuses_are_additive_and_only_help_their_controller",
    "tong_works_anywhere_on_the_field_but_not_in_stalemate",
    "inactive_or_blanked_sources_stop_extending_immediately",
    "bonus_follows_current_control_not_immutable_ownership",
    "cozy_bunk_real_play_opens_and_departure_closes_one_space",
    "each_bonus_really_admits_exactly_its_printed_extra_spaces",
)

EXPECTED_BEHAVIORS = {
    "Tong, the Expansive": (
        "While an active Tong is on the field, its current controller's Interzone capacity rises from three to six and really admits exactly three extra occupied spaces. The bonus applies in Confrontation, Support or Interzone, follows control, stacks with other extensions, and stops if Tong leaves the field, enters Stalemate, is face down or loses its effects.",
    ),
    "Cozy Bunk": (
        "After Cozy Bunk is really played and resolves as an active Persistent Will, its current controller's Interzone capacity rises from three to four and really admits exactly one extra occupied space. The bonus follows control, stacks with other extensions, and stops when the source leaves or loses its effects without evicting cards already present.",
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
        ExtendInterzoneFamily
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
    for name in EXTEND_INTERZONE_NAMES:
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
            "This proof certifies both printed capacity increases, active-source lifetime, current control, addition and real entry limits at four and six occupied spaces.",
            "It does not re-certify every card that enters or counts the Interzone, generic Persistent Will payment rules, or all effects that can blank or change control of a source.",
        ],
    }
    out = ROOT / "reports/systematic-audit/extend-interzone-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
