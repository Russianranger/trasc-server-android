const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const ui=path.resolve('app/src/main/assets/ui');
const markup=`<details open id="client-connection-panel" class="card fold"><summary>Client login address · eqhost.txt</summary><label for="client-host-address">Server IP address</label><input id="client-host-address" value="127.0.0.1"><p id="client-host-ports"></p><div class="buttons"><button id="client-host-save">Save IP address</button><button id="client-host-local">Use 127.0.0.1</button><button id="client-host-restore">Restore original eqhost.txt</button><button id="client-connection-reload">Reload client files</button></div><p id="client-host-status"></p></details><details open id="client-4gb-panel" class="card fold"><summary>Custom client · 4 GB patch</summary><div class="buttons"><button id="client-4gb-apply">Apply 4 GB patch</button><button id="client-4gb-restore">Restore original executable</button></div><p id="client-4gb-status"></p></details>`;
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  for(const profile of ['custom','traditional','takp']){
   const page=await browser.newPage({viewport:{width:393,height:852}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.setContent(`<style>${fs.readFileSync(path.join(ui,'style.css'),'utf8')}</style><main>${markup}</main>`);
   await page.addScriptTag({content:`
    const $=id=>document.getElementById(id);let activeProfile=${JSON.stringify(profile)},busy=0,sessionAction=null;
    let lastNative={profile:activeProfile,alive:true},lastClientNative={profile:activeProfile,alive:false},lastState={profile:activeProfile,jobs:[],client:{imported:true,files:5,bytes:100}};
    window.fixture={calls:[],hold:false,waiters:[],notices:[],revision:1,host:'192.0.2.9',backup:false,patched:false};
    function notice(text,error=false){fixture.notices.push({text,error});}
    function action(id,fn){$(id).addEventListener('click',async()=>{busy++;renderClientConnectionControls();try{await fn();}catch(e){notice(e.message,true);}finally{busy--;renderClientConnectionControls();}});}
    fixture.status=()=>({profile:activeProfile,host:{host:fixture.host,port:activeProfile==='takp'?'6000, 6001':5999,exists:true,backup_exists:fixture.backup,can_save:true,can_restore:fixture.backup,revision:'host-'+fixture.revision,path:'eqhost.txt'},patch:{eligible:activeProfile==='custom',exe:'eqgame.exe',patched:fixture.patched,backup_exists:fixture.patched,can_apply:activeProfile==='custom'&&!fixture.patched,can_restore:activeProfile==='custom'&&fixture.patched,revision:'exe-'+fixture.revision}});
    async function api(op,args){fixture.calls.push({op,args});const result=fixture.status();if(fixture.hold)return new Promise(resolve=>fixture.waiters.push(()=>resolve(result)));return result;}
    async function job(op,args){fixture.calls.push({op,args,profile:activeProfile});const expected=(op.startsWith('client_host')?'host-':'exe-')+fixture.revision;if(args.revision!==expected)throw Error('Client file changed. Reload it before saving.');if(op==='client_host_save'){fixture.host=args.host;fixture.backup=true;}if(op==='client_host_restore')fixture.host='192.0.2.9';if(op==='client_4gb_apply')fixture.patched=true;if(op==='client_4gb_restore')fixture.patched=false;fixture.revision++;return {...fixture.status(),message:'Saved.'};}
   `});
   await page.addScriptTag({path:path.join(ui,'client-connection.js')});
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
   await page.evaluate(()=>{lastClientNative.alive=true;renderClientConnectionControls();});assert(await page.isDisabled('#client-host-save'),'Running clients block edits');
   await page.evaluate(()=>{lastClientNative.alive=false;lastState.jobs=[{status:'running'}];renderClientConnectionControls();});assert(await page.isDisabled('#client-host-save'),'File jobs block edits');
   await page.evaluate(()=>{lastState.jobs=[];renderClientConnectionControls();});
   assert.equal(await page.isVisible('#client-4gb-panel'),profile==='custom');
   if(profile==='custom'){
    await page.click('#client-4gb-apply');await idle();assert(await page.isDisabled('#client-4gb-apply'));assert.equal(await page.isDisabled('#client-4gb-restore'),false);
    await page.click('#client-4gb-restore');await idle();assert.equal(await page.isDisabled('#client-4gb-apply'),false);
   }
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Connection cards fit a narrow screen');
   await page.evaluate(()=>{fixture.hold=true;window.pendingConnection=loadClientConnection();});
   await page.evaluate(()=>{activeProfile=activeProfile==='custom'?'takp':'custom';lastNative.profile=activeProfile;lastClientNative.profile=activeProfile;lastState.profile=activeProfile;resetClientConnectionProfile();fixture.waiters.splice(0).forEach(resolve=>resolve());});
   await page.evaluate(()=>pendingConnection);assert.equal(await page.evaluate(()=>clientConnectionData),null,'A late old-world response is discarded');
   assert(await page.isDisabled('#client-host-save'),'No old-world revision remains available to mutate');
   await page.evaluate(()=>{fixture.hold=false;lastNative.alive=false;renderClientConnectionControls();});
   assert((await page.textContent('#client-host-status')).includes('Open this world'));
   await page.evaluate(()=>{lastNative.alive=true;checkClientConnectionStatus();});await idle();
   assert.equal(await page.isDisabled('#client-host-save'),false,'Opening the runtime loads current-world settings');
   assert.deepEqual(errors,[]);await page.close();
  }
  console.log('PASS: explicit all-profile host edits, retained ports, protected restores, Custom-only patch, busy guards, revision conflicts and stale-profile responses');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
