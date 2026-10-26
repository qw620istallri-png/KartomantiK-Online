"""Record auto-pass/phase invariants and nearby regression families."""
import argparse
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import ROOT, EvidenceResult
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))


class Details(EvidenceResult):
    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        self.current.setdefault("subtests", []).append({
            "testId": subtest.id(), "status": "pass" if err is None else "fail",
            **({"detail": self._exc_info_to_string(err, test)} if err else {}),
        })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", action="store_true")
    args = parser.parse_args()
    start = audit.digest()
    names = ["test_auto_phase_audit.AutoPhaseAudit"]
    if not args.before:
        names += ["test_auto_phase_integration.AutoPhaseIntegration", "test_auto_pass.AutoPassTests",
                  "test_invalid_stack_auto_resolution.InvalidStackAutoResolutionTests",
                  "test_latency_stack_sequences.LatencyStackSequences"]
    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    result = unittest.TextTestRunner(verbosity=1, resultclass=Details).run(suite)
    assert audit.digest() == start, "Sources changed during execution"
    proof = {"schemaVersion": 1, "sourceDigest": start, "published": False,
        "finishedAt": datetime.now(timezone.utc).isoformat(),
        "summary": {"executed": result.testsRun, "passed": sum(t["status"] == "pass" for t in result.executions),
            "failed": sum(t["status"] not in {"pass", "skip"} for t in result.executions), "skipped": len(result.skipped)},
        "tests": result.executions,
        "limits": ["Fifteen-step scheduling with synthetic score effects does not certify every card trigger.",
            "Availability differential checks prepared declaration fixtures, not all possible states or print clauses.",
            "Pacing tests use deterministic gates and spy the configured pause; not a real latency/load benchmark.",
            "No physical-device or full-catalog browser certification."]}
    out = ROOT / "reports/systematic-audit/auto-phase-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / ("before.json" if args.before else "sequences.json")).write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
