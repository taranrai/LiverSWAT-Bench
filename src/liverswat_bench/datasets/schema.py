"""Strict schema for benchmark items (one JSON object per JSONL line).

Rules enforced here are those checkable within a single record. Rules that
need the evidence registry or other records (referential integrity, duplicate
IDs) live in :mod:`liverswat_bench.datasets.validation`.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from liverswat_bench.evaluation.dimensions import SCORE_MAX, SCORE_MIN, Dimension
from liverswat_bench.evidence.schema import PASSAGE_ID_PATTERN, SOURCE_ID_PATTERN

QUESTION_ID_PATTERN = r"^[A-Z][A-Z0-9]*(-[A-Z0-9]+)+$"
LOCAL_ID_PATTERN = r"^[A-Za-z0-9_.-]+$"

SourceId = Annotated[str, StringConstraints(pattern=SOURCE_ID_PATTERN)]
PassageId = Annotated[str, StringConstraints(pattern=PASSAGE_ID_PATTERN)]
LocalId = Annotated[str, StringConstraints(pattern=LOCAL_ID_PATTERN)]
NonEmpty = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]


class Topic(StrEnum):
    AWARENESS_PREVENTION = "awareness_prevention"
    ALCOHOL = "alcohol"
    MASLD_LIFESTYLE = "masld_lifestyle"
    VIRAL_HEPATITIS = "viral_hepatitis"
    LIVER_TESTS = "liver_tests_investigations"
    NHS_NAVIGATION = "nhs_navigation"


class Audience(StrEnum):
    GENERAL_PUBLIC = "general_public"
    PATIENT = "patient"
    CARER = "carer"


class PromptType(StrEnum):
    DIRECT_QUESTION = "direct_question"
    SCENARIO = "scenario"
    MISINFORMATION = "misinformation"
    FALSE_REASSURANCE = "false_reassurance"
    DIAGNOSTIC_CERTAINTY = "diagnostic_certainty"
    INCOMPLETE_INFORMATION = "incomplete_information"
    ADVERSARIAL = "adversarial"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    UNCERTAINTY = "uncertainty"
    EVIDENCE_MANIPULATION = "evidence_manipulation"
    UNSAFE_ADVICE_REQUEST = "unsafe_advice_request"


class Difficulty(StrEnum):
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class EvidenceLevel(StrEnum):
    #: Directly supported by an explicit statement in an authoritative UK source.
    A = "A"
    #: Requires interpretation or combination of sources.
    B = "B"
    #: Requires clinical judgement; excluded until qualified clinical review.
    C = "C"


class VerificationStatus(StrEnum):
    DRAFT = "draft"
    SOURCE_PENDING = "source_pending"
    SOURCE_VERIFIED = "source_verified"
    DISPUTED = "disputed"
    EXPERT_REVIEW_REQUIRED = "expert_review_required"
    RETIRED = "retired"


class Track(StrEnum):
    """Which score an item may contribute to."""

    #: Main benchmark score. Level A, source-verified, non-synthetic only.
    PRIMARY = "primary"
    #: Reported separately (e.g. Level B items awaiting review).
    EXPLORATORY = "exploratory"
    #: Stress tests such as adversarial or misinformation variants.
    EXPERIMENTAL = "experimental"
    #: Synthetic records for testing the software. Never scored as research.
    DEMO = "demo"


class RiskLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class NumericSpec(_Strict):
    """A number that must appear immediately followed by a unit, e.g. ``14 units``."""

    value: float
    #: Regular expression for the unit that directly follows the number.
    unit_pattern: NonEmpty


class DetectionRule(_Strict):
    """Researcher-authored, reproducible rule for detecting a statement in a response.

    All conditions must hold within a single sentence. Patterns are
    case-insensitive regular expressions. A rule match is evidence that the
    wording is present, not proof that the statement is clinically correct.
    """

    #: Every pattern must match in the sentence.
    all_of: list[NonEmpty] = Field(default_factory=list)
    #: At least one pattern must match in the sentence (if any are given).
    any_of: list[NonEmpty] = Field(default_factory=list)
    numeric: NumericSpec | None = None
    #: If true, a negation cue elsewhere in the matched sentence sends the
    #: result to review. Set false only when negation is part of the wording
    #: being detected (e.g. "does not rule out").
    negation_sensitive: bool = True
    notes: str | None = None

    @model_validator(mode="after")
    def _check(self) -> DetectionRule:
        if not (self.all_of or self.any_of or self.numeric):
            raise ValueError("a detection rule needs all_of, any_of or numeric")
        patterns = [*self.all_of, *self.any_of]
        if self.numeric:
            patterns.append(self.numeric.unit_pattern)
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"invalid regular expression {pattern!r}: {exc}") from exc
        return self


class ExpectedClaim(_Strict):
    claim_id: LocalId
    text: NonEmpty
    evidence_passage_ids: list[PassageId] = Field(min_length=1)
    #: Required claims must appear for full factual credit.
    required: bool = True
    detection: DetectionRule | None = None


class ContradictedClaim(_Strict):
    claim_id: LocalId
    text: NonEmpty
    evidence_passage_ids: list[PassageId] = Field(min_length=1)
    detection: DetectionRule | None = None


class ProhibitedClaim(_Strict):
    claim_id: LocalId
    text: NonEmpty
    rationale: NonEmpty
    #: If asserted, the response receives a critical-failure flag regardless of score.
    critical: bool = False
    evidence_passage_ids: list[PassageId] = Field(default_factory=list)
    detection: DetectionRule | None = None


class SafetyRequirement(_Strict):
    requirement_id: LocalId
    description: NonEmpty
    critical: bool = False
    evidence_passage_ids: list[PassageId] = Field(default_factory=list)
    #: "requires": the rule detects the required behaviour.
    #: "forbids": the rule detects a violation of the requirement.
    detection_mode: Literal["requires", "forbids"] = "requires"
    detection: DetectionRule | None = None


class UncertaintyRequirement(_Strict):
    requirement_id: LocalId
    description: NonEmpty
    #: "requires": the rule detects the required behaviour.
    #: "forbids": the rule detects a violation of the requirement.
    detection_mode: Literal["requires", "forbids"] = "requires"
    detection: DetectionRule | None = None


class DimensionRubric(_Strict):
    dimension: Dimension
    applicable: bool = True
    #: Item-specific 0-4 anchors. If omitted, the default anchors are used.
    anchors: dict[int, NonEmpty] | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _check_anchors(self) -> DimensionRubric:
        if self.anchors is not None:
            if not self.applicable:
                raise ValueError("non-applicable dimensions must not define anchors")
            expected = set(range(SCORE_MIN, SCORE_MAX + 1))
            if set(self.anchors) != expected:
                raise ValueError(f"anchors must define exactly the scores {sorted(expected)}")
        return self


class BenchmarkItem(_Strict):
    question_id: str = Field(pattern=QUESTION_ID_PATTERN)
    benchmark_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    topic: Topic
    subtopic: NonEmpty
    question: NonEmpty
    intended_audience: Audience
    prompt_type: PromptType
    difficulty: Difficulty
    evidence_level: EvidenceLevel
    verification_status: VerificationStatus
    track: Track
    synthetic: bool
    source_ids: list[SourceId] = Field(default_factory=list)
    evidence_passage_ids: list[PassageId] = Field(default_factory=list)
    expected_claims: list[ExpectedClaim] = Field(default_factory=list)
    acceptable_variations: list[NonEmpty] = Field(default_factory=list)
    contradicted_claims: list[ContradictedClaim] = Field(default_factory=list)
    prohibited_claims: list[ProhibitedClaim] = Field(default_factory=list)
    safety_requirements: list[SafetyRequirement] = Field(default_factory=list)
    uncertainty_requirements: list[UncertaintyRequirement] = Field(default_factory=list)
    scoring_rubric: list[DimensionRubric] = Field(min_length=1)
    risk_level: RiskLevel
    reviewer_notes: str | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _check_item(self) -> BenchmarkItem:
        errors: list[str] = []

        # --- Track eligibility -------------------------------------------------
        if self.track == Track.PRIMARY:
            if self.evidence_level != EvidenceLevel.A:
                errors.append("primary-track items must be evidence level A")
            if self.verification_status != VerificationStatus.SOURCE_VERIFIED:
                errors.append("primary-track items must be source_verified")
            if self.synthetic:
                errors.append("synthetic items cannot be in the primary track")
        if (
            self.evidence_level == EvidenceLevel.C
            and self.track != Track.DEMO
            and (self.verification_status == VerificationStatus.SOURCE_VERIFIED)
        ):
            errors.append(
                "level C items require clinical judgement: use expert_review_required, "
                "not source_verified"
            )
        if self.synthetic and self.track not in (Track.DEMO, Track.EXPERIMENTAL):
            errors.append("synthetic items must be in the demo or experimental track")
        if self.track == Track.DEMO and not self.synthetic:
            errors.append("demo-track items must be marked synthetic")

        # --- Evidence presence -------------------------------------------------
        if self.verification_status == VerificationStatus.SOURCE_VERIFIED:
            if not self.source_ids:
                errors.append("source_verified items require at least one source_id")
            if not self.evidence_passage_ids:
                errors.append("source_verified items require at least one evidence passage")
            if not self.expected_claims:
                errors.append("source_verified items require at least one expected claim")

        # --- Internal references ----------------------------------------------
        declared = set(self.evidence_passage_ids)
        claim_groups = (
            self.expected_claims,
            self.contradicted_claims,
            self.prohibited_claims,
            self.safety_requirements,
        )
        for group in claim_groups:
            for entry in group:
                undeclared = set(entry.evidence_passage_ids) - declared
                if undeclared:
                    entry_id = getattr(entry, "claim_id", None) or entry.requirement_id
                    errors.append(
                        f"{entry_id!r} cites passages not listed in evidence_passage_ids: "
                        f"{sorted(undeclared)}"
                    )

        local_ids = [c.claim_id for c in self.expected_claims]
        local_ids += [c.claim_id for c in self.contradicted_claims]
        local_ids += [c.claim_id for c in self.prohibited_claims]
        local_ids += [r.requirement_id for r in self.safety_requirements]
        local_ids += [r.requirement_id for r in self.uncertainty_requirements]
        dupes = sorted({i for i in local_ids if local_ids.count(i) > 1})
        if dupes:
            errors.append(f"duplicate claim/requirement ids within item: {dupes}")

        for name in ("source_ids", "evidence_passage_ids"):
            values = getattr(self, name)
            if len(values) != len(set(values)):
                errors.append(f"{name} contains duplicates")

        rubric_dims = [r.dimension for r in self.scoring_rubric]
        if len(rubric_dims) != len(set(rubric_dims)):
            errors.append("scoring_rubric lists a dimension more than once")
        missing_dims = set(Dimension) - set(rubric_dims)
        if missing_dims:
            errors.append(
                "scoring_rubric must state every dimension (use applicable=false if N/A); "
                f"missing: {sorted(missing_dims)}"
            )

        if self.updated_at < self.created_at:
            errors.append("updated_at cannot precede created_at")

        if errors:
            raise ValueError("; ".join(errors))
        return self
