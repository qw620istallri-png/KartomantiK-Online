"""Real Pray declaration, suspended self-source choices, reconnect and free Will."""
import copy,unittest
from unittest.mock import AsyncMock,patch
import test_state_transport_integration as transport
import test_bounce_replay_integration as passes
import test_self_discard as family

main=transport.main

class SelfDiscardIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=transport.StateTransportIntegration.asyncSetUp
    asyncTearDown=transport.StateTransportIntegration.asyncTearDown
    join=transport.StateTransportIntegration.join
    receive_until=transport.StateTransportIntegration.receive_until
    send=transport.StateTransportIntegration.send
    prepare_active_rules=transport.StateTransportIntegration.prepare_active_rules
    pass_stack=passes.BounceReplayIntegration.pass_stack

    async def state(self,ws,predicate):
        m=await self.receive_until(ws,lambda m:m.get('type')=='error' or m.get('type')=='state' and predicate(m))
        self.assertEqual(m['type'],'state',m);return m

    async def pass_current(self):
        first=self.ws1 if self.session.rules_engine['priorityPlayerId']=='p1' else self.ws2
        await self.pass_stack(first,self.ws2 if first is self.ws1 else self.ws1)

    @staticmethod
    def resolved(m,aid):return any(e.get('type')=='rules_action_resolved' and e.get('details',{}).get('actionId')==aid for e in m.get('recentLog',[]))

    async def exercise(self,row,case):
        f=family.SelfDiscard();fixture=f.world();cid=row['cardId'];ponder=f.cid('Ponder');pray=f.cid('Pray the Ether')
        f.field(fixture,'inner-deserts-134','bob',power_bonus=3)
        f.field(fixture,'m4','target',owner='p2')
        f.put(fixture,'p1','hand',[pray,cid]);f.put(fixture,'p1','graveyard',[ponder])
        f.put(fixture,'p1','deck',['m2','m3','m4'])
        s=self.session
        for key in ('card_rules','card_points','manifestation_ids','players','battlefield','tokens','rules_engine','phase_tracker'):
            setattr(s,key,copy.deepcopy(getattr(fixture,key)))
        await main.broadcast_state(s)
        for ws in (self.ws1,self.ws2):await self.state(ws,lambda m:m['rulesEngine']['readyPlayerIds']==['p1','p2'])
        await self.send(self.ws1,{'type':'declare_rules_action','kind':'play_card','label':'Pray','source':{'cardId':pray,'zone':'hand'},'abilityId':'discard-one-then-draw-two'})
        await self.state(self.ws1,lambda m:len(m['rulesEngine']['actionStack'])==1)
        await self.pass_current()
        await self.state(self.ws1,lambda m:(m['rulesEngine']['pendingChoice'] or {}).get('kind')=='discard_from_hand')
        choice=s.rules_engine['pendingChoice']
        await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':choice['id'],'cardIds':[cid]})
        await self.state(self.ws1,lambda m:(m['rulesEngine']['pendingChoice'] or {}).get('sourceCardId')==cid)
        choice=s.rules_engine['pendingChoice']
        suspension=next(e for e in s.rules_engine['suspendedCards'] if e['cardId']==cid)
        await self.ws1.close();self.ws1,_=await self.join({'type':'join','code':self.code,'name':'P1','clientId':'p1'})
        await self.state(self.ws1,lambda m:(m['rulesEngine']['pendingChoice'] or {}).get('id')==choice['id'])
        if row['key']=='nghoul':
            self.assertEqual(choice['kind'],'optional_stack_action')
            await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':choice['id'],'option':'accept'})
            await self.state(self.ws1,lambda m:(m['rulesEngine']['pendingChoice'] or {}).get('kind')=='trigger_targets')
        choice=s.rules_engine['pendingChoice'];self.assertEqual(choice['kind'],'trigger_targets')
        targets=[{'kind':'card','itemId':'target','cardId':'m4'}] if row['key']=='tombloom' else [{'kind':'zone_card','containerId':'p1','ownerId':'p1','zone':'graveyard','cardId':ponder}]
        await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':choice['id'],'targets':targets})
        await self.state(self.ws1,lambda m:m['rulesEngine']['pendingChoice'] is None and len(m['rulesEngine']['actionStack'])==1)
        action=s.rules_engine['actionStack'][-1]
        if case=='source_left':
            self.assertIsNone(s.restore_suspended_card(suspension['id'])[0])
            await main.broadcast_state(s)
        await self.pass_current()
        for ws in (self.ws1,self.ws2):await self.state(ws,lambda m:self.resolved(m,action['id']))
        self.assertEqual(cid in s.players['p1']['zones']['exile'],case!='source_left')
        if row['key']=='tombloom':self.assertEqual(s.rules_manifestation_characteristics(s.find_battlefield_item('target'))['power'],2)
        else:
            self.assertEqual(len(s.rules_engine['playPermissions']),int(case!='source_left'))
            if case!='source_left':
                if s.rules_engine['priorityPlayerId']!='p1':
                    await self.send(self.ws2,{'type':'pass_priority','passed':True})
                    await self.state(self.ws1,lambda m:m['rulesEngine']['priorityPlayerId']=='p1')
                await self.send(self.ws1,{'type':'declare_rules_action','kind':'play_card','label':'Free Ponder','source':{'cardId':ponder,'zone':'graveyard'},'abilityId':'draw-three-cards'})
                await self.state(self.ws1,lambda m:len(m['rulesEngine']['actionStack'])==1)
                played=s.rules_engine['actionStack'][-1]
                self.assertEqual(played['cost']['tributeCardIds'],[])
                await self.pass_current()
                for ws in (self.ws1,self.ws2):await self.state(ws,lambda m:self.resolved(m,played['id']))
                self.assertIn(ponder,s.players['p1']['zones']['exile'])
        self.assertIsNone(s.rules_engine['pendingChoice']);self.assertEqual(s.rules_engine['actionStack'],[])

def network_cases(row):return ('resolve','source_left')
def method_name(row,case):return 'test_'+row['key']+'__websocket_'+case
for row in family.CONTRACTS:
    for case in network_cases(row):
        async def run(self,_driver,row=row,case=case):await self.exercise(row,case)
        setattr(SelfDiscardIntegration,method_name(row,case),patch('main.auto_advance_rules_phases',new_callable=AsyncMock,return_value=False)(run))

if __name__=='__main__':unittest.main()
