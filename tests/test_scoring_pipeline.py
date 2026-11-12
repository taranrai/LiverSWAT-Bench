"""End-to-end tests: evaluate (mock) -> score -> report -> compare. No GPU, API or model."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from liverswat_bench.datasets import discover_files
from liverswat_bench.evaluation.eligibility import primary_eligibility
from liverswat_bench.evaluation.runner import run_evaluation
from liverswat_bench.evaluation.score_run import ScoringError, score_run
from liverswat_bench.evidence.registry import EvidenceRegistry
from liverswat_bench.reporting import (
    ReportError,
    load_scored_run,
    summarise_run,
    write_comparison,
    write_report,
)
from tests import scoring_fixtures as fx
from tests.conftest import REPO_ROOT, write_jsonl

MOCK = REPO_ROOT / "configs" / "models" / "mock.yaml"
SCRIPTED = REPO_ROOT / "configs" / "models" / "mock-scripted.yaml"
DEMO = REPO_ROOT / "data" / "examples" / "demo_items.jsonl"
PILOT = REPO_ROOT / "data" / "pilot" / "uk_cmo_pilot_items.jsonl"
_, SOURCES, PASSAGES = discover_files(REPO_ROOT / "data")


def evaluate(tmp_path, config, dataset, exp, sources=SOURCES, passages=PASSAGES):
    return run_evaluation(
        model_config_path=config,
        dataset_path=dataset,
        source_files=sources,
        passage_files=passages,
        output_dir=tmp_path,
        experiment_id=exp,
        repo_root=REPO_ROOT,
    )


@pytest.fixture
def scripted_run(tmp_path, monkeypatch):
    monkeypatch.chdir(REPO_ROOT)  # script_path in the config is repo-relative
    run = evaluate(tmp_path, SCRIPTED, DEMO, "scripted")
    score_run(run.output_dir, source_files=SOURCES, passage_files=PASSAGES)
    return run.output_dir


# ------------------------------------------------------------- eligibility


def verified_registry(tmp_path: Path, passage_status: str = "verified") -> tuple[Path, Path]:
    sources = write_jsonl(
        tmp_path / "t_sources.jsonl",
        [
            {
                "source_id": "SRC-TEST-VERIFIED",
                "organisation": "NHS",
                "title": "TEST FIXTURE SOURCE (not a real document)",
                "url": "https://example.org/test-fixture",
                "date_accessed": "2026-11-12",
                "licence": "test fixture",
                "source_status": "verified",
            }
        ],
    )
    passage = {
        "passage_id": "PSG-TEST-1",
        "source_id": "SRC-TEST-VERIFIED",
        "section": "fixture",
        "locator": "fixture",
        "text_type": "locator_only",
        "status": passage_status,
    }
    if passage_status == "verified":
        passage["date_verified"] = "2026-11-12"
    passages = write_jsonl(tmp_path / "t_passages.jsonl", [passage])
    review = {
        "timestamp": "2026-11-12T00:00:00Z",
        "source_id": "SRC-TEST-VERIFIED",
        "check_type": "human_review",
        "result": "confirmed",
        "performed_by": "TEST FIXTURE REVIEWER",
    }
    write_jsonl(
        tmp_path / "verification_log.jsonl",
        [review, {**review, "passage_id": "PSG-TEST-1"}],
    )
    return sources, passages


def primary_item_dict() -> dict:
    data = fx.item_dict(
        question_id="TEST-PRIMARY-0001",
        question="[TEST FIXTURE] How much is it safest to drink each week?",
        verification_status="source_verified",
        track="primary",
        synthetic=False,
        source_ids=["SRC-TEST-VERIFIED"],
        evidence_passage_ids=["PSG-TEST-1"],
    )
    for group in ("expected_claims", "contradicted_claims", "prohibited_claims"):
        for entry in data[group]:
            if entry.get("evidence_passage_ids"):
                entry["evidence_passage_ids"] = ["PSG-TEST-1"]
    return data


def test_demo_items_are_never_primary_eligible():
    registry, _ = EvidenceRegistry.load(SOURCES, PASSAGES)
    reasons = primary_eligibility(fx.make_item(), registry)
    assert "synthetic item" in reasons
    assert "verification status draft" in reasons
    assert "track demo" in reasons


def test_pilot_items_are_not_primary_eligible(tmp_path):
    run = evaluate(tmp_path, MOCK, PILOT, "pilot")
    result = score_run(run.output_dir, source_files=SOURCES, passage_files=PASSAGES)
    assert result.manifest.n_primary_eligible_records == 0
    summary = summarise_run(load_scored_run(run.output_dir))
    reasons = summary["partitions"]["non_primary"]["ineligibility_reasons"]
    assert reasons["verification status source_pending"] == 3
    assert reasons["source SRC-UKCMO-LOWRISK-DRINKING is unverified"] == 3


def test_verified_primary_item_is_eligible_and_reported_as_primary(tmp_path):
    sources, passages = verified_registry(tmp_path)
    dataset = write_jsonl(tmp_path / "primary_items.jsonl", [primary_item_dict()])
    run = evaluate(tmp_path, MOCK, dataset, "primary", [sources], [passages])
    result = score_run(run.output_dir, source_files=[sources], passage_files=[passages])
    assert result.manifest.n_primary_eligible_records == 1
    summary = summarise_run(load_scored_run(run.output_dir))
    assert summary["partitions"]["primary"]["n_records"] == 1
    assert summary["partitions"]["non_primary"]["n_records"] == 0


def test_eligibility_is_rechecked_against_current_registry(tmp_path):
    sources, passages = verified_registry(tmp_path)
    dataset = write_jsonl(tmp_path / "primary_items.jsonl", [primary_item_dict()])
    run = evaluate(tmp_path, MOCK, dataset, "recheck", [sources], [passages])
    # The passage is later marked as needing re-verification.
    stale_dir = tmp_path / "stale"
    stale_dir.mkdir()
    _, stale = verified_registry(stale_dir, passage_status="needs_reverification")
    registry, _ = EvidenceRegistry.load([sources], [stale])
    item = fx.make_item(**primary_item_dict())
    assert "passage PSG-TEST-1 is needs_reverification" in primary_eligibility(item, registry)
    with pytest.raises(ScoringError, match="failed validation"):
        score_run(run.output_dir, source_files=[sources], passage_files=[stale])


# ------------------------------------------------------- scoring pipeline


def test_scripted_run_scores_and_reports(scripted_run):
    run = load_scored_run(scripted_run)
    by_q = {s.question_id: s for s in run.scores}
    dims = {d.dimension.value: d for d in by_q["DEMO-0005"].dimension_scores}
    assert dims["safety_behaviour"].score == 0
    assert [f.status for f in by_q["DEMO-0005"].critical_flags] == ["rule_detected"]
    assert {d.dimension.value: d.score for d in by_q["DEMO-0002"].dimension_scores}[
        "factual_accuracy"
    ] == 0
    assert any(c.outcome == "needs_review" for c in by_q["DEMO-0003"].checks)

    paths = write_report(run, scripted_run / "report")
    md = paths["report_md"].read_text()
    assert "SYNTHETIC DEMONSTRATION DATA" in md
    assert "NOT A CLINICAL SAFETY ASSESSMENT" in md
    assert "No primary benchmark scores are reported" in md
    assert "DEMO-0005 | 0 | p1 (prohibited_claim) | rule_detected" in md

    summary = json.loads(paths["summary_json"].read_text())
    non_primary = summary["partitions"]["non_primary"]
    assert summary["partitions"]["primary"]["n_records"] == 0
    assert non_primary["critical_flags"]["n_records_rule_detected"] == 1
    assert non_primary["dimensions"]["actionability"]["n_records"]["abstained"] == 5
    assert non_primary["dimensions"]["uk_evidence_alignment"]["n_records"]["not_applicable"] == 1

    rows = list(csv.DictReader(paths["item_scores_csv"].open()))
    assert len(rows) == 5
    assert {r["primary_eligible"] for r in rows} == {"False"}
    dim_rows = list(csv.DictReader(paths["dimension_summary_csv"].open()))
    assert len(dim_rows) == 12  # 2 partitions x 6 dimensions


def test_case_level_aggregation_averages_trials_first(tmp_path):
    run = run_evaluation(
        model_config_path=MOCK, dataset_path=DEMO, source_files=SOURCES,
        passage_files=PASSAGES, output_dir=tmp_path, experiment_id="trials", trials=3,
        repo_root=REPO_ROOT,
    )  # fmt: skip
    score_run(run.output_dir, source_files=SOURCES, passage_files=PASSAGES)
    summary = summarise_run(load_scored_run(run.output_dir))
    factual = summary["partitions"]["non_primary"]["dimensions"]["factual_accuracy"]
    assert factual["n_records"]["scored"] == 15
    assert factual["n_items_scored"] == 5  # items, not records


def test_generation_errors_are_counted_as_missing(tmp_path):
    cfg = tmp_path / "failing.yaml"
    cfg.write_text(MOCK.read_text() + "backend_options:\n  fail_if_prompt_contains: ['yellow']\n")
    run = evaluate(tmp_path, cfg, DEMO, "errors")
    score_run(run.output_dir, source_files=SOURCES, passage_files=PASSAGES)
    ps = summarise_run(load_scored_run(run.output_dir))["partitions"]["non_primary"]
    assert ps["n_generation_errors"] == 1
    assert ps["dimensions"]["factual_accuracy"]["n_records"]["missing"] == 1


def test_score_refuses_to_overwrite(scripted_run):
    with pytest.raises(ScoringError, match="already exists"):
        score_run(scripted_run, source_files=SOURCES, passage_files=PASSAGES)
    score_run(scripted_run, source_files=SOURCES, passage_files=PASSAGES, overwrite=True)


def test_score_rejects_changed_dataset(tmp_path, demo_items):
    dataset = write_jsonl(tmp_path / "copy_items.jsonl", demo_items)
    run = evaluate(tmp_path, MOCK, dataset, "changed")
    write_jsonl(dataset, demo_items[:4])
    with pytest.raises(ScoringError, match="has changed since the run"):
        score_run(run.output_dir, source_files=SOURCES, passage_files=PASSAGES)


def test_score_rejects_non_run_directory(tmp_path):
    with pytest.raises(ScoringError, match="not a run directory"):
        score_run(tmp_path, source_files=SOURCES, passage_files=PASSAGES)


def test_report_requires_scores(tmp_path):
    run = evaluate(tmp_path, MOCK, DEMO, "unscored")
    with pytest.raises(ReportError, match="run 'liverswat score' first"):
        load_scored_run(run.output_dir)


# ---------------------------------------------------------------- compare


def test_compare_runs(scripted_run, tmp_path):
    plain = evaluate(tmp_path, MOCK, PILOT, "plain-pilot")
    score_run(plain.output_dir, source_files=SOURCES, passage_files=PASSAGES)
    runs = [load_scored_run(scripted_run), load_scored_run(plain.output_dir)]
    paths = write_comparison(runs, tmp_path / "cmp")
    data = json.loads(paths["comparison_json"].read_text())
    assert len(data["rows"]) == 4
    assert any("different datasets" in w for w in data["warnings"])
    assert any("No run contains primary-eligible items" in w for w in data["warnings"])
    md = paths["comparison_md"].read_text()
    assert "Paired, case-level statistical comparison is planned for Milestone 7" in md
