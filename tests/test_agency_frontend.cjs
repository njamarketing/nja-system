const fs=require('node:fs'),vm=require('node:vm');
const nodes=new Map();function node(key){if(!nodes.has(key))nodes.set(key,{innerHTML:'',value:key==='#editorial-month'?'2026-10':'',hidden:false,addEventListener(){},querySelector:()=>node('child'),querySelectorAll:()=>[],focus(){}});return nodes.get(key)}
const sandbox={console,URL,URLSearchParams,Intl,Date,Set,Promise,Uint8Array,JSON,Number,String,Error,setTimeout:()=>{},clearTimeout,setInterval:()=>{},document:{querySelector:node,querySelectorAll:()=>[],addEventListener:()=>{}},navigator:{onLine:true},window:{addEventListener:()=>{},isSecureContext:false},location:{hash:'',search:''}};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(__dirname+'/../static/app.js','utf8').replace(/bootstrap\(\);\s*$/,''),sandbox);vm.runInContext('function renderProfile(){};function enhanceButtons(){};',sandbox);
for(const file of ['business','teamwork','agency','agency-production','agency-approvals','agency-editorial','agency-commercial','agency-finance','agency-calendar','agency-whatsapp','agency-ads'])vm.runInContext(fs.readFileSync(__dirname+'/../static/'+file+'.js','utf8'),sandbox);
vm.runInContext(`
state.user={id:'master',name:'Master',master:true,permissions:[],branch:'foz',active:true};state.users=[state.user];state.company={branches:[{id:'foz',name:'Foz'},{id:'cascavel',name:'Cascavel'}]};state.tasks=[];state.clients=[{id:'c',name:'Cliente'}];
const evil='<img src=x onerror=alert(1)>',root=$('#content');
const checks=[['marketing',{accounts:[],requests:[]}],['production',{plans:[{id:'p',name:evil,items:[]}],projects:[]}],['approvals',{items:[{id:'r',title:evil,status:'draft',versions:[]}],accounts:[],uploads:[]}],['editorial',{accounts:[],posts:[{id:'p',title:evil,scheduled:'2026-10-01',status:'draft',format:'text'}],reviews:[]}],['commercial_ops',{goals:[],followups:[],proposals:[{id:'p',title:evil,status:'draft',versions:[]}],commissions:[],rules:[],sales:[],leads:[]}],['agency_finance',{items:[{id:'e',description:evil,category:evil,reference:evil,kind:'expense',amount:1000,competence:'2026-10'}],rates:[],capacity:[],projects:[]}]];
for(const [page,data] of checks){window.agencySections[page](data);if(root.innerHTML.includes(evil)||$('#ledger-table').innerHTML.includes(evil)||$('#editorial-calendar').innerHTML.includes(evil))throw Error('Unescaped '+page);}
renderAgencyReport({month:'2026-10',production:{done:0,deliverables:0,late:0,extra:0,logged_seconds:0},capacity:[],financial:null});if(!root.innerHTML.includes('Valores financeiros'))throw Error('Report permission boundary missing');
modal(evil,'test');if($('#modal-root').innerHTML.includes(evil))throw Error('Modal title XSS');
state.user={id:'alice',master:false,permissions:['production']};const steps=tutorialSteps();if(!steps.some(s=>s.page==='production')||steps.some(s=>s.page==='agency_finance'))throw Error('Tutorial permissions');
for(const page of ['agency_finance','editorial','commercial_ops'])if(navAllowed(page))throw Error('Forbidden navigation '+page);
`,sandbox);
console.log('OK: new modules render, escape user content, restrict navigation and tutorial.');
