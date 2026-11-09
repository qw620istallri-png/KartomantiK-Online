"""Publish strict selected-clause proof for Gigabonblade."""

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_grant_persist_family import (  # noqa: E402
    GIGABONBLADE,
    GrantPersistFamily,
)


METHODS = (
    "compiles_the_exact_three_paragraph_contract",
    "cannot_be_used_as_tribute_from_hand",
    "activation_scope_and_insufficient_power_are_atomic",
    "pays_two_power_and_grants_persist_only_until_turn_end",
    "winning_with_persist_keeps_gigabonblade_as_next_first",
    "natural_confrontation_loss_captures_without_exile_or_penalty",
    "effect_departure_exiles_and_weakens_each_current_field_manifestation",
    "suspension_or_inactive_text_prevents_exile_rider_and_penalty",
)

EXPECTED_BEHAVIORS = (
    "Gigabonblade can never be selected as Tribute, including from its owner's Hand; rejection is atomic.",
    "Only while active in the Confrontation Zone, Gigabonblade may target its own occurrence and reduce its current power by exactly 2 as an activation cost. Insufficient power, another target, another zone, or inactive text rejects without mutation. On resolution it gains Persist only until the end of that turn; after a win it remains in the Confrontation Zone and becomes its controller's next First Manifestation.",
    "When active Gigabonblade would leave the Confrontation Zone because of a card or effect, that movement is replaced by Exile. Only if it is actually exiled this way, every Manifestation currently on the field, including Support, loses exactly 2 power; the Stalemate Zone is outside the field. Natural confrontation capture, inactive text, or a competing Suspension replacement neither invokes this exile rider nor applies the penalty.",
)


def printed_paragraphs(effect):
    return [
        paragraph.strip()
        for paragraph in str(effect or "").replace("\r\n", "\n").split("\n")
        if paragraph.strip()
    ]


def main():
    start = audit.digest()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        GrantPersistFamily,
    )
    result = unittest.TextTestRunner(
        verbosity=1, resultclass=EvidenceResult,
    ).run(suite)
    executions = {
        test["testId"].rsplit(".", 1)[-1]: test
        for test in result.executions
    }
    tests = [executions["test_" + method] for method in METHODS]
    card = audit.batches.CATALOG.cards[GIGABONBLADE]
    paragraphs = printed_paragraphs(card["effect"])
    if len(paragraphs) != 3:
        raise AssertionError("Gigabonblade must expose exactly three paragraphs")
    clauses = []
    for index, (printed, behavior) in enumerate(zip(
        paragraphs, EXPECTED_BEHAVIORS,
    )):
        clauses.append({
            "cardId": GIGABONBLADE,
            "name": card["name"],
            "paragraphIndex": index,
            "printedParagraph": printed,
            "paragraphSha256": hashlib.sha256(
                printed.encode()
            ).hexdigest(),
            "expectedBehavior": behavior,
            "testIds": [test["testId"] for test in tests],
            "status": (
                "selected-branches-pass"
                if all(test["status"] == "pass" for test in tests)
                else "fail"
            ),
            "allBranchesCertified": False,
        })
    if audit.digest() != start:
        raise RuntimeError("Sources changed during execution")
    proof = {
        "schemaVersion": 1,
        "sourceDigest": start,
        "published": False,
        "finishedAt": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "executed": result.testsRun,
            "passed": sum(
                test["status"] == "pass" for test in result.executions
            ),
            "failed": len(result.failures) + len(result.errors),
            "skipped": len(result.skipped),
            "selectedClauses": len(clauses),
            "cardsWithSelectedClauseProof": 1,
            "fullCatalogSemanticCertification": False,
        },
        "clauses": clauses,
        "tests": result.executions,
        "limits": [
            "This proof certifies Gigabonblade's three paragraphs: Tribute prohibition, legal activation scope and cost, Persist lifetime and winning outcome, effect-departure Exile replacement, field-wide penalty, natural capture, inactive text, Stalemate exclusion, and competing Suspension replacement.",
            "It does not re-certify the separate Persist Ephemeral Will, multiple simultaneous Persist choices, every possible movement replacement ordering, or unrelated global power-loss prevention effects.",
        ],
    }
    out = ROOT / "reports/systematic-audit/grant-persist-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
