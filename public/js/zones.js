// Header, zone blocks and on-field piles.
// Loaded before app.js: declarations only, nothing runs at load time.

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
  applyVfxSpeedPreference();
  applySoundPreference();
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
  // Beta (assisted rules): the engine draws, shuffles and moves cards; piles
  // can only be consulted (Limbo, Vessel, own Exile), never the decks
  if (latestState?.rulesEngine?.enabled) {
    if (zone === "deck") return "";
    return `<button data-open-pile-browser="${esc(ownerId)}:${zone}">${esc(t("search"))}</button>`;
  }
  if (zone === "deck") {
    buttons.push(`<button data-draw="${esc(ownerId)}">${esc(t("drawOne"))}</button>`);
    buttons.push(`<button data-draw-limit="${esc(ownerId)}">${esc(t("drawToLimit"))}</button>`);
    buttons.push(`<button data-discard-top="${esc(ownerId)}" title="${esc(t("discardTop"))}">${esc(t("handDiscard"))}</button>`);
  }
  buttons.push(`<button data-shuffle="${esc(ownerId)}:${zone}">${esc(t("shuffle"))}</button>`);
  if (zone === "receptacle") {
    buttons.push(`<button data-discard-random="${esc(ownerId)}:${zone}" title="${esc(t("discardRandomHint"))}">${esc(t("discardRandom"))}</button>`);
  }
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
    zone === "receptacle" && !isObserver && !latestState?.rulesEngine?.enabled
      ? `<div class="pile-score-adjust">
          <button data-score-delta="${esc(ownerId)}:-10">-10</button><button data-score-delta="${esc(ownerId)}:-5">-5</button>
          <button data-score-delta="${esc(ownerId)}:-1">-1</button><button data-score-delta="${esc(ownerId)}:1">+1</button>
          <button data-score-delta="${esc(ownerId)}:5">+5</button><button data-score-delta="${esc(ownerId)}:10">+10</button>
        </div>`
      : "";
  // shared zones (limbo/exile/vessel) show the actual face of the most
  // recently entered card (index 0, same "top" convention as the deck); the
  // deck itself always stays card-back regardless of who's viewing
  const uncoveredTop = zone === "deck" ? latestState?.rulesEngine?.uncoveredTops?.[ownerId] : null;
  const topCardId = uncoveredTop || (zone !== "deck" && count > 0 ? (zoneData.cards || [])[0] : null);
  const topCardOwnerId = topCardId ? (zoneData?.owners?.[topCardId] || ownerId) : null;
  const canDragTop = pilesLocked && !isObserver && ownerId === myPlayerId && (["graveyard", "exile", "receptacle"].includes(zone) || (zone === "deck" && Boolean(uncoveredTop)));
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
  // while it can be played, the card waits in the hand (rulesGhostHandCards), not beside the pile
  const conditionalCard = zonePermission && !rulesLimboPermissionPlayable(zonePermission.cardId) ? `<div role="button" tabindex="0"
      class="rules-zone-play-card${permissionPlayable ? " is-playable" : ""}"
      data-rules-zone-play-card="${esc(zonePermission.cardId)}"
      data-rules-zone-play-owner="${esc(ownerId)}"
      data-rules-zone-play-enabled="${permissionPlayable ? "true" : "false"}"
      title="${esc(t(permissionPlayable ? "rulesSupportFromLimbo" : "rulesSupportFromLimboHint"))}">
      <img src="${esc(cardImage(zonePermission.cardId))}" alt="${esc(cardName(zonePermission.cardId))}">
      <span>${esc(t("rulesSupportBadge"))}</span>
    </div>` : "";
  const limboPlayButton = zone === "graveyard" && ownerId === myPlayerId && !isObserver
    && latestState?.rulesEngine?.enabled && rulesLimboPlayMode()
    ? `<button type="button" class="limbo-play-btn" data-limbo-play-open>${esc(t("limboPlayButton"))}</button>` : "";
  return `<div class="field-pile ${count === 0 ? "empty" : ""}"${dropAttr} data-field-pile="${esc(key)}" data-zone="${esc(zone)}" data-override-key="${esc(overrideKey)}" style="left:${pos.x}px;top:${pos.y}px;--owner-color:${playerColor(ownerId)}">
    ${scoreAdjust}
    <div class="pile-trigger" data-pile-trigger="${esc(key)}">
      <span class="pile-count">${count}</span>
      <div class="pile-card">${topCardHtml}</div>
      <span class="pile-label">${esc(t(zone))}</span>
      ${pointsBadge}
    </div>
    ${conditionalCard}
    ${limboPlayButton}
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
    el.onclick = () => {
      const [ownerId, zone] = el.dataset.pileTrigger.split(":");
      // beta table: a click on a public pile opens its search at once (decks keep their menu)
      if (window.uiBeta?.active() && zone !== "deck" && latestState?.players?.[ownerId]?.zones?.[zone]?.cards) {
        searchPile(ownerId, zone);
        return;
      }
      toggleZone(el.dataset.pileTrigger);
    };
  });
  $$("[data-pile-top-card]").forEach((el) => {
    const pile = el.closest("[data-field-pile]");
    const [fromOwnerId, fromZone] = pile.dataset.fieldPile.split(":");
    bindCardDragSource(el, {
      kind: "card", cardId: el.dataset.pileTopCard, cardOwnerId: el.dataset.cardOwner || fromOwnerId,
      fromOwnerId, fromZone,
    });
  });
  $$("[data-limbo-play-open]").forEach((el) => {
    el.onclick = (event) => {
      event.stopPropagation();
      openLimboPlayPanel();
    };
    el.onpointerdown = (event) => event.stopPropagation();
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
