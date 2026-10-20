// Card database loading, deck lists, share links, library, import and sideboard.
// Loaded before app.js: declarations only, nothing runs at load time.

async function loadCardDatabase() {
  try {
    const sources = ["cards-data.json", "extensions/inner-desert/cards.json"];
    const lists = await Promise.all(sources.map(async (source) => {
      try {
        const res = await fetch(staticAsset(source));
        if (!res.ok) return [];
        const value = await res.json();
        return Array.isArray(value) ? value : [];
      } catch (error) {
        console.warn(`Card source unavailable: ${source}`, error);
        return [];
      }
    }));
    const list = lists.flat();
    cardsById = new Map(list.map((c) => [c.id, c]));
    cardsByNumber = new Map(list.map((c) => [Number(c.collectionNumber), c]));
    try {
      const abilityResponse = await fetch(staticAsset("card-abilities.json"));
      const abilityData = abilityResponse.ok ? await abilityResponse.json() : {};
      activatedAbilitiesByCard = new Map(
        Object.entries(abilityData || {}).map(([cardId, abilities]) => [
          cardId,
          // a play permission (Wandering Veteran) is not an ability its card activates on the field
          (Array.isArray(abilities) ? abilities : []).filter((ability) => !ability.trigger && !ability.passiveEffect && !ability.playPermission && ability.action !== "play_card"),
        ]),
      );
      playedAbilitiesByCard = new Map(
        Object.entries(abilityData || {}).map(([cardId, abilities]) => [
          cardId,
          (Array.isArray(abilities) ? abilities : []).filter((ability) => !ability.trigger && ability.action === "play_card"),
        ]),
      );
      triggeredAbilitiesByCard = new Map(
        Object.entries(abilityData || {}).map(([cardId, abilities]) => [
          cardId,
          (Array.isArray(abilities) ? abilities : []).filter((ability) => ability.trigger),
        ]),
      );
      passiveEffectsByCard = new Map(
        Object.entries(abilityData || {}).map(([cardId, abilities]) => [
          cardId,
          (Array.isArray(abilities) ? abilities : [])
            .map((ability) => ability.passiveEffect)
            .filter(Boolean),
        ]),
      );
    } catch (error) {
      console.warn("Encoded card abilities unavailable", error);
      activatedAbilitiesByCard = new Map();
      playedAbilitiesByCard = new Map();
      triggeredAbilitiesByCard = new Map();
      passiveEffectsByCard = new Map();
    }
    try {
      const coverageResponse = await fetch(staticAsset("automation-coverage.json"));
      const coverageData = coverageResponse.ok
        ? await coverageResponse.json()
        : { cards: {}, summary: null };
      automationCoverageByCard = new Map(
        Object.entries(coverageData.cards || {})
      );
      automationCoverageSummary = coverageData.summary || null;
    } catch (error) {
      console.warn("Automation coverage unavailable", error);
      automationCoverageByCard = new Map();
      automationCoverageSummary = null;
    }
  } catch (e) {
    console.error("Failed to load card database", e);
  }
}

async function loadStarterDecks() {
  try {
    const res = await fetch(staticAsset("starter-decks.json"));
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
    const card = deckListLineCard(line);
    if (card) {
      if (!current) { current = { kind: null, cardIds: [] }; groups.push(current); }
      current.cardIds.push(card.id);
    }
  }
  return { app: "DeckomantiK", groups };
}

// A DeckomantiK "Copy list" line is "<number> <name>": "#012 Wind Sprout" for
// the base set, "ID-001 Flem" for an extension (its collector code). Plain
// numbers ("12 Wind Sprout") and bare names are accepted too.
function deckListLineCard(line) {
  const codeMatch = line.match(/^([A-Za-z]{1,4})[-_ ]?(\d{1,3})\b/);
  if (codeMatch) {
    const code = `${codeMatch[1]}-${codeMatch[2].padStart(3, "0")}`.toUpperCase();
    const byCode = [...cardsById.values()].find((card) => String(card.collectorCode || "").toUpperCase() === code);
    if (byCode) return byCode;
  }
  const numberMatch = line.match(/^#?(\d+)\b/);
  if (numberMatch) return cardsByNumber.get(Number(numberMatch[1])) || null;
  const name = deckListNormalizedName(line);
  if (!name) return null;
  return [...cardsById.values()].find((card) => deckListNormalizedName(card.name) === name
    || Object.values(card.translations || {}).some((tr) => tr?.name && deckListNormalizedName(tr.name) === name)) || null;
}

function deckListNormalizedName(value) {
  return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
    .replace(/^\s*\d+\s*[x×]\s*/i, "").replace(/[^a-z0-9]+/g, " ").trim();
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
    // v2 stored card indexes, v3 (current DeckomantiK) stores card ids
    return payload && [2, 3].includes(payload.v) && (payload.d || payload.b) ? payload : null;
  } catch (e) {
    return null;
  }
}

// DeckomantiK's card index is the array position in ITS OWN card list, which
// is ordered by collectionNumber starting at 1 with no gaps (index =
// collectionNumber - 1) — resolving through our own cardsByNumber map (keyed
// the same way) sidesteps any risk of the two apps' card-id strings differing.
function dkShareCardId(value) {
  if (typeof value === "string") {
    if (cardsById.has(value)) return value;
    const bare = value.replace(/_(?:en|it)$/i, "").toLowerCase();
    return [...cardsById.keys()].find((id) => id.replace(/_(?:en|it)$/i, "").toLowerCase() === bare) || null;
  }
  return Number.isInteger(value) ? cardsByNumber.get(value + 1)?.id || null : null;
}

function expandDkShareDeck(d) {
  const groups = (d.g || []).map((g) => ({
    kind: g.k || null,
    cardIds: (g.c || []).map(dkShareCardId).filter(Boolean),
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

function importDeckPayload(deck, name, persist = true, confirmDeck = false) {
  send({ type: "import_deck", deck, resetOwnBoard: Boolean(pendingDeckImport?.resetOwnBoard), confirmDeck });
  if (persist) saveDeckToLibrary(name || deck.name || "Deck", deck);
  $("#sideboardPanel").classList.add("hidden");
  $("#importDeckText").value = "";
  $("#importSelectionStatus").textContent = confirmDeck ? t("deckValidationSent") : t("deckImported");
}

function renderCurrentDeckSummary() {
  const box = $("#currentDeckSummary");
  if (!box) return;
  const deck = pendingDeckImport ? null : currentDeckForSideboard();
  const pending = pendingDeckImport || (deck ? splitDeckForEditor(deck, deck.name || t("currentDeck"), false) : null);
  if (!pending) {
    box.innerHTML = `<p>${esc(t("noCurrentDeck"))}</p>`;
    return;
  }

  const names = pending.mainIds.slice(0, 8).map((cardId) => cardName(cardId));
  box.innerHTML = `<button type="button" class="current-deck-card ${pendingDeckImport ? "is-staged" : ""}" id="currentDeckEditBtn" title="${esc(names.join(" · "))}">
    <span><strong>${esc(pending.name)}</strong><small>${pending.mainIds.length} ${esc(t("cards"))} · ${deckImportPoints(pending.mainIds)} ${esc(t("points"))}</small></span>
    <span class="current-deck-sideboard">${esc(t("sideboard"))} · ${pending.sideboardIds.length}/6</span>
  </button>`;
  $("#currentDeckEditBtn").onclick = pendingDeckImport ? renderSideboardEditor : openCurrentSideboard;
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
      if (deck) stageDeckImport(deck, deck.name, false);
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
      if (entry) stageDeckImport(entry.deck, entry.name, true);
    };
  });
  $$("[data-forget-saved]").forEach((btn) => {
    btn.onclick = () => forgetDeckFromLibrary(btn.dataset.forgetSaved);
  });
}

// ---------------------------------------------------------------- i18n paint

const PHASE_GROUPS = [
  {
    id: "recovery", label: "phaseRecovery", detail: "phaseDetailRecovery", weight: 3,
    sections: [{ label: null, steps: [
      { id: "recovery_start", label: "phaseRecoveryStart", detail: "phaseDetailRecoveryStart" },
      { id: "recovery_draw", label: "phaseRecoveryDraw", detail: "phaseDetailRecoveryDraw" },
      { id: "recovery_end", label: "phaseRecoveryEnd", detail: "phaseDetailRecoveryEnd" },
    ] }],
  },
  {
    id: "confrontation", label: "phaseConfrontation", detail: "phaseDetailConfrontation", weight: 6,
    sections: [
      { label: "phaseRevelation", steps: [
        { id: "confrontation_choose", label: "phaseConfrontationChoose", detail: "phaseDetailConfrontationChoose" },
        { id: "confrontation_before_revelation", label: "phaseConfrontationBefore", detail: "phaseDetailConfrontationBefore" },
        { id: "confrontation_reveal", label: "phaseConfrontationReveal", detail: "phaseDetailConfrontationReveal" },
        { id: "confrontation_immediate", label: "phaseConfrontationImmediate", detail: "phaseDetailConfrontationImmediate" },
        { id: "confrontation_entry", label: "phaseConfrontationEntry", detail: "phaseDetailConfrontationEntry" },
      ] },
      { label: "phaseReaction", steps: [
        { id: "confrontation_reaction", label: "phaseConfrontationReaction", detail: "phaseDetailConfrontationReaction" },
      ] },
    ],
  },
  {
    id: "resolution", label: "phaseResolution", detail: "phaseDetailResolution", weight: 3,
    sections: [{ label: null, steps: [
      { id: "resolution_compare", label: "phaseResolutionCompare", detail: "phaseDetailResolutionCompare" },
      { id: "resolution_effects", label: "phaseResolutionEffects", detail: "phaseDetailResolutionEffects" },
      { id: "resolution_move", label: "phaseResolutionMove", detail: "phaseDetailResolutionMove" },
    ] }],
  },
  {
    id: "end", label: "phaseEnd", detail: "phaseDetailEnd", weight: 3,
    sections: [{ label: null, steps: [
      { id: "end_actions", label: "phaseEndActions", detail: "phaseDetailEndActions" },
      { id: "end_triggers", label: "phaseEndTriggers", detail: "phaseDetailEndTriggers" },
      { id: "end_expire", label: "phaseEndExpire", detail: "phaseDetailEndExpire" },
    ] }],
  },
];

const PHASE_VISIBILITY_KEY = "ko_phase_tracker_visible.v3";

let pendingDeckImport = null;

let importDeckValidationArmed = false;

function uniqueCardIds(cardIds) {
  return [...new Set((cardIds || []).filter((cardId) => typeof cardId === "string"))];
}

function splitDeckForEditor(deck, name, persist = true) {
  const main = [];
  const sideboard = [];
  (deck.groups || []).forEach((group) => {
    const kind = String(group.kind || "").toLowerCase();
    if (kind === "maybeboard") return;
    (kind === "sideboard" ? sideboard : main).push(...(group.cardIds || []));
  });
  const mainIds = uniqueCardIds(main);
  const mainSet = new Set(mainIds);
  const sideboardIds = uniqueCardIds(sideboard).filter((cardId) => !mainSet.has(cardId));
  return {
    sourceDeck: deck,
    name: name || deck.name || "Imported deck",
    persist,
    mainIds,
    sideboardIds,
    originalMain: new Set(mainIds),
    originalSideboard: new Set(sideboardIds),
  };
}

function currentDeckForSideboard() {
  const player = latestState?.players?.[myPlayerId];
  if (!player) return null;
  if (player.deckDefinition?.groups) return player.deckDefinition;
  const mainIds = [];
  Object.entries(latestState.players).forEach(([containerId, container]) => {
    Object.entries(container.zones || {}).forEach(([zone, zoneData]) => {
      (zoneData.cards || []).forEach((cardId) => {
        if (zoneCardOwner(containerId, zone, cardId) === myPlayerId) mainIds.push(cardId);
      });
    });
  });
  (latestState.battlefield || []).forEach((item) => {
    if (item.ownerId === myPlayerId && !item.isCopy && !item.isTokenCard && item.cardId) mainIds.push(item.cardId);
  });
  return {
    name: t("currentDeck"),
    cardRarities: { ...(player.cardRarities || {}) },
    groups: [
      { id: "current-deck", kind: "deck", name: t("deck"), cardIds: uniqueCardIds(mainIds) },
      { id: "sideboard", kind: "sideboard", name: t("sideboard"), cardIds: uniqueCardIds(player.sideboard || []) },
    ],
  };
}

function openCurrentSideboard() {
  const deck = currentDeckForSideboard();
  if (!deck) return;
  pendingDeckImport = splitDeckForEditor(deck, deck.name || t("currentDeck"), false);
  pendingDeckImport.resetOwnBoard = true;
  renderSideboardEditor();
}

function stageDeckImport(deck, name, persist = true) {
  pendingDeckImport = splitDeckForEditor(deck, name, persist);
  const validation = deckImportValidation(pendingDeckImport);
  $("#importSelectionStatus").textContent = `${pendingDeckImport.name} · ${pendingDeckImport.mainIds.length} ${t("cards")} · ${pendingDeckImport.sideboardIds.length} ${t("sideboard")} · ${validation.message}`;
  $("#importSelectionStatus").classList.toggle("invalid", !validation.valid);
  $("#importSideboardBtn").disabled = false;
  renderCurrentDeckSummary();
  resetImportDeckValidationArm();
  renderImportPanelActions();
}

function importDeckValidationMode() {
  return Boolean(latestState?.rulesEngine?.enabled && rules_pregame_active_client());
}

function standardDeckSetupActiveClient() {
  const currentPhase = currentPhaseUi();
  const playerIds = Object.keys(latestState?.players || {});
  const confirmed = new Set(latestState?.rulesEngine?.deckConfirmedPlayerIds || []);
  const allCasualDecksConfirmed = playerIds.length >= 2 && playerIds.every((playerId) => confirmed.has(playerId));
  const setupIncomplete = latestState?.mode === "casual"
    ? !allCasualDecksConfirmed
    : !latestState?.players?.[myPlayerId]?.deckDefinition;
  return Boolean(
    !latestState?.rulesEngine?.enabled
    && !latestState?.ended
    && latestState?.phaseTracker?.turn === 1
    && currentPhase.group?.id === "recovery"
    && !isObserver
    && latestState?.players?.[myPlayerId]
    && setupIncomplete
  );
}

function importValidationCandidate() {
  if (pendingDeckImport) return pendingDeckImport;
  const current = currentDeckForSideboard();
  return current ? splitDeckForEditor(current, current.name || t("currentDeck"), false) : null;
}

function resetImportDeckValidationArm() {
  importDeckValidationArmed = false;
  const button = $("#importConfirmBtn");
  if (!button) return;
  button.classList.remove("confirm-armed");
  button.textContent = t("rulesValidateDeck");
}

function renderImportPanelActions() {
  const pasteButton = $("#importPasteBtn");
  const validationButton = $("#importConfirmBtn");
  if (!pasteButton || !validationButton) return;
  pasteButton.disabled = !$("#importDeckText").value.trim() && !pendingDeckImport;
  const validationMode = importDeckValidationMode();
  const standardSetupMode = standardDeckSetupActiveClient();
  const primaryActionAvailable = validationMode || standardSetupMode;
  validationButton.classList.toggle("hidden", !primaryActionAvailable);
  const candidate = importValidationCandidate();
  const mineConfirmed = (latestState?.rulesEngine?.deckConfirmedPlayerIds || []).includes(myPlayerId);
  validationButton.disabled = !primaryActionAvailable
    || (validationMode && mineConfirmed)
    || !deckImportValidation(candidate).valid;
}

function deckImportPoints(cardIds) {
  return cardIds.reduce((total, cardId) => total + (Number(cardsById.get(cardId)?.points) || 0), 0);
}

function deckImportPointLimit(cardIds) {
  return 500 + cardIds.reduce((total, cardId) => {
    const match = /construction limit is increased by (\d+) points/i.exec(cardsById.get(cardId)?.effect || "");
    return total + (match ? Number(match[1]) : 0);
  }, 0);
}

function deckImportValidation(pending = pendingDeckImport) {
  if (!pending) return { valid: false, message: t("deckMissing") };
  const errors = [];
  if (pending.mainIds.length !== 30) errors.push(rulesText("deckCountInvalid", { count: pending.mainIds.length }));
  const points = deckImportPoints(pending.mainIds);
  const pointLimit = deckImportPointLimit(pending.mainIds);
  if (points > pointLimit) errors.push(rulesText("deckPointsInvalid", { points, limit: pointLimit }));
  if (pending.sideboardIds.length > 6) errors.push(rulesText("sideboardCountInvalid", { count: pending.sideboardIds.length }));
  const overlap = pending.mainIds.filter((cardId) => pending.sideboardIds.includes(cardId));
  if (overlap.length) errors.push(t("deckSideboardOverlap"));
  const policyState = latestState?.deckPolicy;
  if (policyState?.enabled) {
    const combined = new Set([...pending.mainIds, ...pending.sideboardIds]);
    const banned = (policyState.policy?.bannedCardIds || []).filter((cardId) => combined.has(cardId));
    if (banned.length) errors.push(`${t("bannedCards")}: ${banned.map(cardName).join(", ")}`);
    for (const group of policyState.policy?.restrictedGroups || []) {
      const present = (group.cardIds || []).filter((cardId) => combined.has(cardId));
      if (present.length > 1) errors.push(`${group.name || t("restrictedGroup")}: ${present.map(cardName).join(", ")}`);
    }
  }
  return { valid: errors.length === 0, message: errors.join(" · ") || t("deckReady") };
}

function deckImportIsValid(pending = pendingDeckImport) {
  return deckImportValidation(pending).valid;
}

function buildEditedDeck(pending = pendingDeckImport) {
  const source = pending.sourceDeck || {};
  const mainSet = new Set(pending.mainIds);
  const assigned = new Set();
  const groups = (source.groups || [])
    .filter((group) => !["sideboard", "maybeboard"].includes(String(group.kind || "").toLowerCase()))
    .map((group) => {
      const cardIds = uniqueCardIds(group.cardIds).filter((cardId) => mainSet.has(cardId));
      cardIds.forEach((cardId) => assigned.add(cardId));
      return { ...group, cardIds };
    });
  const newlyMain = pending.mainIds.filter((cardId) => !assigned.has(cardId));
  if (newlyMain.length) groups.push({ id: "sideboard-additions", kind: "deck", name: t("deck"), cardIds: newlyMain });
  groups.push({ id: "sideboard", kind: "sideboard", name: t("sideboard"), cardIds: [...pending.sideboardIds] });
  (source.groups || []).filter((group) => String(group.kind || "").toLowerCase() === "maybeboard").forEach((group) => groups.push({ ...group, cardIds: uniqueCardIds(group.cardIds) }));
  return { ...source, name: pending.name, groups };
}

function sideboardCardMarkup(cardId, pool) {
  const card = cardsById.get(cardId);
  const originalPool = pendingDeckImport.originalSideboard.has(cardId) ? "sideboard" : "deck";
  const moved = originalPool !== pool;
  const rarity = normalizeRarity(pendingDeckImport.sourceDeck?.cardRarities?.[cardId]);
  return `<button type="button" class="sideboard-card${moved ? " pending-move" : ""}" data-sideboard-card="${esc(cardId)}" data-sideboard-pool="${pool}">
    <span class="sideboard-card-art${rarityClassAttr(rarity)}" style="${rarityCosmosStyle(cardId)}">${raritySurfaceMarkup(rarity, `<img src="${esc(cardImage(cardId))}" alt="${esc(cardName(cardId))}">`)}</span>
    <strong>${esc(cardName(cardId))}</strong><small>${Number(card?.points) || 0} ${esc(t("points"))}${moved ? ` · ${esc(t("pendingMove"))}` : ""}</small>
  </button>`;
}

function renderSideboardEditor() {
  if (!pendingDeckImport) return;
  const points = deckImportPoints(pendingDeckImport.mainIds);
  const validCount = pendingDeckImport.mainIds.length === 30;
  const pointLimit = deckImportPointLimit(pendingDeckImport.mainIds);
  const validPoints = points <= pointLimit;
  $("#sideboardDeckHeading").textContent = t("deckPool");
  $("#sideboardPoolHeading").textContent = t("sideboard");
  $("#sideboardDeckStats").innerHTML = `<strong class="${validCount ? "valid" : "invalid"}">${pendingDeckImport.mainIds.length}/30 ${esc(t("cards"))}</strong><strong class="${validPoints ? "valid" : "invalid"}">${points}/${pointLimit} ${esc(t("points"))}</strong>`;
  $("#sideboardPoolStats").innerHTML = `<strong class="${pendingDeckImport.sideboardIds.length > 6 ? "warning" : ""}">${pendingDeckImport.sideboardIds.length}/6 ${esc(t("cards"))}</strong>`;
  $("#sideboardDeckCards").innerHTML = pendingDeckImport.mainIds.map((cardId) => sideboardCardMarkup(cardId, "deck")).join("");
  $("#sideboardPoolCards").innerHTML = pendingDeckImport.sideboardIds.map((cardId) => sideboardCardMarkup(cardId, "sideboard")).join("");
  $("#sideboardValidationMessage").textContent = deckImportValidation().message;
  $("#sideboardResetWarning").classList.toggle("hidden", !pendingDeckImport.resetOwnBoard);
  $("#sideboardResetWarning").textContent = pendingDeckImport.resetOwnBoard ? t("sideboardResetWarning") : "";
  $("#sideboardValidateBtn").disabled = !deckImportIsValid();
  $$('[data-sideboard-card]').forEach((button) => {
    button.onclick = () => {
      const cardId = button.dataset.sideboardCard;
      const from = button.dataset.sideboardPool;
      const source = from === "deck" ? pendingDeckImport.mainIds : pendingDeckImport.sideboardIds;
      const target = from === "deck" ? pendingDeckImport.sideboardIds : pendingDeckImport.mainIds;
      const index = source.indexOf(cardId);
      if (index >= 0) source.splice(index, 1);
      target.push(cardId);
      renderSideboardEditor();
    };
  });
  $("#sideboardPanel").classList.remove("hidden");
  $$('[data-sideboard-card] .ko-rarity-card').forEach((el) => bindRarityPointer(el, false));
}

async function readDeckImportText(raw) {
  const shareToken = extractShareToken(raw);
  if (shareToken) {
    const payload = await decodeDkShare(shareToken);
    if (!payload || !payload.d) throw new Error(t("importShareFailed"));
    const deck = expandDkShareDeck(payload.d);
    return { deck, name: deck.name || "Imported deck" };
  }
  let deck;
  try { deck = JSON.parse(raw); } catch (e) { deck = parseDeckListText(raw); }
  if (!deck || !Array.isArray(deck.groups) || !deck.groups.some((group) => (group.cardIds || []).length)) throw new Error(t("importReadFailed"));
  const nameMatch = raw.match(/^\[Deck\]\s*(.+)$/mi);
  return { deck, name: deck.name || (nameMatch && nameMatch[1].trim()) || "Imported deck" };
}

async function ensurePendingDeckImport() {
  if (pendingDeckImport) return pendingDeckImport;
  const raw = $("#importDeckText").value.trim();
  if (!raw) return null;
  try {
    const parsed = await readDeckImportText(raw);
    stageDeckImport(parsed.deck, parsed.name, true);
    return pendingDeckImport;
  } catch (error) {
    alert(error.message || t("importReadFailed"));
    return null;
  }
}
