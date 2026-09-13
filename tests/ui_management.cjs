const {chromium}=require('playwright');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert');
const root=path.resolve('app/src/main/assets/ui');
const server=http.createServer((req,res)=>{
 const name=req.url==='/'?'index.html':req.url.slice(1);
 if(!/^[\w.-]+$/.test(name)){res.writeHead(404);res.end();return;}
 try{res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(path.join(root,name)));}catch{res.writeHead(404);res.end();}
});
const fixture={values:{},metadata:{}};
for(let i=0;i<1100;i++){const name='Category'+(i%47)+':Rule'+i;fixture.metadata[name]={type:'int',min:'-2147483648',max:'2147483647',max_length:128,description:'A test rule '+i};fixture.values[name]={value:String(i),ruleset:1};}
for(const [name,type,value,min,max]of [['Character:RaidExpMultiplier','real','0.3','0','1'],['Character:FinalRaidExpMultiplier','real','0.0000000000001','0','3.4e38'],['Zone:StateSavingOnShutdown','bool','true'],['World:MaxClientsPerIP','int','-1','-2147483648','2147483647'],['Custom:Greeting','string','hello']]){
 fixture.metadata[name]={type,min,max,max_length:65535,description:'Description for '+name};fixture.values[name]={value,ruleset:1};
}
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:412,height:915}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(data=>{
   let seq=0,jobs=[];const actions=['None','MouseLeft','MouseRight','PointerUp','PointerDown','PointerLeft','PointerRight','KeyW','KeyT','Space','Escape'];
   let profile={sources:['A','B','RightUp','RightDown','RightLeft','RightRight'],actions,bindings:{A:'Space',B:'Escape',RightUp:'PointerUp',RightDown:'PointerDown',RightLeft:'PointerLeft',RightRight:'PointerRight'},deadzone:.2,sensitivity:700};
   window.__saves=[];
   const state=()=>({version:'0.2.0',running:false,settings:{ip:'127.0.0.1',login_port:5999,repo:'https://github.com/Russianranger/Triptych-Triumvirate',ref:'main',workers:3,jobs:2},source:{commit:'test'},maps_ready:true,database_imported:true,binaries_ready:true,processes:{},jobs,free_bytes:50e9,nektulos:{legacy_ready:true},client:{imported:false}});
   window.Trasc={call(id,op,input){setTimeout(()=>{
    const args=JSON.parse(input);let result;
    if(op==='native_state')result={installed:true,alive:true,status:'Runtime ready',free_bytes:50e9};
    else if(op==='state')result=state();
    else if(op==='controller_state')result=profile;
    else if(op==='controller_save'){profile={...profile,...args};result=profile;}
    else if(op==='controller_capture'){window.clientInputEvent?.({type:'capture',down:args.active});result={...profile,active:args.active};}
    else{
     let completed={};if(op==='gameplay')completed={...data,rulesets:[{id:1,name:'default'}],selected:1,active_name:'default'};
     else if(op==='save_gameplay'){window.__saves.push(args);for(const [name,value]of Object.entries(args.values))data.values[name]={value,ruleset:1};}
     const job={id:String(++seq),operation:op,status:'done',result:completed};jobs=[job];result=job;
    }
    window.nativeReply(id,{ok:true,result});
   },5);}};
  },fixture);
  await page.goto('http://127.0.0.1:'+server.address().port);
  await page.locator('nav [data-tab=gameplay]').click();await page.locator('#load-rules').click();
  await page.waitForFunction(()=>document.getElementById('rules-count').textContent.includes('1105'));
  assert.equal(await page.locator('.rule-category[open]').count(),0,'Categories start collapsed');
  await page.locator('#rule-search').fill('FinalRaid');await page.locator('#rule-Character-FinalRaidExpMultiplier').waitFor();
  assert.equal(await page.locator('#rule-Character-FinalRaidExpMultiplier').inputValue(),'0.0000000000001');
  await page.locator('#rule-search').fill('RaidExp');await page.locator('#rule-Character-RaidExpMultiplier').fill('1.1');await page.locator('#save-rules').click();
  await page.waitForFunction(()=>document.getElementById('rules-errors').textContent.includes('above the maximum 1'));
  assert.equal(await page.evaluate(()=>window.__saves.length),0,'Invalid rules must not reach save API');
  assert.equal(await page.locator('#rule-Character-RaidExpMultiplier').getAttribute('aria-invalid'),'true');
  fs.mkdirSync('ui-reports',{recursive:true});await page.screenshot({path:'ui-reports/rules-mobile.png',fullPage:true});
  await page.locator('#rule-Character-RaidExpMultiplier').fill('0.4');await page.locator('#save-rules').click();
  await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('Settings saved. Restart'));
  assert.deepEqual(await page.evaluate(()=>window.__saves[0].values),{'Character:RaidExpMultiplier':'0.4'},'Only edited values saved');
  await page.locator('#rule-search').fill('MaxClientsPerIP');assert.equal(await page.locator('#rule-World-MaxClientsPerIP').inputValue(),'-1');
  await page.locator('nav [data-tab=client]').click();await page.locator('#binding-A').selectOption('KeyT');await page.locator('#controller-save').click();
  await page.waitForFunction(()=>document.getElementById('notice').textContent==='Controller bindings saved.');
  await page.locator('#controller-capture').click();await page.waitForFunction(()=>document.getElementById('controller-focus').textContent.includes('captured'));
  await page.evaluate(()=>{window.clientInputEvent({type:'button',action:'KeyT',down:true});window.clientInputEvent({type:'pointer',x:90,y:20});});
  assert((await page.locator('#client-input-status').textContent()).includes('KeyT'));
  await page.screenshot({path:'ui-reports/client-mobile.png',fullPage:true});
  await page.locator('nav [data-tab=setup]').click();await page.waitForFunction(()=>document.getElementById('controller-focus').textContent==='Controller capture is off.');
  assert(!(await page.locator('#client-input-status').textContent()).includes('KeyT'),'Leaving tab releases input');
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'No horizontal page overflow on mobile');
  await page.setViewportSize({width:960,height:540});await page.screenshot({path:'ui-reports/setup-landscape.png',fullPage:true});
  assert.deepEqual(errors,[],'UI JavaScript errors');console.log('PASS: large categorized rule UI, bounds errors, dirty-only saves, sentinel/tiny values, client bindings and capture lifecycle');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1;});
