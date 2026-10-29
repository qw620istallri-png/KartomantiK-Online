"""Printed movement oracles; declarations use shipped cards, targets are fixtures."""
import json
import hashlib
import unittest
from unittest.mock import patch
from pathlib import Path
from collections import Counter
import main
import test_exile_family as base

ROOT=Path(__file__).resolve().parents[1]
CONTRACTS=json.loads((ROOT/'audit/zone-destination-family.json').read_text(encoding='utf-8'))['contracts']
for row in CONTRACTS:
    c=next(c for c in main.CARD_DATA if c['id']==row['cardId'])
    assert c['name']==row['name'] and c['effect']==row['printedText']
    assert hashlib.sha256(c['effect'].encode()).hexdigest()==row['printedTextSha256']

class ZoneDestinationFamily(unittest.TestCase):
    world=base.ExileFamily.world
    field=staticmethod(base.ExileFamily.field)
    put=staticmethod(base.ExileFamily.put)
    target=staticmethod(base.ExileFamily.target)
    snapshot=base.ExileFamily.snapshot

    def setup_case(self,row,kind='manifestation'):
        s=self.world()
        s.card_rules['destination-probe']={'type':kind,'power':3,'powerCost':'{G}{G}{G}','temperaments':['phlegmatic']}
        s.manifestation_ids.add('destination-probe')
        s.card_points['destination-probe']=20
        self.put(s,'p1','hand',[row['cardId']])
        for pid in ('p1','p2'): self.put(s,pid,'deck',['m2','m4'])
        s.add_rules_excess_essence('p1',[{'temperament':c,'amount':20} for c in ('vitreous','melancholic','capricious')])
        owner='p1' if row['key'] in ('revive','salvage') else 'p2'
        item=None
        if row['targetZone']=='battlefield':
            item=self.field(s,'destination-probe','destination-target',owner=owner,
                zone='interzone' if row['key']=='manipulate' else 'confrontation')
            if row['key']=='manipulate': s.mark_rules_interzone_entry(item)
            target=self.target(item)
        else:
            pid='p1' if row['key']=='revive' else 'p2'
            s.put_zone_card(pid,row['targetZone'],'destination-probe',owner)
            target={'kind':'zone_card','containerId':pid,'zone':row['targetZone'],'cardId':'destination-probe'}
        return s,item,target,owner

    def begin(self,s,row,target):
        return s.declare_rules_action('p1',row['name'],kind='play_card',source={'cardId':row['cardId'],'zone':'hand'},ability_id=row['abilityId'],targets=[target])

    def outcome(self,s,row,owner):
        if row['destination']=='deck':
            self.assertEqual(s.players[owner]['zones']['deck'],['destination-probe','m2','m4'] if row['position']=='top' else ['m2','m4','destination-probe'])
            self.assertFalse(any(i['cardId']=='destination-probe' for i in s.battlefield))
        elif row['destination']=='receptacle':
            self.assertEqual(s.players['p1']['zones']['receptacle'],['destination-probe'])
            self.assertEqual(s.card_owner_in_zone('p1','receptacle','destination-probe'),owner)
        else:
            items=[i for i in s.battlefield if i['cardId']=='destination-probe']
            self.assertEqual(len(items),1)
            item=items[0]
            self.assertEqual((item['ownerId'],s.rules_item_controller_id(item),s.rules_field_zone(item)),(owner,'p1',row['destination']))
            self.assertEqual(item['counters'],{})
            self.assertFalse(item.get('isSupport'))
            self.assertEqual(s.rules_manifestation_characteristics(item)['power'],3)

    def check_normal(self,row):
        s,item,target,owner=self.setup_case(row)
        self.assertIsNone(self.begin(s,row,target)[0])
        if item: self.assertIn(item,s.battlefield)
        else:self.assertIn('destination-probe',s.players[target['containerId']]['zones'][target['zone']])
        s.resolve_rules_top_action()
        self.outcome(s,row,owner)

    def check_cost(self,row):
        s,_,t,_=self.setup_case(row)
        error,a=self.begin(s,row,t);self.assertIsNone(error)
        spent=Counter()
        for e in a['cost']['essenceSpent']:spent[e['temperament']]+=e['amount']
        self.assertEqual(dict(spent),row['essenceCost'])

    def check_unfunded(self,row):
        s,_,t,_=self.setup_case(row);s.tokens=[];before=self.snapshot(s)
        self.assertIsNotNone(self.begin(s,row,t)[0]);self.assertEqual(self.snapshot(s),before)

    def check_type(self,row):
        for kind in ('persistent_will','ephemeral_will'):
            s,_,t,owner=self.setup_case(row,kind)
            error,_=self.begin(s,row,t)
            if row['key']=='defer':
                self.assertIsNone(error);s.resolve_rules_top_action();self.outcome(s,row,owner)
            else:self.assertIsNotNone(error)

    def check_gone(self,row):
        s,item,t,_=self.setup_case(row);self.assertIsNone(self.begin(s,row,t)[0])
        if item:s._rules_remove_field_item(item,item['ownerId'],'hand')
        else:
            owner=s.card_owner_in_zone(t['containerId'],t['zone'],t['cardId'])
            self.assertIsNone(s.move_zone_card_by_effect(t['containerId'],t['zone'],owner,'hand',t['cardId'],'top')[0])
        s.resolve_rules_top_action()
        self.assertFalse(any(i['cardId']=='destination-probe' for i in s.battlefield))
        self.assertNotIn('destination-probe',s.players['p1']['zones']['receptacle'])
        self.assertTrue(any('destination-probe' in p['zones']['hand'] for p in s.players.values()))

    def check_stale(self,row):
        s,_,t,owner=self.setup_case(row);self.assertIsNone(self.begin(s,row,t)[0])
        pid,zone=t['containerId'],t['zone']
        self.assertIsNone(s.move_zone_card_by_effect(pid,zone,owner,'hand',t['cardId'],'top')[0])
        self.assertIsNone(s.move_zone_card_by_effect(owner,'hand',pid,zone,t['cardId'],'top')[0])
        s.resolve_rules_top_action()
        self.assertIn(t['cardId'],s.players[pid]['zones'][zone])
        self.assertFalse(any(i['cardId']=='destination-probe' for i in s.battlefield))

    def check_old_entry(self,row):
        s,item,t,_=self.setup_case(row)
        if item:item['interzoneTurn']=1
        else:s.rules_engine['zoneEntryTurns'][f"{t['containerId']}:{t['zone']}:{t['cardId']}"]=1
        before=self.snapshot(s);self.assertIsNotNone(self.begin(s,row,t)[0]);self.assertEqual(self.snapshot(s),before)

    def check_protected(self,row):
        s,item,t,_=self.setup_case(row);self.assertIsNone(self.begin(s,row,t)[0])
        s.rules_engine['ongoingEffects'].append({'id':'wall','kind':'protection','target':t,'duration':'until_end_of_turn','startedTurn':2})
        s.resolve_rules_top_action();self.assertIn(item,s.battlefield)

    def check_owner(self,row):
        s,item,t,owner=self.setup_case(row)
        if item and row['key']!='manipulate':
            item['ownerId']='p1';self.assertIsNone(self.begin(s,row,t)[0]);s.resolve_rules_top_action();self.outcome(s,row,'p1')
        elif row['key']=='revive':
            s.move_zone_card_by_effect('p1','graveyard','p1','hand','destination-probe','top')
            s.put_zone_card('p2','graveyard','destination-probe','p2');t.update(containerId='p2',ownerId='p1')
            self.assertIsNotNone(self.begin(s,row,t)[0])
        elif row['key']=='manipulate':
            item['ownerId']='p1';self.assertIsNotNone(self.begin(s,row,t)[0])
        else:
            # Their text requires an opponent's container, even when owners differ.
            s.take_zone_card(t['containerId'],t['zone'],t['cardId'])
            s.put_zone_card('p1',t['zone'],t['cardId'],owner);t['containerId']='p1'
            self.assertIsNotNone(self.begin(s,row,t)[0])

    def check_bob(self,row):
        s,item,t,_=self.setup_case(row)
        self.field(s,'inner-deserts-134','bob',power_bonus=8 if row['destination']=='deck' else 3)
        self.assertIsNone(self.begin(s,row,t)[0]);s.resolve_rules_top_action()
        self.assertTrue(any(e['cardId']=='destination-probe' for e in s.rules_engine['suspendedCards']))
        self.assertFalse(any(i['cardId']=='destination-probe' for i in s.battlefield))
        self.assertFalse(any('destination-probe' in p['zones']['receptacle'] for p in s.players.values()))

    def check_deck_replacement(self,row):
        s,_,t,owner=self.setup_case(row)
        s.create_rules_ongoing_effects(base.base.DiscardDrawClauses().action('Nullify Reason',targets=[{'kind':'player','playerId':owner}],ability_id='nullify-reason-exile-incoming'))
        self.assertIsNone(self.begin(s,row,t)[0]);s.resolve_rules_top_action()
        self.assertIn('destination-probe',s.players[owner]['zones']['exile'])
        self.assertEqual(s.players[owner]['zones']['deck'],['m2','m4'])

    def check_interzone_replacement(self,row):
        s,_,t,owner=self.setup_case(row)
        s.create_rules_ongoing_effects(base.base.DiscardDrawClauses().action('Nullify Reason',targets=[{'kind':'player','playerId':'p1'}],ability_id='nullify-reason-exile-incoming'))
        self.assertIsNone(self.begin(s,row,t)[0]);s.resolve_rules_top_action()
        self.assertIn('destination-probe',s.players[owner]['zones']['exile'])
        self.assertFalse(any(i['cardId']=='destination-probe' for i in s.battlefield))

    def check_interzone_full(self,row):
        s,_,t,_=self.setup_case(row)
        for i in range(3):self.field(s,'m3','full-'+str(i),zone='interzone')
        self.assertIsNone(self.begin(s,row,t)[0]);s.resolve_rules_top_action()
        self.assertIn('destination-probe',s.players['p1']['zones']['graveyard'])
        self.assertFalse(any(i['cardId']=='destination-probe' for i in s.battlefield))

    def check_competing_replacements(self,row):
        for first in ('exile','suspend'):
            s,_,t,_=self.setup_case(row)
            self.field(s,'inner-deserts-134','bob',power_bonus=3)
            s.create_rules_ongoing_effects(base.base.DiscardDrawClauses().action('Nullify Reason',targets=[{'kind':'player','playerId':'p1'}],ability_id='nullify-reason-exile-incoming'))
            self.assertIsNone(self.begin(s,row,t)[0]);s.resolve_rules_top_action()
            choice=s.rules_engine['pendingChoice']
            self.assertEqual(choice['kind'],'replacement_order')
            self.assertIn('destination-probe',s.players['p1']['zones']['graveyard'])
            # The stored order is applied from the end, as in existing replacement tests.
            order=[e['actionId'] for e in sorted(choice['actions'],key=lambda e:e['replacementKind']==first)]
            self.assertIsNone(s.resolve_rules_choice('p1',choice['id'],order)[0])
            self.assertEqual('destination-probe' in s.players['p1']['zones']['exile'],first=='exile')
            self.assertEqual(any(e['cardId']=='destination-probe' for e in s.rules_engine['suspendedCards']),first=='suspend')
            self.assertFalse(any(i['cardId']=='destination-probe' for i in s.battlefield))

    def check_departure_event(self,row):
        for bob in (False,True):
            s,_,t,_=self.setup_case(row)
            if bob:self.field(s,'inner-deserts-134','bob',power_bonus=3)
            self.assertIsNone(self.begin(s,row,t)[0])
            with patch.object(s,'record_rules_observed_event',wraps=s.record_rules_observed_event) as observed:
                s.resolve_rules_top_action()
            exits=[call for call in observed.call_args_list if call.args[0]=='manifestation_left_by_effect' and call.kwargs.get('cardId')=='destination-probe']
            self.assertEqual(len(exits),1)

    def check_ephemeral_on_field(self,row):
        s,item,_,_=self.setup_case(row)
        cid=next(c['id'] for c in main.CARD_DATA if c['name']=='Pray the Ether')
        item['cardId']=cid
        self.assertIsNone(self.begin(s,row,self.target(item))[0])
        s.resolve_rules_top_action()
        self.assertEqual(s.players['p2']['zones']['deck'],[cid,'m2','m4'])
        self.assertIsNone(s.find_battlefield_item(item['id']))

def scenarios(row):
    cases=['normal','cost','unfunded','type','gone','owner']
    if row['targetZone']=='battlefield':cases+=['protected']
    else:cases+=['stale']
    if row['key'] in ('claim','salvage','manipulate'):cases+=['old_entry']
    if row['targetZone']=='graveyard' or row['destination']=='deck':cases+=['bob']
    if row['destination']=='deck':cases+=['deck_replacement']
    if row['key']=='revive':cases+=['interzone_replacement','interzone_full']
    if row['key']=='revive':cases+=['competing_replacements']
    if row['key'] in ('revive','claim'):cases+=['departure_event']
    if row['key']=='defer':cases+=['ephemeral_on_field']
    return cases

def method_name(row,case):return 'test_'+row['key']+'__'+case
for row in CONTRACTS:
    for case in scenarios(row):
        def run(self,row=row,case=case):getattr(self,'check_'+case)(row)
        setattr(ZoneDestinationFamily,method_name(row,case),run)

if __name__=='__main__':unittest.main()
