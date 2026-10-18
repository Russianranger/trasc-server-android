const {chromium}=require('playwright');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert');
const {execFileSync}=require('child_process');
const ui=path.resolve('app/src/main/assets/ui');
const nativeStates=JSON.parse(execFileSync('python3',['tests/test_client_native_status.py','--fixtures'],{encoding:'utf8'}));
const server=http.createServer((req,res)=>{
 const name=req.url==='/'?'index.html':req.url.slice(1);
 if(!/^[\w.-]+$/.test(name)){res.writeHead(404);res.end();return;}
 try{res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(path.join(ui,name)));}catch{res.writeHead(404);res.end();}
});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const browser=await chromium.launch({headless:true});
 try{
  for(const profile of ['custom','traditional','takp']){
   const page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[],dialogs=[];
   page.on('pageerror',error=>errors.push(error.message));page.on('dialog',async dialog=>{dialogs.push(dialog.message());await dialog.dismiss();});
   await page.addInitScript(({profile,nativeStates})=>{
    window.fixture={profile,nativeStates,calls:[],preferences:{custom:true,traditional:true,takp:true},omitPreference:true,cancelLaunch:false,holdPreference:false,preferenceReply:null,holdStart:false,startReply:null,holdClientState:false,stateReply:null};
    window.Trasc={call(id,op,input){setTimeout(()=>{
     const f=fixture,a=JSON.parse(input);f.calls.push({op,a});let result={};
     try{
      if(op!=='native_state'&&a.__profile&&a.__profile!==f.profile)throw Error('World profile changed');
      if(op==='native_state')result={profile:f.profile,installed:true,alive:false,status:'Runtime stopped',free_bytes:50e9};
      else if(op==='client_native_state'){
       result=structuredClone(f.nativeStates[f.profile].stopped);
       if(!f.omitPreference)result.compatibility_warnings_enabled=f.preferences[f.profile];
       if(f.holdClientState){f.holdClientState=false;f.stateReply=()=>{f.stateReply=null;window.nativeReply(id,{ok:true,result});};return;}
      }else if(op==='client_compatibility_warnings'){
       if(typeof a.enabled!=='boolean')throw Error('Boolean preference required');
       f.preferences[f.profile]=a.enabled;f.omitPreference=false;result={profile:f.profile,enabled:a.enabled};
       if(f.holdPreference){f.holdPreference=false;f.preferenceReply=()=>{f.preferenceReply=null;window.nativeReply(id,{ok:true,result});};return;}
      }else if(op==='client_start'){
       result=f.cancelLaunch?{cancelled:true,message:'Client launch cancelled.'}:{started:true};
       if(f.holdStart){f.holdStart=false;f.startReply=()=>{f.startReply=null;window.nativeReply(id,{ok:true,result});};return;}
      }else if(op==='controller_state')result={sources:[],actions:[],layers:[{name:'Main',bindings:{}}],deadzone:.2,sensitivity:700};
      window.nativeReply(id,{ok:true,result});
     }catch(error){window.nativeReply(id,{ok:false,error:error.message});}
    },5);}};
   },{profile,nativeStates});
   await page.goto(`http://127.0.0.1:${server.address().port}/`);
   const idle=()=>page.waitForFunction(()=>!busy&&!polling&&!clientCompatibilityWarningsSaving);
   await page.waitForFunction(p=>activeProfile===p&&lastClientNative?.profile===p&&!polling,profile);
   await page.click('nav [data-tab=client]');await page.locator('#client-options > summary').click();await idle();
   assert.equal(await page.isVisible('#client-compatibility-warnings-panel'),profile==='custom','Compatibility preferences belong to Custom');
   assert(await page.isChecked('#client-compatibility-warnings'),'Warnings default to enabled when native state omits a saved preference');
   assert.equal(await page.evaluate(()=>fixture.calls.filter(c=>c.op==='client_compatibility_warnings').length),0,'Inspecting the launcher never mutates preferences');
   if(profile==='custom'){
    assert(!(await page.isDisabled('#client-compatibility-warnings')),'Preference remains available with server runtime offline');
    await page.uncheck('#client-compatibility-warnings');await idle();
    assert.deepEqual(await page.evaluate(()=>fixture.calls.find(c=>c.op==='client_compatibility_warnings').a),{enabled:false,__profile:'custom'});
    assert((await page.textContent('#client-compatibility-warnings-status')).includes('warnings are off'));
    await page.reload();await page.waitForFunction(()=>activeProfile==='custom'&&!polling);
    // Native persistence is authoritative after a reload, including suppression
    // selected by the separate Android warning dialog.
    await page.evaluate(()=>{fixture.omitPreference=false;fixture.preferences.custom=false;return clientRuntimeState();});
    await page.click('nav [data-tab=client]');await page.locator('#client-options > summary').click();await idle();
    assert(!(await page.isChecked('#client-compatibility-warnings')),'Saved native suppression is displayed');
    await page.check('#client-compatibility-warnings');await idle();
    assert(await page.evaluate(()=>fixture.preferences.custom),'The setting can re-enable future warnings');
    // An old status request must not undo a newer completed preference save.
    await page.evaluate(()=>{fixture.holdClientState=true;window.delayedState=clientRuntimeState();});
    await page.waitForFunction(()=>fixture.stateReply);
    await page.uncheck('#client-compatibility-warnings');await page.waitForFunction(()=>!clientCompatibilityWarningsSaving);
    await page.evaluate(()=>{fixture.stateReply();return delayedState;});
    assert(!(await page.isChecked('#client-compatibility-warnings')),'Late polling cannot revert a newer preference');
    for(const guard of ['busy','session','profile']){
     await page.evaluate(guard=>{if(guard==='busy')busy=1;if(guard==='session')sessionAction='session-export-all';if(guard==='profile')lastClientNative.profile='takp';renderClientCompatibilityWarnings();},guard);
     assert(await page.isDisabled('#client-compatibility-warnings'),guard+' prevents changing the wrong or busy profile');
     await page.evaluate(()=>{busy=0;sessionAction=null;lastClientNative.profile='custom';renderClientCompatibilityWarnings();});
    }
    await page.evaluate(()=>{fixture.holdPreference=true;});await page.check('#client-compatibility-warnings');await page.waitForFunction(()=>fixture.preferenceReply);
    assert(await page.isDisabled('#client-compatibility-warnings'),'An in-flight preference save cannot be submitted twice');
    await page.evaluate(()=>{activeProfile='takp';lastClientNative={profile:'takp',compatibility_warnings_enabled:false};renderClientCompatibilityWarnings();fixture.preferenceReply();});
    await page.waitForTimeout(30);
    assert.equal(await page.evaluate(()=>lastClientNative.profile),'takp','Late preference response retains the active profile');
    assert.equal(await page.evaluate(()=>lastClientNative.compatibility_warnings_enabled),false,'Late Custom preference does not overwrite another profile');
    await page.evaluate(()=>{activeProfile='custom';lastClientNative={...fixture.nativeStates.custom.stopped,compatibility_warnings_enabled:true};renderClientCompatibilityWarnings();});
    await page.evaluate(()=>{fixture.cancelLaunch=true;});
    const views=await page.evaluate(()=>fixture.calls.filter(c=>c.op==='client_view').length);
    await page.click('#client-launch');await idle();
    assert.equal(await page.evaluate(()=>fixture.calls.filter(c=>c.op==='client_view').length),views,'Cancelled native confirmation does not open the client display');
    assert.equal(await page.textContent('#notice'),'Client launch cancelled.');
    assert(!(await page.locator('#notice').evaluate(el=>el.classList.contains('error'))),'Cancellation is not a startup failure');
    await page.evaluate(()=>{fixture.cancelLaunch=false;fixture.preferences.custom=false;fixture.omitPreference=false;return clientRuntimeState();});
    await page.click('#client-launch');await idle();
    assert.equal(await page.evaluate(()=>fixture.calls.filter(c=>c.op==='client_view').length),views+1,'Continue or suppressed warning follows the normal client path');
    await page.evaluate(()=>{fixture.holdStart=true;});await page.click('#client-launch');await page.waitForFunction(()=>fixture.startReply);
    await page.evaluate(()=>{activeProfile='takp';fixture.profile='takp';fixture.startReply();});await idle();
    assert.equal(await page.evaluate(()=>fixture.calls.filter(c=>c.op==='client_view').length),views+1,'A stale launch response never opens another profile');
   }else{
    assert(await page.isDisabled('#client-compatibility-warnings'),'Custom warning preference is disabled for other profiles');
    await page.click('#client-launch');await idle();
    assert.equal(await page.evaluate(()=>fixture.calls.filter(c=>c.op==='client_view').length),1,'Other profiles retain normal client launch');
   }
   assert.deepEqual(dialogs,[],'The browser never adds a second confirmation over the native warning');
   assert.deepEqual(errors,[],profile+' has no browser errors');await page.close();
  }
  console.log('PASS: shipped UI defaults and native warning persistence, re-enable, offline preference, cancelled/continued launch, all profiles, busy/stale guards, no duplicate browser warning');
 }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exit(1);});
