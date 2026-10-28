"""Selected self-discard clauses with original source-occurrence identity."""
import json,sys,unittest
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/d) for d in ('server','tests','tools')]
import card_behavior_audit as audit
from card_atavic_end_audit import Details
import test_self_discard as family
import test_self_discard_integration as network

def main():
    digest=audit.digest()
    result=unittest.TextTestRunner(verbosity=1,resultclass=Details).run(unittest.TestSuite(
        unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in (family.SelfDiscard,network.SelfDiscardIntegration)))
    by_id={t['testId']:t for t in result.executions};clauses=[]
    for row in family.CONTRACTS:
        ids=['test_self_discard.SelfDiscard.'+family.method_name(row,c) for c in family.scenarios(row)]
        ids+=['test_self_discard_integration.SelfDiscardIntegration.'+network.method_name(row,c) for c in network.network_cases(row)]
        assert all(t in by_id for t in ids)
        clauses.append({'cardId':row['cardId'],'name':row['name'],'abilityId':row['abilityId'],
            'paragraphIndex':0,'printedParagraph':row['printedParagraph'],'printedTextSha256':row['printedTextSha256'],
            'independentOracle':{k:row[k] for k in ('expectedPowerDelta','maxWillCost','selfExileFromSuspensionAllowed')},
            'testIds':ids,'status':'selected-branches-pass' if all(by_id[t]['status']=='pass' for t in ids) else 'fail','allBranchesCertified':False})
    proof={'schemaVersion':1,'sourceDigest':digest,'finishedAt':datetime.now(timezone.utc).isoformat(),'published':False,
        'summary':{'executed':result.testsRun,'passed':sum(t['status']=='pass' for t in result.executions),'failed':sum(t['status']!='pass' for t in result.executions),'skipped':len(result.skipped),'selectedClauses':2,'cardsWithSelectedClauseProof':2,'familyScenarios':33,'networkScenarios':4},
        'clauses':clauses,'tests':result.executions,'rulingId':'self-discard-exile-from-suspension',
        'limits':['Two selected clauses and executed branches, not complete card/match certification.',
            'Unit sources, Nullify resolved state, BOB and duplicate occurrences are controlled fixtures. Reentry/source departure interventions are occurrence controls, not complete opponent-response journeys.',
            'Four network journeys use actual Pray declarations and discard choices, then a self-discard choice and live-server reconnect. The successful Nghoul journey plays Ponder through the granted free permission and checks its exile on leaving the Stack.',
            'Private Limbo/Exile occurrence ledgers preserve identical copies and same-zone reorder. Existing in-flight legacy actions without an occurrence snapshot retain their former Limbo fallback; no process restart is certified.',
            'Automatic phase driving is isolated. No new card UI, physical-device, Safari or illustration certification.']}
    assert {t for c in clauses for t in c['testIds']}==set(by_id) and audit.digest()==digest
    out=ROOT/'reports/systematic-audit/self-discard-followup'
    (out/'clauses.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(proof['summary']));return int(not result.wasSuccessful())
if __name__=='__main__':raise SystemExit(main())
