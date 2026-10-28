"""Proof of the user-confirmed discard condition; Beta errata governs Press."""
import hashlib
import json
import sys
import unittest
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/d) for d in ('server','tests','tools')]
import card_behavior_audit as audit
from card_atavic_end_audit import Details
import test_conditional_discard_replacement as family
import test_conditional_discard_integration as network


def runtime_hashes():
    paths=[*sorted((ROOT/'server').rglob('*.py')),ROOT/'public/card-abilities.json',ROOT/'public/cards-data.json',ROOT/'public/extensions/inner-desert/cards.json']
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def main():
    digest=audit.digest();runtime=runtime_hashes()
    result=unittest.TextTestRunner(verbosity=1,resultclass=Details).run(unittest.TestSuite(
        unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in
        (family.ConditionalDiscardReplacement,network.ConditionalDiscardIntegration)))
    by_id={t['testId']:t for t in result.executions};clauses=[]
    for row in family.CONTRACTS:
        ids=['test_conditional_discard_replacement.ConditionalDiscardReplacement.'+family.method_name(row,p,c) for p,c in family.scenarios(row)]
        ids+=['test_conditional_discard_integration.ConditionalDiscardIntegration.'+network.method_name(row,c) for c in network.network_cases(row)]
        assert all(t in by_id for t in ids)
        clauses.append({'cardId':row['cardId'],'name':row['name'],'abilityId':row['abilityId'],
            'paragraphIndex':row['paragraphIndex'],'printedParagraph':row['printedParagraph'],
            'printedTextSha256':row['printedTextSha256'],
            'independentOracle':{k:row[k] for k in ('expectedDraw','discardCount','discardReplacementSatisfiesCondition','sequence','authority')},
            'validationStage':'discard-condition-replacements-ordered-draw-and-network',
            'testIds':ids,'scenarioCount':len(ids),'websocketScenario':True,
            'status':'selected-branches-pass' if all(by_id[t]['status']=='pass' for t in ids) else 'fail',
            'allBranchesCertified':False})
    assert {t for c in clauses for t in c['testIds']}==set(by_id)
    proof={'schemaVersion':1,'family':'conditional-discard-replacement','sourceDigest':digest,
        'finishedAt':datetime.now(timezone.utc).isoformat(),'published':False,
        'summary':{'executed':result.testsRun,'passed':sum(t['status']=='pass' for t in result.executions),
            'failed':sum(t['status']!='pass' for t in result.executions),'skipped':len(result.skipped),
            'cardsWithSelectedClauseProof':2,'selectedClauses':2,'familyScenarios':70,'networkScenarios':6},
        'clauses':clauses,'tests':result.executions,'runtimeHashes':runtime,
        'runtimeUnchangedDuringExecution':runtime_hashes()==runtime,
        'productionFixRequired':False,
        'limits':['Two previously registered cards gain selected replacement branches; no new unique-card coverage is claimed.',
            'The user confirmed that replaced hand discards satisfy the draw condition and that the Beta errata makes Press discard before drawing. The local EN/FR/IT catalog already agrees; no text change is required.',
            'Five destination profiles (Limbo, exile, suspension and both competing-replacement outcomes), bounded decks, duplicate cards, draw locks, Kanon and invalid/replayed choices are executed.',
            'Unit Press effects use isolated trigger-action fixtures. Network Press effects are produced by a real Will declaration, optional acceptance and simultaneous Stack ordering. The underlying Pray action is left unresolved while inspecting Press.',
            'Replacement states are explicit fixtures. Automatic phase driving is isolated; the phase is asserted stable during these choices.',
            'An ordinary discard-choice JSON round trip and live-server reconnect at replacement order are checked; a full process restart or persistent save restoration is not certified.',
            'Other Press clauses and all possible card combinations remain outside this batch. No new card UI, Safari, physical-device or illustration certification.']}
    assert audit.digest()==digest and proof['runtimeUnchangedDuringExecution'],'Sources changed during execution'
    out=ROOT/'reports/systematic-audit/conditional-discard-followup';out.mkdir(parents=True,exist_ok=True)
    (out/'clauses.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(proof['summary']))
    return int(not result.wasSuccessful())


if __name__=='__main__':raise SystemExit(main())
