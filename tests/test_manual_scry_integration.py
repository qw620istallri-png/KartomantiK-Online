"""Manual private Scry and reordering through two production sockets."""
import unittest
import test_state_transport_integration as transport

class ManualScryIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=transport.StateTransportIntegration.asyncSetUp
    asyncTearDown=transport.StateTransportIntegration.asyncTearDown
    join=transport.StateTransportIntegration.join
    receive_until=transport.StateTransportIntegration.receive_until
    send=transport.StateTransportIntegration.send

    def prepare(self):
        s=self.session
        s.rules_engine.update(enabled=False,deckConfirmedPlayerIds=['p1','p2'],readyPlayerIds=['p1','p2'])
        s.phase_tracker.update(enabled=False,turn=2)
        cards=[c['id'] for c in transport.main.CARD_DATA[:15]]
        s.players['p1']['zones']['deck']=cards[:]
        s.players['p1']['zoneOwners']['deck']={c:'p1' for c in cards}
        return cards

    async def test_scry_top_ten_only_sent_to_requesting_player_without_changing_order(self):
        cards=self.prepare()
        await self.send(self.ws1,{'type':'scry','count':10})
        peek=await self.receive_until(self.ws1,lambda m:m.get('type')=='scry_result')
        self.assertEqual(peek['cards'],cards[:10])
        # Scry intentionally sends no state broadcast. Ask the peer to resync
        # to verify the resulting public log without waiting for a non-event.
        await self.send(self.ws2,{'type':'request_state'})
        await self.receive_until(self.ws2,lambda m:m.get('type')=='state' and any(e['type']=='scry' for e in m.get('recentLog',[])))
        self.assertFalse(any(m.get('type')=='scry_result' for m in self.wires[self.ws2]))
        self.assertEqual(self.session.players['p1']['zones']['deck'],cards)
        self.assertFalse(any('cards' in e.get('details',{}) for e in self.baselines[self.ws2]['recentLog'] if e['type']=='scry'))

    async def test_scry_menu_bottom_move_preserves_deck_count_and_private_peer_view(self):
        cards=self.prepare()
        await self.send(self.ws1,{'type':'scry','count':3})
        await self.receive_until(self.ws1,lambda m:m.get('type')=='scry_result')
        await self.send(self.ws1,{'type':'move_card','fromOwnerId':'p1','fromZone':'deck','toOwnerId':'p1','toZone':'deck','cardId':cards[1],'position':'bottom'})
        peer=await self.receive_until(self.ws2,lambda m:m.get('type')=='state' and any(e['type']=='move_card' for e in m.get('recentLog',[])))
        self.assertEqual(self.session.players['p1']['zones']['deck'],[cards[0],*cards[2:],cards[1]])
        self.assertNotIn('cards',peer['players']['p1']['zones']['deck'])
        log=next(e for e in peer['recentLog'] if e['type']=='move_card')
        self.assertNotIn('cardId',log['details'])

    async def test_observer_cannot_scry(self):
        self.prepare()
        observer,_=await self.join({'type':'join','code':self.session.code_observer,'name':'Observer','clientId':'watch'})
        await self.send(observer,{'type':'scry','count':10})
        error=await self.receive_until(observer,lambda m:m.get('type')=='error')
        self.assertIn('cannot',error['message'])

if __name__=='__main__':unittest.main()
