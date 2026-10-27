const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const createReceiver = vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../public/js/connection.js'), 'utf8') + '\ncreateStateReceiver;');
const plain = value => JSON.parse(JSON.stringify(value));
const full = revision => ({ type: 'state', stateRevision: revision, players: { p1: { score: 0, hand: ['private'] } }, recentLog: [{ id: 1 }], rulesEngine: { actionStack: [{ id: 'a' }, { id: 'b' }] } });
const patch = (base, ops) => ({ type: 'state_patch', baseRevision: base, stateRevision: base + 1, ops });

let requests = 0;
let receive = createReceiver(() => requests++);
let state = receive(full(1));
state.players.p1.hand.push('UI mutation');
state = receive(patch(1, [{ op: 'set', path: ['players', 'p1', 'score'], value: 7 },
  { op: 'log_tail', path: ['recentLog'], drop: 1, append: [{ id: 2 }] },
  { op: 'set', path: ['rulesEngine', 'actionStack'], value: [{ id: 'a' }] }]));
assert.equal(state.players.p1.score, 7);
assert.deepEqual(plain(state.players.p1.hand), ['private']);
assert.deepEqual(plain(state.recentLog), [{ id: 2 }]);
assert.deepEqual(plain(state.rulesEngine.actionStack), [{ id: 'a' }]);
assert.equal(requests, 0);
// Entire patches are atomic: a valid first op cannot leak when a later op is invalid.
assert.equal(receive(patch(2, [{ op: 'set', path: ['players', 'p1', 'score'], value: 999 },
  { op: 'delete', path: ['absent', 'key'] }])), null);
assert.equal(requests, 1);
assert.equal(receive(patch(2, [])), null);
assert.equal(receive(patch(100, [])), null);
assert.equal(requests, 1);
assert.equal(receive({ type: 'error', message: 'Still delivered' }).type, 'error');
assert.equal(receive(full(10)).players.p1.score, 0);
assert.equal(receive(patch(10, [{ op: 'delete', path: ['players', 'p1', 'hand'] }])).players.p1.hand, undefined);
assert.equal(receive(patch(10, [])), null); // A duplicate/out-of-order revision requests a snapshot.
assert.equal(requests, 2);
receive({ type: 'joined', playerId: 'observer' });
assert.equal(receive(patch(11, [])), null);
assert.equal(requests, 3);
assert.equal(receive({ type: 'state', players: {} }).type, 'state'); // old server/rollback
// Unusual identifiers are own data keys, never prototype writes.
receive(full(1));
const unusual = receive(patch(1, [{ op: 'set', path: ['players', '__proto__'], value: { safe: true } }]));
assert.equal(Object.hasOwn(unusual.players, '__proto__'), true);
assert.equal({}.safe, undefined);
assert.equal(receive(patch(2, [{ op: 'set', path: ['players', 'constructor', 'polluted'], value: true }])), null);
assert.equal({}.polluted, undefined);

for (const op of [
  { op: 'set', path: [], value: {} }, { op: 'set', path: ['players', 1], value: {} },
  { op: 'set', path: ['players'] }, { op: 'bogus', path: ['players'] },
  { op: 'log_tail', path: ['recentLog'], drop: -1, append: [] },
  { op: 'log_tail', path: ['recentLog'], drop: 2, append: [] },
]) {
  let calls = 0;
  const check = createReceiver(() => calls++);
  check(full(1));
  assert.equal(check(patch(1, [op])), null);
  assert.equal(calls, 1);
}
// Cross-language trace produced by the actual server serializer and diff builder.
if (process.argv[2]) {
  const traces = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  for (const trace of traces) {
    let latest = null;
    const read = createReceiver(() => { throw new Error('Unexpected resync in exact server trace'); });
    for (const step of trace) {
      if (step.packet) latest = read(step.packet);
      assert.deepEqual(plain(latest), step.expected);
    }
  }
  console.log(`Server/client trace parity: ${traces.reduce((n, t) => n + t.length, 0)} states OK`);
}
console.log('State transport client regression: OK');
