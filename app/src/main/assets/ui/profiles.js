'use strict';
const traditionalRepository='https://github.com/Russianranger/Server';
const traditionalRevision='4aceae18b94ffaafc08e2b17bc41cd72c77f795d';
function traditional(){return activeProfile==='traditional';}
function renderProfile(n){
 const profile=n.profile||'custom';
 if(activeProfile&&activeProfile!==profile){location.reload();return false;}
 if(!activeProfile){
  activeProfile=profile;document.body.dataset.profile=profile;$('runtime-heading-label').textContent=traditional()?'Traditional EQEmu runtime':'TRASC Custom runtime';$('world-profile').value=profile;
  document.querySelector('.eyebrow').textContent=traditional()?'TRADITIONAL EQEMU · CLASSIC ADVENTURE':'TRIPTYCH · ANDROID';
  if(traditional()){
   $('source-url').value=traditionalRepository;$('source-ref').value=traditionalRevision;
   $('runtime-online').textContent='Download / refresh build runtime';
   $('build-jobs').value='1';
   for(const option of $('build-jobs').options){option.disabled=Number(option.value)>2;if(option.value==='2')option.textContent='2 · more memory required';}
   $('client-import-help').textContent='Import a separate, clean ROF2 client ZIP. Traditional uses Wine’s built-in DirectInput; your Custom client and DLL stay in their own profile.';
   $('source-import-help').textContent='Use the tested Russianranger/Server revision, then Import from GitHub. Build prepares a patched copy and fetches its pinned websocket headers. Your original source stays intact. Other revisions need qualification.';
   $('setup-finish-help').textContent='Refresh the Traditional build runtime, import the tested source, then compile and stage it in Builds. Database, maps and client imports can follow. Deployment and first login are the next milestone.';
   renderDatabaseSelection();
  }
 }
 syncProfileControls();return true;
}
function syncProfileControls(){
 const blocked=!lastNative||!lastClientNative||!!(busy||sessionAction||lastNative.alive||lastNative.installing||lastNative.session_busy||lastClientNative.alive||lastClientNative.busy);
 $('world-profile').disabled=blocked;$('switch-profile').disabled=blocked||$('world-profile').value===activeProfile;
 $('profile-status').textContent=blocked?'Stop the client and server runtime, then finish transfers to switch.':'Each world keeps its own database, files, client and backups. Switching discards unsaved form edits.';
 if(traditional()){
  for(const id of ['start-server','restart-server','deploy-build','rollback-build','export-client','spire-export','client-prepare'])$(id).disabled=true;
  const activeJob=lastState?.jobs?.some(j=>['queued','running'].includes(j.status));
  $('build-server').disabled=!!(busy||sessionAction||!lastNative?.alive||lastNative?.installing||lastNative?.session_busy||!lastClientNative||lastClientNative.alive||lastClientNative.busy||activeJob||lastState?.profile!=='traditional'||!lastState?.traditional?.build?.build_allowed);
  $('traditional-tested-source').disabled=!!(busy||sessionAction||lastNative?.installing||lastNative?.session_busy||activeJob);
  for(const id of ['client-native-dll','client-fast-spells','client-load-pauses','client-mouse-warp']){$(id).checked=false;$(id).disabled=true;}
  for(const id of ['client-boats','client-particles']){$(id).value='off';$(id).disabled=true;}
 }
 const contentBlocked=!!(busy||!lastNative?.alive||lastState?.running||lastState?.jobs?.some(j=>['queued','running'].includes(j.status)));
 for(const id of ['content-git','content-zip'])$(id).disabled=contentBlocked;
 renderTraditionalStatus();
}
function renderTraditionalStatus(){
 if(!traditional())return;
 const s=lastState,components=s?.traditional?.components||{},build=s?.traditional?.build;
 const entries=[['Server runtime',build?.runtime_ready?'Build tools ready':lastNative?.installed?'Installed · check build tools':'Install in this profile'],['Server source',build?.source_supported?'Supported revision':s?.source?'Imported · not qualified':'Import required'],['Compiled binaries',build?.staged_valid?'Nine binaries staged':build?.staged_message||'Build required'],['PEQ database',s?.database_imported?'Imported':'Import required'],['Server maps',s?.maps_ready?'Present':'Import required']];
 for(const [key,name]of Object.entries({quests:'Quests',plugins:'Perl plugins',lua_modules:'Lua modules',assets:'Server assets'})){
  const c=components[key];entries.push([name,c?.imported?'Imported · '+c.source.files+' files'+(c.source.commit?' · '+c.source.commit.slice(0,10):''):'Import required']);
 }
 entries.push(['ROF2 client',s?.client?.imported?'Imported separately':'Import in Client'],['Client runtime',lastClientNative?.installed?'Installed':'Install in Client'],['Deployment & first login','Next milestone']);
 $('traditional-checklist').replaceChildren(...entries.map(([name,state])=>{const row=document.createElement('tr');for(const text of [name,state]){const cell=document.createElement('td');cell.textContent=text;row.append(cell);}return row;}));
 const message=!build?.runtime_ready?build?.runtime_message:!build?.source_supported?build?.source_message:!build?.build_allowed?build?.runtime_message:'Ready to compile and stage. Content imports and a playable world are separate checks.';
 $('traditional-checklist-note').textContent=lastNative?.alive?message||'Checking build readiness.':'Open this profile’s runtime to inspect build readiness and imported content.';
 $('traditional-build-readiness').textContent=lastNative?.alive?message||'Checking build readiness.':'Install or refresh the Traditional build runtime, then open it.';
}
action('traditional-tested-source',async()=>{$('source-url').value=traditionalRepository;$('source-ref').value=traditionalRevision;notice('Tested source selected. Choose Import from GitHub to download it.');});
$('world-profile').addEventListener('change',syncProfileControls);
action('switch-profile',async()=>{await api('profile_switch',{profile:$('world-profile').value});location.reload();});
function contentChoice(){const kind=$('content-kind').value;$('content-url').value=kind==='assets'?'':'https://github.com/ProjectEQ/projecteqquests';$('content-ref').value=kind==='assets'?'':'master';$('replace-content').checked=false;}
$('content-kind').addEventListener('change',contentChoice);contentChoice();
function contentArgs(){return {kind:$('content-kind').value,replace:$('replace-content').checked};}
action('content-git',async()=>{if(!$('content-url').value.trim())throw Error('Enter the component’s GitHub repository.');const result=await job('import_content',{...contentArgs(),url:$('content-url').value.trim(),ref:$('content-ref').value.trim()});$('content-result').textContent=result.message+(result.backup?' Previous component: '+result.backup:'');$('replace-content').checked=false;});
action('content-zip',async()=>{const args=contentArgs(),f=await api('pick',{kind:'content'});const result=await job('import_content',{...args,file:f.file});$('content-result').textContent=result.message+(result.backup?' Previous component: '+result.backup:'');$('replace-content').checked=false;});
let seedSelections=[];
function renderSeedBundle(){const selected=selectedDatabaseCandidate(),blocked=!!(busy||databaseScanning||sessionAction);$('seed-bundle').textContent=seedSelections.length?seedSelections.map((s,i)=>(i+1)+'. '+s).join('\n'):'No bundle files selected. A complete PEQ ZIP uses Import complete PEQ database.';$('seed-add').disabled=blocked||!selected||['peq_bundle','unsupported_bundle'].includes(selected.kind);$('seed-import').disabled=blocked||!seedSelections.length;}
function clearSeedBundle(){seedSelections=[];renderSeedBundle();}
action('seed-add',async()=>{const selected=selectedDatabaseCandidate();if(!selected||['peq_bundle','unsupported_bundle'].includes(selected.kind))throw Error('Show individual SQL files and choose one first.');const selection=selected.id;if(!seedSelections.includes(selection))seedSelections.push(selection);renderSeedBundle();});
action('seed-clear',async()=>clearSeedBundle());
action('seed-import',async()=>{if(!seedSelections.length)throw Error('Add the seed files in their required order first.');await job('import_database',{selection:seedSelections[0],selections:seedSelections,replace:$('replace-db').checked});seedSelections=[];renderSeedBundle();});
// Retain every tab, while keeping fork-specific repairs out of the clean world.
for(const id of ['ferry-service-panel','boat-trial-panel','spell-fix-panel','addon-panel','dll-panel'])if($(id))$(id).dataset.customOnly='';
$('fix-nektulos').closest('article').dataset.customOnly='';
for(const id of ['client-native-dll','client-fast-spells','client-load-pauses','client-mouse-warp'])$(id).closest('label').dataset.customOnly='';
for(const id of ['client-boats','client-particles'])$(id).closest('.option-field').dataset.customOnly='';
