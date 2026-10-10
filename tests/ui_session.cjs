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
   window.fixture={profile:localStorage.sessionProfile||'custom',runtime:false,server:false,client:false,clientBusy:false,sessionBusy:false,mode:'client',game:true,stale:false,failState:false,failNative:false,failClient:false,hold:false,calls:[],jobs:[]};
   let seq=0;
   window.finishSessionJob=()=>{const f=fixture,j=f.jobs.find(j=>j.status==='running');if(j){f.server=j.operation==='start';j.status='done';j.result={};}};
   window.Trasc={call(id,op,input){setTimeout(()=>{
    const f=fixture;f.calls.push(op);let result={};
    try{
     if(op==='native_state'&&f.failNative)throw Error('Native status unavailable');
     if(op==='native_state')result={profile:f.profile,installed:true,alive:f.runtime,session_busy:f.sessionBusy,status:f.runtime?'Runtime ready':'Runtime closed',free_bytes:50e9};
     else if(op==='runtime_start'){f.runtime=true;result={};}
     else if(op==='runtime_stop'){f.runtime=f.server=false;result={};}
     else if(op==='state'){
      if(f.failState)throw Error('Control daemon unavailable');
      result={running:f.server,settings:{ip:'127.0.0.1',login_port:5999,repo:'fixture',ref:'main',workers:3,jobs:2},processes:{},jobs:f.jobs,source:{},binaries_ready:true,database_imported:true,maps_ready:true,client:{},free_bytes:50e9};
     }else if(op==='client_native_state'){
      if(f.failClient)throw Error('Client status unavailable');
      result={profile:f.profile,alive:f.client,display_ready:f.client,installed:true,busy:f.clientBusy,launch:{mode:f.mode,thread_sample:{sampled_at:Date.now()/1000-(f.stale?60:0),game_running:f.game}}};
     }else if(op==='client_stop'){
      f.client=false;result={};
     }else if(op==='start'||op==='stop'){
      const j={id:String(++seq),operation:op,status:'running',result:{}};f.jobs.push(j);result=j;if(!f.hold)finishSessionJob();
     }else if(op==='controller_state')result={sources:[],actions:[],layers:[{name:'Main',bindings:{}}],deadzone:.2,sensitivity:700};
     else if(op==='files'||op==='native_files')result={path:'.',items:[],total:0,offset:0,next_offset:null};
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
  assert(await page.locator('#client-stop').isDisabled(),'Stop client requires an active client runtime');
  for(const id of ['runtime-open','runtime-close','start-server','stop-server','restart-server','client-launch','client-stop']){
   assert.equal(await page.locator('#'+id).count(),1,'Each lifecycle control has a single handler target');
   assert(await page.locator('.runtime-toolbar #'+id).isVisible(),'Runtime, server and client controls are available from every tab');
  }
  for(const label of ['Runtime','Server','Client'])assert.equal(await page.getByRole('group',{name:label,exact:true}).count(),1,'Each lifecycle group has an accessible visible label');
  assert.equal(await page.locator('#client #client-launch, #client #client-stop').count(),0,'Client tab directs launch actions to the shared toolbar');
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
  assert(!(await page.locator('#client-stop').isDisabled()),'Top Stop client is enabled for the background client');
  await page.evaluate(()=>{fixture.jobs.push({id:'build-running',operation:'build',status:'running'});busy++;sessionAction='restart';renderSessionControls();});
  assert(!(await page.locator('#client-stop').isDisabled()),'Server build/restart and global busy state do not block independent client stop');
  await page.locator('#client-stop').click();await page.waitForFunction(()=>!fixture.client&&document.getElementById('client-stop').disabled);
  assert.equal(await page.evaluate(()=>fixture.calls.filter(op=>op==='client_stop').length),1,'Top Stop client dispatches exactly once while the server is busy');
  await page.evaluate(()=>{fixture.jobs=fixture.jobs.filter(job=>job.id!=='build-running');busy--;sessionAction=null;fixture.client=true;});
  await page.waitForFunction(()=>!document.getElementById('client-stop').disabled);
  await page.evaluate(()=>fixture.clientBusy=true);await page.waitForFunction(()=>document.getElementById('client-stop').disabled);
  await page.evaluate(()=>fixture.clientBusy=false);await page.waitForFunction(()=>!document.getElementById('client-stop').disabled);
  await page.evaluate(()=>fixture.sessionBusy=true);await page.waitForFunction(()=>document.getElementById('client-stop').disabled);
  await page.evaluate(()=>fixture.sessionBusy=false);await page.waitForFunction(()=>!document.getElementById('client-stop').disabled);
  assert((await page.locator('#client-badge').textContent()).includes('background'));
  await page.locator('#stop-server').click();await page.waitForFunction(()=>!document.getElementById('start-server').disabled);
  assert.equal(await page.evaluate(()=>fixture.client),true,'Server stop must not stop the background client');
  await page.locator('#runtime-close').click();await page.waitForFunction(()=>document.getElementById('badge').textContent.includes('Offline'));
  assert.equal(await page.locator('#client-badge').getAttribute('data-state'),'running','Native client status works with the server runtime closed');
  for(const [field,value,text] of [['game',false,'Runtime open'],['game',true,'background'],['stale',true,'Runtime open'],['stale',false,'background'],['mode','desktop','Wine desktop'],['mode','compiler','Compiler active']]){
   await page.evaluate(([field,value])=>fixture[field]=value,[field,value]);await page.waitForFunction(text=>document.getElementById('client-badge').textContent.includes(text),text);
  }
  await page.evaluate(()=>{fixture.client=false;fixture.mode='client';});await page.waitForFunction(()=>document.getElementById('client-badge').textContent.includes('Stopped'));
  assert(await page.locator('#client-stop').isDisabled(),'Top Stop client disables after the client closes');
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
   const bar=await page.locator('.runtime-toolbar').boundingBox();assert(bar.height<height*(width<540?.40:.36),'Session toolbar leaves space to work');
   await page.screenshot({path:'ui-reports/fixes-session-'+label+'.png'});
  }
  for(const profile of ['custom','traditional','takp']){
   await page.evaluate(profile=>localStorage.sessionProfile=profile,profile);await page.reload();await waitIdle();
   await page.waitForFunction(profile=>document.body.dataset.profile===profile,profile);
   for(const theme of ['default','necromancer','monk']){
    await page.selectOption('#launcher-theme',theme);
    for(const [width,height] of [[1280,720],[1024,600],[854,480],[680,480],[393,852],[360,740]]){
     await page.setViewportSize({width,height});await page.evaluate(()=>scrollTo(0,0));
     const layout=await page.evaluate(()=>{
      const box=selector=>{const r=document.querySelector(selector).getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height,center:r.left+r.width/2};};
      const groups=['.runtime-controls','.server-controls','.client-controls'].map(selector=>{const style=getComputedStyle(document.querySelector(selector)),divider=getComputedStyle(document.querySelector(selector),'::before');return {...box(selector),borderTop:parseFloat(style.borderTopWidth),dividerWidth:parseFloat(divider.borderLeftWidth),dividerVisible:divider.display!=='none'};});
      return {bar:box('.runtime-toolbar'),actions:box('.runtime-actions'),groups,buttons:['#runtime-open','#runtime-close','#start-server','#stop-server','#restart-server','#client-launch','#client-stop'].map(selector=>{const e=document.querySelector(selector);return {...box(selector),labelClipped:e.scrollWidth>e.clientWidth||e.scrollHeight>e.clientHeight};}),overflow:document.documentElement.scrollWidth>innerWidth+1};
     });
     assert(!layout.overflow,`${profile}/${theme}/${width}: toolbar does not overflow`);
     assert(Math.abs(layout.actions.center-layout.bar.center)<1,`${profile}/${theme}/${width}: all lifecycle groups are centered together`);
     for(const b of layout.buttons){
      assert(b.height>=44&&b.width>=44,`${profile}/${theme}/${width}: lifecycle controls have touch targets`);
      assert.equal(b.height,layout.buttons[0].height,`${profile}/${theme}/${width}: all seven tiles have equal height`);
      assert(!b.labelClipped,`${profile}/${theme}/${width}: stacked labels fit each tile`);
      assert(b.left>=layout.bar.left&&b.right<=layout.bar.right&&b.top>=layout.bar.top&&b.bottom<=layout.bar.bottom,`${profile}/${theme}/${width}: launch button remains inside the toolbar`);
     }
     if(width>=540){
      for(const b of layout.buttons)assert(Math.abs(b.top-layout.buttons[0].top)<1,`${profile}/${theme}/${width}: all seven tiles line up in one row`);
      for(let i=1;i<layout.groups.length;i++){assert(layout.groups[i-1].right<layout.groups[i].left,`${profile}/${theme}/${width}: lifecycle groups do not overlap`);assert(layout.groups[i].dividerVisible&&layout.groups[i].dividerWidth>=1,`${profile}/${theme}/${width}: visible dividers separate lifecycle groups`);}
     }else{
      for(let i=1;i<layout.groups.length;i++){assert(layout.groups[i-1].bottom<layout.groups[i].top,`${profile}/${theme}/${width}: narrow-screen groups remain separate aligned rows`);assert.equal(layout.groups[i].left,layout.groups[0].left);assert.equal(layout.groups[i].right,layout.groups[0].right);assert(layout.groups[i].borderTop>=1,`${profile}/${theme}/${width}: horizontal dividers separate narrow-screen groups`);}
     }
     if(theme==='monk'&&(width===1280||width===854||width===393))await page.screenshot({path:`ui-reports/runtime-launch-${profile}-${width}.png`});
    }
   }
   if(profile==='takp'){
    assert.equal(await page.locator('#client-launch').textContent(),'Start TAKP');
    const help=await page.locator('#client-export-help').textContent();
    for(const name of ['spells_us.txt','SkillCaps.txt','spells_en.txt','checksum'])assert(help.includes(name),'TAKP help distinguishes export names from the original checksum file');
   }
  }
  assert.deepEqual(errors,[]);console.log('PASS: seven aligned lifecycle tiles with labeled/divided groups across three worlds and themes, lifecycle guards, independent client status, game-process evidence, stale/error recovery and responsive layouts');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exit(1);});
