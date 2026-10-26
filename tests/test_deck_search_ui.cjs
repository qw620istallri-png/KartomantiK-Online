/* Real pointer/input controls, translated prompts and public card references.
 * Local art isolates UI; no remote-art or physical-device certification.
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const http = require("node:http");
const { chromium } = require("playwright");
const root = path.resolve(__dirname, "..");
const publicRoot = path.join(root, "public");
const out = path.join(root, "reports/systematic-audit/deck-search-followup");
const mime = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".webp": "image/webp" };

(async () => {
  fs.mkdirSync(out, { recursive: true });
  const server = http.createServer((req, res) => {
    const pathname = decodeURIComponent(new URL(req.url, "http://localhost").pathname);
    const file = path.resolve(publicRoot, "." + (pathname === "/" ? "/index.html" : pathname));
    if (!file.startsWith(publicRoot + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return res.writeHead(404).end();
    res.writeHead(200, { "Content-Type": mime[path.extname(file)] || "application/octet-stream" });
    fs.createReadStream(file).pipe(res);
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "chrome", headless: true });
  const cases = [];
  try {
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 844, height: 390 }]) {
      for (const language of ["fr", "en", "it"]) {
        const page = await browser.newPage({ viewport });
        const errors = [];
        page.on("pageerror", error => errors.push(error.message));
        await page.route("**/*", route => new URL(route.request().url()).hostname === "127.0.0.1" ? route.continue() : route.abort());
        await page.goto(`http://127.0.0.1:${server.address().port}/`);
        await page.waitForFunction(() => cardsById.size === 450 && typeof renderAll === "function");
        const fixture = await page.evaluate(language => {
          currentLanguage = language;
          myPlayerId = "p1"; isObserver = false; connectionMode = "casual"; connectionRole = "player";
          document.querySelector("#joinScreen").classList.add("hidden");
          document.querySelector("#gameScreen").classList.remove("hidden");
          const cid = name => [...cardsById.values()].find(card => card.name === name).id;
          for (const card of cardsById.values()) card.image = "card-back.webp";
          const zones = () => Object.fromEntries(ZONES.map(zone => [zone, { cards: [], owners: {}, entryVersions: {} }]));
          latestState = { ended: false, players: {
            p1: { id: "p1", name: "P1", seat: 0, score: 50, zones: zones() },
            p2: { id: "p2", name: "P2", seat: 1, score: 50, zones: zones() },
          }, battlefield: [], tokens: [], strokes: [],
          phaseTracker: { enabled: true, advanced: true, turn: 2, passedPlayerIds: [], index: ADVANCED_PHASES.findIndex(p => p.id === "confrontation_reaction") },
          rulesEngine: { enabled: true, priorityPlayerId: "p1", priorityPasses: [], actionStack: [], ongoingEffects: [], playPermissions: [],
            firstManifestationComplete: true, firstManifestationItemIds: {}, readyPlayerIds: ["p1", "p2"], deckConfirmedPlayerIds: ["p1", "p2"] } };
          pendingRulesBoardFlow = null;
          uiBeta.setEnabled(true);
          renderAll();
          window.__deckSent = [];
          send = payload => window.__deckSent.push(payload);
          const cards = [cid("Wind Sprout"), cid("Weaken"), cid("Cleanse")];
          window.__deckChoice = choice => {
            latestState.rulesEngine.pendingChoice = choice;
            window.__deckSent = [];
            resetRulesChoiceInteraction();
            renderRulesChoice(true);
          };
          return { cards, declaredName: cardName(cards[0]), mejik: cid("Mejik, the Labyrinther"),
            hermeto: cid("Hermeto, the Observer"), recall: cid("Recall") };
        }, language);
        for (const count of [0, 1, 2]) {
          const id = `hermeto-${count}`;
          await page.evaluate(({ id, fixture }) => window.__deckChoice({ id, kind: "discard_from_hand", playerId: "p1", count: 2,
            upTo: true, revealSelected: true, candidateCardIds: fixture.cards, sourceCardId: fixture.hermeto }), { id, fixture });
          const text = await page.locator("#rulesChoiceText").innerText();
          assert.ok(text.includes({ fr: "jusqu’à 2", en: "up to 2", it: "fino a 2" }[language]));
          for (let n = 0; n < count; n++) await page.locator(`[data-rules-discard-index="${n}"]`).click();
          await page.locator("#rulesDiscardConfirm").click();
          assert.deepEqual(await page.evaluate(() => window.__deckSent), [{ type: "resolve_rules_choice", choiceId: id, cardIds: fixture.cards.slice(0, count) }]);
        }
        await page.evaluate(fixture => window.__deckChoice({ id: "recall", kind: "discard_from_hand", playerId: "p1", count: 1,
          revealSelected: true, candidateCardIds: fixture.cards, sourceCardId: fixture.recall }), fixture);
        await page.locator('[data-rules-discard-index="1"]').click();
        assert.deepEqual(await page.evaluate(() => window.__deckSent), [{ type: "resolve_rules_choice", choiceId: "recall", cardIds: [fixture.cards[1]] }]);
        await page.evaluate(fixture => window.__deckChoice({ id: "mejik", kind: "declare_card_name", mode: "search_deck", declarationCost: true,
          playerId: "p1", targetPlayerId: "p2", sourceCardId: fixture.mejik }), fixture);
        assert.ok((await page.locator("#rulesChoiceText").innerText()).includes({ fr: "avant", en: "before", it: "prima" }[language]));
        assert.equal(await page.locator("#rulesDeclareNameConfirm").isDisabled(), true);
        await page.locator("#rulesDeclareNameInput").fill("unknown-name");
        assert.equal(await page.locator("#rulesDeclareNameConfirm").isDisabled(), true);
        await page.locator("#rulesDeclareNameInput").fill(fixture.declaredName);
        const buttonBox = await page.locator("#rulesDeclareNameConfirm").boundingBox();
        assert.ok(buttonBox.x >= 0 && buttonBox.y >= 0 && buttonBox.x + buttonBox.width <= viewport.width && buttonBox.y + buttonBox.height <= viewport.height);
        await page.screenshot({ path: path.join(out, `name-cost-${language}-${viewport.width}.png`) });
        await page.locator("#rulesDeclareNameConfirm").click();
        assert.deepEqual(await page.evaluate(() => window.__deckSent), [{ type: "resolve_rules_choice", choiceId: "mejik", option: fixture.cards[0] }]);
        assert.equal(await page.locator("#rulesDeclareNameInput").isDisabled(), true);
        const checks = await page.evaluate(({ fixture, language }) => {
          const details = rulesActionDetails({ source: { cardId: fixture.mejik }, cost: { declaredCardId: fixture.cards[0], sourceExhausted: true } });
          const entry = (details, type = "rules_choice_resolved") => formatLogEntry({ actorId: "p1", actorName: "P1", type, details }, { language, html: true });
          const declaration = entry({ kind: "declare_card_name", status: "declared", declaredCardId: fixture.cards[0], sourceCardId: fixture.mejik, playerId: "p1", mode: "search_deck" });
          const resolved = entry({ label: "Mejik", stackDepth: 0, effectResult: { kind: "declare_card_name", mode: "search_deck", status: "discarded", playerId: "p1", declaredCardId: fixture.cards[0], cardId: fixture.cards[0] } }, "rules_action_resolved");
          const revealed = entry({ kind: "search_deck", revealed: true, cardIds: [fixture.cards[0]], sourceCardId: fixture.hermeto, playerId: "p1" });
          return { details, declaration, resolved, revealed };
        }, { fixture, language });
        for (const value of Object.values(checks)) {
          assert.ok(value.includes(fixture.declaredName) && !/\{\w+\}/.test(value));
          assert.ok(value.includes(`data-${value === checks.details ? "rules" : "log"}-card="${fixture.cards[0]}"`));
        }
        assert.deepEqual(errors, []);
        cases.push({ viewport, language, passed: true, checks: ["hermeto-zero-one-two", "recall-single", "name-cost-input-and-lock", "visible-confirm", "declared-name-stack", "public-reveal-log", "resolution-log"] });
        await page.close();
      }
    }
    fs.writeFileSync(path.join(out, "browser.json"), JSON.stringify({ schemaVersion: 1, engine: "chromium", version: browser.version(), physicalDevice: false,
      finishedAt: new Date().toISOString(), summary: { executed: cases.length, failed: 0 }, cases }, null, 2) + "\n");
    console.log(`Deck search UI: ${cases.length} desktop/mobile language cases passed`);
  } finally { await browser.close(); server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
})().catch(error => { console.error(error); process.exitCode = 1; });
