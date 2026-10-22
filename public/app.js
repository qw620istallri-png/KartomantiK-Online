// Load-time state and wiring. The declarations live in js/*.js, loaded first
// (see index.html); this file keeps every statement that runs at load, in order.

// Keep this value in sync with index.html and style.css when a local asset changes.
const STATIC_ASSET_VERSION = "20261022-rules-beta-139-2-1";

{
  const versionEl = document.getElementById("appVersion");
  // "...-beta-138-1" reads "beta 138.1" (a release without a fix number reads "138.0")
  const versionMatch = STATIC_ASSET_VERSION.match(/beta-(\d+(?:-\d+)*)/);
  const versionParts = versionMatch ? versionMatch[1].split("-") : [];
  if (versionParts.length === 1) versionParts.push("0");
  if (versionEl) versionEl.textContent = versionMatch ? "beta " + versionParts.join(".") : STATIC_ASSET_VERSION;
}

const MISSING_CARD_IMAGE = `${DECKOMANTIK_DESERT_ASSET_ROOT}/Missing_Card_Image.png`;

let clientId = localStorage.getItem("ko_clientId");

if (!clientId) {
  clientId = (crypto.randomUUID ? crypto.randomUUID() : String(Math.random())).replace(/-/g, "").slice(0, 24);
  localStorage.setItem("ko_clientId", clientId);
}

// Positive, versioned preference: new and existing browsers start with rarity effects enabled.
let rarityEffectsDisabled = localStorage.getItem(RARITY_EFFECTS_KEY) === "0";

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

let phaseTrackerVisible = localStorage.getItem(PHASE_VISIBILITY_KEY) === "1";

let vfxSpeed = (() => {
  try {
    const stored = localStorage.getItem(VFX_SPEED_KEY);
    return VFX_SPEEDS.includes(stored) ? stored : "normal";
  } catch {
    return "normal";
  }
})();



$("#limboPlayCloseBtn").onclick = () => closeLimboPlayPanel();

$("#limboPlaySearch").oninput = () => renderLimboPlayList();

// A hover preview whose card was removed by a re-render (e.g. the Stack resolved)
// would never get its mouseleave: drop it as soon as the mouse moves
document.addEventListener("mousemove", () => {
  if (choicePreviewEl && choicePreviewAnchor && !choicePreviewAnchor.isConnected) hideChoiceCardPreview();
  if (cardPreviewEl && cardPreviewAnchor && !cardPreviewAnchor.isConnected) hideCardPreview();
}, { passive: true });

// While the Inspect panel is open, hovering a card shows it there directly
document.addEventListener("mouseover", (event) => {
  const panel = $("#inspectPanel");
  if (!panel || panel.classList.contains("hidden") || !(event.target instanceof Element)) return;
  if (event.target.closest("#inspectPanel")) return;
  const hand = event.target.closest("[data-hand-card]");
  const zone = event.target.closest("[data-zone-card]");
  const board = event.target.closest(".bf-card[data-item-id]");
  const opponent = event.target.closest("[data-opponent-hand-card]");
  let cardId = hand?.dataset.handCard || zone?.dataset.zoneCard?.split(":")[2] || opponent?.dataset.opponentHandCard || null;
  if (!cardId && board) {
    const item = (latestState?.battlefield || []).find((candidate) => candidate.id === board.dataset.itemId);
    if (item && (item.faceUp || (item.ownerId === myPlayerId && !isObserver))) cardId = item.cardId;
  }
  if (cardId && cardId !== inspectHistory[0]) showInspect(cardId);
});

document.addEventListener("mouseover", (event) => {
  const target = event.target instanceof Element ? event.target.closest(CHOICE_PREVIEW_SELECTOR) : null;
  if (target) showChoiceCardPreview(target);
  else if (choicePreviewEl) hideChoiceCardPreview();
});

document.addEventListener("click", hideChoiceCardPreview, true);

try {
  const storedSort = localStorage.getItem("ko_hand_sort");
  if (HAND_SORT_CYCLE.includes(storedSort)) handSortMode = storedSort;
} catch (_error) { /* storage unavailable */ }

document.addEventListener("pointerdown", (event) => { lastPointerType = event.pointerType; }, true);

// every card picture put on screen loads smoothly (see watchCardImage)
new MutationObserver((records) => {
  for (const record of records) {
    for (const node of record.addedNodes) {
      if (node.nodeType !== 1) continue;
      if (node.tagName === "IMG") watchCardImage(node);
      else node.querySelectorAll("img").forEach(watchCardImage);
    }
  }
}).observe(document.body, { childList: true, subtree: true });

// during a game, a long press opens the game's own menu, never the browser's
// (image menu, Lens, "Search"); text fields keep theirs
const inTextField = (target) => Boolean(target?.closest?.("input, textarea, [contenteditable='true']"));
document.addEventListener("contextmenu", (event) => {
  if (!event.isTrusted || lastPointerType === "mouse" || $("#gameScreen").classList.contains("hidden") || inTextField(event.target)) return;
  event.preventDefault();
});
document.addEventListener("selectstart", (event) => {
  if (lastPointerType !== "mouse" && !$("#gameScreen").classList.contains("hidden") && !inTextField(event.target)) event.preventDefault();
});

// back online, or back on the tab after the phone slept: retry at once
window.addEventListener("online", () => reconnectNow());
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") reconnectNow();
});

let revealCardWidth = Math.min(REVEAL_SIZE_MAX, Math.max(90, Number(localStorage.getItem(REVEAL_SIZE_KEY)) || 190));

let handViewCardHeight = Math.min(HAND_VIEW_SIZE_MAX, Math.max(100, Number(localStorage.getItem(HAND_VIEW_SIZE_KEY)) || 182));

let handCardHeight = Math.min(HAND_SIZE_MAX, Math.max(70, Number(localStorage.getItem(HAND_SIZE_KEY)) || 170));

let inspectPanelWidth = Math.min(INSPECT_SIZE_MAX, Math.max(220, Number(localStorage.getItem(INSPECT_SIZE_KEY)) || 280));

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
    if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return;
    const editingText = event.target?.closest?.("input, textarea, select, [contenteditable='true']");
    if (event.code === "Space") {
      if (editingText) return;
      if (!latestState || isObserver) return;
      event.preventDefault();
      if (event.repeat) return;
      toggleHandHidden();
      return;
    }
    // the shortcuts keep working while a button/checkbox has focus; only real text fields swallow them
    if (event.target?.closest?.("textarea, select, [contenteditable='true'], input:not([type='checkbox']):not([type='radio']):not([type='button']):not([type='range'])")) return;
    if (event.code === "Enter" || event.code === "NumpadEnter") {
      // Enter is always the "pass phase / priority" button, whichever button has focus
      const passButton = $("#passPriorityBtn");
      if (!latestState || isObserver || !passButton) return;
      if (document.querySelector("#confirmPanel:not(.hidden)")) return;
      if (rulesPassAllLocked()) {
        // a single Enter gives control back
        event.preventDefault();
        if (!event.repeat) setRulesPassAll(false);
        return;
      }
      // a held Enter (3 s) locks "pass everything"
      if (!event.repeat) startPassAllHold();
      if (passButton.disabled || passButton.offsetParent === null) return;
      event.preventDefault();
      // already passed: a second Enter must not cancel the pass
      if (!event.repeat && !passButton.classList.contains("passed")) passButton.click();
      return;
    }
    if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.code)) {
      if (!latestState || event.target?.closest?.("input[type='range'], [role='slider']")) return;
      if ($("#inspectPanel").classList.contains("hidden")) return;
      event.preventDefault();
      if (event.code === "ArrowUp") stepInspectHistory(-1);
      else if (event.code === "ArrowDown") stepInspectHistory(1);
      else cycleInspectBoard(event.code === "ArrowRight" ? 1 : -1);
      return;
    }
    if (event.code === "KeyI") {
      event.preventDefault();
      if (!event.repeat && latestState) toggleInspectPanel();
    } else if (event.code === "KeyH") {
      event.preventDefault();
      $("#hideInterfaceBtn").click();
    } else if (event.code === "KeyJ") {
      event.preventDefault();
      $("#hideCodesBtn").click();
    }
  });
  document.addEventListener("keyup", (event) => {
    if (event.code === "Enter" || event.code === "NumpadEnter") cancelPassAllHold();
  });
  window.addEventListener("blur", cancelPassAllHold);
  paintStaticText();
  initLanguageSwitch();
  initConfirmPanel();
  initSocialLinks();
  initAppInstall();
  registerAppUpdates();
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
  initVfxSpeedToggle();
  initSoundToggle();
  initChat();
  initViewToggles();
  $("#playerLogCloseBtn").onclick = () => $("#playerLogPanel").classList.add("hidden");
  $("#playerLogCloseBtn").textContent = t("close");
  $("#logCloseBtn").onclick = () => $("#logPanel").classList.add("hidden");
  $("#inspectCloseBtn").onclick = () => {
    $("#inspectPanel").classList.add("hidden");
    $("#gameScreen").classList.remove("inspect-open");
  };
  $("#inspectXBtn").onclick = () => $("#inspectCloseBtn").click();
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
  // reloaded in the middle of a session (an update, the phone dropping the tab): back to the same seat
  resumeSession();
}

boot();
