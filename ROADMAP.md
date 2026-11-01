# Noah development charter

Noah is an independently initialized AI research project. The long-term aim is to help people reason, investigate and create, with accessible inference supported by voluntary contributions. That aspiration is not a claim that the current model is a capable scientific assistant or a superintelligence.

## Current evidence

- Decoder Transformer: 644,608 parameters, random initialization, no external model API.
- Published browser checkpoint: 325 training steps. Cloud research checkpoint and local experiments are separate artifacts; never add their step counts together.
- Research-v1 has 48 project-authored records across biopharma, technology and code. It is a demonstration corpus, without expert validation or evidence of professional competence.
- Local training, bounded candidate iteration, release history and rollback exist. Public cloud training writes remain disabled in the free ephemeral test.
- Web UI supports Chinese, English, Japanese, Spanish and Arabic. UI translation is not evidence of equivalent model fluency.

## Stage 1: durable invited training

Accept internet training results only after all of the following are demonstrated:

1. Checkpoint, optimizer state, version metadata and audit records survive a service restart. A clean environment can restore a verified backup with matching hashes.
2. Each invited node has a distinct identity, revocable access, request limits and explicit resource consent. Invitations and owner credentials never appear in public artifacts.
3. Tasks have bounded leases and replay protection. Invalid shapes, non-finite values, stale versions, duplicates and excessively large updates are rejected. A sample of work is independently recomputed; rejection reasons are recorded.
4. Failure injection and multiple-device tests show that disconnects do not corrupt accepted weights. GPU support is labeled experimental until exercised on actual hardware.
5. A small supervised pilot completes a bounded training run, evaluation, release and rollback. No public download is described as production-ready without this evidence.

No paid resources are authorized. If the free options cannot meet durability and capacity requirements, keep training closed and document the exact missing resource rather than silently running disposable training.

## Stage 2: evaluate useful reasoning

Start with licensed, traceable material and immutable training/validation/audit splits. Detect overlap and retain provenance, license, language and version for every dataset. Never automatically use private chats, medical records or arbitrary web content as training data.

Focus on observable outcomes: identifying assumptions, citing evidence, calibrated uncertainty, checking calculations, producing testable code and correcting errors. Do not equate longer answers or internal-looking reasoning text with better reasoning.

For biopharma, prioritize literature understanding, evidence quality and non-clinical scientific concepts; require expert review of domain evaluations. For technology, use reproducible explanations and quantitative problems. For coding, evaluate functional correctness against independent tests in an isolated execution environment. A small development score is not a release-quality benchmark.

Scale model and data only after measured learning, compute availability and evaluation quality justify the next experiment. Publish a versioned model card and regression results for each released checkpoint. Candidate promotion remains bounded, auditable and reversible.

## Stage 3: voluntary public participation

Before opening participation, provide an auditable client, integrity-checked releases, clear resource controls, pause/uninstall instructions, privacy terms, node revocation and abuse handling. Publish actual service availability and accepted-work metrics, never simulated global node counts. Contribution does not promise income, token rewards or ownership rights.

Share the public project page at https://zenithsmart.xin/train.html (English: `?lang=en`). The source repository remains private under the owner's existing instruction until a deliberate public-source release. Public website publication is separate from source visibility.

Routine implementation decisions follow this charter. Model improvements never authorize acquiring compute without consent, collecting private data, purchasing resources, granting new account access, or making unreviewed claims of professional capability.

## 中文执行原则

发展方向：可验证的科学研究与代码助手，重点覆盖生物制药、科技和编程。先保证成果可保存、可恢复、可验证，再扩大模型和参与规模。每次升级附带真实评测和回滚记录；“引领进步”是愿景，能力以实测为准。贡献者始终自愿接入并掌握设备控制权。
