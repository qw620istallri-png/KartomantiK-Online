"""One executable test ID per real effect and scenario, using handwritten oracles.

Voluntary effects use actual declarations/costs; triggered effects use the
production event queue with explicit stimuli. Full event-producing matches
and other printed clauses remain separate from these selected modifier proofs.
"""
import copy
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from card_effect_families import load_power_contracts
import test_discard_draw_clauses as fixtures
from session import ADVANCED_PHASES

CONTRACTS = load_power_contracts()
COLORS = ('hollow', 'choleric', 'capricious', 'phlegmatic', 'vitreous', 'melancholic')


class PowerFamily(unittest.TestCase):
    world = fixtures.DiscardDrawClauses.world
    field = staticmethod(fixtures.DiscardDrawClauses.field)
    put = staticmethod(fixtures.DiscardDrawClauses.put)
    target = staticmethod(fixtures.base.AtavicEndClauses.target)
    snapshot = fixtures.DiscardDrawClauses.snapshot

    def setup_case(self, row, *, funded=True, token=False, base=None, bonus=0):
        s = self.world()
        base = row['targetBase'] if base is None else base
        s.card_rules['family-probe'] = {'type':'manifestation', 'power':base,
            'temperaments':['phlegmatic'], 'powerCost':'{G}'}
        s.manifestation_ids.add('family-probe')
        cid = row['cardId']
        host = None
        if row['mode'] == 'play': self.put(s, 'p1', 'hand', [cid])
        elif row['sourceZone'] == 'graveyard': self.put(s, 'p1', 'graveyard', [cid])
        else:
            host = self.field(s, cid, 'family-source', zone=row['sourceZone'])
            host['counters'].update(row.get('counterCost', {}))
        owner = 'p1' if row['targetRelation'] in {'self','source'} else 'p2'
        zone = 'confrontation' if row['targetZone']=='field' else row['targetZone']
        if row['targetRelation']=='source':
            picked = host
        elif token:
            picked = s.create_rules_token_copy(None, owner, generic_power=base,
                generic_temperament='phlegmatic', field_zone=zone)
        else:
            picked = self.field(s, 'family-probe', 'family-target', owner=owner, zone=zone)
        if bonus: picked['counters']['power'] = bonus
        # Same printed power, two owners; neither may receive the targeted change.
        others = [self.field(s, 'm4', 'unrelated-' + p, owner=p, zone='confrontation') for p in ('p1','p2')]
        if funded:
            s.add_rules_excess_essence('p1', [{'temperament':c,'amount':30} for c in COLORS])
        if row.get('stimulus')=='hand_choleric_will':
            pid='p2' if row.get('eventRelation')=='opponent' else 'p1'
            self.put(s,pid,'hand',['obn1uv72ewxv3y5_en'])
        return s, host, picked, others

    def queue_event(self, s, row, host, targets):
        event_pid = 'p2' if row.get('eventRelation')=='opponent' else 'p1'
        related = None
        event_card = None
        if row.get('stimulus')=='hand_choleric_will':
            event_card = 'obn1uv72ewxv3y5_en'  # Printed red Oppress; event fixture, not a paid play.
            related = {'id':'family-event', 'kind':'play_card', 'controllerId':event_pid,
                       'source':{'cardId':event_card,'zone':'hand','ownerId':event_pid}}
        return s.queue_rules_triggers(row['cardId'], 'p1', row['event'],
            item_id=(host or {}).get('id'), zone=row['sourceZone'],
            container_id='p1' if row['sourceZone']=='graveyard' else None,
            face_up=(host or {}).get('faceUp',True), controller_id='p1',
            event_controller_id=event_pid, related_action=related,
            event_card_id=event_card, event_targets=targets, defer=True)

    def begin(self, s, row, host, picked):
        targets = [self.target(picked)]
        if row['mode']=='event':
            actions = [a for a in self.queue_event(s,row,host,targets) if a['ability']['id']==row['abilityId']]
            if not actions: return 'No eligible queued effect for the supplied event and target.', None
            self.assertEqual(len(actions),1)
            s.queue_rules_simultaneous_actions(actions)
            return None, actions[0]
        source = {'cardId':row['cardId'], 'zone':'hand'} if row['mode']=='play' else {
            'cardId':row['cardId'], 'zone':'battlefield', 'itemId':host['id']}
        return s.declare_rules_action('p1', row['name'], kind='play_card' if row['mode']=='play' else 'activated_effect',
            source=source, ability_id=row['abilityId'], targets=targets)

    def power(self, s, item):
        return s.rules_manifestation_characteristics(item)['power']

    def resolve(self, s, row, host, picked):
        error, action = self.begin(s,row,host,picked)
        self.assertIsNone(error, row['key'])
        self.assertEqual(s.rules_engine['actionStack'][-1]['id'],action['id'])
        s.resolve_rules_top_action()
        return action

    def normal(self, row, *, token=False, base=None, bonus=0):
        s, host, picked, others = self.setup_case(row,token=token,base=base,bonus=bonus)
        expected_base = row['targetBase'] if base is None else base
        before = [self.power(s,i) for i in others]
        error, action = self.begin(s,row,host,picked)
        self.assertIsNone(error, row['key'])
        self.assertEqual(self.power(s,picked),expected_base+bonus, 'Power must wait for resolution')
        if row['mode']!='event':
            spent = Counter()
            for payment in action['cost'].get('essenceSpent',[]): spent[payment['temperament']]+=payment['amount']
            self.assertEqual(dict(spent),row['essenceCost'])
            for name, count in row.get('counterCost',{}).items():
                self.assertEqual((host.get('counters') or {}).get(name,0),0)
                self.assertIn({'name':name,'amount':count},action['cost']['removedCounters'])
            if row.get('exhaust'): self.assertEqual(int(host['rotation']) % 180,90)
            self.assertEqual(s.players['p1']['score'],50-row.get('scoreCost',0))
        s.resolve_rules_top_action()
        self.assertEqual(self.power(s,picked),expected_base+bonus+row['expectedDelta'])
        self.assertEqual([self.power(s,i) for i in others],before)
        if row['mode']=='play': self.assertEqual(s.players['p1']['zones']['graveyard'].count(row['cardId']),1)
        if row.get('sourceExiled'): self.assertIn(row['cardId'],s.players['p1']['zones']['exile'])
        if row.get('extraScore'): self.assertEqual(s.players['p1']['score'],50+row['extraScore'])
        return s, host, picked

    def check_normal(self,row): self.normal(row)

    def check_existing_bonus(self,row):
        # Flower's total is still <=2 at declaration; no illegal capped target.
        base, bonus = (1,1) if row.get('maxPower') else (row['targetBase'],2)
        if row['targetRelation']=='source': base=2
        self.normal(row,base=base,bonus=bonus)

    def check_token(self,row): self.normal(row,token=True)

    def check_duration(self,row):
        s, host, picked = self.normal(row)
        s.phase_tracker['turn']+=1
        s.prune_rules_ongoing_effects()
        delta = 0 if row['lifetime']=='turn' else row['expectedDelta']
        self.assertEqual(self.power(s,picked),row['targetBase']+delta)

    def check_cleanse(self,row):
        s, host, picked = self.normal(row)
        cleanse = 'inner-deserts-145'
        s.put_zone_card('p1','hand',cleanse,'p1')
        s.rules_engine.update(priorityPlayerId='p1',priorityPasses=[],pendingChoice=None)
        error, action = s.declare_rules_action('p1','Cleanse',kind='play_card',
            source={'cardId':cleanse,'zone':'hand'},ability_id='remove-target-modifiers',targets=[self.target(picked)])
        self.assertIsNone(error)
        s.resolve_rules_top_action()
        self.assertEqual(self.power(s,picked),row['targetBase'])
        # A resolved modifier must not be reapplied at the next recomputation.
        s.prune_rules_ongoing_effects()
        self.assertEqual(self.power(s,picked),row['targetBase'])

    def check_leave_reset(self,row):
        s, host, picked = self.normal(row)
        owner, cid = picked['ownerId'],picked.get('cardId')
        self.assertIsNotNone(cid)
        s._rules_remove_field_item(picked,owner,'hand','top')
        new = s.place_rules_card_in_interzone(owner,owner,'hand',cid)
        self.assertIsNotNone(new)
        self.assertNotEqual(new['id'],picked['id'])
        self.assertEqual(self.power(s,new),row['targetBase'])

    def check_invalid_contract(self,row):
        cases=['stalemate','will']
        if row['targetZone']!='field': cases.append('other_zone')
        if row['targetRelation'] in {'self','opponent'}: cases.append('other_controller')
        if row.get('maxPower'): cases.append('too_powerful')
        if row.get('excludeSource'): cases.append('source')
        for case in cases:
            with self.subTest(invalid=case):
                s, host, picked, _ = self.setup_case(row)
                if case=='stalemate': picked['fieldZone']='stalemate'
                elif case=='will':
                    picked['cardId']='pw3'; picked['fieldZone']='field'
                elif case=='other_zone': picked['fieldZone']='interzone' if row['targetZone']=='confrontation' else 'confrontation'
                elif case=='other_controller': picked['controllerId']='p2' if picked['controllerId']=='p1' else 'p1'
                elif case=='too_powerful': picked['counters']['power']=1
                elif case=='source': picked=host
                before=self.snapshot(s)
                error, action=self.begin(s,row,host,picked)
                self.assertIsNotNone(error)
                self.assertIsNone(action)
                self.assertEqual(self.snapshot(s),before)

    def late(self,row,kind):
        s, host, picked, others=self.setup_case(row)
        error, action=self.begin(s,row,host,picked)
        self.assertIsNone(error)
        if kind=='gone': s._rules_remove_field_item(picked,picked['ownerId'],'hand','top')
        elif kind=='stalemate': picked['fieldZone']='stalemate'
        elif kind=='controller': picked['controllerId']='p2' if picked['controllerId']=='p1' else 'p1'
        elif kind=='protected': s.rules_engine['ongoingEffects'].append({'id':'family-protection','kind':'protection',
            'target':self.target(picked),'duration':'until_end_of_turn','startedTurn':s.phase_tracker['turn']})
        before=[self.power(s,i) for i in others]
        s.resolve_rules_top_action()
        if kind!='gone': self.assertEqual(self.power(s,picked),row['targetBase'])
        else: self.assertIsNone(s.find_battlefield_item(picked['id']))
        self.assertEqual([self.power(s,i) for i in others],before)
        self.assertEqual(len(s.rules_engine['actionStack']),0)

    def check_target_gone(self,row): self.late(row,'gone')
    def check_target_stalemate(self,row): self.late(row,'stalemate')
    def check_target_controller(self,row): self.late(row,'controller')
    def check_target_protected(self,row): self.late(row,'protected')

    def check_source_gone(self,row):
        s, host, picked, _=self.setup_case(row)
        error, action=self.begin(s,row,host,picked)
        self.assertIsNone(error)
        if host: s._rules_remove_field_item(host,'p1','graveyard','top')
        else: s.move_zone_card('p1','graveyard','p1','hand',row['cardId'],'top')
        s.resolve_rules_top_action()
        delta=0 if row['lifetime']=='linked' else row['expectedDelta']
        self.assertEqual(self.power(s,picked),row['targetBase']+delta)

    def check_wrong_priority(self,row):
        s, host, picked, _=self.setup_case(row)
        s.rules_engine['priorityPlayerId']='p2'
        before=self.snapshot(s)
        self.assertIsNotNone(self.begin(s,row,host,picked)[0])
        self.assertEqual(self.snapshot(s),before)

    def check_unpaid(self,row):
        s, host, picked, _=self.setup_case(row,funded=False)
        for name,amount in row.get('counterCost',{}).items(): host['counters'][name]=amount-1
        before=self.snapshot(s)
        self.assertIsNotNone(self.begin(s,row,host,picked)[0])
        self.assertEqual(self.snapshot(s),before)

    def check_use_limit(self,row):
        s, host, picked, _=self.setup_case(row)
        if row.get('oncePerTurn'): host['abilityTurnUses']={row['abilityId']:s.phase_tracker['turn']}
        else: host['abilityUses']={row['abilityId']:row['useLimit']}
        before=self.snapshot(s)
        self.assertIsNotNone(self.begin(s,row,host,picked)[0])
        self.assertEqual(self.snapshot(s),before)

    def check_source_states(self,row):
        states=['covered','stalemate','disabled','other_controller']
        if row.get('exhaust'): states.append('already_exhausted')
        for state in states:
            with self.subTest(source=state):
                s, host, picked, _=self.setup_case(row)
                if state=='covered': host['faceUp']=False
                elif state=='stalemate': host['fieldZone']='stalemate'
                elif state=='disabled': host['effectsDisabled']=True
                elif state=='other_controller': host['controllerId']='p2'
                elif state=='already_exhausted': host['rotation']=90
                before=self.snapshot(s)
                self.assertIsNotNone(self.begin(s,row,host,picked)[0])
                self.assertEqual(self.snapshot(s),before)

    def check_trigger_guards(self,row):
        guards=['face_down'] if row['sourceZone']!='graveyard' else []
        if row.get('requiredSourceZone'): guards.append('source_zone')
        if row.get('eventRelation'): guards.append('event_controller')
        if row.get('stimulus'): guards.append('non_red_stimulus')
        if row.get('onlyConfrontation'): guards.append('outside_phase')
        for guard in guards:
            with self.subTest(guard=guard):
                s, host, picked, _=self.setup_case(row)
                altered=copy.deepcopy(row)
                if guard=='face_down': host['faceUp']=False
                elif guard=='source_zone': host['fieldZone']='confrontation'
                elif guard=='event_controller': altered['eventRelation']='self' if row['eventRelation']=='opponent' else 'opponent'
                elif guard=='non_red_stimulus':
                    # Change the event fixture's printed temperament, not the ability.
                    s.card_rules['obn1uv72ewxv3y5_en']['temperaments']=['phlegmatic']
                elif guard=='outside_phase': s.phase_tracker['index']=ADVANCED_PHASES.index('end_actions')
                actions=self.queue_event(s,altered,host,[self.target(picked)])
                self.assertFalse(any(a['ability']['id']==row['abilityId'] for a in actions))

    def check_phase(self,row):
        for phase in ('end_actions','confrontation_before_revelation'):
            s, host, picked, _=self.setup_case(row)
            s.phase_tracker['index']=ADVANCED_PHASES.index(phase)
            before=self.snapshot(s)
            self.assertIsNotNone(self.begin(s,row,host,picked)[0])
            self.assertEqual(self.snapshot(s),before)


def scenarios(row):
    common=['normal','existing_bonus','duration','cleanse','leave_reset','target_gone','target_stalemate']
    if row['targetRelation']!='source':
        common+=['token','invalid_contract','target_protected']
        if row['mode']!='play': common+=['source_gone']
    if row['targetRelation'] in {'self','opponent'}: common+=['target_controller']
    if row['mode']!='event': common+=['wrong_priority']
    if row['mode']!='event' and (row['essenceCost'] or row.get('counterCost')): common+=['unpaid']
    if row.get('useLimit') or row.get('oncePerTurn'): common+=['use_limit']
    if row['mode']=='activate': common+=['source_states']
    if row['mode']=='event' and (row['sourceZone']!='graveyard' or row.get('eventRelation')
            or row.get('requiredSourceZone') or row.get('stimulus') or row.get('onlyConfrontation')):
        common+=['trigger_guards']
    if row['mode']=='play' and row.get('onlyReaction'): common+=['phase']
    return common


def method_name(row, scenario): return 'test_'+row['key']+'__'+scenario


for contract in CONTRACTS:
    for scenario in scenarios(contract):
        def exercise(self, row=contract, check=scenario):
            getattr(self,'check_'+check)(row)
        exercise.__doc__=contract['name']+' / '+scenario+' / independently pinned printed clause'
        setattr(PowerFamily,method_name(contract,scenario),exercise)


class PowerFamilyOracleSensitivity(unittest.TestCase):
    def test_changed_expected_number_is_detected_for_every_effect(self):
        for contract in CONTRACTS:
            with self.subTest(effect=contract['key']):
                wrong={**contract,'expectedDelta':contract['expectedDelta']+73}
                with self.assertRaises(AssertionError): PowerFamily().normal(wrong)


if __name__=='__main__': unittest.main()
