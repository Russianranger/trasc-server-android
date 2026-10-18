const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const root=path.resolve('app/src/main/assets/ui');
const fixture=`<!doctype html><html><head><style>
body{margin:0;padding:20px;background:#142220;color:white}button,input,select,summary{min-height:44px;margin:8px;padding:8px}button{display:inline-block}nav{display:flex;overflow:auto}.tab{display:none}.tab.active{display:block}details{border:1px solid #aaa;padding:16px;margin:16px}.grid{display:grid;grid-template-columns:1fr 1fr}[hidden]{display:none!important}
</style></head><body><main>
<select id="profile"><option>Custom</option><option>Traditional</option><option>TAKP</option></select>
<button id="disabled" disabled>Disabled</button><button id="runtime">Start runtime</button>
<nav><button data-tab="setup" class="active">Setup</button><button data-tab="build">Build</button><button data-tab="spire">Spire</button><button data-tab="client">Client</button><button data-tab="files">Files</button></nav>
<section id="setup" class="tab active"><article class="card" id="ordinary-tile"><div class="card-heading"><span>01</span><h3 id="ordinary-heading">Install runtime</h3></div><p>Existing setup tile.</p><button id="ordinary-install">Download runtime</button></article><details id="setup-tile"><summary id="setup-summary">Setup tile</summary><button id="install">Install</button></details></section>
<section id="build" class="tab"><details id="build-tile"><summary>Build settings</summary><button id="build-run">Build</button></details></section>
<section id="spire" class="tab"><button id="spire-search">Search</button></section>
<section id="client" class="tab"><div class="grid"><details id="client-tile"><summary id="client-summary">Connection</summary><label for="host">Host IP</label><input id="host" value="127.0.0.1"><button id="save">Save</button><input id="check" type="checkbox"><details id="nested"><summary id="nested-summary">Advanced</summary><button id="nested-button">Deep action</button></details></details><details id="other-tile"><summary id="other-summary">Other tile</summary><button id="other-action">Action</button></details></div><label for="renderer">Renderer</label><select id="renderer"><option value="software">Software</option><option value="disabled" disabled>Unavailable</option><option value="gpu">Android GPU</option></select><input id="readonly" readonly value="Protected path"><button id="hidden" hidden>Hidden</button><div style="height:1600px"></div><button id="bottom">At bottom</button></section>
<section id="files" class="tab"><button id="files-open">Browse</button></section>
</main><script>
let captureActive=false;window.fixture={clicks:0,keyboards:[],suspended:[]};window.Trasc={launcherKeyboard(show){fixture.keyboards.push(show)},launcherMenuSuspended(value){fixture.suspended.push(value)}};
document.querySelectorAll('[data-tab]').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b===button));document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t.id===button.dataset.tab));}));
document.getElementById('save').addEventListener('click',()=>fixture.clicks++);
window.appBack=()=>document.querySelector('[data-tab=setup]').click();
</script></body></html>`;
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1000,height:720}}),errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.setContent(fixture);await page.addStyleTag({path:path.join(root,'controller-menu.css')});await page.addScriptTag({path:path.join(root,'controller-menu.js')});
  const command=name=>page.evaluate(value=>launcherMenuController.command(value),name);
  const focused=()=>page.evaluate(()=>document.activeElement.id||document.activeElement.dataset.tab);
  const focus=id=>page.locator(id).focus();
  assert.equal(await command('down'),true);assert.equal(await focused(),'setup','First direction anchors at active tab');
  await command('nextTab');assert.equal(await focused(),'build');await command('previousTab');assert.equal(await focused(),'setup');
  await command('previousTab');assert.equal(await focused(),'files','LB wraps');await command('nextTab');assert.equal(await focused(),'setup','RB wraps');
  assert(await page.isVisible('#ordinary-install'),'Ordinary tiles start expanded');await command('down');assert.equal(await focused(),'ordinary-heading','Ordinary tile headings participate in controller focus');await command('back');assert.equal(await page.locator('#ordinary-heading').getAttribute('aria-expanded'),'false');assert(!(await page.isVisible('#ordinary-install')),'B minimizes ordinary article tile');
  await command('right');assert(await page.isVisible('#ordinary-install'),'D-pad right expands ordinary tile');await command('accept');assert(!(await page.isVisible('#ordinary-install')),'A toggles ordinary tile heading');await command('accept');await command('down');assert.equal(await focused(),'ordinary-install');await command('back');assert.equal(await focused(),'ordinary-heading');assert(!(await page.isVisible('#ordinary-install')),'B inside ordinary tile minimizes and focuses heading');
  for(const profile of ['Custom','Traditional','TAKP']){
   await page.selectOption('#profile',{label:profile});await page.evaluate(value=>document.querySelector('[data-tab=spire]').hidden=value,profile==='TAKP');
   await focus('[data-tab=build]');await page.click('[data-tab=build]');await command('nextTab');assert.equal(await focused(),profile==='TAKP'?'client':'spire','Shoulders skip hidden profile tabs');
  }
  await page.click('[data-tab=client]');await focus('#client-summary');await command('right');assert(await page.locator('#client-tile').getAttribute('open')!==null,'D-pad right expands tile');
  await command('down');assert.equal(await focused(),'host');await command('accept');assert.equal((await page.evaluate(()=>fixture.keyboards)).at(-1),true,'A requests Android keyboard for text field');
  await command('back');assert.equal((await page.evaluate(()=>fixture.keyboards)).at(-1),false,'B first dismisses keyboard');assert(await page.locator('#client-tile').getAttribute('open')!==null);
  await command('down');assert.equal(await focused(),'save');await command('accept');assert.equal(await page.evaluate(()=>fixture.clicks),1,'A clicks once');
  await page.keyboard.press('Enter');assert.equal(await page.evaluate(()=>fixture.clicks),2,'Keyboard Enter clicks once');await page.keyboard.press('Space');assert.equal(await page.evaluate(()=>fixture.clicks),3,'Keyboard Space clicks once');
  await command('down');assert.equal(await focused(),'check');await command('accept');assert(await page.isChecked('#check'),'A toggles checkboxes');
  await focus('#nested-summary');await command('accept');assert(await page.locator('#nested').getAttribute('open')!==null);await focus('#nested-button');await command('back');assert.equal(await focused(),'nested-summary');assert.equal(await page.locator('#nested').getAttribute('open'),null,'B closes innermost tile');assert(await page.locator('#client-tile').getAttribute('open')!==null);
  await command('back');assert.equal(await focused(),'client-summary');assert.equal(await page.locator('#client-tile').getAttribute('open'),null,'Next B closes parent');
  await command('down');assert.notEqual(await focused(),'host','Closed tile fields cannot receive focus');
  await focus('#client-summary');await command('right');await command('left');assert.equal(await page.locator('#client-tile').getAttribute('open'),null,'Left collapses selected tile');
  await focus('#renderer');await command('accept');assert.equal(await page.locator('dialog[open]').count(),1,'A opens controller select picker');assert.equal(await page.locator('dialog button:disabled').count(),1);
  await command('down');assert.equal(await page.evaluate(()=>document.activeElement.textContent),'Android GPU','Disabled options skipped');await command('accept');assert.equal(await page.inputValue('#renderer'),'gpu');assert.equal(await page.locator('dialog').count(),0);assert.equal(await focused(),'renderer');
  await command('accept');await command('nextTab');assert.equal(await page.locator('nav .active').getAttribute('data-tab'),'client','Modal retains shoulder ownership');await command('back');assert.equal(await page.locator('dialog').count(),0,'B cancels picker');
  await focus('#readonly');const keyboards=await page.evaluate(()=>fixture.keyboards.length);await command('accept');assert.equal(await page.evaluate(()=>fixture.keyboards.length),keyboards,'Readonly fields do not open IME');
  await page.evaluate(()=>document.getElementById('client-tile').open=true);await focus('#host');await page.keyboard.press('ArrowLeft');assert.equal(await focused(),'host','Keyboard arrows retain text editing');
  await page.evaluate(()=>{document.getElementById('client-tile').open=true;document.getElementById('host').focus();captureActive=true;});assert.equal(await command('nextTab'),false,'Active gameplay input test keeps controller');assert.equal(await focused(),'host');
  await page.evaluate(()=>{captureActive=false;launcherMenuController.setSuspended(true)});assert.equal(await command('accept'),false,'Rebinding can exclusively own input');assert.equal((await page.evaluate(()=>fixture.suspended)).at(-1),true);await page.evaluate(()=>launcherMenuController.setSuspended(false));
  await page.evaluate(()=>{const button=document.createElement('button');button.id='dynamic';button.textContent='Dynamic action';document.getElementById('files').append(button);});await page.click('[data-tab=files]');await focus('#files-open');await command('down');assert.equal(await focused(),'dynamic','Live candidates include newly rendered controls');
  await page.evaluate(()=>document.getElementById('dynamic').disabled=true);await command('down');assert.equal(await focused(),'files','Focus recovers from disabled dynamic control');
  await page.click('[data-tab=client]');await focus('#bottom');await command('accept');assert(await page.evaluate(()=>document.getElementById('bottom').getBoundingClientRect().bottom<=innerHeight+1),'Focus scrolls offscreen controls into view');
  assert.equal(await page.locator('#bottom').evaluate(element=>getComputedStyle(element).outlineWidth),'3px','Native focus has visible ring');
  await page.setViewportSize({width:375,height:812});await focus('#renderer');await command('accept');assert(await page.locator('dialog').evaluate(element=>element.getBoundingClientRect().width<=innerWidth),'Picker fits phone viewport');await command('back');
  assert.deepEqual(errors,[]);
  console.log('Controller menu passed: tab wrap/hidden profiles, tile expansion/collapse, single activation, Android IME request, safe readonly fields, accessible selects, modal isolation, capture/rebind ownership, dynamic controls, scrolling and phone layout.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
