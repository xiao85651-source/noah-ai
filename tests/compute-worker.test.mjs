import test from 'node:test';
import assert from 'node:assert/strict';
import {handle, UPSTREAM, PUBLIC_ORIGIN} from '../deploy/compute-worker.mjs';

const request = (path='/', init={}) => new Request(PUBLIC_ORIGIN+path, init);
test('gateway keeps credentials on the fixed origin and strips cookies and spoofed routing headers', async () => {
  let called = 0;
  const response = await handle(request('//attacker.example/api/status?url=https://attacker.example', {headers: {
    Authorization:'Basic test-only', Origin:PUBLIC_ORIGIN, Cookie:'private=secret',
    'X-Noah-Token':'test-session', 'X-Forwarded-Host':'attacker.example'
  }}), async (url, options) => {
    called++;
    assert.equal(new URL(url).origin, UPSTREAM);
    assert.equal(options.redirect, 'manual');
    assert.equal(options.headers.get('Authorization'), 'Basic test-only');
    assert.equal(options.headers.get('Origin'), UPSTREAM);
    assert.equal(options.headers.get('X-Noah-Token'), 'test-session');
    assert.equal(options.headers.has('Cookie'), false);
    assert.equal(options.headers.has('X-Forwarded-Host'), false);
    return new Response('{}', {headers:{'Set-Cookie':'provider=secret','Cache-Control':'public,max-age=999'}});
  });
  assert.equal(called,1); assert.equal(response.status,200);
  assert.equal(response.headers.get('Cache-Control'),'no-store');
  assert.equal(response.headers.has('Set-Cookie'),false);
});

test('foreign origins and main-site owner requests never reach the backend', async () => {
  const never = () => { throw Error('must not reach upstream'); };
  for (const origin of ['https://attacker.example', 'null', 'https://zenithsmart.xin']) {
    assert.equal((await handle(request('/api/status',{headers:{Origin:origin}}),never)).status,403);
  }
  assert.equal((await handle(new Request('https://attacker.example/'),never)).status,421);
  assert.equal((await handle(request('/',{method:'DELETE'}),never)).status,405);
});

test('member CORS is preserved without granting owner access', async () => {
  for (const origin of [PUBLIC_ORIGIN,'https://zenithsmart.xin']) {
    const response=await handle(request('/api/auth/config',{headers:{Origin:origin}}), async (_, options) => {
      const expected=origin===PUBLIC_ORIGIN?UPSTREAM:origin;
      assert.equal(options.headers.get('Origin'),expected);
      return new Response('{}',{headers:{'Access-Control-Allow-Origin':expected}});
    });
    assert.equal(response.headers.get('Access-Control-Allow-Origin'),origin);
  }
});

test('upstream authentication and read-only denial survive the gateway', async () => {
  const unauth=await handle(request(),async()=>new Response('{}',{status:401,headers:{'WWW-Authenticate':'Basic realm="Noah owner"'}}));
  assert.equal(unauth.status,401); assert.match(unauth.headers.get('WWW-Authenticate'),/Noah owner/);
  const denied=await handle(request('/api/train/start',{method:'POST',headers:{'Content-Length':'2'},body:'{}'}), async (_,options)=>{
    assert.equal(new TextDecoder().decode(options.body),'{}');
    assert.equal(options.headers.get('Content-Length'),'2');
    return new Response('{"error":"training disabled"}',{status:403});
  });
  assert.equal(denied.status,403); assert.match(await denied.text(),/training disabled/);
});

test('redirects, oversized bodies and transport failure fail closed', async () => {
  const never=()=>{throw Error('unexpected upstream call');};
  assert.equal((await handle(request('/',{method:'POST',body:'{}'}),never)).status,411);
  assert.equal((await handle(request('/',{method:'POST',headers:{'Content-Length':String(25*1024*1024)},body:'{}'}),never)).status,413);
  assert.equal((await handle(request('/',{method:'POST',headers:{'Content-Length':'1'},body:'{}'}),never)).status,400);
  let calls=0;
  const redirect=await handle(request(),async()=>{calls++;return new Response(null,{status:302,headers:{Location:'https://attacker.example'}});});
  assert.equal(redirect.status,502);assert.equal(calls,1);
  assert.equal((await handle(request(),async()=>{throw Error('timeout');})).status,503);
});
