"""Explicit oracles and execution evidence for selected discard/draw clauses."""
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
from test_discard_draw_clauses import DiscardDrawClauses

COMMON = ["normal_draw_count_and_discard_before_draw", "empty_hand_cannot_pay_discard_and_draws_nothing",
    "draw_lock_is_respected_after_discard", "kanon_replaces_the_post_discard_draw",
    "kanon_does_not_replace_its_controller_own_draws", "recovery_draw_fixture_ignores_nonrecovery_lock_and_kanon",
    "invalid_discard_is_atomic_and_does_not_draw", "multi_card_draw_is_one_denblew_event",
    "press_then_pray_each_draws_after_its_own_discard", "other_players_draw_lock_does_not_block_own_draw",
    "draw_lock_prevents_kanon_offering_a_replacement"]
CONTRACTS = [
    ("Pray the Ether", 0, "Discard exactly one available hand card before requesting two draws; empty hand cannot pay. Respect draw locks, opponent Kanon, Recovery exclusions, one event per batch and independent nested discard/draw sequences.", COMMON),
    ("Alchemical Press", 2, "An own Will play offers an optional discard, then one draw; decline or unavailable/immune hand cannot force a choice. Recheck at resolution and legacy acceptance; pending effect survives source departure and cannot draw twice. Common draw restrictions apply.", COMMON + [
        "press_can_decline_without_discarding_or_drawing", "press_empty_hand_does_not_offer_a_pointless_trigger",
        "press_immune_hand_does_not_offer_an_unpayable_trigger", "press_late_hand_immunity_does_not_open_an_impossible_choice",
        "press_late_empty_hand_does_not_open_an_impossible_choice", "press_source_departure_and_duplicate_choice_draw_only_once",
        "press_legacy_accept_rechecks_discard_availability"]),
    ("Martyrize", 0, "Reveal and exile a hand Manifestation as an additional cost before responses. Request draws equal to its base power, honor draw locks and opponent Kanon; replacement does not refund the donor or prevent the Will's exile. Reject a non-Manifestation atomically.", [
        "martyrize_pays_reveal_exile_before_responses_then_draws_base_power",
        "martyrize_respects_draw_lock_without_refunding_cost", "martyrize_kanon_keeps_paid_cost_and_replaces_three_draws",
        "martyrize_invalid_additional_card_is_rejected_atomically", "draw_lock_prevents_kanon_offering_a_replacement"]),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", action="store_true")
    args = parser.parse_args()
    start = audit.digest()
    cases, contracts = [DiscardDrawClauses], list(CONTRACTS)
    if not args.before:
        from test_discard_draw_integration import DiscardDrawIntegration
        cases.append(DiscardDrawIntegration)
        for index, method in ((0, "pray_reconnect_preserves_discard_then_kanon_and_rejects_replay"),
                              (2, "martyrize_kanon_keeps_paid_exile_cost_through_reconnect")):
            name, paragraph, expectation, methods = contracts[index]
            contracts[index] = (name, paragraph, expectation, [*methods, method])
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in cases)
    result = unittest.TextTestRunner(verbosity=1, resultclass=Details).run(suite)
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
            "selectedParagraphs": 3, "cardsWithSelectedClauseProof": 3},
        "clauses": clauses, "tests": result.executions,
        "limits": ["Press unit cases isolate its triggered action; the combined Pray case explicitly queues paid/play events as the server does.",
            "Network tests isolate automatic phase driving; they do not certify scheduling or VFX.",
            "Recovery timing is an explicit fixture, not legal play or phase traversal of these cards.",
            "Other Press paragraphs, all card combinations, identical copies, physical devices and Safari are not certified."]}
    out = ROOT / "reports/systematic-audit/discard-draw-followup"
    out.mkdir(parents=True, exist_ok=True)
    path = out / ("before.json" if args.before else "clauses.json")
    if args.before and path.exists():
        raise RuntimeError("Refusing to overwrite historical before evidence")
    path.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
