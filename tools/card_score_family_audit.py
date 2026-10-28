"""Execute independent fixed-point contracts and retain each real test ID."""
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/d) for d in ('server','tests','tools')]
import card_behavior_audit as audit
from card_atavic_end_audit import Details
from card_effect_families import score_family_candidates
import test_score_family as family
from test_score_family_integration import ScoreFamilyIntegration, NETWORK_KEYS


def main():
    digest=audit.digest()
    result=unittest.TextTestRunner(verbosity=1,resultclass=Details).run(unittest.TestSuite(
        unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in
        (family.ScoreFamily,family.ScoreFamilyOracleSensitivity,ScoreFamilyIntegration)))
    by_id={t['testId']:t for t in result.executions}
    clauses=[]
    for row in family.CONTRACTS:
        ids=['test_score_family.ScoreFamily.'+family.method_name(row,s) for s in family.scenarios(row)]
        if row['key'] in NETWORK_KEYS:
            ids.append('test_score_family_integration.ScoreFamilyIntegration.test_'+row['key']+'__websocket_resolution')
        assert all(t in by_id for t in ids)
        clauses.append({'cardId':row['cardId'],'name':row['name'],'abilityId':row['abilityId'],
            'paragraphIndex':row['paragraphIndex'],'printedParagraph':row['printedParagraph'],
            'printedTextSha256':row['printedTextSha256'],'independentOracle':{
                k:row[k] for k in ('expectedDelta','recipient','sourceZone','event','eventRelation')},
            'validationStage':'event-queue-and-resolution',
            'producerScenario':row['key'] in family.PRODUCERS or row['key'] in {'cannon','zam_za'},
            'websocketScenario':row['key'] in NETWORK_KEYS,
            'testIds':ids,'scenarioCount':len(ids),
            'status':'selected-branches-pass' if all(by_id[t]['status']=='pass' for t in ids) else 'fail',
            'allBranchesCertified':False})
    linked={t for c in clauses for t in c['testIds']}
    infrastructure=[t for t in by_id if t not in linked]
    assert len(infrastructure)==1
    candidates=score_family_candidates()
    proof={'schemaVersion':1,'family':'fixed-point-change','sourceDigest':digest,
        'finishedAt':datetime.now(timezone.utc).isoformat(),'published':False,
        'summary':{'executed':result.testsRun,'passed':sum(t['status']=='pass' for t in result.executions),
            'failed':sum(t['status']!='pass' for t in result.executions),'skipped':len(result.skipped),
            'cardsWithSelectedClauseProof':len({r['cardId'] for r in family.CONTRACTS}),
            'selectedClauses':len(clauses),'familyScenarios':sum(len(family.scenarios(r)) for r in family.CONTRACTS),
            'networkScenarios':len(NETWORK_KEYS),'auditInfrastructureTests':len(infrastructure)},
        'clauses':clauses,'infrastructureTestIds':infrastructure,'tests':result.executions,
        'candidateInventory':{'source':'ability metadata; grouping only, not proof',
            'effects':len(candidates),'cards':len({c['cardId'] for c in candidates}),
            'withoutIndependentContract':[c for c in candidates if not c['hasIndependentContract']]},
        'limits':['Only the selected fixed-point clauses and explicit branches are certified.',
            'The generic matrix supplies explicit event stimuli, not whole-match event production.',
            'Sixteen producer scenarios use actual turn/confrontation builders, score adjustments, discards, field moves or power counters; each filters the selected ability. Simultaneous ordering is isolated there.',
            'Cannon and Zam-za additionally use paid Strengthen declarations, the production trigger wrapper and both legal Stack orders.',
            'Otranth counter restoration and Chariot movement are not proved by their score-only rows; other clauses on these cards remain outside this batch.',
            'Linoleus is tested with a valid optional target and with no target; late-invalid compound targets require a separate audit.',
            'Scaled point effects remain inventoried, not counted as new proof.',
            'No new browser, physical-device, Safari or illustration certification is implied.']}
    assert audit.digest()==digest,'Sources changed during execution'
    out=ROOT/'reports/systematic-audit/score-family-followup'
    out.mkdir(parents=True,exist_ok=True)
    (out/'clauses.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(proof['summary']))
    return int(not result.wasSuccessful())


if __name__=='__main__': raise SystemExit(main())
