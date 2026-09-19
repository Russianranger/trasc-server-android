const {chromium}=require('playwright');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert');
const root=path.resolve('app/src/main/assets/ui');
const server=http.createServer((req,res)=>{
 const name=req.url==='/'?'index.html':req.url.slice(1);
 if(!/^[\w.-]+$/.test(name)){res.writeHead(404);res.end();return;}
 try{res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.webp')?'image/webp':name.endsWith('.ttf')?'font/ttf':'text/html');res.end(fs.readFileSync(path.join(root,name)));}catch{res.writeHead(404);res.end();}
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
   let seq=0,jobs=[],spellTest={},logRetention=5;let iniRevision='ini1',iniValues=[{section:'Defaults',key:'AllLuclinPcModelsOff',value:'FALSE'},{section:'Defaults',key:'UseLuclinHumanMale',value:'TRUE'},{section:'Defaults',key:'UseLuclinElementals',value:'TRUE'},{section:'Options',key:'MaxFPS',value:'100'},{section:'KeyMaps',key:'Custom',value:'42'}];let addonLocked=false,addonCopied=false;const addonData=()=>({snapshot:'fixture',counts:{missing:addonCopied?0:1,different:0,same:addonCopied?1:0},entries:[{path:'uifiles/default/NMS_Test.xml',status:addonCopied?'same':'missing',locked:addonLocked,protected:false}]});const actions=['None','MouseLeft','MouseRight','PointerUp','PointerDown','PointerLeft','PointerRight','KeyW','KeyT','Space','Escape'];
   let profile={sources:['A','B','L2','RightUp','RightDown','RightLeft','RightRight'],actions:[...actions,'AltLeft+Digit1','F8','ClientMenu','LayerNext','LayerPrevious','Layer1','Layer2','HoldLayer2','Layer3','HoldLayer3','Layer4','HoldLayer4'],format:2,deadzone:.2,sensitivity:700,max_layers:6};
   const base={A:'Space',B:'Escape',L2:'LayerNext',RightUp:'PointerUp',RightDown:'PointerDown',RightLeft:'PointerLeft',RightRight:'PointerRight'},inherit=Object.fromEntries(profile.sources.map(s=>[s,'Inherit']));
   profile.layers=[{name:'Main',bindings:{...base}},{name:'Spells',bindings:{...inherit,A:'AltLeft+Digit1'}}];
   profile.presets={thor:{format:2,layers:[{name:'Main',bindings:{...base,A:'F8'}},{name:'Spells',bindings:{...inherit,A:'AltLeft+Digit1'}}],deadzone:.2,sensitivity:700}};

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
    else if(op==='client_start'){window.__clientStarts.push(args);clientRuntime={...clientRuntime,alive:true,display_ready:true,launch_options:args.mode==='client'?args:clientRuntime.launch_options,launch:{phase:'launch_requested',turnip_driver_requested:args.renderer==='turnip'?args.turnip_driver:undefined,native_dinput8_requested:args.native_dinput8,native_loaded:false,native_d3dx_requested:args.native_d3dx,diagnostic_logging:args.diagnostic_logging}};result=clientRuntime;}
    else if(op==='client_view'){window.__clientViews++;result={};}
    else if(op==='client_stop'){clientRuntime.alive=false;result=clientRuntime;}
    else if(op==='state'){
     if(!window.__alive){window.nativeReply(id,{ok:false,error:'Backend is deliberately unavailable in this regression test'});return;}
     result=state();
    }
    else if(op==='session_backup'){
     window.__alive=false;window.nativeReply(id,{ok:false,error:'Session backup failed: simulated storage error. Runtime is stopped. Logs are still available; open runtime to continue.'});return;
    }
    else if(op==='log_retention'){if(args.count)logRetention=args.count;result={count:logRetention,removed_files:12,removed_bytes:4096,message:'Log retention saved. Removed 12 older logs; current logs are kept.'};}
    else if(op==='logs')result={text:args.name==='app.log'?'session_backup failed: simulated storage error':'Saved output: '+args.name,names:['app.log','runtime.log','control.log','operation.log','server/zones/cabeast.log','client/Logs/dbg.txt','client/dinput8.log']};
    else if(op==='export_logs')result={file:'exports/logs-native.zip'};
    else if(op==='export'){window.__exports.push(args.path);if(window.__cancelExport){window.nativeReply(id,{ok:false,error:'File selection cancelled'});return;}result={message:'File exported'};}
    else if(op==='client_dll_status')result={compiler:true,runtime:true,sdk:true,build:null};
    else if(op==='files'){
     const names=args.path==='client/current'?['Resources',...Array.from({length:2101},(_,i)=>'a'+String(i).padStart(4,'0')+'.txt'),'DINPUT8.dll','z-last.txt']:args.path==='client/toolchain'?['sdk.json']:['players-test.zip'];
     const all=names.filter(n=>n.toLowerCase().includes((args.query||'').trim().toLowerCase())).map(name=>({name,path:args.path+'/'+name,size:100,directory:name==='Resources'}));
     const offset=args.offset||0,limit=args.limit||2000;
     result={path:args.path,items:all.slice(offset,offset+limit),total:all.length,offset,limit,next_offset:offset+limit<all.length?offset+limit:null};
     if(window.__holdFileReply){window.__holdFileReply=false;window.__heldFileReply=()=>window.nativeReply(id,{ok:true,result});return;}
    }
    else if(op==='controller_state')result=profile;
    else if(op==='controller_save'){profile={...profile,...args};result=profile;}
    else if(op==='controller_capture'){window.clientInputEvent?.({type:'capture',down:args.active});result={...profile,active:args.active};}
    else{
     let completed={};if(op==='client_settings'||op==='client_settings_save'){
      if(op==='client_settings_save'){window.__iniChanges=args.changes;for(const c of args.changes){const e=iniValues.find(e=>e.section===c.section&&e.key===c.key);e.value=c.value;}iniRevision='ini2';}
      completed={revision:iniRevision,entries:iniValues,models:['AllLuclinPcModelsOff','UseLuclinHumanMale','UseLuclinElementals'],message:op==='client_settings_save'?'Game settings saved. Restart the client.':''};
     }else if(op==='gameplay')completed={...data,rulesets:[{id:1,name:'default'}],selected:1,active_name:'default'};
     else if(op==='export_client')completed={file:'exports/client-data.zip',local_client_synced:true,copied_files:8,message:'All four client data files overwritten in the local client root and Resources folder. Originals saved in backups/client-setup/test.'};
     else if(op==='apply_spell_test'){spellTest={state:'applied',excluded_ids:[50000,50001,50002,50003,50004,50005,50006,50007],filtered_rows:40914};completed={message:'Spell test applied: 8 high-ID entries excluded.'};}
     else if(op==='restore_spell_test'){spellTest={state:'restored'};completed={message:'Full spell files restored and verified in root and Resources.'};}
     else if(op==='client_addons_scan')completed=addonData();
     else if(op==='client_addons_lock'){addonLocked=args.locked;completed=addonData();}
     else if(op==='client_addons_copy'){if(!addonLocked)addonCopied=true;completed={comparison:addonData(),message:'Add-ons copied.'};}
     else if(op==='player_preview')completed={file:args.file,sha256:'fixture',accounts:1,characters:2,tables:3,table_names:['account','character_data','inventory'],compatible:true,problems:[],changes:[],message:'Ready to stage and validate player restore.'};
     else if(op==='player_restore')completed={message:'Player/account data restored.'};
     else if(op==='save_gameplay'){window.__saves.push(args);for(const [name,value]of Object.entries(args.values))data.values[name]={value,ruleset:1};}
     const job={id:String(++seq),operation:op,status:'done',result:completed};jobs=[job];result=job;
    }
    window.nativeReply(id,{ok:true,result});
   },5);}};
  },fixture);
  const clickDone=async id=>{await page.locator('#'+id).click();await page.waitForFunction(id=>!document.getElementById(id).disabled,id);};
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
  await page.locator('nav [data-tab=client]').click();
  assert(await page.locator('#client-launch').isVisible(),'Launch is visible without opening settings');
  assert(!(await page.locator('#client-resolution').isVisible()),'Settings start collapsed');
  await page.screenshot({path:'ui-reports/client-collapsed-mobile.png',fullPage:true});
  await page.locator('#client-options > summary').click();
  for(const [name,width,height] of [['mobile',412,915],['landscape',854,480],['wide',1280,720]]){
   await page.setViewportSize({width,height});
   await page.locator('#client-options').evaluate(el=>el.scrollIntoView({block:'start'}));
   await page.screenshot({path:'ui-reports/launch-options-'+name+'.png'});
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Launch options fit the viewport');
   await page.locator('.option-checks').evaluate(el=>el.scrollIntoView({block:'start'}));
   await page.screenshot({path:'ui-reports/launch-checkboxes-'+name+'.png'});
  }
  await page.setViewportSize({width:412,height:915});
  await page.locator('#client details').evaluateAll(ds=>ds.forEach(d=>d.open=true));
  await page.locator('#client-particles').scrollIntoViewIfNeeded();
  await page.screenshot({path:'ui-reports/particles-mobile.png'});
  await page.setViewportSize({width:960,height:540});
  await page.locator('#client-particles').scrollIntoViewIfNeeded();
  await page.screenshot({path:'ui-reports/particles-landscape.png'});
  await page.setViewportSize({width:412,height:915});
  await clickDone('game-settings-load');await page.waitForFunction(()=>!document.getElementById('game-settings-editor').hidden);
  await clickDone('game-models-classic');await clickDone('game-settings-save');
  assert.deepEqual(await page.evaluate(()=>window.__iniChanges),[{section:'Defaults',key:'AllLuclinPcModelsOff',value:'TRUE'},{section:'Defaults',key:'UseLuclinHumanMale',value:'FALSE'}],'Classic preset changes player models only');
  await page.locator('#game-other-settings details').evaluateAll(ds=>ds.forEach(d=>d.open=true));
  await page.locator('#game-settings-search').fill('MaxFPS');await page.locator('#ini-3').fill('60');await clickDone('game-settings-save');
  assert.deepEqual(await page.evaluate(()=>window.__iniChanges),[{section:'Options',key:'MaxFPS',value:'60'}],'Only edited existing INI value submitted');
  await page.screenshot({path:'ui-reports/game-settings-mobile.png',fullPage:true});

  await page.locator('#binding-A').selectOption('KeyT');await clickDone('controller-save');
  await page.waitForFunction(()=>document.getElementById('notice').textContent==='Controller bindings saved.');
  await page.locator('#controller-preset').selectOption('thor');await clickDone('controller-defaults');
  await page.waitForFunction(()=>document.getElementById('binding-A').value==='F8');
  await page.locator('#controller-layer').selectOption('1');assert.equal(await page.locator('#binding-A').inputValue(),'AltLeft+Digit1');
  await page.locator('#binding-B').selectOption('KeyT');await page.locator('#controller-layer').selectOption('0');
  await clickDone('controller-save');await page.waitForFunction(()=>document.getElementById('notice').textContent==='Controller bindings saved.');
  await clickDone('controller-load');await page.locator('#controller-layer').selectOption('1');
  await page.waitForFunction(()=>document.getElementById('binding-B').value==='KeyT');
  await page.locator('#controller-layer-name').fill('Spell gems');await clickDone('controller-rename-layer');
  await clickDone('controller-add-layer');assert.equal(await page.locator('#controller-layer').inputValue(),'2');
  await page.locator('#binding-A').selectOption('Layer1');await page.locator('#binding-B').selectOption('HoldLayer2');
  await clickDone('controller-save');await page.waitForFunction(()=>document.getElementById('notice').textContent==='Controller bindings saved.');
  await clickDone('controller-load');await page.locator('#controller-layer').selectOption('2');
  assert.equal(await page.locator('#binding-B').inputValue(),'HoldLayer2');
  await page.locator('#controller-layer').selectOption('1');assert.equal(await page.locator('#controller-layer-name').inputValue(),'Spell gems');
  await clickDone('controller-remove-layer');assert.equal(await page.locator('#binding-B').inputValue(),'None','Removing a layer clears bindings targeting it');
  await page.locator('#controller-layer').selectOption('0');
  assert.equal(await page.locator('#binding-L2').inputValue(),'LayerNext');
  await page.locator('#client-dxvk-hud').uncheck();
  await page.locator('#client-presentation').selectOption('native_surface');await page.locator('#client-display-fps').selectOption('60');
  await page.locator('#controller-capture').click();await page.waitForFunction(()=>document.getElementById('controller-focus').textContent.includes('captured'));
  await page.evaluate(()=>{window.clientInputEvent({type:'button',action:'KeyT',down:true});window.clientInputEvent({type:'pointer',x:90,y:20});window.clientInputEvent({type:'layer',x:1,action:'Spell gems'});});
  assert((await page.locator('#client-input-status').textContent()).includes('KeyT'));
  assert((await page.locator('#controller-active-layer').textContent()).includes('2 · Spell gems'));
  const toolbar=await page.locator('.runtime-toolbar').boundingBox();assert(toolbar.y>=0&&toolbar.y+toolbar.height<915,'Runtime controls remain in the viewport while scrolled');
  await page.screenshot({path:'ui-reports/client-mobile.png',fullPage:true});
  await page.locator('#addons-scan').click();
  await page.waitForFunction(()=>document.getElementById('addons-status').textContent.includes('1 missing'));
  await page.locator('#addons-list button', {hasText:'Lock'}).click();
  await page.waitForFunction(()=>document.getElementById('addons-list').textContent.includes('locked'));
  assert.equal(await page.locator('#addons-list button[data-copy]').count(),0,'Locked files cannot be individually copied');
  await page.locator('#addons-list button', {hasText:'Unlock'}).click();
  await page.waitForFunction(()=>document.querySelector('#addons-list button[data-copy]'));
  await page.locator('#addons-list button[data-copy]').click();
  await page.waitForFunction(()=>document.getElementById('addons-status').textContent.includes('0 missing'));
  await page.locator('#dll-status').click();
  await page.waitForFunction(()=>document.getElementById('dll-state').textContent.includes('SDK imported'));
  await page.locator('#spell-test-apply').click();
  await page.waitForFunction(()=>document.getElementById('spell-test-status').textContent.includes('40914 rows'));
  await page.waitForFunction(()=>!document.getElementById('spell-test-restore').disabled);
  for(const id of ['spell-test-apply','client-import'])assert(await page.locator('#'+id).isDisabled(),'Active compatibility protects '+id);
  for(const id of ['client-prepare','export-client'])assert(!(await page.locator('#'+id).isDisabled()),'Active compatibility allows '+id);
  assert((await page.locator('#spell-excluded-list').textContent()).includes('50007'));
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
  assert.deepEqual(await page.evaluate(()=>window.__clientStarts[0]),{boat_mode:'off',particle_mode:'off',reduce_load_pauses:false,fast_spell_parse:false,mouse_warp:false,dxvk_hud:false,presentation_mode:'native_surface',display_fps:60,turnip_driver:'24.3.4',sound_diagnostics:false,audio:true,npc_rendering:'compatibility',mode:'desktop',resolution:'960x540',fullscreen:false,native_dinput8:true,diagnostic_logging:false,native_d3dx:false,renderer:'software',cpu_profile:'balanced',runtime_mode:'auto',graphics_threading:'multi',cpu_affinity:'available'});
  assert(!(await page.locator('#client-launch-status').textContent()).includes('load confirmed'),'File presence/request must not claim DLL loaded');
  await page.locator('#client-stop').click();await page.waitForFunction(()=>document.getElementById('client-launch-status').textContent.startsWith('Client stopped.'));
  await page.locator('#client-renderer').selectOption('virgl');
  await page.locator('#client-mouse-warp').check();
  await page.locator('#client-fast-spells').check();
  await page.locator('#client-load-pauses').check();
  assert.equal(await page.locator('#client-particles').inputValue(),'off');
  assert.equal(await page.locator('#client-boats').inputValue(),'off');await page.locator('#client-boats').selectOption('profile');
  await page.locator('#client-particles').selectOption('repair');
  await page.locator('#client-launch').click();await page.waitForFunction(()=>window.__clientViews===2);
  assert.equal(await page.evaluate(()=>window.__clientStarts[1].mode),'client');
  assert.equal(await page.evaluate(()=>window.__clientStarts[1].mouse_warp),true);
  assert.equal(await page.evaluate(()=>window.__clientStarts[1].fast_spell_parse),true);
  assert.equal(await page.evaluate(()=>window.__clientStarts[1].boat_mode),'profile');
  assert.equal(await page.evaluate(()=>window.__clientStarts[1].particle_mode),'repair');
  assert.equal(await page.evaluate(()=>window.__clientStarts[1].reduce_load_pauses),true);
  await page.evaluate(async()=>{document.getElementById('client-mouse-warp').checked=false;launchOptionsLoaded=false;await clientRuntimeState();});
  assert(await page.locator('#client-mouse-warp').isChecked(),'Saved mouse recentering survives reload');
  await page.locator('#client-mouse-warp').uncheck();
  assert(await page.locator('#client-fast-spells').isChecked(),'Saved faster spell loading survives reload');
  await page.locator('#client-fast-spells').uncheck();
  assert(await page.locator('#client-load-pauses').isChecked(),'Saved loading pause option survives reload');
  await page.locator('#client-load-pauses').uncheck();
  assert.equal(await page.locator('#client-particles').inputValue(),'repair','Saved particle choice survives reload');
  await page.locator('#client-particles').selectOption('profile');
  await page.evaluate(async()=>{window.__clientEvidence({particle_mode:'profile'});await clientRuntimeState();});
  assert((await page.locator('#client-launch-status').textContent()).includes('Particle diagnostics only'));
  assert.equal(await page.locator('#client-boats').inputValue(),'profile','Saved boat diagnostics survive reload');
  await page.evaluate(async()=>{window.__clientEvidence({boat_mode:'profile'});await clientRuntimeState();});assert((await page.locator('#client-launch-status').textContent()).includes('Boat diagnostics active'));
  await page.locator('#client-boats').selectOption('off');
  await page.locator('#client-particles').selectOption('off');
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
  assert.deepEqual(await page.evaluate(()=>window.__clientStarts[2]),{boat_mode:'off',particle_mode:'off',reduce_load_pauses:false,fast_spell_parse:false,mouse_warp:false,dxvk_hud:false,presentation_mode:'native_surface',display_fps:60,turnip_driver:'24.3.4',sound_diagnostics:false,audio:true,npc_rendering:'compatibility',mode:'desktop',resolution:'960x540',fullscreen:false,native_dinput8:true,diagnostic_logging:true,native_d3dx:false,repair_prefix:true,renderer:'software',cpu_profile:'compatibility',runtime_mode:'compatibility',graphics_threading:'opengl_worker',cpu_affinity:'available'});
  assert((await page.locator('#client-launch-status').textContent()).includes('Verbose diagnostics enabled'));
  await page.locator('#client-stop').click();
  await page.waitForFunction(()=>document.getElementById('client-launch-status').textContent.startsWith('Client stopped.'));
  await page.locator('#client-resolution').selectOption('1280x720');
  await page.locator('#client-fullscreen').check();
  await page.locator('#client-renderer').selectOption('turnip');
  assert.equal(await page.locator('#client-turnip-driver').inputValue(),'24.3.4');
  await page.locator('#client-turnip-driver').selectOption('26.0.0');
  await page.screenshot({path:'ui-reports/turnip-driver-mobile.png',fullPage:true});
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
  assert.equal(await page.evaluate(()=>window.__clientStarts[3].turnip_driver),'26.0.0');
  assert(await page.locator('#client-turnip-driver').isDisabled(),'Stop before switching a running driver');
  assert((await page.locator('#client-launch-status').textContent()).includes('Turnip 26.0.0'));
  assert.equal(await page.evaluate(()=>window.__clientStarts[3].resolution),'1280x720');
  assert.equal(await page.evaluate(()=>window.__clientStarts[3].fullscreen),true);
  assert.equal(await page.evaluate(()=>window.__clientStarts[3].cpu_affinity),'game');
  await page.locator('#client-stop').click();await page.waitForFunction(()=>document.getElementById('client-launch-status').textContent.startsWith('Client stopped.'));
  await page.evaluate(async()=>{document.getElementById('client-turnip-driver').value='24.3.4';launchOptionsLoaded=false;await clientRuntimeState();});
  assert.equal(await page.locator('#client-turnip-driver').inputValue(),'26.0.0','Saved driver survives settings reload');
  await page.locator('#client-turnip-driver').selectOption('24.3.4');
  await page.locator('#client-fullscreen').uncheck();
  await page.locator('#client-renderer').selectOption('virgl');
  assert(!(await page.locator('#client-graphics-threading').isDisabled()),'WineD3D recovery restores threading controls');
  assert(await page.locator('#client-turnip-driver').isDisabled(),'Turnip selection does not apply to VirGL');
  await page.locator('nav [data-tab=setup]').click();await page.waitForFunction(()=>document.getElementById('controller-focus').textContent==='Controller capture is off.');
  assert(!(await page.locator('#client-input-status').textContent()).includes('KeyT'),'Leaving tab releases input');
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'No horizontal page overflow on mobile');
  await page.setViewportSize({width:960,height:540});await page.screenshot({path:'ui-reports/setup-landscape.png',fullPage:true});
  await page.locator('nav [data-tab=database]').click();
  await page.locator('#players-local').click();
  await page.locator('#players-review').click();
  await page.waitForFunction(()=>document.getElementById('players-preview').textContent.includes('2 characters'));
  assert(await page.locator('#players-restore').isDisabled(),'Player restore requires reviewed replacement selection');
  await page.locator('#players-replace').check();
  await page.locator('#players-restore').click();
  await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('Player/account data restored'));
  await page.screenshot({path:'ui-reports/player-data-mobile.png',fullPage:true});
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
  await page.locator('nav [data-tab=logs]').click();
  await page.waitForFunction(()=>document.getElementById('log-retention').value==='5');
  for(const count of ['2','3','4','5']) {
    await page.locator('#log-retention').selectOption(count);await page.locator('#save-log-retention').click();
    await page.waitForFunction(()=>document.getElementById('log-retention-status').textContent.includes('Removed 12'));
    await page.locator('nav [data-tab=server]').click();await page.locator('nav [data-tab=logs]').click();
    await page.waitForFunction(value=>document.getElementById('log-retention').value===value,count);
  }
  await page.screenshot({path:'ui-reports/log-retention-mobile.png',fullPage:true});
  await page.locator('#log-name').selectOption('operation.log');
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
  await page.locator('#runtime-open').click();await page.waitForFunction(()=>window.__alive);
  await page.locator('nav [data-tab=files]').click();
  await page.locator('#file-path').fill('client/current');await page.locator('#file-path').press('Enter');
  await page.waitForFunction(()=>document.getElementById('file-results').textContent==='1–200 of 2104 entries');
  assert(await page.locator('#file-prev').isDisabled());
  for(let n=1;n<=10;n++){
   await page.locator('#file-next').click();
   await page.waitForFunction(start=>document.getElementById('file-results').textContent.startsWith(start+'–'),n*200+1);
  }
  assert(await page.locator('#file-next').isDisabled());
  assert((await page.locator('#file-list').textContent()).includes('z-last.txt'),'Files beyond 2,000 are reachable');
  await page.locator('#file-prev').click();await page.waitForFunction(()=>document.getElementById('file-results').textContent.startsWith('1801–'));
  await page.locator('#file-search').fill('DiNpUt');await page.locator('#file-search').press('Enter');
  await page.waitForFunction(()=>document.getElementById('file-results').textContent==='1–1 of 1 matches');
  await page.locator('#file-list button').click();await page.locator('#file-export').click();
  await page.waitForFunction(()=>window.__exports.at(-1)==='client/current/DINPUT8.dll');
  await page.setViewportSize({width:412,height:915});
  await page.screenshot({path:'ui-reports/file-search-mobile.png',fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'File search fits mobile width');
  await page.locator('#file-search').fill('missing');
  assert.equal(await page.locator('#selected-file').inputValue(),'','Changed search clears old export selection');
  await page.locator('#file-search-go').click();await page.waitForFunction(()=>document.getElementById('file-results').textContent.startsWith('No matching'));
  assert(await page.locator('#file-prev').isDisabled()&&await page.locator('#file-next').isDisabled());
  await page.locator('#file-search-clear').click();await page.waitForFunction(()=>document.getElementById('file-results').textContent==='1–200 of 2104 entries');
  // A slow response for the previous folder must not replace current results.
  await page.evaluate(()=>window.__holdFileReply=true);
  await page.locator('#file-search').fill('dinput');await page.locator('#file-search-go').click();
  await page.waitForFunction(()=>typeof window.__heldFileReply==='function');
  await page.locator('#file-path').fill('client/toolchain');await page.locator('#file-search').fill('SDK.JSON');
  await page.locator('#file-search-go').click();await page.waitForFunction(()=>document.getElementById('file-list').textContent.includes('sdk.json'));
  await page.evaluate(()=>window.__heldFileReply());
  assert.equal(await page.locator('#file-path').inputValue(),'client/toolchain');
  assert(!(await page.locator('#file-list').textContent()).includes('DINPUT8.dll'));
  await page.locator('#file-list button').click();await page.locator('#file-export').click();
  await page.waitForFunction(()=>window.__exports.at(-1)==='client/toolchain/sdk.json');
  await page.setViewportSize({width:960,height:540});await page.screenshot({path:'ui-reports/file-search-landscape.png',fullPage:true});
  assert.deepEqual(errors,[],'UI JavaScript errors');console.log('PASS: management, controller, offline logs, full-folder search/pagination/export and stale-response protection');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1;});
