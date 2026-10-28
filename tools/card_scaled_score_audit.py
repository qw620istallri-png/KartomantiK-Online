"""Execute the six independent scaling contracts with per-card execution links."""
import json
import sys
import unittest
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/d) for d in ('server','tests','tools')]
import card_behavior_audit as audit
from card_atavic_end_audit import Details
import test_scaled_score_family as family
from test_scaled_score_integration import ScaledScoreIntegration


def main():
    digest=audit.digest()
    result=unittest.TextTestRunner(verbosity=1,resultclass=Details).run(unittest.TestSuite(
        unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in
        (family.ScaledScoreFamily,family.ScaledScoreOracleSensitivity,ScaledScoreIntegration)))
    by_id={t['testId']:t for t in result.executions}
    clauses=[]
    for row in family.CONTRACTS:
        ids=['test_scaled_score_family.ScaledScoreFamily.'+family.method_name(row,s)
             for s in family.scenarios(row)]
        ids.append('test_scaled_score_integration.ScaledScoreIntegration.test_'+row['key']+'__websocket_dynamic_count')
        assert all(t in by_id for t in ids)
        clauses.append({'cardId':row['cardId'],'name':row['name'],'abilityId':row['abilityId'],
            'paragraphIndex':row['paragraphIndex'],'printedParagraph':row['printedParagraph'],
            'printedTextSha256':row['printedTextSha256'],'independentOracle':{
                k:row[k] for k in ('expectedMultiplier','recipient','scope','event','essenceCost')},
            'validationStage':'declaration-payment-and-resolution' if row['mode']=='play' else 'event-queue-and-resolution-plus-outcome-builder',
            'testIds':ids,'scenarioCount':len(ids),'websocketScenario':True,
            'status':'selected-branches-pass' if all(by_id[t]['status']=='pass' for t in ids) else 'fail',
            'allBranchesCertified':False})
    linked={t for c in clauses for t in c['testIds']}
    infrastructure=[t for t in by_id if t not in linked]
    assert len(infrastructure)==1
    proof={'schemaVersion':1,'family':'scaled-point-change','sourceDigest':digest,
        'finishedAt':datetime.now(timezone.utc).isoformat(),'published':False,
        'summary':{'executed':result.testsRun,'passed':sum(t['status']=='pass' for t in result.executions),
            'failed':sum(t['status']!='pass' for t in result.executions),'skipped':len(result.skipped),
            'cardsWithSelectedClauseProof':6,'selectedClauses':6,
            'familyScenarios':sum(len(family.scenarios(r)) for r in family.CONTRACTS),
            'networkScenarios':6,'auditInfrastructureTests':1},
        'clauses':clauses,'infrastructureTestIds':infrastructure,'tests':result.executions,
        'limits':['Six selected printed point clauses only; every branch of each card remains uncertified.',
            'Population changes are explicit controlled fixtures; separate producer cases exercise the real confrontation-outcome and End trigger builders, not a complete match.',
            'Plea uses real declarations, green essence payment and resolution; other cards use normal triggered effects on the Stack.',
            'The six WebSocket cases modify the counted fixture while the action waits, then pass actual priority and verify both clients against the precise resolved action ID. Auto-phase driving is isolated.',
            'Donmo tests exhaustion on the field, both upright orientations, Will/token/copy inclusion and current control. Exhausted Stalemate/covered/attached card counting is outside this batch.',
            'Agrupol tests only legal opponent-Vessel populations, including duplicates and reset animation; its bottom-Deck shuffle is not certified.',
            'Donmo activation and tribute prohibition are outside the selected score clause.',
            'All six cards already have selected-clause evidence; the unique-card counter must not increase.',
            'No new browser/card UI, physical device, Safari or illustration certification is implied.']}
    assert audit.digest()==digest,'Sources changed during execution'
    out=ROOT/'reports/systematic-audit/scaled-score-followup'
    out.mkdir(parents=True,exist_ok=True)
    (out/'clauses.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(proof['summary']))
    return int(not result.wasSuccessful())


if __name__=='__main__': raise SystemExit(main())
