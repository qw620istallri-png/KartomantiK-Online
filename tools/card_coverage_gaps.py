"""Generate the exact strict-coverage backlog, grouped by reusable mechanics."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "tools")]
OUTPUT_JSON = ROOT / "reports/systematic-audit/coverage-gaps.json"
OUTPUT_MARKDOWN = ROOT / "reports/systematic-audit/COVERAGE_GAPS.md"
REVIEW_PATHS = tuple(
    ROOT / f"audit/semantic-reviews/{name}.json"
    for name in ("001-150", "151-300", "301-450")
)


def semantic_reviews(paths=REVIEW_PATHS):
    records = {}
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        for record in document.get("records", document.get("cards", [])):
            records[record["cardId"]] = record
    return records


def greedy_mechanic_batches(cards):
    remaining = {card["cardId"] for card in cards}
    by_id = {card["cardId"]: card for card in cards}
    by_mechanic = defaultdict(set)
    for card in cards:
        mechanics = card["mechanics"] or ["unclassified"]
        for mechanic in mechanics:
            by_mechanic[mechanic].add(card["cardId"])
    batches = []
    while remaining:
        mechanic, members = min(
            (
                (mechanic, card_ids & remaining)
                for mechanic, card_ids in by_mechanic.items()
                if card_ids & remaining
            ),
            key=lambda entry: (-len(entry[1]), entry[0]),
        )
        selected = sorted(
            (by_id[card_id] for card_id in members),
            key=lambda card: (card["collectionNumber"], card["name"]),
        )
        batches.append({
            "mechanic": mechanic,
            "cardCount": len(selected),
            "cardIds": [card["cardId"] for card in selected],
            "cards": [card["name"] for card in selected],
        })
        remaining.difference_update(members)
    return batches


def build_inventory(coverage, automation, catalog, reviews):
    covered = {card["cardId"] for card in coverage.get("cards", [])}
    automation_cards = automation.get("cards", {})
    uncovered = []
    for card in catalog:
        if card["id"] in covered:
            continue
        automated = automation_cards.get(card["id"], {})
        review = reviews.get(card["id"], {})
        clauses = review.get("clauses", review.get("clauseReview", []))
        branch_oracles = 0
        for clause in clauses:
            branches = clause.get(
                "branchesAndExactOracles",
                clause.get("negativeAlternativeAndNumericScenario", []),
            )
            if isinstance(branches, list):
                branch_oracles += len(branches)
            elif branches:
                branch_oracles += 1
        mechanics = sorted(set(automated.get("mechanics") or []))
        uncovered.append({
            "cardId": card["id"],
            "collectionNumber": int(card.get("collectionNumber") or 0),
            "name": card["name"],
            "type": card.get("type"),
            "clauseCount": len(clauses),
            "branchOracleCount": branch_oracles,
            "abilityCount": len(automated.get("abilityIds") or []),
            "mechanics": mechanics,
            "reviewStatus": review.get("status"),
            "priorityScore": (
                3 * len(clauses)
                + 2 * len(automated.get("abilityIds") or [])
                + len(mechanics)
            ),
        })
    uncovered.sort(
        key=lambda card: (
            -card["priorityScore"], card["collectionNumber"], card["name"],
        )
    )
    mechanics = Counter(
        mechanic
        for card in uncovered
        for mechanic in (card["mechanics"] or ["unclassified"])
    )
    types = Counter(card["type"] or "unknown" for card in uncovered)
    batches = greedy_mechanic_batches(uncovered)
    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceDigest": coverage.get("sourceDigest"),
        "unitEvidence": coverage.get("unitEvidence"),
        "summary": {
            "catalogCards": len(catalog),
            "strictlyCoveredCards": len(covered),
            "uncoveredCards": len(uncovered),
            "uncoveredClauses": sum(card["clauseCount"] for card in uncovered),
            "uncoveredBranchOracles": sum(
                card["branchOracleCount"] for card in uncovered
            ),
            "greedyMechanicBatches": len(batches),
        },
        "uncoveredByType": dict(sorted(types.items())),
        "uncoveredByMechanic": [
            {"mechanic": mechanic, "cardCount": count}
            for mechanic, count in sorted(
                mechanics.items(), key=lambda entry: (-entry[1], entry[0])
            )
        ],
        "recommendedBatches": batches,
        "cards": uncovered,
    }


def markdown(report):
    summary = report["summary"]
    lines = [
        "# Lacunes de couverture sémantique stricte",
        "",
        f"Empreinte source : `{report['sourceDigest']}`",
        "",
        f"- Cartes couvertes : **{summary['strictlyCoveredCards']}/{summary['catalogCards']}**",
        f"- Cartes hors registre : **{summary['uncoveredCards']}**",
        f"- Paragraphes imprimés restant à relier : **{summary['uncoveredClauses']}**",
        f"- Oracles de branches déjà décrits mais non reliés : **{summary['uncoveredBranchOracles']}**",
        "",
        "## Lots mécaniques recommandés",
        "",
        "| # | Mécanique | Cartes nouvelles | Exemples |",
        "|---:|---|---:|---|",
    ]
    for index, batch in enumerate(report["recommendedBatches"], 1):
        examples = ", ".join(batch["cards"][:6])
        if len(batch["cards"]) > 6:
            examples += ", …"
        lines.append(
            f"| {index} | `{batch['mechanic']}` | {batch['cardCount']} | {examples} |"
        )
    lines.extend([
        "",
        "## Cartes hors registre",
        "",
        "| # | Carte | Type | Clauses | Branches décrites | Mécaniques |",
        "|---:|---|---|---:|---:|---|",
    ])
    for card in sorted(
        report["cards"],
        key=lambda entry: (entry["collectionNumber"], entry["name"]),
    ):
        mechanics = ", ".join(f"`{value}`" for value in card["mechanics"])
        lines.append(
            f"| {card['collectionNumber']} | {card['name']} | {card['type']} | "
            f"{card['clauseCount']} | {card['branchOracleCount']} | "
            f"{mechanics or '`unclassified`'} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_inventory(coverage):
    import main

    automation = json.loads(
        (ROOT / "public/automation-coverage.json").read_text(encoding="utf-8")
    )
    report = build_inventory(
        coverage, automation, main.CARD_DATA, semantic_reviews()
    )
    OUTPUT_JSON.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    OUTPUT_MARKDOWN.write_text(markdown(report), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--coverage",
        default="reports/systematic-audit/coverage-status.json",
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    path = Path(args.coverage)
    if not path.is_absolute():
        path = ROOT / path
    coverage = json.loads(path.read_text(encoding="utf-8"))
    report = write_inventory(coverage) if args.write else build_inventory(
        coverage,
        json.loads(
            (ROOT / "public/automation-coverage.json").read_text(
                encoding="utf-8"
            )
        ),
        __import__("main").CARD_DATA,
        semantic_reviews(),
    )
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
