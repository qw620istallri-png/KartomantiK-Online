"""Collect printed protection/keyword clauses from real test executions."""
import argparse,json,sys,unittest
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('server','tests','tools')]
import card_behavior_audit as audit
from card_atavic_end_audit import Details
import test_protection_keyword_family as family
import test_protection_keyword_integration as network
import test_protection_keyword_oracle as oracle
import test_game_state as legacy

CLASSES=(family.ProtectionKeywordFamily,network.ProtectionKeywordIntegration,oracle.ProtectionKeywordOracle,
         legacy.AnnihilatingNectarNeedsATargetTests)


def main():
    p=argparse.ArgumentParser();p.add_argument('--units');args=p.parse_args();digest=audit.digest()
    expected={t.id() for cls in CLASSES for t in unittest.defaultTestLoader.loadTestsFromTestCase(cls)}
    if args.units:
        full=json.loads((ROOT/args.units).read_text(encoding='utf-8'))
        assert full['sourceDigest']==digest and not full['summary']['failed']
        tests=[t for t in full['tests'] if t['testId'] in expected]
    else:
        result=unittest.TextTestRunner(verbosity=1,resultclass=Details).run(unittest.TestSuite(
            unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in CLASSES));tests=result.executions
    by_id={t['testId']:t for t in tests};assert set(by_id)==expected
    clauses=[]
    for row in family.CONTRACTS:
        ids=[i for i in by_id if not i.startswith('test_protection_keyword_oracle.') and i.rsplit('.',1)[-1].startswith('test_'+row['key']+'__')]
        if row['key']=='nectar':ids += [i for i in by_id if i.startswith('test_game_state.AnnihilatingNectarNeedsATargetTests.')]
        assert ids,row['name']
        for paragraph in row['selectedClauses']:
            clauses.append({'cardId':row['cardId'],'name':row['name'],'abilityId':row['abilityId'],
                'printedParagraph':paragraph,'printedTextSha256':row['printedTextSha256'],
                'independentOracle':{k:row[k] for k in ('observable','activationCost','playCost')},
                'testIds':sorted(ids),'status':'selected-branches-pass' if all(by_id[i]['status']=='pass' for i in ids) else 'fail',
                'allBranchesCertified':False})
    assert audit.digest()==digest
    proof={'schemaVersion':1,'sourceDigest':digest,'finishedAt':datetime.now(timezone.utc).isoformat(),
        'published':False,'executionSource':args.units or 'focused-execution',
        'summary':{'executed':len(tests),'passed':sum(t['status']=='pass' for t in tests),'failed':sum(t['status']!='pass' for t in tests),
            'cardsWithSelectedClauseProof':len(family.CONTRACTS),'selectedClauses':len(clauses),
            'unitScenarios':unittest.defaultTestLoader.loadTestsFromTestCase(family.ProtectionKeywordFamily).countTestCases(),
            'networkJourneys':unittest.defaultTestLoader.loadTestsFromTestCase(network.ProtectionKeywordIntegration).countTestCases(),
            'reusedUpdatedEmptyEntryScenarios':1,
            'oracleSensitivityTests':unittest.defaultTestLoader.loadTestsFromTestCase(oracle.ProtectionKeywordOracle).countTestCases()},
        'clauses':clauses,'tests':tests,'limits':[
            'Selected printed clauses and named branches only; not full certification of each card or all interactions.',
            'Entry fixtures execute the production trigger producer; five socket journeys additionally pay and resolve the Persistent Will before selecting its entry target.',
            'Retarget costs, entry timing, Cleanse, current control, source departure, copy entry, recipient snapshots and exact power values have explicit oracles.',
            'Vessel blanking uses a real Graceful Petal entry trigger; this carrier is not counted as another certified card.',
            'Hot Potato proof selects its entry paragraph only; its repeat transfer and End paragraph are outside this selected contract.',
            'Automatic phase driving disabled in the thirteen real socket journeys. No physical-device, Safari or remote-artwork certification.']}
    out=ROOT/'reports/systematic-audit/protection-keywords-followup';out.mkdir(parents=True,exist_ok=True)
    (out/'clauses.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(proof['summary']));return int(proof['summary']['failed']!=0)


if __name__=='__main__':raise SystemExit(main())
