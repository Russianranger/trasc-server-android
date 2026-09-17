'use strict';
let gameSettings=null,gameSettingsBusy=false;
const iniFields=new Map(),iniId=e=>e.section.toLowerCase()+'/'+e.key.toLowerCase();
function gameSettingsControls(){
 $('game-settings-save').disabled=!gameSettings||gameSettingsBusy||clientFileBusy;
 for(const id of ['game-settings-load','game-models-classic','game-models-luclin'])$(id).disabled=gameSettingsBusy||clientFileBusy;
}
function showGameSettings(data){
 gameSettings=data;iniFields.clear();$('game-settings-editor').hidden=false;
 $('game-model-settings').replaceChildren();$('game-other-settings').replaceChildren();
 const groups=new Map();
 for(const e of data.entries){
  const model=e.section.toLowerCase()==='defaults'&&data.models.includes(e.key);
  const row=document.createElement('div'),label=document.createElement('label');row.dataset.search=(e.section+' '+e.key).toLowerCase();
  const id='ini-'+iniFields.size;label.htmlFor=id;label.textContent=model?e.key==='AllLuclinPcModelsOff'?'Force all available classic player models':e.key.replace(/^UseLuclin/,'Luclin ').replace(/([a-z])([A-Z])/g,'$1 $2'):e.key;
  const bool=model||/^(TRUE|FALSE)$/i.test(e.value),input=document.createElement(bool?'select':'input');input.id=id;
  if(bool){for(const [value,text] of [...(e.missing?[['','Game default (not set)']]:[]),['TRUE','On'],['FALSE','Off']]){const o=document.createElement('option');o.value=value;o.textContent=text;input.append(o);}input.value=e.value.toUpperCase();}
  else{input.type='text';input.value=e.value;input.maxLength=1024;input.spellcheck=false;}
  input.disabled=e.managed;row.append(label,input);iniFields.set(iniId(e),{entry:e,input,initial:input.value});
  if(model)$('game-model-settings').append(row);
  else{if(!groups.has(e.section)){const group=document.createElement('details'),title=document.createElement('summary');title.textContent=e.section;group.append(title);groups.set(e.section,group);$('game-other-settings').append(group);}groups.get(e.section).append(row);}
 }
 $('game-settings-status').textContent=data.message||'Loaded current settings. Only edited values will be saved.';gameSettingsControls();
}
async function iniOperation(fn){gameSettingsBusy=true;gameSettingsControls();try{await fn();}finally{gameSettingsBusy=false;gameSettingsControls();}}
action('game-settings-load',()=>iniOperation(async()=>showGameSettings(await job('client_settings'))));
action('game-settings-save',()=>iniOperation(async()=>{
 if(clientFileBusy)throw new Error('Stop the client before saving game settings.');
 const changes=[];for(const {entry:e,input,initial} of iniFields.values())if(!e.managed&&input.value!==initial&&!(e.missing&&input.value===''))changes.push({section:e.section,key:e.key,value:input.value});
 const result=await job('client_settings_save',{revision:gameSettings.revision,changes});showGameSettings(result);notice(result.message);
}));
function modelPreset(classic){
 if(!gameSettings)return;
 for(const {entry:e,input} of iniFields.values()){
  if(e.section.toLowerCase()!=='defaults')continue;
  if(e.key==='AllLuclinPcModelsOff')input.value=classic?'TRUE':'FALSE';
  else if(e.key.startsWith('UseLuclin')&&e.key!=='UseLuclinElementals')input.value=classic&&!e.key.includes('VahShir')?'FALSE':'TRUE';
 }
 $('game-settings-status').textContent='Model preset selected. Save game settings to apply it on the next client launch.';
}
action('game-models-classic',()=>modelPreset(true));action('game-models-luclin',()=>modelPreset(false));
$('game-settings-search').addEventListener('input',()=>{const query=$('game-settings-search').value.toLowerCase();for(const row of $('game-other-settings').querySelectorAll('[data-search]'))row.hidden=!row.dataset.search.includes(query);for(const group of $('game-other-settings').children){group.hidden=![...group.querySelectorAll('[data-search]')].some(e=>!e.hidden);if(query)group.open=true;}});
