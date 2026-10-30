"""Independent continuous-power clauses, reusable from a passing full execution."""
import argparse
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/p) for p in ('server','tests','tools')]
import card_behavior_audit as audit
from card_atavic_end_audit import Details
import test_continuous_power_family as family
import test_continuous_power_integration as network
import test_continuous_power_oracle as oracle

CLASSES = (family.ContinuousPowerFamily, network.ContinuousPowerIntegration, oracle.ContinuousPowerOracle)
MODULES = ('test_continuous_power_family','test_continuous_power_integration','test_continuous_power_oracle')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--units', help='Reuse actual test IDs from current full unit evidence')
    args = p.parse_args()
    digest = audit.digest()
    expected = {t.id() for cls in CLASSES for t in unittest.defaultTestLoader.loadTestsFromTestCase(cls)}
    if args.units:
        full = json.loads((ROOT/args.units).read_text(encoding='utf-8'))
        assert full['sourceDigest'] == digest and not full['summary']['failed']
        tests = [t for t in full['tests'] if t['testId'].split('.')[0] in MODULES]
    else:
        result = unittest.TextTestRunner(verbosity=1,resultclass=Details).run(unittest.TestSuite(
            unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in CLASSES))
        tests = result.executions
    by_id = {t['testId']:t for t in tests}
    assert set(by_id) == expected
    clauses = []
    for row in family.CONTRACTS:
        ids = ['test_continuous_power_family.ContinuousPowerFamily.'+family.method_name(row,s) for s in family.SCENARIOS]
        ids += [i for i in by_id if i.startswith('test_continuous_power_integration.') and
                i.rsplit('.',1)[-1].startswith('test_'+row['key']+'__')]
        for clause in row['selectedClauses']:
            clauses.append({'cardId':row['cardId'],'name':row['name'],'printedParagraph':clause,
                'printedTextSha256':row['printedTextSha256'],
                'independentOracle':{k:row[k] for k in ('sourceBase','targetBase','expectedPower','inactivePower','changedControlPower','duplicateSourcePower','zonePowers')},
                'testIds':ids,'status':'selected-branches-pass' if all(by_id[i]['status']=='pass' for i in ids) else 'fail',
                'allBranchesCertified':False})
    assert audit.digest() == digest
    proof={'schemaVersion':1,'sourceDigest':digest,'finishedAt':datetime.now(timezone.utc).isoformat(),
        'published':False,'executionSource':args.units or 'focused-execution',
        'summary':{'executed':len(tests),'passed':sum(t['status']=='pass' for t in tests),'failed':sum(t['status']!='pass' for t in tests),
            'selectedClauses':len(clauses),'cardsWithSelectedClauseProof':len(family.CONTRACTS),
            'unitScenarios':228,'networkJourneys':11,'oracleSensitivityTests':2},
        'clauses':clauses,'tests':tests,'limits':[
            'Selected continuous power/Float clauses only; other paragraphs and every interaction are not certified.',
            'Initial zone counts, control changes and comparison snapshots are controlled fixtures, not whole matches.',
            'Paid Defer journeys exercise actual declarations, payments, Stack resolution, owner destinations and both clients public power.',
            'Automatic phase driving disabled in the eleven socket journeys; no new physical-device or remote-artwork certification.',
            'Sensitivity tests mutate encoded rules only in isolated fixtures and verify literal expectations detect the error.']}
    out=ROOT/'reports/systematic-audit/continuous-power-followup';out.mkdir(parents=True,exist_ok=True)
    (out/'clauses.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(proof['summary']))
    return int(proof['summary']['failed'] != 0)


if __name__ == '__main__': raise SystemExit(main())
