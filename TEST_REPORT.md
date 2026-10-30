# Noah local verification

Verified on Windows with CPU PyTorch 2.15.0+cpu, NumPy 2.3.5 and Node 24.22.1. GPU and real internet contributors were not exercised.

## Automated checks

`Check.cmd` / `python -m unittest training.test_training training.test_http training.test_gateway -v`: **6 tests passed**. The isolated HTTP lifecycle test uses the actual Transformer runtime, its optional contributor ingress and a real installed worker subprocess. Verified:

1. Coordinator starts paused and without a worker.
2. Missing consent cannot start a managed worker; invalid credentials/origins fail.
3. Invited contributors receive separate node credentials. The contributor ingress rejects management/session routes.
4. A contributor downloads a real task, computes gradients and advances the model; duplicate submission is rejected.
5. A managed CPU contributor starts with explicit consent and produces an additional accepted update.
6. Training pauses and contribution stops.
7. Weight export is a loadable Noah checkpoint. Sample and chat endpoints generate from the current Noah weights.
8. Coordinator restart restores the saved step and validation loss, with training paused and no worker.

The public-gateway HTTP test also loads the published seed, generates actual output twice, rejects management/training/source-code routes, rejects a foreign origin and malformed/oversized prompts, and returns HTTP 429 with Retry-After after the configured request budget is exhausted.

`node --test tests/*.test.mjs`: **6 tests passed**. Includes five-locale UI key coverage, no external model endpoint, numerical gradient checks, historical MLP learning and the historical HTTP lifecycle.

## Reproducible model artifact

`checkpoints/noah-seed.npz`: own 644,608-parameter causal Transformer, 100 CPU steps from random weights, seed 17. Held-out byte-level cross entropy: **5.5832389832 → 3.1773824215** on the tiny original seed corpus.

SHA-256: `209f8fae53f666007221d8ef9a8ff16fe6aa31eaca2125011b3bb5661baee6a5`.

This verifies a training system and its own weights. It does not establish useful assistant performance, multilingual proficiency or comparable capability to a frontier model.

## Deployment boundary

Browser verification: five languages switch correctly, Arabic uses RTL, and desktop layout has no horizontal overflow. Companion expansion, greeting and pause were exercised. The local contributor UI advanced the owner's working checkpoint from 134 to **325** steps, then paused and stopped the worker. Validation loss at step 325 was **3.0331** on the same tiny corpus. The UI downloaded a loadable 325-step checkpoint and produced raw text through both sample and chat controls. Outputs remain incoherent research samples.

The administration app is local on port 4317. The optional contributor ingress on 4318 is loopback-only, intended for a separately provisioned HTTPS proxy. The distinct public inference process on 4319 is locally tested. The supplied domain has not been deployed or reconfigured; the owner currently has no server. No claim is made that global volunteers, a production installer or free public inference are already operating.
