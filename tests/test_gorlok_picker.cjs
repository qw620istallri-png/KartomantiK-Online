// Explicit choice fixtures, local art, no VFX or physical-device certification.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const out = path.join(root, 'reports/systematic-audit/gorlok-draw-followup');

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
          window.__gorlokSent = [];
          send = payload => window.__gorlokSent.push(payload);
          const repeated = cid('Wind Sprout');
          latestState.players.p2.zones.hand = { count: 5 };
          latestState.rulesEngine.pendingChoice = { id: 'gorlok-draw', kind: 'reveal_hand_discard', purpose: 'gorlok',
            playerId: 'p1', targetPlayerId: 'p2', sourceCardId: cid('Gorlok, the Blinded Indiscreet'),
            cardIds: [repeated, repeated, cid('Weaken')] };
          resetRulesChoiceInteraction(); renderRulesChoice(true);
          return repeated;
        }, language);
        const cards = page.locator('[data-rules-reveal-index]');
        assert.equal(await cards.count(), 3);
        const heading = await page.locator('#rulesChoiceHeading').innerText();
        const text = await page.locator('#rulesChoiceText').innerText();
        assert.equal(heading, { fr: 'Exiler une carte piochée', en: 'Exile a drawn card', it: 'Esilia una carta pescata' }[language]);
        assert(text.includes('Benoît'));
        assert(text.includes('Gorlok'));
        assert.equal(await cards.nth(0).getAttribute('title'), await cards.nth(1).getAttribute('title'));
        await cards.locator('img').evaluateAll(images => Promise.all(images.map(img => img.decode().catch(() => {}))));
        await page.waitForTimeout(500); // Inspect the settled picker, after its existing entrance animation.
        if (language === 'fr') await page.screenshot({ path: path.join(out, `picker-${viewport.width}.png`) });
        await cards.nth(1).click();
        assert.deepEqual(await page.evaluate(() => window.__gorlokSent), [{ type: 'resolve_rules_choice', choiceId: 'gorlok-draw', option: '1' }]);
        assert.equal(await cards.nth(0).isDisabled(), true);
        assert.equal(await cards.nth(1).isDisabled(), true);
        assert.equal(await cards.nth(2).isDisabled(), true);
        assert.deepEqual(errors, []);
        cases.push({ viewport, language, heading, shown: 3, totalHand: 5, chosenIndex: 1, passed: true });
        await page.close();
      }
    }
  } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
  fs.writeFileSync(path.join(out, 'picker.json'), JSON.stringify({ engine: 'chromium', physicalDevice: false,
    summary: { configurations: cases.length, failed: 0 }, cases }, null, 2) + '\n');
  console.log(`Gorlok draw picker: ${cases.length} configurations OK`);
})().catch(error => { console.error(error); process.exitCode = 1; });
