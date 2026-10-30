import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {translations,locales} from '../public/i18n.js';
test('all five languages cover static and dynamic UI keys',()=>{
 const html=['index.html','chat.html'].map(path=>readFileSync(new URL('../public/'+path,import.meta.url),'utf8')).join('\n');
 const app=['app.js','chat.js'].map(path=>readFileSync(new URL('../public/'+path,import.meta.url),'utf8')).join('\n');
 const required=[...html.matchAll(/data-i18n(?:-placeholder)?="([^"]+)"/g)].map(m=>m[1]);
 const dynamic=[...app.matchAll(/\bt\('([^']+)'\)/g)].map(m=>m[1]);
 assert.equal(locales.length,5);
 for(const locale of locales)for(const key of [...required,...dynamic])assert.ok(translations[locale][key],`${locale}: ${key}`);
});
test('Noah UI and runtime do not call external model endpoints',()=>{
 const server=readFileSync(new URL('../server.mjs',import.meta.url),'utf8');
 const transformer=readFileSync(new URL('../training/coordinator.py',import.meta.url),'utf8');
 assert.ok(!server.includes('11439'));
 assert.ok(!transformer.includes('from_pretrained'));
 assert.match(transformer,/self\.model\.generate/);
});
