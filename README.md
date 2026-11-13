# LiverSWAT-Bench

**Evaluating Safety, Truthfulness and Evidence Alignment of Language Models in UK Liver Health
Advice**

> **Research Preview: This benchmark is under active review. The pilot items have not completed
> source verification or clinical expert validation. Results must not be used to certify the
> clinical safety of AI systems.**

[![CI](https://github.com/taranrai/LiverSWAT-Bench/actions/workflows/ci.yml/badge.svg)](https://github.com/taranrai/LiverSWAT-Bench/actions/workflows/ci.yml)
Version 0.1.0 (research preview). Licence: MIT (code). See [Licence](#licence) for data rights.

Documentation follows ASD-STE100 Simplified Technical English principles. Formal compliance has
not been certified.

## Project overview

LiverSWAT-Bench is an open-source research framework for evaluating the safety, truthfulness,
robustness and evidence alignment of language models on UK liver health information tasks.

Each benchmark item is a liver health question. Each benchmark item links to source evidence from
UK health organisations, for example the National Health Service (NHS) website. The framework
collects model responses, scores them with evaluation rules and judge models, and records where
the methods disagree or abstain.

The benchmark is **evidence-grounded, not clinically validated**. A score shows how closely a
model response follows published UK guidance. A score does not show clinical safety, diagnostic
competence or fitness for deployment.

## Research objectives

1. Measure how reliably open-weight language models give truthful and evidence-grounded liver
   health information.
2. Identify observable safety-related failures, for example false reassurance or missing
   urgent-care advice.
3. Measure whether supplied UK source evidence changes model responses.
4. Measure how consistently automated evaluation methods (evaluation rules and judge models)
   identify failures, and where they disagree.

The full list of research questions is in [docs/methodology.md](docs/methodology.md).

## AI safety evaluation dimensions

Artificial intelligence (AI) safety evaluation in this framework uses six dimensions. Each
dimension has a score from 0 to 4 or an abstention.

| Dimension | Key | Provisional weight |
| --- | --- | --- |
| Clinical factual accuracy | `factual_accuracy` | 25% |
| Safety-related behaviour | `safety_behaviour` | 25% |
| UK evidence alignment | `uk_evidence_alignment` | 20% |
| Actionability | `actionability` | 10% |
| Communication quality | `communication_quality` | 10% |
| Uncertainty handling | `uncertainty_handling` | 10% |

The weights are provisional research design choices. Critical failure flags are reported
separately from scores. See [docs/evaluation_protocol.md](docs/evaluation_protocol.md) and
[docs/safety_taxonomy.md](docs/safety_taxonomy.md).

## Features

| Feature | Command or module |
| --- | --- |
| Dataset schema and validation | `liverswat validate` |
| Evidence provenance and verification workflow | `liverswat evidence snapshot\|check\|record-review\|status` |
| Model inference with pinned configurations (mock, Ollama, Transformers, vLLM, OpenAI-compatible) | `liverswat evaluate` |
| Evidence conditions: A baseline, B retrieved, C oracle | `liverswat evaluate --evidence-condition` |
| Rule-based evaluation (deterministic) | `liverswat score` |
| Judge model infrastructure with structured output and validation | `liverswat judge` |
| Abstention and disagreement handling | `liverswat report --policy` |
| Reporting and comparison | `liverswat report`, `liverswat compare` |
| Resumable pilot runs with judge checkpoints | `liverswat pilot --dry-run\|--judge-only` |
| Documentation style check | `liverswat check-docs` |

The framework needs no paid application programming interface (API). The mock models and mock
judge models run without a graphics processing unit (GPU) or network access.

## Installation

Requirements: Python 3.11 or 3.12, and Git.

```bash
git clone https://github.com/taranrai/LiverSWAT-Bench.git
cd LiverSWAT-Bench
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Expected outcome: `liverswat --help` lists the commands.

Optional extras: `hf` (Transformers), `vllm`, `analysis` (pandas, NumPy, SciPy) and `space`
(Hugging Face Hub client for results synchronisation). Real models also need a backend, for
example [Ollama](https://ollama.com).

## Quick start

Run these commands from the repository root. They use mock models only.

1. Validate the data:

   ```bash
   liverswat validate
   ```

   Expected outcome: `Validation passed.`

2. Run the mock pilot (3 evidence conditions, 2 mock judge models):

   ```bash
   liverswat pilot --config configs/experiments/mock-pilot.yaml
   ```

   Expected outcome: `results/mock-pilot/pilot_summary.md`. The results are labelled
   `MOCK TEST RESULTS`. They are software test results, not model results.

## Example benchmark evaluation

This example runs each step separately on the 5 synthetic demo benchmark items.

```bash
# 1. Collect model responses (scripted synthetic responses)
liverswat evaluate --model mock-scripted --dataset data/examples/demo_items.jsonl --experiment-id demo
# 2. Score the model responses with the evaluation rules
liverswat score --results results/demo
# 3. Assess the model responses with two mock judge models and one broken mock judge model
liverswat judge --results results/demo --judge mock-judge-a --judge mock-judge-b --judge mock-judge-broken
# 4. Write the report (JSON, CSV and Markdown)
liverswat report --results results/demo
# 5. Compare all runs in results/
liverswat compare --results results
```

Expected outcome: `results/demo/report/report.md`.

To evaluate a real local model, install Ollama, pull the model, and check that the digest matches
the configuration file. Then run, for example:

```bash
liverswat evaluate --model configs/models/ollama-llama3.1-8b.yaml \
  --dataset data/pilot/nhs_pilot_items.jsonl --evidence-condition oracle
```

The Ollama adapter stops if the installed model digest differs from the configured digest.

## Evidence and dataset status

| File | Benchmark items | Track | Verification status |
| --- | --- | --- | --- |
| `data/pilot/nhs_pilot_items.jsonl` | 12 | exploratory | `source_pending` |
| `data/pilot/uk_cmo_pilot_items.jsonl` | 3 | exploratory | `source_pending` |
| `data/examples/demo_items.jsonl` | 5 | demo (synthetic) | `draft` |
| `data/verified/` | 0 | primary | `source_verified` |

- No benchmark item has a human review. No benchmark item is eligible for primary benchmark
  results.
- The evidence registry has 29 verbatim extracts: 22 from the NHS website and 7 from the UK Chief
  Medical Officers (CMO) guidelines. Each NHS extract has a machine text match against a page
  snapshot.
- National Institute for Health and Care Excellence (NICE) text is not stored, because the NICE
  licence covers UK use only.

See [DATASET_CARD.md](DATASET_CARD.md) and [docs/evidence-verification.md](docs/evidence-verification.md).

## Preliminary experimental results

> The results below are experimental results from an incomplete pilot. Do not use them to rank
> models.

The Milestone 5 pilot evaluated `llama3.1:8b` and `qwen2.5:7b` (Ollama, Q4_K_M) on the 12 NHS
benchmark items under 3 evidence conditions.

| Stage | Status |
| --- | --- |
| Model responses | 72/72 complete (status `ok`) |
| Deterministic evaluation | 72/72 model responses scored. 3 critical failure flags need human review. |
| Judge results, `llama3.1:8b` | 84/84 complete: 80 valid, 4 `invalid_output` |
| Judge results, `qwen2.5:7b` | 0/84. Paused. Not executed. |

The judge coverage is not equal for the two models. The completed judge results therefore do not
give a balanced model comparison. The full report is in
[docs/real-model-pilot.md](docs/real-model-pilot.md).

## Reproducibility

- Each run writes a manifest. The manifest records the model digest, generation settings, seed,
  dataset hash, evidence registry hashes, Git commit, library versions and hardware.
- Model configurations pin the model revision. Real backends refuse unpinned models by default.
- Runs never overwrite existing outputs. The pilot skips completed steps.
- An interrupted judge step resumes from its checkpoint (`liverswat pilot --judge-only`).
- The JSON Schemas in `schemas/` are generated from the Pydantic models
  (`python scripts/export_schemas.py`).

## Limitations

- The benchmark is not clinically validated. No clinician has reviewed the benchmark items.
- No source evidence has a human review yet.
- The pilot has 12 benchmark items and 1 trial. Rates have wide uncertainty.
- Judge models are automated evaluators, not clinical experts. Agreement measures consistency,
  not correctness.
- The evaluation rules are drafts. They can miss paraphrases or match the wrong text.

The full list is in [docs/limitations.md](docs/limitations.md). The release status is in
[docs/release-status.md](docs/release-status.md).

## Roadmap

| Milestone | Status |
| --- | --- |
| 1. Repository foundation | Complete |
| 2. Evaluation harness | Complete |
| 3. Evidence-grounded scoring | Complete |
| 4. Automated judges | Complete |
| 5. Safety experiments (real-model pilot) | Partly complete |
| 6. Verified benchmark dataset | Planned |
| 7. Model comparison | Planned |
| 8. Research publication | Planned |

Details: [docs/roadmap.md](docs/roadmap.md).

## Contributing

Contributions are welcome, especially evidence corrections and reviews of benchmark items. Read
[CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Report
security problems as described in [SECURITY.md](SECURITY.md).

## Citation

Citation metadata is in [CITATION.cff](CITATION.cff).

```bibtex
@software{rai_liverswat_bench_2026,
  author  = {Rai, Taran},
  title   = {{LiverSWAT-Bench: Evaluating Safety, Truthfulness and Evidence Alignment of
             Open-Weight Language Models in UK Liver Health Advice}},
  version = {0.1.0},
  year    = {2026},
  url     = {https://github.com/taranrai/LiverSWAT-Bench}
}
```

## Licence

- **Code and original annotations:** MIT licence ([LICENSE](LICENSE)).
- **NHS extracts:** Information from the NHS website is licensed under the Open Government Licence v3.0 (https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). Each NHS extract is "Information from the NHS website, as at 121126" (12 November 2026).
- **UK Chief Medical Officers extracts:** Contains public sector information licensed under the
  Open Government Licence v3.0. The licence check on 13 November 2026 found no exclusion (see
  [docs/evidence-verification.md](docs/evidence-verification.md)). The check is not legal
  certification.
- **NICE content:** not stored.

Third-party content keeps its publisher's terms. Each source record lists its `licence` and
`reuse_restrictions`. The MIT licence does not apply to third-party extracts.
