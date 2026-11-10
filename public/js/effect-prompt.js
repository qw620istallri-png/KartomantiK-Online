// Effect prompt: the one bar every card-effect choice answers in.
// It sits above the hand (never over it), sized to what is asked, with the
// asking card on the left, the question in the middle and the buttons on the
// right. Four families use it for now:
//   - questions (yes / no): the two answers are the bar's buttons and act at once;
//   - options (temperament, number, penalty…): tiles open above the bar, the
//     picked tile lights up and the bar's Validate button sends it;
//   - cards (deck search, revealed hand, Limbo, power split…): the cards open
//     above the bar, a click picks (or unpicks) one, Validate n/N sends them.
//     When every card is on the table, nothing opens: the cards glow on the
//     table and a click there picks them;
//   - hand (discard, Wills from hand, too many cards…): nothing opens either,
//     a click on a hand card picks it (it rises, greys out, "Chosen"); dragging
//     it onto the bar still works.
// The choice screens keep building their own buttons (choices.js); this file
// only re-dresses #rulesChoicePanel afterwards, so the answers sent to the
// server do not change.

const EFFECT_PROMPT_QUESTION_KINDS = new Set([
  "optional_trigger", "optional_stack_action", "binary_choice", "optional_discard_draw", "effect_memory_return",
]);

const EFFECT_PROMPT_OPTION_KINDS = new Set([
  "temperament_choice", "token_count", "score_delta_choice", "points_or_weaken_first",
  "points_or_hand_limit", "clemency_choice", "skip_confrontation_payment",
]);

// typed or composed answers: a card name, a guess (type, temperament, value)
const EFFECT_PROMPT_INPUT_KINDS = new Set(["declare_card_name", "guess_top_card"]);
const EFFECT_PROMPT_NAME_RESULTS = 12;

const EFFECT_PROMPT_CARD_KINDS = new Set([
  "chain_manifestation", "suspend_hand_will", "persist_first_manifestation", "pick_own_item",
  "pick_distribution_extra", "reveal_hand_discard", "random_target_effect", "draw_replacement",
  "power_loss_distribution",
]);

// cards dragged into piles or into an order: the piles open above the bar
const EFFECT_PROMPT_PILE_KINDS = new Set([
  "deck_reorder", "support_return_order", "simultaneous_stack_order", "replacement_order",
]);

// the buttons each choice screen builds, in the order they are offered
const EFFECT_PROMPT_OPTION_SELECTOR = [
  "[data-rules-optional-trigger]", "[data-rules-binary-option]", "[data-rules-optional-discard]",
  "[data-rules-memory-option]", "[data-rules-temperament-option]", "[data-rules-token-count]",
  "[data-rules-score-option]", "[data-rules-weaken-option]", "[data-rules-hand-limit-option]",
  "[data-rules-clemency-option]", "[data-rules-skip-option]",
].join(", ");

const EFFECT_PROMPT_CARD_SELECTOR = [
  "[data-rules-chain-card]", "[data-rules-suspend-card]", "[data-rules-persist-item]", "[data-rules-pick-item]",
  "[data-rules-distribute-item]", "[data-rules-reveal-index]", "[data-rules-random-target]",
  "[data-rules-private-card]", "[data-rules-discard-index]", "[data-rules-power-target]",
].join(", ");

// from this many cards the scene shows rows, a search and filters
const EFFECT_PROMPT_MANY = 10;

// screens that already count a multiple pick and confirm it themselves
const EFFECT_PROMPT_INNER_CONFIRM = "#rulesPrivateCardsConfirm, #rulesDiscardConfirm, #rulesPowerConfirm";

// answers that turn the effect down: shown as the quiet (secondary) button
const EFFECT_PROMPT_DECLINE_VALUES = new Set(["decline", "no"]);

let effectPromptPick = { choiceId: null, value: null };
let effectPromptFilter = { choiceId: null, text: "", type: "", temperament: "" };

function effectPromptMode(choice) {
  if (!choice || !document.querySelector("#gameScreen.ui-beta")) return null;
  if (choice.kind === "binary_choice" && choice.purpose === "amphora_pick") return "options";
  if (EFFECT_PROMPT_QUESTION_KINDS.has(choice.kind)) return "question";
  if (EFFECT_PROMPT_OPTION_KINDS.has(choice.kind)) return "options";
  if (choice.kind === "discard_from_hand") return Array.isArray(choice.candidateCardIds) ? "cards" : "hand";
  if (choice.kind === "hand_overflow") return "hand";
  if (EFFECT_PROMPT_CARD_KINDS.has(choice.kind)) return "cards";
  if (EFFECT_PROMPT_PILE_KINDS.has(choice.kind)) return "piles";
  if (EFFECT_PROMPT_INPUT_KINDS.has(choice.kind)) return "input";
  return null;
}

// true while the bar holds the answer back until Validate
function effectPromptValidates() {
  return Boolean(document.querySelector("#gameScreen.ui-beta") && $("#rulesChoicePanel")?.classList.contains("effect-prompt"));
}

function effectPromptTag(choice) {
  if (choice.kind === "optional_trigger") return t("epTagTriggered");
  if (choice.kind === "skip_confrontation_payment") return t("epTagCost");
  return t("epTagEffect");
}

function effectPromptIsCardName(text) {
  const value = String(text || "").trim().toLowerCase();
  if (!value) return false;
  // card names in every language: a title may stay in English while the table is in French
  for (const card of cardsById.values()) {
    const names = [card.name, ...Object.values(card.translations || {}).map((entry) => entry?.name)];
    if (names.some((name) => String(name || "").trim().toLowerCase() === value)) return true;
  }
  return false;
}

function effectPromptQuestion(choice, heading) {
  if (!effectPromptIsCardName(heading)) return null;
  const key = choice.kind === "clemency_choice" ? "epQuestion_clemency" : `epQuestion_${choice.purpose || choice.kind}`;
  const params = { card: cardName(choice.sourceCardId), target: cardName(choice.relatedCardId) };
  return t(key) !== key ? rulesText(key, params) : t("epQuestionGeneric");
}

function effectPromptOptionValue(button) {
  const key = Object.keys(button.dataset).find((name) => name.startsWith("rules"));
  return key ? button.dataset[key] : "";
}

function effectPromptOptionLabel(button) {
  // a face-down card has no name to repeat in the Validate button
  if (button.classList.contains("rules-amphora-back")) return "";
  return (button.querySelector("strong")?.textContent || button.getAttribute("title")
    || button.querySelector("span")?.textContent || button.textContent || "").trim();
}

// the table card a card button stands for, when the table takes the click for it
// (the same buttons ui-beta.js answers on the board; a power split keeps its scene)
function effectPromptBoardCard(button) {
  const itemId = button.dataset.rulesPickItem || button.dataset.rulesPersistItem || button.dataset.rulesDistributeItem
    || button.dataset.rulesRandomTarget;
  if (!itemId) return null;
  return [...document.querySelectorAll("#battlefield .bf-card[data-item-id]")].find((card) => card.dataset.itemId === itemId) || null;
}

// Above the hand, centred on the field.
function effectPromptAnchor() {
  const field = document.querySelector("#battlefield")?.getBoundingClientRect();
  const handTops = [...document.querySelectorAll("#handArea [data-hand-card]")]
    .map((card) => card.getBoundingClientRect())
    .filter((rect) => rect.width > 0 && rect.height > 0 && rect.top < window.innerHeight)
    .map((rect) => rect.top);
  const handTop = handTops.length ? Math.min(...handTops) : window.innerHeight - 24;
  return {
    bottom: Math.max(12, Math.round(window.innerHeight - handTop + 14)),
    x: Math.round(field && field.width ? field.left + field.width / 2 : window.innerWidth / 2),
    width: Math.round(field?.width || window.innerWidth),
  };
}

function placeEffectPrompt() {
  const anchor = effectPromptAnchor();
  [$("#rulesChoicePanel.effect-prompt"), document.querySelector("#rulesOpponentDeciding.ep-opponent")].forEach((node) => {
    if (!node) return;
    node.style.setProperty("--ep-bottom", `${anchor.bottom}px`);
    node.style.setProperty("--ep-x", `${anchor.x}px`);
    node.style.setProperty("--ep-field-w", `${anchor.width}px`);
  });
  fitEffectPromptStage();
  // the bar settles (fonts, its rise animation) a frame later: fit again then
  requestAnimationFrame(() => requestAnimationFrame(fitEffectPromptStage));
}

// the scene above the bar never runs under the game header or off the screen
function fitEffectPromptStage() {
  const box = document.querySelector("#rulesChoicePanel.effect-prompt .box");
  if (!box) return;
  const panel = $("#rulesChoicePanel");
  const header = document.querySelector("#gameScreen .game-header")?.getBoundingClientRect();
  let ceiling = Math.max(0, header && header.height ? header.bottom : 0);
  // piles to sort may rise up to the Confrontation Zone's totals
  // (a short screen keeps all its height for them)
  const roomy = innerHeight > 480 && !document.querySelector("#gameScreen.ub-phone");
  const totals = roomy && panel.classList.contains("ep-piles") ? document.querySelector("#ubTotals")?.getBoundingClientRect() : null;
  if (totals && totals.height) ceiling = Math.max(ceiling, totals.bottom);
  const top = box.getBoundingClientRect().top - (parseFloat(getComputedStyle(box).translate?.split(" ")[1]) || 0);
  const stageMax = Math.max(90, Math.round(top - ceiling - (totals ? 18 : 26)));
  panel.style.setProperty("--ep-stage-max", `${stageMax}px`);
  panel.style.setProperty("--ep-bar-h", `${Math.round(box.getBoundingClientRect().height)}px`);
  // the revealed deck cards as large as that room allows: a row of cards to sort, a row of lanes
  const group = panel.classList.contains("ep-piles") ? panel.querySelector(".rules-reorder-group") : null;
  if (group) {
    const count = Math.max(1, ...[...panel.querySelectorAll(".rules-reorder-group")].map((entry) => entry.querySelectorAll(".rules-reorder-card").length));
    const groups = panel.querySelectorAll(".rules-reorder-group").length;
    // the cards to sort get the room; the lanes take smaller copies (0.6)
    const byHeight = ((stageMax - 32) / groups - 64) / 1.6 * 5 / 7;
    const byWidth = (Math.min(1180, (parseFloat(panel.style.getPropertyValue("--ep-field-w")) || innerWidth) - 24) - 40 - (count - 1) * 12) / count;
    panel.style.setProperty("--ep-pile-w", `${Math.round(Math.max(56, Math.min(200, byHeight, byWidth)))}px`);
  }
}

function clearEffectPrompt(panel = $("#rulesChoicePanel")) {
  panel.classList.remove("effect-prompt", "ep-question", "ep-options", "ep-cards", "ep-hand", "ep-piles", "ep-input", "ep-peek", "ep-on-table", "ep-many");
  panel.querySelector(".ep-actions")?.remove();
  panel.querySelector(".ep-tag")?.remove();
  panel.querySelector(".ep-hint")?.remove();
  // piles take the scene out of the bar's box: it goes back for every other screen
  const home = panel.querySelector(".box");
  const scene = $("#rulesChoiceOptions");
  if (home && scene && scene.parentElement !== home) home.appendChild(scene);
  $("#rulesChoiceOptions")?.classList.remove("ep-tiles", "ep-has-pick", "ep-card-row", "ep-filter-none");
  document.querySelectorAll(".ep-board-picked").forEach((card) => card.classList.remove("ep-board-picked"));
}

function effectPromptButton(className, text) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  if (text) button.textContent = text;
  return button;
}

function effectPromptPeekButton(panel) {
  const peek = effectPromptButton("ep-peek-btn");
  peek.title = t("epPeekTable");
  peek.setAttribute("aria-label", peek.title);
  peek.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>';
  const peekOn = () => panel.classList.add("ep-peek");
  const peekOff = () => panel.classList.remove("ep-peek");
  peek.addEventListener("pointerdown", peekOn);
  ["pointerup", "pointerleave", "pointercancel", "blur"].forEach((type) => peek.addEventListener(type, peekOff));
  return peek;
}

function effectPromptHint(panel, text) {
  if (!text) return;
  const hint = document.createElement("span");
  hint.className = "ep-hint";
  hint.textContent = text;
  $("#rulesChoiceText").appendChild(hint);
}

// Called after choices.js has built the screen for the current choice.
function applyEffectPrompt() {
  const panel = $("#rulesChoicePanel");
  clearEffectPrompt(panel);
  const choice = latestState?.rulesEngine?.pendingChoice;
  const mode = panel.classList.contains("hidden") || pendingTriggeredPlacement ? null : effectPromptMode(choice);
  if (!mode) return false;
  if (effectPromptPick.choiceId !== choice.id) effectPromptPick = { choiceId: choice.id, value: null };
  panel.classList.remove("cards-screen", "effect-screen", "temperament-screen", "hand-drop", "chain-screen");
  panel.classList.add("effect-prompt", `ep-${mode}`);
  $("#rulesChoiceCloseBtn").classList.add("hidden");

  // some screens are titled with a card's name: the bar asks a question instead
  const heading = $("#rulesChoiceHeading");
  const question = effectPromptQuestion(choice, heading.textContent);
  if (question) heading.textContent = question;

  const head = panel.querySelector(".rules-choice-head");
  const tag = document.createElement("span");
  tag.className = "ep-tag";
  tag.textContent = effectPromptTag(choice);
  head.insertBefore(tag, head.firstChild);

  const options = $("#rulesChoiceOptions");
  const actions = document.createElement("div");
  actions.className = "ep-actions";
  panel.querySelector(".box").appendChild(actions);

  if (mode === "question") applyEffectPromptQuestion(options, actions);
  else if (mode === "options") applyEffectPromptOptions(panel, choice, options, actions);
  else if (mode === "cards") applyEffectPromptCards(panel, choice, options, actions);
  else if (mode === "piles") applyEffectPromptPiles(panel, options, actions);
  else if (mode === "input") applyEffectPromptInput(panel, choice, options, actions);
  else applyEffectPromptHand(panel, choice, actions);
  placeEffectPrompt();
  return true;
}

function applyEffectPromptQuestion(options, actions) {
  const buttons = [...options.querySelectorAll(EFFECT_PROMPT_OPTION_SELECTOR)];
  // the answers act at once, as before: they just move into the bar
  // the answer that uses the effect is the gold button, on the right
  const primary = buttons.find((button) => !EFFECT_PROMPT_DECLINE_VALUES.has(effectPromptOptionValue(button))) || buttons[0];
  // the DOM keeps the offered order (yes before no); CSS puts the gold one on the right
  buttons.forEach((button) => {
    button.classList.add(button === primary ? "ep-btn-primary" : "ep-btn-secondary");
    actions.appendChild(button);
  });
}

// One pick among buttons that each used to send at once: a click picks,
// Validate sends the pick through the button's own handler.
function wireEffectPromptSinglePick(choice, options, buttons, confirm, onPaint) {
  const paint = () => {
    const picked = buttons.find((button) => effectPromptOptionValue(button) === effectPromptPick.value) || null;
    buttons.forEach((button) => button.setAttribute("aria-pressed", String(button === picked)));
    options.classList.toggle("ep-has-pick", Boolean(picked));
    const waiting = rulesChoiceAnswerPending?.choiceId === choice.id;
    confirm.disabled = !picked || waiting;
    const label = picked ? effectPromptOptionLabel(picked) : "";
    confirm.textContent = label ? rulesText("epValidateWith", { option: label }) : t("epValidate");
    onPaint?.(buttons, picked);
  };
  buttons.forEach((button, index) => {
    const send = button.onclick;
    button.dataset.epKey = String(index + 1);
    button.onclick = () => {
      if (rulesChoiceAnswerPending?.choiceId === choice.id) return;
      const value = effectPromptOptionValue(button);
      // a second click on the picked card puts it back
      effectPromptPick.value = effectPromptPick.value === value && button.classList.contains("ep-card") ? null : value;
      paint();
    };
    button.epSend = send;
  });
  confirm.onclick = () => {
    const picked = buttons.find((button) => effectPromptOptionValue(button) === effectPromptPick.value);
    if (!picked || typeof picked.epSend !== "function") return;
    confirm.disabled = true;
    picked.epSend.call(picked);
    lockRulesChoiceAnswer();
    confirm.disabled = true;
  };
  paint();
}

function applyEffectPromptOptions(panel, choice, options, actions) {
  const buttons = [...options.querySelectorAll(EFFECT_PROMPT_OPTION_SELECTOR)];
  options.classList.add("ep-tiles");
  buttons.forEach((button) => button.classList.add("ep-tile"));
  const confirm = effectPromptButton("primary ep-btn-primary");
  confirm.id = "rulesChoiceConfirm";
  actions.append(effectPromptPeekButton(panel), confirm);
  wireEffectPromptSinglePick(choice, options, buttons, confirm);
}

function applyEffectPromptCards(panel, choice, options, actions) {
  const cards = [...options.querySelectorAll(EFFECT_PROMPT_CARD_SELECTOR)];
  const inner = options.querySelector(EFFECT_PROMPT_INNER_CONFIRM);
  options.classList.add("ep-card-row");
  cards.forEach((card) => card.classList.add("ep-card"));
  // "Pass" and other ways out become the quiet button of the bar
  const decline = options.querySelector("[data-rules-chain-decline]");
  if (decline) {
    decline.classList.remove("rules-choice-destination");
    decline.classList.add("ep-btn-secondary");
    actions.appendChild(decline);
  }
  const confirm = effectPromptButton("primary ep-btn-primary");
  confirm.id = "rulesChoiceConfirm";
  actions.append(effectPromptPeekButton(panel), confirm);
  // every card is on the table: no scene, the table cards glow and take the click
  const onTable = cards.length > 0 && cards.every((card) => effectPromptBoardCard(card));
  // a big place (a whole deck, full Limbo): rows, a name search, type and temperament filters
  const many = !onTable && cards.length >= EFFECT_PROMPT_MANY;
  const strip = many ? effectPromptPickedStrip(actions, confirm) : null;
  const markTable = () => {
    if (strip) strip.paint(cards);
    if (!onTable) return;
    cards.forEach((card) => effectPromptBoardCard(card)?.classList.toggle("ep-board-picked", card.getAttribute("aria-pressed") === "true"));
  };
  panel.classList.toggle("ep-on-table", onTable);
  panel.classList.toggle("ep-many", many);
  if (onTable) effectPromptHint(panel, t("epBoardHint"));
  if (many) effectPromptFilterBar(choice, options, cards);

  if (!inner) {
    wireEffectPromptSinglePick(choice, options, cards, confirm, markTable);
    return;
  }
  // several cards: the screen counts them, the bar shows the count and validates
  inner.classList.add("ep-inner-confirm");
  const total = Number(inner.dataset.epTotal || choice.count || 1);
  const paint = () => {
    const count = inner.dataset.epCount !== undefined
      ? Number(inner.dataset.epCount)
      : cards.filter((card) => card.getAttribute("aria-pressed") === "true").length;
    const waiting = rulesChoiceAnswerPending?.choiceId === choice.id;
    confirm.disabled = inner.disabled || waiting;
    confirm.textContent = choice.upTo
      ? (count ? rulesText("epValidateCount", { count }) : t("epTakeNone"))
      : rulesText("epValidateOf", { count, total });
    options.classList.toggle("ep-has-pick", count > 0);
    markTable();
  };
  cards.forEach((card) => {
    const pick = card.onclick;
    card.onclick = (event) => {
      pick?.call(card, event);
      // a screen that redraws itself re-dresses its new buttons; this one is gone
      if (card.isConnected) paint();
    };
  });
  confirm.onclick = () => {
    if (confirm.disabled) return;
    confirm.disabled = true;
    inner.disabled = false;
    inner.click();
    lockRulesChoiceAnswer();
  };
  paint();
}

// Typed answers. A card name: a search field above the bar, the matching cards
// as pictures under it (click one), Validate names the card. A guess: the chip
// rows above the bar, Validate repeats the guess. The screen's own button stays
// hidden and the bar clicks it.
function applyEffectPromptInput(panel, choice, options, actions) {
  const confirm = effectPromptButton("primary ep-btn-primary");
  confirm.id = "rulesChoiceConfirm";
  actions.append(effectPromptPeekButton(panel), confirm);
  const waiting = () => rulesChoiceAnswerPending?.choiceId === choice.id;
  if (choice.kind === "guess_top_card") {
    const inner = options.querySelector("#rulesGuessConfirm");
    inner?.classList.add("ep-inner-confirm");
    const paint = () => {
      const picked = [...options.querySelectorAll(".rules-chip-group")].map((group) => {
        const chip = group.querySelector('.rules-chip[aria-pressed="true"]');
        return chip ? chip.textContent.trim() : "";
      }).filter(Boolean);
      confirm.textContent = picked.length ? rulesText("epValidateWith", { option: picked.join(" · ") }) : t("epValidate");
      confirm.disabled = !inner || inner.disabled || waiting();
    };
    options.querySelectorAll(".rules-chip").forEach((chip) => {
      const pick = chip.onclick;
      chip.onclick = (event) => { pick?.call(chip, event); paint(); };
    });
    confirm.onclick = () => { if (inner && !inner.disabled) { inner.click(); confirm.disabled = true; } };
    paint();
    return;
  }
  // declare_card_name
  const input = options.querySelector("#rulesDeclareNameInput");
  const inner = options.querySelector("#rulesDeclareNameConfirm");
  if (!input || !inner) return;
  inner.classList.add("ep-inner-confirm");
  input.removeAttribute("list");
  input.type = "search";
  input.classList.add("ep-search");
  input.placeholder = t("epSearchPlaceholder");
  input.setAttribute("aria-label", t("rulesDeclareNameLabel"));
  input.spellcheck = false;
  const label = input.closest("label");
  const field = document.createElement("div");
  field.className = "ep-filter";
  field.appendChild(input);
  label?.replaceWith(field);
  options.querySelector("#rulesDeclareNameList")?.remove();
  const results = document.createElement("div");
  results.className = "ep-name-results";
  options.appendChild(results);
  // one entry per name in this language, every language's name finds it
  const entries = [];
  const seen = new Set();
  for (const card of cardsById.values()) {
    const name = cardName(card.id);
    if (!name || seen.has(name.toLowerCase())) continue;
    seen.add(name.toLowerCase());
    const names = [name, card.name, ...Object.values(card.translations || {}).map((entry) => entry?.name)].filter(Boolean);
    entries.push({ name, cardId: card.id, folded: [...new Set(names.map(effectPromptFold))] });
  }
  const paint = () => {
    const declared = input.value.trim();
    confirm.disabled = inner.disabled || waiting();
    confirm.textContent = !inner.disabled && declared ? rulesText("epValidateWith", { option: declared }) : t("epValidate");
    results.querySelectorAll(".ep-card").forEach((card) => card.setAttribute("aria-pressed", String(card.dataset.epName.toLowerCase() === declared.toLowerCase())));
  };
  const search = () => {
    const text = effectPromptFold(input.value);
    if (text.length < 2) {
      results.innerHTML = `<p class="ep-name-hint">${esc(t("epNameHint"))}</p>`;
    } else {
      const starts = [], contains = [];
      for (const entry of entries) {
        if (entry.folded.some((name) => name.startsWith(text))) starts.push(entry);
        else if (entry.folded.some((name) => name.includes(text))) contains.push(entry);
      }
      const found = [...starts, ...contains].slice(0, EFFECT_PROMPT_NAME_RESULTS);
      results.innerHTML = found.length ? found.map((entry) => `
        <button type="button" class="rules-choice-card ep-card" data-ep-card="${esc(entry.cardId)}" data-ep-name="${esc(entry.name)}" title="${esc(entry.name)}" aria-pressed="false">
          <img src="${esc(cardImage(entry.cardId))}" alt="${esc(entry.name)}" draggable="false"><span>${esc(entry.name)}</span>
        </button>`).join("") : `<p class="ep-name-hint">${esc(t("epSearchEmpty"))}</p>`;
      results.querySelectorAll(".ep-card").forEach((card) => {
        card.onclick = () => {
          if (waiting()) return;
          input.value = card.dataset.epName;
          input.dispatchEvent(new Event("input"));
        };
      });
    }
    paint();
    fitEffectPromptStage();
  };
  const own = input.oninput;
  input.oninput = (event) => { own?.call(input, event); search(); };
  input.onkeydown = (event) => {
    if (event.key === "Enter" && !confirm.disabled) { event.preventDefault(); confirm.click(); }
    if (event.key === "Escape") input.blur();
  };
  confirm.onclick = () => { if (!inner.disabled) { inner.click(); confirm.disabled = true; } };
  search();
  requestAnimationFrame(() => { if (!waiting()) input.focus({ preventScroll: true }); });
}

function effectPromptFold(text) {
  return String(text || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
}

// Search and filters above a big scene. Filtering only hides cards: a picked
// card stays picked (and stays in the bar) even when a filter hides it.
function effectPromptFilterBar(choice, options, cards) {
  if (effectPromptFilter.choiceId !== choice.id) effectPromptFilter = { choiceId: choice.id, text: "", type: "", temperament: "" };
  const cardOf = (button) => cardsById.get(button.dataset.epCard) || null;
  const count = (values) => [...new Set(values.filter(Boolean))];
  const types = count(cards.map((button) => cardOf(button)?.type));
  const temperaments = count(cards.flatMap((button) => cardOf(button)?.temperaments || []));
  const bar = document.createElement("div");
  bar.className = "ep-filter";
  const chips = (kind, values, label) => values.length > 1 ? `<div class="ep-chips" role="group">${values.map((value) => `
    <button type="button" class="ep-chip" data-ep-filter-${kind}="${esc(value)}" aria-pressed="false">${label(value)}</button>`).join("")}</div>` : "";
  bar.innerHTML = `<input type="search" class="ep-search" autocomplete="off" spellcheck="false" placeholder="${esc(t("epSearchPlaceholder"))}" aria-label="${esc(t("epSearchPlaceholder"))}">
    ${chips("type", types, (type) => esc(cardField(cards.map(cardOf).find((card) => card?.type === type), "typeLabel") || type))}
    ${chips("temperament", temperaments, (key) => `<img src="${esc(temperamentSymbol(key))}" alt="" title="${esc(t(`temperament${key[0].toUpperCase()}${key.slice(1)}`))}">`)}
    <span class="ep-filter-count"></span>`;
  options.insertBefore(bar, options.firstChild);
  const empty = document.createElement("p");
  empty.className = "ep-filter-empty";
  empty.textContent = t("epSearchEmpty");
  options.appendChild(empty);
  const input = bar.querySelector(".ep-search");
  input.value = effectPromptFilter.text;
  const apply = () => {
    const text = effectPromptFold(effectPromptFilter.text);
    let shown = 0;
    cards.forEach((button) => {
      const card = cardOf(button);
      const names = card ? [cardName(card.id), card.name, ...Object.values(card.translations || {}).map((entry) => entry?.name)] : [button.textContent];
      const match = (!text || names.some((name) => effectPromptFold(name).includes(text)))
        && (!effectPromptFilter.type || card?.type === effectPromptFilter.type)
        && (!effectPromptFilter.temperament || (card?.temperaments || []).includes(effectPromptFilter.temperament));
      button.classList.toggle("ep-filtered", !match);
      if (match) shown += 1;
    });
    bar.querySelectorAll("[data-ep-filter-type]").forEach((chip) => chip.setAttribute("aria-pressed", String(chip.dataset.epFilterType === effectPromptFilter.type)));
    bar.querySelectorAll("[data-ep-filter-temperament]").forEach((chip) => chip.setAttribute("aria-pressed", String(chip.dataset.epFilterTemperament === effectPromptFilter.temperament)));
    bar.querySelector(".ep-filter-count").textContent = rulesText("epSearchCount", { shown, total: cards.length });
    options.classList.toggle("ep-filter-none", shown === 0);
  };
  input.addEventListener("input", () => { effectPromptFilter.text = input.value; apply(); });
  bar.querySelectorAll("[data-ep-filter-type]").forEach((chip) => chip.addEventListener("click", () => {
    effectPromptFilter.type = effectPromptFilter.type === chip.dataset.epFilterType ? "" : chip.dataset.epFilterType;
    apply();
  }));
  bar.querySelectorAll("[data-ep-filter-temperament]").forEach((chip) => chip.addEventListener("click", () => {
    effectPromptFilter.temperament = effectPromptFilter.temperament === chip.dataset.epFilterTemperament ? "" : chip.dataset.epFilterTemperament;
    apply();
  }));
  apply();
}

// The picked cards as small thumbnails beside Validate: a click puts one back.
function effectPromptPickedStrip(actions, confirm) {
  const strip = document.createElement("div");
  strip.className = "ep-picked";
  actions.insertBefore(strip, confirm);
  return {
    paint(cards) {
      const picked = cards.filter((card) => card.isConnected && card.getAttribute("aria-pressed") === "true");
      strip.innerHTML = picked.map((card, index) => `<button type="button" class="ep-picked-card" data-ep-unpick="${index}" title="${esc(rulesText("rulesUnselectCard", { card: cardName(card.dataset.epCard) }))}">
        <img src="${esc(card.querySelector("img")?.src || "")}" alt="${esc(cardName(card.dataset.epCard))}"></button>`).join("");
      strip.querySelectorAll("[data-ep-unpick]").forEach((thumb) => {
        thumb.onclick = () => picked[Number(thumb.dataset.epUnpick)]?.click();
      });
      // the thumbnails can make the bar taller
      fitEffectPromptStage();
    },
  };
}

// Piles and orders keep their own drag and drop (choices.js); their Confirm
// button moves into the bar as Validate, with its id and handler.
function applyEffectPromptPiles(panel, options, actions) {
  // out of the box: the old full-screen pile rules (".box:has(...)") no longer reach it
  panel.appendChild(options);
  const confirm = options.querySelector("#rulesDeckReorderConfirm, #rulesSupportOrderConfirm, #rulesSimultaneousOrderConfirm");
  actions.appendChild(effectPromptPeekButton(panel));
  if (!confirm) return;
  confirm.classList.add("ep-btn-primary");
  confirm.classList.remove("rules-reorder-confirm");
  confirm.textContent = t("epValidate");
  actions.appendChild(confirm);
  effectPromptHint(panel, t("epDragHint"));
}

function applyEffectPromptHand(panel, choice, actions) {
  const limit = Number(choice.count || 1);
  const picked = rulesHandDropSelected(choice).length;
  const inner = $("#rulesDiscardConfirm");
  const confirm = effectPromptButton("primary ep-btn-primary");
  confirm.id = "rulesChoiceConfirm";
  actions.appendChild(confirm);
  const waiting = rulesChoiceAnswerPending?.choiceId === choice.id;
  confirm.disabled = waiting || (choice.upTo ? picked > limit : picked !== limit);
  // "Place 2 Wills" / "Pass" read better than a count when the screen has its own wording
  confirm.textContent = inner && (choice.upTo || choice.destination === "attach_to_source")
    ? inner.textContent.trim()
    : rulesText("epValidateOf", { count: picked, total: limit });
  confirm.onclick = () => {
    if (confirm.disabled) return;
    confirm.disabled = true;
    sendHandDropSelection(choice);
    lockRulesChoiceAnswer();
  };
  effectPromptHint(panel, t("epHandHint"));
}

// A click on a hand card while the bar asks for hand cards picks it.
function effectPromptHandClick(handIndex) {
  if (!$("#rulesChoicePanel")?.classList.contains("ep-hand") || $("#rulesChoicePanel").classList.contains("hidden")) return false;
  return pickHandDropCard(handIndex, true);
}

// Hand cards: the picked ones rise and grey out ("Chosen"), those the effect cannot take fade.
function paintEffectPromptHand(choice) {
  const active = Boolean(choice) && $("#rulesChoicePanel")?.classList.contains("ep-hand");
  document.body.classList.toggle("ep-hand-choice", active);
  if (active) document.body.style.setProperty("--ep-chosen", JSON.stringify(t("epChosen")));
  const types = active && Array.isArray(choice.requireTypes) && choice.requireTypes.length ? choice.requireTypes
    : active && choice.requireManifestation ? ["manifestation"] : null;
  $$("[data-hand-card]").forEach((card) => {
    card.classList.toggle("ep-hand-ineligible", Boolean(types) && !types.includes(cardsById.get(card.dataset.handCard)?.type));
  });
  // a picked card rises: the bar stays above it
  if (active) placeEffectPrompt();
}

// The other player's view: the same bar, green, without buttons.
function renderEffectPromptOpponent(banner, choice) {
  const cardId = choice.sourceCardId || choice.targetCardId || choice.cardId;
  const image = cardId ? cardImage(cardId) : "";
  banner.classList.add("ep-opponent");
  requestAnimationFrame(placeEffectPrompt);
  banner.innerHTML = `${image ? `<span class="ep-opponent-source" data-ep-peek-card="${esc(cardId)}"><img src="${esc(image)}" alt="${esc(cardName(cardId))}"></span>` : ""}
    <span class="ep-opponent-copy"><small>${esc(t("epTagOpponent"))}</small><span>${esc(rulesText("rulesOpponentDeciding", {
      player: rulesPlayerName(choice.playerId),
      card: cardId ? cardName(cardId) : "",
    }))}</span></span>`;
}

// keyboard: 1-9 picks an option or a card, Enter validates, Escape declines, Space held shows the table
document.addEventListener("keydown", (event) => {
  const panel = $("#rulesChoicePanel");
  if (!panel?.classList.contains("effect-prompt") || panel.classList.contains("hidden")) return;
  if (event.target instanceof Element && event.target.closest("input, textarea, select, [contenteditable]")) return;
  const picking = panel.classList.contains("ep-options") || panel.classList.contains("ep-cards");
  if (picking && /^[1-9]$/.test(event.key)) {
    const cards = [...panel.querySelectorAll("#rulesChoiceOptions .ep-tile, #rulesChoiceOptions .ep-card:not(.ep-filtered)")];
    cards[Number(event.key) - 1]?.click();
    event.preventDefault();
  } else if (event.key === "Enter") {
    const confirm = $("#rulesChoiceConfirm");
    if (confirm && !confirm.disabled) { confirm.click(); event.preventDefault(); }
  } else if (event.key === "Escape") {
    const decline = panel.querySelector(".ep-actions .ep-btn-secondary");
    if (decline && !decline.disabled) { decline.click(); event.preventDefault(); }
  } else if (event.code === "Space" && picking) {
    panel.classList.add("ep-peek");
    event.preventDefault();
  }
});
document.addEventListener("keyup", (event) => {
  if (event.code === "Space") $("#rulesChoicePanel")?.classList.remove("ep-peek");
});
window.addEventListener("resize", () => placeEffectPrompt());
