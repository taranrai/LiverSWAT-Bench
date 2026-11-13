# data/evidence

The UK evidence registry.

- `sources.jsonl`: 11 source records (5 NHS, 1 UK Chief Medical Officers, 5 NICE). All have the
  status `unverified`.
- `passages.jsonl`: 29 verbatim extracts (22 NHS, 7 UK Chief Medical Officers). NICE text is not
  stored, because the NICE licence covers UK use only.
- `verification_log.jsonl`: machine text matches against page snapshots. No human review is
  recorded yet.

The verification workflow is in `docs/evidence-verification.md` and `docs/evidence_policy.md`.

**NHS content attribution.** Information from the NHS website is licensed under the Open Government Licence v3.0 (https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). NHS extracts are "Information from the NHS website, as at 121126".

**UK Chief Medical Officers extracts.** Contains public sector information licensed under the Open
Government Licence v3.0. The licence check on 13 November 2026 found no exclusion. The check
record is in `docs/evidence-verification.md`. The `reuse_restrictions` field of the source record
predates the check.
