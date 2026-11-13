## Summary

<!-- State what the pull request changes and why. Link the issue. -->

## Type of change

- [ ] Software (code, tests, configuration)
- [ ] Evidence registry (sources, passages, verification log)
- [ ] Benchmark items
- [ ] Documentation

## Checks

- [ ] `ruff check .` and `ruff format --check .` pass.
- [ ] `liverswat validate` passes.
- [ ] `liverswat check-docs --strict` passes.
- [ ] `pytest` passes.
- [ ] I regenerated `schemas/` (if I changed a Pydantic model) and `data/dataset_metadata.json` (if I changed benchmark items).

## Research integrity

- [ ] I did not fabricate evidence, quotations, citations or results.
- [ ] I did not set `verified` or `source_verified` without a recorded human review.
- [ ] Mock results are labelled as mock test results.
- [ ] The change does not alter scoring, prompts, seeds or thresholds. If it does, I explain the effect below.
- [ ] The change contains no personal data, credentials or model weights.

## Effect on results

<!-- State "None" or describe the effect on scores, judge results or reproducibility. -->
