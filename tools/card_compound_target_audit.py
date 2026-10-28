"""Explicit printed-clause links for compound target resolution and WS proofs."""
import json
import sys
import unittest
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/d) for d in ('server','tests','tools')]
import card_behavior_audit as audit
from card_atavic_end_audit import Details
import test_compound_targets as family
import test_compound_target_integration as network


def main():
    digest=audit.digest()
    result=unittest.TextTestRunner(verbosity=1,resultclass=Details).run(unittest.TestSuite(
        unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in
        (family.CompoundTargets,network.CompoundTargetIntegration)))
    by_id={t['testId']:t for t in result.executions}
    clauses=[]
    for row in family.CONTRACTS:
        ids=['test_compound_targets.CompoundTargets.'+family.method_name(row,name)
             for name,_,_ in family.scenarios(row)]
        ids+=['test_compound_target_integration.CompoundTargetIntegration.'+network.method_name(row,index)
              for index in network.network_cases(row)]
        assert all(t in by_id for t in ids)
        clauses.append({'cardId':row['cardId'],'name':row['name'],'abilityId':row['abilityId'],
            'paragraphIndex':row['paragraphIndex'],'printedParagraph':row['printedParagraph'],
            'printedTextSha256':row['printedTextSha256'],
            'validationStage':'event-queue-and-resolution' if row['mode']=='event' else 'declaration-payment-and-resolution',
            'oracle':'Handwritten per-card outcome assertions in CompoundTargets.verify; not derived from ability result values.',
            'testIds':ids,'scenarioCount':len(ids),'websocketScenario':True,
            'status':'selected-branches-pass' if all(by_id[t]['status']=='pass' for t in ids) else 'fail',
            'allBranchesCertified':False})
    assert {t for c in clauses for t in c['testIds']}==set(by_id)
    proof={'schemaVersion':1,'family':'compound-target-resolution','sourceDigest':digest,
        'finishedAt':datetime.now(timezone.utc).isoformat(),'published':False,
        'summary':{'executed':result.testsRun,'passed':sum(t['status']=='pass' for t in result.executions),
            'failed':sum(t['status']!='pass' for t in result.executions),'skipped':len(result.skipped),
            'cardsWithSelectedClauseProof':len(clauses),'selectedClauses':len(clauses),
            'familyScenarios':sum(len(family.scenarios(r)) for r in family.CONTRACTS),
            'networkScenarios':sum(len(network.network_cases(r)) for r in family.CONTRACTS)},
        'clauses':clauses,'tests':result.executions,
        'limits':['Selected compound/grouped target clauses only, not every ability or interaction of each card.',
            'Triggered effects use explicit stimuli and production queues; their full producer actions are not covered by this batch.',
            'Played/activated abilities use real declarations and costs. The first ally selection timing of Paciphint is inherited from the existing declaration contract, not independently certified here.',
            'Invalidation is a controlled fixture. WebSocket journeys isolate auto-phase driving and pass real priority; they do not independently certify automatic invalid-target resolution.',
            'Bro die outcomes are fixed at 1; all other random outcomes require separate cases.',
            'Psychowall invalidates both the opponent player and their field card; the bench does not invent a legal opponent field target under that immunity.',
            'Paciphint replacements of its donor movement, tokens as donors and attached-card cases remain outside this batch.',
            'Scrambling Beacon retargeting and other compound handlers are not certified by this bounded group.',
            'No new card UI, physical-device, Safari or illustration certification is implied.']}
    assert audit.digest()==digest,'Sources changed during execution'
    out=ROOT/'reports/systematic-audit/compound-target-followup'
    out.mkdir(parents=True,exist_ok=True)
    (out/'clauses.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(proof['summary']))
    return int(not result.wasSuccessful())


if __name__=='__main__': raise SystemExit(main())
