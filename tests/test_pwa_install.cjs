const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const http = require('node:http');
const crypto = require('node:crypto');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const out = path.join(root, process.env.PWA_PROOF_DIR || 'reports/systematic-audit/mobile-native-install-followup');
fs.mkdirSync(out, { recursive: true });
const before = process.argv.includes('--before');
const android = 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/130.0.0.0 Mobile Safari/537.36';
const samsung = 'Mozilla/5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 SamsungBrowser/29.0 Chrome/130.0.0.0 Mobile Safari/537.36';
const iphone = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1';
const desktop = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36';
const tests = [];
function element() {
  const classes = new Set(['hidden']);
  return { textContent: '', innerHTML: '', classList: { add: x => classes.add(x), remove: x => classes.delete(x), contains: x => classes.has(x), toggle: (x, hidden) => hidden ? classes.add(x) : classes.delete(x) }, addEventListener() {}, focus() {} };
}
function fixture(ua, lang = 'fr', installed = false) {
  const nodes = { '#installAppBtn': element(), '#installGuide': element() };
  const children = { h2: element(), ol: element(), '.install-guide-note': element(), '[data-install-close]': element(), '[data-install-native]': element() };
  nodes['#installGuide'].querySelector = key => children[key];
  const listeners = {};
  const c = vm.createContext({ console, URLSearchParams, Promise, localStorage: { getItem: () => lang, setItem() {} }, navigator: { userAgent: ua, platform: '', maxTouchPoints: 0 }, document: { addEventListener() {} },
    $: key => nodes[key], esc: x => String(x).replaceAll('&', '&amp;').replaceAll('<', '&lt;'),
    window: { matchMedia: () => ({ matches: installed }), addEventListener: (type, fn) => (listeners[type] ||= []).push(fn) } });
  vm.runInContext(fs.readFileSync(path.join(root, 'public/i18n.js'), 'utf8'), c);
  c.t = key => vm.runInContext(`ui[${JSON.stringify(lang)}][${JSON.stringify(key)}] || ui.en[${JSON.stringify(key)}]`, c);
  c.rulesText = (key, values) => c.t(key).replace(/\{(\w+)\}/g, (_, name) => values[name]);
  vm.runInContext(fs.readFileSync(path.join(root, 'public/js/pwa.js'), 'utf8'), c);
  return { c, nodes, children, emit: (type, event = {}) => (listeners[type] || []).forEach(fn => fn(event)) };
}
async function test(name, fn) { try { await fn(); tests.push({ testId: name, status: 'pass' }); } catch (error) { tests.push({ testId: name, status: 'fail', detail: error.stack }); } }
(async () => {
  for (const [name, ua] of [['chrome', android], ['samsung', samsung]]) {
    await test(`${name}-preserves-browser-promotion-and-direct-install`, async () => {
      const f = fixture(ua); let cancelled = 0, prompted = 0;
      f.emit('beforeinstallprompt', { preventDefault() { cancelled++; }, prompt() { prompted++; }, userChoice: new Promise(() => {}) });
      f.c.initAppInstall();
      assert.equal(cancelled, 0, 'Do not suppress the browser installation promotion');
      assert.equal(prompted, 0, 'The native prompt requires a user gesture');
      f.c.installApp();
      assert.equal(prompted, 1, 'Call prompt synchronously from the install action');
    });
    await test(`${name}-native-action-appears-in-already-open-guide`, async () => {
      const f = fixture(ua); f.c.initAppInstall(); await f.c.installApp();
      let prompted = 0;
      f.emit('beforeinstallprompt', { preventDefault() {}, prompt() { prompted++; }, userChoice: new Promise(() => {}) });
      assert.equal(f.children['[data-install-native]'].classList.contains('hidden'), false);
      assert.equal(f.children.ol.classList.contains('hidden'), true);
      assert.equal(prompted, 0);
      f.c.installApp();
      assert.equal(prompted, 1);
      assert.equal(f.nodes['#installGuide'].classList.contains('hidden'), true);
    });
  }
  await test('browser-dismissal-clears-consumed-native-event', async () => {
    const f = fixture(android); f.c.initAppInstall(); let finish, prompted = 0;
    f.emit('beforeinstallprompt', { preventDefault() {}, prompt() { prompted++; }, userChoice: new Promise(resolve => { finish = resolve; }) });
    finish({ outcome: 'dismissed' }); await Promise.resolve();
    await f.c.installApp();
    assert.equal(prompted, 0);
    assert.equal(f.nodes['#installGuide'].classList.contains('hidden'), false);
  });
  for (const lang of ['en', 'fr', 'it']) await test(`samsung-fallback-stays-in-samsung-${lang}`, async () => {
    const f = fixture(samsung, lang); f.c.initAppInstall(); await f.c.installApp();
    assert.match(f.children.h2.textContent, /Samsung Internet/);
    assert.match(f.children.ol.innerHTML, /Samsung Internet/);
    assert.equal(f.children['.install-guide-note'].textContent.includes('Chrome'), false);
    assert.equal(f.children['[data-install-native]'].classList.contains('hidden'), true);
  });
  await test('appinstalled-closes-open-guide', async () => {
    const f = fixture(samsung); f.c.initAppInstall(); await f.c.installApp(); f.emit('appinstalled');
    assert.equal(f.nodes['#installGuide'].classList.contains('hidden'), true);
    assert.equal(f.nodes['#installAppBtn'].classList.contains('hidden'), true);
  });
  await test('installation-before-init-needs-no-dom-helper', () => {
    const f = fixture(samsung), select = f.c.$;
    delete f.c.$;
    f.emit('appinstalled');
    f.c.$ = select;
    f.c.initAppInstall();
    assert.equal(f.nodes['#installAppBtn'].classList.contains('hidden'), true);
  });
  for (const lang of ['en', 'fr', 'it']) await test(`android-no-native-event-${lang}`, async () => {
    const f = fixture(android, lang); f.c.initAppInstall();
    assert.equal(f.nodes['#installAppBtn'].classList.contains('hidden'), false);
    await f.c.installApp();
    assert.equal(f.nodes['#installGuide'].classList.contains('hidden'), false);
    assert.match(f.children.h2.textContent, /Android/);
    assert.equal(f.children.ol.innerHTML.includes('Safari'), false);
  });
  await test('early-native-event-retained-before-init', async () => {
    const f = fixture(desktop); let calls = 0;
    f.emit('beforeinstallprompt', { preventDefault() {}, prompt: async () => { calls++; }, userChoice: Promise.resolve({ outcome: 'dismissed' }) });
    f.c.initAppInstall();
    assert.equal(f.nodes['#installAppBtn'].classList.contains('hidden'), false);
    await f.c.installApp(); assert.equal(calls, 1);
  });
  await test('late-native-prompt-used-once', async () => {
    const f = fixture(android); f.c.initAppInstall(); let calls = 0;
    f.emit('beforeinstallprompt', { preventDefault() {}, prompt: async () => { calls++; }, userChoice: Promise.resolve({ outcome: 'dismissed' }) });
    await f.c.installApp(); await f.c.installApp(); assert.equal(calls, 1);
    assert.equal(f.nodes['#installGuide'].classList.contains('hidden'), false);
  });
  await test('failed-native-prompt-falls-back', async () => {
    const f = fixture(android); f.c.initAppInstall();
    f.emit('beforeinstallprompt', { preventDefault() {}, prompt() { throw Error('not available'); }, userChoice: Promise.resolve({ outcome: 'dismissed' }) });
    await f.c.installApp(); assert.equal(f.nodes['#installGuide'].classList.contains('hidden'), false);
  });
  for (const ua of [android, iphone, desktop]) await test(`installed-hides-${ua.includes('Android') ? 'android' : ua.includes('iPhone') ? 'ios' : 'desktop'}`, () => {
    const f = fixture(ua, 'fr', true); f.c.initAppInstall(); assert.equal(f.nodes['#installAppBtn'].classList.contains('hidden'), true);
  });
  await test('appinstalled-event-hides-mobile-entry', () => {
    const f = fixture(android); f.c.initAppInstall(); f.emit('appinstalled');
    assert.equal(f.nodes['#installAppBtn'].classList.contains('hidden'), true);
  });
  await test('ios-guide-and-desktop-no-false-entry', async () => {
    const f = fixture(iphone); f.c.initAppInstall(); await f.c.installApp(); assert.match(f.children.h2.textContent, /iPhone/);
    const d = fixture(desktop); d.c.initAppInstall(); assert.equal(d.nodes['#installAppBtn'].classList.contains('hidden'), true);
  });
  if (!process.argv.includes('--unit-only')) {
  const publicRoot = path.join(root, 'public');
  const server = http.createServer((req, res) => {
    const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    const file = path.resolve(publicRoot, '.' + (pathname === '/' ? '/index.html' : pathname));
    if (!file.startsWith(publicRoot + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return res.writeHead(404).end();
    const mime = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json', '.woff2': 'font/woff2' };
    res.writeHead(200, { 'Content-Type': mime[path.extname(file)] || 'application/octet-stream' }); fs.createReadStream(file).pipe(res);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    for (const [name, ua, viewport] of [['android', android, { width: 390, height: 844 }], ['samsung', samsung, { width: 390, height: 844 }], ['iphone', iphone, { width: 390, height: 844 }], ['desktop', desktop, { width: 1440, height: 1000 }]]) {
      const page = await browser.newPage({ userAgent: ua, viewport });
      await page.addInitScript(() => { localStorage.setItem('ko_lang', 'fr'); window.addEventListener('beforeinstallprompt', e => { if (e.isTrusted) e.stopImmediatePropagation(); }); });
      await page.route('**/*', route => new URL(route.request().url()).hostname === '127.0.0.1' ? route.continue() : route.abort());
      await page.goto(`http://127.0.0.1:${server.address().port}/`);
      await page.waitForFunction(() => document.querySelector('#installAppBtn').textContent.length > 0);
      await page.screenshot({ path: path.join(out, `${name}-home${before ? '-before' : ''}.png`), fullPage: true });
      if (!before) await test(`browser-${name}-entry`, async () => {
        if (name === 'desktop') return assert.equal(await page.locator('#installAppBtn').isVisible(), false);
        await page.locator('#installAppBtn').click(); await page.locator('#installGuide').waitFor({ state: 'visible' });
        assert.match(await page.locator('#installGuideTitle').textContent(), name === 'samsung' ? /Samsung Internet/ : name === 'android' ? /Android/ : /iPhone/);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
        await page.screenshot({ path: path.join(out, `${name}-guide.png`), fullPage: true });
        if (name === 'android' || name === 'samsung') {
          await page.evaluate(() => {
            const event = new Event('beforeinstallprompt', { cancelable: true });
            event.userChoice = new Promise(() => {});
            event.prompt = () => { window.installPromptCalls = (window.installPromptCalls || 0) + 1; window.installHadGesture = navigator.userActivation.isActive; };
            window.dispatchEvent(event);
            if (event.defaultPrevented) throw Error('Browser promotion was suppressed');
          });
          await page.locator('[data-install-native]').waitFor({ state: 'visible' });
          await page.screenshot({ path: path.join(out, `${name}-native-ready.png`), fullPage: true });
          await page.locator('[data-install-native]').click();
          assert.equal(await page.evaluate(() => window.installPromptCalls), 1);
          assert.equal(await page.evaluate(() => window.installHadGesture), true);
          assert.equal(await page.locator('#installGuide').isVisible(), false);
          await page.locator('#installAppBtn').click();
        }
        await page.locator('[data-install-close]').click(); assert.equal(await page.locator('#installGuide').isVisible(), false);
      });
      await page.close();
    }
  } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
  }
  const proof = { beforeFix: before, tests, summary: { executed: tests.length, passed: tests.filter(t => t.status === 'pass').length, failed: tests.filter(t => t.status !== 'pass').length }, physicalDeviceTested: false, limits: ['Native install events are simulated; rendering uses Chrome with Android/Samsung/iOS user agents, not physical devices, Samsung Internet or Safari.'] };
  proof.sourceHashes = Object.fromEntries(['public/js/pwa.js', 'public/i18n.js', 'public/app.js', 'public/index.html', 'public/sw.js', 'public/style.css'].map(file => [file, crypto.createHash('sha256').update(fs.readFileSync(path.join(root, file))).digest('hex')]));
  fs.writeFileSync(path.join(out, before ? 'before.json' : 'ui.json'), JSON.stringify(proof, null, 2));
  console.log(JSON.stringify(proof.summary));
  if (!before && proof.summary.failed) { console.error(tests.filter(t => t.status !== 'pass')); process.exitCode = 1; }
})().catch(error => { console.error(error); process.exitCode = 1; });
