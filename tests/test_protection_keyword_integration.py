"""Paid entries/activations and response windows on mixed-version sockets."""
import unittest
from unittest.mock import AsyncMock,patch
from session import ADVANCED_PHASES
import test_protection_keyword_family as family
import test_stack_interaction_integration as network


class ProtectionKeywordIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=network.StackInteractionIntegration.asyncSetUp
    asyncTearDown=network.StackInteractionIntegration.asyncTearDown
    join=network.StackInteractionIntegration.join
    receive_until=network.StackInteractionIntegration.receive_until
    send=network.StackInteractionIntegration.send
    prepare_active_rules=network.StackInteractionIntegration.prepare_active_rules
    pass_stack=network.StackInteractionIntegration.pass_stack
    install=network.StackInteractionIntegration.install
    ws=network.StackInteractionIntegration.ws
    state=network.StackInteractionIntegration.state
    resolve_top=network.StackInteractionIntegration.resolve_top
    declare=network.StackInteractionIntegration.declare

    def public(self,row,expected):
        for viewer,state in zip(('p1','p2'),self.last_resolution_states):
            if row['key']=='pillar':
                self.assertTrue(state['players']['p1']['zones']['receptacle']['effectTargetable'])
                continue
            item=next(i for i in state['battlefield'] if i['id']=='target')
            if row['observable']=='protection':self.assertEqual(item['effectTargetable'],viewer=='p1' or not expected)
            elif row['observable']=='blank':self.assertEqual(bool(item.get('effectsInactive')),expected)
            elif row['observable']=='support':self.assertEqual(bool(item.get('canEnterSupport')),expected)
            elif row['observable']=='power':self.assertEqual(item['effectivePower'],2 if expected else 4)
            else:self.assertEqual(any(e['kind']=='grant_float' and e['target'].get('itemId')=='target' for e in state['rulesEngine']['ongoingEffects']),expected)

    async def exercise(self,row):
        f=family.ProtectionKeywordFamily();fixture,source,target,_=f.setup_case(row)
        if row['mode'] in ('link','entry_gift'):
            fixture.battlefield=[i for i in fixture.battlefield if i['id']!='host']
            fixture.phase_tracker['index']=ADVANCED_PHASES.index('end_actions')
            f.put(fixture,'p1','hand',[row['cardId']])
            fixture.add_rules_excess_essence('p1',[{'temperament':c,'amount':n} for c,n in row['playCost'].items()])
        elif row['mode']=='play':fixture.add_rules_excess_essence('p1',[{'temperament':c,'amount':n} for c,n in row['playCost'].items()])
        self.install(fixture);s=self.session
        if row['mode']=='entry_gift':
            await self.declare('p1',row['name'],{'kind':'play_card','source':{'cardId':row['cardId'],'zone':'hand'}},1)
            await self.resolve_top()
            for state in self.last_resolution_states:
                card=next(i for i in state['battlefield'] if i['cardId']==row['cardId'])
                self.assertEqual(card.get('controllerId',card['ownerId']),'p1');self.assertEqual(card.get('counters',{}),{})
            choice=s.rules_engine.get('pendingChoice')
            if choice:
                await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':choice['id'],'targets':[{'kind':'player','playerId':'p2'}]})
                await self.state(self.ws1,lambda m:m['rulesEngine']['pendingChoice'] is None and len(m['rulesEngine']['actionStack'])==1)
            await self.resolve_top()
            for state in self.last_resolution_states:
                card=next(i for i in state['battlefield'] if i['cardId']==row['cardId'])
                self.assertEqual((card['controllerId'],card['ownerId'],card['counters']),('p2','p1',{'Burn':1}))
            return
        if row['mode'] in ('passive','vessel'):
            if row['mode']=='passive':self.assertTrue(f.observed(s,row,s.find_battlefield_item('target')))
            else:self.assertTrue(s.rules_vessel_locked('p1'))
            defer=f.cid('Defer');f.put(s,'p2','hand',[defer]);s.add_rules_excess_essence('p2',[{'temperament':'vitreous','amount':2}])
            s.rules_engine['priorityPlayerId']='p2'
            await self.declare('p2','Defer source',{'kind':'play_card','source':{'cardId':defer,'zone':'hand'},
                'abilityId':'defer-to-deck-top','targets':[f.target(s.find_battlefield_item('host'))]},1)
            await self.resolve_top();self.assertIsNone(s.find_battlefield_item('host'))
            self.assertEqual(s.players['p1']['zones']['deck'][0],row['cardId'])
            self.public(row,False);return
        args={'kind':'play_card' if row['mode'] in ('play','link') else 'activated_effect',
              'source':{'cardId':row['cardId'],'zone':'battlefield' if row['mode']=='sacrifice' else 'hand'}}
        if row['mode']=='sacrifice':args['source']['itemId']='host'
        if row['mode']!='link':
            args.update(abilityId=row['abilityId'],targets=[] if row['key'] in ('protect','gladionimbus') else [f.target(s.find_battlefield_item('target'))])
        await self.declare('p1',row['name'],args,1)
        self.assertFalse(f.observed(s,row,s.find_battlefield_item('target')))
        await self.resolve_top()
        if row['mode']=='link':
            choice=s.rules_engine['pendingChoice'];self.assertEqual(choice['kind'],'trigger_targets')
            await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':choice['id'],'targets':[f.target(s.find_battlefield_item('target'))]})
            await self.state(self.ws1,lambda m:m['rulesEngine']['pendingChoice'] is None and len(m['rulesEngine']['actionStack'])==1)
            self.assertFalse(f.observed(s,row,s.find_battlefield_item('target')))
            await self.resolve_top()
        elif row['key']=='nullify':
            choice=s.rules_engine['pendingChoice']
            await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':choice['id'],'option':'decline'})
            self.last_resolution_states=[]
            for ws in (self.ws1,self.ws2):self.last_resolution_states.append(await self.state(ws,lambda m:m['rulesEngine']['pendingChoice'] is None))
        self.assertTrue(f.observed(s,row,s.find_battlefield_item('target')));self.public(row,True)
        self.assertEqual(s.rules_engine['actionStack'],[])


for row in family.CONTRACTS:
    async def run(self,_driver,row=row):await self.exercise(row)
    setattr(ProtectionKeywordIntegration,'test_'+row['key']+'__websocket',patch('main.auto_advance_rules_phases',new_callable=AsyncMock,return_value=False)(run))
