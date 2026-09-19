const {chromium}=require('playwright');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert');
const root=path.resolve('app/src/main/assets/ui');
const server=http.createServer((req,res)=>{const name=req.url==='/'?'index.html':req.url.slice(1);if(!/^[\w.-]+$/.test(name)){res.writeHead(404);res.end();return;}try{res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.webp')?'image/webp':name.endsWith('.ttf')?'font/ttf':'text/html');res.end(fs.readFileSync(path.join(root,name)));}catch{res.writeHead(404);res.end();}});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:854,height:480}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  await page.addInitScript(()=>{
   let jobs=[],seq=0,name="Traveller's blade",hp='10',pending=0;window.spireCalls=[];window.spireSaves=[];window.spireFailSave=false;window.spireHistoryEntries=[];
   const field=(name,type,key=false)=>({name,label:name,type,key,editable:!key,nullable:false,required:true,length:type.startsWith('varchar')?64:0,min:null,max:null});
   const meta=table=>({table,label:table==='items'?'Items':table==='merchantlist'?'Merchant inventory':'Spells',key:table==='merchantlist'?['merchantid','slot']:['id'],read_only:'',add:table==='merchantlist',remove:table==='merchantlist',impact:'Restart the server. Export spells with the saved RoF2 policy.',fields:table==='merchantlist'?[field('merchantid','int',true),field('slot','int',true),field('item','int')]:table==='spells_new'?[field('id','int',true),field('name','varchar(64)'),field('mana','int')]:[field('id','int',true),field('Name','varchar(64)'),field('hp','int')]});
   const state=()=>({settings:{ip:'127.0.0.1',repo:'https://github.com/Russianranger/Triptych-Triumvirate',ref:'main',workers:3,jobs:2},source:{},running:false,processes:{},jobs,free_bytes:50e9,nektulos:{},client:{}});
   window.Trasc={call(id,op,input){const a=JSON.parse(input);window.spireCalls.push({op,args:a});let result={};try{
    if(op==='native_state')result={installed:true,alive:true,status:'Runtime ready'};
    else if(op==='state')result=state();
    else if(op==='client_native_state')result={installed:true,alive:false,busy:false};
    else if(op==='export')result={};
    else if(op.startsWith('spire_')||op==='export_client'){
     let r;
     if(op==='spire_catalog')r={entities:[{table:'items',label:'Items',available:true},{table:'merchantlist',label:'Merchant inventory',available:true},{table:'spells_new',label:'Spells',available:true}],pending_export:pending,compatibility:true};
     else if(op==='spire_search'){
      const m=meta(a.table),v=a.table==='merchantlist'?{merchantid:'7',slot:'1',item:'100'}:a.table==='spells_new'?{id:'45000',name:'High spell',mana:'10'}:{id:'100',Name:name,hp};
      r={...m,columns:Object.keys(v),records:a.query==='missing'?[]:[{key:Object.fromEntries(m.key.map(k=>[k,v[k]])),values:v}],offset:a.offset||0,next_offset:a.query==='paged'&&a.offset===0?50:null};
     }else if(op==='spire_detail')r={...meta(a.table),values:a.table==='items'?{id:'100',Name:name,hp,custom:'Preserved'}:a.table==='spells_new'?{id:'45000',name:'High spell',mana:'10'}:{merchantid:'7',slot:'1',item:'100'},revision:'r1',links:a.table==='items'?[{label:'Used by Merchant inventory',table:'merchantlist',filters:{item:'100'}}]:[],warnings:a.table==='spells_new'?['This high spell ID remains excluded when RoF2 compatibility is enabled.']:[]};
     else if(op==='spire_merchant_draft')r={...meta('merchantlist'),values:{merchantid:String(a.merchantid),slot:'2'},warnings:['Shared inventory'],links:[]};
     else if(op==='spire_preview')r={token:'token-'+(++seq),table:a.table,action:a.action,key:a.key,changes:Object.entries(a.values).map(([field,after])=>({field,before:field==='hp'?hp:name,after})),warnings:[],impact:'Restart after save.',message:'Backup before saving.'};
     else if(op==='spire_apply'){
      if(window.spireFailSave)throw Error('Record changed after preview; reload and preview again');
      const preview=[...window.spireCalls].reverse().find(c=>c.op==='spire_preview').args;name=preview.values.Name||name;hp=preview.values.hp||hp;window.spireSaves.push(preview);window.spireHistoryEntries.push(preview);
      r={table:preview.table,key:preview.key,action:preview.action,backup:'backups/database-fixture.sql.gz',message:'Saved.',pending_export:pending};
     }else if(op==='spire_history')r={entries:window.spireHistoryEntries.map((x,i)=>({id:String(i),created:'2026-09-19 01:00:00',change:{...x,before:{hp:'10'},after:x.values},backup:'backups/database-fixture.sql.gz'})),next_offset:null,pending_export:pending};
     else if(op==='export_client'){pending=0;r={file:'exports/client-data.zip',local_client_synced:true,message:'Saved compatibility preserved.'};}
     const j={id:String(++seq),operation:op,status:'done',result:r};jobs.push(j);result=j;
    }
    setTimeout(()=>window.nativeReply(id,{ok:true,result}),10);
   }catch(e){setTimeout(()=>window.nativeReply(id,{ok:false,error:e.message}),10);}}};
  });
  await page.goto('http://127.0.0.1:'+server.address().port);await page.locator('nav [data-tab="spire"]').click();
  await page.waitForFunction(()=>!spireState.working&&spireState.loaded);assert.equal(await page.locator('#spire-results tr').count(),1);
  await page.locator('#spire-results button').click();await page.waitForFunction(()=>!spireState.working&&spireState.record);
  await page.locator('#spire-field-hp').fill('20');await page.locator('#spire-preview').click();await page.waitForFunction(()=>!spireState.working&&spireState.preview);
  assert((await page.locator('#spire-diff').textContent()).includes('20'));assert.equal(await page.evaluate(()=>window.spireSaves.length),0);
  await page.locator('#spire-field-hp').fill('21');assert(await page.locator('#spire-preview-panel').isHidden());assert(await page.locator('#spire-save').isDisabled());
  await page.locator('#spire-preview').click();await page.waitForFunction(()=>!spireState.working&&spireState.preview);await page.locator('#spire-save').click();await page.waitForFunction(()=>!spireState.working&&window.spireSaves.length===1);
  assert.equal(await page.evaluate(()=>spireState.dirty),false);assert.equal(await page.evaluate(()=>window.spireHistoryEntries.length),1);assert.equal(await page.locator('#spire-field-hp').inputValue(),'21');assert.equal(await page.locator('#spire-field-id').getAttribute('readonly'),'');
  await page.locator('#spire-field-hp').fill('22');await page.locator('#spire-preview').click();await page.waitForFunction(()=>!spireState.working&&spireState.preview);await page.evaluate(()=>window.spireFailSave=true);await page.locator('#spire-save').click();await page.waitForFunction(()=>!spireState.working);assert((await page.locator('#spire-status').textContent()).includes('changed after preview'));assert.equal(await page.evaluate(()=>window.spireSaves.length),1);assert(await page.locator('#spire-save').isDisabled());
  await page.locator('#spire-links button').click();await page.waitForFunction(()=>!spireState.working&&spireState.table==='merchantlist');assert((await page.locator('#spire-filter-text').textContent()).includes('item = 100'));
  await page.locator('#spire-new').click();await page.waitForFunction(()=>!spireState.working&&spireState.record?.isNew);await page.locator('#spire-field-merchantid').fill('7');await page.locator('#spire-field-slot').fill('2');await page.locator('#spire-field-item').fill('101');await page.locator('#spire-preview').click();await page.waitForFunction(()=>!spireState.working&&spireState.preview);assert.equal(await page.evaluate(()=>window.spireCalls.filter(c=>c.op==='spire_preview').at(-1).args.action),'insert');
  await page.locator('#spire-item-query').fill('missing');await page.locator('#spire-item-search').click();await page.waitForFunction(()=>!spireState.working);assert((await page.locator('#spire-item-results').textContent()).includes('No matching'));
  await page.locator('#spire-item-query').fill('paged');await page.locator('#spire-item-query').press('Enter');await page.waitForFunction(()=>!spireState.working);await page.locator('#spire-item-next').click();await page.waitForFunction(()=>!spireState.working&&spireState.itemOffset===50);await page.locator('#spire-item-prev').click();await page.waitForFunction(()=>!spireState.working&&spireState.itemOffset===0);
  await page.locator('#spire-item-results button').click();await page.waitForFunction(()=>!spireState.working);assert.equal(await page.locator('#spire-field-item').inputValue(),'100');assert(await page.locator('#spire-save').isDisabled());assert((await page.locator('#spire-item-selected').textContent()).includes('Selected:'));
  await page.locator('#spire-merchant-slot').click();await page.waitForFunction(()=>!spireState.working);assert.equal(await page.locator('#spire-field-slot').inputValue(),'2');assert((await page.locator('#spire-warning').textContent()).includes('Shared'));
  await page.evaluate(async()=>{spireState.filters={merchantid:'7'};await spireSearch(0);});await page.locator('#spire-new').click();await page.waitForFunction(()=>!spireState.working&&spireState.record?.isNew);assert.equal(await page.locator('#spire-field-merchantid').inputValue(),'7');assert.equal(await page.locator('#spire-field-slot').inputValue(),'2');assert.equal(await page.locator('#spire-field-item').inputValue(),'');
  await page.locator('#spire-item-query').fill('Sword');await page.locator('#spire-item-search').click();await page.waitForFunction(()=>!spireState.working);await page.locator('#spire-item-results button').click();await page.waitForFunction(()=>!spireState.working);await page.locator('#spire-preview').click();await page.waitForFunction(()=>!spireState.working&&spireState.preview);assert.deepEqual(await page.evaluate(()=>window.spireCalls.filter(c=>c.op==='spire_preview').at(-1).args.values),{merchantid:'7',slot:'2',item:'100'});
  fs.mkdirSync('ui-reports',{recursive:true});
  for(const [label,width,height]of [['phone',412,915],['thor',854,480]]){await page.setViewportSize({width,height});await page.locator('#spire-item-picker').scrollIntoViewIfNeeded();await page.screenshot({path:'ui-reports/merchant-picker-'+label+'.png',fullPage:true});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1));}
  await page.locator('#spire-type').selectOption('spells_new');await page.waitForFunction(()=>!spireState.working&&spireState.table==='spells_new');await page.locator('#spire-results button').click();await page.waitForFunction(()=>!spireState.working&&spireState.record);assert((await page.locator('#spire-warning').textContent()).includes('excluded'));
  fs.mkdirSync('ui-reports',{recursive:true});
  for(const [label,width,height]of [['phone',412,915],['thor',854,480],['wide',1280,720]]){await page.setViewportSize({width,height});await page.locator('#spire').scrollIntoViewIfNeeded();await page.screenshot({path:'ui-reports/spire-'+label+'.png',fullPage:true});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),'page overflow '+label);}
  await page.locator('#spire-export').click();await page.waitForFunction(()=>!spireState.working);assert(await page.evaluate(()=>window.spireCalls.some(c=>c.op==='export_client')));assert((await page.locator('#spire-export-status').textContent()).includes('compatibility is ON'));
  await page.locator('#spire-history-panel summary').click();await page.waitForFunction(()=>!spireState.working&&document.querySelector('#spire-history').textContent.includes('backups/database-fixture.sql.gz'));
  assert.deepEqual(errors,[]);console.log('PASS: Spire tab, preview invalidation, save/error, related filters, composite insert, high-ID warning, existing export, audit and responsive layouts');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exit(1);});
