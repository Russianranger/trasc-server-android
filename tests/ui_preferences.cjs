// Check reparenting keeps original controls/listeners/values, hidden profile tools
// stay hidden, and global search navigates without performing the selected action.
const {chromium}=require('playwright');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert');
const root=path.resolve('app/src/main/assets/ui');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'');
const server=http.createServer((req,res)=>{
 const name=req.url==='/'?'index.html':req.url.slice(1);if(!/^[\w.-]+$/.test(name)){res.writeHead(404);res.end();return;}
 try{res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html');res.end(name==='index.html'?html:fs.readFileSync(path.join(root,name)));}catch{res.writeHead(404);res.end();}
});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  await page.evaluate(()=>{
   document.body.dataset.profile='custom';document.querySelectorAll('.tab').forEach(el=>el.classList.toggle('active',el.id==='client'));
   window.snapshot=()=>Array.from(document.querySelectorAll('input[id],select[id]')).filter(el=>!el.id.startsWith('preferences-')).map(el=>[el.id,el.value,el.checked,el.disabled]).sort((a,b)=>a[0].localeCompare(b[0]));
   window.before=snapshot();window.originalNodes=[...document.querySelectorAll('input[id],select[id]')];
   window.listenerCount=0;document.getElementById('client-audio').addEventListener('change',()=>listenerCount++);
   for(const id of ['client-native-dll','client-fast-spells','client-load-pauses'])document.getElementById(id).closest('label').dataset.customOnly='';
   for(const id of ['client-boats','client-particles'])document.getElementById(id).closest('.option-field').dataset.customOnly='';
   window.navigation=[];window.navigateToControl=id=>{
    navigation.push(id);const el=document.getElementById(id),panel=el.closest('.tab');
    document.querySelectorAll('.tab').forEach(node=>node.classList.toggle('active',node===panel));
    for(let node=el;node;node=node.parentElement)if(node.tagName==='DETAILS')node.open=true;
   };
  });
  await page.addScriptTag({url:'/preferences.js'});
  assert.deepEqual(await page.evaluate(()=>snapshot()),await page.evaluate(()=>before),'Opening settings preserves every original input value/disabled state');
  assert(await page.evaluate(()=>originalNodes.every(node=>node===document.getElementById(node.id))),'No original control nodes replaced');
  assert.equal(await page.locator('#client-camera-help').count(),1,'Profile code retains its camera help target');
  assert(await page.locator('#client-options').evaluate(el=>el.open),'Everyday preferences start expanded');
  for(const id of ['preferences-recommended','preferences-experiments'])assert(!(await page.locator('#'+id).evaluate(el=>el.open)),id+' starts collapsed');
  assert(await page.locator('#client-audio').isVisible());assert(!(await page.locator('#client-cpu-profile').isVisible()));
  await page.uncheck('#client-audio');assert.equal(await page.evaluate(()=>listenerCount),1,'Existing listeners survive reparenting');
  assert((await page.textContent('#preferences-state')).includes('options match'));
  await page.evaluate(()=>{document.getElementById('client-cpu-profile').value='accurate';renderPreferences();});
  assert((await page.textContent('#preferences-state')).includes('1 recommended option differs'));
  await page.fill('#preferences-query','4 GB');assert(await page.locator('[data-control="client-4gb-apply"]').count());
  await page.locator('[data-control="client-4gb-apply"]').click();assert.equal(await page.evaluate(()=>navigation.at(-1)),'client-4gb-apply','Search navigates to a disabled action without running it');
  await page.evaluate(()=>document.getElementById('client').classList.add('active'));
  await page.fill('#preferences-query','FPS');assert(await page.locator('[data-control="client-dxvk-hud"]').count());
  await page.locator('[data-control="client-dxvk-hud"]').focus();await page.evaluate(()=>renderPreferences());
  assert.equal(await page.evaluate(()=>document.activeElement.dataset.control),'client-dxvk-hud','Status refresh preserves focused search result');
  await page.fill('#preferences-query','Spire');assert(await page.locator('[data-control="spire"]').count());
  await page.fill('#preferences-query','spellbook');assert(await page.locator('[data-control="client-spellbook-check"]').count());
  await page.evaluate(()=>{document.body.dataset.profile='traditional';renderPreferences();});
  assert.equal(await page.locator('[data-control="client-spellbook-check"]').count(),0,'Custom-only search result is removed for Traditional');
  await page.fill('#preferences-query','Faster spell');assert.equal(await page.locator('[data-control="client-fast-spells"]').count(),0,'Reparenting preserves Custom-only wrappers');
  await page.evaluate(()=>{document.body.dataset.profile='takp';document.getElementById('client-cpu-profile').value='accurate';renderPreferences();});
  assert((await page.textContent('#preferences-state')).includes('options match'),'TAKP compares with accurate CPU rather than RoF2 balanced');
  await page.evaluate(()=>{document.getElementById('client-cpu-profile').value='balanced';renderPreferences();});
  assert((await page.textContent('#preferences-state')).includes('1 recommended option differs'));
  await page.fill('#preferences-query','controller');assert(await page.locator('[data-control="controller-preset"]').count());
  await page.locator('[data-control="controller-preset"]').click();assert.equal(await page.evaluate(()=>navigation.at(-1)),'controller-preset');
  await page.fill('#preferences-query','<img src=x onerror=alert(1)>');assert.equal(await page.locator('#preferences-search-results img').count(),0);assert((await page.textContent('#preferences-search-status')).includes('No matching'));
  await page.click('#preferences-search-clear');assert.equal(await page.inputValue('#preferences-query'),'');
  assert.deepEqual(errors,[]);console.log('Preference hierarchy, preserved controls, profile baselines and search passed.');
 }finally{await browser.close();server.close();}
})().catch(error=>{console.error(error);server.close();process.exitCode=1;});
