// "Up to N targets" triggered effects (Echo of the Wilds: distribute +3 among
// 1 to 3 cards of your Interzone). 26/11 report: with 1 card in the Interzone,
// after picking it the window said "no legal target" with no way to go on.
// Now the choice is sent once every legal target is taken, and a Confirm button
// ends it early when more targets remain.
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
    const setup = (count) => page.evaluate((count) => {
      closeRulesBoardFlow();
      const echo = "6b4f3yh4tk4091p_en";
      const others = ["inner-deserts-086", "inner-deserts-124", "bu1y6jwy7iaywqu_en"];
      myPlayerId = "p1"; isObserver = false; connectionMode = "casual"; soloControlledPlayerIds = [];
      const zones = () => Object.fromEntries(ZONES.map((key) => [key, { cards: [], owners: {} }]));
      latestState = {
        players: { p1: { id: "p1", name: "P1", seat: 0, score: 0, zones: zones() }, p2: { id: "p2", name: "P2", seat: 1, score: 0, zones: zones() } },
        battlefield: [
          { id: "echo", ownerId: "p1", controllerId: "p1", cardId: echo, x: 500, y: 300, faceUp: true, fieldZone: "confrontation", counters: {} },
          ...others.slice(0, count).map((cardId, index) => ({ id: `iz${index}`, ownerId: "p1", controllerId: "p1", cardId, x: 80, y: 80 + index * 200, faceUp: true, fieldZone: "interzone", counters: {} })),
        ],
        tokens: [], drawings: [],
        phaseTracker: { enabled: true, advanced: true, turn: 5, index: 12, passedPlayerIds: [] },
        rulesEngine: { enabled: true, priorityPlayerId: "p1", actionStack: [], firstManifestationComplete: true, readyPlayerIds: ["p1", "p2"], deckConfirmedPlayerIds: ["p1", "p2"], pendingChoice: {
          kind: "trigger_targets", id: "echo-choice", playerId: "p1", sourceCardId: echo, sourceItemId: "echo",
          targetRules: { min: 1, max: 3, cardType: "manifestation", zones: ["battlefield"], fieldZone: "interzone", controller: "self" },
        } },
      };
      window.__sent = [];
      send = (payload) => window.__sent.push(payload);
      document.querySelector("#joinScreen").classList.add("hidden");
      document.querySelector("#gameScreen").classList.remove("hidden");
      renderAll();
      renderAll();
      return { mode: pendingRulesBoardFlow?.mode, targets: pendingRulesBoardFlow?.draft?.structuredTargets?.length || 0 };
    }, count);
    const pick = (itemId) => page.evaluate((itemId) => {
      const element = document.querySelector(`[data-item-id="${itemId}"].rules-valid-target`) || [...document.querySelectorAll(".rules-valid-target")].find((el) => el.dataset.itemId === itemId);
      if (!element) return false;
      element.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, cancelable: true }));
      return true;
    }, itemId);

    // one card in the Interzone: picking it sends the choice
    let state = await setup(1);
    assert.equal(state.mode, "trigger_target");
    assert.equal(state.targets, 1);
    assert.ok(await pick("iz0"), "the only Interzone card is a target");
    await page.waitForTimeout(400);
    let sent = await page.evaluate(() => window.__sent);
    assert.equal(sent.length, 1, "the choice is sent once the only target is taken");
    assert.equal(sent[0].type, "resolve_rules_choice");
    assert.deepEqual(sent[0].targets.map((target) => target.itemId), ["iz0"]);

    // two cards: after one pick, Confirm ends the choice with that one
    state = await setup(2);
    assert.equal(state.targets, 2);
    assert.ok(await pick("iz1"));
    await page.waitForTimeout(100);
    const button = await page.evaluate(() => {
      const element = document.querySelector("#rulesConfirmTargets");
      return element ? { disabled: element.disabled, text: element.textContent } : null;
    });
    assert.ok(button, "a Confirm button is offered");
    assert.equal(button.disabled, false);
    assert.match(button.text, /1\/3/);
    await page.evaluate(() => document.querySelector("#rulesConfirmTargets").click());
    await page.waitForTimeout(400);
    sent = await page.evaluate(() => window.__sent);
    assert.equal(sent.length, 1);
    assert.deepEqual(sent[0].targets.map((target) => target.itemId), ["iz1"]);
    assert.deepEqual(errors, []);
    console.log("Up-to-N trigger targets: OK");
  } finally {
    await browser.close();
    server.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
