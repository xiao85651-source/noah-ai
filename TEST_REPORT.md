# Noah local verification

Verified on Windows with CPU PyTorch 2.15.0+cpu, NumPy 2.3.5 and Node 24.22.1. GPU and real internet contributors were not exercised.

## Automated checks

`Check.cmd` / `python -m unittest training.test_training training.test_http training.test_gateway training.test_evolution -v`: **9 tests passed**. The isolated HTTP lifecycle test uses the actual Transformer runtime, its optional contributor ingress and a real installed worker subprocess. Verified:

1. Coordinator starts paused and without a worker.
2. Missing consent cannot start a managed worker; invalid credentials/origins fail.
3. Invited contributors receive separate node credentials. The contributor ingress rejects management/session routes.
4. A contributor downloads a real task, computes gradients and advances the model; duplicate submission is rejected.
5. A managed CPU contributor starts with explicit consent and produces an additional accepted update.
6. Training pauses and contribution stops.
7. Weight export is a loadable Noah checkpoint. Sample and chat endpoints generate from the current Noah weights.
8. Coordinator restart restores the saved step and validation loss, with training paused and no worker.

The public-gateway HTTP test also loads the published seed, generates actual output twice, rejects management/training/source-code routes, rejects a foreign origin and malformed/oversized prompts, and returns HTTP 429 with Retry-After after the configured request budget is exhausted.

`node --test tests/*.test.mjs`: **7 tests passed**. Includes a browser Transformer/PyTorch logit comparison (3 token prefixes, maximum allowed absolute error 0.00003), five-locale UI key coverage, no external model endpoint, numerical gradient checks, historical MLP learning and the historical HTTP lifecycle.

Evolution checks exercise real gradient updates, budget stopping, release selection and restart, checksum rejection, browser-independent Python gateway hot reload, serving rollback, per-language regression rejection, audit regression rejection and deadlines without contributors.

A real local automatic session advanced the working model from 325 to 400 steps. Reviews at steps 350, 375 and 400 failed the improvement gate, so the accepted serving version remained at 325. The session stopped at its 75-step budget; training and the automation-owned contributor stopped. Rejection is expected behavior, not a successful capability improvement.

## Reproducible model artifact

`checkpoints/noah-seed.npz`: own 644,608-parameter causal Transformer, 100 CPU steps from random weights, seed 17. Held-out byte-level cross entropy: **5.5832389832 → 3.1773824215** on the tiny original seed corpus.

SHA-256: `209f8fae53f666007221d8ef9a8ff16fe6aa31eaca2125011b3bb5661baee6a5`.

This verifies a training system and its own weights. It does not establish useful assistant performance, multilingual proficiency or comparable capability to a frontier model.

## Deployment boundary

Browser verification: five languages switch correctly, Arabic uses RTL, and desktop layout has no horizontal overflow. Companion expansion, greeting and pause were exercised. The local contributor UI advanced the owner's working checkpoint from 134 to **325** steps, then paused and stopped the worker. Validation loss at step 325 was **3.0331** on the same tiny corpus. The UI downloaded a loadable 325-step checkpoint and produced raw text through both sample and chat controls. Outputs remain incoherent research samples.

The administration app is local on port 4317. The optional contributor ingress on 4318 is loopback-only and has not been publicly deployed. The distinct Python inference process on 4319 is locally tested. The public website now runs browser-local inference at `https://zenithsmart.xin/` and `https://noah-ai.xiao85651.workers.dev/`.

Deployment: Cloudflare static-assets project `noah-ai`, dashboard release `5c13eb92`, status Ready / 100%. Both origins returned the 325-step model manifest and matching weight SHA-256 `58a1365eff1eb03fca684907c9e5f85f1a7303798ab2459193c1e42c402b8dea`. HTTPS requests used a descriptive `Noah-Deployment-Check/0.3` User-Agent; Cloudflare rejects the library default with error 1010. No safety settings were weakened. Training control and private runtime data are absent from the public static bundle.
