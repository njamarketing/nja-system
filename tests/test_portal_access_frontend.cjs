'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const root=path.join(__dirname,'..','static');
for(const file of ['portal-access-ui.js','collaboration-updates.js','compose-tools.js','people-picker.js','portal.js']){
 const source=fs.readFileSync(path.join(root,file),'utf8');
 assert.doesNotThrow(()=>new vm.Script(source,{filename:file}),file+' must parse');
}
const access=fs.readFileSync(path.join(root,'portal-access-ui.js'),'utf8');
assert.match(access,/Copiar link/);assert.match(access,/mode:'password'/);assert.match(access,/mode:'email'/);
const html=fs.readFileSync(path.join(root,'index.html'),'utf8'),worker=fs.readFileSync(path.join(root,'sw.js'),'utf8');
assert.ok(html.includes('/portal-access-ui.js'));assert.ok(worker.includes("'/portal-access-ui.js'"));
console.log('OK: menus, short invites and portal access controls parse and load.');
