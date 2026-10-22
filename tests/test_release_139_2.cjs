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

      const reservedCost = await page.evaluate(() => {
        window.__setup139({ hand: ["3gqrmx5jegwz8kb_en", "r139-2", "r139-2"] });
        beginRulesBoardAction({ cardId: "3gqrmx5jegwz8kb_en", zone: "hand", handIndex: 0 });
        toggleRulesBoardPayment(1);
        const candidates = rulesBoardHandCostCandidates().map((entry) => entry.index);
        resolveRulesBoardCardDrop({ fromOwnerId: "p1", fromZone: "hand", handIndex: 1 }, document.querySelector("#rulesFloatingCard"));
        return { candidates, stage: pendingRulesBoardFlow.stage, sent: window.__sent.length };
      });
      assert.deepEqual(reservedCost, { candidates: [2], stage: "cost_card", sent: 0 });
      await page.evaluate(() => resolveRulesBoardCardDrop({ fromOwnerId: "p1", fromZone: "hand", handIndex: 2 }, document.querySelector("#rulesFloatingCard")));
      await page.waitForFunction(() => window.__sent.length === 1);
      assert.deepEqual(await page.evaluate(() => ({ tribute: window.__sent[0].paymentCardIds, exile: window.__sent[0].costCardId })),
        { tribute: ["r139-2"], exile: "r139-2" });

      for (const existing of [0, 1]) {
        const rally = await page.evaluate((existing) => {
          cardsById.get("r139-5").temperaments = ["phlegmatic"];
          window.__setup139({ hand: ["5q6t7i5pzctbi8s_en", "r139-5"], essences: existing ? [["hollow", existing]] : [] });
          beginRulesBoardAction({ cardId: "5q6t7i5pzctbi8s_en", zone: "hand", handIndex: 0 });
          toggleRulesBoardPayment(1);
          const input = document.querySelector("#rulesExtraEssenceCount");
          return { max: Number(input.max), stage: pendingRulesBoardFlow.stage, visible: !input.closest(".rules-extra-essence-row").hidden };
        }, existing);
        assert.deepEqual(rally, { max: 3 + existing, stage: "extra_essence", visible: true });
        await page.locator("#rulesExtraEssenceCount").fill(String(3 + existing));
        await page.locator("#rulesExtraEssenceConfirm").click();
        await page.waitForFunction(() => window.__sent.length === 1);
        assert.equal(await page.evaluate(() => window.__sent[0].extraEssenceCount), 3 + existing);
      }
      await page.evaluate(() => { cardsById.get("r139-5").temperaments = ["choleric"]; });

      const cancelledPayment = await page.evaluate(() => {
        window.__setup139({ hand: ["3gqrmx5jegwz8kb_en", "r139-2"] });
        const before = JSON.stringify({ players: latestState.players, tokens: latestState.tokens });
        beginRulesBoardAction({ cardId: "3gqrmx5jegwz8kb_en", zone: "hand", handIndex: 0 });
        toggleRulesBoardPayment(1);
        closeRulesBoardFlow();
        return { unchanged: before === JSON.stringify({ players: latestState.players, tokens: latestState.tokens }), sent: window.__sent.length };
      });
      assert.deepEqual(cancelledPayment, { unchanged: true, sent: 0 });

      const persistentResponses = await page.evaluate(() => {
        const checks = [];
        for (const phase of ["end_actions", "confrontation_before_revelation", "confrontation_reaction"]) {
          for (const soup of [false, true]) for (const occupied of [false, true]) {
            window.__setup139({ phase, hand: ["265f4wdooq43pjn_en"], field: soup ? [{
              id: "soup", cardId: "s4dofvhan101mew_en", ownerId: "p1", fieldZone: "interzone",
              faceUp: true, rotation: 0, counters: {}, x: 445, y: 700,
            }] : [] });
            if (occupied) latestState.rulesEngine.actionStack = [{
              id: "pending", controllerId: "p2", kind: "triggered_effect", source: { cardId: "r139-1" },
            }];
            const expected = (phase !== "confrontation_reaction" || soup) && (!occupied || soup);
            checks.push({ phase, soup, occupied, expected, actual: handCardIsPlayable("265f4wdooq43pjn_en"),
              reason: handCardUnplayableReason("265f4wdooq43pjn_en") });
          }
        }
        return checks;
      });
      for (const check of persistentResponses) {
        assert.equal(check.actual, check.expected, JSON.stringify(check));
        assert.equal(Boolean(check.reason), !check.expected, JSON.stringify(check));
      }

      const automaticHonor = await page.evaluate(() => {
        window.__setup139();
        latestState.battlefield.push({ id: "honor", cardId: "y4muuingw5y9l7z_en", ownerId: "p1", fieldZone: "field", x: 445, y: 1300, faceUp: true, rotation: 0, counters: {} });
        latestState.players.p1.score = 10;
        renderAll();
        const entry = { type: "rules_action_resolved", actorId: "p1", actorName: "Player 1", details: { controllerId: "p1", automatic: true, label: "Honor and Respect", source: { cardId: "y4muuingw5y9l7z_en", itemId: "honor", zone: "battlefield" }, effectResult: { kind: "score", playerId: "p1", delta: 10, score: 10 }, stackDepth: 0 } };
        playRulesVfxEvent(captureRulesVfxEvent(entry));
        return { score: document.querySelector('.rules-vfx-impact-score')?.textContent, stackPulses: document.querySelectorAll('.rules-vfx-stack-pulse').length, stackReveals: document.querySelectorAll('.rules-vfx-resolve-reveal').length, log: formatLogEntry(entry) };
      });
      assert.equal(automaticHonor.score, "+10");
      assert.equal(automaticHonor.stackPulses, 0);
      assert.equal(automaticHonor.stackReveals, 0);
      assert.match(automaticHonor.log, /\+10/);
      assert.doesNotMatch(automaticHonor.log, /passe|restante/);
      if (process.env.SCREENSHOT_DIR) { fs.mkdirSync(process.env.SCREENSHOT_DIR, { recursive: true }); await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `honor-automatic-${viewport.width}.png`) }); }

      for (const mode of ["power", "essence"]) {
        await page.evaluate(() => {
          window.__setup139();
          latestState.battlefield.push({ id: "sando", cardId: "inner-deserts-114", ownerId: "p1", fieldZone: "interzone", x: 445, y: 1064, faceUp: true, rotation: 0, counters: { Banner: 1 } });
          renderAll();
        });
        const sando = page.locator('.bf-card[data-item-id="sando"]');
        assert.equal(await sando.locator('.rules-activate-badge').count(), 1);
        assert.match(await sando.locator('.rules-activate-badge').getAttribute("aria-label"), /Dépenser 1 Bannière/);
        await sando.locator('.rules-activate-badge').click();
        assert.equal(await sando.locator('[data-rules-activate-confirm]').count(), 2);
        assert.match(await sando.locator('.rules-activate-text').textContent(), /1 Bannière/);
        assert.match(await sando.locator('[data-rules-activate-confirm="sandokaron-banner-power"]').textContent(), /\+3 puissance/);
        assert.match(await sando.locator('[data-rules-activate-confirm="sandokaron-banner-essence"]').textContent(), /2 Essences colériques/);
        assert.doesNotMatch(await sando.locator('.rules-activate-actions').textContent(), /Activer/);
        assert.ok(await sando.locator('.rules-activate-confirm').evaluate((el) => {
          const rect = el.getBoundingClientRect();
          const button = el.querySelector('[data-rules-activate-confirm]');
          return rect.x >= 0 && rect.y >= 0 && rect.right <= innerWidth && rect.bottom <= innerHeight && button.getBoundingClientRect().height >= 34;
        }));
        if (mode === "power" && process.env.SCREENSHOT_DIR) { fs.mkdirSync(process.env.SCREENSHOT_DIR, { recursive: true }); await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `sandokaron-${viewport.width}.png`) }); }
        await sando.locator(`[data-rules-activate-confirm="sandokaron-banner-${mode}"]`).click();
        if (mode === "power") await page.locator('.bf-card[data-item-id="theirs"]').dispatchEvent("pointerdown");
        await page.waitForFunction(() => window.__sent.length === 1);
        assert.equal(await page.evaluate(() => window.__sent[0].abilityId), `sandokaron-banner-${mode}`);
        await page.evaluate(() => { closeRulesBoardFlow(); latestState.battlefield.find((item) => item.id === "sando").counters.Banner = 0; renderAll(); });
        assert.equal(await sando.locator('.rules-activate-badge').count(), 0);
      }

      for (const free of [false, true]) {
        const requirements = await page.evaluate((free) => {
          window.__setup139({ phase: "end_actions", field: [{ id: "jigon-will", cardId: "lmx5uff1z53fo0g_en", ownerId: "p1", fieldZone: "field", x: 445, y: 1300, faceUp: false, rotation: 0, counters: {}, concealedWill: true, concealedFree: free }], essences: free ? [] : [["vitreous", 2], ["capricious", 2]] });
          const item = latestState.battlefield[0];
          return buildRulesActionDraft(rulesFieldWillPlaySource(item)).paymentRequirements;
        }, free);
        assert.deepEqual(requirements, free ? {} : { vitreous: 2, capricious: 2 });
        const hiddenGhost = page.locator('[data-ghost-card="lmx5uff1z53fo0g_en"][data-ghost-zone="field_play"]');
        assert.equal(await hiddenGhost.count(), 1);
        assert.equal(await hiddenGhost.getAttribute("data-ghost-playable"), "true");
        if (process.env.SCREENSHOT_DIR) { fs.mkdirSync(process.env.SCREENSHOT_DIR, { recursive: true }); await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `jigon-${free ? "free" : "paid"}-${viewport.width}.png`) }); }
        const ghostRect = await hiddenGhost.boundingBox();
        const boardRect = await page.locator('#battlefieldWrap').boundingBox();
        await page.mouse.move(ghostRect.x + ghostRect.width / 2, ghostRect.y + ghostRect.height / 2);
        await page.mouse.down();
        await page.mouse.move(boardRect.x + boardRect.width * .55, boardRect.y + boardRect.height * .4, { steps: 12 });
        await page.mouse.up();
        await page.waitForFunction(() => window.__sent.length === 1);
        assert.equal(await page.evaluate(() => window.__sent[0].type), "declare_rules_action");
        assert.equal(await page.evaluate(() => window.__sent[0].source.zone), "battlefield");
        assert.equal(await page.evaluate(() => window.__sent[0].source.itemId), "jigon-will");
      }
      await page.evaluate(() => {
        closeRulesBoardFlow();
        latestState.phaseTracker.index = ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_reaction");
        renderAll();
      });
      assert.equal(await page.locator('[data-ghost-zone="field_play"][data-ghost-playable="false"]').count(), 1);
      assert.equal(await page.evaluate(() => limboWillIsPlayable("lmx5uff1z53fo0g_en", true)), false);
      await page.evaluate(() => { myPlayerId = "p2"; renderAll(); });
      assert.equal(await page.locator('[data-ghost-zone="field_play"]').count(), 0);

      await page.evaluate(() => {
        window.__setup139();
        latestState.battlefield.push({ id: "gem", cardId: "inner-deserts-143", ownerId: "p1", x: 600, y: 1300, fieldZone: "field", faceUp: true, rotation: 0, counters: { Gem: 2, Choleric: 1 }, chosenTemperament: "choleric" });
        latestState.rulesEngine.actionStack = [{ id: "existing", controllerId: "p2", kind: "triggered_effect", label: "Existing effect", source: { cardId: "r139-1", zone: "battlefield" } }];
        renderAll();
      });
      const gemCard = page.locator('.bf-card[data-item-id="gem"]');
      assert.equal(await gemCard.locator('.bf-counter').count(), 2);
      assert.equal(await gemCard.locator('[data-gem-essence] img').count(), 2);
      assert.equal(await gemCard.locator('.rules-activate-badge').count(), 0);
      assert.equal((await gemCard.locator('.counters').textContent()).trim(), "");
      if (process.env.SCREENSHOT_DIR) { fs.mkdirSync(process.env.SCREENSHOT_DIR, { recursive: true }); await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `splendor-counter-icons-${viewport.width}.png`) }); }
      await gemCard.locator('[data-gem-essence]').first().click();
      assert.deepEqual(await page.evaluate(() => window.__sent), [{ type: "spend_counter_essence", itemId: "gem", abilityId: "splendor-spends-a-gem-as-excess-essence" }]);
      assert.equal(await page.evaluate(() => latestState.rulesEngine.actionStack.length), 1);
      await page.evaluate(() => { latestState.rulesEngine.priorityPlayerId = "p2"; renderAll(); });
      assert.equal(await gemCard.locator('[data-gem-essence]:disabled').count(), 2);

      await page.evaluate(() => {
        window.__setup139({ hand: ["inner-deserts-148"], essences: [["hollow", 2]] });
        latestState.battlefield.push(
          { id: "support-them", cardId: "r139-2", ownerId: "p2", isSupport: true, fieldZone: "confrontation", faceUp: true, rotation: 0, counters: {}, x: 600, y: 525 },
          { id: "support-me", cardId: "r139-1", ownerId: "p1", isSupport: true, fieldZone: "confrontation", faceUp: true, rotation: 0, counters: {}, x: 600, y: 800 }
        );
        renderAll();
        beginRulesBoardAction({ cardId: "inner-deserts-148", zone: "hand", handIndex: 0 });
      });
      if (process.env.SCREENSHOT_DIR) { fs.mkdirSync(process.env.SCREENSHOT_DIR, { recursive: true }); await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `induce-first-${viewport.width}.png`) }); }
      assert.match(await page.locator("#rulesFlowInstruction").textContent(), /1\/2/);
      await page.locator('.bf-card[data-item-id="theirs"]').dispatchEvent("pointerdown");
      assert.match(await page.locator("#rulesFlowInstruction").textContent(), /2\/2/);
      assert.equal(await page.locator('.bf-card[data-item-id="theirs"].rules-selected-effect-target').count(), 1);
      assert.equal(await page.locator('.bf-card[data-item-id="support-me"].rules-valid-target').count(), 0);
      assert.equal(await page.locator('.bf-card[data-item-id="support-them"].rules-valid-target').count(), 1);
      if (process.env.SCREENSHOT_DIR) await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `induce-second-${viewport.width}.png`) });
      await page.locator('.bf-card[data-item-id="support-them"]').dispatchEvent("pointerdown");
      await page.waitForFunction(() => window.__sent.length === 1);
      assert.deepEqual(await page.evaluate(() => window.__sent[0].targets.map((target) => target.itemId)), ["theirs", "support-them"]);
      for (const [abilityId, symbol] of [["pidue-choleric-weakens", "choleric"], ["pidue-capricious-silences", "capricious"], ["pidue-melancholic-discards", "melancholic"]]) {
        await page.evaluate((abilityId) => {
          window.__setup139();
          latestState.rulesEngine.pendingChoice = { id: "pidue-target", kind: "trigger_targets", playerId: "p1", sourceCardId: "inner-deserts-129", sourceAbilityId: abilityId, targetRules: abilityId.includes("melancholic") ? { kind: "player", min: 1, max: 1 } : { kind: "card", cardType: "manifestation", zones: ["battlefield"], min: 1, max: 1 } };
          renderAll();
        }, abilityId);
        const selector = symbol === "melancholic" ? ".rules-player-target-panel .rules-choice-effect" : "#rulesFlowInstruction";
        assert.equal(await page.locator(`${selector} [data-active-ability="${abilityId}"]`).count(), 1);
        assert.equal(await page.locator(`${selector} .rules-current-effect-label img`).count(), 1);
        if (process.env.SCREENSHOT_DIR) await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `pidue-${symbol}-${viewport.width}.png`) });
      }
      await page.evaluate(() => {
        window.__setup139({ hand: ["r139-1", "r139-2"] });
        latestState.rulesEngine.pendingChoice = { id: "pidue-discard", kind: "discard_from_hand", playerId: "p1", sourceCardId: "inner-deserts-129", sourceAbilityId: "pidue-melancholic-discards", count: 1 };
        renderAll();
      });
      assert.equal(await page.locator('#rulesChoicePanel .rules-choice-effect [data-active-ability="pidue-melancholic-discards"]').count(), 1);
      const effectLocales = await page.evaluate(() => {
        const saved = currentLanguage;
        const checks = [];
        for (currentLanguage of ["en", "fr", "it"]) for (const [temperament, suffix] of [["choleric", "weakens"], ["capricious", "silences"], ["phlegmatic", "token"], ["vitreous", "draws"], ["melancholic", "discards"]]) {
          const effect = rulesActiveAbilityEffect(`pidue-${temperament}-${suffix}`);
          checks.push(effect?.temperament === temperament && Boolean(effect.text) && !effect.text.includes("\n"));
        }
        currentLanguage = saved;
        window.__setup139();
        latestState.rulesEngine.pendingChoice = { id: "pidue-order", kind: "simultaneous_stack_order", playerId: "p1", actions: [
          { actionId: "draw", cardId: "inner-deserts-129", abilityId: "pidue-vitreous-draws" },
          { actionId: "token", cardId: "inner-deserts-129", abilityId: "pidue-phlegmatic-token" },
        ] };
        renderAll();
        checks.push(new Set([...document.querySelectorAll("#rulesChoiceOptions [data-order-key] > span")].map((entry) => entry.textContent)).size === 2);
        return checks;
      });
      assert.ok(effectLocales.every(Boolean));

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

      // Optional ranges 0..N still need a usable target picker before the Stack.
      for (const cardId of ["inner-deserts-063", "inner-deserts-038"]) {
        for (const selectCard of [false, true]) {
          await page.evaluate((cardId) => {
            window.__setup139({ limbo: [cardId, "r139-1", "lmx5uff1z53fo0g_en"], opponentLimbo: ["r139-2"] });
            const ability = triggeredAbilitiesByCard.get(cardId).find((entry) => entry.optional);
            latestState.rulesEngine.pendingChoice = {
              id: "audit-targets", kind: "trigger_targets", playerId: "p1", sourceCardId: cardId,
              targetRules: ability.targets,
            };
            renderAll();
          }, cardId);
          const picker = page.locator(".rules-zone-target-panel");
          assert.equal(await picker.locator("[data-zone-pick]").count(), cardId === "inner-deserts-063" ? 2 : 1);
          const confirm = picker.locator("[data-zone-pick-confirm]");
          assert.equal(await confirm.isEnabled(), true);
          if (selectCard) await picker.locator("[data-zone-pick]").first().click();
          assert.equal(await page.evaluate(() => window.__sent.length), 0);
          if (selectCard && process.env.SCREENSHOT_DIR) {
            await page.mouse.move(4, 4);
            await page.waitForFunction(() => !document.querySelector(".choice-card-preview"));
            await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `audit-${cardId}-${viewport.width}.png`) });
          }
          await confirm.click();
          await page.waitForFunction(() => window.__sent.length === 1);
          const selection = await page.evaluate(() => window.__sent[0]);
          assert.equal(selection.type, "resolve_rules_choice");
          assert.equal(selection.targets.length, selectCard ? 1 : 0);
          if (selectCard) assert.equal(selection.targets[0].cardId, cardId === "inner-deserts-063" ? "r139-1" : "lmx5uff1z53fo0g_en");
        }
      }

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

      await page.evaluate(() => {
        window.__setup139({ phase: "recovery_end", field: [{ id: "jugg", cardId: "inner-deserts-100", ownerId: "p1", fieldZone: "field", faceUp: true, rotation: 0, counters: {}, x: 445, y: 1300 }], essences: [["hollow", 2]] });
        latestState.rulesEngine.firstManifestationComplete = false;
        renderAll();
      });
      const juggCard = page.locator('.bf-card[data-item-id="jugg"]');
      assert.equal(await juggCard.evaluate((el) => el.classList.contains("ub-zone-will")), true);
      assert.equal(await juggCard.locator('.rules-activate-badge').count(), 1);
      if (process.env.SCREENSHOT_DIR) await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `juggernut-recovery-${viewport.width}.png`) });
      await juggCard.locator('.rules-activate-badge').click();
      await juggCard.locator('[data-rules-activate-confirm="juggernut-charges-into-confrontation"]').click();
      await page.waitForFunction(() => window.__sent.length === 1);
      assert.equal(await page.evaluate(() => window.__sent[0].abilityId), "juggernut-charges-into-confrontation");
      assert.deepEqual(await page.evaluate(() => window.__sent[0].paymentCardIds), []);
      const occupiedPm = await page.evaluate(() => {
        closeRulesBoardFlow();
        latestState.battlefield.push({ id: "already-cz", cardId: "r139-2", ownerId: "p1", fieldZone: "confrontation", faceUp: true, rotation: 0, counters: {}, x: 445, y: 800 });
        renderAll();
        const available = rulesActivatedActionDraft(latestState.battlefield[0]);
        latestState.phaseTracker.index = ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_choose");
        latestState.players.p1.zones.hand = { cards: ["r139-1"], count: 1, owners: { "r139-1": "p1" } };
        return { activation: !!available, hand: handCardIsPlayable("r139-1") };
      });
      assert.deepEqual(occupiedPm, { activation: false, hand: false });

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
      if (process.env.SCREENSHOT_DIR) { fs.mkdirSync(process.env.SCREENSHOT_DIR, { recursive: true }); await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `splendor-gems-${viewport.width}.png`) }); }

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
