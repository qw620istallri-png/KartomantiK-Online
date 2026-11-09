"""Publish strict selected-clause proof for five Tribute-economy cards."""

import hashlib
import json
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from test_tribute_economy_family import (  # noqa: E402
    BRABATABA,
    CAULDRON,
    FOG,
    ORATOR,
    TEAPOT,
    TributeEconomyFamily,
)


CARD_METHODS = {
    TEAPOT: (
        "compiles_all_five_exact_contracts",
        "teapot_reduces_only_its_controllers_wills_from_the_interzone",
        "teapot_never_makes_a_zero_cost_will_negative_or_changes_manifestations",
        "teapot_and_fog_combine_before_the_zero_floor",
    ),
    FOG: (
        "compiles_all_five_exact_contracts",
        "fog_adds_one_hollow_to_every_players_printed_will",
        "fog_does_not_tax_manifestations_or_an_explicit_free_permission",
        "teapot_and_fog_combine_before_the_zero_floor",
    ),
    ORATOR: (
        "compiles_all_five_exact_contracts",
        "orator_globally_allows_each_players_controlled_field_tribute",
        "orator_rejects_opponent_controlled_stalemate_and_inactive_sources",
    ),
    BRABATABA: (
        "compiles_all_five_exact_contracts",
        "brabataba_makes_own_vessel_manifestation_transcendent_and_exiles_it",
        "brabataba_is_controller_scoped_and_blanking_removes_permission",
    ),
    CAULDRON: (
        "compiles_all_five_exact_contracts",
        "cauldron_retains_only_its_controllers_excess_at_end_of_turn",
        "cauldron_source_must_still_be_active_at_cleanup",
        "cauldron_does_not_create_extra_essence",
    ),
}

EXPECTED_BEHAVIORS = {
    TEAPOT: (
        "Only while an active Arcane Teapot is in its controller's Interzone, that controller pays one fewer Tribute for a printed Will. The reduction cannot make a cost negative, never changes a Manifestation cost, and combines with Cognitive Fog before applying the zero floor.",
    ),
    FOG: (
        "While Cognitive Fog is active, each player's printed Will costs one additional Hollow Tribute. Manifestations and explicit free-play permissions remain untaxed; Arcane Teapot can offset the added Tribute for its controller before the zero floor.",
    ),
    ORATOR: (
        "While an active Orator is on the field, every player may use a Manifestation they control in a Confrontation Zone or Interzone as Tribute, even when another player owns it. Opponent-controlled and Stalemate cards are illegal, and a paid card enters its immutable owner's Limbo.",
    ),
    BRABATABA: (
        "While an active Brabataba is on the field, its controller may use Manifestations in that controller's own Empathic Vessel as Transcendent Tribute. The paid physical card is exiled under its immutable owner; an opponent's Vessel and a blanked Brabataba grant no permission.",
    ),
    CAULDRON: (
        "At end-of-turn cleanup, an active Essence Cauldron preserves exactly its controller's existing excess Essence. It creates no additional Essence, does not preserve an opponent's excess, and cannot preserve anything after leaving the field or losing its effect.",
    ),
}


class EvidenceResult(unittest.TextTestResult):
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
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TributeEconomyFamily)
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
            "This proof certifies the five printed paragraphs of Arcane Teapot, Cognitive Fog, Orator of the Absurd, Brabataba, and Essence Cauldron across the selected strict branches and interactions.",
            "It does not independently re-certify every generic Tribute allocator, alternate payment source, Stack declaration, end-turn cleanup, or browser interaction contract.",
        ],
    }
    out = ROOT / "reports/systematic-audit/tribute-economy-followup"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clauses.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof["summary"]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
