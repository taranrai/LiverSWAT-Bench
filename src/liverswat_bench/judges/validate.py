"""Parse and validate judge output against the item and the evidence actually supplied.

Validation never repairs a judgement into a score. A judgement that cites a
passage the judge was not given (a hallucinated reference), or scores an
evidence-dependent dimension without citing evidence, is marked invalid.
Claims whose text is not in the response, or whose evidence is missing or
invented, are kept but sent to review.
"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from liverswat_bench.datasets.schema import BenchmarkItem
from liverswat_bench.evaluation.dimensions import Dimension
from liverswat_bench.evaluation.rules import normalise
from liverswat_bench.evaluation.scoring_records import ClaimClassification
from liverswat_bench.judges.schema import (
    ClaimJudgement,
    Confidence,
    DimensionJudgement,
    RawJudgeOutput,
)

EVIDENCE_REQUIRED = {Dimension.FACTUAL_ACCURACY, Dimension.UK_EVIDENCE_ALIGNMENT}
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


class JudgeOutputError(ValueError):
    """Output could not be parsed into the required JSON structure."""


def extract_json(text: str) -> dict:
    """Extract one JSON object from model text (plain, fenced, or with surrounding prose)."""
    candidates = [m.group(1) for m in _FENCE.finditer(text)]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    raise JudgeOutputError("no valid JSON object found in judge output")


def parse_output(text: str) -> RawJudgeOutput:
    data = extract_json(text)
    try:
        return RawJudgeOutput.model_validate(data)
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = ".".join(str(p) for p in first["loc"]) or "<output>"
        raise JudgeOutputError(
            f"judge output does not match schema: {loc}: {first['msg']}"
        ) from exc


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", normalise(text)).strip().casefold()


def validate_output(
    raw: RawJudgeOutput,
    item: BenchmarkItem,
    response_text: str,
    supplied_ids: set[str],
) -> tuple[list[DimensionJudgement], list[ClaimJudgement], list[str]]:
    issues: list[str] = []
    applicable = {r.dimension: r.applicable for r in item.scoring_rubric}

    dims: list[DimensionJudgement] = []
    for d in sorted(raw.dimensions, key=lambda x: list(Dimension).index(x.dimension)):
        base = {
            "dimension": d.dimension,
            "evidence_passage_ids": d.evidence_passage_ids,
            "explanation": d.explanation,
            "confidence": d.confidence,
        }
        if not applicable[d.dimension]:
            if not d.abstain:
                issues.append(f"{d.dimension.value}: judge scored a not-applicable dimension")
            dims.append(
                DimensionJudgement(**base, status="not_applicable", reason="rubric: not applicable")
            )
            continue
        invented = sorted(set(d.evidence_passage_ids) - supplied_ids)
        if invented:
            msg = f"cited passage(s) not supplied to the judge: {invented}"
            issues.append(f"{d.dimension.value}: {msg}")
            dims.append(DimensionJudgement(**base, status="invalid", reason=msg))
        elif d.abstain:
            dims.append(DimensionJudgement(**base, status="abstained", reason=d.abstain_reason))
        elif d.dimension in EVIDENCE_REQUIRED and not d.evidence_passage_ids:
            msg = "score given without an evidence reference"
            issues.append(f"{d.dimension.value}: {msg}")
            dims.append(DimensionJudgement(**base, status="invalid", reason=msg))
        else:
            dims.append(DimensionJudgement(**base, status="scored", score=d.score))

    response_norm = _norm(response_text)
    claims: list[ClaimJudgement] = []
    for i, c in enumerate(raw.claims):
        reasons: list[str] = []
        found = _norm(c.text) in response_norm
        if not found:
            reasons.append("claim text not found verbatim in response")
        invented = sorted(set(c.evidence_passage_ids) - supplied_ids)
        if invented:
            reasons.append(f"cited passage(s) not supplied to the judge: {invented}")
        if (
            c.classification in (ClaimClassification.SUPPORTED, ClaimClassification.CONTRADICTED)
            and not c.evidence_passage_ids
        ):
            reasons.append(f"{c.classification.value} without an evidence reference")
        if c.needs_review:
            reasons.append("judge requested review")
        if c.confidence == Confidence.LOW:
            reasons.append("low judge confidence")
        # Validation failures (as opposed to the judge's own uncertainty) are issues.
        issues.extend(
            f"claim {i}: {r}"
            for r in reasons
            if r not in ("judge requested review", "low judge confidence")
        )
        claims.append(
            ClaimJudgement(
                claim_index=i,
                text=c.text,
                text_found_in_response=found,
                classification=c.classification,
                evidence_passage_ids=c.evidence_passage_ids,
                explanation=c.explanation,
                potentially_dangerous=c.potentially_dangerous,
                confidence=c.confidence,
                needs_review=bool(reasons),
                review_reasons=reasons,
            )
        )
    return dims, claims, issues
