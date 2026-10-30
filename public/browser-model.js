// Noah causal Transformer inference. Same layer layout and weights as training/model.py.
const erf=x=>{const sign=x<0?-1:1,a=Math.abs(x),t=1/(1+.3275911*a);return sign*(1-(((((1.061405429*t-1.453152027)*t)+1.421413741)*t-.284496736)*t+.254829592)*t*Math.exp(-a*a));};
export class NoahBrowser{
 constructor(manifest,buffer){
  this.meta=manifest;this.c=manifest.config;
  if(manifest.format!=='noah-browser-v1'||this.c.vocab!==259||this.c.width>256||this.c.context>512||this.c.layers>6||this.c.width%this.c.heads||buffer.byteLength!==manifest.parameters*4)throw Error('Invalid Noah model');
  const values=new Float32Array(buffer);this.weights={};
  for(const [name,tensor]of Object.entries(manifest.tensors)){if(tensor.offset<0||tensor.length<1||tensor.offset+tensor.length>values.length)throw Error('Invalid tensor');this.weights[name]=values.subarray(tensor.offset,tensor.offset+tensor.length);}
  this.reset();
 }
 reset(){this.position=0;this.cache=Array.from({length:this.c.layers},()=>({keys:[],values:[]}));}
 linear(x,name,rows,bias=true){const weight=this.weights[name+'.weight'],b=this.weights[name+'.bias'],out=new Float32Array(rows);if(!weight||weight.length!==rows*x.length)throw Error('Weight shape mismatch');for(let i=0;i<rows;i++){let sum=bias?b[i]:0;const offset=i*x.length;for(let j=0;j<x.length;j++)sum+=weight[offset+j]*x[j];out[i]=sum;}return out;}
 norm(x,name){let mean=0;for(const value of x)mean+=value;mean/=x.length;let variance=0;for(const value of x)variance+=(value-mean)**2;const scale=1/Math.sqrt(variance/x.length+1e-5),out=new Float32Array(x.length),w=this.weights[name+'.weight'],b=this.weights[name+'.bias'];for(let i=0;i<x.length;i++)out[i]=(x[i]-mean)*scale*w[i]+b[i];return out;}
 forward(token){
  const {width:C,heads:H,layers:L,context}=this.c,position=this.position++;
  if(!Number.isInteger(token)||token<0||token>=259||position>=context)throw Error('Invalid token/context');
  let x=new Float32Array(C);const embeddings=this.weights.token_embedding_weight||this.weights['token_embedding.weight'],positions=this.weights['position_embedding.weight'];
  for(let i=0;i<C;i++)x[i]=embeddings[token*C+i]+positions[position*C+i];
  for(let layer=0;layer<L;layer++){
   const prefix='blocks.'+layer,cache=this.cache[layer],qkv=this.linear(this.norm(x,prefix+'.norm1'),prefix+'.attention.qkv',C*3),q=qkv.subarray(0,C),k=qkv.subarray(C,C*2),v=qkv.subarray(C*2);
   cache.keys.push(k);cache.values.push(v);const attended=new Float32Array(C),D=C/H;
   for(let head=0;head<H;head++){
    const scores=new Float64Array(cache.keys.length),start=head*D;let maximum=-Infinity;
    for(let t=0;t<scores.length;t++){let dot=0;for(let d=0;d<D;d++)dot+=q[start+d]*cache.keys[t][start+d];scores[t]=dot/Math.sqrt(D);maximum=Math.max(maximum,scores[t]);}
    let denominator=0;for(let t=0;t<scores.length;t++){scores[t]=Math.exp(scores[t]-maximum);denominator+=scores[t];}
    for(let d=0;d<D;d++){let sum=0;for(let t=0;t<scores.length;t++)sum+=scores[t]/denominator*cache.values[t][start+d];attended[start+d]=sum;}
   }
   const attention=this.linear(attended,prefix+'.attention.output',C);for(let i=0;i<C;i++)x[i]+=attention[i];
   const hidden=this.linear(this.norm(x,prefix+'.norm2'),prefix+'.mlp.0',C*4);for(let i=0;i<hidden.length;i++)hidden[i]=.5*hidden[i]*(1+erf(hidden[i]/Math.SQRT2));
   const feed=this.linear(hidden,prefix+'.mlp.2',C);for(let i=0;i<C;i++)x[i]+=feed[i];
  }
  const normalized=this.norm(x,'norm'),logits=new Float32Array(259),weight=this.weights['token_embedding.weight'];
  for(let token=0;token<259;token++){let sum=0;for(let i=0;i<C;i++)sum+=normalized[i]*weight[token*C+i];logits[token]=sum;}return logits;
 }
 generate(prompt,count=64){
  this.reset();const tokens=[256,...new TextEncoder().encode(prompt)].slice(-Math.floor(this.c.context/2));let logits;
  for(const token of tokens)logits=this.forward(token);
  const output=[],limit=Math.min(count,this.c.context-tokens.length,64);
  for(let index=0;index<limit;index++){
   const top=Array.from(logits,(score,token)=>({score:score/.8,token})).filter(item=>item.token!==256&&item.token!==258).sort((a,b)=>b.score-a.score).slice(0,40);
   const probabilities=top.map(item=>Math.exp(item.score-top[0].score));let random=Math.random()*probabilities.reduce((a,b)=>a+b,0),chosen=top.at(-1).token;
   for(let i=0;i<top.length;i++){random-=probabilities[i];if(random<=0){chosen=top[i].token;break;}}
   if(chosen===257)break;output.push(chosen);if(index<limit-1)logits=this.forward(chosen);
  }
  return new TextDecoder().decode(new Uint8Array(output))||'…';
 }
}
