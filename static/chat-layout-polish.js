'use strict';
(()=>{
function groupFlags(keys){return keys.map((key,index)=>({start:index===0||keys[index-1]!==key,end:index===keys.length-1||keys[index+1]!==key}));}
function actorKey(message){
 if(message.classList.contains('mine'))return 'self';
 const sender=message.querySelector('.sender'),profile=sender?.dataset.profile;
 return profile?'user:'+profile:'external:'+(sender?.textContent||'cliente').trim().toLocaleLowerCase();
}
function avatarMarkup(message,rid){
 const sender=message.querySelector('.sender'),id=sender?.dataset.profile,name=(sender?.textContent||'Cliente').replace(/\s*·\s*Cliente\s*$/,'').trim()||'Cliente';
 if(id){const person=user(id);return `<button type="button" class="message-person-photo profile-link" data-profile="${esc(id)}" aria-label="Abrir perfil de ${esc(person.name)}">${avatar(person)}</button>`;}
 const room=state.rooms.find(item=>item.id===rid),photo=room?.client_id&&room.photo?`<img class="avatar" src="/files/${esc(room.photo)}" alt="Foto de ${esc(name)}">`:`<span class="avatar">${esc(initials(name))}</span>`;
 return `<span class="message-person-photo external" aria-label="${esc(name)}">${photo}</span>`;
}
function decorateMessageGroups(root,rid){
 if(!root)return;const messages=$$('.message',root).filter(message=>!message.classList.contains('message-pending'));if(!messages.length)return;
 const flags=groupFlags(messages.map(actorKey));
 messages.forEach((message,index)=>{
  message.querySelector('.message-person-photo')?.remove();message.classList.remove('chat-group-start','chat-group-end','chat-group-continuation','chat-incoming');
  if(flags[index].start)message.classList.add('chat-group-start');else message.classList.add('chat-group-continuation');
  if(flags[index].end)message.classList.add('chat-group-end');
  if(message.classList.contains('mine'))return;
  message.classList.add('chat-incoming');
  if(!flags[index].end)return;
  message.insertAdjacentHTML('afterbegin',avatarMarkup(message,rid));
  const place=()=>{const photo=message.querySelector('.message-person-photo'),bubble=message.querySelector('.bubble');if(photo&&bubble)photo.style.top=Math.max(0,bubble.offsetTop+bubble.offsetHeight-photo.offsetHeight)+'px'};
  requestAnimationFrame(place);message.querySelectorAll('img,video').forEach(media=>media.addEventListener('load',place,{once:true}));
 });
 bindProfileLinks(root);
}
const previousRefresh=refreshMessages;refreshMessages=async function(force=false){const rid=state.room;await previousRefresh(force);if(state.page==='chats'&&state.room===rid)decorateMessageGroups($('#messages'),rid);};
if(typeof refreshFloating==='function'){
 const previousFloatingRefresh=refreshFloating;refreshFloating=async function(force=false,onlyId=null){await previousFloatingRefresh(force,onlyId);$$('[data-float-messages]').forEach(root=>decorateMessageGroups(root,root.dataset.floatMessages));};
}
const previousBind=bindContent;bindContent=function(){
 previousBind();
 $$('[data-notice]').forEach(button=>button.onclick=async()=>{const notice=state.notifications.find(item=>item.id===button.dataset.notice);if(!notice)return;button.disabled=true;try{if(!notice.seen)await request('/notifications/read',{method:'POST',data:{id:notice.id}});notice.seen=1;button.classList.remove('unseen');button.setAttribute('aria-label','Notificação lida: '+notice.title);updateBadge();const destination='#'+notice.link;if(location.hash===destination)route();else location.hash=notice.link;}catch(error){toast(error.message);button.disabled=false}});
};
window.NJAChatPolish={groupFlags,decorateMessageGroups};
})();
