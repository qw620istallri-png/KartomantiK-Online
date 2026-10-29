// Real app sockets and server handlers; loopback fixture resets only initial zones.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {spawn}=require('node:child_process');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),out=path.join(root,'reports/systematic-audit/manual-motion-followup');
fs.mkdirSync(out,{recursive:true});
const tests=[];
async function check(id,fn){if(process.env.MOTION_CASE&&!id.includes(process.env.MOTION_CASE))return;try{await fn();tests.push({testId:id,status:'pass'});}catch(e){tests.push({testId:id,status:'fail',detail:e.stack});console.log(e.message);}console.log(id,tests.at(-1).status);}
async function drag(page,source,target,touch){
 const a=await source.boundingBox(),b=await target.boundingBox();assert.ok(a&&b);
 const x=a.x+a.width/2,y=Math.min(page.viewportSize().height-12,a.y+a.height*.3),tx=b.x+b.width/2,ty=b.y+b.height*.45;
 const hit=await page.evaluate(({x,y})=>{const el=document.elementFromPoint(x,y);return {id:el?.closest('.bf-card,[data-hand-card]')?.dataset.itemId||el?.closest('[data-hand-card]')?.dataset.handCard,html:el?.outerHTML.slice(0,450)};},{x,y});
 assert.ok(hit.id,'Card origin occluded: '+JSON.stringify({a,b,x,y,hit}));
 if(!touch){await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(tx,ty,{steps:14});await page.mouse.up();return;}
 const c=await page.context().newCDPSession(page);
 try{await c.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y}]});
 for(let i=1;i<=14;i++){await c.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:x+(tx-x)*i/14,y:y+(ty-y)*i/14}]});await page.waitForTimeout(16);}
 await c.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});}finally{await c.detach();}
}
(async()=>{
 const child=spawn('python',['tools/manual_motion_server.py'],{cwd:root,env:{...process.env,PYTHONIOENCODING:'utf-8'},stdio:['ignore','pipe','pipe']});
 let stderr='';child.stderr.on('data',b=>stderr+=b);
 let browser;
 try{
 const info=await new Promise((resolve,reject)=>{let data='';const timer=setTimeout(()=>reject(new Error(stderr||'Server timeout')),15000);child.stdout.on('data',b=>{data+=b;try{const v=JSON.parse(data.split('\n')[0]);clearTimeout(timer);resolve(v);}catch{}});child.on('exit',c=>{clearTimeout(timer);reject(new Error('Server exit '+c+' '+stderr));});});
 const url=`http://127.0.0.1:${info.port}`;
 browser=await chromium.launch({channel:'chrome',headless:true});
 const configs=process.env.MOTION_SMOKE?[['pc-pc',1440,1440]]:[['pc-pc',1440,1440],['mobile-mobile',844,844],['pc-mobile',1440,640]];
 for(const [pair,w1,w2] of configs){
  const pages=[];
  for(const [i,width] of [w1,w2].entries()){
   const page=await browser.newPage({viewport:{width,height:width>1000?1000:width===640?288:390},hasTouch:width<1000,isMobile:width<1000});
   page.setDefaultTimeout(5000);const errors=[];page.on('pageerror',e=>errors.push(e.message));page.errors=errors;
   await page.addInitScript(pid=>localStorage.setItem('ko_clientId',pid),'p'+(i+1));
   await page.route('**/*',r=>new URL(r.request().url()).hostname==='127.0.0.1'?r.continue():r.abort());
   await page.goto(url);await page.waitForFunction(()=>cardsById.size===450);
   await page.evaluate(code=>{for(const c of cardsById.values())c.image='card-back.webp';connectAndJoin({code,name:clientId});},info.code);
   await page.waitForFunction(()=>latestState&&Object.keys(latestState.players).length===2&&ws.readyState===1);
   await page.evaluate(()=>{uiBeta.setEnabled(true);showGameScreen();window.motionFlights=[];window.motionAnimations=[];window.motionSent=[];const originalSend=send;send=p=>{motionSent.push(p);return originalSend(p);};
    const fly=playRulesVfxFlight;playRulesVfxFlight=(kind,origin,target,options={})=>{motionFlights.push({kind,origin,target,options});return fly(kind,origin,target,options);};
    const anim=Element.prototype.animate;Element.prototype.animate=function(frames,options){if(this.matches('.bf-card,.rules-vfx-flight'))motionAnimations.push({className:this.className,itemId:this.dataset.itemId,frames,options});return anim.call(this,frames,options);};});
   pages.push(page);
  }
  for(const actorIndex of [0,1]){
   const actor=pages[actorIndex],peer=pages[1-actorIndex],pid='p'+(actorIndex+1),peerId='p'+(2-actorIndex),key=`${pair}-${pid}`;
   const reset=async()=>{await fetch(`${url}/__fixture?pid=${pid}`);for(const page of pages){await page.waitForFunction(pid=>latestState.battlefield.some(i=>i.id==='motion-source'&&i.ownerId===pid),pid);await page.waitForTimeout(150);await page.evaluate(async()=>{removeRulesVfx();pendingBoardArrivals.clear();lastBoardLayout=null;renderAll();motionFlights=[];motionAnimations=[];motionSent=[];await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));});}};
   for(const zone of ['deck','graveyard','exile','hand','receptacle'])await check(`${key}-field-to-${zone}`,async()=>{
    await reset();const dest=zone==='receptacle'?peerId:pid;
    const origin=await peer.locator('[data-item-id="motion-source"]').evaluate(el=>{const r=el.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2};});
    const pile=await peer.evaluate(({dest,zone})=>zone==='hand'?(rulesVfxCenter(document.querySelector(dest===myPlayerId?'#myHandTray':'#opponentHandFan'))||rulesVfxPlayerOrigin(dest)):rulesVfxPileCenter(dest,zone)||rulesVfxPlayerOrigin(dest),{dest,zone});
    if(zone==='deck'||zone==='receptacle')await drag(actor,actor.locator('[data-item-id="motion-source"]'),actor.locator(`[data-drop-zone="${dest}:${zone}"]:visible`).first(),(actorIndex?w2:w1)<1000);
    else await actor.evaluate(({dest,zone})=>send({type:'remove_battlefield_item',itemId:'motion-source',toOwnerId:dest,toZone:zone}),{dest,zone});
    assert.ok(await actor.evaluate(()=>motionSent.some(p=>p.type==='remove_battlefield_item')),JSON.stringify(await actor.evaluate(()=>motionSent)));
    for(const page of pages)await page.waitForFunction(()=>!latestState.battlefield.some(i=>i.id==='motion-source'));
    await peer.waitForFunction(()=>motionFlights.length>0);
    const flights=await peer.evaluate(()=>motionFlights);assert.equal(flights.length,1,JSON.stringify(flights));
    assert.ok(Math.hypot(flights[0].origin.x-origin.x,flights[0].origin.y-origin.y)<3);
    assert.ok(Math.hypot(flights[0].target.x-pile.x,flights[0].target.y-pile.y)<3,JSON.stringify({flights,pile}));
    assert.ok(await peer.locator('.rules-vfx-flight').count()>0,'A real animated card must be present');
    for(const page of pages){const owner=await page.evaluate(({dest,zone})=>{const z=latestState.players[dest].zones[zone];return z.cards?.length??z.count;},{dest,zone});assert.ok(owner>=1);}
    await peer.screenshot({path:path.join(out,`${key}-${zone}.png`)});
   });
   await check(`${key}-zone-to-zone`,async()=>{await reset();await actor.evaluate(pid=>send({type:'move_card',fromOwnerId:pid,fromZone:'graveyard',toOwnerId:pid,toZone:'deck',cardId:latestState.battlefield[0].cardId}),pid);await peer.waitForFunction(()=>motionFlights.length>0);const f=await peer.evaluate(()=>motionFlights);const target=await peer.evaluate(pid=>rulesVfxPileCenter(pid,'deck'),pid);assert.ok(Math.hypot(f[0].target.x-target.x,f[0].target.y-target.y)<3);});
   for(const zone of ['interzone','will'])await check(`${key}-board-to-${zone}`,async()=>{await reset();const source=zone==='will'?'will-source':'motion-source';const target={boundingBox:async()=>actor.evaluate(zone=>{const r=document.querySelector('#ubIzMe').getBoundingClientRect(),d=document.querySelector('#ubIzMe .ub-divider').getBoundingClientRect();return zone==='will'?{x:r.x,y:d.bottom,width:r.width,height:r.bottom-d.bottom}:{x:r.x,y:r.y,width:r.width,height:d.top-r.y};},zone)};
    await drag(actor,actor.locator(`[data-item-id="${source}"]`),target,(actorIndex?w2:w1)<1000);
    await peer.waitForFunction(id=>motionAnimations.some(a=>a.itemId===id&&a.frames[0].transform?.includes('translate')),source);
    for(const page of pages)assert.equal(await page.evaluate(id=>uiBeta.fieldZone(latestState.battlefield.find(i=>i.id===id)),source),zone);
    assert.equal(await actor.locator('.drag-ghost').count(),0);
   });
   await check(`${key}-cleanup-and-errors`,async()=>{await peer.waitForTimeout(1800);for(const page of pages){assert.equal(await page.locator('.rules-vfx-flight,.drag-ghost').count(),0);assert.deepEqual(page.errors,[]);}});
   await check(`${key}-hidden-hand-to-deck-and-replay`,async()=>{await reset();await actor.evaluate(pid=>send({type:'move_card',fromOwnerId:pid,fromZone:'hand',toOwnerId:pid,toZone:'deck',cardId:latestState.players[pid].zones.hand.cards[0]}),pid);await peer.waitForFunction(()=>motionFlights.length>0);assert.equal(await peer.evaluate(()=>motionFlights[0].kind),'draw-card');assert.equal(await peer.evaluate(()=>motionFlights[0].options.cardId),null);await actor.evaluate(()=>send({type:'request_state'}));await peer.waitForTimeout(180);assert.equal(await peer.evaluate(()=>motionFlights.length),1);});
   await check(`${key}-reduced-motion`,async()=>{await peer.emulateMedia({reducedMotion:'reduce'});await reset();await actor.evaluate(pid=>send({type:'remove_battlefield_item',itemId:'motion-source',toOwnerId:pid,toZone:'exile'}),pid);await peer.waitForFunction(()=>!latestState.battlefield.some(i=>i.id==='motion-source'));assert.equal(await peer.evaluate(()=>motionFlights.length),0);assert.ok(await peer.locator('[class*="rules-vfx"]').count()>0,'Reduced motion retains feedback');await peer.emulateMedia({reducedMotion:'no-preference'});});
   await check(`${key}-draw-to-private-hand`,async()=>{await reset();await actor.evaluate(()=>send({type:'draw',count:1}));await peer.waitForFunction(()=>motionFlights.length===1);const f=await peer.evaluate(()=>motionFlights[0]);assert.equal(f.kind,'draw-card');assert.equal(f.options.cardId,undefined);const target=await peer.evaluate(pid=>rulesVfxManualZoneCenter(pid,'hand'),pid);assert.ok(Math.hypot(f.target.x-target.x,f.target.y-target.y)<3);});
   await check(`${key}-hand-to-field-visible-to-peer`,async()=>{await reset();const before=await peer.evaluate(()=>latestState.battlefield.map(i=>i.id));const target={boundingBox:async()=>actor.evaluate(()=>{const r=document.querySelector('#ubIzMe').getBoundingClientRect(),d=document.querySelector('#ubIzMe .ub-divider').getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:d.top-r.y};})};await drag(actor,actor.locator('#myHandTray [data-hand-card]').first(),target,(actorIndex?w2:w1)<1000);await peer.waitForFunction(before=>latestState.battlefield.some(i=>!before.includes(i.id)),before);const item=await peer.evaluate(before=>latestState.battlefield.find(i=>!before.includes(i.id)),before);assert.equal(item.ownerId,pid);assert.equal(item.faceUp,true);assert.equal(await peer.evaluate(id=>uiBeta.fieldZone(latestState.battlefield.find(i=>i.id===id)),item.id),'interzone');assert.equal(await peer.locator(`[data-item-id="${item.id}"].bf-arrive`).count(),1);});
  }
  for(const page of pages)await page.close();
 }
 }finally{await browser?.close();child.kill();
 const report={schemaVersion:1,summary:{executed:tests.length,passed:tests.filter(t=>t.status==='pass').length,failed:tests.filter(t=>t.status==='fail').length},tests,limits:['Chrome desktop and touch emulation, not physical phones or real Safari.','Real production socket/render/drag path; initial zones reset by loopback fixture.'],sources:Object.fromEntries(['public/js/vfx.js','public/ui-beta.js','public/js/board.js','server/main.py','tools/manual_motion_server.py'].map(f=>[f,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,f))).digest('hex')]))};
 fs.writeFileSync(path.join(out,process.env.MOTION_BEFORE?'before.json':'browser.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report.summary));if(report.summary.failed)process.exitCode=1;}
})().catch(e=>{console.error(e);process.exitCode=1;});
