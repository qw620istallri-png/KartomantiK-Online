const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "../public");
const mime = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json" };

(async () => {
  const server = http.createServer((request, response) => {
    const url = new URL(request.url, "http://localhost");
    const file = path.resolve(root, "." + (url.pathname === "/" ? "/index.html" : decodeURIComponent(url.pathname)));
    if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return response.writeHead(404).end();
    response.writeHead(200, { "Content-Type": mime[path.extname(file)] || "application/octet-stream" });
    fs.createReadStream(file).pipe(response);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "chrome", headless: true });
  const reports = [];
  try {
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 844, height: 390 }]) {
      const page = await browser.newPage({ viewport });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.route("**/*", (route) => new URL(route.request().url()).hostname === "127.0.0.1" ? route.continue() : route.abort());
      await page.goto(`http://127.0.0.1:${server.address().port}/`);
      await page.waitForFunction(() => cardsById.size === 450 && typeof document.querySelector("#rarityEffectsToggleBtn").onclick === "function");
      await page.evaluate(() => {
        myPlayerId = "p1"; isObserver = false;
        const zones = () => Object.fromEntries(ZONES.map((key) => [key, { cards: [], owners: {} }]));
        latestState = { players: { p1: { id: "p1", name: "P1", seat: 0, score: 10, zones: zones() }, p2: { id: "p2", name: "P2", seat: 1, score: 10, zones: zones() } },
          battlefield: [], tokens: [], drawings: [],
          phaseTracker: { enabled: true, advanced: true, turn: 2, index: 5, passedPlayerIds: [] },
          rulesEngine: { enabled: true, priorityPlayerId: "p1", actionStack: [], firstManifestationComplete: true, readyPlayerIds: ["p1", "p2"], deckConfirmedPlayerIds: ["p1", "p2"] } };
        window.__choiceCards = [...cardsById.values()].filter((card) => card.type === "manifestation").slice(0, 4).map((card) => card.id);
        for (const card of cardsById.values()) card.image = "card-back.webp";
        latestState.battlefield = window.__choiceCards.slice(0, 2).map((cardId, index) => ({ id: `target-${index}`, cardId, ownerId: "p2", faceUp: true, fieldZone: "interzone", x: 400 + index * 200, y: 350, counters: {}, rotation: 0 }));
        window.__sent = []; send = (payload) => window.__sent.push(payload);
        document.querySelector("#joinScreen").classList.add("hidden");
        document.querySelector("#gameScreen").classList.remove("hidden");
        window.uiBeta.setEnabled(true);
        window.__setChoice = (choice) => {
          latestState.rulesEngine.pendingChoice = { playerId: "p1", sourceCardId: "inner-deserts-064", ...choice };
          window.__sent = [];
          renderAll();
        };
        window.__choiceRefresh = () => { latestState = structuredClone(latestState); latestState.players.p2.activity = "Inspect"; renderAll(); };
      });
      const power = await page.evaluate(() => {
        window.__setChoice({ id: "kanon-undo", kind: "power_loss_distribution", count: 3, candidateItemIds: ["target-0", "target-1"] });
        document.querySelector('[data-rules-power-target="target-0"] img').click();
        document.querySelector('[data-rules-power-undo="target-1"]').click();
        const emptyUndoSafe = document.querySelector('[data-rules-power-undo="target-0"]').textContent === "−1";
        window.__setChoice({ id: "kanon-refresh", kind: "power_loss_distribution", count: 3, candidateItemIds: ["target-0", "target-1"] });
        document.querySelector('[data-rules-power-target="target-0"] img').click();
        window.__choiceRefresh();
        const partialPowerSurvives = document.querySelector('[data-rules-power-undo="target-0"]').textContent === "−1";
        document.querySelector('[data-rules-power-target="target-1"] img').click();
        document.querySelector('[data-rules-power-target="target-1"] img').click();
        const validPowerSent = window.__sent.some((payload) => JSON.stringify(payload.option?.itemIds) === JSON.stringify(["target-0", "target-1", "target-1"]));
        return { emptyUndoSafe, partialPowerSurvives, validPowerSent };
      });
      const pickers = await page.evaluate(() => {
        window.__setChoice({ id: "draw-replacement", kind: "draw_replacement", count: 2, cardIds: window.__choiceCards });
        document.querySelector('[data-rules-private-card="0"]').click();
        window.__choiceRefresh();
        const privatePickSurvives = document.querySelector('[data-rules-private-card="0"]').getAttribute("aria-pressed") === "true";
        document.querySelector('[data-rules-private-card="1"]').click();
        const privateConfirmReady = !document.querySelector("#rulesPrivateCardsConfirm").disabled;
        window.__setChoice({ id: "limbo-selection", kind: "discard_from_hand", destination: "limbo_exile_add_power", upTo: true, count: 2, candidateCardIds: window.__choiceCards });
        document.querySelector('[data-rules-discard-index="0"]').click();
        window.__choiceRefresh();
        const limboPickSurvives = document.querySelector('[data-rules-discard-index="0"]').getAttribute("aria-pressed") === "true";
        document.querySelector("#rulesDiscardConfirm").click();
        const limboPickSent = JSON.stringify(window.__sent[0]?.cardIds) === JSON.stringify([window.__choiceCards[0]]);
        window.__setChoice({ id: "temperament", kind: "temperament_choice", options: ["choleric", "vitreous"] });
        const buttons = [...document.querySelectorAll("#rulesChoiceOptions button")];
        buttons[0].click();
        window.__choiceRefresh();
        const waitingStaysLocked = [...document.querySelectorAll("#rulesChoiceOptions button")].every((button) => button.disabled);
        document.querySelectorAll("#rulesChoiceOptions button")[1].click();
        const singleAnswer = window.__sent.length === 1;
        handleServerMessage({ type: "error", message: "Choose a valid option." });
        const retryUnlocked = [...document.querySelectorAll("#rulesChoiceOptions button")].every((button) => !button.disabled);
        document.querySelectorAll("#rulesChoiceOptions button")[1].click();
        const retrySent = window.__sent.length === 2;
        clearConnectionGameInteractions();
        renderAll();
        const reconnectUnlocked = [...document.querySelectorAll("#rulesChoiceOptions button")].every((button) => !button.disabled);
        latestState.players.p1.zones.hand.cards = window.__choiceCards.slice(0, 3);
        window.__setChoice({ id: "hand-change", kind: "discard_from_hand", count: 2, upTo: true });
        pickHandDropCard(0, true);
        const handPicked = rulesHandDropSelected(latestState.rulesEngine.pendingChoice).length === 1;
        latestState.players.p1.zones.hand.cards.reverse();
        renderAll();
        const staleHandCleared = rulesHandDropSelected(latestState.rulesEngine.pendingChoice).length === 0;
        window.__setChoice({ id: "old-choice", kind: "temperament_choice", options: ["choleric", "vitreous"] });
        const oldButton = document.querySelector("#rulesChoiceOptions button");
        window.__setChoice({ id: "new-choice", kind: "temperament_choice", options: ["choleric", "vitreous"] });
        oldButton.click();
        const oldChoiceIgnored = window.__sent.length === 0;
        latestState.players.p1.zones.hand.cards = ["inner-deserts-084", ...window.__choiceCards.slice(0, 2)];
        window.__setChoice({ id: "chabak-reserved", kind: "discard_from_hand", count: 2, requireManifestation: true,
          destination: "stalemate_for_support", sourceCardId: "inner-deserts-084" });
        pickHandDropCard(0, true);
        const chabakRemainsInHand = rulesHandDropSelected(latestState.rulesEngine.pendingChoice).length === 0 && window.__sent.length === 0;
        pickHandDropCard(1, true); pickHandDropCard(2, true);
        const chabakOtherCardsSent = JSON.stringify(window.__sent[0]?.cardIds) === JSON.stringify(window.__choiceCards.slice(0, 2));
        latestState.players.p1.zones.hand.cards = ["inner-deserts-084", "inner-deserts-084", window.__choiceCards[0]];
        window.__setChoice({ id: "chabak-spare-copy", kind: "discard_from_hand", count: 2, requireManifestation: true,
          destination: "stalemate_for_support", sourceCardId: "inner-deserts-084" });
        pickHandDropCard(0, true); pickHandDropCard(1, true);
        const lastChabakCopyReserved = rulesHandDropSelected(latestState.rulesEngine.pendingChoice).length === 1 && window.__sent.length === 0;
        pickHandDropCard(2, true);
        const spareChabakCopyAllowed = JSON.stringify(window.__sent[0]?.cardIds) === JSON.stringify(["inner-deserts-084", window.__choiceCards[0]]);
        return { privatePickSurvives, privateConfirmReady, limboPickSurvives, limboPickSent, waitingStaysLocked, singleAnswer, retryUnlocked, retrySent, reconnectUnlocked, handPicked, staleHandCleared, oldChoiceIgnored,
          chabakRemainsInHand, chabakOtherCardsSent, lastChabakCopyReserved, spareChabakCopyAllowed };
      });
      const grimoire = await page.evaluate(() => {
        currentLanguage = "fr";
        const wills = [...cardsById.values()].filter((c) => ["ephemeral_will", "persistent_will"].includes(c.type)).slice(0, 2).map((c) => c.id);
        latestState.players.p1.zones.hand.cards = [wills[0], wills[0], wills[1], window.__choiceCards[0]];
        const choice = { id: "grimoire", kind: "discard_from_hand", destination: "attach_to_source", sourceCardId: "omhqwnu5tvwlzzg_en", requireTypes: ["ephemeral_will", "persistent_will"], count: 3, upTo: true };
        window.__setChoice(choice);
        const emptyLabel = document.querySelector("#rulesDiscardConfirm").textContent === "Ne rien poser";
        pickHandDropCard(0, true); pickHandDropCard(1, true); pickHandDropCard(3, true);
        for (let i = 0; i < 5; i++) window.__choiceRefresh();
        const previewNames = [...document.querySelectorAll("[data-hand-unpick] img")].map((img) => img.alt);
        const duplicatesAreSeparate = previewNames.length === 2 && previewNames.every((name) => name === cardName(wills[0]));
        const oneHint = document.querySelectorAll("#rulesChoicePanel .rules-card-drop-hint").length === 1;
        const selectedImages = [...document.querySelectorAll("#myHandTray .is-choice-selected img")];
        const handIsGrey = selectedImages.length === 2 && selectedImages.every((img) => getComputedStyle(img).filter === "grayscale(1)" && Number(getComputedStyle(img).opacity) < .6);
        document.querySelector('[data-hand-unpick="0"]').click();
        const canUndo = document.querySelectorAll("[data-hand-unpick]").length === 1 && !document.querySelector('[data-hand-index="0"]').classList.contains("is-choice-selected");
        const countedConfirm = document.querySelector("#rulesDiscardConfirm").textContent === "Confirmer la pose (1)";
        document.querySelector("#rulesDiscardConfirm").click();
        const correctPayload = JSON.stringify(window.__sent[0]?.cardIds) === JSON.stringify([wills[0]]);
        document.querySelector("#rulesDiscardConfirm").click();
        const noDuplicateAnswer = window.__sent.length === 1;
        window.__setChoice({ ...choice, id: "grimoire-empty" });
        document.querySelector("#rulesDiscardConfirm").click();
        const emptyIsExplicit = JSON.stringify(window.__sent[0]?.cardIds) === "[]";
        window.__setChoice({ ...choice, id: "grimoire-preview" });
        pickHandDropCard(0, true); pickHandDropCard(2, true);
        document.querySelectorAll(".ko-toast").forEach((toast) => toast.remove());
        return { emptyLabel, duplicatesAreSeparate, oneHint, handIsGrey, canUndo, countedConfirm, correctPayload, noDuplicateAnswer, emptyIsExplicit };
      });
      if (process.env.SCREENSHOT_DIR) {
        fs.mkdirSync(process.env.SCREENSHOT_DIR, { recursive: true });
        await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `grimoire-${viewport.width}.png`) });
      }
      await page.evaluate(() => window.__setChoice({ id: "ponderer-refresh", kind: "deck_reorder", sourceCardId: [...cardsById.values()].find((card) => card.name === "Expansive Ponderer").id,
        groups: [{ playerId: "p1", cardIds: window.__choiceCards, extraSide: "hand", extraMin: 1, extraMax: 1 }] }));
      const first = await page.locator('[data-rules-reorder-strip="pool"] .rules-reorder-card').first().boundingBox();
      const lane = await page.locator('[data-rules-reorder-strip="extra"]').boundingBox();
      await page.mouse.move(first.x + first.width / 2, first.y + first.height / 2);
      await page.mouse.down();
      await page.mouse.move(lane.x + lane.width * .7, lane.y + lane.height / 2, { steps: 12 });
      await page.mouse.up();
      await page.evaluate(() => window.__choiceRefresh());
      const reorderSurvives = await page.locator('[data-rules-reorder-strip="extra"] .rules-reorder-card').count() === 1;
      if (process.env.SCREENSHOT_DIR) {
        fs.mkdirSync(process.env.SCREENSHOT_DIR, { recursive: true });
        await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `choice-continuity-${viewport.width}.png`) });
      }
      reports.push({ width: viewport.width, ...power, ...pickers, ...grimoire, reorderSurvives, errors });
      await page.close();
    }
    console.log(JSON.stringify(reports));
    if (!process.env.DIAGNOSE_ONLY) for (const report of reports) {
      assert.deepEqual(report.errors, []);
      for (const [name, result] of Object.entries(report)) if (typeof result === "boolean") assert.equal(result, true, `${report.width}: ${name}`);
    }
    console.log("Choice continuity regression: OK");
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
