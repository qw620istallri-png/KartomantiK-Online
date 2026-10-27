"""Transport invariants: exact JSON state, log order, rollback and bounded metrics."""
import copy
import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
from state_transport import StateStream, TrafficMetrics, message_cause, state_diff


def reconstruct(previous, packet):
    """Independent test receiver; compare its output with the canonical serializer."""
    if packet["type"] == "state":
        return {key: copy.deepcopy(value) for key, value in packet.items() if key != "stateRevision"}
    result = copy.deepcopy(previous)
    for op in packet["ops"]:
        parent = result
        for key in op["path"][:-1]:
            parent = parent[key]
        key = op["path"][-1]
        if op["op"] == "delete":
            del parent[key]
        elif op["op"] == "log_tail":
            parent[key] = parent[key][op["drop"]:] + copy.deepcopy(op["append"])
        else:
            parent[key] = copy.deepcopy(op["value"])
    return result


class StateTransportTests(unittest.TestCase):
    def fixture(self):
        return {"type": "state", "players": {"p1": {"score": 0, "name": "Élodie",
            "zones": {"hand": {"cards": ["secret"]}}}}, "recentLog": [],
            "rulesEngine": {"actionStack": [], "pendingChoice": None},
            "padding": "unchanged " * 150}

    def sent(self, stream, state, **kwargs):
        wire, snapshot, revision, kind, _ = stream.prepare(state, **kwargs)
        if wire is not None:
            stream.commit(snapshot, revision)
        return json.loads(wire) if wire is not None else None

    def test_first_state_is_complete_then_exact_nested_diff(self):
        s, stream = self.fixture(), StateStream(True)
        first = self.sent(stream, s)
        self.assertEqual(first["stateRevision"], 1)
        s["players"]["p1"]["score"] = 3
        packet = self.sent(stream, s)
        self.assertEqual(packet["type"], "state_patch")
        self.assertEqual(packet["baseRevision"], 1)
        self.assertEqual(packet["stateRevision"], 2)
        self.assertEqual(reconstruct(reconstruct(None, first), packet), s)
        self.assertNotIn("secret", json.dumps(packet))

    def test_prepare_does_not_commit_before_a_successful_send(self):
        stream = StateStream(True)
        wire, snapshot, revision, _, _ = stream.prepare(self.fixture())
        self.assertIsNone(stream.state)
        self.assertEqual(stream.revision, 0)
        stream.commit(snapshot, revision)
        self.assertEqual(stream.revision, 1)

    def test_snapshots_do_not_alias_live_engine_lists(self):
        s, stream = self.fixture(), StateStream(True)
        first = self.sent(stream, s)
        s["rulesEngine"]["actionStack"].append({"id": "new"})
        self.assertEqual(stream.state["rulesEngine"]["actionStack"], [])
        self.assertEqual(reconstruct(reconstruct(None, first), self.sent(stream, s)), s)

    def test_unchanged_broadcast_is_skipped_but_forced_snapshot_is_not(self):
        s, stream = self.fixture(), StateStream(True)
        self.sent(stream, s)
        self.assertIsNone(self.sent(stream, s))
        self.assertEqual(stream.revision, 1)
        forced = self.sent(stream, s, force_full=True)
        self.assertEqual(forced["type"], "state")
        self.assertEqual(forced["stateRevision"], 2)

    def test_old_clients_keep_ordinary_complete_states(self):
        s, stream = self.fixture(), StateStream(False)
        for _ in range(2):
            packet = self.sent(stream, s)
            self.assertEqual(packet, s)
            self.assertNotIn("stateRevision", packet)

    def test_larger_patch_falls_back_to_complete_state(self):
        stream = StateStream(True)
        self.sent(stream, {"type": "state", "a": 1})
        packet = self.sent(stream, {"type": "state", "a": 2})
        self.assertEqual(packet["type"], "state")
        self.assertEqual(packet["stateRevision"], 2)

    def test_journal_tail_adds_only_new_entries_and_preserves_thirty_in_order(self):
        s, stream = self.fixture(), StateStream(True)
        s["recentLog"] = [{"id": n, "details": {"text": "long log " * 10}} for n in range(30)]
        first = self.sent(stream, s)
        s["recentLog"] = s["recentLog"][2:] + [{"id": 30}, {"id": 31}]
        packet = self.sent(stream, s)
        self.assertEqual(packet["ops"], [{"op": "log_tail", "path": ["recentLog"],
            "drop": 2, "append": [{"id": 30}, {"id": 31}]}])
        self.assertEqual(reconstruct(reconstruct(None, first), packet), s)

    def test_journal_reset_and_changed_visibility_replace_the_tail(self):
        for new in ([], [{"id": 1, "text": "revealed"}], [{"id": 200}]):
            with self.subTest(new=new):
                old = {"recentLog": [{"id": 1, "text": "hidden"}]}
                packet = {"type": "state_patch", "ops": state_diff(old, {"recentLog": new})}
                self.assertEqual(reconstruct(old, packet), {"recentLog": new})

    def test_deletions_arrays_null_and_json_types_are_preserved(self):
        old = {"players": {"gone": {}}, "v": True, "nested": [True], "gone": 1}
        new = {"players": {}, "v": 1, "nested": [1], "added": None}
        packet = {"type": "state_patch", "ops": state_diff(old, new)}
        result = reconstruct(old, packet)
        self.assertEqual(json.dumps(result, sort_keys=True), json.dumps(new, sort_keys=True))

    def test_python_tuple_and_numeric_keys_follow_the_actual_json_shape(self):
        s, stream = self.fixture(), StateStream(True)
        s["extra"] = {3: ("first",)}
        first = self.sent(stream, s)
        s["extra"][3] = ("next",)
        packet = self.sent(stream, s)
        self.assertEqual(reconstruct(reconstruct(None, first), packet), json.loads(json.dumps(s)))
        self.assertTrue(all(isinstance(key, str) for op in packet["ops"] for key in op["path"]))

    def test_metrics_measure_utf8_bytes_and_never_payload_content(self):
        logger, now = Mock(), [0]
        metrics = TrafficMetrics(logger, clock=lambda: now[0])
        token = message_cause.set("set_score")
        try:
            metrics.record("patch", len("é".encode()), 100)
            self.assertEqual(metrics.snapshot()["totals"]["jsonBytes"], 2)
            now[0] = 60
            metrics.record("unchanged", 0, 100)
        finally:
            message_cause.reset(token)
        logger.info.assert_called_once()
        logged = json.loads(logger.info.call_args.args[1])
        self.assertEqual(logged["byAction"]["set_score"]["fullStateJsonBytes"], 200)
        self.assertEqual(logged["measurement"], "utf8_json_before_compression")
        self.assertEqual(metrics.snapshot()["totals"], {})

    def test_untrusted_action_labels_cannot_grow_metrics_without_bound(self):
        metrics = TrafficMetrics(Mock(), clock=lambda: 0)
        for n in range(1000):
            token = message_cause.set(f"unknown-{n}")
            metrics.record("otherMessage", 10)
            message_cause.reset(token)
        self.assertLessEqual(len(metrics.by_cause), 65)
        self.assertEqual(metrics.totals["jsonBytes"], 10000)


class StateTransportConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import main
        self.main = main
        self.saved_connections = dict(main.connections)
        main.connections.clear()
        self.entered, self.release = asyncio.Event(), asyncio.Event()
        owner = self

        class Peer:
            def __init__(self):
                self.frames = []

            async def send(self, wire):
                self.frames.append(json.loads(wire))
                if len(self.frames) == 1:
                    owner.entered.set()
                    await owner.release.wait()

        class World:
            state = {"type": "state", "score": 1, "padding": "fixed " * 100}

            def rules_auto_layout(self):
                pass

            def serialize_for(self, player_id, role):
                return {**self.state, **({"private": "old seat"} if role == "player" else {})}

        self.peer, self.world = Peer(), World()
        self.info = {"session": self.world, "playerId": "p1", "role": "player", "_state_stream": StateStream(True)}
        main.connections[self.peer] = self.info

    async def asyncTearDown(self):
        self.release.set()
        self.main.connections.clear()
        self.main.connections.update(self.saved_connections)

    async def test_overlapping_broadcasts_commit_in_send_order(self):
        first = asyncio.create_task(self.main.broadcast_state(self.world))
        await asyncio.wait_for(self.entered.wait(), 2)
        self.world.state["score"] = 2
        second = asyncio.create_task(self.main.broadcast_state(self.world))
        await asyncio.sleep(0)
        self.release.set()
        await asyncio.gather(first, second)
        self.assertEqual([p["stateRevision"] for p in self.peer.frames], [1, 2])
        full = reconstruct(None, self.peer.frames[0])
        self.assertEqual(full["score"], 1)
        self.assertEqual(reconstruct(full, self.peer.frames[1])["score"], 2)

    async def test_old_queued_view_cannot_follow_a_join_to_another_role(self):
        first = asyncio.create_task(self.main.broadcast_state(self.world))
        await asyncio.wait_for(self.entered.wait(), 2)
        self.world.state["score"] = 2
        old_queued = asyncio.create_task(self.main.broadcast_state(self.world))
        await asyncio.sleep(0)
        new_info = {**self.info, "role": "spectator", "_state_stream": StateStream(True, self.info["_state_stream"].lock)}
        self.main.connections[self.peer] = new_info
        joined = asyncio.create_task(self.main.send_to(self.peer, {"type": "joined"}))
        await asyncio.sleep(0)
        new_view = asyncio.create_task(self.main.broadcast_state(self.world))
        self.release.set()
        await asyncio.gather(first, old_queued, joined, new_view)
        self.assertEqual([p["type"] for p in self.peer.frames], ["state", "joined", "state"])
        self.assertEqual(self.peer.frames[-1]["stateRevision"], 1)
        self.assertNotIn("private", self.peer.frames[-1])

    async def test_closed_send_does_not_advance_reference_or_revision(self):
        from websockets.exceptions import ConnectionClosed

        async def fail(_wire):
            raise ConnectionClosed(None, None)

        self.peer.send = fail
        await self.main.broadcast_state(self.world)
        self.assertEqual(self.info["_state_stream"].revision, 0)
        self.assertIsNone(self.info["_state_stream"].state)
        self.assertNotIn(self.peer, self.main.connections)


if __name__ == "__main__":
    unittest.main()
