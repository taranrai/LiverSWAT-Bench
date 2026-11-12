"""Capture reproducibility metadata about the software and hardware environment.

Hostnames, usernames and environment variables are deliberately not recorded.
"""

from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

from liverswat_bench import BENCHMARK_VERSION, __version__

TRACKED_LIBRARIES = ("pydantic", "typer", "pyyaml", "torch", "transformers", "vllm")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(*args: str, cwd: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10, check=True
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip()


def git_state(cwd: Path) -> dict[str, Any]:
    commit = _git("rev-parse", "HEAD", cwd=cwd)
    if commit is None:
        return {"commit": None, "dirty": None}
    status = _git("status", "--porcelain", cwd=cwd)
    return {"commit": commit, "dirty": bool(status)}


def library_versions() -> dict[str, str]:
    versions = {}
    for lib in TRACKED_LIBRARIES:
        try:
            versions[lib] = metadata.version(lib)
        except metadata.PackageNotFoundError:
            continue
    return versions


def capture_environment(cwd: Path, backend_info: dict[str, Any]) -> dict[str, Any]:
    return {
        "liverswat_version": __version__,
        "benchmark_format_version": BENCHMARK_VERSION,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "cpu_count": os.cpu_count(),
        "git": git_state(cwd),
        "libraries": library_versions(),
        "backend": backend_info,
    }
