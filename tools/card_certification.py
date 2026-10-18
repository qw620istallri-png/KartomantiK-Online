"""Run an evidence-based certification pass for every KKO card.

The report deliberately separates full sandbox scenarios from isolated ability
smokes and static-rule execution. This keeps the remaining scenario debt visible
without treating declarative compilation as proof by itself.

Usage::

    py tools/card_certification.py --write
    py tools/card_certification.py --check
    py tools/card_certification.py --strict-scenarios
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = ROOT / "server"
TOOLS_DIR = ROOT / "tools"
for path in (SERVER_DIR, TOOLS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import automation_coverage  # noqa: E402
import card_ability_smoke  # noqa: E402
import main as server_main  # noqa: E402
import sandbox  # noqa: E402
from session import ADVANCED_PHASES, Session  # noqa: E402


OUTPUT_DIR = ROOT / "reports"
OUTPUT_JSON = OUTPUT_DIR / "card-certification.json"
OUTPUT_MARKDOWN = OUTPUT_DIR / "card-certification.md"
KNOWN_CARD_TYPES = {"manifestation", "ephemeral_will", "persistent_will"}
SPECIAL_RESULT_HANDLERS = {
    "first_manifestation_trap": "play_first_manifestation_trap",
}
LEVEL_LABELS = {
    "scenario": "scénario comportemental",
    "simple": "règles génériques exécutées",
    "ability": "capacités exécutées isolément",
    "static": "règles statiques exécutées",
    "structural": "preuve structurelle seulement",
    "partial": "automatisation partielle",
    "manual": "application manuelle",
    "failed": "échec",
}


def new_session() -> Session:
    return Session(
        card_points=server_main.CARD_POINTS,
        card_labels=server_main.CARD_LABELS,
        manifestation_ids=server_main.CARD_MANIFESTATION_IDS,
        card_rules=server_main.CARD_RULES,
        rules_beta=True,
    )


def _compiled_ability_failures(card_id: str) -> list[str]:
    """Prove that every declarative ability reached its responsible rule bucket."""
    abilities = list(server_main.CARD_ABILITIES.get(card_id) or [])
    rules = server_main.CARD_RULES.get(card_id) or {}
    failures: list[str] = []
    ids = [str(ability.get("id") or "") for ability in abilities]
    if any(not ability_id for ability_id in ids):
        failures.append("une capacité déclarative n'a pas d'identifiant")
    if len(ids) != len(set(ids)):
        failures.append("des identifiants de capacités sont dupliqués")

    expected = {
        "activatedAbilities": [],
        "playedAbilities": [],
        "triggeredAbilities": [],
        "playPermissions": [],
    }
    passive_effects = []
    for ability in abilities:
        if ability.get("trigger"):
            expected["triggeredAbilities"].append(ability)
        elif ability.get("playPermission"):
            expected["playPermissions"].append(ability)
        elif isinstance(ability.get("passiveEffect"), dict):
            passive_effects.append(ability["passiveEffect"])
        elif ability.get("action") == "play_card":
            expected["playedAbilities"].append(ability)
        else:
            expected["activatedAbilities"].append(ability)

        result = ability.get("result")
        if result is not None:
            cleaned = Session.clean_rules_action_result(result)
            if ability.get("trigger"):
                cleaned = Session.clean_rules_trigger_result(result) or cleaned
            special_handler = SPECIAL_RESULT_HANDLERS.get(result.get("kind"))
            if cleaned is None and not (
                special_handler and callable(getattr(Session, special_handler, None))
            ):
                failures.append(
                    f"{ability.get('id') or '?'} : résultat {result.get('kind')!r} rejeté par le moteur"
                )
        for phase_id in ability.get("phaseIds") or []:
            if phase_id not in ADVANCED_PHASES:
                failures.append(
                    f"{ability.get('id') or '?'} : phase inconnue {phase_id!r}"
                )
        for contract in [ability.get("targets"), *(ability.get("targetGroups") or [])]:
            if not contract:
                continue
            minimum = int(contract.get("min") or 0)
            maximum = int(contract.get("max") or 0)
            if maximum and minimum > maximum:
                failures.append(
                    f"{ability.get('id') or '?'} : contrat de cible min supérieur à max"
                )

    for bucket, expected_abilities in expected.items():
        compiled = list(rules.get(bucket) or [])
        if compiled != expected_abilities:
            failures.append(f"compilation incohérente dans {bucket}")
    if list(rules.get("passiveEffects") or []) != passive_effects:
        failures.append("compilation incohérente dans passiveEffects")
    return failures


def _state_failures(session: Session, scenario: dict, catalog: sandbox.Catalog) -> list[str]:
    failures = []
    if len(session.players) != 2:
        failures.append(f"{scenario['id']} : {len(session.players)} joueurs au lieu de 2")
    if session.current_phase_id() != scenario["phase"]:
        failures.append(
            f"{scenario['id']} : phase {session.current_phase_id()}, attendu {scenario['phase']}"
        )
    card_ids = [
        card_id
        for player in session.players.values()
        for zone in player["zones"].values()
        for card_id in zone
    ]
    card_ids.extend(item["cardId"] for item in session.battlefield)
    duplicates = sorted(card_id for card_id, count in Counter(card_ids).items() if count > 1)
    if duplicates:
        failures.append(f"{scenario['id']} : cartes dupliquées {', '.join(duplicates)}")
    try:
        for item in session.battlefield:
            if catalog.rules.get(item["cardId"], {}).get("type") == "manifestation":
                session.rules_manifestation_characteristics(item)
        session.rules_player_can_act("certifier")
        session.serialize_for("certifier", "player")
    except Exception as exc:
        failures.append(
            f"{scenario['id']} : lecture moteur impossible : {type(exc).__name__}: {exc}"
        )
    for player in session.players.values():
        hand_types = {
            catalog.cards[card_id]["type"]
            for card_id in player["zones"]["hand"]
        }
        if "manifestation" not in hand_types:
            failures.append(f"{scenario['id']} : main sans Manifestation")
        if not hand_types.intersection({"ephemeral_will", "persistent_will"}):
            failures.append(f"{scenario['id']} : main sans Volonté")
    return failures


async def _run_script(session: Session) -> list[dict]:
    return await sandbox.run_script(
        session,
        server_main.handle_message,
        server_main.auto_advance_rules_phases,
        server_main.AUTO_PASS_MESSAGE_TYPES,
    )


def _exercise_scenario(
    catalog: sandbox.Catalog,
    scenario: dict,
    check_hand_mix: bool,
) -> tuple[list[str], int]:
    failures: list[str] = []
    session = new_session()
    try:
        sandbox.apply_scenario(session, catalog, scenario, "certifier")
        if check_hand_mix:
            failures.extend(_state_failures(session, scenario, catalog))
        else:
            if session.current_phase_id() != scenario["phase"]:
                failures.append(
                    f"{scenario['id']} : phase {session.current_phase_id()}, attendu {scenario['phase']}"
                )
        if scenario.get("script"):
            reports = asyncio.run(_run_script(session))
            failures.extend(
                f"{scenario['id']} / {report.get('label') or report['step']} : {report['error']}"
                for report in reports
                if not report["ok"]
            )
            if len(reports) != len(scenario["script"]):
                failures.append(
                    f"{scenario['id']} : {len(reports)} étapes exécutées sur {len(scenario['script'])}"
                )
            return failures, len(reports)
    except Exception as exc:  # keep the report useful when one card is malformed
        failures.append(f"{scenario.get('id', '?')} : {type(exc).__name__}: {exc}")
    return failures, 0


def _audit_card(
    card_id: str,
    catalog: sandbox.Catalog,
    coverage: dict,
    written_by_card: dict[str, list[dict]],
    ability_smoke: dict,
) -> dict:
    card = catalog.cards[card_id]
    declared = coverage[card_id]
    failures: list[str] = []
    rules = catalog.rules.get(card_id)
    if card.get("type") not in KNOWN_CARD_TYPES:
        failures.append(f"type de carte inconnu : {card.get('type')!r}")
    if not card.get("name"):
        failures.append("nom absent")
    if rules is None:
        failures.append("règles compilées absentes")
    elif rules.get("type") != card.get("type"):
        failures.append("le type compilé diffère du catalogue")
    failures.extend(_compiled_ability_failures(card_id))
    smoke = ability_smoke.get(card_id) or {"abilities": 0, "carriers": 0, "failures": []}
    failures.extend(f"smoke capacité : {failure}" for failure in smoke["failures"])

    refs = list(declared.get("testRefs") or [])
    missing_refs = [ref for ref in refs if not (ROOT / ref).is_file()]
    if declared["status"] == "automated" and not refs:
        failures.append("statut automated sans référence de test")
    if missing_refs:
        failures.append(f"références de test absentes : {', '.join(missing_refs)}")

    if card_id in catalog.simple:
        failures.extend(sandbox.check_simple_card(catalog, card_id))

    generic = sandbox.generic_scenarios(catalog, card_id)
    written = written_by_card.get(card_id, [])
    generic_scripted = [scenario for scenario in generic if scenario.get("script")]
    written_scripted = [scenario for scenario in written if scenario.get("script")]
    steps = 0
    for scenario in generic:
        scenario_failures, count = _exercise_scenario(catalog, scenario, check_hand_mix=True)
        failures.extend(scenario_failures)
        steps += count
    for scenario in written:
        scenario_failures, count = _exercise_scenario(catalog, scenario, check_hand_mix=False)
        failures.extend(scenario_failures)
        steps += count

    if failures:
        level = "failed"
    elif declared["status"] == "manual":
        level = "manual"
    elif declared["status"] == "partial":
        level = "partial"
    elif written_scripted:
        level = "scenario"
    elif card_id in catalog.simple:
        level = "simple"
    elif smoke["abilities"]:
        level = "ability"
    elif declared["status"] == "automated":
        level = "static"
    else:
        level = "structural"

    return {
        "id": card_id,
        "collectionNumber": int(card.get("collectionNumber") or 0),
        "name": card.get("name") or card_id,
        "setName": card.get("setName") or "",
        "declaredStatus": declared["status"],
        "level": level,
        "passed": not failures,
        "explicitAbilities": len(catalog.abilities.get(card_id) or []),
        "smokedAbilities": smoke["abilities"],
        "smokedCarriers": smoke["carriers"],
        "genericScenarios": len(generic),
        "genericScriptedScenarios": len(generic_scripted),
        "writtenScriptedScenarios": len(written_scripted),
        "executedSteps": steps,
        "testRefs": refs,
        "failures": failures,
        **({"notes": declared["notes"]} if declared.get("notes") else {}),
    }


def build_report() -> dict:
    registry = automation_coverage.build_registry()
    coverage = registry["cards"]
    catalog = sandbox.Catalog(
        server_main.CARD_DATA,
        server_main.CARD_ABILITIES,
        server_main.CARD_RULES,
    )
    written_by_card: dict[str, list[dict]] = {}
    for scenario in sandbox.load_scenarios():
        written_by_card.setdefault(scenario["cardId"], []).append(scenario)

    smoke_report = card_ability_smoke.smoke_all()
    cards = [
        _audit_card(card_id, catalog, coverage, written_by_card, smoke_report["cards"])
        for card_id in catalog.order
    ]
    cards.sort(key=lambda entry: entry["collectionNumber"])
    levels = Counter(card["level"] for card in cards)
    declared_statuses = Counter(card["declaredStatus"] for card in cards)
    return {
        "schemaVersion": 1,
        "summary": {
            "catalogCards": len(cards),
            "explicitCards": sum(bool(card["explicitAbilities"]) for card in cards),
            "explicitAbilities": sum(card["explicitAbilities"] for card in cards),
            "smokedAbilities": sum(card["smokedAbilities"] for card in cards),
            "smokedCarriers": sum(card["smokedCarriers"] for card in cards),
            "passed": sum(card["passed"] for card in cards),
            "failed": sum(not card["passed"] for card in cards),
            "executedScripts": sum(
                card["genericScriptedScenarios"] + card["writtenScriptedScenarios"]
                for card in cards
            ),
            "executedSteps": sum(card["executedSteps"] for card in cards),
            "levels": {level: levels.get(level, 0) for level in LEVEL_LABELS},
            "declaredStatuses": dict(sorted(declared_statuses.items())),
        },
        "cards": cards,
    }


def serialized_json(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def _md(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def serialized_markdown(report: dict) -> str:
    summary = report["summary"]
    levels = summary["levels"]
    lines = [
        "# Rapport de certification des cartes KKO",
        "",
        "Ce rapport est généré par `py tools/card_certification.py --write`. Il sépare les tests",
        "comportementaux exécutables des contrôles structurels. Une preuve structurelle confirme",
        "que la carte, ses règles compilées, ses capacités, ses références de tests et ses états",
        "sandbox sont cohérents ; elle ne remplace pas encore un scénario dédié à son texte.",
        "",
        "## Résumé",
        "",
        "| Mesure | Résultat |",
        "| --- | ---: |",
        f"| Cartes du catalogue | {summary['catalogCards']} |",
        f"| Cartes sans échec mécanique | {summary['passed']} |",
        f"| Cartes en échec | {summary['failed']} |",
        f"| Capacités explicites | {summary['explicitAbilities']} |",
        f"| Capacités exécutées par le smoke test | {summary['smokedAbilities']} |",
        f"| Chemins de comportement exécutés | {summary['smokedCarriers']} |",
        f"| Scripts exécutés | {summary['executedScripts']} |",
        f"| Étapes de scripts exécutées | {summary['executedSteps']} |",
        f"| Scénarios comportementaux dédiés | {levels['scenario']} |",
        f"| Cartes simples exécutées de bout en bout | {levels['simple']} |",
        f"| Cartes dont toutes les capacités sont exécutées isolément | {levels['ability']} |",
        f"| Cartes à règles statiques exécutées | {levels['static']} |",
        f"| Preuve structurelle seulement | {levels['structural']} |",
        f"| Automatisation partielle | {levels['partial']} |",
        f"| Application manuelle | {levels['manual']} |",
        "",
        "## Interprétation",
        "",
        "- `scénario comportemental` : un scénario écrit envoie de vrais messages au serveur et vérifie le résultat.",
        "- `règles génériques exécutées` : tout le texte est composé de mots-clés génériques contrôlés et joués automatiquement.",
        "- `capacités exécutées isolément` : chaque résultat, effet continu, passif ou permission déclaré par la carte a traversé son chemin moteur dans un état riche.",
        "- `règles statiques exécutées` : la carte n'a pas de capacité déclarative ; ses états génériques et calculs de caractéristiques ont été exécutés.",
        "- `preuve structurelle seulement` : les contrôles passent, mais il manque encore un scénario dédié à la carte.",
        "- `partielle` ou `manuelle` : le registre documente une mécanique qui reste hors du moteur.",
        "",
        "## Détail par carte",
        "",
        "| Nº | Carte | Extension | Statut déclaré | Niveau de preuve | Capacités | Scripts | Étapes | Résultat |",
        "| ---: | --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for card in report["cards"]:
        scripts = card["genericScriptedScenarios"] + card["writtenScriptedScenarios"]
        result = "OK" if card["passed"] else "; ".join(card["failures"])
        lines.append(
            f"| {card['collectionNumber']} | {_md(card['name'])} | {_md(card['setName'])} | "
            f"{card['declaredStatus']} | {LEVEL_LABELS[card['level']]} | "
            f"{card['explicitAbilities']} | {scripts} | {card['executedSteps']} | {_md(result)} |"
        )
    lines.append("")
    return "\n".join(lines)


def _check_current(path: Path, expected: str) -> bool:
    return path.is_file() and path.read_text(encoding="utf-8") == expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="write JSON and Markdown reports")
    parser.add_argument("--check", action="store_true", help="fail when committed reports are stale")
    parser.add_argument(
        "--strict-scenarios",
        action="store_true",
        help="also fail while an automated card has no dedicated scenario",
    )
    args = parser.parse_args()

    report = build_report()
    json_text = serialized_json(report)
    markdown_text = serialized_markdown(report)
    if args.write:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_JSON.write_text(json_text, encoding="utf-8")
        OUTPUT_MARKDOWN.write_text(markdown_text, encoding="utf-8")
    if args.check:
        stale = []
        if not _check_current(OUTPUT_JSON, json_text):
            stale.append(str(OUTPUT_JSON.relative_to(ROOT)))
        if not _check_current(OUTPUT_MARKDOWN, markdown_text):
            stale.append(str(OUTPUT_MARKDOWN.relative_to(ROOT)))
        if stale:
            print("Rapports périmés : " + ", ".join(stale), file=sys.stderr)
            print("Exécuter `py tools/card_certification.py --write`.", file=sys.stderr)
            return 1

    summary = report["summary"]
    print(
        f"{summary['catalogCards']} cartes contrôlées, {summary['failed']} échec(s), "
        f"{summary['executedScripts']} script(s) et {summary['executedSteps']} étape(s) exécutés."
    )
    print(
        f"Preuves : {summary['levels']['scenario']} scénario(s) dédié(s), "
        f"{summary['levels']['simple']} carte(s) simple(s), "
        f"{summary['levels']['ability']} capacité(s) isolée(s), "
        f"{summary['levels']['static']} statique(s), "
        f"{summary['levels']['structural']} structurelle(s), "
        f"{summary['levels']['partial']} partielle(s), {summary['levels']['manual']} manuelle(s)."
    )
    if summary["failed"]:
        return 1
    scenario_debt = sum(
        summary["levels"][level] for level in ("ability", "static", "structural")
    )
    if args.strict_scenarios and scenario_debt:
        print(
            f"{scenario_debt} carte(s) automatisée(s) sans scénario dédié.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
