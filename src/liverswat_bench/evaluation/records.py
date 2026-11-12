"""Stored model responses and run manifests.

Model outputs are kept separate from benchmark items and evidence. Every
response record carries the provenance of the item it answers, so synthetic
demonstration data can never be mistaken for source-verified benchmark data.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from liverswat_bench.datasets.schema import EvidenceLevel, Track, VerificationStatus
from liverswat_bench.models.config import Backend, GenerationParams

RESPONSE_SCHEMA_VERSION = "1"

SYNTHETIC_LABEL = "SYNTHETIC DEMONSTRATION DATA - NOT RESEARCH RESULTS"
UNVERIFIED_LABEL = "INCLUDES ITEMS THAT ARE NOT SOURCE-VERIFIED - NOT PRIMARY BENCHMARK RESULTS"
NOT_CLINICAL_LABEL = "EVIDENCE-GROUNDED, NOT CLINICALLY VALIDATED"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DataProvenance(_Strict):
    synthetic: bool
    track: Track
    verification_status: VerificationStatus
    evidence_level: EvidenceLevel
    #: True only for items that may count towards the primary benchmark score.
    primary_eligible: bool
    dataset_path: str
    dataset_sha256: str


class ModelInfo(_Strict):
    config_id: str
    model_name: str
    model_revision: str | None
    revision_pinned: bool
    backend: Backend
    licence: str | None
    open_weight: bool | None
    osi_approved_licence: bool | None
    parameter_count: str | None
    quantisation: str | None
    served_model_id: str | None = None


class PromptInfo(_Strict):
    system_prompt: str | None
    prompt_template: str
    messages: list[dict[str, str]]


class EvidenceSupplied(_Strict):
    """Which source evidence the model received (evidence experiment conditions)."""

    condition: Literal["baseline", "retrieved", "oracle"] = "baseline"
    evidence_prompt_version: str | None = None
    passage_ids: list[str] = Field(default_factory=list)
    passages_verified: list[str] = Field(default_factory=list)
    retriever: str | None = None
    retrieval_scores: dict[str, float] = Field(default_factory=dict)
    corpus_size: int | None = None
    corpus_sha256: str | None = None
    #: The item's own cited passages that have stored text.
    oracle_passage_ids: list[str] = Field(default_factory=list)
    #: Retrieved condition only: share of oracle passages that were retrieved.
    oracle_recall: float | None = None


class ResponseInfo(_Strict):
    text: str | None
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class Timing(_Strict):
    started_at: datetime
    completed_at: datetime
    latency_s: float


class ResponseRecord(_Strict):
    schema_version: Literal["1"] = RESPONSE_SCHEMA_VERSION
    record_id: str
    experiment_id: str
    question_id: str
    benchmark_version: str
    trial: int = Field(ge=0)
    data_provenance: DataProvenance
    model: ModelInfo
    prompt: PromptInfo
    evidence: EvidenceSupplied = Field(default_factory=EvidenceSupplied)
    generation: GenerationParams
    response: ResponseInfo
    status: Literal["ok", "error"]
    error: str | None = None
    timing: Timing


class RunManifest(_Strict):
    schema_version: Literal["1"] = RESPONSE_SCHEMA_VERSION
    experiment_id: str
    status_labels: list[str]
    started_at: datetime
    completed_at: datetime
    model_config_path: str
    model_config_sha256: str
    model_settings: dict[str, Any]
    dataset_path: str
    dataset_sha256: str
    registry_files: dict[str, str]
    benchmark_versions: list[str]
    trials: int
    n_items: int
    n_items_skipped_retired: int
    n_records: int
    n_ok: int
    n_error: int
    items_by_track: dict[str, int]
    items_by_verification_status: dict[str, int]
    n_synthetic_items: int
    n_primary_eligible_items: int
    environment: dict[str, Any]
    command: list[str] | None = None
    evidence_condition: Literal["baseline", "retrieved", "oracle"] = "baseline"
    retriever: dict[str, Any] | None = None
