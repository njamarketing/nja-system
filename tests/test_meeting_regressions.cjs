const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const requests=[];let payload;
const ctx={console,Map,Set,Promise,setTimeout,setInterval:()=>{},window:{addEventListener:()=>{}},document:{},chooseCall:()=>{},logoutLocal:()=>{},bindChatDetails:()=>{},shell:()=>{},bootstrap:()=>{},state:{user:{id:'a'},rooms:[]},can:()=>true,currentCall:null,callSetupBusy:false,$:()=>null,toast:()=>{},request:async(path,data)=>{requests.push({path,data});return payload;}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(__dirname+'/../static/meetings.js','utf8'),ctx);
(async()=>{
 payload={meetings:[{id:'elsewhere',my_status:'joined'}],ice_servers:[]};await vm.runInContext('pollMeetings()',ctx);assert(!requests.some(r=>r.path.endsWith('/action')),'An idle tab must not leave another tab’s meeting');
 requests.length=0;payload={meeting:{id:'m',status:'active',my_status:'joined'},signals:[{id:1,sender:'b',kind:'candidate',payload:{candidate:'broken'}},{id:2,sender:'c',kind:'candidate',payload:{candidate:'valid'}}]};
 vm.runInContext(`currentMeeting={id:'m'};syncMeetingPeers=async()=>{};globalThis.accepted=[];meetingPeers.set('b',{pc:{remoteDescription:{},addIceCandidate:async()=>{throw Error('Invalid candidate')}},candidates:[]});meetingPeers.set('c',{pc:{remoteDescription:{},addIceCandidate:async c=>accepted.push(c)},candidates:[]});`,ctx);
 await vm.runInContext('pollMeetings()',ctx);assert.equal(vm.runInContext('accepted.length',ctx),1);assert.equal(vm.runInContext('meetingCursor',ctx),2);
 console.log('OK: second-tab regression and independent processing of group peers. Media connectivity still requires live device testing.');
})().catch(e=>{console.error(e);process.exit(1)});
