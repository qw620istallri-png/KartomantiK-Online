// On-board targeting and payment flows for Stack choices and actions.
// Loaded before app.js: declarations only, nothing runs at load time.

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
  rulesBoardArmedElements = [];
  if (rulesBoardPointerMove) document.removeEventListener("pointermove", rulesBoardPointerMove);
  rulesBoardPointerMove = null;
  const path = $("#rulesTargetArrow .rules-target-arrow-line");
  if (path) path.setAttribute("d", "");
}

function closeRulesBoardFlow() {
  document.body.classList.remove("flow-uses-hand");
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
  // a choice the server still waits for cannot be dismissed (Escape when leaving full screen): it comes back
  if (flow?.choiceId && flow.mode !== "chain") renderRulesBoardFlow();
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
  // "another target ..." effects never offer their own card (Zombieswing in the Limbo)
  if (choice.targetRules?.excludeSource) {
    const draft = pendingRulesBoardFlow.draft;
    draft.structuredTargets = draft.structuredTargets.filter((target) => !(
      target.kind === "zone_card" && target.cardId === choice.sourceCardId
    ));
  }
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
  const chosen = [...(flow.selectedTargets || []), ...(target ? [target] : [])];
  const targetRules = flow.draft.targetRules || {};
  if (option === "retarget" && (
    chosen.length < Number(targetRules.min || 0)
    || chosen.length > Number(targetRules.max || 1)
  )) return;
  flow.previousStage = flow.stage;
  flow.stage = "committing";
  renderRulesBoardFlow();
  send({
    type: "resolve_rules_choice",
    choiceId: flow.choiceId,
    option,
    targets: option === "retarget" ? chosen.map(rulesTargetPayload) : [],
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
  flow.previousStage = flow.stage;
  flow.stage = "committing";
  renderRulesBoardFlow();
  send({
    type: "resolve_rules_choice",
    choiceId: flow.choiceId,
    option,
    cardIds: paymentCardIds,
  });
}

// The played card and the cards paid as its tribute are the "ingredients"
// of the action: they leave the Hand, so they can never be its Hand target.
function rulesBoardIngredientTarget(flow, target) {
  if (target?.kind !== "zone_card" || target.zone !== "hand") return false;
  const ingredients = new Set(
    [...rulesBoardSelectedPayments(flow), ...rulesBoardExtraTributeCards(flow).map((entry) => entry.cardId)]
      .map((ref) => String(ref || ""))
      .filter((ref) => !ref.includes("|") || ref.startsWith("hand|"))
      .map((ref) => ref.replace(/^hand\|/, "")),
  );
  if (flow?.source?.zone === "hand") ingredients.add(flow.source.cardId);
  return ingredients.has(target.cardId);
}

function rulesBoardSelectedPayments(flow = pendingRulesBoardFlow) {
  return [...(flow?.selectedPaymentIndexes || [])]
    .map((selectionKey) => flow?.draft?.manifestations?.find(
      (entry) => entry.selectionKey === selectionKey,
    )?.paymentValue)
    .filter(Boolean);
}

function rulesBoardExtraTributeCards(flow) {
  const chosen = flow?.extraTributeIndexes || new Set();
  return (flow?.draft?.extraTributeCards || []).filter((entry) => (
    chosen.has(entry.index) && !flow.selectedPaymentIndexes?.has(entry.index)
    && entry.index !== flow.costCardIndex
  ));
}

function rulesBoardOptionalExtraEssenceMax(flow) {
  const optional = flow.draft.encodedAbility?.optionalExtraEssence;
  if (!optional) return 0;
  const available = Number(flow.draft.optionalExtraEssenceMax || 0);
  const room = Math.max(0, Number(optional.max || 0) - available);
  const selected = rulesBoardSelectedPayments(flow);
  if (!room || !selected.length) return available;
  const requirements = { ...flow.draft.essencePlan.remaining };
  requirements[optional.temperament] = Number(requirements[optional.temperament] || 0) + room;
  const remaining = rulesRemainingAfterManifestations(selected, requirements);
  const missing = Object.values(remaining).reduce((sum, amount) => sum + Math.max(0, amount), 0);
  return available + Math.max(0, room - missing);
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
    resolveRulesStackCopyTargets("retarget", target);
    return;
  }
  if (flow.mode === "trigger_target") {
    const chosen = [...(flow.selectedTargets || []), ...(target ? [target] : [])];
    if (chosen.length < Number(flow.draft.targetRules?.min || 0)) return;
    flow.previousStage = flow.stage;
    flow.stage = "committing";
    renderRulesBoardFlow();
    send({
      type: "resolve_rules_choice",
      choiceId: flow.choiceId,
      targets: chosen.map(rulesTargetPayload),
    });
    return;
  }
  if (flow.mode === "placement") {
    // target groups (Kaos Bro, Karma Bro: one card per player) arrive as selectedTargets
    const chosen = [...(flow.selectedTargets || []), ...(target ? [target] : [])];
    if (!chosen.length) return;
    sendCardPlacement(flow.placement, flow.source, chosen.map(rulesTargetPayload));
    closeRulesBoardFlow();
    return;
  }
  const activated = !flow.source.playFromField && (
    flow.actionKind === "activated_effect"
    || flow.source.actionKind === "activated_effect"
    || flow.source.zone === "battlefield"
  );
  const selectedTargets = [...(flow.selectedTargets || [])];
  if (target) selectedTargets.push(target);
  if (target && flow.draft.encodedAbility?.extraEssenceForTargetPoints && !flow.targetsConfirmed) {
    flow.selectedTargets = selectedTargets;
    confirmRulesBoardTargets();
    return;
  }
  const payload = {
    type: "declare_rules_action",
    label: rulesText(activated ? "rulesDefaultActivate" : "rulesDefaultPlay", { card: cardName(flow.source.cardId) }),
    kind: activated ? "activated_effect" : "play_card",
    source: {
      cardId: flow.source.cardId,
      zone: flow.source.zone,
      itemId: (activated || flow.source.playFromField || flow.source.zone === "attached") ? flow.source.itemId : null,
      ...(flow.source.containerId ? { containerId: flow.source.containerId } : {}),
    },
    target: "",
    targets: selectedTargets.map(rulesTargetPayload),
    costNote: "",
    paymentCardIds: rulesBoardSelectedPayments(flow),
    extraEssenceCount: Number(flow.extraEssenceCount || 0),
  };
  if (flow.draft.transcendentPayment !== undefined) payload.transcendentPayment = flow.draft.transcendentPayment;
  const extraTribute = rulesBoardExtraTributeCards(flow).map((entry) => entry.cardId);
  if (extraTribute.length) payload.extraPaymentCardIds = extraTribute;
  if (flow.costCardId) payload.costCardId = flow.costCardId;
  if (flow.draft.encodedAbility?.id) payload.abilityId = flow.draft.encodedAbility.id;
  if (flow.source.placement) payload.placement = flow.source.placement;
  send(payload);
  closeRulesBoardFlow();
}

// A rejected payment/target must not leave the flow locked in "committing":
// go back to where the player was so they can choose again (or decline).
function releaseRulesBoardFlowAfterError() {
  const flow = pendingRulesBoardFlow;
  if (flow?.counterEssencePending) { flow.counterEssencePending = null; renderRulesBoardFlow(); return; }
  if (!flow || flow.stage !== "committing") return;
  flow.stage = flow.previousStage && flow.previousStage !== "committing" ? flow.previousStage : "payment";
  if (flow.stage === "payment") flow.selectedPaymentIndexes = new Set();
  renderRulesBoardFlow();
}
function rulesDraftOffersOptionalTargets(draft) {
  return Number(draft?.targetRules?.min || 0) === 0
    && Number(draft?.targetRules?.max || 0) > 0
    && (draft?.structuredTargets || []).length > 0;
}

function scheduleRulesBoardSubmit() {
  const flow = pendingRulesBoardFlow;
  if (!flow) return;
  if (flow.mode === "stack_copy_target") {
    resolveRulesStackCopyTargets("retarget");
    return;
  }
  flow.previousStage = flow.stage;
  flow.stage = "committing";
  renderRulesBoardFlow();
  window.setTimeout(() => {
    if (pendingRulesBoardFlow === flow && flow.stage === "committing") submitRulesBoardFlow();
  }, 180);
}

function confirmRulesBoardTargets() {
  const flow = pendingRulesBoardFlow;
  if (!flow) return;
  const count = (flow.selectedTargets || []).length;
  if (count < Number(flow.draft.targetRules?.min || 0) || count > Number(flow.draft.targetRules?.max || 1)) return;
  const extra = flow.draft.encodedAbility?.extraEssenceByTargetCount;
  const points = flow.draft.encodedAbility?.extraEssenceForTargetPoints;
  let extraAmount = extra && count >= Number(extra.targetCount) ? Number(extra.amount) : 0;
  if (points) {
    const base = rulesActionPaymentDraft({ ...flow.source, targetExtraEssence: 0 }, flow.draft.card, flow.draft.encodedAbility);
    const total = Math.ceil(Number(cardsById.get(flow.selectedTargets[0]?.cardId)?.points || 0) / Number(points.multiplier || 10));
    extraAmount = Math.max(extraAmount, total - Object.values(base.paymentRequirements).reduce((sum, value) => sum + Number(value || 0), 0));
  }
  if (extraAmount > 0) {
    flow.source.targetExtraEssence = extraAmount;
    Object.assign(flow.draft, rulesActionPaymentDraft(flow.source, flow.draft.card, flow.draft.encodedAbility, flow.draft.transcendentPayment));
    flow.targetsConfirmed = true;
    const selected = rulesBoardSelectedPayments(flow);
    if (!rulesManifestationsCover(selected, flow.draft.essencePlan.remaining)) {
      flow.stage = "payment";
      renderRulesBoardFlow();
      return;
    }
  }
  scheduleRulesBoardSubmit();
}

function armRulesBoardTargets(flow) {
  clearRulesBoardTargets();
  const induceDesertion = flow.draft.encodedAbility?.id === "induce-desertion";
  const firstTarget = (flow.selectedTargets || [])[0];
  if (induceDesertion && firstTarget) {
    const element = rulesTargetElement(firstTarget);
    element?.classList.add("rules-selected-effect-target");
    rulesBoardTargetCleanup.push(() => element?.classList.remove("rules-selected-effect-target"));
  }
  const visibleTargets = [];
  const zoneTargetOffsets = new Map();
  const selectedKeys = new Set(
    (flow.selectedTargets || []).map((target) => target.key)
  );
  const targetGroupIndex = (flow.selectedTargets || []).length;
  const candidates = flow.draft.structuredTargets
    .filter((target) => (
      !flow.draft.targetRules?.groups
      || target.targetGroupIndex === targetGroupIndex
    ))
    .filter((target) => !selectedKeys.has(target.key))
    .filter((target) => !rulesBoardIngredientTarget(flow, target))
    .filter((target) => !induceDesertion || (firstTarget
      ? battlefieldItemControllerId(target) === battlefieldItemControllerId(firstTarget)
      : flow.draft.structuredTargets.some((support) => support.targetGroupIndex === 1 && support.id !== target.id && battlefieldItemControllerId(support) === battlefieldItemControllerId(target))));
  // several targets without groups (Atavic Introspection: 2 Limbo cards): pick them
  // one by one, sent once the maximum is reached (or confirmed past the minimum)
  const maxTargets = Number(flow.draft.targetRules?.max || 1);
  const minTargets = Number(flow.draft.targetRules?.min || 0);
  const multiPick = !flow.draft.targetRules?.groups && maxTargets > 1;
  const commitTarget = (target) => {
    playRulesVfxTargetLock(rulesTargetElement(target));
    if (multiPick) {
      flow.selectedTargets = [...(flow.selectedTargets || []), target];
      if (flow.draft.encodedAbility?.extraEssenceByTargetCount || minTargets < maxTargets) {
        renderRulesBoardFlow();
      } else if (flow.selectedTargets.length >= Math.min(maxTargets, flow.selectedTargets.length + candidates.length - 1)) {
        scheduleRulesBoardSubmit();
      } else {
        renderRulesBoardFlow();
      }
      return;
    }
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
  // Choosing a player: a small popup with one button per player (me / opponent)
  if (candidates.length && candidates.every((target) => target.kind === "player")) {
    const popup = document.createElement("div");
    popup.className = "log-panel rules-choice-panel rules-player-target-panel cards-screen player-screen effect-screen";
    const sourceCard = flow.draft.card;
    const sourceImage = sourceCard?.id ? cardImage(sourceCard.id) : "";
    const sourceEffect = sourceCard ? cardField(sourceCard, "effect") : "";
    popup.innerHTML = `<div class="box${sourceImage ? " has-source" : ""}">
      ${sourceImage ? `<span class="rules-choice-source" title="${esc(cardName(sourceCard.id))}"><img src="${esc(sourceImage)}" alt="${esc(cardName(sourceCard.id))}"></span>` : ""}
      ${sourceEffect ? `<p class="rules-choice-effect">${rulesActiveAbilityMarkup(flow.choice?.sourceAbilityId) || esc(sourceEffect)}</p>` : ""}
      <div class="rules-choice-options">
        ${candidates.map((target) => `<button type="button" class="rules-choice-player" data-player-target="${esc(target.key)}" style="--player-tone:${esc(playerColor(target.playerId))}">${esc(target.playerId === myPlayerId ? t("rulesTargetSelf") : t("rulesTargetOpponent"))} · ${esc(rulesPlayerName(target.playerId))}</button>`).join("")}
      </div>
    </div>`;
    document.body.appendChild(popup);
    popup.querySelectorAll("[data-player-target]").forEach((button) => {
      button.onclick = () => commitTarget(candidates.find((target) => target.key === button.dataset.playerTarget));
    });
    rulesBoardTargetCleanup.push(() => popup.remove());
    return;
  }
  // Choosing among public-zone cards (Limbo, Exile...) that have no spot on the board: the cards-only screen
  const zoneChoices = [...(flow.selectedTargets || []), ...candidates];
  if (
    zoneChoices.length
    && zoneChoices.every((target) => target.kind === "zone_card" && target.zone !== "hand")
  ) {
    const popup = document.createElement("div");
    popup.className = "log-panel rules-choice-panel rules-zone-target-panel cards-screen zone-pick-screen effect-screen";
    const sourceCard = flow.draft.card;
    const sourceImage = sourceCard?.id ? cardImage(sourceCard.id) : "";
    const sourceEffect = sourceCard ? cardField(sourceCard, "effect") : "";
    popup.innerHTML = `<div class="box${sourceImage ? " has-source" : ""}">
      ${sourceImage ? `<span class="rules-choice-source" title="${esc(cardName(sourceCard.id))}"><img src="${esc(sourceImage)}" alt="${esc(cardName(sourceCard.id))}"></span>` : ""}
      ${sourceEffect ? `<p class="rules-choice-effect">${esc(sourceEffect)}</p>` : ""}
      <div class="rules-choice-options has-card-picker">
        ${[...(flow.selectedTargets || []), ...candidates].map((target) => {
          const picked = selectedKeys.has(target.key);
          return `<button type="button" class="rules-choice-card${picked ? " is-selected" : ""}" ${picked ? "data-zone-unpick" : "data-zone-pick"}="${esc(target.key)}" title="${esc(cardName(target.cardId))}">
          <img src="${esc(cardImage(target.cardId))}" alt="${esc(cardName(target.cardId))}">
          <span>${esc(rulesPlayerName(target.containerId))} · ${esc(t(target.zone))}</span>
        </button>`;
        }).join("")}
      </div>
      <div class="rules-zone-pick-actions"><button type="button" class="primary" data-zone-pick-confirm ${(flow.selectedTargets || []).length >= minTargets ? "" : "disabled"}>${esc(t("confirm"))} (${(flow.selectedTargets || []).length}/${maxTargets})</button></div>
    </div>`;
    document.body.appendChild(popup);
    popup.querySelectorAll("[data-zone-pick]").forEach((button) => {
      button.onclick = () => {
        const target = candidates.find((target) => target.key === button.dataset.zonePick);
        if (!multiPick) flow.selectedTargets = [target];
        else if ((flow.selectedTargets || []).length < maxTargets) flow.selectedTargets = [...(flow.selectedTargets || []), target];
        renderRulesBoardFlow();
      };
    });
    popup.querySelectorAll("[data-zone-unpick]").forEach((button) => {
      button.onclick = () => {
        flow.selectedTargets = (flow.selectedTargets || []).filter((target) => target.key !== button.dataset.zoneUnpick);
        renderRulesBoardFlow();
      };
    });
    const zoneConfirm = popup.querySelector("[data-zone-pick-confirm]");
    if (zoneConfirm) zoneConfirm.onclick = () => { zoneConfirm.disabled = true; confirmRulesBoardTargets(); };
    rulesBoardTargetCleanup.push(() => popup.remove());
    return;
  }
  if ((flow.selectedTargets || []).length >= maxTargets) return;
  candidates.forEach((target) => {
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
    rulesBoardArmedElements.push(element);
    element.classList.add("rules-valid-target");
    const reticle = document.createElement("span");
    reticle.className = "rules-target-reticle";
    reticle.setAttribute("aria-hidden", "true");
    element.appendChild(reticle);
    const select = (event) => {
      event.preventDefault();
      event.stopPropagation();
      commitTarget(target);
    };
    element.addEventListener("pointerdown", select, true);
    rulesBoardTargetCleanup.push(() => {
      element.classList.remove("rules-valid-target");
      reticle.remove();
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

function appendRulesCounterEssenceOptions(flow, remaining) {
  const counterSources = rulesCounterEssenceSources().filter((source) => Number(remaining[source.temperament] || 0) > 0 || Number(remaining.hollow || 0) > 0);
  if (!counterSources.length) return;
  const choices = document.createElement("div");
  choices.className = "rules-counter-essence-options";
  choices.innerHTML = `<p>${esc(t("rulesCounterEssenceOptional"))}</p>${counterSources.map((source, index) => `<button type="button" data-spend-counter-essence="${index}" ${flow.counterEssencePending ? "disabled" : ""}><img src="${esc(temperamentSymbol(source.temperament))}" alt="">${esc(t("rulesUseEssenceCounter"))} · ${esc(cardName(source.item.cardId))} (${source.count})</button>`).join("")}`;
  $("#rulesFlowCost").appendChild(choices);
  choices.querySelectorAll("[data-spend-counter-essence]").forEach((button) => {
    button.onclick = () => {
      const source = counterSources[Number(button.dataset.spendCounterEssence)];
      if (flow.counterEssencePending) return;
      flow.counterEssencePending = { itemId: source.item.id, counters: JSON.stringify(source.item.counters || {}) };
      choices.querySelectorAll("button").forEach((candidate) => { candidate.disabled = true; });
      send({ type: "spend_counter_essence", itemId: source.item.id, abilityId: source.ability.id });
    };
  });
}

function advanceRulesBoardFlow() {
  const flow = pendingRulesBoardFlow;
  if (!flow) return;
  if (flow.targetsConfirmed) { scheduleRulesBoardSubmit(); return; }
  if (flow.draft.encodedAbility?.additionalCost && !flow.costCardId) {
    flow.stage = "cost_card";
    renderRulesBoardFlow();
    return;
  }
  if (
    (rulesBoardOptionalExtraEssenceMax(flow) > 0 || flow.draft.extraTributeCards?.length)
    && !flow.extraEssenceConfirmed
  ) {
    flow.stage = "extra_essence";
    renderRulesBoardFlow();
    return;
  }
  const needsTarget = Number(flow.draft.targetRules?.min || 0) > 0
    || rulesDraftOffersOptionalTargets(flow.draft);
  if (needsTarget) {
    flow.stage = "target";
    renderRulesBoardFlow();
    return;
  }
  scheduleRulesBoardSubmit();
}

function rulesBoardPaymentKey(ctx) {
  const flow = pendingRulesBoardFlow;
  if (!flow || flow.stage !== "payment") return undefined;
  const key = ctx.kind === "battlefield" ? `battlefield:${ctx.itemId}`
    : ctx.fromOwnerId !== myPlayerId ? undefined
      : ctx.fromZone === "hand" ? ctx.handIndex : ctx.paymentKey;
  return flow.draft.manifestations.some(entry => entry.selectionKey === key) ? key : undefined;
}

function rulesBoardHandCostCandidates(flow = pendingRulesBoardFlow) {
  const hand = latestState?.players?.[myPlayerId]?.zones?.hand?.cards || [];
  const sourceIndex = flow?.source.zone === "hand"
    ? (flow.source.handIndex ?? hand.indexOf(flow.source.cardId)) : -1;
  const discardWill = flow?.draft.encodedAbility?.additionalCost === "discard_hand_will";
  return hand.map((cardId, index) => ({ cardId, index })).filter(entry => entry.index !== sourceIndex
    && !flow?.selectedPaymentIndexes?.has(entry.index)
    && !flow?.extraTributeIndexes?.has(entry.index)
    && (discardWill ? ["ephemeral_will", "persistent_will"].includes(cardsById.get(entry.cardId)?.type)
      : cardsById.get(entry.cardId)?.type === "manifestation"));
}

// Every card cost uses the same deliberate drop onto the asking card.
function resolveRulesBoardCardDrop(ctx, target) {
  const flow = pendingRulesBoardFlow;
  if (!flow || !["payment", "cost_card", "extra_essence"].includes(flow.stage)) return false;
  if (!target?.closest("#rulesFloatingCard")) return true;
  if (flow.stage === "payment") {
    const key = rulesBoardPaymentKey(ctx);
    if (key !== undefined) toggleRulesBoardPayment(key);
    return true;
  }
  if (ctx.fromOwnerId !== myPlayerId || ctx.fromZone !== "hand") return true;
  if (flow.stage === "cost_card") {
    const candidate = rulesBoardHandCostCandidates(flow).find(entry => entry.index === ctx.handIndex);
    if (candidate) {
      flow.costCardId = candidate.cardId;
      flow.costCardIndex = candidate.index;
      advanceRulesBoardFlow();
    }
  } else {
    const candidate = (flow.draft.extraTributeCards || []).find(entry => entry.index === ctx.handIndex
      && !flow.selectedPaymentIndexes.has(entry.index) && entry.index !== flow.costCardIndex);
    if (candidate) {
      if (!flow.extraTributeIndexes) flow.extraTributeIndexes = new Set();
      if (flow.extraTributeIndexes.has(candidate.index)) flow.extraTributeIndexes.delete(candidate.index);
      else flow.extraTributeIndexes.add(candidate.index);
      renderRulesBoardFlow();
    }
  }
  return true;
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
  // several Manifestations may pay together; only a card that could be removed
  // while the Tribute stays fully paid is superfluous (3 + 4 for a 4, not 2 + 3)
  const superfluous = selected.some((_value, skipped) => rulesManifestationsCover(
    selected.filter((_other, position) => position !== skipped),
    flow.draft.essencePlan.remaining,
  ));
  if (superfluous) {
    showToast(t("rulesTributeRedundantError"), true);
    return true;
  }
  advanceRulesBoardFlow();
  return true;
}

let handGhostSignature = "";

let rulesFlowFlipTimer = null;

function renderRulesBoardFlow() {
  const counterFlow = pendingRulesBoardFlow;
  if (counterFlow?.counterEssencePending) {
    const pending = counterFlow.counterEssencePending;
    const source = (latestState?.battlefield || []).find((item) => item.id === pending.itemId);
    const now = JSON.stringify(source?.counters || {});
    if (now !== pending.counters) {
      counterFlow.counterEssencePending = null;
        const ability = counterFlow.mode === "stack_payment" ? { tribute: counterFlow.choice.payment } : counterFlow.draft.encodedAbility;
        Object.assign(counterFlow.draft, rulesActionPaymentDraft(counterFlow.source, counterFlow.draft.card, ability));
      counterFlow.selectedPaymentIndexes.clear();
        counterFlow.stage = counterFlow.mode === "stack_payment" ? "payment" : rulesInitialActionStage(counterFlow.draft);
      if (counterFlow.stage === "target") { advanceRulesBoardFlow(); return; }
    }
  }
  const ghostSignature = pendingRulesBoardFlow?.stage === "payment"
    ? [...pendingRulesBoardFlow.selectedPaymentIndexes].join(",") + "|" + (pendingRulesBoardFlow.draft?.manifestations || []).filter((entry) => entry.zone === "graveyard").map((entry) => entry.selectionKey).join(",")
    : "";
  if (ghostSignature !== handGhostSignature) {
    handGhostSignature = ghostSignature;
    renderHandTray();
  }
  syncRulesStackCopyBoardFlow();
  syncRulesStackPaymentBoardFlow();
  syncRulesChainBoardFlow();
  syncRulesTriggerTargetBoardFlow();
  const flow = pendingRulesBoardFlow;
  const panel = $("#rulesBoardFlow");
  // paying or chaining from the hand (tribute, card cost, Advocate of Catharsis): the hand rises above the dark screen
  document.body.classList.toggle("flow-uses-hand", Boolean(
    flow && flow.mode !== "stack_copy_target" && (flow.mode === "chain" || ["essence_allocation", "payment", "cost_card", "extra_essence"].includes(flow.stage)),
  ));
  if (!flow || !panel) {
    panel?.classList.add("hidden");
    return;
  }
  const flipWait = rulesAnimationsBusyFor();
  if (flipWait > 0 && ["trigger_target", "chain", "stack_copy_target", "stack_payment"].includes(flow.mode)) {
    // effect windows wait for the reveal flip to end
    panel.classList.add("hidden");
    clearTimeout(rulesFlowFlipTimer);
    rulesFlowFlipTimer = setTimeout(() => { rulesFlowFlipTimer = null; renderRulesBoardFlow(); }, Math.min(flipWait + 30, 2500));
    return;
  }
  const handSourceStillValid = (["hand", "graveyard"].includes(flow.source.zone)
    && (latestState?.players?.[myPlayerId]?.zones?.[flow.source.zone]?.cards || []).includes(flow.source.cardId))
    || (flow.source.zone === "suspended" && (latestState?.rulesEngine?.suspendedCards || []).some(entry => entry.id === flow.source.suspensionId && entry.cardId === flow.source.cardId && entry.playableByPlayerId === myPlayerId));
  const battlefieldSource = flow.source.zone === "battlefield"
    ? latestState?.battlefield?.find((item) => item.id === flow.source.itemId)
    : null;
  const battlefieldSourceStillValid = Boolean(
    battlefieldSource
    && battlefieldItemControllerId(battlefieldSource) === myPlayerId
    && battlefieldSource.cardId === flow.source.cardId
    // a Concealed card (Jigon, Tebebe) is played from the field face down
    && (battlefieldSource.faceUp || (flow.source.playFromField && battlefieldSource.concealedWill))
  );
  // Grimoire: a Will placed on its host is played as if it were in the hand
  const attachedHost = flow.source.zone === "attached"
    ? latestState?.battlefield?.find((item) => item.id === flow.source.itemId)
    : null;
  const attachedSourceStillValid = Boolean(
    attachedHost
    && battlefieldItemControllerId(attachedHost) === myPlayerId
    && (attachedHost.attachedCards || []).some((entry) => entry.cardId === flow.source.cardId)
  );
  if (flow.mode === "action" && (
    latestState?.rulesEngine?.priorityPlayerId !== myPlayerId
    || (!handSourceStillValid && !battlefieldSourceStillValid && !attachedSourceStillValid)
  )) {
    closeRulesBoardFlow();
    return;
  }
  panel.classList.remove("hidden");
  const dropHint = $("#rulesCardDropHint");
  dropHint.hidden = !["payment", "cost_card", "extra_essence"].includes(flow.stage);
  dropHint.textContent = t("rulesDragCardToEffect");
  const stackDecision = ["stack_payment", "stack_copy_target"].includes(flow.mode);
  panel.classList.toggle("is-stack-payment", stackDecision);
  // pre-play choices (payment, cost card, extra essence) open in the middle of the screen; board targets keep the side card
  // paying a Tribute asked by an effect (stack_payment) uses the same centred dark screen, with the hand above it
  panel.classList.toggle("is-centered", flow.mode !== "stack_copy_target" && ["choice", "essence_allocation", "payment", "cost_card", "extra_essence", "committing"].includes(flow.stage));
  panel.classList.toggle("is-guided-target", flow.stage === "target" && (flow.draft.encodedAbility?.id === "induce-desertion" || Boolean(rulesActiveAbilityEffect(flow.choice?.sourceAbilityId))));
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
    const candidate = flow.stage === "payment" ? flow.draft.manifestations.some(entry => entry.selectionKey === index)
      : flow.stage === "cost_card" ? rulesBoardHandCostCandidates(flow).some(entry => entry.index === index)
        : flow.stage === "extra_essence" && (flow.draft.extraTributeCards || []).some(entry => entry.index === index && !flow.selectedPaymentIndexes.has(index) && entry.index !== flow.costCardIndex);
    element.classList.toggle("is-tribute-candidate", candidate);
    element.classList.toggle("is-tribute-selected", candidate && (flow.stage === "extra_essence" ? flow.extraTributeIndexes?.has(index) : flow.selectedPaymentIndexes.has(index)));
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
    if (flow.optional) {
      // no question beforehand: drag a card from the hand, or pass
      $("#rulesFlowChoiceActions").classList.remove("hidden");
      const passButton = $("#rulesFlowDeclineBtn");
      passButton.hidden = false;
      passButton.disabled = false;
      passButton.textContent = t("passPhase");
      $("#rulesFlowPayBtn").classList.add("hidden");
    }
    clearRulesBoardTargets();
    return;
  }

  if (flow.mode === "stack_copy_target") {
    const declineButton = $("#rulesFlowDeclineBtn");
    declineButton.hidden = false;
    declineButton.textContent = t("rulesKeepCopiedTargets");
    declineButton.disabled = flow.stage === "committing";
    $("#rulesFlowInstruction").textContent = rulesText("rulesCopyChooseTargetInstruction", {
      card: cardName(flow.choice.targetCardId),
    });
    const original = (flow.choice.originalTargets || []).map(rulesActionTargetRef).join(", ");
    const selected = flow.selectedTargets || [];
    const targetRules = flow.draft.targetRules || {};
    const canConfirm = !targetRules.groups && Number(targetRules.max || 0) > 1;
    $("#rulesFlowCost").innerHTML = `<div class="rules-flow-cost-row"><span>${esc(t("rulesCurrentTarget"))}</span><strong>${original || esc(t("rulesNoTargetRequired"))}</strong></div>${canConfirm ? `<div class="rules-zone-pick-actions"><button type="button" class="primary" id="rulesConfirmTargets" ${selected.length >= Number(targetRules.min || 0) ? "" : "disabled"}>${esc(t("confirm"))} (${selected.length}/${targetRules.max})</button></div>` : ""}`;
    const confirmTargets = $("#rulesConfirmTargets");
    if (confirmTargets) confirmTargets.onclick = confirmRulesBoardTargets;
    if (flow.stage === "committing") clearRulesBoardTargets();
    else armRulesBoardTargets(flow);
    return;
  }
  if (flow.mode === "trigger_target") {
    const activeEffect = rulesActiveAbilityMarkup(flow.choice.sourceAbilityId);
    if (activeEffect) $("#rulesFlowInstruction").innerHTML = activeEffect;
    else $("#rulesFlowInstruction").textContent = rulesText("rulesTriggerChooseTargetInstruction", { card: cardName(flow.choice.sourceCardId) });
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
    declineButton.hidden = Boolean(flow.choice.mustPay);
    appendRulesCounterEssenceOptions(flow, remaining);
    clearRulesBoardTargets();
    return;
  }

  if (flow.stage === "essence_allocation") {
    const choice = flow.draft.essencePlan.transcendentChoice;
    const allocation = flow.transcendentAllocation ||= { ...(flow.draft.transcendentPayment || {}) };
    const colours = Object.keys(choice.requirements).filter((colour) => choice.requirements[colour] > 0);
    $("#rulesFlowInstruction").textContent = rulesText("rulesWhiteEssenceInstruction", { count: choice.amount });
    $("#rulesFlowCost").innerHTML = colours.map((colour) => {
      const name = t(`temperament${colour[0].toUpperCase()}${colour.slice(1)}`);
      const maximum = Math.min(choice.amount, choice.requirements[colour]);
      return `<div class="rules-flow-cost-row rules-white-essence-row"><label for="rulesWhite-${colour}"><img src="${esc(temperamentSymbol(colour))}" alt="">${esc(name)}</label><div class="number-stepper"><button type="button" data-white-minus="${colour}" aria-label="${esc(`${t("decrease")} · ${name}`)}">−</button><input id="rulesWhite-${colour}" data-white-colour="${colour}" type="number" min="0" max="${maximum}" value="${allocation[colour] || 0}" aria-label="${esc(name)}"><button type="button" data-white-plus="${colour}" aria-label="${esc(`${t("increase")} · ${name}`)}">+</button></div></div>`;
    }).join("") + `<div class="rules-flow-cost-row"><span>${esc(t("rulesTributeRemaining"))}</span><span id="rulesWhiteRemaining"></span></div><button type="button" class="primary" id="rulesWhiteConfirm">${esc(t("confirm"))}</button>`;
    const update = (colour, value) => {
      allocation[colour] = Math.max(0, Math.min(Math.floor(Number(value) || 0), choice.amount, choice.requirements[colour]));
      $(`#rulesWhite-${colour}`).value = allocation[colour];
      const total = colours.reduce((sum, key) => sum + Number(allocation[key] || 0), 0);
      $("#rulesWhiteConfirm").disabled = total !== choice.amount;
      const remaining = Object.fromEntries(colours.map((key) => [key, choice.requirements[key] - Number(allocation[key] || 0)]));
      $("#rulesWhiteRemaining").innerHTML = rulesTributeUnitsHtml(remaining, t("rulesCoveredByEssence"));
    };
    for (const colour of colours) {
      $(`#rulesWhite-${colour}`).oninput = (event) => update(colour, event.target.value);
      $(`[data-white-minus="${colour}"]`).onclick = () => update(colour, Number(allocation[colour] || 0) - 1);
      $(`[data-white-plus="${colour}"]`).onclick = () => update(colour, Number(allocation[colour] || 0) + 1);
    }
    update(colours[0], allocation[colours[0]] || 0);
    $("#rulesWhiteConfirm").onclick = () => {
      const payment = Object.fromEntries(colours.filter((key) => allocation[key] > 0).map((key) => [key, allocation[key]]));
      if (Object.values(payment).reduce((sum, value) => sum + value, 0) !== choice.amount) return;
      Object.assign(flow.draft, rulesActionPaymentDraft(flow.source, flow.draft.card, flow.draft.encodedAbility, payment));
      flow.selectedPaymentIndexes.clear();
      if (Object.values(flow.draft.essencePlan.remaining).some((amount) => amount > 0)) {
        flow.stage = "payment";
        renderRulesBoardFlow();
      } else advanceRulesBoardFlow();
    };
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
      <div class="rules-flow-cost-row"><span>${esc(t("rulesTributeRemaining"))}</span>${rulesTributeUnitsHtml(remaining, t("rulesCoveredByEssence"))}</div>${flow.draft.transcendentPayment !== undefined ? `<button type="button" id="rulesChangeWhitePayment">${esc(t("rulesChangeWhitePayment"))}</button>` : ""}`;
    const changeWhite = $("#rulesChangeWhitePayment");
    if (changeWhite) changeWhite.onclick = () => { flow.stage = "essence_allocation"; renderRulesBoardFlow(); };
    appendRulesCounterEssenceOptions(flow, remaining);
    clearRulesBoardTargets();
    return;
  }

  if (flow.stage === "cost_card") {
    const choices = rulesBoardHandCostCandidates(flow);
    const discardCost = flow.draft.encodedAbility?.additionalCost === "discard_hand_will";
    $("#rulesBoardEssence").classList.add("hidden");
    $("#rulesFlowInstruction").textContent = t(
      choices.length
        ? (discardCost ? "rulesCostWillInstruction" : "rulesCostCardInstruction")
        : (discardCost ? "rulesCostWillNone" : "rulesCostCardNone"),
    );
    // Use the real, highlighted hand cards instead of a second clickable picker.
    $("#rulesFlowCost").innerHTML = "";
    clearRulesBoardTargets();
    return;
  }

  if (flow.stage === "extra_essence") {
    const max = rulesBoardOptionalExtraEssenceMax(flow);
    const current = Math.max(
      0, Math.min(Number(flow.extraEssenceCount || 0), max),
    );
    if (!flow.extraTributeIndexes) flow.extraTributeIndexes = new Set();
    const extraCandidates = (flow.draft.extraTributeCards || []).filter(
      (entry) => !flow.selectedPaymentIndexes?.has(entry.index) && entry.index !== flow.costCardIndex,
    );
    const extraCardsHtml = extraCandidates.length ? `
      <div class="rules-flow-cost-row rules-extra-tribute-row">
        <span>${esc(t("rulesOptionalExtraCards"))}</span>
        <strong>${flow.extraTributeIndexes.size}/${extraCandidates.length}</strong>
      </div>` : "";
    $("#rulesBoardEssence").classList.add("hidden");
    $("#rulesFlowInstruction").textContent = rulesText(
      "rulesOptionalExtraEssenceInstruction",
      { max: Number(flow.draft.encodedAbility?.optionalExtraEssence?.max || max) },
    );
    $("#rulesFlowCost").innerHTML = `${extraCardsHtml}
      <div class="rules-flow-cost-row rules-extra-essence-row"${max > 0 ? "" : " hidden"}>
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
  const firstTarget = (flow.selectedTargets || [])[0];
  $("#rulesFlowInstruction").textContent = flow.draft.encodedAbility?.id === "induce-desertion"
    ? firstTarget ? rulesText("rulesInduceSecondTarget", { card: cardName(firstTarget.cardId), player: rulesPlayerName(battlefieldItemControllerId(firstTarget)) }) : t("rulesInduceFirstTarget")
    : `${t("rulesBoardChooseTarget")} — ${effect}`;
  const sourceCost = flow.draft.encodedAbility?.exhaustSource
    ? `<div class="rules-flow-cost-row"><span>${esc(t("rulesCostShort"))}</span><strong>${esc(t("rulesExhaustSourceCost"))}</strong></div>`
    : flow.draft.encodedAbility?.sacrificeSource
      ? `<div class="rules-flow-cost-row"><span>${esc(t("rulesCostShort"))}</span><strong>${esc(t("rulesSacrificeSourceCost"))}</strong></div>`
      : "";
  const selected = flow.selectedTargets || [];
  const targetRules = flow.draft.targetRules || {};
  const canConfirm = !targetRules.groups && Number(targetRules.max || 0) > 1;
  $("#rulesFlowCost").innerHTML = `${sourceCost}<div class="rules-flow-cost-row"><span>${esc(t("rulesTargetLegend"))}</span><strong>${esc(t("rulesBoardClickTarget"))}</strong></div>${canConfirm ? `<div class="rules-zone-pick-actions"><button type="button" class="primary" id="rulesConfirmTargets" ${selected.length >= Number(targetRules.min || 0) ? "" : "disabled"}>${esc(t("confirm"))} (${selected.length}/${targetRules.max})</button></div>` : ""}`;
  if (flow.draft.encodedAbility?.id === "induce-desertion") $("#rulesFlowCost").innerHTML = sourceCost;
  const confirmTargets = $("#rulesConfirmTargets");
  if (confirmTargets) confirmTargets.onclick = confirmRulesBoardTargets;
  armRulesBoardTargets(flow);
}
