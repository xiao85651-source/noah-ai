# Narrow arithmetic-code experiment — 2026-11-02

This experiment teaches Noah to emit `def solve(a,b)` for addition, subtraction, multiplication and division. It starts from this project's independently trained research-v1 checkpoint at step 413. No external pretrained weights or model API is used. It is a separate candidate and does not replace the local coordinator or public chat model.

The coding assistant authored 48 synthetic training examples, 16 validation prompts and 16 audit prompts. Templates are disjoint across splits; **the same four operation families appear in every split**. This measures limited wording generalization, not general coding competence or independent external evaluation. All prompts and the release gate were saved before training. After inspecting these results, future model selection must treat this audit set as development data and reserve a new final test set.

The run used 600 CPU optimizer updates, batch size 8, seed 2041, response-only cross entropy and a fresh AdamW optimizer. Training has a 600-step/300-second limit. Greedy decoding is evaluated against six input/output cases per prompt, including negative, zero and fractional inputs; division denominators are nonzero. Only the existing narrow arithmetic AST evaluator runs generated code, never unrestricted code execution.

| Split | Before | After |
|---|---:|---:|
| Validation | 0/16 | 9/16 |
| Audit | 0/16 | 5/16 |

The predeclared narrow-experiment release gate required 16/16 on **both** sets. It failed. Errors include incorrect operators and malformed Python. Low training loss did not establish reliable instruction following. No measurement supports a comparison with a frontier assistant. No candidate was deployed.

The candidate saves weights, optimizer state, random-generator states and source/dataset hashes. Reloading its weights and rerunning the audit reproduced all results. This check ran in the same process; it does not claim a fresh-process optimizer continuation test.

Run from the repository root with an available local step-413 source checkpoint:

```sh
python -m experiments.coding_probe --source /path/to/noah-transformer.pt --output /path/to/new-experiment-directory
```

The output directory must be new. Exact reproduction requires the same source checkpoint and software environment. The run artifacts remain on the owner's computer in `outputs/noah-coding-experiment-2026-11-02/` outside this source tree. Runtime weights and credentials are not committed. The adjacent result JSON records all generated answers and failures.

Next work should improve data diversity, sequence-length coverage and operation conditioning, then test against new reserved prompts. Repeatedly tuning to these inspected audit prompts would not establish generalization.
