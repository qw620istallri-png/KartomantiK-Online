"""Printed oracles for selected Gummo, Wish and Pescojolero choice branches.

Resolution fixtures isolate the selected paragraphs, not every card ability.
Late movements test stale answers; they are not response windows inside effects.
"""
import copy
import unittest
import test_discard_draw_clauses as base


class VesselChoiceClauses(unittest.TestCase):
    world = base.DiscardDrawClauses.world
    cid = staticmethod(base.DiscardDrawClauses.cid)
    field = staticmethod(base.DiscardDrawClauses.field)
    put = staticmethod(base.DiscardDrawClauses.put)
    action = base.DiscardDrawClauses.action
    snapshot = base.DiscardDrawClauses.snapshot
    choose = base.DiscardDrawClauses.choose
    GUMMO = 'Gummo'
    WISH = 'Wish Upon the Stars'
    PESCO = 'Pescojolero, the Ringing King'

    def vessel(self, s, container, cards, owner=None):
        self.put(s, container, 'receptacle', cards)
        s.players[container]['zoneOwners']['receptacle'] = {c: owner or ('p2' if container == 'p1' else 'p1') for c in cards}
        assert all(s.card_owner_in_zone(container, 'receptacle', c) != container for c in cards), 'A positive Vessel fixture must contain foreign-owned cards'

    def pick(self, purpose, cards=('m3', 'm3', 'm4')):
        s = self.world()
        s.card_points.update(m2=10, m3=20, m4=30)
        if purpose == 'gummo':
            host = self.field(s, self.cid(self.GUMMO), 'gummo', zone='interzone', power_bonus=2)
            self.vessel(s, 'p1', cards)
            s.apply_rules_action_result(self.action(self.GUMMO, host))
        elif purpose == 'wish':
            self.vessel(s, 'p1', ['m2'])
            self.vessel(s, 'p2', cards)
            s.apply_rules_action_result(self.action(self.WISH, targets=[{
                'kind': 'zone_card', 'zone': 'receptacle', 'containerId': 'p1', 'cardId': 'm2', 'ownerId': 'p2'}]))
        else:
            host = self.field(s, self.cid(self.PESCO), 'pesco', zone='interzone')
            gift = self.field(s, 'm4', 'gift', zone='stalemate')
            self.vessel(s, 'p2', cards)
            s.apply_rules_action_result(self.action(self.PESCO, host, [self.target(gift)]))
        return s

    target = staticmethod(base.base.AtavicEndClauses.target)

    def roundtrip(self, s, container, card):
        owner = s.take_zone_card(container, 'receptacle', card)
        s.put_zone_card(owner, 'hand', card, owner)
        s.take_zone_card(owner, 'hand', card)
        s.put_zone_card(container, 'receptacle', card, owner)

    def test_gummo_copies_base_and_effects_once_preserving_own_effects_and_bonus(self):
        s = self.pick('gummo', ['m3'])
        s.card_rules['m3']['passiveEffects'] = [{'kind': 'adamant'}]
        self.choose(s, option='0')
        host = s.find_battlefield_item('gummo')
        self.assertEqual(s.rules_manifestation_base_power(host), 3)
        self.assertEqual(s.rules_manifestation_characteristics(host)['power'], 5)
        self.assertIn({'kind': 'adamant'}, s.rules_item_card_rules(host)['passiveEffects'])
        self.assertTrue(s.rules_item_card_rules(host)['triggeredAbilities'])
        s.take_zone_card('p1', 'receptacle', 'm3')
        s.prune_rules_ongoing_effects()
        self.assertEqual(s.rules_manifestation_characteristics(host)['power'], 5)

    def test_gummo_decline_empty_or_source_departure_has_no_choice(self):
        for case in ('decline', 'empty', 'departed'):
            with self.subTest(case=case):
                s = self.world()
                host = self.field(s, self.cid(self.GUMMO), 'gummo', zone='interzone')
                self.vessel(s, 'p1', [] if case == 'empty' else ['m3'])
                action = self.action(self.GUMMO, host)
                if case == 'decline': action['optionalAccepted'] = False
                if case == 'departed': s.battlefield.remove(host)
                s.apply_rules_action_result(action)
                self.assertIsNone(s.rules_engine['pendingChoice'])
                self.assertNotIn('gummoCopy', host)

    def test_gummo_only_offers_the_end_trigger_from_interzone(self):
        for zone in ('interzone', 'confrontation', 'stalemate'):
            with self.subTest(zone=zone):
                s = self.world()
                host = self.field(s, self.cid(self.GUMMO), 'gummo', zone=zone)
                self.vessel(s, 'p1', ['m3'])
                queued = s.queue_rules_triggers(self.cid(self.GUMMO), 'p1', 'end_of_turn',
                    item_id=host['id'], face_up=True, zone=zone, controller_id='p1', defer=True)
                self.assertEqual(bool(queued), zone == 'interzone')

    def test_gummo_departure_during_choice_cannot_copy_a_new_instance(self):
        s = self.pick('gummo')
        old = s.find_battlefield_item('gummo')
        s.battlefield.remove(old)
        new = self.field(s, self.cid(self.GUMMO), 'new-gummo', zone='interzone')
        result = self.choose(s, option='0')
        self.assertEqual(result['status'], 'target_missing')
        self.assertNotIn('gummoCopy', new)

    def test_indices_and_wrong_actor_are_rejected_atomically(self):
        for purpose in ('gummo', 'wish', 'pescojolero'):
            for option in (True, False, 0.5, -1, '99', {}, None):
                with self.subTest(purpose=purpose, option=option):
                    s = self.pick(purpose)
                    choice = s.rules_engine['pendingChoice']
                    before = self.snapshot(s)
                    self.assertIsNotNone(s.resolve_rules_choice(choice['playerId'], choice['id'], option=option)[0])
                    self.assertEqual(self.snapshot(s), before)
            s = self.pick(purpose)
            choice = s.rules_engine['pendingChoice']
            before = self.snapshot(s)
            wrong = 'p2' if choice['playerId'] == 'p1' else 'p1'
            self.assertIsNotNone(s.resolve_rules_choice(wrong, choice['id'], option='0')[0])
            self.assertEqual(self.snapshot(s), before)

    def test_returned_vessel_card_is_not_an_old_selection(self):
        for purpose in ('gummo', 'wish', 'pescojolero'):
            with self.subTest(purpose=purpose):
                s = self.pick(purpose, ['m3'])
                choice = s.rules_engine['pendingChoice']
                self.roundtrip(s, choice['targetPlayerId'], 'm3')
                before = self.snapshot(s)
                self.assertIsNotNone(s.resolve_rules_choice(choice['playerId'], choice['id'], option=str(choice['cardIds'].index('m3')))[0])
                self.assertEqual(self.snapshot(s), before)

    def test_surviving_identical_vessel_copy_remains_selectable(self):
        for purpose in ('gummo', 'wish', 'pescojolero'):
            with self.subTest(purpose=purpose):
                s = self.pick(purpose)
                choice = s.rules_engine['pendingChoice']
                # The first identical occurrence leaves; the second survives.
                s.take_zone_card(choice['targetPlayerId'], 'receptacle', 'm3')
                selected = choice['cardIds'].index('m3') + 1
                self.assertEqual(choice['cardIds'][selected], 'm3')
                self.choose(s, option=str(selected))

    def test_selected_second_duplicate_moves_that_occurrence_only(self):
        for purpose in ('wish', 'pescojolero'):
            with self.subTest(purpose=purpose):
                s = self.pick(purpose)
                choice = s.rules_engine['pendingChoice']
                candidates = [i for i, cid in enumerate(choice['cardIds']) if cid == 'm3']
                first, second = [choice['_vesselCards'][i] for i in candidates]
                self.choose(s, option=str(candidates[1]))
                self.assertTrue(s.rules_vessel_entry_present(choice['targetPlayerId'], first))
                self.assertFalse(s.rules_vessel_entry_present(choice['targetPlayerId'], second))

    def test_vessel_reorder_does_not_create_new_instances(self):
        s = self.pick('gummo')
        choice = s.rules_engine['pendingChoice']
        original = copy.deepcopy(choice['_vesselCards'])
        s.move_zone_card('p1', 'receptacle', 'p1', 'receptacle', 'm4', 'top')
        self.assertTrue(all(s.rules_vessel_entry_present('p1', e) for e in original))
        self.choose(s, option='1')
        self.assertEqual(s.find_battlefield_item('gummo')['gummoCopy'], 'm3')

    def test_removed_duplicate_cannot_select_the_remaining_copy(self):
        for purpose in ('gummo', 'wish', 'pescojolero'):
            with self.subTest(purpose=purpose):
                s = self.pick(purpose)
                choice = s.rules_engine['pendingChoice']
                s.take_zone_card(choice['targetPlayerId'], 'receptacle', 'm3')
                before = self.snapshot(s)
                index = choice['cardIds'].index('m3')
                self.assertIsNotNone(s.resolve_rules_choice(choice['playerId'], choice['id'], option=str(index))[0])
                self.assertEqual(self.snapshot(s), before)

    def test_successful_answer_cannot_be_replayed(self):
        for purpose in ('gummo', 'wish', 'pescojolero'):
            with self.subTest(purpose=purpose):
                s = self.pick(purpose)
                choice = copy.deepcopy(s.rules_engine['pendingChoice'])
                self.choose(s, option='0')
                before = self.snapshot(s)
                self.assertIsNotNone(s.resolve_rules_choice(choice['playerId'], choice['id'], option='0')[0])
                self.assertEqual(self.snapshot(s), before)

    def test_wish_owner_chooses_equal_or_greater_points_and_returns_to_owners(self):
        s = self.pick('wish', ['m3', 'm4', 'w2'])
        choice = s.rules_engine['pendingChoice']
        self.assertEqual((choice['playerId'], choice['cardIds']), ('p2', ['m3', 'm4']))
        self.put(s, 'p1', 'deck', ['w2'])
        self.put(s, 'p2', 'deck', ['m4'])
        self.choose(s, option='0')
        self.assertEqual(s.players['p1']['zones']['deck'], ['m3', 'w2'])
        self.assertEqual(s.players['p2']['zones']['deck'], ['m2', 'm4'])
        self.assertEqual(s.players['p1']['zones']['receptacle'], [])
        self.assertEqual(s.players['p2']['zones']['receptacle'], ['m4', 'w2'])

    def test_wish_no_eligible_answer_moves_neither_card(self):
        s = self.world()
        s.card_points.update(m2=30, m3=20)
        self.vessel(s, 'p1', ['m2'])
        self.vessel(s, 'p2', ['m3'])
        result = s.apply_rules_action_result(self.action(self.WISH, targets=[{'kind':'zone_card', 'zone':'receptacle', 'containerId':'p1', 'cardId':'m2'}]))
        self.assertEqual(result['status'], 'owner_cannot')
        self.assertIsNone(s.rules_engine['pendingChoice'])
        self.assertEqual(s.players['p1']['zones']['receptacle'], ['m2'])
        self.assertEqual(s.players['p2']['zones']['receptacle'], ['m3'])

    def test_wish_accepts_equal_points_and_excludes_lower_or_wrong_owner(self):
        s = self.world()
        s.card_points.update(m2=20, m3=20, m4=10)
        self.vessel(s, 'p1', ['m2'])
        self.vessel(s, 'p2', ['m3', 'm4', 'replay-man'])
        s.card_points['replay-man'] = 50
        s.players['p2']['zoneOwners']['receptacle']['replay-man'] = 'p2'
        s.apply_rules_action_result(self.action(self.WISH, targets=[{'kind':'zone_card', 'zone':'receptacle', 'containerId':'p1', 'cardId':'m2'}]))
        self.assertEqual(s.rules_engine['pendingChoice']['cardIds'], ['m3'])
        self.choose(s, option='0')
        self.assertEqual(s.players['p1']['zones']['deck'], ['m3'])

    def test_wish_initial_card_roundtrip_cannot_exchange_a_new_entry(self):
        s = self.pick('wish', ['m3'])
        self.roundtrip(s, 'p1', 'm2')
        self.choose(s, option='0')
        self.assertEqual(s.players['p1']['zones']['receptacle'], ['m2'])
        self.assertEqual(s.players['p2']['zones']['receptacle'], ['m3'])
        self.assertEqual(s.players['p1']['zones']['deck'], [])

    def test_wish_deck_suspension_replaces_both_returns(self):
        s = self.pick('wish', ['m3'])
        self.field(s, 'inner-deserts-134', 'bob', power_bonus=2)
        self.choose(s, option='0')
        self.assertEqual(s.players['p1']['zones']['deck'], [])
        self.assertEqual(s.players['p2']['zones']['deck'], [])
        self.assertCountEqual([c['cardId'] for c in s.rules_engine['suspendedCards']], ['m2', 'm3'])

    def test_wish_records_both_departures_for_observers(self):
        s = self.pick('wish', ['m3'])
        s.rules_engine['observedEvents'] = []
        self.choose(s, option='0')
        self.assertCountEqual([e['cardId'] for e in s.rules_engine['observedEvents'] if e['kind'] == 'manifestation_left_by_effect'], ['m2', 'm3'])

    def test_pesco_gifts_first_and_takes_without_chaining_or_paying(self):
        s = self.pick('pescojolero', ['m3', 'm4', 'w2'])
        choice = s.rules_engine['pendingChoice']
        self.assertIsNone(s.find_battlefield_item('gift'))
        self.assertIn('m4', s.players['p2']['zones']['receptacle'])
        self.assertNotIn('w2', choice['cardIds'])
        self.choose(s, option=str(choice['cardIds'].index('m3')))
        placed = next(i for i in s.battlefield if i['cardId'] == 'm3')
        self.assertEqual((placed['ownerId'], placed['controllerId'], s.rules_field_zone(placed)), ('p1', 'p1', 'interzone'))
        self.assertFalse(placed.get('isChained'))

    def test_pesco_source_departure_does_not_cancel_placing_the_card(self):
        s = self.pick('pescojolero', ['m3'])
        s.battlefield.remove(s.find_battlefield_item('pesco'))
        self.choose(s, option=str(s.rules_engine['pendingChoice']['cardIds'].index('m3')))
        self.assertTrue(any(i['cardId'] == 'm3' and s.rules_field_zone(i) == 'interzone' for i in s.battlefield))

    def test_pesco_counts_only_gifts_actually_transferred_and_sums_their_points(self):
        for lost in (False, True):
            with self.subTest(lost=lost):
                s = self.world()
                s.card_points.update(m2=10, m3=20, m4=30)
                host = self.field(s, self.cid(self.PESCO), 'pesco', zone='interzone')
                gifts = [self.field(s, cid, cid, zone='stalemate') for cid in ('m2', 'm3')]
                action = self.action(self.PESCO, host, [self.target(i) for i in gifts])
                self.vessel(s, 'p2', ['m4'])
                if lost: s.battlefield.remove(gifts[0])
                s.apply_rules_action_result(action)
                candidates = s.rules_engine['pendingChoice']['cardIds']
                self.assertEqual('m4' in candidates, not lost)
                self.assertEqual('m2' in s.players['p2']['zones']['receptacle'], not lost)

    def test_gummo_control_change_keeps_the_resolving_effects_controller(self):
        s = self.pick('gummo', ['m3'])
        host = s.find_battlefield_item('gummo')
        host['controllerId'] = 'p2'
        self.choose(s, option='0')
        self.assertEqual((host['controllerId'], host['gummoCopy']), ('p2', 'm3'))

    def test_vessel_instance_ids_are_not_sent_to_players_or_spectators(self):
        s = self.pick('wish')
        for viewer in ('p1', 'p2', 'spectator'):
            view = s.serialize_for(viewer, 'spectator' if viewer == 'spectator' else 'player')
            self.assertNotIn('_vesselEntries', str(view))
            self.assertNotIn('_vesselCards', str(view))

    def test_pesco_put_entry_triggers_for_controller_without_playing_or_chaining(self):
        s = self.world()
        seeker = self.cid('Keen-eyed Seeker')
        s.card_points.update(m4=100)
        host = self.field(s, self.cid(self.PESCO), 'pesco', zone='interzone')
        gift = self.field(s, 'm4', 'gift', zone='stalemate')
        self.vessel(s, 'p2', [seeker])
        self.put(s, 'p1', 'deck', ['m2'])
        s.apply_rules_action_result(self.action(self.PESCO, host, [self.target(gift)]))
        choice = s.rules_engine['pendingChoice']
        self.choose(s, option=str(choice['cardIds'].index(seeker)))
        entries = s.rules_engine['actionStack']
        self.assertEqual([(a['ability']['id'], a['controllerId']) for a in entries], [('draw-on-enter-field', 'p1')])
        self.assertEqual(s.players['p1']['zones']['hand'], [])
        s.resolve_rules_top_action()
        self.assertEqual(s.players['p1']['zones']['hand'], ['m2'])
        self.assertEqual(s.players['p2']['zones']['hand'], [])

    def test_pesco_full_interzone_keeps_the_card_in_vessel_and_keeps_the_gifts(self):
        s = self.pick('pescojolero', ['m3'])
        for i in range(2):
            self.field(s, 'm2', 'filler-' + str(i), zone='interzone')
        choice = s.rules_engine['pendingChoice']
        result = self.choose(s, option=str(choice['cardIds'].index('m3')))
        self.assertEqual(result['status'], 'interzone_full')
        self.assertIn('m3', s.players['p2']['zones']['receptacle'])
        self.assertIn('m4', s.players['p2']['zones']['receptacle'])
        self.assertFalse(any(i['cardId'] == 'm3' for i in s.battlefield))

    def test_missing_interzone_source_card_cannot_create_a_phantom(self):
        s = self.world()
        before = self.snapshot(s)
        self.assertIsNone(s.place_rules_card_in_interzone('p1', 'p2', 'receptacle', 'm3'))
        self.assertEqual(self.snapshot(s), before)


if __name__ == '__main__':
    unittest.main()
