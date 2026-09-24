'use strict';
let addonComparison=null,playerPreview=null;
function addonControls(){
 $('players-restore').disabled=!!(busy||!playerPreview?.compatible||!$('players-replace').checked);
 for(const id of ['addons-missing','addons-all'])$(id).disabled=!!(busy||clientFileBusy||!addonComparison);
 dllControls();
 for(const b of document.querySelectorAll('#addons-list button[data-copy]'))b.disabled=!!(busy||clientFileBusy);
}
function renderAddons(data){
 addonComparison=data;$('addons-status').textContent=data.counts.missing+' missing · '+data.counts.different+' different · '+data.counts.same+' matching';
 $('addons-list').replaceChildren();
 for(const item of data.entries){
  const row=document.createElement('tr'),name=document.createElement('td'),state=document.createElement('td'),buttons=document.createElement('td');
  name.textContent=item.path;state.textContent=item.status+(item.protected?' · managed':item.locked?' · locked':'');
  if(!item.protected){
   const lock=document.createElement('button');lock.className='secondary';lock.textContent=item.locked?'Unlock':'Lock';
   lock.onclick=()=>addonAction(()=>job('client_addons_lock',{path:item.path,locked:!item.locked}).then(renderAddons));buttons.append(lock);
   if(item.status!=='same'&&!item.locked){const copy=document.createElement('button');copy.textContent='Copy';copy.dataset.copy='true';copy.onclick=()=>addonAction(()=>copyAddons('selected',[item.path]));buttons.append(copy);}
  }
  row.append(name,state,buttons);$('addons-list').append(row);
 }
 addonControls();
}
async function addonAction(fn){busy++;addonControls();try{await fn();}catch(e){notice(e.message,true);}finally{busy--;addonControls();}}
async function copyAddons(mode,paths=[]){if(!addonComparison)throw new Error('Compare files first.');const r=await job('client_addons_copy',{mode,paths,snapshot:addonComparison.snapshot});renderAddons(r.comparison);}
action('addons-scan',async()=>renderAddons(await job('client_addons_scan')));
action('addons-missing',()=>copyAddons('missing'));action('addons-all',()=>copyAddons('all'));
let dllCompilerState=null,sdkDownloadInfo=null,sdkSubmitting=false,sdkLastTerminal='';
function sdkDownloadActive(){return sdkSubmitting||!!lastState?.jobs?.some(j=>j.operation==='client_dll_download'&&['queued','running'].includes(j.status));}
function dllControls(){
 const downloading=sdkDownloadActive(),activeJob=lastState?.jobs?.some(j=>['queued','running'].includes(j.status));
 const blocked=!!(busy||clientFileBusy||downloading||activeJob||lastNative?.session_busy||lastNative?.installing);
 const workspaceUnavailable=!lastNative?.alive||!lastState;
 for(const id of ['dll-sdk-download','dll-sdk','dll-build','dll-deploy'])$(id).disabled=blocked||workspaceUnavailable||!!lastState?.running;
 $('dll-tools').disabled=blocked;
 $('dll-status').disabled=!!(busy||workspaceUnavailable);
 if(dllCompilerState&&(!dllCompilerState.compiler||!dllCompilerState.sdk||!dllCompilerState.runtime))$('dll-build').disabled=true;
 $('dll-sdk-confirm').disabled=blocked||workspaceUnavailable||!!lastState?.running||!sdkDownloadInfo||!$('dll-sdk-accept').checked;
 $('dll-sdk-accept').disabled=blocked;
 for(const id of ['session-import','session-export'])$(id).disabled=!!(busy||sessionAction||downloading||lastNative?.session_busy||lastNative?.installing);
 if(downloading)for(const id of ['client-launch','client-desktop','client-prefix-repair','client-runtime-online','client-runtime-offline','client-directx-online','client-directx-offline','client-import','client-prepare'])$(id).disabled=true;
}
function closeSdkConsent(){sdkDownloadInfo=null;$('dll-sdk-consent').hidden=true;$('dll-sdk-accept').checked=false;dllControls();}
function renderSdkDownload(state){
 const jobs=(state?.jobs||[]).filter(j=>j.operation==='client_dll_download');
 const current=jobs.find(j=>['queued','running'].includes(j.status));
 if(current){
  const progress=current.progress||{},bar=$('dll-sdk-progress-bar');
  $('dll-sdk-progress').textContent=progress.message||'Preparing Microsoft toolchain… Open Logs for details or use Cancel operation.';
  bar.hidden=false;
  if(Number(progress.total_bytes)>0){bar.max=Number(progress.total_bytes);bar.value=Math.min(Number(progress.downloaded_bytes)||0,bar.max);}
  else bar.removeAttribute('value');
  $('dll-sdk-consent').hidden=true;
 }else{
  $('dll-sdk-progress-bar').hidden=true;
  const terminal=jobs.at(-1);
  if(terminal&&terminal.id!==sdkLastTerminal){
   sdkLastTerminal=terminal.id;
   if(terminal.status==='done')$('dll-sdk-progress').textContent=terminal.result?.message||'Microsoft toolchain ready. Compile dinput8.dll when you are ready.';
   else if(['error','cancelled'].includes(terminal.status))$('dll-sdk-progress').textContent=terminal.error||'Toolchain download cancelled. The previously installed compiler was retained.';
   if(['done','error','cancelled'].includes(terminal.status))dllStatus().catch(()=>{});
  }
 }
 dllControls();
}
async function dllStatus(){
 const r=await api('client_dll_status');dllCompilerState=r;
 $('dll-state').textContent='Microsoft compiler '+(r.compiler?'imported':'required')+' · Wine runtime '+(r.runtime?'installed':'required')+' · x86 SDK '+(r.sdk?'imported':'required')+(r.build?'\nStaged DLL: '+bytes(r.build.bytes)+' · '+r.build.sha256:'\nNo staged DLL.');
 dllControls();return r;
}
action('dll-status',dllStatus);
action('dll-tools',async()=>{await api('client_runtime_online');await dllStatus();});
action('dll-sdk',async()=>{closeSdkConsent();const f=await api('pick',{kind:'file'});await job('client_dll_sdk',{file:f.file});await dllStatus();});
action('dll-sdk-download',async()=>{
 closeSdkConsent();$('dll-sdk-progress').textContent='Checking Microsoft’s download catalog and available space…';
 try{
  const info=await api('client_dll_download_info');
  if(!info.token||!info.license_url)throw Error('Microsoft license details are unavailable. Try again or import a prepared toolchain ZIP.');
  sdkDownloadInfo=info;
  $('dll-sdk-download-details').textContent=info.toolset+' · '+info.sdk+'. Download '+bytes(info.download_bytes)+'; allow '+bytes(info.required_free_bytes)+' free during preparation ('+bytes(info.free_bytes)+' available).'+(info.needs_msitools?' The app will also prepare its archive extraction helper.':'');
  $('dll-sdk-license').textContent='Read '+(info.license_name||'Microsoft license');
  $('dll-sdk-license-url').textContent=info.license_url;
  $('dll-sdk-accept').checked=false;$('dll-sdk-consent').hidden=false;
  $('dll-sdk-progress').textContent=info.message||'Review the license and accept to download the compiler and SDK.';
 }catch(e){$('dll-sdk-progress').textContent=e.message;throw e;}
});
action('dll-sdk-license',async()=>{if(!sdkDownloadInfo)throw Error('Check the toolchain download details first.');await api('client_dll_license',{url:sdkDownloadInfo.license_url});});
$('dll-sdk-accept').addEventListener('change',dllControls);
$('dll-sdk-cancel').addEventListener('click',()=>{closeSdkConsent();$('dll-sdk-progress').textContent='Download cancelled before installation.';});
action('dll-sdk-confirm',async()=>{
 if(!sdkDownloadInfo||!$('dll-sdk-accept').checked)throw Error('Review and accept the Microsoft license before downloading.');
 const token=sdkDownloadInfo.token;sdkSubmitting=true;closeSdkConsent();renderSessionControls();
 $('dll-sdk-progress').textContent='Starting Microsoft toolchain download…';
 try{
  const result=await job('client_dll_download',{accepted:true,token});
  await dllStatus();$('dll-sdk-progress').textContent=result.message||'Microsoft toolchain ready. Choose Compile dinput8.dll when you are ready.';
 }catch(e){$('dll-sdk-progress').textContent=e.message;await dllStatus().catch(()=>{});throw e;}
 finally{sdkSubmitting=false;$('dll-sdk-progress-bar').hidden=true;dllControls();}
});
$('dll-panel').addEventListener('toggle',()=>{if($('dll-panel').open&&lastNative?.alive)dllStatus().catch(()=>{});});
action('dll-build',async()=>{await api('controller_capture',{active:false});await api('client_start',{mode:'compiler',renderer:'software',resolution:'800x600',audio:false,runtime_mode:'compatibility'});notice('Compiling with Microsoft v142 in a separate Wine prefix. Check client-compiler.log in Logs. Stop client cancels.');await clientRuntimeState();});
action('dll-deploy',()=>job('client_dll_deploy'));
action('players-export',async()=>exportResult(await job('player_export')));
function showPlayers(r){playerPreview=r;$('players-replace').checked=false;$('players-restore').disabled=true;$('players-preview').textContent=r.accounts+' accounts · '+r.characters+' characters · '+r.tables+' tables\n'+r.message+'\n'+[...(r.problems||[]),...(r.changes||[])].join('\n')+'\nTables: '+r.table_names.join(', ');}
action('players-import',async()=>{playerPreview=null;$('players-restore').disabled=true;const f=await api('pick',{kind:'file'});showPlayers(await job('player_preview',{file:f.path||'incoming/'+f.file}));});
action('players-local',async()=>{const r=await api('files',{path:'backups'});$('players-select').replaceChildren();for(const f of r.items.filter(x=>/^players-.*\.zip$/.test(x.name))){const o=document.createElement('option');o.value=f.path;o.textContent=f.name+' · '+bytes(f.size);$('players-select').append(o);}if(!$('players-select').options.length)notice('No local player snapshots yet.');});
action('players-review',async()=>{playerPreview=null;$('players-restore').disabled=true;showPlayers(await job('player_preview',{file:$('players-select').value}));});
$('players-replace').addEventListener('change',()=>{$('players-restore').disabled=!($('players-replace').checked&&playerPreview?.compatible);});
action('players-restore',async()=>{if(!playerPreview?.compatible||!$('players-replace').checked)throw new Error('Review a compatible snapshot and select replacement first.');await job('player_restore',{file:playerPreview.file,sha256:playerPreview.sha256,replace:true});playerPreview=null;$('players-replace').checked=false;$('players-restore').disabled=true;});
