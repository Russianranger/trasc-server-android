'use strict';
let spellbookCompatibilityProfile=null,spellbookCompatibilityGeneration=0,spellbookCompatibilityData=null;
let spellbookCompatibilityLoading=false,spellbookCompatibilityMutating=false,spellbookCompatibilityLoadedAt=0,spellbookCompatibilityError='',spellbookCompatibilityObserved='',spellbookCompatibilityFeedback='';

function resetSpellbookCompatibilityProfile(){
 if(spellbookCompatibilityProfile===activeProfile)return;
 spellbookCompatibilityProfile=activeProfile;spellbookCompatibilityGeneration++;spellbookCompatibilityData=null;
 spellbookCompatibilityLoading=false;spellbookCompatibilityMutating=false;spellbookCompatibilityLoadedAt=0;spellbookCompatibilityError='';spellbookCompatibilityObserved='';spellbookCompatibilityFeedback='';
}
function spellbookCompatibilityContextReady(){
 return activeProfile==='custom'&&lastNative?.profile==='custom'&&!!lastNative.alive&&!lastNative.installing&&!lastNative.session_busy&&!lastNative.lon_input?.busy&&lastClientNative?.profile==='custom'&&lastState?.profile==='custom';
}
function spellbookCompatibilityBlocked(ownAction=false){
 return !!(busy>(ownAction?1:0)||sessionAction||spellbookCompatibilityLoading||spellbookCompatibilityMutating||spellbookCompatibilityError||!spellbookCompatibilityContextReady()||lastClientNative.alive||lastClientNative.busy||lastState?.running||lastState?.jobs?.some(j=>['queued','running'].includes(j.status))||spellbookCompatibilityData?.profile!=='custom');
}
function spellbookFreshnessLabel(value,requirements=null){
 const deployedMatch=value?.state==='stale'&&value.hash_verified===true&&value.source_identity_verified===true&&requirements?.known_deployed===true&&requirements.deployed_binary_verified===true&&requirements.required_spellbook_slots===1440&&value.source_commit&&value.source_commit===requirements.deployed_source_commit;
 if(deployedMatch)return 'Verified for deployed server; selected source differs';
 const labels={current:'Current source build',stale:'Rebuild required for selected source',unknown:'Build source unknown',missing:'Not present',modified:'File changed after build'};
 return value?((labels[value.state]||'Not verified')+(value.reason?' · '+value.reason:'')):'Not verified';
}
function spellbookCompatibilityContext(){
 if(activeProfile!=='custom')return 'Available for the Triptych Custom profile.';
 if(!lastNative?.alive)return 'Open this world’s server runtime to check client compatibility.';
 if(lastNative.installing)return 'Wait for runtime installation to finish.';
 if(lastNative.session_busy||lastNative.lon_input?.busy||sessionAction)return 'Wait for the current file transfer to finish.';
 if(!spellbookCompatibilityContextReady())return 'Waiting for this world’s runtime and client status…';
 if(spellbookCompatibilityLoading)return 'Checking the selected source, executable and DLL…';
 if(spellbookCompatibilityMutating)return 'Updating the Custom client executable. Keep the runtime open…';
 if(lastState?.running||lastClientNative?.alive||lastClientNative?.busy)return 'Stop the server and client before applying, restoring or verifying its executable.';
 if(busy||lastState?.jobs?.some(j=>['queued','running'].includes(j.status)))return 'Wait for the current operation to finish.';
 return spellbookCompatibilityError;
}
function renderSpellbookCompatibilityControls(){
 resetSpellbookCompatibilityProfile();
 const panel=$('client-spellbook-panel');if(!panel)return;
 panel.hidden=activeProfile!=='custom';
 const data=spellbookCompatibilityData,blocked=spellbookCompatibilityBlocked(),context=spellbookCompatibilityContext(),dll=data?.dll;
 $('client-spellbook-check').disabled=!!(busy||sessionAction||spellbookCompatibilityLoading||spellbookCompatibilityMutating||!spellbookCompatibilityContextReady());
 $('client-spellbook-apply').disabled=blocked||data?.can_apply!==true;
 $('client-spellbook-apply').textContent=data?.patched?'Verify 1,440-slot client patch':'Apply 1,440-slot client patch';
 $('client-spellbook-restore').disabled=blocked||data?.can_restore!==true;
 $('client-spellbook-compiler').disabled=!!(busy||sessionAction||activeProfile!=='custom');
 $('client-spellbook-status').textContent=context||spellbookCompatibilityFeedback||data?.warning||data?.message||(data?.patched?'The executable has the 1,440-slot spellbook and 4 GB address patches.':'Check client compatibility before entering a server with the expanded spellbook.');
 const requirements=data?.requirements;
 $('client-spellbook-source').textContent=data?'Selected source: '+(requirements?.selected_source_commit||dll?.source?.commit||'revision not recorded')+(requirements?.selected_spellbook_slots?' · '+requirements.selected_spellbook_slots+' slots in source.':'.')+'\nDeployed server: '+(requirements?.deployed_source_commit||'revision not verified')+(requirements?.known_deployed&&requirements?.deployed_binary_verified&&requirements?.required_spellbook_slots?' · '+requirements.required_spellbook_slots+' slots verified.':' · spellbook requirement not verified.')+(requirements?.message?'\n'+requirements.message:''):'Selected source has not been checked.';
 $('client-spellbook-exe').textContent=data?'Executable: '+(data.path||data.exe||'eqgame.exe')+' · '+(data.patched?'1,440-slot patch detected':data.supported?'Supported executable · patch required':'Unsupported or unavailable executable')+(data.sha256?'\nSHA-256: '+data.sha256:''):'Executable has not been checked.';
 $('client-spellbook-dll').textContent=dll?'Installed dinput8.dll: '+spellbookFreshnessLabel(dll.freshness?.installed,requirements)+(dll.freshness?.installed?.source_commit?'\nInstalled DLL build revision: '+dll.freshness.installed.source_commit:'')+'\nStaged dinput8.dll: '+spellbookFreshnessLabel(dll.freshness?.staged)+(dll.freshness?.staged?.source_commit?'\nStaged DLL build revision: '+dll.freshness.staged.source_commit:'')+(dll.source?.commit?'\nSelected DLL source revision: '+dll.source.commit:'')+(dll.source?.error?'\n'+dll.source.error:''):'DLL freshness has not been checked. A previously compiled DLL may require rebuilding after a source update.';
 $('client-spellbook-backup').textContent=data?.backup_exists?'Protected pre-patch executable: '+(data.backup_path||'retained in this profile’s protected recovery folder')+'. Restore checks the current file revision before replacing it.':'Apply retains a protected copy of the current executable before making changes.';
}
function showSpellbookCompatibility(data){
 if(activeProfile!=='custom'||data?.profile!==activeProfile)return false;
 spellbookCompatibilityData=data;spellbookCompatibilityLoadedAt=Date.now();spellbookCompatibilityError='';spellbookCompatibilityFeedback='';renderSpellbookCompatibilityControls();return true;
}
async function loadSpellbookCompatibility(){
 resetSpellbookCompatibilityProfile();
 if(!spellbookCompatibilityContextReady()||spellbookCompatibilityLoading||spellbookCompatibilityMutating){renderSpellbookCompatibilityControls();return;}
 const profile=activeProfile,generation=++spellbookCompatibilityGeneration;spellbookCompatibilityLoading=true;renderSpellbookCompatibilityControls();
 try{
  const data=await api('client_spellbook_status',{},20000);
  if(profile!==activeProfile||generation!==spellbookCompatibilityGeneration)return;
  if(data?.profile!==profile)throw Error('Compatibility status belongs to another world. Check client compatibility again.');
  showSpellbookCompatibility(data);
 }catch(e){
  if(profile===activeProfile&&generation===spellbookCompatibilityGeneration){spellbookCompatibilityError=e.message;spellbookCompatibilityLoadedAt=Date.now();}
  throw e;
 }finally{
  if(profile===activeProfile&&generation===spellbookCompatibilityGeneration){spellbookCompatibilityLoading=false;renderSpellbookCompatibilityControls();}
 }
}
function checkSpellbookCompatibilityStatus(){
 resetSpellbookCompatibilityProfile();renderSpellbookCompatibilityControls();
 const signature=JSON.stringify([activeProfile,lastState?.source,lastState?.client?.imported,lastState?.client?.files,lastState?.client?.bytes,lastClientNative?.alive,lastClientNative?.busy,!!busy]);
 const changed=signature!==spellbookCompatibilityObserved;spellbookCompatibilityObserved=signature;
 if(!spellbookCompatibilityContextReady()||spellbookCompatibilityLoading||spellbookCompatibilityMutating||busy||sessionAction)return;
 if(changed||!spellbookCompatibilityLoadedAt||Date.now()-spellbookCompatibilityLoadedAt>30000)loadSpellbookCompatibility().catch(()=>{});
}
async function changeSpellbookCompatibility(restore=false){
 if(spellbookCompatibilityBlocked(true))throw Error('Open the Custom runtime, stop the server and client and finish other operations before changing its executable.');
 const data=spellbookCompatibilityData,operation=restore?'client_spellbook_restore':'client_spellbook_apply';
 if((restore?data?.can_restore:data?.can_apply)!==true)throw Error('Check client compatibility again before changing the executable.');
 const prompt=restore?'Restore the protected pre-patch executable? A server using the 1,440-slot spellbook may freeze this client when entering the world until you apply the patch again.':'Apply the 1,440-slot spellbook and 4 GB address patches to this Custom client? The current executable is backed up first. You must also compile and deploy dinput8.dll from the selected source before entering the world.';
 if(!window.confirm(prompt)){spellbookCompatibilityFeedback='Executable change cancelled. No client files were changed.';renderSpellbookCompatibilityControls();notice(spellbookCompatibilityFeedback);return;}
 const profile=activeProfile,generation=++spellbookCompatibilityGeneration;spellbookCompatibilityFeedback='';spellbookCompatibilityMutating=true;renderSpellbookCompatibilityControls();
 try{
  const result=await job(operation,{revision:data.revision,...(restore?{confirm_restore:true}:{confirm_apply:true})});
  if(profile!==activeProfile||generation!==spellbookCompatibilityGeneration)return;
  if(result?.profile!==profile)throw Error('The operation returned another world. Check client compatibility again.');
  showSpellbookCompatibility({...data,...result,dll:result.dll||data.dll,requirements:result.requirements||data.requirements});notice(result.message||(restore?'Protected executable restored.':'1,440-slot executable patch verified. Compile and deploy the current dinput8.dll next.'));
  // The status wrapper also checks DLL provenance; mutation results may contain
  // only the executable state. Refresh through that wrapper after the job.
  spellbookCompatibilityLoadedAt=0;
 }catch(e){
  if(profile===activeProfile&&generation===spellbookCompatibilityGeneration){spellbookCompatibilityError=e.message;spellbookCompatibilityLoadedAt=0;}
  throw e;
 }finally{
  if(profile===activeProfile&&generation===spellbookCompatibilityGeneration){spellbookCompatibilityMutating=false;renderSpellbookCompatibilityControls();}
 }
}
action('client-spellbook-check',loadSpellbookCompatibility);
action('client-spellbook-apply',()=>changeSpellbookCompatibility());
action('client-spellbook-restore',()=>changeSpellbookCompatibility(true));
action('client-spellbook-compiler',()=>{
 tab('client');$('dll-panel').open=true;$('dll-panel').scrollIntoView({behavior:'smooth',block:'center'});$('dll-status').focus();
 if(lastNative?.alive&&typeof dllStatus==='function')return dllStatus();
});
renderSpellbookCompatibilityControls();
