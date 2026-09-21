'use strict';
function traditional(){return activeProfile==='traditional';}
function renderProfile(n){
 const profile=n.profile||'custom';
 if(activeProfile&&activeProfile!==profile){location.reload();return false;}
 if(!activeProfile){
  activeProfile=profile;document.body.dataset.profile=profile;$('runtime-heading-label').textContent=traditional()?'Traditional EQEmu runtime':'TRASC Custom runtime';$('world-profile').value=profile;
  document.querySelector('.eyebrow').textContent=traditional()?'TRADITIONAL EQEMU · CLASSIC ADVENTURE':'TRIPTYCH · ANDROID';
  if(traditional()){
   $('source-url').value='https://github.com/EQEmu/EQEmu';$('source-ref').value='master';
   $('client-import-help').textContent='Import a separate, clean ROF2 client ZIP. Traditional uses Wine’s built-in DirectInput; your Custom client and DLL stay in their own profile.';
   $('source-import-help').textContent='Import your EQEmu fork or the upstream source. Add quests, plugins, Lua modules and assets separately below. GitHub imports record a commit; submodule hydration is part of the next compilation milestone.';
   $('setup-finish-help').textContent='Prepare this profile now. Building, deployment and starting its server become available after we adapt and verify your EQEmu fork for Android.';
   $('db-detail').textContent='Select a complete PEQ seed. For a split distribution, add the world, player/system and local-login SQL files in their required order, then import the bundle once.';
  }
 }
 syncProfileControls();return true;
}
function syncProfileControls(){
 const blocked=!lastNative||!lastClientNative||!!(busy||sessionAction||lastNative.alive||lastNative.installing||lastNative.session_busy||lastClientNative.alive||lastClientNative.busy);
 $('world-profile').disabled=blocked;$('switch-profile').disabled=blocked||$('world-profile').value===activeProfile;
 $('profile-status').textContent=blocked?'Stop the client and server runtime, then finish transfers to switch.':'Each world keeps its own database, files, client and backups. Switching discards unsaved form edits.';
 if(traditional()){
  for(const id of ['start-server','restart-server','build-server','deploy-build','rollback-build','export-client','spire-export','client-prepare'])$(id).disabled=true;
  for(const id of ['client-native-dll','client-fast-spells','client-load-pauses','client-mouse-warp']){$(id).checked=false;$(id).disabled=true;}
  for(const id of ['client-boats','client-particles']){$(id).value='off';$(id).disabled=true;}
 }
 const contentBlocked=!!(busy||!lastNative?.alive||lastState?.running||lastState?.jobs?.some(j=>['queued','running'].includes(j.status)));
 for(const id of ['content-git','content-zip'])$(id).disabled=contentBlocked;
 renderTraditionalStatus();
}
function renderTraditionalStatus(){
 if(!traditional())return;
 const s=lastState,components=s?.traditional?.components||{};
 const entries=[['Server runtime',lastNative?.installed?'Installed':'Install in this profile'],['Server source',s?.source?'Imported':'Import required'],['PEQ database',s?.database_imported?'Imported':'Import required'],['Server maps',s?.maps_ready?'Present':'Import required']];
 for(const [key,name]of Object.entries({quests:'Quests',plugins:'Perl plugins',lua_modules:'Lua modules',assets:'Server assets'})){
  const c=components[key];entries.push([name,c?.imported?'Imported · '+c.source.files+' files'+(c.source.commit?' · '+c.source.commit.slice(0,10):''):'Import required']);
 }
 entries.push(['ROF2 client',s?.client?.imported?'Imported separately':'Import in Client'],['Client runtime',lastClientNative?.installed?'Installed':'Install in Client'],['Android build & first login','Next milestone']);
 $('traditional-checklist').replaceChildren(...entries.map(([name,state])=>{const row=document.createElement('tr');for(const text of [name,state]){const cell=document.createElement('td');cell.textContent=text;row.append(cell);}return row;}));
 $('traditional-checklist-note').textContent=lastNative?.alive?'Imported indicates files are present; compatibility will be checked with the Android build.':'Start this profile’s server runtime to inspect its imported source and content.';
}
$('world-profile').addEventListener('change',syncProfileControls);
action('switch-profile',async()=>{await api('profile_switch',{profile:$('world-profile').value});location.reload();});
function contentChoice(){const kind=$('content-kind').value;$('content-url').value=kind==='assets'?'':'https://github.com/ProjectEQ/projecteqquests';$('content-ref').value=kind==='assets'?'':'master';$('replace-content').checked=false;}
$('content-kind').addEventListener('change',contentChoice);contentChoice();
function contentArgs(){return {kind:$('content-kind').value,replace:$('replace-content').checked};}
action('content-git',async()=>{if(!$('content-url').value.trim())throw Error('Enter the component’s GitHub repository.');const result=await job('import_content',{...contentArgs(),url:$('content-url').value.trim(),ref:$('content-ref').value.trim()});$('content-result').textContent=result.message+(result.backup?' Previous component: '+result.backup:'');$('replace-content').checked=false;});
action('content-zip',async()=>{const args=contentArgs(),f=await api('pick',{kind:'content'});const result=await job('import_content',{...args,file:f.file});$('content-result').textContent=result.message+(result.backup?' Previous component: '+result.backup:'');$('replace-content').checked=false;});
let seedSelections=[];
function renderSeedBundle(){$('seed-bundle').textContent=seedSelections.length?seedSelections.map((s,i)=>(i+1)+'. '+s).join('\n'):'No bundle files selected. A single full seed can use Import selected database.';}
action('seed-add',async()=>{const selection=$('db-candidate').value;if(!selection)throw Error('Scan or upload SQL files and choose one first.');if(!seedSelections.includes(selection))seedSelections.push(selection);renderSeedBundle();});
action('seed-clear',async()=>{seedSelections=[];renderSeedBundle();});
action('seed-import',async()=>{if(!seedSelections.length)throw Error('Add the seed files in their required order first.');await job('import_database',{selection:seedSelections[0],selections:seedSelections,replace:$('replace-db').checked});seedSelections=[];renderSeedBundle();});
// Retain every tab, while keeping fork-specific repairs out of the clean world.
for(const id of ['ferry-service-panel','boat-trial-panel','spell-fix-panel','addon-panel','dll-panel'])if($(id))$(id).dataset.customOnly='';
$('fix-nektulos').closest('article').dataset.customOnly='';
for(const id of ['client-native-dll','client-fast-spells','client-load-pauses','client-mouse-warp'])$(id).closest('label').dataset.customOnly='';
for(const id of ['client-boats','client-particles'])$(id).closest('.option-field').dataset.customOnly='';
