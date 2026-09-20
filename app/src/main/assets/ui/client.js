'use strict';
let controllerLoaded=false,controllerOptions=null,captureActive=false;
const clientPressed=new Set();let pointerX=450,pointerY=160,wheelTotal=0;
let clientFileBusy=false, spellComparison={}, clientImported=false;
function spellTestControls(){
 if(typeof gameSettingsControls==='function')gameSettingsControls();
 if(typeof addonControls==='function')addonControls();
 const active=!!spellComparison.state&&spellComparison.state!=='restored';
 const incomplete=active&&spellComparison.state!=='applied';
 $('spell-test-apply').disabled=!!(busy||clientFileBusy||active||!clientImported);
 $('spell-test-restore').disabled=!!(busy||clientFileBusy||!active);
 $('client-import').disabled=!!(busy||clientFileBusy||active);
 for(const id of ['client-prepare','export-client'])$(id).disabled=!!(busy||clientFileBusy||incomplete);
}
function renderClientStatus(client){
 clientImported=!!client?.imported;spellComparison=client?.spell_test||{};
 $('client-status').textContent=clientImported?client.files+' entries · '+bytes(client.bytes)+' extracted. '+(client.dinput8_present?'dinput8.dll is present.':'dinput8.dll was not found beside eqgame.exe.'):'No client imported.';
 $('spell-test-status').textContent=spellComparison.error|| (spellComparison.state==='applied'?
  'Compatibility on · '+(spellComparison.excluded_count??spellComparison.excluded_ids.length)+' IDs excluded · '+spellComparison.filtered_rows+' rows in each folder. Future exports stay filtered. Latest full table retained for Restore.':
  ['applying','restoring'].includes(spellComparison.state)?'File update incomplete. Use Restore full spell files before launching.':
  spellComparison.state==='restored'?'Full spell files restored and verified in both folders. Compatibility off.':'Compatibility off. Full exports include all spell IDs.');
 const excluded=spellComparison.excluded_spells||[];
 $('spell-excluded-list').textContent=spellComparison.state==='applied'?(excluded.length?excluded.map(s=>s.id+' — '+s.name).join('\n'):(spellComparison.excluded_ids||[]).join(', '))+(spellComparison.excluded_ids_truncated?'\nList limited to first 64; total shown above.':''):'';
 spellTestControls();
}
const sourceLabel=s=>({L1:'LB',R1:'RB',L2:'LT',R2:'RT',L3:'Left stick press',R3:'Right stick press'}[s]||s.replace(/([a-z])([A-Z])/g,'$1 $2'));
const layerTarget=a=>/^(HoldLayer|Layer)[1-6]$/.test(a)?Number(a.at(-1))-1:-1;
function readControllerEdits(){
 if(!controllerOptions)return;
 const target=controllerOptions.layers[Number($('controller-layer').value)];
 for(const source of controllerOptions.sources){const select=$('binding-'+source);if(select)target.bindings[source]=select.value;}
 controllerOptions.deadzone=Number($('controller-deadzone').value);controllerOptions.sensitivity=Number($('controller-speed').value);
}
function controllerFields(){
 const profile=controllerOptions,index=Number($('controller-layer').value),selected=profile.layers[index];if(!selected)return;
 $('controller-bindings').replaceChildren();$('controller-layer-name').value=selected.name;
 $('controller-add-layer').disabled=profile.layers.length>=6;$('controller-remove-layer').disabled=index===0;
 for(const source of profile.sources){const field=document.createElement('div'),label=document.createElement('label'),select=document.createElement('select');label.htmlFor='binding-'+source;label.textContent=sourceLabel(source);select.id='binding-'+source;
  for(const code of index>0?['Inherit',...profile.actions]:profile.actions){
   const target=layerTarget(code);if(target>=profile.layers.length)continue;
   const option=document.createElement('option');option.value=code;
   option.textContent=target>=0?(code.startsWith('Hold')?'Hold: ':'Go to: ')+profile.layers[target].name:code==='LayerNext'?'Next layer':code==='LayerPrevious'?'Previous layer':code.replace(/^Key/,'Key ').replace(/^Digit/,'Number ').replace(/([a-z])([A-Z])/g,'$1 $2');select.append(option);
  }
  select.value=selected.bindings[source];select.addEventListener('change',()=>{selected.bindings[source]=select.value;});field.append(label,select);$('controller-bindings').append(field);
 }
}
function controllerLayers(index=0){
 $('controller-layer').replaceChildren(...controllerOptions.layers.map((l,i)=>{const o=document.createElement('option');o.value=String(i);o.textContent=(i+1)+' · '+l.name;return o;}));
 $('controller-layer').value=String(Math.min(index,controllerOptions.layers.length-1));controllerFields();
}
function renderController(profile){
 controllerOptions=structuredClone(profile);controllerLoaded=true;
 $('controller-deadzone').value=profile.deadzone;$('controller-speed').value=profile.sensitivity;controllerLayers();
 if(profile.error)notice(profile.error,true);
}
async function loadController(force=false){if(controllerLoaded&&!force)return;renderController(await api('controller_state'));}
$('controller-layer').addEventListener('change',()=>controllerOptions&&controllerFields());
action('controller-load',()=>loadController(true));
action('controller-defaults',async()=>{
 await loadController();const preset=controllerOptions.presets?.[$('controller-preset').value];
 if(!preset)throw new Error('Preset unavailable. Reload bindings after updating the app.');
 renderController({...controllerOptions,...preset});notice('Preset filled in. Save bindings to keep it.');
});
action('controller-rename-layer',()=>{
 const index=Number($('controller-layer').value),name=$('controller-layer-name').value.trim();
 if(!name||name.length>24||/[\x00-\x1f\x7f]/.test(name)||controllerOptions.layers.some((l,i)=>i!==index&&l.name.toLowerCase()===name.toLowerCase()))throw new Error('Choose a unique layer name of 1–24 printable characters.');
 controllerOptions.layers[index].name=name;controllerLayers(index);
});
action('controller-add-layer',()=>{
 if(controllerOptions.layers.length>=6)throw new Error('Maximum 6 layers.');
 let n=controllerOptions.layers.length+1;while(controllerOptions.layers.some(l=>l.name.toLowerCase()==='layer '+n))n++;
 controllerOptions.layers.push({name:'Layer '+n,bindings:Object.fromEntries(controllerOptions.sources.map(s=>[s,'Inherit']))});controllerLayers(controllerOptions.layers.length-1);
});
action('controller-remove-layer',()=>{
 const index=Number($('controller-layer').value);if(index===0)throw new Error('Main provides inherited bindings and cannot be removed.');
 controllerOptions.layers.splice(index,1);
 for(const layer of controllerOptions.layers)for(const [source,action] of Object.entries(layer.bindings)){const target=layerTarget(action);if(target===index)layer.bindings[source]='None';else if(target>index)layer.bindings[source]=(action.startsWith('Hold')?'HoldLayer':'Layer')+target;}
 controllerLayers(index);
});
action('controller-save',async()=>{
 if(!controllerLoaded)throw new Error('Load bindings first.');readControllerEdits();
 const {layers,deadzone,sensitivity}=controllerOptions;
 renderController(await api('controller_save',{format:2,layers,deadzone,sensitivity}));notice('Controller bindings saved.');
});
action('client-import',async()=>{await api('controller_capture',{active:false});const f=await api('pick',{kind:'client'});await job('import_client_zip',{file:f.file});});
action('controller-capture',async()=>{await api('controller_capture',{active:true});});
action('controller-release',async()=>{await api('controller_capture',{active:false});});
function drawClientInput(){
 const canvas=$('client-surface'),ctx=canvas.getContext('2d');if(!ctx)return;ctx.fillStyle='#101c20';ctx.fillRect(0,0,canvas.width,canvas.height);
 ctx.strokeStyle='#2d4146';ctx.lineWidth=1;for(let x=0;x<canvas.width;x+=50){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,canvas.height);ctx.stroke();}for(let y=0;y<canvas.height;y+=50){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(canvas.width,y);ctx.stroke();}
 ctx.fillStyle=captureActive?'#b4d19a':'#81938a';ctx.font='18px system-ui';ctx.fillText(captureActive?'Controller input active':'Activate this area to try your bindings',20,32);
 ctx.beginPath();ctx.arc(pointerX,pointerY,clientPressed.has('MouseLeft')?14:8,0,Math.PI*2);ctx.fill();
 $('client-input-status').textContent='Held: '+([...clientPressed].join(', ')||'none')+'\nPointer: '+Math.round(pointerX)+', '+Math.round(pointerY)+' · Scroll: '+wheelTotal;
}
window.clientInputEvent=event=>{
 if(event.type==='capture'){captureActive=event.down;if(!captureActive)clientPressed.clear();$('controller-focus').textContent=captureActive?'Controller captured by the client input area.':'Controller capture is off.';}
 else if(event.type==='layer')$('controller-active-layer').textContent='Active layer: '+(event.x+1)+' · '+event.action;
 else if(event.type==='button'){event.down?clientPressed.add(event.action):clientPressed.delete(event.action);}
 else if(event.type==='pointer'){pointerX=Math.max(0,Math.min(900,pointerX+event.x));pointerY=Math.max(0,Math.min(320,pointerY+event.y));}
 else if(event.type==='wheel')wheelTotal+=event.y;
 drawClientInput();
};
document.addEventListener('visibilitychange',()=>{if(document.hidden)api('controller_capture',{active:false}).catch(()=>{});});
// Editing controls releases capture so controller buttons never operate settings.
$('client').addEventListener('pointerdown',event=>{if(captureActive&&event.target.id!=='client-surface')api('controller_capture',{active:false}).catch(()=>{});});
drawClientInput();

let launchOptionsLoaded=false;
async function clientRuntimeState(){
 const s=await api('client_native_state',{},10000);renderClientActivity(s);
 if(!launchOptionsLoaded){
  launchOptionsLoaded=true;const saved=s.launch_options||{};
  for(const [id,key] of [['client-boats','boat_mode'],['client-particles','particle_mode'],['client-presentation','presentation_mode'],['client-display-fps','display_fps'],['client-turnip-driver','turnip_driver'],['client-npc-rendering','npc_rendering'],['client-renderer','renderer'],['client-cpu-affinity','cpu_affinity'],['client-graphics-threading','graphics_threading'],['client-cpu-profile','cpu_profile'],['client-runtime-mode','runtime_mode'],['client-resolution','resolution']]){
   const select=$(id);if([...select.options].some(o=>o.value===String(saved[key])))select.value=saved[key];
  }
  for(const [id,key] of [['client-load-pauses','reduce_load_pauses'],['client-fast-spells','fast_spell_parse'],['client-mouse-warp','mouse_warp'],['client-dxvk-hud','dxvk_hud'],['client-sound-diagnostics','sound_diagnostics'],['client-audio','audio'],['client-fullscreen','fullscreen'],['client-native-dll','native_dinput8'],['client-native-models','native_d3dx'],['client-diagnostics','diagnostic_logging']])if(typeof saved[key]==='boolean')$(id).checked=saved[key];
 }
 for(const id of ['client-desktop','client-launch','client-prefix-repair','client-runtime-online','client-runtime-offline','client-prepare','client-import','client-directx-online','client-directx-offline'])$(id).disabled=!!(s.alive||s.busy);
 clientFileBusy=!!(s.alive||s.busy);spellTestControls();
 if(s.launch?.compiler)$('dll-state').textContent=s.launch.message||s.launch.phase;
 $('client-view').disabled=!(s.alive&&s.display_ready);
 $('client-runtime-status').textContent=(s.installed?'Installed · ':'Not installed · ')+s.status;
 $('client-directx-status').textContent=s.directx_installed?'DirectX model helpers installed.':'Install the DirectX helpers to enable the legacy character animation and model functions.';
 graphicsControls();
 const launch=s.launch;
 const dllState=launch?.native_loaded?'Native dinput8.dll load confirmed. '+(launch.system_dinput8_loaded?'Wine system DirectInput loaded.':'System DirectInput load not yet confirmed.'):
  launch?.native_dinput8_requested?'Native dinput8.dll requested; load not yet confirmed.':'Built-in dinput8 comparison mode.';
 $('client-launch-status').textContent=launch?.error?launch.error:s.alive?
  (launch?.phase||'Starting').replaceAll('_',' ')+' · '+(launch?.renderer||'Checking graphics')+' · '+(launch?.turnip_driver_requested?'Turnip '+launch.turnip_driver_requested+' · ':'')+(launch?.dxvk_loaded?'DXVK loaded · ':'')+(launch?.cpu_profile||'balanced')+' CPU · '+(launch?.runtime_acceleration_observed?'accelerated runtime':launch?.runtime_acceleration==='compatibility'?'compatibility runtime':'checking runtime')+' · '+(launch?.mode==='desktop'?'Wine desktop test.':dllState)+' '+(launch?.diagnostic_logging?'Verbose diagnostics enabled; launch may be much slower.':'Normal logging.')+' '+(launch?.sound_diagnostics?'Sound diagnostics enabled. ':'')+' '+(launch?.mesa_glthread_requested?(launch?.mesa_glthread_observed?'OpenGL worker observed. ':'OpenGL worker requested; not yet observed. '):'')+' '+(launch?.native_d3dx_requested?'Native model libraries loaded: '+Object.values(launch.model_libraries_loaded||{}).filter(v=>v==='native').length+'/2.':''):
  'Client stopped. '+(launch?.native_loaded?'Last session confirmed native dinput8.dll loading.':'');
 const cameraNote={enabled:'Camera-only recentering requested; activity is recorded in client-camera.log.',needs_dll:'Camera recentering inactive: compile and deploy dinput8.dll with this app, then relaunch.',unsupported_executable:'Camera recentering inactive: this executable has not been verified. Normal mouse movement is retained.'}[launch?.camera_mouse];
 if(cameraNote)$('client-launch-status').textContent+=' '+cameraNote;
 if(launch?.boat_mode==='profile')$('client-launch-status').textContent+=' Boat diagnostics active; select the ship, test boarding and riding, then export logs.';
 if(launch?.boat_mode==='needs_dll')$('client-launch-status').textContent+=' Compile and deploy dinput8.dll with this app for boat diagnostics, then relaunch.';
 if(launch?.boat_mode==='unsupported_executable')$('client-launch-status').textContent+=' Boat diagnostics inactive: this executable is not supported.';
 if(launch?.particle_mode==='repair')$('client-launch-status').textContent+=' Particle repair requested; export logs after testing the first cast.';
 if(launch?.particle_mode==='profile')$('client-launch-status').textContent+=' Particle diagnostics only; game behavior is unchanged.';
 if(launch?.particle_mode==='needs_dll')$('client-launch-status').textContent+=' Compile and deploy dinput8.dll with 0.4.22 or newer for particle options.';
 if(['unsupported_executable','unsupported_graphics'].includes(launch?.particle_mode))$('client-launch-status').textContent+=' Particle option inactive: this client version is not supported.';
 if(launch?.display_loading==='yield')$('client-launch-status').textContent+=' Reduced model-loading pauses requested; timings are in client-loading.log.';
 if(launch?.display_loading==='needs_dll'&&$('client-load-pauses').checked)$('client-launch-status').textContent+=' Compile and deploy dinput8.dll with 0.4.20 or newer to test reduced loading pauses.';
 if(launch?.spell_loading==='fast')$('client-launch-status').textContent+=' Faster spell parsing requested; timings are in client-loading.log.';
 if(launch?.spell_loading==='needs_dll'&&$('client-fast-spells').checked)$('client-launch-status').textContent+=' Compile and deploy dinput8.dll with 0.4.19 or newer to test faster loading.';
 return s;
}
const launchOptions=mode=>({mode,boat_mode:$('client-boats').value,particle_mode:$('client-particles').value,reduce_load_pauses:$('client-load-pauses').checked,fast_spell_parse:$('client-fast-spells').checked,mouse_warp:$('client-mouse-warp').checked,dxvk_hud:$('client-dxvk-hud').checked,presentation_mode:$('client-presentation').value,display_fps:Number($('client-display-fps').value),turnip_driver:$('client-turnip-driver').value,sound_diagnostics:$('client-sound-diagnostics').checked,audio:$('client-audio').checked,npc_rendering:$('client-npc-rendering').value,renderer:$('client-renderer').value,cpu_affinity:$('client-cpu-affinity').value,graphics_threading:$('client-graphics-threading').value,cpu_profile:$('client-cpu-profile').value,runtime_mode:$('client-runtime-mode').value,resolution:$('client-resolution').value,fullscreen:mode==='client'&&$('client-fullscreen').checked,native_dinput8:$('client-native-dll').checked,diagnostic_logging:$('client-diagnostics').checked,native_d3dx:mode==='client'&&$('client-native-models').checked});
action('client-runtime-online',async()=>{notice('Downloading the client runtime…');await api('client_runtime_online');await clientRuntimeState();notice('Client runtime installed. Try Wine desktop first.');});
action('client-runtime-offline',async()=>{await api('pick',{kind:'client-runtime'});await clientRuntimeState();notice('Client runtime installed.');});
action('client-directx-online',async()=>{notice('Downloading Microsoft DirectX model helpers…');await api('client_directx_online');await clientRuntimeState();notice('DirectX model helpers installed. Launch ROF2.');});
action('client-directx-offline',async()=>{await api('pick',{kind:'client-directx'});await clientRuntimeState();notice('DirectX model helpers installed.');});
action('spell-test-apply',()=>job('apply_spell_test'));
action('spell-test-restore',()=>job('restore_spell_test'));
action('client-prepare',async()=>{await job('prepare_client',{resolution:$('client-resolution').value,fullscreen:$('client-fullscreen').checked});});
for(const [id,mode] of [['client-desktop','desktop'],['client-launch','client']])action(id,async()=>{
 await api('controller_capture',{active:false});notice('Opening the client display. First-time Wine setup can take a minute…');
 await api('client_start',launchOptions(mode));await clientRuntimeState();await api('client_view');
});
action('client-prefix-repair',async()=>{
 await api('controller_capture',{active:false});notice('Preserving the previous Wine prefix and preparing a fresh Windows environment…');
 await api('client_start',{...launchOptions('desktop'),repair_prefix:true,renderer:'software'});await clientRuntimeState();await api('client_view');
});
action('client-view',()=>api('client_view'));
action('client-stop',async()=>{await api('client_stop');await clientRuntimeState();notice('Client stopped. Server controls are available at the top.');});
clientRuntimeState().catch(()=>{});

function graphicsControls(){ $('client-turnip-driver').disabled=clientFileBusy||$('client-renderer').value!=='turnip'; $('client-npc-rendering').disabled=$('client-renderer').value!=='turnip'; $('client-graphics-threading').disabled=$('client-renderer').value==='turnip'; }
$('client-renderer').addEventListener('change',graphicsControls);
