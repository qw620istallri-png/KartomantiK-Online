"""Printed oracles: Bloatuba / Expansive Ponderer after Chain.

Synthetic printed-power targets isolate these paragraphs; all actual effect
definitions are shipped. Late Deck mutations are stale-answer stimuli only.
"""
import copy
import unittest
import test_discard_draw_clauses as base


class DeckSequenceClauses(unittest.TestCase):
    world = base.DiscardDrawClauses.world
    cid = staticmethod(base.DiscardDrawClauses.cid)
    field = staticmethod(base.DiscardDrawClauses.field)
    put = staticmethod(base.DiscardDrawClauses.put)
    action = base.DiscardDrawClauses.action
    snapshot = base.DiscardDrawClauses.snapshot
    choose = base.DiscardDrawClauses.choose
    BLOAT = 'Bloatuba'
    PONDER = 'Expansive Ponderer'

    def start(self, name, deck=('m2', 'w2', 'm2', 'm4'), chain=True):
        s = self.world()
        victim = 'p2' if name == self.BLOAT else 'p1'
        self.put(s, victim, 'deck', deck)
        self.put(s, 'p1', 'hand', ['m3'])
        host = self.field(s, self.cid(name), 'host', power_bonus=8)
        s.queue_rules_battlefield_entry_triggers(self.cid(name), 'p1', host['id'], True)
        s.resolve_rules_top_action()
        self.assertEqual(s.rules_engine['pendingChoice']['kind'], 'chain_manifestation')
        if chain:
            result = self.choose(s, card_ids=['m3'])
            return s, result
        return s, host

    def order(self, s, top=(), bottom=(), extra=None):
        choice = s.rules_engine['pendingChoice']
        group = choice['_groups'][0]
        option = {'groups': [{'playerId': group['playerId'], 'top': list(top), 'bottom': list(bottom),
                             **({'extra': list(extra)} if extra is not None else {})}]}
        return self.choose(s, option=option)

    def reject(self, s, **kwargs):
        choice = s.rules_engine['pendingChoice']
        before = self.snapshot(s)
        error, payload = s.resolve_rules_choice(choice['playerId'], choice['id'], **kwargs)
        self.assertIsNotNone(error)
        self.assertIsNone(payload)
        self.assertEqual(self.snapshot(s), before)

    def test_bloatuba_reveals_chained_base_power_then_opponent_picks_and_controller_orders(self):
        s, result = self.start(self.BLOAT, ['w2', 'm2', 'm4', 'pw3'])
        self.assertEqual(result['afterChain']['cardIds'], ['w2', 'm2', 'm4'])
        pick = s.rules_engine['pendingChoice']
        self.assertEqual((pick['playerId'], pick['cardIds']), ('p2', ['m2', 'm4']))
        self.choose(s, option='1')
        impasse = [i for i in s.battlefield if s.rules_field_zone(i) == 'stalemate']
        self.assertEqual([(i['cardId'], i['ownerId'], i['controllerId']) for i in impasse], [('m4', 'p2', 'p2')])
        self.assertEqual(s.rules_engine['pendingChoice']['playerId'], 'p1')
        self.order(s, bottom=['m2', 'w2'])
        self.assertEqual(s.players['p2']['zones']['deck'], ['pw3', 'm2', 'w2'])

    def test_bloatuba_second_identical_pick_removes_only_that_revealed_position(self):
        s, _ = self.start(self.BLOAT)
        result = self.choose(s, option='1')
        self.assertEqual(result['remaining'], ['m2', 'w2'])
        self.assertEqual(s.players['p2']['zones']['deck'], ['m2', 'w2', 'm4'])
        self.assertEqual(s.rules_engine['pendingChoice']['groups'][0]['cardIds'], ['m2', 'w2'])
        self.order(s, bottom=['w2', 'm2'])
        self.assertEqual(s.players['p2']['zones']['deck'], ['m4', 'w2', 'm2'])

    def test_bloatuba_all_identical_cards_leave_two_to_order(self):
        s, _ = self.start(self.BLOAT, ['m2', 'm2', 'm2', 'm4'])
        self.choose(s, option='1')
        self.assertIsNotNone(s.rules_engine['pendingChoice'])
        self.order(s, bottom=['m2', 'm2'])
        self.assertEqual(s.players['p2']['zones']['deck'], ['m4', 'm2', 'm2'])

    def test_bloatuba_no_manifestation_skips_pick_and_orders_all_wills(self):
        s, _ = self.start(self.BLOAT, ['w2', 'w2', 'pw3', 'm4'])
        self.assertEqual(s.rules_engine['pendingChoice']['kind'], 'deck_reorder')
        self.order(s, bottom=['pw3', 'w2', 'w2'])
        self.assertEqual(s.players['p2']['zones']['deck'], ['m4', 'pw3', 'w2', 'w2'])
        self.assertFalse(any(s.rules_field_zone(i) == 'stalemate' for i in s.battlefield))

    def test_short_or_empty_decks_finish_without_missing_card(self):
        for name in (self.BLOAT, self.PONDER):
            for deck in ([], ['m2']):
                with self.subTest(card=name, deck=deck):
                    s, _ = self.start(name, deck)
                    if not deck:
                        self.assertIsNone(s.rules_engine['pendingChoice'])
                    elif name == self.BLOAT:
                        self.choose(s, option='0')
                        self.assertIsNone(s.rules_engine['pendingChoice'])
                    else:
                        self.order(s, extra=['m2'])
                        self.assertEqual(s.players['p1']['zones']['hand'], ['m2'])

    def test_optional_decline_never_chains_or_inspects(self):
        for name in (self.BLOAT, self.PONDER):
            with self.subTest(card=name):
                s, host = self.start(name, chain=False)
                self.choose(s, option='decline')
                self.assertIsNone(s.rules_engine['pendingChoice'])
                self.assertEqual(s.players['p1']['zones']['hand'], ['m3'])
                self.assertEqual(len(s.battlefield), 1)

    def test_no_chainable_card_never_opens_a_deck_choice(self):
        for name in (self.BLOAT, self.PONDER):
            with self.subTest(card=name):
                s = self.world()
                self.put(s, 'p1', 'hand', [self.cid('The Slumberer'), 'w2'])
                host = self.field(s, self.cid(name), 'host')
                s.apply_rules_action_result(self.action(name, host))
                self.assertIsNone(s.rules_engine['pendingChoice'])

    def test_bloatuba_rejects_non_integer_or_out_of_range_indices_atomically(self):
        for option in (False, True, 0.5, -1, '7', None, {}):
            with self.subTest(option=option):
                s, _ = self.start(self.BLOAT)
                self.reject(s, option=option)

    def test_bloatuba_does_not_pick_a_card_outside_the_revealed_prefix(self):
        s, _ = self.start(self.BLOAT, ['w2', 'm2', 'm4', 'm2'])
        s.take_zone_card('p2', 'deck', 'm2')
        self.reject(s, option='0')

    def test_bloatuba_roundtrip_to_same_prefix_is_a_stale_pick(self):
        s, _ = self.start(self.BLOAT, ['m2', 'w2', 'm4', 'm2'])
        s.move_zone_card('p2', 'deck', 'p2', 'hand', 'm2', 'top')
        s.move_zone_card('p2', 'hand', 'p2', 'deck', 'm2', 'top')
        self.reject(s, option='0')

    def test_reorder_rejects_changed_prefix_or_returned_card_atomically(self):
        for name in (self.BLOAT, self.PONDER):
            for mutation in ('prefix', 'roundtrip'):
                with self.subTest(card=name, mutation=mutation):
                    s, _ = self.start(name, ['w2', 'pw3', 'm4', 'm2'])
                    pid = 'p2' if name == self.BLOAT else 'p1'
                    if name == self.BLOAT: self.choose(s, option='0')
                    if mutation == 'prefix':
                        s.players[pid]['zones']['deck'].reverse()
                    else:
                        s.move_zone_card(pid, 'deck', pid, 'hand', 'w2', 'top')
                        s.move_zone_card(pid, 'hand', pid, 'deck', 'w2', 'top')
                    supplied = {'playerId': pid, 'top': [], 'bottom': ['w2', 'pw3']}
                    if name == self.PONDER:
                        supplied.update(top=['w2'], bottom=['pw3'], extra=['m4'])
                    self.reject(s, option={'groups': [supplied]})

    def test_bloatuba_deck_exit_respects_bob_and_orders_remaining_cards(self):
        s, _ = self.start(self.BLOAT, ['w2', 'm2', 'm4', 'pw3'])
        self.field(s, 'inner-deserts-134', 'bob', power_bonus=2)
        self.choose(s, option='1')
        self.assertFalse(any(s.rules_field_zone(i) == 'stalemate' for i in s.battlefield))
        self.assertEqual([c['cardId'] for c in s.rules_engine['suspendedCards']], ['m4'])
        self.order(s, bottom=['m2', 'w2'])
        self.assertEqual(s.players['p2']['zones']['deck'], ['pw3', 'm2', 'w2'])

    def test_stalemate_placement_is_not_an_entry_on_the_field(self):
        seeker = self.cid('Keen-eyed Seeker')
        s, _ = self.start(self.BLOAT, [seeker, 'w2', 'pw3'])
        self.choose(s, option='0')
        self.assertFalse(s.rules_engine['actionStack'])
        self.assertEqual(s.players['p2']['zones']['hand'], [])

    def test_source_departure_does_not_cancel_the_open_sequence(self):
        for name in (self.BLOAT, self.PONDER):
            with self.subTest(card=name):
                s, _ = self.start(name)
                s.battlefield.remove(s.find_battlefield_item('host'))
                if name == self.BLOAT:
                    self.choose(s, option='0')
                    self.order(s, bottom=['w2', 'm2'])
                    self.assertEqual(s.players['p2']['zones']['deck'], ['m4', 'w2', 'm2'])
                else:
                    self.order(s, top=['m2'], bottom=['m2'], extra=['w2'])
                    self.assertEqual(s.players['p1']['zones']['hand'], ['w2'])

    def test_ponderer_splits_identical_cards_between_top_bottom_and_hand(self):
        s, _ = self.start(self.PONDER, ['m2', 'm2', 'm2', 'w2'])
        self.order(s, top=['m2'], bottom=['m2'], extra=['m2'])
        self.assertEqual(s.players['p1']['zones']['deck'], ['m2', 'w2', 'm2'])
        self.assertEqual(s.players['p1']['zones']['hand'], ['m2'])

    def test_ponderer_put_is_not_a_draw_and_ignores_draw_lock_and_kanon(self):
        s, _ = self.start(self.PONDER, ['m2', 'w2', 'm4', 'pw3'])
        self.field(s, self.cid('Kanon, the Deathdealer'), 'kanon', owner='p2', zone='interzone')
        s.rules_engine['drawLocks'] = [{'playerId': 'p1', 'turn': 2}]
        self.order(s, top=['m2'], bottom=['w2'], extra=['m4'])
        self.assertEqual(s.players['p1']['zones']['hand'], ['m4'])
        self.assertFalse(any(e['kind'] == 'cards_drawn' for e in s.rules_engine.get('observedEvents') or []))
        self.assertIsNone(s.rules_engine['pendingChoice'])

    def test_ponderer_bob_suspends_only_the_card_transferred_to_hand(self):
        s, _ = self.start(self.PONDER, ['m2', 'w2', 'm4', 'pw3'])
        self.field(s, 'inner-deserts-134', 'bob', power_bonus=2)
        self.order(s, top=['m2'], bottom=['w2'], extra=['m4'])
        self.assertEqual(s.players['p1']['zones']['hand'], [])
        self.assertEqual(s.players['p1']['zones']['deck'], ['m2', 'pw3', 'w2'])
        self.assertEqual([c['cardId'] for c in s.rules_engine['suspendedCards']], ['m4'])

    def test_ponderer_requires_exactly_one_hand_card_and_exact_multiplicities(self):
        for supplied in ({'top': ['m2', 'm2'], 'bottom': ['w2'], 'extra': []},
                         {'top': [], 'bottom': ['w2'], 'extra': ['m2', 'm2']},
                         {'top': ['m2'], 'bottom': ['m2'], 'extra': ['m4']},
                         {'top': ['m2'], 'bottom': [], 'extra': ['w2']}):
            with self.subTest(supplied=supplied):
                s, _ = self.start(self.PONDER)
                self.reject(s, option={'groups': [{'playerId': 'p1', **supplied}]})

    def test_same_deck_reorder_preserves_zone_versions_and_entry_turns(self):
        weaken = self.cid('Weaken')
        s, _ = self.start(self.BLOAT, ['w2', 'pw3', weaken, 'm4'])
        s.rules_engine.setdefault('zoneEntryVersions', {}).update({'p2:deck:w2': 7, 'p2:deck:pw3': 3})
        # Refreshing the fixture choice after assigning initial metadata is setup.
        s.rules_engine['pendingChoice'] = s.make_bloatuba_reorder('p1', 'p2', ['w2', 'pw3', weaken], self.cid(self.BLOAT))
        s.rules_engine.setdefault('zoneEntryTurns', {}).update({'p2:deck:w2': 1, 'p2:deck:pw3': 2})
        versions = copy.deepcopy(s.rules_engine['zoneEntryVersions'])
        turns = copy.deepcopy(s.rules_engine['zoneEntryTurns'])
        self.order(s, bottom=[weaken, 'w2', 'pw3'])
        self.assertEqual(s.rules_engine['zoneEntryVersions'], versions)
        self.assertEqual(s.rules_engine['zoneEntryTurns'], turns)

    def test_wrong_actor_and_duplicate_reply_cannot_move_cards(self):
        for name in (self.BLOAT, self.PONDER):
            with self.subTest(card=name):
                s, _ = self.start(name, ['m2', 'w2', 'm4', 'pw3'])
                choice = copy.deepcopy(s.rules_engine['pendingChoice'])
                before = self.snapshot(s)
                wrong = 'p1' if choice['playerId'] == 'p2' else 'p2'
                self.assertIsNotNone(s.resolve_rules_choice(wrong, choice['id'], option='0')[0])
                self.assertEqual(self.snapshot(s), before)
                if name == self.BLOAT: self.choose(s, option='0')
                else: self.order(s, top=['m2'], bottom=['w2'], extra=['m4'])
                before = self.snapshot(s)
                self.assertIsNotNone(s.resolve_rules_choice(choice['playerId'], choice['id'], option='0')[0])
                self.assertEqual(self.snapshot(s), before)

    def test_ponderer_inspected_cards_stay_private_bloatuba_reveal_is_public(self):
        s, result = self.start(self.PONDER)
        for role, viewer in (('player', 'p1'), ('player', 'p2'), ('spectator', 'watcher')):
            choice = s.serialize_for(viewer, role)['rulesEngine']['pendingChoice']
            if viewer != 'p1': self.assertNotIn('cardIds', choice['groups'][0])
            self.assertNotIn('_deckPrefix', str(choice))
        s, result = self.start(self.BLOAT)
        visible = s.rules_payload_for_view(result, 'watcher', 'spectator')
        self.assertEqual(visible['afterChain']['cardIds'], ['m2', 'w2', 'm2'])

    def test_bloatuba_bob_replacement_removes_the_second_identical_position(self):
        s, _ = self.start(self.BLOAT)
        self.field(s, 'inner-deserts-134', 'bob', power_bonus=2)
        result = self.choose(s, option='1')
        self.assertEqual(result['remaining'], ['m2', 'w2'])
        self.assertEqual(s.players['p2']['zones']['deck'], ['m2', 'w2', 'm4'])
        self.assertEqual([c['cardId'] for c in s.rules_engine['suspendedCards']], ['m2'])

    def test_shared_multigroup_dissection_validates_both_before_moving_either(self):
        s = self.world()
        self.put(s, 'p1', 'deck', ['m2', 'm2', 'w2', 'pw3'])
        self.put(s, 'p2', 'deck', ['m4', 'm4', 'w2', 'm3'])
        s.apply_rules_action_result(self.action('Dissect'))
        valid = {'groups': [
            {'playerId': 'p1', 'top': ['m2'], 'bottom': ['m2', 'w2']},
            {'playerId': 'p2', 'top': ['m4'], 'bottom': ['m4', 'w2']}]}
        invalid = copy.deepcopy(valid)
        invalid['groups'][1]['bottom'] = ['w2']
        self.reject(s, option=invalid)
        self.choose(s, option=valid)
        self.assertEqual(s.players['p1']['zones']['deck'], ['m2', 'pw3', 'm2', 'w2'])
        self.assertEqual(s.players['p2']['zones']['deck'], ['m4', 'm3', 'm4', 'w2'])


if __name__ == '__main__':
    unittest.main()
