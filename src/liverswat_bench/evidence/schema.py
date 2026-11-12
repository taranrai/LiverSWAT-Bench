"""Schemas for the UK evidence registry: sources and evidence passages.

Evidence is stored separately from benchmark questions and model outputs.
A source being marked ``verified`` means a researcher has checked that the
document exists at the stated URL and that the recorded metadata is accurate.
It does NOT mean any clinical validation has taken place.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

SOURCE_ID_PATTERN = r"^SRC-[A-Z0-9]+(-[A-Z0-9]+)*$"
PASSAGE_ID_PATTERN = r"^PSG-[A-Z0-9]+(-[A-Z0-9]+)*$"


class Organisation(StrEnum):
    NICE = "NICE"
    NHS = "NHS"
    BSG = "BSG"
    BASL = "BASL"
    BRITISH_LIVER_TRUST = "British Liver Trust"
    UKHSA = "UKHSA"
    UK_CMO = "UK Chief Medical Officers"
    #: Fictional organisation used only for software demonstration records.
    SYNTHETIC_DEMO = "SYNTHETIC_DEMO"


class SourceStatus(StrEnum):
    #: Recorded as a candidate; metadata has not been checked against the original.
    UNVERIFIED = "unverified"
    #: A researcher has checked the metadata against the official document.
    VERIFIED = "verified"
    #: Previously verified, but guidance may have changed; must be rechecked.
    NEEDS_REVERIFICATION = "needs_reverification"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


class EvidenceConfidence(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


class PassageTextType(StrEnum):
    #: Exact quotation, stored only where the source licence permits reuse.
    VERBATIM = "verbatim"
    #: Researcher's paraphrase, used where verbatim reuse is not permitted.
    PARAPHRASE = "paraphrase"
    #: No text stored; the passage is identified by its locator only.
    LOCATOR_ONLY = "locator_only"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Source(_Strict):
    """A single authoritative document in the evidence registry."""

    source_id: str = Field(pattern=SOURCE_ID_PATTERN)
    organisation: Organisation
    title: str = Field(min_length=1)
    url: HttpUrl | None = None
    guideline_id: str | None = None
    publication_date: date | None = None
    last_updated_date: date | None = None
    date_accessed: date | None = None
    relevant_sections: list[str] = Field(default_factory=list)
    populations: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    evidence_confidence: EvidenceConfidence | None = None
    source_status: SourceStatus = SourceStatus.UNVERIFIED
    licence: str | None = None
    reuse_restrictions: str | None = None
    #: Attribution required by the licence for each reuse of this source's text.
    attribution: str | None = None
    verification_notes: str | None = None
    synthetic: bool = False

    @model_validator(mode="after")
    def _check_consistency(self) -> Source:
        is_demo_org = self.organisation == Organisation.SYNTHETIC_DEMO
        if self.synthetic != is_demo_org:
            raise ValueError(
                "synthetic sources must use organisation SYNTHETIC_DEMO, and only "
                "synthetic sources may use it"
            )
        if self.synthetic and self.source_status == SourceStatus.VERIFIED:
            raise ValueError("synthetic sources can never be marked verified")
        if self.source_status == SourceStatus.VERIFIED:
            missing = [
                name for name in ("url", "date_accessed", "licence") if getattr(self, name) is None
            ]
            if missing:
                raise ValueError(f"verified sources require: {', '.join(missing)}")
        if (
            self.publication_date
            and self.last_updated_date
            and self.last_updated_date < self.publication_date
        ):
            raise ValueError("last_updated_date cannot precede publication_date")
        return self


class EvidencePassage(_Strict):
    """A specific, locatable piece of a source that a benchmark item relies on."""

    passage_id: str = Field(pattern=PASSAGE_ID_PATTERN)
    source_id: str = Field(pattern=SOURCE_ID_PATTERN)
    section: str = Field(min_length=1)
    #: Stable pointer into the source, e.g. a recommendation number or heading.
    locator: str = Field(min_length=1)
    text_type: PassageTextType
    text: str | None = None
    populations: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    evidence_confidence: EvidenceConfidence | None = None
    status: SourceStatus = SourceStatus.UNVERIFIED
    date_verified: date | None = None
    synthetic: bool = False

    @model_validator(mode="after")
    def _check_consistency(self) -> EvidencePassage:
        if self.text_type == PassageTextType.LOCATOR_ONLY:
            if self.text:
                raise ValueError("locator_only passages must not store text")
        elif not self.text:
            raise ValueError(f"{self.text_type} passages require text")
        if self.synthetic and self.status == SourceStatus.VERIFIED:
            raise ValueError("synthetic passages can never be marked verified")
        if self.status == SourceStatus.VERIFIED and self.date_verified is None:
            raise ValueError("verified passages require date_verified")
        return self
