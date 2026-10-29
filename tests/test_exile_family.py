"""Independent exile oracles: exact costs, legal targets and actual-exile rewards.

ETBs use production optional/target choices. Targets are synthetic printed
fixtures; no complete match, artwork or all-interaction certification claimed.
"""
import hashlib
import json
import unittest
from pathlib import Path
from collections import Counter

import main
import test_discard_draw_clauses as base
from session import ADVANCED_PHASES

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = json.loads((ROOT / 'audit/exile-family.json').read_text(encoding='utf-8'))['contracts']
for row in CONTRACTS:
    card = next(c for c in main.CARD_DATA if c['id'] == row['cardId'])
    assert card['effect'] == row['printedText'] and card['name'] == row['name']
    assert hashlib.sha256(card['effect'].encode()).hexdigest() == row['printedTextSha256']


class ExileFamily(unittest.TestCase):
    world = base.DiscardDrawClauses.world
    field = staticmethod(base.DiscardDrawClauses.field)
    put = staticmethod(base.DiscardDrawClauses.put)
    target = staticmethod(base.base.AtavicEndClauses.target)
    snapshot = base.DiscardDrawClauses.snapshot
    choose = base.DiscardDrawClauses.choose

    def setup_case(self, row, count=1):
        s = self.world()
        for i in range(max(count, 4)):
            cid = 'exile-probe-' + str(i)
            s.card_rules[cid] = {'type': 'ephemeral_will' if row['key'] == 'referen' else 'manifestation',
                'power': 3 + i, 'powerCost': '{G}' * (3 + i), 'temperaments': ['phlegmatic']}
            s.card_points[cid] = 20
            if row['key'] != 'referen': s.manifestation_ids.add(cid)
        s.add_rules_excess_essence('p1', [{'temperament': 'hollow', 'amount': 20}])
        host = None
        if row['mode'] == 'play': self.put(s, 'p1', 'hand', [row['cardId']])
        else:
            host = self.field(s, row['cardId'], 'exile-source',
                zone='confrontation' if row['mode'] == 'event' or row['key'] == 'augustus' else 'field')
            if row['key'] == 'everspring': host['counters']['Tear'] = 3
        targets = []
        for i in range(count):
            cid = 'exile-probe-' + str(i)
            if row['targetZone'] == 'battlefield':
                targets.append(self.target(self.field(s, cid, 'victim-' + str(i), owner='p2')))
            else:
                pid = 'p2' if row['key'] == 'everspring' else 'p1'
                s.put_zone_card(pid, row['targetZone'], cid, 'p1' if row['key'] == 'everspring' else pid)
                targets.append({'kind': 'zone_card', 'containerId': pid, 'zone': row['targetZone'], 'cardId': cid})
        return s, host, targets

    def begin(self, s, row, host, targets):
        if row['mode'] == 'event':
            actions = s.queue_rules_triggers(row['cardId'], 'p1', 'enters_field', zone='confrontation',
                item_id=host['id'], face_up=True, controller_id='p1', event_controller_id='p1', defer=True)
            self.assertEqual(len(actions), 1)
            s.queue_rules_simultaneous_actions(actions)
            if s.rules_engine['pendingChoice'] is None:
                return 'No optional trigger with legal candidates.', None
            self.assertEqual(s.rules_engine['pendingChoice']['kind'], 'optional_stack_action')
            self.choose(s, option='accept')
            choice = s.rules_engine['pendingChoice']
            self.assertIsNotNone(choice, 'Targets must be chosen before this targeted ETB enters the Stack')
            self.assertEqual(choice['kind'], 'trigger_targets')
            error, result = s.resolve_rules_choice('p1', choice['id'], targets=targets)
            return error, actions[0]
        return s.declare_rules_action('p1', row['name'], kind='play_card' if row['mode'] == 'play' else 'activated_effect',
            source={'cardId': row['cardId'], 'zone': 'hand' if host is None else 'battlefield',
                **({'itemId': host['id']} if host else {})}, ability_id=row['abilityId'], targets=targets)

    def resolve(self, s, row, host, targets):
        error, action = self.begin(s, row, host, targets)
        self.assertIsNone(error)
        self.assertEqual(len(s.rules_engine['actionStack']), 1)
        for target in targets:
            if target['kind'] == 'zone_card':
                self.assertIn(target['cardId'], s.players[target['containerId']]['zones'][target['zone']])
            else: self.assertIsNotNone(s.find_battlefield_item(target['itemId']))
        s.resolve_rules_top_action()
        return action

    def power(self, s, host): return s.rules_manifestation_characteristics(host)['power']

    def rewards(self, s, row, host, count, summed=3):
        if row['key'] == 'carcass': self.assertEqual(self.power(s, host), 1 + (summed if count else 0))
        if row['key'] == 'referen': self.assertEqual(self.power(s, host), 2 + count)
        if row['key'] == 'augustus':
            tokens = [i for i in s.battlefield if i.get('isTokenCard')]
            self.assertEqual(len(tokens), count)
            for token in tokens:
                self.assertEqual(s.rules_item_controller_id(token), 'p1')
                self.assertTrue(token['isSupport'])
                self.assertEqual(s.rules_manifestation_characteristics(token)['power'], 1)
                self.assertEqual(s.rules_manifestation_characteristics(token)['temperament'], 'choleric')

    def check_normal(self, row):
        s, host, targets = self.setup_case(row)
        self.resolve(s, row, host, targets)
        owner = 'p2' if row['targetZone'] == 'battlefield' else 'p1'
        self.assertEqual(s.players[owner]['zones']['exile'], ['exile-probe-0'])
        self.rewards(s, row, host, 1)
        self.assertIsNone(s.rules_engine['pendingChoice'])

    def check_cost(self, row):
        s, host, targets = self.setup_case(row)
        error, action = self.begin(s, row, host, targets)
        self.assertIsNone(error)
        if row['mode'] == 'play':
            spent = Counter()
            for e in action['cost']['essenceSpent']: spent[e['temperament']] += e['amount']
            self.assertEqual(dict(spent), row['essenceCost'])
        if row['key'] in ('memory', 'augustus'):
            self.assertEqual(host['rotation'] % 180, 90)
            s.rules_engine['priorityPlayerId'] = 'p1'
            self.assertIsNotNone(self.begin(s, row, host, targets)[0])
        if row['key'] == 'everspring': self.assertEqual(host['counters'].get('Tear', 0), 0)

    def check_unfunded(self, row):
        s, host, targets = self.setup_case(row)
        if row['mode'] == 'play': s.tokens = []
        elif row['key'] == 'everspring': host['counters']['Tear'] = 2
        else: host['rotation'] = 90
        before = self.snapshot(s)
        self.assertIsNotNone(self.begin(s, row, host, targets)[0])
        self.assertEqual(self.snapshot(s), before)

    def check_invalid(self, row):
        for how in ('zone', 'type', 'relation'):
            if how == 'type' and row['key'] in ('memory', 'augustus'): continue
            if how == 'relation' and row['key'] in ('exile', 'subjugate', 'memory'): continue
            s, host, targets = self.setup_case(row)
            t = targets[0]
            if how == 'type': s.card_rules[t['cardId']]['type'] = 'manifestation' if row['key'] == 'referen' else 'ephemeral_will'
            elif how == 'zone':
                if t['kind'] == 'card': s.find_battlefield_item(t['itemId'])['fieldZone'] = 'stalemate'
                else:
                    s.take_zone_card(t['containerId'], t['zone'], t['cardId'])
                    s.put_zone_card(t['containerId'], 'hand', t['cardId'], t['containerId'])
                    t['zone'] = 'hand'
            else:
                pid = 'p1' if row['key'] == 'everspring' else 'p2'
                s.take_zone_card(t['containerId'], t['zone'], t['cardId'])
                s.put_zone_card(pid, t['zone'], t['cardId'], pid)
                t.update(containerId=pid, ownerId='p1')  # forged ownership must not bypass canonicalization
            before = self.snapshot(s)
            error, _ = self.begin(s, row, host, targets)
            self.assertIsNotNone(error, how)
            if row['mode'] != 'event': self.assertEqual(self.snapshot(s), before)

    def check_late(self, row):
        s, host, targets = self.setup_case(row)
        self.assertIsNone(self.begin(s, row, host, targets)[0])
        t = targets[0]
        if t['kind'] == 'card': s._rules_remove_field_item(s.find_battlefield_item(t['itemId']), 'p2', 'hand')
        else:
            owner = 'p1' if row['key'] == 'everspring' else t['containerId']
            self.assertIsNone(s.move_zone_card_by_effect(t['containerId'], t['zone'], owner, 'hand', t['cardId'], 'top')[0])
        s.resolve_rules_top_action()
        self.assertFalse(any(t['cardId'] in p['zones']['exile'] for p in s.players.values()))
        self.rewards(s, row, host, 0)

    def check_reentry(self, row):
        s, host, targets = self.setup_case(row)
        self.assertIsNone(self.begin(s, row, host, targets)[0])
        t = targets[0]
        pid, zone, cid = t['containerId'], t['zone'], t['cardId']
        owner = 'p1' if row['key'] == 'everspring' else pid
        self.assertIsNone(s.move_zone_card_by_effect(pid, zone, owner, 'hand', cid, 'top')[0])
        self.assertIsNone(s.move_zone_card_by_effect(owner, 'hand', pid, zone, cid, 'top')[0])
        s.resolve_rules_top_action()
        self.assertIn(cid, s.players[pid]['zones'][zone])
        self.assertNotIn(cid, s.players[pid]['zones']['exile'])
        self.rewards(s, row, host, 0)

    def check_bob(self, row):
        s, host, targets = self.setup_case(row)
        self.field(s, 'inner-deserts-134', 'bob', power_bonus=3)
        self.resolve(s, row, host, targets)
        self.assertTrue(any(e['cardId'] == targets[0]['cardId'] for e in s.rules_engine['suspendedCards']))
        self.assertNotIn(targets[0]['cardId'], s.players['p1']['zones']['exile'])
        self.rewards(s, row, host, 0)

    def check_maximum(self, row):
        count = row['maximumTargets'] or 21
        s, host, targets = self.setup_case(row, count)
        self.resolve(s, row, host, targets)
        self.rewards(s, row, host, count, sum(range(3, 3 + count)))
        self.assertEqual(len([c for p in s.players.values() for c in p['zones']['exile'] if c.startswith('exile-probe-')]), count)

    def check_too_many(self, row):
        s, host, targets = self.setup_case(row, row['maximumTargets'] + 1)
        self.assertIsNotNone(self.begin(s, row, host, targets)[0])

    def check_zero(self, row):
        s, host, _ = self.setup_case(row)
        self.resolve(s, row, host, [])
        self.assertIsNone(s.rules_engine['pendingChoice'], 'Choosing zero must finish rather than reopen a Limbo chooser')
        self.rewards(s, row, host, 0)
        self.assertIn('exile-probe-0', s.players['p2' if row['key'] == 'everspring' else 'p1']['zones'][row['targetZone']])

    def check_partial(self, row):
        s, host, targets = self.setup_case(row, 2)
        self.assertIsNone(self.begin(s, row, host, targets)[0])
        t = targets[0]
        owner = 'p1' if row['key'] == 'everspring' else t['containerId']
        self.assertIsNone(s.move_zone_card_by_effect(t['containerId'], t['zone'], owner, 'hand', t['cardId'], 'top')[0])
        s.resolve_rules_top_action()
        self.rewards(s, row, host, 1, 4)
        owner = 'p1' if row['key'] == 'everspring' else targets[1]['containerId']
        self.assertIn('exile-probe-1', s.players[owner]['zones']['exile'])
        self.assertNotIn('exile-probe-0', s.players[owner]['zones']['exile'])

    def check_source_gone(self, row):
        s, host, targets = self.setup_case(row)
        self.assertIsNone(self.begin(s, row, host, targets)[0])
        s._rules_remove_field_item(host, 'p1', 'hand')
        s.resolve_rules_top_action()
        owner = 'p1' if row['key'] == 'everspring' else targets[0]['containerId']
        self.assertIn('exile-probe-0', s.players[owner]['zones']['exile'])
        self.assertFalse(any(e.get('kind') == 'power_modifier' for e in s.rules_engine['ongoingEffects']))
        if row['key'] == 'augustus': self.rewards(s, row, host, 1)

    def check_decline(self, row):
        s, host, targets = self.setup_case(row)
        actions = s.queue_rules_triggers(row['cardId'], 'p1', 'enters_field', zone='confrontation',
            item_id=host['id'], face_up=True, controller_id='p1', defer=True)
        s.queue_rules_simultaneous_actions(actions)
        self.choose(s, option='decline')
        self.assertEqual(s.rules_engine['actionStack'], [])
        self.assertIsNone(s.rules_engine['pendingChoice'])
        self.assertIn('exile-probe-0', s.players['p1']['zones']['graveyard'])

    def check_other_limbo(self, row):
        s, host, targets = self.setup_case(row)
        cid = targets[0]['cardId']
        s.take_zone_card('p1', 'graveyard', cid)
        s.put_zone_card('p2', 'graveyard', cid, 'p2')
        targets[0]['containerId'] = 'p2'
        self.resolve(s, row, host, targets)
        self.assertIn(cid, s.players['p2']['zones']['exile'])

    def check_protected(self, row):
        s, host, targets = self.setup_case(row)
        self.assertIsNone(self.begin(s, row, host, targets)[0])
        s.rules_engine['ongoingEffects'].append({'id':'protect', 'kind':'protection', 'target':targets[0], 'duration':'until_end_of_turn', 'startedTurn':2})
        s.resolve_rules_top_action()
        self.assertIsNotNone(s.find_battlefield_item(targets[0]['itemId']))

    def check_points_boundary(self, row):
        for points, needed in ((0, 1), (10, 1), (11, 2), (20, 2), (21, 3), (40, 4), (41, 5), (50, 5), (51, None)):
            s, host, targets = self.setup_case(row)
            s.card_points[targets[0]['cardId']] = points
            error, action = self.begin(s, row, host, targets)
            if needed is None: self.assertIsNotNone(error); continue
            self.assertIsNone(error)
            self.assertEqual(sum(e['amount'] for e in action['cost']['essenceSpent']), needed, points)
            s.resolve_rules_top_action()
            self.assertIn(targets[0]['cardId'], s.players['p2']['zones']['exile'])

    def check_total_points(self, row):
        for total in (59, 60, 61):
            s, host, targets = self.setup_case(row, 2)
            s.card_points[targets[1]['cardId']] = total - 20
            before = self.snapshot(s)
            error, _ = self.begin(s, row, host, targets)
            if total > 60:
                self.assertIsNotNone(error)
                self.assertEqual(self.snapshot(s), before)
            else:
                self.assertIsNone(error)
                s.resolve_rules_top_action()
                self.assertCountEqual(s.players['p1']['zones']['exile'], ['exile-probe-0', 'exile-probe-1'])

    def check_foreign_vessel(self, row):
        s, host, targets = self.setup_case(row)
        s.players['p2']['zoneOwners']['receptacle']['exile-probe-0'] = 'p1'
        self.resolve(s, row, host, targets)
        self.assertEqual(s.players['p1']['zones']['exile'], ['exile-probe-0'])
        self.assertEqual(s.players['p2']['zones']['exile'], [])

    def check_sacrifice(self, row):
        s, host, _ = self.setup_case(row)
        s.tokens = []
        error, action = s.declare_rules_action('p1', 'Memory essence', kind='activated_effect',
            source={'cardId':row['cardId'], 'itemId':host['id'], 'zone':'battlefield'},
            ability_id='shattered-memory-sacrifice-for-essence', targets=[])
        self.assertIsNone(error)
        self.assertIsNone(s.find_battlefield_item(host['id']))
        self.assertIn(row['cardId'], s.players['p1']['zones']['exile'])
        self.assertFalse(any(t.get('isEssence') for t in s.tokens))
        s.resolve_rules_top_action()
        self.assertEqual([(t.get('temperament'),t['counters']['essence']) for t in s.tokens if t.get('isEssence')], [('transcendent',1)])

    def check_limbo_either_player(self, row):
        for pid in ('p1','p2'):
            s, host, _ = self.setup_case(row)
            s.put_zone_card(pid, 'graveyard', 'm3', pid)
            targets = [{'kind':'zone_card','containerId':pid,'zone':'graveyard','cardId':'m3'}]
            self.resolve(s, row, host, targets)
            self.assertIn('m3', s.players[pid]['zones']['exile'])

    def check_any_type(self, row):
        s, host, targets = self.setup_case(row, 2 if row['key']=='augustus' else 1)
        s.card_rules[targets[0]['cardId']]['type'] = 'persistent_will'
        if len(targets)>1: s.card_rules[targets[1]['cardId']]['type'] = 'ephemeral_will'
        self.resolve(s, row, host, targets)
        self.assertCountEqual(s.players['p1']['zones']['exile'], [t['cardId'] for t in targets])
        self.rewards(s,row,host,len(targets))

    def check_duration(self, row):
        s, host, targets = self.setup_case(row)
        self.resolve(s,row,host,targets)
        s.phase_tracker['turn'] += 1
        s.prune_rules_ongoing_effects()
        self.assertEqual(self.power(s,host), 4 if row['key']=='carcass' else 2)
        s._rules_remove_field_item(host, 'p1', 'hand')
        replacement = self.field(s,row['cardId'],'new-incarnation')
        self.assertEqual(self.power(s,replacement),1 if row['key']=='carcass' else 2)

    def check_tribute_surplus(self, row):
        for points, surplus in ((20,3),(50,0)):
            s, host, targets = self.setup_case(row)
            s.tokens = []
            s.card_points[targets[0]['cardId']] = points
            s.card_rules['m4']['power'] = 5
            s.card_rules['m4']['powerCost'] = '{G}'*5
            self.put(s,'p1','hand',[row['cardId'],'m4'])
            error, action = s.declare_rules_action('p1','Subjugate tribute',kind='play_card',
                source={'cardId':row['cardId'],'zone':'hand'},ability_id=row['abilityId'],
                payment_card_ids=['m4'], targets=targets)
            self.assertIsNone(error)
            self.assertIn('m4',s.players['p1']['zones']['graveyard'])
            self.assertEqual(sum(e['amount'] for e in action['cost']['excessEssence']),surplus)
            s.resolve_rules_top_action()
            self.assertIn(targets[0]['cardId'],s.players['p2']['zones']['exile'])

    def check_wrong_phase(self,row):
        s,host,targets=self.setup_case(row)
        s.phase_tracker['index']=ADVANCED_PHASES.index('end_triggers')
        before=self.snapshot(s)
        self.assertIsNotNone(self.begin(s,row,host,targets)[0])
        self.assertEqual(self.snapshot(s),before)


def scenarios(row):
    cases = ['normal', 'invalid', 'late', 'cost']
    if row['mode'] != 'event': cases += ['unfunded']
    else: cases += ['decline']
    if row['targetZone'] != 'battlefield': cases += ['reentry']
    else: cases += ['protected']
    if row['targetZone'] == 'graveyard': cases += ['bob']
    if row['minimumTargets'] == 0: cases += ['zero', 'maximum', 'partial']
    if row['maximumTargets'] is not None: cases += ['too_many']
    if row['mode'] != 'play': cases += ['source_gone']
    if row['key'] in ('exile','memory'): cases += ['other_limbo'] if row['key']=='memory' else []
    if row['key'] == 'everspring': cases += ['total_points','foreign_vessel']
    if row['key'] == 'subjugate': cases += ['points_boundary']
    if row['key'] == 'memory': cases += ['sacrifice']
    if row['key'] in ('exile','memory'): cases += ['limbo_either_player']
    if row['key'] in ('memory','augustus'): cases += ['any_type']
    if row['key'] in ('carcass','referen'): cases += ['duration']
    if row['key'] == 'subjugate': cases += ['tribute_surplus']
    if row['key'] == 'augustus': cases += ['wrong_phase']
    return cases

def method_name(row, case): return 'test_' + row['key'] + '__' + case
for row in CONTRACTS:
    for case in scenarios(row):
        def run(self, row=row, case=case): getattr(self,'check_'+case)(row)
        setattr(ExileFamily, method_name(row,case), run)

if __name__ == '__main__': unittest.main()
