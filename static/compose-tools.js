/* Shared writing controls. No HTML from user input is injected. */
(()=>{
const selection=new WeakMap();
const baseRequest=request;
request=function(path,options={}){
 if(options.data && typeof options.data.text==='string'){
  const mentions=[...new Set([...document.querySelectorAll(fields)].filter(el=>el.value===options.data.text).flatMap(el=>[...(selection.get(el)||new Map())].filter(([id,name])=>el.value.includes('@'+name)).map(([id])=>id)))];
  options={...options,data:{...options.data,mentions}};
 }
 return baseRequest(path,options);
};
const palette=['😀','😊','😂','🥰','😎','🤔','😅','🙌','👏','👍','❤️','💙','🎉','✨','🔥','🚀','✅','📌','📅','💡','💪','🥷','☕','🙏'];
const fields='textarea:not([readonly]):not([disabled]),input[name="text"]:not([disabled])';
function button(text,label,fn){const b=document.createElement('button');b.type='button';b.textContent=text;b.setAttribute('aria-label',label);b.title=label;b.onclick=fn;return b;}
function enhance(input){
 if(input.dataset.writingTools || input.closest('#loginform'))return;
 input.dataset.writingTools='true';selection.set(input,new Map());
 const toolbar=document.createElement('div');toolbar.className='writing-tools';toolbar.setAttribute('role','group');toolbar.setAttribute('aria-label','Ferramentas de escrita');
 const panel=document.createElement('div');panel.className='writing-picker';panel.hidden=true;
 input.after(toolbar);toolbar.after(panel);
 let start=0,end=0,mode='';
 const remember=()=>{start=input.selectionStart??input.value.length;end=input.selectionEnd??start};
 input.addEventListener('select',remember);input.addEventListener('keyup',remember);input.addEventListener('click',remember);input.addEventListener('blur',remember);
 const close=()=>{panel.hidden=true;panel.replaceChildren();mode='';};
 const insert=text=>{if(input.maxLength>0 && input.value.length-(end-start)+text.length>input.maxLength){toast('O texto atingiu o limite deste campo.');return;}input.focus();input.setRangeText(text,start,end,'end');remember();close();input.dispatchEvent(new Event('input',{bubbles:true}));};
 const keyboard=()=>{close();input.focus();input.setSelectionRange(start,end);};
 toolbar.append(button('☺ Emojis','Escolher emoji',()=>{remember();if(mode==='emoji'){keyboard();return;}close();mode='emoji';panel.hidden=false;for(const emoji of palette)panel.append(button(emoji,'Inserir '+emoji,()=>insert(emoji)));}),button('@ Marcar','Marcar uma pessoa',()=>{remember();people('');}),button('⌨ Teclado','Voltar ao teclado para escrever',keyboard));
 function people(query,range=null){
  close();mode='people';panel.hidden=false;
  const search=document.createElement('input');search.type='search';search.placeholder='Buscar pessoa';search.setAttribute('aria-label','Buscar pessoa para mencionar');search.value=query;
  const list=document.createElement('div');list.className='mention-results';
  const draw=()=>{list.replaceChildren();let users=state.users.filter(u=>u.active);if(input.closest('#messageform')){const room=state.rooms.find(r=>r.id===state.room);users=users.filter(u=>room?.members.includes(u.id));}
   users=users.filter(u=>u.name.toLocaleLowerCase().includes(search.value.toLocaleLowerCase()));
   for(const u of users.slice(0,40)){const b=button(u.name+(u.title?' · '+u.title:''),'Mencionar '+u.name,()=>{selection.get(input).set(u.id,u.name);if(range){[start,end]=range;}insert('@'+u.name+' ')});list.append(b);}
   if(!users.length)list.textContent='Nenhuma pessoa encontrada.';
  };search.oninput=draw;panel.append(search,list);draw();if(!range)search.focus();
 }
 input.addEventListener('input',()=>{remember();const match=input.value.slice(0,start).match(/(?:^|\s)@([^@\s]*)$/);if(match){end=start;start-=match[1].length+1;people(match[1],[start,end]);}else if(mode==='people')close();});
 panel.addEventListener('keydown',e=>{if(e.key==='Escape'){e.stopPropagation();keyboard();}});
}
function scan(){document.querySelectorAll(fields).forEach(enhance);const menu=document.getElementById('menu');if(menu){menu.setAttribute('aria-controls','sidebar');menu.setAttribute('aria-expanded',String(document.getElementById('sidebar')?.classList.contains('open')||false));}}
let queued=false;new MutationObserver(()=>{if(!queued){queued=true;queueMicrotask(()=>{queued=false;scan()});}}).observe(document.body,{childList:true,subtree:true});scan();
function closeMenu(){const sidebar=document.getElementById('sidebar');if(!sidebar?.classList.contains('open'))return;sidebar.classList.remove('open');document.getElementById('menu')?.setAttribute('aria-expanded','false');document.getElementById('menu')?.focus();}
document.addEventListener('click',e=>{if(e.target.closest('.sidebar-close') || (e.target.closest('#sidebar nav a')))closeMenu();else if(e.target.closest('#menu')){document.getElementById('menu').setAttribute('aria-expanded',String(document.getElementById('sidebar').classList.contains('open')));}else if(!e.target.closest('#sidebar')&&matchMedia('(max-width:760px)').matches)closeMenu();});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeMenu();});
})();
