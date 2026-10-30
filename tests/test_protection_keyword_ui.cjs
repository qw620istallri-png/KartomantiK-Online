const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),http=require('node:http'),crypto=require('node:crypto');
const {execFileSync}=require('node:child_process'),{chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),pub=path.join(root,'public'),out=path.join(root,'reports/systematic-audit/protection-keywords-followup');
const fixtures=JSON.parse(execFileSync('python',['tools/protection_keyword_ui_fixtures.py'],{cwd:root,encoding:'utf8',maxBuffer:32*1024*1024}));
const files=['server/game/power.py','server/game/board.py','server/game/stack.py','server/game/view.py','server/game/triggers.py',
 'tests/test_protection_keyword_family.py','tools/protection_keyword_ui_fixtures.py','tests/test_protection_keyword_ui.cjs','audit/protection-keywords.json',
 'public/card-abilities.json','public/js/rules-actions.js','public/js/board.js','public/app.js','public/index.html','public/ui-beta.js','public/style.css'];
const hashes=()=>Object.fromEntries(files.map(f=>[f,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,f))).digest('hex')]));
const sourceHashes=hashes(),tests=[],mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json'};
(async()=>{
 const server=http.createServer((req,res)=>{const u=new URL(req.url,'http://localhost'),file=path.resolve(pub,'.'+(u.pathname==='/'?'/index.html':decodeURIComponent(u.pathname)));
  if(!file.startsWith(pub+path.sep)||!fs.existsSync(file)||fs.statSync(file).isDirectory())return res.writeHead(404).end();
  res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream'});fs.createReadStream(file).pipe(res);});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({channel:'chrome',headless:true});
 try{for(const viewport of [{width:1440,height:1000},{width:844,height:390}]){
  const page=await browser.newPage({viewport,hasTouch:viewport.width<1000,isMobile:viewport.width<1000}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',r=>new URL(r.request().url()).hostname==='127.0.0.1'?r.continue():r.abort());
  await page.goto(`http://127.0.0.1:${server.address().port}/`);await page.waitForFunction(()=>cardsById.size===450&&typeof buildRulesActionDraft==='function');
  await page.evaluate(()=>{for(const c of cardsById.values()){c.image='card-back.webp';c.translations={};}
   const probe=cardsById.values().next().value;for(const [id,power,type] of [['m3',3,'manifestation'],['m4',4,'manifestation'],['pw3',null,'persistent_will']])cardsById.set(id,{...probe,id,name:id,power,type,points:10});
   document.querySelector('#joinScreen').classList.add('hidden');document.querySelector('#gameScreen').classList.remove('hidden');isObserver=false;});
  for(const frame of fixtures.frames){const testId=viewport.width+'-'+frame.id;
   try{const actual=await page.evaluate(frame=>{myPlayerId=frame.viewer;latestState=frame.state;lastBoardLayout=null;renderBattlefield();
    const item=latestState.battlefield.find(i=>i.id==='target'),card=document.querySelector('.bf-card[data-item-id="target"]');
    if(!card)throw Error('Missing target card');const draft=buildRulesActionDraft(frame.source,frame.ability);
    return {candidate:draft.structuredTargets.some(t=>frame.vessel?t.zone==='receptacle'&&t.containerId==='p1':t.id==='target'),
     inactive:!!item.effectsInactive,support:!!item.canEnterSupport,power:item.effectivePower,
     badge:!!card.querySelector('.rules-effect-badge'),title:card.querySelector('.rules-effect-badge')?.title||'',
     powerBadges:[...card.querySelectorAll('.bf-counter-effect')].map(e=>e.textContent)};},frame);
    assert.equal(actual.candidate,frame.candidateExpected);
    if(!frame.vessel){assert.equal(actual.inactive,frame.inactiveExpected);assert.equal(actual.support,frame.supportExpected);assert.equal(actual.power,frame.powerExpected);
     assert.equal(actual.badge,frame.modifierExpected);if(actual.badge)assert.ok(actual.title.length>0);
     if(frame.key==='jaw')assert.deepEqual(actual.powerBadges,frame.powerExpected===2?['-2']:[]);}
    assert.deepEqual(errors,[]);tests.push({testId,status:'pass'});
   }catch(e){tests.push({testId,status:'fail',detail:e.stack});}}
  await page.close();}
 }finally{await browser.close();await new Promise(r=>server.close(r));}
 assert.deepEqual(hashes(),sourceHashes);const proof={sourceHashes,summary:{executed:tests.length,passed:tests.filter(t=>t.status==='pass').length,failed:tests.filter(t=>t.status!=='pass').length},tests,
  limits:['Twelve selected cards, active/Cleanse/blanked-source fixtures, both viewers, PC and mobile landscape Chrome.',
   'Production serialization and real candidate filters/DOM markers; controlled fixtures and local artwork, not complete matches or physical devices.']};
 fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'browser.json'),JSON.stringify(proof,null,2)+'\n');console.log(JSON.stringify(proof.summary));assert.equal(proof.summary.failed,0);
})().catch(e=>{console.error(e);process.exitCode=1;});
