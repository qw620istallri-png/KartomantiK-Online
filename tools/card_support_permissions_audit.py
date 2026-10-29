"""Collect exact clause links from a current full run, or execute the focused batch.

--units avoids rerunning the same network journeys solely to build a report.
"""
import argparse
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / p) for p in ('server', 'tests', 'tools')]
import card_behavior_audit as audit
from card_atavic_end_audit import Details
import test_support_permissions as family
import test_support_permissions_integration as network
import test_concealed_play_permissions as jig
import test_support_permissions_oracle as oracle

MODULES = ('test_support_permissions', 'test_support_permissions_integration',
           'test_concealed_play_permissions', 'test_support_permissions_oracle')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--units', help='Current full unit evidence; reuse actual executions without repeating them')
    args = parser.parse_args()
    digest = audit.digest()
    if args.units:
        units = json.loads((ROOT / args.units).read_text(encoding='utf-8'))
        assert units['sourceDigest'] == digest and not units['summary']['failed']
        tests = [t for t in units['tests'] if t['testId'].split('.')[0] in MODULES]
        for module in MODULES: assert any(t['testId'].startswith(module + '.') for t in tests)
    else:
        suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in
            (family.SupportPermissions, jig.ConcealedPlayPermissions,
             oracle.SupportPermissionOracle, network.SupportPermissionsIntegration))
        result = unittest.TextTestRunner(verbosity=1, resultclass=Details).run(suite)
        tests = result.executions
    by_id = {t['testId']: t for t in tests}
    expected = {test.id() for cls in (family.SupportPermissions, jig.ConcealedPlayPermissions,
                oracle.SupportPermissionOracle, network.SupportPermissionsIntegration)
                for test in unittest.defaultTestLoader.loadTestsFromTestCase(cls)}
    assert set(by_id) == expected
    clauses = []
    for row in family.CONTRACTS:
        ids = ['test_support_permissions.SupportPermissions.' + family.method_name(row, s)
               for s in family.scenarios(row)]
        ids += [i for i in by_id if i.startswith('test_support_permissions_integration.')
                and i.rsplit('.', 1)[-1].startswith('test_' + row['key'] + '__')]
        for paragraph in row['printedClauses']:
            clauses.append({'cardId': row['cardId'], 'name': row['name'],
                'printedParagraph': paragraph, 'printedTextSha256': row['printedTextSha256'],
                'independentOracle': {k: row[k] for k in ('fromHand', 'fromInterzone', 'fromStalemate', 'canBeFirst')},
                'testIds': ids, 'allBranchesCertified': False})
    pinned = json.loads((ROOT / 'audit/jigon-concealed-play.json').read_text(encoding='utf-8'))
    card = next(c for c in audit.batches.main.CARD_DATA if c['id'] == pinned['cardId'])
    assert card['effect'] == pinned['printedText']
    assert hashlib.sha256(card['effect'].encode()).hexdigest() == pinned['printedTextSha256']
    jigon_ids = [i for i in by_id if i.startswith('test_concealed_play_permissions.')
        or i.startswith('test_support_permissions_integration.') and '.test_jigon__' in i]
    for paragraph in pinned['clauses']:
        clauses.append({'cardId': pinned['cardId'], 'name': pinned['name'], 'printedParagraph': paragraph,
            'printedTextSha256': pinned['printedTextSha256'], 'independentOracle': pinned['oracle'],
            'testIds': jigon_ids, 'allBranchesCertified': False})
    for c in clauses:
        c['status'] = 'selected-branches-pass' if all(by_id[i]['status'] == 'pass' for i in c['testIds']) else 'fail'
    assert audit.digest() == digest
    proof = {'schemaVersion': 1, 'sourceDigest': digest, 'finishedAt': datetime.now(timezone.utc).isoformat(),
        'published': False, 'executionSource': args.units or 'focused-execution',
        'summary': {'executed': len(tests), 'passed': sum(t['status'] == 'pass' for t in tests),
            'failed': sum(t['status'] != 'pass' for t in tests),
            'selectedClauses': len(clauses), 'cardsWithSelectedClauseProof': len({c['cardId'] for c in clauses}),
            'supportCards': len(family.CONTRACTS), 'networkJourneys': len(list(unittest.defaultTestLoader.loadTestsFromTestCase(network.SupportPermissionsIntegration))),
            'oracleSensitivityTests': 2},
        'clauses': clauses, 'tests': tests,
        'limits': ['Support keyword and First Manifestation restrictions only for the 39 Support cards; other paragraphs are not certified.',
            'Input fixtures supply required ETB targets and played controller choices; those separate effects remain on the Stack.',
            'Jigon search, shuffle, loss trigger, paid/free cast and exact +3 are exercised with Strengthen, not every possible Will.',
            'Two sensitivity tests verify handwritten expectations detect wrong encoded permissions.',
            'Eight real mixed-version socket journeys; automatic phase driving disabled to isolate permissions and Stack resolution.',
            'No new browser, remote-artwork or physical-device certification.']}
    out = ROOT / 'reports/systematic-audit/support-permissions-followup'
    out.mkdir(parents=True, exist_ok=True)
    (out/'clauses.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(proof['summary']))
    return int(proof['summary']['failed'] != 0)


if __name__ == '__main__': raise SystemExit(main())
