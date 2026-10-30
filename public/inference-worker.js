import {NoahBrowser} from './browser-model.js';
let ready;
async function load(){
 const [info,response]=await Promise.all([fetch('/noah-web.json',{cache:'no-cache'}),fetch('/noah-web.bin',{cache:'no-cache'})]);
 if(!info.ok||!response.ok)throw Error('Noah weights could not be loaded');
 const manifest=await info.json(),buffer=await response.arrayBuffer();
 const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',buffer)),b=>b.toString(16).padStart(2,'0')).join('');
 if(digest!==manifest.sha256)throw Error('Noah model checksum mismatch');
 return new NoahBrowser(manifest,buffer);
}
self.addEventListener('message',async event=>{
 const {id,prompt}=event.data;
 try{if(typeof prompt!=='string'||prompt.length>600)throw Error('Invalid prompt');ready??=load();const model=await ready;self.postMessage({id,result:{text:model.generate(prompt),step:model.meta.step,experimental:true,source:'Noah / own browser-local weights'}});}
 catch(error){ready=undefined;self.postMessage({id,error:error.message});}
});
