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
   $('setup-finish-help').textContent='Import the database, maps, quests and server assets, then deploy your staged build in Builds. Import a separate RoF2 client, prepare it and start the server.';
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
  const deployment=lastState?.traditional?.deployment;
  const serverBlocked=!!(busy||sessionAction||!lastNative?.alive||lastNative?.installing||lastNative?.session_busy||lastState?.profile!=='traditional'||lastState?.jobs?.some(j=>['queued','running'].includes(j.status)));
  const clientBlocked=!!(serverBlocked||!lastClientNative||lastClientNative.alive||lastClientNative.busy);
  $('deploy-build').disabled=clientBlocked||!!lastState?.running||!deployment?.deploy_allowed;
  $('rollback-build').disabled=clientBlocked||!!lastState?.running||!deployment?.rollback_allowed;
  $('start-server').disabled=serverBlocked||!!lastState?.running||!deployment?.start_allowed;
  $('restart-server').disabled=serverBlocked||!lastState?.running||!deployment?.start_allowed;
  for(const id of ['export-client','spire-export'])$(id).disabled=clientBlocked||!deployment?.client_data_allowed;
  $('client-prepare').disabled=clientBlocked||!lastState?.client?.imported||!deployment?.client_data_allowed;
  $('client-import').disabled=clientBlocked;
  const activeJob=lastState?.jobs?.some(j=>['queued','running'].includes(j.status));
  $('build-server').disabled=!!(busy||sessionAction||!lastNative?.alive||lastNative?.installing||lastNative?.session_busy||!lastClientNative||lastClientNative.alive||lastClientNative.busy||activeJob||lastState?.profile!=='traditional'||!lastState?.traditional?.build?.build_allowed);
  $('traditional-tested-source').disabled=!!(busy||sessionAction||lastNative?.installing||lastNative?.session_busy||activeJob);
  for(const id of ['client-native-dll','client-fast-spells','client-load-pauses','client-mouse-warp']){$(id).checked=false;$(id).disabled=true;}
  for(const id of ['client-boats','client-particles']){$(id).value='off';$(id).disabled=true;}
 }
 const contentBlocked=!!(busy||sessionAction||!lastNative?.alive||lastNative?.installing||lastNative?.session_busy||lastState?.running||lastState?.jobs?.some(j=>['queued','running'].includes(j.status)));
 for(const id of ['content-git','content-zip',...Object.keys(contentComponents).flatMap(id=>[id+'-git',id+'-zip'])])$(id).disabled=contentBlocked;
 renderContentStatus();renderClientUi();renderTraditionalStatus();
}
function renderTraditionalStatus(){
 if(!traditional())return;
 const s=lastState,components=s?.traditional?.components||{},build=s?.traditional?.build;
 const entries=[['Server runtime',build?.runtime_ready?'Build tools ready':lastNative?.installed?'Installed · check build tools':'Install in this profile'],['Server source',build?.source_supported?'Supported revision':s?.source?'Imported · not qualified':'Import required'],['Compiled binaries',build?.staged_valid?'Nine binaries staged':s?.traditional?.deployment?.deployed_valid?'Nine binaries deployed':build?.staged_message||'Build required'],['PEQ database',s?.database_imported?'Imported':'Import required'],['Server maps',s?.maps_ready?'Present':'Import required']];
 for(const [key,name]of Object.entries({quests:'Quests',plugins:'Perl plugins',lua_modules:'Lua modules',assets:'Server assets'})){
  const c=components[key];entries.push([name,c?.imported?(c.origin==='quests'?'Detected in quests · ':'Present · ')+(c.files??c.source?.files??0)+' files'+(c.source?.commit?' · '+c.source.commit.slice(0,10):''):'Import required']);
 }
 entries.push(['ROF2 client',s?.client?.imported?'Imported separately':'Import in Client'],['Client runtime',lastClientNative?.installed?'Installed':'Install in Client'],['Deployment',s?.traditional?.deployment?.deployed_valid?'Build deployed':s?.traditional?.deployment?.message||'Deploy staged build'],['Local login',s?.traditional?.deployment?.start_allowed?'Ready to start':'Complete deployment prerequisites']);
 $('traditional-checklist').replaceChildren(...entries.map(([name,state])=>{const row=document.createElement('tr');for(const text of [name,state]){const cell=document.createElement('td');cell.textContent=text;row.append(cell);}return row;}));
 const message=!build?.runtime_ready?build?.runtime_message:!build?.source_supported?build?.source_message:!build?.build_allowed?build?.runtime_message:'Ready to compile and stage. Content imports and a playable world are separate checks.';
 $('traditional-checklist-note').textContent=lastNative?.alive?s?.traditional?.deployment?.message||message||'Checking readiness.':'Open this profile’s runtime to inspect build readiness and imported content.';
 $('traditional-build-readiness').textContent=lastNative?.alive?message||'Checking build readiness.':'Install or refresh the Traditional build runtime, then open it.';
}
action('traditional-tested-source',async()=>{$('source-url').value=traditionalRepository;$('source-ref').value=traditionalRevision;notice('Tested source selected. Choose Import from GitHub to download it.');});
$('world-profile').addEventListener('change',syncProfileControls);
action('switch-profile',async()=>{await api('profile_switch',{profile:$('world-profile').value});location.reload();});
const questContentRepository='https://github.com/ProjectEQ/projecteqquests';
const serverAssetsRepository='https://github.com/EQEmu/EQEmu';
const contentComponents={assets:{kind:'assets',name:'Server assets'}};
const questHelpers={plugins:'plugins','lua-modules':'lua_modules'};
const contentResults={};
function componentStateText(kind,name){
 const c=lastState?.traditional?.components?.[kind];
 if(c?.imported)return 'Imported · '+(c.source?.files??0)+' files'+(c.source?.commit?' · '+c.source.commit.slice(0,10):'')+'.'+(contentResults[kind]?.backup?' Previous folder: '+contentResults[kind].backup:'');
 if(!lastNative?.alive)return 'Open this profile’s runtime to import '+name+'.';
 return 'Ready to import '+name+'.'+(lastState?.running?' Stop the server first.':'');
}
function renderContentStatus(){
 for(const [id,{kind,name}]of Object.entries(contentComponents))$(id+'-result').textContent=componentStateText(kind,name);
 const components=lastState?.traditional?.components||{},quests=components.quests;
 for(const [id,kind]of Object.entries(questHelpers)){
  const c=components[kind],source=quests?.source;
  $(id+'-url').value=source?.repo||source?.url||source?.repository||(quests?.imported?'Imported quests ZIP':'');
  $(id+'-path').textContent='Folder: '+(c?.path||'server/quests/'+kind)+(c?.origin==='standalone'?' · retained separate import':'');
  $(id+'-result').textContent=!lastNative?.alive?'Open this profile’s runtime to detect this folder.':c?.imported?'Detected · '+(c.scripts??c.files??0)+' scripts'+(c.origin==='quests'?' in the imported quests tree.':'. Existing separate helpers remain available; a complete quests import uses its bundled helpers.')+(source?.commit?' Quest revision: '+source.commit.slice(0,10)+'.':''):c?.safe===false?'Folder contains a symbolic link and cannot be used. Reimport a complete quests archive.':c?.present?'Folder exists, but contains no usable scripts. Import the complete quests repository below.':'Folder missing. Import or update the complete quests repository below.';
 }
}
function contentChoice(){const kind=$('content-kind').value,name={quests:'quests',plugins:'Perl plugins',lua_modules:'Lua modules',assets:'server assets'}[kind];$('content-url').value=kind==='assets'?serverAssetsRepository:questContentRepository;$('content-ref').value=kind==='assets'?traditionalRevision:'';$('replace-content').checked=false;$('content-git').textContent='Download '+name;$('content-zip').textContent='Choose '+name+' ZIP';}
$('content-kind').addEventListener('change',contentChoice);contentChoice();
function contentArgs(){return {kind:$('content-kind').value,replace:$('replace-content').checked};}
function contentImported(kind,result,id){contentResults[kind]=result;$(id).textContent=result.message+(result.backup?' Previous component: '+result.backup:'');}
action('content-git',async()=>{if(!$('content-url').value.trim())throw Error('Enter the component’s GitHub repository.');const args=contentArgs(),result=await job('import_content',{...args,url:$('content-url').value.trim(),ref:$('content-ref').value.trim()});contentImported(args.kind,result,'content-result');$('replace-content').checked=false;});
action('content-zip',async()=>{const args=contentArgs(),f=await api('pick',{kind:'content'});const result=await job('import_content',{...args,file:f.file});contentImported(args.kind,result,'content-result');$('replace-content').checked=false;});
for(const [id,{kind}]of Object.entries(contentComponents)){
 action(id+'-git',async()=>{
  const url=$(id+'-url').value.trim();if(!url)throw Error('Enter the component’s GitHub repository.');
  const result=await job('import_content',{kind,url,ref:$(id+'-ref').value.trim(),replace:$(id+'-replace').checked});
  contentImported(kind,result,id+'-result');$(id+'-replace').checked=false;
 });
 action(id+'-zip',async()=>{
  const replace=$(id+'-replace').checked,f=await api('pick',{kind:'content'});
  const result=await job('import_content',{kind,file:f.file,replace});
  contentImported(kind,result,id+'-result');$(id+'-replace').checked=false;
 });
}
function renderClientUi(){
 const ui=lastState?.client?.ui,skins=ui?.skins||[];
 const clientStopped=!!lastClientNative&&!lastClientNative.alive&&!lastClientNative.busy;
 $('client-ui-import').disabled=!!(busy||sessionAction||!lastNative?.alive||lastNative?.installing||lastNative?.session_busy||!lastState?.client?.imported||!clientStopped||lastState?.jobs?.some(j=>['queued','running'].includes(j.status)));
 $('client-ui-skins').replaceChildren(...skins.map(s=>{const li=document.createElement('li'),name=document.createElement('strong'),command=document.createElement(/\s/.test(s.name)?'small':'code');name.textContent=s.name+(s.protected?' · built-in default':Number.isFinite(s.files)?' · '+s.files+' files':' · existing skin');command.textContent=/\s/.test(s.name)?'Select this skin in the game’s UI menu.':'/loadskin '+s.name+' 1';li.append(name,command);if(s.backup){const backup=document.createElement('small');backup.textContent='Previous skin: '+s.backup;li.append(backup);}return li;}));
 $('client-ui-status').textContent=!lastNative?.alive?'Open this profile’s server runtime to import UI skins.':!lastState?.client?.imported?'Import this profile’s RoF2 client first.':!clientStopped?'Stop the embedded client before importing UI skins.':ui?.message||(skins.length?'Installed skins are listed below. Load one inside the game.':'Choose a RoF2 UI ZIP to add a skin to this profile’s client.');
}
action('client-ui-import',async()=>{
 await api('controller_capture',{active:false});
 const f=await api('pick',{kind:'client_ui'}),args={file:f.path||f.file,replace:$('client-ui-replace').checked};
 if($('client-ui-name').value.trim())args.name=$('client-ui-name').value.trim();
 if(f.name)args.archive_name=f.name;
 const result=await job('import_client_ui',args);$('client-ui-replace').checked=false;
 $('client-ui-status').textContent=result.message+(result.activation_hint?' '+result.activation_hint:'');
});
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
