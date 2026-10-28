"""A real paid declaration or explicit trigger, late invalidation, then WS passes.

Mixed-version clients must retain the declared roles and see the exact outcome.
Auto-phase driving is isolated; late invalidation itself is a controlled fixture.
"""
import copy
import unittest
from unittest.mock import AsyncMock,patch
import test_state_transport_integration as transport
import test_bounce_replay_integration as passes
import test_compound_targets as family

main=transport.main


class CompoundTargetIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=transport.StateTransportIntegration.asyncSetUp
    asyncTearDown=transport.StateTransportIntegration.asyncTearDown
    join=transport.StateTransportIntegration.join
    receive_until=transport.StateTransportIntegration.receive_until
    send=transport.StateTransportIntegration.send
    prepare_active_rules=transport.StateTransportIntegration.prepare_active_rules
    pass_stack=passes.BounceReplayIntegration.pass_stack

    async def exercise(self,row,index):
        f=family.CompoundTargets()
        fixture,host,targets=f.setup_case(row)
        if row['mode']=='event': action=f.begin(fixture,row,host,targets)
        s=self.session
        for key in ('card_rules','card_points','manifestation_ids','players','battlefield',
                    'tokens','rules_engine','phase_tracker'):
            setattr(s,key,copy.deepcopy(getattr(fixture,key)))
        if row['mode']=='event': action=s.rules_engine['actionStack'][0]
        if row['mode']!='event':
            source={'cardId':row['cardId'],'zone':'hand'} if row['mode']=='play' else {
                'cardId':row['cardId'],'zone':'battlefield','itemId':host['id']}
            await self.send(self.ws1,{'type':'declare_rules_action','label':row['name'],
                'kind':'play_card' if row['mode']=='play' else 'activated_effect',
                'source':source,'abilityId':row['abilityId'],'targets':targets})
            queued=await self.receive_until(self.ws1,lambda m:m.get('type')=='error' or
                m.get('type')=='state' and len(m['rulesEngine']['actionStack'])==1)
            self.assertEqual(queued['type'],'state',queued)
            action=s.rules_engine['actionStack'][0]
        original=copy.deepcopy(action['targets'])
        paid=copy.deepcopy(action['cost'])
        f.invalidate(s,targets[index],'missing')
        before={i['id']:s.rules_item_controller_id(i) for i in s.battlefield if i['id'].startswith('target-')}
        await main.broadcast_state(s)
        for ws in (self.ws1,self.ws2):
            state=await self.receive_until(ws,lambda m:m.get('type')=='state' and
                any(a['id']==action['id'] for a in m['rulesEngine']['actionStack']))
            self.assertEqual(state['rulesEngine']['actionStack'][0]['targets'],original)
        first=self.ws1 if s.rules_engine['priorityPlayerId']=='p1' else self.ws2
        second=self.ws2 if first is self.ws1 else self.ws1
        with patch('game.effects.dice.random.randint',return_value=1):
            await self.pass_stack(first,second)
            for ws in (self.ws1,self.ws2):
                final=await self.receive_until(ws,lambda m:m.get('type')=='state' and
                    any(e.get('type')=='rules_action_resolved' and e.get('details',{}).get('actionId')==action['id']
                        for e in m.get('recentLog',[])))
                self.assertEqual(final['rulesEngine']['actionStack'],[])
                self.assertIsNone(final['rulesEngine']['pendingChoice'])
                self.assertEqual(final['players']['p1']['score'],s.players['p1']['score'])
        valid=[i for i in range(len(targets)) if i!=index]
        f.verify(s,row,targets,valid,before)
        self.assertEqual(action['targets'],original)
        self.assertEqual(action['cost'],paid)
        if valid: self.assertEqual(action['invalidTargetIndices'],[index])
        else: self.assertEqual(action['effectResult']['kind'],'invalid_targets')


def network_cases(row): return [0,1] if row['key']=='paciphint' else [family.target_count(row)-1]


def method_name(row,index): return 'test_'+row['key']+'__websocket_invalid_'+str(index)


for contract in family.CONTRACTS:
    for index in network_cases(contract):
        async def guarded(self,_driver,row=contract,index=index): await self.exercise(row,index)
        setattr(CompoundTargetIntegration,method_name(contract,index),
            patch('main.auto_advance_rules_phases',new_callable=AsyncMock,return_value=False)(guarded))


if __name__=='__main__': unittest.main()
