from __future__ import annotations

import pytest
from pydantic import ValidationError

from liverswat_bench.datasets.schema import BenchmarkItem


def make(item: dict) -> BenchmarkItem:
    return BenchmarkItem.model_validate(item)


def test_demo_items_parse(demo_items):
    parsed = [make(i) for i in demo_items]
    assert len(parsed) == 5
    assert all(p.synthetic and p.track == "demo" for p in parsed)


@pytest.mark.parametrize(
    "field",
    [
        "question_id",
        "question",
        "topic",
        "scoring_rubric",
        "evidence_level",
        "verification_status",
        "created_at",
    ],
)
def test_missing_required_field(demo_item, field):
    del demo_item[field]
    with pytest.raises(ValidationError, match=field):
        make(demo_item)


def test_unknown_field_rejected(demo_item):
    demo_item["unexpected"] = 1
    with pytest.raises(ValidationError, match="unexpected"):
        make(demo_item)


@pytest.mark.parametrize("status", ["verified", "approved", "clinically_validated", ""])
def test_unsupported_verification_status(demo_item, status):
    demo_item["verification_status"] = status
    with pytest.raises(ValidationError, match="verification_status"):
        make(demo_item)


def test_bad_question_id(demo_item):
    demo_item["question_id"] = "demo 1"
    with pytest.raises(ValidationError, match="question_id"):
        make(demo_item)


def test_synthetic_item_cannot_be_primary(demo_item):
    demo_item.update(track="primary", verification_status="source_verified")
    with pytest.raises(ValidationError, match="synthetic items cannot be in the primary"):
        make(demo_item)


def test_primary_requires_level_a(demo_item):
    demo_item.update(
        track="primary", verification_status="source_verified", synthetic=False, evidence_level="B"
    )
    with pytest.raises(ValidationError, match="evidence level A"):
        make(demo_item)


def test_primary_requires_source_verified(demo_item):
    demo_item.update(track="primary", synthetic=False, verification_status="source_pending")
    with pytest.raises(ValidationError, match="must be source_verified"):
        make(demo_item)


def test_level_c_cannot_be_source_verified(demo_item):
    demo_item.update(
        track="exploratory",
        synthetic=False,
        evidence_level="C",
        verification_status="source_verified",
    )
    with pytest.raises(ValidationError, match="level C"):
        make(demo_item)


def test_demo_track_requires_synthetic(demo_item):
    demo_item["synthetic"] = False
    with pytest.raises(ValidationError, match="demo-track items must be marked synthetic"):
        make(demo_item)


def test_source_verified_requires_evidence(demo_item):
    demo_item.update(
        track="exploratory",
        synthetic=False,
        evidence_level="B",
        verification_status="source_verified",
        source_ids=[],
        evidence_passage_ids=[],
        expected_claims=[],
        prohibited_claims=[],
        safety_requirements=[],
    )
    with pytest.raises(ValidationError) as exc:
        make(demo_item)
    msg = str(exc.value)
    assert "at least one source_id" in msg
    assert "at least one evidence passage" in msg


def test_claim_cites_undeclared_passage(demo_item):
    demo_item["expected_claims"][0]["evidence_passage_ids"] = ["PSG-DEMO-0999"]
    with pytest.raises(ValidationError, match="not listed in evidence_passage_ids"):
        make(demo_item)


def test_duplicate_local_ids(demo_item):
    demo_item["prohibited_claims"][0]["claim_id"] = "c1"
    with pytest.raises(ValidationError, match="duplicate claim/requirement ids"):
        make(demo_item)


def test_rubric_must_cover_every_dimension(demo_item):
    demo_item["scoring_rubric"] = demo_item["scoring_rubric"][:-1]
    with pytest.raises(ValidationError, match="missing"):
        make(demo_item)


def test_rubric_anchors_must_cover_0_to_4(demo_item):
    demo_item["scoring_rubric"][0]["anchors"] = {"0": "bad", "4": "good"}
    with pytest.raises(ValidationError, match="anchors must define exactly"):
        make(demo_item)


def test_rubric_full_anchors_accepted(demo_item):
    demo_item["scoring_rubric"][0]["anchors"] = {str(i): f"anchor {i}" for i in range(5)}
    assert make(demo_item).scoring_rubric[0].anchors[4] == "anchor 4"


def test_not_applicable_dimension_is_kept(demo_items):
    item = make(demo_items[3])
    na = [r for r in item.scoring_rubric if not r.applicable]
    assert [r.dimension for r in na] == ["uk_evidence_alignment"]


def test_updated_before_created(demo_item):
    demo_item["updated_at"] = "2020-01-01T00:00:00Z"
    with pytest.raises(ValidationError, match="updated_at"):
        make(demo_item)
