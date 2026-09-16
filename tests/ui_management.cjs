const {chromium}=require('playwright');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert');
const root=path.resolve('app/src/main/assets/ui');
const server=http.createServer((req,res)=>{
 const name=req.url==='/'?'index.html':req.url.slice(1);
 if(!/^[\w.-]+$/.test(name)){res.writeHead(404);res.end();return;}
 try{res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(path.join(root,name)));}catch{res.writeHead(404);res.end();}
});
const fixture={values:{},metadata:{}};
for(let i=0;i<1100;i++){const name='Category'+(i%47)+':Rule'+i;fixture.metadata[name]={type:'int',min:'-2147483648',max:'2147483647',max_length:128,description:'A test rule '+i};fixture.values[name]={value:String(i),ruleset:1};}
for(const [name,type,value,min,max]of [['Character:RaidExpMultiplier','real','0.3','0','1'],['Character:FinalRaidExpMultiplier','real','0.0000000000001','0','3.4e38'],['Zone:StateSavingOnShutdown','bool','true'],['World:MaxClientsPerIP','int','-1','-2147483648','2147483647'],['Custom:Greeting','string','hello']]){
 fixture.metadata[name]={type,min,max,max_length:65535,description:'Description for '+name};fixture.values[name]={value,ruleset:1};
}
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:412,height:915}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(data=>{
   let seq=0,jobs=[],spellTest={};const actions=['None','MouseLeft','MouseRight','PointerUp','PointerDown','PointerLeft','PointerRight','KeyW','KeyT','Space','Escape'];
   let profile={sources:['A','B','RightUp','RightDown','RightLeft','RightRight'],actions,bindings:{A:'Space',B:'Escape',RightUp:'PointerUp',RightDown:'PointerDown',RightLeft:'PointerLeft',RightRight:'PointerRight'},deadzone:.2,sensitivity:700};
   window.__saves=[];window.__alive=true;window.__calls=[];window.__exports=[];window.__clientStarts=[];window.__clientViews=0;
   let clientRuntime={installed:true,alive:false,busy:false,status:'Client runtime installed',directx_installed:false};
   window.__clientEvidence=value=>Object.assign(clientRuntime.launch,value);
   const state=()=>({version:'0.2.1',running:false,settings:{ip:'127.0.0.1',login_port:5999,repo:'https://github.com/Russianranger/Triptych-Triumvirate',ref:'main',workers:3,jobs:2},source:{commit:'test'},maps_ready:true,database_imported:true,binaries_ready:true,processes:{},jobs,free_bytes:50e9,nektulos:{legacy_ready:true},client:{imported:true,files:10,bytes:1000,spell_test:spellTest}});
   window.Trasc={call(id,op,input){setTimeout(()=>{
    const args=JSON.parse(input);let result;window.__calls.push(op);
    if(op==='native_state')result={installed:true,alive:window.__alive,status:window.__alive?'Runtime ready':'Runtime stopped. Logs are still available.',free_bytes:50e9};
    else if(op==='runtime_start'){window.__alive=true;result={};}
    else if(op==='runtime_stop'){window.__alive=false;result={};}
    else if(op==='client_native_state')result=clientRuntime;
    else if(op==='client_directx_online'||(op==='pick'&&args.kind==='client-directx')){clientRuntime.directx_installed=true;result=clientRuntime;}
    else if(op==='client_runtime_online'){clientRuntime.installed=true;result=clientRuntime;}
    else if(op==='client_start'){window.__clientStarts.push(args);clientRuntime={...clientRuntime,alive:true,display_ready:true,launch:{phase:'launch_requested',native_dinput8_requested:args.native_dinput8,native_loaded:false,native_d3dx_requested:args.native_d3dx,diagnostic_logging:args.diagnostic_logging}};result=clientRuntime;}
    else if(op==='client_view'){window.__clientViews++;result={};}
    else if(op==='client_stop'){clientRuntime.alive=false;result=clientRuntime;}
    else if(op==='state'){
     if(!window.__alive){window.nativeReply(id,{ok:false,error:'Backend is deliberately unavailable in this regression test'});return;}
     result=state();
    }
    else if(op==='session_backup'){
     window.__alive=false;window.nativeReply(id,{ok:false,error:'Session backup failed: simulated storage error. Runtime is stopped. Logs are still available; open runtime to continue.'});return;
    }
    else if(op==='logs')result={text:args.name==='app.log'?'session_backup failed: simulated storage error':'Saved output: '+args.name,names:['app.log','runtime.log','control.log','operation.log','server/zones/cabeast.log','client/Logs/dbg.txt','client/dinput8.log']};
    else if(op==='export_logs')result={file:'exports/logs-native.zip'};
    else if(op==='export'){window.__exports.push(args.path);if(window.__cancelExport){window.nativeReply(id,{ok:false,error:'File selection cancelled'});return;}result={message:'File exported'};}
    else if(op==='controller_state')result=profile;
    else if(op==='controller_save'){profile={...profile,...args};result=profile;}
    else if(op==='controller_capture'){window.clientInputEvent?.({type:'capture',down:args.active});result={...profile,active:args.active};}
    else{
     let completed={};if(op==='gameplay')completed={...data,rulesets:[{id:1,name:'default'}],selected:1,active_name:'default'};
     else if(op==='export_client')completed={file:'exports/client-data.zip',local_client_synced:true,copied_files:8,message:'All four client data files overwritten in the local client root and Resources folder. Originals saved in backups/client-setup/test.'};
     else if(op==='apply_spell_test'){spellTest={state:'applied',excluded_ids:[50000,50001,50002,50003,50004,50005,50006,50007],filtered_rows:40914};completed={message:'Spell test applied: 8 high-ID entries excluded.'};}
     else if(op==='restore_spell_test'){spellTest={state:'restored'};completed={message:'Full spell files restored and verified in root and Resources.'};}
     else if(op==='save_gameplay'){window.__saves.push(args);for(const [name,value]of Object.entries(args.values))data.values[name]={value,ruleset:1};}
     const job={id:String(++seq),operation:op,status:'done',result:completed};jobs=[job];result=job;
    }
    window.nativeReply(id,{ok:true,result});
   },5);}};
  },fixture);
  await page.goto('http://127.0.0.1:'+server.address().port);
  await page.locator('#runtime-close').click();await page.waitForFunction(()=>!window.__alive);
  await page.locator('#runtime-open').click();await page.waitForFunction(()=>window.__alive);
  assert.equal(await page.locator('#setup #runtime-open').count(),0,'Runtime controls are outside Setup');
  await page.locator('nav [data-tab=gameplay]').click();await page.locator('#load-rules').click();
  await page.waitForFunction(()=>document.getElementById('rules-count').textContent.includes('1105'));
  assert.equal(await page.locator('.rule-category[open]').count(),0,'Categories start collapsed');
  await page.locator('#rule-search').fill('FinalRaid');await page.locator('#rule-Character-FinalRaidExpMultiplier').waitFor();
  assert.equal(await page.locator('#rule-Character-FinalRaidExpMultiplier').inputValue(),'0.0000000000001');
  await page.locator('#rule-search').fill('RaidExp');await page.locator('#rule-Character-RaidExpMultiplier').fill('1.1');await page.locator('#save-rules').click();
  await page.waitForFunction(()=>document.getElementById('rules-errors').textContent.includes('above the maximum 1'));
  assert.equal(await page.evaluate(()=>window.__saves.length),0,'Invalid rules must not reach save API');
  assert.equal(await page.locator('#rule-Character-RaidExpMultiplier').getAttribute('aria-invalid'),'true');
  fs.mkdirSync('ui-reports',{recursive:true});await page.screenshot({path:'ui-reports/rules-mobile.png',fullPage:true});
  await page.locator('#rule-Character-RaidExpMultiplier').fill('0.4');await page.locator('#save-rules').click();
  await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('Settings saved. Restart'));
  assert.deepEqual(await page.evaluate(()=>window.__saves[0].values),{'Character:RaidExpMultiplier':'0.4'},'Only edited values saved');
  await page.locator('#rule-search').fill('MaxClientsPerIP');assert.equal(await page.locator('#rule-World-MaxClientsPerIP').inputValue(),'-1');
  await page.locator('nav [data-tab=client]').click();await page.locator('#binding-A').selectOption('KeyT');await page.locator('#controller-save').click();
  await page.waitForFunction(()=>document.getElementById('notice').textContent==='Controller bindings saved.');
  await page.locator('#controller-capture').click();await page.waitForFunction(()=>document.getElementById('controller-focus').textContent.includes('captured'));
  await page.evaluate(()=>{window.clientInputEvent({type:'button',action:'KeyT',down:true});window.clientInputEvent({type:'pointer',x:90,y:20});});
  assert((await page.locator('#client-input-status').textContent()).includes('KeyT'));
  const toolbar=await page.locator('.runtime-toolbar').boundingBox();assert(toolbar.y>=0&&toolbar.y+toolbar.height<915,'Runtime controls remain in the viewport while scrolled');
  await page.screenshot({path:'ui-reports/client-mobile.png',fullPage:true});
  await page.locator('#spell-test-apply').click();
  await page.waitForFunction(()=>document.getElementById('spell-test-status').textContent.includes('40914 rows'));
  await page.waitForFunction(()=>!document.getElementById('spell-test-restore').disabled);
  for(const id of ['spell-test-apply','client-prepare','client-import','export-client'])assert(await page.locator('#'+id).isDisabled(),'Active comparison protects '+id);
  await page.screenshot({path:'ui-reports/spell-comparison-mobile.png',fullPage:true});
  await page.locator('#spell-test-restore').click();
  await page.waitForFunction(()=>document.getElementById('spell-test-status').textContent.includes('restored and verified'));
  await page.waitForFunction(()=>!document.getElementById('spell-test-apply').disabled);
  assert(await page.locator('#spell-test-restore').isDisabled());
  await page.locator('#client-directx-online').click();await page.waitForFunction(()=>document.getElementById('client-directx-status').textContent.includes('installed'));
  await page.locator('#client-directx-offline').click();await page.waitForFunction(()=>document.getElementById('notice').textContent==='DirectX model helpers installed.');
  await page.locator('#client-resolution').selectOption('960x540');await page.locator('#client-desktop').click();
  await page.waitForFunction(()=>window.__clientViews===1);
  assert(await page.locator('#spell-test-apply').isDisabled(),'Running client blocks file comparison');
  assert(await page.locator('#client-launch').isDisabled(),'A running desktop must be stopped before another launch');
  assert.deepEqual(await page.evaluate(()=>window.__clientStarts[0]),{sound_diagnostics:false,audio:true,npc_rendering:'compatibility',mode:'desktop',resolution:'960x540',fullscreen:false,native_dinput8:true,diagnostic_logging:false,native_d3dx:false,renderer:'software',cpu_profile:'balanced',runtime_mode:'auto',graphics_threading:'multi',cpu_affinity:'available'});
  assert(!(await page.locator('#client-launch-status').textContent()).includes('load confirmed'),'File presence/request must not claim DLL loaded');
  await page.locator('#client-stop').click();await page.waitForFunction(()=>document.getElementById('client-launch-status').textContent.startsWith('Client stopped.'));
  await page.locator('#client-renderer').selectOption('virgl');
  await page.locator('#client-launch').click();await page.waitForFunction(()=>window.__clientViews===2);
  assert.equal(await page.evaluate(()=>window.__clientStarts[1].mode),'client');
  assert.equal(await page.evaluate(()=>window.__clientStarts[1].native_d3dx),true);
  assert.equal(await page.evaluate(()=>window.__clientStarts[1].renderer),'virgl');
  assert.equal(await page.evaluate(()=>window.__clientStarts[1].cpu_profile),'balanced');
  await page.evaluate(async()=>{window.__clientEvidence({native_loaded:true,system_dinput8_loaded:false});await clientRuntimeState();});
  assert((await page.locator('#client-launch-status').textContent()).includes('System DirectInput load not yet confirmed.'));
  await page.evaluate(async()=>{window.__clientEvidence({system_dinput8_loaded:true});await clientRuntimeState();});
  assert((await page.locator('#client-launch-status').textContent()).includes('Wine system DirectInput loaded.'));
  await page.locator('#client-view').click();await page.waitForFunction(()=>window.__clientViews===3);
  await page.locator('#client-stop').click();await page.waitForFunction(()=>document.getElementById('client-launch-status').textContent.startsWith('Client stopped.'));
  await page.locator('#client-graphics-threading').selectOption('opengl_worker');await page.locator('#client-runtime-mode').selectOption('compatibility');await page.locator('#client-cpu-profile').selectOption('compatibility');await page.locator('#client-diagnostics').check();await page.locator('#client-prefix-repair').click();await page.waitForFunction(()=>window.__clientViews===4);
  assert.deepEqual(await page.evaluate(()=>window.__clientStarts[2]),{sound_diagnostics:false,audio:true,npc_rendering:'compatibility',mode:'desktop',resolution:'960x540',fullscreen:false,native_dinput8:true,diagnostic_logging:true,native_d3dx:false,repair_prefix:true,renderer:'software',cpu_profile:'compatibility',runtime_mode:'compatibility',graphics_threading:'opengl_worker',cpu_affinity:'available'});
  assert((await page.locator('#client-launch-status').textContent()).includes('Verbose diagnostics enabled'));
  await page.locator('#client-stop').click();
  await page.waitForFunction(()=>document.getElementById('client-launch-status').textContent.startsWith('Client stopped.'));
  await page.locator('#client-resolution').selectOption('1280x720');
  await page.locator('#client-fullscreen').check();
  await page.locator('#client-renderer').selectOption('turnip');
  assert(await page.locator('#client-graphics-threading').isDisabled(),'WineD3D threading does not apply to DXVK');
  assert(!(await page.locator('#client-npc-rendering').isDisabled()));
  await page.locator('#client-npc-rendering').selectOption('standard');
  await page.locator('#client-cpu-profile').selectOption('accurate');
  await page.locator('#client-sound-diagnostics').check();
  await page.locator('#client-audio').uncheck();
  await page.locator('#client-cpu-affinity').selectOption('game');
  await page.locator('#client-launch').click();await page.waitForFunction(()=>window.__clientViews===5);
  assert.equal(await page.evaluate(()=>window.__clientStarts[3].audio),false);
  assert.equal(await page.evaluate(()=>window.__clientStarts[3].cpu_profile),'accurate');
  assert.equal(await page.evaluate(()=>window.__clientStarts[3].sound_diagnostics),true);
  assert.equal(await page.evaluate(()=>window.__clientStarts[3].npc_rendering),'standard');
  assert.equal(await page.evaluate(()=>window.__clientStarts[3].renderer),'turnip');
  assert.equal(await page.evaluate(()=>window.__clientStarts[3].resolution),'1280x720');
  assert.equal(await page.evaluate(()=>window.__clientStarts[3].fullscreen),true);
  assert.equal(await page.evaluate(()=>window.__clientStarts[3].cpu_affinity),'game');
  await page.locator('#client-stop').click();await page.waitForFunction(()=>document.getElementById('client-launch-status').textContent.startsWith('Client stopped.'));
  await page.locator('#client-fullscreen').uncheck();
  await page.locator('#client-renderer').selectOption('virgl');
  assert(!(await page.locator('#client-graphics-threading').isDisabled()),'WineD3D recovery restores threading controls');
  await page.locator('nav [data-tab=setup]').click();await page.waitForFunction(()=>document.getElementById('controller-focus').textContent==='Controller capture is off.');
  assert(!(await page.locator('#client-input-status').textContent()).includes('KeyT'),'Leaving tab releases input');
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'No horizontal page overflow on mobile');
  await page.setViewportSize({width:960,height:540});await page.screenshot({path:'ui-reports/setup-landscape.png',fullPage:true});
  await page.locator('nav [data-tab=server]').click();
  await page.locator('#export-client').click();
  await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('File exported.'));
  assert((await page.locator('#notice').textContent()).includes('root and Resources'));
  assert.deepEqual(await page.evaluate(()=>window.__exports),['exports/client-data.zip']);
  await page.evaluate(()=>{window.__cancelExport=true;});
  await page.locator('#export-client').click();
  await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('File selection cancelled'));
  assert((await page.locator('#notice').textContent()).includes('All four client data files overwritten'));
  assert(!(await page.locator('#notice').evaluate(el=>el.classList.contains('error'))),'Cancelling ZIP save must preserve local sync success');
  await page.evaluate(()=>{window.__cancelExport=false;window.__exports=[];});
  await page.locator('#session-export').click();
  await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('simulated storage error'));
  await page.waitForFunction(()=>document.getElementById('badge').textContent==='RUNTIME CLOSED');
  await page.evaluate(async()=>{await poll();window.__calls=[];});
  await page.locator('nav [data-tab=logs]').click();await page.locator('#log-name').selectOption('operation.log');
  await page.waitForFunction(()=>document.getElementById('log-output').textContent==='Saved output: operation.log');
  await page.locator('#log-name').selectOption('server/zones/cabeast.log');
  await page.waitForFunction(()=>document.getElementById('log-output').textContent.includes('server/zones/cabeast.log'));
  await page.locator('#log-name').selectOption('client/Logs/dbg.txt');
  await page.waitForFunction(()=>document.getElementById('log-output').textContent.includes('client/Logs/dbg.txt'));
  await page.locator('#log-name').selectOption('app.log');
  await page.waitForFunction(()=>document.getElementById('log-output').textContent.includes('session_backup failed'));
  await page.locator('#export-logs').click();await page.waitForFunction(()=>window.__exports.length===1);
  await page.waitForFunction(()=>document.getElementById('notice').textContent==='File exported. A local copy is retained.');
  await page.screenshot({path:'ui-reports/logs-runtime-closed.png',fullPage:true});
  await page.locator('nav [data-tab=server]').click();await page.locator('#quick-logs').click();
  await page.waitForFunction(()=>window.__exports.length===2);
  assert.deepEqual(await page.evaluate(()=>window.__exports),['exports/logs-native.zip','exports/logs-native.zip'],'Both buttons save a native log bundle through Android');
  const calls=await page.evaluate(()=>window.__calls);
  assert(!calls.includes('state')&&!calls.includes('runtime_start'),'Offline log access must neither poll backend jobs nor start the runtime');
  assert.deepEqual(errors,[],'UI JavaScript errors');console.log('PASS: categorized rules, field errors, controller lifecycle, and both log export buttons/readers after session failure with runtime closed');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1;});
