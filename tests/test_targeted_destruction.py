"""Printed destruction contracts, paid declarations and exact secondary outcomes.

Targets and confrontation results are explicit fixtures. Event cases use the
production trigger queue, without claiming a full match produced the event.
"""
import copy
import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path

import main
import test_discard_draw_clauses as base
from session import ADVANCED_PHASES

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = json.loads((ROOT / 'audit/targeted-destruction.json').read_text(encoding='utf-8'))['contracts']
for row in CONTRACTS:
    card = next(c for c in main.CARD_DATA if c['id'] == row['cardId'])
    assert card['name'] == row['name'] and card['effect'] == row['printedText']
    assert hashlib.sha256(card['effect'].encode()).hexdigest() == row['printedTextSha256']
    assert row['abilityId'] in {a['id'] for a in main.CARD_ABILITIES[row['cardId']]}


class TargetedDestruction(unittest.TestCase):
    world = base.DiscardDrawClauses.world
    field = staticmethod(base.DiscardDrawClauses.field)
    put = staticmethod(base.DiscardDrawClauses.put)
    target = staticmethod(base.base.AtavicEndClauses.target)
    snapshot = base.DiscardDrawClauses.snapshot
    choose = base.DiscardDrawClauses.choose

    def setup_case(self, row, count=1, token=False):
        s = self.world()
        s.card_rules['destruction-probe'] = {'type': 'manifestation', 'power': 4,
            'temperaments': ['phlegmatic'], 'powerCost': '{G}{G}{G}{G}'}
        s.manifestation_ids.add('destruction-probe')
        s.card_points['destruction-probe'] = 20
        s.add_rules_excess_essence('p1', [{'temperament': color, 'amount': 30} for color in
            ('hollow', 'choleric', 'capricious', 'phlegmatic', 'vitreous', 'melancholic')])
        host = None
        if row['mode'] == 'event':
            host = self.field(s, row['cardId'], 'destruction-source')
        else:
            self.put(s, 'p1', 'hand', [row['cardId']])
        if row.get('resolutionOnly'):
            s.phase_tracker['index'] = ADVANCED_PHASES.index('resolution_effects')
        owner = 'p1' if row['targetController'] == 'self' else 'p2'
        items = []
        for i in range(count):
            item = (s.create_rules_token_copy(None, owner, generic_power=4,
                generic_temperament='phlegmatic', field_zone='confrontation') if token else
                self.field(s, 'destruction-probe', 'destroy-' + str(i), owner=owner))
            item['isSupport'] = row.get('supportOnly', False)
            items.append(item)
        self.put(s, 'p1', 'deck', ['m2', 'm3', 'm4', 'w2', 'pw3'])
        self.put(s, 'p2', 'deck', ['m2', 'm3', 'm4', 'w2', 'pw3'])
        winner = 'p1' if row.get('outcome') or row.get('event') == 'wins_confrontation' else 'p2'
        s.rules_engine['confrontationResult'] = {'turn': 2, 'winnerId': winner,
            'loserId': 'p2' if winner == 'p1' else 'p1', 'stalemate': False,
            'participantItemIds': [i['id'] for i in items] + ([host['id']] if host else [])}
        return s, host, items

    def begin(self, s, row, host, items):
        targets = [self.target(i) for i in items]
        if row['mode'] == 'play':
            return s.declare_rules_action('p1', row['name'], kind='play_card',
                source={'cardId': row['cardId'], 'zone': 'hand'},
                ability_id=row['abilityId'], targets=targets)
        actions = s.queue_rules_triggers(row['cardId'], 'p1', row['event'],
            zone='confrontation', item_id=host['id'], face_up=host.get('faceUp', True),
            controller_id='p1', event_controller_id='p1', event_targets=targets, defer=True)
        actions = [a for a in actions if a['ability']['id'] == row['abilityId']]
        if not actions:
            return 'No eligible trigger for these targets.', None
        self.assertEqual(len(actions), 1)
        s.queue_rules_simultaneous_actions(actions)
        if (s.rules_engine.get('pendingChoice') or {}).get('kind') == 'optional_stack_action':
            self.choose(s, option='accept')
        return None, actions[0]

    def resolve(self, s, row, host, items):
        error, action = self.begin(s, row, host, items)
        self.assertIsNone(error, row['name'])
        self.assertTrue(s.rules_engine['actionStack'])
        self.assertTrue(all(i in s.battlefield for i in items))
        self.assertEqual(s.players['p1']['score'], 50, 'Score loss waits for resolution')
        s.resolve_rules_top_action()
        return action

    def check_normal(self, row):
        s, host, items = self.setup_case(row)
        self.resolve(s, row, host, items)
        item = items[0]
        self.assertIsNone(s.find_battlefield_item(item['id']))
        self.assertEqual(s.players[item['ownerId']]['zones']['graveyard'].count(item['cardId']), 1)
        self.assertEqual(s.players['p1']['score'], 50 + row['scoreOnSuccess'])
        for pid in ('p1', 'p2'):
            expected = row['drawPerDestroyed'] if pid == item['controllerId'] else 0
            self.assertEqual(len(s.players[pid]['zones']['hand']), expected)
        if row['mode'] == 'play':
            self.assertEqual(s.players['p1']['zones']['graveyard'].count(row['cardId']), 1)
        if row.get('tokenCountOnSuccess'):
            self.assert_tokens(s, row['tokenCountOnSuccess'], item['controllerId'])

    def assert_tokens(self, s, count, controller):
        tokens = [i for i in s.battlefield if i.get('isTokenCard')]
        self.assertEqual(len(tokens), count)
        for token in tokens:
            self.assertEqual(s.rules_item_controller_id(token), controller)
            self.assertTrue(token['isSupport'])
            stats = s.rules_manifestation_characteristics(token)
            self.assertEqual(stats['power'], 1)
            self.assertEqual(stats['temperament'], 'hollow')

    def invalidate(self, s, item, how):
        if how == 'gone': s._rules_remove_field_item(item, item['ownerId'], 'hand')
        elif how == 'stalemate': item['fieldZone'] = 'stalemate'
        elif how in ('protection', 'immune'):
            s.rules_engine['ongoingEffects'].append({'id': 'invalidate', 'kind': how,
                'target': self.target(item), 'duration': 'until_end_of_turn', 'startedTurn': 2})
        elif how == 'will': item.update(cardId='pw3', fieldZone='field')
        elif how == 'not_support': item['isSupport'] = False
        elif how == 'controller': item['controllerId'] = 'p2' if item['controllerId'] == 'p1' else 'p1'

    def check_late(self, row, how):
        s, host, items = self.setup_case(row)
        self.assertIsNone(self.begin(s, row, host, items)[0])
        self.invalidate(s, items[0], how)
        before = [len(s.players[p]['zones']['hand']) for p in ('p1', 'p2')]
        s.resolve_rules_top_action()
        if how != 'gone': self.assertIn(items[0], s.battlefield)
        self.assertEqual([len(s.players[p]['zones']['hand']) for p in ('p1', 'p2')], before)
        self.assertEqual(s.players['p1']['score'], 50)
        if row.get('tokenCountOnSuccess'): self.assert_tokens(s, 0, 'p2')

    def check_invalid_declaration(self, row):
        for how in ['stalemate', 'protection', 'immune'] + ([] if row['key'] == 'knobbly' else ['will']):
            with self.subTest(invalid=how):
                s, host, items = self.setup_case(row)
                self.invalidate(s, items[0], how)
                before = self.snapshot(s)
                self.assertIsNotNone(self.begin(s, row, host, items)[0])
                self.assertEqual(self.snapshot(s), before)

    def check_owner(self, row):
        s, host, items = self.setup_case(row)
        original = items[0]['ownerId']
        owner = 'p2' if original == 'p1' else 'p1'
        items[0]['ownerId'] = owner
        self.resolve(s, row, host, items)
        self.assertIn(items[0]['cardId'], s.players[owner]['zones']['graveyard'])
        self.assertNotIn(items[0]['cardId'], s.players[original]['zones']['graveyard'])
        if row['drawPerDestroyed']:
            self.assertEqual(len(s.players[original]['zones']['hand']), 2)
            self.assertEqual(len(s.players[owner]['zones']['hand']), 0)

    def check_adamant(self, row):
        s, host, items = self.setup_case(row)
        s.card_rules['destruction-probe']['adamant'] = True
        self.resolve(s, row, host, items)
        self.assertNotIn(items[0], s.battlefield, 'Adamant permits destruction')

    def check_cost(self, row):
        s, host, items = self.setup_case(row)
        error, action = self.begin(s, row, host, items)
        self.assertIsNone(error)
        spent = Counter()
        for entry in action['cost']['essenceSpent']: spent[entry['temperament']] += entry['amount']
        self.assertEqual(dict(spent), row['essenceCost'])
        self.assertIn(items[0], s.battlefield)
        self.assertEqual(s.players['p1']['score'], 50)

    def check_unfunded(self, row):
        s, host, items = self.setup_case(row)
        s.tokens = [t for t in s.tokens if not t.get('isEssence')]
        before = self.snapshot(s)
        self.assertIsNotNone(self.begin(s, row, host, items)[0])
        self.assertEqual(self.snapshot(s), before)

    def check_partial(self, row):
        for how in ('gone', 'protection', 'immune', 'stalemate', 'not_support'):
            for index in (0, 1):
                with self.subTest(invalid=how, index=index):
                    s, host, items = self.setup_case(row, count=2)
                    self.assertIsNone(self.begin(s, row, host, items)[0])
                    self.invalidate(s, items[index], how)
                    hand_before = len(s.players['p2']['zones']['hand'])
                    s.resolve_rules_top_action()
                    valid = items[1-index]
                    self.assertNotIn(valid, s.battlefield)
                    self.assertEqual(s.players['p2']['zones']['graveyard'].count(valid['cardId']), 1)
                    if how != 'gone': self.assertIn(items[index], s.battlefield)
                    self.assertEqual(len(s.players['p2']['zones']['hand']) - hand_before, row['drawPerDestroyed'])

    def check_replacement(self, row, kind):
        s, host, items = self.setup_case(row)
        if kind == 'suspend': self.field(s, 'inner-deserts-134', 'bob', power_bonus=3)
        else:
            action = base.DiscardDrawClauses().action('Nullify Reason',
                targets=[{'kind': 'player', 'playerId': items[0]['ownerId']}], ability_id='nullify-reason-exile-incoming')
            s.create_rules_ongoing_effects(action)
        self.resolve(s, row, host, items)
        self.assertNotIn(items[0], s.battlefield)
        self.assertNotIn(items[0]['cardId'], s.players[items[0]['ownerId']]['zones']['graveyard'])
        if kind == 'suspend':
            self.assertTrue(any(e['cardId'] == items[0]['cardId'] for e in s.rules_engine['suspendedCards']))
        else: self.assertIn(items[0]['cardId'], s.players[items[0]['ownerId']]['zones']['exile'])
        self.assertEqual(s.players['p1']['score'], 50 + row['scoreOnSuccess'])
        if row['drawPerDestroyed']:
            self.assertEqual(len(s.players['p2']['zones']['hand']), 0,
                'Replaced destruction does not satisfy destroyed this way')
        if row.get('tokenCountOnSuccess'): self.assert_tokens(s, 0, 'p2')

    def check_zero_or_two(self, row):
        for count in (0, 2):
            s, host, items = self.setup_case(row, count=count)
            self.resolve(s, row, host, items)
            self.assertEqual(len(s.players['p2']['zones']['hand']), 2 * count)
            self.assertEqual(s.players['p2']['zones']['graveyard'].count('destruction-probe'), count)

    def check_two_controllers(self, row):
        s, host, items = self.setup_case(row, count=2)
        items[0]['controllerId'] = 'p1'
        self.resolve(s, row, host, items)
        self.assertEqual(len(s.players['p1']['zones']['hand']), 2)
        self.assertEqual(len(s.players['p2']['zones']['hand']), 2)

    def check_token(self, row):
        s, host, items = self.setup_case(row, token=True)
        self.resolve(s, row, host, items)
        self.assertNotIn(items[0], s.battlefield)
        self.assertEqual(s.players['p2']['zones']['graveyard'], [])
        self.assertEqual(len(s.players['p2']['zones']['hand']), row['drawPerDestroyed'])
        if row.get('tokenCountOnSuccess'): self.assert_tokens(s, 4, 'p2')

    def check_threshold(self, row):
        for points in (0, 19, 20, 21):
            s, host, items = self.setup_case(row)
            s.card_points['destruction-probe'] = points
            error, action = self.begin(s, row, host, items)
            self.assertEqual(error is None, points <= 20)
            if points <= 20:
                if points == 20: s.card_points['destruction-probe'] = 21
                s.resolve_rules_top_action()
                self.assertEqual(items[0] in s.battlefield, points == 20)

    def check_vessel(self, row):
        for container, owner in (('p1', 'p1'), ('p1', 'p2'), ('p2', 'p1'), ('p2', 'p2')):
            s, host, items = self.setup_case(row)
            s.battlefield.remove(items[0])
            s.put_zone_card(container, 'receptacle', 'destruction-probe', owner)
            target = {'kind': 'zone_card', 'zone': 'receptacle', 'containerId': container,
                'ownerId': owner, 'cardId': 'destruction-probe'}
            error, action = s.declare_rules_action('p1', row['name'], kind='play_card',
                source={'cardId': row['cardId'], 'zone': 'hand'}, ability_id=row['abilityId'], targets=[target])
            self.assertIsNone(error)
            s.resolve_rules_top_action()
            self.assertEqual(s.players[container]['zones']['receptacle'], [])
            self.assertIn('destruction-probe', s.players[owner]['zones']['graveyard'])

    def check_phase_and_outcome(self, row):
        for bad in ('phase', 'outcome', 'nonparticipant', 'controller'):
            s, host, items = self.setup_case(row)
            if bad == 'phase': s.phase_tracker['index'] = ADVANCED_PHASES.index('confrontation_reaction')
            elif bad == 'outcome': s.rules_engine['confrontationResult']['winnerId'], s.rules_engine['confrontationResult']['loserId'] = 'p2', 'p1'
            elif bad == 'nonparticipant': s.rules_engine['confrontationResult']['participantItemIds'] = []
            else: items[0]['controllerId'] = 'p2' if items[0]['controllerId'] == 'p1' else 'p1'
            before = self.snapshot(s)
            self.assertIsNotNone(self.begin(s, row, host, items)[0], bad)
            self.assertEqual(self.snapshot(s), before)

    def check_source_departure(self, row):
        s, host, items = self.setup_case(row)
        self.assertIsNone(self.begin(s, row, host, items)[0])
        s._rules_remove_field_item(host, 'p1', 'hand')
        s.resolve_rules_top_action()
        self.assertNotIn(items[0], s.battlefield)

    def check_wrong_event(self, row):
        s, host, items = self.setup_case(row)
        other = 'loses_confrontation' if row['event'] == 'wins_confrontation' else 'wins_confrontation'
        actions = s.queue_rules_triggers(row['cardId'], 'p1', other, zone='confrontation',
            item_id=host['id'], face_up=True, controller_id='p1', event_targets=[self.target(items[0])], defer=True)
        self.assertEqual([a for a in actions if a['ability']['id'] == row['abilityId']], [])

    def check_mixed_replacement(self, row):
        s, host, items = self.setup_case(row, count=2)
        items[0].update(ownerId='p1', controllerId='p1')
        s.create_rules_ongoing_effects(base.DiscardDrawClauses().action('Nullify Reason',
            targets=[{'kind': 'player', 'playerId': 'p1'}], ability_id='nullify-reason-exile-incoming'))
        self.resolve(s, row, host, items)
        self.assertEqual(s.players['p1']['zones']['exile'].count('destruction-probe'), 1)
        self.assertEqual(s.players['p2']['zones']['graveyard'], ['destruction-probe'])
        self.assertEqual(len(s.players['p1']['zones']['hand']), 0)
        self.assertEqual(len(s.players['p2']['zones']['hand']), 2)

    def check_exile_memory(self, row):
        s, host, items = self.setup_case(row)
        items[0]['exileIfLeaves'] = True
        self.resolve(s, row, host, items)
        self.assertEqual(s.players['p2']['zones']['exile'], ['destruction-probe'])
        self.assertEqual(s.players['p2']['zones']['hand'], [])

    def check_second_target_payment(self, row):
        for count, amount in ((1, 2), (2, 5)):
            s, host, items = self.setup_case(row, count=count)
            s.tokens = []
            s.add_rules_excess_essence('p1', [{'temperament': 'hollow', 'amount': amount}])
            error, action = self.begin(s, row, host, items)
            self.assertIsNone(error)
            self.assertEqual(sum(e['amount'] for e in action['cost']['essenceSpent']), amount)
            self.assertTrue(all(i in s.battlefield for i in items))
        s, host, items = self.setup_case(row, count=2)
        s.tokens = []
        s.add_rules_excess_essence('p1', [{'temperament': 'hollow', 'amount': 4}])
        before = self.snapshot(s)
        self.assertIsNotNone(self.begin(s, row, host, items)[0])
        self.assertEqual(self.snapshot(s), before)

    def check_wills(self, row):
        for cid in ('pw3', 'w2'):
            s, host, items = self.setup_case(row)
            items[0].update(cardId=cid, fieldZone='field')
            self.resolve(s, row, host, items)
            self.assertEqual(s.players['p2']['zones']['graveyard'], [cid])

    def check_decline(self, row):
        s, host, items = self.setup_case(row)
        actions = s.queue_rules_triggers(row['cardId'], 'p1', row['event'], zone='confrontation',
            item_id=host['id'], face_up=True, controller_id='p1',
            event_targets=[self.target(items[0])], defer=True)
        s.queue_rules_simultaneous_actions(actions)
        self.assertEqual(s.rules_engine['pendingChoice']['kind'], 'optional_stack_action')
        self.choose(s, option='decline')
        self.assertIn(items[0], s.battlefield)
        self.assertEqual(s.rules_engine['actionStack'], [])

    def check_base_not_bonus(self, row):
        s, host, items = self.setup_case(row)
        items[0]['counters']['power'] = 3
        items[0]['controllerId'] = 'p1'
        self.resolve(s, row, host, items)
        self.assert_tokens(s, 4, 'p1')

    def check_self_target(self, row):
        s, host, _ = self.setup_case(row, count=0)
        self.resolve(s, row, host, [host])
        self.assert_tokens(s, 2, 'p1')


def scenarios(row):
    cases = ['normal', 'owner', 'adamant', 'invalid_declaration', 'late_gone', 'late_protection', 'late_immune', 'late_stalemate']
    if row['mode'] == 'play': cases += ['cost', 'unfunded']
    else: cases += ['source_departure', 'wrong_event']
    if row['key'] != 'knobbly': cases += ['late_will']
    if row.get('supportOnly'): cases += ['partial', 'late_not_support']
    if row['targetController'] in ('self', 'opponent'): cases += ['late_controller']
    if row.get('resolutionOnly'): cases += ['phase_and_outcome']
    cases += ['replacement_suspend', 'replacement_exile']
    if row['key'] == 'convert': cases += ['zero_or_two', 'two_controllers', 'token', 'mixed_replacement', 'exile_memory']
    if row['key'] == 'disfigure': cases += ['threshold', 'vessel']
    if row['key'] == 'multicastigate': cases += ['second_target_payment']
    if row['key'] == 'knobbly': cases += ['wills', 'decline']
    if row['key'] == 'lilitha': cases += ['base_not_bonus', 'self_target', 'token', 'decline']
    return cases


def method_name(row, case): return 'test_' + row['key'] + '__' + case
for row in CONTRACTS:
    for case in scenarios(row):
        def run(self, row=row, case=case):
            if case.startswith('late_'): return self.check_late(row, case[5:])
            if case.startswith('replacement_'): return self.check_replacement(row, case[12:])
            return getattr(self, 'check_' + case)(row)
        setattr(TargetedDestruction, method_name(row, case), run)


if __name__ == '__main__': unittest.main()
