const {openTab,openClientOptions,revealControl}=require('./launcher-ui-helper.cjs');
const {chromium}=require('playwright');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert');
const root=path.resolve('app/src/main/assets/ui');
const server=http.createServer((req,res)=>{
 const name=req.url==='/'?'index.html':req.url.slice(1);
 if(!/^[\w.-]+$/.test(name)){res.writeHead(404);res.end();return;}
 try{res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.webp')?'image/webp':'text/html');res.end(fs.readFileSync(path.join(root,name)));}catch{res.writeHead(404);res.end();}
});

(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
   const f=window.fixture={profile:localStorage.takpWorld||'custom',alive:false,client:false,busy:false,jobs:[],calls:[],source:false,quests:false,maps:false,initialized:false,bots:false,accounts:0,staged:false,deployed:false,imported:false,prepared:false};
   f.state=()=>({profile:f.profile,version:'0.6.25',running:f.running||false,
    settings:{ip:'127.0.0.1',login_port:f.profile==='takp'?6000:5999,repo:f.profile==='takp'?'https://github.com/Russianranger/Servertakp':f.profile==='traditional'?'https://github.com/Russianranger/Server':'https://github.com/Russianranger/Triptych-Triumvirate',ref:f.profile==='takp'?'03e934d0fdf460e2e6ce34c0a25a3e05d9f7e167':'main',maps_url:f.profile==='takp'?'https://github.com/Russianranger/Mapstakp':'https://github.com/Akkadius/EQEmuMaps',workers:1,jobs:2},
    processes:{},jobs:f.jobs,source:f.source?{commit:'03e934d0fdf460e2e6ce34c0a25a3e05d9f7e167'}:{},maps_ready:f.maps,database_imported:f.initialized,build_ready:f.staged,binaries_ready:f.deployed,
    client:{imported:f.imported,prepared:f.prepared},free_bytes:50e9,
    traditional:{build:{},components:{}},
    takp:{source_ready:f.source,quests_ready:f.quests,maps_ready:f.maps,database_ready:f.initialized,bot_schema_ready:f.bots,local_accounts:f.accounts,login_port:6000,
     components:{quests:{imported:f.quests,source:{commit:'f43d4fcfa89fecd76b5ac3fb5096f8d658a6c65f'}},maps:{imported:f.maps,source:{commit:'95cb9322b853e7ec2f67158b87442286315042eb'}},assets:{imported:f.source}},
     build:{runtime_ready:true,build_allowed:f.source&&!f.running,staged_valid:f.staged,deployed_valid:f.deployed,message:f.source?'TAKP ARM64 source qualified.':'Import the tested TAKP source first.'},
     deployment:{deploy_allowed:f.staged&&f.initialized&&f.bots&&f.quests&&f.maps&&!f.running,start_allowed:f.deployed&&f.initialized&&f.bots&&f.accounts>0&&!f.running,client_data_allowed:f.deployed&&f.initialized&&f.bots,rollback_allowed:f.deployed,deployed_valid:f.deployed,message:f.deployed?'TAKP build deployed.':f.staged?'Initialize the TAKP database, then deploy.':'Compile the TAKP source first.'},message:'TAKP fixture readiness'}});
   window.Trasc={call(id,op,input){setTimeout(()=>{const a=JSON.parse(input);f.calls.push({op,a});let result={};try{
    if(op!=='native_state'&&a.__profile&&a.__profile!==f.profile)throw Error('World profile changed');
    if(op==='native_state')result={profile:f.profile,installed:true,alive:f.alive,installing:false,session_busy:false,status:'Runtime stopped',free_bytes:50e9};
    else if(op==='client_native_state')result={profile:f.profile,installed:true,alive:f.client,busy:f.busy,status:'Client stopped',launch_options:{...(localStorage.takpCpu?{cpu_profile:localStorage.takpCpu}:{}),native_dinput8:true,native_d3dx:true,mouse_warp:true,fast_spell_parse:true,reduce_load_pauses:true,name_sky_compatibility:true}};
    else if(op==='profile_switch'){if(f.alive||f.client||f.busy)throw Error('Stop runtime and client before switching');localStorage.takpWorld=a.profile;f.profile=a.profile;result={profile:f.profile};}
    else if(op==='runtime_start'){f.alive=true;result={};}
    else if(op==='runtime_stop'){f.alive=false;result={};}
    else if(op==='state')result=f.state();
    else if(op==='controller_state')result={sources:[],actions:[],layers:[{name:'Main',bindings:{}}],deadzone:.2,sensitivity:700};
    else if(op==='files'||op==='native_files')result={path:'.',items:[],total:0,offset:0,next_offset:null};
    else if(op==='logs')result={text:'TAKP profile log',names:['control.log']};
    else if(op==='log_retention')result={count:5};
    else if(op==='pick')result={file:'takp-client.zip'};
    else if(op==='controller_capture')result={};
    else{
     let value={};
     if(op==='spire_catalog')value={entities:[]};
     if(op==='takp_setup'){f.source=f.quests=f.maps=true;value={message:'TAKP server, quests and maps prepared.'};}
     if(op==='update_checklist_scan')value={profile:'takp',scanned_at:Date.now()/1000,source:{revision:'03e934d0fdf460e2e6ce34c0a25a3e05d9f7e167'},rows:[{id:'quests',label:'Quests',state:'review',detail:'Review quest revision.',action:{target:'takp-setup'}},{id:'maps',label:'Maps',state:'review',detail:'Review independent map revision.',action:{target:'takp-setup'}}]};
     if(op==='import_content'){if(f.running||f.client||f.busy)throw Error('Content import while running');if(!a.replace)throw Error('Replacement not approved');if(a.kind==='quests')f.quests=true;else if(a.kind==='maps')f.maps=true;else throw Error('Unsupported TAKP content');value={message:'TAKP '+a.kind+' imported.',backup:'backups/takp-'+a.kind+'-fixture'};}

     if(op==='build'){f.staged=true;value={staged:true,message:'Nine TAKP binaries compiled and staged.'};}
     if(op==='takp_initialize_database'){f.initialized=f.bots=true;value={message:'TAKP database initialized; eleven bot migrations verified.'};}
     if(op==='takp_create_account'){f.accounts++;value={message:'Local TAKP account created.'};}
     if(op==='deploy'){f.deployed=true;value={message:'TAKP build deployed.'};}
     if(op==='start'){f.running=true;value={message:'TAKP server started.'};}
     if(op==='stop'){f.running=false;value={message:'TAKP server stopped.'};}
     if(op==='import_client_zip'){f.imported=true;value={message:'TAKP client imported.'};}
     if(op==='prepare_client'){f.prepared=true;value={message:'TAKP client prepared.'};}
     result={id:String(f.jobs.length+1),operation:op,status:'done',result:value};f.jobs.push(result);
    }
    window.nativeReply(id,{ok:true,result});
   }catch(e){window.nativeReply(id,{ok:false,error:e.message});}},5);}};
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/`);await openTab(page,'setup');
  await page.waitForFunction(()=>!document.getElementById('world-profile').disabled&&!polling);
  const profiles=await page.locator('#world-profile option').allTextContents();
  assert(profiles.some(label=>label.includes('TAKP')),'TAKP appears alongside Custom and Traditional');
  assert.equal(profiles.length,3);
  await page.selectOption('#world-profile','takp');await page.click('#switch-profile');
  await page.waitForFunction(()=>activeProfile==='takp'&&document.body.dataset.profile==='takp'&&!polling);
  assert.equal(await page.inputValue('#source-url'),'https://github.com/Russianranger/Servertakp');
  assert.equal(await page.inputValue('#source-ref'),'03e934d0fdf460e2e6ce34c0a25a3e05d9f7e167');
  assert.equal(await page.inputValue('#maps-url'),'https://github.com/Russianranger/Mapstakp');
  await openTab(page,'setup');assert(await page.locator('#takp-setup').isVisible());
  for(const id of ['source-git','maps-git','import-db'])assert(!(await page.locator('#'+id).isVisible()),'Generic import control is hidden for TAKP: '+id);
  await openTab(page,'server');
  const endpointLabel=await page.locator('#login-endpoint-label').textContent();
  assert(endpointLabel.includes('TAKP')&&endpointLabel.includes('UDP'),'TAKP connection copy identifies its legacy UDP endpoint');
  assert.deepEqual(await page.locator('#client-export-files li').allTextContents(),['spells_us.txt','SkillCaps.txt'],'TAKP exports exactly its two legacy client data files');
  await openTab(page,'client');await openClientOptions(page);
  for(const id of ['client-native-dll','client-fast-spells','client-load-pauses','client-mouse-warp']){
   assert(await page.isDisabled('#'+id),'RoF2 adapter blocked for TAKP: '+id);
   assert(!(await page.isChecked('#'+id)),'RoF2 adapter forced off for TAKP: '+id);
  }
  const options=await page.evaluate(()=>launchOptions('client'));
  assert.equal(options.cpu_profile,'accurate','Fresh TAKP settings use the device-confirmed math mode');
  assert((await page.textContent('#client-cpu-help')).includes('restored visible TAKP NPC models'));
  for(const key of ['native_dinput8','fast_spell_parse','reduce_load_pauses','mouse_warp'])assert.equal(options[key],false);
  await openTab(page,'fixes');
  assert(!(await page.locator('#ferry-service-panel').isVisible()),'RoF2 ferry controls stay hidden');
  assert(!(await page.locator('nav [data-tab=spire]').isVisible()),'PEQ Spire editing is hidden for TAKP');
  await openTab(page,'gameplay');
  assert(!(await page.locator('#era-rules-panel').isVisible()),'Traditional PEQ era rules stay hidden for TAKP');
  await openTab(page,'setup');await page.click('#runtime-open');
  await page.waitForFunction(()=>lastNative?.alive&&!polling);
  assert(await page.isDisabled('#world-profile'),'Active TAKP runtime blocks profile switching');
  assert(await page.isDisabled('#build-server'),'Missing TAKP source blocks compilation');
  assert(await page.isDisabled('#deploy-build'));
  assert(await page.isDisabled('#start-server'));
  await page.click('#takp-setup');await page.waitForFunction(()=>lastState?.takp?.source_ready&&!polling&&!busy);
  await openTab(page,'build');
  assert(await page.isDisabled('#takp-setup'),'First setup remains disabled after world components are installed');
  assert.equal(await page.locator('#takp-content-refresh').evaluate(element=>element.parentElement.id),'build','Content refresh stays outside first-build tools');
  await page.click('#update-checklist-scan');await page.waitForFunction(()=>document.getElementById('update-row-maps')&&!busy);
  await page.click('#update-row-maps');assert.equal(await page.inputValue('#takp-content-kind'),'maps','Map checklist review selects refreshable maps');
  assert(await page.isVisible('#takp-content-url'));assert.equal(await page.inputValue('#takp-content-ref'),'95cb9322b853e7ec2f67158b87442286315042eb');
  assert.equal(await page.evaluate(()=>fixture.calls.filter(c=>c.op==='import_content').length),0,'Checklist Review only navigates; it never imports');
  await page.evaluate(()=>navigateToControl('update-checklist'));await page.click('#update-row-quests');
  assert.equal(await page.inputValue('#takp-content-kind'),'quests','Quest checklist review selects quests');
  assert.equal(await page.inputValue('#takp-content-url'),'https://github.com/Russianranger/queststakp');
  assert.equal(await page.inputValue('#takp-content-ref'),'f43d4fcfa89fecd76b5ac3fb5096f8d658a6c65f');
  assert(await page.isDisabled('#takp-content-git'));assert(await page.isDisabled('#takp-content-zip'));
  assert((await page.evaluate(()=>refreshTakpContent().catch(error=>error.message))).includes('Select replacement'),'Unchecked replacement also rejected by handler guard');
  assert.equal(await page.evaluate(()=>fixture.calls.filter(c=>c.op==='import_content').length),0);
  await page.check('#takp-content-replace');assert(!(await page.isDisabled('#takp-content-git')));
  for(const flag of ['running','client','busy']){
   await page.evaluate(async key=>{while(polling)await new Promise(r=>setTimeout(r,10));fixture[key]=true;await poll();},flag);
   assert(await page.isDisabled('#takp-content-git'),'Content refresh blocked while '+flag);assert(await page.isDisabled('#takp-content-zip'));
   assert((await page.evaluate(()=>refreshTakpContent().catch(error=>error.message))).includes('stop the server and client'),'Handler rejects blocked refresh');
   await page.evaluate(async key=>{while(polling)await new Promise(r=>setTimeout(r,10));fixture[key]=false;await poll();},flag);
  }
  await page.click('#takp-content-git');await page.waitForFunction(()=>fixture.calls.some(c=>c.op==='import_content')&&!polling&&!busy);
  const questsRefresh=await page.evaluate(()=>fixture.calls.find(c=>c.op==='import_content'));
  assert.equal(questsRefresh.a.__profile,'takp');assert.equal(questsRefresh.a.kind,'quests');assert.equal(questsRefresh.a.replace,true);
  assert.equal(questsRefresh.a.url,'https://github.com/Russianranger/queststakp');assert.equal(questsRefresh.a.ref,'f43d4fcfa89fecd76b5ac3fb5096f8d658a6c65f');
  assert(!(await page.isChecked('#takp-content-replace')),'Replacement approval clears after each import');
  assert((await page.textContent('#takp-content-result')).includes('backups/takp-quests-fixture'));
  await page.selectOption('#takp-content-kind','maps');assert.equal(await page.inputValue('#takp-content-url'),'https://github.com/Russianranger/Mapstakp');
  await page.check('#takp-content-replace');await page.fill('#takp-content-ref','reviewed-map-branch');
  assert(!(await page.isChecked('#takp-content-replace')),'Changing source revision clears approval');
  await page.check('#takp-content-replace');await page.click('#takp-content-zip');
  await page.waitForFunction(()=>fixture.calls.filter(c=>c.op==='import_content').length===2&&!polling&&!busy);
  const mapRefresh=await page.evaluate(()=>fixture.calls.filter(c=>c.op==='import_content').at(-1));
  assert.equal(mapRefresh.a.kind,'maps');assert.equal(mapRefresh.a.replace,true);assert.equal(mapRefresh.a.file,'takp-client.zip');
  assert.equal(mapRefresh.a.url,undefined,'Offline refresh uses the chosen ZIP');
  assert.deepEqual(await page.locator('#takp-content-kind option').evaluateAll(options=>options.map(option=>option.value)),['quests','maps'],'Unsupported asset refresh is not offered');
  await page.waitForFunction(()=>!document.getElementById('build-server').disabled);
  await page.click('#build-server');await page.waitForFunction(()=>lastState?.takp?.build?.staged_valid&&!polling&&!busy);
  assert(await page.isDisabled('#deploy-build'),'Compiled TAKP source requires its initialized database');
  await openTab(page,'setup');await page.click('#takp-initialize');
  await page.waitForFunction(()=>lastState?.takp?.bot_schema_ready&&!polling&&!busy);
  await openTab(page,'build');await page.waitForFunction(()=>!document.getElementById('deploy-build').disabled);
  await page.click('#deploy-build');await page.waitForFunction(()=>lastState?.takp?.deployment?.deployed_valid&&!polling&&!busy);
  assert(await page.isDisabled('#start-server'),'A local login account is required for TAKP startup');
  await openTab(page,'setup');
  await page.fill('#takp-username','Thorbot');await page.fill('#takp-password','fixture-password');await page.click('#takp-create-account');
  await page.waitForFunction(()=>lastState?.takp?.local_accounts===1&&!polling&&!busy);
  assert.equal(await page.inputValue('#takp-password'),'','Account password is cleared after submission');
  const account=await page.evaluate(()=>fixture.calls.find(call=>call.op==='takp_create_account'));
  assert.equal(account.a.__profile,'takp');
  assert.equal(account.a.username,'Thorbot');assert.equal(account.a.password,'fixture-password');
  await openTab(page,'server');assert(!(await page.isDisabled('#start-server')));
  await page.click('#start-server');await page.waitForFunction(()=>lastState?.running&&!polling&&!busy);
  assert(await page.isDisabled('#takp-initialize'),'Running TAKP server blocks database initialization');
  await page.click('#stop-server');await page.waitForFunction(()=>!lastState?.running&&!polling&&!busy);
  await openTab(page,'client');
  assert(!(await page.isDisabled('#export-client')),'TAKP exports are enabled only with a deployed database');
  assert(await page.isDisabled('#client-prepare'),'Full client import is required for preparation');
  await page.click('#client-import-title');
  await page.click('#client-import');await page.waitForFunction(()=>lastState?.client?.imported&&!polling&&!busy);
  assert(!(await page.isDisabled('#client-prepare')));
  await page.evaluate(async()=>{while(polling)await new Promise(r=>setTimeout(r,10));fixture.busy=true;await poll();});
  assert(await page.isDisabled('#client-prepare'),'Active client preparation/launch blocks changes');
  assert(await page.isDisabled('#world-profile'));
  await page.evaluate(async()=>{while(polling)await new Promise(r=>setTimeout(r,10));fixture.busy=false;await poll();});
  fs.mkdirSync('ui-reports',{recursive:true});
  for(const theme of ['default','necromancer','monk']){
   await page.selectOption('#launcher-theme',theme);
   for(const viewport of [{width:1280,height:720},{width:393,height:852}]){
    await page.setViewportSize(viewport);
    for(const tab of ['setup','build','server','client']){
     await openTab(page,tab);await page.evaluate(()=>scrollTo(0,0));
     assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'TAKP profile has horizontal overflow');
     if(theme==='default')await page.screenshot({path:`ui-reports/takp-${tab}-${viewport.width}.png`,fullPage:true});
    }
   }
  }
  await openTab(page,'setup');await page.click('#runtime-close');
  await page.waitForFunction(()=>!lastNative?.alive&&!document.getElementById('world-profile').disabled&&!polling);
  await page.selectOption('#world-profile','custom');await page.click('#switch-profile');
  await page.waitForFunction(()=>activeProfile==='custom'&&!polling);
  assert.equal(await page.inputValue('#source-url'),'https://github.com/Russianranger/Triptych-Triumvirate');
  assert(!(await page.locator('#takp-setup').isVisible()),'TAKP controls are scoped to TAKP');
  assert(!(await page.locator('#takp-content-refresh').isVisible()),'TAKP refresh stays hidden in other profiles');
  assert.equal(await page.inputValue('#client-cpu-profile'),'balanced','Custom retains its existing default');
  await page.evaluate(()=>{localStorage.takpWorld='takp';localStorage.takpCpu='balanced';});
  await page.reload();await page.waitForFunction(()=>activeProfile==='takp'&&!polling&&launchOptionsLoaded);
  assert.equal(await page.inputValue('#client-cpu-profile'),'balanced','Explicit saved TAKP comparison choices are retained');
  assert.deepEqual(errors,[]);
  console.log('PASS: TAKP third profile, pinned forks, blocked RoF2 hooks, staged/seed/account/deploy readiness, password clearing, busy guards, deliberate installed-content refresh and all launcher themes at Thor/phone sizes');
 }finally{await browser.close();server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;server.close();});
