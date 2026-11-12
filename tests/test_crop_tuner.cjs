// Compact cut: the four slice bounds drive both the CSS cut and the board
// ratio, the hand tuner (?crop-tuner) changes them live and keeps them in this
// browser, and the top slice always lies 1px over the bottom one.
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
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.route("**/*", route => new URL(route.request().url()).hostname === "127.0.0.1" ? route.continue() : route.abort());
    const url = `http://127.0.0.1:${server.address().port}/?crop-tuner`;
    await page.goto(url);
    await page.waitForFunction(() => cardsById.size >= 450 && document.getElementById("ubCropTuner"));
    const setup = () => page.evaluate(() => {
      myPlayerId = "p1"; isObserver = false;
      const zones = () => Object.fromEntries(ZONES.map(key => [key, { cards: [], owners: {} }]));
      latestState = { players: { p1: { id: "p1", name: "A", seat: 0, score: 10, zones: zones() }, p2: { id: "p2", name: "B", seat: 1, score: 10, zones: zones() } },
        tokens: [], drawings: [], phaseTracker: { enabled: true, advanced: true, turn: 2, index: 5, passedPlayerIds: [] }, rulesEngine: { enabled: false, actionStack: [], firstManifestationItemIds: {} } };
      const manif = [...cardsById.values()].find(card => card.type === "manifestation");
      const will = [...cardsById.values()].find(card => card.type === "persistent_will");
      const base = { ownerId: "p1", faceUp: true, counters: {}, rotation: 0 };
      latestState.battlefield = [{ ...base, id: "m", cardId: manif.id, x: 445, y: 800 }, { ...base, id: "w", cardId: will.id, x: 445, y: 1300 }];
      document.querySelector("#joinScreen").classList.add("hidden");
      document.querySelector("#gameScreen").classList.remove("hidden");
      renderAll();
    });
    await setup();
    const measure = () => page.evaluate(() => Object.fromEntries(["m", "w"].map(id => {
      const card = document.querySelector(`.bf-card[data-item-id="${id}"]`);
      const face = card.querySelector(".ub-compact-card-face");
      const top = face.querySelector(".ub-compact-crop-top").getBoundingClientRect();
      const bottom = face.querySelector(".ub-compact-crop-bottom").getBoundingClientRect();
      const f = face.getBoundingClientRect();
      const scale = f.width / 100;
      return [id, { ratio: f.height / f.width, overlapPx: (top.bottom - bottom.top) / (f.width / face.offsetWidth), filled: Math.abs(bottom.bottom - f.bottom) < 0.6 && Math.abs(top.top - f.top) < 0.6, scale }];
    })));
    const defaults = await page.evaluate(() => window.uiBeta.compactCrop.defaults());
    let m = await measure();
    const expected = (c) => ((c.topTo - c.topFrom) + (c.bottomTo - c.bottomFrom)) / 100 * 1.4;
    assert.ok(Math.abs(m.m.ratio - expected(defaults.manifestation)) < 0.01, "manifestation ratio follows the cut");
    assert.ok(Math.abs(m.w.ratio - expected(defaults.will)) < 0.01, "will ratio follows the cut");
    for (const id of ["m", "w"]) {
      assert.ok(Math.abs(m[id].overlapPx - 1) < 0.2, `${id}: top slice 1px over the bottom one`);
      assert.equal(m[id].filled, true, `${id}: the two slices fill the face`);
    }
    // Drive the tuner: Wills tab, bottom start 85.
    await page.click('#ubCropTuner [data-kind="will"]');
    await page.fill("#ubCrop-bottomFrom", "85");
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    m = await measure();
    const tuned = { ...defaults.will, bottomFrom: 85 };
    assert.ok(Math.abs(m.w.ratio - expected(tuned)) < 0.01, "the tuner changes the will cut live");
    assert.ok(Math.abs(m.m.ratio - expected(defaults.manifestation)) < 0.01, "manifestations untouched");
    // Kept in this browser after a reload.
    await page.goto(url.replace("?crop-tuner", ""));
    await page.waitForFunction(() => cardsById.size >= 450);
    await setup();
    m = await measure();
    assert.ok(Math.abs(m.w.ratio - expected(tuned)) < 0.01, "the saved cut applies after a reload");
    assert.equal(await page.evaluate(() => !document.getElementById("ubCropTuner")), true, "no tuner without ?crop-tuner");
    await page.evaluate(() => window.uiBeta.compactCrop.reset());
    m = await measure();
    assert.ok(Math.abs(m.w.ratio - expected(defaults.will)) < 0.01, "reset brings the defaults back");
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ ok: true, defaults }));
  } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
})().catch(error => { console.error(error); process.exitCode = 1; });
