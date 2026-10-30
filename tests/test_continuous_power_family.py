"""Printed, literal power oracles for live continuous effects and their scopes.

Initial zones/counts are controlled fixtures, not complete event-producing matches.
"""
import copy
import hashlib
import json
from pathlib import Path
import unittest
import main
import test_bounce_replay_clauses as base
from session import ADVANCED_PHASES

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = json.loads((ROOT/'audit/continuous-power-family.json').read_text(encoding='utf-8'))['contracts']
for row in CONTRACTS:
    card = next(c for c in main.CARD_DATA if c['id'] == row['cardId'])
    assert card['name'] == row['name'] and card['effect'] == row['printedText']
    assert card['power'] == row['sourceBase']
    assert hashlib.sha256(card['effect'].encode()).hexdigest() == row['printedTextSha256']
    assert all(clause in card['effect'] for clause in row['selectedClauses'])


class ContinuousPowerFamily(unittest.TestCase):
    world = base.BounceReplayClauses.world
    field = staticmethod(base.BounceReplayClauses.field)
    put = staticmethod(base.BounceReplayClauses.put)
    target = staticmethod(base.BounceReplayClauses.target)
    action = base.BounceReplayClauses.action
    cid = staticmethod(base.BounceReplayClauses.cid)

    def power(self, s, item): return s.rules_manifestation_characteristics(item)['power']

    def setup_case(self, row):
        s = self.world()
        s.card_rules['aura-probe'] = {'type': 'manifestation', 'power': 5, 'temperaments': ['phlegmatic']}
        s.manifestation_ids.add('aura-probe')
        host = self.field(s, row['cardId'], 'host', zone=row['sourceZone'], support=row['key'] == 'skapus')
        target = host if row['selfTarget'] else self.field(s, 'aura-probe', 'recipient',
            zone='interzone' if row['key'] == 'sangen' else 'confrontation',
            support=row['key'] in ('herbaceous', 'gargullo'))
        key = row['key']
        if key == 'sprawling':
            for n in range(3): self.field(s, 'm2', 'count-' + str(n), owner='p1' if n == 0 else 'p2')
        elif key == 'prospero':
            for n in range(2): self.field(s, 'm2', 'count-' + str(n), zone='interzone')
            self.field(s, 'm2', 'enemy', owner='p2', zone='interzone')
            self.field(s, 'w2', 'will-decoy', zone='interzone')
            s.rules_engine['firstManifestationItemIds'] = {'p1': target['id']}
        elif key == 'gargullo':
            for n in range(2): self.field(s, 'm2', 'count-' + str(n))
            token = self.field(s, 'm2', 'token'); token.update(isTokenCard=True, power=1, temperament='phlegmatic')
            copied = self.field(s, 'm2', 'copy'); copied['isCopy'] = True
        elif key == 'thinker':
            self.put(s, 'p1', 'graveyard', ['w2', 'w2', 'w2', 'pw3', 'pw3'])
        elif key == 'tipson':
            self.put(s, 'p1', 'hand', ['m2', 'w2', 'pw3']); self.put(s, 'p2', 'hand', ['w2'])
        elif key == 'urn':
            self.put(s, 'p1', 'graveyard', ['m2', 'm3', 'm4', 'w2', 'pw3'])
            self.put(s, 'p2', 'graveyard', ['m2'] * 5)
        elif key in ('cimba', 'beak'):
            self.field(s, 'm2', 'stalemate-1', owner='p2', zone='stalemate')
            if key == 'beak': self.field(s, 'm3', 'stalemate-2', zone='stalemate')
            self.field(s, 'w2', 'stalemate-will', zone='stalemate')
        elif key == 'skapus':
            self.field(s, 'm2', 'first')
            self.field(s, 'm3', 'enemy-support', owner='p2', support=True)
        elif key in ('lucerco', 'kazadur'):
            for n in range(3 if key == 'lucerco' else 5): self.field(s, 'm2', 'count-' + str(n), owner='p2')
            self.field(s, 'w2', 'will-decoy', owner='p2')
            self.field(s, 'm3', 'interzone-decoy', owner='p2', zone='interzone')
        elif key == 'vilupera':
            for container, cid, owner in (('p1', 'm2', 'p1'), ('p2', 'm3', 'p1'), ('p2', 'm4', 'p1'),
                    ('p1', 'aura-probe', 'p2'), ('p1', 'w2', 'p1')):
                s.put_zone_card(container, 'receptacle', cid, owner)
        elif key == 'bell':
            self.field(s, 'm3', 'enemy', owner='p2')
            self.field(s, 'w2', 'will-decoy')
        elif key == 'berta': target['counters']['power'] = -2
        elif key == 'tower': s.card_rules['aura-probe']['float'] = True
        elif key == 'sangen': self.field(s, 'm3', 'enemy', owner='p2', zone='interzone')
        elif key == 'kelona': self.put(s, 'p1', 'graveyard', ['m2', 'm3', 'm4', *(['w2'] * 6)])
        return s, host, target

    def check_baseline(self, row):
        s, _, target = self.setup_case(row)
        self.assertEqual(self.power(s, target), row['expectedPower'])

    def check_source_zones(self, row):
        for zone, expected in row['zonePowers'].items():
            with self.subTest(zone=zone):
                s, host, target = self.setup_case(row)
                host['fieldZone'] = zone
                if zone != 'confrontation': host['isSupport'] = False
                self.assertEqual(self.power(s, target), expected)

    def check_inactive(self, row):
        for reason in ('face_down', 'disabled', 'removed'):
            with self.subTest(reason=reason):
                s, host, target = self.setup_case(row)
                if reason == 'face_down': host['faceUp'] = False
                elif reason == 'disabled': host['effectsDisabled'] = True
                else: s.battlefield.remove(host)
                self.assertEqual(self.power(s, target), row['inactivePower'])

    def check_controller(self, row):
        s, host, target = self.setup_case(row)
        host['controllerId'] = 'p2'
        self.assertEqual(self.power(s, target), row['changedControlPower'])
        host['controllerId'] = 'p1'
        self.assertEqual(self.power(s, target), row['expectedPower'])

    def check_no_stack(self, row):
        s, _, target = self.setup_case(row)
        before = copy.deepcopy((s.rules_engine, s.battlefield, s.tokens))
        for _ in range(3): self.assertEqual(self.power(s, target), row['expectedPower'])
        self.assertEqual((s.rules_engine, s.battlefield, s.tokens), before)

    def check_phase_and_turn(self, row):
        s, _, target = self.setup_case(row)
        for phase in ('confrontation_reaction', 'resolution_compare', 'end_actions', 'recovery_start'):
            s.phase_tracker['index'] = ADVANCED_PHASES.index(phase)
            s.phase_tracker['turn'] += 1
            self.assertEqual(self.power(s, target), row['expectedPower'])

    def check_duplicate(self, row):
        s, host, target = self.setup_case(row)
        duplicate = {**host, 'id': 'second-source', 'counters': {}}
        s.battlefield.append(duplicate)
        self.assertEqual(self.power(s, target), row['duplicateSourcePower'])

    def check_cleanse(self, row):
        s, _, target = self.setup_case(row)
        target['counters']['power'] = 2
        s.apply_rules_action_result(self.action('Cleanse', targets=[self.target(target)]))
        self.assertEqual(self.power(s, target), 5 if row['key'] == 'berta' else row['expectedPower'])
        self.assertNotIn('power', target['counters'])

    def check_blank_restore(self, row):
        s, _, target = self.setup_case(row)
        cid = next(cid for cid, rule in s.card_rules.items()
            if any(p.get('kind') == 'disable_other_effects' for p in rule.get('passiveEffects', [])))
        blanker = self.field(s, cid, 'blanker', zone='field')
        self.assertEqual(self.power(s, target), row['inactivePower'])
        s.battlefield.remove(blanker)
        self.assertEqual(self.power(s, target), row['expectedPower'])

    def check_scope(self, row):
        s, host, target = self.setup_case(row)
        if row['selfTarget']:
            other = self.field(s, 'aura-probe', 'other')
            self.assertEqual(self.power(s, other), 5)
            return
        target['controllerId'] = 'p2'
        s.refresh_rules_first_manifestations()
        self.assertEqual(self.power(s, target), 5 if row['key'] == 'berta' else row['inactivePower'])

    def check_live_counts(self, row):
        s, host, target = self.setup_case(row)
        key = row['key']
        if key == 'sprawling':
            s.battlefield.remove(s.find_battlefield_item('count-0'))
            self.assertEqual(self.power(s, target), 1)
            token = s.create_rules_token_copy(None, 'p2', generic_power=1, generic_temperament='hollow', field_zone='confrontation')
            self.assertEqual(self.power(s, target), 2)
            s.battlefield.remove(token)
            self.field(s, 'pw3', 'will-count-decoy')
            self.assertEqual(self.power(s, target), 1)
        elif key == 'prospero':
            next_first = self.field(s, 'aura-probe', 'new-first', support=True)
            s._rules_remove_field_item_by_effect(target, 'p1', 'graveyard', 'top', reason='destroy')
            s.refresh_rules_first_manifestations()
            self.assertEqual(s.rules_engine['firstManifestationItemIds']['p1'], next_first['id'])
            self.assertEqual(self.power(s, next_first), 8)
            s.battlefield.remove(s.find_battlefield_item('count-0'))
            self.assertEqual(self.power(s, next_first), 7)
        elif key == 'herbaceous':
            target['isSupport'] = False; self.assertEqual(self.power(s, target), 5)
            target['isSupport'] = True; self.assertEqual(self.power(s, target), 6)
            token = s.create_rules_token_copy(None, 'p1', generic_power=1, generic_temperament='hollow', field_zone='confrontation')
            self.assertEqual(self.power(s, token), 2)
        elif key == 'gargullo':
            s.battlefield.remove(s.find_battlefield_item('count-0'))
            self.assertEqual(self.power(s, target), 6)
            s.create_rules_token_copy(None, 'p1', generic_power=1, generic_temperament='hollow', field_zone='confrontation')
            self.assertEqual(self.power(s, target), 6)
            s.find_battlefield_item('count-1')['controllerId'] = 'p2'
            self.assertEqual(self.power(s, target), 5)
        elif key == 'monument':
            target['fieldZone'] = 'interzone'; self.assertEqual(self.power(s, target), 5)
            target['fieldZone'] = 'confrontation'; self.assertEqual(self.power(s, target), 6)
            token = s.create_rules_token_copy(None, 'p1', generic_power=1, generic_temperament='hollow', field_zone='confrontation')
            self.assertEqual(self.power(s, token), 2)
        elif key == 'thinker':
            for count, expected in ((0, 1), (4, 1), (5, 3), (6, 3)):
                self.put(s, 'p1', 'graveyard', ['w2'] * count + ['m2', 'm3'])
                self.assertEqual(self.power(s, target), expected)
                host['fieldZone'] = 'interzone'
                self.assertEqual(s.rules_card_can_enter_support(host), count >= 5)
                self.assertEqual(self.power(s, target), 1)
                host['fieldZone'] = 'confrontation'
        elif key == 'tipson':
            for cards, expected in (([], 1), (['m2'], 2), (['w2'] * 7, 8)):
                self.put(s, 'p1', 'hand', cards); self.assertEqual(self.power(s, target), expected)
        elif key == 'urn':
            for count, expected in ((0, 1), (1, 2), (3, 4)):
                self.put(s, 'p1', 'graveyard', ['m2'] * count + ['w2', 'pw3'])
                self.assertEqual(self.power(s, target), expected)
        elif key == 'cimba':
            s.battlefield.remove(s.find_battlefield_item('stalemate-1'))
            self.assertEqual(self.power(s, target), 1)
            token = self.field(s, 'm2', 'new-stalemate', owner='p2', zone='stalemate')
            self.assertEqual(self.power(s, target), 2)
            s.battlefield.remove(token); self.assertEqual(self.power(s, target), 1)
        elif key == 'beak':
            self.field(s, 'm2', 'new-stalemate', owner='p2', zone='stalemate')
            self.assertEqual(self.power(s, target), 7)
            s.battlefield.remove(s.find_battlefield_item('stalemate-1'))
            self.assertEqual(self.power(s, target), 6)
        elif key == 'skapus':
            enemy = s.find_battlefield_item('enemy-support')
            enemy['controllerId'] = 'p1'; self.assertEqual(self.power(s, target), 1)
            enemy['controllerId'] = 'p2'; self.assertEqual(self.power(s, target), 3)
            self.field(s, 'm2', 'interzone-decoy', zone='interzone')
            self.field(s, 'm2', 'stalemate-decoy', zone='stalemate', support=True)
            self.assertEqual(self.power(s, target), 3)
        elif key in ('lucerco', 'kazadur'):
            s.battlefield = [i for i in s.battlefield if not i['id'].startswith('count-')]
            powers = ((0, 3), (1, 4), (4, 7), (7, 10)) if key == 'lucerco' else ((0, 4), (1, 5), (2, 6), (3, 7), (7, 7))
            for count, expected in powers:
                s.battlefield = [i for i in s.battlefield if not i['id'].startswith('count-')]
                for n in range(count): self.field(s, 'm2', 'count-' + str(n), owner='p2')
                self.assertEqual(self.power(s, target), expected)
            if key == 'kazadur':
                target['counters']['power'] = 2; self.assertEqual(self.power(s, target), 9)
        elif key == 'vilupera':
            s.move_zone_card('p1', 'receptacle', 'p1', 'hand', 'm2', 'top')
            self.assertEqual(self.power(s, target), 4)
            s.put_zone_card('p2', 'receptacle', 'w2', 'p1')
            self.assertEqual(self.power(s, target), 4)
        elif key == 'bell':
            token = s.create_rules_token_copy(None, 'p1', generic_power=1, generic_temperament='hollow', field_zone='confrontation')
            self.assertEqual(self.power(s, target), 5)
            s.battlefield.remove(token); self.assertEqual(self.power(s, target), 7)
        elif key == 'berta':
            host['counters']['power'] = -1
            self.assertEqual(self.power(s, host), 2)
            target['counters']['power'] = 2; self.assertEqual(self.power(s, target), 7)
            enemy = self.field(s, 'aura-probe', 'enemy', owner='p2', power_bonus=-2)
            self.assertEqual(self.power(s, enemy), 5)
            enemy['fieldZone'] = 'stalemate'; self.assertEqual(self.power(s, enemy), 3)
        elif key == 'tower':
            s.card_rules['aura-probe']['float'] = False
            for counters, expected in ((0, 5), (1, 6), (2, 6), (0, 5)):
                target['counters']['Abstraction'] = counters
                self.assertEqual(s.rules_item_has_float(target), counters > 0)
                self.assertEqual(self.power(s, target), expected)
            target['controllerId'] = 'p2'; target['counters']['Abstraction'] = 1
            self.assertFalse(s.rules_item_has_float(target)); self.assertEqual(self.power(s, target), 5)
        elif key == 'sangen':
            self.assertEqual(self.power(s, host), 3)
            target['fieldZone'] = 'confrontation'; self.assertEqual(self.power(s, target), 5)
            token = s.create_rules_token_copy(None, 'p1', generic_power=3, generic_temperament='hollow', field_zone='interzone')
            self.assertEqual(self.power(s, token), 2)
        elif key == 'kelona':
            for count, expected in ((0, 7), (1, 6), (5, 2), (6, 1), (9, 1)):
                self.put(s, 'p1', 'graveyard', ['w2'] * count); self.assertEqual(self.power(s, target), expected)
            target['counters']['power'] = 2; self.assertEqual(self.power(s, target), 3)

    def check_stalemate_recipient(self, row):
        s, host, _ = self.setup_case(row)
        # Real Nubilung keeps its Stalemate-specific abilities. External auras
        # requiring the field still must not change its power in this zone.
        target = self.field(s, self.cid('Nubilung, the Elder'), 'nubilung', support=True)
        target['counters']['Abstraction'] = 1
        s.rules_engine['confrontationResult'] = {'turn': 2, 'status': 'effects', 'stalemate': True,
            'winnerId': None, 'loserId': None, 'participantItemIds': [target['id']]}
        s.begin_rules_confrontation_cleanup()
        self.assertEqual(s.rules_field_zone(target), 'stalemate')
        self.assertTrue(target['isSupport'])
        self.assertEqual(self.power(s, target), 1)


SCENARIOS = ('baseline', 'source_zones', 'inactive', 'controller', 'no_stack',
             'phase_and_turn', 'duplicate', 'cleanse', 'blank_restore', 'scope', 'live_counts', 'stalemate_recipient')
def method_name(row, scenario): return 'test_' + row['key'] + '__' + scenario
for row in CONTRACTS:
    for scenario in SCENARIOS:
        def run(self, row=row, scenario=scenario): getattr(self, 'check_' + scenario)(row)
        setattr(ContinuousPowerFamily, method_name(row, scenario), run)
