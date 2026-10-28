"""Exact, handwritten scaling oracles for six printed point clauses.

Fixture populations are independent of the encoded counting helpers. Normal
triggers use explicit stimuli; separate producer cases exercise real builders.
"""
import copy
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from card_effect_families import load_scaled_score_contracts
import test_discard_draw_clauses as fixtures
from session import ADVANCED_PHASES

CONTRACTS=load_scaled_score_contracts()


class ScaledScoreFamily(unittest.TestCase):
    world=fixtures.DiscardDrawClauses.world
    field=staticmethod(fixtures.DiscardDrawClauses.field)
    put=staticmethod(fixtures.DiscardDrawClauses.put)

    @staticmethod
    def other(pid): return 'p2' if pid=='p1' else 'p1'

    @staticmethod
    def scores(s): return {pid:p['score'] for pid,p in s.players.items()}

    def setup_case(self,row,units=2,actor='p1',target=None):
        s=self.world()
        other=self.other(actor)
        target=target or other
        host=None
        if row['mode']=='play':
            s.put_zone_card(actor,'hand',row['cardId'],actor)
            s.add_rules_excess_essence(actor,[{'temperament':'phlegmatic','amount':2}])
        else:
            host=self.field(s,row['cardId'],'scaled-source',owner='p1',controller=actor,zone=row['sourceZone'])
        counted=[]
        scope=row['scope']
        if scope in {'interzone','cz_non_token','exhausted'}:
            controller=target if scope=='cz_non_token' else actor
            zone='interzone' if scope=='interzone' else 'confrontation'
            for index in range(units):
                item=self.field(s,'m2','counted-'+str(index),owner=controller,zone=zone)
                if scope=='exhausted': item['rotation']=90
                counted.append(item)
            # These distractors must never affect this population's count.
            self.field(s,'m3','other-player',owner=self.other(controller),zone=zone)
            if scope!='exhausted':
                self.field(s,'m3','other-zone',owner=controller,zone='confrontation' if zone=='interzone' else 'interzone')
                self.field(s,'pw3','ordinary-will',owner=controller,zone=zone)
                hidden=self.field(s,'m3','hidden',owner=controller,zone=zone)
                hidden['faceUp']=False
                self.field(s,'m3','stalemate',owner=controller,zone='stalemate')
        elif scope=='vessel_owned':
            for _ in range(units): s.put_zone_card(other,'receptacle','m2',actor)
            s.put_zone_card(actor,'receptacle','m3',other)
            s.put_zone_card(other,'receptacle','pw3',actor)
            s.put_zone_card(actor,'hand','m4',actor)
        else:
            # Printed source 5; the opponent's CURRENT First has power 5-units.
            s.card_rules['scaled-foe']={'type':'manifestation','power':5-units,
                'temperaments':['phlegmatic'],'powerCost':'{G}'}
            s.manifestation_ids.add('scaled-foe')
            foe=self.field(s,'scaled-foe','first-opponent',owner=other)
            counted=[foe]
            self.field(s,'m4','opponent-support',owner=other,support=True,power_bonus=50)
            s.rules_engine['firstManifestationItemIds']={actor:host['id'],other:foe['id']}
        s.rules_engine['priorityPlayerId']=actor
        s.rules_engine['observedEvents']=[]
        return s,host,counted,target

    def expected_scores(self,row,units,actor='p1',start=50):
        expected={'p1':start,'p2':start}
        expected[actor if row['recipient']=='controller' else self.other(actor)]+=row['expectedMultiplier']*units
        return expected

    def queue(self,s,row,host,target,*,event=None):
        actor=s.rules_item_controller_id(host)
        targets=[{'kind':'player','playerId':target}] if row['scope']=='first_difference' else []
        return [a for a in s.queue_rules_triggers(row['cardId'],host['ownerId'],event or row['event'],
            item_id=host['id'],zone=row['sourceZone'],controller_id=actor,event_controller_id=actor,
            event_targets=targets,defer=True) if a['ability']['id']==row['abilityId']]

    def begin(self,s,row,host,target):
        before=self.scores(s)
        if row['mode']=='play':
            actor=next(pid for pid,p in s.players.items() if row['cardId'] in p['zones']['hand'])
            error,action=s.declare_rules_action(actor,row['name'],kind='play_card',
                source={'cardId':row['cardId'],'zone':'hand'},ability_id=row['abilityId'],
                targets=[{'kind':'player','playerId':target}])
            self.assertIsNone(error)
            spent=Counter()
            for payment in action['cost']['essenceSpent']: spent[payment['temperament']]+=payment['amount']
            self.assertEqual(dict(spent),row['essenceCost'])
        else:
            actions=self.queue(s,row,host,target)
            self.assertEqual(len(actions),1)
            s.queue_rules_simultaneous_actions(actions)
            action=actions[0]
        self.assertEqual(self.scores(s),before,'Points wait for resolution')
        self.assertIsNone(s.rules_engine['pendingChoice'])
        self.assertEqual(s.rules_engine['actionStack'][-1]['id'],action['id'])
        return action

    def resolve(self,s,row,units,actor='p1',start=50):
        s.resolve_rules_top_action()
        self.assertEqual(self.scores(s),self.expected_scores(row,units,actor,start))
        if row['mode']=='play': self.assertIn(row['cardId'],s.players[actor]['zones']['graveyard'])

    def normal(self,row,units=2,actor='p1',start=50,target=None):
        s,host,counted,target=self.setup_case(row,units,actor,target)
        for p in s.players.values(): p['score']=start
        self.begin(s,row,host,target)
        self.resolve(s,row,units,actor,start)
        return s,host,counted

    def check_zero(self,row): self.normal(row,0)
    def check_one(self,row): self.normal(row,1)
    def check_two(self,row): self.normal(row,2)
    def check_three(self,row): self.normal(row,3)
    def check_negative_scores(self,row): self.normal(row,start=-100)
    def check_other_controller(self,row): self.normal(row,actor='p2')

    def check_prevention(self,row):
        s,host,_,target=self.setup_case(row)
        self.begin(s,row,host,target)
        s.rules_engine['ongoingEffects'].append({'kind':'prevent_point_changes'})
        s.resolve_rules_top_action()
        self.assertEqual(self.scores(s),{'p1':50,'p2':50})

    def check_balance(self,row):
        for redirect in (False,True):
            with self.subTest(redirect=redirect):
                s,host,_,target=self.setup_case(row)
                self.field(s,'inner-deserts-137','balance',zone='field')
                for pid in s.players: s.players[pid]['score']+=50-s.rules_vessel_total(pid)
                recipient='p1' if row['recipient']=='controller' else 'p2'
                if redirect: s.players[recipient]['score']+=30 if row['expectedMultiplier']>0 else -30
                expected=self.scores(s)
                expected[self.other(recipient) if redirect else recipient]+=2*row['expectedMultiplier']
                self.begin(s,row,host,target)
                s.resolve_rules_top_action()
                self.assertEqual(self.scores(s),expected)

    def change_population(self,s,row,counted,*,add):
        scope=row['scope']
        if scope=='first_difference': counted[0]['counters']['power']=-1 if add else 1
        elif scope=='vessel_owned':
            if add: s.put_zone_card('p2','receptacle','m2','p1')
            else: s.take_zone_card('p2','receptacle','m2')
        elif add:
            item=self.field(s,'m2','late-add',owner='p2' if scope=='cz_non_token' else 'p1',
                zone='interzone' if scope=='interzone' else 'confrontation')
            if scope=='exhausted': item['rotation']=90
        elif scope=='exhausted': counted[0]['rotation']=0
        else: s._rules_remove_field_item(counted[0],counted[0]['ownerId'],'hand')

    def check_late_increase(self,row):
        s,host,counted,target=self.setup_case(row)
        self.begin(s,row,host,target)
        self.change_population(s,row,counted,add=True)
        self.resolve(s,row,3)

    def check_late_decrease(self,row):
        s,host,counted,target=self.setup_case(row)
        self.begin(s,row,host,target)
        self.change_population(s,row,counted,add=False)
        self.resolve(s,row,1)

    def check_source_departure(self,row):
        s,host,_,target=self.setup_case(row)
        self.begin(s,row,host,target)
        s._rules_remove_field_item(host,'p1','hand')
        self.resolve(s,row,2)

    def check_trigger_guards(self,row):
        for condition in ('hidden','disabled','stalemate','wrong_event'):
            with self.subTest(condition=condition):
                s,host,_,target=self.setup_case(row)
                if condition=='hidden': host['faceUp']=False
                if condition=='disabled': host['effectsDisabled']=True
                if condition=='stalemate': host['fieldZone']='stalemate'
                self.assertEqual(self.queue(s,row,host,target,event='not-the-event' if condition=='wrong_event' else None),[])

    def check_source_control_after_queue(self,row):
        s,host,_,target=self.setup_case(row)
        self.begin(s,row,host,target)
        host['controllerId']='p2'
        self.resolve(s,row,2)  # The queued effect keeps its original controller.

    def check_counted_protected(self,row):
        s,host,counted,target=self.setup_case(row)
        self.begin(s,row,host,target)
        s.rules_engine['ongoingEffects'].append({'kind':'protection','fromOpponents':True,
            'duration':'until_end_of_turn','startedTurn':2,
            'target':{'kind':'card','itemId':counted[0]['id']}})
        self.resolve(s,row,2)  # A counted card is not a target of these effects.

    def check_source_joins_counted_zone(self,row):
        s,host,_,target=self.setup_case(row)
        self.begin(s,row,host,target)
        if row['scope']=='interzone': host['fieldZone']='interzone'
        else: s._rules_remove_field_item_by_effect(host,'p2','receptacle')
        self.resolve(s,row,3)

    def check_builder(self,row):
        s,host,_,_=self.setup_case(row)
        if row['key']=='donmo':
            s.phase_tracker['index']=ADVANCED_PHASES.index('end_triggers')
            actions=s.build_rules_end_turn_field_triggers()
        else:
            s.rules_engine['confrontationResult']={'turn':2,'winnerId':'p1','loserId':'p2',
                'stalemate':False,'participantItemIds':[host['id']]}
            actions=s.queue_rules_confrontation_win_triggers(defer=True)
        selected=[a for a in actions if a['ability']['id']==row['abilityId']]
        self.assertEqual(len(selected),1)
        s.queue_rules_simultaneous_actions(selected)
        self.resolve(s,row,2)

    def check_tokens_and_copies(self,row):
        s,host,_,target=self.setup_case(row,0)
        pid='p2' if row['scope']=='cz_non_token' else 'p1'
        zone='interzone' if row['scope']=='interzone' else 'confrontation'
        token=s.create_rules_token_copy(None,pid,generic_power=2,generic_temperament='phlegmatic',field_zone=zone)
        clone=s.create_rules_token_copy('m4',pid,field_zone=zone)
        if row['scope']=='exhausted': token['rotation']=clone['rotation']=90
        self.begin(s,row,host,target)
        self.resolve(s,row,0 if row['scope']=='cz_non_token' else 2)

    def check_animated_will(self,row):
        s,host,_,target=self.setup_case(row,0)
        scope=row['scope']
        item=self.field(s,'pw3','animated',owner='p2' if scope=='cz_non_token' else 'p1',
            zone='interzone' if scope=='interzone' else 'confrontation')
        item['willManifestation']={'power':3,'turn':2}
        self.begin(s,row,host,target)
        self.resolve(s,row,1)

    def check_control_change(self,row):
        s,host,counted,target=self.setup_case(row)
        self.begin(s,row,host,target)
        counted[0]['controllerId']=self.other(counted[0]['controllerId'])
        self.resolve(s,row,1)

    def check_plea_own_player(self,row): self.normal(row,units=3,target='p1')

    def check_plea_unpayable(self,row):
        s,_,_,target=self.setup_case(row)
        s.tokens=[]
        before=copy.deepcopy((s.players,s.battlefield,s.rules_engine))
        error,_=s.declare_rules_action('p1',row['name'],kind='play_card',
            source={'cardId':row['cardId'],'zone':'hand'},ability_id=row['abilityId'],
            targets=[{'kind':'player','playerId':target}])
        self.assertIsNotNone(error)
        self.assertEqual((s.players,s.battlefield,s.rules_engine),before)

    def check_plea_declaration_guards(self,row):
        for condition in ('wrong_priority','missing_player','pending_choice'):
            with self.subTest(condition=condition):
                s,_,_,target=self.setup_case(row)
                if condition=='wrong_priority': s.rules_engine['priorityPlayerId']='p2'
                if condition=='pending_choice': s.rules_engine['pendingChoice']={'id':'waiting','playerId':'p2','kind':'discard_from_hand'}
                before=copy.deepcopy((s.players,s.battlefield,s.rules_engine,s.tokens))
                error,_=s.declare_rules_action('p1',row['name'],kind='play_card',
                    source={'cardId':row['cardId'],'zone':'hand'},ability_id=row['abilityId'],
                    targets=[{'kind':'player','playerId':'gone' if condition=='missing_player' else target}])
                self.assertIsNotNone(error)
                self.assertEqual((s.players,s.battlefield,s.rules_engine,s.tokens),before)

    def check_vessel_duplicates(self,row):
        s,host,_,target=self.setup_case(row,0)
        for _ in range(3): s.put_zone_card('p2','receptacle','m2','p1')
        self.begin(s,row,host,target)
        self.resolve(s,row,3)

    def check_animation_resets_in_vessel(self,row):
        s,host,_,target=self.setup_case(row,0)
        animated=self.field(s,'pw3','animated-will')
        animated['willManifestation']={'power':3,'turn':2}
        self.begin(s,row,host,target)
        s._rules_remove_field_item_by_effect(animated,'p2','receptacle')
        self.resolve(s,row,0)  # In the Vessel it is its printed Will, not a Manifestation.

    def check_donmo_rotations(self,row):
        s,host,_,target=self.setup_case(row,0)
        for index,rotation in enumerate((0,90,180,270,360)):
            item=self.field(s,'pw3','rotation-'+str(index),zone='field')
            item['rotation']=rotation
        self.begin(s,row,host,target)
        self.resolve(s,row,2)

    def check_donmo_counts_itself(self,row):
        s,host,_,target=self.setup_case(row,0)
        host['rotation']=90
        self.begin(s,row,host,target)
        self.resolve(s,row,1)

    def check_donmo_skipped_end(self,row):
        s,_,_,_=self.setup_case(row)
        s.rules_engine['skipEndPhaseTurns']={'p1':2}
        self.assertFalse(any(a['ability']['id']==row['abilityId'] for a in s.build_rules_end_turn_field_triggers()))

    def check_excess_floor(self,row):
        s,host,counted,target=self.setup_case(row,0)
        counted[0]['counters']['power']=3
        self.begin(s,row,host,target)
        self.resolve(s,row,0)

    def check_excess_current_powers(self,row):
        s,host,counted,target=self.setup_case(row)
        host['baseDoublings']=1
        host['counters']['power']=2  # 5*2+2=12
        counted[0]['counters']['power']=1  # 3+1=4
        self.begin(s,row,host,target)
        self.resolve(s,row,8)

    def check_excess_source_reset(self,row):
        s,host,_,target=self.setup_case(row)
        host['baseDoublings']=1
        host['counters']['power']=7
        self.begin(s,row,host,target)
        s._rules_remove_field_item(host,'p1','graveyard')
        self.resolve(s,row,2)  # printed 5 minus current opponent 3

    def check_excess_promoted_first(self,row):
        s,host,counted,target=self.setup_case(row)
        support=s.find_battlefield_item('opponent-support')
        support['counters']={}
        self.begin(s,row,host,target)
        s._rules_remove_field_item(counted[0],'p2','hand')
        s.prune_rules_ongoing_effects()
        self.assertEqual(s.rules_engine['firstManifestationItemIds']['p2'],support['id'])
        self.resolve(s,row,1)  # source 5 minus promoted Support 4

    def check_excess_empty_opponent(self,row):
        s,host,counted,target=self.setup_case(row)
        self.begin(s,row,host,target)
        s._rules_remove_field_item(counted[0],'p2','hand')
        s._rules_remove_field_item(s.find_battlefield_item('opponent-support'),'p2','hand')
        s.prune_rules_ongoing_effects()
        self.assertNotIn('p2',s.rules_engine['firstManifestationItemIds'])
        self.resolve(s,row,5)

    def check_excess_source_new_instance(self,row):
        s,host,_,target=self.setup_case(row)
        self.begin(s,row,host,target)
        s._rules_remove_field_item(host,'p1','hand')
        returned=s.place_rules_card_in_interzone('p1','p1','hand',row['cardId'])
        self.assertIsNotNone(returned)
        returned['counters']['power']=10
        self.assertNotEqual(returned['id'],host['id'])
        self.resolve(s,row,2)  # New field instance's bonus must not feed the old source.


def scenarios(row):
    common=['zero','one','two','three','negative_scores','other_controller','prevention','balance',
            'late_increase','late_decrease']
    if row['mode']=='event': common+=['source_departure','trigger_guards','builder','source_control_after_queue']
    scope=row['scope']
    if scope in {'interzone','cz_non_token','exhausted'}: common+=['tokens_and_copies','control_change','counted_protected']
    if scope in {'interzone','cz_non_token'}: common+=['animated_will']
    if scope in {'interzone','vessel_owned'}: common+=['source_joins_counted_zone']
    if scope=='cz_non_token': common+=['plea_own_player','plea_unpayable','plea_declaration_guards']
    if scope=='vessel_owned': common+=['vessel_duplicates','animation_resets_in_vessel']
    if scope=='exhausted': common+=['donmo_rotations','donmo_counts_itself','donmo_skipped_end']
    if scope=='first_difference': common+=['excess_floor','excess_current_powers','excess_source_reset',
        'excess_promoted_first','excess_empty_opponent','excess_source_new_instance']
    return common


def method_name(row,scenario): return 'test_'+row['key']+'__'+scenario


for contract in CONTRACTS:
    for scenario in scenarios(contract):
        def run(self,row=contract,scenario=scenario): getattr(self,'check_'+scenario)(row)
        setattr(ScaledScoreFamily,method_name(contract,scenario),run)


class ScaledScoreOracleSensitivity(unittest.TestCase):
    def test_each_multiplier_is_observed(self):
        f=ScaledScoreFamily()
        for row in CONTRACTS:
            with self.subTest(card=row['key']):
                wrong=copy.deepcopy(row)
                wrong['expectedMultiplier']+=73
                with self.assertRaises(AssertionError): f.normal(wrong)


if __name__=='__main__': unittest.main()
