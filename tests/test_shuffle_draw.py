"""Independent printed quantities, draw continuations, immunity and privacy."""
import copy
import hashlib
import json
import sys
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import main
import test_discard_draw_clauses as fixtures
from session import ADVANCED_PHASES

ROOT=Path(__file__).resolve().parents[1]
CONTRACTS=json.loads((ROOT/'audit/shuffle-draw.json').read_text(encoding='utf-8'))['contracts']
for row in CONTRACTS:
    card=next(c for c in main.CARD_DATA if c['id']==row['cardId'])
    assert row['printedText']==card['effect'] and row['name']==card['name']
    assert row['printedTextSha256']==hashlib.sha256(card['effect'].encode()).hexdigest()


class ShuffleDraw(unittest.TestCase):
    world=fixtures.DiscardDrawClauses.world
    field=staticmethod(fixtures.DiscardDrawClauses.field)
    snapshot=fixtures.DiscardDrawClauses.snapshot

    def setup_case(self,row,actor='p1',deck_size=10,hand_size=2):
        s=self.world()
        for pid in s.players:
            for zone,count in (('deck',deck_size),('hand',hand_size)):
                for n in range(count):
                    cid='secret-'+pid+'-'+zone+'-'+str(n)
                    s.card_rules[cid]={'type':'manifestation','power':2,'temperaments':['phlegmatic'],'powerCost':'{G}{G}'}
                    s.manifestation_ids.add(cid)
                    s.put_zone_card(pid,zone,cid,pid,'bottom')
        s.put_zone_card(actor,'hand',row['cardId'],actor)
        s.add_rules_excess_essence(actor,[{'temperament':'capricious','amount':20}])
        s.rules_engine['priorityPlayerId']=actor
        s.phase_tracker['index']=ADVANCED_PHASES.index('confrontation_reaction' if row['allPlayers'] else 'confrontation_before_revelation')
        return s

    def begin(self,s,row,actor='p1'):
        error,action=s.declare_rules_action(actor,row['name'],kind='play_card',
            source={'cardId':row['cardId'],'zone':'hand'},ability_id=row['abilityId'])
        self.assertIsNone(error)
        spent=Counter()
        for payment in action['cost']['essenceSpent']:spent[payment['temperament']]+=payment['amount']
        self.assertEqual(dict(spent),row['essenceCost'])
        self.assertEqual(bool(action.get('immediate')),row['allPlayers'])
        return action

    def resolve(self,s):
        with patch('game.effects.cards.random.shuffle',side_effect=lambda cards:None):
            return s.resolve_rules_top_action()

    def choose(self,s,**kwargs):
        choice=s.rules_engine['pendingChoice'];self.assertIsNotNone(choice)
        error,result=s.resolve_rules_choice(choice['playerId'],choice['id'],**kwargs)
        self.assertIsNone(error)
        return result

    @staticmethod
    def affected(row,actor='p1'):return ['p1','p2'] if row['allPlayers'] else [actor]

    def check_normal(self,row,actor='p1',deck_size=10,hand_size=2):
        s=self.setup_case(row,actor,deck_size,hand_size);self.begin(s,row,actor)
        before=copy.deepcopy(s.players)
        self.resolve(s)
        for pid in s.players:
            old=before[pid]['zones'];now=s.players[pid]['zones']
            if pid in self.affected(row,actor):
                expected=min(row['expectedDraw'],deck_size+hand_size)
                self.assertEqual(len(now['hand']),expected)
                self.assertEqual(len(now['deck']),deck_size+hand_size-expected)
                self.assertEqual(Counter(now['hand']+now['deck']),Counter(old['hand']+old['deck']))
            else:self.assertEqual((now['hand'],now['deck']),(old['hand'],old['deck']))
        self.assertNotIn(row['cardId'],s.players[actor]['zones']['deck'])
        self.assertEqual(s.players[actor]['zones']['graveyard'],[row['cardId']])
        self.assertIsNone(s.rules_engine['pendingChoice'])
        return s

    def check_empty(self,row):self.check_normal(row,deck_size=0,hand_size=0)
    def check_short_pool(self,row):self.check_normal(row,deck_size=1,hand_size=1)
    def check_other_actor(self,row):self.check_normal(row,actor='p2')

    def check_duplicates(self,row):
        s=self.setup_case(row,deck_size=0,hand_size=0)
        for pid in s.players:
            for _ in range(8):s.put_zone_card(pid,'deck','m2',pid,'bottom')
            for _ in range(2):s.put_zone_card(pid,'hand','m2',pid,'bottom')
        self.begin(s,row);self.resolve(s)
        for pid in self.affected(row):
            self.assertEqual(s.players[pid]['zones']['hand'],['m2']*row['expectedDraw'])
            self.assertEqual(s.players[pid]['zones']['deck'],['m2']*(10-row['expectedDraw']))

    def check_draw_lock(self,row,locked='p1'):
        s=self.setup_case(row);self.begin(s,row)
        s.rules_engine['drawLocks']=[{'playerId':locked,'turn':2}]
        self.resolve(s)
        for pid in self.affected(row):self.assertEqual(len(s.players[pid]['zones']['hand']),0 if pid==locked else row['expectedDraw'])

    def check_opponent_lock(self,row):self.check_draw_lock(row,'p2')

    def check_bob(self,row):
        s=self.setup_case(row);self.begin(s,row)
        self.field(s,'inner-deserts-134','bob')
        self.resolve(s)
        self.assertEqual(len(s.rules_engine['suspendedCards']),len(self.affected(row))*(2+row['expectedDraw']))
        for pid in self.affected(row):self.assertEqual(s.players[pid]['zones']['hand'],[])

    def check_hand_immunity(self,row):
        s=self.setup_case(row);self.begin(s,row)
        self.field(s,'inner-deserts-134','bob',power_bonus=6)
        old={pid:list(s.players[pid]['zones']['hand']) for pid in s.players}
        self.resolve(s)
        for pid in self.affected(row):self.assertEqual(s.players[pid]['zones']['hand'],old[pid])

    def kanon(self,s,owner):
        cid=next(c['id'] for c in main.CARD_DATA if c['name']=='Kanon, the Deathdealer')
        return self.field(s,cid,'kanon-'+owner,owner=owner)

    def check_kanon(self,row):
        s=self.setup_case(row);self.begin(s,row);self.kanon(s,'p2');self.resolve(s)
        choice=s.rules_engine['pendingChoice'];self.assertIsNotNone(choice)
        self.assertEqual((choice['kind'],choice['playerId'],choice['count']),('draw_replacement','p1',(row['expectedDraw']+1)//2))
        self.assertEqual(len(choice['_cardIds']),row['expectedDraw'])
        if row['allPlayers']:self.assertEqual(s.players['p2']['zones']['hand'],[],'Other player waits for the first replacement')
        self.choose(s,card_ids=choice['_cardIds'][:choice['count']])
        self.assertEqual(len(s.players['p1']['zones']['hand']),row['expectedDraw']//2)
        if row['allPlayers']:self.assertEqual(len(s.players['p2']['zones']['hand']),4)
        self.assertIsNone(s.rules_engine['pendingChoice'])

    def check_two_kanons(self,row):
        s=self.setup_case(row);self.begin(s,row);self.kanon(s,'p1');self.kanon(s,'p2');self.resolve(s)
        for pid in ('p1','p2'):
            choice=s.rules_engine['pendingChoice'];self.assertIsNotNone(choice)
            self.assertEqual((choice['kind'],choice['playerId'],choice['count']),('draw_replacement',pid,2))
            self.choose(s,card_ids=choice['_cardIds'][:2])
        self.assertIsNone(s.rules_engine['pendingChoice'])
        self.assertEqual([len(s.players[p]['zones']['hand']) for p in ('p1','p2')],[2,2])

    def check_invalid_choice(self,row):
        s=self.setup_case(row);self.begin(s,row);self.kanon(s,'p2');self.resolve(s)
        choice=s.rules_engine['pendingChoice'];before=self.snapshot(s)
        for pid,ids in [('p2',choice['_cardIds'][:choice['count']]),('p1',[]),('p1',['unknown']*choice['count'])]:
            error,_=s.resolve_rules_choice(pid,choice['id'],card_ids=ids)
            self.assertIsNotNone(error);self.assertEqual(self.snapshot(s),before)
        self.choose(s,card_ids=choice['_cardIds'][:choice['count']])
        after=self.snapshot(s)
        error,_=s.resolve_rules_choice('p1',choice['id'],card_ids=choice['_cardIds'][:choice['count']])
        self.assertIsNotNone(error);self.assertEqual(self.snapshot(s),after)

    def check_roundtrip(self,row):
        s=self.setup_case(row);self.begin(s,row);self.kanon(s,'p2');self.resolve(s)
        s.rules_engine=json.loads(json.dumps(s.rules_engine))
        choice=s.rules_engine['pendingChoice']
        self.choose(s,card_ids=choice['_cardIds'][:choice['count']])
        self.assertIsNone(s.rules_engine['pendingChoice'])
        self.assertEqual(len(s.players['p1']['zones']['hand']),row['expectedDraw']//2)
        if row['allPlayers']:self.assertEqual(len(s.players['p2']['zones']['hand']),4)

    def check_replacement_order(self,row):
        s=self.setup_case(row);self.begin(s,row);self.kanon(s,'p2')
        self.field(s,'inner-deserts-134','bob',power_bonus=3)
        selected=list(s.players['p1']['zones']['deck'][:(row['expectedDraw']+1)//2])
        s.rules_engine['limboDrawn']={'p1':[selected[0]]}
        self.resolve(s)
        choice=s.rules_engine['pendingChoice'];self.assertEqual(choice['kind'],'draw_replacement')
        before=copy.deepcopy(s.players)
        self.choose(s,card_ids=selected)
        order=s.rules_engine['pendingChoice'];self.assertEqual(order['kind'],'replacement_order')
        self.assertEqual(s.players,before)
        actions=sorted(order['actions'],key=lambda a:a['replacementKind']=='exile')
        self.choose(s,card_ids=[a['actionId'] for a in actions])
        self.assertIsNone(s.rules_engine['pendingChoice'])
        self.assertEqual(s.players['p1']['zones']['exile'],[selected[0]])
        if row['allPlayers']:
            # BOB intercepts the second player's draw too; it is resumed once.
            self.assertEqual(len([c for c in s.rules_engine['suspendedCards'] if c['ownerId']=='p2']),6)

    def check_kanon_followup(self,row):
        s=self.setup_case(row);self.begin(s,row);self.kanon(s,'p2')
        target=self.field(s,'m4','penalty-target')
        # With a no-op shuffle, these are the first inspected cards.
        for _ in range(2):s.put_zone_card('p1','deck','w2','p1','top')
        self.resolve(s)
        choice=s.rules_engine['pendingChoice'];self.assertIsNotNone(choice)
        self.assertEqual(choice['kind'],'draw_replacement')
        self.choose(s,card_ids=['w2','w2'])
        self.assertEqual(s.rules_engine['pendingChoice']['kind'],'power_loss_distribution')
        self.assertEqual(s.players['p2']['zones']['hand'],[])
        self.choose(s,option={'itemIds':[target['id'],target['id']]})
        self.assertEqual(s.rules_manifestation_characteristics(target)['power'],2)
        self.assertEqual(len(s.players['p2']['zones']['hand']),4)
        self.assertIsNone(s.rules_engine['pendingChoice'])

    def check_protected_opponent_hand(self,row):
        s=self.setup_case(row);self.begin(s,row)
        self.field(s,'l3ne0zha51w387z_en','purifying',owner='p2',zone='field')
        original=list(s.players['p2']['zones']['hand'])
        self.resolve(s)
        self.assertEqual(s.players['p2']['zones']['hand'][:2],original)
        self.assertEqual(len(s.players['p2']['zones']['hand']),6)

    def check_own_hand_protection(self,row):
        s=self.setup_case(row);self.begin(s,row)
        self.field(s,'l3ne0zha51w387z_en','purifying',zone='field')
        self.resolve(s)
        self.assertEqual(len(s.players['p1']['zones']['hand']),row['expectedDraw'])

    def check_batches(self,row):
        s=self.setup_case(row);action=self.begin(s,row)
        with patch('game.effects.cards.random.shuffle',side_effect=lambda cards:None):s.apply_rules_action_result(action)
        for pid in self.affected(row):
            events=[e for e in s.rules_engine['observedEvents'] if e['kind']=='cards_drawn' and e['playerId']==pid]
            self.assertEqual(len(events),row['expectedDraw'])
            self.assertEqual(len({e['drawBatchId'] for e in events}),1)
            self.assertTrue(events[0]['drawBatchId'])

    def check_order(self,row):
        s=self.setup_case(row);self.begin(s,row)
        with patch.object(s,'move_zone_card_by_effect',wraps=s.move_zone_card_by_effect) as moved:self.resolve(s)
        zones=[call.args[1] for call in moved.call_args_list]
        self.assertEqual(zones[:4],['hand']*4)
        self.assertEqual(zones[4:],['deck']*8)

    def check_private_results(self,row):
        s=self.check_normal(row)
        for viewer in ('p1','p2'):
            result=s.serialize_for(viewer,'player')['rulesEngine']['lastResolvedAction']['effectResult']
            encoded=json.dumps(result)
            for cid in s.players['p2' if viewer=='p1' else 'p1']['zones']['hand']:
                self.assertNotIn(cid,encoded)

    def check_timing(self,row):
        s=self.setup_case(row)
        s.phase_tracker['index']=ADVANCED_PHASES.index('confrontation_reaction')
        before=self.snapshot(s)
        error,_=s.declare_rules_action('p1',row['name'],kind='play_card',source={'cardId':row['cardId'],'zone':'hand'},ability_id=row['abilityId'])
        self.assertIsNotNone(error);self.assertEqual(self.snapshot(s),before)

    def check_immediate(self,row):
        s=self.setup_case(row);self.begin(s,row)
        with patch('game.effects.cards.random.shuffle',side_effect=lambda cards:None):results=s.resolve_rules_immediate_actions(max_actions=1)
        self.assertEqual(len(results),1);self.assertEqual(s.rules_engine['actionStack'],[])
        self.assertEqual([len(s.players[p]['zones']['hand']) for p in ('p1','p2')],[4,4])


def scenarios(row):
    cases=['normal','empty','short_pool','other_actor','duplicates','draw_lock','bob','hand_immunity','kanon','own_hand_protection','batches','private_results','invalid_choice','roundtrip','replacement_order']
    if row['allPlayers']:cases+=['opponent_lock','two_kanons','kanon_followup','protected_opponent_hand','order','immediate']
    else:cases+=['timing']
    return cases


def method_name(row,case):return 'test_'+row['key']+'__'+case


for row in CONTRACTS:
    for case in scenarios(row):
        def run(self,row=row,case=case):getattr(self,'check_'+case)(row)
        setattr(ShuffleDraw,method_name(row,case),run)


if __name__=='__main__':unittest.main()
