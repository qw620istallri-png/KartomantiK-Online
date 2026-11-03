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
      const page = await browser.newPage({ viewport });
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
        window.uiBeta.setEnabled(true);
        renderAll();
        const topCard = document.querySelector("#opponentHandFan [data-opponent-hand-card]");
        const initialTopCards = document.querySelectorAll("#opponentHandFan [data-opponent-hand-card]").length;
        const initialBottomCards = document.querySelectorAll("#myHandTray [data-hand-card]").length;
        const topStyle = getComputedStyle(topCard);
        const topActive = document.querySelector("#opponentHandFan").classList.contains("solo-active-hand");
        const bottomInactive = document.querySelector("#handArea").classList.contains("solo-inactive-hand");
        const panelControls = document.querySelectorAll("#ubWhoOpp .ub-solo-controls button").length;
        document.querySelector("[data-ub-solo-edit-deck]").click();
        const deckEditor = {
          open: !document.querySelector("#importPanel").classList.contains("hidden"),
          playerId: myPlayerId,
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
      }
      assert.equal(result.topCards, 2);
      assert.equal(result.bottomCards, 2);
      assert.equal(result.topActive, true);
      assert.equal(result.bottomInactive, true);
      assert.equal(result.topUpright, true);
      assert.deepEqual(result.deckEditor, { open: true, playerId: "solo:p2", closed: true });
      assert.equal(result.panelControls, 3);
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
