# Dataset card: LiverSWAT-Bench

Documentation follows ASD-STE100 Simplified Technical English principles. Formal compliance has
not been certified.

> **Status: not released.** Do not publish this dataset to Hugging Face until all of these
> conditions are true:
>
> 1. The public split contains `source_verified` benchmark items with a confirmed human review.
> 2. Every stored extract has a licence that permits redistribution with the required attribution.
> 3. The maintainer approves the release.
>
> The machine-readable status is in `data/dataset_metadata.json`.

## Summary

LiverSWAT-Bench contains UK liver health questions (benchmark items). Each benchmark item links
to source evidence from UK health organisations. Each benchmark item lists expected claims,
contradicted claims, prohibited claims, safety requirements, uncertainty requirements and
evaluation rules.

- **Benchmark version:** 0.1.0 (pre-release)
- **Clinical validation status:** not clinically validated. Source evidence is checked against
  published guidance only.
- **Language and locale:** English, United Kingdom
- **Version metadata:** `data/dataset_metadata.json`. The script
  `scripts/export_dataset_metadata.py` generates the file. A test checks that the file is current.

## Current contents

| File | Benchmark items | Track | Verification status | Use |
| --- | --- | --- | --- | --- |
| `data/examples/demo_items.jsonl` | 5 | demo | draft | Software tests only. Synthetic. |
| `data/pilot/uk_cmo_pilot_items.jsonl` | 3 | exploratory | source_pending | Pilot. Experimental results only. |
| `data/pilot/nhs_pilot_items.jsonl` | 12 | exploratory | source_pending | Milestone 5 pilot. Experimental results only. |
| `data/verified/` | 0 | primary | source_verified | None yet. |

No benchmark item is eligible for primary benchmark results. Private holdout items are never
published.

## Intended use

- Research on the truthfulness, safety-related behaviour and evidence alignment of language
  models in UK liver health advice.
- Comparison of automated evaluation methods (evaluation rules and judge models).

## Out-of-scope use

- Do not use the dataset to certify a model as clinically safe.
- Do not use the dataset for medical advice or clinical decisions.
- Do not claim National Health Service (NHS) endorsement or regulatory approval.

## Source provenance

| Organisation | Sources | Stored extracts | Licence | Status |
| --- | --- | --- | --- | --- |
| NHS website | 5 | 22 | Open Government Licence (OGL) v3.0 | Machine-checked; human review pending |
| UK Chief Medical Officers | 1 | 7 | OGL v3.0 | Human review pending |
| National Institute for Health and Care Excellence (NICE) | 5 | 0 | NICE UK Open Content Licence (UK use only) | Candidate entries; no text stored |

Each source records the official URL, the access date, the review date (where shown), the
licence and the required attribution. The verification log
(`data/evidence/verification_log.jsonl`) records each machine check with the snapshot hash. See
[docs/evidence-verification.md](docs/evidence-verification.md).

## Construction and verification

1. Select an explicit statement from an official UK page.
2. Store the statement verbatim, if the licence permits reuse.
3. Write a question and expected claims that follow directly from the statement (Level A).
4. Write draft evaluation rules.
5. Check the extract against a page snapshot (machine check).
6. A person reviews the source, the extract and the evaluation rules (human review).
7. After the human review only, change the status to `source_verified`.

## Licences and attribution

- Code and original annotations: MIT licence.
- NHS extracts: Information from the NHS website is licensed under the Open Government Licence
  v3.0 (https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). Each NHS
  extract is "Information from the NHS website, as at 121126".
- UK Chief Medical Officers extracts: Open Government Licence v3.0 (GOV.UK).
- NICE content: not stored. The NICE licence covers UK use only.

## Reproducibility

1. Install the package: `pip install -e ".[dev]"`.
2. Validate the data: `liverswat validate`. Expected outcome: "Validation passed."
3. Regenerate the metadata: `python scripts/export_dataset_metadata.py`.
4. Reproduce the real-model pilot: see [docs/real-model-pilot.md](docs/real-model-pilot.md).

## Limitations

See [docs/limitations.md](docs/limitations.md). The main limitations are:

- No benchmark item has a human review.
- No clinician has reviewed the benchmark items.
- The benchmark covers questions that guidance answers explicitly. Judgement-dependent questions
  are under-represented.
- Public benchmark items can enter future model training data.

## Ethical considerations

- The benchmark items contain no patient data.
- Health information changes. Each source records a review date. Re-check sources before each
  release.
- Do not present results as evidence that a model is safe for patients.
