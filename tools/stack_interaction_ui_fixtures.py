"""Literal candidate IDs for real response abilities and public production states."""
import copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('server','tests','tools')]
import test_stack_interaction_family as family


def fixtures():
    f=family.StackInteractionFamily();frames=[]
    for row in family.CONTRACTS:
        for variant in ('ready','protected','wrong_kind','missing','copied'):
            s,host,original=f.setup_case(row)
            if variant=='protected':s.rules_engine['ongoingEffects'].append({'id':'wall','kind':'protection','duration':'until_end_of_turn',
                'startedTurn':2,'target':{'kind':'stack_action','actionId':original['id']}})
            elif variant=='wrong_kind':
                original=f.original(s,'ephemeral' if row['targetKind']=='stack_effect' else 'effect')
                if row['key']=='beacon':original['targets']=[]
                s.rules_engine['actionStack']=[original]
            elif variant=='missing':s.rules_engine['actionStack']=[]
            elif variant=='copied':
                if row['targetKind']=='stack_effect':original=f.original(s,'ephemeral')
                original=s.build_rules_stack_copy(original,original['controllerId'],'ui-copy')
                s.rules_engine['actionStack']=[original]
            ability=next(a for a in family.main.CARD_ABILITIES[row['cardId']] if a['id']==row['abilityId'])
            source=f.declaration(row,host,original)['source']
            frames.append({'id':row['key']+'-'+variant,'state':s.serialize_for('p1','player'),'source':source,'ability':ability,
                'expectedStackIds':[original['id']] if variant=='ready' or variant=='copied' and row['key'] not in ('ignore','radiance') else []})
    probe={'id':'effect-probe','name':'Effect fixture','type':'manifestation','power':4,'powerCost':'{R}{R}{R}{R}',
        'cost':0,'effect':'','temperaments':['choleric'],'image':'card-back.webp'}
    return {'frames':frames,'cards':[probe,*[{**probe,'id':cid,'name':cid,'power':power,'temperaments':['phlegmatic']} for cid,power in (('m3',3),('m4',4))]]}


if __name__=='__main__':print(json.dumps(fixtures()))
