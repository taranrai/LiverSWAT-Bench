# Milestone 5 real-model pilot: interim report

Documentation follows ASD-STE100 Simplified Technical English principles. Formal compliance has
not been certified.

> **Status: incomplete.** The judge stage stopped at 84 of 168 planned judge results. The
> remaining judge steps move to a Hugging Face Space (see
> [hf-space-judge-migration.md](hf-space-judge-migration.md)). This report gives counts only.
> Agreement, abstention and disagreement metrics are not reported until the judge stage is
> complete.

The method is in [milestone-5-methodology.md](milestone-5-methodology.md). The limitations are in
[limitations.md](limitations.md).

## Result labels

| Part | Label |
| --- | --- |
| Model responses (`results/m5-real-model-pilot/*/responses.jsonl`) | Real model results. Experimental results. |
| Evaluation rule scores (`scores.jsonl`) | Real model results scored by draft evaluation rules. Experimental results. |
| Judge results for `llama3.1-8b` | Real judge results. Experimental results. Judge models saw unverified source evidence. |
| Judge results for `qwen2.5-7b` | Not executed. |
| Source evidence | Pending human review. All 12 benchmark items are `source_pending`. |
| `results/m5-real-model-pilot/judge-smoke-test/` | Real judge results on 2 model responses. Smoke test only. |
| Mock pilot (`configs/experiments/mock-pilot.yaml`) | Mock test results. Software tests only. Not model results. |

## Model responses

| Measurement | Result |
| --- | --- |
| Model responses with status `ok` | 72/72 (2 models x 3 evidence conditions x 12 benchmark items, 1 trial) |

## Judge results at the pause

| Judge model | Prompt | Status `ok` | Status `invalid_output` |
| --- | --- | --- | --- |
| `phi4:14b` | `v2` | 36/36 | 0/36 |
| `mistral-nemo:12b` | `v2` | 32/36 | 4/36 |
| `mistral-nemo:12b` | `v2-alt` | 12/12 | 0/12 |
| **Total** | | **80/84** | **4/84** |

Each `invalid_output` result is an abstention. No score was filled in for it.

## Retrieval coverage (Condition B)

The retrieval coverage describes the retriever only. It does not assess model responses. The data
is in `results/m5-real-model-pilot/retrieval_coverage.json`.

| Measurement | Result |
| --- | --- |
| Retriever | `lexical-tfidf-v1`, top 3, corpus of 29 passages |
| Mean oracle recall | 0.6875 (n = 12 benchmark items) |
| Benchmark items with oracle recall 1.0 | 6/12 |
| Benchmark items with oracle recall 0 | 1/12 (`LSB-NAFLD-0003`) |
| Retrieved passages not cited by the benchmark item | 22/35 |
| Same retrieval for both models | Yes |

For `LSB-HEPB-0002` (hepatitis B), the first retrieved passage is about hepatitis C treatment.
Condition B can therefore give a model misleading source evidence. Condition B results include
this retriever effect.

## Not executed

- Judge results for `qwen2.5-7b` (84 judge results).
- The combined evaluation, the oversight metrics and the pilot summary for the full pilot.
- Human review of source evidence and evaluation rules.
