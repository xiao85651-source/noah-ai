# Noah local verification

Verified on Windows with CPU PyTorch 2.15.0+cpu, NumPy 2.3.5 and Node 24.22.1. GPU and real internet contributors were not exercised.

## Automated checks

`Check.cmd` / `python -m unittest training.test_training training.test_http -v`: **5 tests passed**. The isolated HTTP lifecycle test uses the actual Transformer runtime, its optional contributor ingress and a real installed worker subprocess. Verified:

1. Coordinator starts paused and without a worker.
2. Missing consent cannot start a managed worker; invalid credentials/origins fail.
3. Invited contributors receive separate node credentials. The contributor ingress rejects management/session routes.
4. A contributor downloads a real task, computes gradients and advances the model; duplicate submission is rejected.
5. A managed CPU contributor starts with explicit consent and produces an additional accepted update.
6. Training pauses and contribution stops.
7. Weight export is a loadable Noah checkpoint. Sample and chat endpoints generate from the current Noah weights.
8. Coordinator restart restores the saved step and validation loss, with training paused and no worker.

`node --test tests/*.test.mjs`: **6 tests passed**. Includes five-locale UI key coverage, no external model endpoint, numerical gradient checks, historical MLP learning and the historical HTTP lifecycle.

## Reproducible model artifact

`checkpoints/noah-seed.npz`: own 644,608-parameter causal Transformer, 100 CPU steps from random weights, seed 17. Held-out byte-level cross entropy: **5.5832389832 → 3.1773824215** on the tiny original seed corpus.

SHA-256: `209f8fae53f666007221d8ef9a8ff16fe6aa31eaca2125011b3bb5661baee6a5`.

This verifies a training system and its own weights. It does not establish useful assistant performance, multilingual proficiency or comparable capability to a frontier model.

## Deployment boundary

The administration app is local on port 4317. The optional contributor ingress is loopback-only, intended for a separately provisioned HTTPS proxy. The supplied domain has not been deployed or reconfigured. No claim is made that global volunteers, a production installer or free public inference are already operating.
