from __future__ import annotations

import pytest
from typer.testing import CliRunner

from liverswat_bench.cli import EXIT_INVALID, EXIT_NOT_IMPLEMENTED, app
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
        ["evaluate", "--model", "m", "--dataset", "d.jsonl"],
        ["judge", "--results", "r"],
        ["compare", "--results", "r"],
        ["report", "--results", "r"],
    ],
)
def test_future_commands_fail_clearly(args):
    result = runner.invoke(app, args)
    assert result.exit_code == EXIT_NOT_IMPLEMENTED
    assert "not implemented yet" in result.output
