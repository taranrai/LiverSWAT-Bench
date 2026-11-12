"""Builders for judge tests: deterministic fake adapters and record constructors."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from liverswat_bench.evaluation.dimensions import Dimension
from liverswat_bench.evaluation.scoring_records import ScoreRecord
from liverswat_bench.judges.schema import JudgeRecord
from liverswat_bench.models import AdapterError, GenerationResult, ModelAdapter
from liverswat_bench.models.config import GenerationParams, ModelConfig

DIMS = [d.value for d in Dimension]


class QueueAdapter(ModelAdapter):
    """Returns queued outputs in order (last one repeats). Exceptions are raised."""

    def __init__(self, outputs: list[str | Exception]) -> None:
        super().__init__(
            ModelConfig.model_validate({"config_id": "q", "model_name": "q", "backend": "mock"})
        )
        self.outputs = list(outputs)
        self.calls: list[tuple[list[dict[str, str]], GenerationParams]] = []

    def generate(self, messages, params):
        self.calls.append((messages, params))
        out = self.outputs.pop(0) if len(self.outputs) > 1 else self.outputs[0]
        if isinstance(out, Exception):
            raise out
        return GenerationResult(text=out, prompt_tokens=100, completion_tokens=40)


def dim(name: str, score: int | None = 3, ev: list[str] | None = None, **kw) -> dict[str, Any]:
    out = {
        "dimension": name,
        "score": score,
        "abstain": score is None,
        "evidence_passage_ids": ev if ev is not None else [],
        "explanation": "test",
        "confidence": "high",
    }
    if score is None:
        out["abstain_reason"] = kw.get("reason", "insufficient")
    return out


def output(overrides: dict[str, dict] | None = None, claims: list[dict] | None = None) -> str:
    """Valid judge JSON. Evidence-required dimensions cite PSG-DEMO-0002 by default."""
    overrides = overrides or {}
    dims = []
    for name in DIMS:
        if name in overrides:
            dims.append(overrides[name])
        elif name in ("factual_accuracy", "uk_evidence_alignment"):
            dims.append(dim(name, 2, ["PSG-DEMO-0002"]))
        else:
            dims.append(dim(name, 2))
    return json.dumps({"dimensions": dims, "claims": claims or []})


def claim(text: str, cls: str, ev: list[str] | None = None, **kw) -> dict[str, Any]:
    return {
        "text": text,
        "classification": cls,
        "evidence_passage_ids": ev or [],
        "explanation": "test",
        "potentially_dangerous": kw.get("danger", False),
        "confidence": kw.get("confidence", "high"),
        "needs_review": kw.get("review", False),
    }


def score_record(record_id: str, dims: dict[str, tuple[str, int | None, str]]) -> ScoreRecord:
    """dims: dimension -> (status, score, reason). Unlisted dimensions are scored 2."""
    dim_scores = []
    for name in DIMS:
        status, value, reason = dims.get(name, ("scored", 2, "test"))
        dim_scores.append({"dimension": name, "status": status, "score": value, "reason": reason})
    return ScoreRecord.model_validate(
        {
            "record_id": record_id,
            "experiment_id": "exp",
            "question_id": record_id.split(":")[1],
            "trial": 0,
            "scorer": "test",
            "provenance": {
                "synthetic": True,
                "track": "demo",
                "verification_status": "draft",
                "evidence_level": "A",
                "primary_eligible": False,
            },
            "response_status": "ok",
            "dimension_scores": dim_scores,
            "aggregate": {"status": "incomplete", "applicable_weight": 1.0, "scored_weight": 0.0},
        }
    )


def judge_record(
    record_id: str,
    judge_id: str,
    scores: dict[str, int | str | None],
    *,
    status: str = "ok",
    prompt_version: str = "v1",
    repeat: int = 0,
    claims: list[dict] | None = None,
) -> JudgeRecord:
    """scores: dimension -> int (scored), None (abstained) or 'not_applicable'/'invalid'."""
    dims = []
    if status == "ok":
        for name in DIMS:
            v = scores.get(name, 2)
            if v is None:
                dims.append({"dimension": name, "status": "abstained", "reason": "test"})
            elif isinstance(v, str):
                dims.append({"dimension": name, "status": v, "reason": "test"})
            else:
                dims.append({"dimension": name, "status": "scored", "score": v})
    return JudgeRecord.model_validate(
        {
            "judgement_id": f"{record_id}:{judge_id}:{prompt_version}:{repeat}",
            "record_id": record_id,
            "question_id": record_id.split(":")[1],
            "trial": 0,
            "judge_id": judge_id,
            "judge_model": {"model_name": judge_id},
            "prompt_version": prompt_version,
            "repeat": repeat,
            "evidence_policy": "include_unverified",
            "passages_supplied": [],
            "passages_supplied_verified": [],
            "passages_withheld": {},
            "messages": [],
            "prompt_sha256": "x",
            "generation": {},
            "status": status,
            "attempts": [],
            "dimensions": dims,
            "claims": claims or [],
            "latency_s": 0.1,
            "created_at": datetime.now(UTC).isoformat(),
        }
    )


def adapter_error(msg: str = "boom") -> AdapterError:
    return AdapterError(msg)
