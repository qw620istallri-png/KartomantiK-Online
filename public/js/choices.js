// Pending rules choice panels and screens.
// Loaded before app.js: declarations only, nothing runs at load time.

let rulesChoiceRenderKey = null;
let rulesChoiceContentVisible = false;
let rulesChoiceAnswerPending = null;

function resetRulesChoiceInteraction() {
  rulesChoiceRenderKey = null;
  rulesChoiceContentVisible = false;
  rulesChoiceAnswerPending = null;
  handDropSelection = { choiceId: null, playerId: null, hand: null, indexes: [] };
}

function lockRulesChoiceAnswer() {
  const choice = latestState?.rulesEngine?.pendingChoice;
  const waiting = rulesChoiceAnswerPending?.choiceId === choice?.id && rulesChoiceAnswerPending?.playerId === myPlayerId;
  $("#rulesChoiceOptions")?.setAttribute("aria-busy", waiting ? "true" : "false");
  if (waiting) $$("#rulesChoiceOptions button, #rulesChoiceOptions input, #rulesChoiceOptions select, #rulesChoiceOptions textarea")
    .forEach((control) => { control.disabled = true; });
}

function sendRulesChoiceAnswer(payload) {
  const choice = latestState?.rulesEngine?.pendingChoice;
  if (!latestState?.rulesEngine?.enabled || !choice || choice.id !== payload.choiceId || choice.playerId !== myPlayerId || isObserver || latestState?.ended) return false;
  if (rulesChoiceAnswerPending?.choiceId === choice.id && rulesChoiceAnswerPending?.playerId === myPlayerId) return false;
  rulesChoiceAnswerPending = { choiceId: choice.id, playerId: myPlayerId };
  send(payload);
  lockRulesChoiceAnswer();
  return true;
}

function closeRulesChoicePanel(force = false) {
  const mandatoryChoice = latestState?.rulesEngine?.pendingChoice;
  if (mandatoryChoice?.playerId === myPlayerId && !force) return;
  resetRulesChoiceInteraction();
  pendingTriggeredPlacement = null;
  $("#rulesChoicePanel").classList.add("hidden");
}

// Every decision popup shows the card that asks for the decision; hovering it
// shows the card at full reading size (see CHOICE_PREVIEW_SELECTOR).
function rulesActiveAbilityEffect(abilityId) {
  const temperament = String(abilityId || "").match(/^pidue-(choleric|capricious|phlegmatic|vitreous|melancholic)-/)?.[1];
  if (!temperament) return null;
  const symbols = { choleric: "🔥", capricious: "⚡", phlegmatic: "🌿", vitreous: "💧", melancholic: "🔮" };
  const line = String(cardField(cardsById.get("inner-deserts-129"), "effect") || "").split(/\r?\n/).find((entry) => entry.includes(symbols[temperament]));
  return line ? { temperament, text: line.slice(line.indexOf(",") + 1).trim() } : null;
}

function rulesActiveAbilityMarkup(abilityId) {
  const effect = rulesActiveAbilityEffect(abilityId);
  if (!effect) return "";
  const temperament = t(`temperament${effect.temperament[0].toUpperCase()}${effect.temperament.slice(1)}`);
  return `<span class="rules-current-effect" data-active-ability="${esc(abilityId)}"><strong class="rules-current-effect-label"><img src="${esc(temperamentSymbol(effect.temperament))}" alt="">${esc(rulesText("rulesCurrentEffect", { temperament }))}</strong><span>${esc(effect.text)}</span></span>`;
}

function syncRulesChoiceSourceCard() {
  const head = document.querySelector("#rulesChoicePanel .rules-choice-head");
  if (!head) return;
  const box = head.parentElement;
  box.querySelector(":scope > .rules-choice-source")?.remove();
  document.querySelector("#rulesChoicePanel .rules-choice-effect")?.remove();
  box.classList.remove("has-source");
  if ($("#rulesChoicePanel").classList.contains("hidden")) return;
  const choice = latestState?.rulesEngine?.pendingChoice;
  const cardId = pendingTriggeredPlacement?.payload?.cardId
    || choice?.sourceCardId || choice?.targetCardId || choice?.cardId;
  const image = cardId ? cardImage(cardId) : "";
  if (!image) return;
  const chip = document.createElement("span");
  chip.className = "rules-choice-source";
  chip.title = cardName(cardId);
  chip.innerHTML = `<img src="${esc(image)}" alt="${esc(cardName(cardId))}">`;
  box.insertBefore(chip, box.firstChild);
  box.classList.add("has-source");
  // which effect is being resolved: the source card's text, right under the title
  const effectText = cardId ? cardField(cardsById.get(cardId), "effect") : "";
  if (effectText) {
    const effect = document.createElement("p");
    effect.className = "rules-choice-effect";
    const activeEffect = rulesActiveAbilityMarkup(choice?.sourceAbilityId);
    if (activeEffect) effect.innerHTML = activeEffect;
    else effect.textContent = effectText;
    head.insertAdjacentElement("afterend", effect);
  }
}

// Banner shown to everyone else while a player resolves a decision.
function renderOpponentDecidingBanner() {
  let banner = document.querySelector("#rulesOpponentDeciding");
  if (!banner) {
    banner = document.createElement("div");
    banner.id = "rulesOpponentDeciding";
    banner.className = "rules-opponent-deciding hidden";
    document.body.appendChild(banner);
  }
  const choice = latestState?.rulesEngine?.enabled ? latestState.rulesEngine.pendingChoice : null;
  const waiting = Boolean(choice && choice.playerId && (isObserver || choice.playerId !== myPlayerId));
  banner.classList.toggle("hidden", !waiting);
  if (!waiting) return;
  const cardId = choice.sourceCardId || choice.targetCardId || choice.cardId;
  const image = cardId ? cardImage(cardId) : "";
  banner.innerHTML = `${image ? `<img src="${esc(image)}" alt="">` : ""}<span>${esc(rulesText("rulesOpponentDeciding", {
    player: rulesPlayerName(choice.playerId),
    card: cardId ? cardName(cardId) : "",
  }))}</span>`;
}

// "Nobody can play a card or an effect: resolve the Confrontation?" — shown to the
// player holding priority instead of passing through the Reaction step silently.
function renderResolvePrompt() {
  let prompt = document.querySelector("#rulesResolvePrompt");
  if (!prompt) {
    prompt = document.createElement("div");
    prompt.id = "rulesResolvePrompt";
    prompt.className = "rules-resolve-prompt hidden";
    prompt.innerHTML = `<span id="rulesResolvePromptText"></span><button type="button" class="primary" id="rulesResolvePromptBtn"></button>`;
    document.body.appendChild(prompt);
    prompt.querySelector("button").onclick = () => {
      prompt.classList.add("hidden");
      send({ type: "pass_priority" });
    };
  }
  const rules = latestState?.rulesEngine;
  const show = Boolean(
    rules?.enabled && rules.resolvePrompt && !isObserver
    && rules.priorityPlayerId === myPlayerId && !rules.pendingChoice,
  );
  prompt.classList.toggle("hidden", !show);
  if (!show) return;
  prompt.querySelector("#rulesResolvePromptText").textContent = t("rulesResolvePrompt");
  prompt.querySelector("button").textContent = t("rulesResolvePromptBtn");
}

// Hand choices use a drop onto the effect screen; clicking a hand card only inspects it.
let handDropSelection = { choiceId: null, playerId: null, hand: null, indexes: [] };

function rulesHandDropChoice() {
  const choice = latestState?.rulesEngine?.pendingChoice;
  if (!choice || choice.playerId !== myPlayerId || isObserver) return null;
  if (choice.kind === "peek_top_card") return choice.allowSwap ? choice : null;
  if (!["discard_from_hand", "hand_overflow"].includes(choice.kind)) return null;
  if (Array.isArray(choice.candidateCardIds)) return null;
  return choice;
}

function rulesHandDropSelected(choice) {
  const hand = JSON.stringify(latestState?.players?.[myPlayerId]?.zones?.hand?.cards || []);
  if (handDropSelection.choiceId !== choice.id || handDropSelection.playerId !== myPlayerId || handDropSelection.hand !== hand)
    handDropSelection = { choiceId: choice.id, playerId: myPlayerId, hand, indexes: [] };
  return handDropSelection.indexes;
}

function sendHandDropSelection(choice) {
  const hand = latestState?.players?.[myPlayerId]?.zones?.hand?.cards || [];
  const cardIds = rulesHandDropSelected(choice).map((index) => hand[index]).filter(Boolean);
  sendRulesChoiceAnswer({ type: "resolve_rules_choice", choiceId: choice.id, cardIds });
}

function pickHandDropCard(handIndex, fromDrop = false) {
  const choice = rulesHandDropChoice();
  if (!choice) return false;
  if (rulesChoiceAnswerPending?.choiceId === choice.id) return true;
  if (!fromDrop) return false;
  const hand = latestState?.players?.[myPlayerId]?.zones?.hand?.cards || [];
  const cardId = hand[handIndex];
  const requiredTypes = Array.isArray(choice.requireTypes) && choice.requireTypes.length ? choice.requireTypes
    : choice.requireManifestation ? ["manifestation"] : null;
  if (!cardId || (requiredTypes && !requiredTypes.includes(cardsById.get(cardId)?.type))) {
    showToast(t("rulesBoardCardNotPlayable"), true);
    return true;
  }
  if (choice.kind === "peek_top_card") {
    // a hand card dropped on the peek screen swaps with the top card (a plain click does nothing)
    if (!fromDrop) return true;
    sendRulesChoiceAnswer({ type: "resolve_rules_choice", choiceId: choice.id, option: "swap", cardIds: [cardId] });
    return true;
  }
  const limit = Number(choice.count || 1);
  const selected = rulesHandDropSelected(choice);
  const position = selected.indexOf(handIndex);
  if (
    choice.destination === "stalemate_for_support" && cardId === choice.sourceCardId && position < 0
    && hand.filter((id) => id === cardId).length - selected.filter((index) => hand[index] === cardId).length <= 1
  ) {
    // Chabak enters after the two other cards are put into Stalemate. Keep
    // one physical copy in Hand; spare copies may still pay this choice.
    showToast(t("rulesBoardCardNotPlayable"), true);
    return true;
  }
  if (position >= 0) selected.splice(position, 1);
  else if (selected.length < limit) selected.push(handIndex);
  if (!choice.upTo && selected.length === limit) sendHandDropSelection(choice);
  else renderRulesChoice();
  return true;
}

// effect windows open only once the reveal flip and every queued animation have finished
function rulesAnimationsBusyFor() {
  return Math.max(boardFlipBusyUntil - performance.now(), rulesVfxQueueRemaining());
}

let rulesChoiceFlipTimer = null;

let rulesDeckReorderRetry = null;
let rulesChoiceRetry = null;

function renderRulesChoice(force = false) {
  const choice = latestState?.rulesEngine?.pendingChoice;
  if (rulesChoiceAnswerPending && (rulesChoiceAnswerPending.choiceId !== choice?.id || rulesChoiceAnswerPending.playerId !== myPlayerId))
    rulesChoiceAnswerPending = null;
  const waiting = rulesAnimationsBusyFor();
  if (waiting > 0 && latestState?.rulesEngine?.pendingChoice?.playerId === myPlayerId) {
    $("#rulesChoicePanel").classList.add("hidden");
    clearTimeout(rulesChoiceFlipTimer);
    rulesChoiceFlipTimer = setTimeout(() => { rulesChoiceFlipTimer = null; renderRulesChoice(); }, Math.min(waiting + 30, 2500));
    return;
  }
  renderResolvePrompt();
  renderOpponentDecidingBanner();
  renderRulesChoiceContent(force);
  if (!rulesChoiceRetry) rulesChoiceRetry = () => {
    rulesChoiceAnswerPending = null;
    renderRulesChoice(true);
  };
  lockRulesChoiceAnswer();
  syncRulesChoiceSourceCard();
  const handDrop = rulesHandDropChoice();
  const choicePanel = $("#rulesChoicePanel");
  const choiceOpen = !choicePanel.classList.contains("hidden");
  document.body.classList.toggle("hand-drop-choice", Boolean(handDrop) && choiceOpen);
  if (handDrop && choiceOpen) {
    const hint = choicePanel.querySelector(".rules-card-drop-hint") || document.createElement("p");
    hint.className = "rules-card-drop-hint";
    hint.textContent = t("rulesDragCardToEffect");
    choicePanel.querySelector(".rules-choice-options")?.appendChild(hint);
  }
  // a dark choice screen that does not use the hand also blocks it
  document.body.classList.toggle("choice-blocks-hand", choiceOpen && choicePanel.classList.contains("cards-screen") && !choicePanel.classList.contains("hand-drop") && !choicePanel.classList.contains("hand-swap"));
  const selected = handDrop ? rulesHandDropSelected(handDrop) : [];
  $$("[data-hand-card]").forEach((card) => card.classList.toggle("is-choice-selected", selected.includes(Number(card.dataset.handIndex))));
}

// A row of cards put in order by dragging them (pointer events: no browser drag image, no tab split).
function wireDragOrderRow(row, onReorder) {
  const keys = () => [...row.querySelectorAll("[data-order-key]")].map((entry) => entry.dataset.orderKey);
  row.querySelectorAll("[data-order-key]").forEach((card) => {
    card.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 || event.isPrimary === false) return;
      event.preventDefault();
      const start = keys().join("|");
      const originalCards = [...row.querySelectorAll("[data-order-key]")];
      card.classList.add("is-dragging");
      const move = (e) => {
        const siblings = [...row.querySelectorAll("[data-order-key]")].filter((entry) => entry !== card);
        const before = siblings.find((entry) => {
          const rect = entry.getBoundingClientRect();
          return e.clientY < rect.top || (e.clientY <= rect.bottom && e.clientX < rect.left + rect.width / 2);
        });
        if (before) row.insertBefore(card, before);
        else row.appendChild(card);
      };
      const up = (e) => {
        card.classList.remove("is-dragging");
        if (e.type !== "pointerup") {
          originalCards.forEach((entry) => row.appendChild(entry));
          return;
        }
        if (keys().join("|") !== start) onReorder(keys());
      };
      // Moving between parents releases browser capture; the window still tracks the gesture.
      startCardPointerDrag(event, card, move, up, { capture: false });
    });
  });
}

function dragOrderCardHtml(key, cardId, label, number) {
  return `<div class="rules-choice-card" data-order-key="${esc(key)}" title="${esc(cardName(cardId))}">
    <b class="rules-choice-badge">${number}</b>
    <img src="${esc(cardImage(cardId))}" alt="" draggable="false">
    <span>${esc(label || cardName(cardId))}</span>
  </div>`;
}

// Drag a single card onto one of several slots (or click a slot); the nearest slot lights up on approach.
function wireCardToSlots(card, slots, onPick) {
  const nearest = (e) => {
    let best = null;
    let bestDistance = 130;
    slots.forEach((slot) => {
      const rect = slot.getBoundingClientRect();
      const distance = Math.hypot(Math.max(rect.left - e.clientX, 0, e.clientX - rect.right), Math.max(rect.top - e.clientY, 0, e.clientY - rect.bottom));
      if (distance < bestDistance) { bestDistance = distance; best = slot; }
    });
    return best;
  };
  card.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || event.isPrimary === false) return;
    event.preventDefault();
    const originX = event.clientX;
    const originY = event.clientY;
    card.classList.add("is-dragging");
    const move = (e) => {
      card.style.transform = `translate(${e.clientX - originX}px, ${e.clientY - originY}px)`;
      const near = nearest(e);
      slots.forEach((slot) => slot.classList.toggle("is-over", slot === near));
    };
    const up = (e) => {
      card.classList.remove("is-dragging");
      card.style.transform = "";
      slots.forEach((slot) => slot.classList.remove("is-over"));
      const near = e.type === "pointerup" ? nearest(e) : null;
      if (near) onPick(near);
    };
    startCardPointerDrag(event, card, move, up);
  });
  slots.forEach((slot) => { slot.onclick = () => onPick(slot); });
}

// Every rules choice uses the same effect screen: dark backdrop, no window, the source card on the left,
// the effect text and the prompt centered, unframed choices. Specialised screens set their own layout.
function renderRulesChoiceContent(force = false) {
  // Keep in-progress picks, typed answers and drag order when an unrelated
  // server update redraws the table. Changes to choice inputs still rebuild it.
  const key = JSON.stringify([
    myPlayerId, isObserver, currentLanguage, latestState?.rulesEngine?.enabled, latestState?.ended,
    latestState?.rulesEngine?.pendingChoice, pendingTriggeredPlacement,
    latestState?.players?.[myPlayerId]?.zones?.hand?.cards,
    rulesHandDropChoice() ? [...rulesHandDropSelected(rulesHandDropChoice())] : [],
    Object.entries(latestState?.players || {}).map(([id, player]) => [id, player.name, player.seat]),
    (latestState?.battlefield || []).map((item) => [item.id, item.cardId, item.controllerId, item.ownerId, item.faceUp]),
  ]);
  if (!force && rulesChoiceRenderKey === key) {
    $("#rulesChoicePanel").classList.toggle("hidden", !rulesChoiceContentVisible);
    return;
  }
  rulesChoiceRenderKey = key;
  rulesDeckReorderRetry = null;
  rulesChoiceRetry = null;
  const panel = $("#rulesChoicePanel");
  panel.classList.remove("effect-screen");
  renderRulesChoiceScreen();
  rulesChoiceContentVisible = !panel.classList.contains("hidden");
  const specialised = ["hand-drop", "destination-screen", "replace-screen"].some((name) => panel.classList.contains(name))
    || latestState?.rulesEngine?.pendingChoice?.kind === "deck_reorder" && !pendingTriggeredPlacement;
  if (!panel.classList.contains("hidden") && !specialised) panel.classList.add("cards-screen", "effect-screen");
}

function renderRulesChoiceScreen() {
  const panel = $("#rulesChoicePanel");
  const closeButton = $("#rulesChoiceCloseBtn");
  const options = $("#rulesChoiceOptions");
  options.classList.remove(
    "has-destination-card", "has-order", "has-card-picker", "is-reveal-hand", "is-destination-screen", "has-hand-selection",
  );
  panel.classList.remove("cards-screen", "destination-screen", "hand-drop", "replace-screen", "chain-screen", "player-screen", "hand-swap", "temperament-screen", "deck-reorder-screen");
  if (pendingTriggeredPlacement) {
    const { payload } = pendingTriggeredPlacement;
    $("#rulesChoiceHeading").textContent = t("rulesChooseTriggerTargetHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesChooseTriggerTargetText", { card: cardName(payload.cardId) });
    panel.classList.add("cards-screen", "player-screen");
    closeButton.classList.remove("hidden");
    options.innerHTML = Object.entries(latestState?.players || {}).map(([playerId, player]) => `
      <button type="button" class="rules-choice-player" data-rules-player-target="${esc(playerId)}" style="--player-tone:${esc(playerColor(playerId))}">
        ${esc(playerId === myPlayerId ? t("rulesTargetSelf") : t("rulesTargetOpponent"))} · ${esc(rulesPlayerName(playerId))}
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
  if (!latestState?.rulesEngine?.enabled || latestState?.ended || !choice || choice.playerId !== myPlayerId || isObserver) {
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
    panel.classList.add("cards-screen", "chain-screen");
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
          <strong>${esc(t("passPhase"))}</strong>
        </button>` : ""}`;
    $$("[data-rules-chain-card]").forEach((button) => {
      button.onclick = () => {
        const center = fieldCenterLogical();
        options.querySelectorAll("button").forEach((entry) => {
          entry.disabled = true;
        });
        sendRulesChoiceAnswer({
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
        sendRulesChoiceAnswer({
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
    // Drag and drop: each group has a lane per destination (top / bottom / extra);
    // dragging a card inside a lane reorders it, dragging it to another lane moves it.
    const laneDefs = (group) => [
      { side: "top", label: t("rulesDeckTop") },
      { side: "bottom", label: t("rulesDeckBottom") },
      ...(group.extraSide ? [{ side: "extra", label: t(group.extraSide === "hand" ? "rulesDeckToHand" : "rulesDeckExile") }] : []),
    ];
    const initialSide = (group, index) => {
      const topCount = Number(group.topCount);
      const bottomCount = Number(group.bottomCount);
      if (group.topCount != null && group.bottomCount != null && Number.isInteger(topCount) && Number.isInteger(bottomCount)) {
        return index < topCount ? "top" : "bottom";
      }
      return "pool";
    };
    // cards-only screen: the cards to place wait in the middle, the destinations sit on the right
    panel.classList.add("cards-screen", "deck-reorder-screen");
    const cardMarkup = (cardId) => `
      <div class="rules-reorder-card rules-choice-card" data-rules-reorder-card="${esc(cardId)}" title="${esc(cardName(cardId))}">
        <img src="${esc(cardImage(cardId))}" alt="${esc(cardName(cardId))}"><b></b>
      </div>`;
    options.innerHTML = `
      ${(choice.groups || []).map((group) => `
        <section class="rules-reorder-group" data-rules-reorder-group="${esc(group.playerId)}">
          <div class="rules-reorder-strip rules-reorder-pool" data-rules-reorder-strip="pool">
            ${(group.cardIds || []).map((cardId, index) => initialSide(group, index) === "pool" ? cardMarkup(cardId) : "").join("")}
          </div>
          <div class="rules-reorder-lanes">
            ${laneDefs(group).map((lane) => `
              <div class="rules-reorder-lane" data-rules-reorder-lane="${esc(lane.side)}">
                <small>${lane.side !== "extra" ? `<img class="rules-reorder-back" src="card-back.webp?v=20260905-1" alt="" draggable="false">` : ""}${esc(lane.label)}</small>
                <div class="rules-reorder-strip" data-rules-reorder-strip="${esc(lane.side)}">
                  ${(group.cardIds || []).map((cardId, index) => initialSide(group, index) === lane.side ? cardMarkup(cardId) : "").join("")}
                </div>
              </div>`).join("")}
          </div>
        </section>`).join("")}
      <p class="rules-reorder-hint hidden" id="rulesDeckReorderHint"></p>
      <button type="button" class="primary rules-reorder-confirm" id="rulesDeckReorderConfirm">${esc(t("confirm"))}</button>`;
    // how many cards each destination may hold (Expansive Ponderer: exactly one to the hand)
    const laneLimit = (group, side) => {
      if (side === "extra" && group.extraSide) return Number(group.extraMax ?? Infinity);
      if (side === "top" && group.topCount != null) return Number(group.topCount);
      if (side === "bottom" && group.bottomCount != null) return Number(group.bottomCount);
      return Infinity;
    };
    const groupFor = (section) => (choice.groups || []).find((group) => group.playerId === section.dataset.rulesReorderGroup);
    const reorderProblem = () => {
      for (const group of choice.groups || []) {
        const section = options.querySelector(`[data-rules-reorder-group="${CSS.escape(group.playerId)}"]`);
        if (!section) continue;
        if (section.querySelector('[data-rules-reorder-strip="pool"] .rules-reorder-card')) return "pool";
        const count = (side) => section.querySelectorAll(`[data-rules-reorder-strip="${side}"] .rules-reorder-card`).length;
        if (group.extraSide && (count("extra") < Number(group.extraMin || 0) || count("extra") > Number(group.extraMax ?? Infinity))) {
          return rulesText("rulesDeckReorderExtraCount", {
            count: Number(group.extraMin || 0) === Number(group.extraMax) ? group.extraMax : `${group.extraMin || 0}–${group.extraMax}`,
            zone: t(group.extraSide === "hand" ? "rulesDeckToHand" : "rulesDeckExile"),
          });
        }
        if (group.topCount != null && count("top") !== Number(group.topCount)) return t("rulesDeckReorderLaneCount");
        if (group.bottomCount != null && count("bottom") !== Number(group.bottomCount)) return t("rulesDeckReorderLaneCount");
      }
      return null;
    };
    const showReorderProblem = () => {
      const problem = reorderProblem();
      const hint = $("#rulesDeckReorderHint");
      if (!hint) return problem;
      hint.textContent = problem && problem !== "pool" ? problem : "";
      hint.classList.toggle("hidden", !problem || problem === "pool");
      if ($("#rulesDeckReorderConfirm")) $("#rulesDeckReorderConfirm").disabled = Boolean(problem);
      return problem;
    };
    const numberStrips = () => {
      options.querySelectorAll(".rules-reorder-strip").forEach((strip) => {
        strip.querySelectorAll(".rules-reorder-card").forEach((card, index) => {
          card.querySelector("b").textContent = String(index + 1);
        });
      });
    };
    numberStrips();
    options.querySelectorAll(".rules-reorder-card").forEach((card) => {
      card.addEventListener("pointerdown", (event) => {
        if (event.button !== 0 || event.isPrimary === false) return;
        event.preventDefault();
        const section = card.closest("[data-rules-reorder-group]");
        card.classList.add("is-dragging");
        const move = (e) => {
          // the card snaps to the nearest destination as it gets close, so the drop target is obvious
          let strip = null;
          let best = 110;
          section.querySelectorAll(".rules-reorder-strip").forEach((entry) => {
            const rect = entry.getBoundingClientRect();
            const dx = Math.max(rect.left - e.clientX, 0, e.clientX - rect.right);
            const dy = Math.max(rect.top - e.clientY, 0, e.clientY - rect.bottom);
            const distance = Math.hypot(dx, dy);
            if (distance < best) { best = distance; strip = entry; }
          });
          // a full destination does not take one more card: the card stays where it was
          if (strip && strip !== card.parentElement) {
            const held = [...strip.querySelectorAll(".rules-reorder-card")].filter((other) => other !== card).length;
            if (held >= laneLimit(groupFor(section), strip.dataset.rulesReorderStrip)) strip = null;
          }
          options.querySelectorAll(".rules-reorder-strip").forEach((entry) => entry.classList.toggle("is-over", entry === strip));
          if (!strip || strip.closest("[data-rules-reorder-group]") !== section) return;
          const siblings = [...strip.querySelectorAll(".rules-reorder-card")].filter((entry) => entry !== card);
          const before = siblings.find((entry) => {
            const rect = entry.getBoundingClientRect();
            return e.clientY < rect.top || (e.clientY <= rect.bottom && e.clientX < rect.left + rect.width / 2);
          });
          if (before) strip.insertBefore(card, before);
          else strip.appendChild(card);
          numberStrips();
        };
        const up = () => {
          card.classList.remove("is-dragging");
          options.querySelectorAll(".rules-reorder-strip").forEach((entry) => entry.classList.remove("is-over"));
          // the order is only sent with the Confirm button, so it can still be changed
          showReorderProblem();
        };
        startCardPointerDrag(event, card, move, up, { capture: false });
      });
    });
    let reorderSent = false;
    // a refused distribution can be corrected and sent again
    rulesDeckReorderRetry = () => { rulesChoiceAnswerPending = null; reorderSent = false; showReorderProblem(); lockRulesChoiceAnswer(); };
    rulesChoiceRetry = rulesDeckReorderRetry;
    const submitReorder = () => {
      if (reorderSent || showReorderProblem()) return;
      reorderSent = true;
      const groups = (choice.groups || []).map((group) => {
        const section = options.querySelector(`[data-rules-reorder-group="${CSS.escape(group.playerId)}"]`);
        const ordered = (side) => [...section.querySelectorAll(`[data-rules-reorder-strip="${side}"] .rules-reorder-card`)]
          .map((card) => card.dataset.rulesReorderCard);
        return {
          playerId: group.playerId, top: ordered("top"), bottom: ordered("bottom"),
          ...(group.extraSide ? { extra: ordered("extra") } : {}),
        };
      });
      sendRulesChoiceAnswer({ type: "resolve_rules_choice", choiceId: choice.id, option: { groups } });
    };
    if ($("#rulesDeckReorderConfirm")) $("#rulesDeckReorderConfirm").onclick = submitReorder;
    showReorderProblem();
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "guess_top_card") {
    $("#rulesChoiceHeading").textContent = t("rulesGuessTopCardHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesGuessTopCardText", {
      player: rulesPlayerName(choice.targetPlayerId),
    });
    // three rows of unframed chips (type, temperament, power or cost) instead of drop-down menus
    const guess = {
      type: (choice.types || [])[0],
      temperament: (choice.temperaments || [])[0],
      value: (choice.values || [])[0],
    };
    const chipGroup = (field, label, values, render) => `
      <div class="rules-chip-group">
        <small>${esc(label)}</small>
        <div class="rules-chip-row">
          ${values.map((value) => `<button type="button" class="rules-chip" data-rules-guess-field="${field}" data-rules-guess-value="${esc(value)}" aria-pressed="${String(value) === String(guess[field])}">${render(value)}</button>`).join("")}
        </div>
      </div>`;
    options.innerHTML = `
      ${chipGroup("type", t("type"), choice.types || [], (value) => esc(t(value === "will" ? "rulesTypeWill" : "rulesTypeManifestation")))}
      ${chipGroup("temperament", t("temperament"), choice.temperaments || [], (value) => `<img src="${esc(temperamentSymbol(value))}" alt="">${esc(t(`temperament${value[0].toUpperCase()}${value.slice(1)}`))}`)}
      ${chipGroup("value", t("rulesPowerOrCost"), choice.values || [], (value) => esc(value))}
      <button type="button" class="primary" id="rulesGuessConfirm">${esc(t("confirm"))}</button>`;
    $$("[data-rules-guess-field]").forEach((chip) => {
      chip.onclick = () => {
        const field = chip.dataset.rulesGuessField;
        guess[field] = chip.dataset.rulesGuessValue;
        $$(`[data-rules-guess-field="${field}"]`).forEach((entry) => entry.setAttribute("aria-pressed", String(entry === chip)));
      };
    });
    $("#rulesGuessConfirm").onclick = (event) => {
      event.currentTarget.disabled = true;
      sendRulesChoiceAnswer({
        type: "resolve_rules_choice",
        choiceId: choice.id,
        option: { type: guess.type, temperament: guess.temperament, value: Number(guess.value) },
      });
    };
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "peek_top_card") {
    $("#rulesChoiceHeading").textContent = t("rulesPeekTopCardHeading");
    $("#rulesChoiceText").textContent = `${rulesText("rulesPeekTopCardText", {
      card: cardName(choice.cardId),
    })}${choice.allowSwap ? ` ${t("rulesPeekSwapHint")}` : ""}`;
    // the peeked card in the middle, dragged (or a slot clicked) to the top or the bottom of the deck;
    // a hand card dragged onto the screen swaps with it
    options.innerHTML = `
      <div class="rules-peek-row">
        <div class="rules-peek-card" title="${esc(cardName(choice.cardId))}"><img src="${esc(cardImage(choice.cardId))}" alt="${esc(cardName(choice.cardId))}" draggable="false"></div>
        <div class="rules-peek-slots">
          <button type="button" class="rules-peek-slot" data-rules-peek-option="keep">
            <img src="card-back.webp?v=20260905-1" alt=""><strong>${esc(t("rulesKeepOnTopShort"))}</strong>
          </button>
          <button type="button" class="rules-peek-slot" data-rules-peek-option="bottom">
            <img src="card-back.webp?v=20260905-1" alt=""><strong>${esc(t("rulesDeckBottom"))}</strong>
          </button>
        </div>
      </div>`;
    let peekSent = false;
    wireCardToSlots(options.querySelector(".rules-peek-card"), [...options.querySelectorAll("[data-rules-peek-option]")], (slot) => {
      if (peekSent) return;
      peekSent = true;
      options.querySelectorAll("button").forEach((button) => { button.disabled = true; });
      sendRulesChoiceAnswer({ type: "resolve_rules_choice", choiceId: choice.id, option: slot.dataset.rulesPeekOption });
    });
    if (choice.allowSwap) panel.classList.add("hand-swap");
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
        sendRulesChoiceAnswer({
          type: "resolve_rules_choice",
          choiceId: choice.id,
          option: button.dataset.rulesOptionalTrigger,
        });
      };
    });
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "token_count") {
    $("#rulesChoiceHeading").textContent = t("rulesTokenCountHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesTokenCountText", { max: choice.max });
    options.innerHTML = (choice.options || []).map((value) => `
      <button type="button" class="rules-choice-destination" data-rules-token-count="${esc(value)}">
        <strong>${esc(value)}</strong>
      </button>`).join("");
    $$("[data-rules-token-count]").forEach((button) => {
      button.onclick = () => {
        button.disabled = true;
        sendRulesChoiceAnswer({
          type: "resolve_rules_choice",
          choiceId: choice.id,
          option: button.dataset.rulesTokenCount,
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
        sendRulesChoiceAnswer({
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
    $("#rulesChoiceText").textContent = t(choice.position === "bottom" ? "rulesSupportBottomOrderText" : "rulesSupportOrderText");
    let ordered = [...(choice.items || [])];
    const paintOrder = () => {
      options.innerHTML = `
        <div class="rules-drag-order">
          ${ordered.map((item, index) => dragOrderCardHtml(item.itemId, item.cardId, "", index + 1)).join("")}
        </div>
        <p class="rules-drag-order-hint">${esc(t("rulesDragToOrder"))}</p>
        <button type="button" class="primary" id="rulesSupportOrderConfirm">${esc(t("confirm"))}</button>`;
      wireDragOrderRow(options.querySelector(".rules-drag-order"), (keys) => {
        ordered = keys.map((key) => ordered.find((item) => item.itemId === key)).filter(Boolean);
        paintOrder();
      });
      $("#rulesSupportOrderConfirm").onclick = (event) => {
        event.currentTarget.disabled = true;
        sendRulesChoiceAnswer({
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
        sendRulesChoiceAnswer({
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
        sendRulesChoiceAnswer({ type: "resolve_rules_choice", choiceId: choice.id, option: button.dataset.rulesWeakenOption });
      };
    });
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "declare_card_name") {
    $("#rulesChoiceHeading").textContent = t("rulesDeclareNameHeading");
    $("#rulesChoiceText").textContent = rulesText(
      choice.mode === "search_deck" ? "rulesDeclareNameSearchText" : "rulesDeclareNameTopText",
      { card: cardName(choice.sourceCardId), player: rulesPlayerName(choice.targetPlayerId) },
    );
    const names = new Map();
    for (const cardId of cardsById.keys()) {
      const name = cardName(cardId);
      if (name && !names.has(name.toLowerCase())) names.set(name.toLowerCase(), { name, cardId });
    }
    options.innerHTML = `
      <label>${esc(t("rulesDeclareNameLabel"))}
        <input id="rulesDeclareNameInput" list="rulesDeclareNameList" autocomplete="off">
      </label>
      <datalist id="rulesDeclareNameList">${[...names.values()].map((entry) => `<option value="${esc(entry.name)}"></option>`).join("")}</datalist>
      <button type="button" class="primary" id="rulesDeclareNameConfirm" disabled>${esc(t("confirm"))}</button>`;
    const input = $("#rulesDeclareNameInput");
    const confirmButton = $("#rulesDeclareNameConfirm");
    const declared = () => names.get(input.value.trim().toLowerCase());
    input.oninput = () => { confirmButton.disabled = !declared(); };
    confirmButton.onclick = () => {
      const entry = declared();
      if (!entry) return;
      confirmButton.disabled = true;
      sendRulesChoiceAnswer({ type: "resolve_rules_choice", choiceId: choice.id, option: entry.cardId });
    };
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "temperament_choice") {
    panel.classList.add("temperament-screen");
    $("#rulesChoiceHeading").textContent = t("rulesTemperamentChoiceHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesTemperamentChoiceText", { card: cardName(choice.sourceCardId) });
    options.innerHTML = (choice.options || []).map((temperament) => `
      <button type="button" class="rules-choice-destination" data-rules-temperament-option="${esc(temperament)}">
        <img class="rules-temperament-choice-symbol" src="${esc(temperamentSymbol(temperament))}" alt="">
        <strong>${esc(t(`temperament${temperament[0].toUpperCase()}${temperament.slice(1)}`))}</strong>
      </button>`).join("");
    $$("[data-rules-temperament-option]").forEach((button) => {
      button.onclick = () => {
        button.disabled = true;
        sendRulesChoiceAnswer({ type: "resolve_rules_choice", choiceId: choice.id, option: button.dataset.rulesTemperamentOption });
      };
    });
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "binary_choice") {
    const params = { card: cardName(choice.sourceCardId), target: cardName(choice.relatedCardId), effect: cardName(choice.incomingCardId) };
    $("#rulesChoiceHeading").textContent = t(choice.headingKey);
    $("#rulesChoiceText").textContent = rulesText(choice.textKey, params);
    if (choice.purpose === "amphora_pick") {
      // two face-down manifestations: the picked back enters Support, the other goes to Limbo
      options.innerHTML = `
        <div class="rules-amphora-pick">
          ${[["yes", choice.yesKey], ["no", choice.noKey]].map(([option, key]) => `
            <button type="button" class="rules-amphora-back" data-rules-binary-option="${option}" title="${esc(rulesText(key, params))}">
              <img src="card-back.webp?v=20260905-1" alt="${esc(rulesText(key, params))}" draggable="false">
              <span>${esc(t("rulesAmphoraPick"))}</span>
            </button>`).join("")}
        </div>`;
    } else options.innerHTML = `
      <button type="button" class="rules-choice-destination" data-rules-binary-option="yes">
        <strong>${esc(rulesText(choice.yesKey, params))}</strong>
      </button>
      <button type="button" class="rules-choice-destination" data-rules-binary-option="no">
        <strong>${esc(rulesText(choice.noKey, params))}</strong>
      </button>`;
    $$("[data-rules-binary-option]").forEach((button) => {
      button.onclick = () => {
        $$("[data-rules-binary-option]").forEach((other) => { other.disabled = true; });
        button.classList.add("is-picked");
        sendRulesChoiceAnswer({ type: "resolve_rules_choice", choiceId: choice.id, option: button.dataset.rulesBinaryOption });
      };
    });
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "clemency_choice") {
    $("#rulesChoiceHeading").textContent = t("rulesClemencyHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesClemencyText", {
      card: cardName(choice.sourceCardId),
      will: cardName(choice.relatedCardId),
      points: choice.points,
    });
    options.innerHTML = `
      <button type="button" class="rules-choice-destination" data-rules-clemency-option="allow">
        <strong>${esc(rulesText("rulesClemencyAllow", { points: choice.points }))}</strong>
      </button>
      <button type="button" class="rules-choice-destination" data-rules-clemency-option="neutralize">
        <strong>${esc(t("rulesClemencyNeutralize"))}</strong>
      </button>`;
    $$("[data-rules-clemency-option]").forEach((button) => {
      button.onclick = () => {
        button.disabled = true;
        sendRulesChoiceAnswer({ type: "resolve_rules_choice", choiceId: choice.id, option: button.dataset.rulesClemencyOption });
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
        sendRulesChoiceAnswer({
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
    const limit = Number(choice.count || 0);
    if (choice.kind === "hand_overflow") {
      // the cards stay in the hand: drag the ones to put away, like a discard from hand
      panel.classList.add("cards-screen", "hand-drop");
      options.innerHTML = "";
      panel.classList.remove("hidden");
      return;
    }
    const selected = new Set();
    options.classList.add("has-card-picker");
    options.innerHTML = `
      ${sourceCards.map((cardId, index) => `
        <button type="button" class="rules-choice-card" data-rules-private-card="${index}" aria-pressed="false" title="${esc(cardName(cardId))}">
          <img src="${esc(cardImage(cardId))}" alt="">
          <span>${esc(cardName(cardId))}</span>
        </button>`).join("")}
      ${limit > 1 ? `<button type="button" class="primary" id="rulesPrivateCardsConfirm" disabled>${esc(t("confirm"))}</button>` : ""}`;
    const sendPrivateCards = () => {
      options.querySelectorAll("button").forEach((button) => { button.disabled = true; });
      sendRulesChoiceAnswer({
        type: "resolve_rules_choice",
        choiceId: choice.id,
        cardIds: [...selected].map((index) => sourceCards[index]).filter(Boolean),
      });
    };
    $$("[data-rules-private-card]").forEach((button) => {
      button.onclick = () => {
        const index = Number(button.dataset.rulesPrivateCard);
        if (selected.has(index)) selected.delete(index);
        else if (selected.size < limit) selected.add(index);
        button.setAttribute("aria-pressed", selected.has(index) ? "true" : "false");
        // a single card: picking it is the answer, no confirmation step
        if (limit <= 1 && selected.size === 1) { sendPrivateCards(); return; }
        if ($("#rulesPrivateCardsConfirm")) $("#rulesPrivateCardsConfirm").disabled = selected.size !== limit;
      };
    });
    if ($("#rulesPrivateCardsConfirm")) $("#rulesPrivateCardsConfirm").onclick = sendPrivateCards;
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
    // click a card to give it one point of power loss; the choice is sent once every point is assigned
    const total = Number(choice.count || 0);
    const assigned = [];
    options.classList.add("has-card-picker");
    const paintDistribution = () => {
      options.innerHTML = `
        ${candidates.map((item) => {
          const given = assigned.filter((itemId) => itemId === item.id).length;
          return `<button type="button" class="rules-choice-card" data-rules-power-target="${esc(item.id)}" aria-pressed="${given ? "true" : "false"}" title="${esc(cardName(item.cardId))}">
            <b class="rules-choice-badge" data-rules-power-undo="${esc(item.id)}">${given ? `−${given}` : ""}</b>
            <img src="${esc(cardImage(item.cardId))}" alt="">
            <span>${esc(cardName(item.cardId))}</span>
          </button>`;
        }).join("")}
        <p class="rules-drag-order-hint">${esc(rulesText("rulesPowerLossLeft", { count: total - assigned.length }))} · ${esc(t("rulesPowerLossHint"))}</p>`;
      $$("[data-rules-power-target]").forEach((button) => {
        button.onclick = (event) => {
          const itemId = button.dataset.rulesPowerTarget;
          if (event.target.closest("[data-rules-power-undo]")) {
            const index = assigned.lastIndexOf(itemId);
            if (index < 0) return;
            assigned.splice(index, 1);
            paintDistribution();
            return;
          }
          if (assigned.length >= total) return;
          assigned.push(itemId);
          if (assigned.length < total) { paintDistribution(); return; }
          options.querySelectorAll("button").forEach((entry) => { entry.disabled = true; });
          sendRulesChoiceAnswer({ type: "resolve_rules_choice", choiceId: choice.id, option: { itemIds: [...assigned] } });
        };
      });
    };
    paintDistribution();
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
    options.classList.add("has-card-picker");
    options.innerHTML = candidates.map((item) => `
      <button type="button" class="rules-choice-card" data-rules-random-target="${esc(item.id)}">
        <img src="${esc(cardImage(item.cardId))}" alt="">
        <span>${esc(cardName(item.cardId))}</span>
      </button>`).join("");
    $$("[data-rules-random-target]").forEach((button) => {
      button.onclick = () => {
        button.disabled = true;
        sendRulesChoiceAnswer({
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
        sendRulesChoiceAnswer({
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
    $("#rulesChoiceText").textContent = `${rulesText("rulesRelocationText", {
      card: cardName(choice.sourceCardId),
    })} ${t("rulesRelocationHint")}`;
    // each Manifestation waits in the middle and is dragged to the Interzone (limited slots) or under the deck, in order
    const cardOf = (itemId) => latestState?.battlefield?.find((entry) => entry.id === itemId)?.cardId;
    const laneCard = (itemId) => `
      <div class="rules-reorder-card rules-choice-card" data-rules-relocation-card="${esc(itemId)}" title="${esc(cardName(cardOf(itemId)))}">
        <b class="rules-choice-badge"></b>
        <img src="${esc(cardImage(cardOf(itemId)))}" alt="" draggable="false">
      </div>`;
    options.innerHTML = (choice.groups || []).map((group) => `
      <section class="rules-reorder-group" data-rules-relocation-group="${esc(group.playerId)}" data-slots="${Number(group.interzoneSlots || 0)}">
        ${(choice.groups || []).length > 1 ? `<strong>${esc(rulesPlayerName(group.playerId))}</strong>` : ""}
        <div class="rules-reorder-strip rules-reorder-pool" data-rules-relocation-strip="pool">
          ${(group.itemIds || []).map(laneCard).join("")}
        </div>
        <div class="rules-reorder-lanes">
          <div class="rules-reorder-lane">
            <small>${esc(t("interzone"))} · ${esc(rulesText("rulesInterzoneSlots", { count: group.interzoneSlots }))}</small>
            <div class="rules-reorder-strip" data-rules-relocation-strip="interzone"></div>
          </div>
          <div class="rules-reorder-lane">
            <small>${esc(t("rulesDeckBottom"))}</small>
            <div class="rules-reorder-strip" data-rules-relocation-strip="deck"></div>
          </div>
        </div>
      </section>`).join("");
    let relocationSent = false;
    rulesChoiceRetry = () => { rulesChoiceAnswerPending = null; relocationSent = false; lockRulesChoiceAnswer(); };
    const refreshLanes = () => {
      options.querySelectorAll("[data-rules-relocation-group]").forEach((section) => {
        const interzone = section.querySelector('[data-rules-relocation-strip="interzone"]');
        interzone.classList.toggle("is-full", interzone.children.length >= Number(section.dataset.slots));
        section.querySelectorAll('[data-rules-relocation-strip="deck"] [data-rules-relocation-card]').forEach((card, index) => {
          card.querySelector("b").textContent = String(index + 1);
        });
        section.querySelectorAll('[data-rules-relocation-strip]:not([data-rules-relocation-strip="deck"]) b').forEach((badge) => { badge.textContent = ""; });
      });
    };
    const submitRelocation = () => {
      if (relocationSent) return;
      relocationSent = true;
      const groups = (choice.groups || []).map((group) => {
        const section = options.querySelector(`[data-rules-relocation-group="${CSS.escape(group.playerId)}"]`);
        const ids = (side) => [...section.querySelectorAll(`[data-rules-relocation-strip="${side}"] [data-rules-relocation-card]`)].map((card) => card.dataset.rulesRelocationCard);
        return { playerId: group.playerId, interzone: ids("interzone"), deckBottom: ids("deck") };
      });
      sendRulesChoiceAnswer({ type: "resolve_rules_choice", choiceId: choice.id, option: { groups } });
    };
    options.querySelectorAll("[data-rules-relocation-card]").forEach((card) => {
      card.addEventListener("pointerdown", (event) => {
        if (event.button !== 0 || event.isPrimary === false || relocationSent) return;
        event.preventDefault();
        const section = card.closest("[data-rules-relocation-group]");
        card.classList.add("is-dragging");
        const accepts = (strip) => strip.dataset.rulesRelocationStrip !== "interzone"
          || strip.contains(card) || strip.children.length < Number(section.dataset.slots);
        const move = (e) => {
          let strip = null;
          let best = 110;
          section.querySelectorAll("[data-rules-relocation-strip]").forEach((entry) => {
            if (!accepts(entry)) return;
            const rect = entry.getBoundingClientRect();
            const distance = Math.hypot(Math.max(rect.left - e.clientX, 0, e.clientX - rect.right), Math.max(rect.top - e.clientY, 0, e.clientY - rect.bottom));
            if (distance < best) { best = distance; strip = entry; }
          });
          section.querySelectorAll("[data-rules-relocation-strip]").forEach((entry) => entry.classList.toggle("is-over", entry === strip));
          if (!strip) return;
          const before = [...strip.querySelectorAll("[data-rules-relocation-card]")].filter((entry) => entry !== card).find((entry) => {
            const rect = entry.getBoundingClientRect();
            return e.clientY < rect.top || (e.clientY <= rect.bottom && e.clientX < rect.left + rect.width / 2);
          });
          if (before) strip.insertBefore(card, before);
          else strip.appendChild(card);
          refreshLanes();
        };
        const up = (e) => {
          card.classList.remove("is-dragging");
          section.querySelectorAll("[data-rules-relocation-strip]").forEach((entry) => entry.classList.remove("is-over"));
          // everything placed: no confirmation step
          if (e.type === "pointerup" && !options.querySelector('[data-rules-relocation-strip="pool"] [data-rules-relocation-card]')) submitRelocation();
        };
        startCardPointerDrag(event, card, move, up, { capture: false });
      });
    });
    refreshLanes();
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "suspend_hand_will") {
    $("#rulesChoiceHeading").textContent = t("rulesSuspendWillHeading");
    $("#rulesChoiceText").textContent = rulesText("rulesSuspendWillText", {
      card: cardName(choice.sourceCardId),
    });
    options.classList.add("has-card-picker");
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
        sendRulesChoiceAnswer({
          type: "resolve_rules_choice",
          choiceId: choice.id,
          cardIds: [cardId],
        });
      };
    });
    panel.classList.remove("hidden");
    return;
  }
  if (["simultaneous_stack_order", "replacement_order"].includes(choice.kind)) {
    options.classList.add("has-order");
    $("#rulesChoiceHeading").textContent = t(choice.kind === "replacement_order" ? "rulesReplacementOrderHeading" : "rulesSimultaneousOrderHeading");
    $("#rulesChoiceText").textContent = t(choice.kind === "replacement_order" ? "rulesReplacementOrderText" : "rulesSimultaneousOrderText");
    // shown in resolution order: the first card resolves first (top of the Pile);
    // the server takes the list from the bottom of the Pile up
    let ordered = [...(choice.actions || [])].reverse();
    const paintOrder = () => {
      options.innerHTML = `
        <div class="rules-drag-order">
          ${ordered.map((action, index) => dragOrderCardHtml(
            action.actionId, action.cardId,
              `${action.replacementKind ? t(`rulesReplacement_${action.replacementKind}`) : rulesActiveAbilityEffect(action.abilityId)?.text || action.label || cardName(action.cardId)}${action.immediate ? ` · ${t("rulesImmediateLabel")}` : ""}`,
            index + 1,
          )).join("")}
        </div>
        <p class="rules-drag-order-hint">${esc(t("rulesDragToOrder"))}</p>
        <button type="button" class="primary" id="rulesSimultaneousOrderConfirm">${esc(t("confirm"))}</button>`;
      wireDragOrderRow(options.querySelector(".rules-drag-order"), (keys) => {
        const moved = keys.map((key) => ordered.find((action) => action.actionId === key)).filter(Boolean);
        // immediate actions always stay above the others on the Pile: they resolve first
        ordered = [...moved.filter((action) => action.immediate), ...moved.filter((action) => !action.immediate)];
        paintOrder();
      });
      $("#rulesSimultaneousOrderConfirm").onclick = (event) => {
        event.currentTarget.disabled = true;
        sendRulesChoiceAnswer({
          type: "resolve_rules_choice",
          choiceId: choice.id,
          cardIds: ordered.map((action) => action.actionId).reverse(),
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
    options.classList.add("has-card-picker");
    options.innerHTML = candidates.map((item) => `
      <button type="button" class="rules-choice-card" data-rules-persist-item="${esc(item.id)}" title="${esc(cardName(item.cardId))}">
        <img src="${esc(cardImage(item.cardId))}" alt="">
        <span>${esc(cardName(item.cardId))}</span>
      </button>`).join("");
    $$("[data-rules-persist-item]").forEach((button) => {
      button.onclick = () => {
        button.disabled = true;
        sendRulesChoiceAnswer({
          type: "resolve_rules_choice",
          choiceId: choice.id,
          itemId: button.dataset.rulesPersistItem,
        });
      };
    });
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "pick_own_item") {
    const sacrifice = choice.purpose === "sacrifice";
    $("#rulesChoiceHeading").textContent = t(sacrifice ? "rulesSacrificeItemHeading" : "rulesPickOwnItemHeading");
    $("#rulesChoiceText").textContent = t(sacrifice ? "rulesSacrificeItemText" : "rulesPickOwnItemText");
    const candidates = (choice.candidateItemIds || [])
      .map((itemId) => latestState?.battlefield?.find((item) => item.id === itemId))
      .filter(Boolean);
    options.classList.add("has-card-picker");
    options.innerHTML = candidates.map((item) => `
      <button type="button" class="rules-choice-card" data-rules-pick-item="${esc(item.id)}" title="${esc(cardName(item.cardId))}">
        <img src="${esc(cardImage(item.cardId))}" alt="">
        <span>${esc(cardName(item.cardId))}</span>
      </button>`).join("");
    $$("[data-rules-pick-item]").forEach((button) => {
      button.onclick = () => {
        button.disabled = true;
        sendRulesChoiceAnswer({
          type: "resolve_rules_choice",
          choiceId: choice.id,
          itemId: button.dataset.rulesPickItem,
        });
      };
    });
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "pick_distribution_extra") {
    $("#rulesChoiceHeading").textContent = t("rulesDistributeHeading");
    $("#rulesChoiceText").textContent = t("rulesDistributeText");
    const candidates = (choice.candidateItemIds || [])
      .map((itemId) => latestState?.battlefield?.find((item) => item.id === itemId))
      .filter(Boolean);
    options.classList.add("has-card-picker");
    options.innerHTML = candidates.map((item) => `
      <button type="button" class="rules-choice-card" data-rules-distribute-item="${esc(item.id)}" title="${esc(cardName(item.cardId))}">
        <img src="${esc(cardImage(item.cardId))}" alt="">
        <span>${esc(cardName(item.cardId))}</span>
      </button>`).join("");
    $$("[data-rules-distribute-item]").forEach((button) => {
      button.onclick = () => {
        button.disabled = true;
        sendRulesChoiceAnswer({
          type: "resolve_rules_choice",
          choiceId: choice.id,
          itemId: button.dataset.rulesDistributeItem,
        });
      };
    });
    panel.classList.remove("hidden");
    return;
  }
  if (choice.kind === "reveal_hand_discard") {
    const pickKey = { womb: "rulesWombPick", bloatuba: "rulesBloatubaPick", gummo: "rulesGummoPick", wish: "rulesWishPick", pescojolero: "rulesPescoPick", lunar: "rulesLunarPick" }[choice.purpose];
    $("#rulesChoiceHeading").textContent = t(pickKey ? `${pickKey}Heading` : "rulesRevealDiscardHeading");
    $("#rulesChoiceText").textContent = rulesText(pickKey ? `${pickKey}Text` : "rulesRevealDiscardText", {
      player: rulesPlayerName(choice.targetPlayerId),
    });
    options.classList.add("has-card-picker", "is-reveal-hand");
    panel.classList.add("cards-screen");
    options.innerHTML = (choice.cardIds || []).map((cardId, index) => `
      <button type="button" class="rules-choice-card" data-rules-reveal-index="${index}" title="${esc(cardName(cardId))}">
        <img src="${esc(cardImage(cardId))}" alt="">
        <span>${esc(cardName(cardId))}</span>
      </button>`).join("");
    $$("[data-rules-reveal-index]").forEach((button) => {
      button.onclick = () => {
        $$("[data-rules-reveal-index]").forEach((other) => { other.disabled = true; });
        sendRulesChoiceAnswer({
          type: "resolve_rules_choice",
          choiceId: choice.id,
          option: button.dataset.rulesRevealIndex,
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
        sendRulesChoiceAnswer({
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
    options.classList.add("has-destination-card", "is-destination-screen");
    panel.classList.add("cards-screen", "destination-screen");
    closeButton.classList.add("hidden");
    options.innerHTML = `
      <div class="rules-choice-destination-card" draggable="true" tabindex="0" role="img" aria-label="${esc(cardName(choice.cardId))}" title="${esc(cardName(choice.cardId))}">
        <img draggable="false" src="${esc(cardImage(choice.cardId))}" alt="${esc(cardName(choice.cardId))}">
      </div>
      <button type="button" class="rules-choice-destination" data-rules-destination="interzone">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 7 7-7 11-7-11 7-7Z"/><path d="M8.5 10h7M10 14h4"/></svg>
        <strong>${esc(t("interzone"))}</strong>
        <span>${esc(t("rulesConfrontationInterzoneHint"))}</span>
      </button>
      ${(choice.options || []).includes("karmapult") ? `<button type="button" class="rules-choice-destination" data-rules-destination="karmapult">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h16M7 20l2-9h6l2 9M12 11V4M9 6l3-2 3 2"/></svg>
        <strong>${esc(t("rulesKarmapultDestination"))}</strong>
        <span>${esc(t("rulesKarmapultDestinationHint"))}</span>
      </button>` : ""}
      ${(choice.options || []).includes("deck_bottom") ? `<button type="button" class="rules-choice-destination" data-rules-destination="deck_bottom">
        <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="3" width="11" height="15" rx="2"/><path d="M8 21h11a2 2 0 0 0 2-2V7M10 13l3 3 3-3M13 8v8"/></svg>
        <img class="rules-destination-back" src="card-back.webp?v=20260905-1" alt="">
        <strong>${esc(t("rulesDeckBottom"))}</strong>
        <span>${esc(t("rulesConfrontationDeckHint"))}</span>
      </button>` : ""}`;
    const resolveDestination = (button) => {
      if (!button || button.disabled) return;
      $$('[data-rules-destination]').forEach((candidate) => { candidate.disabled = true; });
      sendRulesChoiceAnswer({
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
    // the nearest destination lights up as the card gets close, wherever it is released around it
    const nearestDestination = (event) => {
      const direct = event.target?.closest?.("[data-rules-destination]");
      if (direct) return direct;
      let best = null;
      let bestDistance = 130;
      $$('[data-rules-destination]').forEach((button) => {
        const rect = button.getBoundingClientRect();
        const distance = Math.hypot(Math.max(rect.left - event.clientX, 0, event.clientX - rect.right), Math.max(rect.top - event.clientY, 0, event.clientY - rect.bottom));
        if (distance < bestDistance) { bestDistance = distance; best = button; }
      });
      return best;
    };
    options.addEventListener("dragover", (event) => {
      event.preventDefault();
      if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
      const near = nearestDestination(event);
      $$('[data-rules-destination]').forEach((button) => button.classList.toggle("is-drop-target", button === near));
    });
    options.addEventListener("drop", (event) => {
      event.preventDefault();
      resolveDestination(nearestDestination(event));
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
    // cards-only screen: the Interzone cards in the middle, the Deck on the right; drag one onto the Deck (or click it)
    panel.classList.add("cards-screen", "replace-screen");
    closeButton.classList.add("hidden");
    options.innerHTML = `
      <div class="rules-replace-row">
        <div class="rules-replace-cards">${candidates.map((item) => `
          <div class="rules-reorder-card rules-choice-card" data-rules-replace-item="${esc(item.id)}" title="${esc(cardName(item.cardId))}">
            <img src="${esc(cardImage(item.cardId))}" alt="${esc(cardName(item.cardId))}">
          </div>`).join("")}</div>
        <div class="rules-replace-deck" data-rules-replace-deck>
          <img src="card-back.webp?v=20260905-1" alt="">
          <strong>${esc(t("rulesDeckBottom"))}</strong>
        </div>
      </div>`;
    const deck = options.querySelector("[data-rules-replace-deck]");
    const chooseItem = (itemId) => {
      if (!itemId || deck.dataset.sent) return;
      deck.dataset.sent = "1";
      sendRulesChoiceAnswer({ type: "resolve_rules_choice", choiceId: choice.id, itemId });
    };
    options.querySelectorAll("[data-rules-replace-item]").forEach((card) => {
      card.addEventListener("click", () => chooseItem(card.dataset.rulesReplaceItem));
      card.addEventListener("pointerdown", (event) => {
        if (event.button !== 0 || event.isPrimary === false) return;
        event.preventDefault();
        const startX = event.clientX;
        const startY = event.clientY;
        let moved = false;
        const near = (e) => {
          const rect = deck.getBoundingClientRect();
          return Math.hypot(Math.max(rect.left - e.clientX, 0, e.clientX - rect.right), Math.max(rect.top - e.clientY, 0, e.clientY - rect.bottom)) < 120;
        };
        const move = (e) => {
          if (!moved && Math.hypot(e.clientX - startX, e.clientY - startY) > 5) {
            moved = true;
            card.classList.add("is-dragging");
          }
          if (moved) {
            card.style.transform = `translate(${e.clientX - startX}px, ${e.clientY - startY}px)`;
            deck.classList.toggle("is-over", near(e));
          }
        };
        const up = (e) => {
          deck.classList.remove("is-over");
          card.classList.remove("is-dragging");
          card.style.transform = "";
          if (e.type === "pointerup" && (!moved || near(e))) chooseItem(card.dataset.rulesReplaceItem);
        };
        startCardPointerDrag(event, card, move, up);
      });
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
        sendRulesChoiceAnswer({
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
  const handWill = !searching && choice.destination === "support_manifestation";
  const handManifestation = !searching && (choice.destination || choice.drawByBasePower || choice.destroyTargetItemId);
  const requiredTypes = Array.isArray(choice.requireTypes) && choice.requireTypes.length ? choice.requireTypes : null;
  const cards = (searching
    ? choice.candidateCardIds
    : latestState?.players?.[myPlayerId]?.zones?.hand?.cards || [])
    // only the card types the effect accepts are offered (e.g. Wills only)
    .filter((cardId) => !requiredTypes || requiredTypes.includes(cardsById.get(cardId)?.type));
  const destinationKeys = {
    bullyboo_reveal: ["rulesChoiceRevealWillHeading", "rulesChoiceRevealWillText"],
    attach_to_source: ["rulesChoicePlaceWillsHeading", "rulesChoicePlaceWillsText"],
    amphora_offer: ["rulesChoiceAmphoraHeading", "rulesChoiceAmphoraText"],
    obelisk_gift: ["rulesChoiceGiftHeading", "rulesChoiceGiftText"],
    obelisk_reply: ["rulesChoiceGiftHeading", "rulesChoiceGiftText"],
    persuasion_place: ["rulesChoicePersuasionHeading", "rulesChoicePersuasionText"],
    deck_bottom_from_hand: ["rulesChoiceBottomHeading", "rulesChoiceBottomText"],
    auction_bid: ["rulesChoiceAuctionBidHeading", "rulesChoiceAuctionBidText"],
    auction_answer: ["rulesChoiceAuctionAnswerHeading", "rulesChoiceAuctionAnswerText"],
    stalemate_for_support: ["rulesChoiceChabakHeading", "rulesChoiceChabakText"],
    limbo_exile_add_power: ["rulesChoiceLimboExileHeading", "rulesChoiceLimboExileText"],
  }[searching && choice.destination !== "limbo_exile_add_power" ? "" : choice.destination];
  if (destinationKeys) {
    $("#rulesChoiceHeading").textContent = t(destinationKeys[0]);
    $("#rulesChoiceText").textContent = rulesText(destinationKeys[1], { card: cardName(choice.sourceCardId), count: choice.count, points: choice.requiredPoints });
  } else $("#rulesChoiceHeading").textContent = t(
    searching ? "rulesChoiceSearchHeading" : handWill ? "rulesChoiceHandWillHeading" : handManifestation ? "rulesChoiceHandHeading" : "rulesChoiceDiscardHeading",
  );
  if (!destinationKeys) $("#rulesChoiceText").textContent = rulesText(
    searching
      ? "rulesChoiceSearchText"
      : handWill
        ? "rulesChoiceHandWillText"
      : handManifestation
        ? "rulesChoiceHandText"
        : Number(choice.drawAfter || 0) > 0 ? "rulesChoiceDiscardThenDrawText" : "rulesChoiceDiscardText",
    {
      card: cardName(choice.sourceCardId),
      count: choice.count,
      draw: Number(choice.drawAfter || 0),
    },
  );
  if (!searching) {
    // the cards stay in the hand: drag one onto the asking card instead of picking from a window
    panel.classList.add("cards-screen", "hand-drop");
    closeButton.classList.add("hidden");
    const limit = Number(choice.count || 1);
    options.classList.add("has-hand-selection");
    const selected = rulesHandDropSelected(choice);
    const picked = selected.length;
    const attaching = choice.destination === "attach_to_source";
    const hand = latestState?.players?.[myPlayerId]?.zones?.hand?.cards || [];
    const previews = selected.length ? `<div class="rules-hand-selection">${selected.map((index) => `
      <button type="button" class="rules-choice-card" data-hand-unpick="${index}" aria-label="${esc(rulesText("rulesUnselectCard", { card: cardName(hand[index]) }))}">
        <img src="${esc(cardImage(hand[index]))}" alt="${esc(cardName(hand[index]))}" draggable="false">
      </button>`).join("")}</div>` : "";
    // an exact count sends itself once complete: until then Confirm shows the progress, disabled
    options.innerHTML = previews + (limit > 1 || choice.upTo
      ? `<button type="button" class="primary" id="rulesDiscardConfirm"${!choice.upTo && picked < limit ? " disabled" : ""}>${esc(attaching ? picked ? rulesText("rulesConfirmPlaceWills", { count: picked }) : t("rulesPlaceNoWills") : choice.upTo && !picked ? t("passPhase") : t("confirm"))}${!choice.upTo ? ` (${picked}/${limit})` : ""}</button>`
      : "");
    options.querySelectorAll("[data-hand-unpick]").forEach((button) => {
      button.onclick = () => pickHandDropCard(Number(button.dataset.handUnpick), true);
    });
    if ($("#rulesDiscardConfirm")) $("#rulesDiscardConfirm").onclick = (event) => {
      event.currentTarget.disabled = true;
      sendHandDropSelection(choice);
    };
    panel.classList.remove("hidden");
    return;
  }
  options.classList.add("has-card-picker");
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
      sendRulesChoiceAnswer({
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
      sendRulesChoiceAnswer({ type: "resolve_rules_choice", choiceId: choice.id, cardIds: [cardId] });
      button.disabled = true;
    };
  });
  panel.classList.remove("hidden");
}
