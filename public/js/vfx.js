// Rules visual effects, sound volume and animation speed.
// Loaded before app.js: declarations only, nothing runs at load time.

// ---------------------------------------------------------------- assisted-rules visual feedback

function rulesVfxCenter(element) {
  if (!element) return null;
  const rect = element.getBoundingClientRect();
  if (!rect.width && !rect.height) return null;
  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
}

function rulesVfxPlayerOrigin(playerId) {
  const player = latestState?.players?.[playerId];
  const mine = playerId === myPlayerId || (player && player.seat === mySeat());
  return { x: window.innerWidth / 2, y: mine ? window.innerHeight - 92 : 108 };
}

function rulesVfxStackTarget() {
  return rulesVfxCenter($("#rulesStackList [data-stack-action-id]"))
    || rulesVfxCenter($("#rulesStackPanel"))
    || { x: window.innerWidth / 2, y: window.innerHeight / 2 };
}

function rulesVfxStackNoticeTarget() {
  const panel = $("#rulesStackPanel")?.getBoundingClientRect();
  return panel?.width
    ? { x: panel.left + panel.width / 2, y: Math.max(30, panel.top - 8) }
    : rulesVfxStackTarget();
}

function rulesVfxFindBattlefieldItem(itemId) {
  if (!itemId) return null;
  return $$(".bf-card[data-item-id]").find((element) => element.dataset.itemId === itemId) || null;
}

function rulesVfxDeclaredTargetElement(declared) {
  if (!declared) return null;
  if (declared.kind === "card") return rulesVfxFindBattlefieldItem(declared.itemId || declared.id);
  try {
    return rulesTargetElement(declared);
  } catch {
    return null;
  }
}

// Cards leaving the Confrontation Zone at the end of the Resolution: where each
// one is now (the board has not been redrawn yet) and the pile it is heading to.
function collectRulesVfxCleanupMoves(details, fallback) {
  const movements = [...(details.captured || []), ...(details.returned || []), ...(details.supportExiled || [])];
  const moves = [];
  movements.forEach((movement) => {
    if (!movement?.itemId || !["moved", "removed_copy"].includes(movement.status)) return;
    const originElement = rulesVfxFindBattlefieldItem(movement.itemId);
    const origin = rulesVfxCenter(originElement);
    if (!origin) return;
    const originRect = originElement.getBoundingClientRect();
    const zone = movement.zone || (movement.status === "removed_copy" ? "exile" : "");
    const containerId = movement.containerId || movement.ownerId;
    const pile = $$("[data-field-pile]").find((element) => element.dataset.fieldPile === `${containerId}:${zone}`);
    const cardId = movement.cardId || (latestState?.battlefield || []).find((item) => item.id === movement.itemId)?.cardId;
    moves.push({
      cardId, zone, removedCopy: movement.status === "removed_copy", origin,
      originSize: originRect.width ? { width: originRect.width, height: originRect.height } : null,
      target: rulesVfxCenter(pile) || (zone === "hand" ? rulesVfxPlayerOrigin(containerId) : fallback),
    });
  });
  return moves;
}

function captureRulesVfxEvent(entry) {
  const event = captureRulesVfxEventInner(entry);
  if (entry.type === "rules_confrontation_cleanup") {
    (event.cleanupMoves || []).slice(0, 12).filter((move) => !move.removedCopy).forEach((move) => rulesVfxHoldCard(move.cardId, move.origin, move.originSize));
    if (event.supportWin) rulesVfxHoldCard(event.supportWin.cardId, event.supportWin.origin);
  }
  return event;
}

function captureRulesVfxEventInner(entry) {
  const details = entry.details || {};
  if (["draw", "draw_to_limit"].includes(entry.type)) {
    return { entry, manualDraw: {
      count: Math.min(5, Math.max(0, Number(details.count) || 0)),
      origin: rulesVfxManualZoneCenter(entry.actorId, "deck"),
      target: rulesVfxManualZoneCenter(entry.actorId, "hand"),
    } };
  }
  if (["move_card", "remove_battlefield_item"].includes(entry.type)) {
    const item = entry.type === "remove_battlefield_item"
      ? (latestState?.battlefield || []).find((item) => item.id === details.itemId) : null;
    const origin = item ? rulesVfxCenter(rulesVfxFindBattlefieldItem(item.id))
      : rulesVfxManualZoneCenter(details.fromOwnerId, details.fromZone);
    // Use the authoritative movement, never another copy already in a pile.
    return { entry, manualMove: origin && details.toZone ? {
      itemId: item?.id, cardId: details.cardId || (item?.faceUp ? item.cardId : null),
      origin, target: rulesVfxManualZoneCenter(details.toOwnerId, details.toZone),
    } : null };
  }
  const fallback = rulesVfxPlayerOrigin(entry.actorId);
  const tributeOrigins = [];
  const handCards = $$('[data-hand-card]');
  const usedHandCards = new Set();
  for (const cardId of details.cost?.tributeCardIds || []) {
    const element = handCards.find((candidate) => candidate.dataset.handCard === cardId && !usedHandCards.has(candidate));
    if (element) usedHandCards.add(element);
    tributeOrigins.push({ cardId, origin: rulesVfxCenter(element) || fallback });
  }
  const essenceOrigins = (details.cost?.essenceSpent || []).map((payment) => {
    const element = $$(".bf-token[data-token-id]").find((candidate) => candidate.dataset.tokenId === payment.tokenId);
    return { ...payment, origin: rulesVfxCenter(element) || fallback };
  });
  const sourceElement = rulesVfxFindBattlefieldItem(details.source?.itemId);
  const sacrificedCard = details.cost?.sacrificedCards?.[0] || null;
  const sacrificePile = sacrificedCard
    ? $$("[data-field-pile]").find((element) => element.dataset.fieldPile === `${sacrificedCard.ownerId}:graveyard`)
    : null;
  const scorePile = details.effectResult?.kind === "score"
    ? $$("[data-field-pile]").find((element) => element.dataset.fieldPile === `${details.effectResult.playerId}:receptacle`)
    : null;
  const effectTarget = entry.type === "rules_choice_resolved"
    ? (details.kind === "chain_manifestation"
      ? (rulesVfxFindBattlefieldItem(details.itemId) || rulesVfxPlayerOrigin(details.playerId))
      : details.kind === "stack_counter_payment"
        ? rulesVfxCenter($$("#rulesStackList [data-stack-action-id]")
          .find((element) => element.dataset.stackActionId === details.targetActionId)) || rulesVfxStackTarget()
        : rulesVfxPlayerOrigin(details.playerId))
    : details.effectResult?.kind === "draw"
    ? rulesVfxPlayerOrigin(details.effectResult.playerId)
    : rulesVfxCenter(scorePile);
  const moveResult = details.effectResult?.kind === "move_card" ? details.effectResult : null;
  const moveSource = moveResult ? rulesVfxFindBattlefieldItem(moveResult.itemId) : null;
  const moveSourcePile = moveResult?.fromContainerId && moveResult?.fromZone
    ? $$('[data-field-pile]').find((element) => element.dataset.fieldPile === `${moveResult.fromContainerId}:${moveResult.fromZone}`)
    : null;
  const movePile = moveResult?.ownerId && moveResult?.toZone
    ? $$('[data-field-pile]').find((element) => element.dataset.fieldPile === `${moveResult.ownerId}:${moveResult.toZone}`)
    : null;
  // Shattering the Self reports the targeted player whose deck was discarded
  const deckDiscardResult = ["discard_deck", "deck_discard_then_weaken"].includes(details.effectResult?.kind) ? details.effectResult : null;
  const deckDiscardSource = deckDiscardResult?.playerId
    ? $$('[data-field-pile]').find((element) => element.dataset.fieldPile === `${deckDiscardResult.playerId}:deck`)
    : null;
  const deckDiscardTarget = deckDiscardResult?.playerId
    ? $$('[data-field-pile]').find((element) => element.dataset.fieldPile === `${deckDiscardResult.playerId}:graveyard`)
    : null;
  const supportWinResult = (details.supportResolved || []).find((result) => (
    result.kind === "opponent_vessel_score" || result.kind === "opponent_vessel"
  )) || null;
  const supportWinSource = supportWinResult ? rulesVfxFindBattlefieldItem(supportWinResult.itemId) : null;
  const supportWinTarget = supportWinResult?.playerId
    ? $$('[data-field-pile]').find((element) => element.dataset.fieldPile === `${supportWinResult.playerId}:receptacle`)
    : null;
  const sourceHandCard = details.source?.zone === "hand"
    ? handCards.find((candidate) => candidate.dataset.handCard === details.source.cardId)
    : null;
  const spotlightOrigin = entry.type === "rules_action_declared"
    ? rulesVfxCenter(sourceHandCard) || rulesVfxCenter(sourceElement) || fallback
    : null;
  const declaredTargets = entry.type === "rules_action_declared"
    ? (details.targets || []).map((declared) => {
      const element = rulesVfxDeclaredTargetElement(declared);
      return { declared, point: rulesVfxCenter(element) };
    })
    : [];
  const stateDestroyed = entry.type === "rules_action_resolved"
    ? (details.stateActions?.destroyed || [])
      .filter((movement) => movement?.cardId)
      .slice(0, 8)
      .map((movement) => ({
        cardId: movement.cardId,
        origin: rulesVfxCenter(rulesVfxFindBattlefieldItem(movement.itemId)) || rulesVfxPlayerOrigin(movement.ownerId),
        target: rulesVfxPileCenter(movement.ownerId, "graveyard") || rulesVfxPlayerOrigin(movement.ownerId),
        removedCopy: movement.status === "removed_copy",
      }))
    : [];
  // a mass exile (Volcano): remember where every exiled card stood before the board re-renders
  const massExiled = entry.type === "rules_action_resolved" && details.effectResult?.kind === "exile_all_wills_and_interzones"
    ? (details.effectResult.itemIds || []).slice(0, 14).map((itemId) => {
      const element = rulesVfxFindBattlefieldItem(itemId);
      const image = element?.querySelector("img")?.getAttribute("src");
      return element && image ? { image, origin: rulesVfxCenter(element) } : null;
    }).filter(Boolean)
    : [];
  return {
    entry,
    stateDestroyed,
    massExiled,
    cleanupMoves: entry.type === "rules_confrontation_cleanup" ? collectRulesVfxCleanupMoves(details, fallback) : [],
    spotlightOrigin,
    declaredTargets,
    tributeOrigins,
    essenceOrigins,
    sourceRect: sourceElement?.getBoundingClientRect?.().toJSON?.() || (sourceElement ? sourceElement.getBoundingClientRect() : null),
    sacrifice: sacrificedCard ? {
      cardId: sacrificedCard.cardId,
      origin: rulesVfxCenter(sourceElement) || fallback,
      target: rulesVfxCenter(sacrificePile) || fallback,
    } : null,
    effectTarget,
    movedCard: moveResult ? {
      ...moveResult,
      origin: rulesVfxCenter(moveSource) || rulesVfxCenter(moveSourcePile) || fallback,
      target: rulesVfxCenter(movePile) || fallback,
    } : null,
    deckDiscard: deckDiscardResult ? {
      ...deckDiscardResult,
      origin: rulesVfxCenter(deckDiscardSource) || fallback,
      target: rulesVfxCenter(deckDiscardTarget) || fallback,
    } : null,
    supportWin: supportWinResult ? {
      ...supportWinResult,
      origin: rulesVfxCenter(supportWinSource) || fallback,
      target: rulesVfxCenter(supportWinTarget) || rulesVfxPlayerOrigin(supportWinResult.playerId),
    } : null,
  };
}

function prepareRulesVfxBatch(nextState) {
  const entries = [...(nextState?.recentLog || [])]
    .filter((entry) => Number.isFinite(Number(entry.sequence)))
    .sort((a, b) => Number(a.sequence) - Number(b.sequence));
  const newest = entries.length ? Number(entries[entries.length - 1].sequence) : 0;
  if (lastRulesVfxSequence === null || newest < lastRulesVfxSequence) {
    lastRulesVfxSequence = newest;
    return [];
  }
  const fresh = entries.filter((entry) => Number(entry.sequence) > lastRulesVfxSequence);
  lastRulesVfxSequence = Math.max(lastRulesVfxSequence, newest);
  return fresh
    .filter((entry) => ["draw", "draw_to_limit", "move_card", "remove_battlefield_item", "rules_action_declared", "rules_action_triggered", "rules_action_resolved", "rules_choice_resolved", "rules_confrontation_cleanup", "rules_phase_advanced", "rules_confrontation_compared", "recovery_draw"].includes(entry.type))
    .map(captureRulesVfxEvent);
}

function prepareRulesEffectVfxChanges(nextState) {
  if (!latestState?.rulesEngine || lastRulesVfxSequence === null) return [];
  const previous = new Map(
    (latestState.rulesEngine.ongoingEffects || [])
      .filter((effect) => effect?.id)
      .map((effect) => [effect.id, effect]),
  );
  const incoming = new Map(
    (nextState?.rulesEngine?.ongoingEffects || [])
      .filter((effect) => effect?.id)
      .map((effect) => [effect.id, effect]),
  );
  const changes = [];
  for (const [effectId, effect] of incoming) {
    if (!previous.has(effectId)) changes.push({ kind: "added", effect });
  }
  for (const [effectId, effect] of previous) {
    if (incoming.has(effectId)) continue;
    const target = rulesVfxCenter(rulesVfxFindBattlefieldItem(effect.target?.itemId));
    if (target) changes.push({ kind: "removed", effect, target, tone: rulesEffectTone(effect) });
  }
  return changes;
}

function removeRulesVfx() {
  clearRulesVfxQueue();
  for (const timer of rulesVfxDelayedTimers) window.clearTimeout(timer);
  rulesVfxDelayedTimers.clear();
  for (const cardId of [...rulesVfxHolds.keys()]) rulesVfxReleaseHold(cardId);
  if (handDrawLockTimer) window.clearTimeout(handDrawLockTimer);
  handDrawLockTimer = null;
  handDrawLockUntil = 0;
  document.body.classList.remove("hand-drawing");
  document.querySelectorAll('body > [class^="rules-vfx-"], body > .vfx-particle, body > .score-float').forEach((node) => node.remove());
  rulesVfxActiveLabels.length = 0;
  $$(".rules-vfx-spotlight, .rules-vfx-resolve-reveal, .rules-vfx-target-arrow, .rules-vfx-phase-banner, .rules-vfx-flight, .rules-vfx-impact, .rules-vfx-exhaust-ring, .rules-vfx-exhaust-label, .rules-vfx-impact-burst, .rules-vfx-target-lock, .rules-vfx-effect-cast, .rules-vfx-effect-seal, .rules-vfx-effect-release, .rules-vfx-stack-pulse")
    .forEach((element) => element.remove());
}

const rulesVfxDelayedTimers = new Set();

function setRulesVfxTimeout(callback, delay) {
  const timer = window.setTimeout(() => {
    rulesVfxDelayedTimers.delete(timer);
    callback();
  }, delay);
  rulesVfxDelayedTimers.add(timer);
  return timer;
}

// ---------------------------------------------------------------- VFX pacing
// Every rules VFX goes through this clock: a per-viewer speed preference
// scales every duration/delay, and a queue plays one log event at a time so
// labels and flights never pile up on top of each other.
const VFX_SPEED_KEY = "ko_vfx_speed";

const VFX_SPEEDS = ["fast", "normal", "slow"];

const VFX_SPEED_SCALE = { fast: 1, normal: 1.4, slow: 1.9 };

const rulesVfxQueue = [];

let rulesVfxQueueTimer = null;

let rulesVfxQueueBusyUntil = 0;

function vfxScale() {
  // when the table runs ahead (auto-passed phases, chained resolutions),
  // catch up instead of replaying a long backlog at full length
  const backlog = rulesVfxQueue.length;
  const pressure = backlog > 5 ? .45 : backlog > 2 ? .7 : 1;
  return (VFX_SPEED_SCALE[vfxSpeed] || 1.4) * pressure * (vfxEffectPaceUntil > performance.now() ? VFX_EFFECT_PACE : 1);
}

// card-effect animations (resolutions, triggers, recovery draw) run a bit slower than the rest
const VFX_EFFECT_PACE = 1.4;

const VFX_EFFECT_PACE_TYPES = ["rules_action_resolved", "rules_action_triggered", "rules_choice_resolved", "recovery_draw"];

let vfxEffectPaceUntil = 0;

function vfxMs(ms) {
  return Math.round(Number(ms || 0) * vfxScale());
}

function vfxTiming(options = {}) {
  return {
    ...options,
    duration: vfxMs(options.duration),
    delay: vfxMs(options.delay),
  };
}

function vfxAnimate(element, keyframes, options = {}) {
  return element.animate(keyframes, vfxTiming(options));
}

function rulesVfxQueueRemaining() {
  const pending = rulesVfxQueue.reduce((sum, beat) => sum + vfxMs(beat.estimate), 0);
  return Math.max(0, rulesVfxQueueBusyUntil - performance.now()) + pending;
}

function enqueueRulesVfx(play, estimate = 600) {
  rulesVfxQueue.push({ play, estimate });
  if (!rulesVfxQueueTimer) runRulesVfxQueue();
}

function runRulesVfxQueue() {
  rulesVfxQueueTimer = null;
  const beat = rulesVfxQueue.shift();
  if (!beat) {
    rulesVfxQueueBusyUntil = 0;
    return;
  }
  let length = 0;
  try {
    if (!$("#gameScreen").classList.contains("hidden")) length = vfxMs(beat.play() || 0);
  } catch (error) {
    console.error(error);
  }
  rulesVfxQueueBusyUntil = performance.now() + length;
  rulesVfxQueueTimer = window.setTimeout(runRulesVfxQueue, length);
}

function clearRulesVfxQueue() {
  rulesVfxQueue.length = 0;
  if (rulesVfxQueueTimer) window.clearTimeout(rulesVfxQueueTimer);
  rulesVfxQueueTimer = null;
  rulesVfxQueueBusyUntil = 0;
}

function vfxSpeedLabel() {
  return `${t("vfxSpeedLabel")} : ${t(`vfxSpeed_${vfxSpeed}`)}`;
}

function applyVfxSpeedPreference() {
  document.documentElement.style.setProperty("--vfx-scale", String(VFX_SPEED_SCALE[vfxSpeed] || 1.4));
  const button = $("#vfxSpeedBtn");
  if (button) button.textContent = vfxSpeedLabel();
}
function applySoundPreference() {
  const button = $("#soundToggleBtn");
  const slider = $("#soundVolumeSlider");
  const output = $("#soundVolumeValue");
  const on = window.KKOAudio?.isEnabled() !== false;
  const volume = Math.round((window.KKOAudio?.getVolume?.() ?? 1) * 100);
  const displayedVolume = on ? volume : 0;
  if (button) {
    button.textContent = t(on ? "soundOn" : "soundOff");
    button.setAttribute("aria-pressed", String(on));
  }
  if (slider) {
    slider.value = String(displayedVolume);
    slider.setAttribute("aria-label", t("soundVolume"));
    slider.setAttribute("aria-valuetext", `${displayedVolume}%`);
  }
  if (output) output.value = `${displayedVolume}%`;
}
function initSoundToggle() {
  const button = $("#soundToggleBtn");
  const slider = $("#soundVolumeSlider");
  applySoundPreference();
  if (button) {
    button.onclick = () => {
      window.KKOAudio?.toggle();
      applySoundPreference();
    };
  }
  if (slider) {
    slider.oninput = () => {
      const volume = Math.max(0, Math.min(100, Number(slider.value))) / 100;
      if (volume > 0) {
        window.KKOAudio?.setVolume(volume);
        window.KKOAudio?.setEnabled(true);
      } else {
        window.KKOAudio?.setEnabled(false);
      }
      applySoundPreference();
    };
  }
}









function initVfxSpeedToggle() {
  const button = $("#vfxSpeedBtn");
  applyVfxSpeedPreference();
  if (!button) return;
  button.onclick = () => {
    vfxSpeed = VFX_SPEEDS[(VFX_SPEEDS.indexOf(vfxSpeed) + 1) % VFX_SPEEDS.length];
    try { localStorage.setItem(VFX_SPEED_KEY, vfxSpeed); } catch {}
    applyVfxSpeedPreference();
  };
}

function rulesVfxAnimateAndRemove(element, keyframes, options) {
  const animation = element.animate(keyframes, { fill: "both", ...vfxTiming(options) });
  animation.finished.catch(() => {}).finally(() => element.remove());
  return animation;
}

function rulesVfxReducedMotion() {
  return Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches);
}

function playRulesVfxPulse(target, tone = "resolved", options = {}) {
  if (!target) return;
  const element = document.createElement("div");
  element.className = `rules-vfx-impact-burst rules-vfx-impact-burst-${tone}`;
  element.setAttribute("aria-hidden", "true");
  element.style.left = `${target.x}px`;
  element.style.top = `${target.y}px`;
  element.style.setProperty("--vfx-burst-tone", options.color || "");
  document.body.appendChild(element);
  const reduced = rulesVfxReducedMotion();
  rulesVfxAnimateAndRemove(element, [
    { transform: "translate(-50%,-50%) scale(.34)", opacity: 0 },
    { offset: .22, transform: "translate(-50%,-50%) scale(.76)", opacity: .95 },
    { transform: `translate(-50%,-50%) scale(${reduced ? 1.05 : 1.7})`, opacity: 0 },
  ], {
    duration: reduced ? 320 : 560,
    delay: Number(options.delay || 0),
    easing: "cubic-bezier(.16,1,.3,1)",
  });
}

// ---- Particle engine: one look per temperament (embers, spores, glass, mist, sparks, dust, light)
const VFX_PARTICLE_STYLES = {
  choleric: { shape: "ember", colors: ["#fff1a8", "#ff8a2a", "#d9381a"], rise: true },
  phlegmatic: { shape: "spore", colors: ["#e4ffc4", "#7bcf6a", "#3d8a45"], rise: true },
  vitreous: { shape: "shard", colors: ["#e3f6ff", "#7fc4ff", "#3a7cc4"], rise: false },
  melancholic: { shape: "mist", colors: ["#ead4ff", "#a06be0", "#5b2f94"], rise: true },
  capricious: { shape: "spark", colors: ["#fffbd0", "#ffe14a", "#ffb300"], rise: false },
  hollow: { shape: "dust", colors: ["#e6e6e6", "#a3a3a3", "#6e6e6e"], rise: true },
  transcendent: { shape: "light", colors: ["#ffffff", "#fff3c4", "#f1d377"], rise: true },
};

function vfxParticleStyle(temperament) {
  return VFX_PARTICLE_STYLES[temperament] || VFX_PARTICLE_STYLES.hollow;
}

// A burst of tinted particles around a point; direction "up" rises, "down" falls, "out" radiates
function spawnVfxParticles(center, temperament, options = {}) {
  if (!center || rulesVfxReducedMotion()) return;
  const style = options.style || vfxParticleStyle(temperament);
  const count = Math.min(36, Math.max(1, Math.round(Number(options.count || 8) * 1.4)));
  const spread = Number(options.spread || 34) * 1.5;
  const direction = options.direction || (style.rise ? "up" : "out");
  for (let index = 0; index < count; index += 1) {
    const particle = document.createElement("span");
    particle.className = `vfx-particle vfx-particle-${style.shape}`;
    particle.setAttribute("aria-hidden", "true");
    particle.style.left = `${center.x}px`;
    particle.style.top = `${center.y}px`;
    particle.style.setProperty("--p-color", style.colors[index % style.colors.length]);
    particle.style.setProperty("--p-size", `${7 + (index % 3) * 3}px`);
    document.body.appendChild(particle);
    const angle = (index / count) * Math.PI * 2 + (index % 3) * 0.5;
    const dx = Math.cos(angle) * spread * (0.5 + (index % 4) * 0.22);
    const dy = direction === "up"
      ? -(spread * (0.7 + (index % 4) * 0.35)) + Math.sin(angle) * 8
      : direction === "down"
        ? spread * (0.7 + (index % 4) * 0.35) + Math.sin(angle) * 8
        : Math.sin(angle) * spread * (0.5 + (index % 4) * 0.22);
    rulesVfxAnimateAndRemove(particle, [
      { transform: "translate(-50%,-50%) scale(.4) rotate(0deg)", opacity: 0 },
      { offset: .18, transform: `translate(calc(-50% + ${dx * .3}px), calc(-50% + ${dy * .3}px)) scale(1.1) rotate(${angle * 20}deg)`, opacity: 1 },
      { transform: `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px)) scale(.2) rotate(${angle * 60}deg)`, opacity: 0 },
    ], { duration: 640 + (index % 4) * 110, delay: Number(options.delay || 0) + (index % 6) * 26, easing: "cubic-bezier(.2,.7,.3,1)" });
  }
}

const VFX_CARD_FLIGHT_KINDS = ["tribute", "sacrifice", "effect-card", "destroy-card", "discard-card", "draw-card"];

// ---- Dedicated card scenes (one-off animations for iconic cards)
function rulesVfxBoardRect() {
  const rect = $("#battlefieldWrap")?.getBoundingClientRect?.();
  return rect?.width ? rect : { left: 0, top: 0, width: window.innerWidth, height: window.innerHeight };
}

function rulesVfxPileCenter(playerId, zone) {
  const key = `${playerId}:${zone}`;
  const pile = $$("[data-field-pile]").find((element) => element.dataset.fieldPile === key);
  if (pile?.closest(".ub-oppblock:not(.open)")) {
    return rulesVfxCenter($$("[data-pile-summary]").find((element) => element.dataset.pileSummary === key))
      || rulesVfxCenter($("#ubOppBar"));
  }
  return rulesVfxCenter(pile);
}

function rulesVfxManualZoneCenter(playerId, zone) {
  if (zone === "hand") {
    return rulesVfxCenter($(playerId === myPlayerId ? "#myHandTray" : "#opponentHandFan"))
      || rulesVfxPlayerOrigin(playerId);
  }
  return rulesVfxPileCenter(playerId, zone) || rulesVfxPlayerOrigin(playerId);
}

function rulesVfxOverlay(className, keyframes, duration, delay = 0) {
  const board = rulesVfxBoardRect();
  const overlay = document.createElement("div");
  overlay.className = `rules-vfx-scene ${className}`;
  overlay.setAttribute("aria-hidden", "true");
  Object.assign(overlay.style, { left: `${board.left}px`, top: `${board.top}px`, width: `${board.width}px`, height: `${board.height}px` });
  document.body.appendChild(overlay);
  rulesVfxAnimateAndRemove(overlay, keyframes, { duration, delay, easing: "ease-in-out" });
  return overlay;
}

const RULES_VFX_CARD_SCENES = {
  // mass destruction: a wave of fire sweeps the field
  "4naoqbqz6ebozj5_en": () => playRulesVfxFireWave("#ff7a2a", "#ffe08a"),
  "nupb1i59d98g3md_en": () => playRulesVfxFireWave("#d3a942", "#fff3c4"),
  // rematch: the board rewinds
  "s6mezxrq1zp2958_en": () => {
    const board = rulesVfxBoardRect();
    rulesVfxOverlay("rules-vfx-rewind", [
      { opacity: 0, transform: "rotate(0deg) scale(.4)" },
      { opacity: .95, transform: "rotate(-180deg) scale(1)", offset: .35 },
      { opacity: .95, transform: "rotate(-540deg) scale(1.1)", offset: .75 },
      { opacity: 0, transform: "rotate(-720deg) scale(1.5)" },
    ], 1900);
    spawnVfxParticles({ x: board.left + board.width / 2, y: board.top + board.height / 2 }, "transcendent", { count: 18, spread: 120, direction: "out", delay: 900 });
  },
  // hot potato: heat flash then a burst on the card
  "b4yyd5uut0ga9df_en": (entry, target) => {
    spawnVfxParticles(target, "choleric", { count: 18, spread: 60, direction: "out" });
    rulesVfxOverlay("rules-vfx-heat", [{ opacity: 0 }, { opacity: .55, offset: .3 }, { opacity: 0 }], 900);
  },
  // greed trap: the jaws snap shut
  "9phkl58pqrs2j2f_en": (entry, target) => {
    rulesVfxOverlay("rules-vfx-jaws", [{ opacity: 0 }, { opacity: 1, offset: .4 }, { opacity: 1, offset: .75 }, { opacity: 0 }], 1100);
    spawnVfxParticles(target, "vitreous", { count: 14, spread: 50, direction: "out", delay: 420 });
  },
  // soul-devouring dunes: sand pours over every Limbo
  "dc44xrlrhikfvlr_en": () => {
    Object.keys(latestState?.players || {}).forEach((playerId) => {
      const limbo = rulesVfxPileCenter(playerId, "graveyard");
      if (!limbo) return;
      for (let wave = 0; wave < 3; wave += 1) {
        spawnVfxParticles({ x: limbo.x, y: limbo.y - 60 }, "hollow", {
          count: 14, spread: 70, direction: "down", delay: wave * 260,
          style: { shape: "dust", colors: ["#f1d9a0", "#d8b878", "#a8875a"] },
        });
      }
    });
    rulesVfxOverlay("rules-vfx-sand", [{ opacity: 0 }, { opacity: .5, offset: .3 }, { opacity: 0 }], 1500);
  },
  // control swaps: the colours of the field invert for a moment
  "zk76fhtep0wm3hh_en": (entry) => playRulesVfxControlSwap(entry),
  "0ujeinffs84nrvq_en": (entry) => playRulesVfxControlSwap(entry),
  // omens: the top of the deck fans out
  "9yylrq6xancbn0m_en": (entry) => {
    const deck = rulesVfxPileCenter(entry.actorId, "deck");
    if (!deck) return;
    for (let index = 0; index < 3; index += 1) {
      playRulesVfxFlight("draw-card", deck, { x: deck.x + (index - 1) * 70, y: deck.y - 110 }, { index: index * 2, land: false });
    }
    spawnVfxParticles(deck, "transcendent", { count: 10, spread: 44, direction: "up" });
  },
  // traumatize: a dark red vignette crushes the screen while mist pours over the victim's hand
  "5r7g2e0r6q17lur_en": (entry) => {
    const victimId = entry.details?.targets?.find?.((declared) => declared.kind === "player")?.playerId
      || Object.keys(latestState?.players || {}).find((playerId) => playerId !== entry.actorId);
    rulesVfxOverlay("rules-vfx-trauma", [{ opacity: 0 }, { opacity: 1, offset: .25 }, { opacity: .8, offset: .6 }, { opacity: 0 }], 1500);
    const hand = rulesVfxPlayerOrigin(victimId);
    spawnVfxParticles(hand, "melancholic", { count: 20, spread: 100, direction: "out", delay: 250 });
    spawnVfxParticles(rulesVfxPlayerOrigin(entry.actorId), "choleric", { count: 10, spread: 60, direction: "up" });
  },
  // atavic oppression: purple mist chokes the opponent's hand, then the owner draws
  "a058t24med4h5nx_en": (entry) => {
    if (!String(entry.details?.ability?.result?.kind || "").startsWith("discard_hand")) return;
    const opponentId = Object.keys(latestState?.players || {}).find((playerId) => playerId !== entry.actorId);
    const hand = rulesVfxPlayerOrigin(opponentId);
    spawnVfxParticles(hand, "melancholic", { count: 22, spread: 90, direction: "down" });
    const deck = rulesVfxPileCenter(entry.actorId, "deck");
    const mine = rulesVfxPlayerOrigin(entry.actorId);
    if (deck) {
      playRulesVfxFlight("draw-card", deck, mine, { index: 6, land: false });
    }
  },
  // volcano: the field erupts, ash and embers rise from below
  "2xqczn7vzkm5n50_en": () => playRulesVfxEruption(),
  // rising from the Limbo
  "gpxqooqq57loyb8_en": (entry, target) => playRulesVfxRiseFromLimbo(entry, target),
  "z2fen73ktw8pbqz_en": (entry, target) => playRulesVfxRiseFromLimbo(entry, target),
};

function playRulesVfxFireWave(core, tip) {
  const board = rulesVfxBoardRect();
  const wave = rulesVfxOverlay("rules-vfx-firewave", [
    { transform: "translateX(-60%)", opacity: 0 },
    { transform: "translateX(-20%)", opacity: 1, offset: .2 },
    { transform: "translateX(60%)", opacity: 1, offset: .8 },
    { transform: "translateX(110%)", opacity: 0 },
  ], 1500);
  wave.style.setProperty("--wave-core", core);
  wave.style.setProperty("--wave-tip", tip);
  for (let step = 0; step < 6; step += 1) {
    spawnVfxParticles({ x: board.left + board.width * (0.1 + step * 0.16), y: board.top + board.height * 0.5 }, "choleric", {
      count: 8, spread: 70, direction: "up", delay: 180 + step * 190,
      style: { shape: "ember", colors: [tip, core, "#d9381a"] },
    });
  }
}

function playRulesVfxEruption() {
  const board = rulesVfxBoardRect();
  rulesVfxOverlay("rules-vfx-eruption", [
    { opacity: 0, transform: "translateY(35%)" },
    { opacity: 1, transform: "translateY(0)", offset: .3 },
    { opacity: .85, transform: "translateY(-8%)", offset: .7 },
    { opacity: 0, transform: "translateY(-20%)" },
  ], 1700);
  $("#battlefieldWrap")?.animate?.([
    { translate: "0 0" }, { translate: "-6px 3px", offset: .1 }, { translate: "5px -4px", offset: .2 },
    { translate: "-4px 2px", offset: .3 }, { translate: "3px -2px", offset: .4 }, { translate: "0 0" },
  ], vfxTiming({ duration: 900, delay: 120 }));
  for (let step = 0; step < 5; step += 1) {
    const point = { x: board.left + board.width * (0.12 + step * 0.19), y: board.top + board.height * 0.85 };
    spawnVfxParticles(point, "choleric", {
      count: 9, spread: 60, direction: "up", delay: 150 + step * 120,
      style: { shape: "ember", colors: ["#ffe08a", "#ff7a2a", "#c2311a"] },
    });
    spawnVfxParticles(point, "hollow", { count: 8, spread: 80, direction: "up", delay: 450 + step * 120 });
  }
}

// An exiled card: it glows, dissolves into pale ash and rises out of the game
function playRulesVfxExileDissolve(origin, image, delay = 0) {
  if (rulesVfxReducedMotion() || !origin || !image) return;
  const element = document.createElement("div");
  element.className = "rules-vfx-flight rules-vfx-wither-card";
  element.setAttribute("aria-hidden", "true");
  element.style.left = `${origin.x - 33}px`;
  element.style.top = `${origin.y - 46}px`;
  element.innerHTML = `<img src="${esc(image)}" alt="">`;
  document.body.appendChild(element);
  vfxAnimate(element, [
    { transform: "translate3d(0,0,0) scale(1)", filter: "brightness(1) sepia(0)", opacity: 1 },
    { offset: .3, transform: "translate3d(0,-2px,0) scale(1.04)", filter: "brightness(1.6) sepia(.8) saturate(2)", opacity: 1 },
    { offset: .65, transform: "translate3d(0,-14px,0) scale(.98)", filter: "brightness(1.2) grayscale(1) blur(1px)", opacity: .6 },
    { transform: "translate3d(0,-60px,0) scale(.9)", filter: "brightness(1.4) grayscale(1) blur(4px)", opacity: 0 },
  ], { duration: 1200, delay, fill: "both", easing: "ease-in" });
  spawnVfxParticles(origin, "hollow", { count: 12, spread: 40, direction: "up", delay: delay + 350 });
  window.setTimeout(() => element.remove(), vfxMs(delay + 1400));
}

function playRulesVfxRiseFromLimbo(entry, target) {
  const limbo = rulesVfxPileCenter(entry.actorId, "graveyard");
  if (!limbo || !target) return;
  spawnVfxParticles(limbo, "transcendent", { count: 14, spread: 40, direction: "up" });
  playRulesVfxFlight("effect-card", limbo, target, { cardId: entry.details?.effectResult?.cardId, index: 0 });
}

// Control swap: the effect's card in the middle of the screen, the two exchanged cards trade places over ~2 s, then the board follows
function playRulesVfxControlSwap(entry) {
  const details = entry?.details || {};
  const cardIds = (details.targets || details.action?.targets || [])
    .filter((target) => target?.kind === "card")
    .map((target) => target.cardId || rulesVfxFindBattlefieldItem(target.itemId)?.cardId)
    .filter(Boolean)
    .slice(0, 2);
  const sourceCardId = details.source?.cardId;
  if (cardIds.length < 2 || !sourceCardId) {
    rulesVfxOverlay("rules-vfx-invert", [{ opacity: 0 }, { opacity: 1, offset: .25 }, { opacity: 1, offset: .5 }, { opacity: 0 }], 900);
    return;
  }
  const stage = document.createElement("div");
  stage.className = "rules-vfx-swap-stage";
  stage.setAttribute("aria-hidden", "true");
  stage.innerHTML = `
    <img class="rules-vfx-swap-source" src="${esc(cardImage(sourceCardId))}" alt="">
    <div class="rules-vfx-swap-row">
      <img class="rules-vfx-swap-card" src="${esc(cardImage(cardIds[0]))}" alt="">
      <img class="rules-vfx-swap-card" src="${esc(cardImage(cardIds[1]))}" alt="">
    </div>`;
  document.body.appendChild(stage);
  const total = vfxMs(2400);
  rulesVfxAnimateAndRemove(stage, [{ opacity: 0 }, { opacity: 1, offset: .12 }, { opacity: 1, offset: .88 }, { opacity: 0 }], { duration: total, easing: "ease-in-out" });
  const [left, right] = stage.querySelectorAll(".rules-vfx-swap-card");
  const gap = 190;
  const swap = (from, to) => [{ transform: "translateX(0) scale(1)" }, { transform: "translateX(0) scale(1)", offset: .3 }, { transform: `translateX(${to}px) translateY(-26px) scale(1.12)`, offset: .62 }, { transform: `translateX(${to}px) scale(1)`, offset: .75 }, { transform: `translateX(${to}px) scale(1)` }];
  left.animate(swap(0, gap), { duration: total, easing: "ease-in-out", fill: "both" });
  right.animate(swap(0, -gap).map((frame) => ({ ...frame, transform: frame.transform.replace("-26px", "26px") })), { duration: total, easing: "ease-in-out", fill: "both" });
  spawnVfxParticles({ x: window.innerWidth / 2, y: window.innerHeight * .68 }, "capricious", { count: 14, spread: 80, direction: "out", delay: total * .55 });
  rulesVfxQueueBusyUntil = Math.max(rulesVfxQueueBusyUntil, performance.now() + total);
}

// The card being resolved appears large for a moment, then flies to where it ends up
function playRulesVfxResolveReveal(entry, immediate = false) {
  const reduced = rulesVfxReducedMotion();
  if (reduced && !immediate) return;
  const details = entry.details || {};
  const cardId = details.source?.cardId;
  if ((!cardId || !cardImage(cardId)) && !immediate) return;
  const resolution = details.sourceResolution || {};
  const ownerId = resolution.ownerId || details.source?.ownerId || entry.actorId;
  const destination = resolution.itemId
    ? rulesVfxCenter(rulesVfxFindBattlefieldItem(resolution.itemId))
    : (resolution.destination === "graveyard" || resolution.destination === "exile")
      ? rulesVfxPileCenter(ownerId, resolution.destination)
      : null;
  const reveal = document.createElement("div");
  reveal.className = `rules-vfx-resolve-reveal${immediate ? " rules-vfx-immediate" : ""}`;
  if (immediate) reveal.setAttribute("role", "status");
  else reveal.setAttribute("aria-hidden", "true");
  reveal.innerHTML = cardId && cardImage(cardId) ? `<img src="${esc(cardImage(cardId))}" alt="">` : "";
  if (immediate) {
    reveal.innerHTML += `<div class="rules-vfx-immediate-caption"><strong>${esc(cardId ? cardName(cardId) : details.label || t("rulesVfxImmediate"))}</strong><span>${esc(t("rulesVfxImmediate"))}</span></div>`;
  }
  document.body.appendChild(reveal);
  const dx = destination ? destination.x - window.innerWidth / 2 : 0;
  const dy = destination ? destination.y - window.innerHeight / 2 : 0;
  // Even a long chain keeps a readable preview before an Immediate Effect's result.
  const duration = immediate ? Math.max(1600, 1500 / vfxScale()) : 1350;
  rulesVfxAnimateAndRemove(reveal, reduced ? [
    { opacity: 0 }, { opacity: 1, offset: .1 }, { opacity: 1, offset: .9 }, { opacity: 0 },
  ] : [
    { opacity: 0, transform: "translate(-50%,-50%) scale(.6)" },
    { opacity: 1, transform: "translate(-50%,-50%) scale(1)", offset: .1 },
    { opacity: 1, transform: "translate(-50%,-50%) scale(1)", offset: immediate ? .82 : .58 },
    { opacity: destination ? .9 : 0, transform: `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px)) scale(${destination ? .32 : 1.08})`, offset: destination ? .94 : 1 },
    { opacity: 0, transform: `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px)) scale(.3)` },
  ], { duration, easing: "ease-in-out" });
  return duration;
}

function playRulesVfxCardScene(entry, target) {
  if (rulesVfxReducedMotion()) return;
  const scene = RULES_VFX_CARD_SCENES[entry.details?.source?.cardId];
  if (scene) scene(entry, target);
}

// A six-sided die tumbles above the Stack and settles on the rolled value
function playRulesVfxDice(roll, anchor) {
  if (rulesVfxReducedMotion()) return;
  const die = document.createElement("div");
  die.className = "rules-vfx-die";
  die.setAttribute("aria-hidden", "true");
  die.innerHTML = `<span class="rules-vfx-die-face">${roll}</span>`;
  die.style.left = `${anchor.x}px`;
  die.style.top = `${anchor.y - 70}px`;
  document.body.appendChild(die);
  const face = die.querySelector(".rules-vfx-die-face");
  const tumble = vfxMs(900);
  const started = performance.now();
  const timer = window.setInterval(() => {
    if (performance.now() - started >= tumble) {
      face.textContent = String(roll);
      window.clearInterval(timer);
      return;
    }
    face.textContent = String(1 + Math.floor(Math.random() * 6));
  }, 70);
  rulesVfxAnimateAndRemove(die, [
    { transform: "translate(-50%,-50%) rotate(-240deg) scale(.4)", opacity: 0 },
    { offset: .15, transform: "translate(-50%,-50%) rotate(-120deg) scale(1.1)", opacity: 1 },
    { offset: .5, transform: "translate(-50%,-50%) rotate(20deg) scale(1)", opacity: 1 },
    { offset: .6, transform: "translate(-50%,-50%) rotate(0deg) scale(1.25)", opacity: 1 },
    { offset: .7, transform: "translate(-50%,-50%) rotate(0deg) scale(1)", opacity: 1 },
    { offset: .92, transform: "translate(-50%,-50%) rotate(0deg) scale(1)", opacity: 1 },
    { transform: "translate(-50%,-50%) rotate(0deg) scale(.8)", opacity: 0 },
  ], { duration: 2000, easing: "ease-out" }).finished.finally(() => window.clearInterval(timer));
  setRulesVfxTimeout(() => spawnVfxParticles({ x: anchor.x, y: anchor.y - 70 }, "capricious", { count: 10, spread: 40, direction: "out" }), vfxMs(1100));
}

// A card that is about to fly away stays visible at its place until its flight starts, so it never vanishes first
const rulesVfxHolds = new Map();

function rulesVfxHoldCard(cardId, origin, size = null) {
  if (!cardId || !origin || rulesVfxReducedMotion()) return;
  rulesVfxReleaseHold(cardId);
  const hold = document.createElement("div");
  hold.className = "rules-vfx-hold";
  hold.setAttribute("aria-hidden", "true");
  hold.innerHTML = `<img src="${esc(cardImage(cardId))}" alt="">`;
  // the size of the card it stands for (a small Stalemate strip card stays small)
  const width = size?.width || 104;
  const height = size?.height || 146;
  hold.style.width = `${width}px`;
  hold.style.height = `${height}px`;
  hold.style.left = `${origin.x - width / 2}px`;
  hold.style.top = `${origin.y - height / 2}px`;
  document.body.appendChild(hold);
  rulesVfxHolds.set(cardId, { hold, timer: window.setTimeout(() => rulesVfxReleaseHold(cardId), 45000) });
}

function rulesVfxReleaseHold(cardId) {
  const entry = rulesVfxHolds.get(cardId);
  if (!entry) return;
  window.clearTimeout(entry.timer);
  entry.hold.remove();
  rulesVfxHolds.delete(cardId);
}

// the winner chooses where their Manifestations go before anything flies to a pile
function rulesVfxAfterWinnerChoices(play, waited = 0) {
  const result = latestState?.rulesEngine?.confrontationResult;
  const waiting = latestState?.rulesEngine?.pendingChoice?.kind === "confrontation_destination"
    || (Array.isArray(result?.pendingOwnItemIds) && result.pendingOwnItemIds.length > 0);
  if (waiting && waited < 60000) {
    setRulesVfxTimeout(() => rulesVfxAfterWinnerChoices(play, waited + 300), 300);
    return;
  }
  play();
}

function playRulesVfxFlight(kind, origin, target, options = {}) {
  const element = document.createElement("div");
  element.className = `rules-vfx-flight rules-vfx-${kind}`;
  element.setAttribute("aria-hidden", "true");
  if (VFX_CARD_FLIGHT_KINDS.includes(kind)) {
    const flightImage = kind === "draw-card" ? "card-back.webp?v=20260905-1" : cardImage(options.cardId);
    element.innerHTML = `<div class="rules-vfx-flight-card"><img src="${esc(flightImage)}" alt=""><span class="rules-vfx-flight-glint"></span></div>`;
  } else {
    element.style.setProperty("--vfx-tone", temperamentInk(options.temperament));
    element.innerHTML = options.temperament
      ? `<img src="${esc(temperamentSymbol(options.temperament))}" alt="">`
      : "";
  }
  const isCard = VFX_CARD_FLIGHT_KINDS.includes(kind);
  const big = isCard && Boolean(options.big);
  if (options.cardId) rulesVfxReleaseHold(options.cardId);
  // flying cards read at the size of the cards on the board (draw-card had no size at all)
  const boardCardWidth = $(".bf-card[data-item-id]")?.getBoundingClientRect?.().width || 0;
  const cardWidth = Math.round(Math.min(110, Math.max(64, boardCardWidth || 72)));
  const cardSize = (factor) => ({ width: Math.round(cardWidth * factor), height: Math.round(cardWidth * factor * 1.4) });
  const size = !isCard
    ? { width: 34, height: 34 }
    : big
      ? cardSize(1.3)
      : ["tribute", "sacrifice"].includes(kind)
      ? cardSize(.85)
      : cardSize(1);
  element.style.width = `${size.width}px`;
  element.style.height = `${size.height}px`;
  element.style.left = `${origin.x - size.width / 2}px`;
  element.style.top = `${origin.y - size.height / 2}px`;
  document.body.appendChild(element);
  const dx = target.x - origin.x;
  const dy = target.y - origin.y;
  const distance = Math.max(1, Math.hypot(dx, dy));
  const arc = Math.min(118, 34 + distance * .13);
  const midX = dx * .5;
  const midY = dy * .5 - arc;
  const tilt = isCard ? (options.index % 2 ? 7 : -7) : 0;
  const duration = isCard ? (big ? 1150 : kind === "tribute" ? 500 : kind === "sacrifice" ? 540 : 660) : 470;
  rulesVfxAnimateAndRemove(element, [
    { transform: "translate3d(0,0,0) scale(.92) rotate(0deg)", opacity: 0 },
    { offset: .12, transform: `translate3d(${dx * .05}px,${dy * .05 - 9}px,0) scale(1.05) rotate(${-tilt * .35}deg)`, opacity: 1 },
    { offset: .68, transform: `translate3d(${midX}px,${midY}px,0) scale(.9) rotate(${tilt}deg)`, opacity: 1 },
    { transform: `translate3d(${dx}px,${dy}px,0) scale(.34) rotate(${tilt * 1.35}deg)`, opacity: 0 },
  ], { duration, delay: Number(options.index || 0) * 36, easing: "cubic-bezier(.22,.72,.2,1)" });
  if (options.land !== false) {
    playRulesVfxPulse(target, kind === "sacrifice" ? "destroyed" : kind === "discard-card" ? "discarded" : "moved", {
      delay: duration * .62 + Number(options.index || 0) * 36,
    });
  }
  // tinted trail and landing burst (family: movement)
  const flightTemperament = options.temperament || cardsById.get(options.cardId)?.colorKey || null;
  if (isCard && flightTemperament && !rulesVfxReducedMotion() && kind !== "draw-card") {
    const trailDelay = Number(options.index || 0) * 36;
    for (let step = 1; step <= 5; step += 1) {
      const progress = step / 6;
      const point = {
        x: origin.x + dx * progress,
        y: origin.y + dy * progress - Math.sin(Math.PI * progress) * arc * 0.9,
      };
      setRulesVfxTimeout(
        () => spawnVfxParticles(point, flightTemperament, { count: 2, spread: 14 }),
        vfxMs(trailDelay + duration * progress),
      );
    }
    setRulesVfxTimeout(
      () => spawnVfxParticles(target, flightTemperament, big ? { count: 20, spread: 70 } : { count: 8, spread: 36 }),
      vfxMs(trailDelay + duration * 0.7),
    );
  }
}

function playRulesVfxDestruction(origin, target, cardId) {
  if (rulesVfxReducedMotion()) return;
  const element = document.createElement("div");
  element.className = "rules-vfx-flight rules-vfx-destroy-card";
  element.setAttribute("aria-hidden", "true");
  element.style.left = `${origin.x - 33}px`;
  element.style.top = `${origin.y - 46}px`;
  const shardShapes = [
    "polygon(0 0,56% 0,43% 42%,0 50%)",
    "polygon(56% 0,100% 0,100% 44%,43% 42%)",
    "polygon(0 50%,43% 42%,55% 100%,0 100%)",
    "polygon(43% 42%,100% 44%,100% 100%,55% 100%)",
    "polygon(36% 28%,68% 18%,74% 76%,46% 84%)",
  ];
  element.innerHTML = `<div class="rules-vfx-destroy-core"><img src="${esc(cardImage(cardId))}" alt=""></div><span class="rules-vfx-destroy-flash"></span>${shardShapes.map((shape, index) => `<span class="rules-vfx-destruction-shard" style="--shard-shape:${shape};--shard-index:${index}"><img src="${esc(cardImage(cardId))}" alt=""></span>`).join("")}`;
  document.body.appendChild(element);
  const dx = target.x - origin.x;
  const dy = target.y - origin.y;
  const burstVectors = [[-30, -36], [34, -27], [-38, 20], [34, 30], [2, -44]];
  const core = element.querySelector(".rules-vfx-destroy-core");
  vfxAnimate(core, [
    { transform: "scale(.9)", filter: "brightness(1) saturate(1)", opacity: 0 },
    { offset: .28, transform: "scale(1.06)", filter: "brightness(1.55) saturate(1.4)", opacity: 1 },
    { transform: "scale(.96)", filter: "brightness(2) saturate(.4)", opacity: 0 },
  ], { duration: 260, fill: "both", easing: "cubic-bezier(.16,1,.3,1)" });
  element.querySelectorAll(".rules-vfx-destruction-shard").forEach((shard, index) => {
    const [bx, by] = burstVectors[index];
    vfxAnimate(shard, [
      { transform: "translate3d(0,0,0) rotate(0deg) scale(.96)", opacity: 0 },
      { offset: .2, transform: "translate3d(0,0,0) rotate(0deg) scale(1)", opacity: 1 },
      { offset: .48, transform: `translate3d(${bx}px,${by}px,0) rotate(${(index - 2) * 13}deg) scale(.92)`, opacity: 1 },
      { transform: `translate3d(${dx}px,${dy}px,0) rotate(${(index - 2) * 32}deg) scale(.12)`, opacity: 0 },
    ], { duration: 720, delay: index * 14, fill: "both", easing: "cubic-bezier(.2,.72,.2,1)" });
  });
  playRulesVfxPulse(origin, "destroyed", { delay: 110 });
  playRulesVfxPulse(target, "discarded", { delay: 520 });
  playRulesVfxBurn(element, origin);
  window.setTimeout(() => element.remove(), vfxMs(1500));
}

// Power surge on a card (Quorum): rings of rage, a burst of embers and a big +N above it
function playRulesVfxPowerSurge(gain) {
  const element = rulesVfxFindBattlefieldItem(gain.itemId);
  const center = rulesVfxCenter(element);
  if (!center) return;
  const value = Number(gain.value || 0);
  if (rulesVfxReducedMotion()) {
    playRulesVfxImpact(center, `${value >= 0 ? "+" : ""}${value}`, value >= 0 ? "score" : "score-loss");
    return;
  }
  const rect = element.getBoundingClientRect();
  const size = Math.max(rect.width, rect.height);
  for (let ring = 0; ring < 3; ring += 1) {
    const wave = document.createElement("div");
    wave.className = "rules-vfx-surge-ring";
    wave.setAttribute("aria-hidden", "true");
    Object.assign(wave.style, { left: `${center.x - size / 2}px`, top: `${center.y - size / 2}px`, width: `${size}px`, height: `${size}px` });
    document.body.appendChild(wave);
    vfxAnimate(wave, [
      { transform: "scale(.7)", opacity: 0 },
      { offset: .25, opacity: .95 },
      { transform: "scale(2.3)", opacity: 0 },
    ], { duration: 1100, delay: ring * 260, fill: "both", easing: "ease-out" });
    window.setTimeout(() => wave.remove(), vfxMs(1100 + ring * 260 + 200));
  }
  vfxAnimate(element, [
    { filter: "brightness(1)", transform: "scale(1)" },
    { offset: .3, filter: "brightness(1.8) saturate(1.5)", transform: "scale(1.12)" },
    { filter: "brightness(1)", transform: "scale(1)" },
  ], { duration: 900, easing: "ease-out" });
  spawnVfxParticles(center, "choleric", { count: 26, spread: 80, direction: "up" });
  playRulesVfxImpact(center, `${value >= 0 ? "+" : ""}${value}`, value >= 0 ? "score" : "score-loss", { delay: 150 });
}

// A card whose power fell to zero: it greys out, crumbles to dust and sinks to the graveyard
function playRulesVfxWither(origin, target, cardId) {
  if (rulesVfxReducedMotion()) return;
  const element = document.createElement("div");
  element.className = "rules-vfx-flight rules-vfx-wither-card";
  element.setAttribute("aria-hidden", "true");
  element.style.left = `${origin.x - 33}px`;
  element.style.top = `${origin.y - 46}px`;
  element.innerHTML = `<img src="${esc(cardImage(cardId))}" alt="">`;
  document.body.appendChild(element);
  const dx = target.x - origin.x;
  const dy = target.y - origin.y;
  vfxAnimate(element, [
    { transform: "translate3d(0,0,0) scale(1)", filter: "grayscale(0) brightness(1)", opacity: 1 },
    { offset: .35, transform: "translate3d(0,4px,0) scale(.97)", filter: "grayscale(1) brightness(.7)", opacity: 1 },
    { offset: .6, transform: "translate3d(0,10px,0) scale(.9)", filter: "grayscale(1) brightness(.45) blur(1px)", opacity: .75 },
    { transform: `translate3d(${dx}px,${dy}px,0) scale(.2)`, filter: "grayscale(1) brightness(.2) blur(3px)", opacity: 0 },
  ], { duration: 1000, fill: "both", easing: "cubic-bezier(.4,0,.6,1)" });
  spawnVfxParticles(origin, "hollow", { count: 14, spread: 46, direction: "down" });
  playRulesVfxImpact(origin, t("rulesVfxDestroyed") || "", "destroyed", { delay: 200 });
  playRulesVfxPulse(target, "discarded", { delay: 800 });
  window.setTimeout(() => element.remove(), vfxMs(1200));
}

// Burning card: a fireball flash, a scorch ring and embers rising from the destroyed card
function playRulesVfxBurn(host, origin) {
  host.style.scale = "1.55";
  const flash = document.createElement("span");
  flash.className = "rules-vfx-burn-flash";
  host.appendChild(flash);
  vfxAnimate(flash, [
    { transform: "scale(.3)", opacity: 0 },
    { offset: .18, transform: "scale(1.15)", opacity: .95 },
    { offset: .5, transform: "scale(1.5)", opacity: .55 },
    { transform: "scale(1.9)", opacity: 0 },
  ], { duration: 640, fill: "both", easing: "ease-out" });
  const scorch = document.createElement("span");
  scorch.className = "rules-vfx-burn-scorch";
  host.appendChild(scorch);
  vfxAnimate(scorch, [
    { transform: "scale(.6)", opacity: 0 },
    { offset: .25, transform: "scale(1)", opacity: .9 },
    { transform: "scale(1.5)", opacity: 0 },
  ], { duration: 900, fill: "both", easing: "ease-out" });
  const embers = 16;
  for (let index = 0; index < embers; index += 1) {
    const ember = document.createElement("span");
    ember.className = "rules-vfx-ember";
    const angle = (index / embers) * Math.PI * 2 + (index % 3) * 0.4;
    const spread = 22 + (index % 5) * 9;
    const rise = 38 + (index % 4) * 18;
    ember.style.left = "50%";
    ember.style.top = "50%";
    ember.style.setProperty("--ember-size", `${3 + (index % 3) * 2}px`);
    host.appendChild(ember);
    vfxAnimate(ember, [
      { transform: "translate(-50%,-50%) scale(1)", opacity: 0 },
      { offset: .15, transform: `translate(calc(-50% + ${Math.cos(angle) * spread * .4}px), calc(-50% + ${Math.sin(angle) * spread * .4}px)) scale(1.1)`, opacity: 1 },
      { transform: `translate(calc(-50% + ${Math.cos(angle) * spread}px), calc(-50% + ${Math.sin(angle) * spread * .5 - rise}px)) scale(.2)`, opacity: 0 },
    ], { duration: 780 + (index % 4) * 120, delay: 90 + (index % 6) * 30, fill: "both", easing: "cubic-bezier(.2,.7,.3,1)" });
  }
  void origin;
}

function playRulesVfxTargetLock(element, hold = 0) {
  const rect = element?.getBoundingClientRect?.();
  if (!rect?.width) return;
  const lock = document.createElement("div");
  lock.className = "rules-vfx-target-lock";
  lock.setAttribute("aria-hidden", "true");
  Object.assign(lock.style, {
    left: `${rect.left - 8}px`, top: `${rect.top - 8}px`,
    width: `${rect.width + 16}px`, height: `${rect.height + 16}px`,
  });
  document.body.appendChild(lock);
  const duration = (rulesVfxReducedMotion() ? 180 : 320) + hold;
  const settle = Math.min(.4, 90 / duration);
  rulesVfxAnimateAndRemove(lock, [
    { transform: "scale(1.16)", opacity: 0 },
    { offset: settle, transform: "scale(1)", opacity: 1 },
    { offset: Math.max(settle, 1 - 200 / duration), transform: "scale(1)", opacity: 1 },
    { transform: "scale(.94)", opacity: 0 },
  ], { duration, easing: "cubic-bezier(.16,1,.3,1)" });
}

function playRulesVfxEffectBind(effect) {
  const targetElement = rulesVfxFindBattlefieldItem(effect?.target?.itemId);
  const target = rulesVfxCenter(targetElement);
  if (!target) return;
  const source = rulesVfxCenter(rulesVfxFindBattlefieldItem(effect?.source?.itemId));
  const tone = rulesEffectTone(effect);
  if (source && !rulesVfxReducedMotion()) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.classList.add("rules-vfx-effect-cast");
    svg.setAttribute("viewBox", `0 0 ${window.innerWidth} ${window.innerHeight}`);
    const distance = Math.max(1, Math.hypot(target.x - source.x, target.y - source.y));
    const bend = Math.min(96, distance * .18);
    const controlX = (source.x + target.x) / 2;
    const controlY = Math.min(source.y, target.y) - bend;
    const pathData = `M ${source.x} ${source.y} Q ${controlX} ${controlY} ${target.x} ${target.y}`;
    svg.innerHTML = `<path class="rules-vfx-effect-cast-shadow" d="${pathData}" pathLength="1"></path><path class="rules-vfx-effect-cast-flow" d="${pathData}" pathLength="1" style="--effect-tone:${esc(tone)}"></path>`;
    document.body.appendChild(svg);
    const flow = svg.querySelector(".rules-vfx-effect-cast-flow");
    vfxAnimate(flow, [
      { strokeDashoffset: 1, opacity: 0 },
      { offset: .18, opacity: 1 },
      { offset: .68, strokeDashoffset: 0, opacity: 1 },
      { strokeDashoffset: -.18, opacity: 0 },
    ], { duration: 720, fill: "both", easing: "cubic-bezier(.16,1,.3,1)" });
    rulesVfxAnimateAndRemove(svg, [
      { opacity: 1 }, { offset: .78, opacity: 1 }, { opacity: 0 },
    ], { duration: 760, easing: "linear" });
  }
  const seal = document.createElement("div");
  seal.className = "rules-vfx-effect-seal";
  seal.setAttribute("aria-hidden", "true");
  seal.style.left = `${target.x}px`;
  seal.style.top = `${target.y}px`;
  seal.style.setProperty("--effect-tone", tone);
  seal.innerHTML = `<svg viewBox="0 0 24 24"><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="12" r="3"></circle><path d="M9 12h6"></path></svg>`;
  document.body.appendChild(seal);
  rulesVfxAnimateAndRemove(seal, [
    { transform: "translate(-50%,-50%) scale(.45) rotate(-18deg)", opacity: 0 },
    { offset: .32, transform: "translate(-50%,-50%) scale(1.08) rotate(0deg)", opacity: 1 },
    { offset: .72, transform: "translate(-50%,-50%) scale(.94)", opacity: 1 },
    { transform: "translate(-50%,-50%) scale(.82)", opacity: 0 },
  ], { duration: rulesVfxReducedMotion() ? 380 : 820, easing: "cubic-bezier(.16,1,.3,1)" });
}

function playRulesVfxEffectRelease(change) {
  if (!change?.target) return;
  const release = document.createElement("div");
  release.className = "rules-vfx-effect-release";
  release.setAttribute("aria-hidden", "true");
  release.style.left = `${change.target.x}px`;
  release.style.top = `${change.target.y}px`;
  release.style.setProperty("--effect-tone", change.tone || rulesEffectTone(change.effect));
  document.body.appendChild(release);
  rulesVfxAnimateAndRemove(release, [
    { transform: "translate(-50%,-50%) scale(.72) rotate(0deg)", opacity: .9 },
    { transform: "translate(-50%,-50%) scale(1.28) rotate(45deg)", opacity: 0 },
  ], { duration: rulesVfxReducedMotion() ? 260 : 520, easing: "cubic-bezier(.4,0,1,1)" });
}

function playRulesEffectVfxChanges(changes) {
  if (!changes.length || $("#gameScreen").classList.contains("hidden")) return;
  enqueueRulesVfx(() => {
    changes.forEach((change) => {
      if (change.kind === "added") playRulesVfxEffectBind(change.effect);
      else playRulesVfxEffectRelease(change);
    });
    return 620;
  }, 620);
}

function playRulesVfxStackPulse(tone) {
  const target = rulesVfxStackTarget();
  const pulse = document.createElement("div");
  pulse.className = `rules-vfx-stack-pulse rules-vfx-stack-pulse-${tone}`;
  pulse.setAttribute("aria-hidden", "true");
  pulse.style.left = `${target.x}px`;
  pulse.style.top = `${target.y}px`;
  document.body.appendChild(pulse);
  rulesVfxAnimateAndRemove(pulse, [
    { transform: "translate(-50%,-50%) scale(.7)", opacity: 0 },
    { offset: .28, transform: "translate(-50%,-50%) scale(1)", opacity: .9 },
    { transform: "translate(-50%,-50%) scale(1.36)", opacity: 0 },
  ], { duration: rulesVfxReducedMotion() ? 300 : 540, easing: "cubic-bezier(.16,1,.3,1)" });
}

const rulesVfxActiveLabels = [];

function rulesVfxLabelSlot(target, lifetime) {
  // labels near the same spot stack upwards instead of covering each other
  const now = performance.now();
  for (let index = rulesVfxActiveLabels.length - 1; index >= 0; index -= 1) {
    if (rulesVfxActiveLabels[index].until <= now) rulesVfxActiveLabels.splice(index, 1);
  }
  let slot = 0;
  while (rulesVfxActiveLabels.some((label) => (
    label.slot === slot && Math.abs(label.x - target.x) < 90 && Math.abs(label.y - target.y) < 40
  ))) slot += 1;
  rulesVfxActiveLabels.push({ x: target.x, y: target.y, slot, until: now + lifetime });
  return slot;
}

function playRulesVfxImpact(target, label, tone = "cost", options = {}) {
  if (!target) return;
  const reduced = rulesVfxReducedMotion();
  const timing = vfxTiming({ duration: reduced ? 900 : 1250, delay: Number(options.delay || 0) });
  const slot = rulesVfxLabelSlot(target, timing.duration + timing.delay);
  const element = document.createElement("div");
  element.className = `rules-vfx-impact rules-vfx-impact-${tone}`;
  element.textContent = label;
  element.setAttribute("role", "status");
  element.style.left = `${target.x}px`;
  element.style.top = `${Math.max(18, target.y - slot * 36)}px`;
  document.body.appendChild(element);
  const animation = element.animate([
    { transform: "translate(-50%,-50%) scale(.86)", opacity: 0, filter: "blur(3px)" },
    { offset: .14, transform: "translate(-50%,-50%) scale(1.04)", opacity: 1, filter: "blur(0)" },
    { offset: .22, transform: "translate(-50%,-50%) scale(1)", opacity: 1, filter: "blur(0)" },
    { offset: .8, transform: "translate(-50%,-50%) scale(1)", opacity: 1, filter: "blur(0)" },
    { transform: `translate(-50%,${reduced ? "-50%" : "-90%"}) scale(.98)`, opacity: 0, filter: "blur(0)" },
  ], { ...timing, fill: "both", easing: "cubic-bezier(.2,.8,.2,1)" });
  animation.finished.catch(() => {}).finally(() => element.remove());
}

function playRulesVfxExhaust(sourceRect) {
  if (!sourceRect?.width || !sourceRect?.height) return;
  const ring = document.createElement("div");
  ring.className = "rules-vfx-exhaust-ring";
  ring.setAttribute("aria-hidden", "true");
  Object.assign(ring.style, {
    left: `${sourceRect.left - 6}px`, top: `${sourceRect.top - 6}px`,
    width: `${sourceRect.width + 12}px`, height: `${sourceRect.height + 12}px`,
  });
  document.body.appendChild(ring);
  rulesVfxAnimateAndRemove(ring, [
    { transform: "scale(.92)", opacity: 0 },
    { offset: .28, transform: "scale(1)", opacity: 1 },
    { transform: "scale(1.035)", opacity: 0 },
  ], { duration: 650, easing: "cubic-bezier(.16,1,.3,1)" });

  const label = document.createElement("div");
  label.className = "rules-vfx-exhaust-label";
  label.textContent = t("rulesVfxExhausted");
  label.style.left = `${sourceRect.left + sourceRect.width / 2}px`;
  label.style.top = `${Math.max(16, sourceRect.top - 8)}px`;
  document.body.appendChild(label);
  rulesVfxAnimateAndRemove(label, [
    { transform: "translate(-50%,-80%)", opacity: 0 },
    { offset: .25, transform: "translate(-50%,-100%)", opacity: 1 },
    { transform: "translate(-50%,-130%)", opacity: 0 },
  ], { duration: 650, easing: "cubic-bezier(.16,1,.3,1)" });
}

const RULES_VFX_BEAT_MS = {
  rules_action_declared: 2300,
  rules_action_triggered: 1150,
  rules_action_resolved: 1700,
  rules_choice_resolved: 1500,
  rules_confrontation_cleanup: 820,
  rules_phase_advanced: 1700,
  rules_confrontation_compared: 3400,
  recovery_draw: 1500,
};

function playRulesVfxBatch(batch) {
  $$(".rules-vfx-phase-banner").forEach((banner) => {
    if (!rulesVfxPhaseIsCurrent({ turn: banner.dataset.turn, phaseId: banner.dataset.phaseId })) banner.remove();
  });
  if (!batch.length || $("#gameScreen").classList.contains("hidden")) return;
  // consecutive phase steps (auto-passed ones included) collapse into one banner
  const beats = [];
  for (const event of batch) {
    const previous = beats[beats.length - 1];
    if (event.entry.type === "rules_phase_advanced" && previous?.entry.type === "rules_phase_advanced") {
      beats[beats.length - 1] = event;
      continue;
    }
    beats.push(event);
  }
  beats.forEach((event) => {
    if (event.entry.type === "rules_action_resolved" && event.entry.details?.immediate) {
      // Immediate actions never remain in the server's Stack snapshot. Give their
      // public source a separate reading beat before playing the normal outcome.
      enqueueRulesVfx(() => playRulesVfxResolveReveal(event.entry, true), 1600);
    }
    const slowed = VFX_EFFECT_PACE_TYPES.includes(event.entry.type);
    const base = RULES_VFX_BEAT_MS[event.entry.type] || 700;
    // effect beats run slower: the estimate must follow, or cards waiting for them land too early.
    // The beat itself returns its base length: vfxMs() already applies the effect pace while it plays.
    const estimate = base * (slowed ? VFX_EFFECT_PACE : 1);
    enqueueRulesVfx(() => {
      const played = playRulesVfxEvent(event);
      if (played === false) return 0;
      return typeof played === "number" ? played : base;
    }, estimate);
    if (event.entry.type === "recovery_draw" && rulesVfxDrawCount(event.entry, myPlayerId)) {
      // the drawn hand cannot be played before its cards have landed
      lockHandUntilDrawn(rulesVfxQueueRemaining());
    }
  });
}

function rulesVfxDrawCount(entry, playerId) {
  const drawn = (entry?.details?.draws || {})[playerId];
  return Number(Array.isArray(drawn) ? drawn.length : drawn?.count ?? drawn) || 0;
}

// Recovery: the hand stays inert while its draw animation plays
let handDrawLockUntil = 0;

let handDrawLockTimer = null;

function handDrawLocked() {
  return handDrawLockUntil > performance.now();
}

function lockHandUntilDrawn(duration) {
  if (rulesVfxReducedMotion() || !(duration > 0)) return;
  handDrawLockUntil = Math.max(handDrawLockUntil, performance.now() + duration);
  if (handDrawLockTimer) window.clearTimeout(handDrawLockTimer);
  document.body.classList.add("hand-drawing");
  handDrawLockTimer = window.setTimeout(() => {
    handDrawLockTimer = null;
    handDrawLockUntil = 0;
    document.body.classList.remove("hand-drawing");
    if (latestState) renderAll();
  }, Math.ceil(handDrawLockUntil - performance.now()) + 50);
}

let lastRulesVfxBannerKey = "";

function rulesVfxPhaseGroupId(phaseId) {
  const phase = ADVANCED_PHASES.find((item) => item.id === phaseId) || BASIC_PHASES.find((item) => item.id === phaseId);
  return phase ? (phase.parent || phase.id) : phaseId || "";
}

function rulesVfxPhaseIsCurrent(details) {
  const tracker = latestState?.phaseTracker;
  return Boolean(tracker?.enabled
    && Number(details.turn || 1) === Number(tracker.turn || 1)
    && rulesVfxPhaseGroupId(details.phaseId) === currentPhaseUi().group?.id);
}

function playRulesVfxPhaseBanner(event) {
  const details = event.entry.details || {};
  // The animation queue can lag behind auto-passed phases. A historical
  // announcement must never tell a player they still have a Reaction window.
  if (!rulesVfxPhaseIsCurrent(details)) return false;
  const turn = Number(details.turn || 1);
  const groupId = rulesVfxPhaseGroupId(details.phaseId);
  const key = `${turn}:${groupId}`;
  if (key === lastRulesVfxBannerKey) return false;
  const newTurn = !lastRulesVfxBannerKey.startsWith(`${turn}:`);
  lastRulesVfxBannerKey = key;
  const lines = phaseLogLines({ ...details, advancedMode: false });
  if (!lines.phase) return false;
  $$(".rules-vfx-phase-banner").forEach((element) => element.remove());
  const banner = document.createElement("div");
  banner.className = `rules-vfx-phase-banner${newTurn ? " is-new-turn" : ""}`;
  banner.dataset.turn = String(turn);
  banner.dataset.phaseId = details.phaseId;
  banner.setAttribute("role", "status");
  banner.innerHTML = `${newTurn ? `<small>${esc(rulesText("rulesVfxTurn", { turn }))}</small>` : ""}<strong>${esc(lines.phase)}</strong>`;
  const anchor = $("#battlefieldWrap")?.getBoundingClientRect?.();
  banner.style.top = `${Math.round(anchor?.height ? anchor.top + anchor.height * .42 : window.innerHeight * .42)}px`;
  document.body.appendChild(banner);
  const reduced = rulesVfxReducedMotion();
  rulesVfxAnimateAndRemove(banner, [
    { transform: `translate(-50%,-50%) scaleX(${reduced ? 1 : .6})`, opacity: 0, letterSpacing: ".32em" },
    { offset: .18, transform: "translate(-50%,-50%) scaleX(1)", opacity: 1, letterSpacing: ".12em" },
    { offset: .78, transform: "translate(-50%,-50%) scaleX(1)", opacity: 1, letterSpacing: ".1em" },
    { transform: `translate(-50%,-50%) scaleX(${reduced ? 1 : 1.04})`, opacity: 0, letterSpacing: ".1em" },
  ], { duration: newTurn ? 2800 : 1700, easing: "cubic-bezier(.2,.8,.2,1)" });
  return newTurn ? 2800 : true;
}

// Winner and Power totals of the Resolution, shown long enough to read even when the steps are skipped
function countUpNumber(element, target, duration, delay = 0) {
  if (!Number.isFinite(target)) { element.textContent = String(target); return; }
  if (rulesVfxReducedMotion() || target === 0) { element.textContent = String(target); return; }
  const startAt = performance.now() + delay;
  const step = (now) => {
    if (!element.isConnected) return;
    const progress = Math.min(1, Math.max(0, (now - startAt) / duration));
    element.textContent = String(Math.round(target * (1 - Math.pow(1 - progress, 3))));
    if (progress < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function playRulesVfxResolutionBanner(entry) {
  const details = entry.details || {};
  const playerName = (playerId) => latestState?.players?.[playerId]?.name || playerId || "?";
  const totals = Object.entries(details.totals || {})
    .map(([playerId, value]) => {
      const tone = details.stalemate ? "" : playerId === details.winnerId ? " is-winner" : " is-loser";
      return `<span class="rules-vfx-total${tone}" style="--player-tone:${esc(playerColor(playerId))}"><i>${esc(playerName(playerId))}</i><b data-count-to="${esc(String(value))}">0</b></span>`;
    })
    .join("");
  $$(".rules-vfx-resolution-banner").forEach((element) => element.remove());
  const banner = document.createElement("div");
  banner.className = "rules-vfx-resolution-banner";
  banner.setAttribute("role", "status");
  banner.innerHTML = `<small>${esc(t("rulesVfxResolution"))}</small>
    <strong>${esc(details.stalemate ? t("rulesVfxStalemate") : rulesText("rulesVfxWinner", { player: playerName(details.winnerId) }))}</strong>
    <span>${totals}</span>`;
  const anchor = $("#battlefieldWrap")?.getBoundingClientRect?.();
  banner.style.top = `${Math.round(anchor?.height ? anchor.top + anchor.height * .3 : window.innerHeight * .3)}px`;
  document.body.appendChild(banner);
  banner.querySelectorAll("[data-count-to]").forEach((counter) => countUpNumber(counter, Number(counter.dataset.countTo), vfxMs(900), vfxMs(350)));
  if (!details.stalemate && !rulesVfxReducedMotion()) banner.classList.add("has-winner-flash");
  rulesVfxAnimateAndRemove(banner, [
    { transform: "translate(-50%,-50%) scale(.85)", opacity: 0 },
    { offset: .09, transform: "translate(-50%,-50%) scale(1)", opacity: 1 },
    { offset: .91, transform: "translate(-50%,-50%) scale(1)", opacity: 1 },
    { transform: "translate(-50%,-50%) scale(1.03)", opacity: 0 },
  ], { duration: 4400, easing: "linear" });
}

// "Uncover the top card of your deck" (Skysailing Triad...): show the card, then what became of it
function rulesTopRevealOutcomeKey(result) {
  if (result?.status === "drawn") return "rulesVfxTopDrawn";
  if (result?.cardType === "manifestation" && !["failed", "revealed_no_effect"].includes(result.status)) return "rulesVfxTopChained";
  return "";
}

// the card Skysailing Triad uncovered, in the short log line seen by both players
function rulesTopRevealLogHtml(result) {
  if (result?.kind !== "resolve_top_deck_by_type" || !result.cardId) return "";
  const outcome = rulesTopRevealOutcomeKey(result);
  return ` — ${esc(t("rulesVfxTopRevealed"))} : ${namedOrUnknownCard(result.cardId)}${outcome ? ` (${esc(t(outcome))})` : ""}`;
}

function playRulesVfxTopReveal(entry) {
  const result = entry.details?.effectResult || {};
  if (!result.cardId) return 0;
  $$(".rules-vfx-top-reveal").forEach((element) => element.remove());
  const outcomeKey = result.status === "drawn" ? "rulesVfxTopDrawn"
    : result.cardType === "manifestation" && result.status !== "failed" && result.status !== "revealed_no_effect" ? "rulesVfxTopChained"
    : "rulesVfxTopNoEffect";
  const panel = document.createElement("div");
  panel.className = "rules-vfx-top-reveal";
  panel.setAttribute("role", "status");
  const sourceId = entry.details?.source?.cardId;
  if (window.uiBeta?.active()) {
    // beta table: the source card, the uncovered card and what became of it
    const outcome = outcomeKey.replace("rulesVfxTop", "").toLowerCase();
    panel.classList.add("is-beta", `is-${outcome}`);
    panel.style.setProperty("--owner-color", playerColor(entry.actorId));
    panel.innerHTML = `<header>
        ${sourceId ? `<img class="src" src="${esc(cardImage(sourceId))}" alt="">` : ""}
        <span><b>${esc(sourceId ? cardName(sourceId) : "")}</b><small>${esc(t("rulesVfxTopRevealed"))}${entry.actorName ? ` · ${esc(entry.actorName)}` : ""}</small></span>
      </header>
      <div class="card"><img src="${esc(cardImage(result.cardId))}" alt="${esc(cardName(result.cardId))}"><i></i></div>
      <strong>${esc(cardName(result.cardId))}</strong>
      <em>${esc(cardField(cardsById.get(result.cardId), "typeLabel") || "")}</em>
      <span class="outcome">${esc(t(outcomeKey))}</span>`;
  } else {
    panel.innerHTML = `<small>${esc(t("rulesVfxTopRevealed"))}</small>
    <img src="${esc(cardImage(result.cardId))}" alt="${esc(cardName(result.cardId))}">
    <strong>${esc(cardName(result.cardId))}</strong>
    <span>${esc(t(outcomeKey))}</span>`;
  }
  const anchor = $("#battlefieldWrap")?.getBoundingClientRect?.();
  panel.style.top = `${Math.round(anchor?.height ? anchor.top + anchor.height * .42 : window.innerHeight * .42)}px`;
  document.body.appendChild(panel);
  rulesVfxAnimateAndRemove(panel, [
    { transform: "translate(-50%,-50%) translateY(46px) scale(.55) rotateY(90deg)", opacity: 0 },
    { offset: .16, transform: "translate(-50%,-50%) scale(1) rotateY(0deg)", opacity: 1 },
    { offset: .88, transform: "translate(-50%,-50%) scale(1)", opacity: 1 },
    { transform: "translate(-50%,-50%) scale(.96)", opacity: 0 },
  ], { duration: 2600, easing: "cubic-bezier(.2,.8,.2,1)" });
  return 2700;
}

function playRulesVfxSpotlight(event) {
  const { entry, spotlightOrigin, declaredTargets } = event;
  const cardId = entry.details?.source?.cardId;
  if (!cardId) return;
  const isOpponent = entry.actorId && entry.actorId !== myPlayerId;
  const stack = rulesVfxStackTarget();
  const width = Math.round(Math.min(210, Math.max(140, window.innerWidth * .13)));
  const height = Math.round(width * 1.4);
  // show the card on whichever side of the board keeps its targets visible
  const board = $("#battlefieldWrap")?.getBoundingClientRect?.();
  const area = board?.width ? board : { left: 0, top: 0, width: window.innerWidth, height: window.innerHeight };
  const avoid = [...(declaredTargets || []).map((target) => target.point), spotlightOrigin].filter(Boolean);
  // beta table: the Interzones sit on the sides, the card always shows in the middle
  const candidates = (window.uiBeta?.active() ? [.5] : [.22, .78])
    .map((ratio) => ({ x: area.left + area.width * ratio, y: area.top + area.height * .44 }));
  const spotCenter = candidates
    .map((point) => ({ point, room: Math.min(Infinity, ...avoid.map((other) => Math.hypot(other.x - point.x, other.y - point.y))) }))
    .sort((a, b) => b.room - a.room)[0].point;
  const centerX = Math.min(window.innerWidth - width / 2 - 24, Math.max(width / 2 + 24, spotCenter.x));
  const centerY = Math.min(window.innerHeight - height / 2 - 24, Math.max(height / 2 + 24, spotCenter.y));
  const spot = document.createElement("div");
  spot.className = `rules-vfx-spotlight${isOpponent ? " is-opponent" : ""}`;
  spot.setAttribute("aria-hidden", "true");
  Object.assign(spot.style, {
    left: `${centerX - width / 2}px`, top: `${centerY - height / 2}px`,
    width: `${width}px`, height: `${height}px`,
  });
  spot.style.setProperty("--owner-color", playerColor(entry.actorId));
  spot.innerHTML = `<img src="${esc(cardImage(cardId))}" alt=""><span class="rules-vfx-spotlight-sheen"></span>${entry.actorName ? `<span class="rules-vfx-spotlight-caption">${esc(entry.actorName)}</span>` : ""}`;
  document.body.appendChild(spot);
  const origin = spotlightOrigin || { x: centerX, y: window.innerHeight };
  const fromX = origin.x - centerX;
  const fromY = origin.y - centerY;
  const toX = stack.x - centerX;
  const toY = stack.y - centerY;
  const reduced = rulesVfxReducedMotion();
  rulesVfxAnimateAndRemove(spot, reduced ? [
    { opacity: 0 }, { offset: .15, opacity: 1 }, { offset: .8, opacity: 1 }, { opacity: 0 },
  ] : [
    { transform: `translate3d(${fromX}px,${fromY}px,0) scale(.32) rotate(${isOpponent ? 6 : -6}deg)`, opacity: 0 },
    { offset: .2, transform: "translate3d(0,0,0) scale(1.03) rotate(0deg)", opacity: 1 },
    { offset: .26, transform: "translate3d(0,0,0) scale(1)", opacity: 1 },
    { offset: .82, transform: "translate3d(0,0,0) scale(1)", opacity: 1 },
    { transform: `translate3d(${toX}px,${toY}px,0) scale(.2)`, opacity: 0 },
  ], { duration: 2700, easing: "cubic-bezier(.3,.7,.2,1)" });
  (declaredTargets || []).forEach((target, index) => {
    // the board was re-rendered since capture: look the target up again
    const element = rulesVfxDeclaredTargetElement(target.declared);
    const point = rulesVfxCenter(element) || target.point;
    if (!point) return;
    const angle = Math.atan2(point.y - centerY, point.x - centerX);
    const edge = Math.min(width, height) / 2 + 6;
    playRulesVfxTargetArrow({ x: centerX + Math.cos(angle) * edge, y: centerY + Math.sin(angle) * edge }, point, index);
    if (element) setRulesVfxTimeout(() => playRulesVfxTargetLock(element, 2000), vfxMs(420 + index * 90));
    else playRulesVfxPulse(point, "triggered", { delay: 420 + index * 90 });
  });
}

function playRulesVfxTargetArrow(from, to, index = 0) {
  if (rulesVfxReducedMotion()) return;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.classList.add("rules-vfx-target-arrow");
  svg.setAttribute("viewBox", `0 0 ${window.innerWidth} ${window.innerHeight}`);
  const distance = Math.max(1, Math.hypot(to.x - from.x, to.y - from.y));
  const bend = Math.min(120, distance * .22);
  const controlX = (from.x + to.x) / 2;
  const controlY = Math.min(from.y, to.y) - bend;
  const angle = Math.atan2(to.y - controlY, to.x - controlX) * 180 / Math.PI;
  const pathData = `M ${from.x} ${from.y} Q ${controlX} ${controlY} ${to.x} ${to.y}`;
  svg.innerHTML = `<path class="rules-vfx-target-arrow-glow" d="${pathData}" pathLength="1"></path><path class="rules-vfx-target-arrow-line" d="${pathData}" pathLength="1"></path><g transform="translate(${to.x} ${to.y}) rotate(${angle})"><path class="rules-vfx-target-arrow-head" d="M 2 0 L -14 -8 L -10 0 L -14 8 Z"></path></g>`;
  document.body.appendChild(svg);
  const delay = 260 + index * 90;
  svg.querySelectorAll(".rules-vfx-target-arrow-glow, .rules-vfx-target-arrow-line").forEach((path) => {
    vfxAnimate(path, [
      { strokeDashoffset: 1 }, { offset: .55, strokeDashoffset: 0 }, { strokeDashoffset: 0 },
    ], { duration: 700, delay, fill: "both", easing: "cubic-bezier(.3,.7,.2,1)" });
  });
  vfxAnimate(svg.querySelector(".rules-vfx-target-arrow-head"), [
    { opacity: 0, transform: "scale(.4)" }, { offset: .5, opacity: 0, transform: "scale(.4)" }, { offset: .65, opacity: 1, transform: "scale(1.15)" }, { opacity: 1, transform: "scale(1)" },
  ], { duration: 700, delay, fill: "both" });
  rulesVfxAnimateAndRemove(svg, [
    { opacity: 1 }, { offset: .82, opacity: 1 }, { opacity: 0 },
  ], { duration: 2600 + index * 90, easing: "linear" });
}

function playRulesVfxEvent(event) {
  const slowed = VFX_EFFECT_PACE_TYPES.includes(event.entry?.type);
  // only effect beats run at the slower pace: a banner right after one plays at its normal speed
  vfxEffectPaceUntil = slowed ? performance.now() + 4500 : 0;
  const played = playRulesVfxEventInner(event);
  if (slowed) {
    const base = typeof played === "number" ? played : RULES_VFX_BEAT_MS[event.entry.type] || 700;
    vfxEffectPaceUntil = performance.now() + vfxMs(base) + 300;
  }
  return played;
}

function playRulesVfxEventInner(event) {
  {
    const { entry, tributeOrigins, essenceOrigins, sourceRect, sacrifice, effectTarget, movedCard, deckDiscard, supportWin } = event;
    if (event.manualDraw) {
      const draw = event.manualDraw;
      if (!draw.count) return 0;
      if (rulesVfxReducedMotion()) { playRulesVfxPulse(draw.target, "moved"); return 180; }
      for (let index = 0; index < draw.count; index += 1) playRulesVfxFlight("draw-card", draw.origin, draw.target, { index });
      return 660 + (draw.count - 1) * 36;
    }
    if (["move_card", "remove_battlefield_item"].includes(entry.type)) {
      const move = event.manualMove;
      if (!move?.target) return 0;
      if (rulesVfxReducedMotion()) {
        playRulesVfxPulse(move.target, "moved");
        return 180;
      }
      playRulesVfxFlight(move.cardId ? "effect-card" : "draw-card", move.origin, move.target, { cardId: move.cardId, index: 0 });
      return 660;
    }
    const target = rulesVfxStackTarget();
    if (entry.type === "rules_phase_advanced") {
      return playRulesVfxPhaseBanner(event);
    }
    if (entry.type === "rules_confrontation_compared") {
      playRulesVfxResolutionBanner(entry);
      return 3400;
    }
    if (entry.type === "recovery_draw") {
      if (rulesVfxReducedMotion()) return 300;
      let played = 0;
      Object.entries(entry.details?.draws || {}).forEach(([playerId, drawn]) => {
        const count = Math.min(5, Number(Array.isArray(drawn) ? drawn.length : drawn?.count ?? drawn) || 0);
        const deck = rulesVfxPileCenter(playerId, "deck");
        if (!count || !deck) return;
        const hand = rulesVfxPlayerOrigin(playerId);
        for (let index = 0; index < count; index += 1) {
          playRulesVfxFlight("draw-card", deck, { x: hand.x + (index - (count - 1) / 2) * 34, y: hand.y }, { index: index * 2, land: false });
        }
        spawnVfxParticles(deck, "vitreous", { count: 6, spread: 28 });
        playRulesVfxImpact(hand, rulesText("rulesVfxDrawn", { count }), "draw", { delay: 250 });
        played = 1;
      });
      return played ? 1000 : 300;
    }
    if (entry.type === "rules_action_declared" && !rulesVfxReducedMotion()) playRulesVfxSpotlight(event);
    if (entry.type === "rules_confrontation_cleanup") {
      const cleanupMoves = event.cleanupMoves || [];
      const cleanupStep = 380;
      cleanupMoves.slice(0, 12).forEach((move, index) => {
        setRulesVfxTimeout(() => rulesVfxAfterWinnerChoices(() => {
          if (rulesVfxReducedMotion()) {
            playRulesVfxImpact(move.target, t(move.zone === "exile" ? "rulesVfxExiled" : "rulesVfxMoved"), "moved");
            return;
          }
          if (move.removedCopy) playRulesVfxDestruction(move.origin, move.target, move.cardId);
          else playRulesVfxFlight("effect-card", move.origin, move.target, { cardId: move.cardId, index, big: true });
          playRulesVfxImpact(
            move.target,
            t(move.zone === "exile" ? "rulesVfxExiled" : "rulesVfxMoved"),
            move.zone === "exile" ? "destroyed" : "moved",
            { delay: 380 },
          );
        }), vfxMs(index * cleanupStep));
      });
      if (supportWin) {
        rulesVfxAfterWinnerChoices(() => {
          const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
          if (!reduced) playRulesVfxFlight("effect-card", supportWin.origin, supportWin.target, { cardId: supportWin.cardId, index: 0, big: true });
          if (supportWin.kind === "opponent_vessel_score") {
            const delta = Number(supportWin.delta || 0);
            playRulesVfxImpact(supportWin.target, `${delta >= 0 ? "+" : ""}${delta}`, delta < 0 ? "score-loss" : "score");
          } else {
            playRulesVfxImpact(supportWin.target, t("rulesVfxOpponentVessel"), "resolved");
          }
        });
      }
      return cleanupMoves.length ? 1600 + Math.min(cleanupMoves.length, 12) * cleanupStep : 820;
    }
    if (entry.type === "rules_action_triggered") {
      const triggerRect = event.sourceRect;
      if (triggerRect?.width && !rulesVfxReducedMotion()) {
        const triggerTemperament = cardsById.get(entry.details?.source?.cardId)?.colorKey || "capricious";
        playRulesVfxFlight("essence", { x: triggerRect.left + triggerRect.width / 2, y: triggerRect.top + triggerRect.height / 2 }, rulesVfxStackNoticeTarget(), { temperament: triggerTemperament, index: 0 });
        playVfxCardElement(entry.details?.source?.cardId, entry.details?.source?.itemId, { envelope: "effect", duration: 1300, grow: 1.9 });
        spawnVfxParticles({ x: triggerRect.left + triggerRect.width / 2, y: triggerRect.top + triggerRect.height / 2 }, triggerTemperament, { count: 6, spread: 26, direction: "out" });
      }
      playRulesVfxStackPulse("triggered");
      playRulesVfxImpact(rulesVfxStackNoticeTarget(), t("rulesVfxTriggered"), "triggered");
      return;
    }
    if (entry.type === "rules_action_resolved") {
      if (entry.details?.automatic && entry.details.effectResult?.kind === "score") {
        const result = entry.details.effectResult;
        const delta = Number(result.delta || 0);
        playRulesVfxImpact(effectTarget || rulesVfxPlayerOrigin(result.playerId), `${delta >= 0 ? "+" : ""}${delta}`, delta < 0 ? "score-loss" : "score");
        return;
      }
      if (!entry.details?.immediate) playRulesVfxResolveReveal(entry);
      // a card on the field that does its effect shows its element
      if (rulesVfxFindBattlefieldItem(entry.details?.source?.itemId)) {
        playVfxCardElement(entry.details.source.cardId, entry.details.source.itemId, { envelope: "effect", duration: 1300, grow: 1.9 });
      }
      playRulesVfxStackPulse("resolved");
      playRulesVfxImpact(target, t("rulesVfxResolved"), "resolved");
      if (entry.details?.effectResult?.kind === "resolve_top_deck_by_type" && entry.details.effectResult.cardId) {
        // an uncovered Will drawn this way stays known in its owner's hand (server side)
        return playRulesVfxTopReveal(entry);
      }
      playRulesVfxCardScene(entry, target);
      (event.massExiled || []).forEach((card, index) => playRulesVfxExileDissolve(card.origin, card.image, 500 + index * 90));
      (event.stateDestroyed || []).forEach((move, index) => {
        if (rulesVfxReducedMotion()) {
          playRulesVfxImpact(move.target, t("rulesVfxDestroyed") || t("rulesVfxMoved"), "destroyed");
          return;
        }
        setRulesVfxTimeout(() => {
          playRulesVfxWither(move.origin, move.target, move.cardId);
        }, vfxMs(500 + index * 260));
      });
      const diceRoll = Number(entry.details?.effectResult?.roll);
      if (Number.isInteger(diceRoll) && diceRoll >= 1 && diceRoll <= 6) playRulesVfxDice(diceRoll, target);
      // one die on each card the Bros chose
      if (entry.details?.effectResult?.kind === "roll_d6_each_target") {
        (entry.details.effectResult.results || []).forEach((rolled, index) => {
          const card = rolled.itemId ? document.querySelector(`#battlefield [data-item-id="${CSS.escape(rolled.itemId)}"]`) : null;
          const rect = card?.getBoundingClientRect();
          const anchor = rect?.width ? { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 } : target;
          setRulesVfxTimeout(() => playRulesVfxDice(Number(rolled.roll), anchor), vfxMs(index * 320));
        });
      }
      if (entry.details?.effectResult?.kind === "neutralize_stack_action") {
        if (entry.details.effectResult.status === "neutralized") {
          // the countered effect shatters against a glass shield
          spawnVfxParticles(target, "vitreous", { count: 16, spread: 54, direction: "out" });
          spawnVfxParticles(target, "transcendent", { count: 8, spread: 36, direction: "out", delay: 120 });
        }
        playRulesVfxImpact(
          target,
          t(entry.details.effectResult.status === "neutralized" ? "rulesVfxNeutralized" : "rulesVfxTargetGone"),
          entry.details.effectResult.status === "neutralized" ? "destroyed" : "target-gone",
        );
      }
      if (entry.details?.effectResult?.kind === "copy_stack_action" && entry.details.effectResult.status === "copied") {
        playRulesVfxImpact(target, t("rulesVfxCopied"), "triggered");
      }
      if (entry.details?.effectResult?.kind === "chain_manifestation" && entry.details.effectResult.status === "no_eligible_card") {
        playRulesVfxImpact(target, t("rulesVfxNoEligibleTarget"), "target-gone");
      }
      if (effectTarget && entry.details?.effectResult?.kind === "score") {
        const delta = Number(entry.details.effectResult.delta || 0);
        playRulesVfxImpact(
          effectTarget,
          `${delta >= 0 ? "+" : ""}${delta}`,
          delta < 0 ? "score-loss" : "score",
        );
      }
      if (effectTarget && entry.details?.effectResult?.kind === "draw" && !rulesVfxReducedMotion()) {
        const drawerId = entry.details.effectResult.playerId;
        const deckPile = $$("[data-field-pile]").find((element) => element.dataset.fieldPile === `${drawerId}:deck`);
        const deckPoint = rulesVfxCenter(deckPile);
        if (deckPoint) {
          const cards = Math.min(5, Math.max(1, Number(entry.details.effectResult.count || 1)));
          for (let index = 0; index < cards; index += 1) {
            playRulesVfxFlight("draw-card", deckPoint, {
              x: effectTarget.x + (index - (cards - 1) / 2) * 34,
              y: effectTarget.y,
            }, { index: index * 2, land: false });
          }
          spawnVfxParticles(deckPoint, "vitreous", { count: 6, spread: 28 });
        }
      }
      if (effectTarget && entry.details?.effectResult?.kind === "draw") {
        playRulesVfxImpact(effectTarget, rulesText("rulesVfxDrawn", {
          count: Number(entry.details.effectResult.count || 0),
        }), "draw");
      }
      if (deckDiscard) {
        const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
        if (!reduced) {
          (deckDiscard.cardIds || []).slice(0, 3).forEach((cardId, index) => {
            playRulesVfxFlight("discard-card", deckDiscard.origin, deckDiscard.target, { cardId, index });
          });
        }
        playRulesVfxImpact(
          deckDiscard.count ? deckDiscard.target : target,
          deckDiscard.count
            ? rulesText("rulesVfxDeckDiscarded", { count: deckDiscard.count })
            : t("rulesVfxDeckEmpty"),
          "discarded",
        );
      }
      if (movedCard?.status === "moved") {
        const reduced = rulesVfxReducedMotion();
        if (!reduced) {
          if (movedCard.reason === "destroy") {
            playRulesVfxDestruction(movedCard.origin, movedCard.target, movedCard.cardId);
          } else {
            playRulesVfxFlight("effect-card", movedCard.origin, movedCard.target, { cardId: movedCard.cardId, index: 0 });
          }
        }
        const impactTarget = movedCard.reason === "destroy" ? movedCard.origin : movedCard.target;
        playRulesVfxImpact(
          impactTarget,
          movedCard.reason === "destroy"
            ? t("rulesVfxDestroyed")
            : movedCard.reason === "exile"
              ? t("rulesVfxExiled")
              : movedCard.toZone === "deck"
            ? t(movedCard.position === "bottom" ? "rulesVfxDeckBottom" : "rulesVfxDeckTop")
            : t(movedCard.toZone === "exile" ? "rulesVfxExiled" : "rulesVfxMoved"),
          movedCard.reason === "destroy" ? "destroyed" : "moved",
          { delay: movedCard.reason === "destroy" && !reduced ? 110 : 260 },
        );
      }
      if (movedCard?.status === "target_missing") {
        playRulesVfxImpact(target, t("rulesVfxTargetGone"), "target-gone");
      }
      if (movedCard?.status === "no_eligible_card") {
        playRulesVfxImpact(target, t("rulesVfxNoEligibleTarget"), "target-gone");
      }
      if (movedCard?.status === "removed_copy") {
        playRulesVfxImpact(movedCard.origin, t("rulesVfxCopyGone"), "target-gone");
      }
      return;
    }
    if (entry.type === "rules_choice_resolved") {
      if (entry.details?.kind === "counter_essence") {
        playRulesVfxImpact(rulesVfxPlayerOrigin(entry.details.playerId), `${t("essence")} +${Number(entry.details.amount || 1)}`, "cost");
        return;
      }
      if (entry.details?.powerGain?.value) playRulesVfxPowerSurge(entry.details.powerGain);
      if (entry.details?.kind === "stack_copy_targets") {
        playRulesVfxImpact(target, t("rulesVfxCopied"), "triggered");
        return;
      }
      if (entry.details?.kind === "stack_counter_payment") {
        if (entry.details.status === "paid") {
          const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
          let index = 0;
          if (!reduced) {
            for (const tribute of tributeOrigins.slice(0, 3)) {
              playRulesVfxFlight("tribute", tribute.origin, effectTarget || target, { cardId: tribute.cardId, index: index++ });
            }
            for (const essence of essenceOrigins) {
              const motes = Math.min(3, Math.max(1, Number(essence.amount || 1)));
              for (let mote = 0; mote < motes && index < 6; mote += 1) {
                playRulesVfxFlight("essence", essence.origin, effectTarget || target, { temperament: essence.temperament, index: index++ });
              }
            }
          }
          playRulesVfxImpact(effectTarget || target, t("rulesVfxStackPaymentPaid"), "cost");
        } else {
          playRulesVfxImpact(
            effectTarget || target,
            t(entry.details.status === "cancelled" ? "rulesVfxCancelled" : entry.details.status === "neutralized" ? "rulesVfxNeutralized" : "rulesVfxTargetGone"),
            entry.details.status === "target_missing" ? "target-gone" : "destroyed",
          );
        }
        return;
      }
      if (entry.details?.kind === "chain_manifestation") {
        if (entry.details.status === "chained" && effectTarget) {
          const chainTarget = rulesVfxCenter(rulesVfxFindBattlefieldItem(entry.details.itemId)) || effectTarget;
          playRulesVfxImpact(chainTarget, t("rulesVfxChained"), "resolved");
        }
        return;
      }
      if (effectTarget && entry.details?.kind === "recovery_shared_choice") {
        playRulesVfxImpact(
          effectTarget,
          entry.details.option === "lose_points_10"
            ? "−10"
            : rulesText("rulesVfxDeckDiscarded", { count: entry.details.count || 0 }),
          entry.details.option === "lose_points_10" ? "score-loss" : "discarded",
        );
        return;
      }
      if (effectTarget) playRulesVfxImpact(effectTarget, t("rulesVfxDiscarded"), "discarded");
      if (effectTarget && Number(entry.details?.drawCount || 0) > 0) {
        playRulesVfxImpact(effectTarget, rulesText("rulesVfxDrawn", {
          count: Number(entry.details.drawCount),
        }), "draw");
      }
      return;
    }
    const reduced = rulesVfxReducedMotion();
    let index = 0;
    if (!reduced) {
      for (const tribute of tributeOrigins.slice(0, 3)) {
        playRulesVfxFlight("tribute", tribute.origin, target, { cardId: tribute.cardId, index: index++ });
      }
      for (const essence of essenceOrigins) {
        const motes = Math.min(3, Math.max(1, Number(essence.amount || 1)));
        for (let mote = 0; mote < motes && index < 6; mote += 1) {
          playRulesVfxFlight("essence", essence.origin, target, { temperament: essence.temperament, index: index++ });
        }
      }
      if (sacrifice) playRulesVfxFlight("sacrifice", sacrifice.origin, sacrifice.target, { cardId: sacrifice.cardId, index: index++ });
    }
    if (sourceRect && entry.details?.cost?.sourceExhausted) playRulesVfxExhaust(sourceRect);
    if (sacrifice) playRulesVfxImpact(sacrifice.target, t("rulesVfxSacrificed"), "sacrificed");
    if (tributeOrigins.length || essenceOrigins.length || entry.details?.cost?.sourceExhausted || sacrifice) {
      playRulesVfxImpact(target, t("rulesVfxCostPaid"));
    }
  }
}

let pendingRulesActionSource = null;

let pendingRulesBoardFlow = null;

let pendingSupportDrop = null;

let rulesBoardTargetCleanup = [];

// the field cards a target choice is armed on: a board rebuild (resize, full screen) replaces them
let rulesBoardArmedElements = [];

let rulesBoardPointerMove = null;
