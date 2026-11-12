const fs=require('fs'),http=require('http'),path=require('path');const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..','public');const mime={'.js':'text/javascript','.css':'text/css','.json':'application/json','.html':'text/html','.png':'image/png','.svg':'image/svg+xml','.webp':'image/webp'};
const assert=require('node:assert/strict');
const out=process.env.RALLY_SHOTS||'';
(async()=>{const server=http.createServer((q,r)=>{const rel=decodeURIComponent(new URL(q.url,'http://x').pathname);const f=path.join(root,rel==='/'?'index.html':rel.slice(1));if(!fs.existsSync(f)||!fs.statSync(f).isFile())return r.writeHead(404).end();r.writeHead(200,{'Content-Type':mime[path.extname(f)]||'application/octet-stream'});fs.createReadStream(f).pipe(r);});
await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch(process.env.BROWSER_CHANNEL?{channel:process.env.BROWSER_CHANNEL}:{});
for(const vp of [{width:541,height:1000},{width:1440,height:900},{width:844,height:390}]){
const page=await browser.newPage({viewport:vp,reducedMotion:'reduce'});page.on('pageerror',e=>console.log('ERR',e.message));
await page.route(/api\.kartomantik\.com/,r=>r.abort());
await page.goto(`http://127.0.0.1:${server.address().port}/`);await page.waitForFunction(()=>typeof cardsById!=='undefined'&&cardsById.size>=450);
const info=await page.evaluate(()=>{send=()=>{};myPlayerId='p1';isObserver=false;
const rally=[...cardsById.values()].find(c=>c.name==='Rally');
const manifs=[...cardsById.values()].filter(c=>c.type==='manifestation'&&c.power===2).slice(0,3).map(c=>c.id);
const hand=[rally.id,...manifs];
const player=(id,h)=>({id,name:id,seat:id==='p1'?0:1,color:'#3fc9a8',score:0,sideboard:[],cardRarities:{},zones:Object.fromEntries(['hand','deck','graveyard','exile','receptacle'].map(z=>[z,{cards:z==='hand'?h:[],count:z==='hand'?h.length:0}]))});
latestState={mode:'casual',status:'active',ended:false,players:{p1:player('p1',hand),p2:player('p2',[])},battlefield:[],tokens:[],strokes:[],recentLog:[],essences:{p1:{hollow:5},p2:{}},phaseTracker:{enabled:true,advanced:true,index:ADVANCED_PHASES.findIndex(p=>p.id==='end_actions'),turn:2,passedPlayerIds:[]},rulesEngine:{enabled:true,readyPlayerIds:['p1','p2'],priorityPlayerId:'p1',priorityPasses:[],actionStack:[],ongoingEffects:[],playPermissions:[],pendingChoice:null,firstManifestationComplete:true}};
document.querySelector('#joinScreen').classList.add('hidden');document.querySelector('#gameScreen').classList.remove('hidden');renderAll();
const source={cardId:rally.id,zone:'hand',handIndex:0};const draft=buildRulesActionDraft(source);
draft.optionalExtraEssenceMax=Math.max(3,draft.optionalExtraEssenceMax||0);draft.extraTributeCards=manifs.slice(0,2).map((cardId,i)=>({cardId,index:i+1,power:2}));
pendingRulesBoardFlow={mode:'action',source,draft,selectedPaymentIndexes:new Set(),extraTributeIndexes:new Set([1]),stage:'extra_essence'};renderAll();
return {ok:!!rally,ui:document.querySelector('#gameScreen').className,stage:pendingRulesBoardFlow?.stage};});
assert.equal(info.stage,'extra_essence');await page.waitForTimeout(400);
if(out)await page.screenshot({path:`${out}/rally-${vp.width}.png`});
const m=await page.evaluate(()=>{const copy=document.querySelector('#rulesBoardFlow .rules-floating-copy').getBoundingClientRect();
const imgs=[...document.querySelectorAll('#rulesFlowCost img')].map(i=>i.getBoundingClientRect()).map(r=>Math.max(r.width,r.height));
const pools=[...document.querySelectorAll('.rules-extra-essence-pool')].map(b=>b.getBoundingClientRect());
const rows=[...document.querySelectorAll('#rulesFlowCost > *')].map(e=>e.getBoundingClientRect());
return {imgs,poolH:pools.map(r=>r.height),inside:rows.every(r=>r.left>=copy.left-1&&r.right<=copy.right+1),
token:document.querySelector('#rulesExtraEssenceTokenTotal').textContent.trim(),spent:document.querySelector('#rulesExtraEssenceSpent').textContent.trim()};});
assert.ok(m.imgs.length>=3&&m.imgs.every(s=>s<=32),`Essence icons must stay small: ${JSON.stringify(m)}`);
assert.ok(m.poolH.every(h=>h<=80),`Essence piles must stay compact: ${JSON.stringify(m)}`);
assert.ok(m.inside,`Rally rows must fit in the panel: ${JSON.stringify(m)}`);
assert.match(m.token,/×2/);assert.doesNotMatch(m.spent,/spent first/i);
console.log('ok',vp.width);await page.close();}
await browser.close();server.close();})();
