"""Publish the shared zone-entry trigger clauses for sixteen cards."""
import hashlib
import json
import re
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_zone_entry_family_clauses import (
    ZONE_ENTRY_NAMES,
    ZoneEntryFamilyClauses,
)


METHODS = (
    "all_sixteen_compile_one_exact_zone_entry_trigger",
    "trigger_requires_the_exact_zone_and_a_live_face_up_source",
    "each_zone_entry_effect_begins_real_resolution",
)


def main():
    start = audit.digest()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        ZoneEntryFamilyClauses
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
    for name in ZONE_ENTRY_NAMES:
        card = catalog[name]
        matches = re.findall(
            r"When [^.\r\n]*?(?:Confrontation Zone|Interzone)",
            card["effect"],
            flags=re.IGNORECASE,
        )
        if not matches:
            raise RuntimeError(f"Missing printed zone-entry phrase: {name}")
        printed = matches[-1].strip()
        clauses.append({
            "cardId": card["id"],
            "name": name,
            "paragraphIndex": None,
            "printedParagraph": printed,
            "paragraphSha256": hashlib.sha256(
                printed.encode()
            ).hexdigest(),
            "expectedBehavior": (
                "This trigger is queued exactly for the encoded entry zone, "
                "only from a live face-up source with active effects, and its "
                "real resolution path begins without an invalid target set."
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
            "This proof certifies the shared printed zone-entry trigger condition, not every branch of each resulting effect.",
            "Card-specific outcomes remain protected by their existing dedicated regressions.",
        ],
    }
    out = ROOT / "reports/systematic-audit/zone-entry-family-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
