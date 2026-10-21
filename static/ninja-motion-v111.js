/* NJA 1.11. Timelines shared by the assistant and the animation laboratory. */
(function(global){
'use strict';
const durations={idle:0,arms:4800,work:10500,roll:1800,jump:2200,jutsu:3100,wave:2200,salute:2200,stretch:3000,meditate:4000,think:3000,celebrate:2400};
const clamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
function rawFrameAt(action,t,duration=durations[action]||2400){
 const p=clamp(t/duration),f={atlas:'actions',frame:0,y:0,rotate:0,scaleX:1,scaleY:1,opacity:1,travel:0,smoke:0};
 if(action==='walk'){f.atlas='walk';f.frame=Math.floor(t*30/1000+1e-7)%36;f.travel=p;f.y=-Math.sin(t/1200*Math.PI*4)*1.1;}
 else if(action==='arms'){f.frame=t<180?0:t<360?1:t<540?2:t<duration-450?3:t<duration-250?2:0;f.y=-Math.sin(t/600)*.7;}
 else if(action==='work'){f.frame=t<400?4:t<800?5:t<duration-700?6+Math.floor(t/160)%2:t<duration-300?5:4;f.rotate=Math.sin(t/280)*.4;}
 else if(action==='roll'){f.frame=p<.15?8:p<.8?10:p<.94?11:0;f.rotate=p<.15?0:p<.8?-360*(p-.15)/.65:-360;f.y=-Math.sin(clamp((p-.12)/.72)*Math.PI)*45;f.travel=p<.15?0:clamp((p-.15)/.7);}
 else if(action==='jump'){f.frame=p<.16?8:p<.83?9:p<.95?11:0;const flight=clamp((p-.16)/.67);f.y=-4*flight*(1-flight)*Math.min(210,global.innerHeight?global.innerHeight*.25:210);f.travel=flight;f.rotate=p>.16&&p<.83?-10+20*flight:0;f.scaleY=p<.16?1-.12*Math.sin(p/.16*Math.PI):p>.83&&p<.95?.9:1;}
 else if(action==='jutsu'){f.frame=t<300?12:t<600?13:t<900?14:15;f.smoke=t>=900&&t<1550?1:t>=1900&&t<2600?2:0;f.opacity=t<1000?1:t<1350?1-clamp((t-1000)/350):t<2000?0:clamp((t-2000)/500);f.travel=t>=1750?1:0;if(t>2600)f.frame=0;}
 else if(action==='think'||action==='salute'){f.frame=2;f.rotate=Math.sin(t/900)*1.5;}
 else if(action==='meditate'){f.frame=4;f.y=-3-Math.sin(t/600)*2;}
 else if(action==='celebrate'||action==='wave'||action==='stretch'){f.frame=Math.floor(t/280)%2?1:0;f.y=-Math.abs(Math.sin(t/330))*6;}
 else{f.frame=0;f.scaleY=1+Math.sin(t/850)*.012;f.rotate=Math.sin(t/1700)*.65;}
 return f;
}
function frameAt(action,t,duration=durations[action]||2400){
 const f=rawFrameAt(action,t,duration);f.next=f.frame;f.mix=0;f.charge=action==='jutsu'&&t<1000?Math.sin(clamp(t/1000)*Math.PI):0;
 if(action==='walk'){const phase=t*30/1000;f.next=(f.frame+1)%36;f.mix=phase-Math.floor(phase+1e-7);if(f.mix<0)f.mix=0;}
 else if(action!=='idle'){const look=120,end=rawFrameAt(action,Math.min(t+look,duration),duration);if(end.frame!==f.frame){let lo=t,hi=Math.min(t+look,duration);for(let i=0;i<12;i++){const mid=(lo+hi)/2;if(rawFrameAt(action,mid,duration).frame===f.frame)lo=mid;else hi=mid;}f.next=rawFrameAt(action,hi,duration).frame;f.mix=clamp(1-(hi-t)/look);}}
 return f;
}
class Player{
 constructor(root,options={}){this.root=root;this.sprite=root.querySelector('.ninja-sprite');this.character=root.querySelector('.ninja-character');this.options=options;this.raf=0;this.smokes=[];this.serial=0;this.lastFrame='';}
 stop(){this.serial++;cancelAnimationFrame(this.raf);this.raf=0;this.smokes.forEach(x=>x.remove());this.smokes=[];this.character.style.transform='';this.character.style.opacity='1';this.root.classList.remove('motion-moving');this.root.style?.setProperty('--ninja-charge','0');}
 draw(f,left=false){const atlas=global.NinjaAtlas[f.atlas],rect=atlas.frames[f.frame],source=atlas.sources?.[f.frame]||atlas;if(!rect)return;const size=parseFloat(getComputedStyle(this.root).getPropertyValue('--sprite-width'))||112;
  // Preserve alpha, align the feet, keep a stable head scale across rows.
  let scale=size/313.5;if(f.atlas==='walk')scale*=371/rect[3];if(f.atlas==='actions'&&f.frame>=12)scale*=1.22;
  const [x,y,w,h]=rect,s=this.sprite.style;s.width=w*scale+'px';s.height=h*scale+'px';s.left=(size-w*scale)/2+'px';s.bottom='0px';s.backgroundImage=`url("${source.url}")`;s.backgroundSize=`${source.width*scale}px ${source.height*scale}px`;s.backgroundPosition=`${-x*scale}px ${-y*scale}px`;s.transform=left?'scaleX(-1)':'none';
  const picture=global.NinjaInbetween?.get(f);
  if(picture){if(!this.canvas){this.canvas=document.createElement('canvas');this.canvas.width=160;this.canvas.height=160;this.canvas.className='ninja-flow-canvas';this.canvas.setAttribute('aria-hidden','true');this.character.append(this.canvas);}const width=size*160/112;Object.assign(this.canvas.style,{width:width+'px',height:width+'px',left:(size-width)/2+'px',transform:left?'scaleX(-1)':'none',display:'block'});const ctx=this.canvas.getContext('2d');ctx.clearRect(0,0,160,160);ctx.drawImage(picture,0,0);this.sprite.style.visibility='hidden';}
  else{this.sprite.style.visibility='visible';if(this.canvas)this.canvas.style.display='none';}
  this.root.style?.setProperty('--ninja-charge',String(f.charge||0));
  this.character.style.transform=`translateY(${f.y}px) rotate(${f.rotate*(left?-1:1)}deg) scale(${f.scaleX},${f.scaleY})`;this.character.style.opacity=f.opacity;this.root.dataset.frame=f.atlas+':'+f.frame;
 }
 smoke(){const r=this.character.getBoundingClientRect(),node=document.createElement('div');node.className='ninja-smoke-v19';node.setAttribute('aria-hidden','true');node.style.left=r.left+r.width/2+'px';node.style.top=r.bottom-45+'px';for(let i=0;i<14;i++){const p=document.createElement('i'),angle=i/14*Math.PI*2;p.style.setProperty('--dx',Math.cos(angle)*(40+i%4*13)+'px');p.style.setProperty('--dy',Math.sin(angle)*42-30+'px');p.style.setProperty('--delay',i%3*25+'ms');node.append(p)}document.body.append(node);this.smokes.push(node);node.addEventListener('animationend',()=>{node.remove();this.smokes=this.smokes.filter(x=>x!==node)},{once:true});}
 play(action='idle',options={}){
  this.stop();const serial=this.serial,quiet=this.options.quiet?.();this.root.dataset.mode=action;
  if(quiet){this.draw(frameAt('idle',0));return;}
  const start=performance.now(),origin=this.options.position?.()||0,target=options.target??origin,duration=options.duration||durations[action]||2400;let smoke=0,lastSample=-1;
  const moving=['walk','jump','jutsu','roll'].includes(action);this.root.classList.toggle('motion-moving',moving);
  const tick=now=>{if(serial!==this.serial||!this.root.isConnected)return;if(this.options.quiet?.()){this.stop();this.draw(frameAt('idle',0));return;}
   const elapsed=now-start,sample=Math.floor(elapsed*60/1000);if(sample===lastSample&&elapsed<duration){this.raf=requestAnimationFrame(tick);return;}lastSample=sample;const f=frameAt(action,action==='idle'?sample*1000/60:Math.min(sample*1000/60,duration),duration);if(moving)this.options.place?.(origin+(target-origin)*f.travel);this.draw(f,target<origin&&moving);
   if(f.smoke&&smoke!==f.smoke){smoke=f.smoke;this.smoke();}
   if(action!=='idle'&&elapsed>=duration){this.options.place?.(moving?target:origin);this.options.onfinish?.(action);return;}
   this.raf=requestAnimationFrame(tick);
  };this.raf=requestAnimationFrame(tick);
 }
}
global.NinjaMotion={Player,frameAt,durations,fps:60,walkCycle:1200};
})(window);
