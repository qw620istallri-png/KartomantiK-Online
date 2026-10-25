"""Text-grounded contracts, executable boundary matrix and traceable card evidence.

Generated contracts explicitly separate printed text, confirmed rulings and code
metadata. A passing smoke or a file reference never certifies the entire text.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "server")]
import card_scenario_batches as batches
import automation_coverage

OUT = ROOT / "reports" / "systematic-audit"
DECISIONS = ROOT / "audit" / "rule-decisions.json"
DIMENSIONS = ("normal", "wrong_priority", "game_ended", "pending_choice", "immediate_pending",
              "source_missing", "no_targets", "protected_targets", "wrong_phase", "unpaid")


def digest():
    paths = [*sorted((ROOT / "server").rglob("*.py")), *sorted((ROOT / "public").rglob("*.js")),
             *sorted((ROOT / "public").rglob("*.css")), ROOT / "public/index.html",
             ROOT / "public/cards-data.json", ROOT / "public/extensions/inner-desert/cards.json",
             ROOT / "public/card-abilities.json", ROOT / "public/automation-coverage-overrides.json",
             *sorted((ROOT / "audit").glob("*.json")),
             *sorted((ROOT / "tools").glob("*.py")), *sorted((ROOT / "tools").glob("*.mjs")),
             *sorted((ROOT / "tests").glob("test_*.*"))]
    h = hashlib.sha256()
    for path in paths:
        h.update(path.relative_to(ROOT).as_posix().encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def printed_assertions(card, rule):
    """Independent expectations read from explicit printed phrases, not flags."""
    text = str(card.get("effect") or "")
    checks = []
    phrases = [
        (r"(?im)^Cannot be played as First Manifestation\.", "canBeFirstManifestation", False),
        (r"(?im)^Cannot be used (?:as tribute|to pay tributes)\.", "canPayTribute", False),
        (r"(?im)^Adamant\.", "adamant", True),
        (r"(?im)^Float\.", "float", True),
        (r"(?im)^Support from hand\.", "supportFromHand", True),
        (r"(?im)^Support\.", "supportFromHand", True),
        (r"(?im)^Support\.", "supportFromInterzone", True),
    ]
    for pattern, field, expected in phrases:
        match = re.search(pattern, text)
        if match:
            actual = rule.get(field, field in {"canBeFirstManifestation", "canPayTribute"})
            checks.append({"clause": match.group(), "field": field, "expected": expected,
                           "actual": actual, "status": "pass" if actual == expected else "fail"})
    return checks


def contract(card, rule, registry, decisions):
    cid = card["id"]
    text = str(card.get("effect") or "")
    rulings = [d for d in decisions if cid in d.get("cards", []) or any(
        name.casefold() in card["name"].casefold() for name in d.get("cardNames", []))
        or not d.get("cards") and not d.get("cardNames")]
    return {"cardId": cid, "name": card["name"], "number": card.get("collectionNumber"), "type": card.get("type"),
            "printedText": text, "printedTextSha256": hashlib.sha256(text.encode()).hexdigest(),
            "clauses": [line.strip() for line in re.split(r"[\r\n]+", text) if line.strip()],
            "clauseReview": [{"text": line.strip(), "status": "independent-scenario-review-required"}
                             for line in re.split(r"[\r\n]+", text) if line.strip()],
            "confirmedRulings": [d["id"] for d in rulings], "printedAssertions": printed_assertions(card, rule),
            "encodedAbilities": copy.deepcopy(batches.main.CARD_ABILITIES.get(cid, [])),
            "mechanics": registry["mechanics"], "implementationStatus": registry["status"],
            "testReferences": registry["testRefs"],
            "semanticReview": "full-text-review-required",
            "limitations": ["Le texte est la référence ; les métadonnées sont l'implémentation à vérifier.",
                            "Une référence de fichier n'est pas une preuve d'exécution ni du texte entier."]}


def action_fixture(cid, ability):
    session, actor, source, targets, cost_card = batches.prepare_action(cid, ability)
    return session, actor, {"label": "Systematic card audit", "kind": ability.get("action") or "activated_effect",
        "source": source, "targets": targets, "ability_id": ability["id"], "payment_card_ids": [],
        "extra_essence_count": 1 if ability.get("optionalExtraEssence") else 0, "cost_card_id": cost_card,
        "as_support": session.card_rules[cid].get("type") == "manifestation" and ability.get("action") == "play_card",
        "placement": {"x": 0, "y": 0}}


def world(session):
    return copy.deepcopy({"players": session.players, "battlefield": session.battlefield, "tokens": session.tokens,
                          "rules": session.rules_engine, "phase": session.phase_tracker, "ended": session.ended})


def boundary_case(cid, ability, dimension):
    session, actor, kwargs = action_fixture(cid, ability)
    source = kwargs["source"]
    if dimension == "wrong_priority":
        session.rules_engine["priorityPlayerId"] = "p1" if actor == "p2" else "p2"
    elif dimension == "game_ended":
        session.ended = True
    elif dimension == "pending_choice":
        session.rules_engine["pendingChoice"] = {"id": "audit-choice", "kind": "binary_choice", "playerId": actor}
    elif dimension == "immediate_pending":
        session.rules_engine["actionStack"].append({"id": "audit-immediate", "immediate": True})
    elif dimension == "source_missing":
        if source["zone"] == "battlefield":
            session.battlefield = [item for item in session.battlefield if item["id"] != source["itemId"]]
        else:
            session.players[source["containerId"]]["zones"][source["zone"]] = []
    elif dimension == "no_targets":
        contract = session.rules_action_target_rules({"ability": ability}) or {}
        if not contract.get("groups") and not int(contract.get("min") or 0):
            return {"status": "not-applicable"}
        kwargs["targets"] = []
    elif dimension == "protected_targets":
        field_targets = [target for target in kwargs["targets"] if target.get("kind") == "card"]
        if not field_targets:
            return {"status": "not-applicable"}
        session.rules_engine["ongoingEffects"].extend({"kind": "protection", "duration": "until_end_of_turn",
            "startedTurn": session.phase_tracker["turn"], "target": target} for target in field_targets)
    elif dimension == "wrong_phase":
        session.phase_tracker["index"] = batches.ADVANCED_PHASES.index("recovery_draw")
    elif dimension == "unpaid":
        requirements, _ = session.rules_tribute_requirements(kwargs["kind"], source, ability, actor)
        if not any(requirements.values()) and not ability.get("essenceCost"):
            return {"status": "not-applicable"}
        session.tokens = []
        for player in session.players.values():
            for zone in ("hand", "graveyard", "receptacle"):
                player["zones"][zone] = [cid] if source["zone"] == zone and source["containerId"] == player["id"] else []
        for item in session.battlefield:
            item["counters"] = {}
    before = world(session)
    try:
        error, _result = session.declare_rules_action(actor, **kwargs)
        mutated = before != world(session)
        return {"status": "pass" if error and not mutated else "fail", "rejected": bool(error),
                "atomic": not mutated, "message": error}
    except Exception as exc:
        return {"status": "fail", "message": f"{type(exc).__name__}: {exc}"}


def matrix_for(cid):
    rows = []
    for ability in batches.main.CARD_ABILITIES.get(cid, []):
        if ability.get("trigger") or ability.get("passiveEffect") or ability.get("playPermission"):
            rows.append({"abilityId": ability["id"], "carrier": "trigger/passive/permission",
                         "checks": {"normal": {"status": "carrier-only"},
                                    **{name: {"status": "needs-family-scenario"} for name in DIMENSIONS[1:]}}})
            continue
        special = (ability.get("result") or {}).get("kind") in {"first_manifestation_trap", "create_essence"}
        failures, _messages = batches._run_player_action(cid, ability)
        checks = {"normal": {"status": "fail" if failures else "pass", "failures": failures}}
        for dimension in DIMENSIONS[1:]:
            checks[dimension] = {"status": "dedicated-path"} if special else boundary_case(cid, ability, dimension)
        rows.append({"abilityId": ability["id"], "carrier": "voluntary", "checks": checks})
    return rows


def build(execute=False):
    start_digest = digest()
    decisions = json.loads(DECISIONS.read_text(encoding="utf-8"))["decisions"]
    registry = automation_coverage.build_registry()["cards"]
    entries = []
    for cid in batches.CATALOG.order:
        entry = contract(batches.CATALOG.cards[cid], batches.main.CARD_RULES[cid], registry[cid], decisions)
        if execute:
            entry["matrix"] = matrix_for(cid)
            smoke = batches.smoke.smoke_card(cid)
            entry["carrierExecution"] = {"status": "fail" if smoke["failures"] else "pass", **smoke}
        entries.append(entry)
    failures = [{"cardId": entry["cardId"], "abilityId": row["abilityId"], "dimension": name, **check}
        for entry in entries for row in entry.get("matrix", []) for name, check in row["checks"].items() if check["status"] == "fail"]
    failures.extend({"cardId": entry["cardId"], "dimension": "carrier", "failures": entry["carrierExecution"]["failures"]}
                    for entry in entries if entry.get("carrierExecution", {}).get("status") == "fail")
    if digest() != start_digest:
        failures.append({"dimension": "source-integrity", "message": "Inputs changed during execution; rerun the matrix."})
    statuses = Counter(check["status"] for entry in entries for row in entry.get("matrix", []) for check in row["checks"].values())
    return {"schemaVersion": 1, "executed": execute, "sourceDigest": start_digest, "rulings": decisions,
            "summary": {"cards": len(entries), "abilities": sum(len(e["encodedAbilities"]) for e in entries),
                        "matrix": dict(sorted(statuses.items())), "failures": len(failures),
                        "printedAssertions": sum(len(e["printedAssertions"]) for e in entries),
                        "printedFailures": sum(c["status"] == "fail" for e in entries for c in e["printedAssertions"])},
            "failures": failures, "cards": entries}


def card_markdown(entry):
    lines = [f"# {entry['name']}", "", f"Identifiant : `{entry['cardId']}`", "", "## Texte de référence", "",
             entry["printedText"] or "Aucun effet imprimé.", "", "## Arbitrages confirmés", "",
             ", ".join(entry["confirmedRulings"]) or "Aucun arbitrage spécifique enregistré.", "", "## Capacités et matrice", "",
             "| Capacité | Normal | Priorité | Fin | Choix en cours | Immédiat | Source absente | Sans cible | Protection | Phase | Coût |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for row in entry.get("matrix", []):
        lines.append("| " + " | ".join([row["abilityId"], *[row["checks"][d]["status"] for d in DIMENSIONS]]) + " |")
    if entry.get("browserExecution"):
        lines += ["", "## Parcours UI effectivement exécutés", "", "| Capacité | Résultat | Résolution |", "|---|---|---|"]
        lines.extend(f"| {a['abilityId']} | {a['status']} | {a.get('resolution') or a.get('error', '')} |"
                     for a in entry["browserExecution"])
    if entry.get("referenceExecution"):
        lines += ["", "## Exécutions des modules référencés", "",
                  "Ce nombre concerne le module entier, pas une certification de cette carte.", ""]
        lines.extend(f"- `{module}` : {count} tests réussis." for module, count in entry["referenceExecution"].items())
    lines += ["", "## Mécaniques", "", ", ".join(entry["mechanics"]) or "Règles générales.",
              "", "## Références de tests (à distinguer des exécutions)", "", *[f"- `{ref}`" for ref in entry["testReferences"]],
              "", "## Limites", "", *[f"- {item}" for item in entry["limitations"]],
              "- Les cases `needs-family-scenario` restent visibles ; elles ne sont pas des réussites.", ""]
    return "\n".join(lines)


def write(report):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cards").mkdir(exist_ok=True)
    (OUT / "matrix.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Vérification systématique des cartes", "", "Texte imprimé, arbitrages, métadonnées et preuves sont séparés.",
             "Un test de capacité isolée n'est pas une certification de l'intégralité du texte.", "",
             "[Rapport des exécutions et limites](EXECUTIONS.md) · [Méthode](../../docs/SYSTEMATIC_CARD_AUDIT.md)", "",
             "```json", json.dumps(report["summary"], ensure_ascii=False, indent=2), "```", "",
             "| Carte | Fiche | Capacités | Tests volontaires réussis | Échecs |", "|---|---|---:|---:|---:|"]
    for entry in report["cards"]:
        cid = entry["cardId"]
        (OUT / "cards" / f"{cid}.md").write_text(card_markdown(entry), encoding="utf-8")
        checks = [c for row in entry.get("matrix", []) for c in row["checks"].values()]
        lines.append(f"| {entry['name']} | [fiche](cards/{cid}.md) | {len(entry['encodedAbilities'])} | {sum(c['status']=='pass' for c in checks)} | {sum(c['status']=='fail' for c in checks)} |")
    (OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        report = json.loads((OUT / "matrix.json").read_text(encoding="utf-8"))
        if report["sourceDigest"] != digest():
            raise SystemExit("Audit périmé : relancer --execute --write.")
        if not report.get("executed") or len(report["cards"]) != len(batches.CATALOG.order):
            raise SystemExit("Audit incomplet : une génération sans exécution ne constitue pas une preuve.")
    else:
        report = build(execute=args.execute)
        if args.write:
            write(report)
    print(json.dumps(report["summary"], ensure_ascii=True))
    for failure in report["failures"]:
        print(json.dumps(failure, ensure_ascii=True))
    return int(bool(report["summary"]["failures"] or report["summary"]["printedFailures"]))


if __name__ == "__main__":
    raise SystemExit(main())
