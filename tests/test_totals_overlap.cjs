// Floating essences and the "+" essence button must never sit on the turn
// counter (they stopped taking clicks on small or squarish screens). The totals
// band measures itself and moves the essences to a second row when needed.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "../public");
const mime = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json" };
(async () => {
  const server = http.createServer((req, res) => {
    const pathname = new URL(req.url, "http://localhost").pathname;
    const file = path.resolve(root, "." + (pathname === "/" ? "/index.html" : decodeURIComponent(pathname)));
    if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return res.writeHead(404).end();
    res.writeHead(200, { "Content-Type": mime[path.extname(file)] || "application/octet-stream" });
    fs.createReadStream(file).pipe(res);
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "chrome", headless: true });
  const reports = [];
  const frames = page => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const audit = page => page.evaluate(() => {
    const turnNode = document.querySelector("#ubTotals .ub-turn");
    const turn = turnNode.getBoundingClientRect();
    const reachable = node => {
      const r = node.getBoundingClientRect();
      const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return Boolean(hit && (hit === node || node.contains(hit)));
    };
    const controls = [...document.querySelectorAll("#ubTotals [data-essence-quick-add], #ubTotals .ub-ess > *")];
    const overlaps = controls.filter(node => {
      const r = node.getBoundingClientRect();
      return r.left < turn.right && r.right > turn.left && r.top < turn.bottom && r.bottom > turn.top;
    }).length;
    return {
      controls: controls.length,
      overlaps,
      unreachable: controls.filter(node => !reachable(node)).length,
      turnReachable: reachable(turnNode),
      stacked: document.querySelector("#gameScreen").classList.contains("ub-totals-stack"),
      crowded: document.querySelector("#ubTotals").classList.contains("ub-totals-crowded"),
    };
  });
  try {
    for (const viewport of [{ width: 1920, height: 1200 }, { width: 1440, height: 900 }, { width: 1366, height: 768 }, { width: 1024, height: 768 }, { width: 1000, height: 1000 }, { width: 844, height: 390 }, { width: 740, height: 360 }]) {
      const page = await browser.newPage({ viewport });
      const errors = [];
      page.on("pageerror", error => errors.push(error.message));
      await page.route("**/*", route => new URL(route.request().url()).hostname === "127.0.0.1" ? route.continue() : route.abort());
      await page.goto(`http://127.0.0.1:${server.address().port}/`);
      await page.waitForFunction(() => cardsById.size === 450 && typeof renderAll === "function");
      await page.evaluate(() => {
        myPlayerId = "p1"; isObserver = false;
        const zones = () => Object.fromEntries(ZONES.map(key => [key, { cards: [], owners: {} }]));
        latestState = { players: {
          p1: { id: "p1", name: "Gobres des longues plaines", seat: 0, score: 10, zones: zones() },
          p2: { id: "p2", name: "Prato", seat: 1, score: 10, zones: zones() }
        }, battlefield: [], tokens: [], drawings: [],
          phaseTracker: { enabled: true, advanced: true, turn: 1, index: 5, passedPlayerIds: [] },
          rulesEngine: { enabled: false, actionStack: [], firstManifestationItemIds: {} } };
        for (const entry of cardsById.values()) entry.image = "card-back.webp";
        const manifs = [...cardsById.values()].filter(card => card.type === "manifestation").slice(0, 2);
        latestState.battlefield = manifs.map((card, index) => ({ id: `m${index}`, cardId: card.id, ownerId: index ? "p2" : "p1", fieldZone: "confrontation", faceUp: true, x: 500, y: 300, counters: {}, rotation: 0 }));
        document.querySelector("#joinScreen").classList.add("hidden");
        document.querySelector("#gameScreen").classList.remove("hidden");
        renderAll();
      });
      await frames(page);
      const empty = await audit(page);
      // A token stands beside a Manifestation at the very same size (compact cards).
      await page.evaluate(() => {
        latestState = structuredClone(latestState);
        latestState.battlefield.push({ id: "tk", isTokenCard: true, temperament: "choleric", power: 1, ownerId: "p2", fieldZone: "confrontation", faceUp: true, x: 500, y: 300, counters: {}, rotation: 0 });
        renderAll();
      });
      await frames(page);
      await page.evaluate(() => Promise.all(document.getAnimations().filter(a => a.effect.getComputedTiming().iterations !== Infinity).map(a => a.finished.catch(() => {}))));
      const sizes = await page.evaluate(() => Object.fromEntries(["m1", "tk"].map(id => {
        const r = document.querySelector(`.bf-card[data-item-id="${id}"]`).getBoundingClientRect();
        return [id, [Math.round(r.width), Math.round(r.height)]];
      })));
      assert.deepEqual(sizes.tk, sizes.m1, `${viewport.width}x${viewport.height}: token and Manifestation share one size`);
      // Three essence colours for the active player, one for the opponent.
      await page.evaluate(() => {
        latestState = structuredClone(latestState);
        latestState.tokens = ["choleric", "phlegmatic", "melancholic"].map((temperament, index) => ({ id: `e${index}`, ownerId: "p1", isEssence: true, temperament, counters: { essence: 12 }, x: 0, y: 0 }))
          .concat([{ id: "e9", ownerId: "p2", isEssence: true, temperament: "choleric", counters: { essence: 1 }, x: 0, y: 0 }]);
        renderAll();
      });
      await frames(page);
      const full = await audit(page);
      assert.equal(full.controls, 5, `${viewport.width}x${viewport.height}: + button and four essences rendered`);
      assert.equal(full.overlaps, 0, `${viewport.width}x${viewport.height}: nothing may sit on the turn counter`);
      assert.equal(full.unreachable, 0, `${viewport.width}x${viewport.height}: every essence control takes clicks`);
      assert.equal(full.turnReachable, true, `${viewport.width}x${viewport.height}: turn counter stays visible`);
      assert.equal(full.crowded, false, `${viewport.width}x${viewport.height}: a layout without overlap was found`);
      // The band and the board agree: the second row is reserved by the geometry.
      assert.equal(await page.evaluate(() => {
        const totals = document.querySelector("#ubTotals").getBoundingClientRect();
        return [...document.querySelectorAll("#ubTotals .ub-ess > *")].every(node => node.getBoundingClientRect().bottom <= totals.bottom + 1);
      }), true, `${viewport.width}x${viewport.height}: essences stay inside the band`);
      // A real click still reaches a floating essence (removes one).
      await page.evaluate(() => { window.__sent = []; const original = window.send; window.send = (...args) => { window.__sent.push(args); }; window.__restoreSend = () => { window.send = original; }; });
      const button = await page.locator('#ubTotals [data-remove-essence="melancholic"]').boundingBox();
      await page.mouse.click(button.x + button.width / 2, button.y + button.height / 2);
      // Back to no essences: a wide screen returns to the single row.
      await page.evaluate(() => { window.__restoreSend(); latestState = structuredClone(latestState); latestState.tokens = []; renderAll(); });
      await frames(page);
      const back = await audit(page);
      if (viewport.width / viewport.height > 1.45 && viewport.height >= 520) {
        assert.equal(empty.stacked, false, `${viewport.width}x${viewport.height}: one row without essences`);
        assert.equal(back.stacked, false, `${viewport.width}x${viewport.height}: back to one row`);
      }
      assert.deepEqual(errors, []);
      reports.push({ viewport: `${viewport.width}x${viewport.height}`, stacked: full.stacked, overlaps: full.overlaps, unreachable: full.unreachable });
      await page.close();
    }
    console.log(JSON.stringify(reports));
  } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
})().catch(error => { console.error(error); process.exitCode = 1; });
