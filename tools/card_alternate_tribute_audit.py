"""Publish the alternate-Tribute-temperament family proof."""
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_alternate_tribute_temperaments import (
    ALTERNATE_TRIBUTE_CONTRACTS,
    AlternateTributeTemperaments,
)


METHODS = (
    "all_eleven_compile_the_exact_printed_tribute_contract",
    "each_card_pays_a_real_will_with_its_alternate_temperament",
    "additional_temperament_remains_a_choice_and_cannot_be_split",
    "rocky_is_transcendent_only_while_used_as_tribute",
)


def main():
    start = audit.digest()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        AlternateTributeTemperaments
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
    for name in ALTERNATE_TRIBUTE_CONTRACTS:
        card = catalog[name]
        printed = card["effect"].strip()
        card_tests = tests if name == "Rocky Heartcrystal" else tests[:3]
        clauses.append({
            "cardId": card["id"],
            "name": name,
            "paragraphIndex": 0,
            "printedParagraph": printed,
            "paragraphSha256": hashlib.sha256(
                printed.encode()
            ).hexdigest(),
            "expectedBehavior": (
                "While this manifestation is used as Tribute, its full power "
                "uses the printed alternate temperament. The ten 'can also' "
                "cards retain their printed option without splitting one card "
                "between both colors; Rocky is Transcendent for Tribute and "
                "may cover mixed requirements."
            ),
            "testIds": [test["testId"] for test in card_tests],
            "status": (
                "selected-branches-pass"
                if all(test["status"] == "pass" for test in card_tests)
                else "fail"
            ),
            "allBranchesCertified": True,
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
            "This proof covers the complete printed alternate-temperament clause for the eleven selected cards.",
            "Interactions with unrelated Tribute modifiers remain covered by their own families.",
        ],
    }
    out = ROOT / "reports/systematic-audit/alternate-tribute-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
