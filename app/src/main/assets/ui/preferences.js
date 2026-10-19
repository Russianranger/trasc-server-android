'use strict';
// Presentation only: move the existing controls so their listeners, saved values,
// validation and profile restrictions continue to belong to the original features.
(()=>{
 const byId=id=>document.getElementById(id);
 const client=byId('client'),options=byId('client-options');
 if(!client||!options)return;
 const profile=()=>document.body.dataset.profile||'custom';
 const make=(tag,className,text)=>{const el=document.createElement(tag);if(className)el.className=className;if(text)el.textContent=text;return el;};
 const group=(id,title,description,collapsed)=>{
  const root=make(collapsed?'details':'fieldset',collapsed?'preferences-group options-help':'option-group preferences-everyday');root.id=id;
  root.append(make(collapsed?'summary':'legend','',title));
  if(description)root.append(make('p','hint',description));
  const grid=make('div','option-grid'),checks=make('div','option-checks');root.append(grid,checks);
  return {root,grid,checks};
 };
 const everyday=group('preferences-everyday','Everyday settings','Choose your display and sound preferences. Launch the client to apply changes.',false);
 const recommended=group('preferences-recommended','Recommended configuration','Inspect your runtime and compatibility choices. Existing saved choices are retained.',true);
 const experiments=group('preferences-experiments','Experiments & diagnostics','Optional comparisons and troubleshooting. These controls keep their existing values; opening this section changes nothing.',true);
 const move=(ids,destination)=>ids.forEach(id=>{
  const control=byId(id),wrapper=control?.closest('.option-field, label.check');
  if(wrapper)(wrapper.matches('label')?destination.checks:destination.grid).append(wrapper);
 });
 move(['client-resolution','client-renderer','client-fullscreen','client-audio','client-dxvk-hud'],everyday);
 move(['client-turnip-driver','client-npc-rendering','client-runtime-mode','client-cpu-affinity','client-cpu-profile','client-native-dll','client-native-models'],recommended);
 move(['client-presentation','client-display-fps','client-boats','client-particles','client-graphics-threading','client-fast-spells','client-load-pauses','client-mouse-warp','client-sound-diagnostics','client-diagnostics','client-name-sky'],experiments);
 const body=options.querySelector('.options-body');
 const cameraHelp=byId('client-camera-help');if(cameraHelp)experiments.root.append(cameraHelp);
 // Both old fieldsets are empty after reparenting; keep the separate warning fieldset.
 body.querySelectorAll(':scope > .option-group').forEach(el=>{if(!el.querySelector('input,select,button'))el.remove();});
 const overview=make('div','preferences-overview');
 const state=make('p','preferences-state');state.id='preferences-state';state.setAttribute('role','status');
 const active=make('p','hint');active.id='preferences-current';
 overview.append(state,active);
 const baseline=make('p','hint');baseline.id='preferences-baseline';recommended.root.insertBefore(baseline,recommended.grid);
 const differences=make('ul','preferences-differences');differences.id='preferences-differences';recommended.root.append(differences);
 const experimentalState=make('p','hint');experimentalState.id='preferences-experiment-state';experiments.root.insertBefore(experimentalState,experiments.grid);
 const shortcuts=make('div','buttons preferences-shortcuts');
 for(const [id,label]of [['controller-preset','Controller mappings'],['game-settings-tile','Player models & game settings'],['client-ui-panel','Client UI skins']]){
  const button=make('button','secondary',label);button.type='button';button.addEventListener('click',()=>reveal(id));shortcuts.append(button);
 }
 everyday.root.append(shortcuts);
 body.prepend(overview,everyday.root,recommended.root,experiments.root);
 options.querySelector(':scope > summary').textContent='Client preferences';options.open=true;
 // Bring normal settings ahead of imports and repair tools. Setup remains reachable
 // through the guide and search, and its original elements are not reconstructed.
 const firstCard=client.querySelector(':scope > .card, :scope > .grid');
 if(firstCard&&firstCard!==options)client.insertBefore(options,firstCard);

 const searchCard=make('article','card preferences-search');searchCard.id='preferences-search';
 searchCard.append(make('h3','','Find a setting or tool'));
 const searchLabel=make('label','','Search all launcher areas');searchLabel.htmlFor='preferences-query';
 const searchRow=make('div','path-bar'),search=make('input');search.id='preferences-query';search.type='search';search.placeholder='FPS, controller, quests, 4 GB, spellbook, Spire…';search.autocomplete='off';search.spellcheck=false;search.maxLength=120;
 search.setAttribute('aria-describedby','preferences-search-status');search.setAttribute('aria-controls','preferences-search-results');
 const clear=make('button','secondary','Clear');clear.type='button';clear.id='preferences-search-clear';clear.hidden=true;
 searchRow.append(search,clear);searchCard.append(searchLabel,searchRow);
 const searchStatus=make('p','hint','Search finds tools in Play, Manage, Customize and Settings for the selected world.');searchStatus.id='preferences-search-status';searchStatus.setAttribute('role','status');searchStatus.setAttribute('aria-live','polite');
 const results=make('ul','preferences-search-results');results.id='preferences-search-results';results.hidden=true;searchCard.append(searchStatus,results);
 client.prepend(searchCard);

 const aliases={
  'client-resolution':'resolution size screen display',
  'client-renderer':'graphics GPU FPS frame rate performance turnip virgl software',
  'client-display-fps':'FPS frame rate display updates refresh',
  'client-dxvk-hud':'FPS counter frame rate statistics overlay',
  'client-audio':'audio sound music volume',
  'client-cpu-profile':'performance CPU TAKP NPC invisible models accuracy',
  'client-native-models':'DirectX animation NPC models',
  'controller-preset':'controller gamepad buttons mapping bindings controls joystick Thor',
  'controller-speed':'mouse pointer right stick sensitivity',
  'client-4gb-apply':'4 GB 4gb patch memory large address aware',
  'client-spellbook-check':'spellbook spells 1440 1,440 compatibility patch',
  'client-compatibility-warnings':'warnings mismatch do not warn again compatibility',
  'client-ui-panel':'appearance skins UI layout inventory',
  'game-settings-tile':'appearance player models Luclin classic eqclient ini',
  'spire':'Spire content editor items NPC loot merchants spells strings AA',
  'quest-scan':'quests plugins sync synchronize update',
  'client-prepare':'prepare client sync export data files login',
  'session-export-all':'backup export all profiles restore',
  'source-update-check':'server source update build'
 };
 const knownTitles={'client-ui-panel':'Client UI skins','game-settings-tile':'Player models & game settings','spire':'Content editor · Spire'};
 function available(el){
  const panel=el?.closest('.tab');
  if(panel&&typeof launcherTabAllowed==='function'&&!launcherTabAllowed(panel.id))return false;
  for(let node=el;node&&node!==document.body;node=node.parentElement){
   if(node.hidden||node.getAttribute('aria-hidden')==='true')return false;
   if(node.hasAttribute('data-custom-only')&&profile()!=='custom')return false;
   if(node.hasAttribute('data-traditional-only')&&profile()!=='traditional')return false;
   if(node.hasAttribute('data-takp-only')&&profile()!=='takp')return false;
   if(node.hasAttribute('data-takp-hide')&&profile()==='takp')return false;
  }
  return true;
 }
 function titleFor(el){
  if(knownTitles[el.id])return knownTitles[el.id];
  if(el.labels?.length)return [...el.labels].map(label=>label.textContent.trim()).join(' ');
  return el.getAttribute('aria-label')||el.querySelector(':scope > summary, :scope > h3')?.textContent.trim()||(el.matches('button')?el.textContent.trim():'');
 }
 function locationFor(el){
  const section=el.closest('.tab'),area={setup:'Manage · Setup',server:'Manage · Server',build:'Manage · Updates & builds',files:'Manage · Files',database:'Customize · Database',gameplay:'Customize · Rules',bots:'Customize · Companions',spire:'Customize · Content editor',appearance:'Customize · Appearance',fixes:'Settings · Troubleshooting',logs:'Settings · Logs',client:'Settings · Client',play:'Play'}[section?.id]||'Launcher';
  const group=el.closest('#preferences-recommended,#preferences-experiments');
  return area+(group?' · '+group.querySelector('summary').textContent:'');
 }
 function reveal(id){
  const target=byId(id);if(!target||!available(target))return;
  if(typeof window.navigateToControl==='function'){window.navigateToControl(id);return;}
  const panel=target.closest('.tab');if(panel&&typeof tab==='function')tab(panel.id);
  for(let parent=target;parent;parent=parent.parentElement)if(parent.tagName==='DETAILS')parent.open=true;
  const focusTarget=target.matches('button,input,select,textarea,summary')?target:target.querySelector('summary,button,input,select');
  (focusTarget||target).scrollIntoView({block:'center'});if(focusTarget&&!focusTarget.disabled)focusTarget.focus({preventScroll:true});
 }
 let searchSignature='',differencesSignature='';
 function searchPreferences(){
  const query=search.value.trim().toLowerCase(),words=query.split(/\s+/).filter(Boolean);clear.hidden=!query;results.hidden=!query;
  if(!query){searchSignature='';results.replaceChildren();searchStatus.textContent='Search finds tools in Play, Manage, Customize and Settings for the selected world.';return;}
  const candidates=[...document.querySelectorAll('main input[id],main select[id],main textarea[id],main button[id]'),...Object.keys(knownTitles).map(byId).filter(Boolean)];
  const matches=[],seen=new Set();
  for(const el of candidates){
   if(seen.has(el.id)||el.closest('#preferences-search')||el.type==='hidden'||el.type==='password'||!available(el))continue;
   seen.add(el.id);const title=titleFor(el);if(!title)continue;
   const location=locationFor(el),text=[title,el.id.replaceAll('-',' '),aliases[el.id]||''].join(' ').toLowerCase();
   if(words.every(word=>text.includes(word)))matches.push({el,title,location,score:title.toLowerCase().includes(query)?0:1});
  }
  matches.sort((a,b)=>a.score-b.score||a.title.localeCompare(b.title));
  const displayed=matches.slice(0,16);
  const signature=JSON.stringify([profile(),query,displayed.map(({el,title,location})=>[el.id,title,location,el.disabled])]);
  if(signature!==searchSignature){searchSignature=signature;results.replaceChildren(...displayed.map(({el,title,location})=>{
   const row=make('li'),button=make('button','secondary preferences-result');button.type='button';button.dataset.control=el.id;
   button.append(make('span','',title),make('small','',location+(el.disabled?' · Open to see requirements':'')));
   button.addEventListener('click',()=>reveal(el.id));row.append(button);return row;
  }));}
  searchStatus.textContent=!matches.length?'No matching tools for this world. Try a shorter term such as “maps” or “controller”.':matches.length>displayed.length?'Showing '+displayed.length+' of '+matches.length+' matches. Add a word to narrow the results.':matches.length+' '+(matches.length===1?'match':'matches')+' in this world. Select a result to open it.';
 }
 search.addEventListener('input',searchPreferences);
 search.addEventListener('keydown',event=>{if(event.key==='Escape'){search.value='';searchPreferences();event.preventDefault();}if(event.key==='Enter'){const first=results.querySelector('button');if(first){event.preventDefault();first.click();}}});
 clear.addEventListener('click',()=>{search.value='';searchPreferences();search.focus();});
 const value=id=>byId(id)?.type==='checkbox'?byId(id).checked:byId(id)?.value;
 const displayValue=id=>{const el=byId(id);return el?.type==='checkbox'?(el.checked?'On':'Off'):el?.selectedOptions?.[0]?.textContent||el?.value||'Unknown';};
 function renderPreferences(){
  const name=profile()==='takp'?'TAKP':profile()==='traditional'?'Traditional':'Custom';
  const loaded=typeof launchOptionsLoaded==='undefined'||launchOptionsLoaded;
  const defaults=[['client-runtime-mode','auto'],['client-cpu-affinity','available'],['client-cpu-profile',profile()==='takp'?'accurate':'balanced']];
  if(profile()==='custom')defaults.push(['client-native-dll',true]);
  if(profile()!=='takp')defaults.push(['client-native-models',true]);
  if(profile()!=='takp'&&value('client-renderer')==='turnip')defaults.push(['client-npc-rendering','compatibility']);
  // compatibility_042 is the same qualified NPC mapping, not a deviation.
  const changed=defaults.filter(([id,expected])=>available(byId(id))&&!(id==='client-npc-rendering'&&value(id)==='compatibility_042')&&value(id)!==expected);
  state.textContent=!loaded?'Checking '+name+' preferences…':changed.length?'Customized · '+changed.length+' recommended '+(changed.length===1?'option differs':'options differ'):'Recommended compatibility options match';
  active.textContent=name+' · '+displayValue('client-renderer')+' · '+displayValue('client-resolution')+' · '+(value('client-audio')?'Audio on':'Audio off')+'. Choices apply on the next client launch.';
  baseline.textContent=profile()==='takp'?'TAKP uses Legacy math accuracy, confirmed for visible NPC models on Thor, plus its own required DirectX helper. Custom client hooks are excluded. Graphics backend and driver remain your choice.':'RoF2 uses Balanced CPU, automatic runtime handling and available CPU cores. Installed DirectX helpers and '+(profile()==='custom'?'the imported native dinput8.dll are enabled by default.':'Wine’s built-in DirectInput are the profile defaults.')+' Turnip uses NPC compatibility mapping. Graphics backend and driver remain your choice.';
  differences.hidden=!loaded||!changed.length;
  const signature=JSON.stringify(changed.map(([id,expected])=>[id,expected,displayValue(id)]));
  if(signature!==differencesSignature){differencesSignature=signature;differences.replaceChildren(...changed.map(([id,expected])=>{
   const row=make('li'),button=make('button','quiet',titleFor(byId(id))+': '+displayValue(id));button.type='button';button.addEventListener('click',()=>reveal(id));
   const expectedText=typeof expected==='boolean'?(expected?'On':'Off'):[...byId(id).options].find(option=>option.value===expected)?.textContent||expected;
   row.append(button,make('small','','Recommended: '+expectedText));return row;
  }));}
  const experimentalDefaults={'client-presentation':'rfb','client-display-fps':'30','client-boats':'off','client-particles':'off','client-graphics-threading':'multi','client-fast-spells':false,'client-load-pauses':false,'client-mouse-warp':false,'client-sound-diagnostics':false,'client-diagnostics':false,'client-name-sky':false};
  const count=Object.entries(experimentalDefaults).filter(([id,expected])=>available(byId(id))&&value(id)!==expected).length;
  experiments.root.querySelector(':scope > summary').textContent='Experiments & diagnostics'+(loaded&&count?' · '+count+' selected':'');
  experimentalState.textContent=!loaded?'Checking saved choices…':count?count+' optional '+(count===1?'comparison or diagnostic is':'comparisons or diagnostics are')+' selected. Review these when troubleshooting.':'Optional comparisons and diagnostics are at their normal defaults.';
  if(search.value.trim())searchPreferences();
 }
 options.addEventListener('change',renderPreferences);
 window.renderPreferences=renderPreferences;
 renderPreferences();
})();
