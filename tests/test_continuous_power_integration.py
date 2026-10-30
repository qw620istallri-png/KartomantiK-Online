"""Paid Defer journeys verify live recalculation and both clients' public power."""
import copy
import unittest
from unittest.mock import AsyncMock, patch
import test_state_transport_integration as transport
import test_bounce_replay_integration as passes
import test_continuous_power_family as family

CASES = (
    ('prospero', 'host', 8, 5), ('herbaceous', 'host', 6, 5), ('gargullo', 'host', 7, 5),
    ('bell', 'blocker', 5, 7), ('berta', 'host', 5, 3), ('sangen', 'host', 4, 5),
    ('tower', 'host', 6, 5), ('kazadur', 'count-0', 7, 6), ('lucerco', 'count-0', 6, 5),
    ('skapus', 'blocker', 1, 3), ('tower', 'stalemate-host', 1, 1),
)


class ContinuousPowerIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = transport.StateTransportIntegration.asyncSetUp
    asyncTearDown = transport.StateTransportIntegration.asyncTearDown
    join = transport.StateTransportIntegration.join
    receive_until = transport.StateTransportIntegration.receive_until
    send = transport.StateTransportIntegration.send
    prepare_active_rules = transport.StateTransportIntegration.prepare_active_rules
    pass_stack = passes.BounceReplayIntegration.pass_stack

    async def exercise(self, row, picked_id, before, after):
        f = family.ContinuousPowerFamily()
        fixture, host, target = f.setup_case(row)
        if row['key'] == 'bell': f.field(fixture, 'aura-probe', 'blocker')
        elif row['key'] == 'kazadur':
            fixture.battlefield = [i for i in fixture.battlefield if i['id'] not in ('count-3', 'count-4')]
        elif row['key'] == 'skapus':
            f.field(fixture, 'm2', 'blocker', support=True)
            f.field(fixture, 'm3', 'old-support', zone='stalemate', support=True)
        elif picked_id == 'stalemate-host':
            target = f.field(fixture, f.cid('Nubilung, the Elder'), 'nubilung', zone='stalemate', support=True)
            target['counters']['Abstraction'] = 1
            picked_id = host['id']
        s = self.session
        self.prepare_active_rules('confrontation_reaction')
        for attr in ('card_rules', 'card_points', 'manifestation_ids', 'players', 'battlefield', 'tokens', 'rules_engine', 'phase_tracker'):
            setattr(s, attr, copy.deepcopy(getattr(fixture, attr)))
        target = s.find_battlefield_item(target['id'])
        picked = s.find_battlefield_item(picked_id)
        defer = f.cid('Defer')
        f.put(s, 'p1', 'hand', [defer])
        s.add_rules_excess_essence('p1', [{'temperament': 'vitreous', 'amount': 2}])
        self.assertEqual(f.power(s, target), before)
        await self.send(self.ws1, {'type': 'declare_rules_action', 'label': 'Defer', 'kind': 'play_card',
            'source': {'cardId': defer, 'zone': 'hand'}, 'abilityId': 'defer-to-deck-top', 'targets': [f.target(picked)]})
        queued = await self.receive_until(self.ws1, lambda m: m.get('type') == 'error' or
            m.get('type') == 'state' and len(m['rulesEngine']['actionStack']) == 1)
        self.assertEqual(queued['type'], 'state', queued)
        self.assertEqual(queued['rulesEngine']['actionStack'][0]['cost']['tributeRequirements'], {'vitreous': 2})
        self.assertEqual(next(i for i in queued['battlefield'] if i['id'] == target['id'])['effectivePower'], before)
        action_id = queued['rulesEngine']['actionStack'][0]['id']
        await self.pass_stack(self.ws2, self.ws1)
        for ws in (self.ws1, self.ws2):
            result = await self.receive_until(ws, lambda m: m.get('type') == 'state' and
                any(e.get('type') == 'rules_action_resolved' and e.get('details', {}).get('actionId') == action_id
                    for e in m.get('recentLog', [])))
            self.assertEqual(next(i for i in result['battlefield'] if i['id'] == target['id'])['effectivePower'], after)
        self.assertEqual(f.power(s, target), after)
        self.assertIsNone(s.find_battlefield_item(picked_id))
        self.assertEqual(s.players[picked['ownerId']]['zones']['deck'][0], picked['cardId'])
        self.assertEqual(s.rules_engine['actionStack'], [])


for key, picked_id, before, after in CASES:
    row = next(r for r in family.CONTRACTS if r['key'] == key)
    async def run(self, _driver, row=row, picked_id=picked_id, before=before, after=after):
        await self.exercise(row, picked_id, before, after)
    setattr(ContinuousPowerIntegration, 'test_' + key + '__defer_' + picked_id.replace('-', '_'),
        patch('main.auto_advance_rules_phases', new_callable=AsyncMock, return_value=False)(run))
