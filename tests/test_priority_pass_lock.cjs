// 26/11 report (Atavic): a player took back their pass while the opponent was
// choosing a payment. A pass can be cancelled only while the opponent does
// nothing: opening an action flow locks it.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("playwright");

const publicRoot = path.join(path.resolve(__dirname, ".."), "public");
const mime = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json" };

(async () => {
  const server = http.createServer((request, response) => {
    const url = new URL(request.url, "http://localhost");
    const file = path.resolve(publicRoot, "." + (url.pathname === "/" ? "/index.html" : decodeURIComponent(url.pathname)));
    if (!file.startsWith(publicRoot + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return response.writeHead(404).end();
    response.writeHead(200, { "Content-Type": mime[path.extname(file)] || "application/octet-stream" });
    fs.createReadStream(file).pipe(response);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "chrome", headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route("**/*", (route) => (new URL(route.request().url()).hostname === "127.0.0.1" ? route.continue() : route.abort()));
    await page.goto(`http://127.0.0.1:${server.address().port}/`);
    await page.waitForFunction(() => typeof cardsById !== "undefined" && cardsById.size > 300 && typeof renderAll === "function");
    const setup = ({ me, passes, locked, choice }) => page.evaluate(({ me, passes, locked, choice }) => {
      closeRulesBoardFlow();
      lastRulesPriorityClaim = "";
      const echo = "6b4f3yh4tk4091p_en";
      myPlayerId = me; isObserver = false; connectionMode = "casual"; soloControlledPlayerIds = [];
      const zones = () => Object.fromEntries(ZONES.map((key) => [key, { cards: [], owners: {} }]));
      latestState = {
        players: { p1: { id: "p1", name: "P1", seat: 0, score: 0, zones: zones() }, p2: { id: "p2", name: "P2", seat: 1, score: 0, zones: zones() } },
        battlefield: [
          { id: "echo", ownerId: "p1", controllerId: "p1", cardId: echo, x: 500, y: 300, faceUp: true, fieldZone: "confrontation", counters: {} },
          { id: "iz0", ownerId: "p1", controllerId: "p1", cardId: "inner-deserts-086", x: 80, y: 80, faceUp: true, fieldZone: "interzone", counters: {} },
        ],
        tokens: [], drawings: [],
        phaseTracker: { enabled: true, advanced: true, turn: 5, index: 12, passedPlayerIds: [] },
        rulesEngine: { enabled: true, priorityPlayerId: "p1", priorityPasses: passes, priorityPassLocked: locked, actionStack: [],
          firstManifestationComplete: true, readyPlayerIds: ["p1", "p2"], deckConfirmedPlayerIds: ["p1", "p2"],
          pendingChoice: choice ? { kind: "trigger_targets", id: "echo-choice", playerId: "p1", sourceCardId: echo, sourceItemId: "echo",
            targetRules: { min: 1, max: 3, cardType: "manifestation", zones: ["battlefield"], fieldZone: "interzone", controller: "self" } } : null },
      };
      window.__sent = [];
      send = (payload) => window.__sent.push(payload);
      document.querySelector("#joinScreen").classList.add("hidden");
      document.querySelector("#gameScreen").classList.remove("hidden");
      renderAll();
      renderAll();
      const button = document.querySelector("#passPriorityBtn");
      return { sent: window.__sent.map((m) => m.type), hidden: button.classList.contains("hidden"), passed: button.classList.contains("passed"), label: button.textContent };
    }, { me, passes, locked, choice });

    // p1 answers p2's pass: opening an action flow locks p2's pass, once
    let state = await setup({ me: "p1", passes: ["p2"], locked: false, choice: true });
    assert.deepEqual(state.sent.filter((type) => type === "claim_rules_priority"), ["claim_rules_priority"]);
    // already locked, or nobody passed: nothing to claim
    state = await setup({ me: "p1", passes: ["p2"], locked: true, choice: true });
    assert.ok(!state.sent.includes("claim_rules_priority"));
    state = await setup({ me: "p1", passes: [], locked: false, choice: true });
    assert.ok(!state.sent.includes("claim_rules_priority"));

    // p2, who passed: can cancel while p1 does nothing...
    state = await setup({ me: "p2", passes: ["p2"], locked: false, choice: false });
    assert.equal(state.hidden, false);
    assert.equal(state.passed, true, "the button offers to cancel the pass");
    // ...but not once p1 started acting: no cancel button, and a click sends nothing
    state = await setup({ me: "p2", passes: ["p2"], locked: true, choice: false });
    assert.equal(state.passed, false);
    assert.equal(state.hidden, true, "no cancel button once the opponent is acting");
    const clicked = await page.evaluate(() => { window.__sent = []; document.querySelector("#passPriorityBtn").click(); return window.__sent; });
    assert.deepEqual(clicked, []);

    assert.deepEqual(errors, []);
    console.log("Priority pass lock: OK");
  } finally {
    await browser.close();
    server.close();
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
