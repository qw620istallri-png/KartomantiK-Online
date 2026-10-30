// Real public serialization + browser render functions; local art, no physical-device claim.
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), http = require('node:http');
const { execFileSync } = require('node:child_process');
const { chromium } = require('playwright');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..'), publicRoot = path.join(root, 'public');
const out = path.join(root, 'reports/systematic-audit/continuous-power-followup');
const fixtures = JSON.parse(execFileSync('python', ['tools/continuous_power_ui_fixtures.py'], { cwd: root, encoding: 'utf8', maxBuffer: 32*1024*1024 }));
const tests = [];
const hashedFiles = ['server/game/power.py','tests/test_continuous_power_family.py','tools/continuous_power_ui_fixtures.py',
  'audit/continuous-power-family.json','public/js/board.js','public/app.js','public/index.html','public/ui-beta.js','public/style.css'];
const hashSources = () => Object.fromEntries(hashedFiles.map(file => [file,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,file))).digest('hex')]));
const sourceHashes = hashSources();
const mime = { '.html':'text/html', '.js':'text/javascript', '.css':'text/css', '.json':'application/json', '.webp':'image/webp' };
(async () => {
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://localhost');
    const file = path.resolve(publicRoot, '.' + (url.pathname === '/' ? '/index.html' : decodeURIComponent(url.pathname)));
    if (!file.startsWith(publicRoot + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return res.writeHead(404).end();
    res.writeHead(200, {'Content-Type': mime[path.extname(file)] || 'application/octet-stream'});
    fs.createReadStream(file).pipe(res);
  });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const browser = await chromium.launch({channel:'chrome',headless:true});
  try {
    for (const viewport of [{width:1440,height:1000},{width:844,height:390}]) {
      const page = await browser.newPage({viewport,hasTouch:viewport.width<1000,isMobile:viewport.width<1000});
      const errors = []; page.on('pageerror', e => errors.push(e.message));
      await page.route('**/*', route => new URL(route.request().url()).hostname === '127.0.0.1' ? route.continue() : route.abort());
      await page.goto(`http://127.0.0.1:${server.address().port}/`);
      await page.waitForFunction(() => cardsById.size === 450 && typeof renderBattlefield === 'function');
      await page.evaluate(probe => {
        for (const card of cardsById.values()) {card.image='card-back.webp';card.translations={};}
        cardsById.set(probe.id,probe);
        for (const [id,power,type] of [['m2',2,'manifestation'],['m3',3,'manifestation'],['m4',4,'manifestation'],['w2',null,'ephemeral_will'],['pw3',null,'persistent_will']]) {
          cardsById.set(id,{...probe,id,name:id,power,type});
        }
        document.querySelector('#joinScreen').classList.add('hidden');
        document.querySelector('#gameScreen').classList.remove('hidden');
        isObserver=false;
      },fixtures.probe);
      for (const frame of fixtures.frames) {
        const testId = `${viewport.width}-${frame.id}`;
        try {
          const result = await page.evaluate(frame => {
            myPlayerId=frame.viewer; latestState=frame.state; lastBoardLayout=null;
            renderBattlefield();
            const card=document.querySelector(`.bf-card[data-item-id="${frame.targetId}"]`);
            if(!card)throw new Error('Target missing from board');
            const counters=[...card.querySelectorAll('.counters .bf-counter-effect')];
            return {texts:counters.map(n=>n.textContent),titles:counters.map(n=>n.title),
              statePower:latestState.battlefield.find(i=>i.id===frame.targetId).effectivePower};
          },frame);
          const delta=frame.expectedPower-frame.printedPower-frame.explicitPower;
          assert.equal(result.statePower,frame.expectedPower);
          assert.deepEqual(result.texts,delta?[`${delta>0?'+':''}${delta}`]:[]);
          assert.ok(result.titles.every(Boolean));
          assert.deepEqual(errors,[]);
          tests.push({testId,status:'pass'});
        } catch(e) {tests.push({testId,status:'fail',detail:e.stack});}
      }
      await page.close();
    }
  } finally {await browser.close();await new Promise(r=>server.close(r));}
  assert.deepEqual(hashSources(),sourceHashes,'Scoped sources changed during rendering checks');
  const proof={sourceHashes,fixtureSha256:crypto.createHash('sha256').update(JSON.stringify(fixtures)).digest('hex'),summary:{executed:tests.length,passed:tests.filter(t=>t.status==='pass').length,failed:tests.filter(t=>t.status!=='pass').length},
    tests,limits:['Production serialized states with controlled fixtures; local artwork.','PC Chrome and mobile landscape/touch emulation, no physical phone or Safari.','DOM modifier rendering and both player views; drag, artwork and animation layout are outside this gate.']};
  fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'browser.json'),JSON.stringify(proof,null,2)+'\n');
  console.log(JSON.stringify(proof.summary));assert.equal(proof.summary.failed,0);
})().catch(e=>{console.error(e);process.exitCode=1;});
