"""Publish the strict wins-confrontation family proof."""
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_wins_confrontation_family import (  # noqa: E402
    WINS_CONFRONTATION_NAMES,
    WinsConfrontationFamily,
)


METHODS = (
    "all_six_compile_the_exact_wins_confrontation_contract",
    "each_actual_winning_participant_queues_exactly_once",
    "loser_nonparticipant_hidden_and_disabled_sources_do_not_trigger",
    "each_card_specific_first_transition_is_authoritative",
)


def printed_win_paragraph(effect):
    paragraphs = [
        paragraph.strip()
        for paragraph in str(effect or "").replace("\r\n", "\n").split("\n")
        if paragraph.strip()
    ]
    return next(
        paragraph for paragraph in paragraphs
        if "wins the confrontation" in paragraph.lower()
        or "wins a confrontation" in paragraph.lower()
    )


def main():
    start = audit.digest()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        WinsConfrontationFamily
    )
    result = unittest.TextTestRunner(
        verbosity=1, resultclass=EvidenceResult
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
    for name in WINS_CONFRONTATION_NAMES:
        card = catalog[name]
        printed = printed_win_paragraph(card["effect"])
        clauses.append({
            "cardId": card["id"],
            "name": name,
            "paragraphIndex": None,
            "printedParagraph": printed,
            "paragraphSha256": hashlib.sha256(
                printed.encode()
            ).hexdigest(),
            "expectedBehavior": (
                "A live face-up Manifestation that actually participated on "
                "the winning side queues its wins-confrontation trigger "
                "exactly once. A loser, non-participant, hidden or disabled "
                "source does not trigger. The valid action begins the printed "
                "retained-Essence, delayed return, choice, control, reveal or "
                "exchange result."
            ),
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
            "cardsWithSelectedClauseProof": len(clauses),
            "fullCatalogSemanticCertification": False,
        },
        "clauses": clauses,
        "tests": result.executions,
        "limits": [
            "This proof certifies win-event eligibility and the first card-specific transition, not every later choice or delayed branch.",
            "Jurat's final end-turn return, Dew's placement, Bullyboo's opponent-payment branches and Ycar's completed search remain covered by their dedicated behavior families.",
        ],
    }
    out = ROOT / "reports/systematic-audit/wins-confrontation-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
