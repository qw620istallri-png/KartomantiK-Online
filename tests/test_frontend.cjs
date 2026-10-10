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
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, locale: "fr-FR" });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  try {
    await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: "networkidle" });
    await page.waitForFunction(() => typeof copyCardMenuItem === "function" && cardsById.size === 450);

    const innerDesertImport = await page.evaluate(async () => {
      const collectionNumbers = [
        427, 301, 325, 349, 373, 397, 302, 303, 326, 327,
        350, 351, 374, 375, 398, 399, 304, 305, 328, 329,
        352, 353, 376, 377, 400, 401, 432, 306, 307, 330,
      ];
      const expectedIds = collectionNumbers.map((number) => cardsByNumber.get(number)?.id);
      const expectedPoints = expectedIds.reduce(
        (total, cardId) => total + Number(cardsById.get(cardId)?.points || 0),
        0,
      );
      const listDeck = parseDeckListText([
        "DECKOMANTIK LIST",
        "[Deck] Inner Desert regression",
        "[Category:manifestations]",
        ...collectionNumbers.map((number) => `#${number}`),
      ].join("\n"));
      const listCandidate = splitDeckForEditor(listDeck, "List import", false);
      const jsonDeck = {
        app: "DeckomantiK",
        name: "Inner Desert JSON",
        groups: [{ kind: "manifestations", cardIds: expectedIds }],
      };
      const jsonParsed = await readDeckImportText(JSON.stringify(jsonDeck));
      const jsonCandidate = splitDeckForEditor(jsonParsed.deck, jsonParsed.name, false);
      const sharedDeck = expandDkShareDeck({
        n: "Inner Desert share",
        g: [{ k: "manifestations", c: collectionNumbers.map((number) => number - 1) }],
      });
      const shareCandidate = splitDeckForEditor(sharedDeck, sharedDeck.name, false);

      return {
        expectedIds,
        expectedPoints,
        listIds: listCandidate.mainIds,
        listPoints: deckImportPoints(listCandidate.mainIds),
        listValidation: deckImportValidation(listCandidate),
        jsonIds: jsonCandidate.mainIds,
        jsonPoints: deckImportPoints(jsonCandidate.mainIds),
        shareIds: shareCandidate.mainIds,
        sharePoints: deckImportPoints(shareCandidate.mainIds),
        flem: cardsByNumber.get(301),
        bob: cardsByNumber.get(434),
      };
    });

    const result = await page.evaluate(() => {
      let rulesBetaPayload = null;
      const originalConnectAndJoin = connectAndJoin;
      connectAndJoin = (payload) => { rulesBetaPayload = payload; };
      document.querySelector("#rulesBetaInput").checked = true;
      document.querySelector("#createName").value = "Beta tester";
      document.querySelector("#createBtn").click();
      const casualPayload = rulesBetaPayload;
      document.querySelector("#createTournamentBtn").click();
      const tournamentPayload = rulesBetaPayload;
      connectAndJoin = originalConnectAndJoin;
      const rulesBetaCreate = {
        casualPayload,
        tournamentPayload,
        insideTournamentLauncher: document.querySelector("#rulesBetaInput").closest("#tournamentLauncherOptions") !== null,
        label: document.querySelector("#rulesBetaLabel").textContent,
        hintFontSize: parseFloat(getComputedStyle(document.querySelector("#rulesBetaHint")).fontSize),
      };
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
        cardId, handLabels, requestedZoneMenus, sent: window.__sent, essenceLabels, neutralLabels, sideboard, desert, zen, silver, rulesBetaCreate,
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

    const wanderingVeteranUi = await page.evaluate(() => {
      const savedState = structuredClone(latestState);
      const veteranId = "iwpmdq754ew0mw7_en";
      const zone = (cards = []) => ({
        cards: [...cards], count: cards.length,
        owners: Object.fromEntries(cards.map((cardId) => [cardId, "p1"])),
      });
      latestState.players.p1.zones.graveyard = zone([veteranId]);
      latestState.phaseTracker = {
        enabled: true,
        advanced: true,
        index: ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_reaction"),
        turn: 2,
        passedPlayerIds: [],
      };
      latestState.rulesEngine = {
        enabled: true, priorityPlayerId: "p1", priorityPasses: [], actionStack: [],
        pendingChoice: null, ongoingEffects: [], firstManifestationItemIds: {},
        firstManifestationValidatedPlayerIds: [], firstManifestationComplete: true,
        playPermissions: [{
          id: "permission-veteran", playerId: "p1", cardId: veteranId,
          fromZone: "graveyard", phaseIds: ["confrontation_reaction"],
          asSupport: true, temperamentOverride: "hollow", turn: 2,
        }],
      };
      renderPiles();
      const playable = document.querySelector('[data-rules-zone-play-card]');
      const initial = {
        exists: Boolean(playable),
        playable: playable?.classList.contains("is-playable") || false,
        enabled: playable?.dataset.rulesZonePlayEnabled,
        badge: playable?.querySelector("span")?.textContent || "",
        badgeFont: parseFloat(getComputedStyle(playable?.querySelector("span")).fontSize),
      };
      const contexts = [];
      const originalResolveDrop = resolveDrop;
      resolveDrop = (ctx) => contexts.push(ctx);
      playable?.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, cancelable: true, clientX: 20, clientY: 20 }));
      window.dispatchEvent(new PointerEvent("pointermove", { bubbles: true, clientX: 45, clientY: 45 }));
      window.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, clientX: 45, clientY: 45 }));
      resolveDrop = originalResolveDrop;

      latestState.rulesEngine.priorityPlayerId = "p2";
      renderPiles();
      const waiting = document.querySelector('[data-rules-zone-play-card]');
      const waitingState = {
        exists: Boolean(waiting),
        playable: waiting?.classList.contains("is-playable") || false,
        enabled: waiting?.dataset.rulesZonePlayEnabled,
      };

      latestState.battlefield.push({
        id: "veteran-support", ownerId: "p1", cardId: veteranId,
        x: 600, y: 500, faceUp: true, rotation: 0, counters: {},
        fieldZone: "confrontation", isSupport: true, temperamentOverride: "hollow",
      });
      renderBattlefield();
      const supportMarker = document.querySelector('[data-item-id="veteran-support"] .rules-support-badge');
      const result = {
        veteranId, initial, waitingState,
        dragContext: contexts[0] ? {
          kind: contexts[0].kind, cardId: contexts[0].cardId,
          cardOwnerId: contexts[0].cardOwnerId, fromOwnerId: contexts[0].fromOwnerId,
          fromZone: contexts[0].fromZone,
        } : null,
        supportMarker: supportMarker?.textContent || "",
        supportMarkerFont: supportMarker ? parseFloat(getComputedStyle(supportMarker).fontSize) : 0,
      };
      latestState = savedState;
      renderAll();
      return result;
    });

    const supportUi = await page.evaluate(() => {
      const savedState = structuredClone(latestState);
      const byNumber = (number) => [...cardsById.values()].find((card) => Number(card.collectionNumber) === number);
      const fromHand = byNumber(1);
      const allowedFirst = byNumber(7);
      const fromInterzone = byNumber(3);
      const noSupport = [...cardsById.values()].find((card) => (
        card.type === "manifestation"
        && !String(card.effect || "").startsWith("Support.")
        && !String(card.effect || "").startsWith("Support from hand.")
        && !String(card.effect || "").includes("Cannot be played as First Manifestation")
        && ![fromHand.id, allowedFirst.id, fromInterzone.id].includes(card.id)
      ));
      const zone = (cards = []) => ({
        cards: [...cards], count: cards.length,
        owners: Object.fromEntries(cards.map((cardId) => [cardId, "p1"])),
      });
      latestState.players.p1.zones.hand = zone([fromHand.id, allowedFirst.id, noSupport.id]);
      latestState.rulesEngine = {
        enabled: true, priorityPlayerId: "p1", priorityPasses: [], actionStack: [],
        pendingChoice: null, ongoingEffects: [], firstManifestationItemIds: {},
        firstManifestationValidatedPlayerIds: [], firstManifestationComplete: false,
        playPermissions: [],
      };
      latestState.phaseTracker = {
        enabled: true, advanced: true,
        index: ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_choose"),
        turn: 2, passedPlayerIds: [],
      };
      renderHandTray();
      const firstStep = {
        forbidden: document.querySelector(`[data-hand-card="${fromHand.id}"]`).classList.contains("is-playable"),
        allowed: document.querySelector(`[data-hand-card="${allowedFirst.id}"]`).classList.contains("is-playable"),
      };

      latestState.rulesEngine.firstManifestationComplete = true;
      latestState.phaseTracker.index = ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_reaction");
      renderHandTray();
      const reactionStep = {
        supportFromHand: document.querySelector(`[data-hand-card="${fromHand.id}"]`).classList.contains("is-playable"),
        ordinary: document.querySelector(`[data-hand-card="${noSupport.id}"]`).classList.contains("is-playable"),
      };
      const contexts = [];
      const originalResolveDrop = resolveDrop;
      resolveDrop = (ctx) => contexts.push(ctx);
      const handCard = document.querySelector(`[data-hand-card="${fromHand.id}"]`);
      handCard.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, cancelable: true, clientX: 300, clientY: 800 }));
      window.dispatchEvent(new PointerEvent("pointermove", { bubbles: true, clientX: 340, clientY: 740 }));
      window.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, clientX: 340, clientY: 740 }));
      resolveDrop = originalResolveDrop;

      latestState.players.p1.zones.hand = zone([]);
      latestState.battlefield = [
        { id: "printed-support", ownerId: "p1", cardId: fromInterzone.id, x: 500, y: 500, faceUp: true, rotation: 0, counters: {}, fieldZone: "interzone" },
        { id: "ordinary-interzone", ownerId: "p1", cardId: noSupport.id, x: 700, y: 500, faceUp: true, rotation: 0, counters: {}, fieldZone: "interzone" },
      ];
      renderBattlefield();
      const contextLabels = (itemId) => {
        document.querySelector(`[data-item-id="${itemId}"]`).dispatchEvent(new MouseEvent("contextmenu", {
          bubbles: true, cancelable: true, clientX: 600, clientY: 500,
        }));
        const labels = [...document.querySelectorAll(".ctx-menu button")].map((button) => button.textContent.trim());
        closeContextMenu();
        return labels;
      };
      const interzoneStep = {
        printedHasAction: contextLabels("printed-support").includes(t("playInSupport")),
        ordinaryHasAction: contextLabels("ordinary-interzone").includes(t("playInSupport")),
      };
      latestState.battlefield[0].fieldZone = "confrontation";
      latestState.battlefield[0].isSupport = true;
      renderBattlefield();
      const marker = document.querySelector('[data-item-id="printed-support"] .rules-support-badge');
      const supportResolutionLog = formatLogEntry({
        actorId: "p1", actorName: "P1", type: "rules_confrontation_cleanup",
        details: {
          winnerId: "p1", captured: [], supportExiled: [],
          supportResolved: [{
            kind: "opponent_vessel_score", cardId: fromInterzone.id,
            itemId: "printed-support", playerId: "p2", delta: 10, score: 10,
          }],
        },
      }, { language: "fr", html: true });
      const result = {
        firstStep, reactionStep, interzoneStep,
        dragContext: contexts[0] ? {
          kind: contexts[0].kind, cardId: contexts[0].cardId,
          fromOwnerId: contexts[0].fromOwnerId, fromZone: contexts[0].fromZone,
        } : null,
        expectedHandSupportId: fromHand.id,
        marker: marker?.textContent || "",
        markerFont: marker ? parseFloat(getComputedStyle(marker).fontSize) : 0,
        markerRight: marker ? getComputedStyle(marker).right : "",
        supportResolutionLog,
      };
      latestState = savedState;
      renderAll();
      return result;
    });

    const targetedSupportUi = await page.evaluate(() => {
      const savedState = structuredClone(latestState);
      const savedPlayerId = myPlayerId;
      const savedObserver = isObserver;
      const originalSend = send;
      const byNumber = (number) => [...cardsById.values()].find((card) => Number(card.collectionNumber) === number);
      const chiff = byNumber(58);
      const ownSupportCard = byNumber(1);
      const opposingSupportCard = byNumber(3);
      const zone = (cards = [], ownerId = "p1") => ({
        cards: [...cards], count: cards.length,
        owners: Object.fromEntries(cards.map((cardId) => [cardId, ownerId])),
      });
      const zones = (hand = [], ownerId = "p1") => ({
        deck: zone([], ownerId), hand: zone(hand, ownerId), graveyard: zone([], ownerId),
        exile: zone([], ownerId), receptacle: zone([], ownerId),
      });
      myPlayerId = "p1";
      isObserver = false;
      latestState = {
        players: {
          p1: { id: "p1", name: "P1", seat: 0, score: 0, zones: zones([chiff.id], "p1") },
          p2: { id: "p2", name: "P2", seat: 1, score: 0, zones: zones([], "p2") },
        },
        battlefield: [
          { id: "own-support", ownerId: "p1", cardId: ownSupportCard.id, x: 480, y: 470, faceUp: true, rotation: 0, counters: {}, fieldZone: "confrontation", isSupport: true, effectivePower: 1 },
          { id: "opponent-support", ownerId: "p2", cardId: opposingSupportCard.id, x: 820, y: 470, faceUp: true, rotation: 0, counters: {}, fieldZone: "confrontation", isSupport: true, effectivePower: 1 },
        ],
        tokens: [], drawings: [],
        phaseTracker: {
          enabled: true, advanced: true,
          index: ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_reaction"),
          turn: 3, passedPlayerIds: [],
        },
        rulesEngine: {
          enabled: true, priorityPlayerId: "p1", priorityPasses: [], actionStack: [],
          pendingChoice: null, ongoingEffects: [], firstManifestationItemIds: {},
          firstManifestationValidatedPlayerIds: ["p1", "p2"], firstManifestationComplete: true,
          playPermissions: [],
          supportEntries: [{ turn: 3, controllerId: "p2", fromZone: "interzone", itemId: "opponent-support" }],
          playRestrictions: [],
        },
      };
      renderBattlefield();
      renderHandTray();
      const conditionUnlocked = handCardIsPlayable(chiff.id);
      latestState.rulesEngine.playRestrictions = [{ turn: 3, playerId: "p1", cardId: chiff.id }];
      const returnedCopyBlocked = !handCardIsPlayable(chiff.id);
      latestState.players.p1.zones.hand.cards.push(chiff.id);
      latestState.players.p1.zones.hand.count = 2;
      const secondCopyStillPlayable = handCardIsPlayable(chiff.id);
      latestState.players.p1.zones.hand = zone([chiff.id], "p1");
      latestState.rulesEngine.playRestrictions = [];

      window.__targetedSupportSent = [];
      send = (payload) => window.__targetedSupportSent.push(payload);
      const placement = {
        type: "place_card", fromZone: "hand", cardId: chiff.id, faceUp: true,
        x: 650, y: 570,
      };
      requestCardPlacement(placement, { cardId: chiff.id, zone: "hand", handIndex: 0 });
      const offeredTargetIds = (pendingRulesBoardFlow?.draft?.structuredTargets || []).map((target) => target.id);
      const ownHighlighted = document.querySelector('[data-item-id="own-support"]')?.classList.contains("rules-valid-target") || false;
      const opponentTarget = document.querySelector('[data-item-id="opponent-support"]');
      const opponentHighlighted = opponentTarget?.classList.contains("rules-valid-target") || false;
      opponentTarget?.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, cancelable: true }));
      const payload = window.__targetedSupportSent[0] || null;

      closeRulesBoardFlow();
      send = originalSend;
      latestState = savedState;
      myPlayerId = savedPlayerId;
      isObserver = savedObserver;
      renderAll();
      return {
        conditionUnlocked, returnedCopyBlocked, secondCopyStillPlayable,
        offeredTargetIds, ownHighlighted, opponentHighlighted, payload,
      };
    });

    const rulesStack = await page.evaluate(() => {
      connectionMode = "casual";
      connectionRole = "player";
      isObserver = false;
      myPlayerId = "p1";
      document.querySelector("#joinScreen").classList.add("hidden");
      document.querySelector("#gameScreen").classList.remove("hidden");
      latestState.mode = "casual";
      latestState.tournament = null;
      latestState.ended = false;
      latestState.phaseTracker = {
        enabled: true,
        advanced: true,
        index: ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_reaction"),
        turn: 2,
        passedPlayerIds: [],
      };
      latestState.rulesEngine = {
        enabled: true,
        priorityPlayerId: "p1",
        priorityPasses: [],
        actionStack: [
          { id: "action-1", controllerId: "p1", label: "Play a Will", kind: "play_card", phaseId: "confrontation_reaction", turn: 2 },
          { id: "action-2", controllerId: "p2", label: "Nom français injecté", kind: "play_card", target: "Cible française injectée", cost: { note: "Coût français injecté" }, phaseId: "confrontation_reaction", turn: 2 },
        ],
        lastResolvedAction: { id: "action-0", controllerId: "p1", label: "Previous effect" },
        outcome: null,
      };
      const sourceCard = [...cardsById.values()].find((card) => (
        card.type === "ephemeral_will"
        && /target manifestation/i.test(String(card.effect || ""))
        && !(playedAbilitiesByCard.get(card.id) || []).length
      ));
      const tributeCard = [...cardsById.values()].find((card) => card.type === "manifestation"
        && card.temperaments?.some((temperament) => sourceCard.temperaments?.includes(temperament)));
      const targetCard = [...cardsById.values()].find((card) => card.type === "manifestation" && card.id !== tributeCard.id);
      latestState.rulesEngine.actionStack[0].source = { cardId: sourceCard.id, zone: "hand" };
      latestState.rulesEngine.actionStack[1].source = { cardId: sourceCard.id, zone: "hand" };
      latestState.players.p1.zones.hand = {
        cards: [sourceCard.id, tributeCard.id],
        count: 2,
        owners: { [sourceCard.id]: "p1", [tributeCard.id]: "p1" },
      };
      latestState.tokens = [];
      latestState.battlefield.push({
        id: "rules-target-1", ownerId: "p2", cardId: targetCard.id,
        x: 720, y: 420, faceUp: true, rotation: 0, counters: {}, isSupport: true,
      });
      window.__sent = [];
      renderAll();
      document.querySelector(`[data-hand-card="${sourceCard.id}"]`).dispatchEvent(new MouseEvent("contextmenu", {
        bubbles: true, cancelable: true, clientX: 320, clientY: 720,
      }));
      const contextLabels = [...document.querySelectorAll(".ctx-menu button")].map((button) => button.textContent.trim());
      [...document.querySelectorAll(".ctx-menu button")]
        .find((button) => button.textContent.trim() === t("rulesDeclareCardAction"))?.click();
      const declaration = {
        visible: !document.querySelector("#rulesActionPanel").classList.contains("hidden"),
        declareActionText: t("rulesDeclareCardAction"),
        kind: document.querySelector("#rulesActionKind").value,
        kindLocked: document.querySelector("#rulesActionKind").disabled,
        targetChoices: document.querySelectorAll("#rulesTargetList input").length,
        tributeChoices: document.querySelectorAll("#rulesTributeList input").length,
        tributeSummaryVisible: !document.querySelector("#rulesTributeSummary").classList.contains("hidden"),
        tributeSummaryColumns: document.querySelectorAll("#rulesTributeSummary > span").length,
        tributeSummaryText: document.querySelector("#rulesTributeSummary").textContent,
        contextLabels,
        minFont: Math.min(...[...document.querySelectorAll("#rulesActionPanel .box, #rulesActionPanel .box *")]
          .filter((element) => getComputedStyle(element).display !== "none")
          .map((element) => parseFloat(getComputedStyle(element).fontSize))
          .filter(Number.isFinite)),
        underSized: [...document.querySelectorAll("#rulesActionPanel .box, #rulesActionPanel .box *")]
          .filter((element) => getComputedStyle(element).display !== "none" && parseFloat(getComputedStyle(element).fontSize) < 14)
          .map((element) => `${element.tagName}.${element.className}:${getComputedStyle(element).fontSize}`),
      };
      document.querySelector("#rulesActionDescription").value = "Play the test Will";
      document.querySelector("#rulesActionTarget").value = "During this confrontation";
      document.querySelector("#rulesActionCostNote").value = "One green Tribute";
      const manualTargetInput = document.querySelector('#rulesTargetList input[value="rules-target-1"]');
      if (!manualTargetInput) {
        throw new Error(JSON.stringify({
          sourceCardId: sourceCard?.id,
          encodedAbilities: playedAbilitiesByCard.get(sourceCard?.id) || [],
          battlefield: latestState.battlefield,
          targetMarkup: document.querySelector("#rulesTargetList").innerHTML,
        }));
      }
      manualTargetInput.checked = true;
      document.querySelector("#rulesTributeList input").checked = true;
      document.querySelector("#rulesActionDeclareForm").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      declaration.closedAfterSubmit = document.querySelector("#rulesActionPanel").classList.contains("hidden");
      declaration.payload = window.__sent.find((payload) => payload.kind === "play_card");
      document.querySelector("#passPriorityBtn").click();
      latestState.rulesEngine.priorityPlayerId = "p2";
      latestState.rulesEngine.priorityPasses = ["p1"];
      renderRulesStack();
      const cancelPass = {
        visible: !document.querySelector("#passPriorityBtn").classList.contains("hidden"),
        passedStyle: document.querySelector("#passPriorityBtn").classList.contains("passed"),
        priorityGreen: getComputedStyle(document.querySelector("#rulesPriority")).color,
      };
      document.querySelector("#passPriorityBtn").click();
      cancelPass.payload = window.__sent.at(-1);
      latestState.rulesEngine.priorityPlayerId = "p1";
      latestState.rulesEngine.priorityPasses = [];
      renderRulesStack();
      const active = {
        visible: !document.querySelector("#rulesStackPanel").classList.contains("hidden"),
        stackItems: document.querySelectorAll("#rulesStackList li[data-stack-action-id]").length,
        stackCards: document.querySelectorAll("#rulesStackList .rules-stack-card img").length,
        stackPlayerColors: [...document.querySelectorAll("#rulesStackList li[data-stack-action-id]")].map((item) => item.style.getPropertyValue("--stack-player-color")),
        topText: document.querySelector('#rulesStackList li[data-stack-action-id="action-2"]')?.textContent || "",
        responseSlotVisible: Boolean(document.querySelector("#rulesStackList .rules-stack-response-slot")),
        responseSlotDotted: getComputedStyle(document.querySelector("#rulesStackList .rules-stack-response-slot")).borderStyle === "dashed",
        responseButtonState: document.querySelector("#passPriorityBtn").classList.contains("offers-response"),
        responseButtonText: document.querySelector("#passPriorityBtn").textContent.trim(),
        responseButtonExpected: t("rulesPassWithoutResponse"),
        priorityText: document.querySelector("#rulesPriority").textContent,
        passDisabled: document.querySelector("#passPriorityBtn").disabled,
        minFont: Math.min(...[...document.querySelectorAll("#rulesStackPanel, #rulesStackPanel *")]
          .filter((element) => getComputedStyle(element).display !== "none")
          .map((element) => parseFloat(getComputedStyle(element).fontSize))
          .filter(Number.isFinite)),
        sent: [...window.__sent],
        cancelPass,
        declaration,
        sourceCardId: sourceCard.id,
        tributeCardId: tributeCard.id,
        targetCardId: targetCard.id,
      };
      latestState.rulesEngine.priorityPasses = ["p2"];
      renderRulesStack();
      active.resolution = {
        responseSlotVisible: Boolean(document.querySelector("#rulesStackList .rules-stack-response-slot.before-resolution")),
        highlightedActionId: document.querySelector("#rulesStackList li.will-resolve")?.dataset.stackActionId || null,
        badge: document.querySelector("#rulesStackList .rules-stack-resolve-state")?.textContent.trim() || "",
        buttonState: document.querySelector("#passPriorityBtn").classList.contains("resolves-stack"),
        buttonText: document.querySelector("#passPriorityBtn").textContent.trim(),
        buttonExpected: rulesText("rulesResolveTop", { card: rulesActionDisplayLabel(latestState.rulesEngine.actionStack[1]) }),
      };
      const originalLanguage = currentLanguage;
      currentLanguage = "en";
      renderRulesStack();
      active.localizedEnglish = document.querySelector('#rulesStackList li[data-stack-action-id="action-2"] strong')?.textContent.trim() || "";
      active.expectedEnglish = rulesActionDisplayLabel(latestState.rulesEngine.actionStack[1]);
      currentLanguage = "fr";
      renderRulesStack();
      active.localizedFrench = document.querySelector('#rulesStackList li[data-stack-action-id="action-2"] strong')?.textContent.trim() || "";
      active.expectedFrench = rulesActionDisplayLabel(latestState.rulesEngine.actionStack[1]);
      currentLanguage = originalLanguage;
      latestState.rulesEngine.priorityPasses = [];
      renderRulesStack();
      const previouslyInspectedCardId = inspectHistory[0];
      document.querySelector("#rulesStackList .rules-stack-card").click();
      active.stackCardInspected = !document.querySelector("#inspectPanel").classList.contains("hidden")
        && document.querySelector("#inspectName").textContent === cardName(sourceCard.id);
      if (previouslyInspectedCardId) showInspect(previouslyInspectedCardId);
      const encodedCard = cardsById.get("ufujqhwlpmaw12y_en");
      latestState.battlefield.push({
        id: "encoded-source-1", ownerId: "p1", cardId: encodedCard.id,
        x: 520, y: 420, faceUp: true, rotation: 0, counters: {},
      });
      latestState.tokens = [{
        id: "encoded-essence", ownerId: "p1", x: 0, y: 0,
        isEssence: true, isNeutralCounter: false, temperament: "hollow",
        counters: { essence: 2 },
      }];
      openRulesActionPanel({ cardId: encodedCard.id, zone: "battlefield", itemId: "encoded-source-1" });
      const encodedTarget = document.querySelector('#rulesTargetList input[value="rules-target-1"]');
      active.encoded = {
        visible: !document.querySelector("#rulesActionPanel").classList.contains("hidden"),
        kind: document.querySelector("#rulesActionKind").value,
        kindLocked: document.querySelector("#rulesActionKind").disabled,
        meta: document.querySelector("#rulesActionSourceMeta").textContent,
        expectedMeta: t("rulesEncodedAbility"),
        targetType: encodedTarget?.type,
        tributeSummaryVisible: !document.querySelector("#rulesTributeSummary").classList.contains("hidden"),
        tributeSummaryText: document.querySelector("#rulesTributeSummary").textContent,
        warning: document.querySelector("#rulesActionWarning").textContent,
        cardId: encodedCard.id,
      };
      encodedTarget.checked = true;
      document.querySelector("#rulesActionDescription").value = "Use encoded effect";
      document.querySelector("#rulesActionDeclareForm").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      active.encoded.payload = window.__sent.find((payload) => payload.abilityId === "ignore-support-power");
      const sacrificeCard = cardsById.get("ng6w09m6mrjq3xc_en");
      latestState.rulesEngine.priorityPlayerId = "p1";
      latestState.battlefield.push({
        id: "sacrifice-source-1", ownerId: "p1", cardId: sacrificeCard.id,
        x: 610, y: 520, faceUp: true, rotation: 0, counters: {}, fieldZone: "interzone",
      });
      renderAll();
      openRulesActionPanel({ cardId: sacrificeCard.id, zone: "battlefield", itemId: "sacrifice-source-1" });
      active.sacrifice = {
        meta: document.querySelector("#rulesActionSourceMeta").textContent,
        expectedMeta: t("rulesSacrificeSourceCost"),
        targetChoices: document.querySelectorAll("#rulesTargetList input").length,
        targetText: document.querySelector("#rulesTargetList").textContent.trim(),
        expectedTargetText: t("rulesNoTargetRequired"),
        cardId: sacrificeCard.id,
      };
      document.querySelector("#rulesActionDescription").value = "Sacrifice Pimbo";
      document.querySelector("#rulesActionDeclareForm").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      active.sacrifice.payload = window.__sent.find((payload) => payload.abilityId === "sacrifice-field-power-loss");

      const strengthenCard = cardsById.get("lo85kdsow36bymu_en");
      const hollowTribute = [...cardsById.values()].find((card) => (
        card.type === "manifestation" && card.temperaments?.includes("hollow")
      ));
      latestState.rulesEngine.priorityPlayerId = "p1";
      latestState.players.p1.zones.hand = {
        cards: [strengthenCard.id, hollowTribute.id], count: 2,
        owners: { [strengthenCard.id]: "p1", [hollowTribute.id]: "p1" },
      };
      latestState.tokens = [];
      renderAll();
      openRulesActionPanel({ cardId: strengthenCard.id, zone: "hand" });
      const playedTributeInput = document.querySelector("#rulesTributeList input");
      active.playedAbility = {
        visible: !document.querySelector("#rulesActionPanel").classList.contains("hidden"),
        kind: document.querySelector("#rulesActionKind").value,
        kindLocked: document.querySelector("#rulesActionKind").disabled,
        targetType: document.querySelector('#rulesTargetList input[value="rules-target-1"]')?.type,
        tributeChoices: document.querySelectorAll("#rulesTributeList input").length,
        tributeSummaryText: document.querySelector("#rulesTributeSummary").textContent,
        cardId: strengthenCard.id,
        tributeCardId: playedTributeInput?.value,
      };
      document.querySelector('#rulesTargetList input[value="rules-target-1"]').checked = true;
      playedTributeInput.checked = true;
      document.querySelector("#rulesActionDescription").value = "Strengthen target";
      document.querySelector("#rulesActionDeclareForm").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      active.playedAbility.payload = window.__sent.find((payload) => payload.abilityId === "strengthen-power-modifier");

      const ponderCard = cardsById.get("ryg8e3lgopl6z52_en");
      latestState.players.p1.zones.hand = {
        cards: [ponderCard.id, hollowTribute.id], count: 2,
        owners: { [ponderCard.id]: "p1", [hollowTribute.id]: "p1" },
      };
      renderAll();
      openRulesActionPanel({ cardId: ponderCard.id, zone: "hand" });
      const ponderTribute = document.querySelector("#rulesTributeList input");
      active.drawAbility = {
        noTargetText: document.querySelector("#rulesTargetList").textContent.trim(),
        expectedNoTargetText: t("rulesNoTargetRequired"),
        targetChoices: document.querySelectorAll("#rulesTargetList input").length,
        warning: document.querySelector("#rulesActionWarning").textContent,
        expectedWarning: t("rulesEncodedAutomaticWarning"),
        cardId: ponderCard.id,
        tributeCardId: ponderTribute?.value,
      };
      ponderTribute.checked = true;
      document.querySelector("#rulesActionDescription").value = "Ponder";
      document.querySelector("#rulesActionDeclareForm").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      active.drawAbility.payload = window.__sent.find((payload) => payload.abilityId === "draw-three-cards");

      const prayCard = cardsById.get("zni76s4aabicqag_en");
      latestState.players.p1.zones.hand = {
        cards: [prayCard.id, hollowTribute.id], count: 2,
        owners: { [prayCard.id]: "p1", [hollowTribute.id]: "p1" },
      };
      renderAll();
      openRulesActionPanel({ cardId: prayCard.id, zone: "hand" });
      active.conditionalDrawAbility = {
        noTargetText: document.querySelector("#rulesTargetList").textContent.trim(),
        expectedNoTargetText: t("rulesNoTargetRequired"),
        targetChoices: document.querySelectorAll("#rulesTargetList input").length,
        cardId: prayCard.id,
      };
      document.querySelector("#rulesActionDescription").value = "Pray the Ether";
      document.querySelector("#rulesActionDeclareForm").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      active.conditionalDrawAbility.payload = window.__sent.find((payload) => payload.abilityId === "discard-one-then-draw-two");

      const deferCard = cardsById.get("ek1bng9r7vhriwt_en");
      const persistentTargetCard = [...cardsById.values()].find((card) => card.type === "persistent_will");
      const vitreousTributes = [...cardsById.values()].filter((card) => (
        card.type === "manifestation" && card.temperaments?.includes("vitreous")
      )).slice(0, 2);
      latestState.players.p1.zones.hand = {
        cards: [deferCard.id, ...vitreousTributes.map((card) => card.id)], count: 3,
        owners: Object.fromEntries([deferCard, ...vitreousTributes].map((card) => [card.id, "p1"])),
      };
      latestState.battlefield.push({
        id: "defer-persistent-target", ownerId: "p2", cardId: persistentTargetCard.id,
        x: 820, y: 480, faceUp: true, rotation: 0, counters: {},
      });
      renderAll();
      openRulesActionPanel({ cardId: deferCard.id, zone: "hand" });
      const deferTarget = document.querySelector('#rulesTargetList input[value="defer-persistent-target"]');
      const deferTributes = [...document.querySelectorAll("#rulesTributeList input")].slice(0, 2);
      active.moveAbility = {
        visible: !document.querySelector("#rulesActionPanel").classList.contains("hidden"),
        targetType: deferTarget?.type,
        targetAvailable: Boolean(deferTarget),
        tributeChoices: deferTributes.length,
        warning: document.querySelector("#rulesActionWarning").textContent,
        expectedWarning: t("rulesEncodedAutomaticWarning"),
        cardId: deferCard.id,
        targetCardId: persistentTargetCard.id,
      };
      deferTarget.checked = true;
      deferTributes.forEach((input) => { input.checked = true; });
      document.querySelector("#rulesActionDescription").value = "Defer target";
      document.querySelector("#rulesActionDeclareForm").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      active.moveAbility.payload = window.__sent.find((payload) => payload.abilityId === "defer-to-deck-top");
      const exileCard = cardsById.get("1q6crbc7nwugrgs_en");
      const limboTarget = [...cardsById.values()].find((card) => card.type === "manifestation"
        && card.id !== targetCard.id && card.id !== persistentTargetCard.id);
      const hollowTributes = [...cardsById.values()].filter((card) => (
        card.type === "manifestation" && card.temperaments?.includes("hollow") && card.id !== limboTarget.id
      )).slice(0, 4);
      latestState.players.p1.zones.hand = {
        cards: [exileCard.id, ...hollowTributes.map((card) => card.id)], count: 5,
        owners: Object.fromEntries([exileCard, ...hollowTributes].map((card) => [card.id, "p1"])),
      };
      latestState.players.p2.zones.graveyard = {
        cards: [limboTarget.id], count: 1, owners: { [limboTarget.id]: "p2" },
      };
      latestState.rulesEngine.priorityPlayerId = "p1";
      renderAll();
      openRulesActionPanel({ cardId: exileCard.id, zone: "hand" });
      const limboTargetInput = [...document.querySelectorAll('#rulesTargetList input[data-target-kind="zone_card"]')]
        .find((input) => input.dataset.containerId === "p2" && input.dataset.cardId === limboTarget.id);
      const exileTributes = [...document.querySelectorAll("#rulesTributeList input")].slice(0, 4);
      active.exileAbility = {
        targetAvailable: Boolean(limboTargetInput),
        targetLabel: limboTargetInput?.closest("label")?.textContent || "",
        targetCardId: limboTarget.id,
        cardId: exileCard.id,
      };
      limboTargetInput.checked = true;
      exileTributes.forEach((input) => { input.checked = true; });
      document.querySelector("#rulesActionDescription").value = "Exile from Limbo";
      document.querySelector("#rulesActionDeclareForm").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      active.exileAbility.payload = window.__sent.find((payload) => payload.abilityId === "exile-manifestation");
      const disfigureCard = cardsById.get("jy05w4j8zcuvezq_en");
      const destroyTarget = [...cardsById.values()].find((card) => (
        card.type === "manifestation" && Number(card.points) <= 20
        && card.id !== limboTarget.id && !hollowTributes.some((tribute) => tribute.id === card.id)
      ));
      const tooValuableTarget = [...cardsById.values()].find((card) => (
        card.type === "manifestation" && Number(card.points) > 20
      ));
      const melancholicTributes = [...cardsById.values()].filter((card) => (
        card.type === "manifestation" && card.temperaments?.includes("melancholic")
        && card.id !== destroyTarget.id && card.id !== tooValuableTarget.id
      )).slice(0, 2);
      latestState.players.p1.zones.hand = {
        cards: [disfigureCard.id, ...melancholicTributes.map((card) => card.id)], count: 3,
        owners: Object.fromEntries([disfigureCard, ...melancholicTributes].map((card) => [card.id, "p1"])),
      };
      latestState.players.p2.zones.receptacle = {
        cards: [destroyTarget.id], count: 1, owners: { [destroyTarget.id]: "p1" },
      };
      latestState.battlefield.push({
        id: "too-valuable-target", ownerId: "p2", cardId: tooValuableTarget.id,
        x: 940, y: 480, faceUp: true, rotation: 0, counters: {},
      });
      renderAll();
      openRulesActionPanel({ cardId: disfigureCard.id, zone: "hand" });
      const destroyTargetInput = [...document.querySelectorAll('#rulesTargetList input[data-target-kind="zone_card"]')]
        .find((input) => input.dataset.containerId === "p2" && input.dataset.zone === "receptacle"
          && input.dataset.cardId === destroyTarget.id);
      const destroyTributes = [...document.querySelectorAll("#rulesTributeList input")].slice(0, 2);
      active.destroyAbility = {
        targetAvailable: Boolean(destroyTargetInput),
        tooValuableAvailable: Boolean(document.querySelector('#rulesTargetList input[data-item-id="too-valuable-target"]')),
        targetCardId: destroyTarget.id,
        cardId: disfigureCard.id,
      };
      destroyTargetInput.checked = true;
      destroyTributes.forEach((input) => { input.checked = true; });
      document.querySelector("#rulesActionDescription").value = "Disfigure target";
      document.querySelector("#rulesActionDeclareForm").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      active.destroyAbility.payload = window.__sent.find((payload) => payload.abilityId === "disfigure-destroy-manifestation");
      const randomDestroyCard = cardsById.get("dey791sghwx2ee3_en");
      const randomDestroyTributes = [...cardsById.values()].filter((card) => (
        card.type === "manifestation" && card.temperaments?.includes("hollow")
        && card.id !== destroyTarget.id
      )).slice(0, 3);
      latestState.players.p1.zones.hand = {
        cards: [randomDestroyCard.id, ...randomDestroyTributes.map((card) => card.id)], count: 4,
        owners: Object.fromEntries([randomDestroyCard, ...randomDestroyTributes].map((card) => [card.id, "p1"])),
      };
      renderAll();
      openRulesActionPanel({ cardId: randomDestroyCard.id, zone: "hand" });
      const targetPlayerInput = document.querySelector('#rulesTargetList input[data-target-kind="player"][data-player-id="p2"]');
      const randomTributeInputs = [...document.querySelectorAll("#rulesTributeList input")].slice(0, 3);
      active.randomDestroyAbility = {
        playerChoices: document.querySelectorAll('#rulesTargetList input[data-target-kind="player"]').length,
        targetAvailable: Boolean(targetPlayerInput),
        playerMark: targetPlayerInput?.closest("label")?.querySelector(".rules-target-player-mark")?.textContent || "",
        cardId: randomDestroyCard.id,
      };
      targetPlayerInput.checked = true;
      randomTributeInputs.forEach((input) => { input.checked = true; });
      document.querySelector("#rulesActionDescription").value = "Remove by Chance";
      document.querySelector("#rulesActionDeclareForm").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      active.randomDestroyAbility.payload = window.__sent.find((payload) => payload.abilityId === "destroy-random-vessel-manifestation");
      const eliminateCard = cardsById.get("5x4aca4v6w9ma1f_en");
      const eliminateTributes = [...cardsById.values()].filter((card) => (
        card.type === "manifestation" && card.temperaments?.includes("hollow")
        && card.id !== destroyTarget.id
      )).slice(0, 4);
      latestState.players.p1.zones.hand = {
        cards: [eliminateCard.id, ...eliminateTributes.map((card) => card.id)], count: 5,
        owners: Object.fromEntries([eliminateCard, ...eliminateTributes].map((card) => [card.id, "p1"])),
      };
      renderAll();
      openRulesActionPanel({ cardId: eliminateCard.id, zone: "hand" });
      const eliminateTargetInput = [...document.querySelectorAll('#rulesTargetList input[data-target-kind="zone_card"]')]
        .find((input) => input.dataset.containerId === "p2" && input.dataset.zone === "receptacle"
          && input.dataset.cardId === destroyTarget.id);
      const eliminateTributeInputs = [...document.querySelectorAll("#rulesTributeList input")].slice(0, 4);
      active.eliminateAbility = {
        targetAvailable: Boolean(eliminateTargetInput),
        battlefieldTargets: document.querySelectorAll('#rulesTargetList input[data-target-kind="card"]').length,
        cardId: eliminateCard.id,
        targetCardId: destroyTarget.id,
      };
      eliminateTargetInput.checked = true;
      eliminateTributeInputs.forEach((input) => { input.checked = true; });
      document.querySelector("#rulesActionDescription").value = "Eliminate the Profane";
      document.querySelector("#rulesActionDeclareForm").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      active.eliminateAbility.payload = window.__sent.find((payload) => payload.abilityId === "destroy-vessel-manifestation");
      latestState.rulesEngine.priorityPlayerId = "p2";
      renderRulesStack();
      active.disabledWithoutPriority = document.querySelector("#passPriorityBtn").disabled;
      return active;
    });
    const pregameUi = await page.evaluate(async () => {
      const savedState = structuredClone(latestState);
      const sourceCard = [...cardsById.values()].find((card) => card.type === "ephemeral_will");
      latestState.phaseTracker = { enabled: true, advanced: true, index: 0, turn: 1, passedPlayerIds: [] };
      latestState.rulesEngine = {
        enabled: true,
        deckConfirmedPlayerIds: ["p1", "p2"],
        openingHandPlayerIds: ["p1", "p2"],
        mulliganPlayerIds: [],
        openingMulliganRequiredPlayerIds: ["p1"],
        openingMulliganFailedPlayerIds: [],
        readyPlayerIds: ["p2"],
        priorityPlayerId: null,
        priorityPasses: [],
        actionStack: [],
        pendingChoice: null,
        outcome: null,
      };
      latestState.players.p1.zones.hand = {
        cards: [sourceCard.id], count: 1, owners: { [sourceCard.id]: "p1" },
      };
      latestState.players.p2.zones.hand = { count: 3 };
      revealedHandCards.delete("p2");
      handToolsOpen = false;
      handHiddenByUser = true;
      window.__sent = [];
      renderAll();
      const pregamePanelRect = document.querySelector("#rulesPregamePanel").getBoundingClientRect();
      const initial = {
        panelVisible: !document.querySelector("#rulesPregamePanel").classList.contains("hidden"),
        panelProminent: document.querySelector("#rulesPregamePanel").classList.contains("mulligan-required"),
        openingHidden: document.querySelector("#rulesOpeningHandBtn").classList.contains("hidden"),
        mulliganEnabled: !document.querySelector("#rulesPregameMulliganBtn").disabled,
        mulliganVisible: !document.querySelector("#rulesPregameMulliganBtn").classList.contains("hidden"),
        readyHidden: document.querySelector("#rulesPregameReadyBtn").classList.contains("hidden"),
        title: document.querySelector("#rulesPregameTitle").textContent.trim(),
        hint: document.querySelector("#rulesPregameHint").textContent.trim(),
        attentionCount: document.querySelectorAll(".rules-pregame-player.attention").length,
        panelFitsViewport: pregamePanelRect.left >= 0 && pregamePanelRect.right <= window.innerWidth,
        titleFontSize: parseFloat(getComputedStyle(document.querySelector("#rulesPregameTitle")).fontSize),
        hintFontSize: parseFloat(getComputedStyle(document.querySelector("#rulesPregameHint")).fontSize),
        mulliganFontSize: parseFloat(getComputedStyle(document.querySelector("#rulesPregameMulliganBtn")).fontSize),
        phaseHidden: document.querySelector("#phaseTracker").classList.contains("hidden"),
        stackHidden: getComputedStyle(document.querySelector("#rulesStackPanel")).display === "none",
        opponentSlots: document.querySelectorAll("#opponentHandFan [data-opponent-hand-slot]").length,
        leakedOpponentIds: document.querySelectorAll("#opponentHandFan [data-opponent-hand-card]").length,
        toolsHidden: document.querySelector("#handToolbar").classList.contains("hidden"),
        handVisible: !document.querySelector("#myHandTray").classList.contains("hidden"),
        handCards: document.querySelectorAll("#myHandTray [data-hand-card]").length,
      };
      latestState.rulesEngine.openingMulliganRequiredPlayerIds = [];
      latestState.rulesEngine.readyPlayerIds = ["p2"];
      renderAll();
      const voluntaryMulligan = {
        keepVisible: !document.querySelector("#rulesPregameReadyBtn").classList.contains("hidden"),
        keepText: document.querySelector("#rulesPregameReadyBtn").textContent.trim(),
        mulliganVisible: !document.querySelector("#rulesPregameMulliganBtn").classList.contains("hidden"),
        mulliganText: document.querySelector("#rulesPregameMulliganBtn").textContent.trim(),
        twoActions: document.querySelectorAll("#rulesPregameActions button:not(.hidden)").length,
      };
      window.__sent = [];
      document.querySelector("#rulesPregameMulliganBtn").click();
      voluntaryMulligan.confirmText = document.querySelector("#confirmPanelText").textContent.trim();
      document.querySelector("#confirmPanelOkBtn").click();
      voluntaryMulligan.payload = window.__sent.at(-1);
      document.querySelector("#handToolsToggleBtn").click();
      initial.toolsOpen = !document.querySelector("#handToolbar").classList.contains("hidden");
      latestState.rulesEngine.openingMulliganRequiredPlayerIds = ["p2"];
      latestState.rulesEngine.readyPlayerIds = ["p1"];
      renderAll();
      initial.waitingButton = {
        visible: !document.querySelector("#rulesPregameMulliganBtn").classList.contains("hidden"),
        disabled: document.querySelector("#rulesPregameMulliganBtn").disabled,
        text: document.querySelector("#rulesPregameMulliganBtn").textContent.trim(),
      };
      latestState.rulesEngine.openingMulliganRequiredPlayerIds = ["p1"];
      latestState.rulesEngine.readyPlayerIds = ["p2"];
      renderAll();
      document.querySelector("#rulesPregameMulliganBtn").click();
      document.querySelector("#confirmPanelOkBtn").click();
      initial.mulliganPayload = window.__sent.at(-1);

      latestState.rulesEngine.mulliganPlayerIds = ["p1"];
      latestState.rulesEngine.openingMulliganRequiredPlayerIds = [];
      latestState.rulesEngine.readyPlayerIds = ["p2"];
      handHiddenByUser = false;
      renderAll();
      initial.afterMulligan = {
        panelVisible: !document.querySelector("#rulesPregamePanel").classList.contains("hidden"),
        mulliganHidden: document.querySelector("#rulesPregameMulliganBtn").classList.contains("hidden"),
        keepVisible: !document.querySelector("#rulesPregameReadyBtn").classList.contains("hidden"),
        keepText: document.querySelector("#rulesPregameReadyBtn").textContent.trim(),
      };
      window.__sent = [];
      document.querySelector("#rulesPregameReadyBtn").click();
      initial.afterMulligan.keepPayload = window.__sent.at(-1);
      latestState.rulesEngine.readyPlayerIds = ["p1", "p2"];
      latestState.phaseTracker.index = ADVANCED_PHASES.findIndex((phase) => phase.id === "recovery_end");
      renderAll();
      initial.panelClosedAfterValidMulligan = document.querySelector("#rulesPregamePanel").classList.contains("hidden");

      latestState.phaseTracker = {
        enabled: true, advanced: true,
        index: ADVANCED_PHASES.findIndex((phase) => phase.id === "recovery_draw"),
        turn: 2, passedPlayerIds: [],
      };
      latestState.rulesEngine.recoveryMulliganTurn = 2;
      latestState.rulesEngine.recoveryMulliganPlayerIds = [];
      latestState.rulesEngine.recoveryMulliganRequiredPlayerIds = ["p1"];
      latestState.rulesEngine.recoveryMulliganFailedPlayerIds = [];
      window.__sent = [];
      renderAll();
      const recoveryMulligan = {
        panelVisible: !document.querySelector("#rulesPregamePanel").classList.contains("hidden"),
        panelProminent: document.querySelector("#rulesPregamePanel").classList.contains("mulligan-required"),
        title: document.querySelector("#rulesPregameTitle").textContent.trim(),
        hint: document.querySelector("#rulesPregameHint").textContent.trim(),
        action: document.querySelector("#rulesPregameMulliganBtn").textContent.trim(),
        readyHidden: document.querySelector("#rulesPregameReadyBtn").classList.contains("hidden"),
        playableCardCount: document.querySelectorAll("#myHandTray .is-playable").length,
      };
      document.querySelector("#rulesPregameMulliganBtn").click();
      recoveryMulligan.confirmText = document.querySelector("#confirmPanelText").textContent.trim();
      document.querySelector("#confirmPanelOkBtn").click();
      recoveryMulligan.payload = window.__sent.at(-1);

      latestState.rulesEngine = {
        enabled: true,
        deckConfirmedPlayerIds: ["p2"],
        openingHandPlayerIds: [],
        mulliganPlayerIds: [],
        openingMulliganRequiredPlayerIds: [],
        openingMulliganFailedPlayerIds: [],
        readyPlayerIds: [],
        priorityPlayerId: null,
        priorityPasses: [],
        actionStack: [],
        firstManifestationComplete: false,
        firstManifestationItemIds: {},
        firstManifestationValidatedPlayerIds: [],
        pendingChoice: null,
        outcome: null,
      };
      latestState.phaseTracker = { enabled: true, advanced: true, index: 0, turn: 1, passedPlayerIds: [] };
      latestState.players.p1.zones.hand = { cards: [], count: 0, owners: {} };
      renderAll();
      const requestedUx = {
        openingActions: [...document.querySelectorAll("#rulesPregameActions button:not(.hidden)")].map((button) => ({
          id: button.id, text: button.textContent.trim(), glow: button.classList.contains("opponent-validated"),
        })),
        emptyHandButtons: document.querySelectorAll("#myHandTray button").length,
        phaseMain: document.querySelector("#phaseCurrentMain").textContent.trim(),
        phaseStep: document.querySelector("#phaseCurrentStep").textContent.trim(),
      };

      document.querySelector("#importDeckBtn").click();
      document.querySelector("#starterDeckList [data-import-starter]").click();
      requestedUx.stagedDeckVisible = document.querySelector("#currentDeckSummary .is-staged") !== null;
      requestedUx.stagedDeckText = document.querySelector("#currentDeckSummary").textContent.replace(/\s+/g, " ").trim();
      window.__sent = [];
      document.querySelector("#importPasteBtn").click();
      await new Promise((resolve) => setTimeout(resolve, 0));
      requestedUx.importPayload = window.__sent.find((payload) => payload.type === "import_deck");
      requestedUx.importPanelStayedOpen = !document.querySelector("#importPanel").classList.contains("hidden");
      window.__sent = [];
      document.querySelector("#importConfirmBtn").click();
      requestedUx.confirmArmed = document.querySelector("#importConfirmBtn").classList.contains("confirm-armed");
      requestedUx.confirmText = document.querySelector("#importConfirmBtn").textContent.trim();
      requestedUx.sentBeforeConfirmation = window.__sent.some((payload) => payload.confirmDeck === true);
      document.querySelector("#importDeckHeading").dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
      requestedUx.confirmDisarmedOutside = !document.querySelector("#importConfirmBtn").classList.contains("confirm-armed");
      document.querySelector("#importConfirmBtn").click();
      document.querySelector("#importConfirmBtn").click();
      requestedUx.confirmPayload = window.__sent.find((payload) => payload.confirmDeck === true);
      requestedUx.importPanelClosedAfterConfirm = document.querySelector("#importPanel").classList.contains("hidden");

      latestState.phaseTracker.index = ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_choose");
      latestState.rulesEngine.firstManifestationItemIds = { p1: "first-p1" };
      latestState.rulesEngine.firstManifestationValidatedPlayerIds = [];
      window.__sent = [];
      renderAll();
      document.querySelector("#passPriorityBtn").click();
      requestedUx.firstValidatePayload = window.__sent.at(-1);
      latestState.rulesEngine.firstManifestationValidatedPlayerIds = ["p1"];
      renderAll();
      document.querySelector("#passPriorityBtn").click();
      requestedUx.firstCancelPayload = window.__sent.at(-1);
      latestState.rulesEngine.firstManifestationValidatedPlayerIds = ["p2"];
      renderAll();
      requestedUx.firstOpponentGlow = document.querySelector("#passPriorityBtn").classList.contains("opponent-validated");

      latestState.players.p1.zones.hand = {
        cards: [sourceCard.id], count: 1, owners: { [sourceCard.id]: "p1" },
      };
      renderAll();
      requestedUx.pointerEvents = {
        area: getComputedStyle(document.querySelector(".hand-area")).pointerEvents,
        tray: getComputedStyle(document.querySelector("#myHandTray")).pointerEvents,
        card: getComputedStyle(document.querySelector("[data-hand-card]")).pointerEvents,
        handle: getComputedStyle(document.querySelector("#handResizeHandle")).pointerEvents,
      };
      const sizeBefore = handCardHeight;
      document.querySelector("#handResizeHandle").dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, clientY: 700 }));
      window.dispatchEvent(new PointerEvent("pointermove", { bubbles: true, clientY: 660 }));
      window.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, clientY: 660 }));
      requestedUx.handResizeDelta = handCardHeight - sizeBefore;

      latestState = savedState;
      latestState.rulesEngine.priorityPlayerId = "p1";
      latestState.rulesEngine.pendingChoice = null;
      const importPanel = document.querySelector("#importPanel");
      importPanel.classList.remove("hidden");
      document.querySelector("#currentDeckSummary").innerHTML = "<p>stale</p>";
      renderAll();
      const deckEditSummary = {
        heading: document.querySelector("#importDeckHeading").textContent.trim(),
        text: document.querySelector("#currentDeckSummary").textContent.replace(/\s+/g, " ").trim(),
        panelVisible: !importPanel.classList.contains("hidden"),
      };
      importPanel.classList.add("hidden");
      latestState.players.p1.zones.hand = {
        cards: [sourceCard.id], count: 1, owners: { [sourceCard.id]: "p1" },
      };
      renderAll();
      let handCard = document.querySelector(`[data-hand-card="${sourceCard.id}"]`);
      const unaffordableAura = handCard.classList.contains("is-playable");
      latestState.tokens = [{ id: "test-essence", ownerId: "p1", isEssence: true, isNeutralCounter: false, temperament: "transcendent", counters: { essence: 20 } }];
      renderAll();
      handCard = document.querySelector(`[data-hand-card="${sourceCard.id}"]`);
      const playableAura = handCard.classList.contains("is-playable");
      const essenceStrip = document.querySelector("#handEssenceStrip");
      const essenceStripShown = !essenceStrip.classList.contains("hidden");
      const essenceStripText = essenceStrip.textContent.trim();
      const essenceStripBesideToggle = essenceStrip.previousElementSibling?.id === "handVisibilityBtn";
      latestState.tokens = [];
      renderAll();
      const essenceStripHiddenWhenEmpty = document.querySelector("#handEssenceStrip").classList.contains("hidden");
      latestState.tokens = [{ id: "test-essence", ownerId: "p1", isEssence: true, isNeutralCounter: false, temperament: "transcendent", counters: { essence: 20 } }];
      renderAll();
      handCard = document.querySelector(`[data-hand-card="${sourceCard.id}"]`);
      handCard.dispatchEvent(new MouseEvent("mouseenter"));
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      const hoverRect = document.querySelector(".hand-card-hover-clone")?.getBoundingClientRect();
      const hoverFullyVisible = Boolean(hoverRect
        && hoverRect.left >= 11
        && hoverRect.top >= 11
        && hoverRect.right <= window.innerWidth - 11
        && hoverRect.bottom <= window.innerHeight - 11);
      handCard.dispatchEvent(new MouseEvent("mouseleave"));
      const supportKeywordCard = [...cardsById.values()].find((card) => (
        card.type === "manifestation" && String(card.effect || "").startsWith("Support.")
      ));
      latestState.phaseTracker = {
        enabled: true, advanced: true,
        index: ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_reaction"),
        turn: 2, passedPlayerIds: [],
      };
      latestState.rulesEngine.enabled = true;
      latestState.rulesEngine.deckConfirmedPlayerIds = ["p1", "p2"];
      latestState.rulesEngine.openingHandPlayerIds = ["p1", "p2"];
      latestState.rulesEngine.readyPlayerIds = ["p1", "p2"];
      latestState.rulesEngine.openingMulliganRequiredPlayerIds = [];
      latestState.rulesEngine.firstManifestationComplete = true;
      latestState.rulesEngine.priorityPlayerId = "p1";
      latestState.rulesEngine.pendingChoice = null;
      latestState.rulesEngine.actionStack = [];
      latestState.players.p1.zones.hand = {
        cards: [supportKeywordCard.id], count: 1, owners: { [supportKeywordCard.id]: "p1" },
      };
      renderAll();
      const supportKeywordPlayableFromHand = document
        .querySelector(`[data-hand-card="${supportKeywordCard.id}"]`)
        .classList.contains("is-playable");
      return {
        initial, voluntaryMulligan, recoveryMulligan, requestedUx, deckEditSummary, unaffordableAura, playableAura, essenceStripShown, essenceStripText, essenceStripBesideToggle, essenceStripHiddenWhenEmpty,
        hoverFullyVisible, supportKeywordPlayableFromHand,
      };
    });
    const newChoiceScreens = await page.evaluate(() => {
      const ids = [...cardsById.keys()];
      const saved = {
        battlefield: latestState.battlefield, priority: latestState.rulesEngine.priorityPlayerId,
        choice: latestState.rulesEngine.pendingChoice,
      };
      latestState.rulesEngine.priorityPlayerId = "p1";
      latestState.battlefield = ids.slice(0, 2).map((cardId, index) => ({
        id: `dist-${index}`, ownerId: "p2", controllerId: "p2", cardId,
        faceUp: true, fieldZone: "interzone", x: 100 + index * 40, y: 100, rotation: 0, counters: {},
      }));
      const show = (choice, selector, who = "p1") => {
        window.__sent = [];
        latestState.rulesEngine.pendingChoice = choice;
        renderAll();
        return {
          visible: !document.querySelector("#rulesChoicePanel").classList.contains("hidden"),
          buttons: document.querySelectorAll(selector).length,
          click: () => { document.querySelector(selector)?.click(); return window.__sent.find((payload) => payload.type === "resolve_rules_choice"); },
        };
      };
      const distribute = show({
        id: "dist-choice", kind: "pick_distribution_extra", playerId: "p1",
        candidateItemIds: ["dist-0", "dist-1"], sourceCardId: ids[0], total: 3, sign: -1,
      }, "[data-rules-distribute-item]");
      const distributePayload = distribute.click();
      const reveal = show({
        id: "reveal-choice", kind: "reveal_hand_discard", playerId: "p1", targetPlayerId: "p2",
        cardIds: ids.slice(2, 5), sourceCardId: ids[0],
      }, "[data-rules-reveal-index]");
      const revealPayload = reveal.click();
      const opponentSees = show({
        id: "reveal-choice-2", kind: "reveal_hand_discard", playerId: "p2", targetPlayerId: "p1",
        cardIds: ids.slice(2, 5), sourceCardId: ids[0],
      }, "[data-rules-reveal-index]");
      latestState.battlefield = saved.battlefield;
      latestState.rulesEngine.priorityPlayerId = saved.priority;
      latestState.rulesEngine.pendingChoice = saved.choice;
      renderAll();
      return {
        distribute: { visible: distribute.visible, buttons: distribute.buttons, payload: distributePayload },
        reveal: { visible: reveal.visible, buttons: reveal.buttons, payload: revealPayload },
        notMine: { visible: opponentSees.visible },
      };
    });
    assert.equal(newChoiceScreens.distribute.visible, true);
    assert.equal(newChoiceScreens.distribute.buttons, 2);
    assert.equal(newChoiceScreens.distribute.payload.itemId, "dist-0");
    assert.equal(newChoiceScreens.reveal.visible, true);
    assert.equal(newChoiceScreens.reveal.buttons, 3);
    assert.equal(newChoiceScreens.reveal.payload.option, "0");
    assert.equal(newChoiceScreens.notMine.visible, false);
    const extraReorder = await page.evaluate(() => {
      const ids = [...cardsById.keys()];
      const saved = { priority: latestState.rulesEngine.priorityPlayerId, choice: latestState.rulesEngine.pendingChoice };
      latestState.rulesEngine.priorityPlayerId = "p1";
      window.__sent = [];
      latestState.rulesEngine.pendingChoice = {
        id: "extra-reorder", kind: "deck_reorder", playerId: "p1", sourceCardId: ids[0],
        groups: [{ playerId: "p2", cardIds: ids.slice(0, 3), topCount: null, bottomCount: null, extraSide: "exile", extraMin: 0, extraMax: 1 }],
      };
      renderAll();
      const options = [...document.querySelectorAll("[data-rules-deck-side] option")].map((option) => option.value);
      document.querySelector('[data-rules-deck-side="p2:1"]').value = "extra";
      document.querySelector("#rulesDeckReorderConfirm").click();
      const payload = window.__sent.find((entry) => entry.type === "resolve_rules_choice");
      latestState.rulesEngine.priorityPlayerId = saved.priority;
      latestState.rulesEngine.pendingChoice = saved.choice;
      renderAll();
      return { options: [...new Set(options)], extra: payload?.option?.groups?.[0]?.extra, top: payload?.option?.groups?.[0]?.top?.length };
    });
    assert.deepEqual(extraReorder.options, ["top", "bottom", "extra"]);
    assert.equal(extraReorder.extra.length, 1);
    assert.equal(extraReorder.top, 2);
    const clemencyUi = await page.evaluate(() => {
      const ids = [...cardsById.keys()];
      const saved = { priority: latestState.rulesEngine.priorityPlayerId, choice: latestState.rulesEngine.pendingChoice };
      const panelVisible = () => !document.querySelector("#rulesChoicePanel").classList.contains("hidden");
      const choice = (playerId) => ({
        id: "clemency", kind: "clemency_choice", playerId, sourceCardId: ids[0], relatedCardId: ids[1],
        points: 5, options: ["allow", "neutralize"],
      });
      latestState.rulesEngine.priorityPlayerId = "p1";
      latestState.rulesEngine.pendingChoice = choice("p2");
      renderAll();
      const notMine = panelVisible();
      latestState.rulesEngine.pendingChoice = choice("p1");
      window.__sent = [];
      renderAll();
      const visible = panelVisible();
      const buttons = [...document.querySelectorAll("[data-rules-clemency-option]")].map((button) => button.dataset.rulesClemencyOption);
      document.querySelector('[data-rules-clemency-option="neutralize"]').click();
      const payload = window.__sent.find((entry) => entry.type === "resolve_rules_choice");
      const ownGorteHidden = rulesActivatedActionDraft(
        { id: "own-gorte", cardId: ids[0], controllerId: "p1", ownerId: "p1", faceUp: true },
        { id: "x", anyPlayer: true, opponentOnly: true },
      ) === null;
      latestState.rulesEngine.priorityPlayerId = saved.priority;
      latestState.rulesEngine.pendingChoice = saved.choice;
      renderAll();
      return { notMine, visible, buttons, option: payload?.option, choiceId: payload?.choiceId, ownGorteHidden };
    });
    assert.equal(clemencyUi.notMine, false);
    assert.equal(clemencyUi.visible, true);
    assert.deepEqual(clemencyUi.buttons, ["allow", "neutralize"]);
    assert.equal(clemencyUi.option, "neutralize");
    assert.equal(clemencyUi.choiceId, "clemency");
    assert.equal(clemencyUi.ownGorteHidden, true);
    const fieldTributeUi = await page.evaluate(() => {
      const orator = "birhlimm9e8lq3d_en", pile = "g3zumpyf623hto6_en";
      const will = [...cardsById.values()].find((card) => card.type === "ephemeral_will" && /^\{[A-Z]\}$/.test(String(card.powerCost || "")));
      const other = [...cardsById.values()].find((card) => card.type === "manifestation" && card.id !== orator);
      const saved = { battlefield: latestState.battlefield, limbo: latestState.players.p1.zones.graveyard };
      const mk = (id, cardId, zone) => ({ id, ownerId: "p1", controllerId: "p1", cardId, faceUp: true, fieldZone: zone, x: 50, y: 50, rotation: 0, counters: {} });
      const count = () => rulesActionPaymentDraft({ cardId: will.id, zone: "hand", handIndex: 0 }, will, null).manifestations.filter((entry) => entry.zone !== "hand").length;
      latestState.battlefield = [mk("o-conf", other.id, "confrontation")];
      const without = count();
      latestState.battlefield = [mk("o-conf", other.id, "confrontation"), mk("o-orator", orator, "interzone")];
      const withOrator = count();
      latestState.battlefield = [];
      latestState.players.p1.zones.graveyard = { cards: [pile], count: 1, owners: { [pile]: "p1" } };
      const withPile = count();
      latestState.battlefield = saved.battlefield;
      latestState.players.p1.zones.graveyard = saved.limbo;
      return { without, withOrator, withPile };
    });
    assert.equal(fieldTributeUi.without, 0);
    assert(fieldTributeUi.withOrator >= 2);
    assert.equal(fieldTributeUi.withPile, 1);
    const vesselAndWillCostUi = await page.evaluate(() => {
      const braba = "zhzp6kenpqrym9h_en", timid = "5zgq2zcogt4g4d0_en";
      const will = [...cardsById.values()].find((card) => card.type === "ephemeral_will" && /^\{[A-Z]\}$/.test(String(card.powerCost || "")));
      const second = [...cardsById.values()].find((card) => card.type === "ephemeral_will" && card.id !== will.id);
      const manifestation = [...cardsById.values()].find((card) => card.type === "manifestation" && card.id !== braba && card.id !== timid);
      const saved = {
        battlefield: latestState.battlefield, vessel: latestState.players.p1.zones.receptacle,
        hand: latestState.players.p1.zones.hand, priority: latestState.rulesEngine.priorityPlayerId,
      };
      const mk = (id, cardId, zone) => ({ id, ownerId: "p1", controllerId: "p1", cardId, faceUp: true, fieldZone: zone, x: 50, y: 50, rotation: 0, counters: {} });
      const count = () => rulesActionPaymentDraft({ cardId: will.id, zone: "hand", handIndex: 0 }, will, null).manifestations.filter((entry) => entry.zone === "receptacle").length;
      latestState.players.p1.zones.receptacle = { cards: [manifestation.id], count: 1, owners: { [manifestation.id]: "p2" } };
      latestState.battlefield = [];
      const without = count();
      latestState.battlefield = [mk("braba", braba, "interzone")];
      const withBraba = count();
      latestState.rulesEngine.priorityPlayerId = "p1";
      latestState.players.p1.zones.hand = {
        cards: [timid, will.id, manifestation.id, second.id], count: 4,
        owners: { [timid]: "p1", [will.id]: "p1", [manifestation.id]: "p1", [second.id]: "p1" },
      };
      latestState.battlefield = [];
      renderAll();
      beginRulesHandActivatedAction(timid, 0);
      const stage = pendingRulesBoardFlow?.stage;
      const costChoices = [...document.querySelectorAll("[data-rules-cost-card]")].map((button) => button.dataset.rulesCostCard);
      closeRulesActionPanel();
      pendingRulesBoardFlow = null;
      latestState.battlefield = saved.battlefield;
      latestState.players.p1.zones.receptacle = saved.vessel;
      latestState.players.p1.zones.hand = saved.hand;
      latestState.rulesEngine.priorityPlayerId = saved.priority;
      renderAll();
      return { without, withBraba, stage, costChoices, willIds: [will.id, second.id] };
    });
    assert.equal(vesselAndWillCostUi.without, 0);
    assert.equal(vesselAndWillCostUi.withBraba, 1);
    assert.equal(vesselAndWillCostUi.stage, "cost_card");
    assert.deepEqual(vesselAndWillCostUi.costChoices.sort(), vesselAndWillCostUi.willIds.sort());
    const rulesChoice = await page.evaluate(() => {
      const darkApparitionId = "7e2ppf4rfgkdfms_en";
      const discardCardId = [...cardsById.keys()].find((cardId) => cardId !== darkApparitionId);
      latestState.rulesEngine.pendingChoice = null;
      latestState.players.p1.zones.hand = {
        cards: [darkApparitionId, discardCardId], count: 2,
        owners: { [darkApparitionId]: "p1", [discardCardId]: "p1" },
      };
      window.__sent = [];
      playFromHand(darkApparitionId, true);
      const targetStep = {
        visible: !document.querySelector("#rulesChoicePanel").classList.contains("hidden"),
        playerChoices: document.querySelectorAll("[data-rules-player-target]").length,
        placementSentBeforeChoice: window.__sent.some((payload) => payload.type === "place_card"),
        minFont: Math.min(...[...document.querySelectorAll("#rulesChoicePanel .box, #rulesChoicePanel .box *")]
          .filter((element) => getComputedStyle(element).display !== "none")
          .map((element) => parseFloat(getComputedStyle(element).fontSize))
          .filter(Number.isFinite)),
      };
      document.querySelector('[data-rules-player-target="p2"]').click();
      targetStep.payload = window.__sent.find((payload) => payload.asSupport === true);

      window.__sent = [];
      latestState.rulesEngine.pendingChoice = {
        id: "choice-1", kind: "discard_from_hand", playerId: "p1", count: 1,
        sourceCardId: darkApparitionId,
      };
      renderAll();
      const discardStep = {
        visible: !document.querySelector("#rulesChoicePanel").classList.contains("hidden"),
        closeHidden: document.querySelector("#rulesChoiceCloseBtn").classList.contains("hidden"),
        cardChoices: document.querySelectorAll("[data-rules-discard-index]").length,
        priorityText: document.querySelector("#rulesPriority").textContent,
        passHidden: document.querySelector("#passPriorityBtn").classList.contains("hidden"),
      };
      document.querySelector('[data-rules-discard-index="1"]').click();
      discardStep.payload = window.__sent.find((payload) => payload.type === "resolve_rules_choice");
      window.__sent = [];
      latestState.rulesEngine.pendingChoice = {
        id: "choice-2", kind: "discard_from_hand", playerId: "p1", count: 1,
        drawAfter: 2, sourceCardId: "zni76s4aabicqag_en",
      };
      renderAll();
      const conditionalStep = {
        text: document.querySelector("#rulesChoiceText").textContent,
        expectedDraw: "2",
      };
      document.querySelector('[data-rules-discard-index="0"]').click();
      conditionalStep.payload = window.__sent.find((payload) => payload.type === "resolve_rules_choice");

      window.__sent = [];
      latestState.rulesEngine.pendingChoice = {
        id: "choice-multi", kind: "discard_from_hand", playerId: "p1", count: 2, upTo: true,
        sourceCardId: "a058t24med4h5nx_en",
      };
      renderAll();
      const multiDiscardStep = {
        confirmEnabledBeforePick: !document.querySelector("#rulesDiscardConfirm").disabled,
      };
      document.querySelector('[data-rules-discard-index="0"]').click();
      document.querySelector('[data-rules-discard-index="1"]').click();
      multiDiscardStep.selectedCount = document.querySelectorAll("[data-rules-discard-index].selected").length;
      document.querySelector("#rulesDiscardConfirm").click();
      multiDiscardStep.payload = window.__sent.find((payload) => payload.type === "resolve_rules_choice");

      window.__sent = [];
      latestState.rulesEngine.pendingChoice = {
        id: "choice-recovery", kind: "recovery_shared_choice", playerId: "p1",
        sourceCardId: "dc44xrlrhikfvlr_en",
        options: ["discard_deck_bottom_3", "lose_points_10"],
      };
      renderAll();
      const recoveryStep = {
        visible: !document.querySelector("#rulesChoicePanel").classList.contains("hidden"),
        choices: document.querySelectorAll("[data-rules-recovery-option]").length,
        text: document.querySelector("#rulesChoiceText").textContent,
        minFont: Math.min(...[...document.querySelectorAll("#rulesChoicePanel .box, #rulesChoicePanel .box *")]
          .filter((element) => getComputedStyle(element).display !== "none")
          .map((element) => parseFloat(getComputedStyle(element).fontSize))
          .filter(Number.isFinite)),
      };
      document.querySelector('[data-rules-recovery-option="discard_deck_bottom_3"]').click();
      recoveryStep.payload = window.__sent.find((payload) => payload.type === "resolve_rules_choice");

      latestState.phaseTracker.index = ADVANCED_PHASES.findIndex((phase) => phase.id === "resolution_compare");
      latestState.rulesEngine.confrontationResult = {
        turn: 2, status: "effects", winnerId: "p1", loserId: "p2", stalemate: false,
        totals: { p1: 7, p2: 4 }, lastTemperaments: { p1: "choleric", p2: "phlegmatic" },
      };
      latestState.rulesEngine.pendingChoice = null;
      renderAll();
      const comparison = {
        visible: !document.querySelector("#rulesConfrontationSummary").classList.contains("hidden"),
        text: document.querySelector("#rulesConfrontationSummary").textContent,
      };

      window.__sent = [];
      latestState.rulesEngine.pendingChoice = {
        id: "choice-destination", kind: "confrontation_destination", playerId: "p1",
        itemId: "winner-card", cardId: darkApparitionId, options: ["interzone", "deck_bottom"],
      };
      renderAll();
      const destinationStep = {
        visible: !document.querySelector("#rulesChoicePanel").classList.contains("hidden"),
        choices: document.querySelectorAll("[data-rules-destination]").length,
        cardVisible: Boolean(document.querySelector(".rules-choice-destination-card img")),
        minFont: Math.min(...[...document.querySelectorAll("#rulesChoicePanel .box, #rulesChoicePanel .box *")]
          .filter((element) => getComputedStyle(element).display !== "none")
          .map((element) => parseFloat(getComputedStyle(element).fontSize))
          .filter(Number.isFinite)),
      };
      const destinationCard = document.querySelector(".rules-choice-destination-card");
      const destinationButton = document.querySelector('[data-rules-destination="interzone"]');
      const dataTransfer = new DataTransfer();
      destinationCard.dispatchEvent(new DragEvent("dragstart", { bubbles: true, dataTransfer }));
      destinationButton.dispatchEvent(new DragEvent("dragover", { bubbles: true, cancelable: true, dataTransfer }));
      destinationStep.dropHighlighted = destinationButton.classList.contains("is-drop-target");
      destinationButton.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer }));
      destinationStep.payload = window.__sent.find((payload) => payload.type === "resolve_rules_choice");

      const replacementCard = latestState.battlefield.find((item) => item.faceUp && item.cardId);
      replacementCard.fieldZone = "interzone";
      window.__sent = [];
      latestState.rulesEngine.pendingChoice = {
        id: "choice-replace", kind: "confrontation_replace_interzone", playerId: "p1",
        itemId: "winner-card", cardId: darkApparitionId, candidateItemIds: [replacementCard.id],
      };
      renderAll();
      const fieldZoneMarker = Boolean(document.querySelector(`[data-item-id="${replacementCard.id}"] .bf-field-zone-marker`));
      document.querySelector(`[data-rules-replace-item="${replacementCard.id}"]`).click();
      const replacementStep = {
        fieldZoneMarker,
        expectedItemId: replacementCard.id,
        payload: window.__sent.find((payload) => payload.type === "resolve_rules_choice"),
      };
      latestState.rulesEngine.pendingChoice = null;
      latestState.rulesEngine.confrontationResult = null;
      closeRulesChoicePanel(true);
      return { darkApparitionId, discardCardId, targetStep, discardStep, conditionalStep, multiDiscardStep, recoveryStep, comparison, destinationStep, replacementStep };
    });
    const rulesVfx = await page.evaluate(async ({ tributeCardId, encodedCardId, sacrificeCardId, gracefulCardId, moveTargetCardId, exileTargetCardId, destroyTargetCardId }) => {
      renderAll();
      const pluffEncoded = (triggeredAbilitiesByCard.get("ghb6i1uoiqq12o2_en") || [])
        .some((ability) => ability.id === "discard-top-card-on-enter-field");
      const initialState = structuredClone(latestState);
      initialState.recentLog = [{ sequence: 500, type: "rules_priority_passed", actorId: "p2", details: {} }];
      lastRulesVfxSequence = null;
      const initialReplayCount = prepareRulesVfxBatch(initialState).length;

      const declaredState = structuredClone(latestState);
      declaredState.type = "state";
      declaredState.recentLog = [{
        sequence: 501,
        type: "rules_action_declared",
        actorId: "p1",
        details: {
          source: { cardId: encodedCardId, zone: "battlefield", itemId: "encoded-source-1" },
          cost: {
            tributeCardIds: [tributeCardId],
            essenceSpent: [{ tokenId: "encoded-essence", temperament: "hollow", amount: 2 }],
            sourceExhausted: true,
          },
        },
      }];
      const encodedSource = declaredState.battlefield.find((item) => item.id === "encoded-source-1");
      encodedSource.rotation = 90;
      handleServerMessage(declaredState);
      await new Promise((resolve) => setTimeout(resolve, 90));
      const declared = {
        essence: document.querySelectorAll(".rules-vfx-essence").length,
        tribute: document.querySelectorAll(".rules-vfx-tribute").length,
        exhaust: document.querySelectorAll(".rules-vfx-exhaust-ring").length,
        impact: document.querySelector(".rules-vfx-impact")?.textContent || "",
        exhaustLabel: document.querySelector(".rules-vfx-exhaust-label")?.textContent || "",
        minFont: Math.min(...[...document.querySelectorAll(".rules-vfx-impact, .rules-vfx-exhaust-label")]
          .map((element) => parseFloat(getComputedStyle(element).fontSize))
          .filter(Number.isFinite)),
      };

      removeRulesVfx();
      const sacrificeState = structuredClone(declaredState);
      sacrificeState.recentLog.push({
        sequence: 502,
        type: "rules_action_declared",
        actorId: "p1",
        details: {
          source: { cardId: sacrificeCardId, zone: "battlefield", itemId: "sacrifice-source-1" },
          cost: {
            sourceSacrificed: true,
            sacrificedCards: [{ itemId: "sacrifice-source-1", cardId: sacrificeCardId, ownerId: "p1", destination: "graveyard" }],
          },
        },
      });
      sacrificeState.battlefield = sacrificeState.battlefield.filter((item) => item.id !== "sacrifice-source-1");
      handleServerMessage(sacrificeState);
      await new Promise((resolve) => setTimeout(resolve, 90));
      const sacrifice = {
        flight: document.querySelectorAll(".rules-vfx-sacrifice").length,
        label: document.querySelector(".rules-vfx-impact-sacrificed")?.textContent || "",
      };

      removeRulesVfx();
      const triggeredState = structuredClone(sacrificeState);
      triggeredState.recentLog.push({
        sequence: 503,
        type: "rules_action_triggered",
        actorId: "p1",
        details: {
          source: { cardId: gracefulCardId, zone: "receptacle", ownerId: "p1", containerId: "p2" },
          stackDepth: 1,
        },
      });
      handleServerMessage(triggeredState);
      await new Promise((resolve) => setTimeout(resolve, 90));
      const triggered = document.querySelector(".rules-vfx-impact-triggered")?.textContent || "";
      const triggeredPulse = document.querySelectorAll(".rules-vfx-stack-pulse-triggered").length;

      removeRulesVfx();
      const resolvedState = structuredClone(triggeredState);
      resolvedState.players.p1.score = 20;
      resolvedState.recentLog.push({
        sequence: 504,
        type: "rules_action_resolved",
        actorId: "p2",
        details: {
          source: { cardId: gracefulCardId, zone: "receptacle", ownerId: "p1", containerId: "p2" },
          effectResult: { kind: "score", playerId: "p1", delta: 20, score: 20 },
        },
      });
      handleServerMessage(resolvedState);
      await new Promise((resolve) => setTimeout(resolve, 90));
      const resolved = document.querySelector(".rules-vfx-impact-resolved")?.textContent || "";
      const score = document.querySelector(".rules-vfx-impact-score")?.textContent || "";
      const resolvedPulse = document.querySelectorAll(".rules-vfx-stack-pulse-resolved").length;

      removeRulesVfx();
      const drawState = structuredClone(resolvedState);
      drawState.recentLog.push({
        sequence: 505,
        type: "rules_action_resolved",
        actorId: "p2",
        details: {
          source: { cardId: "fvk7w9y8xidbuwa_en", zone: "battlefield", ownerId: "p1", itemId: "seeker-1" },
          effectResult: { kind: "draw", playerId: "p1", count: 1 },
        },
      });
      handleServerMessage(drawState);
      await new Promise((resolve) => setTimeout(resolve, 90));
      const draw = document.querySelector(".rules-vfx-impact-draw")?.textContent || "";

      removeRulesVfx();
      const scoreLossState = structuredClone(drawState);
      scoreLossState.players.p1.score = -15;
      scoreLossState.recentLog.push({
        sequence: 506,
        type: "rules_action_resolved",
        actorId: "p2",
        details: {
          source: { cardId: "de3meyzl13rpqo5_en", zone: "battlefield", ownerId: "p1", itemId: "half-han-1" },
          effectResult: { kind: "score", playerId: "p1", delta: -20, score: -15 },
        },
      });
      handleServerMessage(scoreLossState);
      await new Promise((resolve) => setTimeout(resolve, 90));
      const scoreLoss = document.querySelector(".rules-vfx-impact-score-loss")?.textContent || "";

      removeRulesVfx();
      const discardState = structuredClone(scoreLossState);
      discardState.recentLog.push({
        sequence: 507,
        type: "rules_choice_resolved",
        actorId: "p1",
        details: {
          kind: "discard_then_draw", playerId: "p1", count: 1,
          cardIds: ["fvk7w9y8xidbuwa_en"], drawCount: 2,
          sourceCardId: "zni76s4aabicqag_en",
        },
      });
      handleServerMessage(discardState);
      await new Promise((resolve) => setTimeout(resolve, 90));
      const discarded = document.querySelector(".rules-vfx-impact-discarded")?.textContent || "";
      const drawAfterDiscard = document.querySelector(".rules-vfx-impact-draw")?.textContent || "";

      removeRulesVfx();
      const moveState = structuredClone(discardState);
      moveState.battlefield = moveState.battlefield.filter((item) => item.id !== "defer-persistent-target");
      moveState.recentLog.push({
        sequence: 508,
        type: "rules_action_resolved",
        actorId: "p1",
        details: {
          label: "Defer target",
          effectResult: {
            kind: "move_card", status: "moved", cardId: moveTargetCardId,
            itemId: "defer-persistent-target", ownerId: "p2", fromZone: "battlefield",
            toZone: "deck", position: "top",
          },
        },
      });
      handleServerMessage(moveState);
      await new Promise((resolve) => setTimeout(resolve, 90));
      const moved = {
        flight: document.querySelectorAll(".rules-vfx-effect-card").length,
        glint: document.querySelectorAll(".rules-vfx-effect-card .rules-vfx-flight-glint").length,
        label: document.querySelector(".rules-vfx-impact-moved")?.textContent || "",
      };
      removeRulesVfx();
      const exileState = structuredClone(moveState);
      exileState.players.p2.zones.graveyard.cards = exileState.players.p2.zones.graveyard.cards
        .filter((cardId) => cardId !== exileTargetCardId);
      exileState.players.p2.zones.exile.cards = [exileTargetCardId, ...(exileState.players.p2.zones.exile.cards || [])];
      exileState.recentLog.push({
        sequence: 509,
        type: "rules_action_resolved",
        actorId: "p1",
        details: {
          label: "Exile from Limbo",
          effectResult: {
            kind: "move_card", status: "moved", cardId: exileTargetCardId,
            ownerId: "p2", fromContainerId: "p2", fromZone: "graveyard",
            toZone: "exile", position: "top", reason: "exile",
          },
        },
      });
      handleServerMessage(exileState);
      await new Promise((resolve) => setTimeout(resolve, 90));
      const exiled = {
        flight: document.querySelectorAll(".rules-vfx-effect-card").length,
        label: document.querySelector(".rules-vfx-impact-moved")?.textContent || "",
        expectedLabel: t("rulesVfxExiled"),
      };
      removeRulesVfx();
      const destroyState = structuredClone(exileState);
      destroyState.players.p2.zones.receptacle.cards = destroyState.players.p2.zones.receptacle.cards
        .filter((cardId) => cardId !== destroyTargetCardId);
      destroyState.players.p1.zones.graveyard.cards = [destroyTargetCardId, ...(destroyState.players.p1.zones.graveyard.cards || [])];
      destroyState.recentLog.push({
        sequence: 510,
        type: "rules_action_resolved",
        actorId: "p1",
        details: {
          label: "Disfigure target",
          effectResult: {
            kind: "move_card", status: "moved", cardId: destroyTargetCardId,
            ownerId: "p1", fromContainerId: "p2", fromZone: "receptacle",
            toZone: "graveyard", position: "top", reason: "destroy",
          },
        },
      });
      handleServerMessage(destroyState);
      await new Promise((resolve) => setTimeout(resolve, 90));
      const destroyed = {
        flight: document.querySelectorAll(".rules-vfx-destroy-card").length,
        shards: document.querySelectorAll(".rules-vfx-destruction-shard").length,
        burst: document.querySelectorAll(".rules-vfx-impact-burst-destroyed").length,
        label: document.querySelector(".rules-vfx-impact-destroyed")?.textContent || "",
        expectedLabel: t("rulesVfxDestroyed"),
      };
      removeRulesVfx();
      const noEligibleState = structuredClone(destroyState);
      noEligibleState.recentLog.push({
        sequence: 511,
        type: "rules_action_resolved",
        actorId: "p1",
        details: {
          label: "Remove by Chance",
          effectResult: {
            kind: "move_card", status: "no_eligible_card", random: true,
            fromContainerId: "p2", fromZone: "receptacle",
            toZone: "graveyard", position: "top", reason: "destroy",
          },
        },
      });
      handleServerMessage(noEligibleState);
      await new Promise((resolve) => setTimeout(resolve, 90));
      const noEligible = {
        label: document.querySelector(".rules-vfx-impact-target-gone")?.textContent || "",
        expectedLabel: t("rulesVfxNoEligibleTarget"),
      };
      removeRulesVfx();
      const deckDiscardState = structuredClone(noEligibleState);
      deckDiscardState.recentLog.push({
        sequence: 512,
        type: "rules_action_resolved",
        actorId: "p1",
        details: {
          label: "Pluff — triggered effect",
          source: { cardId: "ghb6i1uoiqq12o2_en", ownerId: "p1", zone: "battlefield", itemId: "pluff-1" },
          effectResult: {
            kind: "discard_deck", playerId: "p1", count: 1,
            cardIds: [gracefulCardId],
          },
        },
      });
      handleServerMessage(deckDiscardState);
      await new Promise((resolve) => setTimeout(resolve, 90));
      const deckDiscard = {
        flight: document.querySelectorAll(".rules-vfx-discard-card").length,
        label: document.querySelector(".rules-vfx-impact-discarded")?.textContent || "",
        expectedLabel: rulesText("rulesVfxDeckDiscarded", { count: 1 }),
      };
      removeRulesVfx();
      const mercifulPagoId = "8lion52jjnmxvko_en";
      deckDiscardState.battlefield.push({
        id: "merciful-pago-support", ownerId: "p1", cardId: mercifulPagoId,
        x: 640, y: 420, faceUp: true, rotation: 0, counters: {},
        fieldZone: "confrontation", isSupport: true,
      });
      latestState = deckDiscardState;
      renderAll();
      const supportWinState = structuredClone(deckDiscardState);
      supportWinState.battlefield = supportWinState.battlefield.filter((item) => item.id !== "merciful-pago-support");
      supportWinState.players.p2.score = 10;
      supportWinState.players.p2.zones.receptacle.cards = [mercifulPagoId, ...(supportWinState.players.p2.zones.receptacle.cards || [])];
      supportWinState.recentLog.push({
        sequence: 513,
        type: "rules_confrontation_cleanup",
        actorId: "p1",
        details: {
          winnerId: "p1", captured: [], supportExiled: [],
          supportResolved: [{
            kind: "opponent_vessel_score", cardId: mercifulPagoId,
            itemId: "merciful-pago-support", playerId: "p2", delta: 10, score: 10,
          }],
        },
      });
      handleServerMessage(supportWinState);
      await new Promise((resolve) => setTimeout(resolve, 90));
      const supportWin = {
        flight: document.querySelectorAll(".rules-vfx-effect-card").length,
        score: document.querySelector(".rules-vfx-impact-score")?.textContent || "",
      };
      await new Promise((resolve) => setTimeout(resolve, 1200));
      return {
        pluffEncoded,
        initialReplayCount,
        declared,
        sacrifice,
        triggered,
        triggeredPulse,
        resolved,
        resolvedPulse,
        score,
        draw,
        scoreLoss,
        discarded,
        drawAfterDiscard,
        moved,
        exiled,
        destroyed,
        noEligible,
        deckDiscard,
        supportWin,
        remaining: document.querySelectorAll(".rules-vfx-flight, .rules-vfx-impact, .rules-vfx-exhaust-ring, .rules-vfx-exhaust-label, .rules-vfx-impact-burst, .rules-vfx-target-lock, .rules-vfx-effect-cast, .rules-vfx-effect-seal, .rules-vfx-effect-release, .rules-vfx-stack-pulse").length,
      };
    }, {
      tributeCardId: rulesStack.tributeCardId,
      encodedCardId: rulesStack.encoded.cardId,
      sacrificeCardId: rulesStack.sacrifice.cardId,
      gracefulCardId: "aumzs91roqg77y1_en",
      moveTargetCardId: rulesStack.moveAbility.targetCardId,
      exileTargetCardId: rulesStack.exileAbility.targetCardId,
      destroyTargetCardId: rulesStack.destroyAbility.targetCardId,
    });
    const stackNeutralize = await page.evaluate(({ targetCardId }) => {
      const savedState = structuredClone(latestState);
      const neutralizeCardId = "2y961kgs0crdict_en";
      const targetActionId = "neutralize-target-action";
      latestState.phaseTracker = { enabled: true, advanced: true, index: ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_reaction"), turn: 2, passedPlayerIds: [] };
      latestState.ended = false;
      latestState.players.p1.zones.hand = {
        cards: [neutralizeCardId], count: 1, owners: { [neutralizeCardId]: "p1" },
      };
      latestState.tokens = [{
        id: "neutralize-essence", ownerId: "p1", x: 0, y: 0,
        isEssence: true, isNeutralCounter: false, temperament: "capricious",
        counters: { essence: 2 },
      }];
      latestState.rulesEngine.enabled = true;
      latestState.rulesEngine.pendingChoice = null;
      latestState.rulesEngine.priorityPlayerId = "p1";
      latestState.rulesEngine.priorityPasses = [];
      latestState.rulesEngine.actionStack = [{
        id: targetActionId, controllerId: "p2", label: "Target Will",
        kind: "play_card", phaseId: "confrontation_reaction", turn: 2,
        sourceOnStack: true,
        source: {
          cardId: targetCardId, zone: "hand", ownerId: "p2",
          cardType: "ephemeral_will",
        },
        targets: [], cost: {},
      }];
      window.__sent = [];
      renderAll();

      const playableWithTarget = handCardIsPlayable(neutralizeCardId);
      const began = beginRulesBoardAction({ cardId: neutralizeCardId, zone: "hand", handIndex: 0 });
      const stage = pendingRulesBoardFlow?.stage || null;
      const stackTarget = document.querySelector(`[data-stack-action-id="${targetActionId}"]`);
      const highlighted = stackTarget?.classList.contains("rules-valid-target") || false;
      const legend = document.querySelector("#rulesFlowInstruction")?.textContent || "";
      stackTarget?.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, cancelable: true }));
      const payload = window.__sent.find((entry) => entry.abilityId === "neutralize-stack-card") || null;

      latestState.rulesEngine.actionStack = [];
      renderRulesStack();
      renderHandTray();
      const playableWithoutTarget = handCardIsPlayable(neutralizeCardId);

      latestState = savedState;
      renderAll();
      return {
        neutralizeCardId, targetActionId, began, stage, highlighted, legend,
        playableWithTarget, playableWithoutTarget, payload,
        expectedLabel: rulesText("rulesDefaultPlay", { card: cardName(neutralizeCardId) }),
      };
    }, { targetCardId: rulesStack.sourceCardId });
    const conditionalStackPayment = await page.evaluate(() => {
      const savedState = structuredClone(latestState);
      const denyCardId = "g0mtnp4zbhwj7cb_en";
      const ignoreCardId = "ey6fuk5gguasrb0_en";
      const targetCard = [...cardsById.values()].find((card) => (
        card.type === "ephemeral_will" && ![denyCardId, ignoreCardId].includes(card.id)
      ));
      const effectCard = [...cardsById.values()].find((card) => card.type === "manifestation");
      const paymentCard = [...cardsById.values()].find((card) => (
        card.type === "manifestation" && Number(card.power) >= 2
      ));
      const handZone = (cards) => ({
        cards: [...cards], count: cards.length,
        owners: Object.fromEntries(cards.map((cardId) => [cardId, "p1"])),
      });
      const cardActionId = "conditional-card-action";
      const effectActionId = "conditional-effect-action";
      latestState.phaseTracker = { enabled: true, advanced: true, index: ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_reaction"), turn: 2, passedPlayerIds: [] };
      latestState.ended = false;
      latestState.players.p1.zones.hand = handZone([denyCardId, ignoreCardId, paymentCard.id]);
      latestState.tokens = [];
      latestState.rulesEngine.enabled = true;
      latestState.rulesEngine.priorityPlayerId = "p1";
      latestState.rulesEngine.priorityPasses = [];
      latestState.rulesEngine.pendingChoice = null;
      latestState.rulesEngine.actionStack = [
        {
          id: cardActionId, controllerId: "p2", label: "Target card", kind: "play_card",
          sourceOnStack: true,
          source: { cardId: targetCard.id, zone: "hand", ownerId: "p2", cardType: "ephemeral_will" },
          targets: [], cost: {}, phaseId: "confrontation_reaction", turn: 2,
        },
        {
          id: effectActionId, controllerId: "p2", label: "Target effect", kind: "triggered_effect",
          source: { cardId: effectCard.id, zone: "battlefield", itemId: "effect-source", ownerId: "p2" },
          targets: [], cost: {}, phaseId: "confrontation_reaction", turn: 2,
        },
      ];
      window.__sent = [];
      renderAll();

      const denyPlayable = handCardIsPlayable(denyCardId);
      const ignorePlayable = handCardIsPlayable(ignoreCardId);
      const denyDraftKinds = buildRulesActionDraft({ cardId: denyCardId, zone: "hand", handIndex: 0 })
        .structuredTargets.map((target) => target.kind);
      const ignoreDraftKinds = buildRulesActionDraft({ cardId: ignoreCardId, zone: "hand", handIndex: 1 })
        .structuredTargets.map((target) => target.kind);
      beginRulesBoardAction({ cardId: denyCardId, zone: "hand", handIndex: 0 });
      document.querySelector(`[data-stack-action-id="${cardActionId}"]`)
        .dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, cancelable: true }));
      const denyPayload = window.__sent.find((entry) => entry.abilityId === "deny-stack-card-unless-paid");
      beginRulesBoardAction({ cardId: ignoreCardId, zone: "hand", handIndex: 1 });
      document.querySelector(`[data-stack-action-id="${effectActionId}"]`)
        .dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, cancelable: true }));
      const ignorePayload = window.__sent.find((entry) => entry.abilityId === "ignore-stack-effect-unless-paid");

      latestState.players.p1.zones.hand = handZone([paymentCard.id]);
      latestState.rulesEngine.pendingChoice = {
        id: "stack-payment-pay", kind: "stack_counter_payment", playerId: "p1",
        payment: "{H}{H}", requirements: { hollow: 2 }, mode: "neutralize",
        sourceCardId: denyCardId, targetActionId: cardActionId,
        targetCardId: targetCard.id, targetControllerId: "p2", targetKind: "stack_action",
      };
      window.__sent = [];
      renderAll();
      const payButton = document.querySelector("#rulesFlowPayBtn");
      const paymentCardElement = document.querySelector(`[data-hand-card="${paymentCard.id}"]`);
      const paymentInitial = {
        visible: !document.querySelector("#rulesBoardFlow").classList.contains("hidden"),
        modalHidden: document.querySelector("#rulesChoicePanel").classList.contains("hidden"),
        actionsVisible: !document.querySelector("#rulesFlowChoiceActions").classList.contains("hidden"),
        payDisabled: payButton.disabled,
        candidate: paymentCardElement.classList.contains("is-tribute-candidate"),
        targetMarked: document.querySelector(`[data-stack-action-id="${cardActionId}"]`).classList.contains("rules-counter-payment-target"),
        pendingLabel: document.querySelector(`[data-stack-action-id="${cardActionId}"] .rules-stack-payment-state`)?.textContent || "",
        instruction: document.querySelector("#rulesFlowInstruction").textContent,
        minFont: Math.min(...[...document.querySelectorAll("#rulesFloatingCard, #rulesFloatingCard *")]
          .filter((element) => getComputedStyle(element).display !== "none")
          .map((element) => parseFloat(getComputedStyle(element).fontSize))
          .filter(Number.isFinite)),
      };
      paymentCardElement.click();
      const payEnabledAfterSelection = !document.querySelector("#rulesFlowPayBtn").disabled;
      document.querySelector("#rulesFlowPayBtn").click();
      const payPayload = window.__sent.at(-1);

      latestState.rulesEngine.pendingChoice = {
        ...latestState.rulesEngine.pendingChoice,
        id: "stack-payment-decline", mode: "cancel", targetKind: "stack_effect",
        sourceCardId: ignoreCardId, targetActionId: effectActionId, targetCardId: effectCard.id,
      };
      window.__sent = [];
      renderAll();
      document.querySelector("#rulesFlowDeclineBtn").click();
      const declinePayload = window.__sent.at(-1);

      latestState = savedState;
      renderAll();
      return {
        denyCardId, ignoreCardId, cardActionId, effectActionId,
        denyPlayable, ignorePlayable, denyDraftKinds, ignoreDraftKinds,
        denyPayload, ignorePayload, paymentInitial, payEnabledAfterSelection,
        payPayload, declinePayload, paymentCardId: paymentCard.id,
      };
    });
    const stackCopy = await page.evaluate(() => {
      const savedState = structuredClone(latestState);
      const imitateCardId = "q6rha5kz42bkxle_en";
      const targetWill = [...cardsById.values()].find((card) => (
        card.type === "ephemeral_will" && card.id !== imitateCardId
      ));
      const manifestations = [...cardsById.values()].filter((card) => card.type === "manifestation").slice(0, 2);
      const originalActionId = "imitate-original-action";
      latestState.phaseTracker = { enabled: true, advanced: true, index: ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_reaction"), turn: 2, passedPlayerIds: [] };
      latestState.ended = false;
      latestState.rulesEngine.enabled = true;
      latestState.rulesEngine.priorityPlayerId = "p2";
      latestState.rulesEngine.priorityPasses = [];
      latestState.battlefield = manifestations.map((card, index) => ({
        id: `imitate-target-${index + 1}`, cardId: card.id,
        ownerId: index ? "p2" : "p1", controllerId: index ? "p2" : "p1",
        x: 35 + index * 28, y: 42, faceUp: true, rotation: 0, counters: {},
      }));
      latestState.rulesEngine.actionStack = [
        {
          id: originalActionId, controllerId: "p2", label: "Target Will", kind: "play_card",
          sourceOnStack: true,
          source: { cardId: targetWill.id, zone: "hand", ownerId: "p2", cardType: "ephemeral_will" },
          targets: [{
            kind: "card", itemId: "imitate-target-1", cardId: manifestations[0].id, ownerId: "p1",
          }],
          cost: {}, phaseId: "confrontation_reaction", turn: 2,
        },
        {
          id: "imitate-copy-action", controllerId: "p1", label: "Target Will", kind: "play_card",
          source: { cardId: targetWill.id, zone: "hand", ownerId: "p2", cardType: "ephemeral_will" },
          targets: [{
            kind: "card", itemId: "imitate-target-2", cardId: manifestations[1].id, ownerId: "p2",
          }],
          cost: {}, phaseId: "confrontation_reaction", turn: 2,
          isStackCopy: true, copiedFromActionId: originalActionId,
        },
      ];
      const copyChoice = (id) => ({
        id, kind: "stack_copy_targets", playerId: "p1",
        sourceCardId: imitateCardId, targetActionId: originalActionId,
        targetCardId: targetWill.id,
        targetRules: { kind: "card", min: 1, max: 1, cardType: "manifestation" },
        originalTargets: [{
          kind: "card", itemId: "imitate-target-1", cardId: manifestations[0].id, ownerId: "p1",
        }],
      });
      latestState.rulesEngine.pendingChoice = copyChoice("stack-copy-retarget");
      window.__sent = [];
      renderAll();
      const candidates = [...document.querySelectorAll(".bf-card.rules-valid-target")];
      const initial = {
        visible: !document.querySelector("#rulesBoardFlow").classList.contains("hidden"),
        modalHidden: document.querySelector("#rulesChoicePanel").classList.contains("hidden"),
        actionsVisible: !document.querySelector("#rulesFlowChoiceActions").classList.contains("hidden"),
        payHidden: document.querySelector("#rulesFlowPayBtn").classList.contains("hidden"),
        candidateIds: candidates.map((element) => element.dataset.itemId).sort(),
        keepLabel: document.querySelector("#rulesFlowDeclineBtn").textContent,
        instruction: document.querySelector("#rulesFlowInstruction").textContent,
        copyBadge: document.querySelector(".rules-stack-copy-state")?.textContent || "",
      };
      document.querySelector('.bf-card[data-item-id="imitate-target-2"]')
        .dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, cancelable: true }));
      const retargetPayload = window.__sent.at(-1);

      latestState.rulesEngine.pendingChoice = copyChoice("stack-copy-keep");
      window.__sent = [];
      renderAll();
      document.querySelector("#rulesFlowDeclineBtn").click();
      const keepPayload = window.__sent.at(-1);
      const logHtml = formatLogEntry({
        actorId: "p1", actorName: "P1", type: "rules_choice_resolved",
        details: {
          kind: "stack_copy_targets", playerId: "p1", targetCardId: targetWill.id,
          status: "copied", targets: [{
            kind: "card", itemId: "imitate-target-2", cardId: manifestations[1].id, ownerId: "p2",
          }],
        },
      }, { language: "fr", html: true });

      latestState = savedState;
      renderAll();
      return {
        initial, retargetPayload, keepPayload, logHtml,
        secondCardId: manifestations[1].id,
      };
    });
    const ongoingEffect = await page.evaluate(async ({ encodedCardId, targetCardId }) => {
      latestState.rulesEngine.ongoingEffects = [
        {
          id: "effect-1",
          actionId: "action-effect-1",
          abilityId: "reduce-manifestation-power",
          controllerId: "p1",
          source: { itemId: "encoded-source-1", cardId: encodedCardId, ownerId: "p1" },
          target: { itemId: "rules-target-1", cardId: targetCardId, ownerId: "p2" },
          kind: "power_modifier",
          value: -2,
          duration: "until_end_of_turn",
          startedTurn: 2,
        },
        {
          id: "effect-2",
          actionId: "action-effect-2",
          abilityId: "copy-power-temperament",
          controllerId: "p1",
          source: { itemId: "encoded-source-1", cardId: encodedCardId, ownerId: "p1" },
          target: { itemId: "rules-target-1", cardId: targetCardId, ownerId: "p2" },
          kind: "copy_power_temperament",
          duration: "while_source_and_target_on_field",
          startedTurn: 2,
        },
      ];
      renderBattlefield();
      const target = document.querySelector('.bf-card[data-item-id="rules-target-1"]');
      const badge = target.querySelector(".rules-effect-badge");
      badge.focus();
      playRulesVfxEffectBind(latestState.rulesEngine.ongoingEffects[1]);
      await new Promise((resolve) => setTimeout(resolve, 40));
      const result = {
        marked: target.classList.contains("has-ongoing-effect"),
        frameRemoved: !target.querySelector(".rules-effect-frame"),
        badgeCount: badge.textContent.trim(),
        badgeLabel: badge.getAttribute("aria-label"),
        tempPowerMarker: target.querySelector(".bf-counter-effect.bf-counter-temp")?.textContent,
        temporaryLinkCount: document.querySelectorAll('#rulesEffectLayer [data-effect-id="effect-1"]').length,
        linkCount: document.querySelectorAll("#rulesEffectLayer .rules-effect-link").length,
        highlighted: document.querySelector("#rulesEffectLayer .rules-effect-link")?.classList.contains("highlighted"),
        flowAnimation: getComputedStyle(document.querySelector(".rules-effect-link-flow")).animationName,
        bindPathCount: document.querySelectorAll(".rules-vfx-effect-cast").length,
        sealCount: document.querySelectorAll(".rules-vfx-effect-seal").length,
      };
      badge.blur();
      removeRulesVfx();
      return result;
    }, { encodedCardId: rulesStack.encoded.cardId, targetCardId: rulesStack.targetCardId });
    await page.setViewportSize({ width: 1280, height: 720 });
    const rulesLayout = await page.evaluate(() => {
      phaseTrackerVisible = false;
      latestState.rulesEngine.priorityPlayerId = myPlayerId;
      renderPhaseTracker();
      renderRulesStack();
      const panel = document.querySelector("#rulesStackPanel");
      const chat = document.querySelector("#chatPanel");
      const inspector = document.querySelector("#inspectPanel .box");
      const toolbar = document.querySelector("#sideToolbars");
      const phaseDock = document.querySelector("#phaseTracker");
      const rect = panel.getBoundingClientRect();
      const chatRect = chat.getBoundingClientRect();
      const inspectorRect = inspector.getBoundingClientRect();
      const toolbarRect = toolbar.getBoundingClientRect();
      const phaseRect = phaseDock.getBoundingClientRect();
      const overlapWidth = Math.max(0, Math.min(rect.right, chatRect.right) - Math.max(rect.left, chatRect.left));
      const overlapHeight = Math.max(0, Math.min(rect.bottom, chatRect.bottom) - Math.max(rect.top, chatRect.top));
      const inspectorOverlapWidth = Math.max(0, Math.min(rect.right, inspectorRect.right) - Math.max(rect.left, inspectorRect.left));
      const inspectorOverlapHeight = Math.max(0, Math.min(rect.bottom, inspectorRect.bottom) - Math.max(rect.top, inspectorRect.top));
      const populatedStack = structuredClone(latestState.rulesEngine.actionStack);
      latestState.rulesEngine.actionStack = [];
      renderRulesStack();
      const emptyHeight = panel.getBoundingClientRect().height;
      const emptyBodyHidden = document.querySelector("#rulesStackBody").classList.contains("hidden");
      latestState.rulesEngine.actionStack = populatedStack;
      renderRulesStack();
      return {
        horizontalOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        chatOverlapArea: overlapWidth * overlapHeight,
        inspectorOverlapArea: inspectorOverlapWidth * inspectorOverlapHeight,
        inspectorClearsToolbar: inspectorRect.left >= toolbarRect.right + 4,
        inspectButtonInLeftToolbar: document.querySelector("#viewToolbar #inspectReopenBtn") !== null,
        phaseDetailsHidden: document.querySelector("#phaseTracker").classList.contains("hidden"),
        phaseOrbCount: document.querySelectorAll("#phaseTracker .phase-orb").length,
        phaseBottomGap: window.innerHeight - phaseRect.bottom,
        phaseRightGap: window.innerWidth - phaseRect.right,
        phaseBackground: getComputedStyle(phaseDock).backgroundColor,
        stackAbovePhase: rect.bottom <= phaseRect.top + 8,
        turnContext: document.querySelector("#rulesTurnContext").textContent,
        emptyHeight,
        emptyBodyHidden,
      };
    });
    if (process.env.RULES_LAYOUT_SCREENSHOT_PATH) {
      await page.screenshot({ path: process.env.RULES_LAYOUT_SCREENSHOT_PATH, animations: "disabled" });
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    if (process.env.RULES_VFX_SCREENSHOT_PATH) {
      await page.evaluate(({ tributeCardId, encodedCardId }) => {
        removeRulesVfx();
        const nextState = structuredClone(latestState);
        const sequence = Math.max(0, ...(nextState.recentLog || []).map((entry) => Number(entry.sequence) || 0)) + 1;
        nextState.recentLog.push({
          sequence,
          type: "rules_action_declared",
          actorId: "p1",
          details: {
            source: { cardId: encodedCardId, zone: "battlefield", itemId: "encoded-source-1" },
            cost: {
              tributeCardIds: [tributeCardId],
              essenceSpent: [{ tokenId: "encoded-essence", temperament: "hollow", amount: 2 }],
              sourceExhausted: true,
            },
          },
        });
        handleServerMessage(nextState);
      }, { tributeCardId: rulesStack.tributeCardId, encodedCardId: rulesStack.encoded.cardId });
      await page.waitForTimeout(120);
      await page.screenshot({ path: process.env.RULES_VFX_SCREENSHOT_PATH, animations: "allow" });
      await page.evaluate(() => removeRulesVfx());
    }
    if (process.env.RULES_TRIGGER_SCREENSHOT_PATH) {
      await page.evaluate(() => {
        removeRulesVfx();
        const nextState = structuredClone(latestState);
        const sequence = Math.max(0, ...(nextState.recentLog || []).map((entry) => Number(entry.sequence) || 0)) + 1;
        nextState.recentLog.push({
          sequence,
          type: "rules_action_triggered",
          actorId: "p1",
          details: {
            source: { cardId: "aumzs91roqg77y1_en", zone: "receptacle", ownerId: "p1", containerId: "p2" },
            stackDepth: 1,
          },
        });
        handleServerMessage(nextState);
      });
      await page.waitForTimeout(120);
      await page.screenshot({ path: process.env.RULES_TRIGGER_SCREENSHOT_PATH, animations: "allow" });
      await page.evaluate(() => removeRulesVfx());
    }
    if (process.env.RULES_SCREENSHOT_PATH) {
      await page.locator("#rulesStackPanel").screenshot({
        path: process.env.RULES_SCREENSHOT_PATH,
        animations: "disabled",
        timeout: 5000,
      });
    }
    if (process.env.RULES_ACTION_SCREENSHOT_PATH) {
      await page.evaluate(({ sourceCardId }) => {
        latestState.rulesEngine.priorityPlayerId = myPlayerId;
        renderRulesStack();
        openRulesActionPanel({ cardId: sourceCardId, zone: "hand", itemId: null });
      }, { sourceCardId: rulesStack.sourceCardId });
      await page.locator("#rulesActionPanel .box").screenshot({
        path: process.env.RULES_ACTION_SCREENSHOT_PATH,
        animations: "disabled",
        timeout: 5000,
      });
      await page.evaluate(() => closeRulesActionPanel());
    }
    if (process.env.ENCODED_RULES_SCREENSHOT_PATH) {
      await page.evaluate(({ cardId }) => {
        latestState.rulesEngine.priorityPlayerId = myPlayerId;
        renderRulesStack();
        openRulesActionPanel({ cardId, zone: "battlefield", itemId: "encoded-source-1" });
      }, { cardId: rulesStack.encoded.cardId });
      await page.locator("#rulesActionPanel .box").screenshot({
        path: process.env.ENCODED_RULES_SCREENSHOT_PATH,
        animations: "disabled",
        timeout: 5000,
      });
      await page.evaluate(() => closeRulesActionPanel());
    }

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
      const launcherInitiallyHidden = document.querySelector("#tournamentLauncherOptions").classList.contains("hidden");
      document.querySelector("#tournamentToggleBtn").click();
      const launcherExpanded = !document.querySelector("#tournamentLauncherOptions").classList.contains("hidden")
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
      const drawResolutionLogs = ["fr", "en", "it"].map((language) => formatLogEntry({
        actorId: "p2",
        actorName: "P2",
        type: "rules_action_resolved",
        details: {
          label: "Keen-eyed Seeker — triggered effect",
          source: { cardId: "7e2ppf4rfgkdfms_en" },
          stackDepth: 0,
          effectResult: { kind: "draw", playerId: "p1", count: 1 },
        },
      }, { language }));
      const resolvedCardHoverLog = formatLogEntry({
        actorId: "p2", actorName: "P2", type: "rules_action_resolved",
        details: {
          label: "Keen-eyed Seeker — triggered effect", stackDepth: 0,
          source: { cardId: "7e2ppf4rfgkdfms_en" },
        },
      }, { language: "fr", html: true });
      const scoreLossLogs = ["fr", "en", "it"].map((language) => formatLogEntry({
        actorId: "p2",
        actorName: "P2",
        type: "rules_action_resolved",
        details: {
          label: "Half Han — triggered effect",
          stackDepth: 0,
          effectResult: { kind: "score", playerId: "p1", delta: -20, score: -15 },
        },
      }, { language }));
      const choiceResolutionLogs = ["fr", "en", "it"].map((language) => formatLogEntry({
        actorId: "p1",
        actorName: "P1",
        type: "rules_choice_resolved",
        details: {
          playerId: "p1", count: 1,
          cardIds: ["fvk7w9y8xidbuwa_en"], sourceCardId: "7e2ppf4rfgkdfms_en",
        },
      }, { language }));
      const targetTriggerLogs = ["fr", "en", "it"].map((language) => formatLogEntry({
        actorId: "p1",
        actorName: "P1",
        type: "rules_action_triggered",
        details: {
          source: { cardId: "7e2ppf4rfgkdfms_en" },
          targets: [{ kind: "player", playerId: "p2" }],
          stackDepth: 1,
        },
      }, { language }));
      const moveResolutionLogs = ["fr", "en", "it"].map((language) => formatLogEntry({
        actorId: "p1",
        actorName: "P1",
        type: "rules_action_resolved",
        details: {
          label: "Defer target", stackDepth: 0,
          effectResult: {
            kind: "move_card", status: "moved", cardId: "fvk7w9y8xidbuwa_en",
            ownerId: "p2", toZone: "deck", position: "top",
          },
        },
      }, { language }));
      const publicZoneTargetLogs = ["fr", "en", "it"].map((language) => formatLogEntry({
        actorId: "p1", actorName: "P1", type: "rules_action_declared",
        details: {
          label: "Exile from Limbo", stackDepth: 1,
          source: { cardId: "1q6crbc7nwugrgs_en" },
          targets: [{
            kind: "zone_card", cardId: "fvk7w9y8xidbuwa_en",
            containerId: "p2", ownerId: "p2", zone: "graveyard",
          }],
        },
      }, { language }));
      const destroyResolutionLogs = ["fr", "en", "it"].map((language) => formatLogEntry({
        actorId: "p1", actorName: "P1", type: "rules_action_resolved",
        details: {
          label: "Disfigure target", stackDepth: 0,
          effectResult: {
            kind: "move_card", status: "moved", cardId: "fvk7w9y8xidbuwa_en",
            ownerId: "p1", fromContainerId: "p2", fromZone: "receptacle",
            toZone: "graveyard", position: "top", reason: "destroy",
          },
        },
      }, { language }));
      const noEligibleLogs = ["fr", "en", "it"].map((language) => formatLogEntry({
        actorId: "p1", actorName: "P1", type: "rules_action_resolved",
        details: {
          label: "Remove by Chance", stackDepth: 0,
          effectResult: {
            kind: "move_card", status: "no_eligible_card", random: true,
            fromContainerId: "p2", fromZone: "receptacle",
            toZone: "graveyard", position: "top", reason: "destroy",
          },
        },
      }, { language }));
      const deckDiscardLogs = ["fr", "en", "it"].map((language) => formatLogEntry({
        actorId: "p1", actorName: "P1", type: "rules_action_resolved",
        details: {
          label: "Pluff — triggered effect", stackDepth: 0,
          effectResult: {
            kind: "discard_deck", playerId: "p1", count: 1,
            cardIds: ["fvk7w9y8xidbuwa_en"],
          },
        },
      }, { language }));
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
      return { organizer, judge, launcherInitiallyHidden, launcherExpanded, frenchLog, englishExportLog, drawResolutionLogs, resolvedCardHoverLog, scoreLossLogs, choiceResolutionLogs, targetTriggerLogs, moveResolutionLogs, publicZoneTargetLogs, destroyResolutionLogs, noEligibleLogs, deckDiscardLogs };
    });
    await page.setViewportSize({ width: 390, height: 844 });
    const tournamentMobile = await page.evaluate(() => ({
      noHorizontalOverflow: document.documentElement.scrollWidth <= window.innerWidth,
      headerVisible: document.querySelector(".tournament-header").getBoundingClientRect().height > 0,
      seatsVisible: document.querySelectorAll(".tournament-seat").length === 2,
    }));
    await page.setViewportSize({ width: 1440, height: 1000 });

    const boardFirstPlay = await page.evaluate(() => {
      closeRulesBoardFlow();
      connectionMode = "casual";
      connectionRole = "player";
      isObserver = false;
      myPlayerId = "p1";
      document.querySelector("#gameScreen").classList.remove("hidden");
      const willId = "obn1uv72ewxv3y5_en";
      const tribute = [...cardsById.values()].find((card) => card.type === "manifestation"
        && card.temperaments?.includes("choleric") && Number(card.power) >= 1);
      const target = [...cardsById.values()].find((card) => card.type === "manifestation" && card.id !== tribute.id);
      const zone = (cards = []) => ({ cards: [...cards], count: cards.length, owners: Object.fromEntries(cards.map((cardId) => [cardId, "p1"])) });
      latestState.players.p1.zones.hand = zone([willId, tribute.id]);
      latestState.players.p1.deckDefinition = { main: [willId, tribute.id] };
      latestState.players.p2.deckDefinition = { main: [target.id] };
      latestState.tokens = [{
        id: "board-flow-essence", ownerId: "p1", isEssence: true, isNeutralCounter: false,
        temperament: "choleric", counters: { essence: 1 },
      }];
      latestState.battlefield = [{
        id: "board-flow-target", ownerId: "p2", cardId: target.id,
        x: 690, y: 430, faceUp: true, rotation: 0, counters: {},
      }];
      latestState.phaseTracker = { enabled: true, advanced: true, index: ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_reaction"), turn: 2, passedPlayerIds: [] };
      latestState.rulesEngine = {
        enabled: true, priorityPlayerId: "p1", priorityPasses: [], actionStack: [],
        readyPlayerIds: ["p1", "p2"], firstManifestationComplete: true,
        pendingChoice: null, outcome: null,
      };
      window.__sent = [];
      renderAll();
      const wrap = document.querySelector("#battlefieldWrap").getBoundingClientRect();
      const realElementFromPoint = document.elementFromPoint.bind(document);
      document.elementFromPoint = () => document.querySelector("#battlefield");
      resolveDrop({ kind: "card", cardId: willId, handIndex: 0, cardOwnerId: "p1", fromOwnerId: "p1", fromZone: "hand" }, wrap.left + wrap.width * .68, wrap.top + wrap.height * .34);
      document.elementFromPoint = realElementFromPoint;
      const payment = {
        visible: !document.querySelector("#rulesBoardFlow").classList.contains("hidden"),
        stage: pendingRulesBoardFlow?.stage,
        floatingName: document.querySelector("#rulesFloatingCardName").textContent,
        essenceText: document.querySelector("#rulesBoardEssence").textContent.replace(/\s+/g, " ").trim(),
        candidateCount: document.querySelectorAll(".hand-card.is-tribute-candidate").length,
        sentBeforePayment: window.__sent.length,
      };
      document.elementFromPoint = () => document.querySelector("#battlefield");
      resolveDrop({ kind: "card", cardId: tribute.id, handIndex: 1, cardOwnerId: "p1", fromOwnerId: "p1", fromZone: "hand" }, wrap.left + 40, wrap.top + 40);
      document.elementFromPoint = realElementFromPoint;
      const targeting = {
        stage: pendingRulesBoardFlow?.stage,
        paidByDrag: pendingRulesBoardFlow?.selectedPaymentIndexes?.has(1) || false,
        highlighted: document.querySelectorAll(".rules-valid-target").length,
        reticles: document.querySelectorAll(".rules-target-reticle").length,
        arrowAnimation: getComputedStyle(document.querySelector("#rulesTargetArrow .rules-target-arrow-line")).animationName,
        arrow: document.querySelector("#rulesTargetArrow .rules-target-arrow-line").getAttribute("d"),
        instruction: document.querySelector("#rulesFlowInstruction").textContent,
      };
      document.querySelector('[data-item-id="board-flow-target"]').dispatchEvent(new PointerEvent("pointerdown", {
        bubbles: true, cancelable: true, clientX: 720, clientY: 460,
      }));
      targeting.targetLock = document.querySelectorAll(".rules-vfx-target-lock").length;
      const willPayload = window.__sent.find((payload) => payload.type === "declare_rules_action");
      const closedAfterTarget = document.querySelector("#rulesBoardFlow").classList.contains("hidden");

      const plainManifestation = [...cardsById.values()].find((card) => card.type === "manifestation"
        && String(card.effect || "").includes("Support from hand.")
        && !(triggeredAbilitiesByCard.get(card.id) || []).some((ability) => ability.trigger?.event === "enters_field"));
      latestState.players.p1.zones.hand = zone([plainManifestation.id]);
      latestState.phaseTracker.index = ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_reaction");
      latestState.rulesEngine.priorityPlayerId = "p1";
      latestState.rulesEngine.firstManifestationComplete = true;
      latestState.battlefield = [];
      latestState.tokens = [];
      window.__sent = [];
      renderAll();
      const wrap2 = document.querySelector("#battlefieldWrap").getBoundingClientRect();
      const dropX = wrap2.left + wrap2.width * .58;
      const dropY = wrap2.top + wrap2.height * .42;
      document.elementFromPoint = () => document.querySelector("#battlefield");
      resolveDrop({ kind: "card", cardId: plainManifestation.id, handIndex: 0, cardOwnerId: "p1", fromOwnerId: "p1", fromZone: "hand" }, dropX, dropY);
      document.elementFromPoint = realElementFromPoint;
      const manifestationPayload = window.__sent.find((payload) => payload.asSupport === true);

      const persistentWillId = "y6g3tex9ypttk8u_en";
      const persistentTribute = [...cardsById.values()].find((card) => card.type === "manifestation"
        && card.temperaments?.includes("melancholic") && Number(card.power) >= 2);
      const persistentTarget = [...cardsById.values()].find((card) => card.type === "manifestation" && card.id !== persistentTribute.id);
      latestState.players.p1.zones.hand = zone([persistentWillId, persistentTribute.id]);
      latestState.players.p1.deckDefinition = { main: [persistentWillId, persistentTribute.id] };
      latestState.players.p2.deckDefinition = { main: [persistentTarget.id] };
      latestState.phaseTracker.index = ADVANCED_PHASES.findIndex((phase) => phase.id === "end_actions");
      latestState.rulesEngine.priorityPlayerId = "p1";
      latestState.rulesEngine.actionStack = [];
      latestState.battlefield = [{
        id: "persistent-play-target", ownerId: "p2", cardId: persistentTarget.id,
        x: 740, y: 410, faceUp: true, rotation: 0, counters: {},
      }];
      latestState.tokens = [];
      window.__sent = [];
      renderAll();
      const persistentWrap = document.querySelector("#battlefieldWrap").getBoundingClientRect();
      const persistentDropX = persistentWrap.left + persistentWrap.width * .37;
      const persistentDropY = persistentWrap.top + persistentWrap.height * .46;
      document.elementFromPoint = () => document.querySelector("#battlefield");
      resolveDrop({
        kind: "card", cardId: persistentWillId, handIndex: 0,
        cardOwnerId: "p1", fromOwnerId: "p1", fromZone: "hand",
      }, persistentDropX, persistentDropY);
      document.elementFromPoint = realElementFromPoint;
      const persistentPlacement = {
        stage: pendingRulesBoardFlow?.stage,
        sentBeforePayment: window.__sent.length,
      };
      document.querySelector('[data-hand-index="1"]').click();
      persistentPlacement.targetStage = pendingRulesBoardFlow?.stage;
      document.querySelector('[data-item-id="persistent-play-target"]').dispatchEvent(new PointerEvent("pointerdown", {
        bubbles: true, cancelable: true, clientX: 770, clientY: 440,
      }));
      persistentPlacement.payload = window.__sent.find((payload) => payload.type === "declare_rules_action");

      const activatedSourceId = "ufujqhwlpmaw12y_en";
      const sacrificeSourceId = "ng6w09m6mrjq3xc_en";
      const activationTribute = [...cardsById.values()].find((card) => card.type === "manifestation" && Number(card.power) >= 1);
      const activationTarget = [...cardsById.values()].find((card) => card.type === "manifestation" && card.id !== activationTribute.id);
      latestState.players.p1.zones.hand = zone([activationTribute.id]);
      latestState.players.p1.deckDefinition = { main: [activatedSourceId, activationTribute.id] };
      latestState.players.p2.deckDefinition = { main: [activationTarget.id] };
      latestState.phaseTracker.index = ADVANCED_PHASES.findIndex((phase) => phase.id === "confrontation_reaction");
      latestState.rulesEngine.priorityPlayerId = "p1";
      latestState.battlefield = [
        { id: "activated-source", ownerId: "p1", cardId: activatedSourceId, x: 420, y: 560, faceUp: true, rotation: 0, counters: {}, fieldZone: "interzone" },
        { id: "activated-target", ownerId: "p2", cardId: activationTarget.id, x: 760, y: 410, faceUp: true, rotation: 0, counters: {}, isSupport: true },
      ];
      latestState.tokens = [{
        id: "activated-essence", ownerId: "p1", isEssence: true, isNeutralCounter: false,
        temperament: "hollow", counters: { essence: 1 },
      }];
      window.__sent = [];
      renderAll();
      const activateButton = document.querySelector('[data-item-id="activated-source"] .rules-activate-badge');
      const activationButton = {
        visible: Boolean(activateButton),
        size: activateButton ? Math.min(activateButton.getBoundingClientRect().width, activateButton.getBoundingClientRect().height) : 0,
        label: activateButton?.getAttribute("aria-label") || "",
      };
      activateButton.click();
      activationButton.confirmationVisible = !document.querySelector('[data-item-id="activated-source"] .rules-activate-confirm').classList.contains("hidden");
      activationButton.flowBeforeConfirm = pendingRulesBoardFlow;
      document.querySelector('[data-item-id="activated-source"] [data-rules-activate-confirm]').click();
      activationButton.stage = pendingRulesBoardFlow?.stage;
      activationButton.costText = document.querySelector("#rulesFlowCost").textContent.replace(/\s+/g, " ").trim();
      document.querySelector('[data-hand-index="0"]').click();
      activationButton.targetStage = pendingRulesBoardFlow?.stage;
      document.querySelector('[data-item-id="activated-target"]').dispatchEvent(new PointerEvent("pointerdown", {
        bubbles: true, cancelable: true, clientX: 790, clientY: 440,
      }));
      activationButton.payload = window.__sent.find((payload) => payload.type === "declare_rules_action");

      latestState.battlefield[0].rotation = 90;
      renderBattlefield();
      activationButton.hiddenWhenExhausted = !document.querySelector('[data-item-id="activated-source"] .rules-activate-badge');

      latestState.players.p1.zones.hand = zone([]);
      latestState.battlefield = [{
        id: "sacrifice-board-source", ownerId: "p1", cardId: sacrificeSourceId,
        x: 500, y: 560, faceUp: true, rotation: 0, counters: {}, fieldZone: "confrontation",
      }];
      latestState.tokens = [];
      window.__sent = [];
      renderAll();
      const hiddenOutsideInterzone = !document.querySelector('[data-item-id="sacrifice-board-source"] .rules-activate-badge');
      latestState.battlefield[0].fieldZone = "interzone";
      renderBattlefield();
      const sacrificeButton = document.querySelector('[data-item-id="sacrifice-board-source"] .rules-activate-badge');
      sacrificeButton.click();
      const sacrificeFlow = {
        hiddenOutsideInterzone,
        confirmationVisible: !document.querySelector('[data-item-id="sacrifice-board-source"] .rules-activate-confirm').classList.contains("hidden"),
        noFlowBeforeConfirm: pendingRulesBoardFlow === null,
        hoverExplainsEffect: sacrificeButton.title.includes(cardField(cardsById.get(sacrificeSourceId), "effect")),
      };
      document.querySelector('[data-item-id="sacrifice-board-source"] [data-rules-activate-confirm]').click();
      Object.assign(sacrificeFlow, {
        stage: pendingRulesBoardFlow?.stage,
        costText: document.querySelector("#rulesFlowCost").textContent.replace(/\s+/g, " ").trim(),
      });
      submitRulesBoardFlow();
      sacrificeFlow.payload = window.__sent.find((payload) => payload.type === "declare_rules_action");

      const urocioneId = "xf03zroy4tigefr_en";
      const chainManifestation = [...cardsById.values()].find((card) => (
        card.type === "manifestation" && card.id !== urocioneId
      ));
      const chainWillId = willId;
      latestState.players.p1.zones.hand = zone([chainManifestation.id, chainWillId]);
      latestState.battlefield = [{
        id: "chain-source", ownerId: "p1", cardId: urocioneId,
        x: 530, y: 500, faceUp: true, rotation: 0, counters: {},
      }];
      latestState.rulesEngine.pendingChoice = {
        id: "chain-choice", kind: "chain_manifestation", playerId: "p1",
        fromZone: "hand", optional: true, sourceCardId: urocioneId,
      };
      window.__sent = [];
      renderAll();
      const chainWrap = document.querySelector("#battlefieldWrap").getBoundingClientRect();
      const chainFlow = {
        visible: !document.querySelector("#rulesBoardFlow").classList.contains("hidden"),
        modalHidden: document.querySelector("#rulesChoicePanel").classList.contains("hidden"),
        floatingName: document.querySelector("#rulesFloatingCardName").textContent,
        manifestationHighlighted: Boolean(document.querySelector(`[data-hand-card="${chainManifestation.id}"].is-chain-candidate`)),
        willHighlighted: Boolean(document.querySelector(`[data-hand-card="${chainWillId}"].is-chain-candidate`)),
        declineVisible: !document.querySelector("#rulesFlowCancelBtn").classList.contains("hidden"),
        instruction: document.querySelector("#rulesFlowInstruction").textContent,
        instructionFont: Number.parseFloat(getComputedStyle(document.querySelector("#rulesFlowInstruction")).fontSize),
      };
      document.elementFromPoint = () => document.querySelector("#battlefield");
      resolveDrop({
        kind: "card", cardId: chainManifestation.id, handIndex: 0,
        cardOwnerId: "p1", fromOwnerId: "p1", fromZone: "hand",
      }, chainWrap.left + chainWrap.width * .62, chainWrap.top + chainWrap.height * .44);
      document.elementFromPoint = realElementFromPoint;
      chainFlow.payload = window.__sent.find((payload) => payload.type === "resolve_rules_choice");
      chainFlow.closedAfterDrop = document.querySelector("#rulesBoardFlow").classList.contains("hidden");

      window.__sent = [];
      renderAll();
      cancelRulesBoardFlow();
      chainFlow.declinePayload = window.__sent.find((payload) => payload.type === "resolve_rules_choice");
      chainFlow.closedAfterDecline = document.querySelector("#rulesBoardFlow").classList.contains("hidden");
      chainFlow.logs = ["fr", "en", "it"].map((language) => formatLogEntry({
        type: "rules_choice_resolved", actorId: "p1", details: {
          kind: "chain_manifestation", status: "chained", playerId: "p1",
          fromZone: "hand", cardId: chainManifestation.id, sourceCardId: urocioneId,
        },
      }, { language, html: true }));
      latestState.rulesEngine.pendingChoice = null;

      latestState.rulesEngine.enabled = false;
      latestState.rulesEngine.deckConfirmedPlayerIds = [];
      latestState.mode = "casual";
      latestState.phaseTracker = { enabled: false, advanced: false, index: 0, turn: 1, passedPlayerIds: [] };
      latestState.players.p1.deckDefinition = null;
      latestState.players.p2.deckDefinition = null;
      renderRulesPregame();
      const standardSetup = {
        visible: !document.querySelector("#rulesPregamePanel").classList.contains("hidden"),
        importVisible: !document.querySelector("#rulesOpeningHandBtn").classList.contains("hidden"),
        importAction: document.querySelector("#rulesOpeningHandBtn").dataset.action,
        readyHidden: document.querySelector("#rulesPregameReadyBtn").classList.contains("hidden"),
      };
      window.__sent = [];
      document.querySelector("#rulesOpeningHandBtn").click();
      document.querySelector("#starterDeckList [data-import-starter]").click();
      standardSetup.validationVisible = !document.querySelector("#importConfirmBtn").classList.contains("hidden");
      standardSetup.validationEnabled = !document.querySelector("#importConfirmBtn").disabled;
      document.querySelector("#importConfirmBtn").click();
      standardSetup.confirmArmed = document.querySelector("#importConfirmBtn").classList.contains("confirm-armed");
      document.querySelector("#importConfirmBtn").click();
      standardSetup.importPayload = window.__sent.find((payload) => payload.type === "import_deck");
      standardSetup.importPanelClosed = document.querySelector("#importPanel").classList.contains("hidden");
      latestState.players.p1.deckDefinition = { main: [plainManifestation.id] };
      latestState.rulesEngine.deckConfirmedPlayerIds = ["p1"];
      renderRulesPregame();
      standardSetup.waitingAfterOwnValidation = !document.querySelector("#rulesPregamePanel").classList.contains("hidden");
      standardSetup.ownValidatedState = document.querySelector("#rulesPregamePlayers").textContent.includes(t("rulesDeckConfirmedState"));
      latestState.players.p2.deckDefinition = { main: [plainManifestation.id] };
      latestState.rulesEngine.deckConfirmedPlayerIds = ["p1", "p2"];
      renderRulesPregame();
      standardSetup.closedAfterBothValidate = document.querySelector("#rulesPregamePanel").classList.contains("hidden");
      latestState.mode = "tournament";
      latestState.players.p1.deckDefinition = null;
      renderRulesPregame();
      standardSetup.tournamentVisible = !document.querySelector("#rulesPregamePanel").classList.contains("hidden");

      const phaseBeforeInspect = document.querySelector("#phaseTracker").getBoundingClientRect();
      showInspect(plainManifestation.id);
      const inspectRect = document.querySelector("#inspectPanel .box").getBoundingClientRect();
      const inspectDockedLeft = inspectRect.left < window.innerWidth / 3;
      const phaseAfterInspect = document.querySelector("#phaseTracker").getBoundingClientRect();
      const phaseStayedPut = Math.abs(phaseBeforeInspect.left - phaseAfterInspect.left) < 1
        && Math.abs(phaseBeforeInspect.top - phaseAfterInspect.top) < 1;
      document.querySelector("#inspectCloseBtn").click();
      return { payment, targeting, willPayload, closedAfterTarget, manifestationPayload, persistentPlacement, activationButton, sacrificeFlow, chainFlow, standardSetup, inspectDockedLeft, phaseStayedPut };
    });

    assert.equal(innerDesertImport.expectedPoints, 350);
    assert.deepEqual(innerDesertImport.listIds, innerDesertImport.expectedIds);
    assert.deepEqual(innerDesertImport.jsonIds, innerDesertImport.expectedIds);
    assert.deepEqual(innerDesertImport.shareIds, innerDesertImport.expectedIds);
    assert.equal(innerDesertImport.listPoints, 350);
    assert.equal(innerDesertImport.jsonPoints, 350);
    assert.equal(innerDesertImport.sharePoints, 350);
    assert.equal(innerDesertImport.listValidation.valid, true);
    assert.equal(innerDesertImport.flem.name, "Flem");
    assert.equal(innerDesertImport.flem.points, 5);
    assert.equal(innerDesertImport.bob.name, "BOB");
    assert.equal(innerDesertImport.bob.points, 50);
    assert(result.handLabels.includes(result.copyText));
    assert.equal(result.rulesBetaCreate.casualPayload.rulesBeta, true);
    assert.equal(result.rulesBetaCreate.casualPayload.createNew, true);
    assert.equal(result.rulesBetaCreate.tournamentPayload.rulesBeta, true);
    assert.equal(result.rulesBetaCreate.tournamentPayload.createTournament, true);
    assert.equal(result.rulesBetaCreate.insideTournamentLauncher, true);
    assert(result.rulesBetaCreate.label.length > 0);
    assert(result.rulesBetaCreate.hintFontSize >= 14);
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
    assert.equal(wanderingVeteranUi.initial.exists, true);
    assert.equal(wanderingVeteranUi.initial.playable, true);
    assert.equal(wanderingVeteranUi.initial.enabled, "true");
    assert(wanderingVeteranUi.initial.badge.length > 0);
    assert(wanderingVeteranUi.initial.badgeFont >= 14);
    assert.deepEqual(wanderingVeteranUi.dragContext, {
      kind: "card", cardId: wanderingVeteranUi.veteranId, cardOwnerId: "p1",
      fromOwnerId: "p1", fromZone: "graveyard",
    });
    assert.equal(wanderingVeteranUi.waitingState.exists, true);
    assert.equal(wanderingVeteranUi.waitingState.playable, false);
    assert.equal(wanderingVeteranUi.waitingState.enabled, "false");
    assert(wanderingVeteranUi.supportMarker.length > 0);
    assert(wanderingVeteranUi.supportMarkerFont >= 14);
    assert.equal(supportUi.firstStep.forbidden, false);
    assert.equal(supportUi.firstStep.allowed, true);
    assert.equal(supportUi.reactionStep.supportFromHand, true);
    assert.equal(supportUi.reactionStep.ordinary, false);
    assert.deepEqual(supportUi.dragContext, {
      kind: "card", cardId: supportUi.expectedHandSupportId,
      fromOwnerId: "p1", fromZone: "hand",
    });
    assert.equal(supportUi.interzoneStep.printedHasAction, true);
    assert.equal(supportUi.interzoneStep.ordinaryHasAction, false);
    assert.equal(supportUi.marker, "S");
    assert(supportUi.markerFont >= 14);
    assert.equal(supportUi.markerRight, "4px");
    assert.match(supportUi.supportResolutionLog, /Pago/);
    assert.match(supportUi.supportResolutionLog, /10/);
    assert.match(supportUi.supportResolutionLog, /data-log-card/);
    assert.equal(targetedSupportUi.conditionUnlocked, true);
    assert.equal(targetedSupportUi.returnedCopyBlocked, true);
    assert.equal(targetedSupportUi.secondCopyStillPlayable, true);
    assert.deepEqual(targetedSupportUi.offeredTargetIds, ["opponent-support"]);
    assert.equal(targetedSupportUi.ownHighlighted, false);
    assert.equal(targetedSupportUi.opponentHighlighted, true);
    assert.equal(targetedSupportUi.payload.type, "declare_rules_action");
    assert.equal(targetedSupportUi.payload.kind, "play_card");
    assert.equal(targetedSupportUi.payload.asSupport, true);
    assert.deepEqual(targetedSupportUi.payload.targets, [{
      kind: "card", itemId: "opponent-support", cardId: targetedSupportUi.payload.targets[0].cardId,
    }]);
    assert.equal(boardFirstPlay.payment.visible, true);
    assert.equal(boardFirstPlay.payment.stage, "payment");
    assert(boardFirstPlay.payment.floatingName.length > 0);
    assert.match(boardFirstPlay.payment.essenceText, /1/);
    assert.equal(boardFirstPlay.payment.candidateCount, 1);
    assert.equal(boardFirstPlay.payment.sentBeforePayment, 0);
    assert.equal(boardFirstPlay.targeting.stage, "target");
    assert.equal(boardFirstPlay.targeting.paidByDrag, true);
    assert.equal(boardFirstPlay.targeting.highlighted, 1);
    assert.equal(boardFirstPlay.targeting.reticles, 1);
    assert.notEqual(boardFirstPlay.targeting.arrowAnimation, "none");
    assert.match(boardFirstPlay.targeting.arrow, /^M /);
    assert(boardFirstPlay.targeting.instruction.length > 10);
    assert.equal(boardFirstPlay.closedAfterTarget, true);
    assert.equal(boardFirstPlay.targeting.targetLock, 1);
    assert.equal(boardFirstPlay.willPayload.abilityId, "oppress-power-modifier");
    assert.equal(boardFirstPlay.willPayload.paymentCardIds.length, 1);
    assert.deepEqual(boardFirstPlay.willPayload.targets, [{ kind: "card", itemId: "board-flow-target", cardId: boardFirstPlay.willPayload.targets[0].cardId }]);
    assert.equal(boardFirstPlay.manifestationPayload.type, "declare_rules_action");
    assert.equal(boardFirstPlay.manifestationPayload.kind, "play_card");
    assert.equal(boardFirstPlay.manifestationPayload.asSupport, true);
    assert(Number.isFinite(boardFirstPlay.manifestationPayload.placement.x));
    assert(Number.isFinite(boardFirstPlay.manifestationPayload.placement.y));
    assert.equal(boardFirstPlay.persistentPlacement.stage, "payment");
    assert.equal(boardFirstPlay.persistentPlacement.sentBeforePayment, 0);
    assert.equal(boardFirstPlay.persistentPlacement.targetStage, "target");
    assert.equal(boardFirstPlay.persistentPlacement.payload.kind, "play_card");
    assert.deepEqual(boardFirstPlay.persistentPlacement.payload.source, {
      cardId: "y6g3tex9ypttk8u_en", zone: "hand", itemId: null,
    });
    assert(Number.isFinite(boardFirstPlay.persistentPlacement.payload.placement.x));
    assert(Number.isFinite(boardFirstPlay.persistentPlacement.payload.placement.y));
    assert.equal(boardFirstPlay.persistentPlacement.payload.paymentCardIds.length, 1);
    assert.equal(boardFirstPlay.persistentPlacement.payload.abilityId, "flaying-jaw-power-link");
    assert.equal(boardFirstPlay.persistentPlacement.payload.targets[0].itemId, "persistent-play-target");
    assert.equal(boardFirstPlay.activationButton.visible, true);
    assert(boardFirstPlay.activationButton.size >= 38, `Activation target too small: ${boardFirstPlay.activationButton.size}`);
    assert(boardFirstPlay.activationButton.label.length > 8);
    assert.equal(boardFirstPlay.activationButton.confirmationVisible, true);
    assert.equal(boardFirstPlay.activationButton.flowBeforeConfirm, null);
    assert.equal(boardFirstPlay.activationButton.stage, "payment");
    assert.match(boardFirstPlay.activationButton.costText, /source/i);
    assert.equal(boardFirstPlay.activationButton.targetStage, "target");
    assert.deepEqual(boardFirstPlay.activationButton.payload, {
      type: "declare_rules_action",
      label: boardFirstPlay.activationButton.payload.label,
      kind: "activated_effect",
      source: { cardId: "ufujqhwlpmaw12y_en", zone: "battlefield", itemId: "activated-source" },
      target: "",
      targets: [{ kind: "card", itemId: "activated-target", cardId: boardFirstPlay.activationButton.payload.targets[0].cardId }],
      costNote: "", extraEssenceCount: 0,
      paymentCardIds: [boardFirstPlay.activationButton.payload.paymentCardIds[0]],
      abilityId: "ignore-support-power",
    });
    assert.equal(boardFirstPlay.activationButton.hiddenWhenExhausted, true);
    assert.equal(boardFirstPlay.sacrificeFlow.hiddenOutsideInterzone, true);
    assert.equal(boardFirstPlay.sacrificeFlow.confirmationVisible, true);
    assert.equal(boardFirstPlay.sacrificeFlow.noFlowBeforeConfirm, true);
    assert.equal(boardFirstPlay.sacrificeFlow.hoverExplainsEffect, true);
    assert.equal(boardFirstPlay.sacrificeFlow.stage, "committing");
    assert.match(boardFirstPlay.sacrificeFlow.costText, /source/i);
    assert.deepEqual(boardFirstPlay.sacrificeFlow.payload, {
      type: "declare_rules_action",
      label: boardFirstPlay.sacrificeFlow.payload.label,
      kind: "activated_effect",
      source: { cardId: "ng6w09m6mrjq3xc_en", zone: "battlefield", itemId: "sacrifice-board-source" },
      target: "",
      targets: [],
      costNote: "",
      extraEssenceCount: 0,
      paymentCardIds: [],
      abilityId: "sacrifice-field-power-loss",
    });
    assert.equal(boardFirstPlay.chainFlow.visible, true);
    assert.equal(boardFirstPlay.chainFlow.modalHidden, true);
    assert.match(boardFirstPlay.chainFlow.floatingName, /Urocione/i);
    assert.equal(boardFirstPlay.chainFlow.manifestationHighlighted, true);
    assert.equal(boardFirstPlay.chainFlow.willHighlighted, false);
    assert.equal(boardFirstPlay.chainFlow.declineVisible, true);
    assert(boardFirstPlay.chainFlow.instruction.length > 20);
    assert(boardFirstPlay.chainFlow.instructionFont >= 14);
    assert.equal(boardFirstPlay.chainFlow.payload.type, "resolve_rules_choice");
    assert.equal(boardFirstPlay.chainFlow.payload.choiceId, "chain-choice");
    assert.equal(boardFirstPlay.chainFlow.payload.cardIds.length, 1);
    assert(Number.isFinite(boardFirstPlay.chainFlow.payload.placement.x));
    assert(Number.isFinite(boardFirstPlay.chainFlow.payload.placement.y));
    assert.equal(boardFirstPlay.chainFlow.closedAfterDrop, true);
    assert.deepEqual(boardFirstPlay.chainFlow.declinePayload, {
      type: "resolve_rules_choice", choiceId: "chain-choice", option: "decline",
    });
    assert.equal(boardFirstPlay.chainFlow.closedAfterDecline, true);
    assert.match(boardFirstPlay.chainFlow.logs[0], /Enchaîné/);
    assert.match(boardFirstPlay.chainFlow.logs[1], /Chained/);
    assert.match(boardFirstPlay.chainFlow.logs[2], /Concatenato/);
    assert(boardFirstPlay.chainFlow.logs.every((entry) => entry.includes("data-log-card")));
    assert.equal(boardFirstPlay.standardSetup.visible, true);
    assert.equal(boardFirstPlay.standardSetup.importVisible, true);
    assert.equal(boardFirstPlay.standardSetup.importAction, "import");
    assert.equal(boardFirstPlay.standardSetup.readyHidden, true);
    assert.equal(boardFirstPlay.standardSetup.validationVisible, true);
    assert.equal(boardFirstPlay.standardSetup.validationEnabled, true);
    assert.equal(boardFirstPlay.standardSetup.confirmArmed, true);
    assert.equal(boardFirstPlay.standardSetup.importPayload.confirmDeck, true);
    assert.equal(boardFirstPlay.standardSetup.importPanelClosed, true);
    assert.equal(boardFirstPlay.standardSetup.waitingAfterOwnValidation, true);
    assert.equal(boardFirstPlay.standardSetup.ownValidatedState, true);
    assert.equal(boardFirstPlay.standardSetup.closedAfterBothValidate, true);
    assert.equal(boardFirstPlay.standardSetup.tournamentVisible, true);
    assert.equal(boardFirstPlay.inspectDockedLeft, true);
    assert.equal(boardFirstPlay.phaseStayedPut, true);
    assert.equal(rulesStack.visible, true);
    assert.equal(rulesStack.stackItems, 2);
    assert.equal(rulesStack.stackCards, 2);
    assert.equal(rulesStack.stackCardInspected, true);
    assert.equal(new Set(rulesStack.stackPlayerColors).size, 2);
    assert(!rulesStack.topText.includes("Nom français injecté"));
    assert(!rulesStack.topText.includes("Cible française injectée"));
    assert(!rulesStack.topText.includes("Coût français injecté"));
    assert.equal(rulesStack.responseSlotVisible, true);
    assert.equal(rulesStack.responseSlotDotted, true);
    assert.equal(rulesStack.responseButtonState, true);
    assert.equal(rulesStack.responseButtonText, rulesStack.responseButtonExpected);
    assert.equal(rulesStack.resolution.responseSlotVisible, true);
    assert.equal(rulesStack.resolution.highlightedActionId, "action-2");
    assert(rulesStack.resolution.badge.length > 0);
    assert.equal(rulesStack.resolution.buttonState, true);
    assert.equal(rulesStack.resolution.buttonText, rulesStack.resolution.buttonExpected);
    assert.equal(rulesStack.localizedEnglish, rulesStack.expectedEnglish);
    assert.equal(rulesStack.localizedFrench, rulesStack.expectedFrench);
    assert(!rulesStack.localizedEnglish.includes("Nom français injecté"));
    assert(!rulesStack.localizedFrench.includes("Nom français injecté"));
    assert.notEqual(rulesStack.localizedEnglish, rulesStack.localizedFrench);
    assert(rulesStack.priorityText.length > 0);
    assert.equal(rulesStack.passDisabled, false);
    assert(rulesStack.minFont >= 14);
    assert(rulesStack.declaration.contextLabels.includes(rulesStack.declaration.declareActionText));
    assert.equal(rulesStack.declaration.visible, true);
    assert.equal(rulesStack.declaration.kind, "play_card");
    assert.equal(rulesStack.declaration.kindLocked, true);
    assert(rulesStack.declaration.targetChoices >= 1);
    assert.equal(rulesStack.declaration.tributeChoices, 1);
    assert.equal(rulesStack.declaration.tributeSummaryVisible, true);
    assert.equal(rulesStack.declaration.tributeSummaryColumns, 3);
    assert(rulesStack.declaration.tributeSummaryText.length > 0);
    assert(rulesStack.declaration.minFont >= 14, `Undersized declaration text: ${rulesStack.declaration.underSized.join(", ")}`);
    assert.equal(rulesStack.declaration.closedAfterSubmit, true);
    assert.deepEqual(rulesStack.declaration.payload, {
      type: "declare_rules_action",
      label: "Play the test Will",
      kind: "play_card",
      source: { cardId: rulesStack.sourceCardId, zone: "hand", itemId: null },
      target: "During this confrontation",
      targets: [{ kind: "card", itemId: "rules-target-1", cardId: rulesStack.targetCardId }],
      costNote: "One green Tribute",
      paymentCardIds: [rulesStack.tributeCardId],
    });
    assert.equal(rulesStack.encoded.visible, true);
    assert.equal(rulesStack.encoded.kind, "activated_effect");
    assert.equal(rulesStack.encoded.kindLocked, true);
    assert(rulesStack.encoded.meta.includes(rulesStack.encoded.expectedMeta));
    assert.equal(rulesStack.encoded.targetType, "radio");
    assert.equal(rulesStack.encoded.tributeSummaryVisible, true);
    assert(rulesStack.encoded.tributeSummaryText.length > 0);
    assert(rulesStack.encoded.warning.length > 0);
    assert.deepEqual(rulesStack.encoded.payload, {
      type: "declare_rules_action",
      label: "Use encoded effect",
      kind: "activated_effect",
      source: { cardId: rulesStack.encoded.cardId, zone: "battlefield", itemId: "encoded-source-1" },
      target: "",
      targets: [{ kind: "card", itemId: "rules-target-1", cardId: rulesStack.targetCardId }],
      costNote: "",
      paymentCardIds: [],
      abilityId: "ignore-support-power",
    });
    assert.match(rulesStack.sacrifice.meta, new RegExp(rulesStack.sacrifice.expectedMeta));
    assert.equal(rulesStack.sacrifice.targetChoices, 0);
    assert.equal(rulesStack.sacrifice.targetText, rulesStack.sacrifice.expectedTargetText);
    assert.deepEqual(rulesStack.sacrifice.payload, {
      type: "declare_rules_action",
      label: "Sacrifice Pimbo",
      kind: "activated_effect",
      source: { cardId: rulesStack.sacrifice.cardId, zone: "battlefield", itemId: "sacrifice-source-1" },
      target: "",
      targets: [],
      costNote: "",
      paymentCardIds: [],
      abilityId: "sacrifice-field-power-loss",
    });
    assert.equal(rulesStack.playedAbility.visible, true);
    assert.equal(rulesStack.playedAbility.kind, "play_card");
    assert.equal(rulesStack.playedAbility.kindLocked, true);
    assert.equal(rulesStack.playedAbility.targetType, "radio");
    assert(rulesStack.playedAbility.tributeChoices >= 1);
    assert(rulesStack.playedAbility.tributeSummaryText.length > 0);
    assert.deepEqual(rulesStack.playedAbility.payload, {
      type: "declare_rules_action",
      label: "Strengthen target",
      kind: "play_card",
      source: { cardId: rulesStack.playedAbility.cardId, zone: "hand", itemId: null },
      target: "",
      targets: [{ kind: "card", itemId: "rules-target-1", cardId: rulesStack.targetCardId }],
      costNote: "",
      paymentCardIds: [rulesStack.playedAbility.tributeCardId],
      abilityId: "strengthen-power-modifier",
    });
    assert.equal(rulesStack.drawAbility.targetChoices, 0);
    assert.equal(rulesStack.drawAbility.noTargetText, rulesStack.drawAbility.expectedNoTargetText);
    assert.equal(rulesStack.drawAbility.warning, rulesStack.drawAbility.expectedWarning);
    assert.deepEqual(rulesStack.drawAbility.payload, {
      type: "declare_rules_action",
      label: "Ponder",
      kind: "play_card",
      source: { cardId: rulesStack.drawAbility.cardId, zone: "hand", itemId: null },
      target: "",
      targets: [],
      costNote: "",
      paymentCardIds: [rulesStack.drawAbility.tributeCardId],
      abilityId: "draw-three-cards",
    });
    assert.equal(rulesStack.conditionalDrawAbility.targetChoices, 0);
    assert.equal(rulesStack.conditionalDrawAbility.noTargetText, rulesStack.conditionalDrawAbility.expectedNoTargetText);
    assert.deepEqual(rulesStack.conditionalDrawAbility.payload, {
      type: "declare_rules_action",
      label: "Pray the Ether",
      kind: "play_card",
      source: { cardId: rulesStack.conditionalDrawAbility.cardId, zone: "hand", itemId: null },
      target: "",
      targets: [],
      costNote: "",
      paymentCardIds: [],
      abilityId: "discard-one-then-draw-two",
    });
    assert.equal(rulesStack.moveAbility.visible, true);
    assert.equal(rulesStack.moveAbility.targetAvailable, true);
    assert.equal(rulesStack.moveAbility.targetType, "radio");
    assert.equal(rulesStack.moveAbility.tributeChoices, 2);
    assert.equal(rulesStack.moveAbility.warning, rulesStack.moveAbility.expectedWarning);
    assert.deepEqual(rulesStack.moveAbility.payload, {
      type: "declare_rules_action",
      label: "Defer target",
      kind: "play_card",
      source: { cardId: rulesStack.moveAbility.cardId, zone: "hand", itemId: null },
      target: "",
      targets: [{ kind: "card", itemId: "defer-persistent-target", cardId: rulesStack.moveAbility.targetCardId }],
      costNote: "",
      paymentCardIds: rulesStack.moveAbility.payload.paymentCardIds,
      abilityId: "defer-to-deck-top",
    });
    assert.equal(rulesStack.moveAbility.payload.paymentCardIds.length, 2);
    assert.equal(rulesStack.exileAbility.targetAvailable, true);
    assert.match(rulesStack.exileAbility.targetLabel, /P2/);
    assert.deepEqual(rulesStack.exileAbility.payload, {
      type: "declare_rules_action",
      label: "Exile from Limbo",
      kind: "play_card",
      source: { cardId: rulesStack.exileAbility.cardId, zone: "hand", itemId: null },
      target: "",
      targets: [{
        kind: "zone_card", containerId: "p2", zone: "graveyard",
        cardId: rulesStack.exileAbility.targetCardId,
      }],
      costNote: "",
      paymentCardIds: rulesStack.exileAbility.payload.paymentCardIds,
      abilityId: "exile-manifestation",
    });
    assert.equal(rulesStack.exileAbility.payload.paymentCardIds.length, 4);
    assert.equal(rulesStack.destroyAbility.targetAvailable, true);
    assert.equal(rulesStack.destroyAbility.tooValuableAvailable, false);
    assert.deepEqual(rulesStack.destroyAbility.payload, {
      type: "declare_rules_action",
      label: "Disfigure target",
      kind: "play_card",
      source: { cardId: rulesStack.destroyAbility.cardId, zone: "hand", itemId: null },
      target: "",
      targets: [{
        kind: "zone_card", containerId: "p2", zone: "receptacle",
        cardId: rulesStack.destroyAbility.targetCardId,
      }],
      costNote: "",
      paymentCardIds: rulesStack.destroyAbility.payload.paymentCardIds,
      abilityId: "disfigure-destroy-manifestation",
    });
    assert.equal(rulesStack.destroyAbility.payload.paymentCardIds.length, 2);
    assert.equal(rulesStack.randomDestroyAbility.playerChoices, 2);
    assert.equal(rulesStack.randomDestroyAbility.targetAvailable, true);
    assert.equal(rulesStack.randomDestroyAbility.playerMark, "P");
    assert.deepEqual(rulesStack.randomDestroyAbility.payload, {
      type: "declare_rules_action",
      label: "Remove by Chance",
      kind: "play_card",
      source: { cardId: rulesStack.randomDestroyAbility.cardId, zone: "hand", itemId: null },
      target: "",
      targets: [{ kind: "player", playerId: "p2" }],
      costNote: "",
      paymentCardIds: rulesStack.randomDestroyAbility.payload.paymentCardIds,
      abilityId: "destroy-random-vessel-manifestation",
    });
    assert.equal(rulesStack.randomDestroyAbility.payload.paymentCardIds.length, 3);
    assert.equal(rulesStack.eliminateAbility.targetAvailable, true);
    assert.equal(rulesStack.eliminateAbility.battlefieldTargets, 0);
    assert.deepEqual(rulesStack.eliminateAbility.payload, {
      type: "declare_rules_action",
      label: "Eliminate the Profane",
      kind: "play_card",
      source: { cardId: rulesStack.eliminateAbility.cardId, zone: "hand", itemId: null },
      target: "",
      targets: [{
        kind: "zone_card", containerId: "p2", zone: "receptacle",
        cardId: rulesStack.eliminateAbility.targetCardId,
      }],
      costNote: "",
      paymentCardIds: rulesStack.eliminateAbility.payload.paymentCardIds,
      abilityId: "destroy-vessel-manifestation",
    });
    assert.equal(rulesStack.eliminateAbility.payload.paymentCardIds.length, 4);
    assert(rulesStack.sent.some((payload) => payload.type === "pass_priority" && payload.passed === true));
    assert.equal(rulesStack.cancelPass.visible, true);
    assert.equal(rulesStack.cancelPass.passedStyle, true);
    assert.deepEqual(rulesStack.cancelPass.payload, { type: "pass_priority", passed: false });
    assert.equal(rulesStack.disabledWithoutPriority, true);
    assert.equal(stackNeutralize.playableWithTarget, true);
    assert.equal(stackNeutralize.playableWithoutTarget, false);
    assert.equal(stackNeutralize.began, true);
    assert.equal(stackNeutralize.stage, "target");
    assert.equal(stackNeutralize.highlighted, true);
    assert(stackNeutralize.legend.length > 0);
    assert.deepEqual(stackNeutralize.payload, {
      type: "declare_rules_action",
      label: stackNeutralize.expectedLabel,
      kind: "play_card",
      source: { cardId: stackNeutralize.neutralizeCardId, zone: "hand", itemId: null },
      target: "",
      targets: [{
        kind: "stack_action", actionId: stackNeutralize.targetActionId,
        cardId: rulesStack.sourceCardId,
      }],
      costNote: "", extraEssenceCount: 0,
      paymentCardIds: [],
      abilityId: "neutralize-stack-card",
    });
    assert.equal(conditionalStackPayment.denyPlayable, true);
    assert.equal(conditionalStackPayment.ignorePlayable, true);
    assert.deepEqual(conditionalStackPayment.denyDraftKinds, ["stack_action"]);
    assert.deepEqual(conditionalStackPayment.ignoreDraftKinds, ["stack_effect"]);
    assert.deepEqual(conditionalStackPayment.denyPayload.targets, [{
      kind: "stack_action", actionId: conditionalStackPayment.cardActionId,
      cardId: conditionalStackPayment.denyPayload.targets[0].cardId,
    }]);
    assert.equal(conditionalStackPayment.denyPayload.abilityId, "deny-stack-card-unless-paid");
    assert.deepEqual(conditionalStackPayment.ignorePayload.targets, [{
      kind: "stack_effect", actionId: conditionalStackPayment.effectActionId,
      cardId: conditionalStackPayment.ignorePayload.targets[0].cardId,
    }]);
    assert.equal(conditionalStackPayment.ignorePayload.abilityId, "ignore-stack-effect-unless-paid");
    assert.equal(conditionalStackPayment.paymentInitial.visible, true);
    assert.equal(conditionalStackPayment.paymentInitial.modalHidden, true);
    assert.equal(conditionalStackPayment.paymentInitial.actionsVisible, true);
    assert.equal(conditionalStackPayment.paymentInitial.payDisabled, true);
    assert.equal(conditionalStackPayment.paymentInitial.candidate, true);
    assert.equal(conditionalStackPayment.paymentInitial.targetMarked, true);
    assert(conditionalStackPayment.paymentInitial.pendingLabel.length > 0);
    assert(conditionalStackPayment.paymentInitial.instruction.length > 0);
    assert(conditionalStackPayment.paymentInitial.minFont >= 14);
    assert.equal(conditionalStackPayment.payEnabledAfterSelection, true);
    assert.deepEqual(conditionalStackPayment.payPayload, {
      type: "resolve_rules_choice", choiceId: "stack-payment-pay", option: "pay",
      cardIds: [conditionalStackPayment.paymentCardId],
    });
    assert.deepEqual(conditionalStackPayment.declinePayload, {
      type: "resolve_rules_choice", choiceId: "stack-payment-decline", option: "decline",
      cardIds: [],
    });
    assert.equal(stackCopy.initial.visible, true);
    assert.equal(stackCopy.initial.modalHidden, true);
    assert.equal(stackCopy.initial.actionsVisible, true);
    assert.equal(stackCopy.initial.payHidden, true);
    assert.deepEqual(stackCopy.initial.candidateIds, ["imitate-target-1", "imitate-target-2"]);
    assert(stackCopy.initial.keepLabel.length > 0);
    assert(stackCopy.initial.instruction.length > 0);
    assert(stackCopy.initial.copyBadge.length > 0);
    assert.deepEqual(stackCopy.retargetPayload, {
      type: "resolve_rules_choice", choiceId: "stack-copy-retarget", option: "retarget",
      targets: [{ kind: "card", itemId: "imitate-target-2", cardId: stackCopy.secondCardId }],
    });
    assert.deepEqual(stackCopy.keepPayload, {
      type: "resolve_rules_choice", choiceId: "stack-copy-keep", option: "keep", targets: [],
    });
    assert.match(stackCopy.logHtml, /log-card-ref/);
    assert.equal(pregameUi.initial.panelVisible, true);
    assert.equal(pregameUi.initial.panelProminent, true);
    assert.equal(pregameUi.initial.openingHidden, true);
    assert.equal(pregameUi.initial.mulliganEnabled, true);
    assert.equal(pregameUi.initial.mulliganVisible, true);
    assert.equal(pregameUi.initial.readyHidden, true);
    assert.match(pregameUi.initial.title, /mulligan/i);
    assert.match(pregameUi.initial.hint, /Manifestation/i);
    assert.equal(pregameUi.initial.attentionCount, 1);
    assert.equal(pregameUi.initial.panelFitsViewport, true);
    assert(pregameUi.initial.titleFontSize >= 28);
    assert(pregameUi.initial.hintFontSize >= 16);
    assert(pregameUi.initial.mulliganFontSize >= 14);
    assert.equal(pregameUi.initial.phaseHidden, false);
    assert.equal(pregameUi.initial.stackHidden, true);
    assert.equal(pregameUi.initial.opponentSlots, 3);
    assert.equal(pregameUi.initial.leakedOpponentIds, 0);
    assert.equal(pregameUi.initial.toolsHidden, true);
    assert.equal(pregameUi.initial.toolsOpen, true);
    assert.equal(pregameUi.initial.handVisible, true);
    assert.equal(pregameUi.initial.handCards, 1);
    assert.equal(pregameUi.initial.waitingButton.visible, false);
    assert.equal(pregameUi.initial.waitingButton.disabled, true);
    assert.deepEqual(pregameUi.initial.mulliganPayload, { type: "mulligan" });
    assert.equal(pregameUi.initial.afterMulligan.panelVisible, true);
    assert.equal(pregameUi.initial.afterMulligan.mulliganHidden, true);
    assert.equal(pregameUi.initial.afterMulligan.keepVisible, true);
    assert.match(pregameUi.initial.afterMulligan.keepText, /garder|keep|tieni/i);
    assert.deepEqual(pregameUi.initial.afterMulligan.keepPayload, { type: "set_rules_ready" });
    assert.equal(pregameUi.initial.panelClosedAfterValidMulligan, true);
    assert.equal(pregameUi.voluntaryMulligan.keepVisible, true);
    assert.equal(pregameUi.voluntaryMulligan.mulliganVisible, true);
    assert.equal(pregameUi.voluntaryMulligan.twoActions, 2);
    assert.match(pregameUi.voluntaryMulligan.keepText, /garder|keep|tieni/i);
    assert.match(pregameUi.voluntaryMulligan.mulliganText, /10/);
    assert.match(pregameUi.voluntaryMulligan.confirmText, /10/);
    assert.deepEqual(pregameUi.voluntaryMulligan.payload, { type: "mulligan" });
    assert.equal(pregameUi.recoveryMulligan.panelVisible, true);
    assert.equal(pregameUi.recoveryMulligan.panelProminent, true);
    assert.match(pregameUi.recoveryMulligan.title, /recovery|mulligan/i);
    assert.match(pregameUi.recoveryMulligan.hint, /aucun point|no points/i);
    assert.match(pregameUi.recoveryMulligan.action, /mulligan/i);
    assert.match(pregameUi.recoveryMulligan.confirmText, /aucun point|no points/i);
    assert.equal(pregameUi.recoveryMulligan.readyHidden, true);
    assert.equal(pregameUi.recoveryMulligan.playableCardCount, 0);
    assert.deepEqual(pregameUi.recoveryMulligan.payload, { type: "mulligan" });
    assert.equal(pregameUi.requestedUx.openingActions[0].id, "rulesOpeningHandBtn");
    assert.match(pregameUi.requestedUx.openingActions[0].text, /import/i);
    assert.equal(pregameUi.requestedUx.openingActions.at(-1).id, "rulesPregameReadyBtn");
    assert.equal(pregameUi.requestedUx.openingActions.at(-1).glow, true);
    assert.equal(pregameUi.requestedUx.emptyHandButtons, 0);
    assert(pregameUi.requestedUx.phaseMain.length > 0);
    assert(pregameUi.requestedUx.phaseStep.length > 0);
    assert.equal(pregameUi.requestedUx.stagedDeckVisible, true);
    assert.match(pregameUi.requestedUx.stagedDeckText, /30/);
    assert.equal(pregameUi.requestedUx.importPayload.type, "import_deck");
    assert.equal(pregameUi.requestedUx.importPayload.confirmDeck, false);
    assert.equal(pregameUi.requestedUx.importPanelStayedOpen, true);
    assert.equal(pregameUi.requestedUx.confirmArmed, true);
    assert.match(pregameUi.requestedUx.confirmText, /\?/);
    assert.equal(pregameUi.requestedUx.sentBeforeConfirmation, false);
    assert.equal(pregameUi.requestedUx.confirmDisarmedOutside, true);
    assert.equal(pregameUi.requestedUx.confirmPayload.type, "import_deck");
    assert.equal(pregameUi.requestedUx.confirmPayload.confirmDeck, true);
    assert.equal(pregameUi.requestedUx.importPanelClosedAfterConfirm, true);
    assert.deepEqual(pregameUi.requestedUx.firstValidatePayload, { type: "validate_first_manifestation", validated: true });
    assert.deepEqual(pregameUi.requestedUx.firstCancelPayload, { type: "validate_first_manifestation", validated: false });
    assert.equal(pregameUi.requestedUx.firstOpponentGlow, true);
    assert.deepEqual(pregameUi.requestedUx.pointerEvents, {
      area: "none", tray: "none", card: "auto", handle: "auto",
    });
    assert.equal(pregameUi.requestedUx.handResizeDelta, 40);
    assert.equal(pregameUi.deckEditSummary.heading, "Modifier le deck");
    assert.equal(pregameUi.deckEditSummary.panelVisible, true);
    assert.match(pregameUi.deckEditSummary.text, /Current test deck/);
    assert.match(pregameUi.deckEditSummary.text, /30 cartes/);
    assert.match(pregameUi.deckEditSummary.text, /Sideboard · 1\/6/);
    assert.equal(pregameUi.unaffordableAura, false);
    assert.equal(pregameUi.playableAura, true);
    assert.equal(pregameUi.essenceStripShown, true);
    assert.equal(pregameUi.essenceStripText, "20");
    assert.equal(pregameUi.essenceStripBesideToggle, true);
    assert.equal(pregameUi.essenceStripHiddenWhenEmpty, true);
    assert.equal(pregameUi.hoverFullyVisible, true);
    assert.equal(pregameUi.supportKeywordPlayableFromHand, true);
    assert.equal(rulesChoice.targetStep.visible, true);
    assert.equal(rulesChoice.targetStep.playerChoices, 2);
    assert.equal(rulesChoice.targetStep.placementSentBeforeChoice, false);
    assert(rulesChoice.targetStep.minFont >= 14);
    assert.equal(rulesChoice.targetStep.payload.source.cardId, rulesChoice.darkApparitionId);
    assert.deepEqual(rulesChoice.targetStep.payload.targets, [{ kind: "player", playerId: "p2" }]);
    assert.equal(rulesChoice.discardStep.visible, true);
    assert.equal(rulesChoice.discardStep.closeHidden, true);
    assert.equal(rulesChoice.discardStep.cardChoices, 2);
    assert.match(rulesChoice.discardStep.priorityText, /P1/);
    assert.equal(rulesChoice.discardStep.passHidden, true);
    assert.deepEqual(rulesChoice.discardStep.payload, {
      type: "resolve_rules_choice", choiceId: "choice-1", cardIds: [rulesChoice.discardCardId],
    });
    assert.match(rulesChoice.conditionalStep.text, /2/);
    assert.equal(rulesChoice.multiDiscardStep.confirmEnabledBeforePick, true);
    assert.equal(rulesChoice.multiDiscardStep.selectedCount, 2);
    assert.equal(rulesChoice.multiDiscardStep.payload.choiceId, "choice-multi");
    assert.equal(rulesChoice.multiDiscardStep.payload.cardIds.length, 2);
    assert.deepEqual(rulesChoice.conditionalStep.payload, {
      type: "resolve_rules_choice", choiceId: "choice-2", cardIds: [rulesChoice.darkApparitionId],
    });
    assert.equal(rulesChoice.recoveryStep.visible, true);
    assert.equal(rulesChoice.recoveryStep.choices, 2);
    assert.match(rulesChoice.recoveryStep.text, /every player|chaque joueur|ogni giocatore/i);
    assert(rulesChoice.recoveryStep.minFont >= 14);
    assert.deepEqual(rulesChoice.recoveryStep.payload, {
      type: "resolve_rules_choice", choiceId: "choice-recovery", option: "discard_deck_bottom_3",
    });
    assert.equal(rulesChoice.comparison.visible, true);
    assert.match(rulesChoice.comparison.text, /P1 7/);
    assert.match(rulesChoice.comparison.text, /P2 4/);
    assert.equal(rulesChoice.destinationStep.visible, true);
    assert.equal(rulesChoice.destinationStep.choices, 2);
    assert.equal(rulesChoice.destinationStep.cardVisible, true);
    assert.equal(rulesChoice.destinationStep.dropHighlighted, true);
    assert(rulesChoice.destinationStep.minFont >= 14);
    assert.deepEqual(rulesChoice.destinationStep.payload, {
      type: "resolve_rules_choice", choiceId: "choice-destination", option: "interzone",
    });
    assert.equal(rulesChoice.replacementStep.fieldZoneMarker, true);
    assert.deepEqual(rulesChoice.replacementStep.payload, {
      type: "resolve_rules_choice", choiceId: "choice-replace", itemId: rulesChoice.replacementStep.expectedItemId,
    });
    assert.equal(rulesVfx.initialReplayCount, 0);
    assert.equal(rulesVfx.pluffEncoded, true);
    assert(rulesVfx.declared.essence >= 2, JSON.stringify(rulesVfx));
    assert.equal(rulesVfx.declared.tribute, 1);
    assert.equal(rulesVfx.declared.exhaust, 1);
    assert(rulesVfx.declared.impact.length > 0);
    assert(rulesVfx.declared.exhaustLabel.length > 0);
    assert(rulesVfx.declared.minFont >= 14);
    assert.equal(rulesVfx.sacrifice.flight, 1);
    assert(rulesVfx.sacrifice.label.length > 0);
    assert(rulesVfx.triggered.length > 0);
    assert.equal(rulesVfx.triggeredPulse, 1);
    assert(rulesVfx.resolved.length > 0);
    assert.equal(rulesVfx.resolvedPulse, 1);
    assert.equal(rulesVfx.score, "+20");
    assert.match(rulesVfx.draw, /1/);
    assert.equal(rulesVfx.scoreLoss, "-20");
    assert(rulesVfx.discarded.length > 0);
    assert.match(rulesVfx.drawAfterDiscard, /2/);
    assert.equal(rulesVfx.moved.flight, 1);
    assert.equal(rulesVfx.moved.glint, 1);
    assert(rulesVfx.moved.label.length > 0);
    assert.equal(rulesVfx.exiled.flight, 1);
    assert.equal(rulesVfx.exiled.label, rulesVfx.exiled.expectedLabel);
    assert.equal(rulesVfx.destroyed.flight, 1);
    assert.equal(rulesVfx.destroyed.shards, 5);
    assert(rulesVfx.destroyed.burst >= 1);
    assert.equal(rulesVfx.destroyed.label, rulesVfx.destroyed.expectedLabel);
    assert.equal(rulesVfx.noEligible.label, rulesVfx.noEligible.expectedLabel);
    assert.equal(rulesVfx.deckDiscard.flight, 1);
    assert.equal(rulesVfx.deckDiscard.label, rulesVfx.deckDiscard.expectedLabel);
    assert.equal(rulesVfx.supportWin.flight, 1);
    assert.equal(rulesVfx.supportWin.score, "+10");
    assert.equal(rulesVfx.remaining, 0);
    assert.equal(rulesLayout.horizontalOverflow, 0);
    assert.equal(rulesLayout.chatOverlapArea, 0);
    assert.equal(rulesLayout.inspectorOverlapArea, 0);
    assert.equal(rulesLayout.inspectorClearsToolbar, true);
    assert.equal(rulesLayout.inspectButtonInLeftToolbar, true);
    assert.equal(rulesLayout.phaseDetailsHidden, false);
    assert.equal(rulesLayout.phaseOrbCount, 4);
    assert(rulesLayout.phaseBottomGap <= 40, JSON.stringify(rulesLayout));
    assert(rulesLayout.phaseRightGap <= 24, JSON.stringify(rulesLayout));
    assert.equal(rulesLayout.phaseBackground, "rgba(0, 0, 0, 0)");
    assert.equal(rulesLayout.stackAbovePhase, true, JSON.stringify(rulesLayout));
    assert.match(rulesLayout.turnContext, /2|Turn|Tour|Turno/);
    assert(rulesLayout.emptyHeight <= 58, JSON.stringify(rulesLayout));
    assert.equal(rulesLayout.emptyBodyHidden, true);
    assert.equal(ongoingEffect.marked, true);
    assert.equal(ongoingEffect.frameRemoved, true);
    assert.equal(ongoingEffect.badgeCount, "");
    assert(ongoingEffect.badgeLabel.length > 20);
    assert.equal(ongoingEffect.tempPowerMarker, "-2");
    assert.equal(ongoingEffect.temporaryLinkCount, 0);
    assert.equal(ongoingEffect.linkCount, 1);
    assert.equal(ongoingEffect.highlighted, true);
    assert.notEqual(ongoingEffect.flowAnimation, "none");
    assert.equal(ongoingEffect.bindPathCount, 1);
    assert.equal(ongoingEffect.sealCount, 1);
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
    assert(tournament.drawResolutionLogs.every((entry) => entry.includes("P1")));
    assert.match(tournament.drawResolutionLogs[0], /pioché une carte/);
    assert.match(tournament.drawResolutionLogs[1], /drew one card/);
    assert.match(tournament.drawResolutionLogs[2], /pescato una carta/);
    assert.match(tournament.resolvedCardHoverLog, /data-log-card=/);
    assert.match(tournament.scoreLossLogs[0], /perdu 20/);
    assert.match(tournament.scoreLossLogs[1], /lost 20/);
    assert.match(tournament.scoreLossLogs[2], /perso 20/);
    assert.match(tournament.choiceResolutionLogs[0], /défaussé 1/);
    assert.match(tournament.choiceResolutionLogs[1], /discarded 1/);
    assert.match(tournament.choiceResolutionLogs[2], /scartato 1/);
    assert.match(tournament.targetTriggerLogs[0], /Cible : P2/);
    assert.match(tournament.targetTriggerLogs[1], /Target: P2/);
    assert.match(tournament.targetTriggerLogs[2], /Bersaglio: P2/);
    assert.match(tournament.moveResolutionLogs[0], /dessus/);
    assert.match(tournament.moveResolutionLogs[1], /top/);
    assert.match(tournament.moveResolutionLogs[2], /cima/);
    assert.match(tournament.publicZoneTargetLogs[0], /P2 · Limbo/);
    assert.match(tournament.publicZoneTargetLogs[1], /P2 · Limbo/);
    assert.match(tournament.publicZoneTargetLogs[2], /P2 · Limbo/);
    assert.match(tournament.destroyResolutionLogs[0], /détruite/);
    assert.match(tournament.destroyResolutionLogs[1], /destroyed/);
    assert.match(tournament.destroyResolutionLogs[2], /distrutta/);
    assert.match(tournament.noEligibleLogs[0], /aucune carte éligible/i);
    assert.match(tournament.noEligibleLogs[1], /no eligible card/i);
    assert.match(tournament.noEligibleLogs[2], /carte idonee/i);
    assert.match(tournament.deckDiscardLogs[0], /dessus de son Deck/);
    assert.match(tournament.deckDiscardLogs[1], /top of their Deck/);
    assert.match(tournament.deckDiscardLogs[2], /cima del proprio Mazzo/);
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
