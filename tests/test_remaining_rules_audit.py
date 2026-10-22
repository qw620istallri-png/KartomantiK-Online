"""Remaining movement, copy lifetime and wire privacy audit regressions."""
import copy
import json
import unittest

import test_special_payments as special


class RemainingRulesAuditTests(unittest.TestCase):
    case = special.SpecialPaymentTests()

    def timidette(self, second_owner=True):
        session, p1, p2 = self.case.started()
        field = [self.case.field_item('timid', 'p1', 'inner-deserts-041', isSupport=True),
                 self.case.field_item('kept', 'p2', 'm-6', isSupport=True),
                 self.case.field_item('a', 'p1', 'm-3', isSupport=True),
                 self.case.field_item('b', 'p1', 'm-4', isSupport=True)]
        if second_owner:
            field += [self.case.field_item('c', 'p2', 'm-5', isSupport=True),
                      self.case.field_item('d', 'p2', 'm-7', isSupport=True)]
        session.battlefield += field
        action = {'id': 'timid-action', 'controllerId': 'p1',
                  'source': {'cardId': 'inner-deserts-041', 'itemId': 'timid'},
                  'targets': [{'kind': 'card', 'itemId': 'kept'}],
                  'ability': {'result': {'kind': 'timidette_support_to_deck_bottom'}}}
        session.apply_rules_action_result(action)
        return session, p1, p2

    def test_timidette_orders_both_owners_decks_without_gusted_boost(self):
        session, p1, p2 = self.timidette()
        for ids in [['b', 'a'], ['d', 'c']]:
            choice = session.rules_engine['pendingChoice']
            self.assertEqual(choice['playerId'], 'p1')
            self.assertEqual(choice['position'], 'bottom')
            before = copy.deepcopy(session.rules_engine)
            error, _ = session.resolve_rules_choice('p2', choice['id'], ids)
            self.assertIsNotNone(error)
            self.assertEqual(before, session.rules_engine)
            error, _ = session.resolve_rules_choice('p1', choice['id'], ids)
            self.assertIsNone(error)
        self.assertEqual(p1['zones']['deck'][-2:], ['m-4', 'm-3'])
        self.assertEqual(p2['zones']['deck'][-2:], ['m-7', 'm-5'])
        self.assertIsNotNone(session.find_battlefield_item('timid'))
        self.assertIsNotNone(session.find_battlefield_item('kept'))
        self.assertFalse(session.rules_engine['ongoingEffects'])
        self.assertIsNone(session.rules_engine['pendingChoice'])

    def test_support_returns_skip_order_when_no_deck_has_two_real_cards(self):
        session, p1, p2 = self.case.started()
        items = [self.case.field_item('own', 'p1', 'm-3', isSupport=True),
                 self.case.field_item('foreign', 'p2', 'm-4', isSupport=True),
                 session.create_rules_token_copy('m-5', 'p1')]
        session.battlefield += items[:2]
        result = session._continue_rules_support_return_groups(
            [{'controllerId': 'p1', 'itemIds': [i['id'] for i in items]}], {}, {},
            position='bottom', boost_firsts=False)
        self.assertEqual(result['kind'], 'support_returns_completed')
        self.assertIsNone(session.rules_engine['pendingChoice'])
        self.assertEqual(p1['zones']['deck'][-1], 'm-3')
        self.assertEqual(p2['zones']['deck'][-1], 'm-4')
        self.assertNotIn('m-5', p1['zones']['deck'])

    def test_support_return_respects_bob_suspension(self):
        session, p1, _ = self.case.started()
        # BOB's threshold also replaces movements caused by ordered returns.
        bob = next(cid for cid, data in session.card_rules.items() if data.get('suspensionThresholds'))
        session.battlefield += [self.case.field_item('bob', 'p1', bob),
                                self.case.field_item('s', 'p1', 'm-3', isSupport=True)]
        session.rules_engine['ongoingEffects'].append({'id': 'power', 'kind': 'power_modifier',
            'source': {}, 'target': {'itemId': 'bob'}, 'value': 20, 'duration': 'until_end_of_turn',
            'startedTurn': session.phase_tracker['turn']})
        result = session._continue_rules_support_return_groups(
            [{'controllerId': 'p1', 'itemIds': ['s']}], {}, {}, position='bottom', boost_firsts=False)
        self.assertNotIn('m-3', p1['zones']['deck'])
        self.assertEqual(session.rules_engine['suspendedCards'][0]['cardId'], 'm-3')
        self.assertEqual(result['counts'], {})

    def test_a_bob_copy_releases_its_suspended_cards_when_it_leaves(self):
        session, p1, _ = self.case.started()
        bob = next(cid for cid, data in session.card_rules.items() if data.get('suspensionThresholds'))
        token = session.create_rules_token_copy(bob, 'p1')
        self.case.put(p1, 'deck', ['m-3'])
        error, suspended = session.suspend_zone_card('p1', 'deck', 'm-3', source_effect_id=token['id'])
        self.assertIsNone(error)
        movement = session._rules_remove_field_item(token, 'p1', 'graveyard')
        self.assertEqual(session.rules_engine['suspendedCards'], [])
        self.assertIn('m-3', p1['zones']['deck'])
        self.assertEqual(movement['releasedSuspended'][0]['suspensionId'], suspended['id'])
        self.assertNotIn(bob, p1['zones']['graveyard'])

    def test_mimer_remembers_values_at_departure_without_serialization(self):
        for previously_viewed in [False, True]:
            with self.subTest(previously_viewed=previously_viewed):
                session, _, _ = self.case.started()
                source = self.case.field_item('copy', 'p1', 'm-3')
                target = self.case.field_item('target', 'p2', 'm-4')
                session.battlefield += [source, target]
                session.rules_engine['ongoingEffects'] = [{
                    'id': 'link', 'kind': 'copy_power_temperament', 'duration': 'while_source_on_field',
                    'source': {'itemId': 'copy'}, 'target': {'itemId': 'target'}}]
                if previously_viewed:
                    session.rules_manifestation_characteristics(source)
                target['counters']['power'] = 5
                expected = session.rules_manifestation_characteristics(target)
                base = session.rules_manifestation_base_power(target)
                session._rules_remove_field_item(target, 'p2', 'graveyard')
                session.prune_rules_ongoing_effects()
                self.assertEqual(session.rules_manifestation_characteristics(source), expected)
                self.assertEqual(session.rules_manifestation_base_power(source), base)

    def test_temporary_effects_expire_on_their_own_turn_boundary(self):
        session, _, _ = self.case.started()
        turn = session.phase_tracker['turn']
        session.rules_engine['ongoingEffects'] = [{'id': str(i), 'kind': 'power_modifier',
            'duration': duration, 'startedTurn': turn, 'target': {'itemId': 'first-a'}, 'value': 1}
            for i, duration in enumerate(['until_end_of_turn', 'until_end_of_next_turn'])]
        session.prune_rules_ongoing_effects()
        self.assertEqual(len(session.rules_engine['ongoingEffects']), 2)
        session.phase_tracker['turn'] += 1
        session.prune_rules_ongoing_effects()
        self.assertEqual([e['id'] for e in session.rules_engine['ongoingEffects']], ['1'])
        session.phase_tracker['turn'] += 1
        session.prune_rules_ongoing_effects()
        self.assertEqual(session.rules_engine['ongoingEffects'], [])

    def test_copy_counters_and_effects_are_independent_and_do_not_enter_decks(self):
        session, p1, _ = self.case.started()
        original = session.battlefield[0]
        original['counters'] = {'Gem': 4}
        token = session.create_rules_token_copy(original['cardId'], 'p1', effects_disabled=True)
        self.assertEqual(token['counters'], {})
        self.assertEqual(session.queue_rules_token_copy_entry_triggers(token), [])
        token['counters']['Gem'] = 1
        self.assertEqual(original['counters'], {'Gem': 4})
        session._rules_remove_field_item(token, 'p1', 'deck')
        self.assertNotIn(original['cardId'], p1['zones']['deck'])

    def test_memories_survive_limbo_and_hand_but_clear_in_deck_or_exile(self):
        for destination in ['deck', 'exile']:
            with self.subTest(destination=destination):
                session, _, _ = self.case.started()
                item = session.battlefield[0]
                memory = session.create_rules_effect_memory('p1', item['cardId'], 'win_destination_exile')
                session._rules_remove_field_item(item, 'p1', 'graveyard')
                self.assertIn(memory, session.rules_engine['effectMemories'])
                session.move_zone_card('p1', 'graveyard', 'p1', 'hand', item['cardId'])
                self.assertIn(memory, session.rules_engine['effectMemories'])
                session.move_zone_card('p1', 'hand', 'p1', destination, item['cardId'])
                self.assertNotIn(memory, session.rules_engine['effectMemories'])

    def test_returning_real_card_recovers_memory_but_a_token_copy_does_not(self):
        session, p1, _ = self.case.started()
        original = session.battlefield[0]
        cid = original['cardId']
        memory = session.create_rules_effect_memory('p1', cid, 'win_destination_exile',
                                                    data={'itemId': original['id']})
        session._rules_remove_field_item(original, 'p1', 'graveyard')
        token = session.create_rules_token_copy(cid, 'p1')
        session.queue_rules_token_copy_entry_triggers(token)
        self.assertEqual(memory['data']['itemId'], original['id'])
        session.card_rules[cid]['triggeredAbilities'] = []
        error, chained = session.chain_rules_manifestation('p1', 'graveyard', cid)
        self.assertIsNone(error)
        self.assertEqual(memory['data']['itemId'], chained['itemId'])
        self.assertNotEqual(memory['data']['itemId'], token['id'])

    def test_a_copy_leaving_cannot_leave_a_memory_for_the_real_card(self):
        session, _, _ = self.case.started()
        token = session.create_rules_token_copy('m-3', 'p1')
        memory = session.create_rules_effect_memory('p1', 'm-3', 'win_destination_exile',
                                                    data={'itemId': token['id']})
        session._rules_remove_field_item(token, 'p1', 'graveyard')
        self.assertNotIn(memory, session.rules_engine['effectMemories'])


class PrivateResolutionAuditTests(unittest.TestCase):
    case = special.SpecialPaymentTests()

    def started(self):
        session, p1, p2 = self.case.started()
        for item in session.battlefield:
            item.update(x=0, y=0, rotation=0, stackedOn=None)
        return session, p1, p2

    def test_private_results_stay_private_in_state_recent_and_full_logs(self):
        for mode in ['casual', 'tournament']:
            for kind, payload in [
                ('peek_top_card', {'cardId': 'secret-peek'}),
                ('deck_reorder', {'groups': [{'playerId': 'p1', 'top': ['secret-top'], 'bottom': ['secret-bottom']}]}),
                ('search_deck', {'concealed': True, 'cardIds': ['secret-concealed']}),
                ('deck_bottom_from_hand', {'cardIds': ['secret-hand']}),
                ('draw_replacement', {'drawnCardIds': ['secret-draw'], 'discardedCardIds': ['public-discard']}),
            ]:
                with self.subTest(mode=mode, kind=kind):
                    session, _, _ = self.started()
                    session.mode = mode
                    result = {'kind': kind, 'playerId': 'p1', **payload}
                    session.rules_engine['lastResolvedAction'] = {'controllerId': 'p1', 'effectResult': result}
                    session.add_log('p1', 'rules_choice_resolved', result)
                    before = copy.deepcopy((session.rules_engine, session.log))
                    for role, viewer in [('player', 'p2'), ('spectator', None), ('organizer', None)]:
                        wire = json.dumps([session.serialize_for(viewer, role), session.serialize_log(role, viewer)])
                        self.assertNotIn('secret-', wire)
                    for role, viewer in [('player', 'p1'), ('observer', None), ('judge', None)]:
                        self.assertIn('secret-', json.dumps(session.serialize_for(viewer, role)))
                    self.assertEqual(before, (session.rules_engine, session.log))

    def test_public_search_and_reveals_are_preserved(self):
        session, _, _ = self.started()
        session.add_log('p1', 'rules_choice_resolved', {'kind': 'search_deck', 'interzone': True,
                        'playerId': 'p1', 'cardIds': ['public-search']})
        session.rules_engine['pendingChoice'] = {'id': 'reveal', 'kind': 'reveal_hand_discard',
            'playerId': 'p1', 'cardIds': ['public-reveal'], '_private': 'secret-internal'}
        view = json.dumps(session.serialize_for('p2', 'player'))
        self.assertIn('public-search', view)
        self.assertIn('public-reveal', view)
        self.assertNotIn('secret-internal', view)

    def test_private_pending_choices_and_suspension_returns(self):
        session, _, _ = self.started()
        session.rules_engine['pendingChoice'] = {'id': 'scry', 'kind': 'deck_reorder', 'playerId': 'p1',
            'groups': [{'playerId': 'p2', 'cardIds': ['secret-choice']}], '_groups': ['secret-internal']}
        session.rules_engine['lastResolvedAction'] = {'controllerId': 'p1', 'sourceResolution': {
            'releasedSuspended': [{'suspensionId': 's', 'cardId': 'secret-return', 'ownerId': 'p1',
                                   'fromZone': 'deck', 'destination': 'deck'}]}}
        for role, viewer in [('player', 'p2'), ('spectator', None)]:
            self.assertNotIn('secret-', json.dumps(session.serialize_for(viewer, role)))
        self.assertIn('secret-choice', json.dumps(session.serialize_for('p1', 'player')))
