"""Publish strict enters-Support proof for Gomeran and Unruly Flail."""

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_enters_support_family import (  # noqa: E402
    ENTERS_SUPPORT_NAMES,
    EntersSupportFamily,
)


METHODS = (
    "both_compile_the_exact_selected_support_contract",
    "gomeran_really_copies_an_allied_non_token_support_entry",
    "gomeran_requires_its_controller_and_a_non_token_entry",
    "gomeran_requires_an_active_source_in_the_confrontation_zone",
    "gomerans_created_token_does_not_copy_itself_again",
    "flail_support_is_available_for_exactly_an_eligible_opposing_will",
    "flail_really_enters_support_without_tribute_and_neutralizes_the_chosen_will",
    "flail_triggers_only_for_its_own_entry_from_hand",
)

SELECTED_PARAGRAPH = {
    "Gomeran, Echo Mistress": 0,
    "Unruly Flail": 0,
}

EXPECTED_BEHAVIORS = {
    "Gomeran, Echo Mistress": (
        "While an active Gomeran is in its controller's Confrontation Zone, each non-token Manifestation that enters Support under that controller creates exactly one token copy of itself in Support. Opposing and token entries do not trigger it, the created copy preserves the entering card and controller, and the copy cannot recursively trigger Gomeran.",
    ),
    "Unruly Flail": (
        "Unruly Flail may be played from hand in Support only while an opponent controls a Will anywhere in the Stack that currently targets a Manifestation in the Confrontation Zone. As a Manifestation it enters without Tribute, triggers only from its own hand entry, and neutralizes exactly one chosen eligible opposing Will.",
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
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(EntersSupportFamily)
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
    for name in ENTERS_SUPPORT_NAMES:
        card = catalog[name]
        paragraphs = printed_paragraphs(card["effect"])
        index = SELECTED_PARAGRAPH[name]
        expected = EXPECTED_BEHAVIORS[name]
        if index >= len(paragraphs) or len(expected) != 1:
            raise AssertionError(f"{name}: selected paragraph is unavailable")
        printed = paragraphs[index]
        covered_card_ids.add(card["id"])
        clauses.append({
            "cardId": card["id"],
            "name": name,
            "paragraphIndex": index,
            "printedParagraph": printed,
            "paragraphSha256": hashlib.sha256(printed.encode()).hexdigest(),
            "expectedBehavior": expected[0],
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
            "This proof certifies Gomeran's first printed paragraph and Unruly Flail's printed paragraph, including real Support entry, Flail's no-Tribute Manifestation play, source and event scope, token non-recursion, conditional availability, target eligibility and neutralization.",
            "It does not certify Gomeran's separate bottom-deck shuffle paragraph, every other enters-Support watcher, or every global replacement that can prohibit Support entry.",
        ],
    }
    out = ROOT / "reports/systematic-audit/enters-support-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
