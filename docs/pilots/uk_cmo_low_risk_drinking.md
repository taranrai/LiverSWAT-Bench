# Evidence-verification pilot: UK CMO Low Risk Drinking Guidelines

**Status: MACHINE-RETRIEVED, NOT HUMAN-VERIFIED.** The source and all passages remain
`unverified`, and the three candidate items remain `source_pending` in the `exploratory` track.
Nothing below is clinical validation. A guideline citation shows only what the guideline says.

- **Pilot date:** 2026-11-12
- **Goal:** test whether one real UK recommendation can become a Level A benchmark item, and
  what the verification step needs.

## 1. Sources attempted

| Source | Result |
| --- | --- |
| NICE NG49 (NAFLD) overview, recommendations and NICE terms pages | **Not retrieved.** HTTP 403 on all three pages (automated access blocked). Nothing recorded from NICE; the NG49 registry entry is unchanged. |
| GOV.UK publication page for the UK CMO guidelines | Retrieved (HTTP 200). |
| Guideline PDF linked from that page | Retrieved; text extracted locally. |

The CMO guideline was chosen as a fallback because it is official, short, explicit and
published under the Open Government Licence. It is a general alcohol guideline, not a
liver-specific one; liver disease appears in its supporting explanation (paragraph 17).

## 2. What was retrieved

Each value is labelled with how it was obtained.

| Field | Value | Obtained from |
| --- | --- | --- |
| Document title | UK Chief Medical Officers’ Low Risk Drinking Guidelines | PDF cover page and PDF metadata title |
| GOV.UK page title | Alcohol consumption: advice on low risk drinking | Publication page |
| Official URL (page) | https://www.gov.uk/government/publications/alcohol-consumption-advice-on-low-risk-drinking | Fetched |
| Official URL (PDF) | https://assets.publishing.service.gov.uk/media/5a80b7ed40f0b623026951db/UK_CMOs__report.pdf | Linked from the page |
| PDF SHA-256 | `7ebe010a78c4e66936ac11130df4a1cd74a987438c3a98b8a3687627f240575e` | Computed locally |
| PDF length | 11 pages | pypdf |
| Publisher shown | Department of Health and Social Care | Publication page ("From:") |
| Authors | The 4 UK chief medical officers | Publication page details text |
| Published | 25 August 2016 | Publication page |
| Last updated | Not shown on the page | Publication page |
| PDF cover date | August 2016 | PDF page 1 |
| Licence (page) | "All content is available under the Open Government Licence v3.0, except where otherwise stated" | Publication page footer |
| Copyright (PDF) | "© Crown copyright 2016" | PDF page 11 |
| Licence statement inside PDF | None found in the extracted text | pypdf extraction |

## 3. Recommendation and passages

All seven passages were checked programmatically: each appears word for word in the
extracted PDF text, ignoring line breaks and paragraph numbers. They are stored in
`data/evidence/passages.jsonl`.

| Passage ID | Location | Use |
| --- | --- | --- |
| `PSG-UKCMO-2016-WEEKLY-SCOPE` | p.4, applicability line | Applicability |
| `PSG-UKCMO-2016-WEEKLY-MEN-WOMEN` | p.4, lead-in | Same guideline for men and women |
| `PSG-UKCMO-2016-WEEKLY-LIMIT` | p.4, bullet 1 | **Core recommendation** (14 units) |
| `PSG-UKCMO-2016-WEEKLY-SPREAD` | p.4, bullet 2 | Spread over 3 or more days; heavy episodes |
| `PSG-UKCMO-2016-PARA17` | p.5, para 17 | Liver disease can develop without apparent harm |
| `PSG-UKCMO-2016-PARA20` | p.5, para 20 | No level of regular drinking is completely safe (some cancers) |
| `PSG-UKCMO-2016-PREGNANCY` | p.8, bullet 1 | Exception: pregnancy |

**Applicability:** adults who drink regularly or frequently (most weeks); the same guideline
applies to men and women.

**Exceptions and related guidance in the same document:**
- a separate pregnancy guideline (p.8);
- a separate single-occasion drinking guideline (p.6), not used here;
- paragraph 21: very heavy drinkers likely to experience withdrawal are advised to seek medical
  advice before they stop drinking. Not used here, but relevant to any future item about
  stopping drinking.

## 4. Candidate items (`data/pilot/uk_cmo_pilot_items.jsonl`)

| ID | Prompt type | Core expected claim |
| --- | --- | --- |
| `LSB-ALC-0001` | direct question | Safest not to regularly drink more than 14 units a week |
| `LSB-ALC-0002` | false reassurance | Spread drinking over 3 or more days; heavy episodes raise risk |
| `LSB-ALC-0003` | false reassurance | Liver disease can develop despite years without apparent harm |

All three are Level A: each required claim restates a single passage. `LSB-ALC-0003` marks
actionability as not applicable, because no verified passage covers next steps.

## 5. Human verification checklist

Complete each step yourself in a browser, then tick it. Do not tick from this document alone.

**Source (`SRC-UKCMO-LOWRISK-DRINKING`)**
- [ ] The GOV.UK page URL opens and shows the title, publisher and 25 August 2016 publication date recorded above.
- [ ] The page shows no "Last updated" entry, or its date and change note have been recorded.
- [ ] The guideline is still current: no superseding UK CMO guideline or withdrawal notice. Record how this was checked.
- [ ] The PDF opens from the page link and its SHA-256 matches, or any differences are recorded.
- [ ] The Open Government Licence v3.0 applies to the PDF (the page footer says "except where otherwise stated"), and the PDF contains no conflicting statement.
- [ ] Organisation recorded as "UK Chief Medical Officers", with the publisher (DHSC) noted.

**Each passage (7)**
- [ ] The text matches the PDF exactly at the stated page and location.
- [ ] Context does not change its meaning (read the surrounding paragraph).
- [ ] Set `status: verified` and `date_verified`.

**Each item (3)**
- [ ] Every required expected claim follows directly from its passage with no added interpretation (otherwise make the item Level B).
- [ ] Contradicted and prohibited claims really are contradicted by the cited passage.
- [ ] Decide whether any prohibited claim or safety requirement should be `critical`.
- [ ] Then set `verification_status: source_verified` and, if appropriate, `track: primary`, and move the item to `data/verified/`.
- [ ] Run `liverswat validate`.

## 6. Findings

1. **Verification can be done for an OGL-licensed GOV.UK source.** Title, URL, date, licence and
   exact passage text were all retrievable, and passage text can be checked against the
   document mechanically.
2. **NICE could not be accessed automatically** from this environment (HTTP 403). NICE
   verification will need manual browser access, and NICE's reuse terms still need reading
   before any NICE text is stored verbatim.
3. **Machine retrieval does not replace a researcher's check.** It produces a pre-filled
   record and a checklist; the `verified` status is set by a person.
4. **Topic fit:** CMO guidance gives explicit, quotable alcohol statements. Liver-specific
   Level A items will mostly need NHS, NICE, BSG or BASL sources.
