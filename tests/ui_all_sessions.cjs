const {chromium}=require('playwright');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert');
const root=path.resolve('app/src/main/assets/ui');
const server=http.createServer((req,res)=>{
 const name=req.url==='/'?'index.html':req.url.slice(1);
 if(!/^[\w.-]+$/.test(name)){res.writeHead(404);res.end();return;}
 try{const types={js:'text/javascript',css:'text/css',webp:'image/webp',ttf:'font/ttf',html:'text/html'};res.setHeader('Content-Type',types[name.split('.').pop()]||'application/octet-stream');res.end(fs.readFileSync(path.join(root,name)));}catch{res.writeHead(404);res.end();}
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({headless:true});
 try{
  fs.mkdirSync('ui-reports',{recursive:true});
  const page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
   localStorage.fixtureLoads=String(Number(localStorage.fixtureLoads||0)+1);
   const f=window.fixture={profile:localStorage.fixtureProfile||'custom',calls:JSON.parse(localStorage.fixtureCalls||'[]'),transfer:false,cancellable:true,outcome:'hold'};
   f.finish=result=>{const pending=f.pending;f.pending=null;f.transfer=false;if(result.active_profile){localStorage.fixtureProfile=result.active_profile;}if(result.restored_activation)localStorage.fixtureRestoration=JSON.stringify(result);window.nativeReply(pending.id,{ok:true,result});};
   window.Trasc={call(id,op,input){setTimeout(()=>{
    const args=JSON.parse(input);f.calls.push({op,args});localStorage.fixtureCalls=JSON.stringify(f.calls);let result={};
    if(op==='native_state')result={...JSON.parse(localStorage.fixtureRestoration||'{}'),profile:f.profile,installed:true,alive:false,installing:false,session_busy:f.transfer,session_cancellable:f.cancellable,session_total:100e9,session_bytes:25e9,status:f.transfer?'Exporting TAKP World…':'Runtime stopped',free_bytes:500e9};
    else if(op==='client_native_state')result={profile:f.profile,installed:true,alive:false,busy:false,status:'Client stopped'};
    else if(op==='controller_state')result={sources:[],actions:[],layers:[{name:'Main',bindings:{}}],deadzone:.2,sensitivity:700};
    else if(op==='pick'&&['session-export-all','session-all'].includes(args.kind)){
     if(f.outcome==='cancel')result={cancelled:true};
     else if(f.outcome==='error'){window.nativeReply(id,{ok:false,error:'Not enough free space to stage every profile. Existing profiles are unchanged.'});return;}
     else{f.pending={id,args};f.transfer=true;return;}
    }else if(op==='session_cancel'){f.finish({cancelled:true});result={message:'Cancellation requested'};}
    window.nativeReply(id,{ok:true,result});
   },5);}};
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  const idle=()=>page.waitForFunction(()=>!polling&&busy===0&&lastNative&&lastClientNative);
  const set=async values=>page.evaluate(async values=>{while(polling)await new Promise(r=>setTimeout(r,10));Object.assign(fixture,values);await poll();},values);
  await idle();await page.selectOption('#launcher-theme','monk');
  await page.locator('nav [data-tab=server]').click();
  const beforeLoads=await page.evaluate(()=>Number(localStorage.fixtureLoads));
  await set({outcome:'cancel'});await page.click('#session-export-all');await idle();
  assert.equal(await page.evaluate(()=>Number(localStorage.fixtureLoads)),beforeLoads,'Cancelled destination selection does not reload');
  assert.equal(await page.inputValue('#launcher-theme'),'monk','Cancelled backup preserves appearance');
  assert.deepEqual(await page.evaluate(()=>fixture.calls.filter(c=>c.op==='pick').at(-1).args),{kind:'session-export-all',launcher_preferences:{theme:'monk'},__profile:'custom'},'All-profile export captures appearance and chooses destination first');
  await set({outcome:'hold'});await page.click('#session-export-all');await page.waitForFunction(()=>fixture.transfer);await set({});
  for(const id of ['session-import','session-export','session-import-all','session-export-all','switch-profile','runtime-open'])assert(await page.isDisabled('#'+id),id+' cannot compete with the transfer');
  assert(!(await page.locator('#cancel').isHidden()),'Transfer cancellation is available');
  assert((await page.textContent('#activity-detail')).includes('23.3 GB / 93.1 GB'),'Large transfer progress uses 64-bit quantities');
  await page.click('#cancel');await idle();
  assert((await page.evaluate(()=>fixture.calls)).some(c=>c.op==='session_cancel'),'Cancel routes to native archive transport');
  await set({outcome:'hold',cancellable:false});await page.click('#session-export-all');await page.waitForFunction(()=>fixture.transfer);await set({});
  assert(await page.locator('#cancel').isHidden(),'Activation or other noncancellable phase cannot be interrupted');
  await page.evaluate(()=>fixture.finish({message:'All profiles exported to destination.'}));await idle();
  assert((await page.textContent('#session-result')).includes('All profiles exported'));
  assert(!(await page.evaluate(()=>fixture.calls)).some(c=>c.op==='export'),'Direct SAF export does not create a second destination picker or local ZIP copy');
  await page.screenshot({path:'ui-reports/all-profiles-export-1280.png',fullPage:true});
  await page.locator('nav [data-tab=setup]').click();await set({outcome:'cancel',cancellable:true});
  await page.click('#session-import-all');await idle();
  assert.equal(await page.evaluate(()=>Number(localStorage.fixtureLoads)),beforeLoads,'Cancelled restore does not reload or apply preferences');
  assert.equal(await page.inputValue('#launcher-theme'),'monk');
  await set({outcome:'error'});await page.click('#session-import-all');await idle();
  assert((await page.textContent('#notice')).includes('Not enough free space'));
  assert.equal(await page.evaluate(()=>Number(localStorage.fixtureLoads)),beforeLoads,'Failed verification preserves management state');
  assert.equal(await page.inputValue('#launcher-theme'),'monk');
  assert.equal(await page.evaluate(()=>window.restoreLauncherAppearance({theme:'unknown'})),false,'Unknown appearance from an archive cannot alter the theme');
  await page.check('#replace-all-sessions');await set({outcome:'hold'});await page.click('#session-import-all');await page.waitForFunction(()=>fixture.transfer);
  assert.deepEqual(await page.evaluate(()=>fixture.pending.args),{kind:'session-all',replace:true,__profile:'custom'},'Replacement is explicit and uses all-profile import');
  await page.evaluate(()=>fixture.finish({message:'All profiles restored.',active_profile:'takp',restored_activation:'activation-one',launcher_preferences:{theme:'necromancer'}}));
  await page.waitForFunction(()=>Number(localStorage.fixtureLoads)>1&&activeProfile==='takp'&&!polling&&busy===0);
  assert.equal(await page.inputValue('#launcher-theme'),'necromancer','Only successful restore applies saved appearance before reload');
  assert.equal(await page.evaluate(()=>localStorage.getItem('trasc.launcher.theme')),'necromancer');
  assert.equal(await page.evaluate(()=>localStorage.getItem('trasc.session.restored_activation')),'activation-one','Committed restoration receipt is acknowledged');
  await page.selectOption('#launcher-theme','monk');await set({});
  assert.equal(await page.inputValue('#launcher-theme'),'monk','Later personal theme edits are not reset by polling the same restoration');
  await page.evaluate(()=>localStorage.fixtureRestoration=JSON.stringify({restored_activation:'activation-after-process-death',launcher_preferences:{theme:'necromancer'}}));await page.reload();await idle();
  assert.equal(await page.inputValue('#launcher-theme'),'necromancer','Startup applies a durable receipt after activation without an API reply');
  assert.equal(await page.evaluate(()=>{const original=Storage.prototype.setItem;Storage.prototype.setItem=()=>{throw Error('Unavailable');};try{return window.restoreLauncherAppearanceReceipt({restored_activation:'retry-later',launcher_preferences:{theme:'monk'}});}finally{Storage.prototype.setItem=original;}}),false,'Failed preference storage leaves the receipt available for retry');
  assert.equal(await page.evaluate(()=>localStorage.getItem('trasc.session.restored_activation')),'activation-after-process-death');
  await page.setViewportSize({width:393,height:852});await page.locator('nav [data-tab=setup]').click();
  await page.locator('#session-import-all').scrollIntoViewIfNeeded();await page.screenshot({path:'ui-reports/all-profiles-restore-393.png',fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'All-profile restore fits the phone viewport');
  assert.deepEqual(errors,[],'All-profile transfer UI has no JavaScript errors');
  console.log('PASS: all-profile destination-first export, progress/cancel and operation exclusion, explicit verified restore, failure/cancel preservation, saved theme and responsive layout');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exit(1);});
