"""Seeded state machines with independent conservation and printed-rule oracles.

Replay: python tools/card_audit_traces.py --seed 42
Failures retain the exact prefix through the first failing step.
This covers selected mechanic combinations, not every pair of 450 cards.
"""
import argparse
import copy
import json
import random
from collections import Counter

import card_behavior_audit as audit

batches = audit.batches
WEAKEN = "bithch9c4vi77cu_en"
OPPRESS = "obn1uv72ewxv3y5_en"
CLEANSE = "inner-deserts-145"


def inventory(session):
    """Physical cards with immutable owners; virtual effects/copies excluded."""
    counts = Counter()
    for pid, player in session.players.items():
        for zone, cards in player["zones"].items():
            for cid in cards:
                counts[(session.card_owner_in_zone(pid, zone, cid), cid)] += 1
    for item in session.battlefield:
        if item.get("cardId") and not item.get("isCopy") and not item.get("isTokenCard"):
            counts[(item["ownerId"], item["cardId"])] += 1
    for card in session.rules_engine.get("suspendedCards", []):
        counts[(card["ownerId"], card["cardId"])] += 1
    for action in session.rules_engine.get("actionStack", []):
        if action.get("sourceOnStack") and not action.get("isCopy"):
            source = action["source"]
            counts[(source["ownerId"], source["cardId"])] += 1
    return counts


def invariants(session, expected):
    assert inventory(session) == expected, f"Physical card/owner conservation: {inventory(session) - expected} / missing {expected - inventory(session)}"
    for token in session.tokens:
        if token.get("isEssence"):
            assert token.get("counters", {}).get("essence", 0) >= 0, "Negative essence"
    for pid in session.players:
        view = session.serialize_for(pid, "player")
        json.dumps(view)
        for owner, player in view["players"].items():
            hand = player["zones"]["hand"]
            if owner != pid:
                assert not any(hand.get("cards") or []), "Opponent private Hand leaked"
        choice = view["rulesEngine"].get("pendingChoice")
        assert not choice or not any(k.startswith("_") for k in choice), "Internal choice data leaked"


def zone_machine(seed):
    rng = random.Random(seed)
    session, _, _ = batches.smoke.make_session(WEAKEN, {})
    session.battlefield = []
    session.tokens = []
    session.rules_engine["actionStack"] = []
    for pid, player in session.players.items():
        for zone in player["zones"]:
            player["zones"][zone] = []
            player["zoneOwners"][zone] = {}
    # Every printed card participates, independent of its ability dispatch.
    for index, cid in enumerate(batches.CATALOG.order):
        owner = "p1" if index % 2 == 0 else "p2"
        session.put_zone_card(owner, "deck", cid, owner)
    expected = inventory(session)
    trace = []
    try:
        for cid in batches.CATALOG.order:
            owner = next(pid for pid in session.players if cid in session.players[pid]["zones"]["deck"])
            trace.append({"operation": "suspend-roundtrip", "owner": owner, "cardId": cid})
            error, entry = session.suspend_zone_card(owner, "deck", cid, source_effect_id="audit")
            assert error is None, error
            invariants(session, expected)
            error, _ = session.restore_suspended_card(entry["id"], "hand")
            assert error is None, error
            invariants(session, expected)
        for _ in range(80):
            cards = [(pid, zone, cid) for pid, p in session.players.items() for zone, cs in p["zones"].items() for cid in cs]
            pid, zone, cid = rng.choice(cards)
            owner = session.card_owner_in_zone(pid, zone, cid)
            operation = rng.choice(["move", "suspend", "stale"])
            if operation == "move":
                destination = rng.choice(["deck", "hand", "graveyard", "exile", "receptacle"])
                recipient = rng.choice(["p1", "p2"]) if destination == "receptacle" else owner
                trace.append({"operation": operation, "from": [pid, zone], "to": [recipient, destination], "cardId": cid})
                before = audit.world(session)
                error, _, _ = session.move_zone_card_by_effect(pid, zone, recipient, destination, cid)
                if destination == "receptacle" and recipient == owner:
                    assert error and before == audit.world(session), "Own Vessel destination was not rejected atomically"
                else:
                    assert error is None, error
            elif operation == "suspend":
                trace.append({"operation": operation, "from": [pid, zone], "cardId": cid})
                error, entry = session.suspend_zone_card(pid, zone, cid, source_effect_id="audit", returnZone="hand", returnTurn=2)
                assert error is None, error
                if rng.choice([True, False]):
                    session.expire_rules_temporary_suspensions(2)
                else:
                    session.release_rules_suspended_by("audit")
            else:
                before = audit.world(session)
                trace.append({"operation": "stale-suspension", "id": "nonexistent"})
                error, _ = session.restore_suspended_card("nonexistent")
                assert error and before == audit.world(session), "Stale action mutated state"
            invariants(session, expected)
        return {"seed": seed, "family": "zone-ownership-suspend", "status": "pass", "steps": len(trace), "cards": 450}
    except Exception as exc:
        return {"seed": seed, "family": "zone-ownership-suspend", "status": "fail", "error": str(exc), "failingPrefix": trace}


def stack_machine(seed):
    rng = random.Random(seed)
    session, _, _ = batches.smoke.make_session(WEAKEN, {})
    session.battlefield = [batches.smoke.field_item("target", "p2", "opp-man", counters={})]
    session.card_rules["opp-man"]["power"] = 100
    session.rules_engine.update(actionStack=[], priorityPlayerId="p1", autoSkipPhases=False)
    for pid, player in session.players.items():
        for zone in player["zones"]:
            player["zones"][zone] = []
            player["zoneOwners"][zone] = {}
        for cid in [WEAKEN, OPPRESS, CLEANSE]:
            player["zones"]["hand"].extend([cid] * 40)
            player["zoneOwners"]["hand"][cid] = pid
        session.add_rules_excess_essence(pid, [{"temperament": "transcendent", "amount": 1000}])
    expected = inventory(session)
    modifier = 0
    trace = []
    try:
        for round_index in range(10):
            declared = []
            for _ in range(rng.randint(1, 4)):
                cid = rng.choice([WEAKEN, OPPRESS, CLEANSE])
                actor = session.rules_engine["priorityPlayerId"]
                ability = next(a for a in batches.main.CARD_ABILITIES[cid] if a.get("action") == "play_card")
                trace.append({"operation": "declare", "playerId": actor, "cardId": cid, "abilityId": ability["id"], "target": "target"})
                error, action = session.declare_rules_action(actor, "Seeded printed-rule oracle", kind="play_card",
                    source={"cardId": cid, "zone": "hand"}, ability_id=ability["id"],
                    targets=[{"kind": "card", "itemId": "target", "cardId": "opp-man", "ownerId": "p2"}])
                assert error is None, error
                declared.append((action["id"], cid))
                invariants(session, expected)
                assert session.rules_manifestation_characteristics(session.find_battlefield_item("target"))["power"] == 100 + modifier, "Effect applied before resolution"
            for action_id, cid in reversed(declared):
                for _ in range(2):
                    actor = session.rules_engine["priorityPlayerId"]
                    trace.append({"operation": "pass", "playerId": actor})
                    error, _ = session.pass_rules_priority(actor)
                    assert error is None, error
                last = session.rules_engine["lastResolvedAction"]
                assert last["id"] == action_id, "Stack order is not LIFO"
                # Independent oracle from the three printed texts, no metadata
                # reading to derive the expected modifier or cleanup behavior.
                modifier = 0 if cid == CLEANSE else modifier + (-1 if cid == WEAKEN else -3)
                power = session.rules_manifestation_characteristics(session.find_battlefield_item("target"))["power"]
                assert power == 100 + modifier, f"Printed text expected {100 + modifier}, got {power}"
                invariants(session, expected)
            if round_index % 3 == 2:
                trace.append({"operation": "expire-characteristic-modifiers"})
                session.phase_tracker["turn"] += 1
                session.prune_rules_ongoing_effects()
                modifier = 0
                assert session.rules_manifestation_characteristics(session.find_battlefield_item("target"))["power"] == 100
                invariants(session, expected)
        return {"seed": seed, "family": "stack-cost-power-cleanse-expiry", "status": "pass", "steps": len(trace), "cards": [WEAKEN, OPPRESS, CLEANSE]}
    except Exception as exc:
        return {"seed": seed, "family": "stack-cost-power-cleanse-expiry", "status": "fail", "error": str(exc), "failingPrefix": trace}


def run(seeds):
    start_digest = audit.digest()
    rows = [fn(seed) for seed in seeds for fn in (zone_machine, stack_machine)]
    if audit.digest() != start_digest:
        rows.append({"family": "source-integrity", "status": "fail", "error": "Inputs changed during execution; rerun the traces."})
    return {"schemaVersion": 1, "sourceDigest": start_digest, "seeds": seeds,
            "summary": {"traces": len(rows), "steps": sum(r.get("steps", len(r.get("failingPrefix", []))) for r in rows),
                        "failed": sum(r["status"] == "fail" for r in rows)}, "traces": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--count", type=int, default=20)
    args = parser.parse_args()
    result = run([args.seed] if args.seed is not None else list(range(args.count)))
    audit.OUT.mkdir(parents=True, exist_ok=True)
    (audit.OUT / "traces.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"]))
    for failure in result["traces"]:
        if failure["status"] == "fail":
            print(json.dumps({k: v for k, v in failure.items() if k != "failingPrefix"}))
    raise SystemExit(int(bool(result["summary"]["failed"])))
