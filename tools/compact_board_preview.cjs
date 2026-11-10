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
  { name: "tablet-square-essence", width: 1024, height: 900, count: 3, special: "square" },
  { name: "phone-portrait-4", width: 390, height: 844, count: 4 },
  { name: "phone-landscape-5", width: 844, height: 390, count: 5 },
  { name: "desktop-hover", width: 1320, height: 522, count: 2, hover: true },
  { name: "destination-hold", width: 1440, height: 1000, count: 4, hold: true },
  { name: "back-and-token", width: 1440, height: 1000, count: 2, special: "back-token" },
  { name: "bloatuba-reorder", width: 2048, height: 1152, count: 2, special: "bloatuba" },
  { name: "ponderer-reorder", width: 2048, height: 1152, count: 2, special: "ponderer" },
  { name: "simultaneous-order", width: 2048, height: 1152, count: 2, special: "order" },
];
const selectedCases = process.env.PREVIEW_CASE
  ? cases.filter((capture) => capture.name === process.env.PREVIEW_CASE)
  : cases;

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const web = await server();
  const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "chrome", headless: true });
  const metrics = [];
  try {
    for (const capture of selectedCases) {
      const phone = capture.name.startsWith("phone-");
      const page = await browser.newPage({ viewport: { width: capture.width, height: capture.height }, locale: "fr-FR", hasTouch: phone, isMobile: phone });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.goto(`http://127.0.0.1:${web.address().port}/`, { waitUntil: "networkidle" });
      await page.waitForFunction(() => typeof renderAll === "function" && window.uiBeta?.compactCardsEnabled?.() && cardsById.size >= 450);
      await page.evaluate(({ count, special }) => {
        connectionMode = "casual";
        connectionRole = "player";
        isObserver = false;
        myPlayerId = "p1";
        const zone = (cards = [], ownerId) => ({ cards, count: cards.length, owners: Object.fromEntries(cards.map((id) => [id, ownerId])) });
        const manifestations = [...cardsById.values()].filter((card) => card.type === "manifestation" && card.image);
        const wills = [...cardsById.values()].filter((card) => (card.type === "persistent_will" || card.type === "ephemeral_will") && card.image);
        const thoughtSaboteur = cardsById.get("ymcx9cg62eg0vgm_en");
        const handCards = [
          manifestations[4], wills[3], manifestations[12], thoughtSaboteur,
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
            const cropProbe = cardsById.get(seat ? "jh2nsqxr9x2ii1l_en" : "46id1c09q8inlkz_en");
            const card = index === 0 ? cropProbe : index === 3 ? adamant : manifestations[(index + seat * 9) % manifestations.length];
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
        if (special === "back-token") {
          battlefield.push({ id: "face-down-probe", ownerId: "p2", controllerId: "p2", cardId: manifestations[33].id, faceUp: false, rotation: 0, counters: {}, fieldZone: "interzone", x: 500, y: 285 });
          battlefield.push({ id: "token-probe", ownerId: "p1", controllerId: "p1", cardId: null, faceUp: true, rotation: 0, counters: {}, effectivePower: 1, power: 1, temperament: "phlegmatic", fieldZone: "confrontation", isTokenCard: true, isSupport: true, x: 550, y: 800 });
        }
        const tokens = special === "square" ? [
          { id: "ess-g", ownerId: "p1", isEssence: true, temperament: "phlegmatic", counters: { essence: 4 } },
          { id: "ess-h", ownerId: "p1", isEssence: true, temperament: "hollow", counters: { essence: 3 } },
          { id: "ess-b", ownerId: "p2", isEssence: true, temperament: "vitreous", counters: { essence: 5 } },
        ] : [];
        latestState = {
          mode: "casual", ended: false,
          players: {
            p1: { id: "p1", name: "Istallri", seat: 0, score: 36, zones: zones("p1"), deckDefinition: { main: [] }, cardRarities: {} },
            p2: { id: "p2", name: "Adversaire", seat: 1, score: 31, zones: zones("p2"), deckDefinition: { main: [] }, cardRarities: {} },
          },
          battlefield, tokens, drawings: [], recentLog: [],
          phaseTracker: { enabled: true, advanced: true, index: ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_reaction"), turn: 5, passedPlayerIds: [] },
          rulesEngine: { enabled: true, priorityPlayerId: "p1", priorityPasses: [], passAllPlayerIds: [], actionStack: [], pendingChoice: null, ongoingEffects: [], firstManifestationItemIds: { p1: "p1-m-0", p2: "p2-m-0" }, firstManifestationValidatedPlayerIds: ["p1", "p2"], firstManifestationComplete: true, playPermissions: [], playRestrictions: [] },
        };
        document.querySelector("#joinScreen").classList.add("hidden");
        document.querySelector("#gameScreen").classList.remove("hidden");
        window.uiBeta.activate();
        renderAll();
        if (special === "bloatuba") {
          latestState.rulesEngine.pendingChoice = { id: "bloatuba", kind: "deck_reorder", playerId: "p1", sourceCardId: "vt30v1v8anw5hib_en", groups: [{ playerId: "p2", cardIds: manifestations.slice(40, 44).map((card) => card.id), topCount: 0, bottomCount: 4 }] };
          renderRulesChoice(true);
        } else if (special === "ponderer") {
          latestState.rulesEngine.pendingChoice = { id: "ponderer", kind: "deck_reorder", playerId: "p1", sourceCardId: "xoo3jxtiy1sonm1_en", groups: [{ playerId: "p1", cardIds: manifestations.slice(50, 57).map((card) => card.id), topCount: null, bottomCount: null, extraSide: "hand", extraMin: 1, extraMax: 1 }] };
          renderRulesChoice(true);
        } else if (special === "order") {
          latestState.rulesEngine.pendingChoice = { id: "order", kind: "simultaneous_stack_order", playerId: "p1", actions: manifestations.slice(60, 64).map((card, index) => ({ actionId: `action-${index}`, cardId: card.id, label: card.name, immediate: index === 0 })) };
          renderRulesChoice(true);
        }
      }, { count: capture.count, special: capture.special });
      await page.waitForTimeout(1400);
      if (capture.hold) {
        await page.evaluate(() => {
          const item = latestState.battlefield.find((entry) => entry.id === "p2-m-0");
          const moves = collectRulesVfxCleanupMoves({ captured: [{
            itemId: item.id, cardId: item.cardId, status: "moved",
            zone: "receptacle", containerId: "p1",
          }] }, { x: innerWidth / 2, y: innerHeight / 2 });
          const move = moves[0];
          rulesVfxHoldCard(move.cardId, move.origin, move.originSize, move.compactHold);
          document.querySelector('[data-item-id="p2-m-0"]').style.visibility = "hidden";
        });
      }
      if (capture.hover) {
        await page.locator("#myHandTray .hand-card").nth(3).hover();
        await page.waitForTimeout(350);
      }
      const sizes = await page.evaluate(() => [...document.querySelectorAll('.bf-card.ub-zone-confrontation:not(.ub-floating)')].map((card) => {
        const rect = card.getBoundingClientRect();
        return { id: card.dataset.itemId, width: Math.round(rect.width), height: Math.round(rect.height), compact: card.classList.contains("ub-card-compact") };
      }));
      const uiMetrics = await page.evaluate(() => {
        const hover = document.querySelector(".hand-card-hover-clone")?.getBoundingClientRect();
        const markers = [...document.querySelectorAll(".bf-card :is(.rules-support-badge,.ub-float-badge,.ub-adamant-badge,.ub-first-badge)")]
          .map((marker) => Math.round(marker.getBoundingClientRect().width));
        return {
          hover: hover ? { left: Math.round(hover.left), top: Math.round(hover.top), right: Math.round(hover.right), bottom: Math.round(hover.bottom), fullyVisible: hover.left >= 0 && hover.top >= 0 && hover.right <= innerWidth && hover.bottom <= innerHeight } : null,
          markers,
          compactHolds: document.querySelectorAll(".rules-vfx-hold.ub-compact-hold .ub-compact-crop").length,
          interzoneWidths: ["p1-iz", "p1-will"].map((id) => Math.round(document.querySelector(`[data-item-id="${id}"]`)?.getBoundingClientRect().width || 0)),
          back: (() => { const card = document.querySelector('[data-item-id="face-down-probe"]'); const rect = card?.getBoundingClientRect(); return card ? { compact: card.classList.contains("ub-card-compact"), background: getComputedStyle(card.querySelector(".back-face")).backgroundImage, ratio: rect.height / rect.width } : null; })(),
          token: (() => { const card = document.querySelector('[data-item-id="token-probe"]'); const rect = card?.getBoundingClientRect(); return card ? { compact: card.classList.contains("ub-card-compact"), ratio: rect.height / rect.width } : null; })(),
          totalEssenceOverlap: (() => { const total = document.querySelector(".ub-tside.me .ub-total")?.getBoundingClientRect(); const essence = document.querySelector(".ub-tside.me .ub-ess")?.getBoundingClientRect(); return total && essence ? !(total.right <= essence.left || essence.right <= total.left || total.bottom <= essence.top || essence.bottom <= total.top) : false; })(),
          reorderCards: [...document.querySelectorAll(".rules-reorder-card")].map((card) => Math.round(card.getBoundingClientRect().width)),
          reorderLanes: [...document.querySelectorAll(".rules-reorder-lane > small")].map((lane) => lane.textContent.trim()),
          orderCards: [...document.querySelectorAll(".rules-drag-order .rules-choice-card")].map((card) => Math.round(card.getBoundingClientRect().width)),
        };
      });
      metrics.push({ ...capture, sizes, ...uiMetrics, errors });
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
