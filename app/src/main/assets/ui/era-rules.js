'use strict';
let eraProfile=null,eraGeneration=0,eraReadGeneration=0,eraReading=false,eraNextCheck=0;
let eraStatus=null,eraReview=null,eraChoice=null,eraMessage='';
const eraLabels={velious:'Velious',luclin:'Luclin',pop:'Planes of Power',default:'Default'};
function eraProfileMatches(){return activeProfile==='traditional'&&lastNative?.profile==='traditional'&&lastState?.profile==='traditional'&&(!lastClientNative?.profile||lastClientNative.profile==='traditional');}
function eraHasDraft(){return typeof ruleDraft!=='undefined'&&Object.keys(ruleDraft).length>0;}
function eraBlockReason(ownAction=false){
 if(!eraProfileMatches())return 'Open the Traditional runtime to check era rules.';
 if(!lastNative.alive||lastNative.installing||lastNative.session_busy)return 'Open the Traditional runtime and finish transfers first.';
 if(!lastState.database_imported)return 'Import the Traditional database before choosing an era.';
 if(lastState.running)return 'Stop the server before changing era rules.';
 if(!lastClientNative||lastClientNative.alive||lastClientNative.busy)return 'Stop the client before changing era rules.';
 if(busy>(ownAction?1:0)||sessionAction||lastState.jobs?.some(j=>['queued','running'].includes(j.status)))return 'Finish the current operation before changing era rules.';
 return '';
}
function clearEraReview(message=''){eraReview=null;eraGeneration++;eraMessage=message;$('era-review').hidden=true;}
function resetEraRules(){
 eraProfile=activeProfile;eraStatus=null;eraChoice=null;eraReadGeneration++;eraReading=false;eraNextCheck=0;
 clearEraReview();$('era-current').textContent='Open the Traditional runtime to check the active era.';
}
function eraReviewCurrent(){return !!eraReview&&eraReview.profile===activeProfile&&eraReview.era===eraChoice&&!!eraReview.review_token&&eraReview.revision===eraStatus?.revision;}
function renderEraRules(){
 if(eraProfile!==activeProfile)resetEraRules();
 const traditional=activeProfile==='traditional',blocked=eraBlockReason(),draft=eraHasDraft();
 $('era-refresh').disabled=!traditional||!eraProfileMatches()||!lastNative?.alive||!!(busy||sessionAction||eraReading||lastNative.installing||lastNative.session_busy||lastState?.jobs?.some(j=>['queued','running'].includes(j.status)));
 for(const button of $('era-rules-panel').querySelectorAll('[data-era]')){const selected=traditional&&button.dataset.era===eraChoice;button.disabled=!traditional||!!blocked||eraReading;button.setAttribute('aria-pressed',String(selected));button.classList.toggle('secondary',!selected);}
 if(!traditional){$('era-apply').disabled=true;return;}
 const current=eraStatus?.current;
 $('era-current').textContent=current?'Active: '+(eraLabels[current.era]||current.label||'Custom rule set')+(current.customized?' (customized)':'')+' · rule set '+current.ruleset+'.'+(eraStatus.pending_restart?' Restart required.':'')+(eraStatus.default_ruleset?' Database default: '+eraStatus.default_ruleset.name+' ('+eraStatus.default_ruleset.id+').':''):'Open the Traditional runtime to check the active era.';
 $('era-apply').disabled=!!blocked||eraReading||draft||!eraReviewCurrent();
 $('era-apply').textContent=eraChoice==='default'?'Apply database default':'Apply chosen era';
 $('era-status').textContent=blocked||(draft?'Save changed gameplay rules or reload database settings to discard them before applying an era.':eraMessage||(eraReviewCurrent()?'Review these changes, then apply for the next server start.':'Choose an era to preview its rules and zone routing.'));
 if(!eraReviewCurrent())$('era-review').hidden=true;
}
function eraContextCurrent(context){return context.profile===activeProfile&&context.generation===eraGeneration&&eraProfileMatches();}
async function eraRequest(operation,args,context){
 const started=await api(operation,args);if(!eraContextCurrent(context))return null;
 // Read and mutation operations use the same queued backend interface.
 if(!started?.id)return started;
 for(;;){
  await new Promise(resolve=>setTimeout(resolve,1400));if(!eraContextCurrent(context))return null;
  const state=await api('state');if(!eraContextCurrent(context)||state.profile!==context.profile)return null;
  render(state);const item=state.jobs?.find(j=>j.id===started.id);
  if(!item)throw Error('Era operation status was lost. Refresh era status and try again.');
  if(['error','cancelled'].includes(item.status))throw Error(item.error||'Era operation cancelled.');
  if(item.status==='done')return item.result||{};
 }
}
function acceptEraStatus(status){
 if(status.profile&&status.profile!=='traditional')return false;
 if(!status.revision)throw Error('Era status is incomplete. Refresh before choosing an era.');
 if(eraReview&&eraReview.revision!==status.revision)clearEraReview('Database settings changed. Choose the era again to review fresh changes.');
 eraStatus=status;renderEraRules();return true;
}
async function refreshEraStatus(){
 if(activeProfile!=='traditional'||!eraProfileMatches()||!lastNative?.alive||lastNative.installing||lastNative.session_busy||eraReading||busy||sessionAction||lastState?.jobs?.some(j=>['queued','running'].includes(j.status)))return;
 eraReading=true;eraNextCheck=Date.now()+10000;const read=++eraReadGeneration,context={profile:activeProfile,generation:eraGeneration};renderEraRules();
 try{const status=await eraRequest('era_status',{},context);if(read!==eraReadGeneration||!status||!eraContextCurrent(context))return;acceptEraStatus(status);}
 catch(error){if(read!==eraReadGeneration||!eraContextCurrent(context))return;clearEraReview(error.message);eraStatus=null;}
 finally{if(read===eraReadGeneration){eraReading=false;renderEraRules();}}
}
function checkEraStatus(){if(currentTab==='gameplay'&&activeProfile==='traditional'&&Date.now()>=eraNextCheck)refreshEraStatus();}
function eraValue(value){return value==null?'Not set':typeof value==='object'?JSON.stringify(value):String(value);}
function eraTableRow(values){const row=document.createElement('tr');for(const value of values){const cell=document.createElement('td');cell.textContent=eraValue(value);row.append(cell);}return row;}
function eraList(id,values){$(id).replaceChildren(...(values||[]).map(value=>{const item=document.createElement('li');item.textContent=typeof value==='string'?value:value?.rule&&value?.reason?value.rule+': '+value.reason:eraValue(value);return item;}));}
function showEraReview(review){
 const changes=review.changes||[],zones=review.zone_changes||[],counts=review.zone_counts||{};
 $('era-review-heading').textContent='Review '+(review.label||eraLabels[eraChoice]);
 $('era-review-summary').textContent=changes.length+' rule and world changes. '+(counts.routed??zones.length)+' of '+(counts.total??zones.length)+' zones routed; '+(counts.existing_overrides??0)+' existing zone overrides.'+(review.requires_restart?' Restart required after applying.':'');
 $('era-changes-label').textContent='Rule and world changes · '+changes.length;
 $('era-changes').replaceChildren(...changes.map(change=>eraTableRow([({rules:'Era rules',world_content:'Startup rules',active_ruleset:'World selection'}[change.scope]||change.scope)+(change.ruleset==null?'':' · '+change.ruleset),change.rule,change.before,change.after,change.reason])));
 $('era-zones-label').textContent='Exact zone routing changes · '+zones.length;
 $('era-zones').replaceChildren(...zones.map(change=>eraTableRow([change.zone+' · version '+change.version+' · ID '+change.id,change.before,change.after])));
 eraList('era-limitations',review.limitations||eraStatus?.limitations);eraList('era-omissions',review.omissions);
 $('era-manual-edits').textContent=review.manual_edits?.length?'Existing manual edits: '+review.manual_edits.map(edit=>typeof edit==='string'?edit:edit.ruleset+' · '+edit.rule+' = '+eraValue(edit.value)+' (preset '+eraValue(edit.preset)+')').join('; '):'Manual gameplay editing remains available after applying.';
 $('era-review').hidden=false;
}
async function chooseEra(era){
 const blocked=eraBlockReason();if(blocked)throw Error(blocked);
 if(!Object.hasOwn(eraLabels,era))throw Error('Choose an available expansion era.');
 eraReadGeneration++;eraReading=false;eraChoice=era;clearEraReview('Loading '+eraLabels[era]+' changes…');const context={profile:activeProfile,generation:eraGeneration};
 busy++;renderSessionControls();
 try{
  const review=await eraRequest('era_preview',{era},context);if(!review||!eraContextCurrent(context))return;
  if(!review.review_token||!review.revision)throw Error('Era preview is incomplete. Choose the era again.');
  eraStatus={...(eraStatus||{}),revision:review.revision};eraReview={...review,era,profile:context.profile};eraMessage='';showEraReview(review);
 }catch(error){if(eraContextCurrent(context)){clearEraReview(error.message);notice(error.message,true);}}
 finally{busy--;renderSessionControls();}
}
async function applyEra(){
 const blocked=eraBlockReason();if(blocked)throw Error(blocked);
 if(eraReading)throw Error('Wait for the era status refresh before applying.');
 if(eraHasDraft())throw Error('Save changed gameplay rules or reload database settings to discard them first.');
 if(!eraReviewCurrent())throw Error('Choose an era and review its current changes first.');
 const era=eraChoice,review_token=eraReview.review_token;clearEraReview('Saving '+eraLabels[era]+' rules…');const context={profile:activeProfile,generation:eraGeneration};
 eraReadGeneration++;eraReading=false;busy++;renderSessionControls();
 try{
  const result=await eraRequest(era==='default'?'era_restore':'era_apply',era==='default'?{review_token,mode:'default'}:{era,review_token},context);
  if(!result||!eraContextCurrent(context))return;
  eraMessage=(result.message||eraLabels[era]+' rules saved.')+(result.restart_required?' Restart the server to apply.':'');notice(eraMessage);
  if(Number.isInteger(result.ruleset_id)){await loadRules(result.ruleset_id,()=>eraContextCurrent(context));if(!eraContextCurrent(context))return;}
  eraStatus=null;eraNextCheck=0;
 }catch(error){if(eraContextCurrent(context)){clearEraReview(error.message+' Choose the era again to review fresh changes.');notice(error.message,true);}}
 finally{busy--;renderSessionControls();if(eraContextCurrent(context))await refreshEraStatus();}
}
for(const button of $('era-rules-panel').querySelectorAll('[data-era]'))button.addEventListener('click',()=>chooseEra(button.dataset.era).catch(error=>notice(error.message,true)));
$('era-refresh').addEventListener('click',refreshEraStatus);
$('era-apply').addEventListener('click',()=>applyEra().catch(error=>notice(error.message,true)));
$('era-clear').addEventListener('click',()=>{clearEraReview();eraChoice=null;renderEraRules();});
for(const event of ['input','change'])$('gameplay').addEventListener(event,renderEraRules);
renderEraRules();
