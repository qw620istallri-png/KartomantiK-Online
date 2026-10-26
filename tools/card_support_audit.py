"""Execute selected printed Support clauses and retain their exact test links.

This bounded ledger supplements earlier evidence; no AST name matching and no
claim that every branch of a linked paragraph or card has been certified.
"""
import hashlib
import json
import re
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import ROOT, EvidenceResult
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_support_clause_audit import SupportClauseAudit as Cases

LOCK_TEST = "pin_down_prevents_queued_puts_but_wretched_arena_allows_them"
FIELD_TEST = "consult_and_twist_new_field_entries_trigger_blossom_but_pan_internal_move_does_not"

# Each expectation is handwritten from the cited English paragraph. Indices are
# paragraph positions, not implementation ability IDs. Test links are explicit.
CLAUSES = [
    ("Pan Zuto, the Beckoner", 0, "Optional own Interzone put: CZ entry fires once, no new field entry or card play; stale targets and Pin Down prevent the move.", [
        "pan_interzone_put_fires_first_stone_cz_entry_once_without_reentering_field",
        "pan_interzone_put_does_not_repeat_seeker_field_entry_or_trigger_mazzolong",
        "pan_target_still_needs_own_interzone_at_resolution",
        "pan_only_triggers_when_entering_cz_and_is_optional", FIELD_TEST, LOCK_TEST]),
    ("Consult", 0, "Discard preceding Wills, put the first Manifestation under the recipient's control; field and CZ entries fire, playing does not. A blocked put leaves the Manifestation on top but retains earlier discards.", [
        "consult_put_fires_first_stone_cz_trigger_and_not_mazzolong_play_trigger",
        "consult_no_manifestation_discards_only_actual_deck_and_creates_no_support",
        "consult_still_discards_prior_wills_when_support_entry_is_prevented",
        "consult_checks_recipient_lock_and_old_turn_locks_expire", FIELD_TEST, LOCK_TEST]),
    ("Twist the Soul", 0, "Vessel put fires field and CZ entry once, not a play; Pin Down prevents extraction.", [
        "twist_put_fires_seeker_field_entry_once_and_not_mazzolong_play_trigger",
        "twist_put_fires_first_stone_cz_entry", FIELD_TEST, LOCK_TEST]),
    ("Twist the Soul", 1, "Win returns to the effect controller's Vessel; loss and stalemate return to the immutable owner's hand.", [
        "twist_outcome_returns_to_controller_vessel_on_win_and_owners_hand_otherwise"]),
    ("Stoic Snoozer", 0, "Only the previous turn's loss arms +1 for later Supports of the current controller; no retroactive bonus, source departure does not end it, next turn does.", [
        "stoic_previous_turn_loss_is_required_for_future_support_bonus",
        "stoic_bonus_is_prospective_control_scoped_and_expires"]),
    ("Jondo, the Pure Heart", 0, "Revelation compares base 4 strictly against own First, excluding additive bonuses; absent First, other source zones and next turn do not grant Support.", [
        "jondo_strict_base_comparison_ignores_additive_bonuses",
        "jondo_no_first_or_wrong_source_zone_does_not_grant_support"]),
    ("Jondo, the Pure Heart", 1, "Winning as Support exiles Jondo; First winner and losing Support do not take this exile destination.", [
        "jondo_only_winning_support_is_exiled_at_confrontation_cleanup"]),
    ("Mazzolong, the Log-chief", 0, "Own Support play including Chain and Chabak draws exactly one; put, opponent, wrong watcher zone and silenced watcher do not. Current control determines recipient.", [
        "mazzolong_each_own_support_play_draws_one_but_put_and_other_player_do_not",
        "mazzolong_chain_counts_as_play_and_draws_to_current_controller",
        "mazzolong_outside_interzone_or_silenced_does_not_watch_support",
        "chabak_special_support_play_triggers_mazzolong_once_after_two_cards_are_stalemated"]),
    ("Peropero, the Spirophant", 0, "Both seats see only the current controller's top; top updates, control changes and source departure update visibility.", [
        "peropero_top_visibility_follows_control_and_disappears_when_source_leaves"]),
    ("Peropero, the Spirophant", 1, "Uncovered top Manifestation can play as hand Support; deeper card and top Will are rejected atomically; a valid declared play survives Peropero leaving.", [
        "peropero_rejects_covered_manifestation_and_uncovered_will_atomically",
        "peropero_legal_top_support_survives_source_departure_after_declaration"]),
    ("Chabak, the Ungrateful", 0, "Two other hand Manifestations enter Stalemate; Chabak's special Support play draws once for Mazzolong.", [
        "chabak_special_support_play_triggers_mazzolong_once_after_two_cards_are_stalemated"]),
    ("Silem, the Magnetic", 2, "Stalemate cards put in Support lose effects for the turn: First Stone does not trigger, Mazzolong does not count a play, expiry restores effects without replaying entry.", [
        "silem_put_suppresses_arriving_cards_own_triggers_and_does_not_count_as_play", LOCK_TEST]),
    ("Regurgitating Catacomb", 1, "Selected already-resolving put obeys Pin Down and remains allowed under Wretched Arena; failed put keeps the Limbo card.", [LOCK_TEST]),
    ("Pin Down", 2, "The CZ-entry prohibition also applies to these five previously queued put effects.", [LOCK_TEST]),
    ("Wretched Arena", 0, "Its Support play prohibition permits those five put effects; this case isolates the resolved prohibition.", [LOCK_TEST]),
]


def main():
    start = audit.digest()
    result = unittest.TextTestRunner(verbosity=1, resultclass=EvidenceResult).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(Cases))
    executions = {t["testId"].rsplit(".", 1)[-1]: t for t in result.executions}
    by_name = {c["name"]: c for c in audit.batches.CATALOG.cards.values()}
    clauses, linked = [], set()
    for name, index, expected, methods in CLAUSES:
        card = by_name[name]
        text = (card.get("effect") or "").strip()
        paragraph = re.split(r"[\r\n]+", text)[index]
        tests = [executions["test_" + method] for method in methods]
        linked.update(t["testId"] for t in tests)
        clauses.append({"cardId": card["id"], "name": name, "paragraphIndex": index,
            "printedParagraph": paragraph,
            "paragraphSha256": hashlib.sha256(paragraph.encode()).hexdigest(),
            "expectedBehavior": expected, "testIds": [t["testId"] for t in tests],
            "status": "selected-branches-pass" if all(t["status"] == "pass" for t in tests) else "fail",
            "allBranchesCertified": False})
    assert linked == {t["testId"] for t in result.executions}, "Every executed case needs an explicit clause link"
    assert audit.digest() == start, "Sources changed while running"
    proof = {"schemaVersion": 1, "sourceDigest": start,
        "finishedAt": datetime.now(timezone.utc).isoformat(), "published": False,
        "summary": {"executed": result.testsRun, "passed": sum(t["status"] == "pass" for t in result.executions),
            "failed": len(result.failures) + len(result.errors) + len(result.unexpectedSuccesses),
            "skipped": len(result.skipped), "selectedParagraphs": len(clauses),
            "cardsWithSelectedClauseProof": len({c["cardId"] for c in clauses}),
            "fullCatalogSemanticCertification": False},
        "clauses": clauses, "tests": result.executions,
        "limits": ["Some effects are isolated at resolution, without declaration/payment/UI.",
            "Support event tests explicitly inject production events; they do not certify every entry path.",
            "Unlisted branches and interactions remain outside this batch; no global coverage percentage."]}
    out = ROOT / "reports/systematic-audit/support-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
