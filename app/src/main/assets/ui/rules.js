'use strict';
let ruleSpecs={},ruleDraft={},ruleErrors={},loadedRuleset=null;
const ruleOpen=new Set(),ruleControls=new Map();
const ruleText=(name)=>Object.hasOwn(ruleDraft,name)?ruleDraft[name]:String(rulesValues[name]?.value??'');
function setRule(name,value){
 const original=String(rulesValues[name]?.value??'');
 if(value===original)delete ruleDraft[name];else ruleDraft[name]=value;
 delete ruleErrors[name];
 if(name==='Zone:StateSavingOnShutdown')$('state-saving').checked=['true','1'].includes(value.toLowerCase());
 $('rules-dirty').textContent=Object.keys(ruleDraft).length+' changed rules. Only changed values will be saved.';
}
function ruleField(name){
 const spec=ruleSpecs[name],row=document.createElement('div');row.className='rule-entry';row.dataset.name=name;
 const label=document.createElement('label'),title=document.createElement('strong');title.textContent=name;label.append(title);
 const info=document.createElement('small');info.textContent=spec.description||'No description was supplied for this rule.';label.append(info);
 const input=document.createElement(spec.type==='bool'?'select':spec.type==='string'?'textarea':'input');input.id='rule-'+name.replaceAll(':','-');label.htmlFor=input.id;
 if(spec.type==='bool'){for(const value of ['','true','false']){const o=document.createElement('option');o.value=value;o.textContent=value||'Not set';input.append(o);}input.value=ruleText(name).toLowerCase().replace(/^1$/,'true').replace(/^0$/,'false');}
 else{if(spec.type==='string'){input.rows=2;input.maxLength=spec.max_length??65535;}else{input.type='number';input.step=spec.type==='int'?'1':'any';if(spec.min!=null)input.min=spec.min;if(spec.max!=null)input.max=spec.max;}input.value=ruleText(name);}
 input.dataset.rule=name;input.addEventListener('input',()=>{setRule(name,input.value);input.removeAttribute('aria-invalid');error.textContent='';});
 const detail=document.createElement('small'),origin=rulesValues[name]?.ruleset;
 const limits=spec.min!=null||spec.max!=null?' · allowed '+(spec.min??'unbounded')+' to '+(spec.max??'unbounded'):'';
 detail.textContent=spec.type+limits+' · '+(origin==null?'Source default / unset':origin===loadedRuleset?'This rule set':'Inherited from rule set '+origin)+(spec.bounds_source?' · '+spec.bounds_source:'');
 const error=document.createElement('p');error.className='field-error';error.id=input.id+'-error';error.textContent=ruleErrors[name]||'';input.setAttribute('aria-describedby',error.id);
 if(ruleErrors[name])input.setAttribute('aria-invalid','true');
 row.append(label,input,detail,error);ruleControls.set(name,{input,row,error});return row;
}
function renderRuleCategories(){
 const term=$('rule-search').value.trim().toLowerCase(),groups=new Map();ruleControls.clear();$('rule-categories').replaceChildren();
 for(const name of Object.keys(ruleSpecs).sort()){const spec=ruleSpecs[name];if(term&&!(name+' '+spec.description).toLowerCase().includes(term))continue;const category=name.includes(':')?name.split(':')[0]:'Other';if(!groups.has(category))groups.set(category,[]);groups.get(category).push(name);}
 let found=0;
 for(const [category,names]of groups){found+=names.length;const details=document.createElement('details'),summary=document.createElement('summary'),content=document.createElement('div');details.className='rule-category';details.dataset.category=category;summary.textContent=category+' · '+names.length+' rules';details.append(summary,content);
  let built=false;const fill=()=>{if(!built){const f=document.createDocumentFragment();for(const name of names)f.append(ruleField(name));content.append(f);built=true;}};
  details.addEventListener('toggle',()=>{if(details.open){ruleOpen.add(category);fill();}else ruleOpen.delete(category);});
  if(term||ruleOpen.has(category)||names.some(n=>ruleErrors[n])){details.open=true;fill();}
  $('rule-categories').append(details);
 }
 $('rules-count').textContent=found+' of '+Object.keys(ruleSpecs).length+' rules · '+groups.size+' categories';
}
function showRuleErrors(errors){
 ruleErrors=errors;const messages=Object.values(errors);$('rules-errors').hidden=!messages.length;$('rules-errors').textContent=messages.join('\n');
 if(messages.length){$('rule-search').value='';renderRuleCategories();$('rules-errors').scrollIntoView({block:'center'});}
}
async function loadRules(selected){
 const requested=selected==null?{}:{ruleset:selected};
 const r=await job('gameplay',requested);rulesLoaded=true;rulesValues=r.values;ruleSpecs=r.metadata;ruleDraft={};loadedRuleset=r.selected;showRuleErrors({});
 $('ruleset').replaceChildren();for(const set of r.rulesets){const o=document.createElement('option');o.value=set.id;o.textContent=set.name+' ('+set.id+')';$('ruleset').append(o);}$('ruleset').value=r.selected;
 $('active-rules').textContent='Active global rule set: '+r.active_name+'. Zones can have their own overrides.';
 $('state-saving').checked=['true','1'].includes(ruleText('Zone:StateSavingOnShutdown').toLowerCase());$('state-saving').disabled=!ruleSpecs['Zone:StateSavingOnShutdown'];
 $('rules-dirty').textContent='No unsaved rule changes.';renderRuleCategories();
}
action('load-rules',()=>loadRules());
$('ruleset').addEventListener('change',()=>{
 if(Object.keys(ruleDraft).length){$('ruleset').value=loadedRuleset;notice('Save your changed rules before switching rule sets, or reload settings to discard them.',true);return;}
 loadRules(Number($('ruleset').value)).catch(e=>{$('ruleset').value=loadedRuleset;notice(e.message,true);});
});
$('state-saving').addEventListener('change',()=>{if(!rulesLoaded)return;setRule('Zone:StateSavingOnShutdown',String($('state-saving').checked));const c=ruleControls.get('Zone:StateSavingOnShutdown');if(c)c.input.value=ruleText('Zone:StateSavingOnShutdown');});
$('rule-search').addEventListener('input',renderRuleCategories);
action('rules-expand',async()=>{for(const d of $('rule-categories').children)d.open=true;});
action('rules-collapse',async()=>{ruleOpen.clear();for(const d of $('rule-categories').children)d.open=false;});
action('save-rules',async()=>{
 if(!rulesLoaded)throw new Error('Load database settings first.');const errors={};
 for(const [name,value]of Object.entries(ruleDraft)){
  const spec=ruleSpecs[name];
  if(value.length>spec.max_length)errors[name]=name+': maximum length is '+spec.max_length+' characters.';
  else if(spec.type==='bool'&&!['true','false','1','0'].includes(value.toLowerCase()))errors[name]=name+': choose true or false.';
  else if(['int','real'].includes(spec.type)){
   const n=Number(value);if(!value.trim()||!Number.isFinite(n))errors[name]=name+': enter a finite number.';
   else if(spec.type==='int'&&!/^[+-]?\d+$/.test(value.trim()))errors[name]=name+': enter a whole number.';
   else if(spec.min!=null&&n<Number(spec.min))errors[name]=name+': '+value+' is below the minimum '+spec.min+'.';
   else if(spec.max!=null&&n>Number(spec.max))errors[name]=name+': '+value+' is above the maximum '+spec.max+'.';
  }
 }
 const workers=Number($('workers').value);if(!Number.isInteger(workers)||workers<1||workers>20)errors.workers='Dynamic zone workers: choose a whole number from 1 to 20.';
 showRuleErrors(errors);if(Object.keys(errors).length)throw new Error('Settings were not saved. Correct the highlighted fields.');
 try{await job('save_gameplay',{ruleset:loadedRuleset,workers,values:ruleDraft});await loadRules(loadedRuleset);notice('Settings saved. Restart the server to apply the changes.');}
 catch(e){const found={};for(const name of Object.keys(ruleDraft)){const line=e.message.split('\n').find(l=>l.startsWith(name+':'));if(line)found[name]=line;}if(Object.keys(found).length)showRuleErrors(found);throw e;}
});
