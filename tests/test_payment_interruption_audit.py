"""Payment interruption and replay via the real WebSocket handler."""
import copy
import unittest

import test_websocket_integration as network
import main as server_main


class PaymentInterruptionAuditTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = network.WebSocketRulesIntegrationTests.asyncSetUp
    asyncTearDown = network.WebSocketRulesIntegrationTests.asyncTearDown
    join = network.WebSocketRulesIntegrationTests.join
    receive_until = network.WebSocketRulesIntegrationTests.receive_until
    send = network.WebSocketRulesIntegrationTests.send
    prepare_active_rules = network.WebSocketRulesIntegrationTests.prepare_active_rules

    def pool(self):
        return sum(t.get('counters', {}).get('essence', 0) for t in self.session.tokens if t.get('isEssence') and t['ownerId'] == 'p1')

    def choice(self, kind):
        self.prepare_active_rules('end_actions')
        rules = self.session.rules_engine
        rules['firstManifestationComplete'] = True
        self.session.players['p1']['zones']['hand'] = ['inner-deserts-047']
        self.session.add_rules_excess_essence('p1', [{'temperament': 'transcendent', 'amount': 8}])
        choice = {'id': 'payment-' + kind, 'kind': kind, 'playerId': 'p1', 'payment': '{H}{H}',
                  'sourceCardId': 'inner-deserts-091', 'controllerId': 'p2'}
        if kind == 'effect_memory_payment':
            memory = self.session.create_rules_effect_memory('p2', 'inner-deserts-047', 'return_from_limbo_end_turn')
            self.session.players['p2']['zones']['graveyard'] = ['inner-deserts-047']
            choice['memoryId'] = memory['id']
        if kind == 'stack_counter_payment':
            error, action = self.session.declare_rules_action('p1', 'Dissect', kind='play_card',
                source={'zone': 'hand', 'cardId': 'inner-deserts-047'},
                ability_id=server_main.CARD_ABILITIES['inner-deserts-047'][0]['id'])
            self.assertIsNone(error)
            # Keep an affordable response available after paying, to isolate the choice.
            self.session.players['p1']['zones']['hand'] = ['inner-deserts-047']
            self.session.add_rules_excess_essence('p1', [{'temperament': 'transcendent', 'amount': 8 - self.pool()}])
            choice.update(targetActionId=action['id'], targetKind='stack_action', mode='cancel')
        rules.update(pendingChoice=choice, priorityPlayerId='p1')
        return {'type': 'resolve_rules_choice', 'choiceId': choice['id'], 'option': 'pay', 'cardIds': []}

    async def check_payment(self, kind):
        payload = self.choice(kind)
        before = copy.deepcopy((self.session.players, self.session.tokens, self.session.rules_engine))
        await self.send(self.ws1, {**payload, 'cardIds': ['not-in-hand']})
        await self.receive_until(self.ws1, lambda m: m.get('type') == 'error')
        self.assertEqual((self.session.players, self.session.tokens, self.session.rules_engine), before)
        await self.ws1.close()
        resumed, _ = await self.join({'type': 'join', 'code': self.code, 'clientId': 'p1', 'name': 'P1'})
        state = await self.receive_until(resumed, lambda m: m.get('type') == 'state')
        self.assertEqual(state['rulesEngine']['pendingChoice']['id'], payload['choiceId'])
        self.assertEqual(self.pool(), 8)
        await self.send(self.ws2, payload)
        await self.receive_until(self.ws2, lambda m: m.get('type') == 'error')
        self.assertEqual(self.pool(), 8)
        await self.send(resumed, payload)
        await self.send(resumed, payload)
        await self.receive_until(resumed, lambda m: m.get('type') == 'state' and m['rulesEngine']['pendingChoice'] is None)
        await self.receive_until(resumed, lambda m: m.get('type') == 'error')
        self.assertEqual(self.pool(), 6)
        logs = [e for e in self.session.log if e['type'] == 'rules_choice_resolved'
                and e['details'].get('kind') == kind and e['details'].get('status') == 'paid']
        self.assertEqual(len(logs), 1)

    async def test_effect_payment_retry_reconnect_and_replay(self):
        await self.check_payment('effect_payment')

    async def test_memory_payment_retry_reconnect_and_replay(self):
        await self.check_payment('effect_memory_payment')

    async def test_immediate_payment_retry_reconnect_and_replay(self):
        await self.check_payment('immediate_effect_payment')

    async def test_counter_payment_retry_reconnect_and_replay(self):
        await self.check_payment('stack_counter_payment')

    async def test_essence_converted_before_reconnect_remains_available_once(self):
        payload = self.choice('effect_payment')
        self.session.tokens = []
        self.session.rules_engine['pendingChoice']['payment'] = '{H}'
        self.session.battlefield.append({'id': 'splendor', 'cardId': 'inner-deserts-143',
            'ownerId': 'p1', 'controllerId': 'p1', 'faceUp': True, 'fieldZone': 'field',
            'chosenTemperament': 'choleric', 'counters': {'Gem': 2}, 'rotation': 0, 'x': 740, 'y': 800})
        await self.send(self.ws1, {'type': 'spend_counter_essence', 'itemId': 'splendor',
                                 'abilityId': 'splendor-spends-a-gem-as-excess-essence'})
        await self.receive_until(self.ws1, lambda m: m.get('type') == 'state' and any(t.get('isEssence') for t in m['tokens']))
        await self.ws1.close()
        resumed, _ = await self.join({'type': 'join', 'code': self.code, 'clientId': 'p1', 'name': 'P1'})
        await self.receive_until(resumed, lambda m: m.get('type') == 'state')
        self.assertEqual(self.pool(), 1)
        self.assertEqual(self.session.find_battlefield_item('splendor')['counters']['Gem'], 1)
        await self.send(resumed, payload)
        await self.send(resumed, payload)
        await self.receive_until(resumed, lambda m: m.get('type') == 'state' and m['rulesEngine']['pendingChoice'] is None)
        await self.receive_until(resumed, lambda m: m.get('type') == 'error')
        self.assertEqual(self.pool(), 0)
        self.assertEqual(self.session.find_battlefield_item('splendor')['counters']['Gem'], 1)


    async def test_replacement_order_resumes_and_logs_the_stack_resolution_once(self):
        self.prepare_active_rules('end_actions')
        self.session.rules_engine.update(firstManifestationComplete=True, lastConfrontationWinnerId='p2')
        self.session.players['p1']['zones']['hand'] = ['inner-deserts-047']
        self.session.add_rules_excess_essence('p1', [{'temperament': 'transcendent', 'amount': 8}])
        cid = next(cid for cid, meta in self.session.card_rules.items() if meta.get('type') == 'manifestation' and meta.get('power', 0) > 0)
        self.session.battlefield = [
            {'id': 'bob', 'ownerId': 'p1', 'controllerId': 'p1', 'cardId': 'inner-deserts-134',
             'fieldZone': 'confrontation', 'faceUp': True, 'rotation': 0, 'x': 700, 'y': 800, 'counters': {'power': 3}},
            {'id': 'target', 'ownerId': 'p2', 'controllerId': 'p2', 'cardId': cid,
             'fieldZone': 'confrontation', 'faceUp': True, 'rotation': 0, 'x': 700, 'y': 525, 'counters': {}}]
        self.session.rules_engine['ongoingEffects'] = [{'id': 'nullify', 'actionId': 'nullify-action',
            'controllerId': 'p1', 'kind': 'exile_incoming_manifestations', 'duration': 'until_end_of_turn',
            'startedTurn': self.session.phase_tracker['turn'], 'target': {'kind': 'player', 'playerId': 'p2'},
            'source': {'cardId': '36l7iw5m5hk1pmr_en'}}]
        self.session.rules_engine['actionStack'] = [{'id': 'move-test', 'kind': 'triggered_effect',
            'label': 'Destroy', 'controllerId': 'p1', 'source': {'cardId': '36l7iw5m5hk1pmr_en'},
            'targets': [{'kind': 'card', 'itemId': 'target', 'cardId': cid}],
            'ability': {'id': 'destroy', 'result': {'kind': 'move_target', 'zone': 'graveyard', 'reason': 'destroy'}}}]
        self.assertEqual(self.session.resolve_rules_top_action()['status'], 'choice_required')
        choice = self.session.rules_engine['pendingChoice']
        order = [e['actionId'] for e in sorted(choice['actions'], key=lambda e: e['replacementKind'] == 'exile')]
        await self.ws1.close()
        resumed, _ = await self.join({'type': 'join', 'code': self.code, 'clientId': 'p1', 'name': 'P1'})
        restored = await self.receive_until(resumed, lambda m: m.get('type') == 'state')
        self.assertEqual(restored['rulesEngine']['pendingChoice']['id'], choice['id'])
        payload = {'type': 'resolve_rules_choice', 'choiceId': choice['id'], 'cardIds': order}
        await self.send(resumed, payload)
        await self.send(resumed, payload)
        await self.receive_until(resumed, lambda m: m.get('type') == 'state' and m['rulesEngine']['pendingChoice'] is None)
        await self.receive_until(resumed, lambda m: m.get('type') == 'error')
        self.assertIn(cid, self.session.players['p2']['zones']['exile'])
        self.assertFalse(self.session.rules_engine['actionStack'])
        logs = [e for e in self.session.log if e['type'] == 'rules_action_resolved' and e['details']['actionId'] == 'move-test']
        self.assertEqual(len(logs), 1)
