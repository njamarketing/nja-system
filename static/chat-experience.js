/* Fast chat delivery, AI typing feedback, message receipts and conversation controls. */
(()=>{
'use strict';
const histories=new Map(),thinkingRooms=new Set(),aiRequests=new Map();
const baseRequest=request;
request=async function(path,options={}){
 const result=await baseRequest(path,options);
 const match=path.match(/^\/rooms\/([^/]+)\/messages$/);
 if(match&&(!options.method||options.method==='GET'))histories.set(match[1],result);
 return result;
};

function dateTime(value){
 if(!value)return 'Ainda não registrado';
 return new Intl.DateTimeFormat('pt-BR',{dateStyle:'short',timeStyle:'medium'}).format(new Date(value));
}
function relativeTime(value){
 if(!value)return '';
 const date=new Date(value),now=new Date(),time=new Intl.DateTimeFormat('pt-BR',{hour:'2-digit',minute:'2-digit'}).format(date);
 const today=date.toDateString()===now.toDateString();
 const yesterday=new Date(now);yesterday.setDate(now.getDate()-1);
 if(today)return 'hoje às '+time;
 if(date.toDateString()===yesterday.toDateString())return 'ontem às '+time;
 return new Intl.DateTimeFormat('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}).format(date);
}
function receiptSummary(message,room){
 const receipts=message.receipts||[],read=receipts.filter(r=>r.read_at),delivered=receipts.filter(r=>r.delivered_at);
 if(read.length){const latest=read.map(r=>r.read_at).sort().at(-1);return {state:'read',label:'✓✓ Visualizado'+(room?.kind==='group'?' por '+read.length+'/'+receipts.length:'')+': '+relativeTime(latest)};}
 if(delivered.length){const latest=delivered.map(r=>r.delivered_at).sort().at(-1);return {state:'delivered',label:'✓✓ Entregue'+(room?.kind==='group'?' para '+delivered.length+'/'+receipts.length:'')+': '+relativeTime(latest)};}
 return {state:'sent',label:'✓ Enviada: '+relativeTime(message.created)};
}
function receiptDetails(message){
 const rows=(message.receipts||[]).map(r=>`<div class="receipt-person"><div class="grow"><strong>${esc(r.name)}</strong><small>${r.read_at?'Visualizou a mensagem':'Ainda não visualizou'}</small></div><dl><dt>Entregue no dispositivo</dt><dd>${esc(dateTime(r.delivered_at))}</dd><dt>Visualizada</dt><dd>${esc(dateTime(r.read_at))}</dd></dl></div>`).join('');
 return `<section class="message-detail"><dl><dt>Enviada</dt><dd>${esc(dateTime(message.created))}</dd></dl>${rows||'<p class="muted">Esta conversa não possui outro destinatário para confirmar a entrega.</p>'}</section>`;
}
function showDetails(message){modal('Dados da mensagem',receiptDetails(message),true);}
function decorateReceipts(root,rid){
 const history=histories.get(rid),room=state.rooms.find(r=>r.id===rid);if(!root||!history||!room)return;
 for(const el of $$('.message[data-message-id]',root)){
  const message=history.messages?.find(m=>m.id===el.dataset.messageId);if(!message)continue;
  el.querySelector('.message-delivery')?.remove();
  el.querySelector('[data-message-details]')?.remove();
  if(message.user_id===state.user.id){
   const summary=receiptSummary(message,room),status=document.createElement('button');status.type='button';status.className='message-delivery '+summary.state;status.textContent=summary.label;status.setAttribute('aria-label',summary.label+'. Ver dados da mensagem');status.onclick=()=>showDetails(message);el.append(status);
   const actions=el.querySelector('.message-actions');if(actions){const details=document.createElement('button');details.type='button';details.dataset.messageDetails=message.id;details.textContent='ⓘ Dados';details.onclick=()=>showDetails(message);actions.append(details);}
  }
 }
}

function typingMarkup(){return `<div class="ai-typing-mark"><img src="/nja-symbol.png" alt=""><div><strong>Ninja IA está digitando</strong><span class="typing-dots" aria-label="digitando"><i></i><i></i><i></i></span></div></div>`;}
function paintThinking(root,rid){
 root?.querySelector('.ai-typing-message')?.remove();if(!root||!thinkingRooms.has(rid))return;
 const item=document.createElement('div');item.className='message ai-typing-message';item.setAttribute('role','status');item.setAttribute('aria-live','polite');item.innerHTML=typingMarkup();root.append(item);root.scrollTop=root.scrollHeight;
}
function setThinking(rid,active){
 if(active)thinkingRooms.add(rid);else thinkingRooms.delete(rid);
 if(state.page==='chats'&&state.room===rid)paintThinking($('#messages'),rid);
 if(typeof floatingRoom!=='undefined'&&floatingRoom===rid)paintThinking($('#float-messages'),rid);
 window.dispatchEvent(new CustomEvent('nja:ai-thinking',{detail:{active,roomId:rid,source:'chat-experience'}}));
}
function expectsAi(room,text){return !!(room?.ai_enabled&&can('ai')&&(room.kind==='assistant'||/@ninja\b/i.test(text)));}
async function finishAi(rid,prompt){
 if(aiRequests.has(rid))return aiRequests.get(rid);
 const work=(async()=>{try{await request('/rooms/'+rid+'/ai',{method:'POST',data:{prompt}});if(state.page==='chats'&&state.room===rid)await refreshMessages(true);if(typeof floatingRoom!=='undefined'&&floatingRoom===rid)await refreshFloating(true);}catch(e){toast(e.message)}finally{aiRequests.delete(rid);setThinking(rid,false)}})();
 aiRequests.set(rid,work);return work;
}
function optimistic(root,text){
 if(!root)return;if(!root.querySelector('.message'))root.innerHTML='';
 const item=document.createElement('div');item.className='message mine message-pending';item.innerHTML=`<span class="sender">Você</span><div class="bubble">${esc(text)}</div><small>Enviando…</small>`;root.append(item);root.scrollTop=root.scrollHeight;
}
async function sendFast(form,rid,root){
 const input=form?.elements.text,text=input?.value.trim();if(!text)return;
 const room=state.rooms.find(r=>r.id===rid),replyTo=form.dataset.replyTo||null,replyKind=form.dataset.replyKind||'message',expect=expectsAi(room,text);
 input.value='';delete form.dataset.replyTo;delete form.dataset.replyKind;form.querySelector('.message-reply-draft')?.remove();optimistic(root,text);if(expect)setThinking(rid,true);
 let saved=false;
 try{
  const result=await request('/rooms/'+rid+'/messages',{method:'POST',data:{text,reply_to:replyTo,reply_kind:replyKind,defer_ai:true}});
  saved=true;
  if(state.page==='chats'&&state.room===rid)await refreshMessages(true);if(typeof floatingRoom!=='undefined'&&floatingRoom===rid)await refreshFloating(true);
  if(result.ai_pending)finishAi(rid,text);else if(expect)setThinking(rid,false);
 }catch(e){setThinking(rid,false);if(!saved&&input.isConnected&&!input.value)input.value=text;toast(saved?'Mensagem salva. '+e.message:e.message);if(!saved)root?.querySelector('.message-pending')?.remove();}
}
function bindFastForm(form,rid,root){
 if(!form||form.dataset.fastSendBound)return;form.dataset.fastSendBound='1';
 form.addEventListener('submit',e=>{e.preventDefault();e.stopImmediatePropagation();sendFast(form,rid,root)},{capture:true});
}

function decoratePresence(){
 const room=state.rooms.find(r=>r.id===state.room),head=$('.conversation-head');if(!room||!head)return;
 const sub=$('.grow small',head);if(room.kind==='direct'){const id=room.members.find(x=>x!==state.user.id),person=user(id);if(sub){sub.dataset.presence=id;sub.classList.add('chat-presence');sub.textContent=presenceLabel(person);sub.classList.toggle('online',!!person.online);}}
 else if(room.kind==='assistant'&&sub){sub.textContent=thinkingRooms.has(room.id)?'Ninja IA está digitando…':'Ninja IA disponível';}
}
function deleteConversation(room){
 modal('Excluir conversa',`<p>Esta conversa será removida da sua lista. Ela continuará disponível para os outros participantes e reaparecerá se alguém enviar uma nova mensagem.</p><div class="formfoot"><button type="button" class="btn secondary" data-cancel>Cancelar</button><button type="button" class="btn danger" id="confirm-delete-chat">Excluir conversa</button></div>`);
 $('[data-cancel]').onclick=closeModal;$('#confirm-delete-chat').onclick=async e=>{const b=e.currentTarget;b.disabled=true;try{await request('/rooms/'+room.id,{method:'DELETE',data:{}});if(typeof floatingRoom!=='undefined'&&floatingRoom===room.id){floatingRoom=null;$('#floating-host').innerHTML='';}closeModal();await load();state.room=state.rooms.find(r=>!r.archived)?.id||state.rooms[0]?.id||null;history.replaceState(null,'','#chats');renderContent();toast('Conversa excluída da sua lista.')}catch(err){toast(err.message);b.disabled=false}};
}
function decorateDelete(){
 const room=state.rooms.find(r=>r.id===state.room),head=$('.conversation-head');if(!room||!head||room.kind==='general'||$('#delete-chat'))return;
 const button=document.createElement('button');button.type='button';button.id='delete-chat';button.className='iconbtn delete-chat';button.title='Excluir conversa';button.setAttribute('aria-label','Excluir conversa');button.innerHTML='<span class="delete-symbol" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M4 7h16M9 7V4h6v3m3 0-1 14H7L6 7m4 4v6m4-6v6"/></svg></span><span class="archive-label">Excluir</span>';button.onclick=()=>deleteConversation(room);head.append(button);
}

const previousRefresh=refreshMessages;refreshMessages=async function(force=false){const rid=state.room;await previousRefresh(force);if(state.room!==rid)return;decorateReceipts($('#messages'),rid);paintThinking($('#messages'),rid);decoratePresence();};
const previousFloatRefresh=refreshFloating;refreshFloating=async function(force=false){const rid=typeof floatingRoom==='undefined'?null:floatingRoom;await previousFloatRefresh(force);if(rid&&floatingRoom===rid){decorateReceipts($('#float-messages'),rid);paintThinking($('#float-messages'),rid);}};
const previousFloatRender=renderFloating;renderFloating=function(){previousFloatRender();if(!floatingRoom)return;const form=$('#float-form');if(form){form.onsubmit=null;bindFastForm(form,floatingRoom,$('#float-messages'));}};
const previousBind=bindChatDetails;bindChatDetails=function(){previousBind();const room=state.rooms.find(r=>r.id===state.room);if(!room)return;bindFastForm($('#messageform'),room.id,$('#messages'));decoratePresence();decorateDelete();};
const previousHeartbeat=heartbeat;heartbeat=async function(){await previousHeartbeat();decoratePresence();};
window.addEventListener('nja:ai-thinking',e=>{if(e.detail?.source!=='playful'||!e.detail.roomId)return;const rid=e.detail.roomId;if(e.detail.active)thinkingRooms.add(rid);else thinkingRooms.delete(rid);if(state.page==='chats'&&state.room===rid){paintThinking($('#messages'),rid);decoratePresence();}if(typeof floatingRoom!=='undefined'&&floatingRoom===rid)paintThinking($('#float-messages'),rid);});

window.NJAChatExperience={receiptSummary,dateTime,relativeTime};
})();
