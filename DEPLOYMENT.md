# Domain and public deployment

`zenithsmart.xin` is supplied by the owner. On 2026-10-30 it returned an existing Vercel site titled `SunnyGuard AI ☀️`. Noah has not replaced that site or changed its DNS.

The proposed production split is:

- `zenithsmart.xin` or a chosen subdomain: public multilingual chat frontend.
- A separately operated inference gateway: serves only Noah's own published weights, with queueing and rate limits.
- `compute.zenithsmart.xin`: contributor-only HTTPS ingress, after the owner provides DNS and a persistent server.
- Local/private management: scheduling, training control, checkpoint access and credentials. Never publish `/api/session` or local process controls.

The current browser app is an administrator prototype. Its training buttons can start local worker processes, and its session token is available to the same-machine frontend. It must not be reverse-proxied wholesale to a public hostname.

The supplied Caddy configuration forwards only the restricted contribution listener. It does not provision a domain, purchase hosting or launch a globally available free AI. GitHub hosts source, issues and releases; the training coordinator and inference need actual running machines.

Before public chat launch: implement a distinct public API surface, authentication/fair-use policy as appropriate, server-side capacity controls, inference isolation, request size/time limits and the owner's selected privacy/licensing policies. Then deploy against the existing domain only after the target project and route are confirmed.
