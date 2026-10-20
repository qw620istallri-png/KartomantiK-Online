// Import panel, chat, game and tournament controls, inspect panel.
// Loaded before app.js: declarations only, nothing runs at load time.

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
    .map((m) => m.channel === "observers"
      ? `<div class="chat-msg chat-msg-observers"><i>${esc(m.byName)}:</i> ${esc(m.text)}</div>`
      : `<div class="chat-msg"><b style="color:${playerColor(m.byId)}">${esc(m.byName)}:</b> ${esc(m.text)}</div>`)
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
    armIdleHide();
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
  // the bar never stays out on its own: 10 s after the last interaction with it, it tucks away
  // (even when a button inside kept the focus or the More menu was left open)
  let idleTimer = null;
  const armIdleHide = () => {
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => {
      if (header.matches(":hover")) { armIdleHide(); return; }
      $("#gameMoreMenu").open = false;
      if (header.contains(document.activeElement)) document.activeElement.blur();
      screen.classList.remove("header-peek");
    }, 10000);
  };
  ["mouseenter", "pointermove", "pointerdown", "keydown", "focusin"].forEach((type) => {
    header.addEventListener(type, armIdleHide, { passive: true });
  });
  hotZone.addEventListener("mouseenter", armIdleHide);
}

function initGameControls() {
  $("#rulesFlowCancelBtn").onclick = cancelRulesBoardFlow;
  $("#rulesFlowDeclineBtn").onclick = () => {
    if (pendingRulesBoardFlow?.mode === "chain") cancelRulesBoardFlow();
    else if (pendingRulesBoardFlow?.mode === "stack_copy_target") resolveRulesStackCopyTargets("keep");
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
  // holding the button (mouse or touch) locks "pass everything", like a held Enter
  let passPointerHold = false;
  let passPointerHoldFired = false;
  $("#passPriorityBtn").addEventListener("pointerdown", (event) => {
    passPointerHoldFired = false;
    if (event.button !== 0 || rulesPassAllLocked()) return;
    startPassAllHold();
    passPointerHold = Boolean(passAllHoldTimer);
  });
  const endPassPointerHold = () => {
    if (!passPointerHold) return;
    passPointerHold = false;
    if (passAllHoldTimer) cancelPassAllHold();
    else passPointerHoldFired = true;
  };
  ["pointerup", "pointercancel", "pointerleave"].forEach((type) => $("#passPriorityBtn").addEventListener(type, endPassPointerHold));
  $("#passPriorityBtn").onclick = () => {
    if (passPointerHoldFired) {
      // the click that ends a completed hold is not a pass
      passPointerHoldFired = false;
      return;
    }
    if (rulesPassAllLocked()) setRulesPassAll(false);
    else toggleMyPhasePass();
  };
  $("#rulesAutoSkip").onchange = (event) => send({ type: "set_rules_auto_skip", enabled: event.target.checked });
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

  $("#concedeBtn").onclick = () => {
    $("#gameMoreMenu")?.removeAttribute("open");
    showConfirm(t("confirmConcede"), () => send({ type: "concede" }));
  };

  $("#leaveSessionBtn").onclick = () => {
    showConfirm(t("confirmLeaveSession"), () => {
      if (!isObserver) send({ type: "leave_session" }); // frees the seat for someone else to join
      leaveSession();
    });
  };

  initGameEndOverlay();
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

let inspectCurrentId = null;

let inspectBoardItemId = null;

function showInspect(cardId, hidden, options = {}) {
  inspectCurrentId = hidden || !cardsById.get(cardId) ? null : cardId;
  if (!options.boardItemId) inspectBoardItemId = null;
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
    // arrow-key browsing keeps the list order stable instead of moving the card to the front
    if (!options.keepOrder || !inspectHistory.includes(cardId)) {
      inspectHistory = [cardId, ...inspectHistory.filter((id) => id !== cardId)].slice(0, 12);
    }
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
  renderInspectAttached(hidden ? null : cardId, options.boardItemId);
  renderInspectHistory();
  $("#inspectPanel").classList.remove("hidden");
  $("#gameScreen").classList.add("inspect-open");
}

// Inspecting a Grimoire-like host lists its placed Wills so they can be played from here
function renderInspectAttached(cardId, boardItemId) {
  const box = $("#inspectAttached");
  if (!box) return;
  const host = cardId
    ? (latestState?.battlefield || []).find((item) => item.id === boardItemId && (item.attachedCards || []).length)
      || (latestState?.battlefield || []).find((item) => item.cardId === cardId && item.ownerId === myPlayerId && (item.attachedCards || []).length)
    : null;
  if (!host) {
    box.classList.add("hidden");
    box.innerHTML = "";
    return;
  }
  const canPlay = host.ownerId === myPlayerId && !isObserver
    && (passiveEffectsByCard.get(host.cardId) || []).some((effect) => effect.kind === "play_attached_wills");
  const cards = [...new Set(host.attachedCards.map((entry) => entry.cardId))];
  box.innerHTML = `<h3>${esc(t("attachedPlayHeading"))}</h3><div class="inspect-attached-list">${cards.map((id) => `<button type="button" class="limbo-play-card" data-inspect-attached="${esc(id)}" title="${esc(cardName(id))}"><img src="${esc(cardImage(id))}" alt="${esc(cardName(id))}"><span>${esc(cardName(id))}</span></button>`).join("")}</div>`;
  box.classList.remove("hidden");
  box.querySelectorAll("[data-inspect-attached]").forEach((button) => {
    button.onclick = () => {
      const id = button.dataset.inspectAttached;
      if (canPlay && ["ephemeral_will", "persistent_will"].includes(cardsById.get(id)?.type)) {
        $("#inspectPanel").classList.add("hidden");
        $("#gameScreen").classList.remove("inspect-open");
        beginRulesBoardAction({ cardId: id, zone: "attached", itemId: host.id, placement: { x: host.x + 40, y: host.y + 40 } });
      } else showInspect(id);
    };
  });
}

// Up/Down walk the inspect history list; Left/Right cycle the cards on the board
function stepInspectHistory(delta) {
  if (!inspectHistory.length) return;
  const index = inspectHistory.indexOf(inspectCurrentId);
  const next = index < 0 ? 0 : Math.max(0, Math.min(inspectHistory.length - 1, index + delta));
  showInspect(inspectHistory[next], false, { keepOrder: true });
}

function inspectableBoardItems() {
  return (latestState?.battlefield || [])
    .filter((item) => item.cardId && !item.isTokenCard && (item.faceUp || (!isObserver && item.ownerId === myPlayerId) || isObserver))
    .map((item) => ({ item, pos: stackedScreenPos(item) || rotateForSeat(item.x, item.y, PILE_W, PILE_H) }))
    .sort((a, b) => (a.pos.x - b.pos.x) || (a.pos.y - b.pos.y))
    .map((entry) => entry.item);
}

function cycleInspectBoard(delta) {
  const items = inspectableBoardItems();
  if (!items.length) return;
  let index = items.findIndex((item) => item.id === inspectBoardItemId);
  if (index < 0) index = items.findIndex((item) => item.cardId === inspectCurrentId);
  const next = index < 0 ? (delta > 0 ? 0 : items.length - 1) : (index + delta + items.length) % items.length;
  const target = items[next];
  showInspect(target.cardId, false, { boardItemId: target.id });
  inspectBoardItemId = target.id;
  const el = document.querySelector(`.bf-card[data-item-id="${CSS.escape(target.id)}"]`);
  if (el) {
    el.classList.add("inspect-cycle-focus");
    setTimeout(() => el.classList.remove("inspect-cycle-focus"), 1400);
  }
}

function renderInspectHistory() {
  $("#inspectHistory").innerHTML = inspectHistory
    .map((cid) => `<button class="inspect-history-card${cid === inspectCurrentId ? " is-current" : ""}" data-inspect-history="${esc(cid)}" title="${esc(cardName(cid))}"><img src="${esc(cardImage(cid))}" alt=""></button>`)
    .join("");
  $$("#inspectHistory [data-inspect-history]").forEach((btn) => {
    btn.onclick = () => showInspect(btn.dataset.inspectHistory);
  });
}

const INSPECT_SIZE_KEY = "ko_inspect_card_w";

const INSPECT_SIZE_MAX = 560;

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
  } else {
    // nothing inspected yet: open it empty, hovering a card then fills it
    showInspect(null, true);
    $("#inspectName").textContent = "";
  }
}

function initInspectToolbar() {
  $("#inspectReopenBtn").title = t("reopenLastInspected");
  $("#inspectReopenBtn").disabled = false; // clickable from the start: opens an empty inspect panel
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
