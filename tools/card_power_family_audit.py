"""Execute all independent contracts of the first effect family and retain IDs."""
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/d) for d in ('server','tests','tools')]
import card_behavior_audit as audit
from card_atavic_end_audit import Details
from card_effect_families import power_family_candidates
import test_power_family as family
from test_power_family_integration import PowerFamilyIntegration
from test_coverage_status import CoverageStatus


def main():
    digest=audit.digest()
    result=unittest.TextTestRunner(verbosity=1,resultclass=Details).run(unittest.TestSuite(
        unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in
        (family.PowerFamily,family.PowerFamilyOracleSensitivity,PowerFamilyIntegration,CoverageStatus)))
    by_id={t['testId']:t for t in result.executions}
    clauses=[]
    for row in family.CONTRACTS:
        ids=['test_power_family.PowerFamily.'+family.method_name(row,s) for s in family.scenarios(row)]
        if row['mode']!='event': ids.append('test_power_family_integration.PowerFamilyIntegration.test_'+row['key']+'__websocket_resolution')
        assert all(t in by_id for t in ids)
        clauses.append({'cardId':row['cardId'],'name':row['name'],'abilityId':row['abilityId'],
            'paragraphIndex':row['paragraphIndex'],'printedParagraph':row['printedParagraph'],
            'printedTextSha256':row['printedTextSha256'],'independentOracle':{
                k:row[k] for k in ('expectedDelta','lifetime','targetRelation','targetZone','targetBase','essenceCost')},
            'validationStage':'event-queue-and-resolution' if row['mode']=='event' else 'declaration-payment-and-resolution-plus-websocket',
            'testIds':ids,'scenarioCount':len(ids),
            'status':'selected-branches-pass' if all(by_id[t]['status']=='pass' for t in ids) else 'fail',
            'allBranchesCertified':False})
    linked={t for c in clauses for t in c['testIds']}
    infrastructure=[t for t in by_id if t not in linked]
    assert len(infrastructure)==5
    candidates=power_family_candidates()
    proof={'schemaVersion':1,'family':'fixed-power-change','sourceDigest':digest,
        'finishedAt':datetime.now(timezone.utc).isoformat(),'published':False,
        'summary':{'executed':result.testsRun,'passed':sum(t['status']=='pass' for t in result.executions),
            'failed':sum(t['status']!='pass' for t in result.executions),'skipped':len(result.skipped),
            'cardsWithSelectedClauseProof':len({r['cardId'] for r in family.CONTRACTS}),
            'selectedParagraphs':len(clauses),'familyScenarios':sum(len(family.scenarios(r)) for r in family.CONTRACTS),
            'networkScenarios':sum(r['mode']!='event' for r in family.CONTRACTS),'auditInfrastructureTests':len(infrastructure)},
        'clauses':clauses,'infrastructureTestIds':infrastructure,'tests':result.executions,
        'candidateInventory':{'source':'ability metadata; grouping only, not proof',
            'effects':len(candidates),'cards':len({c['cardId'] for c in candidates}),
            'withoutIndependentContract':[c for c in candidates if not c['hasIndependentContract']]},
        'limits':['Selected power clauses only; other abilities and all branches remain uncertified.',
            'Triggered effects use production event queues with explicit event stimuli; their full producer actions and whole-match scheduling are outside this batch.',
            'The Thornmaster intrinsic source change has its own scenario applicability; targeted Protection/token cases are not applied to it.',
            'Non-power parts of compound effects are only checked where explicitly asserted; costs, trigger conditions and exact deltas are handwritten.',
            'Cards sharing an encoded mechanism but lacking an independent contract are not counted.',
            'No new browser/card-illustration or physical-device certification is implied by these backend tests.']}
    assert audit.digest()==digest,'Sources changed during execution'
    out=ROOT/'reports/systematic-audit/power-family-followup'
    out.mkdir(parents=True,exist_ok=True)
    (out/'clauses.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(proof['summary']))
    return int(not result.wasSuccessful())


if __name__=='__main__': raise SystemExit(main())
