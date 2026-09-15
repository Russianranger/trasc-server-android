'use strict';
let controllerLoaded=false,controllerOptions=null,captureActive=false;
const clientPressed=new Set();let pointerX=450,pointerY=160,wheelTotal=0;
function renderClientStatus(client){$('client-status').textContent=client?.imported?client.files+' entries · '+bytes(client.bytes)+' extracted. '+(client.dinput8_present?'dinput8.dll is present.':'dinput8.dll was not found beside eqgame.exe.'):'No client imported.';}
function renderController(profile){
 controllerOptions=profile;controllerLoaded=true;$('controller-deadzone').value=profile.deadzone;$('controller-speed').value=profile.sensitivity;$('controller-bindings').replaceChildren();
 for(const source of profile.sources){const field=document.createElement('div'),label=document.createElement('label'),select=document.createElement('select');label.htmlFor='binding-'+source;label.textContent=source.replace(/([a-z])([A-Z])/g,'$1 $2');select.id='binding-'+source;
  for(const code of profile.actions){const option=document.createElement('option');option.value=code;option.textContent=code.replace(/^Key/,'Key ').replace(/^Digit/,'Number ').replace(/([a-z])([A-Z])/g,'$1 $2');select.append(option);}select.value=profile.bindings[source];field.append(label,select);$('controller-bindings').append(field);
 }
 if(profile.error)notice(profile.error,true);
}
async function loadController(force=false){if(controllerLoaded&&!force)return;renderController(await api('controller_state'));}
action('controller-load',()=>loadController(true));
action('controller-defaults',async()=>{
 await loadController();const bindings=Object.fromEntries(controllerOptions.sources.map(s=>[s,'None']));Object.assign(bindings,{A:'Space',B:'Escape',X:'KeyE',Y:'Tab',L1:'ShiftLeft',R1:'ControlLeft',L2:'MouseRight',R2:'MouseLeft',L3:'KeyR',R3:'MouseMiddle',Start:'Enter',Select:'KeyI',LeftUp:'KeyW',LeftDown:'KeyS',LeftLeft:'KeyA',LeftRight:'KeyD'});
 for(const dir of ['Up','Down','Left','Right']){bindings['Dpad'+dir]='Arrow'+dir;bindings['Right'+dir]='Pointer'+dir;}
 renderController({...controllerOptions,bindings,deadzone:.2,sensitivity:700});notice('Default bindings filled in. Select Save bindings to keep them.');
});
action('controller-save',async()=>{
 if(!controllerLoaded)throw new Error('Load bindings first.');const bindings=Object.fromEntries(controllerOptions.sources.map(s=>[s,$('binding-'+s).value]));
 renderController(await api('controller_save',{bindings,deadzone:Number($('controller-deadzone').value),sensitivity:Number($('controller-speed').value)}));notice('Controller bindings saved.');
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
 const s=await api('client_native_state');
 if(!launchOptionsLoaded){
  launchOptionsLoaded=true;const saved=s.launch_options||{};
  for(const [id,key] of [['client-renderer','renderer'],['client-cpu-affinity','cpu_affinity'],['client-graphics-threading','graphics_threading'],['client-cpu-profile','cpu_profile'],['client-runtime-mode','runtime_mode'],['client-resolution','resolution']]){
   const select=$(id);if([...select.options].some(o=>o.value===saved[key]))select.value=saved[key];
  }
  for(const [id,key] of [['client-fullscreen','fullscreen'],['client-native-dll','native_dinput8'],['client-native-models','native_d3dx'],['client-diagnostics','diagnostic_logging']])if(typeof saved[key]==='boolean')$(id).checked=saved[key];
 }
 for(const id of ['client-desktop','client-launch','client-prefix-repair','client-runtime-online','client-runtime-offline','client-prepare','client-import','client-directx-online','client-directx-offline'])$(id).disabled=!!(s.alive||s.busy);
 $('client-view').disabled=!(s.alive&&s.display_ready);
 $('client-runtime-status').textContent=(s.installed?'Installed · ':'Not installed · ')+s.status;
 $('client-directx-status').textContent=s.directx_installed?'DirectX model helpers installed.':'Install the DirectX helpers to enable the legacy character animation and model functions.';
 graphicsControls();
 const launch=s.launch;
 const dllState=launch?.native_loaded?'Native dinput8.dll load confirmed. '+(launch.system_dinput8_loaded?'Wine system DirectInput loaded.':'System DirectInput load not yet confirmed.'):
  launch?.native_dinput8_requested?'Native dinput8.dll requested; load not yet confirmed.':'Built-in dinput8 comparison mode.';
 $('client-launch-status').textContent=launch?.error?launch.error:s.alive?
  (launch?.phase||'Starting').replaceAll('_',' ')+' · '+(launch?.renderer||'Checking graphics')+' · '+(launch?.dxvk_loaded?'DXVK loaded · ':'')+(launch?.cpu_profile||'balanced')+' CPU · '+(launch?.runtime_acceleration_observed?'accelerated runtime':launch?.runtime_acceleration==='compatibility'?'compatibility runtime':'checking runtime')+' · '+(launch?.mode==='desktop'?'Wine desktop test.':dllState)+' '+(launch?.diagnostic_logging?'Verbose diagnostics enabled; launch may be much slower.':'Normal logging.')+' '+(launch?.mesa_glthread_requested?(launch?.mesa_glthread_observed?'OpenGL worker observed. ':'OpenGL worker requested; not yet observed. '):'')+' '+(launch?.native_d3dx_requested?'Native model libraries loaded: '+Object.values(launch.model_libraries_loaded||{}).filter(v=>v==='native').length+'/2.':''):
  'Client stopped. '+(launch?.native_loaded?'Last session confirmed native dinput8.dll loading.':'');
 return s;
}
const launchOptions=mode=>({mode,renderer:$('client-renderer').value,cpu_affinity:$('client-cpu-affinity').value,graphics_threading:$('client-graphics-threading').value,cpu_profile:$('client-cpu-profile').value,runtime_mode:$('client-runtime-mode').value,resolution:$('client-resolution').value,fullscreen:mode==='client'&&$('client-fullscreen').checked,native_dinput8:$('client-native-dll').checked,diagnostic_logging:$('client-diagnostics').checked,native_d3dx:mode==='client'&&$('client-native-models').checked});
action('client-runtime-online',async()=>{notice('Downloading the client runtime…');await api('client_runtime_online');await clientRuntimeState();notice('Client runtime installed. Try Wine desktop first.');});
action('client-runtime-offline',async()=>{await api('pick',{kind:'client-runtime'});await clientRuntimeState();notice('Client runtime installed.');});
action('client-directx-online',async()=>{notice('Downloading Microsoft DirectX model helpers…');await api('client_directx_online');await clientRuntimeState();notice('DirectX model helpers installed. Launch ROF2.');});
action('client-directx-offline',async()=>{await api('pick',{kind:'client-directx'});await clientRuntimeState();notice('DirectX model helpers installed.');});
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
action('client-stop',async()=>{await api('client_stop');await clientRuntimeState();notice('Client stopped. Manage the server separately in Server.');});
setInterval(()=>{if(currentTab==='client')clientRuntimeState().catch(e=>{$('client-runtime-status').textContent=e.message;});},1500);
clientRuntimeState().catch(()=>{});

function graphicsControls(){ $('client-graphics-threading').disabled=$('client-renderer').value==='turnip'; }
$('client-renderer').addEventListener('change',graphicsControls);
