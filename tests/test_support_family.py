"""Support spells: independently written printed oracles and real declarations.

Confrontation results, creature targets and entry histories are controlled
fixtures. Winning cleanup uses production sequencing. No whole-match claim.
"""
import hashlib
import json
import unittest
from pathlib import Path
from collections import Counter
from unittest.mock import patch
import main
import test_exile_family as base
from session import ADVANCED_PHASES

ROOT=Path(__file__).resolve().parents[1]
CONTRACTS=json.loads((ROOT/'audit/support-family.json').read_text(encoding='utf-8'))['contracts']
for row in CONTRACTS:
    c=next(c for c in main.CARD_DATA if c['id']==row['cardId'])
    assert c['name']==row['name'] and c['effect']==row['printedText']
    assert hashlib.sha256(c['effect'].encode()).hexdigest()==row['printedTextSha256']

class SupportFamily(unittest.TestCase):
    world=base.ExileFamily.world
    field=staticmethod(base.ExileFamily.field)
    put=staticmethod(base.ExileFamily.put)
    target=staticmethod(base.ExileFamily.target)
    snapshot=base.ExileFamily.snapshot

    def setup_case(self,row):
        s=self.world()
        s.card_rules['support-probe']={'type':'manifestation','power':3,'powerCost':'{G}{G}{G}','temperaments':['phlegmatic']}
        s.manifestation_ids.add('support-probe');s.card_points['support-probe']=20
        self.put(s,'p1','hand',[row['cardId']])
        s.add_rules_excess_essence('p1',[{'temperament':c,'amount':30} for c in ('phlegmatic','vitreous','melancholic','choleric','hollow')])
        items=[];targets=[]
        if row['key']=='reforging':
            s.put_zone_card('p2','graveyard','support-probe','p2')
            targets=[{'kind':'zone_card','containerId':'p2','zone':'graveyard','cardId':'support-probe'}]
        else:
            item=self.field(s,'support-probe','probe',zone='interzone' if row['key']=='unite' else 'confrontation')
            items=[item]
            if row['key']=='incinerate':self.enter_support(s,item)
            if row['key'] in ('mirror','persist'):targets=[self.target(item)]
        return s,items,targets

    def begin(self,s,row,targets,**extra):
        return s.declare_rules_action('p1',row['name'],kind='play_card',source={'cardId':row['cardId'],'zone':'hand'},ability_id=row['abilityId'],targets=targets,**extra)

    def enter_support(self,s,item):
        s.mark_rules_support_entry(item)
        s.queue_rules_support_entry_triggers(item,played=False,defer=True)

    def play(self,s,row,targets,**extra):
        error,a=self.begin(s,row,targets,**extra);self.assertIsNone(error)
        self.assertEqual(len(s.rules_engine['actionStack']),1)
        s.resolve_rules_top_action()
        return a

    def copies(self,s):return [i for i in s.battlefield if i.get('isCopy') or i.get('isTokenCard')]

    def assert_tokens(self,s,count):
        copies=self.copies(s);self.assertEqual(len(copies),count)
        for i in copies:
            self.assertTrue(i.get('isSupport'))
            self.assertEqual((i['ownerId'],s.rules_item_controller_id(i),s.rules_field_zone(i)),('p1','p1','confrontation'))
            stats=s.rules_manifestation_characteristics(i)
            self.assertEqual((stats['power'],stats['temperament']),(1,'hollow'))

    def assert_normal(self,s,row,items,targets,extras=0):
        key=row['key']
        if key=='unite':
            self.assertEqual(items[0].get('supportUntilTurn'),2)
            self.assertTrue(s.rules_card_can_enter_support(items[0]))
            self.assertEqual(s.rules_field_zone(items[0]),'interzone','Granting Support does not move the card')
        elif key=='rally':self.assert_tokens(s,extras)
        elif key=='mirror':
            copies=self.copies(s);self.assertEqual(len(copies),1)
            copy=copies[0];self.assertTrue(copy['isTokenCopy']);self.assertEqual(copy['cardId'],'support-probe')
            self.assertEqual((copy['ownerId'],s.rules_item_controller_id(copy),copy['isSupport']),('p1','p1',True))
            stats=s.rules_manifestation_characteristics(copy)
            self.assertEqual((stats['power'],stats['temperament']),(3,'phlegmatic'))
            self.assertIn(items[0],s.battlefield)
        elif key=='reforging':
            restored=next(i for i in s.battlefield if i['cardId']=='support-probe')
            self.assertEqual((restored['ownerId'],s.rules_item_controller_id(restored),s.rules_field_zone(restored)),('p2','p1','confrontation'))
            self.assertTrue(restored['isSupport']);self.assertEqual(restored.get('supportWinDestination'),'exile')
            self.assertEqual(s.players['p2']['zones']['graveyard'],[])
        elif key=='persist':
            self.assertTrue(s.rules_item_has_persist(items[0]))
            self.assertEqual(s.rules_manifestation_characteristics(items[0])['power'],3)
        else:
            self.assertNotIn(items[0],s.battlefield)
            self.assertIn('support-probe',s.players['p1']['zones']['graveyard'])

    def check_normal(self,row):
        s,items,t=self.setup_case(row)
        self.play(s,row,t,**({'extra_essence_count':2} if row['key']=='rally' else {}))
        self.assert_normal(s,row,items,t,2)

    def check_cost(self,row):
        s,items,t=self.setup_case(row);error,a=self.begin(s,row,t);self.assertIsNone(error)
        spent=Counter()
        for e in a['cost']['essenceSpent']:spent[e['temperament']]+=e['amount']
        self.assertEqual(dict(spent),row['essenceCost'])
        self.assertEqual(self.copies(s),[])
        if row['key']=='persist':self.assertFalse(s.rules_item_has_persist(items[0]))
        if row['key']=='unite':self.assertFalse(s.rules_card_can_enter_support(items[0]))
        if items:self.assertIn(items[0],s.battlefield)
        else:self.assertIn('support-probe',s.players['p2']['zones']['graveyard'])

    def check_unfunded(self,row):
        s,_,t=self.setup_case(row);s.tokens=[];before=self.snapshot(s)
        self.assertIsNotNone(self.begin(s,row,t)[0]);self.assertEqual(self.snapshot(s),before)

    def check_neutralized(self,row):
        s,items,t=self.setup_case(row);self.assertIsNone(self.begin(s,row,t)[0])
        action=s.rules_engine['actionStack'].pop()
        s.neutralize_rules_action_source(action)
        self.assertEqual(self.copies(s),[])
        if items:self.assertIn(items[0],s.battlefield)
        else:self.assertIn('support-probe',s.players['p2']['zones']['graveyard'])
        if row['key']=='unite':self.assertFalse(s.rules_card_can_enter_support(items[0]))
        if row['key']=='persist':self.assertFalse(s.rules_item_has_persist(items[0]))

    def check_gone(self,row):
        s,items,t=self.setup_case(row);self.assertIsNone(self.begin(s,row,t)[0])
        if items:s._rules_remove_field_item(items[0],items[0]['ownerId'],'hand')
        else:s.move_zone_card_by_effect('p2','graveyard','p2','hand','support-probe','top')
        s.resolve_rules_top_action();self.assertEqual(self.copies(s),[])
        self.assertFalse(any(i['cardId']=='support-probe' for i in s.battlefield))

    def check_invalid(self,row):
        for how in ('type','zone','protection'):
            s,items,t=self.setup_case(row)
            if how=='type':s.card_rules['support-probe']['type']='persistent_will'
            elif how=='zone':
                if items:items[0]['fieldZone']='stalemate'
                else:t[0]['zone']='deck'
            elif items:s.rules_engine['ongoingEffects'].append({'id':'protected','kind':'protection','target':t[0],'duration':'until_end_of_turn','startedTurn':2,'fromOpponents':False})
            else:continue
            # Own Protection does not prohibit its controller's targeting.
            if how=='protection':
                items[0]['ownerId']='p2';items[0]['controllerId']='p2'
            before=self.snapshot(s);self.assertIsNotNone(self.begin(s,row,t)[0],how);self.assertEqual(self.snapshot(s),before)

    def check_late_protection(self,row):
        s,items,t=self.setup_case(row);self.assertIsNone(self.begin(s,row,t)[0])
        items[0]['controllerId']='p2'
        s.rules_engine['ongoingEffects'].append({'id':'protected','kind':'protection','target':t[0],'duration':'until_end_of_turn','startedTurn':2})
        s.resolve_rules_top_action();self.assertIn(items[0],s.battlefield)
        self.assertEqual(self.copies(s),[])
        if row['key']=='persist':self.assertFalse(s.rules_item_has_persist(items[0]))

    def check_controller(self,row):
        s,items,t=self.setup_case(row);items[0]['ownerId']='p2'
        self.play(s,row,t);self.assert_normal(s,row,items,t)

    def check_stale(self,row):
        s,_,t=self.setup_case(row);self.assertIsNone(self.begin(s,row,t)[0])
        s.move_zone_card_by_effect('p2','graveyard','p2','hand','support-probe','top')
        s.move_zone_card_by_effect('p2','hand','p2','graveyard','support-probe','top')
        s.resolve_rules_top_action();self.assertIn('support-probe',s.players['p2']['zones']['graveyard'])
        self.assertFalse(any(i['cardId']=='support-probe' for i in s.battlefield))

    def check_bob(self,row):
        s,items,t=self.setup_case(row);self.field(s,'inner-deserts-134','bob',power_bonus=3)
        self.play(s,row,t)
        self.assertTrue(any(e['cardId']=='support-probe' for e in s.rules_engine['suspendedCards']))
        self.assertFalse(any(i['cardId']=='support-probe' for i in s.battlefield))

    def check_departure(self,row):
        for bob in (False,True):
            s,_,t=self.setup_case(row)
            if bob:self.field(s,'inner-deserts-134','bob',power_bonus=3)
            self.assertIsNone(self.begin(s,row,t)[0])
            with patch.object(s,'record_rules_observed_event',wraps=s.record_rules_observed_event) as observed:s.resolve_rules_top_action()
            self.assertEqual(sum(c.args[0]=='manifestation_left_by_effect' and c.kwargs.get('cardId')=='support-probe' for c in observed.call_args_list),1)

    def check_entry_watchers(self,row):
        s,items,t=self.setup_case(row)
        blossom=self.field(s,'5liq0tcj7m9ebqr_en','blossom',zone='interzone')
        self.play(s,row,t,**({'extra_essence_count':2} if row['key']=='rally' else {}))
        self.assertEqual(blossom['counters'].get('Petal',0),0,'The triggered effect must still resolve on the Stack')
        choice=s.rules_engine.get('pendingChoice')
        if choice:
            self.assertEqual(choice['kind'],'simultaneous_stack_order')
            self.assertIsNone(s.resolve_rules_choice(choice['playerId'],choice['id'],[a['actionId'] for a in choice['actions']])[0])
        self.assertEqual(len(s.rules_engine['actionStack']),2 if row['key']=='rally' else 1)
        while s.rules_engine['actionStack']:s.resolve_rules_top_action()
        self.assertEqual(blossom['counters'].get('Petal',0),2 if row['key']=='rally' else 1)

    def check_lock(self,row):
        s,items,t=self.setup_case(row)
        self.assertIsNone(self.begin(s,row,t,**({'extra_essence_count':2} if row['key']=='rally' else {}))[0])
        s.rules_engine['supportLocks']=[{'turn':2,'playerId':'p1'}]
        s.resolve_rules_top_action();self.assertEqual(self.copies(s),[])
        if row['key']=='reforging':self.assertIn('support-probe',s.players['p2']['zones']['graveyard'])

    def check_play_only_lock(self,row):
        s,items,t=self.setup_case(row)
        s.rules_engine['supportLocks']=[{'turn':2,'playerId':'p1','playOnly':True}]
        self.play(s,row,t,**({'extra_essence_count':2} if row['key']=='rally' else {}))
        self.assert_normal(s,row,items,t,2)

    def check_rally_counts(self,row):
        for count in (0,1,3,21):
            s,_,t=self.setup_case(row);self.play(s,row,t,extra_essence_count=count);self.assert_tokens(s,count)

    def check_rally_unpaid_extra(self,row):
        s,_,t=self.setup_case(row);s.tokens=[tok for tok in s.tokens if tok['temperament']=='phlegmatic'];s.tokens[0]['counters']['essence']=2
        before=self.snapshot(s);self.assertIsNotNone(self.begin(s,row,t,extra_essence_count=1)[0]);self.assertEqual(self.snapshot(s),before)

    def check_rally_surplus(self,row):
        s,_,t=self.setup_case(row);s.tokens=[]
        s.card_rules['support-probe']['power']=5;s.card_rules['support-probe']['powerCost']='{G}'*5
        self.put(s,'p1','hand',[row['cardId'],'support-probe'])
        a=self.play(s,row,t,payment_card_ids=['support-probe'],extra_essence_count=3)
        self.assertEqual(a['cost']['optionalExtraEssenceSpent'],3)
        self.assertEqual(a['cost']['excessEssence'],[]);self.assert_tokens(s,3)

    def check_rally_extra_tribute(self,row):
        s,_,t=self.setup_case(row);self.put(s,'p1','hand',[row['cardId'],'support-probe'])
        self.play(s,row,t,extra_payment_card_ids=['support-probe'],extra_essence_count=2)
        self.assert_tokens(s,5);self.assertIn('support-probe',s.players['p1']['zones']['graveyard'])

    def check_unite_scope(self,row):
        s,items,t=self.setup_case(row)
        opponent=self.field(s,'support-probe','opponent',owner='p2',zone='interzone')
        front=self.field(s,'support-probe','front')
        self.play(s,row,t)
        self.assertTrue(s.rules_card_can_enter_support(items[0]))
        self.assertNotIn('supportUntilTurn',opponent);self.assertNotIn('supportUntilTurn',front)
        later=self.field(s,'support-probe','later',zone='interzone')
        self.assertFalse(s.rules_card_can_enter_support(later))
        s.phase_tracker['turn']=3;s.prune_rules_ongoing_effects()
        self.assertFalse(s.rules_card_can_enter_support(items[0]))

    def check_unite_resolution_scope(self,row):
        s,items,t=self.setup_case(row);self.assertIsNone(self.begin(s,row,t)[0])
        items[0]['fieldZone']='confrontation'
        new=self.field(s,'support-probe','new',zone='interzone')
        s.resolve_rules_top_action();self.assertNotIn('supportUntilTurn',items[0]);self.assertEqual(new.get('supportUntilTurn'),2)

    def cleanup(self,s,owned,won=True):
        s.phase_tracker['index']=ADVANCED_PHASES.index('resolution_compare')
        owned['fieldZone']='confrontation'
        opponent=self.field(s,'m2' if won else 'm4','cleanup-opponent',owner='p2')
        if not won:opponent['counters']['power']=10
        result=s.prepare_rules_confrontation_result();self.assertEqual(result['winnerId'],'p1' if won else 'p2')
        s.begin_rules_confrontation_cleanup()
        return result

    def check_persist_win(self,row):
        s,items,t=self.setup_case(row);self.play(s,row,t);self.cleanup(s,items[0])
        self.assertIn(items[0],s.battlefield);self.assertTrue(items[0].get('persistedFirst'))
        s.reset_rules_confrontation_turn();self.assertEqual(s.rules_engine['firstManifestationItemIds'].get('p1'),items[0]['id'])

    def check_persist_loss(self,row):
        s,items,t=self.setup_case(row);self.play(s,row,t);self.cleanup(s,items[0],False)
        self.assertNotIn(items[0],s.battlefield);self.assertIn('support-probe',s.players['p2']['zones']['receptacle'])

    def check_persist_expiry(self,row):
        s,items,t=self.setup_case(row);self.play(s,row,t);s.phase_tracker['turn']=3;s.prune_rules_ongoing_effects()
        self.assertFalse(s.rules_item_has_persist(items[0]))

    def reforged(self,row):
        s,_,t=self.setup_case(row);self.play(s,row,t)
        return s,next(i for i in s.battlefield if i['cardId']=='support-probe')

    def check_reforging_win(self,row):
        s,item=self.reforged(row);self.cleanup(s,item)
        self.assertNotIn(item,s.battlefield);self.assertIn('support-probe',s.players['p2']['zones']['exile'])

    def check_reforging_cleanse(self,row):
        s,_,t=self.setup_case(row)
        s.move_zone_card_by_effect('p2','graveyard','p2','hand','support-probe','top')
        s.put_zone_card('p1','graveyard','support-probe','p1');t[0]['containerId']='p1'
        self.play(s,row,t);item=next(i for i in s.battlefield if i['cardId']=='support-probe')
        action=base.base.DiscardDrawClauses().action('Cleanse',targets=[self.target(item)])
        s.rules_engine['actionStack']=[action];s.resolve_rules_top_action();self.cleanup(s,item)
        self.assertNotIn(item,s.battlefield);self.assertIn('support-probe',s.players['p1']['zones']['exile'])

    def check_reforging_memory(self,row):
        s,item=self.reforged(row)
        memories=s.rules_effect_memories_for('p2','support-probe','win_destination_exile')
        self.assertEqual(len(memories),1);self.assertEqual(memories[0]['data']['itemId'],item['id'])

    def check_incinerate_history(self,row):
        s,items,t=self.setup_case(row)
        old=self.field(s,'m2','old');self.enter_support(s,old)
        s.rules_engine['supportEntries']=[{**e,'turn':1} if e['itemId']=='old' else e for e in s.rules_engine['supportEntries']]
        ordinary=self.field(s,'m4','ordinary')
        returned=self.field(s,'m3','returned',owner='p2');self.enter_support(s,returned);returned.update(fieldZone='interzone',isSupport=False)
        self.play(s,row,t)
        self.assertIn(old,s.battlefield);self.assertIn(ordinary,s.battlefield);self.assertNotIn(returned,s.battlefield)
        self.assertNotIn(items[0],s.battlefield)

    def check_incinerate_stalemate(self,row):
        s,items,t=self.setup_case(row);items[0]['fieldZone']='stalemate';self.play(s,row,t);self.assertIn(items[0],s.battlefield)

    def check_incinerate_protection(self,row):
        s,items,t=self.setup_case(row)
        items[0].update(ownerId='p2',controllerId='p2')
        s.rules_engine['ongoingEffects'].append({'id':'wall','kind':'protection','target':self.target(items[0]),'duration':'until_end_of_turn','startedTurn':2})
        self.play(s,row,t);self.assertNotIn(items[0],s.battlefield)

    def check_incinerate_immunity(self,row):
        for pid in ('p1','p2'):
            s,items,t=self.setup_case(row);items[0].update(ownerId=pid,controllerId=pid)
            s.rules_engine['ongoingEffects'].append({'id':'immune','kind':'immune','target':self.target(items[0]),'duration':'until_end_of_turn','startedTurn':2})
            self.play(s,row,t);self.assertIn(items[0],s.battlefield)

    def check_incinerate_tokens(self,row):
        s,_,t=self.setup_case(row)
        token=s.create_rules_token_copy(None,'p2',generic_power=1,hollow=True)
        copy=s.create_rules_token_copy('support-probe','p1')
        for item in (token,copy):s.queue_rules_support_entry_triggers(item,played=False,defer=True)
        self.play(s,row,t)
        self.assertNotIn(token,s.battlefield);self.assertNotIn(copy,s.battlefield)
        self.assertNotIn('support-probe',s.players['p2']['zones']['graveyard'])

    def check_token_family_routes(self,row):
        routes=[('Buuz, the Helicoidal','create-phlegmatic-support-token-on-entry',1,0),
            ('Atavic Welcome','spend-unions-for-support-tokens',2,0),
            ('Jija, Matron Bomb','create-hollow-tokens-for-target-interzone',1,0),
            ('Mamelath, the Polymancer','mamelath-first-manifestations-become-tokens',3,2),
            ('Horned Augustus','horned-augustus-exiles-limbo-for-tokens',1,0),
            ('Recall the Consumed','exile-limbos-create-hollow-copies',1,1),
            ('Lilitha, the Dismemberer','lilitha-dismembers-confrontation-manifestation',0,3),
            ('Stampeding Brood','stampeding-brood-creates-interzone-tokens',2,0)]
        for name,ability,n1,n2 in routes:
            with self.subTest(route=name):
                s,items,_=self.setup_case(row)
                blossoms=[self.field(s,'5liq0tcj7m9ebqr_en','blossom-'+p,owner=p,zone='field') for p in ('p1','p2')]
                targets=[]
                if name=='Jija, Matron Bomb':
                    self.field(s,'m2','in-iz',zone='interzone');targets=[{'kind':'player','playerId':'p1'}]
                if name=='Mamelath, the Polymancer':
                    opponent=self.field(s,'m2','opponent',owner='p2')
                    s.rules_engine['firstManifestationItemIds']={'p1':items[0]['id'],'p2':opponent['id']}
                if name in ('Horned Augustus','Recall the Consumed'):
                    s.put_zone_card('p1','graveyard','support-probe','p1')
                    if name=='Recall the Consumed':s.put_zone_card('p2','graveyard','m2','p2')
                    else:targets=[{'kind':'zone_card','containerId':'p1','zone':'graveyard','cardId':'support-probe','ownerId':'p1'}]
                if name=='Lilitha, the Dismemberer':
                    items[0].update(ownerId='p2',controllerId='p2');targets=[self.target(items[0])]
                action=base.base.DiscardDrawClauses().action(name,targets=targets,ability_id=ability)
                s.rules_engine['actionStack']=[action];s.resolve_rules_top_action()
                if name=='Stampeding Brood':
                    choice=s.rules_engine['pendingChoice'];self.assertEqual(choice['kind'],'token_count')
                    self.assertIsNone(s.resolve_rules_choice('p1',choice['id'],option='2')[0])
                choice=s.rules_engine.get('pendingChoice')
                while choice:
                    self.assertEqual(choice['kind'],'simultaneous_stack_order')
                    self.assertIsNone(s.resolve_rules_choice(choice['playerId'],choice['id'],[a['actionId'] for a in choice['actions']])[0])
                    choice=s.rules_engine.get('pendingChoice')
                while s.rules_engine['actionStack']:s.resolve_rules_top_action()
                self.assertEqual([b['counters'].get('Petal',0) for b in blossoms],[n1,n2])
                created=self.copies(s)
                self.assertEqual(len(created),n1+n2)
                entries=[e for e in s.rules_engine['supportEntries'] if e['itemId'] in {i['id'] for i in created}]
                self.assertEqual(len(entries),0 if name=='Stampeding Brood' else n1+n2)

    def check_no_targets(self,row):
        s,_,_=self.setup_case(row);before=self.snapshot(s)
        self.assertIsNotNone(self.begin(s,row,[])[0]);self.assertEqual(self.snapshot(s),before)

    def check_empty_field(self,row):
        s,_,t=self.setup_case(row);s.battlefield=[];s.rules_engine['supportEntries']=[]
        self.play(s,row,t);self.assertEqual(s.battlefield,[]);self.assertIsNone(s.rules_engine.get('pendingChoice'))

    def check_control_changed(self,row):
        s,items,t=self.setup_case(row);self.assertIsNone(self.begin(s,row,t)[0]);items[0]['controllerId']='p2'
        s.resolve_rules_top_action();self.assertEqual(self.copies(s),[])

    def check_memory_personal_zones(self,row):
        for zone in ('hand','graveyard','deck','exile'):
            with self.subTest(zone=zone):
                s,item=self.reforged(row);s._rules_remove_field_item(item,'p2',zone)
                memories=s.rules_effect_memories_for('p2','support-probe','win_destination_exile')
                self.assertEqual(len(memories),1 if zone in ('hand','graveyard') else 0)
                if zone=='hand':
                    restored=s.place_rules_card_in_interzone('p2','p2','hand','support-probe')
                    self.assertIsNotNone(restored);self.assertEqual(memories[0]['data']['itemId'],restored['id'])

    def check_persist_cleanse(self,row):
        s,items,t=self.setup_case(row);self.play(s,row,t)
        a=base.base.DiscardDrawClauses().action('Cleanse',targets=[self.target(items[0])])
        s.rules_engine['actionStack']=[a];s.resolve_rules_top_action();self.assertFalse(s.rules_item_has_persist(items[0]))

    def check_rally_then_incinerate(self,row):
        s,_,t=self.setup_case(row);self.play(s,row,t,extra_essence_count=2)
        tokens=self.copies(s);incin=next(r for r in CONTRACTS if r['key']=='incinerate')
        self.put(s,'p1','hand',[incin['cardId']]);s.rules_engine['priorityPlayerId']='p1';self.play(s,incin,[])
        self.assertTrue(all(i not in s.battlefield for i in tokens))

def scenarios(row):
    cases=['normal','cost','unfunded','neutralized']
    if row['key'] in ('mirror','reforging','persist'):cases+=['gone','invalid','no_targets']
    if row['key'] in ('mirror','persist'):cases+=['late_protection']
    if row['key']=='mirror':cases+=['controller','control_changed']
    if row['key']=='reforging':cases+=['stale','bob','departure','reforging_win','reforging_cleanse','reforging_memory','memory_personal_zones']
    if row['key'] in ('mirror','reforging','rally'):cases+=['entry_watchers','lock','play_only_lock']
    if row['key']=='rally':cases+=['rally_counts','rally_unpaid_extra','rally_surplus','rally_extra_tribute','token_family_routes','rally_then_incinerate']
    if row['key']=='unite':cases+=['unite_scope','unite_resolution_scope']
    if row['key']=='persist':cases+=['persist_win','persist_loss','persist_expiry','persist_cleanse']
    if row['key']=='incinerate':cases+=['incinerate_history','incinerate_stalemate','incinerate_protection','incinerate_immunity','incinerate_tokens','bob']
    if row['key'] in ('unite','incinerate'):cases+=['empty_field']
    return cases

def method_name(row,case):return 'test_'+row['key']+'__'+case
for row in CONTRACTS:
    for case in scenarios(row):
        def run(self,row=row,case=case):getattr(self,'check_'+case)(row)
        setattr(SupportFamily,method_name(row,case),run)

if __name__=='__main__':unittest.main()
