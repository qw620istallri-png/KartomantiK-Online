// Wills that put Manifestations or tokens into Support: Reaction only (13/11).
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.resolve(__dirname, "..", "public", "js", "hand.js"), "utf8");
const constant = source.match(/const RULES_REACTION_ONLY_SUPPORT_WILL_IDS = \[[\s\S]*?\];\n/);
const fn = source.match(/function rulesEphemeralPhasesClient\(card\) \{[\s\S]*?\n\}\n/);
assert.ok(constant && fn, "rulesEphemeralPhasesClient not found in hand.js");
const context = {};
vm.runInNewContext(`${constant[0]}${fn[0]}this.phases = rulesEphemeralPhasesClient;`, context);

const read = (...parts) => JSON.parse(fs.readFileSync(path.resolve(__dirname, "..", "public", ...parts), "utf8"));
const cards = [...read("cards-data.json"), ...read("extensions", "inner-desert", "cards.json")];
const byName = (name) => cards.find((card) => card.name === name);
for (const name of [
  "Help!", "Reforging Fate", "Twist the Soul", "Consult", "Mirror the Impulse", "Rally",
  "Recall the Consumed",
]) {
  assert.deepEqual([...context.phases(byName(name))], ["confrontation_reaction"], name);
}
assert.deepEqual(
  [...context.phases(byName("Incinerate"))],
  ["confrontation_reaction", "resolution_effects", "end_actions"],
);
console.log("reaction-only support wills: ok");
