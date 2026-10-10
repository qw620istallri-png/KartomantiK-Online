const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const ZONES = ["deck", "hand", "graveyard", "exile", "receptacle"];
const PRIVATE_ZONES = new Set(["deck", "hand", "exile"]);
// picked to contrast against the board's dark navy background (#0b1e3a)
const PLAYER_COLORS = ["#d3654a", "#3fc9a8", "#8bbf4f", "#b06fd6", "#d98a2b", "#4fa3d9"];
// Keep this value in sync with index.html and style.css when a local asset changes.
const STATIC_ASSET_VERSION = "20261010-rules-beta-102";
const staticAsset = (path) => `${path}?v=${STATIC_ASSET_VERSION}`;
const DECKOMANTIK_DESERT_ASSET_ROOT = "https://qw620istallri-png.github.io/DECKOMANTIK/assets/Desert";
const MISSING_CARD_IMAGE = `${DECKOMANTIK_DESERT_ASSET_ROOT}/Missing_Card_Image.png`;

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

function rulesTributeCandidate(reference) {
  const value = String(reference || "");
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
  return card ? { ...card, paymentValue: value } : null;
}

function rulesRemainingAfterManifestations(cardIds, requirements) {
  const remaining = { ...requirements };
  const cards = cardIds.map(rulesTributeCandidate).filter(Boolean)
    .sort((a, b) => Number(cardTributeTemperaments(a).includes("transcendent")) - Number(cardTributeTemperaments(b).includes("transcendent")));
  for (const card of cards) {
    const power = Math.max(0, Number(card.power) || 0);
    const printedTemperament = card.temperaments?.[0];
    const tributeTemperaments = cardTributeTemperaments(card);
    let temperament = printedTemperament;
    let used = 0;
    if (tributeTemperaments.includes("transcendent")) {
      for (const required of Object.keys(remaining)) {
        const amount = Math.min(power - used, remaining[required]);
        remaining[required] -= amount;
        used += amount;
        if (used >= power) break;
      }
    } else {
      let payable = tributeTemperaments.find(
        (candidate) => Object.hasOwn(remaining, candidate) && remaining[candidate] > 0,
      );
      if (!payable && Number(remaining.hollow || 0) > 0) payable = "hollow";
      if (payable && Object.hasOwn(remaining, payable)) remaining[payable] -= Math.min(power, remaining[payable]);
    }
  }
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
let clientId = localStorage.getItem("ko_clientId");
if (!clientId) {
  clientId = (crypto.randomUUID ? crypto.randomUUID() : String(Math.random())).replace(/-/g, "").slice(0, 24);
  localStorage.setItem("ko_clientId", clientId);
}

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
const revealedHandCards = new Map(); // playerId -> Set(cardId) ever revealed from their hand, for the hand-view popup
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
  const key = `automationStatus_${coverage.status}`;
  return `<span class="automation-coverage-badge status-${esc(coverage.status)}" title="${esc(t(key))}" aria-label="${esc(t(key))}">${esc(t(`automationStatusShort_${coverage.status}`))}</span>`;
}

const RARITY_EFFECTS_KEY = "ko_rarity_effects_enabled.v2";
const RARITY_IDS = new Set(["foil", "silver", "gold", "desert", "galaxy", "void", "zen", "common-glitter", "foil-glitter", "silver-glitter", "gold-glitter", "desert-glitter"]);
// Positive, versioned preference: new and existing browsers start with rarity effects enabled.
let rarityEffectsDisabled = localStorage.getItem(RARITY_EFFECTS_KEY) === "0";

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
          (Array.isArray(abilities) ? abilities : []).filter((ability) => !ability.trigger && !ability.passiveEffect && ability.action !== "play_card"),
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

const BASIC_PHASES = PHASE_GROUPS.map((group) => ({
  id: group.id, label: group.label, detail: group.detail, parent: group.id,
}));
const ADVANCED_PHASES = PHASE_GROUPS.flatMap((group) =>
  group.sections.flatMap((section) =>
    section.steps.map((step, index) => ({
      ...step,
      parent: group.id,
      subphase: section.label,
      stepNumber: index + 1,
    }))
  )
);
const PHASE_VISIBILITY_KEY = "ko_phase_tracker_visible.v3";
let phaseTrackerVisible = localStorage.getItem(PHASE_VISIBILITY_KEY) === "1";

function currentPhaseUi(tracker = latestState?.phaseTracker) {
  const safeTracker = tracker || { enabled: false, advanced: false, index: 0, turn: 1, passedPlayerIds: [] };
  const phases = safeTracker.advanced ? ADVANCED_PHASES : BASIC_PHASES;
  const index = Math.min(Math.max(Number(safeTracker.index) || 0, 0), phases.length - 1);
  const phase = phases[index] || phases[0];
  const group = PHASE_GROUPS.find((item) => item.id === (phase?.parent || phase?.id)) || PHASE_GROUPS[0];
  return { tracker: safeTracker, phases, index, phase, group };
}

function currentPhaseLines(tracker = latestState?.phaseTracker) {
  const state = currentPhaseUi(tracker);
  if (!state.tracker.enabled || !state.phase || !state.group) return { phase: "", step: "" };
  const phase = t(state.group.label);
  let step = "";
  if (state.tracker.advanced) {
    const parts = [];
    if (state.phase.subphase) parts.push(t(state.phase.subphase));
    parts.push(`${t("phaseStep")} ${state.phase.stepNumber} — ${t(state.phase.label)}`);
    step = parts.join(" · ");
  }
  return { phase, step };
}

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

function deckImportValidation(pending = pendingDeckImport) {
  if (!pending) return { valid: false, message: t("deckMissing") };
  const errors = [];
  if (pending.mainIds.length !== 30) errors.push(rulesText("deckCountInvalid", { count: pending.mainIds.length }));
  const points = deckImportPoints(pending.mainIds);
  if (points > 500) errors.push(rulesText("deckPointsInvalid", { points }));
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
  const validPoints = points <= 500;
  $("#sideboardDeckHeading").textContent = t("deckPool");
  $("#sideboardPoolHeading").textContent = t("sideboard");
  $("#sideboardDeckStats").innerHTML = `<strong class="${validCount ? "valid" : "invalid"}">${pendingDeckImport.mainIds.length}/30 ${esc(t("cards"))}</strong><strong class="${validPoints ? "valid" : "invalid"}">${points}/500 ${esc(t("points"))}</strong>`;
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

function currentPhaseLabel(tracker = latestState?.phaseTracker) {
  const lines = currentPhaseLines(tracker);
  return [lines.phase, lines.step].filter(Boolean).join("\n");
}

function toggleMyPhasePass() {
  const tracker = latestState?.phaseTracker;
  if (isObserver || !tracker?.enabled) return;
  const rules = latestState?.rulesEngine;
  if (rules?.enabled) {
    if (rulesFirstManifestationActive()) {
      const validated = !(rules.firstManifestationValidatedPlayerIds || []).includes(myPlayerId);
      send({ type: "validate_first_manifestation", validated });
      return;
    }
    const alreadyPassed = (rules.priorityPasses || []).includes(myPlayerId);
    if (alreadyPassed) send({ type: "pass_priority", passed: false });
    else if (rules.priorityPlayerId === myPlayerId) send({ type: "pass_priority", passed: true });
    return;
  }
  const passed = new Set(tracker.passedPlayerIds || []);
  send({ type: "pass_phase", passed: !passed.has(myPlayerId) });
}

function rulesFirstManifestationActive() {
  const rules = latestState?.rulesEngine;
  return Boolean(
    rules?.enabled
    && currentPhaseUi().phase?.id === "confrontation_choose"
    && !rules.firstManifestationComplete
  );
}

function renderConfrontationSummary(rules) {
  const element = $("#rulesConfrontationSummary");
  const result = rules?.confrontationResult;
  const phaseGroup = currentPhaseUi().group?.id;
  const visible = Boolean(result && phaseGroup === "resolution");
  element.classList.toggle("hidden", !visible);
  if (!visible) return;
  const playerIds = Object.keys(result.totals || {});
  const score = playerIds
    .map((playerId) => `${rulesPlayerName(playerId)} ${Number(result.totals[playerId] || 0)}`)
    .join(" · ");
  const outcome = result.stalemate
    ? t("rulesConfrontationStalemate")
    : rulesText("rulesConfrontationWinner", { player: rulesPlayerName(result.winnerId) });
  element.textContent = `${score} — ${outcome}`;
  element.classList.toggle("stalemate", Boolean(result.stalemate));
  element.style.setProperty("--winner-tone", result.winnerId ? playerColor(result.winnerId) : "#b8ad91");
}

function wirePhasePassControls(root) {
  root.querySelectorAll("[data-pass-phase]").forEach((button) => {
    button.onclick = (event) => {
      event.stopPropagation();
      toggleMyPhasePass();
    };
  });
}

function phaseStepMarkup(step, index, active, canPass, passIsActive, opponentPassIsActive) {
  const body = `<span class="phase-step-number">${esc(t("phaseStep"))} ${index + 1}</span>
    <span class="phase-step-label">${esc(t(step.label))}</span>`;
  if (active && canPass) {
    const action = t(latestState?.rulesEngine?.enabled ? "passPriority" : (passIsActive ? "cancelPhasePass" : "passPhase"));
    return `<button type="button" class="phase-step active phase-pass-target ${passIsActive ? "passed" : ""} ${opponentPassIsActive ? "opponent-passed" : ""}" data-pass-phase title="${esc(t(step.detail))}" aria-label="${esc(`${t(step.label)} — ${action}`)}" aria-current="step" aria-pressed="${passIsActive}">${body}</button>`;
  }
  return `<div class="phase-step ${active ? "active" : ""}" title="${esc(t(step.detail))}" aria-current="${active ? "step" : "false"}">${body}</div>`;
}

function renderPhaseChildren(group, activePhaseId, canPass, passIsActive, opponentPassIsActive) {
  return `<div class="phase-children">${group.sections.map((section) =>
    `<section class="phase-subphase" style="--subphase-weight:${section.steps.length}">
      ${section.label ? `<strong class="phase-subphase-title">${esc(t(section.label))}</strong>` : ""}
      <div class="phase-step-row">${section.steps.map((step, index) =>
        phaseStepMarkup(step, index, step.id === activePhaseId, canPass, passIsActive, opponentPassIsActive)
      ).join("")}</div>
    </section>`
  ).join("")}</div>`;
}

function phaseIconSvg(groupId) {
  const paths = {
    recovery: '<path d="M7 7a7 7 0 1 1-1.6 7.6"/><path d="M7 3v4H3"/><path d="M9 12h6M12 9v6"/>',
    confrontation: '<path d="m5 4 6 6-2 2-6-6V4h2Z"/><path d="m19 4-6 6 2 2 6-6V4h-2Z"/><path d="m8 13-3 3m11-3 3 3M3.5 18.5l2 2m15-2-2 2"/>',
    resolution: '<path d="M12 3v18M6 6h12M7 6 4 12h6L7 6Zm10 0-3 6h6l-3-6ZM8 21h8"/>',
    end: '<path d="M18.5 15.5A8 8 0 0 1 8.5 5a8 8 0 1 0 10 10.5Z"/><path d="M15.5 5.5h3m-1.5-1.5v3"/>',
  };
  return `<svg viewBox="0 0 24 24" aria-hidden="true">${paths[groupId] || paths.recovery}</svg>`;
}

function renderPhaseTracker() {
  const { tracker, phase: activePhase, group: activeGroup } = currentPhaseUi();
  const panel = $("#phaseTracker");
  const rules = latestState?.rulesEngine;
  const panelVisible = tracker.enabled && (Boolean(rules?.enabled) || phaseTrackerVisible);
  const canConfigureAdvanced = !isObserver && mySeat() === 0 && !latestState?.rulesEngine?.enabled;
  const showAdvancedControl = panelVisible && canConfigureAdvanced;
  panel.classList.toggle("hidden", !panelVisible);
  $("#gameScreen").classList.toggle("phase-details-visible", panelVisible);
  $("#phaseTrackerBtn").textContent = t("gamePhases");
  $("#phaseTrackerBtn").title = t(panelVisible ? "hidePhases" : "showPhases");
  $("#phaseTrackerBtn").classList.toggle("active", panelVisible);
  $("#phaseTrackerBtn").disabled = isObserver && !tracker.enabled;
  $("#phaseHeaderControl").classList.toggle("expanded", showAdvancedControl);
  $("#phaseAdvancedLabel").textContent = t("advancedMode");
  $("#phaseAdvancedBtn").title = t("advancedMode");
  $("#phaseAdvancedBtn").classList.toggle("hidden", !canConfigureAdvanced);
  $("#phaseAdvancedBtn").classList.toggle("active", tracker.advanced);
  $("#phaseAdvancedBtn").disabled = !showAdvancedControl;
  $("#phaseAdvancedBtn").setAttribute("aria-pressed", String(Boolean(tracker.advanced)));
  $("#phaseTurn").classList.toggle("hidden", !tracker.enabled);
  if (tracker.enabled) $("#phaseTurn").textContent = `${t("turn")} ${tracker.turn || 1}`;
  if (!tracker.enabled) return;

  const activeGroupId = activeGroup?.id || activePhase?.parent || activePhase?.id;
  const passedPlayerIds = new Set(rules?.enabled ? (rules.priorityPasses || []) : (tracker.passedPlayerIds || []));
  const passIsActive = passedPlayerIds.has(myPlayerId);
  const opponentPassIsActive = !isObserver && [...passedPlayerIds].some((playerId) => playerId !== myPlayerId);
  $("#phaseSequence").classList.toggle("advanced", tracker.advanced);
  $("#phaseSequence").innerHTML = PHASE_GROUPS.map((group) => {
    const active = group.id === activeGroupId;
    const groupSteps = group.sections.flatMap((section) => section.steps);
    const stepIndex = Math.max(0, groupSteps.findIndex((step) => step.id === activePhase?.id));
    const phaseDetail = active && tracker.advanced
      ? `${t(activePhase.label)} — ${t(activePhase.detail)}`
      : t(group.detail);
    return `<div class="phase-orb ${active ? "active" : ""} ${passIsActive && active ? "passed" : ""} ${opponentPassIsActive && active ? "opponent-passed" : ""}"
      data-phase-group="${esc(group.id)}" aria-current="${active ? "step" : "false"}">
      ${phaseIconSvg(group.id)}
      <span class="phase-orb-label">${esc(t(group.label))}</span>
      <span class="phase-orb-tooltip"><strong>${esc(t(group.label))}</strong>${active && tracker.advanced ? `<span>${esc(`${t("phaseStep")} ${stepIndex + 1}/${groupSteps.length} · ${t(activePhase.label)}`)}</span>` : ""}<span>${esc(phaseDetail)}</span></span>
    </div>`;
  }).join("");
  $("#phaseCurrentMain").textContent = t(activeGroup?.label || activePhase?.label || "");
  $("#phaseCurrentStep").textContent = tracker.advanced && activePhase ? t(activePhase.label) : "";
  wirePhasePassControls(panel);
}

function rulesPlayerName(playerId) {
  return latestState?.players?.[playerId]?.name || playerId || "—";
}

function rulesText(key, values = {}) {
  return String(t(key)).replace(/\{(\w+)\}/g, (_match, name) => values[name] ?? "");
}

function rulesActionDisplayLabel(action) {
  const cardId = action?.source?.cardId;
  if (!cardId) return t("rulesUnknownAction");
  if (action.kind === "triggered_effect") {
    return `${cardName(cardId)} — ${t("rulesKindTriggered")}`;
  }
  if (action.kind === "activated_effect") {
    return rulesText("rulesDefaultActivate", { card: cardName(cardId) });
  }
  if (action.kind === "play_card") {
    return rulesText(action.asSupport ? "rulesDefaultSupport" : "rulesDefaultPlay", {
      card: cardName(cardId),
    });
  }
  return cardName(cardId);
}

function rulesActionCardRef(cardId) {
  return `<span class="rules-card-ref" data-rules-card="${esc(cardId)}">${esc(cardName(cardId))}</span>`;
}

function rulesActionTargetRef(target) {
  if (target?.kind === "player") return esc(rulesPlayerName(target.playerId));
  const location = ["stack_action", "stack_effect"].includes(target?.kind)
    ? t("rulesStackTitle")
    : target?.kind === "zone_card"
    ? `${rulesPlayerName(target.containerId)} · ${t(target.zone)}`
    : rulesPlayerName(target.ownerId);
  return `${rulesActionCardRef(target.cardId)} (${esc(location)})`;
}

function rulesEssenceEntriesText(entries) {
  const totals = {};
  for (const entry of entries || []) totals[entry.temperament] = (totals[entry.temperament] || 0) + Number(entry.amount || 0);
  return Object.entries(totals)
    .map(([temperament, amount]) => `${esc(t(`temperament${temperament[0].toUpperCase()}${temperament.slice(1)}`))} ×${amount}`)
    .join(", ");
}

function rulesActionDetails(action) {
  const details = [];
  if (action.isStackCopy) details.push(`<span class="rules-stack-copy-state">${esc(t("rulesStackCopy"))}</span>`);
  if (action.source?.cardId) details.push(rulesActionCardRef(action.source.cardId));
  if (action.targets?.length) {
    details.push(`${esc(t("rulesTargetsShort"))}: ${action.targets.map(rulesActionTargetRef).join(", ")}`);
  }
  if (action.cost?.essenceSpent?.length) details.push(`${esc(t("rulesEssenceShort"))}: ${rulesEssenceEntriesText(action.cost.essenceSpent)}`);
  if (action.cost?.tributeCardIds?.length) {
    details.push(`${esc(t("rulesTributeShort"))}: ${action.cost.tributeCardIds.map(rulesActionCardRef).join(", ")}`);
  }
  if (action.cost?.excessEssence?.length) details.push(`${esc(t("rulesExcessShort"))}: ${rulesEssenceEntriesText(action.cost.excessEssence)}`);
  if (action.cost?.sourceExhausted) details.push(esc(t("rulesSourceExhaustedShort")));
  if (action.cost?.sourceSacrificed) details.push(esc(t("rulesSourceSacrificedShort")));
  return details.join(" · ");
}

function wireRulesStackCardRefs() {
  $$("#rulesStackPanel [data-rules-card]").forEach((element) => {
    const cardId = element.dataset.rulesCard;
    element.onmouseenter = () => showCardPreview(cardId, element);
    element.onmouseleave = hideCardPreview;
    element.onclick = () => showInspect(cardId);
  });
}

function renderRulesStack() {
  const panel = $("#rulesStackPanel");
  const rules = latestState?.rulesEngine;
  const visible = Boolean(rules?.enabled);
  panel.classList.toggle("hidden", !visible);
  if (!visible) return;

  const readyIds = new Set(rules.readyPlayerIds || []);
  const pregameActive = latestState?.phaseTracker?.turn === 1
    && currentPhaseUi().phase?.id === "recovery_start"
    && readyIds.size < 2;
  const playersReady = Object.keys(latestState?.players || {}).length >= 2 && !pregameActive;
  const priorityPlayerId = rules.priorityPlayerId;
  const pendingChoice = rules.pendingChoice;
  renderConfrontationSummary(rules);
  const firstManifestation = rulesFirstManifestationActive();
  const firstItemIds = rules.firstManifestationItemIds || {};
  const firstValidated = rules.firstManifestationValidatedPlayerIds || [];
  const mineHasFirstManifestation = Boolean(firstItemIds[myPlayerId]);
  const mineFirstValidated = firstValidated.includes(myPlayerId);
  const opponentFirstValidated = firstValidated.some((playerId) => playerId !== myPlayerId);
  const priorityPasses = rules.priorityPasses || [];
  const myPassActive = priorityPasses.includes(myPlayerId);
  const myPriority = playersReady && !pendingChoice && !firstManifestation && !isObserver && priorityPlayerId === myPlayerId;
  const canCancelPass = playersReady && !pendingChoice && !isObserver && myPassActive;
  const stack = Array.isArray(rules.actionStack) ? rules.actionStack : [];
  const resolutionArmed = stack.length > 0 && priorityPasses.length > 0;
  if (!myPriority && !$("#rulesActionPanel").classList.contains("hidden")) closeRulesActionPanel();
  panel.classList.toggle("rules-stack-readonly", isObserver);
  const phaseLines = currentPhaseLines();
  const phaseContext = [
    `${t("turn")} ${latestState?.phaseTracker?.turn || 1}`,
    phaseLines.phase,
    phaseLines.step,
  ].filter(Boolean).join(" · ");
  $("#rulesTurnContext").textContent = phaseContext;
  $("#rulesTurnContext").title = phaseContext;
  const priority = $("#rulesPriority");
  priority.classList.toggle("waiting", firstManifestation || !playersReady || !priorityPlayerId || Boolean(pendingChoice));
  priority.classList.toggle("is-mine", myPriority);
  priority.classList.toggle("is-passed", canCancelPass);
  priority.textContent = firstManifestation
    ? t(mineFirstValidated ? "rulesFirstManifestationWaiting" : "rulesFirstManifestationChoose")
    : pendingChoice
    ? rulesText("rulesWaitingChoice", { player: rulesPlayerName(pendingChoice.playerId) })
    : !playersReady || !priorityPlayerId
    ? t("rulesWaitingPlayers")
    : canCancelPass
      ? rulesText("rulesPriorityPassedSelf", { player: rulesPlayerName(priorityPlayerId) })
    : myPriority && stack.length
      ? t(resolutionArmed ? "rulesYourPriorityResolve" : "rulesYourPriorityRespond")
    : myPriority
      ? t("rulesYourPriority")
      : rulesText("rulesPriorityPlayer", { player: rulesPlayerName(priorityPlayerId) });

  panel.classList.toggle("hidden", stack.length === 0);
  const stackTitle = $("#rulesStackTitle");
  stackTitle.classList.toggle("hidden", stack.length === 0);
  stackTitle.textContent = `${t("rulesStackTitle")} · ${stack.length}`;
  $("#rulesStackBody").classList.toggle("hidden", stack.length === 0);
  panel.classList.toggle("has-actions", stack.length > 0);
  const responseSlot = myPriority
    ? `<li class="rules-stack-response-slot ${resolutionArmed ? "before-resolution" : ""}" aria-label="${esc(t(resolutionArmed ? "rulesStackRespondBeforeResolve" : "rulesStackRespondSlot"))}">
        <strong>${esc(t(resolutionArmed ? "rulesStackRespondBeforeResolve" : "rulesStackRespondSlot"))}</strong>
        <small>${esc(t("rulesStackResponseSlotHint"))}</small>
      </li>`
    : "";
  const stackActions = [...stack].reverse().map((action, index) => {
        const level = stack.length - index;
        const controller = rulesPlayerName(action.controllerId);
        const details = rulesActionDetails(action);
        const displayLabel = rulesActionDisplayLabel(action);
        const sourceCardId = action.source?.cardId;
        const sourceCard = sourceCardId
          ? `<button type="button" class="rules-stack-card" data-rules-card="${esc(sourceCardId)}" aria-label="${esc(cardName(sourceCardId))}" title="${esc(cardName(sourceCardId))}"><img src="${esc(cardImage(sourceCardId))}" alt=""></button>`
          : "";
        const awaitingPayment = rules.pendingChoice?.kind === "stack_counter_payment"
          && rules.pendingChoice.targetActionId === action.id;
        const resolvesOnPass = index === 0 && myPriority && resolutionArmed;
        return `<li class="${awaitingPayment ? "rules-counter-payment-target " : ""}${resolvesOnPass ? "will-resolve" : ""}" data-stack-action-id="${esc(action.id)}" style="--stack-player-color:${esc(playerColor(action.controllerId))}" title="${esc(`${controller} — ${displayLabel}`)}">${sourceCard}<div class="rules-stack-copy"><div class="rules-stack-main"><span class="rules-stack-index">${index === 0 ? esc(t("rulesStackTop")) : `#${level}`}</span><strong>${esc(displayLabel)}</strong><small>${esc(controller)}</small></div>${resolvesOnPass ? `<span class="rules-stack-resolve-state">${esc(t("rulesStackResolveOnPass"))}</span>` : ""}${awaitingPayment ? `<span class="rules-stack-payment-state">${esc(t("rulesStackPaymentPending"))}</span>` : ""}${details ? `<div class="rules-stack-detail">${details}</div>` : ""}</div></li>`;
      }).join("");
  $("#rulesStackList").innerHTML = responseSlot + stackActions;
  wireRulesStackCardRefs();

  const current = currentPhaseUi();
  const groupSteps = current.group.sections.flatMap((section) => section.steps);
  const currentStep = Math.max(0, groupSteps.findIndex((step) => step.id === current.phase.id)) + 1;
  $("#passPriorityBtn").textContent = firstManifestation
    ? t(mineFirstValidated ? "rulesFirstManifestationCancel" : "rulesFirstManifestationValidate")
    : canCancelPass
    ? t("cancelPriorityPass")
    : stack.length && resolutionArmed
    ? rulesText("rulesResolveTop", { card: rulesActionDisplayLabel(stack[stack.length - 1]) })
    : stack.length
    ? t("rulesPassWithoutResponse")
    : rulesText("rulesPassStep", { current: currentStep, total: groupSteps.length });
  $("#passPriorityBtn").title = stack.length
    ? t(resolutionArmed ? "rulesResolveTopHint" : "rulesPassWithoutResponseHint")
    : t(current.phase.detail);
  $("#passPriorityBtn").classList.toggle("hidden", firstManifestation ? isObserver : (!myPriority && !canCancelPass));
  $("#passPriorityBtn").classList.toggle("passed", canCancelPass);
  $("#passPriorityBtn").classList.toggle("offers-response", myPriority && stack.length > 0 && !resolutionArmed);
  $("#passPriorityBtn").classList.toggle("resolves-stack", myPriority && resolutionArmed);
  $("#passPriorityBtn").classList.toggle("opponent-validated", firstManifestation && opponentFirstValidated && !mineFirstValidated);
  $("#passPriorityBtn").setAttribute("aria-pressed", String(canCancelPass));
  $("#passPriorityBtn").disabled = firstManifestation
    ? (!mineHasFirstManifestation || isObserver)
    : (!myPriority && !canCancelPass);

  const firstPasser = priorityPasses[0];
  const hint = $("#rulesStackHint");
  hint.classList.toggle("hidden", !firstPasser || Boolean(pendingChoice));
  hint.textContent = firstPasser && !pendingChoice
    ? rulesText("rulesPriorityPassed", {
        player: rulesPlayerName(firstPasser),
        next: rulesPlayerName(priorityPlayerId),
      })
    : "";
}

function renderRulesPregame() {
  const panel = $("#rulesPregamePanel");
  const rules = latestState?.rulesEngine;
  const currentPhase = currentPhaseUi();
  const firstTurn = Boolean(!latestState?.ended && latestState?.phaseTracker?.turn === 1);
  const assistedOpeningWindow = firstTurn && currentPhase.phase?.id === "recovery_start";
  const assistedActive = Boolean(rules?.enabled && assistedOpeningWindow);
  const recoveryMulliganActive = rules_recovery_mulligan_active_client();
  const standardDeckSetup = standardDeckSetupActiveClient();
  const active = assistedActive || recoveryMulliganActive || standardDeckSetup;
  panel.classList.toggle("hidden", !active);
  panel.classList.remove("mulligan-required");
  $("#gameScreen").classList.toggle("rules-pregame-active", active);
  if (!active) return;

  if (standardDeckSetup) {
    const deckConfirmed = new Set(rules?.deckConfirmedPlayerIds || []);
    $("#rulesPregameTurn").textContent = t("rulesPregameTurn");
    $("#rulesPregameTitle").textContent = t("rulesDeckSetupTitle");
    $("#rulesPregameHint").textContent = t("rulesDeckSetupHint");
    $("#rulesPregamePlayers").innerHTML = Object.values(latestState.players || {}).map((player) => {
      const hasDeck = Boolean(player.deckDefinition);
      const isConfirmed = latestState.mode === "casual" ? deckConfirmed.has(player.id) : hasDeck;
      const statusKey = isConfirmed
        ? "rulesDeckConfirmedState"
        : (hasDeck ? "rulesDeckSelectedState" : "rulesDeckMissingState");
      return `<div class="rules-pregame-player ${isConfirmed ? "ready" : ""}">
        <span class="rules-pregame-player-mark" style="--player-tone:${esc(playerColor(player.id))}">${esc((player.name || "?").slice(0, 1).toUpperCase())}</span>
        <span><strong>${esc(player.name || player.id)}</strong><small>${esc(t(statusKey))}</small></span>
        <span class="rules-pregame-check" aria-hidden="true">${isConfirmed ? "✓" : ""}</span>
      </div>`;
    }).join("");
    $("#rulesPregameActions").classList.remove("hidden");
    $("#rulesPregameActions").classList.add("deck-stage");
    $("#rulesOpeningHandBtn").classList.remove("hidden");
    $("#rulesOpeningHandBtn").textContent = t("importDeck");
    $("#rulesOpeningHandBtn").dataset.action = "import";
    $("#rulesOpeningHandBtn").disabled = false;
    $("#rulesPregameMulliganBtn").classList.add("hidden");
    $("#rulesPregameReadyBtn").classList.add("hidden");
    return;
  }

  if (recoveryMulliganActive) {
    const required = new Set(rules.recoveryMulliganRequiredPlayerIds || []);
    const attempted = new Set(rules.recoveryMulliganPlayerIds || []);
    const failed = new Set(rules.recoveryMulliganFailedPlayerIds || []);
    const mineNeedsMulligan = required.has(myPlayerId);
    panel.classList.add("mulligan-required");
    $("#rulesPregameTurn").textContent = rulesText("rulesRecoveryTurn", {
      turn: latestState.phaseTracker.turn,
    });
    $("#rulesPregameTitle").textContent = t(mineNeedsMulligan
      ? "rulesRecoveryMulliganRequiredTitle"
      : "rulesRecoveryMulliganWaitingTitle");
    $("#rulesPregameHint").textContent = t(mineNeedsMulligan
      ? "rulesRecoveryMulliganRequiredHint"
      : "rulesRecoveryMulliganWaitingHint");
    $("#rulesPregamePlayers").innerHTML = Object.values(latestState.players || {}).map((player) => {
      const needsMulligan = required.has(player.id);
      const didMulligan = attempted.has(player.id);
      const didFail = failed.has(player.id);
      const checked = !needsMulligan && !didFail;
      const statusKey = didFail
        ? "rulesRecoveryMulliganFailedState"
        : needsMulligan
          ? "rulesRecoveryMulliganRequiredState"
          : didMulligan
            ? "rulesRecoveryMulliganValidatedState"
            : "rulesRecoveryPlayableState";
      return `<div class="rules-pregame-player ${checked ? "ready" : ""}${needsMulligan || didFail ? " attention" : ""}">
        <span class="rules-pregame-player-mark" style="--player-tone:${esc(playerColor(player.id))}">${esc((player.name || "?").slice(0, 1).toUpperCase())}</span>
        <span><strong>${esc(player.name || player.id)}</strong><small>${esc(t(statusKey))}</small></span>
        <span class="rules-pregame-check" aria-hidden="true">${checked ? "✓" : needsMulligan || didFail ? "!" : ""}</span>
      </div>`;
    }).join("");
    const controlsHidden = isObserver || !latestState.players?.[myPlayerId];
    const waitingForOpponent = required.size > 0 && !mineNeedsMulligan;
    $("#rulesPregameActions").classList.toggle("hidden", controlsHidden || (!mineNeedsMulligan && !waitingForOpponent));
    $("#rulesPregameActions").classList.remove("deck-stage");
    $("#rulesPregameActions").classList.add("mulligan-stage");
    $("#rulesOpeningHandBtn").classList.add("hidden");
    $("#rulesPregameMulliganBtn").classList.toggle("hidden", !mineNeedsMulligan && !waitingForOpponent);
    $("#rulesPregameMulliganBtn").textContent = t(mineNeedsMulligan
      ? "rulesRecoveryMulliganAction"
      : "rulesRecoveryMulliganWaitingAction");
    $("#rulesPregameMulliganBtn").disabled = !mineNeedsMulligan;
    $("#rulesPregameMulliganBtn").dataset.mulliganMode = "recovery";
    $("#rulesPregameReadyBtn").classList.add("hidden");
    return;
  }

  const opened = new Set(rules.openingHandPlayerIds || []);
  const mulliganed = new Set(rules.mulliganPlayerIds || []);
  const mulliganRequired = new Set(rules.openingMulliganRequiredPlayerIds || []);
  const mulliganFailed = new Set(rules.openingMulliganFailedPlayerIds || []);
  const ready = new Set(rules.readyPlayerIds || []);
  const deckConfirmed = new Set(rules.deckConfirmedPlayerIds || []);
  const playerIds = Object.keys(latestState.players || {});
  const decksReady = playerIds.length >= 2 && playerIds.every((playerId) => deckConfirmed.has(playerId));
  $("#rulesPregameTurn").textContent = t("rulesPregameTurn");
  const mineNeedsMulligan = mulliganRequired.has(myPlayerId);
  const mineOpened = opened.has(myPlayerId);
  const mineMulliganed = mulliganed.has(myPlayerId);
  const mineReady = ready.has(myPlayerId);
  const mineChoosingHand = decksReady && mineOpened && !mineNeedsMulligan && !mineReady;
  const openingPaused = decksReady && mulliganRequired.size > 0;
  panel.classList.toggle("mulligan-required", openingPaused);
  $("#rulesPregameTitle").textContent = t(!decksReady
    ? "rulesDeckSetupTitle"
    : mineNeedsMulligan
      ? "rulesMulliganRequiredTitle"
      : mineChoosingHand
        ? "rulesOpeningChoiceTitle"
        : "rulesOpeningWaitingTitle");
  $("#rulesPregameHint").textContent = t(!decksReady
    ? "rulesDeckSetupHint"
    : mineNeedsMulligan
      ? "rulesMulliganRequiredHint"
      : mineChoosingHand
        ? "rulesOpeningChoiceHint"
        : "rulesOpeningWaitingHint");
  $("#rulesPregamePlayers").innerHTML = Object.values(latestState.players || {}).map((player) => {
    const statusKey = !decksReady
      ? (deckConfirmed.has(player.id) ? "rulesDeckConfirmedState" : (player.deckDefinition ? "rulesDeckSelectedState" : "rulesDeckMissingState"))
      : mulliganFailed.has(player.id)
        ? "rulesMulliganFailedState"
        : mulliganRequired.has(player.id)
          ? "rulesMulliganRequiredState"
          : ready.has(player.id)
            ? (mulliganed.has(player.id) ? "rulesMulliganValidatedState" : "rulesOpeningPlayableState")
            : opened.has(player.id)
              ? "rulesOpeningChoosingState"
              : "rulesPregameWaitingState";
    const checked = decksReady ? ready.has(player.id) : deckConfirmed.has(player.id);
    const attention = mulliganRequired.has(player.id) || mulliganFailed.has(player.id);
    return `<div class="rules-pregame-player ${checked ? "ready" : ""}${attention ? " attention" : ""}">
      <span class="rules-pregame-player-mark" style="--player-tone:${esc(playerColor(player.id))}">${esc((player.name || "?").slice(0, 1).toUpperCase())}</span>
      <span><strong>${esc(player.name || player.id)}</strong><small>${esc(t(statusKey))}</small></span>
      <span class="rules-pregame-check" aria-hidden="true">${checked ? "✓" : attention ? "!" : ""}</span>
    </div>`;
  }).join("");

  const mineDeckConfirmed = deckConfirmed.has(myPlayerId);
  const mineHasDeck = Boolean(latestState.players?.[myPlayerId]?.deckDefinition);
  const opponentDeckConfirmed = playerIds.some((playerId) => playerId !== myPlayerId && deckConfirmed.has(playerId));
  const controlsHidden = isObserver || !latestState.players?.[myPlayerId];
  const canMulligan = decksReady && mineOpened && !mineMulliganed && !mineReady && !mulliganFailed.has(myPlayerId);
  const canKeepHand = decksReady && mineOpened && !mineNeedsMulligan && !mineReady && !mulliganFailed.has(myPlayerId);
  $("#rulesPregameActions").classList.toggle("hidden", controlsHidden || (decksReady && !canMulligan && !canKeepHand));
  $("#rulesPregameActions").classList.toggle("deck-stage", !decksReady);
  $("#rulesPregameActions").classList.toggle("mulligan-stage", decksReady);
  $("#rulesOpeningHandBtn").classList.toggle("hidden", decksReady);
  $("#rulesOpeningHandBtn").textContent = t("importDeck");
  $("#rulesOpeningHandBtn").dataset.action = "import";
  $("#rulesOpeningHandBtn").disabled = false;
  $("#rulesPregameMulliganBtn").classList.toggle("hidden", !canMulligan);
  $("#rulesPregameMulliganBtn").textContent = t(mineNeedsMulligan
    ? "rulesMulliganAction"
    : "rulesVoluntaryMulliganAction");
  $("#rulesPregameMulliganBtn").disabled = !canMulligan;
  $("#rulesPregameMulliganBtn").dataset.mulliganMode = "opening";
  $("#rulesPregameMulliganBtn").dataset.mulliganRequired = String(mineNeedsMulligan);
  $("#rulesPregameReadyBtn").classList.toggle("hidden", decksReady && !canKeepHand);
  $("#rulesPregameReadyBtn").textContent = decksReady
    ? t("rulesKeepOpeningHand")
    : (mineDeckConfirmed ? t("rulesCancelDeckValidation") : t("rulesValidateDeck"));
  $("#rulesPregameReadyBtn").disabled = decksReady ? !canKeepHand : !mineHasDeck;
  $("#rulesPregameReadyBtn").dataset.action = decksReady ? "opening" : "deck";
  $("#rulesPregameReadyBtn").classList.toggle("opponent-validated", !decksReady && opponentDeckConfirmed && !mineDeckConfirmed);
}

// ---------------------------------------------------------------- assisted-rules visual feedback

function rulesVfxCenter(element) {
  if (!element) return null;
  const rect = element.getBoundingClientRect();
  if (!rect.width && !rect.height) return null;
  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
}

function rulesVfxPlayerOrigin(playerId) {
  const player = latestState?.players?.[playerId];
  const mine = playerId === myPlayerId || (player && player.seat === mySeat());
  return { x: window.innerWidth / 2, y: mine ? window.innerHeight - 92 : 108 };
}

function rulesVfxStackTarget() {
  return rulesVfxCenter($("#rulesStackList [data-stack-action-id]"))
    || rulesVfxCenter($("#rulesStackPanel"))
    || { x: window.innerWidth / 2, y: window.innerHeight / 2 };
}

function rulesVfxStackNoticeTarget() {
  const panel = $("#rulesStackPanel")?.getBoundingClientRect();
  return panel?.width
    ? { x: panel.left + panel.width / 2, y: Math.max(30, panel.top - 8) }
    : rulesVfxStackTarget();
}

function rulesVfxFindBattlefieldItem(itemId) {
  if (!itemId) return null;
  return $$(".bf-card[data-item-id]").find((element) => element.dataset.itemId === itemId) || null;
}

function captureRulesVfxEvent(entry) {
  const details = entry.details || {};
  const fallback = rulesVfxPlayerOrigin(entry.actorId);
  const tributeOrigins = [];
  const handCards = $$('[data-hand-card]');
  const usedHandCards = new Set();
  for (const cardId of details.cost?.tributeCardIds || []) {
    const element = handCards.find((candidate) => candidate.dataset.handCard === cardId && !usedHandCards.has(candidate));
    if (element) usedHandCards.add(element);
    tributeOrigins.push({ cardId, origin: rulesVfxCenter(element) || fallback });
  }
  const essenceOrigins = (details.cost?.essenceSpent || []).map((payment) => {
    const element = $$(".bf-token[data-token-id]").find((candidate) => candidate.dataset.tokenId === payment.tokenId);
    return { ...payment, origin: rulesVfxCenter(element) || fallback };
  });
  const sourceElement = rulesVfxFindBattlefieldItem(details.source?.itemId);
  const sacrificedCard = details.cost?.sacrificedCards?.[0] || null;
  const sacrificePile = sacrificedCard
    ? $$("[data-field-pile]").find((element) => element.dataset.fieldPile === `${sacrificedCard.ownerId}:graveyard`)
    : null;
  const scorePile = details.effectResult?.kind === "score"
    ? $$("[data-field-pile]").find((element) => element.dataset.fieldPile === `${details.effectResult.playerId}:receptacle`)
    : null;
  const effectTarget = entry.type === "rules_choice_resolved"
    ? (details.kind === "chain_manifestation"
      ? (rulesVfxFindBattlefieldItem(details.itemId) || rulesVfxPlayerOrigin(details.playerId))
      : details.kind === "stack_counter_payment"
        ? rulesVfxCenter($$("#rulesStackList [data-stack-action-id]")
          .find((element) => element.dataset.stackActionId === details.targetActionId)) || rulesVfxStackTarget()
        : rulesVfxPlayerOrigin(details.playerId))
    : details.effectResult?.kind === "draw"
    ? rulesVfxPlayerOrigin(details.effectResult.playerId)
    : rulesVfxCenter(scorePile);
  const moveResult = details.effectResult?.kind === "move_card" ? details.effectResult : null;
  const moveSource = moveResult ? rulesVfxFindBattlefieldItem(moveResult.itemId) : null;
  const moveSourcePile = moveResult?.fromContainerId && moveResult?.fromZone
    ? $$('[data-field-pile]').find((element) => element.dataset.fieldPile === `${moveResult.fromContainerId}:${moveResult.fromZone}`)
    : null;
  const movePile = moveResult?.ownerId && moveResult?.toZone
    ? $$('[data-field-pile]').find((element) => element.dataset.fieldPile === `${moveResult.ownerId}:${moveResult.toZone}`)
    : null;
  const deckDiscardResult = details.effectResult?.kind === "discard_deck" ? details.effectResult : null;
  const deckDiscardSource = deckDiscardResult?.playerId
    ? $$('[data-field-pile]').find((element) => element.dataset.fieldPile === `${deckDiscardResult.playerId}:deck`)
    : null;
  const deckDiscardTarget = deckDiscardResult?.playerId
    ? $$('[data-field-pile]').find((element) => element.dataset.fieldPile === `${deckDiscardResult.playerId}:graveyard`)
    : null;
  const supportWinResult = (details.supportResolved || []).find((result) => (
    result.kind === "opponent_vessel_score" || result.kind === "opponent_vessel"
  )) || null;
  const supportWinSource = supportWinResult ? rulesVfxFindBattlefieldItem(supportWinResult.itemId) : null;
  const supportWinTarget = supportWinResult?.playerId
    ? $$('[data-field-pile]').find((element) => element.dataset.fieldPile === `${supportWinResult.playerId}:receptacle`)
    : null;
  return {
    entry,
    tributeOrigins,
    essenceOrigins,
    sourceRect: sourceElement?.getBoundingClientRect?.().toJSON?.() || (sourceElement ? sourceElement.getBoundingClientRect() : null),
    sacrifice: sacrificedCard ? {
      cardId: sacrificedCard.cardId,
      origin: rulesVfxCenter(sourceElement) || fallback,
      target: rulesVfxCenter(sacrificePile) || fallback,
    } : null,
    effectTarget,
    movedCard: moveResult ? {
      ...moveResult,
      origin: rulesVfxCenter(moveSource) || rulesVfxCenter(moveSourcePile) || fallback,
      target: rulesVfxCenter(movePile) || fallback,
    } : null,
    deckDiscard: deckDiscardResult ? {
      ...deckDiscardResult,
      origin: rulesVfxCenter(deckDiscardSource) || fallback,
      target: rulesVfxCenter(deckDiscardTarget) || fallback,
    } : null,
    supportWin: supportWinResult ? {
      ...supportWinResult,
      origin: rulesVfxCenter(supportWinSource) || fallback,
      target: rulesVfxCenter(supportWinTarget) || rulesVfxPlayerOrigin(supportWinResult.playerId),
    } : null,
  };
}

function prepareRulesVfxBatch(nextState) {
  const entries = [...(nextState?.recentLog || [])]
    .filter((entry) => Number.isFinite(Number(entry.sequence)))
    .sort((a, b) => Number(a.sequence) - Number(b.sequence));
  const newest = entries.length ? Number(entries[entries.length - 1].sequence) : 0;
  if (lastRulesVfxSequence === null || newest < lastRulesVfxSequence) {
    lastRulesVfxSequence = newest;
    return [];
  }
  const fresh = entries.filter((entry) => Number(entry.sequence) > lastRulesVfxSequence);
  lastRulesVfxSequence = Math.max(lastRulesVfxSequence, newest);
  return fresh
    .filter((entry) => ["rules_action_declared", "rules_action_triggered", "rules_action_resolved", "rules_choice_resolved", "rules_confrontation_cleanup"].includes(entry.type))
    .map(captureRulesVfxEvent);
}

function removeRulesVfx() {
  $$(".rules-vfx-flight, .rules-vfx-impact, .rules-vfx-exhaust-ring, .rules-vfx-exhaust-label")
    .forEach((element) => element.remove());
}

function rulesVfxAnimateAndRemove(element, keyframes, options) {
  const animation = element.animate(keyframes, { fill: "forwards", ...options });
  animation.finished.catch(() => {}).finally(() => element.remove());
}

function playRulesVfxFlight(kind, origin, target, options = {}) {
  const element = document.createElement("div");
  element.className = `rules-vfx-flight rules-vfx-${kind}`;
  element.setAttribute("aria-hidden", "true");
  if (["tribute", "sacrifice", "effect-card", "destroy-card", "discard-card"].includes(kind)) {
    element.innerHTML = `<img src="${esc(cardImage(options.cardId))}" alt="">`;
  } else {
    element.style.setProperty("--vfx-tone", temperamentInk(options.temperament));
    element.innerHTML = options.temperament
      ? `<img src="${esc(temperamentSymbol(options.temperament))}" alt="">`
      : "";
  }
  const isCard = ["tribute", "sacrifice", "effect-card", "destroy-card", "discard-card"].includes(kind);
  const size = isCard ? { width: 42, height: 59 } : { width: 28, height: 28 };
  element.style.left = `${origin.x - size.width / 2}px`;
  element.style.top = `${origin.y - size.height / 2}px`;
  document.body.appendChild(element);
  const dx = target.x - origin.x;
  const dy = target.y - origin.y;
  const tilt = isCard ? (options.index % 2 ? 8 : -8) : 0;
  rulesVfxAnimateAndRemove(element, [
    { transform: "translate3d(0,0,0) scale(1)", opacity: 1 },
    { offset: .72, transform: `translate3d(${dx * .84}px,${dy * .84}px,0) scale(.72) rotate(${tilt}deg)`, opacity: .96 },
    { transform: `translate3d(${dx}px,${dy}px,0) scale(.24) rotate(${tilt * 1.4}deg)`, opacity: 0 },
  ], { duration: 560, delay: options.index * 42, easing: "cubic-bezier(.16,1,.3,1)" });
}

function playRulesVfxImpact(target, label, tone = "cost") {
  const element = document.createElement("div");
  element.className = `rules-vfx-impact rules-vfx-impact-${tone}`;
  element.textContent = label;
  element.setAttribute("role", "status");
  element.style.left = `${target.x}px`;
  element.style.top = `${target.y}px`;
  document.body.appendChild(element);
  const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
  rulesVfxAnimateAndRemove(element, [
    { transform: "translate(-50%,-50%) scale(.9)", opacity: 0 },
    { offset: .24, transform: "translate(-50%,-50%) scale(1)", opacity: 1 },
    { transform: `translate(-50%,${reduced ? "-50%" : "-82%"}) scale(1)`, opacity: 0 },
  ], { duration: reduced ? 420 : 680, easing: "cubic-bezier(.16,1,.3,1)" });
}

function playRulesVfxExhaust(sourceRect) {
  if (!sourceRect?.width || !sourceRect?.height) return;
  const ring = document.createElement("div");
  ring.className = "rules-vfx-exhaust-ring";
  ring.setAttribute("aria-hidden", "true");
  Object.assign(ring.style, {
    left: `${sourceRect.left - 6}px`, top: `${sourceRect.top - 6}px`,
    width: `${sourceRect.width + 12}px`, height: `${sourceRect.height + 12}px`,
  });
  document.body.appendChild(ring);
  rulesVfxAnimateAndRemove(ring, [
    { transform: "scale(.92)", opacity: 0 },
    { offset: .28, transform: "scale(1)", opacity: 1 },
    { transform: "scale(1.035)", opacity: 0 },
  ], { duration: 650, easing: "cubic-bezier(.16,1,.3,1)" });

  const label = document.createElement("div");
  label.className = "rules-vfx-exhaust-label";
  label.textContent = t("rulesVfxExhausted");
  label.style.left = `${sourceRect.left + sourceRect.width / 2}px`;
  label.style.top = `${Math.max(16, sourceRect.top - 8)}px`;
  document.body.appendChild(label);
  rulesVfxAnimateAndRemove(label, [
    { transform: "translate(-50%,-80%)", opacity: 0 },
    { offset: .25, transform: "translate(-50%,-100%)", opacity: 1 },
    { transform: "translate(-50%,-130%)", opacity: 0 },
  ], { duration: 650, easing: "cubic-bezier(.16,1,.3,1)" });
}

function playRulesVfxBatch(batch) {
  if (!batch.length || $("#gameScreen").classList.contains("hidden")) return;
  for (const event of batch) {
    const { entry, tributeOrigins, essenceOrigins, sourceRect, sacrifice, effectTarget, movedCard, deckDiscard, supportWin } = event;
    const target = rulesVfxStackTarget();
    if (entry.type === "rules_confrontation_cleanup") {
      if (supportWin) {
        const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
        if (!reduced) playRulesVfxFlight("effect-card", supportWin.origin, supportWin.target, { cardId: supportWin.cardId, index: 0 });
        if (supportWin.kind === "opponent_vessel_score") {
          const delta = Number(supportWin.delta || 0);
          playRulesVfxImpact(supportWin.target, `${delta >= 0 ? "+" : ""}${delta}`, delta < 0 ? "score-loss" : "score");
        } else {
          playRulesVfxImpact(supportWin.target, t("rulesVfxOpponentVessel"), "resolved");
        }
      }
      continue;
    }
    if (entry.type === "rules_action_triggered") {
      playRulesVfxImpact(rulesVfxStackNoticeTarget(), t("rulesVfxTriggered"), "triggered");
      continue;
    }
    if (entry.type === "rules_action_resolved") {
      playRulesVfxImpact(target, t("rulesVfxResolved"), "resolved");
      if (entry.details?.effectResult?.kind === "neutralize_stack_action") {
        playRulesVfxImpact(
          target,
          t(entry.details.effectResult.status === "neutralized" ? "rulesVfxNeutralized" : "rulesVfxTargetGone"),
          entry.details.effectResult.status === "neutralized" ? "destroyed" : "target-gone",
        );
      }
      if (entry.details?.effectResult?.kind === "copy_stack_action" && entry.details.effectResult.status === "copied") {
        playRulesVfxImpact(target, t("rulesVfxCopied"), "triggered");
      }
      if (entry.details?.effectResult?.kind === "chain_manifestation" && entry.details.effectResult.status === "no_eligible_card") {
        playRulesVfxImpact(target, t("rulesVfxNoEligibleTarget"), "target-gone");
      }
      if (effectTarget && entry.details?.effectResult?.kind === "score") {
        const delta = Number(entry.details.effectResult.delta || 0);
        playRulesVfxImpact(
          effectTarget,
          `${delta >= 0 ? "+" : ""}${delta}`,
          delta < 0 ? "score-loss" : "score",
        );
      }
      if (effectTarget && entry.details?.effectResult?.kind === "draw") {
        playRulesVfxImpact(effectTarget, rulesText("rulesVfxDrawn", {
          count: Number(entry.details.effectResult.count || 0),
        }), "draw");
      }
      if (deckDiscard) {
        const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
        if (!reduced) {
          (deckDiscard.cardIds || []).slice(0, 3).forEach((cardId, index) => {
            playRulesVfxFlight("discard-card", deckDiscard.origin, deckDiscard.target, { cardId, index });
          });
        }
        playRulesVfxImpact(
          deckDiscard.count ? deckDiscard.target : target,
          deckDiscard.count
            ? rulesText("rulesVfxDeckDiscarded", { count: deckDiscard.count })
            : t("rulesVfxDeckEmpty"),
          "discarded",
        );
      }
      if (movedCard?.status === "moved") {
        const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
        if (!reduced) playRulesVfxFlight(movedCard.reason === "destroy" ? "destroy-card" : "effect-card", movedCard.origin, movedCard.target, { cardId: movedCard.cardId, index: 0 });
        const impactTarget = movedCard.reason === "destroy" ? movedCard.origin : movedCard.target;
        playRulesVfxImpact(
          impactTarget,
          movedCard.reason === "destroy"
            ? t("rulesVfxDestroyed")
            : movedCard.reason === "exile"
              ? t("rulesVfxExiled")
              : movedCard.toZone === "deck"
            ? t(movedCard.position === "bottom" ? "rulesVfxDeckBottom" : "rulesVfxDeckTop")
            : t(movedCard.toZone === "exile" ? "rulesVfxExiled" : "rulesVfxMoved"),
          movedCard.reason === "destroy" ? "destroyed" : "moved",
        );
      }
      if (movedCard?.status === "target_missing") {
        playRulesVfxImpact(target, t("rulesVfxTargetGone"), "target-gone");
      }
      if (movedCard?.status === "no_eligible_card") {
        playRulesVfxImpact(target, t("rulesVfxNoEligibleTarget"), "target-gone");
      }
      if (movedCard?.status === "removed_copy") {
        playRulesVfxImpact(movedCard.origin, t("rulesVfxCopyGone"), "target-gone");
      }
      continue;
    }
    if (entry.type === "rules_choice_resolved") {
      if (entry.details?.kind === "stack_copy_targets") {
        playRulesVfxImpact(target, t("rulesVfxCopied"), "triggered");
        continue;
      }
      if (entry.details?.kind === "stack_counter_payment") {
        if (entry.details.status === "paid") {
          const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
          let index = 0;
          if (!reduced) {
            for (const tribute of tributeOrigins.slice(0, 3)) {
              playRulesVfxFlight("tribute", tribute.origin, effectTarget || target, { cardId: tribute.cardId, index: index++ });
            }
            for (const essence of essenceOrigins) {
              const motes = Math.min(3, Math.max(1, Number(essence.amount || 1)));
              for (let mote = 0; mote < motes && index < 6; mote += 1) {
                playRulesVfxFlight("essence", essence.origin, effectTarget || target, { temperament: essence.temperament, index: index++ });
              }
            }
          }
          playRulesVfxImpact(effectTarget || target, t("rulesVfxStackPaymentPaid"), "cost");
        } else {
          playRulesVfxImpact(
            effectTarget || target,
            t(entry.details.status === "cancelled" ? "rulesVfxCancelled" : entry.details.status === "neutralized" ? "rulesVfxNeutralized" : "rulesVfxTargetGone"),
            entry.details.status === "target_missing" ? "target-gone" : "destroyed",
          );
        }
        continue;
      }
      if (entry.details?.kind === "chain_manifestation") {
        if (entry.details.status === "chained" && effectTarget) {
          const chainTarget = rulesVfxCenter(rulesVfxFindBattlefieldItem(entry.details.itemId)) || effectTarget;
          playRulesVfxImpact(chainTarget, t("rulesVfxChained"), "resolved");
        }
        continue;
      }
      if (effectTarget && entry.details?.kind === "recovery_shared_choice") {
        playRulesVfxImpact(
          effectTarget,
          entry.details.option === "lose_points_10"
            ? "−10"
            : rulesText("rulesVfxDeckDiscarded", { count: entry.details.count || 0 }),
          entry.details.option === "lose_points_10" ? "score-loss" : "discarded",
        );
        continue;
      }
      if (effectTarget) playRulesVfxImpact(effectTarget, t("rulesVfxDiscarded"), "discarded");
      if (effectTarget && Number(entry.details?.drawCount || 0) > 0) {
        playRulesVfxImpact(effectTarget, rulesText("rulesVfxDrawn", {
          count: Number(entry.details.drawCount),
        }), "draw");
      }
      continue;
    }
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
    let index = 0;
    if (!reduced) {
      for (const tribute of tributeOrigins.slice(0, 3)) {
        playRulesVfxFlight("tribute", tribute.origin, target, { cardId: tribute.cardId, index: index++ });
      }
      for (const essence of essenceOrigins) {
        const motes = Math.min(3, Math.max(1, Number(essence.amount || 1)));
        for (let mote = 0; mote < motes && index < 6; mote += 1) {
          playRulesVfxFlight("essence", essence.origin, target, { temperament: essence.temperament, index: index++ });
        }
      }
      if (sacrifice) playRulesVfxFlight("sacrifice", sacrifice.origin, sacrifice.target, { cardId: sacrifice.cardId, index: index++ });
    }
    if (sourceRect && entry.details?.cost?.sourceExhausted) playRulesVfxExhaust(sourceRect);
    if (sacrifice) playRulesVfxImpact(sacrifice.target, t("rulesVfxSacrificed"), "sacrificed");
    if (tributeOrigins.length || essenceOrigins.length || entry.details?.cost?.sourceExhausted || sacrifice) {
      playRulesVfxImpact(target, t("rulesVfxCostPaid"));
    }
  }
}

let pendingRulesActionSource = null;
let pendingRulesBoardFlow = null;
let rulesBoardTargetCleanup = [];
let rulesBoardPointerMove = null;

function closeRulesActionPanel() {
  pendingRulesActionSource = null;
  $("#rulesActionPanel").classList.add("hidden");
}

function rulesTargetPayload(target) {
  if (target.kind === "player") return { kind: "player", playerId: target.playerId };
  if (["stack_action", "stack_effect", "stack_item"].includes(target.kind)) {
    return { kind: target.kind, actionId: target.actionId, cardId: target.cardId };
  }
  if (target.kind === "zone_card") {
    return { kind: "zone_card", containerId: target.containerId, zone: target.zone, cardId: target.cardId };
  }
  return { kind: "card", itemId: target.id, cardId: target.cardId };
}

function rulesTargetElement(target) {
  if (target.kind === "card") {
    return $$(".bf-card[data-item-id]").find((element) => element.dataset.itemId === target.id) || null;
  }
  if (target.kind === "player") {
    return $$('[data-field-pile]').find((element) => element.dataset.fieldPile === `${target.playerId}:receptacle`) || null;
  }
  if (["stack_action", "stack_effect", "stack_item"].includes(target.kind)) {
    return $$("#rulesStackList [data-stack-action-id]")
      .find((element) => element.dataset.stackActionId === target.actionId) || null;
  }
  if (target.kind === "zone_card" && target.zone === "hand") {
    return $$("[data-hand-card]").find(
      (element) => element.dataset.handCard === target.cardId,
    ) || null;
  }
  return $$('[data-zone-card]').find((element) => {
    const value = element.dataset.zoneCard || "";
    return value === `${target.containerId}:${target.zone}:${target.cardId}`;
  }) || null;
}

function clearRulesBoardTargets() {
  rulesBoardTargetCleanup.forEach((cleanup) => cleanup());
  rulesBoardTargetCleanup = [];
  if (rulesBoardPointerMove) document.removeEventListener("pointermove", rulesBoardPointerMove);
  rulesBoardPointerMove = null;
  const path = $("#rulesTargetArrow .rules-target-arrow-line");
  if (path) path.setAttribute("d", "");
}

function closeRulesBoardFlow() {
  clearRulesBoardTargets();
  pendingRulesBoardFlow = null;
  $("#rulesBoardFlow")?.classList.add("hidden");
  $$('[data-hand-card]').forEach((element) => {
    element.classList.remove("is-tribute-candidate", "is-tribute-selected", "is-chain-candidate");
  });
  $$('[data-zone-card]').forEach((element) => element.classList.remove("is-chain-candidate"));
}

function cancelRulesBoardFlow() {
  const flow = pendingRulesBoardFlow;
  if (flow?.mode === "stack_payment") return;
  if (flow?.mode === "chain") {
    if (!flow.optional) return;
    send({ type: "resolve_rules_choice", choiceId: flow.choiceId, option: "decline" });
  }
  closeRulesBoardFlow();
}

function rulesChainChoice() {
  const choice = latestState?.rulesEngine?.pendingChoice;
  return choice?.kind === "chain_manifestation" && choice.playerId === myPlayerId && !isObserver
    ? choice
    : null;
}

function rulesChainCardEligible(cardId, choice = rulesChainChoice()) {
  return Boolean(
    choice
    && cardsById.get(cardId)?.type === "manifestation"
    && !rulesCardPlayRestrictedClient(cardId)
  );
}

function syncRulesChainBoardFlow() {
  const choice = rulesChainChoice();
  if (!choice) {
    if (pendingRulesBoardFlow?.mode === "chain") closeRulesBoardFlow();
    return;
  }
  if (
    choice.fromZone !== "hand"
    && Array.isArray(choice.cardIds)
  ) {
    if (pendingRulesBoardFlow?.mode === "chain") closeRulesBoardFlow();
    return;
  }
  if (pendingRulesBoardFlow?.mode === "chain" && pendingRulesBoardFlow.choiceId === choice.id) return;
  closeRulesBoardFlow();
  const source = { cardId: choice.sourceCardId, zone: "battlefield" };
  pendingRulesBoardFlow = {
    mode: "chain",
    choiceId: choice.id,
    fromZone: choice.fromZone,
    optional: Boolean(choice.optional),
    source,
    draft: {
      card: cardsById.get(choice.sourceCardId),
      encodedAbility: null,
      essencePlan: { spent: {}, remaining: {} },
      manifestations: [], structuredTargets: [], targetRules: null,
    },
    selectedPaymentIndexes: new Set(),
    stage: "choice",
  };
}

function rulesStackPaymentChoice() {
  const choice = latestState?.rulesEngine?.pendingChoice;
  return [
    "stack_counter_payment",
    "effect_memory_payment",
    "immediate_effect_payment",
    "effect_payment",
  ].includes(choice?.kind)
    && choice.playerId === myPlayerId && !isObserver
    ? choice
    : null;
}

function syncRulesStackPaymentBoardFlow() {
  const choice = rulesStackPaymentChoice();
  if (!choice) {
    if (pendingRulesBoardFlow?.mode === "stack_payment") closeRulesBoardFlow();
    return;
  }
  if (pendingRulesBoardFlow?.mode === "stack_payment" && pendingRulesBoardFlow.choiceId === choice.id) return;
  closeRulesBoardFlow();
  const source = { cardId: choice.targetCardId, zone: "stack" };
  const paymentDraft = rulesActionPaymentDraft(
    source,
    cardsById.get(choice.targetCardId),
    { tribute: choice.payment },
  );
  pendingRulesBoardFlow = {
    mode: "stack_payment",
    choiceId: choice.id,
    choice,
    source,
    draft: {
      card: cardsById.get(choice.targetCardId),
      encodedAbility: null,
      structuredTargets: [], targetRules: null,
      ...paymentDraft,
    },
    selectedPaymentIndexes: new Set(),
    stage: "payment",
  };
}

function rulesStackCopyChoice() {
  const choice = latestState?.rulesEngine?.pendingChoice;
  return choice?.kind === "stack_copy_targets" && choice.playerId === myPlayerId && !isObserver
    ? choice
    : null;
}

function rulesTriggerTargetChoice() {
  const choice = latestState?.rulesEngine?.pendingChoice;
  return choice?.kind === "trigger_targets"
    && choice.playerId === myPlayerId && !isObserver
    ? choice
    : null;
}

function syncRulesTriggerTargetBoardFlow() {
  const choice = rulesTriggerTargetChoice();
  if (!choice) {
    if (pendingRulesBoardFlow?.mode === "trigger_target") closeRulesBoardFlow();
    return;
  }
  if (
    pendingRulesBoardFlow?.mode === "trigger_target"
    && pendingRulesBoardFlow.choiceId === choice.id
  ) return;
  closeRulesBoardFlow();
  const encodedAbility = {
    targets: choice.targetRules || { min: 0, max: 0 },
  };
  pendingRulesBoardFlow = {
    mode: "trigger_target",
    choiceId: choice.id,
    choice,
    source: { cardId: choice.sourceCardId, zone: "battlefield" },
    draft: {
      card: cardsById.get(choice.sourceCardId),
      encodedAbility,
      ...rulesStructuredActionTargets(encodedAbility),
      essencePlan: { spent: {}, remaining: {} },
      manifestations: [],
    },
    selectedPaymentIndexes: new Set(),
    stage: "target",
  };
}

function syncRulesStackCopyBoardFlow() {
  const choice = rulesStackCopyChoice();
  if (!choice) {
    if (pendingRulesBoardFlow?.mode === "stack_copy_target") closeRulesBoardFlow();
    return;
  }
  if (pendingRulesBoardFlow?.mode === "stack_copy_target" && pendingRulesBoardFlow.choiceId === choice.id) return;
  closeRulesBoardFlow();
  const encodedAbility = { targets: choice.targetRules || { min: 0, max: 0 } };
  pendingRulesBoardFlow = {
    mode: "stack_copy_target",
    choiceId: choice.id,
    choice,
    source: { cardId: choice.targetCardId, zone: "stack" },
    draft: {
      card: cardsById.get(choice.targetCardId),
      encodedAbility,
      ...rulesStructuredActionTargets(encodedAbility),
      essencePlan: { spent: {}, remaining: {} },
      manifestations: [],
    },
    selectedPaymentIndexes: new Set(),
    stage: "target",
  };
}

function resolveRulesStackCopyTargets(option, target = null) {
  const flow = pendingRulesBoardFlow;
  if (flow?.mode !== "stack_copy_target" || flow.stage === "committing") return;
  flow.stage = "committing";
  renderRulesBoardFlow();
  send({
    type: "resolve_rules_choice",
    choiceId: flow.choiceId,
    option,
    targets: target ? [rulesTargetPayload(target)] : [],
  });
}

function resolveRulesStackPayment(option) {
  const flow = pendingRulesBoardFlow;
  if (flow?.mode !== "stack_payment" || flow.stage === "committing") return;
  const paymentCardIds = option === "pay" ? rulesBoardSelectedPayments(flow) : [];
  if (option === "pay") {
    const remaining = rulesRemainingAfterManifestations(
      paymentCardIds, flow.draft.essencePlan.remaining,
    );
    if (Object.values(remaining).some((amount) => amount > 0)) return;
  }
  flow.stage = "committing";
  renderRulesBoardFlow();
  send({
    type: "resolve_rules_choice",
    choiceId: flow.choiceId,
    option,
    cardIds: paymentCardIds,
  });
}

function rulesBoardSelectedPayments(flow = pendingRulesBoardFlow) {
  return [...(flow?.selectedPaymentIndexes || [])]
    .map((selectionKey) => flow?.draft?.manifestations?.find(
      (entry) => entry.selectionKey === selectionKey,
    )?.paymentValue)
    .filter(Boolean);
}

function rulesBoardMinimumPaymentCount(flow) {
  const candidates = flow.draft.manifestations;
  const remaining = flow.draft.essencePlan.remaining;
  if (Object.values(remaining).every((amount) => amount <= 0)) return 0;
  const capped = candidates.slice(0, 12);
  for (let count = 1; count <= capped.length; count += 1) {
    const limit = 1 << capped.length;
    for (let mask = 1; mask < limit; mask += 1) {
      let bits = 0;
      for (let value = mask; value; value &= value - 1) bits += 1;
      if (bits !== count) continue;
      const ids = capped.filter((_entry, index) => mask & (1 << index)).map((entry) => entry.paymentValue);
      if (rulesManifestationsCover(ids, remaining)) return count;
    }
  }
  return Infinity;
}

function updateRulesTargetArrow(event) {
  if (!pendingRulesBoardFlow || pendingRulesBoardFlow.stage !== "target") return;
  const cardRect = $("#rulesFloatingCard")?.getBoundingClientRect();
  const path = $("#rulesTargetArrow .rules-target-arrow-line");
  if (!cardRect || !path) return;
  const startX = cardRect.left + cardRect.width * .08;
  const startY = cardRect.top + cardRect.height * .46;
  const endX = event.clientX;
  const endY = event.clientY;
  const curveX = startX + (endX - startX) * .45;
  const curveY = Math.min(startY, endY) - Math.min(120, Math.abs(endX - startX) * .18 + 36);
  path.setAttribute("d", `M ${startX} ${startY} Q ${curveX} ${curveY} ${endX} ${endY}`);
}

function submitRulesBoardFlow(target = null) {
  const flow = pendingRulesBoardFlow;
  if (!flow) return;
  if (flow.mode === "stack_copy_target") {
    if (target) resolveRulesStackCopyTargets("retarget", target);
    return;
  }
  if (flow.mode === "trigger_target") {
    if (!target) return;
    flow.stage = "committing";
    renderRulesBoardFlow();
    send({
      type: "resolve_rules_choice",
      choiceId: flow.choiceId,
      targets: [rulesTargetPayload(target)],
    });
    return;
  }
  if (flow.mode === "placement") {
    if (!target) return;
    const targetPayload = rulesTargetPayload(target);
    sendCardPlacement(flow.placement, flow.source, [targetPayload]);
    closeRulesBoardFlow();
    return;
  }
  const activated = flow.actionKind === "activated_effect"
    || flow.source.actionKind === "activated_effect"
    || flow.source.zone === "battlefield";
  const selectedTargets = [...(flow.selectedTargets || [])];
  if (target) selectedTargets.push(target);
  const payload = {
    type: "declare_rules_action",
    label: rulesText(activated ? "rulesDefaultActivate" : "rulesDefaultPlay", { card: cardName(flow.source.cardId) }),
    kind: activated ? "activated_effect" : "play_card",
    source: {
      cardId: flow.source.cardId,
      zone: flow.source.zone,
      itemId: activated ? flow.source.itemId : null,
    },
    target: "",
    targets: selectedTargets.map(rulesTargetPayload),
    costNote: "",
    paymentCardIds: rulesBoardSelectedPayments(flow),
    extraEssenceCount: Number(flow.extraEssenceCount || 0),
  };
  if (flow.draft.encodedAbility?.id) payload.abilityId = flow.draft.encodedAbility.id;
  if (flow.source.placement) payload.placement = flow.source.placement;
  send(payload);
  closeRulesBoardFlow();
}

function scheduleRulesBoardSubmit() {
  const flow = pendingRulesBoardFlow;
  if (!flow) return;
  flow.stage = "committing";
  renderRulesBoardFlow();
  window.setTimeout(() => {
    if (pendingRulesBoardFlow === flow && flow.stage === "committing") submitRulesBoardFlow();
  }, 180);
}

function armRulesBoardTargets(flow) {
  clearRulesBoardTargets();
  const visibleTargets = [];
  const zoneTargetOffsets = new Map();
  const selectedKeys = new Set(
    (flow.selectedTargets || []).map((target) => target.key)
  );
  const targetGroupIndex = (flow.selectedTargets || []).length;
  flow.draft.structuredTargets
    .filter((target) => (
      !flow.draft.targetRules?.groups
      || target.targetGroupIndex === targetGroupIndex
    ))
    .filter((target) => !selectedKeys.has(target.key))
    .forEach((target) => {
    let element = rulesTargetElement(target);
    let temporaryTarget = false;
    if (!element && target.kind === "zone_card") {
      const pile = $$('[data-field-pile]').find((candidate) => candidate.dataset.fieldPile === `${target.containerId}:${target.zone}`);
      const pileRect = pile?.getBoundingClientRect();
      if (pileRect?.width) {
        const pileKey = `${target.containerId}:${target.zone}`;
        const offset = zoneTargetOffsets.get(pileKey) || 0;
        zoneTargetOffsets.set(pileKey, offset + 1);
        element = document.createElement("button");
        element.type = "button";
        element.className = "rules-zone-target-card";
        element.title = cardName(target.cardId);
        element.innerHTML = `<img src="${esc(cardImage(target.cardId))}" alt="${esc(cardName(target.cardId))}">`;
        element.style.left = `${Math.max(12, Math.min(window.innerWidth - 84, pileRect.left + offset * 24))}px`;
        element.style.top = `${Math.max(58, pileRect.top - 116 - offset * 5)}px`;
        document.body.appendChild(element);
        temporaryTarget = true;
      }
    }
    if (!element) return;
    visibleTargets.push(target);
    element.classList.add("rules-valid-target");
    const select = (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (flow.draft.targetRules?.groups) {
        flow.selectedTargets = [...(flow.selectedTargets || []), target];
        if (flow.selectedTargets.length < flow.draft.targetRules.groups.length) {
          renderRulesBoardFlow();
        } else {
          scheduleRulesBoardSubmit();
        }
      } else {
        submitRulesBoardFlow(target);
      }
    };
    element.addEventListener("pointerdown", select, true);
    rulesBoardTargetCleanup.push(() => {
      element.classList.remove("rules-valid-target");
      element.removeEventListener("pointerdown", select, true);
      if (temporaryTarget) element.remove();
    });
  });
  if (!visibleTargets.length) {
    $("#rulesFlowInstruction").textContent = t("rulesBoardNoVisibleTarget");
    return;
  }
  rulesBoardPointerMove = updateRulesTargetArrow;
  document.addEventListener("pointermove", rulesBoardPointerMove, { passive: true });
  const first = rulesTargetElement(visibleTargets[0]);
  const rect = first?.getBoundingClientRect();
  if (rect) updateRulesTargetArrow({ clientX: rect.left + rect.width / 2, clientY: rect.top + rect.height / 2 });
}

function advanceRulesBoardFlow() {
  const flow = pendingRulesBoardFlow;
  if (!flow) return;
  if (
    flow.draft.optionalExtraEssenceMax > 0
    && !flow.extraEssenceConfirmed
  ) {
    flow.stage = "extra_essence";
    renderRulesBoardFlow();
    return;
  }
  const needsTarget = Number(flow.draft.targetRules?.min || 0) > 0;
  if (needsTarget) {
    flow.stage = "target";
    renderRulesBoardFlow();
    return;
  }
  scheduleRulesBoardSubmit();
}

function toggleRulesBoardPayment(index) {
  const flow = pendingRulesBoardFlow;
  if (!flow || flow.stage !== "payment") return false;
  const candidate = flow.draft.manifestations.find(
    (entry) => entry.selectionKey === index,
  );
  if (!candidate) return false;
  if (flow.selectedPaymentIndexes.has(index)) flow.selectedPaymentIndexes.delete(index);
  else flow.selectedPaymentIndexes.add(index);
  const selected = rulesBoardSelectedPayments(flow);
  const covered = rulesManifestationsCover(selected, flow.draft.essencePlan.remaining);
  renderRulesBoardFlow();
  if (!covered) return true;
  if (flow.mode === "stack_payment") return true;
  const minimum = rulesBoardMinimumPaymentCount(flow);
  if (selected.length > minimum) {
    showToast(t("rulesTributeRedundantError"), true);
    return true;
  }
  advanceRulesBoardFlow();
  return true;
}

function renderRulesBoardFlow() {
  syncRulesStackCopyBoardFlow();
  syncRulesStackPaymentBoardFlow();
  syncRulesChainBoardFlow();
  syncRulesTriggerTargetBoardFlow();
  const flow = pendingRulesBoardFlow;
  const panel = $("#rulesBoardFlow");
  if (!flow || !panel) {
    panel?.classList.add("hidden");
    return;
  }
  const handSourceStillValid = flow.source.zone === "hand"
    && (latestState?.players?.[myPlayerId]?.zones?.hand?.cards || []).includes(flow.source.cardId);
  const battlefieldSource = flow.source.zone === "battlefield"
    ? latestState?.battlefield?.find((item) => item.id === flow.source.itemId)
    : null;
  const battlefieldSourceStillValid = Boolean(
    battlefieldSource
    && battlefieldItemControllerId(battlefieldSource) === myPlayerId
    && battlefieldSource.cardId === flow.source.cardId
    && battlefieldSource.faceUp
  );
  if (flow.mode === "action" && (
    latestState?.rulesEngine?.priorityPlayerId !== myPlayerId
    || (!handSourceStillValid && !battlefieldSourceStillValid)
  )) {
    closeRulesBoardFlow();
    return;
  }
  panel.classList.remove("hidden");
  const stackDecision = ["stack_payment", "stack_copy_target"].includes(flow.mode);
  panel.classList.toggle("is-stack-payment", stackDecision);
  $("#rulesFloatingCardImg").src = cardImage(flow.source.cardId);
  $("#rulesFloatingCardImg").alt = cardName(flow.source.cardId);
  $("#rulesFloatingCardName").textContent = cardName(flow.source.cardId);
  $("#rulesFlowCancelBtn").classList.toggle(
    "hidden",
    stackDecision
    || flow.mode === "trigger_target"
    || (flow.mode === "chain" && !flow.optional),
  );
  $("#rulesFlowCancelBtn").title = t(flow.mode === "chain" ? "rulesChainDecline" : "cancel");
  $("#rulesFlowCancelBtn").setAttribute("aria-label", $("#rulesFlowCancelBtn").title);
  $("#rulesFlowChoiceActions").classList.toggle("hidden", !stackDecision);
  $("#rulesFlowPayBtn").classList.toggle("hidden", flow.mode === "stack_copy_target");

  const essence = flow.draft.essencePlan.spent;
  const essenceItems = Object.entries(essence).filter(([, amount]) => amount > 0);
  $("#rulesBoardEssence").classList.toggle("hidden", !essenceItems.length || flow.stage !== "payment");
  $("#rulesBoardEssence").innerHTML = essenceItems.map(([temperament, amount]) => `
    <span><img src="${esc(temperamentSymbol(temperament))}" alt="">${esc(t("essence"))} ×${amount}</span>`).join("");

  $$('[data-hand-card]').forEach((element) => {
    const index = Number(element.dataset.handIndex);
    const candidate = flow.stage === "payment" && flow.draft.manifestations.some(
      (entry) => entry.selectionKey === index,
    );
    element.classList.toggle("is-tribute-candidate", candidate);
    element.classList.toggle("is-tribute-selected", candidate && flow.selectedPaymentIndexes.has(index));
    const chainCandidate = flow.mode === "chain"
      && flow.fromZone === "hand"
      && rulesChainCardEligible(element.dataset.handCard);
    element.classList.toggle("is-chain-candidate", chainCandidate);
  });
  $$(".bf-card[data-item-id]").forEach((element) => {
    const selectionKey = `battlefield:${element.dataset.itemId}`;
    const candidate = flow.stage === "payment"
      && flow.draft.manifestations.some(
        (entry) => entry.selectionKey === selectionKey,
      );
    element.classList.toggle("is-tribute-candidate", candidate);
    element.classList.toggle(
      "is-tribute-selected",
      candidate && flow.selectedPaymentIndexes.has(selectionKey),
    );
  });

  if (flow.mode === "chain") {
    $$('[data-zone-card]').forEach((element) => {
      const [containerId, zone, cardId] = String(element.dataset.zoneCard || "").split(":");
      element.classList.toggle("is-chain-candidate", (
        containerId === myPlayerId
        && zone === flow.fromZone
        && rulesChainCardEligible(cardId)
      ));
    });
    $("#rulesBoardEssence").classList.add("hidden");
    $("#rulesFlowInstruction").textContent = rulesText("rulesChainChooseInstruction", {
      zone: t(flow.fromZone),
    });
    $("#rulesFlowCost").innerHTML = `<div class="rules-flow-cost-row"><span>${esc(t("rulesChainResultLabel"))}</span><strong>${esc(t("rulesChainResult"))}</strong></div>`;
    clearRulesBoardTargets();
    return;
  }

  if (flow.mode === "stack_copy_target") {
    const declineButton = $("#rulesFlowDeclineBtn");
    declineButton.textContent = t("rulesKeepCopiedTargets");
    declineButton.disabled = flow.stage === "committing";
    $("#rulesFlowInstruction").textContent = rulesText("rulesCopyChooseTargetInstruction", {
      card: cardName(flow.choice.targetCardId),
    });
    const original = (flow.choice.originalTargets || []).map(rulesActionTargetRef).join(", ");
    $("#rulesFlowCost").innerHTML = `<div class="rules-flow-cost-row"><span>${esc(t("rulesCurrentTarget"))}</span><strong>${original || esc(t("rulesNoTargetRequired"))}</strong></div>`;
    if (flow.stage === "committing") clearRulesBoardTargets();
    else armRulesBoardTargets(flow);
    return;
  }
  if (flow.mode === "trigger_target") {
    $("#rulesFlowInstruction").textContent = rulesText(
      "rulesTriggerChooseTargetInstruction",
      { card: cardName(flow.choice.sourceCardId) },
    );
    $("#rulesFlowCost").innerHTML = "";
    if (flow.stage === "committing") clearRulesBoardTargets();
    else armRulesBoardTargets(flow);
    return;
  }

  if (flow.mode === "stack_payment") {
    const selected = rulesBoardSelectedPayments(flow);
    const remaining = rulesRemainingAfterManifestations(selected, flow.draft.essencePlan.remaining);
    const covered = Object.values(remaining).every((amount) => amount <= 0);
    const canPay = Number.isFinite(rulesBoardMinimumPaymentCount(flow));
    const payButton = $("#rulesFlowPayBtn");
    const declineButton = $("#rulesFlowDeclineBtn");
    $("#rulesFlowInstruction").textContent = rulesText(
      flow.choice.kind === "effect_memory_payment"
        ? "rulesMemoryPaymentInstruction"
        : flow.choice.kind === "immediate_effect_payment"
          ? "rulesImmediatePaymentInstruction"
        : flow.choice.kind === "effect_payment"
          ? "rulesEffectPaymentInstruction"
        : "rulesStackPaymentInstruction", {
      source: cardName(flow.choice.sourceCardId),
      target: cardName(flow.choice.targetCardId),
    });
    $("#rulesFlowCost").innerHTML = `
      <div class="rules-flow-cost-row"><span>${esc(t("rulesEssenceUsed"))}</span>${rulesTributeUnitsHtml(essence, t("rulesNoEssenceUsed"))}</div>
      <div class="rules-flow-cost-row"><span>${esc(t("rulesTributeRemaining"))}</span>${rulesTributeUnitsHtml(remaining, t("rulesCoveredByEssence"))}</div>`;
    declineButton.textContent = t(
      flow.choice.kind === "effect_memory_payment"
        ? "rulesDeclineMemoryPayment"
        : flow.choice.kind === "immediate_effect_payment"
          ? "rulesDeclineImmediatePayment"
        : flow.choice.kind === "effect_payment"
          ? "rulesDeclineEffectPayment"
        : flow.choice.mode === "cancel"
          ? "rulesLetEffectCancel"
          : "rulesLetCardNeutralize"
    );
    payButton.textContent = t(
      covered
        ? flow.choice.kind === "effect_memory_payment"
          ? "rulesPayAndPreventReturn"
          : flow.choice.kind === "immediate_effect_payment"
            ? "rulesPayAndContinueConfrontation"
          : flow.choice.kind === "effect_payment"
            ? "rulesPayAndPreventEffect"
          : "rulesPayAndKeepStack"
        : canPay ? "rulesSelectPayment" : "rulesCannotPay"
    );
    payButton.disabled = !covered || flow.stage === "committing";
    declineButton.disabled = flow.stage === "committing";
    clearRulesBoardTargets();
    return;
  }

  if (flow.stage === "payment") {
    const selected = rulesBoardSelectedPayments(flow);
    const remaining = rulesRemainingAfterManifestations(selected, flow.draft.essencePlan.remaining);
    $("#rulesFlowInstruction").textContent = t("rulesBoardPayInstruction");
    const sourceCost = flow.draft.encodedAbility?.exhaustSource
      ? `<div class="rules-flow-cost-row"><span>${esc(t("rulesCostShort"))}</span><strong>${esc(t("rulesExhaustSourceCost"))}</strong></div>`
      : flow.draft.encodedAbility?.sacrificeSource
        ? `<div class="rules-flow-cost-row"><span>${esc(t("rulesCostShort"))}</span><strong>${esc(t("rulesSacrificeSourceCost"))}</strong></div>`
        : "";
    $("#rulesFlowCost").innerHTML = `${sourceCost}
      <div class="rules-flow-cost-row"><span>${esc(t("rulesEssenceUsed"))}</span>${rulesTributeUnitsHtml(essence, t("rulesNoEssenceUsed"))}</div>
      <div class="rules-flow-cost-row"><span>${esc(t("rulesTributeRemaining"))}</span>${rulesTributeUnitsHtml(remaining, t("rulesCoveredByEssence"))}</div>`;
    clearRulesBoardTargets();
    return;
  }

  if (flow.stage === "extra_essence") {
    const max = Number(flow.draft.optionalExtraEssenceMax || 0);
    const current = Math.max(
      0, Math.min(Number(flow.extraEssenceCount || 0), max),
    );
    $("#rulesBoardEssence").classList.add("hidden");
    $("#rulesFlowInstruction").textContent = rulesText(
      "rulesOptionalExtraEssenceInstruction",
      { max },
    );
    $("#rulesFlowCost").innerHTML = `
      <div class="rules-flow-cost-row rules-extra-essence-row">
        <span>${esc(t("rulesOptionalExtraEssence"))}</span>
        <div class="number-stepper">
          <button type="button" id="rulesExtraEssenceMinus" aria-label="${esc(t("decrease"))}">−</button>
          <input id="rulesExtraEssenceCount" type="number" min="0" max="${max}" value="${current}">
          <button type="button" id="rulesExtraEssencePlus" aria-label="${esc(t("increase"))}">+</button>
        </div>
      </div>
      <button type="button" class="primary rules-extra-essence-confirm" id="rulesExtraEssenceConfirm">
        ${esc(t("confirm"))}
      </button>`;
    const input = $("#rulesExtraEssenceCount");
    const setCount = (value) => {
      flow.extraEssenceCount = Math.max(
        0, Math.min(Number(value || 0), max),
      );
      input.value = flow.extraEssenceCount;
    };
    $("#rulesExtraEssenceMinus").onclick = () => {
      setCount(Number(input.value) - 1);
    };
    $("#rulesExtraEssencePlus").onclick = () => {
      setCount(Number(input.value) + 1);
    };
    input.onchange = () => setCount(input.value);
    $("#rulesExtraEssenceConfirm").onclick = () => {
      setCount(input.value);
      flow.extraEssenceConfirmed = true;
      advanceRulesBoardFlow();
    };
    clearRulesBoardTargets();
    return;
  }

  if (flow.stage === "committing") {
    $("#rulesFlowInstruction").textContent = t("rulesBoardToStack");
    $("#rulesFlowCost").innerHTML = flow.draft.encodedAbility?.exhaustSource
      ? `<div class="rules-flow-cost-row"><span>${esc(t("rulesCostShort"))}</span><strong>${esc(t("rulesExhaustSourceCost"))}</strong></div>`
      : flow.draft.encodedAbility?.sacrificeSource
        ? `<div class="rules-flow-cost-row"><span>${esc(t("rulesCostShort"))}</span><strong>${esc(t("rulesSacrificeSourceCost"))}</strong></div>`
        : "";
    clearRulesBoardTargets();
    return;
  }

  const effect = cardField(flow.draft.card, "effect") || t("rulesNoPrintedEffect");
  $("#rulesFlowInstruction").textContent = `${t("rulesBoardChooseTarget")} — ${effect}`;
  const sourceCost = flow.draft.encodedAbility?.exhaustSource
    ? `<div class="rules-flow-cost-row"><span>${esc(t("rulesCostShort"))}</span><strong>${esc(t("rulesExhaustSourceCost"))}</strong></div>`
    : flow.draft.encodedAbility?.sacrificeSource
      ? `<div class="rules-flow-cost-row"><span>${esc(t("rulesCostShort"))}</span><strong>${esc(t("rulesSacrificeSourceCost"))}</strong></div>`
      : "";
  $("#rulesFlowCost").innerHTML = `${sourceCost}<div class="rules-flow-cost-row"><span>${esc(t("rulesTargetLegend"))}</span><strong>${esc(t("rulesBoardClickTarget"))}</strong></div>`;
  armRulesBoardTargets(flow);
}

function rulesDraftCanBePaid(draft) {
  if (!draft) return false;
  if (draft.essenceCostPayable === false) return false;
  if (Object.values(draft.essencePlan.remaining).every((amount) => amount <= 0)) return true;
  const candidates = draft.manifestations.slice(0, 12);
  const combinations = 1 << candidates.length;
  for (let mask = 1; mask < combinations; mask += 1) {
    const selected = candidates
      .filter((_candidate, index) => mask & (1 << index))
      .map((candidate) => candidate.paymentValue);
    if (rulesManifestationsCover(selected, draft.essencePlan.remaining)) return true;
  }
  return false;
}

function rulesCopiedEffectsCardId(item) {
  const effect = (latestState?.rulesEngine?.ongoingEffects || [])
    .find((entry) => (
      entry.kind === "copy_power_effects"
      && entry.source?.itemId === item?.id
      && entry.target?.cardId
    ));
  return effect?.target?.cardId || null;
}

function rulesActivatedAbilitiesForItem(item) {
  const copiedCardId = rulesCopiedEffectsCardId(item);
  return activatedAbilitiesByCard.get(copiedCardId || item?.cardId) || [];
}

function rulesActivatedActionDraft(item, abilityOverride = null) {
  const abilities = rulesActivatedAbilitiesForItem(item);
  const ability = abilityOverride
    || abilities[0]
    || null;
  if (
    isObserver
    || !item?.faceUp
    || (
      battlefieldItemControllerId(item) !== myPlayerId
      && !ability?.anyPlayer
    )
    || !latestState?.rulesEngine?.enabled
    || latestState.rulesEngine.pendingChoice
    || latestState.rulesEngine.priorityPlayerId !== myPlayerId
    || rules_pregame_active_client()
    || rules_recovery_mulligan_active_client()
    || !["confrontation_reaction", "resolution_effects", "end_actions"].includes(currentPhaseUi().phase?.id)
  ) return null;
  if (!abilities.length) return null;
  if (
    Array.isArray(ability.phaseIds)
    && ability.phaseIds.length
    && !ability.phaseIds.includes(currentPhaseUi().phase?.id)
  ) return null;
  const source = { cardId: item.cardId, zone: "battlefield", itemId: item.id };
  const draft = buildRulesActionDraft(source, ability);
  if (!draft.encodedAbility) return null;
  if (draft.encodedAbility.sourceFieldZone && item.fieldZone !== draft.encodedAbility.sourceFieldZone) return null;
  if (
    Array.isArray(draft.encodedAbility.sourceZones)
    && draft.encodedAbility.sourceZones.length
    && !draft.encodedAbility.sourceZones.includes("battlefield")
  ) return null;
  if (draft.encodedAbility.exhaustSource && Math.round(Number(item.rotation || 0)) % 180 !== 0) return null;
  const counterCost = draft.encodedAbility.removeCountersFromSource;
  if (counterCost?.name) {
    const wanted = String(counterCost.name).toLocaleLowerCase();
    const held = Object.entries(item.counters || {})
      .filter(([name]) => name.toLocaleLowerCase() === wanted)
      .reduce((total, [, amount]) => total + Number(amount || 0), 0);
    if (held < Number(counterCost.amount || 0)) return null;
  }
  if (!rulesDraftCanBePaid(draft)) return null;
  if (Number(draft.targetRules?.min || 0) > draft.structuredTargets.length) return null;
  return { source, draft };
}

function beginRulesBoardAction(source) {
  const draft = buildRulesActionDraft(source);
  if (!draft.card || !["ephemeral_will", "persistent_will"].includes(draft.card.type)) return false;
  if (!handCardIsPlayable(source.cardId)) {
    showToast(t("rulesBoardCardNotPlayable"), true);
    return true;
  }
  closeRulesActionPanel();
  pendingRulesBoardFlow = {
    mode: "action",
    source,
    draft,
    selectedPaymentIndexes: new Set(),
    extraEssenceCount: 0,
    extraEssenceConfirmed: false,
    stage: rulesInitialActionStage(draft),
  };
  renderRulesBoardFlow();
  if (pendingRulesBoardFlow && pendingRulesBoardFlow.stage === "target" && Number(draft.targetRules?.min || 0) === 0) {
    scheduleRulesBoardSubmit();
  }
  return true;
}

function beginRulesHandActivatedAction(cardId, handIndex) {
  const source = {
    cardId,
    zone: "hand",
    handIndex,
    actionKind: "activated_effect",
  };
  const draft = buildRulesActionDraft(source);
  if (!draft.encodedAbility || !rulesDraftCanBePaid(draft)) {
    showToast(t("rulesBoardEffectNotAvailable"), true);
    return false;
  }
  closeRulesActionPanel();
  pendingRulesBoardFlow = {
    mode: "action",
    actionKind: "activated_effect",
    source,
    draft,
    selectedPaymentIndexes: new Set(),
    extraEssenceCount: 0,
    extraEssenceConfirmed: false,
    stage: rulesInitialActionStage(draft),
  };
  renderRulesBoardFlow();
  if (
    pendingRulesBoardFlow
    && pendingRulesBoardFlow.stage === "target"
    && Number(draft.targetRules?.min || 0) === 0
  ) scheduleRulesBoardSubmit();
  return true;
}

function beginRulesBoardActivatedAction(item, abilityId = null) {
  const ability = abilityId
    ? rulesActivatedAbilitiesForItem(item).find(
        (candidate) => candidate.id === abilityId,
      )
    : null;
  const available = rulesActivatedActionDraft(item, ability);
  if (!available) {
    showToast(t("rulesBoardEffectNotAvailable"), true);
    return false;
  }
  closeRulesActionPanel();
  pendingRulesBoardFlow = {
    mode: "action",
    source: available.source,
    draft: available.draft,
    selectedPaymentIndexes: new Set(),
    extraEssenceCount: 0,
    extraEssenceConfirmed: false,
    stage: rulesInitialActionStage(available.draft),
  };
  renderRulesBoardFlow();
  if (pendingRulesBoardFlow && pendingRulesBoardFlow.stage === "target" && Number(available.draft.targetRules?.min || 0) === 0) {
    scheduleRulesBoardSubmit();
  }
  return true;
}

function beginRulesBoardPlacementTarget(payload, source) {
  const ability = placementTargetTrigger(payload, source);
  if (!ability || ability.targets?.kind === "player") return false;
  const draft = buildRulesActionDraft(source, ability);
  if (ability.targets?.excludeEventSource && source?.itemId) {
    draft.structuredTargets = draft.structuredTargets.filter((target) => target.id !== source.itemId);
  }
  pendingRulesBoardFlow = {
    mode: "placement",
    source,
    placement: payload,
    draft,
    selectedPaymentIndexes: new Set(),
    stage: "target",
  };
  renderRulesBoardFlow();
  return true;
}

function rulesActionKindOptions(zone) {
  return zone === "hand"
    ? [["play_card", "rulesKindPlayCard"]]
    : [["activated_effect", "rulesKindActivated"], ["triggered_effect", "rulesKindTriggered"]];
}

function rulesStructuredActionTargets(encodedAbility) {
  if (Array.isArray(encodedAbility?.targetGroups)) {
    const groups = encodedAbility.targetGroups;
    const structuredTargets = groups.flatMap((group, targetGroupIndex) => (
      rulesStructuredActionTargets({ targets: group }).structuredTargets
        .map((target) => ({ ...target, targetGroupIndex }))
    ));
    return {
      targetRules: { groups, min: groups.length, max: groups.length },
      noTargetRequired: groups.length === 0,
      structuredTargetKind: "grouped",
      allowedTargetZones: ["battlefield"],
      structuredTargets,
    };
  }
  const targetRules = encodedAbility?.targets || null;
  const noTargetRequired = Boolean(targetRules && Number(targetRules.max) === 0);
  const structuredTargetKind = targetRules?.kind || "card";
  const allowsFieldCard = ["card", "card_or_stack_action"].includes(structuredTargetKind);
  const allowsStackCard = ["stack_action", "card_or_stack_action", "stack_item"].includes(structuredTargetKind);
  const allowedTargetZones = targetRules?.zones || ["battlefield"];
  const allowedTargetTypes = targetRules?.cardTypes || (targetRules?.cardType ? [targetRules.cardType] : []);
  const maxTargetPoints = Number(targetRules?.maxPoints);
  const maxTargetPower = Number(targetRules?.maxPower);
  const minTargetPower = Number(targetRules?.minPower);
  const targetMatchesRules = (cardId) => {
    const targetCard = cardsById.get(cardId);
    if (allowedTargetTypes.length && !allowedTargetTypes.includes(targetCard?.type)) return false;
    return !Number.isFinite(maxTargetPoints) || (Number.isFinite(Number(targetCard?.points)) && Number(targetCard.points) <= maxTargetPoints);
  };
  const fieldTargets = (latestState?.battlefield || [])
    .filter(() => !noTargetRequired && allowsFieldCard && allowedTargetZones.includes("battlefield"))
    .filter((item) => item.faceUp && item.cardId)
    .filter((item) => targetMatchesRules(item.cardId))
    .filter((item) => {
      const controller = item.controllerId || item.ownerId;
      if (targetRules?.controller === "self" && controller !== myPlayerId) return false;
      if (targetRules?.controller === "opponent" && controller === myPlayerId) return false;
      if (targetRules?.owner === "self" && item.ownerId !== myPlayerId) return false;
      if (targetRules?.owner === "opponent" && item.ownerId === myPlayerId) return false;
      if (targetRules?.fieldZone && item.fieldZone !== targetRules.fieldZone) return false;
      if (
        targetRules?.firstManifestationOnly
        && !Object.values(
          latestState?.rulesEngine?.firstManifestationItemIds || {},
        ).includes(item.id)
      ) return false;
      const zonesForType = targetRules?.fieldZonesByType?.[cardsById.get(item.cardId)?.type];
      if (Array.isArray(zonesForType) && !zonesForType.includes(item.fieldZone)) return false;
      if (targetRules?.supportOnly && !item.isSupport) return false;
      if (targetRules?.counter) {
        const key = Object.keys(item.counters || {}).find(
          (name) => name.toLocaleLowerCase()
            === targetRules.counter.toLocaleLowerCase(),
        ) || targetRules.counter;
        if (Number(item.counters?.[key] || 0) < Number(targetRules.minCounters || 0)) return false;
      }
      const power = Number(item.effectivePower ?? cardsById.get(item.cardId)?.power);
      return (
        (!Number.isFinite(maxTargetPower) || (Number.isFinite(power) && power <= maxTargetPower))
        && (!Number.isFinite(minTargetPower) || (Number.isFinite(power) && power >= minTargetPower))
      );
    })
    .map((item) => ({ ...item, kind: "card", zone: "battlefield", key: item.id }));
  const publicZoneTargets = Object.entries(latestState?.players || {}).flatMap(([containerId, player]) => (
    (allowsFieldCard ? allowedTargetZones : [])
      .filter((zone) => zone !== "battlefield")
      .flatMap((zone) => (player.zones?.[zone]?.cards || []).map((cardId, index) => ({
        kind: "zone_card", zone, containerId, cardId,
        ownerId: player.zones?.[zone]?.owners?.[cardId] || containerId,
        key: `zone:${containerId}:${zone}:${cardId}:${index}`,
      })))
  )).filter((item) => targetMatchesRules(item.cardId))
    .filter((item) => (
      targetRules?.owner === "self"
        ? item.ownerId === myPlayerId
        : targetRules?.owner === "opponent"
          ? item.ownerId !== myPlayerId
          : true
    ))
    .filter((item) => (
      targetRules?.container === "opponent"
        ? item.containerId !== myPlayerId
        : true
    ))
    .filter((item) => (
      !targetRules?.enteredThisTurn
      || Number(latestState?.rulesEngine?.zoneEntryTurns?.[
        `${item.containerId}:${item.zone}:${item.cardId}`
      ]) === Number(latestState?.phaseTracker?.turn)
    )).filter((item) => (
      !Array.isArray(targetRules?.limboReasons)
      || targetRules.limboReasons.length === 0
      || (latestState?.rulesEngine?.recentLimboEntries || []).some((entry) => (
        entry.ownerId === item.ownerId
        && entry.cardId === item.cardId
        && targetRules.limboReasons.includes(entry.reason)
      ))
    ));
  const playerTargets = structuredTargetKind === "player" && !noTargetRequired
    ? Object.keys(latestState?.players || {})
      .filter((playerId) => (
        targetRules?.controller === "self"
          ? playerId === myPlayerId
          : targetRules?.controller === "opponent"
            ? playerId !== myPlayerId
            : true
      ))
      .map((playerId) => ({
        kind: "player", playerId, key: `player:${playerId}`,
      }))
    : [];
  const stackTargets = (allowsStackCard || structuredTargetKind === "stack_effect") && !noTargetRequired
    ? (latestState?.rulesEngine?.actionStack || [])
      .filter((action) => (
        structuredTargetKind === "stack_item"
          ? ["play_card", "activated_effect", "triggered_effect"].includes(action.kind)
          : allowsStackCard
          ? action.kind === "play_card" && action.sourceOnStack && action.source?.cardId
          : ["activated_effect", "triggered_effect"].includes(action.kind) && action.source?.cardId
      ))
      .filter((action) => targetMatchesRules(action.source.cardId))
      .filter((action) => {
        if (targetRules?.controller === "self") return action.controllerId === myPlayerId;
        if (targetRules?.controller === "opponent") return action.controllerId !== myPlayerId;
        return true;
      })
      .filter((action) => !(latestState?.rulesEngine?.ongoingEffects || []).some(
        (effect) => (
          effect.kind === "protection"
          && effect.target?.actionId === action.id
        ),
      ))
      .map((action) => ({
        kind: structuredTargetKind === "stack_item"
          ? "stack_item"
          : allowsStackCard ? "stack_action" : structuredTargetKind,
        actionId: action.id, cardId: action.source.cardId,
        controllerId: action.controllerId, key: `stack:${action.id}`,
      }))
    : [];
  return {
    targetRules,
    noTargetRequired,
    structuredTargetKind,
    allowedTargetZones,
    structuredTargets: [...fieldTargets, ...publicZoneTargets, ...playerTargets, ...stackTargets],
  };
}

function rulesActionPaymentDraft(source, card, encodedAbility) {
  const isPrintedWill = ["hand", "suspended"].includes(source.zone)
    && ["ephemeral_will", "persistent_will"].includes(card?.type);
  const paymentRequirements = encodedAbility && Object.hasOwn(encodedAbility, "tribute")
    ? printedTributeRequirements({ powerCost: encodedAbility.tribute })
    : isPrintedWill ? printedTributeRequirements(card) : {};
  let reduction = (latestState?.battlefield || []).reduce((total, item) => {
    if ((item.controllerId || item.ownerId) !== myPlayerId || item.fieldZone !== "interzone") return total;
    return total + (passiveEffectsByCard.get(item.cardId) || [])
      .filter((effect) => effect.kind === "reduce_will_tribute")
      .reduce((sum, effect) => sum + Number(effect.value || 0), 0);
  }, 0);
  if (encodedAbility?.costReduction?.kind === "half_first_base_power") {
    const firstId = latestState?.rulesEngine?.firstManifestationItemIds?.[myPlayerId];
    const first = latestState?.battlefield?.find((item) => item.id === firstId);
    reduction += Math.floor(Number(cardsById.get(first?.cardId)?.power || 0) / 2);
  }
  while (reduction > 0) {
    const payable = Object.keys(paymentRequirements)
      .sort((a, b) => Number(paymentRequirements[b]) - Number(paymentRequirements[a]))[0];
    if (!payable || Number(paymentRequirements[payable]) <= 0) break;
    paymentRequirements[payable] -= 1;
    reduction -= 1;
  }
  if (source.zone === "suspended") {
    const total = Object.values(paymentRequirements)
      .reduce((sum, amount) => sum + Number(amount || 0), 0);
    Object.keys(paymentRequirements).forEach((key) => { delete paymentRequirements[key]; });
    if (total > 0) paymentRequirements.hollow = total;
  }
  const hasPrintedTribute = Object.values(paymentRequirements).some((amount) => amount > 0);
  const essencePlan = rulesEssencePaymentPreview(paymentRequirements);
  const essenceCostRequirements = encodedAbility?.essenceCost
    ? printedTributeRequirements({ powerCost: encodedAbility.essenceCost })
    : {};
  const essenceCostPlan = rulesEssencePaymentPreview(essenceCostRequirements);
  const essenceCostPayable = Object.values(essenceCostPlan.remaining)
    .every((amount) => amount <= 0);
  const totalEssence = (latestState?.tokens || [])
    .filter((token) => (
      token.ownerId === myPlayerId
      && token.isEssence
      && !token.isNeutralCounter
    ))
    .reduce(
      (sum, token) => sum + Number(token.counters?.essence || 0),
      0,
    );
  const mandatoryEssenceSpent = [
    ...Object.values(essencePlan.spent),
    ...Object.values(essenceCostPlan.spent),
  ].reduce((sum, amount) => sum + Number(amount || 0), 0);
  const optionalExtraEssenceMax = encodedAbility?.optionalExtraEssence
    ? Math.max(0, Math.min(
        Number(encodedAbility.optionalExtraEssence.max || 0),
        totalEssence - mandatoryEssenceSpent,
      ))
    : 0;
  const remainingTemperaments = Object.entries(essencePlan.remaining)
    .filter(([, amount]) => amount > 0)
    .map(([temperament]) => temperament);
  const handCards = latestState?.players?.[myPlayerId]?.zones?.hand?.cards || [];
  let sourceCopyReserved = false;
  const manifestations = handCards.flatMap((cardId, index) => {
    const manifestation = cardsById.get(cardId);
    if (manifestation?.type !== "manifestation") return [];
    const isSourceCopy = source.zone === "hand" && cardId === source.cardId
      && (Number.isInteger(source.handIndex) ? index === source.handIndex : !sourceCopyReserved);
    if (isSourceCopy) {
      sourceCopyReserved = true;
      return [];
    }
    if (hasPrintedTribute) {
      const tributeTemperaments = cardTributeTemperaments(manifestation);
      const compatible = tributeTemperaments.includes("transcendent")
        || tributeTemperaments.some((temperament) => remainingTemperaments.includes(temperament))
        || remainingTemperaments.includes("hollow");
      if (!compatible || !remainingTemperaments.length) return [];
    }
    return [{
      cardId, index, selectionKey: index,
      paymentValue: cardId, zone: "hand",
    }];
  });
  const limboSource = (latestState?.battlefield || []).find((item) => (
    (item.controllerId || item.ownerId) === myPlayerId
    && Number(item.counters?.Formula || 0) > 0
    && (passiveEffectsByCard.get(item.cardId) || []).some(
      (effect) => effect.kind === "allow_limbo_tribute_with_counter"
    )
  ));
  if (limboSource) {
    const limboCards = latestState?.players?.[myPlayerId]?.zones?.graveyard?.cards || [];
    for (const cardId of limboCards) {
      const manifestation = cardsById.get(cardId);
      if (manifestation?.type !== "manifestation") continue;
      manifestations.push({
        cardId,
        index: null,
        selectionKey: `graveyard:${cardId}:${manifestations.length}`,
        paymentValue: `graveyard|${cardId}`,
        zone: "graveyard",
      });
    }
  }
  for (const item of latestState?.battlefield || []) {
    const manifestation = cardsById.get(item.cardId);
    if (
      battlefieldItemControllerId(item) !== myPlayerId
      || item.fieldZone !== "interzone"
      || manifestation?.type !== "manifestation"
      || !/\bcan be used as tribute from the Interzone\./i.test(
        String(manifestation.effect || ""),
      )
    ) continue;
    manifestations.push({
      cardId: item.cardId,
      itemId: item.id,
      index: null,
      selectionKey: `battlefield:${item.id}`,
      paymentValue: `battlefield|${item.id}`,
      zone: "interzone",
      powerOverride: rulesTributeCandidate(`battlefield|${item.id}`)?.power,
    });
  }
  if (
    Object.keys(essenceCostRequirements).length
    && !hasPrintedTribute
  ) manifestations.length = 0;
  return {
    paymentRequirements, hasPrintedTribute, essencePlan,
    essenceCostRequirements, essenceCostPlan, essenceCostPayable,
    optionalExtraEssenceMax, remainingTemperaments, manifestations,
  };
}

function rulesInitialActionStage(draft) {
  if (
    Object.values(draft.essencePlan.remaining)
      .some((amount) => amount > 0)
  ) return "payment";
  if (draft.optionalExtraEssenceMax > 0) return "extra_essence";
  return "target";
}

function buildRulesActionDraft(source, abilityOverride = undefined) {
  const card = cardsById.get(source?.cardId);
  const sourceItem = source?.itemId
    ? (latestState?.battlefield || []).find(
      (candidate) => candidate.id === source.itemId,
    )
    : null;
  let encodedAbility = abilityOverride !== undefined
    ? abilityOverride
    : source?.actionKind === "activated_effect"
      ? (activatedAbilitiesByCard.get(source.cardId) || []).find((ability) => (
          !Array.isArray(ability.sourceZones)
          || ability.sourceZones.includes(source.zone)
        )) || null
    : source?.zone === "battlefield"
      ? (rulesActivatedAbilitiesForItem(sourceItem) || [])[0] || null
      : ["hand", "suspended"].includes(source?.zone)
        ? (playedAbilitiesByCard.get(source.cardId) || [])[0] || null
        : null;
  if (encodedAbility?.tributeFromSourceCounter && source?.itemId) {
    const item = latestState?.battlefield?.find(
      (candidate) => candidate.id === source.itemId
    );
    const counters = item?.counters || {};
    const counterKey = Object.keys(counters).find(
      (key) => key.toLocaleLowerCase()
        === encodedAbility.tributeFromSourceCounter.toLocaleLowerCase()
    ) || encodedAbility.tributeFromSourceCounter;
    encodedAbility = {
      ...encodedAbility,
      tribute: "{H}".repeat(
        Math.max(0, Math.min(Number(counters[counterKey]) || 0, 20))
      ),
    };
  }
  const targetDraft = rulesStructuredActionTargets(encodedAbility);
  if (encodedAbility?.targets?.sourceOnly && source?.itemId) {
    targetDraft.structuredTargets = targetDraft.structuredTargets.filter(
      (target) => target.id === source.itemId,
    );
  }
  return {
    card,
    encodedAbility,
    ...targetDraft,
    ...rulesActionPaymentDraft(source, card, encodedAbility),
  };
}

function openRulesActionPanel(source) {
  const rules = latestState?.rulesEngine;
  const draft = buildRulesActionDraft(source);
  const { card, encodedAbility } = draft;
  if (!rules?.enabled || rules.priorityPlayerId !== myPlayerId || isObserver || !card) return;
  pendingRulesActionSource = {
    cardId: source.cardId,
    zone: source.zone,
    itemId: source.itemId || null,
    abilityId: encodedAbility?.id || null,
    actionKind: source.actionKind || null,
  };

  $("#rulesActionHeading").textContent = t("rulesDeclareHeading");
  $("#rulesActionSourceImg").src = cardImage(source.cardId);
  $("#rulesActionSourceImg").alt = cardName(source.cardId);
  $("#rulesActionSourceName").textContent = cardName(source.cardId);
  const playedZone = ["hand", "suspended"].includes(source.zone)
    && source.actionKind !== "activated_effect";
  const printedCost = playedZone && card.cost !== null && card.cost !== undefined
    ? rulesText("rulesPrintedCost", { cost: card.cost })
    : "";
  $("#rulesActionSourceMeta").textContent = [
    cardField(card, "typeLabel") || card.type,
    printedCost,
    encodedAbility ? t("rulesEncodedAbility") : "",
    encodedAbility?.exhaustSource ? t("rulesExhaustSourceCost") : "",
    encodedAbility?.sacrificeSource ? t("rulesSacrificeSourceCost") : "",
  ].filter(Boolean).join(" · ");
  $("#rulesActionSourceEffect").textContent = cardField(card, "effect") || t("rulesNoPrintedEffect");

  const kindOptions = encodedAbility
    ? [[playedZone ? "play_card" : "activated_effect", playedZone ? "rulesKindPlay" : "rulesKindActivated"]]
    : rulesActionKindOptions(source.zone);
  $("#rulesActionKind").innerHTML = kindOptions
    .map(([value, label]) => `<option value="${value}">${esc(t(label))}</option>`)
    .join("");
  $("#rulesActionKind").disabled = kindOptions.length === 1;
  $("#rulesActionDescription").value = rulesText(
    playedZone ? "rulesDefaultPlay" : "rulesDefaultActivate",
    { card: cardName(source.cardId) },
  );
  $("#rulesActionTarget").value = "";
  $("#rulesActionCostNote").value = "";

  const { targetRules, noTargetRequired, structuredTargetKind, allowedTargetZones, structuredTargets } = draft;
  const targetInputType = targetRules?.max === 1 ? "radio" : "checkbox";
  $("#rulesTargetList").innerHTML = noTargetRequired
    ? `<span class="rules-target-empty">${esc(t("rulesNoTargetRequired"))}</span>`
    : structuredTargets.length
    ? structuredTargets.map((item) => item.kind === "player"
      ? `<label class="rules-target-choice rules-target-player-choice" title="${esc(rulesPlayerName(item.playerId))}">
          <input type="${targetInputType}" name="rules-action-target" value="${esc(item.key)}" data-target-kind="player" data-player-id="${esc(item.playerId)}">
          <span class="rules-target-player-mark" aria-hidden="true">${esc(rulesPlayerName(item.playerId).slice(0, 1).toUpperCase())}</span>
          <span class="rules-target-copy"><strong>${esc(rulesPlayerName(item.playerId))}</strong><span>${esc(t("rulesPlayerTarget"))}</span></span>
        </label>`
      : ["stack_action", "stack_effect", "stack_item"].includes(item.kind)
      ? `<label class="rules-target-choice rules-target-stack-choice" title="${esc(cardName(item.cardId))}">
          <input type="${targetInputType}" name="rules-action-target" value="${esc(item.key)}" data-target-kind="${esc(item.kind)}" data-action-id="${esc(item.actionId)}" data-card-id="${esc(item.cardId)}">
          <img src="${esc(cardImage(item.cardId))}" alt="">
          <span class="rules-target-copy"><strong>${esc(cardName(item.cardId))}</strong><span>${esc(`${t("rulesStackTitle")} · ${rulesPlayerName(item.controllerId)}`)}</span></span>
        </label>`
      : `<label class="rules-target-choice" title="${esc(cardName(item.cardId))}">
          <input type="${targetInputType}" name="rules-action-target" value="${esc(item.key)}" data-target-kind="${esc(item.kind)}" data-item-id="${esc(item.id || "")}" data-container-id="${esc(item.containerId || "")}" data-zone="${esc(item.zone)}" data-card-id="${esc(item.cardId)}">
          <img src="${esc(cardImage(item.cardId))}" alt="">
          <span class="rules-target-copy"><strong>${esc(cardName(item.cardId))}</strong><span>${esc(item.kind === "zone_card" ? `${rulesPlayerName(item.containerId)} · ${t(item.zone)}` : rulesPlayerName(item.ownerId))}</span></span>
        </label>`).join("")
    : `<span class="rules-target-empty">${esc(t("rulesNoLegalTargets"))}</span>`;

  const {
    paymentRequirements, hasPrintedTribute, essencePlan,
    essenceCostRequirements, essenceCostPlan, remainingTemperaments, manifestations,
  } = draft;
  const tributeFieldset = $("#rulesTributeList").closest("fieldset");
  const hasEssenceCost = Object.keys(essenceCostRequirements || {}).length > 0;
  tributeFieldset.classList.toggle(
    "hidden",
    source.zone === "hand" && !hasPrintedTribute && !hasEssenceCost,
  );
  $("#rulesTributeSummary").classList.toggle(
    "hidden", !hasPrintedTribute && !hasEssenceCost,
  );
  if (hasPrintedTribute) {
    $("#rulesTributeSummary").innerHTML = `
      <span><strong>${esc(t("rulesTributeRequired"))}</strong>${rulesTributeUnitsHtml(paymentRequirements, t("rulesNone"))}</span>
      <span><strong>${esc(t("rulesEssenceUsed"))}</strong>${rulesTributeUnitsHtml(essencePlan.spent, t("rulesNoEssenceUsed"))}</span>
      <span><strong>${esc(t("rulesTributeRemaining"))}</strong>${rulesTributeUnitsHtml(essencePlan.remaining, t("rulesCoveredByEssence"))}</span>`;
  } else {
    $("#rulesTributeSummary").innerHTML = Object.keys(
      essenceCostRequirements || {},
    ).length
      ? `<span><strong>${esc(t("essence"))}</strong>${rulesTributeUnitsHtml(essenceCostRequirements, t("rulesNone"))}</span>
         <span><strong>${esc(t("rulesEssenceUsed"))}</strong>${rulesTributeUnitsHtml(essenceCostPlan.spent, t("rulesNoEssenceUsed"))}</span>`
      : "";
  }

  $("#rulesTributeList").innerHTML = manifestations.length
    ? manifestations.map(({ cardId, index, paymentValue, zone }) => {
        const tribute = cardsById.get(cardId);
        const temperament = tribute?.temperaments?.[0];
        const power = zone === "interzone"
          ? rulesTributeCandidate(paymentValue)?.power
          : tribute?.power;
        return `<label class="rules-tribute-choice" title="${esc(cardName(cardId))}"><input type="checkbox" value="${esc(paymentValue)}" ${Number.isInteger(index) ? `data-hand-index="${index}"` : ""}>${temperament ? `<img src="${esc(temperamentSymbol(temperament))}" alt="">` : ""}<span>${esc(cardName(cardId))} · ${esc(rulesText("rulesPowerValue", { power: power ?? "—" }))}${zone === "graveyard" ? ` · ${esc(t("graveyard"))}` : zone === "interzone" ? ` · ${esc(t("interzone"))}` : ""}</span></label>`;
      }).join("")
    : `<span class="rules-tribute-empty">${esc(hasPrintedTribute && !remainingTemperaments.length ? t("rulesCoveredByEssence") : t("rulesNoTributeCards"))}</span>`;

  $("#rulesActionKindLabel").textContent = t("rulesActionKindLabel");
  $("#rulesActionDescriptionLabel").textContent = t("rulesActionDescriptionLabel");
  $("#rulesActionTargetLabel").textContent = t("rulesActionTargetLabel");
  $("#rulesActionTarget").placeholder = t("rulesActionTargetPlaceholder");
  $("#rulesTargetLegend").textContent = t(structuredTargetKind === "player"
    ? "rulesPlayerTargetLegend"
    : structuredTargetKind === "stack_action"
      ? "rulesStackTargetLegend"
    : ["stack_effect", "stack_item"].includes(structuredTargetKind)
      ? "rulesStackEffectTargetLegend"
    : allowedTargetZones.some((zone) => zone !== "battlefield")
      ? "rulesStructuredTargetLegend" : "rulesTargetLegend");
  $("#rulesTargetHint").textContent = t(noTargetRequired ? "rulesNoTargetRequired" : encodedAbility ? "rulesEncodedTargetHint" : "rulesTargetHint");
  $("#rulesActionCostLabel").textContent = t("rulesActionCostLabel");
  $("#rulesActionCostNote").placeholder = t("rulesActionCostPlaceholder");
  $("#rulesTributeLegend").textContent = t("rulesTributeLegend");
  $("#rulesTributeHint").textContent = t(hasPrintedTribute ? "rulesTributeAutomaticHint" : "rulesTributeHint");
  $("#rulesActionWarning").textContent = t(
    encodedAbility?.result
      ? "rulesEncodedAutomaticWarning"
      : encodedAbility ? "rulesEncodedAbilityWarning" : "rulesActionManualWarning"
  );
  $("#rulesActionCancelBtn").textContent = t("cancel");
  $("#rulesActionCloseBtn").title = t("close");
  $("#rulesActionCloseBtn").setAttribute("aria-label", t("close"));
  $("#rulesActionDeclareBtn").textContent = t("rulesDeclareAction");
  $("#rulesActionPanel").classList.remove("hidden");
  $("#rulesActionDescription").focus();
}

function rulesActionContextItem(source) {
  const rules = latestState?.rulesEngine;
  if (!rules?.enabled || rules.priorityPlayerId !== myPlayerId || isObserver) return null;
  if (["hand", "suspended"].includes(source.zone)) {
    const cardType = cardsById.get(source.cardId)?.type;
    const handAbility = source.zone === "hand"
      ? (activatedAbilitiesByCard.get(source.cardId) || []).find(
          (ability) => (ability.sourceZones || []).includes("hand"),
        )
      : null;
    if (handAbility) {
      return {
        label: t("rulesDeclareCardAction"),
        onSelect: () => beginRulesHandActivatedAction(
          source.cardId, source.handIndex,
        ),
      };
    }
    const phaseId = currentPhaseUi().phase?.id;
    if (cardType === "ephemeral_will" && !rulesEphemeralPhasesClient(cardsById.get(source.cardId)).includes(phaseId)) return null;
    if (
      cardType === "persistent_will"
      && phaseId !== "end_actions"
      && !(
        phaseId === "confrontation_before_revelation"
        && rulesBeforeRevelationPlayClient(cardsById.get(source.cardId))
      )
    ) return null;
    if (!["ephemeral_will", "persistent_will"].includes(cardType)) return null;
  }
  if (
    source.zone === "battlefield"
    && !["confrontation_reaction", "resolution_effects", "end_actions"].includes(currentPhaseUi().phase?.id)
  ) return null;
  return { label: t("rulesDeclareCardAction"), onSelect: () => openRulesActionPanel(source) };
}
const LANGUAGE_FLAGS = { fr: "🇫🇷", en: "🇬🇧", it: "🇮🇹" };
const LANGUAGE_NAMES = { fr: "Français", en: "English", it: "Italiano" };

function updateLanguageButtons() {
  const index = KO_LANGUAGES.indexOf(currentLanguage);
  const next = KO_LANGUAGES[(index + 1) % KO_LANGUAGES.length];
  [$("#languageBtn"), $("#gameLanguageBtn"), $("#tournamentLanguageBtn")].filter(Boolean).forEach((button) => {
    button.textContent = LANGUAGE_FLAGS[currentLanguage];
    button.title = `${LANGUAGE_NAMES[currentLanguage]} → ${LANGUAGE_NAMES[next]}`;
    button.setAttribute("aria-label", button.title);
  });
}

function setInterfaceLanguage(nextLanguage) {
  currentLanguage = KO_LANGUAGES.includes(nextLanguage) ? nextLanguage : "en";
  localStorage.setItem(KO_LANGUAGE_KEY, currentLanguage);
  document.documentElement.lang = currentLanguage;
  paintStaticText();
  updateLanguageButtons();
  const selectedEssence = selectedEssenceTemperament;
  initEssenceToolbar();
  if (selectedEssence) {
    $(`#essenceTemperamentGrid [data-temperament="${selectedEssence}"]`)?.classList.add("active");
    $("#neutralTokenNameField").classList.toggle("hidden", selectedEssence !== "neutral");
  }
  renderStarterDecks();
  renderSavedDecks();
  renderAll();
  if (!$("#inspectPanel").classList.contains("hidden") && inspectHistory[0]) showInspect(inspectHistory[0]);
}

function initLanguageSwitch() {
  document.documentElement.lang = currentLanguage;
  updateLanguageButtons();
  [$("#languageBtn"), $("#gameLanguageBtn"), $("#tournamentLanguageBtn")].filter(Boolean).forEach((button) => {
    button.onclick = () => {
      const index = KO_LANGUAGES.indexOf(currentLanguage);
      setInterfaceLanguage(KO_LANGUAGES[(index + 1) % KO_LANGUAGES.length]);
    };
  });
}

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
  $("#rulesBetaLabel").textContent = t("rulesBetaLabel");
  $("#rulesBetaHint").textContent = t("rulesBetaHint");
  $("#banListToggleLabel").textContent = t("banListToggleLabel");
  $("#banListToggleHint").textContent = t("banListToggleHint");
  $("#editBanListBtn").textContent = t("edit");
  $("#homePolicyHeading").textContent = t("tournamentDeckRules");
  $("#homeBannedCardsLabel").textContent = t("bannedCards");
  $("#homeBannedCardInput").placeholder = t("cardNameOrNumber");
  $("#homeBannedCardAddBtn").textContent = t("add");
  $("#homeRestrictedGroupAddBtn").textContent = t("addRestrictedGroup");
  $("#homePolicyDoneBtn").textContent = t("confirm");
  $("#tournamentToggleLabel").textContent = t("tournamentMode");
  $("#createTournamentLabel").textContent = t("createTournament");
  $("#createTournamentHint").textContent = t("createTournamentHint");
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
  $("#gameMoreLabel").textContent = t("moreActions");
  $("#importDeckBtn").textContent = t("editDeck");
  $("#currentSideboardBtn").textContent = t("editCurrentSideboard");
  $("#downloadLogBtn").textContent = t("downloadLog");
  $("#endSessionBtn").textContent = t("endSession");
  $("#leaveSessionBtn").textContent = t("leaveSession");
  $("#judgeReturnBtn").textContent = t("returnToTournamentConsole");
  $("#fullscreenBtn").innerHTML = fullscreenIconSvg();
  $("#fullscreenBtn").title = t("fullscreen");
  $("#fullscreenBtn").setAttribute("aria-label", t("fullscreen"));
  $("#phaseTrackerBtn").textContent = t("gamePhases");
  $("#phaseAdvancedLabel").textContent = t("advancedMode");
  $("#importDeckHeading").textContent = t("editDeck");
  $("#starterDecksHeading").textContent = t("starterDecks");
  $("#savedDecksHeading").textContent = t("savedDecks");
  $("#currentDeckHeading").textContent = t("currentDeck");
  $("#importDeckHintText").textContent = t("importDeckHint");
  $("#importDeckText").placeholder = t("importDeckPlaceholder");
  $("#importPasteBtn").textContent = t("import");
  $("#importCancelBtn").textContent = t("close");
  $("#importSideboardBtn").textContent = t("editSideboard");
  resetImportDeckValidationArm();
  $("#sideboardEditorHeading").textContent = t("sideboardEditor");
  $("#sideboardEditorHint").textContent = t("sideboardEditorHint");
  $("#sideboardResetWarning").textContent = t("sideboardResetWarning");
  $("#sideboardCancelBtn").title = t("close");
  $("#sideboardCancelBtn").setAttribute("aria-label", t("close"));
  $("#sideboardValidateBtn").textContent = t("confirm");
  $("#logHeading").textContent = t("logHeader");
  $("#logDownloadBtn").textContent = t("logDownload");
  $("#logCloseBtn").textContent = t("close");
  $("#handDrawOneBtn").textContent = t("handDrawOneBtn");
  $("#handDrawHandBtn").textContent = t("handDrawHandBtn");
  $("#handDiscardBtn").textContent = t("handDiscard");
  $("#handDiscardRandomBtn").textContent = t("handDiscardRandom");
  $("#handShowBtn").textContent = t("handShow");
  $("#handMulliganBtn").textContent = t("mulligan");
  $("#handToolsToggleLabel").textContent = t("handOptions");
  $("#handToolsToggleBtn").title = t("handOptions");
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
  $("#neutralTokenNameLabel").textContent = t("tokenName");
  $("#neutralTokenNameInput").placeholder = t("neutralToken");
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
  $("#tournamentTitle").textContent = t("tournamentConsole");
  $("#tournamentMatchHeading").textContent = t("tournamentControlRoom");
  $("#tournamentAccessHeading").textContent = t("accessCodes");
  $("#tournamentPlayersHeading").textContent = t("playersAndState");
  $("#tournamentLogHeading").textContent = t("liveTournamentLog");
  $("#tournamentExportLogBtn").textContent = t("extractFullLog");
  $("#tournamentStartBtn").textContent = t("startMatch");
  $("#tournamentEndBtn").textContent = t("endMatch");
  $("#tournamentLeaveBtn").textContent = t("leaveConsole");
  $("#tournamentViewMatchBtn").textContent = t("viewMatch");
  $("#tournamentRulesSummary").textContent = t("tournamentDeckRules");
  $("#bannedCardsLabel").textContent = t("bannedCards");
  $("#bannedCardInput").placeholder = t("cardNameOrNumber");
  $("#bannedCardAddBtn").textContent = t("add");
  $("#restrictedGroupAddBtn").textContent = t("addRestrictedGroup");
  $("#tournamentRulesSaveBtn").textContent = t("saveRules");
  $("#tournamentPlayerAlertTitle").textContent = t("tournamentAlert");
  renderTournamentConsole();
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

// kind: "" (neutral, no box), "error" (red — lost/invalid), "warning"
// (orange — connecting/reconnecting), "success" (green — just reconnected)
function setStatus(message, kind = "") {
  const el = $("#gameScreen").classList.contains("hidden") ? $("#statusLine") : $("#gameStatusLine");
  el.textContent = message || "";
  el.classList.remove("error", "warning", "success");
  if (kind) el.classList.add(kind);
}

function initJoinScreen() {
  $("#tournamentToggleBtn").onclick = () => {
    const options = $("#tournamentLauncherOptions");
    const expanded = options.classList.toggle("hidden") === false;
    options.setAttribute("aria-hidden", String(!expanded));
    $("#tournamentToggleBtn").setAttribute("aria-expanded", String(expanded));
  };
  $("#banListInput").onchange = () => {
    $("#editBanListBtn").disabled = !$("#banListInput").checked;
  };
  $("#editBanListBtn").disabled = true;
  $("#editBanListBtn").onclick = () => {
    renderHomeDeckPolicy();
    $("#homePolicyPanel").classList.remove("hidden");
  };
  $("#homePolicyCloseBtn").onclick = () => $("#homePolicyPanel").classList.add("hidden");
  $("#homePolicyDoneBtn").onclick = () => $("#homePolicyPanel").classList.add("hidden");
  $("#homeBannedCardAddBtn").onclick = () => {
    if (!homePolicyDraft) homePolicyDraft = defaultHomeDeckPolicy();
    const cardId = resolveTournamentCard($("#homeBannedCardInput").value);
    if (!cardId) return showToast(t("unknownCard"), true);
    if (!homePolicyDraft.bannedCardIds.includes(cardId)) homePolicyDraft.bannedCardIds.push(cardId);
    $("#homeBannedCardInput").value = "";
    renderHomeDeckPolicy();
  };
  $("#homeRestrictedGroupAddBtn").onclick = () => {
    if (!homePolicyDraft) homePolicyDraft = defaultHomeDeckPolicy();
    homePolicyDraft.restrictedGroups.push({ id: `restricted-${Date.now()}`, name: `${t("restrictedGroup")} ${homePolicyDraft.restrictedGroups.length + 1}`, cardIds: [] });
    renderHomeDeckPolicy();
  };
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
    connectAndJoin({
      createNew: true,
      name,
      rulesBeta: $("#rulesBetaInput").checked,
      banListEnabled: $("#banListInput").checked,
      deckPolicy: homePolicyDraft || defaultHomeDeckPolicy(),
    });
  };

  $("#createTournamentBtn").onclick = () => {
    const name = $("#createName").value.trim() || t("organizer");
    localStorage.setItem("ko_name", name);
    connectAndJoin({ createTournament: true, name, rulesBeta: $("#rulesBetaInput").checked });
  };

  $("#joinBtn").onclick = () => {
    const name = $("#joinName").value.trim() || "Player";
    const code = $("#joinCode").value.trim().toUpperCase();
    if (!code) return setStatus(t("invalidCode"), "error");
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

let pendingCreateFlow = null;

function connectAndJoin(joinPayload) {
  setStatus(t("connecting"), "warning");
  intentionalClose = false;
  joinedCode = joinPayload.code || null;
  joinedName = joinPayload.name;
  const createNew = Boolean(joinPayload.createNew);
  const createTournament = Boolean(joinPayload.createTournament);
  const rulesBeta = Boolean(joinPayload.rulesBeta);
  const banListEnabled = Boolean(joinPayload.banListEnabled);
  pendingCreateFlow = createTournament ? "tournament" : (createNew ? "casual" : null);

  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${proto}//${location.host}/ws`);
  ws.onopen = () => {
    ws.send(JSON.stringify({ type: "join", createNew, createTournament, rulesBeta, banListEnabled, deckPolicy: joinPayload.deckPolicy, code: joinedCode, name: joinedName, clientId }));
  };
  ws.onmessage = (event) => handleServerMessage(JSON.parse(event.data));
  ws.onclose = () => {
    if (intentionalClose) return;
    if ($("#gameScreen").classList.contains("hidden") && $("#tournamentScreen").classList.contains("hidden")) {
      setStatus(t("invalidCode"), "error");
      return;
    }
    wasDisconnected = true;
    if (!$("#tournamentScreen").classList.contains("hidden")) showToast(t("connectionLost"), true);
    else setStatus(t("connectionLost"), "error");
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
  $("#tournamentScreen").classList.add("hidden");
  $("#gameScreen").classList.remove("hidden");
  // #battlefieldWrap is zero-sized while #gameScreen is display:none, so the
  // fit-and-centre math only works once it's actually visible
  centerBoardInView();
}

function showTournamentScreen() {
  judgeMatchView = false;
  $("#joinScreen").classList.add("hidden");
  $("#gameScreen").classList.add("hidden");
  $("#tournamentScreen").classList.remove("hidden");
  renderTournamentConsole();
}

function showTournamentMatch() {
  if (!["judge", "organizer"].includes(connectionRole)) return;
  judgeMatchView = true;
  showGameScreen();
  $("#judgeReturnBtn").classList.remove("hidden");
  renderAll();
}

// Used both when P2/an observer simply leaves (the session carries on for
// everyone else) and, after send()-ing end_session, for P1's own client —
// in both cases *this* client is done and goes back to the home screen.
function leaveSession() {
  intentionalClose = true;
  wasDisconnected = false;
  if (ws) ws.close();
  ws = null;
  latestState = null;
  myPlayerId = null;
  isObserver = false;
  connectionRole = "player";
  connectionMode = "casual";
  codePlayer = null;
  codeObserver = null;
  codeOrganizer = null;
  tournamentCodes = null;
  judgeMatchView = false;
  rulesBetaActivated = false;
  tournamentPolicyDraft = null;
  tournamentPolicyDirty = false;
  openPresenceRole = null;
  lastTournamentNoticeStatus = null;
  lastRulesVfxSequence = null;
  removeRulesVfx();
  joinedCode = null;
  joinedName = null;
  sessionEndedNotified = false;
  revealedHandCards.clear();
  pendingIncomingRequest = null;
  $("#handRequestPanel").classList.add("hidden");
  pendingTriggeredPlacement = null;
  $("#rulesChoicePanel").classList.add("hidden");
  $("#sessionEndedBanner").classList.add("hidden");
  $("#sessionEndedBanner").classList.remove("rules-result");
  $("#gameScreen").classList.add("hidden");
  $("#tournamentScreen").classList.add("hidden");
  $("#joinScreen").classList.remove("hidden");
  $("#codesBox").classList.add("hidden");
  setStatus("");
}

// ---------------------------------------------------------------- server messages

function handleServerMessage(msg) {
  if (msg.type === "joined") {
    myPlayerId = msg.playerId;
    connectionRole = msg.role || (msg.isObserver ? "observer" : "player");
    connectionMode = msg.mode || "casual";
    rulesBetaActivated = Boolean(msg.rulesBeta);
    if (rulesBetaActivated) phaseTrackerVisible = true;
    isObserver = msg.isObserver;
    $("#drawToolbar").classList.toggle("hidden", isObserver);
    $("#tokenToolbar").classList.toggle("hidden", isObserver);
    if (msg.codePlayer) codePlayer = msg.codePlayer;
    codeObserver = msg.codeObserver;
    if (msg.codeOrganizer) codeOrganizer = msg.codeOrganizer;
    if (msg.tournamentCodes) tournamentCodes = msg.tournamentCodes;
    joinedCode = joinedCode || codeOrganizer || codePlayer;
    if (wasDisconnected) {
      wasDisconnected = false;
      if (!$("#tournamentScreen").classList.contains("hidden")) showToast(t("reconnected"));
      else setStatus(t("reconnected"), "success");
    } else {
      setStatus("");
    }

    renderHeaderCodes();
    updateHeaderCounts();

    if (pendingCreateFlow === "casual") {
      pendingCreateFlow = null;
      $("#playerCodeValue").textContent = codePlayer;
      $("#observerCodeValue").textContent = codeObserver;
      $("#codesBox").classList.remove("hidden");
    } else if (pendingCreateFlow === "tournament" || connectionRole === "organizer" || connectionRole === "judge") {
      pendingCreateFlow = null;
      showTournamentScreen();
    } else if ($("#gameScreen").classList.contains("hidden")) {
      showGameScreen();
    }
  } else if (msg.type === "state") {
    const rulesVfxBatch = prepareRulesVfxBatch(msg);
    latestState = msg;
    if (connectionMode === "tournament" && connectionRole === "player") {
      const status = msg.tournament?.status;
      if (status && status !== "active" && status !== lastTournamentNoticeStatus) {
        showTournamentPlayerAlert(t(status === "ended" ? "tournamentMatchEnded" : "tournamentWaitingForStart"), status === "ended");
      }
      lastTournamentNoticeStatus = status;
    }
    if ((connectionRole === "organizer" || connectionRole === "judge") && !judgeMatchView) {
      renderTournamentConsole();
    } else {
      renderAll();
      renderStrokes();
      playRulesVfxBatch(rulesVfxBatch);
    }
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
    if (msg.code === "session_not_found" && !$("#gameScreen").classList.contains("hidden")) {
      // this was a reconnect attempt (gameScreen already visible) hitting a
      // session that's genuinely gone (e.g. the server process restarted) —
      // retrying forever would just keep re-showing "Connecting…", so stop
      // and say so plainly instead of leaving that stuck on screen
      intentionalClose = true;
      if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
      if (ws) ws.close();
      setStatus(t("sessionGone"), "error");
    } else if ($("#gameScreen").classList.contains("hidden") && $("#tournamentScreen").classList.contains("hidden")) {
      setStatus(msg.message, "error");
    } else if (connectionMode === "tournament" && connectionRole === "player") {
      showTournamentPlayerAlert(localizeServerError(msg.message), true);
    } else {
      showToast(localizeServerError(msg.message), true);
    }
    console.warn("Server error:", msg.message);
  } else if (msg.type === "log") {
    if (pendingTournamentLogDownload) {
      pendingTournamentLogDownload = false;
      downloadLog(msg.entries);
    } else if (pendingPlayerLogFor) {
      renderPlayerLog(msg.entries, pendingPlayerLogFor);
      pendingPlayerLogFor = null;
    } else {
      renderLog(msg.entries);
    }
  } else if (msg.type === "chat_message") {
    chatMessages.push(msg);
    if (chatMessages.length > 200) chatMessages.shift();
    renderChatMessages();
    if (chatState !== "open") { unreadChatCount++; updateChatBadge(); }
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
      if (ctx && ctx.allowMoveToField) items.push(copyCardMenuItem(cardId, ctx.ownerId, ctx.zone));
      if (ctx && ctx.allowMoveToField) {
        const cardOwnerId = ctx.cardOwnerId || zoneCardOwner(ctx.ownerId, ctx.zone, cardId);
        items.push({ separator: true });
        items.push({ label: t("playFaceUp"), onSelect: () => { playFromZone(ctx.ownerId, ctx.zone, cardId, true); markRevealCardSent(cardId, t("battlefield")); } });
        items.push({ label: t("playFaceDown"), onSelect: () => { playFromZone(ctx.ownerId, ctx.zone, cardId, false); markRevealCardSent(cardId, t("battlefield")); } });
        items.push({ separator: true });
        ["hand", "graveyard", "exile", "receptacle"].forEach((z) => {
          const toOwnerId = cardDestinationOwner(cardOwnerId, z);
          if (!toOwnerId) return;
          items.push({
            label: cardDestinationLabel(cardOwnerId, z),
            onSelect: () => {
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
            send({ type: "move_card", fromOwnerId: ctx.ownerId, fromZone: ctx.zone, toOwnerId: cardOwnerId, toZone: "deck", cardId, position: "top" });
            markRevealCardSent(cardId, `${t("deck")} (${t("moveToDeckTop")})`, () =>
              send({ type: "move_card", fromOwnerId: cardOwnerId, fromZone: "deck", toOwnerId: ctx.ownerId, toZone: ctx.zone, cardId })
            );
          },
        });
        items.push({
          label: t("moveToDeckBottom"),
          onSelect: () => {
            send({ type: "move_card", fromOwnerId: ctx.ownerId, fromZone: ctx.zone, toOwnerId: cardOwnerId, toZone: "deck", cardId, position: "bottom" });
            markRevealCardSent(cardId, `${t("deck")} (${t("moveToDeckBottom")})`, () =>
              send({ type: "move_card", fromOwnerId: cardOwnerId, fromZone: "deck", toOwnerId: ctx.ownerId, toZone: ctx.zone, cardId })
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
  setMyActivity("reveal");
  wireRevealCards({ ownerId: msg.ownerId, zone: msg.zone, allowMoveToField: !isObserver && msg.ownerId === myPlayerId });
}

function showScryPopup(cardIds) {
  revealSentState = new Map();
  $("#revealHeading").textContent = t("scryHeader");
  $("#revealWho").textContent = "";
  $("#revealCards").innerHTML = cardImagesHtml(cardIds);
  $("#revealPanel").classList.remove("hidden");
  setMyActivity("scry");
  // scry is always a private peek at your own deck, so this is always your own zone
  wireRevealCards({ ownerId: myPlayerId, zone: "deck", allowMoveToField: true });
}

// ---------------------------------------------------------------- actions (send)

function send(payload) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(payload));
}

// ---------------------------------------------------------------- rendering

let sessionEndedNotified = false;

function rulesOutcomeText(outcome) {
  if (outcome?.reason === "invalid_opening_hand_after_mulligan") {
    const loserNames = (outcome.loserIds || []).map((playerId) => latestState?.players?.[playerId]?.name || playerId);
    if (outcome.draw) return t("rulesOpeningMulliganDraw");
    return rulesText("rulesOpeningMulliganLoss", { player: loserNames[0] || "—" });
  }
  if (outcome?.reason === "invalid_recovery_hand_after_mulligan") {
    const loserNames = (outcome.loserIds || []).map((playerId) => latestState?.players?.[playerId]?.name || playerId);
    if (outcome.draw) return t("rulesRecoveryMulliganDraw");
    return rulesText("rulesRecoveryMulliganLoss", { player: loserNames[0] || "—" });
  }
  if (!outcome?.scores) return t("sessionEnded");
  const winnerNames = (outcome.winnerIds || [])
    .map((playerId) => latestState?.players?.[playerId]?.name || playerId);
  const result = outcome.draw
    ? t("rulesResultDraw")
    : `${winnerNames[0] || "—"} ${t("rulesResultWins")}`;
  const scoreLines = Object.entries(outcome.scores).map(([playerId, score]) => {
    const name = latestState?.players?.[playerId]?.name || playerId;
    return `${name}: ${score.total} ${t("vesselPoints")} (${t("rulesVessel")}: ${score.vesselPoints}, ${t("rulesEffects")}: ${score.effectPoints}, ${t("rulesDeckBonus")}: ${score.deckBonus})`;
  });
  return `${t("rulesGameEnded")} ${result} — ${scoreLines.join(" · ")}`;
}

function renderAll() {
  if (!latestState) return;
  renderBattlefield();
  renderHandTray();
  renderOppRows();
  renderPhaseTracker();
  renderRulesStack();
  renderRulesPregame();
  renderRulesChoice();
  renderRulesBoardFlow();
  if (!$("#handViewPanel").classList.contains("hidden")) {
    const viewingId = $("#handViewPanel").dataset.viewingPlayer;
    if (viewingId && latestState.players[viewingId]) openHandView(viewingId);
  }
  if (!$("#deckBrowserPanel").classList.contains("hidden")) {
    const { ownerId, zone } = $("#deckBrowserPanel").dataset;
    if (ownerId && zone && latestState.players[ownerId]) openPileBrowser(ownerId, zone);
  }
  if (!$("#importPanel").classList.contains("hidden")) {
    renderCurrentDeckSummary();
    renderImportPanelActions();
  }
  updateHeaderCounts();
  const isTournament = latestState.mode === "tournament";
  const canEndForAll = !isTournament && !isObserver && mySeat() === 0;
  const playerIds = Object.keys(latestState.players || {});
  const confirmedDecks = new Set(latestState.rulesEngine?.deckConfirmedPlayerIds || []);
  const assistedDecksLocked = Boolean(latestState.rulesEngine?.enabled && playerIds.length >= 2 && playerIds.every((playerId) => confirmedDecks.has(playerId)));
  $("#endSessionBtn").classList.toggle("hidden", !canEndForAll);
  $("#leaveSessionBtn").classList.toggle("hidden", canEndForAll || ["judge", "organizer"].includes(connectionRole));
  $("#resetBoardBtn").classList.toggle("hidden", !canEndForAll);
  $("#currentSideboardBtn").classList.toggle("hidden", isObserver || assistedDecksLocked || !latestState.players?.[myPlayerId] || (isTournament && latestState.tournament?.status !== "lobby" && !rules_pregame_active_client()));
  $("#importDeckBtn").classList.toggle("hidden", isObserver || assistedDecksLocked || (isTournament && latestState.tournament?.status !== "lobby" && !rules_pregame_active_client()));
  $("#downloadLogBtn").classList.toggle("hidden", isTournament && !["judge", "organizer"].includes(connectionRole));
  $("#judgeReturnBtn").classList.toggle("hidden", !(["judge", "organizer"].includes(connectionRole) && judgeMatchView));
  const tournamentLocked = isTournament && latestState.tournament?.status !== "active";
  $("#gameScreen").classList.toggle("tournament-locked", tournamentLocked);
  $("#tournamentWaitingBanner").classList.toggle("hidden", !tournamentLocked);
  if (tournamentLocked) {
    $("#tournamentWaitingBanner").textContent = t(latestState.tournament?.status === "ended" ? "tournamentMatchEnded" : "tournamentWaitingForStart");
  }
  $("#endSessionBtn").disabled = latestState.ended;
  if (latestState.ended) {
    sessionEndedNotified = true;
    const outcome = latestState.rulesEngine?.outcome;
    // A toast fades; the result must stay visible for both players.
    $("#sessionEndedBanner").textContent = outcome ? rulesOutcomeText(outcome) : t("sessionEnded");
    $("#sessionEndedBanner").classList.toggle("rules-result", Boolean(outcome));
    $("#sessionEndedBanner").classList.remove("hidden");
  }
}

// Always-visible row(s), top-left: a regular player only ever needs their
// one opponent's row (their own hand is already visible in the tray below);
// an observer has no "own hand" to skip, so they get one row per player.
// Broadcasts "what menu am I in" so the opponent's row can show e.g.
// "scrying…" instead of leaving them wondering if the other side has gone
// AFK. Never private (it's just a menu name, no card identities), so no
// permission gate is needed either side.
let myActivity = null;
function setMyActivity(activity) {
  if (myActivity === activity) return;
  myActivity = activity;
  send({ type: "set_activity", activity });
}

// The full action log (session.log) is comprehensive by design — it's the
// anti-cheat record, meant to be read by whoever's debugging a dispute, not
// glanced at mid-game. This is a much narrower, friendlier subset/format of
// the SAME underlying entries, limited to the handful of actions the user
// explicitly asked for: drew, discarded/moved a card, played, including a
// card leaving the battlefield straight into a pile.
const PLAYER_LOG_TYPES = new Set([
  "draw", "draw_to_limit", "opening_hand_draw", "move_card", "place_card", "remove_battlefield_item", "pass_phase",
  "rules_action_declared", "rules_action_triggered", "rules_priority_passed", "rules_priority_cancelled", "rules_priority_rolled", "rules_action_resolved", "rules_choice_resolved", "rules_phase_advanced", "rules_confrontation_compared", "rules_confrontation_cleanup", "rules_field_zone_changed",
]);

function isPlayerLogRelevant(e) {
  if (!PLAYER_LOG_TYPES.has(e.type)) return false;
  // a synthetic token-card has no real identity at all — nothing to show
  return !(e.type === "remove_battlefield_item" && e.details && e.details.tokenCard);
}

// Cards that came from a private zone (e.g. what a scry decides to do with a
// card) often have no cardId in the log at all — that's the server's own
// privacy redaction, not a bug — but the EVENT itself ("put a card into X")
// is still worth showing, just with the identity withheld, the same way a
// face-down play already gets a generic "a face-down card" instead of being
// dropped from the feed entirely.
function namedOrUnknownCard(cardId) {
  return cardId
    ? `<span class="pl-card-name" data-pl-card="${esc(cardId)}">${esc(cardName(cardId))}</span>`
    : `<span class="pl-card-unknown">${esc(t("plAnUnknownCard"))}</span>`;
}

// Wires hover-preview + click-to-inspect on every card name a formatted
// player-log entry produced — called after inserting the HTML (both the
// opponent-row mini-feed and the full player-log panel use this).
function wirePlayerLogCardNames(container) {
  container.querySelectorAll("[data-pl-card]").forEach((el) => {
    const cardId = el.dataset.plCard;
    el.addEventListener("mouseenter", () => showCardPreview(cardId, el));
    el.addEventListener("mouseleave", hideCardPreview);
    el.addEventListener("click", (event) => {
      event.stopPropagation();
      showInspect(cardId);
    });
  });
}

function translateFor(key, language = currentLanguage) {
  return (ui[language] && ui[language][key]) ?? ui.en[key] ?? key;
}

function phaseLogLinesFor(details, language = currentLanguage) {
  const phaseId = details.phaseId || details.phase;
  const phase = ADVANCED_PHASES.find((item) => item.id === phaseId)
    || BASIC_PHASES.find((item) => item.id === phaseId)
    || BASIC_PHASES.find((item) => item.id === details.phase);
  if (!phase) return { phase: "", step: "" };
  const group = PHASE_GROUPS.find((item) => item.id === (phase.parent || phase.id));
  const phaseLabel = group ? translateFor(group.label, language) : translateFor(phase.label, language);
  if (!details.advancedMode || !phase.stepNumber) return { phase: phaseLabel, step: "" };
  const step = [phase.subphase ? translateFor(phase.subphase, language) : "", `${translateFor("phaseStep", language)} ${phase.stepNumber} — ${translateFor(phase.label, language)}`]
    .filter(Boolean)
    .join(" · ");
  return { phase: phaseLabel, step };
}

function phaseLogLines(details) {
  return phaseLogLinesFor(details, currentLanguage);
}

function localizeServerError(message) {
  const known = {
    "The tournament match has not started yet.": "tournamentNotStartedError",
    "The tournament match has ended.": "tournamentMatchEnded",
    "Tournament decks are locked once the match starts.": "tournamentDecksLocked",
    "You do not have priority.": "rulesNoPriorityError",
    "Both players must join before using priority.": "rulesNeedPlayersError",
    "Describe the action before adding it to the Stack.": "rulesDescribeActionError",
    "A Persistent Will cannot be played as a response.": "rulesPersistentResponseError",
    "An Ephemeral Will cannot be played during the current step.": "rulesEphemeralTimingError",
    "A Persistent Will can only be played during End actions.": "rulesPersistentTimingError",
    "This effect cannot be activated during the current step.": "rulesActivatedTimingError",
    "This card cannot be played as a Stack action during the current step.": "rulesCardTimingError",
    "This card cannot be played again until the end of the turn.": "rulesPlayRestrictedError",
    "The source card is not in your Hand.": "rulesSourceMovedError",
    "The source card is not on your side of the field.": "rulesSourceMovedError",
    "A card declared in the Stack cannot leave your Hand before it resolves.": "rulesSourceReservedError",
    "A selected Tribute card is no longer in your Hand.": "rulesTributeMovedError",
    "Only Manifestations from your Hand can be declared as Tribute here.": "rulesTributeTypeError",
    "A selected target is no longer face up on the battlefield.": "rulesTargetMovedError",
    "A selected target no longer matches the declared card.": "rulesTargetMovedError",
    "A selected card is no longer available on the Stack.": "rulesStackTargetMovedError",
    "A selected Stack target no longer matches the declared card.": "rulesStackTargetMovedError",
    "The targeted card is no longer on the Stack.": "rulesStackTargetMovedError",
    "A selected effect is no longer available on the Stack.": "rulesStackEffectTargetMovedError",
    "The targeted effect is no longer on the Stack.": "rulesStackEffectTargetMovedError",
    "The selected Manifestations do not pay the full printed Tribute.": "rulesTributeInsufficientError",
    "This Tribute must use fewer Manifestations.": "rulesTributeRedundantError",
    "Choose the activated ability to put on the Stack.": "rulesAbilityRequiredError",
    "Unknown activated ability.": "rulesAbilityUnknownError",
    "Choose the played ability to put on the Stack.": "rulesPlayedAbilityRequiredError",
    "Unknown played ability.": "rulesPlayedAbilityUnknownError",
    "This effect requires a different type of Stack card.": "rulesStackCopyTypeError",
    "Choose whether to keep or replace the copied Will's target.": "rulesCopyChoiceError",
    "The copied Stack action is no longer available.": "rulesCopyMissingError",
    "Choose the required number of targets for this activated ability.": "rulesAbilityTargetCountError",
    "Choose the required number of targets for this effect.": "rulesAbilityTargetCountError",
    "This activated ability requires a different type of target.": "rulesAbilityTargetTypeError",
    "The source card is already exhausted.": "rulesAbilityExhaustedError",
    "Choose a valid player for this triggered effect.": "rulesTriggerPlayerTargetError",
    "A required card choice must be completed first.": "rulesChoicePendingError",
    "This card choice is no longer available.": "rulesChoiceExpiredError",
    "Choose the required number of cards.": "rulesChoiceCountError",
    "A selected card is no longer in your hand.": "rulesChoiceMovedError",
    "Order every simultaneous Stack action exactly once.": "rulesSimultaneousOrderError",
    "Immediate Effects must remain above other simultaneous actions.": "rulesImmediateOrderError",
    "Choose a valid Persist Manifestation.": "rulesPersistChoiceError",
    "A Persist Manifestation is no longer available.": "rulesPersistExpiredError",
    "Choose whether to return the remembered card.": "rulesMemoryReturnChoiceError",
    "This remembered effect is no longer available.": "rulesMemoryExpiredError",
    "This Chain effect cannot be declined.": "rulesChainMandatoryError",
    "Choose one Manifestation to Chain.": "rulesChainChoiceError",
    "The selected Manifestation is no longer in the required zone.": "rulesChainMovedError",
    "Only a Manifestation can be Chained.": "rulesChainTypeError",
    "Choose a valid confrontation destination.": "rulesConfrontationDestinationError",
    "This confrontation card is no longer available.": "rulesConfrontationCardMovedError",
    "Choose a valid Interzone card to replace.": "rulesConfrontationReplacementError",
    "This Interzone choice is no longer available.": "rulesConfrontationReplacementMovedError",
    "Opening hands can only be drawn during the first Recovery start step.": "rulesOpeningHandStepError",
    "You have already drawn your opening hand.": "rulesOpeningHandAlreadyError",
    "Finish the opening-hand setup before playing.": "rulesPregameFinishError",
    "Draw your opening hand before taking a mulligan.": "rulesPregameDrawBeforeMulliganError",
    "Draw your opening hand before confirming readiness.": "rulesPregameDrawBeforeReadyError",
    "You have already taken your opening mulligan.": "rulesPregameMulliganUsedError",
    "You are already ready and cannot change your opening hand.": "rulesPregameAlreadyReadyError",
    "You are already ready.": "rulesPregameAlreadyReadyError",
    "Mulligans are only available before both players are ready.": "rulesPregameFinishError",
    "The opening-hand setup is no longer active.": "rulesPregameFinishError",
    "Both players must join before confirming readiness.": "rulesNeedPlayersError",
    "Your opening hand already contains a playable Manifestation.": "rulesMulliganNotRequiredError",
    "Opening-hand readiness is automatic.": "rulesOpeningAutomaticError",
    "Complete the required Recovery Mulligan before playing.": "rulesRecoveryMulliganPendingError",
    "No Recovery Mulligan is currently required.": "rulesRecoveryMulliganUnavailableError",
    "Your Recovery hand already contains a playable Manifestation.": "rulesRecoveryMulliganNotRequiredError",
    "Choose a valid Recovery effect.": "rulesRecoveryChoiceInvalidError",
    "Your Deck no longer has three cards to discard.": "rulesRecoveryChoiceShortDeckError",
    "This card did not meet its beginning-of-turn play condition.": "rulesPlayConditionError",
    "This card is no longer in its required zone.": "rulesRequiredZoneError",
    "This card can only be played in Support during a confrontation.": "rulesSupportTimingError",
    "A Support Manifestation can only be played from Hand during Reaction.": "rulesSupportHandTimingError",
    "This Manifestation does not have Support from Hand.": "rulesSupportHandMissingError",
    "This Manifestation does not currently have Support.": "rulesSupportMissingError",
  };
  return known[message] ? t(known[message]) : message;
}

function showTournamentPlayerAlert(message, isError = false) {
  const alert = $("#tournamentPlayerAlert");
  $("#tournamentPlayerAlertText").textContent = message;
  alert.classList.toggle("error", isError);
  alert.classList.remove("hidden");
  if (tournamentAlertTimer) clearTimeout(tournamentAlertTimer);
  tournamentAlertTimer = setTimeout(() => alert.classList.add("hidden"), 5200);
}

function tournamentStatusLabel(status) {
  return t(status === "active" ? "statusActive" : status === "ended" ? "statusEnded" : "statusLobby");
}

function tournamentPhaseLabel(phaseId) {
  return phaseLogLines({ phase: phaseId }).phase || phaseId || "—";
}

function tournamentRoleIcon(role) {
  if (role === "spectator") return `<svg viewBox="0 0 24 24"><path d="M3 12s3.5-5 9-5 9 5 9 5-3.5 5-9 5-9-5-9-5Z"/><circle cx="12" cy="12" r="2.5"/></svg>`;
  if (role === "judge") return `<svg viewBox="0 0 24 24"><path d="M12 3v17M6 6h12M4 20h16M7 6l-3 6h6L7 6Zm10 0-3 6h6l-3-6Z"/></svg>`;
  return `<svg viewBox="0 0 24 24"><circle cx="12" cy="7" r="3"/><path d="M6 20c.5-5 2.5-7 6-7s5.5 2 6 7"/></svg>`;
}

function tournamentLogTone(entry) {
  if (entry.type === "search_without_shuffle") return "critical";
  if (["rules_opening_defeat", "rules_recovery_defeat"].includes(entry.type)) return "critical";
  if (entry.type === "search_zone") return "warning";
  if (["rules_opening_mulligan_required", "rules_recovery_mulligan_required"].includes(entry.type)) return "warning";
  if (["create_tournament", "role_joined", "start_tournament", "end_tournament", "update_tournament_policy"].includes(entry.type)) return "system";
  if (["shuffle", "search_followed_by_shuffle", "draw", "draw_to_limit", "opening_hand_draw", "place_card", "move_card", "reveal", "scry", "mulligan", "rules_action_declared", "rules_action_triggered", "rules_priority_passed", "rules_priority_cancelled", "rules_priority_rolled", "rules_action_resolved", "rules_choice_resolved", "rules_phase_advanced", "rules_confrontation_compared", "rules_confrontation_cleanup", "rules_field_zone_changed"].includes(entry.type)) return "action";
  return "info";
}

function tournamentCardLabel(cardId) {
  const card = cardsById.get(cardId);
  return card ? `${String(card.collectionNumber || "").padStart(3, "0")} — ${cardName(cardId)}` : cardId;
}

function resolveTournamentCard(value) {
  const normalized = String(value || "").trim();
  const numberMatch = normalized.match(/^#?(\d{1,3})/);
  if (numberMatch) return cardsByNumber.get(Number(numberMatch[1]))?.id || null;
  const lower = normalized.toLocaleLowerCase();
  return [...cardsById.values()].find((card) => card.id === normalized || cardName(card.id).toLocaleLowerCase() === lower)?.id || null;
}

function tournamentRuleChip(cardId, removeAttrs) {
  return `<span class="tournament-rule-chip"><span>${esc(tournamentCardLabel(cardId))}</span><button type="button" ${removeAttrs} aria-label="${esc(`${t("remove")} ${cardName(cardId)}`)}">×</button></span>`;
}

function defaultHomeDeckPolicy() {
  return {
    bannedCardIds: [82, 128, 86].map((number) => cardsByNumber.get(number)?.id).filter(Boolean),
    restrictedGroups: [{
      id: "opening-tutors",
      name: "Opening tutors",
      cardIds: [267, 284, 281].map((number) => cardsByNumber.get(number)?.id).filter(Boolean),
    }],
  };
}

function renderHomeDeckPolicy() {
  if (!homePolicyDraft) homePolicyDraft = defaultHomeDeckPolicy();
  $("#tournamentCardOptions").innerHTML = [...cardsById.values()]
    .sort((a, b) => Number(a.collectionNumber) - Number(b.collectionNumber))
    .map((card) => `<option value="${esc(`${String(card.collectionNumber).padStart(3, "0")} — ${cardName(card.id)}`)}"></option>`)
    .join("");
  $("#homeBannedCardsList").innerHTML = homePolicyDraft.bannedCardIds
    .map((cardId, index) => tournamentRuleChip(cardId, `data-home-remove-banned="${index}"`)).join("");
  $("#homeRestrictedGroups").innerHTML = homePolicyDraft.restrictedGroups.map((group, groupIndex) => `
    <section class="restricted-group">
      <div class="restricted-group-head"><input value="${esc(group.name || `${t("restrictedGroup")} ${groupIndex + 1}`)}" data-home-restricted-name="${groupIndex}" aria-label="${esc(t("restrictedGroupName"))}"><button type="button" data-home-remove-group="${groupIndex}">${esc(t("remove"))}</button></div>
      <div class="tournament-rule-chips">${(group.cardIds || []).map((cardId, cardIndex) => tournamentRuleChip(cardId, `data-home-remove-card="${groupIndex}:${cardIndex}"`)).join("")}</div>
      <div class="tournament-rule-add"><input data-home-card-input="${groupIndex}" list="tournamentCardOptions" placeholder="${esc(t("cardNameOrNumber"))}"><button type="button" data-home-add-card="${groupIndex}">${esc(t("add"))}</button></div>
    </section>`).join("");
  $$('[data-home-remove-banned]').forEach((button) => button.onclick = () => {
    homePolicyDraft.bannedCardIds.splice(Number(button.dataset.homeRemoveBanned), 1);
    renderHomeDeckPolicy();
  });
  $$('[data-home-restricted-name]').forEach((input) => input.oninput = () => {
    homePolicyDraft.restrictedGroups[Number(input.dataset.homeRestrictedName)].name = input.value;
  });
  $$('[data-home-remove-group]').forEach((button) => button.onclick = () => {
    homePolicyDraft.restrictedGroups.splice(Number(button.dataset.homeRemoveGroup), 1);
    renderHomeDeckPolicy();
  });
  $$('[data-home-remove-card]').forEach((button) => button.onclick = () => {
    const [groupIndex, cardIndex] = button.dataset.homeRemoveCard.split(":").map(Number);
    homePolicyDraft.restrictedGroups[groupIndex].cardIds.splice(cardIndex, 1);
    renderHomeDeckPolicy();
  });
  $$('[data-home-add-card]').forEach((button) => button.onclick = () => {
    const groupIndex = Number(button.dataset.homeAddCard);
    const input = $(`[data-home-card-input="${groupIndex}"]`);
    const cardId = resolveTournamentCard(input.value);
    if (!cardId) return showToast(t("unknownCard"), true);
    if (!homePolicyDraft.restrictedGroups[groupIndex].cardIds.includes(cardId)) homePolicyDraft.restrictedGroups[groupIndex].cardIds.push(cardId);
    renderHomeDeckPolicy();
  });
}

function renderTournamentRules(tournament, organizer) {
  const panel = $("#tournamentRulesPanel");
  panel.classList.toggle("hidden", !organizer);
  if (!organizer) return;
  if (!tournamentPolicyDraft || !tournamentPolicyDirty) {
    tournamentPolicyDraft = JSON.parse(JSON.stringify(tournament.policy || { bannedCardIds: [], restrictedGroups: [] }));
  }
  $("#tournamentCardOptions").innerHTML = [...cardsById.values()]
    .sort((a, b) => Number(a.collectionNumber) - Number(b.collectionNumber))
    .map((card) => `<option value="${esc(`${String(card.collectionNumber).padStart(3, "0")} — ${cardName(card.id)}`)}"></option>`)
    .join("");
  $("#bannedCardsList").innerHTML = tournamentPolicyDraft.bannedCardIds.map((cardId, index) => tournamentRuleChip(cardId, `data-remove-banned="${index}"`)).join("");
  $("#restrictedGroups").innerHTML = tournamentPolicyDraft.restrictedGroups.map((group, groupIndex) => `
    <section class="restricted-group">
      <div class="restricted-group-head"><input value="${esc(group.name || `${t("restrictedGroup")} ${groupIndex + 1}`)}" data-restricted-name="${groupIndex}" aria-label="${esc(t("restrictedGroupName"))}"><button type="button" data-remove-restricted-group="${groupIndex}">${esc(t("remove"))}</button></div>
      <div class="tournament-rule-chips">${(group.cardIds || []).map((cardId, cardIndex) => tournamentRuleChip(cardId, `data-remove-restricted-card="${groupIndex}:${cardIndex}"`)).join("")}</div>
      <div class="tournament-rule-add"><input data-restricted-card-input="${groupIndex}" list="tournamentCardOptions" placeholder="${esc(t("cardNameOrNumber"))}"><button type="button" data-add-restricted-card="${groupIndex}">${esc(t("add"))}</button></div>
    </section>`).join("");

  $$('[data-remove-banned]').forEach((button) => button.onclick = () => {
    tournamentPolicyDraft.bannedCardIds.splice(Number(button.dataset.removeBanned), 1);
    tournamentPolicyDirty = true;
    renderTournamentRules(tournament, organizer);
  });
  $$('[data-restricted-name]').forEach((input) => input.oninput = () => {
    tournamentPolicyDraft.restrictedGroups[Number(input.dataset.restrictedName)].name = input.value;
    tournamentPolicyDirty = true;
  });
  $$('[data-remove-restricted-group]').forEach((button) => button.onclick = () => {
    tournamentPolicyDraft.restrictedGroups.splice(Number(button.dataset.removeRestrictedGroup), 1);
    tournamentPolicyDirty = true;
    renderTournamentRules(tournament, organizer);
  });
  $$('[data-remove-restricted-card]').forEach((button) => button.onclick = () => {
    const [groupIndex, cardIndex] = button.dataset.removeRestrictedCard.split(":").map(Number);
    tournamentPolicyDraft.restrictedGroups[groupIndex].cardIds.splice(cardIndex, 1);
    tournamentPolicyDirty = true;
    renderTournamentRules(tournament, organizer);
  });
  $$('[data-add-restricted-card]').forEach((button) => button.onclick = () => {
    const groupIndex = Number(button.dataset.addRestrictedCard);
    const input = $(`[data-restricted-card-input="${groupIndex}"]`);
    const cardId = resolveTournamentCard(input.value);
    if (!cardId) return showToast(t("unknownCard"), true);
    const group = tournamentPolicyDraft.restrictedGroups[groupIndex];
    if (!group.cardIds.includes(cardId)) group.cardIds.push(cardId);
    tournamentPolicyDirty = true;
    renderTournamentRules(tournament, organizer);
  });
  $("#tournamentRulesSaveBtn").disabled = tournament.status !== "lobby" || !tournamentPolicyDirty;
  $("#tournamentRulesStatus").textContent = tournament.status === "lobby" ? (tournamentPolicyDirty ? t("unsavedRules") : t("rulesSaved")) : t("rulesLocked");
}

function renderTournamentConsole() {
  const consoleScreen = $("#tournamentScreen");
  if (!consoleScreen || !latestState?.tournament) return;
  const tournament = latestState.tournament;
  const roleKey = connectionRole === "judge" ? "judge" : "organizer";
  $("#tournamentRoleLabel").textContent = t(roleKey);
  const stateBadge = $("#tournamentStateBadge");
  stateBadge.textContent = tournamentStatusLabel(tournament.status);
  stateBadge.className = `tournament-state-badge ${tournament.status}`;

  const organizer = connectionRole === "organizer";
  $("#tournamentCodeSection").classList.toggle("hidden", !organizer);
  $("#tournamentActions").classList.remove("hidden");
  $$(".organizer-only").forEach((element) => element.classList.toggle("hidden", !organizer));
  if (organizer && tournamentCodes) {
    const accessRoles = [
      ["player1", "playerOneCode", "playerAccessPermission", "#d3654a"],
      ["player2", "playerTwoCode", "playerAccessPermission", "#3fc9a8"],
      ["spectator", "spectatorCode", "spectatorAccessPermission", "#8bb5d8"],
      ["judge", "judgeCode", "judgeAccessPermission", "#d3a942"],
    ];
    $("#tournamentCodeGrid").innerHTML = accessRoles.map(([key, label, permission, accent]) => `
      <article class="tournament-access-card role-${key}" style="--access-accent:${accent}">
        <div class="tournament-access-head"><span class="tournament-role-icon">${tournamentRoleIcon(key)}</span><span class="tournament-access-label">${esc(t(label))}</span></div>
        <p class="tournament-access-permission">${esc(t(permission))}</p>
        <div class="tournament-access-row"><strong class="tournament-access-code">${esc(tournamentCodes[key])}</strong><button class="tournament-access-copy" data-tournament-copy="${esc(tournamentCodes[key])}" title="${esc(t("copy"))}" aria-label="${esc(`${t("copy")} ${t(label)}`)}">${esc(t("copy"))}</button></div>
      </article>`).join("");
    $$('[data-tournament-copy]').forEach((button) => {
      button.onclick = () => {
        navigator.clipboard?.writeText(button.dataset.tournamentCopy);
        button.textContent = t("copied");
        setTimeout(() => (button.textContent = t("copy")), 1200);
      };
    });
  }

  $("#tournamentSeats").innerHTML = tournament.seats.map((seat) => `
    <article class="tournament-seat">
      <span class="tournament-seat-number">P${seat.seat + 1}</span>
      <div class="tournament-seat-name"><strong>${esc(seat.name || t("seatAvailable"))}</strong><span>${esc(seat.deckReady ? t("deckReadyShort") : seat.name ? (seat.deckError || t("deckMissing")) : t("waitingForPlayer"))}</span></div>
      <span class="connection-dot${seat.connected ? " connected" : ""}" title="${esc(t(seat.connected ? "connected" : "disconnected"))}"></span>
    </article>`).join("");

  const counts = latestState.roleCounts || {};
  const phase = latestState.phaseTracker || { turn: 1 };
  const currentPhaseId = currentPhaseUi(phase).phase?.id || "recovery";
  $("#tournamentMetrics").innerHTML = `
    <button class="tournament-metric" data-presence-role="spectator" aria-expanded="${openPresenceRole === "spectator"}"><strong>${Number(counts.spectator || 0)}</strong><span>${esc(t("spectators"))}</span></button>
    <button class="tournament-metric" data-presence-role="judge" aria-expanded="${openPresenceRole === "judge"}"><strong>${Number(counts.judge || 0)}</strong><span>${esc(t("judges"))}</span></button>
    <div class="tournament-metric"><strong>${Number(phase.turn || 1)}</strong><span>${esc(t("turn"))}</span></div>
    <div class="tournament-metric"><strong>${esc(tournamentPhaseLabel(currentPhaseId))}</strong><span>${esc(t("phaseCurrent"))}</span></div>`;
  $$('[data-presence-role]').forEach((button) => button.onclick = () => {
    openPresenceRole = openPresenceRole === button.dataset.presenceRole ? null : button.dataset.presenceRole;
    renderTournamentConsole();
  });
  const presenceList = $("#tournamentPresenceList");
  const presenceNames = openPresenceRole ? (latestState.roleParticipants?.[openPresenceRole] || []) : [];
  presenceList.classList.toggle("hidden", !openPresenceRole);
  if (openPresenceRole) presenceList.innerHTML = `<strong>${esc(t(openPresenceRole === "judge" ? "connectedJudges" : "connectedSpectators"))}</strong>${presenceNames.length ? `<ul>${presenceNames.map((name) => `<li>${esc(name)}</li>`).join("")}</ul>` : `<p>${esc(t("nobodyConnected"))}</p>`}`;

  const activeAlerts = (tournament.auditAlerts || []).filter((alert) => alert.status !== "resolved");
  $("#tournamentAuditAlerts").innerHTML = activeAlerts.map((alert) => `<div class="tournament-alert-chip ${alert.severity === "critical" ? "" : "warning"}">${esc(alert.severity === "critical" ? t("unshuffledSearchAlert") : t("pendingShuffleAlert")).replace("{player}", esc(alert.actorName))}</div>`).join("");

  const canStart = tournament.status === "lobby" && tournament.seats.every((seat) => seat.connected && seat.deckReady);
  $("#tournamentStartBtn").disabled = !canStart;
  $("#tournamentStartBtn").classList.toggle("hidden", tournament.status !== "lobby");
  $("#tournamentEndBtn").disabled = tournament.status === "ended";
  $("#tournamentEndBtn").classList.toggle("hidden", tournament.status === "ended");
  $("#tournamentViewMatchBtn").disabled = tournament.status === "lobby";
  renderTournamentRules(tournament, organizer);

  const entries = latestState.recentLog || [];
  $("#tournamentLiveLog").innerHTML = entries.length ? [...entries].reverse().map((entry) => `
    <article class="tournament-log-entry" data-tone="${tournamentLogTone(entry)}">
      <div class="tournament-log-sequence">#${String(entry.sequence || 0).padStart(3, "0")}</div>
      <div class="tournament-log-content"><p>${formatLogEntry(entry, { html: true })}</p><small>${new Date(entry.timestamp * 1000).toLocaleTimeString()} · ${esc(t("turn"))} ${entry.turn || 1} · ${esc(tournamentPhaseLabel(entry.phase))}</small></div>
    </article>`).join("") : `<div class="tournament-log-empty">${esc(t("logEmpty"))}</div>`;
  wireLogCardNames($("#tournamentLiveLog"));
}

function phaseLogLabel(details) {
  const lines = phaseLogLines(details);
  return [lines.phase, lines.step].filter(Boolean).join("\n");
}

// Returns safe HTML (the actor's name is colour-coded), not plain text — the
// caller must NOT re-escape the result, only insert it directly.
function formatPlayerLogEntry(e) {
  const who = `<b style="color:${playerColor(e.actorId)}">${esc(e.actorName || e.actorId || "?")}</b>`;
  const d = e.details || {};
  switch (e.type) {
    case "draw":
    case "draw_to_limit":
    case "opening_hand_draw":
      return `${who} ${esc(t("plDrew"))} ${d.count}`;
    case "rules_opening_mulligan_required":
      return `${who} ${esc(t("rulesMulliganRequiredState"))}`;
    case "rules_recovery_mulligan_required":
      return `${who} ${esc(t("rulesRecoveryMulliganRequiredState"))}`;
    case "rules_opening_defeat":
      return d.draw ? esc(t("rulesOpeningMulliganDraw")) : `${who} ${esc(t("rulesMulliganFailedState"))}`;
    case "rules_recovery_defeat":
      return d.draw ? esc(t("rulesRecoveryMulliganDraw")) : `${who} ${esc(t("rulesRecoveryMulliganFailedState"))}`;
    case "rules_recovery_resumed":
      return `${who} ${esc(t("rulesRecoveryMulliganValidatedState"))}`;
    case "place_card":
      if (d.asSupport) return `${who} ${esc(t("plPlayedInSupport"))} ${namedOrUnknownCard(d.cardId)}`;
      return d.faceUp ? `${who} ${esc(t("plPlayed"))} ${namedOrUnknownCard(d.cardId)}` : `${who} ${esc(t("plPlayedFaceDown"))}`;
    case "move_card":
      return d.toZone === "graveyard"
        ? `${who} ${esc(t("plDiscarded"))} ${namedOrUnknownCard(d.cardId)} (${esc(t("plFrom"))} ${esc(t(d.fromZone))})`
        : `${who} ${esc(t("plPutInto"))} ${namedOrUnknownCard(d.cardId)} → ${esc(t(d.toZone))}`;
    case "remove_battlefield_item":
      return d.toZone === "graveyard"
        ? `${who} ${esc(t("plDiscarded"))} ${namedOrUnknownCard(d.cardId)} (${esc(t("plFrom"))} ${esc(t("battlefield"))})`
        : `${who} ${esc(t("plPutInto"))} ${namedOrUnknownCard(d.cardId)} → ${esc(t(d.toZone))}`;
    case "pass_phase": {
      if (d.action === "cancelled") return `${who} ${esc(t("plCancelledPhasePass"))}`;
      const lines = phaseLogLines(d);
      const step = lines.step ? `<br><span class="phase-log-step">${esc(lines.step)}</span>` : "";
      return d.action === "advanced"
        ? `${who} ${esc(t("plAdvancedPhase"))} ${esc(lines.phase)}${step}`
        : `${who} ${esc(t("plPassedPhase"))}${lines.phase ? ` — ${esc(lines.phase)}` : ""}${step}`;
    }
    case "rules_action_declared":
      return `${who} ${esc(t("plDeclaredStackAction"))} ${esc(d.label || "")}`;
    case "rules_action_triggered":
      return `${who} ${esc(t("plDeclaredStackAction"))} ${namedOrUnknownCard(d.source?.cardId)}${d.targets?.[0]?.kind === "player" ? ` → ${esc(rulesPlayerName(d.targets[0].playerId))}` : ""}`;
    case "rules_priority_passed":
      return `${who} ${esc(t("plPassedPriority"))}`;
    case "rules_priority_cancelled":
      return `${who} ${esc(t("plCancelledPriority"))}`;
    case "rules_action_resolved":
      return d.effectResult?.kind === "neutralize_stack_action" && d.effectResult.status === "neutralized"
        ? `${who} ${esc(t("plNeutralizedStackCard"))} ${namedOrUnknownCard(d.effectResult.cardId)}`
        : `${who} ${esc(t("plResolvedStackAction"))} ${esc(d.label || "")}`;
    case "rules_choice_resolved":
      if (d.kind === "stack_copy_targets") {
        return `${who} ${esc(t("plCopiedStackWill"))} ${namedOrUnknownCard(d.targetCardId)}`;
      }
      if (d.kind === "stack_counter_payment") {
        if (d.status === "paid") return `${who} ${esc(t("plPaidStackCounter"))} ${namedOrUnknownCard(d.targetCardId)}`;
        if (d.status === "cancelled") return `${who} ${esc(t("plLetStackEffectCancel"))} ${namedOrUnknownCard(d.targetCardId)}`;
        if (d.status === "neutralized") return `${who} ${esc(t("plLetStackCardNeutralize"))} ${namedOrUnknownCard(d.targetCardId)}`;
        return `${who} ${esc(t("plStackTargetGone"))} ${namedOrUnknownCard(d.targetCardId)}`;
      }
      if (d.kind === "chain_manifestation") {
        if (d.status === "declined") return `${who} ${esc(t("plRulesChainDeclined"))} ${namedOrUnknownCard(d.sourceCardId)}`;
        if (d.status === "chained") return `${who} ${esc(t("plRulesChained"))} ${namedOrUnknownCard(d.cardId)} ${esc(t("plRulesChainFrom"))} ${namedOrUnknownCard(d.sourceCardId)}`;
      }
      if (d.kind === "confrontation_destination") return `${who} ${esc(t("plChoseConfrontationDestination"))} ${namedOrUnknownCard(d.cardId)} → ${esc(t(d.destination === "interzone" ? "interzone" : "rulesDeckBottom"))}`;
      if (d.kind === "confrontation_replace_interzone") return `${who} ${esc(t("plReplacedInterzoneCard"))} ${namedOrUnknownCard(d.replacedCardId)} → ${esc(t("rulesDeckBottom"))}`;
      if (d.kind === "recovery_shared_choice") return d.option === "lose_points_10"
        ? `${who} ${esc(t("plRecoveryLostPoints"))}`
        : `${who} ${esc(rulesText("plRecoveryDiscardedDeck", { count: d.count || 0 }))}`;
      return `${who} ${esc(t("plDiscarded"))} ${namedOrUnknownCard(d.cardIds?.[0])}`;
    case "rules_confrontation_compared": {
      const totals = Object.entries(d.totals || {}).map(([id, value]) => `${esc(rulesPlayerName(id))} ${value}`).join(" · ");
      return d.stalemate
        ? `${esc(t("rulesConfrontationStalemate"))} · ${totals}`
        : `${esc(rulesText("rulesConfrontationWinner", { player: rulesPlayerName(d.winnerId) }))} · ${totals}`;
    }
    case "rules_confrontation_cleanup":
      if (d.stalemate) return esc(t("plMovedToStalemate"));
      return [
        `${esc(t("plConfrontationCardsMoved"))} ${esc(rulesPlayerName(d.winnerId))}`,
        d.supportExiled?.length ? esc(t("plSupportWinnerExiled")) : "",
        ...(d.supportResolved || []).filter((result) => result.kind === "opponent_vessel_score").map((result) => (
          esc(rulesText("plSupportVesselScore", {
            player: rulesPlayerName(result.playerId), delta: result.delta, score: result.score,
          }))
        )),
        ...(d.supportResolved || []).filter((result) => result.kind === "opponent_vessel").map((result) => (
          esc(rulesText("plRulesSupportOpponentVessel", { player: rulesPlayerName(result.playerId) }))
        )),
      ].filter(Boolean).join(" · ");
    case "rules_field_zone_changed":
      return `${who} ${esc(t("plEnteredConfrontation"))} ${namedOrUnknownCard(d.cardId)}`;
    case "rules_phase_advanced": {
      const lines = phaseLogLines(d);
      const step = lines.step ? `<br><span class="phase-log-step">${esc(lines.step)}</span>` : "";
      return `${who} ${esc(t("plAdvancedPhase"))} ${esc(lines.phase)}${step}`;
    }
    default:
      return "";
  }
}

let pendingPlayerLogFor = null;

function openPlayerLog(playerId) {
  pendingPlayerLogFor = playerId;
  send({ type: "request_log" });
}

function renderPlayerLog(entries, playerId) {
  const player = latestState.players[playerId];
  $("#playerLogHeading").textContent = player ? player.name : t("logHeader");
  const relevant = entries.filter((e) => e.actorId === playerId && isPlayerLogRelevant(e));
  $("#playerLogEntries").innerHTML = relevant.length
    ? relevant.map((e) => `<div class="log-entry"><div class="t">${new Date(e.timestamp * 1000).toLocaleString()}</div><div class="what">${formatPlayerLogEntry(e)}</div></div>`).join("")
    : `<p>${esc(t("logEmpty"))}</p>`;
  wirePlayerLogCardNames($("#playerLogEntries"));
  $("#playerLogPanel").classList.remove("hidden");
}

// Which players' mini activity feed is currently collapsed down to just its
// controls (the ▸/▾ toggle + the ··· button) — a per-player choice so an
// observer watching several players can collapse only the noisy ones.
const recentLogCollapsed = new Set();
let opponentHandHiddenByUser = false;

function renderOppRows() {
  const rows = $("#oppRows");
  const tracker = latestState.phaseTracker || { enabled: false, advanced: false, index: 0, turn: 1, passedPlayerIds: [] };
  const rules = latestState.rulesEngine;
  const passed = new Set(rules?.enabled ? (rules.priorityPasses || []) : (tracker.passedPlayerIds || []));
  const phaseLines = currentPhaseLines(tracker);
  const phaseLabel = [phaseLines.phase, phaseLines.step].filter(Boolean).join(" · ");
  const myPassIsActive = passed.has(myPlayerId);
  const canPassNow = !rules?.enabled || rules.priorityPlayerId === myPlayerId;
  rows.innerHTML = Object.values(latestState.players)
    .filter((p) => isObserver || p.id !== myPlayerId)
    .map((p) => {
      const handZone = p.zones.hand;
      const handCount = handZone.count !== undefined ? handZone.count : (handZone.cards || []).length;
      const viewHandTitle = isObserver ? `${p.name}: ${t("viewHand")} (${handCount})` : `${t("opponentHand")} ${handCount}`;
      const vesselPoints = receptaclePoints(p.zones.receptacle, p.score);
      const recent = (latestState.recentLog || []).filter((e) => e.actorId === p.id && isPlayerLogRelevant(e)).slice(-3);
      const collapsed = rules?.enabled ? !recentLogCollapsed.has(p.id) : recentLogCollapsed.has(p.id);
      const passedBadge = tracker.enabled && passed.has(p.id)
        ? `<span class="phase-player-pass-status">✓ ${esc(t("phasePassed"))}</span>`
        : "";
      const phaseControls = tracker.enabled && !rules?.enabled && !isObserver
        ? `<span class="opp-current-phase" title="${esc(phaseLabel)}"><span>${esc(phaseLines.phase)}</span>${phaseLines.step ? `<span class="opp-current-step">${esc(phaseLines.step)}</span>` : ""}</span>
           ${canPassNow ? `<button class="phase-inline-pass ${myPassIsActive ? "active" : ""}" data-pass-phase>${esc(t(rules?.enabled ? "passPriority" : (myPassIsActive ? "cancelPhasePass" : "passPhase")))}</button>` : ""}`
        : "";
      const recentHtml = `<div class="opp-recent-log${collapsed ? " collapsed" : ""}">
        <div class="opp-recent-log-controls">
          ${phaseControls}
          <button data-toggle-recent-log="${esc(p.id)}" title="${esc(t(collapsed ? "expand" : "collapse"))}">${collapsed ? "▸" : "▾"}</button>
          <button data-open-player-log="${esc(p.id)}">···</button>
        </div>
        <div class="opp-recent-log-lines">${recent.map((e) => `<div>${formatPlayerLogEntry(e)}</div>`).join("")}</div>
      </div>`;
      return `<div class="opp-info-row">
        <div class="opp-info-main">
          <span class="hand-mini"><span class="mini-back" style="--owner-color:${playerColor(p.id)}"></span><span>${esc(p.name)}</span>${passedBadge}</span>
          ${!isObserver ? `<button type="button" class="opponent-hand-visibility" data-toggle-opponent-hand title="${esc(t(opponentHandHiddenByUser ? "showOpponentHand" : "hideOpponentHand"))}" aria-label="${esc(t(opponentHandHiddenByUser ? "showOpponentHand" : "hideOpponentHand"))}" aria-pressed="${opponentHandHiddenByUser}">${eyeCardIconSvg(!opponentHandHiddenByUser)}</button>` : ""}
          <button class="hand-stack-btn" data-view-hand="${esc(p.id)}" title="${esc(viewHandTitle)}">
            <span class="hand-stack-icon" style="--owner-color:${playerColor(p.id)}">
              <span class="hand-stack-card"></span>
              <span class="hand-stack-card"></span>
              <span class="hand-stack-card"></span>
            </span>
            <span class="hand-stack-count">${handCount}</span>
          </button>
          <span class="opp-vessel-badge" title="${esc(t("receptacle"))}">${vesselPoints} ${esc(t("vesselPoints"))}</span>
        </div>
        ${p.activity ? `<div class="opp-activity">${esc(t("activity_" + p.activity))}</div>` : ""}
        ${recentHtml}
      </div>`;
    })
    .join("");
  $$("[data-view-hand]").forEach((btn) => {
    btn.onclick = (e) => {
      e.stopPropagation();
      openHandView(btn.dataset.viewHand);
    };
  });
  $$("[data-toggle-opponent-hand]").forEach((btn) => {
    btn.onclick = (event) => {
      event.stopPropagation();
      opponentHandHiddenByUser = !opponentHandHiddenByUser;
      renderOppRows();
    };
  });
  $$("[data-open-player-log]").forEach((btn) => {
    btn.onclick = (e) => {
      e.stopPropagation();
      openPlayerLog(btn.dataset.openPlayerLog);
    };
  });
  $$("[data-toggle-recent-log]").forEach((btn) => {
    btn.onclick = (e) => {
      e.stopPropagation();
      const pid = btn.dataset.toggleRecentLog;
      if (recentLogCollapsed.has(pid)) recentLogCollapsed.delete(pid);
      else recentLogCollapsed.add(pid);
      renderOppRows();
    };
  });
  wirePhasePassControls(rows);
  wirePlayerLogCardNames(rows);
  renderOpponentHandFan();
}

function renderOpponentHandFan() {
  const fan = $("#opponentHandFan");
  if (!fan) return;
  const opponent = !isObserver
    ? Object.values(latestState?.players || {}).find((player) => player.id !== myPlayerId)
    : null;
  if (!opponent || opponentHandHiddenByUser) {
    fan.innerHTML = "";
    fan.classList.add("hidden");
    return;
  }

  const hand = opponent.zones?.hand || {};
  const count = hand.count !== undefined ? hand.count : (hand.cards || []).length;
  const known = hand.cards !== undefined
    ? [...hand.cards]
    : [...(revealedHandCards.get(opponent.id) || [])].slice(0, count);
  const slots = Array.from({ length: count }, (_unused, index) => known[index] || null);
  fan.classList.toggle("hidden", count === 0);
  fan.setAttribute("aria-label", `${t("opponentHand")} ${count}`);
  fan.title = `${opponent.name}: ${t("viewHand")} (${count})`;
  fan.innerHTML = slots.map((cardId, index) => {
    const center = index - (count - 1) / 2;
    const rotate = Math.max(-15, Math.min(15, center * 3.5));
    const arc = Math.abs(center) * Math.abs(center) * 1.7;
    const offset = center * 45;
    if (!cardId) {
      return `<button type="button" class="opponent-hand-card is-hidden" data-opponent-hand-slot="${index}" style="--fan-rotate:${rotate}deg;--fan-arc:${arc}px;--fan-x:${offset}px;--fan-z:${index};--owner-color:${esc(playerColor(opponent.id))}" aria-label="${esc(t("cards"))}"></button>`;
    }
    return `<button type="button" class="opponent-hand-card is-known" data-opponent-hand-slot="${index}" data-opponent-hand-card="${esc(cardId)}" style="--fan-rotate:${rotate}deg;--fan-arc:${arc}px;--fan-x:${offset}px;--fan-z:${index};--owner-color:${esc(playerColor(opponent.id))}" title="${esc(cardName(cardId))}"><img src="${esc(cardImage(cardId))}" alt="${esc(cardName(cardId))}"></button>`;
  }).join("");
  fan.onclick = (event) => {
    const card = event.target.closest("[data-opponent-hand-card]")?.dataset.opponentHandCard;
    if (card) showInspect(card);
    else openHandView(opponent.id);
  };
  fan.querySelectorAll('[data-opponent-hand-card]').forEach((element) => {
    const cardId = element.dataset.opponentHandCard;
    element.onmouseenter = () => showCardPreview(cardId, element);
    element.onmouseleave = hideCardPreview;
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

// { cardId -> { kind: "move"|"play", toZone?, faceUp?, label } } — a choice
// made in the browser is staged here, not sent immediately: the card just
// greys out with an Undo, and nothing actually happens until Validate is
// clicked. Unlike the scry/reveal popup (send-immediately-with-undo), this
// window is often used to sort SEVERAL cards at once, so a review step
// before anything actually moves is worth the extra click. Reset when
// Search opens a browser (see wireZoneButtons) or the panel is closed —
// deliberately NOT reset by renderAll's live-refresh, so an unrelated
// server update elsewhere doesn't wipe out choices still pending Validate.
let pileBrowserStaged = new Map();

function dbCardHtml(ownerId, zone, cid) {
  const cardOwnerId = zoneCardOwner(ownerId, zone, cid);
  const style = `style="--owner-color:${playerColor(cardOwnerId)}"`;
  const staged = pileBrowserStaged.get(cid);
  if (staged) {
    return `<div class="db-card staged" ${style} title="${esc(cardName(cid))}">
      <img src="${esc(cardImage(cid))}" alt="${esc(cardName(cid))}">
      <div class="db-card-staged-label">
        <div>${esc(staged.label)}</div>
        <button class="db-card-undo-btn" data-undo-staged="${esc(cid)}">${esc(t("undo"))}</button>
      </div>
    </div>`;
  }
  return `<div class="db-card" ${style} title="${esc(cardName(cid))}" data-zone-card="${esc(ownerId)}:${esc(zone)}:${esc(cid)}" data-card-owner="${esc(cardOwnerId)}">
    <img src="${esc(cardImage(cid))}" alt="${esc(cardName(cid))}">
  </div>`;
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
  $("#deckBrowserCards").innerHTML = cards.map((cid) => dbCardHtml(ownerId, zone, cid)).join("") || `<p style="color:var(--muted);font-size:14px">${esc(t("cards"))}: 0</p>`;
  $("#deckBrowserValidateBtn").disabled = pileBrowserStaged.size === 0;
  $("#deckBrowserPanel").classList.remove("hidden");
  wirePileBrowserCards(ownerId, zone);
}

function stagePileBrowserChoice(ownerId, zone, cardId, entry) {
  pileBrowserStaged.set(cardId, entry);
  openPileBrowser(ownerId, zone);
}

// Left-click (not the app's usual right-click) opens the option menu here —
// this window is meant to be browsed/acted on quickly. Inspect fires
// immediately; every other option only stages a choice (see
// pileBrowserStaged) instead of sending it right away.
// A position:fixed clone that tracks the card while zoomed in, so it can
// never be clipped by the browser's own scroll container (see the CSS note
// on .db-card-hover-clone). Generic over the clone class name so the same
// helper covers both the pile browser's cards and the hand tray's.
function wireCardHoverZoom(el, cloneClassName) {
  let clone = null;
  let removalObserver = null;
  const clearClone = () => {
    if (clone) clone.remove();
    clone = null;
    if (removalObserver) removalObserver.disconnect();
    removalObserver = null;
  };
  el.addEventListener("mouseenter", () => {
    clearClone();
    const rect = el.getBoundingClientRect();
    clone = el.cloneNode(true);
    const rarityClasses = [...el.classList].filter((name) => name === "ko-rarity-card" || name.startsWith("rarity-"));
    clone.className = [cloneClassName, ...rarityClasses].join(" ");
    let cloneWidth = rect.width;
    let cloneHeight = rect.height;
    let cloneLeft = rect.left;
    let cloneTop = rect.top;
    if (cloneClassName === "hand-card-hover-clone") {
      cloneWidth = el.offsetWidth || rect.width;
      cloneHeight = el.offsetHeight || rect.height;
      cloneLeft = rect.left + rect.width / 2 - cloneWidth / 2;
      cloneTop = rect.top + rect.height / 2 - cloneHeight / 2;
    }
    clone.style.left = cloneLeft + "px";
    clone.style.top = cloneTop + "px";
    clone.style.width = cloneWidth + "px";
    clone.style.height = cloneHeight + "px";
    if (cloneClassName === "hand-card-hover-clone") {
      const margin = 22;
      const configuredScale = Number.parseFloat(
        getComputedStyle(document.documentElement).getPropertyValue("--hand-hover-scale")
      ) || 1.3;
      const scale = Math.max(.2, Math.min(
        configuredScale,
        (window.innerWidth - margin * 2) / Math.max(cloneWidth, 1),
        (window.innerHeight - margin * 2) / Math.max(cloneHeight, 1),
      ));
      const halfWidth = cloneWidth * scale / 2;
      const halfHeight = cloneHeight * scale / 2;
      const centerX = Math.min(
        window.innerWidth - margin - halfWidth,
        Math.max(margin + halfWidth, rect.left + rect.width / 2),
      );
      const centerY = Math.min(
        window.innerHeight - margin - halfHeight,
        Math.max(margin + halfHeight, rect.top + rect.height / 2 - 10),
      );
      clone.style.setProperty("--hand-hover-scale", scale.toFixed(3));
      clone.style.left = `${centerX - cloneWidth / 2}px`;
      // The zoom transform includes translateY(-10px); offset the base box so
      // the final scaled card, not merely its unscaled clone, is clamped.
      clone.style.top = `${centerY - cloneHeight / 2 + 10}px`;
    }
    document.body.appendChild(clone);
    // State updates rebuild card containers with innerHTML. Removing a
    // hovered source does not emit mouseleave, so clean up its fixed clone
    // when the source node is detached as well.
    removalObserver = new MutationObserver(() => {
      if (!el.isConnected) clearClone();
    });
    removalObserver.observe(el.parentNode, { childList: true });
    requestAnimationFrame(() => clone && clone.classList.add("zoomed"));
  });
  el.addEventListener("mousemove", (event) => {
    if (clone) updateRarityPointer(clone, event, true, el);
  });
  el.addEventListener("mouseleave", clearClone);
}

function wirePileBrowserCards(ownerId, zone) {
  $$("#deckBrowserCards [data-zone-card]").forEach((el) => {
    const cardId = el.dataset.zoneCard.split(":")[2];
    const cardOwnerId = el.dataset.cardOwner || ownerId;
    bindCardDragSource(el, { kind: "card", cardId, cardOwnerId, fromOwnerId: ownerId, fromZone: zone });
    wireCardHoverZoom(el, "db-card-hover-clone");
    const openMenu = (event) => {
      event.preventDefault();
      const items = [
        { label: t("inspect"), onSelect: () => showInspect(cardId) },
        copyCardMenuItem(cardId, ownerId, zone),
        { separator: true },
        { label: t("playFaceUp"), onSelect: () => stagePileBrowserChoice(ownerId, zone, cardId, { kind: "play", faceUp: true, label: t("battlefield") }) },
        { label: t("playFaceDown"), onSelect: () => stagePileBrowserChoice(ownerId, zone, cardId, { kind: "play", faceUp: false, label: t("battlefield") }) },
        { separator: true },
      ];
      ZONES.forEach((z) => {
        const toOwnerId = cardDestinationOwner(cardOwnerId, z);
        if (!toOwnerId || (toOwnerId === ownerId && z === zone)) return;
        items.push({
          label: cardDestinationLabel(cardOwnerId, z),
          onSelect: () => stagePileBrowserChoice(ownerId, zone, cardId, { kind: "move", toOwnerId, toZone: z, label: t(z) }),
        });
      });
      showContextMenu(event.clientX, event.clientY, items);
    };
    el.addEventListener("click", openMenu);
    el.addEventListener("contextmenu", openMenu);
  });
  $$("#deckBrowserCards [data-undo-staged]").forEach((btn) => {
    btn.onclick = (event) => {
      event.stopPropagation();
      pileBrowserStaged.delete(btn.dataset.undoStaged);
      openPileBrowser(ownerId, zone);
    };
  });
}

const DECK_BROWSER_SIZE_KEY = "ko_deck_browser_card_w";

function initPileBrowser() {
  $("#deckBrowserSliderLabel").textContent = t("deckBrowserSliderLabel");
  $("#deckBrowserCloseBtn").textContent = t("close");
  $("#deckBrowserValidateBtn").textContent = t("confirm");
  const saved = Number(localStorage.getItem(DECK_BROWSER_SIZE_KEY)) || 140;
  $("#deckBrowserSlider").value = saved;
  document.documentElement.style.setProperty("--db-card-w", saved + "px");
  $("#deckBrowserSlider").oninput = () => {
    document.documentElement.style.setProperty("--db-card-w", $("#deckBrowserSlider").value + "px");
    localStorage.setItem(DECK_BROWSER_SIZE_KEY, $("#deckBrowserSlider").value);
  };
  $("#deckBrowserCloseBtn").onclick = () => {
    $("#deckBrowserPanel").classList.add("hidden");
    pileBrowserStaged = new Map();
    setMyActivity(null);
  };
  $("#deckBrowserValidateBtn").onclick = () => {
    const { ownerId, zone } = $("#deckBrowserPanel").dataset;
    for (const [cardId, entry] of pileBrowserStaged) {
      if (entry.kind === "play") playFromZone(ownerId, zone, cardId, entry.faceUp);
      else send({ type: "move_card", fromOwnerId: ownerId, fromZone: zone, toOwnerId: entry.toOwnerId, toZone: entry.toZone, cardId });
    }
    pileBrowserStaged = new Map();
    $("#deckBrowserPanel").classList.add("hidden");
    setMyActivity(null);
  };
}

// Masks only the DISPLAYED code text, not data-copy-code — copying still
// works while hidden (e.g. paste it to a co-host over voice chat), it's just
// not shown on screen for anyone watching a stream/recording.
let codesHidden = false;

function renderHeaderCodes() {
  const codeItemHtml = (code, labelKey) => `<div class="code-item">
    <span class="code-item-label">${esc(t(labelKey))}</span>
    <button data-copy-code="${esc(code || "")}">${codesHidden ? "••••••" : esc(code || "")}</button>
  </div>`;
  if (connectionMode === "tournament") {
    $("#headerCodes").innerHTML = `<span class="count" id="headerCounts"></span>`;
  } else $("#headerCodes").innerHTML = isObserver
    ? `${codeItemHtml(codeObserver, "observerCode")}<span class="count" id="headerCounts"></span>`
    : `${codeItemHtml(codePlayer, "playerCode")}${codeItemHtml(codeObserver, "observerCode")}<span class="count" id="headerCounts"></span>`;
  $$("#headerCodes [data-copy-code]").forEach((btn) => {
    btn.onclick = () => {
      navigator.clipboard?.writeText(btn.dataset.copyCode);
      const original = btn.textContent;
      btn.textContent = t("copied");
      setTimeout(() => (btn.textContent = codesHidden ? "••••••" : original), 1200);
    };
  });
}

// Both toggles are deliberately transient (not saved to localStorage) — they
// exist for "I'm about to stream/record, hide sensitive stuff for a bit",
// not a persistent setting that could confusingly hide your own tools the
// next time you open the app normally.
let interfaceHidden = false;

// A little playing-card outline with an eye inside, open or shut — a custom
// SVG (not emoji) so the open/closed states render consistently everywhere,
// used only for hideInterfaceBtn (hideCodesBtn's plain eye/see-no-evil emoji
// pairing already reads fine on its own, no card framing needed there).
function eyeCardIconSvg(open) {
  const eye = open
    ? `<path d="M5 12 Q12 7.5 19 12 Q12 16.5 5 12 Z" fill="none" stroke="currentColor" stroke-width="1.4"/><circle cx="12" cy="12" r="2" fill="currentColor"/>`
    : `<path d="M5 12.5 Q12 15.5 19 12.5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>`;
  return `<svg viewBox="0 0 24 24" width="17" height="17"><rect x="3" y="2" width="18" height="20" rx="3" fill="none" stroke="currentColor" stroke-width="1.4"/>${eye}</svg>`;
}

function fullscreenIconSvg() {
  return `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 3H3v5M16 3h5v5M21 16v5h-5M8 21H3v-5"/></svg>`;
}

function rarityEffectsIconSvg() {
  return `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 2 1.3 5.1L18 9l-4.7 1.9L12 16l-1.3-5.1L6 9l4.7-1.9L12 2Z"/><path d="m19 14 .7 2.3L22 17l-2.3.7L19 20l-.7-2.3L16 17l2.3-.7L19 14Z"/></svg>`;
}

function initViewToggles() {
  $("#hideCodesBtn").onclick = () => {
    codesHidden = !codesHidden;
    $("#hideCodesBtn").textContent = codesHidden ? "🙈" : "👁";
    $("#hideCodesBtn").classList.toggle("active", codesHidden);
    $("#hideCodesBtn").title = t(codesHidden ? "showCodes" : "hideCodes");
    renderHeaderCodes();
    updateHeaderCounts();
  };
  $("#hideCodesBtn").textContent = "👁";
  $("#hideCodesBtn").title = t("hideCodes");

  $("#hideInterfaceBtn").onclick = () => {
    interfaceHidden = !interfaceHidden;
    $("#gameScreen").classList.toggle("interface-hidden", interfaceHidden);
    $("#hideInterfaceBtn").classList.toggle("active", interfaceHidden);
    $("#hideInterfaceBtn").title = t(interfaceHidden ? "showInterface" : "hideInterface");
    $("#hideInterfaceBtn").innerHTML = eyeCardIconSvg(!interfaceHidden);
  };
  $("#hideInterfaceBtn").innerHTML = eyeCardIconSvg(true);
  $("#hideInterfaceBtn").title = t("hideInterface");
  $("#rarityEffectsToggleBtn").innerHTML = rarityEffectsIconSvg();
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
    <span class="zone-card-kind" title="${esc(cardField(card, "typeLabel"))}">${kindLetter}</span>`;
}

function zoneCardRowHtml(ownerId, zone, zoneData, cardId, canAct) {
  const cardOwnerId = zoneData?.owners?.[cardId] || ownerId;
  const style = `style="--owner-color:${playerColor(cardOwnerId)}"`;
  if (!canAct) {
    return `<div class="zone-card-row" ${style}>${zoneCardKindBadgeHtml(cardId)}<span>${esc(cardName(cardId))}</span></div>`;
  }
  return `<div class="zone-card-row" ${style} data-zone-card="${esc(ownerId)}:${zone}:${esc(cardId)}" data-card-owner="${esc(cardOwnerId)}" data-preview-card="${esc(cardId)}">
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
      listHtml = `<div class="zone-list">${cards.map((cid) => zoneCardRowHtml(ownerId, zone, zoneData, cid, canAct)).join("") || `<div style="color:var(--muted);font-size:14px">(${t("cards")}: 0)</div>`}</div>`;
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
  const topCardOwnerId = topCardId ? (zoneData?.owners?.[topCardId] || ownerId) : null;
  const canDragTop = pilesLocked && !isObserver && ownerId === myPlayerId && ["graveyard", "exile", "receptacle"].includes(zone);
  const topCardHtml = topCardId
    ? `<img class="pile-top-card" src="${esc(cardImage(topCardId))}" alt="${esc(cardName(topCardId))}" title="${esc(cardName(topCardId))}"${canDragTop ? ` data-pile-top-card="${esc(topCardId)}" data-card-owner="${esc(topCardOwnerId)}"` : ""}>`
    : "";
  const cardPoints = receptacleCardPoints(zoneData);
  const bonusPoints = Number(score) || 0;
  const pointsBadge = zone === "receptacle"
    ? `<div class="pile-points"><span class="pile-card-points" title="${esc(t("vesselManifestationPoints"))}">${cardPoints} ${esc(t("vesselPoints"))}</span><span class="pile-bonus-points" title="${esc(t("vesselBonusPoints"))}">${bonusPoints >= 0 ? "+" : ""}${bonusPoints}</span></div>`
    : "";
  const zonePermission = zone === "graveyard" && ownerId === myPlayerId
    ? (latestState?.rulesEngine?.playPermissions || []).find((permission) => (
        permission.playerId === ownerId
        && permission.fromZone === zone
        && (zoneData.cards || []).includes(permission.cardId)
      ))
    : null;
  const permissionPlayable = Boolean(
    zonePermission
    && zonePermission.phaseIds?.includes(currentPhaseUi().phase?.id)
    && latestState?.rulesEngine?.priorityPlayerId === myPlayerId
  );
  const conditionalCard = zonePermission ? `<div role="button" tabindex="0"
      class="rules-zone-play-card${permissionPlayable ? " is-playable" : ""}"
      data-rules-zone-play-card="${esc(zonePermission.cardId)}"
      data-rules-zone-play-owner="${esc(ownerId)}"
      data-rules-zone-play-enabled="${permissionPlayable ? "true" : "false"}"
      title="${esc(t(permissionPlayable ? "rulesSupportFromLimbo" : "rulesSupportFromLimboHint"))}">
      <img src="${esc(cardImage(zonePermission.cardId))}" alt="${esc(cardName(zonePermission.cardId))}">
      <span>${esc(t("rulesSupportBadge"))}</span>
    </div>` : "";
  return `<div class="field-pile ${count === 0 ? "empty" : ""}"${dropAttr} data-field-pile="${esc(key)}" data-zone="${esc(zone)}" data-override-key="${esc(overrideKey)}" style="left:${pos.x}px;top:${pos.y}px;--owner-color:${playerColor(ownerId)}">
    ${scoreAdjust}
    <div class="pile-trigger" data-pile-trigger="${esc(key)}">
      <span class="pile-count">${count}</span>
      <div class="pile-card">${topCardHtml}</div>
      <span class="pile-label">${esc(t(zone))}</span>
      ${pointsBadge}
    </div>
    ${conditionalCard}
    <span class="pile-coords">${esc(zone)}: ${Math.round(rawPos.x)}, ${Math.round(rawPos.y)}</span>
    ${isOpen ? `<div class="zone-popover">${zoneBlockHtml(ownerId, zone, zoneData, canView, canAct)}</div>` : ""}
  </div>`;
}

function receptacleCardPoints(zoneData) {
  return (zoneData.cards || []).reduce((sum, cid) => {
    const card = cardsById.get(cid);
    return sum + (card?.type === "manifestation" ? card.points || 0 : 0);
  }, 0);
}

function receptaclePoints(zoneData, score) {
  return receptacleCardPoints(zoneData) + (Number(score) || 0);
}

// Pile SCREEN position, keyed by [viewer's own seat][pile owner's seat][zone]
// — see the derivation right after PILE_W/PILE_H below (moved there since it
// needs those + BOARD_SIZE, both declared further down this file).

// A local nudge on top of the table above — a personal display fix, never
// synced to the server or the other player. Keyed by "viewerSeat:ownerSeat:zone".
const PILE_OVERRIDES_KEY = "kartomantik.pileOverrides.v2";
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

// (The empirically-eyeballed mirror-axis marker that used to live here is
// gone: a TRUE 180° rotation — see rotateForSeat — needs no tuning at all,
// it's exact by construction around the board's own centre.)

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
  $$("[data-pile-top-card]").forEach((el) => {
    const pile = el.closest("[data-field-pile]");
    const [fromOwnerId, fromZone] = pile.dataset.fieldPile.split(":");
    bindCardDragSource(el, {
      kind: "card", cardId: el.dataset.pileTopCard, cardOwnerId: el.dataset.cardOwner || fromOwnerId,
      fromOwnerId, fromZone,
    });
  });
  $$("[data-rules-zone-play-card]").forEach((el) => {
    const cardId = el.dataset.rulesZonePlayCard;
    el.onclick = (event) => {
      event.stopPropagation();
      showInspect(cardId);
    };
    el.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      event.stopPropagation();
      showContextMenu(event.clientX, event.clientY, [
        { label: t("inspect"), onSelect: () => showInspect(cardId) },
      ]);
    });
    if (el.dataset.rulesZonePlayEnabled === "true") {
      bindCardDragSource(el, {
        kind: "card", cardId, cardOwnerId: myPlayerId,
        fromOwnerId: el.dataset.rulesZonePlayOwner, fromZone: "graveyard",
      });
    }
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
let handToolsOpen = false;

function applyHandVisibility(meId) {
  const rules = latestState?.rulesEngine;
  const mulliganReviewActive = Boolean(
    rules?.enabled
    && (
      (rules.openingMulliganRequiredPlayerIds || []).length
      || (rules.recoveryMulliganRequiredPlayerIds || []).length
    )
  );
  const collapsed = !meId || (handHiddenByUser && !mulliganReviewActive);
  $("#handArea").classList.toggle("hand-collapsed", collapsed);
  $("#myHandTray").classList.toggle("hidden", collapsed);
  $("#handResizeHandle").classList.toggle("hidden", collapsed);
  // the toolbar itself (and the hide/show toggle inside it) always stays put;
  // only its OTHER tool buttons collapse away with the tray
  $("#handToolbar").classList.toggle("hidden", !meId || !handToolsOpen);
  $("#handToolsToggleBtn").classList.toggle("hidden", !meId);
  $("#handToolsToggleBtn").setAttribute("aria-expanded", String(Boolean(meId && handToolsOpen)));
  $$(".hand-tool-btn").forEach((el) => {
    if (el.id === "handPickHint") return;
    el.classList.toggle("hidden", collapsed);
  });
  $$(".hand-tool-sep").forEach((el) => el.classList.toggle("hidden", collapsed));
  $("#handPickHint").classList.toggle("hidden", collapsed || !handPickMode);
  const visibilityButton = $("#handVisibilityBtn");
  visibilityButton.classList.toggle("hidden", !meId);
  visibilityButton.innerHTML = eyeCardIconSvg(!handHiddenByUser);
  visibilityButton.title = t(handHiddenByUser ? "showHand" : "hideHand");
  visibilityButton.setAttribute("aria-label", visibilityButton.title);
  visibilityButton.setAttribute("aria-pressed", String(handHiddenByUser));
  renderHandEssenceStrip();
}

function renderHandEssenceStrip() {
  const strip = $("#handEssenceStrip");
  if (!strip) return;
  const pool = new Map();
  (latestState?.tokens || []).forEach((token) => {
    const amount = Number(token.counters?.essence || 0);
    if (
      token.ownerId !== myPlayerId || !token.isEssence || token.isNeutralCounter
      || !token.temperament || amount <= 0
    ) return;
    pool.set(token.temperament, (pool.get(token.temperament) || 0) + amount);
  });
  strip.classList.toggle("hidden", !myPlayerId || pool.size === 0);
  strip.innerHTML = [...pool].map(([temperament, amount]) => (
    `<span class="hand-essence-chip" title="${esc(t("essence"))} ×${amount}"><img src="${esc(temperamentSymbol(temperament))}" alt="${esc(temperament)}"><b>${amount}</b></span>`
  )).join("");
  strip.setAttribute("aria-label", t("essence"));
}

function handCardIsPlayable(cardId) {
  const rules = latestState?.rulesEngine;
  const card = cardsById.get(cardId);
  if (!rules?.enabled || !card || isObserver || rules.pendingChoice) return false;
  if (rules_pregame_active_client() || rules_recovery_mulligan_active_client()) return false;
  if (rulesFirstManifestationActive()) {
    return (card.type === "manifestation" || card.placeholder)
      && !String(card.effect || "").includes("Cannot be played as First Manifestation")
      && !(rules.firstManifestationItemIds || {})[myPlayerId];
  }
  if (rules.priorityPlayerId !== myPlayerId) return false;
  if (rulesCardPlayRestrictedClient(cardId)) return false;
  const stackHasActions = (rules.actionStack || []).length > 0;
  const phaseId = currentPhaseUi().phase?.id;
  const responsePhase = card.type === "ephemeral_will"
    ? rulesEphemeralPhasesClient(card).includes(phaseId)
    : ["confrontation_reaction", "resolution_effects", "end_actions"].includes(phaseId);
  if (card.type === "ephemeral_will") {
    if (!responsePhase || !rulesCanAffordCard(cardId)) return false;
    const ability = (playedAbilitiesByCard.get(cardId) || [])[0];
    if (
      ability?.condition === "controller_lost_confrontation"
      && rules.confrontationResult?.loserId !== myPlayerId
    ) return false;
    const draft = ability ? buildRulesActionDraft({ cardId, zone: "hand" }, ability) : null;
    return !draft || Number(draft.targetRules?.min || 0) <= draft.structuredTargets.length;
  }
  if (card.type === "persistent_will") {
    const timingOk = phaseId === "end_actions"
      || (phaseId === "confrontation_before_revelation" && rulesBeforeRevelationPlayClient(card));
    return timingOk && !stackHasActions && rulesCanAffordCard(cardId);
  }
  if (card.type === "manifestation" && rulesEndPhaseInterzonePlayClient(card)) {
    if (phaseId === "end_actions") return !stackHasActions && rulesInterzoneHasRoomClient();
    if (phaseId !== "confrontation_reaction") return false;
  }
  return card.type === "manifestation"
    && phaseId === "confrontation_reaction"
    && rulesSupportFromHandAvailableClient(cardId);
}

function rulesEphemeralPhasesClient(card) {
  const effect = String(card?.effect || "");
  if (/only during the Reaction\b/.test(effect)) return ["confrontation_reaction"];
  if (/only during the Resolution\b/.test(effect)) return ["resolution_compare", "resolution_effects", "resolution_move"];
  if (/only before the Revelation\b/.test(effect)) return ["confrontation_before_revelation"];
  return ["confrontation_reaction", "resolution_effects", "end_actions"];
}

function rulesBeforeRevelationPlayClient(card) {
  return /\bcan be played before the Revelation\./.test(String(card?.effect || ""));
}

function rulesEndPhaseInterzonePlayClient(card) {
  return /^In the End Phase, [^\n]*? can be played into the Interzone\./m.test(String(card?.effect || ""));
}

function rulesInterzoneCapacityClient() {
  const bonus = (latestState?.battlefield || []).reduce((total, item) => {
    if (
      battlefieldItemControllerId(item) !== myPlayerId
      || !item.faceUp
      || item.effectsDisabled
      || item.fieldZone === "stalemate"
    ) return total;
    return total + (passiveEffectsByCard.get(item.cardId) || [])
      .filter((effect) => effect.kind === "extend_interzone")
      .reduce((sum, effect) => sum + Number(effect.value || 0), 0);
  }, 0);
  return 3 + Math.max(0, bonus);
}

function rulesInterzoneHasRoomClient() {
  return (latestState?.battlefield || []).filter((item) => (
    battlefieldItemControllerId(item) === myPlayerId
    && item.fieldZone === "interzone"
    && !item.stackedOn
  )).length < rulesInterzoneCapacityClient();
}

function rulesSupportFromHandAvailableClient(cardId) {
  const card = cardsById.get(cardId);
  const effect = String(card?.effect || "");
  if (/^Support(?: from hand)?[.;]/.test(effect)) return true;
  if ((latestState?.rulesEngine?.playPermissions || []).some((permission) => (
    permission.playerId === myPlayerId
    && permission.cardId === cardId
    && permission.fromZone === "hand"
    && permission.asSupport
    && Number(permission.turn || 0)
      === Number(latestState?.phaseTracker?.turn || 0)
  ))) return true;
  if (!effect.includes("an opponent has put a manifestation into Support from their Interzone")) return false;
  const turn = Number(latestState?.phaseTracker?.turn || 0);
  return (latestState?.rulesEngine?.supportEntries || []).some((entry) => (
    Number(entry.turn || 0) === turn
    && entry.controllerId !== myPlayerId
    && entry.fromZone === "interzone"
  ));
}

function rulesBattlefieldSupportAvailableClient(item) {
  const effect = String(cardsById.get(item?.cardId)?.effect || "");
  if (item?.fieldZone === "stalemate") {
    return /can enter in Support from the Stalemate Zone/i.test(effect);
  }
  if (item?.fieldZone !== "interzone") return false;
  return /^Support[.;]/.test(effect)
    || Number(item.supportUntilTurn || 0) === Number(latestState?.phaseTracker?.turn || 0)
    || item.canEnterSupport === true
    || (
      /as long as there are no Block counters on it, it has Support/i.test(effect)
      && Number((item.counters || {}).Block || 0) <= 0
    );
}

function rulesCardPlayRestrictedClient(cardId) {
  const rules = latestState?.rulesEngine;
  const turn = Number(latestState?.phaseTracker?.turn || 0);
  const restrictedCopies = (rules?.playRestrictions || []).filter((restriction) => (
    restriction.playerId === myPlayerId
    && restriction.cardId === cardId
    && Number(restriction.turn || 0) === turn
  )).length;
  if (!restrictedCopies) return false;
  const handCopies = (latestState?.players?.[myPlayerId]?.zones?.hand?.cards || [])
    .filter((id) => id === cardId).length;
  return handCopies <= restrictedCopies;
}

function rules_pregame_active_client() {
  const rules = latestState?.rulesEngine;
  return Boolean(
    rules?.enabled
    && latestState?.phaseTracker?.turn === 1
    && currentPhaseUi().phase?.id === "recovery_start"
  );
}

function rules_recovery_mulligan_active_client() {
  const rules = latestState?.rulesEngine;
  return Boolean(
    rules?.enabled
    && !latestState?.ended
    && currentPhaseUi().phase?.id === "recovery_draw"
    && rules.recoveryMulliganTurn === latestState?.phaseTracker?.turn
    && (rules.recoveryMulliganRequiredPlayerIds || []).length
  );
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
  const suspendedCards = (latestState?.rulesEngine?.suspendedCards || [])
    .filter((entry) => entry.playableByPlayerId === meId && entry.cardId);
  $("#handCardCount").textContent = `${cards.length} ${cards.length === 1 ? t("card") : t("cards")}`;
  const currentIds = new Set([...cards, ...suspendedCards.map((entry) => entry.cardId)]);
  if (cards.length === 0 && suspendedCards.length === 0) {
    tray.innerHTML = "";
    previousHandCardIds = currentIds;
    return;
  }
  const myRevealed = revealedHandCards.get(meId);
  tray.innerHTML = cards
    .map((cid, index) => {
      const isNew = !previousHandCardIds.has(cid);
      const wasRevealed = myRevealed && myRevealed.has(cid);
      const rarity = rarityForCard(meId, cid);
      const center = index - (cards.length - 1) / 2;
      const rotate = Math.max(-16, Math.min(16, center * 3.25));
      const arc = Math.abs(center) * Math.abs(center) * 1.35;
      const playable = handCardIsPlayable(cid);
      return `<div class="hand-card ${isNew ? "ko-pop-in " : ""}${playable ? "is-playable " : ""}${rarityClassAttr(rarity)}" data-hand-card="${esc(cid)}" data-hand-index="${index}" title="${esc(cardName(cid))}" style="--hand-rotate:${rotate}deg;--hand-arc:${arc}px;--hand-z:${index};${rarityCosmosStyle(cid)}">
      ${raritySurfaceMarkup(rarity, `<img src="${esc(cardImage(cid))}" alt="${esc(cardName(cid))}">`)}
      ${automationCoverageBadgeHtml(cid)}
      ${wasRevealed ? `<span class="hand-card-revealed-icon" title="${esc(t("revealHeader"))}">👁</span>` : ""}
    </div>`;
    })
    .join("") + suspendedCards.map((entry, index) => {
      const cardId = entry.cardId;
      return `<div class="hand-card is-playable" data-suspended-card="${esc(cardId)}" data-suspension-id="${esc(entry.id)}" title="${esc(`${cardName(cardId)} · ${t("rulesSuspended")}`)}" style="--hand-rotate:0deg;--hand-arc:0px;--hand-z:${cards.length + index};${rarityCosmosStyle(cardId)}">
        ${raritySurfaceMarkup(null, `<img src="${esc(cardImage(cardId))}" alt="${esc(cardName(cardId))}">`)}
        ${automationCoverageBadgeHtml(cardId)}
        <span class="hand-card-revealed-icon" title="${esc(t("rulesSuspended"))}">S</span>
      </div>`;
    }).join("");
  previousHandCardIds = currentIds;
  $$("[data-hand-card]").forEach((el) => {
    const cardId = el.dataset.handCard;
    el.onclick = () => {
      if (toggleRulesBoardPayment(Number(el.dataset.handIndex))) return;
      if (!handPickMode) return;
      const mode = handPickMode;
      handPickMode = null;
      updateHandToolbarUi();
      if (mode === "discard") send({ type: "move_card", fromZone: "hand", toZone: "graveyard", cardId });
    };
    bindCardDragSource(el, { kind: "card", cardId, handIndex: Number(el.dataset.handIndex), cardOwnerId: meId, fromOwnerId: meId, fromZone: "hand" });
    bindRarityPointer(el, false);
    wireCardHoverZoom(el, "hand-card-hover-clone");
    el.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      const items = [{ label: t("inspect"), onSelect: () => showInspect(cardId) }];
      const rulesItem = rulesActionContextItem({
        cardId, zone: "hand",
        handIndex: Number(el.dataset.handIndex),
      });
      if (rulesItem) items.push(rulesItem);
      if (
        latestState?.rulesEngine?.enabled
        && cardAutomationCoverage(cardId).status === "manual"
      ) {
        items.push({
          label: t("rulesPlayManually"),
          onSelect: () => playManuallyFromHand(cardId),
        });
      }
      items.push(
        copyCardMenuItem(cardId, meId, "hand"),
        { separator: true },
        { label: t("playFaceUp"), onSelect: () => playFromHand(cardId, true) },
        { label: t("playFaceDown"), onSelect: () => playFromHand(cardId, false) },
        { separator: true },
        { label: t("handDiscard"), onSelect: () => send({ type: "move_card", fromZone: "hand", toZone: "graveyard", cardId }) },
        { label: t("show"), onSelect: () => send({ type: "reveal", zone: "hand", cardId }) },
        { label: `${t("moveTo")} ${t("exile")}`, onSelect: () => send({ type: "move_card", fromZone: "hand", toZone: "exile", cardId }) },
        { label: t("moveToDeckTop"), onSelect: () => send({ type: "move_card", fromZone: "hand", toZone: "deck", cardId, position: "top" }) },
        { label: t("moveToDeckBottom"), onSelect: () => send({ type: "move_card", fromZone: "hand", toZone: "deck", cardId, position: "bottom" }) },
      );
      showContextMenu(event.clientX, event.clientY, items);
    });
  });
  $$("[data-suspended-card]").forEach((el) => {
    const cardId = el.dataset.suspendedCard;
    el.onclick = () => openRulesActionPanel({
      cardId, zone: "suspended", suspensionId: el.dataset.suspensionId,
    });
    wireCardHoverZoom(el, "hand-card-hover-clone");
    el.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      const items = [{ label: t("inspect"), onSelect: () => showInspect(cardId) }];
      const rulesItem = rulesActionContextItem({ cardId, zone: "suspended" });
      if (rulesItem) items.push(rulesItem);
      showContextMenu(event.clientX, event.clientY, items);
    });
  });
}

let handPickMode = null; // null | "discard"

function updateHandToolbarUi() {
  $("#handDiscardBtn").classList.toggle("active", handPickMode === "discard");
  const tray = $("#myHandTray");
  tray.classList.toggle("picking", Boolean(handPickMode));
  const hint = $("#handPickHint");
  hint.classList.toggle("hidden", !handPickMode);
  hint.textContent = handPickMode === "discard" ? t("pickCardToDiscard") : "";
}

function initHandToolbar() {
  $("#handToolsToggleBtn").onclick = () => {
    handToolsOpen = !handToolsOpen;
    applyHandVisibility(isObserver ? null : myPlayerId);
  };
  $("#handDrawOneBtn").onclick = () => send({ type: "draw", count: 1 });
  $("#handDrawHandBtn").onclick = () => send({ type: "draw_to_limit" });
  $("#handDiscardBtn").onclick = () => {
    handPickMode = handPickMode === "discard" ? null : "discard";
    updateHandToolbarUi();
  };
  $("#handShowBtn").onclick = () => send({ type: "reveal", zone: "hand" });
  $("#handDiscardRandomBtn").onclick = () => send({ type: "move_card", fromZone: "hand", toZone: "graveyard", random: true });
  $("#handMulliganBtn").onclick = () => {
    showConfirm(t("confirmMulligan"), () => send({ type: "mulligan" }));
  };
  $("#handVisibilityBtn").onclick = toggleHandHidden;
  $("#rulesOpeningHandBtn").onclick = () => {
    if ($("#rulesOpeningHandBtn").dataset.action === "import") $("#importDeckBtn").click();
    else send({ type: "draw_to_limit" });
  };
  $("#rulesPregameMulliganBtn").onclick = () => {
    const button = $("#rulesPregameMulliganBtn");
    const confirmKey = button.dataset.mulliganMode === "recovery"
      ? "rulesRecoveryMulliganConfirm"
      : button.dataset.mulliganRequired === "true"
        ? "rulesMulliganConfirm"
        : "rulesVoluntaryMulliganConfirm";
    showConfirm(t(confirmKey), () => send({ type: "mulligan" }));
  };
  $("#rulesPregameReadyBtn").onclick = () => {
    const rules = latestState?.rulesEngine;
    if ($("#rulesPregameReadyBtn").dataset.action === "deck") {
      const confirmed = (rules?.deckConfirmedPlayerIds || []).includes(myPlayerId);
      send({ type: "set_rules_deck_confirmed", confirmed: !confirmed });
    } else if ($("#rulesPregameReadyBtn").dataset.action === "opening") {
      send({ type: "set_rules_ready" });
    }
  };
}

function toggleHandHidden() {
  handHiddenByUser = !handHiddenByUser;
  applyHandVisibility(isObserver ? null : myPlayerId);
}

let pendingTriggeredPlacement = null;

function placementEntersSupport(payload, source) {
  if (payload.type === "set_rules_field_zone") return payload.fieldZone === "confrontation";
  if (payload.type !== "place_card" || !payload.faceUp || rulesFirstManifestationActive()) return false;
  if (cardsById.get(payload.cardId)?.type !== "manifestation") return false;
  if (currentPhaseUi().phase?.id !== "confrontation_reaction") return false;
  if (source?.zone === "hand") return rulesSupportFromHandAvailableClient(payload.cardId);
  return (latestState?.rulesEngine?.playPermissions || []).some((permission) => (
    permission.playerId === myPlayerId
    && permission.cardId === payload.cardId
    && permission.fromZone === source?.zone
    && permission.asSupport
  ));
}

function sendCardPlacement(payload, source, triggerTargets = []) {
  const playedAbility = (playedAbilitiesByCard.get(payload.cardId) || [])[0];
  if (!latestState?.rulesEngine?.enabled || !placementEntersSupport(payload, source)) {
    send({
      ...payload,
      ...(triggerTargets.length ? { triggerTargets } : {}),
      ...(triggerTargets[0]?.kind === "player" ? { triggerTargetPlayerId: triggerTargets[0].playerId } : {}),
    });
    return;
  }
  send({
    type: "declare_rules_action",
    label: rulesText("rulesDefaultSupport", { card: cardName(payload.cardId) }),
    kind: "play_card",
    asSupport: true,
    source: {
      cardId: source.cardId,
      zone: source.zone,
      itemId: source.itemId || null,
      containerId: source.containerId || payload.ownerId || myPlayerId,
    },
    target: "",
    targets: triggerTargets,
    costNote: "",
    paymentCardIds: [],
    ...(playedAbility?.id ? { abilityId: playedAbility.id } : {}),
    placement: {
      x: Number(payload.x) || 0,
      y: Number(payload.y) || 0,
    },
  });
}

function placementTargetTrigger(payload, source) {
  if (!payload.faceUp && payload.type !== "set_rules_field_zone") return null;
  if (!latestState?.rulesEngine?.enabled) return null;
  const events = ["enters_field"];
  if (placementEntersSupport(payload, source)) {
    events.push("enters_support", "enters_field_zone");
  }
  const playedAbility = placementEntersSupport(payload, source)
    ? (playedAbilitiesByCard.get(payload.cardId) || []).find(
        (ability) => Number(ability.targets?.max || 0) > 0,
      )
    : null;
  if (playedAbility) return playedAbility;
  return (triggeredAbilitiesByCard.get(payload.cardId) || []).find((ability) => (
    events.includes(ability.trigger?.event)
    && Number(ability.targets?.min || 0) > 0
  )) || null;
}

function closeRulesChoicePanel(force = false) {
  const mandatoryChoice = latestState?.rulesEngine?.pendingChoice;
  if (mandatoryChoice?.playerId === myPlayerId && !force) return;
  pendingTriggeredPlacement = null;
  $("#rulesChoicePanel").classList.add("hidden");
}

function renderRulesChoice() {
  const panel = $("#rulesChoicePanel");
  const closeButton = $("#rulesChoiceCloseBtn");
  const options = $("#rulesChoiceOptions");
  options.classList.remove(
    "has-destination-card", "has-order", "has-card-picker",
  );
  if (pendingTriggeredPlacement) {
    const { payload } = pendingTriggeredPlacement;
    $("#rulesChoiceHeading").textContent = t("rulesChooseTriggerTargetHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesChooseTriggerTargetText", { card: cardName(payload.cardId) });
    closeButton.classList.remove("hidden");
    options.innerHTML = Object.entries(latestState?.players || {}).map(([playerId, player]) => `
      <button type="button" class="rules-choice-player" data-rules-player-target="${esc(playerId)}" style="--player-tone:${esc(playerColor(playerId))}">
        ${esc(player.name || playerId)}
      </button>`).join("");
    $$('[data-rules-player-target]').forEach((button) => {
      button.onclick = () => {
        const placement = pendingTriggeredPlacement;
        pendingTriggeredPlacement = null;
        panel.classList.add("hidden");
        sendCardPlacement(placement.payload, placement.source, [{
          kind: "player", playerId: button.dataset.rulesPlayerTarget,
        }]);
      };
    });
    panel.classList.remove("hidden");
    return;
  }

  const choice = latestState?.rulesEngine?.pendingChoice;
  if (!choice || choice.playerId !== myPlayerId || isObserver) {
    panel.classList.add("hidden");
    return;
  }
  if (choice.kind === "chain_manifestation") {
    if (
      choice.fromZone === "hand"
      || !Array.isArray(choice.cardIds)
    ) {
      panel.classList.add("hidden");
      return;
    }
    closeButton.classList.add("hidden");
    options.classList.add("has-card-picker");
    $("#rulesChoiceHeading").textContent = t("rulesChainPileHeading");
    $("#rulesChoiceText").textContent = rulesText(
      "rulesChainPileText",
      {
        card: cardName(choice.sourceCardId),
        zone: t(choice.fromZone),
        count: choice.cardIds.length,
      },
    );
    options.innerHTML = `
      ${choice.cardIds.map((cardId) => `
        <button type="button" class="rules-choice-card" data-rules-chain-card="${esc(cardId)}">
          <img src="${esc(cardImage(cardId))}" alt="">
          <span>${esc(cardName(cardId))}</span>
        </button>`).join("")}
      ${choice.optional ? `
        <button type="button" class="rules-choice-destination rules-chain-decline" data-rules-chain-decline>
          <strong>${esc(t("rulesChainDecline"))}</strong>
          <span>${esc(t("rulesDeclineEffect"))}</span>
        </button>` : ""}`;
    $$("[data-rules-chain-card]").forEach((button) => {
      button.onclick = () => {
        const center = fieldCenterLogical();
        options.querySelectorAll("button").forEach((entry) => {
          entry.disabled = true;
        });
        send({
          type: "resolve_rules_choice",
          choiceId: choice.id,
          cardIds: [button.dataset.rulesChainCard],
          placement: {
            x: center.x - 75,
            y: center.y - 105,
          },
        });
      };
    });
    const declineButton = options.querySelector(
      "[data-rules-chain-decline]",
    );
    if (declineButton) {
      declineButton.onclick = () => {
        options.querySelectorAll("button").forEach((entry) => {
          entry.disabled = true;
        });
        send({
          type: "resolve_rules_choice",
          choiceId: choice.id,
          option: "decline",
        });
      };
    }
    panel.classList.remove("hidden");
    options.querySelector("button")?.focus();
    return;
  }
  if ([
    "stack_counter_payment", "effect_memory_payment", "effect_payment",
    "immediate_effect_payment", "stack_copy_targets", "trigger_targets",
  ].includes(choice.kind)) {
    panel.classList.add("hidden");
    return;
  }
  closeButton.classList.add("hidden");
  if (choice.kind === "deck_reorder") {
    $("#rulesChoiceHeading").textContent = t("rulesDeckReorderHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesDeckReorderText", {
      card: cardName(choice.sourceCardId),
    });
    options.innerHTML = `
      ${(choice.groups || []).map((group) => `
        <section class="rules-simultaneous-order" data-rules-deck-group="${esc(group.playerId)}">
          <strong>${esc(rulesPlayerName(group.playerId))}</strong>
          ${(group.cardIds || []).map((cardId, index) => `
            <div class="rules-choice-card rules-order-row">
              <img src="${esc(cardImage(cardId))}" alt="">
              <span>${esc(cardName(cardId))}</span>
              <select data-rules-deck-side="${esc(group.playerId)}:${index}">
                <option value="top">${esc(t("rulesDeckTop"))}</option>
                <option value="bottom">${esc(t("rulesDeckBottom"))}</option>
              </select>
              <input type="number" min="1" max="${group.cardIds.length}" value="${index + 1}" data-rules-deck-order="${esc(group.playerId)}:${index}" aria-label="${esc(t("rulesDeckOrder"))}">
            </div>`).join("")}
        </section>`).join("")}
      <button type="button" class="primary" id="rulesDeckReorderConfirm">${esc(t("confirm"))}</button>`;
    (choice.groups || []).forEach((group) => {
      const topCount = Number(group.topCount);
      const bottomCount = Number(group.bottomCount);
      if (!Number.isInteger(topCount) || !Number.isInteger(bottomCount)) return;
      (group.cardIds || []).forEach((_cardId, index) => {
        const select = document.querySelector(`[data-rules-deck-side="${CSS.escape(`${group.playerId}:${index}`)}"]`);
        if (select) select.value = index < topCount ? "top" : "bottom";
      });
    });
    $("#rulesDeckReorderConfirm").onclick = (event) => {
      const groups = (choice.groups || []).map((group) => {
        const entries = (group.cardIds || []).map((cardId, index) => {
          const key = `${group.playerId}:${index}`;
          return {
            cardId,
            side: document.querySelector(`[data-rules-deck-side="${CSS.escape(key)}"]`)?.value || "top",
            order: Number(document.querySelector(`[data-rules-deck-order="${CSS.escape(key)}"]`)?.value || index + 1),
          };
        });
        const ordered = (side) => entries.filter((entry) => entry.side === side)
          .sort((first, second) => first.order - second.order)
          .map((entry) => entry.cardId);
        return { playerId: group.playerId, top: ordered("top"), bottom: ordered("bottom") };
      });
      event.currentTarget.disabled = true;
      send({ type: "resolve_rules_choice", choiceId: choice.id, option: { groups } });
    };
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "guess_top_card") {
    $("#rulesChoiceHeading").textContent = t("rulesGuessTopCardHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesGuessTopCardText", {
      player: rulesPlayerName(choice.targetPlayerId),
    });
    options.innerHTML = `
      <label>${esc(t("type"))}<select id="rulesGuessType">${(choice.types || []).map((value) => `<option value="${esc(value)}">${esc(value === "will" ? t("will") : t("manifestation"))}</option>`).join("")}</select></label>
      <label>${esc(t("temperament"))}<select id="rulesGuessTemperament">${(choice.temperaments || []).map((value) => `<option value="${esc(value)}">${esc(t(value))}</option>`).join("")}</select></label>
      <label>${esc(t("rulesPowerOrCost"))}<select id="rulesGuessValue">${(choice.values || []).map((value) => `<option value="${value}">${value}</option>`).join("")}</select></label>
      <button type="button" class="primary" id="rulesGuessConfirm">${esc(t("confirm"))}</button>`;
    $("#rulesGuessConfirm").onclick = (event) => {
      event.currentTarget.disabled = true;
      send({
        type: "resolve_rules_choice",
        choiceId: choice.id,
        option: {
          type: $("#rulesGuessType").value,
          temperament: $("#rulesGuessTemperament").value,
          value: Number($("#rulesGuessValue").value),
        },
      });
    };
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "peek_top_card") {
    $("#rulesChoiceHeading").textContent = t("rulesPeekTopCardHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesPeekTopCardText", {
      card: cardName(choice.cardId),
    });
    options.innerHTML = `
      <button type="button" class="rules-choice-card" data-rules-peek-option="keep">
        <img src="${esc(cardImage(choice.cardId))}" alt="">
        <span>${esc(t("rulesKeepOnTop"))}</span>
      </button>
      <button type="button" class="rules-choice-destination" data-rules-peek-option="bottom">
        <strong>${esc(t("rulesDeckBottom"))}</strong>
      </button>`;
    $$("[data-rules-peek-option]").forEach((button) => {
      button.onclick = () => {
        button.disabled = true;
        send({
          type: "resolve_rules_choice",
          choiceId: choice.id,
          option: button.dataset.rulesPeekOption,
        });
      };
    });
    panel.classList.remove("hidden");
    return;
  }
  if (["optional_stack_action", "optional_trigger"].includes(choice.kind)) {
    $("#rulesChoiceHeading").textContent = t("rulesOptionalTriggerHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesOptionalTriggerText", {
      card: cardName(choice.sourceCardId),
    });
    options.innerHTML = `
      <button type="button" class="rules-choice-destination" data-rules-optional-trigger="accept">
        <strong>${esc(t("rulesUseEffect"))}</strong>
      </button>
      <button type="button" class="rules-choice-destination" data-rules-optional-trigger="decline">
        <strong>${esc(t("rulesDeclineEffect"))}</strong>
      </button>`;
    $$("[data-rules-optional-trigger]").forEach((button) => {
      button.onclick = () => {
        button.disabled = true;
        send({
          type: "resolve_rules_choice",
          choiceId: choice.id,
          option: button.dataset.rulesOptionalTrigger,
        });
      };
    });
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "score_delta_choice") {
    $("#rulesChoiceHeading").textContent = t("rulesScoreChoiceHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesScoreChoiceText", {
      player: rulesPlayerName(choice.targetPlayerId),
      value: choice.value,
    });
    options.innerHTML = `
      <button type="button" class="rules-choice-destination" data-rules-score-option="gain">
        <strong>${esc(t("rulesGainPoints"))}</strong>
      </button>
      <button type="button" class="rules-choice-destination" data-rules-score-option="lose">
        <strong>${esc(t("rulesLosePoints"))}</strong>
      </button>`;
    $$("[data-rules-score-option]").forEach((button) => {
      button.onclick = () => {
        button.disabled = true;
        send({
          type: "resolve_rules_choice",
          choiceId: choice.id,
          option: button.dataset.rulesScoreOption,
        });
      };
    });
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "support_return_order") {
    options.classList.add("has-order");
    $("#rulesChoiceHeading").textContent = t("rulesSupportOrderHeading");
    $("#rulesChoiceText").textContent = t("rulesSupportOrderText");
    const ordered = [...(choice.items || [])];
    const paintOrder = () => {
      options.innerHTML = `
        <div class="rules-simultaneous-order">
          ${ordered.map((item, index) => `
            <div class="rules-choice-card rules-order-row">
              <img src="${esc(cardImage(item.cardId))}" alt="">
              <span><strong>${index + 1}.</strong> ${esc(cardName(item.cardId))}</span>
              <button type="button" data-rules-support-order-up="${index}" aria-label="${esc(t("rulesMoveEarlier"))}" ${index === 0 ? "disabled" : ""}>↑</button>
              <button type="button" data-rules-support-order-down="${index}" aria-label="${esc(t("rulesMoveLater"))}" ${index === ordered.length - 1 ? "disabled" : ""}>↓</button>
            </div>`).join("")}
        </div>
        <button type="button" class="primary" id="rulesSupportOrderConfirm">${esc(t("confirm"))}</button>`;
      $$("[data-rules-support-order-up]").forEach((button) => {
        button.onclick = () => {
          const index = Number(button.dataset.rulesSupportOrderUp);
          [ordered[index - 1], ordered[index]] = [
            ordered[index], ordered[index - 1],
          ];
          paintOrder();
        };
      });
      $$("[data-rules-support-order-down]").forEach((button) => {
        button.onclick = () => {
          const index = Number(button.dataset.rulesSupportOrderDown);
          [ordered[index], ordered[index + 1]] = [
            ordered[index + 1], ordered[index],
          ];
          paintOrder();
        };
      });
      $("#rulesSupportOrderConfirm").onclick = (event) => {
        event.currentTarget.disabled = true;
        send({
          type: "resolve_rules_choice",
          choiceId: choice.id,
          cardIds: ordered.map((item) => item.itemId),
        });
      };
    };
    paintOrder();
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "optional_discard_draw") {
    $("#rulesChoiceHeading").textContent = t("rulesOptionalDiscardHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesOptionalDiscardText", {
      card: cardName(choice.sourceCardId),
      draw: choice.draw,
    });
    options.innerHTML = `
      <button type="button" class="rules-choice-destination" data-rules-optional-discard="accept">
        <strong>${esc(t("rulesDiscardAndDraw"))}</strong>
      </button>
      <button type="button" class="rules-choice-destination" data-rules-optional-discard="decline">
        <strong>${esc(t("rulesDeclineEffect"))}</strong>
      </button>`;
    $$("[data-rules-optional-discard]").forEach((button) => {
      button.onclick = () => {
        button.disabled = true;
        send({
          type: "resolve_rules_choice",
          choiceId: choice.id,
          option: button.dataset.rulesOptionalDiscard,
        });
      };
    });
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "points_or_weaken_first") {
    $("#rulesChoiceHeading").textContent = t("rulesWeakenChoiceHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesWeakenChoiceText", {
      card: cardName(choice.sourceCardId),
      points: choice.points,
      power: choice.power,
    });
    options.innerHTML = `
      <button type="button" class="rules-choice-destination" data-rules-weaken-option="lose_points">
        <strong>${esc(rulesText("rulesLosePointsAmount", { points: choice.points }))}</strong>
      </button>
      <button type="button" class="rules-choice-destination" data-rules-weaken-option="weaken_first">
        <strong>${esc(rulesText("rulesWeakenFirstAmount", { power: choice.power }))}</strong>
      </button>`;
    $$("[data-rules-weaken-option]").forEach((button) => {
      button.onclick = () => {
        button.disabled = true;
        send({ type: "resolve_rules_choice", choiceId: choice.id, option: button.dataset.rulesWeakenOption });
      };
    });
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "points_or_hand_limit") {
    $("#rulesChoiceHeading").textContent = t("rulesHandLimitChoiceHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesHandLimitChoiceText", {
      card: cardName(choice.sourceCardId),
      points: choice.points,
      limit: choice.limit,
    });
    options.innerHTML = `
      <button type="button" class="rules-choice-destination" data-rules-hand-limit-option="lose_points">
        <strong>${esc(rulesText("rulesLosePointsAmount", { points: choice.points }))}</strong>
      </button>
      <button type="button" class="rules-choice-destination" data-rules-hand-limit-option="limit_hand">
        <strong>${esc(rulesText("rulesLimitHandAmount", { limit: choice.limit }))}</strong>
      </button>`;
    $$("[data-rules-hand-limit-option]").forEach((button) => {
      button.onclick = () => {
        button.disabled = true;
        send({
          type: "resolve_rules_choice",
          choiceId: choice.id,
          option: button.dataset.rulesHandLimitOption,
        });
      };
    });
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "draw_replacement" || choice.kind === "hand_overflow") {
    const sourceCards = choice.kind === "draw_replacement"
      ? (choice.cardIds || [])
      : (latestState?.players?.[myPlayerId]?.zones?.hand?.cards || []);
    $("#rulesChoiceHeading").textContent = t(
      choice.kind === "draw_replacement"
        ? "rulesDrawReplacementHeading" : "rulesHandOverflowHeading"
    );
    $("#rulesChoiceText").textContent = rulesText(
      choice.kind === "draw_replacement"
        ? "rulesDrawReplacementText" : "rulesHandOverflowText",
      {
        card: cardName(choice.sourceCardId),
        count: choice.count,
        destination: choice.destination === "deck_bottom"
          ? t("rulesDeckBottom") : t("graveyard"),
      },
    );
    options.innerHTML = `
      <div class="rules-simultaneous-order">
        ${sourceCards.map((cardId, index) => `
          <label class="rules-choice-card rules-order-row">
            <input type="checkbox" value="${esc(cardId)}" data-rules-private-card="${index}">
            <img src="${esc(cardImage(cardId))}" alt="">
            <span>${esc(cardName(cardId))}</span>
          </label>`).join("")}
      </div>
      <button type="button" class="primary" id="rulesPrivateCardsConfirm">${esc(t("confirm"))}</button>`;
    $("#rulesPrivateCardsConfirm").onclick = (event) => {
      const selected = $$("[data-rules-private-card]:checked").map((input) => input.value);
      if (selected.length !== Number(choice.count || 0)) return;
      event.currentTarget.disabled = true;
      send({
        type: "resolve_rules_choice",
        choiceId: choice.id,
        cardIds: selected,
      });
    };
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "power_loss_distribution") {
    $("#rulesChoiceHeading").textContent = t("rulesPowerDistributionHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesPowerDistributionText", {
      card: cardName(choice.sourceCardId),
      count: choice.count,
    });
    const candidates = (choice.candidateItemIds || [])
      .map((itemId) => latestState?.battlefield?.find((item) => item.id === itemId))
      .filter(Boolean);
    options.innerHTML = `
      ${Array.from({ length: Number(choice.count || 0) }, (_, index) => `
        <label>${esc(rulesText("rulesPowerLossNumber", { number: index + 1 }))}
          <select data-rules-power-target="${index}">
            ${candidates.map((item) => `<option value="${esc(item.id)}">${esc(cardName(item.cardId))}</option>`).join("")}
          </select>
        </label>`).join("")}
      <button type="button" class="primary" id="rulesPowerDistributionConfirm">${esc(t("confirm"))}</button>`;
    $("#rulesPowerDistributionConfirm").onclick = (event) => {
      event.currentTarget.disabled = true;
      send({
        type: "resolve_rules_choice",
        choiceId: choice.id,
        option: {
          itemIds: $$("[data-rules-power-target]").map((select) => select.value),
        },
      });
    };
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "random_target_effect") {
    $("#rulesChoiceHeading").textContent = t("rulesRandomTargetHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesRandomTargetText", {
      card: cardName(choice.sourceCardId),
      roll: choice.roll,
    });
    const candidates = (choice.candidateItemIds || [])
      .map((candidateId) => latestState?.battlefield?.find((item) => item.id === candidateId))
      .filter(Boolean);
    options.innerHTML = candidates.map((item) => `
      <button type="button" class="rules-choice-card" data-rules-random-target="${esc(item.id)}">
        <img src="${esc(cardImage(item.cardId))}" alt="">
        <span>${esc(cardName(item.cardId))}</span>
      </button>`).join("");
    $$("[data-rules-random-target]").forEach((button) => {
      button.onclick = () => {
        button.disabled = true;
        send({
          type: "resolve_rules_choice",
          choiceId: choice.id,
          itemId: button.dataset.rulesRandomTarget,
        });
      };
    });
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "skip_confrontation_payment") {
    $("#rulesChoiceHeading").textContent = t("rulesSkipConfrontationHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesSkipConfrontationText", {
      card: cardName(choice.sourceCardId),
      points: choice.points,
    });
    options.innerHTML = `
      <button type="button" class="rules-choice-destination" data-rules-skip-option="lose_points">
        <strong>${esc(rulesText("rulesLosePointsAmount", { points: choice.points }))}</strong>
      </button>
      <button type="button" class="rules-choice-destination" data-rules-skip-option="skip">
        <strong>${esc(t("rulesSkipConfrontation"))}</strong>
      </button>`;
    $$("[data-rules-skip-option]").forEach((button) => {
      button.onclick = () => {
        button.disabled = true;
        send({
          type: "resolve_rules_choice",
          choiceId: choice.id,
          option: button.dataset.rulesSkipOption,
        });
      };
    });
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "confrontation_relocation") {
    $("#rulesChoiceHeading").textContent = t("rulesRelocationHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesRelocationText", {
      card: cardName(choice.sourceCardId),
    });
    options.innerHTML = `
      ${(choice.groups || []).map((group) => `
        <section class="rules-simultaneous-order">
          <strong>${esc(rulesPlayerName(group.playerId))} · ${esc(rulesText("rulesInterzoneSlots", { count: group.interzoneSlots }))}</strong>
          ${(group.itemIds || []).map((candidateId, index) => {
            const item = latestState?.battlefield?.find((entry) => entry.id === candidateId);
            return `<div class="rules-choice-card rules-order-row">
              <img src="${esc(cardImage(item?.cardId))}" alt="">
              <span>${esc(cardName(item?.cardId))}</span>
              <select data-rules-relocation="${esc(`${group.playerId}:${index}`)}">
                <option value="interzone">${esc(t("interzone"))}</option>
                <option value="deck">${esc(t("rulesDeckBottom"))}</option>
              </select>
              <input type="number" min="1" max="${group.itemIds.length}" value="${index + 1}" data-rules-relocation-order="${esc(`${group.playerId}:${index}`)}" aria-label="${esc(t("rulesDeckOrder"))}">
            </div>`;
          }).join("")}
        </section>`).join("")}
      <button type="button" class="primary" id="rulesRelocationConfirm">${esc(t("confirm"))}</button>`;
    $("#rulesRelocationConfirm").onclick = (event) => {
      const groups = (choice.groups || []).map((group) => {
        const entries = (group.itemIds || []).map((candidateId, index) => {
          const key = `${group.playerId}:${index}`;
          return {
            itemId: candidateId,
            destination: document.querySelector(`[data-rules-relocation="${CSS.escape(key)}"]`)?.value,
            order: Number(document.querySelector(`[data-rules-relocation-order="${CSS.escape(key)}"]`)?.value || index + 1),
          };
        });
        return {
          playerId: group.playerId,
          interzone: entries.filter((entry) => entry.destination === "interzone").map((entry) => entry.itemId),
          deckBottom: entries.filter((entry) => entry.destination === "deck")
            .sort((first, second) => first.order - second.order)
            .map((entry) => entry.itemId),
        };
      });
      event.currentTarget.disabled = true;
      send({
        type: "resolve_rules_choice",
        choiceId: choice.id,
        option: { groups },
      });
    };
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "suspend_hand_will") {
    $("#rulesChoiceHeading").textContent = t("rulesSuspendWillHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesSuspendWillText", {
      card: cardName(choice.sourceCardId),
    });
    options.innerHTML = (choice.cardIds || []).map((cardId, index) => `
      <button type="button" class="rules-choice-card" data-rules-suspend-card="${index}">
        <img src="${esc(cardImage(cardId))}" alt="">
        <span>${esc(cardName(cardId))}</span>
      </button>`).join("");
    $$("[data-rules-suspend-card]").forEach((button) => {
      button.onclick = () => {
        const cardId = choice.cardIds[Number(button.dataset.rulesSuspendCard)];
        if (!cardId) return;
        button.disabled = true;
        send({
          type: "resolve_rules_choice",
          choiceId: choice.id,
          cardIds: [cardId],
        });
      };
    });
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "simultaneous_stack_order") {
    options.classList.add("has-order");
    $("#rulesChoiceHeading").textContent = t("rulesSimultaneousOrderHeading");
    $("#rulesChoiceText").textContent = t("rulesSimultaneousOrderText");
    const ordered = [...(choice.actions || [])];
    const paintOrder = () => {
      options.innerHTML = `
        <div class="rules-simultaneous-order">
          ${ordered.map((action, index) => `
            <div class="rules-choice-card rules-order-row" data-rules-order-action="${esc(action.actionId)}">
              <img src="${esc(cardImage(action.cardId))}" alt="">
              <span><strong>${index + 1}.</strong> ${esc(action.label || cardName(action.cardId))}${action.immediate ? ` · ${esc(t("rulesImmediateLabel"))}` : ""}</span>
              <button type="button" data-rules-order-up="${index}" aria-label="${esc(t("rulesMoveEarlier"))}" ${index === 0 || (action.immediate && !ordered[index - 1]?.immediate) ? "disabled" : ""}>↑</button>
              <button type="button" data-rules-order-down="${index}" aria-label="${esc(t("rulesMoveLater"))}" ${index === ordered.length - 1 || (!action.immediate && ordered[index + 1]?.immediate) ? "disabled" : ""}>↓</button>
            </div>`).join("")}
        </div>
        <button type="button" class="primary" id="rulesSimultaneousOrderConfirm">${esc(t("confirm"))}</button>`;
      $$("[data-rules-order-up]").forEach((button) => {
        button.onclick = () => {
          const index = Number(button.dataset.rulesOrderUp);
          [ordered[index - 1], ordered[index]] = [ordered[index], ordered[index - 1]];
          paintOrder();
        };
      });
      $$("[data-rules-order-down]").forEach((button) => {
        button.onclick = () => {
          const index = Number(button.dataset.rulesOrderDown);
          [ordered[index], ordered[index + 1]] = [ordered[index + 1], ordered[index]];
          paintOrder();
        };
      });
      $("#rulesSimultaneousOrderConfirm").onclick = (event) => {
        event.currentTarget.disabled = true;
        send({
          type: "resolve_rules_choice",
          choiceId: choice.id,
          cardIds: ordered.map((action) => action.actionId),
        });
      };
    };
    paintOrder();
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "persist_first_manifestation") {
    $("#rulesChoiceHeading").textContent = t("rulesPersistChoiceHeading");
    $("#rulesChoiceText").textContent = t("rulesPersistChoiceText");
    const candidates = (choice.candidateItemIds || [])
      .map((itemId) => latestState?.battlefield?.find((item) => item.id === itemId))
      .filter(Boolean);
    options.innerHTML = candidates.map((item) => `
      <button type="button" class="rules-choice-card" data-rules-persist-item="${esc(item.id)}" title="${esc(cardName(item.cardId))}">
        <img src="${esc(cardImage(item.cardId))}" alt="">
        <span>${esc(cardName(item.cardId))}</span>
      </button>`).join("");
    $$("[data-rules-persist-item]").forEach((button) => {
      button.onclick = () => {
        button.disabled = true;
        send({
          type: "resolve_rules_choice",
          choiceId: choice.id,
          itemId: button.dataset.rulesPersistItem,
        });
      };
    });
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "effect_memory_return") {
    $("#rulesChoiceHeading").textContent = t("rulesMemoryReturnHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesMemoryReturnText", {
      card: cardName(choice.sourceCardId),
    });
    options.innerHTML = `
      <button type="button" class="rules-choice-destination" data-rules-memory-option="return">
        <strong>${esc(t("rulesReturnToHand"))}</strong>
        <span>${esc(t("rulesReturnToHandHint"))}</span>
      </button>
      <button type="button" class="rules-choice-destination" data-rules-memory-option="decline">
        <strong>${esc(t("rulesLeaveInLimbo"))}</strong>
        <span>${esc(t("rulesLeaveInLimboHint"))}</span>
      </button>`;
    $$("[data-rules-memory-option]").forEach((button) => {
      button.onclick = () => {
        button.disabled = true;
        send({
          type: "resolve_rules_choice",
          choiceId: choice.id,
          option: button.dataset.rulesMemoryOption,
        });
      };
    });
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "confrontation_destination") {
    $("#rulesChoiceHeading").textContent = t("rulesConfrontationDestinationHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesConfrontationDestinationText", {
      card: cardName(choice.cardId),
    });
    options.classList.add("has-destination-card");
    options.innerHTML = `
      <div class="rules-choice-destination-card" draggable="true" tabindex="0" role="img" aria-label="${esc(cardName(choice.cardId))}" title="${esc(cardName(choice.cardId))}">
        <img src="${esc(cardImage(choice.cardId))}" alt="${esc(cardName(choice.cardId))}">
      </div>
      <button type="button" class="rules-choice-destination" data-rules-destination="interzone">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 7 7-7 11-7-11 7-7Z"/><path d="M8.5 10h7M10 14h4"/></svg>
        <strong>${esc(t("interzone"))}</strong>
        <span>${esc(t("rulesConfrontationInterzoneHint"))}</span>
      </button>
      <button type="button" class="rules-choice-destination" data-rules-destination="deck_bottom">
        <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="3" width="11" height="15" rx="2"/><path d="M8 21h11a2 2 0 0 0 2-2V7M10 13l3 3 3-3M13 8v8"/></svg>
        <strong>${esc(t("rulesDeckBottom"))}</strong>
        <span>${esc(t("rulesConfrontationDeckHint"))}</span>
      </button>`;
    const resolveDestination = (button) => {
      if (!button || button.disabled) return;
      $$('[data-rules-destination]').forEach((candidate) => { candidate.disabled = true; });
      send({
        type: "resolve_rules_choice",
        choiceId: choice.id,
        option: button.dataset.rulesDestination,
      });
    };
    const card = options.querySelector(".rules-choice-destination-card");
    card.addEventListener("dragstart", (event) => {
      event.dataTransfer?.setData("text/plain", choice.itemId || choice.cardId || "confrontation-card");
      if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
      card.classList.add("is-dragging");
    });
    card.addEventListener("dragend", () => {
      card.classList.remove("is-dragging");
      $$('[data-rules-destination]').forEach((button) => button.classList.remove("is-drop-target"));
    });
    $$('[data-rules-destination]').forEach((button) => {
      button.onclick = () => resolveDestination(button);
      button.addEventListener("dragover", (event) => {
        event.preventDefault();
        if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
        button.classList.add("is-drop-target");
      });
      button.addEventListener("dragleave", () => button.classList.remove("is-drop-target"));
      button.addEventListener("drop", (event) => {
        event.preventDefault();
        button.classList.remove("is-drop-target");
        resolveDestination(button);
      });
    });
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "confrontation_replace_interzone") {
    $("#rulesChoiceHeading").textContent = t("rulesConfrontationReplaceHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesConfrontationReplaceText", {
      card: cardName(choice.cardId),
    });
    const candidates = (choice.candidateItemIds || [])
      .map((itemId) => latestState?.battlefield?.find((item) => item.id === itemId))
      .filter(Boolean);
    options.innerHTML = candidates.map((item) => `
      <button type="button" class="rules-choice-card" data-rules-replace-item="${esc(item.id)}" title="${esc(cardName(item.cardId))}">
        <img src="${esc(cardImage(item.cardId))}" alt="">
        <span>${esc(cardName(item.cardId))}</span>
      </button>`).join("");
    $$('[data-rules-replace-item]').forEach((button) => {
      button.onclick = () => {
        send({ type: "resolve_rules_choice", choiceId: choice.id, itemId: button.dataset.rulesReplaceItem });
        button.disabled = true;
      };
    });
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "recovery_shared_choice") {
    $("#rulesChoiceHeading").textContent = t("rulesRecoveryChoiceHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesRecoveryChoiceText", {
      card: cardName(choice.sourceCardId),
    });
    const available = new Set(choice.options || []);
    options.innerHTML = `
      ${available.has("discard_deck_bottom_3") ? `<button type="button" class="rules-choice-destination" data-rules-recovery-option="discard_deck_bottom_3">
        <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="3" width="11" height="15" rx="2"/><path d="M8 21h11a2 2 0 0 0 2-2V7M10 13l3 3 3-3M13 8v8"/></svg>
        <strong>${esc(t("rulesRecoveryDiscardBottom"))}</strong>
        <span>${esc(t("rulesRecoveryDiscardBottomHint"))}</span>
      </button>` : ""}
      ${available.has("lose_points_10") ? `<button type="button" class="rules-choice-destination" data-rules-recovery-option="lose_points_10">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v18M17 7.5c0-2-2-3.5-5-3.5S7 5.3 7 7.5 9 10.3 12 11s5 1.5 5 4-2 4.5-5 4.5-5-1.7-5-4"/></svg>
        <strong>${esc(t("rulesRecoveryLosePoints"))}</strong>
        <span>${esc(t("rulesRecoveryLosePointsHint"))}</span>
      </button>` : ""}`;
    $$('[data-rules-recovery-option]').forEach((button) => {
      button.onclick = () => {
        send({
          type: "resolve_rules_choice",
          choiceId: choice.id,
          option: button.dataset.rulesRecoveryOption,
        });
        button.disabled = true;
      };
    });
    panel.classList.remove("hidden");
    return;
  }
  const searching = Array.isArray(choice.candidateCardIds);
  const handManifestation = !searching && (choice.destination || choice.drawByBasePower || choice.destroyTargetItemId);
  const cards = searching
    ? choice.candidateCardIds
    : latestState?.players?.[myPlayerId]?.zones?.hand?.cards || [];
  $("#rulesChoiceHeading").textContent = t(
    searching ? "rulesChoiceSearchHeading" : handManifestation ? "rulesChoiceHandHeading" : "rulesChoiceDiscardHeading",
  );
  $("#rulesChoiceText").textContent = rulesText(
    searching
      ? "rulesChoiceSearchText"
      : handManifestation
        ? "rulesChoiceHandText"
        : Number(choice.drawAfter || 0) > 0 ? "rulesChoiceDiscardThenDrawText" : "rulesChoiceDiscardText",
    {
      card: cardName(choice.sourceCardId),
      count: choice.count,
      draw: Number(choice.drawAfter || 0),
    },
  );
  options.innerHTML = cards.map((cardId, index) => `
    <button type="button" class="rules-choice-card" data-rules-discard-index="${index}" title="${esc(cardName(cardId))}">
      <img src="${esc(cardImage(cardId))}" alt="">
      <span>${esc(cardName(cardId))}</span>
    </button>`).join("");
  if (Number(choice.count || 1) > 1 || choice.upTo) {
    const selected = new Set();
    const limit = Number(choice.count || 1);
    options.insertAdjacentHTML("beforeend", `
      <button type="button" class="primary" id="rulesDiscardConfirm" disabled>${esc(t("confirm"))}</button>`);
    const confirm = $("#rulesDiscardConfirm");
    const refresh = () => {
      confirm.disabled = choice.upTo ? selected.size > limit : selected.size !== limit;
    };
    if (choice.upTo) confirm.disabled = false;
    $$('[data-rules-discard-index]').forEach((button) => {
      button.onclick = () => {
        const index = Number(button.dataset.rulesDiscardIndex);
        if (selected.has(index)) selected.delete(index);
        else if (selected.size < limit) selected.add(index);
        button.classList.toggle("selected", selected.has(index));
        button.setAttribute("aria-pressed", selected.has(index) ? "true" : "false");
        refresh();
      };
    });
    confirm.onclick = () => {
      confirm.disabled = true;
      send({
        type: "resolve_rules_choice",
        choiceId: choice.id,
        cardIds: [...selected].map((index) => cards[index]).filter(Boolean),
      });
    };
    panel.classList.remove("hidden");
    return;
  }
  $$('[data-rules-discard-index]').forEach((button) => {
    button.onclick = () => {
      const cardId = cards[Number(button.dataset.rulesDiscardIndex)];
      if (!cardId) return;
      send({ type: "resolve_rules_choice", choiceId: choice.id, cardIds: [cardId] });
      button.disabled = true;
    };
  });
  panel.classList.remove("hidden");
}

function requestCardPlacement(payload, source = null) {
  const placementSource = source || {
    cardId: payload.cardId,
    zone: payload.fromZone || (payload.type === "set_rules_field_zone" ? "battlefield" : "hand"),
    itemId: payload.itemId || null,
  };
  const ability = placementTargetTrigger(payload, placementSource);
  if (!ability) {
    sendCardPlacement(payload, placementSource);
    return;
  }
  if (ability.targets?.kind !== "player") {
    beginRulesBoardPlacementTarget(payload, placementSource);
    return;
  }
  pendingTriggeredPlacement = { payload, source: placementSource, abilityId: ability.id };
  renderRulesChoice();
}

function playFromHand(cardId, faceUp) {
  const view = fieldCenterLogical();
  const center = rotateForSeat(view.x, view.y);
  requestCardPlacement({
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
      const panel = $("#deckBrowserPanel");
      // fresh open, or switching to a DIFFERENT pile: clear any pending
      // staged choices. Re-clicking Search on the pile already open keeps them.
      if (panel.classList.contains("hidden") || panel.dataset.ownerId !== ownerId || panel.dataset.zone !== zone) {
        pileBrowserStaged = new Map();
      }
      send({ type: "search_zone", ownerId, zone });
      setMyActivity("search");
      openPileBrowser(ownerId, zone);
    };
  });
  // scoped to the small inline pile lists — the deck/pile BROWSER modal wires
  // its own (larger) copies of these same [data-zone-card] cards itself (see
  // wirePileBrowserCards), since it isn't re-rendered by this function
  $$(".zone-list [data-zone-card]").forEach((el) => {
    const [ownerId, zone, cardId] = el.dataset.zoneCard.split(":");
    const cardOwnerId = el.dataset.cardOwner || ownerId;
    bindCardDragSource(el, { kind: "card", cardId, cardOwnerId, fromOwnerId: ownerId, fromZone: zone });
    el.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      const items = [
        { label: t("inspect"), onSelect: () => showInspect(cardId) },
        copyCardMenuItem(cardId, ownerId, zone),
        { separator: true },
        { label: t("playFaceUp"), onSelect: () => playFromZone(ownerId, zone, cardId, true) },
        { label: t("playFaceDown"), onSelect: () => playFromZone(ownerId, zone, cardId, false) },
        { separator: true },
      ];
      ZONES.forEach((z) => {
        const toOwnerId = cardDestinationOwner(cardOwnerId, z);
        if (!toOwnerId || (toOwnerId === ownerId && z === zone)) return;
        items.push({
          label: cardDestinationLabel(cardOwnerId, z),
          onSelect: () => send({ type: "move_card", fromOwnerId: ownerId, fromZone: zone, toOwnerId, toZone: z, cardId }),
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
  const center = rotateForSeat(view.x, view.y);
  requestCardPlacement({
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
//
// Uses elementsFromPoint (plural), not a single elementFromPoint passed in —
// re-dragging a card that's already on the field (e.g. nudging an
// already-stacked card to adjust its overlap) never moves its real element,
// only a ghost clone follows the cursor (see bindCardDragSource), so the
// card's own stale pre-drag position is often still sitting right under the
// drop point. A single topmost hit would find itself there, get excluded,
// and fall through to unstacking instead of re-stacking — walking the full
// stack of elements at that point lets it see past its own leftover spot to
// whatever anchor is genuinely underneath.
function stackAnchorAt(clientX, clientY, excludeItemId) {
  for (const el of document.elementsFromPoint(clientX, clientY)) {
    const cardEl = el.closest(".bf-card");
    if (!cardEl || cardEl.dataset.itemId === excludeItemId) continue;
    const anchorItem = latestState.battlefield.find((it) => it.id === cardEl.dataset.itemId);
    if (!anchorItem || anchorItem.stackedOn) continue;
    return { anchorEl: cardEl, anchorId: anchorItem.id };
  }
  return null;
}

// Offset of a new card's top-left from the anchor's top-left in screen-space
// units. It deliberately stays viewer-independent: a card magnetised below
// its anchor must remain below it for both players, even though their board
// backgrounds use opposite perspectives.
function stackOffsetFrom(anchorEl, clientX, clientY) {
  const rect = anchorEl.getBoundingClientRect();
  return {
    x: (clientX - rect.left) / zoomLevel - 75,
    y: (clientY - rect.top) / zoomLevel - 105,
  };
}

function resolveDrop(ctx, clientX, clientY) {
  const el = document.elementFromPoint(clientX, clientY);
  if (!el) return;
  const zoneEl = el.closest("[data-drop-zone]");
  const fieldEl = el.closest("#battlefieldWrap");
  const handEl = el.closest("#myHandTray");

  if (ctx.kind === "battlefield") {
    const battlefieldItem = latestState?.battlefield?.find((item) => item.id === ctx.itemId);
    if (zoneEl) {
      const [toOwnerId, toZone] = zoneEl.dataset.dropZone.split(":");
      if (battlefieldItem && !battlefieldItem.isTokenCard && !cardDestinationAllowed(battlefieldItem.ownerId, toOwnerId, toZone)) {
        showToast(t("invalidCardDestination"), true);
        return;
      }
      send({ type: "remove_battlefield_item", itemId: ctx.itemId, toOwnerId, toZone });
    } else if (handEl) {
      send({ type: "remove_battlefield_item", itemId: ctx.itemId, toOwnerId: myPlayerId, toZone: "hand" });
    } else if (fieldEl) {
      const anchor = stackAnchorAt(clientX, clientY, ctx.itemId);
      if (anchor) {
        const offset = stackOffsetFrom(anchor.anchorEl, clientX, clientY);
        send({ type: "move_battlefield_item", itemId: ctx.itemId, stackOnId: anchor.anchorId, offsetX: offset.x, offsetY: offset.y });
      } else {
        const rect = fieldEl.getBoundingClientRect();
        const logical = rotateForSeat((clientX - rect.left - panX) / zoomLevel - 75, (clientY - rect.top - panY) / zoomLevel - 105, PILE_W, PILE_H);
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
  if (
    pendingRulesBoardFlow?.mode === "action"
    && pendingRulesBoardFlow.stage === "payment"
    && ctx.fromZone === "hand"
    && pendingRulesBoardFlow.draft.manifestations.some((entry) => entry.index === ctx.handIndex)
  ) {
    toggleRulesBoardPayment(ctx.handIndex);
    return;
  }
  if (pendingRulesBoardFlow?.mode === "chain") {
    const choice = rulesChainChoice();
    if (!choice || ctx.fromOwnerId !== myPlayerId || ctx.fromZone !== choice.fromZone || !rulesChainCardEligible(ctx.cardId, choice)) {
      showToast(t("rulesChainInvalidCard"), true);
      return;
    }
    if (!fieldEl) {
      showToast(t("rulesChainDropInstruction"), true);
      return;
    }
    const rect = fieldEl.getBoundingClientRect();
    const logical = rotateForSeat(
      (clientX - rect.left - panX) / zoomLevel - 75,
      (clientY - rect.top - panY) / zoomLevel - 105,
      PILE_W, PILE_H,
    );
    send({
      type: "resolve_rules_choice",
      choiceId: choice.id,
      cardIds: [ctx.cardId],
      placement: { x: logical.x, y: logical.y },
    });
    closeRulesBoardFlow();
    return;
  }
  const cardOwnerId = ctx.cardOwnerId || ctx.fromOwnerId;
  if (zoneEl) {
    const [toOwnerId, toZone] = zoneEl.dataset.dropZone.split(":");
    if (toOwnerId === ctx.fromOwnerId && toZone === ctx.fromZone) return;
    if (!cardDestinationAllowed(cardOwnerId, toOwnerId, toZone)) {
      showToast(t("invalidCardDestination"), true);
      return;
    }
    send({ type: "move_card", fromOwnerId: ctx.fromOwnerId, fromZone: ctx.fromZone, toOwnerId, toZone, cardId: ctx.cardId });
  } else if (handEl) {
    if (ctx.fromZone === "hand") reorderHandDrop(ctx.cardId, clientX);
    else if (cardDestinationAllowed(cardOwnerId, myPlayerId, "hand")) send({ type: "move_card", fromOwnerId: ctx.fromOwnerId, fromZone: ctx.fromZone, toOwnerId: myPlayerId, toZone: "hand", cardId: ctx.cardId });
    else showToast(t("invalidCardDestination"), true);
  } else if (fieldEl) {
    const rect = fieldEl.getBoundingClientRect();
    const logical = rotateForSeat((clientX - rect.left - panX) / zoomLevel - 75, (clientY - rect.top - panY) / zoomLevel - 105, PILE_W, PILE_H);
    const anchor = stackAnchorAt(clientX, clientY, null);
    const card = cardsById.get(ctx.cardId);
    if (latestState?.rulesEngine?.enabled && ctx.fromZone === "hand") {
      if (["ephemeral_will", "persistent_will"].includes(card?.type)) {
        beginRulesBoardAction({
          cardId: ctx.cardId,
          zone: "hand",
          handIndex: ctx.handIndex,
          placement: { x: logical.x, y: logical.y },
        });
        return;
      }
      const firstManifestationPlaceholder = rulesFirstManifestationActive() && Boolean(card?.placeholder);
      if ((card?.type !== "manifestation" && !firstManifestationPlaceholder) || !handCardIsPlayable(ctx.cardId)) {
        showToast(t("rulesBoardCardNotPlayable"), true);
        return;
      }
    }
    const faceUp = latestState?.rulesEngine?.enabled && rulesFirstManifestationActive() ? false : true;
    const requestDraggedPlacement = (payload) => {
      const source = { cardId: ctx.cardId, zone: ctx.fromZone, handIndex: ctx.handIndex };
      if (!beginRulesBoardPlacementTarget(payload, source)) requestCardPlacement(payload, source);
    };
    if (anchor) {
      // x/y still sent as a fallback position (this is a BRAND NEW item, so
      // there's no earlier "before it was stacked" position to freeze on)
      const offset = stackOffsetFrom(anchor.anchorEl, clientX, clientY);
      requestDraggedPlacement({ type: "place_card", ownerId: ctx.fromOwnerId, fromZone: ctx.fromZone, cardId: ctx.cardId, faceUp, x: logical.x, y: logical.y, stackOnId: anchor.anchorId, offsetX: offset.x, offsetY: offset.y });
    } else {
      requestDraggedPlacement({ type: "place_card", ownerId: ctx.fromOwnerId, fromZone: ctx.fromZone, cardId: ctx.cardId, faceUp, x: logical.x, y: logical.y });
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
// a fixed 1741x1549 layer (matching the playmat art's native resolution) that
// is translated/scaled as one unit. There is no native scrolling anywhere —
// the wheel zooms (anchored on the cursor) and dragging empty field space pans.

const BOARD_WIDTH = 1741;
const BOARD_HEIGHT = 1549;
let zoomLevel = 1;
let panX = 0;
let panY = 0;

// ---------------------------------------------------------------- seat-based display flip
// Each player should see their OWN side near the bottom of the screen and
// their opponent near the top — AND the printed mat itself needs to make
// sense from wherever they're sitting, since it isn't left-right symmetric
// (The Stack and the Stalemate Zone sit on opposite sides). The fix for both
// is the SAME single idea, applied consistently everywhere: for the seat-1
// viewer, the whole table — background, piles, battlefield cards
// (incl. token-cards), tokens, draw strokes, all of it — is rotated a full
// 180°, exactly like a real player physically walking around to the other
// side of a real table would see the same table rotated.
//
// - The background image is a separate layer (.battlefield-bg.rotated) that
//   gets an actual CSS transform: rotate(180deg) — never touches the
//   cards/piles/tokens layered on top, which are positioned independently.
// - Fixed PILE slots use the independently calibrated coordinates in
//   PILE_SCREEN_POS for each viewer and owner pair.
// - rotateForSeat() applies it to everything a player places freely:
//   battlefield cards, tokens, and draw strokes.
//
// An EARLIER version of this only mirrored y for rotateForSeat's free-
// floating objects (x untouched), on the theory that "nothing forces them to
// match a printed slot, only y matters for keeping your own side near the
// bottom." That was wrong the moment the mat stopped being shown identically
// to both seats: play a card on the right as P1 (near the Stalemate Zone)
// and a y-only mirror leaves it on the right for P2 too — which is now The
// Stack, since that side rotated. Only a full rotation stays consistent with
// a background that's actually rotating. Stacking offsets are deliberately
// exempt: they describe one card relative to another and must look identical
// to both viewers (see stackOffsetFrom/stackedScreenPos).
//
// rotateForSeat's one extra rule: a stored (x,y) is always a box's CSS
// top-left, never a bare point. Rotating a box's top-left 180° around the
// board's centre lands on the OPPOSITE corner unless the box's own
// width/height is subtracted back out — otherwise every rotated position is
// off by exactly that box's size. Pass the object's width/height for
// anything box-shaped; leave them at 0 for bare points (stroke points,
// view-centres) which need no such correction.
const PILE_W = 150, PILE_H = 210;
const TOKEN_W = 52, TOKEN_H = 52;

function rotate180Pos(pos) {
  return { x: BOARD_WIDTH - PILE_W - pos.x, y: BOARD_HEIGHT - PILE_H - pos.y };
}
const PILE_SCREEN_POS = {
  0: {
    0: { deck: { x: 1368, y: 1038 }, graveyard: { x: 1539, y: 1038 }, receptacle: { x: 1368, y: 1295 }, exile: { x: 1539, y: 1295 } },
    1: { deck: { x: 225, y: 300 }, graveyard: { x: 47, y: 300 }, receptacle: { x: 225, y: 20 }, exile: { x: 47, y: 50 } },
  },
  1: {
    0: { deck: { x: 226, y: 303 }, graveyard: { x: 52, y: 303 }, receptacle: { x: 226, y: 48 }, exile: { x: 52, y: 48 } },
    1: { deck: { x: 1368, y: 1040 }, graveyard: { x: 1542, y: 1040 }, receptacle: { x: 1368, y: 1296 }, exile: { x: 1542, y: 1296 } },
  },
};

function mySeat() {
  if (isObserver || !myPlayerId || !latestState) return 0;
  return latestState.players[myPlayerId]?.seat || 0;
}

function rotateForSeat(x, y, w = 0, h = 0) {
  return mySeat() === 1 ? { x: BOARD_WIDTH - w - x, y: BOARD_HEIGHT - h - y } : { x, y };
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
  zoomLevel = Math.min(3, Math.max(0.3, Math.min(wrap.clientWidth / BOARD_WIDTH, wrap.clientHeight / BOARD_HEIGHT)));
  panX = wrap.clientWidth / 2 - (BOARD_WIDTH / 2) * zoomLevel;
  panY = wrap.clientHeight / 2 - (BOARD_HEIGHT / 2) * zoomLevel;
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
// battlefield items and tokens), so rotateForSeat converts both when capturing input
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
  setMyActivity(mode ? "drawing" : null);
}

function makeSvgEl(tag, attrs) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
  return el;
}

function initDrawTool() {
  const svg = $("#drawLayer");
  svg.setAttribute("viewBox", `0 0 ${BOARD_WIDTH} ${BOARD_HEIGHT}`);

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
          const logicalPoints = livePoints.map((p) => rotateForSeat(p.x, p.y)).map((p) => [p.x, p.y]);
          strokeUndoStack.push(id);
          strokeRedoStack = [];
          send({ type: "add_stroke", id, points: logicalPoints, color: playerColor(myPlayerId) });
        }
        liveEl = null; livePoints = [];
      } else {
        if (eraseRectEl) eraseRectEl.remove();
        const p = toDisplayPt(e.clientX, e.clientY);
        const a = rotateForSeat(eraseStartDisplay.x, eraseStartDisplay.y);
        const b = rotateForSeat(p.x, p.y);
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
    setMyActivity("token");
  };
  $("#tokenCancelBtn").onclick = () => {
    $("#tokenPanel").classList.add("hidden");
    setMyActivity(null);
  };
  $("#tokenCreateBtn").onclick = () => {
    if (!selectedTemperament) return;
    const power = Math.max(-20, Math.min(20, Math.round(Number($("#tokenPowerInput").value) || 0)));
    const view = fieldCenterLogical();
    const center = rotateForSeat(view.x, view.y);
    send({
      type: "create_token_card", temperament: selectedTemperament, power,
      x: center.x - 75 + Math.random() * 60 - 30, y: center.y - 105 + Math.random() * 60 - 30,
    });
    $("#tokenPanel").classList.add("hidden");
    setMyActivity(null);
  };
}

let selectedEssenceTemperament = null;

function initEssenceToolbar() {
  $("#createEssenceBtn").textContent = "✨";
  $("#essenceTemperamentGrid").innerHTML = TEMPERAMENTS.map(
    (temp) => `<button data-temperament="${esc(temp.key)}"><img src="${esc(temperamentSymbol(temp.key))}" alt="">${esc(t("temperament" + temp.key[0].toUpperCase() + temp.key.slice(1)))}</button>`
  ).join("") + `<button data-temperament="neutral" class="neutral-token-choice"><span></span>${esc(t("neutralToken"))}</button>`;
  $$("#essenceTemperamentGrid button").forEach((btn) => {
    btn.onclick = () => {
      selectedEssenceTemperament = btn.dataset.temperament;
      $$("#essenceTemperamentGrid button").forEach((b) => b.classList.toggle("active", b === btn));
      $("#neutralTokenNameField").classList.toggle("hidden", selectedEssenceTemperament !== "neutral");
      if (selectedEssenceTemperament === "neutral") $("#neutralTokenNameInput").focus();
    };
  });

  $("#createEssenceBtn").onclick = () => {
    selectedEssenceTemperament = null;
    $$("#essenceTemperamentGrid button").forEach((b) => b.classList.remove("active"));
    $("#essenceTemperamentGrid .neutral-token-choice span").style.setProperty("--neutral-color", playerColor(myPlayerId));
    $("#essenceCountInput").value = 1;
    $("#neutralTokenNameInput").value = t("neutralToken");
    $("#neutralTokenNameField").classList.add("hidden");
    $("#essencePanel").classList.remove("hidden");
    setMyActivity("essence");
  };
  $("#essenceCancelBtn").onclick = () => {
    $("#essencePanel").classList.add("hidden");
    setMyActivity(null);
  };
  $("#essenceCreateBtn").onclick = () => {
    if (!selectedEssenceTemperament) return;
    const count = Math.max(-99, Math.min(99, Math.round(Number($("#essenceCountInput").value) || 0)));
    const view = fieldCenterLogical();
    const center = rotateForSeat(view.x, view.y);
    send({
      type: "create_essence_token",
      temperament: selectedEssenceTemperament === "neutral" ? null : selectedEssenceTemperament,
      neutral: selectedEssenceTemperament === "neutral",
      label: selectedEssenceTemperament === "neutral" ? $("#neutralTokenNameInput").value.trim() : "",
      color: playerColor(myPlayerId), count,
      x: center.x - 26 + Math.random() * 60 - 30, y: center.y - 26 + Math.random() * 60 - 30,
    });
    $("#essencePanel").classList.add("hidden");
    setMyActivity(null);
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
    setMyActivity("dice");
  };
  $("#diceCancelBtn").onclick = () => {
    $("#dicePanel").classList.add("hidden");
    setMyActivity(null);
  };
  $("#diceResultCloseBtn").onclick = () => {
    $("#dicePanel").classList.add("hidden");
    setMyActivity(null);
  };
  $("#diceRollBtn").onclick = () => {
    const count = Math.max(1, Math.min(20, Math.round(Number($("#diceCountInput").value) || 1)));
    send({ type: "roll_dice", mode: selectedDiceMode, count });
    setMyActivity(null);
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
    const pts = s.points.map(([x, y]) => rotateForSeat(x, y));
    const poly = makeSvgEl("polyline", {
      fill: "none", stroke: s.color || playerColor(s.ownerId), "stroke-width": 4,
      "stroke-linecap": "round", "stroke-linejoin": "round",
      points: pts.map((p) => `${p.x},${p.y}`).join(" "),
    });
    svg.appendChild(poly);
  });
}

function rulesEffectTone(effect) {
  return cardsById.get(effect?.source?.cardId)?.glow || "#f1d377";
}

function rulesEffectKindText(effect) {
  if (effect.kind === "power_ignored") return t("rulesEffectPowerIgnored");
  if (effect.kind === "copy_power_temperament") return t("rulesEffectCopyPowerTemperament");
  if (effect.kind === "interzone_lock") return t("rulesEffectInterzoneLock");
  if (effect.kind === "power_modifier") {
    const value = Number(effect.value || 0);
    return rulesText("rulesEffectPowerModifier", { value: `${value > 0 ? "+" : ""}${value}` });
  }
  return t("rulesEffectActive");
}

function rulesEffectDurationText(effect) {
  if (effect.duration === "until_end_of_turn") return t("rulesEffectUntilEndTurn");
  if (effect.duration === "until_end_of_next_turn") return t("rulesEffectUntilEndNextTurn");
  if (effect.duration === "until_resolution") return t("rulesEffectUntilResolution");
  return t("rulesEffectWhileOnField");
}

function rulesEffectDescription(effect) {
  const source = cardName(effect?.source?.cardId);
  return `${rulesEffectKindText(effect)} · ${rulesEffectDurationText(effect)} · ${rulesText("rulesEffectFrom", { card: source })}`;
}

function battlefieldItemCenter(item) {
  const position = stackedScreenPos(item) || rotateForSeat(item.x, item.y, PILE_W, PILE_H);
  return { x: position.x + PILE_W / 2, y: position.y + PILE_H / 2 };
}

function renderRulesEffectLinks() {
  const svg = $("#rulesEffectLayer");
  svg.replaceChildren();
  const effects = latestState?.rulesEngine?.ongoingEffects || [];
  for (const effect of effects) {
    // A temporary modifier already has a visible stat marker on its target.
    // Keep connective lines for effects whose validity actually depends on
    // both cards remaining on the field (copy/link relationships).
    if (effect.duration !== "while_source_and_target_on_field") continue;
    const source = latestState.battlefield.find((item) => item.id === effect.source?.itemId);
    const target = latestState.battlefield.find((item) => item.id === effect.target?.itemId);
    if (!source || !target) continue;
    const from = battlefieldItemCenter(source);
    const to = battlefieldItemCenter(target);
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const distance = Math.max(1, Math.hypot(dx, dy));
    const bend = Math.min(78, distance * .16);
    const middle = { x: (from.x + to.x) / 2, y: (from.y + to.y) / 2 };
    const control = { x: middle.x - dy / distance * bend, y: middle.y + dx / distance * bend };
    const pathData = `M ${from.x} ${from.y} Q ${control.x} ${control.y} ${to.x} ${to.y}`;
    const group = makeSvgEl("g", { "data-effect-id": effect.id });
    group.classList.add("rules-effect-link");
    group.style.setProperty("--effect-tone", rulesEffectTone(effect));
    const title = makeSvgEl("title", {});
    title.textContent = rulesEffectDescription(effect);
    group.appendChild(title);
    group.appendChild(makeSvgEl("path", { class: "rules-effect-link-shadow", d: pathData, "vector-effect": "non-scaling-stroke" }));
    group.appendChild(makeSvgEl("path", { class: "rules-effect-link-flow", d: pathData, "vector-effect": "non-scaling-stroke" }));
    group.appendChild(makeSvgEl("circle", { class: "rules-effect-link-node", cx: to.x, cy: to.y, r: 7, "vector-effect": "non-scaling-stroke" }));
    svg.appendChild(group);
  }
}

function setRulesEffectHighlight(effectIds, highlighted) {
  const ids = new Set(effectIds);
  $$("#rulesEffectLayer [data-effect-id]").forEach((element) => {
    if (ids.has(element.dataset.effectId)) element.classList.toggle("highlighted", highlighted);
  });
}

function rulesEffectMarkerMarkup(effects) {
  if (!effects.length) return "";
  const title = effects.map(rulesEffectDescription).join("\n");
  const label = rulesText("rulesEffectCount", { count: effects.length });
  return `<button type="button" class="rules-effect-badge" title="${esc(title)}" aria-label="${esc(`${label}. ${title}`)}">
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="12" r="3"></circle><path d="M9 12h6"></path></svg>
    </button>`;
}

function wireRulesEffectMarker(cardElement, effects) {
  const badge = cardElement.querySelector(".rules-effect-badge");
  if (!badge) return;
  const effectIds = effects.map((effect) => effect.id);
  badge.addEventListener("pointerdown", (event) => event.stopPropagation());
  badge.addEventListener("mouseenter", () => setRulesEffectHighlight(effectIds, true));
  badge.addEventListener("mouseleave", () => setRulesEffectHighlight(effectIds, false));
  badge.addEventListener("focus", () => setRulesEffectHighlight(effectIds, true));
  badge.addEventListener("blur", () => setRulesEffectHighlight(effectIds, false));
  badge.addEventListener("click", (event) => {
    event.stopPropagation();
    const sourceCardId = effects[effects.length - 1]?.source?.cardId;
    if (sourceCardId) showInspect(sourceCardId);
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
  // the row scrolls sideways (see the single-line CSS) — without this, an
  // un-stopped wheel bubbles up into the board's own wheel handler and zooms
  // the field instead, same fix as the hand tray and reveal panel already have
  $("#handViewCards").addEventListener(
    "wheel",
    (event) => {
      event.preventDefault();
      event.stopPropagation();
      if ($("#handViewCards").scrollWidth > $("#handViewCards").clientWidth) {
        $("#handViewCards").scrollLeft += event.deltaY;
      }
    },
    { passive: false }
  );
}

// ---------------------------------------------------------------- hand resize

const HAND_SIZE_KEY = "ko_hand_card_h";
const HAND_SIZE_MAX = 720;
let handCardHeight = Math.min(HAND_SIZE_MAX, Math.max(70, Number(localStorage.getItem(HAND_SIZE_KEY)) || 170));

function applyHandCardHeight() {
  document.documentElement.style.setProperty("--hand-card-h", handCardHeight + "px");
  // hover should make a card easier to read, not comically huge: a full 30%
  // bump for a normal-sized hand, but capped to +80 logical px once the hand
  // is already large, so an already-huge hand doesn't get even huger. Applied
  // to a position:fixed CLONE (see wireHandCardHoverZoom), not the card
  // itself, so the tray's own top padding no longer needs to reserve any
  // headroom for it — that used to make the gap around the resize handle
  // much bigger than the one below the cards.
  const hoverScale = Math.min(1.55, (handCardHeight + 100) / handCardHeight);
  document.documentElement.style.setProperty("--hand-hover-scale", hoverScale.toFixed(3));
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

function counterCircles(
  counters, ongoingEffects = [], effectivePower = null,
  printedPower = null,
) {
  const renderedCounters = { ...(counters || {}) };
  const ongoingPower = ongoingEffects
    .filter((effect) => (
      effect.kind === "power_modifier" && Number(effect.value)
    ))
    .reduce((sum, effect) => sum + Number(effect.value), 0);
  ongoingEffects
    .filter((effect) => effect.kind === "power_modifier" && Number(effect.value))
    .forEach((effect) => {
      const temporary = ["until_end_of_turn", "until_end_of_next_turn", "until_resolution"]
        .includes(effect.duration);
      const key = temporary ? "rulesTempPower" : "rulesPermanentPower";
      renderedCounters[key] = Number(renderedCounters[key] || 0) + Number(effect.value);
    });
  if (
    Number.isFinite(Number(effectivePower))
    && Number.isFinite(Number(printedPower))
  ) {
    const explicitPower = Number(counters?.power || 0)
      + Number(counters?.tempCounter || 0)
      + ongoingPower;
    const continuousPower = Number(effectivePower)
      - Number(printedPower)
      - explicitPower;
    if (continuousPower) {
      renderedCounters.rulesContinuousPower = continuousPower;
    }
  }
  return Object.entries(renderedCounters)
    .filter(([, v]) => v)
    .map(([k, v]) => {
      const temporary = k === "tempCounter" || k === "rulesTempPower";
      const continuous = k === "rulesContinuousPower";
      const effectDerived = k === "rulesTempPower"
        || k === "rulesPermanentPower"
        || continuous;
      const title = effectDerived
        ? ` title="${esc(t(continuous ? "continuousModifier" : temporary ? "temporaryCounter" : "permanentCounter"))}"`
        : "";
      return `<span class="bf-counter${temporary ? " bf-counter-temp" : ""}${effectDerived ? " bf-counter-effect" : ""}"${title}>${v > 0 ? "+" : ""}${v}</span>`;
    })
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
// instead. The stored offset is screen-relative (see stackOffsetFrom), so it
// is added unchanged after the anchor's own seat transform. That preserves
// the exact overlap direction and spacing for both players.
function stackedScreenPos(item) {
  if (!item.stackedOn) return null;
  const anchor = latestState.battlefield.find((it) => it.id === item.stackedOn);
  if (!anchor) return null;
  const anchorPos = stackedScreenPos(anchor) || rotateForSeat(anchor.x, anchor.y, PILE_W, PILE_H);
  return { x: anchorPos.x + item.stackOffsetX, y: anchorPos.y + item.stackOffsetY };
}

function copyCardToField(cardId, fromOwnerId, fromZone) {
  const view = fieldCenterLogical();
  const center = rotateForSeat(view.x, view.y);
  send({
    type: "copy_card", cardId, fromOwnerId, fromZone,
    x: center.x - 75 + Math.random() * 60 - 30,
    y: center.y - 105 + Math.random() * 60 - 30,
  });
}

function copyCardMenuItem(cardId, fromOwnerId, fromZone) {
  return { label: t("copyCard"), onSelect: () => copyCardToField(cardId, fromOwnerId, fromZone) };
}

function essenceTokenMenuItems(token) {
  const items = [
    { label: "+1", onSelect: () => send({ type: "add_counter", tokenId: token.id, counterKey: "essence", delta: 1 }) },
    { label: "−1", onSelect: () => send({ type: "add_counter", tokenId: token.id, counterKey: "essence", delta: -1 }) },
  ];
  if (token.isNeutralCounter) items.push({
    label: t("renameToken"),
    onSelect: () => {
      const label = prompt(t("tokenName"), token.label || t("neutralToken"));
      if (label !== null) send({ type: "rename_token", tokenId: token.id, label: label.trim() });
    },
  });
  items.push({ separator: true });
  items.push({ label: t("remove"), onSelect: () => send({ type: "remove_token", tokenId: token.id }) });
  return items;
}

function rulesFieldZoneMarkerMarkup(fieldZone) {
  const icons = {
    confrontation: '<path d="m5 4 6 6-2 2-6-6V4h2Z"/><path d="m19 4-6 6 2 2 6-6V4h-2Z"/><path d="m8 13-3 3m11-3 3 3"/>',
    interzone: '<path d="m12 3 7 7-7 11-7-11 7-7Z"/><path d="M8.5 10h7M10 14h4"/>',
    stalemate: '<path d="M6 8h12M6 16h12"/><circle cx="12" cy="12" r="9"/>',
  };
  if (!icons[fieldZone]) return "";
  return `<span class="bf-field-zone-marker" title="${esc(t(`fieldZone_${fieldZone}`))}"><svg viewBox="0 0 24 24" aria-hidden="true">${icons[fieldZone]}</svg></span>`;
}

function rulesControllerMarkerMarkup(item) {
  const controllerId = battlefieldItemControllerId(item);
  if (!controllerId || controllerId === item.ownerId) return "";
  const player = latestState?.players?.[controllerId];
  const label = rulesText("rulesControlledBy", {
    player: player?.name || controllerId,
  });
  return `<span class="rules-controller-badge" style="--controller-tone:${esc(playerColor(controllerId))}" title="${esc(label)}" aria-label="${esc(label)}">C</span>`;
}

function rulesActivateMarkerMarkup(item) {
  const available = rulesActivatedAbilitiesForItem(item)
    .map((ability) => ({
      ability,
      draft: rulesActivatedActionDraft(item, ability),
    }))
    .filter((entry) => entry.draft);
  if (!available.length) return "";
  const baseLabel = rulesText("rulesActivateCardEffect", { card: cardName(item.cardId) });
  const printedEffect = cardField(cardsById.get(item.cardId), "effect");
  const label = printedEffect ? `${baseLabel} — ${printedEffect}` : baseLabel;
  return `<button type="button" class="rules-activate-badge" title="${esc(label)}" aria-label="${esc(label)}">
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13.2 2.5 5.8 13h5.6l-.6 8.5L18.4 11h-5.7l.5-8.5Z"></path></svg>
  </button>
  <div class="rules-activate-confirm hidden" role="group" aria-label="${esc(t("confirmQuestion"))}">
    <span>${esc(t("confirmQuestion"))}</span>
    ${available.map(({ ability }, index) => `
      <button type="button" data-rules-activate-confirm="${esc(ability.id)}">
        ${esc(ability.immediate ? t("rulesImmediateLabel") : `${t("rulesEncodedAbility")} ${index + 1}`)}
      </button>`).join("")}
    <button type="button" class="rules-activate-cancel" data-rules-activate-cancel aria-label="${esc(t("cancel"))}">×</button>
  </div>`;
}

let rulesActivationDismiss = null;

function closeRulesActivationConfirmation() {
  $$(".rules-activate-confirm").forEach((element) => element.classList.add("hidden"));
  if (rulesActivationDismiss) document.removeEventListener("pointerdown", rulesActivationDismiss);
  rulesActivationDismiss = null;
}

function wireRulesActivateMarker(cardElement, item) {
  const button = cardElement.querySelector(".rules-activate-badge");
  const confirmation = cardElement.querySelector(".rules-activate-confirm");
  if (!button) return;
  [button, confirmation].filter(Boolean).forEach((element) => {
    element.addEventListener("pointerdown", (event) => event.stopPropagation());
    element.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      event.stopPropagation();
    });
  });
  button.addEventListener("contextmenu", (event) => {
    event.preventDefault();
    event.stopPropagation();
  });
  button.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    closeRulesActivationConfirmation();
    confirmation.classList.remove("hidden");
    rulesActivationDismiss = (outsideEvent) => {
      if (confirmation.contains(outsideEvent.target) || button.contains(outsideEvent.target)) return;
      closeRulesActivationConfirmation();
    };
    setTimeout(() => document.addEventListener("pointerdown", rulesActivationDismiss), 0);
  });
  confirmation.querySelectorAll("[data-rules-activate-confirm]").forEach(
    (confirmButton) => {
      confirmButton.onclick = (event) => {
        event.preventDefault();
        event.stopPropagation();
        closeRulesActivationConfirmation();
        beginRulesBoardActivatedAction(
          item, confirmButton.dataset.rulesActivateConfirm,
        );
      };
    },
  );
  confirmation.querySelector("[data-rules-activate-cancel]").onclick = (event) => {
    event.preventDefault();
    event.stopPropagation();
    closeRulesActivationConfirmation();
  };
}

function renderBattlefield() {
  $("#battlefieldBg").classList.toggle("rotated", mySeat() === 1);
  renderPiles();
  const bf = $("#battlefield");
  bf.querySelectorAll(".bf-card, .bf-token").forEach((el) => el.remove());

  latestState.battlefield.forEach((item) => {
    const el = document.createElement("div");
    el.className = `bf-card${item.isCopy ? " is-copy" : ""}${item.fieldZone ? ` field-zone-${item.fieldZone}` : ""}`;
    el.dataset.itemId = item.id;
    if (item.fieldZone) el.dataset.fieldZone = item.fieldZone;
    const pos = stackedScreenPos(item) || rotateForSeat(item.x, item.y, PILE_W, PILE_H);
    el.style.left = pos.x + "px";
    el.style.top = pos.y + "px";
    el.style.setProperty("--owner-color", playerColor(item.ownerId));
    const isMine = !isObserver && battlefieldItemControllerId(item) === myPlayerId;
    // a trusted observer gets the same "owner peek" as the actual owner
    const canPeek = isMine || isObserver;
    let inner;
    if (item.isTokenCard) {
      inner = `<div class="bf-card-face" style="background:${esc(temperamentInk(item.temperament))}">${tokenCardFaceHtml(item)}</div>`;
    } else if (item.faceUp && item.cardId) {
      const rarity = normalizeRarity(item.rarity);
      inner = `<div class="bf-card-face${rarityClassAttr(rarity)}" style="${rarityCosmosStyle(item.cardId)}">${raritySurfaceMarkup(rarity, `<img src="${esc(cardImage(item.cardId))}" alt="${esc(cardName(item.cardId))}" title="${esc(cardName(item.cardId))}">`)}</div>`;
    } else if (canPeek && item.cardId) {
      // the owner (or an observer) gets a faint, colour-tinted peek at a face-down card
      inner = `<div class="bf-card-face"><div class="back-face owner-peek"><img src="${esc(cardImage(item.cardId))}"></div></div>`;
    } else {
      inner = `<div class="bf-card-face"><div class="back-face"></div></div>`;
    }
    const ongoingEffects = (latestState.rulesEngine?.ongoingEffects || []).filter((effect) => effect.target?.itemId === item.id);
    if (ongoingEffects.length) {
      el.classList.add("has-ongoing-effect");
      el.style.setProperty("--effect-tone", rulesEffectTone(ongoingEffects[ongoingEffects.length - 1]));
    }
    const printedPower = item.isTokenCard
      ? item.power
      : cardsById.get(item.cardId)?.power;
    el.innerHTML = `<div class="bf-card-inner" style="transform:rotate(${item.rotation || 0}deg)">${inner}${item.faceUp && item.cardId ? automationCoverageBadgeHtml(item.cardId) : ""}${item.effectsDisabled ? `<span class="rules-effects-disabled-badge" title="${esc(t("rulesEffectsDisabled"))}" aria-label="${esc(t("rulesEffectsDisabled"))}">Ø</span>` : ""}${item.isCopy ? `<span class="copy-card-stamp">${esc(t("copyStamp"))}</span>` : ""}</div><div class="counters">${counterCircles(item.counters, ongoingEffects, item.effectivePower, printedPower)}</div>${rulesFieldZoneMarkerMarkup(item.fieldZone)}${rulesControllerMarkerMarkup(item)}${item.isSupport ? `<span class="rules-support-badge" title="${esc(t("playInSupport"))}" aria-label="${esc(t("playInSupport"))}">S</span>` : ""}${rulesEffectMarkerMarkup(ongoingEffects)}${rulesActivateMarkerMarkup(item)}`;
    el.addEventListener("click", (event) => {
      if (toggleRulesBoardPayment(`battlefield:${item.id}`)) {
        event.preventDefault();
        event.stopPropagation();
      }
    });
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
      if (item.isCopy) {
        const copyItems = [{ label: t("inspect"), onSelect: () => showInspect(item.cardId, false) }];
        const rulesItem = isMine && item.faceUp
          ? rulesActionContextItem({ cardId: item.cardId, zone: "battlefield", itemId: item.id })
          : null;
        if (rulesItem) copyItems.push(rulesItem);
        copyItems.push(
          { separator: true },
          counterGridMenuItem("power", { itemId: item.id }),
          { separator: true },
          { label: t("removeCopy"), onSelect: () => send({ type: "remove_battlefield_item", itemId: item.id, toZone: "graveyard" }) },
        );
        showContextMenu(event.clientX, event.clientY, copyItems);
        showCardLabels(el, cardName(item.cardId), t("copyStamp"));
        return;
      }
      const items = [];
      items.push({ label: t("inspect"), onSelect: () => showInspect(item.cardId, !item.faceUp && !canPeek) });
      const rulesItem = isMine && item.faceUp
        ? rulesActionContextItem({ cardId: item.cardId, zone: "battlefield", itemId: item.id })
        : null;
      if (rulesItem) items.push(rulesItem);
      if (item.faceUp) items.push({ label: t("copyCard"), onSelect: () => send({ type: "copy_card", itemId: item.id }) });
      items.push({ separator: true });
      if (isMine) items.push({ label: t("flip"), onSelect: () => send({ type: "flip_card", itemId: item.id }), highlight: !item.faceUp });
      items.push({ label: t("exhaust"), onSelect: () => send({ type: "move_battlefield_item", itemId: item.id, x: item.x, y: item.y, rotation: item.rotation ? 0 : 90 }) });
      if (
        isMine
        && latestState?.rulesEngine?.enabled
        && currentPhaseUi().phase?.id === "confrontation_reaction"
        && latestState.rulesEngine.priorityPlayerId === myPlayerId
        && cardsById.get(item.cardId)?.type === "manifestation"
        && rulesBattlefieldSupportAvailableClient(item)
      ) {
        items.push({
          label: t("playInSupport"),
          onSelect: () => {
            const payload = { type: "set_rules_field_zone", itemId: item.id, cardId: item.cardId, faceUp: item.faceUp, fieldZone: "confrontation", x: item.x, y: item.y };
            const source = { cardId: item.cardId, zone: "battlefield", itemId: item.id };
            requestCardPlacement(payload, source);
          },
          highlight: true,
        });
      }
      items.push(...zOrderItems);
      items.push({ separator: true });
      items.push(counterGridMenuItem("power", { itemId: item.id }));
      items.push({ separator: true });
      // Limbo and Exile always belong to the immutable card owner. The
      // Empathic Vessel is necessarily the other player's.
      ["graveyard", "exile"].forEach((z) => {
        items.push({ label: cardDestinationLabel(item.ownerId, z), onSelect: () => send({ type: "remove_battlefield_item", itemId: item.id, toOwnerId: item.ownerId, toZone: z }) });
      });
      const vesselOwnerId = cardDestinationOwner(item.ownerId, "receptacle");
      if (vesselOwnerId) items.push({ label: cardDestinationLabel(item.ownerId, "receptacle"), onSelect: () => send({ type: "remove_battlefield_item", itemId: item.id, toOwnerId: vesselOwnerId, toZone: "receptacle" }) });
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
    wireRulesEffectMarker(el, ongoingEffects);
    wireRulesActivateMarker(el, item);
    bindRarityPointer(el.querySelector(".bf-card-face.ko-rarity-card"), false, el);
  });

  latestState.tokens.forEach((token) => {
    const el = document.createElement("div");
    el.className = "bf-token" + (token.isEssence ? " bf-essence" : "");
    el.dataset.tokenId = token.id;
    const tpos = rotateForSeat(token.x, token.y, TOKEN_W, TOKEN_H);
    el.style.left = tpos.x + "px";
    el.style.top = tpos.y + "px";
    if (token.isEssence) {
      el.style.background = token.isNeutralCounter ? (token.color || playerColor(token.ownerId)) : temperamentInk(token.temperament);
      const count = token.counters?.essence || 0;
      el.innerHTML = token.isNeutralCounter
        ? `<span class="bf-neutral-label">${esc(token.label || t("neutralToken"))}</span><span class="bf-essence-count">${count > 0 ? "+" : ""}${count}</span>`
        : `<img src="${esc(temperamentSymbol(token.temperament))}" alt=""><span class="bf-essence-count">${count > 0 ? "+" : ""}${count}</span>`;
    } else {
      el.style.background = token.color || playerColor(token.ownerId);
      el.innerHTML = `<span>${esc(token.label || "")}</span><div class="counters">${counterCircles(token.counters)}</div>`;
    }
    if (!isObserver) {
      bindDrag(el, (x, y) => {
        const logical = rotateForSeat(x, y, TOKEN_W, TOKEN_H);
        send({ type: "move_token", tokenId: token.id, x: logical.x, y: logical.y });
      });
      el.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        if (token.isEssence) {
          showContextMenu(event.clientX, event.clientY, essenceTokenMenuItems(token));
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
  renderRulesEffectLinks();
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
    pendingDeckImport = null;
    resetImportDeckValidationArm();
    $("#importSideboardBtn").disabled = !(latestState?.players?.[myPlayerId]);
    $("#importSelectionStatus").textContent = "";
    $("#importPanel").classList.remove("hidden");
    setMyActivity("importing");
    renderSavedDecks();
    renderCurrentDeckSummary();
    renderImportPanelActions();
  };
  $("#importCancelBtn").onclick = () => {
    $("#importPanel").classList.add("hidden");
    resetImportDeckValidationArm();
    setMyActivity(null);
  };
  $("#importDeckText").addEventListener("input", () => {
    pendingDeckImport = null;
    $("#importSideboardBtn").disabled = false;
    $("#importSelectionStatus").textContent = "";
    renderCurrentDeckSummary();
    resetImportDeckValidationArm();
    renderImportPanelActions();
  });
  $("#importPasteBtn").onclick = async () => {
    if (!(await ensurePendingDeckImport())) return;
    if (!deckImportIsValid()) {
      renderSideboardEditor();
      return;
    }
    importDeckPayload(buildEditedDeck(), pendingDeckImport.name, pendingDeckImport.persist, false);
    renderCurrentDeckSummary();
    resetImportDeckValidationArm();
    renderImportPanelActions();
  };
  $("#importSideboardBtn").onclick = async () => {
    if (pendingDeckImport) {
      renderSideboardEditor();
      return;
    }
    if (!$("#importDeckText").value.trim() && latestState?.players?.[myPlayerId]) {
      openCurrentSideboard();
      return;
    }
    if (await ensurePendingDeckImport()) {
      pendingDeckImport.resetOwnBoard = false;
      renderSideboardEditor();
    }
  };
  $("#currentSideboardBtn").onclick = openCurrentSideboard;
  $("#sideboardCancelBtn").onclick = () => $("#sideboardPanel").classList.add("hidden");
  $("#sideboardValidateBtn").onclick = () => {
    if (!deckImportIsValid()) return;
    const apply = () => importDeckPayload(buildEditedDeck(), pendingDeckImport.name, pendingDeckImport.persist);
    if (pendingDeckImport.resetOwnBoard) showConfirm(t("confirmCurrentSideboardReset"), apply);
    else apply();
  };
  $("#importConfirmBtn").onclick = async () => {
    if (!pendingDeckImport && $("#importDeckText").value.trim()) await ensurePendingDeckImport();
    if (!pendingDeckImport) {
      const current = currentDeckForSideboard();
      if (current) pendingDeckImport = splitDeckForEditor(current, current.name || t("currentDeck"), false);
    }
    if (!pendingDeckImport) return;
    if (!deckImportIsValid()) {
      renderSideboardEditor();
      return;
    }
    if (!importDeckValidationArmed) {
      importDeckValidationArmed = true;
      $("#importConfirmBtn").classList.add("confirm-armed");
      $("#importConfirmBtn").textContent = t("confirmQuestion");
      return;
    }
    importDeckPayload(buildEditedDeck(), pendingDeckImport.name, pendingDeckImport.persist, true);
    pendingDeckImport = null;
    renderCurrentDeckSummary();
    $("#importPanel").classList.add("hidden");
    resetImportDeckValidationArm();
    setMyActivity(null);
  };
  document.addEventListener("pointerdown", (event) => {
    if (importDeckValidationArmed && !event.target.closest("#importConfirmBtn")) resetImportDeckValidationArm();
  });
}

// ---------------------------------------------------------------- chat

let chatMessages = [];
let chatState = "open"; // "open" | "minimized" | "closed"
let unreadChatCount = 0;

function renderChatMessages() {
  $("#chatMessages").innerHTML = chatMessages
    .map((m) => `<div class="chat-msg"><b style="color:${playerColor(m.byId)}">${esc(m.byName)}:</b> ${esc(m.text)}</div>`)
    .join("");
  $("#chatMessages").scrollTop = $("#chatMessages").scrollHeight;
}

function updateChatBadge() {
  const btn = $("#chatReopenBtn");
  btn.querySelector(".chat-unread-badge")?.remove();
  if (unreadChatCount > 0 && chatState !== "open") {
    const badge = document.createElement("span");
    badge.className = "chat-unread-badge";
    badge.textContent = String(Math.min(unreadChatCount, 99));
    btn.appendChild(badge);
  }
}

function applyChatState() {
  $("#chatPanel").classList.toggle("hidden", chatState === "closed");
  $("#chatPanel").classList.toggle("minimized", chatState === "minimized");
  $("#chatReopenBtn").classList.toggle("hidden", chatState !== "closed");
  if (chatState === "open") {
    unreadChatCount = 0;
    $("#chatMessages").scrollTop = $("#chatMessages").scrollHeight;
  }
  updateChatBadge();
}

function sendChatMessage() {
  const text = $("#chatInput").value.trim();
  if (!text) return;
  send({ type: "chat_message", text });
  $("#chatInput").value = "";
}

function initChat() {
  $("#chatHeading").textContent = t("chatHeading");
  $("#chatInput").placeholder = t("chatPlaceholder");
  $("#chatSendBtn").textContent = t("chatSend");
  $("#chatCloseBtn").onclick = () => {
    chatState = "closed";
    applyChatState();
  };
  $("#chatReopenBtn").onclick = () => {
    chatState = "open";
    applyChatState();
  };
  $("#chatSendBtn").onclick = sendChatMessage;
  $("#chatInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") sendChatMessage();
  });
  applyChatState();
}

// ---------------------------------------------------------------- token add + end session + log

function initCombatChrome() {
  const screen = $("#gameScreen");
  const header = screen.querySelector(".game-header");
  const hotZone = $("#gameHeaderHotZone");
  let hideTimer = null;
  const show = () => {
    clearTimeout(hideTimer);
    screen.classList.add("header-peek");
  };
  const scheduleHide = () => {
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => {
      if (!header.matches(":hover") && !$("#gameMoreMenu").open) screen.classList.remove("header-peek");
    }, 520);
  };
  hotZone.addEventListener("mouseenter", show);
  header.addEventListener("mouseenter", show);
  header.addEventListener("mouseleave", scheduleHide);
  document.addEventListener("pointermove", (event) => {
    if (!screen.classList.contains("hidden") && event.clientY <= 10) show();
  }, { passive: true });
  $("#gameMoreMenu").addEventListener("toggle", () => {
    if ($("#gameMoreMenu").open) show();
    else scheduleHide();
  });
}

function initGameControls() {
  $("#rulesFlowCancelBtn").onclick = cancelRulesBoardFlow;
  $("#rulesFlowDeclineBtn").onclick = () => {
    if (pendingRulesBoardFlow?.mode === "stack_copy_target") resolveRulesStackCopyTargets("keep");
    else resolveRulesStackPayment("decline");
  };
  $("#rulesFlowPayBtn").onclick = () => resolveRulesStackPayment("pay");
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && pendingRulesBoardFlow) cancelRulesBoardFlow();
  });
  $("#judgeReturnBtn").onclick = () => showTournamentScreen();
  $("#phaseTrackerBtn").onclick = () => {
    const trackerEnabled = Boolean(latestState?.phaseTracker?.enabled);
    if (!trackerEnabled && !isObserver) phaseTrackerVisible = true;
    else phaseTrackerVisible = !phaseTrackerVisible;
    localStorage.setItem(PHASE_VISIBILITY_KEY, phaseTrackerVisible ? "1" : "0");
    if (phaseTrackerVisible && !trackerEnabled && !isObserver) {
      send({ type: "configure_phases", enabled: true });
    }
    renderPhaseTracker();
  };
  $("#phaseAdvancedBtn").onclick = () => {
    if (!isObserver && mySeat() === 0) send({ type: "configure_phases", advanced: !latestState?.phaseTracker?.advanced });
  };
  $("#passPriorityBtn").onclick = () => toggleMyPhasePass();
  $("#gameMoreMenu").addEventListener("click", (event) => {
    if (event.target.closest("button")) $("#gameMoreMenu").open = false;
  });
  $("#rulesActionCloseBtn").onclick = closeRulesActionPanel;
  $("#rulesActionCancelBtn").onclick = closeRulesActionPanel;
  $("#rulesActionPanel").onclick = (event) => {
    if (event.target === $("#rulesActionPanel")) closeRulesActionPanel();
  };
  $("#rulesActionDeclareForm").onsubmit = (event) => {
    event.preventDefault();
    if (!pendingRulesActionSource || latestState?.rulesEngine?.priorityPlayerId !== myPlayerId || isObserver) return;
    const label = $("#rulesActionDescription").value.trim();
    if (!label) {
      $("#rulesActionDescription").focus();
      return;
    }
    const paymentCardIds = $$("#rulesTributeList input:checked").map((input) => input.value);
    const targets = $$("#rulesTargetList input:checked").map((input) => {
      const target = { kind: input.dataset.targetKind || "card", cardId: input.dataset.cardId };
      if (target.kind === "player") {
        delete target.cardId;
        target.playerId = input.dataset.playerId;
      } else if (target.kind === "zone_card") {
        target.containerId = input.dataset.containerId;
        target.zone = input.dataset.zone;
      } else if (["stack_action", "stack_effect", "stack_item"].includes(target.kind)) {
        target.actionId = input.dataset.actionId;
      } else {
        target.itemId = input.dataset.itemId;
      }
      return target;
    });
    const payload = {
      type: "declare_rules_action",
      label,
      kind: pendingRulesActionSource.actionKind
        || $("#rulesActionKind").value,
      source: {
        cardId: pendingRulesActionSource.cardId,
        zone: pendingRulesActionSource.zone,
        itemId: pendingRulesActionSource.itemId,
      },
      target: $("#rulesActionTarget").value.trim(),
      targets,
      costNote: $("#rulesActionCostNote").value.trim(),
      paymentCardIds,
    };
    if (pendingRulesActionSource.abilityId) payload.abilityId = pendingRulesActionSource.abilityId;
    send(payload);
    closeRulesActionPanel();
  };

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
    const logical = rotateForSeat((event.clientX - rect.left - panX) / zoomLevel - 26, (event.clientY - rect.top - panY) / zoomLevel - 26, TOKEN_W, TOKEN_H);
    send({ type: "add_token", x: logical.x, y: logical.y, label, color: playerColor(myPlayerId) });
  });

  $("#resetBoardBtn").textContent = t("resetBoard");
  $("#resetBoardBtn").onclick = () => {
    showConfirm(t("confirmResetBoard"), () => send({ type: "reset_board" }));
  };

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

function initTournamentControls() {
  $("#tournamentViewMatchBtn").onclick = () => showTournamentMatch();
  $("#tournamentStartBtn").onclick = () => send({ type: "start_tournament" });
  $("#tournamentEndBtn").onclick = () => {
    showConfirm(t("confirmEndTournament"), () => send({ type: "end_tournament" }), t("endMatch"));
  };
  $("#tournamentExportLogBtn").onclick = () => {
    pendingTournamentLogDownload = true;
    send({ type: "request_log" });
  };
  $("#bannedCardAddBtn").onclick = () => {
    const cardId = resolveTournamentCard($("#bannedCardInput").value);
    if (!cardId) return showToast(t("unknownCard"), true);
    if (!tournamentPolicyDraft.bannedCardIds.includes(cardId)) tournamentPolicyDraft.bannedCardIds.push(cardId);
    $("#bannedCardInput").value = "";
    tournamentPolicyDirty = true;
    renderTournamentRules(latestState.tournament, true);
  };
  $("#restrictedGroupAddBtn").onclick = () => {
    tournamentPolicyDraft.restrictedGroups.push({ id: `restricted-${Date.now()}`, name: `${t("restrictedGroup")} ${tournamentPolicyDraft.restrictedGroups.length + 1}`, cardIds: [] });
    tournamentPolicyDirty = true;
    renderTournamentRules(latestState.tournament, true);
  };
  $("#tournamentRulesSaveBtn").onclick = () => {
    send({ type: "update_tournament_policy", policy: tournamentPolicyDraft });
    tournamentPolicyDirty = false;
    $("#tournamentRulesStatus").textContent = t("rulesSaved");
  };
  $("#tournamentLeaveBtn").onclick = () => leaveSession();
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
  const art = $("#inspectPanel .inspect-img");
  const rarity = !hidden && card ? visibleRarityForCard(cardId) : null;
  art.className = `inspect-img${rarityClassAttr(rarity)}`;
  art.setAttribute("style", rarityCosmosStyle(cardId || ""));
  art.innerHTML = raritySurfaceMarkup(
    rarity,
    `<img id="inspectImg" src="${hidden || !card ? "" : esc(card.image || "")}" alt="${hidden || !card ? "" : esc(cardField(card, "name"))}">`
  );
  bindRarityPointer(art, false);
  if (!hidden && card) {
    inspectHistory = [cardId, ...inspectHistory.filter((id) => id !== cardId)].slice(0, 12);
    $("#inspectReopenBtn").disabled = false;
  }
  if (hidden || !card) {
    $("#inspectName").textContent = "?";
    $("#inspectMeta").textContent = "";
    $("#inspectEffect").textContent = "";
  } else {
    const coverage = cardAutomationCoverage(cardId);
    $("#inspectName").textContent = cardField(card, "name");
    $("#inspectMeta").textContent = [
      cardField(card, "typeLabel") || card.type,
      cardField(card, "subType"),
      cardField(card, "color"),
      `${t("automationCoverage")}: ${t(`automationStatus_${coverage.status}`)}`,
    ].filter(Boolean).join(" · ");
    $("#inspectEffect").textContent = cardField(card, "effect");
  }
  renderInspectHistory();
  $("#inspectPanel").classList.remove("hidden");
  $("#gameScreen").classList.add("inspect-open");
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

// Toggles: closes the panel if it's already open, otherwise reopens the last
// inspected card. Shared by the toolbar button and the "I" keyboard shortcut.
function toggleInspectPanel() {
  if (!$("#inspectPanel").classList.contains("hidden")) {
    $("#inspectPanel").classList.add("hidden");
    $("#gameScreen").classList.remove("inspect-open");
  } else if (inspectHistory.length) {
    showInspect(inspectHistory[0]);
  }
}

function initInspectToolbar() {
  $("#inspectReopenBtn").title = t("reopenLastInspected");
  $("#inspectReopenBtn").disabled = true;
  $("#inspectReopenBtn").onclick = toggleInspectPanel;
  applyInspectPanelWidth();
  $("#inspectResizeHandle").addEventListener("pointerdown", (event) => {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = inspectPanelWidth;
    const move = (e) => {
      // the handle sits on the box's RIGHT edge (the box itself is left-docked
      // near the screen edge), so dragging further right — away from the box —
      // is what grows it: the same "drag away from content grows it" rule as
      // the reveal/hand-view resize handles, just on the horizontal axis
      inspectPanelWidth = Math.min(INSPECT_SIZE_MAX, Math.max(220, startWidth + (e.clientX - startX)));
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

function logCardName(cardId, language) {
  const card = cardsById.get(cardId);
  return card?.translations?.[language]?.name || card?.name || cardId;
}

function logTemplate(key, values, language, htmlKeys = new Set(), escapeValues = false) {
  return String(translateFor(key, language)).replace(/\{(\w+)\}/g, (_match, name) => {
    const value = values[name] ?? "";
    return !escapeValues || htmlKeys.has(name) ? String(value) : esc(value);
  });
}

function formatLogEntry(e, options = {}) {
  const language = options.language || currentLanguage;
  const html = Boolean(options.html);
  const rawWho = e.actorName || e.actorId || "?";
  const who = html ? `<b style="color:${playerColor(e.actorId)}">${esc(rawWho)}</b>` : rawWho;
  const d = e.details || {};
  const z = (key) => translateFor(key, language) || key;
  const ownerName = (pid) => latestState?.players?.[pid]?.name || pid;
  const cross = d.ownerId && d.ownerId !== e.actorId ? logTemplate("logOwnerSuffix", { owner: ownerName(d.ownerId) }, language) : "";
  const card = (cardId) => {
    if (!cardId) return translateFor("plAnUnknownCard", language);
    const name = logCardName(cardId, language);
    return html ? `<span class="log-card-ref" data-log-card="${esc(cardId)}">${esc(name)}</span>` : name;
  };
  const faceState = (faceUp) => (faceUp === undefined ? "" : translateFor(faceUp ? "logFaceUp" : "logFaceDown", language));
  const viaRequest = (requestedBy) => requestedBy ? logTemplate("logRequestedBy", { requester: requestedBy }, language) : "";
  const f = (key, values = {}, markup = []) => logTemplate(key, { who, ...values }, language, new Set(html ? ["who", ...markup] : []), html);
  switch (e.type) {
    case "import_deck": return f("logImportDeck", { count: d.count });
    case "draw": return f("logDraw", { count: d.count });
    case "draw_to_limit": return f("logDrawToLimit", { count: d.count });
    case "opening_hand_draw": return f("logOpeningHandDraw", { count: d.count });
    case "rules_opening_mulligan_required": return f("logRulesOpeningMulliganRequired", {
      player: ownerName(e.actorId),
    });
    case "rules_recovery_mulligan_required": return f("logRulesRecoveryMulliganRequired", {
      player: ownerName(e.actorId), turn: d.turn,
    });
    case "rules_opening_defeat": return f("logRulesOpeningDefeat", {
      players: (d.loserIds || []).map(ownerName).join(", "),
    });
    case "rules_recovery_defeat": return f("logRulesRecoveryDefeat", {
      players: (d.loserIds || []).map(ownerName).join(", "), turn: d.turn,
    });
    case "rules_recovery_resumed": return f("logRulesRecoveryResumed", { turn: d.turn });
    case "recovery_draw": {
      const draws = Object.entries(d.draws || {})
        .map(([playerId, count]) => `${ownerName(playerId)} +${count}`)
        .join(", ");
      return f("logRecoveryDraw", { draws });
    }
    case "rules_game_end": return f("logRulesGameEnd");
    case "rules_action_declared": {
      const detailText = (value) => html ? esc(value) : String(value);
      const essenceText = (entries) => {
        const totals = {};
        for (const entry of entries || []) totals[entry.temperament] = (totals[entry.temperament] || 0) + Number(entry.amount || 0);
        return Object.entries(totals).map(([temperament, amount]) => {
          const key = `temperament${temperament[0].toUpperCase()}${temperament.slice(1)}`;
          return `${translateFor(key, language)} ×${amount}`;
        }).join(", ");
      };
      const context = [];
      if (d.source?.cardId) context.push(`${translateFor("rulesSourceShort", language)}: ${card(d.source.cardId)}`);
      if (d.targets?.length) {
        context.push(`${translateFor("rulesTargetsShort", language)}: ${d.targets.map((target) => (
          target.kind === "player"
            ? detailText(ownerName(target.playerId))
            : target.kind === "zone_card"
              ? `${card(target.cardId)} (${detailText(`${ownerName(target.containerId)} · ${translateFor(target.zone, language)}`)})`
              : `${card(target.cardId)} (${detailText(ownerName(target.ownerId))})`
        )).join(", ")}`);
      }
      if (d.target) context.push(`${translateFor("rulesTargetNoteShort", language)}: ${detailText(d.target)}`);
      if (d.cost?.note) context.push(`${translateFor("rulesCostShort", language)}: ${detailText(d.cost.note)}`);
      if (d.cost?.essenceSpent?.length) context.push(`${translateFor("rulesEssenceShort", language)}: ${essenceText(d.cost.essenceSpent)}`);
      if (d.cost?.tributeCardIds?.length) {
        context.push(`${translateFor("rulesTributeShort", language)}: ${d.cost.tributeCardIds.map(card).join(", ")}`);
      }
      if (d.cost?.excessEssence?.length) context.push(`${translateFor("rulesExcessShort", language)}: ${essenceText(d.cost.excessEssence)}`);
      if (d.cost?.sourceExhausted) context.push(translateFor("rulesSourceExhaustedShort", language));
      if (d.cost?.sourceSacrificed) context.push(translateFor("rulesSourceSacrificedShort", language));
      return `${f("logRulesActionDeclared", { action: d.label, depth: d.stackDepth })}${context.length ? ` ${context.join(" · ")}` : ""}`;
    }
    case "rules_action_triggered": {
      const triggered = f("logRulesActionTriggered", {
        source: card(d.source?.cardId), depth: d.stackDepth,
      }, ["source"]);
      const playerTarget = (d.targets || []).find((target) => target.kind === "player");
      return playerTarget
        ? `${triggered} ${f("logRulesTriggerTarget", { target: ownerName(playerTarget.playerId) })}`
        : triggered;
    }
    case "rules_priority_passed": return f("logRulesPriorityPassed");
    case "rules_priority_cancelled": return f("logRulesPriorityCancelled");
    case "rules_action_resolved": {
      const resolved = f("logRulesActionResolved", { action: d.label, remaining: d.stackDepth });
      const source = d.source?.cardId
        ? `${translateFor("rulesSourceShort", language)}: ${card(d.source.cardId)}`
        : "";
      const active = d.ongoingEffects?.length
        ? f("logRulesOngoingStarted", { count: d.ongoingEffects.length })
        : "";
      let sourceResult = "";
      if (d.sourceResolution?.status === "moved" && d.source?.cardId) {
        sourceResult = f(
          d.sourceResolution.destination === "battlefield"
            ? "logRulesPersistentToField" : "logRulesEphemeralToLimbo",
          { card: card(d.source.cardId) }, ["card"],
        );
      }
      if (d.sourceResolution?.status === "source_missing" && d.source?.cardId) {
        sourceResult = f("logRulesSourceMissing", { card: card(d.source.cardId) }, ["card"]);
      }
      if (d.sourceResolution?.status === "manual_placement" && d.source?.cardId) {
        sourceResult = f("logRulesManualPlacement", { card: card(d.source.cardId) }, ["card"]);
      }
      let applied = "";
      if (d.effectResult?.kind === "score") {
        const delta = Number(d.effectResult.delta || 0);
        applied = f(delta < 0 ? "logRulesScoreLost" : "logRulesScoreApplied", {
          player: ownerName(d.effectResult.playerId),
          delta: `${delta >= 0 ? "+" : ""}${delta}`,
          amount: Math.abs(delta),
          score: d.effectResult.score,
        });
      }
      if (d.effectResult?.kind === "draw") {
        const count = Number(d.effectResult.count || 0);
        applied = f(count === 1 ? "logRulesCardDrawn" : "logRulesCardsDrawn", {
          player: ownerName(d.effectResult.playerId), count,
        });
      }
      if (d.effectResult?.kind === "discard_deck") {
        const result = d.effectResult;
        const discardedCards = (result.cardIds || []).map(card).join(", ");
        applied = result.count
          ? f("logRulesDeckDiscarded", {
              player: ownerName(result.playerId), count: result.count, cards: discardedCards,
            }, ["cards"])
          : f("logRulesDeckEmpty", { player: ownerName(result.playerId) });
      }
      if (d.effectResult?.kind === "move_card") {
        const result = d.effectResult;
        if (result.status === "target_missing") {
          applied = f("logRulesTargetMissing", { card: card(result.cardId) }, ["card"]);
        } else if (result.status === "no_eligible_card") {
          applied = f("logRulesNoEligibleCard");
        } else if (result.status === "removed_copy") {
          applied = f("logRulesTargetCopyRemoved", { card: card(result.cardId) }, ["card"]);
        } else if (result.reason === "destroy") {
          applied = f("logRulesTargetDestroyed", { card: card(result.cardId) }, ["card"]);
        } else if (result.reason === "exile") {
          applied = f("logRulesTargetExiled", { card: card(result.cardId) }, ["card"]);
        } else {
          applied = f("logRulesTargetMoved", {
            card: card(result.cardId),
            position: translateFor(result.position === "bottom" ? "rulesPositionBottom" : "rulesPositionTop", language),
            zone: z(result.toZone),
          }, ["card"]);
        }
      }
      if (d.effectResult?.kind === "neutralize_stack_action") {
        applied = d.effectResult.status === "neutralized"
          ? f("logRulesStackNeutralized", { card: card(d.effectResult.cardId) }, ["card"])
          : f("logRulesStackTargetMissing", { card: card(d.effectResult.cardId) }, ["card"]);
      }
      if (d.effectResult?.kind === "choice_required" && d.effectResult.choiceKind === "chain_manifestation") {
        applied = f("logRulesChainWaiting", {
          player: ownerName(d.effectResult.playerId),
          zone: z(d.effectResult.fromZone),
          source: card(d.source?.cardId),
        }, ["source"]);
      }
      if (d.effectResult?.kind === "choice_required" && d.effectResult.choiceKind === "stack_counter_payment") {
        applied = f("logRulesStackPaymentRequested", {
          player: ownerName(d.effectResult.playerId),
          source: card(d.source?.cardId),
          target: card(d.effectResult.targetCardId),
        }, ["source", "target"]);
      }
      if (d.effectResult?.kind === "choice_required" && d.effectResult.choiceKind === "stack_copy_targets") {
        applied = f("logRulesCopyWaiting", {
          player: ownerName(d.effectResult.playerId),
          source: card(d.source?.cardId),
          target: card(d.effectResult.targetCardId),
        }, ["source", "target"]);
      }
      if (d.effectResult?.kind === "copy_stack_action" && d.effectResult.status === "copied") {
        applied = f("logRulesCopyCreated", {
          player: ownerName(d.controllerId),
          target: card(d.effectResult.cardId),
          targeting: "",
        }, ["target"]);
      }
      if (d.effectResult?.kind === "chain_manifestation" && d.effectResult.status === "no_eligible_card") {
        applied = f("logRulesChainEmpty", { zone: z(d.effectResult.fromZone) });
      }
      return [resolved, source, sourceResult, applied, active].filter(Boolean).join(" ");
    }
    case "rules_choice_resolved":
      if (d.kind === "simultaneous_stack_order") return f("logRulesSimultaneousOrdered", {
        player: ownerName(d.playerId),
        count: (d.actionIds || []).length,
      });
      if (d.kind === "persist_first_manifestation") return f("logRulesPersistChosen", {
        player: ownerName(d.playerId),
        card: card(d.cardId),
      }, ["card"]);
      if (d.kind === "effect_memory_return") return f(
        d.status === "returned" ? "logRulesMemoryReturned" : "logRulesMemoryDeclined",
        { player: ownerName(d.playerId), card: card(d.cardId) },
        ["card"],
      );
      if (d.kind === "effect_payment") return f(
        d.status === "paid" ? "logRulesEffectPaymentPaid" : "logRulesEffectPaymentDeclined",
        { player: ownerName(d.playerId), card: card(d.sourceCardId) },
        ["card"],
      );
      if (d.kind === "effect_memory_payment") return f(
        d.status === "paid" ? "logRulesMemoryPaymentPaid" : "logRulesMemoryReturned",
        { player: ownerName(d.playerId), card: card(d.cardId) },
        ["card"],
      );
      if (d.kind === "immediate_effect_payment") return f(
        d.status === "paid"
          ? "logRulesImmediatePaymentPaid"
          : "logRulesImmediatePaymentDeclined",
        {
          player: ownerName(d.playerId),
          card: card(d.sourceCardId),
        },
        ["card"],
      );
      if (d.kind === "stack_copy_targets") return f("logRulesCopyCreated", {
        player: ownerName(d.playerId), target: card(d.targetCardId), targeting: "",
      }, ["target"]);
      if (d.kind === "stack_counter_payment") {
        if (d.status === "paid") return f("logRulesStackPaymentPaid", {
          player: ownerName(d.playerId), target: card(d.targetCardId),
        }, ["target"]);
        if (d.status === "cancelled") return f("logRulesStackEffectCancelled", {
          player: ownerName(d.playerId), target: card(d.targetCardId),
        }, ["target"]);
        if (d.status === "neutralized") return f("logRulesStackCardNeutralizedAfterDecline", {
          player: ownerName(d.playerId), target: card(d.targetCardId),
        }, ["target"]);
        return f("logRulesStackPaymentTargetMissing", { target: card(d.targetCardId) }, ["target"]);
      }
      if (d.kind === "chain_manifestation") {
        if (d.status === "declined") return f("logRulesChainDeclined", {
          player: ownerName(d.playerId), source: card(d.sourceCardId),
        }, ["source"]);
        if (d.status === "chained") return f("logRulesChained", {
          player: ownerName(d.playerId), card: card(d.cardId),
          zone: z(d.fromZone), source: card(d.sourceCardId),
        }, ["card", "source"]);
      }
      if (d.kind === "confrontation_destination") return f("logRulesConfrontationDestination", {
        card: card(d.cardId),
        destination: translateFor(d.destination === "interzone" ? "interzone" : "rulesDeckBottom", language),
      }, ["card"]);
      if (d.kind === "confrontation_replace_interzone") return f("logRulesConfrontationReplacement", {
        card: card(d.cardId), replaced: card(d.replacedCardId),
      }, ["card", "replaced"]);
      if (d.kind === "recovery_shared_choice") {
        return d.option === "lose_points_10"
          ? f("logRulesRecoveryChoicePoints", {
              player: ownerName(d.playerId), score: d.score, source: card(d.sourceCardId),
            }, ["source"])
          : f("logRulesRecoveryChoiceDiscard", {
              player: ownerName(d.playerId), count: d.count,
              cards: (d.cardIds || []).map(card).join(", "), source: card(d.sourceCardId),
            }, ["cards", "source"]);
      }
      return f(Number(d.drawCount || 0) > 0 ? "logRulesChoiceDiscardDraw" : "logRulesChoiceResolved", {
        player: ownerName(d.playerId),
        count: d.count,
        draw: Number(d.drawCount || 0),
        source: card(d.sourceCardId),
      }, ["source"]);
    case "rules_confrontation_compared": {
      const totals = Object.entries(d.totals || {}).map(([playerId, value]) => `${ownerName(playerId)} ${value}`).join(" · ");
      return d.stalemate
        ? f("logRulesConfrontationStalemate", { totals })
        : f("logRulesConfrontationWinner", { player: ownerName(d.winnerId), totals });
    }
    case "rules_confrontation_cleanup": {
      const cleanup = d.stalemate
        ? f("logRulesConfrontationMovedStalemate")
        : f("logRulesConfrontationCleanup", { player: ownerName(d.winnerId), count: (d.captured || []).length });
      const support = (d.supportExiled || []).map((movement) => (
        f("logRulesSupportWinnerExiled", { card: card(movement.cardId) }, ["card"])
      )).join(" ");
      const supportEffects = (d.supportResolved || []).map((result) => (
        result.kind === "opponent_vessel_score"
          ? f("logRulesSupportVesselScore", {
              card: card(result.cardId), player: ownerName(result.playerId),
              delta: result.delta, score: result.score,
            }, ["card"])
          : result.kind === "opponent_vessel"
            ? f("logRulesSupportOpponentVessel", {
                card: card(result.cardId), player: ownerName(result.playerId),
              }, ["card"])
            : ""
      )).filter(Boolean).join(" ");
      const persisted = (d.persisted || []).map((result) => (
        f("logRulesPersisted", { card: card(result.cardId) }, ["card"])
      )).join(" ");
      return [cleanup, support, supportEffects, persisted].filter(Boolean).join(" ");
    }
    case "rules_field_zone_changed": return f("logRulesEnteredConfrontation", { card: card(d.cardId) }, ["card"]);
    case "rules_priority_rolled": return f("logRulesPriorityRolled", {
      player: ownerName(d.playerId),
      rolls: Object.entries(d.rolls || {}).map(([id, value]) => `${ownerName(id)} ${value}`).join(" · "),
    });
    case "rules_phase_advanced": {
      const lines = phaseLogLinesFor(d, language);
      const label = [lines.phase, lines.step].filter(Boolean).join(" · ") || d.phaseId || "?";
      const advanced = f("logRulesPhaseAdvanced", { phase: label, turn: d.turn || 1 });
      const rematch = d.rematchStarted ? ` ${f("logRulesRematchStarted")}` : "";
      const expired = d.expiredEffectIds?.length
        ? ` ${f("logRulesOngoingExpired", { count: d.expiredEffectIds.length })}`
        : "";
      return `${advanced}${expired}${rematch}`;
    }
    case "shuffle": return f("logShuffle", { zone: z(d.zone), cross });
    case "reorder": return f("logReorder", { zone: z(d.zone), cross });
    case "reveal": return f("logReveal", { count: d.count, zone: z(d.zone), cross, request: viaRequest(d.requestedBy) });
    case "scry": return f("logScry", { count: d.count });
    case "search_zone": return f("logSearch", { zone: z(d.zone), count: d.count, warning: d.requiresShuffle ? translateFor("logShuffleExpected", language) : "" });
    case "search_followed_by_shuffle": return f("logSearchResolved", { zone: z(d.zone) });
    case "search_without_shuffle": return f("logSearchUnshuffled", { zone: z(d.zone), action: translateFor(`logAction_${d.followupAction}`, language) || d.followupAction });
    case "move_card": return f("logMoveCard", { card: card(d.cardId), from: z(d.fromZone), to: z(d.toZone), request: viaRequest(d.requestedBy) }, ["card"]);
    case "place_card": return d.asSupport
      ? f("logPlaceSupportCard", { card: card(d.cardId), from: z(d.fromZone) }, ["card"])
      : f("logPlaceCard", { card: card(d.cardId), from: z(d.fromZone), face: faceState(d.faceUp) }, ["card"]);
    case "copy_card": return f("logCopyCard", { card: card(d.cardId) }, ["card"]);
    case "move_battlefield_item": return f("logMoveFieldCard");
    case "reorder_battlefield_item": return f("logReorderFieldCard");
    case "flip_card": return f("logFlipCard", { card: card(d.cardId), face: faceState(d.faceUp) }, ["card"]);
    case "remove_battlefield_item": return d.copyCard ? f("logRemoveCopy", { card: card(d.cardId) }, ["card"]) : d.tokenCard ? f("logRemoveTokenCard") : f("logRemoveFieldCard", { card: card(d.cardId), to: z(d.toZone), face: faceState(d.faceUp) }, ["card"]);
    case "create_token_card": return f("logCreateTokenCard", { temperament: translateFor("temperament" + d.temperament[0].toUpperCase() + d.temperament.slice(1), language), power: `${d.power > 0 ? "+" : ""}${d.power}` });
    case "create_essence_token":
      if (d.neutral) return f("logCreateNeutralCounter", { label: d.label || translateFor("neutralToken", language), count: `${d.count > 0 ? "+" : ""}${d.count}` });
      return f("logCreateEssence", { count: d.count, temperament: translateFor("temperament" + d.temperament[0].toUpperCase() + d.temperament.slice(1), language) });
    case "rename_token": return f("logRenameToken");
    case "mulligan": return f(d.scoreCost ? "logMulliganPaid" : "logMulligan", {
      count: d.count, cost: d.scoreCost, score: d.score,
    });
    case "rules_player_ready": return f("logRulesPlayerReady", { player: ownerName(e.actorId) });
    case "rules_match_started": return f("logRulesMatchStarted");
    case "add_token": return f("logAddToken");
    case "move_token": return f("logMoveToken");
    case "remove_token": return f("logRemoveToken");
    case "add_counter": return f("logAdjustCounter", { delta: `${d.delta > 0 ? "+" : ""}${d.delta}` });
    case "reset_counter": return f("logResetCounter");
    case "set_score": return f("logSetScore", { score: d.score });
    case "configure_phases": return f(d.enabled ? "logActivatePhases" : "logDeactivatePhases", { advanced: d.enabled && d.advanced ? translateFor("logAdvancedSuffix", language) : "" });
    case "pass_phase": {
      const lines = phaseLogLinesFor(d, language);
      const label = [lines.phase, lines.step].filter(Boolean).join(" · ") || d.phaseId || d.phase || "?";
      if (d.action === "cancelled") return f("logCancelPass");
      if (d.action === "advanced") return f("logAdvancePhase", { phase: label, turn: d.turn || 1 });
      return f("logPassPhase", { phase: label });
    }
    case "end_session": return f("logEndSession");
    case "create_tournament": return f("logCreateTournament");
    case "role_joined": return f("logRoleJoined", { role: translateFor(d.role || "participant", language), seat: Number.isInteger(d.seat) ? ` (P${d.seat + 1})` : "" });
    case "leave_session": return f("logLeftSession");
    case "player_disconnected": return f("logDisconnected");
    case "start_tournament": return f("logStartTournament");
    case "end_tournament": return f("logEndTournament");
    case "update_tournament_policy": return f("logUpdatePolicy", { banned: d.bannedCount, groups: d.restrictedGroupCount });
    case "add_stroke": return f("logAddStroke");
    case "remove_stroke": return f("logRemoveStroke");
    case "remove_strokes_in_rect": return f("logRemoveStrokes", { count: d.count });
    case "clear_own_strokes": return f("logClearStrokes");
    case "roll_dice": return d.mode === "d6" ? f("logRollDice", { count: d.results.length, results: d.results.join(", ") }) : f("logFlipCoin", { count: d.results.length, results: d.results.join(", ") });
    case "reset_board": return f("logResetBoard");
    case "chat_message": return f("logChat", { text: d.text });
    default: return f("logUnknown", { type: e.type });
  }
}

function wireLogCardNames(container) {
  container.querySelectorAll("[data-log-card]").forEach((element) => {
    const cardId = element.dataset.logCard;
    element.addEventListener("mouseenter", () => showCardPreview(cardId, element));
    element.addEventListener("mouseleave", hideCardPreview);
    element.addEventListener("click", () => showInspect(cardId));
  });
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
      <div class="what">${formatLogEntry(e, { html: true })}</div>
      <div class="detail">${esc(JSON.stringify(e.details || {}))}</div>
    </div>`
        )
        .join("")
    : `<p>${esc(t("logEmpty"))}</p>`;
  wireLogCardNames(box);
  $("#logPanel").classList.remove("hidden");
}

function downloadLog(entries) {
  const lines = entries.map((e) => `[${new Date(e.timestamp * 1000).toLocaleString("en-GB")}] ${formatLogEntry(e, { language: "en" })} ${JSON.stringify(e.details || {})}`);
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
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    const editingText = event.target?.closest?.("input, textarea, select, [contenteditable='true']");
    if (event.code === "Space") {
      if (editingText) return;
      if (!latestState || isObserver) return;
      event.preventDefault();
      if (event.repeat) return;
      toggleHandHidden();
      return;
    }
    if (event.target?.closest?.("input, textarea, select, button, [contenteditable='true']")) return;
    if (event.code === "KeyI") {
      event.preventDefault();
      toggleInspectPanel();
    } else if (event.code === "KeyH") {
      event.preventDefault();
      $("#hideInterfaceBtn").click();
    } else if (event.code === "KeyJ") {
      event.preventDefault();
      $("#hideCodesBtn").click();
    }
  });
  paintStaticText();
  initLanguageSwitch();
  initConfirmPanel();
  initSocialLinks();
  initPileBrowser();
  await loadCardDatabase();
  await loadStarterDecks();
  renderStarterDecks();
  initJoinScreen();
  initTournamentControls();
  initImportPanel();
  initCombatChrome();
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
  initRarityEffectsToggle();
  initChat();
  initViewToggles();
  $("#playerLogCloseBtn").onclick = () => $("#playerLogPanel").classList.add("hidden");
  $("#playerLogCloseBtn").textContent = t("close");
  $("#logCloseBtn").onclick = () => $("#logPanel").classList.add("hidden");
  $("#inspectCloseBtn").onclick = () => {
    $("#inspectPanel").classList.add("hidden");
    $("#gameScreen").classList.remove("inspect-open");
  };
  $("#revealCloseBtn").onclick = () => {
    $("#revealPanel").classList.add("hidden");
    setMyActivity(null);
  };
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
  $("#rulesChoiceCloseBtn").onclick = () => closeRulesChoicePanel();
}

boot();
