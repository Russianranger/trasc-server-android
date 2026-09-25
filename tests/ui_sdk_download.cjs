const {chromium}=require('playwright');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert');
const root=path.resolve('app/src/main/assets/ui');
const server=http.createServer((req,res)=>{
 const name=req.url==='/'?'index.html':req.url.slice(1);
 if(!/^[\w.-]+$/.test(name)){res.writeHead(404);res.end();return;}
 try{res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.webp')?'image/webp':name.endsWith('.ttf')?'font/ttf':'text/html');res.end(fs.readFileSync(path.join(root,name)));}
 catch{res.writeHead(404);res.end();}
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:393,height:852}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
   window.fixture={runtime:true,server:false,client:false,compiler:false,jobs:[],calls:[],infoError:'',offline:false};
   window.Trasc={call(id,op,input){setTimeout(()=>{
    const f=fixture,a=JSON.parse(input);f.calls.push({op,a});let result={};
    try{
     if(op==='native_state')result={profile:'custom',installed:true,alive:f.runtime,status:'Runtime ready',free_bytes:50e9};
     else if(op==='client_native_state')result={installed:true,alive:f.client,busy:false,status:'Stopped'};
     else if(op==='state')result={running:f.server,settings:{ip:'127.0.0.1',login_port:5999,repo:'fixture',ref:'main',workers:3,jobs:2},processes:{},jobs:f.jobs,binaries_ready:true,database_imported:true,maps_ready:true,client:{imported:true,files:3,bytes:123},free_bytes:50e9};
     else if(op==='controller_state')result={sources:[],actions:[],layers:[{name:'Main',bindings:{}}],deadzone:.2,sensitivity:700};
     else if(op==='client_dll_status')result={compiler:f.compiler,sdk:f.compiler,runtime:true,build:null};
     else if(op==='client_dll_download_info'){
      if(f.infoError)throw Error(f.infoError);
      result={token:'catalog-license-token',license_url:'https://visualstudio.microsoft.com/license-terms/vs2022-cruntime/',license_name:'Microsoft Visual Studio license',toolset:'v142 14.29',sdk:'10.0.19041.0',download_bytes:750e6,installed_bytes:1e9,required_free_bytes:8e9,free_bytes:50e9,needs_msitools:true,message:'Review the license before continuing.'};
     }else if(op==='client_dll_download'){
      if(!a.accepted||a.token!=='catalog-license-token')throw Error('License acceptance required.');
      const j={id:String(f.jobs.length+1),operation:op,status:'running',progress:{phase:'download',message:'Downloading compiler packages · 100 MB of 750 MB',downloaded_bytes:100e6,total_bytes:750e6}};f.jobs.push(j);result=j;
     }else if(op==='cancel'){
      const j=f.jobs.find(j=>j.status==='running');if(j){j.status='error';j.error='Operation cancelled. Existing compiler retained.';}
     }else if(op==='pick'){f.offline=true;result={file:'sdk.zip'};}
     else if(op==='client_dll_sdk'){f.compiler=true;const j={id:String(f.jobs.length+1),operation:op,status:'done',result:{message:'Offline toolchain imported'}};f.jobs.push(j);result=j;}
     else if(op==='logs')result={text:'Toolchain log',names:['control.log']};
     else if(op==='log_retention')result={count:5};
     window.nativeReply(id,{ok:true,result});
    }catch(e){window.nativeReply(id,{ok:false,error:e.message});}
   },5);}};
  });
  const idle=()=>page.waitForFunction(()=>!busy&&!polling);
  const downloadCount=()=>page.evaluate(()=>fixture.calls.filter(x=>x.op==='client_dll_download').length);
  const openConsent=async()=>{await page.click('#dll-sdk-download');await page.waitForFunction(()=>!document.getElementById('dll-sdk-consent').hidden&&!busy);};
  const finish=async(status,error)=>page.evaluate(({status,error})=>{const j=fixture.jobs.find(j=>j.status==='running');j.status=status;if(status==='done'){fixture.compiler=true;j.result={message:'Microsoft toolchain ready. Compile dinput8.dll when ready.'};}else j.error=error;},{status,error});
  await page.goto(`http://127.0.0.1:${server.address().port}/`);await idle();
  await page.click('nav [data-tab=client]');await page.click('#dll-panel > summary');await page.waitForFunction(()=>dllCompilerState!==null);await idle();
  assert.equal(await downloadCount(),0,'Opening Client/status must never start a download');
  assert(await page.isDisabled('#dll-build'),'Compiler is unavailable before preparation');
  await openConsent();
  assert(!(await page.isChecked('#dll-sdk-accept')));assert(await page.isDisabled('#dll-sdk-confirm'));
  assert.equal(await downloadCount(),0,'Catalog/license review does not download compiler packages');
  await page.click('#dll-sdk-cancel');assert(!(await page.isVisible('#dll-sdk-consent')));
  assert.equal(await downloadCount(),0,'Cancel before acceptance does not enqueue a download');
  await openConsent();await page.click('#dll-sdk-license');await idle();
  assert.equal(await page.evaluate(()=>fixture.calls.find(x=>x.op==='client_dll_license').a.url),'https://visualstudio.microsoft.com/license-terms/vs2022-cruntime/');
  assert.equal(await downloadCount(),0,'Reading the license does not accept it');
  assert(await page.isDisabled('#dll-sdk-confirm'));
  fs.mkdirSync('ui-reports',{recursive:true});
  for(const viewport of [{width:393,height:852},{width:1280,height:720}]){
   await page.setViewportSize(viewport);await page.locator('#dll-sdk-consent').scrollIntoViewIfNeeded();
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Consent has no horizontal overflow');
   await page.screenshot({path:`ui-reports/sdk-license-${viewport.width}.png`,fullPage:true});
  }
  await page.check('#dll-sdk-accept');await page.click('#dll-sdk-confirm');
  await page.waitForFunction(()=>document.getElementById('dll-sdk-progress').textContent.includes('100 MB'));
  assert.equal(await downloadCount(),1);
  const request=await page.evaluate(()=>fixture.calls.find(x=>x.op==='client_dll_download'));
  assert.deepEqual(request.a,{accepted:true,token:'catalog-license-token',__profile:'custom'});
  assert(!(await page.isChecked('#dll-sdk-accept')),'Consent is consumed and cleared after submission');
  for(const id of ['dll-sdk-download','dll-sdk','dll-build','dll-deploy','client-launch','client-desktop','client-runtime-online','client-runtime-offline','start-server','runtime-close','session-import','session-export','switch-profile'])assert(await page.isDisabled('#'+id),`${id} must be blocked during installation`);
  assert.equal(await page.getAttribute('#dll-sdk-progress-bar','max'),'750000000');
  assert.equal(await page.getAttribute('#dll-sdk-progress-bar','value'),'100000000');
  assert((await page.textContent('#activity-detail')).includes('100 MB'));
  await page.click('#cancel');await page.waitForFunction(()=>!busy&&document.getElementById('dll-sdk-progress').textContent.includes('cancelled'));
  await idle();assert(!(await page.isDisabled('#dll-sdk-download')));
  await openConsent();assert(!(await page.isChecked('#dll-sdk-accept')),'A retry requires fresh acceptance');
  await page.check('#dll-sdk-accept');await page.click('#dll-sdk-confirm');
  await page.waitForFunction(()=>fixture.jobs.some(j=>j.status==='running'));
  await finish('error','Package checksum mismatch. Existing compiler retained.');
  await page.waitForFunction(()=>!busy&&document.getElementById('dll-sdk-progress').textContent.includes('checksum mismatch'));
  assert(await page.isDisabled('#dll-build'));
  await openConsent();await page.check('#dll-sdk-accept');await page.click('#dll-sdk-confirm');
  await page.waitForFunction(()=>fixture.jobs.some(j=>j.status==='running'));
  await page.evaluate(()=>{const j=fixture.jobs.find(j=>j.status==='running');j.progress={phase:'extract',message:'Extracting Windows SDK'};});
  await page.waitForFunction(()=>document.getElementById('dll-sdk-progress').textContent.includes('Extracting'));
  assert.equal(await page.getAttribute('#dll-sdk-progress-bar','value'),null,'Extraction has indeterminate progress');
  await finish('done');await page.waitForFunction(()=>!document.getElementById('dll-build').disabled);
  assert((await page.textContent('#dll-state')).includes('SDK imported'));assert(!(await page.isVisible('#dll-sdk-progress-bar')));
  assert.equal(await page.evaluate(()=>fixture.calls.filter(x=>['client_start','client_dll_deploy'].includes(x.op)).length),0,'Successful installation never compiles or deploys automatically');
  const before=await downloadCount();await page.click('#dll-status');await idle();assert.equal(await downloadCount(),before,'Checking an existing SDK never downloads it again');
  await page.click('#dll-sdk');await page.waitForFunction(()=>fixture.offline&&!busy);assert.equal(await downloadCount(),before,'Offline ZIP import remains separate');
  // An operation found by polling after the management page reopens must also lock controls.
  await page.evaluate(()=>{fixture.jobs.push({id:'restored',operation:'client_dll_download',status:'running',progress:{message:'Verifying cached packages'}});poll();});
  await page.waitForFunction(()=>document.getElementById('dll-sdk-progress').textContent.includes('cached packages'));
  assert(await page.isDisabled('#client-launch'));assert(await page.isDisabled('#dll-sdk'));assert(await page.isDisabled('#session-export'));
  await finish('error','Retry stopped. Existing compiler retained.');await page.evaluate(()=>poll());
  await page.waitForFunction(()=>!document.getElementById('dll-build').disabled);
  await page.evaluate(()=>fixture.infoError='Could not reach Microsoft. Import a prepared ZIP or retry.');
  await page.click('#dll-sdk-download');await page.waitForFunction(()=>!busy&&document.getElementById('dll-sdk-progress').textContent.includes('Could not reach'));
  assert(!(await page.isVisible('#dll-sdk-consent')));assert.equal(await downloadCount(),before);
  assert.deepEqual(errors,[]);console.log('PASS: SDK explicit license consent, cancel/retry, progress and conflicts, failure preservation, compiler-ready refresh, offline import and reopened job gating');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1;});
