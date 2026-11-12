"""Judge checkpoints: an interrupted judge step resumes without repeating judge results."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from liverswat_bench.cli import app
from liverswat_bench.datasets import discover_files
from liverswat_bench.judges.runner import JudgeRunError, checkpoint_paths, judge_run
from liverswat_bench.models import create_adapter
from tests.conftest import REPO_ROOT, load_jsonl

JUDGE = REPO_ROOT / "configs/judges/mock-judge-a.yaml"


class Interrupted(Exception):
    pass


class CountingAdapter:
    """Wrap a real mock adapter. Count calls and optionally stop after ``stop_after`` calls."""

    def __init__(self, inner, stop_after: int | None = None):
        self.inner, self.stop_after, self.calls = inner, stop_after, 0

    def generate(self, messages, params):
        if self.stop_after is not None and self.calls >= self.stop_after:
            raise Interrupted
        self.calls += 1
        return self.inner.generate(messages, params)

    def runtime_info(self):
        return self.inner.runtime_info()

    def close(self):
        self.inner.close()


@pytest.fixture
def run_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    result = CliRunner().invoke(
        app,
        ["evaluate", "--model", "mock-scripted", "--dataset", "data/examples/demo_items.jsonl",
         "--output-dir", str(tmp_path), "--experiment-id", "ck",
         "--data-dir", str(REPO_ROOT / "data")],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    _, sources, passages = discover_files(REPO_ROOT / "data")
    return tmp_path / "ck", {"source_files": sources, "passage_files": passages}


def judge(run_dir, files, adapter, **kw):
    return judge_run(run_dir, JUDGE, adapter_factory=lambda cfg: adapter, **files, **kw)


def interrupt(run_dir, files, stop_after=2, **kw):
    adapter = CountingAdapter(create_adapter(_judge_model()), stop_after=stop_after)
    with pytest.raises(Interrupted):
        judge(run_dir, files, adapter, **kw)


def _judge_model():
    from liverswat_bench.judges.schema import load_judge_config

    return load_judge_config(JUDGE).model


def test_interrupted_step_resumes_from_checkpoint(run_dir):
    run, files = run_dir
    interrupt(run, files, stop_after=2)
    out_dir = run / "judgements"
    partial, meta = checkpoint_paths(out_dir, "mock-judge-a")
    assert not (out_dir / "mock-judge-a.jsonl").exists()
    stored = load_jsonl(partial)
    assert len(stored) == 2
    assert json.loads(meta.read_text())["prompt_versions"] == ["v1"]

    adapter = CountingAdapter(create_adapter(_judge_model()))
    result = judge(run, files, adapter)
    assert result.n_resumed == 2
    assert result.manifest.n_resumed_from_checkpoint == 2
    final = load_jsonl(out_dir / "mock-judge-a.jsonl")
    assert len(final) == result.manifest.n_judgements
    # Resumed judge results are reused unchanged; only the rest are judged again.
    assert [r["judgement_id"] for r in final[:2]] == [r["judgement_id"] for r in stored]
    not_skipped = [r for r in final[2:] if r["status"] != "skipped_no_response"]
    assert adapter.calls == len(not_skipped)
    assert not partial.exists() and not meta.exists()


def test_cut_last_checkpoint_line_is_judged_again(run_dir):
    run, files = run_dir
    interrupt(run, files, stop_after=2)
    partial, _ = checkpoint_paths(run / "judgements", "mock-judge-a")
    with partial.open("a") as f:
        f.write('{"schema_version": "1", "judgement')  # interrupted mid-line
    result = judge(run, files, CountingAdapter(create_adapter(_judge_model())))
    assert result.n_resumed == 2


def test_checkpoint_with_different_inputs_is_not_used(run_dir):
    run, files = run_dir
    interrupt(run, files, stop_after=1)
    partial, meta = checkpoint_paths(run / "judgements", "mock-judge-a")
    before = (partial.read_text(), meta.read_text())
    adapter = CountingAdapter(create_adapter(_judge_model()))
    with pytest.raises(JudgeRunError, match="different inputs"):
        judge(run, files, adapter, prompt_versions=["v1-alt"])
    assert adapter.calls == 0
    assert (partial.read_text(), meta.read_text()) == before


def test_completed_run_leaves_no_checkpoint(run_dir):
    run, files = run_dir
    judge(run, files, CountingAdapter(create_adapter(_judge_model())))
    names = sorted(p.name for p in (run / "judgements").iterdir())
    assert names == ["mock-judge-a.jsonl", "mock-judge-a.manifest.json"]
