// Fixed-origin HTTPS gateway. No credentials, model weights or training state live here.
export const UPSTREAM = 'https://noah-research-test.dockhosting.dev';
export const PUBLIC_ORIGIN = 'https://compute.zenithsmart.xin';
const HOSTS = new Set(['compute.zenithsmart.xin', 'noah-compute.xiao85651.workers.dev']);
const AUTH_PATHS = new Set(['/api/auth/config', '/api/auth/challenge', '/api/auth/google', '/api/auth/me', '/api/auth/logout']);
const MEMBER_ORIGINS = new Set(['https://zenithsmart.xin', 'https://noah-ai-web.xiao85651.workers.dev', 'https://noah-ai.xiao85651.workers.dev']);
const MAX_BODY = 24 * 1024 * 1024;

function failure(status, error) {
  return new Response(JSON.stringify({error}), {status, headers: {
    'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff', 'X-Robots-Tag': 'noindex, nofollow'
  }});
}

export async function handle(request, fetchOrigin = fetch) {
  const incoming = new URL(request.url);
  if (incoming.protocol !== 'https:' || !HOSTS.has(incoming.host)) return failure(421, 'unknown_gateway');
  if (!['GET', 'HEAD', 'POST', 'OPTIONS'].includes(request.method)) return failure(405, 'method_not_allowed');
  if (incoming.pathname.length > 2048 || incoming.search.length > 4096) return failure(414, 'url_too_long');
  const origin = request.headers.get('Origin');
  const sameOrigin = origin === incoming.origin;
  if (origin !== null && !sameOrigin && !(AUTH_PATHS.has(incoming.pathname) && MEMBER_ORIGINS.has(origin))) {
    return failure(403, 'invalid_origin');
  }
  // Setting pathname keeps even //example.org paths on the fixed upstream host.
  const target = new URL(UPSTREAM);
  target.pathname = incoming.pathname;
  target.search = incoming.search;
  const headers = new Headers();
  for (const name of ['Accept', 'Authorization', 'Content-Type', 'X-Noah-Token', 'Access-Control-Request-Method', 'Access-Control-Request-Headers']) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  // Only this verified gateway's own origin is translated; foreign origins are never laundered.
  if (origin !== null) headers.set('Origin', sameOrigin ? UPSTREAM : origin);
  let body;
  if (request.method === 'POST') {
    const length = request.headers.get('Content-Length');
    if (length === null || !/^\d+$/.test(length)) return failure(411, 'content_length_required');
    if (Number(length) < 1 || Number(length) > MAX_BODY) return failure(413, 'request_too_large');
    try { body = await request.arrayBuffer(); } catch { return failure(400, 'invalid_body'); }
    if (body.byteLength !== Number(length) || body.byteLength > MAX_BODY) return failure(400, 'invalid_body_size');
    headers.set('Content-Length', String(body.byteLength));
  }
  let upstream;
  try {
    upstream = await fetchOrigin(target.href, {
      method: request.method === 'HEAD' ? 'GET' : request.method, headers, body,
      redirect: 'manual', cache: 'no-store', signal: AbortSignal.timeout(65000),
      cf: {cacheTtl: 0, cacheEverything: false}
    });
  } catch { return failure(503, 'coordinator_unavailable'); }
  // Never forward credentials along a provider-controlled redirect chain.
  if (upstream.status >= 300 && upstream.status < 400) {
    await upstream.body?.cancel();
    return failure(502, 'unexpected_upstream_redirect');
  }
  const responseHeaders = new Headers(upstream.headers);
  for (const name of ['Set-Cookie', 'Server', 'X-Powered-By']) responseHeaders.delete(name);
  responseHeaders.set('Cache-Control', 'no-store');
  responseHeaders.set('CDN-Cache-Control', 'no-store');
  responseHeaders.set('X-Content-Type-Options', 'nosniff');
  responseHeaders.set('X-Robots-Tag', 'noindex, nofollow');
  responseHeaders.set('Referrer-Policy', 'no-referrer');
  responseHeaders.set('Strict-Transport-Security', 'max-age=31536000');
  if (sameOrigin && responseHeaders.get('Access-Control-Allow-Origin') === UPSTREAM) {
    responseHeaders.set('Access-Control-Allow-Origin', origin);
  }
  if (request.method === 'HEAD') await upstream.body?.cancel();
  return new Response(request.method === 'HEAD' ? null : upstream.body, {status: upstream.status, headers: responseHeaders});
}

export default {fetch: request => handle(request)};
