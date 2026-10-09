'use strict';
// Launcher appearance is one device-local preference, independent of either world.
// This deliberately does not call the native bridge or alter a client skin/INI.
(()=>{
 const key='trasc.launcher.theme';
 const names={default:'Default',necromancer:'Necromancer',monk:'Monk'};
 const select=document.getElementById('launcher-theme');
 const status=document.getElementById('launcher-theme-status');
 const valid=value=>Object.prototype.hasOwnProperty.call(names,value)?value:'default';
 function apply(value,persist=false){
  const theme=valid(value);let saved=true;
  if(persist){try{localStorage.setItem(key,theme);}catch{saved=false;}}
  document.body.dataset.launcherTheme=theme;select.value=theme;
  status.textContent=names[theme]+' theme · applies to both worlds.'+(saved?'':' Available for this session; device storage is unavailable.');
 }
 let saved='default';try{saved=localStorage.getItem(key);}catch{}
 apply(saved);
 select.addEventListener('change',()=>apply(select.value,true));
 window.addEventListener('storage',event=>{if(event.key===key||event.key===null)apply(event.newValue);});
})();
