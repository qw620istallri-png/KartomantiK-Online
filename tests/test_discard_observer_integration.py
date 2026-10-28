"""Discard observer choices and exact results across mixed-version WebSockets."""
import copy
import json
import unittest
from unittest.mock import AsyncMock,patch
import test_state_transport_integration as transport
import test_bounce_replay_integration as passes
import test_discard_draw_clauses as fixtures
import test_discard_observers as family

main=transport.main


class DiscardObserverIntegration(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=transport.StateTransportIntegration.asyncSetUp
    asyncTearDown=transport.StateTransportIntegration.asyncTearDown
    join=transport.StateTransportIntegration.join
    receive_until=transport.StateTransportIntegration.receive_until
    send=transport.StateTransportIntegration.send
    prepare_active_rules=transport.StateTransportIntegration.prepare_active_rules
    pass_stack=passes.BounceReplayIntegration.pass_stack

    async def state(self,ws,predicate):
        m=await self.receive_until(ws,lambda m:m.get('type')=='error' or m.get('type')=='state' and predicate(m))
        self.assertEqual(m['type'],'state',m)
        return m

    async def pass_current(self):
        first=self.ws1 if self.session.rules_engine['priorityPlayerId']=='p1' else self.ws2
        await self.pass_stack(first,self.ws2 if first is self.ws1 else self.ws1)

    async def order(self,desired='exile',reconnect=False):
        s=self.session;choice=s.rules_engine['pendingChoice']
        self.assertEqual(choice['kind'],'replacement_order')
        if reconnect:
            await self.ws1.close()
            self.ws1,_=await self.join({'type':'join','code':self.code,'name':'P1','clientId':'p1'})
            await self.state(self.ws1,lambda m:(m['rulesEngine']['pendingChoice'] or {}).get('id')==choice['id'])
        actions=sorted(choice['actions'],key=lambda a:a['replacementKind']==desired)
        await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':choice['id'],'cardIds':[a['actionId'] for a in actions]})

    @staticmethod
    def resolved(m,action_id):
        return any(e.get('type')=='rules_action_resolved' and e.get('details',{}).get('actionId')==action_id for e in m.get('recentLog',[]))

    async def exercise(self,row,mode):
        bench=family.DiscardObservers();f=fixtures.DiscardDrawClauses()
        if row['key']=='kanon':
            fixture=f.world();f.kanon(fixture)
            bench.field(fixture,'m4','target')
            bench.field(fixture,'inner-deserts-134','bob',power_bonus=3)
            f.put(fixture,'p1','deck',['w2','pw3','m2'])
            fixture.rules_engine['limboDrawn']={'p1':['w2','pw3']}
            ponder=f.cid('Ponder');f.put(fixture,'p1','hand',[ponder])
            fixture.add_rules_excess_essence('p1',[{'temperament':'hollow','amount':1}])
            fixture.rules_engine['priorityPlayerId']='p1'
        else:
            fixture,host,target,cards=bench.setup_case(row,'deck',mode)
            pluff=bench.field(fixture,f.cid('Pluff'),'producer')
            queued=fixture.queue_rules_triggers(pluff['cardId'],'p1','enters_field',zone='confrontation',
                item_id=pluff['id'],face_up=True,controller_id='p1',event_controller_id='p1',defer=True)
            self.assertEqual(len(queued),1)
            fixture.queue_rules_simultaneous_actions(queued)
        s=self.session
        for key in ('card_rules','card_points','manifestation_ids','players','battlefield','tokens','rules_engine','phase_tracker'):
            setattr(s,key,copy.deepcopy(getattr(fixture,key)))
        phase=s.current_phase_id()
        await main.broadcast_state(s)
        for ws in (self.ws1,self.ws2):await self.state(ws,lambda m:m['rulesEngine']['readyPlayerIds']==['p1','p2'])
        if row['key']=='kanon':
            await self.send(self.ws1,{'type':'declare_rules_action','label':'Ponder','kind':'play_card',
                'source':{'cardId':ponder,'zone':'hand'},'abilityId':'draw-three-cards'})
            await self.state(self.ws1,lambda m:len(m['rulesEngine']['actionStack'])==1)
        root=s.rules_engine['actionStack'][-1]['id']
        await self.pass_current()
        root_state=await self.state(self.ws1,lambda m:self.resolved(m,root) or (m['rulesEngine']['pendingChoice'] or {}).get('kind')=='replacement_order')
        if not self.resolved(root_state,root):
            self.assertEqual(s.players['p1']['zones']['deck'],['m2'])
            await self.order(reconnect=True)
            root_state=await self.state(self.ws1,lambda m:self.resolved(m,root))
        peer_root=await self.state(self.ws2,lambda m:self.resolved(m,root))
        if row['key']=='kanon':
            choice=s.rules_engine['pendingChoice'];self.assertEqual(choice['kind'],'draw_replacement')
            self.assertEqual(choice['count'],2)
            self.assertNotIn('cardIds',peer_root['rulesEngine']['pendingChoice'])
            await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':choice['id'],'cardIds':['w2','pw3']})
            for n in range(2):
                await self.state(self.ws1,lambda m:(m['rulesEngine']['pendingChoice'] or {}).get('kind')=='replacement_order')
                self.assertEqual(s.players['p1']['zones']['deck'],['w2','pw3','m2'])
                await self.order(reconnect=n==0)
            await self.state(self.ws2,lambda m:(m['rulesEngine']['pendingChoice'] or {}).get('kind')=='power_loss_distribution')
            follow=s.rules_engine['pendingChoice'];self.assertEqual(follow['count'],2)
            await self.send(self.ws2,{'type':'resolve_rules_choice','choiceId':follow['id'],'option':{'itemIds':['target','target']}})
            for ws in (self.ws1,self.ws2):await self.state(ws,lambda m:m['rulesEngine']['pendingChoice'] is None and
                next(i for i in m['battlefield'] if i['id']=='target')['counters'].get('power',0)==0)
            self.assertEqual(s.rules_manifestation_characteristics(s.find_battlefield_item('target'))['power'],2)
            # New penalty bookkeeping must not reveal the identities of private exiled cards.
            for cid in ('w2','pw3'):
                encoded=json.dumps(s.serialize_for('p2','player')['recentLog'])
                self.assertNotIn(cid,encoded)
        else:
            if row['kind']=='shackle' and mode!='limbo':
                self.assertEqual(s.rules_engine['actionStack'],[])
                self.assertIsNone(s.rules_engine['pendingChoice'])
            else:
                if row['kind']=='power':
                    choice=s.rules_engine['pendingChoice'];self.assertEqual(choice['kind'],'trigger_targets')
                    await self.send(self.ws2,{'type':'resolve_rules_choice','choiceId':choice['id'],
                        'targets':[{'kind':'card','itemId':'target','cardId':'m4'}]})
                    await self.state(self.ws2,lambda m:m['rulesEngine']['pendingChoice'] is None and len(m['rulesEngine']['actionStack'])==1)
                action=s.rules_engine['actionStack'][-1]
                self.assertEqual(action['source']['itemId'],'watcher')
                await self.pass_current()
                for ws in (self.ws1,self.ws2):await self.state(ws,lambda m:self.resolved(m,action['id']))
                if row['kind']=='hand_discard':
                    choice=s.rules_engine['pendingChoice'];self.assertEqual(choice['kind'],'discard_from_hand')
                    await self.send(self.ws1,{'type':'resolve_rules_choice','choiceId':choice['id'],'cardIds':['w2']})
                    for ws in (self.ws1,self.ws2):await self.state(ws,lambda m:m['rulesEngine']['pendingChoice'] is None and
                        len(m['rulesEngine']['suspendedCards'])==2)
            host=s.find_battlefield_item('watcher')
            if row['kind']=='score_event_player':self.assertEqual(s.players['p1']['score'],45)
            if row['kind']=='score_controller':self.assertEqual(s.players['p2']['score'],55)
            if row['kind']=='power':self.assertEqual(s.rules_manifestation_characteristics(s.find_battlefield_item('target'))['power'],3)
            if row['kind']=='quiet':self.assertEqual(host['counters']['Quiet'],2)
            if row['kind']=='shackle':self.assertEqual(host['counters']['Shackle'],1 if mode=='limbo' else 2)
            self.assertEqual(s.rules_engine['actionStack'],[])
            self.assertIsNone(s.rules_engine['pendingChoice'])
        self.assertEqual(s.current_phase_id(),phase)


def network_cases(row):
    if row['key']=='kanon':return ('order_exile',)
    if row['key']=='forfog':return ('suspend','order_exile')
    if row['key']=='otranth':return ('suspend','limbo')
    return ('suspend',)
def method_name(row,case):return 'test_'+row['key']+'__websocket_'+case


for row in family.CONTRACTS:
    for case in network_cases(row):
        async def run(self,_driver,row=row,case=case):await self.exercise(row,case)
        setattr(DiscardObserverIntegration,method_name(row,case),patch('main.auto_advance_rules_phases',new_callable=AsyncMock,return_value=False)(run))


if __name__=='__main__':unittest.main()
