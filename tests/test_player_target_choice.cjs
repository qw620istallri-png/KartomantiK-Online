const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "../public");
const mime = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".json": "application/json" };

// Reported 13/11: playing Dark Apparition, clicking a player did nothing (the
// hidden player buttons were locked as if an answer was already on its way),
// and the picked player was hard to tell apart from the other one.
(async () => {
  const server = http.createServer((request, response) => {
    const url = new URL(request.url, "http://localhost");
    const file = path.resolve(root, "." + (url.pathname === "/" ? "/index.html" : decodeURIComponent(url.pathname)));
    if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return response.writeHead(404).end();
    response.writeHead(200, { "Content-Type": mime[path.extname(file)] || "application/octet-stream" });
    fs.createReadStream(file).pipe(response);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "chrome", headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, locale: "fr-FR" });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route("**/*", (route) => new URL(route.request().url()).hostname === "127.0.0.1" ? route.continue() : route.abort());
    await page.goto(`http://127.0.0.1:${server.address().port}/`);
    await page.waitForFunction(() => cardsById.size === 450);
    const setup = (mode) => page.evaluate((mode) => {
      for (const card of cardsById.values()) card.image = "card-back.webp";
      const zone = (cards = []) => ({ cards: [...cards], count: cards.length, owners: Object.fromEntries(cards.map((id) => [id, "p1"])) });
      const zones = (hand) => ({ hand: zone(hand), graveyard: zone(), deck: zone(), exile: zone(), receptacle: zone() });
      myPlayerId = "p1"; isObserver = false; connectionRole = "player";
      pendingTriggeredPlacement = null;
      latestState = {
        players: {
          p1: { id: "p1", name: "Ista", seat: 0, score: 0, zones: zones(["7e2ppf4rfgkdfms_en"]) },
          p2: { id: "p2", name: "Bot KKO", seat: 1, score: 0, zones: zones([]) },
        },
        battlefield: [
          { id: "mine", cardId: "inner-deserts-104", ownerId: "p1", x: 445, y: 800, fieldZone: "confrontation", faceUp: true, rotation: 0, counters: {} },
          { id: "theirs", cardId: "g3zumpyf623hto6_en", ownerId: "p2", x: 445, y: 525, fieldZone: "confrontation", faceUp: true, rotation: 0, counters: {} },
        ],
        drawings: [], tokens: [],
        phaseTracker: { enabled: true, advanced: true, index: ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_reaction"), turn: 3, passedPlayerIds: [] },
        rulesEngine: { enabled: true, priorityPlayerId: "p1", actionStack: [], deckConfirmedPlayerIds: ["p1", "p2"], readyPlayerIds: ["p1", "p2"], firstManifestationComplete: true },
      };
      window.__sent = []; send = (payload) => window.__sent.push(payload);
      document.querySelector("#joinScreen").classList.add("hidden");
      document.querySelector("#gameScreen").classList.remove("hidden");
      if (mode === "trigger") {
        latestState.rulesEngine.pendingChoice = { id: "tt1", kind: "trigger_targets", playerId: "p1", sourceCardId: "d6jip43i66i34xk_en", targetRules: { kind: "player", min: 1, max: 1 } };
        renderAll();
      } else {
        renderAll();
        requestCardPlacement({ type: "place_card", fromZone: "hand", cardId: "7e2ppf4rfgkdfms_en", faceUp: true, x: 400, y: 700 });
      }
    }, mode);

    // Dark Apparition played from the hand: the player is picked before it is played
    await setup("placement");
    await page.waitForTimeout(300);
    assert.deepEqual(
      await page.evaluate(() => [...document.querySelectorAll("[data-rules-player-target]")].map((button) => [button.dataset.rulesPlayerTarget, button.disabled])),
      [["p1", false], ["p2", false]],
    );
    const opp = await page.evaluate(() => {
      const rect = document.querySelector("#ubField .ub-side.opp").getBoundingClientRect();
      return { x: rect.left + rect.width * .6, y: rect.top + rect.height * .35 };
    });
    await page.mouse.move(opp.x, opp.y, { steps: 4 });
    const hover = await page.evaluate(() => ({
      tag: document.getElementById("ubChoiceArrowTag")?.textContent,
      over: document.querySelector("#gameScreen").dataset.ubTargetOver,
      oppLit: document.querySelector("#ubField .ub-side.opp").classList.contains("ub-target-over"),
      meLit: document.querySelector("#ubField .ub-side.me").classList.contains("ub-target-over"),
    }));
    assert.deepEqual(hover, { tag: "Cibler Bot KKO", over: "opp", oppLit: true, meLit: false });
    if (process.env.SCREENSHOT_DIR) await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, "player-target-hover.png") });
    await page.mouse.click(opp.x, opp.y);
    await page.waitForTimeout(200);
    const sent = await page.evaluate(() => window.__sent);
    assert.equal(sent.length, 1, JSON.stringify(sent));
    assert.equal(sent[0].type, "declare_rules_action");
    assert.deepEqual(sent[0].targets, [{ kind: "player", playerId: "p2" }]);
    assert.equal(await page.evaluate(() => { renderAll(); return document.getElementById("ubChoiceArrowTag"); }), null);

    // a triggered effect waiting for its player (server choice) still answers
    await setup("trigger");
    await page.waitForTimeout(300);
    await page.mouse.move(opp.x, opp.y, { steps: 4 });
    await page.mouse.click(opp.x, opp.y);
    await page.waitForTimeout(200);
    assert.deepEqual(await page.evaluate(() => window.__sent), [
      { type: "resolve_rules_choice", choiceId: "tt1", targets: [{ kind: "player", playerId: "p2" }] },
    ]);
    assert.deepEqual(errors, []);
    console.log("player target choice: ok");
  } finally {
    await browser.close();
    server.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
