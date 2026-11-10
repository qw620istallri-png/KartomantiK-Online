const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "..", "public");
const output = path.resolve(__dirname, "..", "reports", "compact-board-real");
const mime = { ".css": "text/css", ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".png": "image/png", ".webp": "image/webp", ".ttf": "font/ttf", ".woff2": "font/woff2" };

function server() {
  return new Promise((resolve) => {
    const instance = http.createServer((request, response) => {
      const pathname = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
      const relative = pathname === "/" ? "index.html" : pathname.replace(/^\/+/, "");
      const file = path.resolve(root, relative);
      if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return response.writeHead(404).end("Not found");
      response.writeHead(200, { "Content-Type": mime[path.extname(file)] || "application/octet-stream" });
      fs.createReadStream(file).pipe(response);
    });
    instance.listen(0, "127.0.0.1", () => resolve(instance));
  });
}

const cases = [
  { name: "desktop-1", width: 1440, height: 1000, count: 1 },
  { name: "desktop-2", width: 1440, height: 1000, count: 2 },
  { name: "desktop-4", width: 1440, height: 1000, count: 4 },
  { name: "desktop-8", width: 1440, height: 1000, count: 8 },
  { name: "tablet-6", width: 1024, height: 768, count: 6 },
  { name: "phone-portrait-4", width: 390, height: 844, count: 4 },
  { name: "phone-landscape-5", width: 844, height: 390, count: 5 },
];

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const web = await server();
  const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "chrome", headless: true });
  const metrics = [];
  try {
    for (const capture of cases) {
      const phone = capture.name.startsWith("phone-");
      const page = await browser.newPage({ viewport: { width: capture.width, height: capture.height }, locale: "fr-FR", hasTouch: phone, isMobile: phone });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.goto(`http://127.0.0.1:${web.address().port}/`, { waitUntil: "networkidle" });
      await page.waitForFunction(() => typeof renderAll === "function" && window.uiBeta?.compactCardsEnabled?.() && cardsById.size >= 450);
      await page.evaluate(({ count }) => {
        connectionMode = "casual";
        connectionRole = "player";
        isObserver = false;
        myPlayerId = "p1";
        const zone = (cards = [], ownerId) => ({ cards, count: cards.length, owners: Object.fromEntries(cards.map((id) => [id, ownerId])) });
        const manifestations = [...cardsById.values()].filter((card) => card.type === "manifestation" && card.image);
        const wills = [...cardsById.values()].filter((card) => (card.type === "persistent_will" || card.type === "ephemeral_will") && card.image);
        const handCards = [
          manifestations[4], wills[3], manifestations[12], wills[7],
          manifestations[20], wills[11], manifestations[28],
        ].filter(Boolean).map((card) => card.id);
        const zones = (ownerId) => ({
          deck: { count: 31 },
          hand: ownerId === "p1" ? zone(handCards, ownerId) : { count: 7 },
          graveyard: zone([], ownerId),
          exile: zone([], ownerId),
          receptacle: zone([], ownerId),
        });
        const adamant = manifestations.find((card) => /(?:^|\n)Adamant\./i.test(String(card.originalEffect || card.effect || ""))) || manifestations[0];
        const rarity = [null, "foil", "silver", "gold", "desert", "galaxy", "void", "zen"];
        const battlefield = [];
        for (const [seat, ownerId] of ["p1", "p2"].entries()) {
          for (let index = 0; index < count; index += 1) {
            const card = index === 3 ? adamant : manifestations[(index + seat * 9) % manifestations.length];
            battlefield.push({ id: `${ownerId}-m-${index}`, ownerId, controllerId: ownerId, cardId: card.id, faceUp: true, rotation: 0, counters: index === 5 ? { power: 2 } : {}, effectivePower: Number(card.power || 1) + (index === 5 ? 2 : 0), fieldZone: "confrontation", isSupport: index === 1, rarity: rarity[(index + seat) % rarity.length], x: 500 + index * 10, y: ownerId === "p1" ? 800 : 525 });
          }
          const will = wills[seat % wills.length];
          battlefield.push({ id: `${ownerId}-will`, ownerId, controllerId: ownerId, cardId: will.id, faceUp: true, rotation: 0, counters: {}, fieldZone: "field", rarity: seat ? "zen" : "silver-glitter", x: 500, y: ownerId === "p1" ? 1300 : 45 });
          const interzone = manifestations[(seat + 17) % manifestations.length];
          battlefield.push({ id: `${ownerId}-iz`, ownerId, controllerId: ownerId, cardId: interzone.id, faceUp: true, rotation: 0, counters: {}, fieldZone: "interzone", rarity: seat ? "desert" : "galaxy", x: 500, y: ownerId === "p1" ? 1064 : 285 });
          if (count >= 2) {
            const floatCard = manifestations[(seat + 25) % manifestations.length];
            battlefield.push({ id: `${ownerId}-float`, ownerId, controllerId: ownerId, cardId: floatCard.id, faceUp: true, rotation: 0, counters: {}, fieldZone: "confrontation", stackedOn: `${ownerId}-m-0`, rarity: "foil", x: 510, y: ownerId === "p1" ? 790 : 515 });
          }
        }
        latestState = {
          mode: "casual", ended: false,
          players: {
            p1: { id: "p1", name: "Istallri", seat: 0, score: 36, zones: zones("p1"), deckDefinition: { main: [] }, cardRarities: {} },
            p2: { id: "p2", name: "Adversaire", seat: 1, score: 31, zones: zones("p2"), deckDefinition: { main: [] }, cardRarities: {} },
          },
          battlefield, tokens: [], drawings: [], recentLog: [],
          phaseTracker: { enabled: true, advanced: true, index: ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_reaction"), turn: 5, passedPlayerIds: [] },
          rulesEngine: { enabled: true, priorityPlayerId: "p1", priorityPasses: [], passAllPlayerIds: [], actionStack: [], pendingChoice: null, ongoingEffects: [], firstManifestationItemIds: { p1: "p1-m-0", p2: "p2-m-0" }, firstManifestationValidatedPlayerIds: ["p1", "p2"], firstManifestationComplete: true, playPermissions: [], playRestrictions: [] },
        };
        document.querySelector("#joinScreen").classList.add("hidden");
        document.querySelector("#gameScreen").classList.remove("hidden");
        window.uiBeta.activate();
        renderAll();
      }, { count: capture.count });
      await page.waitForTimeout(1400);
      const sizes = await page.evaluate(() => [...document.querySelectorAll('.bf-card.ub-zone-confrontation:not(.ub-floating)')].map((card) => {
        const rect = card.getBoundingClientRect();
        return { id: card.dataset.itemId, width: Math.round(rect.width), height: Math.round(rect.height), compact: card.classList.contains("ub-card-compact") };
      }));
      metrics.push({ ...capture, sizes, errors });
      await page.screenshot({ path: path.join(output, `${capture.name}.png`), animations: "disabled" });
      await page.close();
    }
  } finally {
    await browser.close();
    web.close();
  }
  fs.writeFileSync(path.join(output, "metrics.json"), JSON.stringify({ engine: "chromium", physicalDevice: false, captures: metrics }, null, 2));
  if (metrics.some((entry) => entry.errors.length)) process.exitCode = 1;
})().catch((error) => { console.error(error); process.exitCode = 1; });
