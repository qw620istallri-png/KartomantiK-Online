"""Real socket answers/reconnect with explicit Vessel resolution fixtures."""
import copy
import unittest
from unittest.mock import AsyncMock, patch
import test_state_transport_integration as transport
import test_gorlok_draw_integration as reconnect
import test_vessel_choice_clauses as clauses

main = transport.main


class VesselChoiceIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = transport.StateTransportIntegration.asyncSetUp
    asyncTearDown = transport.StateTransportIntegration.asyncTearDown
    join = transport.StateTransportIntegration.join
    receive_until = transport.StateTransportIntegration.receive_until
    send = transport.StateTransportIntegration.send
    prepare_active_rules = transport.StateTransportIntegration.prepare_active_rules
    reconnect_player = reconnect.GorlokDrawIntegration.reconnect_player

    async def prepare_pick(self, purpose):
        f = clauses.VesselChoiceClauses()
        fixture = f.pick(purpose)
        s = self.session
        self.prepare_active_rules('confrontation_reaction')
        s.card_rules = fixture.card_rules
        s.card_points = fixture.card_points
        s.manifestation_ids = fixture.manifestation_ids
        s.players = copy.deepcopy(fixture.players)
        s.battlefield = copy.deepcopy(fixture.battlefield)
        s.rules_engine = copy.deepcopy(fixture.rules_engine)
        s.phase_tracker = copy.deepcopy(fixture.phase_tracker)
        await main.broadcast_state(s)
        state = await self.receive_until(self.ws1, lambda m: m.get('type') == 'state' and
            (m['rulesEngine']['pendingChoice'] or {}).get('purpose') == purpose)
        return f, s, state['rulesEngine']['pendingChoice']

    @patch('main.auto_advance_rules_phases', new_callable=AsyncMock, return_value=False)
    async def test_gummo_reorder_shuffle_and_reconnect_keep_original_candidates(self, _driver):
        f, s, choice = await self.prepare_pick('gummo')
        original = copy.deepcopy(s.rules_engine['pendingChoice']['_vesselCards'])
        # An open choice blocks manual zone edits. Reordering is a separate
        # protocol fixture before restoring the already-built choice.
        await self.send(self.ws1, {'type': 'shuffle', 'ownerId': 'p1', 'zone': 'receptacle'})
        await self.receive_until(self.ws1, lambda m: m.get('type') == 'error')
        pending = s.rules_engine['pendingChoice']
        s.rules_engine['pendingChoice'] = None
        await self.send(self.ws1, {'type': 'reorder', 'ownerId': 'p1', 'zone': 'receptacle', 'order': ['m4', 'm3', 'm3']})
        await self.receive_until(self.ws1, lambda m: m.get('type') == 'state' and m['players']['p1']['zones']['receptacle']['cards'] == ['m4', 'm3', 'm3'])
        await self.send(self.ws1, {'type': 'shuffle', 'ownerId': 'p1', 'zone': 'receptacle'})
        await self.receive_until(self.ws1, lambda m: m.get('type') == 'state' and any(
            e.get('type') == 'shuffle' for e in m.get('recentLog', [])))
        self.assertTrue(all(s.rules_vessel_entry_present('p1', e) for e in original))
        s.rules_engine['pendingChoice'] = pending
        await main.broadcast_state(s)
        restored = await self.reconnect_player('p1')
        self.assertEqual(restored['rulesEngine']['pendingChoice']['cardIds'], choice['cardIds'])
        self.assertNotIn('_vesselCards', restored['rulesEngine']['pendingChoice'])
        await self.send(self.ws1, {'type':'resolve_rules_choice', 'choiceId':choice['id'], 'option':'1'})
        await self.receive_until(self.ws1, lambda m: m.get('type') == 'state' and m['rulesEngine']['pendingChoice'] is None)
        self.assertEqual(s.find_battlefield_item('gummo')['gummoCopy'], 'm3')

    @patch('main.auto_advance_rules_phases', new_callable=AsyncMock, return_value=False)
    async def test_wish_reconnect_owner_selects_second_copy_and_cannot_repeat(self, _driver):
        f, s, choice = await self.prepare_pick('wish')
        original = copy.deepcopy(s.rules_engine['pendingChoice']['_vesselCards'])
        restored = await self.reconnect_player('p2')
        self.assertEqual(restored['rulesEngine']['pendingChoice']['id'], choice['id'])
        before = f.snapshot(s)
        await self.send(self.ws1, {'type':'resolve_rules_choice', 'choiceId':choice['id'], 'option':'1'})
        await self.receive_until(self.ws1, lambda m: m.get('type') == 'error')
        self.assertEqual(f.snapshot(s), before)
        await self.send(self.ws2, {'type':'resolve_rules_choice', 'choiceId':choice['id'], 'option':'1'})
        await self.receive_until(self.ws1, lambda m: m.get('type') == 'state' and m['rulesEngine']['pendingChoice'] is None)
        self.assertEqual(s.players['p1']['zones']['deck'], ['m3'])
        self.assertEqual(s.players['p2']['zones']['deck'], ['m2'])
        self.assertTrue(s.rules_vessel_entry_present('p2', original[0]))
        self.assertFalse(s.rules_vessel_entry_present('p2', original[1]))
        before = f.snapshot(s)
        await self.send(self.ws2, {'type':'resolve_rules_choice', 'choiceId':choice['id'], 'option':'1'})
        await self.receive_until(self.ws2, lambda m: m.get('type') == 'error')
        self.assertEqual(f.snapshot(s), before)

    @patch('main.auto_advance_rules_phases', new_callable=AsyncMock, return_value=False)
    async def test_pesco_reconnect_rejects_stale_copy_then_takes_survivor(self, _driver):
        f, s, choice = await self.prepare_pick('pescojolero')
        indices = [i for i, cid in enumerate(choice['cardIds']) if cid == 'm3']
        s.take_zone_card('p2', 'receptacle', 'm3')  # Deliberate stale-answer stimulus.
        await self.reconnect_player('p1')
        before = f.snapshot(s)
        await self.send(self.ws1, {'type':'resolve_rules_choice', 'choiceId':choice['id'], 'option':str(indices[0])})
        await self.receive_until(self.ws1, lambda m: m.get('type') == 'error')
        self.assertEqual(f.snapshot(s), before)
        await self.send(self.ws1, {'type':'resolve_rules_choice', 'choiceId':choice['id'], 'option':str(indices[1])})
        await self.receive_until(self.ws1, lambda m: m.get('type') == 'state' and m['rulesEngine']['pendingChoice'] is None)
        placed = [i for i in s.battlefield if i['cardId'] == 'm3']
        self.assertEqual([(i['ownerId'], i['controllerId'], s.rules_field_zone(i)) for i in placed], [('p1','p1','interzone')])
        self.assertIn('m4', s.players['p2']['zones']['receptacle'])


if __name__ == '__main__':
    unittest.main()
