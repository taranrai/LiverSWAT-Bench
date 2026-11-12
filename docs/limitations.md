# Limitations

## Clinical validation

- No clinical experts have validated the benchmark items, expected answers or scoring rubrics.
- The benchmark measures observable adherence to published UK guidance. It does not measure
  clinical safety, diagnostic competence or suitability for autonomous decisions.
- Results must not be used to claim deployment safety, regulatory approval or NHS endorsement.
- LLM judges are not used to certify clinical safety. Agreement between automated evaluators is
  not evidence of medical correctness.

## Evidence

- Guidance changes. A source verified on one date may later be superseded; see the
  re-verification process in [evidence_policy.md](evidence_policy.md).
- Restricting the benchmark to explicit (Level A) statements biases it towards questions that
  guidance answers directly. Harder, judgement-dependent questions are underrepresented by
  design.
- Some publishers restrict verbatim reuse. Paraphrased passages add a possible source of error.

## Dataset

- Version 0.1.0 contains no source-verified items. The five demo items are synthetic, cite
  fictional sources and exist only to test the software.
- Items are written in English and for a UK context. Results may not generalise to other
  languages, health systems or populations.
- Public benchmark items may enter future training data. A private holdout set (kept outside
  version control) is planned to help detect contamination.

## Scoring

- The dimension weights are provisional design choices.
- Rule-based checks can miss paraphrases. Semantic checks can over-credit vague answers.

## Current software state

- All CLI commands are implemented. Paired statistical comparison (Milestone 7) is not.
- Deterministic scoring only covers wording anticipated by each item's detection rules.
  Paraphrases can be missed (false absent), and coincidental wording can match (false
  detected). Negation, attribution and number checks reduce but do not remove this. Rules
  never award 4, and three dimensions always abstain under rules alone.
- The detection rules on the pilot items are drafts and have not been reviewed by a
  researcher.
- **Safety on silence (addressed in Milestone 4).** Under scorer `det-1`, a non-answer could score
  safety 3 when the only safety checks were prohibited-claim rules. Scorer `det-2` requires a met
  `requires` check before awarding 3 on safety or uncertainty; otherwise the dimension abstains.
  As a result, more dimensions abstain until items gain positive `requires` rules. `det-1`
  results remain labelled as such.
- The Transformers and vLLM adapters are tested with stubs only. No real model has been run
  through them in this repository yet.
- The OpenAI-compatible backend cannot verify which weights a server is running; the reported
  model ID is recorded but the revision depends on how the server was started.

## LLM judges

- **Judges are automated evaluators, not clinical experts.** Agreement between judges, or with
  the rules, measures consistency, not correctness. No expert-labelled reference set exists, so
  judge accuracy is unknown.
- **No real judge model has been run in this repository.** The mock judges replay hand-written
  synthetic outputs, so the oversight figures in example reports describe those scripts, not
  any model.
- **Judges with `verified_only` currently see no evidence,** because no passage is verified.
  The example pipeline uses `include_unverified` and is labelled development-only.
- **Judges share the evaluated model's failure modes.** They can hallucinate, be swayed by
  wording, or be biased towards particular styles. Validation catches invented passage IDs and
  claims that aren't quoted word for word, but not a judge misreading a real passage.
- **Consensus is only as independent as the judges.** Judges from the same model family may
  share errors; using different families is recommended.
- **Claim alignment between judges uses identical text only.** This undercounts agreement when
  judges quote different spans of the same statement.
- **Cost estimates exist only if you supply rates.** Local inference cost (hardware, energy) is
  not estimated.

## Milestone 5: real-model pilot

Documentation follows ASD-STE100 Simplified Technical English principles. Formal compliance has
not been certified.

### Evidence

- No benchmark item has a human review. All 15 pilot benchmark items are `source_pending`.
- A machine check confirms only that an extract occurs verbatim in a page snapshot. A machine
  check does not confirm that the extract is current or correctly interpreted.
- National Institute for Health and Care Excellence (NICE) text is not stored. The NICE licence
  covers UK use only. NICE recommendations are therefore not in the pilot.
- The questions, expected claims and evaluation rules are drafts by the project. A researcher
  must review them.

### Models and inference

- The pilot uses two quantised models (Q4_K_M) at about 8 billion parameters. Results do not
  apply to other sizes, quantisation levels or model versions.
- The pilot uses one trial per benchmark item at temperature 0. The pilot does not measure
  variation across trials or across hardware.
- `gpt-oss:20b` could not load in the installed Ollama version and is not in the pilot.

### Evidence conditions

- Condition B uses a lexical retriever (TF-IDF, term frequency-inverse document frequency) over a
  small corpus: the passages in the registry. Condition B does not represent a production
  retrieval system. Oracle recall is reported for each model response.
- Condition C supplies the exact cited extract. Condition C shows an upper bound for evidence
  supply. Condition C does not show how a deployed system would perform.

### Judge models

- The judge models are small (12 to 14 billion parameters) and quantised. In exploratory tests, a
  small judge model paraphrased claims instead of quoting them. Validation sends such claims to
  human review.
- The judge models received unverified source evidence (evidence policy `include_unverified`).
- Judge prompt `v2` was introduced in this milestone after a small model omitted dimensions under
  prompt `v1`. Results from `v1` and `v2` are not directly comparable.
- No independent reference standard exists. The pilot reports agreement, not accuracy.

### Sample size

- The pilot has 12 benchmark items. Rates have wide uncertainty. The pilot does not report
  confidence intervals or statistical tests (planned for Milestone 7).

### Judge stage migration

- The judge stage is incomplete: 84 of 168 planned judge results. Judge results for
  `qwen2.5-7b` are not executed yet.
- The remaining judge steps will run on a different host: a graphics processing unit (GPU) on a
  Hugging Face Space. The completed steps ran on an Apple M4 Pro laptop. Temperature 0 does not
  guarantee identical output on different hardware. A comparison of the two evaluated models can include a hardware effect.
  Each judge manifest records its host.
- The Space configuration was not built or run in Milestone 5. The synchronisation code has unit
  tests with a fake client only.
- `mistral-nemo` gave `invalid_output` for 4 of its 48 completed judge results (prompt `v2`: 4 of
  36; prompt `v2-alt`: 0 of 12). `phi4` gave `invalid_output` for 0 of 36.
