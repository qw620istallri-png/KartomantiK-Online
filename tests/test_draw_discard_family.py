"""Independent quantities and event contracts for fixed draw/discard clauses."""
import copy
import hashlib
import json
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import main
import test_discard_draw_clauses as fixtures
from session import ADVANCED_PHASES

ROOT=Path(__file__).resolve().parents[1]
CONTRACTS=json.loads((ROOT/'audit/draw-discard-family.json').read_text(encoding='utf-8'))['contracts']
for row in CONTRACTS:
    card=next(c for c in main.CARD_DATA if c['id']==row['cardId'])
    assert card['name']==row['name'] and card['effect']==row['printedText']
    assert hashlib.sha256(card['effect'].encode()).hexdigest()==row['printedTextSha256']
    assert [p.strip() for p in card['effect'].splitlines() if p.strip()][row['paragraphIndex']]==row['printedParagraph']
    assert row['abilityId'] in {a['id'] for a in main.CARD_ABILITIES[row['cardId']]}


class DrawDiscardFamily(unittest.TestCase):
    world=fixtures.DiscardDrawClauses.world
    field=staticmethod(fixtures.DiscardDrawClauses.field)
    put=staticmethod(fixtures.DiscardDrawClauses.put)
    snapshot=fixtures.DiscardDrawClauses.snapshot

    @staticmethod
    def other(pid): return 'p2' if pid=='p1' else 'p1'

    def setup_case(self,row,actor='p1',target=None,deck=('m2','m3','m4','w2'),hand=('w2','pw3')):
        s=self.world();host=None
        for pid in s.players:
            self.put(s,pid,'deck',deck);self.put(s,pid,'hand',hand)
        s.add_rules_excess_essence(actor,[{'temperament':c,'amount':5} for c in
            ('hollow','vitreous','melancholic')])
        if row['sourceZone'] in {'hand','graveyard'}:
            owner=actor if row['mode']=='play' else 'p1'
            s.put_zone_card(owner,row['sourceZone'],row['cardId'],owner)
        else: host=self.field(s,row['cardId'],'draw-source',owner='p1',controller=actor,zone=row['sourceZone'])
        recipient=target or (self.other(actor) if row['kind']=='discard' or row['key'].startswith('zum_') else actor)
        s.rules_engine['priorityPlayerId']=actor
        s.rules_engine['observedEvents']=[]
        return s,host,recipient

    def event_player(self,row,actor,recipient):
        if row['key'] in {'wheel','makaboon'}: return recipient
        return self.other(actor) if row['eventRelation']=='opponent' else actor

    def targets(self,row,recipient):
        return [{'kind':'player','playerId':recipient}] if row['kind']=='discard' or row['key'].startswith('zum_') else []

    def queue(self,s,row,host,recipient,actor='p1',**overrides):
        color='vitreous' if row['key']=='pidue_draw' else 'melancholic'
        cid='draw-stimulus-'+color
        s.card_rules[cid]={'type':'ephemeral_will','temperaments':[color]}
        kwargs=dict(zone=row['sourceZone'],container_id='p1' if row['sourceZone']=='graveyard' else None,
            item_id=(host or {}).get('id'),controller_id=actor,face_up=(host or {}).get('faceUp',True),
            event_controller_id=self.event_player(row,actor,recipient),played=True,first_will_of_turn=True,
            event_targets=self.targets(row,recipient),event_card_id=cid,
            related_action={'id':'explicit-will-event','kind':'play_card','controllerId':self.event_player(row,actor,recipient),
                'source':{'cardId':cid,'zone':'hand','ownerId':self.event_player(row,actor,recipient)}},defer=True)
        event=overrides.pop('event',row['event']);kwargs.update(overrides)
        return [a for a in s.queue_rules_triggers(row['cardId'],'p1',event,**kwargs)
                if a['ability']['id']==row['abilityId']]

    def begin(self,s,row,host,recipient,actor='p1'):
        if row['mode']=='event':
            actions=self.queue(s,row,host,recipient,actor)
            self.assertEqual(len(actions),1,row['key'])
            s.queue_rules_simultaneous_actions(actions);action=actions[0]
        else:
            source={'cardId':row['cardId'],'zone':'hand'} if row['mode']=='play' else {
                'cardId':row['cardId'],'zone':'battlefield','itemId':host['id']}
            error,action=s.declare_rules_action(actor,row['name'],kind='play_card' if row['mode']=='play' else 'activated_effect',
                source=source,ability_id=row['abilityId'],targets=self.targets(row,recipient))
            self.assertIsNone(error)
            spent=Counter()
            for part in action['cost']['essenceSpent']:spent[part['temperament']]+=part['amount']
            self.assertEqual(dict(spent),row['essenceCost'])
        self.assertIsNone(s.rules_engine['pendingChoice'])
        return action

    def choose(self,s,selected):
        choice=s.rules_engine['pendingChoice']
        self.assertIsNotNone(choice)
        error,result=s.resolve_rules_choice(choice['playerId'],choice['id'],card_ids=selected)
        self.assertIsNone(error)
        return result

    def normal(self,row,actor='p1',target=None,deck=('m2','m3','m4','w2'),hand=('w2','pw3')):
        s,host,recipient=self.setup_case(row,actor,target,deck,hand)
        self.begin(s,row,host,recipient,actor)
        before=copy.deepcopy(s.players)
        s.resolve_rules_top_action()
        wanted=min(row['expectedAmount'],len(hand) if row['kind']=='discard' else len(deck))
        if row['kind']=='discard' and wanted:
            choice=s.rules_engine['pendingChoice']
            self.assertEqual((choice['kind'],choice['playerId'],choice['count']),('discard_from_hand',recipient,wanted))
            self.assertEqual(s.players[recipient]['zones']['hand'],before[recipient]['zones']['hand'])
            self.choose(s,list(hand[:wanted]))
        self.assertIsNone(s.rules_engine['pendingChoice'])
        zones=s.players[recipient]['zones'];old=before[recipient]['zones']
        if row['kind']=='draw':
            self.assertEqual(zones['hand'],old['hand']+list(deck[:wanted]))
            self.assertEqual(zones['deck'],list(deck[wanted:]))
        elif row['kind']=='mill':
            self.assertEqual(zones['hand'],old['hand'])
            self.assertEqual(zones['deck'],list(deck[wanted:]))
            self.assertEqual(Counter(zones['graveyard'])-Counter(old['graveyard']),Counter(deck[:wanted]))
        else:
            self.assertEqual(Counter(old['hand'])-Counter(zones['hand']),Counter(hand[:wanted]))
            self.assertEqual(Counter(zones['graveyard'])-Counter(old['graveyard']),Counter(hand[:wanted]))
        other=self.other(recipient)
        self.assertEqual(s.players[other]['zones']['deck'],before[other]['zones']['deck'])
        self.assertEqual(s.players[other]['zones']['hand'],before[other]['zones']['hand'])
        if row['mode']=='play': self.assertIn(row['cardId'],s.players[actor]['zones']['graveyard'])
        return s,host,recipient

    def check_normal(self,row): self.normal(row)
    def check_empty(self,row): self.normal(row,deck=(),hand=() if row['kind']=='discard' else ('w2','pw3'))
    def check_one_available(self,row): self.normal(row,deck=('m2',),hand=('w2',))
    def check_duplicates(self,row): self.normal(row,deck=('m2','m2','m2','m3'),hand=('w2','w2'))
    def check_other_controller(self,row): self.normal(row,actor='p2')
    def check_target_self(self,row): self.normal(row,target='p1')

    def check_source_departure(self,row):
        s,host,recipient=self.setup_case(row)
        self.begin(s,row,host,recipient)
        s._rules_remove_field_item(host,'p1','graveyard')
        before=list(s.players[recipient]['zones']['hand'])
        s.resolve_rules_top_action()
        if row['kind']=='discard': self.choose(s,['w2']);self.assertEqual(len(s.players[recipient]['zones']['hand']),len(before)-1)
        elif row['kind']=='draw':self.assertEqual(s.players[recipient]['zones']['hand'],before+['m2']*row['expectedAmount'])
        else:self.assertEqual(s.players[recipient]['zones']['deck'],['m3','m4','w2'])

    def check_trigger_guards(self,row):
        cases=['wrong_event']
        if row['sourceZone']!='graveyard': cases+=['hidden','disabled','stalemate']
        if row['eventRelation'] in {'self','opponent'}:cases+=['wrong_player']
        if row['key'] in {'mazzolong','callus'}: cases+=['wrong_zone']
        if row['key']=='mazzolong':cases+=['put_not_played']
        if row['key']=='threshold':cases+=['not_first_will']
        if row['key'].startswith('pidue_'):cases+=['wrong_color','not_from_hand','outside_confrontation']
        for case in cases:
            with self.subTest(condition=case):
                s,host,recipient=self.setup_case(row);kwargs={}
                if case=='wrong_event':kwargs['event']='not-the-event'
                if case=='hidden':host['faceUp']=False
                if case=='disabled':host['effectsDisabled']=True
                if case=='stalemate':host['fieldZone']='stalemate'
                if case=='wrong_player':kwargs['event_controller_id']='p1' if row['eventRelation']=='opponent' else 'p2'
                if case=='wrong_zone':host['fieldZone']='confrontation';kwargs['zone']='confrontation'
                if case=='put_not_played':kwargs['played']=False
                if case=='not_first_will':kwargs['first_will_of_turn']=False
                if case=='wrong_color':kwargs['event_card_id']='w2'
                if case=='not_from_hand':kwargs['related_action']={'kind':'play_card','source':{'cardId':'w2','zone':'graveyard'}}
                if case=='outside_confrontation':s.phase_tracker['index']=ADVANCED_PHASES.index('end_triggers')
                self.assertEqual(self.queue(s,row,host,recipient,**kwargs),[])

    def check_draw_lock(self,row):
        s,host,recipient=self.setup_case(row)
        self.begin(s,row,host,recipient)
        before=copy.deepcopy(s.players[recipient]['zones'])
        s.rules_engine['drawLocks']=[{'playerId':recipient,'turn':2}]
        s.resolve_rules_top_action()
        self.assertEqual(s.players[recipient]['zones']['hand'],before['hand'])
        self.assertEqual(s.players[recipient]['zones']['deck'],before['deck'])
        self.assertIsNone(s.rules_engine['pendingChoice'])

    def check_kanon(self,row):
        s,host,recipient=self.setup_case(row,deck=('m2','m3','m4','m2'))
        kanon=next(c['id'] for c in main.CARD_DATA if c['name']=='Kanon, the Deathdealer')
        self.field(s,kanon,'kanon',owner=self.other(recipient))
        self.begin(s,row,host,recipient)
        before=list(s.players[recipient]['zones']['hand'])
        s.resolve_rules_top_action()
        choice=s.rules_engine['pendingChoice'];n=row['expectedAmount'];discard=(n+1)//2
        self.assertEqual((choice['kind'],choice['playerId'],choice['count']),('draw_replacement',recipient,discard))
        offered=['m2','m3','m4'][:n]
        self.assertEqual(choice['_cardIds'],offered)
        self.choose(s,offered[:discard])
        self.assertEqual(s.players[recipient]['zones']['hand'],before+offered[discard:])
        self.assertEqual(s.players[recipient]['zones']['deck'],['m2','m3','m4','m2'][n:])

    def check_bob(self,row):
        s,host,recipient=self.setup_case(row)
        self.begin(s,row,host,recipient)
        bob=self.field(s,'inner-deserts-134','bob',power_bonus=3 if row['kind']=='discard' else 0)
        self.assertEqual(s.rules_manifestation_characteristics(bob)['power'],5 if row['kind']=='discard' else 2)
        before=copy.deepcopy(s.players[recipient]['zones'])
        s.resolve_rules_top_action()
        if row['kind']=='discard':self.choose(s,['w2'])
        expected=['w2'] if row['kind']=='discard' else ['m2','m3','m4'][:row['expectedAmount']]
        self.assertCountEqual([c['cardId'] for c in s.rules_engine['suspendedCards']],expected)
        expected_grave=Counter(before['graveyard'])
        if row['mode']=='play':expected_grave[row['cardId']]+=1
        self.assertEqual(Counter(s.players[recipient]['zones']['graveyard']),expected_grave)
        if row['kind']=='draw':self.assertEqual(s.players[recipient]['zones']['hand'],before['hand'])

    def check_hand_immunity(self,row):
        s,host,recipient=self.setup_case(row)
        self.begin(s,row,host,recipient)
        self.field(s,'inner-deserts-134','bob',power_bonus=6)  # 8: hands immune, not exiled.
        before=list(s.players[recipient]['zones']['hand'])
        s.resolve_rules_top_action()
        self.assertIsNone(s.rules_engine['pendingChoice'])
        self.assertEqual(s.players[recipient]['zones']['hand'],before)

    def check_bad_choices(self,row):
        for bad in ([],['absent'],['w2','pw3'],[{}]):
            with self.subTest(selected=bad):
                s,host,recipient=self.setup_case(row)
                self.begin(s,row,host,recipient);s.resolve_rules_top_action()
                choice=s.rules_engine['pendingChoice'];before=self.snapshot(s)
                error,_=s.resolve_rules_choice(recipient,choice['id'],card_ids=bad)
                self.assertIsNotNone(error);self.assertEqual(self.snapshot(s),before)

    def check_choice_actor_replay(self,row):
        s,host,recipient=self.setup_case(row)
        self.begin(s,row,host,recipient);s.resolve_rules_top_action()
        choice=s.rules_engine['pendingChoice'];before=self.snapshot(s)
        self.assertIsNotNone(s.resolve_rules_choice(self.other(recipient),choice['id'],card_ids=['w2'])[0])
        self.assertEqual(self.snapshot(s),before)
        self.choose(s,['w2']);after=self.snapshot(s)
        self.assertIsNotNone(s.resolve_rules_choice(recipient,choice['id'],card_ids=['w2'])[0])
        self.assertEqual(self.snapshot(s),after)

    def check_competing_replacements(self,row):
        for preferred in ('suspend','exile'):
            with self.subTest(first_replacement=preferred):
                s,host,recipient=self.setup_case(row)
                self.begin(s,row,host,recipient)
                self.field(s,'inner-deserts-134','bob',owner=recipient,power_bonus=3)
                s.rules_engine['limboDrawn']={recipient:['w2']}
                s.resolve_rules_top_action()
                original=s.rules_engine['pendingChoice']
                before=copy.deepcopy(s.players)
                self.choose(s,['w2'])
                choice=s.rules_engine['pendingChoice']
                self.assertIsNotNone(choice)
                self.assertEqual((choice['kind'],choice['playerId']),('replacement_order',recipient))
                self.assertEqual(s.players,before,'No extraction before the replacement order')
                self.assertEqual(choice['_originalChoice']['id'],original['id'])
                order=sorted(choice['actions'],key=lambda a:a['replacementKind']==preferred)
                self.choose(s,[a['actionId'] for a in order])
                self.assertIsNone(s.rules_engine['pendingChoice'])
                self.assertEqual(s.players[recipient]['zones']['hand'],['pw3'])
                self.assertEqual(s.players[recipient]['zones']['graveyard'],[])
                self.assertEqual(s.players[recipient]['zones']['exile'],['w2'] if preferred=='exile' else [])
                self.assertEqual([e['cardId'] for e in s.rules_engine['suspendedCards']],['w2'] if preferred=='suspend' else [])

    def check_real_event_builder(self,row):
        s,host,recipient=self.setup_case(row)
        if row['key'] in {'mazzolong','wheel'}:
            entered=self.field(s,'m2','real-support',owner='p1' if row['key']=='mazzolong' else recipient,support=True)
            actions=s.queue_rules_support_entry_triggers(entered,played=True,from_zone='hand',defer=True)
        elif row['key']=='makaboon':
            error,_,_=s.move_zone_card_by_effect(recipient,'deck',recipient,'graveyard','m2')
            self.assertIsNone(error)
            actions=s.queue_rules_observed_event_triggers(defer=True)
        else:
            ponder='ryg8e3lgopl6z52_en'
            s.put_zone_card('p1','hand',ponder,'p1')
            error,paid=s.declare_rules_action('p1','Ponder',kind='play_card',source={'zone':'hand','cardId':ponder},ability_id='draw-three-cards')
            self.assertIsNone(error)
            main.log_rules_declared_action(s,paid)
            choice=s.rules_engine['pendingChoice']
            self.assertEqual(choice['kind'],'simultaneous_stack_order')
            actions=[a for a in choice['_group'] if a['ability']['id']==row['abilityId']]
            self.assertEqual(len(actions),1)
            self.choose(s,[paid['id'],actions[0]['id']])
        selected=[a for a in actions if a['ability']['id']==row['abilityId']]
        self.assertEqual(len(selected),1)
        if row['key'] not in {'callus','threshold'}:s.queue_rules_simultaneous_actions(selected)
        before=list(s.players[recipient]['zones']['hand'])
        self.assertEqual(s.rules_engine['actionStack'][-1]['ability']['id'],row['abilityId'])
        s.resolve_rules_top_action()
        if row['kind']=='discard':
            self.choose(s,['w2'])
            self.assertEqual(s.players[recipient]['zones']['hand'],['pw3'])
        else:self.assertEqual(s.players[recipient]['zones']['hand'],before+['m2'])


def scenarios(row):
    cases=['normal','empty','one_available','duplicates','other_controller','bob']
    if row['kind']=='draw':cases+=['draw_lock','kanon']
    if row['kind']=='discard':cases+=['hand_immunity','bad_choices','choice_actor_replay','competing_replacements']
    if row['kind']=='discard' or row['key'].startswith('zum_'):cases+=['target_self']
    if row['mode']=='event':cases+=['trigger_guards']
    if row['sourceZone'] not in {'graveyard','hand'}:cases+=['source_departure']
    if row['key'] in {'mazzolong','wheel','makaboon','callus','threshold'}:cases+=['real_event_builder']
    return cases


def method_name(row,scenario):return 'test_'+row['key']+'__'+scenario


for row in CONTRACTS:
    for scenario in scenarios(row):
        def run(self,row=row,scenario=scenario):getattr(self,'check_'+scenario)(row)
        setattr(DrawDiscardFamily,method_name(row,scenario),run)


if __name__=='__main__':unittest.main()
