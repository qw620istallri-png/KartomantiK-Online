"""Selected private hand clauses: printed oracles and retained executions."""
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
from test_private_hand_clauses import PrivateHandClauses

COMMON = ['selecting_identical_second_copy_preserves_the_first_instance', 'returned_hand_card_is_not_an_old_selection',
    'indices_and_wrong_actor_are_rejected_without_mutation', 'duplicate_reply_neither_pays_again_nor_chains_again',
    'private_hand_choices_hide_card_lists_from_spectators_but_not_the_players']
CONTRACTS = [
    ('Traumatize', 'Pay the printed essence cost at declaration, then lose five points when resolving. Show the chosen player’s hand and discard exactly the selected instance, respecting hand immunity and movement replacements. Empty/immune hands do not skip the five-point loss. Validate responses atomically; keep hand information private to the involved players and privileged observers.', COMMON + [
        'traumatize_pays_essence_before_response_but_loses_points_at_resolution',
        'traumatize_empty_or_immune_hand_still_loses_five_without_choice',
        'traumatize_can_choose_self_and_own_ritual_does_not_prevent_discard',
        'traumatize_late_hand_immunity_rejects_discard_atomically', 'traumatize_discard_respects_bob_limbo_suspension',
        'traumatize_tenebro_discard_offers_atomic_optional_support']),
    ('Extortionist Womb', 'Trigger as a normal Stack effect at Reaction after Revelation. The opponent may refuse; refusal or inability to Chain creates two hollow power-two Support tokens. If they accept, show their entire non-immune hand privately and let the effect controller choose a legal Manifestation for the opponent to Chain. Preserve selected instances, fallback conditions and the effect after source departure.', COMMON + [
        'womb_triggers_in_reaction_after_revelation_and_waits_on_stack',
        'womb_refusal_produces_exact_two_power_two_hollow_supports',
        'womb_yes_shows_the_whole_hand_but_only_manifestations_are_selectable',
        'womb_no_chainable_manifestation_or_empty_hand_uses_fallback',
        'womb_protected_hand_is_not_shown_and_cannot_be_chained',
        'womb_support_lock_after_show_uses_fallback_without_losing_choice_to_an_error',
        'womb_late_hand_immunity_uses_fallback_without_chain', 'womb_source_departure_does_not_cancel_either_branch',
        'womb_private_hand_proof_is_redacted_in_spectator_logs'])]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--before', action='store_true')
    args = parser.parse_args()
    start = audit.digest()
    cases, contracts = [PrivateHandClauses], list(CONTRACTS)
    if not args.before:
        from test_private_hand_integration import PrivateHandIntegration
        cases.append(PrivateHandIntegration)
        for index, methods in ((0, ['traumatize_reconnect_keeps_optional_replacement_and_pays_once']),
                               (1, ['womb_shows_full_hand_privately_then_chains_after_reconnect',
                                    'womb_no_chainable_hand_still_shows_privately_before_token_result'])):
            name, expected, current = contracts[index]
            contracts[index] = (name, expected, [*current, *methods])
    result = unittest.TextTestRunner(verbosity=1, resultclass=Details).run(
        unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in cases))
    by_name = {t['testId'].rsplit('.', 1)[-1]: t for t in result.executions}
    catalog = {c['name']: c for c in audit.batches.CATALOG.cards.values()}
    clauses, linked = [], set()
    for name, expected, methods in contracts:
        card = catalog[name]
        paragraph = card['effect'].strip()
        tests = [by_name['test_' + method] for method in methods]
        linked.update(t['testId'] for t in tests)
        clauses.append({'cardId': card['id'], 'name': name, 'paragraphIndex': 0,
            'printedParagraph': paragraph, 'paragraphSha256': hashlib.sha256(paragraph.encode()).hexdigest(),
            'expectedBehavior': expected, 'testIds': [t['testId'] for t in tests],
            'status': 'selected-branches-pass' if all(t['status'] == 'pass' for t in tests) else 'fail', 'allBranchesCertified': False})
    assert linked == {t['testId'] for t in result.executions}
    assert audit.digest() == start
    proof = {'schemaVersion': 1, 'sourceDigest': start, 'finishedAt': datetime.now(timezone.utc).isoformat(), 'published': False,
        'summary': {'executed': result.testsRun, 'passed': sum(t['status'] == 'pass' for t in result.executions),
            'failed': sum(t['status'] != 'pass' for t in result.executions), 'skipped': len(result.skipped),
            'selectedParagraphs': 2, 'cardsWithSelectedClauseProof': 2}, 'clauses': clauses, 'tests': result.executions,
        'limits': ['Traumatize uses actual declaration/payment; Womb result branches isolate its shipped effect, with timing checked through actual event queues.',
            'Network cases isolate automatic phase driving; they certify the choice protocol and private reveal delivery, not all phase scheduling.',
            'Late hand mutations are stale-answer checks, not legal response windows during an effect.',
            'Other hand/vessel selectors, all replacement combinations, physical browsers, remote art and VFX are outside this batch.']}
    out = ROOT / 'reports/systematic-audit/private-hand-followup'
    out.mkdir(parents=True, exist_ok=True)
    path = out / ('before.json' if args.before else 'clauses.json')
    if args.before and path.exists():
        raise RuntimeError('Refusing to overwrite historical before evidence')
    path.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(proof['summary']))
    return int(not result.wasSuccessful())


if __name__ == '__main__':
    raise SystemExit(main())
