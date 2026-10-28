"""User-confirmed discard condition, including destinations replaced by BOB/exile."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch
import main
import test_discard_draw_clauses as base

ROOT=Path(__file__).resolve().parents[1]
CONTRACTS=json.loads((ROOT/'audit/conditional-discard-draw.json').read_text(encoding='utf-8'))['contracts']
for row in CONTRACTS:
    card=next(c for c in main.CARD_DATA if c['id']==row['cardId'])
    assert row['printedTextSha256']==hashlib.sha256(card['effect'].encode()).hexdigest()
    assert row['printedParagraph']==[p for p in card['effect'].splitlines() if p.strip()][row['paragraphIndex']]

PROFILES=('limbo','exile','suspend','order_exile','order_suspend')
CASES=('normal','short_deck','empty_deck','duplicates','locked','kanon')


class ConditionalDiscardReplacement(unittest.TestCase):
    def setup_case(self,row,profile='limbo',case='normal',resolve=True):
        f=base.DiscardDrawClauses()
        deck=['m2','m3','m4'] if case not in ('short_deck','empty_deck') else ['m2'] if case=='short_deck' else []
        hand=['w2','w2'] if case=='duplicates' else [] if case=='no_discard' else ['w2']
        s,host=f.setup_discard(row['name'],hand=hand,deck=deck,resolve=False)
        if profile in ('suspend','order_exile','order_suspend'):
            f.field(s,'inner-deserts-134','bob',power_bonus=3)
        if profile in ('exile','order_exile','order_suspend'):s.rules_engine['limboDrawn']={'p1':['w2']}
        if case=='locked':s.rules_engine['drawLocks']=[{'playerId':'p1','turn':2}]
        if case=='kanon':f.kanon(s)
        if resolve:s.resolve_rules_top_action()
        return f,s,host,deck,hand

    def finish_discard(self,f,s,profile):
        choice=s.rules_engine['pendingChoice'];self.assertEqual(choice['kind'],'discard_from_hand')
        before=copy.deepcopy(s.players)
        result=f.choose(s,card_ids=['w2'])
        if profile.startswith('order_'):
            order=s.rules_engine['pendingChoice'];self.assertEqual(order['kind'],'replacement_order')
            self.assertEqual(s.players,before,'No discard or draw before replacement order is chosen')
            desired=profile.removeprefix('order_')
            ordered=sorted(order['actions'],key=lambda e:e['replacementKind']==desired)
            result=f.choose(s,card_ids=[e['actionId'] for e in ordered])
        return result

    def exercise(self,row,profile,case):
        f,s,host,deck,hand=self.setup_case(row,profile,case)
        opponent=copy.deepcopy(s.players['p2'])
        choice=s.rules_engine['pendingChoice'];self.assertEqual(choice['drawAfter'],row['expectedDraw'])
        self.assertEqual(s.players['p1']['zones']['deck'],deck)
        self.assertEqual(s.players['p1']['zones']['hand'],hand)
        self.finish_discard(f,s,profile)
        has_bob=profile in ('suspend','order_exile','order_suspend')
        destination='exile' if profile in ('exile','order_exile') else 'suspend' if has_bob else 'limbo'
        self.assertEqual(s.players['p1']['zones']['hand'].count('w2'),len(hand)-1)
        self.assertEqual(s.players['p1']['zones']['exile'].count('w2'),int(destination=='exile'))
        self.assertEqual(s.players['p1']['zones']['graveyard'].count('w2'),int(destination=='limbo'))
        self.assertEqual(sum(c['cardId']=='w2' for c in s.rules_engine['suspendedCards']),int(destination=='suspend'))
        requested=min(row['expectedDraw'],len(deck)) if case!='locked' else 0
        if case=='kanon':
            kanon=s.rules_engine['pendingChoice'];self.assertEqual(kanon['kind'],'draw_replacement')
            self.assertEqual(kanon['_cardIds'],deck[:requested])
            self.assertEqual(kanon['count'],(requested+1)//2)
            f.choose(s,card_ids=deck[:kanon['count']])
            expected=[] if has_bob else deck[kanon['count']:requested]
        else:expected=[] if has_bob else deck[:requested]
        self.assertEqual(s.players['p1']['zones']['deck'],deck[requested:])
        self.assertEqual(s.players['p1']['zones']['hand'],hand[1:]+expected)
        if has_bob:
            # BOB replaces these draws too; an empty Hand must not hide a skipped draw.
            for cid in deck[:requested]:
                self.assertEqual(sum(c['cardId']==cid for c in s.rules_engine['suspendedCards']),1)
        self.assertIsNone(s.rules_engine['pendingChoice'])
        self.assertEqual(s.players['p2'],opponent)
        self.assertNotIn(row['cardId'],s.players['p1']['zones']['hand'])
        if host:self.assertEqual(host['counters']['Formula'],5,'This trigger does not spend Formula counters')

    def check_invalid(self,row):
        f,s,_,_,_=self.setup_case(row,'order_exile')
        first=s.rules_engine['pendingChoice'];before=f.snapshot(s)
        for actor,ids in [('p2',['w2']),('p1',[]),('p1',['m4']),('p1',['w2','w2'])]:
            self.assertIsNotNone(s.resolve_rules_choice(actor,first['id'],card_ids=ids)[0])
            self.assertEqual(f.snapshot(s),before)
        f.choose(s,card_ids=['w2']);order=s.rules_engine['pendingChoice'];before=f.snapshot(s)
        self.assertIsNotNone(s.resolve_rules_choice('p1',order['id'],card_ids=[])[0]);self.assertEqual(f.snapshot(s),before)
        actions=sorted(order['actions'],key=lambda e:e['replacementKind']=='exile')
        f.choose(s,card_ids=[e['actionId'] for e in actions]);after=f.snapshot(s)
        for old in (first,order):
            self.assertIsNotNone(s.resolve_rules_choice('p1',old['id'],card_ids=['w2'])[0])
            self.assertEqual(f.snapshot(s),after)

    def check_roundtrip(self,row):
        f,s,_,_,_=self.setup_case(row,'order_suspend')
        s.rules_engine=json.loads(json.dumps(s.rules_engine))
        self.finish_discard(f,s,'order_suspend')
        self.assertEqual(s.players['p1']['zones']['deck'],['m2','m3','m4'][row['expectedDraw']:])
        self.assertIsNone(s.rules_engine['pendingChoice'])

    def check_source_departure(self,row):
        f,s,host,_,_=self.setup_case(row,'exile')
        if host:s._rules_remove_field_item(host,'p1','graveyard')
        else:self.assertIn(row['cardId'],s.players['p1']['zones']['graveyard'])
        self.finish_discard(f,s,'exile')
        self.assertEqual(s.players['p1']['zones']['hand'],['m2','m3'][:row['expectedDraw']])

    def check_no_discard(self,row):
        _,s,_,deck,_=self.setup_case(row,'exile','no_discard')
        self.assertIsNone(s.rules_engine['pendingChoice'])
        self.assertEqual(s.players['p1']['zones']['hand'],[])
        self.assertEqual(s.players['p1']['zones']['deck'],deck)

    def check_immunity(self,row):
        f,s,_,deck,hand=self.setup_case(row,resolve=False)
        f.field(s,'inner-deserts-134','bob',power_bonus=6)
        s.resolve_rules_top_action()
        self.assertIsNone(s.rules_engine['pendingChoice'])
        self.assertEqual(s.players['p1']['zones']['hand'],hand)
        self.assertEqual(s.players['p1']['zones']['deck'],deck)


def scenarios(row):return [(profile,case) for profile in PROFILES for case in CASES]+[(None,c) for c in ('invalid','roundtrip','source_departure','no_discard','immunity')]
def method_name(row,profile,case):return 'test_'+row['key']+'__'+(profile+'__' if profile else '')+case


for row in CONTRACTS:
    for profile,case in scenarios(row):
        def run(self,row=row,profile=profile,case=case):
            if profile:self.exercise(row,profile,case)
            else:getattr(self,'check_'+case)(row)
        setattr(ConditionalDiscardReplacement,method_name(row,profile,case),run)


if __name__=='__main__':unittest.main()
