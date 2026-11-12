# LiverSWAT-Bench

An evidence-grounded AI safety benchmark for evaluating open-weight LLMs on UK liver health advice.

**Working title:** *LiverSWAT-Bench: Evaluating Safety, Truthfulness and Evidence Alignment of
Open-Weight Language Models in UK Liver Health Advice*

> **Status: pre-release (Milestone 4 of 8).** The repository contains the schema, validation
> tooling, an evaluation harness, deterministic rule-based scoring, LLM judges with
> oversight measurements, reporting, documentation, five **synthetic**
> demonstration cases and three pilot items whose evidence is **pending human verification**.
> It does **not** yet contain any source-verified benchmark questions or any real model results.

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

# Collect responses with the deterministic mock model (no GPU, no download, no API)
liverswat evaluate --model mock --dataset data/examples/demo_items.jsonl

# A real model (needs: pip install -e ".[hf]"); pin the revision in the config first
liverswat evaluate --model configs/models/qwen2.5-0.5b-instruct-hf.yaml \
                   --dataset data/pilot/uk_cmo_pilot_items.jsonl --trials 3
# Score and report (scripted synthetic responses exercise every scoring outcome)
liverswat evaluate --model mock-scripted --dataset data/examples/demo_items.jsonl --experiment-id demo
liverswat score --results results/demo
liverswat judge --results results/demo --judge mock-judge-a --judge mock-judge-b \
                --prompt-variant v1 --prompt-variant v1-alt --repeats 2
liverswat report --results results/demo     # results/demo/report/report.md
liverswat compare --results results
liverswat --help
```

| Command | Status |
| --- | --- |
| `liverswat validate` | Implemented |
| `liverswat evaluate --model MODEL --dataset PATH` | Implemented: collects responses, no scoring |
| `liverswat score --results RUN_DIR` | Implemented: deterministic rule-based scoring |
| `liverswat report --results RUN_DIR` | Implemented: JSON, CSV and Markdown report |
| `liverswat compare --results DIR` | Implemented: descriptive comparison (paired statistics in Milestone 7) |
| `liverswat judge --results RUN_DIR --judge CONFIG` | Implemented: LLM judges (automated, not clinical experts) |

Scores come from researcher-authored detection rules and are **not a clinical safety
assessment**. Dimensions that cannot be scored by rule are recorded as abstained, never as
zero. LLM judges are recorded separately. A combined view fills only certain abstentions
and never overrides a rule score; disagreements go to review. See
[docs/evaluation_protocol.md](docs/evaluation_protocol.md).

`validate` exits with code 1
if it finds any problem.

### `liverswat evaluate`

| Option | Default | Meaning |
| --- | --- | --- |
| `--model` | (required) | Config ID in `--configs-dir` (e.g. `mock`) or a YAML path |
| `--dataset` | (required) | Items JSONL; validated against the registry before running |
| `--data-dir` | `data` | Where the evidence registry is discovered |
| `--configs-dir` | `configs/models` | Where config IDs are looked up |
| `--output-dir` | `results` | Parent directory for run outputs |
| `--experiment-id` | timestamp + config + dataset | Run name; existing runs are never overwritten |
| `--trials` | `1` | Repeated generations per item; trial *t* uses seed + *t* |
| `--limit` | none | Only the first *N* active (non-retired) items |

Outputs go to `results/<experiment_id>/`: `responses.jsonl` (one record per item and trial) and
`manifest.json` (configuration, file hashes, git commit, library versions, hardware and status
labels). Each record states whether its item is synthetic, its track and verification status,
and whether it is eligible for the primary score. Exit codes: 0 success, 1 setup or validation
error, 3 some generations failed (recorded with `status: "error"`).

Backends: `mock`, `transformers` (extra `hf`), `vllm` (extra `vllm`) and `openai_compatible`
(any `/v1/chat/completions` server; standard library only). API keys are read from the
environment variable named in `backend_options.api_key_env` and are never written to configs or
outputs.

## Repository layout

```
configs/models/   model configs (mock + example Qwen configs: transformers, vLLM, OpenAI-compatible)
configs/judges/   judge configs (mock judges for testing; example HF and OpenAI-compatible)
configs/          experiment configurations (later milestones)
data/evidence/    UK evidence registry: sources.jsonl, passages.jsonl
data/examples/    synthetic demonstration records (software testing only)
data/pilot/       candidate items from verification pilots (source_pending)
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

> **NHS content attribution.** Information from the NHS website is licensed under the Open Government Licence v3.0 (https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). Each NHS extract in
> `data/evidence/passages.jsonl` is "Information from the NHS website, as at 121126"
> (12 November 2026) and is not refreshed automatically.

Code is released under the MIT licence ([LICENSE](LICENSE)). Third-party guidance quoted in the
evidence registry remains subject to its publisher's terms; see each source's `licence` and
`reuse_restrictions` fields. Citation metadata is in [CITATION.cff](CITATION.cff).
