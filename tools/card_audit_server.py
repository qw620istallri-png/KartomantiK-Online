"""Isolated real game server for two-browser audit.

Fixtures are controlled ONLY through the parent process's stdin. No test route,
permission bypass or fixture loader is added to the production application.
All browser traffic uses main.handler, including joins, choices and reconnects.
"""
import asyncio
import json
import random
import sys

import card_scenario_batches as batches
from card_behavior_audit import digest
from websockets.asyncio.server import serve

main = batches.main
session = None
revision = 0
handled = []
handled_changed = asyncio.Event()
class ObservedSocket:
    """Observe completion of an entire production handler iteration.

    The next receive happens AFTER automatic actions and broadcasts, not merely
    after handle_message. Fixtures must never race an unfinished auto-resolution.
    """
    def __init__(self, socket):
        self.socket = socket

    def __getattr__(self, name):
        return getattr(self.socket, name)

    async def __aiter__(self):
        async for raw in self.socket:
            yield raw
            data = json.loads(raw)
            if data.get("type") in {"declare_rules_action", "pass_priority", "resolve_rules_choice", "play_first_manifestation_trap", "spend_counter_essence"}:
                handled.append(data)
                handled_changed.set()


async def observed_handler(socket):
    await main.handler(ObservedSocket(socket))


def emit(value):
    print(json.dumps(value, ensure_ascii=True), flush=True)


def replace(fresh):
    global revision
    codes = {key: value for key, value in session.__dict__.items() if key.startswith("code_")}
    session.__dict__.clear()
    session.__dict__.update(fresh.__dict__)
    session.__dict__.update(codes)
    session.card_labels = {**main.CARD_LABELS, **{cid: cid for cid in session.card_rules if cid not in main.CARD_LABELS}}
    for action in session.rules_engine.get("actionStack", []):
        action.setdefault("label", "Audit fixture: ordinary responseable effect")
    session.rules_engine.update(autoSkipPhases=False, autoSkipOffPlayerIds=["p1", "p2"])
    for player in session.players.values():
        player["connected"] = True
    revision += 1
    handled.clear()
    session.add_log("p1", "audit_fixture", {"revision": revision})


def overrides():
    return [{"id": cid, "name": cid, "effect": "", "points": session.card_points.get(cid, 1), **rule}
            for cid, rule in session.card_rules.items() if cid not in main.CARD_RULES]


async def control(data):
    command = data["command"]
    result = {}
    if command == "catalog":
        result = {"cards": [{"id": cid, "name": batches.CATALOG.cards[cid]["name"]}
                            for cid in batches.CATALOG.order],
                  "actions": [{"cardId": cid, "abilityId": ability["id"]}
                              for cid in batches.CATALOG.order for ability in main.CARD_ABILITIES.get(cid, [])
                              if not any(ability.get(k) for k in ("trigger", "passiveEffect", "playPermission"))]}
    elif command == "render":
        fresh = main.new_sandbox_session()
        scenario = batches.sandbox.generic_scenarios(batches.CATALOG, data["cardId"])[0]
        batches.sandbox.apply_scenario(fresh, batches.CATALOG, scenario, "p1", opp_id="p2")
        replace(fresh)
    elif command == "action":
        cid = data["cardId"]
        random.seed(cid + data["abilityId"])
        ability = next(a for a in main.CARD_ABILITIES[cid] if a["id"] == data["abilityId"])
        fresh, actor, source, targets, cost = batches.prepare_action(cid, ability)
        kind = (ability.get("result") or {}).get("kind")
        if kind == "first_manifestation_trap":
            fresh.battlefield = [i for i in fresh.battlefield if i["id"] != "source"]
            fresh.players[actor]["zones"]["hand"].append(cid)
            fresh.rules_engine.update(firstManifestationComplete=False, firstManifestationTriggersQueued=False,
                                      firstManifestationItemIds={}, firstManifestationValidatedPlayerIds=[])
            fresh.phase_tracker["index"] = batches.ADVANCED_PHASES.index("confrontation_choose")
        if kind == "create_essence":
            fresh.find_battlefield_item("source")["chosenTemperament"] = "phlegmatic"
        replace(fresh)
        result = {"actor": actor, "source": source, "ability": ability, "targets": targets, "costCardId": cost}
    elif command == "choice":
        # Real Gobres result creates a private Suspend choice, then actual UI
        # answers it after a real reconnect. No fabricated client state.
        ability = next(a for a in main.CARD_ABILITIES["inner-deserts-088"] if a.get("trigger"))
        fresh, _, _ = batches.smoke.make_session("inner-deserts-088", ability)
        fresh.rules_engine["actionStack"] = []
        fresh.players["p2"]["zones"]["hand"] = ["inner-deserts-115", "inner-deserts-047"]
        fresh.players["p2"]["zoneOwners"]["hand"] = {cid: "p2" for cid in fresh.players["p2"]["zones"]["hand"]}
        fresh.apply_rules_action_result({"id": "audit-gobres", "controllerId": "p1",
            "source": {"cardId": "inner-deserts-088", "itemId": "source"},
            "targets": [{"kind": "player", "playerId": "p2"}],
            "ability": {"result": {"kind": "suspend_opponent_hand_will"}}})
        replace(fresh)
    elif command == "snapshot":
        result = {"players": session.players, "battlefield": session.battlefield,
                  "tokens": session.tokens, "rules": session.rules_engine,
                  "spectator": session.serialize_for(None, "spectator"), "log": session.log, "handled": handled,
                  "viewSequences": {pid: max((int(e.get("sequence") or 0) for e in session.serialize_for(pid, "player")["recentLog"]), default=0)
                                    for pid in session.players}}
    elif command == "settle":
        async def wait_handled():
            while len(handled) < data["count"]:
                handled_changed.clear()
                await handled_changed.wait()
        await asyncio.wait_for(wait_handled(), timeout=8)
        result = {"handled": len(handled)}
    elif command == "refresh":
        pass
    else:
        raise ValueError(f"Unknown audit command {command}")
    if command not in {"catalog", "snapshot", "settle"}:
        await main.broadcast_state(session)
        result.update(revision=revision, overrides=overrides())
    return result


async def run():
    global session
    cid = batches.CATALOG.order[0]
    session, _, _ = batches.smoke.make_session(cid, {})
    session.rules_engine.update(autoSkipPhases=False, autoSkipOffPlayerIds=["p1", "p2"])
    main.sessions[session.code_player] = session
    async with serve(observed_handler, "127.0.0.1", 0, process_request=main.process_request, compression=None) as server:
        emit({"port": server.sockets[0].getsockname()[1], "code": session.code_player, "sourceDigest": digest()})
        while line := await asyncio.to_thread(sys.stdin.readline):
            data = json.loads(line)
            try:
                emit({"requestId": data["requestId"], "result": await control(data)})
            except Exception as exc:
                emit({"requestId": data["requestId"], "error": f"{type(exc).__name__}: {exc}"})


if __name__ == "__main__":
    asyncio.run(run())
