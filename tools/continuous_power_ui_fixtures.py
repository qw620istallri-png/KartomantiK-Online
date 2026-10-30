"""Public states from production serialization, with literal per-card power oracles."""
import copy
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/p) for p in ('server', 'tests', 'tools')]
import test_continuous_power_family as family


def fixtures():
    f = family.ContinuousPowerFamily()
    rows = []
    for row in family.CONTRACTS:
        s, host, target = f.setup_case(row)
        # Spread display fixtures; geometry itself is outside this test.
        for index, item in enumerate(s.battlefield):
            item.update(x=420+index*30, y=650+index*12)
        for stage, expected in (('active', row['expectedPower']), ('disabled', row['inactivePower']), ('restored', row['expectedPower'])):
            host['effectsDisabled'] = stage == 'disabled'
            for viewer in ('p1', 'p2'):
                rows.append({'id': row['key'] + '-' + stage + '-' + viewer, 'viewer': viewer,
                    'state': s.serialize_for(viewer, 'player'), 'targetId': target['id'],
                    'expectedPower': expected, 'printedPower': row['targetBase'],
                    'explicitPower': int(target['counters'].get('power', 0))})
    return {'frames': rows, 'probe': {'id': 'aura-probe', 'name': 'Power fixture', 'type': 'manifestation',
        'power': 5, 'cost': 0, 'powerCost': '{G}', 'effect': '', 'temperaments': ['phlegmatic'],
        'image': 'card-back.webp', 'typeLabel': 'Manifestation'}}


if __name__ == '__main__': print(json.dumps(fixtures()))
