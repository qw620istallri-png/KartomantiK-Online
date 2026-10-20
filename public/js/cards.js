// Card data helpers: names, images, tribute previews and rarity effects.
// Loaded before app.js: declarations only, nothing runs at load time.

const $ = (sel) => document.querySelector(sel);

const $$ = (sel) => [...document.querySelectorAll(sel)];

const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const ZONES = ["deck", "hand", "graveyard", "exile", "receptacle"];

const PRIVATE_ZONES = new Set(["deck", "hand", "exile"]);

// picked to contrast against the board's dark navy background (#0b1e3a)
const PLAYER_COLORS = ["#d3654a", "#3fc9a8", "#8bbf4f", "#b06fd6", "#d98a2b", "#4fa3d9"];

const staticAsset = (path) => `${path}?v=${STATIC_ASSET_VERSION}`;

const DECKOMANTIK_DESERT_ASSET_ROOT = "https://qw620istallri-png.github.io/DECKOMANTIK/assets/Desert";

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

const TRIBUTE_SYMBOL_TEMPERAMENT = {
  G: "phlegmatic", B: "vitreous", P: "melancholic",
  Y: "capricious", R: "choleric", H: "hollow",
};

function temperamentInk(key) {
  return TEMPERAMENTS.find((t2) => t2.key === key)?.ink || "#6b5b2f";
}

function playManuallyFromHand(cardId) {
  const view = fieldCenterLogical();
  const center = rotateForSeat(view.x, view.y);
  send({
    type: "place_card",
    fromZone: "hand",
    cardId,
    faceUp: true,
    manualBypass: true,
    x: center.x - 75 + Math.random() * 60 - 30,
    y: center.y - 105 + Math.random() * 60 - 30,
  });
}

function temperamentSymbol(key) {
  return staticAsset(`temperaments/${key}.webp`);
}

function printedTributeRequirements(card) {
  const requirements = {};
  for (const match of String(card?.powerCost || "").matchAll(/\{([A-Z])\}/g)) {
    const temperament = TRIBUTE_SYMBOL_TEMPERAMENT[match[1]];
    if (temperament) requirements[temperament] = (requirements[temperament] || 0) + 1;
  }
  if (!Object.keys(requirements).length && Number(card?.cost) > 0 && card?.temperaments?.length === 1) {
    requirements[card.temperaments[0]] = Number(card.cost);
  }
  return requirements;
}

function rulesEssencePaymentPreview(requirements) {
  const remaining = { ...requirements };
  const tokens = (latestState?.tokens || []).filter((token) => token.ownerId === myPlayerId
    && token.isEssence && !token.isNeutralCounter && token.temperament
    && Number(token.counters?.essence || 0) > 0);
  const available = new Map(tokens.map((token) => [token.id, Number(token.counters.essence)]));
  const spent = {};
  const consume = (requirement, candidates) => {
    let needed = remaining[requirement] || 0;
    for (const token of candidates) {
      if (needed <= 0) break;
      const amount = Math.min(needed, available.get(token.id) || 0);
      if (amount <= 0) continue;
      available.set(token.id, available.get(token.id) - amount);
      needed -= amount;
      spent[token.temperament] = (spent[token.temperament] || 0) + amount;
    }
    remaining[requirement] = needed;
  };
  Object.keys(requirements).filter((key) => key !== "hollow").forEach((temperament) => {
    consume(temperament, tokens.filter((token) => token.temperament === temperament));
  });
  if (Object.hasOwn(requirements, "hollow")) {
    const hollowOrder = tokens
      .filter((token) => token.temperament !== "transcendent")
      .sort((a, b) => Number(a.temperament !== "hollow") - Number(b.temperament !== "hollow"));
    consume("hollow", hollowOrder);
  }
  const transcendent = tokens.filter((token) => token.temperament === "transcendent");
  Object.keys(requirements).forEach((temperament) => consume(temperament, transcendent));
  return { remaining, spent };
}

const RULES_KANOPO_PATTERN = /you may sacrifice a Manifestation in your Interzone\. If you do, .{0,40}?base power of (\d+)/is;

function rulesTributeSacrificePower(card) {
  const match = String(card?.effect || "").match(RULES_KANOPO_PATTERN);
  return match ? Number(match[1]) : null;
}

function rulesTributeCandidate(reference) {
  const value = String(reference || "");
  if (value.startsWith("sacrifice|")) {
    const item = (latestState?.battlefield || []).find(
      (candidate) => candidate.id === value.slice("sacrifice|".length),
    );
    const card = cardsById.get(item?.cardId);
    return card ? { ...card, power: 0, sacrifice: true, paymentValue: value } : null;
  }
  if (value.startsWith("battlefield|")) {
    const itemId = value.slice("battlefield|".length);
    const item = (latestState?.battlefield || []).find(
      (candidate) => candidate.id === itemId,
    );
    const card = cardsById.get(item?.cardId);
    if (!item || !card) return null;
    const match = String(card.effect || "").match(
      /used as tribute.*?considered(?: to have a base power of| of base power) ([^\n.]+)/is,
    );
    const powerSymbols = match
      ? [...match[1].matchAll(/\{[A-Z]\}|[🔥🌿💧🔮⚡🌈]/gu)]
      : [];
    const power = powerSymbols.length || Number(card.power || 0);
    return { ...card, power, paymentValue: value };
  }
  const cardId = value.includes("|") ? value.split("|").at(-1) : value;
  const card = cardsById.get(cardId);
  if (card && value.startsWith("receptacle|")) {
    return { ...card, temperaments: ["transcendent"], paymentValue: value };
  }
  const powerOverride = latestState?.rulesEngine?.tributePowerOverrides?.[myPlayerId]?.[cardId];
  return card
    ? { ...card, ...(Number.isFinite(powerOverride) ? { power: powerOverride } : {}), paymentValue: value }
    : null;
}

function rulesRemainingAfterManifestations(cardIds, requirements) {
  const remaining = { ...requirements };
  const candidates = cardIds.map(rulesTributeCandidate).filter(Boolean);
  let sacrifices = candidates.filter((card) => card.sacrifice).length;
  const cards = candidates.filter((card) => !card.sacrifice).map((card) => {
    const sacrificePower = rulesTributeSacrificePower(card);
    if (sacrifices > 0 && sacrificePower !== null) {
      sacrifices -= 1;
      return { ...card, power: sacrificePower };
    }
    return card;
  })
    .sort((a, b) => Number(cardTributeTemperaments(a).includes("transcendent")) - Number(cardTributeTemperaments(b).includes("transcendent")));
  // Every card pays exactly one temperament (or Hollow): search all the ways to
  // assign them, so a greedy choice never makes a payable Tribute look short.
  const options = (state, card) => {
    const power = Math.max(0, Number(card.power) || 0);
    const tribute = cardTributeTemperaments(card);
    if (tribute.includes("transcendent")) {
      const left = { ...state };
      let used = 0;
      for (const required of Object.keys(left)) {
        const amount = Math.min(power - used, left[required]);
        left[required] -= amount;
        used += amount;
        if (used >= power) break;
      }
      return [left];
    }
    const result = [];
    for (const candidate of [...tribute, "hollow"]) {
      if (Object.hasOwn(state, candidate) && state[candidate] > 0) {
        result.push({ ...state, [candidate]: state[candidate] - Math.min(power, state[candidate]) });
      }
    }
    return result.length ? result : [{ ...state }];
  };
  const missing = (state) => Object.values(state).reduce((sum, amount) => sum + Math.max(0, amount), 0);
  let best = null;
  const search = (index, state) => {
    if (best !== null && missing(best) === 0) return;
    if (index === cards.length) {
      if (best === null || missing(state) < missing(best)) best = state;
      return;
    }
    for (const next of options(state, cards[index])) search(index + 1, next);
  };
  search(0, remaining);
  Object.assign(remaining, best || {});
  return remaining;
}

function cardTributeTemperaments(card) {
  const temperaments = [...(card?.temperaments || [])];
  const symbolMap = {
    G: "phlegmatic", B: "vitreous", P: "melancholic",
    Y: "capricious", R: "choleric", H: "hollow", T: "transcendent",
  };
  const effect = String(card?.effect || "");
  const pattern = /used as tribute.*?considered of \{([A-Z])\} temperament/gis;
  for (const match of effect.matchAll(pattern)) {
    const temperament = symbolMap[match[1]];
    if (temperament && !temperaments.includes(temperament)) temperaments.push(temperament);
  }
  return temperaments;
}

function rulesManifestationsCover(cardIds, requirements) {
  return Object.values(rulesRemainingAfterManifestations(cardIds, requirements)).every((amount) => amount <= 0);
}

function rulesCanAffordCard(cardId) {
  const card = cardsById.get(cardId);
  if (!card || !["ephemeral_will", "persistent_will"].includes(card.type)) return true;
  const requirements = printedTributeRequirements(card);
  const remaining = rulesEssencePaymentPreview(requirements).remaining;
  if (Object.values(remaining).every((amount) => amount <= 0)) return true;
  const manifestations = (latestState?.players?.[myPlayerId]?.zones?.hand?.cards || [])
    .filter((candidateId) => candidateId !== cardId && cardsById.get(candidateId)?.type === "manifestation");
  const combinations = 1 << Math.min(manifestations.length, 12);
  for (let mask = 1; mask < combinations; mask += 1) {
    const selected = manifestations.filter((_candidate, index) => mask & (1 << index));
    if (rulesManifestationsCover(selected, remaining)) return true;
  }
  return false;
}

function rulesTributeUnitsHtml(units, emptyLabel) {
  const content = Object.entries(units)
    .filter(([, amount]) => Number(amount) > 0)
    .map(([temperament, amount]) => `<span class="rules-tribute-unit"><img src="${esc(temperamentSymbol(temperament))}" alt="">×${amount}</span>`)
    .join("");
  return `<span class="rules-tribute-units">${content || esc(emptyLabel)}</span>`;
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

let activatedAbilitiesByCard = new Map();

let playedAbilitiesByCard = new Map();

let triggeredAbilitiesByCard = new Map();

let passiveEffectsByCard = new Map();

let automationCoverageByCard = new Map();

let automationCoverageSummary = null;

let starterDecks = [];

let myPlayerId = null;

let isObserver = false;

let connectionRole = "player";

let connectionMode = "casual";

let codePlayer = null;

let codeObserver = null;

let codeOrganizer = null;

let tournamentCodes = null;

let judgeMatchView = false;

let rulesBetaActivated = false;

let joinedCode = null;

let joinedName = null;

let latestState = null;

let colorByPlayer = new Map();

// the revealed cards of a hand the viewer cannot see, at their real place
// (sent by the server as hand.revealed: [{ index, cardId }])
function revealedHandSlots(hand, count) {
  const slots = Array.from({ length: count }, () => null);
  for (const entry of hand?.revealed || []) {
    if (entry.index >= 0 && entry.index < count) slots[entry.index] = entry.cardId;
  }
  return slots;
}

let pendingIncomingRequest = null; // the hand_action_request currently shown in #handRequestPanel

let pendingTournamentLogDownload = false;

let tournamentAlertTimer = null;

let lastTournamentNoticeStatus = null;

let tournamentPolicyDraft = null;

let tournamentPolicyDirty = false;

let homePolicyDraft = null;

let openPresenceRole = null;

let expanded = new Set(); // "ownerId:zone" currently expanded in the UI

let reconnectTimer = null;

let intentionalClose = false;

let wasDisconnected = false; // true while recovering from a dropped connection, for the green "Reconnected" flash

let lastRulesVfxSequence = null;

function playerColor(playerId) {
  if (!colorByPlayer.has(playerId)) {
    colorByPlayer.set(playerId, PLAYER_COLORS[colorByPlayer.size % PLAYER_COLORS.length]);
  }
  return colorByPlayer.get(playerId);
}

function cardField(card, field) {
  return card?.translations?.[currentLanguage]?.[field] ?? card?.[field] ?? "";
}

function zoneCardOwner(containerId, zone, cardId) {
  return latestState?.players?.[containerId]?.zones?.[zone]?.owners?.[cardId] || containerId;
}

function cardDestinationOwner(cardOwnerId, zone) {
  if (zone !== "receptacle") return cardOwnerId;
  return Object.keys(latestState?.players || {}).find((playerId) => playerId !== cardOwnerId) || null;
}

function cardDestinationAllowed(cardOwnerId, containerId, zone) {
  return zone === "receptacle" ? Boolean(containerId && containerId !== cardOwnerId) : containerId === cardOwnerId;
}

function cardDestinationLabel(cardOwnerId, zone) {
  const containerId = cardDestinationOwner(cardOwnerId, zone);
  const ownerSuffix = zone === "receptacle" && containerId ? ` — ${(latestState.players[containerId] || {}).name || containerId}` : "";
  return `${t("moveTo")} ${t(zone)}${ownerSuffix}`;
}

function cardName(cardId) {
  const card = cardsById.get(cardId);
  return card ? cardField(card, "name") : cardId || "Unknown card";
}

function cardImage(cardId) {
  const card = cardsById.get(cardId);
  return card?.image || MISSING_CARD_IMAGE;
}

// Card art comes over the network: until a face has loaded the card shows its
// back (blurred), then the face comes in (only the first time it is fetched).
// The deck and the visible cards are fetched ahead, a few at a time, when idle.
const loadedCardImages = new Set();
let cardArtUrls = null;
function isCardArt(src) {
  if (!cardArtUrls || cardArtUrls.size < cardsById.size) {
    cardArtUrls = new Set([...cardsById.values()].map((card) => card.image && new URL(card.image, location.href).href).filter(Boolean));
  }
  return cardArtUrls.has(src);
}
function watchCardImage(img) {
  const src = img.currentSrc || img.src;
  if (!src || loadedCardImages.has(src) || !isCardArt(src)) return;
  if (img.complete && img.naturalWidth) {
    loadedCardImages.add(src);
    return;
  }
  img.classList.add("ko-img-loading");
  img.addEventListener("load", () => {
    loadedCardImages.add(src);
    img.classList.remove("ko-img-loading");
    img.classList.add("ko-img-in");
    window.setTimeout(() => img.classList.remove("ko-img-in"), 400);
  }, { once: true });
  img.addEventListener("error", () => img.classList.remove("ko-img-loading"), { once: true });
}
const preloadedCardImages = new Set();
function preloadCardImages(cardIds) {
  const queue = [...new Set(cardIds)].map((cardId) => cardsById.get(cardId)?.image).filter((src) => src && !preloadedCardImages.has(src));
  if (!queue.length) return;
  queue.forEach((src) => preloadedCardImages.add(src));
  const idle = window.requestIdleCallback || ((callback) => window.setTimeout(callback, 120));
  const step = () => {
    queue.splice(0, 4).forEach((src) => {
      const img = new Image();
      img.decoding = "async";
      img.fetchPriority = "low";
      img.onload = () => loadedCardImages.add(img.src);
      img.src = src;
    });
    if (queue.length) idle(step);
  };
  idle(step);
}
// my whole deck, then every card the state shows
function stateCardIds(state) {
  const ids = [];
  const collect = (value) => {
    if (typeof value === "string") { if (cardsById.has(value)) ids.push(value); }
    else if (Array.isArray(value)) value.forEach(collect);
    else if (value && typeof value === "object") Object.values(value).forEach(collect);
  };
  collect(state?.players?.[myPlayerId]?.deckDefinition);
  Object.values(state?.players || {}).forEach((player) => Object.values(player.zones || {}).forEach((zone) => collect(zone.cards)));
  (state?.battlefield || []).forEach((item) => { if (item.faceUp && item.cardId) ids.push(item.cardId); });
  return ids;
}

function battlefieldItemControllerId(item) {
  return item?.controllerId || item?.ownerId || null;
}

function cardAutomationCoverage(cardId) {
  return automationCoverageByCard.get(cardId) || {
    status: "manual", abilityIds: [], mechanics: [], testRefs: [],
  };
}

function automationCoverageBadgeHtml(cardId, force = false) {
  if (!force && !latestState?.rulesEngine?.enabled && !rulesBetaActivated) return "";
  const coverage = cardAutomationCoverage(cardId);
  if (coverage.status === "automated" && !force) return "";
  const key = `automationStatus_${coverage.status}`;
  return `<span class="automation-coverage-badge status-${esc(coverage.status)}" title="${esc(t(key))}" aria-label="${esc(t(key))}">${esc(t(`automationStatusShort_${coverage.status}`))}</span>`;
}

const RARITY_EFFECTS_KEY = "ko_rarity_effects_enabled.v2";

const RARITY_IDS = new Set(["foil", "silver", "gold", "desert", "galaxy", "void", "zen", "common-glitter", "foil-glitter", "silver-glitter", "gold-glitter", "desert-glitter"]);

function normalizeRarity(rarity) {
  return RARITY_IDS.has(rarity) ? rarity : null;
}

function rarityBase(rarity) {
  return rarity && rarity.endsWith("-glitter") ? rarity.slice(0, -8) : rarity;
}

function rarityClassAttr(rarity) {
  const normalized = normalizeRarity(rarity);
  if (!normalized) return "";
  const base = rarityBase(normalized);
  return ` ko-rarity-card rarity-${base}${base !== normalized ? " rarity-glitter-fx" : ""}`;
}

function rarityDecorMarkup(rarity) {
  const normalized = normalizeRarity(rarity);
  if (normalized === "zen") return '<i class="rarity-zen-holo" aria-hidden="true"></i><i class="rarity-zen-secret" aria-hidden="true"></i>';
  return normalized?.endsWith("-glitter") ? '<i class="rarity-glitter-layer" aria-hidden="true"></i>' : "";
}

function raritySurfaceMarkup(rarity, content) {
  const decorated = content + rarityDecorMarkup(rarity);
  if (rarityBase(normalizeRarity(rarity)) !== "desert") return decorated;
  return `<span class="rarity-desert-surface">${decorated}<i class="desert-grain-layer" aria-hidden="true"></i><i class="desert-diagonal-layer" aria-hidden="true"></i><i class="desert-storm-layer" aria-hidden="true"></i></span>`;
}

function rarityForCard(ownerId, cardId) {
  return normalizeRarity(latestState?.players?.[ownerId]?.cardRarities?.[cardId]);
}

function visibleRarityForCard(cardId) {
  const battlefieldMatch = latestState?.battlefield?.find((item) => item.faceUp && item.cardId === cardId && normalizeRarity(item.rarity));
  if (battlefieldMatch) return normalizeRarity(battlefieldMatch.rarity);
  for (const player of Object.values(latestState?.players || {})) {
    const rarity = normalizeRarity(player.cardRarities?.[cardId]);
    if (rarity) return rarity;
  }
  return null;
}

function rarityCosmosStyle(cardId) {
  let hash = 0;
  for (let i = 0; i < String(cardId).length; i++) hash = (hash * 31 + String(cardId).charCodeAt(i)) | 0;
  const x = Math.abs(hash % 1000) / 10;
  const y = Math.abs((hash >> 8) % 1000) / 10;
  const card = cardsById.get(cardId);
  const palette = (card?.temperaments || []).map(temperamentInk).filter(Boolean);
  const zenA = palette[0] || card?.ink || "#9fc9c5";
  const zenB = palette[1] || card?.glow || zenA;
  return `--cosmos-x:${x.toFixed(1)}%;--cosmos-y:${y.toFixed(1)}%;--zen-a:${zenA};--zen-b:${zenB};`;
}

function updateRarityPointer(el, event, tilt, source = el) {
  if (!el || rarityEffectsDisabled) return;
  const rect = source.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const x = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
  const y = Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height));
  el.style.setProperty("--spot-x", `${(x * 100).toFixed(1)}%`);
  el.style.setProperty("--spot-y", `${(y * 100).toFixed(1)}%`);
  el.style.setProperty("--fx-shift-x", `${((x - .5) * 10).toFixed(1)}px`);
  el.style.setProperty("--fx-shift-y", `${((y - .5) * 8).toFixed(1)}px`);
  el.style.setProperty("--stack-shift-x", `${((x - .5) * 10).toFixed(1)}px`);
  el.style.setProperty("--stack-shift-y", `${((y - .5) * 8).toFixed(1)}px`);
  el.style.setProperty("--pointer-from-left", x.toFixed(3));
  el.style.setProperty("--pointer-from-top", y.toFixed(3));
  el.style.setProperty("--pointer-from-center", Math.min(1, Math.hypot((x - .5) * 2, (y - .5) * 2)).toFixed(3));
  el.style.setProperty("--desert-tilt-glint", Math.min(1, (Math.abs((x - .5) * 18) + Math.abs((.5 - y) * 14)) / 22).toFixed(3));
  if (tilt) {
    el.style.setProperty("--rarity-tilt-x", `${((x - .5) * 18).toFixed(2)}deg`);
    el.style.setProperty("--rarity-tilt-y", `${((.5 - y) * 14).toFixed(2)}deg`);
  }
}

function bindRarityPointer(el, tilt = false, source = el) {
  if (!el || !source || !el.classList.contains("ko-rarity-card")) return;
  source.addEventListener("pointermove", (event) => updateRarityPointer(el, event, tilt, source));
  source.addEventListener("pointerleave", () => {
    el.style.setProperty("--spot-x", "50%");
    el.style.setProperty("--spot-y", "50%");
    el.style.setProperty("--fx-shift-x", "0px");
    el.style.setProperty("--fx-shift-y", "0px");
    el.style.setProperty("--stack-shift-x", "0px");
    el.style.setProperty("--stack-shift-y", "0px");
    el.style.setProperty("--pointer-from-left", ".5");
    el.style.setProperty("--pointer-from-top", ".5");
    el.style.setProperty("--pointer-from-center", "0");
    el.style.setProperty("--desert-tilt-glint", "0");
    if (tilt) {
      el.style.setProperty("--rarity-tilt-x", "0deg");
      el.style.setProperty("--rarity-tilt-y", "0deg");
    }
  });
}

function applyRarityEffectsPreference() {
  document.body.classList.toggle("rarity-effects-disabled", rarityEffectsDisabled);
  const button = $("#rarityEffectsToggleBtn");
  if (!button) return;
  button.classList.toggle("active", !rarityEffectsDisabled);
  button.setAttribute("aria-pressed", String(!rarityEffectsDisabled));
  button.innerHTML = rarityEffectsIconSvg();
  button.title = t(rarityEffectsDisabled ? "enableRarityEffects" : "disableRarityEffects");
}

function initRarityEffectsToggle() {
  const button = $("#rarityEffectsToggleBtn");
  applyRarityEffectsPreference();
  button.onclick = () => {
    rarityEffectsDisabled = !rarityEffectsDisabled;
    localStorage.setItem(RARITY_EFFECTS_KEY, rarityEffectsDisabled ? "0" : "1");
    applyRarityEffectsPreference();
    renderAll();
  };
}
