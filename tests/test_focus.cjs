// Behavioral checks: hourly rewards, inactivity, sleeping tabs and persistence.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const code=fs.readFileSync(__dirname+'/../static/playful.js','utf8').split('(() => {')[0];
const ctx=vm.createContext({});vm.runInContext(code+';globalThis.Clock=NinjaFocusClock;globalThis.message=ninjaHourMessage;',ctx);
const c=new ctx.Clock({ms:3598000});
assert.equal(c.advance(1000,false),0);assert.equal(c.ms,3598000,'Inactive use must not count');
assert.equal(c.advance(1000,true),0);assert.equal(c.advance(1000,true),1);
assert.equal(c.advance(1000,true),0,'Each hour announces once');
const restored=new ctx.Clock(c.snapshot());assert.equal(restored.advance(1000,true),0,'Refresh must not replay reward');
const sleeping=new ctx.Clock();sleeping.advance(3600000,true);assert.equal(sleeping.ms,5000,'Sleeping tabs must not add a phantom hour');
sleeping.advance(-1000,true);assert.equal(sleeping.ms,5000,'Clock moving backward must not subtract time');
assert.notEqual(ctx.message(1),ctx.message(2));assert.match(ctx.message(10),/10 horas/);
const second=new ctx.Clock({ms:7199000,announced:1});assert.equal(second.advance(1000,true),2);
console.log('OK: hourly rewards, inactivity, persistence, sleeping tabs, time changes and distinct messages.');
