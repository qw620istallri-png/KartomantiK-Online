"""Mixed-version sockets see the dynamically calculated scores of all six cards.

Trigger stimuli are prepared explicitly. Plea uses its actual paid declaration.
Each journey changes a counted value while the effect waits on the Stack.
"""
import copy
import unittest
from unittest.mock import AsyncMock,patch
import test_state_transport_integration as transport
import test_bounce_replay_integration as passes
import test_scaled_score_family as family

main=transport.main


class ScaledScoreIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=transport.StateTransportIntegration.asyncSetUp
    asyncTearDown=transport.StateTransportIntegration.asyncTearDown
    join=transport.StateTransportIntegration.join
    receive_until=transport.StateTransportIntegration.receive_until
    send=transport.StateTransportIntegration.send
    prepare_active_rules=transport.StateTransportIntegration.prepare_active_rules
    pass_stack=passes.BounceReplayIntegration.pass_stack

    async def exercise(self,row):
        f=family.ScaledScoreFamily()
        fixture,host,counted,target=f.setup_case(row)
        if row['mode']=='event': action=f.begin(fixture,row,host,target)
        s=self.session
        for key in ('card_rules','card_points','manifestation_ids','players','battlefield',
                    'tokens','rules_engine','phase_tracker'):
            setattr(s,key,copy.deepcopy(getattr(fixture,key)))
        if row['mode']=='play':
            await self.send(self.ws1,{'type':'declare_rules_action','label':row['name'],
                'kind':'play_card','source':{'cardId':row['cardId'],'zone':'hand'},
                'abilityId':row['abilityId'],'targets':[{'kind':'player','playerId':target}]})
            state=await self.receive_until(self.ws1,lambda m:m.get('type')=='error' or
                m.get('type')=='state' and len(m['rulesEngine']['actionStack'])==1)
            self.assertEqual(state['type'],'state',state)
            action=s.rules_engine['actionStack'][0]
            self.assertEqual(sum(p['amount'] for p in action['cost']['essenceSpent']),2)
        else:
            await main.broadcast_state(s)
        # The change is a controlled game fixture, not a player UI mutation.
        actual=[s.find_battlefield_item(i['id']) for i in counted]
        f.change_population(s,row,actual,add=True)
        await main.broadcast_state(s)
        for ws in (self.ws1,self.ws2):
            queued=await self.receive_until(ws,lambda m:m.get('type')=='state' and
                any(a['id']==action['id'] for a in m['rulesEngine']['actionStack']))
            self.assertEqual({pid:p['score'] for pid,p in queued['players'].items()},{'p1':50,'p2':50})
        first=self.ws1 if s.rules_engine['priorityPlayerId']=='p1' else self.ws2
        second=self.ws2 if first is self.ws1 else self.ws1
        await self.pass_stack(first,second)
        for ws in (self.ws1,self.ws2):
            final=await self.receive_until(ws,lambda m:m.get('type')=='state' and
                any(e.get('type')=='rules_action_resolved' and e.get('details',{}).get('actionId')==action['id']
                    for e in m.get('recentLog',[])))
            self.assertEqual({pid:p['score'] for pid,p in final['players'].items()},f.expected_scores(row,3))
            self.assertEqual(final['rulesEngine']['actionStack'],[])
            self.assertIsNone(final['rulesEngine']['pendingChoice'])


for contract in family.CONTRACTS:
    async def guarded(self,_driver,row=contract): await self.exercise(row)
    setattr(ScaledScoreIntegration,'test_'+contract['key']+'__websocket_dynamic_count',
        patch('main.auto_advance_rules_phases',new_callable=AsyncMock,return_value=False)(guarded))


if __name__=='__main__': unittest.main()
