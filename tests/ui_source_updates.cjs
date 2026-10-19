const {openTab,openClientOptions,revealControl}=require('./launcher-ui-helper.cjs');
const {chromium}=require('playwright');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert');
const root=path.resolve('app/src/main/assets/ui');
const server=http.createServer((req,res)=>{const name=req.url==='/'?'index.html':req.url.slice(1);if(!/^[\w.-]+$/.test(name)){res.writeHead(404);res.end();return;}try{res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(path.join(root,name)));}catch{res.writeHead(404);res.end();}});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({headless:true});
 try{
  fs.mkdirSync('ui-reports',{recursive:true});
  for(const profile of ['custom','traditional','takp']){
   const page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.addInitScript(profile=>{
    const f=window.fixture={profile,calls:[],jobs:[],client:false,running:false,applied:false,staged:false,requiresFresh:profile==='custom',conflict:false,skeletonEnabled:false,hold:false};
    const preview=()=>({profile,token:profile+'-review',from_commit:'old-'+profile,to_commit:'new-'+profile,apply_allowed:!f.conflict,up_to_date:f.applied,counts:{changed:f.applied?0:2,added:f.applied?0:2,deleted:0},files:{changed:['zone/player_bot.cpp','tests/player-bots/run.py'],added:['tests/player-bots/yaulp_spell_tests.py','docs/player-bots-yaulp-ai.md'],deleted:[]},conflicts:f.conflict?['zone/local.cpp']:[],conflict_count:f.conflict?1:0,message:f.conflict?'Keep local changes; this update cannot be applied.':'Verified source changes. Existing deployed binaries are retained.'});
    const skeletons=()=>({supported:true,available:true,restore_available:f.skeletonEnabled,enabled:f.skeletonEnabled,state:f.skeletonEnabled?'enabled':'off',message:f.skeletonEnabled?'Classic skeletons enabled. Originals retained.':'Original skeleton models selected.'});
    const update=()=>({profile,source_available:true,current_revision:f.applied?'new-'+profile:'old-'+profile,target_revision:profile==='custom'?'main':'new-'+profile,deployed_revision:'old-'+profile,update_build_ready:f.staged,requires_fresh_build:f.requiresFresh,cache_reusable:!f.requiresFresh,cache_message:f.requiresFresh?'This historical Custom cache needs one explicit fresh build. Its old output is retained.':'Verified compatible Ninja cache; unchanged objects are reused'});
    f.state=()=>{const build={runtime_ready:true,build_allowed:profile!=='takp'||f.applied,staged_valid:f.staged,deployed_valid:true},deployment={start_allowed:true,deployed_valid:true,deploy_allowed:f.staged,client_data_allowed:true,rollback_allowed:true};return {profile,version:'0.6.25',running:f.running,settings:{ip:'127.0.0.1',login_port:profile==='takp'?6000:5999,repo:'https://github.com/Russianranger/Server',ref:'main',workers:3,jobs:1},processes:{},jobs:f.jobs,source:{commit:f.applied?'new-'+profile:'old-'+profile},maps_ready:true,database_imported:true,binaries_ready:true,build_ready:f.staged,client:{imported:true,prepared:true,skeletons:skeletons()},traditional:{build,deployment,components:{}},takp:{build,deployment,source_ready:f.applied,database_ready:true,bot_schema_ready:true,local_accounts:1,quests_ready:true,maps_ready:true,components:{}},free_bytes:50e9};};
    f.finish=()=>{const j=f.jobs.at(-1);j.status='done';j.result=preview();f.hold=false;};
    window.Trasc={call(id,op,input){setTimeout(()=>{const a=JSON.parse(input);f.calls.push({op,args:a});let result={};
     if(op==='native_state')result={profile,installed:true,alive:true,installing:false,session_busy:false,status:'Runtime ready',free_bytes:50e9};
     else if(op==='client_native_state')result={profile,installed:true,alive:f.client,busy:false,status:f.client?'Client active':'Client stopped'};
     else if(op==='state')result=f.state();
     else if(op==='controller_state')result={sources:[],actions:[],layers:[{name:'Main',bindings:{}}],deadzone:.2,sensitivity:700};
     else if(op==='source_update_status')result=update();
     else if(op==='takp_skeleton_status')result=skeletons();
     else if(['source_update_preview','source_update_apply','build_update','deploy_update','set_takp_skeletons'].includes(op)){
      const j={id:'job-'+f.jobs.length,operation:op,status:'done',result:{message:'Done.'}};
      if(op==='source_update_preview'){j.result=preview();if(f.hold)j.status='running';}
      else if(op==='source_update_apply'){f.applied=true;j.result={...preview(),applied:true,message:'Source updated; deployed server retained.'};}
      else if(op==='build_update'){f.requiresFresh=false;f.staged=true;j.result={message:'Updated build verified and staged.'};}
      else if(op==='deploy_update'){f.staged=false;j.result={message:'Updated binaries deployed. Previous binaries retained.'};}
      else if(op==='set_takp_skeletons'){f.skeletonEnabled=a.enabled;j.result={message:'Model choice saved.',skeletons:skeletons()};}
      f.jobs.push(j);result={id:j.id};
     }
     window.nativeReply(id,{ok:true,result});
    },5);}};
   },profile);
   await page.goto(`http://127.0.0.1:${server.address().port}/`);await openTab(page,'setup');
   const idle=()=>page.waitForFunction(()=>lastState&&lastClientNative&&!polling&&busy===0&&!sourceUpdateLoading&&!takpSkeletonLoading);
   await idle();await openTab(page,'build');await idle();
   assert.equal(await page.isDisabled('#start-server'),false,'Legacy deployed server remains startable even while source needs updating');
   assert(await page.isDisabled('#source-update-deploy'),'An old stage cannot be called an updated build');
   assert.equal(await page.isVisible('#source-update-fresh'),profile==='custom','Only unqualified historical caches request a fresh build');
   await page.click('#source-update-check');await idle();
   assert((await page.textContent('#source-update-counts')).includes('2 changed · 2 added · 0 removed'));
   assert.equal(await page.isDisabled('#source-update-apply'),false);
   assert.equal(await page.evaluate(()=>fixture.calls.filter(c=>c.op==='source_update_apply').length),0,'Review does not apply source changes');
   if(profile==='custom'){
    await page.fill('#source-update-ref','feature-fix');assert(await page.isDisabled('#source-update-apply'),'Changing target invalidates its review');
    await page.click('#source-update-check');await idle();assert.equal(await page.evaluate(()=>fixture.calls.filter(c=>c.op==='source_update_preview').at(-1).args.ref),'feature-fix');
   }
   await page.evaluate(async()=>{fixture.client=true;await poll();});assert(await page.isDisabled('#source-update-apply'),'Native client activity blocks updates');
   await page.evaluate(async()=>{fixture.client=false;await poll();});
   await page.click('#source-update-apply');await idle();assert.equal(await page.isDisabled('#start-server'),false,'Source update preserves server startup');
   assert.equal(await page.evaluate(()=>fixture.calls.filter(c=>['build_update','deploy_update'].includes(c.op)).length),0,'Applying source does not compile or deploy');
   await page.click(profile==='custom'?'#source-update-fresh':'#source-update-build');await idle();
   const build=await page.evaluate(()=>fixture.calls.filter(c=>c.op==='build_update').at(-1));assert.equal(build.args.jobs,1);assert.equal(build.args.allow_fresh===true,profile==='custom');
   assert.equal(await page.isDisabled('#source-update-deploy'),false);
   await page.click('#source-update-deploy');await idle();assert(await page.isDisabled('#source-update-deploy'));
   await page.evaluate(()=>fixture.conflict=true);await page.click('#source-update-check');await idle();assert(await page.isDisabled('#source-update-apply'));
   assert((await page.textContent('#source-update-files')).includes('Keep local edit: zone/local.cpp'));
   await page.screenshot({path:'ui-reports/source-updates-'+profile+'-1280.png',fullPage:true});
   await page.setViewportSize({width:393,height:852});await page.locator('#source-updates-panel').scrollIntoViewIfNeeded();
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Updates fit a narrow screen');
   await page.screenshot({path:'ui-reports/source-updates-'+profile+'-393.png',fullPage:true});
   if(profile==='takp'){
    await openTab(page,'appearance');await idle();
    await page.check('#takp-skeleton-enabled');assert.equal(await page.evaluate(()=>fixture.calls.filter(c=>c.op==='set_takp_skeletons').length),0,'Model checkbox requires explicit application');
    await page.click('#takp-skeleton-apply');await idle();assert(await page.isChecked('#takp-skeleton-enabled'));assert.equal(await page.isDisabled('#takp-skeleton-restore'),false);
    await page.evaluate(async()=>{fixture.client=true;await poll();});assert(await page.isDisabled('#takp-skeleton-restore'),'Active client blocks archive restoration');
    await page.evaluate(async()=>{fixture.client=false;await poll();});await page.click('#takp-skeleton-restore');await idle();assert.equal(await page.isChecked('#takp-skeleton-enabled'),false);
    const operations=await page.evaluate(()=>fixture.calls.filter(c=>c.op==='set_takp_skeletons').map(c=>c.args.enabled));assert.deepEqual(operations,[true,false]);
    await page.screenshot({path:'ui-reports/takp-skeletons-393.png',fullPage:true});
   }else assert.equal(await page.isVisible('#takp-skeleton-panel'),false,'Skeleton model option is TAKP-only');
   assert.deepEqual(errors,[]);await page.close();
  }
  console.log('PASS: all-profile reviewed source updates, explicit fresh-cache fallback, retained legacy startup, staged deployment and reversible TAKP skeleton controls');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exit(1);});
