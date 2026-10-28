"""Printed-text oracles for independent targets and ordered dependent steps."""
import copy
import hashlib
import json
import sys
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import main
import test_discard_draw_clauses as fixtures

ROOT=Path(__file__).resolve().parents[1]
CONTRACTS=json.loads((ROOT/'audit/compound-targets.json').read_text(encoding='utf-8'))['contracts']
for row in CONTRACTS:
    card=next(c for c in main.CARD_DATA if c['id']==row['cardId'])
    assert card['name']==row['name'] and card['effect']==row['printedText']
    assert hashlib.sha256(card['effect'].encode()).hexdigest()==row['printedTextSha256']
    assert [p.strip() for p in card['effect'].splitlines() if p.strip()][row['paragraphIndex']]==row['printedParagraph']
    assert row['abilityId'] in {a['id'] for a in main.CARD_ABILITIES[row['cardId']]}


class CompoundTargets(unittest.TestCase):
    world=fixtures.DiscardDrawClauses.world
    field=staticmethod(fixtures.DiscardDrawClauses.field)
    target=staticmethod(fixtures.base.AtavicEndClauses.target)

    def setup_case(self,row):
        s=self.world(); key=row['key']; host=None
        s.add_rules_excess_essence('p1',[{'temperament':c,'amount':30} for c in
            ('hollow','choleric','capricious','phlegmatic','vitreous','melancholic')])
        if row['mode']=='play': s.put_zone_card('p1','hand',row['cardId'],'p1')
        elif key=='tombloom': s.put_zone_card('p1','graveyard',row['cardId'],'p1',limbo_reason='discard')
        else:
            host=self.field(s,row['cardId'],'compound-source',zone='interzone' if key in {'paciphint','stormmace'} else 'confrontation')
            if key=='paciphint': host['counters']['Flower']=2
        if key=='shattering':
            targets=[{'kind':'player','playerId':'p2'},self.target(self.field(s,'m4','target-1',owner='p2'))]
            for cid in ('m2','pw3','m3'): s.put_zone_card('p2','deck',cid,'p2','bottom')
        elif key in {'kaos','karma','paciphint','tower','dominate','invert','induce','multicastigate'}:
            owners=['p1','p2']
            if key=='invert': owners=['p2','p1']
            if key in {'induce','multicastigate'}: owners=['p2','p2']
            items=[self.field(s,'m4','target-'+str(i),owner=p) for i,p in enumerate(owners)]
            if key=='paciphint': items[0]['fieldZone']='interzone'
            if key=='tower':
                items[0].update(cardId='pw3',fieldZone='field',counters={'Abstraction':2})
                host['fieldZone']='field'
            if key=='invert':
                for i in items: i['fieldZone']='interzone'
            if key=='induce': items[1].update(cardId='m2',isSupport=True)
            if key=='multicastigate':
                for i in items: i['isSupport']=True
            targets=[self.target(i) for i in items]
        else:
            owner='p1' if key in {'linoleus','stormmace'} else 'p2'
            item=self.field(s,'m4','target-0',owner=owner)
            targets=[self.target(item)]
            if key=='stormmace': s.rules_engine['firstManifestationItemIds']={'p1':item['id']}
        s.rules_engine['observedEvents']=[]
        return s,host,targets

    def begin(self,s,row,host,targets):
        if row['mode']=='event':
            zone='graveyard' if row['key']=='tombloom' else 'confrontation'
            actions=s.queue_rules_triggers(row['cardId'],'p1',row['event'],zone=zone,
                container_id='p1' if zone=='graveyard' else None,item_id=(host or {}).get('id'),
                controller_id='p1',event_controller_id='p1',event_targets=targets,defer=True)
            actions=[a for a in actions if a['ability']['id']==row['abilityId']]
            self.assertEqual(len(actions),1)
            s.queue_rules_simultaneous_actions(actions); action=actions[0]
        else:
            source={'cardId':row['cardId'],'zone':'hand'} if row['mode']=='play' else {
                'cardId':row['cardId'],'zone':'battlefield','itemId':host['id']}
            error,action=s.declare_rules_action('p1',row['name'],kind='play_card' if row['mode']=='play' else 'activated_effect',
                source=source,ability_id=row['abilityId'],targets=targets)
            self.assertIsNone(error,row['key'])
            spent=Counter()
            for payment in action['cost']['essenceSpent']: spent[payment['temperament']]+=payment['amount']
            self.assertEqual(dict(spent),row['essenceCost'])
        self.assertIsNone(s.rules_engine['pendingChoice'])
        self.assertEqual({p:v['score'] for p,v in s.players.items()},{'p1':50,'p2':50})
        return action

    def invalidate(self,s,target,how):
        if target['kind']=='player':
            self.field(s,'inner-deserts-022','psychowall',zone='field')
            return
        item=s.find_battlefield_item(target['itemId'])
        if how in {'missing','roundtrip'}:
            s._rules_remove_field_item(item,item['ownerId'],'hand')
            if how=='roundtrip':
                returned=s.place_rules_card_in_interzone(item['ownerId'],item['ownerId'],'hand',item['cardId'])
                self.assertIsNotNone(returned)
                self.assertNotEqual(returned['id'],target['itemId'])
        elif how=='protected':
            s.rules_engine['ongoingEffects'].append({'kind':'protection','duration':'until_end_of_turn',
                'startedTurn':2,'target':dict(target)})
        elif how=='stalemate': item['fieldZone']='stalemate'
        else: raise AssertionError(how)

    def power(self,s,iid):
        item=s.find_battlefield_item(iid)
        return s.rules_manifestation_characteristics(item)['power'] if item else None

    def verify(self,s,row,targets,valid,controllers_before):
        key=row['key']; legal=set(valid); all_valid=len(legal)==len(targets)
        if key in {'linoleus','karma'}:
            expected=50+(5 if key=='linoleus' and legal else 10*len(legal) if key=='karma' else 0)
            self.assertEqual(s.players['p1']['score'],expected)
        else: self.assertEqual(s.players['p1']['score'],50)
        self.assertEqual(s.players['p2']['score'],50)
        if key=='linoleus' and 0 in legal: self.assertEqual(self.power(s,'target-0'),5)
        elif key=='tombloom':
            self.assertEqual(s.players['p1']['zones']['exile'].count(row['cardId']),1 if legal else 0)
            if legal: self.assertEqual(self.power(s,'target-0'),2)
        elif key=='incite':
            self.assertEqual(len(s.rules_engine['effectMemories']),1 if legal else 0)
            if legal: self.assertEqual(self.power(s,'target-0'),10)
        elif key=='stormmace':
            self.assertIn(row['cardId'],s.players['p1']['zones']['graveyard'])
            if legal:
                self.assertEqual(self.power(s,'target-0'),6)
                self.assertTrue(any(e['kind']=='protection' for e in s.rules_engine['ongoingEffects']))
        elif key in {'kaos','multicastigate'}:
            for index in legal: self.assertIsNone(s.find_battlefield_item(targets[index]['itemId']))
        elif key=='shattering':
            self.assertEqual(len(s.players['p2']['zones']['deck']),0 if 0 in legal else 3)
            if 1 in legal: self.assertEqual(self.power(s,'target-1'),2 if all_valid else 4)
        elif key=='paciphint':
            self.assertEqual(s.players['p1']['zones']['deck'].count('m4'),1 if 0 in legal else 0)
            if 0 in legal: self.assertIsNone(s.find_battlefield_item('target-0'))
            if 1 in legal:
                foe=s.find_battlefield_item('target-1')
                self.assertEqual(s.rules_confrontation_power(foe),0 if all_valid else 4)
            host=s.find_battlefield_item('compound-source')
            self.assertEqual(host['counters']['Flower'],1)
        elif key=='tower':
            donor=s.find_battlefield_item('target-0');recipient=s.find_battlefield_item('target-1')
            if donor: self.assertEqual(donor['counters'].get('Abstraction',0),1 if all_valid else 2)
            if recipient: self.assertEqual(recipient['counters'].get('Abstraction',0),1 if all_valid else 0)
        elif key in {'dominate','invert'}:
            now={i['id']:s.rules_item_controller_id(i) for i in s.battlefield if i['id'].startswith('target-')}
            expected={iid:('p2' if pid=='p1' else 'p1') for iid,pid in controllers_before.items()} if all_valid else controllers_before
            self.assertEqual(now,expected)
            self.assertEqual(len(s.rules_engine['effectMemories']),2 if key=='dominate' and all_valid else 0)
        elif key=='induce' and 0 in legal: self.assertEqual(self.power(s,'target-0'),2 if all_valid else 4)

    def exercise(self,row,invalid=(),how='missing'):
        s,host,targets=self.setup_case(row)
        action=self.begin(s,row,host,targets)
        declared=copy.deepcopy(action['targets'])
        paid=copy.deepcopy(action['cost'])
        for index in invalid: self.invalidate(s,targets[index],how)
        if row['key']=='shattering' and 0 in invalid:
            # Psychowall makes both the opponent and their field card Immune.
            # It cannot model an immune player with this opponent's card legal.
            invalid=tuple(range(len(targets)))
        before={i['id']:s.rules_item_controller_id(i) for i in s.battlefield if i['id'].startswith('target-')}
        valid=[i for i in range(len(targets)) if i not in invalid]
        self.assertEqual(s.rules_top_action_has_no_valid_targets(),not valid)
        with patch('game.effects.dice.random.randint',return_value=1) as die:
            s.resolve_rules_top_action()
            if row['key'] in {'kaos','karma'}: self.assertEqual(die.call_count,len(valid))
        self.assertEqual(action['targets'],declared)
        self.assertEqual(action['cost'],paid,'A lost target must not refund paid costs')
        invalid_items={targets[i].get('itemId') for i in invalid}
        self.assertFalse(any(e.get('actionId')==action['id'] and (e.get('target') or {}).get('itemId') in invalid_items
            for e in s.rules_engine['ongoingEffects']))
        if invalid and valid: self.assertEqual(action['invalidTargetIndices'],list(invalid))
        if not valid: self.assertEqual(action['effectResult']['kind'],'invalid_targets')
        self.verify(s,row,targets,valid,before)
        if row['mode']=='play': self.assertIn(row['cardId'],s.players['p1']['zones']['graveyard'])
        return s,action

    def check_valid(self,row): self.exercise(row)
    def check_all_invalid(self,row): self.exercise(row,tuple(range(target_count(row))))

    def check_linoleus_no_target(self,row):
        s,host,_=self.setup_case(row)
        self.begin(s,row,host,[])
        self.assertFalse(s.rules_top_action_has_no_valid_targets())
        s.resolve_rules_top_action()
        self.assertEqual(s.players['p1']['score'],55)
        self.assertEqual(self.power(s,'target-0'),4)


def target_count(row): return 1 if row['key'] in {'linoleus','tombloom','incite','stormmace'} else 2


def scenarios(row):
    cases=[('valid',None,None),('all_invalid',None,None)]
    for index in range(target_count(row)):
        for how in (('immune',) if row['key']=='shattering' and index==0 else ('missing','protected','stalemate','roundtrip')):
            cases.append(('invalid_'+str(index)+'_'+how,index,how))
    if row['key']=='linoleus': cases.append(('linoleus_no_target',None,None))
    return cases


def method_name(row,name): return 'test_'+row['key']+'__'+name


for row in CONTRACTS:
    for name,index,how in scenarios(row):
        def run(self,row=row,name=name,index=index,how=how):
            if index is None: getattr(self,'check_'+name)(row)
            else: self.exercise(row,(index,),how)
        setattr(CompoundTargets,method_name(row,name),run)


if __name__=='__main__': unittest.main()
