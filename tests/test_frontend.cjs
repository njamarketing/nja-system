// Structural rendering checks; not a substitute for browser/device QA.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/../static/app.js','utf8').replace(/bootstrap\(\);\s*$/,'');
const sandbox={console,URL,URLSearchParams,Intl,Date,Set,Promise,Uint8Array,JSON,Number,String,Error,setTimeout,clearTimeout,document:{querySelector:()=>({hidden:false}),querySelectorAll:()=>[],addEventListener:()=>{}},navigator:{onLine:true},window:{addEventListener:()=>{},isSecureContext:false},location:{hash:'',search:''}};
vm.createContext(sandbox);vm.runInContext(source,sandbox);
vm.runInContext(`
state.user={id:'master',name:'Nelson Zeni Junior',email:'master@example.test',master:true,permissions:[],preferences:{tasks:true,events:true,messages:true}};
state.users=[{...state.user,active:1,area:'Direção',title:'Master',bio:'<script>alert(1)</script>'}];
state.metrics={criterion:'Critério real',users:[{id:'master',name:'Nelson',area:'Direção',total:1,done:0,percent:0,late:0,pending:1,progress:0,approval:0}]};
state.tasks=[{id:'one',title:'<img src=x onerror=alert(1)>',description:'Teste',project:'NJA',owner:'master',creator:'master',status:'pending',priority:'normal',due:new Date().toISOString(),checklist:[],members:[]}];
state.events=[{id:'event',title:'Reunião',start:'2026-10-14T12:00:00+00:00',end:'2026-10-14T13:00:00+00:00',recurrence:'weekly',until_date:'2026-11-14T12:00:00+00:00',members:['master']}];
state.rooms=[{id:'general',name:'Equipe NJA',kind:'general',members:['master'],unread:0}];
state.roles=[{id:'member',name:'Equipe',permissions:['tasks']}];
state.notifications=[{id:'n',title:'Aviso',body:'Teste',link:'tasks:one',category:'tasks',seen:0,created:new Date().toISOString()}];
for(const name of ['dashboard','tasksPage','calendarPage','chatsPage','teamPage','notificationsPage','settingsPage']){
 const html=eval(name+'()');if(!html||typeof html!=='string')throw Error('Página vazia: '+name);
 if(html.includes('<img src=x onerror=')||html.includes('<script>alert'))throw Error('Conteúdo sem escape: '+name);
}
state.taskView='list';tasksPage();state.calView='week';calendarPage();state.calView='day';calendarPage();
const occurrences=expandedEvents(new Date('2026-10-14T00:00:00Z'),new Date('2026-11-14T23:59:59Z'));
if(occurrences.length!==5)throw Error('Recorrência não expandida corretamente.');
`,sandbox);
console.log('OK: 7 telas, lista/Kanban, 3 visões de agenda, escape HTML e recorrência.');
