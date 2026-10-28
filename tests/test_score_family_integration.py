"""Six recipient routes through real priority passes and mixed-version sockets.

The effect is queued with an explicit event stimulus before broadcast. These
journeys verify transport/resolution, not whole-match event production.
"""
import copy
import unittest
from unittest.mock import AsyncMock, patch
import test_state_transport_integration as transport
import test_bounce_replay_integration as passes
import test_score_family as family

main=transport.main
NETWORK_KEYS={'incubator','petal','cannon','soul_borer','kox_limbo','linoleus'}


class ScoreFamilyIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=transport.StateTransportIntegration.asyncSetUp
    asyncTearDown=transport.StateTransportIntegration.asyncTearDown
    join=transport.StateTransportIntegration.join
    receive_until=transport.StateTransportIntegration.receive_until
    send=transport.StateTransportIntegration.send
    prepare_active_rules=transport.StateTransportIntegration.prepare_active_rules
    pass_stack=passes.BounceReplayIntegration.pass_stack

    async def exercise(self,row):
        f=family.ScoreFamily()
        fixture,host,picked=f.setup_case(row)
        action=f.begin(fixture,row,host,picked)
        s=self.session
        for key in ('card_rules','card_points','manifestation_ids','players','battlefield',
                    'tokens','rules_engine','phase_tracker'):
            setattr(s,key,copy.deepcopy(getattr(fixture,key)))
        await main.broadcast_state(s)
        for ws in (self.ws1,self.ws2):
            queued=await self.receive_until(ws,lambda m:m.get('type')=='state' and
                any(a['id']==action['id'] for a in m['rulesEngine']['actionStack']))
            self.assertEqual({pid:p['score'] for pid,p in queued['players'].items()},{'p1':50,'p2':50})
        first=self.ws1 if s.rules_engine['priorityPlayerId']=='p1' else self.ws2
        second=self.ws2 if first is self.ws1 else self.ws1
        await self.pass_stack(first,second)
        expected={'p1':50,'p2':50}
        expected[f.recipient(row,'p1',f.event_player(row,'p1'))]+=row['expectedDelta']
        for ws in (self.ws1,self.ws2):
            final=await self.receive_until(ws,lambda m:m.get('type')=='state' and
                any(e.get('type')=='rules_action_resolved' and e.get('details',{}).get('actionId')==action['id']
                    for e in m.get('recentLog',[])))
            self.assertEqual({pid:p['score'] for pid,p in final['players'].items()},expected)
            self.assertEqual(final['rulesEngine']['actionStack'],[])
            self.assertIsNone(final['rulesEngine']['pendingChoice'])


for contract in family.CONTRACTS:
    if contract['key'] in NETWORK_KEYS:
        async def guarded(self,_driver,row=contract): await self.exercise(row)
        setattr(ScoreFamilyIntegration,'test_'+contract['key']+'__websocket_resolution',
            patch('main.auto_advance_rules_phases',new_callable=AsyncMock,return_value=False)(guarded))


if __name__=='__main__': unittest.main()
