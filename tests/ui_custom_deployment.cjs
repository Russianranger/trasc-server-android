const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert'),http=require('http');
const {execFileSync}=require('child_process');
const ui=path.resolve('app/src/main/assets/ui');
const index=fs.readFileSync(path.join(ui,'index.html'),'utf8');
const start=index.indexOf('<div class="custom-deployment"'),end=index.indexOf('<div class="grid takp-setup-grid"',start);
assert(start>=0&&end>start,'Both Setup deployment tiles ship in the app');
assert(index.includes('src="custom-deployment.js"')&&index.includes('href="custom-deployment.css"'),'Shipped page loads the deployment controls and responsive styling');
const markup=index.slice(start,end);
// Generate the preview, conflict markers, content hashes, pagination rows and
// receipt with the same Python transaction and quest wrapper shipped in the APK.
// LoN binary-format qualification is covered separately by test_lon_data.py;
// this browser test consumes the common real deployment preview shape.
const fixtures=JSON.parse(execFileSync('python3',['-c',String.raw`
import json,sys,tempfile,threading,types
from pathlib import Path
sys.path.insert(0,'backend')
import custom_deployment as core,quest_sync,lon_data
from unittest.mock import patch
with tempfile.TemporaryDirectory() as temp:
 work=Path(temp)
 engine=types.SimpleNamespace(work=work,profile='custom',current_job={},cancel=threading.Event(),config={},processes={},server_running=lambda:False,check_cancel=lambda:None,log=lambda text:None)
 def write(name,content):
  file=work/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text(content)
 write('server/eqemu_config.json',json.dumps({'server':{'directories':{'quests':'quests','plugins':'quests/plugins','lua_modules':'quests/lua_modules'}}}))
 write('sources/current/trasc-source.json',json.dumps({'type':'github','repo':'https://github.com/Russianranger/Triptych-Triumvirate','ref':'main','commit':'a'*40}))
 for name in ['matched.lua','changed.lua','custom.lua']:write('sources/current/Release-NMS-Quests/'+name,'return "original"\n')
 write('sources/current/Release-NMS-Plugins/plugin.pm','1;\n')
 write('sources/current/Release-NMS-Quests/lua_modules/module.lua','return {}\n')
 initial=quest_sync.scan(engine)
 quest_sync.apply(engine,{'token':initial['token']})
 for n in range(45):write('sources/current/Release-NMS-Quests/new%02d.lua'%n,'return '+str(n)+'\n')
 write('sources/current/Release-NMS-Quests/changed.lua','return "updated source"\n')
 write('server/quests/custom.lua','return "local customization"\n')
 write('server/quests/runtime-only.lua','return "keep this quest"\n')
 preview=quest_sync.scan(engine)
 rows=quest_sync.files(engine,{'token':preview['token'],'limit':500})
 diff=quest_sync.diff(engine,{'token':preview['token'],'group':'quests','path':'changed.lua'})
 before=quest_sync.status(engine)
 applied=quest_sync.apply(engine,{'token':preview['token'],'include_new':True,'include_changed':True,'confirm_overwrite':True,'approve_conflicts':True})
 after=quest_sync.status(engine)
 def mysql(query):
  if 'COUNT(*)' in query:return 'COUNT(*)\n1\n'
  if 'FROM variables' in query:return 'value\ndefault\n'
  if 'FROM rule_sets' in query:return 'ruleset_id\tname\n1\tdefault\n'
  return 'rule_name\trule_value\nCustom:LoNDataPath\tlon_data\nCustom:LoNEnabled\ttrue\n'
 engine.mysql=mysql
 write('incoming/lon-fixture/data/archetypes/index.dat','index fixture')
 write('incoming/lon-fixture/data/archetypes/storage.dat','storage fixture')
 lon=core.preview(engine,'lon_data',[{'name':'lon_data','source':work/'incoming/lon-fixture/data','destination':work/'server/lon_data'}],{'path':'client/current','kind':'directory'},extra={'validation':{'valid':True,'parsed_archetypes':1,'errors':[],'warnings':[],'server_initialization':'pending_restart'}})
 lonrows=core.details(engine,{'token':lon['token'],'limit':500},'lon_data')
 lonapplied=core.apply(engine,'lon_data',{'token':lon['token']})
 lonapplied['validation']=lon['extra']['validation'];lonapplied['message']='Legends of Norrath files deployed and SHA-256 verified. Restart the server to initialize the card service.'
 verify={}
 for service_state in ('confirmed','failed','pending_restart','disabled'):
  service={'state':service_state,'evidence':'[LoN] card service listening on port 34000' if service_state=='confirmed' else 'Current world startup rejected card data' if service_state=='failed' else None,'world_running':service_state in ('confirmed','failed'),'world_started':12345,'log_warning':'A fresh server start is required' if service_state=='pending_restart' else None}
  rule={'enabled':service_state!='disabled','path':'lon_data'}
  layout={'lon_data':str(work/'server/lon_data'),'lon_rule':rule}
  with patch.object(lon_data,'validate',return_value=lon['extra']['validation']),patch.object(lon_data,'_service_report',return_value=service),patch.object(core,'destinations',return_value=layout):verify[service_state]=lon_data.verify(engine)
 print(json.dumps({'quest':{'preview':preview,'rows':rows,'diff':diff,'before':before,'applied':applied,'after':after},'lon':{'preview':lon,'rows':lonrows,'applied':lonapplied,'verify':verify,'before':{'profile':'custom','destination':str(work/'server/lon_data'),'recovery_required':False}}}))
`],{encoding:'utf8',maxBuffer:8*1024*1024}));
async function fullInterfaceChecks(browser){
 const native=JSON.parse(execFileSync('python3',['tests/test_client_native_status.py','--fixtures'],{encoding:'utf8'}));
 const server=http.createServer((req,res)=>{const name=req.url.split('?')[0]==='/'?'index.html':req.url.split('?')[0].slice(1);if(!/^[\w.-]+$/.test(name)){res.writeHead(404);return res.end();}try{res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.webp')?'image/webp':name.endsWith('.ttf')?'font/ttf':'text/html');res.end(fs.readFileSync(path.join(ui,name)));}catch{res.writeHead(404);res.end();}});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{for(const profile of ['custom','traditional','takp']){
  const page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  try{
   await page.addInitScript(({profile,native,fixtures})=>{
    window.fixture={profile,native,data:fixtures,calls:[],jobs:[],keyboard:[]};window.confirm=()=>true;
    const connection=()=>({profile:fixture.profile,host:{host:'127.0.0.1',port:5999,exists:true,can_save:true,revision:'host-1'},patch:{exe:'eqgame.exe',eligible:fixture.profile==='custom',patched:false,can_apply:fixture.profile==='custom',revision:'exe-1',download:{can_download:fixture.profile==='custom'}}});
    const state=()=>({profile:fixture.profile,running:false,settings:{ip:'127.0.0.1',login_port:5999,repo:'https://github.com/Russianranger/Triptych-Triumvirate',ref:'main',workers:3,jobs:2},source:{commit:'a'.repeat(40)},jobs:fixture.jobs,processes:{},maps_ready:true,database_imported:true,binaries_ready:true,client:{imported:true,files:10,bytes:1000},traditional:{components:{},build:{}},takp:{source_ready:true,components:{},build:{}},free_bytes:50e9});
    window.Trasc={launcherKeyboard(show){fixture.keyboard.push(show);},call(id,op,input){setTimeout(()=>{const f=fixture,args=JSON.parse(input);f.calls.push({op,args});let result={};try{
     if(op==='native_state')result={profile:f.profile,installed:true,alive:true,status:'Runtime ready',free_bytes:50e9};
     else if(op==='client_native_state')result=structuredClone(f.native[f.profile].stopped);
     else if(op==='state')result=state();
     else if(op==='client_connection_status')result=connection();
     else if(op==='quest_sync_status'||op==='lon_data_status'){if(f.profile!=='custom')throw Error('Deployment belongs to Custom');result=structuredClone(f.data[op==='quest_sync_status'?'quest':'lon'].before);}
     else if(op==='quest_sync_scan'||op==='lon_data_scan'){if(f.profile!=='custom')throw Error('Deployment belongs to Custom');result={id:op,operation:op,status:'done',result:structuredClone(f.data[op==='quest_sync_scan'?'quest':'lon'].preview)};f.jobs.push(result);}
     else if(op==='source_update_status')result={profile:f.profile,source_available:true,current_revision:'a'.repeat(40),target_revision:'main'};
     else if(op==='controller_state')result={sources:[],actions:[],layers:[{name:'Main',bindings:{}}],deadzone:.2,sensitivity:700};
     else if(op==='databases')result={candidates:[]};
     window.nativeReply(id,{ok:true,result});
    }catch(e){window.nativeReply(id,{ok:false,error:e.message});}},5);}};
   },{profile,native,fixtures});
   await page.goto('http://127.0.0.1:'+server.address().port+'/');
   await page.waitForFunction(profile=>activeProfile===profile&&!polling&&!!lastClientNative,profile);
   assert.equal(await page.isVisible('#custom-deployment'),profile==='custom','Setup deployment tools stay isolated to '+profile);
   if(profile==='custom'){
    await page.waitForFunction(()=>deploymentModels.quest.data?.source_available===true&&!customDeploymentStatusLoading);
    assert(await page.isEnabled('#quest-scan'),'Normal startup poll enables Custom scanning without a manual refresh');
    await page.click('#quest-scan');await page.waitForFunction(()=>!!deploymentModels.quest.preview?.token&&!busy&&!deploymentModels.quest.working);
    assert.equal(await page.locator('#quest-counts tr').count(),4,'Full shipped UI renders all actual backend groups');
    await page.locator('#custom-quest-sync h3').focus();await page.evaluate(()=>launcherMenuController.command('back'));
    assert.equal(await page.getAttribute('#custom-quest-sync','data-controller-card-collapsed'),'true','Controller B collapses the new tile');
    await page.evaluate(()=>launcherMenuController.command('accept'));
    assert.equal(await page.getAttribute('#custom-quest-sync','data-controller-card-collapsed'),'false','Controller A expands the new tile');
    await page.locator('#lon-source').focus();await page.evaluate(()=>launcherMenuController.command('accept'));assert((await page.evaluate(()=>fixture.keyboard)).includes(true),'Controller A opens Android keyboard on the card-source text field');await page.evaluate(()=>launcherMenuController.command('back'));
    fs.mkdirSync('ui-reports',{recursive:true});
    await page.locator('#custom-quest-sync').screenshot({path:'ui-reports/custom-deployment-thor.png'});
    await page.setViewportSize({width:393,height:852});await page.locator('#custom-quest-sync').screenshot({path:'ui-reports/custom-deployment-phone.png'});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'Full phone app contains the wide comparison table');
    await page.click('#quest-refresh-source');await page.waitForFunction(()=>currentTab==='build'&&fixture.calls.some(c=>c.op==='source_update_status'));
    assert((await page.evaluate(()=>fixture.calls)).some(c=>c.op==='source_update_status'),'Refresh Source opens the existing source-update workflow');
    assert(!(await page.evaluate(()=>fixture.calls)).some(c=>c.op==='source_update_apply'),'Refresh never silently downloads or applies another revision');
   }else assert(!(await page.evaluate(()=>fixture.calls)).some(c=>c.op.startsWith('quest_sync')||c.op.startsWith('lon_data')),'Other profiles never request Custom deployment APIs');
   assert.deepEqual(errors,[],'Full shipped interface has no browser exception for '+profile);
  }finally{await page.close();}
 }}finally{await new Promise(resolve=>server.close(resolve));}
}
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:393,height:852}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setContent(`<style>${fs.readFileSync(path.join(ui,'style.css'),'utf8')}\n${fs.readFileSync(path.join(ui,'custom-deployment.css'),'utf8')}</style><main>${markup}</main>`);
  await page.addScriptTag({content:`
   const $=id=>document.getElementById(id),activeUiActions=new Set();let activeProfile='custom',busy=0,sessionAction=null,currentTab='setup';
   let lastNative={profile:'custom',alive:true},lastState={profile:'custom',running:false,binaries_ready:true,database_imported:true,jobs:[]},lastClientNative={profile:'custom',alive:false,busy:false};
   const operationLabels={};window.fixture={data:${JSON.stringify(fixtures)},calls:[],notices:[],confirm:true,hold:false,fail:false,pickHold:false,pickWaiter:null,waiters:[],recovery:false};
   function bytes(n){return n+' bytes';}function notice(text,error=false){fixture.notices.push({text,error});}function renderSessionControls(){if(typeof renderCustomDeploymentControls==='function')renderCustomDeploymentControls();}async function poll(){}function tab(name){fixture.tab=name;currentTab=name;}window.confirm=text=>{fixture.confirmText=text;return fixture.confirm;};
   async function api(op,args={}){
    fixture.calls.push({op,args,profile:activeProfile});const kind=op.startsWith('lon_data')?'lon':'quest',data=fixture.data[kind];
    if(op.endsWith('_status'))return {...data.before,recovery_required:fixture.recovery};
    if(op.endsWith('_files')){let rows=data.rows.rows.filter(r=>args.classification==='all'||r.classification===args.classification||args.classification==='conflict'&&r.conflict);if(args.query)rows=rows.filter(r=>r.path.includes(args.query));if(args.sort==='modified_desc')rows.sort((a,b)=>(b.source?.modified||b.destination?.modified||0)-(a.source?.modified||a.destination?.modified||0));if(args.sort==='size_desc')rows.sort((a,b)=>(b.source?.bytes||b.destination?.bytes||0)-(a.source?.bytes||a.destination?.bytes||0));if(args.sort==='classification')rows.sort((a,b)=>a.classification.localeCompare(b.classification));return {rows:rows.slice(args.offset,args.offset+args.limit),total:rows.length,offset:args.offset,limit:args.limit};}
    if(op==='quest_sync_diff')return data.diff;
    if(op==='lon_input_state')return {busy:true,cancellable:true,files:8,bytes:65536,total:131072,status:'Staging selected folder'};
    if(op==='lon_input_cancel'){if(fixture.pickWaiter){fixture.pickWaiter({source:'incoming/cancelled',kind:'directory'});fixture.pickWaiter=null;}return {cancelled:true};}
    if(op==='pick'){if(fixture.pickHold)return await new Promise(resolve=>fixture.pickWaiter=resolve);return {source:'incoming/selected/data',kind:args.kind==='lon-data-zip'?'zip':'directory',files:2,bytes:1024,name:'LegendsOfNorrath/data'};}
    if(op==='cancel'){for(const resolve of fixture.waiters.splice(0))resolve(null);return {cancelled:true};}
    return {};
   }
   async function job(op,args={}){
    fixture.calls.push({op,args,profile:activeProfile});if(fixture.fail)throw Error('Fixture transfer interrupted; rollback completed.');
    if(fixture.hold)await new Promise(resolve=>fixture.waiters.push(resolve));
    if(op==='custom_deployment_recover'){fixture.recovery=false;return {message:'Recovery completed.'};}
    if(op==='stop'){lastState.running=false;return {message:'Server stopped.'};}if(op==='start'){lastState.running=true;return {message:'Server started.'};}
    if(op==='lon_data_verify')return structuredClone(fixture.data.lon.verify[fixture.verifyState||'pending_restart']);
    const kind=op.startsWith('lon_data')?'lon':'quest';return structuredClone(fixture.data[kind][op.endsWith('_scan')?'preview':'applied']);
   }
  `});
  await page.addScriptTag({path:path.join(ui,'custom-deployment.js')});
  await page.evaluate(()=>loadCustomDeployment(true));
  assert(await page.isEnabled('#quest-scan'));assert(await page.isEnabled('#lon-scan'));assert(await page.isDisabled('#quest-apply'),'Apply requires an actual preview');
  const idle=()=>page.waitForFunction(()=>!busy&&!customDeploymentStatusLoading&&!Object.values(deploymentModels).some(m=>m.working||m.picking||m.filesLoading));
  await page.click('#quest-scan');await idle();
  assert.equal(await page.locator('#quest-counts tr').count(),4,'Quests, Perl plugins, Lua modules and combined totals appear');
  const expected=fixtures.quest.preview.summary;
  assert((await page.textContent('#quest-counts')).includes('Combined total'));
  const totalCells=await page.locator('#quest-counts tr:last-child td').allTextContents();
  assert.deepEqual(totalCells.slice(1),['new','changed','matching','runtime_only','errors','conflicts'].map(k=>String(expected[k])),'Exact backend counts, including local conflicts, are rendered');
  assert((await page.textContent('#quest-source-version')).includes('a'.repeat(40)),'Exact selected source commit is shown');
  assert((await page.textContent('#quest-last-sync')).includes('a'.repeat(40)),'Last successful synchronization identity is shown');
  assert(await page.isDisabled('#quest-apply'),'Changed files require review approval');
  await page.check('#quest-approve');assert(await page.isDisabled('#quest-apply'),'Locally customized files need independent approval');
  await page.check('#quest-conflicts');assert(await page.isEnabled('#quest-apply'));
  await page.locator('#quest-file-inspection summary').click();await page.waitForFunction(()=>deploymentModels.quest.rows.length>0);await idle();
  assert.equal(await page.locator('#quest-files .deployment-file').count(),40,'File inspector is bounded to one page');
  assert((await page.textContent('#quest-files')).includes('Runtime:')&&(await page.textContent('#quest-files')).includes('Source:'),'Both metadata sides are displayed');
  await page.click('#quest-next');await idle();assert((await page.textContent('#quest-files-status')).includes('Files 41–'));
  await page.selectOption('#quest-filter','runtime_only');await idle();assert.equal(await page.locator('#quest-files .deployment-file').count(),1);assert((await page.textContent('#quest-files')).includes('runtime-only.lua'),'Runtime-only filter uses exact backend classification');
  await page.selectOption('#quest-filter','changed');await idle();assert.equal(await page.locator('#quest-files .deployment-file').count(),2);
  await page.getByRole('button',{name:'Show text diff'}).first().click();assert((await page.textContent('#quest-files pre')).includes('updated source'),'Changed text can be inspected with a bounded backend diff');
  await page.selectOption('#quest-sort','mtime_desc');await idle();assert.equal(await page.evaluate(()=>fixture.calls.filter(c=>c.op==='quest_sync_files').at(-1).args.sort),'modified_desc');
  await page.selectOption('#quest-mode','new');
  assert(await page.isHidden('#quest-approve-row')&&await page.isHidden('#quest-conflicts-row'),'New-only mode never asks to overwrite');
  assert((await page.textContent('#quest-transfer')).includes(expected.new+' selected files'));
  assert((await page.textContent('#quest-transfer')).includes(String(expected.new_bytes)),'New-only selection displays exact bytes');
  await page.selectOption('#quest-mode','both');await page.check('#quest-approve');await page.check('#quest-conflicts');
  await page.evaluate(()=>fixture.confirm=false);await page.click('#quest-apply');await idle();
  assert.equal(await page.evaluate(()=>fixture.calls.filter(c=>c.op==='quest_sync_apply').length),0,'Declining confirmation performs no mutation');
  await page.evaluate(()=>{fixture.confirm=true;lastState.running=true;renderCustomDeploymentControls();});
  assert(await page.isEnabled('#quest-scan'),'Read-only scans remain available while server runs');assert(await page.isDisabled('#quest-apply'),'Live server replacement is blocked');
  await page.click('#quest-stop');await idle();assert(await page.isHidden('#quest-preview'),'Stopping the server requires a fresh preview');
  await page.click('#quest-scan');await idle();await page.check('#quest-approve');await page.check('#quest-conflicts');await page.click('#quest-apply');await idle();
  const apply=await page.evaluate(()=>fixture.calls.find(c=>c.op==='quest_sync_apply'));
  assert.deepEqual(apply.args,{token:fixtures.quest.preview.token,include_new:true,include_changed:true,confirm_overwrite:true,approve_conflicts:true},'Apply submits the exact preview token and separate approvals');
  assert(await page.isVisible('#quest-report'));assert((await page.textContent('#quest-report-summary')).includes(fixtures.quest.applied.copied_files+' files copied'),'Receipt displays verified copied file count');
  assert((await page.textContent('#quest-validation')).includes('Cake Defense')&&(await page.textContent('#quest-validation')).includes('Native achievements'),'Actual October witnesses appear in the post-sync report');
  assert((await page.textContent('#quest-report')).includes('does not apply database migrations'));
  await page.click('#lon-pick-folder');await idle();assert.equal(await page.inputValue('#lon-source'),'incoming/selected/data');
  assert.equal(await page.evaluate(()=>fixture.calls.find(c=>c.op==='pick').args.kind),'lon-data-folder','Native Android folder chooser is used');
  await page.click('#lon-scan');await idle();assert((await page.textContent('#lon-destination')).includes('/server/lon_data'),'Actual configured card destination is shown without an extra data component');
  await page.click('#lon-apply');await idle();assert((await page.textContent('#lon-report')).includes('pending until the server is started'),'Card-service initialization is never claimed from a file copy alone');
  for(const serviceState of ['confirmed','failed','pending_restart','disabled']){
   await page.evaluate(state=>{fixture.verifyState=state;lastState.running=state==='confirmed'||state==='failed';renderCustomDeploymentControls();},serviceState);
   assert(await page.isEnabled('#lon-verify'),'Read-only verification is available while the server runs');
   await page.click('#lon-verify');await idle();
   const state=await page.locator('#lon-validation [data-service-state]').getAttribute('data-service-state');assert.equal(state,serviceState,'Top-level actual service result controls initialization status');
   assert.equal(await page.locator('#lon-validation [data-service-state=pending_restart]').count(),serviceState==='pending_restart'?1:0,'Static validation pending state never overrides current service evidence');
   assert((await page.textContent('#lon-validation')).includes('Card data structure and server-required records validated.'),'Static data validity remains separate from startup status');
   if(serviceState==='confirmed'){assert((await page.textContent('#lon-validation')).includes('[LoN] card service listening on port 34000'));assert(!(await page.textContent('#lon-report-summary')).includes('Deployment completed'),'Read-only verification does not claim it copied files');}
   if(serviceState==='failed')assert((await page.textContent('#lon-validation')).includes('Current world startup rejected card data'));
   if(serviceState==='disabled'){const text=await page.textContent('#lon-validation');assert(text.includes('active Custom:LoNEnabled rule'));assert(!text.includes('Files were deployed'),'Read-only verification never claims deployment');}
  }
  await page.evaluate(()=>{lastState.running=false;renderCustomDeploymentControls();});
  await page.evaluate(()=>{fixture.pickHold=true;});await page.click('#lon-pick-zip');await page.waitForFunction(()=>deploymentModels.lon.picking);await page.waitForTimeout(800);
  assert((await page.textContent('#lon-progress-detail')).includes('65536'),'SAF staging reports live byte counts');
  await page.click('#lon-cancel');await idle();assert((await page.evaluate(()=>fixture.calls)).some(c=>c.op==='lon_input_cancel'),'SAF staging cancellation uses native transfer API');
  await page.evaluate(()=>{fixture.pickHold=false;fixture.hold=true;});await page.click('#quest-scan');await page.waitForFunction(()=>deploymentModels.quest.working);
  assert(await page.isDisabled('#lon-scan'),'Another deployment cannot interfere');await page.click('#quest-cancel');await idle();assert((await page.evaluate(()=>fixture.calls)).some(c=>c.op==='cancel'),'Backend cancellation is exposed');
  await page.evaluate(()=>{fixture.hold=false;fixture.fail=true;});await page.click('#quest-scan');await idle();assert((await page.textContent('#quest-status')).includes('interrupted'));assert(await page.isDisabled('#quest-apply'),'Failed preview never enables mutation');
  await page.evaluate(()=>{fixture.fail=false;fixture.recovery=true;deploymentModels.quest.data={recovery_required:true};renderCustomDeploymentControls();});
  assert(await page.isVisible('#quest-recover'));await page.click('#quest-recover');await idle();assert((await page.evaluate(()=>fixture.calls)).some(c=>c.op==='custom_deployment_recover'));
  // A stale response may never populate another profile or make its actions live.
  for(const profile of ['traditional','takp']){
   await page.evaluate(profile=>{activeProfile=profile;lastNative.profile=profile;lastState.profile=profile;lastClientNative.profile=profile;renderCustomDeploymentControls();},profile);
   assert(await page.isHidden('#custom-deployment'));
   const count=await page.evaluate(()=>fixture.calls.length);await page.evaluate(()=>scanDeployment('quest').catch(()=>{}));assert.equal(await page.evaluate(()=>fixture.calls.length),count,'Other profiles cannot submit a hidden sync action');
  }
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'Phone layout keeps wide comparison tables inside their card');
  assert.deepEqual(errors,[],'Deployment interface has no browser exceptions');
  await page.close();
  await fullInterfaceChecks(browser);
 }finally{await browser.close();}
 console.log('Custom deployment UI checks passed.');
})().catch(e=>{console.error(e);process.exit(1);});
