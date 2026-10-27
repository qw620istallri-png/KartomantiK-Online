"""Retain actual executions for selected Kanon/observer printed clauses."""
import argparse
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import ROOT
from card_atavic_end_audit import Details
import card_behavior_audit as audit
sys.path.insert(0, str(ROOT / "tests"))
from test_kanon_event_clauses import KanonEventClauses

CONTRACTS = [
    ("Kanon, the Deathdealer", 1, "Inspect without moving cards; discard half rounded up, accounting for identical copies, before drawing the rest. Honor movement replacements and emit actual draw/discard events once per batch. Reject malformed, stale and repeated choices without extra moves.", [
        "half_rounded_up_and_short_deck_quantities", "inspection_does_not_move_cards_before_confirmation",
        "invalid_choices_are_atomic_including_malformed_ids", "identical_copies_are_selected_by_quantity",
        "discards_all_chosen_cards_before_drawing_the_rest", "draw_records_only_kept_cards_and_one_batch",
        "suspension_replaces_movements_without_draw_discard_or_will_penalty",
        "source_departure_does_not_cancel_already_created_replacement", "repeated_answer_cannot_move_or_trigger_again",
        "stale_inspected_deck_is_cancelled_without_moving_cards"]),
    ("Kanon, the Deathdealer", 2, "Only Wills actually discarded cause one permanent -1 each, distributed among legal opposing field Manifestations, including repeated targets. No prompt without a legal target; suspension causes no discard penalty.", [
        "discarded_wills_allow_split_or_repeated_target_and_exact_power_loss",
        "no_will_penalty_choice_without_a_legal_target", "suspension_replaces_movements_without_draw_discard_or_will_penalty"]),
    ("Denblew, the Puritan", 2, "One +1 for each distinct opponent draw event after Kanon, regardless of cards in that event. Normal/replaced and two replaced draws remain distinct in one flush. No trigger for own draws, zero draws or inactive sources.", [
        "denblew_gets_one_bonus_for_multi_card_kept_draw", "denblew_sees_two_distinct_replaced_draws_before_flush",
        "denblew_separates_normal_and_replaced_draw_batches", "denblew_no_bonus_when_no_cards_are_drawn_or_own_player_draws",
        "inactive_watchers_do_not_trigger"]),
    ("Makaboon", 1, "Kanon's deck-discard batch triggers exactly one additional hand discard for that player. Empty hand does not block; the hand discard does not retrigger Makaboon.", [
        "makaboon_discards_one_extra_from_hand_per_deck_discard_batch", "makaboon_empty_hand_does_not_open_an_impossible_choice"]),
    ("Pale Entity", 0, "Two Kanon discards in one batch trigger one +5 score gain while Pale Entity is in the Interzone.", ["discard_score_watchers_trigger_once_for_two_discards"]),
    ("Forfog, the Hanged", 0, "Two Kanon discards by an opponent in one batch trigger one -5 score loss while Forfog is in the Interzone.", ["discard_score_watchers_trigger_once_for_two_discards"]),
    ("Tombloom", 0, "Kanon's discard enters Limbo from the Deck with discard provenance, triggering Tombloom once; resolution exiles it and applies exactly -2 to the chosen Manifestation.", ["tombloom_discard_trigger_exiles_source_and_weakens_target"]),
    ("Tenebro, Night Assailant", 0, "The player may replace Kanon's discard with entry as Support. Ask before any partial movement; acceptance and decline both complete the remaining draw and emit one discard event.", ["tenebro_optional_replacement_is_offered_without_partial_movement"]),
    ("Gorlok, the Blinded Indiscreet", 0, "For one isolated Kanon draw event, show only retained drawn cards, exile one and reduce Gorlok's power by exactly the number shown.", ["gorlok_single_event_shows_only_kept_cards_then_exiles_one"]),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", action="store_true")
    args = parser.parse_args()
    start = audit.digest()
    cases, contracts = [KanonEventClauses], list(CONTRACTS)
    if not args.before:
        from test_kanon_events_integration import KanonEventsIntegration
        cases.append(KanonEventsIntegration)
        name, paragraph, expectation, methods = contracts[0]
        contracts[0] = (name, paragraph, expectation, [*methods,
            "kanon_duplicate_copies_reconnect_and_denblew_exact_bonus",
            "tenebro_replacement_reconnect_keeps_the_whole_draw_atomic"])
    result = unittest.TextTestRunner(verbosity=1, resultclass=Details).run(
        unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in cases))
    by_name = {t["testId"].rsplit(".", 1)[-1]: t for t in result.executions}
    catalog = {c["name"]: c for c in audit.batches.CATALOG.cards.values()}
    clauses, linked = [], set()
    for name, index, expectation, methods in contracts:
        card = catalog[name]
        paragraph = [p.strip() for p in card["effect"].splitlines() if p.strip()][index]
        tests = [by_name["test_" + method] for method in methods]
        linked.update(t["testId"] for t in tests)
        clauses.append({"cardId": card["id"], "name": name, "paragraphIndex": index,
            "printedParagraph": paragraph, "paragraphSha256": hashlib.sha256(paragraph.encode()).hexdigest(),
            "expectedBehavior": expectation, "testIds": [t["testId"] for t in tests],
            "status": "selected-branches-pass" if all(t["status"] == "pass" for t in tests) else "fail",
            "allBranchesCertified": False})
    assert linked == {t["testId"] for t in result.executions}
    assert audit.digest() == start
    proof = {"schemaVersion": 1, "sourceDigest": start, "finishedAt": datetime.now(timezone.utc).isoformat(), "published": False,
        "summary": {"executed": result.testsRun, "passed": sum(t["status"] == "pass" for t in result.executions),
            "failed": sum(t["status"] != "pass" for t in result.executions), "skipped": len(result.skipped),
            "selectedParagraphs": len(contracts), "cardsWithSelectedClauseProof": len({c[0] for c in contracts})},
        "clauses": clauses, "tests": result.executions,
        "limits": ["Draw requests are explicit fixtures; most observer effects are resolved in isolation. Tombloom uses the actual target-choice/Stack path.",
            "Network fixtures seed an inspected draw and isolate automatic phase driving; reconnect and choices use actual sockets.",
            "Gorlok is tested for a single draw event; concurrent/delayed events, stale hand copies and its full text remain outside this batch.",
            "Tenebro's victory exile and other printed paragraphs are not certified.",
            "BOB coverage uses one Deck-suspension source, not competing replacements, all thresholds or release.",
            "No new real-device, Safari, remote-art, full-catalog UI or VFX certification."]}
    out = ROOT / "reports/systematic-audit/kanon-events-followup"
    out.mkdir(parents=True, exist_ok=True)
    path = out / ("before.json" if args.before else "clauses.json")
    if args.before and path.exists():
        raise RuntimeError("Refusing to overwrite historical before evidence")
    path.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
