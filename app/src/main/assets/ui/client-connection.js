'use strict';
let clientConnectionData=null,clientConnectionProfile=null,clientConnectionGeneration=0;
let clientConnectionLoading=false,clientConnectionMutating=false,clientConnectionLoadedAt=0,clientConnectionError='';
let clientConnectionHostEdited=false,clientConnectionDraftRevision=null,clientConnectionObservedClient='';

function resetClientConnectionProfile(){
 if(clientConnectionProfile===activeProfile)return;
 clientConnectionProfile=activeProfile;clientConnectionGeneration++;clientConnectionData=null;
 clientConnectionLoading=false;clientConnectionMutating=false;clientConnectionLoadedAt=0;clientConnectionError='';
 clientConnectionHostEdited=false;clientConnectionDraftRevision=null;clientConnectionObservedClient='';
 $('client-host-address').value='127.0.0.1';
}
function clientConnectionContextReady(){
 return !!activeProfile&&lastNative?.profile===activeProfile&&!!lastNative.alive&&!lastNative.installing&&!lastNative.session_busy&&lastClientNative?.profile===activeProfile;
}
function clientConnectionBlocked(ownAction=false){
 return !!(busy>(ownAction?1:0)||sessionAction||clientConnectionLoading||clientConnectionMutating||clientConnectionError||!clientConnectionContextReady()||lastState?.profile!==activeProfile||lastClientNative.alive||lastClientNative.busy||lastState.jobs?.some(j=>['queued','running'].includes(j.status))||clientConnectionData?.profile!==activeProfile);
}
function renderClientConnectionControls(){
 resetClientConnectionProfile();const data=clientConnectionData,host=data?.host,patch=data?.patch,download=patch?.download,blocked=clientConnectionBlocked();
 $('client-host-address').disabled=blocked||host?.can_save!==true;
 $('client-host-local').disabled=blocked||host?.can_save!==true;
 $('client-host-save').disabled=blocked||host?.can_save!==true||!$('client-host-address').value.trim();
 $('client-host-restore').disabled=blocked||host?.can_restore!==true;
 $('client-connection-reload').disabled=!!(busy||sessionAction||clientConnectionLoading||clientConnectionMutating||!clientConnectionContextReady());
 $('client-4gb-panel').hidden=activeProfile!=='custom';
 $('client-4gb-apply').disabled=blocked||activeProfile!=='custom'||patch?.can_apply!==true;
 $('client-4gb-apply').textContent=patch?.patched?'Verify 4 GB patch':'Apply 4 GB patch';
 $('client-4gb-restore').disabled=blocked||activeProfile!=='custom'||patch?.can_restore!==true;
 $('client-4gb-download').disabled=blocked||activeProfile!=='custom'||download?.can_download!==true;
 if(!clientConnectionHostEdited)$('client-host-address').value=host?.host||'127.0.0.1';
 $('client-host-ports').textContent=host?.port!=null?'Existing port'+(String(host.port).includes(',')?'s':'')+': '+host.port+' · retained when the IP changes.':'Existing port is retained when the IP changes.';
 const context=!activeProfile?'Checking this world…':!lastNative?.alive?'Open this world’s server runtime to inspect or change client files.':lastNative.session_busy||sessionAction?'Wait for the current file transfer to finish.':lastNative.installing?'Wait for runtime installation to finish.':!clientConnectionContextReady()?'Waiting for this world’s client status…':clientConnectionLoading?'Checking this world’s client files…':clientConnectionMutating?'Saving this world’s client files…':lastClientNative?.alive||lastClientNative?.busy?'Stop the client before changing or verifying its files.':busy||lastState?.jobs?.some(j=>['queued','running'].includes(j.status))?'Wait for the current operation to finish.':clientConnectionError;
 const draftChanged=clientConnectionHostEdited&&host&&clientConnectionDraftRevision!==host.revision;
 $('client-host-status').textContent=context||host?.warning||(draftChanged?'eqhost.txt changed while you were editing. Reload client files, then enter your IP again.':host?((host.exists?'Reading '+(host.path||'eqhost.txt')+'.':'No eqhost.txt exists yet. Save creates it with the local default port.')+' '+(host.backup_exists?'The original file is protected and available for Restore.':'The original file is protected on the first change.')+(clientConnectionHostEdited?' IP edit has not been saved.':'')):'Client files have not been checked.');
 $('client-4gb-status').textContent=context||patch?.warning||(patch?(patch.patched?'4 GB address support is already enabled for '+patch.exe+'.':patch.eligible?'4 GB address support is off for '+patch.exe+'.':'Import the Custom client to inspect its executable.')+(patch.backup_exists?' A protected original is available for Restore.':''):'Client executable has not been checked.');
 $('client-4gb-download-status').textContent=context||download?.warning||(download?.downloaded?'NTCore 4 GB Patch is saved at '+download.path+'. Open it from the Wine desktop when needed.':download?.can_download?'Download the official NTCore utility to '+download.path+'. Downloading leaves '+patch.exe+' unchanged.':patch?.warning||'Import the Custom client to download the official tool into its folder.');
 if(draftChanged)$('client-host-save').disabled=true;
}
function showClientConnection(data){
 if(data?.profile!==activeProfile)return false;
 clientConnectionData=data;clientConnectionLoadedAt=Date.now();clientConnectionError='';
 renderClientConnectionControls();return true;
}
async function loadClientConnection(discardEdits=false){
 resetClientConnectionProfile();if(!clientConnectionContextReady()||clientConnectionLoading||clientConnectionMutating){renderClientConnectionControls();return;}
 if(discardEdits){clientConnectionHostEdited=false;clientConnectionDraftRevision=null;}
 const profile=activeProfile,generation=++clientConnectionGeneration;clientConnectionLoading=true;renderClientConnectionControls();
 try{
  const data=await api('client_connection_status',{},10000);
  if(generation!==clientConnectionGeneration||profile!==activeProfile)return;
  if(data?.profile!==profile)throw Error('The client-file status belongs to another world. Reload client files.');
  showClientConnection(data);
 }catch(e){
  if(generation===clientConnectionGeneration&&profile===activeProfile){clientConnectionError=e.message;clientConnectionLoadedAt=Date.now();}
  throw e;
 }finally{
  if(generation===clientConnectionGeneration&&profile===activeProfile){clientConnectionLoading=false;renderClientConnectionControls();}
 }
}
// The poll hook checks imported-client changes and the transition back from a file
// operation. A refresh never discards an unsaved IP or advances its file revision.
function checkClientConnectionStatus(){
 resetClientConnectionProfile();renderClientConnectionControls();
 const client=lastState?.client,signature=JSON.stringify([activeProfile,client?.imported,client?.files,client?.bytes,lastClientNative?.alive,!!busy]);
 const changed=clientConnectionObservedClient!==signature;clientConnectionObservedClient=signature;
 if(!clientConnectionContextReady()||clientConnectionLoading||clientConnectionMutating||busy||sessionAction)return;
 if(changed||!clientConnectionLoadedAt||Date.now()-clientConnectionLoadedAt>15000)loadClientConnection().catch(()=>{});
}
async function changeClientConnection(operation,section,args={}){
 if(clientConnectionBlocked(true))throw Error('Open this world’s runtime, stop the client and finish other operations before changing client files.');
 const data=clientConnectionData?.[section],profile=activeProfile;
 const restoring=operation.endsWith('_restore');
 const allowed=operation==='client_4gb_download'?data?.download?.can_download:restoring?data?.can_restore:section==='host'?data?.can_save:data?.can_apply;
 if(allowed!==true)throw Error('Reload client files before making this change.');
 const revision=section==='host'&&!restoring&&clientConnectionHostEdited?clientConnectionDraftRevision:data.revision;
 if(revision!==data.revision)throw Error('eqhost.txt changed while you were editing. Reload client files, then enter your IP again.');
 const generation=++clientConnectionGeneration;clientConnectionMutating=true;renderClientConnectionControls();
 try{
  const result=await job(operation,{...args,revision});
  if(generation!==clientConnectionGeneration||profile!==activeProfile)return;
  if(result?.profile!==profile)throw Error('The operation returned a different world. Reload client files.');
  if(section==='host'){clientConnectionHostEdited=false;clientConnectionDraftRevision=null;}
  showClientConnection(result);
  notice(result.message||'Client file saved.');
 }catch(e){
  if(generation===clientConnectionGeneration&&profile===activeProfile){clientConnectionError=e.message;clientConnectionLoadedAt=0;}
  throw e;
 }finally{
  if(generation===clientConnectionGeneration&&profile===activeProfile){clientConnectionMutating=false;renderClientConnectionControls();}
 }
}
function editClientHost(){
 if(!clientConnectionHostEdited)clientConnectionDraftRevision=clientConnectionData?.host?.revision;
 clientConnectionHostEdited=true;renderClientConnectionControls();
}
$('client-host-address').addEventListener('input',editClientHost);
action('client-connection-reload',()=>loadClientConnection(true));
action('client-host-local',()=>{$('client-host-address').value='127.0.0.1';editClientHost();});
action('client-host-save',()=>changeClientConnection('client_host_save','host',{host:$('client-host-address').value.trim()}));
action('client-host-restore',()=>changeClientConnection('client_host_restore','host'));
action('client-4gb-apply',()=>changeClientConnection('client_4gb_apply','patch'));
action('client-4gb-restore',()=>changeClientConnection('client_4gb_restore','patch'));
action('client-4gb-download',()=>changeClientConnection('client_4gb_download','patch'));
renderClientConnectionControls();
