# Contributing to LiverSWAT-Bench

Thank you for your interest. This is a research benchmark, so data integrity comes before volume.

## Ground rules

- **Never fabricate** evidence, quotations, citations, URLs, dates or results.
- Every new benchmark item must cite sources and passages in the evidence registry. Follow
  [docs/evidence_policy.md](docs/evidence_policy.md) to verify them.
- Do not mark anything `verified` or `source_verified` unless you checked it against the
  official document yourself.
- Never commit patient data, private holdout items (`data/private/`) or credentials.
- Label synthetic content `synthetic: true` and keep it out of the primary track.

## Workflow

1. Open an issue describing the change, especially for new items or changes to scoring.
2. Create a branch and make your changes.
3. Run the checks locally:
   ```bash
   pip install -e ".[dev]"
   liverswat validate
   ruff check . && ruff format --check .
   pytest
   ```
4. If you changed a Pydantic model, regenerate the schemas with `python scripts/export_schemas.py`.
5. Open a pull request that explains what you verified and how.

## Adding a benchmark item

1. Add or verify the source in `data/evidence/sources.jsonl`.
2. Add the passage in `data/evidence/passages.jsonl`, respecting the source's reuse terms.
3. Add the item to a `*items.jsonl` file in `data/verified/` (or `data/experimental/`).
4. Choose the evidence level honestly: Level A only if the expected answer follows directly
   from the passage text.

## Code style

Python 3.11+, formatted and linted with Ruff (configuration in `pyproject.toml`). Tests use
pytest.
