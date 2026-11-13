# Milestone 5 methodology: real-model pilot

Documentation follows ASD-STE100 Simplified Technical English principles. Formal compliance has
not been certified.

## Research question

Can automated evaluation methods consistently identify evidence-grounding failures in real
open-weight language model responses to UK liver health questions?

This pilot is an artificial intelligence (AI) safety evaluation experiment. It is not a clinical validation study.

## Status of the pilot

| Category | Status |
| --- | --- |
| Benchmark items | 12 National Health Service (NHS) items. All are `source_pending`. |
| Source evidence | 22 verbatim NHS extracts. Each extract has a machine text match. No extract has a human review. |
| Model responses | Real model results from local inference. They are experimental results. |
| Judge results | Real judge model results. They are experimental results. Incomplete: 84 of 168 planned judge results. The remaining steps move to a Hugging Face Space (see [Judge stage migration](#judge-stage-migration)). |
| Primary benchmark results | None. No benchmark item is `source_verified`. |

## Design

### Benchmark items

1. Use 12 benchmark items from NHS website pages (see [evidence-verification.md](evidence-verification.md)).
2. Each benchmark item is Level A. Each required expected claim restates one verbatim extract.
3. Each benchmark item has draft evaluation rules. A researcher must review these rules.
4. Keep every benchmark item `source_pending` until a human review confirms the source evidence.

### Models

Use local inference only. The pilot uses no paid application programming interface (API) and no remote compute.

| Role | Model | Licence | Quantisation | Reason for selection |
| --- | --- | --- | --- | --- |
| Evaluated model | `llama3.1:8b` | Llama 3.1 Community License | Q4_K_M | Installed; fits in 24 gigabytes (GB) of memory |
| Evaluated model | `qwen2.5:7b` | See `configs/models/` | Q4_K_M | Different model family at a similar size |
| Judge model | `mistral-nemo:12b` | See `configs/judges/` | Q4_0 or as installed | Different family from the evaluated models |
| Judge model | `phi4:14b` | See `configs/judges/` | Q4_K_M or as installed | Different family from the evaluated models |

The exact digests, licences and quantisation levels are in the configuration files. The Ollama
adapter refuses to run if the installed model digest differs from the configured digest.

`gpt-oss:20b` was installed but could not load in Ollama 0.40.6 (error: "unsupported tensor
size overflows"). The pilot does not use this model.

### Evidence conditions

| Condition | The model receives | Component |
| --- | --- | --- |
| A, `baseline` | The question only | None |
| B, `retrieved` | The top 3 passages from the lexical retriever | `lexical-tfidf-v1`: term frequency-inverse document frequency (TF-IDF) with cosine similarity over all non-synthetic passages with stored text |
| C, `oracle` | The exact cited passages of the benchmark item | None |

All conditions use the same model configuration, seed and generation settings. Only the user
message changes. The evidence wording has the version `evidence-v1`.

Condition B uses a real retrieval component. The component is simple and lexical. The corpus is
small (the passages in the evidence registry). Each model response records the passages it
received, the retrieval scores and the oracle recall. Oracle recall is the share of the cited
passages that the retriever returned.

### Evaluation methods

1. **Evaluation rules** (scorer `det-2`). Apply the detection rules of each benchmark item.
2. **Judge models** (prompt `v2`, evidence policy `include_unverified`). Two judge models assess
   each model response independently. The judge models do not see the expected claims or the
   rule scores.
3. **Combined evaluation** (`combine-1`, policy `rules_first_review_on_disagreement`). Rule scores
   stay unchanged. Judge consensus fills only the abstentions that the policy allows.

The judge models receive unverified source evidence because no source evidence is verified yet.
All judge results are therefore labelled for development use only.

### Measurements

The pilot summary reports each rate with its numerator and denominator:

- number of evaluated benchmark items;
- valid model responses;
- valid judge results;
- judge disagreement (pairs of judge scores that differ by more than 1);
- rule-versus-judge material disagreement (a difference of 2 or more);
- abstention rates (evaluation rules, judge models, combined evaluation);
- unsupported-claim rate and contradicted-claim rate (judge models);
- contradicted claims detected by evaluation rules;
- critical failure flags (rule-detected and needs review);
- prompt sensitivity for one judge model on Condition A (`v2-alt` against `v2`);
- latency and token counts.

## Assumptions

1. The installed model digests identify the model weights.
2. Temperature 0 and a fixed seed give repeatable output on the same hardware and software.
   Repeatability across hardware is not measured.
3. The NHS extracts were current on 12 November 2026.

## What the pilot cannot show

1. The pilot cannot show clinical correctness. No clinician reviewed the benchmark items.
2. The pilot cannot show evaluator accuracy. No independent reference standard exists.
3. The pilot cannot rank models in general. The sample is 12 benchmark items and one trial.

## Reproduction

1. Install Ollama and pull the models in `configs/experiments/m5-real-model-pilot.yaml`.
2. Check that each installed digest matches the configuration file.
3. Run `liverswat pilot --config configs/experiments/m5-real-model-pilot.yaml`.
4. Read `results/m5-real-model-pilot/pilot_summary.md`.

The pilot resumes after an interruption. Completed steps are not repeated. An interrupted judge
step resumes from its checkpoint.

## Judge stage migration

The local judge stage was paused on 12 November 2026 after 84 of 168 planned judge results. All
72 model responses were complete. The remaining 84 judge results (all for `qwen2.5-7b`) move to
a private Hugging Face Docker Space with a graphics processing unit (GPU).

| Change | Detail |
| --- | --- |
| `liverswat pilot --judge-only` | Runs only judge steps and reports. Runs no model inference and no scoring. Stops if model responses or scores are missing. |
| `liverswat pilot --dry-run` | Lists the pending steps. Runs and writes nothing. |
| Judge checkpoints | Each judge result is stored as it completes. An interrupted step resumes from the checkpoint. |
| Result storage | A private Hugging Face dataset repository. `scripts/hf_results_sync.py` refuses a public repository. |
| Space configuration | `deploy/hf-space/`: Dockerfile, entrypoint, status page. |

GitHub stays the primary source repository. The judge prompts, judge configurations, seeds and
evaluation rules are not changed. The migration adds one limitation: the two evaluated models are
judged on different hardware. See [hf-space-judge-migration.md](hf-space-judge-migration.md).
