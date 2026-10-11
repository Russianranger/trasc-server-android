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
  status.textContent=names[theme]+' theme · applies to all worlds.'+(saved?'':' Available for this session; device storage is unavailable.');
  return saved;
 }
 let saved='default';try{saved=localStorage.getItem(key);}catch{}
 apply(saved);
 window.launcherAppearanceSnapshot=()=>({theme:valid(select.value)});
 window.restoreLauncherAppearance=snapshot=>{
  if(!snapshot||typeof snapshot!=='object'||!Object.prototype.hasOwnProperty.call(names,snapshot.theme))return false;
  return apply(snapshot.theme,true);
 };
 window.restoreLauncherAppearanceReceipt=receipt=>{
  if(!receipt?.restored_activation||typeof receipt.restored_activation!=='string')return false;
  const marker='trasc.session.restored_activation';
  try{if(localStorage.getItem(marker)===receipt.restored_activation)return true;}catch{}
  if(!window.restoreLauncherAppearance(receipt.launcher_preferences))return false;
  try{localStorage.setItem(marker,receipt.restored_activation);}catch{return false;}
  return true;
 };
 select.addEventListener('change',()=>apply(select.value,true));
 window.addEventListener('storage',event=>{if(event.key===key||event.key===null)apply(event.newValue);});
})();
