'use strict';
const traditionalRepository='https://github.com/Russianranger/Server';
const traditionalRevision='4aceae18b94ffaafc08e2b17bc41cd72c77f795d';
function traditional(){return activeProfile==='traditional';}
const takpRepository='https://github.com/Russianranger/Servertakp';
const takpRevision='25bf70acb6bd24853cf09e447ddd62b96a4491a4';
function takp(){return activeProfile==='takp';}
function renderProfile(n){
 const profile=n.profile||'custom';
 if(activeProfile&&activeProfile!==profile){if(typeof resetEraRules==='function')resetEraRules();resetClientUi();if(typeof resetBots==='function')resetBots();location.reload();return false;}
 if(!activeProfile){
  activeProfile=profile;document.body.dataset.profile=profile;$('runtime-heading-label').textContent=takp()?'TAKP server runtime':traditional()?'Traditional EQEmu runtime':'TRASC Custom runtime';$('world-profile').value=profile;
  document.querySelector('.eyebrow').textContent=takp()?'TAKP · AL’KABOR ADVENTURE':traditional()?'TRADITIONAL EQEMU · CLASSIC ADVENTURE':'TRIPTYCH · ANDROID';
  if(takp()){
   $('client-cpu-profile').querySelector('option[value="accurate"]').textContent='Legacy math accuracy (recommended for TAKP)';
   $('client-cpu-help').textContent='Legacy math accuracy restored visible TAKP NPC models in the Thor device test. It is the default for new TAKP launch settings; saved choices are retained. Brief visual glitches settled in that test. Relaunch after changing this option.';
   $('source-url').value=takpRepository;$('source-ref').value=takpRevision;
   $('maps-url').value='https://github.com/Russianranger/Mapstakp';$('maps-ref').value='95cb9322b853e7ec2f67158b87442286315042eb';
   $('runtime-online').textContent='Download / refresh TAKP build runtime';$('build-jobs').value='1';
   for(const option of $('build-jobs').options){option.disabled=Number(option.value)>2;if(option.value==='2')option.textContent='2 · more memory required';}
   $('login-endpoint-label').textContent='TAKP login endpoint · UDP';
   $('client-export-help').textContent='The TAKP server exports spells_us.txt and SkillCaps.txt. Prepare copies those exact files to your imported client root, with backups. The client’s supplied spells_en.txt is a separate file: it stays unchanged because the server validates its checksum at login.';
   $('client-export-files').replaceChildren(...['spells_us.txt','SkillCaps.txt'].map(name=>{const li=document.createElement('li');li.textContent=name;return li;}));
   $('client-preparation-help').textContent='Prepare exports and syncs spells_us.txt and SkillCaps.txt from the TAKP server while preserving the client’s original spells_en.txt for its login checksum. It also writes local eqhost.txt, installs the supplied client patches and applies display settings. Open the server runtime for Prepare and start the server before signing in. Android Back returns here while the client stays open. Saved controller bindings and the display Keyboard remain available. Wine prefix recovery preserves the previous prefix before opening a fresh desktop.';
   $('client-import-title').textContent='Import your TAKP client';$('client-launch-label').textContent='TAKP';
   $('client-directx-help').textContent='Install Microsoft’s legacy DirectX helpers, including the 32-bit D3DX9_43 required by TAKP’s D3D8 wrapper. This downloads the official June 2010 redistributable.';
   $('client-native-models').closest('label').dataset.takpHide='';
   $('client-import-help').textContent='Choose a complete Windows TAKP client ZIP (TAKP 2.1 recommended), including eqgame.exe, eqmain.dll, eqgfx_dx8.dll and eqmac.exe. Prepare installs the supplied TAKP patches into this separate client.';
   $('setup-finish-help').textContent='Download the TAKP world files, initialize its fresh database and create a local account. Build and deploy in Builds, then import and prepare your separate TAKP client.';
   $('client-ui-help').textContent='Use the UI skins included with your TAKP client through the in-game UI menu or /loadskin. Launcher skin import and character layout activation support RoF2 clients.';
  }
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
 if(traditional()||takp()){
  const world=takp()?lastState?.takp:lastState?.traditional,deployment=world?.deployment;
  const serverBlocked=!!(busy||sessionAction||!lastNative?.alive||lastNative?.installing||lastNative?.session_busy||lastState?.profile!==activeProfile||lastState?.jobs?.some(j=>['queued','running'].includes(j.status)));
  const clientBlocked=!!(serverBlocked||!lastClientNative||lastClientNative.alive||lastClientNative.busy);
  $('deploy-build').disabled=clientBlocked||!!lastState?.running||!deployment?.deploy_allowed;
  $('rollback-build').disabled=clientBlocked||!!lastState?.running||!deployment?.rollback_allowed;
  $('start-server').disabled=serverBlocked||!!lastState?.running||!deployment?.start_allowed;
  $('restart-server').disabled=serverBlocked||!lastState?.running||!deployment?.start_allowed;
  for(const id of ['export-client','spire-export'])$(id).disabled=clientBlocked||!deployment?.client_data_allowed;
  $('client-prepare').disabled=clientBlocked||!lastState?.client?.imported||!deployment?.client_data_allowed;
  $('client-import').disabled=clientBlocked;
  const activeJob=lastState?.jobs?.some(j=>['queued','running'].includes(j.status));
  $('build-server').disabled=!!(busy||sessionAction||!lastNative?.alive||lastNative?.installing||lastNative?.session_busy||!lastClientNative||lastClientNative.alive||lastClientNative.busy||activeJob||lastState?.profile!==activeProfile||!world?.build?.build_allowed);
  $('traditional-tested-source').disabled=!!(busy||sessionAction||lastNative?.installing||lastNative?.session_busy||activeJob);
  for(const id of ['client-native-dll','client-fast-spells','client-load-pauses']){$(id).checked=false;$(id).disabled=true;}
  $('client-mouse-warp').disabled=takp()||!!(busy||sessionAction||!lastClientNative||lastClientNative.alive||lastClientNative.busy);
  $('client-camera-help').textContent=takp()?'Use Look on/off beside the gear in the TAKP display to toggle mouse look. The right stick and touch drags steer the camera while it is on. Toggle it off for pointer input; opening launcher controls also turns it off. Controller mappings offer Toggle mouse look.':'Traditional camera recentering uses a separate bundled adapter for the verified RoF2 client. Original DirectInput is restored when the client stops. Disable and relaunch to revert.';
  if(takp()){
   for(const id of ['client-mouse-warp','client-name-sky','client-native-models']){$(id).checked=false;$(id).disabled=true;}
   $('takp-setup').disabled=clientBlocked||!!lastState?.running||!!(world?.source_ready&&world?.quests_ready&&world?.maps_ready&&world?.components?.assets?.imported);
   $('takp-initialize').disabled=clientBlocked||!!lastState?.running||!world?.source_ready||!!world?.database_ready;
   $('takp-create-account').disabled=serverBlocked||!world?.database_ready;
  }
  for(const id of ['client-boats','client-particles']){$(id).value='off';$(id).disabled=true;}
 }
 const contentBlocked=!!(busy||sessionAction||!lastNative?.alive||lastNative?.installing||lastNative?.session_busy||lastState?.running||lastState?.jobs?.some(j=>['queued','running'].includes(j.status)));
 for(const id of ['content-git','content-zip',...Object.keys(contentComponents).flatMap(id=>[id+'-git',id+'-zip'])])$(id).disabled=contentBlocked;
 renderContentStatus();renderClientUi();renderTraditionalStatus();renderTakpStatus();
}
function renderTakpStatus(){
 if(!takp())return;
 const w=lastState?.takp||{},build=w.build||{},deployment=w.deployment||{};
 const entries=[['Server runtime',build.runtime_ready?'Build tools ready':lastNative?.installed?'Installed · open runtime':'Install in this profile'],['Server source + bots',w.source_ready?'Pinned fork ready':'Download world files'],['Quests',w.quests_ready?'Pinned fork ready':'Download world files'],['Maps',w.maps_ready?'Pinned fork ready':'Download world files'],['Al’Kabor database',w.database_ready?'Initialized':'Initialize fresh database'],['Playerbot schema',w.bot_schema_ready?'Eleven migrations verified':'Initialize fresh database'],['Local accounts',String(w.local_accounts||0)+' created'],['Compiled binaries',build.staged_valid?'Nine binaries staged':build.deployed_valid?'Nine binaries deployed':'Build required'],['Windows TAKP client',lastState?.client?.imported?'Imported separately':'Import in Client'],['Client runtime',lastClientNative?.installed?'Installed in this profile':'Install in Client'],['Local login · UDP 6000',deployment.start_allowed?'Ready to start':'Complete setup and deployment']];
 $('takp-checklist').replaceChildren(...entries.map(([name,state])=>{const row=document.createElement('tr');for(const value of [name,state]){const cell=document.createElement('td');cell.textContent=value;row.append(cell);}return row;}));
 $('takp-status').textContent=lastNative?.alive?w.message||deployment.message||'Checking TAKP readiness.':'Install and open the TAKP server runtime to begin.';
 $('takp-build-readiness').textContent=lastNative?.alive?(build.build_allowed?'Ready to compile the pinned TAKP server with playerbots.':build.message||w.message||'Download world files and check build tools first.'):'Install and open the TAKP build runtime first.';
 if(!lastNative?.alive)for(const id of ['takp-setup','takp-initialize','takp-create-account'])$(id).disabled=true;
}
action('takp-setup',()=>job('takp_setup'));
action('takp-initialize',()=>job('takp_initialize_database'));
action('takp-create-account',async()=>{
 const username=$('takp-username').value.trim(),password=$('takp-password').value;
 if(!username||!password)throw Error('Enter a local TAKP username and password.');
 const pendingAccount=job('takp_create_account',{username,password});$('takp-password').value='';
 const result=await pendingAccount;notice(result.message||'Local TAKP account created.');
});
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
action('switch-profile',async()=>{await api('profile_switch',{profile:$('world-profile').value});if(typeof resetBots==='function')resetBots();location.reload();});
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
let clientUiProfile=null,clientUiGeneration=0,clientUiEditGeneration=0,clientUiResultMessage=null;
let clientUiSelection={skin:'',character_file:'',apply_layout:false};
function resetClientUi(){
 clientUiProfile=null;clientUiGeneration++;clientUiEditGeneration++;clientUiResultMessage=null;
 clientUiSelection={skin:'',character_file:'',apply_layout:false};
 for(const id of ['client-ui-skin','client-ui-character']){$(id).value='';$(id).disabled=true;}
 $('client-ui-layout').checked=false;$('client-ui-layout').disabled=true;
 $('client-ui-activate').disabled=$('client-ui-restore').disabled=true;
 $('client-ui-current').textContent='';$('client-ui-activation-status').textContent='Checking this world’s UI settings…';
}
function clientUiProfileMatches(){return !!activeProfile&&(lastNative?.profile||'custom')===activeProfile&&(lastState?.profile||'custom')===activeProfile&&(!lastClientNative?.profile||lastClientNative.profile===activeProfile);}
function clientUiData(){return clientUiProfileMatches()?lastState?.client?.ui:null;}
function clientUiBlocked(ownAction=false){return !!(busy>(ownAction?1:0)||sessionAction||!clientUiProfileMatches()||!lastNative?.alive||lastNative?.installing||lastNative?.session_busy||!lastState?.client?.imported||!lastClientNative||lastClientNative.alive||lastClientNative.busy||lastState?.jobs?.some(j=>['queued','running'].includes(j.status)));}
function clientUiCharacter(){return clientUiData()?.characters?.find(c=>c.file===clientUiSelection.character_file);}
function clientUiOptions(id,entries,empty){
 const select=$(id),signature=JSON.stringify(entries);
 if(select.dataset.options!==signature){select.replaceChildren(...(entries.length?entries:[['',empty]]).map(([value,text])=>{const option=document.createElement('option');option.value=value;option.textContent=text;return option;}));select.dataset.options=signature;}
}
function renderClientUi(){
 if(clientUiProfile!==activeProfile){resetClientUi();clientUiProfile=activeProfile;}
 const ui=clientUiData(),skins=ui?.skins||[],characters=ui?.characters||[],characterErrors=ui?.character_errors?.length||0,blocked=clientUiBlocked();
 $('client-ui-import').disabled=blocked||takp();
 if(takp()){
  for(const id of ['client-ui-skin','client-ui-character','client-ui-layout','client-ui-activate','client-ui-restore'])$(id).disabled=true;
  $('client-ui-skins').replaceChildren();$('client-ui-current').textContent='';
  $('client-ui-status').textContent='Use the skins bundled with your TAKP client in the game’s UI menu or with /loadskin.';
  $('client-ui-activation-status').textContent='RoF2 UI import and saved character layout activation are unavailable for TAKP.';
  return;
 }
 $('client-ui-skins').replaceChildren(...skins.map(s=>{const li=document.createElement('li'),name=document.createElement('strong'),command=document.createElement(/\s/.test(s.name)?'small':'code');name.textContent=s.name+(s.protected?' · built-in default':Number.isFinite(s.files)?' · '+s.files+' files':' · existing skin');command.textContent=/\s/.test(s.name)?'Select this skin in the game’s UI menu.':'/loadskin '+s.name+' 0 · use the skin’s XML layout\n/loadskin '+s.name+' 1 · keep saved window positions';li.append(name,command);if(s.backup){const backup=document.createElement('small');backup.textContent='Previous skin: '+s.backup;li.append(backup);}return li;}));
 $('client-ui-status').textContent=!lastNative?.alive?'Open this profile’s server runtime to import UI skins.':!lastState?.client?.imported?'Import this profile’s RoF2 client first.':lastClientNative?.alive||lastClientNative?.busy?'Stop the embedded client before importing UI skins.':ui?.message||(skins.length?'Installed skins are listed below.':'Choose a RoF2 UI ZIP to add a skin to this profile’s client.');
 if(ui&&!characters.some(c=>c.file===clientUiSelection.character_file)){clientUiSelection.character_file=characters[0]?.file||'';clientUiSelection.apply_layout=false;clientUiEditGeneration++;clientUiResultMessage=null;}
 const character=clientUiCharacter();
 if(ui&&!skins.some(s=>s.name===clientUiSelection.skin)){clientUiSelection.skin=skins.find(s=>s.name.toLowerCase()===(character?.skin||'').toLowerCase())?.name||skins[0]?.name||'';clientUiEditGeneration++;clientUiResultMessage=null;}
 const layoutAvailable=!!character?.layout_skins?.includes(clientUiSelection.skin);
 if(!layoutAvailable)clientUiSelection.apply_layout=false;
 clientUiOptions('client-ui-skin',skins.map(s=>[s.name,s.name+(s.protected?' · built-in default':'')]),'No UI skins installed');
 clientUiOptions('client-ui-character',characters.map(c=>[c.file,c.file]),'No character settings found');
 $('client-ui-skin').value=clientUiSelection.skin;$('client-ui-character').value=clientUiSelection.character_file;
 $('client-ui-skin').disabled=blocked||!skins.length||!character;$('client-ui-character').disabled=blocked||!characters.length;
 $('client-ui-layout').checked=clientUiSelection.apply_layout;$('client-ui-layout').disabled=blocked||!layoutAvailable;
 $('client-ui-current').textContent=character?character.file+' · Saved skin for next launch: '+(character.skin||'Default')+'.'+(character.previous_settings?.backup?' Previous settings: '+character.previous_settings.backup+'.':''):'';
 const characterAttention=characterErrors+' character settings '+(characterErrors===1?'file needs':'files need')+' attention. Check diagnostic logs or restore a known good file.';
 $('client-ui-layout-help').textContent=layoutAvailable?'An included layout matches '+character.file+' and '+clientUiSelection.skin+'. Applying it is optional.':character?'No matching included layout is available for this character and skin.':characterErrors?characterAttention:'Enter the game once, then exit normally to create UI_<character>_<server>.ini.';
 $('client-ui-activate').disabled=blocked||!character?.revision||!clientUiSelection.skin||!skins.some(s=>s.name===clientUiSelection.skin);
 $('client-ui-restore').disabled=blocked||!character?.revision||!character.previous_settings?.id;
 let status=!clientUiProfileMatches()?'Checking this world’s UI settings…':!lastNative?.alive?'Open this profile’s server runtime to apply or restore UI settings.':!lastState?.client?.imported?'Import this profile’s RoF2 client first.':!lastClientNative||lastClientNative.alive||lastClientNative.busy?'Stop the embedded client before changing UI settings.':blocked?'Finish the current operation before changing UI settings.':!character?(characterErrors?characterAttention:'Enter the game once, then exit normally to create UI_<character>_<server>.ini.'):!character.revision?'Refresh character settings before changing the UI.':!skins.length?'Import a UI skin first.':'Apply the selected skin for the next launch. Your saved positions are kept unless you choose the included layout.';
 if(clientUiResultMessage&&clientUiResultMessage.profile===activeProfile&&!blocked)status=clientUiResultMessage.text;
 $('client-ui-activation-status').textContent=status;
}
function clientUiChoiceChanged(){clientUiEditGeneration++;clientUiResultMessage=null;renderClientUi();}
$('client-ui-skin').addEventListener('change',()=>{clientUiSelection.skin=$('client-ui-skin').value;clientUiSelection.apply_layout=false;clientUiChoiceChanged();});
$('client-ui-character').addEventListener('change',()=>{clientUiSelection.character_file=$('client-ui-character').value;clientUiSelection.apply_layout=false;clientUiChoiceChanged();});
$('client-ui-layout').addEventListener('change',()=>{clientUiSelection.apply_layout=$('client-ui-layout').checked;clientUiChoiceChanged();});
function clientUiContextCurrent(context){return context.profile===activeProfile&&context.generation===clientUiGeneration&&clientUiProfileMatches();}
async function clientUiJob(operation,args,context){
 const started=await api(operation,args);if(!clientUiContextCurrent(context))return null;
 notice(operation==='restore_client_ui'?'Restoring previous UI settings…':'Applying client UI skin…');
 for(;;){
  await new Promise(resolve=>setTimeout(resolve,1400));if(!clientUiContextCurrent(context))return null;
  const state=await api('state');if(!clientUiContextCurrent(context)||(state.profile||'custom')!==context.profile)return null;
  render(state);const item=state.jobs.find(j=>j.id===started.id);
  if(!item)throw Error('Operation status was lost. Check logs.');
  if(['error','cancelled'].includes(item.status))throw Error(item.error||'Operation cancelled.');
  if(item.status==='done'){const result=item.result||{};notice(result.message||'UI settings saved.');return result;}
 }
}
async function changeClientUi(restore=false){
 const character=clientUiCharacter(),skin=clientUiSelection.skin;
 if(clientUiBlocked(true)||!character?.revision)throw Error('Stop the client and finish other operations, then refresh this profile’s character settings.');
 if(restore&&!character.previous_settings?.id)throw Error('No previous UI settings backup is available for this character.');
 if(!restore&&!clientUiData()?.skins?.some(s=>s.name===skin))throw Error('Choose an installed UI skin.');
 if(!restore&&clientUiSelection.apply_layout&&!character.layout_skins?.includes(skin))throw Error('No matching included layout is available for this character and skin.');
 const context={profile:activeProfile,generation:++clientUiGeneration,edit:clientUiEditGeneration};
 const args=restore?{character_file:character.file,revision:character.revision,activation_id:character.previous_settings.id}:{skin,character_file:character.file,revision:character.revision,apply_layout:clientUiSelection.apply_layout};
 try{
  await api('controller_capture',{active:false});if(!clientUiContextCurrent(context))return;
  const result=await clientUiJob(restore?'restore_client_ui':'activate_client_ui',args,context);
  if(!result||!clientUiContextCurrent(context))return;
  if(result.ui)lastState.client={...lastState.client,ui:result.ui};
  if(context.edit===clientUiEditGeneration)clientUiResultMessage={profile:context.profile,text:(result.message||(restore?'Previous UI settings restored.':'Skin saved for the next launch.'))+' Character: '+(result.character_file||character.file)+'. Skin: '+(result.skin||skin)+'.'+(!restore?' Included layout: '+(result.layout_applied?'applied':'not applied')+'.':'')+(result.backup?' Backup: '+result.backup+'.':'')};
  renderClientUi();
 }catch(error){if(clientUiContextCurrent(context))throw error;}
}
action('client-ui-activate',()=>changeClientUi());
action('client-ui-restore',()=>changeClientUi(true));
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
for(const id of ['client-native-dll','client-fast-spells','client-load-pauses'])$(id).closest('label').dataset.customOnly='';
for(const id of ['client-boats','client-particles'])$(id).closest('.option-field').dataset.customOnly='';
