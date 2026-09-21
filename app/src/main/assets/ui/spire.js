'use strict';
const spireState={loaded:false,working:false,table:'items',filters:{},offset:0,next:null,record:null,preview:null,dirty:false,historyNext:null,itemOffset:0,itemNext:null};
const spireText=value=>value===null?'NULL':value===undefined?'—':String(value);
function spireElement(tag,text,className){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(className)e.className=className;return e;}
function spireInvalidate(){spireState.preview=null;$('spire-preview-panel').hidden=true;$('spire-save').disabled=true;}
function spireDirty(){spireState.dirty=true;spireInvalidate();}
function spireDiscardAllowed(){return !spireState.dirty||window.confirm('Discard the unsaved changes to this record?');}
async function spireRun(fn){
 if(spireState.working)return;spireState.working=true;const controls=[...$('spire').querySelectorAll('button,input,select,textarea')],disabled=controls.map(e=>e.disabled);controls.forEach(e=>e.disabled=true);
 try{await fn();}catch(e){$('spire-status').textContent=e.message;notice(e.message,true);}
 finally{controls.forEach((e,i)=>{if(e.isConnected)e.disabled=disabled[i];});spireState.working=false;spireControls();}
}
function spireControls(){
 if(typeof syncProfileControls==='function')syncProfileControls();
 $('spire-prev').disabled=spireState.offset===0;$('spire-next').disabled=spireState.next===null;
 $('spire-save').disabled=!spireState.preview;
 $('spire-item-prev').disabled=spireState.itemOffset===0;$('spire-item-next').disabled=spireState.itemNext===null;
 if(spireState.record){$('spire-preview').disabled=!!spireState.record.read_only;$('spire-delete').disabled=!!spireState.record.read_only;}
}
function spireBind(id,fn){$(id).addEventListener('click',()=>spireRun(fn));}
function spireExportStatus(data){$('spire-export-status').textContent=(data.pending_export?data.pending_export+' saved edit(s) need client export. ':'No content edits are awaiting client export. ')+(data.compatibility===undefined?'':data.compatibility?'RoF2 spell compatibility is ON. ':'RoF2 spell compatibility is OFF. ')+'Export uses the existing four-file workflow and preserves that setting. AA definitions/effects require a server restart and a new login.';}
async function spireCatalog(){
 const data=await job('spire_catalog');const choice=$('spire-type');choice.replaceChildren();
 for(const e of data.entities){const o=spireElement('option',e.label+(e.available?'':' · unavailable'));o.value=e.table;o.disabled=!e.available;choice.append(o);}
 if([...choice.options].some(o=>o.value===spireState.table&&!o.disabled))choice.value=spireState.table;
 else choice.value=[...choice.options].find(o=>!o.disabled)?.value||'';
 spireState.table=choice.value;spireExportStatus(data);spireState.loaded=true;
}
async function loadSpire(){if(spireState.loaded||spireState.working)return;await spireRun(async()=>{await spireCatalog();if(spireState.table)await spireSearch(0);});}
async function spireSearch(offset){
 const r=await job('spire_search',{table:spireState.table,query:$('spire-query').value,filters:spireState.filters,offset});
 spireState.offset=r.offset;spireState.next=r.next_offset;spireState.schema=r;
 $('spire-filter').hidden=!Object.keys(spireState.filters).length;$('spire-filter-text').textContent='Related records: '+Object.entries(spireState.filters).map(([k,v])=>k+' = '+v).join(', ');
 $('spire-new').hidden=!r.add;$('spire-new').textContent=r.table==='merchantlist'?'Add item to merchant':'Add record';$('spire-status').textContent=r.records.length?`Showing ${r.offset+1}–${r.offset+r.records.length}${r.next_offset===null?' · end of results':''}. ${r.read_only||''}`:'No matching records. '+(r.read_only||'');
 const head=spireElement('tr');for(const c of r.columns)head.append(spireElement('th',c.replaceAll('_',' ')));head.append(spireElement('th',''));$('spire-columns').replaceChildren(head);$('spire-results').replaceChildren();
 for(const item of r.records){const row=spireElement('tr');for(const c of r.columns){const text=spireText(item.values[c]);const cell=spireElement('td',text.length>140?text.slice(0,140)+'…':text);row.append(cell);}const cell=spireElement('td');const button=spireElement('button','Open','secondary');button.disabled=!r.key.length;button.onclick=()=>spireRun(async()=>{if(spireDiscardAllowed())await spireOpen(item.key);});cell.append(button);row.append(cell);$('spire-results').append(row);}
 spireControls();
}
async function spireOpen(key){const r=await job('spire_detail',{table:spireState.table,key});spireShowRecord(r,false);}
function spireShowRecord(r,isNew){
 spireState.record={...r,isNew};spireState.dirty=false;spireInvalidate();$('spire-record').hidden=false;
 $('spire-record-title').textContent=(isNew?'Add to ':'Edit ')+r.label+(!isNew?' · '+r.key.map(k=>r.values[k]).join(' / '):'');
 $('spire-impact').textContent=r.impact;$('spire-warning').textContent=(r.warnings||[]).join(' ');$('spire-readonly').textContent=r.read_only||'Only the fields below can be changed. Other fields are preserved.';
 $('spire-delete').hidden=isNew||!r.remove;$('spire-links').replaceChildren();
 for(const link of r.links||[]){const b=spireElement('button',link.label,'secondary');b.onclick=()=>spireRun(async()=>{if(!spireDiscardAllowed())return;spireState.dirty=false;spireState.table=link.table;spireState.filters=link.filters;$('spire-type').value=link.table;$('spire-query').value='';spireClose();await spireSearch(0);});$('spire-links').append(b);}
 if(r.table==='merchantlist'&&!isNew&&!r.read_only){const b=spireElement('button','Add another item to this merchant');b.onclick=()=>spireRun(async()=>{if(spireDiscardAllowed())await spireNewMerchant(r.values.merchantid);});$('spire-links').prepend(b);}
 if(r.table==='npc_types'&&Number(r.values?.merchant_id)>0){const b=spireElement('button','Add item to this merchant');b.onclick=()=>spireRun(async()=>{if(!spireDiscardAllowed())return;await spireNewMerchant(r.values.merchant_id);});$('spire-links').prepend(b);}
 $('spire-item-picker').hidden=r.table!=='merchantlist'||!!r.read_only;
 $('spire-merchant-slot').hidden=!isNew;
 $('spire-item-results').replaceChildren();$('spire-item-query').value='';spireState.itemOffset=0;spireState.itemNext=null;
 $('spire-item-selected').textContent=r.values?.item?'Current item ID: '+r.values.item:'Choose an item below or enter its ID in the Item field.';
 $('spire-fields').replaceChildren();$('spire-field-filter').value='';
 for(const field of r.fields){
  const box=spireElement('div',undefined,'spire-field');box.dataset.field=field.name;
  const label=spireElement('label',field.label+(field.key?' · key':''));const id='spire-field-'+field.name;label.htmlFor=id;
  const value=(r.values||{})[field.name];const input=spireElement(/text|value|description/.test(field.type+' '+field.name)?'textarea':'input');input.id=id;input.name=field.name;input.value=value??'';input.dataset.touched='false';
  input.readOnly=!!r.read_only||(!isNew&&!field.editable);if(input.tagName==='INPUT'){input.type='text';if(/int|float|double|decimal/.test(field.type))input.inputMode='decimal';}
  if(field.length)input.maxLength=Math.min(field.length,32768);if(isNew)input.placeholder=field.required?'Required':'Database default';
  input.addEventListener('input',()=>{input.dataset.touched='true';spireDirty();if(r.table==='merchantlist'&&field.name==='item')$('spire-item-selected').textContent='Item ID: '+input.value;if(r.table==='merchantlist'&&isNew&&field.name==='merchantid')$('spire-warning').textContent='Inventory changed. Use next free slot before previewing. This inventory may be shared by several NPCs.';});box.append(label,input);
  if(field.nullable&&!input.readOnly){const l=spireElement('label',undefined,'check');const n=spireElement('input');n.type='checkbox';n.className='spire-null';n.checked=value===null;n.onchange=()=>{input.disabled=n.checked;input.dataset.touched='true';spireDirty();};input.disabled=n.checked;l.append(n,document.createTextNode('NULL'));box.append(l);}
  box.append(spireElement('small',field.type+(field.min!==null&&field.min!==undefined?' · minimum '+field.min:'')+(field.max!==null&&field.max!==undefined?' · maximum '+field.max:'')));$('spire-fields').append(box);
 }
 const editable=new Set(r.fields.map(f=>f.name));$('spire-other').textContent=Object.entries(r.values||{}).filter(([k])=>!editable.has(k)).map(([k,v])=>k+': '+spireText(v)).join('\n')||'No other fields.';
 spireControls();$('spire-record').scrollIntoView({block:'start',behavior:'smooth'});
}
function spireClose(){spireState.record=null;spireState.dirty=false;spireInvalidate();$('spire-record').hidden=true;}
function spireSetField(name,value){const e=$('spire-field-'+name);e.value=value;e.dataset.touched='true';const n=e.closest('.spire-field').querySelector('.spire-null');if(n){n.checked=false;e.disabled=false;}spireDirty();}
async function spireNewMerchant(merchant){
 const r=await job('spire_merchant_draft',{merchantid:merchant});
 spireState.table='merchantlist';spireState.filters={merchantid:merchant};$('spire-type').value='merchantlist';$('spire-query').value='';await spireSearch(0);
 spireShowRecord(r,true);$('spire-item-query').focus();
}
async function spireItems(offset){
 const r=await job('spire_search',{table:'items',query:$('spire-item-query').value,offset});
 spireState.itemOffset=r.offset;spireState.itemNext=r.next_offset;$('spire-item-results').replaceChildren();
 if(!r.records.length)$('spire-item-results').append(spireElement('p','No matching items. Try another name or ID.'));
 for(const item of r.records){const v=item.values,b=spireElement('button',`${v.Name||v.name||'Item'} · ID ${v.id}`,'secondary');b.type='button';b.onclick=()=>spireRun(async()=>{spireSetField('item',v.id);$('spire-item-selected').textContent='Selected: '+(v.Name||v.name||'Item')+' · ID '+v.id;});$('spire-item-results').append(b);}
 spireControls();
}
function spireChanges(){const r=spireState.record,result={};for(const f of r.fields){if(!r.isNew&&!f.editable)continue;const input=$('spire-field-'+f.name),box=input.closest('.spire-field');if(r.isNew&&input.dataset.touched!=='true'&&input.value==='')continue;const v=box.querySelector('.spire-null')?.checked?null:input.value;if(r.isNew||v!==r.values[f.name])result[f.name]=v;}return result;}
async function spirePreview(action){
 const r=spireState.record;if(!r)throw new Error('Open a record first');spireInvalidate();
 const result=await job('spire_preview',{table:r.table,action:action||(r.isNew?'insert':'update'),key:r.isNew?{}:Object.fromEntries(r.key.map(k=>[k,r.values[k]])),revision:r.revision,values:action==='delete'?{}:spireChanges()});
 spireState.preview=result;$('spire-diff').replaceChildren();for(const c of result.changes){const row=spireElement('tr');for(const v of [c.field,c.before,c.after])row.append(spireElement('td',spireText(v)));$('spire-diff').append(row);}
 $('spire-preview-message').textContent=result.action.toUpperCase()+' · '+result.message;$('spire-preview-warning').textContent=[...result.warnings,result.impact].join(' ');$('spire-preview-panel').hidden=false;$('spire-preview-panel').scrollIntoView({block:'start',behavior:'smooth'});spireControls();
}
async function spireHistory(offset=0){const r=await job('spire_history',{offset});if(offset===0)$('spire-history').replaceChildren();for(const e of r.entries){const d=spireElement('details',undefined,'options-help');d.append(spireElement('summary',e.created+' UTC · '+e.change.action+' '+e.change.table+' · '+Object.values(e.change.key).join(' / ')));d.append(spireElement('p','Backup: '+e.backup+(e.exported?' · Client export: '+e.exported:'')));const pre=spireElement('pre');pre.textContent=JSON.stringify({before:e.change.before,after:e.change.after},null,2);d.append(pre);$('spire-history').append(d);}if(offset===0&&!r.entries.length)$('spire-history').textContent='No Spire changes have been saved.';spireState.historyNext=r.next_offset;$('spire-history-more').hidden=r.next_offset===null;spireExportStatus(r);}
spireBind('spire-refresh',async()=>{if(!spireDiscardAllowed())return;spireClose();await spireCatalog();await spireSearch(0);});
spireBind('spire-search',async()=>{if(!spireDiscardAllowed())return;spireClose();await spireSearch(0);});
$('spire-query').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();$('spire-search').click();}});
$('spire-type').addEventListener('change',()=>{const selected=$('spire-type').value;spireRun(async()=>{if(!spireDiscardAllowed()){$('spire-type').value=spireState.table;return;}spireClose();spireState.table=selected;spireState.filters={};$('spire-query').value='';await spireSearch(0);});});
spireBind('spire-clear-filter',async()=>{if(!spireDiscardAllowed())return;spireClose();spireState.filters={};await spireSearch(0);});
for(const [id,next] of [['spire-prev',false],['spire-next',true]])spireBind(id,async()=>{if(!spireDiscardAllowed())return;spireClose();await spireSearch(next?spireState.next:Math.max(0,spireState.offset-50));});
spireBind('spire-new',async()=>{if(!spireDiscardAllowed())return;const merchant=spireState.filters.merchantid;if(spireState.table==='merchantlist'&&merchant)await spireNewMerchant(merchant);else spireShowRecord({...spireState.schema,values:{...spireState.filters},links:[]},true);});
spireBind('spire-item-search',()=>spireItems(0));spireBind('spire-item-prev',()=>spireItems(Math.max(0,spireState.itemOffset-50)));spireBind('spire-item-next',()=>spireItems(spireState.itemNext));
$('spire-item-query').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();$('spire-item-search').click();}});
spireBind('spire-merchant-slot',async()=>{const r=await job('spire_merchant_draft',{merchantid:$('spire-field-merchantid').value});spireSetField('slot',r.values.slot);$('spire-warning').textContent=r.warnings.join(' ');});
spireBind('spire-close',async()=>{if(spireDiscardAllowed())spireClose();});
$('spire-field-filter').addEventListener('input',()=>{const q=$('spire-field-filter').value.toLowerCase();$('spire-fields').querySelectorAll('.spire-field').forEach(e=>e.hidden=!e.dataset.field.toLowerCase().includes(q));});
$('spire-form').addEventListener('submit',e=>{e.preventDefault();spireRun(()=>spirePreview());});
spireBind('spire-delete',()=>spirePreview('delete'));
spireBind('spire-discard',async()=>spireInvalidate());
spireBind('spire-save',async()=>{if(!spireState.preview)return;const token=spireState.preview.token;spireInvalidate();const r=await job('spire_apply',{token});spireState.dirty=false;spireExportStatus(r);await spireSearch(spireState.offset);if(r.action==='delete')spireClose();else await spireOpen(r.key);notice(r.message+' Backup: '+r.backup);});
spireBind('spire-export',async()=>{const r=await job('export_client');await exportResult(r);await spireCatalog();});
spireBind('spire-history-load',()=>spireHistory());spireBind('spire-history-more',()=>spireHistory(spireState.historyNext));
$('spire-history-panel').addEventListener('toggle',()=>{if($('spire-history-panel').open)spireRun(()=>spireHistory());});
