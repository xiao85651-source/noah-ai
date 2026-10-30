import http from 'node:http';
import {readFileSync,writeFileSync,mkdirSync,existsSync,renameSync,appendFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {join,dirname} from 'node:path';
import {randomBytes,randomUUID} from 'node:crypto';
import {spawn} from 'node:child_process';
import {createModel,encode,batch,applyGradient,sample,keys,seeded,context} from './model.mjs';
const root=dirname(fileURLToPath(import.meta.url)),dataDir=process.env.NOAH_DATA||join(root,'data');mkdirSync(dataDir,{recursive:true});
const port=Number(process.env.PORT||4317),host=`127.0.0.1:${port}`,token=randomBytes(32).toString('hex');
const publicPort=Number(process.env.NOAH_PUBLIC_PORT||0),joinToken=process.env.NOAH_JOIN_TOKEN||'';
if(publicPort&&(!Number.isInteger(publicPort)||publicPort===port||joinToken.length<32))throw Error('Public ingress needs a distinct port and a join token of at least 32 characters.');
const nodeTokens=new Map(),nodePaths=new Set(['/api/nodes/join','/api/nodes/leave','/api/tasks/next','/api/tasks/result']);
const lines=readFileSync(join(root,'corpus.txt'),'utf8').trim().split('\n');
const trainText=lines.filter((_,i)=>i%5!==4).join('\n'),validationText=lines.filter((_,i)=>i%5===4).join('\n');
const checkpoint=join(dataDir,'checkpoint.json');
let model=existsSync(checkpoint)?JSON.parse(readFileSync(checkpoint,'utf8')):createModel(trainText+validationText);
if(model.format!=='noah-tiny-v1')throw Error('Unsupported checkpoint');
const trainIds=encode(model,trainText),validationIds=encode(model,validationText);
const validationPositions=Array.from({length:32},(_,i)=>context+Math.floor(i*(validationIds.length-context)/32));
const lossOf=m=>batch(m,validationIds,validationPositions,false).loss;
let validationLoss=lossOf(model),active=false,duty=20,worker=null,workerNode=null,accepted=0;
const initialLoss=validationLoss,nodes=new Map(),jobs=new Map(),events=[],history=[{step:model.step,loss:validationLoss}],random=seeded(2026);
function event(message){events.unshift({time:new Date().toISOString(),message});events.splice(30);}
event('本机协调器启动；训练已暂停，等待用户自愿接入。');
function save(){writeFileSync(checkpoint+'.tmp',JSON.stringify(model));renameSync(checkpoint+'.tmp',checkpoint);}
function status(){const now=Date.now();return {name:'Noah',scope:'localhost',training:active,duty,managedWorker:!!worker,model:{name:'Noah Seed',type:'字符神经网络实验模型',step:model.step,parameters:keys.reduce((n,k)=>n+model[k].length,0),vocab:model.vocab.length,validationLoss,initialLoss,trainCharacters:trainIds.length,validationCharacters:validationIds.length,accepted},nodes:[...nodes.values()].map(n=>({...n,online:now-n.lastSeen<15000})),history,events};}
function stopWorker(){if(worker){worker.kill();worker=null;}if(workerNode&&nodes.has(workerNode))nodes.get(workerNode).lastSeen=0;workerNode=null;}
function startWorker(){if(worker)return;worker=spawn(process.execPath,[join(root,'worker.mjs'),'--managed'],{cwd:root,windowsHide:true,env:{...process.env,NOAH_URL:`http://${host}`,NOAH_TOKEN:token},stdio:['ignore','pipe','pipe']});const owned=worker;for(const stream of [owned.stdout,owned.stderr])stream.on('data',b=>appendFileSync(join(dataDir,'worker.log'),b));owned.on('error',e=>event('客户端启动失败：'+e.message));owned.on('exit',()=>{if(worker===owned){worker=null;if(workerNode&&nodes.has(workerNode))nodes.get(workerNode).lastSeen=0;}event('本机算力客户端已退出。');});event('已按用户操作启动本机单线程客户端。');}
function json(res,status,value){res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});res.end(JSON.stringify(value));}
async function body(req){let text='';for await(const chunk of req){text+=chunk;if(text.length>4*1024*1024)throw Error('Request too large');}return JSON.parse(text||'{}');}
const handler=async(req,res)=>{
 try{
  const publicIngress=!!publicPort&&req.socket.localPort===publicPort;
  if(!publicIngress&&req.headers.host!==host&&req.headers.host!==`localhost:${port}`)return json(res,403,{error:'Invalid host'});
  const path=new URL(req.url,`http://${host}`).pathname;
  if(publicIngress&&(req.method!=='POST'||!nodePaths.has(path)||req.headers.origin))return json(res,403,{error:'Contributor API only'});
  if(req.headers.origin&&![`http://${host}`,`http://localhost:${port}`].includes(req.headers.origin))return json(res,403,{error:'Invalid origin'});
  if(req.method==='GET'){
   if(path==='/api/session')return json(res,200,{token});
   if(path==='/api/status')return json(res,200,status());
   if(path==='/api/model/export'){res.setHeader('Content-Disposition','attachment; filename="noah-tiny-checkpoint.json"');return json(res,200,model);}
   const files={'/':'index.html','/app.js':'app.js','/i18n.js':'i18n.js','/mascot.svg':'mascot.svg','/style.css':'style.css'};if(!files[path])return json(res,404,{error:'Not found'});
   res.writeHead(200,{'Content-Type':path.endsWith('.js')?'text/javascript; charset=utf-8':path.endsWith('.css')?'text/css; charset=utf-8':path.endsWith('.svg')?'image/svg+xml':'text/html; charset=utf-8','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'self'; connect-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'"});return res.end(readFileSync(join(root,'public',files[path])));
  }
  if(req.method!=='POST')return json(res,405,{error:'Method not allowed'});
  const b=await body(req);
  const credential=req.headers['x-noah-token'];
  const authorized=publicIngress?(path==='/api/nodes/join'?credential===joinToken:nodeTokens.has(b.id)&&nodeTokens.get(b.id)===credential):credential===token||(nodePaths.has(path)&&path!=='/api/nodes/join'&&nodeTokens.has(b.id)&&nodeTokens.get(b.id)===credential);
  if(!authorized)return json(res,403,{error:'Unauthorized'});
  if(path==='/api/training') {if(typeof b.active!=='boolean')throw Error('Invalid state');active=b.active;if(Number.isInteger(b.duty)&&b.duty>=5&&b.duty<=50)duty=b.duty;event(active?'训练任务已开放。':'训练已暂停；不会接受新的参数更新。');if(!active)save();return json(res,200,{ok:true});}
  if(path==='/api/worker') {if(b.start===true){if(b.consent!==true)throw Error('Explicit consent required');startWorker();}else stopWorker();return json(res,200,{ok:true});}
  if(path==='/api/nodes/join') {if(nodes.size>=100)throw Error('Node limit reached');const id=randomUUID(),accessToken=randomBytes(32).toString('hex');nodeTokens.set(id,accessToken);nodes.set(id,{id,name:String(b.name||'Windows 节点').slice(0,80),cpu:String(b.cpu||'CPU').slice(0,120),threads:Number(b.threads)||1,lastSeen:Date.now(),batches:0,computeMs:0});if(b.managed&&worker&&!publicIngress)workerNode=id;event('节点自愿接入：'+nodes.get(id).name);return json(res,200,{id,accessToken});}
  if(path==='/api/nodes/leave') {const node=nodes.get(b.id);if(node)node.lastSeen=0;return json(res,200,{ok:true});}
  if(path==='/api/tasks/next') {
   const node=nodes.get(b.id);if(!node)return json(res,404,{error:'Unknown node'});node.lastSeen=Date.now();
   for(const [id,job]of jobs)if(Date.now()-job.created>60000)jobs.delete(id);
   if(!active||[...jobs.values()].some(j=>j.node===b.id))return json(res,200,{job:null});
   if(jobs.size>=8)return json(res,200,{job:null});
   const id=randomUUID(),positions=Array.from({length:32},()=>context+Math.floor(random()*(trainIds.length-context)));
   jobs.set(id,{node:b.id,version:model.step,created:Date.now()});return json(res,200,{job:id,model,ids:trainIds,positions,duty});
  }
  if(path==='/api/tasks/result') {
   const job=jobs.get(b.job),node=nodes.get(b.id);if(!job||job.node!==b.id||!node)return json(res,400,{error:'Unknown job'});jobs.delete(b.job);node.lastSeen=Date.now();
   if(!active||job.version!==b.version||model.step-job.version>4)return json(res,200,{accepted:false,reason:'Paused or stale'});
   if(!Number.isFinite(b.loss)||b.loss<0||b.loss>100)throw Error('Invalid loss');
   const candidate=applyGradient(model,b.gradient),nextLoss=lossOf(candidate);
   if(!Number.isFinite(nextLoss)||nextLoss>validationLoss+.25)return json(res,200,{accepted:false,reason:'Validation guard'});
   model=candidate;validationLoss=nextLoss;accepted++;node.batches++;node.computeMs+=Math.max(0,Math.min(60000,Number(b.duration)||0));history.push({step:model.step,loss:nextLoss});if(history.length>200)history.shift();if(model.step%10===0)save();return json(res,200,{accepted:true,step:model.step});
  }
  if(path==='/api/sample') {const prompt=String(b.prompt||'问：').slice(0,200);return json(res,200,{text:sample(model,prompt,100),step:model.step,experimental:true});}
  if(path==='/api/chat') {
   if(!Array.isArray(b.messages)||b.messages.length>25)throw Error('Invalid conversation');
   const messages=b.messages.map(m=>{if(!['user','assistant'].includes(m.role)||typeof m.content!=='string'||m.content.length>12000)throw Error('Invalid message');return {role:m.role,content:m.content};});
   const prompt=messages.at(-1)?.content||'';
   return json(res,200,{text:sample(model,prompt,100),step:model.step,experimental:true,source:'Noah historical MLP baseline / own random initialization'});
  }
  return json(res,404,{error:'Not found'});
 }catch(error){json(res,400,{error:error.message});}
};
const server=http.createServer(handler);
const contributorServer=publicPort?http.createServer(handler):null;
if(contributorServer)contributorServer.listen(publicPort,'127.0.0.1',()=>console.log(`Contributor ingress on 127.0.0.1:${publicPort}; use an HTTPS reverse proxy.`));
server.listen(port,'127.0.0.1',()=>console.log(`Noah本机原型：http://${host}\n仅本机访问；没有公网节点；不会自动启动训练。`));
function shutdown(){active=false;stopWorker();save();contributorServer?.close();server.close(()=>process.exit(0));setTimeout(()=>process.exit(0),1000).unref();}
process.on('SIGINT',shutdown);process.on('SIGTERM',shutdown);
