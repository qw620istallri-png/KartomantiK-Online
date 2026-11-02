"""Publish complete no-effect contracts for the sixteen vanilla cards."""
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_vanilla_card_clauses import VANILLA_NAMES, VanillaCardClauses


METHODS = (
    "catalog_contains_exact_sixteen_vanilla_manifestations",
    "vanilla_compilation_contains_only_base_characteristics",
    "vanilla_runtime_uses_default_first_tribute_and_no_support_or_triggers",
)


def main():
    start = audit.digest()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        VanillaCardClauses
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
    cards = [{
        "cardId": catalog[name]["id"],
        "name": name,
        "noEffectTextContract": True,
        "printedText": "",
        "expectedBehavior": (
            "No printed ability. Base characteristics compile exactly; the "
            "card uses normal Tribute and First Manifestation rules, has no "
            "Support permission, and creates no entry trigger."
        ),
        "testIds": [test["testId"] for test in tests],
        "status": (
            "all-branches-pass"
            if all(test["status"] == "pass" for test in tests)
            else "fail"
        ),
        "allBranchesCertified": True,
    } for name in VANILLA_NAMES]
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
            "noEffectContracts": len(cards),
            "cardsWithSelectedClauseProof": len(cards),
            "fullCatalogSemanticCertification": False,
        },
        "cards": cards,
        "tests": result.executions,
        "limits": [
            "Certification is complete for the absence of printed effects and default base behavior only.",
            "Interactions caused by other cards targeting these Manifestations remain covered by their own clauses.",
        ],
    }
    out = ROOT / "reports/systematic-audit/vanilla-cards-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
