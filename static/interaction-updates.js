/* NJA 1.17 — room-scoped interactions and private story viewers. */
(()=>{
'use strict';
const palette=['👍','❤️','😂','🎉','🔥','🥷','👏','✅'],histories=new Map();
let reactionOpen=null,visibleStoryRecorder=null;
document.addEventListener('visibilitychange',()=>{if(!document.hidden)visibleStoryRecorder?.();});
const oldRequest=request;
request=async function(path,options={}){
 const result=await oldRequest(path,options);
 const m=path.match(/^\/rooms\/([^/]+)\/messages$/);
 if(m&&(!options.method||options.method==='GET')){histories.delete(m[1]);histories.set(m[1],result);if(histories.size>10)histories.delete(histories.keys().next().value);}
 return result;
};
function targetFrom(history,id,kind){return (kind==='file'?history?.files:history?.messages)?.find(m=>m.id===id);}
function bindReply(form,item,kind){
 if(!form?.elements.text)return;
 form.dataset.replyTo=item.id;form.dataset.replyKind=kind;
 form.querySelector('.message-reply-draft')?.remove();
 const hint=document.createElement('div');hint.className='message-reply-draft';
 hint.innerHTML=`<div><strong>Respondendo a ${esc(user(item.user_id).name)}</strong><span>${esc((kind==='file'?item.name:item.text).slice(0,160))}</span></div><button type="button" aria-label="Cancelar resposta">×</button>`;
 hint.querySelector('button').onclick=()=>{delete form.dataset.replyTo;delete form.dataset.replyKind;hint.remove();form.elements.text.focus();};
 form.prepend(hint);form.elements.text.focus();
}
async function decorateMessages(root,rid,form){
 const identity=state.user?.id;if(!root||!identity)return;
 const history=histories.get(rid);if(!history)return;
 let data;try{data=await request('/rooms/'+rid+'/interactions')}catch{return}
 if(!root.isConnected||identity!==state.user?.id||root!==$('#'+root.id))return;
 const wasBottom=root.scrollHeight-root.scrollTop-root.clientHeight<110;
 const room=state.rooms.find(r=>r.id===rid),canSend=room?.can_send!==false;
 $$('.message[data-message-id]',root).forEach(el=>{
  const id=el.dataset.messageId,kind=el.dataset.messageKind||'message',item=targetFrom(history,id,kind);if(!item)return;
  // Replace legacy controls, so the full and floating chat behave identically.
  $$('.reaction-tools,.reaction-counts,.message-actions,.message-reaction-summary,.message-quote',el).forEach(n=>n.remove());
  if(item.reply){const quote=document.createElement('button');quote.type='button';quote.className='message-quote';quote.innerHTML=item.reply.unavailable?'Mensagem original indisponível':`<strong>${esc(item.reply.name)}</strong><span>${esc(item.reply.text)}</span>`;quote.onclick=()=>{const target=$$('.message[data-message-id]',root).find(n=>n.dataset.messageId===item.reply.id);if(!target)return toast('A mensagem original não está entre as mensagens carregadas.');target.scrollIntoView({block:'nearest',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});target.classList.add('message-reply-highlight');setTimeout(()=>target.classList.remove('message-reply-highlight'),1800)};$('.bubble',el).prepend(quote);}
  const controls=document.createElement('div');controls.className='message-actions';
  const reply=document.createElement('button');reply.type='button';reply.textContent='↩ Responder';reply.disabled=!canSend;reply.onclick=()=>bindReply(form,item,kind);
  const react=document.createElement('button');react.type='button';react.textContent='☺ Reagir';react.disabled=!canSend;react.setAttribute('aria-expanded','false');
  controls.append(reply,react);el.append(controls);
  const send=async emoji=>{try{await request('/rooms/'+rid+'/interactions',{method:'POST',data:{target_id:id,kind,emoji}});reactionOpen?.remove();reactionOpen=null;if(root.id==='messages')await refreshMessages(true);else await refreshFloating(true)}catch(e){toast(e.message)}};
  react.onclick=()=>{reactionOpen?.remove();const pop=document.createElement('div');pop.className='message-reaction-picker';pop.setAttribute('role','group');pop.setAttribute('aria-label','Escolher reação');for(const emoji of palette){const b=document.createElement('button');b.type='button';b.textContent=emoji;b.setAttribute('aria-label','Reagir com '+emoji);b.onclick=()=>{react.setAttribute('aria-expanded','false');send(emoji)};pop.append(b)}const close=document.createElement('button');close.type='button';close.textContent='×';close.setAttribute('aria-label','Fechar reações');close.onclick=()=>{pop.remove();react.setAttribute('aria-expanded','false');reactionOpen=null;react.focus()};pop.append(close);controls.append(pop);reactionOpen=pop;react.setAttribute('aria-expanded','true');pop.querySelector('button').focus();};
  const entries=data.reactions.filter(r=>r.target_id===id&&r.kind===kind);if(entries.length){const counts=document.createElement('div');counts.className='message-reaction-summary';for(const emoji of palette){const people=entries.filter(x=>x.emoji===emoji);if(!people.length)continue;const b=document.createElement('button');b.type='button';b.textContent=emoji+' '+people.length;b.classList.toggle('selected',people.some(x=>x.user_id===identity));b.setAttribute('aria-pressed',String(people.some(x=>x.user_id===identity)));b.title=people.map(p=>user(p.user_id).name).join(', ');b.setAttribute('aria-label',emoji+': '+b.title);b.disabled=!canSend;b.onclick=()=>send(emoji);counts.append(b)}el.append(counts)}
 });
 if(wasBottom)root.scrollTop=root.scrollHeight;
}
const oldRefresh=refreshMessages;refreshMessages=async function(force=false){const rid=state.room;await oldRefresh(force);if(state.page==='chats'&&state.room===rid)await decorateMessages($('#messages'),rid,$('#messageform'));};
const oldFloatRefresh=refreshFloating;refreshFloating=async function(force=false){const rid=floatingRoom;await oldFloatRefresh(force);if(floatingRoom===rid){floatPresence();await decorateMessages($('#float-messages'),rid,$('#float-form'));}};
function floatPresence(){const room=state.rooms.find(r=>r.id===floatingRoom);if(!room||room.kind!=='direct')return;const other=room.members.find(id=>id!==state.user.id),person=user(other);let el=$('#float-presence');if(!el)return;el.textContent=presenceLabel(person);el.classList.toggle('online',!!person.online);}
const oldFloatRender=renderFloating;renderFloating=function(){
 const old=$('#float-form'),draft=old?.elements.text?.value||'',replyTo=old?.dataset.replyTo,replyKind=old?.dataset.replyKind;
 oldFloatRender();const room=state.rooms.find(r=>r.id===floatingRoom),header=$('.float-header');if(!room||!header)return;
 const name=$('strong',header),title=document.createElement('div');title.className='float-person';name.replaceWith(title);title.append(name);
 if(room.kind==='direct'){const status=document.createElement('small');status.id='float-presence';title.append(status);floatPresence();for(const [mode,label,icon] of [['audio','Ligar por voz','phone'],['video','Ligar por vídeo','video']]){const b=document.createElement('button');b.className='float-call';b.type='button';b.setAttribute('aria-label',label);b.title=label;b.innerHTML=ic(icon);b.onclick=()=>chooseCall(room,mode);$('#float-expand').before(b);}}
 const form=$('#float-form');if(form?.elements.text){form.elements.text.value=draft;if(replyTo){const target=targetFrom(histories.get(room.id),replyTo,replyKind);if(target)bindReply(form,target,replyKind);}}
};
const oldHeartbeat=heartbeat;heartbeat=async function(){await oldHeartbeat();if(state.user)floatPresence();};
const oldStory=storyViewer;storyViewer=function(id,index=0){
 oldStory(id,index);const story=state.stories.find(s=>s.id===activeStoryId),viewer=$('.story-viewer'),identity=state.user.id;visibleStoryRecorder=null;if(!story||!viewer)return;
 const same=()=>state.user?.id===identity&&activeStoryId===story.id&&viewer.isConnected;
 if(story.user_id!==identity){let sent=false;const record=()=>{if(sent||document.hidden||!same())return;sent=true;request('/stories/'+story.id+'/view',{method:'POST',data:{}}).catch(()=>{sent=false})};const img=$('img',viewer);visibleStoryRecorder=record;if(img&&!img.complete)img.addEventListener('load',record,{once:true});else if(!img||img.naturalWidth>0)record();return;}
 const section=document.createElement('section');section.className='story-private-viewers';section.innerHTML='<button type="button" class="btn secondary small" aria-expanded="false">Quem visualizou</button><p class="tiny muted">Visível somente para você.</p><div class="story-viewer-list" hidden></div>';viewer.append(section);
 const b=$('button',section),list=$('.story-viewer-list',section);b.onclick=async()=>{const expanded=b.getAttribute('aria-expanded')==='true';b.setAttribute('aria-expanded',String(!expanded));list.hidden=expanded;if(expanded)return;b.disabled=true;try{const data=await request('/stories/'+story.id+'/viewers');if(!same())return;b.textContent='Quem visualizou ('+data.count+')';list.innerHTML=data.viewers.map(v=>`<div class="row">${avatar(v)}<div><strong>${esc(v.name)}</strong><small>${fmt(v.viewed)}</small></div></div>`).join('')||'<p>Nenhuma visualização registrada ainda.</p>';}catch(e){if(same())list.textContent=e.message}finally{b.disabled=false}};
};
// Existing alpha in the official logo is preserved; only its presentation changes.
const oldBrand=brand;brand=function(){return oldBrand().replace('class="systems-logo"','class="systems-logo outlined-system-logo"');};
function fitNinjaKeyboard(){const panel=$('.ninja-talk'),v=window.visualViewport;if(!panel||!v)return;const typing=!!document.activeElement?.closest('.ninja-chat-form');panel.classList.toggle('ninja-keyboard-open',typing&&innerHeight-v.height>100);panel.style.setProperty('--ninja-visible-height',v.height+'px');panel.style.setProperty('--ninja-visible-top',v.offsetTop+'px');}
window.visualViewport?.addEventListener('resize',fitNinjaKeyboard);window.visualViewport?.addEventListener('scroll',fitNinjaKeyboard);document.addEventListener('focusin',fitNinjaKeyboard);document.addEventListener('focusout',()=>setTimeout(fitNinjaKeyboard,100));
const oldLogout=logoutLocal;logoutLocal=function(){histories.clear();reactionOpen?.remove();reactionOpen=null;oldLogout();};
})();
