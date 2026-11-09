"""Publish strict selected-clause proof for five protection/timing cards."""

import hashlib
import json
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT / "tests"))
from test_protection_timing_distribution_family import (  # noqa: E402
    CARESS,
    PALM,
    RITUAL,
    SCUTTLER,
    TRAP,
    ProtectionTimingDistributionFamily,
)


CARD_METHODS = {
    RITUAL: (
        "compiles_all_five_exact_contracts",
        "ritual_blocks_hostile_discard_but_not_self_discard",
        "ritual_protects_only_its_controller_hand",
    ),
    TRAP: (
        "compiles_all_five_exact_contracts",
        "trap_waits_hidden_then_reveals_after_opponent_first",
        "trap_cannot_be_played_as_an_ordinary_reaction_even_with_permission",
    ),
    CARESS: (
        "compiles_all_five_exact_contracts",
        "caress_zero_and_four_targets_are_legal_but_five_mixed_or_stale_are_not",
        "caress_splits_three_and_four_with_exact_order",
        "caress_with_zero_targets_resolves_without_a_choice",
        "caress_invalid_order_is_atomic",
        "caress_returns_foreign_owned_card_to_its_owners_deck",
    ),
    PALM: (
        "compiles_all_five_exact_contracts",
        "palm_applies_to_both_players_but_only_after_a_draw",
        "palm_overflow_uses_deck_entry_replacements",
        "palm_sequences_each_players_post_draw_overflow",
        "palm_overflow_choice_keeps_the_hand_private",
    ),
    SCUTTLER: (
        "compiles_all_five_exact_contracts",
        "scuttler_loss_queues_only_its_trigger_and_stalemates_winner",
        "scuttler_does_not_trigger_without_a_loss_and_lock_expires_next_turn",
    ),
}

EXPECTED_BEHAVIORS = {
    RITUAL: (
        "While Purifying Ritual is active, an opponent-controlled effect cannot inspect, discard, steal, or otherwise affect the controller's Hand; the protection is not global and does not protect the opponent's Hand.",
        "The controller's own effects and rule procedures, including a chosen hand-limit overflow, can still discard or move cards from that Hand.",
    ),
    TRAP: (
        "Trap can only replace its controller's First Manifestation during Revelation. It cannot be declared as an ordinary Reaction play, even when another effect grants a generic play permission.",
        "Trap waits face down and hidden from the opponent. After the opponent validates and reveals their First Manifestation, Trap is revealed, enters its owner's Limbo, costs 5 points, and its controller then plays and reveals their First Manifestation.",
    ),
    CARESS: (
        "Choose zero to four eligible cards that entered one player's Limbo during the current turn; five cards, stale entries, and cards from mixed Limbos are illegal.",
        "Move the rounded-up half to the bottoms of the physical cards' owners' Decks in the submitted order and the rest to the tops in the submitted order. Invalid partitions are atomic, and a foreign-owned card in the selected Limbo returns to its owner's Deck.",
    ),
    PALM: (
        "While Palm Coercer is active, every player's Hand limit is six cards.",
        "After each actual draw, that player privately chooses exactly the excess cards and their order for the bottom of their Deck. Ordered multi-player draws pause for each player in turn, and Deck-entry replacement effects still apply.",
    ),
    SCUTTLER: (
        "Only when Static Scuttler loses, every winner-controlled Manifestation in the Confrontation Zone moves to the Stalemate Zone and is protected from zone changes for the rest of that turn. Loser-controlled cards stay put, no loss queues no trigger, and the lock expires on the next turn.",
    ),
}


class EvidenceResult(unittest.TextTestResult):
    """Small local equivalent of the full audit runner's execution recorder."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executions = []
        self.current = None

    def startTest(self, test):
        super().startTest(test)
        self.current = {
            "testId": test.id(), "status": "running",
            "started": time.monotonic(),
        }

    def addSuccess(self, test):
        super().addSuccess(test)
        self.current["status"] = "pass"

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.current.update(
            status="fail", detail=self._exc_info_to_string(err, test),
        )

    def addError(self, test, err):
        super().addError(test, err)
        self.current.update(
            status="error", detail=self._exc_info_to_string(err, test),
        )

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.current.update(status="skip", reason=reason)

    def stopTest(self, test):
        self.current["durationMs"] = round(
            (time.monotonic() - self.current.pop("started")) * 1000, 3,
        )
        self.executions.append(self.current)
        self.current = None
        super().stopTest(test)


def source_digest():
    paths = [
        *sorted((ROOT / "server").rglob("*.py")),
        *sorted((ROOT / "public").rglob("*.js")),
        *sorted((ROOT / "public").rglob("*.css")),
        ROOT / "public/index.html",
        ROOT / "public/cards-data.json",
        ROOT / "public/extensions/inner-desert/cards.json",
        ROOT / "public/card-abilities.json",
        ROOT / "public/automation-coverage-overrides.json",
        *sorted((ROOT / "audit").glob("*.json")),
        *sorted((ROOT / "tools").glob("*.py")),
        *sorted((ROOT / "tools").glob("*.mjs")),
        *sorted((ROOT / "tests").glob("test_*.*")),
    ]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def selected_catalog():
    cards = json.loads(
        (ROOT / "public/cards-data.json").read_text(encoding="utf-8")
    )
    cards += json.loads(
        (ROOT / "public/extensions/inner-desert/cards.json").read_text(
            encoding="utf-8"
        )
    )
    return {card["id"]: card for card in cards if card["id"] in CARD_METHODS}


def printed_paragraphs(effect):
    return [
        paragraph.strip()
        for paragraph in str(effect or "").replace("\r\n", "\n").split("\n")
        if paragraph.strip()
    ]


def main():
    start = source_digest()
    catalog = selected_catalog()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        ProtectionTimingDistributionFamily,
    )
    result = unittest.TextTestRunner(
        verbosity=1, resultclass=EvidenceResult,
    ).run(suite)
    executions = {
        test["testId"].rsplit(".", 1)[-1]: test
        for test in result.executions
    }
    clauses = []
    for card_id, methods in CARD_METHODS.items():
        card = catalog[card_id]
        paragraphs = printed_paragraphs(card["effect"])
        behaviors = EXPECTED_BEHAVIORS[card_id]
        if len(paragraphs) != len(behaviors):
            raise AssertionError(
                f"{card_id} exposes {len(paragraphs)} paragraphs, "
                f"expected {len(behaviors)}"
            )
        tests = [executions["test_" + method] for method in methods]
        for index, (printed, behavior) in enumerate(zip(paragraphs, behaviors)):
            clauses.append({
                "cardId": card_id,
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
    if source_digest() != start:
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
            "cardsWithSelectedClauseProof": len(CARD_METHODS),
            "fullCatalogSemanticCertification": False,
        },
        "clauses": clauses,
        "tests": result.executions,
        "limits": [
            "This proof certifies the nine printed paragraphs of Purifying Ritual, Trap, Caress the Dawn, Palm Coercer, and Static Scuttler across the selected strict branches and interactions.",
            "It does not independently re-certify every generic Hand effect, Stack permission, Revelation protocol, zone-movement replacement, draw replacement, or Confrontation cleanup contract.",
        ],
    }
    out = ROOT / "reports/systematic-audit/protection-timing-distribution-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
