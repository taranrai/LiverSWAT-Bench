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

- Only `liverswat validate` is implemented. Evaluation, judging, comparison and reporting are
  planned for later milestones.
