import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { spawn } from "node:child_process";
import { chromium } from "playwright";


const root = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/(?:[A-Za-z]:)/, (m) => m.slice(1))), "..");
const manifestPath = path.join(root, "reports", "card-scenario-manifest.json");
const outputPath = path.join(root, "reports", "card-browser-results.json");
const port = Number(process.env.KKO_BROWSER_TEST_PORT || 8796);
const baseUrl = `http://127.0.0.1:${port}`;
const chromeCandidates = [
  process.env.KKO_CHROME,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
].filter(Boolean);
const chromePath = chromeCandidates.find((candidate) => fs.existsSync(candidate));

if (!chromePath) throw new Error("Google Chrome est introuvable pour les scénarios client.");
if (!fs.existsSync(manifestPath)) throw new Error("Le manifeste des scénarios est absent.");

const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
const server = spawn("py", ["-B", "server/main.py"], {
  cwd: root,
  env: { ...process.env, KKO_SANDBOX: "1", HOST: "127.0.0.1", PORT: String(port) },
  windowsHide: true,
  stdio: "ignore",
});

async function waitForServer() {
  let lastError;
  for (let attempt = 0; attempt < 80; attempt += 1) {
    try {
      const response = await fetch(`${baseUrl}/sandbox/index.json`);
      if (response.ok) return;
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 125));
  }
  throw new Error(`Le serveur de sandbox ne répond pas : ${lastError || "timeout"}`);
}

let browser;
try {
  await waitForServer();
  browser = await chromium.launch({
    headless: true,
    executablePath: chromePath,
    args: ["--disable-gpu", "--no-first-run", "--disable-background-networking"],
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const pageErrors = [];
  let currentCard = null;
  page.on("pageerror", (error) => pageErrors.push({ cardId: currentCard, message: error.message }));
  page.on("console", (message) => {
    if (message.type() === "error") pageErrors.push({ cardId: currentCard, message: message.text() });
  });

  const first = manifest.cards[0];
  await page.goto(`${baseUrl}/?sandbox=${encodeURIComponent(first.cardId)}`, {
    waitUntil: "domcontentloaded", timeout: 30_000,
  });
  await page.waitForSelector("#sandboxPanel .sb-current h2", { timeout: 30_000 });

  const cards = [];
  for (let index = 0; index < manifest.cards.length; index += 1) {
    const card = manifest.cards[index];
    currentCard = card.cardId;
    const errorStart = pageErrors.length;
    const started = Date.now();
    const failures = [];
    try {
      if (index > 0) {
        await page.evaluate((cardId) => {
          if (typeof window.send !== "function") throw new Error("La fonction client send() est absente.");
          window.send({ type: "sandbox_load", cardId });
        }, card.cardId);
      }
      await page.waitForFunction(
        ({ name }) => document.querySelector("#sandboxPanel .sb-current h2")?.textContent?.includes(name),
        { name: card.name }, { timeout: 10_000 },
      );
      await page.waitForTimeout(35);
      const rendered = await page.evaluate(({ cardId, name }) => {
        const hand = [...document.querySelectorAll("[data-hand-card]")]
          .some((element) => element.dataset.handCard === cardId);
        const battlefield = Boolean(
          document.querySelector('#battlefield .bf-card[data-item-id="tested"]')
          || [...document.querySelectorAll("#battlefield .bf-card img")]
            .some((image) => image.alt === name || image.title === name || image.src.includes(cardId))
        );
        const publicZone = [...document.querySelectorAll("[data-zone-card]")]
          .some((element) => String(element.dataset.zoneCard || "").endsWith(`:${cardId}`));
        const scenarioId = document.querySelector("#sandboxPanel .sb-current select")?.value || null;
        return {
          renderedIn: hand ? "main" : battlefield ? "plateau" : publicZone ? "zone publique" : null,
          scenarioId,
        };
      }, card);
      if (!rendered.renderedIn) failures.push("la carte n'est rendue ni dans la main, ni sur le plateau, ni dans une zone publique");
      const ownErrors = pageErrors.slice(errorStart).map((entry) => entry.message);
      failures.push(...ownErrors);
      cards.push({
        cardId: card.cardId, name: card.name, number: card.number, batch: card.batch,
        scenarioId: rendered.scenarioId, renderedIn: rendered.renderedIn,
        ok: failures.length === 0, failures, durationMs: Date.now() - started,
      });
    } catch (error) {
      failures.push(error.message);
      cards.push({
        cardId: card.cardId, name: card.name, number: card.number, batch: card.batch,
        scenarioId: null, renderedIn: null, ok: false, failures,
        durationMs: Date.now() - started,
      });
    }
  }
  const result = {
    summary: {
      cards: cards.length,
      passed: cards.filter((card) => card.ok).length,
      failed: cards.filter((card) => !card.ok).length,
      batches: Math.ceil(cards.length / 10),
      browser: "Google Chrome via Playwright",
    },
    cards,
  };
  fs.writeFileSync(outputPath, `${JSON.stringify(result, null, 2)}\n`, "utf8");
  console.log(JSON.stringify(result.summary));
  process.exitCode = result.summary.failed ? 1 : 0;
} finally {
  if (browser) await browser.close();
  server.kill();
}
