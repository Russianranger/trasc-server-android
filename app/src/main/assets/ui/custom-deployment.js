'use strict';
// Each preview belongs to a single Custom profile and exact backend token. The
// backend repeats hash, destination and process checks before committing files.
const deploymentKinds={lon:{operation:'lon_data',title:'Legends of Norrath'},quest:{operation:'quest_sync',title:'Quest synchronization'}};
const deploymentModels=Object.fromEntries(Object.keys(deploymentKinds).map(key=>[key,{data:null,preview:null,report:null,loading:false,working:false,picking:false,nativeProgress:null,error:'',loadedAt:0,offset:0,total:0,rows:[],filesLoading:false,fileGeneration:0}]));
let customDeploymentProfile=null,customDeploymentGeneration=0,customDeploymentStatusLoading=false;
const deploymentClassLabels={new:'New',changed:'Changed',matching:'Matching',runtime_only:'Runtime only',error:'Error',conflict:'Local conflict'};
const deploymentGroupLabels={quests:'Quests',plugins:'Perl plugins',lua_modules:'Lua modules',lon_data:'Card data',data:'Card data',lon:'Card data'};
function deploymentClass(value){return String(value||'error').replaceAll('-','_');}
function deploymentSize(value){if(value==null)return 'Not present';const size=Number(value);return size<1024?size+' B':bytes(size);}
function deploymentDate(value){if(value==null||value==='')return 'Modified time unavailable';const date=typeof value==='number'?new Date(value*1000):new Date(value);return Number.isFinite(date.getTime())?date.toLocaleString():'Modified time unavailable';}
function deploymentSummary(report){return report?.summary||report?.totals||{};}
function deploymentCount(summary,key){return Number(summary?.[key]??(key==='errors'?summary?.error:0))||0;}
function deploymentContext(){return activeProfile==='custom'&&lastNative?.profile==='custom'&&lastNative.alive&&!lastNative.installing&&!lastNative.session_busy&&lastState?.profile==='custom';}
function deploymentBusy(){return !!(busy||sessionAction||customDeploymentStatusLoading||Object.values(deploymentModels).some(m=>m.working||m.picking)||lastState?.jobs?.some(j=>['queued','running'].includes(j.status))||lastClientNative?.busy);}
function deploymentRecovery(data){return !!(lastState?.custom_deployment_recovery_error||data?.recovery_required||data?.recovery_pending||data?.recovery_error||data?.recovery?.required||data?.recovery?.pending||data?.recovery?.error);}
function resetCustomDeploymentProfile(){
 if(customDeploymentProfile===activeProfile)return;
 customDeploymentProfile=activeProfile;customDeploymentGeneration++;
 for(const [key,m]of Object.entries(deploymentModels)){
  Object.assign(m,{data:null,preview:null,report:null,loading:false,working:false,picking:false,nativeProgress:null,error:'',loadedAt:0,offset:0,total:0,rows:[],filesLoading:false,fileGeneration:m.fileGeneration+1});
  $(key+'-preview').hidden=true;$(key+'-report').hidden=true;$(key+'-approve').checked=false;$(key+'-conflicts').checked=false;$(key+'-files').replaceChildren();$(key+'-files-status').textContent='';$(key+'-progress-detail').textContent='';
 }
 $('lon-source').value='client/current';$('quest-source-version').textContent='Source revision has not been inspected.';$('quest-last-sync').textContent='';
}
function deploymentSelection(key){const mode=key==='lon'?'both':$(key+'-mode').value;return {include_new:mode!=='changed',include_changed:mode!=='new'};}
function deploymentTransfer(key){
 const m=deploymentModels[key],s=deploymentSummary(m.preview),selection=deploymentSelection(key);
 const count=(selection.include_new?deploymentCount(s,'new'):0)+(selection.include_changed?deploymentCount(s,'changed'):0);
 const perClass=m.preview?.transfer||{};
 let size=null;
 if(perClass.new_bytes!=null||perClass.changed_bytes!=null)size=(selection.include_new?Number(perClass.new_bytes||0):0)+(selection.include_changed?Number(perClass.changed_bytes||0):0);
 else if(s.new_bytes!=null||s.changed_bytes!=null)size=(selection.include_new?Number(s.new_bytes||0):0)+(selection.include_changed?Number(s.changed_bytes||0):0);
 else if(selection.include_new&&selection.include_changed)size=s.bytes??perClass.bytes??null;
 return {count,bytes:size,changed:selection.include_changed?deploymentCount(s,'changed'):0,conflicts:selection.include_changed?deploymentCount(s,'conflicts'):0};
}
function renderDeploymentSource(){
 const m=deploymentModels.quest,s=m.preview?.source||m.preview?.extra?.source||m.data?.source||m.preview?.source_identity||{},last=m.data?.last_sync||m.data?.last_successful_sync||{};
 const revision=s.commit||s.revision||m.data?.current_commit;
 $('quest-source-version').textContent='Current source commit: '+(revision||'Not recorded')+(s.dirty===true?' · Source files changed since the last synchronization.':s.dirty===false?' · Source matches the last synchronization.':'');
 const commit=s.last_commit||last.commit||last.source?.commit||last.source?.revision||m.data?.last_sync_commit;
 const time=s.last_sync||last.completed_at||last.timestamp||last.date||m.data?.last_sync_at;
 $('quest-last-sync').textContent=commit?'Last successful sync: '+commit+(time?' · '+deploymentDate(time):''):'No successful quest synchronization is recorded.';
}
function renderCustomDeploymentControls(){
 resetCustomDeploymentProfile();$('custom-deployment').hidden=activeProfile!=='custom';if(activeProfile!=='custom')return;
 const context=deploymentContext(),blocked=!context||deploymentBusy(),running=!!lastState?.running;
 for(const [key,m]of Object.entries(deploymentModels)){
  const recovery=deploymentRecovery(m.data),summary=deploymentSummary(m.preview),transfer=deploymentTransfer(key);
  $(key+'-scan').disabled=blocked||m.loading||(key==='quest'&&m.data?.source_available===false);
  $(key+'-reload').disabled=blocked||m.loading;
  $(key+'-cancel').hidden=!(m.working||m.picking);$(key+'-cancel').disabled=m.cancelling===true;
  $(key+'-live-warning').hidden=!running;$(key+'-stop').hidden=!running;$(key+'-stop').disabled=blocked;
  $(key+'-recover').hidden=!recovery;$(key+'-recover').disabled=blocked;
  $(key+'-mode').disabled=key==='lon'||blocked||!m.preview;
  $(key+'-approve-row').hidden=!transfer.changed;$(key+'-conflicts-row').hidden=!transfer.conflicts;
  $(key+'-approve').disabled=blocked||!transfer.changed;$(key+'-conflicts').disabled=blocked||!transfer.conflicts;
  $(key+'-apply').disabled=blocked||running||recovery||!m.preview?.token||!transfer.count||!!deploymentCount(summary,'errors')||(transfer.changed&&!$(key+'-approve').checked)||(transfer.conflicts&&!$(key+'-conflicts').checked)||!!lastClientNative?.alive;
  $(key+'-transfer').textContent=m.preview?transfer.count.toLocaleString()+' selected files'+(transfer.bytes==null?'': ' · '+deploymentSize(transfer.bytes))+' to transfer. '+(transfer.changed?'Changed destination files are backed up before replacement. ':'')+'Runtime-only files are retained.':'';
  $(key+'-previous').disabled=blocked||m.filesLoading||m.offset===0;$(key+'-next').disabled=blocked||m.filesLoading||m.offset+m.rows.length>=m.total;
  $(key+'-start').disabled=blocked||running||!lastState?.binaries_ready||!lastState?.database_imported;
  for(const suffix of ['filter','sort','search'])$(key+'-'+suffix).disabled=blocked||!m.preview;
  let status=m.error||m.data?.source_error||m.data?.message||'';
  if(m.picking)status='Preparing selected card data. You can cancel while files are copied.';
  else if(m.working)status='Working… verified byte counts and progress appear below.';
  else if(!context)status='Open the Custom server runtime to inspect deployment files.';
  else if(m.loading)status='Inspecting this world’s deployment status…';
  else if(recovery)status=lastState?.custom_deployment_recovery_error||m.data?.recovery_error||'An interrupted deployment needs recovery. Stop the server, close and reopen the runtime, then refresh status.';
  else if(!status)status=m.preview?'Preview ready. Review the file list and selected changes before synchronizing.':'Ready to scan. No files have been changed.';
  if(lastClientNative?.alive&&!m.working&&!m.picking)status+=' Stop the client before deploying files.';
  $(key+'-status').textContent=status;
  renderDeploymentProgress(key);
 }
 for(const id of ['lon-use-client','lon-pick-folder','lon-pick-zip','lon-source'])$(id).disabled=blocked;
 $('quest-refresh-source').disabled=blocked;
 $('lon-verify').disabled=blocked||deploymentModels.lon.loading;
 renderDeploymentSource();
}
function renderDeploymentProgress(key,state=null){
 const m=deploymentModels[key],jobState=lastState?.jobs?.find(j=>['queued','running'].includes(j.status)&&j.operation?.startsWith(deploymentKinds[key].operation)),p=state||(m.picking?m.nativeProgress:null)||jobState?.progress;
 const shown=m.working||m.picking;$(key+'-progress').hidden=!shown;
 if(!shown){$(key+'-progress-detail').textContent='';return;}
 const done=Number(p?.bytes??p?.bytes_done??p?.copied_bytes??0),total=Number(p?.total??p?.total_bytes??p?.bytes_total??0),files=p?.files??p?.files_done??p?.copied_files;
 if(total>0){$(key+'-progress').max=total;$(key+'-progress').value=Math.min(done,total);}else $(key+'-progress').removeAttribute('value');
 $(key+'-progress-detail').textContent=[p?.message||p?.status||p?.phase||(m.picking?'Waiting for folder or document selection…':'Inspecting and verifying files…'),files!=null?files+' files':null,total>0?deploymentSize(done)+' / '+deploymentSize(total):done?deploymentSize(done):null].filter(Boolean).join(' · ');
}
async function loadCustomDeployment(force=false){
 resetCustomDeploymentProfile();if(!deploymentContext()||customDeploymentStatusLoading||deploymentBusy())return;
 const generation=customDeploymentGeneration;customDeploymentStatusLoading=true;
 const models=Object.entries(deploymentModels).filter(([,m])=>force||!m.loadedAt||Date.now()-m.loadedAt>15000);
 if(!models.length){customDeploymentStatusLoading=false;return;}
 for(const [,m]of models)m.loading=true;renderCustomDeploymentControls();
 try{await Promise.allSettled(models.map(async([key,m])=>{
  try{const result=await api(deploymentKinds[key].operation+'_status',{},20000);if(generation!==customDeploymentGeneration||activeProfile!=='custom'||result?.profile&&result.profile!=='custom')return;m.data=result;m.error='';m.loadedAt=Date.now();}
  catch(e){if(generation===customDeploymentGeneration){m.error=e.message;m.loadedAt=Date.now();}}
  finally{if(generation===customDeploymentGeneration)m.loading=false;}
 }));}finally{customDeploymentStatusLoading=false;renderCustomDeploymentControls();}
}
function checkCustomDeploymentStatus(){
 renderCustomDeploymentControls();if(activeProfile==='custom'&&currentTab==='setup'&&deploymentContext()&&!deploymentBusy())loadCustomDeployment().catch(e=>notice(e.message,true));
}
async function deploymentRun(key,operation,fn){
 const m=deploymentModels[key];if(!deploymentContext()||deploymentBusy())throw Error('Open the Custom runtime and wait for other operations to finish.');
 const generation=customDeploymentGeneration,previousJobs=new Set((lastState?.jobs||[]).map(j=>j.id));m.working=true;m.error='';busy++;activeUiActions.add('custom-deployment-'+key);renderSessionControls();renderCustomDeploymentControls();
 try{const result=await fn();if(generation!==customDeploymentGeneration||activeProfile!=='custom')return null;return result;}
 catch(e){if(generation===customDeploymentGeneration){m.error=e.message;if(['apply','scan','pick'].includes(operation)){const failed=[...(lastState?.jobs||[])].reverse().find(j=>!previousJobs.has(j.id)&&j.operation===deploymentKinds[key].operation+'_'+operation&&j.status==='error');renderDeploymentFailure(key,e,failed?.failure);}notice(e.message,true);}return null;}
 finally{m.working=false;m.picking=false;m.cancelling=false;busy--;activeUiActions.delete('custom-deployment-'+key);renderSessionControls();renderCustomDeploymentControls();poll().catch(()=>{});}
}
function renderDeploymentFailure(key,error,receipt){
 const m=deploymentModels[key],failure=receipt||{failed:true,copied_files:0,copied_bytes:0,recovery_required:false};m.report=failure;$(key+'-report').hidden=false;
 const destinations=failure.destinations||m.preview?.destinations||m.data?.destinations||m.data?.destination;
 const destination=typeof destinations==='string'?destinations:destinations?Object.entries(destinations).map(([kind,path])=>kind+': '+path).join(' · '):'Not resolved; no runtime copy started.';
 $(key+'-report-summary').textContent='Failed: '+(failure.error||error.message)+'. '+(failure.recovery_required?'Recovery is required; the final copied file and byte counts remain unverified.':failure.rolled_back?'Rollback completed. 0 files / 0 bytes remain changed by this operation.':'0 runtime files / 0 runtime bytes copied.')+' Destination: '+destination+(failure.backup?'. Protected backup: '+failure.backup:'');
 const list=$(key+'-validation');list.replaceChildren();
 if(failure.attempted_files!=null||failure.attempted_bytes!=null){const li=document.createElement('li');li.textContent='Transfer before recovery: '+Number(failure.attempted_files||0)+' files attempted · '+deploymentSize(failure.attempted_bytes||0)+' copied into temporary or runtime files. These are not retained deployment totals.';list.append(li);}
 const li=document.createElement('li');li.textContent=failure.recovery_required?'Refresh status and recover the interrupted deployment before starting the server or trying again.':'Review the error, refresh status and scan again before retrying.';list.append(li);$(key+'-start').hidden=true;
}
function clearDeploymentPreview(key){const m=deploymentModels[key];m.preview=null;m.rows=[];m.offset=0;m.total=0;m.fileGeneration++;$(key+'-preview').hidden=true;$(key+'-approve').checked=false;$(key+'-conflicts').checked=false;$(key+'-files').replaceChildren();}
function renderDeploymentPreview(key,report){
 const m=deploymentModels[key];m.preview=report;m.offset=0;m.rows=[];m.total=0;m.fileGeneration++;$(key+'-preview').hidden=!report?.token;
 $(key+'-approve').checked=false;$(key+'-conflicts').checked=false;
 const tbody=$(key+'-counts');tbody.replaceChildren();
 const rawGroups=Array.isArray(report.groups)?report.groups:Object.entries(report.group_summaries||report.groups||{}).map(([name,value])=>({name,...value}));
 const grouped=new Map();
 for(const group of rawGroups){const name=String(group.name||group.group||'Files').startsWith('lua_modules')?'lua_modules':group.name||group.group||'Files',counts=group.summary||group.counts||group.totals||group;if(!grouped.has(name))grouped.set(name,{name,summary:{}});const target=grouped.get(name).summary;for(const field of ['new','changed','matching','runtime_only','errors','conflicts'])target[field]=(target[field]||0)+deploymentCount(counts,field);}
 const groups=[...grouped.values()];
 for(const group of [...groups,{name:'Combined total',summary:deploymentSummary(report)}]){
  const row=document.createElement('tr'),counts=group.summary||group.counts||group.totals||group;
  const labels=['Files','New','Changed','Matching','Runtime only','Errors','Local conflicts'],values=[(group.name==='lua_modules'&&rawGroups.filter(item=>String(item.name||item.group).startsWith('lua_modules')).length>1?'Lua modules · all target folders':deploymentGroupLabels[group.name||group.group])||group.name||group.group||'Files',...['new','changed','matching','runtime_only','errors','conflicts'].map(k=>deploymentCount(counts,k).toLocaleString())];for(const [index,value]of values.entries()){const td=document.createElement('td');td.dataset.label=labels[index];td.textContent=value;row.append(td);}tbody.append(row);
 }
 const destinations=report.destinations||report.destination||report.extra?.destination||m.data?.destinations||m.data?.destination;
 $(key+'-destination').textContent='Destination: '+(typeof destinations==='string'?destinations:destinations?Object.entries(destinations).map(([name,value])=>name+': '+value).join(' · '):'Resolved by this world’s active runtime configuration');
 $(key+'-files-status').textContent='Expand to inspect the complete preview in pages of 40 files.';
 renderCustomDeploymentControls();
 if($(key+'-file-inspection').open)loadDeploymentFiles(key).catch(e=>deploymentFileError(key,e));
}
function deploymentFileError(key,e){deploymentModels[key].filesLoading=false;$(key+'-files-status').textContent=e.message;renderCustomDeploymentControls();}
async function scanDeployment(key){
 const m=deploymentModels[key];
 const report=await deploymentRun(key,'scan',async()=>{
  clearDeploymentPreview(key);m.report=null;$(key+'-report').hidden=true;
  return await job(deploymentKinds[key].operation+'_scan',key==='lon'?{source:$('lon-source').value.trim()||'client/current',kind:m.sourceKind||'auto'}:{});
 });
 if(report){renderDeploymentPreview(key,report);m.data={...m.data,message:'Preview ready. No runtime files were changed.'+(key==='lon'&&report.extra?.lon_rule?.enabled===false?' The active Custom:LoNEnabled rule disables the card service. File import does not enable it.':'')};renderCustomDeploymentControls();}
}
function deploymentMetadata(file,side){
 const obj=file[side]||{},short=side==='source'?'source':'destination';
 return {size:typeof obj==='object'?obj.size??obj.bytes??file[short+'_size']:file[short+'_size'],mtime:typeof obj==='object'?obj.mtime??obj.modified??file[short+'_mtime']:file[short+'_mtime']};
}
async function loadDeploymentFiles(key,offset=null){
 const m=deploymentModels[key];if(!m.preview?.token||activeProfile!=='custom'||!deploymentContext()||m.working||m.picking)return;
 const token=m.preview.token,generation=customDeploymentGeneration,fileGeneration=++m.fileGeneration;
 if(offset!=null)m.offset=Math.max(0,offset);m.filesLoading=true;$(key+'-files-status').textContent='Loading preview files…';renderCustomDeploymentControls();
 try{
  const result=await api(deploymentKinds[key].operation+'_files',{token,classification:$(key+'-filter').value.replace('runtime_only','runtime-only'),query:$(key+'-search').value.trim(),sort:({path:'filename',mtime_desc:'modified_desc'}[$(key+'-sort').value]||$(key+'-sort').value),offset:m.offset,limit:40},20000);
  if(generation!==customDeploymentGeneration||m.preview?.token!==token||fileGeneration!==m.fileGeneration)return;
  m.rows=result.files||result.rows||result.items||[];m.total=Number(result.total??result.count??m.rows.length);m.offset=Number(result.offset??m.offset);
  $(key+'-files').replaceChildren(...m.rows.map(file=>deploymentFileElement(key,file)));
  $(key+'-files-status').textContent=m.total?('Files '+(m.offset+1)+'–'+(m.offset+m.rows.length)+' of '+m.total.toLocaleString()+'. Every proposed replacement is available in this list.'):'No files match this filter.';
 }finally{if(generation===customDeploymentGeneration&&fileGeneration===m.fileGeneration){m.filesLoading=false;renderCustomDeploymentControls();}}
}
function deploymentFileElement(key,file){
 const item=document.createElement('div');item.className='deployment-file';
 const header=document.createElement('div');header.className='deployment-file-title';
 const badge=document.createElement('span'),classification=deploymentClass(file.classification||file.status);badge.className='deployment-class';badge.dataset.class=classification;badge.textContent=deploymentClassLabels[classification]||classification;
 const name=document.createElement('code');name.textContent=(file.group?((deploymentModels[key].preview?.group_labels?.[file.group]||deploymentGroupLabels[file.group]||file.group)+'/'):'')+(file.path||file.relative_path||'Unknown path');header.append(badge,name);item.append(header);
 if(file.conflict||file.local_modification){const conflict=document.createElement('small');conflict.className='deployment-conflict';conflict.textContent='Local modification · explicit approval required before replacement';item.append(conflict);}
 const metadata=document.createElement('div');metadata.className='deployment-file-meta';
 for(const [side,label]of [['source','Source'],['destination','Runtime']]){const fields=deploymentMetadata(file,side),text=document.createElement('small');text.textContent=label+': '+deploymentSize(fields.size)+(fields.size!=null?' · '+deploymentDate(fields.mtime):'');metadata.append(text);}item.append(metadata);
 const inspectionErrors=[file.error,file.source?.error,file.destination?.error].filter(Boolean);if(inspectionErrors.length){const error=document.createElement('small');error.className='deployment-file-error';error.textContent=[...new Set(inspectionErrors)].join(' · ');item.append(error);}
 if(key==='quest'&&classification==='changed'&&/\.(pl|pm|lua|ini|json|conf|cfg|txt|xml|csv)$/i.test(file.path||file.relative_path||'')){
  const button=document.createElement('button');button.className='secondary';button.textContent='Show text diff';
  button.addEventListener('click',async()=>{
   if(button.dataset.loaded){const diff=item.querySelector('pre');diff.hidden=!diff.hidden;button.textContent=diff.hidden?'Show text diff':'Hide text diff';return;}
   const token=deploymentModels[key].preview?.token,generation=customDeploymentGeneration;button.disabled=true;
   try{const result=await api('quest_sync_diff',{token,group:file.group,path:file.path||file.relative_path},20000);if(generation!==customDeploymentGeneration||deploymentModels[key].preview?.token!==token)return;const pre=document.createElement('pre');pre.className='deployment-diff';pre.textContent=(typeof result==='string'?result:result.diff||result.text||result.message||'No text diff available.')+(result.truncated?'\nDiff is limited; inspect the files before approving.':'');item.append(pre);button.dataset.loaded='true';button.textContent='Hide text diff';}
   catch(e){notice(e.message,true);}finally{button.disabled=false;}
  });item.append(button);
 }
 return item;
}
function renderDeploymentReport(key,result){
 const m=deploymentModels[key];m.report=result;$(key+'-report').hidden=false;
 const verification=key==='lon'&&!!result.service;
 const summary=result.result||result.deployment||result,s=summary.summary||summary;
 const copied=summary.files_copied??summary.copied_files??s.files??s.new_files;
 const size=summary.bytes_copied??summary.copied_bytes??s.bytes;
 const destination=result.destinations||result.destination||m.preview?.destinations||m.preview?.destination||m.data?.destination;
 const label=typeof destination==='string'?destination:destination?Object.entries(destination).map(([k,v])=>k+': '+v).join(' · '):'';
 $(key+'-report-summary').textContent=(result.message||(verification?'Card data and card-service status inspected.':'Deployment completed and copied files were verified.'))+(copied!=null?' '+copied+' files copied.':'')+(size!=null?' '+deploymentSize(size)+'.':'')+(label?' Destination: '+label+'.':'')+(result.backup?' Protected backup: '+result.backup+'.':'')+(verification?'':' Start the server and inspect its logs to verify service initialization.');
 const validation=$(key+'-validation');validation.replaceChildren();
 const features=result.features?.features||result.features||result.extra?.features?.features||result.extra?.features||[];
 const stateLabels={source_present_deployed:'Present in source and deployed successfully',source_present_not_deployed:'Present in source but not deployed',database_or_server_code:'Database/server-code feature; no corresponding quest deployment',missing_or_additional_setup:'Missing or requiring additional setup'};
 if(Array.isArray(features))for(const feature of features){const li=document.createElement('li');li.textContent=(feature.update?feature.update+' · ':'')+(feature.name||feature.title||'Feature')+': '+(stateLabels[feature.state]||feature.state||'Check required')+(feature.note?' — '+feature.note:'');const files=feature.files||[];if(files.length){const details=document.createElement('details'),title=document.createElement('summary');title.textContent=files.length+' inspected source files';details.append(title);const paths=document.createElement('pre');paths.className='deployment-diff';paths.textContent=files.map(f=>typeof f==='string'?f:(f.source||f.path||'')+' → '+(f.destination||'')+' · '+(f.state||'')+(f.destinations?.length?'\n'+f.destinations.map(d=>'  '+d.path+' · '+d.state+(d.error?' · '+d.error:'')).join('\n'):'' )).join('\n');details.append(paths);li.append(details);}validation.append(li);}
 if(key==='lon'&&(result.lon_rule||result.extra?.lon_rule)?.enabled===false){const li=document.createElement('li');li.textContent='Additional setup required: the active Custom:LoNEnabled rule disables the card service. '+(verification?'Verification does not change this database rule.':'Files were deployed without changing this database rule.');validation.append(li);}
 const v=result.validation||result.extra?.validation;
 if(v){for(const text of [v.valid?'Card data structure and server-required records validated.':'Card data validation needs attention.',...(v.errors||[]),...(v.warnings||[])]){const li=document.createElement('li');li.textContent=text;validation.append(li);}}
 if(key==='lon'){
  const service=result.service||{},state=service.state||result.server_initialization||v?.server_initialization||'pending_restart';
  const labels={confirmed:'Card service initialized successfully in the current server session.',failed:'Card-service startup failed. Review its log evidence and the card-data validation report.',pending_restart:'Card-service initialization remains pending until the server is started after deployment and its logs confirm success.',disabled:'Card service is disabled by the active Custom:LoNEnabled rule.'};
  const row=document.createElement('li');row.dataset.serviceState=state;row.textContent=labels[state]||'Card-service initialization could not be confirmed.';validation.append(row);
  if(service.evidence){const evidence=document.createElement('li');evidence.textContent='Server log evidence: '+service.evidence;validation.append(evidence);}
  if(service.log_warning){const warning=document.createElement('li');warning.textContent='Service verification: '+service.log_warning;validation.append(warning);}
  for(const warning of result.cleanup?.warnings||[]){const row=document.createElement('li');row.textContent=warning;validation.append(row);}
  if(result.cleanup?.removed?.length){const row=document.createElement('li');row.textContent='Temporary import copies were removed after successful deployment. Your original client or SD data was retained. Choose the folder or ZIP again to preview another import.';validation.append(row);}
 }
 $(''+key+'-start').hidden=verification&&result.server_initialization!=='pending_restart';
}
async function applyDeployment(key){
 const m=deploymentModels[key],preview=m.preview,selection=deploymentSelection(key),transfer=deploymentTransfer(key);
 if(!preview?.token)throw Error('Scan and review this world’s files first.');
 if(lastState?.running)throw Error('Stop the server before deploying files.');
 if(lastClientNative?.alive)throw Error('Stop the client before deploying files.');
 if(deploymentRecovery(m.data))throw Error('Recover the interrupted deployment before synchronizing.');
 if(transfer.changed&&!$(key+'-approve').checked)throw Error('Review the changed files and approve replacement first.');
 if(transfer.conflicts&&!$(key+'-conflicts').checked)throw Error('Locally modified files require separate explicit approval.');
 if(!window.confirm('Synchronize '+transfer.count+' selected files'+(transfer.bytes!=null?' ('+deploymentSize(transfer.bytes)+')':'')+' to this Custom world?'+(transfer.changed?' Changed files will be backed up.':'')+' Runtime-only files will be kept.'))return;
 const token=preview.token;
 const result=await deploymentRun(key,'apply',()=>job(deploymentKinds[key].operation+'_apply',{token,...selection,confirm_overwrite:!!$(key+'-approve').checked,approve_conflicts:!!$(key+'-conflicts').checked}));
 if(result){renderDeploymentReport(key,result);clearDeploymentPreview(key);m.data=null;m.loadedAt=0;await loadCustomDeployment(true);renderCustomDeploymentControls();}else{clearDeploymentPreview(key);m.loadedAt=0;renderCustomDeploymentControls();}
}
async function pickDeploymentSource(kind){
 await deploymentRun('lon','pick',async()=>{
  const m=deploymentModels.lon;m.picking=true;m.nativeProgress=null;renderCustomDeploymentControls();
  const generation=customDeploymentGeneration;
  let querying=false;
  const timer=setInterval(async()=>{if(querying)return;querying=true;try{const progress=await api('lon_input_state',{},10000);if(generation===customDeploymentGeneration&&m.picking){m.nativeProgress=progress;renderDeploymentProgress('lon',progress);}}catch{}finally{querying=false;}},600);
  try{
   const result=await api('pick',{kind:kind==='directory'?'lon-data-folder':'lon-data-zip'});
   if(generation!==customDeploymentGeneration||!result)return;
   if(result.cancelled){m.data={...m.data,message:result.message||'File selection cancelled. No server files were changed.'};return;}
   const source=result.source||result.path;if(!source)throw Error('The selected data did not produce a readable source.');
   $('lon-source').value=source;m.sourceKind=result.kind||kind;clearDeploymentPreview('lon');m.report=null;$('lon-report').hidden=true;
   m.data={...m.data,message:'Selected '+(result.name||source)+(result.files!=null?' · '+result.files+' files':'')+(result.bytes!=null?' · '+deploymentSize(result.bytes):'')+'. Preview the import before copying into the server.'};
  }finally{clearInterval(timer);m.picking=false;}
 });
}
function deploymentBind(id,fn){$(id).addEventListener('click',()=>Promise.resolve().then(fn).catch(e=>notice(e.message,true)));}
for(const key of Object.keys(deploymentKinds)){
 deploymentBind(key+'-scan',()=>scanDeployment(key));deploymentBind(key+'-reload',()=>loadCustomDeployment(true));deploymentBind(key+'-apply',()=>applyDeployment(key));
 deploymentBind(key+'-cancel',async()=>{const m=deploymentModels[key];if(!m.working&&!m.picking)return;m.cancelling=true;renderCustomDeploymentControls();try{await api(m.picking?'lon_input_cancel':'cancel');notice('Cancellation requested. Files already touched are recovered before another deployment.');}finally{m.cancelling=false;renderCustomDeploymentControls();}});
 deploymentBind(key+'-stop',async()=>{if(!lastState?.running)return;if(!window.confirm('Stop this Custom server before deployment? You can start it again after synchronizing.'))return;await deploymentRun(key,'stop',()=>job('stop'));clearDeploymentPreview(key);deploymentModels[key].loadedAt=0;await loadCustomDeployment(true);notice('Server stopped. Scan again to review the current files before deploying.');});
 deploymentBind(key+'-start',()=>deploymentRun(key,'start',()=>job('start')));
 deploymentBind(key+'-recover',async()=>{if(lastState?.running)throw Error('Stop the server before recovering a deployment.');const result=await deploymentRun(key,'recover',()=>job('custom_deployment_recover'));if(result){clearDeploymentPreview(key);await loadCustomDeployment(true);notice(result.message||'Interrupted deployment recovery completed. Scan again before synchronizing.');}});
 for(const suffix of ['approve','conflicts'])$(key+'-'+suffix).addEventListener('change',renderCustomDeploymentControls);
 $(key+'-mode').addEventListener('change',()=>{$(key+'-approve').checked=false;$(key+'-conflicts').checked=false;renderCustomDeploymentControls();});
 for(const suffix of ['filter','sort'])$(key+'-'+suffix).addEventListener('change',()=>loadDeploymentFiles(key,0).catch(e=>deploymentFileError(key,e)));
 let searchTimer;$(key+'-search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>loadDeploymentFiles(key,0).catch(e=>deploymentFileError(key,e)),250);});
 $(key+'-file-inspection').addEventListener('toggle',()=>{if($(key+'-file-inspection').open)loadDeploymentFiles(key).catch(e=>deploymentFileError(key,e));});
 deploymentBind(key+'-previous',()=>loadDeploymentFiles(key,deploymentModels[key].offset-40));deploymentBind(key+'-next',()=>loadDeploymentFiles(key,deploymentModels[key].offset+40));
}
deploymentBind('lon-verify',async()=>{const result=await deploymentRun('lon','verify',()=>job('lon_data_verify'));if(result){renderDeploymentReport('lon',result);renderCustomDeploymentControls();}});
deploymentBind('lon-pick-folder',()=>pickDeploymentSource('directory'));deploymentBind('lon-pick-zip',()=>pickDeploymentSource('zip'));
deploymentBind('lon-use-client',()=>{$('lon-source').value='client/current';deploymentModels.lon.sourceKind='auto';clearDeploymentPreview('lon');renderCustomDeploymentControls();});
$('lon-source').addEventListener('input',()=>{deploymentModels.lon.sourceKind='auto';clearDeploymentPreview('lon');renderCustomDeploymentControls();});
deploymentBind('quest-refresh-source',()=>{
 clearDeploymentPreview('quest');tab('build');const panel=$('source-updates-panel');
 const outer=panel.closest('details');if(outer)outer.open=true;panel.scrollIntoView({behavior:'smooth',block:'start'});
 notice('Review the saved repository and selected branch, tag or commit in Updates. Check source update, review it, and apply it before scanning quests again.');
 $('source-update-ref').focus({preventScroll:true});
});
Object.assign(operationLabels,{lon_data_scan:'Inspecting Legends of Norrath data',lon_data_apply:'Deploying Legends of Norrath data',lon_data_verify:'Verifying card data and current card service',quest_sync_scan:'Comparing quests, plugins and Lua modules',quest_sync_apply:'Synchronizing quests, plugins and Lua modules'});
renderCustomDeploymentControls();
