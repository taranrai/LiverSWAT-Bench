# Roadmap

Documentation follows ASD-STE100 Simplified Technical English principles. Formal compliance has
not been certified.

The roadmap is a plan. Dates are not committed. The status is correct for version 0.1.0.

| Milestone | Scope | Status |
| --- | --- | --- |
| 1. Repository foundation | Package, schemas, evidence registry, demo benchmark items, tests, continuous integration (CI) | Complete |
| 2. Evaluation harness | Model adapters, pinned configurations, response storage, `liverswat evaluate` | Complete |
| 3. Evidence-grounded scoring | Deterministic evaluation rules, claim assessments, reports | Complete |
| 4. Automated judges | Judge models, structured output, abstention, disagreement analysis | Complete |
| 5. Safety experiments | Evidence conditions and a real-model pilot | Partly complete (see below) |
| 6. Verified benchmark dataset | Source-verified UK liver health benchmark items with human review | Planned |
| 7. Model comparison | Reproducible evaluation of selected open-weight models, paired statistics | Planned |
| 8. Research publication | Technical report, benchmark documentation, Hugging Face dataset | Planned |

## Milestone 5: open work

1. Complete the 84 pending judge results for `qwen2.5:7b`. The plan is in
   [hf-space-judge-migration.md](hf-space-judge-migration.md). Paid hardware needs maintainer
   approval.
2. Decide whether to judge all 168 judge results on one host, to remove the hardware effect.
3. Implement adversarial prompt variants (false premise, pressure for certainty, instructions to
   ignore evidence). These variants are in the original Milestone 5 scope and are not
   implemented.
4. Do a human review of the 12 National Health Service (NHS) benchmark items, their extracts
   and their evaluation rules.

## Milestone 6: verified benchmark dataset

1. Do a human review of each source and extract. Record each review in the verification log.
2. Add Level A benchmark items to `data/verified/` only after the human review.
3. Work towards the targets per topic in [methodology.md](methodology.md). The targets are not
   quotas.
4. Confirm the licence of each stored extract before public release.

## Milestone 7: model comparison

1. Select open-weight models and pin each revision.
2. Run all evidence conditions with more than one trial.
3. Report confidence intervals and paired comparisons at the benchmark item level.

## Milestone 8: research publication

1. Write the technical report.
2. Publish the dataset on Hugging Face only when the release conditions in
   [../DATASET_CARD.md](../DATASET_CARD.md) are true.

## How to influence the roadmap

Open a discussion or an issue. See [../CONTRIBUTING.md](../CONTRIBUTING.md).
