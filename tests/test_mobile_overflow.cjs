// Native touch scrolling in Chrome emulation; no physical-device certification.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const crypto = require('node:crypto');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..'), publicRoot = path.join(root, 'public');
const out = path.join(root, process.env.MOBILE_OVERFLOW_PROOF_DIR || 'reports/systematic-audit/mobile-overflow-followup');
const before = process.argv.includes('--before');
const tests = [];
async function check(name, fn) {
  try { await fn(); tests.push({ testId: name, status: 'pass' }); }
  catch (error) { tests.push({ testId: name, status: 'fail', detail: error.stack }); }
}
async function onScreen(page, locator) {
  const box = await locator.boundingBox();
  assert.ok(box, 'Element must be displayed');
  const viewport = await page.evaluate(() => ({ width: innerWidth, height: innerHeight }));
  assert.ok(box.x >= -1 && box.y >= -1 && box.x + box.width <= viewport.width + 1 &&
    box.y + box.height <= viewport.height + 1, `Outside viewport: ${JSON.stringify({ box, viewport })}`);
}
async function swipe(page, locator) {
  const box = await locator.boundingBox();
  const client = await page.context().newCDPSession(page);
  const x = box.x + box.width * .65, y = box.y + box.height * .85;
  const delta = Math.min(230, box.height * .65);
  try {
    await client.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] });
    for (let step = 1; step <= 12; step++) {
      await client.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x, y: y - delta * step / 12 }] });
      await page.waitForTimeout(16);
    }
    await client.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    await page.waitForTimeout(180);
  } finally { await client.detach(); }
}
(async () => {
  fs.mkdirSync(out, { recursive: true });
  const server = http.createServer((req, res) => {
    const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    const file = path.resolve(publicRoot, '.' + (pathname === '/' ? '/index.html' : pathname));
    if (!file.startsWith(publicRoot + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return res.writeHead(404).end();
    res.writeHead(200, { 'Content-Type': ({ '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.webp': 'image/webp' })[path.extname(file)] || 'application/octet-stream' });
    fs.createReadStream(file).pipe(res);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const configs = [
    { width: 1440, height: 1000, touch: false }, { width: 844, height: 390, touch: false },
    { width: 320, height: 568, touch: true }, { width: 390, height: 844, touch: true },
    { width: 568, height: 320, touch: true }, { width: 844, height: 390, touch: true },
    // Screenshot dimensions, plus one plausible CSS viewport at DPR 2.
    { width: 1280, height: 576, touch: true }, { width: 640, height: 288, touch: true, scale: 2 },
  ];
  try {
    for (const config of configs) for (const language of ['fr', 'en', 'it']) {
      const key = `${config.width}x${config.height}${config.scale ? '-dpr' + config.scale : ''}-${config.touch ? 'touch' : 'mouse'}-${language}`;
      const capture = language === 'fr' || language === 'it' && (config.width === 1280 || config.width === 640);
      const page = await browser.newPage({ viewport: { width: config.width, height: config.height },
        hasTouch: config.touch, isMobile: config.touch, deviceScaleFactor: config.scale || 1 });
      page.setDefaultTimeout(3500);
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      await page.addInitScript(language => localStorage.setItem('ko_language', language), language);
      await page.route('**/*', r => new URL(r.request().url()).hostname === '127.0.0.1' ? r.continue() : r.abort());
      await page.goto(`http://127.0.0.1:${server.address().port}/`);
      await page.waitForFunction(() => cardsById.size === 450 && typeof renderAll === 'function');
      await page.waitForFunction(() => document.querySelector('#deckBrowserValidateBtn').textContent === t('confirm'));
      // Portrait is a layout stress case: production asks players to rotate.
      await page.addStyleTag({ content: '.ub-rotate { display: none !important; }' });
      const fixture = await page.evaluate(({ language, touch }) => {
        currentLanguage = language; myPlayerId = 'p1'; isObserver = false; connectionRole = 'player';
        lastPointerType = touch ? 'touch' : 'mouse';
        for (const c of cardsById.values()) c.image = 'card-back.webp';
        const ids = [...cardsById.keys()].slice(0, 40);
        const zones = () => Object.fromEntries(ZONES.map(z => [z, { cards: [], count: 0, owners: {} }]));
        latestState = { ended: false, players: {
          p1: { id: 'p1', name: 'Alice', seat: 0, score: 50, zones: zones() },
          p2: { id: 'p2', name: 'Benoît', seat: 1, score: 50, zones: zones() },
        }, battlefield: [{ id: 'mobile-card', cardId: ids[0], ownerId: 'p1', controllerId: 'p1',
          x: 300, y: 500, rotation: 0, faceUp: true, counters: {}, fieldZone: 'confrontation' }],
          tokens: [], strokes: [], phaseTracker: { enabled: false, advanced: false, index: 0, turn: 2 },
          rulesEngine: { enabled: false, priorityPlayerId: 'p1', actionStack: [], ongoingEffects: [] } };
        latestState.players.p1.zones.deck = { cards: ids, count: 40, owners: Object.fromEntries(ids.map(id => [id, 'p1'])) };
        document.querySelector('#joinScreen').classList.add('hidden');
        document.querySelector('#gameScreen').classList.remove('hidden');
        renderAll(); window.__mobileSent = []; send = p => window.__mobileSent.push(p);
        return { ids, bottom: t('moveToDeckBottom'), confirm: t('confirm') };
      }, { language, touch: config.touch });
      await check(`${key}-deck-confirm-and-scroll`, async () => {
        await page.evaluate(cardId => {
          openPileBrowser('p1', 'deck');
          stagePileBrowserChoice('p1', 'deck', cardId, { kind: 'move', toOwnerId: 'p1', toZone: 'graveyard', label: t('graveyard') });
        }, fixture.ids[0]);
        if (capture) await page.screenshot({ path: path.join(out, `${key}-deck${before ? '-before' : ''}.png`) });
        const confirm = page.locator('#deckBrowserValidateBtn');
        assert.equal(await confirm.textContent(), fixture.confirm);
        await onScreen(page, confirm);
        assert.equal(await confirm.isEnabled(), true);
        const cards = page.locator('#deckBrowserCards');
        assert.ok(await cards.evaluate(el => el.scrollHeight > el.clientHeight));
        if (config.touch) await swipe(page, cards);
        else { await cards.hover(); await page.mouse.wheel(0, 400); await page.waitForTimeout(100); }
        assert.ok(await cards.evaluate(el => el.scrollTop > 0), 'Cards must scroll using a real gesture');
        await onScreen(page, confirm);
        if (config.touch) await confirm.tap(); else await confirm.click();
        assert.deepEqual(await page.evaluate(() => window.__mobileSent.filter(p => p.type === 'move_card')),
          [{ type: 'move_card', fromOwnerId: 'p1', fromZone: 'deck', toOwnerId: 'p1', toZone: 'graveyard', cardId: fixture.ids[0] }]);
      });
      await page.evaluate(() => { document.querySelector('#deckBrowserCloseBtn').click(); closeContextMenu(); window.__mobileSent = []; });
      await check(`${key}-field-menu-bottom-deck`, async () => {
        await page.evaluate(() => document.querySelector('.bf-card[data-item-id="mobile-card"]').dispatchEvent(
          new MouseEvent('contextmenu', { bubbles: true, cancelable: true, clientX: innerWidth - 8, clientY: innerHeight - 8 })));
        const menu = page.locator('.ctx-menu');
        if (capture) await page.screenshot({ path: path.join(out, `${key}-menu${before ? '-before' : ''}.png`) });
        await onScreen(page, menu);
        const scrollable = await menu.evaluate(el => el.scrollHeight > el.clientHeight + 1);
        if (scrollable) {
          assert.match(await menu.evaluate(el => getComputedStyle(el).overflowY), /auto|scroll/);
          if (config.touch) for (let i = 0; i < 5; i++) await swipe(page, menu);
          else { await menu.hover(); await page.mouse.wheel(0, 1200); await page.waitForTimeout(100); }
          assert.ok(await menu.evaluate(el => el.scrollTop > 0));
        }
        const bottom = menu.getByRole('button', { name: fixture.bottom, exact: true });
        await onScreen(page, bottom);
        if (capture && !before) await page.screenshot({ path: path.join(out, `${key}-menu-scrolled.png`) });
        if (config.touch) await bottom.tap(); else await bottom.click();
        assert.deepEqual(await page.evaluate(() => window.__mobileSent),
          [{ type: 'remove_battlefield_item', itemId: 'mobile-card', toOwnerId: 'p1', toZone: 'deck', position: 'bottom' }]);
      });
      await page.evaluate(() => closeContextMenu());
      await check(`${key}-menu-resize-clamps`, async () => {
        await page.evaluate(() => showContextMenu(innerWidth - 8, innerHeight - 8,
          [{ label: t('inspect'), onSelect() {} }, { label: t('moveToDeckBottom'), onSelect() {} }]));
        await page.setViewportSize({ width: 320, height: 320 });
        await page.waitForFunction(() => {
          const r = document.querySelector('.ctx-menu').getBoundingClientRect();
          return r.left >= 0 && r.top >= 0 && r.right <= innerWidth && r.bottom <= innerHeight;
        });
        await onScreen(page, page.locator('.ctx-menu'));
      });
      await check(`${key}-no-script-errors`, () => assert.deepEqual(errors, []));
      await page.close();
    }
    const proof = { schemaVersion: 1, beforeFix: before, engine: 'Chrome', version: browser.version(),
      finishedAt: new Date().toISOString(), physicalDeviceTested: false,
      summary: { executed: tests.length, passed: tests.filter(t => t.status === 'pass').length,
        failed: tests.filter(t => t.status !== 'pass').length }, tests,
      sourceHashes: Object.fromEntries(['public/style.css', 'public/js/drag-drop.js', 'public/js/players.js'].map(p =>
        [p, crypto.createHash('sha256').update(fs.readFileSync(path.join(root, p))).digest('hex')])),
      limits: ['Native touch gestures use Chrome device emulation, not a physical phone or Safari/Samsung Internet.',
        'The rotate-device overlay is hidden in the fixture to inspect portrait geometry; production still requests landscape play.',
        'The 1280x576 screenshot does not identify its CSS viewport or DPR. 1280x576 at DPR 1 and 640x288 at DPR 2 are two layout hypotheses, not an identified device.'] };
    fs.writeFileSync(path.join(out, before ? 'before.json' : 'browser.json'), JSON.stringify(proof, null, 2) + '\n');
    console.log(JSON.stringify(proof.summary));
    if (!before && proof.summary.failed) { console.error(tests.filter(t => t.status !== 'pass')); process.exitCode = 1; }
  } finally { await browser.close(); server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
})().catch(error => { console.error(error); process.exitCode = 1; });
