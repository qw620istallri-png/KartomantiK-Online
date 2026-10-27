"""Reproducible local serialization/deflate comparison; never contacts Render.

Uses shipped serialization/broadcasting and actual client reconstruction. Frame
sizes include the installed WebSocket encoder's deflate and WS headers, not TLS,
TCP, keepalives or other messages. These fixtures don't predict a monthly bill.
"""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tests"), str(ROOT / "server"), str(ROOT / "tools")]
import test_bounce_replay_clauses as fixtures
import test_latency_stack_sequences as latency
import main
import card_behavior_audit as audit
from state_transport import StateStream, TrafficMetrics, message_cause
from websockets.frames import Frame, Opcode
from websockets.extensions.permessage_deflate import enable_server_permessage_deflate


class Peer:
    def __init__(self):
        self.frames = []

    async def send(self, wire):
        self.frames.append(wire)


def compressed_size(frames):
    factory = enable_server_permessage_deflate([])[0]
    _, extension = factory.process_request_params([("client_max_window_bits", None)], [])
    return sum(len(Frame(Opcode.TEXT, wire.encode("utf-8")).serialize(mask=False, extensions=[extension]))
               for wire in frames)


def world():
    f = fixtures.BounceReplayClauses()
    s = f.world()
    ids = [c["id"] for c in main.CARD_DATA[:35]]
    for pid in ("p1", "p2"):
        f.put(s, pid, "deck", ids[:30])
        f.put(s, pid, "hand", ids[30:])
        s.players[pid]["deckDefinition"] = {"name": "Synthetic bandwidth fixture", "groups": [{"kind": "deck", "cardIds": ids}]}
    for i in range(8):
        f.field(s, "replay-man", f"field-{i}", owner="p1" if i % 2 == 0 else "p2", support=i >= 2)
    for i in range(30):
        s.add_log("p1", "rules_priority_passed", {"phaseId": "confrontation_reaction", "stackDepth": i % 3})
    return s


async def scenario(kind):
    s = world()
    if kind == "manual":
        s.rules_engine["enabled"] = False
    if kind == "stack":
        s.rules_engine["actionStack"] = [latency.LatencyStackSequences.effect(f"effect-{n}") for n in range(33)]
    old, new = [Peer(), Peer()], [Peer(), Peer()]
    for pid, legacy, modern in zip(("p1", "p2"), old, new):
        for peer, enabled in ((legacy, False), (modern, True)):
            main.connections[peer] = {"session": s, "playerId": pid, "role": "player", "_state_stream": StateStream(enabled)}
    traces = [[], []]
    steps = 34 if kind == "stack" else 101
    for i in range(steps):
        cause = "background"
        if kind == "stack" and i:
            s.resolve_rules_top_action()
            s.add_log("p1", "rules_action_resolved", {"actionId": f"effect-{33-i}"})
            cause = "pass_priority"
        elif kind == "journal":
            s.add_log("p1", "set_score", {"playerId": "p1", "score": 50+i})
            cause = "set_score"
        elif kind == "deck":
            deck = s.players["p1"]["zones"]["deck"]
            deck.append(deck.pop(0))
            cause = "reorder_deck"
        elif kind in {"mixed", "manual"}:
            if i % 5 == 0:
                s.add_log("p1", "set_score", {"playerId": "p1", "score": 50+i})
                cause = "set_score"
            elif i % 5 == 1:
                s.players["p1"]["activity"] = "searching" if i % 2 else None
                cause = "set_activity"
            elif i % 5 == 2:
                s.players["p1"]["score"] += 1
                cause = "set_score"
            elif i % 5 == 3:
                s.battlefield[0]["x"] += 1
                cause = "move_field"
        before = [len(p.frames) for p in new]
        token = message_cause.set(cause)
        try:
            await main.broadcast_state(s)
        finally:
            message_cause.reset(token)
        for n in range(2):
            traces[n].append({"expected": json.loads(old[n].frames[-1]),
                              "packet": json.loads(new[n].frames[-1]) if len(new[n].frames) > before[n] else None})
    old_bytes = sum(len(wire.encode("utf-8")) for peer in old for wire in peer.frames)
    new_bytes = sum(len(wire.encode("utf-8")) for peer in new for wire in peer.frames)
    old_compressed, new_compressed = sum(compressed_size(p.frames) for p in old), sum(compressed_size(p.frames) for p in new)
    for peer in old + new:
        main.connections.pop(peer)
    return {"scenario": kind, "canonicalStatesCompared": steps * 2,
            "fullFrames": sum(len(p.frames) for p in old), "incrementalFrames": sum(len(p.frames) for p in new),
            "fullJsonBytes": old_bytes, "incrementalJsonBytes": new_bytes,
            "jsonReductionPercent": round(100 * (1 - new_bytes / old_bytes), 2),
            "fullLocalCompressedFrameBytes": old_compressed, "incrementalLocalCompressedFrameBytes": new_compressed,
            "localCompressedFrameReductionPercent": round(100 * (1 - new_compressed / old_compressed), 2)}, traces


async def run():
    saved, metrics = dict(main.connections), main.WS_TRAFFIC
    main.connections.clear()
    main.WS_TRAFFIC = TrafficMetrics(Mock(), interval=float("inf"))
    cases, traces = [], []
    try:
        for kind in ("mixed", "manual", "journal", "deck", "unchanged", "stack"):
            result, trace = await scenario(kind)
            cases.append(result)
            traces.extend(trace)
    finally:
        main.connections.clear()
        main.connections.update(saved)
        main.WS_TRAFFIC = metrics
    with tempfile.TemporaryDirectory(prefix="kko-transport-") as temp:
        trace_file = Path(temp) / "trace.json"
        trace_file.write_text(json.dumps(traces), encoding="utf-8")
        checked = subprocess.run(["node", "tests/test_state_transport.cjs", str(trace_file)], cwd=ROOT,
                                 capture_output=True, text=True, check=True, timeout=60)
    return cases, checked.stdout


if __name__ == "__main__":
    digest = audit.digest()
    cases, parity = asyncio.run(run())
    assert audit.digest() == digest
    proof = {"schemaVersion": 1, "sourceDigest": digest, "published": False,
             "cases": cases, "clientParity": parity.strip(),
             "limits": ["Synthetic local fixtures, not captured production traffic or a monthly forecast.",
                        "Compressed frame encoding uses the installed library defaults (12-bit windows, context takeover, memLevel 5); excludes TLS/TCP/keepalives.",
                        "Production metrics count UTF-8 JSON bytes before compression; Render's meter remains authoritative."]}
    out = ROOT / "reports/network-usage"
    out.mkdir(parents=True, exist_ok=True)
    (out / "benchmark.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(cases, indent=2))
    print(parity)
