"""Paid movement declarations over production sockets; zones are initial fixtures."""
import copy
import unittest
from unittest.mock import AsyncMock,patch
import test_state_transport_integration as transport
import test_bounce_replay_integration as passes
import test_zone_destination_family as family

class ZoneDestinationFamilyIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=transport.StateTransportIntegration.asyncSetUp
    asyncTearDown=transport.StateTransportIntegration.asyncTearDown
    join=transport.StateTransportIntegration.join
    receive_until=transport.StateTransportIntegration.receive_until
    send=transport.StateTransportIntegration.send
    prepare_active_rules=transport.StateTransportIntegration.prepare_active_rules
    pass_stack=passes.BounceReplayIntegration.pass_stack

    async def exercise(self,row,case):
        f=family.ZoneDestinationFamily()
        fixture,_,target,owner=f.setup_case(row)
        s=self.session;self.prepare_active_rules('confrontation_reaction')
        for attr in ('card_rules','card_points','manifestation_ids','players','battlefield','tokens','rules_engine','phase_tracker'):
            setattr(s,attr,copy.deepcopy(getattr(fixture,attr)))
        if case=='bob':f.field(s,'inner-deserts-134','bob',power_bonus=3)
        await self.send(self.ws1,{'type':'declare_rules_action','label':row['name'],'kind':'play_card',
            'source':{'cardId':row['cardId'],'zone':'hand'},'abilityId':row['abilityId'],'targets':[target]})
        queued=await self.receive_until(self.ws1,lambda m:m.get('type')=='error' or m.get('type')=='state' and len(m['rulesEngine']['actionStack'])==1)
        self.assertEqual(queued['type'],'state',queued)
        action_id=queued['rulesEngine']['actionStack'][0]['id']
        if row['targetZone']!='battlefield':self.assertIn('destination-probe',s.players[target['containerId']]['zones'][target['zone']])
        await self.pass_stack(self.ws2,self.ws1)
        await self.receive_until(self.ws1,lambda m:m.get('type')=='state' and not m['rulesEngine']['actionStack'] and m['rulesEngine']['pendingChoice'] is None and
            any(e.get('type')=='rules_action_resolved' and e.get('details',{}).get('actionId')==action_id for e in m.get('recentLog',[])))
        if case=='bob':
            self.assertTrue(any(e['cardId']=='destination-probe' for e in s.rules_engine['suspendedCards']))
            self.assertFalse(any(i['cardId']=='destination-probe' for i in s.battlefield))
        else:f.outcome(s,row,owner)

for row in family.CONTRACTS:
    for case in ['normal']+(['bob'] if row['key'] in ('revive','claim') else []):
        async def run(self,_driver,row=row,case=case):await self.exercise(row,case)
        setattr(ZoneDestinationFamilyIntegration,'test_'+row['key']+'__websocket_'+case,
            patch('main.auto_advance_rules_phases',new_callable=AsyncMock,return_value=False)(run))

if __name__=='__main__':unittest.main()
