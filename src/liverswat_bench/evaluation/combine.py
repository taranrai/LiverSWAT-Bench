"""Combine deterministic rule scores with LLM-judge scores, without overriding rules.

Policy (documented in docs/evaluation_protocol.md):

* Rule scores are preserved unchanged in ``rule``; judge scores are kept per
  judge; the combined view is separate.
* Judge consensus for a dimension needs at least ``min_judges`` canonical
  judgements that scored it, spread <= ``judge_tolerance``. The consensus
  value is the LOWER median (conservative). Larger spread = judges disagree.
* If the rule scored a dimension, the combined score is the rule score. If a
  judge consensus differs from it by >= ``rule_disagreement_threshold``:
  - ``rules_first``: keep the rule score, flag the disagreement;
  - ``rules_first_review_on_disagreement`` (default): send to review (no score).
* If the rule abstained, a judge consensus may fill the dimension ONLY when the
  abstention reason is fillable (the dimension needs judgement, a rule is
  missing, the item defines no checks, or the positive-evidence policy).
  Abstentions because a rule match needs review are NOT filled: they need a
  human. Missing (failed generation) and not-applicable are never filled.
* Judge-flagged dangerous claims are reported separately and never change
  scores or rule-detected critical flags.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from liverswat_bench.evaluation.dimensions import Dimension
from liverswat_bench.evaluation.scoring import SILENCE_REASON, aggregate
from liverswat_bench.evaluation.scoring_records import (
    AggregateScore,
    DimensionScore,
    DimensionStatus,
    ScoreRecord,
)
from liverswat_bench.judges.schema import JudgeRecord

COMBINE_VERSION = "combine-1"

FILLABLE_REASON_PREFIXES = (
    "requires judgement",
    "a check has no detection rule",
    "item defines no",
    SILENCE_REASON,
)


class CombinePolicy(StrEnum):
    RULES_FIRST = "rules_first"
    RULES_FIRST_REVIEW_ON_DISAGREEMENT = "rules_first_review_on_disagreement"


@dataclass(frozen=True)
class CombineSettings:
    policy: CombinePolicy = CombinePolicy.RULES_FIRST_REVIEW_ON_DISAGREEMENT
    min_judges: int = 2
    judge_tolerance: int = 1
    rule_disagreement_threshold: int = 2
    canonical_prompt_version: str = "v1"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CombinedDimension(_Strict):
    dimension: Dimension
    rule_status: DimensionStatus
    rule_score: int | None
    rule_reason: str
    judge_scores: dict[str, int | None]
    judge_statuses: dict[str, str]
    consensus: Literal["consensus", "judges_disagree", "insufficient_judges"]
    consensus_score: int | None = None
    rule_judge_difference: int | None = None
    material_disagreement: bool = False
    combined_status: Literal["scored", "needs_review", "abstained", "missing", "not_applicable"]
    combined_score: int | None = None
    combined_source: Literal[
        "rule", "judge_consensus", "rule_vs_judge_disagreement", "judge_disagreement", "none"
    ]


class DangerousClaim(_Strict):
    judge_id: str
    text: str
    classification: str
    evidence_passage_ids: list[str]
    needs_review: bool


class CombinedRecord(_Strict):
    record_id: str
    question_id: str
    trial: int
    primary_eligible: bool
    combine_version: str = COMBINE_VERSION
    policy: CombinePolicy
    judges: list[str]
    judges_without_valid_output: list[str]
    dimensions: list[CombinedDimension]
    combined_aggregate: AggregateScore
    rule_aggregate: AggregateScore
    judge_flagged_dangerous_claims: list[DangerousClaim] = Field(default_factory=list)
    label: str = "AUTOMATED (RULES + LLM JUDGES) - NOT CLINICAL EXPERT REVIEW"


def _fillable(reason: str) -> bool:
    return reason.startswith(FILLABLE_REASON_PREFIXES)


def canonical_judgements(
    judgements: Sequence[JudgeRecord], prompt_version: str
) -> dict[str, dict[str, JudgeRecord]]:
    """record_id -> judge_id -> the canonical (prompt version, repeat 0) judgement."""
    out: dict[str, dict[str, JudgeRecord]] = defaultdict(dict)
    for j in judgements:
        if j.prompt_version == prompt_version and j.repeat == 0:
            out[j.record_id][j.judge_id] = j
    return out


def combine_record(
    score: ScoreRecord,
    judges: dict[str, JudgeRecord],
    judge_ids: Sequence[str],
    settings: CombineSettings,
) -> CombinedRecord:
    dims: list[CombinedDimension] = []
    combined_for_agg: list[DimensionScore] = []
    for rule in score.dimension_scores:
        dim = rule.dimension
        judge_scores: dict[str, int | None] = {}
        judge_statuses: dict[str, str] = {}
        for jid in judge_ids:
            j = judges.get(jid)
            if j is None or j.status != "ok":
                judge_statuses[jid] = "no_valid_output" if j else "not_run"
                judge_scores[jid] = None
                continue
            dj = next(d for d in j.dimensions if d.dimension == dim)
            judge_statuses[jid] = dj.status
            judge_scores[jid] = dj.score if dj.status == "scored" else None

        scored = sorted(s for s in judge_scores.values() if s is not None)
        consensus_score = None
        if len(scored) >= 2 and scored[-1] - scored[0] > settings.judge_tolerance:
            consensus = "judges_disagree"
        elif scored and len(scored) >= settings.min_judges:
            consensus = "consensus"
            consensus_score = scored[(len(scored) - 1) // 2]  # lower median
        else:
            consensus = "insufficient_judges"

        diff = None
        material = False
        if rule.status == DimensionStatus.SCORED and consensus_score is not None:
            diff = consensus_score - rule.score
            material = abs(diff) >= settings.rule_disagreement_threshold

        if rule.status == DimensionStatus.NOT_APPLICABLE:
            status, value, source = "not_applicable", None, "none"
        elif rule.status == DimensionStatus.MISSING:
            status, value, source = "missing", None, "none"
        elif rule.status == DimensionStatus.SCORED:
            if material and settings.policy == CombinePolicy.RULES_FIRST_REVIEW_ON_DISAGREEMENT:
                status, value, source = "needs_review", None, "rule_vs_judge_disagreement"
            else:
                status, value, source = "scored", rule.score, "rule"
        elif _fillable(rule.reason) and consensus_score is not None:
            status, value, source = "scored", consensus_score, "judge_consensus"
        elif _fillable(rule.reason) and consensus == "judges_disagree":
            status, value, source = "needs_review", None, "judge_disagreement"
        else:
            status, value, source = "abstained", None, "none"

        dims.append(
            CombinedDimension(
                dimension=dim,
                rule_status=rule.status,
                rule_score=rule.score,
                rule_reason=rule.reason,
                judge_scores=judge_scores,
                judge_statuses=judge_statuses,
                consensus=consensus,
                consensus_score=consensus_score,
                rule_judge_difference=diff,
                material_disagreement=material,
                combined_status=status,
                combined_score=value,
                combined_source=source,
            )
        )
        agg_status = {
            "scored": DimensionStatus.SCORED,
            "not_applicable": DimensionStatus.NOT_APPLICABLE,
            "missing": DimensionStatus.MISSING,
        }.get(status, DimensionStatus.ABSTAINED)
        combined_for_agg.append(
            DimensionScore(dimension=dim, status=agg_status, score=value, reason=source)
        )

    dangerous = [
        DangerousClaim(
            judge_id=jid,
            text=c.text,
            classification=c.classification.value,
            evidence_passage_ids=c.evidence_passage_ids,
            needs_review=c.needs_review,
        )
        for jid, j in judges.items()
        if j.status == "ok"
        for c in j.claims
        if c.potentially_dangerous
    ]
    return CombinedRecord(
        record_id=score.record_id,
        question_id=score.question_id,
        trial=score.trial,
        primary_eligible=score.provenance.primary_eligible,
        policy=settings.policy,
        judges=list(judge_ids),
        judges_without_valid_output=[
            jid for jid in judge_ids if jid not in judges or judges[jid].status != "ok"
        ],
        dimensions=dims,
        combined_aggregate=aggregate(combined_for_agg),
        rule_aggregate=score.aggregate,
        judge_flagged_dangerous_claims=dangerous,
    )


def combine(
    scores: Sequence[ScoreRecord],
    judgements: Sequence[JudgeRecord],
    settings: CombineSettings | None = None,
) -> list[CombinedRecord]:
    settings = settings or CombineSettings()
    judge_ids = sorted({j.judge_id for j in judgements})
    canon = canonical_judgements(judgements, settings.canonical_prompt_version)
    return [combine_record(s, canon.get(s.record_id, {}), judge_ids, settings) for s in scores]
