"""Actual entry queue, priority passes, Chain choices and mixed-version sockets."""
import unittest
from unittest.mock import AsyncMock, patch
import test_state_transport_integration as transport
import test_bounce_replay_integration as passing
import test_gorlok_draw_integration as reconnect
import test_deck_sequence_clauses as clauses

main = transport.main


class DeckSequenceIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = transport.StateTransportIntegration.asyncSetUp
    asyncTearDown = transport.StateTransportIntegration.asyncTearDown
    join = transport.StateTransportIntegration.join
    receive_until = transport.StateTransportIntegration.receive_until
    send = transport.StateTransportIntegration.send
    prepare_active_rules = transport.StateTransportIntegration.prepare_active_rules
    pass_stack = passing.BounceReplayIntegration.pass_stack
    reconnect_player = reconnect.GorlokDrawIntegration.reconnect_player

    async def start(self, name, deck, bob=False):
        f, s = clauses.DeckSequenceClauses(), self.session
        self.prepare_active_rules('confrontation_reaction')
        fixture = f.world()
        s.card_rules, s.card_points, s.manifestation_ids = fixture.card_rules, fixture.card_points, fixture.manifestation_ids
        s.phase_tracker.update(enabled=True, advanced=True, turn=2)
        s.rules_engine.update(firstManifestationComplete=True, firstManifestationTriggersQueued=True)
        f.put(s, 'p1', 'hand', ['m3'])
        f.put(s, 'p2' if name == f.BLOAT else 'p1', 'deck', deck)
        f.field(s, f.cid(name), 'host')
        if bob: f.field(s, 'inner-deserts-134', 'bob', power_bonus=2)
        s.queue_rules_battlefield_entry_triggers(f.cid(name), 'p1', 'host', True)
        await main.broadcast_state(s)
        await self.receive_until(self.ws2, lambda m: m.get('type') == 'state' and len(m['rulesEngine']['actionStack']) == 1)
        await self.pass_stack(self.ws2, self.ws1)
        state = await self.receive_until(self.ws1, lambda m: m.get('type') == 'state' and
            (m['rulesEngine']['pendingChoice'] or {}).get('kind') == 'chain_manifestation')
        await self.send(self.ws1, {'type':'resolve_rules_choice', 'choiceId':state['rulesEngine']['pendingChoice']['id'], 'cardIds':['m3']})
        actor = self.ws2 if name == f.BLOAT else self.ws1
        kind = 'reveal_hand_discard' if name == f.BLOAT else 'deck_reorder'
        state = await self.receive_until(actor, lambda m: m.get('type') == 'state' and
            (m['rulesEngine']['pendingChoice'] or {}).get('kind') == kind)
        return f, s, state

    @patch('main.auto_advance_rules_phases', new_callable=AsyncMock, return_value=False)
    async def test_bloatuba_reconnect_preserves_two_actors_and_the_remaining_duplicate(self, _driver):
        f, s, state = await self.start(clauses.DeckSequenceClauses.BLOAT, ['m2','w2','m2','m4'])
        choice_id = state['rulesEngine']['pendingChoice']['id']
        self.assertEqual(state['rulesEngine']['pendingChoice']['cardIds'], ['m2','m2'])
        self.assertNotIn('_pickPositions', state['rulesEngine']['pendingChoice'])
        reveal = next(e['details']['afterChain'] for e in state['recentLog'] if e.get('type') == 'rules_choice_resolved' and e.get('details',{}).get('afterChain'))
        self.assertEqual(reveal['cardIds'], ['m2','w2','m2'])
        restored = await self.reconnect_player('p2')
        self.assertEqual(restored['rulesEngine']['pendingChoice']['id'], choice_id)
        before = f.snapshot(s)
        await self.send(self.ws1, {'type':'resolve_rules_choice', 'choiceId':choice_id, 'option':'1'})
        await self.receive_until(self.ws1, lambda m: m.get('type') == 'error')
        self.assertEqual(f.snapshot(s), before)
        await self.send(self.ws2, {'type':'resolve_rules_choice', 'choiceId':choice_id, 'option':'1'})
        ordered = await self.receive_until(self.ws1, lambda m: m.get('type') == 'state' and
            (m['rulesEngine']['pendingChoice'] or {}).get('kind') == 'deck_reorder')
        order_id = ordered['rulesEngine']['pendingChoice']['id']
        restored = await self.reconnect_player('p1')
        self.assertEqual(restored['rulesEngine']['pendingChoice']['groups'][0]['cardIds'], ['m2','w2'])
        await self.send(self.ws1, {'type':'resolve_rules_choice', 'choiceId':order_id,
            'option':{'groups':[{'playerId':'p2','top':[],'bottom':['w2','m2']}]}})
        final = await self.receive_until(self.ws2, lambda m: m.get('type') == 'state' and m['rulesEngine']['pendingChoice'] is None)
        self.assertEqual(final['players']['p2']['zones']['deck']['cards'], ['m4','w2','m2'])
        self.assertEqual([i['cardId'] for i in s.battlefield if s.rules_field_zone(i)=='stalemate'], ['m2'])
        before = f.snapshot(s)
        await self.send(self.ws1, {'type':'resolve_rules_choice', 'choiceId':order_id,
            'option':{'groups':[{'playerId':'p2','top':[],'bottom':['w2','m2']}]}})
        await self.receive_until(self.ws1, lambda m: m.get('type') == 'error')
        self.assertEqual(f.snapshot(s), before)

    @patch('main.auto_advance_rules_phases', new_callable=AsyncMock, return_value=False)
    async def test_ponderer_private_duplicate_distribution_survives_reconnect_and_bad_reply(self, _driver):
        f, s, state = await self.start(clauses.DeckSequenceClauses.PONDER, ['m2','m2','m2','w2'])
        choice_id = state['rulesEngine']['pendingChoice']['id']
        peer = await self.receive_until(self.ws2, lambda m: m.get('type') == 'state' and
            (m['rulesEngine']['pendingChoice'] or {}).get('id') == choice_id)
        self.assertNotIn('cardIds', peer['rulesEngine']['pendingChoice']['groups'][0])
        self.assertNotIn('_deckPrefix', str(peer['rulesEngine']['pendingChoice']))
        restored = await self.reconnect_player('p1')
        self.assertEqual(restored['rulesEngine']['pendingChoice']['groups'][0]['cardIds'], ['m2','m2','m2'])
        before = f.snapshot(s)
        await self.send(self.ws1, {'type':'resolve_rules_choice', 'choiceId':choice_id,
            'option':{'groups':[{'playerId':'p1','top':['m2','m2'],'bottom':['m2'],'extra':['m2']}]}})
        await self.receive_until(self.ws1, lambda m: m.get('type') == 'error')
        self.assertEqual(f.snapshot(s), before)
        await self.send(self.ws1, {'type':'resolve_rules_choice', 'choiceId':choice_id,
            'option':{'groups':[{'playerId':'p1','top':['m2'],'bottom':['m2'],'extra':['m2']}]}})
        await self.receive_until(self.ws1, lambda m: m.get('type') == 'state' and m['rulesEngine']['pendingChoice'] is None)
        self.assertEqual(s.players['p1']['zones']['deck'], ['m2','w2','m2'])
        self.assertEqual(s.players['p1']['zones']['hand'], ['m2'])
        self.assertFalse(any(e['kind']=='cards_drawn' for e in s.rules_engine.get('observedEvents') or []))

    @patch('main.auto_advance_rules_phases', new_callable=AsyncMock, return_value=False)
    async def test_bloatuba_bob_replacement_then_order_reconnect(self, _driver):
        f, s, state = await self.start(clauses.DeckSequenceClauses.BLOAT, ['m2','w2','m2','m4'], bob=True)
        await self.send(self.ws2, {'type':'resolve_rules_choice', 'choiceId':state['rulesEngine']['pendingChoice']['id'], 'option':'1'})
        ordered = await self.receive_until(self.ws1, lambda m: m.get('type') == 'state' and
            (m['rulesEngine']['pendingChoice'] or {}).get('kind') == 'deck_reorder')
        self.assertEqual([c['cardId'] for c in s.rules_engine['suspendedCards']], ['m2'])
        self.assertFalse(any(s.rules_field_zone(i)=='stalemate' for i in s.battlefield))
        restored = await self.reconnect_player('p1')
        self.assertEqual(restored['rulesEngine']['pendingChoice']['groups'][0]['cardIds'], ['m2','w2'])
        await self.send(self.ws1, {'type':'resolve_rules_choice', 'choiceId':ordered['rulesEngine']['pendingChoice']['id'],
            'option':{'groups':[{'playerId':'p2','top':[],'bottom':['m2','w2']}]}})
        await self.receive_until(self.ws2, lambda m: m.get('type')=='state' and m['rulesEngine']['pendingChoice'] is None)
        self.assertEqual(s.players['p2']['zones']['deck'], ['m4','m2','w2'])


if __name__ == '__main__': unittest.main()
