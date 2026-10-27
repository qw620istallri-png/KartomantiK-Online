"""Explicit printed oracle and actual execution proof for Gorlok's draw clause."""
import argparse
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import ROOT
from card_atavic_end_audit import Details
import card_behavior_audit as audit
sys.path.insert(0, str(ROOT / "tests"))
from test_gorlok_draw_clauses import GorlokDrawClauses


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", action="store_true")
    args = parser.parse_args()
    start = audit.digest()
    cases = [GorlokDrawClauses]
    if not args.before:
        from test_gorlok_draw_integration import GorlokDrawIntegration
        cases.append(GorlokDrawIntegration)
    result = unittest.TextTestRunner(verbosity=1, resultclass=Details).run(
        unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in cases))
    card = next(c for c in audit.batches.CATALOG.cards.values() if c['name'] == GorlokDrawClauses.NAME)
    paragraph = card['effect'].strip()
    assert audit.digest() == start
    proof = {"schemaVersion": 1, "sourceDigest": start, "finishedAt": datetime.now(timezone.utc).isoformat(), "published": False,
        "summary": {"executed": result.testsRun, "passed": sum(t["status"] == "pass" for t in result.executions),
            "failed": sum(t["status"] != "pass" for t in result.executions), "skipped": len(result.skipped),
            "selectedParagraphs": 1, "cardsWithSelectedClauseProof": 1},
        "clauses": [{"cardId": card['id'], "name": card['name'], "paragraphIndex": 0,
            "printedParagraph": paragraph, "paragraphSha256": hashlib.sha256(paragraph.encode()).hexdigest(),
            "expectedBehavior": "Each opponent draw outside Recovery creates its own immutable group of drawn hand instances. Resolve surviving instances only, in Stack order, without consuming another trigger's group. Show those cards, exile exactly one and apply power loss equal to the number shown to the original source still present. Effect survives source departure; exclude immune hands, invalid and repeated answers and private draw identities before resolution.",
            "testIds": [t['testId'] for t in result.executions],
            "status": "selected-branches-pass" if result.wasSuccessful() else "fail", "allBranchesCertified": False}],
        "tests": result.executions,
        "limits": ["Draw stimuli are explicit shared-engine requests, not every possible printed draw source.",
            "Network tests isolate automatic phase driving; no certification of full scheduling or VFX.",
            "Unexpected hand changes during an already-open choice are rejection checks, not legal interruption windows inside an effect.",
            "Physical devices, Safari Mac, remote illustrations and all card combinations remain outside this lot."]}
    out = ROOT / 'reports/systematic-audit/gorlok-draw-followup'
    out.mkdir(parents=True, exist_ok=True)
    path = out / ('before.json' if args.before else 'clauses.json')
    if args.before and path.exists():
        raise RuntimeError('Refusing to overwrite historical before evidence')
    path.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(proof['summary']))
    return int(not result.wasSuccessful())


if __name__ == '__main__':
    raise SystemExit(main())
