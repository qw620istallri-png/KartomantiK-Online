"""Independent Support clauses and executable branch evidence."""
import argparse
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / d) for d in ('server', 'tests', 'tools')]
import card_behavior_audit as audit
from card_atavic_end_audit import Details
import test_support_family as family


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--before', action='store_true')
    parser.add_argument('--units-only', action='store_true')
    parser.add_argument('--output')
    args = parser.parse_args()
    digest = audit.digest()
    classes = [family.SupportFamily]
    if not args.units_only:
        import test_support_family_integration as network
        classes.append(network.SupportFamilyIntegration)
    result = unittest.TextTestRunner(verbosity=1, resultclass=Details).run(unittest.TestSuite(
        unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in classes))
    by_id = {t['testId']: t for t in result.executions}
    clauses = []
    for row in family.CONTRACTS:
        ids = ['test_support_family.SupportFamily.' + family.method_name(row, c)
            for c in family.scenarios(row)]
        ids += [i for i in by_id if i.startswith('test_support_family_integration.')
            and i.rsplit('.', 1)[-1].startswith('test_' + row['key'] + '__')]
        for index, paragraph in enumerate(p.strip() for p in row['printedText'].splitlines() if p.strip()):
            if index not in row.get('selectedParagraphs', range(100)): continue
            clauses.append({'cardId': row['cardId'], 'name': row['name'], 'abilityId': row['abilityId'],
                'paragraphIndex': index, 'printedParagraph': paragraph,
                'printedClauseSha256': hashlib.sha256(paragraph.encode()).hexdigest(),
                'independentOracle': {k: row[k] for k in ('essenceCost',) if k in row},
                'testIds': ids, 'status': 'selected-branches-pass' if all(by_id[t]['status'] == 'pass' for t in ids) else 'fail',
                'allBranchesCertified': False})
    assert {t for c in clauses for t in c['testIds']} == set(by_id)
    assert audit.digest() == digest
    proof = {'schemaVersion': 1, 'sourceDigest': digest, 'finishedAt': datetime.now(timezone.utc).isoformat(),
        'published': False, 'summary': {'executed': result.testsRun,
            'passed': sum(t['status'] == 'pass' for t in result.executions),
            'failed': sum(t['status'] != 'pass' for t in result.executions), 'skipped': len(result.skipped),
            'selectedClauses': len(clauses), 'cardsWithSelectedClauseProof': len(family.CONTRACTS)},
        'clauses': clauses, 'tests': result.executions,
        'limits': ['Selected clauses and explicit branches, not certification of every card interaction.',
            'Targets, entry histories, locks and comparison results are controlled fixtures; production declarations, entry events and cleanup are exercised.',
            'Printed costs, token counts, ownership, duration and victory destinations are literal oracles.',
            'No new browser, physical-device or automatic phase-driving certification.']}
    out = ROOT / 'reports/systematic-audit/support-family-followup'
    out.mkdir(parents=True, exist_ok=True)
    (out / (args.output or ('before.json' if args.before else 'clauses.json'))).write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(proof['summary']))
    return int(not result.wasSuccessful())


if __name__ == '__main__': raise SystemExit(main())
