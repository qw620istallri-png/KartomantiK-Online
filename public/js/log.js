// Game log formatting and the confirm dialog.
// Loaded before app.js: declarations only, nothing runs at load time.

function logCardName(cardId, language) {
  const card = cardsById.get(cardId);
  return card?.translations?.[language]?.name || card?.name || cardId;
}

function logTemplate(key, values, language, htmlKeys = new Set(), escapeValues = false) {
  return String(translateFor(key, language)).replace(/\{(\w+)\}/g, (_match, name) => {
    const value = values[name] ?? "";
    return !escapeValues || htmlKeys.has(name) ? String(value) : esc(value);
  });
}

// A die rolled by a card effect, and what it did, as one line of the logs (plain text)
function rulesRollLogText(result, language = currentLanguage) {
  if (!result || typeof result !== "object") return "";
  const tr = (key, values = {}) => logTemplate(key, values, language);
  const signed = (value) => `${Number(value) >= 0 ? "+" : ""}${Number(value)}`;
  const parity = (roll) => tr(Number(roll) % 2 === 0 ? "rulesLogDiceEven" : "rulesLogDiceOdd");
  if (result.kind === "roll_d6_each_target" && Array.isArray(result.rolls)) {
    // Kaos Bro / Karma Bro: one die per chosen card, a 1 or a 6 hits
    const hits = Number(result.hitCount || 0);
    const outcome = !hits ? tr("rulesLogDiceNoEffect")
      : result.onHit === "points" ? tr("rulesLogDicePoints", { value: signed(result.delta || 0) })
      : `${tr("rulesLogDiceDestroyed")}${hits > 1 ? ` ×${hits}` : ""}`;
    return `${tr("rulesLogDiceMany", { rolls: result.rolls.join(", ") })} → ${outcome}`;
  }
  if (Array.isArray(result.rolls) && result.rolls.length) {
    const even = Number(result.evenCount || 0);
    const odd = Number(result.oddCount || 0);
    const parts = [];
    if (even) parts.push(tr("rulesLogDicePowerCounters", { value: signed(even) }));
    if (odd) parts.push(tr("rulesLogDiceHandDiscard", { count: odd }));
    return `${tr("rulesLogDiceMany", { rolls: result.rolls.join(", ") })} → ${parts.join(", ") || tr("rulesLogDiceNoEffect")}`;
  }
  const roll = Number(result.roll);
  if (!Number.isInteger(roll) || roll < 1) return "";
  const head = `${tr("rulesLogDice", { roll })} (${parity(roll)})`;
  let outcome = "";
  if (result.status === "source_missing") outcome = tr("rulesLogDiceSourceGone");
  else if (result.status === "target_missing") outcome = tr("rulesLogDiceTargetGone");
  else if (result.status === "no_target") outcome = tr("rulesLogDiceNoTarget");
  else if (result.kind === "choice_required" && result.choiceKind === "random_target_effect") outcome = tr("rulesLogDiceRandomTarget");
  else if (result.kind === "random_target_effect") outcome = tr("rulesLogDiceRandomTargetHit");
  else if (result.status === "draw") outcome = tr("rulesLogDiceDraw");
  else if (result.essences !== undefined) outcome = tr("rulesLogDiceEssence", { count: result.essences });
  else if (result.discarded !== undefined && typeof result.discarded === "number") {
    outcome = result.discarded
      ? `${tr("rulesLogDiceDeckDiscard", { count: result.discarded })}, ${tr("rulesLogDicePowerCounters", { value: signed(result.discarded) })}`
      : tr("rulesLogDiceNoEffect");
  } else if (result.kind === "roll_d6_move_source_to_stalemate_on_odd") {
    outcome = tr(result.status === "moved" ? "rulesLogDiceToStalemate" : "rulesLogDiceStays");
  } else if (result.delta !== undefined) outcome = tr("rulesLogDicePoints", { value: signed(result.delta) });
  else if (result.outcome) {
    const nested = result.outcome;
    outcome = nested.status === "power" ? tr("rulesLogDicePower", { value: signed(nested.value) })
      : nested.status === "temperament" ? tr("rulesLogDiceTemperament", { temperament: tr(`temperament${String(nested.temperament || "").replace(/^./, (c) => c.toUpperCase())}`) })
      : nested.reason === "destroy" || nested.status === "moved" ? tr("rulesLogDiceDestroyed")
      : tr("rulesLogDiceNoEffect");
  } else if (result.value !== undefined) {
    outcome = Number(result.value) ? tr("rulesLogDicePower", { value: signed(result.value) }) : tr("rulesLogDiceNoEffect");
  }
  return outcome ? `${head} → ${outcome}` : head;
}

function formatLogEntry(e, options = {}) {
  const language = options.language || currentLanguage;
  const html = Boolean(options.html);
  const rawWho = e.actorName || e.actorId || "?";
  const who = html ? `<b style="color:${playerColor(e.actorId)}">${esc(rawWho)}</b>` : rawWho;
  const d = e.details || {};
  const z = (key) => translateFor(key, language) || key;
  const ownerName = (pid) => latestState?.players?.[pid]?.name || pid;
  const cross = d.ownerId && d.ownerId !== e.actorId ? logTemplate("logOwnerSuffix", { owner: ownerName(d.ownerId) }, language) : "";
  const card = (cardId) => {
    if (!cardId) return translateFor("plAnUnknownCard", language);
    const name = logCardName(cardId, language);
    return html ? `<span class="log-card-ref" data-log-card="${esc(cardId)}">${esc(name)}</span>` : name;
  };
  const faceState = (faceUp) => (faceUp === undefined ? "" : translateFor(faceUp ? "logFaceUp" : "logFaceDown", language));
  const viaRequest = (requestedBy) => requestedBy ? logTemplate("logRequestedBy", { requester: requestedBy }, language) : "";
  const f = (key, values = {}, markup = []) => logTemplate(key, { who, ...values }, language, new Set(html ? ["who", ...markup] : []), html);
  switch (e.type) {
    case "import_deck": return f("logImportDeck", { count: d.count });
    case "rules_first_manifestation_trap_placed": return f("logRulesTrapPlaced");
    case "rules_first_manifestation_trap": return f("logRulesTrapRevealed", { card: card(d.cardId), points: Math.abs(Number(d.delta) || 5) }, ["card"]);
    case "draw": return f("logDraw", { count: d.count });
    case "draw_to_limit": return f("logDrawToLimit", { count: d.count });
    case "opening_hand_draw": return f("logOpeningHandDraw", { count: d.count });
    case "rules_opening_mulligan_required": return f("logRulesOpeningMulliganRequired", {
      player: ownerName(e.actorId),
    });
    case "rules_recovery_mulligan_required": return f("logRulesRecoveryMulliganRequired", {
      player: ownerName(e.actorId), turn: d.turn,
    });
    case "rules_opening_defeat": return f("logRulesOpeningDefeat", {
      players: (d.loserIds || []).map(ownerName).join(", "),
    });
    case "rules_recovery_defeat": return f("logRulesRecoveryDefeat", {
      players: (d.loserIds || []).map(ownerName).join(", "), turn: d.turn,
    });
    case "rules_recovery_resumed": return f("logRulesRecoveryResumed", { turn: d.turn });
    case "recovery_draw": {
      const draws = Object.entries(d.draws || {})
        .map(([playerId, count]) => `${ownerName(playerId)} +${count}`)
        .join(", ");
      return f("logRecoveryDraw", { draws });
    }
    case "rules_game_end": return f("logRulesGameEnd");
    case "rules_action_declared": {
      const detailText = (value) => html ? esc(value) : String(value);
      const essenceText = (entries) => {
        const totals = {};
        for (const entry of entries || []) totals[entry.temperament] = (totals[entry.temperament] || 0) + Number(entry.amount || 0);
        return Object.entries(totals).map(([temperament, amount]) => {
          const key = `temperament${temperament[0].toUpperCase()}${temperament.slice(1)}`;
          return `${translateFor(key, language)} ×${amount}`;
        }).join(", ");
      };
      const context = [];
      if (d.source?.cardId) context.push(`${translateFor("rulesSourceShort", language)}: ${card(d.source.cardId)}`);
      if (d.targets?.length) {
        context.push(`${translateFor("rulesTargetsShort", language)}: ${d.targets.map((target) => (
          target.kind === "player"
            ? detailText(ownerName(target.playerId))
            : target.kind === "zone_card"
              ? `${card(target.cardId)} (${detailText(`${ownerName(target.containerId)} · ${translateFor(target.zone, language)}`)})`
              : `${card(target.cardId)} (${detailText(ownerName(target.ownerId))})`
        )).join(", ")}`);
      }
      if (d.target) context.push(`${translateFor("rulesTargetNoteShort", language)}: ${detailText(d.target)}`);
      if (d.cost?.note) context.push(`${translateFor("rulesCostShort", language)}: ${detailText(d.cost.note)}`);
      if (d.cost?.essenceSpent?.length) context.push(`${translateFor("rulesEssenceShort", language)}: ${essenceText(d.cost.essenceSpent)}`);
      if (d.cost?.tributeCardIds?.length) {
        context.push(`${translateFor("rulesTributeShort", language)}: ${d.cost.tributeCardIds.map(card).join(", ")}`);
      }
      if (d.cost?.excessEssence?.length) context.push(`${translateFor("rulesExcessShort", language)}: ${essenceText(d.cost.excessEssence)}`);
      if (d.cost?.sourceExhausted) context.push(translateFor("rulesSourceExhaustedShort", language));
      if (d.cost?.sourceSacrificed) context.push(translateFor("rulesSourceSacrificedShort", language));
      return `${f("logRulesActionDeclared", { action: d.label, depth: d.stackDepth })}${context.length ? ` ${context.join(" · ")}` : ""}`;
    }
    case "rules_action_triggered": {
      const triggered = f("logRulesActionTriggered", {
        source: card(d.source?.cardId), depth: d.stackDepth,
      }, ["source"]);
      const playerTarget = (d.targets || []).find((target) => target.kind === "player");
      return playerTarget
        ? `${triggered} ${f("logRulesTriggerTarget", { target: ownerName(playerTarget.playerId) })}`
        : triggered;
    }
    case "rules_priority_passed": return f("logRulesPriorityPassed");
    case "rules_priority_cancelled": return f("logRulesPriorityCancelled");
    case "rules_action_resolved": {
      const resolved = d.automatic ? "" : f("logRulesActionResolved", { action: d.label, remaining: d.stackDepth });
      const source = d.source?.cardId
        ? `${translateFor("rulesSourceShort", language)}: ${card(d.source.cardId)}`
        : "";
      const active = d.ongoingEffects?.length
        ? f("logRulesOngoingStarted", { count: d.ongoingEffects.length })
        : "";
      let sourceResult = "";
      if (d.sourceResolution?.status === "moved" && d.source?.cardId) {
        sourceResult = f(
          d.sourceResolution.destination === "battlefield"
            ? "logRulesPersistentToField" : "logRulesEphemeralToLimbo",
          { card: card(d.source.cardId) }, ["card"],
        );
      }
      if (d.sourceResolution?.status === "source_missing" && d.source?.cardId) {
        sourceResult = f("logRulesSourceMissing", { card: card(d.source.cardId) }, ["card"]);
      }
      if (d.sourceResolution?.status === "manual_placement" && d.source?.cardId) {
        sourceResult = f("logRulesManualPlacement", { card: card(d.source.cardId) }, ["card"]);
      }
      let applied = "";
      if (d.effectResult?.kind === "score") {
        const delta = Number(d.effectResult.delta || 0);
        applied = f(delta < 0 ? "logRulesScoreLost" : "logRulesScoreApplied", {
          player: ownerName(d.effectResult.playerId),
          delta: `${delta >= 0 ? "+" : ""}${delta}`,
          amount: Math.abs(delta),
          score: d.effectResult.score,
        });
      }
      if (d.effectResult?.kind === "draw") {
        const count = Number(d.effectResult.count || 0);
        applied = f(count === 1 ? "logRulesCardDrawn" : "logRulesCardsDrawn", {
          player: ownerName(d.effectResult.playerId), count,
        });
      }
      if (d.effectResult?.kind === "discard_deck") {
        const result = d.effectResult;
        const discardedCards = (result.cardIds || []).map(card).join(", ");
        applied = result.count
          ? f("logRulesDeckDiscarded", {
              player: ownerName(result.playerId), count: result.count, cards: discardedCards,
            }, ["cards"])
          : f("logRulesDeckEmpty", { player: ownerName(result.playerId) });
      }
      if (d.effectResult?.kind === "move_card") {
        const result = d.effectResult;
        if (result.status === "target_missing") {
          applied = f("logRulesTargetMissing", { card: card(result.cardId) }, ["card"]);
        } else if (result.status === "no_eligible_card") {
          applied = f("logRulesNoEligibleCard");
        } else if (result.status === "removed_copy") {
          applied = f("logRulesTargetCopyRemoved", { card: card(result.cardId) }, ["card"]);
        } else if (result.reason === "destroy") {
          applied = f("logRulesTargetDestroyed", { card: card(result.cardId) }, ["card"]);
        } else if (result.reason === "exile") {
          applied = f("logRulesTargetExiled", { card: card(result.cardId) }, ["card"]);
        } else {
          applied = f("logRulesTargetMoved", {
            card: card(result.cardId),
            position: translateFor(result.position === "bottom" ? "rulesPositionBottom" : "rulesPositionTop", language),
            zone: z(result.toZone),
          }, ["card"]);
        }
      }
      if (d.effectResult?.kind === "neutralize_stack_action") {
        applied = d.effectResult.status === "neutralized"
          ? f("logRulesStackNeutralized", { card: card(d.effectResult.cardId) }, ["card"])
          : f("logRulesStackTargetMissing", { card: card(d.effectResult.cardId) }, ["card"]);
      }
      if (d.effectResult?.kind === "choice_required" && d.effectResult.choiceKind === "chain_manifestation") {
        applied = f("logRulesChainWaiting", {
          player: ownerName(d.effectResult.playerId),
          zone: z(d.effectResult.fromZone),
          source: card(d.source?.cardId),
        }, ["source"]);
      }
      if (d.effectResult?.kind === "choice_required" && d.effectResult.choiceKind === "stack_counter_payment") {
        applied = f("logRulesStackPaymentRequested", {
          player: ownerName(d.effectResult.playerId),
          source: card(d.source?.cardId),
          target: card(d.effectResult.targetCardId),
        }, ["source", "target"]);
      }
      if (d.effectResult?.kind === "choice_required" && d.effectResult.choiceKind === "stack_copy_targets") {
        applied = f("logRulesCopyWaiting", {
          player: ownerName(d.effectResult.playerId),
          source: card(d.source?.cardId),
          target: card(d.effectResult.targetCardId),
        }, ["source", "target"]);
      }
      if (d.effectResult?.kind === "copy_stack_action" && d.effectResult.status === "copied") {
        applied = f("logRulesCopyCreated", {
          player: ownerName(d.controllerId),
          target: card(d.effectResult.cardId),
          targeting: "",
        }, ["target"]);
      }
      if (d.effectResult?.kind === "chain_manifestation" && d.effectResult.status === "no_eligible_card") {
        applied = f("logRulesChainEmpty", { zone: z(d.effectResult.fromZone) });
      }
      // Skysailing Triad: the uncovered card is public, both players read it
      if (d.effectResult?.kind === "resolve_top_deck_by_type" && d.effectResult.cardId) {
        applied = `${applied ? `${applied} ` : ""}${logTemplate("rulesVfxTopRevealed", {}, language)} : ${card(d.effectResult.cardId)}${rulesTopRevealOutcomeKey(d.effectResult) ? ` (${logTemplate(rulesTopRevealOutcomeKey(d.effectResult), {}, language)})` : ""}.`;
      }
      const rollText = rulesRollLogText(d.effectResult, language);
      const dice = rollText ? `${html ? esc(rollText) : rollText}.` : "";
      return [resolved, source, sourceResult, dice, applied, active].filter(Boolean).join(" ");
    }
    case "rules_choice_resolved":
      if (d.kind === "random_target_effect" && d.roll) {
        const rollText = rulesRollLogText(d, language);
        return `${f("logRulesRandomTargetChosen", { player: ownerName(d.playerId), card: card(latestState?.battlefield?.find((item) => item.id === d.itemId)?.cardId) }, ["card"])} ${html ? esc(rollText) : rollText}.`;
      }
      if (d.kind === "simultaneous_stack_order") return f("logRulesSimultaneousOrdered", {
        player: ownerName(d.playerId),
        count: (d.actionIds || []).length,
      });
      if (d.kind === "persist_first_manifestation") return f("logRulesPersistChosen", {
        player: ownerName(d.playerId),
        card: card(d.cardId),
      }, ["card"]);
      if (d.kind === "effect_memory_return") return f(
        d.status === "returned" ? "logRulesMemoryReturned" : "logRulesMemoryDeclined",
        { player: ownerName(d.playerId), card: card(d.cardId) },
        ["card"],
      );
      if (d.kind === "effect_payment") return f(
        d.status === "paid" ? "logRulesEffectPaymentPaid" : "logRulesEffectPaymentDeclined",
        { player: ownerName(d.playerId), card: card(d.sourceCardId) },
        ["card"],
      );
      if (d.kind === "effect_memory_payment") return f(
        d.status === "paid" ? "logRulesMemoryPaymentPaid" : "logRulesMemoryReturned",
        { player: ownerName(d.playerId), card: card(d.cardId) },
        ["card"],
      );
      if (d.kind === "declare_card_name") return f(
        d.status === "matched" ? "logRulesDeclareMatched"
          : d.status === "discarded" ? (d.mode === "search_deck" ? "logRulesDeclareSearchFound" : "logRulesDeclareMissed")
          : d.mode === "search_deck" ? "logRulesDeclareSearchNone" : "logRulesDeclareMissed",
        { player: ownerName(d.playerId), declared: card(d.declaredCardId), card: card(d.revealedCardId || d.cardId) },
        ["declared", "card"],
      );
      if (d.kind === "pick_own_item") return f(d.purpose === "sacrifice" ? "logRulesSacrificeItem" : "logRulesPickOwnItem", {
        player: ownerName(d.playerId),
      });
      if (d.kind === "distribute_power") return f("logRulesDistributePower", {
        player: ownerName(d.playerId),
      });
      if (d.kind === "reveal_hand_discard") return f("logRulesRevealDiscard", {
        player: ownerName(d.playerId), target: ownerName(d.targetPlayerId),
        card: card(d.cardId),
      }, ["card"]);
      if (d.kind === "immediate_effect_payment") return f(
        d.status === "paid"
          ? "logRulesImmediatePaymentPaid"
          : "logRulesImmediatePaymentDeclined",
        {
          player: ownerName(d.playerId),
          card: card(d.sourceCardId),
        },
        ["card"],
      );
      if (d.kind === "stack_copy_targets") return f("logRulesCopyCreated", {
        player: ownerName(d.playerId), target: card(d.targetCardId), targeting: "",
      }, ["target"]);
      if (d.kind === "stack_counter_payment") {
        if (d.status === "paid") return f("logRulesStackPaymentPaid", {
          player: ownerName(d.playerId), target: card(d.targetCardId),
        }, ["target"]);
        if (d.status === "cancelled") return f("logRulesStackEffectCancelled", {
          player: ownerName(d.playerId), target: card(d.targetCardId),
        }, ["target"]);
        if (d.status === "neutralized") return f("logRulesStackCardNeutralizedAfterDecline", {
          player: ownerName(d.playerId), target: card(d.targetCardId),
        }, ["target"]);
        return f("logRulesStackPaymentTargetMissing", { target: card(d.targetCardId) }, ["target"]);
      }
      if (d.kind === "chain_manifestation") {
        if (d.status === "declined") return f("logRulesChainDeclined", {
          player: ownerName(d.playerId), source: card(d.sourceCardId),
        }, ["source"]);
        if (d.status === "chained") return f("logRulesChained", {
          player: ownerName(d.playerId), card: card(d.cardId),
          zone: z(d.fromZone), source: card(d.sourceCardId),
        }, ["card", "source"]);
      }
      if (d.kind === "confrontation_destination") return f("logRulesConfrontationDestination", {
        card: card(d.cardId),
        destination: translateFor(d.destination === "interzone" ? "interzone" : "rulesDeckBottom", language),
      }, ["card"]);
      if (d.kind === "confrontation_replace_interzone") return f("logRulesConfrontationReplacement", {
        card: card(d.cardId), replaced: card(d.replacedCardId),
      }, ["card", "replaced"]);
      if (d.kind === "recovery_shared_choice") {
        return d.option === "lose_points_10"
          ? f("logRulesRecoveryChoicePoints", {
              player: ownerName(d.playerId), score: d.score, source: card(d.sourceCardId),
            }, ["source"])
          : f("logRulesRecoveryChoiceDiscard", {
              player: ownerName(d.playerId), count: d.count,
              cards: (d.cardIds || []).map(card).join(", "), source: card(d.sourceCardId),
            }, ["cards", "source"]);
      }
      return f(Number(d.drawCount || 0) > 0 ? "logRulesChoiceDiscardDraw" : "logRulesChoiceResolved", {
        player: ownerName(d.playerId),
        count: d.count,
        draw: Number(d.drawCount || 0),
        source: card(d.sourceCardId),
      }, ["source"]);
    case "rules_confrontation_compared": {
      const totals = Object.entries(d.totals || {}).map(([playerId, value]) => `${ownerName(playerId)} ${value}`).join(" · ");
      return d.stalemate
        ? f("logRulesConfrontationStalemate", { totals })
        : f("logRulesConfrontationWinner", { player: ownerName(d.winnerId), totals });
    }
    case "rules_confrontation_cleanup": {
      const cleanup = d.stalemate
        ? f("logRulesConfrontationMovedStalemate")
        : f("logRulesConfrontationCleanup", { player: ownerName(d.winnerId), count: (d.captured || []).length });
      const support = (d.supportExiled || []).map((movement) => (
        f("logRulesSupportWinnerExiled", { card: card(movement.cardId) }, ["card"])
      )).join(" ");
      const supportEffects = (d.supportResolved || []).map((result) => (
        result.kind === "opponent_vessel_score"
          ? f("logRulesSupportVesselScore", {
              card: card(result.cardId), player: ownerName(result.playerId),
              delta: result.delta, score: result.score,
            }, ["card"])
          : result.kind === "opponent_vessel"
            ? f("logRulesSupportOpponentVessel", {
                card: card(result.cardId), player: ownerName(result.playerId),
              }, ["card"])
            : ""
      )).filter(Boolean).join(" ");
      const persisted = (d.persisted || []).map((result) => (
        f("logRulesPersisted", { card: card(result.cardId) }, ["card"])
      )).join(" ");
      const vesselRolls = [...(d.captured || []), ...(d.returned || [])]
        .filter((movement) => Number.isInteger(Number(movement.vesselRoll)) && movement.vesselRoll)
        .map((movement) => f(Number(movement.vesselRoll) % 2 ? "logRulesVesselRollHand" : "logRulesVesselRollVessel", {
          card: card(movement.cardId), roll: movement.vesselRoll,
        }, ["card"]))
        .join(" ");
      return [cleanup, support, supportEffects, persisted, vesselRolls].filter(Boolean).join(" ");
    }
    case "rules_field_zone_changed": return f("logRulesEnteredConfrontation", { card: card(d.cardId) }, ["card"]);
    case "rules_priority_rolled": return f("logRulesPriorityRolled", {
      player: ownerName(d.playerId),
      rolls: Object.entries(d.rolls || {}).map(([id, value]) => `${ownerName(id)} ${value}`).join(" · "),
    });
    case "rules_auto_passed": {
      const lines = phaseLogLinesFor(d, language);
      const label = [lines.phase, lines.step].filter(Boolean).join(" · ") || d.phaseId || "?";
      return f("logRulesAutoPassed", { phase: label, turn: d.turn || 1, steps: d.steps || 0 });
    }
    case "rules_auto_skip_changed": return f(d.enabled ? "logRulesAutoSkipOn" : "logRulesAutoSkipOff");
    case "rules_pass_all_changed": return f(d.enabled ? "logRulesPassAllOn" : "logRulesPassAllOff", { player: ownerName(d.playerId) });
    case "rules_phase_advanced": {
      const lines = phaseLogLinesFor(d, language);
      const label = [lines.phase, lines.step].filter(Boolean).join(" · ") || d.phaseId || "?";
      const advanced = f("logRulesPhaseAdvanced", { phase: label, turn: d.turn || 1 });
      const rematch = d.rematchStarted ? ` ${f("logRulesRematchStarted")}` : "";
      const expired = d.expiredEffectIds?.length
        ? ` ${f("logRulesOngoingExpired", { count: d.expiredEffectIds.length })}`
        : "";
      return `${advanced}${expired}${rematch}`;
    }
    case "shuffle": return f("logShuffle", { zone: z(d.zone), cross });
    case "reorder": return f("logReorder", { zone: z(d.zone), cross });
    case "reveal": return f("logReveal", { count: d.count, zone: z(d.zone), cross, request: viaRequest(d.requestedBy) });
    case "scry": return f("logScry", { count: d.count });
    case "search_zone": return f("logSearch", { zone: z(d.zone), count: d.count, warning: d.requiresShuffle ? translateFor("logShuffleExpected", language) : "" });
    case "search_followed_by_shuffle": return f("logSearchResolved", { zone: z(d.zone) });
    case "search_without_shuffle": return f("logSearchUnshuffled", { zone: z(d.zone), action: translateFor(`logAction_${d.followupAction}`, language) || d.followupAction });
    case "move_card": return f("logMoveCard", { card: card(d.cardId), from: z(d.fromZone), to: z(d.toZone), request: viaRequest(d.requestedBy) }, ["card"]);
    case "place_card": return d.asSupport
      ? f("logPlaceSupportCard", { card: card(d.cardId), from: z(d.fromZone) }, ["card"])
      : f("logPlaceCard", { card: card(d.cardId), from: z(d.fromZone), face: faceState(d.faceUp) }, ["card"]);
    case "copy_card": return f("logCopyCard", { card: card(d.cardId) }, ["card"]);
    case "move_battlefield_item": return f("logMoveFieldCard");
    case "reorder_battlefield_item": return f("logReorderFieldCard");
    case "flip_card": return f("logFlipCard", { card: card(d.cardId), face: faceState(d.faceUp) }, ["card"]);
    case "remove_battlefield_item": return d.copyCard ? f("logRemoveCopy", { card: card(d.cardId) }, ["card"]) : d.tokenCard ? f("logRemoveTokenCard") : f("logRemoveFieldCard", { card: card(d.cardId), to: z(d.toZone), face: faceState(d.faceUp) }, ["card"]);
    case "create_token_card": return f("logCreateTokenCard", { temperament: translateFor("temperament" + d.temperament[0].toUpperCase() + d.temperament.slice(1), language), power: `${d.power > 0 ? "+" : ""}${d.power}` });
    case "create_essence_token":
      if (d.neutral) return f("logCreateNeutralCounter", { label: d.label || translateFor("neutralToken", language), count: `${d.count > 0 ? "+" : ""}${d.count}` });
      return f("logCreateEssence", { count: d.count, temperament: translateFor("temperament" + d.temperament[0].toUpperCase() + d.temperament.slice(1), language) });
    case "rename_token": return f("logRenameToken");
    case "mulligan": return f(d.scoreCost ? "logMulliganPaid" : "logMulligan", {
      count: d.count, cost: d.scoreCost, score: d.score,
    });
    case "rules_player_ready": return f("logRulesPlayerReady", { player: ownerName(e.actorId) });
    case "rules_match_started": return f("logRulesMatchStarted");
    case "add_token": return f("logAddToken");
    case "move_token": return f("logMoveToken");
    case "remove_token": return f("logRemoveToken");
    case "add_counter": return f("logAdjustCounter", { delta: `${d.delta > 0 ? "+" : ""}${d.delta}` });
    case "reset_counter": return f("logResetCounter");
    case "set_score": return f("logSetScore", { score: d.score });
    case "configure_phases": return f(d.enabled ? "logActivatePhases" : "logDeactivatePhases", { advanced: d.enabled && d.advanced ? translateFor("logAdvancedSuffix", language) : "" });
    case "pass_phase": {
      const lines = phaseLogLinesFor(d, language);
      const label = [lines.phase, lines.step].filter(Boolean).join(" · ") || d.phaseId || d.phase || "?";
      if (d.action === "cancelled") return f("logCancelPass");
      if (d.action === "advanced") return f("logAdvancePhase", { phase: label, turn: d.turn || 1 });
      return f("logPassPhase", { phase: label });
    }
    case "end_session": return f("logEndSession");
    case "concede": return f("logConcede");
    case "create_tournament": return f("logCreateTournament");
    case "role_joined": return f("logRoleJoined", { role: translateFor(d.role || "participant", language), seat: Number.isInteger(d.seat) ? ` (P${d.seat + 1})` : "" });
    case "leave_session": return f("logLeftSession");
    case "player_disconnected": return f("logDisconnected");
    case "start_tournament": return f("logStartTournament");
    case "end_tournament": return f("logEndTournament");
    case "update_tournament_policy": return f("logUpdatePolicy", { banned: d.bannedCount, groups: d.restrictedGroupCount });
    case "add_stroke": return f("logAddStroke");
    case "remove_stroke": return f("logRemoveStroke");
    case "remove_strokes_in_rect": return f("logRemoveStrokes", { count: d.count });
    case "clear_own_strokes": return f("logClearStrokes");
    case "roll_dice": return d.mode === "d6" ? f("logRollDice", { count: d.results.length, results: d.results.join(", ") }) : f("logFlipCoin", { count: d.results.length, results: d.results.join(", ") });
    case "reset_board": return f("logResetBoard");
    case "chat_message": return f("logChat", { text: d.text });
    default: return f("logUnknown", { type: e.type });
  }
}

function wireLogCardNames(container) {
  container.querySelectorAll("[data-log-card]").forEach((element) => {
    const cardId = element.dataset.logCard;
    element.addEventListener("mouseenter", () => showCardPreview(cardId, element));
    element.addEventListener("mouseleave", hideCardPreview);
    element.addEventListener("click", () => showInspect(cardId));
  });
}

let latestLogEntries = [];

function renderLog(entries) {
  latestLogEntries = entries;
  const box = $("#logEntries");
  box.innerHTML = entries.length
    ? entries
        .map(
          (e) => `<div class="log-entry">
      <div class="t">${new Date(e.timestamp * 1000).toLocaleString()}</div>
      <div class="what">${formatLogEntry(e, { html: true })}</div>
      <div class="detail">${esc(JSON.stringify(e.details || {}))}</div>
    </div>`
        )
        .join("")
    : `<p>${esc(t("logEmpty"))}</p>`;
  wireLogCardNames(box);
  $("#logPanel").classList.remove("hidden");
}

function downloadLog(entries) {
  const lines = entries.map((e) => `[${new Date(e.timestamp * 1000).toLocaleString("en-GB")}] ${formatLogEntry(e, { language: "en" })} ${JSON.stringify(e.details || {})}`);
  const blob = new Blob([lines.join("\n")], { type: "text/plain" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `kartomantik-online-log-${Date.now()}.txt`;
  link.click();
  URL.revokeObjectURL(link.href);
}

// ---------------------------------------------------------------- confirm modal
// An in-app replacement for window.confirm(), themed like every other panel
// instead of popping the browser's own dialog.

let pendingConfirmCallback = null;

function initConfirmPanel() {
  $("#confirmPanelCancelBtn").textContent = t("close");
  $("#confirmPanelCancelBtn").onclick = () => {
    pendingConfirmCallback = null;
    $("#confirmPanel").classList.add("hidden");
  };
  $("#confirmPanelOkBtn").onclick = () => {
    const cb = pendingConfirmCallback;
    pendingConfirmCallback = null;
    $("#confirmPanel").classList.add("hidden");
    if (cb) cb();
  };
}

function showConfirm(message, onConfirm, confirmLabel) {
  $("#confirmPanelText").textContent = message;
  $("#confirmPanelOkBtn").textContent = confirmLabel || t("confirm");
  pendingConfirmCallback = onConfirm;
  $("#confirmPanel").classList.remove("hidden");
}
