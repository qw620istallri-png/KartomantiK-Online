// Board transform and zoom, drawing, toolbars, effect markers, counters and battlefield rendering.
// Loaded before app.js: declarations only, nothing runs at load time.

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

// "Lock view": freezes the current pan + zoom (wheel, drag and +/- do nothing)
let viewLocked = false;

function setZoomAt(newZoom, anchorClientX, anchorClientY) {
  if (viewLocked) return;
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
  $("#viewLockBtn").title = t("lockView");
  $("#viewLockBtn").onclick = () => {
    viewLocked = !viewLocked;
    $("#viewLockBtn").classList.toggle("active", viewLocked);
    $("#viewLockBtn").setAttribute("aria-pressed", String(viewLocked));
    $("#viewLockBtn").title = t(viewLocked ? "unlockView" : "lockView");
    ["zoomInBtn", "zoomOutBtn", "zoomResetBtn"].forEach((id) => { $("#" + id).disabled = viewLocked; });
  };

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
    if (viewLocked) return;
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
  const button = $("#createEssenceBtn");
  button.textContent = "⊕";
  button.title = t("neutralToken");
  $("#essenceTemperamentGrid").innerHTML = `<button data-temperament="neutral" class="neutral-token-choice active"><span></span>${esc(t("neutralToken"))}</button>`;

  button.onclick = () => {
    selectedEssenceTemperament = "neutral";
    const choice = $("#essenceTemperamentGrid .neutral-token-choice");
    choice.classList.add("active");
    choice.querySelector("span").style.setProperty("--neutral-color", playerColor(myPlayerId));
    $("#essenceCountInput").value = 1;
    $("#neutralTokenNameInput").value = t("neutralToken");
    $("#neutralTokenNameField").classList.remove("hidden");
    $("#essencePanelHeading").textContent = t("neutralToken");
    $("#essencePanel").classList.remove("hidden");
    $("#neutralTokenNameInput").focus();
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
    if (!["while_source_and_target_on_field", "while_source_on_field"].includes(effect.duration)) continue;
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

function applyRevealCardWidth() {
  document.documentElement.style.setProperty("--reveal-card-w", revealCardWidth + "px");
  if ($("#revealSizeInput")) $("#revealSizeInput").value = String(revealCardWidth);
}

function initRevealResize() {
  applyRevealCardWidth();
  $("#revealSizeInput").addEventListener("input", (event) => {
    revealCardWidth = Math.min(REVEAL_SIZE_MAX, Math.max(90, Number(event.target.value) || 190));
    applyRevealCardWidth();
    localStorage.setItem(REVEAL_SIZE_KEY, String(revealCardWidth));
  });
}

// ---------------------------------------------------------------- hand-view resize

const HAND_VIEW_SIZE_KEY = "ko_hand_view_card_h";

const HAND_VIEW_SIZE_MAX = 500;

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

function rulesCardCountersMarkup(item, ongoingEffects, printedPower) {
  const ability = rulesActivatedAbilitiesForItem(item).find(rulesIsCounterEssenceAbility);
  if (!ability) return counterCircles(item.counters, ongoingEffects, item.effectivePower, printedPower);
  const counters = { ...(item.counters || {}) };
  const counterName = ability.removeCountersFromSource.name.toLowerCase();
  let count = 0;
  for (const key of Object.keys(counters)) {
    if (key.toLowerCase() === counterName) {
      count += Number(counters[key] || 0);
      delete counters[key];
    } else if (key.toLowerCase() === item.chosenTemperament) {
      // Older states used a numeric counter to display the chosen colour.
      delete counters[key];
    }
  }
  const canSpend = rulesCanSpendCounterEssence()
    && rulesCounterEssenceSources().some((entry) => entry.item.id === item.id && entry.ability.id === ability.id);
  const temperament = item.chosenTemperament || "hollow";
  const label = `${t("rulesUseEssenceCounter")} · ${t(`temperament${temperament[0].toUpperCase()}${temperament.slice(1)}`)}`;
  const gems = Array.from({ length: Math.max(0, Math.min(50, count)) }, () =>
    `<button type="button" class="bf-counter bf-gem-essence" data-gem-essence="${esc(ability.id)}" title="${esc(label)}" aria-label="${esc(label)}" ${canSpend ? "" : "disabled"}><img src="${esc(temperamentSymbol(temperament))}" alt=""></button>`).join("");
  return counterCircles(counters, ongoingEffects, item.effectivePower, printedPower) + gems;
}

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
    effectivePower !== null && effectivePower !== undefined
    && printedPower !== null && printedPower !== undefined
    && Number.isFinite(Number(effectivePower))
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

function rulesTemperamentMarkerMarkup(item, effects) {
  if (!item.faceUp) return "";
  const override = [...effects].reverse().find((effect) => effect.kind === "temperament_override");
  const temperament = item.effectiveTemperament || override?.temperament || item.temperamentOverride;
  if (!TEMPERAMENTS.some((entry) => entry.key === temperament)) return "";
  const printed = item.isTokenCard ? [item.temperament] : cardsById.get(item.cardId)?.temperaments || [];
  if (!override && !item.temperamentOverride && printed.includes(temperament)) return "";
  const name = t(`temperament${temperament[0].toUpperCase()}${temperament.slice(1)}`);
  return `<img class="rules-temperament-badge" src="${esc(temperamentSymbol(temperament))}" title="${esc(name)}" alt="${esc(name)}">`;
}

function rulesActivationChoiceLabel(ability, index, count) {
  const labels = {
    "sandokaron-banner-power": "rulesBannerPower", "sandokaron-banner-essence": "rulesBannerEssence",
    "zum-weaken": "rulesAbilityWeaken", "zum-silence": "rulesAbilitySilence",
    "zum-strengthen": "rulesAbilityStrengthen", "zum-draw": "rulesAbilityDraw", "zum-mill": "rulesAbilityMill",
    "malaleuco-copy-will": "rulesAbilityCopyWill", "malaleuco-to-interzone": "rulesAbilityToInterzone",
    "mechanism-one-shuffle": "rulesAbilityShuffle", "mechanism-two-peek-and-swap": "rulesAbilityPeekSwap",
    "mechanism-three-bottom-a-card": "rulesAbilityResetEnigma",
    "exhaust-to-change-points": "rulesAbilityChangePoints", "exhaust-sacrifice-to-prevent-point-changes": "rulesAbilityFreezePoints",
    "shattered-memory-exile-limbo-card": "rulesAbilityExileLimbo", "shattered-memory-sacrifice-for-essence": "rulesAbilityExileForEssence",
  };
  const temperament = ability.ongoingEffect?.kind === "temperament_override" ? ability.ongoingEffect.temperament : null;
  if (temperament) return t(`temperament${temperament[0].toUpperCase()}${temperament.slice(1)}`);
  if (labels[ability.id]) return `${ability.immediate ? `${t("rulesImmediateLabel")} · ` : ""}${t(labels[ability.id])}`;
  return ability.immediate ? t("rulesImmediateLabel") : count > 1 ? `${t("rulesActivateShort")} ${index + 1}` : t("rulesActivateShort");
}

function rulesActivateMarkerMarkup(item) {
  const available = rulesActivatedAbilitiesForItem(item)
    .filter((ability) => !rulesIsCounterEssenceAbility(ability))
    .map((ability) => ({
      ability,
      draft: rulesActivatedActionDraft(item, ability),
    }))
    .filter((entry) => entry.draft);
  if (!available.length) return "";
  const bannerModes = { "sandokaron-banner-power": "rulesBannerPower", "sandokaron-banner-essence": "rulesBannerEssence" };
  const bannerChoice = available.every(({ ability }) => Object.hasOwn(bannerModes, ability.id));
  const baseLabel = bannerChoice ? t("rulesSpendBanner") : rulesText("rulesActivateCardEffect", { card: cardName(item.cardId) });
  const printedEffect = bannerChoice ? t("rulesBannerChoice") : cardField(cardsById.get(item.cardId), "effect");
  const label = printedEffect ? `${baseLabel} — ${printedEffect}` : baseLabel;
  return `<button type="button" class="rules-activate-badge" title="${esc(label)}" aria-label="${esc(label)}">
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13.2 2.5 5.8 13h5.6l-.6 8.5L18.4 11h-5.7l.5-8.5Z"></path></svg>
  </button>
  <div class="rules-activate-confirm hidden" role="group" aria-label="${esc(t(bannerChoice ? "rulesSpendBanner" : "confirmQuestion"))}">
    <header>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13.2 2.5 5.8 13h5.6l-.6 8.5L18.4 11h-5.7l.5-8.5Z"></path></svg>
      <b>${esc(cardName(item.cardId))}</b>
      <button type="button" class="rules-activate-cancel" data-rules-activate-cancel aria-label="${esc(t("cancel"))}">×</button>
    </header>
    ${printedEffect ? `<p class="rules-activate-text">${esc(printedEffect)}</p>` : ""}
    <div class="rules-activate-actions">
      ${available.map(({ ability }, index) => {
        const temperament = ability.ongoingEffect?.kind === "temperament_override" ? ability.ongoingEffect.temperament : null;
        const label = rulesActivationChoiceLabel(ability, index, available.length);
        return `<button type="button" data-rules-activate-confirm="${esc(ability.id)}">
          ${temperament ? `<img src="${esc(temperamentSymbol(temperament))}" alt="">` : ""}${esc(label)}
        </button>`;
      }).join("")}
    </div>
  </div>`;
}

let rulesActivationDismiss = null;

function closeRulesActivationConfirmation() {
  $$(".rules-activate-confirm").forEach((element) => {
    if (typeof element.hidePopover === "function" && element.matches(":popover-open")) element.hidePopover();
    element.classList.add("hidden");
  });
  if (rulesActivationDismiss) document.removeEventListener("pointerdown", rulesActivationDismiss);
  rulesActivationDismiss = null;
}

function wireRulesActivateMarker(cardElement, item) {
  cardElement.querySelectorAll("[data-gem-essence]").forEach((counter) => {
    counter.addEventListener("pointerdown", (event) => event.stopPropagation());
    counter.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      cardElement.querySelectorAll("[data-gem-essence]").forEach((button) => { button.disabled = true; });
      beginRulesBoardActivatedAction(item, counter.dataset.gemEssence);
    });
  });
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
    if (typeof confirmation.showPopover === "function") {
      confirmation.setAttribute("popover", "manual");
      confirmation.showPopover();
      const anchor = button.getBoundingClientRect();
      const popup = confirmation.getBoundingClientRect();
      confirmation.style.left = `${Math.max(8, Math.min(innerWidth - popup.width - 8, anchor.right + 8))}px`;
      confirmation.style.top = `${Math.max(8, Math.min(innerHeight - popup.height - 8, anchor.bottom - popup.height))}px`;
    }
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

// Battlefield cards are rebuilt on every render; remembering where each one
// was lets a card glide to its new spot (or drop in when it is new) instead of
// teleporting. Moves the local player just dragged are skipped.
let lastBoardLayout = null;

const recentLocalBoardMoves = new Map();

const pendingBoardArrivals = new Map();

function markLocalBoardMove(itemId) {
  if (itemId) recentLocalBoardMoves.set(itemId, performance.now());
}

function animateBoardCard(el, item, pos) {
  const previous = lastBoardLayout?.get(item.id);
  if (!lastBoardLayout || rulesVfxReducedMotion()) return;
  const now = performance.now();
  if (!previous) {
    // a new card waits for the effects announcing it, then drops in
    pendingBoardArrivals.set(item.id, { start: now + Math.min(2400, rulesVfxQueueRemaining()), duration: vfxMs(380) });
  }
  const arrival = pendingBoardArrivals.get(item.id);
  if (arrival) {
    if (now < arrival.start + arrival.duration) {
      el.classList.add("bf-arrive");
      el.style.setProperty("--bf-arrive-delay", `${Math.round(arrival.start - now)}ms`);
      el.style.setProperty("--bf-arrive-duration", `${arrival.duration}ms`);
      return;
    }
    pendingBoardArrivals.delete(item.id);
  }
  if (!previous) return;
  const localMove = recentLocalBoardMoves.get(item.id);
  if (localMove && performance.now() - localMove < 1500) return;
  // a UI beta card is scaled: its own translate runs in scaled units
  const scale = Number.parseFloat(el.style.scale) || 1;
  const dx = (previous.x - pos.x) / scale;
  const dy = (previous.y - pos.y) / scale;
  if (Math.hypot(dx, dy) * scale > 3) {
    el.animate([
      { transform: `translate(${dx}px,${dy}px)` },
      { transform: "translate(0,0)" },
    ], vfxTiming({ duration: 420, easing: "cubic-bezier(.2,.8,.2,1)" }));
  }
  if ((previous.rotation || 0) !== (item.rotation || 0)) {
    el.querySelector(".bf-card-inner")?.animate([
      { transform: `rotate(${previous.rotation || 0}deg)` },
      { transform: `rotate(${item.rotation || 0}deg)` },
    ], vfxTiming({ duration: 300, easing: "cubic-bezier(.2,.8,.2,1)" }));
  }
}

// Impact ring (and shake for strong cards) shared by the reveal flip and the arrival on the board
function playCardImpactRing(el, tier, tone, hasEffect, impactDelay) {
  const ring = document.createElement("span");
  ring.className = `bf-flip-ring tier-${tier}${hasEffect ? " has-effect" : ""}`;
  ring.style.setProperty("--flip-tone", tone);
  el.appendChild(ring);
  ring.animate([
    { opacity: 0, transform: "scale(.7)" },
    { opacity: .95, transform: "scale(1)", offset: 0.2 },
    { opacity: 0, transform: `scale(${1.25 + tier * 0.2})` },
  ], { duration: vfxMs(520 + tier * 120), delay: impactDelay, easing: "ease-out", fill: "backwards" })
    .finished.then(() => ring.remove(), () => ring.remove());
  if (tier >= 2) {
    const amplitude = tier === 3 ? 7 : 4;
    el.animate([
      { transform: "translate(0,0)" },
      { transform: `translate(${-amplitude}px,${amplitude / 2}px)`, offset: 0.2 },
      { transform: `translate(${amplitude}px,${-amplitude / 2}px)`, offset: 0.45 },
      { transform: `translate(${-amplitude / 2}px,0)`, offset: 0.7 },
      { transform: "translate(0,0)" },
    ], { duration: vfxMs(320), delay: impactDelay, easing: "ease-out" });
  }
}

// Power and counter changes on a board card (families: power, counters)
function playBoardStatChanges(el, item, previous) {
  if (rulesVfxReducedMotion() || !lastBoardLayout) return;
  const arrivalDelay = Math.min(1500, rulesVfxQueueRemaining());
  if (!previous) {
    // copies shimmer, tokens crystallise (family: control / copy / tokens)
    if (item.isCopy || item.isTokenCard) {
      window.setTimeout(() => spawnVfxParticles(rulesVfxCenter(el), item.isCopy ? "transcendent" : (item.temperament || "hollow"), {
        count: item.isCopy ? 12 : 9, spread: 40, direction: "out",
        style: item.isCopy ? { shape: "light", colors: ["#ffffff", "#bfe6ff", "#8fc8ff"] } : { shape: "shard", colors: ["#ffffff", "#d8d8d8", "#9a9a9a"] },
      }), arrivalDelay + 250);
    }
    return;
  }
  const controllerNow = battlefieldItemControllerId(item);
  if (previous.controllerId && controllerNow && previous.controllerId !== controllerNow) {
    const ownerTone = playerColor(controllerNow);
    window.setTimeout(() => {
      if (el.isConnected) playCardImpactRing(el, 3, ownerTone, true, 0);
      spawnVfxParticles(rulesVfxCenter(el), null, {
        count: 14, spread: 46, direction: "out",
        style: { shape: "mist", colors: [ownerTone, "#ffffff", ownerTone] },
      });
    }, arrivalDelay);
  }
  const ongoingNow = (latestState.rulesEngine?.ongoingEffects || []).filter((effect) => effect.target?.itemId === item.id).length;
  if (Number(previous.ongoing || 0) > ongoingNow) {
    // an effect expired: the card dulls for a moment and dust falls off it
    el.animate([
      { filter: "grayscale(0)" }, { filter: "grayscale(.9) brightness(.8)", offset: 0.35 }, { filter: "grayscale(0)" },
    ], { duration: vfxMs(900), delay: arrivalDelay });
    window.setTimeout(() => spawnVfxParticles(rulesVfxCenter(el), "hollow", { count: 8, spread: 28, direction: "down" }), arrivalDelay);
  }
  if (item.isTokenCard) return;
  const card = cardsById.get(item.cardId);
  const temperament = card?.colorKey || item.temperament || null;
  const tone = card?.glow || "#f1d377";
  const delay = Math.min(1500, rulesVfxQueueRemaining());
  const centerOf = () => rulesVfxCenter(el);
  const anchorPoint = centerOf() || { x: 0, y: 0 };
  const prevPower = previous.power;
  const nowPower = item.effectivePower ?? null;
  if (prevPower !== null && prevPower !== undefined && nowPower !== null && Number(prevPower) !== Number(nowPower)) {
    const delta = Number(nowPower) - Number(prevPower);
    const label = document.createElement("span");
    label.className = `bf-stat-float ${delta > 0 ? "gain" : "loss"}`;
    label.textContent = `${delta > 0 ? "+" : ""}${delta}`;
    const anchorRect = el.getBoundingClientRect();
    label.style.left = `${anchorRect.left + anchorRect.width / 2}px`;
    label.style.top = `${anchorRect.top + anchorRect.height * 0.2}px`;
    document.body.appendChild(label);
    label.animate([
      { transform: "translate(-50%, 8px) scale(.5)", opacity: 0 },
      { transform: "translate(-50%, -8px) scale(1.4)", opacity: 1, offset: 0.25 },
      { transform: "translate(-50%, -46px) scale(1)", opacity: 0 },
    ], { duration: vfxMs(1300), delay, easing: "ease-out", fill: "both" })
      .finished.then(() => label.remove(), () => label.remove());
    window.setTimeout(() => spawnVfxParticles(centerOf(), null, {
      count: Math.min(14, 5 + Math.abs(delta) * 2),
      spread: 42,
      direction: delta > 0 ? "up" : "down",
      style: delta > 0
        ? { shape: "light", colors: ["#ffffff", "#c9f5c0", "#7bcf6a"] }
        : { shape: "shard", colors: ["#ffd8d0", "#ff6a4a", "#8a1f12"] },
    }), delay);
  }
  const prevCounters = previous.counters || {};
  Object.entries(item.counters || {}).forEach(([name, value]) => {
    const before = Number(prevCounters[name] || 0);
    const now = Number(value || 0);
    if (before === now || !Number.isFinite(now)) return;
    window.setTimeout(() => {
      const center = centerOf() || { x: anchorPoint.x, y: anchorPoint.y };
      spawnVfxParticles(center, temperament, {
        count: Math.min(10, 3 + Math.abs(now - before) * 2),
        spread: 30,
        direction: now > before ? "down" : "up",
      });
      const crossed = [5, 10].some((threshold) => (before < threshold && now >= threshold));
      if (crossed) {
        if (el.isConnected) playCardImpactRing(el, 3, tone, true, 0);
        spawnVfxParticles(center, "transcendent", { count: 14, spread: 50, direction: "out", delay: 120 });
      }
    }, delay);
  });
}

function cardImpactTier(item) {
  const card = cardsById.get(item.cardId);
  const power = Math.max(0, Number(item.effectivePower ?? card?.power ?? 0));
  return power >= 5 ? 3 : power >= 3 ? 2 : 1;
}

// Reveal flip: power sets the impact tier, a printed effect adds a coloured glow
// choice windows wait for the reveal flip to end so they never cover it
let boardFlipBusyUntil = 0;

function playCardFlipReveal(el, item) {
  const face = el.querySelector(".bf-card-face");
  if (!face || rulesVfxReducedMotion()) return;
  const card = cardsById.get(item.cardId);
  const power = Math.max(0, Number(item.effectivePower ?? card?.power ?? 0));
  const tier = power >= 5 ? 3 : power >= 3 ? 2 : 1;
  const hasEffect = Boolean(card && String(card.effect || "").trim());
  const tone = card?.glow || "#f1d377";
  const delay = Math.min(1800, rulesVfxQueueRemaining());
  const duration = vfxMs(420 + tier * 90);
  boardFlipBusyUntil = Math.max(boardFlipBusyUntil, performance.now() + delay + duration + 450);
  const timing = { duration, delay, easing: "cubic-bezier(.2,.8,.2,1)", fill: "backwards" };
  const lift = 1 + tier * 0.07;
  // the card first shows its back (until the reveal is announced), then turns edge-on and shows its face once
  const back = document.createElement("div");
  back.className = "bf-flip-back back-face";
  back.style.setProperty("--owner-color", playerColor(item.ownerId));
  el.appendChild(back);
  back.animate([
    { transform: "perspective(900px) rotateY(0deg)", opacity: 1, offset: 0 },
    { transform: "perspective(900px) rotateY(90deg)", opacity: 1, offset: 0.99 },
    { transform: "perspective(900px) rotateY(90deg)", opacity: 0, offset: 1 },
  ], { duration: Math.round(duration * 0.4), delay, easing: "ease-in", fill: "both" })
    .finished.then(() => back.remove(), () => back.remove());
  face.animate([
    { transform: "perspective(900px) rotateY(90deg) scale(.92)", filter: "brightness(2.2)", offset: 0 },
    { transform: `perspective(900px) rotateY(90deg) scale(${lift})`, filter: "brightness(1.8)", offset: 0.4 },
    { transform: `perspective(900px) rotateY(0deg) scale(${lift + 0.1})`, filter: `brightness(1.5) drop-shadow(0 0 ${6 + tier * 6}px ${tone})`, offset: 0.72 },
    { transform: "perspective(900px) rotateY(0deg) scale(1)", filter: "brightness(1)", offset: 1 },
  ], timing);
  playCardImpactRing(el, tier, tone, hasEffect, delay + Math.round(duration * 0.72));
}

function renderBattlefield() {
  $("#battlefieldBg").classList.toggle("rotated", mySeat() === 1);
  renderPiles();
  const bf = $("#battlefield");
  bf.querySelectorAll(".bf-card, .bf-token").forEach((el) => el.remove());
  const boardLayout = new Map();
  // UI beta places cards by zone (see ui-beta.js); null on the classic table
  const betaPlacement = window.uiBeta?.active() ? window.uiBeta.placement() : null;

  latestState.battlefield.forEach((item) => {
    const el = document.createElement("div");
    el.className = `bf-card${item.isCopy ? " is-copy" : ""}${item.fieldZone ? ` field-zone-${item.fieldZone}` : ""}${Math.round(Number(item.rotation || 0)) % 180 ? " is-exhausted" : ""}`;
    el.dataset.itemId = item.id;
    if (item.pendingSupportActionId) el.classList.add("is-pending-support");
    if (item.fieldZone) el.dataset.fieldZone = item.fieldZone;
    const betaBox = betaPlacement?.get(item.id) || null;
    const pos = betaBox || stackedScreenPos(item) || rotateForSeat(item.x, item.y, PILE_W, PILE_H);
    if (betaBox) el.style.scale = betaBox.k.toFixed(4);
    el.style.left = pos.x + "px";
    el.style.top = pos.y + "px";
    const previousLayout = lastBoardLayout?.get(item.id) || null;
    const flippedUp = Boolean(previousLayout && !previousLayout.faceUp && item.faceUp);
    boardLayout.set(item.id, {
      x: pos.x, y: pos.y, rotation: item.rotation || 0, faceUp: Boolean(item.faceUp),
      power: item.effectivePower ?? null, counters: { ...(item.counters || {}) },
      controllerId: battlefieldItemControllerId(item),
      ongoing: (latestState.rulesEngine?.ongoingEffects || []).filter((effect) => effect.target?.itemId === item.id).length,
    });
    animateBoardCard(el, item, pos);
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
    // a Will turned into a Manifestation has no printed Power: all of it shows as a badge
    const printedPower = item.isTokenCard
      ? item.power
      : item.willManifestation ? 0 : cardsById.get(item.cardId)?.power;
    el.innerHTML = `<div class="bf-card-inner" style="transform:rotate(${item.rotation || 0}deg)">${inner}${item.faceUp && item.cardId ? automationCoverageBadgeHtml(item.cardId) : ""}${rulesTemperamentMarkerMarkup(item, ongoingEffects)}${item.effectsDisabled ? `<span class="rules-effects-disabled-badge" title="${esc(t("rulesEffectsDisabled"))}" aria-label="${esc(t("rulesEffectsDisabled"))}">Ø</span>` : ""}${item.isCopy ? `<span class="copy-card-stamp">${esc(t("copyStamp"))}</span>` : ""}</div><div class="counters">${rulesCardCountersMarkup(item, ongoingEffects, printedPower)}</div>${rulesFieldZoneMarkerMarkup(item.fieldZone)}${rulesControllerMarkerMarkup(item)}${item.isSupport ? `<span class="rules-support-badge" title="${esc(t("playInSupport"))}" aria-label="${esc(t("playInSupport"))}">S</span>` : ""}${rulesEffectMarkerMarkup(ongoingEffects)}${rulesActivateMarkerMarkup(item)}`;
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
        { keepInBeta: true, zOrder: true, label: t("bringToFront"), onSelect: () => send({ type: "reorder_battlefield_item", itemId: item.id, position: "front" }) },
        { keepInBeta: true, zOrder: true, label: t("sendToBack"), onSelect: () => send({ type: "reorder_battlefield_item", itemId: item.id, position: "back" }) },
      ];
      if (item.isTokenCard) {
        showContextMenu(event.clientX, event.clientY, betaMenuItems([
          { label: t("exhaust"), onSelect: () => send({ type: "move_battlefield_item", itemId: item.id, x: item.x, y: item.y, rotation: item.rotation ? 0 : 90 }) },
          { separator: true },
          ...zOrderItems,
          { separator: true },
          counterGridMenuItem("power", { itemId: item.id }),
          { separator: true },
          { label: t("remove"), onSelect: () => send({ type: "remove_battlefield_item", itemId: item.id, toZone: "graveyard" }) },
        ]));
        return;
      }
      if (item.isCopy) {
        const copyItems = [{ keepInBeta: true, label: t("inspect"), onSelect: () => showInspect(item.cardId, false) }];
        const rulesItem = isMine && item.faceUp
          ? rulesActionContextItem({ cardId: item.cardId, zone: "battlefield", itemId: item.id })
          : null;
        if (rulesItem) copyItems.push({ ...rulesItem, keepInBeta: !rulesItem.debug });
        copyItems.push(
          { separator: true },
          ...zOrderItems,
          { separator: true },
          counterGridMenuItem("power", { itemId: item.id }),
          { separator: true },
          { label: t("removeCopy"), onSelect: () => send({ type: "remove_battlefield_item", itemId: item.id, toZone: "graveyard" }) },
        );
        showContextMenu(event.clientX, event.clientY, betaMenuItems(copyItems));
        showCardLabels(el, cardName(item.cardId), t("copyStamp"));
        return;
      }
      const items = [];
      items.push({ keepInBeta: true, label: t("inspect"), onSelect: () => showInspect(item.cardId, !item.faceUp && !canPeek) });
      if (manualStackAvailable()) {
        items.push(item.manualStack
          ? { label: t("ubTakeFromStack"), onSelect: () => { markLocalBoardMove(item.id); send({ type: "move_battlefield_item", itemId: item.id, manualStack: false }); } }
          : { label: t("ubPutInStack"), onSelect: () => { markLocalBoardMove(item.id); send({ type: "move_battlefield_item", itemId: item.id, manualStack: true, unstack: true }); } });
      }
      if (!latestState?.rulesEngine?.enabled) {
        items.push({ label: t("ubSendToStalemate"), onSelect: () => sendItemToManualStalemate(item) });
      }
      const rulesItem = isMine && item.faceUp
        ? rulesActionContextItem({ cardId: item.cardId, zone: "battlefield", itemId: item.id })
        : null;
      if (rulesItem) items.push({ ...rulesItem, keepInBeta: !rulesItem.debug });
      if (isMine && (passiveEffectsByCard.get(item.cardId) || []).some((effect) => effect.kind === "swap_with_targeted_confrontation_manifestation")) {
        items.push({
          keepInBeta: true,
          label: t(item.outcastOff ? "rulesOutcastOff" : "rulesOutcastOn"),
          onSelect: () => send({ type: "toggle_item_option", itemId: item.id, option: "outcastOff" }),
        });
      }
      if (isMine && (passiveEffectsByCard.get(item.cardId) || []).some((effect) => effect.kind === "interzone_substitute_holder")) {
        items.push({
          keepInBeta: true,
          label: t(item.karmapultAuto ? "rulesKarmapultAutoOn" : "rulesKarmapultAutoOff"),
          onSelect: () => send({ type: "toggle_item_option", itemId: item.id, option: "karmapultAuto" }),
        });
      }
      if ((item.attachedCards || []).length) {
        items.push({
          keepInBeta: true,
          label: rulesText("rulesAttachedList", { count: item.attachedCards.length }),
          onSelect: () => openAttachedPlayPanel(item.id),
        });
      }
      if (isMine && tebebeManifestationIsPlayable(item)) {
        items.push({
          keepInBeta: true,
          label: t("rulesPlayConcealed"),
          onSelect: () => beginRulesBoardAction({
            cardId: item.cardId, zone: "battlefield", itemId: item.id, playFromField: true, fieldFree: false, tebebe: true, fixedHollow: 3,
            placement: { x: item.x, y: item.y },
          }),
          highlight: true,
        });
      }
      if (isMine && (item.playableFree || item.concealedWill || item.persuaded) && limboWillIsPlayable(item.cardId, true)) {
        const fieldFree = Boolean(item.playableFree || item.concealedFree);
        items.push({
          keepInBeta: true,
          label: fieldFree ? t("rulesPlayFreeFromField") : item.persuaded ? t("rulesPlayPersuaded") : t("rulesPlayConcealed"),
          onSelect: () => beginRulesBoardAction(rulesFieldWillPlaySource(item)),
        });
      }
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
          keepInBeta: true,
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
      showContextMenu(event.clientX, event.clientY, betaMenuItems(items));
      // must run AFTER showContextMenu: it calls closeContextMenu() first
      // (to dismiss any previously-open menu), which would otherwise wipe
      // out labels created before it
      const canSeeName = item.faceUp || canPeek;
      showCardLabels(el, canSeeName ? cardName(item.cardId) : null, (latestState.players[item.ownerId] || {}).name || "");
    });
    if (betaBox) window.uiBeta.decorateCard(el, item, betaBox);
    bf.appendChild(el);
    if (item.faceUp) playBoardStatChanges(el, item, previousLayout);
    if (flippedUp && !item.isTokenCard) playCardFlipReveal(el, item);
    else if (el.classList.contains("bf-arrive") && !item.isTokenCard && item.cardId && !rulesVfxReducedMotion()) {
      const arrivalDelay = Number.parseFloat(el.style.getPropertyValue("--bf-arrive-delay")) || 0;
      const arrivalDuration = Number.parseFloat(el.style.getPropertyValue("--bf-arrive-duration")) || 380;
      const arrivalCard = cardsById.get(item.cardId);
      playCardImpactRing(el, cardImpactTier(item), arrivalCard?.glow || "#f1d377", false, arrivalDelay + Math.round(arrivalDuration * 0.8));
    }
    if (item.faceUp) playVfxBoardElement(el, item, previousLayout, { flipped: flippedUp, arriving: !previousLayout && el.classList.contains("bf-arrive") });
    wireRulesEffectMarker(el, ongoingEffects);
    wireRulesActivateMarker(el, item);
    bindRarityPointer(el.querySelector(".bf-card-face.ko-rarity-card"), false, el);
  });
  lastBoardLayout = boardLayout;

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
        // beta automates Essence: no manual options on floating Essences
        if (token.isEssence && !token.isNeutralCounter && latestState?.rulesEngine?.enabled) return;
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
  rearmRulesBoardTargetsIfDetached();
}

// a rebuilt field (full screen, resize) loses the targets of an open choice: arm them again on the new cards
function rearmRulesBoardTargetsIfDetached() {
  if (!pendingRulesBoardFlow || !rulesBoardArmedElements.some((element) => !element.isConnected)) return;
  renderRulesBoardFlow();
}

function bindDrag(el, onDrop) {
  el.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || event.isPrimary === false) return;
    if (event.target.closest("button, select")) return;
    event.preventDefault();
    const startX = event.clientX, startY = event.clientY;
    const startLeft = parseFloat(el.style.left) || 0, startTop = parseFloat(el.style.top) || 0;
    const move = (e) => {
      const x = startLeft + (e.clientX - startX) / zoomLevel;
      const y = startTop + (e.clientY - startY) / zoomLevel;
      el.style.left = x + "px";
      el.style.top = y + "px";
    };
    const up = (e) => {
      if (e.type === "pointerup") onDrop(parseFloat(el.style.left), parseFloat(el.style.top));
      else {
        el.style.left = startLeft + "px";
        el.style.top = startTop + "px";
      }
    };
    startCardPointerDrag(event, el, move, up);
  });
}
