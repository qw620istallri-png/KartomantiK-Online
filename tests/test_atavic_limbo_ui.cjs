// Local art and explicit choice fixtures; no physical-device certification.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const out = path.join(root, 'reports/systematic-audit/atavic-limbo-followup');
const before = process.argv.includes('--before');

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
      for (const language of before ? ['fr'] : ['fr', 'en', 'it']) {
        const page = await browser.newPage({ viewport });
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('**/*', route => new URL(route.request().url()).hostname === '127.0.0.1' ? route.continue() : route.abort());
        await page.goto(`http://127.0.0.1:${server.address().port}/`);
        await page.waitForFunction(() => cardsById.size === 450);
        const cards = await page.evaluate(language => {
          currentLanguage = language;
          myPlayerId = 'p1'; isObserver = false; connectionRole = 'player';
          for (const card of cardsById.values()) card.image = 'card-back.webp';
          const cid = name => [...cardsById.values()].find(c => c.name === name).id;
          const zones = () => Object.fromEntries(ZONES.map(z => [z, { cards: [], count: 0, owners: {} }]));
          latestState = { players: { p1: { id: 'p1', name: 'Alice', seat: 0, score: 50, zones: zones() },
            p2: { id: 'p2', name: 'Benoît', seat: 1, score: 50, zones: zones() } }, battlefield: [], tokens: [], strokes: [],
            phaseTracker: { enabled: true, advanced: true, turn: 2, index: ADVANCED_PHASES.findIndex(p => p.id === 'end_actions') },
            rulesEngine: { enabled: true, priorityPlayerId: 'p1', actionStack: [], ongoingEffects: [],
              readyPlayerIds: ['p1', 'p2'], deckConfirmedPlayerIds: ['p1', 'p2'], firstManifestationComplete: true } };
          document.querySelector('#joinScreen').classList.add('hidden');
          document.querySelector('#gameScreen').classList.remove('hidden');
          uiBeta.setEnabled(true); renderAll();
          window.__limboSent = [];
          send = payload => window.__limboSent.push(payload);
          window.__limboChoice = (owner, cards) => {
            window.__limboSent = [];
            latestState.rulesEngine.pendingChoice = { id: 'limbo-' + owner, kind: 'deck_reorder', playerId: 'p1',
              sourceCardId: cid('Atavic Introspection'),
              groups: [{ playerId: owner, fromZone: 'graveyard', cardIds: cards, topCount: 1, bottomCount: 1 }] };
            resetRulesChoiceInteraction(); renderRulesChoice(true);
          };
          return [cid('Wind Sprout'), cid('Weaken')];
        }, language);
        for (const owner of before ? ['p2'] : ['p1', 'p2']) {
          await page.evaluate(({ owner, cards }) => window.__limboChoice(owner, cards), { owner, cards });
          if (!before) {
            const heading = await page.locator('#rulesChoiceHeading').innerText();
            const text = await page.locator('#rulesChoiceText').innerText();
            assert(heading.includes('Limbo'));
            assert(text.includes(owner === 'p1' ? 'Alice' : 'Benoît'));
            const caption = await page.locator('.rules-reorder-group > strong').innerText();
            assert(caption.includes(owner === 'p1' ? 'Alice' : 'Benoît'));
            assert(caption.includes('Deck'));
            assert.equal(await page.locator('.rules-reorder-group > strong').isVisible(), true);
            const box = await page.locator('#rulesDeckReorderConfirm').boundingBox();
            assert(box && box.y >= 0 && box.y + box.height <= viewport.height);
          }
          if (language === 'fr' && owner === 'p2') await page.screenshot({ path: path.join(out, `${before ? 'before' : 'after'}-${viewport.width}.png`) });
          await page.locator('#rulesDeckReorderConfirm').click();
          assert.deepEqual(await page.evaluate(() => window.__limboSent), [{ type: 'resolve_rules_choice', choiceId: 'limbo-' + owner,
            option: { groups: [{ playerId: owner, top: [cards[0]], bottom: [cards[1]] }] } }]);
          assert.equal(await page.locator('#rulesDeckReorderConfirm').isDisabled(), true);
        }
        assert.deepEqual(errors, []);
        cases.push({ viewport, language, owners: before ? ['p2'] : ['p1', 'p2'], passed: true });
        await page.close();
      }
    }
  } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
  fs.writeFileSync(path.join(out, before ? 'browser-before.json' : 'browser.json'), JSON.stringify({ engine: 'chromium', physicalDevice: false,
    summary: { configurations: cases.length, ownerCases: before ? cases.length : cases.length * 2, failed: 0 }, cases }, null, 2) + '\n');
  console.log(`Atavic Limbo UI: ${cases.length} configurations OK`);
})().catch(error => { console.error(error); process.exitCode = 1; });
