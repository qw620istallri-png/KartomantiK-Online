"""Publish strict proof for the three remaining sacrifice-source cards."""
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_sacrifice_source_family import (  # noqa: E402
    SACRIFICE_SOURCE_NAMES,
    SacrificeSourceFamily,
)


METHODS = (
    "all_three_compile_the_exact_sacrifice_contract",
    "nebulas_enter_support_from_hand_and_really_have_float",
    "gusted_nebula_sacrifices_from_interzone_then_returns_supports",
    "cirrocumulus_rejects_a_foreign_stack_item_then_resolves_its_own",
    "rah_kio_pays_both_costs_then_destroys_only_field_tokens",
)

EXPECTED_BEHAVIORS = {
    "Gusted Nebula": [
        "Gusted Nebula may be played from Hand into Support without Tribute and has active Float semantics when it occupies the Interzone.",
        "Only an Interzone Gusted Nebula may pay its sacrifice cost; after payment, each controlled Support returns to its owner's Deck and each controller's First Manifestation gains the matching power.",
    ],
    "Cirrocumulus": [
        "Cirrocumulus may be played from Hand into Support without Tribute and has active Float semantics when it occupies the Interzone.",
        "Only an Interzone Cirrocumulus may sacrifice itself to resolve one controlled Stack item immediately; a foreign Stack item is rejected before payment.",
    ],
    "Rah-kio, the Flyswatter": [
        "A ready field Rah-kio exhausts and sacrifices itself as the activation cost, then destroys generic, copied and persistent-Will Tokens on the field while preserving physical Manifestations and Tokens in Stalemate.",
    ],
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
        SacrificeSourceFamily
    )
    result = unittest.TextTestRunner(
        verbosity=1, resultclass=EvidenceResult
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
    for name in SACRIFICE_SOURCE_NAMES:
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
            "This proof certifies the five printed paragraphs, their source costs, legal source or target gates and first authoritative results.",
            "It does not re-certify every destruction watcher, immunity replacement, Support ordering permutation or generic Stack interaction owned by other families.",
        ],
    }
    out = ROOT / "reports/systematic-audit/sacrifice-source-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
