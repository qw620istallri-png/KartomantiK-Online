"""Count unique cards with explicit, passing clause-to-test links; never AST mentions."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def collect_selected_cards(documents,executions,catalog):
    cards={}
    excluded=[]
    for source,document in documents:
        if document.get('summary',{}).get('failed',0):
            excluded.append({'source':source,'reason':'report contains failing tests'})
            continue
        for clause in document.get('clauses',document.get('cards',[])):
            cid=clause.get('cardId')
            ids=clause.get('testIds') or []
            if not ids: continue  # Interaction/carrier lists are not clause proofs.
            if cid not in catalog or any(executions.get(t)!='pass' for t in ids):
                excluded.append({'source':source,'cardId':cid,'reason':'unknown card or missing/non-passing execution'})
                continue
            printed=clause.get('printedParagraph') or clause.get('printedText')
            if printed and ' '.join(printed.split()) not in ' '.join(catalog[cid]['effect'].split()):
                excluded.append({'source':source,'cardId':cid,'reason':'printed text changed; needs review'})
                continue
            entry=cards.setdefault(cid,{'cardId':cid,'name':catalog[cid]['name'],'proofs':[],'allBranchesCertified':False})
            entry['proofs'].append({'source':source,'testIds':sorted(set(ids)),
                'paragraphIndex':clause.get('paragraphIndex'),
                'printedClauseSha256':hashlib.sha256((printed or '').encode()).hexdigest()})
    return sorted(cards.values(),key=lambda c:c['name']),excluded


def status(unit_path):
    import card_behavior_audit as audit
    import main
    out=ROOT/'reports/systematic-audit'
    unit_path=Path(unit_path)
    if not unit_path.is_absolute(): unit_path=ROOT/unit_path
    unit=json.loads(unit_path.read_text(encoding='utf-8'))
    executions={t['testId']:t['status'] for t in unit['tests']}
    paths=[out/'numeric.json',*sorted(out.glob('*-followup/clauses.json'))]
    documents=[(p.relative_to(ROOT).as_posix(),json.loads(p.read_text(encoding='utf-8'))) for p in paths]
    catalog={c['id']:c for c in main.CARD_DATA}
    cards,excluded=collect_selected_cards(documents,executions,catalog)
    digest=audit.digest()
    return {'schemaVersion':1,'generatedAt':datetime.now(timezone.utc).isoformat(),'sourceDigest':digest,
        'unitEvidence':unit_path.relative_to(ROOT).as_posix(),'unitEvidenceSourceDigest':unit['sourceDigest'],
        'currentUnitEvidence':unit['sourceDigest']==digest,
        'unitEvidencePassed':not unit['summary'].get('failed') and len(executions)==unit['summary']['executed'] and all(v=='pass' for v in executions.values()),
        'summary':{'catalogCards':len(catalog),'cardsWithSelectedClauseProof':len(cards),
                   'percentageWithSelectedClauseProof':round(100*len(cards)/len(catalog),1),
                   'cardsOutsideThisStrictRegister':len(catalog)-len(cards),'fullCatalogSemanticCertification':False},
        'countingRule':'At least one explicit printed clause linked to tests that all passed in the named full unit run. Unique card IDs; interaction-only references excluded. Selected clauses do not certify all branches.',
        'cards':cards,'excluded':excluded}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--units',required=True)
    p.add_argument('--write',action='store_true')
    args=p.parse_args()
    report=status(args.units)
    if args.write:
        if not report['currentUnitEvidence']: raise RuntimeError('Unit proof is stale; rerun on the current source first')
        if not report['unitEvidencePassed']: raise RuntimeError('The named full unit run must pass before updating progress')
        path=ROOT/'reports/systematic-audit/coverage-status.json'
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'summary':report['summary'],'currentUnitEvidence':report['currentUnitEvidence'],'excluded':report['excluded']},ensure_ascii=False))
    return int(args.write and not report['currentUnitEvidence'])


if __name__=='__main__': raise SystemExit(main())
