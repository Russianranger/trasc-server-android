'use strict';
const $=id=>document.getElementById(id), pending=new Map();
let activeProfile=null,lastClientNative=null;
let seq=0,currentTab='setup',lastState=null,lastNative=null,busy=0,rulesLoaded=false,rulesValues={},initialSettings=false,polling=false,sessionAction=null;
window.nativeReply=(id,response)=>{const p=pending.get(id);if(!p)return;pending.delete(id);clearTimeout(p.timer);response.ok?p.resolve(response.result):p.reject(new Error(response.error));};
function api(op,args={},timeoutMs=0){return new Promise((resolve,reject)=>{const id=String(++seq);const timer=timeoutMs?setTimeout(()=>{pending.delete(id);reject(new Error('Status check timed out.'));},timeoutMs):null;pending.set(id,{resolve,reject,timer});if(!window.Trasc){pending.delete(id);clearTimeout(timer);reject(new Error('Open this interface in the TRASC Android app.'));return;}Trasc.call(id,op,JSON.stringify(activeProfile?{...args,__profile:activeProfile}:args));});}
function notice(text,error=false){$('notice').hidden=false;$('notice').classList.toggle('error',error);$('notice').textContent=text;}
function bytes(n){if(n==null)return '—';return n>=1073741824?(n/1073741824).toFixed(1)+' GB':n>=1048576?(n/1048576).toFixed(1)+' MB':(n/1024).toFixed(0)+' KB';}
function ready(id,ok){$(id).textContent=ok?'Ready':'Required';$(id).classList.toggle('done',ok);}
function tab(name){if(currentTab==='client'&&name!=='client')api('controller_capture',{active:false}).catch(()=>{});currentTab=name;document.body.dataset.scene=name;renderOverview();document.querySelectorAll('.tab').forEach(e=>e.classList.toggle('active',e.id===name));document.querySelectorAll('nav button').forEach(e=>e.classList.toggle('active',e.dataset.tab===name));if(name==='client'&&typeof loadController==='function')loadController().catch(e=>notice(e.message,true));if(name==='spire'&&typeof loadSpire==='function')loadSpire().catch(e=>notice(e.message,true));if(name==='files')browse().catch(e=>notice(e.message,true));if(name==='logs'){logs().catch(()=>{});loadLogRetention().catch(e=>notice(e.message,true));}}
window.appBack=()=>tab('server');
document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>tab(b.dataset.tab)));
function action(id,fn){$(id).addEventListener('click',async()=>{const b=$(id);b.disabled=true;busy++;renderSessionControls();try{await fn();}catch(e){notice(e.message,true);}finally{busy--;b.disabled=false;renderSessionControls();poll().catch(()=>{});}});}
const operationLabels={ferry_service_status:'Checking Qeynos–Erudin route',ferry_service_preview:'Previewing route changes',ferry_service_apply:'Saving route changes',boat_trial_status:'Checking ferry',boat_trial_preview:'Previewing ferry changes',boat_trial_apply:'Saving ferry changes',start:'Starting server',stop:'Stopping server',spire_catalog:'Loading Spire',spire_search:'Searching content',spire_detail:'Loading record',spire_preview:'Validating changes',spire_apply:'Saving content',spire_history:'Loading change history'};
function operationLabel(operation){return operationLabels[operation]||operation.replaceAll('_',' ');}
// Keep scrolled/focused controls clear of the sticky runtime panel in either orientation.
const runtimeToolbar=document.querySelector('.runtime-toolbar');
new ResizeObserver(()=>{document.documentElement.style.scrollPaddingTop=(runtimeToolbar.getBoundingClientRect().height+20)+'px';}).observe(runtimeToolbar);
async function job(operation,args={}){
 const j=await api(operation,args);notice(operationLabels[operation]?operationLabel(operation)+'…':operationLabel(operation)+' started.');
 for(;;){await new Promise(r=>setTimeout(r,1400));const state=await api('state');render(state);const item=state.jobs.find(x=>x.id===j.id);if(!item)throw new Error('Operation status was lost. Check logs.');if(item.status==='error')throw new Error(item.error);if(item.status==='done'){const result=item.result||{};notice(operation==='start'?'Server started. Verify zone readiness in server logs.':result.message||'Operation completed.');return result;}}
}
const tabStories={
 setup:['Build your world.','Start with the runtime, then bring in your server, maps and database.'],
 server:['Your realm awaits.','Launch your world, manage connections and preserve your adventures.'],
 gameplay:['Shape the adventure.','Tune the rules and bring your world to life.'],
 build:['At the forge.','Prepare your source, build your server and deploy when ready.'],
 spire:['Discover your world.','Explore items, creatures, merchants and the treasures they hold.'],
 fixes:['Restore the journey.','Find world repairs and client recovery tools in one place.'],
 database:['The world’s memory.','Preserve characters, explore records and manage your database.'],
 client:['Beyond the gate.','Return to your adventure with your saved controls and settings.'],
 files:['Pack for the journey.','Find and organize the files that make your world.'],
 logs:['Chronicles of your realm.','Review recent events and gather clues when something goes wrong.']
};
function renderOverview(){const [title,summary]=tabStories[currentTab]||tabStories.setup;$('headline').textContent=currentTab==='server'&&lastState?.running?'Your world is running.':title;$('summary').textContent=summary;}
function statusBadge(id,label,state){const el=$(id);el.textContent=label;el.dataset.state=state;el.classList.toggle('online',state==='running');}
function renderClientActivity(s){
 lastClientNative=s;if(typeof syncProfileControls==='function')syncProfileControls();
 let label='Client · Stopped',state='stopped';
 if(s.alive){
  const launch=s.launch||{};
  if(launch.compiler||launch.mode==='compiler'){label='Client · Compiler active';state='busy';}
  else if(launch.mode==='desktop'){label='Client · Wine desktop';state='busy';}
  else if(['stopped','error'].includes(launch.phase)){label='Client · Closing';state='busy';}
  else {const sample=launch.thread_sample,fresh=sample&&Date.now()/1000-sample.sampled_at<25;
   label=fresh&&sample.game_running?'Client · Running in background':s.display_ready?'Client · Runtime open':'Client · Starting';state=fresh&&sample.game_running?'running':'busy';}
 }else if(s.busy){label='Client · Preparing';state='busy';}
 statusBadge('client-badge',label,state);
}
function renderSessionControls(){
 const n=lastNative,s=lastState,active=s?.jobs?.find(j=>['queued','running'].includes(j.status));
 const blocked=!!(busy||sessionAction||n?.installing||n?.session_busy||active);
 $('runtime-open').disabled=blocked||!n?.installed||!!n?.alive;
 $('runtime-close').disabled=blocked||!n?.alive;
 $('start-server').disabled=blocked||!n?.alive||!s||!!s.running||!s.binaries_ready||!s.database_imported;
 $('stop-server').disabled=$('restart-server').disabled=blocked||!n?.alive||!s?.running;
 const operation=sessionAction||active?.operation;
 if(['start','stop','restart'].includes(operation)){statusBadge('badge','Server · '+({start:'Starting',stop:'Stopping',restart:'Restarting'}[operation]),'busy');}
 else if(!n){statusBadge('badge','Server · Status unavailable','unknown');}
 else if(!n.alive){statusBadge('badge','Server · Offline','stopped');}
 else if(!s){statusBadge('badge','Server · Status unavailable','unknown');}
 else {statusBadge('badge',s.running?'Server · Running':'Server · Stopped',s.running?'running':'stopped');}
 if(typeof syncProfileControls==='function')syncProfileControls();
}
function render(s){lastState=s;renderSessionControls();renderOverview();if(typeof renderBoatTrial==='function')renderBoatTrial();if(typeof renderFerryService==='function')renderFerryService();$('free').textContent=bytes(s.free_bytes);
 $('nektulos-status').textContent=s.nektulos?.applied?'Legacy pair applied · original backup: backups/nektulos/'+s.nektulos.backup:s.nektulos?.legacy_ready?'Both legacy files are available.':'Import both legacy Nektulos files before applying the fix.';if(typeof renderClientStatus==='function')renderClientStatus(s.client);ready('source-ready',!!s.source);ready('maps-ready',s.maps_ready);ready('database-ready',s.database_imported);
 $('source-info').textContent=s.source?JSON.stringify(s.source,null,2):'Import a server repository in Setup.';
 $('build-status').textContent=(s.build_ready?'A successful build is ready to deploy.':'No staged build yet.')+(s.binaries_ready?' Deployed binaries are available.':'')+(s.rollback_ready?' Previous binaries can be restored.':'');
 $('pending-rules').textContent=s.settings.rules_pending_restart?'Settings saved · restart required.':'';
 $('endpoint').textContent=$('login-address').textContent=s.settings.ip+':'+s.settings.login_port;
 if(!initialSettings){$('server-ip').value=s.settings.ip;$('source-url').value=s.settings.repo;$('source-ref').value=s.settings.ref;$('workers').value=s.settings.workers;$('build-jobs').value=s.settings.jobs;initialSettings=true;}
 $('processes').replaceChildren();for(const [name,p]of Object.entries(s.processes)){const row=document.createElement('div');row.className='process';const title=document.createElement('strong');title.textContent=name;const state=document.createElement('span');state.textContent=p.running?'Running · '+p.pid:'Stopped · '+p.exit;if(!p.running)state.className='failed';row.append(title,state);$('processes').append(row);}if(!Object.keys(s.processes).length)$('processes').textContent='No server processes running.';
 const running=s.jobs.find(j=>j.status==='running'||j.status==='queued');if(running){$('activity').hidden=false;$('activity-title').textContent=operationLabel(running.operation);$('activity-detail').textContent='In progress · open Logs for command output';$('cancel').hidden=false;}else if(!busy){$('activity').hidden=true;}
}
async function poll(){
 if(polling)return;polling=true;
 try{await Promise.allSettled([
  (async()=>{let nativeKnown=false;try{
   const n=await api('native_state',{},10000);nativeKnown=true;lastNative=n;if(typeof renderProfile==='function'&&!renderProfile(n))return;$('runtime-status').textContent=n.status;ready('runtime-ready',n.installed);
   if(n.session_busy||n.installing){lastState=null;$('activity').hidden=false;$('activity-title').textContent=n.session_busy?'Complete session transfer':'Runtime installation';$('activity-detail').textContent=n.status;$('cancel').hidden=true;}
   else if(n.alive){lastState=null;render(await api('state',{},10000));}
   else {lastState=null;$('free').textContent=bytes(n.free_bytes);if(!busy)$('activity').hidden=true;}
  }catch(e){if(!nativeKnown)lastNative=null;lastState=null;$('runtime-status').textContent=e.message;}
  finally{renderSessionControls();renderOverview();}})(),
  (async()=>{try{if(typeof clientRuntimeState==='function')await clientRuntimeState();else renderClientActivity(await api('client_native_state',{},10000));}
   catch(e){lastClientNative=null;if(typeof syncProfileControls==='function')syncProfileControls();statusBadge('client-badge','Client · Status unavailable','unknown');}})()
 ]);}finally{polling=false;}
}
document.addEventListener('visibilitychange',()=>{if(!document.hidden)poll();});
async function scanDB(){const data=await api('databases');const select=$('db-candidate'),previous=select.value;select.replaceChildren();for(const c of data.candidates){const option=document.createElement('option');option.value=c.id;option.textContent=c.id+' · '+bytes(c.size);select.append(option);}if([...select.options].some(o=>o.value===previous))select.value=previous;if(!data.candidates.length){const o=document.createElement('option');o.value='';o.textContent='No SQL files found. Import source or a database file first.';select.append(o);}notice('Found '+data.candidates.length+' database candidates. Choose the full seed.');}
async function exportResult(result){
 const completed=result.message?result.message+' ':'';
 try{if(result.file)await api('export',{path:result.file});}
 catch(e){if(!result.local_client_synced)throw e;notice(completed+'ZIP not saved: '+e.message+'. The generated ZIP is retained in the app.',e.message!=='File selection cancelled');return;}
 notice(completed+'File exported. A local copy is retained.');
}
action('runtime-online',async()=>{await api('runtime_install');await api('runtime_start');notice('Runtime ready. Import your server next.');});
action('runtime-offline',async()=>{await api('pick',{kind:'runtime'});await api('runtime_start');notice('Offline runtime ready.');});
action('runtime-open',async()=>{await api('runtime_start');notice('Runtime opened.');});
action('runtime-close',async()=>{await api('runtime_stop');notice('Server and database shut down.');});
const sourceArgs=()=>({url:$('source-url').value.trim(),ref:$('source-ref').value.trim()});
action('source-git',async()=>{await job('import_source',sourceArgs());await scanDB();});
action('source-zip',async()=>{const f=await api('pick',{kind:'source'});await job('import_source',{file:f.file});await scanDB();});
action('maps-git',async()=>{await job('import_maps',{url:$('maps-url').value.trim(),ref:$('maps-ref').value.trim()});});
action('maps-zip',async()=>{const f=await api('pick',{kind:'maps'});await job('import_maps',{file:f.file});});
action('scan-db',scanDB);
action('upload-db',async()=>{await api('pick',{kind:'database'});await scanDB();});
action('import-db',async()=>{const selection=$('db-candidate').value;if(!selection)throw new Error('Choose a database file first.');await job('import_database',{selection,replace:$('replace-db').checked});});
async function serverAction(operation){
 sessionAction=operation;renderSessionControls();
 try{if(operation==='restart'){await job('stop');await job('start');}else await job(operation);}
 finally{sessionAction=null;renderSessionControls();}
}
action('start-server',()=>serverAction('start'));action('stop-server',()=>serverAction('stop'));
action('restart-server',()=>serverAction('restart'));
action('save-network',()=>job('network',{ip:$('server-ip').value.trim()}));
action('export-client',async()=>exportResult(await job('export_client')));
for(const id of ['quick-backup','db-backup'])action(id,async()=>exportResult(await job('backup_database')));
for(const id of ['quick-logs','export-logs'])action(id,async()=>exportResult(await api('export_logs')));
action('refresh-source',()=>job('import_source',sourceArgs()));
action('build-server',()=>job('build',{jobs:Number($('build-jobs').value)}));
action('deploy-build',()=>job('deploy'));action('rollback-build',()=>job('rollback'));
action('cancel',async()=>{await api('cancel');notice('Cancellation requested. Cleanup can take a moment.');});
action('load-backups',async()=>{const r=await api('files',{path:'backups'});$('backup-select').replaceChildren();for(const f of r.items.filter(x=>x.name.endsWith('.sql.gz'))){const o=document.createElement('option');o.value=f.path;o.textContent=f.name+' · '+bytes(f.size);$('backup-select').append(o);}if(!$('backup-select').options.length)notice('No local database backups yet.');});
action('restore-backup',async()=>{if(!$('backup-select').value)throw new Error('Select a snapshot first.');await job('restore_database',{file:$('backup-select').value});});
document.querySelectorAll('[data-query]').forEach(b=>b.addEventListener('click',()=>{$('sql-query').value=b.dataset.query;$('sql-write').checked=false;}));
action('run-sql',async()=>{const r=await job('sql',{query:$('sql-query').value,write:$('sql-write').checked});$('sql-result').textContent=r.output+(r.truncated?'\n[Output truncated]':'');});
let fileBrowseGeneration=0,fileOffset=0,fileNext=null;
const filePageSize=200;
function clearFileResults(message){
 ++fileBrowseGeneration;$('file-list').replaceChildren();$('selected-file').value='';
 $('file-prev').disabled=$('file-next').disabled=true;$('file-results').textContent=message;
}
async function browse(offset=0){
 clearFileResults('Loading files…');const request=fileBrowseGeneration;
 const path=$('file-path').value.trim(),query=$('file-search').value.trim();
 try{
  const r=await api('files',{path,query,offset,limit:filePageSize});
  if(request!==fileBrowseGeneration)return;
  $('file-path').value=r.path==='.'?'':r.path;fileOffset=r.offset;fileNext=r.next_offset;
  for(const f of r.items){
   const row=document.createElement('tr'),name=document.createElement('td'),size=document.createElement('td'),select=document.createElement('td');
   if(f.directory){const b=document.createElement('button');b.className='folder';b.textContent='▸ '+f.name;
    b.onclick=()=>{$('file-path').value=f.path;$('file-search').value='';browse().catch(e=>notice(e.message,true));};name.append(b);
   }else name.textContent=f.name;
   size.textContent=f.directory?'Folder':bytes(f.size);const b=document.createElement('button');b.className='secondary';b.textContent='Select';
   b.onclick=()=>{$('selected-file').value=f.path;};select.append(b);row.append(name,size,select);$('file-list').append(row);
  }
  $('file-results').textContent=r.total?`${r.offset+1}–${r.offset+r.items.length} of ${r.total} ${query?'matches':'entries'}`:query?'No matching names in this folder.':'This folder is empty.';
  $('file-prev').disabled=r.offset===0;$('file-next').disabled=r.next_offset==null;
  $('file-list').closest('.table-wrap').scrollTop=0;
 }catch(e){if(request!==fileBrowseGeneration)return;$('file-results').textContent='Could not load files. '+e.message;throw e;}
}
for(const id of ['file-path','file-search'])$(id).addEventListener('input',()=>clearFileResults('Press Search or Open folder to load files.'));
function fileBrowseAction(id,fn){$(id).addEventListener('click',()=>fn().catch(e=>notice(e.message,true)));}
fileBrowseAction('file-go',()=>browse());fileBrowseAction('file-search-go',()=>browse());
fileBrowseAction('file-search-clear',()=>{$('file-search').value='';return browse();});
fileBrowseAction('file-up',()=>{$('file-path').value=$('file-path').value.split('/').slice(0,-1).join('/');$('file-search').value='';return browse();});
fileBrowseAction('file-prev',()=>browse(Math.max(0,fileOffset-filePageSize)));
fileBrowseAction('file-next',()=>browse(fileNext??0));
for(const [id,button] of [['file-path','file-go'],['file-search','file-search-go']])$(id).addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();$(button).click();}});
action('file-upload',async()=>{const f=await api('pick',{kind:'file'});$('file-path').value='incoming';$('file-search').value='';await browse();$('selected-file').value=f.path;notice('File imported. Set its destination, then Copy or Move.');});
for(const op of ['copy','move'])action('file-'+op,async()=>{await job('edit_file',{action:op,path:$('selected-file').value,destination:$('destination-file').value.trim()});await browse();});
action('file-export',()=>api('export',{path:$('selected-file').value}));
let logRetentionRead=0,logRetentionWrite=Promise.resolve();
async function loadLogRetention(){
 const request=++logRetentionRead,select=$('log-retention'),save=$('save-log-retention');select.disabled=save.disabled=true;
 try{await logRetentionWrite;const r=await api('log_retention');if(request===logRetentionRead)select.value=String(r.count);}
 finally{if(request===logRetentionRead)select.disabled=save.disabled=false;}
}
action('save-log-retention',async()=>{
 const select=$('log-retention');if(select.disabled)return;const request=++logRetentionRead;select.disabled=true;
 const write=api('log_retention',{count:Number(select.value)});logRetentionWrite=write.catch(()=>{});
 try{const r=await write;$('log-retention-status').textContent=r.message+' Freed '+bytes(r.removed_bytes)+'.';await logs();}
 finally{if(request===logRetentionRead)select.disabled=false;}
});
async function logs(){const name=$('log-name').value;const r=await api('logs',{name});const view=$('log-output');view.textContent=r.text;if(r.names){$('log-name').replaceChildren();for(const entry of [...new Set([name,...r.names])].filter(Boolean)){const option=document.createElement('option');option.value=option.textContent=entry;$('log-name').append(option);}$('log-name').value=name;}if($('follow-log').checked)view.scrollTop=view.scrollHeight;}
action('refresh-log',logs);$('log-name').addEventListener('change',()=>logs().catch(e=>notice(e.message,true)));
action('export-runtime-log',()=>api('export',{path:'logs/runtime.log'}));
setInterval(()=>{poll();if(currentTab==='logs'&&$('follow-log').checked)logs().catch(()=>{});},2500);poll();

action('fix-nektulos',()=>job('fix_nektulos'));
action('revert-nektulos',()=>job('revert_nektulos'));
action('session-export',async()=>{notice('Stopping the session and creating a complete backup…');const r=await api('session_backup');$('session-result').textContent='Local ZIP: '+r.file;await exportResult(r);notice('Complete session exported. Open runtime when you want to play again.');});
action('session-import',async()=>{const r=await api('pick',{kind:'session',replace:$('replace-session').checked});initialSettings=false;rulesLoaded=false;notice(r.message);window.location.reload();});

for(const [id,mode] of [['clear-old-logs','older_2_days'],['reset-logs','reset']])action(id,async()=>{
 const buttons=[$('clear-old-logs'),$('reset-logs')];buttons.forEach(b=>b.disabled=true);
 try{const r=await api('clear_logs',{mode});$('log-cleanup-status').textContent=r.message+' Freed '+bytes(r.cleared_bytes)+'.';notice(r.message);await logs();}
 finally{buttons.forEach(b=>b.disabled=false);}
});
