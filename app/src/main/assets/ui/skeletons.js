'use strict';
let takpSkeletonData=null,takpSkeletonProfile=null,takpSkeletonLoading=false,takpSkeletonDirty=false;
function renderTakpSkeletonControls(){
 if(takpSkeletonProfile!==activeProfile){takpSkeletonProfile=activeProfile;takpSkeletonData=null;takpSkeletonDirty=false;$('takp-skeleton-enabled').checked=false;$('takp-skeleton-status').textContent='Import a TAKP client and open the server runtime to check the model archives.';}
 const workspace=activeProfile==='takp'&&lastNative?.alive&&!lastNative.installing&&!lastNative.session_busy&&lastState?.profile==='takp';
 const blocked=!!(busy||sessionAction||clientFileBusy||takpSkeletonLoading||!workspace||!lastClientNative||lastClientNative.alive||lastClientNative.busy||lastState?.jobs?.some(j=>['queued','running'].includes(j.status)));
 $('takp-skeleton-refresh').disabled=!!(busy||sessionAction||takpSkeletonLoading||!workspace);
 $('takp-skeleton-enabled').disabled=blocked||!takpSkeletonData?.available;
 const desired=$('takp-skeleton-enabled').checked,enabled=!!takpSkeletonData?.enabled;
 $('takp-skeleton-apply').disabled=blocked||desired===enabled||(desired?!takpSkeletonData?.available:!takpSkeletonData?.restore_available);
 $('takp-skeleton-restore').disabled=blocked||!takpSkeletonData?.restore_available;
}
function renderTakpSkeletonStatus(data){
 if(activeProfile!=='takp')return;renderTakpSkeletonControls();takpSkeletonData=data;
 $('takp-skeleton-status').textContent=data.message||data.error||(data.enabled?'classic skeleton models enabled.':'Original skeleton models selected.');
 if(!takpSkeletonDirty)$('takp-skeleton-enabled').checked=!!data.enabled;
 renderTakpSkeletonControls();
}
async function loadTakpSkeletons(){
 if(activeProfile!=='takp'||!lastNative?.alive||lastNative.installing||lastNative.session_busy)return;
 const profile=activeProfile;takpSkeletonLoading=true;renderTakpSkeletonControls();
 try{const data=await api('takp_skeleton_status');if(profile===activeProfile)renderTakpSkeletonStatus(data);}
 finally{takpSkeletonLoading=false;renderTakpSkeletonControls();}
}
async function saveTakpSkeletons(enabled){
 const result=await job('set_takp_skeletons',{enabled});takpSkeletonDirty=false;
 if(result.skeletons)renderTakpSkeletonStatus(result.skeletons);else await loadTakpSkeletons();
 notice(result.message||'Skeleton model choice saved.');
}
$('takp-skeleton-enabled').addEventListener('change',()=>{takpSkeletonDirty=true;renderTakpSkeletonControls();});
action('takp-skeleton-refresh',loadTakpSkeletons);
action('takp-skeleton-apply',()=>saveTakpSkeletons($('takp-skeleton-enabled').checked));
action('takp-skeleton-restore',()=>saveTakpSkeletons(false));
