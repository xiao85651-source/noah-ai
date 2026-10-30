// A small, real character-level neural language model; not a general assistant.
export const context = 6, embedding = 12, hidden = 48;
export function seeded(seed=17) { return () => { seed=(Math.imul(seed,1664525)+1013904223)>>>0; return seed/4294967296; }; }
export function createModel(text) {
  const vocab=['�',...new Set(Array.from(text).filter(c=>c!=='�'))];
  const random=seeded(), v=vocab.length;
  const init=(n,scale)=>Array.from({length:n},()=> (random()*2-1)*scale);
  return {format:'noah-tiny-v1',vocab,context,embedding,hidden,step:0,
    E:init(v*embedding,.1),W:init(context*embedding*hidden,.08),b:Array(hidden).fill(0),U:init(hidden*v,.08),c:Array(v).fill(0)};
}
export const keys=['E','W','b','U','c'];
export function encode(m,text) { const ids=new Map(m.vocab.map((c,i)=>[c,i])); return Array.from(text,c=>ids.get(c)??0); }
function forward(m,ids) {
  const v=m.vocab.length,d=context*embedding,x=new Float64Array(d),h=new Float64Array(hidden),p=new Float64Array(v);
  for(let j=0;j<context;j++) for(let k=0;k<embedding;k++) x[j*embedding+k]=m.E[ids[j]*embedding+k];
  for(let k=0;k<hidden;k++) { let z=m.b[k];for(let j=0;j<d;j++)z+=x[j]*m.W[j*hidden+k];h[k]=Math.tanh(z); }
  let max=-Infinity;
  for(let t=0;t<v;t++) {let z=m.c[t];for(let k=0;k<hidden;k++)z+=h[k]*m.U[k*v+t];p[t]=z;max=Math.max(max,z);}
  let sum=0;for(let t=0;t<v;t++){p[t]=Math.exp(p[t]-max);sum+=p[t];}for(let t=0;t<v;t++)p[t]/=sum;
  return {x,h,p};
}
export function batch(m,ids,positions,withGradient=true) {
  const v=m.vocab.length,d=context*embedding,g=withGradient?Object.fromEntries(keys.map(k=>[k,new Float64Array(m[k].length)])):null;
  let loss=0;
  for(const pos of positions) {
    const input=ids.slice(pos-context,pos),target=ids[pos],{x,h,p}=forward(m,input);
    loss-=Math.log(Math.max(p[target],1e-12));if(!withGradient)continue;
    p[target]-=1;const dh=new Float64Array(hidden),dx=new Float64Array(d);
    for(let t=0;t<v;t++) {g.c[t]+=p[t];for(let k=0;k<hidden;k++){g.U[k*v+t]+=h[k]*p[t];dh[k]+=m.U[k*v+t]*p[t];}}
    for(let k=0;k<hidden;k++){const dz=dh[k]*(1-h[k]*h[k]);g.b[k]+=dz;for(let j=0;j<d;j++){g.W[j*hidden+k]+=x[j]*dz;dx[j]+=m.W[j*hidden+k]*dz;}}
    for(let j=0;j<context;j++)for(let k=0;k<embedding;k++)g.E[input[j]*embedding+k]+=dx[j*embedding+k];
  }
  if(g)for(const k of keys)g[k]=Array.from(g[k],n=>n/positions.length);
  return {loss:loss/positions.length,gradient:g};
}
export function applyGradient(m,g,rate=.2) {
  let norm=0;for(const k of keys){if(!Array.isArray(g[k])||g[k].length!==m[k].length)throw Error('Invalid gradient shape');for(const n of g[k]){if(!Number.isFinite(n)||Math.abs(n)>100)throw Error('Invalid gradient value');norm+=n*n;}}
  const scale=Math.min(1,1/(Math.sqrt(norm)||1));
  const next={...m,step:m.step+1};for(const k of keys)next[k]=m[k].map((n,i)=>n-rate*scale*g[k][i]);return next;
}
export function sample(m,prompt,length=100,temperature=.7,random=Math.random) {
  let ids=encode(m,prompt);while(ids.length<context)ids.unshift(0);let output='';
  for(let n=0;n<length;n++) {const {p}=forward(m,ids.slice(-context));let total=0;for(let i=0;i<p.length;i++){p[i]=Math.pow(p[i],1/temperature);total+=p[i];}let r=random()*total,id=p.length-1;for(let i=0;i<p.length;i++){r-=p[i];if(r<=0){id=i;break;}}ids.push(id);output+=m.vocab[id];}
  return output;
}
