let config,worker,sequence=0;
const pending=new Map();
export async function infer(prompt,language){
 config??=fetch('/runtime.json').then(response=>{if(!response.ok)throw Error('Runtime unavailable');return response.json();});
 if((await config).mode==='browser'){
  if(!worker){worker=new Worker(new URL('./inference-worker.js',import.meta.url),{type:'module'});worker.addEventListener('message',event=>{const job=pending.get(event.data.id);if(!job)return;pending.delete(event.data.id);clearTimeout(job.timer);event.data.error?job.reject(Error(event.data.error)):job.resolve(event.data.result);});worker.addEventListener('error',()=>{for(const job of pending.values()){clearTimeout(job.timer);job.reject(Error('Local inference unavailable'));}pending.clear();worker.terminate();worker=null;});}
  return new Promise((resolve,reject)=>{const id=++sequence,timer=setTimeout(()=>{pending.delete(id);worker?.terminate();worker=null;reject(Error('Local inference timed out'));},60000);pending.set(id,{resolve,reject,timer});worker.postMessage({id,prompt});});
 }
 const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:[{role:'user',content:prompt}],language}),signal:AbortSignal.timeout(30000)});
 if(!response.ok){const error=Error('Chat unavailable');error.status=response.status;throw error;}return response.json();
}
