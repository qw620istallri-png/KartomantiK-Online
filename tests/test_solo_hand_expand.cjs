// Solo: P2's enlarged hand lies flat across the field with every card
// readable, and hovering a P2 card shows no light frame (the zoom clone is a
// button and must not keep the button's padding, background or inset ring).
const assert = require("node:assert/strict");
const fs = require("node:fs"), http = require("node:http"), path = require("node:path");
const { chromium } = require("playwright");
const root = path.resolve(__dirname, "../public");
const mime = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json" };
(async () => {
  const server = http.createServer((req, res) => {
    const p = new URL(req.url, "http://x").pathname;
    const file = path.resolve(root, "." + (p === "/" ? "/index.html" : decodeURIComponent(p)));
    if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return res.writeHead(404).end();
    res.writeHead(200, { "Content-Type": mime[path.extname(file)] || "application/octet-stream" }); fs.createReadStream(file).pipe(res);
  });
  await new Promise(r => server.listen(0, "127.0.0.1", r));
  const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "chrome", headless: true });
  const reports = [];
  try {
    for (const [vw, vh, n] of [[1440, 900, 7], [1024, 768, 8], [1440, 900, 3]]) {
      const page = await browser.newPage({ viewport: { width: vw, height: vh } });
      const errors = []; page.on("pageerror", e => errors.push(e.message));
      await page.route("**/*", route => new URL(route.request().url()).hostname === "127.0.0.1" ? route.continue() : route.abort());
      await page.goto(`http://127.0.0.1:${server.address().port}/`);
      await page.waitForFunction(() => typeof cardsById !== "undefined" && cardsById.size >= 450);
      await page.evaluate((n) => {
        const ids = ["inner-deserts-066", "inner-deserts-124", "inner-deserts-115", "inner-deserts-147", "inner-deserts-001", "inner-deserts-066", "inner-deserts-124", "inner-deserts-115"].slice(0, n);
        const zone = (cards, ownerId) => ({ cards, count: cards.length, owners: Object.fromEntries(cards.map(c => [c, ownerId])) });
        const zones = (hand, o) => ({ hand: zone(hand, o), deck: zone([], o), graveyard: zone([], o), exile: zone([], o), receptacle: zone([], o) });
        myPlayerId = "solo:p1"; soloPrimaryPlayerId = "solo:p1"; soloControlledPlayerIds = ["solo:p1", "solo:p2"]; soloInteractionPlayerId = null;
        connectionMode = "solo"; connectionRole = "player"; isObserver = false;
        latestState = { type: "state", mode: "solo", solo: { enabled: true, controlledPlayerIds: [...soloControlledPlayerIds] },
          players: { "solo:p1": { id: "solo:p1", name: "P1", seat: 0, score: 0, zones: zones(ids.slice(0, 3), "solo:p1") }, "solo:p2": { id: "solo:p2", name: "P2", seat: 1, score: 0, zones: zones(ids, "solo:p2") } },
          battlefield: [], tokens: [], strokes: [], ended: false,
          phaseTracker: { enabled: true, advanced: true, turn: 2, index: 5, passedPlayerIds: [] },
          rulesEngine: { enabled: false, priorityPlayerId: "solo:p2", priorityPasses: [], actionStack: [], pendingChoice: null, deckConfirmedPlayerIds: ["solo:p1", "solo:p2"], readyPlayerIds: ["solo:p1", "solo:p2"], firstManifestationComplete: true }, recentLog: [] };
        ws = { readyState: WebSocket.OPEN, send: () => {} };
        document.querySelector("#joinScreen").classList.add("hidden");
        document.querySelector("#gameScreen").classList.remove("hidden");
        renderAll();
      }, n);
      await page.evaluate(() => { for (const entry of cardsById.values()) entry.image = "card-back.webp"; renderAll(); });
      await page.click("[data-ub-solo-toggle-hand]");
      await page.waitForTimeout(400);
      const info = await page.evaluate(() => {
        const cards = [...document.querySelectorAll("#opponentHandFan .opponent-hand-card")].map(n => n.getBoundingClientRect()).sort((a, b) => a.left - b.left);
        const overlaps = cards.slice(1).map((r, i) => Math.max(0, cards[i].right - r.left) / r.width);
        return { count: cards.length, w: cards[0].width, maxOverlap: Math.max(0, ...overlaps), left: Math.min(...cards.map(r => r.left)), right: Math.max(...cards.map(r => r.right)), top: Math.min(...cards.map(r => r.top)), rotated: cards.some(r => Math.abs(r.top - cards[0].top) > 2) };
      });
      assert.equal(info.count, n);
      assert.ok(info.maxOverlap <= 0.4, `${vw}x${vh}/${n}: every card shows at least 60% (${info.maxOverlap.toFixed(2)})`);
      assert.ok(info.left >= 0 && info.right <= vw && info.top >= 0, `${vw}x${vh}/${n}: the hand stays on screen`);
      assert.equal(info.rotated, false, `${vw}x${vh}/${n}: cards laid flat`);
      assert.ok(info.w >= 90, `${vw}x${vh}/${n}: cards large enough to read (${info.w})`);
      const third = page.locator("#opponentHandFan .opponent-hand-card").nth(Math.floor(n / 2));
      const box = await third.boundingBox();
      await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.5);
      await page.waitForTimeout(400);
      const clone = await page.evaluate(() => {
        const node = document.querySelector("body > .hand-card-hover-clone");
        if (!node) return null;
        const cs = getComputedStyle(node);
        return { padding: cs.paddingTop, shadow: cs.boxShadow, bg: cs.backgroundColor };
      });
      assert.ok(clone, "the hover zoom shows");
      assert.equal(clone.padding, "0px", "no button padding around the zoomed card");
      assert.ok(!/inset/.test(clone.shadow), "no light inset ring");
      assert.deepEqual(errors, []);
      reports.push({ viewport: `${vw}x${vh}`, n, w: Math.round(info.w), maxOverlap: Number(info.maxOverlap.toFixed(2)) });
      await page.close();
    }
    console.log(JSON.stringify(reports));
  } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
})().catch(error => { console.error(error); process.exitCode = 1; });
