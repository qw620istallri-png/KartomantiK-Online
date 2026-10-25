// Phase tracker, pass controls, the Stack panel and the pregame panel.
// Loaded before app.js: declarations only, nothing runs at load time.

function currentPhaseUi(tracker = latestState?.phaseTracker) {
  const safeTracker = tracker || { enabled: false, advanced: false, index: 0, turn: 1, passedPlayerIds: [] };
  const phases = safeTracker.advanced ? ADVANCED_PHASES : BASIC_PHASES;
  const index = Math.min(Math.max(Number(safeTracker.index) || 0, 0), phases.length - 1);
  const phase = phases[index] || phases[0];
  const group = PHASE_GROUPS.find((item) => item.id === (phase?.parent || phase?.id)) || PHASE_GROUPS[0];
  return { tracker: safeTracker, phases, index, phase, group };
}

function currentPhaseLines(tracker = latestState?.phaseTracker) {
  const state = currentPhaseUi(tracker);
  if (!state.tracker.enabled || !state.phase || !state.group) return { phase: "", step: "" };
  const phase = t(state.group.label);
  let step = "";
  if (state.tracker.advanced) {
    const parts = [];
    if (state.phase.subphase) parts.push(t(state.phase.subphase));
    parts.push(`${t("phaseStep")} ${state.phase.stepNumber} — ${t(state.phase.label)}`);
    step = parts.join(" · ");
  }
  return { phase, step };
}

function currentPhaseLabel(tracker = latestState?.phaseTracker) {
  const lines = currentPhaseLines(tracker);
  return [lines.phase, lines.step].filter(Boolean).join("\n");
}

// Holding Enter for PASS_ALL_HOLD_MS fills the pass button and locks "pass
// everything": the engine passes for me even with playable cards, until a
// single Enter (or a click on the button) gives control back.
const PASS_ALL_HOLD_MS = 3000;

let passAllHoldTimer = null;

function rulesPassAllLocked() {
  return Boolean(
    latestState?.rulesEngine?.enabled
    && (latestState.rulesEngine.passAllPlayerIds || []).includes(myPlayerId)
  );
}

function setRulesPassAll(enabled) {
  cancelPassAllHold();
  send({ type: "set_rules_pass_all", enabled });
}

function startPassAllHold() {
  cancelPassAllHold();
  if (!latestState?.rulesEngine?.enabled || isObserver || rulesFirstManifestationActive()) return;
  const button = $("#passPriorityBtn");
  button?.style.setProperty("--pass-all-hold-ms", `${PASS_ALL_HOLD_MS}ms`);
  button?.classList.add("pass-all-filling");
  passAllHoldTimer = setTimeout(() => {
    passAllHoldTimer = null;
    setRulesPassAll(true);
  }, PASS_ALL_HOLD_MS);
}

function cancelPassAllHold() {
  if (passAllHoldTimer) clearTimeout(passAllHoldTimer);
  passAllHoldTimer = null;
  $("#passPriorityBtn")?.classList.remove("pass-all-filling");
}

function toggleMyPhasePass() {
  const tracker = latestState?.phaseTracker;
  if (isObserver || !tracker?.enabled) return;
  const rules = latestState?.rulesEngine;
  if (rules?.enabled) {
    if (rulesFirstManifestationActive()) {
      // a placed first Manifestation is final: validating cannot be undone
      if ((rules.firstManifestationValidatedPlayerIds || []).includes(myPlayerId)) return;
      send({ type: "validate_first_manifestation", validated: true });
      return;
    }
    const alreadyPassed = (rules.priorityPasses || []).includes(myPlayerId);
    if (alreadyPassed) send({ type: "pass_priority", passed: false });
    else if (rules.priorityPlayerId === myPlayerId) send({ type: "pass_priority", passed: true });
    return;
  }
  const passed = new Set(tracker.passedPlayerIds || []);
  send({ type: "pass_phase", passed: !passed.has(myPlayerId) });
}

function rulesFirstManifestationActive() {
  const rules = latestState?.rulesEngine;
  return Boolean(
    rules?.enabled
    && currentPhaseUi().phase?.id === "confrontation_choose"
    && !rules.firstManifestationComplete
  );
}

function renderConfrontationSummary(rules) {
  const element = $("#rulesConfrontationSummary");
  const result = rules?.confrontationResult;
  const phaseGroup = currentPhaseUi().group?.id;
  const visible = Boolean(result && phaseGroup === "resolution");
  element.classList.toggle("hidden", !visible);
  if (!visible) return;
  const playerIds = Object.keys(result.totals || {});
  const score = playerIds
    .map((playerId) => `<span class="rules-summary-total${!result.stalemate && playerId === result.winnerId ? " is-winner" : ""}" style="--player-tone:${esc(playerColor(playerId))}">${esc(rulesPlayerName(playerId))} <b>${Number(result.totals[playerId] || 0)}</b></span>`)
    .join("");
  const outcome = result.stalemate
    ? t("rulesConfrontationStalemate")
    : rulesText("rulesConfrontationWinner", { player: rulesPlayerName(result.winnerId) });
  element.innerHTML = `${score}<em>${esc(outcome)}</em>`;
  element.classList.toggle("stalemate", Boolean(result.stalemate));
  element.style.setProperty("--winner-tone", result.winnerId ? playerColor(result.winnerId) : "#b8ad91");
}

function wirePhasePassControls(root) {
  root.querySelectorAll("[data-pass-phase]").forEach((button) => {
    button.onclick = (event) => {
      event.stopPropagation();
      toggleMyPhasePass();
    };
  });
}

function phaseStepMarkup(step, index, active, canPass, passIsActive, opponentPassIsActive) {
  const body = `<span class="phase-step-number">${esc(t("phaseStep"))} ${index + 1}</span>
    <span class="phase-step-label">${esc(t(step.label))}</span>`;
  if (active && canPass) {
    const action = t(latestState?.rulesEngine?.enabled ? "passPriority" : (passIsActive ? "cancelPhasePass" : "passPhase"));
    return `<button type="button" class="phase-step active phase-pass-target ${passIsActive ? "passed" : ""} ${opponentPassIsActive ? "opponent-passed" : ""}" data-pass-phase title="${esc(t(step.detail))}" aria-label="${esc(`${t(step.label)} — ${action}`)}" aria-current="step" aria-pressed="${passIsActive}">${body}</button>`;
  }
  return `<div class="phase-step ${active ? "active" : ""}" title="${esc(t(step.detail))}" aria-current="${active ? "step" : "false"}">${body}</div>`;
}

function renderPhaseChildren(group, activePhaseId, canPass, passIsActive, opponentPassIsActive) {
  return `<div class="phase-children">${group.sections.map((section) =>
    `<section class="phase-subphase" style="--subphase-weight:${section.steps.length}">
      ${section.label ? `<strong class="phase-subphase-title">${esc(t(section.label))}</strong>` : ""}
      <div class="phase-step-row">${section.steps.map((step, index) =>
        phaseStepMarkup(step, index, step.id === activePhaseId, canPass, passIsActive, opponentPassIsActive)
      ).join("")}</div>
    </section>`
  ).join("")}</div>`;
}

function phaseIconSvg(groupId) {
  const paths = {
    recovery: '<path d="M7 7a7 7 0 1 1-1.6 7.6"/><path d="M7 3v4H3"/><path d="M9 12h6M12 9v6"/>',
    confrontation: '<path d="m5 4 6 6-2 2-6-6V4h2Z"/><path d="m19 4-6 6 2 2 6-6V4h-2Z"/><path d="m8 13-3 3m11-3 3 3M3.5 18.5l2 2m15-2-2 2"/>',
    resolution: '<path d="M12 3v18M6 6h12M7 6 4 12h6L7 6Zm10 0-3 6h6l-3-6ZM8 21h8"/>',
    end: '<path d="M18.5 15.5A8 8 0 0 1 8.5 5a8 8 0 1 0 10 10.5Z"/><path d="M15.5 5.5h3m-1.5-1.5v3"/>',
  };
  return `<svg viewBox="0 0 24 24" aria-hidden="true">${paths[groupId] || paths.recovery}</svg>`;
}

function renderPhaseTracker() {
  const { tracker, phase: activePhase, group: activeGroup } = currentPhaseUi();
  const panel = $("#phaseTracker");
  const rules = latestState?.rulesEngine;
  const panelVisible = tracker.enabled && (Boolean(rules?.enabled) || phaseTrackerVisible);
  const canConfigureAdvanced = !isObserver && mySeat() === 0 && !latestState?.rulesEngine?.enabled;
  const showAdvancedControl = panelVisible && canConfigureAdvanced;
  panel.classList.toggle("hidden", !panelVisible);
  $("#gameScreen").classList.toggle("phase-details-visible", panelVisible);
  $("#phaseTrackerBtn").textContent = t("gamePhases");
  $("#phaseTrackerBtn").title = t(panelVisible ? "hidePhases" : "showPhases");
  $("#phaseTrackerBtn").classList.toggle("active", panelVisible);
  $("#phaseTrackerBtn").disabled = isObserver && !tracker.enabled;
  $("#phaseHeaderControl").classList.toggle("expanded", showAdvancedControl);
  $("#phaseAdvancedLabel").textContent = t("advancedMode");
  $("#phaseAdvancedBtn").title = t("advancedMode");
  $("#phaseAdvancedBtn").classList.toggle("hidden", !canConfigureAdvanced);
  $("#phaseAdvancedBtn").classList.toggle("active", tracker.advanced);
  $("#phaseAdvancedBtn").disabled = !showAdvancedControl;
  $("#phaseAdvancedBtn").setAttribute("aria-pressed", String(Boolean(tracker.advanced)));
  $("#phaseTurn").classList.toggle("hidden", !tracker.enabled);
  if (tracker.enabled) $("#phaseTurn").textContent = `${t("turn")} ${tracker.turn || 1}`;
  if (!tracker.enabled) return;

  const activeGroupId = activeGroup?.id || activePhase?.parent || activePhase?.id;
  const passedPlayerIds = new Set(rules?.enabled ? (rules.priorityPasses || []) : (tracker.passedPlayerIds || []));
  const passIsActive = passedPlayerIds.has(myPlayerId);
  const opponentPassIsActive = !isObserver && [...passedPlayerIds].some((playerId) => playerId !== myPlayerId);
  $("#phaseSequence").classList.toggle("advanced", tracker.advanced);
  $("#phaseSequence").innerHTML = PHASE_GROUPS.map((group) => {
    const active = group.id === activeGroupId;
    const groupSteps = group.sections.flatMap((section) => section.steps);
    const stepIndex = Math.max(0, groupSteps.findIndex((step) => step.id === activePhase?.id));
    const phaseDetail = active && tracker.advanced
      ? `${t(activePhase.label)} — ${t(activePhase.detail)}`
      : t(group.detail);
    return `<div class="phase-orb ${active ? "active" : ""} ${passIsActive && active ? "passed" : ""} ${opponentPassIsActive && active ? "opponent-passed" : ""}"
      data-phase-group="${esc(group.id)}" aria-current="${active ? "step" : "false"}">
      ${phaseIconSvg(group.id)}
      <span class="phase-orb-label">${esc(t(group.label))}</span>
      <span class="phase-orb-tooltip"><strong>${esc(t(group.label))}</strong>${active && tracker.advanced ? `<span>${esc(`${t("phaseStep")} ${stepIndex + 1}/${groupSteps.length} · ${t(activePhase.label)}`)}</span>` : ""}<span>${esc(phaseDetail)}</span></span>
    </div>`;
  }).join("");
  $("#phaseCurrentMain").textContent = t(activeGroup?.label || activePhase?.label || "");
  $("#phaseCurrentStep").textContent = tracker.advanced && activePhase ? t(activePhase.label) : "";
  wirePhasePassControls(panel);
}

function rulesPlayerName(playerId) {
  return latestState?.players?.[playerId]?.name || playerId || "—";
}

function rulesText(key, values = {}) {
  return String(t(key)).replace(/\{(\w+)\}/g, (_match, name) => values[name] ?? "");
}

function rulesActionDisplayLabel(action) {
  const cardId = action?.source?.cardId;
  if (!cardId) return t("rulesUnknownAction");
  if (action.kind === "triggered_effect") {
    return `${cardName(cardId)} — ${t("rulesKindTriggered")}`;
  }
  if (action.kind === "activated_effect") {
    return rulesText("rulesDefaultActivate", { card: cardName(cardId) });
  }
  if (action.kind === "play_card") {
    return rulesText(action.asSupport ? "rulesDefaultSupport" : "rulesDefaultPlay", {
      card: cardName(cardId),
    });
  }
  return cardName(cardId);
}

function rulesActionCardRef(cardId) {
  return `<span class="rules-card-ref" data-rules-card="${esc(cardId)}">${esc(cardName(cardId))}</span>`;
}

function rulesActionTargetRef(target) {
  if (target?.kind === "player") return esc(rulesPlayerName(target.playerId));
  const location = ["stack_action", "stack_effect"].includes(target?.kind)
    ? t("rulesStackTitle")
    : target?.kind === "zone_card"
    ? `${rulesPlayerName(target.containerId)} · ${t(target.zone)}`
    : rulesPlayerName(target.ownerId);
  return `${rulesActionCardRef(target.cardId)} (${esc(location)})`;
}

function rulesEssenceEntriesText(entries) {
  const totals = {};
  for (const entry of entries || []) totals[entry.temperament] = (totals[entry.temperament] || 0) + Number(entry.amount || 0);
  return Object.entries(totals)
    .map(([temperament, amount]) => `${esc(t(`temperament${temperament[0].toUpperCase()}${temperament.slice(1)}`))} ×${amount}`)
    .join(", ");
}

function rulesActionDetails(action) {
  const details = [];
  if (action.isStackCopy) details.push(`<span class="rules-stack-copy-state">${esc(t("rulesStackCopy"))}</span>`);
  if (action.source?.cardId) details.push(rulesActionCardRef(action.source.cardId));
  if (action.targets?.length) {
    details.push(`${esc(t("rulesTargetsShort"))}: ${action.targets.map(rulesActionTargetRef).join(", ")}`);
  }
  if (action.cost?.essenceSpent?.length) details.push(`${esc(t("rulesEssenceShort"))}: ${rulesEssenceEntriesText(action.cost.essenceSpent)}`);
  if (action.cost?.tributeCardIds?.length) {
    details.push(`${esc(t("rulesTributeShort"))}: ${action.cost.tributeCardIds.map(rulesActionCardRef).join(", ")}`);
  }
  if (action.cost?.excessEssence?.length) details.push(`${esc(t("rulesExcessShort"))}: ${rulesEssenceEntriesText(action.cost.excessEssence)}`);
  if (action.cost?.sourceExhausted) details.push(esc(t("rulesSourceExhaustedShort")));
  if (action.cost?.sourceSacrificed) details.push(esc(t("rulesSourceSacrificedShort")));
  return details.join(" · ");
}

function wireRulesStackCardRefs() {
  $$("#rulesStackPanel [data-rules-card]").forEach((element) => {
    const cardId = element.dataset.rulesCard;
    element.onmouseenter = () => showCardPreview(cardId, element);
    element.onmouseleave = hideCardPreview;
    element.onclick = () => showInspect(cardId);
  });
}

function renderRulesStack() {
  const panel = $("#rulesStackPanel");
  const rules = latestState?.rulesEngine;
  const visible = Boolean(rules?.enabled);
  panel.classList.toggle("hidden", !visible);
  if (!visible) return;

  const readyIds = new Set(rules.readyPlayerIds || []);
  const pregameActive = latestState?.phaseTracker?.turn === 1
    && currentPhaseUi().phase?.id === "recovery_start"
    && readyIds.size < 2;
  const playersReady = Object.keys(latestState?.players || {}).length >= 2 && !pregameActive;
  const priorityPlayerId = rules.priorityPlayerId;
  const pendingChoice = rules.pendingChoice;
  renderConfrontationSummary(rules);
  const firstManifestation = rulesFirstManifestationActive();
  const firstItemIds = rules.firstManifestationItemIds || {};
  const firstValidated = rules.firstManifestationValidatedPlayerIds || [];
  const mineHasFirstManifestation = Boolean(firstItemIds[myPlayerId]);
  const mineFirstValidated = firstValidated.includes(myPlayerId);
  const opponentFirstValidated = firstValidated.some((playerId) => playerId !== myPlayerId);
  const priorityPasses = rules.priorityPasses || [];
  const myPassActive = priorityPasses.includes(myPlayerId);
  const immediatePending = rulesImmediateEffectPendingClient();
  const myPriority = playersReady && !pendingChoice && !immediatePending && !firstManifestation && !isObserver && priorityPlayerId === myPlayerId;
  const canCancelPass = playersReady && !pendingChoice && !immediatePending && !isObserver && myPassActive;
  const stack = Array.isArray(rules.actionStack) ? rules.actionStack : [];
  const resolutionArmed = stack.length > 0 && priorityPasses.length > 0;
  if (!myPriority && !$("#rulesActionPanel").classList.contains("hidden")) closeRulesActionPanel();
  panel.classList.toggle("rules-stack-readonly", isObserver);
  const phaseLines = currentPhaseLines();
  const phaseContext = [
    `${t("turn")} ${latestState?.phaseTracker?.turn || 1}`,
    phaseLines.phase,
    phaseLines.step,
  ].filter(Boolean).join(" · ");
  $("#rulesTurnContext").textContent = phaseContext;
  $("#rulesTurnContext").title = phaseContext;
  const priority = $("#rulesPriority");
  priority.classList.toggle("waiting", firstManifestation || !playersReady || !priorityPlayerId || Boolean(pendingChoice) || immediatePending);
  priority.classList.toggle("is-mine", myPriority);
  priority.classList.toggle("is-passed", canCancelPass);
  priority.textContent = firstManifestation
    ? t(isObserver ? "rulesFirstManifestationObserver" : mineFirstValidated ? "rulesFirstManifestationWaiting" : "rulesFirstManifestationChoose")
    : pendingChoice
    ? (pendingChoice.playerId === myPlayerId ? t("rulesYourChoice") : rulesText("rulesWaitingChoice", { player: rulesPlayerName(pendingChoice.playerId) }))
    : immediatePending
    ? t("rulesImmediateResolving")
    : !playersReady || !priorityPlayerId
    ? t("rulesWaitingPlayers")
    : canCancelPass
      ? rulesText("rulesPriorityPassedSelf", { player: rulesPlayerName(priorityPlayerId) })
    : myPriority && stack.length
      ? t(resolutionArmed ? "rulesYourPriorityResolve" : "rulesYourPriorityRespond")
    : myPriority
      ? t("rulesYourPriority")
      : rulesText("rulesPriorityPlayer", { player: rulesPlayerName(priorityPlayerId) });

  panel.classList.toggle("hidden", stack.length === 0);
  const stackTitle = $("#rulesStackTitle");
  stackTitle.classList.toggle("hidden", stack.length === 0);
  stackTitle.textContent = `${t("rulesStackTitle")} · ${stack.length}`;
  $("#rulesStackBody").classList.toggle("hidden", stack.length === 0);
  panel.classList.toggle("has-actions", stack.length > 0);
  const responseSlot = myPriority
    ? `<li class="rules-stack-response-slot ${resolutionArmed ? "before-resolution" : ""}" aria-label="${esc(t(resolutionArmed ? "rulesStackRespondBeforeResolve" : "rulesStackRespondSlot"))}">
        <strong>${esc(t(resolutionArmed ? "rulesStackRespondBeforeResolve" : "rulesStackRespondSlot"))}</strong>
        <small>${esc(t("rulesStackResponseSlotHint"))}</small>
      </li>`
    : "";
  const stackActions = [...stack].reverse().map((action, index) => {
        const level = stack.length - index;
        const controller = rulesPlayerName(action.controllerId);
        let details = rulesActionDetails(action);
        const displayLabel = rulesActionDisplayLabel(action);
        const sourceCardId = action.source?.cardId;
        const paymentButton = action.neutralizePayment && myPriority && !pendingChoice && !isObserver
          ? `<button type="button" class="secondary" data-stack-payment="${esc(action.id)}">${esc(t("rulesPayToNeutralize"))}</button>` : "";
        details += paymentButton;
        const sourceCard = sourceCardId
          ? `<button type="button" class="rules-stack-card" data-rules-card="${esc(sourceCardId)}" aria-label="${esc(cardName(sourceCardId))}" title="${esc(cardName(sourceCardId))}"><img src="${esc(cardImage(sourceCardId))}" alt=""></button>`
          : "";
        const awaitingPayment = rules.pendingChoice?.kind === "stack_counter_payment"
          && rules.pendingChoice.targetActionId === action.id;
        const resolvesOnPass = index === 0 && myPriority && resolutionArmed;
        return `<li class="${awaitingPayment ? "rules-counter-payment-target " : ""}${resolvesOnPass ? "will-resolve" : ""}" data-stack-action-id="${esc(action.id)}" style="--stack-player-color:${esc(playerColor(action.controllerId))}" title="${esc(`${controller} — ${displayLabel}`)}">${sourceCard}<div class="rules-stack-copy"><div class="rules-stack-main"><span class="rules-stack-index">${index === 0 ? esc(t("rulesStackTop")) : `#${level}`}</span><strong>${esc(displayLabel)}</strong><small>${esc(controller)}</small></div>${awaitingPayment ? `<span class="rules-stack-payment-state">${esc(t("rulesStackPaymentPending"))}</span>` : ""}${details ? `<div class="rules-stack-detail">${details}</div>` : ""}</div>${resolvesOnPass ? `<span class="rules-stack-resolve-state">${esc(t("rulesStackResolveOnPass"))}</span>` : ""}</li>`;
      }).join("");
  $("#rulesStackList").innerHTML = responseSlot + stackActions;
  $$("#rulesStackList [data-stack-payment]").forEach((button) => {
    button.onclick = () => send({ type: "request_rules_stack_payment", actionId: button.dataset.stackPayment });
  });
  wireRulesStackCardRefs();

  const current = currentPhaseUi();
  const groupSteps = current.group.sections.flatMap((section) => section.steps);
  const currentStep = Math.max(0, groupSteps.findIndex((step) => step.id === current.phase.id)) + 1;
  const autoSkipBox = $("#rulesAutoSkip");
  $("#rulesAutoSkipLabel").textContent = t("rulesAutoSkipLabel");
  $("#rulesAutoSkipWrap").title = t("rulesAutoSkipHint");
  $("#rulesAutoSkipWrap").classList.toggle("hidden", isObserver);
  autoSkipBox.checked = rules.autoSkipPhases !== false
    && !(rules.autoSkipOffPlayerIds || []).includes(myPlayerId);
  const passAllLocked = !firstManifestation && rulesPassAllLocked();
  $("#passPriorityBtn").textContent = firstManifestation
    ? t(mineFirstValidated ? "rulesFirstManifestationLocked" : "rulesFirstManifestationValidate")
    : passAllLocked
    ? t("rulesPassAllLocked")
    : canCancelPass
    ? t("cancelPriorityPass")
    : stack.length && resolutionArmed
    ? rulesText("rulesResolveTop", { card: rulesActionDisplayLabel(stack[stack.length - 1]) })
    : stack.length
    ? t("rulesPassWithoutResponse")
    : rulesText("rulesPassStep", { current: currentStep, total: groupSteps.length });
  $("#passPriorityBtn").title = passAllLocked
    ? t("rulesPassAllLockedHint")
    : stack.length
    ? t(resolutionArmed ? "rulesResolveTopHint" : "rulesPassWithoutResponseHint")
    : t(current.phase.detail);
  $("#passPriorityBtn").classList.toggle("hidden", firstManifestation ? isObserver : (!myPriority && !canCancelPass && !passAllLocked));
  $("#passPriorityBtn").classList.toggle("pass-all-locked", passAllLocked);
  $("#passPriorityBtn").classList.toggle("passed", canCancelPass);
  $("#passPriorityBtn").classList.toggle("must-act", myPriority && !canCancelPass);
  $("#passPriorityBtn").classList.toggle("offers-response", myPriority && stack.length > 0 && !resolutionArmed);
  $("#passPriorityBtn").classList.toggle("resolves-stack", myPriority && resolutionArmed);
  $("#passPriorityBtn").classList.toggle("opponent-validated", firstManifestation && opponentFirstValidated && !mineFirstValidated);
  $("#passPriorityBtn").setAttribute("aria-pressed", String(canCancelPass));
  $("#passPriorityBtn").disabled = firstManifestation
    ? (!mineHasFirstManifestation || isObserver || mineFirstValidated)
    : (immediatePending || !myPriority && !canCancelPass && !passAllLocked);

  const firstPasser = priorityPasses[0];
  const hint = $("#rulesStackHint");
  hint.classList.toggle("hidden", !firstPasser || Boolean(pendingChoice));
  hint.textContent = firstPasser && !pendingChoice
    ? rulesText("rulesPriorityPassed", {
        player: rulesPlayerName(firstPasser),
        next: rulesPlayerName(priorityPlayerId),
      })
    : "";
}

function renderRulesPregame() {
  const panel = $("#rulesPregamePanel");
  const rules = latestState?.rulesEngine;
  const currentPhase = currentPhaseUi();
  const firstTurn = Boolean(!latestState?.ended && latestState?.phaseTracker?.turn === 1);
  const assistedOpeningWindow = firstTurn && currentPhase.phase?.id === "recovery_start";
  const assistedActive = Boolean(rules?.enabled && assistedOpeningWindow);
  const recoveryMulliganActive = rules_recovery_mulligan_active_client();
  const standardDeckSetup = standardDeckSetupActiveClient();
  const active = assistedActive || recoveryMulliganActive || standardDeckSetup;
  panel.classList.toggle("hidden", !active);
  panel.classList.remove("mulligan-required");
  $("#gameScreen").classList.toggle("rules-pregame-active", active);
  if (!active) return;

  if (standardDeckSetup) {
    const deckConfirmed = new Set(rules?.deckConfirmedPlayerIds || []);
    $("#rulesPregameTurn").textContent = t("rulesPregameTurn");
    $("#rulesPregameTitle").textContent = t("rulesDeckSetupTitle");
    $("#rulesPregameHint").textContent = t("rulesDeckSetupHint");
    $("#rulesPregamePlayers").innerHTML = Object.values(latestState.players || {}).map((player) => {
      const hasDeck = Boolean(player.deckDefinition);
      const isConfirmed = latestState.mode === "casual" ? deckConfirmed.has(player.id) : hasDeck;
      const statusKey = isConfirmed
        ? "rulesDeckConfirmedState"
        : (hasDeck ? "rulesDeckSelectedState" : "rulesDeckMissingState");
      return `<div class="rules-pregame-player ${isConfirmed ? "ready" : ""}">
        <span class="rules-pregame-player-mark" style="--player-tone:${esc(playerColor(player.id))}">${esc((player.name || "?").slice(0, 1).toUpperCase())}</span>
        <span><strong>${esc(player.name || player.id)}</strong><small>${esc(t(statusKey))}</small></span>
        <span class="rules-pregame-check" aria-hidden="true">${isConfirmed ? "✓" : ""}</span>
      </div>`;
    }).join("");
    $("#rulesPregameActions").classList.remove("hidden");
    $("#rulesPregameActions").classList.add("deck-stage");
    $("#rulesOpeningHandBtn").classList.remove("hidden");
    $("#rulesOpeningHandBtn").textContent = t("importDeck");
    $("#rulesOpeningHandBtn").dataset.action = "import";
    $("#rulesOpeningHandBtn").disabled = false;
    $("#rulesPregameMulliganBtn").classList.add("hidden");
    $("#rulesPregameReadyBtn").classList.add("hidden");
    return;
  }

  if (recoveryMulliganActive) {
    const required = new Set(rules.recoveryMulliganRequiredPlayerIds || []);
    const attempted = new Set(rules.recoveryMulliganPlayerIds || []);
    const failed = new Set(rules.recoveryMulliganFailedPlayerIds || []);
    const mineNeedsMulligan = required.has(myPlayerId);
    panel.classList.add("mulligan-required");
    $("#rulesPregameTurn").textContent = rulesText("rulesRecoveryTurn", {
      turn: latestState.phaseTracker.turn,
    });
    $("#rulesPregameTitle").textContent = t(mineNeedsMulligan
      ? "rulesRecoveryMulliganRequiredTitle"
      : "rulesRecoveryMulliganWaitingTitle");
    $("#rulesPregameHint").textContent = t(mineNeedsMulligan
      ? "rulesRecoveryMulliganRequiredHint"
      : "rulesRecoveryMulliganWaitingHint");
    $("#rulesPregamePlayers").innerHTML = Object.values(latestState.players || {}).map((player) => {
      const needsMulligan = required.has(player.id);
      const didMulligan = attempted.has(player.id);
      const didFail = failed.has(player.id);
      const checked = !needsMulligan && !didFail;
      const statusKey = didFail
        ? "rulesRecoveryMulliganFailedState"
        : needsMulligan
          ? "rulesRecoveryMulliganRequiredState"
          : didMulligan
            ? "rulesRecoveryMulliganValidatedState"
            : "rulesRecoveryPlayableState";
      return `<div class="rules-pregame-player ${checked ? "ready" : ""}${needsMulligan || didFail ? " attention" : ""}">
        <span class="rules-pregame-player-mark" style="--player-tone:${esc(playerColor(player.id))}">${esc((player.name || "?").slice(0, 1).toUpperCase())}</span>
        <span><strong>${esc(player.name || player.id)}</strong><small>${esc(t(statusKey))}</small></span>
        <span class="rules-pregame-check" aria-hidden="true">${checked ? "✓" : needsMulligan || didFail ? "!" : ""}</span>
      </div>`;
    }).join("");
    const controlsHidden = isObserver || !latestState.players?.[myPlayerId];
    const waitingForOpponent = required.size > 0 && !mineNeedsMulligan;
    $("#rulesPregameActions").classList.toggle("hidden", controlsHidden || (!mineNeedsMulligan && !waitingForOpponent));
    $("#rulesPregameActions").classList.remove("deck-stage");
    $("#rulesPregameActions").classList.add("mulligan-stage");
    $("#rulesOpeningHandBtn").classList.add("hidden");
    $("#rulesPregameMulliganBtn").classList.toggle("hidden", !mineNeedsMulligan && !waitingForOpponent);
    $("#rulesPregameMulliganBtn").textContent = t(mineNeedsMulligan
      ? "rulesRecoveryMulliganAction"
      : "rulesRecoveryMulliganWaitingAction");
    $("#rulesPregameMulliganBtn").disabled = !mineNeedsMulligan;
    $("#rulesPregameMulliganBtn").dataset.mulliganMode = "recovery";
    $("#rulesPregameReadyBtn").classList.add("hidden");
    return;
  }

  const opened = new Set(rules.openingHandPlayerIds || []);
  const mulliganed = new Set(rules.mulliganPlayerIds || []);
  const mulliganRequired = new Set(rules.openingMulliganRequiredPlayerIds || []);
  const mulliganFailed = new Set(rules.openingMulliganFailedPlayerIds || []);
  const ready = new Set(rules.readyPlayerIds || []);
  const deckConfirmed = new Set(rules.deckConfirmedPlayerIds || []);
  const playerIds = Object.keys(latestState.players || {});
  const decksReady = playerIds.length >= 2 && playerIds.every((playerId) => deckConfirmed.has(playerId));
  $("#rulesPregameTurn").textContent = t("rulesPregameTurn");
  const mineNeedsMulligan = mulliganRequired.has(myPlayerId);
  const mineOpened = opened.has(myPlayerId);
  const mineMulliganed = mulliganed.has(myPlayerId);
  const mineReady = ready.has(myPlayerId);
  const mineChoosingHand = decksReady && mineOpened && !mineNeedsMulligan && !mineReady;
  const openingPaused = decksReady && mulliganRequired.size > 0;
  panel.classList.toggle("mulligan-required", openingPaused);
  // tournament: decks locked, the opening hands wait for the organizer's start
  const awaitingOrganizer = decksReady && latestState.mode === "tournament" && latestState.tournament?.status === "lobby";
  $("#rulesPregameTitle").textContent = t(awaitingOrganizer
    ? "rulesTournamentStartWaitingTitle"
    : !decksReady
    ? "rulesDeckSetupTitle"
    : mineNeedsMulligan
      ? "rulesMulliganRequiredTitle"
      : mineChoosingHand
        ? "rulesOpeningChoiceTitle"
        : "rulesOpeningWaitingTitle");
  $("#rulesPregameHint").textContent = t(awaitingOrganizer
    ? "rulesTournamentStartWaitingHint"
    : !decksReady
    ? "rulesDeckSetupHint"
    : mineNeedsMulligan
      ? "rulesMulliganRequiredHint"
      : mineChoosingHand
        ? "rulesOpeningChoiceHint"
        : "rulesOpeningWaitingHint");
  $("#rulesPregamePlayers").innerHTML = Object.values(latestState.players || {}).map((player) => {
    const statusKey = !decksReady
      ? (deckConfirmed.has(player.id) ? "rulesDeckConfirmedState" : (player.deckDefinition ? "rulesDeckSelectedState" : "rulesDeckMissingState"))
      : mulliganFailed.has(player.id)
        ? "rulesMulliganFailedState"
        : mulliganRequired.has(player.id)
          ? "rulesMulliganRequiredState"
          : ready.has(player.id)
            ? (mulliganed.has(player.id) ? "rulesMulliganValidatedState" : "rulesOpeningPlayableState")
            : opened.has(player.id)
              ? "rulesOpeningChoosingState"
              : "rulesPregameWaitingState";
    const checked = decksReady ? ready.has(player.id) : deckConfirmed.has(player.id);
    const attention = mulliganRequired.has(player.id) || mulliganFailed.has(player.id);
    return `<div class="rules-pregame-player ${checked ? "ready" : ""}${attention ? " attention" : ""}">
      <span class="rules-pregame-player-mark" style="--player-tone:${esc(playerColor(player.id))}">${esc((player.name || "?").slice(0, 1).toUpperCase())}</span>
      <span><strong>${esc(player.name || player.id)}</strong><small>${esc(t(statusKey))}</small></span>
      <span class="rules-pregame-check" aria-hidden="true">${checked ? "✓" : attention ? "!" : ""}</span>
    </div>`;
  }).join("");

  const mineDeckConfirmed = deckConfirmed.has(myPlayerId);
  const mineHasDeck = Boolean(latestState.players?.[myPlayerId]?.deckDefinition);
  const opponentDeckConfirmed = playerIds.some((playerId) => playerId !== myPlayerId && deckConfirmed.has(playerId));
  const controlsHidden = isObserver || !latestState.players?.[myPlayerId];
  const canMulligan = decksReady && mineOpened && !mineMulliganed && !mineReady && !mulliganFailed.has(myPlayerId);
  const canKeepHand = decksReady && mineOpened && !mineNeedsMulligan && !mineReady && !mulliganFailed.has(myPlayerId);
  $("#rulesPregameActions").classList.toggle("hidden", controlsHidden || (decksReady && !canMulligan && !canKeepHand));
  $("#rulesPregameActions").classList.toggle("deck-stage", !decksReady);
  $("#rulesPregameActions").classList.toggle("mulligan-stage", decksReady);
  $("#rulesOpeningHandBtn").classList.toggle("hidden", decksReady);
  $("#rulesOpeningHandBtn").textContent = t("importDeck");
  $("#rulesOpeningHandBtn").dataset.action = "import";
  $("#rulesOpeningHandBtn").disabled = false;
  $("#rulesPregameMulliganBtn").classList.toggle("hidden", !canMulligan);
  $("#rulesPregameMulliganBtn").textContent = t(mineNeedsMulligan
    ? "rulesMulliganAction"
    : "rulesVoluntaryMulliganAction");
  $("#rulesPregameMulliganBtn").disabled = !canMulligan;
  $("#rulesPregameMulliganBtn").dataset.mulliganMode = "opening";
  $("#rulesPregameMulliganBtn").dataset.mulliganRequired = String(mineNeedsMulligan);
  $("#rulesPregameReadyBtn").classList.toggle("hidden", decksReady && !canKeepHand);
  $("#rulesPregameReadyBtn").textContent = decksReady
    ? t("rulesKeepOpeningHand")
    : (mineDeckConfirmed ? t("rulesCancelDeckValidation") : t("rulesValidateDeck"));
  $("#rulesPregameReadyBtn").disabled = decksReady ? !canKeepHand : !mineHasDeck;
  $("#rulesPregameReadyBtn").dataset.action = decksReady ? "opening" : "deck";
  $("#rulesPregameReadyBtn").classList.toggle("opponent-validated", !decksReady && opponentDeckConfirmed && !mineDeckConfirmed);
}
