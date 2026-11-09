"""Publish strict selected-clause proof for five mass/distribution cards."""

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from card_tribute_economy_audit import EvidenceResult, ROOT, source_digest

sys.path.insert(0, str(ROOT / "tests"))
from test_mass_distribution_outcomes_family import (  # noqa: E402
    DAMAGE,
    ENTRUST,
    EXTINGUISH,
    PUNISH,
    RECALL,
    MassDistributionOutcomesFamily,
)


CARD_METHODS = {
    ENTRUST: (
        "compiles_all_five_exact_contracts",
        "entrust_doubles_current_base_repeatedly_without_doubling_bonus",
        "entrust_doubles_a_generic_token_base",
    ),
    PUNISH: (
        "compiles_all_five_exact_contracts",
        "punish_destroys_only_present_winning_participants_of_this_turn",
        "punish_is_mass_nontargeting_but_respects_immunity",
    ),
    DAMAGE: (
        "compiles_all_five_exact_contracts",
        "damage_distributes_exactly_three_across_one_two_or_three_targets",
        "damage_rejects_wrong_zone_controller_and_invalid_extra_choice_atomically",
        "damage_modifier_persists_while_target_stays_on_field",
    ),
    RECALL: (
        "compiles_all_five_exact_contracts",
        "recall_exiles_manifestations_and_creates_hollow_effectless_supports_per_limbo",
        "recall_replacement_prevents_exile_and_copy",
        "recall_foreign_owned_card_exiles_to_owner_but_copy_stays_with_limbo_player",
    ),
    EXTINGUISH: (
        "compiles_all_five_exact_contracts",
        "extinguish_is_immediate_exiles_every_limbo_but_not_its_resolving_source",
        "extinguish_limbo_exit_replacement_prevents_exile",
        "extinguish_foreign_owned_card_exiles_to_immutable_owner",
    ),
}

EXPECTED_BEHAVIORS = {
    ENTRUST: (
        "Double the target field Manifestation's current base power. Repeated Entrust effects double the already-doubled base without multiplying additive bonuses; generic Token bases are valid, and Cleanse removes the doubling.",
    ),
    PUNISH: (
        "Destroy each face-up Manifestation still on the field whose item participated under this turn's confrontation winner. New cards and departed participants are not chased. Protection against targeting does not stop this mass effect, while Immunity does.",
    ),
    DAMAGE: (
        "Choose one to three opponent-controlled Interzone Manifestations and distribute exactly three lasting points of power loss: -3; -1/-2 in the chosen extra-point order; or -1 each. Wrong zones/controllers and invalid extra choices are rejected atomically.",
    ),
    RECALL: (
        "Exile every Manifestation actually leaving every Limbo and create one Hollow, effectless Support Token copy under that Limbo player's control. Wills remain; replacement-prevented exiles create no copy; copies use printed base and no points; physical cards enter their immutable owners' Exiles.",
    ),
    EXTINGUISH: (
        "Resolve immediately with no response window and exile every card actually leaving every player's Limbo, except the resolving source itself. Limbo-exit replacements still apply, and each physical card enters its immutable owner's Exile.",
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
        MassDistributionOutcomesFamily,
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
                "cardId": card_id, "name": card["name"],
                "paragraphIndex": index, "printedParagraph": printed,
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
        "schemaVersion": 1, "sourceDigest": start, "published": False,
        "finishedAt": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "executed": result.testsRun,
            "passed": sum(test["status"] == "pass" for test in result.executions),
            "failed": len(result.failures) + len(result.errors),
            "skipped": len(result.skipped), "selectedClauses": len(clauses),
            "cardsWithSelectedClauseProof": len(CARD_METHODS),
            "fullCatalogSemanticCertification": False,
        },
        "clauses": clauses, "tests": result.executions,
        "limits": [
            "This proof certifies the five printed paragraphs of Entrust, Punish the Winners, Damage, Recall the Consumed, and Extinguish Nostalgia across the selected strict branches.",
            "It does not independently re-certify every generic modifier, destruction replacement, Immediate protocol, token-entry trigger, or zone-movement contract.",
        ],
    }
    out = ROOT / "reports/systematic-audit/mass-distribution-outcomes-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
