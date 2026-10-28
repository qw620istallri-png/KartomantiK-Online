// Server-serialized choices, local art; pointer gestures on identical cards.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const out = path.join(root, 'reports/systematic-audit/deck-sequence-followup');
const fixtures = JSON.parse(fs.readFileSync(path.join(out, 'picker-fixtures.json'), 'utf8'));

(async () => {
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
        await page.evaluate(language => {
          currentLanguage = language; myPlayerId = 'p1'; isObserver = false; connectionRole = 'player';
          for (const card of cardsById.values()) card.image = 'card-back.webp';
          const seed = [...cardsById.values()].find(c => c.name === 'Wind Sprout');
          for (const id of ['m2', 'm3', 'm4', 'w2', 'pw3']) cardsById.set(id, { ...seed, id });
          const zones = () => Object.fromEntries(ZONES.map(z => [z, { cards: [], count: 0, owners: {} }]));
          latestState = { players: { p1: { id: 'p1', name: 'Alice', seat: 0, score: 50, zones: zones() },
            p2: { id: 'p2', name: 'Benoît', seat: 1, score: 50, zones: zones() } }, battlefield: [], tokens: [], strokes: [],
            phaseTracker: { enabled: true, advanced: true, turn: 2, index: ADVANCED_PHASES.findIndex(p => p.id === 'confrontation_reaction') },
            rulesEngine: { enabled: true, priorityPlayerId: 'p1', actionStack: [], ongoingEffects: [],
              readyPlayerIds: ['p1', 'p2'], deckConfirmedPlayerIds: ['p1', 'p2'], firstManifestationComplete: true } };
          document.querySelector('#joinScreen').classList.add('hidden');
          document.querySelector('#gameScreen').classList.remove('hidden');
          uiBeta.setEnabled(true); renderAll();
          send = payload => window.__deckSent.push(payload);
        }, language);
        for (const [scenario, choice] of Object.entries(fixtures)) {
          await page.evaluate(choice => {
            myPlayerId = choice.playerId; window.__deckSent = [];
            latestState.rulesEngine.pendingChoice = choice;
            resetRulesChoiceInteraction(); renderRulesChoice(true);
          }, choice);
          if (scenario === 'bloatuba-pick') {
            const cards = page.locator('[data-rules-reveal-index]');
            assert.equal(await cards.count(), 2);
            assert.equal(await cards.nth(0).getAttribute('title'), await cards.nth(1).getAttribute('title'));
            await cards.nth(1).click();
            assert.deepEqual(await page.evaluate(() => window.__deckSent), [{ type:'resolve_rules_choice', choiceId:choice.id, option:'1' }]);
            assert.equal(await cards.nth(0).isDisabled(), true);
          } else {
            const confirm = page.locator('#rulesDeckReorderConfirm');
            if (scenario === 'ponderer') {
              assert.equal(await confirm.isDisabled(), true);
              const pool = page.locator('[data-rules-reorder-strip="pool"] .rules-reorder-card');
              assert.equal(await pool.count(), 3);
              for (const side of ['extra', 'top', 'bottom']) {
                const box = await pool.first().boundingBox();
                const lane = await page.locator(`[data-rules-reorder-strip="${side}"]`).boundingBox();
                await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
                await page.mouse.down();
                await page.mouse.move(lane.x + lane.width * .75, lane.y + lane.height / 2, { steps: 12 });
                await page.mouse.up();
              }
              assert.equal(await pool.count(), 0);
              for (const side of ['top','bottom','extra']) assert.equal(await page.locator(`[data-rules-reorder-strip="${side}"] .rules-reorder-card`).count(), 1);
            } else {
              assert.equal(await page.locator('[data-rules-reorder-strip="bottom"] .rules-reorder-card').count(), 3);
            }
            assert.equal(await confirm.isDisabled(), false);
            await page.mouse.move(viewport.width - 2, viewport.height - 2);
            if (language === 'fr') {
              await page.waitForTimeout(500);
              await page.screenshot({ path: path.join(out, `${scenario}-${viewport.width}.png`) });
            }
            await confirm.click();
            const expected = scenario === 'ponderer'
              ? { playerId:'p1', top:['m2'], bottom:['m2'], extra:['m2'] }
              : { playerId:'p2', top:[], bottom:['w2','w2','pw3'] };
            assert.deepEqual(await page.evaluate(() => window.__deckSent), [{ type:'resolve_rules_choice', choiceId:choice.id, option:{groups:[expected]} }]);
            assert.equal(await confirm.isDisabled(), true);
            // Exercise the existing error/retry hook without duplicating a send.
            await page.evaluate(() => { rulesDeckReorderRetry(); window.__deckSent = []; });
            assert.equal(await confirm.isDisabled(), false);
            await confirm.click();
            assert.deepEqual(await page.evaluate(() => window.__deckSent[0].option.groups[0]), expected);
          }
          cases.push({ scenario, language, viewport, actor:choice.playerId, passed:true });
        }
        assert.deepEqual(errors, []);
        await page.close();
      }
    }
  } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
  fs.writeFileSync(path.join(out, 'picker.json'), JSON.stringify({engine:'chromium', physicalDevice:false,
    summary:{configurations:6, scenarios:cases.length, failed:0}, cases}, null, 2) + '\n');
  console.log(`Deck sequence UI: 6 configurations / ${cases.length} scenarios OK`);
})().catch(error => { console.error(error); process.exitCode=1; });
