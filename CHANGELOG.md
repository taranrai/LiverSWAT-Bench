# Changelog

All notable changes to LiverSWAT-Bench are listed in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Version numbers follow
[Semantic Versioning](https://semver.org/).

Documentation follows ASD-STE100 Simplified Technical English principles. Formal compliance has
not been certified.

## [0.1.0] - Research preview

First public research preview. The benchmark is not clinically validated. No benchmark item has
completed source verification.

### Added

- **Dataset schema and validation.** Pydantic schemas for benchmark items, sources, passages,
  model responses, scores and judge results. JSON Schemas in `schemas/`. `liverswat validate`.
- **Evidence registry and verification workflow.** Source and passage records, page snapshots,
  machine text match, human review log (`liverswat evidence`). The validator rejects `verified`
  evidence without a recorded human review.
- **Evaluation harness.** Model adapters for mock, Ollama, Transformers, vLLM and
  OpenAI-compatible servers. Pinned model revisions. Run manifests with hashes, Git state and
  hardware (`liverswat evaluate`).
- **Evidence conditions.** A (baseline), B (retrieved, lexical retriever `lexical-tfidf-v1`) and
  C (oracle).
- **Rule-based evaluation.** Deterministic scorer `det-2/rules-1` with detection rules, claim
  assessments, critical failure flags and abstention (`liverswat score`).
- **Judge model infrastructure.** Versioned judge prompts (`v1`, `v1-alt`, `v2`, `v2-alt`),
  structured output validation, evidence reference checks, repair retries and abstention
  (`liverswat judge`).
- **Combination and oversight metrics.** Policy `combine-1`, judge consensus, disagreement and
  abstention rates with denominators, prompt sensitivity (`liverswat report`, `liverswat
  compare`).
- **Pilot orchestration.** `liverswat pilot` with resume, `--dry-run`, `--judge-only` and judge
  checkpoints.
- **Benchmark items.** 12 NHS pilot benchmark items and 3 UK Chief Medical Officers pilot
  benchmark items (all `source_pending`). 5 synthetic demo benchmark items for software tests.
- **Milestone 5 pilot results.** 72 real model responses (`llama3.1:8b`, `qwen2.5:7b`) and 84 of
  168 planned judge results. See `docs/real-model-pilot.md`.
- **Hugging Face Space configuration** for the remaining judge steps (`deploy/hf-space/`). Not
  built or run.
- **Documentation.** Methodology, evaluation protocol, evidence policy, limitations, dataset card,
  documentation style check (`liverswat check-docs`).
- **Project files.** Contributing guide, code of conduct, security policy, issue templates and a
  pull request template.

### Known limitations

- No source evidence has a human review. No clinician has reviewed the benchmark items.
- The judge stage is incomplete. No judge result exists for `qwen2.5:7b`.
- The evaluation rules on the pilot benchmark items are drafts.
- The Transformers and vLLM adapters are tested with stubs only.

See `docs/limitations.md`.
