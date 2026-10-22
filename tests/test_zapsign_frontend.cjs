const fs=require('node:fs'),vm=require('node:vm');
const sandbox={console,URL,URLSearchParams,Intl,Date,Set,Promise,Uint8Array,JSON,Number,String,Error,FormData,classList:{},setTimeout,clearTimeout,setInterval:()=>{},document:{querySelector:()=>({hidden:false}),querySelectorAll:()=>[],addEventListener:()=>{}},navigator:{onLine:true,clipboard:{writeText:async()=>{}}},window:{addEventListener:()=>{},isSecureContext:false},location:{hash:'',search:''}};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(__dirname+'/../static/app.js','utf8').replace(/bootstrap\(\);\s*$/,''),sandbox);
vm.runInContext('function renderProfile(){};function enhanceButtons(){};',sandbox);
vm.runInContext(fs.readFileSync(__dirname+'/../static/business.js','utf8'),sandbox);
vm.runInContext(fs.readFileSync(__dirname+'/../static/contracts-zapsign.js','utf8'),sandbox);

const ui=sandbox.window.NJAZapSignUI;
if(!ui)throw Error('ZapSign UI helpers not exported');
if(ui.statusClass('signed')!=='signed'||ui.statusClass('pending')!=='pending')throw Error('Document status mapping failed');
const today=new Date();
const future=new Date(today.getFullYear(),today.getMonth(),today.getDate()+7).toISOString().slice(0,10);
const reminder=ui.reminderText({status:'active',expires:future});
if(!reminder.includes('7 dia'))throw Error('Contract reminder countdown was not preserved');

const source=fs.readFileSync(__dirname+'/../static/contracts-zapsign.js','utf8');
for(const text of ['Criar documento','Contratos e lembretes','Modelos ZapSign','Sincronizar estados ZapSign']){
 if(!source.includes(text))throw Error('Missing contract workspace feature: '+text);
}
if(source.includes('ZAPSIGN_API_TOKEN'))throw Error('API token reference leaked into frontend');
console.log('OK: ZapSign contracts UI, statuses, reminders and frontend secret isolation.');
