"""Two-socket exile journeys, real declarations and ETB choices.

Events and card zones are fixtures. Automatic phase driving is paused to isolate
response windows and exact rewards; this does not certify complete matches.
"""
import copy
import unittest
from unittest.mock import AsyncMock, patch
import test_state_transport_integration as transport
import test_bounce_replay_integration as passes
import test_exile_family as family


class ExileFamilyIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = transport.StateTransportIntegration.asyncSetUp
    asyncTearDown = transport.StateTransportIntegration.asyncTearDown
    join = transport.StateTransportIntegration.join
    receive_until = transport.StateTransportIntegration.receive_until
    send = transport.StateTransportIntegration.send
    prepare_active_rules = transport.StateTransportIntegration.prepare_active_rules
    pass_stack = passes.BounceReplayIntegration.pass_stack

    async def exercise(self, row, case):
        f = family.ExileFamily()
        fixture, host, targets = f.setup_case(row)
        s = self.session
        self.prepare_active_rules('confrontation_reaction')
        for attr in ('card_rules','card_points','manifestation_ids','players','battlefield','tokens','rules_engine','phase_tracker'):
            setattr(s,attr,copy.deepcopy(getattr(fixture,attr)))
        host = s.find_battlefield_item(host['id']) if host else None
        if case == 'bob': f.field(s,'inner-deserts-134','bob',power_bonus=3)
        if row['mode'] == 'event':
            actions = s.queue_rules_triggers(row['cardId'],'p1','enters_field',zone='confrontation',
                item_id=host['id'],face_up=True,controller_id='p1',defer=True)
            s.queue_rules_simultaneous_actions(actions)
            choice = s.rules_engine['pendingChoice']
            await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':choice['id'],'option':'accept'})
            offered = await self.receive_until(self.ws1,lambda m:m.get('type')=='error' or
                m.get('type')=='state' and (m['rulesEngine'].get('pendingChoice') or {}).get('kind')=='trigger_targets')
            self.assertEqual(offered['type'],'state',offered)
            self.assertEqual(s.rules_engine['actionStack'],[])
            choice = s.rules_engine['pendingChoice']
            await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':choice['id'],'targets':targets})
        else:
            await self.send(self.ws1,{'type':'declare_rules_action','label':row['name'],
                'kind':'play_card' if row['mode']=='play' else 'activated_effect',
                'source':{'cardId':row['cardId'],'zone':'battlefield' if host else 'hand',
                    **({'itemId':host['id']} if host else {})}, 'abilityId':row['abilityId'],'targets':targets})
        queued = await self.receive_until(self.ws1,lambda m:m.get('type')=='error' or
            m.get('type')=='state' and len(m['rulesEngine']['actionStack'])==1)
        self.assertEqual(queued['type'],'state',queued)
        f.rewards(s,row,host,0)
        action_id = queued['rulesEngine']['actionStack'][0]['id']
        await self.pass_stack(self.ws2,self.ws1)
        await self.receive_until(self.ws1,lambda m:m.get('type')=='state' and
            not m['rulesEngine']['actionStack'] and m['rulesEngine']['pendingChoice'] is None and
            any(e.get('type')=='rules_action_resolved' and e.get('details',{}).get('actionId')==action_id for e in m.get('recentLog',[])))
        f.rewards(s,row,host,0 if case=='bob' else 1)
        if case=='bob': self.assertTrue(any(e['cardId']=='exile-probe-0' for e in s.rules_engine['suspendedCards']))
        else:
            owner = 'p2' if row['targetZone']=='battlefield' else 'p1'
            self.assertIn('exile-probe-0',s.players[owner]['zones']['exile'])


for row in family.CONTRACTS:
    for case in ['normal'] + (['bob'] if row['key'] in ('carcass','referen') else []):
        async def run(self,_driver,row=row,case=case): await self.exercise(row,case)
        setattr(ExileFamilyIntegration,'test_'+row['key']+'__websocket_'+case,
            patch('main.auto_advance_rules_phases',new_callable=AsyncMock,return_value=False)(run))

if __name__=='__main__': unittest.main()
