const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const crypto = require('node:crypto');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..'), publicRoot = path.join(root, 'public');
const out = path.join(root, process.env.MOBILE_MANUAL_PROOF_DIR || 'reports/systematic-audit/mobile-direct-ui-followup');
const tests = [];
async function check(testId, fn) {
  try { await fn(); tests.push({ testId, status: 'pass' }); }
  catch (error) { tests.push({ testId, status: 'fail', detail: error.stack }); }
}
async function drag(page, source, zone, cancel = false, capture = '', hold = false) {
  const box = await source.boundingBox(); assert.ok(box);
  const height = await page.evaluate(() => innerHeight);
  const x = box.x + box.width / 2, y = Math.min(height - 12, box.y + box.height * .3);
  const client = await page.context().newCDPSession(page);
  try {
    await client.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] });
    await client.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: x + 22, y: y - 22 }] });
    const target = page.locator(`.bf-card[data-item-id="${zone === 'interzone' ? 'iz-anchor' : 'will-anchor'}"]`);
    const rect = await target.boundingBox();
    assert.ok(rect.y >= 0);
    const tx = rect.x + rect.width / 2, ty = rect.y + rect.height * .35;
    for (let i = 1; i <= 8; i++) {
      await client.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: x + (tx-x)*i/8, y: y + (ty-y)*i/8 }] });
      await page.waitForTimeout(16);
    }
    if (hold) {
      await page.waitForTimeout(560);
      assert.equal(await target.evaluate(el => el.classList.contains('ub-stack-ready')), true);
    }
    if (capture) await page.screenshot({ path: path.join(out, capture) });
    await client.send('Input.dispatchTouchEvent', { type: cancel ? 'touchCancel' : 'touchEnd', touchPoints: [] });
    assert.equal(await page.locator('.drag-ghost').count(), 0);
    assert.equal(await page.locator('.ub-touch-zone-over, .ub-stack-ready').count(), 0);
    assert.equal(await page.locator('#ubManualDropTargets').count(), 0);
  } finally { await client.detach(); }
}
async function holdCard(page, locator) {
  const r = await locator.boundingBox(), client = await page.context().newCDPSession(page);
  try {
    await client.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: r.x+r.width/2, y: r.y+Math.min(r.height/2, 50) }] });
    await page.waitForTimeout(600);
    await page.locator('.ctx-menu').waitFor({ state: 'visible' });
    await client.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    assert.equal(await page.locator('.drag-ghost').count(), 0);
    assert.equal(await page.locator('#inspectPanel').isVisible(), false);
  } finally { await client.detach(); }
}
async function scrollCards(page) {
  const r = await page.locator('#deckBrowserCards').boundingBox(), client = await page.context().newCDPSession(page);
  const x = r.x+r.width*.6, y = r.y+r.height*.8;
  try {
    await client.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] });
    for (let i=1;i<=12;i++) {
      await client.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x, y: y-r.height*.6*i/12 }] });
      await page.waitForTimeout(16);
    }
    await client.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    await page.waitForTimeout(150);
  } finally { await client.detach(); }
  assert.ok(await page.locator('#deckBrowserCards').evaluate(el => el.scrollTop > 0));
  assert.equal(await page.locator('.ctx-menu, .drag-ghost').count(), 0);
}
(async () => {
  fs.mkdirSync(out, { recursive: true });
  const server = http.createServer((req, res) => {
    const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    const file = path.resolve(publicRoot, '.' + (pathname === '/' ? '/index.html' : pathname));
    if (!file.startsWith(publicRoot + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return res.writeHead(404).end();
    res.writeHead(200, { 'Content-Type': ({ '.html':'text/html', '.css':'text/css', '.js':'text/javascript', '.json':'application/json', '.webp':'image/webp' })[path.extname(file)] || 'application/octet-stream' });
    fs.createReadStream(file).pipe(res);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    for (const config of [{ width: 844, height: 390, touch: true }, { width: 640, height: 288, touch: true }, { width: 1440, height: 1000, touch: false }]) {
      for (const language of ['fr', 'en', 'it']) for (const seat of [0, 1]) {
        const key = `${config.width}-${language}-seat${seat}`;
        const page = await browser.newPage({ viewport: { width: config.width, height: config.height }, hasTouch: config.touch, isMobile: config.touch });
        page.setDefaultTimeout(4000);
        const errors = []; page.on('pageerror', e => errors.push(e.message));
        await page.addInitScript(language => localStorage.setItem('ko_language', language), language);
        await page.route('**/*', r => new URL(r.request().url()).hostname === '127.0.0.1' ? r.continue() : r.abort());
        await page.goto(`http://127.0.0.1:${server.address().port}/`);
        await page.waitForFunction(() => cardsById.size === 450 && document.querySelector('#deckBrowserFilter').oninput);
        await page.addStyleTag({ content: '* { animation: none !important; transition: none !important; }' });
        const info = await page.evaluate(({ seat, touch }) => {
          for (const c of cardsById.values()) c.image = 'card-back.webp';
          const man = [...cardsById.values()].find(c => c.type === 'manifestation').id;
          const will = [...cardsById.values()].find(c => c.type === 'persistent_will').id;
          const me = seat === 0 ? 'p1' : 'p2', opp = seat === 0 ? 'p2' : 'p1';
          const ids = [...cardsById.keys()].slice(0, 40);
          window.manualSetup = (mode = 'manual') => {
            closeContextMenu(); document.querySelector('#deckBrowserPanel').classList.add('hidden');
            if (!document.querySelector('#inspectPanel').classList.contains('hidden')) toggleInspectPanel();
            document.querySelector('#deckBrowserFilter').value = ''; pileBrowserStaged = new Map();
            myPlayerId = me; isObserver = mode === 'observer'; connectionRole = isObserver ? 'observer' : 'player';
            lastPointerType = touch ? 'touch' : 'mouse';
            const zones = () => Object.fromEntries(ZONES.map(z => [z, { cards: [], count: 0, owners: {} }]));
            const item = (id, cardId, x, y) => ({ id, cardId, ownerId: me, controllerId: me, x, y, faceUp: true, rotation: 0, counters: {} });
            latestState = { ended: false, players: { p1: { id: 'p1', name: 'Alice', seat: 0, score: 50, zones: zones() }, p2: { id: 'p2', name: 'Benoît', seat: 1, score: 50, zones: zones() } },
              battlefield: [item('source', man, 445, seat ? 525 : 800), item('iz-anchor', man, 445, seat ? 285 : 1064), item('will-anchor', will, 445, seat ? 45 : 1300)], tokens: [], strokes: [],
              phaseTracker: { enabled: false, advanced: false, index: 0, turn: 2 },
              rulesEngine: { enabled: mode === 'rules', priorityPlayerId: me, actionStack: [], ongoingEffects: [], firstManifestationComplete: true } };
            latestState.players[me].zones.deck = { cards: ids, count: ids.length, owners: Object.fromEntries(ids.map(cid => [cid, me])) };
            latestState.players[me].zones.hand = { cards: [man, will], count: 2, owners: { [man]: me, [will]: me } };
            document.querySelector('#joinScreen').classList.add('hidden'); document.querySelector('#gameScreen').classList.remove('hidden');
            renderAll(); window.manualSent = []; send = p => window.manualSent.push(p);
          };
          window.manualSetup();
          return { me, opp, man, will, ids, query: cardName(ids[15]), handLabel: cardDestinationLabel(me, 'hand') };
        }, { seat, touch: config.touch });
        await check(`${key}-deck-shortcut-filter-and-stage`, async () => {
          const shortcut = page.locator('.pile-search-shortcut');
          assert.equal(await shortcut.count(), 1);
          assert.equal(await shortcut.isVisible(), config.touch);
          if (config.touch) assert.ok((await shortcut.boundingBox()).height >= 44);
          if (config.touch) await shortcut.tap(); else await page.evaluate(me => searchPile(me, 'deck'), info.me);
          await page.locator('#deckBrowserPanel').waitFor({ state: 'visible' });
          const cardsBox = await page.locator('#deckBrowserCards').boundingBox();
          const actionsBox = await page.locator('.deck-browser-actions').boundingBox();
          assert.ok(actionsBox.x+actionsBox.width <= cardsBox.x);
          if (config.touch) await scrollCards(page);
          await page.locator('#deckBrowserFilter').fill(info.query.toUpperCase());
          assert.equal(await page.locator('#deckBrowserCards .db-card').count(), 1);
          if (config.touch) await holdCard(page, page.locator('#deckBrowserCards .db-card')); else await page.locator('#deckBrowserCards .db-card').click();
          const move = page.locator('.ctx-menu').getByRole('button', { name: info.handLabel, exact: true });
          if (config.touch) await move.tap(); else await move.click();
          assert.equal(await page.locator('#deckBrowserCards .db-card.staged').count(), 1);
          await page.locator('#deckBrowserFilter').fill('zzz-impossible-card');
          assert.equal(await page.locator('#deckBrowserCards .db-card').count(), 0);
          assert.equal(await page.locator('.deck-browser-empty').isVisible(), true);
          assert.equal(await page.locator('#deckBrowserValidateBtn').isEnabled(), true);
          await page.locator('#deckBrowserFilter').fill('');
          assert.equal(await page.locator('#deckBrowserCards .db-card').count(), 40);
          assert.equal(await page.locator('#deckBrowserCards .db-card.staged').count(), 1);
          if (language === 'it' && seat === 0) await page.screenshot({ path: path.join(out, `${key}-search.png`) });
          await page.locator('#deckBrowserFilter').fill(info.query);
          if (language === 'it' && seat === 0) await page.screenshot({ path: path.join(out, `${key}-filtered.png`) });
          if (config.touch) await page.locator('#deckBrowserValidateBtn').tap(); else await page.locator('#deckBrowserValidateBtn').click();
          assert.deepEqual(await page.evaluate(() => manualSent.filter(p => p.type === 'move_card')), [{ type: 'move_card', fromOwnerId: info.me, fromZone: 'deck', toOwnerId: info.me, toZone: 'hand', cardId: info.ids[15] }]);
          assert.ok((await page.evaluate(() => manualSent)).some(p => p.type === 'search_zone'));
          if (config.touch) await shortcut.tap(); else await page.evaluate(me => searchPile(me, 'deck'), info.me);
          assert.equal(await page.locator('#deckBrowserFilter').inputValue(), '');
          assert.equal(await page.locator('#deckBrowserCards .db-card.staged').count(), 0);
          await page.locator('#deckBrowserCloseBtn').click();
        });
        if (config.touch) {
          for (const zone of ['interzone', 'will']) for (const sourceKind of ['battlefield', 'hand']) {
            await check(`${key}-${sourceKind}-to-${zone}`, async () => {
              await page.evaluate(() => manualSetup());
              const cid = zone === 'will' ? info.will : info.man;
              const source = sourceKind === 'battlefield' ? page.locator('.bf-card[data-item-id="source"]') : page.locator(`[data-hand-card="${cid}"]`);
              await drag(page, source, zone);
              const messages = await page.evaluate(() => manualSent.filter(p => ['place_card', 'move_battlefield_item'].includes(p.type)));
              assert.equal(messages.length, 1);
              const message = messages[0];
              assert.equal(message.stackOnId, undefined);
              assert.equal(message.type, sourceKind === 'battlefield' ? 'move_battlefield_item' : 'place_card');
              if (sourceKind === 'battlefield') assert.equal(message.unstack, true);
              const inferred = await page.evaluate(message => uiBeta.fieldZone({ id: 'landed', ownerId: myPlayerId, cardId: latestState.battlefield[0].cardId, x: message.x, y: message.y }), message);
              assert.equal(inferred, zone);
            });
          }
          for (const zone of ['interzone', 'will']) await check(`${key}-hold-to-stack-in-${zone}`, async () => {
            await page.evaluate(() => manualSetup());
            await drag(page, page.locator('.bf-card[data-item-id="source"]'), zone, false,
              language === 'it' && seat === 0 && zone === 'interzone' ? `${key}-hold-stack.png` : '', true);
            const messages = await page.evaluate(() => manualSent);
            assert.equal(messages.length, 1);
            assert.equal(messages[0].stackOnId, zone === 'interzone' ? 'iz-anchor' : 'will-anchor');
          });
          await check(`${key}-tap-card-inspects-without-options`, async () => {
            await page.evaluate(me => { manualSetup(); searchPile(me, 'deck'); }, info.me);
            await page.locator('#deckBrowserFilter').fill(info.query);
            await page.locator('#deckBrowserCards .db-card').tap();
            await page.locator('#inspectPanel').waitFor({ state: 'visible' });
            assert.equal(await page.locator('.ctx-menu').count(), 0);
            await page.locator('#inspectPanel .inspect-x-btn').tap();
            assert.equal(await page.locator('#inspectPanel').isVisible(), false);
          });
          await check(`${key}-cancel-cleans-targets`, async () => {
            await page.evaluate(() => manualSetup());
            await drag(page, page.locator('.bf-card[data-item-id="source"]'), 'interzone', true);
            assert.deepEqual(await page.evaluate(() => manualSent), []);
          });
        }
        await check(`${key}-direct-drop-follows-input-method`, async () => {
          const messages = await page.evaluate(() => {
            manualSetup();
            const source = document.querySelector('.bf-card[data-item-id="source"]');
            const anchor = document.querySelector('.bf-card[data-item-id="iz-anchor"]').getBoundingClientRect();
            const ctx = { kind: 'battlefield', itemId: 'source' };
            const ghost = buildDragGhost(ctx, source);
            try { resolveDrop(ctx, anchor.x + anchor.width / 2, anchor.y + anchor.height * .25); }
            finally { removeGhost(ghost); }
            return manualSent;
          });
          assert.equal(messages.length, 1);
          if (config.touch) { assert.equal(messages[0].stackOnId, undefined); assert.equal(messages[0].unstack, true); }
          else assert.equal(messages[0].stackOnId, 'iz-anchor');
        });
        await check(`${key}-no-shortcuts-in-rules-or-observer-mode`, async () => {
          for (const mode of ['rules', 'observer']) {
            await page.evaluate(mode => manualSetup(mode), mode);
            assert.equal(await page.locator('.pile-search-shortcut').count(), 0);
            assert.equal(await page.locator('#ubManualDropTargets').count(), 0);
          }
        });
        await check(`${key}-no-script-errors`, () => assert.deepEqual(errors, []));
        await page.close();
      }
    }
    const proof = { finishedAt: new Date().toISOString(), engine: 'Chrome', version: browser.version(), physicalDevice: false,
      summary: { executed: tests.length, passed: tests.filter(t => t.status === 'pass').length, failed: tests.filter(t => t.status !== 'pass').length }, tests,
      sourceHashes: Object.fromEntries(['public/ui-beta.js', 'public/ui-beta.css', 'public/js/drag-drop.js', 'public/js/players.js', 'public/js/zones.js', 'public/i18n.js', 'public/index.html', 'public/style.css'].map(p => [p, crypto.createHash('sha256').update(fs.readFileSync(path.join(root, p))).digest('hex')])),
      limits: ['Chrome touch emulation; not physical-device, Safari or Samsung Internet certification. Local card-back artwork. Server responses are not simulated as full card-rule matches.'] };
    fs.writeFileSync(path.join(out, 'browser.json'), JSON.stringify(proof, null, 2) + '\n');
    console.log(JSON.stringify(proof.summary));
    if (proof.summary.failed) { console.error(tests.filter(t => t.status !== 'pass')); process.exitCode = 1; }
  } finally { await browser.close(); server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
})().catch(e => { console.error(e); process.exitCode = 1; });
