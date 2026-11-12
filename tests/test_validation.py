from __future__ import annotations

import copy

from liverswat_bench.datasets import discover_files, validate_dataset
from tests.conftest import REPO_ROOT, write_jsonl


def run(tmp_path, items, sources, passages):
    item_file = write_jsonl(tmp_path / "items.jsonl", items)
    return validate_dataset([item_file], [sources], [passages])


def messages(report) -> list[str]:
    return [i.message for i in report.issues]


def test_repository_data_is_valid():
    items, sources, passages = discover_files(REPO_ROOT / "data")
    report = validate_dataset(items, sources, passages)
    assert report.ok, "\n".join(str(i) for i in report.issues)
    assert sum(report.items_per_file.values()) == 5


def test_duplicate_question_ids(tmp_path, demo_items, demo_source_file, demo_passage_file):
    items = [demo_items[0], copy.deepcopy(demo_items[0])]
    report = run(tmp_path, items, demo_source_file, demo_passage_file)
    assert any("duplicate question_id 'DEMO-0001'" in m for m in messages(report))


def test_unknown_source_and_passage(tmp_path, demo_item, demo_source_file, demo_passage_file):
    demo_item["source_ids"] = ["SRC-NOPE"]
    demo_item["evidence_passage_ids"] = ["PSG-NOPE"]
    for group in ("expected_claims", "safety_requirements"):
        for entry in demo_item[group]:
            entry["evidence_passage_ids"] = ["PSG-NOPE"]
    report = run(tmp_path, [demo_item], demo_source_file, demo_passage_file)
    msgs = messages(report)
    assert any("unknown source_id 'SRC-NOPE'" in m for m in msgs)
    assert any("unknown evidence_passage_id 'PSG-NOPE'" in m for m in msgs)


def test_passage_from_unlisted_source(tmp_path, demo_item, demo_source_file, demo_passage_file):
    # PSG-DEMO-0001 belongs to SRC-DEMO-0001; list only the other source.
    demo_item["source_ids"] = ["SRC-DEMO-0002"]
    report = run(tmp_path, [demo_item], demo_source_file, demo_passage_file)
    assert any("not listed in source_ids" in m for m in messages(report))


def test_real_item_cannot_cite_synthetic_source(
    tmp_path, demo_item, demo_source_file, demo_passage_file
):
    demo_item.update(synthetic=False, track="experimental")
    report = run(tmp_path, [demo_item], demo_source_file, demo_passage_file)
    assert any("is synthetic but item synthetic=False" in m for m in messages(report))


def test_source_verified_item_needs_verified_evidence(tmp_path):
    sources = write_jsonl(
        tmp_path / "sources.jsonl",
        [{"source_id": "SRC-NICE-T", "organisation": "NICE", "title": "T"}],
    )
    passages = write_jsonl(
        tmp_path / "passages.jsonl",
        [
            {
                "passage_id": "PSG-NICE-T-1",
                "source_id": "SRC-NICE-T",
                "section": "1",
                "locator": "1.1",
                "text_type": "locator_only",
            }
        ],
    )
    item = {
        "question_id": "LSB-T-0001",
        "benchmark_version": "0.1.0",
        "topic": "alcohol",
        "subtopic": "s",
        "question": "q?",
        "intended_audience": "general_public",
        "prompt_type": "direct_question",
        "difficulty": "basic",
        "evidence_level": "A",
        "verification_status": "source_verified",
        "track": "primary",
        "synthetic": False,
        "source_ids": ["SRC-NICE-T"],
        "evidence_passage_ids": ["PSG-NICE-T-1"],
        "expected_claims": [
            {"claim_id": "c1", "text": "t", "evidence_passage_ids": ["PSG-NICE-T-1"]}
        ],
        "scoring_rubric": [
            {"dimension": d}
            for d in (
                "factual_accuracy",
                "safety_behaviour",
                "uk_evidence_alignment",
                "actionability",
                "communication_quality",
                "uncertainty_handling",
            )
        ],
        "risk_level": "low",
        "created_at": "2026-11-12T00:00:00Z",
        "updated_at": "2026-11-12T00:00:00Z",
    }
    report = run(tmp_path, [item], sources, passages)
    msgs = messages(report)
    assert any("source 'SRC-NICE-T' has status 'unverified'" in m for m in msgs)
    assert any("passage 'PSG-NICE-T-1' has status 'unverified'" in m for m in msgs)


def test_discovery_skips_private(tmp_path):
    (tmp_path / "private").mkdir()
    (tmp_path / "private" / "holdout_items.jsonl").write_text("")
    (tmp_path / "public_items.jsonl").write_text("")
    items, _, _ = discover_files(tmp_path)
    assert [p.name for p in items] == ["public_items.jsonl"]
