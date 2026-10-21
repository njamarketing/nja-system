const fs=require('node:fs'),vm=require('node:vm');
const sandbox={console,URL,URLSearchParams,Intl,Date,Set,Promise,Uint8Array,JSON,Number,String,Error,setTimeout,clearTimeout,setInterval:()=>{},document:{querySelector:()=>({hidden:false}),querySelectorAll:()=>[],addEventListener:()=>{}},navigator:{onLine:true},window:{addEventListener:()=>{},isSecureContext:false},location:{hash:'',search:''}};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(__dirname+'/../static/app.js','utf8').replace(/bootstrap\(\);\s*$/,''),sandbox);vm.runInContext('function renderProfile(){};function enhanceButtons(){};',sandbox);vm.runInContext(fs.readFileSync(__dirname+'/../static/business.js','utf8'),sandbox);
vm.runInContext(`
state.user={id:'master',name:'Master',master:true,permissions:[]};state.users=[state.user];state.clients=[];
const evil='<img src=x onerror=alert(1)>';
biz.items=[{id:'id',name:evil,phone:'5545999999999',company:'Empresa',city:'Foz',industry:'Serviços',product:'Site',budget:120050,owner:'master',stage:'new',source:'manual'}];biz.salespeople=[state.user];
if(crmPage().includes(evil))throw Error('Lead XSS');
biz.banks={itau:'Itaú',cora:'Cora',infinitepay:'InfinitePay'};biz.items=[{id:'id',reference:'REF',bank:'itau',customer:evil,amount:12345,due:'2026-01-01',status:'open',source:'manual',documents:[{id:'doc',name:evil}]}];
if(financePage().includes(evil))throw Error('Finance XSS');
biz.items.push({...biz.items[0],id:'test',bank:'cora',reference:'stage:inv_1',amount:99999999});if(invoiceRows().length!==1)throw Error('Sandbox included in actual totals');
biz.items=[{id:'contract',title:evil,owner:'master',start:'2026-01-01',expires:'2026-12-01',renewal:null,amount:10000,status:'active',notes:evil,documents:[]}];if(contractsPage().includes(evil))throw Error('Contract XSS');
biz.items=[{id:'post',platform:'facebook',text:evil,status:'draft',created:new Date().toISOString()}];if(marketingPage().includes(evil))throw Error('Post XSS');
state.user={id:'alice',name:'Alice',master:false,permissions:['crm']};if(navAllowed('finance')||navAllowed('contracts')||navAllowed('integrations_manage'))throw Error('Forbidden navigation');
`,sandbox);
console.log('OK: business rendering, XSS escaping, sandbox exclusion, permission-aware navigation.');
