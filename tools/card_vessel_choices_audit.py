"""Retain independently specified Vessel choice executions and printed text."""
import argparse
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone
from run_card_audit import ROOT
from card_atavic_end_audit import Details
import card_behavior_audit as audit
sys.path.insert(0, str(ROOT / 'tests'))
from test_vessel_choice_clauses import VesselChoiceClauses


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--before', action='store_true')
    args = parser.parse_args()
    start = audit.digest()
    cases = [VesselChoiceClauses]
    if not args.before:
        from test_vessel_choice_integration import VesselChoiceIntegration
        cases.append(VesselChoiceIntegration)
    result = unittest.TextTestRunner(verbosity=1, resultclass=Details).run(
        unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in cases))
    contracts = [
        ('Gummo', 'gummo', 'Offer the End trigger from the Interzone; copy base power and gain effects in addition to its own from a chosen Vessel instance. Preserve existing bonuses, optionality and the copy after the chosen card leaves. Only the first printed paragraph is selected.'),
        ('Wish Upon the Stars', 'wish', 'The initial card owner chooses an eligible caster-owned Manifestation of equal or greater points in their Vessel. Return both to their owners’ Deck tops using effect movements and replacements, only while both original instances remain.'),
        ('Pescojolero, the Ringing King', 'pesco', 'Give the valid Stalemate Manifestations first, then put an eligible original Vessel instance worth at most the transferred points into your Interzone without Chain or tribute. Preserve immutable owner and current controller.')]
    clauses = []
    shared_scopes = {
        'test_indices_and_wrong_actor_are_rejected_atomically': {'gummo', 'wish', 'pesco'},
        'test_returned_vessel_card_is_not_an_old_selection': {'gummo', 'wish', 'pesco'},
        'test_surviving_identical_vessel_copy_remains_selectable': {'gummo', 'wish', 'pesco'},
        'test_removed_duplicate_cannot_select_the_remaining_copy': {'gummo', 'wish', 'pesco'},
        'test_successful_answer_cannot_be_replayed': {'gummo', 'wish', 'pesco'},
        'test_selected_second_duplicate_moves_that_occurrence_only': {'wish', 'pesco'},
        'test_vessel_reorder_does_not_create_new_instances': {'gummo'},
        'test_vessel_instance_ids_are_not_sent_to_players_or_spectators': {'wish'},
        'test_missing_interzone_source_card_cannot_create_a_phantom': {'pesco'},
    }
    for name, prefix, expected in contracts:
        card = next(c for c in audit.batches.CATALOG.cards.values() if c['name'] == name)
        paragraph = card['effect'].splitlines()[0] if prefix == 'gummo' else card['effect'].strip()
        tests = [t for t in result.executions if t['testId'].rsplit('.', 1)[-1].startswith('test_' + prefix)
                 or prefix in shared_scopes.get(t['testId'].rsplit('.', 1)[-1], set())]
        clauses.append({'cardId': card['id'], 'name': name, 'paragraphIndex': 0, 'printedParagraph': paragraph,
            'paragraphSha256': hashlib.sha256(paragraph.encode()).hexdigest(), 'expectedBehavior': expected,
            'testIds': [t['testId'] for t in tests], 'status': 'selected-branches-pass' if all(t['status'] == 'pass' for t in tests) else 'fail',
            'allBranchesCertified': False})
    assert set(t['testId'] for t in result.executions) == set(t for c in clauses for t in c['testIds'])
    assert audit.digest() == start, 'Sources changed during this execution'
    proof = {'schemaVersion': 1, 'sourceDigest': start, 'finishedAt': datetime.now(timezone.utc).isoformat(), 'published': False,
        'summary': {'executed': result.testsRun, 'passed': sum(t['status'] == 'pass' for t in result.executions),
                    'failed': sum(t['status'] != 'pass' for t in result.executions), 'skipped': len(result.skipped),
                    'selectedParagraphs': 3, 'cardsWithSelectedClauseProof': 3},
        'clauses': clauses, 'tests': result.executions,
        'limits': ['Resolution fixtures isolate the selected paragraphs; they do not certify all abilities or full phase scheduling.',
                   'Late mutations test stale answers, not legal responses inside an effect.',
                   'Other Vessel selectors, all replacement combinations, remote art, physical devices and Safari are outside this batch.']}
    out = ROOT / 'reports/systematic-audit/vessel-choice-followup'
    out.mkdir(parents=True, exist_ok=True)
    path = out / ('before.json' if args.before else 'clauses.json')
    if args.before and path.exists():
        raise RuntimeError('Refusing to overwrite historical evidence')
    path.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if not args.before:
        fixtures = {}
        for purpose in ('gummo', 'wish', 'pescojolero'):
            s = VesselChoiceClauses().pick(purpose)
            actor = s.rules_engine['pendingChoice']['playerId']
            fixtures[purpose] = s.serialize_for(actor, 'player')['rulesEngine']['pendingChoice']
        (out / 'picker-fixtures.json').write_text(json.dumps(fixtures, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(proof['summary']))
    return int(not result.wasSuccessful())


if __name__ == '__main__':
    raise SystemExit(main())
