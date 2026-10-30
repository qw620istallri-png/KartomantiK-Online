"""Selected Stack clauses, real response paths and explicitly reused Duel proofs."""
import argparse,json,sys,unittest
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('server','tests','tools')]
import card_behavior_audit as audit
from card_atavic_end_audit import Details
import test_stack_interaction_family as family
import test_stack_interaction_triggers as special
import test_stack_interaction_integration as network
import test_stack_interaction_oracle as oracle
import test_stack_intrinsic_payment as prior

CLASSES=(family.StackInteractionFamily,special.StackInteractionTriggers,
         network.StackInteractionIntegration,oracle.StackInteractionOracle,prior.StackIntrinsicPaymentTests)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--units');args=parser.parse_args()
    digest=audit.digest()
    expected={t.id() for cls in CLASSES for t in unittest.defaultTestLoader.loadTestsFromTestCase(cls)}
    if args.units:
        full=json.loads((ROOT/args.units).read_text(encoding='utf-8'))
        assert full['sourceDigest']==digest and not full['summary']['failed']
        tests=[t for t in full['tests'] if t['testId'] in expected]
    else:
        result=unittest.TextTestRunner(verbosity=1,resultclass=Details).run(unittest.TestSuite(
            unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in CLASSES))
        tests=result.executions
    by_id={t['testId']:t for t in tests};assert set(by_id)==expected
    clauses=[]
    for row in family.ALL_CONTRACTS:
        ids=[i for i in by_id if (i.startswith('test_stack_interaction_family.') or i.startswith('test_stack_interaction_integration.'))
             and i.rsplit('.',1)[-1].startswith('test_'+row['key']+'__')]
        ids += [i for i in by_id if i.startswith('test_stack_interaction_triggers.') and
                i.rsplit('.',1)[-1].startswith('test_'+row['key']+'_')]
        if row['key']=='duel':ids += [i for i in by_id if i.startswith('test_stack_intrinsic_payment.StackIntrinsicPaymentTests.')]
        assert ids,row['name']
        for text in row['selectedClauses']:
            clauses.append({'cardId':row['cardId'],'name':row['name'],'abilityId':row['abilityId'],
                'printedParagraph':text,'printedTextSha256':row['printedTextSha256'],
                'independentOracle':{k:row[k] for k in ('essenceCost','targetKind','outcome','counterCost','exhaustSource')},
                'testIds':sorted(set(ids)),'status':'selected-branches-pass' if all(by_id[i]['status']=='pass' for i in ids) else 'fail',
                'allBranchesCertified':False})
    assert audit.digest()==digest
    proof={'schemaVersion':1,'sourceDigest':digest,'finishedAt':datetime.now(timezone.utc).isoformat(),
        'published':False,'executionSource':args.units or 'focused-execution',
        'summary':{'executed':len(tests),'passed':sum(t['status']=='pass' for t in tests),'failed':sum(t['status']!='pass' for t in tests),
            'selectedClauses':len(clauses),'cardsWithSelectedClauseProof':len(family.ALL_CONTRACTS),
            'coreScenarios':len(list(unittest.defaultTestLoader.loadTestsFromTestCase(family.StackInteractionFamily))),
            'triggerScenarios':len(list(unittest.defaultTestLoader.loadTestsFromTestCase(special.StackInteractionTriggers))),
            'networkJourneys':len(list(unittest.defaultTestLoader.loadTestsFromTestCase(network.StackInteractionIntegration))),
            'oracleSensitivityTests':len(list(unittest.defaultTestLoader.loadTestsFromTestCase(oracle.StackInteractionOracle))),
            'reusedDuelScenarios':len(list(unittest.defaultTestLoader.loadTestsFromTestCase(prior.StackIntrinsicPaymentTests)))},
        'clauses':clauses,'tests':tests,
        'resolvedRulings':[
            {'id':'stack-copy-owner','rule':'A copy is owned by its creator: Deny payment and Compensate printed-tribute refund go to that player.','status':'creator-confirmed; regression-tested'},
            {'id':'eorthoda-timing','rule':'Protection is intrinsic at tribute payment, without a separate Stack object.','status':'creator-confirmed; regression-tested'},
            {'id':'stack-copy-category','rule':'Will copies are card tokens on the Stack, not detached effects. Persistent copies enter the field as tokens.','status':'creator-confirmed; regression-tested'}],
        'limits':['Selected clauses and explicit branches only, not every interaction of the thirteen cards.',
            'Core pending original actions are controlled fixtures; responses use production declarations, costs and Stack resolution.',
            'Triggered tests also execute the public server declaration hook that produces tribute and Will-play triggers.',
            'Eorthoda timing uses the atomic public declaration hook; a bare Session declaration does not invoke the public trigger producer.',
            'Copied targets use production declarations; controlled pending originals isolate the selected interactions.',
            'Automatic phase driving disabled in the real socket journeys. Physical devices and remote artwork are not certified.']}
    out=ROOT/'reports/systematic-audit/stack-interactions-followup';out.mkdir(parents=True,exist_ok=True)
    (out/'clauses.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(proof['summary']));return int(proof['summary']['failed']!=0)


if __name__=='__main__':raise SystemExit(main())
