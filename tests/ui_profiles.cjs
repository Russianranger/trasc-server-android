const {chromium}=require('playwright');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert');
const root=path.resolve('app/src/main/assets/ui');
const server=http.createServer((req,res)=>{const name=req.url==='/'?'index.html':req.url.slice(1);if(!/^[\w.-]+$/.test(name)){res.writeHead(404);res.end();return;}try{res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.webp')?'image/webp':'text/html');res.end(fs.readFileSync(path.join(root,name)));}catch{res.writeHead(404);res.end();}});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
   window.fixture={profile:localStorage.profile||'custom',alive:false,client:false,components:{},jobs:[],calls:[]};
   window.Trasc={call(id,op,input){setTimeout(()=>{const f=fixture,a=JSON.parse(input);let result={};f.calls.push({op,a});try{
    if(op!=='native_state'&&a.__profile&&a.__profile!==f.profile)throw Error('World profile changed');
    if(op==='native_state')result={profile:f.profile,installed:true,alive:f.alive,status:'Runtime stopped',free_bytes:50e9};
    else if(op==='profile_switch'){if(f.alive||f.client)throw Error('Stop runtime and client');localStorage.profile=a.profile;f.profile=a.profile;result={profile:f.profile};}
    else if(op==='runtime_start')f.alive=true;
    else if(op==='runtime_stop')f.alive=false;
    else if(op==='client_native_state')result={installed:true,alive:f.client,busy:false,status:'Stopped',launch_options:{native_dinput8:true,fast_spell_parse:true}};
    else if(op==='state')result={profile:f.profile,running:false,settings:{ip:'127.0.0.1',login_port:5999,repo:f.profile==='custom'?'https://github.com/Russianranger/Triptych-Triumvirate':'https://github.com/EQEmu/EQEmu',ref:f.profile==='custom'?'main':'master',workers:3,jobs:2},processes:{},jobs:f.jobs,source:{commit:'abc'},maps_ready:true,database_imported:true,binaries_ready:true,client:{imported:false},traditional:{components:f.components},free_bytes:50e9};
    else if(op==='controller_state')result={sources:[],actions:[],layers:[{name:'Main',bindings:{}}],deadzone:.2,sensitivity:700};
    else if(op==='files')result={path:'.',items:[],total:0,offset:0,next_offset:null};
    else if(op==='logs')result={text:'Profile log',names:['control.log']};
    else if(op==='log_retention')result={count:5};
    else if(op==='controller_capture')result={};
    else if(op==='pick')result={file:'content.zip'};
    else {
     let value={};if(op==='spire_catalog')value={entities:[]};
     if(op==='import_content'){f.components[a.kind]={imported:true,source:{files:5,commit:'1234567890abcdef'}};value={message:'Component imported',backup:a.replace?'backups/content/previous':null};}
     result={id:String(f.jobs.length+1),operation:op,status:'done',result:value};f.jobs.push(result);
    }
    window.nativeReply(id,{ok:true,result});
   }catch(e){window.nativeReply(id,{ok:false,error:e.message});}},5);}};
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  await page.waitForFunction(()=>document.getElementById('world-profile').disabled===false);
  await page.selectOption('#world-profile','traditional');await page.click('#switch-profile');
  await page.waitForFunction(()=>document.body.dataset.profile==='traditional');
  assert.equal(await page.inputValue('#source-url'),'https://github.com/EQEmu/EQEmu');
  assert.equal(await page.isChecked('#client-native-dll'),false);
  assert.equal(await page.isChecked('#client-fast-spells'),false);
  await page.click('#runtime-open');await page.waitForFunction(()=>lastNative?.alive);
  assert(await page.isDisabled('#world-profile'));
  assert(await page.isDisabled('#start-server'));assert(await page.isDisabled('#build-server'));
  await page.selectOption('#content-kind','plugins');await page.check('#replace-content');await page.click('#content-zip');
  await page.waitForFunction(()=>document.getElementById('content-result').textContent.includes('backups/content'));
  const request=await page.evaluate(()=>fixture.calls.find(x=>x.op==='import_content'));
  assert.equal(request.a.__profile,'traditional');assert.equal(request.a.kind,'plugins');assert.equal(request.a.replace,true);
  fs.mkdirSync('ui-reports',{recursive:true});const scenes=new Set();
  for(const viewport of [{width:1280,height:720},{width:393,height:852}]){
   await page.setViewportSize(viewport);
   for(const tab of ['setup','server','gameplay','build','spire','fixes','database','client','files','logs']){
    await page.locator(`nav [data-tab=${tab}]`).click();await page.evaluate(()=>scrollTo(0,0));
    const art=await page.evaluate(()=>getComputedStyle(document.body).getPropertyValue('--scene-image'));scenes.add(art);
    const filename=art.match(/classic-[a-z]+\.webp/)[0];assert(fs.existsSync(path.join(root,filename)));
    assert(await page.locator(`#${tab}`).isVisible());
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'horizontal overflow');
    if(['setup','client','fixes'].includes(tab))await page.screenshot({path:`ui-reports/profiles-${tab}-${viewport.width}.png`,fullPage:true});
   }
  }
  assert.equal(scenes.size,10);assert.equal(await page.locator('nav button').count(),10);
  await page.locator('nav [data-tab=fixes]').click();assert(await page.locator('#prefix-fix-panel').isVisible());assert(!(await page.locator('#ferry-service-panel').isVisible()));
  await page.click('#runtime-close');await page.waitForFunction(()=>!lastNative?.alive);
  await page.evaluate(()=>{fixture.client=true;poll();});await page.waitForFunction(()=>lastClientNative?.alive);assert(await page.isDisabled('#world-profile'));
  await page.evaluate(()=>{fixture.client=false;poll();});await page.waitForFunction(()=>!document.getElementById('world-profile').disabled);
  await page.selectOption('#world-profile','custom');await page.click('#switch-profile');await page.waitForFunction(()=>document.body.dataset.profile==='custom'&&activeProfile==='custom');
  assert.equal(await page.inputValue('#source-url'),'https://github.com/Russianranger/Triptych-Triumvirate');
  assert.equal(await page.inputValue('#source-ref'),'main');
  await page.locator('nav [data-tab=fixes]').click();assert(await page.locator('#ferry-service-panel').isVisible());
  assert.equal(await page.locator('nav button').count(),10);assert.deepEqual(errors,[]);
  console.log('PASS: profile switch persistence, active-process gating, shared tabs, 10 classic scenes, clean DLL controls, scoped component import and return to Custom');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
