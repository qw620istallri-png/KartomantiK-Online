"""Printed contracts and actual executions of two after-Chain paragraphs."""
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
from test_deck_sequence_clauses import DeckSequenceClauses


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--before', action='store_true')
    args = parser.parse_args()
    start = audit.digest()
    cases = [DeckSequenceClauses]
    if not args.before:
        from test_deck_sequence_integration import DeckSequenceIntegration
        cases.append(DeckSequenceIntegration)
    result = unittest.TextTestRunner(verbosity=1, resultclass=Details).run(
        unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in cases))
    shared = {'test_no_chainable_card_never_opens_a_deck_choice', 'test_optional_decline_never_chains_or_inspects',
        'test_short_or_empty_decks_finish_without_missing_card', 'test_source_departure_does_not_cancel_the_open_sequence',
        'test_wrong_actor_and_duplicate_reply_cannot_move_cards', 'test_reorder_rejects_changed_prefix_or_returned_card_atomically',
        'test_ponderer_inspected_cards_stay_private_bloatuba_reveal_is_public'}
    bloat_only = {'test_same_deck_reorder_preserves_zone_versions_and_entry_turns', 'test_stalemate_placement_is_not_an_entry_on_the_field'}
    contracts = [
        ('Bloatuba', 'bloatuba', 'Offer the optional entry Chain. Reveal top cards equal to the Chained Manifestation’s base power. The opponent puts one revealed Manifestation into Stalemate if possible; the controller orders every remaining occurrence on the bottom. Respect Deck-exit replacements, choice actors, stale snapshots and unchanged in-Deck identities.'),
        ('Expansive Ponderer', 'ponderer', 'Offer the optional entry Chain; privately inspect top cards equal to the Chained Manifestation’s base power. Put exactly one into Hand, then distribute every other occurrence between top and bottom in any order. This is a put, not a draw; preserve actual movement replacements and exact multiplicities.')]
    clauses = []
    for name, prefix, expected in contracts:
        card = next(c for c in audit.batches.CATALOG.cards.values() if c['name'] == name)
        tests = [t for t in result.executions if t['testId'].rsplit('.', 1)[-1].startswith('test_' + prefix)
                 or t['testId'].rsplit('.', 1)[-1] in shared
                 or prefix == 'bloatuba' and t['testId'].rsplit('.', 1)[-1] in bloat_only]
        paragraph = card['effect'].strip()
        clauses.append({'cardId': card['id'], 'name': name, 'paragraphIndex': 0, 'printedParagraph': paragraph,
            'paragraphSha256': hashlib.sha256(paragraph.encode()).hexdigest(), 'expectedBehavior': expected,
            'testIds': [t['testId'] for t in tests], 'status': 'selected-branches-pass' if all(t['status'] == 'pass' for t in tests) else 'fail',
            'allBranchesCertified': False})
    interactions = [t['testId'] for t in result.executions if 'test_shared_multigroup_' in t['testId']]
    assert {t['testId'] for t in result.executions} == {t for c in clauses for t in c['testIds']} | set(interactions)
    assert audit.digest() == start, 'Sources changed during execution'
    proof = {'schemaVersion': 1, 'sourceDigest': start, 'finishedAt': datetime.now(timezone.utc).isoformat(), 'published': False,
        'summary': {'executed': result.testsRun, 'passed': sum(t['status'] == 'pass' for t in result.executions),
                    'failed': sum(t['status'] != 'pass' for t in result.executions), 'skipped': len(result.skipped),
                    'selectedParagraphs': 2, 'cardsWithSelectedClauseProof': 2}, 'clauses': clauses,
        'otherInteractions': [{'name': 'Dissect', 'scope': 'Shared multi-group distribution only; not full card certification', 'testIds': interactions}],
        'tests': result.executions,
        'limits': ['Entry and Chain use actual queued abilities; synthetic Manifestations isolate printed base-power counts.',
                   'Network tests isolate automatic phase driving and do not certify complete match sequences.',
                   'Late Deck mutations check stale responses, not legal responses inside effects.',
                   'Deck snapshots use existing per-card-ID zone versions, not globally unique identities for every Deck occurrence.',
                   'Base-power modifiers applied to the Chained card during its entry are not certified by these printed-power fixtures.',
                   'Other afterDraw/afterDiscard continuations, all replacement combinations, real Safari, physical devices and remote art remain outside this batch.']}
    out = ROOT / 'reports/systematic-audit/deck-sequence-followup'
    out.mkdir(parents=True, exist_ok=True)
    path = out / ('before.json' if args.before else 'clauses.json')
    if args.before and path.exists(): raise RuntimeError('Refusing to overwrite historical evidence')
    path.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if not args.before:
        f = DeckSequenceClauses()
        fixtures = {}
        for label, name, deck in [('bloatuba-pick', f.BLOAT, ['m2', 'w2', 'm2', 'm4']),
                                  ('bloatuba-order', f.BLOAT, ['w2', 'w2', 'pw3', 'm4']),
                                  ('ponderer', f.PONDER, ['m2', 'm2', 'm2', 'w2'])]:
            s, _ = f.start(name, deck)
            actor = s.rules_engine['pendingChoice']['playerId']
            fixtures[label] = s.serialize_for(actor, 'player')['rulesEngine']['pendingChoice']
        (out / 'picker-fixtures.json').write_text(json.dumps(fixtures, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(proof['summary']))
    return int(not result.wasSuccessful())


if __name__ == '__main__': raise SystemExit(main())
