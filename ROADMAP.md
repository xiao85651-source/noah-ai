# Noah roadmap

The selected application direction is biopharmaceutical research, science/technology and code generation. Measure evidence quality, correct uncertainty, checked calculations and actually tested code. `research-v1` is a tiny original curriculum and pipeline experiment, not evidence of those capabilities; see `RESEARCH.md`.

1. **Verified seed:** own Transformer, original multilingual seed corpus, own trained weights, CPU tests, voluntary client protocol, local control UI and reproducible checkpoints.
2. **Trusted remote pilot:** deploy a dedicated HTTPS contributor endpoint; recruit 2–5 willing testers; measure real throughput, transfer volume, outages and validation behavior. Add revocation and task verification.
3. **Resource controls:** operating-system resource limits, idle/power/thermal detection, explicit GPU consent, signed Windows installation and updates.
4. **Model/data scale:** use authorized, documented multilingual corpora; train larger Noah configurations from random initialization on stable authorized GPUs; keep independent benchmarks and model provenance. Establish useful capabilities before claiming a general assistant.
5. **Efficient collaboration:** compare compressed gradients, longer local training and appropriate aggregation against a single-device baseline. Do not assume internet-connected heterogeneous devices behave like one datacenter.
6. **Public collaboration:** after owner review, make the repository/client available, choose licenses and contribution terms, publish measured results and tested binaries.
7. **Free public access:** deploy a separate inference gateway using Noah weights, add fair queues and transparent limits, measure electricity/bandwidth/maintenance requirements and establish continuing voluntary support. Free access is the intended policy, not a claim that costs disappear.

No release gate is “looks like Claude.” Model progress must be measured on agreed independent tasks, with data and compute accounted for.
