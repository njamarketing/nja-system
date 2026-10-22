/* Mobile conversations, birthday highlights and the phone calling experience. */
(()=>{
'use strict';
const mobile=()=>matchMedia('(max-width:760px)').matches;
let mobileConversation=location.hash.startsWith('#chats:'),lastBirthdayDay='';
function birthdayPeople(date=today()){
 return state.users.filter(u=>u.active!==0&&u.active!==false&&!u.deleted&&/^\d{4}-\d{2}-\d{2}$/.test(u.birthday||'')&&u.birthday.slice(5)===date.slice(5)).sort((a,b)=>a.name.localeCompare(b.name,'pt-BR'));
}
function birthdayRow(person,room){return `<button type="button" class="room birthday-room" ${room?`data-room="${esc(room.id)}"`:`data-birthday-user="${esc(person.id)}"`} aria-label="${esc(person.name)} faz aniversário hoje">${avatar(person)}<div class="grow"><strong><span aria-hidden="true">🎁</span> ${esc(person.name)}</strong><small><span class="birthday-pill">Faz aniversário hoje!</span></small></div><time>hoje</time></button>`;}
const regularRoomList=roomList;
roomList=function(){
 const birthdays=birthdayPeople().filter(u=>!chatFilter||u.name.toLocaleLowerCase('pt-BR').includes(chatFilter.toLocaleLowerCase('pt-BR')));
 if(showArchived||chatUnreadOnly||!birthdays.length)return regularRoomList();
 const pinned=new Set();
 const top=birthdays.map(u=>{const room=state.rooms.find(r=>r.kind==='direct'&&!r.archived&&r.members.includes(u.id)&&u.id!==state.user.id);if(room)pinned.add(room.id);return birthdayRow(u,room)}).join('');
 const rows=state.rooms.filter(r=>!r.archived&&!pinned.has(r.id)&&(!chatFilter||(roomName(r)+' '+(r.project||'')).toLocaleLowerCase('pt-BR').includes(chatFilter.toLocaleLowerCase('pt-BR')))).map(r=>`<button class="room ${r.id===state.room?'active':''}" data-room="${esc(r.id)}">${roomAvatar(r)}<div class="grow"><strong>${esc(roomName(r))}</strong><small>${esc(r.last?.text||r.description||'Comece a conversa')}</small></div><div class="room-meta">${r.last?`<small>${fmt(r.last.created,{hour:'2-digit',minute:'2-digit'})}</small>`:''}${r.unread?`<span class="unread">${r.unread}</span>`:''}</div></button>`).join('');
 return top+rows;
};
function decorateChat(){
 const layout=$('.chat-layout');document.body.classList.toggle('mobile-chat-open',!!layout&&mobile()&&mobileConversation&&state.page==='chats');
 if(!layout)return;
 layout.classList.toggle('mobile-conversation-open',mobileConversation);
 const header=$('.conversation-head',layout);
 if(header&&!$('#mobile-chat-back')){const b=document.createElement('button');b.type='button';b.id='mobile-chat-back';b.className='iconbtn';b.setAttribute('aria-label','Voltar às conversas');b.innerHTML='←';header.prepend(b);b.onclick=()=>{mobileConversation=false;history.replaceState(null,'','#chats');decorateChat();$('#roomlist .room')?.focus()};}
 const room=state.rooms.find(r=>r.id===state.room),people=birthdayPeople().filter(p=>room?.members.includes(p.id));
 let notice=$('.birthday-conversation-notice',layout);
 if(people.length&&header){if(!notice){notice=document.createElement('div');notice.className='birthday-conversation-notice';notice.setAttribute('role','status');header.after(notice)}const content=people.map(p=>`<span>${avatar(p)}<strong>${esc(p.name)}</strong><span class="birthday-pill">Faz aniversário hoje!</span></span>`).join('');if(notice.innerHTML!==content)notice.innerHTML=content;}else notice?.remove();
 fitViewport();
}
function fitViewport(){
 const v=window.visualViewport,height=v?.height||innerHeight,top=v?.offsetTop||0;
 document.documentElement.style.setProperty('--mobile-visible-height',height+'px');document.documentElement.style.setProperty('--mobile-visible-top',top+'px');
 document.body.classList.toggle('mobile-chat-typing',mobile()&&!!document.activeElement?.closest('.composer,.ninja-chat-form'));
}
const communicationsRender=renderContent;renderContent=function(){communicationsRender();decorateChat()};
document.addEventListener('click',e=>{const room=e.target.closest('[data-room]');if(room&&state.page==='chats'){mobileConversation=true;history.replaceState(null,'','#chats:'+encodeURIComponent(room.dataset.room));}},true);
document.addEventListener('click',async e=>{const b=e.target.closest('[data-birthday-user]');if(!b)return;b.disabled=true;try{if(b.dataset.birthdayUser===state.user.id){profilePanel(state.user.id);return}const existing=state.rooms.find(r=>r.kind==='direct'&&r.members.includes(b.dataset.birthdayUser));if(existing)showArchived=!!existing.archived;mobileConversation=true;await directChat(b.dataset.birthdayUser);decorateChat()}catch(err){toast(err.message)}finally{if(b.isConnected)b.disabled=false}});
window.addEventListener('hashchange',()=>{mobileConversation=location.hash.startsWith('#chats:');decorateChat()});
window.addEventListener('resize',decorateChat);window.visualViewport?.addEventListener('resize',fitViewport);window.visualViewport?.addEventListener('scroll',fitViewport);document.addEventListener('focusin',fitViewport);document.addEventListener('focusout',()=>requestAnimationFrame(fitViewport));
setInterval(()=>{const day=today();if(day!==lastBirthdayDay){lastBirthdayDay=day;if(state.page==='chats'&&$('#roomlist')){const list=$('#roomlist'),scroll=list.scrollTop;list.innerHTML=roomList();bindRoomList();list.scrollTop=scroll;decorateChat();}}},60000);

// A local synthesized telephone tone. No audio files or remote requests.
let audioContext=null,tone=null,toneTimer=null,toneLimit=null,toneOwner='',toneDirection='',oscillators=new Set();
function unlockCallAudio(){
 const Audio=window.AudioContext||window.webkitAudioContext;if(!Audio)return;
 try{audioContext||=new Audio();if(audioContext.state!=='running')audioContext.resume().then(()=>{if(tone&&!toneTimer)startCadence()}).catch(()=>{});}catch{}
}
function stopCallTone(owner){
 if(owner&&toneOwner!==owner)return;
 clearInterval(toneTimer);clearTimeout(toneLimit);toneTimer=null;toneLimit=null;tone=null;toneOwner='';toneDirection='';
 for(const oscillator of oscillators){try{oscillator.stop()}catch{}}oscillators.clear();
}
function ringBurst(){
 if(!tone||!audioContext||audioContext.state!=='running')return;
 const now=audioContext.currentTime;
 for(const delay of toneDirection==='incoming'?[0,.36]:[0]){
  const gain=audioContext.createGain();gain.connect(audioContext.destination);gain.gain.setValueAtTime(0,now+delay);gain.gain.linearRampToValueAtTime(.055,now+delay+.03);gain.gain.setValueAtTime(.055,now+delay+.24);gain.gain.linearRampToValueAtTime(0,now+delay+.3);
  let remaining=2;
  for(const frequency of toneDirection==='incoming'?[660,880]:[440,480]){const oscillator=audioContext.createOscillator();oscillator.type='sine';oscillator.frequency.value=frequency;oscillator.connect(gain);oscillators.add(oscillator);oscillator.onended=()=>{oscillators.delete(oscillator);oscillator.disconnect();if(--remaining===0)gain.disconnect()};oscillator.start(now+delay);oscillator.stop(now+delay+.32);}
 }
}
function startCadence(){if(!tone||toneTimer||audioContext?.state!=='running')return;ringBurst();toneTimer=setInterval(ringBurst,toneDirection==='incoming'?2600:3000)}
function playCallTone(owner,direction,id){
 const key=owner+':'+id+':'+direction;if(tone===key){startCadence();return}stopCallTone();tone=key;toneOwner=owner;toneDirection=direction;toneLimit=setTimeout(()=>stopCallTone(owner),65000);unlockCallAudio();startCadence();
}
document.addEventListener('pointerdown',unlockCallAudio,{capture:true});document.addEventListener('keydown',unlockCallAudio,{capture:true});
function offerSoundButton(panel){
 if(!panel||$('#call-enable-sound',panel)||audioContext?.state==='running')return;
 const button=document.createElement('button');button.type='button';button.id='call-enable-sound';button.className='call-enable-sound';button.textContent='Ativar som da chamada';button.onclick=()=>{unlockCallAudio();button.remove()};panel.append(button);
}
function callPortrait(person){return `<div class="phone-person"><div class="phone-avatar-halo">${avatar(person,'big')}</div><h2>${esc(person.name)}</h2><p>${currentCall?.mode==='video'?'Chamada de vídeo':'Chamada de voz'}</p><span class="phone-ring-symbol" aria-hidden="true">${ic('phone')}</span></div>`;}
const phoneDrawCall=drawCall;drawCall=function(status){phoneDrawCall(status);const panel=$('#call-panel');if(!panel||!currentCall)return;panel.classList.add('phone-call-screen');panel.setAttribute('role','dialog');panel.setAttribute('aria-modal','true');panel.setAttribute('aria-label','Chamada em andamento');panel.dataset.mode=currentCall.mode;panel.dataset.phase=currentCall.status==='ringing'?'ringing':'connecting';const person=user(currentCall.caller===state.user.id?currentCall.callee:currentCall.caller);const hero=document.createElement('div');hero.className='phone-person-host';hero.innerHTML=callPortrait(person);$('.call-videos',panel).before(hero);if(currentCall.status==='ringing'&&currentCall.caller===state.user.id)playCallTone('call','outgoing',currentCall.id);else stopCallTone('call');};
const phoneStatus=setCallStatus;setCallStatus=function(text){phoneStatus(text);const panel=$('#call-panel');if(panel&&currentCall)panel.dataset.phase=rtc?.connectionState==='connected'?'connected':currentCall.status==='ringing'?'ringing':'connecting';if(currentCall?.status!=='ringing'||rtc?.connectionState==='connected')stopCallTone('call');};
const phoneIncoming=incomingCall;incomingCall=function(call,servers){phoneIncoming(call,servers);const panel=$('#incoming-call');if(!panel||currentCall?.id!==call.id)return;panel.classList.add('phone-incoming-screen');panel.setAttribute('aria-modal','true');panel.dataset.phase='ringing';playCallTone('call','incoming',call.id);offerSoundButton(panel);const accept=$('#call-accept'),decline=$('#call-decline');for(const button of [accept,decline]){if(!button)continue;const original=button.onclick;button.onclick=async e=>{stopCallTone('call');return original(e)}}};
const phonePollCalls=pollCalls;pollCalls=async function(){try{return await phonePollCalls()}finally{if(!currentCall||currentCall.status!=='ringing')stopCallTone('call')}};
const phoneCleanup=cleanupCall;cleanupCall=function(){stopCallTone('call');phoneCleanup()};

function meetingPeopleHTML(m){const labels={joined:'Na chamada',invited:'Chamando…',declined:'Recusou',missed:'Não atendeu',left:'Saiu',removed:'Removido'};return m.members.map(p=>`<article class="phone-group-person ${p.status==='invited'?'is-ringing':''}">${avatar({...user(p.user_id),...p,id:p.user_id},'big')}<strong>${esc(p.name)}</strong><small>${labels[p.status]||'Indisponível'}</small></article>`).join('');}
const phoneMeetingTile=meetingTile;meetingTile=function(id,name,local=false){return phoneMeetingTile(id,name,local).replace('<video ',`<div class="meeting-avatar">${avatar({...user(id),name},'big')}</div><video `)};
function updateMeetingVideo(id,stream){const tile=$('[data-meeting-tile="'+id+'"]');tile?.classList.toggle('has-video',!!stream?.getVideoTracks().some(t=>t.enabled&&t.readyState!=='ended'&&!t.muted));}
const phoneMeetingPeer=makeMeetingPeer;makeMeetingPeer=async function(id){const entry=await phoneMeetingPeer(id);if(!entry.phoneDecorated){entry.phoneDecorated=true;const original=entry.pc.ontrack;entry.pc.ontrack=e=>{original?.(e);updateMeetingVideo(id,entry.stream);for(const event of ['mute','unmute','ended'])e.track.addEventListener(event,()=>updateMeetingVideo(id,entry.stream))};}return entry;};
const answeredMeetings=new Set();
const phoneRoster=updateMeetingRoster;updateMeetingRoster=function(){phoneRoster();if(!currentMeeting)return;const panel=$('#meeting-panel');if(!panel)return;panel.classList.add('phone-meeting-screen');panel.classList.toggle('audio-meeting',currentMeeting.mode==='audio');panel.setAttribute('role','dialog');panel.setAttribute('aria-modal','true');panel.setAttribute('aria-label','Chamada em grupo');let portraits=$('#phone-group-portraits');if(!portraits){portraits=document.createElement('div');portraits.id='phone-group-portraits';portraits.className='phone-group-portraits';$('#meeting-grid').before(portraits)}const content=meetingPeopleHTML(currentMeeting);if(portraits.innerHTML!==content)portraits.innerHTML=content;const alone=currentMeeting.members.filter(p=>p.status==='joined').length===1;if(!alone)answeredMeetings.add(currentMeeting.id);panel.classList.toggle('group-ringing',alone);if(currentMeeting.host===state.user.id&&alone&&!answeredMeetings.has(currentMeeting.id)&&currentMeeting.members.some(p=>p.status==='invited'))playCallTone('meeting','outgoing',currentMeeting.id);else stopCallTone('meeting');};
const phoneRosterVideos=updateMeetingRoster;updateMeetingRoster=function(){phoneRosterVideos();if(!currentMeeting)return;updateMeetingVideo(state.user.id,meetingStream);for(const [id,entry] of meetingPeers)updateMeetingVideo(id,entry.stream)};
const phoneMeetingInvite=showMeetingInvite;showMeetingInvite=function(m,servers){phoneMeetingInvite(m,servers);const panel=$('#meeting-incoming');if(!panel||meetingIncoming?.id!==m.id)return;panel.classList.add('phone-incoming-screen','phone-group-incoming');panel.setAttribute('aria-modal','true');if(!$('.phone-group-portraits',panel)){const portraits=document.createElement('div');portraits.className='phone-group-portraits';portraits.innerHTML=meetingPeopleHTML(m);$('.inline-actions',panel).before(portraits)}playCallTone('meeting','incoming',m.id);offerSoundButton(panel);for(const id of ['meeting-accept','meeting-decline']){const button=$('#'+id);if(!button||button.dataset.phoneBound)continue;button.dataset.phoneBound='true';const original=button.onclick;button.onclick=async e=>{stopCallTone('meeting');return original(e)}}};
const phonePollMeetings=pollMeetings;pollMeetings=async function(){try{return await phonePollMeetings()}finally{if(!currentMeeting&&!meetingIncoming)stopCallTone('meeting')}};
const phoneCleanupMeeting=cleanupMeeting;cleanupMeeting=function(){stopCallTone('meeting');if(currentMeeting)answeredMeetings.delete(currentMeeting.id);phoneCleanupMeeting()};
const communicationsLogout=logoutLocal;logoutLocal=function(){stopCallTone();mobileConversation=false;document.body.classList.remove('mobile-chat-open','mobile-chat-typing');communicationsLogout()};window.addEventListener('pagehide',()=>stopCallTone());
// Expose the sound lifecycle for deterministic regression checks.
window.NJACallAudio={stop:stopCallTone,play:playCallTone,unlock:unlockCallAudio};
if(state.user&&state.page==='chats'&&$('#roomlist')){$('#roomlist').innerHTML=roomList();bindRoomList()}
decorateChat();fitViewport();
})();
