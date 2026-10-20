(() => {
  "use strict";

  const STORAGE_KEY = "kko_audio_enabled";
  const VOLUME_STORAGE_KEY = "kko_audio_volume";
  const BASE = "audio/ui/";
  const CUES = {
    menuClick: { files: ["UI_MouseClick_01.ogg"], volume: 0.17, cooldown: 55 },
    confirm: { files: ["floating_button_press.ogg"], volume: 0.22, cooldown: 120 },
    error: { files: ["UI_no_can_do.ogg"], volume: 0.27, cooldown: 450 },
    draw: { files: ["draw_card_1.ogg", "draw_card_2.ogg", "draw_card_3.ogg"], volume: 0.24, cooldown: 100 },
    drawMany: { files: ["draw_card_1.ogg", "draw_card_2.ogg", "draw_card_3.ogg"], volume: 0.27, cooldown: 240 },
    effectDraw: { files: ["draw_card_and_add_to_hand_1.ogg", "draw_card_and_add_to_hand_2.ogg", "draw_card_and_add_to_hand_3.ogg"], volume: 0.25, cooldown: 100 },
    drawIntoPlay: { files: ["draw_card_into_play.ogg"], volume: 0.27, cooldown: 150 },
    cardPlay: { files: ["play_card_from_hand_1.ogg", "play_card_from_hand_2.ogg", "play_card_from_hand_3.ogg"], volume: 0.3, cooldown: 120 },
    cardFlip: { files: ["card_turn_over_normal.ogg", "card_turn_over_rare.ogg", "card_turn_over_epic.ogg", "card_turn_over_legendary.ogg"], volume: 0.27, cooldown: 100 },
    cardFlipNormal: { files: ["card_turn_over_normal.ogg"], volume: 0.23, cooldown: 100 },
    cardFlipRare: { files: ["card_turn_over_rare.ogg"], volume: 0.25, cooldown: 100 },
    cardFlipEpic: { files: ["card_turn_over_epic.ogg"], volume: 0.27, cooldown: 100 },
    cardFlipLegendary: { files: ["card_turn_over_legendary.ogg"], volume: 0.29, cooldown: 100 },
    cardPlace: { files: ["collection_manager_drop_card.ogg"], volume: 0.24, cooldown: 110 },
    cardMove: { files: ["collection_manager_place_card_in_deck.ogg"], volume: 0.22, cooldown: 130 },
    destroyed: { files: ["Shared_Armor_Destroyed_1.ogg"], volume: 0.3, cooldown: 180 },
    summon: { files: ["FX_MinionSummon03_CardActivated_05.ogg"], volume: 0.28, cooldown: 180 },
    effectTrigger: { files: ["Trigger_Effect_Cast_01.ogg", "Trigger_Effect_Cast_02.ogg", "Trigger_Effect_Cast_03.ogg"], volume: 0.25, cooldown: 180 },
    effectResolve: { files: ["Generic_Untargeted_Cast_01.ogg"], volume: 0.24, cooldown: 170 },
    discard: { files: ["Fatigue_DismissPoof_01.ogg", "Fatigue_DismissPoof_02.ogg", "Fatigue_DismissPoof_03.ogg"], volume: 0.25, cooldown: 180 },
    targetNegative: { files: ["Priest_ShadowWordPain_Impact_1.ogg"], volume: 0.29, cooldown: 180 },
    targetBonus: { files: ["Holy_Heal_Cast_01.ogg", "Holy_Heal_Cast_02.ogg", "Holy_Heal_Cast_03.ogg"], volume: 0.27, cooldown: 180 },
    capture: { files: ["arena_key_transition.ogg"], volume: 0.3, cooldown: 500 },
    essenceGain: { files: ["mana_crystal_add.ogg"], volume: 0.28, cooldown: 120 },
    essenceSpend: { files: ["mana_crystal_expend.ogg"], volume: 0.26, cooldown: 120 },
    notEnough: { files: ["UI_no_can_do.ogg"], volume: 0.27, cooldown: 500 },
    yourTurn: { files: ["UI_BnetToast.ogg"], volume: 0.27, cooldown: 1400 },
    turnStart: { files: ["FX_EndTurnFlip.ogg"], volume: 0.24, cooldown: 900 },
    matchStart: { files: ["FX_GameStart09_CardsOntoTable.ogg"], volume: 0.3, cooldown: 3000 },
    confrontationWin: { files: ["arena_reward_open_normal.ogg"], volume: 0.32, cooldown: 1200 },
    confrontationLose: { files: ["defeat_screen_start.ogg"], volume: 0.3, cooldown: 1200 },
    victory: { files: ["victory_jingle.ogg"], volume: 0.38, cooldown: 5000 },
    defeat: { files: ["defeat_jingle.ogg"], volume: 0.36, cooldown: 5000 },
    matchDraw: { files: ["FX_EndTurnFlip.ogg"], volume: 0.3, cooldown: 5000 },
  };

  let enabled = true;
  let masterVolume = 1;
  try {
    enabled = localStorage.getItem(STORAGE_KEY) !== "off";
    const storedVolume = localStorage.getItem(VOLUME_STORAGE_KEY);
    if (storedVolume !== null && Number.isFinite(Number(storedVolume))) {
      masterVolume = Math.max(0, Math.min(1, Number(storedVolume)));
    }
  } catch {}
  let unlocked = false;
  let lastLogSequence = null;
  const templates = new Map();
  const lastPlayed = new Map();
  const lastVariant = new Map();

  function chooseFile(name, files) {
    if (files.length === 1) return files[0];
    const previous = lastVariant.get(name);
    const candidates = files.filter((file) => file !== previous);
    const file = candidates[Math.floor(Math.random() * candidates.length)];
    lastVariant.set(name, file);
    return file;
  }

  function template(file) {
    if (!templates.has(file)) {
      const audio = new Audio(BASE + file);
      audio.preload = "auto";
      templates.set(file, audio);
    }
    return templates.get(file);
  }

  function unlock() {
    unlocked = true;
    ["UI_MouseClick_01.ogg", "play_card_from_hand_1.ogg", "UI_BnetToast.ogg", "UI_no_can_do.ogg"].forEach(template);
  }

  function play(name, options = {}) {
    const cue = CUES[name];
    if (!enabled || !unlocked || !cue) return false;
    const now = performance.now();
    if (lastPlayed.has(name) && now - lastPlayed.get(name) < Number(options.cooldown ?? cue.cooldown ?? 0)) return false;
    lastPlayed.set(name, now);
    const file = chooseFile(name, cue.files);
    const audio = template(file).cloneNode();
    audio.volume = Math.max(0, Math.min(1, Number(options.volume ?? cue.volume ?? 0.4) * masterVolume));
    audio.playbackRate = Number(options.rate || 1);
    audio.play().catch(() => {});
    return true;
  }

  function setEnabled(next) {
    enabled = Boolean(next);
    try { localStorage.setItem(STORAGE_KEY, enabled ? "on" : "off"); } catch {}
    if (enabled) unlock();
    return enabled;
  }

  function setVolume(next) {
    const numeric = Number(next);
    if (!Number.isFinite(numeric)) return masterVolume;
    masterVolume = Math.max(0, Math.min(1, numeric));
    try { localStorage.setItem(VOLUME_STORAGE_KEY, String(masterVolume)); } catch {}
    return masterVolume;
  }

  function handCount(state, playerId) {
    const hand = state?.players?.[playerId]?.zones?.hand;
    if (!hand) return 0;
    return Number(hand.count ?? hand.cards?.length ?? 0);
  }

  function essenceTotal(state, playerId) {
    return (state?.tokens || []).reduce((sum, token) => (
      token.ownerId === playerId && token.isEssence && !token.isNeutralCounter
        ? sum + Math.max(0, Number(token.counters?.essence || 0))
        : sum
    ), 0);
  }

  function freshLogEntries(state) {
    const entries = (state?.recentLog || [])
      .filter((entry) => Number.isFinite(Number(entry.sequence)))
      .sort((a, b) => Number(a.sequence) - Number(b.sequence));
    const newest = Number(entries.at(-1)?.sequence || 0);
    if (lastLogSequence === null || newest < lastLogSequence) {
      lastLogSequence = newest;
      return [];
    }
    const fresh = entries.filter((entry) => Number(entry.sequence) > lastLogSequence);
    if (fresh.length) lastLogSequence = Number(fresh.at(-1).sequence);
    return fresh;
  }

  function outcomeCue(details, playerId, confrontation = false) {
    if (details?.stalemate) return "matchDraw";
    const winners = details?.winnerIds || (details?.winnerId ? [details.winnerId] : []);
    const losers = details?.loserIds || (details?.loserId ? [details.loserId] : []);
    if (winners.includes(playerId)) return confrontation ? "confrontationWin" : "victory";
    if (losers.includes(playerId)) return confrontation ? "confrontationLose" : "defeat";
    return confrontation ? null : "matchDraw";
  }

  function resolutionCue(details) {
    const result = details?.effectResult || details || {};
    const ongoing = details?.ongoingEffects || [];
    const text = JSON.stringify({ result, ongoing }).toLowerCase();
    if (/discard/.test(text)) return "discard";
    const values = [result.delta, result.value, ...ongoing.map((effect) => effect?.value)]
      .map(Number).filter(Number.isFinite);
    if (values.some((value) => value < 0)
      || /(destroy|exile|weaken|lose|remove|lock|ignore|reduce|sacrifice|neutraliz|cancel|debuff|damage)/.test(text)) return "targetNegative";
    if (values.some((value) => value > 0)
      || /(gain|draw|score|ready|increase|heal|bonus|copy|create|essence|buff)/.test(text)) return "targetBonus";
    return "effectResolve";
  }

  function observeLogEntries(entries, playerId) {
    for (const entry of entries) {
      const details = entry.details || {};
      if (entry.type === "rules_match_started") play("matchStart");
      else if (entry.type === "rules_action_triggered") play("effectTrigger");
      else if (entry.type === "rules_action_resolved" || entry.type === "rules_choice_resolved") play(resolutionCue(details));
      else if (entry.type === "rules_action_declared" && /discard/.test(JSON.stringify(details.cost || {}).toLowerCase())) play("discard");
      else if (entry.type === "rules_confrontation_compared") {
        const cue = outcomeCue(details, playerId, true);
        if (cue) play(cue);
      } else if (entry.type === "rules_confrontation_cleanup" && (details.captured || []).length) play("capture");
      else if (entry.type === "rules_game_end") play(outcomeCue(details, playerId));
    }
  }

  function flipCue(item) {
    const printed = globalThis.cardsById?.get?.(item?.cardId);
    const power = Number(item?.effectivePower ?? item?.power ?? printed?.power ?? 0);
    if (power >= 10) return "cardFlipLegendary";
    if (power >= 7) return "cardFlipEpic";
    if (power >= 4) return "cardFlipRare";
    return "cardFlipNormal";
  }

  function logText(entries) {
    return JSON.stringify(entries || []).toLowerCase();
  }

  function observeState(previous, next, playerId) {
    if (!next || !playerId) return;
    const freshEntries = freshLogEntries(next);
    if (!previous) return;

    const freshText = logText(freshEntries);
    const beforeHand = handCount(previous, playerId);
    const afterHand = handCount(next, playerId);
    if (afterHand > beforeHand) {
      const effectDraw = freshEntries.some((entry) => (
        ["rules_action_resolved", "rules_choice_resolved"].includes(entry.type)
        && /draw/.test(JSON.stringify(entry.details || {}).toLowerCase())
      ));
      play(effectDraw ? "effectDraw" : (afterHand - beforeHand > 2 ? "drawMany" : "draw"));
    }

    const beforeStack = new Set((previous.rulesEngine?.actionStack || []).map((action) => action.id));
    const addedActions = (next.rulesEngine?.actionStack || []).filter((action) => !beforeStack.has(action.id));
    if (addedActions.some((action) => action.kind === "play_card" && action.sourceOnStack)) play("cardPlay");
    else if (addedActions.some((action) => action.kind === "triggered_effect")) play("effectTrigger");

    const beforeItems = new Map((previous.battlefield || []).map((item) => [item.id, item]));
    const afterItems = new Map((next.battlefield || []).map((item) => [item.id, item]));
    const arrived = [...afterItems.values()].filter((item) => item.faceUp && !beforeItems.has(item.id));
    const removed = [...beforeItems.values()].filter((item) => !afterItems.has(item.id));
    const flipped = [...afterItems.values()].filter((item) => (
      beforeItems.has(item.id) && Boolean(beforeItems.get(item.id).faceUp) !== Boolean(item.faceUp)
    ));
    const moved = [...afterItems.values()].some((item) => (
      beforeItems.has(item.id)
      && beforeItems.get(item.id).fieldZone !== item.fieldZone
    )) || /(move_card|move_battlefield_item|rules_field_zone_changed)/.test(freshText);
    const topDeckIntoPlay = arrived.length > 0 && /"fromzone":"deck"/.test(freshText);
    if (arrived.some((item) => item.isTokenCard)) play("summon");
    else if (topDeckIntoPlay) play("drawIntoPlay");
    else if (arrived.some((item) => item.cardId)) play("cardPlace");
    if (flipped.length) {
      const strongest = flipped.reduce((best, item) => {
        const value = Number(item?.effectivePower ?? item?.power ?? globalThis.cardsById?.get?.(item?.cardId)?.power ?? 0);
        return !best || value > best.value ? { item, value } : best;
      }, null);
      play(flipCue(strongest?.item));
    }
    if (moved) play("cardMove");
    else if (removed.length && !/(capture|move|return|deck|hand|receptacle|graveyard|exile)/.test(freshText)) play("destroyed");

    const beforeEssence = essenceTotal(previous, playerId);
    const afterEssence = essenceTotal(next, playerId);
    if (afterEssence > beforeEssence) play("essenceGain");
    else if (afterEssence < beforeEssence) play("essenceSpend");

    const beforePriority = previous.rulesEngine?.priorityPlayerId;
    const afterPriority = next.rulesEngine?.priorityPlayerId;
    if (afterPriority !== beforePriority && afterPriority === playerId) play("yourTurn");

    const beforeTurn = Number(previous.phaseTracker?.turn || 0);
    const afterTurn = Number(next.phaseTracker?.turn || 0);
    if (afterTurn > beforeTurn) play("turnStart");
    if (!previous.rulesEngine?.firstManifestationComplete && next.rulesEngine?.firstManifestationComplete) play("matchStart");

    observeLogEntries(freshEntries, playerId);

    const beforeOutcome = previous.rulesEngine?.outcome;
    const outcome = next.rulesEngine?.outcome;
    if (!beforeOutcome && outcome) play(outcomeCue(outcome, playerId));
  }

  document.addEventListener("pointerdown", unlock, { capture: true, once: true });
  document.addEventListener("focusin", unlock, { capture: true, once: true });
  document.addEventListener("click", (event) => {
    const button = event.target.closest?.("button, summary");
    if (!button || button.disabled || button.id === "soundToggleBtn") return;
    const deckButton = button.matches("#importDeckBtn, #importPasteBtn, #importConfirmBtn, #sideboardValidateBtn")
      || button.id === "rulesOpeningHandBtn"
      || (button.id === "rulesPregameReadyBtn" && button.dataset.action === "deck");
    play(deckButton || !button.classList.contains("primary") ? "menuClick" : "confirm");
  }, { capture: true });

  window.KKOAudio = {
    play,
    observeState,
    setEnabled,
    setVolume,
    getVolume() { return masterVolume; },
    toggle() { return setEnabled(!enabled); },
    isEnabled() { return enabled; },
    unlock,
  };
})();
