const {chromium}=require('playwright');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert');
const root=path.resolve('app/src/main/assets/ui');
const server=http.createServer((req,res)=>{
 const name=req.url==='/'?'index.html':req.url.slice(1);
 if(!/^[\w.-]+$/.test(name)){res.writeHead(404);res.end();return;}
 try{const types={js:'text/javascript',css:'text/css',svg:'image/svg+xml',webp:'image/webp',ttf:'font/ttf',html:'text/html'};res.setHeader('Content-Type',types[name.split('.').pop()]||'application/octet-stream');res.end(fs.readFileSync(path.join(root,name)));}catch{res.writeHead(404);res.end();}
});
const key='trasc.launcher.theme';
const scenes=['setup','server','gameplay','build','spire','fixes','database','client','files','logs'];
function contrast(a,b){const l=c=>c.slice(0,3).map(x=>x/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4).reduce((s,x,i)=>s+x*[.2126,.7152,.0722][i],0),x=l(a),y=l(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
   window.fixture={profile:localStorage.profile||'custom',calls:[],jobs:[]};
   window.Trasc={call(id,op,input){setTimeout(()=>{
    const f=fixture,a=JSON.parse(input);f.calls.push({op,a});let result={};
    if(op==='native_state')result={profile:f.profile,installed:true,alive:false,status:'Runtime stopped',free_bytes:50e9};
    else if(op==='client_native_state')result={profile:f.profile,installed:true,alive:false,busy:false,status:'Stopped',launch_options:{resolution:'1280x720',native_d3dx:true}};
    else if(op==='profile_switch'){localStorage.profile=a.profile;f.profile=a.profile;result={profile:f.profile};}
    else if(op==='controller_state')result={sources:[],actions:[],layers:[{name:'Main',bindings:{}}],deadzone:.2,sensitivity:700};
    else if(op==='native_files'||op==='files')result={path:'.',items:[],total:0,offset:0,next_offset:null};
    else if(op==='logs')result={text:'Theme fixture log',names:['control.log']};
    else if(op==='log_retention')result={count:5};
    else if(op==='state')result={profile:f.profile,running:false,settings:{ip:'127.0.0.1',login_port:5999,repo:'https://github.com/Russianranger/Server',ref:'main',workers:3,jobs:1},processes:{},jobs:f.jobs,client:{imported:true},traditional:{components:{},build:{},deployment:{}},free_bytes:50e9};
    else{result={id:String(f.jobs.length+1),operation:op,status:'done',result:op==='spire_catalog'?{entities:[]}:{}};f.jobs.push(result);}
    window.nativeReply(id,{ok:true,result});
   },5);}};
  });
  const url=`http://127.0.0.1:${server.address().port}/`;
  await page.goto(url);await page.waitForFunction(()=>!document.getElementById('world-profile').disabled);
  assert.equal(await page.getAttribute('body','data-launcher-theme'),'default');
  const appearance=()=>page.evaluate(()=>['body','.card','nav','.runtime-toolbar','.overview','input','button'].map(selector=>{const s=getComputedStyle(document.querySelector(selector));return [selector,s.color,s.background,s.borderColor,s.borderRadius,s.fontFamily];}));
  const original=await appearance();
  await page.evaluate(()=>localStorage.setItem('unrelated.preference','keep me'));
  const before=await page.evaluate(()=>({calls:fixture.calls.length,resolution:document.getElementById('client-resolution').value,d3dx:document.getElementById('client-native-models').checked}));
  await page.selectOption('#launcher-theme','necromancer');
  const after=await page.evaluate(()=>({calls:fixture.calls.length,resolution:document.getElementById('client-resolution').value,d3dx:document.getElementById('client-native-models').checked}));
  assert.deepEqual(after,before,'Appearance does not invoke native operations or change client choices');
  assert.equal(await page.evaluate(k=>localStorage.getItem(k),key),'necromancer');
  await page.reload();await page.waitForFunction(()=>!document.getElementById('world-profile').disabled);
  assert.equal(await page.inputValue('#launcher-theme'),'necromancer');
  await page.selectOption('#world-profile','traditional');await page.click('#switch-profile');
  await page.waitForFunction(()=>document.body.dataset.profile==='traditional');
  assert.equal(await page.inputValue('#launcher-theme'),'necromancer','Theme survives real profile-switch reload');
  for(const theme of ['necromancer','monk']){
   await page.selectOption('#launcher-theme',theme);
   const colors=await page.evaluate(()=>{
    const s=getComputedStyle(document.body),canvas=document.createElement('canvas'),ctx=canvas.getContext('2d');
    const color=name=>{ctx.clearRect(0,0,1,1);ctx.fillStyle=s.getPropertyValue(name).trim();ctx.fillRect(0,0,1,1);return [...ctx.getImageData(0,0,1,1).data];};
    return Object.fromEntries(['--text','--muted','--theme-muted','--theme-card','--theme-surface','--theme-header','--theme-button','--theme-button-edge','--theme-button-text','--theme-secondary','--gold'].map(n=>[n,color(n)]));
   });
   for(const text of ['--text','--muted','--theme-muted'])for(const bg of ['--theme-card','--theme-surface','--theme-header'])assert(contrast(colors[text],colors[bg])>=4.5,`${theme}: readable ${text} on ${bg}`);
   for(const bg of ['--theme-button','--theme-button-edge'])assert(contrast(colors['--theme-button-text'],colors[bg])>=4.5,`${theme}: readable primary button`);
   assert(contrast(colors['--gold'],colors['--theme-surface'])>=3,`${theme}: visible focus color`);
   for(const scene of scenes){
    await page.locator(`nav [data-tab=${scene}]`).click();
    assert.equal(await page.getAttribute('body','data-scene'),scene);
    assert((await page.evaluate(()=>getComputedStyle(document.body).getPropertyValue('--scene-image'))).includes(`theme-${theme}.svg`),`${theme} art on ${scene}`);
   }
   await page.locator('#launcher-theme').focus();
   assert.equal(await page.locator('#launcher-theme').evaluate(e=>getComputedStyle(e).outlineWidth),'2px');
   await page.setViewportSize({width:375,height:812});
   for(const scene of scenes){
    await page.locator(`nav [data-tab=${scene}]`).click();
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${theme}: no page overflow on ${scene}`);
   }
   const geometry=await page.locator('#launcher-theme').boundingBox();assert(geometry.height>=44&&geometry.x>=0&&geometry.x+geometry.width<=375,'Phone theme control stays visible and touch-sized');
   await page.setViewportSize({width:1280,height:720});
  }
  await page.selectOption('#launcher-theme','default');
  await page.waitForFunction(()=>!document.getElementById('world-profile').disabled);
  await page.selectOption('#world-profile','custom');await page.click('#switch-profile');
  await page.waitForFunction(()=>document.body.dataset.profile==='custom');
  assert.deepEqual(await appearance(),original,'Default restores the original artwork and component appearance');
  assert.equal(await page.evaluate(()=>localStorage.getItem('unrelated.preference')),'keep me');
  await page.evaluate(k=>localStorage.setItem(k,'untrusted-value'),key);await page.reload();
  assert.equal(await page.inputValue('#launcher-theme'),'default','Unknown saved choices fall back safely');
  const blocked=await browser.newPage();
  await blocked.addInitScript(()=>Object.defineProperty(window,'localStorage',{get(){throw Error('Storage blocked');}}));
  await blocked.goto(url);await blocked.selectOption('#launcher-theme','monk');
  assert.equal(await blocked.getAttribute('body','data-launcher-theme'),'monk');
  assert((await blocked.textContent('#launcher-theme-status')).includes('this session'),'Blocked storage still allows session-only choice');
  await blocked.close();
  assert.deepEqual(errors,[]);console.log('Launcher themes: persistence, world isolation, Default restoration, all tabs, contrast and phone layout passed.');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1;});
