"""Publish strict Manifestation-as-Tribute proof for Mirror and Mountain."""

import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_manifestation_used_as_tribute_family import (  # noqa: E402
    MANIFESTATION_USED_AS_TRIBUTE_NAMES,
    ManifestationUsedAsTributeFamily,
)


METHODS = (
    "both_compile_the_exact_printed_contract",
    "real_will_payment_queues_both_with_exact_tribute_metadata",
    "mirror_only_follows_its_controller_and_only_while_ready",
    "inactive_sources_do_not_observe_tributes",
    "mirror_decline_does_not_exhaust_or_create_a_copy",
    "mirror_accept_exhausts_and_creates_one_support_token_copy",
    "mountain_exiles_the_immutable_owner_card_and_scores_other_players",
)

EXPECTED_BEHAVIORS = {
    "Melancholic Mirror": (
        "While its ready, active card is on the field, Melancholic Mirror offers its current controller an optional trigger only when that controller uses a Manifestation as Tribute. Declining changes nothing; accepting exhausts the Mirror and creates exactly one Support token copy of the paid Manifestation under that controller. An exhausted, disabled, or inactive Mirror offers no trigger.",
    ),
    "Sacred Mountain": (
        "While active on the field, Sacred Mountain observes every player's Manifestation Tribute. It exiles the paid card from its immutable owner's Limbo, including when its payer differs from that owner, then grants 5 Points to every player other than the payer. An inactive Mountain does not trigger.",
    ),
}


def printed_paragraphs(effect):
    return [
        paragraph.strip()
        for paragraph in str(effect or "").replace("\r\n", "\n").split("\n")
        if paragraph.strip()
    ]


def main():
    start = audit.digest()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        ManifestationUsedAsTributeFamily,
    )
    result = unittest.TextTestRunner(
        verbosity=1, resultclass=EvidenceResult,
    ).run(suite)
    executions = {
        test["testId"].rsplit(".", 1)[-1]: test
        for test in result.executions
    }
    tests = [executions["test_" + method] for method in METHODS]
    catalog = {
        card["name"]: card for card in audit.batches.CATALOG.cards.values()
    }
    clauses = []
    covered_card_ids = set()
    for name in MANIFESTATION_USED_AS_TRIBUTE_NAMES:
        card = catalog[name]
        paragraphs = printed_paragraphs(card["effect"])
        expected = EXPECTED_BEHAVIORS[name]
        if len(paragraphs) != len(expected):
            raise AssertionError(
                f"{name}: {len(paragraphs)} paragraphs, {len(expected)} oracles"
            )
        covered_card_ids.add(card["id"])
        for index, (printed, behavior) in enumerate(zip(paragraphs, expected)):
            clauses.append({
                "cardId": card["id"],
                "name": name,
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
            "cardsWithSelectedClauseProof": len(covered_card_ids),
            "fullCatalogSemanticCertification": False,
        },
        "clauses": clauses,
        "tests": result.executions,
        "limits": [
            "This proof certifies both printed Manifestation-as-Tribute clauses, real Will-payment metadata, Mirror controller/readiness and accept/decline branches, inactive-source suppression, Mountain immutable ownership, exile, and payer-relative scoring.",
            "It does not re-certify every alternate Tribute source, simultaneous Stack ordering among multiple copies, token-copy entry watchers, or every global Point replacement.",
        ],
    }
    out = ROOT / "reports/systematic-audit/manifestation-used-as-tribute-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
