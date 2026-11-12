# Evidence policy

## Principles

1. **No fabrication.** No invented recommendations, quotations, citations, dates or URLs. If
   something has not been checked, the record says so.
2. **Official sources first.** Use the publisher's own page or PDF, not secondary summaries.
3. **Separation.** Sources (`data/evidence/sources.jsonl`), passages
   (`data/evidence/passages.jsonl`), benchmark items (`*items.jsonl`) and model outputs are stored
   separately.
4. **Source verification is not clinical validation.** It confirms that a document says what the
   record claims it says, and nothing more.

## Priority sources

1. National Institute for Health and Care Excellence (NICE)
2. National Health Service (NHS)
3. British Society of Gastroenterology (BSG)
4. British Association for the Study of the Liver (BASL)
5. British Liver Trust
6. UK Health Security Agency (UKHSA)
7. UK Chief Medical Officers

## Source records

Fields are defined in [`schemas/source.schema.json`](../schemas/source.schema.json). Each source
moves through these statuses:

| Status | Meaning |
| --- | --- |
| `unverified` | Candidate entry; metadata not yet checked against the official document. |
| `verified` | A researcher opened the official document and confirmed title, URL, identifier, dates and licence. |
| `needs_reverification` | Previously verified; guidance may have changed. |
| `superseded` / `withdrawn` | No longer current. Items citing it must be re-reviewed or retired. |

A `verified` source must have a `url`, `date_accessed` and `licence`, and the validator enforces
this. Synthetic (demo) sources can never be `verified`.

**Current state:** every real source in the registry is `unverified`.

- The NICE entries were recorded without browsing and must be checked before any item relies on
  them. Automated access to nice.org.uk returned HTTP 403, so NICE checks need a browser.
- The UK CMO low-risk drinking guideline was retrieved by machine in the Milestone 2 pilot. Its
  metadata and seven verbatim passages are recorded but still await a researcher's check; see
  [pilots/uk_cmo_low_risk_drinking.md](pilots/uk_cmo_low_risk_drinking.md).
- BSG, BASL, British Liver Trust and UKHSA documents have not been added yet, to avoid recording
  titles or URLs from memory.

**Machine retrieval is not verification.** An automated fetch can pre-fill a record and check
that passage text appears in a downloaded document. Only a researcher who has checked the
official document sets `verified`.

## Passage records

A passage is a specific, locatable part of a source (for example a numbered recommendation).

- `text_type: verbatim`: an exact quotation, stored **only where the licence permits reuse**.
- `text_type: paraphrase`: the researcher's own wording, where verbatim reuse is restricted.
- `text_type: locator_only`: no text stored; the `locator` identifies the passage.

A `verified` passage needs a `date_verified`.

## Manual verification workflow (for non-clinical researchers)

For each source:

1. Open the official URL. Confirm the organisation, title and guideline identifier.
2. Record the publication date, last-updated date and today's date as `date_accessed`.
3. Read the licence and reuse terms and record them in `licence` / `reuse_restrictions`.
4. Set `source_status: verified` and add a short `verification_notes` entry.

For each passage:

1. Find the passage in the official document and record its `section` and `locator`.
2. Copy the text exactly (if reuse is permitted) or paraphrase it faithfully.
3. Check that the item's expected claim follows **directly** from the passage text. If it needs
   interpretation, the item is Level B. If it needs clinical judgement, it is Level C.
4. Set `status: verified` and `date_verified`.

Run `liverswat validate` after every change.

## Evidence levels

| Level | Meaning | Benchmark use |
| --- | --- | --- |
| A | Follows from an explicit statement in an authoritative UK source. | Primary, once source-verified. |
| B | Requires combining or interpreting sources. | Exploratory only, until reviewed. |
| C | Requires clinical judgement (diagnosis, triage, medication, treatment). | Excluded; mark `expert_review_required`. |

## Re-verification

Guidance changes. Before each release:

- Recheck the `last_updated_date` of every verified source.
- Mark changed sources `needs_reverification`. Items citing them drop out of `source_verified`
  until rechecked, because the validator requires verified evidence for verified items.
- Record changes in the release notes.
