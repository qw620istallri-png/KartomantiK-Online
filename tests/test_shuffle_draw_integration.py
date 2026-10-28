"""Real mixed-version messages for shuffle/draw privacy and continuations."""
import copy
import json
import unittest
from unittest.mock import AsyncMock,patch
import test_state_transport_integration as transport
import test_bounce_replay_integration as passes
import test_draw_family_integration as counts
import test_shuffle_draw as family

main=transport.main


class ShuffleDrawIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=transport.StateTransportIntegration.asyncSetUp
    asyncTearDown=transport.StateTransportIntegration.asyncTearDown
    join=transport.StateTransportIntegration.join
    receive_until=transport.StateTransportIntegration.receive_until
    send=transport.StateTransportIntegration.send
    prepare_active_rules=transport.StateTransportIntegration.prepare_active_rules
    pass_stack=passes.BounceReplayIntegration.pass_stack
    hand_count=staticmethod(counts.DrawFamilyIntegration.hand_count)

    async def state(self,ws,predicate):
        message=await self.receive_until(ws,lambda m:m.get('type')=='error' or m.get('type')=='state' and predicate(m))
        self.assertEqual(message['type'],'state',message)
        return message

    async def exercise(self,row,case):
        f=family.ShuffleDraw();fixture=f.setup_case(row)
        if case!='normal':f.kanon(fixture,'p2')
        if case=='two_kanons':f.kanon(fixture,'p1')
        if case=='followup':
            target=f.field(fixture,'m4','penalty-target')
            for _ in range(2):fixture.put_zone_card('p1','deck','w2','p1','top')
        s=self.session
        for key in ('card_rules','card_points','manifestation_ids','players','battlefield','tokens','rules_engine','phase_tracker'):
            setattr(s,key,copy.deepcopy(getattr(fixture,key)))
        phase=s.current_phase_id()
        await main.broadcast_state(s)
        for ws in (self.ws1,self.ws2):await self.state(ws,lambda m:m['rulesEngine']['readyPlayerIds']==['p1','p2'])
        await self.send(self.ws1,{'type':'declare_rules_action','label':row['name'],'kind':'play_card',
            'source':{'cardId':row['cardId'],'zone':'hand'},'abilityId':row['abilityId']})
        if not row['allPlayers']:
            await self.state(self.ws1,lambda m:len(m['rulesEngine']['actionStack'])==1)
            first=self.ws1 if s.rules_engine['priorityPlayerId']=='p1' else self.ws2
            await self.pass_stack(first,self.ws2 if first is self.ws1 else self.ws1)
        resolved_states={}
        for ws in (self.ws1,self.ws2):
            resolved_states[ws]=await self.state(ws,lambda m:(m['rulesEngine'].get('lastResolvedAction') or {}).get('source',{}).get('cardId')==row['cardId'])
        if case!='normal':
            choice=s.rules_engine['pendingChoice'];self.assertEqual(choice['kind'],'draw_replacement')
            self.assertEqual(len(s.players['p2']['zones']['hand']),0 if row['allPlayers'] else 2)
            # A fresh full snapshot must preserve the private chooser after reconnect.
            await self.ws1.close()
            self.ws1,_=await self.join({'type':'join','code':self.code,'name':'P1','clientId':'p1'})
            resumed=await self.state(self.ws1,lambda m:(m['rulesEngine']['pendingChoice'] or {}).get('id')==choice['id'])
            self.assertEqual(resumed['rulesEngine']['pendingChoice']['cardIds'],choice['_cardIds'])
            await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':choice['id'],'cardIds':[]})
            invalid=await self.receive_until(self.ws1,lambda m:m.get('type')=='error')
            self.assertEqual(invalid['type'],'error');self.assertEqual(s.rules_engine['pendingChoice']['id'],choice['id'])
            selected=['w2','w2'] if case=='followup' else choice['_cardIds'][:choice['count']]
            await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':choice['id'],'cardIds':selected})
            if case=='two_kanons':
                next_state=await self.state(self.ws2,lambda m:(m['rulesEngine']['pendingChoice'] or {}).get('playerId')=='p2')
                next_choice=next_state['rulesEngine']['pendingChoice']
                self.assertEqual(next_choice['kind'],'draw_replacement')
                await self.send(self.ws2,{'type':'resolve_rules_choice','choiceId':next_choice['id'],
                    'cardIds':s.rules_engine['pendingChoice']['_cardIds'][:2]})
            elif case=='followup':
                await self.state(self.ws2,lambda m:(m['rulesEngine']['pendingChoice'] or {}).get('kind')=='power_loss_distribution')
                self.assertEqual(s.players['p2']['zones']['hand'],[])
                follow=s.rules_engine['pendingChoice']
                await self.send(self.ws2,{'type':'resolve_rules_choice','choiceId':follow['id'],
                    'option':{'itemIds':[target['id'],target['id']]}})
        for ws,pid in ((self.ws1,'p1'),(self.ws2,'p2')):
            final=resolved_states[ws] if case=='normal' else await self.state(ws,lambda m:m['rulesEngine']['pendingChoice'] is None and not m['rulesEngine']['actionStack']
                and (m['rulesEngine'].get('lastResolvedAction') or {}).get('source',{}).get('cardId')==row['cardId'])
            expected1=row['expectedDraw'] if case=='normal' else row['expectedDraw']//2
            expected2=2 if not row['allPlayers'] or case=='two_kanons' else 4
            self.assertEqual(self.hand_count(final,'p1'),expected1)
            self.assertEqual(self.hand_count(final,'p2'),expected2)
            result=json.dumps(final['rulesEngine']['lastResolvedAction']['effectResult'])
            other='p2' if pid=='p1' else 'p1'
            for cid in s.players[other]['zones']['hand']:self.assertNotIn(cid,result)
        self.assertEqual(s.current_phase_id(),phase)
        if case=='followup':self.assertEqual(s.rules_manifestation_characteristics(s.find_battlefield_item(target['id']))['power'],2)
        if case!='normal':
            before=copy.deepcopy(s.players)
            await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':choice['id'],'cardIds':selected})
            await self.receive_until(self.ws1,lambda m:m.get('type')=='error')
            self.assertEqual(s.players,before)


def network_cases(row):return ['normal','two_kanons','followup'] if row['allPlayers'] else ['normal','kanon']
def method_name(row,case):return 'test_'+row['key']+'__websocket_'+case


for row in family.CONTRACTS:
    for case in network_cases(row):
        async def guarded(self,_driver,row=row,case=case):
            with patch('game.effects.cards.random.shuffle',side_effect=lambda cards:None):await self.exercise(row,case)
        setattr(ShuffleDrawIntegration,method_name(row,case),
            patch('main.auto_advance_rules_phases',new_callable=AsyncMock,return_value=False)(guarded))


if __name__=='__main__':unittest.main()
