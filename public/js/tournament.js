// Player log entries and the tournament console.
// Loaded before app.js: declarations only, nothing runs at load time.

function setMyActivity(activity) {
  if (myActivity === activity) return;
  myActivity = activity;
  send({ type: "set_activity", activity });
}

// The full action log (session.log) is comprehensive by design — it's the
// anti-cheat record, meant to be read by whoever's debugging a dispute, not
// glanced at mid-game. This is a much narrower, friendlier subset/format of
// the SAME underlying entries, limited to the handful of actions the user
// explicitly asked for: drew, discarded/moved a card, played, including a
// card leaving the battlefield straight into a pile.
const PLAYER_LOG_TYPES = new Set([
  "draw", "draw_to_limit", "opening_hand_draw", "move_card", "place_card", "remove_battlefield_item", "pass_phase",
  "rules_action_declared", "rules_action_triggered", "rules_priority_passed", "rules_priority_cancelled", "rules_priority_rolled", "rules_action_resolved", "rules_choice_resolved", "rules_phase_advanced", "rules_auto_passed", "rules_auto_skip_changed", "rules_pass_all_changed", "rules_confrontation_compared", "rules_confrontation_cleanup", "rules_field_zone_changed",
]);

function isPlayerLogRelevant(e) {
  if (!PLAYER_LOG_TYPES.has(e.type)) return false;
  // a synthetic token-card has no real identity at all — nothing to show
  return !(e.type === "remove_battlefield_item" && e.details && e.details.tokenCard);
}

// Cards that came from a private zone (e.g. what a scry decides to do with a
// card) often have no cardId in the log at all — that's the server's own
// privacy redaction, not a bug — but the EVENT itself ("put a card into X")
// is still worth showing, just with the identity withheld, the same way a
// face-down play already gets a generic "a face-down card" instead of being
// dropped from the feed entirely.
function namedOrUnknownCard(cardId) {
  return cardId
    ? `<span class="pl-card-name" data-pl-card="${esc(cardId)}">${esc(cardName(cardId))}</span>`
    : `<span class="pl-card-unknown">${esc(t("plAnUnknownCard"))}</span>`;
}

// Wires hover-preview + click-to-inspect on every card name a formatted
// player-log entry produced — called after inserting the HTML (both the
// opponent-row mini-feed and the full player-log panel use this).
function wirePlayerLogCardNames(container) {
  container.querySelectorAll("[data-pl-card]").forEach((el) => {
    const cardId = el.dataset.plCard;
    el.addEventListener("mouseenter", () => showCardPreview(cardId, el));
    el.addEventListener("mouseleave", hideCardPreview);
    el.addEventListener("click", (event) => {
      event.stopPropagation();
      showInspect(cardId);
    });
  });
}

function translateFor(key, language = currentLanguage) {
  return (ui[language] && ui[language][key]) ?? ui.en[key] ?? key;
}

function phaseLogLinesFor(details, language = currentLanguage) {
  const phaseId = details.phaseId || details.phase;
  const phase = ADVANCED_PHASES.find((item) => item.id === phaseId)
    || BASIC_PHASES.find((item) => item.id === phaseId)
    || BASIC_PHASES.find((item) => item.id === details.phase);
  if (!phase) return { phase: "", step: "" };
  const group = PHASE_GROUPS.find((item) => item.id === (phase.parent || phase.id));
  const phaseLabel = group ? translateFor(group.label, language) : translateFor(phase.label, language);
  if (!details.advancedMode || !phase.stepNumber) return { phase: phaseLabel, step: "" };
  const step = [phase.subphase ? translateFor(phase.subphase, language) : "", `${translateFor("phaseStep", language)} ${phase.stepNumber} — ${translateFor(phase.label, language)}`]
    .filter(Boolean)
    .join(" · ");
  return { phase: phaseLabel, step };
}

function phaseLogLines(details) {
  return phaseLogLinesFor(details, currentLanguage);
}

function localizeServerError(message) {
  const known = {
    "The tournament match has not started yet.": "tournamentNotStartedError",
    "The tournament match has ended.": "tournamentMatchEnded",
    "Tournament decks are locked once the match starts.": "tournamentDecksLocked",
    "You do not have priority.": "rulesNoPriorityError",
    "Both players must join before using priority.": "rulesNeedPlayersError",
    "Describe the action before adding it to the Stack.": "rulesDescribeActionError",
    "A Persistent Will cannot be played as a response.": "rulesPersistentResponseError",
    "An Ephemeral Will cannot be played during the current step.": "rulesEphemeralTimingError",
    "A Persistent Will can only be played during End actions.": "rulesPersistentTimingError",
    "This effect cannot be activated during the current step.": "rulesActivatedTimingError",
    "This card cannot be played as a Stack action during the current step.": "rulesCardTimingError",
    "This card cannot be played again until the end of the turn.": "rulesPlayRestrictedError",
    "The source card is not in your Hand.": "rulesSourceMovedError",
    "The source card is not on your side of the field.": "rulesSourceMovedError",
    "A card declared in the Stack cannot leave your Hand before it resolves.": "rulesSourceReservedError",
    "A selected Tribute card is no longer in your Hand.": "rulesTributeMovedError",
    "Only Manifestations from your Hand can be declared as Tribute here.": "rulesTributeTypeError",
    "A selected target is no longer face up on the battlefield.": "rulesTargetMovedError",
    "A selected target no longer matches the declared card.": "rulesTargetMovedError",
    "A selected card is no longer available on the Stack.": "rulesStackTargetMovedError",
    "A selected Stack target no longer matches the declared card.": "rulesStackTargetMovedError",
    "The targeted card is no longer on the Stack.": "rulesStackTargetMovedError",
    "A selected effect is no longer available on the Stack.": "rulesStackEffectTargetMovedError",
    "The targeted effect is no longer on the Stack.": "rulesStackEffectTargetMovedError",
    "The selected Manifestations do not pay the full printed Tribute.": "rulesTributeInsufficientError",
    "Choose a valid allocation for your Transcendent Essences.": "rulesWhitePaymentError",
    "This Tribute must use fewer Manifestations.": "rulesTributeRedundantError",
    "Choose the activated ability to put on the Stack.": "rulesAbilityRequiredError",
    "Unknown activated ability.": "rulesAbilityUnknownError",
    "Choose the played ability to put on the Stack.": "rulesPlayedAbilityRequiredError",
    "Unknown played ability.": "rulesPlayedAbilityUnknownError",
    "This effect requires a different type of Stack card.": "rulesStackCopyTypeError",
    "Choose whether to keep or replace the copied Will's target.": "rulesCopyChoiceError",
    "The copied Stack action is no longer available.": "rulesCopyMissingError",
    "Choose the required number of targets for this activated ability.": "rulesAbilityTargetCountError",
    "Choose the required number of targets for this effect.": "rulesAbilityTargetCountError",
    "This activated ability requires a different type of target.": "rulesAbilityTargetTypeError",
    "The source card is already exhausted.": "rulesAbilityExhaustedError",
    "Choose a valid player for this triggered effect.": "rulesTriggerPlayerTargetError",
    "A required card choice must be completed first.": "rulesChoicePendingError",
    "This card choice is no longer available.": "rulesChoiceExpiredError",
    "Choose the required number of cards.": "rulesChoiceCountError",
    "A selected card is no longer in your hand.": "rulesChoiceMovedError",
    "Order every simultaneous Stack action exactly once.": "rulesSimultaneousOrderError",
    "Immediate Effects must remain above other simultaneous actions.": "rulesImmediateOrderError",
    "Immediate Effects must resolve before another action can be declared.": "rulesImmediateResolving",
    "Immediate Effects must resolve before priority can be passed.": "rulesImmediateResolving",
    "Choose a valid Persist Manifestation.": "rulesPersistChoiceError",
    "A Persist Manifestation is no longer available.": "rulesPersistExpiredError",
    "Choose whether to return the remembered card.": "rulesMemoryReturnChoiceError",
    "This remembered effect is no longer available.": "rulesMemoryExpiredError",
    "This Chain effect cannot be declined.": "rulesChainMandatoryError",
    "Choose one Manifestation to Chain.": "rulesChainChoiceError",
    "The selected Manifestation is no longer in the required zone.": "rulesChainMovedError",
    "Only a Manifestation can be Chained.": "rulesChainTypeError",
    "This Manifestation can only be played as a Persistent Will and cannot be Chained.": "rulesChainPersistentOnlyError",
    "Choose a valid confrontation destination.": "rulesConfrontationDestinationError",
    "This confrontation card is no longer available.": "rulesConfrontationCardMovedError",
    "Choose a valid Interzone card to replace.": "rulesConfrontationReplacementError",
    "This Interzone choice is no longer available.": "rulesConfrontationReplacementMovedError",
    "Opening hands can only be drawn during the first Recovery start step.": "rulesOpeningHandStepError",
    "You have already drawn your opening hand.": "rulesOpeningHandAlreadyError",
    "Finish the opening-hand setup before playing.": "rulesPregameFinishError",
    "Draw your opening hand before taking a mulligan.": "rulesPregameDrawBeforeMulliganError",
    "Draw your opening hand before confirming readiness.": "rulesPregameDrawBeforeReadyError",
    "You have already taken your opening mulligan.": "rulesPregameMulliganUsedError",
    "You are already ready and cannot change your opening hand.": "rulesPregameAlreadyReadyError",
    "You are already ready.": "rulesPregameAlreadyReadyError",
    "Mulligans are only available before both players are ready.": "rulesPregameFinishError",
    "The opening-hand setup is no longer active.": "rulesPregameFinishError",
    "Both players must join before confirming readiness.": "rulesNeedPlayersError",
    "Your opening hand already contains a playable Manifestation.": "rulesMulliganNotRequiredError",
    "Opening-hand readiness is automatic.": "rulesOpeningAutomaticError",
    "Complete the required Recovery Mulligan before playing.": "rulesRecoveryMulliganPendingError",
    "No Recovery Mulligan is currently required.": "rulesRecoveryMulliganUnavailableError",
    "Your Recovery hand already contains a playable Manifestation.": "rulesRecoveryMulliganNotRequiredError",
    "Choose a valid Recovery effect.": "rulesRecoveryChoiceInvalidError",
    "Your Deck no longer has three cards to discard.": "rulesRecoveryChoiceShortDeckError",
    "This card did not meet its beginning-of-turn play condition.": "rulesPlayConditionError",
    "This card is no longer in its required zone.": "rulesRequiredZoneError",
    "This card can only be played in Support during a confrontation.": "rulesSupportTimingError",
    "A Support Manifestation can only be played from Hand during Reaction.": "rulesSupportHandTimingError",
    "This Manifestation does not have Support from Hand.": "rulesSupportHandMissingError",
    "This Manifestation does not currently have Support.": "rulesSupportMissingError",
  };
  return known[message] ? t(known[message]) : message;
}

function showTournamentPlayerAlert(message, isError = false) {
  const alert = $("#tournamentPlayerAlert");
  $("#tournamentPlayerAlertText").textContent = message;
  alert.classList.toggle("error", isError);
  alert.classList.remove("hidden");
  if (tournamentAlertTimer) clearTimeout(tournamentAlertTimer);
  tournamentAlertTimer = setTimeout(() => alert.classList.add("hidden"), 5200);
}

function tournamentStatusLabel(status) {
  return t(status === "active" ? "statusActive" : status === "ended" ? "statusEnded" : "statusLobby");
}

function tournamentPhaseLabel(phaseId) {
  return phaseLogLines({ phase: phaseId }).phase || phaseId || "—";
}

function tournamentRoleIcon(role) {
  if (role === "spectator") return `<svg viewBox="0 0 24 24"><path d="M3 12s3.5-5 9-5 9 5 9 5-3.5 5-9 5-9-5-9-5Z"/><circle cx="12" cy="12" r="2.5"/></svg>`;
  if (role === "judge") return `<svg viewBox="0 0 24 24"><path d="M12 3v17M6 6h12M4 20h16M7 6l-3 6h6L7 6Zm10 0-3 6h6l-3-6Z"/></svg>`;
  return `<svg viewBox="0 0 24 24"><circle cx="12" cy="7" r="3"/><path d="M6 20c.5-5 2.5-7 6-7s5.5 2 6 7"/></svg>`;
}

function tournamentLogTone(entry) {
  if (entry.type === "search_without_shuffle") return "critical";
  if (["rules_opening_defeat", "rules_recovery_defeat"].includes(entry.type)) return "critical";
  if (entry.type === "search_zone") return "warning";
  if (["rules_opening_mulligan_required", "rules_recovery_mulligan_required"].includes(entry.type)) return "warning";
  if (["create_tournament", "role_joined", "start_tournament", "end_tournament", "update_tournament_policy"].includes(entry.type)) return "system";
  if (["shuffle", "search_followed_by_shuffle", "draw", "draw_to_limit", "opening_hand_draw", "place_card", "move_card", "reveal", "scry", "mulligan", "rules_action_declared", "rules_action_triggered", "rules_priority_passed", "rules_priority_cancelled", "rules_priority_rolled", "rules_action_resolved", "rules_choice_resolved", "rules_phase_advanced", "rules_auto_passed", "rules_auto_skip_changed", "rules_pass_all_changed", "rules_confrontation_compared", "rules_confrontation_cleanup", "rules_field_zone_changed"].includes(entry.type)) return "action";
  return "info";
}

function tournamentCardLabel(cardId) {
  const card = cardsById.get(cardId);
  return card ? `${String(card.collectionNumber || "").padStart(3, "0")} — ${cardName(cardId)}` : cardId;
}

function resolveTournamentCard(value) {
  const normalized = String(value || "").trim();
  const numberMatch = normalized.match(/^#?(\d{1,3})/);
  if (numberMatch) return cardsByNumber.get(Number(numberMatch[1]))?.id || null;
  const lower = normalized.toLocaleLowerCase();
  return [...cardsById.values()].find((card) => card.id === normalized || cardName(card.id).toLocaleLowerCase() === lower)?.id || null;
}

function tournamentRuleChip(cardId, removeAttrs) {
  return `<span class="tournament-rule-chip"><span>${esc(tournamentCardLabel(cardId))}</span><button type="button" ${removeAttrs} aria-label="${esc(`${t("remove")} ${cardName(cardId)}`)}">×</button></span>`;
}

function defaultHomeDeckPolicy() {
  return {
    bannedCardIds: [82, 128, 86].map((number) => cardsByNumber.get(number)?.id).filter(Boolean),
    restrictedGroups: [{
      id: "opening-tutors",
      name: "Opening tutors",
      cardIds: [267, 284, 281].map((number) => cardsByNumber.get(number)?.id).filter(Boolean),
    }],
  };
}

function renderHomeDeckPolicy() {
  if (!homePolicyDraft) homePolicyDraft = defaultHomeDeckPolicy();
  $("#tournamentCardOptions").innerHTML = [...cardsById.values()]
    .sort((a, b) => Number(a.collectionNumber) - Number(b.collectionNumber))
    .map((card) => `<option value="${esc(`${String(card.collectionNumber).padStart(3, "0")} — ${cardName(card.id)}`)}"></option>`)
    .join("");
  $("#homeBannedCardsList").innerHTML = homePolicyDraft.bannedCardIds
    .map((cardId, index) => tournamentRuleChip(cardId, `data-home-remove-banned="${index}"`)).join("");
  $("#homeRestrictedGroups").innerHTML = homePolicyDraft.restrictedGroups.map((group, groupIndex) => `
    <section class="restricted-group">
      <div class="restricted-group-head"><input value="${esc(group.name || `${t("restrictedGroup")} ${groupIndex + 1}`)}" data-home-restricted-name="${groupIndex}" aria-label="${esc(t("restrictedGroupName"))}"><button type="button" data-home-remove-group="${groupIndex}">${esc(t("remove"))}</button></div>
      <div class="tournament-rule-chips">${(group.cardIds || []).map((cardId, cardIndex) => tournamentRuleChip(cardId, `data-home-remove-card="${groupIndex}:${cardIndex}"`)).join("")}</div>
      <div class="tournament-rule-add"><input data-home-card-input="${groupIndex}" list="tournamentCardOptions" placeholder="${esc(t("cardNameOrNumber"))}"><button type="button" data-home-add-card="${groupIndex}">${esc(t("add"))}</button></div>
    </section>`).join("");
  $$('[data-home-remove-banned]').forEach((button) => button.onclick = () => {
    homePolicyDraft.bannedCardIds.splice(Number(button.dataset.homeRemoveBanned), 1);
    renderHomeDeckPolicy();
  });
  $$('[data-home-restricted-name]').forEach((input) => input.oninput = () => {
    homePolicyDraft.restrictedGroups[Number(input.dataset.homeRestrictedName)].name = input.value;
  });
  $$('[data-home-remove-group]').forEach((button) => button.onclick = () => {
    homePolicyDraft.restrictedGroups.splice(Number(button.dataset.homeRemoveGroup), 1);
    renderHomeDeckPolicy();
  });
  $$('[data-home-remove-card]').forEach((button) => button.onclick = () => {
    const [groupIndex, cardIndex] = button.dataset.homeRemoveCard.split(":").map(Number);
    homePolicyDraft.restrictedGroups[groupIndex].cardIds.splice(cardIndex, 1);
    renderHomeDeckPolicy();
  });
  $$('[data-home-add-card]').forEach((button) => button.onclick = () => {
    const groupIndex = Number(button.dataset.homeAddCard);
    const input = $(`[data-home-card-input="${groupIndex}"]`);
    const cardId = resolveTournamentCard(input.value);
    if (!cardId) return showToast(t("unknownCard"), true);
    if (!homePolicyDraft.restrictedGroups[groupIndex].cardIds.includes(cardId)) homePolicyDraft.restrictedGroups[groupIndex].cardIds.push(cardId);
    renderHomeDeckPolicy();
  });
}

function renderTournamentRules(tournament, organizer) {
  const panel = $("#tournamentRulesPanel");
  panel.classList.toggle("hidden", !organizer);
  if (!organizer) return;
  if (!tournamentPolicyDraft || !tournamentPolicyDirty) {
    tournamentPolicyDraft = JSON.parse(JSON.stringify(tournament.policy || { bannedCardIds: [], restrictedGroups: [] }));
  }
  $("#tournamentCardOptions").innerHTML = [...cardsById.values()]
    .sort((a, b) => Number(a.collectionNumber) - Number(b.collectionNumber))
    .map((card) => `<option value="${esc(`${String(card.collectionNumber).padStart(3, "0")} — ${cardName(card.id)}`)}"></option>`)
    .join("");
  $("#bannedCardsList").innerHTML = tournamentPolicyDraft.bannedCardIds.map((cardId, index) => tournamentRuleChip(cardId, `data-remove-banned="${index}"`)).join("");
  $("#restrictedGroups").innerHTML = tournamentPolicyDraft.restrictedGroups.map((group, groupIndex) => `
    <section class="restricted-group">
      <div class="restricted-group-head"><input value="${esc(group.name || `${t("restrictedGroup")} ${groupIndex + 1}`)}" data-restricted-name="${groupIndex}" aria-label="${esc(t("restrictedGroupName"))}"><button type="button" data-remove-restricted-group="${groupIndex}">${esc(t("remove"))}</button></div>
      <div class="tournament-rule-chips">${(group.cardIds || []).map((cardId, cardIndex) => tournamentRuleChip(cardId, `data-remove-restricted-card="${groupIndex}:${cardIndex}"`)).join("")}</div>
      <div class="tournament-rule-add"><input data-restricted-card-input="${groupIndex}" list="tournamentCardOptions" placeholder="${esc(t("cardNameOrNumber"))}"><button type="button" data-add-restricted-card="${groupIndex}">${esc(t("add"))}</button></div>
    </section>`).join("");

  $$('[data-remove-banned]').forEach((button) => button.onclick = () => {
    tournamentPolicyDraft.bannedCardIds.splice(Number(button.dataset.removeBanned), 1);
    tournamentPolicyDirty = true;
    renderTournamentRules(tournament, organizer);
  });
  $$('[data-restricted-name]').forEach((input) => input.oninput = () => {
    tournamentPolicyDraft.restrictedGroups[Number(input.dataset.restrictedName)].name = input.value;
    tournamentPolicyDirty = true;
  });
  $$('[data-remove-restricted-group]').forEach((button) => button.onclick = () => {
    tournamentPolicyDraft.restrictedGroups.splice(Number(button.dataset.removeRestrictedGroup), 1);
    tournamentPolicyDirty = true;
    renderTournamentRules(tournament, organizer);
  });
  $$('[data-remove-restricted-card]').forEach((button) => button.onclick = () => {
    const [groupIndex, cardIndex] = button.dataset.removeRestrictedCard.split(":").map(Number);
    tournamentPolicyDraft.restrictedGroups[groupIndex].cardIds.splice(cardIndex, 1);
    tournamentPolicyDirty = true;
    renderTournamentRules(tournament, organizer);
  });
  $$('[data-add-restricted-card]').forEach((button) => button.onclick = () => {
    const groupIndex = Number(button.dataset.addRestrictedCard);
    const input = $(`[data-restricted-card-input="${groupIndex}"]`);
    const cardId = resolveTournamentCard(input.value);
    if (!cardId) return showToast(t("unknownCard"), true);
    const group = tournamentPolicyDraft.restrictedGroups[groupIndex];
    if (!group.cardIds.includes(cardId)) group.cardIds.push(cardId);
    tournamentPolicyDirty = true;
    renderTournamentRules(tournament, organizer);
  });
  $("#tournamentRulesSaveBtn").disabled = tournament.status !== "lobby" || !tournamentPolicyDirty;
  $("#tournamentRulesStatus").textContent = tournament.status === "lobby" ? (tournamentPolicyDirty ? t("unsavedRules") : t("rulesSaved")) : t("rulesLocked");
}

function renderTournamentConsole() {
  const consoleScreen = $("#tournamentScreen");
  if (!consoleScreen || !latestState?.tournament) return;
  const tournament = latestState.tournament;
  const roleKey = connectionRole === "judge" ? "judge" : "organizer";
  $("#tournamentRoleLabel").textContent = t(roleKey);
  const stateBadge = $("#tournamentStateBadge");
  stateBadge.textContent = tournamentStatusLabel(tournament.status);
  stateBadge.className = `tournament-state-badge ${tournament.status}`;

  const organizer = connectionRole === "organizer";
  $("#tournamentCodeSection").classList.toggle("hidden", !organizer);
  $("#tournamentActions").classList.remove("hidden");
  $$(".organizer-only").forEach((element) => element.classList.toggle("hidden", !organizer));
  if (organizer && tournamentCodes) {
    const accessRoles = [
      ["player1", "playerOneCode", "playerAccessPermission", "#d3654a"],
      ["player2", "playerTwoCode", "playerAccessPermission", "#3fc9a8"],
      ["spectator", "spectatorCode", "spectatorAccessPermission", "#8bb5d8"],
      ["judge", "judgeCode", "judgeAccessPermission", "#d3a942"],
    ];
    $("#tournamentCodeGrid").innerHTML = accessRoles.map(([key, label, permission, accent]) => `
      <article class="tournament-access-card role-${key}" style="--access-accent:${accent}">
        <div class="tournament-access-head"><span class="tournament-role-icon">${tournamentRoleIcon(key)}</span><span class="tournament-access-label">${esc(t(label))}</span></div>
        <p class="tournament-access-permission">${esc(t(permission))}</p>
        <div class="tournament-access-row"><strong class="tournament-access-code">${esc(tournamentCodes[key])}</strong><button class="tournament-access-copy" data-tournament-copy="${esc(tournamentCodes[key])}" title="${esc(t("copy"))}" aria-label="${esc(`${t("copy")} ${t(label)}`)}">${esc(t("copy"))}</button></div>
      </article>`).join("");
    $$('[data-tournament-copy]').forEach((button) => {
      button.onclick = () => {
        navigator.clipboard?.writeText(button.dataset.tournamentCopy);
        button.textContent = t("copied");
        setTimeout(() => (button.textContent = t("copy")), 1200);
      };
    });
  }

  $("#tournamentSeats").innerHTML = tournament.seats.map((seat) => `
    <article class="tournament-seat">
      <span class="tournament-seat-number">P${seat.seat + 1}</span>
      <div class="tournament-seat-name"><strong>${esc(seat.name || t("seatAvailable"))}</strong><span>${esc(seat.deckReady ? t("deckReadyShort") : seat.name ? (seat.deckError || t("deckMissing")) : t("waitingForPlayer"))}</span></div>
      <span class="connection-dot${seat.connected ? " connected" : ""}" title="${esc(t(seat.connected ? "connected" : "disconnected"))}"></span>
    </article>`).join("");

  const counts = latestState.roleCounts || {};
  const phase = latestState.phaseTracker || { turn: 1 };
  const currentPhaseId = currentPhaseUi(phase).phase?.id || "recovery";
  $("#tournamentMetrics").innerHTML = `
    <button class="tournament-metric" data-presence-role="spectator" aria-expanded="${openPresenceRole === "spectator"}"><strong>${Number(counts.spectator || 0)}</strong><span>${esc(t("spectators"))}</span></button>
    <button class="tournament-metric" data-presence-role="judge" aria-expanded="${openPresenceRole === "judge"}"><strong>${Number(counts.judge || 0)}</strong><span>${esc(t("judges"))}</span></button>
    <div class="tournament-metric"><strong>${Number(phase.turn || 1)}</strong><span>${esc(t("turn"))}</span></div>
    <div class="tournament-metric"><strong>${esc(tournamentPhaseLabel(currentPhaseId))}</strong><span>${esc(t("phaseCurrent"))}</span></div>`;
  $$('[data-presence-role]').forEach((button) => button.onclick = () => {
    openPresenceRole = openPresenceRole === button.dataset.presenceRole ? null : button.dataset.presenceRole;
    renderTournamentConsole();
  });
  const presenceList = $("#tournamentPresenceList");
  const presenceNames = openPresenceRole ? (latestState.roleParticipants?.[openPresenceRole] || []) : [];
  presenceList.classList.toggle("hidden", !openPresenceRole);
  if (openPresenceRole) presenceList.innerHTML = `<strong>${esc(t(openPresenceRole === "judge" ? "connectedJudges" : "connectedSpectators"))}</strong>${presenceNames.length ? `<ul>${presenceNames.map((name) => `<li>${esc(name)}</li>`).join("")}</ul>` : `<p>${esc(t("nobodyConnected"))}</p>`}`;

  const activeAlerts = (tournament.auditAlerts || []).filter((alert) => alert.status !== "resolved");
  $("#tournamentAuditAlerts").innerHTML = activeAlerts.map((alert) => `<div class="tournament-alert-chip ${alert.severity === "critical" ? "" : "warning"}">${esc(alert.severity === "critical" ? t("unshuffledSearchAlert") : t("pendingShuffleAlert")).replace("{player}", esc(alert.actorName))}</div>`).join("");

  const canStart = tournament.status === "lobby" && tournament.seats.every((seat) => seat.connected && seat.deckReady);
  $("#tournamentStartBtn").disabled = !canStart;
  $("#tournamentStartBtn").classList.toggle("hidden", tournament.status !== "lobby");
  $("#tournamentEndBtn").disabled = tournament.status === "ended";
  $("#tournamentEndBtn").classList.toggle("hidden", tournament.status === "ended");
  $("#tournamentViewMatchBtn").disabled = tournament.status === "lobby";
  renderTournamentRules(tournament, organizer);

  const entries = latestState.recentLog || [];
  $("#tournamentLiveLog").innerHTML = entries.length ? [...entries].reverse().map((entry) => `
    <article class="tournament-log-entry" data-tone="${tournamentLogTone(entry)}">
      <div class="tournament-log-sequence">#${String(entry.sequence || 0).padStart(3, "0")}</div>
      <div class="tournament-log-content"><p>${formatLogEntry(entry, { html: true })}</p><small>${new Date(entry.timestamp * 1000).toLocaleTimeString()} · ${esc(t("turn"))} ${entry.turn || 1} · ${esc(tournamentPhaseLabel(entry.phase))}</small></div>
    </article>`).join("") : `<div class="tournament-log-empty">${esc(t("logEmpty"))}</div>`;
  wireLogCardNames($("#tournamentLiveLog"));
}

function phaseLogLabel(details) {
  const lines = phaseLogLines(details);
  return [lines.phase, lines.step].filter(Boolean).join("\n");
}

// Returns safe HTML (the actor's name is colour-coded), not plain text — the
// caller must NOT re-escape the result, only insert it directly.
function formatPlayerLogEntry(e) {
  const who = `<b style="color:${playerColor(e.actorId)}">${esc(e.actorName || e.actorId || "?")}</b>`;
  const d = e.details || {};
  switch (e.type) {
    case "draw":
    case "draw_to_limit":
    case "opening_hand_draw":
      return `${who} ${esc(t("plDrew"))} ${d.count}`;
    case "rules_opening_mulligan_required":
      return `${who} ${esc(t("rulesMulliganRequiredState"))}`;
    case "rules_recovery_mulligan_required":
      return `${who} ${esc(t("rulesRecoveryMulliganRequiredState"))}`;
    case "rules_opening_defeat":
      return d.draw ? esc(t("rulesOpeningMulliganDraw")) : `${who} ${esc(t("rulesMulliganFailedState"))}`;
    case "rules_recovery_defeat":
      return d.draw ? esc(t("rulesRecoveryMulliganDraw")) : `${who} ${esc(t("rulesRecoveryMulliganFailedState"))}`;
    case "rules_recovery_resumed":
      return `${who} ${esc(t("rulesRecoveryMulliganValidatedState"))}`;
    case "place_card":
      if (d.asSupport) return `${who} ${esc(t("plPlayedInSupport"))} ${namedOrUnknownCard(d.cardId)}`;
      return d.faceUp ? `${who} ${esc(t("plPlayed"))} ${namedOrUnknownCard(d.cardId)}` : `${who} ${esc(t("plPlayedFaceDown"))}`;
    case "move_card":
      return d.toZone === "graveyard"
        ? `${who} ${esc(t("plDiscarded"))} ${namedOrUnknownCard(d.cardId)} (${esc(t("plFrom"))} ${esc(t(d.fromZone))})`
        : `${who} ${esc(t("plPutInto"))} ${namedOrUnknownCard(d.cardId)} → ${esc(t(d.toZone))}`;
    case "remove_battlefield_item":
      return d.toZone === "graveyard"
        ? `${who} ${esc(t("plDiscarded"))} ${namedOrUnknownCard(d.cardId)} (${esc(t("plFrom"))} ${esc(t("battlefield"))})`
        : `${who} ${esc(t("plPutInto"))} ${namedOrUnknownCard(d.cardId)} → ${esc(t(d.toZone))}`;
    case "pass_phase": {
      if (d.action === "cancelled") return `${who} ${esc(t("plCancelledPhasePass"))}`;
      const lines = phaseLogLines(d);
      const step = lines.step ? `<br><span class="phase-log-step">${esc(lines.step)}</span>` : "";
      return d.action === "advanced"
        ? `${who} ${esc(t("plAdvancedPhase"))} ${esc(lines.phase)}${step}`
        : `${who} ${esc(t("plPassedPhase"))}${lines.phase ? ` — ${esc(lines.phase)}` : ""}${step}`;
    }
    case "rules_action_declared":
      // the card's name in the reader's language (the engine's label is English)
      return `${who} ${esc(t("plDeclaredStackAction"))} ${d.source?.cardId ? namedOrUnknownCard(d.source.cardId) : esc(d.label || "")}`;
    case "rules_action_triggered":
      return `${who} ${esc(t("plDeclaredStackAction"))} ${namedOrUnknownCard(d.source?.cardId)}${d.targets?.[0]?.kind === "player" ? ` → ${esc(rulesPlayerName(d.targets[0].playerId))}` : ""}`;
    case "rules_priority_passed":
      return `${who} ${esc(t("plPassedPriority"))}`;
    case "rules_priority_cancelled":
      return `${who} ${esc(t("plCancelledPriority"))}`;
    case "rules_action_resolved":
      return d.effectResult?.kind === "neutralize_stack_action" && d.effectResult.status === "neutralized"
        ? `${who} ${esc(t("plNeutralizedStackCard"))} ${namedOrUnknownCard(d.effectResult.cardId)}`
        : `${who} ${esc(t("plResolvedStackAction"))} ${d.source?.cardId ? namedOrUnknownCard(d.source.cardId) : esc(d.label || "")}${rulesRollLogText(d.effectResult) ? ` — ${esc(rulesRollLogText(d.effectResult))}` : ""}${rulesTopRevealLogHtml(d.effectResult)}`;
    case "rules_choice_resolved":
      if (d.kind === "stack_copy_targets") {
        return `${who} ${esc(t("plCopiedStackWill"))} ${namedOrUnknownCard(d.targetCardId)}`;
      }
      if (d.kind === "stack_counter_payment") {
        if (d.status === "paid") return `${who} ${esc(t("plPaidStackCounter"))} ${namedOrUnknownCard(d.targetCardId)}`;
        if (d.status === "cancelled") return `${who} ${esc(t("plLetStackEffectCancel"))} ${namedOrUnknownCard(d.targetCardId)}`;
        if (d.status === "neutralized") return `${who} ${esc(t("plLetStackCardNeutralize"))} ${namedOrUnknownCard(d.targetCardId)}`;
        return `${who} ${esc(t("plStackTargetGone"))} ${namedOrUnknownCard(d.targetCardId)}`;
      }
      if (d.kind === "chain_manifestation") {
        if (d.status === "declined") return `${who} ${esc(t("plRulesChainDeclined"))} ${namedOrUnknownCard(d.sourceCardId)}`;
        if (d.status === "chained") return `${who} ${esc(t("plRulesChained"))} ${namedOrUnknownCard(d.cardId)} ${esc(t("plRulesChainFrom"))} ${namedOrUnknownCard(d.sourceCardId)}`;
      }
      if (d.kind === "confrontation_destination") return `${who} ${esc(t("plChoseConfrontationDestination"))} ${namedOrUnknownCard(d.cardId)} → ${esc(t(d.destination === "interzone" ? "interzone" : "rulesDeckBottom"))}`;
      if (d.kind === "confrontation_replace_interzone") return `${who} ${esc(t("plReplacedInterzoneCard"))} ${namedOrUnknownCard(d.replacedCardId)} → ${esc(t("rulesDeckBottom"))}`;
      if (d.kind === "recovery_shared_choice") return d.option === "lose_points_10"
        ? `${who} ${esc(t("plRecoveryLostPoints"))}`
        : `${who} ${esc(rulesText("plRecoveryDiscardedDeck", { count: d.count || 0 }))}`;
      return `${who} ${esc(t("plDiscarded"))} ${namedOrUnknownCard(d.cardIds?.[0])}`;
    case "rules_confrontation_compared": {
      const totals = Object.entries(d.totals || {}).map(([id, value]) => `${esc(rulesPlayerName(id))} ${value}`).join(" · ");
      return d.stalemate
        ? `${esc(t("rulesConfrontationStalemate"))} · ${totals}`
        : `${esc(rulesText("rulesConfrontationWinner", { player: rulesPlayerName(d.winnerId) }))} · ${totals}`;
    }
    case "rules_confrontation_cleanup":
      if (d.stalemate) return esc(t("plMovedToStalemate"));
      return [
        `${esc(t("plConfrontationCardsMoved"))} ${esc(rulesPlayerName(d.winnerId))}`,
        d.supportExiled?.length ? esc(t("plSupportWinnerExiled")) : "",
        ...(d.supportResolved || []).filter((result) => result.kind === "opponent_vessel_score").map((result) => (
          esc(rulesText("plSupportVesselScore", {
            player: rulesPlayerName(result.playerId), delta: result.delta, score: result.score,
          }))
        )),
        ...(d.supportResolved || []).filter((result) => result.kind === "opponent_vessel").map((result) => (
          esc(rulesText("plRulesSupportOpponentVessel", { player: rulesPlayerName(result.playerId) }))
        )),
      ].filter(Boolean).join(" · ");
    case "rules_field_zone_changed":
      return `${who} ${esc(t("plEnteredConfrontation"))} ${namedOrUnknownCard(d.cardId)}`;
    case "rules_phase_advanced": {
      const lines = phaseLogLines(d);
      const step = lines.step ? `<br><span class="phase-log-step">${esc(lines.step)}</span>` : "";
      return `${who} ${esc(t("plAdvancedPhase"))} ${esc(lines.phase)}${step}`;
    }
    default:
      return "";
  }
}

let pendingPlayerLogFor = null;

function openPlayerLog(playerId) {
  pendingPlayerLogFor = playerId;
  send({ type: "request_log" });
}

function renderPlayerLog(entries, playerId) {
  const player = latestState.players[playerId];
  $("#playerLogHeading").textContent = player ? player.name : t("logHeader");
  const relevant = entries.filter((e) => e.actorId === playerId && isPlayerLogRelevant(e));
  $("#playerLogEntries").innerHTML = relevant.length
    ? relevant.map((e) => `<div class="log-entry"><div class="t">${new Date(e.timestamp * 1000).toLocaleString()}</div><div class="what">${formatPlayerLogEntry(e)}</div></div>`).join("")
    : `<p>${esc(t("logEmpty"))}</p>`;
  wirePlayerLogCardNames($("#playerLogEntries"));
  $("#playerLogPanel").classList.remove("hidden");
}

// Which players' mini activity feed is currently collapsed down to just its
// controls (the ▸/▾ toggle + the ··· button) — a per-player choice so an
// observer watching several players can collapse only the noisy ones.
const recentLogCollapsed = new Set();

let opponentHandHiddenByUser = false;
