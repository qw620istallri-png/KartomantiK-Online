"""Run KKO card scenarios in batches of ten through server, player and client contracts.

The server layer exercises every declarative behavior carrier.  Player actions
are declared through ``main.handle_message`` with legal phases, targets, costs
and two player views.  The browser layer is supplied by card_browser_batches.mjs
and proves that the shipped sandbox UI can load and render each card.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
for path in (ROOT / "server", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import automation_coverage
import card_ability_smoke as smoke
import main
import sandbox
from session import ADVANCED_PHASES


REPORT_DIR = ROOT / "reports" / "card-scenario-batches"
SUMMARY_JSON = ROOT / "reports" / "card-scenario-batches.json"
SUMMARY_MD = ROOT / "reports" / "card-scenario-batches.md"
BROWSER_JSON = ROOT / "reports" / "card-browser-results.json"
MANIFEST_JSON = ROOT / "reports" / "card-scenario-manifest.json"
BATCH_SIZE = 10
TEMPERAMENTS = [
    "phlegmatic", "choleric", "melancholic", "vitreous",
    "capricious", "hollow", "transcendent",
]
CATALOG = sandbox.Catalog(main.CARD_DATA, main.CARD_ABILITIES, main.CARD_RULES)


class CaptureSocket:
    def __init__(self):
        self.messages = []

    async def send(self, raw):
        self.messages.append(json.loads(raw))

    @property
    def errors(self):
        return [entry.get("message") for entry in self.messages if entry.get("type") == "error"]


def _card_type(contract):
    return contract.get("cardType") or next(iter(contract.get("cardTypes") or []), "manifestation")


def _synthetic_rule(card_type, power=1, temperament="phlegmatic"):
    result = {"type": card_type}
    if card_type == "manifestation":
        result.update({"power": power, "temperaments": [temperament]})
    else:
        result.update({"cost": 1, "powerCost": "{G}", "temperaments": [temperament]})
    return result


def _add_zone_target(session, contract, index, actor):
    zone = next(iter(contract.get("zones") or []), "graveyard")
    container = "p2" if contract.get("container") == "opponent" else actor
    owner_rule = contract.get("owner")
    owner = "p2" if owner_rule == "opponent" else actor
    if container == actor and contract.get("container") == "opponent":
        container = "p2"
    card_type = _card_type(contract)
    card_id = f"scenario-zone-{index}"
    session.card_rules[card_id] = _synthetic_rule(card_type)
    session.card_points[card_id] = 1
    session.players[container]["zones"][zone].append(card_id)
    session.players[container]["zoneOwners"][zone][card_id] = owner
    if contract.get("enteredThisTurn"):
        session.rules_engine.setdefault("zoneEntryTurns", {})[
            f"{container}:{zone}:{card_id}"
        ] = session.phase_tracker["turn"]
    reasons = list(contract.get("limboReasons") or [])
    if reasons:
        session.rules_engine.setdefault("recentLimboEntries", []).append({
            "ownerId": owner, "cardId": card_id, "reason": reasons[0],
            "turn": session.phase_tracker["turn"],
        })
    return {
        "kind": "zone_card", "containerId": container, "zone": zone,
        "cardId": card_id, "ownerId": owner,
    }


def _add_field_target(session, contract, index, actor, source_item):
    if contract.get("sourceOnly"):
        return {
            "kind": "card", "itemId": source_item["id"],
            "cardId": source_item["cardId"], "ownerId": source_item["ownerId"],
        }
    card_type = _card_type(contract)
    field_zones = contract.get("fieldZonesByType") or {}
    zone = contract.get("fieldZone") or next(iter(field_zones.get(card_type) or []), "confrontation")
    controller = "p2" if contract.get("controller") == "opponent" else actor
    owner = "p2" if contract.get("owner") == "opponent" else actor
    card_id = f"scenario-field-{index}"
    power = max(int(contract.get("minPower") or 1), 2)
    if isinstance(contract.get("maxPower"), (int, float)):
        power = min(power, int(contract["maxPower"]))
    session.card_rules[card_id] = _synthetic_rule(card_type, power=power)
    session.card_points[card_id] = 1
    if card_type == "manifestation":
        session.manifestation_ids.add(card_id)
    counters = {}
    if contract.get("counter"):
        counters[str(contract["counter"])] = max(1, int(contract.get("minCounters") or 1))
    item = smoke.field_item(
        f"scenario-field-item-{index}", owner, card_id, zone,
        controllerId=controller, counters=counters,
        isSupport=bool(contract.get("supportOnly")),
        rotation=90 if contract.get("exhaustedOnly") else 0,
    )
    if contract.get("enteredInterzoneThisTurn"):
        item["interzoneTurn"] = session.phase_tracker["turn"]
    session.battlefield.append(item)
    if contract.get("firstManifestationOnly"):
        session.rules_engine["firstManifestationItemIds"][controller] = item["id"]
    outcome = contract.get("confrontationOutcome")
    if outcome in {"won", "lost"}:
        result = {
            "turn": session.phase_tracker["turn"],
            "winnerId": controller if outcome == "won" else ("p2" if controller == actor else actor),
            "loserId": controller if outcome == "lost" else ("p2" if controller == actor else actor),
            "participantItemIds": [item["id"]],
        }
        session.rules_engine["confrontationResult"] = result
    return {"kind": "card", "itemId": item["id"], "cardId": card_id, "ownerId": owner}


def _stack_target(session, contract, stack_action, actor, source_item):
    kind = contract.get("kind") or "stack_item"
    required_type = _card_type(contract)
    stack_card = "scenario-stack-card"
    session.card_rules[stack_card] = _synthetic_rule(required_type)
    stack_action["source"] = {"cardId": stack_card, "ownerId": actor, "zone": "hand"}
    stack_action["controllerId"] = actor if contract.get("controller") == "self" else "p2"
    stack_action["targets"] = [{
        "kind": "card", "itemId": "own-con", "cardId": "own-man", "ownerId": actor,
    }]
    if kind == "stack_action":
        stack_action["kind"] = "play_card"
        stack_action["sourceOnStack"] = True
    elif kind == "stack_effect":
        stack_action["kind"] = "activated_effect"
        stack_action.pop("sourceOnStack", None)
    if contract.get("effectTemperamentChosenBySource"):
        source_item["chosenTemperament"] = "phlegmatic"
        session.card_rules[stack_card]["temperaments"] = ["phlegmatic"]
    return {
        "kind": kind, "actionId": stack_action["id"], "cardId": stack_card,
        "controllerId": stack_action["controllerId"],
    }


def _build_targets(session, ability, stack_action, actor, source_item):
    contracts = list(ability.get("targetGroups") or [])
    if not contracts and ability.get("targets"):
        raw = ability["targets"]
        contracts = list(raw.get("groups") or []) or [raw]
    targets = []
    index = 0
    for contract in contracts:
        minimum = int(contract.get("min") or 0)
        count = minimum
        if not count and int(contract.get("max") or 0) and contract.get("kind") != "player":
            count = 1
        for _ in range(count):
            kind = contract.get("kind") or "card"
            if kind == "player":
                target = {"kind": "player", "playerId": "p2" if contract.get("controller") != "self" else actor}
            elif kind == "zone_card" or (
                kind == "card" and set(contract.get("zones") or [])
                and "battlefield" not in set(contract.get("zones") or [])
            ):
                target = _add_zone_target(session, contract, index, actor)
            elif kind in {"stack_action", "stack_effect", "stack_item"}:
                target = _stack_target(session, contract, stack_action, actor, source_item)
            elif kind == "card_or_stack_action":
                target = _add_field_target(session, contract, index, actor, source_item)
            else:
                target = _add_field_target(session, contract, index, actor, source_item)
            targets.append(target)
            index += 1
    return targets


def prepare_action(card_id, ability):
    session, source_item, stack_action = smoke.make_session(card_id, ability)
    actor = "p2" if ability.get("opponentOnly") else "p1"
    session.rules_engine["priorityPlayerId"] = actor
    card_rules = session.card_rules[card_id]
    phase = next(iter(ability.get("phaseIds") or []), None)
    if not phase:
        phase = next(iter(card_rules.get("playPhases") or []), None)
    if not phase and ability.get("action") == "play_card" and card_rules.get("playBeforeRevelation"):
        phase = "confrontation_before_revelation"
    if not phase:
        phase = "end_actions" if card_rules.get("type") == "persistent_will" and ability.get("action") == "play_card" else "confrontation_reaction"
    session.phase_tracker["index"] = ADVANCED_PHASES.index(phase)

    source_zone = "hand" if ability.get("action") == "play_card" else next(iter(ability.get("sourceZones") or []), "battlefield")
    source_container = actor
    if source_zone == "receptacle":
        source_container = "p1" if actor == "p2" else "p2"
    if source_zone != "battlefield":
        session.battlefield = [entry for entry in session.battlefield if entry["id"] != "source"]
        session.players[source_container]["zones"][source_zone].insert(0, card_id)
        session.players[source_container]["zoneOwners"][source_zone][card_id] = actor
    source = {"cardId": card_id, "ownerId": actor, "containerId": source_container, "zone": source_zone}
    if source_zone == "battlefield":
        source["itemId"] = "source"
        if not ability.get("opponentOnly"):
            source_item["ownerId"] = actor
            source_item["controllerId"] = actor

    for counter in (
        "Petal", "Atavic", "Fatigue", "Burn", "Union", "Control", "Coil",
        "Violence", "Berry", "Grudge", "Tear", "Bone", "Banner", "Lucore",
        "Flame", "Gem", "Flower", "Abstraction",
    ):
        source_item.setdefault("counters", {})[counter] = 20
    gate = ability.get("requireSourceCounter") or {}
    if gate:
        source_item["counters"][gate.get("name")] = int(gate.get("min") or 0)
    if ability.get("sacrificeTokenCreatedBySource"):
        session.battlefield.append({
            "id": "source-token", "ownerId": actor, "controllerId": actor,
            "cardId": None, "isTokenCard": True, "createdByItemId": "source",
            "temperament": "phlegmatic", "power": 1, "faceUp": True,
            "fieldZone": "confrontation", "counters": {}, "x": 0, "y": 0,
            "rotation": 0,
        })
    for owner in ("p1", "p2"):
        for index, temperament in enumerate(TEMPERAMENTS):
            session.tokens.append({
                "id": f"scenario-essence-{owner}-{index}", "ownerId": owner,
                "isEssence": True, "isNeutralCounter": False,
                "temperament": temperament, "counters": {"essence": 100},
                "x": 0, "y": 0,
            })
    for index in range(max(0, int(ability.get("requireHandManifestations") or 0))):
        filler = f"scenario-hand-man-{index}"
        session.card_rules[filler] = _synthetic_rule("manifestation")
        session.manifestation_ids.add(filler)
        session.players[actor]["zones"]["hand"].append(filler)
        session.players[actor]["zoneOwners"]["hand"][filler] = actor

    targets = _build_targets(session, ability, stack_action, actor, source_item)
    if not any(target.get("kind", "").startswith("stack") for target in targets):
        session.rules_engine["actionStack"] = []
    if ability.get("condition") == "controller_lost_confrontation":
        session.rules_engine["confrontationResult"] = {
            "turn": session.phase_tracker["turn"], "winnerId": "p2" if actor == "p1" else "p1",
            "loserId": actor, "participantItemIds": ["own-con", "opp-con"],
        }
    if ability.get("condition") == "last_opponent_support_low_power":
        support = session.find_battlefield_item("opp-support")
        session.card_rules[support["cardId"]]["power"] = 2
        session.rules_engine["supportEntries"] = [{
            "itemId": support["id"], "controllerId": "p2" if actor == "p1" else "p1",
        }]
    extra_cost = ability.get("additionalCost")
    cost_card_id = "hand-will" if extra_cost == "discard_hand_will" else "own-man-2"
    if cost_card_id not in session.players[actor]["zones"]["hand"]:
        session.players[actor]["zones"]["hand"].append(cost_card_id)
        session.players[actor]["zoneOwners"]["hand"][cost_card_id] = actor
    return session, actor, source, targets, cost_card_id


def _view_failures(session):
    failures = []
    try:
        own = session.serialize_for("p1", "player")
        opponent = session.serialize_for("p2", "player")
        json.dumps(own)
        json.dumps(opponent)
        own_hand = ((own.get("players") or {}).get("p1") or {}).get("zones", {}).get("hand", {})
        opp_hand = ((opponent.get("players") or {}).get("p1") or {}).get("zones", {}).get("hand", {})
        if isinstance(own_hand, dict) and "cards" not in own_hand:
            failures.append("la vue du joueur masque sa propre main")
        if isinstance(opp_hand, dict):
            exposed = [card for card in (opp_hand.get("cards") or []) if card]
            if exposed:
                failures.append("la vue adverse révèle une main privée")
    except Exception as exc:
        failures.append(f"sérialisation des deux joueurs impossible : {type(exc).__name__}: {exc}")
    return failures


async def _send_action(session, actor, message):
    socket = CaptureSocket()
    info = {"session": session, "playerId": actor, "role": "player", "isObserver": False}
    before_ids = {
        entry.get("id") for entry in session.rules_engine.get("actionStack") or []
    }
    await main.handle_message(socket, info, message)
    if socket.errors:
        return "; ".join(socket.errors), 1
    messages = 1
    declared_ids = {
        entry.get("id") for entry in session.rules_engine.get("actionStack") or []
    } - before_ids
    if declared_ids:
        for _ in range(6):
            live_ids = {
                entry.get("id") for entry in session.rules_engine.get("actionStack") or []
            }
            if not (declared_ids & live_ids) or session.rules_engine.get("pendingChoice"):
                break
            current = session.rules_engine.get("priorityPlayerId")
            pass_socket = CaptureSocket()
            await main.handle_message(
                pass_socket,
                {"session": session, "playerId": current, "role": "player", "isObserver": False},
                {"type": "pass_priority"},
            )
            messages += 1
            if pass_socket.errors:
                return "; ".join(pass_socket.errors), messages
    return None, messages


def _run_player_action(card_id, ability):
    if (ability.get("result") or {}).get("kind") == "first_manifestation_trap":
        session, _source, _stack = smoke.make_session(card_id, ability)
        session.battlefield = [entry for entry in session.battlefield if entry["id"] != "source"]
        session.players["p1"]["zones"]["hand"].append(card_id)
        session.players["p1"]["zoneOwners"]["hand"][card_id] = "p1"
        session.rules_engine["firstManifestationComplete"] = False
        session.rules_engine["firstManifestationTriggersQueued"] = False
        session.rules_engine["firstManifestationItemIds"] = {}
        session.rules_engine["firstManifestationValidatedPlayerIds"] = []
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_choose")
        before = _view_failures(session)
        error, messages = asyncio.run(_send_action(session, "p1", {
            "type": "play_first_manifestation_trap", "cardId": card_id,
        }))
        return before + ([error] if error else []) + _view_failures(session), messages

    session, actor, source, targets, cost_card_id = prepare_action(card_id, ability)
    failures = _view_failures(session)
    message = {
        "type": "declare_rules_action", "label": ability.get("id") or card_id,
        "kind": ability.get("action") or "activated_effect", "source": source,
        "targets": targets, "abilityId": ability.get("id"), "paymentCardIds": [],
        "extraEssenceCount": 1 if ability.get("optionalExtraEssence") else 0,
        "costCardId": cost_card_id,
        "asSupport": bool(
            session.card_rules[card_id].get("type") == "manifestation"
            and ability.get("action") == "play_card"
        ),
        "placement": {"x": 0, "y": 0},
    }
    error, messages = asyncio.run(_send_action(session, actor, message))
    if error:
        failures.append(f"action joueur {ability.get('id')}: {error}")
    failures.extend(_view_failures(session))
    return failures, messages


def _run_generic(card_id):
    failures = []
    scripts = steps = 0
    for scenario in sandbox.generic_scenarios(CATALOG, card_id):
        session = main.new_sandbox_session()
        try:
            sandbox.apply_scenario(session, CATALOG, scenario, "p1")
            failures.extend(_view_failures(session))
            if scenario.get("script"):
                scripts += 1
                reports = asyncio.run(sandbox.run_script(
                    session, main.handle_message, main.auto_advance_rules_phases,
                    main.AUTO_PASS_MESSAGE_TYPES,
                ))
                steps += len(reports)
                failures.extend(
                    f"{scenario['id']} / {entry.get('label')}: {entry.get('error')}"
                    for entry in reports if not entry.get("ok")
                )
                failures.extend(_view_failures(session))
        except Exception as exc:
            failures.append(f"{scenario['id']}: {type(exc).__name__}: {exc}")
    return failures, scripts, steps


def _browser_results():
    if not BROWSER_JSON.is_file():
        return {}
    try:
        payload = json.loads(BROWSER_JSON.read_text(encoding="utf-8"))
        return {entry["cardId"]: entry for entry in payload.get("cards") or []}
    except (OSError, ValueError, KeyError):
        return {}


def run_card(card_id, browser, coverage):
    card = CATALOG.cards[card_id]
    abilities = list(main.CARD_ABILITIES.get(card_id) or [])
    smoke_report = smoke.smoke_card(card_id)
    server_failures = list(smoke_report["failures"])
    generic_failures, scripts, steps = _run_generic(card_id)
    server_failures.extend(generic_failures)
    player_failures = []
    messages = 0
    actionable = 0
    for ability in abilities:
        if ability.get("trigger") or ability.get("passiveEffect") or ability.get("playPermission"):
            continue
        actionable += 1
        failures, count = _run_player_action(card_id, ability)
        player_failures.extend(failures)
        messages += count
    if not actionable:
        # Triggered, passive and vanilla cards still cross both recipient serializers.
        session, _source, _stack = smoke.make_session(card_id, abilities[0] if abilities else {})
        player_failures.extend(_view_failures(session))
    browser_entry = browser.get(card_id)
    client_failures = []
    if not browser_entry:
        client_failures.append("scénario navigateur non exécuté")
    elif not browser_entry.get("ok"):
        client_failures.extend(browser_entry.get("failures") or ["échec navigateur sans détail"])
    declared = coverage[card_id]
    manual = declared.get("status") in {"manual", "partial"}
    failures = server_failures + player_failures + client_failures
    return {
        "cardId": card_id,
        "number": card.get("collectionNumber") or card.get("number"),
        "name": card.get("name"),
        "type": card.get("type"),
        "declaredStatus": declared.get("status"),
        "manualReview": manual,
        "server": {
            "ok": not server_failures, "abilities": len(abilities),
            "carriers": smoke_report["carriers"], "genericScripts": scripts,
            "genericSteps": steps, "failures": server_failures,
        },
        "players": {
            "ok": not player_failures, "actionableAbilities": actionable,
            "messages": messages, "views": 2, "failures": player_failures,
        },
        "client": {
            "ok": not client_failures, "scenarioId": (browser_entry or {}).get("scenarioId"),
            "renderedIn": (browser_entry or {}).get("renderedIn"),
            "failures": client_failures,
        },
        "ok": not failures,
        "failures": failures,
    }


def build_report():
    coverage = automation_coverage.build_registry()["cards"]
    browser = _browser_results()
    cards = [run_card(card_id, browser, coverage) for card_id in CATALOG.order]
    batches = []
    for offset in range(0, len(cards), BATCH_SIZE):
        entries = cards[offset:offset + BATCH_SIZE]
        batch_no = offset // BATCH_SIZE + 1
        batches.append({
            "batch": batch_no, "from": offset + 1, "to": offset + len(entries),
            "ok": all(entry["ok"] for entry in entries),
            "manualReview": sum(entry["manualReview"] for entry in entries),
            "cards": entries,
        })
    summary = {
        "cards": len(cards), "batches": len(batches),
        "passed": sum(entry["ok"] for entry in cards),
        "failed": sum(not entry["ok"] for entry in cards),
        "manualReview": sum(entry["manualReview"] for entry in cards),
        "serverPassed": sum(entry["server"]["ok"] for entry in cards),
        "playerPassed": sum(entry["players"]["ok"] for entry in cards),
        "clientPassed": sum(entry["client"]["ok"] for entry in cards),
        "abilities": sum(entry["server"]["abilities"] for entry in cards),
        "carriers": sum(entry["server"]["carriers"] for entry in cards),
        "playerActions": sum(entry["players"]["actionableAbilities"] for entry in cards),
        "playerMessages": sum(entry["players"]["messages"] for entry in cards),
        "genericSteps": sum(entry["server"]["genericSteps"] for entry in cards),
    }
    return {"summary": summary, "batches": batches}


def _batch_markdown(batch):
    lines = [
        f"# Lot {batch['batch']:02d} — cartes {batch['from']} à {batch['to']}", "",
        f"Verdict : **{'PASS' if batch['ok'] else 'FAIL'}** · {batch['manualReview']} contrôle(s) manuel(s) conservé(s).", "",
        "| # | Carte | Serveur | Joueurs | Client | Statut |", "|---:|---|---|---|---|---|",
    ]
    for entry in batch["cards"]:
        mark = lambda ok: "✓" if ok else "✗"
        status = "manuel" if entry["manualReview"] else ("PASS" if entry["ok"] else "FAIL")
        lines.append(
            f"| {entry['number'] or ''} | {entry['name']} | {mark(entry['server']['ok'])} "
            f"({entry['server']['abilities']} cap.) | {mark(entry['players']['ok'])} "
            f"({entry['players']['actionableAbilities']} actions) | {mark(entry['client']['ok'])} | {status} |"
        )
    failures = [entry for entry in batch["cards"] if entry["failures"]]
    if failures:
        lines += ["", "## Écarts", ""]
        for entry in failures:
            lines.append(f"- **{entry['name']}** : " + " ; ".join(entry["failures"]))
    lines += ["", "## Parcours vérifié", "",
              "1. Préparer deux joueurs, la phase, les zones, la Pile, les cibles et les coûts.",
              "2. Déclarer chaque action volontaire par le gestionnaire de messages du serveur.",
              "3. Résoudre la Pile ou exposer le choix obligatoire au joueur concerné.",
              "4. Sérialiser l’état pour les deux sièges et contrôler la confidentialité des mains.",
              "5. Charger la carte dans le vrai bac à sable Chromium et vérifier son rendu.", ""]
    return "\n".join(lines)


def _summary_markdown(report):
    summary = report["summary"]
    lines = [
        "# Scénarios réels des cartes KKO — lots de 10", "",
        f"**{summary['passed']}/{summary['cards']} cartes passent les trois couches** ; "
        f"{summary['failed']} échec(s), {summary['manualReview']} contrôle(s) manuel(s) conservé(s).", "",
        f"- Serveur : {summary['serverPassed']}/{summary['cards']}",
        f"- Vues et actions joueurs : {summary['playerPassed']}/{summary['cards']}",
        f"- Client Chromium : {summary['clientPassed']}/{summary['cards']}",
        f"- Capacités : {summary['abilities']} · chemins : {summary['carriers']}",
        f"- Actions volontaires déclarées : {summary['playerActions']} · messages : {summary['playerMessages']}",
        f"- Étapes génériques supplémentaires : {summary['genericSteps']}", "",
        "| Lot | Cartes | Verdict | Manuel | Rapport |", "|---:|---:|---|---:|---|",
    ]
    for batch in report["batches"]:
        lines.append(
            f"| {batch['batch']:02d} | {batch['from']}–{batch['to']} | "
            f"{'PASS' if batch['ok'] else 'FAIL'} | {batch['manualReview']} | "
            f"[lot-{batch['batch']:02d}.md](card-scenario-batches/lot-{batch['batch']:02d}.md) |"
        )
    return "\n".join(lines) + "\n"


def _manifest():
    return {
        "cards": [
            {
                "cardId": card_id, "name": CATALOG.cards[card_id].get("name"),
                "number": CATALOG.cards[card_id].get("collectionNumber") or CATALOG.cards[card_id].get("number"),
                "batch": index // BATCH_SIZE + 1,
            }
            for index, card_id in enumerate(CATALOG.order)
        ]
    }


def write(report):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SUMMARY_MD.write_text(_summary_markdown(report), encoding="utf-8")
    MANIFEST_JSON.write_text(json.dumps(_manifest(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for batch in report["batches"]:
        (REPORT_DIR / f"lot-{batch['batch']:02d}.md").write_text(_batch_markdown(batch), encoding="utf-8")


def main_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report()
    if args.check:
        expected = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if not SUMMARY_JSON.is_file() or SUMMARY_JSON.read_text(encoding="utf-8") != expected:
            print("Le rapport des lots n'est pas à jour.")
            return 1
    if args.write or not args.check:
        write(report)
    print(report["summary"])
    return 1 if report["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main_cli())
