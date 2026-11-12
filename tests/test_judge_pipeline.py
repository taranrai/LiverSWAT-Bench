"""Full pipeline with mock judges: evaluate -> score -> judge -> report -> compare."""

from __future__ import annotations

import csv
import json

import pytest
from typer.testing import CliRunner

from liverswat_bench.cli import EXIT_INVALID, app
from tests.conftest import REPO_ROOT

runner = CliRunner()
DATA = ["--data-dir", str(REPO_ROOT / "data")]


def invoke(*args):
    result = runner.invoke(app, list(args))
    return result


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    monkeypatch.chdir(REPO_ROOT)  # mock script paths are repo-relative
    run = tmp_path / "pipe"
    steps = [
        ("evaluate", "--model", "mock-scripted", "--dataset", "data/examples/demo_items.jsonl",
         "--output-dir", str(tmp_path), "--experiment-id", "pipe", *DATA),
        ("score", "--results", str(run), *DATA),
        ("judge", "--results", str(run), "--judge", "mock-judge-a", "--judge", "mock-judge-b",
         "--judge", "mock-judge-broken", "--prompt-variant", "v1", "--prompt-variant", "v1-alt",
         "--repeats", "2", *DATA),
        ("report", "--results", str(run)),
    ]  # fmt: skip
    outputs = []
    for step in steps:
        result = invoke(*step)
        assert result.exit_code == 0, (step[0], result.output)
        outputs.append(result.output)
    return run, outputs


def test_full_pipeline_outputs(pipeline):
    run, outputs = pipeline
    judge_out = outputs[2]
    assert "Judge mock-judge-a: 20 judgement(s) {'ok': 20}" in judge_out
    assert "Judge mock-judge-broken: 20 judgement(s) {'invalid_output': 20}" in judge_out
    assert "NOT CLINICAL EXPERT REVIEW" in judge_out

    report = run / "report"
    for name in ("report.md", "summary.json", "combined_scores.jsonl", "combined_scores.csv",
                 "oversight.json"):  # fmt: skip
        assert (report / name).is_file(), name

    combined = {
        json.loads(line)["question_id"]: json.loads(line)
        for line in (report / "combined_scores.jsonl").read_text().splitlines()
    }

    def dim(qid, name):
        return next(d for d in combined[qid]["dimensions"] if d["dimension"] == name)

    # Judge B's hallucinated reference was invalidated, so it does not count.
    assert dim("DEMO-0002", "factual_accuracy")["judge_statuses"]["mock-judge-b"] == "invalid"
    # Rule score is preserved where rules scored.
    assert dim("DEMO-0002", "factual_accuracy")["combined_source"] == "rule"
    assert dim("DEMO-0002", "factual_accuracy")["combined_score"] == 0
    # Judges disagree on DEMO-0003 safety; the rule abstained for review -> stays abstained.
    d3 = dim("DEMO-0003", "safety_behaviour")
    assert d3["consensus"] == "judges_disagree" and d3["combined_status"] == "abstained"
    # A judgement-only dimension is filled by consensus.
    assert dim("DEMO-0001", "actionability")["combined_source"] == "judge_consensus"
    # The broken judge is listed as having no valid output.
    assert combined["DEMO-0001"]["judges_without_valid_output"] == ["mock-judge-broken"]

    summary = json.loads((report / "summary.json").read_text())
    judges = summary["judges"]
    assert any("NOT CLINICAL EXPERT REVIEW" in label for label in judges["labels"])
    assert any("UNVERIFIED EVIDENCE" in label for label in judges["labels"])
    assert len(judges["dangerous_claims"]) == 5
    assert summary["partitions"]["primary"]["n_records"] == 0

    oversight = json.loads((report / "oversight.json").read_text())
    assert oversight["per_judge"]["mock-judge-broken"]["mean_retries"] == 2.0
    assert oversight["per_judge"]["mock-judge-b"]["n_validation_issues"] == 8
    sens = oversight["prompt_sensitivity"]["mock-judge-a"]["variants"]["v1-alt"]
    assert sens["exact_agreement"] < 1.0
    assert oversight["stability_across_repeats"]["mock-judge-a"]["identical_across_repeats"] == 1.0

    md = (report / "report.md").read_text()
    assert "## Automated LLM judges" in md
    assert "DEMO-0003 | safety_behaviour | judge_vs_judge" in md
    rows = list(csv.DictReader((report / "combined_scores.csv").open()))
    assert len(rows) == 5


def test_compare_includes_judge_view(pipeline, tmp_path):
    run, _ = pipeline
    result = invoke("compare", "--results", str(run), "--output-dir", str(tmp_path / "cmp"))
    assert result.exit_code == 0, result.output
    md = (tmp_path / "cmp" / "comparison.md").read_text()
    assert "Combined rule + judge view" in md
    data = json.loads((tmp_path / "cmp" / "comparison.json").read_text())
    row = next(r for r in data["rows"] if r["partition"] == "non_primary")
    assert row["judge_vs_judge_disagreements"] == 1
    assert row["judge_flagged_dangerous_records"] == 2


def test_report_policy_option(pipeline):
    run, _ = pipeline
    result = invoke("report", "--results", str(run), "--policy", "rules_first")
    assert result.exit_code == 0, result.output
    bad = invoke("report", "--results", str(run), "--policy", "judges_win")
    assert bad.exit_code == EXIT_INVALID
    assert "unknown policy" in bad.output


def test_judge_refuses_overwrite_and_unknown_config(pipeline):
    run, _ = pipeline
    again = invoke("judge", "--results", str(run), "--judge", "mock-judge-a", *DATA)
    assert again.exit_code == EXIT_INVALID and "already exists" in again.output
    missing = invoke("judge", "--results", str(run), "--judge", "no-such-judge", *DATA)
    assert missing.exit_code == EXIT_INVALID and "cannot read judge config" in missing.output
    variant = invoke("judge", "--results", str(run), "--judge", "mock-judge-a", "--overwrite",
                     "--prompt-variant", "v9", *DATA)  # fmt: skip
    assert variant.exit_code == EXIT_INVALID and "unknown prompt version" in variant.output


def test_judge_on_non_run_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    result = invoke("judge", "--results", str(tmp_path), "--judge", "mock-judge-a", *DATA)
    assert result.exit_code == EXIT_INVALID
    assert "not a run directory" in result.output


def test_compare_mixed_judged_and_unjudged_runs(pipeline, tmp_path):
    """Regression: CSV columns must cover rows from judged and unjudged runs."""
    run, _ = pipeline
    plain = tmp_path / "plain"
    for step in (
        ("evaluate", "--model", "mock", "--dataset", "data/pilot/uk_cmo_pilot_items.jsonl",
         "--output-dir", str(tmp_path), "--experiment-id", "plain", *DATA),
        ("score", "--results", str(plain), *DATA),
    ):  # fmt: skip
        assert invoke(*step).exit_code == 0
    result = invoke(
        "compare", "--results", str(plain), "--results", str(run),
        "--output-dir", str(tmp_path / "mixed"),
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader((tmp_path / "mixed" / "comparison.csv").open()))
    assert len(rows) == 4
    assert "judge_vs_judge_disagreements" in rows[0]
    by_run = {(r["experiment_id"], r["partition"]): r for r in rows}
    assert by_run[("plain", "non_primary")]["judges"] == ""
    assert by_run[("pipe", "non_primary")]["judge_vs_judge_disagreements"] == "1"
