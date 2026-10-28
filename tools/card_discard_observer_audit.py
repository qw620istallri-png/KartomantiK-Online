"""Execute discard observer contracts with actual movement producers."""
import json
import sys
import unittest
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/d) for d in ('server','tests','tools')]
import card_behavior_audit as audit
from card_atavic_end_audit import Details
import test_discard_observers as family
import test_discard_observer_integration as network


def main():
    digest=audit.digest()
    result=unittest.TextTestRunner(verbosity=1,resultclass=Details).run(unittest.TestSuite(
        unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in (family.DiscardObservers,network.DiscardObserverIntegration)))
    by_id={t['testId']:t for t in result.executions};clauses=[]
    for row in family.CONTRACTS:
        ids=['test_discard_observers.DiscardObservers.'+family.method_name(row,c) for c in family.scenarios(row)]
        ids+=['test_discard_observer_integration.DiscardObserverIntegration.'+network.method_name(row,c) for c in network.network_cases(row)]
        assert all(t in by_id for t in ids)
        clauses.append({'cardId':row['cardId'],'name':row['name'],'abilityId':row['abilityId'],
            'paragraphIndex':row['paragraphIndex'],'printedParagraph':row['printedParagraph'],
            'printedTextSha256':row['printedTextSha256'],
            'independentOracle':{k:row[k] for k in ('kind','event','eventRelation','expectedDelta','sourceZone','duration')},
            'validationStage':'movement-producer-observed-event-target-choice-and-exact-resolution',
            'testIds':ids,'scenarioCount':len(ids),'websocketScenario':True,
            'status':'selected-branches-pass' if all(by_id[t]['status']=='pass' for t in ids) else 'fail',
            'allBranchesCertified':False})
    assert {t for c in clauses for t in c['testIds']}==set(by_id)
    proof={'schemaVersion':1,'family':'discard-observers-under-replacement','sourceDigest':digest,
        'finishedAt':datetime.now(timezone.utc).isoformat(),'published':False,
        'summary':{'executed':result.testsRun,'passed':sum(t['status']=='pass' for t in result.executions),
            'failed':sum(t['status']!='pass' for t in result.executions),'skipped':len(result.skipped),
            'cardsWithSelectedClauseProof':8,'selectedClauses':8,'familyScenarios':168,'networkScenarios':10},
        'clauses':clauses,'tests':result.executions,
        'rulingId':'replaced-discard-observers',
        'supersededHistoricalInterpretation':{'testId':'test_kanon_event_clauses.KanonEventClauses.test_suspension_replaces_movements_without_draw_discard_or_will_penalty',
            'note':'Historical test ID retained for evidence identity; assertions now require discard events and Will penalties. The older report describes the previous interpretation, superseded by the explicit 2026-10-28 ruling.'},
        'limits':['Eight selected clauses and their executed branches; not all abilities or combinations of these cards.',
            'Ordinary movement methods and the multi-card discard result produce actual events. No synthetic cards_discarded stimulus is used to prove replaced discard watchers.',
            'Replacement sources are explicit fixtures. Most network roots are controlled Pluff entry-trigger actions, not a complete Pluff play or entry journey. Kanon uses an actual Ponder declaration and payment.',
            'The two network Otranth cases distinguish actual Limbo entry from suspension. Self-discard triggers such as Tombloom or Nghoul-ong outside Limbo remain a separate audit.',
            'Group counts are checked for one multi-card discard action. Multiple separate discard instructions before one event flush are outside this batch.',
            'Kanon keeps its existing public discardedCardIds list restricted to ordinary Limbo/Support movements; the Will penalty now counts all successful discards without exposing private suspended/exiled identities.',
            'Network checks use delta and legacy clients, live-server reconnect, choices and priority passes; automatic phase driving is isolated.',
            'No new card UI, Safari, physical-device, process-restart or illustration certification.']}
    assert audit.digest()==digest,'Sources changed during execution'
    out=ROOT/'reports/systematic-audit/discard-observer-followup';out.mkdir(parents=True,exist_ok=True)
    (out/'clauses.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(proof['summary']))
    return int(not result.wasSuccessful())


if __name__=='__main__':raise SystemExit(main())
