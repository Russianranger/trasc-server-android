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
