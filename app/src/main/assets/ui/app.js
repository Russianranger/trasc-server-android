'use strict';
const $=id=>document.getElementById(id), pending=new Map();
let seq=0,currentTab='setup',lastState=null,busy=0,rulesLoaded=false,rulesValues={},initialSettings=false;
window.nativeReply=(id,response)=>{const p=pending.get(id);if(!p)return;pending.delete(id);response.ok?p.resolve(response.result):p.reject(new Error(response.error));};
function api(op,args={}){return new Promise((resolve,reject)=>{const id=String(++seq);pending.set(id,{resolve,reject});if(!window.Trasc){pending.delete(id);reject(new Error('Open this interface in the TRASC Android app.'));return;}Trasc.call(id,op,JSON.stringify(args));});}
function notice(text,error=false){$('notice').hidden=false;$('notice').classList.toggle('error',error);$('notice').textContent=text;}
function bytes(n){if(n==null)return '—';return n>=1073741824?(n/1073741824).toFixed(1)+' GB':n>=1048576?(n/1048576).toFixed(1)+' MB':(n/1024).toFixed(0)+' KB';}
function ready(id,ok){$(id).textContent=ok?'Ready':'Required';$(id).classList.toggle('done',ok);}
function tab(name){if(currentTab==='client'&&name!=='client')api('controller_capture',{active:false}).catch(()=>{});currentTab=name;document.querySelectorAll('.tab').forEach(e=>e.classList.toggle('active',e.id===name));document.querySelectorAll('nav button').forEach(e=>e.classList.toggle('active',e.dataset.tab===name));if(name==='client'&&typeof loadController==='function')loadController().catch(e=>notice(e.message,true));if(name==='files')browse().catch(e=>notice(e.message,true));if(name==='logs')logs().catch(()=>{});}
window.appBack=()=>tab('server');
document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>tab(b.dataset.tab)));
function action(id,fn){$(id).addEventListener('click',async()=>{const b=$(id);b.disabled=true;busy++;try{await fn();}catch(e){notice(e.message,true);}finally{busy--;b.disabled=false;poll().catch(()=>{});}});}
async function job(operation,args={}){
 const j=await api(operation,args);notice(operation.replaceAll('_',' ')+' started.');
 for(;;){await new Promise(r=>setTimeout(r,1400));const state=await api('state');render(state);const item=state.jobs.find(x=>x.id===j.id);if(!item)throw new Error('Operation status was lost. Check logs.');if(item.status==='error')throw new Error(item.error);if(item.status==='done'){const result=item.result||{};notice(result.message||'Operation completed.');return result;}}
}
function render(s){lastState=s;$('free').textContent=bytes(s.free_bytes);$('badge').textContent=s.running?'SERVER RUNNING':'RUNTIME READY';$('badge').classList.toggle('online',true);$('headline').textContent=s.running?'Your world is running.':'Your server workspace.';$('summary').textContent=s.running?'Manage gameplay, export client data and keep an eye on your server.':'Import, compile and manage your local Triptych server.';
 $('nektulos-status').textContent=s.nektulos?.applied?'Legacy pair applied · original backup: backups/nektulos/'+s.nektulos.backup:s.nektulos?.legacy_ready?'Both legacy files are available.':'Import both legacy Nektulos files before applying the fix.';if(typeof renderClientStatus==='function')renderClientStatus(s.client);ready('source-ready',!!s.source);ready('maps-ready',s.maps_ready);ready('database-ready',s.database_imported);
 $('source-info').textContent=s.source?JSON.stringify(s.source,null,2):'Import a server repository in Setup.';
 $('build-status').textContent=(s.build_ready?'A successful build is ready to deploy.':'No staged build yet.')+(s.binaries_ready?' Deployed binaries are available.':'')+(s.rollback_ready?' Previous binaries can be restored.':'');
 $('pending-rules').textContent=s.settings.rules_pending_restart?'Settings saved · restart required.':'';
 $('endpoint').textContent=$('login-address').textContent=s.settings.ip+':'+s.settings.login_port;
 if(!initialSettings){$('server-ip').value=s.settings.ip;$('source-url').value=s.settings.repo;$('source-ref').value=s.settings.ref;$('workers').value=s.settings.workers;$('build-jobs').value=s.settings.jobs;initialSettings=true;}
 $('processes').replaceChildren();for(const [name,p]of Object.entries(s.processes)){const row=document.createElement('div');row.className='process';const title=document.createElement('strong');title.textContent=name;const state=document.createElement('span');state.textContent=p.running?'Running · '+p.pid:'Stopped · '+p.exit;if(!p.running)state.className='failed';row.append(title,state);$('processes').append(row);}if(!Object.keys(s.processes).length)$('processes').textContent='No server processes running.';
 const running=s.jobs.find(j=>j.status==='running'||j.status==='queued');if(running){$('activity').hidden=false;$('activity-title').textContent=running.operation.replaceAll('_',' ');$('activity-detail').textContent='In progress · open Logs for command output';$('cancel').hidden=false;}else if(!busy){$('activity').hidden=true;}
}
async function poll(){try{const n=await api('native_state');$('runtime-status').textContent=n.status;if(!busy){$('runtime-open').disabled=!n.installed||n.alive||n.installing||n.session_busy;$('runtime-close').disabled=!n.alive||n.installing||n.session_busy;}ready('runtime-ready',n.installed);if(!n.alive){$('free').textContent=bytes(n.free_bytes);$('badge').textContent=n.installing?'INSTALLING':'RUNTIME CLOSED';$('badge').classList.remove('online');}if(n.session_busy){$('activity').hidden=false;$('activity-title').textContent='Complete session transfer';$('activity-detail').textContent=n.status;$('cancel').hidden=true;}else if(n.installing){$('activity').hidden=false;$('activity-title').textContent='Runtime installation';$('activity-detail').textContent=n.status;$('cancel').hidden=true;}else if(n.alive){render(await api('state'));}else if(!busy)$('activity').hidden=true;}catch(e){$('runtime-status').textContent=e.message;}}
async function scanDB(){const data=await api('databases');const select=$('db-candidate'),previous=select.value;select.replaceChildren();for(const c of data.candidates){const option=document.createElement('option');option.value=c.id;option.textContent=c.id+' · '+bytes(c.size);select.append(option);}if([...select.options].some(o=>o.value===previous))select.value=previous;if(!data.candidates.length){const o=document.createElement('option');o.value='';o.textContent='No SQL files found. Import source or a database file first.';select.append(o);}notice('Found '+data.candidates.length+' database candidates. Choose the full seed.');}
async function exportResult(result){if(result.file)await api('export',{path:result.file});notice('File exported. A local copy is retained.');}
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
action('start-server',()=>job('start'));action('stop-server',()=>job('stop'));
action('restart-server',async()=>{await job('stop');await job('start');});
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
async function browse(){const r=await api('files',{path:$('file-path').value.trim()});$('file-path').value=r.path==='.'?'':r.path;$('file-list').replaceChildren();for(const f of r.items){const row=document.createElement('tr'),name=document.createElement('td'),size=document.createElement('td'),select=document.createElement('td');if(f.directory){const b=document.createElement('button');b.className='folder';b.textContent='▸ '+f.name;b.onclick=()=>{$('file-path').value=f.path;browse().catch(e=>notice(e.message,true));};name.append(b);}else name.textContent=f.name;size.textContent=f.directory?'Folder':bytes(f.size);const b=document.createElement('button');b.className='secondary';b.textContent='Select';b.onclick=()=>{$('selected-file').value=f.path;};select.append(b);row.append(name,size,select);$('file-list').append(row);}}
action('file-go',browse);action('file-up',async()=>{$('file-path').value=$('file-path').value.split('/').slice(0,-1).join('/');await browse();});
action('file-upload',async()=>{const f=await api('pick',{kind:'file'});$('selected-file').value=f.path;$('file-path').value='incoming';await browse();notice('File imported. Set its destination, then Copy or Move.');});
for(const op of ['copy','move'])action('file-'+op,async()=>{await job('edit_file',{action:op,path:$('selected-file').value,destination:$('destination-file').value.trim()});await browse();});
action('file-export',()=>api('export',{path:$('selected-file').value}));
async function logs(){const name=$('log-name').value;const r=await api('logs',{name});const view=$('log-output');view.textContent=r.text;for(const entry of r.names||[]){if(![...$('log-name').options].some(o=>o.value===entry)){const option=document.createElement('option');option.value=option.textContent=entry;$('log-name').append(option);}}if($('follow-log').checked)view.scrollTop=view.scrollHeight;}
action('refresh-log',logs);$('log-name').addEventListener('change',()=>logs().catch(e=>notice(e.message,true)));
action('export-runtime-log',()=>api('export',{path:'logs/runtime.log'}));
setInterval(()=>{poll();if(currentTab==='logs'&&$('follow-log').checked)logs().catch(()=>{});},2500);poll();

action('fix-nektulos',()=>job('fix_nektulos'));
action('revert-nektulos',()=>job('revert_nektulos'));
action('session-export',async()=>{notice('Stopping the session and creating a complete backup…');const r=await api('session_backup');$('session-result').textContent='Local ZIP: '+r.file;await exportResult(r);notice('Complete session exported. Open runtime when you want to play again.');});
action('session-import',async()=>{const r=await api('pick',{kind:'session',replace:$('replace-session').checked});initialSettings=false;rulesLoaded=false;notice(r.message);window.location.reload();});
