// Building rules action drafts: playability, Limbo play, payment and the action panel.
// Loaded before app.js: declarations only, nothing runs at load time.

// "As an additional cost ... reveal and exile a manifestation from your hand" (Censor, Martyrize)
// or "discard a Will" (Timid Brain): without such a card in hand, the card cannot be played.
function rulesAdditionalCostAvailableClient(draft, selected = []) {
  const kind = draft?.encodedAbility?.additionalCost;
  if (!["exile_hand_manifestation", "discard_hand_will"].includes(kind)) return true;
  const hand = [...(latestState?.players?.[myPlayerId]?.zones?.hand?.cards || [])];
  const sourceIndex = !draft.source || draft.source.zone === "hand" ? hand.indexOf(draft.card?.id) : -1;
  if (sourceIndex >= 0) hand.splice(sourceIndex, 1);
  for (const candidate of selected.filter((entry) => entry.zone === "hand")) {
    const index = hand.indexOf(candidate.cardId);
    if (index >= 0) hand.splice(index, 1);
  }
  const costTypes = kind === "discard_hand_will" ? ["ephemeral_will", "persistent_will"] : ["manifestation"];
  return hand.some((cardId) => costTypes.includes(cardsById.get(cardId)?.type));
}

function rulesTributeSelectionAvailableClient(draft, selected, complete = true) {
  const tributes = selected.filter((entry) => !entry.sacrifice);
  if (tributes.length > 7) return false;
  if (tributes.filter((entry) => entry.usesFormula).length > Number(draft.limboTributeBudget || 0)) return false;
  const sacrifices = selected.filter((entry) => entry.sacrifice);
  if (sacrifices.some((entry) => tributes.some((tribute) => tribute.itemId === entry.itemId))) return false;
  if (complete && sacrifices.length > tributes.filter((entry) => rulesTributeSacrificePower(cardsById.get(entry.cardId)) !== null).length) return false;
  return rulesAdditionalCostAvailableClient(draft, selected);
}

function rulesFindTributePaymentClient(draft, remaining) {
  if (Object.values(remaining).every((amount) => amount <= 0)) return [];
  const candidates = draft.manifestations;
  const capacities = candidates.map((entry) => entry.sacrifice ? 0 : Math.max(
    Number(rulesTributeCandidate(entry.paymentValue)?.power || 0),
    Number(rulesTributeSacrificePower(cardsById.get(entry.cardId)) || 0),
  ));
  const required = Object.values(remaining).reduce((sum, amount) => sum + Math.max(0, amount), 0);
  if (capacities.toSorted((a, b) => b - a).slice(0, 7).reduce((sum, power) => sum + power, 0) < required) return null;
  const values = (entries) => entries.map((entry) => entry.paymentValue);
  if (!rulesManifestationsCover(values(candidates), remaining)) return null;
  const maxCount = Math.min(candidates.length, 7 + Math.min(7, candidates.filter((entry) => entry.sacrifice).length));
  const search = (start, selected, count) => {
    if (!rulesTributeSelectionAvailableClient(draft, selected, false)) return null;
    if (selected.length === count) return rulesTributeSelectionAvailableClient(draft, selected)
      && rulesManifestationsCover(values(selected), remaining) ? selected : null;
    if (candidates.length - start < count - selected.length) return null;
    const held = selected.reduce((sum, entry) => sum + capacities[candidates.indexOf(entry)], 0);
    if (held + capacities.slice(start).sort((a, b) => b - a).slice(0, count - selected.length).reduce((sum, power) => sum + power, 0) < required) return null;
    if (!rulesManifestationsCover(values([...selected, ...candidates.slice(start)]), remaining)) return null;
    const seen = new Set();
    for (let index = start; index < candidates.length; index += 1) {
      const candidate = candidates[index];
      if (seen.has(candidate.paymentValue)) continue;
      seen.add(candidate.paymentValue);
      const found = search(index + 1, [...selected, candidate], count);
      if (found) return found;
    }
    return null;
  };
  for (let count = 1; count <= maxCount; count += 1) {
    const found = search(0, [], count);
    if (found) return found;
  }
  return null;
}

function rulesDraftCanBePaid(draft) {
  if (!draft) return false;
  if (!rulesAdditionalCostAvailableClient(draft)) return false;
  if (draft.essenceCostPayable === false) return false;
  const plans = (draft.essencePlan.transcendentChoice || rulesCounterEssenceSources().length) && draft.transcendentPayment === undefined
    ? rulesEssencePaymentOptions(draft.paymentRequirements, true) : [draft.essencePlan];
  for (const { remaining } of plans) {
    if (rulesFindTributePaymentClient(draft, remaining) !== null) return true;
  }
  return false;
}

function rulesCopiedEffectsCardId(item) {
  const effect = (latestState?.rulesEngine?.ongoingEffects || [])
    .findLast((entry) => (
      entry.kind === "copy_power_effects"
      && entry.source?.itemId === item?.id
      && entry.target?.cardId
    ));
  return effect?.target?.cardId || null;
}

function rulesActivatedAbilitiesForItem(item) {
  const copy = (latestState?.rulesEngine?.ongoingEffects || []).findLast((entry) => (
    entry.kind === "copy_power_effects" && entry.source?.itemId === item?.id
  ));
  const copiedCardId = rulesCopiedEffectsCardId(item);
  const own = copy?.copiedRules ? copy.copiedRules.activatedAbilities || []
    : activatedAbilitiesByCard.get(copiedCardId || item?.cardId) || [];
  // Gummo gains the effects of a Vessel card in addition to its own.
  return item?.gummoCopy ? [...own, ...(activatedAbilitiesByCard.get(item.gummoCopy) || [])] : own;
}

function rulesFirstManifestationSlotTakenClient() {
  const rules = latestState?.rulesEngine;
  return !!rules?.firstManifestationComplete || !!rules?.firstManifestationItemIds?.[myPlayerId]
    || (latestState?.battlefield || []).some((item) => (
      battlefieldItemControllerId(item) === myPlayerId && item.fieldZone === "confrontation"
      && (item.isTokenCard || item.willManifestation || cardsById.get(item.cardId)?.type === "manifestation")
    ));
}

function rulesImmediateEffectPendingClient() {
  const stack = latestState?.rulesEngine?.actionStack || [];
  return Boolean(stack[stack.length - 1]?.immediate);
}

function rulesEndActionsSkippedClient() {
  return String(currentPhaseUi().phase?.id || "").startsWith("end_")
    && (latestState?.rulesEngine?.skipEndPhasePlayerIds || []).includes(myPlayerId);
}

function rulesActivatedActionDraft(item, abilityOverride = null) {
  const abilities = rulesActivatedAbilitiesForItem(item);
  const ability = abilityOverride
    || abilities[0]
    || null;
  if (
    isObserver || latestState?.ended || rulesImmediateEffectPendingClient() || rulesEndActionsSkippedClient()
    || !item?.faceUp
    // a card without its effects (Stalemate Zone, lost effects) has nothing to activate
    || item.effectsInactive
    || item.effectsDisabled
    || (
      battlefieldItemControllerId(item) !== myPlayerId
      && !ability?.anyPlayer
    )
    || (
      ability?.opponentOnly
      && battlefieldItemControllerId(item) === myPlayerId
    )
    || !latestState?.rulesEngine?.enabled
    || latestState.rulesEngine.pendingChoice
    || latestState.rulesEngine.priorityPlayerId !== myPlayerId
    || rules_pregame_active_client()
    || rules_recovery_mulligan_active_client()
    || (!["confrontation_reaction", "resolution_effects", "end_actions"].includes(currentPhaseUi().phase?.id)
      && !ability?.phaseIds?.includes(currentPhaseUi().phase?.id))
  ) return null;
  if (!abilities.length) return null;
  if (Array.isArray(item.usableAbilityIds) && !item.usableAbilityIds.includes(ability?.id)) return null;
  if (
    Array.isArray(ability.phaseIds)
    && ability.phaseIds.length
    && !ability.phaseIds.includes(currentPhaseUi().phase?.id)
  ) return null;
  const source = { cardId: item.cardId, zone: "battlefield", itemId: item.id };
  const draft = buildRulesActionDraft(source, ability);
  if (!draft.encodedAbility) return null;
  if (["field_becomes_first_manifestation", "interzone_becomes_first_manifestation"].includes(ability.result?.kind) && rulesFirstManifestationSlotTakenClient()) return null;
  if (draft.encodedAbility.sourceFieldZone && rulesFieldZoneClient(item) !== draft.encodedAbility.sourceFieldZone) return null;
  if (
    Array.isArray(draft.encodedAbility.sourceZones)
    && draft.encodedAbility.sourceZones.length
    && !draft.encodedAbility.sourceZones.includes("battlefield")
  ) return null;
  if (draft.encodedAbility.exhaustSource && Math.round(Number(item.rotation || 0)) % 180 !== 0) return null;
  const counterGate = ability.requireSourceCounter;
  if (counterGate) {
    const held = Object.entries(item.counters || {})
      .filter(([name]) => name.toLocaleLowerCase() === String(counterGate.name || "").toLocaleLowerCase())
      .reduce((total, [, amount]) => total + Number(amount || 0), 0);
    if (held < Number(counterGate.min || 0) || held > Number(counterGate.max ?? 99)) return null;
  }
  if (ability.requireHandCard && !latestState?.players?.[myPlayerId]?.zones?.hand?.cards?.length) return null;
  const turnNow = Number(latestState?.phaseTracker?.turn || 0);
  if (ability.oncePerTurnSupport && [item.supportUsedTurn, item.supportUntilTurn].some((value) => Number(value || 0) === turnNow)) return null;
  const counterCost = draft.encodedAbility.removeCountersFromSource;
  if (counterCost?.name) {
    const wanted = String(counterCost.name).toLocaleLowerCase();
    const held = Object.entries(item.counters || {})
      .filter(([name]) => name.toLocaleLowerCase() === wanted)
      .reduce((total, [, amount]) => total + Number(amount || 0), 0);
    if (held < Number(counterCost.amount || 0)) return null;
  }
  if (!rulesDraftCanBePaid(draft)) return null;
  if (!rulesDraftHasTargetsClient(draft)) return null;
  return { source, draft };
}

// "Can only be played as if it were a persistent Will" (The Slumberer).
function rulesPlayType(card) {
  return /\bCan only be played as if it were a persistent Will\b/i.test(String(card?.effect || ""))
    ? "persistent_will"
    : card?.type;
}

function beginRulesBoardAction(source) {
  if (rulesEndActionsSkippedClient()) return false;
  const draft = buildRulesActionDraft(source);
  if (!draft.card || !(source.tebebe || ["ephemeral_will", "persistent_will"].includes(rulesPlayType(draft.card)))) return false;
  const playable = source.tebebe
    ? tebebeManifestationIsPlayable(latestState?.battlefield?.find((entry) => entry.id === source.itemId))
    : source.playFromField
    ? limboWillIsPlayable(source.cardId, true)
    : source.zone === "graveyard"
      ? limboWillIsPlayable(source.cardId)
      : handCardIsPlayable(source.cardId, source);
  if (!playable) {
    if (source.zone === "hand" && !source.tebebe && !source.playFromField) refuseHandCard(source.cardId, source.handIndex ?? null);
    else showToast(t("rulesBoardCardNotPlayable"), true);
    return true;
  }
  closeRulesActionPanel();
  pendingRulesBoardFlow = {
    mode: "action",
    source,
    draft,
    selectedPaymentIndexes: new Set(),
    extraEssenceCount: 0,
    extraEssenceConfirmed: false,
    stage: rulesInitialActionStage(draft),
  };
  renderRulesBoardFlow();
  if (
    pendingRulesBoardFlow && pendingRulesBoardFlow.stage === "target"
    && Number(draft.targetRules?.min || 0) === 0
    && !rulesDraftOffersOptionalTargets(draft)
  ) scheduleRulesBoardSubmit();
  return true;
}

function beginRulesHandActivatedAction(cardId, handIndex, zone = "hand", containerId = null) {
  const source = {
    cardId,
    zone,
    handIndex,
    actionKind: "activated_effect",
  };
  if (containerId) source.containerId = containerId;
  const available = rulesZoneActivatedActionDraft(source);
  if (!available) {
    showToast(t("rulesBoardEffectNotAvailable"), true);
    return false;
  }
  const { draft } = available;
  closeRulesActionPanel();
  pendingRulesBoardFlow = {
    mode: "action",
    actionKind: "activated_effect",
    source,
    draft,
    selectedPaymentIndexes: new Set(),
    extraEssenceCount: 0,
    extraEssenceConfirmed: false,
    stage: rulesInitialActionStage(draft),
  };
  renderRulesBoardFlow();
  if (
    pendingRulesBoardFlow
    && pendingRulesBoardFlow.stage === "target"
    && Number(draft.targetRules?.min || 0) === 0
    && !rulesDraftOffersOptionalTargets(draft)
  ) scheduleRulesBoardSubmit();
  return true;
}

function beginRulesBoardActivatedAction(item, abilityId = null) {
  if (rulesEndActionsSkippedClient()) return false;
  const ability = abilityId
    ? rulesActivatedAbilitiesForItem(item).find(
        (candidate) => candidate.id === abilityId,
      )
    : null;
  const counterSource = rulesCounterEssenceSources().find((entry) => entry.item.id === item.id && (!abilityId || entry.ability.id === abilityId));
  if (counterSource && rulesCanSpendCounterEssence()) {
    closeRulesActionPanel();
    send({ type: "spend_counter_essence", itemId: item.id, abilityId: counterSource.ability.id });
    return true;
  }
  const available = rulesActivatedActionDraft(item, ability);
  if (!available) {
    showToast(t("rulesBoardEffectNotAvailable"), true);
    return false;
  }
  closeRulesActionPanel();
  pendingRulesBoardFlow = {
    mode: "action",
    source: available.source,
    draft: available.draft,
    selectedPaymentIndexes: new Set(),
    extraEssenceCount: 0,
    extraEssenceConfirmed: false,
    stage: rulesInitialActionStage(available.draft),
  };
  renderRulesBoardFlow();
  if (
    pendingRulesBoardFlow && pendingRulesBoardFlow.stage === "target"
    && Number(available.draft.targetRules?.min || 0) === 0
    && !rulesDraftOffersOptionalTargets(available.draft)
  ) scheduleRulesBoardSubmit();
  return true;
}

function beginRulesBoardPlacementTarget(payload, source) {
  const ability = placementTargetTrigger(payload, source);
  if (!ability || ability.targets?.kind === "player") return false;
  const draft = buildRulesActionDraft(source, ability);
  if (ability.targets?.excludeEventSource && source?.itemId) {
    draft.structuredTargets = draft.structuredTargets.filter((target) => target.id !== source.itemId);
  }
  pendingRulesBoardFlow = {
    mode: "placement",
    source,
    placement: payload,
    draft,
    selectedPaymentIndexes: new Set(),
    stage: "target",
  };
  renderRulesBoardFlow();
  return true;
}

function rulesActionKindOptions(zone) {
  return zone === "hand"
    ? [["play_card", "rulesKindPlayCard"]]
    : [["activated_effect", "rulesKindActivated"], ["triggered_effect", "rulesKindTriggered"]];
}

function rulesFieldZoneClient(item) {
  return ["field", "confrontation", "interzone", "stalemate"].includes(item?.fieldZone)
    ? item.fieldZone
    : Object.values(latestState?.rulesEngine?.firstManifestationItemIds || {}).includes(item?.id) ? "confrontation" : "field";
}

function rulesDraftHasTargetsClient(draft, chosenTargets = []) {
  const groups = draft?.targetRules?.groups;
  if (!Array.isArray(groups)) {
    const minimum = Number(draft?.targetRules?.min || 0);
    if (minimum > (draft?.structuredTargets?.length || 0)) return false;
    if (!rulesDraftTargetCombinationValidClient(draft, chosenTargets)) return false;
    const assign = (start, selected) => selected.length >= minimum || draft.structuredTargets.some((target, index) => (
      index >= start && !selected.some((entry) => entry.key === target.key)
      && rulesDraftTargetCombinationValidClient(draft, [...selected, target])
      && assign(index + 1, [...selected, target])
    ));
    return assign(0, chosenTargets);
  }
  const assign = (index, selected) => index === groups.length || draft.structuredTargets.some((target) => (
    target.targetGroupIndex === index && !selected.some((entry) => entry.key === target.key)
    && rulesDraftTargetCombinationValidClient(draft, [...selected, target])
    && assign(index + 1, [...selected, target])
  ));
  return rulesDraftTargetCombinationValidClient(draft, chosenTargets) && assign(chosenTargets.length, chosenTargets);
}

function rulesDraftTargetCombinationValidClient(draft, targets) {
  const rules = draft.targetRules || {};
  if (rules.sameContainer && new Set(targets.map((target) => target.containerId)).size > 1) return false;
  if (rules.distinctTargets) {
    const identities = targets.map((target) => target.key || target.itemId || target.id
      || `${target.kind}:${target.containerId}:${target.zone}:${target.cardId}`);
    if (new Set(identities).size !== identities.length) return false;
  }
  if (rules.distinctTemperaments) {
    const temperaments = targets.map((target) => target.effectiveTemperament || target.temperamentOverride
      || target.temperament || cardsById.get(target.cardId)?.temperaments?.[0] || null);
    if (new Set(temperaments).size !== temperaments.length) return false;
  }
  if (Number.isFinite(draft.targetRules?.maxTotalPoints) && targets.reduce((sum, target) => sum + Number(cardsById.get(target.cardId)?.points || 0), 0) > draft.targetRules.maxTotalPoints) return false;
  if (draft.encodedAbility?.id === "induce-desertion" && targets.length > 1
      && battlefieldItemControllerId(targets[0]) !== battlefieldItemControllerId(targets[1])) return false;
  if (draft.encodedAbility?.result?.kind === "retarget_stack_action" && targets.length > 1) {
    const action = (latestState?.rulesEngine?.actionStack || []).find((entry) => entry.id === targets[0].actionId);
    if (Array.isArray(action?.retargetableItemIds) && !action.retargetableItemIds.includes(targets[1].id)) return false;
  }
  return true;
}

function rulesZoneActivatedActionDraft(source, abilityOverride = null) {
  const rules = latestState?.rulesEngine;
  if (!rules?.enabled || latestState?.ended || isObserver || rules.pendingChoice || rulesImmediateEffectPendingClient() || rulesEndActionsSkippedClient()
      || rules.priorityPlayerId !== myPlayerId || rules_pregame_active_client()
      || rules_recovery_mulligan_active_client() || rulesFirstManifestationActive()) return null;
  const containerId = source.containerId || myPlayerId;
  const zone = latestState?.players?.[containerId]?.zones?.[source.zone];
  if (!["hand", "receptacle"].includes(source.zone) || !(zone?.cards || []).includes(source.cardId)) return null;
  if (source.zone === "hand" && containerId !== myPlayerId) return null;
  if (source.zone === "receptacle" && (containerId === myPlayerId || (zone.owners?.[source.cardId] || containerId) !== myPlayerId)) return null;
  if (source.zone === "hand" && Array.isArray(rules.usableHandAbilityCardIds) && !rules.usableHandAbilityCardIds.includes(source.cardId)) return null;
  const ability = abilityOverride || (activatedAbilitiesByCard.get(source.cardId) || []).find((entry) => (entry.sourceZones || []).includes(source.zone));
  if (!ability || !(ability.sourceZones || []).includes(source.zone)) return null;
  const phaseId = currentPhaseUi().phase?.id;
  if (!(ability.phaseIds?.length ? ability.phaseIds : ["confrontation_reaction", "resolution_effects", "end_actions"]).includes(phaseId)) return null;
  const draft = buildRulesActionDraft(source, ability);
  return rulesDraftCanBePaid(draft) && rulesDraftHasTargetsClient(draft) ? { source, draft } : null;
}

function rulesStructuredActionTargets(encodedAbility, context = {}) {
  // abilities may spell their target groups as targets.groups (Shattering the Self)
  if (!Array.isArray(encodedAbility?.targetGroups) && Array.isArray(encodedAbility?.targets?.groups)) {
    encodedAbility = { ...encodedAbility, targetGroups: encodedAbility.targets.groups };
  }
  if (Array.isArray(encodedAbility?.targetGroups)) {
    const groups = encodedAbility.targetGroups;
    const structuredTargets = groups.flatMap((group, targetGroupIndex) => (
      rulesStructuredActionTargets({ targets: group }, context).structuredTargets
        .map((target) => ({ ...target, targetGroupIndex }))
    ));
    return {
      targetRules: { ...(encodedAbility.targets || {}), groups, min: groups.length, max: groups.length },
      noTargetRequired: groups.length === 0,
      structuredTargetKind: "grouped",
      allowedTargetZones: ["battlefield"],
      structuredTargets,
    };
  }
  const targetRules = encodedAbility?.targets || null;
  const noTargetRequired = Boolean(encodedAbility && (!targetRules || Number(targetRules.max) === 0));
  const structuredTargetKind = targetRules?.kind || "card";
  const allowsFieldCard = ["card", "card_or_stack_action"].includes(structuredTargetKind);
  const allowsStackCard = ["stack_action", "card_or_stack_action", "stack_item"].includes(structuredTargetKind);
  const allowedTargetZones = targetRules?.zones || ["battlefield"];
  const allowedTargetTypes = targetRules?.cardTypes || (targetRules?.cardType ? [targetRules.cardType] : []);
  const maxTargetPoints = Number(targetRules?.maxPoints);
  const maxTargetPower = Number(targetRules?.maxPower);
  const minTargetPower = Number(targetRules?.minPower);
  const fieldTargetType = (item) => item.willManifestation || (item.isTokenCard && !item.isCopy)
    ? "manifestation" : cardsById.get(item.cardId)?.type;
  const targetMatchesRules = (cardId, fieldItem = null) => {
    const targetCard = cardsById.get(cardId);
    const targetType = fieldItem ? fieldTargetType(fieldItem) : targetCard?.type;
    if (allowedTargetTypes.length && !allowedTargetTypes.includes(targetType)) return false;
    if (Number.isFinite(targetRules?.maxCost) && Number(targetCard?.cost || 0) > targetRules.maxCost) return false;
    return !Number.isFinite(maxTargetPoints) || (Number.isFinite(Number(targetCard?.points)) && Number(targetCard.points) <= maxTargetPoints);
  };
  const fieldTargets = (latestState?.battlefield || [])
    .filter(() => !noTargetRequired && allowsFieldCard && allowedTargetZones.includes("battlefield"))
    .filter((item) => item.faceUp && (item.cardId || item.isTokenCard))
    .filter((item) => item.effectTargetable !== false)
    .filter((item) => targetMatchesRules(item.cardId, item))
    .filter((item) => {
      const controller = item.controllerId || item.ownerId;
      if (targetRules?.sourceOnly && item.id !== context.sourceItemId) return false;
      if (targetRules?.excludeSource && item.id === context.sourceItemId) return false;
      if (targetRules?.excludeEventSource && item.id === context.eventItemId) return false;
      // same field zone as the server (rules_field_zone): a resolved persistent Will has no
      // explicit fieldZone and stands in the "field" zone, a First Manifestation in the Confrontation
      const itemFieldZone = rulesFieldZoneClient(item);
      const outcomeRule = targetRules?.confrontationOutcome;
      if (["won", "lost"].includes(outcomeRule)) {
        const outcome = latestState?.rulesEngine?.confrontationResult || {};
        if (controller !== outcome[outcomeRule === "won" ? "winnerId" : "loserId"] || !(outcome.participantItemIds || []).includes(item.id)) return false;
      }
      if (targetRules?.enteredInterzoneThisTurn && (itemFieldZone !== "interzone" || Number(item.interzoneTurn) !== Number(latestState?.phaseTracker?.turn))) return false;
      if (targetRules?.controller === "self" && controller !== myPlayerId) return false;
      if (targetRules?.controller === "opponent" && controller === myPlayerId) return false;
      if (targetRules?.owner === "self" && item.ownerId !== myPlayerId) return false;
      if (targetRules?.owner === "opponent" && item.ownerId === myPlayerId) return false;
      if (targetRules?.fieldZone && itemFieldZone !== targetRules.fieldZone) return false;
      // the Stalemate Zone is not on the field (server: rules_ability_targets_error)
      if (
        itemFieldZone === "stalemate" && targetRules?.fieldZone !== "stalemate"
        && !(targetRules?.fieldZonesByType?.[fieldTargetType(item)] || []).includes("stalemate")
      ) return false;
      if (
        targetRules?.firstManifestationOnly
        && !Object.values(
          latestState?.rulesEngine?.firstManifestationItemIds || {},
        ).includes(item.id)
      ) return false;
      const zonesForType = targetRules?.fieldZonesByType?.[fieldTargetType(item)];
      if (Array.isArray(zonesForType) && !zonesForType.includes(itemFieldZone)) return false;
      if (targetRules?.supportOnly && !item.isSupport) return false;
      if (targetRules?.exhaustedOnly && Math.round(Number(item.rotation || 0)) % 180 === 0) return false;
      if (targetRules?.counter) {
        const key = Object.keys(item.counters || {}).find(
          (name) => name.toLocaleLowerCase()
            === targetRules.counter.toLocaleLowerCase(),
        ) || targetRules.counter;
        if (Number(item.counters?.[key] || 0) < Number(targetRules.minCounters || 0)) return false;
      }
      const power = Number(item.effectivePower ?? cardsById.get(item.cardId)?.power);
      return (
        (!Number.isFinite(maxTargetPower) || (Number.isFinite(power) && power <= maxTargetPower))
        && (!Number.isFinite(minTargetPower) || (Number.isFinite(power) && power >= minTargetPower))
      );
    })
    .map((item) => ({ ...item, kind: "card", zone: "battlefield", key: item.id }));
  const publicZoneTargets = Object.entries(latestState?.players || {}).flatMap(([containerId, player]) => (
    (allowsFieldCard || structuredTargetKind === "zone_card" ? allowedTargetZones : [])
      .filter((zone) => zone !== "battlefield")
      .flatMap((zone) => (player.zones?.[zone]?.cards || []).map((cardId, index) => ({
        kind: "zone_card", zone, containerId, cardId,
        ownerId: player.zones?.[zone]?.owners?.[cardId] || containerId,
        key: `zone:${containerId}:${zone}:${cardId}:${index}`,
      })))
  )).filter((item) => targetMatchesRules(item.cardId))
    .filter((item) => latestState?.players?.[item.containerId]?.zones?.[item.zone]?.effectTargetable !== false)
    .filter((item) => item.zone !== "hand" || item.containerId === myPlayerId)
    .filter((item) => !targetRules?.excludeSource || item.cardId !== context.sourceCardId)
    .filter((item) => (
      targetRules?.owner === "self"
        ? item.ownerId === myPlayerId
        : targetRules?.owner === "opponent"
          ? item.ownerId !== myPlayerId
          : true
    ))
    .filter((item) => (
      targetRules?.container === "opponent"
        ? item.containerId !== myPlayerId
        : targetRules?.container === "self"
          ? item.containerId === myPlayerId
          : true
    ))
    .filter((item) => (
      !targetRules?.enteredThisTurn
      || Number(latestState?.rulesEngine?.zoneEntryTurns?.[
        `${item.containerId}:${item.zone}:${item.cardId}`
      ]) === Number(latestState?.phaseTracker?.turn)
    )).filter((item) => (
      !Array.isArray(targetRules?.limboReasons)
      || targetRules.limboReasons.length === 0
      || (latestState?.rulesEngine?.recentLimboEntries || []).some((entry) => (
        entry.ownerId === item.ownerId
        && entry.cardId === item.cardId
        && Number(entry.turn) === Number(latestState?.phaseTracker?.turn)
        && targetRules.limboReasons.includes(entry.reason)
      ))
    ));
  const playerTargets = structuredTargetKind === "player" && !noTargetRequired
    ? Object.keys(latestState?.players || {})
      .filter((playerId) => latestState.players[playerId].effectTargetable !== false)
      .filter((playerId) => (
        targetRules?.controller === "self"
          ? playerId === myPlayerId
          : targetRules?.controller === "opponent"
            ? playerId !== myPlayerId
            : true
      ))
      .map((playerId) => ({
        kind: "player", playerId, key: `player:${playerId}`,
      }))
    : [];
  const stackTargets = (allowsStackCard || structuredTargetKind === "stack_effect") && !noTargetRequired
    ? (latestState?.rulesEngine?.actionStack || [])
      .filter((action) => (
        structuredTargetKind === "stack_item"
          ? ["play_card", "activated_effect", "triggered_effect"].includes(action.kind)
          : allowsStackCard
          ? action.kind === "play_card" && (action.sourceOnStack || action.isStackCopy) && action.source?.cardId
          : (["activated_effect", "triggered_effect"].includes(action.kind) || action.sourceRemainsOnField) && action.source?.cardId
      ))
      .filter((action) => targetMatchesRules(action.source.cardId))
      .filter((action) => action.effectTargetable !== false)
      .filter((action) => !context.retargetsStackAction || !Array.isArray(action.retargetableItemIds) || action.retargetableItemIds.length > 0)
      .filter((action) => !targetRules?.targetsFieldCard || (action.targets || []).some((target) => (
        target.kind === "card" && (latestState?.battlefield || []).some((item) => item.id === target.itemId)
      )))
      .filter((action) => !targetRules?.targetsOwnFieldCard || (action.targets || []).some((target) => (
        target.kind === "card" && (latestState?.battlefield || []).some((item) => item.id === target.itemId && battlefieldItemControllerId(item) === myPlayerId)
      )))
      .filter((action) => !targetRules?.effectTemperamentChosenBySource || (
        (cardsById.get(action.source.cardId)?.temperaments || []).includes(
          (latestState?.battlefield || []).find((item) => item.id === context.sourceItemId)?.chosenTemperament,
        )
      ))
      .filter((action) => !targetRules?.targetsConfrontationManifestation
        || (action.targets || []).some((target) => {
          const item = (latestState?.battlefield || []).find((candidate) => candidate.id === target.itemId);
          return target.kind === "card"
            && rulesFieldZoneClient(item) === "confrontation"
            && fieldTargetType(item) === "manifestation";
        }))
      .filter((action) => {
        if (targetRules?.controller === "self") return action.controllerId === myPlayerId;
        if (targetRules?.controller === "opponent") return action.controllerId !== myPlayerId;
        return true;
      })
      .filter((action) => !(latestState?.rulesEngine?.ongoingEffects || []).some(
        (effect) => (
          effect.kind === "protection"
          && effect.target?.actionId === action.id
          && (!effect.fromOpponents || action.controllerId !== myPlayerId)
        ),
      ))
      .map((action) => ({
        kind: structuredTargetKind === "stack_item"
          ? "stack_item"
          : allowsStackCard ? "stack_action" : structuredTargetKind,
        actionId: action.id, cardId: action.source.cardId,
        controllerId: action.controllerId, key: `stack:${action.id}`,
      }))
    : [];
  const structuredTargets = [...fieldTargets, ...publicZoneTargets, ...playerTargets, ...stackTargets];
  const resolvedTargetRules = targetRules?.anyNumber
    ? { ...targetRules, max: new Set(structuredTargets.map((target) => target.key)).size }
    : targetRules;
  return {
    targetRules: resolvedTargetRules,
    noTargetRequired,
    structuredTargetKind,
    allowedTargetZones,
    structuredTargets,
  };
}

function rulesPersistentWillsAsEphemeralClient() {
  return (latestState?.battlefield || []).some((item) => (
    (item.controllerId || item.ownerId) === myPlayerId
    && item.fieldZone === "interzone"
    && item.faceUp
    && (passiveEffectsByCard.get(item.cardId) || []).some(
      (effect) => effect.kind === "persistent_wills_as_ephemeral",
    )
  ));
}

function isTrapCardClient(cardId) {
  return (playedAbilitiesByCard.get(cardId) || []).some((ability) => ability.result?.kind === "first_manifestation_trap");
}

function trapPlayableClient(cardId) {
  const rules = latestState?.rulesEngine;
  return Boolean(
    rules?.enabled && !isObserver && isTrapCardClient(cardId)
    && rulesFirstManifestationActive()
    && !rulesFirstManifestationSlotTakenClient()
    && !(rules.firstManifestationValidatedPlayerIds || []).includes(myPlayerId)
    && !(rules.trapPlayerIds || []).includes(myPlayerId)
  );
}

function rulesLimboPlayMode(cardId = null) {
  const turn = Number(latestState?.phaseTracker?.turn || 0);
  const phaseId = currentPhaseUi().phase?.id;
  if ((latestState?.rulesEngine?.playPermissions || []).some((permission) => (
    permission.playerId === myPlayerId
    && permission.fromZone === "graveyard"
    && permission.noTribute && permission.exileOnLeave
    && Number(permission.turn || 0) === turn
    && (permission.phaseIds || []).includes(phaseId)
    && (!cardId && permission.anyWill || (cardId ? [cardId] : latestState?.players?.[myPlayerId]?.zones?.graveyard?.cards || []).some((candidateId) => {
      const candidate = cardsById.get(candidateId);
      const version = latestState?.players?.[myPlayerId]?.zones?.graveyard?.entryVersions?.[candidateId];
      return ["ephemeral_will", "persistent_will"].includes(candidate?.type)
        && (permission.cardId === candidateId || permission.anyWill)
        && (!permission.ephemeralOnly || candidate.type === "ephemeral_will")
        && (permission.maxCost == null || Number(candidate.cost || 0) <= Number(permission.maxCost))
        && (permission.zoneEntryVersion === undefined || Number(permission.zoneEntryVersion) === Number(version));
    }))
  ))) return "free";
  const hollow = (latestState?.battlefield || []).some((item) => (
    (item.controllerId || item.ownerId) === myPlayerId
    && item.faceUp !== false
    && (passiveEffectsByCard.get(item.cardId) || []).some(
      (effect) => effect.kind === "play_wills_from_limbo_hollow_tribute"
    )
  ));
  return hollow ? "hollow" : null;
}

const JU_LIEN_CARD_ID = "qapv47r7rz6gqah_en";

// Cards that can be played from another zone right now (Limbo, Wills placed on a Grimoire) show up as faded cards at the end of the hand
function rulesGhostHandCards() {
  const rules = latestState?.rulesEngine;
  if (!rules?.enabled || isObserver || !latestState?.players?.[myPlayerId]) return [];
  const ghosts = [];
  const uncoveredTop = rules.uncoveredTops?.[myPlayerId];
  if (uncoveredTop && cardsById.get(uncoveredTop)?.type === "manifestation") {
    ghosts.push({
      cardId: uncoveredTop,
      zone: "deck",
      label: t("deck"),
      playable: handCardIsPlayable(uncoveredTop),
    });
  }
  const paying = pendingRulesBoardFlow?.stage === "payment" ? pendingRulesBoardFlow : null;
  if (paying) {
    // Tribute cards outside the Hand appear beside it and retain their source-zone label.
    for (const candidate of paying.draft?.manifestations || []) {
      if (candidate.zone !== "hand") ghosts.push({
        cardId: candidate.cardId,
        zone: "payment",
        selectionKey: candidate.selectionKey,
        label: t(candidate.zone),
      });
    }
    return ghosts;
  }
  if (rules.pendingChoice) return ghosts;
  for (const cardId of new Set(latestState.players[myPlayerId].zones?.graveyard?.cards || [])) {
    if (limboWillIsPlayable(cardId)) ghosts.push({ cardId, zone: "graveyard", label: t("graveyard") });
    // Wandering Veteran: playable in Support from the Limbo, shown in the hand while it can be played
    else if (rulesLimboPermissionPlayable(cardId)) ghosts.push({ cardId, zone: "graveyard", label: t("graveyard"), permission: true });
  }
  // Ju Lien and Concealed Wills: cards playable from the field use the hand's play path.
  for (const item of latestState.battlefield || []) {
    if (battlefieldItemControllerId(item) !== myPlayerId) continue;
    if (item.concealedWill && ["ephemeral_will", "persistent_will"].includes(cardsById.get(item.cardId)?.type)) {
      const source = rulesFieldWillPlaySource(item);
      ghosts.push({ cardId: item.cardId, zone: "field_play", itemId: item.id, label: item.revealedFreeWill ? cardName("inner-deserts-126").split(",")[0] : t("rulesConcealedLabel"), playable: limboWillIsPlayable(item.cardId, true) && rulesDraftCanBePaid(buildRulesActionDraft(source)) });
    } else if (
      item.faceUp
      && Number(item.playableFree) === Number(latestState.phaseTracker?.turn)
      && limboWillIsPlayable(item.cardId, true)
    ) ghosts.push({ cardId: item.cardId, zone: "field_free", itemId: item.id, label: cardName(JU_LIEN_CARD_ID).split(",")[0] });
  }
  for (const host of latestState.battlefield || []) {
    if (battlefieldItemControllerId(host) !== myPlayerId || host.faceUp === false || host.effectsDisabled || !(host.attachedCards || []).length) continue;
    if (!(passiveEffectsByCard.get(host.cardId) || []).some((effect) => effect.kind === "play_attached_wills")) continue;
    for (const cardId of new Set(host.attachedCards.map((entry) => entry.cardId))) {
      if (["ephemeral_will", "persistent_will"].includes(cardsById.get(cardId)?.type)) {
        const source = { cardId, zone: "attached", itemId: host.id };
        ghosts.push({ ...source, playable: handCardIsPlayable(cardId, source), label: cardName(host.cardId) });
      }
    }
  }
  return ghosts;
}

function rulesFieldWillPlaySource(item, placement = { x: item.x, y: item.y }) {
  return {
    cardId: item.cardId, zone: "battlefield", itemId: item.id, playFromField: true,
    fieldFree: Number(item.playableFree) === Number(latestState?.phaseTracker?.turn) || Boolean(item.concealedFree),
    surcharge: item.persuaded ? 2 : 0,
    ...(item.tebebeConcealed ? { fixedHollow: 3 } : {}),
    placement,
  };
}

// Tebebe: a Concealed Manifestation is played into the Interzone for 3 hollow Essences
function tebebeManifestationIsPlayable(item) {
  const rules = latestState?.rulesEngine;
  const card = cardsById.get(item?.cardId);
  if (!rules?.enabled || !item?.tebebeConcealed || card?.type !== "manifestation" || isObserver || rules.pendingChoice || rulesEndActionsSkippedClient()) return false;
  if (rules.priorityPlayerId !== myPlayerId || rulesCardPlayRestrictedClient(item.cardId)) return false;
  return ["confrontation_reaction", "end_actions"].includes(currentPhaseUi().phase?.id);
}

// a Limbo card with a play permission (Wandering Veteran) that can be played right now
function rulesLimboPermission(cardId) {
  return (latestState?.rulesEngine?.playPermissions || []).find((permission) => (
    permission.playerId === myPlayerId
    && permission.fromZone === "graveyard"
    && permission.asSupport
    && permission.cardId === cardId
    && Number(permission.turn || 0) === Number(latestState?.phaseTracker?.turn || 0)
  )) || null;
}

function rulesLimboPermissionPlayable(cardId) {
  const rules = latestState?.rulesEngine;
  const permission = rulesLimboPermission(cardId);
  if (!permission || !rules?.enabled || isObserver || rules.pendingChoice) return false;
  if (rules.priorityPlayerId !== myPlayerId) return false;
  if (!(latestState?.players?.[myPlayerId]?.zones?.graveyard?.cards || []).includes(cardId)) return false;
  if (permission.phaseIds?.length && !permission.phaseIds.includes(currentPhaseUi().phase?.id)) return false;
  return !(permission.asSupport && rulesSupportEntryLockedClient());
}

function limboWillIsPlayable(cardId, fromField = false) {
  const rules = latestState?.rulesEngine;
  const card = cardsById.get(cardId);
  if (!rules?.enabled || !card || isObserver || rules.pendingChoice || rulesEndActionsSkippedClient()) return false;
  if (!["ephemeral_will", "persistent_will"].includes(card.type)) return false;
  if (rules.priorityPlayerId !== myPlayerId || !(fromField || rulesLimboPlayMode(cardId))) return false;
  if (rulesCardPlayRestrictedClient(cardId)) return false;
  const phaseId = currentPhaseUi().phase?.id;
  if (card.type === "persistent_will") {
    return phaseId === "end_actions";
  }
  return rulesEphemeralPhasesClient(card).includes(phaseId);
}

// null = the player's Limbo; { itemId } = the Wills placed on a host (Grimoire)
let limboPlayAttachedHost = null;

function openAttachedPlayPanel(itemId) {
  limboPlayAttachedHost = itemId;
  openLimboPlayPanel();
}

function openLimboPlayPanel() {
  const attached = limboPlayAttachedHost !== null;
  $("#limboPlayHeading").textContent = t(attached ? "attachedPlayHeading" : "limboPlayHeading");
  $("#limboPlaySearch").placeholder = t(attached ? "attachedPlaySearch" : "limboPlaySearch");
  $("#limboPlaySearch").value = "";
  $("#limboPlayPanel").classList.remove("hidden");
  renderLimboPlayList();
  $("#limboPlaySearch").focus();
}

function closeLimboPlayPanel() {
  limboPlayAttachedHost = null;
  $("#limboPlayPanel").classList.add("hidden");
}

function renderLimboPlayList() {
  const list = $("#limboPlayList");
  const query = $("#limboPlaySearch").value.trim().toLocaleLowerCase();
  const host = limboPlayAttachedHost !== null
    ? (latestState?.battlefield || []).find((candidate) => candidate.id === limboPlayAttachedHost)
    : null;
  const attachedMode = limboPlayAttachedHost !== null;
  const cards = attachedMode
    ? [...new Set((host?.attachedCards || []).map((entry) => entry.cardId))]
      .filter((cardId) => !query || cardName(cardId).toLocaleLowerCase().includes(query))
    : [...new Set(latestState?.players?.[myPlayerId]?.zones?.graveyard?.cards || [])]
      .filter((cardId) => limboWillIsPlayable(cardId))
      .filter((cardId) => !query || cardName(cardId).toLocaleLowerCase().includes(query));
  list.innerHTML = cards.length
    ? cards.map((cardId) => `<button type="button" class="limbo-play-card" data-limbo-play-card="${esc(cardId)}" title="${esc(cardName(cardId))}">
        <img src="${esc(cardImage(cardId))}" alt="${esc(cardName(cardId))}"><span>${esc(cardName(cardId))}</span></button>`).join("")
    : `<p>${esc(t(attachedMode ? "attachedPlayEmpty" : "limboPlayEmpty"))}</p>`;
  list.querySelectorAll("[data-limbo-play-card]").forEach((button) => {
    button.onclick = () => {
      const cardId = button.dataset.limboPlayCard;
      if (attachedMode) {
        const canPlay = host && host.ownerId === myPlayerId && !isObserver
          && ["ephemeral_will", "persistent_will"].includes(cardsById.get(cardId)?.type)
          && (passiveEffectsByCard.get(host.cardId) || []).some((effect) => effect.kind === "play_attached_wills");
        closeLimboPlayPanel();
        if (canPlay) {
          beginRulesBoardAction({
            cardId, zone: "attached", itemId: host.id,
            placement: { x: host.x + 40, y: host.y + 40 },
          });
        } else showInspect(cardId);
        return;
      }
      closeLimboPlayPanel();
      beginRulesBoardAction({ cardId, zone: "graveyard", placement: { x: 700, y: 300 } });
    };
  });
}

function rulesActionPaymentDraft(source, card, encodedAbility, transcendentPayment = undefined) {
  const limboPlay = source.playFromField
    ? (source.fieldFree === false ? null : "free")
    : source.zone === "graveyard"
      && ["ephemeral_will", "persistent_will"].includes(card?.type)
      ? rulesLimboPlayMode(source.cardId) : null;
  const isPrintedWill = (["hand", "suspended", "attached"].includes(source.zone) || Boolean(limboPlay) || Boolean(source.playFromField))
    && ["ephemeral_will", "persistent_will"].includes(rulesPlayType(card));
  const freeWillPermission = (source.zone === "hand" && source.actionKind !== "activated_effect" && card?.type === "manifestation" && rulesPlayType(card) === "persistent_will") || isPrintedWill && (latestState?.rulesEngine?.playPermissions || []).some((permission) => (
    permission.playerId === myPlayerId
    && permission.fromZone === "hand"
    && permission.noTribute
    && (permission.cardId === source.cardId || permission.anyWill)
    && Number(permission.turn || 0) === Number(latestState?.phaseTracker?.turn || 0)
  ));
  const paymentRequirements = source.fixedHollow
    ? { hollow: Number(source.fixedHollow) }
    : limboPlay
    ? (limboPlay === "free" ? {} : { hollow: 1 })
    : freeWillPermission
    ? {}
    : encodedAbility && Object.hasOwn(encodedAbility, "tribute")
    ? printedTributeRequirements({ powerCost: encodedAbility.tribute })
    : isPrintedWill ? printedTributeRequirements(card) : {};
  const passiveSources = (latestState?.battlefield || []).filter((item) => item.faceUp && !item.effectsDisabled && !item.effectsInactive && item.fieldZone !== "stalemate");
  const printedWillTribute = isPrintedWill && !limboPlay && !source.fixedHollow && !freeWillPermission && !(encodedAbility && Object.hasOwn(encodedAbility, "tribute"));
  let reduction = !printedWillTribute ? 0 : passiveSources.reduce((total, item) => {
    if ((item.controllerId || item.ownerId) !== myPlayerId || item.fieldZone !== "interzone") return total;
    return total + (passiveEffectsByCard.get(item.cardId) || [])
      .filter((effect) => effect.kind === "reduce_will_tribute")
      .reduce((sum, effect) => sum + Number(effect.value || 0), 0);
  }, 0);
  if (encodedAbility?.costReduction?.kind === "half_first_base_power") {
    const firstId = latestState?.rulesEngine?.firstManifestationItemIds?.[myPlayerId];
    const first = latestState?.battlefield?.find((item) => item.id === firstId);
    reduction += Math.floor(Number(cardsById.get(first?.cardId)?.power || 0) / 2);
  }
  while (reduction > 0) {
    const payable = Object.keys(paymentRequirements)
      .sort((a, b) => Number(paymentRequirements[b]) - Number(paymentRequirements[a]))[0];
    if (!payable || Number(paymentRequirements[payable]) <= 0) break;
    paymentRequirements[payable] -= 1;
    reduction -= 1;
  }
  if (printedWillTribute) {
    const increase = passiveSources.reduce((total, item) => (
      total + (passiveEffectsByCard.get(item.cardId) || [])
        .filter((effect) => effect.kind === "increase_will_tribute")
        .reduce((sum, effect) => sum + Number(effect.value || 0), 0)
    ), 0);
    if (increase > 0) {
      paymentRequirements.hollow = Number(paymentRequirements.hollow || 0) + increase;
    }
  }
  if (source.playFromField && Number(source.surcharge || 0) > 0) {
    paymentRequirements.hollow = Number(paymentRequirements.hollow || 0) + Number(source.surcharge);
  }
  if (source.zone === "suspended") {
    const total = Object.values(paymentRequirements)
      .reduce((sum, amount) => sum + Number(amount || 0), 0);
    Object.keys(paymentRequirements).forEach((key) => { delete paymentRequirements[key]; });
    if (total > 0) paymentRequirements.hollow = total;
  }
  if (Number(source.targetExtraEssence || 0) > 0) paymentRequirements.hollow = Number(paymentRequirements.hollow || 0) + Number(source.targetExtraEssence);
  const hasPrintedTribute = Object.values(paymentRequirements).some((amount) => amount > 0);
  const essenceCostRequirements = encodedAbility?.essenceCost
    ? printedTributeRequirements({ powerCost: encodedAbility.essenceCost })
    : {};
  // An Essence-only ability can wait in the payment flow while the player
  // explicitly converts a Gem. Manifestations remain unavailable for this cost.
  if (!hasPrintedTribute) Object.assign(paymentRequirements, essenceCostRequirements);
  let essencePlan = rulesEssencePaymentPreview(paymentRequirements, transcendentPayment);
  // Before the player assigns White Essences, keep every remaining colour's
  // Tribute candidates visible, including payments requested by effects.
  if (essencePlan.transcendentChoice && transcendentPayment === undefined) {
    essencePlan = rulesEssencePaymentPreview(paymentRequirements, {});
  }
  const essenceCostPlan = rulesEssencePaymentPreview(essenceCostRequirements, undefined, true);
  const essenceCostPayable = Object.values(essenceCostPlan.remaining)
    .every((amount) => amount <= 0);
  const totalEssence = (latestState?.tokens || [])
    .filter((token) => (
      token.ownerId === myPlayerId
      && token.isEssence
      && !token.isNeutralCounter
    ))
    .reduce(
      (sum, token) => sum + Number(token.counters?.essence || 0),
      0,
    );
  const mandatoryEssenceSpent = [
    ...Object.values(essencePlan.spent),
    ...Object.values(essenceCostPlan.spent),
  ].reduce((sum, amount) => sum + Number(amount || 0), 0);
  const optionalExtraEssenceMax = encodedAbility?.optionalExtraEssence
    ? Math.max(0, Math.min(
        encodedAbility.optionalExtraEssence.max == null ? Infinity : Number(encodedAbility.optionalExtraEssence.max),
        totalEssence - mandatoryEssenceSpent,
      ))
    : 0;
  const extraTributeCards = [];
  if (encodedAbility?.optionalExtraEssence) {
    let sourceSkipped = false;
    (latestState?.players?.[myPlayerId]?.zones?.hand?.cards || []).forEach((cardId, index) => {
      const card = cardsById.get(cardId);
      if (card?.type !== "manifestation") return;
      if (!sourceSkipped && source.zone === "hand" && cardId === source.cardId
        && (Number.isInteger(source.handIndex) ? index === source.handIndex : true)) {
        sourceSkipped = true;
        return;
      }
      extraTributeCards.push({ cardId, index, power: Math.max(0, Number(card.power || 0)) });
    });
  }
  const remainingTemperaments = Object.entries(essencePlan.remaining)
    .filter(([, amount]) => amount > 0)
    .map(([temperament]) => temperament);
  const handCards = latestState?.players?.[myPlayerId]?.zones?.hand?.cards || [];
  let sourceCopyReserved = false;
  const manifestations = handCards.flatMap((cardId, index) => {
    const manifestation = cardsById.get(cardId);
    if (manifestation?.type !== "manifestation") return [];
    if (/^Cannot be used (?:to pay tributes|as tribute)/im.test(String(manifestation.effect || ""))) return [];
    const isSourceCopy = source.zone === "hand" && cardId === source.cardId
      && (Number.isInteger(source.handIndex) ? index === source.handIndex : !sourceCopyReserved);
    if (isSourceCopy) {
      sourceCopyReserved = true;
      return [];
    }
    if (hasPrintedTribute) {
      const tributeTemperaments = cardTributeTemperaments(manifestation);
      const compatible = tributeTemperaments.includes("transcendent")
        || tributeTemperaments.some((temperament) => remainingTemperaments.includes(temperament))
        || remainingTemperaments.includes("hollow");
      if (!compatible || !remainingTemperaments.length) return [];
    }
    return [{
      cardId, index, selectionKey: index,
      paymentValue: cardId, zone: "hand",
    }];
  });
  const limboSource = passiveSources.find((item) => (
    (item.controllerId || item.ownerId) === myPlayerId
    && Number(item.counters?.Formula || 0) > 0
    && (passiveEffectsByCard.get(item.cardId) || []).some(
      (effect) => effect.kind === "allow_limbo_tribute_with_counter"
    )
  ));
  if (limboSource) {
    const limboCards = latestState?.players?.[myPlayerId]?.zones?.graveyard?.cards || [];
    for (const cardId of limboCards) {
      const manifestation = cardsById.get(cardId);
      if (manifestation?.type !== "manifestation") continue;
      if (/^Cannot be used (?:to pay tributes|as tribute)/im.test(String(manifestation.effect || ""))) continue;
      manifestations.push({
        cardId,
        index: null,
        selectionKey: `graveyard:${cardId}:${manifestations.length}`,
        paymentValue: `graveyard|${cardId}`,
        zone: "graveyard",
        usesFormula: !/\bcan be used as tribute from (?:the )?Limbo\./i.test(String(manifestation.effect || "")),
      });
    }
  }
  if (!limboSource) {
    const limboCards = latestState?.players?.[myPlayerId]?.zones?.graveyard?.cards || [];
    for (const cardId of limboCards) {
      const manifestation = cardsById.get(cardId);
      if (
        manifestation?.type !== "manifestation"
        || !/\bcan be used as tribute from (?:the )?Limbo\./i.test(
          String(manifestation.effect || ""),
        )
      ) continue;
      manifestations.push({
        cardId,
        index: null,
        selectionKey: `graveyard:${cardId}:${manifestations.length}`,
        paymentValue: `graveyard|${cardId}`,
        zone: "graveyard",
      });
    }
  }
  const fieldTributeActive = passiveSources.some((item) => (
    (passiveEffectsByCard.get(item.cardId) || []).some(
      (effect) => effect.kind === "field_manifestations_as_tribute"
    )
  ));
  for (const item of latestState?.battlefield || []) {
    const manifestation = cardsById.get(item.cardId);
    const interzoneTribute = item.fieldZone === "interzone"
      && /\bcan be used as tribute from the Interzone\./i.test(
        String(manifestation?.effect || ""),
      );
    const fieldTribute = fieldTributeActive
      && ["interzone", "confrontation"].includes(item.fieldZone)
      && !item.isTokenCard
      && !/^Cannot be used (?:to pay tributes|as tribute)/im.test(
        String(manifestation?.effect || ""),
      );
    if (
      battlefieldItemControllerId(item) !== myPlayerId
      || manifestation?.type !== "manifestation"
      || item.id === source?.itemId
      || !(interzoneTribute || fieldTribute)
    ) continue;
    manifestations.push({
      cardId: item.cardId,
      itemId: item.id,
      index: null,
      selectionKey: `battlefield:${item.id}`,
      paymentValue: `battlefield|${item.id}`,
      zone: "interzone",
      powerOverride: rulesTributeCandidate(`battlefield|${item.id}`)?.power,
    });
  }
  if (manifestations.some((entry) => rulesTributeSacrificePower(cardsById.get(entry.cardId)) !== null)) {
    for (const item of latestState?.battlefield || []) {
      if (
        battlefieldItemControllerId(item) !== myPlayerId
        || item.fieldZone !== "interzone"
        || cardsById.get(item.cardId)?.type !== "manifestation"
        || item.id === source?.itemId
      ) continue;
      manifestations.push({
        cardId: item.cardId,
        itemId: item.id,
        index: null,
        selectionKey: `sacrifice:${item.id}`,
        paymentValue: `sacrifice|${item.id}`,
        zone: "interzone",
        sacrifice: true,
      });
    }
  }
  const vesselTributeActive = passiveSources.some((item) => (
    battlefieldItemControllerId(item) === myPlayerId
    && (passiveEffectsByCard.get(item.cardId) || []).some(
      (effect) => effect.kind === "vessel_manifestations_as_tribute"
    )
  ));
  if (vesselTributeActive) {
    const vesselCards = latestState?.players?.[myPlayerId]?.zones?.receptacle?.cards || [];
    for (const cardId of vesselCards) {
      const manifestation = cardsById.get(cardId);
      if (
        manifestation?.type !== "manifestation"
        || /^Cannot be used (?:to pay tributes|as tribute)/im.test(
          String(manifestation.effect || ""),
        )
      ) continue;
      manifestations.push({
        cardId,
        index: null,
        selectionKey: `receptacle:${cardId}:${manifestations.length}`,
        paymentValue: `receptacle|${cardId}`,
        zone: "receptacle",
      });
    }
  }
  if (
    Object.keys(essenceCostRequirements).length
    && !hasPrintedTribute
  ) manifestations.length = 0;
  return {
    paymentRequirements, hasPrintedTribute, essencePlan, transcendentPayment,
    limboTributeBudget: Number(limboSource?.counters?.Formula || 0),
    essenceCostRequirements, essenceCostPlan, essenceCostPayable,
    optionalExtraEssenceMax, extraTributeCards, remainingTemperaments, manifestations,
  };
}

function rulesInitialActionStage(draft) {
  if (draft.essencePlan.transcendentChoice && draft.transcendentPayment === undefined) return "essence_allocation";
  if (
    Object.values(draft.essencePlan.remaining)
      .some((amount) => amount > 0)
  ) return "payment";
  if (draft.encodedAbility?.additionalCost) return "cost_card";
  if (draft.optionalExtraEssenceMax > 0 || draft.extraTributeCards?.length) return "extra_essence";
  return "target";
}

function buildRulesActionDraft(source, abilityOverride = undefined) {
  const card = cardsById.get(source?.cardId);
  const sourceItem = source?.itemId
    ? (latestState?.battlefield || []).find(
      (candidate) => candidate.id === source.itemId,
    )
    : null;
  let encodedAbility = abilityOverride !== undefined
    ? abilityOverride
    : source?.actionKind === "activated_effect"
      // an ability naming the zone wins over a field ability (Malaleuco: Interzone copy, then from Hand)
      ? (activatedAbilitiesByCard.get(source.cardId) || []).find((ability) => (
          Array.isArray(ability.sourceZones) && ability.sourceZones.includes(source.zone)
        )) || (activatedAbilitiesByCard.get(source.cardId) || []).find((ability) => (
          !Array.isArray(ability.sourceZones)
        )) || null
    : source?.playFromField
      ? (playedAbilitiesByCard.get(source.cardId) || [])[0] || null
    : source?.zone === "battlefield"
      ? (rulesActivatedAbilitiesForItem(sourceItem) || [])[0] || null
      : ["hand", "suspended", "graveyard", "attached"].includes(source?.zone)
        ? (playedAbilitiesByCard.get(source.cardId) || [])[0] || null
        : null;
  if (encodedAbility?.tributeFromSourceCounter && source?.itemId) {
    const item = latestState?.battlefield?.find(
      (candidate) => candidate.id === source.itemId
    );
    const counters = item?.counters || {};
    const counterKey = Object.keys(counters).find(
      (key) => key.toLocaleLowerCase()
        === encodedAbility.tributeFromSourceCounter.toLocaleLowerCase()
    ) || encodedAbility.tributeFromSourceCounter;
    encodedAbility = {
      ...encodedAbility,
      tribute: "{H}".repeat(
        Math.max(0, Math.min(Number(counters[counterKey]) || 0, 20))
      ),
    };
  }
  const targetDraft = rulesStructuredActionTargets(encodedAbility, { sourceItemId: source?.itemId, sourceCardId: source?.cardId, retargetsStackAction: encodedAbility?.result?.kind === "retarget_stack_action" });
  if (encodedAbility?.targets?.sourceOnly && source?.itemId) {
    targetDraft.structuredTargets = targetDraft.structuredTargets.filter(
      (target) => target.id === source.itemId,
    );
  }
  return {
    source,
    card,
    encodedAbility,
    ...targetDraft,
    ...rulesActionPaymentDraft(source, card, encodedAbility),
  };
}

function openRulesActionPanel(source) {
  if (rulesEndActionsSkippedClient()) return;
  const rules = latestState?.rulesEngine;
  const draft = buildRulesActionDraft(source);
  const { card, encodedAbility } = draft;
  if (!rules?.enabled || rules.priorityPlayerId !== myPlayerId || isObserver || !card) return;
  if (draft.essencePlan.transcendentChoice) {
    closeRulesActionPanel();
    pendingRulesBoardFlow = { mode: "action", source, draft, selectedPaymentIndexes: new Set(), stage: "essence_allocation" };
    renderRulesBoardFlow();
    return;
  }
  pendingRulesActionSource = {
    cardId: source.cardId,
    zone: source.zone,
    ...(source.suspensionId ? { suspensionId: source.suspensionId } : {}),
    itemId: source.itemId || null,
    abilityId: encodedAbility?.id || null,
    actionKind: source.actionKind || null,
  };

  $("#rulesActionHeading").textContent = t("rulesDeclareHeading");
  $("#rulesActionSourceImg").src = cardImage(source.cardId);
  $("#rulesActionSourceImg").alt = cardName(source.cardId);
  $("#rulesActionSourceName").textContent = cardName(source.cardId);
  const playedZone = ["hand", "suspended"].includes(source.zone)
    && source.actionKind !== "activated_effect";
  const printedCost = playedZone && card.cost !== null && card.cost !== undefined
    ? rulesText("rulesPrintedCost", { cost: card.cost })
    : "";
  $("#rulesActionSourceMeta").textContent = [
    cardField(card, "typeLabel") || card.type,
    printedCost,
    encodedAbility ? t("rulesEncodedAbility") : "",
    encodedAbility?.exhaustSource ? t("rulesExhaustSourceCost") : "",
    encodedAbility?.sacrificeSource ? t("rulesSacrificeSourceCost") : "",
  ].filter(Boolean).join(" · ");
  $("#rulesActionSourceEffect").textContent = cardField(card, "effect") || t("rulesNoPrintedEffect");

  const kindOptions = encodedAbility
    ? [[playedZone ? "play_card" : "activated_effect", playedZone ? "rulesKindPlay" : "rulesKindActivated"]]
    : rulesActionKindOptions(source.zone);
  $("#rulesActionKind").innerHTML = kindOptions
    .map(([value, label]) => `<option value="${value}">${esc(t(label))}</option>`)
    .join("");
  $("#rulesActionKind").disabled = kindOptions.length === 1;
  $("#rulesActionDescription").value = rulesText(
    playedZone ? "rulesDefaultPlay" : "rulesDefaultActivate",
    { card: cardName(source.cardId) },
  );
  $("#rulesActionTarget").value = "";
  $("#rulesActionCostNote").value = "";

  const { targetRules, noTargetRequired, structuredTargetKind, allowedTargetZones, structuredTargets } = draft;
  const targetInputType = targetRules?.max === 1 ? "radio" : "checkbox";
  $("#rulesTargetList").innerHTML = noTargetRequired
    ? `<span class="rules-target-empty">${esc(t("rulesNoTargetRequired"))}</span>`
    : structuredTargets.length
    ? structuredTargets.map((item) => item.kind === "player"
      ? `<label class="rules-target-choice rules-target-player-choice" title="${esc(rulesPlayerName(item.playerId))}">
          <input type="${targetInputType}" name="rules-action-target" value="${esc(item.key)}" data-target-kind="player" data-player-id="${esc(item.playerId)}">
          <span class="rules-target-player-mark" aria-hidden="true">${esc(rulesPlayerName(item.playerId).slice(0, 1).toUpperCase())}</span>
          <span class="rules-target-copy"><strong>${esc(rulesPlayerName(item.playerId))}</strong><span>${esc(t("rulesPlayerTarget"))}</span></span>
        </label>`
      : ["stack_action", "stack_effect", "stack_item"].includes(item.kind)
      ? `<label class="rules-target-choice rules-target-stack-choice" title="${esc(cardName(item.cardId))}">
          <input type="${targetInputType}" name="rules-action-target" value="${esc(item.key)}" data-target-kind="${esc(item.kind)}" data-action-id="${esc(item.actionId)}" data-card-id="${esc(item.cardId)}">
          <img src="${esc(cardImage(item.cardId))}" alt="">
          <span class="rules-target-copy"><strong>${esc(cardName(item.cardId))}</strong><span>${esc(`${t("rulesStackTitle")} · ${rulesPlayerName(item.controllerId)}`)}</span></span>
        </label>`
      : `<label class="rules-target-choice" title="${esc(item.isTokenCard && !item.isCopy ? t("token") : cardName(item.cardId))}">
          <input type="${targetInputType}" name="rules-action-target" value="${esc(item.key)}" data-target-kind="${esc(item.kind)}" data-item-id="${esc(item.id || "")}" data-container-id="${esc(item.containerId || "")}" data-zone="${esc(item.zone)}" data-card-id="${esc(item.cardId || "")}">
          <img src="${esc(item.isTokenCard && !item.isCopy ? temperamentSymbol(item.temperament) : cardImage(item.cardId))}" alt="">
          <span class="rules-target-copy"><strong>${esc(item.isTokenCard && !item.isCopy ? `${t("token")} · ${item.effectivePower ?? item.power}` : cardName(item.cardId))}</strong><span>${esc(item.kind === "zone_card" ? `${rulesPlayerName(item.containerId)} · ${t(item.zone)}` : rulesPlayerName(item.ownerId))}</span></span>
        </label>`).join("")
    : `<span class="rules-target-empty">${esc(t("rulesNoLegalTargets"))}</span>`;

  const {
    paymentRequirements, hasPrintedTribute, essencePlan,
    essenceCostRequirements, essenceCostPlan, remainingTemperaments, manifestations,
  } = draft;
  const tributeFieldset = $("#rulesTributeList").closest("fieldset");
  const hasEssenceCost = Object.keys(essenceCostRequirements || {}).length > 0;
  tributeFieldset.classList.toggle(
    "hidden",
    ["hand", "graveyard"].includes(source.zone) && !hasPrintedTribute && !hasEssenceCost,
  );
  $("#rulesTributeSummary").classList.toggle(
    "hidden", !hasPrintedTribute && !hasEssenceCost,
  );
  if (hasPrintedTribute) {
    $("#rulesTributeSummary").innerHTML = `
      <span><strong>${esc(t("rulesTributeRequired"))}</strong>${rulesTributeUnitsHtml(paymentRequirements, t("rulesNone"))}</span>
      <span><strong>${esc(t("rulesEssenceUsed"))}</strong>${rulesTributeUnitsHtml(essencePlan.spent, t("rulesNoEssenceUsed"))}</span>
      <span><strong>${esc(t("rulesTributeRemaining"))}</strong>${rulesTributeUnitsHtml(essencePlan.remaining, t("rulesCoveredByEssence"))}</span>`;
  } else {
    $("#rulesTributeSummary").innerHTML = Object.keys(
      essenceCostRequirements || {},
    ).length
      ? `<span><strong>${esc(t("essence"))}</strong>${rulesTributeUnitsHtml(essenceCostRequirements, t("rulesNone"))}</span>
         <span><strong>${esc(t("rulesEssenceUsed"))}</strong>${rulesTributeUnitsHtml(essenceCostPlan.spent, t("rulesNoEssenceUsed"))}</span>`
      : "";
  }

  $("#rulesTributeList").innerHTML = manifestations.length
    ? manifestations.map(({ cardId, index, paymentValue, zone, sacrifice }) => {
        const tribute = cardsById.get(cardId);
        const temperament = tribute?.temperaments?.[0];
        const power = zone === "interzone"
          ? rulesTributeCandidate(paymentValue)?.power
          : tribute?.power;
        return `<label class="rules-tribute-choice" title="${esc(cardName(cardId))}"><input type="checkbox" value="${esc(paymentValue)}" ${Number.isInteger(index) ? `data-hand-index="${index}"` : ""}>${temperament ? `<img src="${esc(temperamentSymbol(temperament))}" alt="">` : ""}<span>${esc(cardName(cardId))} · ${esc(rulesText("rulesPowerValue", { power: power ?? "—" }))}${sacrifice ? ` · ${esc(t("rulesSacrificeLabel"))}` : zone === "graveyard" ? ` · ${esc(t("graveyard"))}` : zone === "receptacle" ? ` · ${esc(t("receptacle"))}` : zone === "interzone" ? ` · ${esc(t("interzone"))}` : ""}</span></label>`;
      }).join("")
    : `<span class="rules-tribute-empty">${esc(hasPrintedTribute && !remainingTemperaments.length ? t("rulesCoveredByEssence") : t("rulesNoTributeCards"))}</span>`;

  $("#rulesActionKindLabel").textContent = t("rulesActionKindLabel");
  $("#rulesActionDescriptionLabel").textContent = t("rulesActionDescriptionLabel");
  $("#rulesActionTargetLabel").textContent = t("rulesActionTargetLabel");
  $("#rulesActionTarget").placeholder = t("rulesActionTargetPlaceholder");
  $("#rulesTargetLegend").textContent = t(structuredTargetKind === "player"
    ? "rulesPlayerTargetLegend"
    : structuredTargetKind === "stack_action"
      ? "rulesStackTargetLegend"
    : ["stack_effect", "stack_item"].includes(structuredTargetKind)
      ? "rulesStackEffectTargetLegend"
    : allowedTargetZones.some((zone) => zone !== "battlefield")
      ? "rulesStructuredTargetLegend" : "rulesTargetLegend");
  $("#rulesTargetHint").textContent = t(noTargetRequired ? "rulesNoTargetRequired" : encodedAbility ? "rulesEncodedTargetHint" : "rulesTargetHint");
  $("#rulesActionCostLabel").textContent = t("rulesActionCostLabel");
  $("#rulesActionCostNote").placeholder = t("rulesActionCostPlaceholder");
  $("#rulesTributeLegend").textContent = t("rulesTributeLegend");
  $("#rulesTributeHint").textContent = t(hasPrintedTribute ? "rulesTributeAutomaticHint" : "rulesTributeHint");
  $("#rulesActionWarning").textContent = t(
    encodedAbility?.result
      ? "rulesEncodedAutomaticWarning"
      : encodedAbility ? "rulesEncodedAbilityWarning" : "rulesActionManualWarning"
  );
  $("#rulesActionCancelBtn").textContent = t("cancel");
  $("#rulesActionCloseBtn").title = t("close");
  $("#rulesActionCloseBtn").setAttribute("aria-label", t("close"));
  $("#rulesActionDeclareBtn").textContent = t("rulesDeclareAction");
  $("#rulesActionPanel").classList.remove("hidden");
  $("#rulesActionDescription").focus();
}

function rulesActionContextItem(source) {
  const rules = latestState?.rulesEngine;
  if (source.zone === "hand" && trapPlayableClient(source.cardId)) {
    return {
      label: t("rulesPlayTrap"),
      onSelect: () => send({ type: "play_first_manifestation_trap", cardId: source.cardId }),
    };
  }
  if (!rules?.enabled || rules.priorityPlayerId !== myPlayerId || isObserver || rulesImmediateEffectPendingClient() || rulesEndActionsSkippedClient()) return null;
  if (["hand", "suspended"].includes(source.zone)) {
    const cardType = rulesPlayType(cardsById.get(source.cardId));
    const handAbility = source.zone === "hand"
      ? (activatedAbilitiesByCard.get(source.cardId) || []).find(
          (ability) => (ability.sourceZones || []).includes("hand"),
        )
      : null;
    if (handAbility) {
      if (!rulesZoneActivatedActionDraft(source, handAbility)) return null;
      return {
        label: rulesText("rulesActivateCardEffect", { card: cardName(source.cardId) }),
        onSelect: () => beginRulesHandActivatedAction(
          source.cardId, source.handIndex,
        ),
      };
    }
    if (!handCardIsPlayable(source.cardId, source)) return null;
    const phaseId = currentPhaseUi().phase?.id;
    if (cardType === "ephemeral_will" && !rulesEphemeralPhasesClient(cardsById.get(source.cardId)).includes(phaseId)) return null;
    if (
      cardType === "persistent_will"
      && phaseId !== "end_actions"
      && !(
        phaseId === "confrontation_before_revelation"
        && rulesBeforeRevelationPlayClient(cardsById.get(source.cardId))
      )
      && !(
        ["confrontation_reaction", "resolution_effects"].includes(phaseId)
        && rulesPersistentWillsAsEphemeralClient()
      )
    ) return null;
    if (!["ephemeral_will", "persistent_will"].includes(cardType)) return null;
  }
  if (
    source.zone === "battlefield"
    && !["confrontation_reaction", "resolution_effects", "end_actions"].includes(currentPhaseUi().phase?.id)
  ) return null;
  // free-form declaration: a debug fallback, left out of the UI beta
  return { debug: true, label: t("rulesDeclareCardAction"), onSelect: () => openRulesActionPanel(source) };
}

const LANGUAGE_FLAGS = { fr: "🇫🇷", en: "🇬🇧", it: "🇮🇹" };

const LANGUAGE_NAMES = { fr: "Français", en: "English", it: "Italiano" };
