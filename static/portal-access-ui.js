'use strict';
(()=>{
const original=window.agencySections?.approvals;
if(!original)return;

async function copyValue(input,button){
 try{await navigator.clipboard.writeText(input.value)}catch{input.select();document.execCommand('copy')}
 button.textContent='Copiado ✓';setTimeout(()=>button.textContent='Copiar link',1800);toast('Link copiado.');
}
function linkModal(result,title='Link de acesso pronto'){
 modal(title,`<div class="portal-link-result"><span>✓</span><div><strong>Convite seguro criado</strong><small>Válido por 48 horas e para um único uso.</small></div></div><label class="field">Código simples do cliente<input readonly value="${esc(result.client_code||'')}" aria-label="Código do cliente"></label><label class="field">Link curto<input id="portal-short-link" readonly value="${esc(result.url)}" aria-label="Link curto de acesso"></label><div class="portal-link-actions"><button type="button" class="btn lime" id="portal-copy-link">Copiar link</button><a class="btn secondary" href="${esc(result.url)}" target="_blank" rel="noopener">Testar acesso ↗</a></div><p class="mission-muted">Compartilhe este endereço somente com a pessoa convidada.</p>`);
 const input=$('#portal-short-link'),button=$('#portal-copy-link');button.onclick=()=>copyValue(input,button);
}
function inviteForm(){
 agencyForm('Convidar contato do cliente',selectField('Cliente','client_id',clientOptions(),state.clients[0]?.id)+field('Nome','name','text','',true)+field('E-mail','email','email','',true)+'<label class="portal-approval-check"><input type="checkbox" name="can_approve"> Pode aprovar materiais</label><div class="portal-invite-note"><span>↗</span><p>O sistema cria um código parecido com o nome do cliente e um link curto para copiar. O convite vale por 48 horas.</p></div>',async(d,form)=>{const result=await request('/agency/portal/invite',{method:'POST',data:{...d,can_approve:new FormData(form).has('can_approve')}});setTimeout(()=>linkModal(result,'Convite criado'),100);return result;});
}
function accessPanel(account){
 const client=state.clients.find(item=>item.id===account.client_id);
 modal('Gerenciar acesso do cliente',`<div class="portal-access-person"><span>${esc((account.name||'C').split(/\s+/).slice(0,2).map(part=>part[0]).join('').toUpperCase())}</span><div><strong>${esc(account.name)}</strong><small>${esc(account.email)} · ${esc(client?.name||'Cliente')}</small></div><em class="${account.active?'active':''}">${account.active?'Ativo':'Desativado'}</em></div><div class="portal-client-code"><small>CÓDIGO DO CLIENTE</small><strong>${esc(account.client_code||client?.portal_code||client?.name||'')}</strong><p>Este é o código simples usado na tela de entrada do portal.</p></div><div class="portal-access-actions"><button type="button" id="portal-new-link"><i>↗</i><span><strong>Gerar novo link</strong><small>Revoga sessões anteriores e cria um convite curto.</small></span><b>›</b></button><button type="button" id="portal-email-link"><i>✉</i><span><strong>Enviar link por e-mail</strong><small>Envia um novo acesso diretamente ao contato.</small></span><b>›</b></button><button type="button" id="portal-password-toggle"><i>⌁</i><span><strong>Definir uma nova senha</strong><small>Redefina a senha agora e encerre as sessões abertas.</small></span><b>›</b></button></div><form id="portal-password-form" hidden><div class="portal-password-fields">${field('Nova senha','password','password','',true)}${field('Confirmar nova senha','confirmation','password','',true)}</div><button class="btn" type="submit">Salvar nova senha</button></form><button type="button" class="textlink portal-revoke" id="portal-toggle-access">${account.active?'Revogar acesso':'Reativar acesso'}</button>`,true);
 $('#portal-new-link').onclick=async event=>{event.currentTarget.disabled=true;try{linkModal(await request('/agency/portal/accounts/'+account.id+'/reset',{method:'POST',data:{mode:'link'}}))}catch(error){toast(error.message);event.currentTarget.disabled=false}};
 $('#portal-email-link').onclick=async event=>{event.currentTarget.disabled=true;try{await request('/agency/portal/accounts/'+account.id+'/reset',{method:'POST',data:{mode:'email'}});toast('Novo link enviado para '+account.email+'.');closeModal()}catch(error){toast(error.message);event.currentTarget.disabled=false}};
 $('#portal-password-toggle').onclick=()=>{const form=$('#portal-password-form');form.hidden=!form.hidden;if(!form.hidden)form.elements.password.focus()};
 $('#portal-password-form').onsubmit=event=>{event.preventDefault();formSubmit(event.currentTarget,()=>request('/agency/portal/accounts/'+account.id+'/reset',{method:'POST',data:{mode:'password',...Object.fromEntries(new FormData(event.currentTarget))}}),()=>{closeModal();toast('Senha do cliente redefinida. As sessões anteriores foram encerradas.')})};
 $('#portal-toggle-access').onclick=async event=>{event.currentTarget.disabled=true;try{await request('/agency/portal/accounts/'+account.id,{method:'PATCH',data:{active:!account.active}});closeModal();await load();route();toast(account.active?'Acesso revogado.':'Acesso reativado.')}catch(error){toast(error.message);event.currentTarget.disabled=false}};
}
window.agencySections.approvals=data=>{
 original(data);
 const invite=$('#portal-invite');if(invite){const fresh=invite.cloneNode(true);invite.replaceWith(fresh);fresh.onclick=inviteForm}
 $$('[data-portal-account]').forEach(button=>{const account=data.accounts.find(item=>item.id===button.dataset.portalAccount);button.textContent='Gerenciar acesso';button.className='btn secondary small';button.onclick=()=>accessPanel(account)});
};
})();
