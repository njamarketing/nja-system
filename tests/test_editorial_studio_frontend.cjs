const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes=new Map(),fields=new Map(),calls=[];let connected=true,closeCount=0,shouldFail=false;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function node(key){
 if(!nodes.has(key)){let html='',value='';const n={dataset:{},disabled:false,files:[],classList:{add(){},toggle(){}},setAttribute(){},focus(){},querySelectorAll(){return []},get isConnected(){return connected},closest(){return node('dialog')},get value(){return value},set value(v){value=v},get innerHTML(){return html},set innerHTML(v){html=v;const option=v.match(/^<option value="([^"]*)"/);if(option)value=option[1]},setRangeText(t,start,end){value=value.slice(0,start)+t+value.slice(end)}};nodes.set(key,n)}return nodes.get(key);
}
function field(label,name,type,value=''){const n=node('field:'+name);n.value=value;fields.set(name,n);return `<input name="${name}" value="${esc(value)}">`}
function selectField(label,name,options,value=''){field(label,name,'select',value||options[0]?.[0]||'');return `<select name="${name}"></select>`}
const context={console,Map,Set,Date,Math,Number,String,JSON,encodeURIComponent,URLSearchParams,AbortController,crypto:{randomUUID:()=> 'test-editorial-nonce-12345'},MutationObserver:class{observe(){}disconnect(){}},window:{agencySections:{}},state:{clients:[{id:'c1',name:'Cliente <A>',active:1},{id:'c2',name:'Cliente B',active:1}],csrf:'csrf'},location:{hash:'#editorial:c1'},esc,initials:n=>n.slice(0,2),field,selectField,textarea:(label,name,value='')=>field(label,name,'textarea',value),$:(s)=>node(s),$$:()=>[],modal:()=>{connected=true;node('#editorial-compose').elements={namedItem:name=>fields.get(name)}},closeModal:()=>{connected=false;closeCount++},datePayload:v=>v?v+'-03:00':null,inputDate:v=>v,today:()=> '2026-10-21',toast(){},agencyPage:async()=>{},confirm:()=>true,request:async(path,options)=>{calls.push({path,options});if(shouldFail)throw Error('Conexão interrompida');return {id:'post'}},URL:{revokeObjectURL(){}}};
vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/../static/agency-editorial.js','utf8'),context);
const accounts=[{id:'ig',client_id:'c1',name:'Perfil IG',platform:'instagram',active:1,verified:'yes'},{id:'fb',client_id:'c2',name:'Página FB',platform:'facebook',active:1,verified:'yes'}];
const data={accounts,uploads:[]};context.data=data;
assert.equal(vm.runInContext("editorialFormatsFor('facebook').includes('video')",context),true);
const preview=vm.runInContext("editorialPreview('instagram','<profile>','<img src=x onerror=bad>',[{id:'file',mime:'image/jpeg'}],0,'image')",context);
assert.ok(preview.includes('&lt;profile&gt;'));assert.ok(!preview.includes('<img src=x'));assert.ok(preview.includes('/files/file'));
assert.ok(vm.runInContext("editorialPreview('facebook','Page','Caption',[{id:'v',mime:'video/mp4'}],0,'video')",context).includes('<video'));
assert.ok(vm.runInContext("editorialPreview('instagram','IG','Caption',[{id:'a',mime:'image/jpeg'},{id:'b',mime:'image/jpeg'}],1,'carousel')",context).includes('2/2'));
(async()=>{
 vm.runInContext("openEditorialComposer(data,'c1')",context);
 assert.equal(fields.get('account_id').value,'ig');assert.ok(fields.get('format').innerHTML.includes('carousel'));assert.ok(!fields.get('format').innerHTML.includes('value="video"'));
 fields.get('client_id').value='c2';fields.get('client_id').onchange();assert.equal(fields.get('account_id').value,'fb');assert.ok(fields.get('format').innerHTML.includes('value="video"'));
 fields.get('format').value='text';fields.get('caption').value='Nova legenda';fields.get('caption').oninput();assert.ok(node('#editorial-live-preview').innerHTML.includes('Nova legenda'));
 fields.get('title').value='Título';fields.get('scheduled').value='2026-10-25T15:30';
 const submit=()=>node('#editorial-compose').onsubmit({preventDefault(){},submitter:{dataset:{mode:'schedule'}}});
 shouldFail=true;await submit();assert.equal(closeCount,0);assert.equal(node('#editorial-compose-error').textContent,'Conexão interrompida');
 shouldFail=false;await submit();assert.equal(closeCount,1);assert.equal(calls[0].options.data.nonce,calls[1].options.data.nonce,'A network retry must reuse the submission nonce');
 const saved=calls[1];assert.equal(saved.path,'/agency/editorial/direct');assert.equal(saved.options.data.account_id,'fb');assert.equal(saved.options.data.client_id,'c2');assert.equal(saved.options.data.scheduled,'2026-10-25T15:30-03:00');assert.equal(saved.options.data.mode,'schedule');
 console.log('OK: safe social previews, platform formats, client/account switching, live caption, São Paulo scheduling and safe retry.');
})().catch(e=>{console.error(e);process.exitCode=1});
