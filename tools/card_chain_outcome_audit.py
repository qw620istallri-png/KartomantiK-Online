"""Run explicit, text-grounded Chain clauses with detailed subtest evidence.

No card-name search is used to infer coverage. Associations below identify
selected branches only; the report does not certify a complete card.
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
import test_chain_outcome_clause_audit as clauses
import test_chain_outcome_integration as network


class Details(EvidenceResult):
    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        self.current.setdefault("subtests", []).append({
            "testId": subtest.id(), "status": "pass" if err is None else "fail",
            **({"detail": self._exc_info_to_string(err, test)} if err else {}),
        })


LOCK = ["chain_play_locks_filter_candidates_and_prevent_direct_mutation",
        "previously_queued_urocione_cannot_chain_after_a_support_play_lock",
        "chain_lock_only_applies_to_its_player_and_current_turn"]
URO = [
    "urocione_winner_goes_to_opponent_of_immutable_owner",
    "urocione_victory_memory_survives_cleanse_and_source_departure",
    "urocione_snapshot_win_does_not_change_after_later_control_change",
    "urocione_memory_survives_hand_limbo_and_vessel_then_new_entry",
    "urocione_memory_is_forgotten_after_deck_or_exile",
    "urocione_memory_does_not_attach_to_another_copy_still_in_hand",
    "urocione_stalemate_does_not_apply_victory_destination",
    "urocione_memory_applies_after_reentry_as_first_and_while_original_effects_are_lost",
    "urocione_reconnect_keeps_private_choice_and_foreign_owner_victory_destination",
]
LADY_SEARCH = [
    "lady_search_is_mandatory_and_shuffles_only_after_a_valid_selection",
    "lady_failed_search_still_shuffles_deck_without_revealing_it",
    "lady_suspension_replaces_chain_but_does_not_skip_final_shuffle",
    "lady_rejected_choice_retry_and_replay_shuffle_exactly_once",
]
DOL_RETURN = [
    "dol_effect_exit_returns_to_original_vessel_even_after_source_departure",
    "dol_return_memory_survives_vessel_hand_and_a_later_field_entry",
    "dol_return_memory_is_not_a_modifier_removed_by_cleanse",
    "dol_return_memory_is_forgotten_at_deck_or_exile",
    "dol_return_memory_does_not_apply_to_another_copy_on_field",
]

# Printed paragraph index; explicit independent expectation; exact test methods.
CONTRACTS = [
    ("Urocione, the Anarchist", 0, "Private hand Chain may be declined; no unusable empty choice; reconnect preserves it and only its controller can answer.", [
        "urocione_private_choice_can_be_declined_without_spending_or_moving",
        "urocione_no_chainable_hand_does_not_request_an_empty_choice",
        "urocione_reconnect_keeps_private_choice_and_foreign_owner_victory_destination"]),
    ("Urocione, the Anarchist", 1, "Victory sends the card to the immutable owner's opponent; memory survives Cleanse, source departure and non-Deck/Exile visits, without spreading to another live copy. Stalemate does not trigger victory.", URO),
    ("Lady of the Humps", 0, "Mandatory legal Deck selection; final shuffle once on successful Chain, failed search or suspended Chain; rejected/replayed answers cannot shuffle again.", LADY_SEARCH),
    ("Lady of the Humps", 1, "Only winning Chain is exiled to its immutable owner's Exile, including after Cleanse/source departure; defeat and stalemate are not wins.", [
        "lady_win_exiles_foreign_owned_chain_after_cleanse_and_host_departure", "lady_nonwinning_chain_is_not_exiled"]),
    ("Mind Parasite", 0, "Valid Limbo selection through its CZ entry trigger; other entry/payment branches are not asserted here.", ["mind_parasite_exile_memory_survives_source_departure"]),
    ("Mind Parasite", 1, "Winning selected Chain is still exiled after Mind Parasite leaves.", ["mind_parasite_exile_memory_survives_source_departure"]),
    ("Help!", 0, "Resolution loses exactly ten points even without a Chainable card; with a Manifestation it starts the required hand choice. Declaration/tribute is isolated out.", ["help_loses_exactly_ten_even_without_a_chainable_hand"]),
    ("Help!", 1, "Real declaration, tribute and Stack resolution put the Will in Limbo exactly once; its winning Chained card is exiled and the score cost remains exactly ten.", ["help_winning_chain_is_exiled_without_exiling_the_source_will_again"]),
    ("Looj, Cautious Agitator", 0, "Valid hand Chain through field entry; no-eligible and decline branches are outside this paragraph's selected proof.", ["looj_loss_returns_to_owner_and_scores_printed_five_for_actual_winning_opponent"]),
    ("Looj, Cautious Agitator", 1, "Losing Wind Sprout returns to its owner's hand and gives its printed five points to the winner; both orders of the two outcome effects work after source departure.", ["looj_loss_returns_to_owner_and_scores_printed_five_for_actual_winning_opponent"]),
    ("Dol, the Aching", 0, "May Chain owned cards from either Vessel, while cards owned by the opponent stay excluded.", ["dol_can_chain_owned_cards_from_either_vessel_but_not_opponents_cards"]),
    ("Dol, the Aching", 1, "Normal winning-card exile is not replaced by the rule for leaving due to cards/effects.", ["dol_win_exile_is_not_replaced_by_its_effect_exit_rule"]),
    ("Dol, the Aching", 2, "Effect exit returns to the original Vessel, even after source departure, Cleanse and non-Deck/Exile visits. Memory is erased by Deck/Exile and does not spread to another live copy.", DOL_RETURN),
    ("Pin Down", 2, "Chain is a Support play: candidates and direct/queued Chain respect the lock, player scope and expiry.", LOCK),
    ("Wretched Arena", 0, "Unlike a put, Chain is a Support play and is prevented by this resolved prohibition.", LOCK),
]


def main():
    start = audit.digest()
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c)
        for c in (clauses.ChainOutcomeClauseAudit, network.ChainOutcomeIntegration))
    result = unittest.TextTestRunner(verbosity=1, resultclass=Details).run(suite)
    executions = {t["testId"].rsplit(".", 1)[-1]: t for t in result.executions}
    by_name = {c["name"]: c for c in audit.batches.CATALOG.cards.values()}
    contracts, linked = [], set()
    for name, index, expectation, methods in CONTRACTS:
        card = by_name[name]
        text = re.split(r"[\r\n]+", (card.get("effect") or "").strip())[index]
        tests = [executions["test_" + method] for method in methods]
        linked.update(t["testId"] for t in tests)
        contracts.append({"cardId": card["id"], "name": name, "paragraphIndex": index,
            "printedParagraph": text, "paragraphSha256": hashlib.sha256(text.encode()).hexdigest(),
            "expectedBehavior": expectation, "testIds": [t["testId"] for t in tests],
            "status": "selected-branches-pass" if all(t["status"] == "pass" for t in tests) else "fail",
            "allBranchesCertified": False})
    assert linked == {t["testId"] for t in result.executions}, "Missing explicit clause association"
    assert audit.digest() == start, "Sources changed during the audit"
    proof = {"schemaVersion": 1, "sourceDigest": start,
        "finishedAt": datetime.now(timezone.utc).isoformat(), "published": False,
        "summary": {"executed": result.testsRun,
            "passed": sum(t["status"] == "pass" for t in result.executions),
            "failed": len(result.failures) + len(result.errors) + len(result.unexpectedSuccesses),
            "skipped": len(result.skipped), "networkScenarios": 2,
            "selectedParagraphs": len(contracts), "cardsWithSelectedClauseProof": len({c["cardId"] for c in contracts}),
            "fullCatalogSemanticCertification": False},
        "clauses": contracts, "tests": result.executions,
        "limits": ["Selected printed branches only; competing simultaneous memories are not certified.",
            "Some resolution tests isolate declaration, payment and comparison.",
            "The two live WebSocket tests hold automatic phase driving; its separate latency tests remain applicable.",
            "Two-player destination only; no multiplayer owner-opponent selection UI.",
            "No new physical-device, illustration or broad 450-card browser certification from this batch."]}
    out = ROOT / "reports/systematic-audit/chain-outcomes-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
