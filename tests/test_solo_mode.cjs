const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "..");
const publicRoot = path.join(root, "public");
const mime = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
};

(async () => {
  const server = http.createServer((request, response) => {
    const url = new URL(request.url, "http://localhost");
    const file = path.resolve(
      publicRoot,
      "." + (url.pathname === "/" ? "/index.html" : decodeURIComponent(url.pathname)),
    );
    if (!file.startsWith(publicRoot + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      return response.writeHead(404).end();
    }
    response.writeHead(200, {
      "Content-Type": mime[path.extname(file)] || "application/octet-stream",
    });
    fs.createReadStream(file).pipe(response);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const browser = await chromium.launch({
    channel: process.env.BROWSER_CHANNEL || "chrome",
    headless: true,
  });
  try {
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 844, height: 390 }]) {
      const page = await browser.newPage({ viewport, locale: "fr-FR" });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.route("**/*", (route) => (
        new URL(route.request().url()).hostname === "127.0.0.1"
          ? route.continue()
          : route.abort()
      ));
      await page.goto(`http://127.0.0.1:${server.address().port}/`);
      await page.waitForFunction(() => (
        cardsById.size === 450
        && typeof renderAll === "function"
        && typeof document.querySelector("#importCancelBtn").onclick === "function"
      ));
      const launch = await page.evaluate(() => {
        window.__soloLaunch = null;
        connectAndJoin = (payload) => { window.__soloLaunch = payload; };
        document.querySelector("#createName").value = "Trainer";
        document.querySelector("#createSoloBtn").click();
        return window.__soloLaunch;
      });
      assert.equal(launch.createSolo, true);
      assert.equal(launch.name, "Trainer");
      assert.equal(launch.opponentName, "P2");
      const result = await page.evaluate(async () => {
        const cardIds = [...cardsById.keys()].slice(0, 4);
        const zone = (cards) => ({
          cards,
          count: cards.length,
          owners: Object.fromEntries(cards.map((cardId) => [cardId, "p1"])),
        });
        const zones = (hand, ownerId) => ({
          hand: {
            ...zone(hand),
            owners: Object.fromEntries(hand.map((cardId) => [cardId, ownerId])),
          },
          deck: zone([]),
          graveyard: zone([]),
          exile: zone([]),
          receptacle: zone([]),
        });
        myPlayerId = "solo:p1";
        soloPrimaryPlayerId = "solo:p1";
        soloControlledPlayerIds = ["solo:p1", "solo:p2"];
        soloInteractionPlayerId = null;
        connectionMode = "solo";
        connectionRole = "player";
        isObserver = false;
        latestState = {
          type: "state",
          mode: "solo",
          solo: { enabled: true, controlledPlayerIds: [...soloControlledPlayerIds] },
          players: {
            "solo:p1": { id: "solo:p1", name: "P1", seat: 0, score: 0, zones: zones(cardIds.slice(0, 2), "solo:p1") },
            "solo:p2": { id: "solo:p2", name: "P2", seat: 1, score: 0, zones: zones(cardIds.slice(2), "solo:p2") },
          },
          battlefield: [],
          tokens: [],
          strokes: [],
          ended: false,
          phaseTracker: {
            enabled: true,
            advanced: true,
            turn: 2,
            index: ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_reaction"),
            passedPlayerIds: ["solo:p1"],
          },
          rulesEngine: {
            enabled: false,
            priorityPlayerId: "solo:p2",
            priorityPasses: [],
            actionStack: [],
            pendingChoice: null,
            deckConfirmedPlayerIds: ["solo:p1", "solo:p2"],
            readyPlayerIds: ["solo:p1", "solo:p2"],
            firstManifestationComplete: true,
          },
          recentLog: [],
        };
        window.__sent = [];
        ws = {
          readyState: WebSocket.OPEN,
          send: (payload) => window.__sent.push(JSON.parse(payload)),
        };
        document.querySelector("#joinScreen").classList.add("hidden");
        document.querySelector("#gameScreen").classList.remove("hidden");

        renderAll();
        latestState.phaseTracker.turn = 1;
        latestState.phaseTracker.index = ADVANCED_PHASES.findIndex((phase) => phase.id === "recovery_start");
        latestState.rulesEngine.deckConfirmedPlayerIds = [];
        latestState.rulesEngine.readyPlayerIds = [];
        renderAll();
        const pregameButtons = [...document.querySelectorAll("[data-solo-pregame-deck]")].map((button) => ({
          playerId: button.dataset.soloPregameDeck,
          label: button.textContent.trim(),
          tone: button.style.getPropertyValue("--player-tone"),
        }));
        const pregameGenericHidden = document.querySelector("#rulesPregameActions").classList.contains("hidden");
        document.querySelector('[data-solo-pregame-deck="solo:p2"]').click();
        const pregameP2Editor = {
          open: !document.querySelector("#importPanel").classList.contains("hidden"),
          playerId: myPlayerId,
          target: document.querySelector("#importDeckPlayer").textContent.trim(),
        };
        const activityRoundTrip = structuredClone(latestState);
        activityRoundTrip.players["solo:p2"].activity = "importing";
        handleServerMessage(activityRoundTrip);
        pregameP2Editor.playerIdAfterState = myPlayerId;
        pregameP2Editor.targetAfterState = document.querySelector("#importDeckPlayer").textContent.trim();
        window.__sent = [];
        importDeckPayload({ name: "P2 test", groups: [] }, "P2 test", false, false);
        const pregameP2Import = window.__sent.at(-1);
        document.querySelector("#importCancelBtn").click();
        latestState.rulesEngine.enabled = true;
        latestState.rulesEngine.deckConfirmedPlayerIds = ["solo:p1", "solo:p2"];
        latestState.rulesEngine.openingHandPlayerIds = ["solo:p1", "solo:p2"];
        latestState.rulesEngine.mulliganPlayerIds = [];
        latestState.rulesEngine.openingMulliganRequiredPlayerIds = [];
        latestState.rulesEngine.openingMulliganFailedPlayerIds = [];
        latestState.rulesEngine.readyPlayerIds = ["solo:p1"];
        renderAll();
        const p2OpeningActions = {
          activePlayerId: myPlayerId,
          mulliganVisible: !document.querySelector("#rulesPregameMulliganBtn").classList.contains("hidden"),
          mulliganDisabled: document.querySelector("#rulesPregameMulliganBtn").disabled,
          readyVisible: !document.querySelector("#rulesPregameReadyBtn").classList.contains("hidden"),
          readyDisabled: document.querySelector("#rulesPregameReadyBtn").disabled,
        };
        window.__sent = [];
        document.querySelector("#rulesPregameMulliganBtn").click();
        document.querySelector("#confirmPanelOkBtn").click();
        p2OpeningActions.mulliganPayload = window.__sent.at(-1);
        window.__sent = [];
        renderAll();
        document.querySelector("#rulesPregameReadyBtn").click();
        p2OpeningActions.readyPayload = window.__sent.at(-1);
        latestState.rulesEngine.enabled = false;
        latestState.phaseTracker.turn = 2;
        latestState.phaseTracker.index = ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_reaction");
        latestState.rulesEngine.deckConfirmedPlayerIds = ["solo:p1", "solo:p2"];
        latestState.rulesEngine.readyPlayerIds = ["solo:p1", "solo:p2"];
        latestState.players["solo:p1"].zones.deck.count = 11;
        latestState.players["solo:p2"].zones.deck.count = 23;
        renderAll();
        beginSoloInteraction("solo:p2");
        renderAll();
        const pileLayout = {
          left: [...document.querySelectorAll("#ubMyPiles [data-field-pile]")].map((pile) => pile.dataset.fieldPile),
          right: [...document.querySelectorAll("#ubOppPiles [data-field-pile]")].map((pile) => pile.dataset.fieldPile),
        };
        const originalSearchPile = searchPile;
        window.__soloPileSearch = null;
        searchPile = (ownerId, zoneName) => { window.__soloPileSearch = { ownerId, zone: zoneName }; };
        document.querySelector('[data-pile-trigger="solo:p2:graveyard"]').click();
        const pileSearch = window.__soloPileSearch;
        searchPile = originalSearchPile;
        const parsedPileKey = splitOwnerSuffixKey("solo:p2:graveyard");
        const parsedZoneCardKey = splitZoneCardKey(`solo:p2:graveyard:${cardIds[2]}`);
        endSoloInteraction();
        renderAll();
        const topCard = document.querySelector("#opponentHandFan [data-opponent-hand-card]");
        const initialTopCards = document.querySelectorAll("#opponentHandFan [data-opponent-hand-card]").length;
        const initialBottomCards = document.querySelectorAll("#myHandTray [data-hand-card]").length;
        const topStyle = getComputedStyle(topCard);
        const bottomPlayableCard = document.createElement("div");
        bottomPlayableCard.className = "hand-card is-playable";
        const topPlayableCard = document.createElement("button");
        topPlayableCard.className = "opponent-hand-card is-playable";
        document.body.append(bottomPlayableCard, topPlayableCard);
        const playableHighlight = (element) => ({
          borderColor: getComputedStyle(element).borderColor,
          boxShadow: getComputedStyle(element).boxShadow,
          innerBorderColor: getComputedStyle(element, "::after").borderColor,
          innerBoxShadow: getComputedStyle(element, "::after").boxShadow,
        });
        const matchingPlayableHighlight = {
          p1: playableHighlight(bottomPlayableCard),
          p2: playableHighlight(topPlayableCard),
        };
        bottomPlayableCard.remove();
        topPlayableCard.remove();
        const fan = document.querySelector("#opponentHandFan");
        const soloFanRect = fan.getBoundingClientRect();
        const soloCardRect = topCard.getBoundingClientRect();
        const savedFanClasses = fan.className;
        fan.classList.remove("solo-hand-fan", "solo-active-hand", "solo-inactive-hand");
        const normalFanRect = fan.getBoundingClientRect();
        const normalCardRect = topCard.getBoundingClientRect();
        fan.className = savedFanClasses;
        const zcMeRect = document.querySelector("#ubZcMe").getBoundingClientRect();
        const zcOppRect = document.querySelector("#ubZcOpp").getBoundingClientRect();
        const totalMeRect = document.querySelector("#ubTotals .ub-total.me").getBoundingClientRect();
        const totalOppRect = document.querySelector("#ubTotals .ub-total.opp").getBoundingClientRect();
        // since 152.1 the two totals flank the turn counter: each stays on its own player's side
        const fieldMiddle = (zcMeRect.left + zcMeRect.width / 2 + zcOppRect.left + zcOppRect.width / 2) / 2;
        const confrontationUiAtOuterSides = (
          totalMeRect.right <= fieldMiddle
          && totalOppRect.left >= fieldMiddle
        );
        const confrontationUiPositions = {
          me: totalMeRect.left + totalMeRect.width / 2,
          meZone: zcMeRect.left + zcMeRect.width / 2,
          opp: totalOppRect.left + totalOppRect.width / 2,
          oppZone: zcOppRect.left + zcOppRect.width / 2,
        };
        const topActive = document.querySelector("#opponentHandFan").classList.contains("solo-active-hand");
        const bottomInactive = document.querySelector("#handArea").classList.contains("solo-inactive-hand");
        const panelControls = document.querySelectorAll("#ubWhoOpp .ub-solo-controls button").length;
        document.querySelector("[data-ub-solo-edit-deck]").click();
        const deckEditor = {
          open: !document.querySelector("#importPanel").classList.contains("hidden"),
          playerId: myPlayerId,
          target: document.querySelector("#importDeckPlayer").textContent.trim(),
        };
        document.querySelector("#importCancelBtn").click();
        deckEditor.closed = document.querySelector("#importPanel").classList.contains("hidden");
        window.__sent = [];
        document.querySelector("#opponentHandFan [data-opponent-hand-card]").dispatchEvent(new MouseEvent("contextmenu", {
          bubbles: true,
          cancelable: true,
          clientX: 300,
          clientY: 100,
        }));
        const discard = [...document.querySelectorAll(".ctx-menu button")]
          .find((button) => button.textContent.trim() === t("handDiscard"));
        discard?.click();
        const manualSent = window.__sent[0];
        latestState.rulesEngine.priorityPlayerId = "solo:p1";
        latestState.phaseTracker.passedPlayerIds = ["solo:p2"];
        renderAll();
        const topInactiveAfter = document.querySelector("#opponentHandFan").classList.contains("solo-inactive-hand");
        const bottomActiveAfter = document.querySelector("#handArea").classList.contains("solo-active-hand");
        const syntheticWill = "solo-free-will";
        cardsById.set(syntheticWill, {
          id: syntheticWill,
          name: "Solo Will",
          type: "ephemeral_will",
          cost: 0,
          powerCost: "",
          effect: "",
          temperaments: [],
        });
        playedAbilitiesByCard.set(syntheticWill, []);
        latestState.players["solo:p2"].zones.hand = {
          cards: [syntheticWill],
          count: 1,
          owners: { [syntheticWill]: "solo:p2" },
        };
        latestState.rulesEngine.enabled = true;
        latestState.rulesEngine.priorityPlayerId = "solo:p2";
        latestState.phaseTracker.passedPlayerIds = [];
        window.__sent = [];
        renderAll();
        const assistedPlayable = evaluateForSoloPlayer(
          "solo:p2",
          () => handCardIsPlayable(syntheticWill),
        );
        const assistedOpened = beginRulesBoardAction({
          cardId: syntheticWill,
          zone: "hand",
          handIndex: 0,
          actingPlayerId: "solo:p2",
        });
        await new Promise((resolve) => setTimeout(resolve, 250));
        const assistedSent = window.__sent.find(
          (payload) => payload.type === "declare_rules_action",
        );
        return {
          topCards: initialTopCards,
          bottomCards: initialBottomCards,
          topActive,
          bottomInactive,
          topUpright: Number(new DOMMatrix(topStyle.transform).a) > 0,
          deckEditor,
          panelControls,
          pregameButtons,
          pregameGenericHidden,
          pregameP2Editor,
          pregameP2Import,
          p2OpeningActions,
          pileLayout,
          pileSearch,
          parsedPileKey,
          parsedZoneCardKey,
          handLayoutMatchesNormal: {
            fanTop: Math.abs(soloFanRect.top - normalFanRect.top) < 1,
            fanWidth: Math.abs(soloFanRect.width - normalFanRect.width) < 1,
            fanHeight: Math.abs(soloFanRect.height - normalFanRect.height) < 1,
            cardTop: Math.abs(soloCardRect.top - normalCardRect.top) < 1,
            cardWidth: Math.abs(soloCardRect.width - normalCardRect.width) < 1,
            cardHeight: Math.abs(soloCardRect.height - normalCardRect.height) < 1,
          },
          confrontationUiAtOuterSides,
          confrontationUiPositions,
          matchingPlayableHighlight,
          sent: manualSent,
          topInactiveAfter,
          bottomActiveAfter,
          assistedPlayable,
          assistedOpened,
          assistedSent,
        };
      });
      if (process.env.SCREENSHOT_DIR) {
        fs.mkdirSync(process.env.SCREENSHOT_DIR, { recursive: true });
        await page.screenshot({
          path: path.join(process.env.SCREENSHOT_DIR, `solo-${viewport.width}.png`),
        });
        await page.evaluate(() => {
          latestState.phaseTracker.turn = 1;
          latestState.phaseTracker.index = ADVANCED_PHASES.findIndex((phase) => phase.id === "recovery_start");
          latestState.rulesEngine.deckConfirmedPlayerIds = [];
          latestState.rulesEngine.readyPlayerIds = [];
          renderAll();
        });
        await page.screenshot({
          path: path.join(process.env.SCREENSHOT_DIR, `solo-decks-${viewport.width}.png`),
        });
        await page.evaluate(() => {
          latestState.phaseTracker.turn = 2;
          latestState.phaseTracker.index = ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_reaction");
          latestState.rulesEngine.deckConfirmedPlayerIds = ["solo:p1", "solo:p2"];
          latestState.rulesEngine.readyPlayerIds = ["solo:p1", "solo:p2"];
          renderAll();
        });
        await page.locator("[data-ub-solo-edit-deck]").click();
        await page.screenshot({
          path: path.join(process.env.SCREENSHOT_DIR, `solo-import-${viewport.width}.png`),
        });
        await page.locator("#importCancelBtn").click();
      }
      assert.equal(result.topCards, 2);
      assert.equal(result.bottomCards, 2);
      assert.equal(result.topActive, true);
      assert.equal(result.bottomInactive, true);
      assert.equal(result.topUpright, true);
      assert.deepEqual(result.deckEditor, {
        open: true,
        playerId: "solo:p2",
        target: "Deck du joueur P2",
        closed: true,
      });
      assert.equal(result.panelControls, 4);
      assert.deepEqual(result.pregameButtons.map(({ playerId, label }) => ({ playerId, label })), [
        { playerId: "solo:p1", label: "Importer un deck" },
        { playerId: "solo:p2", label: "Importer un deck" },
      ]);
      assert.notEqual(result.pregameButtons[0].tone, result.pregameButtons[1].tone);
      assert.equal(result.pregameGenericHidden, true);
      assert.deepEqual(result.pregameP2Editor, {
        open: true,
        playerId: "solo:p2",
        target: "Deck du joueur P2",
        playerIdAfterState: "solo:p2",
        targetAfterState: "Deck du joueur P2",
      });
      assert.equal(result.pregameP2Import.type, "import_deck");
      assert.equal(result.pregameP2Import.actingPlayerId, "solo:p2");
      assert.deepEqual(result.p2OpeningActions, {
        activePlayerId: "solo:p2",
        mulliganVisible: true,
        mulliganDisabled: false,
        readyVisible: true,
        readyDisabled: false,
        mulliganPayload: { type: "mulligan", actingPlayerId: "solo:p2" },
        readyPayload: { type: "set_rules_ready", actingPlayerId: "solo:p2" },
      });
      assert.deepEqual(result.pileLayout.left, [
        "solo:p1:deck",
        "solo:p1:graveyard",
        "solo:p1:exile",
        "solo:p1:receptacle",
      ]);
      assert.deepEqual(result.pileLayout.right, [
        "solo:p2:deck",
        "solo:p2:graveyard",
        "solo:p2:exile",
        "solo:p2:receptacle",
      ]);
      assert.deepEqual(result.pileSearch, { ownerId: "solo:p2", zone: "graveyard" });
      assert.deepEqual(result.parsedPileKey, ["solo:p2", "graveyard"]);
      assert.deepEqual(result.parsedZoneCardKey.slice(0, 2), ["solo:p2", "graveyard"]);
      assert.ok(result.parsedZoneCardKey[2]);
      assert.deepEqual(result.handLayoutMatchesNormal, {
        fanTop: true,
        fanWidth: true,
        fanHeight: true,
        cardTop: true,
        cardWidth: true,
        cardHeight: true,
      });
      assert.equal(result.confrontationUiAtOuterSides, true, JSON.stringify(result.confrontationUiPositions));
      assert.deepEqual(result.matchingPlayableHighlight.p2, result.matchingPlayableHighlight.p1);
      assert.equal(result.sent.actingPlayerId, "solo:p2");
      assert.equal(result.sent.type, "move_card");
      assert.equal(result.topInactiveAfter, true);
      assert.equal(result.bottomActiveAfter, true);
      assert.equal(result.assistedPlayable, true);
      assert.equal(result.assistedOpened, true);
      assert.equal(result.assistedSent.actingPlayerId, "solo:p2");
      assert.equal(result.assistedSent.source.cardId, "solo-free-will");
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log("Solo mode browser regression: OK");
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
