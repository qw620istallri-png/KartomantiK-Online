// Language, join screen, server connection, messages and the main render.
// Loaded before app.js: declarations only, nothing runs at load time.

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
  $("#concedeBtn").textContent = t("concede");
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
  updateHandSortButton();
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
    ws.send(JSON.stringify({ type: "join", createNew, createTournament, rulesBeta, banListEnabled, deckPolicy: joinPayload.deckPolicy, code: joinedCode, name: joinedName, clientId, sandbox: joinPayload.sandbox }));
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
    const rulesEffectVfxChanges = prepareRulesEffectVfxChanges(msg);
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
      // queue the VFX first so freshly rendered cards know how long to wait
      playRulesVfxBatch(rulesVfxBatch);
      renderAll();
      renderStrokes();
      playRulesEffectVfxChanges(rulesEffectVfxChanges);
      if (pendingSupportDrop) {
        const pending = pendingSupportDrop;
        if (pending.itemId) {
          const supported = (msg.battlefield || []).find((item) => item.id === pending.itemId);
          if (!supported || Date.now() - pending.at > 120000) pendingSupportDrop = null;
          else if (!pendingRulesBoardFlow && Number(supported.supportUntilTurn || 0) === Number(msg.phaseTracker?.turn || 0)) {
            pendingSupportDrop = null;
            resolveDrop(pending.ctx, pending.clientX, pending.clientY);
          }
        } else {
        const stillInHand = (msg.players?.[myPlayerId]?.zones?.hand?.cards || []).includes(pending.ctx.cardId);
        if (!stillInHand || Date.now() - pending.at > 120000) pendingSupportDrop = null;
        else if (!pendingRulesBoardFlow && handCardIsPlayable(pending.ctx.cardId)
          && (msg.rulesEngine?.playPermissions || []).some((permission) => permission.playerId === myPlayerId && permission.cardId === pending.ctx.cardId)) {
          pendingSupportDrop = null;
          resolveDrop(pending.ctx, pending.clientX, pending.clientY);
        }
        }
      }
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
    releaseRulesBoardFlowAfterError();
    if (rulesDeckReorderRetry) rulesDeckReorderRetry();
    // a refused destination leaves the other destinations usable (drag or click)
    $$("#rulesChoicePanel [data-rules-destination]:disabled").forEach((button) => { button.disabled = false; });
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
  if (outcome?.reason === "concession") {
    const loserName = latestState?.players?.[(outcome.loserIds || [])[0]]?.name || "—";
    return rulesText("rulesConcessionLoss", { player: loserName });
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

let gameEndDismissed = false;

const lastVesselScores = new Map();

// Floating "+N" over a player's points badge whenever it changes
function animateScoreDeltas() {
  const players = latestState?.players || {};
  Object.values(players).forEach((p) => {
    const value = receptaclePoints(p.zones.receptacle, p.score);
    const previous = lastVesselScores.get(p.id);
    lastVesselScores.set(p.id, value);
    if (previous === undefined || previous === value || rulesVfxReducedMotion()) return;
    const badge = document.querySelector(`#gameScreen.ui-beta [data-ub-vessel="${CSS.escape(p.id)}"]`)
      || document.querySelector(`[data-vessel-badge="${CSS.escape(p.id)}"]`);
    if (!badge) return;
    const rect = badge.getBoundingClientRect();
    const delta = value - previous;
    const float = document.createElement("div");
    float.className = `score-float ${delta > 0 ? "gain" : "loss"}`;
    float.textContent = `${delta > 0 ? "+" : ""}${delta}`;
    float.style.left = `${rect.left + rect.width / 2}px`;
    // near the top edge the number rises downwards, so it stays on screen
    const rise = rect.top < 90 ? -1 : 1;
    float.style.top = `${rise > 0 ? rect.top : rect.bottom}px`;
    document.body.appendChild(float);
    const scoreDelay = Math.min(1500, rulesVfxQueueRemaining());
    window.setTimeout(() => spawnVfxParticles(
      { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 },
      null,
      {
        count: Math.min(16, 6 + Math.abs(delta) * 2),
        spread: 46,
        direction: delta > 0 ? "up" : "down",
        style: delta > 0
          ? { shape: "spark", colors: ["#fffbd0", "#ffe14a", "#f1d377"] }
          : { shape: "ember", colors: ["#ffd0c4", "#ff6a4a", "#a8281a"] },
      },
    ), scoreDelay);
    badge.animate([
      { transform: "scale(1)" }, { transform: "scale(1.3)", offset: 0.3 }, { transform: "scale(1)" },
    ], { duration: vfxMs(600), delay: Math.min(1500, rulesVfxQueueRemaining()) });
    float.animate([
      { transform: `translate(-50%, ${6 * rise}px) scale(.6)`, opacity: 0 },
      { transform: `translate(-50%, ${-14 * rise}px) scale(1.25)`, opacity: 1, offset: 0.25 },
      { transform: `translate(-50%, ${-52 * rise}px) scale(1)`, opacity: 0 },
    ], { duration: vfxMs(1400), delay: Math.min(1500, rulesVfxQueueRemaining()), easing: "ease-out", fill: "both" })
      .finished.then(() => float.remove(), () => float.remove());
  });
}

function renderGameEndOverlay() {
  const overlay = $("#gameEndOverlay");
  if (!overlay) return;
  if (!latestState?.ended) {
    gameEndDismissed = false;
    overlay.classList.add("hidden");
    return;
  }
  if (gameEndDismissed) {
    overlay.classList.add("hidden");
    return;
  }
  const outcome = latestState.rulesEngine?.outcome;
  const scores = outcome?.scores || null;
  const winners = new Set(outcome?.winnerIds || []);
  $("#gameEndTitle").textContent = scores || outcome?.reason === "concession" ? t("rulesGameEnded") : t("sessionEnded");
  const winnerNames = [...winners].map((id) => latestState.players?.[id]?.name || id);
  $("#gameEndResult").textContent = scores
    ? (outcome.draw ? t("rulesResultDraw") : `${winnerNames[0] || "—"} ${t("rulesResultWins")}`)
    : (outcome ? rulesOutcomeText(outcome) : "");
  $("#gameEndPlayers").innerHTML = scores ? Object.entries(scores).map(([playerId, score]) => `
    <div class="game-end-player${winners.has(playerId) && !outcome.draw ? " is-winner" : ""}" style="--owner-color:${playerColor(playerId)}">
      <strong class="game-end-name">${esc(latestState.players?.[playerId]?.name || playerId)}</strong>
      <span class="game-end-total" data-count-to="${score.total}">0</span>
      <span class="game-end-unit">${esc(t("vesselPoints"))}</span>
      <ul class="game-end-breakdown">
        <li><span>${esc(t("rulesVessel"))}</span><b>${score.vesselPoints}</b></li>
        <li><span>${esc(t("rulesEffects"))}</span><b>${score.effectPoints}</b></li>
        <li><span>${esc(t("rulesDeckBonus"))}</span><b>${score.deckBonus}</b></li>
      </ul>
    </div>`).join("") : "";
  const canReplay = latestState.mode !== "tournament" && !isObserver && mySeat() === 0;
  const replay = $("#gameEndReplayBtn");
  replay.textContent = t("rulesEndReplay");
  replay.classList.toggle("hidden", latestState.mode === "tournament" || isObserver);
  replay.disabled = !canReplay;
  $("#gameEndHint").textContent = t("rulesEndReplayHint");
  $("#gameEndHint").classList.toggle("hidden", canReplay || latestState.mode === "tournament" || isObserver);
  $("#gameEndQuitBtn").textContent = t("rulesEndQuit");
  $("#gameEndCloseBtn").title = t("rulesEndClose");
  overlay.classList.remove("hidden");
  if (overlay.dataset.countedFor !== JSON.stringify(scores || {})) {
    overlay.dataset.countedFor = JSON.stringify(scores || {});
    $$("#gameEndPlayers [data-count-to]").forEach((counter) => countUpNumber(counter, Number(counter.dataset.countTo), 1400, 350));
  } else {
    $$("#gameEndPlayers [data-count-to]").forEach((counter) => { counter.textContent = counter.dataset.countTo; });
  }
}

function initGameEndOverlay() {
  $("#gameEndReplayBtn").onclick = () => {
    gameEndDismissed = false;
    send({ type: "reset_board" });
  };
  $("#gameEndQuitBtn").onclick = () => {
    if (!isObserver && mySeat() !== 0) send({ type: "leave_session" });
    leaveSession();
  };
  $("#gameEndCloseBtn").onclick = () => {
    gameEndDismissed = true;
    $("#gameEndOverlay").classList.add("hidden");
  };
}

function renderAll() {
  if (!latestState) return;
  renderBattlefield();
  renderHandTray();
  renderOppRows();
  renderMyInfoStrip();
  $("#tokenToolbar")?.classList.toggle("hidden", Boolean(latestState?.rulesEngine?.enabled));
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
  $("#concedeBtn").classList.toggle("hidden", isObserver || !latestState.players?.[myPlayerId] || playerIds.length < 2 || latestState.ended || (isTournament && latestState.tournament?.status !== "active"));
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
  renderGameEndOverlay();
  animateScoreDeltas();
}

// Always-visible row(s), top-left: a regular player only ever needs their
// one opponent's row (their own hand is already visible in the tray below);
// an observer has no "own hand" to skip, so they get one row per player.
// Broadcasts "what menu am I in" so the opponent's row can show e.g.
// "scrying…" instead of leaving them wondering if the other side has gone
// AFK. Never private (it's just a menu name, no card identities), so no
// permission gate is needed either side.
let myActivity = null;
