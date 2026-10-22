"""Ordering simultaneous replacements follows controller groups and priority."""
import copy
import random
import unittest

import test_special_payments as special


class ReplacementOrderAuditTests(unittest.TestCase):
    case = special.SpecialPaymentTests()

    def setup(self, nullify_controller='p1'):
        session, p1, p2 = self.case.started()
        session.battlefield.append(self.case.field_item('bob', 'p1', 'inner-deserts-134', counters={'power': 3}))
        session.rules_engine['ongoingEffects'].append({'id': 'nullify', 'actionId': 'nullify-action',
            'kind': 'exile_incoming_manifestations', 'duration': 'until_end_of_turn',
            'startedTurn': session.phase_tracker['turn'], 'controllerId': nullify_controller,
            'source': {'cardId': '36l7iw5m5hk1pmr_en'}, 'target': {'kind': 'player', 'playerId': 'p2'}})
        action = {'id': 'move-action', 'kind': 'triggered_effect', 'label': 'Destroy', 'controllerId': 'p1',
            'source': {'cardId': 'test-effect'}, 'targets': [{'kind': 'card', 'itemId': 'first-b', 'cardId': 'm-2'}],
            'ability': {'id': 'destroy', 'result': {'kind': 'move_target', 'zone': 'graveyard', 'reason': 'destroy'}}}
        return session, p1, p2, action

    def order(self, session, first):
        choice = session.rules_engine['pendingChoice']
        effects = sorted(choice['actions'], key=lambda e: e['replacementKind'] == first)
        return choice['id'], [e['actionId'] for e in effects]

    def test_same_controller_chooses_exile_or_suspension_before_any_move(self):
        for first in ['exile', 'suspend']:
            with self.subTest(first=first):
                session, _, p2, action = self.setup()
                before = copy.deepcopy((session.players, session.battlefield, session.tokens))
                rng = random.getstate()
                result = session.apply_rules_action_result(action)
                self.assertEqual(result['choiceKind'], 'replacement_order')
                self.assertEqual(before, (session.players, session.battlefield, session.tokens))
                reserved = random.getstate()
                choice_id, order = self.order(session, first)
                error, _ = session.resolve_rules_choice('p1', choice_id, order)
                self.assertIsNone(error)
                self.assertEqual(random.getstate(), reserved)
                self.assertIsNone(session.rules_engine['pendingChoice'])
                self.assertIsNone(session.find_battlefield_item('first-b'))
                self.assertEqual('m-2' in p2['zones']['exile'], first == 'exile')
                self.assertEqual(bool(session.rules_engine['suspendedCards']), first == 'suspend')

    def test_different_controllers_use_non_priority_group_first(self):
        for priority, expected in [('p1', 'exile'), ('p2', 'suspend')]:
            with self.subTest(priority=priority):
                session, _, p2, action = self.setup('p2')
                session.phase_tracker['index'] = special.ADVANCED_PHASES.index('end_actions')
                session.rules_engine['lastConfrontationWinnerId'] = priority
                session.apply_rules_action_result(action)
                self.assertIsNone(session.rules_engine['pendingChoice'])
                self.assertEqual('m-2' in p2['zones']['exile'], expected == 'exile')
                self.assertEqual(bool(session.rules_engine['suspendedCards']), expected == 'suspend')

    def test_rejected_or_replayed_order_never_changes_the_game(self):
        session, _, _, action = self.setup()
        session.apply_rules_action_result(action)
        choice_id, order = self.order(session, 'exile')
        for player, ids in [('p2', order), ('p1', order[:1]), ('p1', [{}])]:
            before = copy.deepcopy((session.players, session.battlefield, session.rules_engine))
            error, _ = session.resolve_rules_choice(player, choice_id, ids)
            self.assertIsNotNone(error)
            self.assertEqual(before, (session.players, session.battlefield, session.rules_engine))
        self.assertIsNone(session.resolve_rules_choice('p1', choice_id, order)[0])
        after = copy.deepcopy((session.players, session.battlefield, session.rules_engine))
        self.assertIsNotNone(session.resolve_rules_choice('p1', choice_id, order)[0])
        self.assertEqual(after, (session.players, session.battlefield, session.rules_engine))

    def test_a_stack_action_is_resolved_once_after_the_order(self):
        session, _, p2, action = self.setup()
        session.rules_engine['actionStack'] = [action]
        result = session.resolve_rules_top_action()
        self.assertEqual(result['status'], 'choice_required')
        self.assertEqual(session.rules_engine['actionStack'], [action])
        choice_id, order = self.order(session, 'exile')
        error, result = session.resolve_rules_choice('p1', choice_id, order)
        self.assertIsNone(error)
        self.assertEqual(session.rules_engine['actionStack'], [])
        self.assertEqual(result['_resolvedActions'][0]['action']['id'], action['id'])
        self.assertIn('m-2', p2['zones']['exile'])

    def test_a_later_conflict_does_not_apply_earlier_targets(self):
        session, _, _, action = self.setup()
        action['targets'].insert(0, {'kind': 'card', 'itemId': 'first-a', 'cardId': 'm-1'})
        action['ability']['result']['kind'] = 'move_targets'
        before = copy.deepcopy((session.players, session.battlefield, session.tokens))
        session.apply_rules_action_result(action)
        self.assertEqual(before, (session.players, session.battlefield, session.tokens))
        self.assertEqual(session.rules_engine['pendingChoice']['kind'], 'replacement_order')


    def test_quasimillenary_and_bob_have_the_same_order_choice(self):
        session, p1, _, action = self.setup()
        session.rules_engine['ongoingEffects'] = []
        session.rules_engine['limboDrawn'] = {'p1': ['m-1']}
        action['targets'] = [{'kind': 'card', 'itemId': 'first-a', 'cardId': 'm-1'}]
        result = session.apply_rules_action_result(action)
        self.assertEqual(result['choiceKind'], 'replacement_order')
        choice_id, order = self.order(session, 'exile')
        self.assertIsNone(session.resolve_rules_choice('p1', choice_id, order)[0])
        self.assertIn('m-1', p1['zones']['exile'])

    def test_a_card_choice_resumes_after_its_replacement_order(self):
        session, _, p2, _ = self.setup()
        self.case.put(p2, 'graveyard', ['m-3'])
        original = {'id': 'reorder', 'kind': 'deck_reorder', 'playerId': 'p1',
                    '_groups': [{'playerId': 'p2', 'fromZone': 'graveyard', 'cardIds': ['m-3']}]}
        session.rules_engine['pendingChoice'] = original
        error, result = session.resolve_rules_choice('p1', 'reorder', option={
            'groups': [{'playerId': 'p2', 'top': ['m-3'], 'bottom': []}]})
        self.assertIsNone(error)
        self.assertEqual(result['choiceKind'], 'replacement_order')
        self.assertIn('m-3', p2['zones']['graveyard'])
        choice_id, order = self.order(session, 'exile')
        error, result = session.resolve_rules_choice('p1', choice_id, order)
        self.assertIsNone(error)
        self.assertIn('m-3', p2['zones']['exile'])
        self.assertNotIn('m-3', p2['zones']['graveyard'])
        self.assertIsNone(session.rules_engine['pendingChoice'])

    def test_dormant_replacement_orders_do_not_change_other_games_random_draws(self):
        session, _, _, action = self.setup()
        session.apply_rules_action_result(action)
        choice_id, order = self.order(session, 'exile')
        random.random()  # another session may roll while the chooser waits
        other_game_state = random.getstate()
        self.assertIsNone(session.resolve_rules_choice('p1', choice_id, order)[0])
        self.assertEqual(random.getstate(), other_game_state)


    def test_replacement_during_payment_is_chosen_before_any_cost_is_spent(self):
        session, p1, p2, _ = self.setup()
        session.phase_tracker['index'] = special.ADVANCED_PHASES.index('end_actions')
        session.rules_engine['lastConfrontationWinnerId'] = 'p2'
        other = self.case.field_item('bob-other', 'p2', 'inner-deserts-134', counters={'power': 3}, controllerId='p1')
        enabler = next(cid for cid, meta in session.card_rules.items() if any(
            e.get('kind') == 'field_manifestations_as_tribute' for e in meta.get('passiveEffects') or []))
        session.battlefield += [other, self.case.field_item('enabler', 'p1', enabler, 'interzone')]
        self.case.put(p2, 'deck', ['m-3'])
        session.suspend_zone_card('p2', 'deck', 'm-3', source_effect_id='bob')
        self.case.put(p1, 'hand', ['whwfrjzl6flgww9_en'])
        session.add_rules_excess_essence('p1', [{'temperament': 'transcendent', 'amount': 1}])
        before = copy.deepcopy((session.players, session.battlefield, session.tokens))
        error, result = session.declare_rules_action('p1', 'Protect', kind='play_card',
            source={'cardId': 'whwfrjzl6flgww9_en', 'zone': 'hand'},
            ability_id=self.case.ABILITIES['whwfrjzl6flgww9_en'][0]['id'], payment_card_ids=['battlefield|bob'])
        self.assertIsNone(error)
        self.assertEqual(result['choiceKind'], 'replacement_order')
        self.assertEqual(before, (session.players, session.battlefield, session.tokens))
        choice_id, order = self.order(session, 'exile')
        error, result = session.resolve_rules_choice('p1', choice_id, order)
        self.assertIsNone(error)
        self.assertEqual(len(result['_declaredActions']), 1)
        self.assertEqual(len(session.rules_engine['actionStack']), 1)
        self.assertNotIn('whwfrjzl6flgww9_en', p1['zones']['hand'])
        self.assertIn('m-3', p2['zones']['exile'])
