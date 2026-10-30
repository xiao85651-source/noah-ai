# Domain and public deployment

`zenithsmart.xin` is supplied by the owner. On 2026-10-30 it returned an existing Vercel site titled `SunnyGuard AI ☀️`. Noah has not replaced that site or changed its DNS.

The proposed production split is:

- `zenithsmart.xin` or a chosen subdomain: public multilingual chat frontend.
- `training/gateway.py` on loopback port 4319: a separately operated inference gateway, using only Noah's own published weights, one inference slot, request limits and a small rate budget.
- `compute.zenithsmart.xin`: contributor-only HTTPS ingress, after the owner provides DNS and a persistent server.
- Local/private management: scheduling, training control, checkpoint access and credentials. Never publish `/api/session` or local process controls.

The browser app on port 4317 is an administrator prototype. Its training buttons can start local worker processes, and its session token is available to the same-machine frontend. It must not be reverse-proxied wholesale to a public hostname. `PublicChat.cmd` starts the distinct public-facing preview on port 4319; it has no admin routes and does not train or save chats.

The supplied Caddy configuration proposes `chat.zenithsmart.xin` for public chat and `compute.zenithsmart.xin` for invited contribution. It does not provision a domain, purchase hosting or launch a globally available free AI. GitHub hosts source, issues and releases; the training coordinator and inference need actual running machines. The owner currently has a domain but no server.

## Rehearse locally

1. `Setup.cmd` installs the environment; `Check.cmd` verifies the full isolated lifecycle.
2. `Start.cmd` opens the management service on 4317, paused by default.
3. `PublicChat.cmd` starts the separate public preview on 4319 using the published 100-step seed. To serve an exported Noah checkpoint instead, set `NOAH_CHAT_CHECKPOINT` to its absolute local path before starting this process. Restart to select new weights; training never mutates the gateway's in-memory model.
4. Use `Contribute.cmd` for a voluntary CPU client, or use the explicit-consent control in the local management UI. Stop and pause when finished.

## When a persistent server is available

Install the same CPU requirements in an isolated Python environment. Keep the management process private; administer it locally or through an authenticated SSH tunnel. Start its optional restricted contribution listener using the environment in [REMOTE.md](REMOTE.md). Run the inference gateway in a separate process:

```powershell
$env:NOAH_CHAT_HOSTS = 'chat.zenithsmart.xin'
$env:NOAH_CHAT_RPM = '10'
python -m training.gateway
```

Set DNS only after the target machine and HTTPS proxy are ready, then configure `deploy/Caddyfile`. This avoids replacing the existing apex site. The same environment variables work on Linux with that shell's export syntax. Use a service manager to restart the processes after failures/reboots; protect the private management port from public ingress.

Gateway limits: prompts are at most 600 Unicode characters and 8 KiB per request; only one generation runs at a time, with HTTP 503 for concurrent work. Per-address limits use the direct peer address and deliberately ignore untrusted forwarded headers. Behind a proxy, all visitors therefore share the configured budget; add trustworthy per-user/per-IP limits at the edge before broad access. The Python standard-library server is for a small supervised pilot; production requires a hardened proxy, connection/time limits, monitoring and measured capacity. Privacy, public licensing and contributor terms remain owner decisions.
