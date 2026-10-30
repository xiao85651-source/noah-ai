import {test} from 'node:test';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {batch} from '../model.mjs';
test('consent, local request boundaries and real training lifecycle',async()=>{
 const dir=mkdtempSync(join(tmpdir(),'noah-test-')),port=14317,base=`http://127.0.0.1:${port}`;
 const invite='test-only-invitation-abcdefghijklmnopqrstuvwxyz',publicPort=14318;
 const child=spawn(process.execPath,['server.mjs'],{cwd:new URL('..',import.meta.url),env:{...process.env,PORT:String(port),NOAH_DATA:dir,NOAH_PUBLIC_PORT:String(publicPort),NOAH_JOIN_TOKEN:invite},stdio:'pipe'});
 let token='';
 const api=async(path,data,headers={})=>{const r=await fetch(base+path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json','X-Noah-Token':token,...headers},body:data?JSON.stringify(data):undefined});return {status:r.status,body:await r.json()};};
 try{
  for(let i=0;i<100;i++){try{token=(await api('/api/session')).body.token;break;}catch{await new Promise(r=>setTimeout(r,50));}}
  assert.ok(token);assert.equal((await api('/api/status')).body.model.step,0);
  assert.equal((await api('/api/training',{active:true},{'X-Noah-Token':''})).status,403);
  assert.equal((await api('/api/training',{active:true},{Origin:'https://example.com'})).status,403);
  assert.equal((await api('/api/worker',{start:true})).status,400);
  const remote=async(path,data,key=invite)=>{const r=await fetch(`http://127.0.0.1:${publicPort}`+path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json','X-Noah-Token':key},body:data?JSON.stringify(data):undefined});return {status:r.status,body:await r.json()};};
  assert.equal((await remote('/api/session')).status,403);
  assert.equal((await remote('/api/training',{active:true})).status,403);
  assert.equal((await remote('/api/nodes/join',{name:'bad'},'bad-token')).status,403);
  const guest=(await remote('/api/nodes/join',{name:'guest',cpu:'CPU',threads:1})).body;
  assert.ok(guest.accessToken);
  assert.equal((await remote('/api/tasks/next',{id:guest.id},guest.accessToken)).status,200);
  assert.equal((await remote('/api/tasks/next',{id:guest.id},invite)).status,403);
  const id=(await api('/api/nodes/join',{name:'test',cpu:'CPU',threads:1})).body.id;
  assert.equal((await api('/api/tasks/next',{id})).body.job,null);
  await api('/api/training',{active:true,duty:20});
  const task=(await api('/api/tasks/next',{id})).body;assert.ok(task.job);
  const result=batch(task.model,task.ids,task.positions);
  const submit=await api('/api/tasks/result',{id,job:task.job,version:task.model.step,gradient:result.gradient,loss:result.loss,duration:10});
  assert.equal(submit.body.accepted,true);assert.equal((await api('/api/status')).body.model.step,1);
  assert.equal((await remote('/api/tasks/next',{id},guest.accessToken)).status,403);
  const remoteTask=(await remote('/api/tasks/next',{id:guest.id},guest.accessToken)).body;
  const remoteResult=batch(remoteTask.model,remoteTask.ids,remoteTask.positions);
  const remoteSubmit=await remote('/api/tasks/result',{id:guest.id,job:remoteTask.job,version:remoteTask.model.step,gradient:remoteResult.gradient,loss:remoteResult.loss,duration:10},guest.accessToken);
  assert.equal(remoteSubmit.body.accepted,true);assert.equal((await api('/api/status')).body.model.step,2);
  assert.equal((await api('/api/tasks/result',{id,job:task.job,version:0,gradient:result.gradient,loss:result.loss})).status,400);
  const second=(await api('/api/tasks/next',{id})).body;await api('/api/training',{active:false});
  assert.equal((await api('/api/tasks/result',{id,job:second.job,version:2,gradient:result.gradient,loss:result.loss})).body.accepted,false);
  assert.equal((await api('/api/model/export')).body.step,2);
  assert.equal((await api('/api/sample',{prompt:'问：'})).body.experimental,true);
 }finally{child.kill();await new Promise(resolve=>child.once('exit',resolve));rmSync(dir,{recursive:true,force:true});}
});
