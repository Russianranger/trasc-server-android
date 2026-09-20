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
   let jobs=[],seq=0,active=true,preview=null;window.boatCalls=[];window.boatSaves=[];window.boatRunning=false;window.boatFail=false;
   window.Trasc={call(id,op,input){
    const a=JSON.parse(input);window.boatCalls.push({op,args:a});let result={};
    try{
     if(op==='native_state')result={installed:true,alive:true,status:'Runtime ready'};
     else if(op==='state')result={settings:{ip:'127.0.0.1',repo:'fixture',ref:'main',workers:3,jobs:2},source:{},running:window.boatRunning,processes:{},jobs,free_bytes:50e9,nektulos:{},client:{}};
     else if(op==='client_native_state')result={installed:true,alive:false,busy:false};
     else if(op.startsWith('boat_trial_')||op==='spire_catalog'||op==='spire_search'){
      let r={};
      if(op==='spire_catalog')r={entities:[{table:'items',label:'Items',available:true}]};
      if(op==='spire_search')r={table:'items',key:['id'],fields:[],columns:[],records:[],offset:0,next_offset:null};
      if(op==='boat_trial_status')r={active,message:active?'Ferry installed.':'No trial installed.'};
      if(op==='boat_trial_preview'){preview=a.action;r={token:'preview-'+(++seq),action:a.action,summary:'Review '+a.action+' ferry.',message:'Stop server. Full database backup first.'};}
      if(op==='boat_trial_apply'){
       if(window.boatRunning)throw Error('Stop the server');
       if(window.boatFail)throw Error('Trial changed after preview; preview again');
       active=preview!=='remove';window.boatSaves.push(preview);r={active,message:'Ferry '+preview+' complete.',backup:'backups/ferry.sql.gz'};
      }
      const j={id:String(++seq),operation:op,status:'done',result:r};jobs.push(j);result=j;
     }
     setTimeout(()=>window.nativeReply(id,{ok:true,result}),5);
    }catch(e){setTimeout(()=>window.nativeReply(id,{ok:false,error:e.message}),5);}
   }};
  });
  await page.goto('http://127.0.0.1:'+server.address().port);await page.locator('nav [data-tab="fixes"]').click();
  await page.locator('#boat-trial-panel summary').click();await page.waitForFunction(()=>!boatTrial.working&&boatTrial.active===true);
  assert.equal(await page.locator('#boat-trial-install, #boat-trial-reset').count(),0,'Retired trials cannot be installed or reset from the app');
  assert.equal(await page.locator('#spire #boat-trial-panel').count(),0);
  await page.locator('#boat-trial-remove').click();await page.waitForFunction(()=>!boatTrial.working&&boatTrial.preview);
  assert.equal(await page.evaluate(()=>boatSaves.length),0);
  await page.evaluate(()=>{boatRunning=true;lastState.running=true;renderBoatTrial();});
  assert(await page.locator('#boat-trial-save').isDisabled());
  await page.evaluate(()=>{boatRunning=false;lastState.running=false;renderBoatTrial();});
  await page.locator('#boat-trial-refresh').click();await page.waitForFunction(()=>!boatTrial.working);
  assert(await page.locator('#boat-trial-preview').isHidden());assert(await page.locator('#boat-trial-save').isDisabled());
  await page.locator('#boat-trial-remove').click();await page.waitForFunction(()=>!boatTrial.working&&boatTrial.preview);
  await page.evaluate(()=>boatFail=true);await page.locator('#boat-trial-save').click();await page.waitForFunction(()=>!boatTrial.working);
  assert((await page.locator('#boat-trial-status').textContent()).includes('changed after preview'));assert(await page.locator('#boat-trial-save').isDisabled());
  assert.equal(await page.evaluate(()=>boatSaves.length),0);
  await page.evaluate(()=>boatFail=false);await page.locator('#boat-trial-remove').click();await page.waitForFunction(()=>!boatTrial.working&&boatTrial.preview);
  await page.locator('#boat-trial-save').click();await page.waitForFunction(()=>!boatTrial.working&&boatTrial.active===false);
  assert.equal(await page.evaluate(()=>boatSaves.join(',')),'remove');
  assert(await page.locator('#boat-trial-remove').isDisabled());
  await page.locator('#boat-trial-refresh').click();await page.waitForFunction(()=>!boatTrial.working);
  assert((await page.locator('#boat-trial-status').textContent()).includes('Nothing to clean up'));
  assert.deepEqual(await page.evaluate(()=>boatCalls.filter(c=>c.op==='boat_trial_preview').map(c=>c.args.action)),['remove','remove','remove']);
  fs.mkdirSync('ui-reports',{recursive:true});
  for(const [label,width,height] of [['boat-thor',854,480],['boat-phone',393,852]]){
   await page.setViewportSize({width,height});await page.locator('#boat-trial-panel').scrollIntoViewIfNeeded();
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await page.screenshot({path:'ui-reports/'+label+'.png'});
  }
  assert.deepEqual(errors,[]);console.log('PASS: retired ferry cleanup, running-server guard, preview invalidation, failure recovery, scoped removal and responsive layouts');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exit(1);});
