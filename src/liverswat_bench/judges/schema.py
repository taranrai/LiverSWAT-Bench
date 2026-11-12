"""Schemas for LLM judges: configuration, structured output and stored judgements.

Judges are automated evaluators. They are not clinical experts, and their
outputs are recorded separately from deterministic rule scores and from the
verified evidence they were given.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from liverswat_bench.evaluation.dimensions import Dimension
from liverswat_bench.evaluation.scoring_records import ClaimClassification
from liverswat_bench.models.config import ConfigError, GenerationParams, ModelConfig

JUDGE_SCHEMA_VERSION = "1"
JUDGE_LABEL = "AUTOMATED LLM-JUDGE ASSESSMENTS - NOT CLINICAL EXPERT REVIEW, NOT VERIFIED EVIDENCE"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidencePolicy(StrEnum):
    #: Only passages with status "verified" are shown to the judge (default).
    VERIFIED_ONLY = "verified_only"
    #: Unverified passages are also shown, labelled as unverified. Development only.
    INCLUDE_UNVERIFIED = "include_unverified"


class CostRates(_Strict):
    """Optional, user-supplied prices. Never guessed: unset means 'not available'."""

    currency: str | None = None
    input_per_1k_tokens: float | None = Field(default=None, ge=0)
    output_per_1k_tokens: float | None = Field(default=None, ge=0)


class JudgeConfig(_Strict):
    judge_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    model: ModelConfig
    prompt_version: str = "v1"
    evidence_policy: EvidencePolicy = EvidencePolicy.VERIFIED_ONLY
    #: Extra attempts after an invalid output or a generation error.
    max_retries: int = Field(default=2, ge=0, le=10)
    cost: CostRates = Field(default_factory=CostRates)
    notes: str | None = None


def load_judge_config(path: Path) -> JudgeConfig:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"cannot read judge config {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"judge config {path} must be a YAML mapping")
    try:
        return JudgeConfig.model_validate(data)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or '<config>'}: {e['msg']}" for e in exc.errors()
        )
        raise ConfigError(f"invalid judge config {path}: {details}") from exc


# ------------------------------------------------------- raw judge output


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RawDimensionJudgement(_Strict):
    dimension: Dimension
    score: int | None = Field(default=None, ge=0, le=4)
    abstain: bool = False
    abstain_reason: str | None = None
    evidence_passage_ids: list[str] = Field(default_factory=list)
    explanation: str = Field(min_length=1)
    confidence: Confidence

    @model_validator(mode="after")
    def _consistent(self) -> RawDimensionJudgement:
        if self.abstain and self.score is not None:
            raise ValueError("an abstaining judgement must not give a score")
        if not self.abstain and self.score is None:
            raise ValueError("a non-abstaining judgement must give a score")
        if self.abstain and not self.abstain_reason:
            raise ValueError("abstain_reason is required when abstaining")
        return self


class RawClaimJudgement(_Strict):
    #: Exact text copied from the model response.
    text: str = Field(min_length=1)
    classification: ClaimClassification
    evidence_passage_ids: list[str] = Field(default_factory=list)
    explanation: str = Field(min_length=1)
    potentially_dangerous: bool = False
    confidence: Confidence
    needs_review: bool = False


class RawJudgeOutput(_Strict):
    """The JSON object a judge must return."""

    dimensions: list[RawDimensionJudgement]
    claims: list[RawClaimJudgement] = Field(default_factory=list)

    @model_validator(mode="after")
    def _all_dimensions(self) -> RawJudgeOutput:
        dims = [d.dimension for d in self.dimensions]
        if sorted(dims) != sorted(Dimension):
            raise ValueError("dimensions must list each of the six dimensions exactly once")
        return self


# --------------------------------------------------- validated judgements


class DimensionJudgement(_Strict):
    dimension: Dimension
    status: Literal["scored", "abstained", "not_applicable", "invalid"]
    score: int | None = None
    evidence_passage_ids: list[str] = Field(default_factory=list)
    explanation: str | None = None
    confidence: Confidence | None = None
    #: Why the judgement was abstained or invalidated (judge's or validator's reason).
    reason: str | None = None


class ClaimJudgement(_Strict):
    claim_index: int
    text: str
    text_found_in_response: bool
    classification: ClaimClassification
    evidence_passage_ids: list[str]
    explanation: str
    potentially_dangerous: bool
    confidence: Confidence
    needs_review: bool
    review_reasons: list[str] = Field(default_factory=list)


class Attempt(_Strict):
    attempt: int
    seed: int | None = None
    raw_output: str | None
    error: str | None
    latency_s: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class JudgeRecord(_Strict):
    schema_version: Literal["1"] = JUDGE_SCHEMA_VERSION
    judgement_id: str
    record_id: str
    question_id: str
    trial: int
    judge_id: str
    judge_model: dict[str, Any]
    prompt_version: str
    repeat: int
    evidence_policy: EvidencePolicy
    passages_supplied: list[str]
    passages_supplied_verified: list[str]
    passages_withheld: dict[str, str]
    messages: list[dict[str, str]]
    prompt_sha256: str
    generation: GenerationParams
    status: Literal["ok", "invalid_output", "error", "skipped_no_response"]
    attempts: list[Attempt]
    validation_issues: list[str] = Field(default_factory=list)
    dimensions: list[DimensionJudgement] = Field(default_factory=list)
    claims: list[ClaimJudgement] = Field(default_factory=list)
    latency_s: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    estimated_cost: float | None = None
    cost_currency: str | None = None
    created_at: datetime


class JudgeRunManifest(_Strict):
    schema_version: Literal["1"] = JUDGE_SCHEMA_VERSION
    experiment_id: str
    judge_id: str
    judge_config_path: str
    judge_config_sha256: str
    judge_config: dict[str, Any]
    prompt_versions: list[str]
    repeats: int
    status_labels: list[str]
    started_at: datetime
    completed_at: datetime
    n_judgements: int
    n_resumed_from_checkpoint: int = 0
    n_by_status: dict[str, int]
    responses_sha256: str
    dataset_sha256: str
    registry_files: dict[str, str]
    environment: dict[str, Any]
