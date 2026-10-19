const {chromium}=require('playwright');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert');
const root=path.resolve('app/src/main/assets/ui');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,'');
const app=fs.readFileSync(path.join(root,'app.js'),'utf8');
const actualTab=app.slice(app.indexOf('function tab(name)'),app.indexOf('\nwindow.appBack'));
const server=http.createServer((req,res)=>{
 const name=req.url==='/'?'index.html':req.url.slice(1);
 if(!/^[\w.-]+$/.test(name)){res.writeHead(404);res.end();return;}
 try{res.setHeader('Content-Type',name.endsWith('.css')?'text/css':name.endsWith('.js')?'text/javascript':name.endsWith('.webp')?'image/webp':'text/html');res.end(name==='index.html'?html:fs.readFileSync(path.join(root,name)));}catch{res.writeHead(404);res.end();}
});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  await page.addScriptTag({content:`const $=id=>document.getElementById(id);let currentTab='play',activeProfile='custom';
   function renderOverview(){}function api(){return Promise.resolve({});}function notice(){}
   function browse(){return Promise.resolve();}function logs(){return Promise.resolve();}function loadLogRetention(){return Promise.resolve();}
   window.fixture={mutations:0};${actualTab}
   window.appBack=()=>tab('play');
   document.querySelectorAll('[data-tab]').forEach(button=>button.addEventListener('click',()=>tab(button.dataset.tab)));
   document.getElementById('source-git').addEventListener('click',()=>fixture.mutations++);`});
  await page.addScriptTag({path:path.join(root,'navigation.js')});
  await page.addScriptTag({path:path.join(root,'controller-menu.js')});
  const activeTab=()=>page.locator('.tab.active').getAttribute('id');
  const area=()=>page.locator('.primary-nav [aria-current=page]').getAttribute('data-area');
  const command=name=>page.evaluate(name=>launcherMenuController.command(name),name);
  assert.equal(await activeTab(),'play');assert.equal(await area(),'play');
  assert.equal(await page.locator('.primary-nav button').count(),4);
  assert.equal(await page.locator('.runtime-toolbar button').count(),6,'Header retains exactly runtime/server/client Start and Stop');
  assert.equal(await page.locator('#server #restart-server').count(),1,'Restart belongs to Manage > Server');
  assert.equal(await page.locator('.runtime-toolbar #restart-server').count(),0);
  assert.equal(await page.locator('.secondary-nav:visible').count(),0,'Play opens without a secondary menu');
  await command('nextTab');assert.equal(await area(),'manage');assert.equal(await activeTab(),'setup');
  assert.equal(await page.locator('#setup-tools').getAttribute('open'),null,'Setup guide leads before advanced tools');
  await page.click('.secondary-nav [data-tab=server]');assert.equal(await activeTab(),'server');
  await command('nextTab');assert.equal(await area(),'customize');assert.equal(await activeTab(),'gameplay');
  await command('nextTab');assert.equal(await area(),'settings');assert.equal(await activeTab(),'client');
  await command('nextTab');assert.equal(await area(),'play');
  await command('previousTab');assert.equal(await area(),'settings','Shoulder wraps four areas');
  await page.click('.primary-nav [data-area=manage]');assert.equal(await activeTab(),'server','Area returns to remembered page');
  await page.evaluate(()=>navigateToControl('source-git'));
  assert.equal(await activeTab(),'setup');assert(await page.locator('#setup-tools').evaluate(element=>element.open));
  assert.equal(await page.evaluate(()=>document.activeElement.id),'source-git');
  assert.equal(await page.evaluate(()=>fixture.mutations),0,'A checklist route never activates the target action');
  await page.fill('#source-ref','my-review-branch');
  await page.evaluate(()=>navigateToControl('build-jobs'));
  assert.equal(await activeTab(),'build');assert(await page.locator('#build-tools').evaluate(element=>element.open));
  assert.equal(await page.locator('#source-updates-panel').evaluate(element=>element.parentElement.id),'build','Reviewed updates stay outside manual tools');
  await page.evaluate(()=>navigateToControl('source-git'));
  assert.equal(await page.inputValue('#source-ref'),'my-review-branch','Routing preserves unsaved inputs');
  await page.click('#source-git');assert.equal(await page.evaluate(()=>fixture.mutations),1,'Original action listener remains attached exactly once');
  await page.evaluate(()=>navigateToControl('game-settings-load'));assert.equal(await activeTab(),'appearance');assert.equal(await area(),'customize');
  assert.equal(await page.locator('#appearance #client-ui-panel').count(),1);
  assert.equal(await page.locator('#appearance #takp-skeleton-panel').count(),1);
  await page.evaluate(()=>{activeProfile='takp';document.body.dataset.profile='takp';});
  assert(!(await page.locator('.secondary-nav [data-tab=spire]').isVisible()),'Unsupported TAKP content editor stays hidden');
  assert.equal(await page.evaluate(()=>navigateToControl('lon-scan')),false,'Routing does not reveal wrong-profile controls');
  await page.evaluate(()=>tab('spire'));assert.equal(await activeTab(),'appearance','Unsupported tab cannot be selected programmatically');
  await page.evaluate(()=>navigateToControl('takp-skeleton-refresh'));assert.equal(await activeTab(),'appearance');
  const focused=await page.evaluate(()=>document.activeElement.id);
  await page.evaluate(()=>{for(let i=0;i<5;i++){renderImprovedUi();syncLauncherNavigation();}});
  assert.equal(await page.evaluate(()=>document.activeElement.id),focused,'Status rendering preserves keyboard/gamepad focus');
  await command('back');assert.equal(await page.evaluate(()=>document.activeElement.closest('article')?.id),'takp-skeleton-panel');
  await command('back');assert.equal(await page.evaluate(()=>document.activeElement.dataset.area),'customize');
  await command('back');assert.equal(await activeTab(),'play','B returns to Play after collapsing local controls');
  for(const width of [375,720,1280]){
   await page.setViewportSize({width,height:width===720?1280:812});
   assert(await page.locator('.primary-nav').evaluate(element=>element.getBoundingClientRect().right<=innerWidth),'Main navigation fits '+width);
   assert(await page.locator('.runtime-toolbar').evaluate(element=>element.getBoundingClientRect().right<=innerWidth),'Session controls fit '+width);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal page overflow at '+width);
  }
  const duplicates=await page.evaluate(()=>{const ids=[...document.querySelectorAll('[id]')].map(e=>e.id);return ids.filter((id,i)=>ids.indexOf(id)!==i);});
  assert.deepEqual(duplicates,[]);assert.deepEqual(errors,[]);
  console.log('Improved navigation passed: four areas, six persistent controls, server restart, remembered subpages, setup/build disclosure routing, preserved actions and edits, profile guards, focus stability, controller back and responsive layout.');
 }finally{await browser.close();server.close();}
})().catch(error=>{console.error(error);server.close();process.exitCode=1;});
