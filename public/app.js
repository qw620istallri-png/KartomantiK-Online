const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const ZONES = ["deck", "hand", "graveyard", "exile", "receptacle"];
const PRIVATE_ZONES = new Set(["deck", "hand"]);
// picked to contrast against the board's dark navy background (#0b1e3a)
const PLAYER_COLORS = ["#d3654a", "#3fc9a8", "#8bbf4f", "#b06fd6", "#d98a2b", "#4fa3d9"];

// the 7 temperaments, their real card-art ink colour and their symbol image
const TEMPERAMENTS = [
  { key: "capricious", ink: "#aa8e33" },
  { key: "choleric", ink: "#a94b43" },
  { key: "hollow", ink: "#5f6266" },
  { key: "melancholic", ink: "#725482" },
  { key: "phlegmatic", ink: "#4f7655" },
  { key: "transcendent", ink: "#a86975" },
  { key: "vitreous", ink: "#3f6f99" },
];
function temperamentInk(key) {
  return TEMPERAMENTS.find((t2) => t2.key === key)?.ink || "#6b5b2f";
}
function temperamentSymbol(key) {
  return `temperaments/${key}.png`;
}
function tokenCardFaceHtml(item) {
  return `<div class="token-card-face">
    <img src="${esc(temperamentSymbol(item.temperament))}" alt="${esc(t("temperament" + item.temperament[0].toUpperCase() + item.temperament.slice(1)))}">
    <span class="token-card-name">${esc(t("token"))}</span>
    <span class="token-card-power">${item.power > 0 ? "+" : ""}${item.power}</span>
  </div>`;
}

const DECK_LIBRARY_KEY = "ko_deck_library";

let ws = null;
let cardsById = new Map();
let cardsByNumber = new Map();
let starterDecks = [];
let clientId = localStorage.getItem("ko_clientId");
if (!clientId) {
  clientId = (crypto.randomUUID ? crypto.randomUUID() : String(Math.random())).replace(/-/g, "").slice(0, 24);
  localStorage.setItem("ko_clientId", clientId);
}

let myPlayerId = null;
let isObserver = false;
let codePlayer = null;
let codeObserver = null;
let joinedCode = null;
let joinedName = null;
let latestState = null;
let colorByPlayer = new Map();
const revealedHandCards = new Map(); // playerId -> Set(cardId) ever revealed from their hand, for the hand-view popup
let pendingIncomingRequest = null; // the hand_action_request currently shown in #handRequestPanel
let expanded = new Set(); // "ownerId:zone" currently expanded in the UI
let reconnectTimer = null;
let intentionalClose = false;

function playerColor(playerId) {
  if (!colorByPlayer.has(playerId)) {
    colorByPlayer.set(playerId, PLAYER_COLORS[colorByPlayer.size % PLAYER_COLORS.length]);
  }
  return colorByPlayer.get(playerId);
}

function cardName(cardId) {
  const card = cardsById.get(cardId);
  return card ? card.name : cardId || "Unknown card";
}
function cardImage(cardId) {
  const card = cardsById.get(cardId);
  return card ? card.image : "";
}

async function loadCardDatabase() {
  try {
    const res = await fetch("cards-data.json");
    const list = await res.json();
    cardsById = new Map(list.map((c) => [c.id, c]));
    cardsByNumber = new Map(list.map((c) => [Number(c.collectionNumber), c]));
  } catch (e) {
    console.error("Failed to load card database", e);
  }
}

async function loadStarterDecks() {
  try {
    const res = await fetch("starter-decks.json");
    starterDecks = await res.json();
  } catch (e) {
    console.error("Failed to load starter decks", e);
    starterDecks = [];
  }
}

// ---------------------------------------------------------------- deck import parsing + local library

function parseDeckListText(text) {
  const groups = [];
  let current = null;
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || /^DECKOMANTIK LIST/i.test(line) || /^\[Deck\]/i.test(line)) continue;
    const catMatch = line.match(/^\[Category(?::([a-zA-Z]+))?\]/i);
    if (catMatch) {
      current = { kind: (catMatch[1] || "").toLowerCase() || null, cardIds: [] };
      groups.push(current);
      continue;
    }
    const cardMatch = line.match(/^#?(\d+)\b/);
    if (cardMatch) {
      const card = cardsByNumber.get(Number(cardMatch[1]));
      if (card) {
        if (!current) { current = { kind: null, cardIds: [] }; groups.push(current); }
        current.cardIds.push(card.id);
      }
    }
  }
  return { app: "DeckomantiK", groups };
}

// DeckomantiK's own "share via URL" feature (#dk=<base64url(gzip(JSON))>,
// format v2) — decoded here with the exact same encoding it was written with
// (native CompressionStream/DecompressionStream gzip, no library), so a
// player can paste that link straight in instead of a whole JSON export.
// This never talks to DeckomantiK's origin at all: the token is fully
// self-contained, so there's no cross-origin request and nothing to be
// blocked by (reading DeckomantiK's actual localStorage from here would be
// blocked — different origin — but decoding a token the user pasted isn't
// storage access, just parsing a string).
function extractShareToken(text) {
  const hashMatch = text.match(/#dk=([A-Za-z0-9_-]+)/);
  if (hashMatch) return hashMatch[1];
  return /^[A-Za-z0-9_-]{20,}$/.test(text.trim()) ? text.trim() : null;
}

async function decodeDkShare(token) {
  try {
    const base64 = token.replace(/-/g, "+").replace(/_/g, "/");
    const binary = atob(base64);
    const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
    let jsonBytes = bytes;
    if (typeof DecompressionStream !== "undefined") {
      const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
      jsonBytes = new Uint8Array(await new Response(stream).arrayBuffer());
    }
    const payload = JSON.parse(new TextDecoder().decode(jsonBytes));
    return payload && payload.v === 2 && (payload.d || payload.b) ? payload : null;
  } catch (e) {
    return null;
  }
}

// DeckomantiK's card index is the array position in ITS OWN card list, which
// is ordered by collectionNumber starting at 1 with no gaps (index =
// collectionNumber - 1) — resolving through our own cardsByNumber map (keyed
// the same way) sidesteps any risk of the two apps' card-id strings differing.
function expandDkShareDeck(d) {
  const groups = (d.g || []).map((g) => ({
    kind: g.k || null,
    cardIds: (g.c || []).map((index) => cardsByNumber.get(index + 1)?.id).filter(Boolean),
  }));
  return { app: "DeckomantiK", name: d.n, groups };
}

function getDeckLibrary() {
  try { return JSON.parse(localStorage.getItem(DECK_LIBRARY_KEY)) || []; } catch (e) { return []; }
}

function saveDeckToLibrary(name, deck) {
  const list = getDeckLibrary().filter((entry) => entry.name !== name);
  list.unshift({ name, deck, savedAt: Date.now() });
  localStorage.setItem(DECK_LIBRARY_KEY, JSON.stringify(list.slice(0, 20)));
  renderSavedDecks();
}

function forgetDeckFromLibrary(name) {
  localStorage.setItem(DECK_LIBRARY_KEY, JSON.stringify(getDeckLibrary().filter((entry) => entry.name !== name)));
  renderSavedDecks();
}

function importDeckPayload(deck, name, persist = true) {
  send({ type: "import_deck", deck });
  if (persist) saveDeckToLibrary(name || deck.name || "Deck", deck);
  $("#importPanel").classList.add("hidden");
  $("#importDeckText").value = "";
}

function renderStarterDecks() {
  const box = $("#starterDeckList");
  box.innerHTML = starterDecks
    .map(
      (d) => `<button class="deck-pick deck-pick-temperament" data-import-starter="${esc(d.id)}" style="--temperament-ink:${esc(temperamentInk(d.colorKey))}">
        <img src="${esc(temperamentSymbol(d.colorKey))}" alt="">${esc(d.name)}
      </button>`
    )
    .join("");
  $$("[data-import-starter]").forEach((btn) => {
    btn.onclick = () => {
      const deck = starterDecks.find((d) => d.id === btn.dataset.importStarter);
      if (deck) importDeckPayload(deck, deck.name, false);
    };
  });
}

function renderSavedDecks() {
  const list = getDeckLibrary();
  const box = $("#savedDeckList");
  if (!list.length) {
    box.innerHTML = `<p style="color:var(--muted);font-size:14px">${esc(t("noSavedDecks"))}</p>`;
    return;
  }
  box.innerHTML = list
    .map((entry) => `<div class="deck-pick-row">
      <button class="deck-pick" data-import-saved="${esc(entry.name)}" title="${esc(t("savedOn"))} ${esc(new Date(entry.savedAt).toLocaleDateString())}">${esc(entry.name)}</button>
      <button class="deck-forget" data-forget-saved="${esc(entry.name)}" title="${esc(t("forgetDeck"))}">×</button>
    </div>`)
    .join("");
  $$("[data-import-saved]").forEach((btn) => {
    btn.onclick = () => {
      const entry = getDeckLibrary().find((e) => e.name === btn.dataset.importSaved);
      if (entry) importDeckPayload(entry.deck, entry.name, false);
    };
  });
  $$("[data-forget-saved]").forEach((btn) => {
    btn.onclick = () => forgetDeckFromLibrary(btn.dataset.forgetSaved);
  });
}

// ---------------------------------------------------------------- i18n paint

function paintStaticText() {
  $("#appTitle").textContent = t("appName");
  $("#tagline").textContent = t("tagline");
  $("#tabCreate").textContent = t("createGame");
  $("#tabJoin").textContent = t("joinGame");
  $("#nameLabel1").textContent = t("yourName");
  $("#nameLabel2").textContent = t("yourName");
  $("#createName").placeholder = t("namePlaceholder");
  $("#joinName").placeholder = t("namePlaceholder");
  $("#createBtn").textContent = t("createButton");
  $("#playerCodeLabel").textContent = t("playerCode");
  $("#observerCodeLabel").textContent = t("observerCode");
  $("#copyPlayerCode").textContent = t("copy");
  $("#copyObserverCode").textContent = t("copy");
  $("#shareHint").textContent = t("shareHint");
  $("#continueBtn").textContent = t("continueToGame");
  $("#codeLabel").textContent = "Code";
  $("#joinCode").placeholder = t("codePlaceholder");
  $("#joinBtn").textContent = t("joinButton");
  $("#brandText").textContent = t("appName");
  $("#importDeckBtn").textContent = t("importDeck");
  $("#downloadLogBtn").textContent = t("downloadLog");
  $("#endSessionBtn").textContent = t("endSession");
  $("#leaveSessionBtn").textContent = t("leaveSession");
  $("#fullscreenBtn").textContent = t("fullscreen");
  $("#importDeckHeading").textContent = t("importDeck");
  $("#starterDecksHeading").textContent = t("starterDecks");
  $("#savedDecksHeading").textContent = t("savedDecks");
  $("#importDeckHintText").textContent = t("importDeckHint");
  $("#importDeckText").placeholder = t("importDeckPlaceholder");
  $("#importCancelBtn").textContent = t("close");
  $("#importConfirmBtn").textContent = t("import");
  $("#logHeading").textContent = t("logHeader");
  $("#logDownloadBtn").textContent = t("logDownload");
  $("#logCloseBtn").textContent = t("close");
  $("#handDrawOneBtn").textContent = t("handDrawOneBtn");
  $("#handDrawHandBtn").textContent = t("handDrawHandBtn");
  $("#handDiscardBtn").textContent = t("handDiscard");
  $("#handDiscardRandomBtn").textContent = t("handDiscardRandom");
  $("#handShowBtn").textContent = t("handShow");
  $("#handMulliganBtn").textContent = t("mulligan");
  $("#handHideBtn").textContent = t("hideHand");
  $("#inspectCloseBtn").textContent = t("close");
  $("#drawPenBtn").title = t("draw");
  $("#drawEraseBtn").title = t("remove");
  $("#drawUndoBtn").title = t("undo");
  $("#drawRedoBtn").title = t("redo");
  $("#drawClearBtn").title = t("clearDrawings");
  $("#revealHeading").textContent = t("revealHeader");
  $("#revealCloseBtn").textContent = t("close");
  $("#createTokenBtn").title = t("createToken");
  $("#tokenPanelHeading").textContent = t("tokenPanelHeading");
  $("#tokenPanelHint").textContent = t("tokenPanelHint");
  $("#tokenPowerLabel").textContent = t("tokenPower");
  $("#tokenCancelBtn").textContent = t("close");
  $("#tokenCreateBtn").textContent = t("create");
  $("#createEssenceBtn").title = t("createEssence");
  $("#pileCalibrateBtn").title = t(pilesLocked ? "unlockPiles" : "lockPiles");
  $("#essencePanelHeading").textContent = t("essencePanelHeading");
  $("#essencePanelHint").textContent = t("essencePanelHint");
  $("#essenceCountLabel").textContent = t("essenceCount");
  $("#essenceCancelBtn").textContent = t("close");
  $("#essenceCreateBtn").textContent = t("create");
  $("#handRequestDeclineBtn").textContent = t("decline");
  $("#handRequestAcceptBtn").textContent = t("accept");
  $("#socialDeckomantik").textContent = t("socialDeckomantik");
  $("#socialDiscord").textContent = t("socialDiscord");
  $("#socialInstagram").textContent = t("socialInstagram");
  $("#socialInstagramOfficialLabel").textContent = t("officialInstagram");
  $("#socialInstagramFanLabel").textContent = t("fanFranceInstagram");
  $("#socialLegal").textContent = t("legalNotices");
  $("#legalHeading").textContent = t("legalNotices");
  $("#legalCopy").innerHTML = ["legalP1", "legalP2", "legalP3", "legalP4"].map((k) => `<p>${esc(t(k))}</p>`).join("");
  $("#legalCloseBtn").textContent = t("close");
}

function initSocialLinks() {
  $("#socialInstagram").onclick = (event) => {
    event.stopPropagation();
    const open = $("#socialInstagramMenu").classList.toggle("hidden") === false;
    $("#socialInstagram").setAttribute("aria-expanded", String(open));
  };
  document.addEventListener("click", (event) => {
    if (event.target.closest(".social-instagram-wrap")) return;
    $("#socialInstagramMenu").classList.add("hidden");
    $("#socialInstagram").setAttribute("aria-expanded", "false");
  });
  $("#socialLegal").onclick = () => $("#legalPanel").classList.remove("hidden");
  $("#legalCloseBtn").onclick = () => $("#legalPanel").classList.add("hidden");
}

// ---------------------------------------------------------------- join screen

function setStatus(message, isError = false) {
  const el = $("#gameScreen").classList.contains("hidden") ? $("#statusLine") : $("#gameStatusLine");
  el.textContent = message || "";
  el.classList.toggle("error", Boolean(isError));
}

function initJoinScreen() {
  $("#tabCreate").onclick = () => {
    $("#tabCreate").classList.add("active");
    $("#tabJoin").classList.remove("active");
    $("#createPane").classList.remove("hidden");
    $("#joinPane").classList.add("hidden");
  };
  $("#tabJoin").onclick = () => {
    $("#tabJoin").classList.add("active");
    $("#tabCreate").classList.remove("active");
    $("#joinPane").classList.remove("hidden");
    $("#createPane").classList.add("hidden");
  };

  const savedName = localStorage.getItem("ko_name") || "";
  $("#createName").value = savedName;
  $("#joinName").value = savedName;

  $("#createBtn").onclick = () => {
    const name = $("#createName").value.trim() || "Player";
    localStorage.setItem("ko_name", name);
    connectAndJoin({ createNew: true, name });
  };

  $("#joinBtn").onclick = () => {
    const name = $("#joinName").value.trim() || "Player";
    const code = $("#joinCode").value.trim().toUpperCase();
    if (!code) return setStatus(t("invalidCode"), true);
    localStorage.setItem("ko_name", name);
    connectAndJoin({ code, name });
  };

  $$('[data-copy]').forEach((btn) => {
    btn.onclick = () => {
      const val = $("#" + btn.dataset.copy).textContent;
      navigator.clipboard?.writeText(val);
      const original = btn.textContent;
      btn.textContent = t("copied");
      setTimeout(() => (btn.textContent = original), 1200);
    };
  });

  $("#continueBtn").onclick = () => showGameScreen();
}

let pendingCreateFlow = false;

function connectAndJoin(joinPayload) {
  setStatus(t("connecting"));
  intentionalClose = false;
  joinedCode = joinPayload.code || null;
  joinedName = joinPayload.name;
  const createNew = Boolean(joinPayload.createNew);
  pendingCreateFlow = createNew;

  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${proto}//${location.host}/ws`);
  ws.onopen = () => {
    ws.send(JSON.stringify({ type: "join", createNew, code: joinedCode, name: joinedName, clientId }));
  };
  ws.onmessage = (event) => handleServerMessage(JSON.parse(event.data));
  ws.onclose = () => {
    if (intentionalClose) return;
    if ($("#gameScreen").classList.contains("hidden")) {
      setStatus(t("invalidCode"), true);
      return;
    }
    setStatus(t("connectionLost"), true);
    scheduleReconnect();
  };
  ws.onerror = () => {};
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectAndJoin({ code: joinedCode || codePlayer, name: joinedName });
  }, 2000);
}

function showGameScreen() {
  $("#joinScreen").classList.add("hidden");
  $("#gameScreen").classList.remove("hidden");
  // #battlefieldWrap is zero-sized while #gameScreen is display:none, so the
  // fit-and-centre math only works once it's actually visible
  centerBoardInView();
}

// Used both when P2/an observer simply leaves (the session carries on for
// everyone else) and, after send()-ing end_session, for P1's own client —
// in both cases *this* client is done and goes back to the home screen.
function leaveSession() {
  intentionalClose = true;
  if (ws) ws.close();
  ws = null;
  latestState = null;
  myPlayerId = null;
  isObserver = false;
  codePlayer = null;
  codeObserver = null;
  joinedCode = null;
  joinedName = null;
  sessionEndedNotified = false;
  revealedHandCards.clear();
  pendingIncomingRequest = null;
  $("#handRequestPanel").classList.add("hidden");
  $("#sessionEndedBanner").classList.add("hidden");
  $("#gameScreen").classList.add("hidden");
  $("#joinScreen").classList.remove("hidden");
  $("#codesBox").classList.add("hidden");
  setStatus("");
}

// ---------------------------------------------------------------- server messages

function handleServerMessage(msg) {
  if (msg.type === "joined") {
    myPlayerId = msg.playerId;
    isObserver = msg.isObserver;
    $("#drawToolbar").classList.toggle("hidden", isObserver);
    $("#tokenToolbar").classList.toggle("hidden", isObserver);
    if (msg.codePlayer) codePlayer = msg.codePlayer;
    codeObserver = msg.codeObserver;
    joinedCode = joinedCode || codePlayer;
    setStatus("");

    const codeItemHtml = (code, labelKey) => `<div class="code-item">
      <span class="code-item-label">${esc(t(labelKey))}</span>
      <button data-copy-code="${esc(code || "")}">${esc(code || "")}</button>
    </div>`;
    $("#headerCodes").innerHTML = isObserver
      ? `${codeItemHtml(codeObserver, "observerCode")}<span class="count" id="headerCounts"></span>`
      : `${codeItemHtml(codePlayer, "playerCode")}${codeItemHtml(codeObserver, "observerCode")}<span class="count" id="headerCounts"></span>`;
    $$("#headerCodes [data-copy-code]").forEach((btn) => {
      btn.onclick = () => {
        navigator.clipboard?.writeText(btn.dataset.copyCode);
        const original = btn.textContent;
        btn.textContent = t("copied");
        setTimeout(() => (btn.textContent = original), 1200);
      };
    });

    if (pendingCreateFlow) {
      pendingCreateFlow = false;
      $("#playerCodeValue").textContent = codePlayer;
      $("#observerCodeValue").textContent = codeObserver;
      $("#codesBox").classList.remove("hidden");
    } else if ($("#gameScreen").classList.contains("hidden")) {
      showGameScreen();
    }
  } else if (msg.type === "state") {
    latestState = msg;
    renderAll();
    renderStrokes();
  } else if (msg.type === "reveal") {
    if (msg.zone === "hand") {
      if (!revealedHandCards.has(msg.ownerId)) revealedHandCards.set(msg.ownerId, new Set());
      const set = revealedHandCards.get(msg.ownerId);
      msg.cards.forEach((cid) => set.add(cid));
    }
    showRevealPopup(msg);
  } else if (msg.type === "scry_result") {
    showScryPopup(msg.cards);
  } else if (msg.type === "dice_result") {
    handleDiceResult(msg);
  } else if (msg.type === "error") {
    if ($("#gameScreen").classList.contains("hidden")) setStatus(msg.message, true);
    else showToast(msg.message, true);
    console.warn("Server error:", msg.message);
  } else if (msg.type === "log") {
    renderLog(msg.entries);
  } else if (msg.type === "hand_action_request") {
    pendingIncomingRequest = msg;
    $("#handRequestHeading").textContent = t(msg.action === "discard" ? "handRequestHeadingDiscard" : "handRequestHeadingShow");
    $("#handRequestText").textContent = `${msg.fromName} ${t(msg.action === "discard" ? "handRequestTextDiscard" : "handRequestTextShow")}`;
    $("#handRequestCard").innerHTML = `<img src="${esc(cardImage(msg.cardId))}" alt="${esc(cardName(msg.cardId))}" title="${esc(cardName(msg.cardId))}">`;
    $("#handRequestPanel").classList.remove("hidden");
  } else if (msg.type === "hand_action_declined") {
    showToast(`${msg.byName} ${t("handActionDeclined")}`, true);
  } else if (msg.type === "hand_action_failed") {
    showToast(t("handActionFailed"), true);
  }
}

function showToast(text, isError = false) {
  const line = document.createElement("div");
  line.className = "ko-toast" + (isError ? " error" : "");
  line.textContent = text;
  document.body.appendChild(line);
  setTimeout(() => line.remove(), isError ? 5000 : 6000);
}

// Tracks, for the CURRENTLY open reveal/scry popup only, which cards have
// already been sent somewhere — reset every time a new popup opens. Each
// entry is { label, undo } — undo is only present for destinations that are
// cleanly reversible (a plain move_card back to the reveal's own source
// zone); playing to the battlefield creates a new item with no id known
// back here, so those aren't offered an undo.
let revealSentState = new Map();

function sentCardHtml(cardId, sent) {
  return `<img src="${esc(cardImage(cardId))}" alt="${esc(cardName(cardId))}">
    <div class="sent-label">
      <div>${esc(t("sentTo"))} ${esc(sent.label)}</div>
      ${sent.undo ? `<button class="sent-undo-btn" data-undo-card="${esc(cardId)}">${esc(t("undo"))}</button>` : ""}
    </div>`;
}

function cardImagesHtml(cardIds) {
  if (!cardIds.length) return `<p>${esc(t("cards"))}: 0</p>`;
  return cardIds
    .map((cid) => {
      const sent = revealSentState.get(cid);
      return `<div class="reveal-card${sent ? " sent" : ""}" data-card-id="${esc(cid)}">
      ${sent ? sentCardHtml(cid, sent) : `<img src="${esc(cardImage(cid))}" alt="${esc(cardName(cid))}" title="${esc(cardName(cid))}">`}
    </div>`;
    })
    .join("");
}

// Once a card is sent somewhere, it stays in the popup but greyed out with
// "sent to X" instead of vanishing — the point is to keep the whole reveal
// visible as a record of what was looked at and where each card ended up.
function markRevealCardSent(cardId, destinationLabel, undoFn) {
  revealSentState.set(cardId, { label: destinationLabel, undo: undoFn });
  const el = document.querySelector(`#revealCards [data-card-id="${cardId}"]`);
  if (!el) return;
  el.classList.add("sent");
  el.innerHTML = sentCardHtml(cardId, revealSentState.get(cardId));
  if (undoFn) {
    el.querySelector(".sent-undo-btn").onclick = (event) => {
      event.stopPropagation();
      undoFn();
      revealSentState.delete(cardId);
      el.classList.remove("sent");
      el.innerHTML = `<img src="${esc(cardImage(cardId))}" alt="${esc(cardName(cardId))}" title="${esc(cardName(cardId))}">`;
    };
  }
}

// Right-click on a card shown in the reveal/scry popup: always let the viewer
// inspect it (they've already seen its identity, that's the point of a
// reveal), but only offer "move to field" when the viewer actually owns the
// zone it came from — matches the server's own can_act_on_zone check.
function wireRevealCards(ctx) {
  $$("#revealCards [data-card-id]").forEach((el) => {
    const cardId = el.dataset.cardId;
    el.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      // checked at fire-time, not just when this listener was attached: the
      // card's own listener stays bound even after markRevealCardSent()
      // replaces its innerHTML (that only clears children, not el's own
      // listeners), so this is what actually stops actions on a sent card
      if (revealSentState.has(cardId)) return;
      const items = [{ label: t("inspect"), onSelect: () => showInspect(cardId) }];
      if (ctx && ctx.allowMoveToField) {
        items.push({ separator: true });
        items.push({ label: t("playFaceUp"), onSelect: () => { playFromZone(ctx.ownerId, ctx.zone, cardId, true); markRevealCardSent(cardId, t("battlefield")); } });
        items.push({ label: t("playFaceDown"), onSelect: () => { playFromZone(ctx.ownerId, ctx.zone, cardId, false); markRevealCardSent(cardId, t("battlefield")); } });
        items.push({ separator: true });
        ["hand", "graveyard", "exile", "receptacle"].forEach((z) => {
          items.push({
            label: `${t("moveTo")} ${t(z)}`,
            onSelect: () => {
              // Empathic Vessel always collects into the ACTOR's own vessel
              const toOwnerId = z === "receptacle" ? myPlayerId : ctx.ownerId;
              send({ type: "move_card", fromOwnerId: ctx.ownerId, fromZone: ctx.zone, toOwnerId, toZone: z, cardId });
              markRevealCardSent(cardId, t(z), () =>
                send({ type: "move_card", fromOwnerId: toOwnerId, fromZone: z, toOwnerId: ctx.ownerId, toZone: ctx.zone, cardId })
              );
            },
          });
        });
        items.push({
          label: t("moveToDeckTop"),
          onSelect: () => {
            send({ type: "move_card", fromOwnerId: ctx.ownerId, fromZone: ctx.zone, toOwnerId: ctx.ownerId, toZone: "deck", cardId, position: "top" });
            markRevealCardSent(cardId, `${t("deck")} (${t("moveToDeckTop")})`, () =>
              send({ type: "move_card", fromOwnerId: ctx.ownerId, fromZone: "deck", toOwnerId: ctx.ownerId, toZone: ctx.zone, cardId })
            );
          },
        });
        items.push({
          label: t("moveToDeckBottom"),
          onSelect: () => {
            send({ type: "move_card", fromOwnerId: ctx.ownerId, fromZone: ctx.zone, toOwnerId: ctx.ownerId, toZone: "deck", cardId, position: "bottom" });
            markRevealCardSent(cardId, `${t("deck")} (${t("moveToDeckBottom")})`, () =>
              send({ type: "move_card", fromOwnerId: ctx.ownerId, fromZone: "deck", toOwnerId: ctx.ownerId, toZone: ctx.zone, cardId })
            );
          },
        });
      }
      showContextMenu(event.clientX, event.clientY, items);
    });
  });
}

function showRevealPopup(msg) {
  revealSentState = new Map();
  const owner = latestState?.players?.[msg.ownerId];
  $("#revealHeading").textContent = t("revealHeader");
  $("#revealWho").textContent = `${owner ? owner.name : msg.ownerId} ${t("revealedBy")} · ${t(msg.zone)}`;
  $("#revealCards").innerHTML = cardImagesHtml(msg.cards);
  $("#revealPanel").classList.remove("hidden");
  wireRevealCards({ ownerId: msg.ownerId, zone: msg.zone, allowMoveToField: !isObserver && msg.ownerId === myPlayerId });
}

function showScryPopup(cardIds) {
  revealSentState = new Map();
  $("#revealHeading").textContent = t("scryHeader");
  $("#revealWho").textContent = "";
  $("#revealCards").innerHTML = cardImagesHtml(cardIds);
  $("#revealPanel").classList.remove("hidden");
  // scry is always a private peek at your own deck, so this is always your own zone
  wireRevealCards({ ownerId: myPlayerId, zone: "deck", allowMoveToField: true });
}

// ---------------------------------------------------------------- actions (send)

function send(payload) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(payload));
}

// ---------------------------------------------------------------- rendering

let sessionEndedNotified = false;

function renderAll() {
  if (!latestState) return;
  renderBattlefield();
  renderHandTray();
  renderOppRows();
  if (!$("#handViewPanel").classList.contains("hidden")) {
    const viewingId = $("#handViewPanel").dataset.viewingPlayer;
    if (viewingId && latestState.players[viewingId]) openHandView(viewingId);
  }
  if (!$("#deckBrowserPanel").classList.contains("hidden")) {
    const { ownerId, zone } = $("#deckBrowserPanel").dataset;
    if (ownerId && zone && latestState.players[ownerId]) openPileBrowser(ownerId, zone);
  }
  updateHeaderCounts();
  const canEndForAll = !isObserver && mySeat() === 0;
  $("#endSessionBtn").classList.toggle("hidden", !canEndForAll);
  $("#leaveSessionBtn").classList.toggle("hidden", canEndForAll);
  $("#endSessionBtn").disabled = latestState.ended;
  if (latestState.ended && !sessionEndedNotified) {
    sessionEndedNotified = true;
    // a toast fades; the others need this to stay up so they don't miss it
    $("#sessionEndedBanner").textContent = t("sessionEnded");
    $("#sessionEndedBanner").classList.remove("hidden");
  }
}

// Always-visible row(s), top-left: a regular player only ever needs their
// one opponent's row (their own hand is already visible in the tray below);
// an observer has no "own hand" to skip, so they get one row per player.
function renderOppRows() {
  const rows = $("#oppRows");
  rows.innerHTML = Object.values(latestState.players)
    .filter((p) => isObserver || p.id !== myPlayerId)
    .map((p) => {
      const handZone = p.zones.hand;
      const handCount = handZone.count !== undefined ? handZone.count : (handZone.cards || []).length;
      const viewHandLabel = isObserver ? `${esc(p.name)}: ${esc(t("viewHand"))} (${handCount})` : `${esc(t("opponentHand"))} ${handCount}`;
      const vesselPoints = receptaclePoints(p.zones.receptacle, p.score);
      return `<div class="opp-info-row">
        <span class="hand-mini"><span class="mini-back" style="--owner-color:${playerColor(p.id)}"></span>${esc(p.name)}</span>
        <button class="view-hand-btn" data-view-hand="${esc(p.id)}">${viewHandLabel}</button>
        <span class="opp-vessel-badge" title="${esc(t("receptacle"))}">${vesselPoints} ${esc(t("vesselPoints"))}</span>
      </div>`;
    })
    .join("");
  $$("[data-view-hand]").forEach((btn) => {
    btn.onclick = (e) => {
      e.stopPropagation();
      openHandView(btn.dataset.viewHand);
    };
  });
}

// Approximates the opponent's hand for a regular player: we only ever learn
// their live count (privacy-preserving) plus whichever specific cardIds have
// been `reveal`-ed at some point, so we show that many revealed-face-up slots
// and pad the rest with generic face-down backs. Observers get the real
// zone contents from the server (their can_view_zone is unconditional), so
// their view just shows every actual card, face up.
function openHandView(playerId) {
  const player = latestState.players[playerId];
  if (!player) return;
  const handZone = player.zones.hand;
  const isMine = playerId === myPlayerId && !isObserver;
  const canRequest = !isObserver && !isMine;
  const hvCardHtml = (i, cid) =>
    `<div class="hv-card revealed" data-hv-index="${i}" data-hv-card="${esc(cid)}" style="--owner-color:${playerColor(playerId)}"><img src="${esc(cardImage(cid))}" alt="${esc(cardName(cid))}" title="${esc(cardName(cid))}"></div>`;
  let count, cardsHtml;
  if (handZone.cards !== undefined) {
    count = handZone.cards.length;
    cardsHtml = handZone.cards.map((cid, i) => hvCardHtml(i, cid)).join("");
  } else {
    count = handZone.count || 0;
    const revealedIds = [...(revealedHandCards.get(playerId) || [])].slice(0, count);
    cardsHtml = Array.from({ length: count }, (_, i) =>
      revealedIds[i] ? hvCardHtml(i, revealedIds[i]) : `<div class="hv-card" data-hv-index="${i}" style="--owner-color:${playerColor(playerId)}"></div>`
    ).join("");
  }
  $("#handViewTitle").textContent = `${player.name}${isMine ? ` (${t("you")})` : ""} — ${count} ${count === 1 ? t("card") : t("cards")}`;
  $("#handViewCards").innerHTML = cardsHtml || `<p style="color:#cfc7a8;font-size:14px">${esc(t("cards"))}: 0</p>`;
  $("#handViewPanel").dataset.viewingPlayer = playerId;
  $("#handViewPanel").classList.remove("hidden");
  // Inspect: an observer or the hand's own owner can inspect any card here;
  // any other player only ever gets a real cardId on cards that have already
  // been revealed at some point (see hvCardHtml above) — everything else is
  // just a generic face-down placeholder with no identity to show.
  $$("#handViewCards [data-hv-index]").forEach((el) => {
    const index = Number(el.dataset.hvIndex);
    const cid = el.dataset.hvCard || null;
    if (cid) {
      el.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        showContextMenu(event.clientX, event.clientY, [{ label: t("inspect"), onSelect: () => showInspect(cid) }]);
      });
    }
    if (canRequest) {
      el.onclick = (event) => {
        showContextMenu(event.clientX, event.clientY, [
          { label: t("requestDiscard"), onSelect: () => send({ type: "request_hand_action", targetPlayerId: playerId, index, action: "discard" }) },
          { label: t("requestShow"), onSelect: () => send({ type: "request_hand_action", targetPlayerId: playerId, index, action: "show" }) },
        ]);
      };
    }
  });
}

// Full visual browser for ANY pile (deck, graveyard, exile, receptacle) —
// replaces the old "Search" toggle, which just revealed a plain name-list
// inline in the pile popover. Only ever reachable via the Search button,
// which only renders when this viewer canAct on that zone (see
// zoneActionsHtml) — but stay defensive in case a zone is ever a count-only
// view (e.g. this got called for someone else's private deck somehow).
function openPileBrowser(ownerId, zone) {
  const player = latestState.players[ownerId];
  const cards = player?.zones?.[zone]?.cards;
  if (!player || !cards) return;
  $("#deckBrowserPanel").dataset.ownerId = ownerId;
  $("#deckBrowserPanel").dataset.zone = zone;
  $("#deckBrowserHeading").textContent = `${player.name} — ${t(zone)} (${cards.length})`;
  $("#deckBrowserCards").innerHTML =
    cards
      .map(
        (cid) => `<div class="db-card" style="--owner-color:${playerColor(ownerId)}" title="${esc(cardName(cid))}" data-zone-card="${esc(ownerId)}:${esc(zone)}:${esc(cid)}">
      <img src="${esc(cardImage(cid))}" alt="${esc(cardName(cid))}">
    </div>`
      )
      .join("") || `<p style="color:var(--muted);font-size:14px">${esc(t("cards"))}: 0</p>`;
  $("#deckBrowserPanel").classList.remove("hidden");
  wirePileBrowserCards(ownerId, zone);
}

// Same right-click inspect/move menu as a pile's own inline list (see
// wireZoneButtons' [data-zone-card] handling) — reachable only via Search,
// which already gates on canAct, so no extra permission check is needed here.
function wirePileBrowserCards(ownerId, zone) {
  $$("#deckBrowserCards [data-zone-card]").forEach((el) => {
    const cardId = el.dataset.zoneCard.split(":")[2];
    bindCardDragSource(el, { kind: "card", cardId, fromOwnerId: ownerId, fromZone: zone });
    el.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      const items = [
        { label: t("inspect"), onSelect: () => showInspect(cardId) },
        { separator: true },
        { label: t("playFaceUp"), onSelect: () => playFromZone(ownerId, zone, cardId, true) },
        { label: t("playFaceDown"), onSelect: () => playFromZone(ownerId, zone, cardId, false) },
        { separator: true },
      ];
      ZONES.filter((z) => z !== zone).forEach((z) => {
        items.push({
          label: `${t("moveTo")} ${t(z)}`,
          onSelect: () => send({ type: "move_card", fromOwnerId: ownerId, fromZone: zone, toOwnerId: ownerId, toZone: z, cardId }),
        });
      });
      showContextMenu(event.clientX, event.clientY, items);
    });
  });
}

const DECK_BROWSER_SIZE_KEY = "ko_deck_browser_card_w";

function initPileBrowser() {
  $("#deckBrowserSliderLabel").textContent = t("deckBrowserSliderLabel");
  $("#deckBrowserCloseBtn").textContent = t("close");
  const saved = Number(localStorage.getItem(DECK_BROWSER_SIZE_KEY)) || 140;
  $("#deckBrowserSlider").value = saved;
  document.documentElement.style.setProperty("--db-card-w", saved + "px");
  $("#deckBrowserSlider").oninput = () => {
    document.documentElement.style.setProperty("--db-card-w", $("#deckBrowserSlider").value + "px");
    localStorage.setItem(DECK_BROWSER_SIZE_KEY, $("#deckBrowserSlider").value);
  };
  $("#deckBrowserCloseBtn").onclick = () => $("#deckBrowserPanel").classList.add("hidden");
}

function updateHeaderCounts() {
  const el = $("#headerCounts");
  if (!el || !latestState) return;
  const playerCount = Object.keys(latestState.players).length;
  const observerCount = latestState.observerCount || 0;
  el.textContent = `${playerCount} ${t("players")} · ${observerCount} ${t("observers")}`;
}

function zoneActionsHtml(ownerId, zone, canAct) {
  const buttons = [];
  if (!canAct) return "";
  const mine = ownerId === myPlayerId;
  if (zone === "deck") {
    buttons.push(`<button data-draw="${esc(ownerId)}">${esc(t("drawOne"))}</button>`);
    buttons.push(`<button data-draw-limit="${esc(ownerId)}">${esc(t("drawToLimit"))}</button>`);
    buttons.push(`<button data-discard-top="${esc(ownerId)}" title="${esc(t("discardTop"))}">${esc(t("handDiscard"))}</button>`);
  }
  buttons.push(`<button data-shuffle="${esc(ownerId)}:${zone}">${esc(t("shuffle"))}</button>`);
  if (zone === "deck") {
    buttons.push(`<span class="reveal-n-group">
      <input type="number" min="1" max="10" value="1" data-reveal-n-input="${esc(ownerId)}:${zone}">
      <button data-reveal-n="${esc(ownerId)}:${zone}">${esc(t("show"))}</button>
    </span>`);
    if (mine) {
      buttons.push(`<span class="reveal-n-group">
        <input type="number" min="1" max="10" value="1" data-scry-n-input="${esc(ownerId)}:${zone}">
        <button data-scry="${esc(ownerId)}:${zone}">${esc(t("scry"))}</button>
      </span>`);
    }
  }
  // Search opens the same full visual browser for every pile: your own deck
  // (private, so gated to its owner) or any shared pile (already actionable
  // by anyone here, since canAct is already true for those — see zoneBlockHtml)
  if (zone !== "deck" || mine) {
    buttons.push(`<button data-open-pile-browser="${esc(ownerId)}:${zone}">${esc(t("search"))}</button>`);
  }
  return buttons.join("");
}

// "M"/"W" for Manifestation/Will, plus the card's own temperament symbol —
// reuses the same icon set as tokens/essences, keyed the same way (colorKey).
function zoneCardKindBadgeHtml(cardId) {
  const card = cardsById.get(cardId);
  if (!card) return "";
  const kindLetter = card.type === "manifestation" ? "M" : "W";
  return `<img class="zone-card-temperament" src="${esc(temperamentSymbol(card.colorKey))}" alt="">
    <span class="zone-card-kind" title="${esc(card.typeLabel || "")}">${kindLetter}</span>`;
}

function zoneCardRowHtml(ownerId, zone, cardId, canAct) {
  const style = `style="--owner-color:${playerColor(ownerId)}"`;
  if (!canAct) {
    return `<div class="zone-card-row" ${style}>${zoneCardKindBadgeHtml(cardId)}<span>${esc(cardName(cardId))}</span></div>`;
  }
  return `<div class="zone-card-row" ${style} data-zone-card="${esc(ownerId)}:${zone}:${esc(cardId)}" data-preview-card="${esc(cardId)}">
    ${zoneCardKindBadgeHtml(cardId)}<span>${esc(cardName(cardId))}</span>
  </div>`;
}

function zoneBlockHtml(ownerId, zone, zoneData, canView, canAct) {
  const key = `${ownerId}:${zone}`;
  const isOpen = expanded.has(key);
  const count = zoneData.count !== undefined ? zoneData.count : (zoneData.cards || []).length;
  const label = t(zone);
  // your own deck never reveals its list inline any more — Search now opens
  // the full visual deck browser instead of toggling this popover's list
  const gatedBySearch = zone === "deck" && ownerId === myPlayerId;
  let listHtml = "";
  if (canView && isOpen) {
    if (gatedBySearch) {
      listHtml = `<div class="zone-search-hint">${esc(t("searchHint"))}</div>`;
    } else {
      const cards = zoneData.cards || [];
      listHtml = `<div class="zone-list">${cards.map((cid) => zoneCardRowHtml(ownerId, zone, cid, canAct)).join("") || `<div style="color:var(--muted);font-size:14px">(${t("cards")}: 0)</div>`}</div>`;
    }
  }
  return `<div class="zone">
    <div class="zone-head">
      <strong>${esc(label)}</strong>
      <span class="count">${count} ${count === 1 ? esc(t("card")) : esc(t("cards"))}</span>
      ${canView ? `<button data-toggle-zone="${esc(key)}" style="padding:3px 7px;font-size:14px;min-height:0">${isOpen ? "▾" : "▸"}</button>` : ""}
    </div>
    ${canAct ? `<div class="zone-actions">${zoneActionsHtml(ownerId, zone, canAct)}</div>` : ""}
    ${listHtml}
  </div>`;
}

function toggleZone(key) {
  if (expanded.has(key)) expanded.delete(key);
  else expanded.add(key);
  renderBattlefield();
}

function pileFieldHtml(ownerId, zone, zoneData, canView, canAct, pos, score, overrideKey, rawPos) {
  const key = `${ownerId}:${zone}`;
  const count = zoneData.count !== undefined ? zoneData.count : (zoneData.cards || []).length;
  const isOpen = expanded.has(key);
  const dropAttr = canAct ? ` data-drop-zone="${esc(key)}"` : "";
  const scoreAdjust =
    zone === "receptacle" && !isObserver
      ? `<div class="pile-score-adjust">
          <button data-score-delta="${esc(ownerId)}:-10">-10</button><button data-score-delta="${esc(ownerId)}:-5">-5</button>
          <button data-score-delta="${esc(ownerId)}:-1">-1</button><button data-score-delta="${esc(ownerId)}:1">+1</button>
          <button data-score-delta="${esc(ownerId)}:5">+5</button><button data-score-delta="${esc(ownerId)}:10">+10</button>
        </div>`
      : "";
  // shared zones (limbo/exile/vessel) show the actual face of the most
  // recently entered card (index 0, same "top" convention as the deck); the
  // deck itself always stays card-back regardless of who's viewing
  const topCardId = zone !== "deck" && count > 0 ? (zoneData.cards || [])[0] : null;
  const topCardHtml = topCardId
    ? `<img class="pile-top-card" src="${esc(cardImage(topCardId))}" alt="${esc(cardName(topCardId))}" title="${esc(cardName(topCardId))}">`
    : "";
  const pointsBadge = zone === "receptacle" ? `<div class="pile-points">${receptaclePoints(zoneData, score)} ${esc(t("vesselPoints"))}</div>` : "";
  return `<div class="field-pile ${count === 0 ? "empty" : ""}"${dropAttr} data-field-pile="${esc(key)}" data-zone="${esc(zone)}" data-override-key="${esc(overrideKey)}" style="left:${pos.x}px;top:${pos.y}px;--owner-color:${playerColor(ownerId)}">
    ${scoreAdjust}
    <div class="pile-trigger" data-pile-trigger="${esc(key)}">
      <span class="pile-count">${count}</span>
      <div class="pile-card">${topCardHtml}</div>
      <span class="pile-label">${esc(t(zone))}</span>
      ${pointsBadge}
    </div>
    <span class="pile-coords">${esc(zone)}: ${Math.round(rawPos.x)}, ${Math.round(rawPos.y)}</span>
    ${isOpen ? `<div class="zone-popover">${zoneBlockHtml(ownerId, zone, zoneData, canView, canAct)}</div>` : ""}
  </div>`;
}

function receptaclePoints(zoneData, score) {
  const cardPoints = (zoneData.cards || []).reduce((sum, cid) => sum + (cardsById.get(cid)?.points || 0), 0);
  return cardPoints + (score || 0);
}

// Pile SCREEN position, keyed by [viewer's own seat][pile owner's seat][zone].
// This is deliberately NOT a single stored position mirrored through some
// formula for the "away" viewer: dragging a pile while directly viewing it
// vs. viewing that same pile from the OTHER seat (mirrored) measurably don't
// agree on one "correct" spot, so there is no substitute for a value per
// (viewer, owner) pair — 16 numbers total, all independently calibrated by
// dragging in-app and reading off the coordinates (see bindPileCalibration).
//
// The [1][0] and [1][1] entries (both captured from a seat-1 browser window)
// were fixed once already: the calibration tool's PREVIOUS version displayed
// the dragged position after converting it through the old mirror formula
// (screen -> "raw storage" space) rather than the raw screen position itself
// — invisible from a seat-0 window (identity there) but very much not from
// seat-1, where it silently swapped which corner the numbers described. The
// values below are the seat-1 readings corrected back to true screen space;
// [0][0] and [0][1] (captured from seat 0) never needed correcting.
const PILE_SCREEN_POS = {
  0: {
    0: { deck: { x: 1194, y: 1039 }, graveyard: { x: 1366, y: 1039 }, receptacle: { x: 1192, y: 1297 }, exile: { x: 1366, y: 1297 } },
    1: { deck: { x: 210, y: 305 }, graveyard: { x: 31, y: 305 }, receptacle: { x: 209, y: 48 }, exile: { x: 31, y: 48 } },
  },
  1: {
    0: { deck: { x: 208, y: 304 }, graveyard: { x: 33, y: 304 }, receptacle: { x: 208, y: 50 }, exile: { x: 32, y: 48 } },
    1: { deck: { x: 1192, y: 1039 }, graveyard: { x: 1367, y: 1039 }, receptacle: { x: 1191, y: 1293 }, exile: { x: 1364, y: 1293 } },
  },
};

// A local nudge on top of the table above — a personal display fix, never
// synced to the server or the other player. Keyed by "viewerSeat:ownerSeat:zone".
const PILE_OVERRIDES_KEY = "kartomantik.pileOverrides";
let pileOverrides = {};
let pilesLocked = true;

function loadPileOverrides() {
  try {
    pileOverrides = JSON.parse(localStorage.getItem(PILE_OVERRIDES_KEY) || "{}");
  } catch (e) {
    pileOverrides = {};
  }
}

function savePileOverrides() {
  localStorage.setItem(PILE_OVERRIDES_KEY, JSON.stringify(pileOverrides));
}

function initPileCalibration() {
  loadPileOverrides();
  loadCenterMarkerOverride();
  $("#pileCalibrateBtn").textContent = "🔒";
  $("#pileCalibrateBtn").onclick = () => {
    pilesLocked = !pilesLocked;
    $("#pileCalibrateBtn").textContent = pilesLocked ? "🔒" : "🔓";
    $("#pileCalibrateBtn").classList.toggle("active", !pilesLocked);
    $("#pileCalibrateBtn").title = t(pilesLocked ? "unlockPiles" : "lockPiles");
    renderBattlefield();
  };
}

function bindPileCalibration() {
  $$(".field-pile").forEach((el) => {
    el.classList.toggle("calibrating", !pilesLocked);
    if (pilesLocked) return;
    el.addEventListener("pointerdown", (event) => {
      if (event.target.closest("button")) return;
      event.preventDefault();
      event.stopPropagation();
      const overrideKey = el.dataset.overrideKey;
      const move = (e) => {
        const rect = $("#battlefieldWrap").getBoundingClientRect();
        // this is already screen/display space — no flip involved any more,
        // since a pile's position is now looked up directly per (viewer, owner)
        const pos = { x: (e.clientX - rect.left - panX) / zoomLevel - 75, y: (e.clientY - rect.top - panY) / zoomLevel - 105 };
        pileOverrides[overrideKey] = pos;
        el.style.left = pos.x + "px";
        el.style.top = pos.y + "px";
        el.querySelector(".pile-coords").textContent = `${el.dataset.zone}: ${Math.round(pos.x)}, ${Math.round(pos.y)}`;
      };
      const up = () => {
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
        savePileOverrides();
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up);
    });
    el.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      event.stopPropagation();
      showContextMenu(event.clientX, event.clientY, [
        { label: t("resetPilePosition"), onSelect: () => { delete pileOverrides[el.dataset.overrideKey]; savePileOverrides(); renderPiles(); } },
      ]);
    });
  });
}

// The flipY axis (see MIRROR_CENTER_Y above) drawn as a visible, draggable
// line + dot, only while calibration mode is unlocked — the same idea as
// pileOverrides, for the one other number that was ever eyeballed/measured
// rather than directly calibrated. A local-only nudge; never sent anywhere.
const CENTER_MARKER_KEY = "kartomantik.centerMarkerOverride";
let centerMarkerOverride = null;

function loadCenterMarkerOverride() {
  try {
    centerMarkerOverride = JSON.parse(localStorage.getItem(CENTER_MARKER_KEY) || "null");
  } catch (e) {
    centerMarkerOverride = null;
  }
}

function effectiveMirrorCenterY() {
  return centerMarkerOverride ? centerMarkerOverride.y : MIRROR_CENTER_Y;
}

function renderCenterMarker() {
  $$(".center-marker").forEach((el) => el.remove());
  if (pilesLocked) return;
  const bf = $("#battlefield");
  const markerX = centerMarkerOverride ? centerMarkerOverride.x : BOARD_SIZE / 2;
  const markerY = effectiveMirrorCenterY();
  const line = document.createElement("div");
  line.className = "center-marker center-marker-line";
  line.style.top = markerY + "px";
  bf.appendChild(line);
  const dot = document.createElement("div");
  dot.className = "center-marker center-marker-dot";
  dot.style.left = markerX + "px";
  dot.style.top = markerY + "px";
  dot.title = `${Math.round(markerX)}, ${Math.round(markerY)}`;
  dot.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    event.stopPropagation();
    const move = (e) => {
      const rect = $("#battlefieldWrap").getBoundingClientRect();
      const pos = { x: (e.clientX - rect.left - panX) / zoomLevel, y: (e.clientY - rect.top - panY) / zoomLevel };
      centerMarkerOverride = pos;
      dot.style.left = pos.x + "px";
      dot.style.top = pos.y + "px";
      dot.title = `${Math.round(pos.x)}, ${Math.round(pos.y)}`;
      line.style.top = pos.y + "px";
      renderBattlefield(); // live preview: cards/tokens/strokes re-mirror against the new axis immediately
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      localStorage.setItem(CENTER_MARKER_KEY, JSON.stringify(centerMarkerOverride));
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  });
  dot.addEventListener("contextmenu", (event) => {
    event.preventDefault();
    event.stopPropagation();
    showContextMenu(event.clientX, event.clientY, [
      { label: t("resetMarker"), onSelect: () => { centerMarkerOverride = null; localStorage.removeItem(CENTER_MARKER_KEY); renderBattlefield(); } },
    ]);
  });
  bf.appendChild(dot);
}

function renderPiles() {
  const bf = $("#battlefield");
  bf.querySelectorAll(".field-pile").forEach((el) => el.remove());
  const pileZones = ["deck", "graveyard", "exile", "receptacle"];
  Object.values(latestState.players).forEach((player) => {
    pileZones.forEach((zone) => {
      const zoneData = player.zones[zone];
      const canView = zoneData.cards !== undefined;
      const isMine = player.id === myPlayerId;
      const canAct = !isObserver && (isMine || !PRIVATE_ZONES.has(zone));
      const overrideKey = `${mySeat()}:${player.seat}:${zone}`;
      const pos = pileOverrides[overrideKey] || PILE_SCREEN_POS[mySeat()][player.seat][zone];
      bf.insertAdjacentHTML("beforeend", pileFieldHtml(player.id, zone, zoneData, canView, canAct, pos, player.score, overrideKey, pos));
    });
  });
  wireZoneButtons();
  $$("[data-pile-trigger]").forEach((el) => {
    el.onclick = () => toggleZone(el.dataset.pileTrigger);
  });
  $$("[data-score-delta]").forEach((btn) => {
    btn.onclick = (event) => {
      event.stopPropagation();
      const [pid, delta] = btn.dataset.scoreDelta.split(":");
      send({ type: "set_score", playerId: pid, delta: Number(delta) });
    };
  });
  bindPileCalibration();
  repositionOpenPopovers();
}

// .zone-popover is normally centred below its pile via pure CSS, which
// overflows off-screen for piles near an edge (piles are fixed, so this is a
// small, bounded set of positions, but a real measurement is simpler and more
// robust than hardcoding a per-pile correction).
function repositionOpenPopovers() {
  $$(".zone-popover").forEach((pop) => {
    pop.style.transform = "";
    pop.classList.remove("zone-popover-above");
    const margin = 4;
    let rect = pop.getBoundingClientRect();
    if (rect.bottom > window.innerHeight - margin) pop.classList.add("zone-popover-above");
    rect = pop.getBoundingClientRect();
    let dx = 0;
    if (rect.left < margin) dx = margin - rect.left;
    else if (rect.right > window.innerWidth - margin) dx = window.innerWidth - margin - rect.right;
    if (dx) pop.style.transform = `translateX(calc(-50% + ${dx}px))`;
  });
}

let previousHandCardIds = new Set();
let handHiddenByUser = false;

function applyHandVisibility(meId) {
  const collapsed = !meId || handHiddenByUser;
  $("#handArea").classList.toggle("hand-collapsed", collapsed);
  $("#myHandTray").classList.toggle("hidden", collapsed);
  $("#handResizeHandle").classList.toggle("hidden", collapsed);
  // the toolbar itself (and the hide/show toggle inside it) always stays put;
  // only its OTHER tool buttons collapse away with the tray
  $("#handToolbar").classList.toggle("hidden", !meId);
  $$(".hand-tool-btn").forEach((el) => {
    if (el.id === "handPickHint") return;
    el.classList.toggle("hidden", collapsed);
  });
  $$(".hand-tool-sep").forEach((el) => el.classList.toggle("hidden", collapsed));
  $("#handPickHint").classList.toggle("hidden", collapsed || !handPickMode);
  $("#handHideBtn").classList.toggle("hidden", !meId);
  $("#handHideBtn").textContent = t(handHiddenByUser ? "showHand" : "hideHand");
}

function renderHandTray() {
  const tray = $("#myHandTray");
  tray.dataset.emptyHint = t("handEmptyHint");
  const meId = isObserver ? null : myPlayerId;
  applyHandVisibility(meId);
  if (!meId || !latestState.players[meId]) {
    tray.innerHTML = "";
    $("#handCardCount").textContent = "";
    return;
  }
  const cards = latestState.players[meId].zones.hand.cards || [];
  $("#handCardCount").textContent = `${cards.length} ${cards.length === 1 ? t("card") : t("cards")}`;
  const currentIds = new Set(cards);
  const deckZone = latestState.players[meId].zones.deck;
  const deckCount = deckZone.count !== undefined ? deckZone.count : (deckZone.cards || []).length;
  if (cards.length === 0 && deckCount === 0) {
    tray.innerHTML = `<button class="hand-card import-card-btn" id="handImportCardBtn"><span class="import-plus">+</span><span>${esc(t("importDeckCard"))}</span></button>`;
    $("#handImportCardBtn").onclick = () => $("#importDeckBtn").click();
    previousHandCardIds = currentIds;
    return;
  }
  if (cards.length === 0 && deckCount > 0) {
    tray.innerHTML = `
      <button class="hand-card import-card-btn" id="handEmptyDrawOneBtn"><span class="import-plus">+</span><span>${esc(t("drawOne"))}</span></button>
      <button class="hand-card import-card-btn" id="handEmptyDrawHandBtn"><span class="import-plus">+</span><span>${esc(t("drawToLimit"))}</span></button>`;
    $("#handEmptyDrawOneBtn").onclick = () => send({ type: "draw", count: 1 });
    $("#handEmptyDrawHandBtn").onclick = () => send({ type: "draw_to_limit" });
    previousHandCardIds = currentIds;
    return;
  }
  const myRevealed = revealedHandCards.get(meId);
  tray.innerHTML = cards
    .map((cid) => {
      const isNew = !previousHandCardIds.has(cid);
      const wasRevealed = myRevealed && myRevealed.has(cid);
      return `<div class="hand-card ${isNew ? "ko-pop-in" : ""}" data-hand-card="${esc(cid)}" title="${esc(cardName(cid))}">
      <img src="${esc(cardImage(cid))}" alt="${esc(cardName(cid))}">
      ${wasRevealed ? `<span class="hand-card-revealed-icon" title="${esc(t("revealHeader"))}">👁</span>` : ""}
    </div>`;
    })
    .join("");
  previousHandCardIds = currentIds;
  $$("[data-hand-card]").forEach((el) => {
    const cardId = el.dataset.handCard;
    el.onclick = () => {
      if (!handPickMode) return;
      const mode = handPickMode;
      handPickMode = null;
      updateHandToolbarUi();
      if (mode === "discard") send({ type: "move_card", fromZone: "hand", toZone: "graveyard", cardId });
      else if (mode === "show") send({ type: "reveal", zone: "hand", cardId });
    };
    bindCardDragSource(el, { kind: "card", cardId, fromOwnerId: meId, fromZone: "hand" });
    el.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      showContextMenu(event.clientX, event.clientY, [
        { label: t("inspect"), onSelect: () => showInspect(cardId) },
        { separator: true },
        { label: t("playFaceUp"), onSelect: () => playFromHand(cardId, true) },
        { label: t("playFaceDown"), onSelect: () => playFromHand(cardId, false) },
        { separator: true },
        { label: t("handDiscard"), onSelect: () => send({ type: "move_card", fromZone: "hand", toZone: "graveyard", cardId }) },
        { label: t("handShow"), onSelect: () => send({ type: "reveal", zone: "hand", cardId }) },
        { label: `${t("moveTo")} ${t("exile")}`, onSelect: () => send({ type: "move_card", fromZone: "hand", toZone: "exile", cardId }) },
        { label: t("moveToDeckTop"), onSelect: () => send({ type: "move_card", fromZone: "hand", toZone: "deck", cardId, position: "top" }) },
        { label: t("moveToDeckBottom"), onSelect: () => send({ type: "move_card", fromZone: "hand", toZone: "deck", cardId, position: "bottom" }) },
      ]);
    });
  });
}

let handPickMode = null; // null | "discard" | "show"

function updateHandToolbarUi() {
  $("#handDiscardBtn").classList.toggle("active", handPickMode === "discard");
  $("#handShowBtn").classList.toggle("active", handPickMode === "show");
  const tray = $("#myHandTray");
  tray.classList.toggle("picking", Boolean(handPickMode));
  const hint = $("#handPickHint");
  hint.classList.toggle("hidden", !handPickMode);
  hint.textContent = handPickMode === "discard" ? t("pickCardToDiscard") : handPickMode === "show" ? t("pickCardToShow") : "";
}

function initHandToolbar() {
  $("#handDrawOneBtn").onclick = () => send({ type: "draw", count: 1 });
  $("#handDrawHandBtn").onclick = () => send({ type: "draw_to_limit" });
  $("#handDiscardBtn").onclick = () => {
    handPickMode = handPickMode === "discard" ? null : "discard";
    updateHandToolbarUi();
  };
  $("#handShowBtn").onclick = () => {
    handPickMode = handPickMode === "show" ? null : "show";
    updateHandToolbarUi();
  };
  $("#handDiscardRandomBtn").onclick = () => send({ type: "move_card", fromZone: "hand", toZone: "graveyard", random: true });
  $("#handMulliganBtn").onclick = () => {
    showConfirm(t("confirmMulligan"), () => send({ type: "mulligan" }));
  };
  $("#handHideBtn").onclick = toggleHandHidden;
}

function toggleHandHidden() {
  handHiddenByUser = !handHiddenByUser;
  applyHandVisibility(isObserver ? null : myPlayerId);
}

function playFromHand(cardId, faceUp) {
  const view = fieldCenterLogical();
  const center = flipY(view.x, view.y);
  send({
    type: "place_card", fromZone: "hand", cardId, faceUp,
    x: center.x - 75 + Math.random() * 60 - 30, y: center.y - 105 + Math.random() * 60 - 30,
  });
}

function wireZoneButtons() {
  $$("[data-toggle-zone]").forEach((btn) => {
    btn.onclick = (event) => {
      event.stopPropagation();
      toggleZone(btn.dataset.toggleZone);
    };
  });
  $$("[data-draw]").forEach((btn) => {
    btn.onclick = (e) => { e.stopPropagation(); send({ type: "draw", count: 1 }); };
  });
  $$("[data-draw-limit]").forEach((btn) => {
    btn.onclick = (e) => { e.stopPropagation(); send({ type: "draw_to_limit" }); };
  });
  $$("[data-discard-top]").forEach((btn) => {
    btn.onclick = (e) => {
      e.stopPropagation();
      send({ type: "move_card", fromOwnerId: btn.dataset.discardTop, fromZone: "deck", toOwnerId: btn.dataset.discardTop, toZone: "graveyard" });
    };
  });
  $$("[data-shuffle]").forEach((btn) => {
    const [ownerId, zone] = btn.dataset.shuffle.split(":");
    btn.onclick = (e) => { e.stopPropagation(); send({ type: "shuffle", ownerId, zone }); pulseZone(ownerId, zone); };
  });
  $$("[data-reveal-n]").forEach((btn) => {
    const [ownerId, zone] = btn.dataset.revealN.split(":");
    btn.onclick = (e) => {
      e.stopPropagation();
      const input = document.querySelector(`[data-reveal-n-input="${ownerId}:${zone}"]`);
      const n = Number(input?.value || 1);
      if (!n || n < 1) return;
      send({ type: "reveal", ownerId, zone, count: Math.min(10, Math.round(n)) });
    };
  });
  $$("[data-reveal-n-input]").forEach((input) => {
    input.onclick = (e) => e.stopPropagation();
    input.onpointerdown = (e) => e.stopPropagation();
  });
  $$("[data-scry]").forEach((btn) => {
    btn.onclick = (e) => {
      e.stopPropagation();
      const input = document.querySelector(`[data-scry-n-input="${btn.dataset.scry}"]`);
      const n = Number(input?.value || 1);
      send({ type: "scry", count: Math.min(10, Math.max(1, n || 1)) });
    };
  });
  $$("[data-scry-n-input]").forEach((input) => {
    input.onclick = (e) => e.stopPropagation();
    input.onpointerdown = (e) => e.stopPropagation();
  });
  $$("[data-open-pile-browser]").forEach((btn) => {
    btn.onclick = (e) => {
      e.stopPropagation();
      const [ownerId, zone] = btn.dataset.openPileBrowser.split(":");
      openPileBrowser(ownerId, zone);
    };
  });
  // scoped to the small inline pile lists — the deck/pile BROWSER modal wires
  // its own (larger) copies of these same [data-zone-card] cards itself (see
  // wirePileBrowserCards), since it isn't re-rendered by this function
  $$(".zone-list [data-zone-card]").forEach((el) => {
    const [ownerId, zone, cardId] = el.dataset.zoneCard.split(":");
    bindCardDragSource(el, { kind: "card", cardId, fromOwnerId: ownerId, fromZone: zone });
    el.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      const items = [
        { label: t("inspect"), onSelect: () => showInspect(cardId) },
        { separator: true },
        { label: t("playFaceUp"), onSelect: () => playFromZone(ownerId, zone, cardId, true) },
        { label: t("playFaceDown"), onSelect: () => playFromZone(ownerId, zone, cardId, false) },
        { separator: true },
      ];
      ZONES.filter((z) => z !== zone).forEach((z) => {
        items.push({
          label: `${t("moveTo")} ${t(z)}`,
          onSelect: () => send({ type: "move_card", fromOwnerId: ownerId, fromZone: zone, toOwnerId: ownerId, toZone: z, cardId }),
        });
      });
      showContextMenu(event.clientX, event.clientY, items);
    });
  });
  $$("[data-preview-card]").forEach((el) => {
    el.addEventListener("mouseenter", () => showCardPreview(el.dataset.previewCard, el));
    el.addEventListener("mouseleave", hideCardPreview);
  });
}

let cardPreviewEl = null;

function showCardPreview(cardId, anchorEl) {
  hideCardPreview();
  const img = cardImage(cardId);
  if (!img) return;
  const el = document.createElement("div");
  el.className = "card-preview";
  el.innerHTML = `<img src="${esc(img)}" alt="">`;
  document.body.appendChild(el);
  const rect = anchorEl.getBoundingClientRect();
  let left = rect.right + 10;
  if (left + 180 > window.innerWidth) left = rect.left - 190;
  let top = Math.min(rect.top, window.innerHeight - 260);
  el.style.left = Math.max(4, left) + "px";
  el.style.top = Math.max(4, top) + "px";
  cardPreviewEl = el;
}

function hideCardPreview() {
  if (cardPreviewEl) cardPreviewEl.remove();
  cardPreviewEl = null;
}

function playFromZone(ownerId, zone, cardId, faceUp) {
  const view = fieldCenterLogical();
  const center = flipY(view.x, view.y);
  send({
    type: "place_card", ownerId, fromZone: zone, cardId, faceUp,
    x: center.x - 75 + Math.random() * 80 - 40, y: center.y - 105 + Math.random() * 80 - 40,
  });
}

// ---------------------------------------------------------------- drag and drop

let lastDropHighlight = null;

function dropTargetElAt(x, y) {
  const el = document.elementFromPoint(x, y);
  return el && el.closest("[data-drop-zone], #battlefieldWrap, #myHandTray");
}

function highlightDropTargetAt(x, y) {
  const target = dropTargetElAt(x, y);
  if (target === lastDropHighlight) return;
  clearDropHighlights();
  if (target) {
    target.classList.add("drop-target-active");
    lastDropHighlight = target;
  }
}

function clearDropHighlights() {
  if (lastDropHighlight) lastDropHighlight.classList.remove("drop-target-active");
  lastDropHighlight = null;
}

// A drop landing exactly on another (non-stacked) battlefield card stacks
// onto it instead of placing/moving freely — see stackedScreenPos for how
// that's rendered. Chains are deliberately not supported (only "free" cards
// can be an anchor), which also rules out any possibility of a cycle.
function stackAnchorAt(el, excludeItemId) {
  const cardEl = el.closest(".bf-card");
  if (!cardEl || cardEl.dataset.itemId === excludeItemId) return null;
  const anchorItem = latestState.battlefield.find((it) => it.id === cardEl.dataset.itemId);
  if (!anchorItem || anchorItem.stackedOn) return null;
  return { anchorEl: cardEl, anchorId: anchorItem.id };
}

// Offset of a new card's top-left from the anchor's top-left, in the same
// board-logical units as x/y — deliberately NOT run through flipY, since the
// whole point is that this offset must look identical to both viewers.
function stackOffsetFrom(anchorEl, clientX, clientY) {
  const rect = anchorEl.getBoundingClientRect();
  return { x: (clientX - rect.left) / zoomLevel - 75, y: (clientY - rect.top) / zoomLevel - 105 };
}

function resolveDrop(ctx, clientX, clientY) {
  const el = document.elementFromPoint(clientX, clientY);
  if (!el) return;
  const zoneEl = el.closest("[data-drop-zone]");
  const fieldEl = el.closest("#battlefieldWrap");
  const handEl = el.closest("#myHandTray");

  if (ctx.kind === "battlefield") {
    if (zoneEl) {
      const [toOwnerId, toZone] = zoneEl.dataset.dropZone.split(":");
      send({ type: "remove_battlefield_item", itemId: ctx.itemId, toOwnerId, toZone });
    } else if (handEl) {
      send({ type: "remove_battlefield_item", itemId: ctx.itemId, toOwnerId: myPlayerId, toZone: "hand" });
    } else if (fieldEl) {
      const anchor = stackAnchorAt(el, ctx.itemId);
      if (anchor) {
        const offset = stackOffsetFrom(anchor.anchorEl, clientX, clientY);
        send({ type: "move_battlefield_item", itemId: ctx.itemId, stackOnId: anchor.anchorId, offsetX: offset.x, offsetY: offset.y });
      } else {
        const rect = fieldEl.getBoundingClientRect();
        const logical = flipY((clientX - rect.left - panX) / zoomLevel - 75, (clientY - rect.top - panY) / zoomLevel - 105, PILE_W, PILE_H);
        // an explicit unstack, not just an absent stackOnId: dropping in open
        // space is the "detach" gesture, unlike e.g. exhaust which also omits
        // stackOnId but must NOT detach a stacked card as a side effect
        send({ type: "move_battlefield_item", itemId: ctx.itemId, x: logical.x, y: logical.y, unstack: true });
      }
    }
    return;
  }

  // ctx.kind === "card": a card dragged from hand or from an open zone popover.
  // handEl must be checked before fieldEl: the hand area now overlays the
  // board, so #battlefieldWrap is an ancestor of the hand tray too.
  if (zoneEl) {
    const [toOwnerId, toZone] = zoneEl.dataset.dropZone.split(":");
    if (toOwnerId === ctx.fromOwnerId && toZone === ctx.fromZone) return;
    send({ type: "move_card", fromOwnerId: ctx.fromOwnerId, fromZone: ctx.fromZone, toOwnerId, toZone, cardId: ctx.cardId });
  } else if (handEl) {
    if (ctx.fromZone === "hand") reorderHandDrop(ctx.cardId, clientX);
    else send({ type: "move_card", fromOwnerId: ctx.fromOwnerId, fromZone: ctx.fromZone, toOwnerId: myPlayerId, toZone: "hand", cardId: ctx.cardId });
  } else if (fieldEl) {
    const rect = fieldEl.getBoundingClientRect();
    const logical = flipY((clientX - rect.left - panX) / zoomLevel - 75, (clientY - rect.top - panY) / zoomLevel - 105, PILE_W, PILE_H);
    const anchor = stackAnchorAt(el, null);
    if (anchor) {
      // x/y still sent as a fallback position (this is a BRAND NEW item, so
      // there's no earlier "before it was stacked" position to freeze on)
      const offset = stackOffsetFrom(anchor.anchorEl, clientX, clientY);
      send({ type: "place_card", ownerId: ctx.fromOwnerId, fromZone: ctx.fromZone, cardId: ctx.cardId, faceUp: true, x: logical.x, y: logical.y, stackOnId: anchor.anchorId, offsetX: offset.x, offsetY: offset.y });
    } else {
      send({ type: "place_card", ownerId: ctx.fromOwnerId, fromZone: ctx.fromZone, cardId: ctx.cardId, faceUp: true, x: logical.x, y: logical.y });
    }
  }
}

function reorderHandDrop(cardId, clientX) {
  const meId = isObserver ? null : myPlayerId;
  if (!meId || !latestState.players[meId]) return;
  const cards = latestState.players[meId].zones.hand.cards || [];
  const order = cards.filter((cid) => cid !== cardId);
  const otherEls = [...document.querySelectorAll("#myHandTray [data-hand-card]")].filter((el) => el.dataset.handCard !== cardId);
  let insertAt = order.length;
  for (let i = 0; i < otherEls.length; i++) {
    const rect = otherEls[i].getBoundingClientRect();
    if (clientX < rect.left + rect.width / 2) { insertAt = i; break; }
  }
  order.splice(insertAt, 0, cardId);
  send({ type: "reorder", zone: "hand", order });
}

function bindCardDragSource(el, ctx) {
  el.addEventListener("pointerdown", (event) => {
    if (event.target.closest("button, select")) return;
    event.preventDefault();
    const startX = event.clientX, startY = event.clientY;
    let moved = false;
    let ghost = null;
    const move = (e) => {
      if (!moved && (Math.abs(e.clientX - startX) > 4 || Math.abs(e.clientY - startY) > 4)) {
        moved = true;
        ghost = buildDragGhost(ctx, el);
      }
      if (moved) {
        highlightDropTargetAt(e.clientX, e.clientY);
        moveGhostTo(ghost, e.clientX, e.clientY);
      }
    };
    const up = (e) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      clearDropHighlights();
      removeGhost(ghost);
      if (moved) resolveDrop(ctx, e.clientX, e.clientY);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  });
}

// ---------------------------------------------------------------- context menu

let activeContextMenu = null;
let activeCardLabels = [];

function closeContextMenu() {
  if (activeContextMenu) activeContextMenu.remove();
  activeContextMenu = null;
  document.removeEventListener("pointerdown", closeContextMenuOnOutsideClick, true);
  activeCardLabels.forEach((el) => el.remove());
  activeCardLabels = [];
}

// Floating labels shown alongside a battlefield card's right-click menu: the
// card's name above it (only when its identity is actually knowable to this
// viewer) and its owner's name below-right of it (always). Tied to the
// context menu's lifecycle since they're only ever shown together.
function showCardLabels(cardEl, nameText, ownerText) {
  const rect = cardEl.getBoundingClientRect();
  if (nameText) {
    const nameEl = document.createElement("div");
    nameEl.className = "bf-float-label bf-name-label";
    nameEl.textContent = nameText;
    document.body.appendChild(nameEl);
    nameEl.style.left = rect.left + rect.width / 2 + "px";
    nameEl.style.top = rect.top - 8 + "px";
    activeCardLabels.push(nameEl);
  }
  if (ownerText) {
    const ownerEl = document.createElement("div");
    ownerEl.className = "bf-float-label bf-owner-label";
    ownerEl.textContent = ownerText;
    document.body.appendChild(ownerEl);
    ownerEl.style.left = rect.left + "px";
    ownerEl.style.top = rect.bottom + 4 + "px";
    activeCardLabels.push(ownerEl);
  }
}

function closeContextMenuOnOutsideClick(event) {
  if (activeContextMenu && !activeContextMenu.contains(event.target)) closeContextMenu();
}

// Items are normally { label, onSelect } (closes the menu on click) or
// { separator: true }. A few extra, general-purpose fields/shapes support
// richer content without special-casing any one caller:
//   { label, onSelect, keepOpen: true } — stays open after clicking, so a
//     repeatable action (e.g. +1 counter) can be clicked several times in a row.
//   { label, onSelect, highlight: true } — visually emphasized (e.g. "flip"
//     when the card is currently face-down, the action most people want next).
//   { html, afterRender: (containerEl) => {...} } — raw markup (e.g. a whole
//     counter grid) inserted as-is; afterRender wires up its own listeners
//     since it isn't a single label+action.
function showContextMenu(clientX, clientY, items) {
  closeContextMenu();
  const menu = document.createElement("div");
  menu.className = "ctx-menu";
  menu.style.left = clientX + "px";
  menu.style.top = clientY + "px";
  menu.innerHTML = items
    .map((item, i) => {
      if (item.separator) return `<div class="ctx-sep"></div>`;
      if (item.html) return `<div data-ctx-item="${i}">${item.html}</div>`;
      return `<button data-ctx-item="${i}"${item.highlight ? ' class="ctx-highlight"' : ""}>${esc(item.label)}</button>`;
    })
    .join("");
  document.body.appendChild(menu);
  items.forEach((item, i) => {
    if (item.separator) return;
    const container = menu.querySelector(`[data-ctx-item="${i}"]`);
    if (item.html) {
      if (item.afterRender) item.afterRender(container);
      return;
    }
    container.onclick = () => {
      if (!item.keepOpen) closeContextMenu();
      item.onSelect();
    };
  });
  const rect = menu.getBoundingClientRect();
  if (rect.right > window.innerWidth) menu.style.left = Math.max(4, window.innerWidth - rect.width - 4) + "px";
  if (rect.bottom > window.innerHeight) menu.style.top = Math.max(4, window.innerHeight - rect.height - 4) + "px";
  activeContextMenu = menu;
  setTimeout(() => document.addEventListener("pointerdown", closeContextMenuOnOutsideClick, true), 0);
}

// ---------------------------------------------------------------- zoom + pan
// The whole board (background + piles + cards + tokens) lives in #battlefield,
// a fixed 1549x1549 layer (matching the playmat art's native resolution) that
// is translated/scaled as one unit. There is no native scrolling anywhere —
// the wheel zooms (anchored on the cursor) and dragging empty field space pans.

const BOARD_SIZE = 1549;
let zoomLevel = 1;
let panX = 0;
let panY = 0;

// ---------------------------------------------------------------- seat-based display flip
// Each player should see their OWN side near the bottom of the screen and
// their opponent near the top. Two different mechanisms do that, for two
// different kinds of object:
//
// - Fixed PILE slots use no transform at all any more: PILE_SCREEN_POS holds
//   a screen position per (viewer's seat, pile owner's seat, zone) directly.
//   An earlier version derived the "away" seat's positions from the "near"
//   seat's through a single mirror axis, but dragging a pile while actually
//   viewing it directly vs. viewing that same pile from the OTHER seat
//   (mirrored) measurably didn't agree on one "correct" spot — no single axis
//   reproduces the printed art from both viewpoints, so there's a value per
//   (viewer, owner) pair instead, with nothing computed at render time.
//
// - flipY (vertical-only reflection, x untouched) is for everything a player
//   places freely: battlefield cards (incl. token-cards), tokens, and draw
//   strokes. A full 180° reflection would also mirror left/right between
//   multiple such objects, so two cards deliberately arranged/overlapped by
//   one player would look left-right flipped to the other. Since nothing
//   forces these free-floating objects to match a printed slot, there's no
//   reason to flip x for them at all — only y, so each player still sees
//   their own side near the bottom. The mirror axis (812) was re-derived from
//   the live-rendered slot labels' own centres, not the canvas centre
//   (774.5) and not raw pixel-alpha sampling of the art (both tried first).
//
// flipY's one extra rule: a stored (x,y) is always a box's CSS top-left,
// never a bare point. Reflecting a box's top-left across an axis lands on
// the OPPOSITE corner unless the box's own width/height is subtracted back
// out — otherwise every flipped position is off by exactly that box's size.
// Pass the object's width/height for anything box-shaped; leave them at 0
// for bare points (stroke points, view-centres) which need no such correction.
const MIRROR_CENTER_Y = 812;
const PILE_W = 150, PILE_H = 210;
const TOKEN_W = 52, TOKEN_H = 52;

function mySeat() {
  if (isObserver || !myPlayerId || !latestState) return 0;
  return latestState.players[myPlayerId]?.seat || 0;
}

function flipY(x, y, w = 0, h = 0) {
  return mySeat() === 1 ? { x, y: 2 * effectiveMirrorCenterY() - h - y } : { x, y };
}

function applyTransform() {
  $("#battlefield").style.transform = `translate(${panX}px, ${panY}px) scale(${zoomLevel})`;
  $("#zoomResetBtn").textContent = Math.round(zoomLevel * 100) + "%";
}

function setZoomAt(newZoom, anchorClientX, anchorClientY) {
  const rect = $("#battlefieldWrap").getBoundingClientRect();
  const ax = anchorClientX - rect.left;
  const ay = anchorClientY - rect.top;
  const oldZoom = zoomLevel;
  zoomLevel = Math.min(3, Math.max(0.3, newZoom));
  const logicalX = (ax - panX) / oldZoom;
  const logicalY = (ay - panY) / oldZoom;
  panX = ax - logicalX * zoomLevel;
  panY = ay - logicalY * zoomLevel;
  applyTransform();
}

function setZoom(newZoom) {
  const rect = $("#battlefieldWrap").getBoundingClientRect();
  setZoomAt(newZoom, rect.left + rect.width / 2, rect.top + rect.height / 2);
}

function fieldCenterLogical() {
  const rect = $("#battlefieldWrap").getBoundingClientRect();
  return { x: (rect.width / 2 - panX) / zoomLevel, y: (rect.height / 2 - panY) / zoomLevel };
}

function centerBoardInView() {
  const wrap = $("#battlefieldWrap");
  // fit the whole board in view on first load, then centre it
  zoomLevel = Math.min(3, Math.max(0.3, Math.min(wrap.clientWidth / BOARD_SIZE, wrap.clientHeight / BOARD_SIZE)));
  panX = wrap.clientWidth / 2 - (BOARD_SIZE / 2) * zoomLevel;
  panY = wrap.clientHeight / 2 - (BOARD_SIZE / 2) * zoomLevel;
  applyTransform();
}

function initZoomControls() {
  $("#zoomInBtn").title = t("zoomIn");
  $("#zoomOutBtn").title = t("zoomOut");
  $("#zoomResetBtn").title = t("zoomReset");
  $("#zoomInBtn").onclick = () => setZoom(zoomLevel + 0.15);
  $("#zoomOutBtn").onclick = () => setZoom(zoomLevel - 0.15);
  $("#zoomResetBtn").onclick = () => setZoom(1);

  const wrap = $("#battlefieldWrap");
  wrap.addEventListener(
    "wheel",
    (event) => {
      event.preventDefault();
      setZoomAt(zoomLevel + (event.deltaY < 0 ? 0.1 : -0.1), event.clientX, event.clientY);
    },
    { passive: false }
  );

  wrap.addEventListener("pointerdown", (event) => {
    if (event.target !== wrap && event.target !== $("#battlefield")) return;
    event.preventDefault();
    const startX = event.clientX, startY = event.clientY;
    const startPanX = panX, startPanY = panY;
    const move = (e) => {
      panX = startPanX + (e.clientX - startX);
      panY = startPanY + (e.clientY - startY);
      applyTransform();
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  });
}

// ---------------------------------------------------------------- drag ghost

function buildDragGhost(ctx, sourceEl) {
  const ghost = document.createElement("div");
  ghost.className = "drag-ghost";
  ghost.style.width = "150px";
  ghost.style.height = "210px";
  if (ctx.kind === "battlefield") {
    const inner = sourceEl.querySelector("img, .back-face");
    ghost.innerHTML = inner ? inner.outerHTML : "";
  } else {
    const img = cardImage(ctx.cardId);
    ghost.innerHTML = img ? `<img src="${esc(img)}">` : `<div class="back-face">${esc(cardName(ctx.cardId))}</div>`;
  }
  document.body.appendChild(ghost);
  return ghost;
}

function moveGhostTo(ghost, clientX, clientY) {
  if (!ghost) return;
  ghost.style.left = clientX - parseFloat(ghost.style.width) / 2 + "px";
  ghost.style.top = clientY - parseFloat(ghost.style.height) / 2 + "px";
}

function removeGhost(ghost) {
  if (ghost) ghost.remove();
}

// ---------------------------------------------------------------- drawing tool
// Strokes are stored server-side in logical/real board coordinates (like
// battlefield items and tokens), so flipY converts both when capturing input
// and when rendering. The SVG layer sits inside #battlefield, so it inherits
// the pan/zoom transform automatically — only the screen -> local-canvas step
// needs the manual pan/zoom math.

let drawMode = null; // null | "draw" | "erase"
let strokeUndoStack = [];
let strokeRedoStack = [];

function setDrawMode(mode) {
  drawMode = mode;
  $("#drawPenBtn").classList.toggle("active", mode === "draw");
  $("#drawEraseBtn").classList.toggle("active", mode === "erase");
  $("#drawLayer").classList.toggle("mode-draw", mode === "draw");
  $("#drawLayer").classList.toggle("mode-erase", mode === "erase");
  $("#battlefieldWrap").classList.toggle("mode-draw", mode === "draw");
  $("#battlefieldWrap").classList.toggle("mode-erase", mode === "erase");
}

function makeSvgEl(tag, attrs) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
  return el;
}

function initDrawTool() {
  const svg = $("#drawLayer");
  svg.setAttribute("viewBox", `0 0 ${BOARD_SIZE} ${BOARD_SIZE}`);

  $("#drawPenBtn").onclick = () => setDrawMode(drawMode === "draw" ? null : "draw");
  $("#drawEraseBtn").onclick = () => setDrawMode(drawMode === "erase" ? null : "erase");
  $("#drawUndoBtn").onclick = undoStroke;
  $("#drawRedoBtn").onclick = redoStroke;
  $("#drawClearBtn").onclick = () => send({ type: "clear_own_strokes" });

  let livePoints = [];
  let liveEl = null;
  let eraseStartDisplay = null;
  let eraseRectEl = null;

  svg.addEventListener("pointerdown", (event) => {
    if (!drawMode) return;
    event.preventDefault();
    event.stopPropagation();
    const rect = $("#battlefieldWrap").getBoundingClientRect();
    const toDisplayPt = (cx, cy) => ({ x: (cx - rect.left - panX) / zoomLevel, y: (cy - rect.top - panY) / zoomLevel });

    if (drawMode === "draw") {
      livePoints = [toDisplayPt(event.clientX, event.clientY)];
      liveEl = makeSvgEl("polyline", { fill: "none", stroke: playerColor(myPlayerId), "stroke-width": 4, "stroke-linecap": "round", "stroke-linejoin": "round", points: "" });
      svg.appendChild(liveEl);
    } else {
      eraseStartDisplay = toDisplayPt(event.clientX, event.clientY);
      eraseRectEl = makeSvgEl("rect", { class: "erase-rect", x: eraseStartDisplay.x, y: eraseStartDisplay.y, width: 0, height: 0 });
      svg.appendChild(eraseRectEl);
    }

    const move = (e) => {
      const p = toDisplayPt(e.clientX, e.clientY);
      if (drawMode === "draw") {
        livePoints.push(p);
        liveEl.setAttribute("points", livePoints.map((pt) => `${pt.x},${pt.y}`).join(" "));
      } else if (eraseRectEl) {
        eraseRectEl.setAttribute("x", Math.min(eraseStartDisplay.x, p.x));
        eraseRectEl.setAttribute("y", Math.min(eraseStartDisplay.y, p.y));
        eraseRectEl.setAttribute("width", Math.abs(p.x - eraseStartDisplay.x));
        eraseRectEl.setAttribute("height", Math.abs(p.y - eraseStartDisplay.y));
      }
    };
    const up = (e) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      if (drawMode === "draw") {
        if (liveEl) liveEl.remove();
        if (livePoints.length > 1) {
          const id = "s" + Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
          const logicalPoints = livePoints.map((p) => flipY(p.x, p.y)).map((p) => [p.x, p.y]);
          strokeUndoStack.push(id);
          strokeRedoStack = [];
          send({ type: "add_stroke", id, points: logicalPoints, color: playerColor(myPlayerId) });
        }
        liveEl = null; livePoints = [];
      } else {
        if (eraseRectEl) eraseRectEl.remove();
        const p = toDisplayPt(e.clientX, e.clientY);
        const a = flipY(eraseStartDisplay.x, eraseStartDisplay.y);
        const b = flipY(p.x, p.y);
        send({ type: "remove_strokes_in_rect", x0: a.x, y0: a.y, x1: b.x, y1: b.y });
        eraseRectEl = null; eraseStartDisplay = null;
      }
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  });
}

// ---------------------------------------------------------------- token cards

let selectedTemperament = null;

function initTokenToolbar() {
  $("#tokenTemperamentGrid").innerHTML = TEMPERAMENTS.map(
    (temp) => `<button data-temperament="${esc(temp.key)}"><img src="${esc(temperamentSymbol(temp.key))}" alt="">${esc(t("temperament" + temp.key[0].toUpperCase() + temp.key.slice(1)))}</button>`
  ).join("");
  $$("#tokenTemperamentGrid button").forEach((btn) => {
    btn.onclick = () => {
      selectedTemperament = btn.dataset.temperament;
      $$("#tokenTemperamentGrid button").forEach((b) => b.classList.toggle("active", b === btn));
    };
  });

  $("#createTokenBtn").onclick = () => {
    selectedTemperament = null;
    $$("#tokenTemperamentGrid button").forEach((b) => b.classList.remove("active"));
    $("#tokenPowerInput").value = 1;
    $("#tokenPanel").classList.remove("hidden");
  };
  $("#tokenCancelBtn").onclick = () => $("#tokenPanel").classList.add("hidden");
  $("#tokenCreateBtn").onclick = () => {
    if (!selectedTemperament) return;
    const power = Math.max(-20, Math.min(20, Math.round(Number($("#tokenPowerInput").value) || 0)));
    const view = fieldCenterLogical();
    const center = flipY(view.x, view.y);
    send({
      type: "create_token_card", temperament: selectedTemperament, power,
      x: center.x - 75 + Math.random() * 60 - 30, y: center.y - 105 + Math.random() * 60 - 30,
    });
    $("#tokenPanel").classList.add("hidden");
  };
}

let selectedEssenceTemperament = null;

function initEssenceToolbar() {
  $("#createEssenceBtn").textContent = "✨";
  $("#essenceTemperamentGrid").innerHTML = TEMPERAMENTS.map(
    (temp) => `<button data-temperament="${esc(temp.key)}"><img src="${esc(temperamentSymbol(temp.key))}" alt="">${esc(t("temperament" + temp.key[0].toUpperCase() + temp.key.slice(1)))}</button>`
  ).join("");
  $$("#essenceTemperamentGrid button").forEach((btn) => {
    btn.onclick = () => {
      selectedEssenceTemperament = btn.dataset.temperament;
      $$("#essenceTemperamentGrid button").forEach((b) => b.classList.toggle("active", b === btn));
    };
  });

  $("#createEssenceBtn").onclick = () => {
    selectedEssenceTemperament = null;
    $$("#essenceTemperamentGrid button").forEach((b) => b.classList.remove("active"));
    $("#essenceCountInput").value = 1;
    $("#essencePanel").classList.remove("hidden");
  };
  $("#essenceCancelBtn").onclick = () => $("#essencePanel").classList.add("hidden");
  $("#essenceCreateBtn").onclick = () => {
    if (!selectedEssenceTemperament) return;
    const count = Math.max(-99, Math.min(99, Math.round(Number($("#essenceCountInput").value) || 0)));
    const view = fieldCenterLogical();
    const center = flipY(view.x, view.y);
    send({
      type: "create_essence_token", temperament: selectedEssenceTemperament, count,
      x: center.x - 26 + Math.random() * 60 - 30, y: center.y - 26 + Math.random() * 60 - 30,
    });
    $("#essencePanel").classList.add("hidden");
  };
}

let selectedDiceMode = "d6";

function initDiceToolbar() {
  $("#createDiceBtn").title = t("createDice");
  $("#dicePanelHeading").textContent = t("dicePanelHeading");
  $("#diceCountLabel").textContent = t("diceCountLabel");
  $("#diceRollBtn").textContent = t("diceRollBtn");
  $("#diceCancelBtn").textContent = t("close");
  $("#diceResultCloseBtn").textContent = t("close");
  $$("#diceModeGrid button").forEach((btn) => {
    btn.textContent = (btn.dataset.diceMode === "d6" ? "🎲 " : "🪙 ") + t(btn.dataset.diceMode === "d6" ? "diceModeD6" : "diceModeCoin");
    btn.onclick = () => {
      selectedDiceMode = btn.dataset.diceMode;
      $$("#diceModeGrid button").forEach((b) => b.classList.toggle("active", b === btn));
    };
  });
  $("#createDiceBtn").onclick = () => {
    selectedDiceMode = "d6";
    $$("#diceModeGrid button").forEach((b) => b.classList.toggle("active", b.dataset.diceMode === "d6"));
    $("#diceCountInput").value = 1;
    $("#diceConfigView").classList.remove("hidden");
    $("#diceResultView").classList.add("hidden");
    $("#dicePanel").classList.remove("hidden");
  };
  $("#diceCancelBtn").onclick = () => $("#dicePanel").classList.add("hidden");
  $("#diceResultCloseBtn").onclick = () => $("#dicePanel").classList.add("hidden");
  $("#diceRollBtn").onclick = () => {
    const count = Math.max(1, Math.min(20, Math.round(Number($("#diceCountInput").value) || 1)));
    send({ type: "roll_dice", mode: selectedDiceMode, count });
  };
}

function diceResultDisplayHtml(msg) {
  if (msg.mode === "d6") {
    const sum = msg.results.reduce((a, b) => a + b, 0);
    return `<div class="dice-result-values">🎲 ${esc(msg.results.join(", "))}</div><div class="dice-result-total">${esc(t("diceTotal"))} ${sum}</div>`;
  }
  const labels = msg.results.map((r) => t(r === "H" ? "coinHeads" : "coinTails"));
  return `<div class="dice-result-values">🪙 ${esc(labels.join(", "))}</div>`;
}

// Own roll: shown persistently INSIDE the (already-open, non-blocking) dice
// panel — it stays up until closed, instead of auto-hiding, so it can be
// reread/screenshotted mid-game. Someone else's roll: this client never had
// that panel open, so it gets its own small bubble instead — same idea
// (broadcast + logged, just as trustworthy as a reveal), closed individually
// whenever they're done with it rather than auto-fading like a plain toast.
function handleDiceResult(msg) {
  if (!isObserver && msg.byId === myPlayerId) {
    $("#diceResultHeading").textContent = t("dicePanelHeading");
    $("#diceResultDisplay").innerHTML = diceResultDisplayHtml(msg);
    $("#diceConfigView").classList.add("hidden");
    $("#diceResultView").classList.remove("hidden");
    $("#dicePanel").classList.remove("hidden");
  } else {
    showDiceBubble(msg);
  }
}

function showDiceBubble(msg) {
  let box = document.querySelector("#diceBubbles");
  if (!box) {
    box = document.createElement("div");
    box.className = "dice-bubbles";
    box.id = "diceBubbles";
    document.body.appendChild(box);
  }
  const bubble = document.createElement("div");
  bubble.className = "dice-bubble";
  const modeLabel = msg.mode === "d6" ? t("diceModeD6") : t("diceModeCoin");
  bubble.innerHTML = `<button class="dice-bubble-close">×</button><div>${esc(msg.byName || "?")} — ${esc(modeLabel)}</div>${diceResultDisplayHtml(msg)}`;
  bubble.querySelector(".dice-bubble-close").onclick = () => bubble.remove();
  box.appendChild(bubble);
}

function undoStroke() {
  const id = strokeUndoStack.pop();
  if (!id) return;
  const stroke = (latestState?.strokes || []).find((s) => s.id === id);
  if (stroke) strokeRedoStack.push(stroke);
  send({ type: "remove_stroke", strokeId: id });
}

function redoStroke() {
  const stroke = strokeRedoStack.pop();
  if (!stroke) return;
  strokeUndoStack.push(stroke.id);
  send({ type: "add_stroke", id: stroke.id, points: stroke.points, color: stroke.color });
}

function renderStrokes() {
  const svg = $("#drawLayer");
  svg.querySelectorAll("polyline").forEach((el) => el.remove());
  (latestState.strokes || []).forEach((s) => {
    const pts = s.points.map(([x, y]) => flipY(x, y));
    const poly = makeSvgEl("polyline", {
      fill: "none", stroke: s.color || playerColor(s.ownerId), "stroke-width": 4,
      "stroke-linecap": "round", "stroke-linejoin": "round",
      points: pts.map((p) => `${p.x},${p.y}`).join(" "),
    });
    svg.appendChild(poly);
  });
}

// ---------------------------------------------------------------- simple animations

function pulseZone(ownerId, zone) {
  const el = document.querySelector(`[data-field-pile="${ownerId}:${zone}"] .pile-card`);
  if (!el) return;
  el.classList.remove("ko-shuffle");
  void el.offsetWidth;
  el.classList.add("ko-shuffle");
}

// ---------------------------------------------------------------- reveal/scry resize

const REVEAL_SIZE_KEY = "ko_reveal_card_w";
const REVEAL_SIZE_MAX = 400;
let revealCardWidth = Math.min(REVEAL_SIZE_MAX, Math.max(90, Number(localStorage.getItem(REVEAL_SIZE_KEY)) || 190));

function applyRevealCardWidth() {
  document.documentElement.style.setProperty("--reveal-card-w", revealCardWidth + "px");
}

function initRevealResize() {
  applyRevealCardWidth();
  $("#revealResizeHandle").addEventListener("pointerdown", (event) => {
    event.preventDefault();
    const startY = event.clientY;
    const startWidth = revealCardWidth;
    const move = (e) => {
      // unlike the hand's handle (above its tray), this one sits BELOW the
      // card row, so dragging away from the content (down) is what should grow it
      revealCardWidth = Math.min(REVEAL_SIZE_MAX, Math.max(90, startWidth + (e.clientY - startY)));
      applyRevealCardWidth();
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      localStorage.setItem(REVEAL_SIZE_KEY, String(revealCardWidth));
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  });
  $("#revealCards").addEventListener(
    "wheel",
    (event) => {
      event.preventDefault();
      event.stopPropagation();
      if ($("#revealCards").scrollWidth > $("#revealCards").clientWidth) {
        $("#revealCards").scrollLeft += event.deltaY;
      }
    },
    { passive: false }
  );
}

// ---------------------------------------------------------------- hand-view resize

const HAND_VIEW_SIZE_KEY = "ko_hand_view_card_h";
const HAND_VIEW_SIZE_MAX = 500;
let handViewCardHeight = Math.min(HAND_VIEW_SIZE_MAX, Math.max(100, Number(localStorage.getItem(HAND_VIEW_SIZE_KEY)) || 182));

function applyHandViewCardHeight() {
  document.documentElement.style.setProperty("--hv-card-h", handViewCardHeight + "px");
}

function initHandViewResize() {
  applyHandViewCardHeight();
  $("#handViewResizeHandle").addEventListener("pointerdown", (event) => {
    event.preventDefault();
    const startY = event.clientY;
    const startHeight = handViewCardHeight;
    const move = (e) => {
      // handle sits below the card row, same as the reveal panel's — dragging down grows it
      handViewCardHeight = Math.min(HAND_VIEW_SIZE_MAX, Math.max(100, startHeight + (e.clientY - startY)));
      applyHandViewCardHeight();
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      localStorage.setItem(HAND_VIEW_SIZE_KEY, String(handViewCardHeight));
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  });
}

// ---------------------------------------------------------------- hand resize

const HAND_SIZE_KEY = "ko_hand_card_h";
const HAND_SIZE_MAX = 720;
let handCardHeight = Math.min(HAND_SIZE_MAX, Math.max(70, Number(localStorage.getItem(HAND_SIZE_KEY)) || 170));

function applyHandCardHeight() {
  document.documentElement.style.setProperty("--hand-card-h", handCardHeight + "px");
  // hover should make a card easier to read, not comically huge: a full 30%
  // bump for a normal-sized hand, but capped to +80 logical px once the hand
  // is already large, so an already-huge hand doesn't get even huger
  const hoverScale = Math.min(1.3, (handCardHeight + 80) / handCardHeight);
  document.documentElement.style.setProperty("--hand-hover-scale", hoverScale.toFixed(3));
  // the tray's own top padding is reserved headroom for that same hover grow
  // (half the height increase, since the scale is centered, plus the hover's
  // 10px lift) — computed from the current card height/scale instead of a
  // fixed guess, so it's never more than exactly what's needed to avoid
  // clipping the grown card against the tray's overflow:hidden
  const topPad = Math.ceil((handCardHeight * (hoverScale - 1)) / 2 + 10 + 4);
  document.documentElement.style.setProperty("--hand-tray-top-pad", topPad + "px");
}

function initHandResize() {
  applyHandCardHeight();
  $("#handResizeHandle").addEventListener("pointerdown", (event) => {
    event.preventDefault();
    const startY = event.clientY;
    const startHeight = handCardHeight;
    const move = (e) => {
      handCardHeight = Math.min(HAND_SIZE_MAX, Math.max(70, startHeight + (startY - e.clientY)));
      applyHandCardHeight();
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      localStorage.setItem(HAND_SIZE_KEY, String(handCardHeight));
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  });
  // cards can get big enough that they don't all fit — let the wheel scroll
  // sideways instead of doing nothing (there's no vertical overflow to scroll).
  // Always stop it here regardless: the hand tray now lives INSIDE
  // #battlefieldWrap, so an un-stopped wheel event bubbles up into the
  // board's own wheel handler and zooms the field instead.
  $("#myHandTray").addEventListener(
    "wheel",
    (event) => {
      event.preventDefault();
      event.stopPropagation();
      if ($("#myHandTray").scrollWidth > $("#myHandTray").clientWidth) {
        $("#myHandTray").scrollLeft += event.deltaY;
      }
    },
    { passive: false }
  );
}

// ---------------------------------------------------------------- battlefield

function counterCircles(counters) {
  return Object.entries(counters || {})
    .filter(([, v]) => v)
    .map(([k, v]) => `<span class="bf-counter${k === "tempCounter" ? " bf-counter-temp" : ""}">${v > 0 ? "+" : ""}${v}</span>`)
    .join("");
}

// A two-column +1/-1/reset grid for a card/token's counters: one column for
// its existing "permanent" counter (power/mark/essence — whichever this
// entity already used before), one for a new, generic "temporary" counter
// alongside it. Returned as a showContextMenu html+afterRender item so the
// menu stays open across repeated clicks (see showContextMenu's own doc).
function counterGridMenuItem(permKey, target) {
  const col = (key, labelKey, cls) => `
    <div class="counter-col ${cls}">
      <div class="counter-col-label">${esc(t(labelKey))}</div>
      <div class="counter-col-btns">
        <button data-counter-key="${esc(key)}" data-counter-op="sub">−1</button>
        <button data-counter-key="${esc(key)}" data-counter-op="add">+1</button>
      </div>
      <button class="counter-reset-btn" data-counter-key="${esc(key)}" data-counter-op="reset">${esc(t("removeCounters"))}</button>
    </div>`;
  return {
    html: `<div class="counter-grid">${col(permKey, "permanentCounter", "counter-col-perm")}${col("tempCounter", "temporaryCounter", "counter-col-temp")}</div>`,
    afterRender: (container) => {
      container.querySelectorAll("[data-counter-op]").forEach((btn) => {
        btn.onclick = (event) => {
          event.stopPropagation();
          const key = btn.dataset.counterKey;
          if (btn.dataset.counterOp === "reset") send({ type: "reset_counter", ...target, counterKey: key });
          else send({ type: "add_counter", ...target, counterKey: key, delta: btn.dataset.counterOp === "add" ? 1 : -1 });
        };
      });
    },
  };
}

// A stacked card's own x/y is a frozen fallback (wherever it was before being
// stacked — see apply_stack_fields server-side), not its live position: while
// stacked, it's rendered relative to its anchor's CURRENT screen position
// instead. Crucially the offset itself is never flipped (see flipY's own
// comment) — it's captured directly in screen pixels, so a deliberate overlap
// arrangement looks identical to both players regardless of seat.
function stackedScreenPos(item) {
  if (!item.stackedOn) return null;
  const anchor = latestState.battlefield.find((it) => it.id === item.stackedOn);
  if (!anchor) return null;
  const anchorPos = stackedScreenPos(anchor) || flipY(anchor.x, anchor.y, PILE_W, PILE_H);
  return { x: anchorPos.x + item.stackOffsetX, y: anchorPos.y + item.stackOffsetY };
}

function renderBattlefield() {
  renderPiles();
  const bf = $("#battlefield");
  bf.querySelectorAll(".bf-card, .bf-token").forEach((el) => el.remove());

  latestState.battlefield.forEach((item) => {
    const el = document.createElement("div");
    el.className = "bf-card";
    el.dataset.itemId = item.id;
    const pos = stackedScreenPos(item) || flipY(item.x, item.y, PILE_W, PILE_H);
    el.style.left = pos.x + "px";
    el.style.top = pos.y + "px";
    el.style.setProperty("--owner-color", playerColor(item.ownerId));
    const isMine = !isObserver && item.ownerId === myPlayerId;
    // a trusted observer gets the same "owner peek" as the actual owner
    const canPeek = isMine || isObserver;
    let inner;
    if (item.isTokenCard) {
      inner = `<div class="bf-card-face" style="background:${esc(temperamentInk(item.temperament))}">${tokenCardFaceHtml(item)}</div>`;
    } else if (item.faceUp && item.cardId) {
      inner = `<div class="bf-card-face"><img src="${esc(cardImage(item.cardId))}" alt="${esc(cardName(item.cardId))}" title="${esc(cardName(item.cardId))}"></div>`;
    } else if (canPeek && item.cardId) {
      // the owner (or an observer) gets a faint, colour-tinted peek at a face-down card
      inner = `<div class="bf-card-face"><div class="back-face owner-peek"><img src="${esc(cardImage(item.cardId))}"></div></div>`;
    } else {
      inner = `<div class="bf-card-face"><div class="back-face"></div></div>`;
    }
    el.innerHTML = `<div class="bf-card-inner" style="transform:rotate(${item.rotation || 0}deg)">${inner}</div><div class="counters">${counterCircles(item.counters)}</div>`;
    if (!isObserver) bindCardDragSource(el, { kind: "battlefield", itemId: item.id });
    el.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      if (isObserver) {
        // nothing read-only-useful to show for a token card (no real identity to inspect)
        if (!item.isTokenCard) {
          showContextMenu(event.clientX, event.clientY, [{ label: t("inspect"), onSelect: () => showInspect(item.cardId, !item.faceUp && !canPeek) }]);
        }
        return;
      }
      const zOrderItems = [
        { label: t("bringToFront"), onSelect: () => send({ type: "reorder_battlefield_item", itemId: item.id, position: "front" }) },
        { label: t("sendToBack"), onSelect: () => send({ type: "reorder_battlefield_item", itemId: item.id, position: "back" }) },
      ];
      if (item.isTokenCard) {
        showContextMenu(event.clientX, event.clientY, [
          { label: t("exhaust"), onSelect: () => send({ type: "move_battlefield_item", itemId: item.id, x: item.x, y: item.y, rotation: item.rotation ? 0 : 90 }) },
          { separator: true },
          ...zOrderItems,
          { separator: true },
          counterGridMenuItem("power", { itemId: item.id }),
          { separator: true },
          { label: t("remove"), onSelect: () => send({ type: "remove_battlefield_item", itemId: item.id, toZone: "graveyard" }) },
        ]);
        return;
      }
      const items = [];
      items.push({ label: t("inspect"), onSelect: () => showInspect(item.cardId, !item.faceUp && !canPeek) });
      items.push({ separator: true });
      if (isMine) items.push({ label: t("flip"), onSelect: () => send({ type: "flip_card", itemId: item.id }), highlight: !item.faceUp });
      items.push({ label: t("exhaust"), onSelect: () => send({ type: "move_battlefield_item", itemId: item.id, x: item.x, y: item.y, rotation: item.rotation ? 0 : 90 }) });
      items.push(...zOrderItems);
      items.push({ separator: true });
      items.push(counterGridMenuItem("power", { itemId: item.id }));
      items.push({ separator: true });
      // Empathic Vessel always collects into the ACTOR's own vessel,
      // regardless of whose card it is — Limbo/Exile stay with the card's
      // own owner, each player keeping their own
      ["graveyard", "exile"].forEach((z) => {
        items.push({ label: `${t("moveTo")} ${t(z)}`, onSelect: () => send({ type: "remove_battlefield_item", itemId: item.id, toOwnerId: item.ownerId, toZone: z }) });
      });
      items.push({ label: `${t("moveTo")} ${t("receptacle")}`, onSelect: () => send({ type: "remove_battlefield_item", itemId: item.id, toOwnerId: myPlayerId, toZone: "receptacle" }) });
      if (isMine) {
        items.push({ label: `${t("moveTo")} ${t("hand")}`, onSelect: () => send({ type: "remove_battlefield_item", itemId: item.id, toOwnerId: item.ownerId, toZone: "hand" }) });
        items.push({ label: t("moveToDeckTop"), onSelect: () => send({ type: "remove_battlefield_item", itemId: item.id, toOwnerId: item.ownerId, toZone: "deck", position: "top" }) });
        items.push({ label: t("moveToDeckBottom"), onSelect: () => send({ type: "remove_battlefield_item", itemId: item.id, toOwnerId: item.ownerId, toZone: "deck", position: "bottom" }) });
      }
      showContextMenu(event.clientX, event.clientY, items);
      // must run AFTER showContextMenu: it calls closeContextMenu() first
      // (to dismiss any previously-open menu), which would otherwise wipe
      // out labels created before it
      const canSeeName = item.faceUp || canPeek;
      showCardLabels(el, canSeeName ? cardName(item.cardId) : null, (latestState.players[item.ownerId] || {}).name || "");
    });
    bf.appendChild(el);
  });

  latestState.tokens.forEach((token) => {
    const el = document.createElement("div");
    el.className = "bf-token" + (token.isEssence ? " bf-essence" : "");
    const tpos = flipY(token.x, token.y, TOKEN_W, TOKEN_H);
    el.style.left = tpos.x + "px";
    el.style.top = tpos.y + "px";
    if (token.isEssence) {
      el.style.background = temperamentInk(token.temperament);
      const count = token.counters?.essence || 0;
      el.innerHTML = `<img src="${esc(temperamentSymbol(token.temperament))}" alt=""><span class="bf-essence-count">${count > 0 ? "+" : ""}${count}</span>`;
    } else {
      el.style.background = token.color || playerColor(token.ownerId);
      el.innerHTML = `<span>${esc(token.label || "")}</span><div class="counters">${counterCircles(token.counters)}</div>`;
    }
    if (!isObserver) {
      bindDrag(el, (x, y) => {
        const logical = flipY(x, y, TOKEN_W, TOKEN_H);
        send({ type: "move_token", tokenId: token.id, x: logical.x, y: logical.y });
      });
      el.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        if (token.isEssence) {
          showContextMenu(event.clientX, event.clientY, [
            counterGridMenuItem("essence", { tokenId: token.id }),
            { separator: true },
            { label: t("remove"), onSelect: () => send({ type: "remove_token", tokenId: token.id }) },
          ]);
          return;
        }
        showContextMenu(event.clientX, event.clientY, [
          counterGridMenuItem("mark", { tokenId: token.id }),
          { separator: true },
          { label: t("remove"), onSelect: () => send({ type: "remove_token", tokenId: token.id }) },
        ]);
      });
    }
    bf.appendChild(el);
  });

  renderCenterMarker();
}

function bindDrag(el, onDrop) {
  el.addEventListener("pointerdown", (event) => {
    if (event.target.closest("button, select")) return;
    event.preventDefault();
    const wrap = $("#battlefieldWrap");
    const startX = event.clientX, startY = event.clientY;
    const startLeft = parseFloat(el.style.left) || 0, startTop = parseFloat(el.style.top) || 0;
    const move = (e) => {
      const x = startLeft + (e.clientX - startX) / zoomLevel;
      const y = startTop + (e.clientY - startY) / zoomLevel;
      el.style.left = x + "px";
      el.style.top = y + "px";
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      onDrop(parseFloat(el.style.left), parseFloat(el.style.top));
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  });
}

// ---------------------------------------------------------------- deck import

function initImportPanel() {
  $("#importDeckBtn").onclick = () => {
    $("#importPanel").classList.remove("hidden");
    renderSavedDecks();
  };
  $("#importCancelBtn").onclick = () => $("#importPanel").classList.add("hidden");
  $("#importConfirmBtn").onclick = async () => {
    const raw = $("#importDeckText").value.trim();
    if (!raw) return;
    const shareToken = extractShareToken(raw);
    if (shareToken) {
      const payload = await decodeDkShare(shareToken);
      if (!payload || !payload.d) {
        alert(t("importShareFailed"));
        return;
      }
      const deck = expandDkShareDeck(payload.d);
      importDeckPayload(deck, deck.name || "Imported deck");
      return;
    }
    let deck;
    try {
      deck = JSON.parse(raw);
    } catch (e) {
      deck = parseDeckListText(raw);
    }
    if (!deck || !Array.isArray(deck.groups) || !deck.groups.some((g) => (g.cardIds || []).length)) {
      alert("Could not read any cards from that text. Paste a DeckomantiK share link, a list (\"Copy list\"), or a deck JSON export.");
      return;
    }
    const nameMatch = raw.match(/^\[Deck\]\s*(.+)$/mi);
    const deckName = deck.name || (nameMatch && nameMatch[1].trim()) || "Imported deck";
    importDeckPayload(deck, deckName);
  };
}

// ---------------------------------------------------------------- token add + end session + log

function initGameControls() {
  $("#highlightOwnersBtn").onclick = () => {
    const on = $("#battlefield").classList.toggle("highlight-owners");
    $("#highlightOwnersBtn").classList.toggle("active", on);
  };
  $("#battlefieldWrap").addEventListener("dblclick", (event) => {
    if (isObserver) return;
    if (event.target !== $("#battlefield") && event.target !== $("#battlefieldWrap")) return;
    const label = prompt("Token label (e.g. 1/1):", "");
    if (label === null) return;
    const rect = $("#battlefieldWrap").getBoundingClientRect();
    const logical = flipY((event.clientX - rect.left - panX) / zoomLevel - 26, (event.clientY - rect.top - panY) / zoomLevel - 26, TOKEN_W, TOKEN_H);
    send({ type: "add_token", x: logical.x, y: logical.y, label, color: playerColor(myPlayerId) });
  });

  $("#endSessionBtn").onclick = () => {
    showConfirm(t("confirmEndSession"), () => {
      send({ type: "end_session" });
      leaveSession();
    });
  };

  $("#leaveSessionBtn").onclick = () => {
    showConfirm(t("confirmLeaveSession"), () => {
      if (!isObserver) send({ type: "leave_session" }); // frees the seat for someone else to join
      leaveSession();
    });
  };

  $("#downloadLogBtn").onclick = () => send({ type: "request_log" });
  $("#logDownloadBtn").onclick = () => downloadLog(latestLogEntries);

  $("#fullscreenBtn").onclick = () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen?.();
  };
}

// ---------------------------------------------------------------- card inspect

// Most-recent-first list of cardIds shown with a real identity at some point
// (never a hidden/unknown peek) — lets the reopen-last-inspected toolbar
// button and the panel's own side history revisit any of the last few, not
// just the very last one. In-memory only: like other per-session UI state
// (e.g. revealSentState), it isn't meant to survive a reload.
let inspectHistory = [];

function showInspect(cardId, hidden) {
  const card = cardsById.get(cardId);
  if (!hidden && card) {
    inspectHistory = [cardId, ...inspectHistory.filter((id) => id !== cardId)].slice(0, 12);
    $("#inspectReopenBtn").disabled = false;
  }
  if (hidden || !card) {
    $("#inspectImg").src = "";
    $("#inspectName").textContent = "?";
    $("#inspectMeta").textContent = "";
    $("#inspectEffect").textContent = "";
  } else {
    $("#inspectImg").src = card.image || "";
    $("#inspectImg").alt = card.name || "";
    $("#inspectName").textContent = card.name || "";
    $("#inspectMeta").textContent = [card.typeLabel || card.type, card.subType, card.color].filter(Boolean).join(" · ");
    $("#inspectEffect").textContent = card.effect || "";
  }
  renderInspectHistory();
  $("#inspectPanel").classList.remove("hidden");
}

function renderInspectHistory() {
  $("#inspectHistory").innerHTML = inspectHistory
    .map((cid) => `<button class="inspect-history-card" data-inspect-history="${esc(cid)}" title="${esc(cardName(cid))}"><img src="${esc(cardImage(cid))}" alt=""></button>`)
    .join("");
  $$("#inspectHistory [data-inspect-history]").forEach((btn) => {
    btn.onclick = () => showInspect(btn.dataset.inspectHistory);
  });
}

const INSPECT_SIZE_KEY = "ko_inspect_card_w";
const INSPECT_SIZE_MAX = 560;
let inspectPanelWidth = Math.min(INSPECT_SIZE_MAX, Math.max(220, Number(localStorage.getItem(INSPECT_SIZE_KEY)) || 280));

function applyInspectPanelWidth() {
  document.documentElement.style.setProperty("--inspect-w", inspectPanelWidth + "px");
}

function initInspectToolbar() {
  $("#inspectReopenBtn").title = t("reopenLastInspected");
  $("#inspectReopenBtn").disabled = true;
  $("#inspectReopenBtn").onclick = () => {
    if (inspectHistory.length) showInspect(inspectHistory[0]);
  };
  applyInspectPanelWidth();
  $("#inspectResizeHandle").addEventListener("pointerdown", (event) => {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = inspectPanelWidth;
    const move = (e) => {
      // the handle sits on the box's LEFT edge (the box itself is right-docked
      // near the screen edge), so dragging further left — away from the box —
      // is what grows it: the same "drag away from content grows it" rule as
      // the reveal/hand-view resize handles, just on the horizontal axis
      inspectPanelWidth = Math.min(INSPECT_SIZE_MAX, Math.max(220, startWidth + (startX - e.clientX)));
      applyInspectPanelWidth();
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      localStorage.setItem(INSPECT_SIZE_KEY, String(inspectPanelWidth));
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  });
}

function formatLogEntry(e) {
  const who = e.actorName || e.actorId || "?";
  const d = e.details || {};
  const z = (key) => t(key) || key;
  const ownerName = (pid) => latestState?.players?.[pid]?.name || pid;
  const cross = d.ownerId && d.ownerId !== e.actorId ? ` (${ownerName(d.ownerId)}'s)` : "";
  const named = (cardId) => (cardId ? ` "${cardName(cardId)}"` : "");
  const faceState = (faceUp) => (faceUp === undefined ? "" : faceUp ? " (face up)" : " (face down)");
  const viaRequest = (requestedBy) => (requestedBy ? ` (requested by ${requestedBy})` : "");
  switch (e.type) {
    case "import_deck": return `${who} imported a deck (${d.count} cards).`;
    case "draw": return `${who} drew ${d.count} card(s).`;
    case "draw_to_limit": return `${who} drew up to hand size (+${d.count}).`;
    case "shuffle": return `${who} shuffled ${z(d.zone)}${cross}.`;
    case "reorder": return `${who} reordered ${z(d.zone)}${cross}.`;
    case "reveal": return `${who} revealed ${d.count} card(s) from ${z(d.zone)}${cross}${viaRequest(d.requestedBy)}.`;
    case "scry": return `${who} scried ${d.count} card(s) privately.`;
    case "move_card": return `${who} moved a card${named(d.cardId)}: ${z(d.fromZone)} → ${z(d.toZone)}${viaRequest(d.requestedBy)}.`;
    case "place_card": return `${who} played a card${named(d.cardId)} from ${z(d.fromZone)} onto the field${faceState(d.faceUp)}.`;
    case "move_battlefield_item": return `${who} moved a card on the field.`;
    case "flip_card": return `${who} flipped a card${named(d.cardId)}${faceState(d.faceUp)}.`;
    case "remove_battlefield_item": return d.tokenCard ? `${who} removed a token card.` : `${who} sent a field card${named(d.cardId)} to ${z(d.toZone)}${faceState(d.faceUp)}.`;
    case "create_token_card": return `${who} created a ${t("temperament" + d.temperament[0].toUpperCase() + d.temperament.slice(1))} token (${d.power > 0 ? "+" : ""}${d.power}).`;
    case "create_essence_token": return `${who} created ${d.count} ${t("temperament" + d.temperament[0].toUpperCase() + d.temperament.slice(1))} essence.`;
    case "mulligan": return `${who} took a mulligan (drew ${d.count} new card(s)).`;
    case "add_token": return `${who} added a token.`;
    case "move_token": return `${who} moved a token.`;
    case "remove_token": return `${who} removed a token.`;
    case "add_counter": return `${who} adjusted a counter (${d.delta > 0 ? "+" : ""}${d.delta}).`;
    case "set_score": return `${who} set score to ${d.score}.`;
    case "end_session": return `${who} ended the session.`;
    case "add_stroke": return `${who} drew on the board.`;
    case "remove_stroke": return `${who} erased a drawing.`;
    case "remove_strokes_in_rect": return `${who} erased ${d.count} drawing(s).`;
    case "clear_own_strokes": return `${who} cleared their drawings.`;
    case "roll_dice": return d.mode === "d6" ? `${who} rolled ${d.results.length}×D6: ${d.results.join(", ")}.` : `${who} flipped ${d.results.length} coin(s): ${d.results.join(", ")}.`;
    default: return `${who} — ${e.type}`;
  }
}

let latestLogEntries = [];

function renderLog(entries) {
  latestLogEntries = entries;
  const box = $("#logEntries");
  box.innerHTML = entries.length
    ? entries
        .map(
          (e) => `<div class="log-entry">
      <div class="t">${new Date(e.timestamp * 1000).toLocaleString()}</div>
      <div class="what">${esc(formatLogEntry(e))}</div>
      <div class="detail">${esc(JSON.stringify(e.details || {}))}</div>
    </div>`
        )
        .join("")
    : `<p>${esc(t("logEmpty"))}</p>`;
  $("#logPanel").classList.remove("hidden");
}

function downloadLog(entries) {
  const lines = entries.map((e) => `[${new Date(e.timestamp * 1000).toLocaleString()}] ${formatLogEntry(e)} ${JSON.stringify(e.details || {})}`);
  const blob = new Blob([lines.join("\n")], { type: "text/plain" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `kartomantik-online-log-${Date.now()}.txt`;
  link.click();
  URL.revokeObjectURL(link.href);
}

// ---------------------------------------------------------------- confirm modal
// An in-app replacement for window.confirm(), themed like every other panel
// instead of popping the browser's own dialog.

let pendingConfirmCallback = null;

function initConfirmPanel() {
  $("#confirmPanelCancelBtn").textContent = t("close");
  $("#confirmPanelCancelBtn").onclick = () => {
    pendingConfirmCallback = null;
    $("#confirmPanel").classList.add("hidden");
  };
  $("#confirmPanelOkBtn").onclick = () => {
    const cb = pendingConfirmCallback;
    pendingConfirmCallback = null;
    $("#confirmPanel").classList.add("hidden");
    if (cb) cb();
  };
}

function showConfirm(message, onConfirm, confirmLabel) {
  $("#confirmPanelText").textContent = message;
  $("#confirmPanelOkBtn").textContent = confirmLabel || t("confirm");
  pendingConfirmCallback = onConfirm;
  $("#confirmPanel").classList.remove("hidden");
}

// ---------------------------------------------------------------- boot

async function boot() {
  // the whole app has its own right-click menus everywhere that needs one;
  // the browser's native one is never wanted, on any surface
  document.addEventListener("contextmenu", (event) => {
    event.preventDefault();
    if (drawMode) setDrawMode(null); // right-click is also the "exit draw/erase mode" gesture
  });
  document.addEventListener("click", (event) => {
    const btn = event.target.closest(".stepper-btn");
    if (!btn) return;
    const input = $("#" + btn.dataset.target);
    const min = input.min === "" ? -Infinity : Number(input.min);
    const max = input.max === "" ? Infinity : Number(input.max);
    input.value = Math.max(min, Math.min(max, (Number(input.value) || 0) + Number(btn.dataset.step)));
  });
  document.addEventListener("keydown", (event) => {
    if (event.target?.closest?.("input, textarea, select, button")) return;
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.code === "Space") {
      if (!latestState || isObserver) return;
      event.preventDefault();
      toggleHandHidden();
    } else if (event.code === "KeyI" && inspectHistory.length) {
      event.preventDefault();
      showInspect(inspectHistory[0]);
    }
  });
  paintStaticText();
  initConfirmPanel();
  initSocialLinks();
  initPileBrowser();
  await loadCardDatabase();
  await loadStarterDecks();
  renderStarterDecks();
  initJoinScreen();
  initImportPanel();
  initGameControls();
  initZoomControls();
  initHandResize();
  initRevealResize();
  initHandViewResize();
  initHandToolbar();
  initDrawTool();
  initTokenToolbar();
  initEssenceToolbar();
  initDiceToolbar();
  initPileCalibration();
  initInspectToolbar();
  $("#logCloseBtn").onclick = () => $("#logPanel").classList.add("hidden");
  $("#inspectCloseBtn").onclick = () => $("#inspectPanel").classList.add("hidden");
  $("#revealCloseBtn").onclick = () => $("#revealPanel").classList.add("hidden");
  $("#handViewCloseBtn").onclick = () => $("#handViewPanel").classList.add("hidden");
  $("#handRequestAcceptBtn").onclick = () => {
    if (!pendingIncomingRequest) return;
    send({ type: "respond_hand_action", requestId: pendingIncomingRequest.requestId, accepted: true });
    pendingIncomingRequest = null;
    $("#handRequestPanel").classList.add("hidden");
  };
  $("#handRequestDeclineBtn").onclick = () => {
    if (!pendingIncomingRequest) return;
    send({ type: "respond_hand_action", requestId: pendingIncomingRequest.requestId, accepted: false });
    pendingIncomingRequest = null;
    $("#handRequestPanel").classList.add("hidden");
  };
}

boot();
