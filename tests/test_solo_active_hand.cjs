const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "..");
const publicRoot = path.join(root, "public");
const qaDir = process.argv[2] ? path.resolve(process.argv[2]) : null;
if (qaDir) fs.mkdirSync(qaDir, { recursive: true });
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
      const setup = await page.evaluate(() => {
        const cardIds = [...cardsById.values()]
          .filter((card) => card.type === "manifestation" && !String(card.effect || "").includes("Cannot be played as First Manifestation"))
          .slice(0, 2)
          .map((card) => card.id);
        const zone = (cards, ownerId) => ({
          cards,
          count: cards.length,
          owners: Object.fromEntries(cards.map((cardId) => [cardId, ownerId])),
        });
        const zones = (hand, ownerId) => ({
          hand: zone(hand, ownerId),
          deck: zone([], ownerId),
          graveyard: zone([], ownerId),
          exile: zone([], ownerId),
          receptacle: zone([], ownerId),
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
            "solo:p1": { id: "solo:p1", name: "P1", seat: 0, score: 0, zones: zones([cardIds[0]], "solo:p1") },
            "solo:p2": { id: "solo:p2", name: "P2", seat: 1, score: 0, zones: zones([cardIds[1]], "solo:p2") },
          },
          battlefield: [],
          tokens: [],
          strokes: [],
          ended: false,
          phaseTracker: {
            enabled: true,
            advanced: true,
            turn: 2,
            index: ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_choose"),
            passedPlayerIds: [],
          },
          rulesEngine: {
            enabled: true,
            priorityPlayerId: "solo:p1",
            priorityPasses: [],
            actionStack: [],
            pendingChoice: null,
            deckConfirmedPlayerIds: ["solo:p1", "solo:p2"],
            readyPlayerIds: ["solo:p1", "solo:p2"],
            firstManifestationComplete: false,
            firstManifestationItemIds: { "solo:p1": "first-p1" },
            firstManifestationValidatedPlayerIds: ["solo:p1"],
            trapPlayerIds: [],
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
        document.querySelector("#gameScreen").classList.add("ui-beta");
        renderAll();
        return {
          p2CardId: cardIds[1],
          actorAfterRender: myPlayerId,
          topActive: document.querySelector("#opponentHandFan").classList.contains("solo-active-hand"),
          bottomInactive: document.querySelector("#handArea").classList.contains("solo-inactive-hand"),
          topPlayable: document.querySelector("#opponentHandFan [data-opponent-hand-card]").classList.contains("is-playable"),
        };
      });
      await page.waitForTimeout(500);
      Object.assign(setup, await page.evaluate(() => {
        const scaleOf = (element) => {
          const matrix = new DOMMatrix(getComputedStyle(element).transform);
          return Math.hypot(matrix.a, matrix.b);
        };
        return {
          topScale: scaleOf(document.querySelector("#opponentHandFan")),
          bottomScale: scaleOf(document.querySelector("#handArea")),
        };
      }));

      const topCard = page.locator("#opponentHandFan [data-opponent-hand-card]");
      await topCard.dispatchEvent("mouseenter");
      await page.waitForTimeout(260);
      if (qaDir) {
        await page.screenshot({
          path: path.join(qaDir, `solo-p2-active-${viewport.width}x${viewport.height}.png`),
        });
      }
      const topHover = await page.locator(".hand-card-hover-clone").boundingBox();
      const topSourceOpacity = await topCard.evaluate((element) => getComputedStyle(element).opacity);
      await topCard.dispatchEvent("mouseleave");
      await page.waitForTimeout(220);

      const bottomCard = page.locator("#myHandTray [data-hand-card]");
      await bottomCard.dispatchEvent("mouseenter");
      await page.waitForTimeout(260);
      const bottomHover = await page.locator(".hand-card-hover-clone").boundingBox();
      await bottomCard.dispatchEvent("mouseleave");
      await page.waitForTimeout(220);

      const dragSource = await topCard.boundingBox();
      const battlefield = await page.locator("#battlefieldWrap").boundingBox();
      await page.mouse.move(dragSource.x + dragSource.width / 2, dragSource.y + dragSource.height / 2);
      await page.mouse.down();
      await page.mouse.move(battlefield.x + battlefield.width / 2, battlefield.y + battlefield.height / 2, { steps: 12 });
      await page.mouse.up();
      const drag = await page.evaluate(() => (
        window.__sent.find((entry) => entry.type === "place_card") || null
      ));

      await page.evaluate(() => {
        const p2CardId = latestState.players["solo:p2"].zones.hand.cards[0];
        latestState.rulesEngine.enabled = false;
        latestState.rulesEngine.priorityPlayerId = null;
        latestState.phaseTracker.passedPlayerIds = [];
        latestState.battlefield = [{
          id: "solo-p2-field",
          cardId: p2CardId,
          ownerId: "solo:p2",
          controllerId: "solo:p2",
          faceUp: true,
          fieldZone: "confrontation",
          x: 900,
          y: 400,
          rotation: 0,
          counters: { power: 2, tempCounter: -1 },
          stackedOn: null,
        }];
        window.__sent = [];
        endSoloInteraction();
        renderAll();
      });
      await page.waitForTimeout(500);

      const expandButton = page.locator("[data-ub-solo-toggle-hand]");
      const expandButtonCount = await expandButton.count();
      let expandedHand = null;
      if (expandButtonCount) {
        await expandButton.click();
        await page.waitForTimeout(260);
        const expandedTopCard = await page.locator("#opponentHandFan [data-opponent-hand-card]").boundingBox();
        const activeBottomCard = await page.locator("#myHandTray [data-hand-card]").boundingBox();
        expandedHand = {
          pressed: await expandButton.getAttribute("aria-pressed"),
          classApplied: await page.locator("#opponentHandFan").evaluate((element) => element.classList.contains("solo-hand-expanded")),
          heightRatio: expandedTopCard.height / activeBottomCard.height,
        };
      }

      const manualCounters = await page.locator('.bf-card[data-item-id="solo-p2-field"] .bf-counter:not(.bf-gem-essence)').evaluateAll((elements) => (
        elements.map((element) => {
          const style = getComputedStyle(element);
          return {
            background: style.backgroundColor,
            borderColor: style.borderTopColor,
            borderRadius: style.borderRadius,
          };
        })
      ));
      if (qaDir) {
        await page.screenshot({
          path: path.join(qaDir, `solo-p2-expanded-manual-${viewport.width}x${viewport.height}.png`),
        });
      }
      await page.locator('.bf-card[data-item-id="solo-p2-field"]').dispatchEvent("contextmenu", {
        button: 2,
        clientX: 700,
        clientY: 300,
      });
      await page.locator(".ctx-menu button").filter({ hasText: "Retourner" }).click();
      const flip = await page.evaluate(() => (
        window.__sent.find((entry) => entry.type === "flip_card") || null
      ));

      assert.equal(setup.actorAfterRender, "solo:p1");
      assert.equal(setup.topActive, true);
      assert.equal(setup.bottomInactive, true);
      assert.equal(setup.topPlayable, true);
      assert.ok(setup.topScale > 1.04, `P2 active scale was ${setup.topScale}`);
      assert.ok(setup.bottomScale < 0.9, `P1 inactive scale was ${setup.bottomScale}`);
      assert.ok(topHover.y < viewport.height / 2, `P2 hover opened too low at ${topHover.y}`);
      assert.ok(topHover.height / bottomHover.height > 0.85, `P2 hover was too small: ${topHover.height}/${bottomHover.height}`);
      assert.ok(topHover.height / bottomHover.height < 1.15, `P2 hover was too large: ${topHover.height}/${bottomHover.height}`);
      assert.equal(topSourceOpacity, "0");
      assert.equal(drag?.actingPlayerId, "solo:p2");
      assert.equal(drag?.cardId, setup.p2CardId);
      assert.equal(drag?.faceUp, false);
      assert.equal(expandButtonCount, 1);
      assert.deepEqual(expandedHand && {
        pressed: expandedHand.pressed,
        classApplied: expandedHand.classApplied,
      }, { pressed: "true", classApplied: true });
      assert.ok(expandedHand.heightRatio > 0.9 && expandedHand.heightRatio < 1.1, `Expanded P2/P1 height ratio was ${expandedHand.heightRatio}`);
      assert.equal(manualCounters.length, 2);
      assert.ok(manualCounters.every((counter) => counter.background === "rgb(8, 11, 15)"), JSON.stringify(manualCounters));
      assert.ok(manualCounters.every((counter) => counter.borderRadius === "999px"), JSON.stringify(manualCounters));
      assert.notEqual(manualCounters[0].borderColor, manualCounters[1].borderColor);
      assert.equal(flip?.actingPlayerId, "solo:p2");
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log("Solo active hand regression: OK");
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
