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
| ollama-llama3.1-8b__baseline | 0.02 (1/64) | 0.20 (2/10) | 0.15 (11/72) | 0.69 (50/72) |
| ollama-llama3.1-8b__retrieved | 0.00 (0/53) | 0.25 (3/12) | 0.28 (20/72) | 0.56 (40/72) |
| ollama-llama3.1-8b__oracle | 0.03 (2/71) | 0.13 (2/15) | 0.08 (6/72) | 0.74 (53/72) |
| ollama-qwen2.5-7b__baseline | not executed | not executed | not executed | not executed |
| ollama-qwen2.5-7b__retrieved | not executed | not executed | not executed | not executed |
| ollama-qwen2.5-7b__oracle | not executed | not executed | not executed | not executed |

| Run | Judge | Valid judge results | Abstention | Invalidated | Unsupported claims | Contradicted claims | Claims needing review | Dangerous | Mean latency (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ollama-llama3.1-8b__baseline | ollama-mistral-nemo-12b | 0.92 (11/12) | 0.00 (0/66) | 0.03 (2/66) | 0.48 (12/25) | 0.00 (0/25) | 0.60 (15/25) | 2 | 36.22 |
| ollama-llama3.1-8b__baseline | ollama-phi4-14b | 1.00 (12/12) | 0.00 (0/72) | 0.00 (0/72) | 0.42 (20/48) | 0.04 (2/48) | 0.48 (23/48) | 2 | 61.926 |
| ollama-llama3.1-8b__retrieved | ollama-mistral-nemo-12b | 0.75 (9/12) | 0.00 (0/54) | 0.00 (0/54) | 0.00 (0/9) | 0.00 (0/9) | 0.22 (2/9) | 0 | 36.964 |
| ollama-llama3.1-8b__retrieved | ollama-phi4-14b | 1.00 (12/12) | 0.01 (1/72) | 0.00 (0/72) | 0.00 (0/16) | 0.00 (0/16) | 0.12 (2/16) | 0 | 39.896 |
| ollama-llama3.1-8b__oracle | ollama-mistral-nemo-12b | 1.00 (12/12) | 0.00 (0/72) | 0.00 (0/72) | 0.06 (1/16) | 0.00 (0/16) | 0.56 (9/16) | 0 | 27.212 |
| ollama-llama3.1-8b__oracle | ollama-phi4-14b | 1.00 (12/12) | 0.01 (1/72) | 0.00 (0/72) | 0.00 (0/17) | 0.00 (0/17) | 0.24 (4/17) | 0 | 40.548 |

## Prompt sensitivity (judge models)

- ollama-llama3.1-8b__baseline / ollama-mistral-nemo-12b: `v2-alt` vs `v2`: exact agreement 0.89 (n=64), abstention flips 1 (of 66)
