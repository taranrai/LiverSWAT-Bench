"""Integration tests for the evaluation runner, using the mock backend."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from liverswat_bench.datasets import discover_files
from liverswat_bench.evaluation.records import (
    NOT_CLINICAL_LABEL,
    SYNTHETIC_LABEL,
    UNVERIFIED_LABEL,
    ResponseRecord,
    RunManifest,
)
from liverswat_bench.evaluation.runner import EvaluationError, run_evaluation
from liverswat_bench.models import AdapterError
from tests.conftest import REPO_ROOT, load_jsonl, write_jsonl

MOCK_CONFIG = REPO_ROOT / "configs" / "models" / "mock.yaml"
DEMO = REPO_ROOT / "data" / "examples" / "demo_items.jsonl"
PILOT = REPO_ROOT / "data" / "pilot" / "uk_cmo_pilot_items.jsonl"
_, SOURCES, PASSAGES = discover_files(REPO_ROOT / "data")


def run(tmp_path: Path, dataset: Path = DEMO, **kw):
    kw.setdefault("model_config_path", MOCK_CONFIG)
    return run_evaluation(
        dataset_path=dataset,
        source_files=SOURCES,
        passage_files=PASSAGES,
        output_dir=tmp_path,
        repo_root=REPO_ROOT,
        **kw,
    )


def records(result) -> list[ResponseRecord]:
    return [ResponseRecord.model_validate(r) for r in load_jsonl(result.responses_path)]


def test_mock_run_writes_valid_records_and_manifest(tmp_path):
    result = run(tmp_path, experiment_id="demo-run")
    recs = records(result)
    assert len(recs) == 5
    assert {r.question_id for r in recs} == {f"DEMO-000{i}" for i in range(1, 6)}
    for r in recs:
        assert r.status == "ok" and r.response.text
        assert r.data_provenance.synthetic is True
        assert r.data_provenance.track == "demo"
        assert r.data_provenance.primary_eligible is False
        assert r.model.backend == "mock"
        assert r.timing.latency_s >= 0
        assert r.record_id == f"demo-run:{r.question_id}:0"

    manifest = RunManifest.model_validate_json((result.output_dir / "manifest.json").read_text())
    assert manifest.status_labels[0] == SYNTHETIC_LABEL
    assert NOT_CLINICAL_LABEL in manifest.status_labels
    assert UNVERIFIED_LABEL in manifest.status_labels
    assert manifest.n_synthetic_items == 5
    assert manifest.n_primary_eligible_items == 0
    assert (manifest.n_ok, manifest.n_error) == (5, 0)
    assert len(manifest.dataset_sha256) == 64
    assert (
        manifest.environment["git"]["commit"] is None
        or len(manifest.environment["git"]["commit"]) == 40
    )
    assert "python_version" in manifest.environment


def test_runs_are_reproducible(tmp_path):
    a = records(run(tmp_path, experiment_id="a"))
    b = records(run(tmp_path, experiment_id="b"))
    assert [r.response.text for r in a] == [r.response.text for r in b]


def test_real_unverified_items_are_labelled_but_not_synthetic(tmp_path):
    result = run(tmp_path, dataset=PILOT, experiment_id="pilot")
    recs = records(result)
    assert len(recs) == 3
    assert all(not r.data_provenance.synthetic for r in recs)
    assert all(r.data_provenance.verification_status == "source_pending" for r in recs)
    assert all(not r.data_provenance.primary_eligible for r in recs)
    assert SYNTHETIC_LABEL not in result.manifest.status_labels
    assert UNVERIFIED_LABEL in result.manifest.status_labels


def test_trials_use_incrementing_seeds(tmp_path):
    recs = records(run(tmp_path, experiment_id="t", trials=3, limit=1))
    assert [r.trial for r in recs] == [0, 1, 2]
    assert [r.generation.seed for r in recs] == [0, 1, 2]
    assert len({r.response.text for r in recs}) == 3


def test_generation_errors_are_recorded_not_fatal(tmp_path):
    cfg = tmp_path / "failing.yaml"
    cfg.write_text(
        MOCK_CONFIG.read_text().replace("config_id: mock", "config_id: failing")
        + "backend_options:\n  fail_if_prompt_contains: ['yellow']\n"
    )
    result = run(tmp_path, model_config_path=cfg, experiment_id="f")
    recs = records(result)
    failed = [r for r in recs if r.status == "error"]
    assert [r.question_id for r in failed] == ["DEMO-0001"]
    assert failed[0].response.text is None
    assert "mock failure" in failed[0].error
    assert (result.manifest.n_ok, result.manifest.n_error) == (4, 1)


def test_retired_items_are_skipped(tmp_path, demo_items):
    demo_items[0]["verification_status"] = "retired"
    dataset = write_jsonl(tmp_path / "retired_items.jsonl", demo_items)
    result = run(tmp_path, dataset=dataset, experiment_id="r")
    assert result.manifest.n_items == 4
    assert result.manifest.n_items_skipped_retired == 1


def test_invalid_dataset_is_refused(tmp_path, demo_items):
    demo_items[0]["source_ids"] = ["SRC-NOPE"]
    dataset = write_jsonl(tmp_path / "bad_items.jsonl", demo_items)
    with pytest.raises(EvaluationError, match="failed validation"):
        run(tmp_path, dataset=dataset)
    assert not any(p.is_dir() for p in tmp_path.iterdir())


def test_existing_output_dir_is_not_overwritten(tmp_path):
    run(tmp_path, experiment_id="same")
    with pytest.raises(EvaluationError, match="already exists"):
        run(tmp_path, experiment_id="same")


@pytest.mark.parametrize("bad", ["../escape", "a/b", ""])
def test_experiment_id_is_sanitised(tmp_path, bad):
    with pytest.raises(EvaluationError):
        run(tmp_path, experiment_id=bad or " ")


def test_adapter_load_failure_writes_nothing(tmp_path):
    def broken(_config):
        raise AdapterError("cannot load")

    with pytest.raises(AdapterError):
        run(tmp_path, experiment_id="x", adapter_factory=broken)
    assert not (tmp_path / "x").exists()


def test_records_are_one_json_object_per_line(tmp_path):
    result = run(tmp_path, experiment_id="lines")
    lines = result.responses_path.read_text().splitlines()
    assert len(lines) == 5
    assert all(isinstance(json.loads(line), dict) for line in lines)
