const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "../public");
const output = path.resolve(__dirname, "../reports/systematic-audit");
const mime = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json" };
(async () => {
  const server = http.createServer((req, res) => {
    const file = path.resolve(root, "." + (new URL(req.url, "http://localhost").pathname === "/" ? "/index.html" : decodeURIComponent(new URL(req.url, "http://localhost").pathname)));
    if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return res.writeHead(404).end();
    res.writeHead(200, { "Content-Type": mime[path.extname(file)] || "application/octet-stream" });
    fs.createReadStream(file).pipe(res);
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "chrome", headless: true });
  const reports = [];
  try {
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 844, height: 390 }]) {
      const page = await browser.newPage({ viewport });
      const errors = [];
      page.on("pageerror", error => errors.push(error.message));
      await page.route("**/*", route => new URL(route.request().url()).hostname === "127.0.0.1" ? route.continue() : route.abort());
      await page.goto(`http://127.0.0.1:${server.address().port}/`);
      await page.waitForFunction(() => cardsById.size === 450 && typeof document.querySelector("#rarityEffectsToggleBtn").onclick === "function");
      await page.evaluate(() => {
        myPlayerId = "p1"; isObserver = false;
        const zones = () => Object.fromEntries(ZONES.map(key => [key, { cards: [], owners: {} }]));
        latestState = { players: {
          p1: { id: "p1", name: "Alexandre des longues plaines", seat: 0, score: 10, zones: zones() },
          p2: { id: "p2", name: "Camille des dunes lointaines", seat: 1, score: 10, zones: zones() }
        }, battlefield: [], tokens: [], drawings: [],
          phaseTracker: { enabled: true, advanced: true, turn: 2, index: 5, passedPlayerIds: [] },
          rulesEngine: { enabled: false, actionStack: [], firstManifestationItemIds: {} } };
        const card = [...cardsById.values()].find(card => card.type === "manifestation" && Number(card.points) === 20);
        const other = [...cardsById.values()].find(card => card.type === "manifestation" && Number(card.points) === 30);
        if (!card || !other) throw new Error("Expected real 20/30-point cards");
        for (const entry of cardsById.values()) entry.image = "card-back.webp";
        latestState.battlefield = [
          { id: "a", cardId: card.id, ownerId: "p1", controllerId: "p2" },
          { id: "b", cardId: other.id, ownerId: "p2" },
          { id: "c", cardId: card.id, ownerId: "p2" }
        ].map(item => ({ ...item, faceUp: true, fieldZone: "stalemate", x: 500, y: 300, counters: {}, rotation: 0 }));
        document.querySelector("#joinScreen").classList.add("hidden");
        document.querySelector("#gameScreen").classList.remove("hidden");
        window.uiBeta.setEnabled(true); renderAll();
      });
      const prefix = process.env.BASELINE ? "stalemate-before" : "stalemate";
      await page.screenshot({ path: path.join(output, `${prefix}-${viewport.width}.png`) });
      if (process.env.BASELINE) { await page.close(); continue; }
      for (const seat of ["p1", "p2"]) {
        await page.evaluate(seat => { myPlayerId = seat; renderAll(); }, seat);
        const totals = await page.locator("#ubStaleStrip [data-stale-player]").evaluateAll(nodes => Object.fromEntries(nodes.map(n => [n.dataset.stalePlayer, Number(n.querySelector("b").textContent)])));
        assert.deepEqual(totals, { p1: 20, p2: 50 });
        const clear = await page.evaluate(() => {
          const summary = document.querySelector(".ub-stale-summary").getBoundingClientRect();
          const cards = [...document.querySelectorAll(".ub-stale-strip-card")].map(n => n.getBoundingClientRect());
          const more = document.querySelector("#ubStaleStrip .more").getBoundingClientRect();
          return cards.every(r => r.left >= summary.right && r.right <= more.left)
            && [...document.querySelectorAll(".ub-stale-player b")].every(n => n.getBoundingClientRect().width > 0);
        });
        assert.equal(clear, true, "Cards must not overlap totals or enlarge control");
      }
      // The board routes a real click to the strip underneath it.
      const strip = await page.locator("#ubStaleStrip").boundingBox();
      await page.mouse.click(strip.x + 30, strip.y + 12);
      await page.locator("#ubStalePanel").waitFor({ state: "visible" });
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      await page.evaluate(() => Promise.all(document.getAnimations().filter(a => a.effect.getComputedTiming().iterations !== Infinity).map(a => a.finished.catch(() => {}))));
      await page.screenshot({ path: path.join(output, `stalemate-open-${viewport.width}.png`) });
      assert.deepEqual(await page.locator("#ubStalePanel [data-stale-player]").evaluateAll(nodes => Object.fromEntries(nodes.map(n => [n.dataset.stalePlayer, Number(n.querySelector("b").textContent)]))), { p1: 20, p2: 50 });
      assert.equal(await page.evaluate(() => {
        const headings = [...document.querySelectorAll("#ubStalePanel h3")].map(n => n.getBoundingClientRect());
        return [...document.querySelectorAll(".bf-card.ub-stale-open")].every(n => n.getBoundingClientRect().top >= Math.max(...headings.map(r => r.bottom)));
      }), true, "Expanded cards must stay below the totals");
      // State refresh, rules mode, copies and a player with no cards.
      await page.evaluate(() => {
        latestState = structuredClone(latestState);
        latestState.rulesEngine.enabled = true;
        latestState.battlefield = latestState.battlefield.filter(item => item.ownerId === "p1");
        latestState.battlefield.push({ ...latestState.battlefield[0], id: "copy", ownerId: "p2", isCopy: true, isTokenCard: true, temperament: "hollow", power: 4 });
        renderAll();
      });
      assert.deepEqual(await page.locator("#ubStalePanel [data-stale-player]").evaluateAll(nodes => Object.fromEntries(nodes.map(n => [n.dataset.stalePlayer, Number(n.querySelector("b").textContent)]))), { p1: 20, p2: 0 });
      // Public observer view uses the same owner split.
      await page.evaluate(() => { isObserver = true; myPlayerId = null; renderAll(); });
      assert.deepEqual(await page.locator("#ubStalePanel [data-stale-player]").evaluateAll(nodes => Object.fromEntries(nodes.map(n => [n.dataset.stalePlayer, Number(n.querySelector("b").textContent)]))), { p1: 20, p2: 0 });
      await page.evaluate(() => { latestState.battlefield = []; renderAll(); });
      assert.equal(await page.locator("#ubStaleStrip").isVisible(), false);
      assert.equal(await page.locator("#ubStalePanel").isVisible(), false);
      assert.deepEqual(errors, []);
      reports.push({ viewport, seats: 2, observer: true, ownerTotals: true, copiesScoreZero: true, boardClickOpen: true, refreshAndEmpty: true, noOverlap: true });
      await page.close();
    }
    console.log(JSON.stringify(reports));
  } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
})().catch(error => { console.error(error); process.exitCode = 1; });
