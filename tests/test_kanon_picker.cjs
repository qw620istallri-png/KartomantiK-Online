// Explicit choice fixtures, local art, no VFX or physical-device certification.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const out = path.join(root, 'reports/systematic-audit/kanon-events-followup');

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
        const card = await page.evaluate(language => {
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
          window.__kanonSent = [];
          send = payload => window.__kanonSent.push(payload);
          const repeated = cid('Wind Sprout');
          latestState.rulesEngine.pendingChoice = { id: 'four-copies', kind: 'draw_replacement', playerId: 'p1',
            sourceCardId: cid('Kanon, the Deathdealer'), count: 2, cardIds: Array(4).fill(repeated) };
          resetRulesChoiceInteraction(); renderRulesChoice(true);
          return repeated;
        }, language);
        const cards = page.locator('[data-rules-private-card]');
        assert.equal(await cards.count(), 4);
        const confirm = page.locator('#rulesPrivateCardsConfirm');
        assert.equal(await confirm.isDisabled(), true);
        await cards.nth(0).click();
        assert.equal(await confirm.isDisabled(), true);
        await cards.nth(2).click();
        assert.equal(await confirm.isDisabled(), false);
        await cards.nth(3).click();
        assert.equal(await cards.nth(3).getAttribute('aria-pressed'), 'false');
        await cards.nth(0).click();
        assert.equal(await confirm.isDisabled(), true);
        await cards.nth(3).click();
        assert.equal(await confirm.isVisible(), true);
        await confirm.click();
        assert.deepEqual(await page.evaluate(() => window.__kanonSent), [{ type: 'resolve_rules_choice', choiceId: 'four-copies', cardIds: [card, card] }]);
        assert.equal(await confirm.isDisabled(), true);
        assert.deepEqual(errors, []);
        cases.push({ viewport, language, identicalCards: 4, chosen: 2, passed: true });
        await page.close();
      }
    }
  } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
  fs.writeFileSync(path.join(out, 'picker.json'), JSON.stringify({ engine: 'chromium', physicalDevice: false,
    summary: { configurations: cases.length, failed: 0 }, cases }, null, 2) + '\n');
  console.log(`Kanon duplicate picker: ${cases.length} configurations OK`);
})().catch(error => { console.error(error); process.exitCode = 1; });
