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
   window.fixture={runtime:false,server:false,client:false,mode:'client',game:true,stale:false,failState:false,failNative:false,failClient:false,hold:false,calls:[],jobs:[]};
   let seq=0;
   window.finishSessionJob=()=>{const f=fixture,j=f.jobs.find(j=>j.status==='running');if(j){f.server=j.operation==='start';j.status='done';j.result={};}};
   window.Trasc={call(id,op,input){setTimeout(()=>{
    const f=fixture;f.calls.push(op);let result={};
    try{
     if(op==='native_state'&&f.failNative)throw Error('Native status unavailable');
     if(op==='native_state')result={installed:true,alive:f.runtime,status:f.runtime?'Runtime ready':'Runtime closed',free_bytes:50e9};
     else if(op==='runtime_start'){f.runtime=true;result={};}
     else if(op==='runtime_stop'){f.runtime=f.server=false;result={};}
     else if(op==='state'){
      if(f.failState)throw Error('Control daemon unavailable');
      result={running:f.server,settings:{ip:'127.0.0.1',login_port:5999,repo:'fixture',ref:'main',workers:3,jobs:2},processes:{},jobs:f.jobs,source:{},binaries_ready:true,database_imported:true,maps_ready:true,client:{},free_bytes:50e9};
     }else if(op==='client_native_state'){
      if(f.failClient)throw Error('Client status unavailable');
      result={alive:f.client,display_ready:f.client,installed:true,busy:false,launch:{mode:f.mode,thread_sample:{sampled_at:Date.now()/1000-(f.stale?60:0),game_running:f.game}}};
     }else if(op==='start'||op==='stop'){
      const j={id:String(++seq),operation:op,status:'running',result:{}};f.jobs.push(j);result=j;if(!f.hold)finishSessionJob();
     }else if(op==='controller_state')result={sources:[],actions:[],layers:[{name:'Main',bindings:{}}],deadzone:.2,sensitivity:700};
     else if(op==='files')result={path:'.',items:[],total:0,offset:0,next_offset:null};
     else if(op==='logs')result={text:'Session log',names:['control.log']};
     else if(op==='log_retention')result={count:5};
     else if(op==='spire_catalog'||op==='spire_search'){
      const j={id:String(++seq),operation:op,status:'done',result:op==='spire_catalog'?{entities:[]}:{records:[],fields:[],columns:[],key:[],offset:0,next_offset:null}};f.jobs.push(j);result=j;
     }
     window.nativeReply(id,{ok:true,result});
    }catch(e){window.nativeReply(id,{ok:false,error:e.message});}
   },5);}};
  });
  await page.goto('http://127.0.0.1:'+server.address().port);
  const waitIdle=()=>page.waitForFunction(()=>!busy&&!polling);
  await waitIdle();
  assert(await page.locator('#start-server').isDisabled());
  await page.locator('#runtime-open').click();await page.waitForFunction(()=>!document.getElementById('start-server').disabled);
  await page.locator('nav [data-tab=fixes]').click();
  assert.equal(await page.locator('#spire #ferry-service-panel, #spire #boat-trial-panel').count(),0);
  assert.equal(await page.locator('#fixes #fix-nektulos, #fixes #spell-test-apply, #fixes #client-prefix-repair, #fixes #ferry-service-panel').count(),4);
  await page.evaluate(()=>fixture.hold=true);await page.locator('#start-server').click();
  await page.waitForFunction(()=>fixture.jobs.some(j=>j.status==='running'));
  assert((await page.locator('#badge').textContent()).includes('Starting'));
  for(const id of ['start-server','stop-server','restart-server','runtime-close'])assert(await page.locator('#'+id).isDisabled());
  await page.evaluate(()=>{finishSessionJob();fixture.hold=false;});await page.waitForFunction(()=>!document.getElementById('stop-server').disabled);
  assert.equal(await page.locator('#badge').textContent(),'Server · Running');
  await page.locator('#restart-server').click();await page.waitForFunction(()=>!document.getElementById('stop-server').disabled);
  assert.deepEqual(await page.evaluate(()=>fixture.calls.filter(x=>x==='start'||x==='stop')),['start','stop','start']);
  await page.evaluate(()=>fixture.client=true);await page.waitForFunction(()=>document.getElementById('client-badge').dataset.state==='running');
  assert((await page.locator('#client-badge').textContent()).includes('background'));
  await page.locator('#stop-server').click();await page.waitForFunction(()=>!document.getElementById('start-server').disabled);
  assert.equal(await page.evaluate(()=>fixture.client),true,'Server stop must not stop the background client');
  await page.locator('#runtime-close').click();await page.waitForFunction(()=>document.getElementById('badge').textContent.includes('Offline'));
  assert.equal(await page.locator('#client-badge').getAttribute('data-state'),'running','Native client status works with the server runtime closed');
  for(const [field,value,text] of [['game',false,'Runtime open'],['game',true,'background'],['stale',true,'Runtime open'],['stale',false,'background'],['mode','desktop','Wine desktop'],['mode','compiler','Compiler active']]){
   await page.evaluate(([field,value])=>fixture[field]=value,[field,value]);await page.waitForFunction(text=>document.getElementById('client-badge').textContent.includes(text),text);
  }
  await page.evaluate(()=>{fixture.client=false;fixture.mode='client';});await page.waitForFunction(()=>document.getElementById('client-badge').textContent.includes('Stopped'));
  await page.locator('#runtime-open').click();await page.waitForFunction(()=>!document.getElementById('start-server').disabled);
  await page.evaluate(()=>{fixture.failState=true;fixture.client=true;});
  await page.waitForFunction(()=>document.getElementById('badge').textContent.includes('unavailable')&&document.getElementById('client-badge').dataset.state==='running');
  assert(await page.locator('#start-server').isDisabled());assert(await page.locator('#stop-server').isDisabled());
  await page.evaluate(()=>{fixture.failState=false;fixture.failClient=true;});await page.waitForFunction(()=>document.getElementById('client-badge').textContent.includes('unavailable'));
  await page.evaluate(()=>fixture.failClient=false);await page.waitForFunction(()=>document.getElementById('client-badge').dataset.state==='running');
  await page.evaluate(()=>fixture.failNative=true);await page.waitForFunction(()=>document.getElementById('runtime-status').textContent.includes('Native status unavailable'));
  assert((await page.locator('#badge').textContent()).includes('unavailable'));
  assert.equal(await page.locator('#client-badge').getAttribute('data-state'),'running');
  await page.evaluate(()=>fixture.failNative=false);await page.waitForFunction(()=>!document.getElementById('start-server').disabled);
  fs.mkdirSync('ui-reports',{recursive:true});
  const scenes=new Set();
  for(const name of ['setup','server','gameplay','build','spire','fixes','database','client','files','logs']){
   await page.locator('nav [data-tab='+name+']').click();await page.evaluate(()=>scrollTo(0,0));await page.waitForTimeout(100);
   const art=await page.evaluate(()=>getComputedStyle(document.body).getPropertyValue('--scene-image').trim());scenes.add(art);
   const file=art.match(/fantasy-[\w-]+\.webp/)[0];assert(fs.existsSync(path.join(root,file)),file+' is bundled');
   await page.screenshot({path:'ui-reports/scene-'+name+'.png'});
  }
  assert.equal(scenes.size,10,'Each tab has a distinct picture');
  await page.locator('nav [data-tab=fixes]').click();
  for(const [label,width,height] of [['thor',1280,720],['small-landscape',854,480],['phone',393,852],['small-phone',360,740]]){
   await page.setViewportSize({width,height});await page.evaluate(()=>scrollTo(0,0));
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   const bar=await page.locator('.runtime-toolbar').boundingBox();assert(bar.height<height*.36,'Session toolbar leaves space to work');
   await page.screenshot({path:'ui-reports/fixes-session-'+label+'.png'});
  }
  assert.deepEqual(errors,[]);console.log('PASS: shared lifecycle controls, independent native client status, game-process evidence, stale/error recovery, ten scenes and responsive layouts');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exit(1);});
