"""Execute the explicit creator ruling without rewriting earlier audit evidence."""
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone
from run_card_audit import ROOT, EvidenceResult
import card_behavior_audit as audit
sys.path.insert(0, str(ROOT / "tests"))
from test_atavic_limbo_ruling import AtavicLimboRuling
from test_atavic_limbo_integration import AtavicLimboIntegration


if __name__ == "__main__":
    digest = audit.digest()
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c)
                               for c in (AtavicLimboRuling, AtavicLimboIntegration))
    result = unittest.TextTestRunner(verbosity=1, resultclass=EvidenceResult).run(suite)
    card = audit.batches.CATALOG.cards["265f4wdooq43pjn_en"]
    paragraph = [p.strip() for p in card["effect"].splitlines() if p.strip()][3]
    decisions = json.loads((ROOT / "audit/rule-decisions.json").read_text(encoding="utf-8"))
    ruling = next(d for d in decisions["decisions"] if d["id"] == "atavic-introspection-single-limbo")
    assert audit.digest() == digest
    proof = {"schemaVersion": 1, "sourceDigest": digest, "finishedAt": datetime.now(timezone.utc).isoformat(), "published": False,
        "summary": {"executed": result.testsRun, "passed": sum(t["status"] == "pass" for t in result.executions),
                    "failed": len(result.failures) + len(result.errors), "skipped": len(result.skipped), "networkScenarios": 1},
        "cardId": card["id"], "paragraphIndex": 3, "printedParagraph": paragraph,
        "paragraphSha256": hashlib.sha256(paragraph.encode()).hexdigest(), "ruling": ruling,
        "expectedBehavior": "Select exactly two cards from either single Limbo, never a mixture. The controller chooses the top/bottom order, but both cards return to their original owner's Deck. Other player's Deck contents remain private.",
        "testIds": [t["testId"] for t in result.executions], "tests": result.executions,
        "allBranchesCertified": False,
        "limits": ["Phase trigger is prepared explicitly in the protocol case; auto phase driving is isolated.",
                   "Identical copies and partial invalidation placement remain outside this batch.",
                   "No new full-catalog browser, remote-art or real physical-device/Safari Mac certification."]}
    out = ROOT / "reports/systematic-audit/atavic-limbo-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "ruling.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof["summary"]))
    raise SystemExit(not result.wasSuccessful())
