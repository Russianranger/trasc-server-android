const {chromium}=require('playwright');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert');
const root=path.resolve('app/src/main/assets/ui');
const server=http.createServer((req,res)=>{
 const name=req.url==='/'?'index.html':req.url.slice(1);
 if(!/^[\w.-]+$/.test(name)){res.writeHead(404);res.end();return;}
 try{res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.webp')?'image/webp':name.endsWith('.ttf')?'font/ttf':'text/html');res.end(fs.readFileSync(path.join(root,name)));}catch{res.writeHead(404);res.end();}
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:412,height:915}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
   window.fixture={profile:localStorage.profile||'custom',alive:false,client:false,busy:false,installing:false,sessionBusy:false,calls:[],removed:[],preview:null,holdPreview:false,failDelete:false};
   const entry=(name,folder,deletable=true,directory=false)=>({name,path:folder?folder+'/'+name:name,size:directory?null:1024,directory,deletable,protection:deletable?'':'Essential fixture file'});
   const entries=folder=>folder==='backups'?[entry('database-latest.sql.gz',folder,false),...Array.from({length:204},(_,i)=>entry('database-'+String(i).padStart(4,'0')+'.sql.gz',folder))]:folder==='exports'?[entry('session-export.zip',folder),entry('logs-export.zip',folder)]:folder==='incoming'?[entry('old-import.zip',folder)]:folder==='client/prefix-backups'?[entry('prefix-backup-20261001',folder,true,true)]:[entry('backups','',false,true),entry('server','',false,true),entry('client','',false,true),entry('settings.json','',false)];
   window.Trasc={call(id,op,input){setTimeout(()=>{const f=fixture,a=JSON.parse(input);let result={};f.calls.push({op,a});try{
    if(op!=='native_state'&&a.__profile&&a.__profile!==f.profile)throw Error('World profile changed');
    if(op==='native_state')result={profile:f.profile,installed:true,alive:f.alive,installing:f.installing,session_busy:f.sessionBusy,status:'Runtime stopped',free_bytes:50e9};
    else if(op==='client_native_state')result={installed:true,alive:f.client,busy:f.busy,status:'Stopped'};
    else if(op==='state')result={profile:f.profile,running:false,settings:{ip:'127.0.0.1',login_port:5999,repo:'fixture',ref:'main',workers:3,jobs:2},source:{},processes:{},jobs:[],free_bytes:50e9,nektulos:{},client:{}};
    else if(op==='profile_switch'){localStorage.profile=a.profile;f.profile=a.profile;result={profile:f.profile};}
    else if(op==='controller_state')result={sources:[],actions:[],layers:[{name:'Main',bindings:{}}],deadzone:.2,sensitivity:700};
    else if(op==='native_files'||op==='files'){
     const folder=a.path||'.',all=entries(folder==='.'?'':folder).filter(x=>!f.removed.includes(x.path)&&x.name.toLowerCase().includes((a.query||'').trim().toLowerCase())),offset=a.offset||0,limit=a.limit||200;
     result={path:folder,items:all.slice(offset,offset+limit),total:all.length,offset,limit,next_offset:offset+limit<all.length?offset+limit:null};
    }
    else if(op==='file_delete_preview'){
     if(f.alive||f.client||f.busy||f.installing||f.sessionBusy)throw Error('Stop the client and server runtime before deleting files');
     const paths=[...a.paths].sort();if(paths.some(p=>p.includes('latest')||p==='settings.json'))throw Error('Protected file');
     result={token:'preview-'+f.calls.length,paths,bytes:paths.length*1024,files:paths.length};f.preview={...result,profile:f.profile};
     if(f.holdPreview){f.holdPreview=false;f.heldPreview=()=>window.nativeReply(id,{ok:true,result});return;}
    }
    else if(op==='file_delete'){
     if(f.alive||f.client||f.busy||f.installing||f.sessionBusy)throw Error('Stop the client and server runtime before deleting files');
     if(f.failDelete){f.failDelete=false;throw Error('Selected files changed after review. Review them again.');}
     if(!f.preview||a.token!==f.preview.token||f.preview.profile!==f.profile||JSON.stringify([...a.paths].sort())!==JSON.stringify(f.preview.paths))throw Error('Deletion review expired');
     f.removed.push(...a.paths);result={bytes:a.paths.length*1024,files:a.paths.length,paths:a.paths,message:'Deleted '+a.paths.length+' files.'};f.preview=null;
    }
    window.nativeReply(id,{ok:true,result});
   }catch(e){window.nativeReply(id,{ok:false,error:e.message});}},5);}};
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  await page.waitForFunction(()=>lastNative&&lastClientNative&&activeProfile==='custom');
  await page.locator('nav [data-tab=files]').click();
  await page.waitForFunction(()=>document.querySelector('#file-list').textContent.includes('settings.json'));
  assert.equal(await page.locator('[data-delete-path]:not([disabled])').count(),0,'Essential root entries are protected');
  assert.equal(await page.locator('#file-list button[aria-label^="Why is "]').count(),4,'Protected rows offer a reason');
  await page.getByRole('button',{name:'Why is settings.json protected?'}).click();assert.equal(await page.locator('#notice').textContent(),'Essential fixture file','Protected reason can be read on a touch device');
  const checked=()=>page.locator('[data-delete-path]:checked');
  const deleteCalls=()=>page.evaluate(()=>fixture.calls.filter(x=>x.op==='file_delete').length);
  const openBackups=async()=>{await page.locator('#cleanup-backups').click();await page.waitForFunction(()=>document.getElementById('file-results').textContent==='1–200 of 205 entries');};
  const review=async()=>{await page.locator('#cleanup-review').click();await page.locator('#cleanup-confirm').waitFor({state:'visible'});};
  await page.locator('#cleanup-incoming').click();await page.waitForFunction(()=>document.getElementById('file-list').textContent.includes('old-import.zip'));
  await page.locator('#cleanup-prefix').click();await page.waitForFunction(()=>document.getElementById('file-list').textContent.includes('prefix-backup-20261001'));
  await openBackups();
  assert(await page.evaluate(()=>fixture.calls.some(x=>x.op==='native_files')&&!fixture.calls.some(x=>x.op==='state'||x.op==='runtime_start'||x.op==='files')),'Closed-runtime browsing uses only native file access');
  assert.equal(await page.locator('[data-delete-path]:not([disabled])').count(),199);
  await page.locator('#cleanup-select-page').click();assert.equal(await checked().count(),199,'Select page excludes protected entries');
  await page.locator('#cleanup-clear-selection').click();await page.locator('[data-delete-path]:not([disabled])').first().check();
  await page.locator('#file-next').click();await page.waitForFunction(()=>document.getElementById('file-results').textContent==='201–205 of 205 entries');
  assert.equal(await checked().count(),0,'The new page initially has no checked items');assert((await page.locator('#cleanup-status').textContent()).startsWith('1 copies selected'),'The prior page selection is preserved');
  await page.locator('#cleanup-select-page').click();assert.equal(await checked().count(),5,'Select page does not include unseen entries');
  await review();
  const preview=await page.evaluate(()=>fixture.calls.filter(x=>x.op==='file_delete_preview').at(-1));
  assert.equal(preview.a.paths.length,6,'Review includes only explicitly selected pages/items');assert(preview.a.paths.every(p=>p.startsWith('backups/database-')));assert.equal(preview.a.__profile,'custom');
  assert.equal(await deleteCalls(),0,'Review performs no deletion');assert(await page.locator('#cleanup-delete').isDisabled(),'Permanent deletion requires the acknowledgement');
  assert((await page.locator('#cleanup-paths').textContent()).includes(preview.a.paths[0]));
  await page.locator('#cleanup-cancel').click();assert(await page.locator('#cleanup-confirm').isHidden());assert.equal(await deleteCalls(),0,'Cancel performs no deletion');
  await page.locator('#cleanup-clear-selection').click();assert.equal(await checked().count(),0);assert(await page.locator('#cleanup-review').isDisabled());
  // Editing the query or folder invalidates both the selection and any review.
  await page.locator('#cleanup-select-page').click();await review();await page.locator('#file-search').fill('database-020');
  assert.equal(await checked().count(),0);assert(await page.locator('#cleanup-confirm').isHidden());assert(await page.locator('#cleanup-delete').isDisabled());
  await page.locator('#file-search-go').click();await page.waitForFunction(()=>document.getElementById('file-results').textContent==='1–4 of 4 matches');
  await page.locator('#cleanup-select-page').click();await review();await page.locator('#file-path').fill('exports');
  assert.equal(await checked().count(),0);assert(await page.locator('#cleanup-confirm').isHidden());
  await page.locator('#file-go').click();await page.waitForFunction(()=>document.getElementById('file-list').textContent.includes('logs-export.zip'));
  await page.locator('#cleanup-select-page').click();await review();await page.locator('#cleanup-clear-selection').click();
  assert(await page.locator('#cleanup-confirm').isHidden());assert.equal(await checked().count(),0);
  // A preview arriving after navigation cannot reopen an obsolete confirmation.
  await openBackups();await page.locator('[data-delete-path]:not([disabled])').first().check();await page.evaluate(()=>fixture.holdPreview=true);
  await page.locator('#cleanup-review').click();await page.waitForFunction(()=>typeof fixture.heldPreview==='function');
  await page.locator('#file-search').fill('never-matches');await page.evaluate(()=>fixture.heldPreview());
  await page.waitForFunction(()=>!busy);assert(await page.locator('#cleanup-confirm').isHidden());assert.equal(await deleteCalls(),0);
  // Both live runtimes and transfers disable deletion, but browsing stays native/offline.
  await openBackups();await page.locator('[data-delete-path]:not([disabled])').first().check();
  await review();await page.locator('#cleanup-understand').check();assert(!(await page.locator('#cleanup-delete').isDisabled()));
  for(const flag of ['alive','client','busy','installing','sessionBusy']){
   await page.evaluate(flag=>{fixture[flag]=true;return poll();},flag);
   await page.waitForFunction(flag=>flag==='alive'?lastNative?.alive:flag==='client'?lastClientNative?.alive:flag==='busy'?lastClientNative?.busy:flag==='installing'?lastNative?.installing:lastNative?.session_busy,flag);
   assert(await page.locator('#cleanup-review').isDisabled(),flag+' blocks cleanup');assert(await page.locator('#cleanup-delete').isDisabled());
   await page.locator('#cleanup-delete').evaluate(button=>button.click());assert.equal(await deleteCalls(),0,'An active '+flag+' cannot submit permanent deletion');
   await page.evaluate(flag=>{fixture[flag]=false;return poll();},flag);await page.waitForFunction(()=>!lastNative?.alive&&!lastNative?.installing&&!lastNative?.session_busy&&!lastClientNative?.alive&&!lastClientNative?.busy);
  }
  await page.waitForFunction(()=>!document.getElementById('world-profile').disabled);
  await page.selectOption('#world-profile','traditional');await page.locator('#switch-profile').click();await page.waitForFunction(()=>document.body.dataset.profile==='traditional');
  await page.locator('nav [data-tab=files]').click();await page.locator('#cleanup-exports').click();await page.waitForFunction(()=>document.getElementById('file-list').textContent.includes('session-export.zip'));
  assert.equal(await checked().count(),0,'Profile switch discards prior selection');assert(await page.locator('#cleanup-confirm').isHidden());
  await page.locator('#cleanup-select-page').click();await review();
  assert.equal((await page.evaluate(()=>fixture.calls.filter(x=>x.op==='file_delete_preview').at(-1))).a.__profile,'traditional');
  fs.mkdirSync('ui-reports',{recursive:true});
  for(const [label,width,height]of [['phone',393,852],['thor',1280,720]]){
   await page.setViewportSize({width,height});await page.locator('#cleanup-confirm').scrollIntoViewIfNeeded();await page.screenshot({path:'ui-reports/file-cleanup-'+label+'.png',fullPage:true});
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Cleanup fits '+label+' width');
  }
  await page.locator('#cleanup-understand').check();assert(!(await page.locator('#cleanup-delete').isDisabled()));
  // Backend revalidation errors must leave every file in place.
  await page.evaluate(()=>fixture.failDelete=true);await page.locator('#cleanup-delete').click();await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('Selected files changed'));
  assert.deepEqual(await page.evaluate(()=>fixture.removed),[]);assert.equal(await deleteCalls(),1);
  await page.locator('#cleanup-review').click();await page.locator('#cleanup-confirm').waitFor({state:'visible'});await page.locator('#cleanup-understand').check();
  await page.locator('#cleanup-delete').click();await page.waitForFunction(()=>fixture.removed.length===2&&document.getElementById('file-results').textContent==='This folder is empty.');
  assert.equal(await checked().count(),0);assert(await page.locator('#cleanup-confirm').isHidden());assert.equal(await deleteCalls(),2);
  assert.deepEqual(await page.evaluate(()=>fixture.removed.sort()),['exports/logs-export.zip','exports/session-export.zip']);
  const offlineCalls=await page.evaluate(()=>fixture.calls);assert(!offlineCalls.some(x=>x.op==='runtime_start'),'Cleanup never starts a runtime');assert(offlineCalls.some(x=>x.op==='native_files'),'Files browser uses native listing');
  assert.deepEqual(errors,[],'No UI JavaScript errors');
  console.log('PASS: offline protected browsing, page-only selection, confirmation/cancel, scoped/stale review invalidation, runtime gating, profile isolation, backend revalidation, deletion refresh and phone/Thor layout');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
