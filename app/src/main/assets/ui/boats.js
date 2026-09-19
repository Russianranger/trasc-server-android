'use strict';
const boatTrial={active:null,working:false,preview:null};
function boatInvalidate(){boatTrial.preview=null;$('boat-trial-preview').hidden=true;$('boat-trial-save').disabled=true;}
function renderBoatTrial(){
 const blocked=boatTrial.working,known=boatTrial.active!==null;
 $('boat-trial-refresh').disabled=blocked;
 $('boat-trial-install').disabled=blocked||!known||boatTrial.active;
 for(const id of ['boat-trial-reset','boat-trial-remove'])$(id).disabled=blocked||!known||!boatTrial.active;
 $('boat-trial-save').disabled=blocked||!boatTrial.preview||!!lastState?.running;
 $('boat-trial-discard').disabled=blocked;
}
async function boatRun(fn){
 if(boatTrial.working)return;
 boatTrial.working=true;busy++;renderBoatTrial();
 try{await fn();}catch(e){boatInvalidate();$('boat-trial-status').textContent=e.message;notice(e.message,true);}
 finally{boatTrial.working=false;busy--;renderBoatTrial();}
}
async function boatRefresh(){
 boatInvalidate();boatTrial.active=null;
 const r=await job('boat_trial_status');boatTrial.active=!!r.active;
 $('boat-trial-status').textContent=r.message;
}
function boatBind(id,fn){$(id).addEventListener('click',()=>boatRun(fn));}
boatBind('boat-trial-refresh',boatRefresh);
$('boat-trial-panel').addEventListener('toggle',()=>{if($('boat-trial-panel').open)boatRun(boatRefresh);});
for(const action of ['install','reset','remove'])boatBind('boat-trial-'+action,async()=>{
 boatInvalidate();const r=await job('boat_trial_preview',{action});boatTrial.preview=r;
 $('boat-trial-summary').textContent=r.summary;$('boat-trial-warning').textContent=r.message;
 $('boat-trial-preview').hidden=false;
});
boatBind('boat-trial-discard',async()=>boatInvalidate());
boatBind('boat-trial-save',async()=>{
 if(!boatTrial.preview||lastState?.running)return;
 const token=boatTrial.preview.token;boatInvalidate();
 const r=await job('boat_trial_apply',{token});boatTrial.active=!!r.active;
 $('boat-trial-status').textContent=r.message+' Backup: '+r.backup;
});
