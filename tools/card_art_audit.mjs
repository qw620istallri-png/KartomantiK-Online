// Real remote illustration responses and browser decoding; never substitute a back.
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const publicRoot = path.join(root, "public");
const out = path.join(root, "reports/systematic-audit");
const mime = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".css": "text/css", ".webp": "image/webp", ".png": "image/png", ".woff2": "font/woff2" };
const server = http.createServer((req, res) => {
  const relative = decodeURIComponent(new URL(req.url, "http://localhost").pathname);
  const file = path.resolve(publicRoot, "." + (relative === "/" ? "/index.html" : relative));
  if (!file.startsWith(publicRoot + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return res.writeHead(404).end();
  res.writeHead(200, { "Content-Type": mime[path.extname(file)] || "application/octet-stream" });
  fs.createReadStream(file).pipe(res);
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "chrome", headless: true });
const report = { schemaVersion: 1, startedAt: new Date().toISOString(), browser: browser.version(), platform: process.platform,
  physicalDevice: false, substitutedArt: false, cards: [], supplemental: [], errors: [] };
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.on("pageerror", e => report.errors.push(e.message));
  const responses = new Map(), bodies = [];
  page.on("response", response => {
    if (response.request().resourceType() !== "image" || !response.url().startsWith("https://")) return;
    let first = response.request();
    while (first.redirectedFrom()) first = first.redirectedFrom();
    const record = { status: response.status(), finalUrl: response.url(), contentType: response.headers()["content-type"] };
    responses.set(first.url(), record);
    bodies.push(response.body().then(body => {
      record.bytes = body.length;
      record.sha256 = crypto.createHash("sha256").update(body).digest("hex");
    }).catch(e => { record.bodyError = e.message; }));
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/`, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => cardsById.size === 450);
  const cards = await page.evaluate(() => [...cardsById.values()].map(c => ({ cardId: c.id, name: c.name, url: cardImage(c.id) })));
  const extra = await page.evaluate(() => [{ assetId: "missing-card-fallback", url: MISSING_CARD_IMAGE }]);
  report.manifestDigest = crypto.createHash("sha256").update(JSON.stringify(cards)).digest("hex");
  report.inputHashes = Object.fromEntries(["public/cards-data.json", "public/extensions/inner-desert/cards.json", "public/js/cards.js", "public/app.js"].map(file => [file, crypto.createHash("sha256").update(fs.readFileSync(path.join(root, file))).digest("hex")]));
  for (let offset = 0; offset < cards.length + extra.length; offset += 8) {
    const entries = [...cards, ...extra].slice(offset, offset + 8);
    const decoded = await page.evaluate(entries => Promise.all(entries.map(entry => new Promise(resolve => {
      const image = new Image(), start = performance.now();
      let complete = false;
      const finish = (status, error = null) => {
        if (complete) return;
        complete = true; clearTimeout(timer);
        resolve({ ...entry, status, error, width: image.naturalWidth, height: image.naturalHeight, milliseconds: Math.round(performance.now() - start) });
      };
      const timer = setTimeout(() => finish("fail", "timeout"), 25000);
      image.onload = async () => { try { await image.decode(); finish(image.naturalWidth && image.naturalHeight ? "pass" : "fail"); } catch(e) { finish("fail", String(e)); } };
      image.onerror = () => finish("fail", "image-error");
      image.src = entry.url;
    }))), entries);
    for (const entry of decoded) (entry.cardId ? report.cards : report.supplemental).push(entry);
    if (offset % 80 === 0) console.log(JSON.stringify({ decoded: report.cards.length, failures: report.cards.filter(c => c.status !== "pass").length }));
  }
  await Promise.allSettled(bodies);
  for (const entry of [...report.cards, ...report.supplemental]) {
    entry.response = responses.get(new URL(entry.url, page.url()).href) || null;
    if (entry.response && (entry.response.status < 200 || entry.response.status >= 400)) entry.status = "fail";
  }
  const hashes = new Map();
  for (const entry of report.cards) {
    const hash = entry.response?.sha256;
    if (!hash) continue;
    if (!hashes.has(hash)) hashes.set(hash, []);
    hashes.get(hash).push(entry.cardId);
  }
  report.identicalBodies = [...hashes].filter(([, ids]) => ids.length > 1).map(([sha256, cardIds]) => ({ sha256, cardIds }));
  report.summary = { cards: report.cards.length, passed: report.cards.filter(c => c.status === "pass").length,
    failed: report.cards.filter(c => c.status !== "pass").length, supplementalFailed: report.supplemental.filter(c => c.status !== "pass").length,
    identicalBodyGroups: report.identicalBodies.length, pageErrors: report.errors.length };
  report.finishedAt = new Date().toISOString();
  report.limitations = ["Automated Chrome on Windows, not a physical phone or Safari iOS test.", "Transport, MIME, dimensions and hashes do not independently prove that an illustration depicts the intended card."];
  fs.mkdirSync(out, { recursive: true });
  fs.writeFileSync(path.join(out, "remote-art.json"), JSON.stringify(report, null, 2) + "\n");
  console.log(JSON.stringify(report.summary));
  if (report.summary.failed || report.summary.supplementalFailed || report.errors.length) process.exitCode = 1;
} finally { await browser.close(); server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
