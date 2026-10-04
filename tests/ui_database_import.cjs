const {chromium}=require('playwright');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert');
const root=path.resolve('app/src/main/assets/ui');
const server=http.createServer((req,res)=>{
 const name=req.url==='/'?'index.html':req.url.slice(1);
 if(!/^[\w.-]+$/.test(name)){res.writeHead(404);res.end();return;}
 try{res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(path.join(root,name)));}catch{res.writeHead(404);res.end();}
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:393,height:852}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
   const parts=['content','login','player','state','system'].map(x=>'create_tables_'+x+'.sql');
   const bundle=archive=>({id:archive+'!peq-dump/create_all_tables.sql',kind:'peq_bundle',origin:'uploaded',label:'Complete PEQ database · 5 parts',parts,selections:parts.map(p=>archive+'!peq-dump/'+p),size:8e8});
   window.fixture={profile:'traditional',calls:[],jobs:[],candidates:[],upload:'incoming/20261004-peq-latest.zip',holdScan:false,savedMaps:''};
   window.addBundle=archive=>{const c=bundle(archive);fixture.candidates.push(c,...c.selections.map(id=>({id,kind:'sql',origin:'uploaded',size:1000})));return c.id;};
   window.oldBundle=addBundle('incoming/older-peq.zip');
   fixture.candidates.push({id:'sources/current/utils/sql/eqemu_release/release-peq.sql.gz',kind:'sql',origin:'source',size:8e8});
   for(let i=0;i<600;i++)fixture.candidates.push({id:'sources/current/utils/sql/migrations/required/'+String(i).padStart(4,'0')+'.sql',kind:'sql',origin:'source',size:1000});
   window.Trasc={call(id,op,input){setTimeout(()=>{
    const f=fixture,a=JSON.parse(input);f.calls.push({op,a});let result={};
    if(op==='native_state')result={profile:f.profile,installed:true,alive:true,status:'Runtime ready',free_bytes:50e9};
    else if(op==='client_native_state')result={installed:true,alive:false,busy:false,status:'Stopped'};
    else if(op==='state')result={profile:f.profile,running:false,settings:{ip:'127.0.0.1',login_port:5999,repo:'fixture',ref:'main',workers:3,jobs:1,maps_url:f.savedMaps},jobs:f.jobs,processes:{},source:{},maps_ready:false,database_imported:false,client:{},traditional:{components:{},build:{runtime_ready:true,source_supported:true,build_allowed:true}},free_bytes:50e9};
    else if(op==='controller_state')result={sources:[],actions:[],layers:[{name:'Main',bindings:{}}],deadzone:.2,sensitivity:700};
    else if(op==='controller_capture')result={};
    else if(op==='files'||op==='native_files')result={path:'.',items:[],total:0,offset:0,next_offset:null};
    else if(op==='logs')result={text:'Profile log',names:['operation.log']};
    else if(op==='log_retention')result={count:5};
    else if(op==='pick'){
     const archive=f.upload.startsWith('incoming/')?f.upload:'incoming/'+f.upload;
     if(f.unsupported)f.candidates.push({id:archive+'!peq-dump/create_all_tables.sql',kind:'unsupported_bundle',origin:'uploaded',label:'Incomplete PEQ database',reason:'PEQ bundle is missing create_tables_login.sql',size:1000});
     else if(!f.candidates.some(c=>c.id.startsWith(archive+'!')))addBundle(archive);
     result=f.upload.startsWith('incoming/')?{file:archive.split('/').pop(),path:archive,name:'peq-latest.zip'}:{file:f.upload,name:'peq-latest.zip'};
    }else if(op==='databases'){
     result={candidates:JSON.parse(JSON.stringify(f.candidates))};
     if(f.holdScan){f.holdScan=false;window.heldScanReply=()=>window.nativeReply(id,{ok:true,result});return;}
    }else {
     result={id:String(f.jobs.length+1),operation:op,status:'done',result:{message:'Imported selected database'}};f.jobs.push(result);
    }
    window.nativeReply(id,{ok:true,result});
   },5);}};
  });
  await page.goto('http://127.0.0.1:'+server.address().port+'/');
  await page.waitForFunction(()=>activeProfile==='traditional'&&!polling);
  assert.equal(await page.inputValue('#maps-url'),'https://github.com/Russianranger/eqemu-maps');
  assert.equal(await page.inputValue('#maps-ref'),'');
  await page.fill('#maps-url','https://github.com/example/custom-maps');
  await page.evaluate(async()=>{await poll();});
  assert.equal(await page.inputValue('#maps-url'),'https://github.com/example/custom-maps','Polling must preserve a typed maps URL');
  await page.evaluate(async()=>{fixture.savedMaps='https://github.com/example/saved-maps';initialSettings=false;await poll();});
  assert.equal(await page.inputValue('#maps-url'),'https://github.com/example/saved-maps','Existing saved nonempty maps URL overrides the new default');
  await page.click('#scan-db');await page.waitForFunction(()=>!busy);
  assert.equal(await page.locator('#db-candidate option').count(),2,'Hundreds of source migrations and recognized bundle parts are hidden');
  assert.equal(await page.inputValue('#db-candidate'),await page.evaluate(()=>oldBundle),'Ordinary scan selects a complete seed');
  assert.equal(await page.textContent('#import-db'),'Import complete PEQ database');
  await page.click('#upload-db');await page.waitForFunction(()=>!busy);
  const selected='incoming/20261004-peq-latest.zip!peq-dump/create_all_tables.sql';
  assert.equal(await page.inputValue('#db-candidate'),selected,'Newly uploaded ZIP is selected instead of an older seed');
  assert.equal(await page.locator('#db-parts li').count(),5);
  assert.deepEqual(await page.locator('#db-parts li').allTextContents(),['create_tables_content.sql','create_tables_login.sql','create_tables_player.sql','create_tables_state.sql','create_tables_system.sql']);
  assert.equal(await page.locator('#db-candidate option').count(),3);
  const seedLabels=await page.locator('#db-candidate option').allTextContents();assert(seedLabels.some(x=>x.includes('older-peq.zip'))&&seedLabels.some(x=>x.includes('20261004-peq-latest.zip')),'Touch dropdown names distinguish uploaded archives');
  assert((await page.textContent('#db-detail')).includes('20261004-peq-latest.zip'));
  assert(await page.isDisabled('#seed-add'),'Complete bundles must use their single import action');
  await page.check('#replace-db');await page.click('#import-db');await page.waitForFunction(()=>!busy);
  const request=await page.evaluate(()=>fixture.calls.find(x=>x.op==='import_database'));
  assert.deepEqual(request.a,{selection:selected,replace:true,__profile:'traditional'},'Import passes the same exact bundle ID; backend expands ordered parts');
  await page.fill('#db-search','create_tables_login');
  assert.equal(await page.locator('#db-candidate option').count(),2,'Search includes a complete bundle’s part filenames');
  await page.fill('#db-search','no matching file');assert(await page.isDisabled('#import-db'));
  await page.fill('#db-search','');await page.check('#db-show-scripts');
  assert.equal(await page.locator('#db-candidate option').count(),613,'Advanced mode preserves manually selectable SQL parts and source scripts');
  await page.fill('#db-search','0042');assert.equal(await page.locator('#db-candidate option').count(),1);
  assert((await page.inputValue('#db-candidate')).endsWith('0042.sql'));
  assert.equal(await page.textContent('#import-db'),'Import selected database');
  await page.fill('#db-search','');await page.selectOption('#db-candidate',selected.replace('create_all_tables.sql','create_tables_content.sql'));
  await page.locator('[data-traditional-only] > summary').filter({hasText:'Advanced:'}).click();
  await page.click('#seed-add');await page.waitForFunction(()=>!busy);
  assert((await page.textContent('#seed-bundle')).includes('create_tables_content.sql'));
  await page.evaluate(()=>{fixture.upload='20261005-newer.zip';});
  await page.click('#upload-db');await page.waitForFunction(()=>!busy);
  assert.equal(await page.inputValue('#db-candidate'),'incoming/20261005-newer.zip!peq-dump/create_all_tables.sql','Bare picker filename is matched to its incoming archive');
  assert.equal(await page.isChecked('#db-show-scripts'),false);
  assert.equal(await page.inputValue('#db-search'),'');
  assert(!(await page.textContent('#seed-bundle')).includes('create_tables_content.sql'),'Uploading another archive clears the old manual split bundle');
  assert(await page.isDisabled('#seed-import'));
  await page.evaluate(()=>{fixture.upload='incoming/incomplete.zip';fixture.unsupported=true;});
  await page.click('#upload-db');await page.waitForFunction(()=>!busy);
  assert((await page.textContent('#db-detail')).includes('missing create_tables_login.sql'));
  assert(await page.isDisabled('#import-db'));
  assert(await page.locator('#db-candidate option[value="incoming/incomplete.zip!peq-dump/create_all_tables.sql"]').isDisabled());
  assert.equal(await page.locator('#db-parts li').count(),0);
  // A stale response from an earlier scan must not replace the current archive.
  await page.evaluate(()=>{fixture.holdScan=true;scanDB().catch(()=>{});});await page.waitForFunction(()=>typeof heldScanReply==='function');
  await page.evaluate(async()=>{fixture.candidates=fixture.candidates.filter(c=>!c.id.startsWith('incoming/incomplete.zip!'));await scanDB('incoming/20261004-peq-latest.zip');heldScanReply();});
  assert.equal(await page.inputValue('#db-candidate'),selected);
  assert.equal(await page.locator('#db-parts li').count(),5);
  await page.evaluate(()=>{activeProfile='custom';document.body.dataset.profile='custom';fixture.profile='custom';renderDatabaseSelection();});
  assert(await page.isDisabled('#import-db'),'Split PEQ requires Traditional');
  assert((await page.textContent('#db-detail')).includes('Traditional EQEmu'));
  assert(await page.locator('#db-candidate option[value="sources/current/utils/sql/eqemu_release/release-peq.sql.gz"]').count()===1,'Custom release-peq full seed stays visible');
  await page.selectOption('#db-candidate','sources/current/utils/sql/eqemu_release/release-peq.sql.gz');assert(!(await page.isDisabled('#import-db')),'Custom full source seed remains importable');
  await page.evaluate(()=>{activeProfile='traditional';document.body.dataset.profile='traditional';fixture.profile='traditional';});await page.selectOption('#db-candidate',selected);
  fs.mkdirSync('ui-reports',{recursive:true});
  await page.locator('#db-candidate').scrollIntoViewIfNeeded();await page.screenshot({path:'ui-reports/database-import-mobile.png',fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Database import fits mobile width');
  await page.setViewportSize({width:1280,height:720});await page.screenshot({path:'ui-reports/database-import-thor.png',fullPage:true});
  assert.deepEqual(errors,[],'UI JavaScript errors');
  console.log('PASS: one-choice complete PEQ import, five-part preview, exact uploaded selection, script filter/search, manual bundle reset, incomplete/stale safeguards and maps defaults');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
