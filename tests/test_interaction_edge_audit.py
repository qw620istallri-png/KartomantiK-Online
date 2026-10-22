"""Interaction audit: card identity, replacements, source lifetime and payments."""
import copy
import unittest

import test_special_payments as special


class InteractionEdgeAuditTests(unittest.TestCase):
    case = special.SpecialPaymentTests()

    def test_memories_are_isolated_between_owners_with_the_same_card(self):
        session, _, _ = self.case.started()
        first = self.case.field_item('a', 'p1', 'm-3')
        second = self.case.field_item('b', 'p2', 'm-3')
        session.battlefield += [first, second]
        a = session.create_rules_effect_memory('p1', 'm-3', 'win_destination_exile', data={'itemId': 'a'})
        b = session.create_rules_effect_memory('p2', 'm-3', 'win_destination_exile', data={'itemId': 'b'})
        token = session.create_rules_token_copy('m-3', 'p1')
        session.queue_rules_token_copy_entry_triggers(token)
        session._rules_remove_field_item(first, 'p1', 'deck')
        self.assertNotIn(a, session.rules_engine['effectMemories'])
        self.assertIn(b, session.rules_engine['effectMemories'])
        self.assertEqual(b['data']['itemId'], 'b')

    def test_mimer_keeps_an_already_resolved_modifier_when_its_effects_are_disabled(self):
        session, _, _ = self.case.started()
        source = self.case.field_item('mimer', 'p1', 'pwsjhnw4vpvqgkv_en')
        target = session.battlefield[1]
        session.battlefield.append(source)
        session.create_rules_ongoing_effects({'controllerId': 'p1',
            'source': {'itemId': 'mimer', 'cardId': source['cardId']},
            'targets': [{'kind': 'card', 'itemId': target['id']}],
            'ability': session.card_rules[source['cardId']]['activatedAbilities'][0]})
        expected = session.rules_manifestation_characteristics(source)
        source['effectsDisabled'] = True
        session.prune_rules_ongoing_effects()
        self.assertEqual(session.rules_manifestation_characteristics(source), expected)
        self.assertEqual(len(session.rules_engine['ongoingEffects']), 1)

    def test_quasimillenary_manifestation_leaving_field_for_hand_is_exiled(self):
        session, p1, _ = self.case.started()
        item = session.battlefield[0]
        session.rules_engine['limboDrawn'] = {'p1': [item['cardId']]}
        movement = session._rules_remove_field_item_by_effect(item, 'p1', 'hand')
        self.assertNotIn(item['cardId'], p1['zones']['hand'])
        self.assertIn(item['cardId'], p1['zones']['exile'])
        self.assertEqual(movement['zone'], 'exile')

    def test_quasimillenary_can_still_enter_an_opponents_vessel(self):
        session, _, p2 = self.case.started()
        item = session.battlefield[0]
        session.rules_engine['limboDrawn'] = {'p1': [item['cardId']]}
        session._rules_remove_field_item_by_effect(item, 'p2', 'receptacle')
        self.assertIn(item['cardId'], p2['zones']['receptacle'])
        self.assertEqual(session.rules_engine['limboDrawn']['p1'], [])

    def test_limbo_tribute_is_a_cost_and_does_not_partly_pay_then_suspend(self):
        session, p1, _ = self.case.started()
        cid = next(cid for cid, data in session.card_rules.items() if data.get('canPayTributeFromLimbo'))
        self.case.put(p1, 'graveyard', [cid])
        session.battlefield.append(self.case.field_item('bob', 'p2', 'inner-deserts-134', counters={'power': 3}))
        session.add_rules_excess_essence('p1', [{'temperament': 'hollow', 'amount': 1}])
        error, plan = session.rules_action_payment('p1', 'activated_effect', None, ['graveyard|' + cid],
                                                  {'tribute': '{H}{H}'})
        self.assertIsNone(error)
        session.pay_rules_tribute('p1', plan)
        self.assertIn(cid, p1['zones']['exile'])
        self.assertNotIn(cid, p1['zones']['graveyard'])
        self.assertFalse(session.rules_engine['suspendedCards'])

    def test_nullify_redirect_reports_actual_destination_and_no_limbo_entry(self):
        session, p1, _ = self.case.started()
        item = session.battlefield[0]
        session.rules_engine['ongoingEffects'].append({'id': 'nullify', 'kind': 'exile_incoming_manifestations',
            'duration': 'until_end_of_turn', 'startedTurn': session.phase_tracker['turn'],
            'target': {'kind': 'player', 'playerId': 'p1'}, 'source': {}})
        movement = session._rules_remove_field_item_by_effect(item, 'p1', 'graveyard', reason='destroy')
        self.assertIn(item['cardId'], p1['zones']['exile'])
        self.assertEqual(movement['zone'], 'exile')
        self.assertFalse(session.rules_engine['recentLimboEntries'])

    def test_activation_sacrifice_releases_suspensions_and_attached_cards(self):
        session, p1, _ = self.case.started()
        item = session.battlefield[0]
        item['attachedCards'] = [{'cardId': 'm-3', 'ownerId': 'p1'}]
        self.case.put(p1, 'deck', ['m-4'])
        session.suspend_zone_card('p1', 'deck', 'm-4', source_effect_id=item['id'])
        session.pay_rules_activation_cost({'itemId': item['id'], 'controllerId': 'p1'}, {'sacrificeSource': True})
        self.assertIn('m-3', p1['zones']['exile'])
        self.assertIn('m-4', p1['zones']['deck'])
        self.assertFalse(session.rules_engine['suspendedCards'])

    def test_activated_effect_already_on_stack_survives_source_removal(self):
        session, _, _ = self.case.started()
        drill = self.case.field_item('drill', 'p1', 'inner-deserts-131')
        hourglass = self.case.field_item('glass', 'p2', 'lmx5uff1z53fo0g_en', 'field')
        session.battlefield += [drill, hourglass]
        session.add_rules_excess_essence('p1', [{'temperament': 'hollow', 'amount': 2}])
        error, action = session.declare_rules_action('p1', 'Drildrill', kind='activated_effect',
            source={'itemId': 'drill', 'zone': 'battlefield', 'cardId': drill['cardId']},
            ability_id='drildrill-destroys-persistent-will',
            targets=[{'kind': 'card', 'itemId': 'glass', 'cardId': hourglass['cardId']}])
        self.assertIsNone(error)
        session._rules_remove_field_item(drill, 'p1', 'graveyard')
        session.resolve_rules_top_action()
        self.assertIsNone(session.find_battlefield_item('glass'))


    def test_continuous_links_resume_after_temporary_source_blanking(self):
        for cid, expected_kind in [('y6g3tex9ypttk8u_en', 'power_modifier'),
                                   ('7gd19pmexrjlrap_en', 'lose_effects'),
                                   ('8g5pn3mukkuniog_en', 'protection'),
                                   ('vt3extxbwd6gybn_en', 'grant_support'),
                                   ('ymcx9cg62eg0vgm_en', 'control_link')]:
            with self.subTest(cid=cid):
                session, _, _ = self.case.started()
                source = self.case.field_item('link-source', 'p1', cid, 'field' if expected_kind != 'control_link' else 'interzone')
                target = session.battlefield[1]
                session.battlefield.append(source)
                effects = session.create_rules_ongoing_effects({'controllerId': 'p1',
                    'source': {'itemId': source['id'], 'cardId': cid},
                    'targets': [{'kind': 'card', 'itemId': target['id']}],
                    'ability': self.case.ABILITIES[cid][0]})
                effect = effects[0]
                def observed():
                    if expected_kind == 'power_modifier': return session.rules_manifestation_characteristics(target)['power']
                    if expected_kind == 'lose_effects': return session.rules_item_effects_active(target)
                    if expected_kind == 'protection': return session.rules_item_is_protected(target, 'p1')
                    if expected_kind == 'grant_support': return session.rules_card_can_enter_support(target)
                    return session.rules_item_controller_id(target)
                for field_item in session.battlefield:
                    field_item.update(x=0, y=0, rotation=0, stackedOn=None)
                active_value = observed()
                source['effectsDisabled'] = True
                session.prune_rules_ongoing_effects()
                self.assertIn(effect, session.rules_engine['ongoingEffects'])
                self.assertNotEqual(observed(), active_value)
                visible = session.serialize_for('p2', 'player')['rulesEngine']['ongoingEffects']
                self.assertNotIn(effect['id'], [e['id'] for e in visible])
                source.pop('effectsDisabled')
                session.prune_rules_ongoing_effects()
                self.assertEqual(observed(), active_value)
                visible = session.serialize_for('p2', 'player')['rulesEngine']['ongoingEffects']
                self.assertIn(effect['id'], [e['id'] for e in visible])


    def test_limbo_tribute_retains_payment_triggers_without_a_limbo_entry(self):
        session, p1, _ = self.case.started()
        cid = next(cid for cid, data in session.card_rules.items() if data.get('canPayTributeFromLimbo'))
        self.case.put(p1, 'graveyard', [cid])
        session.battlefield.append(self.case.field_item('bob', 'p2', 'inner-deserts-134', counters={'power': 3}))
        error, plan = session.rules_action_payment('p1', 'activated_effect', None,
                                                  ['graveyard|' + cid], {'tribute': '{H}'})
        self.assertIsNone(error)
        paid = session.pay_rules_tribute('p1', plan)
        self.assertEqual(paid['movements'][0]['destination'], 'exile')
        self.assertEqual(paid['movements'][0]['fromZone'], 'graveyard')
        self.assertFalse(session.rules_engine['recentLimboEntries'])

    def test_sacrificed_source_respects_its_exile_replacement(self):
        session, p1, _ = self.case.started()
        source = self.case.field_item('source', 'p1', 'm-3', exileIfLeaves=True)
        session.battlefield.append(source)
        paid = session.pay_rules_activation_cost({'itemId': source['id'], 'controllerId': 'p1'}, {'sacrificeSource': True})
        self.assertIn('m-3', p1['zones']['exile'])
        self.assertNotIn('m-3', p1['zones']['graveyard'])
        self.assertEqual(paid['sacrificedCards'][0]['destination'], 'exile')


    def test_another_bob_suspends_cards_released_towards_the_deck(self):
        session, p1, _ = self.case.started()
        first = self.case.field_item('bob-a', 'p1', 'inner-deserts-134', counters={'power': 3})
        second = self.case.field_item('bob-b', 'p2', 'inner-deserts-134', counters={'power': 3})
        session.battlefield += [first, second]
        self.case.put(p1, 'deck', ['m-3'])
        session.suspend_zone_card('p1', 'deck', 'm-3', source_effect_id=first['id'])
        session._rules_remove_field_item(first, 'p1', 'graveyard')
        self.assertNotIn('m-3', p1['zones']['deck'])
        self.assertEqual(len(session.rules_engine['suspendedCards']), 1)
        self.assertEqual(session.rules_engine['suspendedCards'][0]['sourceEffectId'], second['id'])

    def test_a_suspended_host_does_not_lose_its_attached_cards(self):
        session, p1, _ = self.case.started()
        host = session.battlefield[0]
        host['attachedCards'] = [{'cardId': 'm-3', 'ownerId': 'p1'}]
        session.battlefield.append(self.case.field_item('bob', 'p2', 'inner-deserts-134', counters={'power': 3}))
        movement = session._rules_remove_field_item_by_effect(host, 'p1', 'graveyard', reason='destroy')
        self.assertEqual(movement['status'], 'suspended')
        self.assertIn('m-3', p1['zones']['exile'])
