const {chromium}=require('playwright');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert');
const root=path.resolve('app/src/main/assets/ui');
const server=http.createServer((req,res)=>{const name=req.url==='/'?'index.html':req.url.slice(1);if(!/^[\w.-]+$/.test(name)){res.writeHead(404);res.end();return;}try{res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(path.join(root,name)));}catch{res.writeHead(404);res.end();}});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.addInitScript(()=>{
   window.fixture={profile:localStorage.profile||'custom',alive:false,client:false,clientBusy:false,running:false,jobs:[],calls:[],revision:'initial',current:{era:'custom',label:'My existing rules',ruleset:3},default_ruleset:{id:7,name:'default'},delayPreview:0,delayStatus:0,previewError:'',applyError:'',tokens:{},restart:false};
   const labels={velious:'Velious',luclin:'Luclin',pop:'Planes of Power',default:'Default'};
   function state(){const f=fixture;return {profile:f.profile,running:f.running,settings:{ip:'127.0.0.1',login_port:5999,repo:'https://github.com/Russianranger/Server',ref:'main',workers:3,jobs:1},processes:{},jobs:f.jobs,source:{commit:'test'},maps_ready:true,database_imported:true,binaries_ready:true,client:{imported:true},traditional:{deployment:{},components:{},build:{}},free_bytes:50e9};}
   function status(){return {profile:'traditional',revision:fixture.revision,current:fixture.current,default_ruleset:fixture.default_ruleset,available:Object.keys(labels).map(key=>({key,label:labels[key]})),managed:[],pending_restart:fixture.restart,limitations:['Content tags are incomplete in this PEQ database.']};}
   window.Trasc={call(id,operation,input){const args=JSON.parse(input),f=fixture;f.calls.push({operation,args});setTimeout(()=>{let result={};try{
    if(operation!=='native_state'&&args.__profile&&args.__profile!==f.profile)throw Error('World profile changed');
    if(operation.startsWith('era_')&&f.profile!=='traditional')throw Error('Traditional only');
    if(operation==='native_state')result={profile:f.profile,installed:true,alive:f.alive,status:f.alive?'Runtime open':'Runtime stopped',free_bytes:50e9};
    else if(operation==='client_native_state')result={profile:f.profile,installed:true,alive:f.client,busy:f.clientBusy,status:'Client stopped',launch_options:{}};
    else if(operation==='state')result=state();
    else if(operation==='profile_switch'){localStorage.profile=args.profile;f.profile=args.profile;result={profile:f.profile};}
    else if(operation==='runtime_start')f.alive=true;
    else if(operation==='runtime_stop')f.alive=false;
    else if(operation==='era_status')result=status();
    else if(operation==='controller_state')result={sources:[],actions:[],layers:[{name:'Main',bindings:{}}],deadzone:.2,sensitivity:700};
    else if(operation==='files'||operation==='native_files')result={path:'.',items:[],total:0};
    else if(operation==='logs')result={text:'',names:['control.log']};
    else if(operation==='log_retention')result={count:5};
    else if(operation==='controller_capture')result={};
    else {
     let value={};
     if(operation==='era_preview'){
      if(f.previewError)throw Error(f.previewError);
      const token='token-'+f.calls.length;f.tokens[token]={era:args.era,revision:f.revision};
      value={review_token:token,revision:f.revision,label:labels[args.era],requires_restart:true,changes:[{scope:'active_ruleset',ruleset:args.era==='default'?7:101,rule:'World rule set',before:f.current.ruleset,after:args.era==='default'?7:101,reason:'Select the reviewed era'}, {scope:'rules',ruleset:101,rule:'Character:MaxLevel',before:'70',after:args.era==='pop'?'65':'60',reason:'Era level cap'}],zone_changes:[{id:1,zone:'qeynos',version:0,before:9,after:101}],zone_counts:{total:2,routed:2,existing_overrides:1},limitations:['Server rules do not replace era quests.'],omissions:['No full TAKP content conversion.'],manual_edits:[]};
     }
     if(operation==='era_apply'||operation==='era_restore'){
      if(f.applyError)throw Error(f.applyError);
      const token=f.tokens[args.review_token];if(!token||token.revision!==f.revision)throw Error('Database changed since review');
      const era=operation==='era_restore'?'default':args.era;
      if(operation==='era_restore'&&args.mode!=='default')throw Error('Unexpected restore mode');
      f.current={era,label:labels[era],ruleset:era==='default'?7:101};f.revision+='-saved';f.restart=true;
      value={era,ruleset_id:f.current.ruleset,message:labels[era]+' saved.',restart_required:true,backup:'backups/era/test'};
     }
     if(operation==='gameplay')value={selected:args.ruleset??f.current.ruleset,active:f.current.ruleset,active_name:f.current.label,rulesets:[{id:3,name:'My existing rules'},{id:7,name:'default'},{id:101,name:'TRASC Velious'}],metadata:{'Character:MaxLevel':{type:'int',min:1,max:255,max_length:20,description:'Level cap'}},values:{'Character:MaxLevel':{value:'60',ruleset:args.ruleset??f.current.ruleset}}};
     if(operation==='spire_catalog')value={entities:[]};
     result={id:String(f.jobs.length+1),operation,status:'done',result:value};f.jobs.push(result);
    }
    window.nativeReply(id,{ok:true,result});
   }catch(error){window.nativeReply(id,{ok:false,error:error.message});}},operation==='era_preview'?f.delayPreview:operation==='era_status'?f.delayStatus:5);}};
  });
  const sync=async updates=>{await page.evaluate(async updates=>{while(polling)await new Promise(resolve=>setTimeout(resolve,10));Object.assign(fixture,updates);await poll();},updates);};
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  await page.waitForFunction(()=>activeProfile==='custom'&&!document.getElementById('world-profile').disabled);
  await page.locator('nav [data-tab=gameplay]').click();
  assert(!(await page.locator('#era-rules-panel').isVisible()),'Custom hides era controls');
  assert.equal(await page.evaluate(()=>fixture.calls.filter(call=>call.operation.startsWith('era_')).length),0,'Custom does not probe Traditional database');
  await page.selectOption('#world-profile','traditional');await page.click('#switch-profile');await page.waitForFunction(()=>activeProfile==='traditional');
  await page.locator('nav [data-tab=gameplay]').click();assert(await page.locator('#era-rules-panel').isVisible());assert(await page.isDisabled('#era-velious'),'Closed runtime blocks era changes');
  await page.click('#runtime-open');await page.waitForFunction(()=>lastNative?.alive&&!document.getElementById('era-velious').disabled);
  await page.waitForFunction(()=>document.getElementById('era-current').textContent.includes('default (7)'));
  await page.click('#load-rules');await page.waitForFunction(()=>busy===0&&loadedRuleset===3);
  await page.click('#era-velious');await page.waitForFunction(()=>!document.getElementById('era-apply').disabled);
  assert((await page.textContent('#era-changes')).includes('Character:MaxLevel'));
  assert((await page.textContent('#era-changes')).includes('70'));
  assert((await page.textContent('#era-review-summary')).includes('2 of 2 zones'));
  assert((await page.textContent('#era-zones')).includes('qeynos'));
  assert.equal(await page.locator('#era-velious').getAttribute('aria-pressed'),'true');
  // Each live guard blocks the reviewed apply without silently changing the database.
  for(const updates of [{alive:false},{running:true},{client:true},{clientBusy:true},{jobs:[{id:'active',operation:'import_source',status:'running'}]}]){
   await sync(updates);assert(await page.isDisabled('#era-apply'));await sync({alive:true,running:false,client:false,clientBusy:false,jobs:[]});await page.waitForFunction(()=>!document.getElementById('era-apply').disabled);
  }
  await page.fill('#rule-search','MaxLevel');await page.fill('#rule-Character-MaxLevel','59');assert(await page.isDisabled('#era-apply'),'Unsaved gameplay draft blocks era replacement');
  assert((await page.textContent('#era-status')).includes('Save changed gameplay rules'));
  await page.click('#load-rules');await page.waitForFunction(()=>busy===0&&!document.getElementById('era-apply').disabled);assert.equal(await page.evaluate(()=>Object.keys(ruleDraft).length),0,'Existing reload discards manual draft explicitly');
  await page.click('#era-apply');await page.waitForFunction(()=>busy===0&&loadedRuleset===101&&document.getElementById('era-current').textContent.includes('Velious'));
  const apply=await page.evaluate(()=>fixture.calls.find(call=>call.operation==='era_apply'));
  assert.equal(apply.args.era,'velious');assert.equal(apply.args.__profile,'traditional');assert(apply.args.review_token);
  assert((await page.textContent('#era-current')).includes('Restart required'));
  await page.evaluate(()=>{fixture.current.customized=true;});await page.click('#era-refresh');await page.waitForFunction(()=>!eraReading);assert((await page.textContent('#era-current')).includes('(customized)'),'Managed manual edits remain visible');
  await page.evaluate(()=>{fixture.current.customized=false;});
  assert(await page.isDisabled('#era-apply'),'Apply consumes the review');
  await page.evaluate(async()=>{const before=loadedRuleset;let current=true;const read=loadRules(7,()=>current);current=false;await read;if(loadedRuleset!==before)throw Error('Stale gameplay read replaced the selected era rule set');});
  await page.click('#era-default');await page.waitForFunction(()=>!document.getElementById('era-apply').disabled);
  assert((await page.textContent('#era-changes')).includes('7'),'Restore previews actual named default ID');
  await page.click('#era-apply');await page.waitForFunction(()=>busy===0&&loadedRuleset===7&&document.getElementById('era-current').textContent.includes('Default'));
  const restored=await page.evaluate(()=>fixture.calls.find(call=>call.operation==='era_restore'));
  assert.equal(restored.args.mode,'default');assert.equal(await page.evaluate(()=>fixture.current.ruleset),7,'Nonzero database default is restored');
  await page.click('#era-luclin');await page.waitForFunction(()=>!document.getElementById('era-apply').disabled);
  await page.evaluate(()=>{fixture.revision='external-change';fixture.delayStatus=150;});await page.click('#era-refresh');assert(await page.isDisabled('#era-apply'),'Apply waits for a pending status refresh');await page.waitForFunction(()=>!eraReading);await page.evaluate(()=>{fixture.delayStatus=0;});
  assert(await page.isDisabled('#era-apply'),'Revision change clears prior review');assert(!(await page.locator('#era-review').isVisible()));
  assert((await page.textContent('#era-status')).includes('Database settings changed'));
  await page.click('#era-pop');await page.waitForFunction(()=>!document.getElementById('era-apply').disabled);
  await page.evaluate(()=>{fixture.revision='changed-before-apply';});await page.click('#era-apply');await page.waitForFunction(()=>busy===0);
  assert(await page.isDisabled('#era-apply'),'Backend stale-token failure requires a fresh preview');
  assert((await page.textContent('#notice')).includes('Database changed since review'));
  await page.evaluate(()=>{fixture.previewError='Preview unavailable';});await page.click('#era-pop');await page.waitForFunction(()=>busy===0);
  assert(await page.isDisabled('#era-apply'));assert(!(await page.locator('#era-review').isVisible()));
  await page.evaluate(()=>{fixture.previewError='';});await page.click('#era-pop');await page.waitForFunction(()=>!document.getElementById('era-apply').disabled);
  for(const viewport of [{width:1280,height:720},{width:393,height:852}]){
   await page.setViewportSize(viewport);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Era preview does not overflow mobile viewport');
   await page.locator('#era-zones').evaluate(element=>{element.closest('details').open=true;});
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Open routing table remains within viewport');
  }
  assert.equal(await page.locator('#launcher-theme option').count(),3,'Era UI preserves all launcher themes');
  await page.click('#era-clear');await page.evaluate(()=>{fixture.delayPreview=350;});await page.click('#era-velious');
  await page.evaluate(()=>{activeProfile='custom';lastNative.profile='custom';lastState.profile='custom';lastClientNative.profile='custom';document.body.dataset.profile='custom';fixture.profile='custom';renderEraRules();});
  await page.waitForFunction(()=>busy===0);assert(!(await page.locator('#era-review').isVisible()),'Late preview cannot leak into another profile');
  const before=await page.evaluate(()=>fixture.calls.filter(call=>call.operation.startsWith('era_')).length);
  await page.evaluate(async()=>{await refreshEraStatus();checkEraStatus();});
  assert.equal(await page.evaluate(()=>fixture.calls.filter(call=>call.operation.startsWith('era_')).length),before,'Inactive Custom profile makes no era request');
  assert.deepEqual(errors,[]);console.log('Traditional era controls: review/apply/default restore, active guards, drafts, stale responses and mobile layout passed.');
 }finally{await browser.close();server.close();}
})().catch(error=>{console.error(error);server.close();process.exitCode=1;});
