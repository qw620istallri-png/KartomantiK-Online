// Explicit choice fixtures, local art, no VFX or physical-device certification.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const out = path.join(root, 'reports/systematic-audit/private-hand-followup');
const assetVersion = fs.readFileSync(path.join(root, 'public/app.js'), 'utf8').match(/STATIC_ASSET_VERSION = "([^"]+)"/)[1];
const versionParts = assetVersion.match(/beta-(\d+(?:-\d+)*)/)[1].split('-');
// a release without a fix number reads "141.0", like the app label
if (versionParts.length === 1) versionParts.push('0');
const expectedLabel = 'beta ' + versionParts.join('.');

(async () => {
  fs.mkdirSync(out, { recursive: true });
  const publicRoot = path.join(root, 'public');
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://localhost');
    const file = path.resolve(publicRoot, '.' + (url.pathname === '/' ? '/index.html' : decodeURIComponent(url.pathname)));
    if (!file.startsWith(publicRoot + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return res.writeHead(404).end();
    res.setHeader('Content-Type', ({ '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.json': 'application/json' })[path.extname(file)] || 'application/octet-stream');
    fs.createReadStream(file).pipe(res);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const cases = [];
  try {
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 844, height: 390 }]) {
      for (const language of ['fr', 'en', 'it']) {
        const page = await browser.newPage({ viewport });
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('**/*', route => new URL(route.request().url()).hostname === '127.0.0.1' ? route.continue() : route.abort());
        await page.goto(`http://127.0.0.1:${server.address().port}/`);
        await page.waitForFunction(() => cardsById.size === 450);
        const versionLabel = await page.locator('#appVersion').innerText();
        assert.equal(versionLabel, expectedLabel);
        await page.evaluate(language => {
          currentLanguage = language;
          myPlayerId = 'p1'; isObserver = false; connectionRole = 'player';
          for (const card of cardsById.values()) card.image = 'card-back.webp';
          const cid = name => [...cardsById.values()].find(c => c.name === name).id;
          const zones = () => Object.fromEntries(ZONES.map(z => [z, { cards: [], count: 0, owners: {} }]));
          latestState = { players: { p1: { id: 'p1', name: 'Alice', seat: 0, score: 50, zones: zones() },
            p2: { id: 'p2', name: 'Benoît', seat: 1, score: 50, zones: zones() } }, battlefield: [], tokens: [], strokes: [],
            phaseTracker: { enabled: true, advanced: true, turn: 2, index: ADVANCED_PHASES.findIndex(p => p.id === 'confrontation_reaction') },
            rulesEngine: { enabled: true, priorityPlayerId: 'p1', actionStack: [], ongoingEffects: [],
              readyPlayerIds: ['p1', 'p2'], deckConfirmedPlayerIds: ['p1', 'p2'], firstManifestationComplete: true } };
          document.querySelector('#joinScreen').classList.add('hidden');
          document.querySelector('#gameScreen').classList.remove('hidden');
          uiBeta.setEnabled(true); renderAll();
          window.__handSent = [];
          send = payload => window.__handSent.push(payload);
          const repeated = cid('Wind Sprout');
          latestState.players.p2.zones.hand = { count: 4 };
          const wholeHand = [cid('Weaken'), repeated, repeated, cid('Wall off')];
          window.__wholeHand = wholeHand;
          window.__wombFixture = { id: 'womb-pick', kind: 'reveal_hand_discard', purpose: 'womb',
            playerId: 'p1', targetPlayerId: 'p2', sourceCardId: cid('Extortionist Womb'),
            cardIds: [repeated, repeated], revealedHandCardIds: wholeHand };
          resetRulesChoiceInteraction(); renderRulesChoice(true);
          showRevealPopup({ type: 'reveal', ownerId: 'p2', zone: 'hand', cards: [cid('Weaken'), cid('Wall off')] });
        }, language);
        assert.equal(await page.locator('#revealCards [data-card-id]').count(), 2);
        assert.equal(await page.locator('#revealPanel').isVisible(), true);
        await page.locator('#revealCloseBtn').click();
        await page.evaluate(() => {
          window.__handSent = [];
          latestState.rulesEngine.pendingChoice = window.__wombFixture;
          resetRulesChoiceInteraction(); renderRulesChoice(true);
        });
        const cards = page.locator('[data-rules-reveal-index]');
        assert.equal(await cards.count(), 2);
        assert.equal(await page.locator('#rulesChoiceOptions .rules-choice-card').count(), 4);
        assert.equal(await page.locator('#rulesChoiceOptions .rules-choice-card[disabled]').count(), 2);
        const heading = await page.locator('#rulesChoiceHeading').innerText();
        const text = await page.locator('#rulesChoiceText').innerText();
        assert.equal(heading, { fr: 'Quelle manifestation Chaîner ?', en: 'Chain which manifestation?', it: 'Quale manifestazione concatenare?' }[language]);
        assert(text.includes('Benoît'));
        assert.equal(await cards.nth(0).getAttribute('title'), await cards.nth(1).getAttribute('title'));
        await page.mouse.move(8, 8); // Keep the existing hover preview out of the layout capture.
        await cards.locator('img').evaluateAll(images => Promise.all(images.map(img => img.decode().catch(() => {}))));
        await page.waitForTimeout(500); // Inspect the settled picker, after its existing entrance animation.
        if (language === 'fr') await page.screenshot({ path: path.join(out, `picker-${viewport.width}.png`) });
        await cards.nth(1).click();
        assert.deepEqual(await page.evaluate(() => window.__handSent), [{ type: 'resolve_rules_choice', choiceId: 'womb-pick', option: '1' }]);
        assert.equal(await cards.nth(0).isDisabled(), true);
        assert.equal(await cards.nth(1).isDisabled(), true);
        await page.evaluate(() => {
          window.__handSent = [];
          latestState.rulesEngine.pendingChoice = { id: 'trauma-pick', kind: 'reveal_hand_discard', playerId: 'p1',
            targetPlayerId: 'p2', sourceCardId: [...cardsById.values()].find(c => c.name === 'Traumatize').id,
            cardIds: window.__wholeHand };
          resetRulesChoiceInteraction(); renderRulesChoice(true);
        });
        assert.equal(await cards.count(), 4);
        const traumaHeading = await page.locator('#rulesChoiceHeading').innerText();
        assert.equal(traumaHeading, { fr: 'Choisir une carte à défausser', en: 'Choose a card to discard', it: 'Scegli una carta da scartare' }[language]);
        await cards.nth(3).click();
        assert.deepEqual(await page.evaluate(() => window.__handSent), [{ type: 'resolve_rules_choice', choiceId: 'trauma-pick', option: '3' }]);
        assert.deepEqual(errors, []);
        cases.push({ viewport, language, versionLabel, heading, traumaHeading, fullHand: 4, wombEligible: 2, scenarios: 2, passed: true });
        await page.close();
      }
    }
  } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
  fs.writeFileSync(path.join(out, 'picker.json'), JSON.stringify({ engine: 'chromium', physicalDevice: false,
    summary: { configurations: cases.length, scenarios: cases.length * 2, failed: 0 }, cases }, null, 2) + '\n');
  console.log(`Private hand picker: ${cases.length} configurations / ${cases.length * 2} scenarios OK`);
})().catch(error => { console.error(error); process.exitCode = 1; });
