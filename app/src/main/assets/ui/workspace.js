'use strict';
let addonComparison=null,playerPreview=null;
function addonControls(){
 $('players-restore').disabled=!!(busy||!playerPreview?.compatible||!$('players-replace').checked);
 for(const id of ['addons-missing','addons-all'])$(id).disabled=!!(busy||clientFileBusy||!addonComparison);
 $('dll-deploy').disabled=!!(busy||clientFileBusy);
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
async function dllStatus(){const r=await api('client_dll_status');$('dll-state').textContent='Microsoft compiler '+(r.compiler?'imported':'required')+' · Wine runtime '+(r.runtime?'installed':'required')+' · x86 SDK '+(r.sdk?'imported':'required')+(r.build?'\nStaged DLL: '+bytes(r.build.bytes)+' · '+r.build.sha256:'\nNo staged DLL.');}
action('dll-status',dllStatus);
action('dll-tools',async()=>{await api('client_runtime_online');await dllStatus();});
action('dll-sdk',async()=>{const f=await api('pick',{kind:'file'});await job('client_dll_sdk',{file:f.file});await dllStatus();});
action('dll-build',async()=>{await api('controller_capture',{active:false});await api('client_start',{mode:'compiler',renderer:'software',resolution:'800x600',audio:false,runtime_mode:'compatibility'});notice('Compiling with Microsoft v142 in a separate Wine prefix. Check client-compiler.log in Logs. Stop client cancels.');await clientRuntimeState();});
action('dll-deploy',()=>job('client_dll_deploy'));
action('players-export',async()=>exportResult(await job('player_export')));
function showPlayers(r){playerPreview=r;$('players-replace').checked=false;$('players-restore').disabled=true;$('players-preview').textContent=r.accounts+' accounts · '+r.characters+' characters · '+r.tables+' tables\n'+r.message+'\n'+[...(r.problems||[]),...(r.changes||[])].join('\n')+'\nTables: '+r.table_names.join(', ');}
action('players-import',async()=>{playerPreview=null;$('players-restore').disabled=true;const f=await api('pick',{kind:'file'});showPlayers(await job('player_preview',{file:f.path||'incoming/'+f.file}));});
action('players-local',async()=>{const r=await api('files',{path:'backups'});$('players-select').replaceChildren();for(const f of r.items.filter(x=>/^players-.*\.zip$/.test(x.name))){const o=document.createElement('option');o.value=f.path;o.textContent=f.name+' · '+bytes(f.size);$('players-select').append(o);}if(!$('players-select').options.length)notice('No local player snapshots yet.');});
action('players-review',async()=>{playerPreview=null;$('players-restore').disabled=true;showPlayers(await job('player_preview',{file:$('players-select').value}));});
$('players-replace').addEventListener('change',()=>{$('players-restore').disabled=!($('players-replace').checked&&playerPreview?.compatible);});
action('players-restore',async()=>{if(!playerPreview?.compatible||!$('players-replace').checked)throw new Error('Review a compatible snapshot and select replacement first.');await job('player_restore',{file:playerPreview.file,sha256:playerPreview.sha256,replace:true});playerPreview=null;$('players-replace').checked=false;$('players-restore').disabled=true;});
