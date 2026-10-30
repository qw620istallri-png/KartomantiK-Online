"""Literal state/recipient/lifetime oracles for protection and granted keywords."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
import main
from session import ADVANCED_PHASES
import test_bounce_replay_clauses as fixtures

ROOT=Path(__file__).resolve().parents[1]
CONTRACTS=json.loads((ROOT/'audit/protection-keywords.json').read_text(encoding='utf-8'))['contracts']
for row in CONTRACTS:
    card=next(c for c in main.CARD_DATA if c['id']==row['cardId'])
    assert card['effect']==row['printedText']
    assert hashlib.sha256(card['effect'].encode()).hexdigest()==row['printedTextSha256']


class ProtectionKeywordFamily(unittest.TestCase):
    world=fixtures.BounceReplayClauses.world
    field=staticmethod(fixtures.BounceReplayClauses.field)
    put=staticmethod(fixtures.BounceReplayClauses.put)
    cid=staticmethod(fixtures.BounceReplayClauses.cid)
    target=staticmethod(fixtures.BounceReplayClauses.target)
    snapshot=fixtures.BounceReplayClauses.snapshot
    action=fixtures.BounceReplayClauses.action

    def setup_case(self,row):
        s=self.world()
        target=self.field(s,'m4','target',zone='interzone')
        other=self.field(s,'m3','other',zone='interzone')
        source=None
        if row['mode'] in ('link','passive','vessel','sacrifice','entry_gift'):
            zone='interzone' if row['key'] in ('rajas','gladionimbus') else 'confrontation' if row['key']=='sanctuary' else 'field'
            source=self.field(s,row['cardId'],'host',zone=zone)
        if row['key']=='sanctuary':target['fieldZone']='confrontation'
        if row['mode'] in ('play','hand'):self.put(s,'p1','hand',[row['cardId']])
        if row['key']=='pillar':
            self.put(s,'p1','receptacle',[self.cid('Haltan, the Favored')])
            s.players['p1']['zoneOwners']['receptacle'][self.cid('Haltan, the Favored')]='p2'
        return s,source,target,other

    def observed(self,s,row,item):
        kind=row['observable']
        if kind=='protection':return s.rules_item_is_protected(item,'p2')
        if kind=='support':return s.rules_card_can_enter_support(item)
        if kind=='blank':return not s.rules_item_effects_active(item)
        if kind=='float':return s.rules_item_has_float(item)
        if kind=='power':return s.rules_manifestation_characteristics(item)['power']==2
        raise AssertionError(kind)

    def cleanse(self,s,item):return s.apply_rules_action_result(self.action('Cleanse',targets=[self.target(item)]))

    def enter(self,row):
        s,source,target,other=self.setup_case(row)
        self.assertFalse(self.observed(s,row,target))
        queued=s.queue_rules_battlefield_entry_triggers(row['cardId'],'p1',source['id'],True,event_targets=[self.target(target)])
        self.assertEqual(len(queued),1,'The printed entry must create exactly one trigger')
        self.assertEqual(s.rules_engine['actionStack'],queued)
        self.assertFalse(self.observed(s,row,target))
        s.resolve_rules_top_action();self.assertTrue(self.observed(s,row,target))
        return s,source,target,other

    def check_link_entry(self,row):
        s,source,target,other=self.enter(row)
        self.assertFalse(self.observed(s,row,other))
        self.assertEqual(s.rules_engine['actionStack'],[])
        self.assertEqual(len(s.rules_engine['ongoingEffects']),1)
        if row['key']=='husk':self.assertFalse(s.rules_item_is_protected(target,'p1'))

    def check_link_cleanse(self,row):
        s,source,target,_=self.enter(row);self.cleanse(s,target)
        self.assertFalse(self.observed(s,row,target))
        for _ in range(3):s.prune_rules_ongoing_effects();self.assertFalse(self.observed(s,row,target))
        self.assertEqual(s.rules_engine['actionStack'],[])

    def check_link_dormant(self,row):
        for key,value in (('effectsDisabled',True),('faceUp',False)):
            s,source,target,_=self.enter(row);source[key]=value
            self.assertFalse(self.observed(s,row,target))
            source[key]=False if key=='effectsDisabled' else True
            self.assertTrue(self.observed(s,row,target));self.assertEqual(s.rules_engine['actionStack'],[])

    def check_link_source_cleanse(self,row):
        s,source,target,_=self.enter(row);source['effectsDisabled']=True
        self.assertFalse(self.observed(s,row,target));self.cleanse(s,source)
        self.assertTrue(self.observed(s,row,target));self.assertEqual(s.rules_engine['actionStack'],[])

    def check_link_source_left(self,row):
        s,source,target,_=self.enter(row)
        s._rules_remove_field_item_by_effect(source,'p1','graveyard','top',reason='destroy')
        s.prune_rules_ongoing_effects();self.assertFalse(self.observed(s,row,target))
        self.field(s,row['cardId'],'replacement',zone='field')
        self.assertFalse(self.observed(s,row,target))

    def check_link_target_left(self,row):
        s,_,target,_=self.enter(row)
        s._rules_remove_field_item_by_effect(target,'p1','hand','top',reason='return')
        s.prune_rules_ongoing_effects()
        fresh=self.field(s,'m4','fresh',zone='interzone')
        self.assertFalse(self.observed(s,row,fresh))

    def check_link_stalemate(self,row):
        s,_,target,_=self.enter(row)
        s.rules_stalemate_item(target['id']);s.prune_rules_ongoing_effects()
        self.assertFalse(any(e.get('target',{}).get('itemId')==target['id'] for e in s.rules_engine['ongoingEffects']))

    def retarget(self,s,row,source,target):
        s.phase_tracker['index']=ADVANCED_PHASES.index('end_actions');s.rules_engine['priorityPlayerId']='p1'
        s.add_rules_excess_essence('p1',[{'temperament':c,'amount':n} for c,n in row['activationCost'].items()])
        return s.declare_rules_action('p1','Retarget',kind='activated_effect',
            source={'cardId':row['cardId'],'itemId':source['id'],'zone':'battlefield'},
            ability_id=row['retargetAbilityId'],targets=[self.target(target)])

    def check_link_retarget(self,row):
        s,source,old,new=self.enter(row)
        error,action=self.retarget(s,row,source,new);self.assertIsNone(error)
        self.assertEqual(action['cost']['tributeRequirements'],row['activationCost']);self.assertEqual(source['rotation'],90)
        self.assertTrue(self.observed(s,row,old));self.assertFalse(self.observed(s,row,new))
        s.resolve_rules_top_action();self.assertFalse(self.observed(s,row,old))
        if row['key']=='jaw':self.assertEqual(s.rules_manifestation_characteristics(new)['power'],1)
        else:self.assertTrue(self.observed(s,row,new))
        self.assertEqual(len(s.rules_engine['ongoingEffects']),1)

    def check_link_reapply_after_cleanse(self,row):
        s,source,target,_=self.enter(row);self.cleanse(s,target)
        self.assertIsNone(self.retarget(s,row,source,target)[0]);s.resolve_rules_top_action()
        self.assertTrue(self.observed(s,row,target))

    def check_link_wrong_phase(self,row):
        s,source,_,new=self.enter(row)
        s.add_rules_excess_essence('p1',[{'temperament':c,'amount':n} for c,n in row['activationCost'].items()])
        before=self.snapshot(s)
        error,_=s.declare_rules_action('p1','Retarget',kind='activated_effect',source={'cardId':row['cardId'],'itemId':source['id'],'zone':'battlefield'},ability_id=row['retargetAbilityId'],targets=[self.target(new)])
        self.assertIsNotNone(error);self.assertEqual(self.snapshot(s),before)

    def check_link_source_missing_at_resolution(self,row):
        s,source,old,new=self.enter(row);self.assertIsNone(self.retarget(s,row,source,new)[0])
        s._rules_remove_field_item_by_effect(source,'p1','graveyard','top',reason='destroy');s.prune_rules_ongoing_effects()
        s.resolve_rules_top_action();self.assertFalse(self.observed(s,row,old));self.assertFalse(self.observed(s,row,new))

    def check_link_invalid_late_target(self,row):
        s,source,old,new=self.enter(row);self.assertIsNone(self.retarget(s,row,source,new)[0])
        s._rules_remove_field_item_by_effect(new,'p1','hand','top',reason='return');s.resolve_rules_top_action()
        self.assertTrue(self.observed(s,row,old));self.assertEqual(source['rotation'],90)

    def check_link_token_entry(self,row):
        s,_,target,_=self.setup_case(row);s.battlefield=[i for i in s.battlefield if i['id']!='host']
        token=s.create_rules_token_copy(row['cardId'],'p1')
        triggers=s.queue_rules_token_copy_entry_triggers(token,defer=True)
        self.assertEqual(len(triggers),1)
        # Entry selection uses the normal trigger target UI after the batch is queued.
        s.queue_rules_simultaneous_actions(triggers)
        choice=s.rules_engine['pendingChoice'];self.assertEqual(choice['kind'],'trigger_targets')
        self.assertIsNone(s.resolve_rules_choice('p1',choice['id'],targets=[self.target(target)])[0])
        s.resolve_rules_top_action();self.assertTrue(self.observed(s,row,target))

    def check_link_paid_entry(self,row):
        s,_,target,_=self.setup_case(row);s.battlefield=[i for i in s.battlefield if i['id']!='host']
        s.phase_tracker['index']=ADVANCED_PHASES.index('end_actions')
        self.put(s,'p1','hand',[row['cardId']]);s.add_rules_excess_essence('p1',[{'temperament':c,'amount':n} for c,n in row['playCost'].items()])
        error,action=s.declare_rules_action('p1',row['name'],kind='play_card',source={'cardId':row['cardId'],'zone':'hand'})
        self.assertIsNone(error);self.assertEqual(action['cost']['tributeRequirements'],row['playCost'])
        self.assertFalse(self.observed(s,row,target));s.resolve_rules_top_action()
        self.assertFalse(self.observed(s,row,target))
        choice=s.rules_engine['pendingChoice'];self.assertEqual(choice['kind'],'trigger_targets')
        self.assertIsNone(s.resolve_rules_choice('p1',choice['id'],targets=[self.target(target)])[0])
        self.assertFalse(self.observed(s,row,target));s.resolve_rules_top_action()
        self.assertTrue(self.observed(s,row,target));self.assertEqual(len(s.rules_engine['ongoingEffects']),1)

    def check_link_unfunded(self,row):
        s,source,_,new=self.enter(row);s.phase_tracker['index']=ADVANCED_PHASES.index('end_actions')
        before=self.snapshot(s)
        error,_=s.declare_rules_action('p1','Retarget',kind='activated_effect',source={'cardId':row['cardId'],'itemId':source['id'],'zone':'battlefield'},ability_id=row['retargetAbilityId'],targets=[self.target(new)])
        self.assertIsNotNone(error);self.assertEqual(self.snapshot(s),before)

    def check_link_late_protection(self,row):
        s,source,old,new=self.enter(row);self.assertIsNone(self.retarget(s,row,source,new)[0])
        s.rules_engine['ongoingEffects'].append({'id':'late-wall','kind':'protection','target':self.target(new),'duration':'until_end_of_turn','startedTurn':2})
        s.resolve_rules_top_action();self.assertTrue(self.observed(s,row,old))
        self.assertEqual(source['rotation'],90)
        self.assertTrue(s.rules_item_effects_active(new));self.assertEqual(s.rules_manifestation_characteristics(new)['power'],3)

    def declaration(self,s,row,source,target):
        if row['mode']=='play':
            s.add_rules_excess_essence('p1',[{'temperament':c,'amount':n} for c,n in row['playCost'].items()])
        return s.declare_rules_action('p1',row['name'],kind='play_card' if row['mode']=='play' else 'activated_effect',
            source={'cardId':row['cardId'],'zone':'hand' if row['mode'] in ('play','hand') else 'battlefield',
                    **({'itemId':source['id']} if source else {})},ability_id=row['abilityId'],
            targets=[] if row['key'] in ('protect','gladionimbus') else [self.target(target)])

    def apply(self,row,option='decline'):
        s,source,target,other=self.setup_case(row)
        error,action=self.declaration(s,row,source,target);self.assertIsNone(error)
        self.assertFalse(self.observed(s,row,target));s.resolve_rules_top_action()
        if row['key']=='nullify':
            choice=s.rules_engine['pendingChoice'];self.assertEqual(choice['kind'],'effect_payment')
            self.assertEqual(choice['playerId'],'p1');self.assertEqual(choice['requirements'],{'hollow':2})
            if option=='pay':s.add_rules_excess_essence('p1',[{'temperament':'hollow','amount':2}])
            self.assertIsNone(s.resolve_rules_choice('p1',choice['id'],option=option)[0])
        return s,source,target,other,action

    def check_grant_normal(self,row):
        s,source,target,other,action=self.apply(row)
        self.assertTrue(self.observed(s,row,target))
        self.assertEqual(action['cost']['tributeRequirements'],row['playCost'] if row['mode']=='play' else {})
        if row['key'] in ('protect','gladionimbus'):self.assertTrue(self.observed(s,row,other))
        else:self.assertFalse(self.observed(s,row,other))
        if row['mode']=='play':self.assertIn(row['cardId'],s.players['p1']['zones']['graveyard'])
        if row['key']=='bivalv':self.assertIn(row['cardId'],s.players['p1']['zones']['graveyard'])
        if row['key']=='gladionimbus':self.assertIsNone(s.find_battlefield_item('host'))

    def check_grant_cleanse(self,row):
        s,_,target,_,_=self.apply(row);self.cleanse(s,target)
        self.assertFalse(self.observed(s,row,target));s.prune_rules_ongoing_effects()
        self.assertFalse(self.observed(s,row,target))

    def check_grant_lifetime(self,row):
        s,_,target,_,_=self.apply(row);self.assertTrue(self.observed(s,row,target))
        s.phase_tracker['turn']=3;s.prune_rules_ongoing_effects()
        self.assertEqual(self.observed(s,row,target),row['key'] not in ('protect','bivalv'))

    def check_grant_snapshot(self,row):
        s,_,target,_,_=self.apply(row)
        new=self.field(s,'m3','later',zone='interzone')
        self.assertFalse(self.observed(s,row,new))
        if row['key']=='gladionimbus':
            target['fieldZone']='confrontation';self.assertTrue(s.rules_item_has_float(target))

    def check_grant_target_returned(self,row):
        s,_,target,_,_=self.apply(row)
        s._rules_remove_field_item_by_effect(target,'p1','hand','top',reason='return');s.prune_rules_ongoing_effects()
        fresh=self.field(s,'m4','fresh',zone='interzone');self.assertFalse(self.observed(s,row,fresh))

    def check_grant_resolution_recipients(self,row):
        s,source,target,_=self.setup_case(row)
        foe=self.field(s,'m3','foe',owner='p2',zone='interzone')
        stale=self.field(s,'m3','stale',zone='stalemate')
        will=self.field(s,'pw3','will',zone='field')
        self.assertIsNone(self.declaration(s,row,source,target)[0])
        late=self.field(s,'m3','before-resolution',zone='interzone')
        s.resolve_rules_top_action()
        self.assertTrue(self.observed(s,row,late));self.assertFalse(self.observed(s,row,foe))
        self.assertFalse(self.observed(s,row,stale))
        self.assertEqual(s.rules_item_is_protected(will,'p2'),row['key']=='protect')

    def check_grant_blanking(self,row):
        s,_,target,_,_=self.apply(row);target['effectsDisabled']=True
        self.assertEqual(self.observed(s,row,target),row['observable']=='protection')
        target.pop('effectsDisabled');self.assertTrue(self.observed(s,row,target))

    def check_nullify_pay(self,row):
        s,_,target,_,_=self.apply(row,option='pay');self.assertTrue(s.rules_item_effects_active(target))
        self.assertEqual(sum(t.get('counters',{}).get('essence',0) for t in s.tokens if t.get('isEssence')),0)

    def check_nullify_owner(self,row):
        s,source,target,_=self.setup_case(row);target.update(ownerId='p2',controllerId='p1')
        self.assertIsNone(self.declaration(s,row,source,target)[0]);s.resolve_rules_top_action()
        choice=s.rules_engine['pendingChoice'];self.assertEqual(choice['playerId'],'p2')
        before=self.snapshot(s);self.assertIsNotNone(s.resolve_rules_choice('p1',choice['id'],option='decline')[0]);self.assertEqual(self.snapshot(s),before)

    def check_nullify_persistent(self,row):
        s,source,target,_=self.setup_case(row);target.update(cardId='pw3',fieldZone='field')
        self.assertIsNone(self.declaration(s,row,source,target)[0]);s.resolve_rules_top_action()
        choice=s.rules_engine['pendingChoice'];self.assertIsNone(s.resolve_rules_choice('p1',choice['id'],option='decline')[0])
        self.assertFalse(s.rules_item_effects_active(target))

    def check_passive_normal(self,row):
        s,source,target,other=self.setup_case(row)
        self.assertTrue(self.observed(s,row,target));self.assertFalse(s.rules_item_is_protected(target,'p1'))
        self.assertFalse(self.observed(s,row,source))
        self.assertEqual(s.rules_engine['actionStack'],[]);self.assertEqual(s.rules_engine['ongoingEffects'],[])

    def check_passive_source_states(self,row):
        for change in ('hidden','blank','stalemate','gone'):
            s,source,target,_=self.setup_case(row)
            if change=='hidden':source['faceUp']=False
            elif change=='blank':source['effectsDisabled']=True
            elif change=='stalemate':s.rules_stalemate_item(source['id'])
            else:s._rules_remove_field_item_by_effect(source,'p1','graveyard','top',reason='destroy')
            self.assertFalse(self.observed(s,row,target))

    def check_passive_recipients(self,row):
        s,_,target,_=self.setup_case(row)
        target['controllerId']='p2';self.assertFalse(s.rules_item_is_protected(target,'p1'))
        target['controllerId']='p1';target['ownerId']='p2';self.assertTrue(self.observed(s,row,target))
        target['fieldZone']='stalemate';self.assertFalse(self.observed(s,row,target))

    def check_passive_cleanse(self,row):
        s,_,target,_=self.setup_case(row);self.cleanse(s,target)
        self.assertTrue(self.observed(s,row,target));self.assertEqual(s.rules_engine['ongoingEffects'],[])

    def check_passive_current_control(self,row):
        s,source,target,_=self.setup_case(row);source['controllerId']='p2'
        self.assertFalse(self.observed(s,row,target))
        target['controllerId']='p2';self.assertTrue(s.rules_item_is_protected(target,'p1'))

    def check_passive_late_arrival(self,row):
        s,_,_,_=self.setup_case(row)
        new=self.field(s,'m3','new',zone='confrontation' if row['key']=='sanctuary' else 'interzone')
        self.assertTrue(self.observed(s,row,new))

    def check_rajas_wills(self,row):
        s,_,target,_=self.setup_case(row);target.update(cardId='pw3',fieldZone='field')
        self.assertTrue(self.observed(s,row,target));target['fieldZone']='stalemate'
        self.assertFalse(self.observed(s,row,target))

    def check_pillar_normal(self,row):
        s,_,_,_=self.setup_case(row)
        self.assertTrue(s.rules_vessel_locked('p1'));self.assertFalse(s.rules_vessel_locked('p2'))
        self.assertEqual(s.rules_engine['ongoingEffects'],[])

    def check_pillar_source(self,row):
        for change in ('blank','hidden','stalemate','control','gone'):
            s,source,_,_=self.setup_case(row)
            if change=='blank':source['effectsDisabled']=True
            elif change=='hidden':source['faceUp']=False
            elif change=='stalemate':s.rules_stalemate_item(source['id'])
            elif change=='control':source['controllerId']='p2'
            else:s._rules_remove_field_item_by_effect(source,'p1','graveyard','top',reason='destroy')
            self.assertFalse(s.rules_vessel_locked('p1'))
            if change=='control':self.assertTrue(s.rules_vessel_locked('p2'))

    def check_pillar_targeting(self,row):
        s,source,_,_=self.setup_case(row);cid=self.cid('Haltan, the Favored')
        target={'kind':'zone_card','zone':'receptacle','containerId':'p1','ownerId':'p2','cardId':cid}
        rules={'kind':'zone_card','zones':['receptacle'],'min':1,'max':1,'cardType':'manifestation'}
        self.assertIsNotNone(s.rules_ability_targets_error(rules,[target],'p2'))
        self.assertIsNone(s.rules_ability_targets_error(rules,[target],'p1'))
        source['effectsDisabled']=True;self.assertIsNone(s.rules_ability_targets_error(rules,[target],'p2'))

    def check_pillar_suppresses_vessel_triggers(self,row):
        s,source,_,_=self.setup_case(row);cid=self.cid('Graceful Petal')
        self.put(s,'p1','receptacle',[cid]);s.players['p1']['zoneOwners']['receptacle'][cid]='p2'
        self.assertEqual(s.queue_rules_triggers(cid,'p2','enters_zone',zone='receptacle',container_id='p1',controller_id='p2',defer=True),[])
        source['effectsDisabled']=True
        self.assertEqual(len(s.queue_rules_triggers(cid,'p2','enters_zone',zone='receptacle',container_id='p1',controller_id='p2',defer=True)),1)

    def gift_trigger(self,row):
        s,host,_,_=self.setup_case(row)
        actions=s.queue_rules_battlefield_entry_triggers(row['cardId'],'p1',host['id'],True,event_targets=[{'kind':'player','playerId':'p2'}])
        self.assertEqual(len(actions),1)
        self.assertEqual(host['controllerId'],'p1');self.assertEqual(host['counters'],{})
        return s,host,actions[0]

    def check_gift_entry(self,row):
        s,host,_=self.gift_trigger(row);s.resolve_rules_top_action()
        self.assertEqual((host['controllerId'],host['ownerId'],host['counters']),('p2','p1',{'Burn':1}))

    def check_gift_source_left(self,row):
        s,host,_=self.gift_trigger(row)
        s._rules_remove_field_item_by_effect(host,'p1','graveyard','top',reason='destroy');s.resolve_rules_top_action()
        self.assertEqual(s.battlefield[0]['id'],'target')
        self.assertEqual(s.players['p1']['zones']['graveyard'].count(row['cardId']),1)

    def check_gift_cancel(self,row):
        s,host,action=self.gift_trigger(row);s.counter_rules_stack_action(action,'cancel')
        self.assertIn(host,s.battlefield);self.assertEqual(host['controllerId'],'p1');self.assertEqual(host['counters'],{})

    def check_gift_hidden(self,row):
        s,host,_,_=self.setup_case(row);host['faceUp']=False
        self.assertEqual(s.queue_rules_battlefield_entry_triggers(row['cardId'],'p1',host['id'],False),[])

    def resolve_gift_target(self,s):
        choice=s.rules_engine.get('pendingChoice')
        if choice:
            self.assertEqual(choice['kind'],'trigger_targets')
            self.assertIsNone(s.resolve_rules_choice('p1',choice['id'],targets=[{'kind':'player','playerId':'p2'}])[0])
        self.assertEqual(s.rules_engine['actionStack'][-1]['targets'],[{'kind':'player','playerId':'p2'}])
        s.resolve_rules_top_action()

    def check_gift_token_entry(self,row):
        s,_,_,_=self.setup_case(row);s.battlefield=[i for i in s.battlefield if i['id']!='host']
        host=s.create_rules_token_copy(row['cardId'],'p1');triggers=s.queue_rules_token_copy_entry_triggers(host,defer=True)
        self.assertEqual(len(triggers),1);s.queue_rules_simultaneous_actions(triggers);self.resolve_gift_target(s)
        self.assertEqual((host['controllerId'],host['ownerId'],host['counters']),('p2','p1',{'Burn':1}))

    def check_gift_paid_entry(self,row):
        s,_,_,_=self.setup_case(row);s.battlefield=[i for i in s.battlefield if i['id']!='host']
        s.phase_tracker['index']=ADVANCED_PHASES.index('end_actions')
        self.put(s,'p1','hand',[row['cardId']]);s.add_rules_excess_essence('p1',[{'temperament':'capricious','amount':2}])
        error,action=s.declare_rules_action('p1',row['name'],kind='play_card',source={'cardId':row['cardId'],'zone':'hand'})
        self.assertIsNone(error);self.assertEqual(action['cost']['tributeRequirements'],{'capricious':2})
        s.resolve_rules_top_action();host=next(i for i in s.battlefield if i['cardId']==row['cardId'])
        self.assertEqual(host['controllerId'],'p1');self.assertEqual(host['counters'],{})
        self.resolve_gift_target(s);self.assertEqual((host['controllerId'],host['ownerId'],host['counters']),('p2','p1',{'Burn':1}))

    def check_gift_opponent_only(self,row):
        s,_,_,_=self.setup_case(row);rules={'kind':'player','min':1,'max':1,'controller':'opponent'}
        self.assertIsNotNone(s.rules_ability_targets_error(rules,[{'kind':'player','playerId':'p1'}],'p1'))
        self.assertIsNone(s.rules_ability_targets_error(rules,[{'kind':'player','playerId':'p2'}],'p1'))


def scenarios(row):
    if row['mode']=='entry_gift':return ['gift_entry','gift_source_left','gift_cancel','gift_hidden','gift_token_entry','gift_paid_entry','gift_opponent_only']
    if row['mode']=='link':return ['link_entry','link_cleanse','link_dormant','link_source_cleanse','link_source_left','link_target_left','link_stalemate','link_retarget','link_reapply_after_cleanse','link_wrong_phase','link_source_missing_at_resolution','link_invalid_late_target','link_token_entry','link_paid_entry','link_unfunded','link_late_protection']
    if row['mode']=='passive':return ['passive_normal','passive_source_states','passive_recipients','passive_cleanse','passive_current_control','passive_late_arrival']+(['rajas_wills'] if row['key']=='rajas' else [])
    if row['mode']=='vessel':return ['pillar_normal','pillar_source','pillar_targeting','pillar_suppresses_vessel_triggers']
    return ['grant_normal','grant_cleanse','grant_lifetime','grant_snapshot','grant_target_returned']+(['nullify_pay','nullify_owner','nullify_persistent'] if row['key']=='nullify' else ['grant_blanking'])+(['grant_resolution_recipients'] if row['key'] in ('protect','gladionimbus') else [])

for row in CONTRACTS:
    for case in scenarios(row):
        def run(self,row=row,case=case):getattr(self,'check_'+case)(row)
        setattr(ProtectionKeywordFamily,'test_'+row['key']+'__'+case,run)
