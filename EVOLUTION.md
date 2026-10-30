# Noah 自动迭代 / Measured weight iteration

This feature automates bounded model training and version selection. It does not rewrite source code, invent new knowledge, crawl the web or guarantee a more capable assistant.

## Use

Open the local management app with `Start.cmd`, select **自动迭代 / Model iteration**, read the resource notice, volunteer this computer's CPU and start a session. This starts the existing installed CPU contributor if one is not running. Other invited voluntary nodes use the same task/gradient protocol. Training remains paused after coordinator restart; prior releases and reports remain available.

Default session: review every 25 accepted training steps, at most 75 steps or 30 minutes. A management client may choose 5–200 steps between reviews, up to 1,000 total accepted steps and 1–120 minutes. The ordinary contributor duty setting applies to the local client; it is an approximate duty cycle, not an OS limit. The automation stops opening tasks at the budget and stops its own managed contributor. A contributor that was already running remains under its existing owner's control.

## Gate and release

The fixed validation corpus and separately authored `training/audit.jsonl` are never used as gradient-training documents. Scores are mean language-level losses over fixed beginning/end windows. A candidate is promoted only if validation loss improves by at least 0.2%, aggregate audit loss increases by no more than 1%, and no evaluated language regresses by more than 3% on either suite. All measurements must be finite. Candidate artifacts, decisions, source hashes and parent IDs are saved under `data/releases/`. Rejected candidates do not replace the current serving version.

These small, repeatedly consulted development suites are regression gates, not independent general-capability benchmarks. Repeated optimization against them can overfit. Larger authorized datasets and genuinely independent human/task evaluations are necessary for capability claims. Source dependency checks and tests remain separate from model-weight evaluation.

The current pointer changes atomically after writing/checking a release. `PublicChat.cmd` enables following accepted releases; a valid new model is loaded at the next request under a serving lock. Checksum or load errors keep the previous in-memory model. The rollback control selects the prior accepted serving release. Working training weights are kept separately so a serving rollback does not silently erase training history. Nothing is automatically deleted or uploaded from private runtime data.

## Static browser deployment

`python -m training.export_web --release-dir data/releases` exports the selected accepted serving weights to `checkpoints/noah-web.bin` and `noah-web.json`. Run `node --test tests/*.test.mjs` to verify browser logits against the PyTorch reference, then `node build-web.mjs` to build the public static app. Only the public weight artifacts and frontend are copied to `dist/`; management APIs, source training data and credentials are excluded.

The static browser app runs Noah inference in a Web Worker on the visitor's device. It uses at most half the model context for the prefix and generates up to 64 bytes without crossing the context bound. Published model weights are downloadable public assets by design. Chat text is not submitted to the training coordinator. Publishing a new static weight bundle still requires updating the deployment; local hot reload updates the Python gateway only. No claim is made that a private GitHub repository has become a globally operating training network.
