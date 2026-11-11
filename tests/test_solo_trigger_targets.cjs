// Solo: a triggered effect of Player 2's card offers Player 2's targets
// (Zombieswing returns a Manifestation from its owner's Limbo, never from Player 1's).
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
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, locale: "fr-FR" });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route("**/*", (route) => (new URL(route.request().url()).hostname === "127.0.0.1" ? route.continue() : route.abort()));
    await page.goto(`http://127.0.0.1:${server.address().port}/`);
    await page.waitForFunction(() => typeof cardsById !== "undefined" && cardsById.size > 300 && typeof renderAll === "function");
    for (const solo of [false, true]) {
      for (const viewer of ["p1", "p2"]) {
        if (!solo && viewer === "p1") continue; // Player 1 does not answer Player 2's choice
        const result = await page.evaluate(({ solo, viewer }) => {
          closeRulesBoardFlow();
          const zombieswing = "bu1y6jwy7iaywqu_en";
          myPlayerId = viewer; isObserver = false;
          if (solo) { connectionMode = "solo"; soloControlledPlayerIds = ["p1", "p2"]; soloPrimaryPlayerId = "p1"; }
          else { connectionMode = "casual"; soloControlledPlayerIds = []; }
          const zones = () => Object.fromEntries(ZONES.map((key) => [key, { cards: [], owners: {} }]));
          latestState = {
            players: { p1: { id: "p1", name: "P1", seat: 0, score: 0, zones: zones() }, p2: { id: "p2", name: "P2", seat: 1, score: 0, zones: zones() } },
            battlefield: [], tokens: [], drawings: [],
            phaseTracker: { enabled: true, advanced: true, turn: 3, index: 5, passedPlayerIds: [] },
            rulesEngine: { enabled: true, priorityPlayerId: "p1", actionStack: [], firstManifestationComplete: true, readyPlayerIds: ["p1", "p2"], deckConfirmedPlayerIds: ["p1", "p2"], pendingChoice: null },
          };
          latestState.players.p1.zones.graveyard.cards = ["inner-deserts-124"];
          latestState.players.p2.zones.graveyard.cards = ["inner-deserts-086", zombieswing];
          latestState.rulesEngine.pendingChoice = {
            kind: "trigger_targets", id: "zombieswing-choice", playerId: "p2", sourceCardId: zombieswing,
            targetRules: { kind: "zone_card", min: 1, max: 1, cardType: "manifestation", zones: ["graveyard"], owner: "self", container: "self", excludeSource: true },
          };
          window.__sent = [];
          send = (payload) => window.__sent.push(payload);
          document.querySelector("#joinScreen").classList.add("hidden");
          document.querySelector("#gameScreen").classList.remove("hidden");
          renderAll();
          renderAll();
          const flow = pendingRulesBoardFlow;
          return {
            mode: flow?.mode,
            targets: (flow?.draft?.structuredTargets || []).map((target) => `${target.containerId}:${target.cardId}`),
          };
        }, { solo, viewer });
        assert.equal(result.mode, "trigger_target", `solo=${solo} viewer=${viewer}`);
        assert.deepEqual(result.targets, ["p2:inner-deserts-086"], `solo=${solo} viewer=${viewer}`);
      }
    }
    assert.deepEqual(errors, []);
    console.log("Solo trigger targets regression: OK");
  } finally {
    await browser.close();
    server.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
