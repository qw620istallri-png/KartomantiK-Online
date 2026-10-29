"""A concealed Will is played, rather than activating its face-down field effects."""
import test_game_state as fixtures
from session import ADVANCED_PHASES
from unittest.mock import patch


class ConcealedPlayPermissions(fixtures.RealCardRulesCase):
    JIGON = 'z6awx4mwwkfrvdd_en'
    STRENGTHEN = 'lo85kdsow36bymu_en'
    ALL = (JIGON, STRENGTHEN)

    def started(self):
        s, p1, p2 = self.make_session()
        s.phase_tracker['index'] = ADVANCED_PHASES.index('confrontation_reaction')
        s.rules_engine.update(readyPlayerIds=['p1', 'p2'], firstManifestationComplete=True, priorityPlayerId='p1')
        return s, p1, p2

    def setup_hidden(self, *, free=False):
        s, p1, p2 = self.started()
        hidden = self.field_item('hidden', 'p1', self.STRENGTHEN, 'field', faceUp=False,
            concealedWill=True, concealedFree=free, jigonItemId='jigon')
        target = self.field_item('target', 'p1', 'm-0')
        s.battlefield = [hidden, target]
        s.add_rules_excess_essence('p1', [{'temperament': 'hollow', 'amount': 10}])
        return s, hidden, target

    def cast(self, s, hidden, target, **extra):
        return s.declare_rules_action('p1', 'Strengthen', kind='play_card',
            source={'cardId': self.STRENGTHEN, 'itemId': hidden['id'], 'zone': 'battlefield'},
            ability_id='strengthen-power-modifier',
            targets=[{'kind': 'card', 'itemId': target['id'], 'cardId': target['cardId']}], **extra)

    def test_paid_concealed_encoded_will_resolves_its_printed_effect(self):
        s, hidden, target = self.setup_hidden()
        error, action = self.cast(s, hidden, target)
        self.assertIsNone(error)
        self.assertEqual(action['cost']['tributeRequirements'], {'hollow': 1})
        self.assertEqual(s.rules_manifestation_characteristics(target)['power'], 1)
        self.assertNotIn(hidden, s.battlefield)
        s.resolve_rules_top_action()
        self.assertEqual(s.rules_manifestation_characteristics(target)['power'], 4)
        self.assertIn(self.STRENGTHEN, s.players['p1']['zones']['graveyard'])

    def test_free_concealed_encoded_will_resolves_without_tribute(self):
        s, hidden, target = self.setup_hidden(free=True)
        s.tokens = []
        error, action = self.cast(s, hidden, target)
        self.assertIsNone(error)
        self.assertEqual(action['cost']['tributeRequirements'], {})
        s.resolve_rules_top_action()
        self.assertEqual(s.rules_manifestation_characteristics(target)['power'], 4)

    def test_concealed_permission_does_not_allow_an_unmarked_face_down_card(self):
        s, hidden, target = self.setup_hidden()
        hidden.pop('concealedWill')
        self.assertIsNotNone(self.cast(s, hidden, target)[0])
        self.assertIn(hidden, s.battlefield)
        self.assertEqual(s.rules_engine['actionStack'], [])

    def test_concealed_permission_preserves_timing_and_target_validation(self):
        for invalid in ('timing', 'target'):
            with self.subTest(invalid=invalid):
                s, hidden, target = self.setup_hidden()
                if invalid == 'timing':
                    s.phase_tracker['index'] = ADVANCED_PHASES.index('recovery_start')
                else:
                    s.battlefield.remove(target)
                self.assertIsNotNone(self.cast(s, hidden, target)[0])
                self.assertIn(hidden, s.battlefield)
                self.assertEqual(s.rules_engine['actionStack'], [])

    def test_blanked_manifestation_still_cannot_activate_its_ability(self):
        s, _, _ = self.setup_hidden()
        source = self.field_item('source', 'p1', 'm-1', effectsDisabled=True)
        s.battlefield.append(source)
        s.card_rules['m-1']['activatedAbilities'] = [{'id': 'probe', 'targets': {'min': 0, 'max': 0},
            'result': {'kind': 'score_owner', 'value': 5}}]
        error, _ = s.declare_rules_action('p1', 'probe', kind='activated_effect',
            source={'cardId': 'm-1', 'itemId': 'source', 'zone': 'battlefield'}, ability_id='probe')
        self.assertIn('lost its effects', error)

    def test_jigon_search_and_loss_make_the_actual_concealed_will_playable(self):
        s, p1, _ = self.started()
        jigon = self.field_item('jigon', 'p1', self.JIGON)
        target = self.field_item('target', 'p1', 'm-0')
        s.battlefield = [jigon, target]
        self.put(p1, 'deck', [self.STRENGTHEN, 'm-1', 'm-2'])
        queued = s.queue_rules_field_zone_entry_triggers(jigon, 'confrontation', defer=True)
        self.assertEqual(len(queued), 1)
        s.rules_engine['actionStack'] = queued
        s.resolve_rules_top_action()
        choice = s.rules_engine['pendingChoice']
        with patch('game.choices.cards.random.shuffle') as shuffle:
            self.assertIsNone(s.resolve_rules_choice('p1', choice['id'], card_ids=[self.STRENGTHEN])[0])
            shuffle.assert_called_once_with(p1['zones']['deck'])
        hidden = next(i for i in s.battlefield if i.get('concealedWill'))
        self.assertFalse(hidden['faceUp'])
        self.assertNotIn(self.STRENGTHEN, p1['zones']['deck'])
        s.rules_engine['confrontationResult'] = {'turn': s.phase_tracker['turn'], 'winnerId': 'p2',
            'loserId': 'p1', 'participantItemIds': ['jigon', 'target']}
        s.rules_engine['actionStack'] = s.queue_rules_confrontation_win_triggers(defer=True)
        self.assertEqual(len(s.rules_engine['actionStack']), 1)
        s.resolve_rules_top_action()
        self.assertTrue(hidden['concealedFree'])
        s.rules_engine['priorityPlayerId'] = 'p1'
        error, action = self.cast(s, hidden, target)
        self.assertIsNone(error)
        self.assertEqual(action['cost']['tributeRequirements'], {})
        s.resolve_rules_top_action()
        self.assertEqual(s.rules_manifestation_characteristics(target)['power'], 4)

    def test_jigon_winning_does_not_make_the_concealed_will_free(self):
        s, hidden, _ = self.setup_hidden()
        s.battlefield.append(self.field_item('jigon', 'p1', self.JIGON))
        s.rules_engine['confrontationResult'] = {'turn': s.phase_tracker['turn'], 'winnerId': 'p1',
            'loserId': 'p2', 'participantItemIds': ['jigon']}
        self.assertEqual(s.queue_rules_confrontation_win_triggers(defer=True), [])
        self.assertFalse(hidden['concealedFree'])

    def test_paid_concealed_will_still_requires_payment(self):
        s, hidden, target = self.setup_hidden()
        s.tokens = []
        error, _ = self.cast(s, hidden, target)
        self.assertIsNotNone(error)
        self.assertNotIn('lost its effects', error)
        self.assertIn(hidden, s.battlefield)
        self.assertEqual(s.rules_engine['actionStack'], [])

    def test_tebebe_encoded_concealed_will_keeps_its_three_hollow_cost(self):
        s, hidden, target = self.setup_hidden()
        hidden['tebebeConcealed'] = True
        error, action = self.cast(s, hidden, target)
        self.assertIsNone(error)
        self.assertEqual(action['cost']['tributeRequirements'], {'hollow': 3})
        s.resolve_rules_top_action()
        self.assertEqual(s.rules_manifestation_characteristics(target)['power'], 4)

    def test_freeing_one_jigon_does_not_free_another_jigons_will(self):
        s, hidden, _ = self.setup_hidden()
        other = {**hidden, 'id': 'other-hidden', 'jigonItemId': 'another-jigon'}
        s.battlefield.append(other)
        s.apply_rules_action_result({'controllerId': 'p1', 'source': {'itemId': 'jigon'},
            'ability': self.ability(self.JIGON, 'jigon-frees-concealed-wills')})
        self.assertTrue(hidden['concealedFree'])
        self.assertFalse(other['concealedFree'])
