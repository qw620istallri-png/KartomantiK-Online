"""Publish strict proof for six previously unclassified intrinsic rules."""
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone

from run_card_audit import EvidenceResult, ROOT
import card_behavior_audit as audit

sys.path.insert(0, str(ROOT / "tests"))
from test_intrinsic_rules_family import (  # noqa: E402
    INTRINSIC_RULE_NAMES,
    IntrinsicRulesFamily,
)


METHODS = (
    "all_six_compile_the_exact_intrinsic_contract",
    "forgotten_pile_and_solar_use_their_printed_tribute_zones",
    "conditional_tribute_values_require_the_exact_printed_history",
    "zizek_requires_six_limbo_wills_and_retains_its_excess",
)

EXPECTED_BEHAVIORS = {
    "Forgotten Pile": [
        "Forgotten Pile may pay Tribute from Limbo and is exiled by that real payment; an ordinary Limbo Manifestation has no such permission.",
    ],
    "Solar Apparition": [
        "Solar Apparition may pay Tribute from its controller's Interzone; an ordinary Interzone Manifestation has no such intrinsic permission.",
        "When that real payment funds a power-reducing ephemeral Will, Solar Apparition adds exactly -2 to the power reduction.",
    ],
    "Zizek, the Immolated": [
        "Zizek is blocked from entering the Confrontation Zone with five Limbo Wills and becomes eligible at exactly six.",
        "A real Tribute payment with Zizek marks its three excess Essences as retained so end-of-turn expiry does not remove them.",
    ],
    "Alakazim, the Magician": [
        "Alakazim contributes base power 3 as Tribute only after its controller has played at least two Wills during the current turn.",
    ],
    "Kanopo, the Headless": [
        "Kanopo contributes base power 6 only with the additional sacrifice of a controlled Interzone Manifestation; a foreign donor is rejected.",
    ],
    "Palgonphio": [
        "Palgonphio contributes base power 4 only after its controller lost a Confrontation or any Confrontation stalemated during the previous turn.",
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
        IntrinsicRulesFamily
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
    for name in INTRINSIC_RULE_NAMES:
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
            "This proof certifies the eight printed intrinsic clauses and their first authoritative payment or eligibility transition.",
            "It does not re-certify every downstream Will resolution, Confrontation sequence or generic Tribute interaction already owned by dedicated families.",
        ],
    }
    out = ROOT / "reports/systematic-audit/intrinsic-rules-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
