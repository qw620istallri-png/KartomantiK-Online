"""Explicit selected Atavic paragraphs, independent expectations and executions."""
import argparse
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import ROOT, EvidenceResult
import card_behavior_audit as audit
sys.path.insert(0, str(ROOT / "tests"))
from test_atavic_end_clauses import AtavicEndClauses


class Details(EvidenceResult):
    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        self.current.setdefault("subtests", []).append({"testId": subtest.id(), "status": "pass" if err is None else "fail"})


COUNTERS = ["matching_plays_add_one_counter_per_distinct_event", "wrong_color_opponent_play_and_activation_do_not_count",
            "counter_follows_current_controller_not_immutable_owner", "face_down_or_blanked_source_does_not_collect",
            "putting_a_manifestation_on_field_is_not_a_play_event"]
ENDS = ["end_trigger_needs_ten_and_does_not_spend_counters", "skipped_end_phase_suppresses_only_its_controller",
        "declining_end_effect_does_not_move_cards_or_spend_counters"]
CONTRACTS = [
    ("Atavic Introspection", 1, "Each own blue play adds exactly one Control; two events add two. Wrong colors, opponent plays, activated effects, put events and inactive sources do not count; current controller governs ownership of the effect.", COUNTERS),
    ("Atavic Introspection", 3, "Ten counters enable an optional End effect without spending counters. Require two available cards; refuse empty/impossible choices, put exactly one on top and one on bottom in the chosen order, no shuffle; validate orders atomically and retain effect after source departure.", ENDS + [
        "introspection_does_not_offer_with_fewer_than_two_cards", "introspection_places_exact_top_and_bottom_in_either_order",
        "introspection_invalid_orders_and_wrong_player_are_atomic", "introspection_effect_survives_source_departure_after_targets"]),
    ("Atavic Oppression", 1, "Each own purple play adds exactly one Fatigue; event/controller and inactive-source exclusions match the printed condition.", COUNTERS),
    ("Atavic Oppression", 2, "Five counters are paid before responses. Opponent discards first, then controller draws one, including if no discard was possible. Source departure does not cancel the effect; invalid/repeated choices cannot draw. Kanon's draw replacement remains available after the discard.", [
        "oppression_activation_pays_five_before_responses", "oppression_discards_before_owner_draws",
        "oppression_draw_still_happens_when_opponent_cannot_discard", "oppression_source_departure_and_duplicate_choice_do_not_cancel_or_redraw",
        "oppression_invalid_discard_cannot_draw_or_change_the_pending_choice", "oppression_preserves_kanon_draw_replacement_after_discard"]),
    ("Atavic Oppression", 3, "Ten Fatigue enable optional End discard of zero, one or two available hand cards, without consuming counters; empty hand requires no offer; own skipped End suppresses the effect.", ENDS + [
        "oppression_optional_discard_accepts_zero_one_or_two", "oppression_empty_hand_has_no_end_offer"]),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", action="store_true")
    args = parser.parse_args()
    start = audit.digest()
    cases = [AtavicEndClauses]
    contracts = list(CONTRACTS)
    if not args.before:
        from test_atavic_end_integration import AtavicEndIntegration
        cases.append(AtavicEndIntegration)
        for index, method in ((1, "introspection_reconnect_preserves_exact_top_bottom_choice_and_rejects_bad_order"),
                              (3, "oppression_reconnect_keeps_discard_then_draws_once_after_confirmation")):
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
            "status": "selected-branches-pass" if all(t["status"] == "pass" for t in tests) else "fail", "allBranchesCertified": False})
    assert linked == {t["testId"] for t in result.executions}
    assert audit.digest() == start
    proof = {"schemaVersion": 1, "sourceDigest": start, "finishedAt": datetime.now(timezone.utc).isoformat(), "published": False,
        "summary": {"executed": result.testsRun, "passed": sum(t["status"] == "pass" for t in result.executions),
            "failed": sum(t["status"] != "pass" for t in result.executions), "skipped": len(result.skipped), "selectedParagraphs": 5, "cardsWithSelectedClauseProof": 2},
        "clauses": clauses, "tests": result.executions,
        "limits": ["Counter stimuli isolate play events from declaration; activated Oppression uses actual declaration and payment.",
            "This batch covers own-Limbo branches; the later atavic-limbo-followup executes the separate ruling for opponent Limbos and owner Deck destinations.",
            "Identical-copy selection and partial target invalidation placement are outside this batch.",
            "No certification of other printed paragraphs, all combinations or physical browsers."]}
    out = ROOT / "reports/systematic-audit/atavic-end-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / ("before.json" if args.before else "clauses.json")).write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
