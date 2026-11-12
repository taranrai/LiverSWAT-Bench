"""Structured outputs of scoring: checks, claim assessments, dimension scores, flags."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from liverswat_bench.datasets.schema import EvidenceLevel, Track, VerificationStatus
from liverswat_bench.evaluation.dimensions import Dimension

SCORING_SCHEMA_VERSION = "1"
SCORING_LABEL = "AUTOMATED RULE-BASED SCORES - NOT A CLINICAL SAFETY ASSESSMENT"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CheckKind(StrEnum):
    EXPECTED_CLAIM = "expected_claim"
    CONTRADICTED_CLAIM = "contradicted_claim"
    PROHIBITED_CLAIM = "prohibited_claim"
    SAFETY_REQUIREMENT = "safety_requirement"
    UNCERTAINTY_REQUIREMENT = "uncertainty_requirement"


class CheckOutcome(StrEnum):
    PRESENT = "present"  # expected claim stated
    ABSENT = "absent"  # expected claim not found
    DETECTED = "detected"  # contradicted/prohibited claim stated
    NOT_DETECTED = "not_detected"
    MET = "met"  # requirement satisfied
    NOT_MET = "not_met"
    NEEDS_REVIEW = "needs_review"  # ambiguous: human or later method must decide
    NO_RULE = "no_rule"  # no detection rule defined; not checkable deterministically


class Check(_Strict):
    check_id: str
    kind: CheckKind
    description: str
    critical: bool = False
    evidence_passage_ids: list[str] = Field(default_factory=list)
    outcome: CheckOutcome
    review_reasons: list[str] = Field(default_factory=list)
    response_excerpts: list[str] = Field(default_factory=list)


class ClaimClassification(StrEnum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    UNSUPPORTED = "unsupported"
    UNVERIFIABLE = "unverifiable"


class ClaimAssessment(_Strict):
    """A statement identified in the response, assessed against the item's evidence."""

    claim_id: str
    claim_text: str
    evidence_passage_ids: list[str]
    classification: ClaimClassification
    method: Literal["deterministic_rule"] = "deterministic_rule"
    explanation: str
    response_excerpts: list[str]
    abstained: bool
    needs_review: bool


class DimensionStatus(StrEnum):
    SCORED = "scored"
    NOT_APPLICABLE = "not_applicable"
    #: The method could not score reliably (no rule, ambiguity, needs judgement).
    ABSTAINED = "abstained"
    #: No response to score (generation failed).
    MISSING = "missing"


class DimensionScore(_Strict):
    dimension: Dimension
    status: DimensionStatus
    score: int | None = Field(default=None, ge=0, le=4)
    rule: str | None = None
    reason: str
    check_ids: list[str] = Field(default_factory=list)


class AggregateScore(_Strict):
    status: Literal["complete", "incomplete", "not_applicable"]
    #: Weighted 0-4 score, renormalised over applicable dimensions. Only
    #: computed when every applicable dimension was scored.
    score: float | None = None
    applicable_weight: float
    scored_weight: float
    unscored_dimensions: list[Dimension] = Field(default_factory=list)


class CriticalFlag(_Strict):
    check_id: str
    kind: CheckKind
    description: str
    status: Literal["rule_detected", "needs_review"]
    response_excerpts: list[str] = Field(default_factory=list)


class ScoringProvenance(_Strict):
    synthetic: bool
    track: Track
    verification_status: VerificationStatus
    evidence_level: EvidenceLevel
    primary_eligible: bool
    ineligibility_reasons: list[str] = Field(default_factory=list)


class ScoreRecord(_Strict):
    schema_version: Literal["1"] = SCORING_SCHEMA_VERSION
    record_id: str
    experiment_id: str
    question_id: str
    trial: int
    scorer: str
    provenance: ScoringProvenance
    response_status: Literal["ok", "error"]
    checks: list[Check] = Field(default_factory=list)
    claim_assessments: list[ClaimAssessment] = Field(default_factory=list)
    dimension_scores: list[DimensionScore]
    aggregate: AggregateScore
    critical_flags: list[CriticalFlag] = Field(default_factory=list)
    #: Critical checks that could not be evaluated (no rule).
    unchecked_critical: list[str] = Field(default_factory=list)
    note: str = (
        "Only statements covered by the item's detection rules were assessed; other "
        "content of the response is unassessed."
    )


class ScoringManifest(_Strict):
    schema_version: Literal["1"] = SCORING_SCHEMA_VERSION
    experiment_id: str
    scorer: str
    scored_at: datetime
    status_labels: list[str]
    responses_sha256: str
    dataset_path: str
    dataset_sha256: str
    registry_files: dict[str, str]
    n_records: int
    n_primary_eligible_records: int
