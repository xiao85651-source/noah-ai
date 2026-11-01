# Cloud coordinator deployment

The code supplies a Python cloud edge, Docker source and an explicit Python Nixpacks configuration. The account's free test service is `https://noah-research-test.dockhosting.dev`; verify `/healthz` after each deployment before claiming a version is live. The existing Cloudflare website remains browser-local inference; the old `noah-ai.xiao85651.workers.dev` address is a retained earlier deployment. The current chat site is `https://zenithsmart.xin/`.

## What is exposed

Run `python -m training.cloud` on a host that terminates valid HTTPS. `/healthz` and the exact member identity routes under `/api/auth/` are public; see [AUTH.md](AUTH.md) for Google verification and origin restrictions. The management UI and management APIs require a distinct, strong owner HTTP Basic credential; the browser then also obtains the coordinator's own rotating session token. Foreign browser origins are rejected. Installed invited contributors use only the exact four node protocol routes, with their existing invite/node credentials; they cannot use those credentials to obtain an owner session. Passwords and invitations are not logged or committed.

The edge listens on the host-provided `PORT`, default 10000, while the coordinator's admin and contributor listeners stay on internal loopback ports. Do not expose those loopback ports separately. The source includes an isolated real HTTP test of owner/node separation and storage-mode restrictions.

This remains a supervised trusted-tester pilot. It does not yet provide open-registration poisoning resistance, independent recomputation, participant revocation, signed client distribution or production abuse controls. Put it behind platform TLS, request/connection limits and monitoring before invited internet tests; do not advertise an unrestricted global training network.

## Free connectivity test

Set these environment values in the hosting platform, not in frontend code or Git:

```text
NOAH_CLOUD_ORIGIN=https://<the-actual-assigned-hostname>
NOAH_PROFILE=research-v1
NOAH_DATA=/tmp/noah-research-test
NOAH_STORAGE_MODE=ephemeral-test
NOAH_OWNER_USER=owner
NOAH_OWNER_PASSWORD=<a-new-random-secret-at-least-32-characters>
NOAH_JOIN_TOKEN=<a-different-random-secret-at-least-32-characters>
```

Native Python build command:

```sh
pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements.txt
```

Start command: `python -m training.cloud`. Select Python 3.12. Use `/healthz` as a health path where supported. The startup values must use the actual HTTPS origin, without a path or trailing slash. On Render, `NOAH_CLOUD_ORIGIN` may be omitted initially: the server reads the actual platform-assigned `RENDER_EXTERNAL_URL`, documented in [Render's default environment variables](https://render.com/docs/environment-variables). It does not guess a hostname. Set an explicit origin before changing to a custom domain. Keep the service on the free plan for this test; creating this configuration does not authorize purchasing an upgraded plan or disk.

In `ephemeral-test` mode **training POST operations and contributor registration are disabled**. Member sign-in and sign-out remain available. The owner can check connection, UI and metadata, but this mode is not a substitute for persistent training. The UI displays this restriction. Render's [free-instance documentation](https://render.com/docs/free) states that free web services sleep after inactivity and do not support persistent disks. Its [disk documentation](https://render.com/docs/disks) explains the persistence requirements. Other hosts must be checked for their own terms.

For mixed Python/web repositories, `nixpacks.toml` explicitly selects the Python provider, creates a Python 3.12 environment, installs the official CPU PyTorch wheel, and starts the authenticated cloud edge. It avoids automatically choosing `npm start` for the coordinator. When a platform offers explicit networking fields, set port `10000` and health path `/healthz`. Keep memory and plan unchanged unless the owner approves a priced change. The Docker source also includes curl for platform readiness checks. See the [Nixpacks file reference](https://nixpacks.com/docs/configuration/file) and [Python provider](https://nixpacks.com/docs/providers/python).

## Persistent invited pilot

After the owner has approved a concrete provider/plan/budget, provision a persistent volume, verify write permissions and backup/restore, use a new or deliberately migrated data directory, and set `NOAH_DATA` to that volume and `NOAH_STORAGE_MODE=persistent`. The code cannot prove that an operator's configured path is actually durable; the platform configuration and a restart/restore check must verify it. Training starts paused after each restart. The owner starts a bounded session explicitly; contributors start their own installed clients voluntarily.

Use the assigned HTTPS hostname first. Only after its authentication, contributor protocol, persistence and restart checks pass should `compute.zenithsmart.xin` be pointed to it. The root chat site's existing route should remain independent.

For Docker, build this repository's `Dockerfile`; mount a directory writable by UID 10001 for `NOAH_DATA`. Docker is not installed in the current Windows workspace, so the image build itself has not been exercised. Python entry points, transport boundaries and model training were tested locally. Do not treat a successful local Python test as a verified Linux image deployment.

Keep backups and operational credentials outside the private source archive. See `deploy/cloud.env.example` for names only; placeholder secrets deliberately fail startup validation.
