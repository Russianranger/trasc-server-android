'use strict';
const ferryService={active:null,ready:false,working:false,preview:null};
function ferryInvalidate(){ferryService.preview=null;$('ferry-service-preview').hidden=true;$('ferry-service-save').disabled=true;}
function renderFerryService(){
 const f=ferryService,known=f.active!==null;
 $('ferry-service-refresh').disabled=f.working;
 $('ferry-service-install').disabled=f.working||!known||f.active||!f.ready;
 $('ferry-service-reset').disabled=f.working||!known||!f.active||!f.ready;
 $('ferry-service-remove').disabled=f.working||!known||!f.active;
 $('ferry-service-save').disabled=f.working||!f.preview||!!lastState?.running;
 $('ferry-service-discard').disabled=f.working;
}
async function ferryRun(fn){
 if(ferryService.working)return;
 ferryService.working=true;busy++;renderFerryService();
 try{await fn();}catch(e){ferryInvalidate();$('ferry-service-status').textContent=e.message;notice(e.message,true);}
 finally{ferryService.working=false;busy--;renderFerryService();}
}
async function ferryRefresh(){
 ferryInvalidate();ferryService.active=null;
 const r=await job('ferry_service_status');ferryService.active=!!r.active;ferryService.ready=!!r.server_ready;
 let text=r.message;
 if(!r.server_ready)text+=' Build and deploy the server with this app version to enable route support.';
 if(r.active&&!r.running)text+=' The next server start begins at Qeynos.';
 if(r.active&&r.running&&r.route){
  const s=r.route,places=['','South Qeynos','Erud’s Crossing, toward Erudin','Erudin','Erud’s Crossing, toward Qeynos'];
  const stages={pause:'Waiting at a waypoint',sailing:'Sailing',prepare:'Preparing the next zone',ready:'Destination ship ready',receiving:'Waiting for passengers to load',fault:'Route paused'};
  text+=' '+(places[s.phase]||'Route')+' · '+(stages[s.status]||s.status)+'.';
  if(s.error)text+=' '+s.error;
 }
 $('ferry-service-status').textContent=text;
}
function ferryBind(id,fn){$(id).addEventListener('click',()=>ferryRun(fn));}
ferryBind('ferry-service-refresh',ferryRefresh);
$('ferry-service-panel').addEventListener('toggle',()=>{if($('ferry-service-panel').open)ferryRun(ferryRefresh);});
for(const action of ['install','reset','remove'])ferryBind('ferry-service-'+action,async()=>{
 ferryInvalidate();const r=await job('ferry_service_preview',{action});ferryService.preview=r;
 $('ferry-service-summary').textContent=r.summary;$('ferry-service-warning').textContent=r.message;
 $('ferry-service-preview').hidden=false;
});
ferryBind('ferry-service-discard',async()=>ferryInvalidate());
ferryBind('ferry-service-save',async()=>{
 if(!ferryService.preview||lastState?.running)return;
 const token=ferryService.preview.token;ferryInvalidate();
 const r=await job('ferry_service_apply',{token});ferryService.active=!!r.active;
 $('ferry-service-status').textContent=r.message+' Backup: '+r.backup;
});
