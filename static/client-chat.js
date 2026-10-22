(()=>{
const portal=!!document.getElementById('portal-app');let current=null;
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;};
function mount(host,cid){
 if(current)current.cancelled=true;
 const run={cancelled:false,busy:false,first:0,last:0};current=run;
 const wrap=el('section',null,'client-chat');host.append(wrap);
 wrap.append(el('h2',portal?'Converse com a NJA':'Atendimento ao cliente'),el('p','Esta conversa é compartilhada com os contatos ativos desta empresa e a equipe NJA autorizada.','tiny muted'));
 const older=el('button','Carregar mensagens anteriores','btn secondary');older.type='button';older.hidden=true;
 const log=el('div',null,'client-chat-log');log.setAttribute('role','log');log.setAttribute('aria-label','Mensagens do atendimento');log.setAttribute('aria-live','polite');
 const status=el('p','Carregando conversa…','client-chat-status');status.setAttribute('role','status');
 const form=el('form');const input=el('textarea');input.name='text';input.rows=3;input.maxLength=5000;input.required=true;input.placeholder='Escreva sua mensagem…';input.setAttribute('aria-label','Mensagem ao atendimento');
 const send=el('button','Enviar mensagem','btn');send.type='submit';form.append(input,send);wrap.append(older,log,status,form);
 const path=portal?'chat':'/agency/client-chats/'+encodeURIComponent(cid);
 const call=(suffix='',data)=>portal?api(path+suffix,data):request(path+suffix,data?{method:'POST',data}:{});
 const alive=()=>!run.cancelled&&wrap.isConnected;
 function render(rows,prepend=false){const fragment=document.createDocumentFragment();for(const m of rows){const item=el('article',null,'client-chat-message '+m.side);item.append(el('strong',m.name+(m.side==='staff'?' · NJA':' · Cliente')),el('p',m.text),el('small',new Date(m.created).toLocaleString('pt-BR')));fragment.append(item);run.first=run.first?Math.min(run.first,m.seq):m.seq;run.last=Math.max(run.last,m.seq);}if(prepend)log.prepend(fragment);else log.append(fragment);}
 async function refresh(initial=false){if(!alive()||run.busy)return;run.busy=true;try{const near=log.scrollHeight-log.scrollTop-log.clientHeight<90;const r=await call(run.last?'?after='+run.last:'');if(!alive())return;render(r.messages);if(initial){older.hidden=!r.has_older;}if(initial||near)log.scrollTop=log.scrollHeight;status.textContent='Atualização automática a cada 5 segundos.';}catch(e){if(alive()){status.textContent=e.message;if(/Entre no portal|Sem permissão|permissão para|fora da sua carteira|Cliente desativado/.test(e.message)){log.replaceChildren();form.hidden=true;run.cancelled=true;}}}finally{run.busy=false;}}
 older.onclick=async()=>{older.disabled=true;try{const r=await call('?before='+run.first);if(!alive())return;const height=log.scrollHeight;render(r.messages,true);log.scrollTop+=log.scrollHeight-height;older.hidden=!r.has_older;}catch(e){status.textContent=e.message;}finally{older.disabled=false;}};
 form.onsubmit=async e=>{e.preventDefault();if(!input.value.trim())return;send.disabled=true;input.readOnly=true;try{await call('',{text:input.value});if(!alive())return;input.value='';await refresh();log.scrollTop=log.scrollHeight;input.focus();}catch(err){if(alive())status.textContent=err.message;}finally{send.disabled=false;input.readOnly=false;}};
 refresh(true);const timer=setInterval(()=>{if(!alive()){clearInterval(timer);return;}if(!document.hidden)refresh();},5000);
}
async function openStaff(){try{const data=await request('/agency/client-chats');modal('Chats com clientes','<div id="client-chat-host"></div>',true);const host=document.getElementById('client-chat-host');if(!data.clients.length){host.textContent='Nenhum cliente ativo na sua carteira.';return;}const label=el('label','Selecione o cliente');const select=el('select');select.setAttribute('aria-label','Cliente do atendimento');for(const c of data.clients){const o=el('option',c.name);o.value=c.id;select.append(o);}label.append(select);const area=el('div');host.append(label,area);const change=()=>{area.replaceChildren();mount(area,select.value);};select.onchange=change;change();}catch(e){toast(e.message);}}
function scan(){if(portal){const root=document.getElementById('portal-app');if(root?.querySelector('.mission-head')&&!root.querySelector('.client-chat'))mount(root);return;}if(typeof state==='undefined'||!state.user)return;const content=document.getElementById('content');if(content&&state.page==='clients'&&can('chats')&&!content.querySelector('#client-chat-open')){const b=el('button','Chats com clientes','btn secondary');b.id='client-chat-open';b.type='button';b.onclick=openStaff;content.prepend(b);}}
let queued=false;new MutationObserver(()=>{if(!queued){queued=true;queueMicrotask(()=>{queued=false;scan();});}}).observe(document.body,{childList:true,subtree:true});scan();
})();
