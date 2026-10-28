"""Actual Will declarations, replacement order, draws and reconnect over WebSockets."""
import copy
import unittest
from unittest.mock import AsyncMock,patch
import test_state_transport_integration as transport
import test_bounce_replay_integration as passes
import test_conditional_discard_replacement as family

main=transport.main


class ConditionalDiscardIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=transport.StateTransportIntegration.asyncSetUp
    asyncTearDown=transport.StateTransportIntegration.asyncTearDown
    join=transport.StateTransportIntegration.join
    receive_until=transport.StateTransportIntegration.receive_until
    send=transport.StateTransportIntegration.send
    prepare_active_rules=transport.StateTransportIntegration.prepare_active_rules
    pass_stack=passes.BounceReplayIntegration.pass_stack

    async def state(self,ws,predicate):
        message=await self.receive_until(ws,lambda m:m.get('type')=='error' or m.get('type')=='state' and predicate(m))
        self.assertEqual(message['type'],'state',message)
        return message

    async def exercise(self,row,profile):
        bench=family.ConditionalDiscardReplacement()
        f,fixture,_,_,_=bench.setup_case(row,profile,resolve=False)
        fixture.rules_engine['actionStack']=[]
        fixture.rules_engine['priorityPlayerId']='p1'
        # Press is triggered by a real Pray declaration. Pray itself remains below
        # the Press effect, allowing that effect's results to be inspected separately.
        f.put(fixture,'p1','hand',[f.cid(f.PRAY),'w2'])
        if profile=='exile':f.kanon(fixture)
        s=self.session
        for key in ('card_rules','card_points','manifestation_ids','players','battlefield','tokens','rules_engine','phase_tracker'):
            setattr(s,key,copy.deepcopy(getattr(fixture,key)))
        phase=s.current_phase_id()
        await main.broadcast_state(s)
        for ws in (self.ws1,self.ws2):await self.state(ws,lambda m:m['rulesEngine']['readyPlayerIds']==['p1','p2'])
        await self.send(self.ws1,{'type':'declare_rules_action','kind':'play_card','label':'Pray',
            'source':{'cardId':f.cid(f.PRAY),'zone':'hand'},'abilityId':'discard-one-then-draw-two'})
        if row['key']=='press':
            offer=await self.state(self.ws1,lambda m:(m['rulesEngine']['pendingChoice'] or {}).get('kind')=='optional_stack_action')
            await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':offer['rulesEngine']['pendingChoice']['id'],'option':'accept'})
            ordered=await self.state(self.ws1,lambda m:(m['rulesEngine']['pendingChoice'] or {}).get('kind')=='simultaneous_stack_order')
            group=s.rules_engine['pendingChoice']['_group']
            ids=[a['id'] for a in group if a['source']['cardId']==f.cid(f.PRAY)]+[a['id'] for a in group if a['source']['cardId']==row['cardId']]
            await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':ordered['rulesEngine']['pendingChoice']['id'],'cardIds':ids})
        await self.state(self.ws1,lambda m:m['rulesEngine']['pendingChoice'] is None and len(m['rulesEngine']['actionStack'])==(2 if row['key']=='press' else 1))
        first=self.ws1 if s.rules_engine['priorityPlayerId']=='p1' else self.ws2
        await self.pass_stack(first,self.ws2 if first is self.ws1 else self.ws1)
        for ws in (self.ws1,self.ws2):
            await self.state(ws,lambda m:(m['rulesEngine']['pendingChoice'] or {}).get('kind')=='discard_from_hand')
        original=s.rules_engine['pendingChoice'];before=f.snapshot(s)
        await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':original['id'],'cardIds':[]})
        await self.receive_until(self.ws1,lambda m:m.get('type')=='error');self.assertEqual(f.snapshot(s),before)
        await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':original['id'],'cardIds':['w2']})
        if profile=='order_exile':
            order_state=await self.state(self.ws1,lambda m:(m['rulesEngine']['pendingChoice'] or {}).get('kind')=='replacement_order')
            order=s.rules_engine['pendingChoice']
            self.assertEqual(s.players['p1']['zones']['hand'],['w2'])
            self.assertEqual(s.players['p1']['zones']['deck'],['m2','m3','m4'])
            self.assertFalse(any(k.startswith('_') for k in order_state['rulesEngine']['pendingChoice']))
            await self.ws1.close()
            self.ws1,_=await self.join({'type':'join','code':self.code,'name':'P1','clientId':'p1'})
            await self.state(self.ws1,lambda m:(m['rulesEngine']['pendingChoice'] or {}).get('id')==order['id'])
            ordered=sorted(order['actions'],key=lambda e:e['replacementKind']=='exile')
            await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':order['id'],'cardIds':[e['actionId'] for e in ordered]})
        elif profile=='exile':
            replaced=await self.state(self.ws1,lambda m:(m['rulesEngine']['pendingChoice'] or {}).get('kind')=='draw_replacement')
            choice=replaced['rulesEngine']['pendingChoice']
            self.assertEqual(choice['cardIds'],['m2','m3'][:row['expectedDraw']])
            self.assertEqual(replaced['players']['p1']['zones']['hand']['cards'],[])
            peer=await self.state(self.ws2,lambda m:(m['rulesEngine']['pendingChoice'] or {}).get('id')==choice['id'])
            self.assertNotIn('cardIds',peer['rulesEngine']['pendingChoice'])
            await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':choice['id'],'cardIds':['m2']})
        for ws in (self.ws1,self.ws2):
            final=await self.state(ws,lambda m:m['rulesEngine']['pendingChoice'] is None and
                len(m['rulesEngine']['actionStack'])==(1 if row['key']=='press' else 0) and
                (m['rulesEngine'].get('lastResolvedAction') or {}).get('source',{}).get('cardId')==row['cardId'])
            self.assertEqual(final['phaseTracker']['index'],s.phase_tracker['index'])
        self.assertEqual(s.current_phase_id(),phase)
        self.assertEqual(s.players['p1']['zones']['deck'],['m2','m3','m4'][row['expectedDraw']:])
        self.assertEqual(s.players['p1']['zones']['hand'],['m3'] if profile=='exile' and row['expectedDraw']==2 else [])
        self.assertEqual(s.players['p1']['zones']['exile'].count('w2'),int(profile!='suspend'))
        self.assertEqual(sum(c['cardId']=='w2' for c in s.rules_engine['suspendedCards']),int(profile=='suspend'))
        if profile!='exile':
            for cid in ['m2','m3'][:row['expectedDraw']]:self.assertEqual(sum(c['cardId']==cid for c in s.rules_engine['suspendedCards']),1)
        if row['key']=='press':self.assertEqual(s.find_battlefield_item('press')['counters']['Formula'],5)
        before=f.snapshot(s)
        await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':original['id'],'cardIds':['w2']})
        await self.receive_until(self.ws1,lambda m:m.get('type')=='error');self.assertEqual(f.snapshot(s),before)


def network_cases(row):return ('exile','suspend','order_exile')
def method_name(row,case):return 'test_'+row['key']+'__websocket_'+case


for row in family.CONTRACTS:
    for case in network_cases(row):
        async def run(self,_driver,row=row,case=case):await self.exercise(row,case)
        setattr(ConditionalDiscardIntegration,method_name(row,case),patch('main.auto_advance_rules_phases',new_callable=AsyncMock,return_value=False)(run))


if __name__=='__main__':unittest.main()
