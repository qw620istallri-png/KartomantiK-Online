"""Representative permission classes and Jigon casts over real mixed-version sockets."""
import copy
import unittest
from unittest.mock import AsyncMock, patch
import test_state_transport_integration as transport
import test_bounce_replay_integration as passes
import test_support_permissions as family
import test_concealed_play_permissions as jig

NETWORK_CASES = (
    ('Wind Sprout', 'hand'), ('Forest Guide', 'interzone'),
    ('Bibi, the Confused', 'hand'), ('Jesterina, the Decadent', 'hand'),
    ('Buuz, the Helicoidal', 'hand'), ('Nubilung, the Elder', 'stalemate'),
)


class SupportPermissionsIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = transport.StateTransportIntegration.asyncSetUp
    asyncTearDown = transport.StateTransportIntegration.asyncTearDown
    join = transport.StateTransportIntegration.join
    receive_until = transport.StateTransportIntegration.receive_until
    send = transport.StateTransportIntegration.send
    prepare_active_rules = transport.StateTransportIntegration.prepare_active_rules
    pass_stack = passes.BounceReplayIntegration.pass_stack

    def install(self, fixture):
        self.prepare_active_rules('confrontation_reaction')
        for attr in ('card_rules', 'card_points', 'manifestation_ids', 'players', 'battlefield', 'tokens', 'rules_engine', 'phase_tracker'):
            setattr(self.session, attr, copy.deepcopy(getattr(fixture, attr)))
        # Unit fixtures omit visual geometry; socket serialization requires it.
        for item in self.session.battlefield:
            for key in ('rotation', 'x', 'y'): item.setdefault(key, 0)

    async def declare_and_resolve(self, payload):
        await self.send(self.ws1, {'type': 'declare_rules_action', **payload})
        queued = await self.receive_until(self.ws1, lambda m: m.get('type') == 'error' or
            m.get('type') == 'state' and len(m['rulesEngine']['actionStack']) == 1)
        self.assertEqual(queued['type'], 'state', queued)
        action_id = queued['rulesEngine']['actionStack'][0]['id']
        await self.pass_stack(self.ws2, self.ws1)
        for ws in (self.ws1, self.ws2):
            await self.receive_until(ws, lambda m: m.get('type') == 'state' and
                any(e.get('type') == 'rules_action_resolved' and e.get('details', {}).get('actionId') == action_id
                    for e in m.get('recentLog', [])))
        return queued

    async def support(self, name, zone):
        row = next(r for r in family.CONTRACTS if r['name'] == name)
        f = family.SupportPermissions()
        fixture, item = f.setup_card(row, zone)
        self.install(fixture)
        item = self.session.find_battlefield_item(item['id']) if item else None
        args = f.declaration(row, item)
        args['asSupport'] = args.pop('as_support')
        args['abilityId'] = args.pop('ability_id')
        queued = await self.declare_and_resolve({'label': name, **args})
        if zone != 'hand':
            pending = next(i for i in queued['battlefield'] if i['id'] == item['id'])
            self.assertEqual(pending['fieldZone'], zone)
            self.assertFalse(pending.get('isSupport'))
        arrival = next(i for i in self.session.battlefield if i['cardId'] == row['cardId'])
        self.assertEqual((arrival['fieldZone'], arrival['isSupport'], arrival['ownerId']), ('confrontation', True, 'p1'))
        self.assertEqual(len(f.history(self.session)), 1)

    async def jigon(self, free):
        f = jig.ConcealedPlayPermissions()
        fixture, hidden, target = f.setup_hidden(free=free)
        if free: fixture.tokens = []
        self.install(fixture)
        queued = await self.declare_and_resolve({'label': 'Strengthen', 'kind': 'play_card',
            'source': {'cardId': f.STRENGTHEN, 'itemId': hidden['id'], 'zone': 'battlefield'},
            'abilityId': 'strengthen-power-modifier',
            'targets': [{'kind': 'card', 'itemId': target['id'], 'cardId': target['cardId']}]})
        self.assertFalse(any(i['id'] == hidden['id'] for i in queued['battlefield']))
        paid = queued['rulesEngine']['actionStack'][0]['cost']['tributeRequirements']
        self.assertEqual(paid, {} if free else {'hollow': 1})
        self.assertEqual(self.session.rules_manifestation_characteristics(
            self.session.find_battlefield_item(target['id']))['power'], 4)
        self.assertIn(f.STRENGTHEN, self.session.players['p1']['zones']['graveyard'])


for name, zone in NETWORK_CASES:
    row = next(r for r in family.CONTRACTS if r['name'] == name)
    async def run(self, _driver, name=name, zone=zone): await self.support(name, zone)
    setattr(SupportPermissionsIntegration, 'test_' + row['key'] + '__websocket_' + zone,
            patch('main.auto_advance_rules_phases', new_callable=AsyncMock, return_value=False)(run))
for free in (False, True):
    async def run(self, _driver, free=free): await self.jigon(free)
    setattr(SupportPermissionsIntegration, 'test_jigon__websocket_' + ('free' if free else 'paid'),
            patch('main.auto_advance_rules_phases', new_callable=AsyncMock, return_value=False)(run))
