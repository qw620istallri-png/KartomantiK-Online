"""Explicit printed paragraphs, expectations and actual bounce/replay executions."""
import argparse
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import ROOT, EvidenceResult
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_bounce_replay_clauses import BounceReplayClauses


class Details(EvidenceResult):
    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        self.current.setdefault("subtests", []).append({
            "testId": subtest.id(), "status": "pass" if err is None else "fail",
            **({"detail": self._exc_info_to_string(err, test)} if err else {}),
        })


SINGLE = ["single_returns_owner_and_restricts_only_after_resolution",
    "foreign_control_returns_to_owner_and_locks_owner_not_controller",
    "returned_card_cannot_bypass_lock_through_stack_declaration",
    "returned_card_cannot_be_chained_from_hand",
    "another_hand_copy_can_play_once_without_unlocking_returned_copy",
    "next_turn_expires_lock_and_play_has_printed_power_without_old_bonus",
    "source_departure_and_cleanse_do_not_remove_replay_lock",
    "invalidated_target_does_not_create_a_replay_lock",
    "locked_hand_card_is_not_reported_as_a_playable_support"]
CONTRACTS = [
    ("Pigon, the Apprentice", 0, "Pay two hollow and exhaust before responses; only Support targets, owner-based return at resolution, no refund if target disappears. Returned copy cannot be played/Chained this turn; other hand copies and hand activations remain available.", SINGLE + [
        "pigon_pays_two_and_exhausts_before_opponent_response", "pigon_cannot_target_non_support_or_activate_while_exhausted",
        "pigon_failed_resolution_does_not_refund_paid_cost", "restriction_does_not_forbid_discard_activation_from_hand"]),
    ("Chiff and Chaff", 0, "Current recorded opponent Interzone Support entry permits hand Support; own entry or opponent hand entry alone does not. Cross-turn scope is not asserted.", ["chiff_support_condition_needs_opponent_interzone_entry"]),
    ("Chiff and Chaff", 1, "Own Support entry queues an opponent Support return; another card's entry never triggers it. Return and replay prohibition follow the owner and leave another unbound hand copy usable.", SINGLE + [
        "chiff_real_support_entry_queues_return_without_moving_target_early", "chiff_does_not_trigger_when_another_players_or_own_other_card_enters_support"]),
    ("Atavic Introspection", 2, "Spend exactly five Control counters before responses; fewer than five is refused atomically. Return any field Manifestation to its owner, with the same current-turn play restriction and copy/expiry rules.", SINGLE + ["atavic_spends_exactly_five_counters_before_resolving"]),
    ("Abandon", 0, "Only the chosen player's CZ Supports return, each to its own owner. Opponent Adamant prevents return, but own Adamant does not. Tokens do not become real hand cards and empty sets require no choice.", [
        "abandon_returns_only_target_players_cz_supports_to_each_owner", "abandon_adamant_only_prevents_opponents_return_and_creates_no_lock",
        "abandon_empty_supports_does_not_request_choice_or_create_locks", "abandon_token_return_creates_neither_hand_card_nor_lock"]),
    ("Abandon", 1, "Each actually returned copy is locked this turn; two returned copies remain locked when an unrelated third copy is played. Prevented/token returns create no lock.", [
        "abandon_duplicate_returned_copies_all_locked_but_third_copy_available",
        "abandon_adamant_only_prevents_opponents_return_and_creates_no_lock", "abandon_token_return_creates_neither_hand_card_nor_lock"]),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", action="store_true")
    args = parser.parse_args()
    start = audit.digest()
    cases = [BounceReplayClauses]
    if not args.before:
        from test_bounce_replay_integration import BounceReplayIntegration
        cases.append(BounceReplayIntegration)
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in cases)
    result = unittest.TextTestRunner(verbosity=1, resultclass=Details).run(suite)
    executions = {t["testId"].rsplit(".", 1)[-1]: t for t in result.executions}
    catalog = {c["name"]: c for c in audit.batches.CATALOG.cards.values()}
    clauses, linked = [], set()
    contracts = list(CONTRACTS)
    if not args.before:
        name, index, expectation, methods = contracts[0]
        contracts[0] = (name, index, expectation, methods + [
            "pigon_return_reconnect_rejects_stack_replay_but_next_turn_accepts"])
        name, index, expectation, methods = contracts[2]
        contracts[2] = (name, index, expectation, methods + [
            "unrestricted_copy_can_play_without_triggering_chiff_again_or_unlocking_returned_copy"])
    for name, index, expectation, methods in contracts:
        card = catalog[name]
        text = [p.strip() for p in card["effect"].splitlines() if p.strip()][index]
        tests = [executions["test_" + method] for method in methods]
        linked.update(t["testId"] for t in tests)
        clauses.append({"cardId": card["id"], "name": name, "paragraphIndex": index,
            "printedParagraph": text, "paragraphSha256": hashlib.sha256(text.encode()).hexdigest(),
            "expectedBehavior": expectation, "testIds": [t["testId"] for t in tests],
            "status": "selected-branches-pass" if all(t["status"] == "pass" for t in tests) else "fail", "allBranchesCertified": False})
    assert linked == {t["testId"] for t in result.executions}
    assert audit.digest() == start
    proof = {"schemaVersion": 1, "sourceDigest": start, "published": False,
        "finishedAt": datetime.now(timezone.utc).isoformat(),
        "summary": {"executed": result.testsRun, "passed": sum(t["status"] == "pass" for t in result.executions),
            "failed": sum(t["status"] not in {"pass", "skip"} for t in result.executions), "skipped": len(result.skipped),
            "selectedParagraphs": 6, "cardsWithSelectedClauseProof": 4, "fullCatalogSemanticCertification": False},
        "clauses": clauses, "tests": result.executions,
        "limits": ["Selected branches only; some resolutions isolate costs/declaration.",
            "Hidden-zone copy identity, Deck/Exile memory reset and arbitrary non-Hand Chain sources are outside this batch.",
            "Chiff's condition is checked with current-turn recorded entries; its cross-turn scope is not certified.",
            "The nine enters_support definitions are inspected; only selected Chiff branches are independently executed here."]}
    out = ROOT / "reports/systematic-audit/bounce-replay-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / ("before.json" if args.before else "clauses.json")).write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
