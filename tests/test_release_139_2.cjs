const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("playwright");
const root = path.resolve(__dirname, "../public");
const mime = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".json": "application/json" };

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
  try {
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 844, height: 390 }]) {
      const page = await browser.newPage({ viewport });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.route("**/*", (route) => new URL(route.request().url()).hostname === "127.0.0.1" ? route.continue() : route.abort());
      await page.goto(`http://127.0.0.1:${server.address().port}/`);
      await page.waitForFunction(() => cardsById.size === 450 && typeof document.querySelector("#rarityEffectsToggleBtn").onclick === "function");
      await page.evaluate(() => {
        for (const card of cardsById.values()) card.image = "card-back.webp";
        for (const power of [1, 2, 3, 4, 5, 6]) cardsById.set(`r139-${power}`, { id: `r139-${power}`, name: `Tribute ${power}`, type: "manifestation", power, temperaments: ["choleric"], image: "card-back.webp" });
        window.__setup139 = (config = {}) => {
          closeRulesBoardFlow(); removeRulesVfx();
          document.querySelector("#rulesChoicePanel").classList.add("hidden");
          document.querySelector("#inspectPanel").classList.add("hidden");
          document.querySelector("#gameScreen").classList.remove("inspect-open");
          const zone = (cards = []) => ({ cards: [...cards], count: cards.length, owners: Object.fromEntries(cards.map((id) => [id, "p1"])) });
          const zones = (hand, graveyard) => ({ hand: zone(hand), graveyard: zone(graveyard), deck: zone(), exile: zone(), receptacle: zone() });
          myPlayerId = "p1"; isObserver = false; connectionRole = "player";
          latestState = {
            players: { p1: { id: "p1", name: "Player 1", seat: 0, score: 0, zones: zones(config.hand || [], config.limbo || []) }, p2: { id: "p2", name: "Player 2", seat: 1, score: 0, zones: zones([], config.opponentLimbo || []) } },
            battlefield: config.field || [
              { id: "mine", cardId: "r139-3", ownerId: "p1", x: 445, y: 800, fieldZone: "confrontation", faceUp: true, rotation: 0, counters: {} },
              { id: "theirs", cardId: "r139-4", ownerId: "p2", x: 445, y: 525, fieldZone: "confrontation", faceUp: true, rotation: 0, counters: {} },
            ], drawings: [],
            tokens: (config.essences || []).map(([temperament, amount], i) => ({ id: `ess-${i}`, ownerId: "p1", isEssence: true, temperament, x: 700, y: 700, counters: { essence: amount } })),
            phaseTracker: { enabled: true, advanced: true, index: ADVANCED_PHASES.findIndex((phase) => phase.id === (config.phase || "confrontation_reaction")), turn: 5, passedPlayerIds: [] },
            rulesEngine: { enabled: config.auto !== false, priorityPlayerId: "p1", actionStack: [], deckConfirmedPlayerIds: ["p1", "p2"], readyPlayerIds: ["p1", "p2"], firstManifestationComplete: true },
          };
          window.__sent = []; send = (payload) => window.__sent.push(payload);
          document.querySelector("#joinScreen").classList.add("hidden"); document.querySelector("#gameScreen").classList.remove("hidden");
          window.uiBeta.setEnabled(true); renderAll();
        };
      });

      const specialPayments = await page.evaluate(() => {
        const field = (id, cardId, extra = {}) => ({ id, cardId, ownerId: "p1", faceUp: true, rotation: 0, fieldZone: "interzone", counters: {}, x: 400, y: 700, ...extra });
        const will = "0coh7nrbvcvan1i_en";
        const result = {};
        window.__setup139({ hand: [will], limbo: ["g3zumpyf623hto6_en"] });
        result.limboTributePlayable = handCardIsPlayable(will);
        window.__setup139({ hand: [will], limbo: ["r139-1"], field: [field("tribute", "7j3udrfh5t8vl25_en")] });
        result.interzoneTributePlayable = handCardIsPlayable(will);
        window.__setup139({ hand: [will], limbo: ["r139-1"], field: [field("braba", "zhzp6kenpqrym9h_en")] });
        latestState.players.p1.zones.receptacle = { cards: ["r139-2"], count: 1, owners: { "r139-2": "p2" } };
        result.vesselTributePlayable = handCardIsPlayable(will);
        window.__setup139({ hand: ["obn1uv72ewxv3y5_en", "r139-1"], field: [field("teapot", "pxp1zvyxfv16bdd_en")] });
        result.reducedWillPlayable = handCardIsPlayable("obn1uv72ewxv3y5_en");
        const hat = field("hat", "ufujqhwlpmaw12y_en", { fieldZone: "field" });
        latestState.battlefield.push(hat);
        result.activatedTribute = buildRulesActionDraft({ cardId: hat.cardId, zone: "battlefield", itemId: hat.id }).paymentRequirements.hollow;
        const drill = field("drill", "inner-deserts-131");
        const victim = field("will", "9bkn03sc9veaa88_en", { ownerId: "p2", fieldZone: "field" });
        window.__setup139({ hand: ["r139-5"], field: [drill, victim] });
        result.noFreeDrill = rulesActivatedActionDraft(drill) === null;
        latestState.tokens = [{ id: "pay", ownerId: "p1", isEssence: true, temperament: "hollow", counters: { essence: 2 } }];
        result.paidDrill = rulesActivatedActionDraft(drill) !== null;
        const zum = field("zum", "282b0n6ldnzdp0p_en");
        const splendor = field("gem", "inner-deserts-143", { fieldZone: "field", counters: { Gem: 2 }, chosenTemperament: "choleric" });
        window.__setup139({ field: [zum, splendor, field("victim", "r139-4", { ownerId: "p2", fieldZone: "confrontation" })] });
        const activation = rulesActivatedActionDraft(zum, activatedAbilitiesByCard.get(zum.cardId).find((a) => a.id === "zum-weaken"));
        result.gemActivationAvailable = activation !== null;
        if (activation) { beginRulesBoardActivatedAction(zum, activation.draft.encodedAbility.id); result.gemPaymentStage = pendingRulesBoardFlow?.stage; }
        return result;
      });
      assert.deepEqual(specialPayments, { limboTributePlayable: true, interzoneTributePlayable: true, vesselTributePlayable: true, reducedWillPlayable: true, activatedTribute: 2, noFreeDrill: true, paidDrill: true, gemActivationAvailable: true, gemPaymentStage: "payment" });
      const specialPaymentLimits = await page.evaluate(() => {
        const field = (id, cardId, extra = {}) => ({ id, cardId, ownerId: "p1", faceUp: true, rotation: 0, fieldZone: "interzone", counters: {}, x: 400, y: 700, ...extra });
        const results = [];
        window.__setup139({ hand: ["obn1uv72ewxv3y5_en", "r139-1"], field: [field("teapot", "pxp1zvyxfv16bdd_en", { effectsInactive: true }), field("target", "r139-4", { ownerId: "p2", fieldZone: "confrontation" })] });
        results.push(!handCardIsPlayable("obn1uv72ewxv3y5_en"));
        window.__setup139({ hand: ["0coh7nrbvcvan1i_en"], limbo: ["r139-2"], field: [field("press", "ze99bj8uw2oisfx_en", { fieldZone: "field", counters: { Formula: 1 } })] });
        results.push(rulesCanAffordCard("0coh7nrbvcvan1i_en"));
        cardsById.set("special-cost-six", { id: "special-cost-six", type: "ephemeral_will", powerCost: "{P}{P}{P}{P}{P}{P}", temperaments: ["melancholic"], effect: "" });
        window.__setup139({ hand: ["special-cost-six", "inner-deserts-052"], field: [field("sacrifice", "r139-1")] });
        results.push(rulesCanAffordCard("special-cost-six"));
        window.__setup139({ hand: ["0coh7nrbvcvan1i_en"], field: [field("potato", "b4yyd5uut0ga9df_en", { fieldZone: "field", counters: { Burn: 3 } })] });
        results.push(buildRulesActionDraft({ cardId: "b4yyd5uut0ga9df_en", itemId: "potato", zone: "battlefield" }).paymentRequirements.hollow === 3);
        latestState.battlefield = [field("conditional", "inner-deserts-028")];
        latestState.rulesEngine.tributePowerOverrides = { p1: {} };
        const base = Number(cardsById.get("inner-deserts-028").power);
        results.push(rulesTributeCandidate("battlefield|conditional").power === base);
        latestState.rulesEngine.tributePowerOverrides.p1["inner-deserts-028"] = 3;
        results.push(rulesTributeCandidate("battlefield|conditional").power === 3);
        for (const [cardId, abilities] of activatedAbilitiesByCard) for (const ability of abilities.filter((entry) => entry.essenceCost)) {
          const source = { cardId, itemId: "source", zone: "battlefield" };
          window.__setup139({ hand: ["r139-5"], field: [field("source", cardId)] });
          const noEssence = buildRulesActionDraft(source, ability);
          results.push(!rulesDraftCanBePaid(noEssence) && noEssence.manifestations.length === 0);
          latestState.tokens = [{ id: "white", ownerId: "p1", isEssence: true, temperament: "transcendent", counters: { essence: 5 } }];
          results.push(rulesDraftCanBePaid(buildRulesActionDraft(source, ability)));
        }
        return results;
      });
      assert.ok(specialPaymentLimits.every(Boolean), JSON.stringify(specialPaymentLimits));

      const requestedGemPayments = await page.evaluate(() => ["stack_counter_payment", "effect_memory_payment", "effect_payment", "immediate_effect_payment"].map((kind) => {
        window.__setup139({ field: [{ id: "gem", cardId: "inner-deserts-143", ownerId: "p1", faceUp: true, rotation: 0, fieldZone: "field", chosenTemperament: "choleric", counters: { Gem: 2 }, x: 400, y: 700 }] });
        latestState.rulesEngine.priorityPlayerId = "p2";
        latestState.rulesEngine.pendingChoice = { id: "requested", kind, playerId: "p1", payment: "{R}", targetCardId: "0coh7nrbvcvan1i_en", sourceCardId: "inner-deserts-143" };
        renderAll();
        document.querySelector("[data-spend-counter-essence]").click();
        const requested = window.__sent[0]?.type === "spend_counter_essence";
        latestState.battlefield[0].counters.Gem = 1;
        latestState.tokens = [{ id: "gem-pay", ownerId: "p1", isEssence: true, temperament: "choleric", counters: { essence: 1 } }];
        renderAll();
        const keptChoice = pendingRulesBoardFlow?.mode === "stack_payment" && pendingRulesBoardFlow.stage === "payment" && !document.querySelector("#rulesFlowPayBtn").disabled;
        resolveRulesStackPayment("pay");
        return requested && keptChoice && window.__sent.at(-1).type === "resolve_rules_choice" && window.__sent.at(-1).choiceId === "requested";
      }));
      assert.deepEqual(requestedGemPayments, [true, true, true, true]);

      const subjugatePayment = await page.evaluate(() => {
        window.__setup139({ hand: ["inner-deserts-140", "r139-2", "r139-1"] });
        cardsById.get("r139-4").points = 30;
        beginRulesBoardAction({ cardId: "inner-deserts-140", zone: "hand", handIndex: 0 });
        toggleRulesBoardPayment(1);
        const target = pendingRulesBoardFlow.draft.structuredTargets.find((entry) => entry.id === "theirs");
        submitRulesBoardFlow(target);
        const waitingForExtra = pendingRulesBoardFlow?.stage === "payment" && pendingRulesBoardFlow.targetsConfirmed;
        const extraRequirement = pendingRulesBoardFlow.draft.paymentRequirements.hollow;
        toggleRulesBoardPayment(2);
        return { waitingForExtra, extraRequirement, committing: pendingRulesBoardFlow.stage === "committing" };
      });
      assert.deepEqual(subjugatePayment, { waitingForExtra: true, extraRequirement: 3, committing: true });

      // Limbo selection always uses cards and an explicit confirmation, even if
      // a pile browser has already created matching data-zone-card elements.
      await page.evaluate(() => {
        window.__setup139({ hand: ["0coh7nrbvcvan1i_en"], limbo: ["r139-1"], essences: [["hollow", 2]] });
        const stale = document.createElement("button"); stale.dataset.zoneCard = "p1:graveyard:r139-1"; stale.id = "old-pile-target"; document.body.append(stale);
        beginRulesBoardAction({ cardId: "0coh7nrbvcvan1i_en", zone: "hand", handIndex: 0 });
      });
      await page.locator(".rules-zone-target-panel [data-zone-pick]").click();
      assert.equal(await page.evaluate(() => window.__sent.length), 0);
      await page.locator(".rules-zone-target-panel [data-zone-pick-confirm]").click();
      await page.waitForFunction(() => window.__sent.length === 1);
      let sent = await page.evaluate(() => { document.querySelector("#old-pile-target").remove(); return window.__sent[0]; });
      assert.equal(sent.targets[0].zone, "graveyard");
      assert.equal(sent.targets[0].cardId, "r139-1");

      await page.evaluate(() => {
        window.__setup139({ hand: ["z2fen73ktw8pbqz_en"], limbo: ["r139-1"], opponentLimbo: ["r139-2"], essences: [["melancholic", 3]] });
        beginRulesBoardAction({ cardId: "z2fen73ktw8pbqz_en", zone: "hand", handIndex: 0 });
      });
      assert.equal(await page.locator(".rules-zone-target-panel [data-zone-pick]").count(), 2);
      await page.locator('.rules-zone-target-panel [data-zone-pick*="p2:graveyard"]').click();
      await page.locator(".rules-zone-target-panel [data-zone-pick-confirm]").click();
      await page.waitForFunction(() => window.__sent.length === 1);
      sent = await page.evaluate(() => window.__sent[0]);
      assert.equal(sent.targets[0].containerId, "p2");
      assert.equal(sent.targets[0].zone, "graveyard");

      const grimoire = await page.evaluate(() => {
        window.__setup139({ limbo: ["r139-1"], essences: [["hollow", 2]] });
        const book = { id: "book", ownerId: "p1", cardId: "omhqwnu5tvwlzzg_en", fieldZone: "field", x: 445, y: 1300, faceUp: true, rotation: 0, counters: {}, attachedCards: [{ cardId: "0coh7nrbvcvan1i_en", ownerId: "p1" }, { cardId: "obn1uv72ewxv3y5_en", ownerId: "p1" }] };
        latestState.battlefield.push(book); renderAll();
        const ghosts = rulesGhostHandCards();
        beginRulesBoardAction({ cardId: "0coh7nrbvcvan1i_en", zone: "attached", itemId: "book" });
        return { recover: ghosts.some((entry) => entry.cardId === "0coh7nrbvcvan1i_en"), oppress: ghosts.some((entry) => entry.cardId === "obn1uv72ewxv3y5_en"), ability: pendingRulesBoardFlow?.draft.encodedAbility?.id };
      });
      assert.deepEqual(grimoire, { recover: true, oppress: true, ability: "return-limbo-card-to-hand" });
      await page.locator(".rules-zone-target-panel [data-zone-pick]").click();
      await page.locator(".rules-zone-target-panel [data-zone-pick-confirm]").click();
      await page.waitForFunction(() => window.__sent.length === 1);
      sent = await page.evaluate(() => window.__sent[0]);
      assert.equal(sent.source.zone, "attached"); assert.equal(sent.source.itemId, "book");

      await page.evaluate(() => { window.__setup139({ hand: ["inner-deserts-100"], phase: "end_actions" }); beginRulesBoardAction({ cardId: "inner-deserts-100", zone: "hand", handIndex: 0 }); });
      await page.waitForFunction(() => window.__sent.length === 1);
      sent = await page.evaluate(() => window.__sent[0]);
      assert.deepEqual(sent.paymentCardIds, []);

      for (const [second, moreTribute] of [[false, false], [true, false], [true, true]]) {
        await page.evaluate(({ moreTribute }) => {
          window.__setup139({ hand: ["inner-deserts-138", moreTribute ? "r139-2" : "r139-5", "r139-3"] });
          latestState.battlefield.forEach((item) => { item.isSupport = true; }); renderAll();
          beginRulesBoardAction({ cardId: "inner-deserts-138", zone: "hand", handIndex: 0 });
          toggleRulesBoardPayment(1);
          document.querySelector('.bf-card[data-item-id="theirs"]').dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
        }, { moreTribute });
        assert.equal(await page.evaluate(() => window.__sent.length), 0);
        if (second) await page.evaluate(() => document.querySelector('.bf-card[data-item-id="mine"]').dispatchEvent(new PointerEvent("pointerdown", { bubbles: true })));
        await page.locator("#rulesConfirmTargets").click();
        if (moreTribute) {
          assert.equal(await page.evaluate(() => pendingRulesBoardFlow.stage), "payment");
          await page.evaluate(() => toggleRulesBoardPayment(2));
        }
        await page.waitForFunction(() => window.__sent.length === 1);
        sent = await page.evaluate(() => window.__sent[0]);
        assert.equal(sent.targets.length, second ? 2 : 1);
        assert.deepEqual(sent.paymentCardIds, moreTribute ? ["r139-2", "r139-3"] : ["r139-5"]);
      }

      const gems = await page.evaluate(() => {
        window.__setup139({ hand: ["obn1uv72ewxv3y5_en"] });
        latestState.battlefield.push({ id: "splendor", ownerId: "p1", cardId: "inner-deserts-143", fieldZone: "field", x: 445, y: 1300, faceUp: true, rotation: 0, counters: { Gem: 2 }, chosenTemperament: "choleric" });
        renderAll();
        const playable = handCardIsPlayable("obn1uv72ewxv3y5_en");
        beginRulesBoardAction({ cardId: "obn1uv72ewxv3y5_en", zone: "hand", handIndex: 0 });
        return { playable, stage: pendingRulesBoardFlow?.stage, buttons: document.querySelectorAll("[data-spend-counter-essence]").length, sent: window.__sent.length, gems: latestState.battlefield.find((item) => item.id === "splendor").counters.Gem };
      });
      assert.deepEqual(gems, { playable: true, stage: "payment", buttons: 1, sent: 0, gems: 2 });
      await page.locator("[data-spend-counter-essence]").click();
      assert.equal(await page.evaluate(() => window.__sent[0].type), "spend_counter_essence");
      await page.evaluate(() => {
        latestState.battlefield.find((item) => item.id === "splendor").counters.Gem = 1;
        latestState.tokens.push({ id: "gem-1", ownerId: "p1", isEssence: true, temperament: "choleric", x: 0, y: 0, counters: { essence: 1 } });
        renderRulesBoardFlow();
      });
      assert.equal(await page.locator("[data-spend-counter-essence]:enabled").count(), 1);

      const manual = await page.evaluate(() => {
        window.__setup139({ auto: false });
        latestState.battlefield[0].counters = { power: 2 }; latestState.battlefield.forEach((item) => delete item.fieldZone); renderAll();
        return { total: confrontationPowerOf("p1"), opponent: confrontationPowerOf("p2"), priority: document.querySelector("#ubField").dataset.prio };
      });
      assert.deepEqual(manual, { total: 5, opponent: 4, priority: "opp" });

      await page.evaluate(() => {
        window.__setup139();
        latestState.rulesEngine.pendingChoice = { id: "colour", kind: "temperament_choice", playerId: "p1", sourceCardId: "inner-deserts-143", options: ["capricious", "choleric", "melancholic", "phlegmatic", "vitreous"] };
        renderRulesChoice();
      });
      assert.equal(await page.locator("[data-rules-temperament-option] img").count(), 5);
      if (process.env.SCREENSHOT_DIR) { fs.mkdirSync(process.env.SCREENSHOT_DIR, { recursive: true }); await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `splendor-${viewport.width}.png`) }); }

      await page.evaluate(() => {
        window.__setup139();
        latestState.rulesEngine.suspendedCards = [{ id: "s-visible", ownerId: "p1", cardId: "r139-1" }, { id: "s-hidden", ownerId: "p2", cardId: null }]; renderAll();
      });
      await page.locator("#ubSuspensionStrip").click();
      assert.equal(await page.locator("#ubSuspensionPanel [data-suspension-card]").count(), 2);
      assert.equal(await page.locator("#ubSuspensionPanel [data-suspension-card]:disabled").count(), 1);
      if (process.env.SCREENSHOT_DIR) await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `suspension-${viewport.width}.png`) });
      await page.locator("[data-close-suspension]").click();

      if (viewport.width > 1000) {
        const wills = await page.evaluate(() => {
          window.__setup139({ auto: false, hand: ["r139-1", "r139-2", "r139-3"] });
          for (let i = 0; i < 3; i++) latestState.battlefield.push({ id: `will-${i}`, ownerId: "p1", cardId: "9bkn03sc9veaa88_en", fieldZone: "field", x: 445 + i * 170, y: 1300, faceUp: true, rotation: 0, counters: {} });
          renderAll();
          const cards = [...document.querySelectorAll('.bf-card.ub-side-me.ub-zone-will')].map((el) => el.getBoundingClientRect());
          return { count: cards.length, minWidth: Math.min(...cards.map((r) => r.width)), bottom: Math.max(...cards.map((r) => r.bottom)), height: innerHeight };
        });
        assert.equal(wills.count, 3); assert.ok(wills.minWidth >= 100, JSON.stringify(wills)); assert.ok(wills.bottom > wills.height * .75, JSON.stringify(wills));
        if (process.env.SCREENSHOT_DIR) await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, "wills-desktop.png") });
      }
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log("Beta 139.2 browser regressions: OK");
  } finally { await browser.close(); await new Promise((resolve) => server.close(resolve)); }
})().catch((error) => { console.error(error); process.exitCode = 1; });
