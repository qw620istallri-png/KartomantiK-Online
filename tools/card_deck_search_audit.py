"""Explicit, text-grounded Deck search clauses and detailed execution evidence."""
import argparse
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import ROOT, EvidenceResult
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_deck_search_clause_audit import DeckSearchClauses
from test_deck_search_integration import DeckSearchIntegration


class Details(EvidenceResult):
    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        self.current.setdefault("subtests", []).append({
            "testId": subtest.id(), "status": "pass" if err is None else "fail",
            **({"detail": self._exc_info_to_string(err, test)} if err else {}),
        })


SEARCH = ["search_empty_deck_still_executes_final_shuffle_without_empty_choice",
    "search_candidates_private_but_selected_cards_are_revealed",
    "search_invalid_and_opposing_answers_do_not_move_or_shuffle", "concealed_search_results_remain_private"]
CONTRACTS = [
    ("Hermeto, the Observer", "Only opponent Vessel entry triggers for the immutable owner. Owner may select zero/one/two, reveal only selected cards, add them to hand, then shuffle once. Empty/single-card Decks and atomic refusals are checked.", SEARCH + [
        "hermeto_zero_one_two_selection_moves_exact_cards_then_shuffles_once",
        "search_duplicate_or_excess_cards_are_rejected_atomically",
        "hermeto_entry_uses_immutable_owner_and_only_opponent_vessel",
        "hermeto_single_card_deck_caps_the_choice_at_one",
        "hermeto_reconnect_keeps_search_private_then_reveals_selected_card_to_peer"]),
    ("Recall", "Only a current-turn loss permits declaration. Available search requires exactly one card, publicly revealed, then shuffle; replay cannot move or shuffle again.", SEARCH + [
        "recall_requires_current_turn_loss_before_declaration",
        "recall_search_requires_exactly_one_card_when_available",
        "search_replay_cannot_move_or_shuffle_again",
        "recall_real_play_resolves_before_search_and_goes_to_limbo_once"]),
    ("Mejik, the Labyrinther", "Unexhausted Interzone source declares a name as activation cost before opponent priority. Resolution uses that locked name even after source departure, discards from either target's Deck and shuffles once even on a failed search.", [
        "mejik_name_and_exhaustion_are_committed_before_opponent_priority",
        "mejik_declared_name_resolves_once_after_source_departure",
        "mejik_failed_search_still_shuffles_only_target_deck",
        "mejik_invalid_name_and_wrong_player_preserve_unpaid_declaration",
        "mejik_only_interzone_unexhausted_source_can_start_declaration",
        "mejik_pending_cost_blocks_responses_and_replay_cannot_activate_twice",
        "mejik_protocol_commits_name_before_peer_can_react_and_resolves_without_second_choice"]),
    ("Poopom, the Hydromancer", "Real field entry asks for a name. Match by printed name keeps the top card there and gives exactly +4 until turn end. Mismatch reveals/discards only that card without drawing; source departure still permits reveal/discard; invalid name is atomic.", [
        "poopom_matching_card_stays_on_top_and_gives_exact_four_until_turn_end",
        "poopom_wrong_name_discards_exactly_top_card_without_drawing",
        "poopom_name_comparison_is_by_name_not_catalogue_id",
        "poopom_source_departure_does_not_prevent_reveal_and_discard",
        "poopom_invalid_name_does_not_reveal_or_change_the_deck"]),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", action="store_true")
    args = parser.parse_args()
    start = audit.digest()
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c)
        for c in (DeckSearchClauses, DeckSearchIntegration))
    result = unittest.TextTestRunner(verbosity=1, resultclass=Details).run(suite)
    executions = {t["testId"].rsplit(".", 1)[-1]: t for t in result.executions}
    catalog = {c["name"]: c for c in audit.batches.CATALOG.cards.values()}
    clauses, linked = [], set()
    for name, expectation, methods in CONTRACTS:
        card = catalog[name]
        text = card["effect"].strip()
        tests = [executions["test_" + method] for method in methods]
        linked.update(t["testId"] for t in tests)
        clauses.append({"cardId": card["id"], "name": name, "paragraphIndex": 0,
            "printedParagraph": text, "paragraphSha256": hashlib.sha256(text.encode()).hexdigest(),
            "expectedBehavior": expectation, "testIds": [t["testId"] for t in tests],
            "status": "selected-branches-pass" if all(t["status"] == "pass" for t in tests) else "fail",
            "allBranchesCertified": False})
    assert linked == {t["testId"] for t in result.executions}
    assert audit.digest() == start, "Sources changed during execution"
    proof = {"schemaVersion": 1, "sourceDigest": start, "published": False,
        "finishedAt": datetime.now(timezone.utc).isoformat(),
        "summary": {"executed": result.testsRun, "passed": sum(t["status"] == "pass" for t in result.executions),
            "failed": sum(t["status"] not in {"pass", "skip"} for t in result.executions), "skipped": len(result.skipped),
            "selectedParagraphs": 4, "cardsWithSelectedClauseProof": 4, "networkScenarios": 2,
            "fullCatalogSemanticCertification": False},
        "clauses": clauses, "tests": result.executions,
        "limits": ["Selected branches only; some cases isolate resolution or prepare the confrontation outcome.",
            "No full-catalog or physical-device certification from this batch."]}
    out = ROOT / "reports/systematic-audit/deck-search-followup"
    out.mkdir(parents=True, exist_ok=True)
    filename = "before.json" if args.before else "clauses.json"
    (out / filename).write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
