from __future__ import annotations

import pytest
from typer.testing import CliRunner

from liverswat_bench.cli import EXIT_INVALID, EXIT_NOT_IMPLEMENTED, EXIT_PARTIAL_FAILURE, app
from tests.conftest import REPO_ROOT, write_jsonl

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "liverswat-bench" in result.output


def test_validate_repository_data():
    result = runner.invoke(app, ["validate", "--data-dir", str(REPO_ROOT / "data")])
    assert result.exit_code == 0, result.output
    assert "Validation passed." in result.output


def test_validate_reports_issues(tmp_path, demo_items, demo_source_file, demo_passage_file):
    items = write_jsonl(tmp_path / "x_items.jsonl", [demo_items[0], demo_items[0]])
    result = runner.invoke(
        app,
        [
            "validate",
            "--items",
            str(items),
            "--sources",
            str(demo_source_file),
            "--passages",
            str(demo_passage_file),
        ],
    )
    assert result.exit_code == EXIT_INVALID
    assert "duplicate question_id" in result.output


def test_validate_missing_directory(tmp_path):
    result = runner.invoke(app, ["validate", "--data-dir", str(tmp_path / "nope")])
    assert result.exit_code == EXIT_INVALID
    assert "data directory not found" in result.output


def test_validate_missing_file(tmp_path):
    result = runner.invoke(
        app, ["validate", "--data-dir", str(tmp_path), "--items", str(tmp_path / "missing.jsonl")]
    )
    assert result.exit_code == EXIT_INVALID
    assert "file not found" in result.output


def test_validate_no_items(tmp_path):
    result = runner.invoke(app, ["validate", "--data-dir", str(tmp_path)])
    assert result.exit_code == EXIT_INVALID
    assert "no item files found" in result.output


@pytest.mark.parametrize(
    "args",
    [
        ["judge", "--results", "r"],
    ],
)
def test_future_commands_fail_clearly(args):
    result = runner.invoke(app, args)
    assert result.exit_code == EXIT_NOT_IMPLEMENTED
    assert "not implemented yet" in result.output


def _evaluate(tmp_path, *extra):
    return runner.invoke(
        app,
        [
            "evaluate",
            "--model",
            "mock",
            "--dataset",
            str(REPO_ROOT / "data" / "examples" / "demo_items.jsonl"),
            "--data-dir",
            str(REPO_ROOT / "data"),
            "--configs-dir",
            str(REPO_ROOT / "configs" / "models"),
            "--output-dir",
            str(tmp_path),
            *extra,
        ],
    )


def test_evaluate_mock_end_to_end(tmp_path):
    result = _evaluate(tmp_path, "--experiment-id", "cli-run")
    assert result.exit_code == 0, result.output
    assert "SYNTHETIC DEMONSTRATION DATA" in result.output
    assert "5 ok, 0 failed" in result.output
    assert (tmp_path / "cli-run" / "responses.jsonl").is_file()
    assert (tmp_path / "cli-run" / "manifest.json").is_file()


def test_evaluate_unknown_model(tmp_path):
    result = runner.invoke(
        app,
        [
            "evaluate",
            "--model",
            "no-such-model",
            "--dataset",
            str(REPO_ROOT / "data" / "examples" / "demo_items.jsonl"),
            "--data-dir",
            str(REPO_ROOT / "data"),
            "--configs-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == EXIT_INVALID
    assert "no model config found" in result.output


def test_evaluate_missing_dataset(tmp_path):
    result = runner.invoke(
        app, ["evaluate", "--model", "mock", "--dataset", str(tmp_path / "none.jsonl")]
    )
    assert result.exit_code == EXIT_INVALID
    assert "dataset not found" in result.output


def test_evaluate_partial_failure_exit_code(tmp_path):
    cfg = tmp_path / "failing.yaml"
    cfg.write_text(
        (REPO_ROOT / "configs" / "models" / "mock.yaml").read_text()
        + "backend_options:\n  fail_if_prompt_contains: ['yellow']\n"
    )
    result = runner.invoke(
        app,
        [
            "evaluate",
            "--model",
            str(cfg),
            "--dataset",
            str(REPO_ROOT / "data" / "examples" / "demo_items.jsonl"),
            "--data-dir",
            str(REPO_ROOT / "data"),
            "--output-dir",
            str(tmp_path / "out"),
        ],
    )
    assert result.exit_code == EXIT_PARTIAL_FAILURE
    assert "4 ok, 1 failed" in result.output


def _scripted_run(tmp_path):
    result = runner.invoke(
        app,
        [
            "evaluate",
            "--model",
            str(REPO_ROOT / "configs" / "models" / "mock-scripted.yaml"),
            "--dataset",
            str(REPO_ROOT / "data" / "examples" / "demo_items.jsonl"),
            "--data-dir",
            str(REPO_ROOT / "data"),
            "--output-dir",
            str(tmp_path),
            "--experiment-id",
            "cli-scripted",
        ],
    )
    assert result.exit_code == 0, result.output
    return tmp_path / "cli-scripted"


def test_score_report_compare_end_to_end(tmp_path, monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    run_dir = _scripted_run(tmp_path)
    data = ["--data-dir", str(REPO_ROOT / "data")]

    scored = runner.invoke(app, ["score", "--results", str(run_dir), *data])
    assert scored.exit_code == 0, scored.output
    assert "NOT A CLINICAL SAFETY ASSESSMENT" in scored.output
    assert "5 (0 primary-eligible)" in scored.output

    again = runner.invoke(app, ["score", "--results", str(run_dir), *data])
    assert again.exit_code == EXIT_INVALID
    assert "already exists" in again.output

    reported = runner.invoke(app, ["report", "--results", str(run_dir)])
    assert reported.exit_code == 0, reported.output
    assert (run_dir / "report" / "report.md").is_file()

    compared = runner.invoke(
        app, ["compare", "--results", str(tmp_path), "--output-dir", str(tmp_path / "cmp")]
    )
    assert compared.exit_code == 0, compared.output
    assert "Compared 1 run(s)." in compared.output
    assert (tmp_path / "cmp" / "comparison.md").is_file()


def test_report_on_unscored_run(tmp_path, monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    run_dir = _scripted_run(tmp_path)
    result = runner.invoke(app, ["report", "--results", str(run_dir)])
    assert result.exit_code == EXIT_INVALID
    assert "liverswat score" in result.output


def test_score_on_missing_directory(tmp_path):
    result = runner.invoke(
        app, ["score", "--results", str(tmp_path / "nope"), "--data-dir", str(REPO_ROOT / "data")]
    )
    assert result.exit_code == EXIT_INVALID
    assert "not a run directory" in result.output


def test_compare_without_scored_runs(tmp_path):
    result = runner.invoke(app, ["compare", "--results", str(tmp_path)])
    assert result.exit_code == EXIT_INVALID
    assert "no scored runs found" in result.output
