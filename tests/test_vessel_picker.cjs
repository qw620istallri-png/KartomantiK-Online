// Shipped server choice payloads, local card art, desktop/mobile emulation.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const out = path.join(root, 'reports/systematic-audit/vessel-choice-followup');
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
          for (const id of ['m2', 'm3', 'm4']) cardsById.set(id, { ...seed, id, name: 'Fixture ' + id });
          const zones = () => Object.fromEntries(ZONES.map(z => [z, { cards: [], count: 0, owners: {} }]));
          latestState = { players: { p1: { id: 'p1', name: 'Alice', seat: 0, score: 50, zones: zones() },
            p2: { id: 'p2', name: 'Benoît', seat: 1, score: 50, zones: zones() } }, battlefield: [], tokens: [], strokes: [],
            phaseTracker: { enabled: true, advanced: true, turn: 2, index: ADVANCED_PHASES.findIndex(p => p.id === 'confrontation_reaction') },
            rulesEngine: { enabled: true, priorityPlayerId: 'p1', actionStack: [], ongoingEffects: [],
              readyPlayerIds: ['p1', 'p2'], deckConfirmedPlayerIds: ['p1', 'p2'], firstManifestationComplete: true } };
          document.querySelector('#joinScreen').classList.add('hidden');
          document.querySelector('#gameScreen').classList.remove('hidden');
          uiBeta.setEnabled(true); renderAll();
          send = payload => window.__vesselSent.push(payload);
        }, language);
        for (const [purpose, choice] of Object.entries(fixtures)) {
          await page.evaluate(choice => {
            myPlayerId = choice.playerId;
            latestState.rulesEngine.pendingChoice = choice;
            window.__vesselSent = [];
            resetRulesChoiceInteraction(); renderRulesChoice(true);
          }, choice);
          const cards = page.locator('[data-rules-reveal-index]');
          assert.equal(await cards.count(), choice.cardIds.length);
          const heading = await page.locator('#rulesChoiceHeading').innerText();
          const expected = {
            gummo: { fr: 'Gummo', en: 'Gummo', it: 'Gummo' },
            wish: { fr: 'Choisir la Manifestation à renvoyer', en: 'Choose the Manifestation to return', it: 'Scegli la Manifestazione da restituire' },
            pescojolero: { fr: 'Prendre une Manifestation dans votre Interzone', en: 'Take a Manifestation into your Interzone', it: 'Prendi una Manifestazione nella tua Interzona' },
          }[purpose][language];
          assert.equal(heading, expected);
          assert((await page.locator('#rulesChoiceText').innerText()).length > 25);
          const index = choice.cardIds.lastIndexOf('m3');
          assert(index >= 1);
          await page.mouse.move(viewport.width - 3, viewport.height - 3);
          await cards.locator('img').evaluateAll(images => Promise.all(images.map(img => img.decode().catch(() => {}))));
          if (language === 'fr') {
            await page.waitForTimeout(500);
            await page.screenshot({ path: path.join(out, `${purpose}-${viewport.width}.png`) });
          }
          await cards.nth(index).click();
          assert.deepEqual(await page.evaluate(() => window.__vesselSent), [{ type: 'resolve_rules_choice', choiceId: choice.id, option: String(index) }]);
          assert.equal(await cards.nth(0).isDisabled(), true);
          // A fresh server snapshot after reconnect must offer the same indices.
          await page.evaluate(choice => {
            latestState.rulesEngine.pendingChoice = structuredClone(choice);
            resetRulesChoiceInteraction(); renderRulesChoice(true); window.__vesselSent = [];
          }, choice);
          assert.equal(await cards.nth(index).isDisabled(), false);
          await cards.nth(index).click();
          assert.equal((await page.evaluate(() => window.__vesselSent))[0].option, String(index));
          cases.push({ viewport, language, purpose, actor: choice.playerId, heading, candidateCount: choice.cardIds.length, selectedIndex: index, passed: true });
        }
        assert.deepEqual(errors, []);
        await page.close();
      }
    }
  } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
  fs.writeFileSync(path.join(out, 'picker.json'), JSON.stringify({ engine: 'chromium', physicalDevice: false,
    summary: { configurations: 6, scenarios: cases.length, failed: 0 }, cases }, null, 2) + '\n');
  console.log(`Vessel picker: 6 configurations / ${cases.length} scenarios OK`);
})().catch(error => { console.error(error); process.exitCode = 1; });
