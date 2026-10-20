// Placing cards, zone buttons, previews, drag and drop and the context menu.
// Loaded before app.js: declarations only, nothing runs at load time.

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
    // no legal target for the entry effect: the card is still played, the effect just has nothing to do
    const draft = buildRulesActionDraft(placementSource, ability);
    const legal = (draft?.structuredTargets || []).filter((target) => (
      !ability.targets?.excludeEventSource || !placementSource?.itemId || target.id !== placementSource.itemId
    ));
    if (!legal.length && !Array.isArray(ability.targets?.groups)) {
      sendCardPlacement(payload, placementSource);
      return;
    }
    beginRulesBoardPlacementTarget(payload, placementSource);
    return;
  }
  const playerIds = Object.keys(latestState?.players || {});
  const candidates = ability.targets?.controller === "opponent" ? playerIds.filter((id) => id !== myPlayerId) : playerIds;
  if (candidates.length === 1) {
    // a single legal player: nothing to choose
    sendCardPlacement(payload, placementSource, [{ kind: "player", playerId: candidates[0] }]);
    return;
  }
  pendingTriggeredPlacement = { payload, source: placementSource, abilityId: ability.id };
  renderRulesChoice();
}

// Manual play in the new table: the Stack is a place cards wait in until a
// player drags them out to resolve them
function manualStackAvailable() {
  return Boolean(window.uiBeta?.active() && !latestState?.rulesEngine?.enabled && !isObserver);
}

function playFromHandToManualStack(cardId) {
  const view = fieldCenterLogical();
  const center = rotateForSeat(view.x, view.y);
  send({ type: "place_card", fromZone: "hand", cardId, faceUp: true, x: center.x - 75, y: center.y - 105, manualStack: true });
}

// Manual play: the Stalemate Zone is read from the position, so a card is
// sent there by moving it onto the next free Stalemate slot
function manualStalemateSlot(excludeId = null) {
  const inside = (item) => {
    const cx = Number(item.x || 0) + 75;
    const cy = Number(item.y || 0) + 105;
    return cx >= 1354 && cx <= 1703 && cy >= 543 && cy <= 1008;
  };
  const used = (latestState?.battlefield || []).filter((item) => item.id !== excludeId && !item.stackedOn && !item.manualStack && inside(item)).length;
  return { x: 1429 + Math.floor(used / 2) * 40, y: 560 + (used % 2) * 230 };
}

function sendItemToManualStalemate(item) {
  const slot = manualStalemateSlot(item.id);
  markLocalBoardMove(item.id);
  send({ type: "move_battlefield_item", itemId: item.id, x: slot.x, y: slot.y, unstack: true, manualStack: false });
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
  $$("[data-discard-random]").forEach((btn) => {
    const [ownerId, zone] = btn.dataset.discardRandom.split(":");
    btn.onclick = (e) => {
      e.stopPropagation();
      send({ type: "move_card", fromOwnerId: ownerId, fromZone: zone, toOwnerId: ownerId, toZone: "graveyard", random: true, toCardOwner: true });
      pulseZone(ownerId, zone);
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
      searchPile(ownerId, zone);
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
        { keepInBeta: true, label: t("inspect"), onSelect: () => showInspect(cardId) },
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
      showContextMenu(event.clientX, event.clientY, betaMenuItems(items));
    });
  });
  $$("[data-preview-card]").forEach((el) => {
    el.addEventListener("mouseenter", () => showCardPreview(el.dataset.previewCard, el));
    el.addEventListener("mouseleave", hideCardPreview);
  });
}

let cardPreviewEl = null;

let cardPreviewAnchor = null;

// the last pointer kind: a tap emulates mouseenter, and a touch screen has no hover to end the preview
let lastPointerType = "mouse";

function showCardPreview(cardId, anchorEl) {
  hideCardPreview();
  if (lastPointerType === "touch") return;
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
  cardPreviewAnchor = anchorEl;
}

function hideCardPreview() {
  if (cardPreviewEl) cardPreviewEl.remove();
  cardPreviewEl = null;
  cardPreviewAnchor = null;
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

function boardDropLogical(fieldEl, clientX, clientY, ctx = null) {
  // UI beta: the drop picks a slot in the zone under the pointer (or the
  // card's natural zone) instead of a raw board position
  if (window.uiBeta?.active()) return window.uiBeta.dropLogical(clientX, clientY, ctx);
  const rect = fieldEl.getBoundingClientRect();
  return rotateForSeat((clientX - rect.left - panX) / zoomLevel - 75, (clientY - rect.top - panY) / zoomLevel - 105, PILE_W, PILE_H);
}

function resolveDrop(ctx, clientX, clientY) {
  const el = document.elementFromPoint(clientX, clientY);
  if (!el) return;
  const zoneEl = el.closest("[data-drop-zone]");
  const fieldEl = el.closest("#battlefieldWrap");
  const handEl = el.closest("#myHandTray");

  if (ctx.kind === "card" && ctx.fromZone === "hand" && !handEl && rulesHandDropChoice()) {
    pickHandDropCard(Number(ctx.handIndex), true);
    return;
  }
  const manualStackDrop = manualStackAvailable() && el.closest("#ubStack");
  if (manualStackDrop && ctx.kind === "battlefield") {
    markLocalBoardMove(ctx.itemId);
    send({ type: "move_battlefield_item", itemId: ctx.itemId, manualStack: true, unstack: true });
    return;
  }
  if (manualStackDrop && ctx.kind === "card" && !rulesHandDropChoice()) {
    const view = fieldCenterLogical();
    const center = rotateForSeat(view.x, view.y);
    send({
      type: "place_card", ownerId: ctx.fromOwnerId, fromZone: ctx.fromZone, cardId: ctx.cardId, faceUp: true,
      x: center.x - 75, y: center.y - 105, manualStack: true,
    });
    return;
  }
  if (ctx.kind === "battlefield") {
    const battlefieldItem = latestState?.battlefield?.find((item) => item.id === ctx.itemId);
    const turnNow = Number(latestState?.phaseTracker?.turn || 0);
    const supportAbility = latestState?.rulesEngine?.enabled && fieldEl && !zoneEl && battlefieldItem
      && battlefieldItem.fieldZone === "interzone" && battlefieldItemControllerId(battlefieldItem) === myPlayerId
      && Number(battlefieldItem.supportUntilTurn || 0) !== turnNow
      ? rulesActivatedAbilitiesForItem(battlefieldItem).find((ability) => String(ability.result?.kind || "").includes("grant_source_support"))
      : null;
    if (supportAbility && !pendingRulesBoardFlow) {
      // Diabolical Giant: dropping it from the Interzone pays the cost first, then the same drop is replayed once it has Support
      if (beginRulesBoardActivatedAction(battlefieldItem, supportAbility.id)) {
        pendingSupportDrop = { ctx, clientX, clientY, at: Date.now(), itemId: battlefieldItem.id };
      }
      return;
    }
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
        markLocalBoardMove(ctx.itemId);
        send({
          type: "move_battlefield_item", itemId: ctx.itemId, stackOnId: anchor.anchorId, offsetX: offset.x, offsetY: offset.y,
          ...(battlefieldItem?.manualStack ? { manualStack: false } : {}),
        });
      } else {
        const logical = boardDropLogical(fieldEl, clientX, clientY, ctx);
        // an explicit unstack, not just an absent stackOnId: dropping in open
        // space is the "detach" gesture, unlike e.g. exhaust which also omits
        // stackOnId but must NOT detach a stacked card as a side effect
        markLocalBoardMove(ctx.itemId);
        send({
          type: "move_battlefield_item", itemId: ctx.itemId, x: logical.x, y: logical.y, unstack: true,
          ...(battlefieldItem?.manualStack ? { manualStack: false } : {}),
        });
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
    const logical = boardDropLogical(fieldEl, clientX, clientY, ctx);
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
    const logical = boardDropLogical(fieldEl, clientX, clientY, ctx);
    const anchor = stackAnchorAt(clientX, clientY, null);
    const card = cardsById.get(ctx.cardId);
    if (latestState?.rulesEngine?.enabled && ctx.fromZone === "field_free" && ctx.ghostHostId) {
      beginRulesBoardAction({
        cardId: ctx.cardId, zone: "battlefield", itemId: ctx.ghostHostId, playFromField: true, fieldFree: true,
        placement: { x: logical.x, y: logical.y },
      });
      return;
    }
    if (latestState?.rulesEngine?.enabled && ctx.fromZone === "attached" && ctx.ghostHostId) {
      beginRulesBoardAction({
        cardId: ctx.cardId, zone: "attached", itemId: ctx.ghostHostId,
        placement: { x: logical.x, y: logical.y },
      });
      return;
    }
    if (
      latestState?.rulesEngine?.enabled
      && ctx.fromZone === "graveyard"
      && ctx.fromOwnerId === myPlayerId
      && ["ephemeral_will", "persistent_will"].includes(card?.type)
      && rulesLimboPlayMode()
    ) {
      beginRulesBoardAction({
        cardId: ctx.cardId,
        zone: "graveyard",
        placement: { x: logical.x, y: logical.y },
      });
      return;
    }
    if (
      latestState?.rulesEngine?.enabled && ctx.fromZone === "graveyard"
      && !(latestState.rulesEngine.playPermissions || []).some((permission) => (
        permission.playerId === myPlayerId && permission.cardId === ctx.cardId && permission.fromZone === "graveyard"
      ))
    ) {
      // beta: a Limbo card only comes back through the engine (Wills above, Support permissions on the card itself)
      showToast(t("rulesBoardCardNotPlayable"), true);
      return;
    }
    if (latestState?.rulesEngine?.enabled && ctx.fromZone === "hand") {
      if (trapPlayableClient(ctx.cardId)) {
        send({ type: "play_first_manifestation_trap", cardId: ctx.cardId });
        return;
      }
      if (["ephemeral_will", "persistent_will"].includes(rulesPlayType(card))) {
        beginRulesBoardAction({
          cardId: ctx.cardId,
          zone: "hand",
          handIndex: ctx.handIndex,
          placement: { x: logical.x, y: logical.y },
        });
        return;
      }
      const firstManifestationPlaceholder = rulesFirstManifestationActive() && Boolean(card?.placeholder);
      if (
        card?.type === "manifestation" && !handCardIsPlayable(ctx.cardId) && handCardHasHandAction(ctx.cardId)
        && (activatedAbilitiesByCard.get(ctx.cardId) || []).some((ability) => String(ability.result?.kind || "").includes("grant_source_support"))
        && !pendingRulesBoardFlow
      ) {
        // Timid Brain: dropping the card pays its cost, then the card is played in Support on its own once the permission resolves
        if (beginRulesHandActivatedAction(ctx.cardId, ctx.handIndex)) {
          pendingSupportDrop = { ctx, clientX, clientY, at: Date.now() };
        }
        return;
      }
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
  if (handSortMode !== "none") return;
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
    // the freshly drawn Recovery hand is not playable before it has landed
    if (ctx.fromZone === "hand" && handDrawLocked() && latestState?.rulesEngine?.enabled) return;
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
// Beta (assisted rules): board cards keep Inspect, the layer order and the
// entries that are the engine's only way to act (flagged keepInBeta); every
// manual option (flip, exhaust, counters, moves...) is hidden.
function betaMenuItems(items) {
  if (!latestState?.rulesEngine?.enabled) return items;
  const kept = [];
  for (const item of items.filter((entry) => entry && (entry.separator || entry.keepInBeta))) {
    if (item.separator && (!kept.length || kept[kept.length - 1].separator)) continue;
    kept.push(item);
  }
  while (kept.length && kept[kept.length - 1].separator) kept.pop();
  return kept;
}

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
