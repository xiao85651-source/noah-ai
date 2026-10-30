import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {NoahBrowser} from '../public/browser-model.js';
test('browser Transformer reproduces PyTorch logits from our exported weights',()=>{
 const manifest=JSON.parse(readFileSync(new URL('../checkpoints/noah-web.json',import.meta.url),'utf8'));
 const bytes=readFileSync(new URL('../checkpoints/noah-web.bin',import.meta.url));
 assert.equal(createHash('sha256').update(bytes).digest('hex'),manifest.sha256);
 const model=new NoahBrowser(manifest,bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength));
 for(const reference of manifest.referenceCases){model.reset();let logits;for(const token of reference.tokens)logits=model.forward(token);const error=Math.max(...logits.map((value,i)=>Math.abs(value-reference.logits[i])));assert.ok(error<.00003,`maximum logit error ${error}`);}
 assert.equal(typeof model.generate('Noah is',8),'string');
});
