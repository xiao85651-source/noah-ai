# Invited remote contribution

Default: no public listener. The local administration UI stays on `127.0.0.1:4317`.

On a server you control:

```powershell
$env:NOAH_PUBLIC_PORT = '4318'
$env:NOAH_JOIN_TOKEN = '<random invitation of at least 32 characters>'
python -m training.coordinator
```

The contributor listener binds only to `127.0.0.1:4318`. Put it behind a real HTTPS reverse proxy. Never forward the admin listener to the public internet. See `deploy/Caddyfile`.

On an authorized contributor's Windows computer:

```powershell
$env:NOAH_URL = 'https://compute.zenithsmart.xin'
$env:NOAH_NODE_TOKEN = '<invitation supplied privately by the owner>'
$env:NOAH_NODE_NAME = 'A public name I choose'
.\Contribute.ps1 -Device cpu
```

This hostname is a proposed deployment address, **not an already configured service**. DNS and hosting have not been changed. Remote URLs must be HTTPS. Invites create distinct node credentials; a node cannot use its token for another node or the administration API. Restarting the coordinator invalidates node sessions; clients retry registration using their invitation.

Only installed source code executes. Network messages contain model tensors, public token data, job IDs, gradients, loss, device description and client-reported duration. User chats and personal files are not collected. The request format uses compressed NumPy arrays with `allow_pickle=False`, bounded archive sizes and explicit tensor-shape checks.

This is a trusted-tester protocol. It still needs per-participant invitation management/revocation, rate limits, independent result recomputation, poisoning resistance, robust network-failure recovery and signed client releases before broad public participation. Whole-model transfer per batch is useful for this small experiment and will not scale directly to a large model.
