"""Literal oracles for real Stack response cards; pending originals are controlled fixtures."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from collections import Counter
import main
import test_bounce_replay_clauses as fixtures

ROOT=Path(__file__).resolve().parents[1]
ALL_CONTRACTS=json.loads((ROOT/'audit/stack-interactions.json').read_text(encoding='utf-8'))['contracts']
CONTRACTS=[r for r in ALL_CONTRACTS if r['mode'] in ('play','activate')]
for row in ALL_CONTRACTS:
    card=next(c for c in main.CARD_DATA if c['id']==row['cardId'])
    assert card['name']==row['name'] and card['effect']==row['printedText']
    assert hashlib.sha256(card['effect'].encode()).hexdigest()==row['printedTextSha256']
    assert all(c in card['effect'] for c in row['selectedClauses'])


class StackInteractionFamily(unittest.TestCase):
    world=fixtures.BounceReplayClauses.world
    field=staticmethod(fixtures.BounceReplayClauses.field)
    put=staticmethod(fixtures.BounceReplayClauses.put)
    cid=staticmethod(fixtures.BounceReplayClauses.cid)
    field_target=staticmethod(fixtures.BounceReplayClauses.target)
    snapshot=fixtures.BounceReplayClauses.snapshot
    action=fixtures.BounceReplayClauses.action

    def power(self,s,item):return s.rules_manifestation_characteristics(item)['power']
    def pool(self,s,pid):
        pool=Counter()
        for t in s.tokens:
            if t.get('isEssence') and t.get('ownerId')==pid:pool[t['temperament']]+=t['counters']['essence']
        return dict(pool)

    def original(self,s,kind='ephemeral',controller='p2',owner='p2'):
        if kind=='effect':
            cid='effect-probe'
            s.card_rules[cid]={'type':'manifestation','power':4,'temperaments':['choleric']}
            s.manifestation_ids.add(cid)
            self.field(s,cid,'effect-source',owner=owner,controller=controller)
            ability={'id':'probe-effect','targets':{'min':1,'max':1,'cardType':'manifestation'},
                     'ongoingEffect':{'kind':'power_modifier','value':2,'duration':'until_end_of_turn'}}
            source={'cardId':cid,'itemId':'effect-source','zone':'battlefield','ownerId':owner}
        else:
            cid=self.cid('Hermetic Hourglass' if kind=='persistent' else 'Wind Sprout' if kind=='manifestation' else 'Strengthen')
            ability=copy.deepcopy(main.CARD_ABILITIES[cid][0]) if kind=='ephemeral' else None
            source={'cardId':cid,'zone':'hand','ownerId':owner,'cardType':s.card_rules[cid]['type']}
        targets=[{'kind':'card','itemId':'original-target','cardId':'m4'}] if kind in ('ephemeral','effect') else []
        action={'id':'original','controllerId':controller,'label':'Original fixture',
                'kind':'activated_effect' if kind=='effect' else 'play_card','source':source,
                'sourceOnStack':kind!='effect','targets':targets,'ability':ability,
                'cost':{'tributeRequirements':{},'essenceSpent':[]},'turn':2,'phaseId':'confrontation_reaction'}
        if kind=='manifestation':action['asSupport']=True
        return action

    def setup_case(self,row):
        s=self.world()
        self.field(s,'m4','original-target')
        self.field(s,'m3','new-target')
        kind='effect' if row['targetKind']=='stack_effect' else 'persistent' if row['outcome']=='refund' else 'ephemeral'
        original=self.original(s,kind,controller='p1' if row['key']=='malaleuco' else 'p2',owner='p1' if row['key']=='malaleuco' else 'p2')
        s.rules_engine['actionStack']=[original]
        host=None
        if row['mode']=='play':self.put(s,'p1','hand',[row['cardId']])
        else:
            host=self.field(s,row['cardId'],'responder',zone='interzone' if row['key']=='malaleuco' else 'field')
            if row['counterCost']:host['counters'][row['counterCost']['name']]=3
            if row['key']=='radiance':host['chosenTemperament']='choleric'
        s.add_rules_excess_essence('p1',[{'temperament':c,'amount':30} for c in ('hollow','capricious','vitreous','phlegmatic','choleric','melancholic')])
        return s,host,original

    def targets(self,row,original):
        targets=[{'kind':'stack_effect' if original['kind']!='play_card' or original.get('sourceRemainsOnField') else 'stack_action',
                  'actionId':original['id'],'cardId':original['source']['cardId']}]
        if row['key']=='beacon':targets.append({'kind':'card','itemId':'new-target','cardId':'m3'})
        return targets

    def declaration(self,row,host,original):
        return {'kind':'play_card' if row['mode']=='play' else 'activated_effect',
                'source':{'cardId':row['cardId'],'zone':'hand' if host is None else 'battlefield',
                          **({'itemId':host['id']} if host else {})},
                'ability_id':row['abilityId'],'targets':self.targets(row,original)}

    def begin(self,s,row,host,original):return s.declare_rules_action('p1',row['name'],**self.declaration(row,host,original))

    def resolve_response(self,s,row):
        result=s.resolve_rules_top_action()
        if row['outcome'] in ('pay_neutralize','pay_cancel'):
            choice=s.rules_engine['pendingChoice']
            self.assertEqual(choice['kind'],'stack_counter_payment')
            self.assertIsNone(s.resolve_rules_choice(choice['playerId'],choice['id'],option='decline')[0])
        return result

    def assert_outcome(self,s,row,original):
        outcome=row['outcome']
        if outcome in ('neutralize','pay_neutralize','pay_cancel','cancel','return','refund'):
            self.assertNotIn(original,s.rules_engine['actionStack'])
            if original['kind']=='play_card':
                destination='hand' if outcome=='return' else 'graveyard'
                self.assertEqual(s.players[original['source']['ownerId']]['zones'][destination].count(original['source']['cardId']),1)
            else:self.assertIsNotNone(s.find_battlefield_item('effect-source'))
            if outcome=='refund':self.assertEqual(self.pool(s,'p2'),{'vitreous':2,'capricious':2})
            self.assertEqual(self.power(s,s.find_battlefield_item('original-target')),4)
        elif outcome=='copy':
            choice=s.rules_engine['pendingChoice']
            self.assertEqual(choice['kind'],'stack_copy_targets')
            self.assertIsNone(s.resolve_rules_choice('p1',choice['id'],option='retarget',
                targets=[{'kind':'card','itemId':'new-target','cardId':'m3'}])[0])
            copied=s.rules_engine['actionStack'][-1]
            self.assertTrue(copied['isStackCopy']);self.assertEqual(copied['controllerId'],'p1')
            self.assertEqual(copied['cost']['tributeRequirements'],{})
            self.assertEqual(original['targets'][0]['itemId'],'original-target')
            self.assertEqual(self.power(s,s.find_battlefield_item('new-target')),3)
            s.resolve_rules_top_action()
            self.assertEqual(self.power(s,s.find_battlefield_item('new-target')),6)
            self.assertEqual(self.power(s,s.find_battlefield_item('original-target')),4)
            self.assertNotIn(original['source']['cardId'],s.players[original['source']['ownerId']]['zones']['graveyard'])
            s.resolve_rules_top_action()
            self.assertEqual(self.power(s,s.find_battlefield_item('original-target')),7)
            self.assertEqual(s.players[original['source']['ownerId']]['zones']['graveyard'].count(original['source']['cardId']),1)
        elif outcome=='retarget':
            self.assertEqual(original['targets'][0]['itemId'],'new-target')
            s.resolve_rules_top_action()
            self.assertEqual(self.power(s,s.find_battlefield_item('new-target')),6)
            self.assertEqual(self.power(s,s.find_battlefield_item('original-target')),4)
        elif outcome=='protect':
            self.assertTrue(s.rules_stack_action_is_protected(original,'p1'))
            self.assertTrue(s.rules_stack_action_is_protected(original,'p2'))
            s.resolve_rules_top_action()
            self.assertEqual(self.power(s,s.find_battlefield_item('original-target')),7)

    def check_normal(self,row):
        s,host,original=self.setup_case(row)
        self.assertIsNone(self.begin(s,row,host,original)[0])
        self.assertIn(original,s.rules_engine['actionStack'])
        self.assertEqual(self.power(s,s.find_battlefield_item('original-target')),4)
        self.resolve_response(s,row);self.assert_outcome(s,row,original)
        if row['mode']=='play':self.assertEqual(s.players['p1']['zones']['graveyard'].count(row['cardId']),1)

    def check_cost(self,row):
        s,host,original=self.setup_case(row)
        before=sum(self.pool(s,'p1').values())
        error,action=self.begin(s,row,host,original);self.assertIsNone(error)
        self.assertEqual(action['cost']['tributeRequirements'],row['essenceCost'])
        self.assertEqual(sum(self.pool(s,'p1').values()),before-sum(row['essenceCost'].values()))
        if row['counterCost']:
            self.assertEqual(host['counters'][row['counterCost']['name']],2)
        if row['exhaustSource']:self.assertEqual(host['rotation'],90)

    def check_missing(self,row):
        s,host,original=self.setup_case(row);s.rules_engine['actionStack']=[]
        before=self.snapshot(s);self.assertIsNotNone(self.begin(s,row,host,original)[0]);self.assertEqual(self.snapshot(s),before)

    def check_wrong_kind(self,row):
        s,host,original=self.setup_case(row)
        wrong=self.original(s,'ephemeral' if row['targetKind']=='stack_effect' else 'effect')
        if row['key']=='beacon':wrong['targets']=[]
        s.rules_engine['actionStack']=[wrong]
        before=self.snapshot(s);self.assertIsNotNone(self.begin(s,row,host,wrong)[0]);self.assertEqual(self.snapshot(s),before)

    def check_wrong_priority(self,row):
        s,host,original=self.setup_case(row);s.rules_engine['priorityPlayerId']='p2'
        before=self.snapshot(s);self.assertIsNotNone(self.begin(s,row,host,original)[0]);self.assertEqual(self.snapshot(s),before)

    def check_late_missing(self,row):
        s,host,original=self.setup_case(row);self.assertIsNone(self.begin(s,row,host,original)[0])
        s.counter_rules_stack_action(original,'cancel')
        s.resolve_rules_top_action()
        self.assertEqual(s.rules_engine['actionStack'],[]);self.assertIsNone(s.rules_engine['pendingChoice'])
        if row['mode']=='play':self.assertEqual(s.players['p1']['zones']['graveyard'].count(row['cardId']),1)

    def check_late_protection(self,row):
        s,host,original=self.setup_case(row);self.assertIsNone(self.begin(s,row,host,original)[0])
        s.rules_engine['ongoingEffects'].append({'id':'wall','kind':'protection','duration':'until_end_of_turn',
            'startedTurn':2,'target':{'kind':'stack_action','actionId':original['id']}})
        s.resolve_rules_top_action()
        self.assertEqual(s.rules_engine['actionStack'],[original]);self.assertIsNone(s.rules_engine['pendingChoice'])
        self.assertEqual(original['targets'],[] if row['outcome']=='refund' else [{'kind':'card','itemId':'original-target','cardId':'m4'}])

    def check_unfunded(self,row):
        s,host,original=self.setup_case(row);s.tokens=[]
        before=self.snapshot(s);self.assertIsNotNone(self.begin(s,row,host,original)[0]);self.assertEqual(self.snapshot(s),before)

    def check_source_gone(self,row):
        s,host,original=self.setup_case(row);self.assertIsNone(self.begin(s,row,host,original)[0])
        s._rules_remove_field_item_by_effect(host,'p1','graveyard','top',reason='destroy')
        self.resolve_response(s,row);self.assert_outcome(s,row,original)

    def check_bad_source(self,row):
        for change in ('blank','hidden','counter' if row['counterCost'] else 'exhausted'):
            s,host,original=self.setup_case(row)
            if change=='blank':host['effectsDisabled']=True
            elif change=='hidden':host['faceUp']=False
            elif change=='counter':host['counters'][row['counterCost']['name']]=0
            else:host['rotation']=90
            before=self.snapshot(s);self.assertIsNotNone(self.begin(s,row,host,original)[0]);self.assertEqual(self.snapshot(s),before)

    def check_paid_escape(self,row):
        s,host,original=self.setup_case(row)
        s.add_rules_excess_essence('p2',[{'temperament':'hollow','amount':2}])
        self.assertIsNone(self.begin(s,row,host,original)[0]);s.resolve_rules_top_action()
        choice=s.rules_engine['pendingChoice'];self.assertEqual(choice['playerId'],'p2')
        self.assertEqual(choice['requirements'],{'hollow':2})
        self.assertIsNone(s.resolve_rules_choice('p2',choice['id'],option='pay')[0])
        self.assertEqual(sum(self.pool(s,'p2').values()),0)
        self.assertEqual(s.rules_engine['actionStack'],[original])
        before=self.snapshot(s)
        self.assertIsNotNone(s.resolve_rules_choice('p2',choice['id'],option='pay')[0]);self.assertEqual(self.snapshot(s),before)
        s.resolve_rules_top_action()
        self.assertEqual(self.power(s,s.find_battlefield_item('original-target')),6 if row['key']=='ignore' else 7)

    def check_payer(self,row):
        s,host,original=self.setup_case(row)
        original['controllerId']='p1'
        source=s.find_battlefield_item('effect-source')
        if source:source['controllerId']='p1'
        self.assertIsNone(self.begin(s,row,host,original)[0]);s.resolve_rules_top_action()
        choice=s.rules_engine['pendingChoice']
        self.assertEqual(choice['playerId'],'p1' if row['key']=='ignore' else 'p2')
        before=self.snapshot(s)
        wrong='p2' if choice['playerId']=='p1' else 'p1'
        self.assertIsNotNone(s.resolve_rules_choice(wrong,choice['id'],option='decline')[0]);self.assertEqual(self.snapshot(s),before)

    def check_payment_target_gone(self,row):
        s,host,original=self.setup_case(row)
        s.add_rules_excess_essence('p2',[{'temperament':'hollow','amount':2}])
        self.assertIsNone(self.begin(s,row,host,original)[0]);s.resolve_rules_top_action()
        choice=s.rules_engine['pendingChoice'];s.counter_rules_stack_action(original,'cancel')
        before=self.pool(s,'p2')
        self.assertIsNone(s.resolve_rules_choice('p2',choice['id'],option='pay')[0]);self.assertEqual(self.pool(s,'p2'),before)
        self.assertIsNone(s.rules_engine['pendingChoice'])

    def check_manifestation(self,row):
        for in_field in (False,True):
            s,host,original=self.setup_case(row)
            original=self.original(s,'manifestation');s.rules_engine['actionStack']=[original]
            waiting=None
            if in_field:
                cid=self.cid('Forest Guide');waiting=self.field(s,cid,'waiting',owner='p2',zone='interzone')
                waiting['pendingSupportActionId']=original['id']
                original.update(sourceRemainsOnField=True,sourceOnStack=False)
                original['source'].update(cardId=cid,zone='battlefield',itemId='waiting')
            if in_field:
                before=self.snapshot(s)
                self.assertIsNotNone(self.begin(s,row,host,original)[0]);self.assertEqual(self.snapshot(s),before)
                continue
            self.assertIsNone(self.begin(s,row,host,original)[0]);self.resolve_response(s,row)
            self.assertNotIn(original,s.rules_engine['actionStack'])
            if in_field:
                self.assertIn(waiting,s.battlefield);self.assertEqual(waiting['fieldZone'],'interzone')
                self.assertNotIn('pendingSupportActionId',waiting)
                self.assertNotIn(cid,s.players['p2']['zones']['graveyard'])
            else:self.assertIn(original['source']['cardId'],s.players['p2']['zones']['graveyard'])

    def check_wrong_card_type(self,row):
        for kind in (('ephemeral','manifestation') if row['key']=='compensate' else ('manifestation',)):
            s,host,_=self.setup_case(row);wrong=self.original(s,kind);s.rules_engine['actionStack']=[wrong]
            before=self.snapshot(s);self.assertIsNotNone(self.begin(s,row,host,wrong)[0]);self.assertEqual(self.snapshot(s),before)

    def check_support_movement(self,row):
        s,host,_=self.setup_case(row)
        original=self.original(s,'manifestation');cid=self.cid('Forest Guide')
        waiting=self.field(s,cid,'waiting',owner='p2',zone='interzone')
        waiting['pendingSupportActionId']=original['id']
        original.update(sourceRemainsOnField=True,sourceOnStack=False)
        original['source'].update(cardId=cid,zone='battlefield',itemId='waiting')
        s.rules_engine['actionStack']=[original]
        self.assertIsNone(self.begin(s,row,host,original)[0]);self.resolve_response(s,row)
        self.assertEqual(s.rules_engine['actionStack'],[])
        self.assertIn(waiting,s.battlefield);self.assertEqual(waiting['fieldZone'],'interzone')
        self.assertNotIn('pendingSupportActionId',waiting)
        self.assertNotIn(cid,s.players['p2']['zones']['graveyard'])

    def check_unneutralizable(self,row):
        s,host,original=self.setup_case(row);original['cannotBeNeutralized']=True
        self.assertIsNone(self.begin(s,row,host,original)[0]);self.resolve_response(s,row)
        self.assertEqual(s.rules_engine['actionStack'],[original])
        self.assertEqual(self.pool(s,'p2'),{})
        self.assertNotIn(original['source']['cardId'],s.players['p2']['zones']['graveyard'])
        self.assertNotIn(original['source']['cardId'],s.players['p2']['zones']['hand'])

    def check_copy_keep(self,row):
        s,host,original=self.setup_case(row);self.assertIsNone(self.begin(s,row,host,original)[0]);s.resolve_rules_top_action()
        choice=s.rules_engine['pendingChoice']
        self.assertIsNone(s.resolve_rules_choice('p1',choice['id'],option='keep')[0])
        s.resolve_rules_top_action();self.assertEqual(self.power(s,s.find_battlefield_item('original-target')),7)
        self.assertEqual(s.rules_engine['actionStack'],[original])
        s.resolve_rules_top_action();self.assertEqual(self.power(s,s.find_battlefield_item('original-target')),10)

    def check_copy_countered(self,row):
        s,host,original=self.setup_case(row);self.assertIsNone(self.begin(s,row,host,original)[0]);s.resolve_rules_top_action()
        choice=s.rules_engine['pendingChoice'];self.assertIsNone(s.resolve_rules_choice('p1',choice['id'],option='keep')[0])
        copied=s.rules_engine['actionStack'][-1]
        self.assertEqual(s.counter_rules_stack_action(copied,'neutralize')['status'],'neutralized')
        self.assertNotIn(original['source']['cardId'],s.players[original['source']['ownerId']]['zones']['graveyard'])
        self.assertEqual(s.rules_engine['actionStack'],[original])

    def check_retarget_effect(self,row):
        s,host,_=self.setup_case(row);original=self.original(s,'effect');s.rules_engine['actionStack']=[original]
        self.assertIsNone(self.begin(s,row,host,original)[0]);s.resolve_rules_top_action()
        self.assertEqual(original['targets'][0]['itemId'],'new-target')
        s.resolve_rules_top_action();self.assertEqual(self.power(s,s.find_battlefield_item('new-target')),5)

    def check_invalid_retarget(self,row):
        s,host,original=self.setup_case(row)
        s.find_battlefield_item('new-target')['cardId']='pw3'
        args=self.declaration(row,host,original);args['targets'][1]['cardId']='pw3'
        before=self.snapshot(s)
        self.assertIsNotNone(s.declare_rules_action('p1',row['name'],**args)[0]);self.assertEqual(self.snapshot(s),before)

    def check_radiance_conditions(self,row):
        for condition in ('color','controller','field_target'):
            s,host,original=self.setup_case(row)
            if condition=='color':host['chosenTemperament']='vitreous'
            elif condition=='controller':original['controllerId']='p1'
            else:s.find_battlefield_item('original-target')['controllerId']='p2'
            before=self.snapshot(s);self.assertIsNotNone(self.begin(s,row,host,original)[0]);self.assertEqual(self.snapshot(s),before)

    def check_radiance_snapshot(self,row):
        s,host,original=self.setup_case(row);error,action=self.begin(s,row,host,original);self.assertIsNone(error)
        self.assertEqual(action['ability']['targets']['sourceChosenTemperament'],'choleric')
        # Existing-source revalidation still observes its current chosen color.
        host['chosenTemperament']='vitreous';s.resolve_rules_top_action()
        self.assertEqual(s.rules_engine['actionStack'],[original])

    def check_wall_field_and_expiry(self,row):
        s,host,original=self.setup_case(row)
        args=self.declaration(row,host,original);args['targets']=[{'kind':'card','itemId':'original-target','cardId':'m4'}]
        self.assertIsNone(s.declare_rules_action('p1',row['name'],**args)[0]);s.resolve_rules_top_action()
        target=s.find_battlefield_item('original-target')
        for pid in ('p1','p2'):self.assertTrue(s.rules_item_is_protected(target,pid))
        s.phase_tracker['turn']=3;s.prune_rules_ongoing_effects()
        for pid in ('p1','p2'):self.assertFalse(s.rules_item_is_protected(target,pid))

    def check_wall_transfer(self,row):
        s,host,_=self.setup_case(row);original=self.original(s,'persistent');s.rules_engine['actionStack']=[original]
        self.assertIsNone(self.begin(s,row,host,original)[0]);s.resolve_rules_top_action();s.resolve_rules_top_action()
        target=next(i for i in s.battlefield if i['cardId']==original['source']['cardId'])
        for pid in ('p1','p2'):self.assertTrue(s.rules_item_is_protected(target,pid))
        s.phase_tracker['turn']=3;s.prune_rules_ongoing_effects()
        for pid in ('p1','p2'):self.assertFalse(s.rules_item_is_protected(target,pid))

    def check_exile_override(self,row):
        s,host,original=self.setup_case(row);original['source']['exileOnLeave']=True
        self.assertIsNone(self.begin(s,row,host,original)[0]);s.resolve_rules_top_action()
        self.assertIn(original['source']['cardId'],s.players['p2']['zones']['exile'])
        self.assertNotIn(original['source']['cardId'],s.players['p2']['zones']['hand'])

    def check_copied_target(self,row):
        s,host,original=self.setup_case(row)
        if row['key']=='ignore':
            original=self.original(s,'ephemeral')
        creator='p1' if row['key']=='malaleuco' else 'p2'
        original['source']['ownerId']='p2' if creator=='p1' else 'p1'
        copied=s.build_rules_stack_copy(original,creator,'copy-producer')
        self.assertEqual(copied['source']['ownerId'],creator)
        self.assertNotEqual(original['source']['ownerId'],creator)
        s.rules_engine['actionStack']=[original,copied]
        if row['key']=='ignore':
            before=self.snapshot(s)
            self.assertIsNotNone(self.begin(s,row,host,copied)[0]);self.assertEqual(self.snapshot(s),before)
            return
        self.assertIsNone(self.begin(s,row,host,copied)[0])
        s.resolve_rules_top_action()
        if row['key']=='deny':
            choice=s.rules_engine['pendingChoice'];self.assertEqual(choice['playerId'],creator)
            self.assertIsNone(s.resolve_rules_choice(creator,choice['id'],option='decline')[0])
        elif row['outcome']=='copy':
            choice=s.rules_engine['pendingChoice']
            self.assertIsNone(s.resolve_rules_choice('p1',choice['id'],option='keep')[0])
            newest=s.rules_engine['actionStack'][-1]
            self.assertEqual(newest['source']['ownerId'],'p1');self.assertTrue(newest['isStackCopy'])
            self.assertEqual(newest['copiedFromActionId'],copied['id'])
        elif row['key']=='wall':
            self.assertTrue(s.rules_stack_action_is_protected(copied,'p1'))
        elif row['key']=='beacon':self.assertEqual(copied['targets'][0]['itemId'],'new-target')
        else:
            self.assertNotIn(copied,s.rules_engine['actionStack']);self.assertIn(original,s.rules_engine['actionStack'])
        if row['key']=='compensate':self.assertEqual(self.pool(s,'p2'),{'vitreous':2,'capricious':2})
        for pid in ('p1','p2'):
            for zone in ('hand','graveyard','exile'):
                self.assertNotIn(original['source']['cardId'],s.players[pid]['zones'][zone])

    def check_persistent_copy_enters(self,row):
        s,host,_=self.setup_case(row)
        original=self.original(s,'persistent',controller='p1' if row['key']=='malaleuco' else 'p2')
        s.rules_engine['actionStack']=[original]
        self.assertIsNone(self.begin(s,row,host,original)[0]);s.resolve_rules_top_action()
        self.assertIsNone(s.rules_engine['pendingChoice'])
        copied=s.rules_engine['actionStack'][-1];self.assertTrue(copied['isStackCopy'])
        s.resolve_rules_top_action()
        token=next(i for i in s.battlefield if i['cardId']==original['source']['cardId'])
        self.assertTrue(token['isTokenCopy']);self.assertEqual(token['ownerId'],'p1')
        self.assertEqual(token['controllerId'],'p1');self.assertEqual(s.rules_field_zone(token),'field')
        self.assertIn(original,s.rules_engine['actionStack'])
        s._rules_remove_field_item_by_effect(token,'p1','graveyard','top',reason='destroy')
        self.assertNotIn(original['source']['cardId'],s.players['p1']['zones']['graveyard'])

    def check_persistent_copy_etb(self,row):
        s,host,_=self.setup_case(row)
        original=self.original(s,'persistent',controller='p1' if row['key']=='malaleuco' else 'p2')
        original['source']['cardId']=self.cid('Scrambling Beacon')
        s.rules_engine['actionStack']=[original]
        self.assertIsNone(self.begin(s,row,host,original)[0]);s.resolve_rules_top_action();s.resolve_rules_top_action()
        token=next(i for i in s.battlefield if i.get('isTokenCopy'))
        while s.rules_engine['actionStack'][-1] is not original:s.resolve_rules_top_action()
        self.assertEqual(token['counters'],{'Lucore':3})

    def check_copy_does_not_reserve_hand(self,row):
        s,host,original=self.setup_case(row)
        copied=s.build_rules_stack_copy(original,'p1','copy');s.rules_engine['actionStack']=[original,copied]
        self.put(s,'p1','hand',[original['source']['cardId']])
        self.assertIsNone(s.rules_source_reservation_error('p1','hand',original['source']['cardId']))

    def check_copied_paid_escape(self,row):
        s,host,original=self.setup_case(row)
        copied=s.build_rules_stack_copy(original,'p2','copy');s.rules_engine['actionStack']=[original,copied]
        s.add_rules_excess_essence('p2',[{'temperament':'hollow','amount':2}])
        self.assertIsNone(self.begin(s,row,host,copied)[0]);s.resolve_rules_top_action()
        choice=s.rules_engine['pendingChoice'];self.assertEqual(choice['playerId'],'p2')
        self.assertIsNone(s.resolve_rules_choice('p2',choice['id'],option='pay')[0])
        self.assertEqual(self.pool(s,'p2'),{});self.assertEqual(s.rules_engine['actionStack'],[original,copied])
        s.resolve_rules_top_action();self.assertEqual(self.power(s,s.find_battlefield_item('original-target')),7)

    def check_copy_counted_as_card(self,row):
        s,_,original=self.setup_case(row)
        original['controllerId']='p2'
        copied=s.build_rules_stack_copy(original,'p2','copy')
        effect=self.original(s,'effect');effect['id']='non-card'
        s.rules_engine['actionStack']=[original,copied,effect]
        host=s.find_battlefield_item('original-target')
        result=s.apply_rules_action_result({'id':'count','controllerId':'p1','source':{'itemId':host['id']},
            'ability':{'result':{'kind':'thoughtcutter_surge'}},'targets':[]})
        self.assertEqual(result['value'],2);self.assertEqual(self.power(s,host),6)


def scenarios(row):
    cases=['normal','cost','missing','wrong_kind','wrong_priority','late_missing','late_protection']
    if row['essenceCost']:cases.append('unfunded')
    if row['mode']=='activate':cases+=['source_gone','bad_source']
    if row['key'] in ('deny','ignore'):cases+=['paid_escape','payer','payment_target_gone']
    if row['key']=='ignore':cases+=['support_movement']
    if row['key'] in ('neutralize','deny'):cases+=['manifestation']
    if row['key'] in ('veer','compensate','imitate','malaleuco'):cases+=['wrong_card_type']
    if row['key'] in ('neutralize','deny','veer','compensate'):cases+=['unneutralizable']
    if row['outcome']=='copy':cases+=['copy_keep','copy_countered']
    if row['key']=='beacon':cases+=['retarget_effect','invalid_retarget']
    if row['key']=='radiance':cases+=['radiance_conditions','radiance_snapshot']
    if row['key']=='wall':cases+=['wall_field_and_expiry','wall_transfer']
    if row['key']=='veer':cases+=['exile_override']
    if row['key']!='radiance':cases+=['copied_target']
    if row['outcome']=='copy':cases+=['persistent_copy_enters','persistent_copy_etb','copy_does_not_reserve_hand','copy_counted_as_card']
    if row['key']=='deny':cases+=['copied_paid_escape']
    return cases
def method_name(row,case):return 'test_'+row['key']+'__'+case
for row in CONTRACTS:
    for case in scenarios(row):
        def run(self,row=row,case=case):getattr(self,'check_'+case)(row)
        setattr(StackInteractionFamily,method_name(row,case),run)
