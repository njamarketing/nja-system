const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const context={window:{innerHeight:900},console,cancelAnimationFrame:()=>{}};vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/../static/ninja-atlas-v110.js','utf8'),context);vm.runInContext(fs.readFileSync(__dirname+'/../static/ninja-motion-v111.js','utf8'),context);
const {frameAt,durations}=context.window.NinjaMotion,atlas=context.window.NinjaAtlas;
assert.equal(new Set(Array.from({length:36},(_,i)=>frameAt('walk',i*1000/30).frame)).size,36);assert.equal(frameAt('walk',1200).frame,0);
assert.deepEqual([0,200,400,900,4700].map(t=>frameAt('arms',t).frame),[0,1,2,3,0]);
assert.equal(frameAt('work',0).frame,4);assert.equal(frameAt('work',500).frame,5);assert.notEqual(frameAt('work',1000).frame,frameAt('work',1160).frame);assert.equal(frameAt('work',10400).frame,4);
assert.equal(frameAt('roll',0).frame,8);assert.equal(frameAt('roll',600).frame,10);assert.equal(frameAt('roll',1600).frame,11);assert.equal(frameAt('roll',1800).rotate,-360);
assert.equal(frameAt('jump',0).travel,0);assert.ok(frameAt('jump',1100).y<-150);assert.equal(frameAt('jump',2200).travel,1);assert.ok(Math.abs(frameAt('jump',2200).y)<.001);
assert.equal(frameAt('jutsu',1000).smoke,1);assert.equal(frameAt('jutsu',1600).opacity,0);assert.equal(frameAt('jutsu',1800).travel,1);assert.equal(frameAt('jutsu',2100).smoke,2);assert.equal(frameAt('jutsu',3100).opacity,1);
for(const [name,duration] of Object.entries(durations)){for(let t=0;t<=duration;t+=25){const f=frameAt(name,t,duration||2400);assert.ok(atlas[f.atlas].frames[f.frame],name);assert.ok(f.opacity>=0&&f.opacity<=1);assert.ok(f.travel>=0&&f.travel<=1)}}
for(const sheet of Object.values(atlas))for(const [i,[x,y,w,h]] of sheet.frames.entries()){const src=sheet.sources?.[i]||sheet;assert.ok(x>=0&&y>=0&&x+w<=src.width&&y+h<=src.height)}
console.log('PASS: 36 walk frames, arm transitions, notebook/typing/closing, roll, jump arc, two smoke phases, teleport opacity, atlas bounds.');
// Interruption and cancellation must restore visibility and never teleport later.
let callbacks=new Map(),nextId=0,clock=0,position=0,finished=0;
context.performance={now:()=>clock};context.getComputedStyle=()=>({getPropertyValue:()=>112});context.requestAnimationFrame=fn=>{callbacks.set(++nextId,fn);return nextId};context.cancelAnimationFrame=id=>callbacks.delete(id);
const sprite={style:{}},character={style:{}},root={isConnected:true,dataset:{},querySelector:s=>s==='.ninja-sprite'?sprite:character,classList:{remove(){},toggle(){}}};
const player=new context.window.NinjaMotion.Player(root,{position:()=>position,place:x=>position=x,onfinish:()=>finished++});
const advance=t=>{clock=t;const jobs=[...callbacks.values()];callbacks.clear();jobs.forEach(fn=>fn(t))};
player.play('jump',{target:400});advance(1100);assert.ok(position>0&&position<400);const snapshot=position;player.stop();advance(2300);assert.equal(position,snapshot);assert.equal(character.style.opacity,'1');assert.equal(finished,0);assert.equal(callbacks.size,0);
player.play('walk',{target:400,duration:900});advance(3200);assert.equal(position,400);assert.equal(finished,1);
const quiet=new context.window.NinjaMotion.Player(root,{quiet:()=>true});quiet.play('jump',{target:900});assert.equal(callbacks.size,0);assert.equal(root.dataset.frame,'actions:0');
console.log('PASS: interrupting motion cancels travel, restores visibility, stops callbacks; reduced motion stays still.');

const imageKeys=Array.from({length:60},(_,i)=>{const f=frameAt('walk',i*1000/60);return f.frame+':'+Math.round(f.mix*24)});assert.equal(new Set(imageKeys).size,60);assert.equal(context.window.NinjaMotion.fps,60);assert.equal(frameAt('walk',1200).frame,0);assert.equal(frameAt('walk',1200).mix,0);assert.ok(frameAt('jutsu',500).charge>.9);assert.equal(frameAt('jutsu',1600).charge,0);assert.notEqual(frameAt('idle',3000).rotate,frameAt('idle',4000).rotate);
console.log('PASS: 60 distinct image samples per second, seamless cycle indices, preparatory jutsu aura.');
