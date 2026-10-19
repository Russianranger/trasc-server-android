'use strict';
// Native gamepad events are consumed before reaching WebView. Keyboard fallback
// handles ordinary keyboards; both paths use this single activation function.
(()=>{
 const focusable='button,input:not([type="hidden"]),select,textarea,summary,a[href],[tabindex]:not([tabindex="-1"])';
 const directions=new Set(['up','down','left','right']);
 let suspended=false,focused=null,editing=null,selectDialog=null;
 const cards=new WeakSet();
 function prepareCards(){
  for(const card of document.querySelectorAll('article.card')){
   if(cards.has(card))continue;cards.add(card);
   let headings=[...card.children].flatMap(child=>child.tagName==='H3'?[child]:(child.classList.contains('card-heading')||child.classList.contains('section-title'))?[...child.querySelectorAll('h3')]:[]);
   if(!headings.length){const heading=document.createElement('h3');heading.textContent=card.querySelector('#file-path')?'File browser':card.getAttribute('aria-label')||'Settings';card.prepend(heading);headings=[heading];}
   for(const heading of headings){
    heading.tabIndex=0;heading.setAttribute('role','button');heading.setAttribute('aria-expanded','true');heading.dataset.controllerCardHeading='true';
    let row=heading;while(row.parentElement!==card)row=row.parentElement;row.classList.add('controller-card-title');
    heading.addEventListener('click',()=>{setCard(card,card.dataset.controllerCardCollapsed!=='true');});
   }
  }
 }
 function setCard(card,collapsed){
  card.dataset.controllerCardCollapsed=String(collapsed);
  card.querySelectorAll('[data-controller-card-heading]').forEach(heading=>heading.setAttribute('aria-expanded',String(!collapsed)));
 }
 function cardHeading(card){return [...card.querySelectorAll('[data-controller-card-heading]')].find(visible);}
 function blocked(){return suspended||document.hidden||(typeof captureActive!=='undefined'&&captureActive);}
 function visible(element){
  if(!element?.isConnected||element.disabled||element.matches(':disabled')||element.closest('[hidden],[inert],[aria-hidden="true"]'))return false;
  const style=getComputedStyle(element);if(style.visibility==='hidden'||style.display==='none'||!element.getClientRects().length)return false;
  for(let parent=element.parentElement;parent;parent=parent.parentElement){
   if(parent.tagName==='DETAILS'&&!parent.open){const summary=parent.querySelector(':scope > summary');if(!summary?.contains(element))return false;}
  }
  return true;
 }
 function modal(){return [...document.querySelectorAll('dialog[open],[role="dialog"][aria-modal="true"]')].filter(visible).at(-1)||null;}
 function candidates(root=modal()||document){return [...root.querySelectorAll(focusable)].filter(element=>visible(element)&&(!element.matches('.primary-nav [data-area],nav:not(.secondary-nav) [data-tab]')||element.classList.contains('active')));}
 function tabButton(){return [...document.querySelectorAll('.primary-nav [data-area].active,nav [data-tab].active')].find(visible);}
 function mark(element){
  if(focused!==element)focused?.classList.remove('controller-menu-focus');
  focused=element;if(element)element.classList.add('controller-menu-focus');
 }
 function focus(element){
  if(!visible(element))return false;
  document.body.dataset.controllerMenu='active';
  element.focus({preventScroll:true});mark(element);
  element.scrollIntoView({block:'nearest',inline:'nearest',behavior:'instant'});return true;
 }
 function keyboard(show){if(window.Trasc?.launcherKeyboard)window.Trasc.launcherKeyboard(show);}
 function current(items){return items.includes(document.activeElement)?document.activeElement:null;}
 function chooseSelect(select){
  if(selectDialog)return;
  const dialog=document.createElement('dialog');selectDialog=dialog;dialog.className='controller-select-dialog';
  const title=document.createElement('h2');title.id='controller-select-title';title.textContent=select.labels?.[0]?.textContent.trim()||select.getAttribute('aria-label')||'Choose an option';
  dialog.setAttribute('aria-labelledby',title.id);dialog.append(title);
  const options=document.createElement('div');options.className='controller-select-options';let selected=null;
  for(const option of select.options){
   if(option.hidden)continue;
   const button=document.createElement('button');button.type='button';button.textContent=option.label||option.textContent;
   button.disabled=option.disabled||option.parentElement?.disabled===true;
   if(option.selected){button.setAttribute('aria-current','true');selected=button;}
   button.addEventListener('click',()=>{
    if(!select.isConnected||select.disabled){dialog.close();return;}
    const changed=select.selectedIndex!==option.index;select.selectedIndex=option.index;
    if(changed){select.dispatchEvent(new Event('input',{bubbles:true}));select.dispatchEvent(new Event('change',{bubbles:true}));}
    dialog.close();
   });options.append(button);
  }
  dialog.append(options);const cancel=document.createElement('button');cancel.type='button';cancel.textContent='Cancel';cancel.className='secondary';cancel.addEventListener('click',()=>dialog.close());dialog.append(cancel);
  dialog.addEventListener('close',()=>{selectDialog=null;dialog.remove();focus(select);},{once:true});
  document.body.append(dialog);dialog.showModal();focus(selected&&!selected.disabled?selected:candidates(dialog)[0]);
 }
 function accept(){
  const items=candidates(),element=current(items)||tabButton()||items[0];if(!element)return false;
  focus(element);
  if(element.matches('select')){chooseSelect(element);return true;}
  if(element.matches('textarea,input:not([type=checkbox]):not([type=radio]):not([type=button]):not([type=submit]):not([type=reset]):not([type=range]):not([type=color]):not([type=file])')||element.isContentEditable){
   if(!element.readOnly){editing=element;keyboard(true);}return true;
  }
  element.click();return true;
 }
 function back(){
  if(editing){keyboard(false);editing=null;return true;}
  const scope=modal();
  if(scope){
   if(scope.tagName==='DIALOG'){scope.close();return true;}
   const close=[...scope.querySelectorAll('[data-controller-close],[aria-label="Close"],[aria-label="Cancel"]')].find(visible);close?.click();return true;
  }
  const detail=document.activeElement?.closest('details[open]');
  const card=document.activeElement?.closest('article.card');
  const expandedCard=card&&card.dataset.controllerCardCollapsed!=='true';
  // Collapse the innermost surface: setup/build disclosure groups can contain
  // cards, and those cards can themselves contain nested details.
  if(detail&&(!expandedCard||card.contains(detail))){detail.open=false;focus(detail.querySelector(':scope > summary'));return true;}
  if(expandedCard){setCard(card,true);focus(cardHeading(card));return true;}
  const tab=tabButton();if(tab&&document.activeElement!==tab){focus(tab);return true;}
  if(typeof window.appBack==='function'){window.appBack();focus(tabButton());return true;}
  return false;
 }
 function cycleTab(step){
  if(modal())return true;
  const primary=document.querySelector('.primary-nav');
  const tabs=[...(primary?primary.querySelectorAll('[data-area]'):document.querySelectorAll('nav [data-tab]'))].filter(visible);if(!tabs.length)return false;
  const index=tabs.findIndex(button=>button.classList.contains('active'));
  const next=tabs[(Math.max(0,index)+step+tabs.length)%tabs.length];keyboard(false);editing=null;next.click();focus(next);return true;
 }
 function move(direction){
  const items=candidates();if(!items.length)return false;
  const element=current(items);
  if(!element){focus(modal()?items[0]:tabButton()||items[0]);return true;}
  editing=null;keyboard(false);
  if(element.tagName==='SUMMARY'){
   const detail=element.parentElement;
   if(direction==='right'&&!detail.open){detail.open=true;focus(element);return true;}
   if(direction==='left'&&detail.open){detail.open=false;focus(element);return true;}
  }
  if(element.hasAttribute('data-controller-card-heading')){
   const card=element.closest('article.card');
   if(direction==='right'&&card.dataset.controllerCardCollapsed==='true'){setCard(card,false);focus(element);return true;}
   if(direction==='left'&&card.dataset.controllerCardCollapsed!=='true'){setCard(card,true);focus(element);return true;}
  }
  const index=items.indexOf(element),step=direction==='up'||direction==='left'?-1:1;
  if(direction==='up'||direction==='down'){
   // Reading order always reaches every control, including tall and nested tiles.
   focus(items[Math.max(0,Math.min(items.length-1,index+step))]);return true;
  }
  const box=element.getBoundingClientRect(),cx=box.x+box.width/2,cy=box.y+box.height/2;
  const next=items.filter(item=>item!==element).map(item=>{
   const r=item.getBoundingClientRect(),dx=(r.x+r.width/2-cx)*step,dy=Math.abs(r.y+r.height/2-cy);
   return {item,dx,score:dx+dy*3};
  }).filter(item=>item.dx>4).sort((a,b)=>a.score-b.score)[0]?.item;
  focus(next||items[Math.max(0,Math.min(items.length-1,index+step))]);return true;
 }
 function command(name){
  if(blocked())return false;
  prepareCards();
  if(name==='nextTab')return cycleTab(1);if(name==='previousTab')return cycleTab(-1);
  if(name==='accept')return accept();if(name==='back')return back();
  return directions.has(name)?move(name):false;
 }
 window.launcherMenuController={command,setSuspended(value){suspended=!!value;window.Trasc?.launcherMenuSuspended?.(suspended);}};
 const map={ArrowUp:'up',ArrowDown:'down',ArrowLeft:'left',ArrowRight:'right',Enter:'accept',' ':'accept',Escape:'back',GamepadA:'accept',GamepadB:'back',PageUp:'previousTab',PageDown:'nextTab'};
 const consumed=new Set();
 document.addEventListener('keydown',event=>{
  const name=map[event.key];if(!name||event.altKey||event.ctrlKey||event.metaKey)return;
  const text=event.target.matches?.('input,textarea,select,[contenteditable=true]');
  if(text&&(directions.has(name)||event.key===' '||event.key==='Enter'))return;
  if(blocked())return;
  if(event.repeat&&!directions.has(name)||command(name)){event.preventDefault();event.stopImmediatePropagation();consumed.add(event.code||event.key);}
 },true);
 document.addEventListener('keyup',event=>{if(consumed.delete(event.code||event.key)){event.preventDefault();event.stopImmediatePropagation();}},true);
 document.addEventListener('focusin',event=>{if(document.body.dataset.controllerMenu==='active'&&event.target.matches(focusable))mark(event.target);});
 document.addEventListener('pointerdown',()=>{delete document.body.dataset.controllerMenu;mark(null);editing=null;},true);
 prepareCards();
 const help=document.createElement('p');help.className='controller-menu-help';help.textContent='LB / RB: main areas · D-pad: move · A: select / keyboard · B: collapse / back';document.querySelector('nav')?.insertAdjacentElement('afterend',help);
})();
