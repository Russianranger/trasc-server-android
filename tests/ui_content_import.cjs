const {chromium}=require('playwright');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert');
const root=path.resolve('app/src/main/assets/ui');
const server=http.createServer((req,res)=>{
 const name=req.url==='/'?'index.html':req.url.slice(1);
 if(!/^[\w.-]+$/.test(name)){res.writeHead(404);res.end();return;}
 try{res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.webp')?'image/webp':'text/html');res.end(fs.readFileSync(path.join(root,name)));}catch{res.writeHead(404);res.end();}
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:393,height:852}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
   window.fixture={profile:localStorage.world||'traditional',alive:true,client:false,clientBusy:false,clientImported:true,server:false,jobs:[],calls:[],upload:'1790000-component.zip',uploadName:'MySkin.zip',components:{},skins:JSON.parse(localStorage.skins||'{"traditional":[],"custom":[]}'),failUi:false};
   window.Trasc={call(id,op,input){setTimeout(()=>{
    const f=fixture,a=JSON.parse(input);f.calls.push({op,a});let result={};
    try{
     if(op!=='native_state'&&a.__profile&&a.__profile!==f.profile)throw Error('World profile changed');
     if(op==='native_state')result={profile:f.profile,installed:true,alive:f.alive,status:'Runtime ready',free_bytes:50e9};
     else if(op==='client_native_state')result={installed:true,alive:f.client,busy:f.clientBusy,status:'Stopped'};
     else if(op==='state')result={profile:f.profile,running:f.server,settings:{ip:'127.0.0.1',login_port:5999,repo:'fixture',ref:'main',workers:3,jobs:1},jobs:f.jobs,processes:{},source:{},maps_ready:true,database_imported:true,client:{imported:f.clientImported,ui:{imported:!!f.skins[f.profile].length,skins:f.skins[f.profile],message:f.skins[f.profile].length?'UI skins imported. Select one in game.':''}},traditional:{components:f.components,build:{runtime_ready:true,source_supported:true,build_allowed:true}},free_bytes:50e9};
     else if(op==='profile_switch'){if(f.alive||f.client)throw Error('Stop runtime and client');localStorage.world=a.profile;f.profile=a.profile;result={profile:f.profile};}
     else if(op==='runtime_start')f.alive=true;
     else if(op==='runtime_stop')f.alive=false;
     else if(op==='controller_state')result={sources:[],actions:[],layers:[{name:'Main',bindings:{}}],deadzone:.2,sensitivity:700};
     else if(op==='controller_capture')result={};
     else if(op==='files'||op==='native_files')result={path:'.',items:[],total:0,offset:0,next_offset:null};
     else if(op==='logs')result={text:'Profile log',names:['operation.log']};
     else if(op==='log_retention')result={count:5};
     else if(op==='pick')result={file:f.upload,path:'incoming/'+f.upload,name:f.uploadName};
     else {
      let value={};
      if(op==='import_content'){
       if(f.components[a.kind]?.imported&&!a.replace)throw Error('Select Replace this component to preserve a backup and replace its directory');
       f.components[a.kind]={imported:true,source:{files:7,commit:'1234567890abcdef'}};
       value={message:'Component imported',backup:a.replace?'backups/content/'+a.kind+'-previous':null};
      }
      if(op==='import_client_ui'){
       if(f.failUi){f.failUi=false;throw Error('UI ZIP contains unsafe archive paths');}
       if(f.client||f.clientBusy)throw Error('Stop the embedded client before importing UI skins');
       const name=a.name||'MySkin';
       if(f.skins[f.profile].some(s=>s.name===name)&&!a.replace)throw Error('Select Replace matching skins before replacing an installed UI');
       f.skins[f.profile]=[{name,files:4,bytes:1000,backup:a.replace?'backups/client-ui/'+name+'-previous':null}];localStorage.skins=JSON.stringify(f.skins);
       value={message:'UI skin imported',activation_hint:'/loadskin '+name+' 1'};
      }
      result={id:String(f.jobs.length+1),operation:op,status:'done',result:value};f.jobs.push(result);
     }
     window.nativeReply(id,{ok:true,result});
    }catch(e){window.nativeReply(id,{ok:false,error:e.message});}
   },5);}};
  });
  await page.goto('http://127.0.0.1:'+server.address().port+'/');
  await page.waitForFunction(()=>activeProfile==='traditional'&&!polling&&lastClientNative);
  // poll() deliberately skips overlapping requests. Wait for the current refresh
  // before changing native fixture state, then await a complete new refresh.
  const updateFixture=changes=>page.evaluate(async changes=>{while(polling)await new Promise(r=>setTimeout(r,10));Object.assign(fixture,changes);await poll();},changes);
  const quests='https://github.com/ProjectEQ/projecteqquests',assets='https://github.com/EQEmu/EQEmu',revision='4aceae18b94ffaafc08e2b17bc41cd72c77f795d';
  assert.equal(await page.inputValue('#plugins-url'),quests);
  assert.equal(await page.inputValue('#lua-modules-url'),quests);
  assert.equal(await page.inputValue('#assets-url'),assets);
  assert.equal(await page.inputValue('#plugins-ref'),'');assert.equal(await page.inputValue('#lua-modules-ref'),'');
  assert.equal(await page.inputValue('#assets-ref'),revision);
  assert(await page.locator('#plugins-import-panel').isVisible());assert(await page.locator('#lua-modules-import-panel').isVisible());assert(await page.locator('#assets-import-panel').isVisible());
  assert(!(await page.locator('#content-kind').isVisible()),'Advanced compatibility selector starts collapsed');
  await page.fill('#plugins-url','https://github.com/example/my-plugins');await page.fill('#plugins-ref','my-quest-revision');
  await updateFixture({});
  assert.equal(await page.inputValue('#plugins-url'),'https://github.com/example/my-plugins');assert.equal(await page.inputValue('#plugins-ref'),'my-quest-revision','Polling must preserve edited repositories/revisions');
  await page.fill('#plugins-url',quests);await page.fill('#plugins-ref','');
  for(const [id,kind,url,ref]of [['plugins','plugins',quests,''],['lua-modules','lua_modules',quests,''],['assets','assets',assets,revision]]){
   await page.click('#'+id+'-git');await page.waitForFunction(()=>busy===0);
   const call=await page.evaluate(kind=>fixture.calls.find(c=>c.op==='import_content'&&c.a.kind===kind),kind);
   assert.deepEqual(call.a,{kind,url,ref,replace:false,__profile:'traditional'});
   assert((await page.textContent('#'+id+'-result')).includes('7 files'));
  }
  // Replacements require the existing backup guard; separate ZIP controls use the native basename.
  await page.click('#plugins-git');await page.waitForFunction(()=>busy===0);
  assert((await page.textContent('#notice')).includes('Select Replace this component'));
  await page.check('#plugins-replace');await page.click('#plugins-zip');await page.waitForFunction(()=>busy===0);
  const zipCall=await page.evaluate(()=>fixture.calls.filter(c=>c.op==='import_content'&&c.a.file).at(-1));
  assert.deepEqual(zipCall.a,{kind:'plugins',file:'1790000-component.zip',replace:true,__profile:'traditional'});
  assert.equal(await page.isChecked('#plugins-replace'),false);
  assert((await page.textContent('#plugins-result')).includes('backups/content/plugins-previous'));
  for(const [setting,value]of [['server',true],['alive',false]]){
   await updateFixture({[setting]:value});
   for(const id of ['plugins','lua-modules','assets'])for(const action of ['git','zip'])assert(await page.isDisabled('#'+id+'-'+action));
   await updateFixture({[setting]:setting==='alive'});
  }
  fs.mkdirSync('ui-reports',{recursive:true});await page.locator('#plugins-import-panel').scrollIntoViewIfNeeded();
  await page.screenshot({path:'ui-reports/content-import-mobile.png',fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Support import cards fit mobile');
  await page.locator('nav [data-tab=client]').click();
  assert(await page.locator('#client-ui-panel').isVisible());assert(!(await page.isDisabled('#client-ui-import')));
  await page.fill('#client-ui-name','ClassicUI');await updateFixture({});assert.equal(await page.inputValue('#client-ui-name'),'ClassicUI');
  await page.click('#client-ui-import');await page.waitForFunction(()=>busy===0);
  const uiCall=await page.evaluate(()=>fixture.calls.find(c=>c.op==='import_client_ui'));
  assert.deepEqual(uiCall.a,{file:'incoming/1790000-component.zip',replace:false,name:'ClassicUI',archive_name:'MySkin.zip',__profile:'traditional'});
  assert((await page.textContent('#client-ui-skins')).includes('/loadskin ClassicUI 1'));
  await page.click('#client-ui-import');await page.waitForFunction(()=>busy===0);
  assert((await page.textContent('#notice')).includes('Replace matching skins'));
  await page.check('#client-ui-replace');await page.click('#client-ui-import');await page.waitForFunction(()=>busy===0);
  assert.equal(await page.isChecked('#client-ui-replace'),false);assert((await page.textContent('#client-ui-skins')).includes('backups/client-ui'));
  for(const [key,value]of [['client',true],['clientBusy',true],['clientImported',false],['alive',false]]){
   await updateFixture({[key]:value});assert(await page.isDisabled('#client-ui-import'),'UI ZIP import must be disabled when '+key+' = '+value);
   await updateFixture({[key]:['clientImported','alive'].includes(key)});
  }
  await page.evaluate(()=>{fixture.failUi=true;});await page.click('#client-ui-import');await page.waitForFunction(()=>busy===0);
  assert((await page.textContent('#notice')).includes('unsafe archive paths'),'Backend validation errors reach user');
  await page.evaluate(async()=>{while(polling)await new Promise(r=>setTimeout(r,10));fixture.skins.traditional.push({name:'Stone UI',files:2},{name:'Default',protected:true});await poll();});
  const skinList=await page.textContent('#client-ui-skins');assert(skinList.includes('Select this skin in the game’s UI menu.'));assert(!skinList.includes('/loadskin Stone UI 1'));assert(!skinList.includes('undefined'));
  await page.locator('#client-ui-panel').scrollIntoViewIfNeeded();await page.screenshot({path:'ui-reports/ui-skin-traditional-mobile.png',fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'UI skins fit mobile');
  // Switch through the real UI after closing the runtime: Custom starts with an independent skin list.
  await page.click('#runtime-close');await page.waitForFunction(()=>!lastNative?.alive&&!polling);
  await page.selectOption('#world-profile','custom');await page.click('#switch-profile');await page.waitForFunction(()=>activeProfile==='custom'&&!polling);
  await page.locator('nav [data-tab=client]').click();
  assert(await page.locator('#client-ui-panel').isVisible());assert.equal(await page.locator('#client-ui-skins li').count(),0);
  assert(!(await page.locator('#plugins-import-panel').isVisible()));
  await page.fill('#client-ui-name','CustomUI');await page.click('#client-ui-import');await page.waitForFunction(()=>busy===0);
  assert((await page.textContent('#client-ui-skins')).includes('/loadskin CustomUI 1'));
  const customCall=await page.evaluate(()=>fixture.calls.filter(c=>c.op==='import_client_ui').at(-1));assert.equal(customCall.a.__profile,'custom');
  assert.deepEqual(await page.evaluate(()=>fixture.skins.traditional.map(s=>s.name)),['ClassicUI'],'Custom skin imports leave Traditional skin metadata intact');
  assert(await page.evaluate(()=>fixture.calls.filter(c=>c.op==='state').every(c=>c.a.__profile==='custom')));
  await page.setViewportSize({width:1280,height:720});await page.locator('#client-ui-panel').scrollIntoViewIfNeeded();
  await page.screenshot({path:'ui-reports/ui-skin-custom-thor.png',fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'UI skins fit Thor landscape');
  assert.deepEqual(errors,[],'UI JavaScript errors');
  console.log('PASS: separate plugin/Lua/asset default downloads and ZIP imports, replacement backups, preserved edits, runtime guards, independent Traditional/Custom UI skin actions and mobile layouts');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
