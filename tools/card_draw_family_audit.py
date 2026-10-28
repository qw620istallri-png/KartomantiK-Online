"""Execute independent fixed draw, hand-discard and deck-discard contracts."""
import json
import sys
import unittest
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/d) for d in ('server','tests','tools')]
import card_behavior_audit as audit
from card_atavic_end_audit import Details
import test_draw_discard_family as family
import test_draw_family_integration as network


def main():
    digest=audit.digest()
    result=unittest.TextTestRunner(verbosity=1,resultclass=Details).run(unittest.TestSuite(
        unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in
        (family.DrawDiscardFamily,network.DrawFamilyIntegration)))
    by_id={t['testId']:t for t in result.executions};clauses=[]
    for row in family.CONTRACTS:
        ids=['test_draw_discard_family.DrawDiscardFamily.'+family.method_name(row,scenario)
             for scenario in family.scenarios(row)]
        ids+=['test_draw_family_integration.DrawFamilyIntegration.'+network.method_name(row,case)
              for case in network.network_cases(row)]
        assert all(t in by_id for t in ids)
        clauses.append({'cardId':row['cardId'],'name':row['name'],'abilityId':row['abilityId'],
            'paragraphIndex':row['paragraphIndex'],'printedParagraph':row['printedParagraph'],
            'printedTextSha256':row['printedTextSha256'],
            'independentOracle':{k:row[k] for k in ('kind','expectedAmount','sourceZone','eventRelation','essenceCost')},
            'validationStage':'event-queue-and-resolution' if row['mode']=='event' else 'declaration-payment-and-resolution',
            'testIds':ids,'scenarioCount':len(ids),'websocketScenario':True,
            'status':'selected-branches-pass' if all(by_id[t]['status']=='pass' for t in ids) else 'fail',
            'allBranchesCertified':False})
    assert {t for c in clauses for t in c['testIds']}==set(by_id)
    proof={'schemaVersion':1,'family':'draw-discard-fixed','sourceDigest':digest,
        'finishedAt':datetime.now(timezone.utc).isoformat(),'published':False,
        'summary':{'executed':result.testsRun,'passed':sum(t['status']=='pass' for t in result.executions),
            'failed':sum(t['status']!='pass' for t in result.executions),'skipped':len(result.skipped),
            'cardsWithSelectedClauseProof':len({r['cardId'] for r in family.CONTRACTS}),
            'selectedClauses':len(clauses),'familyScenarios':sum(len(family.scenarios(r)) for r in family.CONTRACTS),
            'networkScenarios':sum(len(network.network_cases(r)) for r in family.CONTRACTS)},
        'clauses':clauses,'tests':result.executions,
        'limits':['Fifteen selected fixed-quantity clauses, not all abilities or interactions of the thirteen cards.',
            'Trigger stimuli are explicit and use production queues. Five additional producer cases use actual Support/Will/deck-discard paths; tribute-producing declarations and complete matches are not certified.',
            'Ponder and Zum use real declarations, exact paid essences and resolution. Other Zum abilities and the all-five Support condition are outside this batch.',
            'Pidue covers only its vitreous draw and melancholic discard branches. Its other temperaments remain outside this batch.',
            'Kanon replacement checks use Manifestations as discarded cards, so the Will-discard power-distribution follow-up is not certified by this batch.',
            'BOB/Quasimillenary ordering is tested on simple single hand-discard effects. Discard-then-draw conditional continuations, exiling costs, shuffles and larger sequential effects require separate proofs.',
            'The network journeys use controlled event/replacement fixtures and actual choice/priority messages; auto-phase driving is isolated.',
            'No new card UI, physical-device, Safari or illustration certification is implied.']}
    assert audit.digest()==digest,'Sources changed during execution'
    out=ROOT/'reports/systematic-audit/draw-family-followup';out.mkdir(parents=True,exist_ok=True)
    (out/'clauses.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(proof['summary']))
    return int(not result.wasSuccessful())


if __name__=='__main__':raise SystemExit(main())
