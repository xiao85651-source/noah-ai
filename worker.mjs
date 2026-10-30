import {cpus} from 'node:os';
import {createInterface} from 'node:readline/promises';
import {stdin,stdout} from 'node:process';
import {batch} from './model.mjs';
const args=process.argv.slice(2),managed=args.includes('--managed');
const base=process.env.NOAH_URL||'http://127.0.0.1:4317';
const local=/^http:\/\/127\.0\.0\.1:\d+$/.test(base);
const endpoint=new URL(base);
if(!local&&(endpoint.protocol!=='https:'||endpoint.username||endpoint.password||endpoint.pathname!=='/'||endpoint.search||endpoint.hash))throw Error('Remote coordinator must be a plain HTTPS origin without embedded credentials.');
if(!managed){const rl=createInterface({input:stdin,output:stdout});console.log('Noah算力客户端：只执行随项目提供的字符模型训练代码。会消耗 CPU、电力和网络资源。\n单线程运行，每个批次后休息。Ctrl+C 退出。');const answer=await rl.question('输入 JOIN 自愿加入本机训练：');rl.close();if(answer!=='JOIN')process.exit(0);}
let token=process.env.NOAH_TOKEN||process.env.NOAH_NODE_TOKEN,id,stopping=false;
async function api(path,data){const r=await fetch(base+path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json','X-Noah-Token':token||''},body:data?JSON.stringify(data):undefined,signal:AbortSignal.timeout(30000)});const result=await r.json();if(!r.ok)throw Error(result.error||r.status);return result;}
if(!token){if(!local)throw Error('Remote contribution requires NOAH_NODE_TOKEN from the coordinator owner.');token=(await api('/api/session')).token;}
const enrollmentToken=token;
async function enroll(){token=enrollmentToken;const registration=await api('/api/nodes/join',{name:process.env.NOAH_NODE_NAME||'Windows 贡献节点',cpu:cpus()[0]?.model||'CPU',threads:cpus().length,managed:managed&&local});id=registration.id;token=registration.accessToken;}
await enroll();
console.log('已接入协调器。节点：'+id+'；等待任务。Ctrl+C 退出。');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function leave(){stopping=true;try{await api('/api/nodes/leave',{id});}catch{}process.exit(0);}
process.on('SIGINT',leave);process.on('SIGTERM',leave);
while(!stopping){try{const task=await api('/api/tasks/next',{id});if(!task.job){await delay(1500);continue;}const started=Date.now();const result=batch(task.model,task.ids,task.positions);const duration=Date.now()-started;const status=await api('/api/tasks/result',{id,job:task.job,version:task.model.step,gradient:result.gradient,loss:result.loss,duration});console.log(`任务 ${task.job.slice(0,8)} | loss ${result.loss.toFixed(4)} | ${status.accepted?'已接受':'已丢弃'} | ${duration}ms`);await delay(Math.max(300,Math.ceil(duration*(100/task.duty-1))));}catch(error){console.error(error.message);if(/Unknown node|Unauthorized/.test(error.message)){try{await enroll();}catch(e){console.error(e.message);}}await delay(3000);}}
