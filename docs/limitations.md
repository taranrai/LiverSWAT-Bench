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
