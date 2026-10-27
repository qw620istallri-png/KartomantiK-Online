"""Negotiated, recipient-specific state diffs and bounded JSON traffic counters.

No game rules live here. Old clients continue receiving ordinary full states.
Metrics count UTF-8 JSON before WebSocket compression, not billed wire bytes.
"""
import asyncio
from collections import Counter
from contextvars import ContextVar
import json
import time


message_cause = ContextVar("ws_message_cause", default="background")


def encode(payload):
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def state_diff(previous, current, path=()):
    if isinstance(previous, dict) and isinstance(current, dict):
        ops = [{"op": "delete", "path": [*path, key]} for key in previous if key not in current]
        for key, value in current.items():
            if key not in previous:
                ops.append({"op": "set", "path": [*path, key], "value": value})
            else:
                ops.extend(state_diff(previous[key], value, (*path, key)))
        return ops
    if type(previous) is type(current) and previous == current and encode(previous) == encode(current):
        return []
    if path == ("recentLog",) and isinstance(previous, list) and isinstance(current, list):
        for overlap in range(min(len(previous), len(current)), 0, -1):
            if previous[-overlap:] == current[:overlap]:
                return [{"op": "log_tail", "path": list(path), "drop": len(previous) - overlap,
                         "append": current[overlap:]}]
    return [{"op": "set", "path": list(path), "value": current}]


class StateStream:
    def __init__(self, enabled=False, lock=None):
        self.enabled = enabled
        self.lock = lock if lock is not None else asyncio.Lock()
        self.state = None
        self.revision = 0

    def prepare(self, payload, *, force_full=False):
        # Freeze the actual JSON tree before awaiting, including stringified keys
        # and tuples encoded as arrays. The receiver must see this exact shape.
        full = encode(payload)
        snapshot = json.loads(full)
        if not self.enabled:
            return full, snapshot, 0, "full", len(full.encode("utf-8"))
        revision = self.revision + 1
        message = {**snapshot, "stateRevision": revision}
        wire = encode(message)
        kind = "full"
        if self.state is not None and not force_full:
            ops = state_diff(self.state, snapshot)
            if not ops:
                return None, snapshot, self.revision, "unchanged", len(full.encode("utf-8"))
            patch = encode({"type": "state_patch", "baseRevision": self.revision,
                            "stateRevision": revision, "ops": ops})
            if len(patch.encode("utf-8")) < len(wire.encode("utf-8")):
                wire, kind = patch, "patch"
        return wire, snapshot, revision, kind, len(full.encode("utf-8"))

    def commit(self, snapshot, revision):
        if self.enabled:
            self.state, self.revision = snapshot, revision

    def reset(self):
        self.state, self.revision = None, 0


class TrafficMetrics:
    def __init__(self, logger, interval=60, clock=time.monotonic):
        self.logger, self.interval, self.clock = logger, interval, clock
        self.started = clock()
        self.totals = Counter()
        self.by_cause = {}

    def record(self, kind, sent_bytes, full_state_bytes=0):
        cause = str(message_cause.get())[:60]
        if cause not in self.by_cause and len(self.by_cause) >= 64:
            cause = "other"
        counters = self.by_cause.setdefault(cause, Counter())
        values = {"jsonBytes": sent_bytes, "fullStateJsonBytes": full_state_bytes, kind: 1}
        self.totals.update(values)
        counters.update(values)
        now = self.clock()
        if now - self.started >= self.interval:
            self.logger.info("ws_traffic %s", encode(self.snapshot(now)))
            self.started = now
            self.totals.clear()
            self.by_cause.clear()

    def snapshot(self, now=None):
        return {"measurement": "utf8_json_before_compression", "seconds": round((now if now is not None else self.clock()) - self.started, 2),
                "totals": dict(self.totals), "byAction": {key: dict(value) for key, value in self.by_cause.items()}}
