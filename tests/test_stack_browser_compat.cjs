/* Real layout/decoding in Chromium and WebKit. Local art isolates geometry;
 * WebKit on Windows is not a certification of macOS Safari or its network.
 */
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium, webkit } = require("playwright");

const root = path.resolve(__dirname, "..");
const publicRoot = path.join(root, "public");
const out = path.resolve(root, process.env.KKO_STACK_COMPAT_OUTPUT || "reports/systematic-audit/safari-stack-followup");
const mime = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".webp": "image/webp", ".woff2": "font/woff2" };
const contains = (a, b, tolerance = 1.5) => b.left >= a.left - tolerance && b.top >= a.top - tolerance
  && b.right <= a.right + tolerance && b.bottom <= a.bottom + tolerance;
const sourceFiles = ["public/style.css", "public/ui-beta.css", "public/ui-beta.js", "public/index.html",
  "public/js/phases.js", "public/js/cards.js", "public/js/board.js", "tests/test_stack_browser_compat.cjs"];
const sourceHashes = () => Object.fromEntries(sourceFiles.map(file => [file,
  crypto.createHash("sha256").update(fs.readFileSync(path.join(root, file))).digest("hex")]));

(async () => {
  fs.mkdirSync(out, { recursive: true });
  const server = http.createServer((req, res) => {
    const pathname = decodeURIComponent(new URL(req.url, "http://localhost").pathname);
    const file = path.resolve(publicRoot, "." + (pathname === "/" ? "/index.html" : pathname));
    if (!file.startsWith(publicRoot + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return res.writeHead(404).end();
    res.writeHead(200, { "Content-Type": mime[path.extname(file)] || "application/octet-stream" });
    fs.createReadStream(file).pipe(res);
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const report = { schemaVersion: 1, physicalDevice: false, macOSSafari: false,
    startedAt: new Date().toISOString(), sourceHashes: sourceHashes(), cases: [] };
  try {
    for (const [engine, type] of [["chromium", chromium], ["webkit", webkit]]) {
      const browser = await type.launch(engine === "chromium" ? { channel: process.env.BROWSER_CHANNEL || "chrome", headless: true } : { headless: true });
      try {
        for (const viewport of [{ width: 1440, height: 1000 }, { width: 1280, height: 720 }]) {
          for (const flavor of ["classic-assisted", "beta-assisted", "beta-manual"]) {
          for (const profile of ["local", "remote-delayed-expanded"]) {
            const context = await browser.newContext({ viewport, locale: "fr-FR" });
            const page = await context.newPage();
            const row = { engine, version: browser.version(), viewport, flavor, profile, status: "fail" };
            const errors = [];
            page.on("pageerror", error => errors.push(error.message));
            try {
              const artUrls = new Set();
              await page.route("**/*", async route => {
                if (new URL(route.request().url()).hostname === "127.0.0.1") return route.continue();
                if (artUrls.has(route.request().url())) {
                  await new Promise(resolve => setTimeout(resolve, 350));
                  return route.continue();
                }
                return route.abort();
              });
              await page.goto(`http://127.0.0.1:${server.address().port}/`, { waitUntil: "load" });
              await page.waitForFunction(() => cardsById.size === 450 && typeof renderAll === "function" && window.uiBeta);
              if (profile !== "local") {
                const urls = await page.evaluate(() => [...cardsById.values()].slice(0, 4).map(card => new URL(card.image, location.href).href));
                urls.forEach(url => artUrls.add(url));
                row.artUrls = urls;
              }
              await page.evaluate(({ flavor, profile, artUrls }) => {
                document.querySelector("#joinScreen").classList.add("hidden");
                document.querySelector("#gameScreen").classList.remove("hidden");
                connectionMode = "casual"; connectionRole = "player"; myPlayerId = "p1"; isObserver = false;
                const zones = () => Object.fromEntries(ZONES.map(zone => [zone, { cards: [], owners: {}, entryVersions: {} }]));
                const assisted = flavor !== "beta-manual";
                const ids = Array.from({ length: 4 }, (_, n) => `stack-compat-${n}`);
                ids.forEach((id, n) => cardsById.set(id, {
                  id, name: `Carte de pile ${n + 1}`, type: "ephemeral_will", typeLabel: "Volonté Éphémère",
                  cost: 1, powerCost: "{H}", temperaments: ["hollow"], effect: "",
                  image: profile === "local" ? `card-back.webp?stack-compat=${n}` : artUrls[n],
                }));
                latestState = {
                  mode: "casual", ended: false, tournament: null,
                  players: { p1: { id: "p1", name: "P1", seat: 0, score: 50, zones: zones() }, p2: { id: "p2", name: "P2", seat: 1, score: 50, zones: zones() } },
                  battlefield: assisted ? [] : ids.map((cardId, n) => ({ id: `field-${n}`, cardId, ownerId: n % 2 ? "p2" : "p1",
                    faceUp: true, fieldZone: "field", rotation: 0, x: 500, y: 400, counters: {}, manualStack: n + 1 })),
                  tokens: [], strokes: [],
                  phaseTracker: { enabled: true, advanced: true, turn: 2, passedPlayerIds: [], index: ADVANCED_PHASES.findIndex(p => p.id === "confrontation_reaction") },
                  rulesEngine: { enabled: assisted, priorityPlayerId: "p2", priorityPasses: [], firstManifestationComplete: true,
                    firstManifestationItemIds: {}, readyPlayerIds: ["p1", "p2"], deckConfirmedPlayerIds: ["p1", "p2"],
                    ongoingEffects: [], playPermissions: [], pendingChoice: null,
                    actionStack: assisted ? ids.map((cardId, n) => ({ id: `action-${n}`, kind: "play_card", controllerId: n % 2 ? "p2" : "p1",
                      source: { cardId, zone: "hand" }, targets: [], turn: 2, phaseId: "confrontation_reaction" })) : [] },
                };
                uiBeta.setEnabled(flavor !== "classic-assisted");
                renderAll();
              }, { flavor, profile, artUrls: [...artUrls] });
              const selector = flavor === "beta-manual" ? "#ubManualStack .ub-mstack-card" : "#rulesStackList [data-stack-action-id]";
              await page.waitForFunction(selector => document.querySelectorAll(selector).length === 4, selector);
              if (profile !== "local") {
                // Re-render while cold images are in flight, then expand using the real control.
                await page.evaluate(() => renderAll());
                if (flavor !== "classic-assisted") await page.locator("#ubStack > header").click();
              }
              await page.waitForFunction(selector => [...document.querySelectorAll(`${selector} img`)].every(img => img.complete && img.naturalWidth > 0), selector);
              await page.waitForTimeout(500);
              row.metrics = await page.evaluate(selector => {
                const box = el => {
                  const r = el.getBoundingClientRect();
                  return { left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: r.width, height: r.height };
                };
                return [...document.querySelectorAll(selector)].map(el => {
                  const surface = el.querySelector(".rules-stack-card, .bf-card-face");
                  const image = surface.querySelector("img");
                  return { row: box(el), surface: box(surface), image: box(image), naturalWidth: image.naturalWidth,
                    opacity: getComputedStyle(image).opacity, visibility: getComputedStyle(image).visibility,
                    display: getComputedStyle(image).display, appearance: getComputedStyle(surface).appearance,
                    imagePosition: getComputedStyle(image).position, zoom: getComputedStyle(el).zoom };
                });
              }, selector);
              for (const item of row.metrics) {
                assert.ok(item.naturalWidth > 0 && Number(item.opacity) > .9 && item.visibility !== "hidden" && item.display !== "none", "decoded image must have visible styles");
                assert.ok(item.surface.width >= 35 && item.surface.width < 200 && item.surface.height >= 45 && item.surface.height < 280, "card must keep thumbnail dimensions");
                assert.ok(contains(item.row, item.surface, 4), "card surface must stay inside its row");
                assert.ok(contains(item.surface, item.image), "image must stay inside its card surface");
                assert.ok(Math.abs(item.image.width / item.image.height - 5 / 7) < .07, "image should preserve the card ratio");
              }
              assert.deepEqual(errors, []);
              row.status = "pass";
            } catch (error) {
              row.error = error.stack;
            }
            if (row.status === "fail" || (viewport.width === 1440 && flavor === "beta-assisted")) {
              const filename = `${engine}-${flavor}-${viewport.width}-${profile}.png`;
              await page.screenshot({ path: path.join(out, filename) });
              row.screenshot = filename;
            }
            report.cases.push(row);
            await context.close();
          }
          }
        }
      } finally { await browser.close(); }
    }
  } finally {
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
    report.summary = { executed: report.cases.length, failed: report.cases.filter(c => c.status !== "pass").length };
    report.finishedAt = new Date().toISOString();
    assert.deepEqual(sourceHashes(), report.sourceHashes, "client sources changed during the test");
    fs.writeFileSync(path.join(out, "browser.json"), JSON.stringify(report, null, 2) + "\n");
    console.log(JSON.stringify(report.summary));
    for (const row of report.cases.filter(c => c.status !== "pass")) console.log(row.engine, row.flavor, row.viewport.width, row.error);
  }
  assert.equal(report.summary.executed, 24);
  assert.equal(report.summary.failed, 0);
})().catch(error => { console.error(error); process.exitCode = 1; });
