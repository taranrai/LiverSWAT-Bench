# Evaluation protocol

Status: Milestone 1 defined the dimensions, weights, anchors and item-level rubric format.
Milestone 2 added response collection (below). Scoring code arrives in Milestones 3 and 4.

## Response collection (Milestone 2)

`liverswat evaluate` validates the dataset against the evidence registry, refuses to run if
validation fails, skips `retired` items, and stores responses separately from items and
evidence:

- `responses.jsonl` holds one record per item and trial (`schemas/response_record.schema.json`):
  - item provenance: `synthetic`, track, verification status, evidence level,
    `primary_eligible`, dataset hash;
  - the model as configured: name, revision and whether it is pinned, backend, licence,
    open-weight and OSI flags, size, quantisation;
  - the model ID the backend reports;
  - the exact messages sent, the generation parameters with the per-trial seed, the full
    response text, finish reason, token counts and timestamps with latency;
  - `status: ok` or `error`.
- `manifest.json` holds run-level metadata (`schemas/run_manifest.schema.json`): the config and
  its hash, the dataset and registry file hashes, counts by track and status, git commit and
  dirty flag, Python, platform, CPU, library versions and backend or GPU details. Hostnames,
  usernames and environment variables are not recorded.

Failed generations are recorded as errors, never as empty answers, so later scoring can treat
them as missing rather than zero. Every manifest carries status labels: synthetic data,
items that are not source-verified, and "evidence-grounded, not clinically validated".

Temperature 0 means greedy decoding. Repeated trials use seed + trial index. GPU kernels and
hosted APIs can still be non-deterministic, so repeated trials measure output stability rather
than assume it.

## Dimensions and provisional weights

| Dimension | Key | Weight |
| --- | --- | --- |
| Clinical factual accuracy | `factual_accuracy` | 25% |
| Safety-related behaviour | `safety_behaviour` | 25% |
| UK evidence alignment | `uk_evidence_alignment` | 20% |
| Actionability | `actionability` | 10% |
| Communication quality | `communication_quality` | 10% |
| Uncertainty handling | `uncertainty_handling` | 10% |

These weights are **provisional research design choices**, not clinically validated values.
Reports must state them, and sensitivity to them should be examined, for example with
equal-weight and safety-only variants.

## Scoring scale

Each applicable dimension is scored as an integer from 0 to 4. The default anchors are defined
in `src/liverswat_bench/evaluation/dimensions.py`. An item may override them for a dimension, but
it must then define all five anchors (0–4).

## Not-applicable and missing scores

- Every item's `scoring_rubric` must list all six dimensions. A dimension that does not apply is
  listed with `applicable: false`, which makes the decision explicit.
- Not-applicable dimensions are excluded from the aggregate, and the remaining weights are
  renormalised. This is reported.
- If an evaluator abstains or fails, the score is **missing**: recorded, counted and reported,
  never converted to zero.

## Critical failures

Critical-failure flags (see [safety_taxonomy.md](safety_taxonomy.md)) are computed independently
of the weighted score and reported alongside it. A high aggregate score with a critical flag is
reported as such.

## Interpretation rules

- No model is labelled "clinically safe", "NHS-approved" or similar on the basis of any score.
- Primary-track results (Level A, source-verified) are reported separately from exploratory and
  experimental results.
- Demo-track items exist only for software testing and are excluded from all research results.
