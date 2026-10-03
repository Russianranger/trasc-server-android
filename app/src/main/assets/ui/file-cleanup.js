'use strict';
let cleanupSelection=new Set(),cleanupEntries=[],cleanupScope=null,cleanupPreview=null,cleanupGeneration=0,cleanupWorking=false;
function cleanupStopped(){return !!lastNative&&!!lastClientNative&&!lastNative.alive&&!lastNative.installing&&!lastNative.session_busy&&!lastClientNative.alive&&!lastClientNative.busy;}
function cleanupInvalidate(){
 cleanupGeneration++;cleanupPreview=null;$('cleanup-confirm').hidden=true;$('cleanup-understand').checked=false;
 cleanupControls();
}
function cleanupReset(){cleanupSelection.clear();cleanupEntries=[];cleanupScope=null;cleanupInvalidate();}
function cleanupPage(entries,path,query){
 const scope=(activeProfile||'custom')+'\0'+path+'\0'+query;
 if(scope!==cleanupScope){cleanupSelection.clear();cleanupScope=scope;}
 cleanupEntries=entries;cleanupControls();
}
function cleanupCell(entry){
 const cell=document.createElement('td');
 if(entry.deletable){
  const input=document.createElement('input');input.type='checkbox';input.dataset.deletePath=entry.path;input.setAttribute('aria-label','Delete '+entry.name);
  input.checked=cleanupSelection.has(entry.path);input.disabled=cleanupWorking;
  input.addEventListener('change',()=>{if(input.checked&&cleanupSelection.size>=500){input.checked=false;notice('Review and delete up to 500 copies at a time.',true);return;}if(input.checked)cleanupSelection.add(entry.path);else cleanupSelection.delete(entry.path);cleanupInvalidate();});cell.append(input);
 }else{const label=document.createElement('button');label.className='folder';label.textContent='Protected';label.setAttribute('aria-label','Why is '+entry.name+' protected?');label.onclick=()=>notice(entry.protection||'Required by the app');cell.append(label);}
 return cell;
}
function cleanupControls(){
 const count=cleanupSelection.size,blocked=cleanupWorking||!!busy;
 $('cleanup-review').disabled=blocked||!count||!cleanupStopped();
 $('cleanup-select-page').disabled=blocked||!cleanupEntries.some(e=>e.deletable);
 $('cleanup-clear-selection').disabled=blocked||!count;
 $('cleanup-delete').disabled=blocked||!cleanupPreview||!$('cleanup-understand').checked||!cleanupStopped();
 $('cleanup-cancel').disabled=cleanupWorking;
 $('cleanup-status').textContent=cleanupWorking?'Checking and removing selected copies…':count?count+' copies selected. '+(cleanupStopped()?'Review their size before deleting.':'Stop the client and server runtime to review deletion.'):'Select removable files using their Delete checkboxes below.';
 for(const input of document.querySelectorAll('[data-delete-path]'))input.disabled=cleanupWorking;
}
for(const [id,path] of [['cleanup-backups','backups'],['cleanup-exports','exports'],['cleanup-incoming','incoming'],['cleanup-prefix','client/prefix-backups']]){
 $(id).addEventListener('click',()=>{cleanupReset();$('file-path').value=path;$('file-search').value='';browse().catch(e=>notice(e.message,true));});
}
$('cleanup-select-page').addEventListener('click',()=>{
 for(const e of cleanupEntries)if(e.deletable&&cleanupSelection.size<500)cleanupSelection.add(e.path);
 for(const input of document.querySelectorAll('[data-delete-path]'))input.checked=cleanupSelection.has(input.dataset.deletePath);
 cleanupInvalidate();
});
$('cleanup-clear-selection').addEventListener('click',()=>{cleanupSelection.clear();for(const input of document.querySelectorAll('[data-delete-path]'))input.checked=false;cleanupInvalidate();});
$('cleanup-understand').addEventListener('change',cleanupControls);
$('cleanup-cancel').addEventListener('click',cleanupInvalidate);
$('cleanup-review').addEventListener('click',async()=>{
 cleanupInvalidate();const generation=cleanupGeneration,profile=activeProfile,paths=[...cleanupSelection].sort();
 if(!paths.length||!cleanupStopped())return;
 cleanupWorking=true;busy++;renderSessionControls();
 try{
  const review=await api('file_delete_preview',{paths});
  if(generation!==cleanupGeneration||profile!==activeProfile)return;
  if(!review.token||!Array.isArray(review.paths))throw Error('Deletion preview was incomplete. Refresh and retry.');
  cleanupPreview={...review,profile};$('cleanup-summary').textContent=review.paths.length+' copies · '+review.files+' files · '+bytes(review.bytes)+' to remove. This cannot be undone.';
  $('cleanup-paths').textContent=review.paths.join('\n');$('cleanup-confirm').hidden=false;
 }catch(e){notice(e.message,true);}
 finally{cleanupWorking=false;busy--;renderSessionControls();}
});
$('cleanup-delete').addEventListener('click',async()=>{
 const review=cleanupPreview;
 if(!review||review.profile!==activeProfile||!$('cleanup-understand').checked||!cleanupStopped())return;
 cleanupWorking=true;busy++;renderSessionControls();
 try{
  const r=await api('file_delete',{paths:review.paths,token:review.token});
  cleanupReset();await browse();notice(r.message+' Removed '+bytes(r.bytes)+'.');
 }catch(e){cleanupInvalidate();notice(e.message,true);await browse().catch(()=>{});}
 finally{cleanupWorking=false;busy--;renderSessionControls();poll().catch(()=>{});}
});
cleanupControls();
