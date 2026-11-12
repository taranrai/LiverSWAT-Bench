"""Export machine-readable JSON Schemas from the Pydantic models."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from liverswat_bench.datasets.schema import BenchmarkItem
from liverswat_bench.evaluation.combine import CombinedRecord
from liverswat_bench.evaluation.records import ResponseRecord, RunManifest
from liverswat_bench.evaluation.scoring_records import ScoreRecord, ScoringManifest
from liverswat_bench.evidence.schema import EvidencePassage, Source
from liverswat_bench.judges.schema import JudgeConfig, JudgeRecord, JudgeRunManifest

SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "benchmark_item.schema.json": BenchmarkItem,
    "source.schema.json": Source,
    "evidence_passage.schema.json": EvidencePassage,
    "response_record.schema.json": ResponseRecord,
    "run_manifest.schema.json": RunManifest,
    "score_record.schema.json": ScoreRecord,
    "scoring_manifest.schema.json": ScoringManifest,
    "judge_config.schema.json": JudgeConfig,
    "judge_record.schema.json": JudgeRecord,
    "judge_manifest.schema.json": JudgeRunManifest,
    "combined_record.schema.json": CombinedRecord,
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
