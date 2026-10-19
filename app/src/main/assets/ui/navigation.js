'use strict';
// Navigation changes presentation only. Existing actions keep their native guards,
// confirmations and profile-aware API calls.
const launcherAreas={
 play:['play'],
 manage:['setup','server','build','files'],
 customize:['gameplay','spire','bots','appearance','database'],
 settings:['client','fixes','logs']
};
const launcherAreaHistory={play:'play',manage:'setup',customize:'gameplay',settings:'client'};
function launcherAreaForTab(name){return Object.keys(launcherAreas).find(area=>launcherAreas[area].includes(name))||'play';}
function launcherTabAllowed(name){return Object.values(launcherAreas).some(names=>names.includes(name))&&!(name==='spire'&&activeProfile==='takp');}
function syncLauncherNavigation(){
 const area=launcherAreaForTab(currentTab);
 document.body.dataset.area=area;launcherAreaHistory[area]=currentTab;
 document.querySelectorAll('.primary-nav [data-area]').forEach(button=>{
  const selected=button.dataset.area===area;button.classList.toggle('active',selected);
  if(selected)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');
 });
 document.querySelectorAll('[data-nav-area]').forEach(nav=>{nav.hidden=nav.dataset.navArea!==area;});
 document.querySelectorAll('.secondary-nav [data-tab]').forEach(button=>{
  const selected=button.dataset.tab===currentTab;button.classList.toggle('active',selected);
  if(selected)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');
 });
}
function navigateLauncherArea(area){
 if(!launcherAreas[area])return false;
 const remembered=launcherAreaHistory[area];
 const next=launcherTabAllowed(remembered)?remembered:launcherAreas[area].find(launcherTabAllowed);
 if(!next)return false;tab(next);return true;
}
function launcherControlAvailable(element){
 if(!element||element.closest('[hidden],[inert],[aria-hidden="true"]'))return false;
 const profile=activeProfile||document.body.dataset.profile||'custom';
 if(element.closest('[data-custom-only]')&&profile!=='custom')return false;
 if(element.closest('[data-traditional-only]')&&profile!=='traditional')return false;
 if(element.closest('[data-takp-only]')&&profile!=='takp')return false;
 if(element.closest('[data-takp-hide]')&&profile==='takp')return false;
 return true;
}
function navigateToControl(id){
 const target=$(id);if(!launcherControlAvailable(target))return false;
 const panel=target.closest('.tab');
 if(panel){if(!launcherTabAllowed(panel.id))return false;if(currentTab!==panel.id)tab(panel.id);}
 // Opening an existing panel must not recreate controls or discard unsaved edits.
 for(let parent=target;parent;parent=parent.parentElement){
  if(parent.tagName==='DETAILS')parent.open=true;
  if(parent.dataset.controllerCardCollapsed==='true'){
   parent.dataset.controllerCardCollapsed='false';
   parent.querySelectorAll('[data-controller-card-heading]').forEach(heading=>heading.setAttribute('aria-expanded','true'));
  }
 }
 let focusTarget=target;
 if(target.disabled){focusTarget=target.closest('article.card,details')?.querySelector('summary,h3,h2')||target;}
 if(!focusTarget.matches('button,input,select,textarea,summary,a[href],[tabindex]'))focusTarget.tabIndex=-1;
 focusTarget.focus({preventScroll:true});target.scrollIntoView({block:'start',behavior:'auto'});
 return true;
}
window.navigateToControl=navigateToControl;
window.navigateLauncherArea=navigateLauncherArea;
function renderImprovedUi(){
 if(typeof renderReadiness==='function')renderReadiness();
 if(typeof renderPreferences==='function')renderPreferences();
}
document.querySelectorAll('.primary-nav [data-area]').forEach(button=>button.addEventListener('click',()=>navigateLauncherArea(button.dataset.area)));

// Keep original nodes and event listeners while giving visual customization its
// own destination. Hidden profile-specific cards remain hidden in this container.
for(const id of ['client-ui-panel','game-settings-tile','takp-skeleton-panel']){
 const card=$(id);if(card)$('appearance').append(card);
}

// Updates lead with the checklist and reviewed source flow. Compilation and
// recovery are still available without occupying the whole opening screen.
const buildPanel=$('build'),sourceUpdatePanel=$('source-updates-panel');
if(buildPanel&&sourceUpdatePanel){
 const manualTools=document.createElement('details');manualTools.id='build-tools';manualTools.className='navigation-tools';
 const summary=document.createElement('summary');summary.textContent='First build, compiler options & recovery';manualTools.append(summary);
 const body=document.createElement('div');body.className='navigation-tools-body';manualTools.append(body);
 for(const child of [...buildPanel.children])if(!['update-checklist','takp-content-refresh'].includes(child.id)&&child!==sourceUpdatePanel)body.append(child);
 buildPanel.append(sourceUpdatePanel);if($('takp-content-refresh'))buildPanel.append($('takp-content-refresh'));buildPanel.append(manualTools);
}
syncLauncherNavigation();
