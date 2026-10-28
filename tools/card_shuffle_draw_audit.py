"""Execute handwritten shuffle/draw contracts and their actual protocol paths."""
import json
import sys
import unittest
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/d) for d in ('server','tests','tools')]
import card_behavior_audit as audit
from card_atavic_end_audit import Details
import test_shuffle_draw as family
import test_shuffle_draw_integration as network


def main():
    digest=audit.digest()
    result=unittest.TextTestRunner(verbosity=1,resultclass=Details).run(unittest.TestSuite(
        unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in
        (family.ShuffleDraw,network.ShuffleDrawIntegration)))
    by_id={t['testId']:t for t in result.executions};clauses=[]
    for row in family.CONTRACTS:
        ids=['test_shuffle_draw.ShuffleDraw.'+family.method_name(row,case) for case in family.scenarios(row)]
        ids+=['test_shuffle_draw_integration.ShuffleDrawIntegration.'+network.method_name(row,case) for case in network.network_cases(row)]
        assert all(t in by_id for t in ids)
        clauses.append({'cardId':row['cardId'],'name':row['name'],'abilityId':row['abilityId'],
            'paragraphIndex':row['paragraphIndex'],'printedParagraph':row['printedParagraph'],
            'printedTextSha256':row['printedTextSha256'],
            'independentOracle':{k:row[k] for k in ('expectedDraw','allPlayers','essenceCost')},
            'validationStage':'declaration-payment-ordered-resolution-and-network-choices',
            'testIds':ids,'scenarioCount':len(ids),'websocketScenario':True,
            'status':'selected-branches-pass' if all(by_id[t]['status']=='pass' for t in ids) else 'fail',
            'allBranchesCertified':False})
    assert {t for c in clauses for t in c['testIds']}==set(by_id)
    proof={'schemaVersion':1,'family':'shuffle-then-draw','sourceDigest':digest,
        'finishedAt':datetime.now(timezone.utc).isoformat(),'published':False,
        'summary':{'executed':result.testsRun,'passed':sum(t['status']=='pass' for t in result.executions),
            'failed':sum(t['status']!='pass' for t in result.executions),'skipped':len(result.skipped),
            'cardsWithSelectedClauseProof':2,'selectedClauses':2,'familyScenarios':37,'networkScenarios':5},
        'clauses':clauses,'tests':result.executions,
        'limits':['Two selected shuffle/draw clauses, not every interaction of the two cards.',
            'Shuffles are held deterministic for exact order and conservation assertions; randomness quality is not assessed.',
            'Kanon, both players with Kanon, its Will-discard power distribution, draw locks, BOB, Purifying Ritual and competing suspension/exile are exercised in controlled states.',
            'Network tests cover a delta client and a legacy client, reconnect and invalid/replayed confirmations. Automatic phase driving is isolated; phase stability during these choices is asserted.',
            'Conditional discard-then-draw semantics under replacement remain pending a user ruling and are not certified here.',
            'No new UI, Safari, physical-device or illustration certification is implied.']}
    assert audit.digest()==digest,'Sources changed during execution'
    out=ROOT/'reports/systematic-audit/shuffle-draw-followup';out.mkdir(parents=True,exist_ok=True)
    (out/'clauses.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(proof['summary']))
    return int(not result.wasSuccessful())


if __name__=='__main__':raise SystemExit(main())
