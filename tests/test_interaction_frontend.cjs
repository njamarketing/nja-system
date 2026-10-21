const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function node(){return {innerHTML:'',textContent:'',dataset:{},children:[],isConnected:true,style:{setProperty(){}},classList:{toggle(){},add(){},remove(){}},setAttribute(k,v){this[k]=v},append(...n){this.children.push(...n)},prepend(...n){this.children.unshift(...n)},before(n){this.children.push(n)},replaceWith(n){this.replacement=n},querySelector(){return this.button||(this.button=node())},querySelectorAll(){return []},remove(){this.isConnected=false},focus(){},addEventListener(){}}}
(async()=>{
 const elements=new Map(),calls=[],hooks={};const get=s=>elements.get(s)||null;
 const header=node(),name=node(),expand=node(),form=node();form.elements={text:{value:'Rascunho'}};header.querySelector=()=>name;
 elements.set('.float-header',header);elements.set('#float-expand',expand);elements.set('#float-form',form);
 const context={console,Date,Promise,Map,Set,Error,String,encodeURIComponent,setTimeout:()=>0,state:{user:{id:'master'},users:[],rooms:[{id:'dm',kind:'direct',members:['master','alice']}]},floatingRoom:'dm',refreshMessages:async()=>{},refreshFloating:async()=>{},renderFloating:()=>{},heartbeat:async()=>{},storyViewer:()=>{},brand:()=>'<img class="systems-logo">',logoutLocal:()=>{},request:async()=>({messages:[],files:[]}),$:(s,r)=>r?r.querySelector(s):get(s),$$:()=>[],user:id=>({id,name:'Alice',online:true}),presenceLabel:u=>u.online?'Online':'Offline',ic:n=>n,esc,document:{addEventListener:(k,f)=>hooks[k]=f,createElement:node,activeElement:null,hidden:false},window:{visualViewport:null},matchMedia:()=>({matches:true}),chooseCall:(r,m)=>calls.push([r.id,m]),toast:()=>{}};
 vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/../static/interaction-updates.js','utf8'),context);
 vm.runInContext('renderFloating()',context);
 assert.equal(expand.children.length,2);expand.children[0].onclick();expand.children[1].onclick();assert.deepEqual(calls,[['dm','audio'],['dm','video']]);assert.equal(form.elements.text.value,'Rascunho');
 assert.ok(vm.runInContext('brand()',context).includes('outlined-system-logo'));
 const intervals=[],events=[],body=node();let currentEvent=null;
 const sale={console,Date,Promise,Math,String,Number,setInterval:f=>intervals.push(f),setTimeout:()=>0,clearTimeout(){},state:{user:{id:'bob'}},navigator:{onLine:true},matchMedia:()=>({matches:true}),shell(){},logoutLocal(){},esc,innerWidth:1200,innerHeight:800,document:{hidden:false,body,createElement:node,querySelectorAll:()=>[],addEventListener(){}},window:{addEventListener(){},dispatchEvent:e=>events.push(e)},CustomEvent:function(type,opts){this.type=type;this.detail=opts.detail},request:async path=>path.includes('?')?{cursor:1,items:currentEvent?[currentEvent]:[]}:{cursor:0,items:[]}};
 vm.createContext(sale);vm.runInContext(fs.readFileSync(__dirname+'/../static/celebrations.js','utf8'),sale);
 await intervals[0]();assert.equal(body.children.length,0,'No replay on first connection');
 currentEvent={seq:1,name:'<img src=x>',position:1,assumed_first:true,month:'2026-10',created:new Date().toISOString()};await intervals[0]();
 assert.equal(body.children.length,1);const banner=body.children[0];assert.ok(banner.innerHTML.includes('&lt;img src=x&gt;'));assert.ok(banner.innerHTML.includes('Assumiu o 1º lugar'));assert.equal(events.length,0,'Reduced motion does not launch particles');
 sale.state.user=null;await intervals[0]();assert.equal(banner.isConnected,false,'Logout removes private event UI');
 console.log('OK: floating voice/video, draft preservation, logo wrapper, sales baseline, escaped winner, reduced motion and logout cleanup.');
})().catch(e=>{console.error(e);process.exitCode=1});
