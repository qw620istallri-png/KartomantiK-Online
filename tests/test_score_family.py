"""Selected fixed-point clauses: real event queues and exact, manual score oracles.

Events in this matrix are explicit stimuli. Producer actions and compound
non-score clauses require dedicated cases, not certification by association.
"""
import copy
import unittest
import main

from card_effect_families import load_score_contracts
import test_discard_draw_clauses as fixtures

CONTRACTS = load_score_contracts()


class ScoreFamily(unittest.TestCase):
    world = fixtures.DiscardDrawClauses.world
    field = staticmethod(fixtures.DiscardDrawClauses.field)
    put = staticmethod(fixtures.DiscardDrawClauses.put)
    target = staticmethod(fixtures.base.AtavicEndClauses.target)

    def setup_case(self, row, controller='p1'):
        s = self.world()
        host = None
        if row['sourceZone'] in {'graveyard', 'receptacle'}:
            container = 'p2' if row['sourceZone']=='receptacle' else 'p1'
            s.put_zone_card(container, row['sourceZone'], row['cardId'], 'p1')
            # This fixture only supplies the trigger; entry events are not reused.
            s.rules_engine['observedEvents'] = []
        else:
            host = self.field(s, row['cardId'], 'score-source', zone=row['sourceZone'], controller=controller)
            if row.get('thresholdCounter'):
                host['counters'][row['thresholdCounter']] = row['threshold']
        if row.get('leftVessel'):
            s.rules_engine['leftVesselCards'] = ['p1:'+row['cardId']]
        picked = self.field(s, 'm4', 'score-target', owner=controller) if row.get('optionalPowerTarget') else None
        return s, host, picked

    def event_player(self, row, controller):
        return ('p2' if controller=='p1' else 'p1') if row['eventRelation']=='opponent' else controller

    def recipient(self, row, controller, event_player):
        return {'controller':controller, 'owner':'p1', 'event':event_player,
                'container':'p2', 'opponent':'p2' if controller=='p1' else 'p1'}[row['recipient']]

    def queue(self, s, row, host, picked, *, event=None, event_player=None, zone=None, container=None):
        controller = s.rules_item_controller_id(host) if host else 'p1'
        return [a for a in s.queue_rules_triggers(row['cardId'], 'p1', event or row['event'],
            item_id=(host or {}).get('id'), zone=zone or row['sourceZone'],
            container_id=container or ('p2' if row['sourceZone']=='receptacle' else None),
            face_up=(host or {}).get('faceUp', True), controller_id=controller,
            event_controller_id=event_player or self.event_player(row, controller),
            event_targets=[self.target(picked)] if picked else [], defer=True)
            if a['ability']['id']==row['abilityId']]

    def begin(self, s, row, host, picked, **kwargs):
        before = self.scores(s)
        actions = self.queue(s,row,host,picked,**kwargs)
        self.assertEqual(len(actions),1, row['key'])
        s.queue_rules_simultaneous_actions(actions)
        self.assertEqual(self.scores(s),before, 'A normal trigger must wait on the Stack')
        self.assertIsNone(s.rules_engine['pendingChoice'])
        self.assertEqual(s.rules_engine['actionStack'][-1]['id'],actions[0]['id'])
        return actions[0]

    @staticmethod
    def scores(s): return {pid:p['score'] for pid,p in s.players.items()}

    def normal(self, row, *, controller='p1', start=50, event_player=None):
        s, host, picked = self.setup_case(row,controller)
        for p in s.players.values(): p['score']=start
        event_player=event_player or self.event_player(row,controller)
        self.begin(s,row,host,picked,event_player=event_player)
        expected={pid:start for pid in s.players}
        expected[self.recipient(row,controller,event_player)]+=row['expectedDelta']
        s.resolve_rules_top_action()
        self.assertEqual(self.scores(s),expected)
        if picked: self.assertEqual(s.rules_manifestation_characteristics(picked)['power'],5)
        return s,host,picked

    def check_exact(self,row): self.normal(row)
    def check_negative_score(self,row): self.normal(row,start=-100)

    def check_twice(self,row):
        s,host,picked=self.normal(row)
        self.begin(s,row,host,picked)
        s.resolve_rules_top_action()
        expected={'p1':50,'p2':50}
        expected[self.recipient(row,'p1',self.event_player(row,'p1'))]+=2*row['expectedDelta']
        self.assertEqual(self.scores(s),expected)

    def check_prevention(self,row):
        s,host,picked=self.setup_case(row)
        self.begin(s,row,host,picked)
        s.rules_engine['ongoingEffects'].append({'kind':'prevent_point_changes'})
        s.resolve_rules_top_action()
        self.assertEqual(self.scores(s),{'p1':50,'p2':50})
        self.assertFalse(any(e['kind'] in {'points_gained','points_lost'}
                             for e in s.rules_engine.get('observedEvents',[])))
        if picked: self.assertEqual(s.rules_manifestation_characteristics(picked)['power'],5)

    def check_wrong_event(self,row):
        s,host,picked=self.setup_case(row)
        self.assertEqual(self.queue(s,row,host,picked,event='not-a-card-event'),[])
        self.assertEqual(self.scores(s),{'p1':50,'p2':50})

    def check_controller(self,row): self.normal(row,controller='p2')

    def check_event_player(self,row):
        s,host,picked=self.setup_case(row)
        if row['eventRelation']=='any': self.normal(row,event_player='p2')
        else:
            wrong='p1' if row['eventRelation']=='opponent' else 'p2'
            self.assertEqual(self.queue(s,row,host,picked,event_player=wrong),[])

    def check_hidden(self,row):
        s,host,picked=self.setup_case(row)
        host['faceUp']=False
        self.assertEqual(self.queue(s,row,host,picked),[])

    def check_disabled(self,row):
        s,host,picked=self.setup_case(row)
        host['effectsDisabled']=True
        self.assertEqual(self.queue(s,row,host,picked),[])

    def check_source_departure(self,row):
        s,host,picked=self.setup_case(row)
        self.begin(s,row,host,picked)
        # The already queued normal effect is independent of its departed source.
        s._rules_remove_field_item(host,'p1','hand','top')
        s.resolve_rules_top_action()
        expected={'p1':50,'p2':50}
        expected[self.recipient(row,'p1',self.event_player(row,'p1'))]+=row['expectedDelta']
        self.assertEqual(self.scores(s),expected)

    def check_wrong_zone(self,row):
        s,host,picked=self.setup_case(row)
        host['fieldZone']='confrontation'
        self.assertEqual(self.queue(s,row,host,picked,zone='confrontation'),[])

    def check_counter_threshold(self,row):
        for amount,expected in ((9,0),(10,1),(11,1)):
            with self.subTest(amount=amount):
                s,host,picked=self.setup_case(row)
                host['counters'][row['thresholdCounter']]=amount
                self.assertEqual(len(self.queue(s,row,host,picked)),expected)

    def check_history(self,row):
        s,host,picked=self.setup_case(row)
        s.rules_engine['leftVesselCards']=[] if row['leftVessel'] else ['p1:'+row['cardId']]
        self.assertEqual(self.queue(s,row,host,picked),[])

    def check_own_vessel(self,row):
        s,host,picked=self.setup_case(row)
        # Negative event filter only: no illegal own-Vessel placement is made.
        self.assertEqual(self.queue(s,row,host,picked,container='p1'),[])

    def check_optional_target(self,row):
        s,host,picked=self.setup_case(row)
        s.battlefield.remove(picked)
        self.begin(s,row,host,None)
        s.resolve_rules_top_action()
        self.assertEqual(self.scores(s),{'p1':55,'p2':50})
        # Linoleus's own bonus cannot generate another points-gained trigger.
        self.assertEqual(s.rules_engine['actionStack'],[])
        self.assertIsNone(s.rules_engine['pendingChoice'])

    def check_balance_tie(self,row):
        s,host,picked=self.setup_case(row)
        self.field(s,'inner-deserts-137','balance',zone='field')
        # Card points in a Vessel count too; equalize real totals explicitly.
        for pid in s.players: s.players[pid]['score']=50-s.rules_vessel_total(pid)+s.players[pid]['score']
        before=self.scores(s)
        self.begin(s,row,host,picked)
        s.resolve_rules_top_action()
        before[self.recipient(row,'p1',self.event_player(row,'p1'))]+=row['expectedDelta']
        self.assertEqual(self.scores(s),before)

    def check_balance_redirect(self,row):
        s,host,picked=self.setup_case(row)
        self.field(s,'inner-deserts-137','balance',zone='field')
        recipient=self.recipient(row,'p1',self.event_player(row,'p1'))
        other='p2' if recipient=='p1' else 'p1'
        for pid in s.players: s.players[pid]['score']=50-s.rules_vessel_total(pid)+s.players[pid]['score']
        s.players[recipient]['score']+=30 if row['expectedDelta']>0 else -30
        before=self.scores(s)
        self.begin(s,row,host,picked)
        s.resolve_rules_top_action()
        before[other]+=row['expectedDelta']
        self.assertEqual(self.scores(s),before)

    def check_producer(self,row):
        """Use real builders/movements instead of supplying an observed event."""
        s,host,picked=self.setup_case(row)
        key=row['key']
        expected={'p1':50,'p2':50}
        if row['event']=='beginning_of_turn':
            actions=s.queue_rules_beginning_turn_triggers(defer=True)
            self.assertEqual(s.queue_rules_beginning_turn_triggers(defer=True),[])
        elif key in {'pale_discard','forfog'}:
            self.put(s,'p2','hand',['m2','m3'])
            for cid in ('m2','m3'):
                error,_=s.move_zone_card('p2','hand','p2','graveyard',cid)
                self.assertIsNone(error)
            actions=s.queue_rules_observed_event_triggers(defer=True)
        elif key in {'pale_loss','shuk','linoleus'}:
            if picked: s.battlefield.remove(picked)
            pid='p2' if key=='pale_loss' else 'p1'
            delta=10 if key=='linoleus' else -10
            self.assertEqual(s.adjust_rules_score(pid,delta),delta)
            expected[pid]+=delta
            actions=s.queue_rules_observed_event_triggers(defer=True)
        elif key=='orchard':
            donor=self.field(s,'m2','donor',controller='p2')
            s._rules_remove_field_item_by_effect(donor,'p2','receptacle')
            self.assertEqual(s.players['p2']['zones']['receptacle'],['m2'])
            actions=s.queue_rules_observed_event_triggers(defer=True)
        elif key=='welcome':
            entrant=self.field(s,'m2','entrant',support=True)
            actions=s.queue_rules_support_entry_triggers(entrant,played=False,from_zone='interzone',defer=True)
        elif key in {'fury','chariot_loser'}:
            s.rules_engine['confrontationResult']={'turn':2,'winnerId':'p1' if key=='fury' else 'p2',
                'loserId':'p2' if key=='fury' else 'p1','stalemate':False,'participantItemIds':[]}
            actions=s.queue_rules_confrontation_win_triggers(defer=True)
        elif key=='kox_limbo':
            s.take_zone_card('p1','graveyard',row['cardId'])
            s.put_zone_card('p1','graveyard',row['cardId'],'p1',from_zone='hand',limbo_reason='discard')
            actions=s.queue_rules_observed_event_triggers(defer=True)
        elif key in {'katun_five','katun_ten'}:
            for owner in ('p1','p2'):
                donor=self.field(s,'m2','depart-'+owner,owner=owner)
                s._rules_remove_field_item_by_effect(donor,owner,'hand')
            actions=s.queue_rules_observed_event_triggers(defer=True)
        elif key=='imgurd':
            donor=self.field(s,'m4','weakened',owner='p2')
            s.adjust_rules_power_counter(donor,-2)
            self.assertEqual(s.rules_manifestation_characteristics(donor)['power'],2)
            actions=s.queue_rules_observed_event_triggers(defer=True)
        else: raise AssertionError('No producer adapter for '+key)
        actions=[a for a in actions if a['ability']['id']==row['abilityId']]
        count=2 if key.startswith('katun') else 1
        self.assertEqual(len(actions),count)
        self.assertEqual(self.scores(s),expected)
        # Independent builder proof, not simultaneous-order certification.
        for action in actions:
            s.rules_engine['actionStack']=[action]
            s.resolve_rules_top_action()
        expected[self.recipient(row,'p1',self.event_player(row,'p1'))]+=count*row['expectedDelta']
        self.assertEqual(self.scores(s),expected)

    def check_paid_producer(self,row):
        for trigger_first in (True,False):
            with self.subTest(trigger_first=trigger_first):
                s,host,_=self.setup_case(row)
                target=self.field(s,'m4','paid-target')
                will='lo85kdsow36bymu_en'  # Strengthen, printed cost {H}.
                tribute=row['key']=='zam_za'
                self.put(s,'p1','hand',[will]+([row['cardId']] if tribute else []))
                if tribute: s.take_zone_card('p1','graveyard',row['cardId'])
                else: s.add_rules_excess_essence('p1',[{'temperament':'hollow','amount':1}])
                error,action=s.declare_rules_action('p1','Strengthen',kind='play_card',
                    source={'cardId':will,'zone':'hand'},ability_id='strengthen-power-modifier',
                    targets=[self.target(target)],payment_card_ids=[row['cardId']] if tribute else None)
                self.assertIsNone(error)
                main.log_rules_declared_action(s,action)
                choice=s.rules_engine['pendingChoice']
                self.assertEqual(choice['kind'],'simultaneous_stack_order')
                effects=[a for a in choice['_group'] if a['ability']['id']==row['abilityId']]
                self.assertEqual(len(effects),1)
                effect=effects[0]
                order=[action['id'],effect['id']] if trigger_first else [effect['id'],action['id']]
                error,_=s.resolve_rules_choice('p1',choice['id'],card_ids=order)
                self.assertIsNone(error)
                self.assertEqual(self.scores(s),{'p1':50,'p2':50})
                s.resolve_rules_top_action()
                expected={'p1':50,'p2':50}
                expected[self.recipient(row,'p1','p1')]+=row['expectedDelta']
                self.assertEqual(self.scores(s),expected if trigger_first else {'p1':50,'p2':50})
                s.resolve_rules_top_action()
                self.assertEqual(self.scores(s),expected)
                self.assertEqual(s.rules_manifestation_characteristics(target)['power'],7)
                if tribute:
                    self.assertIn(row['cardId'],s.players['p1']['zones']['graveyard'])
                    self.assertEqual(action['cost']['excessEssence'],[{'temperament':'phlegmatic','amount':3}])


PRODUCERS={'incubator','soul_borer','otranth','pale_discard','pale_loss','forfog','shuk','linoleus',
           'orchard','welcome','fury','chariot_loser','kox_limbo','katun_five','katun_ten','imgurd'}


def scenarios(row):
    result=['exact','negative_score','twice','prevention','wrong_event','balance_tie','balance_redirect']
    if row['event'] not in {'enters_field','enters_zone','enters_limbo','beginning_of_turn',
                            'used_as_tribute','loses_confrontation'}:
        result+=['event_player']
    if row['sourceZone'] not in {'receptacle','graveyard'}:
        result+=['controller','hidden','disabled','source_departure']
    if row['sourceZone']=='interzone' and row['event']!='enters_field': result+=['wrong_zone']
    if row.get('thresholdCounter'): result+=['counter_threshold']
    if 'leftVessel' in row: result+=['history']
    if row['sourceZone']=='receptacle': result+=['own_vessel']
    if row.get('optionalPowerTarget'): result+=['optional_target']
    if row['key'] in PRODUCERS: result+=['producer']
    if row['key'] in {'cannon','zam_za'}: result+=['paid_producer']
    return result


def method_name(row,scenario): return 'test_'+row['key']+'__'+scenario


for row in CONTRACTS:
    for scenario in scenarios(row):
        def run(self, row=row, scenario=scenario): getattr(self,'check_'+scenario)(row)
        setattr(ScoreFamily,method_name(row,scenario),run)


class ScoreFamilyOracleSensitivity(unittest.TestCase):
    def test_each_handwritten_delta_is_observed(self):
        f=ScoreFamily()
        for row in CONTRACTS:
            with self.subTest(contract=row['key']):
                wrong=copy.deepcopy(row)
                wrong['expectedDelta']+=73
                with self.assertRaises(AssertionError): f.normal(wrong)


if __name__=='__main__': unittest.main()
