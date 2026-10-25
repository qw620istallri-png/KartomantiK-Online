"""Preflight competing movement replacements before changing the live game."""
import copy
from functools import wraps
import random

from .common import new_id


class ReplacementOrderRequired(Exception):
    def __init__(self, key, player_id, effects, choice=None):
        self.key, self.player_id, self.effects = key, player_id, effects
        self.choice = choice or {}


def replacement_checkpoint(shape):
    def decorate(method):
        @wraps(method)
        def checked(self, *args, **kwargs):
            if (getattr(self, '_rules_replacement_running', False)
                    or (self.rules_engine.get('pendingChoice') or {}).get('kind') == 'replacement_order'
                    or (self.rules_engine.get('pendingChoice') or {}).get('_optionalReplacement')
                    or not self.rules_competing_replacements_possible()):
                return method(self, *args, **kwargs)
            # The probe is isolated and synchronous: it cannot spend a live
            # resource or change another session's random sequence.
            memo = {id(getattr(self, key)): getattr(self, key)
                    for key in ('card_rules', 'card_points', 'card_labels') if hasattr(self, key)}
            probe = copy.deepcopy(self, memo)
            probe._rules_replacement_running = True
            # Reserve one private random stream for this operation, including
            # across a reconnect. Other games may roll while its chooser waits.
            local_state = getattr(self, '_rules_replacement_random_state', None)
            if local_state is None:
                local_state = random.Random(random.getrandbits(256)).getstate()
            global_state = random.getstate()
            priority = getattr(self, '_rules_replacement_priority', None)
            if priority is None:
                priority = (self.rules_lowest_confrontation_power_player() if self.current_phase_group() == 'confrontation'
                            else self.rules_engine.get('lastConfrontationWinnerId')) or self.rules_engine.get('priorityPlayerId')
            probe._rules_replacement_priority = priority
            random.setstate(local_state)
            conflict = None
            try:
                method(probe, *copy.deepcopy(args), **copy.deepcopy(kwargs))
            except ReplacementOrderRequired as needed:
                conflict = needed
            finally:
                random.setstate(global_state)
            if conflict is not None:
                previous = self.rules_engine.get('pendingChoice')
                choice = {
                    'id': new_id(), 'kind': 'replacement_order', 'playerId': conflict.player_id,
                    'actions': conflict.effects,
                    '_orderKey': conflict.key,
                    '_operation': {'method': method.__name__, 'args': args, 'kwargs': kwargs, 'shape': shape},
                    '_originalChoice': previous,
                    '_priorityPlayerId': self.rules_engine.get('priorityPlayerId'),
                    '_priorityPasses': list(self.rules_engine.get('priorityPasses') or []),
                    '_randomState': local_state,
                    '_replacementPriority': priority,
                    '_orders': copy.deepcopy(getattr(self, '_rules_replacement_orders', {})),
                    **conflict.choice,
                }
                self.rules_engine['pendingChoice'] = choice
                self.rules_engine['priorityPlayerId'] = choice['playerId']
                result = {'status': 'choice_required', 'kind': 'choice_required',
                          'choiceKind': choice['kind'], 'choiceId': choice['id'],
                          'playerId': choice['playerId'], 'stackDepth': len(self.rules_engine['actionStack'])}
                if shape in {'zone_move', 'zone_effect_move'}:
                    owner = self.card_owner_in_zone(args[0], args[1], args[4])
                    return (None, owner, result) if shape == 'zone_effect_move' else (None, owner)
                return (None, result) if shape in {'choice', 'declaration', 'priority'} else result
            previous_running = getattr(self, '_rules_replacement_running', False)
            previous_priority = getattr(self, '_rules_replacement_priority', None)
            self._rules_replacement_running = True
            self._rules_replacement_priority = priority
            random.setstate(local_state)
            try:
                return method(self, *args, **kwargs)
            finally:
                self._rules_replacement_running = previous_running
                self._rules_replacement_priority = previous_priority
                random.setstate(global_state)
        return checked
    return decorate
