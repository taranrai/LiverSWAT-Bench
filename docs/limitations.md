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

- `validate`, `evaluate`, `score`, `report` and `compare` are implemented. LLM judges and
  claim extraction (Milestone 4) and paired statistics (Milestone 7) are not.
- Deterministic scoring only covers wording anticipated by each item's detection rules.
  Paraphrases can be missed (false absent), and coincidental wording can match (false
  detected). Negation, attribution and number checks reduce but do not remove this. Rules
  never award 4, and three dimensions always abstain.
- The detection rules on the pilot items are drafts and have not been reviewed by a
  researcher.
- **Safety on silence (known limitation, policy unchanged).** If an item's only safety checks
  are prohibited-claim rules, a response that says nothing relevant (a non-answer, a refusal or
  placeholder text) passes every check and scores safety behaviour **3**. The score shows only
  that no prohibited wording was detected, not that the response was safe or helpful. Factual
  accuracy usually exposes such responses (score 1), but safety scores should be read with this
  in mind. A regression test (`test_safety_on_silence_known_limitation`) records the current
  behaviour; the policy will be revisited in Milestone 4.
- The Transformers and vLLM adapters are tested with stubs only. No real model has been run
  through them in this repository yet.
- The OpenAI-compatible backend cannot verify which weights a server is running; the reported
  model ID is recorded but the revision depends on how the server was started.
