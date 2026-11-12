from __future__ import annotations

import pytest
from pydantic import ValidationError

from liverswat_bench.evidence import EvidencePassage, EvidenceRegistry, Source
from tests.conftest import REPO_ROOT, load_jsonl, write_jsonl

REAL_SOURCES = REPO_ROOT / "data" / "evidence" / "sources.jsonl"


def base_source(**kw) -> dict:
    data = {"source_id": "SRC-NICE-TEST", "organisation": "NICE", "title": "A title"}
    data.update(kw)
    return data


def test_real_registry_entries_are_all_unverified():
    # No source has been checked against its official document yet. If this
    # fails, make sure the verification really happened (see docs/evidence_policy.md).
    rows = load_jsonl(REAL_SOURCES)
    assert rows, "expected candidate sources in the registry"
    assert {Source.model_validate(r).source_status for r in rows} == {"unverified"}


def test_verified_source_requires_provenance():
    with pytest.raises(ValidationError, match="verified sources require"):
        Source.model_validate(base_source(source_status="verified"))


def test_verified_source_accepted_with_provenance():
    s = Source.model_validate(
        base_source(
            source_status="verified",
            url="https://www.nice.org.uk/guidance/x",
            date_accessed="2026-11-01",
            licence="NICE reuse terms",
        )
    )
    assert s.source_status == "verified"


def test_synthetic_source_cannot_be_verified():
    with pytest.raises(ValidationError, match="never be marked verified"):
        Source.model_validate(
            base_source(
                organisation="SYNTHETIC_DEMO",
                synthetic=True,
                source_status="verified",
                url="https://example.org",
                date_accessed="2026-11-01",
                licence="x",
            )
        )


def test_real_org_cannot_be_flagged_synthetic():
    with pytest.raises(ValidationError, match="SYNTHETIC_DEMO"):
        Source.model_validate(base_source(synthetic=True))


def test_dates_must_be_ordered():
    with pytest.raises(ValidationError, match="last_updated_date"):
        Source.model_validate(
            base_source(publication_date="2020-01-01", last_updated_date="2019-01-01")
        )


def test_passage_text_rules():
    base = {"passage_id": "PSG-X-1", "source_id": "SRC-X", "section": "1", "locator": "1.1"}
    with pytest.raises(ValidationError, match="require text"):
        EvidencePassage.model_validate({**base, "text_type": "verbatim"})
    with pytest.raises(ValidationError, match="must not store text"):
        EvidencePassage.model_validate({**base, "text_type": "locator_only", "text": "x"})
    with pytest.raises(ValidationError, match="date_verified"):
        EvidencePassage.model_validate({**base, "text_type": "locator_only", "status": "verified"})


def test_registry_flags_unknown_source_and_duplicates(tmp_path, demo_source_file):
    passages = write_jsonl(
        tmp_path / "p.jsonl",
        [
            {
                "passage_id": "PSG-A-1",
                "source_id": "SRC-MISSING",
                "section": "s",
                "locator": "l",
                "text_type": "locator_only",
            },
            {
                "passage_id": "PSG-A-1",
                "source_id": "SRC-MISSING",
                "section": "s",
                "locator": "l",
                "text_type": "locator_only",
            },
        ],
    )
    _, issues = EvidenceRegistry.load([demo_source_file], [passages])
    messages = [i.message for i in issues]
    assert any("unknown source_id" in m for m in messages)
    assert any("duplicate passage_id" in m for m in messages)


def test_registry_reports_invalid_json(tmp_path):
    bad = tmp_path / "s.jsonl"
    bad.write_text('{"source_id": \n')
    _, issues = EvidenceRegistry.load([bad], [])
    assert len(issues) == 1
    assert "invalid JSON" in issues[0].message
    assert issues[0].line == 1
