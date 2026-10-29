"""Paid Will declarations over two real sockets; controlled target interventions."""
import copy
import unittest
from unittest.mock import AsyncMock, patch

import test_state_transport_integration as transport
import test_bounce_replay_integration as passes
import test_targeted_destruction as family


class TargetedDestructionIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = transport.StateTransportIntegration.asyncSetUp
    asyncTearDown = transport.StateTransportIntegration.asyncTearDown
    join = transport.StateTransportIntegration.join
    receive_until = transport.StateTransportIntegration.receive_until
    send = transport.StateTransportIntegration.send
    prepare_active_rules = transport.StateTransportIntegration.prepare_active_rules
    pass_stack = passes.BounceReplayIntegration.pass_stack

    async def exercise(self, row, case):
        f = family.TargetedDestruction()
        fixture, _, items = f.setup_case(row, count=2 if case == 'partial_reconnect' else 1)
        s = self.session
        self.prepare_active_rules('confrontation_reaction')
        for attr in ('card_rules', 'card_points', 'manifestation_ids', 'players', 'battlefield', 'tokens', 'rules_engine', 'phase_tracker'):
            setattr(s, attr, copy.deepcopy(getattr(fixture, attr)))
        if case == 'exile':
            s.create_rules_ongoing_effects(family.base.DiscardDrawClauses().action('Nullify Reason',
                targets=[{'kind': 'player', 'playerId': items[0]['ownerId']}], ability_id='nullify-reason-exile-incoming'))
        if case == 'suspend': f.field(s, 'inner-deserts-134', 'bob', power_bonus=3)
        await self.send(self.ws1, {'type': 'declare_rules_action', 'label': row['name'], 'kind': 'play_card',
            'source': {'cardId': row['cardId'], 'zone': 'hand'}, 'abilityId': row['abilityId'],
            'targets': [f.target(i) for i in items]})
        queued = await self.receive_until(self.ws1, lambda m: m.get('type') == 'error' or
            m.get('type') == 'state' and len(m['rulesEngine']['actionStack']) == 1)
        self.assertEqual(queued['type'], 'state', queued)
        action_id = queued['rulesEngine']['actionStack'][0]['id']
        self.assertEqual(s.players['p1']['score'], 50)
        self.assertTrue(all(s.find_battlefield_item(i['id']) for i in items))
        second = self.ws1
        if case == 'partial_reconnect':
            f.invalidate(s, s.find_battlefield_item(items[0]['id']), 'protection')
            await self.ws1.close()
            second, _ = await self.join({'type': 'join', 'code': self.code, 'name': 'P1', 'clientId': 'p1'})
            restored = await self.receive_until(second, lambda m: m.get('type') == 'state')
            self.assertEqual(restored['rulesEngine']['actionStack'][0]['id'], action_id)
        await self.pass_stack(self.ws2, second)
        final = await self.receive_until(second, lambda m: m.get('type') == 'state' and
            not m['rulesEngine']['actionStack'] and m['rulesEngine']['pendingChoice'] is None and
            any(e.get('type') == 'rules_action_resolved' and e.get('details', {}).get('actionId') == action_id for e in m.get('recentLog', [])))
        self.assertEqual(s.players['p1']['score'], 50 + row['scoreOnSuccess'])
        if case == 'partial_reconnect':
            self.assertIsNotNone(s.find_battlefield_item(items[0]['id']))
            self.assertIsNone(s.find_battlefield_item(items[1]['id']))
        else: self.assertIsNone(s.find_battlefield_item(items[0]['id']))
        if case == 'exile':
            self.assertEqual(s.players['p2']['zones']['hand'], [])
            self.assertEqual(s.players[items[0]['ownerId']]['zones']['exile'].count('destruction-probe'), 1)
        elif case == 'suspend':
            self.assertTrue(any(e['cardId'] == 'destruction-probe' for e in s.rules_engine['suspendedCards']))
        elif row['drawPerDestroyed']:
            self.assertEqual(s.players['p2']['zones']['hand'], ['m2', 'm3'])
            self.assertEqual(s.players['p2']['zones']['deck'], ['m4', 'w2', 'pw3'])
        self.assertEqual(final['rulesEngine']['pendingChoice'], None)


def network_cases(row):
    if row['mode'] != 'play': return []
    if row['key'] == 'repress': return ['normal', 'suspend', 'exile']
    return ['normal', 'partial_reconnect', 'exile'] if row['key'] == 'convert' else ['normal']

for row in family.CONTRACTS:
    for case in network_cases(row):
        async def run(self, _driver, row=row, case=case): await self.exercise(row, case)
        setattr(TargetedDestructionIntegration, 'test_' + row['key'] + '__websocket_' + case,
            patch('main.auto_advance_rules_phases', new_callable=AsyncMock, return_value=False)(run))


if __name__ == '__main__': unittest.main()
