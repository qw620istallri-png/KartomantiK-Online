/* Semantic UI contracts use the shipped browser functions and literal oracles.
 * Local images isolate behavior; this gate does not certify remote artwork.
 */
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
  const reports = [];
  try {
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 844, height: 390 }]) {
      const page = await browser.newPage({ viewport });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.route("**/*", (route) => new URL(route.request().url()).hostname === "127.0.0.1" ? route.continue() : route.abort());
      await page.goto(`http://127.0.0.1:${server.address().port}/`);
      await page.waitForFunction(() => cardsById.size === 450 && typeof rulesBoardOptionalExtraEssenceMax === "function");
      const result = await page.evaluate(async () => {
        const checks = {};
        const zones = () => Object.fromEntries(ZONES.map((zone) => [zone, { cards: [], owners: {}, entryVersions: {} }]));
        myPlayerId = "p1"; isObserver = false;
        latestState = {
          ended: false, players: {
            p1: { id: "p1", name: "P1", seat: 0, score: 0, zones: zones() },
            p2: { id: "p2", name: "P2", seat: 1, score: 0, zones: zones() },
          }, battlefield: [], tokens: [], strokes: [],
          phaseTracker: { enabled: true, advanced: true, turn: 2,
            index: ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_reaction"), passedPlayerIds: [] },
          rulesEngine: { enabled: true, priorityPlayerId: "p1", priorityPasses: [], actionStack: [], ongoingEffects: [],
            playPermissions: [], pendingChoice: null, readyPlayerIds: ["p1", "p2"], deckConfirmedPlayerIds: ["p1", "p2"],
            firstManifestationComplete: true, firstManifestationItemIds: {}, skipEndPhasePlayerIds: [] },
        };
        pendingRulesBoardFlow = null;
        const will = (id, cost) => ({ id, name: id, type: "ephemeral_will", typeLabel: "Ephemeral Will",
          cost, powerCost: "{H}".repeat(cost), temperaments: ["hollow"], effect: "", image: "card-back.webp" });
        const chosen = will("semantic-chosen-will", 3);
        const other = will("semantic-other-will", 2);
        cardsById.set(chosen.id, chosen); cardsById.set(other.id, other);
        const graveyard = latestState.players.p1.zones.graveyard;
        graveyard.cards = [chosen.id, other.id];
        graveyard.entryVersions = { [chosen.id]: 2, [other.id]: 0 };
        latestState.rulesEngine.playPermissions = [{ id: "nghoul", playerId: "p1", fromZone: "graveyard",
          cardId: chosen.id, zoneEntryVersion: 2, noTribute: true, exileOnLeave: true, ephemeralOnly: true,
          maxCost: 3, phaseIds: ["confrontation_reaction", "end_actions"], turn: 2 }];
        checks.boundPermission = rulesLimboPlayMode(chosen.id) === "free" && rulesLimboPlayMode(other.id) === null;
        checks.boundPaymentFree = Object.keys(rulesActionPaymentDraft({ cardId: chosen.id, zone: "graveyard" }, chosen, null).paymentRequirements).length === 0;
        checks.boundWillGhostOnly = JSON.stringify(rulesGhostHandCards().map((entry) => entry.cardId)) === JSON.stringify([chosen.id]);
        checks.boundWillNotSupport = rulesLimboPermission(chosen.id) === null;
        chosen.cost = 4;
        checks.boundCostLimit = rulesLimboPlayMode(chosen.id) === null;
        chosen.cost = 3;
        graveyard.entryVersions[chosen.id] = 4;
        checks.boundRoundtripInvalid = rulesLimboPlayMode(chosen.id) === null
          && !rulesGhostHandCards().some((entry) => entry.cardId === chosen.id);

        latestState.rulesEngine.playPermissions = [];
        graveyard.cards = [];
        const staged = { id: "jodorosk-revealed", cardId: chosen.id, ownerId: "p1", controllerId: "p1",
          fieldZone: "field", faceUp: true, rotation: 0, counters: {}, x: 740, y: 800,
          concealedWill: true, concealedFree: true, revealedFreeWill: true, effectsDisabled: true };
        latestState.battlefield = [staged];
        let ghost = rulesGhostHandCards().find((entry) => entry.itemId === staged.id);
        checks.jodoroskLabel = ghost?.label === cardName("inner-deserts-126").split(",")[0]
          && ghost?.label !== t("rulesConcealedLabel");
        checks.jodoroskFreeFromField = rulesFieldWillPlaySource(staged).fieldFree
          && Object.keys(buildRulesActionDraft(rulesFieldWillPlaySource(staged)).paymentRequirements).length === 0;
        latestState.phaseTracker.turn += 1;
        ghost = rulesGhostHandCards().find((entry) => entry.itemId === staged.id);
        checks.jodoroskNoInventedExpiry = Boolean(ghost?.playable);

        latestState.battlefield = [];
        const many = Array.from({ length: 21 }, (_, index) => will(`semantic-many-${index}`, 4));
        many.forEach((card) => cardsById.set(card.id, card));
        graveyard.cards = many.map((card) => card.id);
        const targetRules = { kind: "zone_card", min: 0, max: 20, anyNumber: true,
          cardTypes: ["ephemeral_will"], zones: ["graveyard"], container: "self" };
        const unlimited = rulesStructuredActionTargets({ targets: targetRules });
        checks.anyNumberTwentyOne = unlimited.structuredTargets.length === 21 && unlimited.targetRules.max === 21;
        window.__semanticSent = [];
        send = (payload) => window.__semanticSent.push(payload);
        latestState.rulesEngine.pendingChoice = { id: "twenty-one-targets", kind: "trigger_targets", playerId: "p1",
          sourceCardId: "inner-deserts-038", sourceAbilityId: "referen-doom-exiles-limbo-wills", targetRules };
        syncRulesTriggerTargetBoardFlow();
        renderRulesBoardFlow();
        for (let index = 0; index < 21; index += 1) {
          const button = document.querySelector("[data-zone-pick]");
          if (!button) break;
          button.click();
        }
        const selectedTwentyOne = pendingRulesBoardFlow?.selectedTargets?.length === 21;
        document.querySelector("[data-zone-pick-confirm]")?.click();
        await new Promise((resolve) => window.setTimeout(resolve, 240));
        checks.anyNumberTwentyOneConfirmedInPicker = selectedTwentyOne
          && window.__semanticSent.some((payload) => payload.choiceId === "twenty-one-targets" && payload.targets?.length === 21);
        latestState.rulesEngine.pendingChoice = null;
        closeRulesBoardFlow();
        const cheapOnly = rulesStructuredActionTargets({ targets: { ...targetRules, min: 1, max: 1, anyNumber: false, maxCost: 3 } });
        checks.maxCostFiltersTargets = cheapOnly.structuredTargets.length === 0;
        checks.sameContainer = !rulesDraftTargetCombinationValidClient({ targetRules: { sameContainer: true } },
          [{ kind: "zone_card", key: "a", containerId: "p1" }, { kind: "zone_card", key: "b", containerId: "p2" }]);
        checks.sameContainerFeasibility = !rulesDraftHasTargetsClient({ targetRules: { min: 2, max: 2, sameContainer: true },
          structuredTargets: [{ key: "a", containerId: "p1" }, { key: "b", containerId: "p2" }] });
        checks.distinctTemperaments = !rulesDraftTargetCombinationValidClient({ targetRules: { distinctTemperaments: true } },
          [{ key: "a", effectiveTemperament: "vitreous" }, { key: "b", effectiveTemperament: "vitreous" }])
          && rulesDraftTargetCombinationValidClient({ targetRules: { distinctTemperaments: true } },
            [{ key: "a", effectiveTemperament: "vitreous" }, { key: "b", effectiveTemperament: "choleric" }]);
        checks.distinctTargets = !rulesDraftTargetCombinationValidClient({ targetRules: { distinctTargets: true } },
          [{ key: "same" }, { key: "same" }]);

        latestState.rulesEngine.skipEndPhasePlayerIds = ["p1"];
        checks.skippedEndAllSubphases = ["end_actions", "end_triggers", "end_expire"].every((phaseId) => {
          latestState.phaseTracker.index = ADVANCED_PHASES.findIndex((phase) => phase.id === phaseId);
          return rulesEndActionsSkippedClient() && !limboWillIsPlayable(chosen.id, true)
            && beginRulesBoardAction({ cardId: chosen.id, zone: "hand" }) === false;
        });
        latestState.phaseTracker.index = ADVANCED_PHASES.findIndex((phase) => phase.id === "end_actions");
        myPlayerId = "p2"; latestState.rulesEngine.priorityPlayerId = "p2";
        checks.otherPlayerKeepsEnd = !rulesEndActionsSkippedClient() && limboWillIsPlayable(chosen.id, true);
        myPlayerId = "p1"; latestState.rulesEngine.priorityPlayerId = "p1";
        latestState.rulesEngine.skipEndPhasePlayerIds = [];

        const rally = will("semantic-rally", 1);
        const large = { id: "semantic-large-tribute", name: "Large tribute", type: "manifestation",
          power: 35, points: 10, temperaments: ["hollow"], effect: "" };
        cardsById.set(rally.id, rally); cardsById.set(large.id, large);
        latestState.players.p1.zones.hand.cards = [rally.id, large.id];
        graveyard.cards = [];
        const optional = { id: "semantic-rally-extra", action: "play_card", targets: { min: 0, max: 0 },
          optionalExtraEssence: { temperament: "hollow", max: null } };
        latestState.tokens = [{ id: "excess", ownerId: "p1", isEssence: true, isExcess: true,
          isNeutralCounter: false, temperament: "hollow", counters: { essence: 30 } }];
        const pooled = rulesActionPaymentDraft({ cardId: rally.id, zone: "hand" }, rally, optional);
        checks.rallyPoolAboveTwenty = pooled.optionalExtraEssenceMax === 29;
        latestState.tokens = [];
        const tributeDraft = rulesActionPaymentDraft({ cardId: rally.id, zone: "hand" }, rally, optional);
        const flow = { source: { cardId: rally.id, zone: "hand" }, draft: { ...tributeDraft, encodedAbility: optional },
          selectedPaymentIndexes: new Set([1]), extraTributeIndexes: new Set() };
        checks.rallyTributeSurplusAboveTwenty = rulesBoardOptionalExtraEssenceMax(flow) === 34;
        flow.selectedPaymentIndexes.clear();
        checks.rallyNoUnpaidSurplus = rulesBoardOptionalExtraEssenceMax(flow) === 0;
        return checks;
      });

      // Pointer clicks prove that the shipped controls are reachable, rather
      // than merely exercising a helper or invoking its event handler directly.
      await page.evaluate(() => {
        document.querySelector("#joinScreen").classList.add("hidden");
        document.querySelector("#gameScreen").classList.remove("hidden");
        window.uiBeta.setEnabled(true);
        for (const card of cardsById.values()) card.image = "card-back.webp";
        latestState.phaseTracker.index = ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_reaction");
        latestState.rulesEngine.actionStack = [{ id: "semantic-duel", kind: "play_card", controllerId: "p1",
          source: { cardId: [...cardsById.values()].find((card) => card.name === "Duel Honorably").id,
            ownerId: "p1", zone: "hand" }, targets: [], neutralizePayment: ["H", "H"] }];
        window.__semanticPrepareDuel = (playerId, priorityId, observer = false, pending = false) => {
          myPlayerId = playerId; isObserver = observer;
          latestState.rulesEngine.priorityPlayerId = priorityId;
          latestState.rulesEngine.pendingChoice = pending ? { id: "another-choice", kind: "effect_payment", playerId } : null;
          window.__semanticSent = [];
          renderAll();
        };
      });
      for (const playerId of ["p1", "p2"]) {
        await page.evaluate((actor) => window.__semanticPrepareDuel(actor, actor), playerId);
        const button = page.locator('[data-stack-payment="semantic-duel"]');
        assert.equal(await button.count(), 1, `Duel payment must be offered to ${playerId}`);
        // The phone stack deliberately collapses its details until opened.
        if (!(await button.isVisible())) await page.locator("#ubStack").click();
        await button.click();
        result[`duelPriority${playerId}PointerPayload`] = await page.evaluate(() =>
          JSON.stringify(window.__semanticSent) === JSON.stringify([{ type: "request_rules_stack_payment", actionId: "semantic-duel" }]));
      }
      for (const [name, actor, priority, observer, pending] of [
        ["OutsidePriority", "p1", "p2", false, false],
        ["Observer", "p1", "p1", true, false],
        ["PendingChoice", "p1", "p1", false, true],
      ]) {
        await page.evaluate((args) => window.__semanticPrepareDuel(...args), [actor, priority, observer, pending]);
        result[`duelAbsent${name}`] = await page.locator("[data-stack-payment]").count() === 0;
      }
      await page.evaluate(() => {
        latestState.rulesEngine.actionStack = [];
        latestState.rulesEngine.pendingChoice = null;
        myPlayerId = "p1"; isObserver = false;
        window.__semanticBinary = (purpose, option, language) => {
          currentLanguage = language;
          const tenebro = [...cardsById.values()].find((card) => card.name === "Tenebro, Night Assailant").id;
          const outcast = [...cardsById.values()].find((card) => card.name === "Wandering Outcast").id;
          const incoming = [...cardsById.values()].find((card) => card.name === "Cleanse").id;
          const prefix = purpose === "tenebro" ? "rulesDiscardSupport" : "rulesOutcastSwap";
          const choice = { id: `${purpose}-${option}-${language}`, kind: "binary_choice", playerId: "p1", options: ["yes", "no"],
            purpose: purpose === "tenebro" ? "discard_support_replacement" : "outcast_swap",
            sourceCardId: purpose === "tenebro" ? tenebro : outcast,
            relatedCardId: purpose === "tenebro" ? tenebro : "inner-deserts-001",
            incomingCardId: purpose === "tenebro" ? undefined : incoming,
            headingKey: `${prefix}Heading`, textKey: `${prefix}Text`, yesKey: `${prefix}Yes`, noKey: `${prefix}No` };
          latestState.rulesEngine.pendingChoice = choice;
          window.__semanticSent = [];
          resetRulesChoiceInteraction();
          renderRulesChoice(true);
          return { id: choice.id, source: cardName(choice.sourceCardId), target: cardName(choice.relatedCardId),
            incoming: cardName(choice.incomingCardId), prefix };
        };
      });
      const binaryLabels = {
        en: { tenebro: ["Put in Support", "Put in Limbo"], outcast: ["Swap positions", "Keep the original target"] },
        fr: { tenebro: ["Placer en Soutien", "Placer dans les Limbes"], outcast: ["Échanger les positions", "Garder la cible initiale"] },
        it: { tenebro: ["Metti in Supporto", "Metti nel Limbo"], outcast: ["Scambia le posizioni", "Mantieni il bersaglio originale"] },
      };
      for (const language of ["en", "fr", "it"]) {
        for (const purpose of ["tenebro", "outcast"]) {
          for (const option of ["yes", "no"]) {
            const fixture = await page.evaluate(({ purpose, option, language }) => window.__semanticBinary(purpose, option, language), { purpose, option, language });
            const panel = page.locator("#rulesChoicePanel");
            assert.equal(await panel.isVisible(), true, `${purpose} ${language} must display a choice`);
            const heading = await page.locator("#rulesChoiceHeading").innerText();
            const text = await page.locator("#rulesChoiceText").innerText();
            const buttons = page.locator("[data-rules-binary-option]");
            const labels = await buttons.allInnerTexts();
            result[`${purpose}${language}${option}MeaningfulPrompt`] = heading.length > 5
              && !heading.includes("rules") && text.includes(fixture.source) && !/\{[^}]+\}/.test(text)
              && labels.length === 2 && labels.every((label) => label.trim().length > 3 && !label.includes("rules"))
              && labels[0] !== labels[1]
              && (purpose !== "outcast" || text.includes(fixture.incoming) && text.includes(fixture.target));
            result[`${purpose}${language}${option}ExactOptions`] = JSON.stringify(labels) === JSON.stringify(binaryLabels[language][purpose]);
            await page.locator(`[data-rules-binary-option="${option}"]`).click();
            result[`${purpose}${language}${option}PointerPayload`] = await page.evaluate(({ choiceId, option }) =>
              JSON.stringify(window.__semanticSent) === JSON.stringify([{ type: "resolve_rules_choice", choiceId, option }]),
              { choiceId: fixture.id, option });
            result[`${purpose}${language}${option}AnswerLocksBoth`] = await buttons.evaluateAll((entries) => entries.every((button) => button.disabled));
          }
        }
      }
      assert.deepEqual(errors, []);
      const failures = Object.entries(result).filter(([, passed]) => !passed).map(([name]) => name);
      assert.deepEqual(failures, [], JSON.stringify({ viewport, failures, result }));
      reports.push({ viewport, checks: Object.keys(result).length, passed: true });
      await page.close();
    }
    process.stdout.write(`Semantic UI contracts: ${JSON.stringify(reports)}\n`);
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
