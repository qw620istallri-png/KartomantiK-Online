// Manual play: the Confrontation total counts only the Manifestations really in
// the Confrontation Zone, not a card floating on an Interzone card nor a card
// waiting in the Stack (both can keep coordinates over the CZ). The pile
// browser leaves the inspect column visible.
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
  try {
    for (const viewport of [{ width: 1440, height: 900 }, { width: 1024, height: 768 }]) {
      const page = await browser.newPage({ viewport });
      const errors = [];
      page.on("pageerror", error => errors.push(error.message));
      await page.route("**/*", route => new URL(route.request().url()).hostname === "127.0.0.1" ? route.continue() : route.abort());
      await page.goto(`http://127.0.0.1:${server.address().port}/`);
      await page.waitForFunction(() => cardsById.size === 450 && typeof renderAll === "function");
      const expected = await page.evaluate(() => {
        myPlayerId = "p1"; isObserver = false;
        const zones = () => Object.fromEntries(ZONES.map(key => [key, { cards: [], owners: {} }]));
        const manifs = [...cardsById.values()].filter(card => card.type === "manifestation" && Number(card.power) > 0).slice(0, 4);
        for (const entry of cardsById.values()) entry.image = "card-back.webp";
        latestState = { players: {
          p1: { id: "p1", name: "Alpha", seat: 0, score: 10, zones: zones() },
          p2: { id: "p2", name: "Beta", seat: 1, score: 10, zones: zones() }
        }, tokens: [], drawings: [],
          phaseTracker: { enabled: true, advanced: true, turn: 2, index: 5, passedPlayerIds: [] },
          rulesEngine: { enabled: false, actionStack: [], firstManifestationItemIds: {} } };
        latestState.players.p1.zones.graveyard.cards = manifs.map(card => card.id);
        const base = { ownerId: "p1", faceUp: true, counters: {}, rotation: 0 };
        latestState.battlefield = [
          { ...base, id: "cz", cardId: manifs[0].id, x: 445, y: 800 },
          { ...base, id: "iz", cardId: manifs[1].id, x: 445, y: 1064 },
          // floats on the Interzone card but its own coordinates lie over the CZ
          { ...base, id: "float", cardId: manifs[2].id, x: 660, y: 800, stackedOn: "iz" },
          // waiting in the manual Stack, coordinates over the CZ as well
          { ...base, id: "stack", cardId: manifs[3].id, x: 875, y: 800, manualStack: true },
        ];
        document.querySelector("#joinScreen").classList.add("hidden");
        document.querySelector("#gameScreen").classList.remove("hidden");
        renderAll();
        return Number(manifs[0].power);
      });
      const total = await page.evaluate(() => ({
        fn: confrontationPowerOf("p1"),
        shown: Number(document.querySelector("#ubTotals .ub-total.me .ub-pw").textContent),
      }));
      assert.equal(total.fn, expected, `${viewport.width}: only the CZ Manifestation counts`);
      assert.equal(total.shown, expected, `${viewport.width}: the totals band shows it`);
      // A card floating on the CZ Manifestation stays in the CZ.
      const withCzFloat = await page.evaluate(() => {
        latestState = structuredClone(latestState);
        latestState.battlefield.find(item => item.id === "float").stackedOn = "cz";
        renderAll();
        return confrontationPowerOf("p1");
      });
      assert.ok(withCzFloat > expected, `${viewport.width}: a float on a CZ card still counts`);
      // Pile browser with a card open in the inspect column.
      await page.evaluate(() => { showInspect(latestState.players.p1.zones.graveyard.cards[0]); openPileBrowser("p1", "graveyard"); });
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const layout = await page.evaluate(() => {
        const inspect = document.querySelector("#inspectPanel .box").getBoundingClientRect();
        const browserPanel = document.querySelector("#deckBrowserPanel").getBoundingClientRect();
        const box = document.querySelector("#deckBrowserPanel .box").getBoundingClientRect();
        const hit = document.elementFromPoint(inspect.left + inspect.width / 2, inspect.top + inspect.height / 2);
        return { inspectRight: inspect.right, panelLeft: browserPanel.left, boxRight: box.right, inspectOnTop: Boolean(hit?.closest("#inspectPanel")) };
      });
      assert.ok(layout.panelLeft >= layout.inspectRight - 1, `${viewport.width}: pile browser starts after the inspect column`);
      assert.ok(layout.boxRight <= viewport.width + 1, `${viewport.width}: pile browser fits the screen`);
      assert.equal(layout.inspectOnTop, true, `${viewport.width}: inspect column stays visible`);
      if (process.env.SHOTS) await page.screenshot({ path: path.join(process.env.SHOTS, `pile-${viewport.width}.png`) });
      // Without the inspect column the browser takes the whole screen again.
      await page.evaluate(() => { document.querySelector("#inspectPanel").classList.add("hidden"); });
      assert.equal(await page.evaluate(() => document.querySelector("#deckBrowserPanel").getBoundingClientRect().left), 0);
      assert.deepEqual(errors, []);
      reports.push({ viewport: viewport.width, total: total.fn, withCzFloat, layout });
      await page.close();
    }
    console.log(JSON.stringify(reports));
  } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
})().catch(error => { console.error(error); process.exitCode = 1; });
