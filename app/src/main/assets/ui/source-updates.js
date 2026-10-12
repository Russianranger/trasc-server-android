'use strict';
let sourceUpdateData=null,sourceUpdatePreview=null,sourceUpdateProfile=null,sourceUpdateLoading=false,sourceUpdateRefEdited=false;
function sourceUpdateBlocked(){return !!(busy||sessionAction||sourceUpdateLoading||!lastNative?.alive||lastNative.installing||lastNative.session_busy||!lastState||lastState.profile!==activeProfile||lastState.running||!lastClientNative||lastClientNative.alive||lastClientNative.busy||lastState.jobs?.some(j=>['queued','running'].includes(j.status)));}
function resetSourceUpdateProfile(){
 if(sourceUpdateProfile===activeProfile)return;
 sourceUpdateProfile=activeProfile;sourceUpdateData=null;sourceUpdatePreview=null;sourceUpdateRefEdited=false;
 $('source-update-status').textContent="Open this world's runtime to check for source updates.";
 $('source-update-revisions').textContent='';$('source-update-cache').textContent='';$('source-update-review').hidden=true;
 $('source-update-ref').value=lastState?.settings?.ref||'main';
}
function renderSourceUpdatesControls(){
 resetSourceUpdateProfile();const blocked=sourceUpdateBlocked(),world=activeProfile==='takp'?lastState?.takp:activeProfile==='traditional'?lastState?.traditional:null;
 const source=sourceUpdateData?.source_available??!!lastState?.source;
 $('source-update-refresh').disabled=!!(busy||sessionAction||sourceUpdateLoading||!lastNative?.alive||lastNative.installing||lastNative.session_busy);
 $('source-update-check').disabled=blocked||!source;$('source-update-ref').disabled=blocked;
 $('source-update-apply').disabled=blocked||!sourceUpdatePreview?.token||!sourceUpdatePreview.apply_allowed||sourceUpdatePreview.up_to_date||!!sourceUpdatePreview.conflict_count;
 const canBuild=source&&(!world||world.build?.build_allowed);
 $('source-update-build').disabled=blocked||!canBuild||!!sourceUpdateData?.requires_fresh_build;
 $('source-update-fresh').hidden=!sourceUpdateData?.requires_fresh_build;
 $('source-update-fresh').disabled=blocked||!canBuild||!sourceUpdateData?.requires_fresh_build;
 $('source-update-deploy').disabled=blocked||!sourceUpdateData?.update_build_ready;
}
function renderSourceUpdateReview(preview){
 sourceUpdatePreview=preview?.profile===activeProfile?preview:null;
 $('source-update-review').hidden=!sourceUpdatePreview;
 if(!sourceUpdatePreview){renderSourceUpdatesControls();return;}
 const p=sourceUpdatePreview,c=p.counts||{};
 $('source-update-counts').textContent=(p.from_commit||'Recorded source')+' → '+(p.to_commit||'Target revision')+' · '+(c.changed||0)+' changed · '+(c.added||0)+' added · '+(c.deleted||0)+' removed';
 const lines=[];for(const [kind,label] of [['changed','Change'],['added','Add'],['deleted','Remove']])for(const path of p.files?.[kind]||[])lines.push(label+' '+path);
 for(const conflict of p.conflicts||[])lines.push('Keep local edit: '+(typeof conflict==='string'?conflict:conflict.path||JSON.stringify(conflict)));
 $('source-update-files').textContent=lines.join('\n')||(p.up_to_date?'Source is already current.':'No file changes listed.');
 $('source-update-warning').textContent=(p.message||'')+(p.files_truncated?' The displayed file list is limited; the change counts cover the complete update.':'');
 renderSourceUpdatesControls();
}
async function loadSourceUpdates(){
 resetSourceUpdateProfile();if(!lastNative?.alive||lastNative.session_busy||lastNative.installing)return;
 const profile=activeProfile;sourceUpdateLoading=true;renderSourceUpdatesControls();
 try{
  const data=await api('source_update_status');if(profile!==activeProfile||data.profile&&data.profile!==profile)return;
  sourceUpdateData=data;$('source-update-status').textContent=data.message||(data.recovery_required?'A source update needs recovery before continuing.':data.source_available?'Review a source update before applying it.':'Import this world’s source in Setup first.');
  const current=data.current_revision||lastState?.source?.commit||'Not recorded',target=data.target_revision||lastState?.settings?.ref||'Recorded repository';
  $('source-update-revisions').textContent='Imported: '+current+' · Update target: '+target+(data.deployed_revision?' · Deployed: '+data.deployed_revision:'');
  $('source-update-cache').textContent=data.cache_message||'Compatible compiler output is reused; a missing or incompatible cache requires a fresh build.';
  if(activeProfile==='custom'&&!sourceUpdateRefEdited)$('source-update-ref').value=lastState?.settings?.ref||'main';
  if(data.preview)renderSourceUpdateReview(data.preview);
 }finally{sourceUpdateLoading=false;renderSourceUpdatesControls();}
}
$('source-update-ref').addEventListener('input',()=>{sourceUpdateRefEdited=true;sourceUpdatePreview=null;$('source-update-review').hidden=true;renderSourceUpdatesControls();});
action('source-update-refresh',loadSourceUpdates);
action('source-update-check',async()=>{
 sourceUpdatePreview=null;$('source-update-review').hidden=true;
 const args=activeProfile==='custom'?{ref:$('source-update-ref').value.trim()}:{};
 renderSourceUpdateReview(await job('source_update_preview',args));await loadSourceUpdates();
});
action('source-update-apply',async()=>{
 if(!sourceUpdatePreview?.token||sourceUpdatePreview.profile!==activeProfile)throw Error('Review this world’s source update first.');
 const result=await job('source_update_apply',{token:sourceUpdatePreview.token});
 sourceUpdatePreview=null;$('source-update-review').hidden=true;await loadSourceUpdates();notice(result.message||'Reviewed source changes applied. Current deployed binaries are retained.');
});
action('source-update-build',async()=>{const result=await job('build_update',{jobs:Number($('build-jobs').value)});await loadSourceUpdates();notice(result.message||'Updated binaries verified and staged. Deploy when ready.');});
action('source-update-deploy',async()=>{const result=await job('deploy_update');await loadSourceUpdates();notice(result.message||'Updated binaries deployed. Previous binaries retained.');});

action('source-update-fresh',async()=>{const result=await job('build_update',{jobs:Number($('build-jobs').value),allow_fresh:true});await loadSourceUpdates();notice(result.message||'Fresh build verified and staged. Previous compiler output and deployed binaries retained.');});
