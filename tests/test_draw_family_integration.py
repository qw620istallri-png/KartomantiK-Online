"""Mixed-version WS draw/discard clauses, including replacement continuations.

Trigger stimuli and replacement states are controlled fixtures. Voluntary
abilities are declared and paid through actual protocol messages.
"""
import copy
import unittest
from unittest.mock import AsyncMock,patch
import test_state_transport_integration as transport
import test_bounce_replay_integration as passes
import test_draw_discard_family as family

main=transport.main


class DrawFamilyIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=transport.StateTransportIntegration.asyncSetUp
    asyncTearDown=transport.StateTransportIntegration.asyncTearDown
    join=transport.StateTransportIntegration.join
    receive_until=transport.StateTransportIntegration.receive_until
    send=transport.StateTransportIntegration.send
    prepare_active_rules=transport.StateTransportIntegration.prepare_active_rules
    pass_stack=passes.BounceReplayIntegration.pass_stack

    @staticmethod
    def hand_count(message,player):
        hand=message['players'][player]['zones']['hand']
        return len(hand['cards']) if 'cards' in hand else hand['count']

    async def choice_state(self,ws,kind):
        message=await self.receive_until(ws,lambda m:m.get('type')=='error' or
            m.get('type')=='state' and (m['rulesEngine']['pendingChoice'] or {}).get('kind')==kind)
        self.assertEqual(message['type'],'state',message)
        return message['rulesEngine']['pendingChoice']

    async def exercise(self,row,preferred='suspend'):
        f=family.DrawDiscardFamily();fixture,host,recipient=f.setup_case(row)
        if row['mode']=='event':f.begin(fixture,row,host,recipient)
        s=self.session
        for key in ('card_rules','card_points','manifestation_ids','players','battlefield','tokens','rules_engine','phase_tracker'):
            setattr(s,key,copy.deepcopy(getattr(fixture,key)))
        if row['mode']=='event':action=s.rules_engine['actionStack'][0]
        else:
            source={'cardId':row['cardId'],'zone':'hand'} if row['mode']=='play' else {
                'cardId':row['cardId'],'zone':'battlefield','itemId':host['id']}
            await self.send(self.ws1,{'type':'declare_rules_action','label':row['name'],
                'kind':'play_card' if row['mode']=='play' else 'activated_effect','source':source,
                'abilityId':row['abilityId'],'targets':f.targets(row,recipient)})
            state=await self.receive_until(self.ws1,lambda m:m.get('type')=='error' or
                m.get('type')=='state' and len(m['rulesEngine']['actionStack'])==1)
            self.assertEqual(state['type'],'state',state);action=s.rules_engine['actionStack'][0]
        if row['kind']=='draw':
            kanon=next(c['id'] for c in main.CARD_DATA if c['name']=='Kanon, the Deathdealer')
            f.field(s,kanon,'kanon',owner=f.other(recipient))
        else:
            f.field(s,'inner-deserts-134','bob',owner=recipient,power_bonus=3 if row['kind']=='discard' else 0)
            if row['kind']=='discard':s.rules_engine['limboDrawn']={recipient:['w2']}
        before=copy.deepcopy(s.players[recipient]['zones'])
        await main.broadcast_state(s)
        resolved_states={}
        for ws in (self.ws1,self.ws2):
            resolved_states[ws]=await self.receive_until(ws,lambda m:m.get('type')=='state' and
                any(a['id']==action['id'] for a in m['rulesEngine']['actionStack']))
        first=self.ws1 if s.rules_engine['priorityPlayerId']=='p1' else self.ws2
        second=self.ws2 if first is self.ws1 else self.ws1
        await self.pass_stack(first,second)
        for ws in (self.ws1,self.ws2):
            await self.receive_until(ws,lambda m:m.get('type')=='state' and
                any(e.get('type')=='rules_action_resolved' and e.get('details',{}).get('actionId')==action['id']
                    for e in m.get('recentLog',[])))
        chooser=self.ws1 if recipient=='p1' else self.ws2
        if row['kind']=='draw':
            choice=s.rules_engine['pendingChoice'];self.assertEqual(choice['kind'],'draw_replacement')
            n=row['expectedAmount'];selected=['m2','m3'][:(n+1)//2]
            self.assertEqual(choice['count'],len(selected))
            await self.send(chooser,{'type':'resolve_rules_choice','choiceId':choice['id'],'cardIds':selected})
            expected_hand=before['hand']+['m2','m3','m4'][:n][len(selected):]
        elif row['kind']=='discard':
            choice=s.rules_engine['pendingChoice'];self.assertEqual(choice['kind'],'discard_from_hand')
            await self.send(chooser,{'type':'resolve_rules_choice','choiceId':choice['id'],'cardIds':['w2']})
            order=await self.choice_state(chooser,'replacement_order')
            self.assertEqual(s.players[recipient]['zones']['hand'],before['hand'])
            actions=sorted(order['actions'],key=lambda a:a['replacementKind']==preferred)
            await self.send(chooser,{'type':'resolve_rules_choice','choiceId':order['id'],
                'cardIds':[a['actionId'] for a in actions]})
            expected_hand=['pw3']
        else:expected_hand=before['hand']
        for ws in (self.ws1,self.ws2):
            final=resolved_states[ws] if row['kind']=='mill' else await self.receive_until(ws,lambda m:m.get('type')=='error' or m.get('type')=='state' and
                m['rulesEngine']['pendingChoice'] is None and not m['rulesEngine']['actionStack'] and
                (len(m['rulesEngine']['suspendedCards'])==1 if row['kind']=='mill' or row['kind']=='discard' and preferred=='suspend'
                 else self.hand_count(m,recipient)==len(expected_hand)))
            self.assertEqual(final['type'],'state',final)
            self.assertEqual(self.hand_count(final,recipient),len(expected_hand))
        self.assertEqual(s.players[recipient]['zones']['hand'],expected_hand)
        if row['kind']=='draw':self.assertEqual(s.players[recipient]['zones']['deck'],['m2','m3','m4','w2'][row['expectedAmount']:])
        if row['kind']=='discard':
            self.assertEqual(s.players[recipient]['zones']['exile'],['w2'] if preferred=='exile' else [])
            self.assertEqual([c['cardId'] for c in s.rules_engine['suspendedCards']],['w2'] if preferred=='suspend' else [])
        if row['kind']=='mill':self.assertEqual([c['cardId'] for c in s.rules_engine['suspendedCards']],['m2'])


def network_cases(row):return ['suspend','exile'] if row['key']=='wheel' else ['suspend']
def method_name(row,case):return 'test_'+row['key']+'__websocket_'+case


for row in family.CONTRACTS:
    for case in network_cases(row):
        async def guarded(self,_driver,row=row,case=case):await self.exercise(row,case)
        setattr(DrawFamilyIntegration,method_name(row,case),
            patch('main.auto_advance_rules_phases',new_callable=AsyncMock,return_value=False)(guarded))


if __name__=='__main__':unittest.main()
