"""Shared executable scenarios with independently pinned per-card keyword oracles.

Other ETBs and outcome abilities remain on the Stack and are not certified here.
"""
import hashlib
import json
from pathlib import Path
import unittest
import main
from session import ADVANCED_PHASES
import test_bounce_replay_clauses as fixtures

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = json.loads((ROOT/'audit/support-permissions.json').read_text(encoding='utf-8'))['contracts']
for row in CONTRACTS:
    card = next(c for c in main.CARD_DATA if c['id'] == row['cardId'])
    assert card['name'] == row['name'] and card['effect'] == row['printedText']
    assert hashlib.sha256(card['effect'].encode()).hexdigest() == row['printedTextSha256']
    assert all(clause in card['effect'] for clause in row['printedClauses'])


class SupportPermissions(unittest.TestCase):
    world = fixtures.BounceReplayClauses.world
    field = staticmethod(fixtures.BounceReplayClauses.field)
    put = staticmethod(fixtures.BounceReplayClauses.put)
    snapshot = fixtures.BounceReplayClauses.snapshot

    def setup_card(self, row, zone='hand'):
        s = self.world()
        self.field(s, 'm2', 'first-p1')
        self.field(s, 'm3', 'first-p2', owner='p2')
        item = None
        if zone == 'hand': self.put(s, 'p1', 'hand', [row['cardId']])
        else: item = self.field(s, row['cardId'], 'candidate', zone=zone)
        return s, item

    def declaration(self, row, item=None):
        targets = []
        if row['name'] in ('Chitinous Repeller', 'Manymaws', 'Phalanx Tower'):
            targets = [{'kind': 'card', 'itemId': 'first-p1', 'cardId': 'm2'}]
        elif row['name'] in ('Lament, Thought-nullifier', 'Jesterina, the Decadent'):
            targets = [{'kind': 'player', 'playerId': 'p2'}]
        ability = 'enter-under-chosen-control' if row['name'] in ('Bibi, the Confused', 'Chobariki, of the Shiny Muscles') else None
        return {'kind': 'play_card', 'as_support': True, 'targets': targets, 'ability_id': ability,
                'source': {'cardId': row['cardId'], 'zone': 'battlefield' if item else 'hand',
                           **({'itemId': item['id']} if item else {})}}

    def begin(self, s, row, item=None):
        return s.declare_rules_action('p1', row['name'], **self.declaration(row, item))

    def history(self, s):
        return [e for e in s.rules_engine.get('supportEntries', []) if e['cardId'] not in ('m2', 'm3')]

    def check_hand(self, row):
        s, _ = self.setup_card(row)
        error, action = self.begin(s, row)
        self.assertIsNone(error)
        self.assertEqual(action['cost']['tributeRequirements'], {})
        self.assertTrue(action['sourceOnStack'])
        self.assertNotIn(row['cardId'], s.players['p1']['zones']['hand'])
        self.assertFalse(any(i['cardId'] == row['cardId'] for i in s.battlefield))
        self.assertEqual(self.history(s), [])
        s.resolve_rules_top_action()
        item = next(i for i in s.battlefield if i['cardId'] == row['cardId'])
        self.assertEqual((s.rules_field_zone(item), s.rules_item_controller_id(item), item['ownerId']),
                         ('confrontation', 'p1', 'p1'))
        self.assertTrue(item['isSupport'])
        self.assertEqual(len(self.history(s)), 1)
        self.assertEqual(self.history(s)[0]['itemId'], item['id'])

    def check_field_zone(self, row, zone, expected):
        s, item = self.setup_card(row, zone)
        before = self.snapshot(s)
        error, action = self.begin(s, row, item)
        if not expected:
            self.assertIsNotNone(error)
            self.assertEqual(self.snapshot(s), before)
            return
        self.assertIsNone(error)
        self.assertIn(item, s.battlefield)
        self.assertEqual(s.rules_field_zone(item), zone)
        self.assertFalse(item['isSupport'])
        self.assertEqual(item['pendingSupportActionId'], action['id'])
        self.assertFalse(action['sourceOnStack'])
        s.resolve_rules_top_action()
        self.assertEqual(s.rules_field_zone(item), 'confrontation')
        self.assertTrue(item['isSupport'])
        self.assertNotIn('pendingSupportActionId', item)
        self.assertEqual(len(self.history(s)), 1)

    def check_interzone(self, row): self.check_field_zone(row, 'interzone', row['fromInterzone'])
    def check_stalemate(self, row): self.check_field_zone(row, 'stalemate', row['fromStalemate'])

    def check_wrong_phase(self, row):
        for zone in ('hand', 'interzone'):
            s, item = self.setup_card(row, zone)
            s.phase_tracker['index'] = ADVANCED_PHASES.index('end_actions')
            before = self.snapshot(s)
            self.assertIsNotNone(self.begin(s, row, item)[0])
            self.assertEqual(self.snapshot(s), before)

    def check_wrong_priority(self, row):
        for zone in ('hand', 'interzone'):
            s, item = self.setup_card(row, zone)
            s.rules_engine['priorityPlayerId'] = 'p2'
            before = self.snapshot(s)
            self.assertIsNotNone(self.begin(s, row, item)[0])
            self.assertEqual(self.snapshot(s), before)

    def check_opponent(self, row):
        s, item = self.setup_card(row, 'interzone')
        item['controllerId'] = 'p2'
        before = self.snapshot(s)
        self.assertIsNotNone(self.begin(s, row, item)[0])
        self.assertEqual(self.snapshot(s), before)

    def check_disabled(self, row):
        s, item = self.setup_card(row, 'interzone')
        item['effectsDisabled'] = True
        before = self.snapshot(s)
        self.assertIsNotNone(self.begin(s, row, item)[0])
        self.assertEqual(self.snapshot(s), before)

    def check_lock(self, row):
        for zone in ('hand', 'interzone'):
            s, item = self.setup_card(row, zone)
            s.rules_engine['supportLocks'] = [{'turn': 2, 'playerId': 'p1'}]
            before = self.snapshot(s)
            self.assertIsNotNone(self.begin(s, row, item)[0])
            self.assertEqual(self.snapshot(s), before)

    def check_duplicate(self, row):
        s, _ = self.setup_card(row)
        self.assertIsNone(self.begin(s, row)[0])
        s.rules_engine['priorityPlayerId'] = 'p1'
        before = self.snapshot(s)
        self.assertIsNotNone(self.begin(s, row)[0])
        self.assertEqual(self.snapshot(s), before)

    def check_first(self, row):
        s, _ = self.setup_card(row)
        s.battlefield = []
        s.phase_tracker['index'] = ADVANCED_PHASES.index('confrontation_choose')
        s.rules_engine.update(firstManifestationComplete=False, firstManifestationItemIds={})
        item = self.field(s, row['cardId'], 'first')
        before = self.snapshot(s)
        error = s.register_first_manifestation('p1', item)
        self.assertEqual(error is None, row['canBeFirst'])
        if row['canBeFirst']: self.assertEqual(s.rules_engine['firstManifestationItemIds']['p1'], 'first')
        else: self.assertEqual(self.snapshot(s), before)

    def check_controlled(self, row):
        s, item = self.setup_card(row, 'interzone')
        item['ownerId'] = 'p2'
        error, action = self.begin(s, row, item)
        self.assertEqual(error is None, row['fromInterzone'])
        if action:
            s.resolve_rules_top_action()
            self.assertEqual((item['ownerId'], s.rules_item_controller_id(item), item['isSupport']), ('p2', 'p1', True))

    def check_duplicate_field(self, row):
        s, item = self.setup_card(row, 'interzone')
        self.assertIsNone(self.begin(s, row, item)[0])
        s.rules_engine['priorityPlayerId'] = 'p1'
        before = self.snapshot(s)
        self.assertIsNotNone(self.begin(s, row, item)[0])
        self.assertEqual(self.snapshot(s), before)


SCENARIOS = ('hand', 'interzone', 'stalemate', 'wrong_phase', 'wrong_priority',
             'opponent', 'disabled', 'lock', 'duplicate', 'first', 'controlled', 'duplicate_field')

def method_name(row, scenario): return 'test_' + row['key'] + '__' + scenario
def scenarios(row): return [s for s in SCENARIOS if s != 'duplicate_field' or row['fromInterzone']]

for row in CONTRACTS:
    for scenario in scenarios(row):
        def run(self, row=row, scenario=scenario): getattr(self, 'check_' + scenario)(row)
        setattr(SupportPermissions, method_name(row, scenario), run)
