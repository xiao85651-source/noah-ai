# Noah research direction

The owner selected **biopharmaceutical research, science/technology and code generation**. Noah remains an independently initialized model. This direction is a development target, not a statement that the deployed model has these capabilities.

## Run the research profile

On Windows, run `Research.cmd` and open `http://127.0.0.1:4323/#network`. This sets `NOAH_PROFILE=research-v1` and stores working weights under `data-profiles/research-v1/`. The original seed branch and its owner checkpoint under `data/` remain separate. No new profile silently loads a seed checkpoint whose corpus hash belongs to a different dataset.

The first research experiment initializes a new Noah configuration from random weights, then trains on the original project-authored curriculum. It does not incorporate another provider's model. The original browser serving weights remain unchanged until a separately reviewed publication.

The bundled curriculum contains 48 bilingual records: 36 training, 6 validation and 6 audit records. These were authored for the project by the coding assistant and have not been reviewed by a domain expert. Each record includes an ID, concept group, split, domain, language and authored provenance. Duplicate records, unsupported provenance and concept groups shared between training and evaluation are rejected. This is a tiny development corpus; topical overlap and repeated consultation still prevent interpreting it as an independent general benchmark.

The data target evidence quality and uncertainty, boundaries between laboratory and clinical evidence, reference honesty, measurement/units, reproducibility, data leakage, simple pure functions, edge cases and tests. Responses should give a concise, checkable explanation and state assumptions; long explanations alone do not demonstrate correct reasoning.

## Measure capability

```powershell
$env:NOAH_PROFILE = 'research-v1'
python -m training.train --steps 40
python -m training.research_eval --output data-profiles/research-v1/evaluation.json
```

The development runner measures held-out byte-level loss by language and domain, then checks six fixed tasks covering evidence restraint, unknown references, arithmetic and two Python functions. Only an explicitly allowlisted arithmetic-function AST may execute, in a short-lived isolated Python process; imports, attributes, calls, loops and exponentiation are rejected. This narrow checker is not a sandbox for general code or a broad software benchmark. Other generated code is not executed.

The actual first run completed 40 CPU updates: validation loss **5.5747075876 → 4.0395072699**. Development task pass count remained **0/6** before and after. This establishes a working targeted training/evaluation loop, and fails to establish useful domain reasoning. Training and serving were not switched to claim specialist capability.

Automatic iteration additionally requires all six current development probes to pass, the existing language/audit gates, and no evaluated domain loss regression above 3%. The baseline snapshot is an experimental reference; it is not a qualified specialist release. Passing these six known tasks would still be insufficient for clinical, scientific or production-software claims. Larger independent evaluation and expert review are necessary before such claims or publication.

## Expand data responsibly

Use original authorized material or sources with verified machine-learning/reuse rights, retain the source/version/license/attribution/retraction status, and deduplicate by document/concept before splitting. Do not ingest private patient records, proprietary laboratory documents or visitor chats by default. No internet corpus was bulk downloaded by this change.

PMC explicitly states that not every article is reusable, licenses vary, and automated retrieval must use its approved services. Its dataset distribution changed in August 2026, so old FTP examples should not be copied blindly. See [PMC article datasets](https://pmc.ncbi.nlm.nih.gov/tools/textmining/).

For evaluation governance, consult the [FDA page linking current GMLP principles](https://www.fda.gov/medical-devices/artificial-intelligence-enabled-medical-devices/good-machine-learning-practice-medical-device-development-guiding-principles). This project is not a medical device validation, clinical evidence package or regulatory approval. Research-model text must not independently direct treatment or operational biological experimentation.

The current 644,608-parameter, 128-byte-context model is a pipeline prototype. Scaling toward useful reasoning needs substantially larger appropriate context/model/data, authorized GPU resources, data governance and independent task evaluation. Connecting many heterogeneous devices does not remove communication, verification, electricity or maintenance costs.
