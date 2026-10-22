"""Execute every declarative card ability against an isolated rich game state.

This is a smoke harness, not a replacement for a hand-authored rules oracle. It
does make each result dispatcher, ongoing-effect builder, passive integration
surface, and conditional play-permission path execute with the shipped card
definition instead of a copied fixture.
"""

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "server")]
import main
from session import Session, ADVANCED_PHASES


def field_item(item_id, owner, card, zone="confrontation", **extra):
    return {"id": item_id, "ownerId": owner, "controllerId": owner,
            "cardId": card, "faceUp": True, "fieldZone": zone,
            "counters": {"power": 3, "Atavic": 3, "Petal": 3, "Fatigue": 12},
            "x": 0, "y": 0, "rotation": 0, **extra}


def make_session(card_id, ability):
    rules = copy.deepcopy(main.CARD_RULES)
    synthetic = {
        "own-man": {"type": "manifestation", "power": 3, "temperaments": ["phlegmatic"]},
        "own-man-2": {"type": "manifestation", "power": 2, "temperaments": ["choleric"]},
        "opp-man": {"type": "manifestation", "power": 3, "temperaments": ["melancholic"]},
        "opp-man-2": {"type": "manifestation", "power": 2, "temperaments": ["vitreous"]},
        "own-will": {"type": "persistent_will", "cost": 1, "powerCost": "{G}"},
        "opp-will": {"type": "persistent_will", "cost": 1, "powerCost": "{P}"},
        "hand-will": {"type": "ephemeral_will", "cost": 1, "powerCost": "{G}"},
        "deck-man": {"type": "manifestation", "power": 4, "temperaments": ["phlegmatic"]},
        "grave-man": {"type": "manifestation", "power": 2, "temperaments": ["choleric"]},
    }
    rules.update(synthetic)
    session = Session(card_points={key: 1 for key in rules},
                      manifestation_ids={key for key, value in rules.items() if value.get("type") == "manifestation"},
                      card_rules=rules, rules_beta=True)
    p1 = session.get_or_create_player("p1", "P1", seat=0)
    p2 = session.get_or_create_player("p2", "P2", seat=1)
    for player in (p1, p2):
        player["score"] = 50
        player["essences"] = {"phlegmatic": 10, "choleric": 10, "melancholic": 10,
                              "vitreous": 10, "capricious": 10, "hollow": 10, "transcendent": 10}
    def put(player, zone, cards, owners=None):
        player["zones"][zone] = list(cards)
        player["zoneOwners"][zone] = {card: (owners or player["id"]) for card in cards}
    put(p1, "hand", ["own-man-2", "hand-will"])
    put(p2, "hand", ["opp-man-2"])
    put(p1, "deck", ["deck-man", "own-man"])
    put(p2, "deck", ["opp-man", "opp-man-2"])
    put(p1, "graveyard", ["grave-man"])
    put(p2, "graveyard", ["opp-will"])
    put(p1, "receptacle", ["opp-man"], owners="p2")
    put(p2, "receptacle", ["own-man"], owners="p1")
    put(p1, "exile", [])
    put(p2, "exile", [])
    source_zone = ability.get("sourceFieldZone") or "confrontation"
    source = field_item("source", "p1", card_id, source_zone)
    if rules[card_id].get("type") != "manifestation":
        source["fieldZone"] = "field"
    session.battlefield = [
        source,
        field_item("own-con", "p1", "own-man", "confrontation"),
        field_item("own-support", "p1", "own-man-2", "confrontation", isSupport=True),
        field_item("own-inter", "p1", "grave-man", "interzone"),
        field_item("own-will-field", "p1", "own-will", "field"),
        field_item("opp-con", "p2", "opp-man", "confrontation"),
        field_item("opp-support", "p2", "opp-man-2", "confrontation", isSupport=True),
        field_item("opp-inter", "p2", "deck-man", "interzone"),
        field_item("opp-will-field", "p2", "opp-will", "field"),
        field_item("stalemate", "p2", "opp-man-2", "stalemate"),
    ]
    session.rules_engine["deckConfirmedPlayerIds"] = ["p1", "p2"]
    session.rules_engine["readyPlayerIds"] = ["p1", "p2"]
    session.rules_engine["firstManifestationItemIds"] = {"p1": "own-con", "p2": "opp-con"}
    session.rules_engine["firstManifestationComplete"] = True
    session.rules_engine["firstManifestationTriggersQueued"] = True
    session.phase_tracker["enabled"] = True
    session.phase_tracker["advanced"] = True
    session.phase_tracker["turn"] = 2
    session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_reaction")
    if (ability.get("result") or {}).get("kind") in {
        "first_manifestation_trap", "field_becomes_first_manifestation", "interzone_becomes_first_manifestation",
    }:
        if (ability.get("result") or {}).get("kind") == "interzone_becomes_first_manifestation":
            source["fieldZone"] = "interzone"
        session.rules_engine["firstManifestationItemIds"] = {}
        session.rules_engine["firstManifestationComplete"] = False
        for item in session.battlefield:
            if item is not source and session.rules_item_controller_id(item) == "p1" and item.get("fieldZone") == "confrontation":
                item["fieldZone"] = "interzone"
                item["isSupport"] = False
    stack_action = {
        "id": "stack-1", "controllerId": "p2", "kind": "play_card",
        "source": {"cardId": "hand-will", "ownerId": "p2", "zone": "hand"},
        "targets": [{"kind": "card", "itemId": "own-con", "cardId": "own-man", "ownerId": "p1"}],
        "ability": {"id": "synthetic", "targets": {"kind": "card", "min": 1, "max": 1},
                    "result": {"kind": "score_owner", "value": 1}},
        "cost": {"tributeCardIds": [], "tributeMovements": [], "excessEssence": {}},
    }
    session.rules_engine["actionStack"] = [stack_action]
    return session, source, stack_action


def candidate_for(contract, index, stack_action):
    kind = contract.get("kind") or "card"
    if kind == "player":
        return {"kind": "player", "playerId": "p2"}
    if kind in {"stack_action", "stack_effect", "stack_item"}:
        return {"kind": kind, "actionId": stack_action["id"], "cardId": "hand-will", "controllerId": "p2"}
    if kind == "card_or_stack_action":
        return {"kind": "card", "itemId": "opp-con", "cardId": "opp-man", "ownerId": "p2", "controllerId": "p2"}
    if kind == "zone_card":
        zones = contract.get("zones") or ["graveyard"]
        zone = zones[0]
        owner = "p2" if contract.get("controller") == "opponent" else "p1"
        card = {"hand": "opp-man-2" if owner == "p2" else "own-man-2",
                "deck": "opp-man" if owner == "p2" else "deck-man",
                "graveyard": "opp-will" if owner == "p2" else "grave-man",
                "receptacle": "own-man" if owner == "p2" else "opp-man"}.get(zone, "grave-man")
        return {"kind": "zone_card", "playerId": owner, "zone": zone, "cardId": card}
    controller = contract.get("controller")
    owner = "p1" if controller == "self" else "p2"
    zone = contract.get("fieldZone")
    support = contract.get("supportOnly")
    if owner == "p1":
        item = "own-support" if support else "own-inter" if zone == "interzone" else "own-will-field" if contract.get("cardType") == "persistent_will" else "own-con"
        card = {"own-support": "own-man-2", "own-inter": "grave-man", "own-will-field": "own-will", "own-con": "own-man"}[item]
    else:
        item = "opp-support" if support else "opp-inter" if zone == "interzone" else "opp-will-field" if contract.get("cardType") == "persistent_will" else "opp-con"
        card = {"opp-support": "opp-man-2", "opp-inter": "deck-man", "opp-will-field": "opp-will", "opp-con": "opp-man"}[item]
    return {"kind": "card", "itemId": item, "cardId": card, "ownerId": owner, "controllerId": owner}


def targets_for(ability, stack_action):
    contracts = list(ability.get("targetGroups") or [])
    if not contracts and ability.get("targets"):
        target = ability["targets"]
        contracts = list(target.get("groups") or []) or [target]
    targets = []
    for contract in contracts:
        count = max(int(contract.get("min") or 0), 1 if int(contract.get("max") or 0) else 0)
        for index in range(count):
            targets.append(candidate_for(contract, index, stack_action))
    return targets


def build_action(card_id, ability, stack_action):
    return {
            "id": "probe", "controllerId": "p1", "kind": ability.get("action") or "activated_effect",
            "source": {"cardId": card_id, "ownerId": "p1", "itemId": "source", "zone": "battlefield"},
            "targets": targets_for(ability, stack_action), "ability": copy.deepcopy(ability),
            "cost": {"tributeCardIds": ["own-man-2"], "tributeMovements": [],
                     "excessEssence": {"phlegmatic": 3}, "optionalExtraEssenceSpent": 2,
                     "removedCounters": [{"counter": "Petal", "value": 3}]},
            "eventCardId": "opp-man", "eventItemId": "opp-con", "eventOwnerId": "p2",
            "eventControllerId": "p2", "eventPlayerId": "p2", "eventZone": "confrontation",
            "eventValue": 3, "eventCount": 3, "optionalAccepted": True,
        }


def exercise_special_result(session, card_id, ability, kind):
    if kind == "first_manifestation_trap":
        session.battlefield = [item for item in session.battlefield if item["id"] != "source"]
        player = session.players["p1"]
        player["zones"]["hand"].append(card_id)
        player["zoneOwners"]["hand"][card_id] = "p1"
        session.rules_engine["firstManifestationComplete"] = False
        session.rules_engine["firstManifestationTriggersQueued"] = False
        session.rules_engine["firstManifestationItemIds"] = {}
        session.rules_engine["firstManifestationValidatedPlayerIds"] = []
        session.rules_engine["trapPlayerIds"] = []
        session.phase_tracker["index"] = ADVANCED_PHASES.index("confrontation_choose")
        error, result = session.play_first_manifestation_trap("p1", card_id)
        if error or not result:
            raise AssertionError(error or "Trap did not produce a result")
        return
    if kind == "final_deck_points":
        session.battlefield = [item for item in session.battlefield if item["id"] != "source"]
        player = session.players["p1"]
        player["zones"]["deck"].insert(0, card_id)
        player["zoneOwners"]["deck"][card_id] = "p1"
        expected = int((ability.get("result") or {}).get("value") or 0)
        if session.rules_end_game_points("p1") != expected:
            raise AssertionError("end-game deck points were not applied")
        return
    if kind == "final_vessel_penalty":
        session.battlefield = [item for item in session.battlefield if item["id"] != "source"]
        player = session.players["p1"]
        player["zones"]["receptacle"].insert(0, card_id)
        player["zoneOwners"]["receptacle"][card_id] = "p2"
        player["zones"]["receptacle"].append("own-man-2")
        player["zoneOwners"]["receptacle"]["own-man-2"] = "p2"
        if session.rules_end_game_points("p1") >= 0:
            raise AssertionError("end-game Vessel penalty was not applied")
        return
    raise AssertionError(f"unknown specialized result {kind!r}")


SPECIAL_RESULTS = {
    "first_manifestation_trap", "final_deck_points", "final_vessel_penalty",
}


def smoke_ability(card_id, ability):
    """Return carrier count and readable failures for one shipped ability."""
    session, source_item, stack_action = make_session(card_id, ability)
    action = build_action(card_id, ability, stack_action)
    failures = []
    carriers = 0
    try:
        result = ability.get("result")
        if result:
            carriers += 1
            kind = result.get("kind")
            if kind in SPECIAL_RESULTS:
                exercise_special_result(session, card_id, ability, kind)
            elif session.apply_rules_action_result(action) is None:
                raise AssertionError(f"result {kind!r} returned no payload")

        ongoing = [ability.get("ongoingEffect"), *(ability.get("ongoingEffects") or [])]
        ongoing = [entry for entry in ongoing if entry]
        if ongoing:
            carriers += len(ongoing)
            session.create_rules_ongoing_effects(action)

        passive = ability.get("passiveEffect")
        if passive:
            carriers += 1
            kind = str(passive.get("kind") or "")
            session_source = "\n".join(
                path.read_text(encoding="utf-8")
                for path in [ROOT / "server" / "session.py", *sorted((ROOT / "server" / "game").rglob("*.py"))]
            )
            compiled_passives = {
                "construction_limit_bonus": (
                    session.card_rules[card_id].get("constructionLimitBonus")
                    == int(passive.get("value") or 0)
                ),
                "cannot_enter_confrontation": bool(
                    session.card_rules[card_id].get("cannotEnterConfrontation")
                ),
            }
            if kind in compiled_passives and not compiled_passives[kind]:
                raise AssertionError(f"passive {kind!r} was not compiled into static rules")
            if not kind or (kind not in session_source and kind not in compiled_passives):
                raise AssertionError(f"passive {kind!r} has no engine consumer")
            session.rules_manifestation_characteristics(source_item)
            session.rules_confrontation_power(source_item)
            session.resolve_rules_state_actions()
            session.serialize_for("p1", "player")

        permission = ability.get("playPermission")
        if permission:
            carriers += 1
            session.battlefield = [item for item in session.battlefield if item["id"] != "source"]
            player = session.players["p1"]
            player["zones"]["graveyard"].append(card_id)
            player["zoneOwners"]["graveyard"][card_id] = "p1"
            session.rules_engine["beginningPermissionsTurn"] = None
            granted = session.grant_rules_beginning_turn_permissions()
            if not any(entry.get("abilityId") == ability.get("id") for entry in granted):
                raise AssertionError("conditional play permission was not granted")

        if not carriers:
            raise AssertionError("ability has no executable behavior carrier")
    except Exception as exc:
        failures.append(f"{ability.get('id') or '?'}: {type(exc).__name__}: {exc}")
    return {"carriers": carriers, "failures": failures}


def smoke_card(card_id):
    failures = []
    carriers = 0
    abilities = list(main.CARD_ABILITIES.get(card_id) or [])
    for ability in abilities:
        report = smoke_ability(card_id, ability)
        carriers += report["carriers"]
        failures.extend(report["failures"])
    return {"abilities": len(abilities), "carriers": carriers, "failures": failures}


def smoke_all():
    cards = {card_id: smoke_card(card_id) for card_id in main.CARD_ABILITIES}
    return {
        "cards": cards,
        "summary": {
            "cards": len(cards),
            "abilities": sum(entry["abilities"] for entry in cards.values()),
            "carriers": sum(entry["carriers"] for entry in cards.values()),
            "failedCards": sum(bool(entry["failures"]) for entry in cards.values()),
        },
    }


if __name__ == "__main__":
    report = smoke_all()
    print(report["summary"])
    for card_id, entry in report["cards"].items():
        for failure in entry["failures"]:
            print(f"{card_id}: {failure}")
    raise SystemExit(1 if report["summary"]["failedCards"] else 0)
