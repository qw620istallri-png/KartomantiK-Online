const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("playwright");

(async () => {
  const root = path.resolve(__dirname, "../public");
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, "http://localhost");
    const file = path.resolve(root, "." + (url.pathname === "/" ? "/index.html" : decodeURIComponent(url.pathname)));
    if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return res.writeHead(404).end();
    res.setHeader("Content-Type", ({ ".js": "text/javascript", ".css": "text/css", ".html": "text/html", ".json": "application/json" })[path.extname(file)] || "application/octet-stream");
    fs.createReadStream(file).pipe(res);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const reports = [];
  try {
    for (const config of [{ width: 1440, height: 1000, theme: "dark" }, { width: 1280, height: 720, theme: "sand" }, { width: 844, height: 390, theme: "dark" }]) {
      const page = await browser.newPage({ viewport: { width: config.width, height: config.height } });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.route("**/*", (route) => new URL(route.request().url()).hostname === "127.0.0.1" ? route.continue() : route.abort());
      await page.goto(`http://127.0.0.1:${server.address().port}/`);
      await page.waitForFunction(() => cardsById.size === 450 && typeof document.querySelector("#rarityEffectsToggleBtn").onclick === "function");
      await page.evaluate((theme) => {
        for (const card of cardsById.values()) card.image = "card-back.webp";
        const zone = () => ({ cards: [], count: 0, owners: {} });
        const player = (id, seat) => ({ id, name: id, seat, score: 0, zones: Object.fromEntries(ZONES.map((key) => [key, zone()])) });
        myPlayerId = "p1"; isObserver = false; connectionRole = "player";
        latestState = { players: { p1: player("p1", 0), p2: player("p2", 1) }, battlefield: [], tokens: [], drawings: [],
          phaseTracker: { enabled: true, advanced: true, index: 5, turn: 2, passedPlayerIds: [] },
          rulesEngine: { enabled: true, priorityPlayerId: "p1", actionStack: [], readyPlayerIds: ["p1", "p2"], firstManifestationComplete: true, deckConfirmedPlayerIds: ["p1", "p2"] } };
        window.__sent = []; send = (payload) => window.__sent.push(payload);
        document.querySelector("#joinScreen").classList.add("hidden");
        document.querySelector("#gameScreen").classList.remove("hidden");
        window.uiBeta.setEnabled(true);
        document.documentElement.dataset.ubTheme = theme;
        const source = [...cardsById.values()].find((card) => card.name === "Expansive Ponderer");
        latestState.rulesEngine.pendingChoice = { id: "ponderer", kind: "deck_reorder", playerId: "p1", sourceCardId: source.id,
          groups: [{ playerId: "p1", cardIds: [...cardsById.keys()].filter((id) => id !== source.id).slice(0, 7), extraSide: "hand", extraMin: 1, extraMax: 1 }] };
        renderAll();
      }, config.theme);
      const overflow = () => page.evaluate(() => [...document.querySelectorAll("#rulesChoicePanel, #rulesChoicePanel *")].filter((el) => {
        const css = getComputedStyle(el);
        return el.clientWidth > 0 && ((/auto|scroll/.test(css.overflowX) && el.scrollWidth > el.clientWidth + 2) || (/auto|scroll/.test(css.overflowY) && el.scrollHeight > el.clientHeight + 2));
      }).map((el) => `${el.id || el.className}: ${el.scrollWidth}x${el.scrollHeight}/${el.clientWidth}x${el.clientHeight}`));
      const states = [];
      const outsideViewport = [];
      const inspectLayout = async () => {
        states.push(await overflow());
        outsideViewport.push(...await page.evaluate(() => [...document.querySelectorAll("#rulesChoicePanel .rules-reorder-strip, #rulesDeckReorderConfirm")].filter((el) => {
          const rect = el.getBoundingClientRect();
          return rect.width > 0 && (rect.left < -2 || rect.right > innerWidth + 2 || rect.top < -2 || rect.bottom > innerHeight + 2);
        }).map((el) => el.dataset.rulesReorderStrip || el.id)));
      };
      const screenshot = async (name) => {
        if (!process.env.SCREENSHOT_DIR) return;
        fs.mkdirSync(process.env.SCREENSHOT_DIR, { recursive: true });
        await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `ponderer-${config.width}-${config.theme}-${name}.png`) });
      };
      await screenshot("empty");
      await inspectLayout();
      const minimumContrast = await page.evaluate(() => {
        const rgb = (value) => {
          const channels = value.match(/[\d.]+/g).map(Number).slice(0, 3);
          return value.startsWith("color(") ? channels : channels.map((channel) => channel / 255);
        };
        const luminance = (value) => rgb(value).map((v) => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4).reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0);
        return Math.min(...[...document.querySelectorAll(".rules-reorder-lane .rules-reorder-strip")].map((el) => {
          const css = getComputedStyle(el);
          const values = [luminance(css.borderTopColor), luminance(css.backgroundColor)].sort((a, b) => b - a);
          return (values[0] + .05) / (values[1] + .05);
        }));
      });
      for (let index = 0; index < 7; index++) {
        const card = await page.locator('[data-rules-reorder-strip="pool"] .rules-reorder-card').first().boundingBox();
        const side = index === 0 ? "extra" : "top";
        const lane = await page.locator(`[data-rules-reorder-strip="${side}"]`).boundingBox();
        await page.mouse.move(card.x + card.width / 2, card.y + card.height / 2);
        await page.mouse.down();
        await page.mouse.move(lane.x + lane.width * .7, lane.y + lane.height / 2, { steps: 12 });
        await page.waitForTimeout(170);
        await inspectLayout();
        if (index === 6) await screenshot("dragging");
        await page.mouse.up();
      }
      // Moving the last pool card must not collapse the layout while dragging.
      const counts = await page.evaluate(() => ({ top: document.querySelectorAll('[data-rules-reorder-strip="top"] .rules-reorder-card').length, hand: document.querySelectorAll('[data-rules-reorder-strip="extra"] .rules-reorder-card').length }));
      const report = { ...config, overflow: states.flat(), outsideViewport, minimumContrast, counts, errors };
      reports.push(report);
      if (!process.env.DIAGNOSE_ONLY) {
        assert.deepEqual(report.overflow, []);
        assert.deepEqual(outsideViewport, []);
        assert.ok(minimumContrast >= 3, JSON.stringify(report));
        assert.deepEqual(counts, { top: 6, hand: 1 });
        await page.locator("#rulesDeckReorderConfirm").click();
        assert.equal(await page.evaluate(() => window.__sent[0]?.option?.groups[0]?.extra?.length), 1);
        assert.deepEqual(errors, []);
      }
      await page.close();
    }
    console.log(JSON.stringify(reports));
    console.log("Ponderer drag regression: OK");
  } finally { await browser.close(); await new Promise((resolve) => server.close(resolve)); }
})().catch((error) => { console.error(error); process.exitCode = 1; });
