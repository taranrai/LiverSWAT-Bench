"""Summaries of scored runs.

Aggregation is case-level: trials of the same item are averaged first, then
items are averaged, so repeated trials are not treated as independent cases.
Primary-eligible records and all other records are always summarised
separately; only the primary partition may be described as benchmark results.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import fmean
from typing import Any

from liverswat_bench.evaluation.dimensions import PROVISIONAL_WEIGHTS, Dimension
from liverswat_bench.evaluation.records import RunManifest
from liverswat_bench.evaluation.score_run import SCORES_FILE, SCORING_MANIFEST_FILE
from liverswat_bench.evaluation.scoring_records import (
    DimensionStatus,
    ScoreRecord,
    ScoringManifest,
)
from liverswat_bench.io import read_jsonl_models
from liverswat_bench.judges.schema import JudgeRecord, JudgeRunManifest

PARTITIONS = ("primary", "non_primary")


class ReportError(RuntimeError):
    pass


@dataclass
class ScoredRun:
    run_dir: Path
    run_manifest: RunManifest
    scoring_manifest: ScoringManifest
    scores: list[ScoreRecord]
    judgements: list[JudgeRecord] = field(default_factory=list)
    judge_manifests: list[JudgeRunManifest] = field(default_factory=list)


def load_scored_run(run_dir: Path) -> ScoredRun:
    scores_path = run_dir / SCORES_FILE
    if not scores_path.is_file():
        raise ReportError(f"{run_dir} has no {SCORES_FILE}; run 'liverswat score' first")
    try:
        run_manifest = RunManifest.model_validate_json((run_dir / "manifest.json").read_text())
        scoring_manifest = ScoringManifest.model_validate_json(
            (run_dir / SCORING_MANIFEST_FILE).read_text()
        )
    except (OSError, ValueError) as exc:
        raise ReportError(f"cannot read manifests in {run_dir}: {exc}") from exc
    records, issues = read_jsonl_models(scores_path, ScoreRecord)
    if issues:
        raise ReportError(f"invalid score records: {issues[0]}")
    judgements: list[JudgeRecord] = []
    judge_manifests: list[JudgeRunManifest] = []
    for path in sorted((run_dir / "judgements").glob("*.jsonl")):
        js, j_issues = read_jsonl_models(path, JudgeRecord)
        if j_issues:
            raise ReportError(f"invalid judge records: {j_issues[0]}")
        judgements.extend(j for _, j in js)
        manifest_path = path.with_name(path.stem + ".manifest.json")
        try:
            judge_manifests.append(JudgeRunManifest.model_validate_json(manifest_path.read_text()))
        except (OSError, ValueError) as exc:
            raise ReportError(f"cannot read judge manifest {manifest_path}: {exc}") from exc
    return ScoredRun(
        run_dir,
        run_manifest,
        scoring_manifest,
        [r for _, r in records],
        judgements,
        judge_manifests,
    )


def _case_mean(values_by_item: dict[str, list[float]]) -> tuple[float | None, int]:
    item_means = [fmean(v) for v in values_by_item.values() if v]
    return (round(fmean(item_means), 4) if item_means else None), len(item_means)


def summarise_partition(records: list[ScoreRecord]) -> dict[str, Any]:
    items = {r.question_id: r for r in records}
    out: dict[str, Any] = {
        "n_records": len(records),
        "n_items": len(items),
        "n_generation_errors": sum(r.response_status == "error" for r in records),
        "items_by_track": dict(Counter(r.provenance.track.value for r in items.values())),
        "items_by_verification_status": dict(
            Counter(r.provenance.verification_status.value for r in items.values())
        ),
        "n_synthetic_items": sum(r.provenance.synthetic for r in items.values()),
    }

    dims: dict[str, Any] = {}
    for dim in Dimension:
        statuses: Counter[str] = Counter()
        reasons: Counter[str] = Counter()
        distribution: Counter[int] = Counter()
        by_item: dict[str, list[float]] = defaultdict(list)
        for r in records:
            ds = next(d for d in r.dimension_scores if d.dimension == dim)
            statuses[ds.status.value] += 1
            if ds.status == DimensionStatus.SCORED:
                by_item[r.question_id].append(ds.score)
                distribution[ds.score] += 1
            elif ds.status in (DimensionStatus.ABSTAINED, DimensionStatus.MISSING):
                reasons[ds.reason] += 1
        mean, n_items_scored = _case_mean(by_item)
        dims[dim.value] = {
            "weight": PROVISIONAL_WEIGHTS[dim],
            "case_level_mean": mean,
            "n_items_scored": n_items_scored,
            "n_records": {s.value: statuses.get(s.value, 0) for s in DimensionStatus},
            "score_distribution": {str(k): distribution[k] for k in sorted(distribution)},
            "abstention_and_missing_reasons": dict(reasons),
        }
    out["dimensions"] = dims

    agg_by_item: dict[str, list[float]] = defaultdict(list)
    for r in records:
        if r.aggregate.status == "complete":
            agg_by_item[r.question_id].append(r.aggregate.score)
    agg_mean, agg_items = _case_mean(agg_by_item)
    out["aggregate"] = {
        "n_records": dict(Counter(r.aggregate.status for r in records)),
        "case_level_mean_of_complete": agg_mean,
        "n_items_with_complete_aggregate": agg_items,
    }

    flags = [(r, f) for r in records for f in r.critical_flags]
    out["critical_flags"] = {
        "n_records_rule_detected": len(
            {r.record_id for r, f in flags if f.status == "rule_detected"}
        ),
        "n_records_needs_review": len(
            {r.record_id for r, f in flags if f.status == "needs_review"}
        ),
        "items_with_rule_detected": sorted(
            {r.question_id for r, f in flags if f.status == "rule_detected"}
        ),
        "n_records_with_unchecked_critical": sum(bool(r.unchecked_critical) for r in records),
        "flags": [
            {
                "record_id": r.record_id,
                "question_id": r.question_id,
                "trial": r.trial,
                "check_id": f.check_id,
                "kind": f.kind.value,
                "status": f.status,
                "description": f.description,
                "excerpt": f.response_excerpts[0] if f.response_excerpts else None,
            }
            for r, f in flags
        ],
    }
    out["check_outcomes"] = dict(
        Counter(f"{c.kind.value}:{c.outcome.value}" for r in records for c in r.checks)
    )
    out["claim_assessments"] = {
        "by_classification": dict(
            Counter(a.classification.value for r in records for a in r.claim_assessments)
        ),
        "n_abstained": sum(a.abstained for r in records for a in r.claim_assessments),
    }
    out["ineligibility_reasons"] = dict(
        Counter(reason for r in items.values() for reason in r.provenance.ineligibility_reasons)
    )
    return out


def summarise_run(run: ScoredRun) -> dict[str, Any]:
    m, sm = run.run_manifest, run.scoring_manifest
    parts = {
        "primary": [s for s in run.scores if s.provenance.primary_eligible],
        "non_primary": [s for s in run.scores if not s.provenance.primary_eligible],
    }
    return {
        "experiment_id": m.experiment_id,
        "status_labels": sm.status_labels,
        "scorer": sm.scorer,
        "scored_at": sm.scored_at.isoformat(),
        "model": {
            k: m.model_settings.get(k)
            for k in (
                "config_id",
                "model_name",
                "model_revision",
                "backend",
                "licence",
                "open_weight",
                "osi_approved_licence",
                "parameter_count",
                "quantisation",
            )
        },
        "generation": m.model_settings.get("generation"),
        "trials": m.trials,
        "dataset": {"path": sm.dataset_path, "sha256": sm.dataset_sha256},
        "registry_files": sm.registry_files,
        "responses_sha256": sm.responses_sha256,
        "git": m.environment.get("git"),
        "weights_note": "Dimension weights are provisional research design choices, "
        "not clinically validated.",
        "partitions": {name: summarise_partition(recs) for name, recs in parts.items()},
    }
