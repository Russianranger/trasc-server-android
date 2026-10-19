'use strict';
// Readiness is derived from the selected world's live state. A checked box is
// never a substitute for an import receipt or a file comparison.
(()=>{
 const names={custom:'TRASC Custom',traditional:'Traditional EQEmu',takp:'TAKP World'};
 // Unknown future operations are conservatively treated as possible mutations.
 const readOnlyJob=/(?:^update_checklist_scan$|_(?:status|scan|preview|verify|catalog|search|detail|history|files|diff|characters|roster)$)/;
 let profile=null,report=null,reportFingerprint=null,scanning=false,scanError='',setupMode='new',scanGeneration=0;
 const cache=new Map();
 function savedSetupMode(){try{const mode=localStorage.getItem('trasc.setup-mode.'+activeProfile);return ['new','existing','restore'].includes(mode)?mode:'new';}catch{return 'new';}}
 function chooseSetupMode(mode){setupMode=mode;try{localStorage.setItem('trasc.setup-mode.'+activeProfile,mode);}catch{}renderReadiness();}
 function el(tag,text,className){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;}
 function button(id,text,handler,className='secondary'){const node=el('button',text,className);node.type='button';node.id=id;node.addEventListener('click',handler);return node;}
 async function go(id){
  try{
   if(/^takp-content-(quests|maps)$/.test(id)&&typeof window.reviewTakpContent==='function'){
    window.reviewTakpContent(id.slice('takp-content-'.length));return;
   }
   // Build eligibility may have changed since this tab last loaded its receipt.
   if(/^source-update-(build|fresh|deploy)$/.test(id)&&lastNative?.alive&&!busy&&typeof loadSourceUpdates==='function'){
    await loadSourceUpdates();
    if(id!=='source-update-deploy')id=sourceUpdateData?.requires_fresh_build?'source-update-fresh':'source-update-build';
   }
   if(typeof window.navigateToControl==='function')window.navigateToControl(id);
  }catch(error){notice(error.message,true);}
 }
 function text(id,value){const node=$(id);if(node&&node.textContent!==value)node.textContent=value;}
 function profileState(){return lastState&&(!lastState.profile||lastState.profile===activeProfile)?lastState:null;}
 function fingerprint(){
  const s=profileState();if(!s)return null;
  const update=s.source_update||{};
  return JSON.stringify([activeProfile,s.source,update.deployed_revision,update.staged_revision,update.update_build_ready,update.recovery_required,s.build_ready,s.binaries_ready,s.database_imported,s.maps_ready,
   s.client?.imported_at,s.client?.prepared_at,$('client-native-dll')?.checked,(s.jobs||[]).filter(j=>!readOnlyJob.test(j.operation)).map(j=>[j.id,j.operation,j.status])]);
 }
 function locked(){return !!(scanning||busy||sessionAction||!lastNative||lastNative.installing||lastNative.session_busy||lastClientNative?.busy||profileState()?.jobs?.some(j=>['queued','running'].includes(j.status)));}
 function invalidate(reason){if(report){report=null;reportFingerprint=null;scanError=reason||'Files or build state changed. Run the checklist again.';}}
 function step(id,label,state,detail,target){return {id,label,state,detail,target};}
 function setupSteps(){
  const s=profileState(),n=lastNative,c=lastClientNative,w=activeProfile==='takp'?s?.takp:activeProfile==='traditional'?s?.traditional:null;
  const rows=[step('profile','Choose a world profile',activeProfile?'current':'review',(names[activeProfile]||'Choose Custom, Traditional or TAKP')+'. Each profile keeps its own server, client and settings.','world-profile'),step('runtime','Verify runtime installation',n?.installed?'current':'attention',n?.installed?(n.alive?'Runtime is open.':'Already installed. Open it to check the remaining steps; no reinstall is needed.'):'Download the runtime, or choose an offline archive. Ready-made session backups include it.',n?.installed?'runtime-open':'runtime-online')];
  if(!n?.alive||!s){
   for(const [id,label]of [['build','Configure or import the server'],['database','Verify database and account'],['world','Verify quests, plugins, maps and content'],['client','Import and prepare client'],['compatibility','Review client/server compatibility'],['launch','Start server and launch client']])rows.push(step(id,label,'review','Open this world’s runtime to check existing files.','runtime-open'));
   return rows;
  }
  let worldTarget=activeProfile==='takp'?'takp-setup':'source-git',worldDetail='Import server source, maps, quests and supporting files.',worldState='attention';
  if(s.source&&s.maps_ready){
   if(activeProfile==='traditional'){
    const missing=['quests','plugins','lua_modules','assets'].find(k=>!w?.components?.[k]?.imported);
    worldState=missing?'attention':'current';worldTarget=missing==='assets'?'assets-git':'content-git';worldDetail=missing?'Import '+missing.replace('_',' ')+' for this world.':'Source, maps, quests and supporting files are present.';
   }else if(activeProfile==='takp'){
    worldState=w?.quests_ready&&w?.components?.assets?.imported?'current':'attention';worldDetail=worldState==='current'?'Pinned world components are present.':'Complete the TAKP world download.';
   }else{
    const content=report?.rows?.filter(r=>['quests','plugins','lua_modules'].includes(r.id))||[];
    worldState=content.length&&content.every(r=>['current','not_applicable'].includes(r.state))?'current':'review';worldTarget='update-checklist';worldDetail='Source and maps are present. Check quests and plugins against the imported source.';
   }
  }else if(s.source){worldTarget=activeProfile==='takp'?'takp-setup':'maps-git';worldDetail='Source is present. Import the maps for this world.';}
  rows.push(step('world','Verify quests, plugins, maps and content',worldState,worldDetail,worldTarget));
  const accountMissing=activeProfile==='takp'&&s.database_imported&&!w?.local_accounts;
  rows.push(step('database','Verify database and account',s.database_imported&&!accountMissing?'current':'attention',accountMissing?'Create a local TAKP account.':s.database_imported?'Existing database detected. Keep it when updating this world.':'Import the matching full database for a new world.',accountMissing?'takp-create-account':activeProfile==='takp'?'takp-initialize':'database-deployment'));
  const deployed=w?!!w.deployment?.deployed_valid:!!s.binaries_ready;
  const startReady=!w||!!w.deployment?.start_allowed;
  rows.push(step('build','Configure or import the server',deployed?(startReady?'current':'review'):'attention',deployed?(startReady?'Server binaries are installed. Update verification is a separate check.':w.deployment?.message||'Review this profile’s deployment prerequisites.'):!s.source?'Import the server source for this profile.':s.build_ready?'A staged build is waiting for deployment.':'Compile the imported source, then deploy its binaries.',!s.source?(activeProfile==='takp'?'takp-setup':'source-git'):deployed&&!startReady?(activeProfile==='takp'?'takp-checklist':'traditional-checklist'):s.build_ready?'deploy-build':'build-server'));
  let clientTarget='client-import',clientDetail='Import your own complete client ZIP.',clientState='attention';
  if(s.client?.imported){
   if(!c?.installed){clientTarget='client-runtime-online';clientDetail='Client files are imported. Install the client runtime.';}
   else if(c.directx_installed===false){clientTarget='client-directx-online';clientDetail='Install the DirectX model helpers for this client.';}
   else{
    const verified=report?.rows?.find(r=>r.id==='client_data')?.local_export_matches===true;
    clientState=verified||s.client.prepared?'current':'review';clientTarget='client-prepare';clientDetail=clientState==='current'?'Local client preparation is recorded. Review update freshness separately.':'Client and runtime are present. Prepare the client, then run the update checklist to verify its generated files.';
   }
  }
  rows.push(step('client','Import and prepare client',clientState,clientDetail,clientTarget));
  const compatibility=report?.rows?.find(row=>row.id==='compatibility');
  rows.push(step('compatibility','Review client/server compatibility',compatibility?.state==='current'?'current':'review',compatibility?.detail||(activeProfile==='custom'?'Run the update checklist to check the deployed server, executable and DLL. Launch keeps Continue / Cancel and the per-profile “Don’t warn again” choice.':'Review the client connection and generated files for this profile; confirm first login on the device.'),activeProfile==='custom'?'update-checklist':'client-connection-reload'));
  const playing=!!(s.running&&c?.alive&&c.display_ready&&c.launch?.thread_sample?.game_running&&Date.now()/1000-c.launch.thread_sample.sampled_at<25);
  rows.push(step('launch','Start server and launch client',playing?'current':'review',playing?'Server and client processes are running. Confirm world entry on the device.':'Use the top controls after reviewing readiness. Opening a checklist step never starts a session.',s.running?'client-launch':'start-server'));
  const order=['profile','runtime','build','database','world','client','compatibility','launch'];
  return order.map(id=>rows.find(row=>row.id===id));
 }
 function renderRows(root,rows,prefix){
  const signature=JSON.stringify(rows);if(cache.get(root)===signature)return;cache.set(root,signature);
  const existing=new Map([...root.children].map(n=>[n.dataset.key,n]));
  for(const row of rows){
   let item=existing.get(row.id);
   if(!item){item=el('li',undefined,'readiness-row');item.dataset.key=row.id;const copy=el('div',undefined,'readiness-copy');copy.append(el('strong'),el('span',undefined,'readiness-detail'));item.append(el('span',undefined,'readiness-state'),copy,button(prefix+row.id,'Review',()=>go(item.dataset.target)));root.append(item);}
   existing.delete(row.id);item.dataset.state=row.state;item.dataset.target=row.target||'';
   item.querySelector('strong').textContent=row.label;item.querySelector('.readiness-detail').textContent=row.detail;
   item.querySelector('.readiness-state').textContent=({current:'✓ Checked',missing:'Missing',outdated:'Outdated',modified:'Modified',attention:'Action needed',review:'Needs review',not_applicable:'Not applicable'})[row.condition||row.state]||'Not checked';
   const action=item.querySelector('button');action.hidden=!row.target;action.textContent=row.actionLabel||'Review';
  }
  for(const item of existing.values())item.remove();
 }
 function mainAction(){
  const s=profileState(),n=lastNative,c=lastClientNative;
  if(c?.alive&&c.display_ready)return {label:'Return to game',target:'client-view',activate:true};
  if(!n||!activeProfile)return {label:'Checking this world…',disabled:true};
  if(!n.installed)return {label:'Set up this world',target:'setup-guide'};
  if(!n.alive)return {label:'Open runtime',target:'runtime-open',activate:true};
  if(!s)return {label:'Check readiness',refresh:true};
  const world=activeProfile==='takp'?s.takp:activeProfile==='traditional'?s.traditional:null;
  const deployed=world?!!world.deployment?.deployed_valid:!!s.binaries_ready;
  if(!s.source||!s.database_imported||!s.maps_ready||!deployed||!s.client?.imported||!c?.installed)return {label:'Continue setup',target:'setup-guide'};
  if(world&&!world.deployment?.start_allowed&&!s.running)return {label:'Review server readiness',target:activeProfile==='takp'?'takp-checklist':'traditional-checklist'};
  if(!s.running)return {label:'Start server',target:'start-server',activate:true};
  return {label:'Launch client',target:'client-launch',activate:true};
 }
 function updateTarget(row){
  const targets={source:'source-update-check',build:profileState()?.source_update?.requires_fresh_build?'source-update-fresh':'source-update-build',deployed:'source-update-deploy',quests:activeProfile==='custom'?'quest-scan':activeProfile==='takp'?'takp-setup':'content-git',plugins:activeProfile==='custom'?'quest-scan':activeProfile==='takp'?'takp-setup':'content-git',lua_modules:activeProfile==='custom'?'quest-scan':activeProfile==='takp'?'takp-setup':'content-git',maps:activeProfile==='takp'?'takp-setup':'maps-git',assets:activeProfile==='traditional'?'assets-git':activeProfile==='takp'?'takp-setup':'source-update-check',lon:'lon-scan',client_data:'export-client',database:'database'};
  if(row.state==='not_applicable')return null;
  if(activeProfile==='takp'&&['quests','lua_modules','maps'].includes(row.id))return 'takp-content-'+(row.id==='maps'?'maps':'quests');
  if(row.id==='build')return targets.build;
  if(row.id==='assets'&&activeProfile!=='traditional')return 'file-path';
  const target=row.action?.target;
  return target&&(!window.launcherControlAvailable||window.launcherControlAvailable($(target)))?target:targets[row.id];
 }
 async function scan(){
  if(locked())return;
  if(!lastNative?.alive){if(!$('runtime-open').disabled)$('runtime-open').click();return;}
  const selected=activeProfile,generation=++scanGeneration;scanning=true;scanError='';report=null;renderReadiness();
  try{
   const result=await job('update_checklist_scan',{client_options:{native_dinput8:$('client-native-dll')?.checked!==false}});
   if(generation!==scanGeneration||selected!==activeProfile)return;
   if(result.profile!==selected||!Array.isArray(result.rows))throw Error('The checklist did not return results for this world. Try again.');
   report=result;reportFingerprint=fingerprint();
  }catch(error){if(generation===scanGeneration)scanError=error.message;}
  finally{if(generation===scanGeneration)scanning=false;renderReadiness();}
 }
 function mount(){
  const play=$('play-checklist'),guide=$('setup-guide'),updates=$('update-checklist');if(!play||!guide||!updates)return false;
  if(play.dataset.ready)return true;play.dataset.ready='true';
  const hero=el('article',undefined,'card readiness-hero');hero.append(el('h3','Your next adventure'),el('p','Checking the selected world…'));hero.children[1].id='play-readiness-summary';
  const actions=el('div',undefined,'buttons');actions.append(button('play-primary','Checking…',()=>{const a=mainAction();if(a.disabled)return;if(a.refresh){poll();return;}if(a.activate){const target=$(a.target);if(target&&!target.disabled)target.click();}else go(a.target);},''),button('play-manage','Setup checklist',()=>go('setup-guide')),button('play-updates','Review server updates',()=>go('update-checklist')));hero.append(actions);
  const status=el('p','Updates have not been checked.', 'hint');status.id='play-sync-summary';hero.append(status);play.append(hero);
  const quick=el('div',undefined,'buttons readiness-shortcuts');quick.append(button('play-controls','Controller mappings',()=>go('controller-layer')),button('play-content','Customize gameplay',()=>go('gameplay')),button('play-backup','Back up this world',()=>go('session-export')));play.append(quick);
  guide.append(el('h2','Set up your world'),el('p','Keep your progress. Each step checks what is already installed in the selected world.','hint'));
  const modes=el('div',undefined,'buttons');
  for(const [mode,label]of [['new','New setup'],['existing','Use existing files'],['restore','Restore a backup']])modes.append(button('setup-mode-'+mode,label,()=>chooseSetupMode(mode)));
  guide.append(modes);const help=el('p');help.id='setup-path-help';guide.append(help);
  const restore=el('div',undefined,'buttons');restore.id='setup-restore-actions';restore.append(button('setup-restore-one','Restore selected world',()=>go('session-import')),button('setup-restore-all','Restore all profiles',()=>go('session-import-all')));guide.append(restore);
  const space=el('p',undefined,'hint');space.id='setup-space';guide.append(space);
  const list=el('ol',undefined,'readiness-list');list.id='setup-step-list';guide.append(list);
  const progress=el('p',undefined,'hint');progress.id='setup-progress';progress.setAttribute('role','status');guide.insertBefore(progress,list);
  const next=button('setup-next','Continue setup',()=>{const step=setupSteps().find(r=>!['current','not_applicable'].includes(r.state));go(step?.target||'play');},'');guide.append(next);
  updates.append(el('h2','Server update checklist'),el('p','Compare the installed world with your imported source and recorded component revisions. This check does not download, replace, or delete files.','hint'));
  const buttons=el('div',undefined,'buttons');buttons.append(button('update-checklist-scan','Check installed files',scan,''),button('update-checklist-source','Review source updates',()=>go('source-update-check')));updates.append(buttons);
  const summary=el('p');summary.id='update-checklist-summary';summary.setAttribute('role','status');summary.setAttribute('aria-live','polite');updates.append(summary);
  const revisions=el('p',undefined,'hint');revisions.id='update-checklist-revisions';updates.append(revisions);
  const checks=el('ul',undefined,'readiness-list');checks.id='update-checklist-rows';updates.append(checks);
  const stages=el('ol',undefined,'update-workflow');
  for(const message of ['Review: check installed files, then open a component to inspect its changes and conflicts.','Apply: use that component’s existing confirmation, backup and deployment tools.','Verify: check installed files again, then review database/startup logs and test the client.'])stages.append(el('li',message));
  updates.insertBefore(stages,buttons);
  updates.append(button('update-checklist-verify','Verify after applying changes',scan));
  updates.append(el('p','Source, quests, maps and database content can have different revisions. “Needs review” remains visible when a component cannot be verified. Use its Review button, then check again after applying changes.','hint'));
  return true;
 }
 window.renderReadiness=function(){
  if(!mount())return;
  if(profile!==activeProfile){profile=activeProfile;report=null;reportFingerprint=null;scanError='';setupMode=savedSetupMode();++scanGeneration;scanning=false;cache.clear();}
  if(report&&(!lastNative?.alive||reportFingerprint!==fingerprint()))invalidate();
  const s=profileState(),action=mainAction(),rows=setupSteps();
  const primary=$('play-primary');primary.textContent=action.label;primary.disabled=!!(action.disabled||locked()||(action.activate&&$(action.target)?.disabled));
  text('play-readiness-summary',(names[activeProfile]||'Selected world')+' · '+(lastClientNative?.alive?'Client session is active.':s?.running?'Server is running.':!lastNative?.installed?'Choose setup or restore to begin.':!lastNative?.alive?'Open the runtime to inspect readiness.':'Your progress is kept with this world.'));
  for(const mode of ['new','existing','restore'])$('setup-mode-'+mode).setAttribute('aria-pressed',String(setupMode===mode));
  text('setup-path-help',setupMode==='restore'?'Restore a complete session or all-profile backup. The archive includes the runtime; no fresh install or rebuild is needed.':setupMode==='existing'?'Review each step and choose its offline ZIP or file option. Existing installations are detected; completed work does not need repeating.':'Use the tested download sources already selected for this world. Repository choices and offline alternatives remain available inside each step.');
  $('setup-restore-actions').hidden=setupMode!=='restore';$('setup-step-list').hidden=setupMode==='restore';$('setup-next').hidden=setupMode==='restore';
  text('setup-space','Available storage: '+bytes(s?.free_bytes??lastNative?.free_bytes)+'. New installations need at least 12 GB plus room for your client, maps and backups. Each importer checks its actual requirements.');
  renderRows($('setup-step-list'),rows,'setup-step-');
  text('setup-progress',rows.filter(r=>r.state==='current').length+' of '+rows.length+' steps checked for '+(names[activeProfile]||'this world')+'. Progress is detected from installed files and current status.');
  const next=rows.find(r=>!['current','not_applicable'].includes(r.state));text('setup-next',next?'Continue: '+next.label:'Return to Play');
  const scanButton=$('update-checklist-scan');scanButton.textContent=scanning?'Checking files…':lastNative?.alive?'Check installed files':'Open runtime to check';scanButton.disabled=locked()||!lastNative?.installed;
  $('update-checklist-verify').disabled=scanButton.disabled;
  const summary=report?report.rows.reduce((c,r)=>{c[r.state]=(c[r.state]||0)+1;return c;},{}):null;
  const message=scanning?'Checking files. Progress and cancellation are available in the activity panel.':scanError||(!lastNative?.alive?'Open this world’s runtime to inspect its files.':report?`${summary.current||0} checked · ${summary.attention||0} need action · ${summary.review||0} need review. Checked ${new Date(report.scanned_at*1000).toLocaleTimeString()}.`:'Not checked in this session. Run this after updating source, deploying binaries or synchronizing content.');
  text('update-checklist-summary',message);text('play-sync-summary',report?'Update checklist: '+message:scanError?'Update checklist needs a fresh check.':'Update checklist has not been run for the current files.');
  const revision=record=>record?.revision||record?.commit||'Not recorded';
  text('update-checklist-revisions',report?'Imported source: '+revision(report.source)+' · Staged build: '+revision(report.staged)+' · Deployed: '+revision(report.deployed):'');
  renderRows($('update-checklist-rows'),report?report.rows.map(row=>({...row,target:updateTarget(row),actionLabel:'Review'})):[],'update-row-');
 };
 Object.assign(operationLabels,{update_checklist_scan:'Checking installed world files'});
 // Native imports/restores can replace a world outside the backend job queue.
 document.addEventListener('click',event=>{const id=event.target.closest('button')?.id||'';if(/^(session-import|client-import|file-copy|file-move|file-upload|cleanup-delete|runtime-online|runtime-offline)/.test(id)){invalidate('World files may have changed. Check again when the operation finishes.');renderReadiness();}},true);
 window.renderReadiness();
})();
