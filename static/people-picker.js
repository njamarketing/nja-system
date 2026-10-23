'use strict';

const njaPeopleFieldNames=new Set(['members','managers','send_members','invite_members']);
document.addEventListener('pointerdown',event=>{$$('.people-picker').forEach(picker=>{if(picker.contains(event.target))return;const popover=$('.people-popover',picker),trigger=$('.people-trigger',picker);if(popover)popover.hidden=true;if(trigger)trigger.setAttribute('aria-expanded','false')})});

function njaPersonVisual(person){
 const picture=person?.photo?`<img src="/files/${esc(person.photo)}" alt="">`:`<span>${esc(initials(person?.name||'Pessoa'))}</span>`;
 return `<span class="people-photo">${picture}</span>`;
}

function njaEnhancePeopleSelect(select){
 if(select.dataset.peoplePicker||!select.multiple||!njaPeopleFieldNames.has(select.name))return;
 select.dataset.peoplePicker='true';select.tabIndex=-1;select.classList.add('people-native-select');
 const options=[...select.options],people=new Map(state.users.map(person=>[String(person.id),person]));
 const originalField=select.parentElement,originalHint=originalField?.querySelector('.hint'),labelText=[...(originalField?.childNodes||[])].find(node=>node.nodeType===Node.TEXT_NODE)?.textContent.trim()||'Pessoas';
 const shell=document.createElement('div');shell.className='people-picker';
 shell.innerHTML=`<button type="button" class="people-trigger" aria-expanded="false"><span class="people-trigger-content"></span><span class="people-chevron">⌄</span></button><section class="people-popover" hidden><label class="people-search"><span>⌕</span><input type="search" placeholder="Buscar por nome, cargo ou área" autocomplete="off"></label><div class="people-results" role="listbox" aria-multiselectable="true"></div><p class="people-empty" hidden>Nenhuma pessoa encontrada.</p></section>`;
 if(originalField?.tagName==='LABEL'){
  const field=document.createElement('div');field.className=originalField.className+' people-field';field.innerHTML=`<span class="people-label">${esc(labelText)}</span>`;originalField.before(field);field.append(shell,select);if(originalHint)field.append(originalHint);originalField.remove();
 }else select.before(shell);
 const trigger=$('.people-trigger',shell),content=$('.people-trigger-content',shell),popover=$('.people-popover',shell),search=$('input',shell),results=$('.people-results',shell),empty=$('.people-empty',shell);
 let maximum=Infinity;
 const selected=()=>options.filter(option=>option.selected);
 const personFor=option=>people.get(String(option.value))||{id:option.value,name:option.textContent};
 const draw=()=>{
  const chosen=selected();content.innerHTML=chosen.length?`<span class="people-stack">${chosen.slice(0,4).map(option=>njaPersonVisual(personFor(option))).join('')}</span><strong>${chosen.length===1?esc(personFor(chosen[0]).name):chosen.length+' pessoas selecionadas'}</strong>`:'<span class="people-placeholder">Toque para escolher pessoas</span>';
  const needle=search.value.trim().toLocaleLowerCase('pt-BR');let visible=0;
  results.innerHTML=options.map(option=>{const person=personFor(option),haystack=[person.name,person.title,person.area].join(' ').toLocaleLowerCase('pt-BR');if(needle&&!haystack.includes(needle))return'';visible++;return `<button type="button" class="people-option ${option.selected?'selected':''}" data-person-value="${esc(option.value)}" role="option" aria-selected="${option.selected?'true':'false'}">${njaPersonVisual(person)}<span><strong>${esc(person.name)}</strong><small>${esc([person.title,person.area].filter(Boolean).join(' · ')||'Integrante da equipe')}</small></span><i>${option.selected?'✓':'＋'}</i></button>`}).join('');empty.hidden=visible>0;
  $$('[data-person-value]',results).forEach(button=>button.onclick=()=>{const option=options.find(item=>item.value===button.dataset.personValue);if(!option)return;if(!option.selected&&selected().length>=maximum){for(const item of selected())item.selected=false;}option.selected=!option.selected;select.dispatchEvent(new Event('change',{bubbles:true}));draw();if(maximum===1){popover.hidden=true;trigger.setAttribute('aria-expanded','false')}});
 };
 const open=value=>{popover.hidden=!value;trigger.setAttribute('aria-expanded',String(value));if(value){search.value='';draw();search.focus()}};
 trigger.onclick=()=>open(popover.hidden);search.oninput=draw;
 select.njaPeoplePicker={setMaximum(value){maximum=value||Infinity;if(selected().length>maximum)selected().slice(maximum).forEach(option=>option.selected=false);draw()},draw};
 shell.addEventListener('keydown',event=>{if(event.key==='Escape')open(false)});
 const hint=select.parentElement?.querySelector('.hint');if(hint)hint.textContent='Busque pelo nome e toque nas pessoas para selecionar.';
 draw();
}

function njaEnhancePeople(root=document){$$('select[multiple]',root).forEach(njaEnhancePeopleSelect)}

const njaPeopleModal=modal;
modal=function(...args){const result=njaPeopleModal(...args);njaEnhancePeople($('#modal-root'));return result};

function njaExternalFields(room){
 const linked=room?.client_id&&state.clients?.find(client=>client.id===room.client_id),clients=(state.clients||[]).filter(client=>client.active!==0);
 return `<div class="external-invite-intro"><span>↗</span><div><strong>Convidar pessoa externa</strong><small>Ela receberá um link para entrar no Portal do Cliente e participar deste grupo.</small></div></div>${linked?`<div class="external-linked-client">Cliente vinculado: <strong>${esc(linked.name)}</strong><input type="hidden" name="client_id" value="${esc(linked.id)}"></div>`:`<label class="field">Vincular a<select name="client_mode"><option value="existing" ${clients.length?'':'disabled'}>Cliente já cadastrado</option><option value="new" ${clients.length?'':'selected'}>Novo cliente · cadastro inicial</option></select></label><label class="field external-existing-client">Cliente<select name="client_id">${clients.map(client=>`<option value="${esc(client.id)}">${esc(client.name)}</option>`).join('')}</select></label><div class="external-new-client" hidden>${field('Nome do cliente ou empresa','client_name','text','')}${field('Plano ou serviço inicial','product','text','')}</div>`}${field('Nome da pessoa convidada','name','text','',true)}${field('E-mail para acesso','email','email','',true)}<label class="external-approve"><input type="checkbox" name="can_approve" checked> Pode aprovar materiais no portal</label><p class="tiny muted">O link expira em 48 horas. A pessoa cria a própria senha antes de acessar a conversa.</p>`;
}

function njaBindExternalMode(form){
 const mode=form.elements.client_mode;if(!mode)return;
 const existing=$('.external-existing-client',form),fresh=$('.external-new-client',form);
 const update=()=>{const isNew=mode.value==='new';existing.hidden=isNew;fresh.hidden=!isNew;const name=form.elements.client_name;if(name)name.required=isNew};mode.onchange=update;update();
}

function njaExternalPayload(form){
 const data=Object.fromEntries(new FormData(form));
 return {name:data.name,email:data.email,client_id:data.client_mode==='new'?'':data.client_id||'',client_name:data.client_name||'',product:data.product||'',can_approve:new FormData(form).has('can_approve')};
}

function njaInvitationResult(invitation,roomId){
 modal('Convite pronto',`<div class="invite-success"><span>✓</span><div><strong>${invitation.client_created?'Cliente e acesso criados':'Acesso ao portal preparado'}</strong><p>${esc(invitation.client_name)} já está vinculado a esta conversa.</p></div></div><label class="field">Link de acesso<input id="external-invite-url" readonly value="${esc(invitation.url)}"></label><div class="invite-actions"><button type="button" class="btn lime" id="copy-external-invite">Copiar link</button><a class="btn secondary" href="${esc(invitation.url)}" target="_blank" rel="noopener">Testar acesso ↗</a><button type="button" class="textlink" id="finish-external-invite">Ir para a conversa</button></div><p class="tiny muted">Envie este link somente à pessoa convidada. Ele poderá ser usado uma vez, durante 48 horas.</p>`);
 $('#copy-external-invite').onclick=async()=>{const input=$('#external-invite-url');try{await navigator.clipboard.writeText(input.value)}catch{input.select();document.execCommand('copy')}toast('Link copiado.');};
 $('#finish-external-invite').onclick=()=>{closeModal();if(roomId){state.room=roomId;location.hash='chats:'+roomId;route()}};
}

function njaOpenExternalInvite(room){
 modal('Convidar cliente para o grupo',`<form id="external-invite-form">${njaExternalFields(room)}${footer('Criar acesso e gerar link')}</form>`,true);
 const form=$('#external-invite-form');njaBindExternalMode(form);$('[data-cancel]',form).onclick=closeModal;
 form.onsubmit=event=>{event.preventDefault();formSubmit(form,()=>request('/rooms/'+room.id+'/external-invite',{method:'POST',data:njaExternalPayload(form)}),async invitation=>{await load();njaInvitationResult(invitation,room.id)})};
}

function njaNewRoomForm(){
 const people=state.users.filter(person=>person.active&&person.id!==state.user.id),externalAllowed=can('portal_manage')&&can('client_manage');
 modal('Nova conversa',`<form id="modalform" class="modern-room-form">${selectField('Tipo de conversa','kind',can('chat_manage')?[['direct','Conversa individual'],['group','Grupo']]:[['direct','Conversa individual']],'direct')}<div id="new-room-group-fields" hidden>${field('Nome do grupo','name','text','')}${field('Cliente / projeto','project','text','')}${textarea('Descrição do grupo','description','')}</div>${selectField('Pessoas da conversa','members',people.map(person=>[person.id,person.name]),[],true)}<p class="people-guidance">Você já participa automaticamente. Busque e toque nas fotos para montar a conversa.</p>${externalAllowed?`<button type="button" class="external-invite-button" id="new-room-external" hidden><span>＋</span><div><strong>Convidar uma pessoa de fora</strong><small>Criar acesso de cliente por link</small></div><b>›</b></button><section id="new-room-external-panel" class="external-invite-panel" hidden>${njaExternalFields(null)}</section>`:''}${footer('Criar conversa')}</form>`,true);
 const form=$('#modalform'),kind=form.elements.kind,group=$('#new-room-group-fields'),roomNameInput=$('[name=name]',group),memberSelect=form.elements.members,externalButton=$('#new-room-external'),externalPanel=$('#new-room-external-panel');
 const enableExternal=enabled=>{if(!externalPanel)return;$$('input,select',externalPanel).forEach(control=>control.disabled=!enabled);if(enabled)njaBindExternalMode(form)};
 const syncKind=()=>{const isGroup=kind.value==='group';group.hidden=!isGroup;roomNameInput.required=isGroup;if(externalButton)externalButton.hidden=!isGroup;if(!isGroup&&externalPanel){externalPanel.hidden=true;externalButton.classList.remove('active');enableExternal(false)}memberSelect.njaPeoplePicker?.setMaximum(isGroup?Infinity:1)};kind.onchange=syncKind;enableExternal(false);syncKind();
 if(externalButton){externalButton.onclick=()=>{externalPanel.hidden=!externalPanel.hidden;externalButton.classList.toggle('active',!externalPanel.hidden);enableExternal(!externalPanel.hidden)}}
 $('[data-cancel]',form).onclick=closeModal;
 form.onsubmit=event=>{event.preventDefault();formSubmit(form,async()=>{const fd=new FormData(form),data=Object.fromEntries(fd);data.name=roomNameInput.value;data.members=fd.getAll('members');if(externalPanel&&!externalPanel.hidden)data.external=njaExternalPayload(form);return request('/rooms',{method:'POST',data})},async result=>{closeModal();await load();state.room=result.id;location.hash='chats:'+result.id;route();if(result.invitation)njaInvitationResult(result.invitation,result.id)})};
}

const njaPreviousRoomForm=roomForm;
roomForm=function(room=null){
 if(!room)return njaNewRoomForm();
 njaPreviousRoomForm(room);njaEnhancePeople($('#modal-root'));
 if(room.kind==='group'&&can('portal_manage')&&can('client_manage')){
  const form=$('#modalform'),foot=$('.formfoot',form);if(form&&foot&&!$('#room-external-invite',form)){const button=document.createElement('button');button.type='button';button.id='room-external-invite';button.className='external-invite-button';button.innerHTML='<span>＋</span><div><strong>Convidar pessoa externa</strong><small>Gerar link do Portal do Cliente</small></div><b>›</b>';foot.before(button);button.onclick=()=>njaOpenExternalInvite(room)}
 }
};
