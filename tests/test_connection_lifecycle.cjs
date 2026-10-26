const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("playwright");

(async () => {
  const root = path.resolve(__dirname, "../public");
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, "http://localhost");
    const file = path.resolve(root, "." + (url.pathname === "/" ? "/index.html" : decodeURIComponent(url.pathname)));
    if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return res.writeHead(404).end();
    res.setHeader("Content-Type", ({ ".js": "text/javascript", ".css": "text/css", ".html": "text/html", ".json": "application/json" })[path.extname(file)] || "application/octet-stream");
    fs.createReadStream(file).pipe(res);
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.route("**/*", route => new URL(route.request().url()).hostname === "127.0.0.1" ? route.continue() : route.abort());
    await page.goto(`http://127.0.0.1:${server.address().port}/`);
    await page.waitForFunction(() => cardsById.size === 450 && typeof document.querySelector("#rarityEffectsToggleBtn").onclick === "function");
    await page.evaluate(() => {
      for (const card of cardsById.values()) card.image = "card-back.webp";
      window.__sockets = [];
      window.WebSocket = class {
        static OPEN = 1;
        constructor() { this.readyState = 1; this.sent = []; window.__sockets.push(this); }
        send(raw) { this.sent.push(JSON.parse(raw)); }
        close() { this.readyState = 3; this.onclose?.(); }
      };
      const zone = () => ({ cards: [], count: 0, owners: {} });
      const player = (id, seat) => ({ id, name: id, seat, score: 0, zones: Object.fromEntries(ZONES.map(key => [key, zone()])) });
      window.__fixture = () => {
        myPlayerId = "p1"; isObserver = false; connectionRole = "player";
        latestState = { type: "state", players: { p1: player("p1", 0), p2: player("p2", 1) }, battlefield: [], tokens: [], strokes: [], recentLog: [],
          phaseTracker: { enabled: true, advanced: true, index: ADVANCED_PHASES.findIndex(p => p.id === "end_actions"), turn: 2, passedPlayerIds: [] },
          rulesEngine: { enabled: true, priorityPlayerId: "p1", actionStack: [], readyPlayerIds: ["p1", "p2"], firstManifestationComplete: true,
            deckConfirmedPlayerIds: ["p1", "p2"] } };
        document.querySelector("#joinScreen").classList.add("hidden");
        document.querySelector("#gameScreen").classList.remove("hidden");
        renderAll();
      };
      window.__fixture();
    });
    const callbacks = await page.evaluate(() => {
      connectAndJoin({ code: "FIRST", name: "P1" });
      const old = ws;
      const oldClose = old.onclose, oldOpen = old.onopen, oldMessage = old.onmessage;
      connectAndJoin({ code: "SECOND", name: "P1" });
      const current = ws;
      current.onopen();
      const currentCount = current.sent.length;
      oldOpen();
      const extraJoin = current.sent.length - currentCount;
      oldMessage({ data: JSON.stringify({ ...latestState, staleMarker: true }) });
      const staleState = latestState.staleMarker === true;
      oldClose();
      const staleClose = wasDisconnected;
      if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
      wasDisconnected = false; showConnectionBanner(null);
      return { extraJoin, staleState, staleClose };
    });

    const reset = await page.evaluate(async () => {
      window.__fixture();
      const cid = "inner-deserts-094";
      latestState.players.p1.zones.hand = { cards: [cid], count: 1, owners: { [cid]: "p1" } };
      latestState.tokens = [{ id: "white", ownerId: "p1", temperament: "transcendent", isEssence: true, counters: { essence: 20 } }];
      renderAll();
      beginRulesBoardAction({ cardId: cid, zone: "hand" });
      const flowBefore = Boolean(pendingRulesBoardFlow);
      lastPointerType = "touch";
      sendCardPlacement({ type: "place_card", cardId: cid, fromZone: "hand", faceUp: true, x: 0, y: 0 }, { cardId: cid, zone: "hand" });
      const graceBefore = Boolean(pendingPlacementGrace);
      const current = ws;
      current.onclose();
      const afterDisconnect = { flow: Boolean(pendingRulesBoardFlow), grace: Boolean(pendingPlacementGrace) };
      if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
      leaveSession();
      connectAndJoin({ code: "THIRD", name: "P1" });
      const next = ws;
      await new Promise(resolve => setTimeout(resolve, PLACEMENT_GRACE_MS + 220));
      const staleSends = next.sent.filter(p => p.type !== "join");
      if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
      return { flowBefore, graceBefore, afterDisconnect, staleSends };
    });

    const vfx = await page.evaluate(async () => {
      window.__fixture();
      const cid = "inner-deserts-094";
      rulesVfxHoldCard(cid, { x: 400, y: 200 });
      const before = document.querySelectorAll(".rules-vfx-hold").length;
      latestState.rulesEngine.pendingChoice = { kind: "confrontation_destination" };
      let delayed = 0;
      rulesVfxAfterWinnerChoices(() => delayed++);
      removeRulesVfx();
      latestState.rulesEngine.pendingChoice = null;
      await new Promise(resolve => setTimeout(resolve, 360));
      return { before, holds: document.querySelectorAll(".rules-vfx-hold").length, delayed };
    });
    console.log(JSON.stringify({ callbacks, reset, vfx, errors }));
    assert.deepEqual(callbacks, { extraJoin: 0, staleState: false, staleClose: false });
    assert.equal(reset.flowBefore, true);
    assert.equal(reset.graceBefore, true);
    assert.deepEqual(reset.afterDisconnect, { flow: false, grace: false });
    assert.deepEqual(reset.staleSends, []);
    assert.deepEqual(vfx, { before: 1, holds: 0, delayed: 0 });
    const commandContext = await page.evaluate(() => {
      window.__fixture();
      const current = ws;
      current.sent.length = 0;
      const original = { type: "pass_priority", passed: true };
      send(original);
      const empty = current.sent.at(-1).rulesContext;
      latestState.rulesEngine.actionStack = [{ id: "visible-top", controllerId: "p2" }];
      send({ type: "declare_rules_action", label: "Context probe" });
      const stacked = current.sent.at(-1).rulesContext;
      const retained = { turn: 1, phaseId: "confrontation_reaction", topActionId: "old" };
      send({ type: "pass_priority", rulesContext: retained });
      const oldIntentRetained = JSON.stringify(current.sent.at(-1).rulesContext) === JSON.stringify(retained);
      send({ type: "set_rules_pass_all", enabled: false });
      const persistentSettingUnstamped = !current.sent.at(-1).rulesContext;
      latestState.rulesEngine.enabled = false;
      send({ type: "pass_phase", passed: true });
      const manualUnstamped = !current.sent.at(-1).rulesContext;
      window.__fixture();
      const cid = "inner-deserts-094";
      latestState.players.p1.zones.hand = { cards: [cid], count: 1, owners: { [cid]: "p1" } };
      latestState.tokens = [{ id: "white", ownerId: "p1", temperament: "transcendent", isEssence: true, counters: { essence: 20 } }];
      beginRulesBoardAction({ cardId: cid, zone: "hand" });
      const hadFlow = Boolean(pendingRulesBoardFlow);
      const messages = [];
      for (const language of ["en", "fr", "it"]) {
        currentLanguage = language;
        messages.push(localizeServerError("The phase or Stack has changed. Review the table and try again."));
      }
      currentLanguage = "fr";
      handleServerMessage({ type: "error", code: "rules_context_changed", message: "The phase or Stack has changed. Review the table and try again." });
      return { empty, stacked, oldIntentRetained, persistentSettingUnstamped, manualUnstamped,
        originalUnchanged: !Object.hasOwn(original, "rulesContext"),
        rejectedFlowClosed: hadFlow && !pendingRulesBoardFlow, messages };
    });
    assert.deepEqual(commandContext.empty, { turn: 2, phaseId: "end_actions", topActionId: null });
    assert.deepEqual(commandContext.stacked, { turn: 2, phaseId: "end_actions", topActionId: "visible-top" });
    for (const name of ["oldIntentRetained", "persistentSettingUnstamped", "manualUnstamped", "originalUnchanged", "rejectedFlowClosed"]) assert.equal(commandContext[name], true, name);
    assert.equal(new Set(commandContext.messages).size, 3);
    assert.ok(commandContext.messages[1].includes("La phase ou la pile a changé"));
    const suspended = await page.evaluate(async () => {
      clearConnectionGameInteractions();
      window.__fixture();
      const cid = "inner-deserts-094";
      latestState.tokens = [{ id: "white", ownerId: "p1", temperament: "transcendent", isEssence: true, counters: { essence: 20 } }];
      latestState.rulesEngine.suspendedCards = [{ id: "suspension-exact", cardId: cid, ownerId: "p2", playableByPlayerId: "p1" }];
      renderAll();
      const ownPriority = document.querySelector("[data-suspended-card]").classList.contains("is-playable");
      latestState.rulesEngine.priorityPlayerId = "p2";
      renderHandTray();
      const opponentPriority = document.querySelector("[data-suspended-card]").classList.contains("is-playable");
      latestState.rulesEngine.priorityPlayerId = "p1";
      beginRulesBoardAction({ cardId: cid, zone: "suspended", suspensionId: "suspension-exact" });
      const current = ws;
      current.sent.length = 0;
      await new Promise(resolve => setTimeout(resolve, 220));
      return { ownPriority, opponentPriority, source: current.sent.find(p => p.type === "declare_rules_action")?.source };
    });
    assert.equal(suspended.ownPriority, true);
    assert.equal(suspended.opponentPriority, false);
    assert.equal(suspended.source?.suspensionId, "suspension-exact");
    const immediate = await page.evaluate(() => {
      clearConnectionGameInteractions();
      window.__fixture();
      const cid = "inner-deserts-094";
      latestState.players.p1.zones.hand = { cards: [cid], count: 1, owners: { [cid]: "p1" } };
      latestState.tokens = [{ id: "white", ownerId: "p1", temperament: "transcendent", isEssence: true, counters: { essence: 20 } }];
      latestState.rulesEngine.actionStack = [{ id: "immediate-ui", controllerId: "p2", label: "Immediate", kind: "triggered_effect", immediate: true, source: { cardId: "inner-deserts-115" }, targets: [] }];
      renderAll();
      const blocked = { playable: handCardIsPlayable(cid), passDisabled: document.querySelector("#passPriorityBtn").disabled,
        responseSlots: document.querySelectorAll(".rules-stack-response-slot").length, label: document.querySelector("#rulesPriority").textContent };
      latestState.rulesEngine.actionStack[0].immediate = false;
      renderAll();
      return { blocked, playableAfter: handCardIsPlayable(cid), resolving: t("rulesImmediateResolving") };
    });
    assert.equal(immediate.blocked.playable, false);
    assert.equal(immediate.blocked.passDisabled, true);
    assert.equal(immediate.blocked.responseSlots, 0);
    assert.equal(immediate.blocked.label, immediate.resolving);
    assert.equal(immediate.playableAfter, true);
    assert.deepEqual(errors, []);
    console.log("Connection lifecycle regression: OK");
  } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
})().catch(error => { console.error(error); process.exitCode = 1; });
