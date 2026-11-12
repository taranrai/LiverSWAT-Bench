# Pilot summary: m5-real-model-pilot

> **REAL MODEL RESULTS - EXPERIMENTAL RESULTS, SOURCE EVIDENCE PENDING HUMAN REVIEW**

- Agreement between automated evaluators measures consistency, not correctness.
- No independent reference standard exists; evaluator accuracy is not reported.

Dataset: `data/pilot/nhs_pilot_items.jsonl`. Combination policy: `rules_first_review_on_disagreement`.

Benchmark items by verification status: {'source_pending': 12}. Only source_verified items can produce primary benchmark results.

## Model responses and rule-based evaluation

| Run | Model | Condition | Items | Valid responses | Mean latency (s) | Oracle recall | Rule abstention | Contradicted (rules) | Critical (rule / review) | Factual mean (rules) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ollama-llama3.1-8b__baseline | `llama3.1:8b` | baseline | 12 | 1.00 (12/12) | 8.89 | n/a | 0.82 (59/72) | 0.00 (0/5) | 2 / 0 | 2.50 (n=10) |
| ollama-llama3.1-8b__retrieved | `llama3.1:8b` | retrieved | 12 | 1.00 (12/12) | 0.989 | 0.69 (n=12) | 0.79 (57/72) | 0.00 (0/5) | 0 / 0 | 2.33 (n=12) |
| ollama-llama3.1-8b__oracle | `llama3.1:8b` | oracle | 12 | 1.00 (12/12) | 0.898 | n/a | 0.79 (57/72) | 0.00 (0/5) | 0 / 0 | 2.58 (n=12) |
| ollama-qwen2.5-7b__baseline | `qwen2.5:7b` | baseline | 12 | 1.00 (12/12) | 7.771 | n/a | 0.81 (58/72) | 0.00 (0/5) | 0 / 0 | 2.50 (n=10) |
| ollama-qwen2.5-7b__retrieved | `qwen2.5:7b` | retrieved | 12 | 1.00 (12/12) | 2.268 | 0.69 (n=12) | 0.78 (56/72) | 0.00 (0/5) | 0 / 0 | 2.75 (n=12) |
| ollama-qwen2.5-7b__oracle | `qwen2.5:7b` | oracle | 12 | 1.00 (12/12) | 1.775 | n/a | 0.78 (56/72) | 0.00 (0/5) | 1 / 0 | 2.92 (n=12) |

## Judge models and combined evaluation

| Run | Judge disagreement | Rule vs judge (material) | Combined abstention or review | Filled by judge consensus |
| --- | --- | --- | --- | --- |
| ollama-llama3.1-8b__baseline | not executed | not executed | not executed | not executed |
| ollama-llama3.1-8b__retrieved | not executed | not executed | not executed | not executed |
| ollama-llama3.1-8b__oracle | not executed | not executed | not executed | not executed |
| ollama-qwen2.5-7b__baseline | not executed | not executed | not executed | not executed |
| ollama-qwen2.5-7b__retrieved | not executed | not executed | not executed | not executed |
| ollama-qwen2.5-7b__oracle | not executed | not executed | not executed | not executed |

| Run | Judge | Valid judge results | Abstention | Invalidated | Unsupported claims | Contradicted claims | Claims needing review | Dangerous | Mean latency (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Prompt sensitivity (judge models)

Not executed.
