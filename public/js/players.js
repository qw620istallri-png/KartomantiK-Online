// Player strips, opponent rows, hand view, pile browser and hover zoom.
// Loaded before app.js: declarations only, nothing runs at load time.

// a field card that counts as a Manifestation: tokens, and Wills turned into one (Rinq, Ju Lien)
function fieldItemIsManifestation(item) {
  return Boolean(item?.isTokenCard || item?.willManifestation || cardsById.get(item?.cardId)?.type === "manifestation");
}

// Total Power of a player's face-up Manifestations in the Confrontation Zone
function confrontationPowerOf(playerId) {
  return (latestState?.battlefield || []).reduce((total, item) => {
    if (!item.faceUp || item.fieldZone !== "confrontation") return total;
    if ((item.controllerId || item.ownerId) !== playerId) return total;
    if (!fieldItemIsManifestation(item)) return total;
    // the server's own count when it sends one (never below 0, ignored Power = 0)
    const power = Number(item.confrontationPower ?? Math.max(0, Number(item.effectivePower ?? cardsById.get(item.cardId)?.power ?? item.power)));
    return total + (Number.isFinite(power) ? power : 0);
  }, 0);
}

// The "active" Temperament: the one of the last Manifestation the player added
// to the Confrontation Zone (the Resolution tiebreak colour).
function activeTemperamentOf(playerId) {
  const battlefield = latestState?.battlefield || [];
  let best = null;
  battlefield.forEach((item, index) => {
    if (!item.faceUp || item.fieldZone !== "confrontation") return;
    if ((item.controllerId || item.ownerId) !== playerId) return;
    if (!fieldItemIsManifestation(item)) return;
    const order = Number(item.confrontationOrder || 0);
    if (!best || order > best.order || (order === best.order && index > best.index)) {
      best = { item, order, index };
    }
  });
  if (!best) return "";
  const temperament = best.item.effectiveTemperament || best.item.temperament || cardsById.get(best.item.cardId)?.temperaments?.[0];
  return temperament ? `<img class="active-temperament-badge" src="${esc(temperamentSymbol(temperament))}" alt="${esc(temperament)}" title="${esc(t("rulesActiveTemperament"))}">` : "";
}
function essencePoolForPlayer(playerId) {
  const pool = new Map();
  (latestState?.tokens || []).forEach((token) => {
    const amount = Number(token.counters?.essence || 0);
    if (token.ownerId !== playerId || !token.isEssence || token.isNeutralCounter || !token.temperament || amount <= 0) return;
    pool.set(token.temperament, (pool.get(token.temperament) || 0) + amount);
  });
  return pool;
}
let essenceQuickHeldOpen = false;
function essenceQuickPickerMarkup(playerId) {
  if (isObserver || playerId !== myPlayerId || latestState?.rulesEngine?.enabled) return "";
  return `<span class="essence-quick${essenceQuickHeldOpen ? " is-open" : ""}" data-essence-quick>
    <button type="button" class="essence-quick-add" data-essence-quick-add aria-label="${esc(t("essenceAddOne"))}" title="${esc(t("essenceAddOne"))}" aria-expanded="${String(essenceQuickHeldOpen)}">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>
    </button>
    <span class="essence-quick-popover" role="menu" aria-label="${esc(t("essenceAddOne"))}">
      ${TEMPERAMENTS.map((temperament) => `<button type="button" role="menuitem" data-create-essence="${esc(temperament.key)}" title="${esc(t(`temperament${temperament.key[0].toUpperCase()}${temperament.key.slice(1)}`))}"><img src="${esc(temperamentSymbol(temperament.key))}" alt=""></button>`).join("")}
    </span>
  </span>`;
}
function createQuickEssence(temperament) {
  if (isObserver || !myPlayerId || latestState?.rulesEngine?.enabled || !TEMPERAMENTS.some((entry) => entry.key === temperament)) return;
  const view = fieldCenterLogical();
  const center = rotateForSeat(view.x, view.y);
  send({
    type: "create_essence_token", temperament, neutral: false, label: "",
    color: playerColor(myPlayerId), count: 1,
    x: center.x - 26 + Math.random() * 60 - 30,
    y: center.y - 26 + Math.random() * 60 - 30,
  });
}
function removeQuickEssence(temperament) {
  if (isObserver || !myPlayerId || latestState?.rulesEngine?.enabled) return;
  const token = (latestState?.tokens || []).find((entry) => (
    entry.ownerId === myPlayerId && entry.isEssence && !entry.isNeutralCounter
    && entry.temperament === temperament && Number(entry.counters?.essence || 0) > 0
  ));
  if (!token) return;
  if (Number(token.counters?.essence || 0) <= 1) send({ type: "remove_token", tokenId: token.id });
  else send({ type: "add_counter", tokenId: token.id, counterKey: "essence", delta: -1 });
}
function bindEssenceQuickControls(root = document) {
  root.querySelectorAll?.("[data-essence-quick]").forEach((picker) => {
    const add = picker.querySelector("[data-essence-quick-add]");
    add?.addEventListener("click", (event) => {
      event.stopPropagation();
      essenceQuickHeldOpen = !picker.classList.contains("is-open");
      picker.classList.toggle("is-open", essenceQuickHeldOpen);
      add.setAttribute("aria-expanded", String(essenceQuickHeldOpen));
    });
    picker.addEventListener("pointerleave", () => {
      essenceQuickHeldOpen = false;
      picker.classList.remove("is-open");
      add?.setAttribute("aria-expanded", "false");
    });
    picker.querySelectorAll("[data-create-essence]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        createQuickEssence(button.dataset.createEssence);
        essenceQuickHeldOpen = true;
        picker.classList.add("is-open");
        add?.setAttribute("aria-expanded", "true");
      });
    });
  });
  root.querySelectorAll?.("[data-remove-essence]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      removeQuickEssence(button.dataset.removeEssence);
    });
  });
}

function renderMyInfoStrip() {
  const strip = $("#myInfoStrip");
  if (!strip) return;
  const me = !isObserver ? latestState?.players?.[myPlayerId] : null;
  strip.classList.toggle("hidden", !me);
  if (!me) return;
  const handZone = me.zones.hand;
  const handCount = handZone.count !== undefined ? handZone.count : (handZone.cards || []).length;
  strip.innerHTML = `
    <span class="my-info-badge" title="${esc(t("hand"))}"><span class="hand-stack-icon" style="--owner-color:${playerColor(me.id)}"><span class="hand-stack-card"></span><span class="hand-stack-card"></span><span class="hand-stack-card"></span></span><b>${handCount}</b></span>
    <span class="opp-vessel-badge" data-vessel-badge="${esc(me.id)}" title="${esc(t("receptacle"))}">${receptaclePoints(me.zones.receptacle, me.score)} ${esc(t("vesselPoints"))}</span>
    <span class="cz-essence-control">${essenceQuickPickerMarkup(me.id)}<span class="opp-power-badge" title="${esc(t("rulesPowerTotal"))}">⚔ ${confrontationPowerOf(me.id)}${activeTemperamentOf(me.id)}</span></span>`;
  bindEssenceQuickControls(strip);
}

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
          <span class="opp-vessel-badge" data-vessel-badge="${esc(p.id)}" title="${esc(t("receptacle"))}">${vesselPoints} ${esc(t("vesselPoints"))}</span>
          <span class="opp-power-badge" title="${esc(t("rulesPowerTotal"))}">⚔ ${confrontationPowerOf(p.id)}${activeTemperamentOf(p.id)}</span>
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
    const rotate = -Math.max(-15, Math.min(15, center * 3.5));
    const arc = -Math.abs(center) * Math.abs(center) * 1.7;
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
function searchPile(ownerId, zone) {
  const panel = $("#deckBrowserPanel");
  // fresh open, or switching to a DIFFERENT pile: clear any pending
  // staged choices. Re-clicking Search on the pile already open keeps them.
  if (panel.classList.contains("hidden") || panel.dataset.ownerId !== ownerId || panel.dataset.zone !== zone) {
    pileBrowserStaged = new Map();
  }
  send({ type: "search_zone", ownerId, zone });
  setMyActivity("search");
  openPileBrowser(ownerId, zone);
}

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
// Cards listed in a choice panel (search, discard, chain, Limbo picker) are
// small; hovering one shows it at full reading size next to the panel.
const CHOICE_PREVIEW_SELECTOR = ".rules-choice-card, .limbo-play-card, .rules-choice-source, #rulesFloatingCardImg";

let choicePreviewEl = null;

let choicePreviewAnchor = null;

function hideChoiceCardPreview() {
  if (choicePreviewEl) choicePreviewEl.remove();
  choicePreviewEl = null;
  choicePreviewAnchor = null;
}

function showChoiceCardPreview(source) {
  const image = source.tagName === "IMG" ? source : source.querySelector("img");
  if (!image || !image.src) return;
  hideChoiceCardPreview();
  const preview = document.createElement("div");
  preview.className = "choice-card-preview";
  const full = document.createElement("img");
  full.src = image.src;
  full.alt = image.alt || "";
  preview.appendChild(full);
  document.body.appendChild(preview);
  const rect = source.getBoundingClientRect();
  const height = Math.min(window.innerHeight - 24, 560);
  const width = Math.round(height * 5 / 7);
  preview.style.width = `${width}px`;
  preview.style.height = `${height}px`;
  const roomRight = window.innerWidth - rect.right;
  const left = roomRight >= width + 16
    ? rect.right + 12
    : Math.max(8, rect.left - width - 12);
  preview.style.left = `${Math.min(left, window.innerWidth - width - 8)}px`;
  preview.style.top = `${Math.max(12, Math.min(rect.top + rect.height / 2 - height / 2, window.innerHeight - height - 12))}px`;
  choicePreviewEl = preview;
  choicePreviewAnchor = source;
}

function wireCardHoverZoom(el, cloneClassName) {
  let clone = null;
  let removalObserver = null;
  const clearClone = () => {
    if (clone && clone.classList.contains("ub-grow") && el.isConnected) {
      // beta table: the card shrinks back into the hand before it shows again
      const closing = clone;
      closing.classList.remove("zoomed");
      setTimeout(() => {
        closing.remove();
        if (!clone) el.classList.remove("ub-hover-src");
      }, 170);
    } else {
      if (clone) clone.remove();
      el.classList.remove("ub-hover-src");
    }
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
      const scale = Math.max(1, Math.min(
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
      // The clone is laid out at its zoomed size and starts scaled down, so the
      // zoomed card is drawn at full resolution instead of an upscaled (blurry) one.
      clone.style.setProperty("--hand-hover-scale", "1");
      clone.style.setProperty("--hand-hover-from", (1 / scale).toFixed(4));
      clone.style.width = `${cloneWidth * scale}px`;
      clone.style.height = `${cloneHeight * scale}px`;
      clone.style.left = `${centerX - cloneWidth * scale / 2}px`;
      // The zoom transform includes translateY(-10px); offset the base box so
      // the final card is clamped.
      clone.style.top = `${centerY - cloneHeight * scale / 2 + 10}px`;
      if ($("#gameScreen")?.classList.contains("ui-beta")) {
        // beta table: the hand card itself grows out of its place in the fan
        const rotation = getComputedStyle(el).getPropertyValue("--hand-rotate").trim() || "0deg";
        clone.style.setProperty("--hover-dx", `${rect.left + rect.width / 2 - centerX}px`);
        clone.style.setProperty("--hover-dy", `${rect.top + rect.height / 2 - (centerY + 10)}px`);
        clone.style.setProperty("--hover-rot", rotation);
        clone.classList.add("ub-grow");
        el.classList.add("ub-hover-src");
      }
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
        { keepInBeta: true, label: t("inspect"), onSelect: () => showInspect(cardId) },
        copyCardMenuItem(cardId, ownerId, zone),
        ...(zone === "receptacle" && ownerId !== myPlayerId && cardOwnerId === myPlayerId
          && latestState?.rulesEngine?.enabled
          && (activatedAbilitiesByCard.get(cardId) || []).some((ability) => (ability.sourceZones || []).includes("receptacle"))
          ? [{ keepInBeta: true, label: rulesText("rulesActivateCardEffect", { card: cardName(cardId) }), onSelect: () => { $("#deckBrowserCloseBtn").click(); beginRulesHandActivatedAction(cardId, null, "receptacle", ownerId); } }]
          : []),
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
      showContextMenu(event.clientX, event.clientY, betaMenuItems(items));
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
  // a click on empty space (outside the cards and the controls) closes it too
  $("#deckBrowserPanel").addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    if (target.closest(".db-card, button, input, label, .deck-browser-slider-group, .ctx-menu, .context-menu")) return;
    $("#deckBrowserCloseBtn").click();
  });
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
