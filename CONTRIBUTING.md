# Contributing to LiverSWAT-Bench

Documentation follows ASD-STE100 Simplified Technical English principles. Formal compliance has
not been certified.

LiverSWAT-Bench is a research benchmark. Data integrity is more important than the number of
benchmark items. Read this guide before you open an issue or a pull request.

## Ground rules

1. Do not fabricate evidence, quotations, citations, URLs, dates or results.
2. Link every new benchmark item to source records and passage records in the evidence registry.
3. Do not set `verified` or `source_verified` unless you checked the official source yourself and
   recorded a human review (`liverswat evidence record-review`).
4. Do not commit patient data, personal health information, private holdout items
   (`data/private/`), credentials or model weights.
5. Set `synthetic: true` on synthetic content. Keep synthetic content out of the primary track.
6. Do not store text from a source whose licence does not permit public redistribution, for
   example National Institute for Health and Care Excellence (NICE) content. Store a locator
   instead.
7. Label mock results as mock test results. Do not present them as model results.

## Types of contribution

| Contribution | Start with |
| --- | --- |
| Software bug | Issue template "Bug report" |
| Error in a source record or extract | Issue template "Evidence correction" |
| Review of a benchmark item | Issue template "Benchmark item review" |
| Model response that shows a safety failure | Issue template "Safety evaluation failure" |
| New feature | Issue template "Feature request" |
| Research question or methodology feedback | GitHub Discussions |

## Workflow

1. Open an issue. Describe the problem or the proposed change. For new benchmark items or changes
   to scoring, wait for maintainer feedback before you start.
2. Fork the repository and create a branch from `main`.
3. Install the development environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```

4. Make the change. Add or update tests.
5. Run the checks. All checks must pass:

   ```bash
   ruff check .
   ruff format --check .
   liverswat validate
   liverswat check-docs --strict
   pytest
   ```

6. If you changed a Pydantic model, run `python scripts/export_schemas.py`. If you changed
   benchmark items, run `python scripts/export_dataset_metadata.py`.
7. Open a pull request. Complete the pull request template. State what you verified and how.

The continuous integration (CI) workflow runs the same checks on Python 3.11 and 3.12.

## Add a benchmark item

1. Add the source to `data/evidence/sources.jsonl`, or use an existing source.
2. Add the passage to `data/evidence/passages.jsonl`. Obey the reuse terms of the source.
3. Make a page snapshot and record the machine text match:
   `liverswat evidence snapshot --out data/evidence/snapshots --source-id SOURCE_ID`, then
   `liverswat evidence check --snapshots data/evidence/snapshots --record`. Git ignores the
   snapshot directory.
4. Add the benchmark item to a `*items.jsonl` file in `data/pilot/` or `data/experimental/`.
   Start with the status `source_pending`.
5. Use Level A only if the expected answer follows directly from the passage text.
6. Run `liverswat validate`.

The detailed workflow is in [docs/evidence-verification.md](docs/evidence-verification.md) and
[docs/evidence_policy.md](docs/evidence_policy.md).

## Repository layout

| Path | Content |
| --- | --- |
| `src/liverswat_bench/` | Python package and command-line interface (CLI) |
| `tests/` | pytest suite |
| `schemas/` | JSON Schemas generated from the Pydantic models |
| `configs/models/`, `configs/judges/` | Model and judge model configurations |
| `configs/experiments/` | Pilot configurations |
| `data/evidence/` | Evidence registry: sources, passages, verification log |
| `data/pilot/` | `source_pending` pilot benchmark items |
| `data/examples/` | Synthetic demo records for software tests |
| `data/verified/`, `data/experimental/` | Verified benchmark items and stress-test items (both empty) |
| `results/m5-real-model-pilot/` | Milestone 5 pilot results (other result folders are not committed) |
| `deploy/hf-space/` | Hugging Face Space configuration for the judge stage |
| `docs/` | Methodology, protocol, policies, reports. Index: [docs/README.md](docs/README.md) |

## Code style

Python 3.11 or later. Ruff formats and lints the code (configuration in `pyproject.toml`). Tests
use pytest. Documentation follows the writing rules in `CLAUDE.md` (section "Technical writing
standard").

## Licence of contributions

By contributing, you agree that your contribution is licensed under the MIT licence of this
repository. Third-party extracts keep the licence of their publisher.
