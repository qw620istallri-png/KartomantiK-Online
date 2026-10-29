"""Support declarations, entry triggers and ordering over two real sockets."""
import copy
import unittest
from unittest.mock import AsyncMock,patch
import test_state_transport_integration as transport
import test_bounce_replay_integration as passes
import test_support_family as family

class SupportFamilyIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=transport.StateTransportIntegration.asyncSetUp
    asyncTearDown=transport.StateTransportIntegration.asyncTearDown
    join=transport.StateTransportIntegration.join
    receive_until=transport.StateTransportIntegration.receive_until
    send=transport.StateTransportIntegration.send
    prepare_active_rules=transport.StateTransportIntegration.prepare_active_rules
    pass_stack=passes.BounceReplayIntegration.pass_stack

    async def exercise(self,row,case):
        f=family.SupportFamily();fixture,items,targets=f.setup_case(row)
        s=self.session;self.prepare_active_rules('confrontation_reaction')
        for attr in ('card_rules','card_points','manifestation_ids','players','battlefield','tokens','rules_engine','phase_tracker'):
            setattr(s,attr,copy.deepcopy(getattr(fixture,attr)))
        items=[s.find_battlefield_item(i['id']) for i in items]
        if case=='bob':f.field(s,'inner-deserts-134','bob',power_bonus=3)
        blossom=f.field(s,'5liq0tcj7m9ebqr_en','blossom',zone='field') if case=='watcher' else None
        await self.send(self.ws1,{'type':'declare_rules_action','label':row['name'],'kind':'play_card',
            'source':{'cardId':row['cardId'],'zone':'hand'},'abilityId':row['abilityId'],'targets':targets,
            **({'extraEssenceCount':2} if row['key']=='rally' else {})})
        queued=await self.receive_until(self.ws1,lambda m:m.get('type')=='error' or m.get('type')=='state' and len(m['rulesEngine']['actionStack'])==1)
        self.assertEqual(queued['type'],'state',queued)
        action_id=queued['rulesEngine']['actionStack'][0]['id']
        self.assertEqual(f.copies(s),[])
        await self.pass_stack(self.ws2,self.ws1)
        await self.receive_until(self.ws1,lambda m:m.get('type')=='state' and
            any(e.get('type')=='rules_action_resolved' and e.get('details',{}).get('actionId')==action_id for e in m.get('recentLog',[])))
        if case=='bob':self.assertTrue(any(e['cardId']=='support-probe' for e in s.rules_engine['suspendedCards']))
        else:f.assert_normal(s,row,items,targets,2)
        if blossom:
            self.assertEqual(blossom['counters'].get('Petal',0),0)
            choice=s.rules_engine.get('pendingChoice')
            if choice:
                self.assertEqual(choice['kind'],'simultaneous_stack_order')
                await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':choice['id'],'cardIds':[a['actionId'] for a in choice['actions']]})
                await self.receive_until(self.ws1,lambda m:m.get('type')=='state' and m['rulesEngine']['pendingChoice'] is None and bool(m['rulesEngine']['actionStack']))
            self.assertEqual(len(s.rules_engine['actionStack']),2 if row['key']=='rally' else 1)
            while s.rules_engine['actionStack']:
                current=s.rules_engine['actionStack'][-1]['id']
                first,second=(self.ws1,self.ws2) if s.rules_engine['priorityPlayerId']=='p1' else (self.ws2,self.ws1)
                await self.pass_stack(first,second)
                await self.receive_until(self.ws1,lambda m:m.get('type')=='state' and
                    any(e.get('type')=='rules_action_resolved' and e.get('details',{}).get('actionId')==current for e in m.get('recentLog',[])))
            self.assertEqual(blossom['counters'].get('Petal',0),2 if row['key']=='rally' else 1)

for row in family.CONTRACTS:
    for case in ['normal']+(['watcher'] if row['key'] in ('mirror','rally','reforging') else [])+(['bob'] if row['key']=='reforging' else []):
        async def run(self,_driver,row=row,case=case):await self.exercise(row,case)
        setattr(SupportFamilyIntegration,'test_'+row['key']+'__websocket_'+case,
            patch('main.auto_advance_rules_phases',new_callable=AsyncMock,return_value=False)(run))

if __name__=='__main__':unittest.main()
