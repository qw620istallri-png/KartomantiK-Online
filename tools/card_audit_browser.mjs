// Two independent browser seats, real WebSockets and production UI handlers.
// DOM-dispatched targets are reported separately from physical pointer checks.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import readline from "node:readline";
import assert from "node:assert/strict";
import { chromium } from "playwright";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const out = path.join(root, "reports/systematic-audit");
fs.mkdirSync(out, { recursive: true });
const server = spawn(process.env.PYTHON || "python", ["-B", "tools/card_audit_server.py"], {
  cwd: root, windowsHide: true, env: process.env, stdio: ["pipe", "pipe", "pipe"],
});
let stderr = "";
server.stderr.on("data", (chunk) => { stderr += chunk; });
const pending = new Map();
const actionsOnly = process.argv.includes("--actions-only");
const focus = process.argv.find((arg) => arg.startsWith("--focus="))?.slice(8).split(",");
const debugRun = actionsOnly || Boolean(focus);
let requestId = 0;
let readyResolve, readyReject;
const ready = new Promise((resolve, reject) => { readyResolve = resolve; readyReject = reject; });
readline.createInterface({ input: server.stdout }).on("line", (line) => {
  const data = JSON.parse(line);
  if (data.port) return readyResolve(data);
  const waiter = pending.get(data.requestId);
  if (!waiter) return;
  clearTimeout(waiter.timeout); pending.delete(data.requestId);
  if (data.error) waiter.reject(new Error(data.error)); else waiter.resolve(data.result);
});
server.on("exit", (code) => {
  readyReject(new Error(`Audit server exited ${code}: ${stderr.slice(-4000)}`));
  for (const waiter of pending.values()) { clearTimeout(waiter.timeout); waiter.reject(new Error(stderr)); }
  pending.clear();
});
function control(command, args = {}) {
  const id = ++requestId;
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => { pending.delete(id); reject(new Error(`Control timeout: ${command}`)); }, 30000);
    pending.set(id, { resolve, reject, timeout });
    server.stdin.write(JSON.stringify({ command, requestId: id, ...args }) + "\n");
  });
}
const result = { schemaVersion: 1, sourceDigest: null, rendering: [], actions: [], journeys: [], errors: [] };
let browser;
let expectedActionCount = null;
try {
  const address = await ready;
  result.sourceDigest = address.sourceDigest;
  browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "chrome", headless: true });
  const pages = {};
  const frames = { p1: [], p2: [] };
  const errors = { p1: [], p2: [] };
  for (const pid of ["p1", "p2"]) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    await context.addInitScript((id) => { localStorage.setItem("ko_clientId", id); localStorage.setItem("ko_vfx_speed", "fast"); }, pid);
    const page = pages[pid] = await context.newPage();
    page.setDefaultTimeout(8000);
    page.on("pageerror", (error) => result.errors.push({ player: pid, message: error.message }));
    page.on("websocket", (socket) => {
      socket.on("framesent", ({ payload }) => frames[pid].push(JSON.parse(payload.toString())));
      socket.on("framereceived", ({ payload }) => {
        const message = JSON.parse(payload.toString());
        if (message.type === "error") errors[pid].push(message.message);
      });
    });
    await page.route("**/*", (route) => new URL(route.request().url()).hostname === "127.0.0.1" ? route.continue() : route.abort());
    await page.goto(`http://127.0.0.1:${address.port}/`);
    await page.waitForFunction(() => cardsById.size === 450 && typeof connectAndJoin === "function" && document.querySelector("#passPriorityBtn").onclick);
    await page.evaluate((code) => connectAndJoin({ code, name: localStorage.getItem("ko_clientId") }), address.code);
    await page.waitForFunction((id) => myPlayerId === id && latestState?.players?.p2, pid);
  }

  async function load(command, args = {}) {
    // A fresh fixture is a new isolated scenario, not the continuation of the
    // previous game's unfinished animation/selection queue.
    for (const page of Object.values(pages)) await page.evaluate(() => clearConnectionGameInteractions());
    const fixture = await control(command, args);
    for (const page of Object.values(pages)) {
      await page.waitForFunction((rev) => latestState?.recentLog?.some((entry) => entry.type === "audit_fixture" && entry.details.revision === rev), fixture.revision);
      // Only synthetic card labels and characteristics are supplied; state and
      // legal-target flags always come from the actual server recipient view.
      await page.evaluate((cards) => { for (const card of cards) cardsById.set(card.id, { image: "card-back.webp", ...card }); renderAll(); }, fixture.overrides);
    }
    return fixture;
  }
  const catalog = await control("catalog");
  expectedActionCount = catalog.actions.length;
  for (const card of debugRun ? [] : catalog.cards) {
    await load("render", { cardId: card.id });
    const views = {};
    for (const [pid, page] of Object.entries(pages)) views[pid] = await page.evaluate((cid) => {
      const hand = Boolean(document.querySelector(`[data-hand-card="${CSS.escape(cid)}"]`));
      const fieldIds = (latestState.battlefield || []).filter((i) => i.cardId === cid).map((i) => i.id);
      const field = fieldIds.some((id) => document.querySelector(`.bf-card[data-item-id="${CSS.escape(id)}"]`));
      const publicZone = [...document.querySelectorAll("[data-zone-card]")].some((e) => e.dataset.zoneCard.endsWith(`:${cid}`));
      const hiddenHand = latestState.players[myPlayerId === "p1" ? "p2" : "p1"].zones.hand;
      return { rendered: hand || field || publicZone, opponentHandHidden: !(hiddenHand.cards || []).some(Boolean) };
    }, card.id);
    // Gorte explicitly reveals opponents' Hands while it is on the field.
    const privacyCorrect = card.id === "w8364ml7m6erl8s_en"
      ? !views.p1.opponentHandHidden && views.p2.opponentHandHidden
      : Object.values(views).every((v) => v.opponentHandHidden);
    result.rendering.push({ cardId: card.id, views, privacyRule: card.id === "w8364ml7m6erl8s_en" ? "printed-Gorte-reveal" : "private-hand", status: views.p1.rendered && privacyCorrect ? "pass" : "fail" });
  }
  console.log(JSON.stringify({ rendering: result.rendering.length, failed: result.rendering.filter((r) => r.status === "fail").length }));

  async function answerChoice(choice) {
    const page = pages[choice.playerId];
    await page.waitForFunction((id) => latestState?.rulesEngine?.pendingChoice?.id === id && rulesAnimationsBusyFor() <= 0, choice.id, { timeout: 25000 });
    // Wait for normal render timers; do not replace client state or transport.
    await page.waitForTimeout(70);
    if (choice.kind === "deck_reorder") {
      for (const group of choice.groups) {
        const section = `[data-rules-reorder-group="${group.playerId}"]`;
        let index = 0;
        while (await page.locator(`${section} [data-rules-reorder-strip="pool"] .rules-reorder-card`).count()) {
          const side = index < Number(group.extraMin || 0) ? "extra"
            : group.topCount != null && index - Number(group.extraMin || 0) >= Number(group.topCount) ? "bottom" : "top";
          const card = await page.locator(`${section} [data-rules-reorder-strip="pool"] .rules-reorder-card`).first().boundingBox();
          const lane = await page.locator(`${section} [data-rules-reorder-strip="${side}"]`).boundingBox();
          assert.ok(card && lane, "Reorder card/lane not visible");
          await page.mouse.move(card.x + card.width / 2, card.y + card.height / 2);
          await page.mouse.down();
          await page.mouse.move(lane.x + lane.width / 2, lane.y + lane.height / 2, { steps: 6 });
          await page.mouse.up();
          assert.ok(++index <= group.cardIds.length, "Reorder drag did not leave pool");
        }
      }
      await page.locator("#rulesDeckReorderConfirm").click();
      return "physical-pointer-deck-reorder";
    }
    return page.evaluate(() => {
      const choice = latestState.rulesEngine.pendingChoice;
      const click = (selector) => {
        const button = document.querySelector(selector);
        if (!button || button.disabled || button.closest(".hidden")) return false;
        button.click(); return true;
      };
      if (["effect_payment", "stack_counter_payment", "immediate_effect_payment", "effect_memory_payment"].includes(choice.kind)) {
        if (click("#rulesFlowPayBtn")) return "pay";
        if (click("#rulesFlowDeclineBtn")) return "decline-payment";
      }
      if (choice.kind === "stack_copy_targets" && click("#rulesFlowDeclineBtn")) return "keep-copy-targets";
      if (choice.kind === "discard_from_hand") {
        const limit = Number(choice.count || 1);
        if (Array.isArray(choice.candidateCardIds)) {
          const buttons = [...document.querySelectorAll("[data-rules-discard-index]")];
          for (const button of buttons.slice(0, Math.min(limit, buttons.length))) button.click();
          click("#rulesDiscardConfirm");
        } else {
          const types = choice.requireTypes || (choice.requireManifestation ? ["manifestation"] : null);
          const candidates = latestState.players[myPlayerId].zones.hand.cards.map((cid, index) => ({ cid, index }))
            .filter((c) => (!types || types.includes(cardsById.get(c.cid)?.type))
              && !(choice.destination === "stalemate_for_support" && c.index === latestState.players[myPlayerId].zones.hand.cards.indexOf(choice.sourceCardId)));
          for (const card of candidates.slice(0, limit)) pickHandDropCard(card.index, true);
          click("#rulesDiscardConfirm");
        }
        return "production-discard-handler";
      }
      if (choice.kind === "chain_manifestation") {
        if (click("[data-rules-chain-card]")) return "chain-public-card";
        const card = latestState.players[myPlayerId].zones.hand.cards.find((cid) => rulesChainCardEligible(cid));
        if (card) {
          const rect = document.querySelector("#battlefield").getBoundingClientRect();
          resolveDrop({ kind: "card", cardId: card, fromOwnerId: myPlayerId, fromZone: "hand" }, rect.x + rect.width / 2, rect.y + rect.height / 2);
          return "production-chain-drop-handler";
        }
        if (choice.optional && click("#rulesFlowCancelBtn")) return "decline-chain";
      }
      if (choice.kind === "declare_card_name") {
        const input = document.querySelector("#rulesDeclareNameInput");
        input.value = cardName("inner-deserts-047"); input.dispatchEvent(new Event("input", { bubbles: true }));
        if (click("#rulesDeclareNameConfirm")) return "declare-catalog-name";
      }
      if (choice.kind === "trigger_targets") {
        const player = document.querySelector("[data-player-target]");
        if (player) { player.click(); return "trigger-player"; }
        const target = document.querySelector(".rules-valid-target");
        if (target) { target.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, cancelable: true, pointerId: 1 })); return "trigger-target"; }
      }
      const selectors = { pick_own_item: "[data-rules-pick-item]", reveal_hand_discard: "[data-rules-reveal-index]",
        random_target_effect: "[data-rules-random-target]",
        peek_top_card: '[data-rules-peek-option="keep"]', score_delta_choice: '[data-rules-score-option="gain"]',
        optional_stack_action: '[data-rules-optional-trigger="accept"]', optional_trigger: '[data-rules-optional-trigger="accept"]',
        temperament_choice: "[data-rules-temperament-option]", suspend_hand_will: "[data-rules-suspend-card]",
        binary_choice: "[data-rules-binary-option]" };
      if (selectors[choice.kind] && click(selectors[choice.kind])) return "choice-button";
      return `unhandled:${choice.kind}`;
    });
  }

  async function syncPage(page, state) {
    await page.waitForFunction((sequences) => Math.max(0, ...(latestState?.recentLog || []).map((e) => Number(e.sequence || 0))) >= sequences[myPlayerId], state.viewSequences);
  }

  for (const item of catalog.actions.filter((item) => !focus || focus.includes(item.cardId))) {
    const entry = { ...item, status: "fail", driver: "production-UI-handlers-and-DOM-events", trace: [] };
    try {
      const fixture = await load("action", item);
      const page = pages[fixture.actor];
      const start = frames[fixture.actor].length;
      const errorStart = errors[fixture.actor].length;
      const errorCounts = Object.fromEntries(Object.entries(errors).map(([id, values]) => [id, values.length]));
      const frameStarts = Object.fromEntries(Object.entries(frames).map(([id, values]) => [id, values.length]));
      const settleFrames = async () => {
        await new Promise((resolve) => setTimeout(resolve, 15));
        const types = ["declare_rules_action", "pass_priority", "resolve_rules_choice", "play_first_manifestation_trap", "spend_counter_essence"];
        const count = Object.entries(frames).reduce((total, [id, values]) => total + values.slice(frameStarts[id]).filter((m) => types.includes(m.type)).length, 0);
        await control("settle", { count });
        return control("snapshot");
      };
      const begun = await page.evaluate((f) => {
        const source = { ...f.source, handIndex: latestState.players[myPlayerId].zones.hand.cards.indexOf(f.source.cardId) };
        if (f.ability.result?.kind === "first_manifestation_trap") {
          const action = rulesActionContextItem({ ...source, zone: "hand" });
          if (!action || action.debug) return false;
          action.onSelect(); return true;
        }
        if (source.zone === "battlefield") return beginRulesBoardActivatedAction(latestState.battlefield.find((i) => i.id === source.itemId), f.ability.id);
        if (f.ability.action === "play_card" && cardsById.get(source.cardId).type === "manifestation") {
          requestCardPlacement({ type: "place_card", ownerId: myPlayerId, fromZone: source.zone, cardId: source.cardId, faceUp: true, x: 350, y: 550 }, source);
          return true;
        }
        if (f.ability.action === "play_card") return beginRulesBoardAction(source);
        return beginRulesHandActivatedAction(source.cardId, source.handIndex, source.zone, source.containerId);
      }, fixture);
      assert.equal(begun, true, "production UI did not offer/start the action");
      for (let step = 0; step < 24; step++) {
        if (frames[fixture.actor].slice(start).some((m) => ["declare_rules_action", "play_first_manifestation_trap", "spend_counter_essence"].includes(m.type))) break;
        const driven = await page.evaluate((expected) => {
          const flow = pendingRulesBoardFlow;
          if (!flow) {
            const player = document.querySelector("[data-rules-player-target]");
            if (player) { player.click(); return "placement-player"; }
            return "no-flow";
          }
          if (flow.stage === "committing") return "committing";
          if (flow.stage === "extra_essence") { document.querySelector("#rulesExtraEssenceConfirm").click(); return "extra-confirm"; }
          if (flow.stage === "cost_card") {
            const cost = rulesBoardHandCostCandidates(flow).find((c) => c.cardId === expected.costCardId);
            if (!cost) return "cost-unavailable";
            resolveRulesBoardCardDrop({ fromOwnerId: myPlayerId, fromZone: "hand", handIndex: cost.index }, document.querySelector("#rulesFloatingCard"));
            return "production-drop-handler";
          }
          if (flow.stage !== "target") return `unhandled:${flow.stage}`;
          const key = (t) => t.kind === "card" ? `card:${t.itemId || t.id}` : t.kind === "zone_card" ? `${t.containerId}:${t.zone}:${t.cardId}` : t.kind === "player" ? `player:${t.playerId}` : `stack:${t.actionId}`;
          const wanted = expected.targets[(flow.selectedTargets || []).length];
          const candidate = flow.draft.structuredTargets.find((t) => wanted && key(t) === key(wanted) && (!flow.draft.targetRules.groups || t.targetGroupIndex === (flow.selectedTargets || []).length));
          if (candidate) {
            const zoneButton = [...document.querySelectorAll("[data-zone-pick]")].find((e) => e.dataset.zonePick === candidate.key);
            const playerButton = [...document.querySelectorAll("[data-player-target]")].find((e) => e.dataset.playerTarget === candidate.key);
            if (zoneButton || playerButton) { (zoneButton || playerButton).click(); return "popup-target"; }
            const element = rulesTargetElement(candidate);
            if (element?.classList.contains("rules-valid-target")) { element.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, cancelable: true, pointerId: 1 })); return "DOM-pointer-target"; }
          }
          const confirm = document.querySelector("[data-zone-pick-confirm]:not(:disabled), #rulesConfirmTargets:not(:disabled)");
          if (confirm) { confirm.click(); return "confirm-targets"; }
          return "target-unavailable";
        }, fixture);
        entry.trace.push(driven);
        if (["no-flow", "cost-unavailable", "target-unavailable"].includes(driven) || driven.startsWith("unhandled:")) break;
        await page.waitForTimeout(driven === "committing" ? 200 : 10);
      }
      const sent = frames[fixture.actor].slice(start).find((m) => ["declare_rules_action", "play_first_manifestation_trap", "spend_counter_essence"].includes(m.type));
      assert.ok(sent, `No action sent: ${entry.trace.join(", ")}`);
      entry.sent = sent;
      // Ordered stdin round trip occurs after the browser frame has arrived.
      let state = await settleFrames();
      assert.deepEqual(errors[fixture.actor].slice(errorStart), [], "server rejected UI action");
      const declared = state.log.some((e) => e.type === "rules_action_declared" && e.details?.ability?.id === item.abilityId)
        || state.rules.actionStack.some((a) => a.ability?.id === item.abilityId)
        || sent.type !== "declare_rules_action";
      assert.ok(declared, "No matching server declaration");
      const actionIds = state.rules.actionStack.filter((a) => a.ability?.id === item.abilityId).map((a) => a.id);
      for (let pass = 0; pass < 8 && actionIds.some((id) => state.rules.actionStack.some((a) => a.id === id)) && !state.rules.pendingChoice; pass++) {
        const actor = state.rules.priorityPlayerId;
        await syncPage(pages[actor], state);
        entry.trace.push(`pass:${actor}:${state.rules.actionStack.length}`);
        await pages[actor].evaluate(() => document.querySelector("#passPriorityBtn").click());
        state = await settleFrames();
      }
      assert.deepEqual(errors[fixture.actor].slice(errorStart), [], "server rejected progression");
      for (let step = 0; step < 48 && (state.rules.pendingChoice || state.rules.actionStack.length); step++) {
        if (state.rules.pendingChoice) {
          const answers = () => Object.values(frames).flat().filter((m) => m.type === "resolve_rules_choice").length;
          const starts = answers();
          const answer = await answerChoice(state.rules.pendingChoice);
          entry.trace.push(answer);
          assert.ok(!answer.startsWith("unhandled:"), answer);
          await pages[state.rules.pendingChoice.playerId].waitForTimeout(10);
          assert.equal(answers(), starts + 1, "Choice UI sent no answer or more than one answer");
        } else {
          const actor = state.rules.priorityPlayerId;
          await syncPage(pages[actor], state);
          entry.trace.push(`pass:${actor}:${state.rules.actionStack.length}`);
          await pages[actor].evaluate(() => document.querySelector("#passPriorityBtn").click());
        }
        state = await settleFrames();
        for (const id of Object.keys(errors)) assert.deepEqual(errors[id].slice(errorCounts[id]), [], "server rejected choice/progression");
      }
      assert.ok(!state.rules.pendingChoice && !state.rules.actionStack.length, "Choice/Stack did not finish within 48 UI steps");
      entry.status = "pass";
      entry.resolution = "completed-no-pending-choice";
      for (const page of Object.values(pages)) await page.waitForFunction(() => !latestState.rulesEngine.actionStack.length && !latestState.rulesEngine.pendingChoice);
    } catch (error) {
      entry.error = error.message;
      entry.diagnostics = {};
      for (const [id, page] of Object.entries(pages)) entry.diagnostics[id] = await page.evaluate(() => ({ priority: latestState.rulesEngine.priorityPlayerId,
        choice: latestState.rulesEngine.pendingChoice, stack: latestState.rulesEngine.actionStack.map((a) => a.id), busy: rulesAnimationsBusyFor(), flow: pendingRulesBoardFlow?.mode }));
      entry.diagnostics.handled = (await control("snapshot")).handled;
    }
    result.actions.push(entry);
    fs.writeFileSync(path.join(out, "browser-progress.json"), JSON.stringify({ completed: result.actions.length,
      last: entry, failures: result.actions.filter((a) => a.status === "fail").map((a) => ({ cardId: a.cardId, error: a.error })) }, null, 2));
    if (result.actions.length % 25 === 0) console.log(JSON.stringify({ actions: result.actions.length, failed: result.actions.filter((a) => a.status === "fail").length }));
  }

  // Physical pointer + reconnect + private choice + duplicate answer on both sizes.
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 844, height: 390 }]) {
    const journey = { name: "Suspend / private choice / reconnect / duplicate", viewport, status: "fail" };
    try {
      for (const page of Object.values(pages)) await page.setViewportSize(viewport);
      await load("choice");
      const before = await control("snapshot");
      const choiceId = before.rules.pendingChoice.id;
      assert.equal(await pages.p1.evaluate(() => latestState.rulesEngine.pendingChoice.cardIds), undefined);
      assert.equal(before.spectator.rulesEngine.pendingChoice.cardIds, undefined);
      await pages.p2.reload();
      await pages.p2.waitForFunction(() => cardsById.size === 450 && document.querySelector("#passPriorityBtn").onclick);
      await pages.p2.evaluate((code) => connectAndJoin({ code, name: "P2" }), address.code);
      await pages.p2.waitForFunction((id) => latestState?.rulesEngine?.pendingChoice?.id === id, choiceId);
      const start = frames.p2.length;
      await pages.p2.locator('[data-rules-suspend-card="0"]').click();
      await pages.p2.waitForFunction(() => !latestState.rulesEngine.pendingChoice && latestState.rulesEngine.suspendedCards.length === 1);
      const answer = frames.p2.slice(start).find((m) => m.type === "resolve_rules_choice");
      assert.ok(answer);
      const after = await control("snapshot");
      assert.equal(after.rules.suspendedCards.length, 1);
      // Replay through the actual socket to verify server-side duplicate safety.
      const count = errors.p2.length;
      await pages.p2.evaluate((payload) => send(payload), answer);
      await pages.p2.waitForTimeout(80);
      assert.equal(errors.p2.length, count + 1);
      const replay = await control("snapshot");
      assert.deepEqual(replay.rules, after.rules);
      assert.deepEqual(replay.players, after.players);
      assert.deepEqual(replay.battlefield, after.battlefield);
      await pages.p2.screenshot({ path: path.join(out, `suspend-${viewport.width}.png`) });
      journey.status = "pass";
    } catch (error) { journey.error = error.message; }
    result.journeys.push(journey);
  }
} catch (error) { result.errors.push({ message: error.stack }); }
finally {
  if (browser) await browser.close();
  server.kill();
  result.summary = { cards: result.rendering.length, actions: result.actions.length, journeys: result.journeys.length,
    failed: [...result.rendering, ...result.actions, ...result.journeys].filter((r) => r.status === "fail").length + result.errors.length,
    unresolvedChoiceScenarios: result.actions.filter((a) => a.resolution?.startsWith("needs-")).length };
  result.scope = debugRun ? "focused-debug-run" : "full-catalog";
  fs.writeFileSync(path.join(out, debugRun ? "browser-debug.json" : "browser.json"), JSON.stringify(result, null, 2) + "\n");
  console.log(JSON.stringify(result.summary));
  for (const entry of [...result.actions, ...result.journeys].filter((r) => r.status === "fail")) console.log(JSON.stringify(entry));
  if (result.errors.length) console.log(JSON.stringify(result.errors));
  process.exitCode = result.summary.failed || (!debugRun && (result.rendering.length !== 450 || result.actions.length !== expectedActionCount)) || result.journeys.length !== 2 ? 1 : 0;
}
