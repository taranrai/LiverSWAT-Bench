# Release status: version 0.1.0 (research preview)

Documentation follows ASD-STE100 Simplified Technical English principles. Formal compliance has
not been certified.

> **Research Preview: This benchmark is under active review. The pilot items have not completed
> source verification or clinical expert validation. Results must not be used to certify the
> clinical safety of AI systems.**

## What version 0.1.0 is

Version 0.1.0 is a software and methodology release. The release is for inspection,
installation, testing and contribution. Version 0.1.0 is not a benchmark
dataset release. Version 0.1.0 contains no primary benchmark results.

## Component status

| Component | Status | Tested by |
| --- | --- | --- |
| Command-line interface (CLI), `liverswat` | Complete | `tests/test_cli.py`, continuous integration (CI) mock pipeline |
| Dataset schema and validation | Complete | `tests/test_item_schema.py`, `tests/test_validation.py` |
| Evidence provenance and verification workflow | Complete | `tests/test_verification.py`, `tests/test_evidence.py` |
| Rule-based evaluation | Complete | `tests/test_rules.py`, `tests/test_scoring*.py` |
| Judge model infrastructure | Complete | `tests/test_judges.py`, `tests/test_judge_pipeline.py` |
| Abstention and disagreement handling | Complete | `tests/test_combine_oversight.py` |
| Model inference configuration | Complete | `tests/test_model_config.py`, `tests/test_adapters.py` |
| Ollama adapter | Complete. Used for the real-model pilot. | `tests/test_ollama_adapter.py` |
| Transformers and vLLM adapters | Implemented. Tested with stubs only. | `tests/test_adapters.py` |
| Resumable evaluation and judge checkpoints | Complete | `tests/test_pilot.py`, `tests/test_judge_checkpoint.py` |
| Reporting and comparison | Complete | `tests/test_scoring_pipeline.py`, `tests/test_judge_pipeline.py` |
| Hugging Face Space configuration | Not built. Not run. | `tests/test_hf_results.py` (fake client only) |

## Data status

| Data | Count | Status |
| --- | --- | --- |
| National Health Service (NHS) pilot benchmark items | 12 | `source_pending`, no human review |
| UK Chief Medical Officers pilot benchmark items | 3 | `source_pending`, no human review |
| Synthetic demo benchmark items | 5 | Software tests only |
| Source-verified benchmark items | 0 | None |
| Stored extracts | 29 | 22 NHS (machine text match), 7 UK Chief Medical Officers |

## Experimental result status

| Result | Count | Status |
| --- | --- | --- |
| Model responses | 72 of 72 | Complete |
| Rule-based scores | 72 of 72 | Complete (draft evaluation rules) |
| Judge results, `llama3.1:8b` | 84 of 84 | Complete |
| Judge results, `qwen2.5:7b` | 0 of 84 | Paused. Not executed. |

Details: [real-model-pilot.md](real-model-pilot.md).

## Not tested in this release

- Hosted graphics processing unit (GPU) execution on a Hugging Face Space.
- Real models through the Transformers and vLLM adapters.
- Paid application programming interface (API) backends. The project needs no paid API.

## Release conditions for a later dataset release

The conditions are in [../DATASET_CARD.md](../DATASET_CARD.md). No condition is met for
version 0.1.0.
