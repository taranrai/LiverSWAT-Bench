"""Synchronise pilot results with a private Hugging Face dataset repository.

GitHub is the primary source repository. The dataset repository is temporary, private
storage for a judge run on a Hugging Face Space. It keeps the results when the Space
restarts. Every function refuses a public repository.

Merge rules for ``pull`` (remote files into the local results directory):

1. A file that is missing locally is copied.
2. A file that is identical locally is not changed.
3. A derived file (``report/``, ``comparison/``, ``pilot_summary.*``) is replaced. The pilot
   writes these files again from the primary files.
4. A primary file that differs locally is a conflict. The pull stops and changes nothing.
5. A judge output file is used only if its manifest exists and the manifest count matches
   the number of records. Otherwise the pair is not copied, and the step runs again from
   its checkpoint.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DERIVED_DIRS = {"report", "comparison"}
DERIVED_FILES = {"pilot_summary.json", "pilot_summary.md"}
CHECKPOINT_PATTERNS = ["**/*.partial.jsonl", "**/*.partial.meta.json"]


class SyncError(RuntimeError):
    """A condition that stops a results synchronisation."""


@dataclass
class MergeResult:
    copied: list[str] = field(default_factory=list)
    replaced_derived: list[str] = field(default_factory=list)
    identical: list[str] = field(default_factory=list)
    skipped_incomplete: list[str] = field(default_factory=list)


def is_derived(rel: Path) -> bool:
    return rel.name in DERIVED_FILES or any(part in DERIVED_DIRS for part in rel.parts[:-1])


def incomplete_judgements(root: Path) -> set[Path]:
    """Return judge output files (and manifests) under ``root`` that are not complete."""
    bad: set[Path] = set()
    for data in root.rglob("judgements/*.jsonl"):
        if data.name.endswith(".partial.jsonl"):
            continue
        manifest = data.with_name(data.name[: -len(".jsonl")] + ".manifest.json")
        n_lines = sum(1 for line in data.read_text(encoding="utf-8").splitlines() if line.strip())
        try:
            expected = json.loads(manifest.read_text())["n_judgements"]
        except (OSError, ValueError, KeyError):
            expected = None
        if expected != n_lines:
            bad.update({data.relative_to(root), manifest.relative_to(root)})
    return bad


def merge_into(src: Path, dest: Path) -> MergeResult:
    """Copy files from ``src`` into ``dest`` with the merge rules in the module docstring."""
    result = MergeResult()
    skip = incomplete_judgements(src)
    plan: list[tuple[Path, Path, str]] = []
    conflicts: list[str] = []
    for path in sorted(p for p in src.rglob("*") if p.is_file()):
        rel = path.relative_to(src)
        if rel.parts and rel.parts[0] == ".cache":
            continue  # Hugging Face download metadata
        if rel in skip:
            result.skipped_incomplete.append(str(rel))
            continue
        target = dest / rel
        if not target.exists():
            plan.append((path, target, "copied"))
        elif target.read_bytes() == path.read_bytes():
            result.identical.append(str(rel))
        elif is_derived(rel):
            plan.append((path, target, "replaced_derived"))
        else:
            conflicts.append(str(rel))
    if conflicts:
        raise SyncError(
            "remote and local primary files differ; nothing was changed. Inspect: "
            + ", ".join(conflicts)
        )
    for path, target, kind in plan:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        getattr(result, kind).append(str(target.relative_to(dest)))
    return result


def require_private(api: Any, repo_id: str, *, create: bool = False) -> None:
    """Stop unless ``repo_id`` is a private dataset repository. Optionally create it."""
    if not api.repo_exists(repo_id, repo_type="dataset"):
        if not create:
            raise SyncError(f"dataset repository {repo_id} does not exist (use --create)")
        api.create_repo(repo_id, repo_type="dataset", private=True)
    info = api.repo_info(repo_id, repo_type="dataset")
    if not info.private:
        raise SyncError(f"dataset repository {repo_id} is public; results are not synchronised")


def pull(api: Any, repo_id: str, results_dir: Path) -> MergeResult:
    """Download the remote results for ``results_dir`` and merge them into it."""
    require_private(api, repo_id)
    with tempfile.TemporaryDirectory(prefix="lsb-pull-") as tmp:
        api.snapshot_download(
            repo_id,
            repo_type="dataset",
            local_dir=tmp,
            allow_patterns=[f"{results_dir.name}/**"],
        )
        remote = Path(tmp) / results_dir.name
        if not remote.is_dir():
            return MergeResult()
        results_dir.mkdir(parents=True, exist_ok=True)
        return merge_into(remote, results_dir)


def push(api: Any, repo_id: str, results_dir: Path, message: str) -> None:
    """Upload ``results_dir``. Remote checkpoint files are replaced by the local ones."""
    require_private(api, repo_id)
    if not results_dir.is_dir():
        raise SyncError(f"{results_dir} is not a directory")
    api.upload_folder(
        repo_id=repo_id,
        repo_type="dataset",
        folder_path=str(results_dir),
        path_in_repo=results_dir.name,
        commit_message=message,
        delete_patterns=CHECKPOINT_PATTERNS,
    )
