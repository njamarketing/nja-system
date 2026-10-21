const fs=require('node:fs'),vm=require('node:vm');
const sandbox={console,URL,URLSearchParams,Intl,Date,Set,Promise,Uint8Array,JSON,Number,String,Error,setTimeout,clearTimeout,setInterval:()=>{},document:{querySelector:()=>({hidden:false}),querySelectorAll:()=>[],addEventListener:()=>{}},navigator:{onLine:true},window:{addEventListener:()=>{},isSecureContext:false},location:{hash:'',search:''}};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(__dirname+'/../static/app.js','utf8').replace(/bootstrap\(\);\s*$/,''),sandbox);vm.runInContext('function renderProfile(){};function enhanceButtons(){};',sandbox);vm.runInContext(fs.readFileSync(__dirname+'/../static/business.js','utf8'),sandbox);
vm.runInContext(fs.readFileSync(__dirname+'/../static/teamwork.js','utf8'),sandbox);
vm.runInContext(`
state.user={id:'alice',name:'Alice',master:false,permissions:['dashboard','sales_ranking','chats']};
state.company={branches:[{id:'foz',name:'Foz'},{id:'teixeira',name:'Teixeira'},{id:'cascavel',name:'Cascavel/PR'}]};
const evil='<img src=x onerror=alert(1)>';
salesRank={items:[{id:'alice',name:evil,amount:50000,deals:1},{id:'bob',name:'Bob',amount:20000,deals:1},{id:'c',name:'Carol',amount:10000,deals:1}],month:'2026-10',branch:'national'};
const html=rankingCard();if(html.includes(evil))throw Error('ranking XSS');
for(const word of ['place-1','place-2','place-3','Cascavel/PR','Nacional'])if(!html.includes(word))throw Error('Missing '+word);
let steps=tutorialSteps();if(steps.some(s=>s.page==='finance'||s.page==='crm'))throw Error('Tour exposes restricted modules');
if(!steps.some(s=>s.page==='chats'))throw Error('Missing permitted chat tutorial');
state.user.permissions=['settings'];if(navAllowed('sales_ranking'))throw Error('Unauthorized sales navigation');
`,sandbox);
console.log('OK: podium, ranking escaping, three units, tutorial permission filtering.');
