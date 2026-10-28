"""Replay corrected oracles on published 141 class methods, without file edits.

Run from the repository with its normal Python test dependencies available.
Only the six changed gameplay mixins are replaced in memory. No main.py
network handlers are exercised by these 18 synchronous resolution tests.
"""
import hashlib
import importlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / d) for d in ('server', 'tests', 'tools')]
from test_vessel_choice_clauses import VesselChoiceClauses
from card_atavic_end_audit import Details
import card_behavior_audit as audit

BASE = '355efdd244fed3f5e2736dd25beb4326320f5844'
out = Path(__file__).resolve().parent
overrides = {}
for name, cls_name in [('game.zones', 'ZonesMixin'), ('game.choices.cards', 'CardsChoicesMixin'),
                       ('game.effects.board', 'BoardEffectsMixin'), ('game.effects.signature', 'SignatureEffectsMixin'),
                       ('game.phases', 'PhasesMixin'), ('game.chain', 'ChainMixin')]:
    module = importlib.import_module(name)
    relative = Path(module.__file__).resolve().relative_to(ROOT).as_posix()
    raw = subprocess.check_output(['git', 'show', BASE + ':' + relative], cwd=ROOT)
    namespace = dict(module.__dict__)
    exec(compile(raw.decode('utf-8'), relative, 'exec'), namespace)
    actual = getattr(module, cls_name)
    for method, value in namespace[cls_name].__dict__.items():
        if not method.startswith('__'):
            setattr(actual, method, value)
    overrides[relative] = hashlib.sha256(raw).hexdigest()

historical = json.loads((out / 'before.json').read_text(encoding='utf-8'))
names = [t['testId'].rsplit('.', 1)[-1] for t in historical['tests']]
names += ['test_pesco_put_entry_triggers_for_controller_without_playing_or_chaining',
          'test_missing_interzone_source_card_cannot_create_a_phantom']
result = unittest.TextTestRunner(resultclass=Details).run(unittest.TestSuite(VesselChoiceClauses(n) for n in names))
proof = {'schemaVersion': 1, 'filesystemSourceDigest': audit.digest(), 'runtimeBaselineCommit': BASE,
         'runtimeMixinOverridesSha256': overrides,
         'scope': 'Corrected synchronous resolution fixtures on published gameplay methods; no network handlers or file changes.',
         'summary': {'executed': result.testsRun, 'passed': sum(t['status'] == 'pass' for t in result.executions),
                     'failed': sum(t['status'] != 'pass' for t in result.executions), 'skipped': len(result.skipped)},
         'tests': result.executions}
(out / 'baseline-corrected.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(proof['summary']))
