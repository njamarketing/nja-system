/* Small, non-blocking celebrations, delivered only from confirmed server sales. */
(()=>{
'use strict';
let identity='',cursor=null,busy=false,queue=[],active=null,timer=null,serial=0;
const reduced=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
function cleanup(){clearTimeout(timer);active?.remove();active=null;document.querySelectorAll('.sale-shuriken').forEach(n=>n.remove());}
function star(){return '<svg viewBox="0 0 100 100" aria-hidden="true"><path d="M50 2 61 35 98 50 65 61 50 98 39 65 2 50 35 39Z" fill="currentColor"/><circle cx="50" cy="50" r="9" fill="#092440"/></svg>';}
window.addEventListener('nja:shuriken-burst',e=>{
 if(reduced()||document.hidden||!active)return;
 const {x,y}=e.detail;
 for(let i=0;i<12;i++){const n=document.createElement('span');n.className='sale-shuriken';n.setAttribute('aria-hidden','true');n.innerHTML=star();n.style.left=x+'px';n.style.top=y+'px';const angle=i/12*Math.PI*2;const distance=Math.min(innerWidth,innerHeight)*(.45+Math.random()*.25);n.style.setProperty('--sx',Math.cos(angle)*distance+'px');n.style.setProperty('--sy',Math.sin(angle)*distance+'px');n.style.setProperty('--delay',i%4*.18+'s');document.body.append(n);n.addEventListener('animationend',()=>n.remove(),{once:true});}
});
function showNext(){
 if(active||!queue.length||document.hidden||!state.user)return;
 const event=queue.shift();if(Date.now()-new Date(event.created).getTime()>120000)return showNext();
 const node=document.createElement('section');node.className='sale-celebration';node.setAttribute('role','status');node.setAttribute('aria-live','polite');
 const month=event.month===new Date().toLocaleDateString('sv-SE',{timeZone:'America/Sao_Paulo'}).slice(0,7)?'':` · ${event.month.slice(5)}/${event.month.slice(0,4)}`;
 node.innerHTML=`<div class="sale-announcement"><span class="sale-emblem" aria-hidden="true">${event.assumed_first?'🏆':'🎉'}</span><div><span class="label">NOVA CONQUISTA NJA</span><strong>${esc(event.name)} fez uma venda!</strong><p>${event.assumed_first?'Assumiu o 1º lugar do pódio nacional!':event.position+'º lugar no ranking nacional'}${esc(month)}</p></div><button type="button" aria-label="Fechar comemoração">×</button></div>`;
 document.body.append(node);active=node;
 const done=()=>{cleanup();showNext()};node.querySelector('button').onclick=done;
 if(!reduced()){
  const effects=document.createElement('div');effects.className='sale-fireworks';effects.setAttribute('aria-hidden','true');
  for(let burst=0;burst<4;burst++)for(let i=0;i<14;i++){const particle=document.createElement('i');const angle=i/14*Math.PI*2;particle.style.setProperty('--bx',[15,80,35,65][burst]+'vw');particle.style.setProperty('--by',[25,30,60,65][burst]+'vh');particle.style.setProperty('--px',Math.cos(angle)*(70+burst*12)+'px');particle.style.setProperty('--py',Math.sin(angle)*(70+burst*12)+'px');particle.style.setProperty('--delay',burst*.65+'s');particle.style.setProperty('--color',['#3cd8ff','#2d8aff','#ffd67a','#8b74ff'][i%4]);effects.append(particle)}node.prepend(effects);
  window.dispatchEvent(new CustomEvent('nja:sale-celebrate',{detail:event}));
 }
 timer=setTimeout(done,6500);
}
async function poll(){
 const id=state.user?.id||'';if(id!==identity){identity=id;cursor=null;serial++;queue=[];cleanup();}
 if(!id||document.hidden||!navigator.onLine||busy)return;
 const gen=serial;busy=true;
 try{const data=await request('/celebrations'+(cursor===null?'':'?after='+cursor));if(gen!==serial||state.user?.id!==id)return;cursor=data.cursor;for(const item of data.items)if(!queue.some(x=>x.seq===item.seq))queue.push(item);queue=queue.slice(-10);showNext()}catch{}finally{busy=false}
}
const previousShell=shell;shell=function(){previousShell();poll();};
setInterval(poll,5000);document.addEventListener('visibilitychange',()=>{if(document.hidden)cleanup();else{showNext();poll()}});
const oldLogout=logoutLocal;logoutLocal=function(){serial++;identity='';cursor=null;queue=[];cleanup();oldLogout();};
})();
