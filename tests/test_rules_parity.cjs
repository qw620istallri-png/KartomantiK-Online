const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { execFileSync } = require("node:child_process");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "..");
const publicRoot = path.join(root, "public");
const fixtures = JSON.parse(execFileSync("python", ["tools/frontend_rules_fixtures.py"], {
  cwd: root, encoding: "utf8", maxBuffer: 64 * 1024 * 1024,
}));
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
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route("**/*", (route) => new URL(route.request().url()).hostname === "127.0.0.1" ? route.continue() : route.abort());
    await page.goto(`http://127.0.0.1:${server.address().port}/`);
    await page.waitForFunction(() => cardsById.size === 450 && typeof rulesActivatedActionDraft === "function");
    const failures = await page.evaluate((cases) => {
      const failures = [];
      const key = (target) => target.kind === "card" ? `card:${target.itemId || target.id}`
        : target.kind === "zone_card" ? `zone_card:${target.containerId}:${target.zone}:${target.cardId}`
        : target.kind === "player" ? `player:${target.playerId}` : `stack:${target.actionId}`;
      isObserver = false;
      for (const test of cases) {
        myPlayerId = test.actor;
        latestState = test.state;
        for (const card of test.cards) cardsById.set(card.id, card);
        if (typeof test.playable === "boolean") {
          const actual = handCardIsPlayable(test.source.cardId, test.source);
          if (actual !== test.playable) failures.push({ label: test.label, check: "play window", expected: test.playable, actual, error: test.serverError });
          continue;
        }
        const draft = buildRulesActionDraft(test.source, test.ability);
        const actual = [...new Set(draft.structuredTargets.map((target) => `${target.targetGroupIndex || 0}:${key(target)}`))].sort();
        if (JSON.stringify(actual) !== JSON.stringify(test.targets)) failures.push({ label: test.label, check: "targets", expected: test.targets, actual });
        if (test.source.zone === "battlefield" && test.ability.action !== "play_card") {
          const source = latestState.battlefield.find((item) => item.id === test.source.itemId);
          const available = Boolean(rulesActivatedActionDraft(source, test.ability));
          // A valid declared target set is a witness; a source gate rejection must also hide the action.
          if (test.sourceAllowed !== null && available !== test.sourceAllowed) failures.push({ label: test.label, check: "activation", expected: test.sourceAllowed, actual: available, error: test.serverError });
        }
        if (["hand", "receptacle"].includes(test.source.zone) && test.ability.action !== "play_card" && test.sourceAllowed !== null) {
          const available = Boolean(rulesZoneActivatedActionDraft(test.source, test.ability));
          if (available !== test.sourceAllowed) failures.push({ label: test.label, check: "zone activation", expected: test.sourceAllowed, actual: available, error: test.serverError });
        }
      }
      return failures;
    }, fixtures);
    assert.deepEqual(failures, []);
    const payments = await page.evaluate(() => {
      myPlayerId = "p1";
      latestState.battlefield = [];
      latestState.tokens = [];
      const hand = latestState.players.p1.zones.hand;
      const will = { id: "parity-will", type: "ephemeral_will", powerCost: "{R}{G}", cost: 2, effect: "" };
      cardsById.set(will.id, will);
      cardsById.set("parity-red", { id: "parity-red", type: "manifestation", power: 1, temperaments: ["choleric"], effect: "" });
      cardsById.set("parity-green", { id: "parity-green", type: "manifestation", power: 1, temperaments: ["phlegmatic"], effect: "" });
      hand.cards = [will.id, ...Array(12).fill("parity-red"), "parity-green"];
      const draft = buildRulesActionDraft({ cardId: will.id, zone: "hand" }, null);
      const lateTribute = rulesDraftCanBePaid(draft) && rulesBoardMinimumPaymentCount({ draft }) === 2;
      will.powerCost = "{G}";
      const extraCost = { id: "extra-cost", tribute: "{G}", additionalCost: "exile_hand_manifestation", targets: { min: 0, max: 0 } };
      hand.cards = [will.id, "parity-green"];
      const cannotReuse = !rulesDraftCanBePaid(buildRulesActionDraft({ cardId: will.id, zone: "hand" }, extraCost));
      hand.cards.push("parity-green");
      const distinctCost = rulesDraftCanBePaid(buildRulesActionDraft({ cardId: will.id, zone: "hand" }, extraCost));
      const suspendedCost = rulesAdditionalCostAvailableClient({ source: { zone: "suspended" }, card: { id: will.id }, encodedAbility: { additionalCost: "discard_hand_will" } });
      const formulaDraft = { encodedAbility: null, essencePlan: { remaining: { phlegmatic: 2 } }, paymentRequirements: { phlegmatic: 2 }, limboTributeBudget: 1,
        manifestations: [0, 1].map((index) => ({ cardId: "parity-green", zone: "graveyard", usesFormula: true, selectionKey: index, paymentValue: "graveyard|parity-green" })) };
      const formulaLimited = !rulesDraftCanBePaid(formulaDraft);
      formulaDraft.limboTributeBudget = 2;
      const formulaEnough = rulesDraftCanBePaid(formulaDraft);
      const many = { encodedAbility: null, essencePlan: { remaining: { choleric: 8 } }, paymentRequirements: { choleric: 8 },
        manifestations: Array.from({ length: 30 }, (_, index) => ({ cardId: "parity-red", zone: "hand", selectionKey: index, paymentValue: "parity-red" })) };
      const start = performance.now();
      const sevenCardLimit = !rulesDraftCanBePaid(many);
      const boundedSearch = performance.now() - start < 1000;
      const grouped = { targetRules: { groups: [{}, {}] }, structuredTargets: [
        { key: "same", targetGroupIndex: 0 }, { key: "same", targetGroupIndex: 1 },
      ] };
      const distinctTargets = !rulesDraftHasTargetsClient(grouped);
      grouped.structuredTargets.push({ key: "other", targetGroupIndex: 1 });
      const completeGroups = rulesDraftHasTargetsClient(grouped);
      grouped.structuredTargets = [
        { key: "same", targetGroupIndex: 0 }, { key: "other", targetGroupIndex: 0 }, { key: "same", targetGroupIndex: 1 },
      ];
      const noGroupDeadEnd = !rulesDraftHasTargetsClient(grouped, [grouped.structuredTargets[0]]) && rulesDraftHasTargetsClient(grouped, [grouped.structuredTargets[1]]);
      return { lateTribute, cannotReuse, distinctCost, suspendedCost, formulaLimited, formulaEnough, sevenCardLimit, boundedSearch, distinctTargets, completeGroups, noGroupDeadEnd };
    });
    assert.ok(Object.values(payments).every(Boolean), JSON.stringify(payments));
    const flowCases = fixtures.filter((test) => test.label.endsWith("/ready") && (
      test.ability.opponentOnly || test.source.zone === "receptacle" || test.ability.id === "zum-weaken" || test.ability.extraEssenceByTargetCount
    ));
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 844, height: 390 }]) {
      await page.setViewportSize(viewport);
      const lifecycle = await page.evaluate((cases) => {
        const install = (test) => {
          closeRulesBoardFlow();
          myPlayerId = test.actor;
          latestState = structuredClone(test.state);
          for (const card of test.cards) cardsById.set(card.id, card);
          send = (payload) => window.__paritySent.push(payload);
          window.__paritySent = [];
        };
        const opponent = cases.find((test) => test.ability.opponentOnly);
        install(opponent);
        beginRulesBoardActivatedAction(latestState.battlefield.find((item) => item.id === opponent.source.itemId), opponent.ability.id);
        const opponentOpened = Boolean(pendingRulesBoardFlow);
        closeRulesBoardFlow();
        const vessel = cases.find((test) => test.source.zone === "receptacle");
        install(vessel);
        beginRulesHandActivatedAction(vessel.source.cardId, null, "receptacle", vessel.source.containerId);
        const vesselOpened = Boolean(pendingRulesBoardFlow);
        latestState.players[vessel.source.containerId].zones.receptacle.cards = [];
        renderRulesBoardFlow();
        const vesselRemovalCloses = !pendingRulesBoardFlow;
        const zum = cases.find((test) => test.ability.id === "zum-weaken");
        const openZum = () => {
          install(zum);
          beginRulesBoardActivatedAction(latestState.battlefield.find((item) => item.id === zum.source.itemId), zum.ability.id);
        };
        openZum();
        latestState.phaseTracker.index = ADVANCED_PHASES.findIndex((phase) => phase.id === "end_actions");
        renderRulesBoardFlow();
        const phaseCloses = !pendingRulesBoardFlow;
        openZum();
        latestState.battlefield.find((item) => item.id === zum.source.itemId).controllerId = "p2";
        renderRulesBoardFlow();
        const controlCloses = !pendingRulesBoardFlow;
        openZum();
        latestState.rulesEngine.ongoingEffects.push({ kind: "copy_power_effects", source: { itemId: zum.source.itemId }, copiedRules: { activatedAbilities: [] } });
        renderRulesBoardFlow();
        const lostAbilityCloses = !pendingRulesBoardFlow;
        openZum();
        const stale = pendingRulesBoardFlow.draft.structuredTargets.find((target) => target.id === "own-con");
        pendingRulesBoardFlow.selectedTargets = [stale];
        latestState.battlefield.find((item) => item.id === stale.id).effectTargetable = false;
        renderRulesBoardFlow();
        const staleSelectionRemoved = pendingRulesBoardFlow?.selectedTargets.length === 0
          && !pendingRulesBoardFlow.draft.structuredTargets.some((target) => target.id === stale.id);
        submitRulesBoardFlow(stale);
        const staleNeverSent = window.__paritySent.length === 0;
        openZum();
        latestState.ended = true;
        const terminalHasNoActivation = !rulesActivatedActionDraft(latestState.battlefield.find((item) => item.id === zum.source.itemId), zum.ability);
        renderRulesBoardFlow();
        const terminalCloses = !pendingRulesBoardFlow;
        const multicastigate = cases.find((test) => test.ability.extraEssenceByTargetCount);
        install(multicastigate);
        const tributeId = "parity-surplus";
        cardsById.set(tributeId, { id: tributeId, type: "manifestation", power: 5, temperaments: ["transcendent"], effect: "" });
        latestState.players.p1.zones.hand.cards = [multicastigate.source.cardId, tributeId];
        latestState.tokens = [];
        beginRulesBoardAction(multicastigate.source);
        toggleRulesBoardPayment(1);
        const firstPayment = rulesBoardSelectedPayments();
        pendingRulesBoardFlow.selectedTargets = pendingRulesBoardFlow.draft.structuredTargets.slice(0, 2);
        confirmRulesBoardTargets();
        const surplusKept = JSON.stringify(rulesBoardSelectedPayments()) === JSON.stringify(firstPayment)
          && pendingRulesBoardFlow.targetsConfirmed && pendingRulesBoardFlow.selectedTargets.length === 2;
        submitRulesBoardFlow();
        const surplusSent = window.__paritySent.some((payload) => payload.type === "declare_rules_action"
          && payload.targets.length === 2 && JSON.stringify(payload.paymentCardIds) === JSON.stringify([tributeId]));
        closeRulesBoardFlow();
        return { opponentOpened, vesselOpened, vesselRemovalCloses, phaseCloses, controlCloses, lostAbilityCloses, staleSelectionRemoved, staleNeverSent, terminalHasNoActivation, terminalCloses, surplusKept, surplusSent };
      }, flowCases);
      assert.ok(Object.values(lifecycle).every(Boolean), `${viewport.width}: ${JSON.stringify(lifecycle)}`);
      const tokens = await page.evaluate((test) => {
        myPlayerId = test.actor;
        latestState = structuredClone(test.state);
        isObserver = false;
        for (const card of test.cards) cardsById.set(card.id, card);
        window.__paritySent = [];
        send = (payload) => window.__paritySent.push(payload);
        const token = latestState.battlefield.find((item) => item.isTokenCard && (item.controllerId || item.ownerId) === "p2");
        // The ordinary action dialog must identify a generic Token by its
        // symbol and current Power, despite having no printed cardId.
        openRulesActionPanel(test.source);
        const row = [...document.querySelectorAll("#rulesTargetList input")].find((input) => input.dataset.itemId === token.id)?.closest("label");
        const labelled = Boolean(row && row.textContent.includes(t("token")) && row.textContent.includes("6"));
        const symbol = row?.querySelector("img")?.getAttribute("src") === temperamentSymbol(token.temperament);
        closeRulesActionPanel();
        // The board flow must preserve the physical item id in the payload.
        beginRulesBoardAction(test.source);
        const target = pendingRulesBoardFlow?.draft.structuredTargets.find((item) => item.id === token.id);
        submitRulesBoardFlow(target);
        const sent = window.__paritySent.some((payload) => payload.type === "declare_rules_action"
          && payload.targets.some((entry) => entry.itemId === token.id && !entry.cardId));
        closeRulesBoardFlow();
        return { labelled, symbol, sent };
      }, fixtures.find((test) => test.source.cardId === "obn1uv72ewxv3y5_en" && test.label.endsWith("/generic-token-targets")));
      assert.ok(Object.values(tokens).every(Boolean), `${viewport.width}: Token targeting ${JSON.stringify(tokens)}`);
    }
    assert.deepEqual(errors, []);
    console.log(`Rules frontend/server parity: ${fixtures.length} catalog scenarios OK`);
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
