"""Results synchronisation with a private Hugging Face dataset repository (no network)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from liverswat_bench.hf_results import (
    CHECKPOINT_PATTERNS,
    SyncError,
    incomplete_judgements,
    merge_into,
    pull,
    push,
    require_private,
)


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def judge_pair(root: Path, run: str, n_lines: int, n_manifest: int | None) -> None:
    j = root / run / "judgements"
    write(j / "judge-a.jsonl", "".join("{}\n" for _ in range(n_lines)))
    if n_manifest is not None:
        write(j / "judge-a.manifest.json", json.dumps({"n_judgements": n_manifest}))


class FakeApi:
    def __init__(self, private=True, exists=True, remote: dict[str, str] | None = None):
        self.private, self.exists, self.remote = private, exists, remote or {}
        self.calls: list[tuple] = []

    def repo_exists(self, repo_id, repo_type):
        return self.exists

    def create_repo(self, repo_id, repo_type, private):
        self.calls.append(("create_repo", repo_id, repo_type, private))
        self.exists, self.private = True, private

    def repo_info(self, repo_id, repo_type):
        return SimpleNamespace(private=self.private)

    def upload_folder(self, **kw):
        self.calls.append(("upload_folder", kw))

    def snapshot_download(self, repo_id, repo_type, local_dir, allow_patterns):
        for rel, text in self.remote.items():
            write(Path(local_dir) / rel, text)


def test_merge_copies_missing_and_keeps_identical(tmp_path):
    src, dest = tmp_path / "src", tmp_path / "dest"
    write(src / "run/responses.jsonl", "same")
    write(dest / "run/responses.jsonl", "same")
    write(src / "run/judgements/x.partial.jsonl", "{}\n")
    r = merge_into(src, dest)
    assert r.identical == ["run/responses.jsonl"]
    assert r.copied == ["run/judgements/x.partial.jsonl"]


def test_merge_replaces_derived_files(tmp_path):
    src, dest = tmp_path / "src", tmp_path / "dest"
    for rel in ("pilot_summary.md", "run/report/report.md", "comparison/comparison.json"):
        write(src / rel, "new")
        write(dest / rel, "old")
    r = merge_into(src, dest)
    assert len(r.replaced_derived) == 3
    assert (dest / "run/report/report.md").read_text() == "new"


def test_merge_conflict_on_primary_file_changes_nothing(tmp_path):
    src, dest = tmp_path / "src", tmp_path / "dest"
    write(src / "run/responses.jsonl", "remote")
    write(src / "run/new.txt", "x")
    write(dest / "run/responses.jsonl", "local")
    with pytest.raises(SyncError, match=r"run/responses\.jsonl"):
        merge_into(src, dest)
    assert not (dest / "run/new.txt").exists()
    assert (dest / "run/responses.jsonl").read_text() == "local"


def test_incomplete_judge_outputs_are_not_copied(tmp_path):
    src, dest = tmp_path / "src", tmp_path / "dest"
    judge_pair(src, "complete", 3, 3)
    judge_pair(src, "cut", 2, 3)
    judge_pair(src, "no-manifest", 3, None)
    assert incomplete_judgements(src) == {
        Path("cut/judgements/judge-a.jsonl"),
        Path("cut/judgements/judge-a.manifest.json"),
        Path("no-manifest/judgements/judge-a.jsonl"),
        Path("no-manifest/judgements/judge-a.manifest.json"),
    }
    merge_into(src, dest)
    assert (dest / "complete/judgements/judge-a.jsonl").is_file()
    assert not (dest / "cut/judgements").exists()
    assert not (dest / "no-manifest/judgements").exists()


def test_public_repository_is_refused():
    with pytest.raises(SyncError, match="public"):
        require_private(FakeApi(private=False), "o/r")


def test_missing_repository_is_created_private_only_on_request():
    api = FakeApi(exists=False)
    with pytest.raises(SyncError, match="does not exist"):
        require_private(api, "o/r")
    require_private(api, "o/r", create=True)
    assert api.calls == [("create_repo", "o/r", "dataset", True)]


def test_push_uploads_folder_and_mirrors_checkpoints(tmp_path):
    results = tmp_path / "m5"
    write(results / "a.txt", "x")
    api = FakeApi()
    push(api, "o/r", results, "msg")
    ((name, kw),) = api.calls
    assert name == "upload_folder"
    assert kw["path_in_repo"] == "m5" and kw["repo_type"] == "dataset"
    assert kw["delete_patterns"] == CHECKPOINT_PATTERNS


def test_push_refuses_public_repository(tmp_path):
    api = FakeApi(private=False)
    with pytest.raises(SyncError):
        push(api, "o/r", tmp_path, "msg")
    assert api.calls == []


def test_pull_merges_remote_results(tmp_path):
    results = tmp_path / "m5"
    write(results / "run/responses.jsonl", "same")
    api = FakeApi(
        remote={"m5/run/responses.jsonl": "same", "m5/run/judgements/j.partial.jsonl": "{}\n"}
    )
    r = pull(api, "o/r", results)
    assert r.copied == ["run/judgements/j.partial.jsonl"]
    assert r.identical == ["run/responses.jsonl"]
