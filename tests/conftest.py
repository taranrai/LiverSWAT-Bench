from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = REPO_ROOT / "data" / "examples"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


@pytest.fixture
def demo_items() -> list[dict]:
    return load_jsonl(EXAMPLES / "demo_items.jsonl")


@pytest.fixture
def demo_item(demo_items) -> dict:
    return copy.deepcopy(demo_items[0])


@pytest.fixture
def demo_source_file() -> Path:
    return EXAMPLES / "demo_sources.jsonl"


@pytest.fixture
def demo_passage_file() -> Path:
    return EXAMPLES / "demo_passages.jsonl"
