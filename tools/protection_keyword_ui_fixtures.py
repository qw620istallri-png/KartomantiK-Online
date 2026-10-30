"""Production serialized fixtures; candidate/marker expectations are literal."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('server','tests','tools')]
import test_protection_keyword_family as family


def fixtures():
    f=family.ProtectionKeywordFamily();frames=[]
    for row in family.CONTRACTS:
        if row['mode']=='entry_gift':continue  # Hot Potato has separate entry/socket proof.
        for variant in ('active','cleansed','source_blanked'):
            if row['mode']=='link':s,source,target,_=f.enter(row)
            elif row['mode'] in ('passive','vessel'):s,source,target,_=f.setup_case(row)
            else:s,source,target,_,_=f.apply(row)
            if variant=='cleansed':f.cleanse(s,target)
            elif variant=='source_blanked' and source is not None:source['effectsDisabled']=True
            active=variant=='active' or variant=='cleansed' and row['mode'] in ('passive','vessel') or variant=='source_blanked' and row['mode'] in ('play','hand','sacrifice')
            for viewer in ('p1','p2'):
                is_vessel=row['key']=='pillar'
                name='Eliminate the Profane' if is_vessel else 'Weaken'
                cid=f.cid(name);ability=family.main.CARD_ABILITIES[cid][0]
                frames.append({'id':row['key']+'-'+variant+'-'+viewer,'key':row['key'],'viewer':viewer,
                    'state':s.serialize_for(viewer,'player'),'source':{'cardId':cid,'zone':'hand'},'ability':ability,
                    'targetId':'target','vessel':is_vessel,
                    'candidateExpected':viewer=='p1' or not active if is_vessel or row['observable']=='protection' else True,
                    'inactiveExpected':bool(active and row['observable']=='blank'),
                    'supportExpected':bool(active and row['observable']=='support'),
                    'powerExpected':2 if active and row['key']=='jaw' else 4,
                    'modifierExpected':row['mode'] not in ('passive','vessel') and active})
    return {'frames':frames}


if __name__=='__main__':print(json.dumps(fixtures()))
