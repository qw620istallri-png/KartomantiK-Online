"""Generate or validate the assisted-rules coverage registry."""
import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = ROOT / "server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import main as server_main


PUBLIC_DIR = ROOT / "public"
OUTPUT_PATH = PUBLIC_DIR / "automation-coverage.json"
OVERRIDES_PATH = PUBLIC_DIR / "automation-coverage-overrides.json"
ALLOWED_STATUSES = {"manual", "generic", "partial", "automated"}


def generic_mechanics(rule):
    mechanics = []
    if not rule.get("canBeFirstManifestation", True):
        mechanics.append("first-restriction")
    if rule.get("supportFromHand"):
        mechanics.append("support-from-hand")
    if rule.get("supportFromInterzone"):
        mechanics.append("support-from-interzone")
    if rule.get("supportFromHandCondition"):
        mechanics.append("conditional-support")
    if rule.get("supportWinDestination"):
        mechanics.append(f'support-win:{rule["supportWinDestination"]}')
    if rule.get("supportWinEffect"):
        mechanics.append(
            f'support-win-effect:{rule["supportWinEffect"].get("kind")}'
        )
    if rule.get("continuousPowerRules"):
        mechanics.append("continuous-power")
    for keyword in ("adamant", "float", "persist"):
        if rule.get(keyword):
            mechanics.append(keyword)
    if rule.get("tributeDestination") != "graveyard":
        mechanics.append(f'tribute-destination:{rule["tributeDestination"]}')
    if set(rule.get("tributeTemperaments") or []) != set(rule.get("temperaments") or []):
        mechanics.append("alternate-tribute-temperament")
    if rule.get("suspensionThresholds"):
        mechanics.append("suspension-thresholds")
    return mechanics


def ability_mechanics(ability):
    mechanics = []
    trigger = ability.get("trigger") or {}
    result = ability.get("result") or {}
    ongoing = ability.get("ongoingEffect") or {}
    permission = ability.get("playPermission") or {}
    passive = ability.get("passiveEffect") or {}
    if trigger.get("event"):
        mechanics.append(f'trigger:{trigger["event"]}')
    if result.get("kind"):
        mechanics.append(f'result:{result["kind"]}')
    if ongoing.get("kind"):
        mechanics.append(f'ongoing:{ongoing["kind"]}')
    if permission:
        mechanics.append("play-permission")
    if passive.get("kind"):
        mechanics.append(f'passive:{passive["kind"]}')
    target_contracts = [
        ability.get("targets") or {},
        *(ability.get("targetGroups") or []),
    ]
    for target in target_contracts:
        if target.get("kind"):
            mechanics.append(f'target:{target["kind"]}')
        if target.get("counter"):
            mechanics.append("target:counter")
    for cost in (
        "tribute", "exhaustSource", "sacrificeSource",
        "removeAllCountersFromSource",
    ):
        if ability.get(cost):
            mechanics.append(f'cost:{cost}')
    if ability.get("condition"):
        mechanics.append(f'condition:{ability["condition"]}')
    if ability.get("phaseIds"):
        mechanics.append("phase-window")
    if ability.get("anyPlayer"):
        mechanics.append("activation:any-player")
    return mechanics


def load_overrides():
    if not OVERRIDES_PATH.exists():
        return {"schemaVersion": 1, "cards": {}}
    value = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    if value.get("schemaVersion") != 1 or not isinstance(value.get("cards"), dict):
        raise ValueError("automation-coverage-overrides.json has an invalid schema.")
    return value


def build_registry():
    overrides = load_overrides()["cards"]
    cards = {}
    counts = {status: 0 for status in sorted(ALLOWED_STATUSES)}
    for card in sorted(
        server_main.CARD_DATA,
        key=lambda entry: int(entry.get("collectionNumber") or 0),
    ):
        card_id = card["id"]
        abilities = list(server_main.CARD_ABILITIES.get(card_id) or [])
        mechanics = generic_mechanics(server_main.CARD_RULES[card_id])
        for ability in abilities:
            mechanics.extend(ability_mechanics(ability))
        mechanics = sorted(set(mechanics))
        status = "partial" if abilities else "generic" if mechanics else "manual"
        override = overrides.get(card_id) or {}
        if override.get("status"):
            if override["status"] not in ALLOWED_STATUSES:
                raise ValueError(f"Unknown coverage status for {card_id}.")
            status = override["status"]
        entry = {
            "collectionNumber": int(card.get("collectionNumber") or 0),
            "name": card.get("name") or card_id,
            "setName": card.get("setName") or "",
            "status": status,
            "abilityIds": [
                str(ability.get("id") or "") for ability in abilities
                if ability.get("id")
            ],
            "mechanics": mechanics,
            "testRefs": list(override.get("testRefs") or []),
        }
        if override.get("notes"):
            entry["notes"] = str(override["notes"])
        cards[card_id] = entry
        counts[status] += 1
    return {
        "schemaVersion": 1,
        "summary": {
            "catalogCards": len(server_main.CARD_DATA),
            "explicitCards": len(server_main.CARD_ABILITIES),
            "explicitAbilities": sum(
                len(abilities)
                for abilities in server_main.CARD_ABILITIES.values()
            ),
            "statuses": counts,
        },
        "cards": cards,
    }


def serialized_registry():
    return json.dumps(build_registry(), ensure_ascii=False, indent=2) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true",
        help="Fail if the generated registry differs from the committed file.",
    )
    parser.add_argument(
        "--write", action="store_true",
        help="Write the generated registry.",
    )
    args = parser.parse_args()
    generated = serialized_registry()
    if args.check:
        current = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else ""
        if current != generated:
            print(
                "automation-coverage.json is stale; run "
                "`py tools/automation_coverage.py --write`.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        return
    if args.write or not args.check:
        OUTPUT_PATH.write_text(generated, encoding="utf-8")


if __name__ == "__main__":
    main()
