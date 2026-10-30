const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),http=require('node:http'),crypto=require('node:crypto');
const {execFileSync}=require('node:child_process');const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),pub=path.join(root,'public'),out=path.join(root,'reports/systematic-audit/stack-interactions-followup');
const fixtures=JSON.parse(execFileSync('python',['tools/stack_interaction_ui_fixtures.py'],{cwd:root,encoding:'utf8',maxBuffer:32*1024*1024}));
const files=['server/game/actions.py','server/game/chain.py','server/game/stack.py','server/game/triggers.py','server/game/zones.py','server/game/priority.py','server/game/effects/signature.py','tests/test_stack_interaction_family.py',
 'tools/stack_interaction_ui_fixtures.py','tests/test_stack_interaction_ui.cjs','audit/stack-interactions.json','public/js/rules-actions.js','public/index.html'];
const hashes=()=>Object.fromEntries(files.map(f=>[f,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,f))).digest('hex')]));
const sourceHashes=hashes(),tests=[];const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json'};
(async()=>{
 const server=http.createServer((req,res)=>{const u=new URL(req.url,'http://localhost');const file=path.resolve(pub,'.'+(u.pathname==='/'?'/index.html':decodeURIComponent(u.pathname)));
  if(!file.startsWith(pub+path.sep)||!fs.existsSync(file)||fs.statSync(file).isDirectory())return res.writeHead(404).end();
  res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream'});fs.createReadStream(file).pipe(res);});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({channel:'chrome',headless:true});
 try{for(const viewport of [{width:1440,height:1000},{width:844,height:390}]){
  const page=await browser.newPage({viewport,hasTouch:viewport.width<1000,isMobile:viewport.width<1000});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>new URL(route.request().url()).hostname==='127.0.0.1'?route.continue():route.abort());
  await page.goto(`http://127.0.0.1:${server.address().port}/`);await page.waitForFunction(()=>cardsById.size===450&&typeof buildRulesActionDraft==='function');
  await page.evaluate(cards=>{for(const card of cards)cardsById.set(card.id,card);myPlayerId='p1';isObserver=false;},fixtures.cards);
  for(const frame of fixtures.frames){const testId=viewport.width+'-'+frame.id;
   try{const actual=await page.evaluate(frame=>{latestState=frame.state;const draft=buildRulesActionDraft(frame.source,frame.ability);
    return [...new Set(draft.structuredTargets.filter(t=>['stack_action','stack_effect','stack_item'].includes(t.kind)&&Number(t.targetGroupIndex||0)===0).map(t=>t.actionId))].sort();},frame);
    assert.deepEqual(actual,frame.expectedStackIds,testId);assert.deepEqual(errors,[]);tests.push({testId,status:'pass'});
   }catch(e){tests.push({testId,status:'fail',detail:e.stack});}}
  await page.close();}
 }finally{await browser.close();await new Promise(r=>server.close(r));}
 assert.deepEqual(hashes(),sourceHashes);
 const proof={sourceHashes,summary:{executed:tests.length,passed:tests.filter(t=>t.status==='pass').length,failed:tests.filter(t=>t.status!=='pass').length},tests,
  limits:['Client candidate filters for ten response cards, five controlled target states including copied Wills, PC and mobile landscape Chrome.','Synthetic pending originals and local artwork; no full game or physical device certification.','Timing, ownership and exact effect outcomes are checked by the associated Python and socket journeys, not this candidate-filter gate.']};
 fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'browser.json'),JSON.stringify(proof,null,2)+'\n');console.log(JSON.stringify(proof.summary));assert.equal(proof.summary.failed,0);
})().catch(e=>{console.error(e);process.exitCode=1;});
