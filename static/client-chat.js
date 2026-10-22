(()=>{
'use strict';
const portal=!!document.getElementById('portal-app');
let current=null;
const el=(tag,text,cls)=>{const node=document.createElement(tag);if(text)node.textContent=text;if(cls)node.className=cls;return node};

function mountRoom(host,room){
 if(current)current.cancelled=true;
 host.replaceChildren();
 const run={cancelled:false,busy:false,first:0,last:0};current=run;
 const wrap=el('section',null,'client-chat');host.append(wrap);
 wrap.append(el('h2',room.name,'client-chat-title'),el('p','Você conversa aqui com os colaboradores que participam deste grupo. As mesmas mensagens aparecem no chat interno da equipe.','tiny muted'));
 const older=el('button','Carregar mensagens anteriores','btn secondary');older.type='button';older.hidden=true;
 const log=el('div',null,'client-chat-log');log.setAttribute('role','log');log.setAttribute('aria-label','Mensagens do grupo');log.setAttribute('aria-live','polite');
 const status=el('p','Carregando conversa…','client-chat-status');status.setAttribute('role','status');
 const form=el('form'),input=el('textarea'),send=el('button','Enviar mensagem','btn');
 input.name='text';input.rows=3;input.maxLength=5000;input.required=true;input.placeholder='Escreva para o grupo…';input.setAttribute('aria-label','Mensagem para o grupo');send.type='submit';form.append(input,send);wrap.append(older,log,status,form);
 const path='rooms/'+encodeURIComponent(room.id)+'/messages';
 const alive=()=>!run.cancelled&&wrap.isConnected;
 function render(rows,prepend=false){
  const fragment=document.createDocumentFragment();
  for(const message of rows){
   const own=message.side==='client',item=el('article',null,'client-chat-message '+(own?'mine':'staff'));
   item.append(el('strong',message.name+(own?' · Você':' · NJA')),el('p',message.text),el('small',new Date(message.created).toLocaleString('pt-BR')));fragment.append(item);
   run.first=run.first?Math.min(run.first,message.seq):message.seq;run.last=Math.max(run.last,message.seq);
  }
  if(prepend)log.prepend(fragment);else log.append(fragment);
 }
 async function refresh(initial=false){
  if(!alive()||run.busy)return;run.busy=true;
  try{const near=log.scrollHeight-log.scrollTop-log.clientHeight<90,response=await api(path+(run.last?'?after='+run.last:''));if(!alive())return;render(response.messages);if(initial)older.hidden=!response.has_older;if(initial||near)log.scrollTop=log.scrollHeight;status.textContent='Conversa conectada ao grupo · atualização automática.'}
  catch(error){if(alive()){status.textContent=error.message;if(/Entre no portal|não encontrado|desativado/.test(error.message)){log.replaceChildren();form.hidden=true;run.cancelled=true}}}
  finally{run.busy=false}
 }
 older.onclick=async()=>{older.disabled=true;try{const response=await api(path+'?before='+run.first),height=log.scrollHeight;if(!alive())return;render(response.messages,true);log.scrollTop+=log.scrollHeight-height;older.hidden=!response.has_older}catch(error){status.textContent=error.message}finally{older.disabled=false}};
 form.onsubmit=async event=>{event.preventDefault();if(!input.value.trim())return;send.disabled=true;input.readOnly=true;try{await api(path,{text:input.value});if(!alive())return;input.value='';await refresh();log.scrollTop=log.scrollHeight;input.focus()}catch(error){if(alive())status.textContent=error.message}finally{send.disabled=false;input.readOnly=false}};
 refresh(true);const timer=setInterval(()=>{if(!alive()){clearInterval(timer);return}if(!document.hidden)refresh()},5000);
}

function mountPortal(host){
 const rooms=homeData?.rooms||[];
 if(!rooms.length){const box=el('section',null,'client-chat client-chat-empty');box.append(el('h2','Conversa com a equipe'),el('p','A equipe ainda não vinculou um grupo ao seu cadastro.','muted'));host.append(box);return}
 const shell=el('section',null,'client-group-connection'),area=el('div');
 if(rooms.length>1){const label=el('label','Escolha a conversa','field'),select=el('select');select.setAttribute('aria-label','Grupo do cliente');for(const room of rooms){const option=el('option',room.name);option.value=room.id;select.append(option)}label.append(select);shell.append(label);select.onchange=()=>mountRoom(area,rooms.find(room=>room.id===select.value))}
 shell.append(area);host.append(shell);mountRoom(area,rooms[0]);
}

function scan(){if(!portal)return;const host=document.getElementById('portal-app');if(host?.querySelector('.mission-head')&&!host.querySelector('.client-group-connection')&&!host.querySelector('.client-chat-empty'))mountPortal(host)}
let queued=false;new MutationObserver(()=>{if(!queued){queued=true;queueMicrotask(()=>{queued=false;scan()})}}).observe(document.body,{childList:true,subtree:true});scan();
})();
