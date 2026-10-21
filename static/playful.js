'use strict';
/* Local encouragement only. This timer never writes work logs or task hours. */
class NinjaFocusClock {
  constructor(saved={}) {
    this.ms=Math.min(86400000,Math.max(0,Number(saved.ms)||0));
    this.announced=Math.max(0,Number(saved.announced)||0);
  }
  advance(delta,active) {
    if(active)this.ms+=Math.max(0,Math.min(5000,delta));
    const hour=Math.floor(this.ms/3600000);
    if(hour>this.announced){this.announced=hour;return hour}
    return 0;
  }
  snapshot(){return {ms:this.ms,announced:this.announced}}
}
const ninjaHourMessage=hour=>[
  '1 hora de produtividade. Parabéns! Seu foco faz a diferença.',
  '2 horas de produtividade! Suas ideias estão ganhando vida.',
  '3 horas de produtividade! Cada entrega leva a NJA mais longe.',
  '4 horas de produtividade! Você merece uma pausa para respirar.',
  '5 horas de produtividade! Talento e dedicação em movimento.',
  '6 horas de produtividade! Obrigado por construir com a NJA.',
  '7 horas de produtividade! Que tal se alongar e beber uma água?',
  '8 horas de produtividade! Celebre o que você construiu hoje.'
][hour-1]||`${hour} horas de produtividade! Mais um marco na sua jornada. Cuide também das suas pausas.`;

(() => {
  const originalEventForm=eventForm;
  eventForm=function(...args){
    originalEventForm(...args);
    document.querySelector('#modal-root .modal')?.classList.add('event-popup');
    document.querySelector('#modalform input[name=title]')?.focus();
  };
  document.addEventListener('click',e=>{
    const cell=e.target.closest('[data-open-day]');
    if(cell&&!e.target.closest('button,a,input,select,textarea'))eventForm(cell.dataset.openDay);
  });
  document.addEventListener('keydown',e=>{
    if((e.key==='Enter'||e.key===' ')&&e.target.matches('[data-open-day]')){
      e.preventDefault();eventForm(e.target.dataset.openDay);
    }
  });
  const read=(key,fallback={})=>{try{return JSON.parse(localStorage.getItem(key))||fallback}catch{return fallback}};
  const write=(key,value)=>{try{localStorage.setItem(key,JSON.stringify(value))}catch{/* private browsing: session-only counter */}};
  const dayKey=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  let root=null,restore=null,identity='',key='',clock=new NinjaFocusClock(),last=Date.now(),interaction=Date.now(),paused=false,prefs={};
  let nextAction=0,step=0,x=0,lastRoute='',epoch=0,motion=null;
  const rest=()=>Date.now()+8000+Math.random()*6000;
  let panelTab='',panelRequest=0,assistantRoom='',chatBusy=false,nextPoll=0,pollBusy=false,summary=null,weatherData=null;
  let notices=[],noticeUntil=0,currentNotice=null,voiceArmed=false;
  const reduce=matchMedia('(prefers-reduced-motion: reduce)');
  const active=()=>!paused&&!document.hidden&&document.hasFocus()&&Date.now()-interaction<300000;
  const safe=()=>root&&identity===state.user?.id;
  const hourTime=value=>new Intl.DateTimeFormat('pt-BR',{timeZone:'America/Sao_Paulo',hour:'2-digit',minute:'2-digit'}).format(new Date(value));
  function stopWalk(){motion?.stop()}
  function mode(name,duration=0){
    if(!root)return;
    root.dataset.mode=name;
    motion?.play(name,{duration:duration||window.NinjaMotion.durations[name]});
  }
  function bounds(){const width=root?.getBoundingClientRect().width||288;return {left:innerWidth>900?252:12,right:Math.max(12,innerWidth-width-18)}}
  function place(next){const b=bounds();x=Math.max(Math.min(b.left,b.right),Math.min(next,b.right));root.style.left=x+'px';root.style.right='auto';root.classList.toggle('dock-left',x<innerWidth/2-140)}
  function travelAcross(action='walk'){
    if(!safe()||paused||prefs.hidden||prefs.compact||panelTab||noticeUntil>Date.now()||document.hidden||reduce.matches)return;
    const b=bounds(),target=Math.abs(x-b.right)<20?Math.min(b.left,b.right):b.right;
    const distance=Math.abs(target-x);
    // On narrow screens use the available space; no jumps beyond the viewport.
    motion.play(action,{target,duration:action==='walk'?Math.max(900,distance/115*1000):window.NinjaMotion.durations[action]});
    nextAction=rest();
  }
  function walkAcross(){travelAcross('walk')}
  function speak(text){
    if(!prefs.voice||!voiceArmed||!('speechSynthesis' in window)||document.hidden||!document.hasFocus())return;
    speechSynthesis.cancel();const utterance=new SpeechSynthesisUtterance(text.slice(0,700));utterance.lang='pt-BR';utterance.rate=1;
    const voice=speechSynthesis.getVoices().find(v=>v.lang==='pt-BR');if(voice)utterance.voice=voice;
    speechSynthesis.speak(utterance);
  }
  function announce(text,kind='info',eventId=null){
    if(!safe())return;
    if(kind==='summary')notices=notices.filter(n=>n.kind!=='summary');
    notices.push({text,kind,eventId,expires:kind==='alert'?Date.now()+60000:Infinity});if(notices.length>10)notices.shift();showNotice();
  }
  function showNotice(){
    if(!safe()||noticeUntil>Date.now()||!notices.length||document.hidden||panelTab)return;
    notices=notices.filter(n=>n.expires>Date.now());if(!notices.length)return;
    currentNotice=notices.shift();const sign=root.querySelector('.ninja-sign');
    sign.querySelector('[data-ninja-message]').textContent=currentNotice.text;
    sign.querySelector('[data-ninja=event]').hidden=!currentNotice.eventId;
    sign.hidden=false;noticeUntil=Date.now()+18000;
    mode(currentNotice.kind==='hour'?'celebrate':currentNotice.kind==='alert'?'salute':'wave',2200);
    speak(currentNotice.text);
  }
  function dismissNotice(){if(!root)return;root.querySelector('.ninja-sign').hidden=true;noticeUntil=0;currentNotice=null}
  function savePrefs(){write('nja-companion-prefs:'+identity,prefs)}
  function updateVisibility(){root.hidden=!!prefs.hidden;restore.hidden=!prefs.hidden;root.classList.toggle('compact',!!prefs.compact);if(prefs.hidden||prefs.compact)mode('idle');place(Math.min(x,bounds().right))}
  function updateControls(){
    const button=root.querySelector('[data-ninja=pause]');button.textContent=paused?'▶':'Ⅱ';button.setAttribute('aria-label',paused?'Retomar contador de uso':'Pausar contador de uso');button.title=button.getAttribute('aria-label');
    root.querySelector('[data-ninja=motion]').setAttribute('aria-pressed',String(!!prefs.compact));
    const voice=root.querySelector('[data-ninja=voice]');voice.setAttribute('aria-pressed',String(!!prefs.voice&&voiceArmed));voice.title=prefs.voice&&voiceArmed?'Desativar voz':'Ativar voz do ninja';voice.setAttribute('aria-label',voice.title);voice.textContent=prefs.voice&&voiceArmed?'◖))':'◖';voice.hidden=!('speechSynthesis' in window);
  }
  function mount(){
    root=document.createElement('aside');root.className='ninja-companion ninja-v17 ninja-v19';root.setAttribute('aria-label','Assistente Ninja NJA');
    root.innerHTML=`<section class="ninja-talk" role="dialog" aria-label="Balão do Ninja" hidden><header><img src="/nja-systems-icon.png" alt=""><div><strong>Ninja</strong><small>Seu parceiro na NJA</small></div><button data-ninja="close" aria-label="Fechar balão">×</button></header><nav aria-label="Recursos do Ninja"><button data-ninja="today">Meu dia</button><button data-ninja="weather">Clima</button><button data-ninja="chat">Conversar com IA</button></nav><div class="ninja-talk-body"></div></section>
    <div class="ninja-stage"><div class="ninja-sign" role="status" aria-live="polite" hidden><button data-ninja="dismiss" aria-label="Dispensar aviso">×</button><span data-ninja-message></span><button data-ninja="event" class="ninja-event-link" hidden>Ver compromisso →</button></div><button class="ninja-character" data-ninja="chat" aria-label="Conversar com o Ninja IA"><span class="ninja-sprite" aria-hidden="true"></span></button></div>
    <div class="ninja-controls"><button class="ninja-chat-trigger" data-ninja="chat" title="Conversar com o Ninja IA" aria-label="Abrir chat com Ninja IA">${ic('chats')}</button><span class="ninja-time"><span data-ninja-clock>00:00</span><small data-ninja-status>Uso ativo hoje</small></span><button data-ninja="actions" title="Escolher animação" aria-label="Escolher animação do Ninja">✦</button><button data-ninja="voice" aria-label="Ativar voz do ninja">◖</button><button data-ninja="pause" title="Pausar contador de uso" aria-label="Pausar contador de uso">Ⅱ</button><button data-ninja="motion" title="Recolher personagem" aria-label="Recolher personagem">◇</button><button data-ninja="hide" title="Ocultar ninja" aria-label="Ocultar ninja">×</button></div><div class="ninja-progress"><span></span></div>`;
    restore=document.createElement('button');restore.className='ninja-reopen';restore.title='Mostrar mini ninja';restore.setAttribute('aria-label','Mostrar mini ninja');restore.innerHTML='<img src="/nja-systems-icon.png" alt="">';restore.hidden=true;
    document.body.append(root,restore);place(bounds().right);
    motion=new window.NinjaMotion.Player(root,{position:()=>x,place,quiet:()=>paused||reduce.matches||document.hidden||!!prefs.hidden||!!prefs.compact,onfinish:()=>{if(safe()){mode('idle');nextAction=rest()}}});
    restore.onclick=()=>{prefs.hidden=false;savePrefs();updateVisibility();mode('wave',1800);showNotice()};
    root.addEventListener('click',e=>{
      const action=e.target.closest('[data-ninja]')?.dataset.ninja;
      if(['chat','today','weather','actions'].includes(action))openPanel(action);
      if(action==='close')closePanel();
      if(action==='dismiss')dismissNotice();
      if(action==='event'&&currentNotice?.eventId){const id=currentNotice.eventId,generation=epoch;dismissNotice();request('/events').then(events=>{if(!safe()||generation!==epoch)return;state.events=events;eventDetail(id)}).catch(e=>toast(e.message))}
      if(action==='voice'){prefs.voice=!(prefs.voice&&voiceArmed);voiceArmed=prefs.voice;savePrefs();updateControls();if(prefs.voice)speak('Olá! Agora posso ler seus avisos em voz alta.');else window.speechSynthesis?.cancel()}
      if(action==='pause'){paused=!paused;prefs.paused=paused;savePrefs();updateControls();mode('idle')}
      if(action==='motion'){prefs.compact=!prefs.compact;savePrefs();updateVisibility()}
      if(action==='hide'){closePanel();prefs.hidden=true;savePrefs();updateVisibility();window.speechSynthesis?.cancel()}
      if(action==='fullchat'){closePanel();location.hash='ninja'}
    });
    updateVisibility();updateControls();mode('idle');nextAction=rest();
  }
  function summaryText(data){
    const parts=[];if(data.tasks)parts.push(`${data.tasks.open} tarefa${data.tasks.open===1?'':'s'} a concluir (${data.tasks.due_today} com prazo hoje)`);
    if(data.events)parts.push(`${data.events.length} compromisso${data.events.length===1?'':'s'} hoje`);
    return `Olá, ${data.name}! ${parts.length?'Você tem '+parts.join(' e ')+'.':'Seu espaço está pronto. Vamos começar?'}`;
  }
  async function loadBriefing(greet=false){
    const currentEpoch=epoch;
    try{const data=await request('/companion/briefing');if(!safe()||epoch!==currentEpoch)return;summary=data;if(greet)announce(summaryText(data),'summary');return data}catch(e){if(greet&&safe())announce('Não consegui consultar seu resumo agora. Confira sua conexão.');throw e}
  }
  function body(){return root?.querySelector('.ninja-talk-body')}
  function closePanel(){
    panelTab='';panelRequest++;if(!root)return;root.querySelector('.ninja-talk').hidden=true;root.classList.remove('talk-open');root.querySelector('.ninja-chat-trigger').focus();mode('idle');nextAction=rest();
  }
  async function openPanel(tab){
    if(!safe())return;panelTab=tab;const generation=++panelRequest,currentEpoch=epoch;
    root.querySelector('.ninja-talk').hidden=false;root.classList.add('talk-open');mode('think');
    root.querySelectorAll('.ninja-talk nav button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.ninja===tab)));
    root.querySelector('[data-ninja=close]').focus();body().innerHTML='<p class="ninja-hint" role="status">Consultando…</p>';
    const valid=()=>safe()&&epoch===currentEpoch&&generation===panelRequest&&panelTab===tab;
    try{
      if(tab==='actions'){
        const actions=[['idle','Descansar'],['walk','Caminhar pela tela'],['arms','Cruzar os braços'],['work','Abrir notebook e digitar'],['roll','Dar cambalhota'],['jump','Pular para o outro lado'],['jutsu','Jutsu com fumaça'],['wave','Acenar'],['salute','Saudar'],['stretch','Alongar'],['meditate','Meditar'],['celebrate','Comemorar']];
        body().innerHTML='<h3>Qual é a próxima missão?</h3><p class="ninja-hint">Escolha um movimento. Depois, o Ninja volta à rotina com pausas.</p><div class="ninja-action-picker">'+actions.map(([key,label])=>`<button type="button" data-ninja-animation="${key}">${label}</button>`).join('')+'</div>';
        body().querySelectorAll('[data-ninja-animation]').forEach(b=>b.onclick=()=>{
          const action=b.dataset.ninjaAnimation;closePanel();dismissNotice();
          if(reduce.matches){mode('idle');toast('As animações estão reduzidas nas preferências do dispositivo.');return}
          paused=false;prefs.paused=false;prefs.compact=false;savePrefs();updateControls();updateVisibility();
          if(['walk','jump','jutsu'].includes(action))travelAcross(action);
          else if(action==='roll'){const b=bounds();motion.play('roll',{target:Math.max(Math.min(b.left,b.right),Math.min(b.right,x+(x>b.right-90?-80:80)))});}
          else mode(action);
          nextAction=Date.now()+(action==='idle'?30000:15000);
        });return;
      }else if(tab==='today'){
        const data=await loadBriefing();if(!valid())return;
        body().innerHTML=`<p class="ninja-intro">${esc(summaryText(data))}</p>${data.tasks?`<a class="ninja-summary-count" href="#tasks"><strong>${data.tasks.open}</strong><span>Tarefas a concluir<small>${data.tasks.due_today} com prazo hoje</small></span></a>`:''}<h3>Sua agenda de hoje</h3>${data.events===null?'<p class="ninja-hint">Agenda indisponível para este perfil.</p>':data.events.length?data.events.map(e=>`<button class="ninja-agenda-item" data-event-open="${esc(e.id)}"><time>${hourTime(e.start)}</time><span>${esc(e.title)}<small>${esc(e.location||'Sem local definido')}</small></span></button>`).join(''):'<p class="ninja-hint">Nenhum compromisso hoje.</p>'}<small class="ninja-hint">Atualizado às ${hourTime(data.updated)} · horário de São Paulo</small>`;
        body().querySelectorAll('[data-event-open]').forEach(b=>b.onclick=async()=>{const id=b.dataset.eventOpen;try{state.events=await request('/events');if(!valid())return;closePanel();eventDetail(id)}catch(e){toast(e.message)}});
      }else if(tab==='weather'){
        const data=await request('/companion/weather');if(!valid())return;weatherData=data;
        if(!data.available){body().innerHTML=`<h3>${esc(data.city)}</h3><p class="ninja-hint">${esc(data.message)}</p>${state.user.master?'<p class="ninja-hint">Ative a chave OpenWeather no servidor conforme o guia 1.7.</p>':''}`;return}
        const text=`Em ${data.city}, ${data.stale?'a última consulta registrou':'agora são'} ${data.temperature} graus, ${data.description}.`;
        body().innerHTML=`<div class="ninja-weather"><span>${esc(data.city)}</span><strong>${esc(data.temperature)}°C</strong><p>${esc(data.description)}<small>Sensação de ${esc(data.feels_like)}°C</small></p></div>${data.stale?'<p class="ninja-hint">Última consulta disponível; atualização temporariamente indisponível.</p>':''}<h3>Próximas horas</h3>${data.forecast.length?data.forecast.slice(0,4).map(f=>`<div class="ninja-forecast"><time>${hourTime(f.time)}</time><span>${esc(f.description)}<small>${f.rain_probability}% de chance de chuva</small></span><strong>${f.temperature}°</strong></div>`).join(''):'<p class="ninja-hint">Previsão temporariamente indisponível.</p>'}<small class="ninja-hint">Observação: ${hourTime(data.observed)} · <a href="https://openweathermap.org/" target="_blank" rel="noopener">OpenWeather</a></small>`;
        speak(text+(data.forecast[0]?` Às ${hourTime(data.forecast[0].time)}, a previsão é ${data.forecast[0].description}, com ${data.forecast[0].temperature} graus.`:''));
      }else{
        if(!can('ai')||!can('chats')){body().innerHTML='<p class="ninja-hint">Seu perfil não tem acesso à IA. Solicite ao gestor.</p>';return}
        const room=await request('/ai/room',{method:'POST',data:{}});if(!valid())return;assistantRoom=room.id;
        const history=await request('/rooms/'+room.id+'/messages');if(!valid())return;
        body().innerHTML=`<div class="ninja-chat-log" role="log" aria-live="polite"></div><p class="ninja-chat-status" role="status"></p><form class="ninja-chat-form"><textarea name="message" rows="2" maxlength="5000" placeholder="Pergunte ao Ninja…" aria-label="Mensagem para o Ninja" required></textarea><button type="submit" aria-label="Enviar ao Ninja" ${chatBusy?'disabled':''}>↑</button></form><button data-ninja="fullchat" class="ninja-full-chat">Abrir conversa completa ↗</button>`;
        renderChat(history);const form=body().querySelector('form');form.onsubmit=e=>{e.preventDefault();sendChat(form,valid)};
        if(!state.integrations.ai_configured)body().querySelector('.ninja-chat-status').textContent='A IA aguarda ativação da conta OpenAI da empresa.';
        form.elements.message.focus();mode('idle');
      }
    }catch(e){if(valid())body().innerHTML=`<p class="ninja-hint" role="alert">${esc(e.message)}</p>`}
  }
  function renderChat(history){
    const log=body()?.querySelector('.ninja-chat-log');if(!log)return;
    log.innerHTML=history.messages?.length?history.messages.slice(-30).map(m=>`<article class="ninja-chat-message ${m.user_id===identity?'mine':''}"><small>${m.user_id===identity?'Você':'Ninja IA'}</small><p>${esc(m.text)}</p></article>`).join(''):'<p class="ninja-hint">Olá! Posso ajudar com ideias, textos e dúvidas. O resumo do dia e o clima ficam nas abas acima.</p>';
    log.scrollTop=log.scrollHeight;
  }
  async function sendChat(form,valid){
    if(chatBusy)return;const text=form.elements.message.value.trim();if(!text)return;
    chatBusy=true;const sendingEpoch=epoch,button=form.querySelector('button'),status=body().querySelector('.ninja-chat-status'),rid=assistantRoom;
    button.disabled=true;status.textContent='Enviando…';mode('think');
    try{
      const result=await request('/rooms/'+rid+'/messages',{method:'POST',data:{text}});
      if(!valid())return;form.elements.message.value='';status.textContent=result.ai_error?'Mensagem salva. '+result.ai_error:'Mensagem enviada.';
      const history=await request('/rooms/'+rid+'/messages');if(!valid())return;renderChat(history);
      if(result.ai&&!result.ai_error){const reply=history.messages.filter(m=>m.user_id!==identity).at(-1);if(reply)speak(reply.text)}
    }catch(e){if(valid())status.textContent=e.message}
    finally{if(sendingEpoch===epoch)chatBusy=false;if(valid()){button.disabled=false;mode('idle')}}
  }
  async function pollAlerts(){
    if(pollBusy||document.hidden||!document.hasFocus()||!navigator.onLine||!safe())return;
    const currentEpoch=epoch;pollBusy=true;
    try{const data=await request('/companion/alerts',{method:'POST',data:{}});if(!safe()||epoch!==currentEpoch)return;for(const e of data.alerts)announce(`${e.title} começa em ${e.minutes===60?'1 hora':e.minutes+' minutos'}, às ${hourTime(e.start)}.`,'alert',e.id)}
    catch{/* notifications remain available on the server; retry next poll */}
    finally{pollBusy=false}
  }
  window.addEventListener('nja:sale-celebrate',e=>{
    if(!safe()||document.hidden||prefs.hidden||prefs.compact||paused||reduce.matches)return;
    mode('celebrate',4000);nextAction=rest();
    window.dispatchEvent(new CustomEvent('nja:shuriken-burst',{detail:{x:x+(root.getBoundingClientRect().width||288)-56,y:root.querySelector('.ninja-character').getBoundingClientRect().top+55}}));
  });
  function resetUser(){
    epoch++;stopWalk();window.speechSynthesis?.cancel();if(root){root.remove();restore.remove();root=restore=null}
    identity=state.user?.id||'';chatBusy=false;last=interaction=Date.now();panelTab='';panelRequest++;notices=[];noticeUntil=0;currentNotice=null;lastRoute='';summary=null;weatherData=null;assistantRoom='';voiceArmed=false;nextPoll=0;
    if(!identity)return;
    key='nja-focus:'+identity+':'+dayKey();clock=new NinjaFocusClock(read(key));prefs=read('nja-companion-prefs:'+identity);paused=!!prefs.paused;mount();
  }
  ['pointerdown','pointermove','keydown','touchstart','scroll'].forEach(event=>document.addEventListener(event,()=>{interaction=Date.now()},{passive:true}));
  window.addEventListener('focus',()=>{last=interaction=Date.now();nextPoll=0});
  document.addEventListener('visibilitychange',()=>{last=Date.now();if(document.hidden){mode('idle');window.speechSynthesis?.cancel()}else nextPoll=0});
  window.addEventListener('resize',()=>{if(root){mode('idle');place(Math.min(x,bounds().right))}});
  reduce.addEventListener('change',()=>{if(root)mode('idle')});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&panelTab){e.preventDefault();closePanel()}});
  setInterval(()=>{
    if((state.user?.id||'')!==identity)resetUser();
    if(!safe())return;
    const now=Date.now(),newKey='nja-focus:'+identity+':'+dayKey();
    if(newKey!==key){key=newKey;clock=new NinjaFocusClock(read(key));last=now;lastRoute=''}
    const stored=read(key);clock.ms=Math.max(clock.ms,Math.min(86400000,Number(stored.ms)||0));clock.announced=Math.max(clock.announced,Number(stored.announced)||0);
    const hour=clock.advance(now-last,active());last=now;write(key,clock.snapshot());
    const minutes=Math.floor(clock.ms/60000),hours=Math.floor(minutes/60);
    root.querySelector('[data-ninja-clock]').textContent=String(hours).padStart(2,'0')+':'+String(minutes%60).padStart(2,'0');
    root.querySelector('[data-ninja-status]').textContent=paused?'Contador pausado':active()?'Uso ativo hoje':'Aguardando você';
    root.querySelector('.ninja-time').title='Uso ativo neste navegador. Não altera as horas das tarefas.';
    root.style.setProperty('--ninja-progress',(clock.ms%3600000/36000)+'%');
    if(hour)announce(ninjaHourMessage(hour),'hour');
    if(noticeUntil&&now>=noticeUntil)dismissNotice();
    if(state.page!==lastRoute){const previous=lastRoute;lastRoute=state.page;if(previous)walkAcross();if(state.page==='dashboard')loadBriefing(true).catch(()=>{})}
    if(now>=nextPoll){nextPoll=now+30000;pollAlerts()}
    showNotice();
    if(root.dataset.mode==='idle'&&now>=nextAction&&!paused&&!document.hidden&&!prefs.hidden&&!prefs.compact&&!panelTab&&!noticeUntil&&!reduce.matches){
      const sequence=['arms','walk','work','roll','jump','arms','jutsu','work'];const action=sequence[step++%sequence.length];
      if(['walk','jump','jutsu'].includes(action))travelAcross(action);else if(action==='roll'){const b=bounds();motion.play('roll',{target:Math.max(Math.min(b.left,b.right),Math.min(b.right,x+(x>b.right-90?-80:80)))});}else mode(action);
      nextAction=rest();
    }
  },1000);
})();
