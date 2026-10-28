"""One real two-player WebSocket journey per voluntary power-family effect."""
import copy
import unittest
from unittest.mock import AsyncMock, patch
import test_state_transport_integration as transport
import test_bounce_replay_integration as passes
import test_power_family as family

main=transport.main
VOLUNTARY=[r for r in family.CONTRACTS if r['mode']!='event']


class PowerFamilyIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=transport.StateTransportIntegration.asyncSetUp
    asyncTearDown=transport.StateTransportIntegration.asyncTearDown
    join=transport.StateTransportIntegration.join
    receive_until=transport.StateTransportIntegration.receive_until
    send=transport.StateTransportIntegration.send
    prepare_active_rules=transport.StateTransportIntegration.prepare_active_rules
    pass_stack=passes.BounceReplayIntegration.pass_stack

    async def exercise(self,row):
        f=family.PowerFamily()
        fixture,host,picked,_=f.setup_case(row)
        s=self.session
        self.prepare_active_rules('confrontation_reaction')
        s.card_rules,s.card_points,s.manifestation_ids=fixture.card_rules,fixture.card_points,fixture.manifestation_ids
        s.players=copy.deepcopy(fixture.players)
        s.battlefield=copy.deepcopy(fixture.battlefield)
        s.tokens=copy.deepcopy(fixture.tokens)
        s.rules_engine=copy.deepcopy(fixture.rules_engine)
        s.phase_tracker=copy.deepcopy(fixture.phase_tracker)
        source={'cardId':row['cardId'],'zone':'hand'} if row['mode']=='play' else {
            'cardId':row['cardId'],'zone':'battlefield','itemId':host['id']}
        await self.send(self.ws1,{'type':'declare_rules_action','label':row['name'],
            'kind':'play_card' if row['mode']=='play' else 'activated_effect',
            'source':source,'abilityId':row['abilityId'],'targets':[f.target(picked)]})
        queued=await self.receive_until(self.ws1,lambda m:m.get('type')=='error' or
            m.get('type')=='state' and len(m['rulesEngine']['actionStack'])==1)
        self.assertEqual(queued['type'],'state',queued)
        current=s.find_battlefield_item(picked['id'])
        self.assertEqual(f.power(s,current),row['targetBase'])
        self.assertEqual(s.players['p1']['score'],50-row.get('scoreCost',0))
        await self.pass_stack(self.ws2,self.ws1)
        action_id=queued['rulesEngine']['actionStack'][0]['id']
        final=await self.receive_until(self.ws1,lambda m:m.get('type')=='state' and
            not m['rulesEngine']['actionStack'] and m['rulesEngine']['pendingChoice'] is None and
            any(e.get('type')=='rules_action_resolved' and e.get('details',{}).get('actionId')==action_id for e in m.get('recentLog',[])))
        self.assertEqual(f.power(s,current),row['targetBase']+row['expectedDelta'])
        self.assertTrue(any(e.get('type')=='rules_action_resolved' for e in final.get('recentLog',[])))
        if row['mode']=='play': self.assertEqual(s.players['p1']['zones']['graveyard'].count(row['cardId']),1)


# Apply the asynchronous patch through a signature that accepts its mock.
for contract in VOLUNTARY:
    async def guarded(self,_driver,row=contract): await self.exercise(row)
    setattr(PowerFamilyIntegration,'test_'+contract['key']+'__websocket_resolution',
            patch('main.auto_advance_rules_phases',new_callable=AsyncMock,return_value=False)(guarded))


if __name__=='__main__': unittest.main()
