const {chromium}=require('playwright');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert');
const {execFileSync}=require('child_process');
// Exercise the exact state emitted by the Java runtime, rather than constructing
// a frontend-only shape that can silently hide missing bridge fields.
const nativeStates=JSON.parse(execFileSync('python3',['tests/test_client_native_status.py','--fixtures'],{encoding:'utf8'}));
const ui=path.resolve('app/src/main/assets/ui');
const index=fs.readFileSync(path.join(ui,'index.html'),'utf8');
const markup=['client-connection-panel','client-4gb-panel'].map(id=>{
 const match=index.match(new RegExp('<details[^>]+id="'+id+'"[\\s\\S]*?</details>'));
 assert(match,'Client panel exists in shipped HTML: '+id);return match[0].replace('<details ','<details open ');
}).join('');
async function checkFullUiPolling(browser){
 const server=http.createServer((req,res)=>{
  const name=req.url==='/'?'index.html':req.url.slice(1);
  if(!/^[\w.-]+$/.test(name)){res.writeHead(404);res.end();return;}
  try{res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.webp')?'image/webp':name.endsWith('.ttf')?'font/ttf':'text/html');res.end(fs.readFileSync(path.join(ui,name)));}catch{res.writeHead(404);res.end();}
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{
  for(const profile of ['custom','traditional','takp']){
   const page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
   try{
    await page.addInitScript(({profile,nativeStates})=>{
     window.fixture={profile,nativeStates,alive:false,mode:'stopped',calls:[],jobs:[],downloaded:false};
     const connection=()=>({profile:fixture.profile,host:{host:'127.0.0.1',port:5999,exists:true,backup_exists:false,can_save:true,can_restore:false,revision:'host-1',path:'eqhost.txt'},patch:{eligible:fixture.profile==='custom',exe:'eqgame.exe',patched:false,backup_exists:false,can_apply:fixture.profile==='custom',can_restore:false,revision:'exe-1',download:{can_download:fixture.profile==='custom',downloaded:fixture.downloaded,path:'client/current/4gb_patch.exe',source_url:'https://ntcore.com/4gb-patch/'}}});
     const state=()=>({profile:fixture.profile,running:false,settings:{ip:'127.0.0.1',login_port:5999,repo:'fixture',ref:'main',workers:3,jobs:2},source:{},processes:{},jobs:fixture.jobs,free_bytes:50e9,nektulos:{},client:{imported:true,files:5,bytes:100}});
     window.Trasc={call(id,op,input){setTimeout(()=>{const f=fixture,a=JSON.parse(input);let result={};f.calls.push({op,a});try{
      if(op!=='native_state'&&a.__profile&&a.__profile!==f.profile)throw Error('World profile changed');
      if(op==='native_state')result={profile:f.profile,installed:true,alive:f.alive,status:f.alive?'Runtime ready':'Runtime stopped',free_bytes:50e9};
      else if(op==='client_native_state')result=structuredClone(f.nativeStates[f.profile][f.mode]);
      else if(op==='runtime_start')f.alive=true;
      else if(op==='state')result=state();
      else if(op==='client_connection_status')result=connection();
      else if(op==='client_4gb_download'){
       if(!f.alive||f.profile!=='custom'||f.mode!=='stopped'||a.revision!=='exe-1')throw Error('Download is not allowed');
       f.downloaded=true;result={id:'download-1',operation:op,status:'done',result:{...connection(),message:'NTCore 4 GB Patch downloaded.'}};f.jobs.push(result);
      }
      else if(op==='controller_state')result={sources:[],actions:[],layers:[{name:'Main',bindings:{}}],deadzone:.2,sensitivity:700};
      window.nativeReply(id,{ok:true,result});
     }catch(e){window.nativeReply(id,{ok:false,error:e.message});}},5);}};
    },{profile,nativeStates});
    await page.goto(`http://127.0.0.1:${server.address().port}/`);
    await page.waitForFunction(p=>activeProfile===p&&lastNative&&lastClientNative&&!polling,profile);
    assert.equal(await page.evaluate(()=>lastClientNative.profile),profile,'Full UI receives the owning profile from native Java state');
    assert.equal(await page.evaluate(()=>fixture.calls.filter(c=>c.op==='client_connection_status').length),0,'Closed runtime never requests backend file status');
    assert(await page.isDisabled('#client-host-save'),'Closed runtime blocks file edits');
    assert(await page.isDisabled('#client-4gb-download'),'Closed runtime blocks download');
    // Click the shipped runtime action. Its normal poll/finally hook must fetch
    // the file status; this test never calls loadClientConnection directly.
    await page.click('#runtime-open');
    await page.waitForFunction(()=>!busy&&!polling&&!clientConnectionLoading&&clientConnectionData?.profile===activeProfile&&!document.getElementById('client-host-save').disabled);
    assert((await page.evaluate(()=>fixture.calls)).some(c=>c.op==='client_connection_status'&&c.a.__profile===profile),'Runtime opening automatically inspects the current world');
    assert.equal(await page.isDisabled('#client-4gb-download'),profile!=='custom','Real stopped state enables the official download only in Custom');
    assert(!(await page.textContent('#client-host-status')).includes('Waiting for this world'),'Polling resolves the waiting status');
    if(profile==='custom'){
     await page.locator('nav [data-tab=client]').click();
     await page.locator('#client-4gb-panel > summary').click();
     await page.click('#client-4gb-download');
     await page.waitForFunction(()=>fixture.downloaded&&!busy&&!clientConnectionMutating);
     const download=await page.evaluate(()=>fixture.calls.find(c=>c.op==='client_4gb_download'));
     assert.deepEqual(download.a,{revision:'exe-1',__profile:'custom'},'The shipped API submits the inspected revision and owning profile');
     assert((await page.textContent('#client-4gb-download-status')).includes('saved at client/current/4gb_patch.exe'),'The full UI displays the completed download');
    }
    assert.deepEqual(errors,[],'Full client status UI has no browser errors for '+profile);
   }finally{await page.close();}
  }
 }finally{await new Promise(resolve=>server.close(resolve));}
}
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  for(const profile of ['custom','traditional','takp']){
   const page=await browser.newPage({viewport:{width:393,height:852}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.setContent(`<style>${fs.readFileSync(path.join(ui,'style.css'),'utf8')}</style><main>${markup}</main>`);
   await page.addScriptTag({content:`
    const $=id=>document.getElementById(id);let activeProfile=${JSON.stringify(profile)},busy=0,sessionAction=null;
    const nativeStates=${JSON.stringify(nativeStates)};
    let lastNative={profile:activeProfile,alive:true},lastClientNative=structuredClone(nativeStates[activeProfile].stopped),lastState={profile:activeProfile,jobs:[],client:{imported:true,files:5,bytes:100}};
    window.fixture={calls:[],hold:false,waiters:[],notices:[],revision:1,host:'192.0.2.9',backup:false,patched:false,downloaded:false,downloadWarning:''};
    function notice(text,error=false){fixture.notices.push({text,error});}
    function action(id,fn){$(id).addEventListener('click',async()=>{busy++;renderClientConnectionControls();try{await fn();}catch(e){notice(e.message,true);}finally{busy--;renderClientConnectionControls();}});}
    fixture.status=()=>({profile:activeProfile,host:{host:fixture.host,port:activeProfile==='takp'?'6000, 6001':5999,exists:true,backup_exists:fixture.backup,can_save:true,can_restore:fixture.backup,revision:'host-'+fixture.revision,path:'eqhost.txt'},patch:{eligible:activeProfile==='custom',exe:'eqgame.exe',patched:fixture.patched,backup_exists:fixture.patched,can_apply:activeProfile==='custom',can_restore:activeProfile==='custom'&&fixture.patched,revision:'exe-'+fixture.revision,download:{can_download:activeProfile==='custom'&&!fixture.downloadWarning,downloaded:fixture.downloaded,path:'client/current/4gb_patch.exe',source_url:'https://ntcore.com/4gb-patch/',warning:fixture.downloadWarning}}});
    async function api(op,args){fixture.calls.push({op,args});const result=fixture.status();if(fixture.hold)return new Promise(resolve=>fixture.waiters.push(()=>resolve(result)));return result;}
    async function job(op,args){fixture.calls.push({op,args,profile:activeProfile});const expected=(op.startsWith('client_host')?'host-':'exe-')+fixture.revision;if(args.revision!==expected)throw Error('Client file changed. Reload it before saving.');if(op==='client_host_save'){fixture.host=args.host;fixture.backup=true;}if(op==='client_host_restore')fixture.host='192.0.2.9';if(op==='client_4gb_apply')fixture.patched=true;if(op==='client_4gb_restore')fixture.patched=false;if(op==='client_4gb_download')fixture.downloaded=true;fixture.revision++;return {...fixture.status(),message:'Saved.'};}
   `});
   await page.addScriptTag({path:path.join(ui,'client-connection.js')});
   await page.addScriptTag({path:path.join(ui,'controller-menu.js')});
   assert.equal(await page.evaluate(()=>lastClientNative.profile),profile,'The real native state identifies its owning world');
   await page.evaluate(()=>loadClientConnection());
   const idle=()=>page.waitForFunction(()=>busy===0&&!clientConnectionLoading&&!clientConnectionMutating);
   assert.equal(await page.inputValue('#client-host-address'),'192.0.2.9','Inspection retains the imported endpoint');
   assert.equal(await page.evaluate(()=>fixture.calls.filter(c=>c.op!=='client_connection_status').length),0,'Inspection never writes');
   assert((await page.textContent('#client-host-ports')).includes(profile==='takp'?'6000, 6001':'5999'),'Existing ports are shown unchanged');
   await page.click('#client-host-local');await idle();assert.equal(await page.inputValue('#client-host-address'),'127.0.0.1');
   assert.equal(await page.evaluate(()=>fixture.calls.filter(c=>c.op==='client_host_save').length),0,'Local default requires Save');
   await page.fill('#client-host-address','198.51.100.12');
   await page.evaluate(()=>loadClientConnection());assert.equal(await page.inputValue('#client-host-address'),'198.51.100.12','Refresh preserves the unsaved IP');
   await page.click('#client-host-save');await idle();
   const save=await page.evaluate(()=>fixture.calls.find(c=>c.op==='client_host_save'));
   assert.deepEqual(save.args,{host:'198.51.100.12',revision:'host-1'},'Only host and inspected revision are submitted; no port override');
   assert.equal(save.profile,profile);assert.equal(await page.isDisabled('#client-host-restore'),false);
   await page.click('#client-host-restore');await idle();assert.equal(await page.inputValue('#client-host-address'),'192.0.2.9');
   await page.fill('#client-host-address','203.0.113.2');await page.evaluate(()=>{fixture.revision++;return loadClientConnection();});
   assert(await page.isDisabled('#client-host-save'),'An external file edit invalidates the unsaved revision');
   assert((await page.textContent('#client-host-status')).includes('changed while you were editing'));
   await page.click('#client-connection-reload');await idle();assert.equal(await page.inputValue('#client-host-address'),'192.0.2.9','Explicit reload discards draft');
   for(const mode of ['running','busy']){
    await page.evaluate(mode=>{lastClientNative=structuredClone(nativeStates[activeProfile][mode]);renderClientConnectionControls();},mode);
    assert(await page.isDisabled('#client-host-save'),'Real native '+mode+' state blocks edits');assert(await page.isDisabled('#client-4gb-download'),'Real native '+mode+' state blocks downloads');
   }
   await page.evaluate(()=>{lastClientNative=structuredClone(nativeStates[activeProfile].stopped);lastState.jobs=[{status:'running'}];renderClientConnectionControls();});assert(await page.isDisabled('#client-host-save'),'File jobs block edits');assert(await page.isDisabled('#client-4gb-download'),'Other file jobs block downloads');
   await page.evaluate(()=>{lastState.jobs=[];renderClientConnectionControls();});
   for(const guard of ['missing-profile','other-profile','native-install','native-session','session-action','ui-busy']){
    const calls=await page.evaluate(()=>fixture.calls.length);
    await page.evaluate(guard=>{
     if(guard==='missing-profile')delete lastClientNative.profile;
     if(guard==='other-profile')lastClientNative=structuredClone(nativeStates[activeProfile==='custom'?'takp':'custom'].stopped);
     if(guard==='native-install')lastNative.installing=true;
     if(guard==='native-session')lastNative.session_busy=true;
     if(guard==='session-action')sessionAction='session-export-all';
     if(guard==='ui-busy')busy=1;
     checkClientConnectionStatus();
    },guard);
    assert(await page.isDisabled('#client-host-save'),guard+' blocks edits');assert(await page.isDisabled('#client-4gb-download'),guard+' blocks downloads');
    assert.equal(await page.evaluate(()=>fixture.calls.length),calls,guard+' does not inspect another or unavailable world');
    await page.evaluate(()=>{lastClientNative=structuredClone(nativeStates[activeProfile].stopped);lastNative.installing=false;lastNative.session_busy=false;sessionAction=null;busy=0;renderClientConnectionControls();});
   }
   assert.equal(await page.isVisible('#client-4gb-panel'),profile==='custom');
   assert.equal(await page.isDisabled('#client-4gb-download'),profile!=='custom','Official tool belongs only to the Custom client');
   if(profile==='custom'){
    await page.click('#client-4gb-apply');await idle();assert.equal(await page.isDisabled('#client-4gb-apply'),false);assert.equal(await page.textContent('#client-4gb-apply'),'Verify 4 GB patch');assert.equal(await page.isDisabled('#client-4gb-restore'),false);
    await page.click('#client-4gb-apply');await idle();assert.equal(await page.evaluate(()=>fixture.patched),true,'An already-enabled patch can be verified without disabling the control');
    assert.equal(await page.isDisabled('#client-4gb-download'),false,'A patched client can still download the separate official utility');
    await page.click('#client-4gb-restore');await idle();assert.equal(await page.isDisabled('#client-4gb-apply'),false);
    assert((await page.textContent('#client-4gb-download-status')).includes('Downloading leaves eqgame.exe unchanged'));
    await page.evaluate(()=>{fixture.downloadWarning='A different 4gb_patch.exe is already present.';return loadClientConnection();});
    assert(await page.isDisabled('#client-4gb-download'),'An existing conflicting tool disables replacement');
    assert((await page.textContent('#client-4gb-download-status')).includes('different 4gb_patch.exe'));
    await page.evaluate(()=>{fixture.downloadWarning='';return loadClientConnection();});
    const revision=await page.evaluate(()=>clientConnectionData.patch.revision);
    await page.focus('#client-4gb-apply');
    await page.evaluate(()=>launcherMenuController.command('down'));
    assert.equal(await page.evaluate(()=>document.activeElement.id),'client-4gb-download','D-pad reaches the separate download action');
    assert(await page.evaluate(()=>launcherMenuController.command('accept')),'Controller A accepts the download action');await idle();
    const download=await page.evaluate(()=>fixture.calls.find(c=>c.op==='client_4gb_download'));
    assert.deepEqual(download.args,{revision},'Download uses the inspected client revision and fixed official source');
    assert.equal(download.profile,'custom');
    assert.equal(await page.evaluate(()=>fixture.patched),false,'Downloading does not apply the patch');
    assert.equal(await page.isDisabled('#client-4gb-apply'),false,'Built-in Apply remains available after download');
    assert.equal(await page.isDisabled('#client-4gb-download'),false,'A repeated request can reuse the verified tool');
    assert((await page.textContent('#client-4gb-download-status')).includes('saved at client/current/4gb_patch.exe'),'Downloaded file path is shown');
    await page.focus('#client-4gb-download');await page.evaluate(()=>launcherMenuController.command('accept'));await idle();
    assert.equal(await page.evaluate(()=>fixture.calls.filter(c=>c.op==='client_4gb_download').length),2,'Controller A can request the verified tool again');
    assert.equal(await page.evaluate(()=>fixture.patched),false,'Repeated download also leaves the game executable unchanged');
   }
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Connection cards fit a narrow screen');
   await page.evaluate(()=>{fixture.hold=true;window.pendingConnection=loadClientConnection();});
   await page.evaluate(()=>{activeProfile=activeProfile==='custom'?'takp':'custom';lastNative.profile=activeProfile;lastClientNative=structuredClone(nativeStates[activeProfile].stopped);lastState.profile=activeProfile;resetClientConnectionProfile();fixture.waiters.splice(0).forEach(resolve=>resolve());});
   await page.evaluate(()=>pendingConnection);assert.equal(await page.evaluate(()=>clientConnectionData),null,'A late old-world response is discarded');
   assert(await page.isDisabled('#client-host-save'),'No old-world revision remains available to mutate');
   await page.evaluate(()=>{fixture.hold=false;lastNative.alive=false;renderClientConnectionControls();});
   assert((await page.textContent('#client-host-status')).includes('Open this world'));
   await page.evaluate(()=>{lastNative.alive=true;checkClientConnectionStatus();});await idle();
   assert.equal(await page.isDisabled('#client-host-save'),false,'Opening the runtime loads current-world settings');
   assert.deepEqual(errors,[]);await page.close();
  }
  await checkFullUiPolling(browser);
  console.log('PASS: real native state enables all-profile client files and Custom download; full UI runtime-open polling, protected edits/restores, controller download, busy/session/profile guards and stale responses');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
