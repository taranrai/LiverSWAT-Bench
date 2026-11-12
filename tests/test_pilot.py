"""Pilot orchestration with mock models and mock judges (no real inference)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from liverswat_bench.cli import EXIT_INVALID, app
from liverswat_bench.evaluation.records import MOCK_LABEL, REAL_LABEL, RunManifest
from liverswat_bench.evaluation.runner import status_labels
from tests.conftest import REPO_ROOT, load_jsonl

runner = CliRunner()


def pilot_config(tmp_path: Path, **overrides) -> Path:
    cfg = yaml.safe_load((REPO_ROOT / "configs/experiments/mock-pilot.yaml").read_text())
    cfg["output_dir"] = str(tmp_path / "pilot")
    cfg.update(overrides)
    path = tmp_path / "pilot.yaml"
    path.write_text(yaml.safe_dump(cfg))
    return path


@pytest.fixture
def ran(tmp_path, monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    cfg = pilot_config(tmp_path)
    result = runner.invoke(app, ["pilot", "--config", str(cfg)])
    assert result.exit_code == 0, result.output
    return tmp_path / "pilot", cfg, result.output


def test_mock_pilot_outputs_and_labels(ran):
    out, _, log = ran
    assert "[done]" in log
    summary = json.loads((out / "pilot_summary.json").read_text())
    assert summary["result_label"].startswith("MOCK TEST RESULTS")
    assert [r["evidence_condition"] for r in summary["runs"]] == ["baseline", "retrieved", "oracle"]
    for run in summary["runs"]:
        assert MOCK_LABEL in run["status_labels"]
        assert REAL_LABEL not in run["status_labels"]
        assert run["valid_model_responses"] == {"numerator": 5, "denominator": 5, "rate": 1.0}
        j = run["judges"]
        for rate in (j["judge_disagreement"], j["rule_vs_judge_material_disagreement"]):
            assert set(rate) == {"numerator", "denominator", "rate"}
    baseline = summary["runs"][0]
    variants = baseline["judges"]["prompt_sensitivity"]["mock-judge-a"]["variants"]
    assert "v1-alt" in variants
    assert summary["runs"][1]["retrieval_oracle_recall_mean"] is not None
    md = (out / "pilot_summary.md").read_text()
    assert "MOCK TEST RESULTS" in md and "(5/5)" in md
    assert (out / "comparison" / "comparison.md").is_file()
    for name in ("mock-scripted__baseline", "mock-scripted__retrieved", "mock-scripted__oracle"):
        assert (out / name / "report" / "report.md").is_file()


def test_resume_skips_completed_steps(ran):
    _, cfg, _ = ran
    again = runner.invoke(app, ["pilot", "--config", str(cfg)])
    assert again.exit_code == 0, again.output
    assert "[evaluate]" not in again.output
    assert "[judge]" not in again.output
    assert "[done]" in again.output


def test_interrupted_run_is_not_silently_reused(ran):
    out, cfg, _ = ran
    (out / "mock-scripted__oracle" / "manifest.json").unlink()
    result = runner.invoke(app, ["pilot", "--config", str(cfg)])
    assert result.exit_code == EXIT_INVALID
    assert "interrupted run" in result.output


def test_summarise_only(ran):
    out, cfg, _ = ran
    (out / "pilot_summary.md").unlink()
    result = runner.invoke(app, ["pilot", "--config", str(cfg), "--summarise-only"])
    assert result.exit_code == 0, result.output
    assert (out / "pilot_summary.md").is_file()


def test_pilot_results_are_reproducible(tmp_path, monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    outs = []
    for name in ("a", "b"):
        d = tmp_path / name
        d.mkdir()
        cfg = pilot_config(d, conditions=["oracle"], prompt_sensitivity=None)
        assert runner.invoke(app, ["pilot", "--config", str(cfg)]).exit_code == 0
        outs.append(d / "pilot" / "mock-scripted__oracle")

    def stable(run_dir: Path):
        responses = [r["response"]["text"] for r in load_jsonl(run_dir / "responses.jsonl")]
        scores = [
            [(d["dimension"], d["status"], d["score"]) for d in s["dimension_scores"]]
            for s in load_jsonl(run_dir / "scores.jsonl")
        ]
        judged = [
            [(d["dimension"], d["status"], d.get("score")) for d in j["dimensions"]]
            for j in load_jsonl(run_dir / "judgements" / "mock-judge-a.jsonl")
        ]
        return responses, scores, judged

    assert stable(outs[0]) == stable(outs[1])


def test_invalid_pilot_config(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("pilot_id: x\n")
    result = runner.invoke(app, ["pilot", "--config", str(bad)])
    assert result.exit_code == EXIT_INVALID
    assert "invalid pilot configuration" in result.output


def test_status_labels_distinguish_real_and_mock():
    assert MOCK_LABEL in status_labels([], "mock")
    assert REAL_LABEL in status_labels([], "ollama")
    assert REAL_LABEL in status_labels([], "transformers")


def test_real_model_configs_are_pinned():
    from liverswat_bench.models.config import load_model_config

    for path in sorted((REPO_ROOT / "configs/models").glob("ollama-*.yaml")):
        cfg = load_model_config(path)
        assert cfg.revision_pinned, path.name
        assert cfg.licence and cfg.quantisation, path.name
    manifest_fields = RunManifest.model_fields
    assert "evidence_condition" in manifest_fields
