import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createModel,encode,batch,applyGradient,sample,seeded,keys} from '../model.mjs';
test('backpropagation matches finite differences',()=>{
 const model=createModel('abcabcabcabcabcabc'),ids=encode(model,'abcabcabcabcabcabc'),positions=[6,7,8],result=batch(model,ids,positions);
 for(const [key,index]of [['E',13],['W',50],['b',3],['U',5],['c',1]]){
  const original=model[key][index],epsilon=1e-5;
  model[key][index]=original+epsilon;const plus=batch(model,ids,positions,false).loss;
  model[key][index]=original-epsilon;const minus=batch(model,ids,positions,false).loss;model[key][index]=original;
  assert.ok(Math.abs((plus-minus)/(2*epsilon)-result.gradient[key][index])<1e-6,`${key} gradient`);
 }
});
test('real parameter updates learn a repeating sequence',()=>{
 let model=createModel('abcabcabcabcabcabc'),ids=encode(model,'abcabcabcabcabcabc');const positions=[6,7,8,9,10,11];const initial=batch(model,ids,positions,false).loss;
 for(let i=0;i<120;i++)model=applyGradient(model,batch(model,ids,positions).gradient,.3);
 assert.ok(batch(model,ids,positions,false).loss<initial*.3);
 assert.equal(model.step,120);assert.equal(sample(model,'abcabc',9,.1,seeded()),'abcabcabc');
});
test('rejects malformed and non-finite gradients before updates',()=>{
 const model=createModel('abcabcabcabc'),gradient=Object.fromEntries(keys.map(k=>[k,Array(model[k].length).fill(0)]));gradient.E[0]=NaN;
 assert.throws(()=>applyGradient(model,gradient),/Invalid gradient/);assert.equal(model.step,0);
 gradient.E=[0];assert.throws(()=>applyGradient(model,gradient),/shape/);
});
