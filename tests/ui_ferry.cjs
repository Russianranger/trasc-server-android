const {chromium}=require('playwright');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert');
const root=path.resolve('app/src/main/assets/ui');
const server=http.createServer((req,res)=>{
 const name=req.url==='/'?'index.html':req.url.slice(1);
 if(!/^[\w.-]+$/.test(name)){res.writeHead(404);res.end();return;}
 try{res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.webp')?'image/webp':name.endsWith('.ttf')?'font/ttf':'text/html');res.end(fs.readFileSync(path.join(root,name)));}
 catch{res.writeHead(404);res.end();}
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:854,height:480}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
   let jobs=[],seq=0,active=false,preview=null;window.ferryCalls=[];window.ferrySaves=[];window.ferryRunning=false;window.ferryFail=false;window.ferryReady=false;
   window.Trasc={call(id,op,input){
    const a=JSON.parse(input);window.ferryCalls.push({op,args:a});let result={};
    try{
     if(op==='native_state')result={installed:true,alive:true,status:'Runtime ready'};
     else if(op==='state')result={settings:{ip:'127.0.0.1',repo:'fixture',ref:'main',workers:3,jobs:2},source:{},running:window.ferryRunning,processes:{},jobs,free_bytes:50e9,nektulos:{},client:{}};
     else if(op==='client_native_state')result={installed:true,alive:false,busy:false};
     else if(op.startsWith('ferry_service_')||op==='spire_catalog'||op==='spire_search'){
      let r={};
      if(op==='spire_catalog')r={entities:[{table:'items',label:'Items',available:true}]};
      if(op==='spire_search')r={table:'items',key:['id'],fields:[],columns:[],records:[],offset:0,next_offset:null};
      if(op==='ferry_service_status')r={active,server_ready:window.ferryReady,message:active?'Ferry installed.':'No trial installed.'};
      if(op==='ferry_service_preview'){preview=a.action;r={token:'preview-'+(++seq),action:a.action,summary:'Review '+a.action+' ferry.',message:'Stop server. Full database backup first.'};}
      if(op==='ferry_service_apply'){
       if(window.ferryRunning)throw Error('Stop the server');
       if(window.ferryFail)throw Error('Trial changed after preview; preview again');
       active=preview!=='remove';window.ferrySaves.push(preview);r={active,message:'Ferry '+preview+' complete.',backup:'backups/ferry.sql.gz'};
      }
      const j={id:String(++seq),operation:op,status:'done',result:r};jobs.push(j);result=j;
     }
     setTimeout(()=>window.nativeReply(id,{ok:true,result}),5);
    }catch(e){setTimeout(()=>window.nativeReply(id,{ok:false,error:e.message}),5);}
   }};
  });
  await page.goto('http://127.0.0.1:'+server.address().port);await page.locator('nav [data-tab="spire"]').click();
  await page.locator('#ferry-service-panel summary').click();await page.waitForFunction(()=>!ferryService.working&&ferryService.active===false);
  assert(await page.locator('#ferry-service-reset').isDisabled());
  assert(await page.locator('#ferry-service-install').isDisabled());
  await page.evaluate(()=>ferryReady=true);await page.locator('#ferry-service-refresh').click();await page.waitForFunction(()=>!ferryService.working&&ferryService.ready);
  assert(await page.locator('#ferry-service-install').isEnabled());
  await page.locator('#ferry-service-install').click();await page.waitForFunction(()=>!ferryService.working&&ferryService.preview);
  assert.equal(await page.evaluate(()=>ferrySaves.length),0);
  await page.evaluate(()=>{ferryRunning=true;lastState.running=true;renderFerryService();});
  assert(await page.locator('#ferry-service-save').isDisabled());
  await page.evaluate(()=>{ferryRunning=false;lastState.running=false;renderFerryService();});
  await page.locator('#ferry-service-save').click();await page.waitForFunction(()=>!ferryService.working&&ferryService.active===true);
  assert.equal(await page.evaluate(()=>ferrySaves.join(',')),'install');assert(await page.locator('#ferry-service-preview').isHidden());
  assert(await page.locator('#ferry-service-install').isDisabled());assert(await page.locator('#ferry-service-reset').isEnabled());
  await page.locator('#ferry-service-update').click();await page.waitForFunction(()=>!ferryService.working&&ferryService.preview);
  assert((await page.locator('#ferry-service-summary').textContent()).includes('update'));
  await page.locator('#ferry-service-save').click();await page.waitForFunction(()=>!ferryService.working);
  await page.locator('#ferry-service-reset').click();await page.waitForFunction(()=>!ferryService.working&&ferryService.preview);
  await page.locator('#ferry-service-refresh').click();await page.waitForFunction(()=>!ferryService.working);
  assert(await page.locator('#ferry-service-preview').isHidden());assert(await page.locator('#ferry-service-save').isDisabled());
  await page.locator('#ferry-service-remove').click();await page.waitForFunction(()=>!ferryService.working&&ferryService.preview);
  await page.evaluate(()=>ferryFail=true);await page.locator('#ferry-service-save').click();await page.waitForFunction(()=>!ferryService.working);
  assert((await page.locator('#ferry-service-status').textContent()).includes('changed after preview'));assert(await page.locator('#ferry-service-save').isDisabled());
  assert.equal(await page.evaluate(()=>ferrySaves.length),2);
  await page.evaluate(()=>ferryFail=false);await page.locator('#ferry-service-remove').click();await page.waitForFunction(()=>!ferryService.working&&ferryService.preview);
  await page.locator('#ferry-service-save').click();await page.waitForFunction(()=>!ferryService.working&&ferryService.active===false);
  assert.equal(await page.evaluate(()=>ferrySaves.join(',')),'install,update,remove');
  fs.mkdirSync('ui-reports',{recursive:true});
  for(const [label,width,height] of [['ferry-thor',854,480],['ferry-phone',393,852]]){
   await page.setViewportSize({width,height});await page.locator('#ferry-service-panel').scrollIntoViewIfNeeded();
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await page.screenshot({path:'ui-reports/'+label+'.png'});
  }
  assert.deepEqual(errors,[]);console.log('PASS: ferry preview/save, running-server guard, reset preview invalidation, failure recovery, scoped removal and responsive layouts');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exit(1);});
