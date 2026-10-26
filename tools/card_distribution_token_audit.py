"""Selected text-grounded Echo/Brood clauses, with explicit test associations."""
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import ROOT, EvidenceResult
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_distribution_token_clauses import DistributionTokenClauses


class Details(EvidenceResult):
    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        self.current.setdefault("subtests", []).append({
            "testId": subtest.id(), "status": "pass" if err is None else "fail",
            **({"detail": self._exc_info_to_string(err, test)} if err else {}),
        })


CONTRACTS = [
    ("Echo of the Wilds", "Only a losing participant triggers, with legal own Interzone targets. One/two/three targets receive +3, chosen +2/+1, or +1 each. Selection precedes Stack resolution. Modifier persists through next turn/source departure, but not Cleanse/target field exit.", [
        "echo_one_target_receives_all_three_without_a_choice",
        "echo_two_targets_player_chooses_which_receives_two",
        "echo_three_targets_each_receive_one",
        "echo_invalid_extra_target_and_wrong_player_do_not_mutate_choice",
        "echo_modifier_survives_next_turn_and_source_departure",
        "echo_cleanse_and_field_exit_remove_the_modifier",
        "echo_targets_require_controller_interzone_and_one_to_three_cards",
        "echo_only_defeat_of_a_participant_triggers",
        "echo_loss_target_selection_enters_stack_before_power_is_applied",
        "echo_no_legal_interzone_target_does_not_request_a_choice",
        "echo_disappeared_target_does_not_receive_a_modifier",
    ]),
    ("Stampeding Brood", "Opponent Vessel entry triggers for the immutable owner; own Vessel/other zones do not. Owner chooses zero/one/two within available slots. Tokens have one green power and Support in owner's Interzone and survive Resolution/next turn there. Invalid, opposing and replayed answers cannot mutate the choice or duplicate tokens.", [
        "brood_zero_one_two_are_real_choices_with_exact_characteristics",
        "brood_available_spaces_limit_choice_without_overflow",
        "brood_invalid_count_and_wrong_player_leave_state_unchanged",
        "brood_tokens_belong_to_owner_not_vessel_container",
        "brood_own_vessel_and_other_zones_do_not_trigger",
        "brood_interzone_tokens_survive_resolution_and_next_turn",
        "brood_token_choice_cannot_be_replayed",
        "brood_interzone_creation_does_not_bypass_support_prohibition_into_cz",
    ]),
]


def main():
    start = audit.digest()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DistributionTokenClauses)
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
            "failed": len(result.failures) + len(result.errors), "skipped": len(result.skipped),
            "selectedParagraphs": 2, "cardsWithSelectedClauseProof": 2,
            "fullCatalogSemanticCertification": False},
        "clauses": clauses, "tests": result.executions,
        "limits": ["Selected branches only; some cases isolate resolution or supply the confrontation outcome.",
            "No new two-seat network or full-catalog browser campaign in this batch.",
            "Brood persistence is checked in the Interzone; later CZ loss/stalemate interactions remain unasserted.",
            "WebKit Windows is not macOS Safari certification."]}
    out = ROOT / "reports/systematic-audit/distribution-token-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
