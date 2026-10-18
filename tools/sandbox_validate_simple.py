"""Validate in the card sandbox every card that is only keywords (or no text at all).

A card qualifies when it has no ability of its own and every printed line is a
keyword the engine handles generically (Support, Float, First Manifestation
restriction, tribute variants...): see sandbox.SIMPLE_LINES. For each one this
checks the compiled rules flags against the printed lines, plays every scripted
sandbox scenario of the card, and records the verdict in sandbox/validation.json
with "auto": true. A verdict written by a person is never overwritten.

    python tools/sandbox_validate_simple.py          # check and write
    python tools/sandbox_validate_simple.py --check  # check only, exit 1 on a failure
"""
import argparse
import asyncio
import os
import sys

SERVER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server"))
sys.path.insert(0, SERVER_DIR)

import main  # noqa: E402
import sandbox  # noqa: E402
from session import Session  # noqa: E402


def play(catalog, scenario):
    session = Session(
        card_points=main.CARD_POINTS, card_labels=main.CARD_LABELS,
        manifestation_ids=main.CARD_MANIFESTATION_IDS, card_rules=main.CARD_RULES, rules_beta=True,
    )
    sandbox.apply_scenario(session, catalog, scenario, "tester")
    return asyncio.run(sandbox.run_script(
        session, main.handle_message, main.auto_advance_rules_phases, main.AUTO_PASS_MESSAGE_TYPES,
    ))


def audit_simple_card(catalog, card_id):
    """(failures, scripted scenario ids) for one keyword-only card."""
    failures = sandbox.check_simple_card(catalog, card_id)
    scripted = []
    for scenario in sandbox.generic_scenarios(catalog, card_id):
        if not scenario.get("script"):
            continue
        scripted.append(scenario["id"])
        for report in play(catalog, scenario):
            if not report["ok"]:
                failures.append(f"{scenario['title']} / {report['label']} : {report['error']}")
    return failures, scripted


def main_cli():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="only check, write nothing")
    args = parser.parse_args()
    catalog = main.SANDBOX_CATALOG
    validation = sandbox.load_validation()
    written = kept = 0
    failed = []
    for card_id in catalog.order:
        if card_id not in catalog.simple:
            continue
        name = catalog.cards[card_id]["name"]
        failures, scripted = audit_simple_card(catalog, card_id)
        if failures:
            failed.append((name, failures))
            continue
        existing = validation.get(card_id)
        if existing and not existing.get("auto"):
            kept += 1
            continue
        label = sandbox.simple_label(catalog.simple[card_id])
        note = f"Auto : {label}. Règles compilées conformes au texte, {len(scripted)} script(s) joué(s) sans erreur."
        validation[card_id] = sandbox.validation_entry("ok", note, scripted[0] if scripted else None, auto=True)
        written += 1
    for name, failures in failed:
        print(f"ÉCHEC {name}")
        for failure in failures:
            print(f"  - {failure}")
    print(f"{len(catalog.simple)} cartes simples : {written} validées automatiquement, "
          f"{kept} déjà jugées à la main, {len(failed)} en échec.")
    if not args.check:
        sandbox.write_validation(validation)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main_cli())
