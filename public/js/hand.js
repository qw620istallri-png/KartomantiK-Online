// Hand tray, playability checks and card placement requests.
// Loaded before app.js: declarations only, nothing runs at load time.

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
  const myHandZone = meId ? latestState?.players?.[meId]?.zones?.hand : null;
  const myHandCount = myHandZone
    ? (myHandZone.count !== undefined ? myHandZone.count : (myHandZone.cards || []).length)
    : 0;
  $("#handResizeHandle").classList.toggle("hidden", collapsed || myHandCount === 0);
  // the toolbar itself (and the hide/show toggle inside it) always stays put;
  // only its OTHER tool buttons collapse away with the tray
  // beta (assisted rules) automates the hand: the options shrink to a single sort button
  const handBeta = Boolean(latestState?.rulesEngine?.enabled);
  $("#handToolbar").classList.toggle("hidden", !meId || !handToolsOpen || handBeta);
  $("#handToolsToggleBtn").classList.toggle("hidden", !meId || handBeta);
  $("#handSortQuickBtn").classList.toggle("hidden", !meId || !handBeta);
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
  const manual = !latestState?.rulesEngine?.enabled;
  strip.innerHTML = [...pool].map(([temperament, amount]) => manual
    ? `<button type="button" class="hand-essence-chip" data-remove-essence="${esc(temperament)}" title="${esc(t("essenceRemoveOne"))}: ${esc(t(`temperament${temperament[0].toUpperCase()}${temperament.slice(1)}`))}"><img src="${esc(temperamentSymbol(temperament))}" alt=""><b>${amount}</b></button>`
    : `<span class="hand-essence-chip" title="${esc(t(`temperament${temperament[0].toUpperCase()}${temperament.slice(1)}`))}"><img src="${esc(temperamentSymbol(temperament))}" alt=""><b>${amount}</b></span>`
  ).join("");
  strip.setAttribute("aria-label", t("essence"));
  bindEssenceQuickControls(strip);
}

// Manifestations with an ability usable from the Hand (e.g. Ranba) stay actionable
// Why a hand card cannot be played right now, in the player's words ("" when
// it can, or when the question does not apply). Mirrors handCardIsPlayable.
function handCardUnplayableReason(cardId) {
  const rules = latestState?.rulesEngine;
  const card = cardsById.get(cardId);
  if (!rules?.enabled || !card || isObserver || handCardIsPlayable(cardId) || handCardHasHandAction(cardId)) return "";
  if (rules.pendingChoice) return t("unplayablePending");
  if (rulesImmediateEffectPendingClient()) return t("rulesImmediateResolving");
  if (handDrawLocked()) return t("unplayableDrawing");
  if (rules_pregame_active_client() || rules_recovery_mulligan_active_client()) return t("unplayablePregame");
  // a Trap only goes face down while the First Manifestations are being chosen
  if (isTrapCardClient(cardId)) return rulesFirstManifestationActive() ? t("unplayableTrapUsed") : t("unplayableTrapWindow");
  if (rulesFirstManifestationActive()) {
    if (rulesFirstManifestationSlotTakenClient()) return t("unplayableFirstDone");
    if (card.type !== "manifestation" && !card.placeholder) return t("unplayableFirstType");
    return t("unplayableFirstForbidden");
  }
  if (rules.priorityPlayerId !== myPlayerId) {
    return rulesText("unplayablePriority", { player: rulesPlayerName(rules.priorityPlayerId) || "—" });
  }
  if (rulesCardPlayRestrictedClient(cardId)) return t("unplayableRestricted");
  const phaseId = currentPhaseUi().phase?.id;
  const phaseNames = (ids) => ids
    .map((id) => ADVANCED_PHASES.find((phase) => phase.id === id))
    .filter(Boolean).map((phase) => t(phase.label)).join(", ");
  const wrongPhase = (ids) => rulesText("unplayablePhase", { phases: phaseNames(ids) });
  const payable = () => {
    if (!rulesCanAffordCard(cardId)) return t("unplayableCost");
    const ability = (playedAbilitiesByCard.get(cardId) || [])[0];
    const draft = ability ? buildRulesActionDraft({ cardId, zone: "hand" }, ability) : null;
    if (draft && !rulesAdditionalCostAvailableClient(draft)) return t("unplayableExtraCost");
    if (!rulesPlayedAbilityTargetsAvailableClient(cardId)) return t("unplayableNoTarget");
    return "";
  };
  const playType = rulesPlayType(card);
  if (playType === "ephemeral_will") {
    const phases = rulesEphemeralPhasesClient(card);
    if (!phases.includes(phaseId)) return wrongPhase(phases);
    const ability = (playedAbilitiesByCard.get(cardId) || [])[0];
    if (ability?.condition === "controller_lost_confrontation" && rules.confrontationResult?.loserId !== myPlayerId) {
      return t("unplayableLostConfrontation");
    }
    return payable() || t("rulesBoardCardNotPlayable");
  }
  if (playType === "persistent_will") {
    const phases = ["end_actions"];
    if (rulesBeforeRevelationPlayClient(card)) phases.unshift("confrontation_before_revelation");
    if (rulesPersistentWillsAsEphemeralClient()) phases.unshift("confrontation_reaction", "resolution_effects");
    if (!phases.includes(phaseId)) return wrongPhase(phases);
    if ((rules.actionStack || []).length && !rulesPersistentWillsAsEphemeralClient()) return t("unplayableStack");
    return payable() || t("rulesBoardCardNotPlayable");
  }
  if (card.type !== "manifestation") return t("rulesBoardCardNotPlayable");
  if (rulesEndPhaseInterzonePlayClient(card)) {
    if (phaseId === "end_actions") {
      if ((rules.actionStack || []).length) return t("unplayableStack");
      if (!rulesInterzoneHasRoomClient()) return t("unplayableInterzoneFull");
    } else if (phaseId !== "confrontation_reaction") {
      return wrongPhase(["confrontation_reaction", "end_actions"]);
    }
  }
  if (rulesSupportEntryLockedClient() || (rules.supportEntryLockedPlayerIds || []).includes(myPlayerId)) return t("unplayableSupportLocked");
  if (!rulesSupportFromHandAvailableClient(cardId)) return t("unplayableNoSupport");
  if (phaseId !== "confrontation_reaction") return wrongPhase(["confrontation_reaction"]);
  return t("rulesBoardCardNotPlayable");
}
// a refused hand card says why, and shakes
function refuseHandCard(cardId, handIndex = null) {
  showToast(handCardUnplayableReason(cardId) || t("rulesBoardCardNotPlayable"), true);
  const selector = handIndex === null ? `[data-hand-card="${CSS.escape(cardId)}"]` : `[data-hand-index="${handIndex}"]`;
  const card = $(`#myHandTray ${selector}`) || $(selector);
  if (!card || rulesVfxReducedMotion()) return;
  card.classList.remove("ko-refuse");
  void card.offsetWidth;
  card.classList.add("ko-refuse");
  window.setTimeout(() => card.classList.remove("ko-refuse"), 500);
}
function handCardHasHandAction(cardId) {
  const rules = latestState?.rulesEngine;
  const card = cardsById.get(cardId);
  if (!rules?.enabled || !card || isObserver || rules.pendingChoice || rulesImmediateEffectPendingClient() || handDrawLocked() || card.type !== "manifestation") return false;
  // while the first Manifestation (or a mulligan) is being chosen, hand effects are not usable
  if (rules_pregame_active_client() || rules_recovery_mulligan_active_client() || rulesFirstManifestationActive()) return false;
  if (rules.priorityPlayerId !== myPlayerId) return false;
  const phaseId = currentPhaseUi().phase?.id;
  // the server knows the conditions (Ranba: the last opponent Support's power)
  const usable = rules.usableHandAbilityCardIds;
  if (Array.isArray(usable) && !usable.includes(cardId)) return false;
  return (activatedAbilitiesByCard.get(cardId) || []).some((ability) => {
    if (!(ability.sourceZones || []).includes("hand")) return false;
    if (Array.isArray(ability.phaseIds) && !ability.phaseIds.includes(phaseId)) return false;
    // highlight only when a required target exists (Glabron needs a Manifestation in your Interzone)
    const draft = buildRulesActionDraft({ cardId, zone: "hand" }, ability);
    if (!draft) return true;
    if (!rulesAdditionalCostAvailableClient(draft)) return false;
    if (Array.isArray(draft.targetRules?.groups)) {
      return draft.targetRules.groups.every((_group, index) => (
        draft.structuredTargets.some((target) => target.targetGroupIndex === index)
      ));
    }
    return Number(draft.targetRules?.min || 0) <= draft.structuredTargets.length;
  });
}

// a Will whose played ability needs a target (Annihilating Nectar...) is not
// playable while no legal target exists
function rulesPlayedAbilityTargetsAvailableClient(cardId, source = null) {
  const ability = (playedAbilitiesByCard.get(cardId) || [])[0];
  const draft = ability ? buildRulesActionDraft(source || { cardId, zone: "hand" }, ability) : null;
  if (!draft) return true;
  if (Array.isArray(draft.targetRules?.groups)) {
    return draft.targetRules.groups.every((_group, index) => (
      draft.structuredTargets.some((target) => target.targetGroupIndex === index)
    ));
  }
  return Number(draft.targetRules?.min || 0) <= draft.structuredTargets.length;
}

function handCardIsPlayable(cardId, source = null) {
  const canAfford = () => source ? rulesDraftCanBePaid(buildRulesActionDraft(source)) : rulesCanAffordCard(cardId);
  const rules = latestState?.rulesEngine;
  const card = cardsById.get(cardId);
  if (!rules?.enabled || !card || isObserver || rules.pendingChoice || rulesImmediateEffectPendingClient() || handDrawLocked()) return false;
  if (rules_pregame_active_client() || rules_recovery_mulligan_active_client()) return false;
  if (isTrapCardClient(cardId)) return trapPlayableClient(cardId);
  if (rulesFirstManifestationActive()) {
    if (trapPlayableClient(cardId)) return true;
    return ((card.type === "manifestation" && rulesPlayType(card) === "manifestation") || card.placeholder)
      && !String(card.effect || "").includes("Cannot be played as First Manifestation")
      && !rulesFirstManifestationSlotTakenClient();
  }
  if (rules.priorityPlayerId !== myPlayerId) return false;
  if (rulesCardPlayRestrictedClient(cardId)) return false;
  const stackHasActions = (rules.actionStack || []).length > 0;
  const phaseId = currentPhaseUi().phase?.id;
  const playType = rulesPlayType(card);
  const responsePhase = playType === "ephemeral_will"
    ? rulesEphemeralPhasesClient(card).includes(phaseId)
    : ["confrontation_reaction", "resolution_effects", "end_actions"].includes(phaseId);
  if (playType === "ephemeral_will") {
    if (!responsePhase || !canAfford()) return false;
    const ability = (playedAbilitiesByCard.get(cardId) || [])[0];
    if (
      ability?.condition === "controller_lost_confrontation"
      && rules.confrontationResult?.loserId !== myPlayerId
    ) return false;
    const draft = ability ? buildRulesActionDraft(source || { cardId, zone: "hand" }, ability) : null;
    if (!draft) return true;
    if (!rulesAdditionalCostAvailableClient(draft)) return false;
    return rulesPlayedAbilityTargetsAvailableClient(cardId, source);
  }
  if (playType === "persistent_will") {
    if (
      ["confrontation_reaction", "resolution_effects"].includes(phaseId)
      && rulesPersistentWillsAsEphemeralClient()
    ) return canAfford() && rulesPlayedAbilityTargetsAvailableClient(cardId, source);
    const timingOk = phaseId === "end_actions"
      || (phaseId === "confrontation_before_revelation" && rulesBeforeRevelationPlayClient(card));
    return timingOk && (!stackHasActions || rulesPersistentWillsAsEphemeralClient()) && canAfford()
      && rulesPlayedAbilityTargetsAvailableClient(cardId, source);
  }
  const supportLocked = (rules.supportEntryLockedPlayerIds || []).includes(myPlayerId);
  if (card.type === "manifestation" && rulesEndPhaseInterzonePlayClient(card)) {
    if (phaseId === "end_actions") return !stackHasActions && rulesInterzoneHasRoomClient();
    if (phaseId !== "confrontation_reaction" || supportLocked) return false;
  }
  // Pin Down: no Manifestation may enter the Confrontation Zone this turn
  if (card.type === "manifestation" && rulesSupportEntryLockedClient()) return false;
  if (card.type === "manifestation" && rulesTopOfStackIsWillClient(card)) return !supportLocked;
  return card.type === "manifestation"
    && !supportLocked
    && phaseId === "confrontation_reaction"
    && rulesSupportFromHandAvailableClient(cardId);
}

function rulesSupportEntryLockedClient() {
  return Boolean(latestState?.rulesEngine?.supportEntryLocked);
}

function rulesTopOfStackIsWillClient(card) {
  if (!/As long as the top card on the Stack is a Will, you may play .{0,40} in Support from hand/.test(String(card?.effect || ""))) return false;
  const stack = latestState?.rulesEngine?.actionStack || [];
  const top = stack[stack.length - 1];
  return Boolean(top)
    && top.kind === "play_card"
    && ["ephemeral_will", "persistent_will"].includes(cardsById.get(top.source?.cardId)?.type);
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
  if (rulesTopOfStackIsWillClient(card)) return true;
  if ((latestState?.rulesEngine?.conditionalSupportHandCardIds?.[myPlayerId] || []).includes(cardId)) return true;
  if (/5 or more Wills in your Limbo, .*gains Support/i.test(effect)) {
    const limbo = latestState?.players?.[myPlayerId]?.zones?.graveyard?.cards || [];
    if (limbo.filter((c) => ["ephemeral_will", "persistent_will"].includes(cardsById.get(c.cardId || c.id || c)?.type)).length >= 5) return true;
  }
  if ((latestState?.rulesEngine?.playPermissions || []).some((permission) => (
    permission.playerId === myPlayerId
    && permission.cardId === cardId
    && permission.fromZone === "hand"
    && permission.asSupport
    && Number(permission.turn || 0)
      === Number(latestState?.phaseTracker?.turn || 0)
  ))) return true;
  if (effect.includes("an opponent controls at least one Will in the stack that targets a manifestation in the Confrontation Zone")) {
    return (latestState?.rulesEngine?.actionStack || []).some((entry) => (
      entry.controllerId !== myPlayerId
      && entry.kind === "play_card"
      && ["ephemeral_will", "persistent_will"].includes(cardsById.get(entry.source?.cardId)?.type)
      && (entry.targets || []).some((target) => {
        const item = (latestState?.battlefield || []).find((candidate) => candidate.id === target.itemId);
        return target.kind === "card"
          && item?.fieldZone === "confrontation"
          && cardsById.get(item.cardId)?.type === "manifestation";
      })
    ));
  }
  if (!effect.includes("an opponent has put a manifestation into Support from their Interzone")) return false;
  const turn = Number(latestState?.phaseTracker?.turn || 0);
  return (latestState?.rulesEngine?.supportEntries || []).some((entry) => (
    Number(entry.turn || 0) === turn
    && entry.controllerId !== myPlayerId
    && entry.fromZone === "interzone"
  ));
}

function rulesBattlefieldSupportAvailableClient(item) {
  if (rulesSupportEntryLockedClient() || item?.effectsInactive || item?.effectsDisabled) return false;
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

// Hand sort: cards matching the chosen category come first (display only)
// "Sort hand": one button. 1st click sorts in the given order (First Manifestation,
// Ephemeral Wills, Support only, Persistent Wills); each further click rotates which
// group comes first, then the last click goes back to the hand's own order.
const HAND_SORT_CYCLE = ["none", "all", "ephemeral", "support", "persistent"];

const HAND_SORT_ORDERS = {
  all: ["first", "ephemeral", "support", "persistent"],
  ephemeral: ["ephemeral", "support", "persistent", "first"],
  support: ["support", "persistent", "first", "ephemeral"],
  persistent: ["persistent", "first", "ephemeral", "support"],
};

let handSortMode = "none";

function handSortRank(mode) {
  const supportOnly = (card) => card?.type === "manifestation" && (
    /^Support(?: from hand)?[.;]/.test(String(card.effect || ""))
    || String(card.effect || "").includes("Cannot be played as First Manifestation")
  );
  const group = (card) => {
    if (card?.type === "ephemeral_will") return "ephemeral";
    if (card?.type === "persistent_will") return "persistent";
    if (supportOnly(card)) return "support";
    if (card?.type === "manifestation") return "first";
    return "other";
  };
  const order = HAND_SORT_ORDERS[mode];
  return (cardId) => {
    if (!order) return 0;
    const position = order.indexOf(group(cardsById.get(cardId)));
    return position === -1 ? order.length : position;
  };
}

function updateHandSortButton() {
  const button = $("#handSortBtn");
  if (!button) return;
  const labels = {
    all: "handSortFirst", ephemeral: "handSortEphemeral", support: "handSortSupport", persistent: "handSortPersistent",
  };
  button.textContent = handSortMode === "none" ? t("handSortBtn") : `${t("handSortBtn")} · ${t(labels[handSortMode] || "handSortFirst")}`;
  button.title = t("handSortHint");
  button.classList.toggle("active", handSortMode !== "none");
  const quick = $("#handSortQuickBtn");
  if (quick) {
    const label = handSortMode === "none" ? t("handSortBtn") : `${t("handSortBtn")} · ${t(labels[handSortMode] || "handSortFirst")}`;
    quick.title = label;
    quick.setAttribute("aria-label", label);
    quick.classList.toggle("active", handSortMode !== "none");
  }
}

// extra cards (suspended, Limbo, Grimoire) follow the same curve as the hand
function handCurveStyle(position, total) {
  const center = position - (total - 1) / 2;
  const rotate = Math.max(-16, Math.min(16, center * 3.25));
  const arc = Math.abs(center) * Math.abs(center) * 1.35;
  return `--hand-rotate:${rotate}deg;--hand-arc:${arc}px;`;
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
  const ghostCards = rulesGhostHandCards();
  const currentIds = new Set([...cards, ...suspendedCards.map((entry) => entry.cardId)]);
  if (cards.length === 0 && suspendedCards.length === 0 && ghostCards.length === 0) {
    tray.innerHTML = "";
    previousHandCardIds = currentIds;
    return;
  }
  const myRevealed = new Set(latestState.players[meId].zones.hand.revealedIndices || []);
  const sortRank = handSortRank(handSortMode);
  const displayOrder = cards
    .map((cid, index) => ({ cid, index }))
    .sort((first, second) => sortRank(first.cid) - sortRank(second.cid) || first.index - second.index);
  tray.innerHTML = displayOrder
    .map(({ cid, index }, position) => {
      const isNew = !previousHandCardIds.has(cid);
      const wasRevealed = myRevealed.has(index);
      const rarity = rarityForCard(meId, cid);
      const center = position - (cards.length + suspendedCards.length + ghostCards.length - 1) / 2;
      const rotate = Math.max(-16, Math.min(16, center * 3.25));
      const arc = Math.abs(center) * Math.abs(center) * 1.35;
      const playable = handCardIsPlayable(cid) || handCardHasHandAction(cid);
      const reason = playable ? "" : handCardUnplayableReason(cid);
      const label = reason ? `${cardName(cid)} — ${reason}` : cardName(cid);
      return `<div class="hand-card ${isNew ? "ko-pop-in " : ""}${playable ? "is-playable " : ""}${rarityClassAttr(rarity)}" data-hand-card="${esc(cid)}" data-hand-index="${index}"${reason ? ` data-unplayable="${esc(reason)}"` : ""} role="button" tabindex="0" aria-label="${esc(label)}" title="${esc(label)}" style="--hand-rotate:${rotate}deg;--hand-arc:${arc}px;--hand-z:${position};${rarityCosmosStyle(cid)}">
      ${raritySurfaceMarkup(rarity, `<img src="${esc(cardImage(cid))}" alt="${esc(cardName(cid))}">`)}
      ${reason ? `<span class="hand-card-reason">${esc(reason)}</span>` : ""}
      ${automationCoverageBadgeHtml(cid)}
      ${wasRevealed ? `<span class="hand-card-revealed-icon" title="${esc(t("revealHeader"))}">👁</span>` : ""}
    </div>`;
    })
    .join("") + suspendedCards.map((entry, index) => {
      const cardId = entry.cardId;
      const playable = handCardIsPlayable(cardId, { cardId, zone: "suspended", suspensionId: entry.id });
      const curve = handCurveStyle(cards.length + index, cards.length + suspendedCards.length + ghostCards.length);
      return `<div class="hand-card${playable ? " is-playable" : ""}" data-suspended-card="${esc(cardId)}" data-suspension-id="${esc(entry.id)}" role="button" tabindex="0" aria-label="${esc(`${cardName(cardId)} · ${t("rulesSuspended")}`)}" title="${esc(`${cardName(cardId)} · ${t("rulesSuspended")}`)}" style="${curve}--hand-z:${cards.length + index};${rarityCosmosStyle(cardId)}">
        ${raritySurfaceMarkup(null, `<img src="${esc(cardImage(cardId))}" alt="${esc(cardName(cardId))}">`)}
        ${automationCoverageBadgeHtml(cardId)}
        <span class="hand-card-revealed-icon" title="${esc(t("rulesSuspended"))}">S</span>
      </div>`;
    }).join("") + ghostCards.map((ghost, index) => `<div class="hand-card ${ghost.playable === false ? "" : "is-playable "}is-ghost" data-ghost-card="${esc(ghost.cardId)}" data-ghost-zone="${esc(ghost.zone)}" data-ghost-host="${esc(ghost.itemId || "")}" data-ghost-key="${esc(String(ghost.selectionKey ?? ""))}" data-ghost-playable="${ghost.playable === false ? "false" : "true"}"${ghost.permission ? ` data-ghost-permission="true"` : ""} role="button" tabindex="0" aria-label="${esc(`${cardName(ghost.cardId)} · ${ghost.label}`)}" title="${esc(`${cardName(ghost.cardId)} · ${ghost.label}`)}" style="${handCurveStyle(cards.length + suspendedCards.length + index, cards.length + suspendedCards.length + ghostCards.length)}--hand-z:${cards.length + suspendedCards.length + index};${rarityCosmosStyle(ghost.cardId)}">
        ${raritySurfaceMarkup(null, `<img src="${esc(cardImage(ghost.cardId))}" alt="${esc(cardName(ghost.cardId))}">`)}
        <span class="hand-ghost-label">${esc(ghost.label)}</span>
      </div>`).join("");
  previousHandCardIds = currentIds;
  $$("[data-hand-card]").forEach((el) => {
    const cardId = el.dataset.handCard;
    el.onclick = () => showInspect(cardId);
    bindCardDragSource(el, { kind: "card", cardId, handIndex: Number(el.dataset.handIndex), cardOwnerId: meId, fromOwnerId: meId, fromZone: "hand" });
    bindRarityPointer(el, false);
    wireCardHoverZoom(el, "hand-card-hover-clone");
    el.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      const items = [{ keepInBeta: true, label: t("inspect"), onSelect: () => showInspect(cardId) }];
      const rulesItem = rulesActionContextItem({
        cardId, zone: "hand",
        handIndex: Number(el.dataset.handIndex),
      });
      if (rulesItem) items.push({ ...rulesItem, keepInBeta: !rulesItem.debug });
      if (
        latestState?.rulesEngine?.enabled
        && cardAutomationCoverage(cardId).status === "manual"
      ) {
        items.push({
          keepInBeta: true,
          label: t("rulesPlayManually"),
          onSelect: () => playManuallyFromHand(cardId),
        });
      }
      items.push(
        copyCardMenuItem(cardId, meId, "hand"),
        { separator: true },
        { label: t("playFaceUp"), onSelect: () => playFromHand(cardId, true) },
        { label: t("playFaceDown"), onSelect: () => playFromHand(cardId, false) },
        ...(manualStackAvailable() ? [{ label: t("ubPlayToStack"), onSelect: () => playFromHandToManualStack(cardId) }] : []),
        { separator: true },
        { label: t("handDiscard"), onSelect: () => send({ type: "move_card", fromZone: "hand", toZone: "graveyard", cardId }) },
        { label: t("show"), onSelect: () => send({ type: "reveal", zone: "hand", cardId }) },
        { label: `${t("moveTo")} ${t("exile")}`, onSelect: () => send({ type: "move_card", fromZone: "hand", toZone: "exile", cardId }) },
        { label: t("moveToDeckTop"), onSelect: () => send({ type: "move_card", fromZone: "hand", toZone: "deck", cardId, position: "top" }) },
        { label: t("moveToDeckBottom"), onSelect: () => send({ type: "move_card", fromZone: "hand", toZone: "deck", cardId, position: "bottom" }) },
      );
      showContextMenu(event.clientX, event.clientY, betaMenuItems(items));
    });
  });
  $$("[data-ghost-card]").forEach((el) => {
    const cardId = el.dataset.ghostCard;
    const zone = el.dataset.ghostZone;
    const itemId = el.dataset.ghostHost || null;
    if (el.dataset.ghostPlayable === "false") {
      el.onclick = () => showInspect(cardId);
      wireCardHoverZoom(el, "hand-card-hover-clone");
      return;
    }
    if (zone === "payment") {
      const candidate = pendingRulesBoardFlow?.draft?.manifestations?.find((entry) => String(entry.selectionKey) === el.dataset.ghostKey);
      el.onclick = () => showInspect(cardId);
      bindCardDragSource(el, { kind: "card", cardId, fromOwnerId: meId, fromZone: "payment", paymentKey: candidate?.selectionKey });
      el.classList.toggle("is-choice-selected", Boolean(candidate && pendingRulesBoardFlow.selectedPaymentIndexes.has(candidate.selectionKey)));
      wireCardHoverZoom(el, "hand-card-hover-clone");
      return;
    }
    el.onclick = () => showInspect(cardId);
    bindCardDragSource(el, { kind: "card", cardId, handIndex: null, cardOwnerId: meId, fromOwnerId: meId, fromZone: zone, ghostHostId: itemId });
    wireCardHoverZoom(el, "hand-card-hover-clone");
    el.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      showContextMenu(event.clientX, event.clientY, [{ label: t("inspect"), onSelect: () => showInspect(cardId) }]);
    });
  });
  $$("[data-suspended-card]").forEach((el) => {
    const cardId = el.dataset.suspendedCard;
    el.onclick = () => showInspect(cardId);
    bindCardDragSource(el, { kind: "card", cardId, fromOwnerId: meId, fromZone: "suspended", suspensionId: el.dataset.suspensionId });
    wireCardHoverZoom(el, "hand-card-hover-clone");
    el.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      const items = [{ label: t("inspect"), onSelect: () => showInspect(cardId) }];
      const rulesItem = rulesActionContextItem({ cardId, zone: "suspended", suspensionId: el.dataset.suspensionId });
      if (rulesItem) items.push(rulesItem);
      showContextMenu(event.clientX, event.clientY, items);
    });
  });
  $$(`[data-hand-card], [data-ghost-card], [data-suspended-card]`).forEach((el) => {
    el.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        el.click();
        return;
      }
      if (event.key === "ContextMenu" || (event.shiftKey && event.key === "F10")) {
        event.preventDefault();
        const rect = el.getBoundingClientRect();
        el.dispatchEvent(new MouseEvent("contextmenu", {
          bubbles: true, clientX: rect.left + rect.width / 2, clientY: rect.top + rect.height / 2,
        }));
      }
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
  const cycleHandSort = () => {
    handSortMode = HAND_SORT_CYCLE[(HAND_SORT_CYCLE.indexOf(handSortMode) + 1) % HAND_SORT_CYCLE.length];
    try { localStorage.setItem("ko_hand_sort", handSortMode); } catch (_error) { /* storage unavailable */ }
    updateHandSortButton();
    renderHandTray();
  };
  $("#handSortBtn").onclick = cycleHandSort;
  $("#handSortQuickBtn").onclick = cycleHandSort;
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
  if (source?.zone === "deck" && latestState?.rulesEngine?.uncoveredTops?.[myPlayerId] === payload.cardId) {
    return rulesSupportFromHandAvailableClient(payload.cardId);
  }
  return (latestState?.rulesEngine?.playPermissions || []).some((permission) => (
    permission.playerId === myPlayerId
    && permission.cardId === payload.cardId
    && permission.fromZone === source?.zone
    && permission.asSupport
  ));
}

// A card dropped with a finger is played after a short grace delay, so a slip
// can be taken back before anything reaches the server (and before the
// opponent is given priority). The First Manifestation, still movable until
// validated, goes at once.
const PLACEMENT_GRACE_MS = 2500;
let pendingPlacementGrace = null;
function sendCardPlacement(payload, source, triggerTargets = []) {
  const commit = () => sendCardPlacementNow(payload, source, triggerTargets);
  if (lastPointerType !== "touch" || !latestState?.rulesEngine?.enabled || rulesFirstManifestationActive()) {
    commit();
    return;
  }
  settlePlacementGrace(true);
  const bar = document.createElement("div");
  bar.className = "placement-grace";
  bar.setAttribute("role", "status");
  bar.innerHTML = `<img src="${esc(cardImage(payload.cardId))}" alt=""><span>${esc(rulesText("placementGracePlaying", { card: cardName(payload.cardId) }))}</span>`
    + `<button type="button" data-grace-cancel>${esc(t("placementGraceCancel"))}</button>`
    + `<button type="button" class="primary" data-grace-play>${esc(t("placementGracePlay"))}</button>`
    + `<i class="placement-grace-timer" style="animation-duration:${PLACEMENT_GRACE_MS}ms"></i>`;
  document.body.appendChild(bar);
  const grace = { bar, commit, timer: window.setTimeout(() => settlePlacementGrace(true), PLACEMENT_GRACE_MS) };
  pendingPlacementGrace = grace;
  bar.querySelector("[data-grace-play]").addEventListener("click", () => settlePlacementGrace(true));
  bar.querySelector("[data-grace-cancel]").addEventListener("click", () => {
    settlePlacementGrace(false);
    renderAll();
  });
}
function settlePlacementGrace(play) {
  const grace = pendingPlacementGrace;
  if (!grace) return;
  pendingPlacementGrace = null;
  window.clearTimeout(grace.timer);
  grace.bar.remove();
  if (play) grace.commit();
}
function sendCardPlacementNow(payload, source, triggerTargets = []) {
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
