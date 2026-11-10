// Effect bar (public/js/effect-prompt.js): questions and options asked by card
// effects answer in one bar above the hand.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "../public");
const mime = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json" };

(async () => {
  const server = http.createServer((request, response) => {
    const url = new URL(request.url, "http://localhost");
    const file = path.resolve(root, "." + (url.pathname === "/" ? "/index.html" : decodeURIComponent(url.pathname)));
    if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return response.writeHead(404).end();
    response.writeHead(200, { "Content-Type": mime[path.extname(file)] || "application/octet-stream" });
    fs.createReadStream(file).pipe(response);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "chrome", headless: true });
  try {
    for (const viewport of [{ width: 1440, height: 900 }, { width: 844, height: 390 }]) {
      const page = await browser.newPage({ viewport, locale: "fr-FR" });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.route("**/*", (route) => new URL(route.request().url()).hostname === "127.0.0.1" ? route.continue() : route.abort());
      await page.goto(`http://127.0.0.1:${server.address().port}/`);
      await page.waitForFunction(() => cardsById.size > 300 && typeof applyEffectPrompt === "function");
      await page.evaluate(() => {
        myPlayerId = "p1"; isObserver = false;
        const zones = () => Object.fromEntries(ZONES.map((key) => [key, { cards: [], owners: {} }]));
        const ids = [...cardsById.keys()];
        for (const card of cardsById.values()) card.image = "card-back.webp";
        latestState = { players: { p1: { id: "p1", name: "P1", seat: 0, score: 10, zones: zones() }, p2: { id: "p2", name: "P2", seat: 1, score: 10, zones: zones() } },
          battlefield: [], tokens: [], drawings: [],
          phaseTracker: { enabled: true, advanced: true, turn: 2, index: 5, passedPlayerIds: [] },
          rulesEngine: { enabled: true, priorityPlayerId: "p1", actionStack: [], firstManifestationComplete: true, readyPlayerIds: ["p1", "p2"], deckConfirmedPlayerIds: ["p1", "p2"] } };
        latestState.players.p1.zones.hand.cards = ids.slice(0, 5);
        window.__sent = []; send = (payload) => window.__sent.push(payload);
        document.querySelector("#joinScreen").classList.add("hidden");
        document.querySelector("#gameScreen").classList.remove("hidden");
        window.__setChoice = (choice) => {
          latestState.rulesEngine.pendingChoice = { playerId: "p1", sourceCardId: ids[0], ...choice };
          window.__sent = [];
          rulesChoiceAnswerPending = null;
          renderAll();
        };
        renderAll();
      });

      // a question: its two answers sit in the bar and act at once
      const question = await page.evaluate(() => {
        window.__setChoice({ id: "q1", kind: "optional_trigger", options: ["accept", "decline"] });
        const panel = document.querySelector("#rulesChoicePanel");
        const bar = panel.querySelector(".box").getBoundingClientRect();
        const handTop = Math.min(...[...document.querySelectorAll("#handArea [data-hand-card]")].map((card) => card.getBoundingClientRect().top));
        const actions = [...panel.querySelectorAll(".ep-actions [data-rules-optional-trigger]")];
        const result = {
          prompt: panel.classList.contains("effect-prompt") && panel.classList.contains("ep-question") && !panel.classList.contains("hidden"),
          answersInBar: actions.map((button) => button.dataset.rulesOptionalTrigger).join(","),
          primaryRight: panel.querySelector(".ep-btn-primary").getBoundingClientRect().left > panel.querySelector(".ep-btn-secondary").getBoundingClientRect().left,
          tag: panel.querySelector(".ep-tag")?.textContent.length > 2,
          fullTextHidden: !panel.querySelector(".rules-choice-effect") || getComputedStyle(panel.querySelector(".rules-choice-effect")).display === "none",
          aboveHand: bar.bottom <= handTop + 1,
          insideScreen: bar.left >= 0 && bar.right <= innerWidth && bar.top >= 0,
        };
        panel.querySelector('[data-rules-optional-trigger="accept"]').click();
        result.sent = window.__sent.map((entry) => entry.option).join(",");
        return result;
      });
      assert.deepEqual(question, {
        prompt: true, answersInBar: "accept,decline", primaryRight: true, tag: true, fullTextHidden: true,
        aboveHand: true, insideScreen: true, sent: "accept",
      }, `${viewport.width}: question bar`);

      // a screen titled with a card's name asks a real question in the bar
      const cardTitled = await page.evaluate(() => {
        const ids = [...cardsById.keys()];
        window.__setChoice({ id: "b1", kind: "binary_choice", purpose: "support_else_chain", relatedCardId: ids[1], options: ["yes", "no"],
          headingKey: "rulesSupportElseChainHeading", textKey: "rulesSupportElseChainText", yesKey: "rulesSupportElseChainYes", noKey: "rulesSupportElseChainNo" });
        const heading = document.querySelector("#rulesChoiceHeading").textContent;
        return heading !== t("rulesSupportElseChainHeading") && heading.includes(cardName(ids[1]));
      });
      assert.equal(cardTitled, true, `${viewport.width}: the bar asks a question, not a card name`);

      // options: picking lights the tile, Validate (or Enter) sends it
      const options = await page.evaluate(() => {
        window.__setChoice({ id: "o1", kind: "temperament_choice", options: ["choleric", "phlegmatic", "vitreous"] });
        const panel = document.querySelector("#rulesChoicePanel");
        const confirm = document.querySelector("#rulesChoiceConfirm");
        const before = { disabled: confirm.disabled, sent: window.__sent.length };
        document.querySelector('[data-rules-temperament-option="vitreous"]').click();
        const afterPick = {
          sent: window.__sent.length,
          pressed: document.querySelector('[data-rules-temperament-option="vitreous"]').getAttribute("aria-pressed"),
          othersFaded: document.querySelector("#rulesChoiceOptions").classList.contains("ep-has-pick"),
          enabled: !confirm.disabled,
        };
        // a redraw of the table keeps the pick
        latestState = structuredClone(latestState);
        renderAll();
        const kept = document.querySelector('[data-rules-temperament-option="vitreous"]').getAttribute("aria-pressed") === "true";
        const stage = document.querySelector("#rulesChoiceOptions").getBoundingClientRect();
        const bar = panel.querySelector(".box").getBoundingClientRect();
        document.dispatchEvent(new KeyboardEvent("keydown", { key: "1", bubbles: true }));
        const keyPick = document.querySelector('[data-rules-temperament-option="choleric"]').getAttribute("aria-pressed") === "true";
        document.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
        return { before, afterPick, kept, stageAboveBar: stage.bottom <= bar.top, keyPick, sent: window.__sent.map((entry) => entry.option).join(",") };
      });
      assert.deepEqual(options, {
        before: { disabled: true, sent: 0 },
        afterPick: { sent: 0, pressed: "true", othersFaded: true, enabled: true },
        kept: true, stageAboveBar: true, keyPick: true, sent: "choleric",
      }, `${viewport.width}: option tiles`);

      // the other player sees the same bar, without buttons
      const opponent = await page.evaluate(() => {
        window.__setChoice({ id: "w1", kind: "score_delta_choice", playerId: "p2", targetPlayerId: "p1", value: 2 });
        const banner = document.querySelector("#rulesOpponentDeciding");
        return {
          shown: !banner.classList.contains("hidden") && banner.classList.contains("ep-opponent"),
          noButtons: banner.querySelectorAll("button").length === 0,
          chooserPanelHidden: document.querySelector("#rulesChoicePanel").classList.contains("hidden"),
        };
      });
      assert.deepEqual(opponent, { shown: true, noButtons: true, chooserPanelHidden: true }, `${viewport.width}: opponent bar`);

      // cards: one card picked above the bar, a second click puts it back, Enter sends it
      const oneCard = await page.evaluate(() => {
        const ids = [...cardsById.keys()];
        window.__setChoice({ id: "c1", kind: "suspend_hand_will", cardIds: ids.slice(10, 13) });
        const panel = document.querySelector("#rulesChoicePanel");
        const cards = [...panel.querySelectorAll("#rulesChoiceOptions .ep-card")];
        const confirm = document.querySelector("#rulesChoiceConfirm");
        const stage = document.querySelector("#rulesChoiceOptions").getBoundingClientRect();
        const bar = panel.querySelector(".box").getBoundingClientRect();
        cards[1].click();
        const picked = { sent: window.__sent.length, pressed: cards[1].getAttribute("aria-pressed"), label: confirm.textContent.includes(cardName(ids[11])), enabled: !confirm.disabled };
        cards[1].click();
        const unpicked = { pressed: cards[1].getAttribute("aria-pressed"), disabled: confirm.disabled };
        document.dispatchEvent(new KeyboardEvent("keydown", { key: "3", bubbles: true }));
        document.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
        return {
          mode: panel.classList.contains("ep-cards"), count: cards.length, stageAboveBar: stage.bottom <= bar.top,
          handFree: !document.body.classList.contains("choice-blocks-hand"),
          picked, unpicked, sent: JSON.stringify(window.__sent.map((entry) => entry.cardIds)) === JSON.stringify([[ids[12]]]),
        };
      });
      assert.deepEqual(oneCard, {
        mode: true, count: 3, stageAboveBar: true, handFree: true,
        picked: { sent: 0, pressed: "true", label: true, enabled: true }, unpicked: { pressed: "false", disabled: true }, sent: true,
      }, `${viewport.width}: one card`);

      // several cards: Validate counts them and stays grey until the count is right
      const severalCards = await page.evaluate(() => {
        const ids = [...cardsById.keys()];
        window.__setChoice({ id: "c2", kind: "draw_replacement", count: 2, cardIds: ids.slice(20, 24) });
        const cards = [...document.querySelectorAll("#rulesChoiceOptions .ep-card")];
        const confirm = document.querySelector("#rulesChoiceConfirm");
        const steps = [[confirm.textContent, confirm.disabled]];
        cards[0].click();
        steps.push([confirm.textContent, confirm.disabled]);
        cards[3].click();
        steps.push([confirm.textContent, confirm.disabled]);
        const innerHidden = getComputedStyle(document.querySelector("#rulesPrivateCardsConfirm")).display === "none";
        const sentBefore = window.__sent.length;
        confirm.click();
        return { steps, innerHidden, sentBefore, sent: JSON.stringify(window.__sent.map((entry) => entry.cardIds)) === JSON.stringify([[ids[20], ids[23]]]) };
      });
      assert.deepEqual(severalCards, {
        steps: [["Valider 0/2", true], ["Valider 1/2", true], ["Valider 2/2", false]], innerHidden: true, sentBefore: 0, sent: true,
      }, `${viewport.width}: several cards`);

      // a power split: each click gives −1, the badge takes it back, nothing leaves before Validate
      const split = await page.evaluate(() => {
        const ids = [...cardsById.keys()].filter((id) => cardsById.get(id).type === "manifestation");
        latestState.battlefield = [0, 1].map((n) => ({ id: `opp-${n}`, cardId: ids[n], ownerId: "p2", controllerId: "p2", faceUp: true, fieldZone: "field", rotation: 0, x: 300 + 200 * n, y: 200, counters: {} }));
        window.__setChoice({ id: "d1", kind: "power_loss_distribution", count: 3, candidateItemIds: ["opp-0", "opp-1"] });
        const card = (n) => document.querySelector(`#rulesChoiceOptions [data-rules-power-target="opp-${n}"]`);
        card(0).click(); card(0).click(); card(1).click();
        // the split keeps its scene even though the cards are on the table
        const stageShown = getComputedStyle(document.querySelector("#rulesChoiceOptions")).display !== "none";
        const full = { stageShown, sent: window.__sent.length, label: document.querySelector("#rulesChoiceConfirm").textContent, badge: card(0).querySelector(".rules-choice-badge").textContent };
        card(0).querySelector(".rules-choice-badge").click();
        const undone = document.querySelector("#rulesChoiceConfirm").textContent;
        card(1).click();
        document.querySelector("#rulesChoiceConfirm").click();
        const answer = window.__sent[0]?.option?.itemIds?.slice().sort().join(",");
        latestState.battlefield = [];
        return { full, undone, answer };
      });
      assert.deepEqual(split, { full: { stageShown: true, sent: 0, label: "Valider 3/3", badge: "−2" }, undone: "Valider 2/3", answer: "opp-0,opp-1,opp-1" }, `${viewport.width}: power split`);

      // hand: a click picks a hand card (it rises and reads "Chosen"), Validate sends
      const hand = await page.evaluate(async () => {
        window.__setChoice({ id: "h1", kind: "discard_from_hand", count: 2 });
        const panel = document.querySelector("#rulesChoicePanel");
        const handCard = (n) => document.querySelector(`#handArea [data-hand-index="${n}"]`);
        const before = handCard(1).getBoundingClientRect().top;
        handCard(1).click();
        handCard(3).click();
        await new Promise((resolve) => setTimeout(resolve, 400));
        const confirm = document.querySelector("#rulesChoiceConfirm");
        const bar = panel.querySelector(".box").getBoundingClientRect();
        const handTop = Math.min(...[...document.querySelectorAll("#handArea [data-hand-card]")].map((card) => card.getBoundingClientRect().top));
        const result = {
          mode: panel.classList.contains("ep-hand"), noStage: getComputedStyle(document.querySelector("#rulesChoiceOptions")).display === "none",
          chosen: handCard(1).classList.contains("is-choice-selected") && handCard(3).classList.contains("is-choice-selected"),
          label: getComputedStyle(handCard(1), "::after").content, risen: handCard(1).getBoundingClientRect().top < before - 10,
          notInspected: document.querySelector("#inspectModal")?.classList.contains("hidden") !== false,
          sentBefore: window.__sent.length, confirm: [confirm.textContent, confirm.disabled], barAboveHand: bar.bottom <= handTop + 1,
        };
        confirm.click();
        const hand = latestState.players.p1.zones.hand.cards;
        result.sent = JSON.stringify(window.__sent.map((entry) => entry.cardIds)) === JSON.stringify([[hand[1], hand[3]]]);
        return result;
      });
      assert.deepEqual(hand, {
        mode: true, noStage: true, chosen: true, label: '"Choisie"', risen: true, notInspected: true,
        sentBefore: 0, confirm: ["Valider 2/2", false], barAboveHand: true, sent: true,
      }, `${viewport.width}: cards from the hand`);

      // all the cards are on the table: no scene, the table cards glow and take the click
      const board = await page.evaluate(async () => {
        const ids = [...cardsById.keys()].filter((id) => cardsById.get(id).type === "manifestation");
        latestState.battlefield = [0, 1].map((n) => ({ id: `mine-${n}`, cardId: ids[n], ownerId: "p1", controllerId: "p1", faceUp: true, fieldZone: "field", rotation: 0, x: 300 + 220 * n, y: 520, counters: {} }));
        window.__setChoice({ id: "b2", kind: "pick_own_item", purpose: "sacrifice", candidateItemIds: ["mine-0", "mine-1"] });
        await new Promise((resolve) => setTimeout(resolve, 50));
        const panel = document.querySelector("#rulesChoicePanel");
        const field = document.querySelector('#battlefield .bf-card[data-item-id="mine-1"]');
        const rect = field.getBoundingClientRect();
        const at = { bubbles: true, cancelable: true, clientX: rect.left + rect.width / 2, clientY: rect.top + rect.height / 2, button: 0, pointerType: "mouse", isPrimary: true };
        field.dispatchEvent(new PointerEvent("pointerdown", at));
        field.dispatchEvent(new PointerEvent("pointerup", at));
        const result = {
          bar: panel.classList.contains("ep-on-table") && getComputedStyle(panel).display !== "none" && panel.querySelector(".box").getBoundingClientRect().height > 0,
          noStage: getComputedStyle(document.querySelector("#rulesChoiceOptions")).display === "none",
          oldBanner: !document.querySelector("#ubChoiceBanner") || document.querySelector("#ubChoiceBanner").classList.contains("hidden"),
          glowing: field.classList.contains("ub-choice-pick"), picked: field.classList.contains("ep-board-picked"),
          sentBefore: window.__sent.length,
        };
        document.querySelector("#rulesChoiceConfirm").click();
        result.sent = window.__sent.map((entry) => entry.itemId).join(",");
        latestState.battlefield = [];
        return result;
      });
      assert.deepEqual(board, { bar: true, noStage: true, oldBanner: true, glowing: true, picked: true, sentBefore: 0, sent: "mine-1" }, `${viewport.width}: cards on the table`);

      // a whole deck: rows, a name search and type filters; a hidden pick stays picked and stays in the bar
      const big = await page.evaluate(() => {
        const all = [...cardsById.values()];
        const wills = all.filter((card) => card.type !== "manifestation").slice(0, 8).map((card) => card.id);
        const manifestations = all.filter((card) => card.type === "manifestation").slice(0, 16).map((card) => card.id);
        const deck = [...manifestations, ...wills];
        window.__setChoice({ id: "s1", kind: "discard_from_hand", count: 2, candidateCardIds: deck });
        const panel = document.querySelector("#rulesChoicePanel");
        const options = document.querySelector("#rulesChoiceOptions");
        const visible = () => [...options.querySelectorAll(".ep-card")].filter((card) => getComputedStyle(card).display !== "none");
        const rows = new Set(visible().map((card) => Math.round(card.getBoundingClientRect().top))).size;
        const input = options.querySelector(".ep-search");
        visible()[0].click();
        const firstName = cardName(deck[0]);
        input.value = firstName.slice(1, 6).toUpperCase();
        input.dispatchEvent(new Event("input", { bubbles: true }));
        const searched = visible().map((card) => card.dataset.epCard);
        input.value = "";
        input.dispatchEvent(new Event("input", { bubbles: true }));
        options.querySelector(`[data-ep-filter-type="${cardsById.get(wills[0]).type}"]`).click();
        const typed = visible().map((card) => cardsById.get(card.dataset.epCard).type);
        const stillPicked = options.querySelector(`[data-ep-card="${deck[0]}"]`).getAttribute("aria-pressed") === "true";
        const thumbs = panel.querySelectorAll(".ep-actions .ep-picked-card").length;
        visible()[0].click();
        const confirm = document.querySelector("#rulesChoiceConfirm");
        const label = confirm.textContent;
        confirm.click();
        const stage = options.getBoundingClientRect();
        return {
          many: panel.classList.contains("ep-many"), rows: rows >= 2, searchFound: searched.includes(deck[0]),
          searchNarrowed: searched.length < deck.length, typeOnly: typed.length > 0 && typed.every((type) => type === cardsById.get(wills[0]).type),
          stillPicked, thumbs, label, onScreen: stage.top >= 0,
          sent: JSON.stringify(window.__sent.map((entry) => entry.cardIds)) === JSON.stringify([[deck[0], wills[0]]]),
        };
      });
      assert.deepEqual(big, {
        many: true, rows: true, searchFound: true, searchNarrowed: true, typeOnly: true,
        stillPicked: true, thumbs: 1, label: "Valider 2/2", onScreen: true, sent: true,
      }, `${viewport.width}: a big place`);

      // a card name: typed above the bar, the matching cards as pictures, Validate names the card
      const named = await page.evaluate(() => {
        window.__setChoice({ id: "n1", kind: "declare_card_name", mode: "search_deck", targetPlayerId: "p2" });
        const panel = document.querySelector("#rulesChoicePanel");
        const options = document.querySelector("#rulesChoiceOptions");
        const input = options.querySelector("#rulesDeclareNameInput");
        const confirm = document.querySelector("#rulesChoiceConfirm");
        const before = { disabled: confirm.disabled, hint: Boolean(options.querySelector(".ep-name-hint")) };
        const target = [...cardsById.keys()][7];
        const name = cardName(target);
        input.value = name.slice(0, 4).toLowerCase();
        input.dispatchEvent(new Event("input"));
        const found = [...options.querySelectorAll(".ep-name-results .ep-card")];
        const card = found.find((entry) => entry.dataset.epName === name);
        card?.click();
        const label = confirm.textContent;
        const enabled = !confirm.disabled;
        const sentBefore = window.__sent.length;
        confirm.click();
        const stage = options.getBoundingClientRect();
        const bar = panel.querySelector(".box").getBoundingClientRect();
        return {
          input: panel.classList.contains("ep-input"), before, found: found.length > 0 && found.length <= 12, card: Boolean(card),
          label: label === `Valider : ${name}`, enabled, sentBefore, aboveBar: stage.bottom <= bar.top, onScreen: stage.top >= 0,
          sent: window.__sent.length === 1 && cardName(window.__sent[0].option) === name,
        };
      });
      assert.deepEqual(named, {
        input: true, before: { disabled: true, hint: true }, found: true, card: true, label: true, enabled: true, sentBefore: 0,
        aboveBar: true, onScreen: true, sent: true,
      }, `${viewport.width}: a card name`);

      // a guess: chip rows above the bar, Validate repeats the guess
      const guessed = await page.evaluate(() => {
        window.__setChoice({ id: "g1", kind: "guess_top_card", targetPlayerId: "p2", types: ["manifestation", "will"], temperaments: ["choleric", "vitreous"], values: [1, 2, 3] });
        const options = document.querySelector("#rulesChoiceOptions");
        const confirm = document.querySelector("#rulesChoiceConfirm");
        options.querySelector('[data-rules-guess-field="temperament"][data-rules-guess-value="vitreous"]').click();
        options.querySelector('[data-rules-guess-field="value"][data-rules-guess-value="3"]').click();
        const label = confirm.textContent;
        const innerHidden = getComputedStyle(options.querySelector("#rulesGuessConfirm")).display === "none";
        const sentBefore = window.__sent.length;
        confirm.click();
        return { label: label.startsWith("Valider : ") && label.endsWith("· 3"), innerHidden, sentBefore, sent: window.__sent[0]?.option };
      });
      assert.deepEqual(guessed, { label: true, innerHidden: true, sentBefore: 0, sent: { type: "manifestation", temperament: "vitreous", value: 3 } }, `${viewport.width}: a guess`);

      // fonts stay readable
      const minFont = await page.evaluate(() => {
        window.__setChoice({ id: "o2", kind: "clemency_choice", relatedCardId: [...cardsById.keys()][1], points: 3 });
        return Math.min(...[...document.querySelectorAll("#rulesChoicePanel .box *")]
          .filter((element) => getComputedStyle(element).display !== "none" && element.textContent.trim())
          .map((element) => parseFloat(getComputedStyle(element).fontSize)));
      });
      assert.ok(minFont >= 14, `${viewport.width}: smallest font ${minFont}`);
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log("effect prompt ok");
  } finally {
    await browser.close();
    server.close();
  }
})().catch((error) => { console.error(error); process.exit(1); });
