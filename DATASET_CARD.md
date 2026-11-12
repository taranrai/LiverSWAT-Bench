# Dataset Card: LiverSWAT-Bench

> **Draft.** The dataset has not been released. This card will be completed before any
> publication. Nothing is published to Hugging Face without the maintainer's explicit approval.

## Summary

Questions about UK liver health, paired with expected claims, prohibited claims, safety
requirements and uncertainty requirements, each linked to passages from authoritative UK
guidance.

- **Benchmark version:** 0.1.0 (pre-release)
- **Clinical validation status:** **not clinically validated.** The items are evidence-grounded
  (source-verified) only.
- **Language / locale:** English, United Kingdom

## Current contents

| Split / track | Items | Notes |
| --- | --- | --- |
| primary | 0 | No source-verified items yet. |
| exploratory | 3 | Pilot candidates (`data/pilot/`), `source_pending`; UK CMO alcohol guideline; evidence awaiting human verification. |
| experimental | 0 | |
| demo | 5 | Synthetic. Fictional sources. For software testing only. |

Only release-eligible records will be published: `track` primary or exploratory,
`verification_status: source_verified`, `synthetic: false`, and evidence whose licence permits
redistribution. Experimental items may be released separately and clearly labelled. Private
holdout items are never published.

## Intended use

- Research on LLM truthfulness, safety-related behaviour and evidence alignment in UK liver
  health advice.
- Comparing models and automated evaluation methods.

## Out-of-scope use

- Certifying any model as clinically safe or suitable for patient-facing deployment.
- Medical advice or clinical decision-making.
- Claims of NHS endorsement or regulatory approval.

## Source provenance

Sources are prioritised from NICE, NHS, BSG, BASL, the British Liver Trust, UKHSA and the UK
Chief Medical Officers. Each source records its official URL, identifier, dates, date accessed,
licence and verification status. See [docs/evidence_policy.md](docs/evidence_policy.md).

## Construction and verification

See [docs/methodology.md](docs/methodology.md) and [docs/evidence_policy.md](docs/evidence_policy.md).
In summary: each item links to verified passages. Level A items follow directly from explicit
statements. Level B and C items are excluded from the primary score.

## Limitations and ethical considerations

See [docs/limitations.md](docs/limitations.md). In particular, the benchmark is not clinically
validated, it is biased towards questions that guidance answers explicitly, and items may leak
into future training data. Items contain no patient data.

## Licence

Benchmark code and original annotations: MIT. Quoted or paraphrased guidance remains subject to
each publisher's terms, recorded per source in `licence` and `reuse_restrictions`. Those terms
must be confirmed before release.
