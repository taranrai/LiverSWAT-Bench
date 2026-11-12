"""Export machine-readable JSON Schemas from the Pydantic models."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from liverswat_bench.datasets.schema import BenchmarkItem
from liverswat_bench.evidence.schema import EvidencePassage, Source

SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "benchmark_item.schema.json": BenchmarkItem,
    "source.schema.json": Source,
    "evidence_passage.schema.json": EvidencePassage,
}


def render_schema(model: type[BaseModel]) -> str:
    schema = model.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def export_schemas(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for filename, model in SCHEMA_MODELS.items():
        path = out_dir / filename
        path.write_text(render_schema(model), encoding="utf-8")
        written.append(path)
    return written
