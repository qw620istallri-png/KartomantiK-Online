"""Publish strict proof for five zone, Revelation, and threshold cards."""

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from card_tribute_economy_audit import EvidenceResult, ROOT, source_digest

sys.path.insert(0, str(ROOT / "tests"))
from test_zone_revelation_threshold_family import (  # noqa: E402
    BONZAI,
    DULFER,
    QUPER,
    SPIKED_PIT,
    TUXNU,
    ZoneRevelationThresholdFamily,
)


CARD_METHODS = {
    DULFER: (
        "compiles_all_five_exact_contracts",
        "dulfer_triggers_only_from_an_opponents_unlocked_vessel",
        "dulfer_vessel_owner_can_lose_exactly_ten_points",
        "dulfer_weakens_the_current_first_until_that_occurrence_leaves",
    ),
    TUXNU: (
        "compiles_all_five_exact_contracts",
        "tuxnu_copies_a_non_token_persistent_will_for_each_other_player",
        "tuxnu_excludes_wrong_types_hidden_cards_and_token_copies",
        "each_active_tuxnu_copies_once_without_recursive_growth",
    ),
    QUPER: (
        "compiles_all_five_exact_contracts",
        "quper_sacrifices_at_five_and_boosts_only_current_allied_confrontation_cards",
        "quper_uses_current_controller_and_bonus_expires_at_end_of_turn",
        "quper_replaced_sacrifice_grants_no_bonus",
    ),
    BONZAI: (
        "compiles_all_five_exact_contracts",
        "bonzai_reveals_only_the_vessel_owners_hand_to_its_owner_before_revelation",
        "bonzai_uses_immutable_owner_and_stops_when_vessel_effects_are_locked",
    ),
    SPIKED_PIT: (
        "compiles_all_five_exact_contracts",
        "spiked_pit_weakens_only_manifestations_entering_an_opponents_interzone",
        "spiked_pits_stack_follow_current_control_and_require_active_sources",
        "spiked_pit_applies_to_generic_manifestation_tokens_but_not_retroactively",
    ),
}

EXPECTED_BEHAVIORS = {
    DULFER: (
        "At Revelation, Dulfer triggers only from an opponent's unlocked Empathic Vessel. That Vessel's owner atomically chooses either to lose exactly 10 Points or to give their current First Manifestation -2 Power for that occurrence's remaining field lifetime; wrong actors and invalid choices do nothing.",
    ),
    TUXNU: (
        "While each active Tuxnu is on the field, every face-up non-Token Persistent Will entering under a player's control creates one Token copy under every other player's control. Manifestations, Ephemeral Wills, hidden cards, and Token copies do not trigger it, so created copies cannot recurse.",
    ),
    QUPER: (
        "While active on the field, Quper reaching at least 5 Power is Sacrificed to its immutable owner's Limbo. Only if that Sacrifice succeeds, every Manifestation its current controller already controls in the Confrontation Zone gets +2 Power until end of turn; later arrivals, other zones, and opponents are excluded, and a replaced Sacrifice grants no bonus.",
    ),
    BONZAI: (
        "Before Revelation, Bonzai in an Empathic Vessel reveals that Vessel owner's Hand only to Bonzai's immutable owner. The reveal exists during First selection and the before-Revelation window, ends afterward, and is suppressed while that Vessel's effects are disabled.",
    ),
    SPIKED_PIT: (
        "Whenever a Manifestation, including a generic Manifestation Token, enters an opponent's Interzone, each active Spiked Pit controlled by another player gives it -1 Power. Own entries, Wills, inactive sources, sources controlled by the entering player, and cards already present are unaffected.",
    ),
}


def catalog():
    cards = json.loads(
        (ROOT / "public/cards-data.json").read_text(encoding="utf-8")
    )
    cards += json.loads(
        (ROOT / "public/extensions/inner-desert/cards.json").read_text(
            encoding="utf-8"
        )
    )
    return {card["id"]: card for card in cards if card["id"] in CARD_METHODS}


def main():
    start = source_digest()
    cards = catalog()
    result = unittest.TextTestRunner(
        verbosity=1, resultclass=EvidenceResult,
    ).run(unittest.defaultTestLoader.loadTestsFromTestCase(
        ZoneRevelationThresholdFamily,
    ))
    executions = {
        test["testId"].rsplit(".", 1)[-1]: test
        for test in result.executions
    }
    clauses = []
    for card_id, methods in CARD_METHODS.items():
        card = cards[card_id]
        paragraphs = [
            line.strip() for line in str(card.get("effect") or "").splitlines()
            if line.strip()
        ]
        behaviors = EXPECTED_BEHAVIORS[card_id]
        if len(paragraphs) != len(behaviors):
            raise AssertionError(
                f"{card_id}: {len(paragraphs)} paragraphs != {len(behaviors)}"
            )
        tests = [executions["test_" + method] for method in methods]
        for index, (printed, behavior) in enumerate(zip(paragraphs, behaviors)):
            clauses.append({
                "cardId": card_id,
                "name": card["name"],
                "paragraphIndex": index,
                "printedParagraph": printed,
                "paragraphSha256": hashlib.sha256(printed.encode()).hexdigest(),
                "expectedBehavior": behavior,
                "testIds": [test["testId"] for test in tests],
                "status": (
                    "selected-branches-pass"
                    if all(test["status"] == "pass" for test in tests)
                    else "fail"
                ),
                "allBranchesCertified": False,
            })
    if source_digest() != start:
        raise RuntimeError("Sources changed during execution")
    proof = {
        "schemaVersion": 1,
        "sourceDigest": start,
        "published": False,
        "finishedAt": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "executed": result.testsRun,
            "passed": sum(test["status"] == "pass" for test in result.executions),
            "failed": len(result.failures) + len(result.errors),
            "skipped": len(result.skipped),
            "selectedClauses": len(clauses),
            "cardsWithSelectedClauseProof": len(CARD_METHODS),
            "fullCatalogSemanticCertification": False,
        },
        "clauses": clauses,
        "tests": result.executions,
        "limits": [
            "This proof certifies the five printed paragraphs of Dulfer, Tuxnu, Quper, Bonzai, and Spiked Pit across the selected strict branches.",
            "It does not independently re-certify every generic Vessel lock, privacy serialization, token-copy entry, Sacrifice replacement, state-action, or Power-modifier contract.",
        ],
    }
    out = ROOT / "reports/systematic-audit/zone-revelation-threshold-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
