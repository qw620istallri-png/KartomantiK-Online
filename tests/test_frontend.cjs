const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("playwright");
const { PNG } = require("pngjs");

const publicRoot = path.resolve(__dirname, "..", "public");
const mime = {
  ".css": "text/css", ".html": "text/html", ".js": "text/javascript",
  ".json": "application/json", ".png": "image/png", ".webp": "image/webp",
  ".woff2": "font/woff2",
};

function startServer() {
  return new Promise((resolve) => {
    const server = http.createServer((request, response) => {
      const urlPath = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
      const relative = urlPath === "/" ? "index.html" : urlPath.replace(/^\/+/, "");
      const filePath = path.resolve(publicRoot, relative);
      if (!filePath.startsWith(publicRoot + path.sep) || !fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
        response.writeHead(404).end("Not found");
        return;
      }
      response.writeHead(200, { "Content-Type": mime[path.extname(filePath)] || "application/octet-stream" });
      fs.createReadStream(filePath).pipe(response);
    });
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

(async () => {
  const server = await startServer();
  const port = server.address().port;
  const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "chrome", headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  try {
    await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: "networkidle" });
    await page.waitForFunction(() => typeof copyCardMenuItem === "function" && cardsById.size >= 31);

    const result = await page.evaluate(() => {
      const ids = [...cardsById.values()]
        .sort((left, right) => (Number(left.points) || 0) - (Number(right.points) || 0))
        .slice(0, 31)
        .map((card) => card.id);
      const cardId = ids[0];
      const sideboardId = ids[30];
      const zone = (cards = []) => ({ cards: [...cards], count: cards.length });
      const zones = (deck = [], hand = []) => ({
        deck: zone(deck), hand: zone(hand), graveyard: zone(), exile: zone(), receptacle: zone(),
      });
      myPlayerId = "p1";
      isObserver = false;
      latestState = {
        players: {
          p1: {
            id: "p1", name: "P1", seat: 0, score: 0, zones: zones(ids.slice(1, 30), [cardId]),
            cardRarities: { [cardId]: "desert" },
            sideboard: [sideboardId],
            deckDefinition: {
              name: "Current test deck",
              cardRarities: { [cardId]: "desert" },
              groups: [
                { id: "main", kind: "deck", cardIds: ids.slice(0, 30) },
                { id: "side", kind: "sideboard", cardIds: [sideboardId] },
              ],
            },
          },
        },
        battlefield: [], tokens: [], drawings: [],
        phaseTracker: { enabled: false, advanced: false, index: 0, turn: 1, passedPlayerIds: [] },
      };

      window.__sent = [];
      send = (payload) => window.__sent.push(payload);
      renderHandTray();
      document.querySelector("[data-hand-card]").dispatchEvent(new MouseEvent("contextmenu", {
        bubbles: true, cancelable: true, clientX: 200, clientY: 200,
      }));
      const handLabels = [...document.querySelectorAll(".ctx-menu button")].map((button) => button.textContent.trim());
      const copyButton = [...document.querySelectorAll(".ctx-menu button")].find((button) => button.textContent.trim() === t("copyCard"));
      copyButton.click();

      const requestedZoneMenus = {};
      document.querySelector("#deckBrowserCards").innerHTML = dbCardHtml("p1", "deck", ids[1]);
      wirePileBrowserCards("p1", "deck");
      document.querySelector("#deckBrowserCards [data-zone-card]").dispatchEvent(new MouseEvent("contextmenu", {
        bubbles: true, cancelable: true, clientX: 220, clientY: 220,
      }));
      requestedZoneMenus.deck = [...document.querySelectorAll(".ctx-menu button")].map((button) => button.textContent.trim());
      closeContextMenu();

      const zoneList = document.createElement("div");
      zoneList.className = "zone-list";
      for (const [index, name] of ["graveyard", "exile", "receptacle"].entries()) {
        zoneList.insertAdjacentHTML("beforeend", `<div data-zone-card="p1:${name}:${ids[index + 2]}" data-card-owner="p1"></div>`);
      }
      document.body.appendChild(zoneList);
      wireZoneButtons();
      for (const name of ["graveyard", "exile", "receptacle"]) {
        zoneList.querySelector(`[data-zone-card^="p1:${name}:"]`).dispatchEvent(new MouseEvent("contextmenu", {
          bubbles: true, cancelable: true, clientX: 240, clientY: 240,
        }));
        requestedZoneMenus[name] = [...document.querySelectorAll(".ctx-menu button")].map((button) => button.textContent.trim());
        closeContextMenu();
      }
      zoneList.remove();

      latestState.battlefield = [{
        id: "field-1", ownerId: "p1", cardId, x: 100, y: 100,
        faceUp: true, rotation: 0, counters: {}, rarity: "desert", stackedOn: null,
      }];
      renderBattlefield();
      document.querySelector('.bf-card[data-item-id="field-1"]').dispatchEvent(new MouseEvent("contextmenu", {
        bubbles: true, cancelable: true, clientX: 260, clientY: 260,
      }));
      requestedZoneMenus.battlefield = [...document.querySelectorAll(".ctx-menu button")].map((button) => button.textContent.trim());
      closeContextMenu();

      latestState.battlefield = [{
        id: "copy-1", ownerId: "p1", cardId, x: 100, y: 100,
        faceUp: true, rotation: 0, counters: {}, rarity: "desert", stackedOn: null, isCopy: true,
      }];
      renderBattlefield();
      document.querySelector('.bf-card[data-item-id="copy-1"]').dispatchEvent(new MouseEvent("contextmenu", {
        bubbles: true, cancelable: true, clientX: 260, clientY: 260,
      }));
      const copyCounterButton = document.querySelector('.ctx-menu [data-counter-key="power"][data-counter-op="add"]');
      const copyCounterAvailable = Boolean(copyCounterButton);
      copyCounterButton?.click();
      closeContextMenu();

      const chatHasOnlyClose = !document.querySelector("#chatMinimizeBtn")
        && Boolean(document.querySelector("#chatCloseBtn"));
      const playerLogCloseInToolbar = Boolean(document.querySelector("#playerLogPanel .log-toolbar #playerLogCloseBtn"));
      document.querySelector("#playerLogPanel").classList.remove("hidden");
      document.querySelector("#playerLogCloseBtn").click();
      const playerLogClosed = document.querySelector("#playerLogPanel").classList.contains("hidden");

      const essenceLabels = essenceTokenMenuItems({ id: "essence-1", isEssence: true })
        .filter((item) => item.label).map((item) => item.label);
      const neutralLabels = essenceTokenMenuItems({ id: "neutral-1", isEssence: true, isNeutralCounter: true, label: "Ward" })
        .filter((item) => item.label).map((item) => item.label);

      document.querySelector("#createEssenceBtn").click();
      document.querySelector('[data-temperament="neutral"]').click();
      document.querySelector("#neutralTokenNameInput").value = "Doom";
      document.querySelector("#essenceCountInput").value = "4";
      document.querySelector("#essenceCreateBtn").click();

      openCurrentSideboard();
      const sideboard = {
        visible: !document.querySelector("#sideboardPanel").classList.contains("hidden"),
        warningVisible: !document.querySelector("#sideboardResetWarning").classList.contains("hidden"),
        resetOwnBoard: pendingDeckImport.resetOwnBoard,
        mainCount: pendingDeckImport.mainIds.length,
        sideboardCount: pendingDeckImport.sideboardIds.length,
        valid: deckImportIsValid(),
      };
      document.querySelector("#sideboardValidateBtn").click();
      sideboard.confirmVisible = !document.querySelector("#confirmPanel").classList.contains("hidden");
      document.querySelector("#confirmPanelOkBtn").click();
      const resetPayload = window.__sent.find((payload) => payload.type === "import_deck");
      sideboard.sentReset = resetPayload?.resetOwnBoard;
      sideboard.sentMainCount = resetPayload
        ? resetPayload.deck.groups.filter((group) => !["sideboard", "maybeboard"].includes(String(group.kind).toLowerCase()))
          .reduce((count, group) => count + group.cardIds.length, 0)
        : 0;

      showInspect(cardId);
      const art = document.querySelector("#inspectPanel .inspect-img");
      const surface = art.querySelector(".rarity-desert-surface");
      const artStyle = getComputedStyle(art);
      const surfaceStyle = getComputedStyle(surface);
      const desert = {
        rootClass: art.classList.contains("rarity-desert"),
        surface: Boolean(surface),
        edgeMask: surfaceStyle.maskImage || surfaceStyle.webkitMaskImage,
        rootMask: artStyle.maskImage || artStyle.webkitMaskImage,
        filter: artStyle.filter,
        transparentBackground: artStyle.backgroundColor,
        hasGrain: Boolean(surface.querySelector(".desert-grain-layer")),
        hasDiagonal: Boolean(surface.querySelector(".desert-diagonal-layer")),
        hasStorm: Boolean(surface.querySelector(".desert-storm-layer")),
      };
      const rarityProbe = document.createElement("div");
      rarityProbe.style.cssText = "position:fixed;left:20px;top:20px;width:280px;aspect-ratio:5/7;border-radius:12px;overflow:hidden";
      rarityProbe.className = `ko-rarity-card rarity-zen`;
      rarityProbe.setAttribute("style", `${rarityProbe.getAttribute("style")};${rarityCosmosStyle(cardId)}`);
      rarityProbe.innerHTML = `<img src="${cardImage(cardId)}" alt="">${rarityDecorMarkup("zen")}`;
      document.body.appendChild(rarityProbe);
      const probeRect = rarityProbe.getBoundingClientRect();
      updateRarityPointer(rarityProbe, { clientX: probeRect.right, clientY: probeRect.top }, false);
      const zenHolo = rarityProbe.querySelector(".rarity-zen-holo");
      const zenSecret = rarityProbe.querySelector(".rarity-zen-secret");
      const zen = {
        normalized: normalizeRarity("zen"),
        hasHolo: Boolean(zenHolo),
        hasSecret: Boolean(zenSecret),
        glow: getComputedStyle(rarityProbe).filter,
        zenA: rarityProbe.style.getPropertyValue("--zen-a"),
        holoBackground: getComputedStyle(zenHolo).backgroundImage,
        beamBackground: getComputedStyle(zenHolo, "::before").backgroundImage,
        secretBackground: getComputedStyle(zenSecret).backgroundImage,
        secretFoilBackground: getComputedStyle(zenSecret, "::before").backgroundImage,
        pointerLeft: rarityProbe.style.getPropertyValue("--pointer-from-left"),
        pointerTop: rarityProbe.style.getPropertyValue("--pointer-from-top"),
        pointerCenter: rarityProbe.style.getPropertyValue("--pointer-from-center"),
      };
      rarityProbe.className = "ko-rarity-card rarity-silver";
      rarityProbe.innerHTML = `<img src="${cardImage(cardId)}" alt="">`;
      const silver = {
        outline: getComputedStyle(rarityProbe).outlineStyle,
        beforeBackground: getComputedStyle(rarityProbe, "::before").backgroundImage,
        afterBackground: getComputedStyle(rarityProbe, "::after").backgroundImage,
        afterOpacity: getComputedStyle(rarityProbe, "::after").opacity,
      };
      rarityProbe.remove();
      const battlefieldStyle = getComputedStyle(document.querySelector("#battlefield"));
      const board = {
        width: BOARD_WIDTH,
        height: BOARD_HEIGHT,
        cssWidth: battlefieldStyle.width,
        cssHeight: battlefieldStyle.height,
        viewBox: document.querySelector("#drawLayer").getAttribute("viewBox"),
        rotatedOrigin: rotate180Pos({ x: 0, y: 0 }),
      };
      return {
        cardId, handLabels, requestedZoneMenus, sent: window.__sent, essenceLabels, neutralLabels, sideboard, desert, zen, silver,
        copyCounterAvailable, chatHasOnlyClose, playerLogCloseInToolbar, playerLogClosed, board, piles: PILE_SCREEN_POS,
        copyText: t("copyCard"), removeText: t("remove"), renameText: t("renameToken"),
        resetConfirmText: t("confirmResetBoard"),
      };
    });

    const pileDrag = await page.evaluate(() => {
      const ids = [...cardsById.keys()].slice(0, 6);
      const zone = (cards = []) => ({ cards: [...cards], count: cards.length, owners: Object.fromEntries(cards.map((cardId) => [cardId, "p1"])) });
      const zones = () => ({ deck: zone(), hand: zone(), graveyard: zone(), exile: zone(), receptacle: zone() });
      latestState.players.p1.zones.graveyard = zone([ids[0], ids[1]]);
      latestState.players.p1.zones.exile = zone([ids[2]]);
      latestState.players.p1.zones.receptacle = { cards: [ids[3]], count: 1, owners: { [ids[3]]: "p2" } };
      latestState.players.p2 = { id: "p2", name: "P2", seat: 1, score: 0, zones: zones(), cardRarities: {} };
      latestState.players.p2.zones.graveyard = zone([ids[4]]);
      renderPiles();

      const contexts = [];
      const originalResolveDrop = resolveDrop;
      resolveDrop = (ctx) => contexts.push(ctx);
      for (const zoneName of ["graveyard", "exile", "receptacle"]) {
        const source = document.querySelector(`[data-field-pile="p1:${zoneName}"] [data-pile-top-card]`);
        source?.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, cancelable: true, clientX: 10, clientY: 10 }));
        window.dispatchEvent(new PointerEvent("pointermove", { bubbles: true, clientX: 30, clientY: 30 }));
        window.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, clientX: 30, clientY: 30 }));
      }
      resolveDrop = originalResolveDrop;
      return {
        contexts: contexts.map(({ kind, cardId, cardOwnerId, fromOwnerId, fromZone }) => ({ kind, cardId, cardOwnerId, fromOwnerId, fromZone })),
        ownTopIds: ["graveyard", "exile", "receptacle"].map((zoneName) => document.querySelector(`[data-field-pile="p1:${zoneName}"] [data-pile-top-card]`)?.dataset.pileTopCard || null),
        opponentDraggable: Boolean(document.querySelector('[data-field-pile="p2:graveyard"] [data-pile-top-card]')),
      };
    });

    await page.evaluate(() => {
      document.querySelector("#sideboardPanel").classList.add("hidden");
      document.querySelector("#inspectPanel .inspect-main").style.background = "repeating-conic-gradient(#20e0c0 0 25%, #c020e0 0 50%) 0 0 / 36px 36px";
      document.querySelector("#inspectPanel .inspect-img").style.setProperty(
        "--desert-edge-mask", "linear-gradient(to right, transparent 0 40%, black 40% 100%)"
      );
      document.querySelector("#inspectPanel .inspect-img").style.setProperty("filter", "none", "important");
      document.getAnimations().forEach((animation) => {
        animation.pause();
        animation.currentTime = 0;
      });
    });
    const inspectArt = page.locator("#inspectPanel .inspect-img");
    const clip = await inspectArt.boundingBox();
    const snap = async () => PNG.sync.read(await page.screenshot({ clip, animations: "disabled" }));
    const masked = await snap();
    await inspectArt.evaluate((element) => { element.style.visibility = "hidden"; });
    const behind = await snap();
    await inspectArt.evaluate((element) => { element.style.visibility = ""; });
    const sample = (png, x, y) => {
      const index = (Math.floor(png.height * y) * png.width + Math.floor(png.width * x)) * 4;
      return [...png.data.subarray(index, index + 3)];
    };
    assert.deepEqual(sample(masked, .2, .5), sample(behind, .2, .5), "The transparent half must show the real background");
    assert.notDeepEqual(sample(masked, .65, .5), sample(behind, .65, .5), "The opaque half must keep the card artwork");
    await inspectArt.evaluate((element) => { element.style.removeProperty("filter"); });
    const glowing = await snap();
    assert.notDeepEqual(sample(glowing, .35, .5), sample(behind, .35, .5), "The exterior halo must remain visible through the cutout");

    const tournament = await page.evaluate(() => {
      const launcherInitiallyHidden = document.querySelector("#createTournamentBtn").classList.contains("hidden");
      document.querySelector("#tournamentToggleBtn").click();
      const launcherExpanded = !document.querySelector("#createTournamentBtn").classList.contains("hidden")
        && document.querySelector("#tournamentToggleBtn").getAttribute("aria-expanded") === "true";
      connectionRole = "organizer";
      isObserver = true;
      tournamentCodes = { player1: "PLAYER01", player2: "PLAYER02", spectator: "WATCH001", judge: "JUDGE001" };
      const catalog = [...cardsById.values()];
      const byNumber = (number) => catalog.find((card) => Number(card.collectionNumber) === number)?.id;
      const hoverCardId = byNumber(82) || catalog[0].id;
      latestState.mode = "tournament";
      latestState.tournament = {
        enabled: true,
        status: "lobby",
        seats: [
          { seat: 0, name: "P1", connected: true, deckCount: 30, deckReady: true },
          { seat: 1, name: "P2", connected: true, deckCount: 30, deckReady: true },
        ],
        policy: {
          bannedCardIds: [byNumber(82), byNumber(128), byNumber(86)].filter(Boolean),
          restrictedGroups: [{ id: "restricted-1", name: "Restricted group 1", cardIds: [byNumber(267), byNumber(284), byNumber(281)].filter(Boolean) }],
        },
        auditAlerts: [{ id: "alert-1", actorName: "P1", status: "pending", severity: "warning", zone: "deck" }],
      };
      latestState.roleCounts = { spectator: 2, judge: 1, organizer: 1, observer: 0 };
      latestState.roleParticipants = { spectator: ["Alice", "Bob"], judge: ["Judge Jane"], organizer: ["Organizer"] };
      latestState.recentLog = [
        { sequence: 1, timestamp: Date.now() / 1000, actorId: "host", actorName: "Organizer", type: "create_tournament", details: {}, turn: 1, phase: "recovery" },
        { sequence: 2, timestamp: Date.now() / 1000, actorId: "p1", actorName: "P1", type: "move_card", details: { cardId: hoverCardId, fromZone: "hand", toZone: "graveyard" }, turn: 1, phase: "recovery" },
      ];
      showTournamentScreen();
      document.querySelector('[data-presence-role="spectator"]').click();
      const organizer = {
        visible: !document.querySelector("#tournamentScreen").classList.contains("hidden"),
        codeCards: document.querySelectorAll(".tournament-access-card").length,
        distinctRoleCards: new Set([...document.querySelectorAll(".tournament-access-card")].map((card) => card.className)).size,
        seats: document.querySelectorAll(".tournament-seat").length,
        startEnabled: !document.querySelector("#tournamentStartBtn").disabled,
        logEntries: document.querySelectorAll(".tournament-log-entry").length,
        hasCardHover: Boolean(document.querySelector('[data-log-card]')),
        hasSearchAlert: Boolean(document.querySelector(".tournament-alert-chip.warning")),
        spectatorNames: document.querySelector("#tournamentPresenceList").textContent,
        bannedCards: document.querySelectorAll("#bannedCardsList .tournament-rule-chip").length,
        restrictedGroups: document.querySelectorAll("#restrictedGroups .restricted-group").length,
        minLogFont: Math.min(...[...document.querySelectorAll(".tournament-log-entry, .tournament-log-entry *")].map((element) => parseFloat(getComputedStyle(element).fontSize))),
      };
      const frenchLog = formatLogEntry({ actorId: "p1", actorName: "P1", type: "search_zone", details: { zone: "deck", count: 30, requiresShuffle: true } }, { language: "fr" });
      const englishExportLog = formatLogEntry({ actorId: "p1", actorName: "P1", type: "search_zone", details: { zone: "deck", count: 30, requiresShuffle: true } }, { language: "en" });
      latestState.tournament.status = "active";
      renderTournamentConsole();
      organizer.viewButtonEnabled = !document.querySelector("#tournamentViewMatchBtn").disabled;
      connectionRole = "judge";
      renderTournamentConsole();
      const judge = {
        codesHidden: document.querySelector("#tournamentCodeSection").classList.contains("hidden"),
        viewButtonVisible: !document.querySelector("#tournamentViewMatchBtn").classList.contains("hidden"),
      };
      document.querySelector("#tournamentViewMatchBtn").click();
      judge.matchVisible = !document.querySelector("#gameScreen").classList.contains("hidden");
      judge.returnVisible = !document.querySelector("#judgeReturnBtn").classList.contains("hidden");
      document.querySelector("#judgeReturnBtn").click();
      judge.returnedToConsole = !document.querySelector("#tournamentScreen").classList.contains("hidden");
      return { organizer, judge, launcherInitiallyHidden, launcherExpanded, frenchLog, englishExportLog };
    });
    await page.setViewportSize({ width: 390, height: 844 });
    const tournamentMobile = await page.evaluate(() => ({
      noHorizontalOverflow: document.documentElement.scrollWidth <= window.innerWidth,
      headerVisible: document.querySelector(".tournament-header").getBoundingClientRect().height > 0,
      seatsVisible: document.querySelectorAll(".tournament-seat").length === 2,
    }));
    await page.setViewportSize({ width: 1440, height: 1000 });

    assert(result.handLabels.includes(result.copyText));
    assert.equal(result.sent[0].type, "copy_card");
    assert.equal(result.sent[0].cardId, result.cardId);
    assert.equal(result.sent[0].fromZone, "hand");
    for (const [zoneName, labels] of Object.entries(result.requestedZoneMenus)) {
      assert(labels.includes(result.copyText), `Copy action missing from ${zoneName}`);
    }
    assert.equal(result.copyCounterAvailable, true);
    assert(result.sent.some((payload) => payload.type === "add_counter" && payload.itemId === "copy-1" && payload.counterKey === "power" && payload.delta === 1));
    assert.equal(result.chatHasOnlyClose, true);
    assert.equal(result.playerLogCloseInToolbar, true);
    assert.equal(result.playerLogClosed, true);
    assert.deepEqual(pileDrag.contexts, [
      { kind: "card", cardId: pileDrag.ownTopIds[0], cardOwnerId: "p1", fromOwnerId: "p1", fromZone: "graveyard" },
      { kind: "card", cardId: pileDrag.ownTopIds[1], cardOwnerId: "p1", fromOwnerId: "p1", fromZone: "exile" },
      { kind: "card", cardId: pileDrag.ownTopIds[2], cardOwnerId: "p2", fromOwnerId: "p1", fromZone: "receptacle" },
    ]);
    assert.equal(pileDrag.opponentDraggable, false);
    assert.deepEqual(result.board, {
      width: 1741, height: 1549, cssWidth: "1741px", cssHeight: "1549px",
      viewBox: "0 0 1741 1549", rotatedOrigin: { x: 1591, y: 1339 },
    });
    assert.deepEqual(result.piles, {
      0: {
        0: { deck: { x: 1368, y: 1038 }, graveyard: { x: 1539, y: 1038 }, receptacle: { x: 1368, y: 1295 }, exile: { x: 1539, y: 1295 } },
        1: { deck: { x: 225, y: 300 }, graveyard: { x: 47, y: 300 }, receptacle: { x: 225, y: 20 }, exile: { x: 47, y: 50 } },
      },
      1: {
        0: { deck: { x: 226, y: 303 }, graveyard: { x: 52, y: 303 }, receptacle: { x: 226, y: 48 }, exile: { x: 52, y: 48 } },
        1: { deck: { x: 1368, y: 1040 }, graveyard: { x: 1542, y: 1040 }, receptacle: { x: 1368, y: 1296 }, exile: { x: 1542, y: 1296 } },
      },
    });
    assert.deepEqual(result.essenceLabels, ["+1", "−1", result.removeText]);
    assert(result.neutralLabels.includes(result.renameText));
    const neutralCreate = result.sent.find((payload) => payload.type === "create_essence_token");
    assert.equal(neutralCreate.neutral, true);
    assert.equal(neutralCreate.label, "Doom");
    assert.equal(neutralCreate.count, 4);
    assert.deepEqual(result.sideboard, {
      visible: true, warningVisible: true, resetOwnBoard: true, mainCount: 30, sideboardCount: 1,
      valid: true, confirmVisible: true, sentReset: true, sentMainCount: 30,
    });
    assert.match(result.resetConfirmText, /active imported deck|deck actif importé|mazzo attivo importato/i);
    assert.equal(result.desert.rootClass, true);
    assert.equal(result.desert.surface, true);
    assert.match(result.desert.edgeMask, /desert-edge-mask\.png/);
    assert.equal(result.desert.rootMask, "none");
    assert.match(result.desert.filter, /drop-shadow/);
    assert.equal(result.desert.transparentBackground, "rgba(0, 0, 0, 0)");
    assert.equal(result.desert.hasGrain, true);
    assert.equal(result.desert.hasDiagonal, true);
    assert.equal(result.desert.hasStorm, true);
    assert.equal(result.zen.normalized, "zen");
    assert.equal(result.zen.hasHolo, true);
    assert.equal(result.zen.hasSecret, true);
    assert.match(result.zen.glow, /drop-shadow/);
    assert.notEqual(result.zen.zenA, "");
    assert.match(result.zen.holoBackground, /repeating-linear-gradient/);
    assert.match(result.zen.beamBackground, /repeating-linear-gradient/);
    assert.match(result.zen.secretBackground, /glitter\.webp/);
    assert.match(result.zen.secretFoilBackground, /geometric\.webp/);
    assert.equal(result.zen.pointerLeft, "1.000");
    assert.equal(result.zen.pointerTop, "0.000");
    assert.equal(result.zen.pointerCenter, "1.000");
    assert.equal(result.silver.outline, "solid");
    assert.match(result.silver.beforeBackground, /radial-gradient/);
    assert.match(result.silver.afterBackground, /repeating-linear-gradient/);
    assert.doesNotMatch(result.silver.afterBackground, /metal\.png|grain\.webp/);
    assert.equal(result.silver.afterOpacity, "0.62");
    assert.equal(tournament.launcherInitiallyHidden, true);
    assert.equal(tournament.launcherExpanded, true);
    assert.equal(tournament.organizer.visible, true);
    assert.equal(tournament.organizer.codeCards, 4);
    assert.equal(tournament.organizer.distinctRoleCards, 4);
    assert.equal(tournament.organizer.seats, 2);
    assert.equal(tournament.organizer.startEnabled, true);
    assert.equal(tournament.organizer.logEntries, 2);
    assert.equal(tournament.organizer.hasCardHover, true);
    assert.equal(tournament.organizer.hasSearchAlert, true);
    assert.match(tournament.organizer.spectatorNames, /Alice/);
    assert.match(tournament.organizer.spectatorNames, /Bob/);
    assert.equal(tournament.organizer.bannedCards, 3);
    assert.equal(tournament.organizer.restrictedGroups, 1);
    assert.equal(tournament.organizer.viewButtonEnabled, true);
    assert(tournament.organizer.minLogFont >= 14);
    assert.match(tournament.frenchLog, /fouillé|mélange/);
    assert.match(tournament.englishExportLog, /searched|shuffle/);
    assert.deepEqual(tournament.judge, {
      codesHidden: true, viewButtonVisible: true, matchVisible: true, returnVisible: true, returnedToConsole: true,
    });
    assert.deepEqual(tournamentMobile, { noHorizontalOverflow: true, headerVisible: true, seatsVisible: true });
    assert.deepEqual(errors, []);
    if (process.env.SCREENSHOT_PATH) {
      await page.evaluate(() => {
        document.querySelector("#sideboardPanel").classList.add("hidden");
        document.querySelector("#inspectPanel .inspect-main").style.background = "repeating-conic-gradient(#19d4c8 0 25%, #6e2388 0 50%) 50% / 40px 40px";
      });
      await page.locator("#inspectPanel .inspect-main").screenshot({ path: process.env.SCREENSHOT_PATH });
    }
    process.stdout.write("Frontend feature regression: OK\n");
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
