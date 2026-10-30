"""Real response declarations, choices and priority over mixed-version sockets."""
import copy
import unittest
from unittest.mock import AsyncMock,patch
import test_state_transport_integration as transport
import test_bounce_replay_integration as passes
import test_stack_interaction_family as family
from session import ADVANCED_PHASES


class StackInteractionIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=transport.StateTransportIntegration.asyncSetUp
    asyncTearDown=transport.StateTransportIntegration.asyncTearDown
    join=transport.StateTransportIntegration.join
    receive_until=transport.StateTransportIntegration.receive_until
    send=transport.StateTransportIntegration.send
    prepare_active_rules=transport.StateTransportIntegration.prepare_active_rules
    pass_stack=passes.BounceReplayIntegration.pass_stack

    def install(self,fixture):
        self.prepare_active_rules('confrontation_reaction')
        for attr in ('card_rules','card_points','manifestation_ids','players','battlefield','tokens','rules_engine','phase_tracker'):
            setattr(self.session,attr,copy.deepcopy(getattr(fixture,attr)))

    def ws(self,pid):return self.ws1 if pid=='p1' else self.ws2

    async def state(self,ws,predicate):
        message=await self.receive_until(ws,lambda m:m.get('type')=='error' or m.get('type')=='state' and predicate(m))
        self.assertEqual(message['type'],'state',message)
        return message

    async def resolve_top(self):
        s=self.session;action_id=s.rules_engine['actionStack'][-1]['id']
        first=self.ws(s.rules_engine['priorityPlayerId']);second=self.ws2 if first is self.ws1 else self.ws1
        await self.pass_stack(first,second)
        result=None
        self.last_resolution_states=[]
        for ws in (self.ws1,self.ws2):
            result=await self.state(ws,lambda m:any(e.get('type')=='rules_action_resolved' and e.get('details',{}).get('actionId')==action_id for e in m.get('recentLog',[])))
            self.last_resolution_states.append(result)
        return result

    async def orders(self,original_id=None):
        s=self.session
        while (s.rules_engine.get('pendingChoice') or {}).get('kind')=='simultaneous_stack_order':
            choice=s.rules_engine['pendingChoice'];ids=[a['actionId'] for a in choice['actions']]
            if original_id in ids:ids=[original_id]+[i for i in ids if i!=original_id]
            await self.send(self.ws(choice['playerId']),{'type':'resolve_rules_choice','choiceId':choice['id'],'cardIds':ids})
            await self.state(self.ws(choice['playerId']),lambda m:(m['rulesEngine'].get('pendingChoice') or {}).get('id')!=choice['id'])

    async def declare(self,pid,label,args,stack_size):
        payload={**args}
        if 'ability_id' in payload:payload['abilityId']=payload.pop('ability_id')
        if 'payment_card_ids' in payload:payload['paymentCardIds']=payload.pop('payment_card_ids')
        await self.send(self.ws(pid),{'type':'declare_rules_action','label':label,**payload})
        return await self.state(self.ws(pid),lambda m:len(m['rulesEngine']['actionStack'])==stack_size or
            (m['rulesEngine'].get('pendingChoice') or {}).get('kind')=='simultaneous_stack_order')

    async def exercise(self,row,source_gone=False):
        f=family.StackInteractionFamily();fixture,host,original=f.setup_case(row);self.install(fixture)
        s=self.session;host=s.find_battlefield_item(host['id']) if host else None
        original=s.rules_engine['actionStack'][0]
        await self.declare('p1',row['name'],f.declaration(row,host,original),2)
        self.assertEqual(f.power(s,s.find_battlefield_item('original-target')),4)
        if source_gone:
            defer=f.cid('Defer');f.put(s,'p2','hand',[defer])
            s.add_rules_excess_essence('p2',[{'temperament':'vitreous','amount':2}])
            await self.declare('p2','Defer',{'kind':'play_card','source':{'cardId':defer,'zone':'hand'},
                'abilityId':'defer-to-deck-top','targets':[f.field_target(host)]},3)
            await self.resolve_top()
            self.assertIsNone(s.find_battlefield_item(host['id']))
            self.assertEqual(s.players['p1']['zones']['deck'][0],row['cardId'])
        await self.resolve_top()
        if row['outcome'] in ('pay_neutralize','pay_cancel'):
            choice=s.rules_engine['pendingChoice'];pid=choice['playerId']
            await self.send(self.ws(pid),{'type':'resolve_rules_choice','choiceId':choice['id'],'option':'decline'})
            await self.state(self.ws(pid),lambda m:m['rulesEngine']['pendingChoice'] is None)
        elif row['outcome']=='copy':
            choice=s.rules_engine['pendingChoice']
            await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':choice['id'],'option':'retarget',
                'targets':[{'kind':'card','itemId':'new-target','cardId':'m3'}]})
            await self.state(self.ws1,lambda m:m['rulesEngine']['pendingChoice'] is None and len(m['rulesEngine']['actionStack'])==2)
            self.assertEqual(f.power(s,s.find_battlefield_item('new-target')),3)
            await self.resolve_top();self.assertEqual(f.power(s,s.find_battlefield_item('new-target')),6)
            await self.resolve_top();self.assertEqual(f.power(s,s.find_battlefield_item('original-target')),7)
            self.assertEqual(s.players[original['source']['ownerId']]['zones']['graveyard'].count(original['source']['cardId']),1)
            return
        elif row['outcome'] in ('retarget','protect'):
            if row['outcome']=='retarget':self.assertEqual(original['targets'][0]['itemId'],'new-target')
            else:self.assertTrue(s.rules_stack_action_is_protected(original,'p2'))
            await self.resolve_top()
            self.assertEqual(f.power(s,s.find_battlefield_item('new-target' if row['outcome']=='retarget' else 'original-target')),6 if row['outcome']=='retarget' else 7)
            return
        f.assert_outcome(s,row,original)

    async def eorthoda(self):
        f=family.StackInteractionFamily();fixture=f.world();f.field(fixture,'m4','target')
        will=f.cid('Strengthen');donor=f.cid('Eorthoda, the Limpid');f.put(fixture,'p1','hand',[will,donor]);self.install(fixture)
        await self.declare('p1','Strengthen',{'kind':'play_card','source':{'cardId':will,'zone':'hand'},
            'abilityId':'strengthen-power-modifier','paymentCardIds':[donor],
            'targets':[{'kind':'card','itemId':'target','cardId':'m4'}]},1)
        declared=next(e for e in reversed(self.session.log) if e['type']=='rules_action_declared')
        original_id=declared['details']['actionId']
        self.assertIsNone(self.session.rules_engine['pendingChoice'])
        original=self.session.rules_engine['actionStack'][-1];self.assertTrue(original['cannotBeNeutralized'])
        await self.resolve_top()
        self.assertEqual(f.power(self.session,self.session.find_battlefield_item('target')),7)

    async def copied_will(self,persistent=False):
        f=family.StackInteractionFamily();row=next(r for r in family.CONTRACTS if r['key']=='imitate')
        fixture,_,_=f.setup_case(row)
        original=f.original(fixture,'persistent' if persistent else 'ephemeral')
        fixture.rules_engine['actionStack']=[original];self.install(fixture);s=self.session
        original=s.rules_engine['actionStack'][0]
        await self.declare('p1','Imitate',f.declaration(row,None,original),2);await self.resolve_top()
        if not persistent:
            choice=s.rules_engine['pendingChoice']
            await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':choice['id'],'option':'keep'})
            await self.state(self.ws1,lambda m:m['rulesEngine']['pendingChoice'] is None and len(m['rulesEngine']['actionStack'])==2)
        copied=s.rules_engine['actionStack'][-1];self.assertTrue(copied['isStackCopy'])
        self.assertEqual(copied['source']['ownerId'],'p1');self.assertEqual(original['source']['ownerId'],'p2')
        response=next(r for r in family.CONTRACTS if r['key']==('compensate' if persistent else 'neutralize'))
        f.put(s,'p2','hand',[response['cardId']]);s.add_rules_excess_essence('p2',[{'temperament':t,'amount':n} for t,n in response['essenceCost'].items()])
        before=f.pool(s,'p1')
        await self.declare('p2',response['name'],f.declaration(response,None,copied),3);await self.resolve_top()
        for state in self.last_resolution_states:
            self.assertEqual(len(state['rulesEngine']['actionStack']),1)
            self.assertEqual(state['rulesEngine']['actionStack'][0]['id'],original['id'])
        self.assertEqual(s.rules_engine['actionStack'],[original])
        for pid in ('p1','p2'):
            for zone in ('hand','graveyard','exile'):self.assertNotIn(original['source']['cardId'],s.players[pid]['zones'][zone])
        if persistent:
            after=f.pool(s,'p1');self.assertEqual(after['vitreous']-before['vitreous'],2);self.assertEqual(after['capricious']-before['capricious'],2)

    async def clemency(self,remove_original=False):
        f=family.StackInteractionFamily();fixture=f.world()
        source=f.field(fixture,f.cid('Simulacrum of Clemency'),'clemency',zone='field')
        f.field(fixture,'m4','target');will=f.cid('Strengthen');f.put(fixture,'p2','hand',[will])
        fixture.add_rules_excess_essence('p2',[{'temperament':'hollow','amount':1}]);fixture.rules_engine['priorityPlayerId']='p2'
        self.install(fixture);s=self.session
        await self.declare('p2','Strengthen',{'kind':'play_card','source':{'cardId':will,'zone':'hand'},
            'abilityId':'strengthen-power-modifier','targets':[{'kind':'card','itemId':'target','cardId':'m4'}]},2)
        original=next(a for a in s.rules_engine['actionStack'] if a['kind']=='play_card')
        if remove_original:
            if s.rules_engine['priorityPlayerId']!='p1':
                await self.send(self.ws2,{'type':'pass_priority','passed':True})
                await self.state(self.ws2,lambda m:m['rulesEngine']['priorityPlayerId']=='p1')
            neutralize=f.cid('Neutralize');f.put(s,'p1','hand',[neutralize])
            s.add_rules_excess_essence('p1',[{'temperament':'capricious','amount':2}])
            await self.declare('p1','Neutralize',{'kind':'play_card','source':{'cardId':neutralize,'zone':'hand'},
                'abilityId':'neutralize-stack-card','targets':[{'kind':'stack_action','actionId':original['id']}]},3)
            await self.resolve_top()
        await self.resolve_top()
        if remove_original:
            self.assertIsNone(s.rules_engine['pendingChoice']);self.assertEqual(s.players['p1']['score'],55)
            self.assertEqual(s.find_battlefield_item(source['id'])['rotation'],0)
        else:
            choice=s.rules_engine['pendingChoice']
            await self.send(self.ws2,{'type':'resolve_rules_choice','choiceId':choice['id'],'option':'neutralize'})
            await self.state(self.ws2,lambda m:m['rulesEngine']['pendingChoice'] is None)
            self.assertEqual(s.players['p1']['score'],50);self.assertEqual(s.find_battlefield_item(source['id'])['rotation'],90)
        self.assertEqual(s.rules_engine['actionStack'],[])

    async def duel(self):
        f=family.StackInteractionFamily();fixture=f.world();will=f.cid('Duel Honorably')
        fixture.phase_tracker['index']=ADVANCED_PHASES.index('confrontation_before_revelation')
        f.put(fixture,'p1','hand',[will]);self.install(fixture)
        await self.declare('p1','Duel',{'kind':'play_card','source':{'cardId':will,'zone':'hand'},
            'abilityId':'lock-support-entries-unless-opponent-pays','targets':[]},1)
        self.assertFalse(self.session.rules_support_entry_locked('p2'))
        await self.resolve_top()
        self.assertTrue(self.session.rules_support_entry_locked('p1'));self.assertTrue(self.session.rules_support_entry_locked('p2'))


for row in family.CONTRACTS:
    async def run(self,_driver,row=row):await self.exercise(row)
    setattr(StackInteractionIntegration,'test_'+row['key']+'__websocket',patch('main.auto_advance_rules_phases',new_callable=AsyncMock,return_value=False)(run))
async def radiance_gone(self,_driver):
    await self.exercise(next(r for r in family.CONTRACTS if r['key']=='radiance'),source_gone=True)
StackInteractionIntegration.test_radiance__source_gone_websocket=patch('main.auto_advance_rules_phases',new_callable=AsyncMock,return_value=False)(radiance_gone)
for key,method in (('eorthoda','eorthoda'),('clemency','clemency'),('duel','duel')):
    async def run(self,_driver,method=method):await getattr(self,method)()
    setattr(StackInteractionIntegration,'test_'+key+'__websocket',patch('main.auto_advance_rules_phases',new_callable=AsyncMock,return_value=False)(run))
async def clemency_missing(self,_driver):await self.clemency(remove_original=True)
StackInteractionIntegration.test_clemency__missing_will_websocket=patch('main.auto_advance_rules_phases',new_callable=AsyncMock,return_value=False)(clemency_missing)
for key,persistent in (('neutralize',False),('compensate',True)):
    async def copied(self,_driver,persistent=persistent):await self.copied_will(persistent)
    setattr(StackInteractionIntegration,'test_'+key+'__copied_will_websocket',patch('main.auto_advance_rules_phases',new_callable=AsyncMock,return_value=False)(copied))
