const {openTab,openClientOptions,revealControl}=require('./launcher-ui-helper.cjs');
const {chromium}=require('playwright');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert');
const root=path.resolve('app/src/main/assets/ui');
const server=http.createServer((req,res)=>{
 const name=new URL(req.url,'http://localhost').pathname.slice(1)||'index.html';
 if(!/^[\w.-]+$/.test(name)){res.writeHead(404);res.end();return;}
 try{res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(path.join(root,name)));}catch{res.writeHead(404);res.end();}
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})});
 try{
  const page=await browser.newPage({viewport:{width:393,height:852}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
   const parts=['content','login','player','state','system'].map(p=>'create_tables_'+p+'.sql');
   window.makeBundle=(archive,size=20,modified=10)=>({id:archive+'!peq/create_all_tables.sql',kind:'peq_bundle',origin:'uploaded',label:'Complete PEQ database · 5 parts',parts,selections:parts.map(p=>archive+'!peq/'+p),size,modified});
   const bundle=makeBundle('incoming/bundle.zip');
   window.fixture={profile:new URLSearchParams(location.search).get('profile')||'custom',calls:[],jobs:[],holdScan:false,candidates:[
    {id:'incoming/large.sql',kind:'sql',origin:'uploaded',size:900,modified:20},
    {id:'incoming/tie-b.sql',kind:'sql',origin:'uploaded',size:40,modified:50},
    {id:'incoming/tie-a.sql',kind:'sql',origin:'uploaded',size:40,modified:50},
    {id:'incoming/zero.sql',kind:'sql',origin:'uploaded',size:0,modified:0},
    {id:'incoming/missing.sql',kind:'sql',origin:'uploaded',size:null,modified:null},
    {id:'incoming/unknown.sql',kind:'sql',origin:'uploaded'},
    {id:'incoming/incomplete.zip!peq/create_all_tables.sql',kind:'unsupported_bundle',origin:'uploaded',label:'Incomplete PEQ database',reason:'Missing login part',size:100,modified:100},
    {id:'sources/current/utils/sql/eqemu_release/release-peq.sql.gz',kind:'sql',origin:'source',size:200,modified:30},
    {id:'sources/current/utils/sql/migrations/required/0001.sql',kind:'sql',origin:'source',size:2000,modified:40},
    bundle,...bundle.selections.map(id=>({id,kind:'sql',origin:'uploaded',size:1,modified:60}))
   ]};
   window.Trasc={call(id,op,input){setTimeout(()=>{
    const f=fixture,a=JSON.parse(input);f.calls.push({op,a});let result={};
    if(op==='native_state')result={profile:f.profile,installed:true,alive:true,status:'Runtime ready',free_bytes:50e9};
    else if(op==='client_native_state')result={installed:true,alive:false,busy:false,status:'Stopped'};
    else if(op==='state')result={profile:f.profile,running:false,settings:{ip:'127.0.0.1',login_port:f.profile==='takp'?6000:5999,repo:'fixture',ref:'main',workers:3,jobs:1},jobs:f.jobs,processes:{},source:{},maps_ready:false,database_imported:false,client:{},traditional:{components:{},build:{}},takp:{source_ready:true,components:{},build:{}},free_bytes:50e9};
    else if(op==='databases'){
     result={candidates:JSON.parse(JSON.stringify(f.candidates))};
     if(f.holdScan){f.holdScan=false;window.releaseScan=()=>window.nativeReply(id,{ok:true,result});return;}
    }else if(op==='pick'){
     const bundle=makeBundle('incoming/new-upload.zip',3,-100);f.candidates.push(bundle,...bundle.selections.map(id=>({id,kind:'sql',origin:'uploaded',size:1,modified:-100})));
     result={file:'new-upload.zip',path:'incoming/new-upload.zip'};
    }else if(op==='controller_state')result={sources:[],actions:[],layers:[{name:'Main',bindings:{}}],deadzone:.2,sensitivity:700};
    else if(op==='controller_capture')result={};
    else if(op==='files'||op==='native_files')result={path:'.',items:[],total:0,offset:0,next_offset:null};
    else if(op==='logs')result={text:'Profile log',names:['operation.log']};
    else if(op==='log_retention')result={count:5};
    else {result={id:String(f.jobs.length+1),operation:op,status:'done',result:{}};f.jobs.push(result);}
    window.nativeReply(id,{ok:true,result});
   },5);}};
  });
  const values=()=>page.locator('#db-candidate option').evaluateAll(options=>options.map(o=>o.value).filter(Boolean));
  const plain='incoming/large.sql',bundle='incoming/bundle.zip!peq/create_all_tables.sql',incomplete='incoming/incomplete.zip!peq/create_all_tables.sql',release='sources/current/utils/sql/eqemu_release/release-peq.sql.gz',migration='sources/current/utils/sql/migrations/required/0001.sql';
  for(const profile of ['custom','traditional','takp']){
   await page.goto('http://127.0.0.1:'+server.address().port+'/?profile='+profile);await openTab(page,'setup');
   await page.waitForFunction(p=>activeProfile===p&&!polling,profile);
   assert(await page.isVisible('#database-deployment'),'Shared database card visible for '+profile);
   assert(await page.isVisible('#db-sort'),'Sort dropdown visible for '+profile);
   assert.equal(await page.inputValue('#db-sort'),profile==='custom'?'recommended':'modified_desc','Sort preference survives profile reloads');
   await page.click('#scan-db');await page.waitForFunction(()=>!busy&&!databaseScanning);
   if(profile==='custom')assert.equal((await values())[0],bundle,'Recommended keeps complete seeds first');
   await page.selectOption('#db-candidate',plain);
   if(profile!=='takp')await page.check('#replace-db');
   await page.evaluate(()=>{seedSelections=['incoming/tie-a.sql'];});
   await page.selectOption('#db-sort','size_desc');
   assert.deepEqual(await values(),[plain,release,incomplete,'incoming/tie-a.sql','incoming/tie-b.sql',bundle,'incoming/zero.sql','incoming/missing.sql','incoming/unknown.sql'],'Numeric descending sizes, ties by ID and missing sizes last for '+profile);
   assert.equal(await page.inputValue('#db-candidate'),plain,'Sorting preserves exact selected candidate');
   assert(await page.locator('#db-candidate option[value="'+incomplete+'"]').isDisabled(),'Unsupported candidate remains disabled');
   assert.deepEqual(await page.evaluate(()=>seedSelections),['incoming/tie-a.sql'],'Sorting preserves manual bundle draft');
   await page.selectOption('#db-sort','modified_desc');
   assert.deepEqual(await values(),[incomplete,'incoming/tie-a.sql','incoming/tie-b.sql',release,plain,bundle,'incoming/zero.sql','incoming/missing.sql','incoming/unknown.sql'],'Numeric modified descending, epoch zero before missing dates for '+profile);
   assert.equal(await page.inputValue('#db-candidate'),plain);
   await page.evaluate(async()=>{fixture.candidates.reverse();await scanDB();});
   assert.equal(await page.inputValue('#db-candidate'),plain,'Refresh preserves selection');
   assert.equal(await page.inputValue('#db-sort'),'modified_desc','Refresh preserves sorting');
   await page.fill('#db-search','tie-');assert.deepEqual(await values(),['incoming/tie-a.sql','incoming/tie-b.sql'],'Search uses current sort');
   await page.selectOption('#db-candidate','incoming/tie-b.sql');await page.fill('#db-search','');
   assert.equal(await page.inputValue('#db-candidate'),'incoming/tie-b.sql','Clearing search preserves visible selection');
   await page.check('#db-show-scripts');await page.selectOption('#db-sort','size_desc');
   assert.equal((await values())[0],migration,'Size sort compares source scripts without recommended rank');
   assert.equal(await page.inputValue('#db-candidate'),'incoming/tie-b.sql');
   await page.selectOption('#db-sort','modified_desc');
   assert.equal((await values())[1],'incoming/bundle.zip!peq/create_tables_content.sql','Date sort includes advanced bundle parts');
   await page.fill('#db-search','missing.sql');assert.equal(await page.isDisabled('#import-db'),profile==='takp');
   assert((await page.textContent('#db-detail')).includes('modified time unavailable'));
   await page.fill('#db-search','does-not-exist');assert(await page.isDisabled('#import-db'));
   await page.fill('#db-search','tie-');
   await page.click('#upload-db');await page.waitForFunction(()=>!busy&&!databaseScanning);
   assert.equal(await page.inputValue('#db-candidate'),'incoming/new-upload.zip!peq/create_all_tables.sql','Upload preference wins over current sort');
   assert.equal(await page.inputValue('#db-sort'),'modified_desc','Upload retains sort');
   assert.equal(await page.inputValue('#db-search'),'');assert.equal(await page.isChecked('#db-show-scripts'),false);
   assert.deepEqual(await page.evaluate(()=>seedSelections),[],'Upload resets manual bundle draft');
   assert.equal(await page.isDisabled('#import-db'),profile!=='traditional','Profile import restrictions retained');
   if(profile==='takp'){
    assert(!(await page.isVisible('#import-db')),'TAKP catalog does not offer generic import');
    assert(await page.isVisible('#takp-initialize'),'Pinned TAKP initialization remains available');
    assert((await page.textContent('#db-detail')).includes('pinned database'));
    await page.evaluate(()=>{$('import-db').disabled=false;$('import-db').click();});await page.waitForFunction(()=>!busy);
    assert(!(await page.evaluate(()=>fixture.calls.some(c=>c.op==='import_database'))),'Even a forced TAKP generic import is guarded');
   }
   await page.evaluate(()=>{fixture.holdScan=true;scanDB();});await page.waitForFunction(()=>typeof releaseScan==='function');
   assert(await page.isDisabled('#db-sort'),'Sorting waits for active scan');
   await page.evaluate(()=>releaseScan());await page.waitForFunction(()=>!databaseScanning);
   await page.locator('#db-sort').focus();await page.evaluate(()=>launcherMenuController.command('accept'));
   assert.equal(await page.locator('dialog[open] .controller-select-options button').count(),3,'Controller opens all sort choices');
   await page.locator('dialog[open] .controller-select-options button').filter({hasText:'Size · largest first'}).click();
   await page.waitForFunction(()=>!document.querySelector('dialog[open]'));
   assert.equal(await page.inputValue('#db-sort'),'size_desc','Controller picker changes sorting');
   await page.selectOption('#db-sort','modified_desc');
   await page.locator('#db-sort').scrollIntoViewIfNeeded();
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Phone layout fits '+profile);
   fs.mkdirSync('ui-reports',{recursive:true});await page.screenshot({path:'ui-reports/database-sort-'+profile+'-mobile.png',fullPage:true});
   await page.setViewportSize({width:1280,height:720});
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Thor layout fits '+profile);
   await page.screenshot({path:'ui-reports/database-sort-'+profile+'-thor.png',fullPage:true});
   await page.setViewportSize({width:393,height:852});
  }
  assert.deepEqual(errors,[],'UI JavaScript errors');
  console.log('PASS: all three profiles share size/date descending sorts, deterministic ties, missing/zero metadata, selection/filter/refresh/upload safeguards, cross-profile preference, controller picker and phone/Thor layouts; TAKP pinned deployment preserved');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
