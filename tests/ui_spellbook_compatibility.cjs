const {openTab,openClientOptions,revealControl}=require('./launcher-ui-helper.cjs');
const {chromium}=require('playwright');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert');
const {execFileSync}=require('child_process');
const ui=path.resolve('app/src/main/assets/ui');
const index=fs.readFileSync(path.join(ui,'index.html'),'utf8');
const markup=index.match(/<details[^>]+id="client-spellbook-panel"[\s\S]*?<\/details>/)?.[0];
assert(markup,'Shipped HTML contains the spellbook compatibility tile');
const nativeStates=JSON.parse(execFileSync('python3',['tests/test_client_native_status.py','--fixtures'],{encoding:'utf8'}));

async function focused(browser){
 for(const profile of ['custom','traditional','takp']){
  const page=await browser.newPage({viewport:{width:393,height:852}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  let accept=true,dialogs=[];page.on('dialog',async d=>{dialogs.push(d.message());await (accept?d.accept():d.dismiss());});
  try{
   await page.setContent(`<style>${fs.readFileSync(path.join(ui,'style.css'),'utf8')}\n${fs.readFileSync(path.join(ui,'spellbook-compatibility.css'),'utf8')}</style><main>${markup.replace('<details ','<details open ')}<details id="dll-panel"><summary>Compiler</summary><button id="dll-status">Check compiler</button></details></main>`);
   await page.addScriptTag({content:`
    const $=id=>document.getElementById(id);let activeProfile=${JSON.stringify(profile)},busy=0,sessionAction=null;
    const nativeStates=${JSON.stringify(nativeStates)};
    let lastNative={profile:activeProfile,alive:true},lastClientNative=structuredClone(nativeStates[activeProfile].stopped),lastState={profile:activeProfile,running:false,source:{commit:'selected-commit'},jobs:[],client:{imported:true,files:5,bytes:100}};
    window.fixture={calls:[],notices:[],revision:1,patched:false,supported:true,error:'',hold:false,waiters:[],sourceCommit:'selected-commit',jobHold:false,jobContinue:null};
    function notice(text,error=false){fixture.notices.push({text,error});}
    function action(id,fn){$(id).addEventListener('click',async()=>{busy++;renderSpellbookCompatibilityControls();try{await fn();}catch(e){notice(e.message,true);}finally{busy--;renderSpellbookCompatibilityControls();}});}
    function tab(name){fixture.tab=name;}
    async function dllStatus(){fixture.compilerOpened=true;}
    fixture.status=()=>({profile:activeProfile,revision:'exe-'+fixture.revision,path:'client/current/eqgame.exe',sha256:'abc123',patched:fixture.patched,supported:fixture.supported,can_apply:activeProfile==='custom'&&fixture.supported,can_restore:activeProfile==='custom'&&fixture.patched,backup_exists:fixture.patched,backup_path:'backups/client-connection/spellbook/original.exe',warning:fixture.supported?'':'Unsupported executable. Expected exact qualified RoF2 SHA-256.',message:fixture.patched?'1,440-slot executable verified.':'Supported executable needs the 1,440-slot patch.',source_commit:fixture.sourceCommit,expected_slots:1440,requirements:{selected_source_commit:fixture.sourceCommit,selected_spellbook_slots:1440,deployed_source_commit:'deployed-commit',required_spellbook_slots:1440,known_deployed:true,deployed_binary_verified:true,message:'Deployed binary hash verified.'},dll:{compiler:true,runtime:true,sdk:true,source:{available:true,commit:fixture.sourceCommit,sha256:'dll-source'},freshness:{installed:{state:'stale',source_commit:'installed-old-commit',reason:'Installed DLL predates the selected source.'},staged:{state:'current',source_commit:fixture.sourceCommit,reason:'Staged build matches selected source.'}}}});
    async function api(op,args){fixture.calls.push({op,args});const result=fixture.status();if(fixture.error)throw Error(fixture.error);if(fixture.hold)return new Promise(resolve=>fixture.waiters.push(()=>resolve(result)));return result;}
    async function job(op,args){fixture.calls.push({op,args,profile:activeProfile});if(fixture.jobHold)await new Promise(resolve=>fixture.jobContinue=resolve);if(fixture.error)throw Error(fixture.error);if(args.revision!=='exe-'+fixture.revision)throw Error('Executable changed. Check compatibility again.');if(op==='client_spellbook_apply'){if(args.confirm_apply!==true)throw Error('Approval missing');fixture.patched=true;}if(op==='client_spellbook_restore'){if(args.confirm_restore!==true)throw Error('Restore approval missing');fixture.patched=false;}fixture.revision++;return {...fixture.status(),message:'Executable operation complete.'};}
   `});
   await page.addScriptTag({path:path.join(ui,'spellbook-compatibility.js')});
   await page.addScriptTag({path:path.join(ui,'controller-menu.js')});
   assert.equal(await page.isVisible('#client-spellbook-panel'),profile==='custom','Spellbook patch belongs only to Custom');
   await page.evaluate(()=>loadSpellbookCompatibility());
   if(profile!=='custom'){
    assert.equal(await page.evaluate(()=>fixture.calls.length),0,'Other profiles never request the Custom executable status');
    assert(await page.isDisabled('#client-spellbook-apply'));assert(await page.isDisabled('#client-spellbook-restore'));continue;
   }
   const idle=()=>page.waitForFunction(()=>!busy&&!spellbookCompatibilityLoading&&!spellbookCompatibilityMutating);
   assert.equal(await page.evaluate(()=>fixture.calls.filter(c=>c.op!=='client_spellbook_status').length),0,'Checking compatibility never patches');
   assert((await page.textContent('#client-spellbook-source')).includes('deployed-commit · 1440 slots verified.'),'Actual deployed proof is distinguished from selected source');
   assert((await page.textContent('#client-spellbook-dll')).includes('Rebuild required'),'Old installed DLL is called out');
   assert((await page.textContent('#client-spellbook-dll')).includes('Staged dinput8.dll: Current source build'),'Staged and installed freshness are separate');
   assert((await page.textContent('#client-spellbook-dll')).includes('Installed DLL build revision: installed-old-commit'),'Installed build provenance comes from its receipt');
   assert((await page.textContent('#client-spellbook-dll')).includes('Staged DLL build revision: selected-commit'),'Staged build provenance comes from its own receipt');
   assert((await page.textContent('#client-spellbook-dll')).includes('Selected DLL source revision: selected-commit'),'Selected source is explicitly labeled separately');
   await page.evaluate(()=>{const data=fixture.status();data.requirements.deployed_source_commit='installed-old-commit';Object.assign(data.dll.freshness.installed,{hash_verified:true,source_identity_verified:true});showSpellbookCompatibility(data);});
   assert((await page.textContent('#client-spellbook-dll')).includes('Verified for deployed server; selected source differs'),'A verified installed DLL can match the deployed server while selected source advances');
   for(const missingProof of ['hash_verified','source_identity_verified','deployed_binary_verified']){
    await page.evaluate(key=>{const data=fixture.status();data.requirements.deployed_source_commit='installed-old-commit';Object.assign(data.dll.freshness.installed,{hash_verified:true,source_identity_verified:true});if(key==='deployed_binary_verified')data.requirements[key]=false;else data.dll.freshness.installed[key]=false;showSpellbookCompatibility(data);},missingProof);
    assert(!(await page.textContent('#client-spellbook-dll')).includes('Verified for deployed server'),missingProof+' is required for deployed-server applicability');
   }
   await page.evaluate(()=>loadSpellbookCompatibility());
   accept=false;await page.click('#client-spellbook-apply');await idle();
   assert.equal(await page.evaluate(()=>fixture.calls.filter(c=>c.op==='client_spellbook_apply').length),0,'Cancel makes no mutation request');
   assert((await page.evaluate(()=>fixture.notices.at(-1).text)).includes('cancelled'));
   accept=true;await page.evaluate(()=>{fixture.jobHold=true;});await page.click('#client-spellbook-apply');
   await page.waitForFunction(()=>spellbookCompatibilityMutating&&fixture.jobContinue);
   assert(await page.isDisabled('#client-spellbook-apply'),'An active patch job cannot be submitted again');
   assert((await page.textContent('#client-spellbook-status')).includes('Keep the runtime open'),'Active executable work has a visible progress status');
   await page.evaluate(()=>{fixture.jobHold=false;fixture.jobContinue();});await idle();
   assert.deepEqual(await page.evaluate(()=>fixture.calls.find(c=>c.op==='client_spellbook_apply').args),{revision:'exe-1',confirm_apply:true},'Apply uses the inspected revision and explicit approval');
   assert(dialogs.some(x=>x.includes('compile and deploy dinput8.dll')),'Approval explains the independent DLL requirement');
   assert.equal(await page.textContent('#client-spellbook-apply'),'Verify 1,440-slot client patch');
   assert((await page.textContent('#client-spellbook-backup')).includes('backups/client-connection/spellbook/original.exe'));
   await page.click('#client-spellbook-apply');await idle();assert.equal(await page.evaluate(()=>fixture.patched),true,'Already patched state remains available to verify');
   accept=false;await page.click('#client-spellbook-restore');await idle();assert.equal(await page.evaluate(()=>fixture.patched),true,'Cancelled restore retains the executable');
   accept=true;await page.click('#client-spellbook-restore');await idle();
   assert.deepEqual(await page.evaluate(()=>fixture.calls.find(c=>c.op==='client_spellbook_restore').args),{revision:'exe-3',confirm_restore:true});
   assert(dialogs.some(x=>x.includes('may freeze this client')),'Restore explicitly warns about the expanded-server incompatibility');
   assert.equal(await page.evaluate(()=>fixture.patched),false);
   await page.click('#client-spellbook-compiler');await idle();
   assert.equal(await page.evaluate(()=>fixture.compilerOpened),true);assert(await page.evaluate(()=>document.getElementById('dll-panel').open),'Compiler action opens the existing build/deploy tile');
   await page.evaluate(()=>{fixture.supported=false;return loadSpellbookCompatibility();});
   assert(await page.isDisabled('#client-spellbook-apply'),'Unrecognized executables fail closed');
   assert((await page.textContent('#client-spellbook-status')).includes('Expected exact qualified RoF2 SHA-256'));
   await page.evaluate(()=>{fixture.supported=true;return loadSpellbookCompatibility();});
   for(const guard of ['server-running','client-running','client-busy','missing-profile','other-profile','native-install','native-session','native-saf','session-action','queued-job','ui-busy']){
    await page.evaluate(guard=>{
     if(guard==='server-running')lastState.running=true;
     if(guard==='client-running')lastClientNative=structuredClone(nativeStates.custom.running);
     if(guard==='client-busy')lastClientNative=structuredClone(nativeStates.custom.busy);
     if(guard==='missing-profile')delete lastClientNative.profile;
     if(guard==='other-profile')lastClientNative=structuredClone(nativeStates.takp.stopped);
     if(guard==='native-install')lastNative.installing=true;
     if(guard==='native-session')lastNative.session_busy=true;
     if(guard==='native-saf')lastNative.lon_input={busy:true};
     if(guard==='session-action')sessionAction='session-export-all';
     if(guard==='queued-job')lastState.jobs=[{status:'queued'}];
     if(guard==='ui-busy')busy=1;
     renderSpellbookCompatibilityControls();
    },guard);
    assert(await page.isDisabled('#client-spellbook-apply'),guard+' blocks executable mutation');
    await page.evaluate(()=>{lastState.running=false;lastState.jobs=[];lastClientNative=structuredClone(nativeStates.custom.stopped);lastNative={profile:'custom',alive:true};sessionAction=null;busy=0;renderSpellbookCompatibilityControls();});
   }
   await page.evaluate(()=>{fixture.revision++;});
   await page.click('#client-spellbook-apply');await idle();
   assert((await page.textContent('#client-spellbook-status')).includes('Executable changed'),'Revision race is shown instead of silently succeeding');
   assert.equal(await page.evaluate(()=>fixture.patched),false);
   await page.click('#client-spellbook-check');await idle();assert.equal(await page.isDisabled('#client-spellbook-apply'),false,'Explicit reload recovers from an outdated revision');
   await page.evaluate(()=>{fixture.error='Protected backup could not be verified.';});
   await page.click('#client-spellbook-apply');await idle();
   assert((await page.textContent('#client-spellbook-status')).includes('Protected backup could not be verified.'));
   await page.evaluate(()=>{fixture.error='';return loadSpellbookCompatibility();});
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Tile fits the phone viewport');
   await page.evaluate(()=>{fixture.hold=true;window.pendingSpellbook=loadSpellbookCompatibility();});
   await page.evaluate(()=>{activeProfile='traditional';lastNative.profile=activeProfile;lastClientNative=structuredClone(nativeStates.traditional.stopped);lastState.profile=activeProfile;resetSpellbookCompatibilityProfile();fixture.waiters.splice(0).forEach(resolve=>resolve());});
   await page.evaluate(()=>pendingSpellbook);
   assert.equal(await page.evaluate(()=>spellbookCompatibilityData),null,'Late responses from the old profile are discarded');
   assert.deepEqual(errors,[]);
  }finally{await page.close();}
 }
}

async function fullUi(browser){
 const server=http.createServer((req,res)=>{
  const name=req.url==='/'?'index.html':req.url.slice(1);
  if(!/^[\w.-]+$/.test(name)){res.writeHead(404);res.end();return;}
  try{res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.webp')?'image/webp':name.endsWith('.ttf')?'font/ttf':'text/html');res.end(fs.readFileSync(path.join(ui,name)));}catch{res.writeHead(404);res.end();}
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{
  for(const profile of ['custom','traditional','takp']){
   const page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
   try{
    await page.addInitScript(({profile,nativeStates})=>{
     window.fixture={profile,nativeStates,alive:false,calls:[],jobs:[],patched:false};
     const state=()=>({profile:fixture.profile,running:false,settings:{ip:'127.0.0.1',login_port:5999,repo:'fixture',ref:'main',workers:3,jobs:2},source:{commit:'current-source'},processes:{},jobs:fixture.jobs,free_bytes:50e9,nektulos:{},client:{imported:true,files:5,bytes:100}});
     const compatibility=()=>({profile:fixture.profile,revision:fixture.patched?'patched':'original',supported:true,patched:fixture.patched,can_apply:true,can_restore:fixture.patched,sha256:'supported-sha',source_commit:'current-source',expected_slots:1440,dll:{source:{commit:'current-source'},freshness:{installed:{state:'stale',reason:'Compile and deploy the current source.'},staged:{state:'missing'}}}});
     window.Trasc={call(id,op,input){setTimeout(()=>{const f=fixture,a=JSON.parse(input);let result={};f.calls.push({op,a});try{
      if(op!=='native_state'&&a.__profile&&a.__profile!==f.profile)throw Error('World profile changed');
      if(op==='native_state')result={profile:f.profile,installed:true,alive:f.alive,status:f.alive?'Runtime ready':'Runtime stopped',free_bytes:50e9};
      else if(op==='client_native_state')result=structuredClone(f.nativeStates[f.profile].stopped);
      else if(op==='runtime_start')f.alive=true;
      else if(op==='state')result=state();
      else if(op==='client_spellbook_status')result=compatibility();
      else if(op==='client_spellbook_apply'){
       if(!f.alive||f.profile!=='custom'||a.revision!=='original'||a.confirm_apply!==true)throw Error('Patch is not allowed');
       f.patched=true;result={id:'spellbook-1',operation:op,status:'done',result:{...compatibility(),message:'1,440-slot executable patch complete.'}};f.jobs.push(result);
      }
      else if(op==='controller_state')result={sources:[],actions:[],layers:[{name:'Main',bindings:{}}],deadzone:.2,sensitivity:700};
      window.nativeReply(id,{ok:true,result});
     }catch(e){window.nativeReply(id,{ok:false,error:e.message});}},5);}};
    },{profile,nativeStates});
    await page.goto(`http://127.0.0.1:${server.address().port}/`);await openTab(page,'setup');
    await page.waitForFunction(p=>activeProfile===p&&lastNative&&lastClientNative&&!polling,profile);
    assert.equal(await page.evaluate(()=>fixture.calls.filter(c=>c.op==='client_spellbook_status').length),0,'Closed runtime makes no backend compatibility request');
    await page.click('#runtime-open');
    await page.waitForFunction(()=>!busy&&!polling&&lastNative.alive);
    if(profile==='custom'){
     await page.waitForFunction(()=>spellbookCompatibilityData?.profile==='custom'&&!spellbookCompatibilityLoading&&!document.getElementById('client-spellbook-apply').disabled);
     await openTab(page,'client');await page.locator('#client-spellbook-panel > summary').click();
     assert((await page.textContent('#client-spellbook-dll')).includes('Rebuild required'));
     await page.click('#client-spellbook-apply');
     await page.waitForFunction(()=>fixture.patched&&!busy&&!spellbookCompatibilityMutating);
     const apply=await page.evaluate(()=>fixture.calls.find(c=>c.op==='client_spellbook_apply'));
     assert.deepEqual(apply.a,{revision:'original',confirm_apply:true,__profile:'custom'},'Shipped bridge sends the source-bound executable revision, owner and approval');
    }else{
     assert.equal(await page.evaluate(()=>fixture.calls.filter(c=>c.op==='client_spellbook_status').length),0,'Other profiles never inspect a Custom executable');
     assert(await page.isHidden('#client-spellbook-panel'));
    }
    assert.deepEqual(errors,[],'Full shipped UI has no script errors for '+profile);
   }finally{await page.close();}
  }
 }finally{await new Promise(resolve=>server.close(resolve));}
}

(async()=>{
 const browser=await chromium.launch({headless:true});
 try{await focused(browser);await fullUi(browser);console.log('PASS: spellbook executable and DLL provenance, explicit apply/restore approval, guarded revisions, real native/profile polling, cancellation, failures and all-profile isolation');}
 finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
