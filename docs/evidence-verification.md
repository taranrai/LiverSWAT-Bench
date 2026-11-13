# Evidence verification

Documentation follows ASD-STE100 Simplified Technical English principles. Formal compliance has
not been certified.

This document describes the source-verification workflow for National Health Service (NHS)
and other UK sources. It also describes the status of the source evidence.
The general policy is in [evidence_policy.md](evidence_policy.md).

## Rules

1. A machine check can confirm that a stored extract occurs verbatim in a snapshot of the
   official page. A machine check does not verify the extract.
2. Only a human review can change a source or extract to `verified`.
3. A statement by a language model is never a verification record.
4. The validator rejects `verified` source evidence that has no confirmed human review in
   `data/evidence/verification_log.jsonl`.
5. Entries in the verification log are appended. Do not edit or delete entries.

## Workflow

1. Add the source and the extracts to `data/evidence/sources.jsonl` and
   `data/evidence/passages.jsonl` with the status `unverified`.
2. Take a snapshot of each official page:

   ```bash
   liverswat evidence snapshot --out data/evidence/snapshots
   ```

   The command records the Hypertext Transfer Protocol (HTTP) status, the final URL, the
   retrieval time and the Secure Hash Algorithm 256-bit (SHA-256) hash.
   Snapshots stay out of Git. Only the hashes go into the log.
3. Run the machine check and record the result:

   ```bash
   liverswat evidence check --snapshots data/evidence/snapshots --record
   ```

4. A person opens each official page in a browser and checks:
   - the title, the organisation and the URL;
   - the "Page last reviewed" date;
   - each extract, at its stated location;
   - the context of each extract;
   - the reuse terms.
5. The person records the result:

   ```bash
   liverswat evidence record-review --source-id SRC-NHS-HEPC --passage-id PSG-NHS-HEPC-CURE \
       --reviewer "Full Name" --result confirmed --notes "Checked in browser on 2026-11-20."
   ```

6. The person changes the status in the registry to `verified` and adds `date_verified`.
7. Run `liverswat validate`. Expected outcome: "Validation passed."
8. Show the status of all extracts:

   ```bash
   liverswat evidence status
   ```

## Licence decisions

| Source | Licence | Decision |
| --- | --- | --- |
| NHS website | Open Government Licence (OGL) v3.0, NHS website terms 3.3 to 3.6 | Store short unchanged extracts with the attribution "Information from the NHS website, as at 121126". Publish the statement "Information from the NHS website is licensed under the Open Government Licence v3.0". |
| UK Chief Medical Officers (GOV.UK) | OGL v3.0 (GOV.UK publication page). Licence check on 13 November 2026: no exclusion found (see below). | Store short unchanged extracts with the attribution "Contains public sector information licensed under the Open Government Licence v3.0." |
| National Institute for Health and Care Excellence (NICE) | NICE UK Open Content Licence: UK use only. International use needs a permission request. | Do not store NICE text in public files. A public GitHub repository is international. |

The NHS website terms exclude logos, images, third-party content and medical devices from the OGL.
The repository stores none of these.

### Licence check: UK Chief Medical Officers guidelines (13 November 2026)

The maintainer approved OGL v3.0 as the reuse basis after this check. The check is a record of the
licence position. It is not legal advice or legal certification. It does not verify the source
evidence or the benchmark items, which stay `source_pending`.

| Item | Result |
| --- | --- |
| Publication page | https://www.gov.uk/government/publications/alcohol-consumption-advice-on-low-risk-drinking |
| Licence statement on the page | "All content is available under the Open Government Licence v3.0, except where otherwise stated" |
| Document | https://assets.publishing.service.gov.uk/media/5a80b7ed40f0b623026951db/UK_CMOs__report.pdf |
| Document hash (SHA-256) | `7ebe010a78c4e66936ac11130df4a1cd74a987438c3a98b8a3687627f240575e` (same as the Milestone 2 snapshot) |
| Rights statements in the document | "© Crown copyright 2016" (page 11) only |
| Exclusions or third-party notices | None found on the page or in the extracted document text |
| Extracts | All 7 stored extracts occur in the document text. All are text by the UK Chief Medical Officers. No extract is from a figure, logo or quoted third-party work. |
| Attribution | Contains public sector information licensed under the Open Government Licence v3.0. Source: UK Chief Medical Officers' Low Risk Drinking Guidelines, Department of Health, August 2016. |

Method: text search of the page and of the document text (extracted with pypdf) for licence,
copyright, third-party, permission and reuse statements. Text inside images is not searched.
The source record in `data/evidence/sources.jsonl` is not changed, to keep the registry hashes
of the Milestone 5 pilot. Update the record at the human review in Milestone 6.

## Status on 12 November 2026

| Item | Count | Status |
| --- | --- | --- |
| NHS sources | 5 | `unverified`. Snapshots taken; HTTP 200 for each. |
| NHS extracts | 22 | `unverified`. Machine check: 22 of 22 match. Human review: 0 of 22. |
| UK Chief Medical Officers source | 1 | `unverified`. See [pilots/uk_cmo_low_risk_drinking.md](pilots/uk_cmo_low_risk_drinking.md). |
| UK Chief Medical Officers extracts | 7 | `unverified`. Machine-checked against the PDF in Milestone 2. Not in the log. |
| NHS benchmark items | 12 | `source_pending` |

### NHS sources

| Source ID | Page | Page last reviewed | Next review due |
| --- | --- | --- | --- |
| `SRC-NHS-NAFLD` | Non-alcoholic fatty liver disease (NAFLD) | 31 July 2025 | 31 July 2028 |
| `SRC-NHS-ARLD` | Alcohol-related liver disease (ARLD) | 15 July 2026 | 15 July 2029 |
| `SRC-NHS-HEPC` | Hepatitis C | 19 March 2026 | 19 March 2029 |
| `SRC-NHS-HEPB` | Hepatitis B | 17 November 2025 | 17 November 2028 |
| `SRC-NHS-JAUNDICE` | Jaundice | 22 January 2024 | 22 January 2027 |

The NHS "Liver disease" overview page was not used. Its review was due on 9 August 2026, and
the page had not been reviewed on 12 November 2026.

## Human review checklist (per NHS benchmark item)

1. Confirm that each extract is on the official page at the stated location.
2. Confirm that the context does not change the meaning of the extract.
3. Confirm that each required expected claim follows directly from its extract.
4. Review the draft evaluation rules:
   - Does each rule detect the claim?
   - Does each rule avoid unrelated wording?
5. Decide which prohibited claims and safety requirements are critical.
6. Record the review with `liverswat evidence record-review`.
7. Change the status values and run `liverswat validate`.
