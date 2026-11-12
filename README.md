# LiverSWAT-Bench

An evidence-grounded AI safety benchmark for evaluating open-weight LLMs on UK liver health advice.

**Working title:** *LiverSWAT-Bench: Evaluating Safety, Truthfulness and Evidence Alignment of
Open-Weight Language Models in UK Liver Health Advice*

> **Status: pre-release (Milestone 1 of 8).** The repository contains the schema, validation
> tooling, documentation and five **synthetic** demonstration cases. It does **not** yet contain
> any source-verified benchmark questions or any model results.

## What this benchmark is, and is not

LiverSWAT-Bench measures how closely model answers adhere to published UK liver health guidance
(NICE, NHS, BSG, BASL, British Liver Trust, UKHSA, UK Chief Medical Officers).

It is **evidence-grounded, not clinically validated**. Scores do not establish clinical safety,
diagnostic competence, fitness for deployment, regulatory approval or NHS endorsement. See
[docs/limitations.md](docs/limitations.md).

## Research questions

How reliably do open-weight language models provide safe, truthful and evidence-grounded liver
health information, and can automated evaluation identify model failures without extensive
clinical expert annotation? The eight secondary questions (safety, truthfulness, evidence
alignment, robustness, uncertainty, scalable oversight, open-weight comparison and evidence
augmentation) are set out in [docs/methodology.md](docs/methodology.md).

## Installation

Requires Python 3.11 or newer.

```bash
git clone https://github.com/taranrai/LiverSWAT-Bench.git
cd LiverSWAT-Bench
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Optional extras: `analysis` (pandas/NumPy/SciPy), `hf` (Transformers/Datasets), `vllm`.

## Usage

```bash
liverswat validate                      # validate everything under data/
liverswat validate --items data/examples/demo_items.jsonl \
                   --sources data/examples/demo_sources.jsonl \
                   --passages data/examples/demo_passages.jsonl
liverswat --help
```

| Command | Status |
| --- | --- |
| `liverswat validate` | Implemented |
| `liverswat evaluate --model MODEL_ID --dataset PATH` | Planned (Milestone 2) |
| `liverswat report --results DIR` | Planned (Milestone 3) |
| `liverswat judge --results PATH` | Planned (Milestone 4) |
| `liverswat compare --results DIR` | Planned (Milestone 7) |

Commands that are not implemented yet exit with code 2 and say so. `validate` exits with code 1
if it finds any problem.

## Repository layout

```
configs/          model, experiment and judge configurations (from Milestone 2)
data/evidence/    UK evidence registry: sources.jsonl, passages.jsonl
data/examples/    synthetic demonstration records (software testing only)
data/verified/    source-verified benchmark items (none yet)
data/experimental/ adversarial / misinformation stress-test items (none yet)
data/private/     holdout data; git-ignored, never committed
schemas/          JSON Schemas generated from the Pydantic models
docs/             methodology, evidence policy, taxonomy, protocol, limitations
src/liverswat_bench/  the Python package
tests/            pytest suite
results/          run outputs (git-ignored)
```

## Data model in brief

- **Sources** and **evidence passages** are stored separately from **benchmark items**, and model
  outputs will be stored separately again.
- Each item has an **evidence level** (A: directly supported; B: interpretation; C: clinical
  judgement), a **verification status** (`draft`, `source_pending`, `source_verified`, `disputed`,
  `expert_review_required`, `retired`) and a **track** (`primary`, `exploratory`, `experimental`,
  `demo`).
- Only Level A, `source_verified`, non-synthetic items can enter the primary score. The validator
  enforces this.
- Source verification means the cited document and passage were checked. It is not clinical
  validation.

Details: [docs/evidence_policy.md](docs/evidence_policy.md) and
[docs/evaluation_protocol.md](docs/evaluation_protocol.md).

## Development

```bash
pytest                              # run tests
ruff check . && ruff format --check .
python scripts/export_schemas.py    # regenerate schemas/ after changing a model
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence and citation

Code is released under the MIT licence ([LICENSE](LICENSE)). Third-party guidance quoted in the
evidence registry remains subject to its publisher's terms; see each source's `licence` and
`reuse_restrictions` fields. Citation metadata is in [CITATION.cff](CITATION.cff).
