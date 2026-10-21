const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("playwright");

const publicRoot = path.resolve(__dirname, "../public");
const mime = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json" };

(async () => {
  const server = http.createServer((request, response) => {
    const url = new URL(request.url, "http://localhost");
    const file = path.resolve(publicRoot, "." + (url.pathname === "/" ? "/index.html" : decodeURIComponent(url.pathname)));
    if (!file.startsWith(publicRoot + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return response.writeHead(404).end();
    response.writeHead(200, { "Content-Type": mime[path.extname(file)] || "application/octet-stream" });
    fs.createReadStream(file).pipe(response);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "chrome", headless: true });
  try {
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 844, height: 390 }]) {
      const page = await browser.newPage({ viewport });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.route("**/*", (route) => new URL(route.request().url()).hostname === "127.0.0.1" ? route.continue() : route.abort());
      await page.goto(`http://127.0.0.1:${server.address().port}/`);
      await page.waitForFunction(() => cardsById.size === 450 && typeof document.querySelector("#rarityEffectsToggleBtn").onclick === "function");
      const initial = await page.evaluate(() => {
        const will = { id: "test-will", name: "Volonté multicolore", type: "persistent_will", powerCost: "{R}{G}", cost: 2, temperaments: ["choleric", "phlegmatic"], image: "card-back.webp" };
        cardsById.set(will.id, will);
        cardsById.set("test-red", { id: "test-red", name: "Tribut rouge", type: "manifestation", power: 1, temperaments: ["choleric"], image: "card-back.webp" });
        cardsById.set("test-green", { id: "test-green", name: "Tribut vert", type: "manifestation", power: 1, temperaments: ["phlegmatic"], image: "card-back.webp" });
        const zones = (cards) => Object.fromEntries(["hand", "deck", "graveyard", "exile", "receptacle"].map((key) => [key, { cards: key === "hand" ? cards : [], count: key === "hand" ? cards.length : 0 }]));
        myPlayerId = "p1";
        isObserver = false;
        latestState = {
          players: { p1: { id: "p1", name: "Joueur 1", seat: 0, score: 0, zones: zones([will.id, "test-red", "test-green"]) }, p2: { id: "p2", name: "Joueur 2", seat: 1, score: 0, zones: zones([]) } },
          battlefield: [], drawings: [],
          tokens: [{ id: "white", ownerId: "p1", isEssence: true, temperament: "transcendent", counters: { essence: 1 }, x: 500, y: 500 }],
          phaseTracker: { enabled: true, advanced: true, index: ADVANCED_PHASES.findIndex((phase) => phase.id === "end_actions"), turn: 1, passedPlayerIds: [] },
          rulesEngine: { enabled: true, priorityPlayerId: "p1", actionStack: [], deckConfirmedPlayerIds: ["p1", "p2"], readyPlayerIds: ["p1", "p2"], firstManifestationComplete: true },
        };
        window.__sent = [];
        send = (payload) => window.__sent.push(payload);
        document.querySelector("#joinScreen").classList.add("hidden");
        document.querySelector("#gameScreen").classList.remove("hidden");
        window.uiBeta.setEnabled(true);
        renderAll();
        const hand = latestState.players.p1.zones.hand.cards;
        latestState.players.p1.zones.hand.cards = [will.id, "test-red"];
        const payableWithRedOnly = rulesCanAffordCard(will.id) && rulesDraftCanBePaid(buildRulesActionDraft({ cardId: will.id, zone: "hand", handIndex: 0 }));
        latestState.players.p1.zones.hand.cards = hand;
        beginRulesBoardAction({ cardId: will.id, zone: "hand", handIndex: 0 });
        return { payableWithRedOnly, stage: pendingRulesBoardFlow?.stage, prompt: document.querySelector("#rulesFlowInstruction").textContent, disabled: document.querySelector("#rulesWhiteConfirm")?.disabled, sent: window.__sent.length };
      });
      assert.equal(initial.payableWithRedOnly, true);
      assert.equal(initial.stage, "essence_allocation");
      assert.match(initial.prompt, /Essences blanches.*1/);
      assert.equal(initial.disabled, true);
      assert.equal(initial.sent, 0);
      if (process.env.SCREENSHOT_DIR) {
        fs.mkdirSync(process.env.SCREENSHOT_DIR, { recursive: true });
        await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `white-essence-${viewport.width}.png`) });
      }
      await page.locator('[data-white-plus="phlegmatic"]').click();
      await page.locator("#rulesWhiteConfirm").click();
      let payment = await page.evaluate(() => ({ stage: pendingRulesBoardFlow.stage, remaining: pendingRulesBoardFlow.draft.essencePlan.remaining, cards: pendingRulesBoardFlow.draft.manifestations.map((entry) => entry.cardId) }));
      assert.equal(payment.stage, "payment");
      assert.deepEqual(payment.remaining, { choleric: 1, phlegmatic: 0 });
      assert.deepEqual(payment.cards, ["test-red"]);
      await page.locator("#rulesChangeWhitePayment").click();
      await page.locator("#rulesWhite-phlegmatic").fill("0");
      // Keyboard input has the same effect as the stepper buttons.
      await page.locator("#rulesWhite-choleric").fill("1");
      await page.locator("#rulesWhiteConfirm").click();
      payment = await page.evaluate(() => ({ remaining: pendingRulesBoardFlow.draft.essencePlan.remaining, cards: pendingRulesBoardFlow.draft.manifestations.map((entry) => entry.cardId) }));
      assert.deepEqual(payment.remaining, { choleric: 0, phlegmatic: 1 });
      assert.deepEqual(payment.cards, ["test-green"]);
      await page.evaluate(() => toggleRulesBoardPayment(2));
      await page.waitForFunction(() => window.__sent.some((payload) => payload.type === "declare_rules_action"));
      const sent = await page.evaluate(() => window.__sent[0]);
      assert.deepEqual(sent.transcendentPayment, { choleric: 1 });
      assert.deepEqual(sent.paymentCardIds, ["test-green"]);
      const guards = await page.evaluate(() => {
        const source = { cardId: "test-will", zone: "hand", handIndex: 0 };
        const card = cardsById.get(source.cardId);
        card.powerCost = "{R}{R}{G}{G}";
        latestState.tokens[0].counters.essence = 2;
        beginRulesBoardAction(source);
        document.querySelector("#rulesWhite-choleric").value = "1";
        document.querySelector("#rulesWhite-choleric").dispatchEvent(new Event("input"));
        const partialDisabled = document.querySelector("#rulesWhiteConfirm").disabled;
        document.querySelector("#rulesWhite-phlegmatic").value = "1";
        document.querySelector("#rulesWhite-phlegmatic").dispatchEvent(new Event("input"));
        document.querySelector("#rulesWhiteConfirm").click();
        const split = { ...pendingRulesBoardFlow.draft.transcendentPayment };
        const remaining = { ...pendingRulesBoardFlow.draft.essencePlan.remaining };
        closeRulesBoardFlow();
        card.powerCost = "{R}{G}";
        const fullyCovered = rulesInitialActionStage(buildRulesActionDraft(source)) !== "essence_allocation";
        latestState.tokens[0].counters.essence = 0;
        const noWhitePrompt = rulesInitialActionStage(buildRulesActionDraft(source)) === "payment";
        latestState.tokens[0].counters.essence = 1;
        latestState.tokens.push({ id: "red", ownerId: "p1", isEssence: true, temperament: "choleric", counters: { essence: 1 } });
        const oneColourLeft = rulesInitialActionStage(buildRulesActionDraft(source)) !== "essence_allocation";
        latestState.tokens.pop();
        openRulesActionPanel(source);
        const debugPrompt = pendingRulesBoardFlow?.stage === "essence_allocation";
        cancelRulesBoardFlow();
        return { partialDisabled, split, remaining, fullyCovered, noWhitePrompt, oneColourLeft, debugPrompt, cancelled: pendingRulesBoardFlow === null, sent: window.__sent.length };
      });
      assert.deepEqual(guards, { partialDisabled: true, split: { choleric: 1, phlegmatic: 1 }, remaining: { choleric: 1, phlegmatic: 1 }, fullyCovered: true, noWhitePrompt: true, oneColourLeft: true, debugPrompt: true, cancelled: true, sent: 1 });
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log("White Essence allocation frontend regression: OK");
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
